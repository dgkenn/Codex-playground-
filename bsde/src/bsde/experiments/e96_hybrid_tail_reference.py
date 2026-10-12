"""E96 -- Is the transport/range tension fundamental, or an artefact of using only the two extreme tail models?

REGISTERED BEFORE THE HYBRID SCHEME IS SCORED. It reads tables that already exist and whose awake-only and
span-reference behaviour E93-E95 have reported; nothing about a modelled tail has been computed.

**SCOPE NOTE, STATED RATHER THAN SLIPPED THROUGH.** E95's stopping rule closed the SPAN-REFERENCE line:
adding ever-deeper anchors to the same estimator. This is not a fourth reference for that estimator -- it
is an EIGHTH SCHEME in E91's bake-off frame, and it changes the estimator while holding the reference
fixed at LEMON awake. The investigator asked for it explicitly, which is the external reason a closed line
requires.

=========================================================================================================
THE TENSION, AND WHY IT MAY BE AN ARTEFACT
=========================================================================================================
E88: z-scoring does not transport -- 0 of 6 adult awake pairs, the centre moving up to 1.6 SD.
E91: rank transports best of seven schemes and discriminates best.
E93: rank SATURATES -- 97.9 % of N3 recordings lie above the reference's maximum (2.693 median against a
     reference range of [0.371, 1.997]), so 138 of 141 map to the same percentile and their ordering is
     destroyed at the rank step, not at the display step.

So: **rank has transport and no range; z has range and no transport.** But those two are not independent
choices. Rank IS the empirical CDF of the reference. z IS the Gaussian CDF fitted to the reference. They
differ in ONE thing -- the tail model -- and the empirical CDF's tail model is "nothing exists out there",
while the Gaussian's is "a very light tail, everywhere, including in the bulk where you have data".

**Neither is a good model of an EEG aperiodic exponent's tail, and no third option has been tried.** If the
tension is really about the tail, a scheme that keeps the empirical CDF where there IS data and models the
distribution only where there is NOT should have both properties. If it does not, the tension is real.

=========================================================================================================
THE SCHEME
=========================================================================================================
    S8 HYBRID.  Inside the reference's observed range, the empirical percentile -- **identical to S3, and
                G1 asserts that to 1e-9**, so the bulk is not disturbed. Outside it, the survival function
                is continued with an exponential tail fitted to the reference's own extreme decile (a
                generalised Pareto with shape 0, the standard peaks-over-threshold default). The score
                therefore keeps decreasing past the last observed reference value instead of pinning.

Compared against, on identical data: **S1** (z, the UCE v1 scheme), **S3** (rank, E91's winner) and
**S3-SPAN-DEEP** (E95's best reference, carried so the two remedies -- a bigger reference and a modelled
tail -- can be read against each other rather than in separate experiments).

=========================================================================================================
CRITERIA -- all comparisons or structural, NO round-number thresholds (rule 63)
=========================================================================================================
Rule 63 was earned twice today by gates set at `1e-9` and `0.05` that turned out to measure the number
rather than the data. Every criterion below is either a comparison against another scheme on the same data
or a structural property that cannot be tuned:

    C1  RANGE.      Is the Sleep-EDFx staircase W > N1 > N2 > N3 strictly monotone, AND is **N3's
                    bootstrap interval non-degenerate** (width > 0)? A zero-width interval means every
                    recording in the stratum received the same score, which is saturation by definition
                    and needs no threshold to detect.
    C2  TRANSPORT.  Is |awake eegmmidb - the awake landmark| **no worse than S3's** on the same reference?
                    A comparison, not a margin.
    C3  BOTH.       S8 is the answer only if it satisfies C1 AND C2. Either alone is already available:
                    S1 has range, S3 has transport.

VERDICT, wrong direction FIRST (rule 37):

    (a) S8 transports WORSE than S3
            -> THE TAIL MODEL COSTS TRANSPORT. Modelling the tail buys range by reintroducing exactly the
               cross-cohort sensitivity rank was chosen to avoid, and the tension is real rather than an
               artefact of the two extremes. Report as a refutation of this experiment's premise.
    (b) S8 does not satisfy C1
            -> EXTRAPOLATION DOES NOT HELP. The saturation is not a tail-model problem.
    (c) S8 satisfies both
            -> THE TENSION WAS AN ARTEFACT. A hybrid empirical-plus-modelled-tail reference has the
               transport of a percentile and the range of a z-score, and the choice between them was a
               false dichotomy created by only ever trying the two endpoints.

PREDICTED: **(c)**, and it is the comfortable prediction, which is worth flagging -- (a) is the
informative outcome and the one that would settle the question against this design.

GATES (rule 40):
    G1  BULK UNCHANGED. Inside the reference's interquartile range, S8 must equal S3 to 1e-9. (A tolerance
        here is legitimate: the two are the SAME arithmetic on the same inputs, so any difference is a
        coding error, not accumulated float error over a long window -- which is what made E92's 1e-9
        inappropriate.)
    G2  THE TAIL ACTUALLY EXTRAPOLATES. Among test values above the reference maximum, the number of
        DISTINCT S8 scores must equal the number of distinct input values. If two different exponents get
        the same score the tail is not doing its job and C1 cannot be credited to it.
    G3  DISJOINT. No reference subject appears in the staircase or transport cohorts, asserted on ids.
    G4  DIRECTION. N3 below W under every scheme, guarding the sign convention as E93 and E94 do.

SCOPE. A measurement-scale question; no outcome is consulted. A hybrid winning here would say the
coordinate CAN be made simultaneously comparable and graded. It would say nothing about whether the
ordering is clinically meaningful, and nothing about consciousness. And the modelled tail is an
EXTRAPOLATION: it is unverifiable exactly where it is used, which is a permanent limitation of the scheme
and not a defect of this test.

    python -m bsde.experiments.e96_hybrid_tail_reference
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.experiments.e92_two_region_information_v2 import (state_ds004541,   # noqa: E402
                                                            state_ds005620)

OUT = os.path.join(RESULTS, "e96_hybrid_tail_reference.json")
STAGES = ("W", "N1", "N2", "N3")
TAIL_Q = 0.10                      # peaks-over-threshold: the reference's extreme decile
REPS = 4000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def rows_of(name):
    p = os.path.join(RESULTS, name)
    return list(csv.DictReader(open(p, newline=""))) if os.path.exists(p) else []


def col(name, key="aperiodic_wholehead", where=None):
    rs = [r for r in rows_of(name) if r.get("status") == "ok"]
    if where:
        rs = [r for r in rs if where(r)]
    v = np.array([_f(r.get(key, "")) for r in rs], float)
    s = [r.get("subject", "") for r in rs]
    m = np.isfinite(v)
    return v[m], [s[i] for i in np.flatnonzero(m)]


# ---- the four schemes ---------------------------------------------------------------------------------

def s_rank(x, ref):
    """Empirical percentile, then sign-flipped so suppressed (steeper, larger stored value) is low."""
    return 1.0 - np.searchsorted(ref, x, side="left") / max(len(ref), 1)


def s_z(x, ref):
    mu, sd = float(np.mean(ref)), float(np.std(ref, ddof=1))
    return -(x - mu) / (sd if sd > 1e-12 else 1.0)


def s_hybrid(x, ref):
    """Empirical CDF inside the reference's range; exponential (GPD shape-0) tails outside it.

    Upper tail: threshold u = the reference's (1 - TAIL_Q) quantile, scale b = mean(ref[ref>u] - u).
    For x > ref.max the survival function is continued as S(x) = TAIL_Q * exp(-(x-u)/b), which is
    continuous with the empirical curve at u and strictly decreasing thereafter -- so two different inputs
    above the reference maximum can never receive the same score. The lower tail is the mirror image.
    """
    ref = np.asarray(ref, float)
    x = np.asarray(x, float)
    out = s_rank(x, np.sort(ref))
    lo_u = float(np.quantile(ref, TAIL_Q))
    hi_u = float(np.quantile(ref, 1.0 - TAIL_Q))
    hi_b = float(np.mean(ref[ref > hi_u] - hi_u)) if np.any(ref > hi_u) else 1.0
    lo_b = float(np.mean(lo_u - ref[ref < lo_u])) if np.any(ref < lo_u) else 1.0
    hi_b = hi_b if hi_b > 1e-9 else 1.0
    lo_b = lo_b if lo_b > 1e-9 else 1.0
    above = x > ref.max()
    below = x < ref.min()
    # score = 1 - CDF; above the max the survival continues shrinking, so the score goes below 0
    out[above] = TAIL_Q * np.exp(-(x[above] - hi_u) / hi_b)
    out[below] = 1.0 - TAIL_Q * np.exp(-(lo_u - x[below]) / lo_b)
    return out


SCHEMES = {"S1_z": s_z, "S3_rank": s_rank, "S8_hybrid": s_hybrid}


def boot_median(v, subs, seed, reps=REPS):
    subs = np.asarray(subs)
    uniq = np.unique(subs)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        d = rng.choice(uniq, size=uniq.size, replace=True)
        idx = np.concatenate([np.flatnonzero(subs == g) for g in d])
        if idx.size:
            out.append(float(np.median(v[idx])))
    out = np.sort(out)
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def main() -> int:
    la, la_s = col("lemon_regional_aperiodic.csv")
    da, da_s = col("ds005620_regional_aperiodic_w20.csv",
                   where=lambda r: state_ds005620(r["recording_id"]) == "anaesthetised")
    ga, ga_s = col("ds004541_regional_aperiodic.csv",
                   where=lambda r: r.get("subject") != "sub-02"
                   and state_ds004541(r["recording_id"]) == "anaesthetised")
    ea, ea_s = col("eegmmidb_regional_aperiodic.csv")

    stages = {}
    for r in rows_of("sleep_edfx_five_stage.csv"):
        rid = r.get("recording_id", "")
        if "@" not in rid:
            continue
        st = rid.rsplit("@", 1)[1]
        if st in STAGES or st == "REM":
            stages.setdefault(st, ([], []))
            stages[st][0].append(_f(r.get("whole_head_exponent", "")))
            stages[st][1].append(r.get("subject", ""))
    stages = {k: (np.asarray(v, float), s) for k, (v, s) in stages.items()}

    res = {"gates": {}, "schemes": {}}
    print(f"reference LEMON awake n={la.size}, range [{la.min():.3f}, {la.max():.3f}]")
    print(f"eegmmidb awake n={ea.size}; sleep stages "
          f"{ {k: int(np.isfinite(v).sum()) for k, (v, _) in stages.items()} }")

    overlap = sorted((set(la_s) | set(da_s) | set(ga_s))
                     & (set(ea_s) | {s for k in stages for s in stages[k][1]}))
    res["gates"].update({"G3_overlap": overlap, "G3_pass": not overlap})
    print(f"G3 disjoint   {len(overlap)} shared ids   {'PASS' if not overlap else 'FAIL'}")

    ref_sorted = np.sort(la)
    q1, q3 = np.percentile(la, [25, 75])
    allsleep = np.concatenate([stages[k][0][np.isfinite(stages[k][0])] for k in STAGES])
    bulk = allsleep[(allsleep >= q1) & (allsleep <= q3)]
    g1 = bool(bulk.size and np.max(np.abs(s_hybrid(bulk, la) - s_rank(bulk, ref_sorted))) < 1e-9)
    res["gates"]["G1_pass"] = g1
    print(f"G1 bulk       {bulk.size} in-IQR values, hybrid == rank   {'PASS' if g1 else 'FAIL'}")

    tail_vals = np.unique(allsleep[allsleep > la.max()])
    tail_scores = s_hybrid(tail_vals, la)
    g2 = bool(tail_vals.size and np.unique(np.round(tail_scores, 15)).size == tail_vals.size)
    res["gates"].update({"G2_tail_inputs": int(tail_vals.size),
                         "G2_distinct_scores": int(np.unique(np.round(tail_scores, 15)).size),
                         "G2_pass": g2})
    print(f"G2 tail       {tail_vals.size} distinct inputs above the reference max -> "
          f"{np.unique(np.round(tail_scores, 15)).size} distinct scores   {'PASS' if g2 else 'FAIL'}")

    # scheme -> (reference used, landmark, stage medians, transport)
    arms = [("S1_z", la, s_z), ("S3_rank", la, s_rank), ("S8_hybrid", la, s_hybrid),
            ("S3_rank_SPAN_DEEP", np.concatenate([la, da, ga]), s_rank)]
    for name, ref, fn in arms:
        rs = np.sort(ref)
        lm = float(np.median(fn(la, rs if fn is s_rank else ref)))
        d = {"landmark": lm, "n_reference": int(ref.size), "stages": {}}
        print(f"\n=== {name} (reference n={ref.size}) ===")
        for k in STAGES + ("REM",):
            v, s = stages[k]
            m = np.isfinite(v)
            u = fn(v[m], rs if fn is s_rank else ref) - lm
            lo, hi = boot_median(u, [s[i] for i in np.flatnonzero(m)], SEED)
            d["stages"][k] = {"median": float(np.median(u)), "lo": lo, "hi": hi,
                              "width": float(hi - lo)}
            print(f"   {k:4s} median {np.median(u):+.4f} [{lo:+.4f}, {hi:+.4f}]  width {hi - lo:.6f}")
        meds = [d["stages"][k]["median"] for k in STAGES]
        d["monotone"] = bool(all(meds[i] > meds[i + 1] for i in range(3)))
        d["n3_width"] = d["stages"]["N3"]["width"]
        d["transport"] = float(np.median(fn(ea, rs if fn is s_rank else ref)) - lm)
        d["C1_range"] = bool(d["monotone"] and d["n3_width"] > 0)
        print(f"   monotone {d['monotone']}   N3 interval width {d['n3_width']:.6f}   "
              f"transport {d['transport']:+.4f}   C1 {d['C1_range']}")
        res["schemes"][name] = d

    S = res["schemes"]
    c2 = abs(S["S8_hybrid"]["transport"]) <= abs(S["S3_rank"]["transport"]) + 1e-12
    g4 = all(S[n]["stages"]["N3"]["median"] < S[n]["stages"]["W"]["median"] for n in S)
    res["gates"]["G4_pass"] = bool(g4)
    print(f"\nG4 direction  {'PASS' if g4 else 'FAIL'}")
    print(f"C1 range      S8 {S['S8_hybrid']['C1_range']} | S3 {S['S3_rank']['C1_range']} | "
          f"S1 {S['S1_z']['C1_range']} | S3-span-deep {S['S3_rank_SPAN_DEEP']['C1_range']}")
    print(f"C2 transport  S8 {S['S8_hybrid']['transport']:+.4f} vs S3 "
          f"{S['S3_rank']['transport']:+.4f} (S1 {S['S1_z']['transport']:+.4f})   "
          f"S8 no worse than S3: {c2}")

    if not all(res["gates"][k] for k in ("G1_pass", "G2_pass", "G3_pass", "G4_pass")):
        print("\nGATE FAILED -- no verdict. ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    if not c2:
        v = (f"THE TAIL MODEL COSTS TRANSPORT -- S8's awake landmark offset is "
             f"{S['S8_hybrid']['transport']:+.4f} against S3's {S['S3_rank']['transport']:+.4f}. "
             f"Modelling the tail buys range by reintroducing the cross-cohort sensitivity rank was "
             f"chosen to avoid. The tension is real, not an artefact of the two extremes.")
    elif not S["S8_hybrid"]["C1_range"]:
        v = ("EXTRAPOLATION DOES NOT HELP -- the hybrid still fails the range criterion, so the "
             "saturation is not a tail-model problem.")
    else:
        v = (f"THE TENSION WAS AN ARTEFACT -- S8 satisfies BOTH criteria on one awake-only reference: "
             f"staircase monotone with a non-degenerate N3 interval ({S['S8_hybrid']['n3_width']:.6f}), "
             f"and transport {S['S8_hybrid']['transport']:+.4f} against rank's "
             f"{S['S3_rank']['transport']:+.4f}. The choice between a percentile and a z-score was a "
             f"false dichotomy created by only ever trying the two endpoint tail models. **The modelled "
             f"tail is an EXTRAPOLATION and is unverifiable exactly where it is used** -- a permanent "
             f"limitation of the scheme, not of this test.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
