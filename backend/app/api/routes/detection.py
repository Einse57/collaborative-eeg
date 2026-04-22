"""
Event Detection API - Plugin-based

Uses the plugin architecture for modular event detection.
Long-running detection jobs run in a background thread and are polled
by the frontend for status / progress.
"""
import asyncio
import threading
import traceback
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...services.mne_service import mne_service
from ..routes.datasets import datasets_db
from plugins import plugin_registry
from plugins.loader import load_plugins_background

router = APIRouter()

# Load plugins in background so the server starts immediately.
# Remote users can access datasets, annotations, etc. right away.
load_plugins_background()


# ---------------------------------------------------------------------------
# Job tracking
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DetectionJob:
    """Tracks a single background detection run."""

    def __init__(self, job_id: str, dataset_id: str, plugin_id: str):
        self.job_id = job_id
        self.dataset_id = dataset_id
        self.plugin_id = plugin_id
        self.status: JobStatus = JobStatus.PENDING
        self.progress: float = 0.0       # 0-100
        self.message: str = "Queued"
        self.detections: List[dict] = []
        self.plugin_name: str = ""
        self.error: Optional[str] = None
        self.created_at: str = datetime.now().isoformat()


# In-memory registry (cleaned on restart — fine for dev)
_jobs: Dict[str, DetectionJob] = {}
_jobs_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class DetectionRequest(BaseModel):
    plugin_id: str  # e.g., 'rf', 'cnn_cbam', 'reve', 'distilled_reve_single'
    segment_duration: float = 2.0
    threshold: float = 0.5
    config: Optional[Dict[str, Any]] = None  # Plugin-specific config


class DetectionResponse(BaseModel):
    success: bool
    plugin_id: str
    plugin_name: str
    detections: List[dict]
    message: str


class JobStartResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    plugin_id: str
    plugin_name: str
    detections: List[dict]
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_detection_job(job: DetectionJob, raw, plugin, kwargs):
    """Executed in a background thread."""
    try:
        job.status = JobStatus.RUNNING
        job.plugin_name = plugin.display_name
        job.message = "Loading model…"
        job.progress = 5.0

        # Inject a progress callback the plugin can use
        def _progress_cb(pct: float, msg: str = ""):
            job.progress = pct
            if msg:
                job.message = msg

        kwargs["_progress_cb"] = _progress_cb

        detections = plugin_registry.detect(job.plugin_id, raw, **kwargs)
        job.progress = 90.0
        job.message = "Saving annotations…"

        # Save detections as annotations
        from .annotations import annotations_db

        if job.dataset_id not in annotations_db:
            annotations_db[job.dataset_id] = {}

        saved_annotations = []
        for detection in detections:
            ann_id = f"ann_{len(annotations_db[job.dataset_id]) + 1}_{detection['user']}"
            new_annotation = {
                "id": ann_id,
                "dataset_id": job.dataset_id,
                "onset": detection["onset"],
                "duration": detection["duration"],
                "description": detection["description"],
                "user": detection["user"],
                "confidence": detection.get("confidence", 1.0),
                "created_at": datetime.now().isoformat(),
            }
            annotations_db[job.dataset_id][ann_id] = new_annotation
            saved_annotations.append(new_annotation)

        # Persist to file
        try:
            all_annotations = list(annotations_db[job.dataset_id].values())
            mne_service.persist_annotations_to_file(job.dataset_id, all_annotations)
        except Exception as e:
            print(f"Warning: Could not persist annotations to file: {e}")

        job.detections = saved_annotations
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.message = (
            f"Detected {len(detections)} potential events "
            f"using {plugin.display_name}"
        )
        print(f"  Job {job.job_id}: completed — {len(detections)} detections")

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.message = f"Detection failed: {exc}"
        print(f"  Job {job.job_id}: FAILED\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/plugins")
async def list_detection_plugins():
    """Get list of available detection plugins"""
    plugins = plugin_registry.list_plugins(available_only=False)
    return {
        'plugins': plugins,
        'count': len([p for p in plugins if p['available']]),
        'loading': plugin_registry.is_loading,
        'loaded': plugin_registry.is_loaded,
    }


@router.post("/{dataset_id}/detect")
async def detect_events(dataset_id: str, request: DetectionRequest):
    """
    Start a detection job.  Returns immediately with a job_id that the
    frontend can poll via GET /detection/jobs/{job_id}.
    """
    # Validate dataset — auto-reload if evicted from memory
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

    # Validate plugin
    plugin = plugin_registry.get_plugin(request.plugin_id)
    if plugin is None:
        available_plugins = [p['id'] for p in plugin_registry.list_plugins()]
        raise HTTPException(
            status_code=404,
            detail=f"Plugin '{request.plugin_id}' not found. Available: {available_plugins}",
        )
    if not plugin.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Plugin '{request.plugin_id}' unavailable — "
                   f"missing: {', '.join(plugin.requires_dependencies)}",
        )

    raw = mne_service.loaded_datasets[dataset_id]

    kwargs: Dict[str, Any] = {
        "segment_duration": request.segment_duration,
        "threshold": request.threshold,
    }
    if request.config:
        kwargs.update(request.config)

    # Create job and launch in background thread
    job_id = uuid.uuid4().hex[:12]
    job = DetectionJob(job_id=job_id, dataset_id=dataset_id, plugin_id=request.plugin_id)
    job.plugin_name = plugin.display_name
    with _jobs_lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_detection_job,
        args=(job, raw, plugin, kwargs),
        daemon=True,
    )
    thread.start()

    return JobStartResponse(
        job_id=job_id,
        status=job.status.value,
        message=f"Detection job started with {plugin.display_name}",
    )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Poll for the status of a detection job."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        message=job.message,
        plugin_id=job.plugin_id,
        plugin_name=job.plugin_name,
        detections=job.detections if job.status == JobStatus.COMPLETED else [],
        error=job.error,
    )
