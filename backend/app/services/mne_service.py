"""
MNE Service for handling neurophysiological data files
"""
import mne
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

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
        
        loader = loaders.get(file_ext)
        if not loader:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        raw = loader(file_path, preload=False)
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
        
        return {
            'n_channels': len(raw.ch_names),
            'n_samples': len(raw.times),
            'sampling_rate': raw.info['sfreq'],
            'duration': raw.times[-1],
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
        Only works for .fif format - other formats don't support writing annotations.
        Returns True if successful, False if format doesn't support persistence.
        """
        if dataset_id not in self.loaded_datasets:
            raise ValueError(f"Dataset {dataset_id} not loaded")
        
        if dataset_id not in self.dataset_file_paths:
            raise ValueError(f"File path not tracked for dataset {dataset_id}")
        
        file_path = self.dataset_file_paths[dataset_id]
        file_ext = Path(file_path).suffix.lower()
        
        # Only .fif format supports writing with annotations
        if file_ext != '.fif':
            print(f"Warning: {file_ext} format does not support annotation persistence")
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
            raw.save(file_path, overwrite=True)
            print(f"Successfully persisted {len(annotations)} annotations to {file_path}")
            return True
        except Exception as e:
            print(f"Error persisting annotations: {e}")
            raise

# Global instance
mne_service = MNEService()
