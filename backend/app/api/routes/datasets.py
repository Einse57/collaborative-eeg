"""
Dataset API routes
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional, List
import shutil
from pathlib import Path
import os

from app.services.mne_service import mne_service
from app.core.config import settings

router = APIRouter()

# Ensure upload directory exists
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

# In-memory storage for datasets (for MVP, will use database later)
datasets_db = {}

@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload a neurophysiological data file"""
    try:
        # Enforce max upload size
        contents = await file.read()
        if len(contents) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({len(contents) / (1024**3):.1f} GB). Maximum allowed: {settings.MAX_UPLOAD_SIZE / (1024**3):.0f} GB"
            )

        # Save uploaded file
        file_path = Path(settings.UPLOAD_DIR) / file.filename
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        del contents  # free memory before loading into MNE
        
        # Load with MNE
        raw, dataset_id = mne_service.load_file(str(file_path))
        metadata = mne_service.get_metadata(raw)
        annotations = mne_service.load_annotations(raw)
        
        # Store dataset info
        dataset_info = {
            'id': dataset_id,
            'filename': file.filename,
            'file_path': str(file_path),
            'metadata': metadata,
            'annotations': annotations,
            'uploaded_at': None  # Add timestamp in production
        }
        datasets_db[dataset_id] = dataset_info
        
        return {
            'dataset_id': dataset_id,
            'filename': file.filename,
            'metadata': metadata,
            'annotations': annotations
        }
    
    except Exception as e:
        import traceback
        print(f"Error uploading dataset: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/")
async def list_datasets():
    """Get list of all uploaded datasets"""
    return {
        'datasets': [
            {
                'id': ds['id'],
                'filename': ds['filename'],
                'n_channels': ds['metadata']['n_channels'],
                'duration': ds['metadata']['duration'],
                'sampling_rate': ds['metadata']['sampling_rate']
            }
            for ds in datasets_db.values()
        ]
    }

@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str):
    """Get dataset metadata"""
    if dataset_id not in datasets_db:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    dataset = datasets_db[dataset_id]
    
    # Ensure the dataset is loaded in mne_service
    # If it's not loaded (e.g., after server restart), reload it
    if dataset_id not in mne_service.loaded_datasets:
        try:
            print(f"Dataset {dataset_id} not in memory, reloading from {dataset['file_path']}")
            raw, _ = mne_service.load_file(dataset['file_path'])
            print(f"Successfully reloaded dataset {dataset_id}")
        except Exception as e:
            print(f"Error reloading dataset {dataset_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Could not reload dataset: {str(e)}")
    
    # Ensure we have the complete metadata including duration
    response = {
        'id': dataset['id'],
        'filename': dataset['filename'],
        'file_path': dataset['file_path'],
        'duration': dataset['metadata'].get('duration'),
        'n_channels': dataset['metadata'].get('n_channels'),
        'sampling_rate': dataset['metadata'].get('sampling_rate'),
        'metadata': dataset['metadata'],
        'annotations': dataset.get('annotations', [])
    }
    print(f"Returning dataset {dataset_id} with duration: {response['duration']}")
    return response

@router.get("/{dataset_id}/data")
async def get_dataset_data(
    dataset_id: str,
    start_time: float = Query(0, description="Start time in seconds"),
    duration: float = Query(10, description="Duration in seconds"),
    downsample: int = Query(1, description="Downsample factor"),
    channels: Optional[str] = Query(None, description="Comma-separated channel indices")
):
    """Get signal data chunk"""
    if dataset_id not in datasets_db:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    try:
        channel_list = None
        if channels:
            channel_list = [int(ch.strip()) for ch in channels.split(',')]
        
        data = mne_service.get_data_chunk(
            dataset_id=dataset_id,
            start_time=start_time,
            duration=duration,
            channels=channel_list,
            downsample=downsample
        )
        
        return data
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{dataset_id}/export/edfplus")
async def export_to_edfplus(dataset_id: str):
    """Export dataset with annotations to EDF+ format"""
    if dataset_id not in datasets_db:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    if dataset_id not in mne_service.loaded_datasets:
        raise HTTPException(status_code=400, detail="Dataset not loaded in memory")
    
    try:
        # Import annotations to merge with dataset
        from .annotations import annotations_db
        import mne
        
        # Get the raw data
        raw = mne_service.loaded_datasets[dataset_id]
        print(f"Got raw data for {dataset_id}: {type(raw)}, {raw.info['nchan']} channels")
        
        # Ensure data is loaded in memory for export
        if not raw.preload:
            print("Loading raw data into memory...")
            raw.load_data()
        
        # Create a copy and pick only EDF-compatible channels
        # EDF format works best with EEG, EOG, ECG, EMG channels
        # MEG and other exotic channel types may not export properly
        print(f"Original channel types: {raw.get_channel_types()}")
        
        # Try to pick EEG/EOG/ECG/EMG channels
        try:
            picks = mne.pick_types(raw.info, meg=False, eeg=True, eog=True, ecg=True, emg=True, 
                                   stim=False, exclude='bads')
            if len(picks) > 0:
                raw_copy = raw.copy().pick(picks)
                print(f"Selected {len(picks)} EDF-compatible channels (EEG/EOG/ECG/EMG)")
            else:
                # If no specific types, pick all data channels
                picks = mne.pick_types(raw.info, meg=False, ref_meg=False, exclude='bads')
                if len(picks) > 0:
                    raw_copy = raw.copy().pick(picks)
                    print(f"Selected {len(picks)} data channels")
                else:
                    raw_copy = raw.copy()
                    print("Using all channels (no filtering)")
        except Exception as e:
            print(f"Error filtering channels: {e}, using all channels")
            raw_copy = raw.copy()
        
        print(f"Channels to export: {raw_copy.info['nchan']}")
        print("Created copy of raw data")
        
        # Load current annotations from the dataset
        if dataset_id in annotations_db and annotations_db[dataset_id]:
            print(f"Found {len(annotations_db[dataset_id])} annotations to export")
            
            # Convert our annotations to MNE format
            onsets = []
            durations = []
            descriptions = []
            
            for ann in annotations_db[dataset_id].values():
                onsets.append(ann['onset'])
                durations.append(ann['duration'])
                # Include user info in description for auto-detected events
                desc = ann['description']
                if ann.get('user') and ann['user'].startswith('EventDetector_'):
                    method = ann['user'].replace('EventDetector_', '')
                    confidence = ann.get('confidence', 0)
                    desc = f"{desc} [{method} {confidence:.2%}]"
                descriptions.append(desc)
            
            # Create MNE Annotations object
            annotations_mne = mne.Annotations(
                onset=onsets,
                duration=durations,
                description=descriptions
            )
            
            # Set annotations on the raw copy
            raw_copy.set_annotations(annotations_mne)
            print(f"Added {len(annotations_mne)} annotations to export")
        else:
            print("No annotations to export")
        
        # Create export directory if it doesn't exist
        export_dir = Path(settings.UPLOAD_DIR) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        print(f"Export directory: {export_dir}")
        
        # Generate output filename
        dataset_info = datasets_db[dataset_id]
        base_filename = Path(dataset_info['filename']).stem
        output_filename = f"{base_filename}_with_annotations.edf"
        output_path = export_dir / output_filename
        
        # Export to EDF+
        print(f"Exporting to EDF+ format: {output_path}")
        print(f"Raw data info: channels={raw_copy.info['nchan']}, sfreq={raw_copy.info['sfreq']}, duration={raw_copy.times[-1]:.1f}s")
        print(f"Data shape: {raw_copy.get_data().shape}")
        print(f"Data is preloaded: {raw_copy.preload}")
        
        # Check data range to ensure it's not all zeros
        data_sample = raw_copy.get_data()[:, :1000]  # Check first 1000 samples
        print(f"Data range check - min: {data_sample.min():.6f}, max: {data_sample.max():.6f}, mean: {data_sample.mean():.6f}")
        
        try:
            # EDF physical min/max header fields are limited to 8 characters.
            # MNE stores EEG in Volts internally; edfio converts to µV for EDF,
            # which can overflow the 8-char field for large-amplitude iEEG data.
            # Fix: pass an explicit physical_range in Volts that produces a µV
            # string fitting in 8 chars (max ±9999999 µV = ±9.999999 V).
            data_all = raw_copy.get_data()
            pmin, pmax = float(data_all.min()), float(data_all.max())
            # Convert to µV to check if it fits in 8 chars
            pmin_uv, pmax_uv = pmin * 1e6, pmax * 1e6
            if len(f"{pmin_uv:.0f}") > 8 or len(f"{pmax_uv:.0f}") > 8:
                # Data in Volts is too large for EDF µV headers.
                # Likely the data was loaded in µV but MNE thinks it's Volts.
                # Rescale: divide by 1e6 so MNE's V→µV conversion recovers
                # the original range.
                print(f"Data range in µV would be {pmin_uv:.0f} to {pmax_uv:.0f} (overflows EDF 8-char header)")
                print(f"Rescaling: data appears to already be in µV, correcting units")
                raw_copy.apply_function(lambda x: x * 1e-6, picks='all', channel_wise=False)
                data_all = raw_copy.get_data()
                pmin, pmax = float(data_all.min()), float(data_all.max())
                print(f"New data range: {pmin:.9f} to {pmax:.9f} V ({pmin*1e6:.1f} to {pmax*1e6:.1f} µV)")

            raw_copy.export(str(output_path), fmt='edf', overwrite=True, physical_range='auto')
            print(f"Successfully exported to {output_path}")
            # Check file size
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"Exported file size: {file_size_mb:.2f} MB")
        except Exception as export_error:
            print(f"Export failed: {export_error}")
            print(f"Trying alternative approach...")
            # Some file formats may not support direct export
            # Try writing as FIF first, then converting
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.fif', delete=False) as tmp:
                tmp_path = tmp.name
            try:
                raw_copy.save(tmp_path, overwrite=True)
                raw_temp = mne.io.read_raw_fif(tmp_path, preload=True)
                raw_temp.export(str(output_path), fmt='edf', overwrite=True)
                os.unlink(tmp_path)
                print(f"Successfully exported via FIF intermediate")
            except Exception as e2:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise Exception(f"Failed both direct and indirect export: {export_error}, {e2}")
        
        # Return the file
        return FileResponse(
            path=str(output_path),
            filename=output_filename,
            media_type='application/octet-stream',
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}"
            }
        )
    
    except Exception as e:
        import traceback
        error_detail = f"Error exporting to EDF+: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """Delete a dataset"""
    if dataset_id not in datasets_db:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    dataset = datasets_db[dataset_id]
    
    # Delete file if it's not a sample dataset
    if not dataset.get('is_sample', False):
        file_path = Path(dataset['file_path'])
        if file_path.exists():
            file_path.unlink()
    
    # Remove from memory
    del datasets_db[dataset_id]
    del mne_service.loaded_datasets[dataset_id]
    
    return {"message": "Dataset deleted successfully"}
