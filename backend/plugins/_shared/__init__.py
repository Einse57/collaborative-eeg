"""
Shared utilities used across multiple detection plugins.

Re-exports preprocessing functions and model loaders so plugins can do:
    from .._shared import resample, zscore, window_fixed_length
    from .._shared import load_reve_large_backbone
"""
from .reve_preprocess import resample, zscore, window_fixed_length
from .reve_model import load_reve_large_backbone, ReveLoadResult
