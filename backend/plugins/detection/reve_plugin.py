"""
REVE-Large Foundation Model Detection Plugin

Uses the REVE-Large EEG foundation model (brain-bzh/reve-large) as a
feature extractor. Detections are produced via embedding-based anomaly
scoring: segments whose pooled embeddings deviate significantly from
the recording's baseline are flagged as candidate events.

No fine-tuning or labelled data is required — the pretrained backbone
produces general-purpose EEG representations out of the box.
"""
import numpy as np
import mne
from typing import Dict, List, Any

from . import DetectionPlugin

# Check for dependencies at import time
try:
    import torch
    from transformers import AutoModel  # noqa: F401
    import einops  # noqa: F401
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Target sampling frequency and window size expected by REVE
_TARGET_SFREQ = 200.0
_WINDOW_SAMPLES = 400  # 2 seconds at 200 Hz


class REVEPlugin(DetectionPlugin):
    """REVE-Large foundation model anomaly detection plugin"""

    def __init__(self):
        self._backbone = None
        self._device: str | None = None

    # -- Plugin metadata --------------------------------------------------

    @property
    def plugin_id(self) -> str:
        return "reve"

    @property
    def display_name(self) -> str:
        return "REVE-Large"

    @property
    def description(self) -> str:
        return (
            "EEG foundation model (REVE-Large) — flags anomalous segments "
            "via embedding deviation from baseline"
        )

    @property
    def icon(self) -> str:
        return "🧠"

    @property
    def color(self) -> str:
        return "#7b1fa2"  # purple

    @property
    def requires_dependencies(self) -> List[str]:
        return ["torch", "transformers", "einops"]

    def is_available(self) -> bool:
        return HAS_DEPENDENCIES

    # -- Config schema for UI ---------------------------------------------

    def get_config_schema(self) -> Dict[str, Any]:
        schema = super().get_config_schema()
        schema.update({
            "sensitivity": {
                "type": "number",
                "default": 1.5,
                "min": 0.5,
                "max": 5.0,
                "step": 0.1,
                "label": "Sensitivity (σ multiplier — lower = more detections)",
            },
            "max_windows": {
                "type": "number",
                "default": 0,
                "min": 0,
                "max": 10000,
                "step": 1,
                "label": "Max windows (0 = unlimited)",
            },
        })
        return schema

    # -- Internals --------------------------------------------------------

    def _load_backbone(self):
        """Lazy-load the REVE-Large backbone (cached across calls)."""
        if self._backbone is not None:
            return

        if not HAS_DEPENDENCIES:
            raise RuntimeError("REVE dependencies not available")

        from .reve_model import load_reve_large_backbone

        result = load_reve_large_backbone()
        self._backbone = result.backbone
        self._device = result.device
        print(f"✓ REVE-Large backbone loaded on {self._device}")

    @staticmethod
    def _make_positions(channels: int, batch: int, device: str) -> "torch.Tensor":
        """Build synthetic electrode positions on a unit circle.

        If full 3-D montage coordinates are available on the Raw object they
        could be used instead, but the circular fallback works for any
        channel count and is what the SWEZ-ETHZ reference pipeline uses.
        """
        import torch as _torch

        theta = _torch.linspace(0, 2 * _torch.pi, channels + 1, device=device)[:-1]
        x = _torch.cos(theta)
        y = _torch.sin(theta)
        z = _torch.zeros_like(x)
        pos = _torch.stack([x, y, z], dim=-1)  # (C, 3)
        return pos.unsqueeze(0).expand(batch, -1, -1).contiguous()  # (B, C, 3)

    # -- Main detection entry point ----------------------------------------

    def detect(
        self,
        raw: mne.io.Raw,
        segment_duration: float = 2.0,
        threshold: float = 0.5,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Run anomaly-scored detection using REVE-Large embeddings.

        1. Extract all EEG channels from the Raw object.
        2. Resample to 200 Hz, z-score, window into 2-second chunks.
        3. Pass each window through the REVE backbone → pooled embedding.
        4. Compute per-window L2 norm of the embedding.
        5. Flag windows whose norm exceeds mean + sensitivity × std.
        """
        if not self.is_available():
            raise RuntimeError(
                f"Missing dependencies: {', '.join(self.requires_dependencies)}"
            )

        self._load_backbone()
        import torch as _torch
        from .reve_preprocess import resample, zscore, window_fixed_length

        sensitivity: float = float(kwargs.get("sensitivity", 1.5))
        max_windows: int = int(kwargs.get("max_windows", 0))

        # --- 1. Get data --------------------------------------------------
        picks = mne.pick_types(raw.info, meg=False, eeg=True, exclude="bads")
        if len(picks) == 0:
            # Fallback: use all channels if none are typed as EEG
            picks = list(range(len(raw.ch_names)))
        data = raw.get_data(picks=picks)  # (channels, samples)
        sfreq = raw.info["sfreq"]

        # --- 2. Preprocess ------------------------------------------------
        data = resample(
            data.astype(np.float32), orig_sfreq=sfreq, new_sfreq=_TARGET_SFREQ
        )
        data = zscore(data, axis=-1)

        window_size = int(round(segment_duration * _TARGET_SFREQ))
        try:
            windows = window_fixed_length(data, window_size=window_size, stride=window_size)
        except ValueError:
            # Recording shorter than one window
            return []

        n_windows = windows.shape[0]
        if max_windows > 0:
            n_windows = min(n_windows, max_windows)
        windows = windows[:n_windows]

        # --- 3. Compute embeddings ----------------------------------------
        pos = self._make_positions(windows.shape[1], n_windows, self._device)
        batch = _torch.from_numpy(windows).to(self._device)

        with _torch.no_grad():
            feats = self._backbone(eeg=batch, pos=pos)
            pooled = self._backbone.attention_pooling(feats)  # (B, E)

        embeddings = pooled.cpu().numpy()  # (n_windows, embed_dim)

        # --- 4. Anomaly scoring -------------------------------------------
        norms = np.linalg.norm(embeddings, axis=-1)  # (n_windows,)
        mean_norm = float(norms.mean())
        std_norm = float(norms.std()) if norms.size > 1 else 1.0

        # Threshold: windows whose norm exceeds mean + sensitivity * std
        cutoff = mean_norm + sensitivity * std_norm

        # --- 5. Build detections ------------------------------------------
        detections: List[Dict[str, Any]] = []
        for i in range(n_windows):
            if norms[i] > cutoff:
                # Map confidence to 0-1 range (how many σ above baseline)
                sigma_above = (norms[i] - mean_norm) / std_norm if std_norm > 0 else 0.0
                confidence = float(np.clip(sigma_above / (sensitivity * 2), 0.0, 1.0))

                onset_sec = float(i * window_size) / _TARGET_SFREQ
                detections.append({
                    "onset": onset_sec,
                    "duration": segment_duration,
                    "description": "Anomaly_detected",
                    "confidence": confidence,
                    "user": f"EventDetector_{self.plugin_id.upper()}",
                })

        return detections
