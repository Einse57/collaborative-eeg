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
        # Save uploaded file
        file_path = Path(settings.UPLOAD_DIR) / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
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
    
    return datasets_db[dataset_id]

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

@router.get("/samples/list")
async def list_sample_datasets():
    """List available MNE sample datasets"""
    return {
        'samples': [
            {
                'name': 'sample',
                'description': 'MNE sample dataset (auditory/visual)',
                'size': 'Full dataset (~1.5GB)'
            },
            {
                'name': 'testing',
                'description': 'MNE testing dataset (truncated)',
                'size': 'Small dataset (~50MB)'
            }
        ]
    }

@router.post("/samples/{sample_name}")
async def load_sample_dataset(sample_name: str):
    """Download and load an MNE sample dataset"""
    try:
        file_path = mne_service.download_sample_dataset(sample_name)
        
        # Load with MNE
        raw, dataset_id = mne_service.load_file(file_path)
        metadata = mne_service.get_metadata(raw)
        annotations = mne_service.load_annotations(raw)
        
        # Store dataset info
        dataset_id = f"sample_{sample_name}"
        dataset_info = {
            'id': dataset_id,
            'filename': f"{sample_name}_dataset.fif",
            'file_path': file_path,
            'metadata': metadata,
            'annotations': annotations,
            'is_sample': True
        }
        datasets_db[dataset_id] = dataset_info
        
        return {
            'dataset_id': dataset_id,
            'filename': dataset_info['filename'],
            'metadata': metadata,
            'annotations': annotations
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
