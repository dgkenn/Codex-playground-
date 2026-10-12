#!/usr/bin/env python3
"""E45 -- five-year test-retest stability of each measure, on our own estimator.

Registered in `analysis/ds005385_extract.py`'s docstring before any feature value from this deposit
existed. This file implements it and changes nothing about it.

REGISTERED PRIMARY. ICC(2,1) between `ses-1` and `ses-2`, matched on task and acq, for `exponent_low`,
`lempel_ziv`, `whole_head_exponent` and `lrtc_alpha` (E42's refined Challenge B marker, which has never had
a reliability estimate of any kind).

REGISTERED PREDICTION. `exponent_low` ICC in [0.5, 0.8]; `lrtc_alpha` LOWER than `exponent_low`, because
DFA over a 184 s window has fewer effectively independent scales than a spectral fit does.

REGISTERED STATEMENT OF WHAT THIS CANNOT SHOW, and it must survive into any write-up. E38 measured a
LABEL's reliability and found it capped Challenge B at rho ~ 0.54; nobody has measured the PREDICTOR's.
sqrt(ICC) is the ceiling on any trait correlation a measure can support. **But a five-year interval is a
LOWER BOUND on measurement reliability, not an estimate of it** -- real biological change over five years
is confounded with measurement error and cannot be separated here. So a high ICC is informative and a low
one is ambiguous, and reporting sqrt(ICC) as "the reliability" would overstate what the design supports.

AN EXTERNAL CHECK THAT COMES FREE. PMID 42395346 reports a five-year ICC of **0.668** for the aperiodic
exponent on publicly available adult data with a five-year follow-up -- which is almost certainly this
deposit, though the paper is not yet in PMC and the identification is inferred rather than verified. If our
`whole_head_exponent` lands near 0.668 that is an independent estimator agreeing with a published one on
the same data; if it lands far away, one of the two pipelines is doing something the other is not. Either
way it is more informative than our number alone, and it is stated BEFORE the run.

POOL. Only **208 of 608** subjects have a second session, so the maximum is ~207 paired and the pool is
COMPLETE -- it does not grow with further extraction.

    python -m bsde.experiments.e45_five_year_icc
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
OUT = os.path.join(RESULTS, "e45_five_year_icc.json")

PRIMARY = ("exponent_low", "lempel_ziv", "whole_head_exponent", "lrtc_alpha")
EXTRA = ("exponent_high", "exponent_low_robust", "rel_alpha", "alpha_peak_hz", "sef95", "dfa_exponent")
PUBLISHED_EXPONENT_ICC = 0.668          # PMID 42395346, stated before the run
TASK, ACQ = "EyesClosed", "pre"
MIN_SUBJECTS = 50
REPS = 20000
SEED = 20260731


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:                                                        # noqa: BLE001
        return None


def icc21(x, y):
    """ICC(2,1): two-way random effects, absolute agreement, single measurement.

    Shrout & Fleiss (1979). k = 2 sessions, n subjects. Absolute agreement rather than consistency,
    because a systematic five-year drift IS a threat to using one recording as a reference point -- a
    consistency ICC would forgive exactly the shift the reference cannot tolerate.
    """
    m = np.vstack([x, y]).T
    n, k = m.shape
    if n < 3:
        return float("nan")
    gm = m.mean()
    ms_r = k * ((m.mean(axis=1) - gm) ** 2).sum() / (n - 1)
    ms_c = n * ((m.mean(axis=0) - gm) ** 2).sum() / (k - 1)
    resid = m - m.mean(axis=1, keepdims=True) - m.mean(axis=0, keepdims=True) + gm
    ms_e = (resid ** 2).sum() / ((n - 1) * (k - 1))
    denom = ms_r + (k - 1) * ms_e + k * (ms_c - ms_e) / n
    return float((ms_r - ms_e) / denom) if denom != 0 else float("nan")


def _paired(rows, feat):
    a, b = {}, {}
    for r in rows:
        if r["task"] != TASK or r["acq"] != ACQ:
            continue
        v = _f(r.get(feat))
        if v is None:
            continue
        (a if r["session"] == "1" else b if r["session"] == "2" else {}).setdefault(
            r["subject"], []).append(v)
    subs = sorted(set(a) & set(b))
    return (np.array([float(np.mean(a[s])) for s in subs]),
            np.array([float(np.mean(b[s])) for s in subs]), subs)


def main() -> int:
    with open(FEATURES) as fh:
        rows = list(csv.DictReader(fh))
    rng = np.random.default_rng(SEED)

    print("=" * 100)
    print(f"E45 -- five-year ICC(2,1), {TASK}/{ACQ}, ses-1 vs ses-2")
    print("=" * 100)
    res = {}
    print(f"   {'measure':22s} {'ICC(2,1)':>9s} {'95% CI':>20s} {'sqrt(ICC)':>10s} {'n':>5s}")
    print("   " + "-" * 72)
    for feat in list(PRIMARY) + list(EXTRA):
        x, y, subs = _paired(rows, feat)
        if x.size < MIN_SUBJECTS:
            print(f"   {feat:22s} insufficient paired subjects ({x.size})")
            res[feat] = {"verdict": "SKIPPED", "n": int(x.size)}
            continue
        pt = icc21(x, y)
        draws = []
        for _ in range(REPS):
            i = rng.integers(0, x.size, x.size)
            v = icc21(x[i], y[i])
            if math.isfinite(v):
                draws.append(v)
        d = np.sort(np.array(draws))
        lo, hi = (float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))) if d.size else (float("nan"),) * 2
        res[feat] = {"icc": pt, "ci": [lo, hi], "sqrt_icc": math.sqrt(pt) if pt > 0 else float("nan"),
                     "n": int(x.size)}
        sq = math.sqrt(pt) if pt > 0 else float("nan")
        print(f"   {feat:22s} {pt:9.3f} [{lo:+8.3f},{hi:+8.3f}] {sq:10.3f} {x.size:5d}")

    print("\n" + "-" * 100)
    # registered prediction 1: exponent_low in [0.5, 0.8]
    el = res.get("exponent_low", {}).get("icc", float("nan"))
    p1 = ("HELD" if 0.5 <= el <= 0.8 else
          f"MISSED -- predicted [0.5, 0.8], observed {el:.3f}") if math.isfinite(el) else "NOT EVALUABLE"
    # registered prediction 2: lrtc_alpha LOWER than exponent_low
    lr = res.get("lrtc_alpha", {}).get("icc", float("nan"))
    if math.isfinite(el) and math.isfinite(lr):
        p2 = ("HELD" if lr < el else
              f"REFUTED IN THE OPPOSITE DIRECTION -- lrtc_alpha {lr:.3f} is HIGHER than exponent_low {el:.3f}")
    else:
        p2 = "NOT EVALUABLE"
    print(f"REGISTERED PREDICTION 1 (exponent_low ICC in [0.5, 0.8]): {p1}")
    print(f"REGISTERED PREDICTION 2 (lrtc_alpha < exponent_low):      {p2}")

    wh = res.get("whole_head_exponent", {})
    if "icc" in wh:
        inside = math.isfinite(wh["ci"][0]) and wh["ci"][0] <= PUBLISHED_EXPONENT_ICC <= wh["ci"][1]
        print(f"\nEXTERNAL CHECK vs PMID 42395346 (published exponent ICC {PUBLISHED_EXPONENT_ICC}):")
        print(f"   ours {wh['icc']:.3f} [{wh['ci'][0]:.3f}, {wh['ci'][1]:.3f}] -> published value is "
              + ("INSIDE our interval; an independent estimator agrees" if inside else
                 "OUTSIDE our interval; the two pipelines differ on the same data"))

    print("\nWHAT THIS CANNOT SHOW (registered, and it must survive into any write-up):")
    print("   A five-year interval is a LOWER BOUND on measurement reliability, not an estimate of it.")
    print("   Real biological change over five years is confounded with measurement error here, so a high")
    print("   ICC is informative and a low one is ambiguous. sqrt(ICC) above is a FLOOR on the trait")
    print("   ceiling, not the ceiling.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump({"results": res, "prediction_1": p1, "prediction_2": p2,
               "published_exponent_icc": PUBLISHED_EXPONENT_ICC, "task": TASK, "acq": ACQ,
               "reps": REPS, "seed": SEED}, open(OUT, "w"), indent=2, default=str)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
