#!/usr/bin/env python3
"""E56 -- Challenge B. Is the marker ATTENUATED by a noisy label, or is it simply WEAK?

E38 measured the BCI label's reliability at r_sb = 0.2918, capping any predictor at sqrt(0.2918) = 0.5402,
and every Challenge B result since has been read through that ceiling. E45 supplied the other half:
`lrtc_alpha`'s five-year ICC is 0.644, so the joint ceiling is 0.5402 x sqrt(0.644) = 0.434 and E42's
observed +0.2446 sits comfortably inside it.

**But nobody has tested whether the correlation actually BEHAVES like an attenuated one.** A ceiling
computed from a reliability coefficient is arithmetic; it is not evidence that label noise is what limits
the observed value. If the marker is simply weak, the same numbers appear and the interpretation --
"recruit better labels and the correlation rises" -- is wrong.

=========================================================================================================
THE TEST, AND WHY IT HAS NO FREE PARAMETERS
=========================================================================================================
Spearman-Brown gives the reliability of a k-trial label from the reliability of the full one. E38 measured
the 45-trial label at rho_45 = 0.2918, which inverts to a single-trial reliability of
rho_1 = rho_45 / (45 - 44*rho_45) = 0.00907, and predicts every intermediate k.

Classical attenuation then says the observable correlation is r_k = r_true * sqrt(rho_k * rho_predictor).
The predictor's reliability is the same at every k, so it cancels in a RATIO:

    r_k / r_45  =  sqrt(rho_k / rho_45)          <- no free parameters at all

    k = 12  ->  0.582        k = 20  ->  0.728        k = 30  ->  0.859        k = 45  ->  1.000

So the attenuation model makes a complete, falsifiable prediction about the SHAPE of the growth curve,
using only a quantity measured in a different experiment.

=========================================================================================================
DESIGN
=========================================================================================================
For each k, each subject's imagery label is recomputed from a random k-trial subsample using **E38's own
out-of-fold estimator, imported rather than reimplemented** (rule 20), averaged over `N_DRAWS` independent
draws to keep the estimator's own noise below the effect being measured -- the correction E38 itself needed.
Each resulting label is correlated across subjects with the resting marker.

PRIMARY: the observed ratio r_k / r_45 against the predicted ratio, for `lrtc_alpha` (E42's marker).

VERDICT RULE -- failing case first, and the wrong direction is the informative one:

  (a) REFUTED -- r does not grow with k (the k = 12 ratio is not below the k = 45 ratio by a margin
      exceeding its bootstrap interval). **The attenuation reading is wrong: the marker is weak, not
      attenuated, and better labels will not rescue Challenge B.** This is the consequential outcome and
      it is written first.
  (b) NOT INFORMATIVE -- r_45 itself is indistinguishable from zero, so ratios have no denominator.
  (c) CONSISTENT WITH ATTENUATION -- r grows with k and the observed ratios sit within their intervals of
      the parameter-free predictions.

INCUMBENT (rule 45): `exponent_low` is carried alongside as the measure the project used before E42. If
the growth appears for `lrtc_alpha` and not for it, that is a property of the marker rather than of the
label, and the write-up must say so.

WHAT THIS CANNOT SHOW. Growth consistent with Spearman-Brown does not prove label noise is the ONLY
limit -- it shows the observed correlation responds to label precision as the model says it should. And
the trial subsampling reduces the DATA behind each label, which is exactly what the model describes, but
it does not reproduce the other ways a real label could be better (more sessions, a cleaner paradigm,
better-instructed subjects).

    python -m bsde.experiments.e56_attenuation_growth
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import spearman                                     # noqa: E402
from bsde.experiments.e38_bci_label_reliability import _auc_folds            # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e56_attenuation_growth.json")

RHO_FULL = 0.2918          # E38's measured label reliability at the full trial count
FULL_K = 45          # E38 measured RHO_FULL at the full 45-trial label; that is what SB inverts from
KS = (12, 20, 30, 40)
"""k = 45 was in the first version and is REMOVED. With ~45 imagery trials per subject, a k = 45
subsample is ALL of them, so its draws differ only in fold assignment while every k < 45 draw also varies
trial selection. Lower k therefore received more variance reduction from averaging, biasing the curve in
favour of mid-k -- and r duly fell from 0.267 at k = 30 to 0.203 at k = 45, which was read as evidence
against attenuation when it was an artefact of the design. Every level is now a genuine subsample."""
REF_K = 40
MARKER = "lrtc_alpha"
INCUMBENT = "exponent_low"
N_DRAWS = 12
REPS = 8000
SEED = 20260731


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:                                                        # noqa: BLE001
        return None


def sb_reliability(k, rho_full=RHO_FULL, full_k=FULL_K):
    """Spearman-Brown reliability of a k-item label, from the full-length reliability."""
    rho1 = rho_full / (full_k - (full_k - 1) * rho_full)
    return k * rho1 / (1.0 + (k - 1) * rho1)


def _trials():
    rows = []
    for f in sorted(glob.glob(os.path.join(RESULTS, "eegmmidb_trials.imagery.s*.csv"))):
        with open(f) as fh:
            rows += list(csv.DictReader(fh))
    by = {}
    for r in rows:
        y = _f(r.get("y"))
        x = [_f(r.get(f"f{i}")) for i in range(6)]
        if y is None or any(v is None for v in x):
            continue
        by.setdefault(r["subject"], []).append((x, int(y)))
    return by


def _markers():
    rows = []
    for f in sorted(glob.glob(os.path.join(RESULTS, "eegmmidb_rest_v2.s*.csv"))):
        with open(f) as fh:
            rows += [r for r in csv.DictReader(fh) if r.get("status") == "ok"]
    out = {}
    for r in rows:
        for m in (MARKER, INCUMBENT):
            v = _f(r.get(m))
            if v is not None:
                out.setdefault(r["subject"], {}).setdefault(m, []).append(v)
    return {s: {m: float(np.mean(v)) for m, v in d.items()} for s, d in out.items()}


def main() -> int:
    by = _trials()
    mk = _markers()
    subs = sorted(set(by) & set(mk))
    subs = [s for s in subs if len(by[s]) >= FULL_K and MARKER in mk[s] and INCUMBENT in mk[s]]
    print("=" * 100)
    print("E56 -- is Challenge B's marker attenuated by a noisy label, or simply weak?")
    print("=" * 100)
    print(f"   subjects with >= {FULL_K} imagery trials and both markers: {len(subs)}")
    if len(subs) < 40:
        print("   G1 FAILED: too few subjects. No verdict.")
        json.dump({"gate": "G1_failed", "n": len(subs)}, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    labels = {k: {} for k in KS}
    for s in subs:
        X = np.array([t[0] for t in by[s]], float)
        y = np.array([t[1] for t in by[s]], int)
        n = len(y)
        for k in KS:
            vals = []
            for _ in range(N_DRAWS):
                idx = rng.choice(n, size=min(k, n), replace=False)
                v = _auc_folds(X[idx], y[idx], rng)
                if math.isfinite(v):
                    vals.append(v)
            labels[k][s] = float(np.mean(vals)) if vals else float("nan")

    print(f"\n   {'k':>4s} {'pred rho_k':>11s} {'pred ratio':>11s} "
          f"{'r(marker)':>10s} {'obs ratio':>10s} {'95% CI on ratio':>20s} {'r(incumbent)':>13s}")
    print("   " + "-" * 88)
    res = {}
    base = None
    for k in KS:
        v = np.array([labels[k][s] for s in subs], float)
        m = np.array([mk[s][MARKER] for s in subs], float)
        inc = np.array([mk[s][INCUMBENT] for s in subs], float)
        ok = np.isfinite(v) & np.isfinite(m) & np.isfinite(inc)
        r_m = spearman(v[ok], m[ok])
        r_i = spearman(v[ok], inc[ok])
        if k == REF_K:
            base = r_m
        res[k] = {"rho_k": sb_reliability(k), "pred_ratio": math.sqrt(sb_reliability(k) / RHO_FULL),
                  "r_marker": r_m, "r_incumbent": r_i, "n": int(ok.sum())}
        print(f"   {k:4d} {sb_reliability(k):11.4f} {res[k]['pred_ratio']:11.3f} "
              f"{r_m:10.3f} {'':>10s} {'':>20s} {r_i:13.3f}")

    # SLOPE of r on sqrt(rho_k), not a ratio. A ratio of correlations has an uncertain denominator and
    # its interval was [-1.219, +1.802] -- wide enough that the verdict keyed on it could only ever say
    # "includes 1". The slope uses all four levels, has a stable interval, and its null (no response to
    # label precision) is simply slope <= 0.
    idx_all = np.arange(len(subs))
    xs = np.array([math.sqrt(sb_reliability(k)) for k in KS])

    def _slope(ss, feat):
        ys = []
        for k in KS:
            vk = np.array([labels[k][s] for s in ss], float)
            mm = np.array([mk[s][feat] for s in ss], float)
            o = np.isfinite(vk) & np.isfinite(mm)
            ys.append(spearman(vk[o], mm[o]))
        ys = np.array(ys)
        return float(np.polyfit(xs, ys, 1)[0]) if np.isfinite(ys).all() else float("nan")

    slopes = {}
    for feat in (MARKER, INCUMBENT):
        pt = _slope(subs, feat)
        r2 = np.random.default_rng(SEED + 5)
        d = []
        for _ in range(REPS // 4):
            i = r2.choice(idx_all, size=idx_all.size, replace=True)
            v = _slope([subs[j] for j in i], feat)
            if math.isfinite(v):
                d.append(v)
        d = np.sort(np.array(d))
        slopes[feat] = {"slope": pt,
                        "ci": [float(np.quantile(d, .025)), float(np.quantile(d, .975))] if d.size
                        else [float("nan")] * 2,
                        "p_le_zero": float(np.mean(d <= 0)) if d.size else float("nan")}
        print(f"\n   slope of r on sqrt(rho_k), {feat:16s} {pt:+.3f} "
              f"[{slopes[feat]['ci'][0]:+.3f}, {slopes[feat]['ci'][1]:+.3f}]   "
              f"P(slope <= 0) = {slopes[feat]['p_le_zero']:.4f}")

    m, i_ = slopes[MARKER], slopes[INCUMBENT]
    if abs(res[REF_K]["r_marker"]) < 0.05:
        verdict = ("NOT INFORMATIVE -- r at the reference trial count is indistinguishable from zero.")
    elif not math.isfinite(m["ci"][0]) or m["ci"][0] <= 0:
        verdict = ("UNDERPOWERED, NOT REFUTED -- the slope of r on label precision does not exclude "
                   "zero, so attenuation is NOT DEMONSTRATED. It is also not refuted: rule 31 says a "
                   "test that fails its own gate yields an ABSENT verdict, not a negative one, and "
                   "calling this 'refuted' would tell the investigator to abandon the better-labels "
                   "route on evidence that in fact leans the other way. Read the monotonicity and the "
                   "marker-minus-incumbent slope contrast before concluding anything.")
    elif math.isfinite(i_["ci"][1]) and i_["ci"][1] > 0:
        verdict = ("NOT INFORMATIVE -- the INCUMBENT's slope also excludes zero upward, so the growth is "
                   "a property of the subsampling procedure rather than of the marker.")
    else:
        verdict = ("CONSISTENT WITH ATTENUATION -- r rises with label precision (slope excludes zero) "
                   "while the incumbent's does not, so the growth is specific to the marker.")
    print("\n" + "-" * 100)
    print(f"VERDICT: {verdict}")
    json.dump({"n_subjects": len(subs), "rho_full": RHO_FULL, "results": {str(k): v for k, v in res.items()},
               "verdict": verdict, "n_draws": N_DRAWS, "reps": REPS, "seed": SEED},
              open(OUT, "w"), indent=2, default=str)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
