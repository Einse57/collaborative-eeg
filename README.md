# Collaborative Annotation Platform

Browser-based collaborative platform for annotating neurophysiological data. Built with MNE-Python, FastAPI, and React.

## Overview

This platform provides a web interface for annotating EEG/MEG recordings with real-time multi-user collaboration. It supports neurophysiological file formats and integrates with the MNE-Python ecosystem.

### Key Features

- Load and visualize neurophysiological data (.fif, .edf, .bdf, .set, .vhdr, .mat)
- Interactive canvas-based signal viewer with time/amplitude controls
- Drag-to-create annotations with live preview
- Custom annotation type definitions
- Import/export annotations (JSON, CSV)
- Automatic persistence to original .fif files
- Real-time multi-user collaboration via WebSocket
- MNE-Python compatible data handling


### Datasets

**Supported file formats:**
- `.fif` - FIF files containing **raw data** (must end with `raw.fif`, `_meg.fif`, `_eeg.fif`, etc.)
- `.edf` - European Data Format
- `.bdf` - BioSemi Data Format
- `.set` - EEGLAB format
- `.vhdr` - BrainVision format
- `.mat` - MATLAB files containing iEEG/EEG data (e.g. SWEC-ETHZ dataset)

**Important:** Not all `.fif` files contain raw data. Files like:

**Using MNE sample data:** If you have MNE sample data installed, use files like:
- `sample_audvis_raw.fif` ✅
- `sample_audvis_filt-0-40_raw.fif` ✅
- NOT `sample_audvis-cov.fif` ❌


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

### Quick Start (Recommended)

For a fresh installation, run the automated setup script:

```powershell
.\setup.ps1
```

This will:
- Check for Python 3.9+ and Node.js 18+
- Create Python virtual environment
- Install all backend dependencies
- Install all frontend dependencies
- Auto-detect your network IP address
- Create `.env` file with correct configuration
- Create uploads directory

Then configure firewall (run as Administrator):
```powershell
.\configure-firewall.ps1
```

Finally, start the application:
```powershell
.\start.ps1
```

The `start.ps1` script automatically detects your network IP and updates the `.env` file on each run, so it always uses the correct configuration even if your IP changes.

## Running the Platform

### Quick Start (Recommended)

**First time setup:**
```powershell
.\setup.ps1
```

**Configure firewall (run ONCE as Administrator):**
```powershell
.\configure-firewall.ps1
```

**Start the application:**
```powershell
.\start.ps1
```

The `start.ps1` script automatically:
- Detects your current network IP address
- Updates `frontend/.env` with the correct backend URL
- Starts backend server on `http://0.0.0.0:8000`
- Starts frontend server on `http://0.0.0.0:3000`
- Opens both in separate PowerShell windows

**Access the platform:**
- Local: `http://localhost:3000`
- Network: `http://YOUR_IP:3000` (shown in console output)
- Remote clients just browse to `http://YOUR_IP:3000`


### Automated Scripts

The platform includes PowerShell scripts for easy setup and deployment:

**setup.ps1** - First-time installation
**start.ps1** - Start application (use every time)
**configure-firewall.ps1** - Configure Windows Firewall (run once)
**start-port80.ps1** - Enterprise firewall-friendly startup (requires nginx)

### Enterprise Networks & Firewall Issues

**Solution: Use Port 80 (Standard HTTP)**

The platform includes an nginx-based solution to serve everything on standard HTTP port 80, which works through most enterprise firewalls.

**Setup for port 80:**

1. **Download and install nginx:**
   - Download from https://nginx.org/en/download.html
   - Extract to `C:\nginx`

2. **Run the startup script as Administrator:**
   ```powershell
   # The script will automatically copy nginx.conf to C:\nginx\conf\
   .\start-port80.ps1 -Network
   ```

3. **Access the platform:**
   - Users can access at `http://YOUR_IP` (no port number needed!)
   - API docs at `http://YOUR_IP/docs`

### How It Works

When you run `.\start.ps1`:
1. Script detects your computer's IP address (e.g., 192.168.1.100)
2. Updates `frontend/.env` with `VITE_API_URL=http://192.168.1.100:8000`
3. Starts backend listening on all network interfaces (0.0.0.0:8000)
4. Starts frontend accessible from network (0.0.0.0:3000)
5. Displays URLs for both local and network access

**All clients connect to the same backend**, ensuring:
- Same datasets visible to everyone
- Real-time annotation synchronization via WebSockets
- Collaborative editing with instant updates

## Configuration

### Backend (.env or environment variables)

```bash
UPLOAD_DIR=./uploads
API_V1_PREFIX=/api
```

**Note:** The `uploads` directory is created automatically in `backend/uploads/` by the setup script.

### Frontend (vite.config.js)

```javascript
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/socket.io': 'http://localhost:8000'
  }
}
```

### Python compatibility

- NumPy >= 1.26.0 required for Python 3.12+
- MNE-Python >= 1.5.1 for current API
- Virtual environment recommended to avoid conflicts

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



