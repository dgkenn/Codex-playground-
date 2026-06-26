"""metrics.py -- incremental-value statistics (Sec 12).

The primary contrast is ΔAUROC between two nested models on the SAME patients, so
the AUCs are correlated and an independent test is wrong. We use the fast DeLong
method (Sun & Xu 2014) for the correlated-ROC variance, plus continuous NRI and
IDI (Pencina 2008) and patient-level bootstrap CIs.

numpy/scipy are imported at module load (this stage already requires the science
stack); nothing here touches the network.
"""
from __future__ import annotations

import numpy as np


# --------------------------------------------------------------------------
# Fast DeLong (Sun & Xu, IEEE SPL 2014) -- midrank implementation.
# --------------------------------------------------------------------------
def _midrank(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x)
    x_sorted = x[order]
    n = len(x)
    t = np.zeros(n)
    i = 0
    while i < n:
        j = i
        while j < n and x_sorted[j] == x_sorted[i]:
            j += 1
        t[i:j] = 0.5 * (i + j - 1) + 1  # 1-based midrank
        i = j
    out = np.empty(n)
    out[order] = t
    return out


def _fast_delong(predictions_sorted: np.ndarray, m: int):
    """Return (aucs, covariance) for k predictors; first m samples are positives.
    `predictions_sorted` is (k, n) with positives in the first m columns."""
    k, n = predictions_sorted.shape
    nneg = n - m
    tx = np.empty([k, m]); ty = np.empty([k, nneg]); tz = np.empty([k, n])
    for r in range(k):
        tx[r] = _midrank(predictions_sorted[r, :m])
        ty[r] = _midrank(predictions_sorted[r, m:])
        tz[r] = _midrank(predictions_sorted[r])
    aucs = (tz[:, :m].sum(axis=1) / m - (m + 1) / 2.0) / nneg
    v01 = (tz[:, :m] - tx) / nneg
    v10 = 1.0 - (tz[:, m:] - ty) / m
    sx = np.cov(v01)
    sy = np.cov(v10)
    s = sx / m + sy / nneg
    s = np.atleast_2d(s)
    return aucs, s


def delong_roc_test(y_true, prob_a, prob_b):
    """Two correlated AUCs on the same samples. Returns dict with auc_a/auc_b,
    delta (b - a), z, and two-sided p for H0: AUC_a == AUC_b."""
    from scipy import stats

    y = np.asarray(y_true).astype(int)
    a = np.asarray(prob_a, float)
    b = np.asarray(prob_b, float)
    order = np.argsort(-y)  # positives (1) first
    y = y[order]; a = a[order]; b = b[order]
    m = int(y.sum())
    if m == 0 or m == len(y):
        raise ValueError("need both classes present")
    preds = np.vstack([a, b])[:, :]
    aucs, cov = _fast_delong(preds, m)
    var = cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]
    delta = aucs[1] - aucs[0]
    z = delta / np.sqrt(var) if var > 0 else 0.0
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    return {"auc_a": float(aucs[0]), "auc_b": float(aucs[1]),
            "delta": float(delta), "z": float(z), "p_value": float(p),
            "var_delta": float(var)}


# --------------------------------------------------------------------------
# Continuous NRI and IDI (Pencina et al. 2008).
# --------------------------------------------------------------------------
def idi_nri(y_true, prob_old, prob_new):
    """Continuous (category-free) NRI and IDI for new vs old risk model."""
    y = np.asarray(y_true).astype(int)
    old = np.asarray(prob_old, float)
    new = np.asarray(prob_new, float)
    ev = y == 1; nonev = y == 0
    d = new - old
    # continuous NRI: events moving up - down; non-events moving down - up
    nri_e = np.mean(d[ev] > 0) - np.mean(d[ev] < 0)
    nri_ne = np.mean(d[nonev] < 0) - np.mean(d[nonev] > 0)
    nri = nri_e + nri_ne
    # IDI: change in discrimination slope
    idi = (new[ev].mean() - old[ev].mean()) - (new[nonev].mean() - old[nonev].mean())
    return {"nri": float(nri), "nri_events": float(nri_e),
            "nri_nonevents": float(nri_ne), "idi": float(idi)}


# --------------------------------------------------------------------------
# Patient-level bootstrap CI for any paired statistic.
# --------------------------------------------------------------------------
def bootstrap_ci(stat_fn, y_true, prob_a, prob_b, groups, n_iter=2000,
                 seed=0, alpha=0.05):
    """Cluster (patient) bootstrap CI for stat_fn(y, a, b) -> float. Resamples
    whole patients (groups) so within-patient correlation is respected (Sec 11.6)."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y_true); a = np.asarray(prob_a, float); b = np.asarray(prob_b, float)
    g = np.asarray(groups)
    uniq = np.unique(g)
    idx_by_g = {u: np.where(g == u)[0] for u in uniq}
    stats_out = []
    for _ in range(n_iter):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_g[u] for u in pick])
        yy = y[idx]
        if yy.min() == yy.max():
            continue
        try:
            stats_out.append(stat_fn(yy, a[idx], b[idx]))
        except Exception:
            continue
    if not stats_out:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(stats_out, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(lo), float(hi))
