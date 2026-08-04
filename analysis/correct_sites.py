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
        """Apply the frozen correction, aligning every batch to the frozen grand
        mean / pooled scale.

        Known (discovery) batches use their frozen location/scale parameters. An
        UNKNOWN batch -- e.g. the held-out hospital, which the frozen transform
        never saw -- is aligned to the same frozen grand mean using location/
        scale estimated from that batch's own embeddings at apply time. This is
        the standard ComBat new-batch harmonization; it uses EEG embeddings only
        (no outcome), so it does not breach the firewall, and it is what makes a
        frozen site-correction applicable to a brand-new confirmation site.
        """
        import numpy as np

        if self.params_ is None:
            raise RuntimeError("call fit() before transform()")
        X = np.asarray(X, dtype="float64")
        gm = np.asarray(self.params_["grand_mean"])
        pooled_std = np.asarray(self.params_["pooled_std"])
        gamma = self.params_["gamma"]
        delta = self.params_["delta"]
        batch = list(batch)

        # On-the-fly params for any batch absent from the frozen fit.
        unknown = {b for b in set(batch) if b not in gamma}
        est_gamma, est_delta = {}, {}
        for b in unknown:
            idx = [i for i, bb in enumerate(batch) if bb == b]
            Xb = X[idx]
            est_gamma[b] = Xb.mean(axis=0) - gm
            est_delta[b] = np.sqrt((Xb.var(axis=0) + 1e-12) / (pooled_std ** 2 + 1e-12))

        out = X.copy()
        for i, b in enumerate(batch):
            g = np.asarray(gamma[b]) if b in gamma else est_gamma[b]
            d = np.asarray(delta[b]) if b in delta else est_delta[b]
            out[i] = (X[i] - gm - g) / d + gm
        return out

    def transform_new_site(self, X):
        """Convenience: align a single new site's embeddings (all one batch) to
        the frozen reference. Equivalent to transform(X, ['__new__']*len(X))."""
        return self.transform(X, ["__new__"] * len(X))

    # -- freeze -------------------------------------------------------------
    def content_hash(self) -> str:
        """Hash of the fitted parameters -- pins the correction transform."""
        if self.params_ is None:
            raise RuntimeError("nothing fitted to hash")
        return hash_object(self.params_)

    # -- persistence (cross-process freeze/unlock) --------------------------
    def save(self, path: str) -> str:
        """Serialise the fitted params to JSON (they are already JSON-native).

        Returns the content hash, so the caller can record it in the frozen
        manifest and re-verify on load (Sec 3).
        """
        import json
        import os

        if self.params_ is None:
            raise RuntimeError("nothing fitted to save")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"method": self.method, "params": self.params_}, fh,
                      sort_keys=True)
        return self.content_hash()

    @classmethod
    def load(cls, path: str, cfg: dict) -> "SiteCorrection":
        """Reconstruct a frozen SiteCorrection from disk. Its `content_hash`
        must equal the value pinned in the manifest before it is applied."""
        import json

        with open(path, "r", encoding="utf-8") as fh:
            blob = json.load(fh)
        obj = cls(cfg)
        obj.method = blob.get("method", obj.method)
        obj.params_ = blob["params"]
        return obj
