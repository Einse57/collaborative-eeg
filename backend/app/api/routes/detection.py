"""
Event Detection API - Plugin-based

Uses the plugin architecture for modular event detection.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from ...services.mne_service import mne_service
from plugins.detection import plugin_registry
from plugins.detection.loader import load_plugins

router = APIRouter()

# Load plugins on module import
load_plugins()


class DetectionRequest(BaseModel):
    plugin_id: str  # e.g., 'rf', 'cnn'
    segment_duration: float = 2.0
    threshold: float = 0.5
    config: Optional[Dict[str, Any]] = None  # Plugin-specific config


class DetectionResponse(BaseModel):
    success: bool
    plugin_id: str
    plugin_name: str
    detections: List[dict]
    message: str


@router.get("/plugins")
async def list_detection_plugins():
    """Get list of available detection plugins"""
    plugins = plugin_registry.list_plugins(available_only=False)
    return {
        'plugins': plugins,
        'count': len([p for p in plugins if p['available']])
    }


@router.post("/{dataset_id}/detect")
async def detect_events(dataset_id: str, request: DetectionRequest):
    """
    Run event detection using specified plugin.
    
    The application works without any plugins installed.
    If plugins are available, they can be used for automatic detection.
    """
    # Check if dataset is loaded
    if dataset_id not in mne_service.loaded_datasets:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not loaded")
    
    # Get the plugin
    plugin = plugin_registry.get_plugin(request.plugin_id)
    if plugin is None:
        available_plugins = [p['id'] for p in plugin_registry.list_plugins()]
        raise HTTPException(
            status_code=404,
            detail=f"Plugin '{request.plugin_id}' not found. Available plugins: {available_plugins}"
        )
    
    if not plugin.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Plugin '{request.plugin_id}' is not available. "
                   f"Missing dependencies: {', '.join(plugin.requires_dependencies)}"
        )
    
    # Get the data
    raw = mne_service.loaded_datasets[dataset_id]
    
    try:
        # Run detection
        kwargs = {
            'segment_duration': request.segment_duration,
            'threshold': request.threshold
        }
        if request.config:
            kwargs.update(request.config)
        
        detections = plugin_registry.detect(request.plugin_id, raw, **kwargs)
        
        # Save detections as annotations
        from ..routes.annotations import annotations_db
        
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
                'confidence': detection.get('confidence', 1.0),
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
        
        return DetectionResponse(
            success=True,
            plugin_id=request.plugin_id,
            plugin_name=plugin.display_name,
            detections=saved_annotations,
            message=f"Detected {len(detections)} potential events using {plugin.display_name}"
        )
        
    except Exception as e:
        import traceback
        error_detail = f"Error during detection: {str(e)}\n\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=str(e))
