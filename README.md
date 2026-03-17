# Collaborative EEG Annotation Platform

Browser-based collaborative platform for annotating neurophysiological data. Built with MNE-Python, FastAPI, and React.

## Features

- Load and visualize EEG/MEG data (`.fif`, `.edf`, `.bdf`, `.set`, `.vhdr`, `.mat`, `.h5`)
- Interactive canvas-based signal viewer with pan/zoom
- Drag-to-create annotations with custom types
- Import/export annotations (JSON, CSV)
- Real-time multi-user collaboration via WebSocket
- Plugin-based event detection (CNN, Random Forest, REVE-Large)
- MNE-Python compatible data handling

## Quick Start

**Prerequisites:** Python 3.9+, Node.js 18+

```powershell
.\setup.ps1                  # one-time install
.\configure-firewall.ps1     # one-time, run as Admin
.\start.ps1                  # launches backend + frontend
```

Open http://localhost:3000. Remote collaborators connect to `http://YOUR_IP:3000` (IP shown in console).

### start.ps1 Options

| Command | Behavior |
|---------|----------|
| `.\start.ps1` | Local only, ports 3000/8000 |
| `.\start.ps1 -Network` | LAN access, ports 3000/8000 |
| `.\start.ps1 -Nginx` | Port 80 via nginx (requires Admin) |
| `.\start.ps1 -Network -Nginx` | Port 80 via nginx + LAN access |

The `-Nginx` flag is useful on enterprise networks that block non-standard ports. It requires [nginx for Windows](https://nginx.org/en/download.html) extracted to `C:\nginx`.

## Supported File Formats

| Extension | Format | Notes |
|-----------|--------|-------|
| `.fif` | MNE FIF | Raw data files only (`*raw.fif`, `*_meg.fif`, `*_eeg.fif`) |
| `.edf` | European Data Format | |
| `.bdf` | BioSemi Data Format | |
| `.set` | EEGLAB | |
| `.vhdr` | BrainVision | |
| `.mat` | MATLAB v5/v7/v7.3 | Auto-detects EEG array + companion `*_info.mat` for sfreq & seizure annotations |
| `.h5` | HDF5 / NeuroTec | Reads `data/ieeg` or the largest 2-D dataset |

### Example Datasets

| Format | Source | Link |
|--------|--------|------|
| `.mat` | SWEZ-ETHZ Long-Term iEEG | http://ieeg-swez.ethz.ch/long-term_dataset/ |
| `.h5` | NeuroTec SWEC-iEEG (HDF5) | https://huggingface.co/datasets/NeuroTec/SWEC_iEEG_Dataset/tree/main |
| `.edf` | PhysioNet CHB-MIT Scalp EEG | https://physionet.org/content/chbmit/1.0.0/ |
| `.edf` | PhysioNet EEG Motor Movement | https://physionet.org/content/eegmmidb/1.0.0/ |
| `.fif` | MNE Sample Data | https://mne.tools/stable/documentation/datasets.html |
| `.bdf` | BioSemi example files | https://www.biosemi.com/download.htm |
| `.set` | EEGLAB sample datasets | https://sccn.ucsd.edu/eeglab/downloaddata.php |

## Architecture

```
Browser (React + Socket.IO)
  ├── DatasetManager  — upload / select files
  ├── SignalViewer    — canvas-based waveform display
  └── AnnotationPanel — create / edit / import / export
          │
      HTTP / WebSocket
          │
FastAPI Backend
  ├── Dataset routes   — upload, list, stream data
  ├── Annotation routes — CRUD, export
  ├── Socket.IO hub    — real-time broadcast per dataset room
  └── MNE Service      — load raw data, extract chunks, manage annotations
          │
      In-Memory Storage (datasets + annotations dicts)
```

## Manual Setup

If you prefer not to use the scripts:

```powershell
# Backend
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m app.main                # http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

For network access, add `-- --host` to the frontend command and update `frontend/.env` with your IP.

## API Docs

Interactive Swagger UI at http://localhost:8000/docs when the backend is running.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT

