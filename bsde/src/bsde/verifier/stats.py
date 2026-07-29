"""Statistical primitives for the verifier. NumPy only, no scipy, no sklearn.

Two deliberate departures from the implementations in the sibling project's `analysis/` scripts:

1. **`auc` uses MIDRANKS.** The sibling implementation ranks with `argsort(kind="mergesort")`, which assigns
   distinct ranks to tied scores and therefore reports a biased AUC whenever the score is discrete or
   saturates. That is tolerable for continuous morphology features and intolerable here, because the verifier
   will be handed constant and near-constant candidates on purpose — a planted confound whose score is a site
   indicator is *all* ties. `test_verifier_stats.py` pins the tied case against a hand-computed value.

2. **Bootstrap resamples SUBJECTS, not rows** (`cluster_bootstrap_ci`). Resampling windows or epochs from the
   same patient understates uncertainty by however many windows each patient contributed. Rule 10 of the
   sibling project's error catalogue was paid for with a wrong result of exactly this kind.
"""
from __future__ import annotations

from typing import Callable, Sequence

import numpy as np


def auc(y: Sequence, score: Sequence) -> float:
    """Area under the ROC curve, tie-corrected (Mann-Whitney U with midranks).

    Returns NaN when either class is empty — never 0.5, which would read as "no discrimination" when the
    truth is "not evaluable".
    """
    y = np.asarray(y, float)
    s = np.asarray(score, float)
    ok = np.isfinite(y) & np.isfinite(s)
    y, s = y[ok], s[ok]
    n1 = float((y == 1).sum())
    n0 = float((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((_midranks(s)[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def _midranks(s: np.ndarray) -> np.ndarray:
    """Ranks 1..n with ties receiving the average of the ranks they span."""
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), float)
    ranks[order] = np.arange(1, len(s) + 1, dtype=float)
    srt = s[order]
    i = 0
    while i < len(srt):
        j = i
        while j + 1 < len(srt) and srt[j + 1] == srt[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0  # mean of ranks i+1 .. j+1
        i = j + 1
    return ranks


def auc_abs(y: Sequence, score: Sequence) -> float:
    """Direction-free discrimination, `max(a, 1-a)`, on [0.5, 1].

    Used ONLY for nuisance probes, where the question is "does this representation carry information about
    site?" and the sign is meaningless. It is never used for a candidate's primary claim, because a candidate
    that fires in the direction OPPOSITE to its declared prediction has been refuted, not confirmed
    (`directional_auc` enforces that).
    """
    a = auc(y, score)
    return float("nan") if not np.isfinite(a) else max(a, 1.0 - a)


def directional_auc(y: Sequence, score: Sequence, predicted: str) -> float:
    """AUC oriented so that > 0.5 means "moved in the DECLARED direction".

    predicted is "higher" (score higher in the y==1 group) or "lower". Any other value raises: a candidate
    that predicted "unchanged" cannot be scored by discrimination, and silently picking a direction here is
    exactly how a two-sided result becomes a one-sided claim.
    """
    if predicted not in ("higher", "lower"):
        raise ValueError(f"directional_auc needs a signed prediction, got {predicted!r}")
    a = auc(y, score)
    return a if predicted == "higher" else (1.0 - a if np.isfinite(a) else a)


def spearman(x: Sequence, y: Sequence) -> float:
    """Rank correlation, tie-corrected via the same midranks."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return float("nan")
    rx, ry = _midranks(x[ok]), _midranks(y[ok])
    sx, sy = rx.std(), ry.std()
    if sx < 1e-12 or sy < 1e-12:
        return float("nan")
    return float(((rx - rx.mean()) * (ry - ry.mean())).mean() / (sx * sy))


def brier(y: Sequence, p: Sequence) -> float:
    """Mean squared error of a probabilistic prediction. Absent from the sibling project entirely."""
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    ok = np.isfinite(y) & np.isfinite(p)
    return float(np.mean((p[ok] - y[ok]) ** 2)) if ok.sum() else float("nan")


def calibration(y: Sequence, p: Sequence) -> dict:
    """Calibration intercept and slope from a logistic recalibration of the logit of p.

    Perfect calibration is intercept 0, slope 1. Slope < 1 means over-confident. Discrimination without
    calibration is half a result, and the missing half is the half clinicians use.
    """
    y = np.asarray(y, float)
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    if len(y) < 10 or len(np.unique(y)) < 2:
        return {"intercept": float("nan"), "slope": float("nan"), "n": int(len(y))}
    X = np.column_stack([np.ones(len(y)), np.log(p / (1 - p))])
    b = logit_fit(X, y)
    return {"intercept": float(b[0]), "slope": float(b[1]), "n": int(len(y))}


def logit_fit(X: np.ndarray, y: np.ndarray, iters: int = 60, ridge: float = 1e-6) -> np.ndarray:
    """IRLS logistic regression with a small ridge. Lifted from the sibling project (icare_morph_replication)
    so that numbers are comparable across the two codebases; kept byte-comparable in behaviour on purpose."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(p * (1 - p), 1e-9, None)
        z = eta + (y - p) / w
        A = X.T @ (X * w[:, None]) + ridge * np.eye(X.shape[1])
        try:
            nb = np.linalg.solve(A, X.T @ (w * z))
        except np.linalg.LinAlgError:
            break
        if not np.all(np.isfinite(nb)) or np.max(np.abs(nb - b)) < 1e-8:
            b = nb if np.all(np.isfinite(nb)) else b
            break
        b = nb
    return b


def predict_proba(X: np.ndarray, b: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(np.asarray(X, float) @ b, -30, 30)))


def cluster_bootstrap_ci(stat_fn: Callable[[np.ndarray], float], subject: Sequence, rng,
                         reps: int = 1000, alpha: float = 0.05) -> tuple:
    """Percentile CI from resampling SUBJECTS with replacement.

    `stat_fn` receives an index array into the original rows and returns a scalar. Draws that produce a
    degenerate statistic (NaN — usually one outcome class absent) are dropped and counted; if more than half
    the draws are degenerate the CI is returned as NaN rather than as a narrow interval computed from the
    non-degenerate minority, which would be biased toward whichever resamples happened to be evaluable.
    """
    subject = np.asarray(subject)
    uniq = np.unique(subject)
    idx_by_subj = {u: np.flatnonzero(subject == u) for u in uniq}
    vals = []
    for _ in range(reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_subj[u] for u in drawn])
        v = stat_fn(idx)
        if np.isfinite(v):
            vals.append(v)
    n_ok = len(vals)
    if n_ok < reps // 2:
        return float("nan"), float("nan"), n_ok
    v = np.sort(np.asarray(vals, float))
    return (float(np.quantile(v, alpha / 2)), float(np.quantile(v, 1 - alpha / 2)), n_ok)


def permutation_null(stat_fn: Callable[[np.ndarray], float], y: Sequence, subject: Sequence, rng,
                     reps: int = 1000) -> dict:
    """Null distribution from permuting the outcome ACROSS SUBJECTS, keeping each subject's rows together.

    Permuting rows would break the within-subject dependence and produce a null that is too narrow, which
    makes everything look significant. `stat_fn(y_permuted)` returns the statistic under that relabelling.

    Returns the null mean and quantiles plus `null_centered`, a check on the machinery itself: for a
    discrimination statistic the permuted mean must sit at chance. If it does not, the harness is broken and
    any comparison against this null is uninterpretable — the caller must report INDETERMINATE, not a
    negative result (sibling error catalogue rule 31).
    """
    y = np.asarray(y, float)
    subject = np.asarray(subject)
    uniq = np.unique(subject)
    subj_y = np.array([y[subject == u][0] for u in uniq])
    pos = {u: np.flatnonzero(subject == u) for u in uniq}
    vals = []
    for _ in range(reps):
        perm = rng.permutation(subj_y)
        yp = np.empty_like(y)
        for u, val in zip(uniq, perm):
            yp[pos[u]] = val
        v = stat_fn(yp)
        if np.isfinite(v):
            vals.append(v)
    if not vals:
        return {"mean": float("nan"), "q025": float("nan"), "q975": float("nan"),
                "n": 0, "null_centered": False}
    v = np.sort(np.asarray(vals, float))
    return {"mean": float(v.mean()), "q025": float(np.quantile(v, 0.025)),
            "q975": float(np.quantile(v, 0.975)), "n": int(len(v)),
            "null_centered": bool(abs(v.mean() - 0.5) < 0.05)}
