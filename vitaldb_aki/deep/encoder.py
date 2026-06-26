"""encoder.py -- compact multichannel 1D-CNN waveform encoder (§9, §9F, §10).

Maps one multimodal intraoperative window ``(n_channels, win_len)`` to a fixed-size
embedding vector, and pools per-window embeddings to one per-case vector. This is the
deep-learning arm's representation of "all the information the tabular summaries
discard" (§7F).

Capacity discipline (§10)
-------------------------
The labelable cohort yields only ~906 AKI events, so capacity is deliberately SMALL:
a 3-block depthwise-separable 1D-CNN with width ``base_channels`` (default 16) and a
small embedding dim (default 32). This keeps the encoder in the tens-of-thousands of
parameters, not millions. The §10 mandate is explicit: if the deep model has orders of
magnitude more parameters than events, its results are exploratory; we keep it lean so
the head-to-head against the tabular baseline (H3) is honest.

torch is imported lazily inside the module-level factory/classes' methods are pure once
constructed; ``count_parameters`` and ``mean_pool_embeddings`` work without a forward
pass. Everything is CPU-runnable (this box is torch 2.5.1+cpu, no GPU).
"""
from __future__ import annotations

from typing import Any


# ---- config-readable encoder geometry -------------------------------------
DEFAULT_BASE_CHANNELS: int = 16
DEFAULT_EMB_DIM: int = 32
DEFAULT_N_BLOCKS: int = 3
DEFAULT_KERNEL_SIZE: int = 7
DEFAULT_DROPOUT: float = 0.1


def build_encoder(n_channels: int,
                  base_channels: int = DEFAULT_BASE_CHANNELS,
                  emb_dim: int = DEFAULT_EMB_DIM,
                  n_blocks: int = DEFAULT_N_BLOCKS,
                  kernel_size: int = DEFAULT_KERNEL_SIZE,
                  dropout: float = DEFAULT_DROPOUT):
    """Construct the compact 1D-CNN encoder (a torch.nn.Module).

    Returns an instance of `WaveformEncoder`. torch is imported here (lazy heavy
    import) so the module imports under the stdlib-only contract.
    """
    return WaveformEncoder(
        n_channels=n_channels, base_channels=base_channels, emb_dim=emb_dim,
        n_blocks=n_blocks, kernel_size=kernel_size, dropout=dropout,
    )


def _make_module(n_channels, base_channels, emb_dim, n_blocks, kernel_size, dropout):
    """Build the nn.Module graph (separated so torch import stays lazy)."""
    import torch.nn as nn

    class _SepConvBlock(nn.Module):
        """Depthwise-separable conv -> BN -> GELU -> maxpool(2). Parameter-frugal."""

        def __init__(self, c_in: int, c_out: int, k: int, p_drop: float):
            super().__init__()
            pad = k // 2
            self.depthwise = nn.Conv1d(c_in, c_in, k, padding=pad, groups=c_in)
            self.pointwise = nn.Conv1d(c_in, c_out, 1)
            self.bn = nn.BatchNorm1d(c_out)
            self.act = nn.GELU()
            self.pool = nn.MaxPool1d(2)
            self.drop = nn.Dropout(p_drop)

        def forward(self, x):
            x = self.depthwise(x)
            x = self.pointwise(x)
            x = self.bn(x)
            x = self.act(x)
            x = self.pool(x)
            return self.drop(x)

    class _Encoder(nn.Module):
        def __init__(self):
            super().__init__()
            blocks = []
            c_in = n_channels
            c_out = base_channels
            for _ in range(n_blocks):
                blocks.append(_SepConvBlock(c_in, c_out, kernel_size, dropout))
                c_in = c_out
                c_out = c_out * 2
            self.blocks = nn.Sequential(*blocks)
            self.head = nn.Linear(c_in, emb_dim)   # c_in == width of last block
            self._last_width = c_in

        def forward(self, x):
            # x: (batch, n_channels, win_len) -> (batch, emb_dim)
            h = self.blocks(x)                      # (batch, C, L')
            h = h.mean(dim=-1)                       # global average pool over time
            return self.head(h)                      # (batch, emb_dim)

    return _Encoder()


class WaveformEncoder:
    """Thin wrapper around the torch encoder module.

    Exposes ``module`` (the nn.Module), ``forward``/``__call__`` (delegates), and
    ``count_parameters``. Kept as a wrapper so the rest of the package never imports
    torch at module load -- consistent with the repo's lazy-heavy-import convention.
    """

    def __init__(self, n_channels: int,
                 base_channels: int = DEFAULT_BASE_CHANNELS,
                 emb_dim: int = DEFAULT_EMB_DIM,
                 n_blocks: int = DEFAULT_N_BLOCKS,
                 kernel_size: int = DEFAULT_KERNEL_SIZE,
                 dropout: float = DEFAULT_DROPOUT):
        self.n_channels = int(n_channels)
        self.emb_dim = int(emb_dim)
        self.module = _make_module(
            n_channels, base_channels, emb_dim, n_blocks, kernel_size, dropout
        )

    def __call__(self, x):
        return self.module(x)

    def forward(self, x):
        return self.module(x)

    def parameters(self):
        return self.module.parameters()

    def eval(self):
        self.module.eval()
        return self

    def train(self, mode: bool = True):
        self.module.train(mode)
        return self

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.module.parameters() if p.requires_grad)

    def embed_windows(self, windows):
        """Embed (n_windows, n_channels, win_len) -> (n_windows, emb_dim) numpy array.

        No-grad inference (frozen-style use for the H3 head-to-head feature export).
        """
        import numpy as np
        import torch

        self.module.eval()
        x = torch.from_numpy(np.asarray(windows, dtype="float32"))
        if x.dim() != 3:
            raise ValueError("windows must be (n_windows, n_channels, win_len)")
        with torch.no_grad():
            emb = self.module(x)
        return emb.detach().cpu().numpy()


def mean_pool_embeddings(window_embeddings):
    """Pool (n_windows, emb_dim) -> (emb_dim,) per-case vector by mean over windows.

    Pure NumPy; the contract the frozen per-case embedding export depends on
    (mirrors ``pipeline.embed.pool_embeddings`` with the "mean" op).
    """
    import numpy as np

    we = np.asarray(window_embeddings, dtype="float64")
    if we.ndim != 2 or we.shape[0] == 0:
        raise ValueError("window_embeddings must be (n_windows>0, emb_dim)")
    return we.mean(axis=0).astype("float32")
