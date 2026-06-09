"""
H5DatasetRef — Lazy reference to a SWEZ-ETHZ H5 patient recording.

Holds file paths + metadata with ZERO signal data in memory.
Provides random-access reads via h5py and a precomputed
min/max envelope for the full-timeline overview bar.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import h5py
    import hdf5plugin  # noqa: F401 — register Blosc decompressor
except ImportError:
    h5py = None


class H5DatasetRef:
    """Zero-memory reference to a SWEZ-ETHZ H5 fileset.

    After construction, only metadata is stored (~1 KB).
    Signal data is read on demand via :meth:`read_chunk`.
    """

    def __init__(
        self,
        total_path: str,
        *,
        fs: float = 512.0,
        n_channels: int = 128,
        total_samples: int = 0,
        part_files: Optional[List[str]] = None,
        seizures: Optional[List[Dict]] = None,
        is_vds_broken: bool = False,
    ):
        self.total_path = total_path
        self.fs = fs
        self.n_channels = n_channels
        self.total_samples = total_samples
        self.part_files = part_files or []
        self.seizures = seizures or []
        self.is_vds_broken = is_vds_broken

        # Derived
        self.duration_seconds = total_samples / fs
        self.ch_names = [f"iEEG{i:03d}" for i in range(n_channels)]

        # Cached envelope (computed lazily)
        self._envelope: Optional[np.ndarray] = None
        self._envelope_lock = threading.Lock()

        # Part file sample boundaries (for random access)
        self._part_boundaries: Optional[List[Tuple[int, int]]] = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_scan(cls, info: Dict) -> "H5DatasetRef":
        """Create from the dict returned by ``_scan_h5_info()``."""
        return cls(
            total_path=info.get("path", ""),
            fs=info["fs"],
            n_channels=info["n_channels"],
            total_samples=info["n_samples"],
            part_files=info.get("part_files", []),
            seizures=info.get("seizures", []),
            is_vds_broken=info.get("is_vds_broken", False),
        )

    # ------------------------------------------------------------------
    # Random-access reads
    # ------------------------------------------------------------------

    def _ensure_part_boundaries(self):
        """Lazily compute per-part sample ranges."""
        if self._part_boundaries is not None:
            return
        if not self.is_vds_broken or not self.part_files:
            self._part_boundaries = [(0, self.total_samples)]
            return
        bounds = []
        offset = 0
        for pf in self.part_files:
            with h5py.File(pf, "r") as f:
                n = f["data/ieeg"].shape[1]
            bounds.append((offset, offset + n))
            offset += n
        self._part_boundaries = bounds

    def read_chunk(
        self,
        start_sec: float,
        duration_sec: float,
        channels: Optional[List[int]] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Read a time segment directly from H5.

        Returns:
            data: (n_channels, n_samples) float64
            times: (n_samples,) float64 — seconds from start_sec
        """
        start_sample = int(start_sec * self.fs)
        end_sample = min(start_sample + int(duration_sec * self.fs),
                         self.total_samples)

        if channels is None:
            ch_slice = slice(None)
        else:
            ch_slice = channels

        if self.is_vds_broken and self.part_files:
            data = self._read_parts(start_sample, end_sample, ch_slice)
        else:
            with h5py.File(self.total_path, "r") as f:
                data = np.array(f["data/ieeg"][ch_slice, start_sample:end_sample],
                                dtype=np.float64)

        n_samples = data.shape[1]
        times = np.arange(n_samples) / self.fs + start_sec
        return data, times

    def _read_parts(self, start: int, end: int, ch_slice) -> np.ndarray:
        """Read across part files for a broken VDS."""
        self._ensure_part_boundaries()
        chunks = []
        for pf, (pf_start, pf_end) in zip(self.part_files, self._part_boundaries):
            if end <= pf_start or start >= pf_end:
                continue
            local_start = max(0, start - pf_start)
            local_end = min(pf_end - pf_start, end - pf_start)
            with h5py.File(pf, "r") as f:
                chunks.append(np.array(
                    f["data/ieeg"][ch_slice, local_start:local_end],
                    dtype=np.float64,
                ))
        return np.concatenate(chunks, axis=1) if chunks else np.zeros(
            (self.n_channels, 0), dtype=np.float64
        )

    # ------------------------------------------------------------------
    # Envelope (for timeline overview bar)
    # ------------------------------------------------------------------

    def get_envelope(self, target_points: int = 2000) -> Dict:
        """Compute or return cached min/max envelope for the full recording.

        Returns dict with:
            times: (P,) midpoint times in seconds
            env_min: (n_channels, P) per-channel minimum in each bin
            env_max: (n_channels, P) per-channel maximum in each bin
        """
        with self._envelope_lock:
            if (self._envelope is not None and
                    self._envelope["times"].shape[0] == target_points):
                return self._envelope

        # Compute envelope in bins — read only what's needed
        samples_per_bin = max(1, self.total_samples // target_points)
        actual_bins = (self.total_samples + samples_per_bin - 1) // samples_per_bin

        # Use a subset of channels for the overview (first 8 real channels)
        n_env_ch = min(self.n_channels, 8)
        env_min = np.zeros((n_env_ch, actual_bins), dtype=np.float32)
        env_max = np.zeros((n_env_ch, actual_bins), dtype=np.float32)
        times = np.zeros(actual_bins, dtype=np.float32)

        for b in range(actual_bins):
            s = b * samples_per_bin
            e = min(s + samples_per_bin, self.total_samples)
            chunk, _ = self.read_chunk(
                s / self.fs, (e - s) / self.fs,
                channels=list(range(n_env_ch)),
            )
            env_min[:, b] = chunk.min(axis=1).astype(np.float32)
            env_max[:, b] = chunk.max(axis=1).astype(np.float32)
            times[b] = (s + e) / 2 / self.fs

        result = {
            "times": times,
            "env_min": env_min,
            "env_max": env_max,
            "n_channels": n_env_ch,
        }
        with self._envelope_lock:
            self._envelope = result
        return result

    # ------------------------------------------------------------------
    # MNE-compatible metadata (so existing endpoints can work)
    # ------------------------------------------------------------------

    def get_metadata(self) -> Dict:
        """Return metadata dict in the same shape as MNEService.get_metadata."""
        return {
            "n_channels": self.n_channels,
            "n_samples": self.total_samples,
            "sampling_rate": self.fs,
            "duration": self.duration_seconds,
            "channel_names": self.ch_names,
            "channel_types": ["eeg"] * self.n_channels,
            "meas_date": None,
            "highpass": None,
            "lowpass": None,
            "is_h5_ref": True,
        }

    def get_annotations(self) -> List[Dict]:
        """Return seizure annotations in platform format."""
        annots = []
        for i, sz in enumerate(self.seizures):
            annots.append({
                "id": f"ann_sz_{i}",
                "onset": sz["onset"],
                "duration": sz["offset"] - sz["onset"],
                "description": "Seizure",
                "orig_time": None,
            })
        return annots
