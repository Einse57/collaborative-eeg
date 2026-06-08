"""
MNE Service for handling neurophysiological data files
"""
import mne
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json


# ── H5 helpers (SWEZ-ETHZ iEEG HDF5 format) ──────────────────────────────

def _scan_h5_info(file_path: str) -> Dict:
    """Read H5 metadata without loading signal data into memory.

    Returns dict with: n_channels, n_samples, fs, duration_hours,
    size_gb, seizures, is_vds_broken, part_files.
    """
    import h5py
    try:
        import hdf5plugin  # noqa: F401 — register Blosc decompressor
    except ImportError:
        pass

    p = Path(file_path)
    f = h5py.File(file_path, "r")

    # Sampling rate
    fs = None
    for key in ["data/Fs", "info/fs", "info/Fs", "info/sampling_rate"]:
        if key in f:
            fs = float(f[key][()])
            break
    if fs is None and "sampling_rate" in f.attrs:
        fs = float(f.attrs["sampling_rate"])
    if fs is None:
        fs = 512.0

    ieeg = f["data/ieeg"]
    n_ch = ieeg.shape[0]
    n_samples = ieeg.shape[1]

    # Seizure annotations
    seizures = []
    if "data/seizures" in f:
        sz_data = f["data/seizures"][()]
        seizures = [
            {"onset": float(row[0]["onsets"]), "offset": float(row[0]["offsets"])}
            for row in sz_data
        ]
    elif "annotations_start" in f:
        starts = f["annotations_start"][()].ravel().tolist()
        stops = f["annotations_stop"][()].ravel().tolist()
        seizures = [{"onset": s, "offset": e} for s, e in zip(starts, stops)]

    # Check for broken VDS
    is_vds_broken = False
    if "_total" in p.stem:
        test = ieeg[:, :min(512, n_samples)]
        if np.all(test == 0):
            is_vds_broken = True

    # Find part files
    patient_id = p.stem.replace("_total", "").split("_part_")[0]
    part_files = sorted(
        p.parent.glob(f"{patient_id}_part_*.h5"),
        key=lambda x: int(x.stem.split("_part_")[1]),
    )

    # If VDS broken, compute total samples from parts
    if is_vds_broken and part_files:
        n_samples = 0
        for pf in part_files:
            with h5py.File(str(pf), "r") as pf_h:
                n_samples += pf_h["data/ieeg"].shape[1]

    f.close()

    duration_s = n_samples / fs
    size_bytes = p.stat().st_size
    if is_vds_broken and part_files:
        size_bytes = sum(pf.stat().st_size for pf in part_files)

    return {
        "n_channels": n_ch,
        "n_samples": n_samples,
        "fs": fs,
        "duration_seconds": duration_s,
        "duration_hours": duration_s / 3600,
        "size_gb": size_bytes / (1024 ** 3),
        "seizures": seizures,
        "n_seizures": len(seizures),
        "is_vds_broken": is_vds_broken,
        "part_files": [str(pf) for pf in part_files],
    }


def _load_h5_as_raw(
    file_path: str,
    start_sec: float = 0,
    duration_sec: Optional[float] = None,
) -> mne.io.RawArray:
    """Load SWEZ-ETHZ H5 file (or segment) as MNE RawArray.

    Args:
        file_path: Path to *_total.h5 or *_part_N.h5
        start_sec: Start time in seconds (0 = beginning)
        duration_sec: Duration to load in seconds (None = entire file)
    """
    import h5py
    try:
        import hdf5plugin  # noqa: F401
    except ImportError:
        pass

    info = _scan_h5_info(file_path)
    fs = info["fs"]
    n_ch = info["n_channels"]

    # Determine sample range
    start_sample = int(start_sec * fs)
    if duration_sec is not None:
        end_sample = min(start_sample + int(duration_sec * fs), info["n_samples"])
    else:
        end_sample = info["n_samples"]

    # Read data — handle VDS fallback
    if info["is_vds_broken"] and info["part_files"]:
        # Read from part files
        chunks = []
        offset = 0
        for pf_path in info["part_files"]:
            with h5py.File(pf_path, "r") as pf_h:
                pf_samples = pf_h["data/ieeg"].shape[1]
                pf_end = offset + pf_samples
                if pf_end <= start_sample:
                    offset = pf_end
                    continue
                if offset >= end_sample:
                    break
                local_start = max(0, start_sample - offset)
                local_end = min(pf_samples, end_sample - offset)
                chunks.append(np.array(pf_h["data/ieeg"][:, local_start:local_end],
                                       dtype=np.float64))
                offset = pf_end
        data = np.concatenate(chunks, axis=1) if chunks else np.zeros((n_ch, 0))
    else:
        f = h5py.File(file_path, "r")
        data = np.array(f["data/ieeg"][:, start_sample:end_sample], dtype=np.float64)
        f.close()

    # Build MNE RawArray
    ch_names = [f"iEEG{i:03d}" for i in range(n_ch)]
    ch_types = ["eeg"] * n_ch
    mne_info = mne.create_info(ch_names=ch_names, sfreq=fs, ch_types=ch_types)
    raw = mne.io.RawArray(data, mne_info)

    # Add seizure annotations (adjusted for segment offset)
    if info["seizures"]:
        onsets, durations, descriptions = [], [], []
        seg_start = start_sec
        seg_end = end_sample / fs
        for sz in info["seizures"]:
            sz_on = sz["onset"]
            sz_off = sz["offset"]
            if sz_off <= seg_start or sz_on >= seg_end:
                continue
            local_on = max(sz_on - seg_start, 0.0)
            local_off = min(sz_off - seg_start, seg_end - seg_start)
            onsets.append(local_on)
            durations.append(local_off - local_on)
            descriptions.append("Seizure")
        if onsets:
            raw.set_annotations(mne.Annotations(
                onset=onsets, duration=durations, description=descriptions
            ))

    return raw


# ── .mat helpers (SWEC-ETHZ iEEG format) ──────────────────────────────────

_EEG_KEYS = ["EEG", "eeg", "data", "ieeg", "raw", "X", "x"]
_SFREQ_KEYS = ["fs", "Fs", "sfreq", "sampling_rate", "SamplingRate", "srate"]


def _load_mat_as_raw(file_path: str) -> mne.io.RawArray:
    """Load a SWEC-ETHZ style .mat file as an MNE RawArray.

    Searches for common key names for the EEG data array and sampling
    frequency.  Falls back to the largest 2-D array and 512 Hz if the
    expected keys are not found.
    """
    from scipy.io import loadmat

    mat = loadmat(file_path)

    # --- Find EEG data array ---
    data = None
    for key in _EEG_KEYS:
        if key in mat and isinstance(mat[key], np.ndarray) and mat[key].ndim == 2:
            data = mat[key]
            break
    if data is None:
        best_key, best_size = None, 0
        for k, v in mat.items():
            if k.startswith("__"):
                continue
            if isinstance(v, np.ndarray) and v.ndim == 2:
                sz = v.shape[0] * v.shape[1]
                if sz > best_size:
                    best_key, best_size = k, sz
        if best_key is not None:
            data = mat[best_key]
    if data is None:
        raise ValueError(f"No 2-D EEG array found in {file_path}")

    data = np.asarray(data, dtype=np.float64)

    # Expect (channels, samples) — transpose if rows >> cols
    if data.shape[0] > data.shape[1] * 4:
        data = data.T

    # --- Sampling frequency ---
    sfreq = None
    for key in _SFREQ_KEYS:
        if key in mat:
            try:
                sfreq = float(np.asarray(mat[key]).squeeze())
                break
            except Exception:
                pass
    if sfreq is None:
        sfreq = 512.0

    # --- Build MNE RawArray ---
    n_channels = data.shape[0]
    ch_names = [f"iEEG{i:03d}" for i in range(n_channels)]
    ch_types = ["eeg"] * n_channels
    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types=ch_types)

    # Embed seizure annotations from companion *_info.mat if present
    info_path = _find_companion_info(file_path)
    raw = mne.io.RawArray(data, info)

    # First try inline seizure keys (demo/trimmed files embed them)
    annots = _annotations_from_inline(mat, n_samples=data.shape[1], sfreq=sfreq)
    if len(annots) == 0 and info_path is not None:
        annots = _load_seizure_annotations(info_path, file_path, sfreq,
                                           n_samples=data.shape[1])
    if len(annots) > 0:
        raw.set_annotations(annots)

    return raw


def _find_companion_info(mat_path: str) -> Optional[str]:
    """Look for <PatientID>_info.mat beside or in same directory tree."""
    p = Path(mat_path)
    stem = p.stem  # e.g. "ID03_89h"
    patient_id = stem.split("_")[0]  # "ID03"

    # Check same directory
    info = p.parent / f"{patient_id}_info.mat"
    if info.is_file():
        return str(info)

    # Check for demo companion (<stem>_info.mat)
    info = p.parent / f"{stem}_info.mat"
    if info.is_file():
        return str(info)

    # Check parent directory (datasets/ may have flat layout)
    info = p.parent.parent / patient_id / f"{patient_id}_info.mat"
    if info.is_file():
        return str(info)

    return None


def _annotations_from_inline(mat: dict, n_samples: int, sfreq: float) -> mne.Annotations:
    """Extract seizure annotations stored directly in the .mat file."""
    sb_key = next((k for k in ("seizure_begin", "seizure_start") if k in mat), None)
    se_key = next((k for k in ("seizure_end", "seizure_stop") if k in mat), None)
    if sb_key is None or se_key is None:
        return mne.Annotations(onset=[], duration=[], description=[])

    begins = np.asarray(mat[sb_key], dtype=float).flatten()
    ends = np.asarray(mat[se_key], dtype=float).flatten()
    file_duration = n_samples / sfreq

    onsets, durations, descriptions = [], [], []
    for b, e in zip(begins, ends):
        if b < 0 or b >= file_duration:
            continue
        e = min(e, file_duration)
        onsets.append(float(b))
        durations.append(float(e - b))
        descriptions.append("Seizure")

    return mne.Annotations(onset=onsets, duration=durations, description=descriptions)


def _load_seizure_annotations(
    info_path: str,
    mat_path: str,
    sfreq: float,
    n_samples: int,
) -> mne.Annotations:
    """Extract seizure onset/offset from *_info.mat and map them to this file's time range."""
    from scipy.io import loadmat

    mat = loadmat(info_path)
    sb_key = next((k for k in ("seizure_begin", "seizure_start", "Seizure_begin") if k in mat), None)
    se_key = next((k for k in ("seizure_end", "seizure_stop", "Seizure_end") if k in mat), None)
    if sb_key is None or se_key is None:
        return mne.Annotations(onset=[], duration=[], description=[])

    begins = np.asarray(mat[sb_key], dtype=float).flatten()
    ends = np.asarray(mat[se_key], dtype=float).flatten()

    # Determine this file's absolute time range
    # Convention: <ID>_<H>h.mat covers [H*3600, (H+1)*3600) seconds
    stem = Path(mat_path).stem
    parts = stem.split("_")
    hour_part = [p for p in parts if p.endswith("h")]
    if hour_part:
        try:
            hour_idx = int(hour_part[0].rstrip("h"))
        except ValueError:
            return mne.Annotations(onset=[], duration=[], description=[])
    else:
        return mne.Annotations(onset=[], duration=[], description=[])

    file_start_s = hour_idx * 3600
    file_end_s = file_start_s + n_samples / sfreq

    onsets, durations, descriptions = [], [], []
    for b, e in zip(begins, ends):
        if e <= file_start_s or b >= file_end_s:
            continue
        # Clip to file boundaries
        local_start = max(b - file_start_s, 0.0)
        local_end = min(e - file_start_s, file_end_s - file_start_s)
        onsets.append(local_start)
        durations.append(local_end - local_start)
        descriptions.append("Seizure")

    return mne.Annotations(onset=onsets, duration=durations, description=descriptions)

class MNEService:
    """Service for MNE-Python operations"""
    
    def __init__(self):
        self.loaded_datasets = {}  # Cache for loaded datasets
        self.dataset_file_paths = {}  # Track original file paths for persistence
    
    def load_file(self, file_path: str, start_sec: float = 0,
                  duration_sec: Optional[float] = None) -> Tuple[mne.io.Raw, str]:
        """Load a neurophysiological data file"""
        file_ext = Path(file_path).suffix.lower()
        
        # .mat files need special handling (not an MNE built-in format)
        if file_ext == '.mat':
            raw = _load_mat_as_raw(file_path)
            dataset_id = Path(file_path).stem
            self.loaded_datasets[dataset_id] = raw
            self.dataset_file_paths[dataset_id] = file_path
            return raw, dataset_id

        # .h5 files — SWEZ-ETHZ iEEG format
        if file_ext == '.h5':
            raw = _load_h5_as_raw(file_path, start_sec=start_sec,
                                  duration_sec=duration_sec)
            stem = Path(file_path).stem
            # Make dataset_id unique for segments
            if start_sec > 0 or duration_sec is not None:
                dataset_id = f"{stem}_s{int(start_sec)}"
                if duration_sec is not None:
                    dataset_id += f"_d{int(duration_sec)}"
            else:
                dataset_id = stem
            self.loaded_datasets[dataset_id] = raw
            self.dataset_file_paths[dataset_id] = file_path
            return raw, dataset_id

        loaders = {
            '.fif': mne.io.read_raw_fif,
            '.edf': mne.io.read_raw_edf,
            '.bdf': mne.io.read_raw_bdf,
            '.set': mne.io.read_raw_eeglab,
            '.vhdr': mne.io.read_raw_brainvision,
        }
        
        loader = loaders.get(file_ext)
        if not loader:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        try:
            raw = loader(file_path, preload=False)
        except ValueError as e:
            if "Could not find measurement data" in str(e):
                raise ValueError(
                    f"This file does not contain raw EEG/MEG data. "
                    f"It may be a covariance matrix, forward solution, or other FIF file type. "
                    f"Please upload a raw data file (should end with 'raw.fif' or '_meg.fif', '_eeg.fif', etc.)"
                )
            raise
        
        dataset_id = Path(file_path).stem
        self.loaded_datasets[dataset_id] = raw
        self.dataset_file_paths[dataset_id] = file_path  # Track file path
        
        return raw, dataset_id
    
    def get_metadata(self, raw: mne.io.Raw) -> Dict:
        """Extract metadata from Raw object"""
        # Get channel types - use the get_channel_types method
        try:
            channel_types = raw.get_channel_types()
        except:
            # Fallback: extract from info
            channel_types = ['unknown'] * len(raw.ch_names)
        
        # Handle meas_date which can be datetime or None
        meas_date_str = None
        if raw.info.get('meas_date') is not None:
            try:
                if hasattr(raw.info['meas_date'], 'isoformat'):
                    meas_date_str = raw.info['meas_date'].isoformat()
                else:
                    meas_date_str = str(raw.info['meas_date'])
            except:
                pass
        
        # Calculate duration safely
        try:
            duration = float(raw.times[-1]) if len(raw.times) > 0 else 0.0
        except:
            # Fallback calculation if times array is problematic
            duration = float(len(raw.times)) / float(raw.info['sfreq']) if raw.info['sfreq'] > 0 else 0.0
        
        return {
            'n_channels': len(raw.ch_names),
            'n_samples': len(raw.times),
            'sampling_rate': raw.info['sfreq'],
            'duration': duration,
            'channel_names': raw.ch_names,
            'channel_types': channel_types,
            'meas_date': meas_date_str,
            'highpass': raw.info.get('highpass'),
            'lowpass': raw.info.get('lowpass'),
        }
    
    def get_data_chunk(
        self,
        dataset_id: str,
        start_time: float = 0,
        duration: float = 10,
        channels: Optional[List[int]] = None,
        downsample: int = 1
    ) -> Dict:
        """Get a chunk of signal data"""
        if dataset_id not in self.loaded_datasets:
            raise ValueError(f"Dataset {dataset_id} not loaded")
        
        raw = self.loaded_datasets[dataset_id]
        sfreq = raw.info['sfreq']
        
        # Validate and sanitize inputs to prevent NaN/inf issues
        import math
        if not math.isfinite(start_time) or not math.isfinite(duration):
            raise ValueError(f"Invalid time parameters: start_time={start_time}, duration={duration}")
        
        # Ensure non-negative values
        start_time = max(0, start_time)
        duration = max(0.1, duration)
        
        # Ensure we don't go beyond the recording
        max_time = raw.times[-1]
        if start_time >= max_time:
            start_time = max(0, max_time - duration)
        if start_time + duration > max_time:
            duration = max_time - start_time
        
        start_sample = int(start_time * sfreq)
        end_sample = int((start_time + duration) * sfreq)
        
        if channels is None:
            data, times = raw[:, start_sample:end_sample]
            channel_indices = list(range(len(raw.ch_names)))
        else:
            data, times = raw[channels, start_sample:end_sample]
            channel_indices = channels
        
        # Downsample if requested
        if downsample > 1:
            data = data[:, ::downsample]
            times = times[::downsample]
        
        return {
            'data': data.tolist(),
            'times': times.tolist(),
            'channel_indices': channel_indices,
            'channel_names': [raw.ch_names[i] for i in channel_indices],
            'sampling_rate': sfreq / downsample
        }
    
    def load_annotations(self, raw: mne.io.Raw) -> List[Dict]:
        """Extract annotations from Raw object"""
        if raw.annotations is None or len(raw.annotations) == 0:
            return []
        
        annotations = []
        for i, ann in enumerate(raw.annotations):
            try:
                orig_time_str = None
                if raw.annotations.orig_time is not None:
                    # Handle different types of orig_time (datetime, float, etc.)
                    if hasattr(raw.annotations.orig_time, 'isoformat'):
                        orig_time_str = raw.annotations.orig_time.isoformat()
                    else:
                        orig_time_str = str(raw.annotations.orig_time)
                
                annotations.append({
                    'id': f"ann_{i}",
                    'onset': float(ann['onset']),
                    'duration': float(ann['duration']),
                    'description': str(ann['description']),
                    'orig_time': orig_time_str
                })
            except Exception as e:
                print(f"Warning: Could not parse annotation {i}: {e}")
                continue
        
        return annotations
    
    def save_annotations(
        self,
        annotations: List[Dict],
        output_path: str,
        format: str = 'json'
    ) -> str:
        """Save annotations to file"""
        if format == 'json':
            with open(output_path, 'w') as f:
                json.dump(annotations, f, indent=2)
        elif format == 'csv':
            import csv
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['onset', 'duration', 'description'])
                writer.writeheader()
                for ann in annotations:
                    writer.writerow({
                        'onset': ann['onset'],
                        'duration': ann['duration'],
                        'description': ann['description']
                    })
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return output_path
    
    def download_sample_dataset(self, dataset_name: str = 'sample') -> str:
        """Download MNE sample dataset and copy to backend/datasets/."""
        import shutil
        from app.core.config import settings

        datasets_dir = Path(settings.UPLOAD_DIR)
        datasets_dir.mkdir(parents=True, exist_ok=True)

        if dataset_name == 'sample':
            data_path = mne.datasets.sample.data_path()
            src = data_path / 'MEG' / 'sample' / 'sample_audvis_raw.fif'
        elif dataset_name == 'testing':
            data_path = mne.datasets.testing.data_path()
            src = data_path / 'MEG' / 'sample' / 'sample_audvis_trunc_raw.fif'
        else:
            raise ValueError(f"Unknown sample dataset: {dataset_name}")

        dest = datasets_dir / src.name
        if not dest.exists():
            shutil.copy2(str(src), str(dest))
        return str(dest)
    
    def persist_annotations_to_file(
        self,
        dataset_id: str,
        annotations: List[Dict]
    ) -> bool:
        """
        Persist annotations back to the original file.
        Works for .fif and .edf formats (EDF+ with annotations).
        Returns True if successful, False if format doesn't support persistence.
        """
        if dataset_id not in self.loaded_datasets:
            raise ValueError(f"Dataset {dataset_id} not loaded")
        
        if dataset_id not in self.dataset_file_paths:
            raise ValueError(f"File path not tracked for dataset {dataset_id}")
        
        file_path = self.dataset_file_paths[dataset_id]
        file_ext = Path(file_path).suffix.lower()
        
        # .fif and .edf formats support writing with annotations
        # .edf writes as EDF+ with annotations
        if file_ext not in ['.fif', '.edf']:
            print(f"Warning: {file_ext} format does not support annotation persistence")
            print(f"Supported formats: .fif, .edf (saves as EDF+)")
            return False
        
        raw = self.loaded_datasets[dataset_id]
        
        # Convert annotations dict to MNE Annotations object
        if len(annotations) == 0:
            annot = mne.Annotations(onset=[], duration=[], description=[])
        else:
            onsets = [ann['onset'] for ann in annotations]
            durations = [ann['duration'] for ann in annotations]
            descriptions = [ann['description'] for ann in annotations]
            annot = mne.Annotations(onset=onsets, duration=durations, description=descriptions)
        
        # Set annotations on raw object
        raw.set_annotations(annot)
        
        # Save back to file (overwrite original)
        try:
            if file_ext == '.fif':
                raw.save(file_path, overwrite=True)
                print(f"Successfully persisted {len(annotations)} annotations to {file_path}")
            elif file_ext == '.edf':
                # For EDF, we need to use export with preloaded data
                # Make sure data is loaded
                if not raw.preload:
                    raw.load_data()
                # Export back to EDF+ format
                raw.export(file_path, fmt='edf', overwrite=True, physical_range='auto')
                print(f"Successfully persisted {len(annotations)} annotations to {file_path} (EDF+)")
            return True
        except Exception as e:
            print(f"Error persisting annotations: {e}")
            raise

# Global instance
mne_service = MNEService()
