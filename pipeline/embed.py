"""embed.py -- frozen foundation-model forward pass + pooling (Sec 7.1, 7.3).

Loads an open EEG foundation-model checkpoint (default: CBraMod), frozen, and
runs windows through it with no gradients and no activation storage (Sec 0). The
per-window embeddings are pooled to one compact per-recording vector (mean+std
by default). Epoch-level embeddings are persisted only for a small random
subsample reserved for stability analysis (Sec 7.3).

torch + the model are imported lazily. `pool_embeddings` is a pure NumPy/stdlib
function so the pooling contract is testable without the model.
"""
from __future__ import annotations

import hashlib
from typing import Any

from common.hashing import hash_file


def torch_inference(fn):
    """Decorator: run under torch.no_grad if torch is present (else passthrough)."""
    def wrapper(*args, **kwargs):  # pragma: no cover - needs torch
        try:
            import torch
        except ImportError:
            return fn(*args, **kwargs)
        with torch.no_grad():
            return fn(*args, **kwargs)
    return wrapper


class FrozenEmbedder:
    """Wraps a frozen checkpoint; verifies its hash before first use (Sec 3)."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.model = None
        self.checkpoint_path: str | None = None
        self._verified = False

    def load(self, checkpoint_path: str):  # pragma: no cover - needs torch + ckpt
        import torch

        expected = self.cfg["model"].get("checkpoint_sha256")
        actual = hash_file(checkpoint_path)
        if expected and not str(expected).upper().startswith("TO-CONFIRM"):
            if actual.lower() != str(expected).lower():
                raise ValueError(
                    f"checkpoint hash mismatch: expected {expected}, got {actual}"
                )
        self.checkpoint_path = checkpoint_path
        self._verified = True

        # Adapter boundary: construct the chosen architecture and load weights.
        # Kept generic so CBraMod / LaBraM / EEGPT / BIOT can be swapped via cfg.
        raise NotImplementedError(
            "Construct the configured architecture (cfg.model.name) and "
            "load_state_dict from the verified checkpoint, then model.eval() "
            "and freeze all parameters (requires_grad=False)."
        )

    @torch_inference
    def embed_windows(self, windows):  # pragma: no cover - needs torch + model
        """windows: (n_windows, n_channels, n_samples) -> (n_windows, d).

        Frozen forward only: torch.no_grad, eval mode, nothing retained.
        """
        if self.model is None:
            raise RuntimeError("call load() first")
        import torch

        x = torch.from_numpy(windows).float()
        feats = self.model(x)  # architecture-specific embedding head
        return feats.detach().cpu().numpy()


def pool_embeddings(window_embeddings, pooling: list[str]):
    """Pool (n_windows, d) -> compact per-recording vector.

    Supports "mean" and "std" (concatenated in the order given). Pure NumPy;
    this is the contract the persisted embedding table depends on.
    """
    import numpy as np

    we = np.asarray(window_embeddings, dtype="float64")
    if we.ndim != 2 or we.shape[0] == 0:
        raise ValueError("window_embeddings must be (n_windows>0, d)")
    parts = []
    for op in pooling:
        if op == "mean":
            parts.append(we.mean(axis=0))
        elif op == "std":
            parts.append(we.std(axis=0))
        else:
            raise ValueError(f"unknown pooling op {op!r}")
    return np.concatenate(parts).astype("float32")


def should_keep_epoch_subset(recording_id: str, fraction: float) -> bool:
    """Deterministic per-recording subsampling for epoch-level storage.

    Hash-based so the kept subset is reproducible from the recording id alone
    (no global RNG state, resume-safe).
    """
    if fraction <= 0:
        return False
    if fraction >= 1:
        return True
    digest = hashlib.sha256(recording_id.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return bucket < fraction
