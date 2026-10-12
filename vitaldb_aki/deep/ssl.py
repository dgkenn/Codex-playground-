"""ssl.py -- self-supervised, label-free pretraining objective (§9, §10).

Masked-signal reconstruction. We mask contiguous spans of each input window (set them
to zero), pass the corrupted window through the compact 1D-CNN encoder + a light
decoder, and train to reconstruct the ORIGINAL signal at the masked positions. The loss
uses **no AKI label** -- it is computed purely from the waveform itself.

Why this is the right SSL choice here (§10 "consider pretraining/transfer for the
signal encoder"):
  * Label-free -> it pretrains on ALL cases' waveforms, not just the ~906-event
    labelable subset, so the representation is learned on far more data than the
    supervised head ever sees. This is the sample-size discipline §10 asks for.
  * Leakage-safe -> it never touches the outcome and only sees intraoperative samples
    (windows already clipped to [.., opend] by ``waveforms.py``), so pretraining cannot
    leak the label or postoperative information (§11).

After pretraining, the encoder is frozen and its per-case mean-pooled embedding is
concatenated with the tabular feature matrix for the H3 head-to-head (see README).

torch is imported lazily inside the functions. ``make_mask`` is pure NumPy so the
masking contract is testable without torch.
"""
from __future__ import annotations

from typing import Any

# ---- config-readable SSL hyperparameters ----------------------------------
DEFAULT_MASK_FRACTION: float = 0.4   # fraction of each window's timesteps masked
DEFAULT_MIN_SPAN: int = 5            # min contiguous masked-span length (samples)
DEFAULT_MAX_SPAN: int = 25          # max contiguous masked-span length (samples)
DEFAULT_LR: float = 1e-3


def make_mask(n_windows: int, win_len: int, mask_fraction: float = DEFAULT_MASK_FRACTION,
              min_span: int = DEFAULT_MIN_SPAN, max_span: int = DEFAULT_MAX_SPAN,
              rng=None):
    """Build a boolean mask (n_windows, win_len): True where the signal is masked out.

    Masks contiguous spans (not random points) so the encoder must use temporal
    context to reconstruct -- a stronger pretext than per-sample dropout. Spans are
    placed until at least ``mask_fraction`` of the timesteps are covered. Pure NumPy,
    deterministic given ``rng`` (a numpy Generator) for reproducible tests.
    """
    import numpy as np

    if rng is None:
        rng = np.random.default_rng(0)
    target = int(round(mask_fraction * win_len))
    mask = np.zeros((n_windows, win_len), dtype=bool)
    if target <= 0 or win_len <= 0:
        return mask
    lo = max(1, int(min_span))
    hi = max(lo, min(int(max_span), win_len))
    for w in range(n_windows):
        covered = 0
        guard = 0
        # guard against pathological infinite loops on tiny windows
        while covered < target and guard < 4 * win_len:
            guard += 1
            span = int(rng.integers(lo, hi + 1))
            start = int(rng.integers(0, win_len))
            end = min(win_len, start + span)
            newly = int((~mask[w, start:end]).sum())
            mask[w, start:end] = True
            covered += newly
    return mask


def _make_decoder(emb_dim: int, n_channels: int, win_len: int):
    """A small linear decoder: embedding -> flattened (n_channels, win_len) signal."""
    import torch.nn as nn

    return nn.Sequential(
        nn.Linear(emb_dim, max(emb_dim, n_channels * win_len // 4)),
        nn.GELU(),
        nn.Linear(max(emb_dim, n_channels * win_len // 4), n_channels * win_len),
    )


class MaskedReconstructionSSL:
    """Masked-signal-reconstruction pretraining wrapper around a `WaveformEncoder`.

    Holds the encoder + a light decoder + an Adam optimizer. ``train_step`` runs one
    masked-reconstruction update on a batch and returns the scalar loss. The objective
    is MSE between reconstruction and original, computed **only at masked positions**
    (the model is rewarded for inferring hidden signal from context, not for copying
    the visible part through).
    """

    def __init__(self, encoder, win_len: int, n_channels: int | None = None,
                 lr: float = DEFAULT_LR,
                 mask_fraction: float = DEFAULT_MASK_FRACTION,
                 min_span: int = DEFAULT_MIN_SPAN, max_span: int = DEFAULT_MAX_SPAN,
                 seed: int = 0):
        import numpy as np
        import torch

        self.encoder = encoder
        self.win_len = int(win_len)
        self.n_channels = int(n_channels if n_channels is not None else encoder.n_channels)
        self.mask_fraction = float(mask_fraction)
        self.min_span = int(min_span)
        self.max_span = int(max_span)
        self._np_rng = np.random.default_rng(seed)
        torch.manual_seed(seed)

        self.decoder = _make_decoder(encoder.emb_dim, self.n_channels, self.win_len)
        params = list(encoder.parameters()) + list(self.decoder.parameters())
        self.optimizer = torch.optim.Adam(params, lr=lr)

    def _forward_loss(self, batch):
        """Compute the masked-reconstruction loss for a (B, C, L) float tensor batch."""
        import numpy as np
        import torch

        x = batch
        b, c, length = x.shape
        mask_np = make_mask(b, length, self.mask_fraction, self.min_span,
                            self.max_span, rng=self._np_rng)          # (B, L)
        mask = torch.from_numpy(mask_np).to(x.dtype)                  # 1.0 where masked
        mask_c = mask.unsqueeze(1).expand(-1, c, -1)                  # (B, C, L)

        corrupted = x * (1.0 - mask_c)                               # zero the masked spans
        emb = self.encoder(corrupted)                                # (B, emb_dim)
        recon = self.decoder(emb).reshape(b, c, length)             # (B, C, L)

        # MSE at masked positions only.
        diff2 = (recon - x) ** 2 * mask_c
        denom = mask_c.sum().clamp_min(1.0)
        return diff2.sum() / denom

    def train_step(self, batch) -> float:
        """One optimizer step on a batch (numpy array or torch tensor). Returns loss."""
        import numpy as np
        import torch

        self.encoder.train()
        self.decoder.train()
        if not torch.is_tensor(batch):
            batch = torch.from_numpy(np.asarray(batch, dtype="float32"))
        batch = batch.float()

        self.optimizer.zero_grad()
        loss = self._forward_loss(batch)
        loss.backward()
        self.optimizer.step()
        return float(loss.detach().cpu())

    @property
    def loss_on(self):
        """Bound method alias kept for readability in drivers."""
        return self.eval_loss

    def eval_loss(self, batch) -> float:
        """Masked-reconstruction loss without an optimizer step (no grad)."""
        import numpy as np
        import torch

        self.encoder.eval()
        self.decoder.eval()
        if not torch.is_tensor(batch):
            batch = torch.from_numpy(np.asarray(batch, dtype="float32"))
        batch = batch.float()
        with torch.no_grad():
            loss = self._forward_loss(batch)
        return float(loss.detach().cpu())
