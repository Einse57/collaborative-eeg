"""
REVE Preprocessing Utilities

Ported from SWEZ-ETHZ iEEG project. Provides signal preprocessing
functions for the REVE foundation model pipeline:
  - Resampling to 200 Hz
  - Z-score normalization
  - Fixed-length windowing (2s @ 200 Hz = 400 samples)
"""
from __future__ import annotations

from typing import Optional

import numpy as np


def zscore(x: np.ndarray, *, axis: int = -1, eps: float = 1e-8) -> np.ndarray:
    mean = x.mean(axis=axis, keepdims=True)
    std = x.std(axis=axis, keepdims=True)
    return (x - mean) / (std + eps)


def window_fixed_length(
    x: np.ndarray,
    *,
    window_size: int,
    stride: Optional[int] = None,
) -> np.ndarray:
    if x.ndim != 2:
        raise ValueError(f"Expected shape (channels, samples), got {x.shape}")

    stride = window_size if stride is None else stride
    channels, samples = x.shape

    if samples < window_size:
        raise ValueError(f"Not enough samples ({samples}) for window_size={window_size}")

    starts = range(0, samples - window_size + 1, stride)
    windows = [x[:, s : s + window_size] for s in starts]
    return np.stack(windows, axis=0)


def resample(
    x: np.ndarray,
    *,
    orig_sfreq: float,
    new_sfreq: float,
) -> np.ndarray:
    if orig_sfreq == new_sfreq:
        return x

    try:
        import mne
        return mne.filter.resample(x, up=new_sfreq, down=orig_sfreq, axis=-1)
    except Exception:
        ratio = float(new_sfreq) / float(orig_sfreq)
        new_len = int(round(x.shape[-1] * ratio))
        idx = np.linspace(0, x.shape[-1] - 1, new_len)
        return np.stack(
            [np.interp(idx, np.arange(x.shape[-1]), ch) for ch in x], axis=0
        )
