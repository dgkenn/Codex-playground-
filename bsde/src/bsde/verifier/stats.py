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
    """Null distribution from permuting the outcome, using the scheme the design actually calls for.

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
    pos = {u: np.flatnonzero(subject == u) for u in uniq}

    # WITHIN-SUBJECT vs BETWEEN-SUBJECT designs need different nulls, and using the wrong one does not
    # produce a slightly-off null -- it produces no null at all, or a badly wrong one.
    #
    # The bug this replaces: the old code took ONE label per subject (`y[subject == u][0]`) and assigned it
    # to every row of that subject. On the Sleep-EDF wake-vs-N3 cohort each subject contributes exactly two
    # rows, and because `@N3` sorts before `@W` the first row of all 145 subjects was N3 -- so the
    # per-subject label vector was the constant 1, every "permutation" of it was still all-ones, every
    # permuted AUC was NaN for want of a negative class, and the null came back with n_perm = 0. The
    # machinery gate then correctly refused to issue a verdict (error-catalogue rule 31), which is how this
    # was found rather than silently believed.
    #
    # So: if any subject carries more than one distinct label, this is a within-subject (paired) design and
    # the labels are shuffled WITHIN each subject, which is the null that asks "is the direction consistent
    # inside subjects, or could this arise from arbitrary relabelling of each subject's own conditions?".
    # Otherwise there is one label per subject and whole subjects are permuted, which keeps each subject's
    # rows together and preserves the between-subject dependence.
    varying = [u for u in uniq if len(np.unique(y[pos[u]][np.isfinite(y[pos[u]])])) > 1]
    within_subject = len(varying) > 0

    vals = []
    for _ in range(reps):
        yp = y.copy()
        if within_subject:
            for u in uniq:
                idx = pos[u]
                if idx.size > 1:
                    yp[idx] = rng.permutation(y[idx])
        else:
            subj_y = np.array([y[pos[u]][0] for u in uniq])
            perm = rng.permutation(subj_y)
            for u, val in zip(uniq, perm):
                yp[pos[u]] = val
        v = stat_fn(yp)
        if np.isfinite(v):
            vals.append(v)
    if not vals:
        return {"mean": float("nan"), "q025": float("nan"), "q975": float("nan"),
                "n": 0, "scheme": "within_subject" if within_subject else "between_subject",
                "null_centered": False}
    v = np.sort(np.asarray(vals, float))
    return {"mean": float(v.mean()), "q025": float(np.quantile(v, 0.025)),
            "q975": float(np.quantile(v, 0.975)), "n": int(len(v)),
            "scheme": "within_subject" if within_subject else "between_subject",
            "null_centered": bool(abs(v.mean() - 0.5) < 0.05)}

def cv_predict_proba(x: Sequence, y: Sequence, subject: Sequence, rng, folds: int = 5) -> np.ndarray:
    """OUT-OF-FOLD probabilities from a univariate logistic on `x`, with SUBJECT-level folds.

    Why out-of-fold and why subject-level. In-sample calibration is meaningless -- a logistic fit on the
    same rows it is scored on is calibrated by construction, so reporting its intercept and slope would
    always look perfect and would say nothing. And folds must split on subject, because a subject
    contributing rows to both train and test leaks that subject's level, which for a within-subject contrast
    is most of the signal.

    Returns NaN for any row whose fold could not be fitted (a fold with one outcome class). Those rows are
    excluded downstream rather than imputed.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    subject = np.asarray(subject)
    out = np.full(len(x), np.nan)
    uniq = np.unique(subject)
    if len(uniq) < folds:
        folds = max(2, len(uniq))
    order = rng.permutation(len(uniq))
    assign = {uniq[order[i]]: i % folds for i in range(len(uniq))}
    fold_of = np.array([assign[s] for s in subject])
    for k in range(folds):
        te = fold_of == k
        tr = ~te & np.isfinite(x) & np.isfinite(y)
        if te.sum() == 0 or tr.sum() < 8 or len(np.unique(y[tr])) < 2:
            continue
        X = np.column_stack([np.ones(int(tr.sum())), x[tr]])
        b = logit_fit(X, y[tr])
        m = te & np.isfinite(x)
        out[m] = predict_proba(np.column_stack([np.ones(int(m.sum())), x[m]]), b)
    return out


def within_subject_auc(y: Sequence, score: Sequence, subject: Sequence, predicted: str,
                       min_per_class: int = 1) -> float:
    """Mean over subjects of that subject's own directional AUC. NaN if no subject is evaluable.

    WHY THIS AND NOT THE POOLED AUC. E14 measured an intraclass correlation above 0.9 for these candidates
    across windows of the same person, which means a pooled AUC over rows is mostly answering "are these two
    people different?" rather than "did this person change?". A design whose contrast is a state change
    WITHIN a patient has to be scored within the patient; pooling silently swaps the question.

    Each subject contributes ONE number regardless of how many windows they supply, so a patient with forty
    windows does not outvote a patient with four. Subjects lacking either class are skipped, which is why the
    caller must report how many were evaluable -- the mean is over those, and if that set is selected on
    something outcome-related the statistic inherits it (rule 14).

    Deliberately unweighted: weighting by window count would reintroduce exactly the imbalance the
    per-subject reduction removes.
    """
    y = np.asarray(y, float)
    score = np.asarray(score, float)
    subject = np.asarray(subject)
    vals = []
    for u in np.unique(subject):
        m = subject == u
        ok = m & np.isfinite(score)
        yy, ss = y[ok], score[ok]
        if (yy == 1).sum() < min_per_class or (yy == 0).sum() < min_per_class:
            continue
        a = directional_auc(yy, ss, predicted)
        if np.isfinite(a):
            vals.append(a)
    return float(np.mean(vals)) if vals else float("nan")


def n_evaluable_subjects(y: Sequence, score: Sequence, subject: Sequence,
                         min_per_class: int = 1) -> int:
    """How many subjects `within_subject_auc` actually averaged over. Reported, never assumed."""
    y = np.asarray(y, float)
    score = np.asarray(score, float)
    subject = np.asarray(subject)
    n = 0
    for u in np.unique(subject):
        ok = (subject == u) & np.isfinite(score)
        yy = y[ok]
        if (yy == 1).sum() >= min_per_class and (yy == 0).sum() >= min_per_class:
            n += 1
    return n


def oob_auc_increment(Xa: np.ndarray, Xb: np.ndarray, y: Sequence, subject: Sequence, rng,
                      reps: int = 400, min_oob_subjects: int = 5,
                      alpha: float = 0.05, return_diffs: bool = False) -> tuple:
    """Out-of-bag bootstrap for the AUC increment of model B over model A, clustered on SUBJECT.

    Each rep draws SUBJECTS with replacement, fits both models on the drawn subjects' rows, and evaluates
    both on the rows of the subjects NOT drawn. The returned interval is over those differences.

    WHY THIS SHAPE, and it is error-catalogue rule 9 restated. Refitting on a resample and evaluating on the
    same resample puts a subject in train and test and inflates the AUC. Bootstrapping FIXED out-of-fold
    predictions ignores refit variance and gives an interval that is too narrow. Both were used in the
    sibling project and both were wrong; this is the corrected form, adapted from
    `analysis/icare_morph_replication.py` with the resampling unit changed from the row to the subject,
    because here a subject contributes many windows and row resampling would leak that subject's level
    across the train/test split.

    `Xa` and `Xb` must already include an intercept column. Returns (mean, lo, hi, n_reps_used); a run with
    fewer than 30 usable reps returns NaNs rather than an interval computed from a handful of draws.
    """
    # THE INTERCEPT IS A REQUIREMENT AND IT IS NOW ENFORCED, not documented. E99 passed a bare feature
    # column, `logit_fit` fitted a through-the-origin logistic, and the increment came out at
    # -0.0320 [-0.0544, -0.0111] -- reported as HURTS -- where the same call WITH the intercept gives
    # +0.0168 [+0.0049, +0.0269]. A docstring sentence did not prevent that; a raise does.
    for _nm, _X in (("Xa", Xa), ("Xb", Xb)):
        _c = np.asarray(_X, float)[:, 0]
        if _c.size and (not np.allclose(_c, _c[0]) or _c[0] == 0):
            raise ValueError(
                f"{_nm}'s first column is not a constant non-zero intercept. `oob_auc_increment` fits an "
                "IRLS logistic with no intercept of its own, so a design without one is fitted through "
                "the origin and its AUC increment can change SIGN. Prepend np.ones(len(y)).")
    y = np.asarray(y, float)
    subject = np.asarray(subject)
    uniq = np.unique(subject)
    idx_by_subj = {u: np.flatnonzero(subject == u) for u in uniq}
    diffs = []
    for _ in range(reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        drawn_set = set(drawn.tolist())
        oob_subj = [u for u in uniq if u not in drawn_set]
        if len(oob_subj) < min_oob_subjects:
            continue
        tr = np.concatenate([idx_by_subj[u] for u in drawn])
        te = np.concatenate([idx_by_subj[u] for u in oob_subj])
        if len(np.unique(y[tr])) < 2 or len(np.unique(y[te])) < 2:
            continue
        try:
            ba = logit_fit(Xa[tr], y[tr])
            bb = logit_fit(Xb[tr], y[tr])
            aa = auc(y[te], predict_proba(Xa[te], ba))
            ab = auc(y[te], predict_proba(Xb[te], bb))
        except Exception:                                     # noqa: BLE001
            continue
        if np.isfinite(aa) and np.isfinite(ab):
            diffs.append(ab - aa)
    if len(diffs) < 30:
        nan = float("nan")
        return (nan, nan, nan, len(diffs), np.asarray(diffs, float)) if return_diffs else \
               (nan, nan, nan, len(diffs))
    d = np.asarray(diffs, float)
    res = (float(d.mean()), float(np.quantile(d, alpha / 2)), float(np.quantile(d, 1 - alpha / 2)),
           len(d))
    return res + (d,) if return_diffs else res


def within_subject_spearman(x: Sequence, z: Sequence, subject: Sequence,
                            min_points: int = 4, min_distinct: int = 3) -> float:
    """Mean over subjects of that subject's own rank correlation between `x` and `z`.

    The continuous-axis sibling of `within_subject_auc`, and it exists for the same reason: with an ICC
    above 0.9 across windows of one person, a pooled correlation mostly answers "do these two people
    differ?" rather than "did this person's measure follow their own dose?".

    `min_distinct` is not decoration. A patient held at one steady concentration for the whole case has no
    within-subject dose variation, and their rank correlation over ties is either undefined or driven by
    numerical noise in the ranking — including them would dilute the mean toward zero with subjects who
    could not have contributed. Requiring at least three distinct values of `z` states that exclusion rather
    than letting a tie-handling convention decide it silently, and the caller must report how many subjects
    survived it (rule 14).
    """
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    subject = np.asarray(subject)
    vals = []
    for u in np.unique(subject):
        m = (subject == u) & np.isfinite(x) & np.isfinite(z)
        if m.sum() < min_points or np.unique(z[m]).size < min_distinct:
            continue
        r = spearman(x[m], z[m])
        if np.isfinite(r):
            vals.append(r)
    return float(np.mean(vals)) if vals else float("nan")


def n_evaluable_spearman(x: Sequence, z: Sequence, subject: Sequence,
                         min_points: int = 4, min_distinct: int = 3) -> int:
    """How many subjects `within_subject_spearman` averaged over. Reported, never assumed."""
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    subject = np.asarray(subject)
    n = 0
    for u in np.unique(subject):
        m = (subject == u) & np.isfinite(x) & np.isfinite(z)
        if m.sum() >= min_points and np.unique(z[m]).size >= min_distinct:
            n += 1
    return n


def ridge_fit(X: np.ndarray, y: np.ndarray, lam: float = 1.0) -> np.ndarray:
    """Ridge coefficients for a design that ALREADY carries an intercept column in position 0.

    The intercept is not penalised. Standardisation is the caller's job and must be done on TRAINING rows
    only — standardising before the split leaks the test fold's scale into the fit.
    """
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    p = X.shape[1]
    P = np.eye(p) * float(lam)
    P[0, 0] = 0.0
    return np.linalg.solve(X.T @ X + P, X.T @ y)


def _standardise(Xtr: np.ndarray, Xte: np.ndarray):
    """Centre/scale by TRAINING statistics, prepend an intercept, and NaN-fill with the training mean.

    Constant training columns get scale 1 so they collapse to zero rather than exploding.
    """
    mu = np.nanmean(Xtr, axis=0)
    mu = np.where(np.isfinite(mu), mu, 0.0)
    sd = np.nanstd(Xtr, axis=0)
    sd = np.where(np.isfinite(sd) & (sd > 1e-12), sd, 1.0)

    def prep(X):
        Z = np.where(np.isfinite(X), X, mu)
        Z = (Z - mu) / sd
        return np.column_stack([np.ones(len(Z)), Z])

    return prep(Xtr), prep(Xte)


def grouped_cv_predict(X: np.ndarray, y: Sequence, subject: Sequence, rng, folds: int = 5,
                       lam: float = 1.0) -> np.ndarray:
    """Out-of-fold ridge predictions with SUBJECTS held out whole.

    Windows within one case are highly correlated, so ungrouped folds would put the same case on both sides
    and inflate every fidelity number computed from the result.
    """
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    subject = np.asarray(subject)
    uniq = np.unique(subject)
    order = rng.permutation(len(uniq))
    assign = {uniq[order[i]]: i % folds for i in range(len(uniq))}
    fold_of = np.array([assign[s] for s in subject])
    pred = np.full(len(y), np.nan)
    for k in range(folds):
        te = np.flatnonzero(fold_of == k)
        tr = np.flatnonzero(fold_of != k)
        if te.size == 0 or tr.size < X.shape[1] + 2:
            continue
        Ztr, Zte = _standardise(X[tr], X[te])
        pred[te] = Zte @ ridge_fit(Ztr, y[tr], lam)
    return pred


def screen_candidates(cols, min_finite=20, min_distinct=3):
    """Split a candidate dict into (usable, dropped_with_reason) BEFORE any statistic is computed.

    WHY THIS IS SHARED RATHER THAN FIXED PER FILE. The same defect has now appeared three times. E157
    scored an all-NaN `wpli_alpha` at p = 0.0000 because `nanmean(null >= nan)` counts every comparison
    False. E161 fixed it locally. E164 then scored a CONSTANT column -- `age`, whose within-subject
    change is identically zero in a change design -- at p = 0.0000 by the same mechanism, because the
    local fix was never carried across.

    A column with almost no data, or with no variation, cannot carry an association and must be dropped
    and NAMED rather than allowed to reach a p-value. Callers report `dropped` so the exclusion is visible
    in the output instead of being silent (rule 14).
    """
    usable, dropped = {}, {}
    for k, v in cols.items():
        a = np.asarray(v, float)
        fin = np.isfinite(a)
        if fin.sum() < min_finite:
            dropped[k] = f"only {int(fin.sum())} finite values"
            continue
        if len(np.unique(a[fin])) < min_distinct:
            dropped[k] = f"only {len(np.unique(a[fin]))} distinct values"
            continue
        usable[k] = a
    return usable, dropped


def cluster_permute(col, subject, rng):
    """Permute a column ACROSS clusters, whole blocks at a time.

    A row-level shuffle destroys the cluster structure along with the association and therefore produces a
    null the real data could never have drawn from. Here each subject's block of values is replaced by
    another subject's block; unequal block lengths are handled by resampling the donor's values, which
    preserves the donor's within-subject distribution. Rule 69 is about counting clusters correctly, and
    this is the same principle applied to the permutation rather than to the resample.
    """
    col = np.asarray(col, float)
    subject = np.asarray(subject)
    uniq = np.unique(subject)
    donors = rng.permutation(uniq)
    out = np.empty_like(col)
    idx = {u: np.flatnonzero(subject == u) for u in uniq}
    for u, d in zip(uniq, donors):
        iu, idn = idx[u], idx[d]
        out[iu] = col[idn] if len(idn) == len(iu) else rng.choice(col[idn], size=len(iu), replace=True)
    return out


def permutation_increment(Xa: np.ndarray, Xb: np.ndarray, y: Sequence, subject: Sequence, rng,
                          stat=None, folds: int = 5, reps: int = 500, lam: float = 1.0,
                          n_extra: int = 1) -> tuple:
    """Cross-fitted increment of model B over model A, tested against a CLUSTER-PERMUTATION null.

    WHY THIS EXISTS. `oob_regression_increment` is an estimator whose bootstrap tail fraction was being
    used as a test, and E146 measured what that costs: at n = 60 subjects and a partial correlation of
    0.35 it detected in **0 %** of draws where an ordinary partial-correlation test detected in 88 %. The
    bootstrap spread reflects resample-to-resample variability rather than the sampling distribution of
    the increment, so its tail is conservative to the point of blindness. Its point estimate is not in
    question and is still worth reporting; its p-value is.

    This computes the increment ONCE on subject-grouped out-of-fold predictions, then builds the null by
    permuting the added column(s) across clusters and refitting. The null is therefore generated by the
    same pipeline as the observed value, which is what makes the p-value calibrated rather than merely
    conservative.

    `stat(y_true, y_pred) -> float` defaults to -Spearman, so LOWER IS BETTER and a NEGATIVE increment
    means B helps -- the same convention as `oob_regression_increment`, kept deliberately so the two are
    not read with opposite signs. `n_extra` is how many trailing columns of Xb are the addition.

    Returns `(observed, p_one_sided, null_mean, n_null)` where `p` is the fraction of null increments at
    or below the observed one.
    """
    if stat is None:
        def stat(t, p):
            r = spearman(list(np.asarray(t, float)), list(np.asarray(p, float)))
            return -r if np.isfinite(r) else float("nan")
    Xa = np.asarray(Xa, float)
    Xb = np.asarray(Xb, float)
    y = np.asarray(y, float)
    subject = np.asarray(subject)

    # The fold assignment is drawn ONCE and reused for the observed increment and every permutation. If it
    # were redrawn, the null would carry fold-assignment noise the observed value does not, which both
    # slows the test down and widens the null for a reason that has nothing to do with the hypothesis.
    fold_rng = np.random.default_rng(int(rng.integers(0, 2 ** 31 - 1)))
    uniq_s = np.unique(subject)
    order = fold_rng.permutation(len(uniq_s))
    assign = {uniq_s[order[i]]: i % folds for i in range(len(uniq_s))}
    fold_of = np.array([assign[s] for s in subject])

    def _cv(X):
        pred = np.full(len(y), np.nan)
        for k in range(folds):
            te = np.flatnonzero(fold_of == k)
            tr = np.flatnonzero(fold_of != k)
            if te.size == 0 or tr.size < X.shape[1] + 2:
                continue
            Ztr, Zte = _standardise(X[tr], X[te])
            pred[te] = Zte @ ridge_fit(Ztr, y[tr], lam)
        return pred

    pa = _cv(Xa)

    def _inc(Xb_):
        pb = _cv(Xb_)
        ok = np.isfinite(pa) & np.isfinite(pb)
        if ok.sum() < 10:
            return float("nan")
        return stat(y[ok], pb[ok]) - stat(y[ok], pa[ok])

    obs = _inc(Xb)
    if not np.isfinite(obs):
        return float("nan"), float("nan"), float("nan"), 0
    nulls = []
    for _ in range(reps):
        Xp = Xb.copy()
        for j in range(Xb.shape[1] - n_extra, Xb.shape[1]):
            Xp[:, j] = cluster_permute(Xb[:, j], subject, rng)
        v = _inc(Xp)
        if np.isfinite(v):
            nulls.append(v)
    if len(nulls) < 30:
        return obs, float("nan"), float("nan"), len(nulls)
    n = np.asarray(nulls, float)
    return obs, float((n <= obs).mean()), float(n.mean()), len(n)


def oob_regression_increment(Xa: np.ndarray, Xb: np.ndarray, y: Sequence, subject: Sequence, rng,
                             stat=None, reps: int = 400, min_oob_subjects: int = 5,
                             lam: float = 1.0, alpha: float = 0.05,
                             return_diffs: bool = False) -> tuple:
    """Out-of-bag bootstrap for the change in a REGRESSION error statistic from model A to model B.

    The regression twin of `oob_auc_increment`, and it exists for the same reason (rule 9): bootstrapping
    fixed out-of-fold predictions ignores refit variance and gives an interval that is too narrow, while
    refitting and evaluating on the same resample puts a subject in train and test. Each rep fits both
    models on the drawn subjects and scores both on the subjects NOT drawn.

    `stat(y_true, y_pred) -> float` defaults to median absolute error. The returned difference is
    **B minus A**, so for an error statistic a NEGATIVE value means B is BETTER. That sign convention is
    the opposite of `oob_auc_increment`'s and is stated here because reading it backwards would invert a
    verdict.

    `alpha` widens the returned interval for a multiplicity correction: passing 0.05/K gives the
    Bonferroni-adjusted interval for K simultaneous comparisons. The default reproduces the previous
    hard-coded 2.5/97.5 percentiles exactly, so no existing caller changes.

    `return_diffs` appends the raw out-of-bag difference array as a fifth element. It exists because an
    extreme quantile of a bootstrap distribution is unresolvable at the rep counts this project uses --
    E143 asked for the 0.078th percentile of 400 draws, which is the minimum -- and a one-sided tail
    FRACTION is estimable where that quantile is not. Callers that do not pass it are unaffected.
    """
    if stat is None:
        def stat(t, p):
            return float(np.median(np.abs(np.asarray(t, float) - np.asarray(p, float))))
    Xa = np.asarray(Xa, float)
    Xb = np.asarray(Xb, float)
    y = np.asarray(y, float)
    subject = np.asarray(subject)
    uniq = np.unique(subject)
    idx_by_subj = {u: np.flatnonzero(subject == u) for u in uniq}
    diffs = []
    for _ in range(reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        drawn_set = set(drawn.tolist())
        oob_subj = [u for u in uniq if u not in drawn_set]
        if len(oob_subj) < min_oob_subjects:
            continue
        tr = np.concatenate([idx_by_subj[u] for u in drawn])
        te = np.concatenate([idx_by_subj[u] for u in oob_subj])
        try:
            Atr, Ate = _standardise(Xa[tr], Xa[te])
            Btr, Bte = _standardise(Xb[tr], Xb[te])
            ea = stat(y[te], Ate @ ridge_fit(Atr, y[tr], lam))
            eb = stat(y[te], Bte @ ridge_fit(Btr, y[tr], lam))
        except Exception:                                     # noqa: BLE001
            continue
        if np.isfinite(ea) and np.isfinite(eb):
            diffs.append(eb - ea)
    if len(diffs) < 30:
        nan = float("nan")
        return (nan, nan, nan, len(diffs), np.asarray(diffs, float)) if return_diffs else \
               (nan, nan, nan, len(diffs))
    d = np.asarray(diffs, float)
    res = (float(d.mean()), float(np.quantile(d, alpha / 2)), float(np.quantile(d, 1 - alpha / 2)),
           len(d))
    return res + (d,) if return_diffs else res
