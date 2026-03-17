"""
MNE Service for handling neurophysiological data files
"""
import mne
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

# HDF5 support for .mat (MATLAB v7.3) and .h5 files
try:
    import h5py
    try:
        import hdf5plugin  # noqa: F401 – registers extra compression codecs
    except Exception:
        pass
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False


# ----- HDF5 / MAT helpers -------------------------------------------------- #

_IEEG_KEY_CANDIDATES = ["data/ieeg", "data", "ieeg", "EEG", "eeg", "raw"]
_SFREQ_CANDIDATES = ("sfreq", "sampling_rate", "fs", "Fs", "SamplingRate")
_SEIZURE_KEY_CANDIDATES = ["data/seizures", "seizures", "events"]


def _h5_find_2d_dataset(f: "h5py.File") -> Optional[str]:
    """Walk the file and return the key of the first large 2-D dataset."""
    for key in _IEEG_KEY_CANDIDATES:
        if key in f and hasattr(f[key], "shape") and f[key].ndim == 2:
            return key
    # Fallback: pick the largest 2-D dataset
    best_key, best_size = None, 0
    def _visit(name, obj):
        nonlocal best_key, best_size
        if isinstance(obj, h5py.Dataset) and obj.ndim == 2:
            sz = obj.shape[0] * obj.shape[1]
            if sz > best_size:
                best_key, best_size = name, sz
    f.visititems(_visit)
    return best_key


def _h5_try_read_sfreq(f: "h5py.File") -> Optional[float]:
    """Try to infer sampling frequency from attributes or root datasets."""
    for k in _SFREQ_CANDIDATES:
        if k in f.attrs:
            try:
                return float(np.asarray(f.attrs[k]).squeeze())
            except Exception:
                pass
        if k in f:
            try:
                return float(np.asarray(f[k][()]).squeeze())
            except Exception:
                continue
    return None


def _h5_try_read_seizures(f: "h5py.File", sfreq: float) -> List[Tuple[float, float]]:
    """Try to read seizure intervals as [(onset_sec, offset_sec), ...]."""
    for key in _SEIZURE_KEY_CANDIDATES:
        if key not in f:
            continue
        try:
            arr = np.asarray(f[key][()])
        except Exception:
            continue
        if arr.size == 0:
            return []
        # Structured array with onsets/offsets fields
        if arr.dtype.fields and "onsets" in arr.dtype.fields and "offsets" in arr.dtype.fields:
            on = np.asarray(arr["onsets"]).reshape(-1)
            off = np.asarray(arr["offsets"]).reshape(-1)
            return [(float(o), float(f_)) for o, f_ in zip(on, off)]
        # Plain Nx2 numeric
        if arr.ndim == 2 and arr.shape[1] >= 2:
            return [(float(r[0]), float(r[1])) for r in arr]
    return []


def _h5_try_read_channel_names(f: "h5py.File", n_channels: int) -> List[str]:
    """Try to read channel labels; fall back to generic names."""
    for key in ("channel_names", "channels", "ch_names", "labels"):
        if key in f:
            try:
                names = [x.decode() if isinstance(x, bytes) else str(x) for x in f[key][()]]
                if len(names) == n_channels:
                    return names
            except Exception:
                pass
        if key in f.attrs:
            try:
                names = [x.decode() if isinstance(x, bytes) else str(x) for x in f.attrs[key]]
                if len(names) == n_channels:
                    return names
            except Exception:
                pass
    return [f"CH{i}" for i in range(n_channels)]


def _is_hdf5(file_path: str) -> bool:
    """Check the file's magic bytes to see if it is HDF5."""
    try:
        with open(file_path, "rb") as fh:
            return fh.read(8)[:4] == b"\x89HDF"
    except Exception:
        return False


_MAT_EEG_KEY_CANDIDATES = ["EEG", "eeg", "data", "ieeg", "raw", "X", "x"]
_MAT_SFREQ_CANDIDATES = ["fs", "Fs", "sfreq", "sampling_rate", "SamplingRate", "srate"]


def _find_mat_info_file(data_file_path: str) -> Optional[str]:
    """Look for a companion *_info.mat file in the same directory.

    Convention: data file ``ID01_100h.mat`` → info file ``ID01_info.mat``.
    The patient prefix is everything before the first underscore-digit segment.
    """
    import re
    p = Path(data_file_path)
    directory = p.parent
    stem = p.stem  # e.g. "ID01_100h"

    # Extract patient prefix (e.g. "ID01" from "ID01_100h")
    m = re.match(r"^([A-Za-z]+\d+)", stem)
    if m:
        prefix = m.group(1)
        candidate = directory / f"{prefix}_info.mat"
        if candidate.exists():
            return str(candidate)

    # Fallback: look for any *_info.mat in the same directory
    for f in directory.glob("*_info.mat"):
        return str(f)
    return None


def _load_mat_info(info_path: str) -> dict:
    """Parse a companion *_info.mat and return sfreq + seizure intervals."""
    from scipy.io import loadmat
    mat = loadmat(info_path)
    result: dict = {}

    # Sampling rate
    for key in _MAT_SFREQ_CANDIDATES:
        if key in mat:
            try:
                result["sfreq"] = float(np.asarray(mat[key]).squeeze())
                break
            except Exception:
                pass

    # Seizure begin/end (in samples) — convert to seconds if sfreq available
    sb_key = next((k for k in ("seizure_begin", "seizure_start", "Seizure_begin") if k in mat), None)
    se_key = next((k for k in ("seizure_end", "seizure_stop", "Seizure_end") if k in mat), None)
    if sb_key and se_key:
        sfreq = result.get("sfreq", 1.0)
        begins = np.asarray(mat[sb_key], dtype=float).flatten()
        ends = np.asarray(mat[se_key], dtype=float).flatten()
        seizures = []
        for b, e in zip(begins, ends):
            onset_sec = b / sfreq
            offset_sec = e / sfreq
            seizures.append((onset_sec, offset_sec))
        result["seizures"] = seizures

    # Channel names (if present in the info file)
    for key in ("ch_names", "channels", "labels", "channel_names"):
        if key in mat:
            try:
                raw_names = mat[key]
                if raw_names.ndim == 2:
                    raw_names = raw_names.flatten()
                names = [str(x).strip() if not isinstance(x, np.ndarray)
                         else str(x.flat[0]).strip() for x in raw_names]
                result["ch_names"] = names
                break
            except Exception:
                pass

    return result


def _load_mat_v5_as_raw(file_path: str) -> mne.io.RawArray:
    """Load a MATLAB v5/v7 .mat file (non-HDF5) and return an MNE RawArray."""
    from scipy.io import loadmat

    mat = loadmat(file_path)

    # --- companion info file (e.g. ID01_info.mat) ---
    info_data: dict = {}
    info_path = _find_mat_info_file(file_path)
    if info_path:
        try:
            info_data = _load_mat_info(info_path)
            print(f"✓ Loaded companion info file: {info_path}")
        except Exception as e:
            print(f"⚠ Could not parse info file {info_path}: {e}")

    # --- find EEG data array ---
    data = None
    for key in _MAT_EEG_KEY_CANDIDATES:
        if key in mat and isinstance(mat[key], np.ndarray) and mat[key].ndim == 2:
            data = mat[key]
            break
    if data is None:
        # Fallback: largest 2-D array in the file
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
        raise ValueError(
            f"Could not find a 2-D EEG array in {file_path}. "
            f"Tried keys: {_MAT_EEG_KEY_CANDIDATES}"
        )

    data = np.asarray(data, dtype=np.float64)

    # Heuristic: if dim-0 >> dim-1 the data is likely (samples, channels)
    if data.shape[0] > data.shape[1] * 4:
        data = data.T

    n_channels = data.shape[0]

    # --- sampling frequency (prefer info file, then data file, then default) ---
    sfreq = info_data.get("sfreq")
    if sfreq is None:
        for key in _MAT_SFREQ_CANDIDATES:
            if key in mat:
                try:
                    sfreq = float(np.asarray(mat[key]).squeeze())
                    break
                except Exception:
                    pass
    if sfreq is None:
        sfreq = 512.0
        print(f"⚠ Could not detect sampling rate in {file_path}; defaulting to {sfreq} Hz")

    # --- channel names (prefer info file, then data file, then generic) ---
    ch_names = None
    if "ch_names" in info_data and len(info_data["ch_names"]) == n_channels:
        ch_names = info_data["ch_names"]
    if ch_names is None:
        for key in ("ch_names", "channels", "labels", "channel_names"):
            if key in mat:
                try:
                    raw_names = mat[key]
                    if raw_names.ndim == 2:
                        # MATLAB cell arrays come in as (1, N) or (N, 1) object arrays
                        raw_names = raw_names.flatten()
                    names = [str(x).strip() if not isinstance(x, np.ndarray)
                             else str(x.flat[0]).strip() for x in raw_names]
                    if len(names) == n_channels:
                        ch_names = names
                        break
                except Exception:
                    pass
    if ch_names is None:
        ch_names = [f"CH{i}" for i in range(n_channels)]

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info)

    # --- seizure annotations (prefer info file, then inline) ---
    seizures_applied = False
    if "seizures" in info_data and info_data["seizures"]:
        try:
            szs = info_data["seizures"]
            onsets = [s[0] for s in szs]
            durations = [s[1] - s[0] for s in szs]
            raw.set_annotations(mne.Annotations(
                onset=onsets,
                duration=durations,
                description=["Seizure"] * len(onsets),
            ))
            seizures_applied = True
            print(f"✓ Applied {len(szs)} seizure annotation(s) from info file")
        except Exception as e:
            print(f"⚠ Could not apply seizures from info file: {e}")

    if not seizures_applied:
        for key in ("seizures", "events", "Seizures", "Events"):
            if key in mat:
                try:
                    arr = np.asarray(mat[key])
                    if arr.ndim == 2 and arr.shape[1] >= 2:
                        onsets = arr[:, 0].astype(float).tolist()
                        durations = (arr[:, 1] - arr[:, 0]).astype(float).tolist()
                        raw.set_annotations(mne.Annotations(
                            onset=onsets,
                            duration=durations,
                            description=["Seizure"] * len(onsets),
                        ))
                        break
                except Exception:
                    pass

    return raw


def _load_h5_as_raw(file_path: str) -> mne.io.RawArray:
    """Load an HDF5 / MATLAB-v7.3 file and return an MNE RawArray."""
    if not HAS_H5PY:
        raise RuntimeError(
            "h5py is required to load .h5 / .mat files. "
            "Install it with: pip install h5py hdf5plugin"
        )

    with h5py.File(file_path, "r") as f:
        data_key = _h5_find_2d_dataset(f)
        if data_key is None:
            raise ValueError(
                f"Could not find a 2-D EEG dataset in {file_path}. "
                f"Tried keys: {_IEEG_KEY_CANDIDATES}"
            )

        dset = f[data_key]
        shape = dset.shape  # expect (channels, samples) or (samples, channels)

        # Heuristic: if dim-0 >> dim-1 the data is likely (samples, channels)
        if shape[0] > shape[1] * 4:
            data = np.asarray(dset[()], dtype=np.float64).T  # transpose to (ch, samp)
        else:
            data = np.asarray(dset[()], dtype=np.float64)

        n_channels = data.shape[0]

        sfreq = _h5_try_read_sfreq(f)
        if sfreq is None:
            sfreq = 512.0  # sensible default for iEEG
            print(f"⚠ Could not detect sampling rate in {file_path}; defaulting to {sfreq} Hz")

        ch_names = _h5_try_read_channel_names(f, n_channels)
        seizures = _h5_try_read_seizures(f, sfreq)

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info)

    # Convert seizure intervals to MNE Annotations
    if seizures:
        onsets = [s[0] for s in seizures]
        durations = [s[1] - s[0] for s in seizures]
        descriptions = ["Seizure"] * len(seizures)
        raw.set_annotations(mne.Annotations(onset=onsets, duration=durations, description=descriptions))

    return raw


def _load_mat_or_h5_as_raw(file_path: str) -> mne.io.RawArray:
    """Load a .mat or .h5 file, auto-detecting the format."""
    file_ext = Path(file_path).suffix.lower()

    # .h5 files are always HDF5
    if file_ext == ".h5":
        return _load_h5_as_raw(file_path)

    # .mat files can be v5/v7 (scipy) or v7.3 (HDF5) — check magic bytes
    if _is_hdf5(file_path):
        return _load_h5_as_raw(file_path)
    else:
        return _load_mat_v5_as_raw(file_path)


# --------------------------------------------------------------------------- #


class MNEService:
    """Service for MNE-Python operations"""
    
    def __init__(self):
        self.loaded_datasets = {}  # Cache for loaded datasets
        self.dataset_file_paths = {}  # Track original file paths for persistence
    
    def load_file(self, file_path: str) -> Tuple[mne.io.Raw, str]:
        """Load a neurophysiological data file"""
        file_ext = Path(file_path).suffix.lower()
        
        loaders = {
            '.fif': mne.io.read_raw_fif,
            '.edf': mne.io.read_raw_edf,
            '.bdf': mne.io.read_raw_bdf,
            '.set': mne.io.read_raw_eeglab,
            '.vhdr': mne.io.read_raw_brainvision,
        }
        
        # HDF5-based formats (.h5) and MATLAB formats (.mat v5/v7/v7.3)
        if file_ext in ('.h5', '.mat'):
            raw = _load_mat_or_h5_as_raw(file_path)
            dataset_id = Path(file_path).stem
            self.loaded_datasets[dataset_id] = raw
            self.dataset_file_paths[dataset_id] = file_path
            return raw, dataset_id
        
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
        """Download MNE sample dataset"""
        if dataset_name == 'sample':
            data_path = mne.datasets.sample.data_path()
            file_path = data_path / 'MEG' / 'sample' / 'sample_audvis_raw.fif'
            return str(file_path)
        elif dataset_name == 'testing':
            data_path = mne.datasets.testing.data_path()
            file_path = data_path / 'MEG' / 'sample' / 'sample_audvis_trunc_raw.fif'
            return str(file_path)
        else:
            raise ValueError(f"Unknown sample dataset: {dataset_name}")
    
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
