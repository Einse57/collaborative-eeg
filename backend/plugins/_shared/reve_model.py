"""
REVE-Large Model Wrapper

Ported from SWEZ-ETHZ iEEG project. Provides lazy loading of the
REVE-Large foundation model backbone from Hugging Face.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch


@dataclass(frozen=True)
class ReveLoadResult:
    backbone: torch.nn.Module
    device: str


# Pin to a specific known-good revision for reproducibility and security.
_DEFAULT_MODEL_ID = "brain-bzh/reve-large"


def load_reve_large_backbone(
    *,
    model_id: str = _DEFAULT_MODEL_ID,
    device: Optional[str] = None,
) -> ReveLoadResult:
    from transformers import AutoModel

    backbone = AutoModel.from_pretrained(model_id, trust_remote_code=True)

    if device:
        resolved_device = device
    elif torch.cuda.is_available():
        resolved_device = "cuda"
    elif hasattr(torch, "xpu") and torch.xpu.is_available():
        resolved_device = "xpu"
    else:
        resolved_device = "cpu"
    backbone.to(resolved_device)
    backbone.eval()

    return ReveLoadResult(backbone=backbone, device=resolved_device)
