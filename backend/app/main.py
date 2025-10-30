"""
Main FastAPI application for EEG/MEG Annotation Platform
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import socketio

from app.api.routes import datasets, annotations
from app.core.config import settings

# Create FastAPI app
app = FastAPI(
    title="EEG/MEG Annotation Platform API",
    description="Multi-user web-based annotation platform for neurophysiological data",
    version="0.1.0"
)

# CORS middleware - Allow connections from any origin for local network collaboration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow any origin for development/local network
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO server for real-time collaboration
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*"  # Allow any origin for development/local network
)

# Wrap with Socket.IO's ASGI app
socket_app = socketio.ASGIApp(sio, app)

# Include API routers
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(annotations.router, prefix="/api/annotations", tags=["annotations"])

@app.get("/")
async def root():
    return {
        "message": "EEG/MEG Annotation Platform API",
        "version": "0.1.0",
        "docs": "/docs"
    }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}

# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.event
async def join_dataset(sid, data):
    """Join a dataset room for real-time updates"""
    dataset_id = data.get('dataset_id')
    await sio.enter_room(sid, f"dataset_{dataset_id}")
    await sio.emit('user_joined', {'user': data.get('user')}, room=f"dataset_{dataset_id}")

@sio.event
async def annotation_created(sid, data):
    """Broadcast new annotation to all users viewing the dataset"""
    dataset_id = data.get('dataset_id')
    await sio.emit('annotation_created', data, room=f"dataset_{dataset_id}", skip_sid=sid)

@sio.event
async def annotation_updated(sid, data):
    """Broadcast annotation update"""
    dataset_id = data.get('dataset_id')
    await sio.emit('annotation_updated', data, room=f"dataset_{dataset_id}", skip_sid=sid)

@sio.event
async def annotation_deleted(sid, data):
    """Broadcast annotation deletion"""
    dataset_id = data.get('dataset_id')
    await sio.emit('annotation_deleted', data, room=f"dataset_{dataset_id}", skip_sid=sid)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:socket_app", host="0.0.0.0", port=8000, reload=True)
