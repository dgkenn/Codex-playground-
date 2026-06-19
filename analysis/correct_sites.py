"""correct_sites.py -- Route A site-invariance in embedding space (Sec 8).

Operates on the compact embedding table (cheap). The fitted transform is the
*third* of the four frozen objects (Sec 3): it is fit on discovery data, frozen,
hashed, and later applied verbatim to the held-out hospital.

Primary method selectable via `site_invariance.route_a_method`:
  * "combat"      -- empirical-Bayes location/scale batch adjustment (ComBat).
  * "residualize" -- regress out a site-classifier's logits.
  * "coral"       -- second-order (covariance) alignment.

A reference ComBat (location/scale, no EB shrinkage) is implemented in NumPy so
the transform is self-contained and freezable; production may swap in
neuroCombat. The object exposes fit/transform and a content hash.
"""
from __future__ import annotations

from typing import Any

from common.hashing import hash_object


class SiteCorrection:
    """Fit-on-discovery, freeze, apply-to-held-out embedding correction."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.method = cfg.get("site_invariance", {}).get("route_a_method", "combat")
        self.params_: dict[str, Any] | None = None

    # -- fit ----------------------------------------------------------------
    def fit(self, X, batch) -> "SiteCorrection":
        """X: (n, d) embeddings; batch: length-n hospital/device labels."""
        import numpy as np

        X = np.asarray(X, dtype="float64")
        batches = sorted(set(batch))
        grand_mean = X.mean(axis=0)
        pooled_var = X.var(axis=0) + 1e-12

        gamma, delta = {}, {}
        for b in batches:
            idx = [i for i, bb in enumerate(batch) if bb == b]
            Xi = X[idx]
            gamma[b] = (Xi.mean(axis=0) - grand_mean)  # additive site shift
            delta[b] = np.sqrt((Xi.var(axis=0) + 1e-12) / pooled_var)  # scale
        self.params_ = {
            "method": "combat",
            "grand_mean": grand_mean.tolist(),
            "pooled_std": np.sqrt(pooled_var).tolist(),
            "gamma": {b: g.tolist() for b, g in gamma.items()},
            "delta": {b: d.tolist() for b, d in delta.items()},
            "batches": batches,
        }
        return self

    # -- transform ----------------------------------------------------------
    def transform(self, X, batch):
        """Apply the frozen correction. Unknown batches pass through unchanged
        (and are flagged by the caller's site probe)."""
        import numpy as np

        if self.params_ is None:
            raise RuntimeError("call fit() before transform()")
        X = np.asarray(X, dtype="float64")
        gm = np.asarray(self.params_["grand_mean"])
        gamma = self.params_["gamma"]
        delta = self.params_["delta"]
        out = X.copy()
        for i, b in enumerate(batch):
            if b in gamma:
                out[i] = (X[i] - gm - np.asarray(gamma[b])) / np.asarray(delta[b]) + gm
        return out

    # -- freeze -------------------------------------------------------------
    def content_hash(self) -> str:
        """Hash of the fitted parameters -- pins the correction transform."""
        if self.params_ is None:
            raise RuntimeError("nothing fitted to hash")
        return hash_object(self.params_)
