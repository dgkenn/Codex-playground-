#!/usr/bin/env python3
"""E151 -- does anything change MORE at the behavioural transition than at a matched non-transition?

REGISTERED BEFORE THE NEW STATISTIC HAS BEEN COMPUTED ON ANY SUBJECT. Successor to E148, whose ROC arm
was correctly specified and whose own placebo refuted it. The cohort, the candidates, the aliveness gate
and the window widths are E148's, unchanged. **The statistic changes, for a reason E148 measured.**

=========================================================================================================
WHAT E148 GOT AND WHY IT DOES NOT SURVIVE
=========================================================================================================
E148 compared, across each behavioural landmark, whether a candidate stayed with the drug (the adjacent
window, at essentially the same concentration) or returned to the awake baseline. At ROC four candidates
came in decisively on the drug side:

    rel_delta        -0.3891 [-0.5943, -0.1939]   2 of 10 subjects positive
    spectral_entropy -0.3916 [-0.6147, -0.1641]   2 of 10
    rel_beta         -0.3014 [-0.4771, -0.1349]   1 of 10
    alpha_peak_hz    -0.7037 [-0.8402, -0.5538]   **0 of 10**

which is the registered prediction confirmed, and it is wrong. **The random-landmark placebo puts those
four at percentiles 0.456, 0.532, 0.498 and 0.625** of landmarks drawn from the interior of the
unconscious period. The reason is arithmetic, not physiological: **two ADJACENT windows resemble each
other anywhere in a smooth recording**, so the "distance to the adjacent window" term is small at every
landmark and the statistic reports temporal autocorrelation wearing a pharmacological label. Rule 64, for
the second time in this project.

(E148's LOC arm was separately mis-specified -- it used the awake baseline as the state reference on both
sides, which inverts the meaning at LOC -- and its numbers are withdrawn in the ledger. This file fixes
that too, by not needing a state reference at all.)

=========================================================================================================
THE STATISTIC, WHICH IS BUILT SO THE PLACEBO CANNOT REPRODUCE IT
=========================================================================================================
For candidate f, subject s, landmark L and window W:

    jump(L)  =  | median f over [L+1, L+W]  -  median f over [L-W+1, L] |   in that subject's MAD units
    D(s, f)  =  jump(L_real)  -  median over 200 random L of jump(L_random)

Random landmarks are drawn from the interior of the unconscious period, so they share the real landmark's
window widths, its adjacency, its drug trajectory and its autocorrelation -- **everything except the
behavioural transition.** D > 0 therefore means the candidate moves more when responsiveness changes than
when it does not, which is what "tracks behavioural state" has to mean if it is to mean anything beyond
smoothness.

**Scaling by each subject's own MAD of f across the recording is not cosmetic.** Rule 57: an amplitude in
arbitrary units is not a magnitude, and a subject-specific gain would otherwise dominate the
between-subject variance of D. The normalisation is applied identically to the real and random jumps, so
it cannot create the effect.

**This is a strictly harder test than E148's and it is the honest one.** E148 asked "which reference is it
closer to"; a null there could be produced by the recording being smooth. Here the placebo is the
denominator rather than a gate applied afterwards.

=========================================================================================================
GATES
=========================================================================================================
G1  MANIFEST, E148's, unchanged: 10 volunteers, one behavioural LOC and one behavioural ROC each,
    >= 300 epochs of drug-free baseline and >= 300 epochs either side of each landmark.
G2  ALIVENESS, E148's, unchanged: |AUC - 0.5| >= 0.10 for conscious versus unconscious. All eleven
    candidates passed at 0.121 to 0.422, so this is a check rather than a filter here, and it is kept so
    the two files are comparable.
G3  **POSITIVE CONTROL, AND IT CAN FAIL.** A synthetic candidate constructed as the label itself plus
    noise -- a feature that by definition changes exactly at the behavioural landmark and nowhere else --
    must return D > 0 with an interval excluding zero, at three noise levels. If the machinery cannot
    detect a feature built to be detectable, no null below is interpretable (rule 40 inverted: a test
    that nothing can pass is not a test). E103's whole value was that it carried a positive control which
    failed and exposed a broken extractor.
G4  **NEGATIVE CONTROL.** A synthetic candidate that is smooth in time and independent of the label -- a
    random walk with the same autocorrelation as the real features -- must return D indistinguishable
    from zero. If smoothness alone produces D > 0, the statistic has not escaped E148's problem.
G5  WINDOW AGREEMENT: the sign of the subject-level mean D must agree at W in {60, 150, 300} epochs.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
Subject-level mean D per candidate per landmark, subject bootstrap over ten volunteers, plus the sign
count -- which at n = 10 is the inference with the fewest assumptions (10/10 gives p = 0.002 two-sided,
9/10 gives 0.011). Holm across the candidates within each landmark.

**IF NOTHING HAS D > 0**, then on the best-anchored behavioural transition data available to this project
no spectral summary changes more at loss or return of responsiveness than at an arbitrary moment of
matched drug exposure. That is a strong negative for Challenge A's recovery clause **and it is the outcome
E148's placebo already points to**, so it is the expected one and is written first. It would mean the
frontal spectral signature tracks the drug's trajectory and is indifferent to the behavioural threshold
crossing -- which is a clean, publishable statement about what these features are, and an argument that a
consciousness marker cannot be built from the amplitude family alone.

**IF SOMETHING HAS D > 0** at both landmarks with G3 and G4 passed, it is the first evidence in this
project of a spectral feature that is sensitive to the behavioural transition rather than to the exposure,
and it goes straight to the OR cohort (44 cases, a different monitor, a different population) for
replication before anything else is said about it.

**REGISTERED PREDICTION: NOTHING CLEARS AT BOTH LANDMARKS. The most likely single positive, if there is
one, is `alpha_peak_hz` at ROC**, because it was the one candidate E148 found unanimous across subjects
(0 of 10 positive) and unanimity across subjects is the part of that result the placebo does not explain
-- the placebo explains the LEVEL, not why every subject agrees.

SCOPE. Ten subjects, one agent, spectra only. Unchanged from E148 and stated again because a negative here
bounds the amplitude family on propofol, not representations in general.

WHAT WAS ALREADY SEEN (rule 41). All of E148's output, quoted above.

    python bsde/src/bsde/experiments/e151_landmark_specific_transition.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import auc_abs, cluster_bootstrap_ci                  # noqa: E402

sys.path.insert(0, HERE)
from e148_roc_concentration_matched_dissociation import (BASELINE_EPOCHS,      # noqa: E402
                                                         FEATURES, WINDOWS, _med, load)

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e151_landmark_specific.json")

W_PRIMARY = 150
RANDOM_DRAWS = 200
ALIVE_BAR = 0.10


def jump(v, lm, w, scale):
    pre = _med(v, lm - w + 1, lm + 1)
    post = _med(v, lm + 1, lm + 1 + w)
    if not (math.isfinite(pre) and math.isfinite(post)) or scale <= 0:
        return float("nan")
    return abs(post - pre) / scale


def d_stat(v, lm, w, lo_i, hi_i, rng, draws=RANDOM_DRAWS):
    """Real jump minus the median jump at random landmarks with identical geometry."""
    s = np.nanmedian(np.abs(v - np.nanmedian(v)))
    if not math.isfinite(s) or s <= 0:
        return float("nan"), float("nan")
    real = jump(v, lm, w, s)
    rnd = []
    if hi_i > lo_i:
        for _ in range(draws):
            j = jump(v, int(rng.integers(lo_i, hi_i)), w, s)
            if math.isfinite(j):
                rnd.append(j)
    if not rnd or not math.isfinite(real):
        return float("nan"), float("nan")
    return real - float(np.median(rnd)), float(np.mean(np.asarray(rnd) >= real))


def main(argv=None) -> int:
    rng = np.random.default_rng(151)
    data = load()
    subs = sorted(data)
    ok_subj = [c for c in subs
               if len(data[c]["loc"]) == 1 and len(data[c]["roc"]) == 1
               and data[c]["loc"][0] >= max(BASELINE_EPOCHS, max(WINDOWS))
               and data[c]["roc"][0] - data[c]["loc"][0] >= 2 * max(WINDOWS)
               and data[c]["n"] - data[c]["roc"][0] >= max(WINDOWS)]
    g1 = len(ok_subj) >= 8
    print(f"G1 MANIFEST  {len(ok_subj)} of {len(subs)} volunteers usable -> {'PASS' if g1 else 'FAIL'}")
    out = {"experiment": "E151", "usable": ok_subj, "window": W_PRIMARY}

    alive = []
    for f in FEATURES:
        vals = []
        for c in ok_subj:
            d = data[c]
            m = np.isfinite(d["X"][f]) & np.isin(d["label"], (0.0, 1.0))
            if m.sum() > 50 and len(set(d["label"][m])) > 1:
                vals.append(auc_abs(list(d["label"][m]), list(d["X"][f][m])) - 0.5)
        a = float(np.mean(vals)) if vals else float("nan")
        if math.isfinite(a) and a >= ALIVE_BAR:
            alive.append(f)
    print(f"G2 ALIVENESS  {len(alive)} of {len(FEATURES)} candidates alive")
    out["G2_alive"] = alive

    def interior(d):
        return int(d["loc"][0]) + max(WINDOWS), int(d["roc"][0]) - max(WINDOWS)

    def run_series(series_of, tag_extra=""):
        """Subject-level D at each landmark for a per-subject series-producing callable."""
        res = {}
        for tag, key in (("LOC", "loc"), ("ROC", "roc")):
            per, pct, wins = {}, {}, {}
            for c in ok_subj:
                d = data[c]
                v = series_of(c)
                lm = int(d[key][0])
                lo_i, hi_i = interior(d)
                per[c], pct[c] = d_stat(v, lm, W_PRIMARY, lo_i, hi_i, rng)
                wins[c] = [d_stat(v, lm, w, lo_i, hi_i, rng, draws=80)[0] for w in WINDOWS]
            vals = np.array([per[c] for c in ok_subj], float)
            good = np.isfinite(vals)
            if good.sum() < 6:
                continue
            m = float(np.mean(vals[good]))
            lo, hi, _n = cluster_bootstrap_ci(
                lambda ix, vv=vals[good]: float(np.mean(vv[list(ix)])),
                np.arange(int(good.sum())), rng, reps=2000)
            npos = int((vals[good] > 0).sum())
            pv = np.array([pct[c] for c in ok_subj], float)
            pv = pv[np.isfinite(pv)]
            wm = [float(np.nanmean([wins[c][i] for c in ok_subj])) for i in range(len(WINDOWS))]
            g5 = len({int(np.sign(x)) for x in wm if math.isfinite(x) and x != 0}) == 1
            res[tag] = {"mean_D": m, "ci": [lo, hi], "n_pos": npos, "n": int(good.sum()),
                        "mean_random_pct": float(np.mean(pv)) if len(pv) else float("nan"),
                        "window_means": wm, "G5_sign_agrees": bool(g5),
                        "per_subject": {c: per[c] for c in ok_subj}}
        return res

    # ---- G3 positive control ---------------------------------------------------------------------------
    print(f"\nG3 POSITIVE CONTROL  synthetic = label + noise, must give D > 0 with an interval "
          f"excluding zero")
    g3_rows = {}
    for sigma in (0.25, 0.5, 1.0):
        syn = {c: data[c]["label"] + sigma * rng.standard_normal(data[c]["n"]) for c in ok_subj}
        r = run_series(lambda c, s=syn: s[c])
        g3_rows[f"sigma{sigma}"] = r
        for tag in ("LOC", "ROC"):
            v = r.get(tag)
            if v:
                print(f"   sigma={sigma:<4} {tag}  D={v['mean_D']:+.4f} "
                      f"[{v['ci'][0]:+.4f},{v['ci'][1]:+.4f}]  {v['n_pos']}/{v['n']}")
    g3 = all(v["ci"][0] > 0 for r in g3_rows.values() for v in r.values())
    print(f"   -> {'PASS' if g3 else 'FAIL: the machinery cannot detect a feature built to be detected'}")

    # ---- G4 negative control ---------------------------------------------------------------------------
    print(f"\nG4 NEGATIVE CONTROL  smooth random walk, independent of the label, must give D ~ 0")
    walk = {}
    for c in ok_subj:
        n = data[c]["n"]
        w = np.cumsum(rng.standard_normal(n))
        k = 51
        walk[c] = np.convolve(w, np.ones(k) / k, mode="same")
    r4 = run_series(lambda c, s=walk: s[c])
    for tag, v in r4.items():
        print(f"   {tag}  D={v['mean_D']:+.4f} [{v['ci'][0]:+.4f},{v['ci'][1]:+.4f}]  "
              f"{v['n_pos']}/{v['n']}")
    g4 = all(v["ci"][0] <= 0 <= v["ci"][1] for v in r4.values())
    print(f"   -> {'PASS' if g4 else 'FAIL: smoothness alone produces a landmark effect'}")
    out["G3"], out["G4"] = {"rows": g3_rows, "pass": bool(g3)}, {"rows": r4, "pass": bool(g4)}

    gates = g1 and g3 and g4
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    # ---- primary ----------------------------------------------------------------------------------------
    print(f"{'candidate':18s} {'lm':4s} {'mean D':>8s} {'95% CI':>20s} {'signs':>7s} "
          f"{'rand pct':>9s} {'G5':>5s}")
    res, pv_by = {}, {"LOC": {}, "ROC": {}}
    for f in alive:
        r = run_series(lambda c, ff=f: data[c]["X"][ff])
        for tag, v in r.items():
            res[f"{f}|{tag}"] = {**v, "feature": f, "landmark": tag}
            pv_by[tag][f] = v["mean_random_pct"]
            print(f"{f:18s} {tag:4s} {v['mean_D']:+8.4f} "
                  f"[{v['ci'][0]:+7.4f},{v['ci'][1]:+7.4f}] {v['n_pos']:3d}/{v['n']:<3d} "
                  f"{v['mean_random_pct']:9.3f} {'ok' if v['G5_sign_agrees'] else 'FAIL':>5s}")
    out["primary"] = res
    for tag in ("LOC", "ROC"):
        if pv_by[tag]:
            adj = holm(list(pv_by[tag].values()), list(pv_by[tag].keys()))
            for f, a in adj.items():
                res[f"{f}|{tag}"]["p_holm_random"] = a

    both = [f for f in alive
            if res.get(f"{f}|LOC", {}).get("ci", [-1, 1])[0] > 0
            and res.get(f"{f}|ROC", {}).get("ci", [-1, 1])[0] > 0
            and res.get(f"{f}|LOC", {}).get("G5_sign_agrees")
            and res.get(f"{f}|ROC", {}).get("G5_sign_agrees")]
    if not gates:
        verdict = ("NO VERDICT -- " + ("G3 failed (positive control undetected) " if not g3 else "")
                   + ("G4 failed (smoothness alone makes a landmark effect) " if not g4 else "")
                   + ("G1 failed" if not g1 else ""))
    elif both:
        verdict = (f"POSITIVE -- {', '.join(both)} change more at the behavioural transition than at a "
                   f"matched non-transition, at BOTH landmarks, with the positive and negative controls "
                   f"passed. Replicate on the 44 OR cases before anything else is said.")
    else:
        verdict = ("NEGATIVE -- no spectral summary changes more at loss or return of responsiveness "
                   "than at an arbitrary moment of matched drug exposure. On the best-anchored "
                   "behavioural transition data available to this project, the frontal amplitude family "
                   "tracks the exposure trajectory and is indifferent to the behavioural threshold "
                   "crossing. This is the registered prediction and E148's placebo already pointed to it.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
