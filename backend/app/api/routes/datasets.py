"""
Dataset API routes
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import shutil
from pathlib import Path
import os

from app.services.mne_service import mne_service, _scan_h5_info
from app.services.h5_dataset_ref import H5DatasetRef
from app.core.config import settings

router = APIRouter()

# Ensure upload directory exists
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

# In-memory storage for datasets (for MVP, will use database later)
datasets_db = {}

# H5DatasetRef instances keyed by dataset_id (lazy, zero-memory references)
h5_refs: dict[str, H5DatasetRef] = {}

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
    
    # Ensure the dataset is loaded in mne_service (skip for H5 refs — they're lazy)
    # If it's not loaded (e.g., after server restart), reload it
    if dataset_id not in h5_refs and dataset_id not in mne_service.loaded_datasets:
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

        # Use H5DatasetRef for lazy H5 datasets (no MNE, no memory)
        if dataset_id in h5_refs:
            ref = h5_refs[dataset_id]
            data_arr, times_arr = ref.read_chunk(
                start_sec=start_time,
                duration_sec=duration,
                channels=channel_list,
            )
            if channel_list is None:
                channel_indices = list(range(ref.n_channels))
            else:
                channel_indices = channel_list

            # Downsample
            if downsample > 1:
                data_arr = data_arr[:, ::downsample]
                times_arr = times_arr[::downsample]

            return {
                "data": data_arr.tolist(),
                "times": times_arr.tolist(),
                "channel_indices": channel_indices,
                "channel_names": [ref.ch_names[i] for i in channel_indices],
                "sampling_rate": ref.fs / downsample,
            }

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


# ── H5 local file browser endpoints ──────────────────────────────────────

# Allowed root directories for browsing (prevents arbitrary filesystem access)
# Configured via H5_BROWSE_ROOTS env var (comma-separated paths).
# Additional roots can be registered at runtime via POST /h5/roots.
_h5_config_roots: list[Path] = [Path(settings.UPLOAD_DIR).resolve()]
if settings.H5_BROWSE_ROOTS:
    _h5_config_roots.extend(
        Path(p.strip()).resolve() for p in settings.H5_BROWSE_ROOTS.split(",") if p.strip()
    )
_h5_session_roots: list[Path] = []   # added at runtime via the API


def _all_h5_roots() -> list[Path]:
    return _h5_config_roots + _h5_session_roots


def _is_path_allowed(p: Path) -> bool:
    """Check that p is under one of the allowed roots."""
    resolved = p.resolve()
    return any(
        resolved == root or root in resolved.parents
        for root in _all_h5_roots()
    )


@router.get("/h5/roots")
async def list_h5_roots():
    """Return the list of allowed H5 browse roots."""
    roots = []
    for r in _all_h5_roots():
        exists = r.exists()
        roots.append({"path": str(r), "exists": exists})
    return {"roots": roots}


class H5AddRootRequest(BaseModel):
    path: str


@router.post("/h5/roots")
async def add_h5_root(req: H5AddRootRequest):
    """Register a new browse root for this server session."""
    p = Path(req.path).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {req.path}")
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    if p not in _all_h5_roots():
        _h5_session_roots.append(p)
    return {"path": str(p), "roots": [str(r) for r in _all_h5_roots()]}


@router.get("/h5/browse")
async def browse_h5_directory(
    path: str = Query(None, description="Directory to browse (defaults to first allowed root)"),
):
    """Browse a local directory for H5 files.

    Returns list of patient folders and H5 files in the directory.
    Only directories under allowed roots are accessible.
    """
    if path is None:
        # Default to first allowed root
        path = str(_all_h5_roots()[0])
    p = Path(path)
    if not _is_path_allowed(p):
        raise HTTPException(status_code=403, detail=f"Path outside allowed directories. Add it first via the \"Add Root\" button.")
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    entries = []
    try:
        for child in sorted(p.iterdir()):
            if child.name.startswith("."):
                continue
            if child.is_dir():
                # Count H5 files inside
                h5_count = len(list(child.glob("*.h5")))
                entries.append({
                    "name": child.name,
                    "path": str(child),
                    "type": "directory",
                    "h5_count": h5_count,
                })
            elif child.suffix.lower() == ".h5":
                entries.append({
                    "name": child.name,
                    "path": str(child),
                    "type": "file",
                    "size_mb": child.stat().st_size / (1024 ** 2),
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"path": str(p), "entries": entries}


@router.get("/h5/inspect")
async def inspect_h5_file(
    path: str = Query(..., description="Path to H5 file"),
):
    """Inspect an H5 file: return metadata, channel count, duration,
    seizure annotations, and estimated memory usage — without loading data.
    """
    p = Path(path)
    if not _is_path_allowed(p):
        raise HTTPException(status_code=403, detail="Path outside allowed directories")
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    if p.suffix.lower() != ".h5":
        raise HTTPException(status_code=400, detail="Not an H5 file")

    try:
        info = _scan_h5_info(str(p))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading H5: {e}")

    # Estimate memory for full load (float64)
    mem_gb = info["n_channels"] * info["n_samples"] * 8 / (1024 ** 3)

    return {
        "path": str(p),
        "patient_id": p.stem.replace("_total", "").split("_part_")[0],
        **info,
        "estimated_memory_gb": round(mem_gb, 2),
    }


class H5LoadRequest(BaseModel):
    path: str
    start_sec: float = 0
    duration_sec: Optional[float] = None
    lazy: bool = True  # True = H5DatasetRef (no memory), False = load into MNE


@router.post("/h5/load")
async def load_h5_file(req: H5LoadRequest):
    """Load an H5 file (or segment) into the annotation platform.

    With lazy=True (default), registers a zero-memory H5DatasetRef that
    serves data on demand via h5py random-access reads.
    With lazy=False, loads the segment fully into an MNE RawArray.

    Returns dataset_id, metadata, and annotations — same shape as upload.
    """
    p = Path(req.path)
    if not _is_path_allowed(p):
        raise HTTPException(status_code=403, detail="Path outside allowed directories")
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.path}")

    try:
        if req.lazy and req.duration_sec is None and req.start_sec == 0:
            # Lazy mode — register H5DatasetRef, no signal in memory
            info = _scan_h5_info(str(p))
            info["path"] = str(p)
            ref = H5DatasetRef.from_scan(info)
            patient_id = p.stem.replace("_total", "").split("_part_")[0]
            dataset_id = f"h5_{patient_id}"
            h5_refs[dataset_id] = ref

            metadata = ref.get_metadata()
            annotations = ref.get_annotations()

            datasets_db[dataset_id] = {
                "id": dataset_id,
                "filename": p.name,
                "file_path": str(p),
                "metadata": metadata,
                "annotations": annotations,
                "uploaded_at": None,
            }

            return {
                "dataset_id": dataset_id,
                "filename": p.name,
                "metadata": metadata,
                "annotations": annotations,
            }
        else:
            # Eager mode — load segment into MNE RawArray
            raw, dataset_id = mne_service.load_file(
                str(p), start_sec=req.start_sec, duration_sec=req.duration_sec,
            )
            metadata = mne_service.get_metadata(raw)
            annotations = mne_service.load_annotations(raw)

            datasets_db[dataset_id] = {
                "id": dataset_id,
                "filename": p.name,
                "file_path": str(p),
                "metadata": metadata,
                "annotations": annotations,
                "uploaded_at": None,
            }

            return {
                "dataset_id": dataset_id,
                "filename": p.name,
                "metadata": metadata,
                "annotations": annotations,
            }
    except Exception as e:
        import traceback
        print(f"Error loading H5: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_id}/envelope")
async def get_dataset_envelope(
    dataset_id: str,
    points: int = Query(2000, description="Number of envelope points"),
):
    """Get a downsampled min/max envelope of the full recording.

    Only available for H5DatasetRef datasets (lazy mode).
    Returns arrays suitable for drawing a full-timeline overview bar.
    """
    if dataset_id not in h5_refs:
        raise HTTPException(
            status_code=400,
            detail="Envelope only available for lazy-loaded H5 datasets",
        )
    ref = h5_refs[dataset_id]
    try:
        env = ref.get_envelope(target_points=points)
        return {
            "times": env["times"].tolist(),
            "env_min": env["env_min"].tolist(),
            "env_max": env["env_max"].tolist(),
            "n_channels": env["n_channels"],
            "duration": ref.duration_seconds,
            "seizures": ref.seizures,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
