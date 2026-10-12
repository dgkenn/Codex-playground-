"""Correlating a CHANGE against its own BASELINE — the coupling trap, and the three ways out.

WHY THIS MODULE EXISTS. A claim in this project's prior work reported that a pre-induction baseline
aperiodic exponent predicts the spectral change at loss of consciousness, **rho = -0.81, N = 2,647**. If
"change" is `value_after - value_before`, then `value_before` appears on both sides of the correlation and
**the null is not zero**. Simulated with no true relationship whatever:

    spread of after-values relative to before   expected rho(before, after - before)
    equal                                       -0.707     (analytic -1/sqrt(2))
    0.7x                                        -0.819     (analytic -0.819)
    1.4x                                        -0.581

**-0.819 under a pure null is what was reported as -0.81**, and 0.7x is exactly what an intervention that
compresses between-subject variability produces. Worse, the artefact runs the wrong way for the
hypothesis: a genuine POSITIVE relationship between before and after makes the observed
change-correlation LESS negative (true 0.2 -> -0.632; 0.4 -> -0.547). So a large negative number is
consistent with nothing being there.

This is Oldham's problem (Oldham 1962), rediscovered regularly as regression to the mean, mathematical
coupling, or the baseline-change fallacy. It is not a reason to abandon a claim — it is a reason to
compute a statistic whose null is zero and see whether the claim survives.

WHAT TO REPORT INSTEAD. `analyse` returns all four side by side so the coupled one can be shown with its
own null rather than hidden:

    coupled       rho(before, after - before)               null NOT zero -- see below
    oldham        rho((before + after)/2, after - before)   null NOT zero either, unless the variances
                                                            happen to match -- see the correction below
    on_value      rho(before, after)                        **null IS zero at every spread. This is the
                                                            one to report.**
    partial       partial rho(before, after) given a caller-supplied covariate; None when none is given

**A CORRECTION MADE TO THIS MODULE BEFORE IT SHIPPED, AND IT MATTERS.** The first draft recommended
Oldham's method as the fix and asserted its null was zero. It is not. Under the null,

    corr( (a+b)/2 , a-b )  =  (var(a) - var(b)) / (var(a) + var(b))

which is zero **only when the two variances are equal**. Verified empirically to three decimals: at
sd(after)/sd(before) = 0.6 the null is **-0.470**; at 1.6 it is **+0.438**. So Oldham trades one
variance-driven artefact for a smaller one, and in exactly the situation that motivated this module -- an
intervention that compresses between-subject variance -- it is still biased.

**`on_value`, plain `corr(before, after)`, is zero at every spread and is therefore the statistic to
report.** Oldham is kept because it answers a subtly different question (does the change depend on the
underlying level?) and because a reader may expect it, but it is now reported beside its own null too.

`expected_coupled_null` gives the analytic null for the coupled statistic at the observed spreads, so a
reader can see how much of the coupled number is arithmetic. **If the coupled value does not clear its own
null by a wide margin, there is nothing to report.**

Everything here is plain numpy and has no bearing on any candidate. It is a verifier utility.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np


def _rank(x: np.ndarray) -> np.ndarray:
    """Midranks, so Spearman handles ties the way the rest of this project's stats do."""
    order = np.argsort(x, kind="mergesort")
    r = np.empty(x.size, float)
    r[order] = np.arange(x.size, dtype=float)
    # average tied ranks
    i = 0
    xs = x[order]
    while i < x.size:
        j = i
        while j + 1 < x.size and xs[j + 1] == xs[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return r


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return float("nan")
    ra, rb = _rank(a[ok]), _rank(b[ok])
    sa, sb = ra.std(), rb.std()
    if sa < 1e-12 or sb < 1e-12:
        return float("nan")
    return float(((ra - ra.mean()) * (rb - rb.mean())).mean() / (sa * sb))


def expected_coupled_null(sd_before: float, sd_after: float, rho_true: float = 0.0) -> float:
    """Analytic value of `corr(before, after - before)` when the true before-after correlation is
    `rho_true`.

        corr(b, a - b) = (rho * sd_a - sd_b) / sqrt(sd_a^2 + sd_b^2 - 2 rho sd_a sd_b)

    At `rho_true = 0` and equal spreads this is -1/sqrt(2) = -0.7071. **That, not zero, is the number a
    coupled correlation has to beat.**
    """
    sa, sb = float(sd_after), float(sd_before)
    den = sa ** 2 + sb ** 2 - 2.0 * rho_true * sa * sb
    if den <= 0:
        return float("nan")
    return float((rho_true * sa - sb) / np.sqrt(den))


def expected_oldham_null(sd_before: float, sd_after: float) -> float:
    """Analytic value of `corr((a+b)/2, a-b)` when `a` and `b` are independent.

        (var(a) - var(b)) / (var(a) + var(b))

    Zero only at equal variances. Verified against simulation to three decimals across a 0.6-1.6 spread
    ratio in `tests/test_change_scores.py`.
    """
    va, vb = float(sd_after) ** 2, float(sd_before) ** 2
    if va + vb <= 0:
        return float("nan")
    return float((va - vb) / (va + vb))


def analyse(before: Sequence, after: Sequence,
            covariate: Optional[Sequence] = None) -> Dict[str, object]:
    """Every statistic a before/after claim should be reported with, and the coupled one's own null.

    `before` and `after` are paired per subject. Returns Spearman correlations (rank-based, so the
    analytic null below is an approximation for them — it is exact for Pearson, and the two agree closely
    for roughly linear data; `pearson_coupled` is returned so the comparison is available directly).
    """
    b = np.asarray(before, float)
    a = np.asarray(after, float)
    if b.shape != a.shape:
        raise ValueError(f"before and after must be paired: got {b.shape} and {a.shape}")
    ok = np.isfinite(b) & np.isfinite(a)
    b, a = b[ok], a[ok]
    n = b.size
    if n < 3:
        return {"n": int(n), "error": "fewer than 3 paired observations"}
    change = a - b
    mean_ba = (a + b) / 2.0

    sd_b, sd_a = float(b.std(ddof=1)), float(a.std(ddof=1))
    pear_coupled = (float(np.corrcoef(b, change)[0, 1])
                    if sd_b > 0 and change.std() > 0 else float("nan"))

    out = {
        "n": int(n),
        "sd_before": sd_b,
        "sd_after": sd_a,
        "coupled": _spearman(b, change),
        "pearson_coupled": pear_coupled,
        "expected_coupled_null": expected_coupled_null(sd_b, sd_a, 0.0),
        "oldham": _spearman(mean_ba, change),
        "expected_oldham_null": expected_oldham_null(sd_b, sd_a),
        "on_value": _spearman(b, a),
        "partial": None,
    }
    if covariate is not None:
        c = np.asarray(covariate, float)[ok]
        m = np.isfinite(c)
        if m.sum() >= 4:
            # partial Spearman of (before, after) given the covariate, via residual ranks
            rb, ra, rc = _rank(b[m]), _rank(a[m]), _rank(c[m])
            def resid(y, x):
                x1 = np.column_stack([np.ones(x.size), x])
                beta, *_ = np.linalg.lstsq(x1, y, rcond=None)
                return y - x1 @ beta
            out["partial"] = float(np.corrcoef(resid(rb, rc), resid(ra, rc))[0, 1])
    return out


def report(res: Dict[str, object]) -> list:
    """Human-readable lines, with the coupled statistic shown AGAINST ITS OWN NULL rather than zero."""
    if res.get("error"):
        return [f"   {res['error']}"]
    exp = res["expected_coupled_null"]
    coup = res["coupled"]
    excess = coup - exp if np.isfinite(coup) and np.isfinite(exp) else float("nan")
    lines = [
        f"   n = {res['n']}   sd(before) = {res['sd_before']:.4f}   sd(after) = {res['sd_after']:.4f}",
        "",
        f"   coupled   rho(before, after-before)      = {coup:+.4f}",
        f"             its NULL at these spreads      = {exp:+.4f}   <- not zero",
        f"             excess over the null           = {excess:+.4f}",
        "",
        f"   oldham    rho(mean(before,after), change) = {res['oldham']:+.4f}",
        f"             its NULL at these spreads       = {res['expected_oldham_null']:+.4f}"
        f"   <- zero only if the variances match",
        f"   on_value  rho(before, after)              = {res['on_value']:+.4f}"
        f"   <- NULL IS ZERO AT EVERY SPREAD",
    ]
    if res.get("partial") is not None:
        lines.append(f"   partial   rho(before, after | covariate) = {res['partial']:+.4f}")
    lines += [
        "",
        "   REPORT `on_value`. It is the only one of the three whose null is zero regardless of how the",
        "   spreads move. `coupled` and `oldham` are shown against their own nulls so a reader can see how",
        "   much of a headline correlation was arithmetic.",
    ]
    return lines
