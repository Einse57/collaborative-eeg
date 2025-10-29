# Collaborative Annotation Platform

Browser-based collaborative platform for annotating neurophysiological data. Built with MNE-Python, FastAPI, and React.

## Overview

This platform provides a web interface for annotating EEG/MEG recordings with real-time multi-user collaboration. It supports standard neurophysiological file formats and integrates with the MNE-Python ecosystem.

### Key Features

- Load and visualize neurophysiological data (.fif, .edf, .bdf, .set, .vhdr)
- Interactive canvas-based signal viewer with time/amplitude controls
- Drag-to-create annotations with live preview
- Custom annotation type definitions
- Import/export annotations (JSON, CSV)
- Automatic persistence to original .fif files
- Real-time multi-user collaboration via WebSocket
- MNE-Python compatible data handling

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser Client                        │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ Dataset Manager │  │Signal Viewer │  │Annotation Panel│ │
│  │  - Upload files │  │- Canvas render│  │ - CRUD ops    │ │
│  │  - Select data  │  │- Pan/Zoom    │  │ - Import/Export│ │
│  └────────┬────────┘  └──────┬───────┘  └────────┬───────┘ │
│           │                   │                    │          │
│           └───────────────────┴────────────────────┘          │
│                               │                               │
│                          React App                            │
│                      Socket.IO Client                         │
└───────────────────────────────┬───────────────────────────────┘
                                │
                    HTTP/WebSocket (localhost:3000)
                                │
┌───────────────────────────────┴───────────────────────────────┐
│                      FastAPI Backend                          │
│  ┌──────────────┐    ┌─────────────────┐   ┌──────────────┐ │
│  │Dataset Routes│    │Annotation Routes│   │Socket.IO Hub │ │
│  │- Upload      │    │- CRUD           │   │- Broadcast   │ │
│  │- List        │    │- Export         │   │- Dataset rooms│ │
│  │- Get data    │    │                 │   │              │ │
│  └──────┬───────┘    └────────┬────────┘   └──────┬───────┘ │
│         │                     │                    │          │
│         └─────────────────────┴────────────────────┘          │
│                               │                               │
│                      ┌────────┴────────┐                      │
│                      │  MNE Service    │                      │
│                      │ - Load raw data │                      │
│                      │ - Get metadata  │                      │
│                      │ - Extract chunks│                      │
│                      └─────────────────┘                      │
│                               │                               │
└───────────────────────────────┴───────────────────────────────┘
                                │
                    ┌───────────┴──────────┐
                    │  In-Memory Storage   │
                    │  - Datasets dict     │
                    │  - Annotations dict  │
                    └──────────────────────┘
```

## Installation

### Prerequisites

- Python 3.9+ with pip
- Node.js 18+ with npm
- 4GB RAM minimum (8GB recommended for large datasets)

### Backend Setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**Dependencies:**
- mne >= 1.5.1
- fastapi >= 0.104.1
- python-socketio >= 5.10.0
- uvicorn >= 0.24.0
- numpy >= 1.26.0

### Frontend Setup

```powershell
cd frontend
npm install
```

**Dependencies:**
- react 18.2.0
- vite 5.4.21
- axios 1.6.2
- socket.io-client 4.7.2

## Running the Platform

### Development Mode

**Terminal 1 - Start Backend:**
```powershell
cd backend
.\venv\Scripts\activate
python -m app.main
```
Server runs at http://localhost:8000

**Terminal 2 - Start Frontend:**
```powershell
cd frontend
npm run dev
```
Client runs at http://localhost:3000

### Quick Start Script

**Local access only:**
```powershell
.\start.ps1
```

**Network access (multi-user):**
```powershell
.\start-network.ps1
```

Starts both backend and frontend in separate PowerShell windows.

## Network Access (Multi-User Setup)

### Quick Setup (Recommended)

1. **Configure firewall** (run ONCE as Administrator):
   ```powershell
   .\configure-firewall.ps1
   ```

2. **Start servers with network access:**
   ```powershell
   .\start-network.ps1
   ```

The script will:
- Detect your network IP automatically
- Check firewall configuration
- Start both servers with network access enabled
- Display URLs for local and network access

### Manual Setup

If you prefer to start servers manually:
### Manual Setup

If you prefer to start servers manually:

1. **Configure firewall** (run as Administrator):
   ```powershell
   .\configure-firewall.ps1
   ```

2. **Start backend:**
   ```powershell
   cd backend
   .\venv\Scripts\activate
   python -m app.main
   ```

3. **Start frontend with network access:**
   ```powershell
   cd frontend
   npm run dev -- --host
   ```

4. **Find your IP address:**
   ```powershell
   ipconfig | findstr IPv4
   ```

5. **Share your network URL:**
   - Share: `http://YOUR_IP:3000`

See `NETWORK_QUICK_START.md` for detailed instructions.

**Note:** Backend already listens on `0.0.0.0:8000` and CORS is configured for local network access.

## Usage Examples

### 1. Loading Data

**Upload a file:**
```
1. Click "Upload File" 
2. Select .fif, .edf, .bdf, .set, or .vhdr file
3. Wait for processing (file is loaded with MNE-Python)
4. Dataset appears in the list
```

**Load MNE sample data:**
```
1. Click "Load Sample (Testing)"
2. Downloads sample_audvis_raw.fif (~50MB, first time only)
3. Dataset loads automatically
```

### 2. Viewing Signals

The signal viewer displays EEG/MEG channels on an HTML5 canvas with:

- **Time Navigation:** Pan left/right buttons or time slider (0 to duration)
- **Zoom Controls:** Zoom in/out adjusts viewport duration (1-10 seconds typical)
- **Amplitude Scaling:** Bigger/smaller buttons adjust signal amplitude
- **Channel Display:** Shows first 20 channels by default, adjustable up to all channels

### 3. Creating Annotations

**Interactive method (recommended):**
```
1. Select annotation type from dropdown (e.g., "BAD_artifact")
2. Click and drag on canvas to mark time span
3. Annotation appears with colored overlay and label
4. Other users see it immediately via WebSocket
```

**Supported annotation types:**
- BAD_artifact, BAD_blink, BAD_movement
- Blink, Movement, Sleep_spindle, K_complex
- Custom types (add via Annotation Panel)

### 4. Managing Annotations

**Add custom types:**
```
1. Enter type name in "Add Custom Annotation Type" field
2. Click "Add Type"
3. Type becomes available in Signal Viewer dropdown
```

**Import annotations:**
```
1. Click "Import" button
2. Select JSON or CSV file
3. Annotations load with auto-type detection
4. New types automatically added to dropdown
```

**Export annotations:**
```
1. Click "Export JSON" or "Export CSV"
2. File downloads to browser downloads folder
3. Compatible with MNE-Python's annotation format
```

**JSON format:**
```json
[
  {
    "id": "ann_1",
    "onset": 10.5,
    "duration": 2.0,
    "description": "BAD_artifact",
    "user": "researcher1"
  }
]
```

**CSV format:**
```csv
onset,duration,description,user
10.5,2.0,BAD_artifact,researcher1
```

### 5. Multi-User Collaboration

**Setup:**
```
1. Open platform in two browser windows (or different browsers)
2. Enter different usernames when prompted
3. Both users load the same dataset
```

**Real-time sync:**
- Annotation created by User A appears immediately for User B
- Deletions sync in real-time
- Header shows connected users count
- Each annotation tagged with creator's username

## API Reference

### Dataset Endpoints

**Upload dataset:**
```http
POST /api/datasets/upload
Content-Type: multipart/form-data

file: <binary>
```

**List datasets:**
```http
GET /api/datasets/
Response: {
  "datasets": [
    {
      "id": "sample_audvis_raw",
      "filename": "sample_audvis_raw.fif",
      "n_channels": 102,
      "duration": 277.714,
      "sampling_rate": 600.614
    }
  ]
}
```

**Get signal data:**
```http
GET /api/datasets/{dataset_id}/data?start_time=0&duration=10&downsample=2
Response: {
  "channel_names": ["MEG 0113", "MEG 0112", ...],
  "data": [[...], [...], ...],
  "times": [0.0, 0.001, ...],
  "sampling_rate": 300.307
}
```

### Annotation Endpoints

**Create annotation:**
```http
POST /api/annotations/
Content-Type: application/json

{
  "dataset_id": "sample_audvis_raw",
  "onset": 10.5,
  "duration": 2.0,
  "description": "BAD_artifact",
  "user": "researcher1"
}
```

**Get annotations:**
```http
GET /api/annotations/{dataset_id}
Response: {
  "annotations": [...]
}
```

**Delete annotation:**
```http
DELETE /api/annotations/{annotation_id}?dataset_id={dataset_id}
```

**Export annotations:**
```http
GET /api/annotations/{dataset_id}/export?format=json
GET /api/annotations/{dataset_id}/export?format=csv
```

### WebSocket Events

**Client emits:**
- `join_dataset`: Join dataset room for updates
- `annotation_created`: Broadcast new annotation
- `annotation_deleted`: Broadcast deletion

**Server emits:**
- `annotation_created`: New annotation from another user
- `annotation_updated`: Annotation modified
- `annotation_deleted`: Annotation removed
- `user_joined`: New user joined dataset

## Project Structure

## Project Structure

```
eeg-annotation-platform/
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── datasets.py          # Dataset CRUD, upload, data retrieval
│   │   │   └── annotations.py       # Annotation CRUD, export
│   │   ├── core/
│   │   │   └── config.py            # Settings (upload dir, API prefix)
│   │   ├── services/
│   │   │   └── mne_service.py       # MNE-Python wrapper, data loading
│   │   └── main.py                  # FastAPI app, Socket.IO server
│   ├── requirements.txt
│   └── uploads/                     # Uploaded datasets (gitignored)
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DatasetManager.jsx   # Upload/select datasets
│   │   │   ├── SignalViewer.jsx     # Canvas rendering, annotations
│   │   │   └── AnnotationPanel.jsx  # CRUD, import/export, custom types
│   │   ├── App.jsx                  # Main app, Socket.IO client
│   │   └── main.jsx                 # React entry point
│   ├── package.json
│   └── vite.config.js               # API proxy configuration
│
├── start.ps1                        # Startup script for Windows
└── README.md
```

## Technical Details

### Signal Rendering

- **Canvas API:** Direct pixel manipulation for performance
- **Coordinate conversion:** Mouse position → time → canvas pixels
- **Auto-normalization:** Each channel scaled independently
- **Rendering order:** Signals → time axis → annotations (ensures labels visible)
- **Viewport management:** Load only visible time window with configurable duration

### Data Handling

- **Chunked loading:** Request data by time window (start_time, duration)
- **Downsampling:** Configurable factor to reduce data transfer
- **In-memory caching:** Backend keeps raw objects in memory (MVP)
- **Format support:** MNE-Python's `read_raw` handles all formats
- **Auto-persistence:** Annotations automatically saved to .fif files on create/update/delete

### Real-time Collaboration

- **Socket.IO rooms:** Users join dataset-specific rooms
- **Event broadcasting:** Skip sender (skip_sid) to avoid duplicate updates
- **State sync:** Annotations reload on remote create/update/delete events
- **Username tracking:** localStorage-based user identification

## Configuration

### Backend (.env or environment variables)

```bash
UPLOAD_DIR=./uploads
API_V1_PREFIX=/api
```

### Frontend (vite.config.js)

```javascript
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/socket.io': 'http://localhost:8000'
  }
}
```

## Development

### API Documentation

Interactive Swagger docs: http://localhost:8000/docs

### Console Logging

**Backend:**
- Dataset loading progress
- Socket.IO connection/disconnection events
- API request logging

**Frontend:**
- Annotation rendering steps
- WebSocket event handling
- Data loading status

### Code Organization

**Backend patterns:**
- Service layer for MNE-Python operations
- In-memory dictionaries for MVP storage
- Async endpoints for FastAPI

**Frontend patterns:**
- React hooks for state management
- useEffect for Socket.IO event handling
- Canvas refs for direct DOM manipulation

## Troubleshooting

### Port conflicts

**Backend (8000):**
```powershell
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

**Frontend (3000):**
```powershell
netstat -ano | findstr :3000
taskkill /PID <pid> /F
```

### MNE data download issues

- First-time sample data download requires internet
- Downloads to `~/mne_data/` (configurable via MNE_DATA environment variable)
- ~50MB for sample_audvis_raw.fif

### WebSocket connection failures

**Check CORS settings:**
```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

**Verify Socket.IO client:**
```javascript
// Browser console
localStorage.getItem('eeg_annotation_username')  // Should show username
```

### Canvas rendering issues

- Check browser console for errors
- Verify dataset has loaded (check Network tab)
- Reduce channel count if performance issues
- Try different viewport duration (1-10 seconds)

### Python compatibility

- NumPy >= 1.26.0 required for Python 3.12+
- MNE-Python >= 1.5.1 for current API
- Virtual environment recommended to avoid conflicts

## Limitations (Current MVP)

- **Storage:** In-memory only, data lost on restart
- **File size:** Limited by available RAM
- **Concurrent users:** No conflict resolution for simultaneous edits
- **Authentication:** Username prompt only, no security
- **Persistence:** Auto-save only works for .fif format (EDF/BDF/SET/VHDR are read-only)
- **Undo/redo:** Not implemented
- **Channel selection:** Shows all channels or limited subset

## Future Enhancements

### Planned Features

**Phase 1 (Current):**
- Drag-to-create annotations
- Multi-user real-time sync
- Import/export JSON/CSV
- Custom annotation types

**Phase 2:**
- PostgreSQL database integration
- User authentication (OAuth2/JWT)
- Annotation editing (resize/move)
- Channel filtering and selection
- Keyboard shortcuts

**Phase 3:**
- Signal processing (filtering, re-referencing)
- Annotation templates and workflows
- Conflict resolution for edits
- Activity audit log
- ML-powered auto-annotation suggestions

## Integration with MNE-Python

### Automatic Persistence (.fif files)

For .fif format files, annotations are automatically persisted to the original file whenever you create, update, or delete an annotation. You can reload the file in MNE-Python and see your annotations:

```python
import mne

# Reload your annotated file
raw = mne.io.read_raw_fif('your_data.fif', preload=True)

# Annotations are already there!
print(raw.annotations)
```

**Note:** Only .fif format supports writing annotations. For other formats (EDF, BDF, SET, VHDR), use the export feature and load manually.

### Loading Exported Annotations (Non-.fif formats)

```python
import mne
import json

# Load your raw data
raw = mne.io.read_raw_fif('your_data.fif', preload=True)

# Import annotations from platform export
with open('annotations_export.json', 'r') as f:
    data = json.load(f)

# Convert to MNE Annotations object
onsets = [a['onset'] for a in data]
durations = [a['duration'] for a in data]
descriptions = [a['description'] for a in data]

annot = mne.Annotations(onset=onsets, duration=durations, description=descriptions)
raw.set_annotations(annot)

# Save to file
raw.save('annotated_data.fif', overwrite=True)
```

### Loading Existing Annotations

The platform automatically loads annotations embedded in MNE-compatible files (.fif) on upload.

## Contributing

Contributions are welcome. This is a research tool in active development.

**Guidelines:**
1. Fork repository
2. Create feature branch
3. Follow existing code style (Python: PEP 8, JavaScript: ESLint)
4. Test with sample data
5. Submit pull request with description

## License

MIT License

## Acknowledgments

Built with MNE-Python (https://mne.tools/)

## References

- MNE-Python Documentation: https://mne.tools/stable/index.html
- Annotation Tutorial: https://mne.tools/stable/auto_tutorials/raw/30_annotate_raw.html
- FastAPI Documentation: https://fastapi.tiangolo.com/
- React Documentation: https://react.dev/

## Support

- Check API docs: http://localhost:8000/docs
- Review console logs (browser DevTools and terminal)
- Verify backend/frontend both running
- Test with MNE sample data first
