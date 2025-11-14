"""
Event Detection Service - PROOF OF CONCEPT ONLY

⚠️ IMPORTANT DISCLAIMER ⚠️
This is a research/educational proof of concept and is NOT intended for clinical use.
DO NOT use this for medical diagnosis, treatment decisions, or patient care.
This software has NOT been validated on clinical data or approved by regulatory bodies.

For educational and research purposes only.

Implements both classical ML (Random Forest) and Deep Learning (CNN) methods
for exploring automatic event detection approaches in EEG data.
"""
import os
import numpy as np
import mne
from typing import Dict, List, Optional, Tuple
from pathlib import Path

try:
    import pywt
    from scipy.stats import skew
    from scipy.signal import welch
    from sklearn.ensemble import RandomForestClassifier
    HAS_CLASSICAL_ML = True
except ImportError:
    HAS_CLASSICAL_ML = False
    print("Warning: Classical ML dependencies not available. Install PyWavelets, scikit-learn.")

try:
    import torch
    import torch.nn as nn
    from huggingface_hub import hf_hub_download
    from PIL import Image
    import torchvision.transforms as transforms
    HAS_DEEP_LEARNING = True
except ImportError:
    HAS_DEEP_LEARNING = False
    print("Warning: Deep learning dependencies not available. Install torch, huggingface-hub, pillow, torchvision.")


# CNN Model Architecture for EEG Seizure Detection (ThomasCdnns compatible)
class EEGSeizureNet(nn.Module):
    """
    CNN for EEG seizure detection from spectrograms
    Architecture compatible with ThomasCdnns/EEG-Seizure-Detection model
    """
    def __init__(self, num_classes=2):
        super(EEGSeizureNet, self).__init__()
        
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
        
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        
        self.dropout = nn.Dropout(p=0.5)
        
        # Fully connected layers (for 32x32 input: after 2 pools -> 8x8 -> 64*8*8=4096)
        self.fc1 = nn.Linear(4096, 120)
        self.fc2 = nn.Linear(120, 32)
        self.fc3 = nn.Linear(32, num_classes)
    
    def forward(self, x):
        # Conv block 1
        x = self.pool(torch.relu(self.bn1(self.conv1(x))))
        
        # Conv block 2
        x = self.pool(torch.relu(self.bn2(self.conv2(x))))
        
        # Flatten
        x = x.view(x.size(0), -1)
        
        # Fully connected layers
        x = torch.relu(self.fc1(x))
        x = self.dropout(x)
        x = torch.relu(self.fc2(x))
        x = self.dropout(x)
        x = self.fc3(x)
        
        return x


class EventDetectionService:
    """
    Service for exploring event detection approaches using multiple methods
    
    ⚠️ PROOF OF CONCEPT - NOT FOR CLINICAL USE ⚠️
    """
    
    def __init__(self):
        self.rf_model = None
        self.cnn_model = None
        
    def detect_events_rf(
        self,
        raw: mne.io.Raw,
        segment_duration: float = 2.0,
        threshold: float = 0.5
    ) -> List[Dict]:
        """
        Detect events using Random Forest with Wavelet features
        Based on: github.com/hakanbicerrr/Epileptic_Seizure_Detection
        
        Args:
            raw: MNE Raw object containing EEG data
            segment_duration: Duration of segments to analyze (seconds)
            threshold: Probability threshold for event detection
            
        Returns:
            List of event annotations with onset, duration, description, confidence
        """
        if not HAS_CLASSICAL_ML:
            error_msg = "Classical ML dependencies not installed. Please install: pip install PyWavelets scikit-learn"
            print(f"ERROR: {error_msg}")
            raise ImportError(error_msg)
        
        print(f"Starting Random Forest event detection... (HAS_CLASSICAL_ML={HAS_CLASSICAL_ML})")
        print("⚠️  PROOF OF CONCEPT - Results are for research/educational purposes only")
        
        # Get data and sampling rate
        raw_copy = raw.copy()  # Don't modify original
        
        # Load data into memory if not already loaded (required for filtering)
        if not raw_copy.preload:
            print("  Loading data into memory...")
            raw_copy.load_data()
        
        sfreq = raw_copy.info['sfreq']
        
        # Preprocess using MNE: filter to remove artifacts and focus on seizure-relevant bands
        print("  Preprocessing: Applying bandpass filter (0.5-50 Hz) and notch filter (60 Hz)")
        raw_copy.filter(0.5, 50., fir_design='firwin', verbose=False)
        raw_copy.notch_filter(60, verbose=False)  # Remove powerline noise
        
        # Get preprocessed data
        data, times = raw_copy[:, :]
        
        # Limit to EEG channels only if available
        if raw_copy.ch_names:
            # Try to pick EEG channels
            try:
                eeg_picks = mne.pick_types(raw_copy.info, meg=False, eeg=True, exclude='bads')
                if len(eeg_picks) > 0:
                    data = data[eeg_picks, :]
                    print(f"  Using {len(eeg_picks)} EEG channels")
                else:
                    # Fallback to first 23 channels
                    n_channels = min(23, data.shape[0])
                    data = data[:n_channels, :]
                    print(f"  Using first {n_channels} channels")
            except:
                n_channels = min(23, data.shape[0])
                data = data[:n_channels, :]
                print(f"  Using first {n_channels} channels")
        
        # Calculate segment size in samples
        segment_samples = int(segment_duration * sfreq)
        n_segments = data.shape[1] // segment_samples
        
        print(f"Analyzing {n_segments} segments of {segment_duration}s each...")
        
        seizure_annotations = []
        
        for i in range(n_segments):
            start_sample = i * segment_samples
            end_sample = start_sample + segment_samples
            segment = data[:, start_sample:end_sample]
            
            # Extract features using DWT + spectral analysis
            features = self._extract_dwt_features(segment, sfreq=sfreq)
            
            if features is None:
                continue
            
            # Classify (for now, use simple heuristic - in production, use trained model)
            # This is a placeholder - you would load a pre-trained RandomForest model
            is_seizure, confidence = self._classify_segment_rf(features)
            
            if is_seizure and confidence >= threshold:
                onset_time = start_sample / sfreq
                seizure_annotations.append({
                    'onset': float(onset_time),
                    'duration': float(segment_duration),
                    'description': 'Event_detected',
                    'user': 'EventDetector_RF',
                    'confidence': float(confidence),
                    'method': 'Random Forest + DWT'
                })
                print(f"  Event detected at {onset_time:.1f}s (confidence: {confidence:.2f})")
        
        print(f"Detection complete. Found {len(seizure_annotations)} potential events.")
        return seizure_annotations
    
    def _extract_dwt_features(self, segment: np.ndarray, sfreq: float = 256.0) -> Optional[np.ndarray]:
        """
        Extract features using both DWT and MNE's spectral analysis
        Combines:
        - 36 DWT features per channel (Energy, Max, Min, Mean, STD, Skewness × 6 bands)
        - Band power features using MNE/scipy (delta, theta, alpha, beta, gamma)
        """
        try:
            n_channels = segment.shape[0]
            all_features = []
            
            for ch in range(n_channels):
                channel_data = segment[ch, :]
                
                # === DWT Features (original approach) ===
                coeffs = pywt.wavedec(channel_data, 'coif3', level=7)
                
                if len(coeffs) < 8:
                    return None
                
                cA7, cD7, cD6, cD5, cD4, cD3, cD2, cD1 = coeffs
                
                # Extract features from 6 detail coefficient bands
                bands = [cD7, cD6, cD5, cD4, cD3, cD2]
                channel_features = []
                
                for band in bands:
                    if len(band) == 0:
                        continue
                    # 6 features per band
                    channel_features.extend([
                        np.sum(band ** 2),      # Energy
                        np.max(band),            # Max
                        np.min(band),            # Min
                        np.mean(band),           # Mean
                        np.std(band),            # Standard deviation
                        skew(band)               # Skewness
                    ])
                
                # === Additional spectral features using scipy ===
                # Compute power spectral density
                freqs, psd = welch(channel_data, fs=sfreq, nperseg=min(256, len(channel_data)))
                
                # Band power in clinically relevant frequency bands
                # Delta (0.5-4 Hz), Theta (4-8 Hz), Alpha (8-13 Hz), Beta (13-30 Hz), Gamma (30-50 Hz)
                freq_bands = {
                    'delta': (0.5, 4),
                    'theta': (4, 8),
                    'alpha': (8, 13),
                    'beta': (13, 30),
                    'gamma': (30, 50)
                }
                
                for band_name, (low, high) in freq_bands.items():
                    band_mask = (freqs >= low) & (freqs <= high)
                    band_power = np.trapz(psd[band_mask], freqs[band_mask])
                    channel_features.append(band_power)
                
                all_features.extend(channel_features)
            
            return np.array(all_features)
        
        except Exception as e:
            print(f"Error extracting features: {e}")
            return None
    
    def _classify_segment_rf(self, features: np.ndarray) -> Tuple[bool, float]:
        """
        Classify segment using Random Forest
        
        NOTE: This is a placeholder implementation. In production, you would:
        1. Load a pre-trained Random Forest model
        2. Use the model to predict: prediction, proba = model.predict(features)
        
        For now, using a simple heuristic based on feature energy
        """
        # Placeholder heuristic - replace with trained model
        # High energy in certain bands suggests seizure activity
        mean_energy = np.mean(features[::6])  # Every 6th feature is energy
        
        # Simple threshold (this would be learned from data in real implementation)
        threshold = np.percentile(features, 90)
        
        if mean_energy > threshold:
            confidence = min(0.95, mean_energy / threshold)
            return True, confidence
        
        return False, 0.0
    
    def detect_events_cnn(
        self,
        raw: mne.io.Raw,
        segment_duration: float = 2.0,
        threshold: float = 0.5
    ) -> List[Dict]:
        """
        Detect events using CNN from Hugging Face
        Model: ThomasCdnns/EEG-Seizure-Detection
        
        Args:
            raw: MNE Raw object containing EEG data
            segment_duration: Duration of segments to analyze (seconds)
            threshold: Probability threshold for event detection
            
        Returns:
            List of seizure annotations
        """
        if not HAS_DEEP_LEARNING:
            error_msg = "Deep learning dependencies not installed. Please install: pip install torch huggingface-hub"
            print(f"ERROR: {error_msg}")
            raise ImportError(error_msg)
        
        print(f"Starting CNN seizure detection... (HAS_DEEP_LEARNING={HAS_DEEP_LEARNING})")
        print("⚠️  PROOF OF CONCEPT - Results are for research/educational purposes only")
        print("Converting EEG to spectrograms using MNE time-frequency analysis...")
        
        # Preprocess using MNE
        raw_copy = raw.copy()
        
        # Load data into memory if not already loaded (required for filtering)
        if not raw_copy.preload:
            print("  Loading data into memory...")
            raw_copy.load_data()
        
        raw_copy.filter(0.5, 50., fir_design='firwin', verbose=False)
        raw_copy.notch_filter(60, verbose=False)
        
        # Get preprocessed data
        data, times = raw_copy[:, :]
        sfreq = raw_copy.info['sfreq']
        
        # Use EEG channels if available
        try:
            eeg_picks = mne.pick_types(raw_copy.info, meg=False, eeg=True, exclude='bads')
            if len(eeg_picks) > 0:
                data = data[eeg_picks, :]
                print(f"  Using {len(eeg_picks)} EEG channels")
            else:
                # Use first channel
                data = data[0:1, :]
                print(f"  Using first channel for spectrogram analysis")
        except:
            data = data[0:1, :]
            print(f"  Using first channel for spectrogram analysis")
        
        segment_samples = int(segment_duration * sfreq)
        n_segments = data.shape[1] // segment_samples
        
        seizure_annotations = []
        
        # Load CNN model (lazy loading)
        if self.cnn_model is None:
            self.cnn_model = self._load_cnn_model()
        
        for i in range(n_segments):
            start_sample = i * segment_samples
            end_sample = start_sample + segment_samples
            segment = data[:, start_sample:end_sample]
            
            # Convert segment to spectrogram image (32x32)
            spectrogram_image = self._eeg_to_spectrogram(segment, sfreq)
            
            if spectrogram_image is None:
                continue
            
            # Classify using CNN
            is_seizure, confidence = self._classify_segment_cnn(spectrogram_image)
            
            if is_seizure and confidence >= threshold:
                onset_time = start_sample / sfreq
                seizure_annotations.append({
                    'onset': float(onset_time),
                    'duration': float(segment_duration),
                    'description': 'Event_detected',
                    'user': 'EventDetector_CNN',
                    'confidence': float(confidence),
                    'method': 'CNN (Spectrogram-based)'
                })
                print(f"  Event detected at {onset_time:.1f}s (confidence: {confidence:.2f})")
        
        print(f"Detection complete. Found {len(seizure_annotations)} potential events.")
        return seizure_annotations
    
    def _load_cnn_model(self):
        """Load pre-trained CNN model"""
        try:
            print("Loading CNN model...")
            
            model = EEGSeizureNet(num_classes=2)
            weights_loaded = False
            
            # Priority 1: Try to load from HuggingFace (ThomasCdnns model)
            try:
                print("  Attempting to download from HuggingFace (ThomasCdnns/EEG-Seizure-Detection)...")
                # Try safetensors format first
                try:
                    from safetensors.torch import load_file
                    safetensors_path = hf_hub_download(
                        repo_id="ThomasCdnns/EEG-Seizure-Detection",
                        filename="model.safetensors"
                    )
                    state_dict = load_file(safetensors_path)
                    model.load_state_dict(state_dict)
                    print("  ✓ Loaded pre-trained weights from HuggingFace (safetensors)")
                    weights_loaded = True
                except Exception as e:
                    print(f"  Safetensors not found, trying PyTorch format: {e}")
                    # Try pytorch_model.bin
                    try:
                        pytorch_path = hf_hub_download(
                            repo_id="ThomasCdnns/EEG-Seizure-Detection",
                            filename="pytorch_model.bin"
                        )
                        model.load_state_dict(torch.load(pytorch_path, map_location='cpu'))
                        print("  ✓ Loaded pre-trained weights from HuggingFace (pytorch)")
                        weights_loaded = True
                    except Exception as e2:
                        print(f"  PyTorch format not found: {e2}")
            except Exception as e:
                print(f"  ⚠ Could not load from HuggingFace: {e}")
            
            # Priority 2: Try local trained weights if HuggingFace failed
            if not weights_loaded:
                local_weights_path = "models/cnn_weights.pth"
                if os.path.exists(local_weights_path):
                    try:
                        model.load_state_dict(torch.load(local_weights_path, map_location='cpu'))
                        print(f"  ✓ Loaded locally trained weights from {local_weights_path}")
                        weights_loaded = True
                    except Exception as e:
                        print(f"  ⚠ Error loading local weights: {e}")
            
            # If no weights loaded, warn user
            if not weights_loaded:
                print("  ⚠ No pre-trained weights found. Using randomly initialized model.")
                print("  📚 Run 'python train_cnn_model.py' to train the model on your data")
                print("  🚫 DO NOT use untrained models for any real analysis")
            
            model.eval()
            return model
            
        except Exception as e:
            print(f"Error loading CNN model: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _eeg_to_spectrogram(self, segment: np.ndarray, sfreq: float) -> Optional[np.ndarray]:
        """Convert EEG segment to 32x32 spectrogram image using scipy"""
        try:
            from scipy import signal
            from PIL import Image
            
            # Average across channels if multiple channels
            if segment.shape[0] > 1:
                eeg_data = np.mean(segment, axis=0)
            else:
                eeg_data = segment[0, :]
            
            # Compute spectrogram
            f, t, Sxx = signal.spectrogram(
                eeg_data,
                sfreq,
                nperseg=min(256, len(eeg_data) // 4),
                noverlap=min(128, len(eeg_data) // 8)
            )
            
            # Focus on 0-50 Hz range
            freq_mask = f <= 50
            Sxx_filtered = Sxx[freq_mask, :]
            
            # Convert to dB scale
            Sxx_db = 10 * np.log10(Sxx_filtered + 1e-10)
            
            # Normalize to 0-255 range for PIL
            Sxx_norm = ((Sxx_db - Sxx_db.min()) / (Sxx_db.max() - Sxx_db.min() + 1e-10) * 255).astype(np.uint8)
            
            # Resize to 32x32 using PIL (grayscale)
            img = Image.fromarray(Sxx_norm, mode='L')
            img_resized = img.resize((32, 32), Image.Resampling.LANCZOS)
            
            # Convert to float array and normalize as per ThomasCdnns model
            # Normalize to [0, 1] then apply mean=0.5, std=0.5
            spec_array = np.array(img_resized, dtype=np.float32) / 255.0
            spec_normalized = (spec_array - 0.5) / 0.5  # Normalize with mean=0.5, std=0.5
            
            return spec_normalized
        
        except Exception as e:
            print(f"Error creating spectrogram: {e}")
            return None
    
    def _classify_segment_cnn(self, image: np.ndarray) -> Tuple[bool, float]:
        """
        Classify spectrogram image using CNN
        """
        if self.cnn_model is None:
            # No model loaded, return low confidence
            return False, 0.0
        
        try:
            # Prepare image for model input: [batch, channels, height, width]
            img_tensor = torch.from_numpy(image).unsqueeze(0).unsqueeze(0)  # Add batch and channel dims
            
            # Run inference
            with torch.no_grad():
                outputs = self.cnn_model(img_tensor)
                probabilities = torch.softmax(outputs, dim=1)
                seizure_prob = probabilities[0, 1].item()  # Probability of seizure class
            
            # Determine if seizure based on probability
            is_seizure = seizure_prob > 0.5
            
            return is_seizure, seizure_prob
            
        except Exception as e:
            print(f"Error during CNN inference: {e}")
            # Fallback to placeholder
            return False, 0.3


# Global instance
event_detection_service = EventDetectionService()
