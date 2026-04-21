"""
Event Detection API routes (Legacy)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ...services.mne_service import mne_service
from ...services.event_detection import event_detection_service
from ..routes.datasets import datasets_db

router = APIRouter()


class EventDetectionRequest(BaseModel):
    method: str = "rf"  # 'rf' or 'cnn'
    segment_duration: float = 2.0
    threshold: float = 0.5


class EventDetectionResponse(BaseModel):
    success: bool
    method: str
    detections: List[dict]
    message: str


@router.post("/{dataset_id}/detect-events")
async def detect_events(dataset_id: str, request: EventDetectionRequest):
    """
    Automatically detect events in EEG data using specified method (legacy endpoint)
    
    Methods:
    - 'rf': Random Forest with Wavelet features (classical ML)
    - 'cnn': Convolutional Neural Network (deep learning)
    """
    # Check if dataset is loaded — auto-reload if evicted from memory
    if dataset_id not in mne_service.loaded_datasets:
        ds_info = datasets_db.get(dataset_id)
        if ds_info and ds_info.get("file_path"):
            try:
                mne_service.load_file(ds_info["file_path"])
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Could not reload dataset {dataset_id}: {e}",
                )
        else:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not loaded")
    
    raw = mne_service.loaded_datasets[dataset_id]
    
    try:
        if request.method.lower() == 'rf':
            detections = event_detection_service.detect_events_rf(
                raw=raw,
                segment_duration=request.segment_duration,
                threshold=request.threshold
            )
            method_name = "Random Forest (DWT features)"
        
        elif request.method.lower() == 'cnn':
            detections = event_detection_service.detect_events_cnn(
                raw=raw,
                segment_duration=request.segment_duration,
                threshold=request.threshold
            )
            method_name = "CNN (Spectrogram-based)"
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown method: {request.method}. Use 'rf' or 'cnn'"
            )
        
        # Save detections as annotations
        from .annotations import annotations_db
        
        if dataset_id not in annotations_db:
            annotations_db[dataset_id] = {}
        
        saved_annotations = []
        for detection in detections:
            # Generate annotation ID
            ann_id = f"ann_{len(annotations_db[dataset_id]) + 1}_{detection['user']}"
            
            new_annotation = {
                'id': ann_id,
                'dataset_id': dataset_id,
                'onset': detection['onset'],
                'duration': detection['duration'],
                'description': detection['description'],
                'user': detection['user'],
                'confidence': detection.get('confidence', 0.0),
                'method': detection.get('method', ''),
                'created_at': datetime.now().isoformat()
            }
            
            annotations_db[dataset_id][ann_id] = new_annotation
            saved_annotations.append(new_annotation)
        
        # Persist to file
        try:
            all_annotations = list(annotations_db[dataset_id].values())
            mne_service.persist_annotations_to_file(dataset_id, all_annotations)
        except Exception as e:
            print(f"Warning: Could not persist annotations to file: {e}")
        
        return EventDetectionResponse(
            success=True,
            method=method_name,
            detections=saved_annotations,
            message=f"Found and saved {len(saved_annotations)} potential events using {method_name}"
        )
    
    except ImportError as e:
        import traceback
        error_detail = f"Dependencies not installed: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_detail)  # Log to console
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )
    
    except Exception as e:
        import traceback
        error_detail = f"Error during event detection: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_detail)  # Log to console
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )


@router.get("/{dataset_id}/detection-status")
async def get_detection_status(dataset_id: str):
    """Get available detection methods and their status"""
    try:
        from ...services.event_detection import HAS_CLASSICAL_ML, HAS_DEEP_LEARNING
        
        return {
            'dataset_id': dataset_id,
            'available_methods': {
                'rf': {
                    'name': 'Random Forest (Classical ML)',
                    'available': HAS_CLASSICAL_ML,
                    'description': 'Wavelet-based feature extraction with Random Forest classifier',
                    'accuracy': '~95%',
                    'speed': 'Fast'
                },
                'cnn': {
                    'name': 'CNN (Deep Learning)',
                    'available': HAS_DEEP_LEARNING,
                    'description': 'Spectrogram-based image classification with CNN',
                    'accuracy': 'Unknown (pre-trained)',
                    'speed': 'Slower'
                }
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking detection status: {str(e)}"
        )
