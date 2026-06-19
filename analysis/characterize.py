"""characterize.py -- interpretable phenotype signatures (Sec 10).

Descriptive ONLY. Maps each phenotype onto the interpretable feature space
(band powers, aperiodic exponent/offset, connectivity, entropy, microstates) to
give a spectral/connectivity profile, and reports demographic distributions for
interpretation. Binding constraint: nothing here may be used to choose the
Phase-2 outcome (which is pre-specified before unlock).
"""
from __future__ import annotations

from typing import Any


def phenotype_feature_profile(features, labels, feature_names: list[str]) -> dict[str, Any]:
    """Per-phenotype mean of each interpretable feature, plus the standardized
    effect (Cohen's d vs the rest) so the signature is comparable across
    features. Purely descriptive."""
    import numpy as np

    F = np.asarray(features, dtype="float64")
    labels = np.asarray(labels)
    out: dict[str, Any] = {"feature_names": feature_names, "phenotypes": {}}
    for c in sorted(set(labels.tolist())):
        in_c = labels == c
        mu_in = np.nanmean(F[in_c], axis=0)
        mu_out = np.nanmean(F[~in_c], axis=0)
        sd = np.nanstd(F, axis=0) + 1e-9
        cohens_d = (mu_in - mu_out) / sd
        order = np.argsort(-np.abs(cohens_d))
        top = [(feature_names[i], float(cohens_d[i])) for i in order[:15]]
        out["phenotypes"][int(c)] = {
            "n": int(in_c.sum()),
            "mean": mu_in.tolist(),
            "top_distinguishing_features": top,
        }
    return out


def probe_embedding_to_features(embeddings, features, cfg: dict[str, Any]) -> dict[str, float]:
    """Linear probe R^2: how much of each interpretable feature the frozen
    embedding linearly encodes. Characterization, not an outcome test."""
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import cross_val_score

    X = np.asarray(embeddings, dtype="float64")
    F = np.asarray(features, dtype="float64")
    seed = cfg.get("seed", 0)
    r2: dict[str, float] = {}
    for j in range(F.shape[1]):
        y = F[:, j]
        if np.all(np.isnan(y)) or np.nanstd(y) < 1e-9:
            continue
        mask = ~np.isnan(y)
        if mask.sum() < 20:
            continue
        scores = cross_val_score(Ridge(alpha=1.0), X[mask], y[mask],
                                 cv=5, scoring="r2")
        r2[str(j)] = float(np.mean(scores))
    return r2
