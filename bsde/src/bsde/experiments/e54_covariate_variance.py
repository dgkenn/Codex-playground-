#!/usr/bin/env python3
"""E54 -- how much between-subject variance do age and sex explain, and what gain does that buy?

This is Q16's step-4 regression, the one `NORMAL_REFERENCE_COVARIATES.md` §8 and
`REFERENCE_AGAINST_ALL_THREE.md` §4(c) both call the step that kills or sizes the whole conditional-
reference idea for the price of one regression. It is run here on the OPEN cohorts because they are in
hand; the HEEDB version adds comorbidity and medication, which these deposits do not carry.

WHY IT MATTERS (`REFERENCE_AGAINST_ALL_THREE.md` §2). If part of a measure's between-subject variance is
covariate-predictable nuisance -- variance that cannot correlate with an ability because it is age -- then
it dilutes any correlation, and removing it raises the correlation without recruiting anyone. The gain has
a closed form: **r rises by 1 / sqrt(1 - R^2)**. So R^2 forecasts the Challenge B benefit before a single
new subject is recruited.

THE SHARPENING E45 MAKES POSSIBLE, AND IT WAS NOT IN THE ORIGINAL PLAN. Only the RELIABLE part of
between-subject variance can correlate with anything; the rest is measurement noise and is already lost.
E45 measured that reliable fraction directly as a five-year ICC. So the honest denominator for "how much
of the usable variance is nuisance" is not 1, it is the ICC:

    R2_raw       fraction of TOTAL between-subject variance explained by age and sex
    R2_reliable  = R2_raw / ICC, the fraction of the RELIABLE variance that is covariate-predictable
    gain         = 1 / sqrt(1 - R2_raw)      <- what REFERENCE_AGAINST_ALL_THREE registered

`R2_reliable` can exceed 1, and if it does that is informative rather than an error: it would mean age and
sex explain more variance than the measure reliably has, which can only happen if the ICC is an
underestimate -- and E45 registered that its five-year ICC IS a lower bound, because biological change is
confounded with measurement error over that interval. So R2_reliable > 1 is a consistency check on E45,
not a contradiction.

DESIGN. Healthy adults only, eyes-closed, one row per subject, pooled across cohorts with COHORT as a fixed
effect so a between-deposit level difference cannot be scored as an age effect. R^2 is the INCREMENT of
age + age^2 + sex over a cohort-only model -- not the total, which would be dominated by the batch effects
E48 measured at 5.0-5.6 in units of within-cohort spread.

THE CONDITION THAT MUST BE CHECKED BEFORE THE GAIN IS BELIEVED, and it CANNOT be checked here.
`REFERENCE_AGAINST_ALL_THREE.md` §2 states it: the gain holds only if the covariate variance is unrelated
to the outcome. If age predicts BCI ability too, residualising the predictor on age removes real signal
along with nuisance. **None of these cohorts carries a BCI label, so this experiment sizes the ceiling of
the gain and cannot confirm it is realisable.** Testing it needs a deposit with both, which is Q14
(Stieger 2021: 62 subjects, age, sex, handedness, 450 trials/session).

    python -m bsde.experiments.e54_covariate_variance
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e54_covariate_variance.json")

_p = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "analysis", "normative_multicohort.py"))
_spec = importlib.util.spec_from_file_location("nmc", _p)
nmc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nmc)

MEASURES = ("exponent_low", "exponent_low_robust", "whole_head_exponent", "exponent_high",
            "lempel_ziv", "lrtc_alpha", "rel_alpha", "alpha_peak_hz", "sef95")
# Five-year ICCs from E45 (ds005385, EyesClosed/pre, n = 207). Stated here so the arithmetic is auditable.
ICC = {"exponent_low": 0.756, "exponent_low_robust": 0.841, "whole_head_exponent": 0.748,
       "exponent_high": 0.757, "lempel_ziv": 0.193, "lrtc_alpha": 0.644, "rel_alpha": 0.851,
       "alpha_peak_hz": 0.629, "sef95": 0.746}
REPS = 4000
SEED = 20260731


def _r2_increment(rows, cohorts, values):
    """R^2 of age + age^2 + sex OVER a cohort-only model."""
    v = np.asarray(values, float)
    ok = np.isfinite(v)
    if ok.sum() < 60:
        return float("nan")
    rr = [r for r, k in zip(rows, ok) if k]
    y = v[ok]
    base = np.vstack([np.ones(len(rr))] +
                     [np.array([1.0 if r["_cohort"] == c else 0.0 for r in rr]) for c in cohorts[1:]]).T
    age = np.array([nmc._f(r["age"]) for r in rr], float)
    sex = np.array([1.0 if (r["sex"] or "").upper().startswith("M") else 0.0 for r in rr])
    full = np.hstack([base, np.vstack([age, age ** 2, sex]).T])

    def rss(X):
        c, *_ = np.linalg.lstsq(X, y, rcond=None)
        return float(((y - X @ c) ** 2).sum())
    r0, r1 = rss(base), rss(full)
    return float((r0 - r1) / r0) if r0 > 0 else float("nan")


def main() -> int:
    rows = nmc._load()
    adults = [r for r in rows if (nmc._f(r["age"]) or 0) >= nmc.ADULT_MIN_AGE]
    cohorts = [c for c in sorted({r["_cohort"] for r in adults})
               if sum(1 for r in adults if r["_cohort"] == c) >= nmc.MIN_PER_COHORT]
    adults = [r for r in adults if r["_cohort"] in cohorts]
    rng = np.random.default_rng(SEED)

    print("=" * 100)
    print("E54 -- Q16 step 4: covariate-explained variance and the Challenge B gain it forecasts")
    print("=" * 100)
    print(f"   {len(adults)} healthy adults across {len(cohorts)} cohorts: {cohorts}")
    print(f"\n   {'measure':22s} {'R2(age,sex)':>12s} {'95% CI':>18s} {'gain':>7s} {'ICC':>6s} "
          f"{'R2/ICC':>7s}")
    print("   " + "-" * 82)
    res = {}
    for m in MEASURES:
        vals = np.array([nmc._f(r.get(m)) for r in adults], float)
        pt = _r2_increment(adults, cohorts, vals)
        if not math.isfinite(pt):
            print(f"   {m:22s} not evaluable")
            continue
        d = []
        for _ in range(REPS):
            i = rng.integers(0, len(adults), len(adults))
            sub = [adults[j] for j in i]
            v = _r2_increment(sub, cohorts, vals[i])
            if math.isfinite(v):
                d.append(v)
        d = np.sort(np.array(d))
        lo, hi = (float(np.quantile(d, .025)), float(np.quantile(d, .975))) if d.size else (float("nan"),) * 2
        gain = 1.0 / math.sqrt(1.0 - pt) if pt < 1 else float("inf")
        icc = ICC.get(m, float("nan"))
        rel = pt / icc if icc and math.isfinite(icc) and icc > 0 else float("nan")
        res[m] = {"r2": pt, "ci": [lo, hi], "gain": gain, "icc": icc, "r2_over_icc": rel,
                  "n": int(np.isfinite(vals).sum())}
        print(f"   {m:22s} {pt:12.4f} [{lo:7.4f},{hi:7.4f}] {gain:7.3f} {icc:6.3f} {rel:7.3f}")

    best = max((v["r2"] for v in res.values() if math.isfinite(v["r2"])), default=float("nan"))
    print("\n" + "-" * 100)
    if not math.isfinite(best):
        verdict = "NOT EVALUABLE"
    elif best < 0.02:
        verdict = ("THE IDEA IS DEAD FOR THESE MEASURES -- age and sex explain under 2 % of between-subject "
                   "variance, so a conditional reference is no better than a pooled one and the gain is "
                   "under 1.01. This is the outcome NORMAL_REFERENCE_COVARIATES §8 said to hope for early.")
    elif best < 0.10:
        verdict = (f"MARGINAL -- best R^2 = {best:.4f}, gain {1/math.sqrt(1-best):.3f}. Real but small; a "
                   "conditional reference buys little over a pooled one on age and sex ALONE, and the "
                   "HEEDB-only covariates (comorbidity, medication) would have to carry the rest.")
    else:
        verdict = (f"WORTH BUILDING -- best R^2 = {best:.4f}, gain {1/math.sqrt(1-best):.3f} before "
                   "comorbidity and medication are added.")
    print(f"VERDICT: {verdict}")
    print("\nUNTESTABLE HERE (registered): the gain is real only if the covariate variance is unrelated to")
    print("the outcome. No cohort here carries a BCI label, so this sizes the CEILING of the gain and")
    print("cannot confirm it is realisable. That needs Q14 (Stieger 2021).")
    os.makedirs(RESULTS, exist_ok=True)
    json.dump({"n_adults": len(adults), "cohorts": cohorts, "results": res, "verdict": verdict,
               "reps": REPS, "seed": SEED}, open(OUT, "w"), indent=2, default=str)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
