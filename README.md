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

### Manual Installation

If you prefer manual setup:

#### Prerequisites

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

### Development Mode (Manual Start)

If you prefer to start servers manually in separate terminals:

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
**Terminal 2 - Start Frontend:**
```powershell
cd frontend
npm run dev
```
Client runs at http://localhost:3000

**Note:** Manual start requires manually updating `frontend/.env` with your IP address if you want network access.

### Automated Scripts

The platform includes PowerShell scripts for easy setup and deployment:

**setup.ps1** - First-time installation
- Checks for Python 3.9+ and Node.js 18+
- Creates Python virtual environment in `backend/venv`
- Installs all Python dependencies from `requirements.txt`
- Installs all Node.js dependencies from `package.json`
- Auto-detects network IP and creates `frontend/.env`
- Creates `backend/uploads` directory
- Run this once after cloning the repository

**start.ps1** - Start application (use every time)
- Auto-detects current network IP address
- Updates `frontend/.env` with correct backend URL
- Handles dynamic IP changes (DHCP networks)
- Starts backend in new PowerShell window on port 8000
- Starts frontend in new PowerShell window on port 3000
- Displays local and network access URLs
- Run this every time you want to start the platform

**configure-firewall.ps1** - Configure Windows Firewall (run once)
- Must be run as Administrator
- Adds inbound rules for ports 8000 (backend) and 3000 (frontend)
- Enables network access from other computers
- Only needed once per installation

**start-network.ps1** - Alternative start with network features
- Similar to `start.ps1` but with additional network diagnostics
- Checks firewall configuration
- Displays detailed network information
- Use if you have network connectivity issues

### Quick Start Script

## Network Access (Multi-User Setup)

### Quick Setup (3 Steps)

The platform is designed to work seamlessly on your local network:

**1. First time only - Run setup:**
```powershell
.\setup.ps1
```

**2. First time only - Configure firewall as Administrator:**
```powershell
.\configure-firewall.ps1
```

**3. Every time - Start the application:**
```powershell
.\start.ps1
```

That's it! The `start.ps1` script automatically detects your IP and configures everything.

**For remote users:**
- They simply browse to `http://YOUR_IP:3000`
- No installation needed on remote computers
- All users see the same datasets and annotations in real-time
- Annotations sync automatically across all connected clients

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
