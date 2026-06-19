"""audits.py -- the refutation battery (Sec 11, 13, 17).

The agentic loop's job is to *break* candidate phenotypes, never to generate
hypotheses. This module runs, on the compact tables:

  * negative controls that MUST fail:
      - shuffled outcome -> association collapses to chance;
      - phase-randomized surrogate embeddings -> structure collapses;
  * leave-one-site-out reproducibility;
  * acquisition-covariate association (sampling rate, montage, length).

Every audit is reported regardless of result.
"""
from __future__ import annotations

from typing import Any


def negative_control_shuffled_outcome(labels, outcome, cfg: dict[str, Any],
                                     n_perm: int = 200) -> dict[str, Any]:
    """Under shuffled outcome, phenotype<->outcome association must collapse to
    chance. Returns the permutation distribution summary. (Phase-2 audit; the
    real outcome stays sealed -- pass a permuted/synthetic vector here.)"""
    import numpy as np
    from sklearn.metrics import mutual_info_score

    rng = np.random.default_rng(cfg.get("seed", 0))
    labels = np.asarray(labels)
    outcome = np.asarray(outcome)
    perms = []
    for _ in range(n_perm):
        perms.append(mutual_info_score(labels, rng.permutation(outcome)))
    perms = np.asarray(perms)
    return {"mean_mi_under_null": float(perms.mean()),
            "p95_mi_under_null": float(np.percentile(perms, 95)),
            "n_perm": n_perm}


def clustering_structure_score(X, labels) -> float:
    """A single scalar for "how much cluster structure is present" -- the mean
    silhouette of the labeling. Returns 0.0 when <2 clusters or degenerate."""
    import numpy as np
    from sklearn.metrics import silhouette_score

    X = np.asarray(X, dtype="float64")
    labels = np.asarray(labels)
    if len(set(labels.tolist())) < 2 or X.shape[0] <= len(set(labels.tolist())):
        return 0.0
    try:
        return float(silhouette_score(X, labels))
    except ValueError:
        return 0.0


def phase_randomized_surrogate(X, rng):
    """Embedding-table analog of phase-randomized surrogate EEG: independently
    permute each embedding dimension across recordings. This destroys the joint
    (cross-dimension) structure that clusters live in while preserving every
    marginal distribution -- so genuine phenotype structure must beat it."""
    import numpy as np
    X = np.asarray(X, dtype="float64")
    out = np.empty_like(X)
    for j in range(X.shape[1]):
        out[:, j] = X[rng.permutation(X.shape[0]), j]
    return out


def surrogate_structure_collapse(structure_score_real: float,
                                surrogate_scores: list[float]) -> dict[str, Any]:
    """Phase-randomized surrogate EEG (computed transiently on streamed raw)
    must destroy phenotype structure. Real clustering-quality must exceed the
    surrogate distribution; otherwise the 'structure' is an artifact."""
    import numpy as np
    s = np.asarray(surrogate_scores, dtype="float64")
    thr = float(np.percentile(s, 95)) if s.size else float("nan")
    return {"real_score": float(structure_score_real),
            "surrogate_p95": thr,
            "structure_is_real": bool(structure_score_real > thr)}


def leave_one_site_out(embeddings, sites, assigner_factory, cfg: dict[str, Any]) -> dict[str, Any]:
    """Structure derived while excluding each discovery site must persist
    (Sec 11). Returns per-held-site ARI between the full-data and LOSO
    assignments on the held-site rows."""
    import numpy as np
    from sklearn.metrics import adjusted_rand_score

    X = np.asarray(embeddings, dtype="float64")
    sites = np.asarray(sites)
    full = assigner_factory().fit(X)
    full_lab = full.assign(X)
    results = {}
    for s in sorted(set(sites.tolist())):
        keep = sites != s
        loso = assigner_factory().fit(X[keep])
        held = sites == s
        if held.sum() < 5:
            continue
        ari = adjusted_rand_score(full_lab[held], loso.assign(X[held]))
        results[str(s)] = float(ari)
    return {"per_site_ari": results,
            "min_ari": float(min(results.values())) if results else float("nan")}


def acquisition_covariate_association(labels, covariates: dict[str, Any],
                                     cfg: dict[str, Any]) -> dict[str, Any]:
    """Flag phenotypes that depend on acquisition covariates (sampling rate,
    montage, recording length) -- a batch artifact red flag (Sec 11)."""
    import numpy as np
    from sklearn.metrics import mutual_info_score

    labels = np.asarray(labels)
    out = {}
    for name, vals in covariates.items():
        v = np.asarray(vals)
        if v.dtype.kind in "fc":  # continuous -> coarse bins for MI
            v = np.digitize(v, np.nanquantile(v[~np.isnan(v)], [.25, .5, .75]))
        out[name] = {"mutual_info": float(mutual_info_score(labels, v))}
    return out
