#!/usr/bin/env python3
"""E44 -- how far does EYE STATE move the measures destined for the normative scale?

The registration is in `analysis/ds005385_extract.py`'s module docstring, committed before any feature
value from this deposit existed. This file implements it and changes nothing about it.

WHY IT MATTERS. `NORMAL_REFERENCE_COVARIATES.md` originally filed eyes-open-versus-closed under "known
unknowns". PMID 42395346 reports Cohen's d = -0.761 on the aperiodic exponent, which would make it the
largest uncontrolled term in a HEEDB-derived reference after vigilance -- and HEEDB does not record eye
state. On that citation alone the covariate was promoted out of the unknowns list. **E44 checks whether
that promotion was justified, on our own estimator, at n = 607 paired subjects.**

REGISTERED PRIMARY. Within-subject paired difference, eyes-closed minus eyes-open, at `acq-pre` in `ses-1`,
for `exponent_low` (1-20 Hz) and `lempel_ziv` -- the two measures E43's band decomposition selected.
Reported as Cohen's d_z with a subject-level bootstrap CI.

REGISTERED DIRECTION: none. PMID 42395346 reports the exponent RISING with eyes open, the opposite of the
naive "eyes closed = drowsier = steeper" intuition, and this project has been burned repeatedly by verdict
rules that did not enumerate the wrong-direction case. **The registered question is MAGNITUDE.**

REGISTERED DECISION RULE, three branches, the middle one existing so the rule cannot be satisfied by
whatever comes out:
  * |d_z| >= 0.5 for either measure -> FIRST-ORDER. Eye state must be resolved in-signal and frozen into
    the reference alongside the wake detector; the promotion was correct.
  * |d_z| < 0.2 for both            -> OVER-REACTION. The promotion was driven by one citation on one
    cohort and must be reverted IN WRITING, not quietly dropped.
  * anything between                -> report the number, change nothing, say it is between.

REGISTERED INCUMBENT: `whole_head_exponent`, the measure this project used before E43. If eye state moves
it MORE than `exponent_low`, that is a second independent reason to prefer the sub-band fit, unrelated to
EMG. If LESS, that is a cost of the E43 switch and must be reported as one.

REGISTERED PLACEBO: `acq-pre` vs `acq-post` within the SAME eye state -- same subject, session and montage,
separated by a two-hour cognitive battery. A real eye-state effect should exceed it. The gate is a
COMPARISON, never an absolute threshold, and if the primary's interval includes zero it prints NOT
INFORMATIVE rather than PASSED (rule 48).

REGISTERED ADDITION, from the smoke run and committed before any analysis: the peak-suppressed
`exponent_low_robust` and `whole_head_robust` are reported alongside the OLS columns. If the OLS contrast
is large and the robust contrast small, the effect was ALPHA and not the aperiodic slope -- the alpha peak
occupies a far larger share of a 1-20 Hz fit window than of a 1-45 Hz one.

    python -m bsde.experiments.e44_eye_state_effect
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

FEATURES = "/tmp/eeg_probe/ds005385_features.csv"
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e44_eye_state_effect.json")

PRIMARY = ("exponent_low", "lempel_ziv")
INCUMBENT = "whole_head_exponent"
EXTRA = ("exponent_low_robust", "whole_head_robust", "rel_alpha", "alpha_peak_hz",
         "exponent_high", "lrtc_alpha")
MIN_SUBJECTS = 100
REPS = 20000
SEED = 20260731
BIG, SMALL = 0.5, 0.2


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:                                                        # noqa: BLE001
        return None


def _paired(rows, feat, key_a, key_b):
    """Per-subject (a, b) for two conditions. Returns aligned arrays."""
    a, b = {}, {}
    for r in rows:
        v = _f(r.get(feat))
        if v is None:
            continue
        k = (r["session"], r["acq"], r["task"])
        if k == key_a:
            a.setdefault(r["subject"], []).append(v)
        elif k == key_b:
            b.setdefault(r["subject"], []).append(v)
    subs = sorted(set(a) & set(b))
    return (np.array([float(np.mean(a[s])) for s in subs]),
            np.array([float(np.mean(b[s])) for s in subs]), subs)


def _dz(x, y):
    """Cohen's d_z for paired samples: mean(difference) / SD(difference)."""
    d = x - y
    sd = float(np.std(d, ddof=1))
    return float(np.mean(d) / sd) if sd > 0 else float("nan")


def _boot(x, y, reps=REPS, seed=SEED):
    rng = np.random.default_rng(seed)
    n = x.size
    v = [_dz(x[i], y[i]) for i in (rng.integers(0, n, n) for _ in range(reps))]
    v = np.sort(np.array([z for z in v if math.isfinite(z)]))
    if v.size < reps // 2:
        return float("nan"), float("nan")
    return float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))


def main() -> int:
    with open(FEATURES) as fh:
        rows = list(csv.DictReader(fh))
    EC = ("1", "pre", "EyesClosed")
    EO = ("1", "pre", "EyesOpen")
    ECpost = ("1", "post", "EyesClosed")

    print("=" * 100)
    print("E44 -- how far does eye state move the measures destined for the normative scale?")
    print("=" * 100)
    res = {}
    order = list(PRIMARY) + [INCUMBENT] + list(EXTRA)
    print(f"   {'measure':22s} {'d_z (EC-EO)':>12s} {'95% CI':>20s} {'n':>5s}   {'placebo d_z':>12s}")
    print("   " + "-" * 82)
    n_used = 0
    for feat in order:
        x, y, subs = _paired(rows, feat, EC, EO)
        if x.size < MIN_SUBJECTS:
            print(f"   {feat:22s} insufficient paired subjects ({x.size})")
            res[feat] = {"verdict": "SKIPPED", "n": int(x.size)}
            continue
        n_used = max(n_used, x.size)
        dz = _dz(x, y)
        lo, hi = _boot(x, y)
        # PLACEBO: pre vs post within the SAME eye state
        px, py, _ps = _paired(rows, feat, EC, ECpost)
        pdz = _dz(px, py) if px.size >= MIN_SUBJECTS else float("nan")
        res[feat] = {"d_z": dz, "ci": [lo, hi], "n": int(x.size),
                     "placebo_d_z": pdz, "placebo_n": int(px.size)}
        print(f"   {feat:22s} {dz:+12.3f} [{lo:+8.3f},{hi:+8.3f}] {x.size:5d}   {pdz:+12.3f}")

    # ---- registered decision rule, evaluated on the PRIMARY pair only
    prim = [res[f] for f in PRIMARY if "d_z" in res[f]]
    if len(prim) < len(PRIMARY):
        verdict = "NOT EVALUABLE (a primary measure had too few paired subjects)"
    else:
        mags = [abs(p["d_z"]) for p in prim]
        spans_zero = any(not (math.isfinite(p["ci"][0]) and math.isfinite(p["ci"][1]))
                         or p["ci"][0] <= 0 <= p["ci"][1] for p in prim)
        if max(mags) >= BIG:
            verdict = ("FIRST-ORDER -- eye state must be resolved in-signal and frozen into the reference "
                       "alongside the wake detector. The promotion out of 'known unknowns' was correct.")
        elif all(m < SMALL for m in mags):
            verdict = ("OVER-REACTION -- both |d_z| < 0.2. The promotion rested on one citation on one "
                       "cohort and must be REVERTED IN WRITING in NORMAL_REFERENCE_COVARIATES.md.")
        else:
            verdict = (f"BETWEEN -- max |d_z| = {max(mags):.3f} sits between {SMALL} and {BIG}. "
                       "Report the number and change nothing.")
        # placebo branch: a comparison, and it cannot validate a null (rule 48)
        # PER MEASURE, not aggregated. The first version compared the BEST primary against the WORST
        # placebo and printed a global PASS -- which hid that lempel_ziv's own placebo (|d_z| 0.927)
        # EXCEEDS its own primary (0.477). A placebo is a comparison for the measure it belongs to; pooling
        # them lets a strong measure carry a weak one (rules 34, 37).
        pl = {}
        for f_ in PRIMARY:
            p_ = res[f_]
            ci = p_["ci"]
            if not (math.isfinite(ci[0]) and math.isfinite(ci[1])) or ci[0] <= 0 <= ci[1]:
                pl[f_] = "NOT INFORMATIVE (its own interval includes zero)"
            elif not math.isfinite(p_["placebo_d_z"]):
                pl[f_] = "NOT INFORMATIVE (placebo not evaluable)"
            elif abs(p_["d_z"]) > abs(p_["placebo_d_z"]):
                pl[f_] = (f"PASSED ({abs(p_['d_z']):.3f} > placebo {abs(p_['placebo_d_z']):.3f})")
            else:
                pl[f_] = (f"FAILED -- placebo {abs(p_['placebo_d_z']):.3f} matches or exceeds the primary "
                          f"{abs(p_['d_z']):.3f}; this measure's contrast is NOT specific to eye state")
    print("\n" + "-" * 100)
    print(f"VERDICT: {verdict}")
    for f_, v_ in (pl.items() if isinstance(pl, dict) else [("(all)", pl)]):
        print(f"PLACEBO [{f_}]: {v_}")

    inc = res.get(INCUMBENT, {})
    if "d_z" in inc and all("d_z" in res[f] for f in PRIMARY):
        el = abs(res["exponent_low"]["d_z"])
        wh = abs(inc["d_z"])
        print(f"\nINCUMBENT: |d_z| whole_head_exponent {wh:.3f} vs exponent_low {el:.3f} -> "
              + ("the broadband fit is MORE eye-state sensitive; a second reason to prefer the sub-band"
                 if wh > el else
                 "the sub-band is MORE eye-state sensitive; a COST of the E43 switch, reported as one"))
    if "exponent_low_robust" in res and "d_z" in res["exponent_low_robust"]:
        print(f"\nALPHA CHECK: exponent_low {res['exponent_low']['d_z']:+.3f} vs peak-suppressed "
              f"{res['exponent_low_robust']['d_z']:+.3f} -> "
              + ("most of the contrast SURVIVES peak suppression, so it is the aperiodic slope"
                 if abs(res["exponent_low_robust"]["d_z"]) > 0.6 * abs(res["exponent_low"]["d_z"]) else
                 "the contrast COLLAPSES under peak suppression, so it was largely the alpha peak"))

    os.makedirs(RESULTS, exist_ok=True)
    json.dump({"results": res, "verdict": verdict, "placebo": pl, "n": n_used,
               "reps": REPS, "seed": SEED}, open(OUT, "w"), indent=2, default=str)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
