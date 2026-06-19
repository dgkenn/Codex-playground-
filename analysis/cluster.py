"""cluster.py -- phenotype discovery + the "real phenotype" bar (Sec 9).

On the *corrected* embeddings: cluster, choose k by a stability criterion
(consensus clustering / PAC, never by interpretability), and admit a cluster as
a phenotype only if it is resampling-stable AND cross-site reproducible AND
survives the site audit.

The fitted assignment function is the *fourth* frozen object (Sec 3).
scikit-learn / NumPy are imported lazily.
"""
from __future__ import annotations

from typing import Any

from common.hashing import hash_object


def _fit_labels(X, k: int, algorithm: str, seed: int):
    import numpy as np  # noqa: F401
    if algorithm == "gmm":
        from sklearn.mixture import GaussianMixture
        gm = GaussianMixture(n_components=k, random_state=seed, n_init=1)
        return gm.fit_predict(X)
    from sklearn.cluster import KMeans  # fallback proxy for Leiden in this seam
    return KMeans(n_clusters=k, random_state=seed, n_init=10).fit_predict(X)


def consensus_pac(X, cfg: dict[str, Any]) -> dict[int, float]:
    """Proportion of Ambiguous Clustering (PAC) per candidate k (lower=better).

    Consensus clustering (Monti 2003): repeatedly subsample, cluster, and build
    a co-assignment matrix; PAC is the fraction of pairs whose consensus index
    falls in the ambiguous band (pac_low, pac_high). k is chosen at min PAC.
    """
    import numpy as np

    cc = cfg["clustering"]
    cons = cc["consensus"]
    seed = cfg.get("seed", 0)
    rng = np.random.default_rng(seed)
    X = np.asarray(X, dtype="float64")
    n = X.shape[0]
    frac = cons["subsample_fraction"]
    R = cons["n_resamples"]
    lo, hi = cons["pac_low"], cons["pac_high"]

    pac: dict[int, float] = {}
    for k in cc["k_candidates"]:
        co = np.zeros((n, n))
        cnt = np.zeros((n, n))
        for _ in range(R):
            idx = rng.choice(n, size=int(frac * n), replace=False)
            lab = _fit_labels(X[idx], k, cc["algorithm"], int(rng.integers(1 << 30)))
            same = (lab[:, None] == lab[None, :]).astype(float)
            co[np.ix_(idx, idx)] += same
            cnt[np.ix_(idx, idx)] += 1
        with np.errstate(invalid="ignore"):
            consensus = np.where(cnt > 0, co / np.maximum(cnt, 1), 0.0)
        iu = np.triu_indices(n, k=1)
        vals = consensus[iu]
        ambiguous = np.mean((vals > lo) & (vals < hi))
        pac[int(k)] = float(ambiguous)
    return pac


def select_k(pac: dict[int, float]) -> int:
    """Pick k minimising PAC (the pre-specified stability criterion, Sec 9)."""
    return min(pac, key=pac.get)


def stability_score(X, k: int, cfg: dict[str, Any]) -> float:
    """Mean adjusted-Rand similarity of labelings across resamples (Sec 9)."""
    import numpy as np
    from sklearn.metrics import adjusted_rand_score

    seed = cfg.get("seed", 0)
    rng = np.random.default_rng(seed)
    X = np.asarray(X, dtype="float64")
    n = X.shape[0]
    base = _fit_labels(X, k, cfg["clustering"]["algorithm"], seed)
    scores = []
    for _ in range(20):
        idx = rng.choice(n, size=int(0.8 * n), replace=False)
        lab = _fit_labels(X[idx], k, cfg["clustering"]["algorithm"],
                          int(rng.integers(1 << 30)))
        scores.append(adjusted_rand_score(base[idx], lab))
    return float(np.mean(scores))


class PhenotypeAssigner:
    """Frozen phenotype-assignment function (the 4th frozen object, Sec 3).

    Fit on corrected discovery embeddings; applied verbatim to the held-out
    hospital. Backed by a GMM so assignment is a deterministic function of the
    embedding.
    """

    def __init__(self, cfg: dict[str, Any], k: int):
        self.cfg = cfg
        self.k = k
        self.model = None

    def fit(self, X) -> "PhenotypeAssigner":
        from sklearn.mixture import GaussianMixture
        self.model = GaussianMixture(
            n_components=self.k, random_state=self.cfg.get("seed", 0), n_init=5
        ).fit(X)
        return self

    def assign(self, X):
        if self.model is None:
            raise RuntimeError("fit() first")
        return self.model.predict(X)

    def content_hash(self) -> str:
        import numpy as np
        if self.model is None:
            raise RuntimeError("nothing fitted to hash")
        params = {
            "k": self.k,
            "means": np.asarray(self.model.means_).round(6).tolist(),
            "weights": np.asarray(self.model.weights_).round(6).tolist(),
            "covariance_type": self.model.covariance_type,
        }
        return hash_object(params)


def cross_site_reproducibility(assigner: PhenotypeAssigner, X_site, X_redrived_labels,
                              cfg: dict[str, Any]) -> dict[str, Any]:
    """Compare frozen assignments to an independently re-derived clustering on a
    held-out site; phenotype passes if ARI >= the pre-specified threshold
    (Sec 6, 9)."""
    from sklearn.metrics import adjusted_rand_score

    thr = cfg["sites"]["reproducibility_ari_threshold"]
    frozen = assigner.assign(X_site)
    ari = float(adjusted_rand_score(frozen, X_redrived_labels))
    return {"ari": ari, "threshold": thr, "pass": ari >= thr}
