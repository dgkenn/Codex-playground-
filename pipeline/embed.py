"""embed.py -- frozen foundation-model forward pass + pooling (Sec 7.1, 7.3).

Loads an open EEG foundation-model checkpoint (default: CBraMod), frozen, and
runs windows through it with no gradients and no activation storage (Sec 0). The
per-window embeddings are pooled to one compact per-recording vector (mean+std
by default). Epoch-level embeddings are persisted only for a small random
subsample reserved for stability analysis (Sec 7.3).

torch + the model are imported lazily. `pool_embeddings` is a pure NumPy/stdlib
function so the pooling contract is testable without the model.

CBraMod architecture reference
-------------------------------
CBraMod (Chen et al., 2024; https://github.com/wh-xu/cbramod) is a masked
auto-encoder pre-trained on continuous scalp EEG at 200 Hz. Its encoder expects
a tensor of shape (batch, n_channels, n_patches, patch_size) where

    patch_size  = sfreq * patch_seconds   (= 200 samples @ 200 Hz, 1 s)
    n_patches   = n_samples // patch_size

The model returns per-token (patch x channel) representations. We mean-pool
those to one (batch, d_model) embedding per window.

NOTE: The reshape logic and CBraMod constructor call below are implemented
against the published braindecode / CBraMod interface and have NOT been
validated on real weights in this environment. Validation requires
`pip install torch braindecode huggingface_hub` and the actual checkpoint.
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
    """Wraps a frozen CBraMod checkpoint; verifies its hash before first use (Sec 3).

    Usage
    -----
    embedder = FrozenEmbedder(cfg)
    embedder.load()                          # downloads + verifies + freezes
    emb = embedder.embed_windows(windows)    # (n_windows, n_ch, n_samples) -> (n_windows, d)
    """

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.model = None
        self.checkpoint_path: str | None = None
        self._verified = False

    def load(self, checkpoint_path: str | None = None):
        """Load, verify, and freeze the CBraMod checkpoint.

        Parameters
        ----------
        checkpoint_path : str | None
            Path to the local ``pretrained_weights.pth`` file.  If *None*
            the file is downloaded from Hugging Face Hub using the coordinates
            in ``cfg.model`` (repo_id, checkpoint_file, revision).

        Raises
        ------
        ImportError
            If ``torch``, ``braindecode``, or ``huggingface_hub`` are not
            installed.
        ValueError
            If the SHA-256 of the checkpoint does not match the pinned value
            in the config (only enforced when the config value is not
            ``TO-CONFIRM``).

        Notes
        -----
        The CBraMod constructor call below uses the parameters that braindecode
        exposes via ``braindecode.models.CBraMod``.  If the installed version
        uses different keyword names the constructor may need adjusting.  This
        implementation has NOT been validated on real weights; validate on
        hardware before running Phase-1 embedding.
        """
        # ------------------------------------------------------------------
        # 1. Guard: make sure heavy dependencies are available before we
        #    try anything else.  Fail with an actionable message.
        # ------------------------------------------------------------------
        try:
            import torch  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "torch is required to load the CBraMod checkpoint. "
                "Install with: pip install torch braindecode huggingface_hub"
            ) from exc

        try:
            import braindecode  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "braindecode is required to build the CBraMod architecture. "
                "Install with: pip install torch braindecode huggingface_hub"
            ) from exc

        # ------------------------------------------------------------------
        # 2. Resolve checkpoint path (download if not given).
        # ------------------------------------------------------------------
        model_cfg = self.cfg["model"]

        if checkpoint_path is None:
            try:
                from huggingface_hub import hf_hub_download
            except ImportError as exc:
                raise ImportError(
                    "huggingface_hub is required for automatic checkpoint "
                    "download. Install with: pip install huggingface_hub"
                ) from exc

            repo_id = model_cfg["repo_id"]
            filename = model_cfg["checkpoint_file"]
            revision = model_cfg.get("revision", "main")

            # Pass revision only when it is a pinned commit SHA so the
            # download is fully reproducible; "main" is the HF default.
            dl_kwargs: dict[str, Any] = {"repo_id": repo_id, "filename": filename}
            if revision and revision != "main":
                dl_kwargs["revision"] = revision

            checkpoint_path = hf_hub_download(**dl_kwargs)

        # ------------------------------------------------------------------
        # 3. SHA-256 verification (firewall, Sec 3).
        # ------------------------------------------------------------------
        expected = model_cfg.get("checkpoint_sha256")
        actual = hash_file(checkpoint_path)
        if expected and not str(expected).upper().startswith("TO-CONFIRM"):
            if actual.lower() != str(expected).lower():
                raise ValueError(
                    f"checkpoint hash mismatch:\n"
                    f"  expected : {expected}\n"
                    f"  actual   : {actual}\n"
                    f"  file     : {checkpoint_path}\n"
                    "Re-download the checkpoint or update checkpoint_sha256 in config.yaml."
                )

        self.checkpoint_path = checkpoint_path
        self._verified = True

        # ------------------------------------------------------------------
        # 4. Build the CBraMod architecture and load weights.
        # ------------------------------------------------------------------
        import torch
        from braindecode.models import CBraMod  # type: ignore[import]

        n_chans = len(model_cfg["channels_10_20"])
        sfreq = float(model_cfg["expected_sfreq_hz"])

        # braindecode's CBraMod signature (as of braindecode >= 0.8):
        #   CBraMod(n_chans, sfreq, ...)
        # Additional kwargs (n_times, n_classes, etc.) are omitted here so
        # braindecode uses its defaults, which match the pre-training regime.
        # If the installed version requires different arguments, adjust below
        # and document the version constraint.
        self.model = CBraMod(n_chans=n_chans, sfreq=sfreq)

        # ------------------------------------------------------------------
        # 5. Load state dict -- handle common checkpoint layouts.
        # ------------------------------------------------------------------
        raw = torch.load(checkpoint_path, map_location="cpu")

        if isinstance(raw, dict):
            # Some checkpoints wrap weights under a key.
            if "model" in raw:
                state_dict = raw["model"]
            elif "state_dict" in raw:
                state_dict = raw["state_dict"]
            else:
                # Assume the dict itself is the state dict.
                state_dict = raw
        else:
            # Older-style torch.save of the model object (rare but possible).
            state_dict = raw.state_dict()

        # strict=False lets us load when the checkpoint has extra keys
        # (e.g. pre-training decoder weights not needed for inference).
        missing, unexpected = self.model.load_state_dict(state_dict, strict=False)
        if missing:
            import warnings
            warnings.warn(
                f"CBraMod load_state_dict: {len(missing)} missing keys "
                f"(first few: {missing[:5]}). Forward pass may be incorrect.",
                UserWarning,
                stacklevel=2,
            )

        # ------------------------------------------------------------------
        # 6. Freeze: eval mode + no gradients anywhere.
        # ------------------------------------------------------------------
        self.model.eval()
        for param in self.model.parameters():
            param.requires_grad = False

    @torch_inference
    def embed_windows(self, windows):
        """Embed a batch of EEG windows via the frozen CBraMod encoder.

        Parameters
        ----------
        windows : numpy.ndarray, shape (n_windows, n_channels, n_samples)
            Pre-harmonised EEG at ``cfg.model.expected_sfreq_hz`` Hz.
            ``n_samples`` should equal ``window_seconds * expected_sfreq_hz``
            (= 6 000 samples for 30 s @ 200 Hz); any trailing remainder that
            does not fill a complete patch is silently discarded.

        Returns
        -------
        numpy.ndarray, shape (n_windows, d)
            One embedding vector per window.  ``d`` is CBraMod's hidden
            dimension (512 by default in the published checkpoint).

        Raises
        ------
        RuntimeError
            If :meth:`load` has not been called yet.

        Notes
        -----
        CBraMod patch layout
        ~~~~~~~~~~~~~~~~~~~~
        The model expects ``(batch, n_channels, n_patches, patch_size)``
        where ``patch_size = round(patch_seconds * sfreq)`` (= 200 samples).
        We reshape the input accordingly and trim any trailing remainder::

            patch_size  = round(patch_seconds * sfreq)   # 200
            n_patches   = n_samples // patch_size         # 30 for a 30-s window
            x           = x[:, :, :n_patches*patch_size] # trim remainder
            x           = x.reshape(n_win, n_ch, n_patches, patch_size)

        Output pooling
        ~~~~~~~~~~~~~~
        CBraMod's encoder returns either a plain tensor of shape
        ``(batch, n_tokens, d)`` or a tuple whose first element is that
        tensor.  We mean-pool over the token dimension (axis=1) to obtain
        ``(batch, d)``.  If the output has more than three dimensions we
        flatten trailing dims first so callers always receive ``(n_windows, d)``.

        This has NOT been validated on real weights -- validate on hardware.
        """
        # Guard: model must be loaded. This check runs BEFORE any torch import
        # so that the RuntimeError is testable even without torch installed.
        if self.model is None:
            raise RuntimeError(
                "call load() before embed_windows(). "
                "The model has not been initialised."
            )

        import torch
        import numpy as np

        model_cfg = self.cfg["model"]
        sfreq = float(model_cfg["expected_sfreq_hz"])
        patch_seconds = float(model_cfg.get("patch_seconds", 1.0))
        patch_size = round(patch_seconds * sfreq)  # 200 samples @ 200 Hz

        # Convert input to float32 tensor on CPU.
        x = torch.from_numpy(np.asarray(windows, dtype="float32"))
        # x: (n_windows, n_channels, n_samples)
        n_win, n_ch, n_samples = x.shape

        # Trim to a multiple of patch_size and reshape into patch layout.
        n_patches = n_samples // patch_size
        if n_patches == 0:
            raise ValueError(
                f"window length {n_samples} samples is shorter than one patch "
                f"({patch_size} samples). Increase window_seconds or reduce "
                "patch_seconds in the config."
            )
        x = x[:, :, : n_patches * patch_size]           # trim remainder
        x = x.reshape(n_win, n_ch, n_patches, patch_size)
        # x: (n_windows, n_channels, n_patches, patch_size) -- CBraMod input

        # Forward pass (torch.no_grad is already active via @torch_inference).
        output = self.model(x)

        # Unwrap tuple outputs (some braindecode models return (embeddings, ...)).
        if isinstance(output, (tuple, list)):
            output = output[0]

        # output is expected to be (batch, n_tokens, d).
        # Be defensive about rank so callers always get (n_windows, d).
        if output.dim() == 2:
            # Already (batch, d) -- nothing to pool.
            feats = output
        elif output.dim() == 3:
            # (batch, n_tokens, d) -- mean-pool over token dimension.
            feats = output.mean(dim=1)
        else:
            # Unexpected rank: flatten everything beyond the batch dim, then
            # mean-pool so we still return (n_windows, d).
            batch = output.shape[0]
            feats = output.reshape(batch, -1).mean(dim=1, keepdim=True)

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
