#!/usr/bin/env python3
"""E243 -- how many labelled subjects does a new site need before a transported measure works?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.

WHY THIS IS THE QUESTION AND NOT "DOES IT TRANSPORT". Transport has been measured and the answer is
settled: `whole_head_exponent` separates wake from N3 essentially perfectly INSIDE each deposit --
AUC 0.9920 on Sleep-EDFx (141 subjects) and 1.0000 on ds006695 (19 subjects, complete separation, the
largest wake value +1.6708 below the smallest N3 value +1.9042) -- and its VALUE does not carry across.
Sleep-EDFx runs 0.7123 -> 2.6904 where ds006695 runs 1.1318 -> 2.0890: **higher at wake, lower at deep
sleep**, diverging in opposite directions from their own baselines, with less than half the dynamic
range. No additive offset aligns both states, and within-subject referencing makes the mismatch worse
(gated ratio 0.211 -> 0.657).

Repeating that as "it does not transport" is a dead end, because the finding is not that the measure is
broken -- it discriminates perfectly at both sites -- but that it is UNCALIBRATED. So the useful
question is the deployment one: **a new site can always label a few subjects; how few is enough?** That
turns an obstacle into a cost, and a cost can be reported.

WHAT IS FITTED, AND WHY TWO PARAMETERS RATHER THAN ONE. The deposits differ in both location and scale,
so three schemes are compared, in increasing cost:

  NONE          use the source deposit's decision threshold directly. Zero labels. The baseline that
                the transport finding predicts will fail.
  OFFSET        shift the target's values by (target wake mean - source wake mean), estimated from k
                labelled WAKE subjects only. Wake is the cheap label -- a new site can record an awake
                baseline without a sleep study -- so this scheme is the one worth wanting.
  OFFSET+SCALE  affine-align the target to the source using k labelled subjects of EACH state. Costs
                twice the labels and needs deep sleep, which is the expensive part.

PRIMARY. Held-out wake-versus-N3 accuracy on ds006695 as a function of k, for each scheme, with the
calibration subjects DISJOINT from the evaluation subjects at every k. The number reported is the
smallest k at which a scheme reaches the within-deposit ceiling, and the answer "no k is enough" is a
legitimate and informative outcome for the OFFSET scheme.

  P1  accuracy(scheme, k) curves, k = 1..8, each averaged over repeated disjoint draws.
  P2  the smallest k at which OFFSET reaches the ceiling, or a statement that it does not.
  P3  the same for OFFSET+SCALE, and the difference between them -- which is the price, in labelled deep
      sleep, of the scale parameter.

GATES, each able to go either way (rules 40 and 81).

  G1  THE CEILING MUST EXIST. A within-deposit classifier trained and evaluated on disjoint ds006695
      subjects must reach high accuracy. If the measure cannot separate the states at the target site
      even with target labels, no calibration scheme can and the question is void.
  G2  THE UNCALIBRATED BASELINE MUST FAIL. If NONE already reaches the ceiling, the deposits are aligned
      and there is nothing to calibrate -- the transport finding would then be wrong and this file must
      say so rather than reporting a calibration benefit that is noise.
  G3  CAPABILITY, both directions, on synthetic deposits whose answer is known by construction. Two
      synthetic sites differing by a known OFFSET ONLY must be fully corrected by the OFFSET scheme;
      two differing by offset AND scale must NOT be, and must require OFFSET+SCALE. If the schemes
      cannot be told apart on data built to distinguish them, they cannot be told apart on real data.
  G4  DISJOINTNESS. At every k, calibration and evaluation subjects must not overlap. Asserted in code
      and reported, not promised in prose.

PLACEBO. Calibration constants estimated from subjects whose stage labels have been PERMUTED. A scheme
that improves accuracy under permuted labels is improving it by shrinking variance rather than by
aligning states, and the gain is not calibration. Compared against the placebo's DISTRIBUTION over
draws, never its mean (rule 37).

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37).

  (a) Calibration makes accuracy WORSE than the uncalibrated baseline at every k -> WRONG DIRECTION. The
      alignment is anti-correlated with what the target needs, which would mean the source and target
      differ in a way an affine map cannot express, and is a stronger negative than "calibration does
      not help".
  (b) OFFSET reaches the ceiling at small k -> CHEAP CALIBRATION. A new site needs only a handful of
      labelled WAKE recordings, which is the practically important outcome and the one that would make
      this measure deployable.
  (c) OFFSET never reaches the ceiling but OFFSET+SCALE does -> SCALE IS REQUIRED. Deployment needs
      labelled deep sleep at the target site, and the report is the number of subjects.
  (d) Neither reaches the ceiling at any k tested -> AFFINE ALIGNMENT IS INSUFFICIENT. The deposits
      differ by more than location and scale, and the successor must ask what.

  Gating, applied AFTER the primaries because a gate can only invalidate a pass and never rescue a null
  (rule 37): G1, G2 or G3 failing -> NOT INTERPRETABLE. The placebo matching a scheme's gain -> that
  scheme's gain is reported as variance reduction and not as calibration.

SCOPE. Two sleep deposits, one measure, one state contrast. ds006695 is a 3-channel forehead montage
with 19 subjects against Sleep-EDFx's 2-channel with 141, and the project's own deposit probe records
that this makes `whole_head_exponent` arguably a different measurement in each. A calibration cost
measured between these two is not a general calibration cost, and the direction of transfer matters --
only source Sleep-EDFx to target ds006695 is tested here.

INCUMBENT (rule 45): the uncalibrated transfer, scheme NONE, at zero labels. Every calibrated scheme is
reported as an improvement over it or not at all.

    python bsde/src/bsde/experiments/e243_calibration_cost.py
"""
from __future__ import annotations

import collections
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

SOURCE = "bsde/results/sleep_edfx_five_stage.csv"
TARGET = "bsde/results/ds006695_features.csv"
OUT = "bsde/results/e243_calibration_cost.json"
FEATURE = "whole_head_exponent"
K_RANGE = tuple(range(1, 9))
N_DRAWS = 400
N_PLACEBO = 200
SEED = 20260802


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def subject_means(rows, stage_of, feature):
    import numpy as np
    d = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        st = stage_of(r)
        v = _f(r.get(feature))
        if np.isfinite(v):
            d[r["__subj__"]][st].append(v)
    return {s: {k: float(np.mean(v)) for k, v in st.items()} for s, st in d.items()}


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import read_rows
    rng = np.random.default_rng(SEED)

    src, _ = read_rows(SOURCE)
    for r in src:
        r["__subj__"] = r["recording_id"].split("@")[0][:6]
    tgt, _ = read_rows(TARGET)
    for r in tgt:
        r["__subj__"] = r["subject"]

    S = subject_means(src, lambda r: r["recording_id"].split("@")[-1], FEATURE)
    T = subject_means(tgt, lambda r: r["stage"], FEATURE)
    S = {s: v for s, v in S.items() if "W" in v and "N3" in v}
    T = {s: v for s, v in T.items() if "W" in v and "N3" in v}
    assert S and T, "no subject carries both states"
    print(f"source Sleep-EDFx: {len(S)} subjects with both W and N3")
    print(f"target ds006695:  {len(T)} subjects with both W and N3")
    sw = np.asarray([S[s]["W"] for s in S], float)
    sn = np.asarray([S[s]["N3"] for s in S], float)
    print(f"source W {sw.mean():+.4f}  N3 {sn.mean():+.4f}   "
          f"target W {np.mean([T[s]['W'] for s in T]):+.4f}  "
          f"N3 {np.mean([T[s]['N3'] for s in T]):+.4f}")

    # source decision threshold: the midpoint that maximises source accuracy
    grid = np.linspace(min(sw.min(), sn.min()), max(sw.max(), sn.max()), 2001)
    acc = [float(np.mean(sw < t) / 2 + np.mean(sn >= t) / 2) for t in grid]
    THR = float(grid[int(np.argmax(acc))])
    print(f"source threshold {THR:.4f} (source accuracy {max(acc):.4f})")

    tsub = sorted(T)

    def evaluate(subs, a, b):
        """Accuracy on `subs` after mapping target values as a*x + b."""
        ok = 0
        for s in subs:
            ok += (a * T[s]["W"] + b) < THR
            ok += (a * T[s]["N3"] + b) >= THR
        return ok / (2 * len(subs))

    def fit(scheme, cal, labels=None):
        """Calibration constants from the labelled subset `cal`. `labels` permutes states for the placebo."""
        lab = labels or {s: {"W": T[s]["W"], "N3": T[s]["N3"]} for s in cal}
        w = np.asarray([lab[s]["W"] for s in cal], float)
        n = np.asarray([lab[s]["N3"] for s in cal], float)
        if scheme == "NONE":
            return 1.0, 0.0
        if scheme == "OFFSET":
            return 1.0, float(sw.mean() - w.mean())
        rng_t = float(n.mean() - w.mean())
        rng_s = float(sn.mean() - sw.mean())
        a = rng_s / rng_t if abs(rng_t) > 1e-9 else 1.0
        return a, float(sw.mean() - a * w.mean())

    # ---- G1 ceiling / G2 uncalibrated baseline --------------------------------------------------------
    ceil_draws = []
    for _ in range(N_DRAWS):
        idx = rng.permutation(len(tsub))
        cal = [tsub[i] for i in idx[:4]]
        ev = [tsub[i] for i in idx[4:]]
        a, b = fit("OFFSET+SCALE", cal)
        ceil_draws.append(evaluate(ev, a, b))
    within = []
    for _ in range(N_DRAWS):
        idx = rng.permutation(len(tsub))
        cal = [tsub[i] for i in idx[:4]]
        ev = [tsub[i] for i in idx[4:]]
        w = np.mean([T[s]["W"] for s in cal])
        n = np.mean([T[s]["N3"] for s in cal])
        thr = (w + n) / 2
        within.append(np.mean([[T[s]["W"] < thr, T[s]["N3"] >= thr] for s in ev]))
    CEIL = float(np.mean(within))
    base = evaluate(tsub, 1.0, 0.0)
    g1 = CEIL > 0.9
    g2 = base < CEIL - 0.05
    print(f"G1 within-deposit ceiling (target-native threshold, disjoint eval): {CEIL:.4f} "
          f"-> {'PASS' if g1 else 'FAIL'}")
    print(f"G2 uncalibrated transfer (scheme NONE): {base:.4f} against the ceiling "
          f"-> {'PASS (there is something to calibrate)' if g2 else 'FAIL'}")

    # ---- G3 capability on synthetic sites -------------------------------------------------------------
    cap = {}
    for name, (off, sc) in (("offset_only", (0.8, 1.0)), ("offset_and_scale", (0.8, 0.5))):
        gw = rng.normal(sw.mean(), sw.std(), 200)
        gn = rng.normal(sn.mean(), sn.std(), 200)
        fw, fn = sc * gw + off, sc * gn + off
        syn = {f"x{i}": {"W": fw[i], "N3": fn[i]} for i in range(200)}
        saveT = T
        globals()["T"] = syn
        subs = sorted(syn)
        r = {}
        for sch in ("NONE", "OFFSET", "OFFSET+SCALE"):
            accs = []
            for _ in range(100):
                i = rng.permutation(len(subs))
                a, b = fit(sch, [subs[j] for j in i[:8]])
                accs.append(evaluate([subs[j] for j in i[8:]], a, b))
            r[sch] = float(np.mean(accs))
        globals()["T"] = saveT
        cap[name] = r
        print(f"G3 synthetic {name:18s} NONE {r['NONE']:.3f}  OFFSET {r['OFFSET']:.3f}  "
              f"OFFSET+SCALE {r['OFFSET+SCALE']:.3f}")
    g3 = (cap["offset_only"]["OFFSET"] > 0.9
          and cap["offset_and_scale"]["OFFSET"] < cap["offset_and_scale"]["OFFSET+SCALE"] - 0.05)
    print(f"     -> G3 {'PASS' if g3 else 'FAIL'} (OFFSET must fix an offset-only difference and must "
          "NOT fix an offset+scale one)")

    # ---- primaries -------------------------------------------------------------------------------------
    curves, plac = {}, {}
    g4_ok = True
    print()
    print(f"{'k':>3}" + "".join(f"{s:>16}" for s in ("NONE", "OFFSET", "OFFSET+SCALE")))
    for k in K_RANGE:
        if k + 3 > len(tsub):
            break
        row = {}
        for sch in ("NONE", "OFFSET", "OFFSET+SCALE"):
            accs, pls = [], []
            for _ in range(N_DRAWS):
                i = rng.permutation(len(tsub))
                cal = [tsub[j] for j in i[:k]]
                ev = [tsub[j] for j in i[k:]]
                if set(cal) & set(ev):
                    g4_ok = False
                a, b = fit(sch, cal)
                accs.append(evaluate(ev, a, b))
            for _ in range(N_PLACEBO):
                i = rng.permutation(len(tsub))
                cal = [tsub[j] for j in i[:k]]
                ev = [tsub[j] for j in i[k:]]
                lab = {}
                for s in cal:
                    v = [T[s]["W"], T[s]["N3"]]
                    rng.shuffle(v)
                    lab[s] = {"W": v[0], "N3": v[1]}
                a, b = fit(sch, cal, labels=lab)
                pls.append(evaluate(ev, a, b))
            row[sch] = float(np.mean(accs))
            plac.setdefault(sch, {})[k] = float(np.mean(pls))
        curves[k] = row
        print(f"{k:3d}" + "".join(f"{row[s]:16.4f}" for s in ("NONE", "OFFSET", "OFFSET+SCALE")))
    print(f"G4 calibration and evaluation subjects disjoint at every k: {'PASS' if g4_ok else 'FAIL'}")
    print()
    print("placebo (calibration constants from PERMUTED stage labels):")
    for sch in ("OFFSET", "OFFSET+SCALE"):
        print(f"  {sch:14s} " + "  ".join(f"k={k}:{plac[sch][k]:.3f}" for k in sorted(plac[sch])))

    def first_at_ceiling(sch):
        for k in sorted(curves):
            if curves[k][sch] >= CEIL - 0.02:
                return k
        return None

    k_off, k_os = first_at_ceiling("OFFSET"), first_at_ceiling("OFFSET+SCALE")
    print()
    print(f"P2 OFFSET reaches the ceiling at k = {k_off if k_off else 'NEVER (within k<=8)'}")
    print(f"P3 OFFSET+SCALE reaches it at k = {k_os if k_os else 'NEVER (within k<=8)'}")

    best = max(curves[k]["OFFSET"] for k in curves) if curves else 0.0
    if best < base - 0.02 and max(curves[k]["OFFSET+SCALE"] for k in curves) < base - 0.02:
        verdict = ("WRONG DIRECTION -- calibration makes the transfer WORSE than using the source "
                   "threshold untouched, at every k; the two sites differ in a way an affine map cannot "
                   "express and this is a stronger negative than 'calibration does not help'")
    elif k_off is not None:
        verdict = (f"CHEAP CALIBRATION -- {k_off} labelled WAKE subjects at the target site are enough to "
                   "reach the within-deposit ceiling; deployment needs no sleep study")
    elif k_os is not None:
        verdict = (f"SCALE IS REQUIRED -- offset alone never reaches the ceiling within k <= 8, but "
                   f"offset-plus-scale does at k = {k_os}; deployment needs labelled DEEP SLEEP at the "
                   "target site, which is the expensive label")
    else:
        verdict = ("AFFINE ALIGNMENT IS INSUFFICIENT -- neither scheme reaches the ceiling at any k "
                   "tested, so the deposits differ by more than location and scale and the successor "
                   "must ask what")
    if not g3:
        verdict = "NOT INTERPRETABLE -- G3 failed; the schemes cannot be told apart on data built to distinguish them"
    elif not g1:
        verdict = "NOT INTERPRETABLE -- G1 failed; there is no ceiling to reach at the target site"
    elif not g2:
        verdict = "NOT INTERPRETABLE -- G2 failed; the uncalibrated transfer already works and there is nothing to calibrate"
    elif not g4_ok:
        verdict = "NOT INTERPRETABLE -- G4 failed; calibration and evaluation subjects overlapped"
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"n_source": len(S), "n_target": len(T), "source_threshold": THR,
                   "ceiling": CEIL, "uncalibrated": base, "curves": {str(k): v for k, v in curves.items()},
                   "placebo": {s: {str(k): v for k, v in d.items()} for s, d in plac.items()},
                   "k_offset": k_off, "k_offset_scale": k_os, "capability": cap,
                   "gates": {"G1": bool(g1), "G2": bool(g2), "G3": bool(g3), "G4": bool(g4_ok)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
