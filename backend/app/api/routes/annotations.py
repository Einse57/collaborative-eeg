"""
Annotation API routes
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from ...services.mne_service import mne_service

router = APIRouter()# In-memory storage for annotations (will use database later)
annotations_db = {}

class AnnotationCreate(BaseModel):
    dataset_id: str
    onset: float
    duration: float
    description: str
    user: Optional[str] = "anonymous"

class AnnotationUpdate(BaseModel):
    onset: Optional[float] = None
    duration: Optional[float] = None
    description: Optional[str] = None

@router.get("/{dataset_id}")
async def get_annotations(dataset_id: str):
    """Get all annotations for a dataset"""
    # If annotations not in memory, try to load from the MNE file
    if dataset_id not in annotations_db:
        # Import datasets_db to check if dataset exists
        from .datasets import datasets_db
        
        if dataset_id in mne_service.loaded_datasets:
            # Load annotations from the MNE Raw object
            raw = mne_service.loaded_datasets[dataset_id]
            file_annotations = mne_service.load_annotations(raw)
            
            # Initialize annotations_db for this dataset
            annotations_db[dataset_id] = {}
            
            # Convert file annotations to our format
            for ann in file_annotations:
                annotations_db[dataset_id][ann['id']] = {
                    'id': ann['id'],
                    'dataset_id': dataset_id,
                    'onset': ann['onset'],
                    'duration': ann['duration'],
                    'description': ann['description'],
                    'user': 'from_file',
                    'created_at': ann.get('orig_time', datetime.now().isoformat())
                }
        else:
            return {'annotations': []}
    
    return {'annotations': list(annotations_db[dataset_id].values())}

@router.post("/")
async def create_annotation(annotation: AnnotationCreate, request: Request):
    """Create a new annotation"""
    dataset_id = annotation.dataset_id
    
    if dataset_id not in annotations_db:
        annotations_db[dataset_id] = {}
    
    # Generate annotation ID
    ann_id = f"ann_{len(annotations_db[dataset_id]) + 1}"
    
    new_annotation = {
        'id': ann_id,
        'dataset_id': dataset_id,
        'onset': annotation.onset,
        'duration': annotation.duration,
        'description': annotation.description,
        'user': annotation.user,
        'created_at': datetime.now().isoformat()
    }
    
    annotations_db[dataset_id][ann_id] = new_annotation
    
    # Persist to file automatically
    try:
        all_annotations = list(annotations_db[dataset_id].values())
        mne_service.persist_annotations_to_file(dataset_id, all_annotations)
    except Exception as e:
        print(f"Warning: Could not persist annotations to file: {e}")
    
    # Broadcast to other users via Socket.IO
    try:
        sio = request.app.state.sio
        await sio.emit('annotation_created', new_annotation, room=f"dataset_{dataset_id}")
    except Exception as e:
        print(f"Warning: Could not broadcast annotation_created: {e}")
    
    return new_annotation

@router.put("/{annotation_id}")
async def update_annotation(
    annotation_id: str,
    dataset_id: str,
    update: AnnotationUpdate,
    request: Request
):
    """Update an existing annotation"""
    if dataset_id not in annotations_db or annotation_id not in annotations_db[dataset_id]:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    annotation = annotations_db[dataset_id][annotation_id]
    
    if update.onset is not None:
        annotation['onset'] = update.onset
    if update.duration is not None:
        annotation['duration'] = update.duration
    if update.description is not None:
        annotation['description'] = update.description
    
    annotation['updated_at'] = datetime.now().isoformat()
    
    # Persist to file automatically
    try:
        all_annotations = list(annotations_db[dataset_id].values())
        mne_service.persist_annotations_to_file(dataset_id, all_annotations)
    except Exception as e:
        print(f"Warning: Could not persist annotations to file: {e}")
    
    # Broadcast to other users via Socket.IO
    try:
        sio = request.app.state.sio
        await sio.emit('annotation_updated', annotation, room=f"dataset_{dataset_id}")
    except Exception as e:
        print(f"Warning: Could not broadcast annotation_updated: {e}")
    
    return annotation

@router.delete("/{annotation_id}")
async def delete_annotation(annotation_id: str, dataset_id: str, request: Request):
    """Delete an annotation"""
    if dataset_id not in annotations_db or annotation_id not in annotations_db[dataset_id]:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    del annotations_db[dataset_id][annotation_id]
    
    # Persist to file automatically
    try:
        all_annotations = list(annotations_db[dataset_id].values())
        mne_service.persist_annotations_to_file(dataset_id, all_annotations)
    except Exception as e:
        print(f"Warning: Could not persist annotations to file: {e}")
    
    # Broadcast to other users via Socket.IO
    try:
        sio = request.app.state.sio
        await sio.emit('annotation_deleted', {'id': annotation_id, 'dataset_id': dataset_id}, room=f"dataset_{dataset_id}")
    except Exception as e:
        print(f"Warning: Could not broadcast annotation_deleted: {e}")
    
    return {"message": "Annotation deleted successfully"}

@router.get("/{dataset_id}/export")
async def export_annotations(dataset_id: str, format: str = "json"):
    """Export annotations in specified format"""
    if dataset_id not in annotations_db:
        return {'annotations': []}
    
    annotations = list(annotations_db[dataset_id].values())
    
    if format == "csv":
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=['onset', 'duration', 'description', 'user'])
        writer.writeheader()
        for ann in annotations:
            writer.writerow({
                'onset': ann['onset'],
                'duration': ann['duration'],
                'description': ann['description'],
                'user': ann['user']
            })
        
        return {'format': 'csv', 'data': output.getvalue()}
    
    return {'format': 'json', 'annotations': annotations}
