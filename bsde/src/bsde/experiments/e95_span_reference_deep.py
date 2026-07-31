"""E95 -- The span reference given a DEEP anchor. Third and final pass, with a stopping rule.

REGISTERED AFTER E94 WAS REFUSED AND BECAUSE OF IT. **THIRD AND FINAL PASS AT THIS QUESTION.** E93
established that a percentile reference saturates; E94 tested one remedy and measured how far it got; E95
extends the remedy along the axis E94's own diagnosis named. If G2 fails again, percentile referencing is
recorded as UNABLE to resolve deep states on the deposits this project holds, and the line is closed.

WHAT E94 MEASURED, and it is why this is not a rerun. Adding ds005620's propofol sedation to the reference
cut the extreme-percentile fraction from **0.5168 to 0.2028** and turned the staircase monotone
(W +0.3073, N1 -0.2025, N2 -0.5279, N3 -0.5838) without costing transport (+0.0419 against +0.0651, both
inside the margin). Both co-primaries would have passed. G2 refused it because **N3's interval is
zero-width at the floor -- every N3 recording is still outside the reference's support** -- and G2 was
registered precisely so monotonicity arriving with a saturated bottom could not be credited to the span.

THE ONE INSTRUMENT CHANGE (rule 58): the reference gains **ds004541's post-LOC general anaesthesia**, 62
channels, which E93 placed at the very floor of the awake-only reference and which is therefore deeper
than the sedation anchor E94 used. Nothing else moves -- same test cohorts, same margins, same gates, same
scoring. The change is dictated by E94's measured diagnosis (a sedation anchor cannot support a scale that
must resolve deep NREM), not by a wish for a different answer.

Original E94 header follows, since the design is otherwise unchanged.

E94 -- Rule 62's prescription, tested: does a reference spanning the measured range restore the staircase?

REGISTERED BEFORE ANY SPAN REFERENCE IS BUILT. Every table it reads exists and E93 has already reported
the awake-only arm, which is the comparison; nothing about the span arm has been computed.

=========================================================================================================
THE PROBLEM, IN ONE LINE
=========================================================================================================
E91 found rank/percentile referencing is the only autonomous scheme that transports (worst 0.298 against
the z-scheme's 1.212) and it discriminates best. E93 then placed twenty strata on it and the sleep
staircase collapsed: W +0.4674, N1 -0.2837, **N2 -0.5000, N3 -0.5000** -- both pinned at the 0th
percentile, along with VitalDB's BIS [20,60) bands and all of ds004541's anaesthetised arm.

**So there is a genuine tension and both halves are measured, not asserted: a z-score has dynamic range
and does not transport; a percentile transports and has no dynamic range below its reference.**

Rule 62's prescription is to build the reference over the RANGE YOU INTEND TO MEASURE rather than over the
state you happen to call normal -- the way a growth chart is built from the whole population and not from
the healthy tail. This experiment tests whether that actually works, or whether it buys range by giving
back the origin.

=========================================================================================================
THE TWO REFERENCES
=========================================================================================================
    R-AWAKE   LEMON awake only (215 adults). E93's reference, reproduced here so the comparison is
              like-for-like rather than quoted across experiments.
    R-SPAN    LEMON awake (215) POOLED WITH ds005620 anaesthetised (143). Same percentile machinery; the
              only change is that the reference distribution now has support below wakefulness.

**Neither reference contains any recording from the cohorts it is tested on.** Sleep-EDFx supplies the
staircase and eegmmidb supplies the transport check; neither appears in either reference. That is what
makes this leave-one-out rather than a demonstration.

The suppressed anchor is ds005620 rather than sleep, deliberately: using deep SLEEP to anchor a reference
and then testing the SLEEP staircase would be circular, and the circularity would be invisible in the
output.

=========================================================================================================
CO-PRIMARIES -- both must hold, because either alone is the failure mode of the other
=========================================================================================================
    P1  RANGE.      Under R-SPAN, is the Sleep-EDFx staircase strictly monotone, W > N1 > N2 > N3?
                    Under R-AWAKE it is not (N2 and N3 tie at the floor). REM is excluded, as in E93,
                    because its placement is a separate question and gating on it would assume an answer.
    P2  TRANSPORT.  Under R-SPAN, does awake eegmmidb -- in neither reference -- still sit within +-0.10
                    of the awake landmark?

**The awake landmark moves and that is not a defect.** Under R-AWAKE, 0.5 is the awake median by
construction. Under R-SPAN the reference contains suppressed recordings too, so the awake median sits
higher; the landmark is therefore defined as **the median percentile of the R-SPAN reference's own awake
half**, computed from the reference and not from the test data. P2 measures eegmmidb's distance from THAT.
Getting this wrong would make transport look broken for a bookkeeping reason.

VERDICT, wrong direction first (rule 37):

    (a) P2 fails while P1 passes
            -> RANGE BOUGHT WITH THE ORIGIN. The span reference restores the staircase and loses the
               cross-cohort landmark. That is a TRADE, not a fix, and it must be reported as one: it would
               mean no scheme tested here has both, and the coordinate cannot be both comparable and
               graded.
    (b) P1 fails
            -> SPAN DOES NOT FIX IT. The saturation was not a support problem and the diagnosis in rule 62
               is wrong. Say so.
    (c) both hold
            -> RECOMMENDATION. Build the reference over the measured range; this is the scheme to use, and
               the cost is that the reference now needs suppressed recordings, which an awake-only
               normative cohort cannot supply.

PREDICTED: **(c)**, because the diagnosis is arithmetic rather than empirical -- a percentile saturates
exactly when the reference has no support, and adding support is the direct remedy. Predicting the
comfortable outcome is worth flagging: the informative result here is (a).

GATES (rule 40):
    G1  DISJOINT. No recording in either reference may appear in the staircase or transport cohorts.
        Asserted on subject identifiers, not assumed from the deposit names.
    G2  SUPPORT EXISTS. Under R-SPAN, fewer than 5 % of Sleep-EDFx recordings may land at either extreme
        percentile. **This is the mechanism P1 depends on**, and if it fails while P1 somehow passes, the
        monotonicity came from somewhere else and must not be credited to the span.
    G3  COVERAGE. >= 30 recordings per stage and >= 100 in each reference half.
    G4  DIRECTION. N3 must sit below W under both references, guarding the deliberate sign flip that E93
        also guards.

SCOPE. A measurement-scale question, no outcome consulted. Restoring a monotone staircase would show the
coordinate can ORDER depth; it would say nothing about whether the ordering means anything clinically, and
nothing about consciousness.

    python -m bsde.experiments.e94_span_reference
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

OUT = os.path.join(RESULTS, "e95_span_reference_deep.json")
STAGES = ("W", "N1", "N2", "N3")
MIN_PER_STAGE, MIN_REF_HALF = 30, 100
TRANSPORT_MARGIN = 0.10
EXTREME_MAX_FRAC = 0.05
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


def lemon_awake():
    rs = [r for r in rows_of("lemon_regional_aperiodic.csv") if r.get("status") == "ok"]
    return (np.asarray([_f(r["aperiodic_wholehead"]) for r in rs], float),
            [r.get("subject", "") for r in rs])


def ds005620_anaes():
    rs = [r for r in rows_of("ds005620_regional_aperiodic_w20.csv")
          if r.get("status") == "ok" and state_ds005620(r["recording_id"]) == "anaesthetised"]
    return (np.asarray([_f(r["aperiodic_wholehead"]) for r in rs], float),
            [r.get("subject", "") for r in rs])


def ds004541_anaes():
    """The DEEP anchor E94's diagnosis called for: post-LOC general anaesthesia, 62 channels."""
    rs = [r for r in rows_of("ds004541_regional_aperiodic.csv")
          if r.get("status") == "ok" and r.get("subject") != "sub-02"
          and state_ds004541(r["recording_id"]) == "anaesthetised"]
    return (np.asarray([_f(r["aperiodic_wholehead"]) for r in rs], float),
            [r.get("subject", "") for r in rs])


def eegmmidb_awake():
    rs = [r for r in rows_of("eegmmidb_regional_aperiodic.csv") if r.get("status") == "ok"]
    return (np.asarray([_f(r["aperiodic_wholehead"]) for r in rs], float),
            [r.get("subject", "") for r in rs])


def sleep_stages():
    out = {}
    for r in rows_of("sleep_edfx_five_stage.csv"):
        rid = r.get("recording_id", "")
        if "@" not in rid:
            continue
        st = rid.rsplit("@", 1)[1]
        if st in STAGES or st == "REM":
            out.setdefault(st, ([], []))
            out[st][0].append(_f(r.get("whole_head_exponent", "")))
            out[st][1].append(r.get("subject", ""))
    return {k: (np.asarray(v, float), s) for k, (v, s) in out.items()}


def pct(values, ref_sorted):
    """Percentile of each value in the reference. Higher stored exponent = steeper = more suppressed,
    so the SCORE is 1 - percentile, keeping 'suppressed is low' as in E93."""
    return 1.0 - np.searchsorted(ref_sorted, values, side="left") / max(len(ref_sorted), 1)


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
    la, la_s = lemon_awake()
    da, da_s = ds005620_anaes()
    ea, ea_s = eegmmidb_awake()
    stages = sleep_stages()
    ok = lambda a: a[np.isfinite(a)]                                          # noqa: E731
    ga, ga_s = ds004541_anaes()
    la, da, ea, ga = ok(la), ok(da), ok(ea), ok(ga)
    res = {"gates": {}, "R_AWAKE": {}, "R_SPAN": {}, "R_SPAN_DEEP": {}}
    print(f"LEMON awake {la.size} | ds005620 anaesthetised {da.size} | "
          f"ds004541 anaesthetised (DEEP) {ga.size} | eegmmidb awake {ea.size}")
    for k in STAGES + ("REM",):
        if k in stages:
            print(f"   sleep {k}: {np.isfinite(stages[k][0]).sum()}")

    # G1 disjoint
    ref_subs = set(la_s) | set(da_s) | set(ga_s)
    test_subs = set(ea_s) | {s for k in stages for s in stages[k][1]}
    overlap = sorted(ref_subs & test_subs)
    res["gates"].update({"G1_overlap": overlap, "G1_pass": not overlap})
    print(f"G1 disjoint   {len(overlap)} shared subject ids   {'PASS' if not overlap else 'FAIL'}")

    g3 = (la.size >= MIN_REF_HALF and da.size >= MIN_REF_HALF
          and all(np.isfinite(stages[k][0]).sum() >= MIN_PER_STAGE for k in STAGES if k in stages))
    res["gates"]["G3_pass"] = bool(g3)
    print(f"G3 coverage   {'PASS' if g3 else 'FAIL'}")

    refs = {"R_AWAKE": np.sort(la), "R_SPAN": np.sort(np.concatenate([la, da])),
            "R_SPAN_DEEP": np.sort(np.concatenate([la, da, ga]))}
    # the awake landmark: the median score of the reference's OWN awake half, per reference
    landmarks = {name: float(np.median(pct(la, r))) for name, r in refs.items()}
    print(f"landmarks     R_AWAKE {landmarks['R_AWAKE']:.4f}   R_SPAN {landmarks['R_SPAN']:.4f}")

    for name, ref in refs.items():
        d = {"n_reference": int(ref.size), "landmark": landmarks[name], "stages": {}}
        print(f"\n=== {name} (n={ref.size}) ===")
        for k in STAGES + ("REM",):
            if k not in stages:
                continue
            v, s = stages[k]
            m = np.isfinite(v)
            u = pct(v[m], ref) - landmarks[name]
            lo, hi = boot_median(u, [s[i] for i in np.flatnonzero(m)], SEED)
            d["stages"][k] = {"n": int(m.sum()), "median": float(np.median(u)), "lo": lo, "hi": hi}
            print(f"   {k:4s} n={m.sum():4d}  median {np.median(u):+.4f} [{lo:+.4f}, {hi:+.4f}]")
        meds = [d["stages"][k]["median"] for k in STAGES if k in d["stages"]]
        d["monotone"] = bool(len(meds) == 4 and all(meds[i] > meds[i + 1] for i in range(3)))
        # extreme saturation, on the staircase cohort
        allv = np.concatenate([stages[k][0][np.isfinite(stages[k][0])] for k in STAGES if k in stages])
        p = pct(allv, ref)
        frac = float(np.mean((p <= 1e-12) | (p >= 1.0 - 1e-12)))
        d["extreme_fraction"] = frac
        # transport
        ue = pct(ea, ref) - landmarks[name]
        d["transport_eegmmidb"] = float(np.median(ue))
        print(f"   monotone {d['monotone']}   extreme-percentile fraction {frac:.4f}   "
              f"eegmmidb awake {np.median(ue):+.4f}")
        res[name] = d

    PRIMARY_REF = "R_SPAN_DEEP"
    g2 = res[PRIMARY_REF]["extreme_fraction"] < EXTREME_MAX_FRAC
    g4 = (res[PRIMARY_REF]["stages"]["N3"]["median"] < res[PRIMARY_REF]["stages"]["W"]["median"]
          and res["R_AWAKE"]["stages"]["N3"]["median"] < res["R_AWAKE"]["stages"]["W"]["median"])
    res["gates"].update({"G2_pass": bool(g2), "G4_pass": bool(g4)})
    print(f"\nG2 support    {PRIMARY_REF} extreme fraction {res[PRIMARY_REF]['extreme_fraction']:.4f} "
          f"(< {EXTREME_MAX_FRAC})   {'PASS' if g2 else 'FAIL'}")
    print(f"G4 direction  {'PASS' if g4 else 'FAIL'}")

    if not all(res["gates"][k] for k in ("G1_pass", "G2_pass", "G3_pass", "G4_pass")):
        print("\nGATE FAILED -- no co-primary is evaluated. ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    p1 = res[PRIMARY_REF]["monotone"]
    p2 = abs(res[PRIMARY_REF]["transport_eegmmidb"]) <= TRANSPORT_MARGIN
    print(f"\nP1 range      {PRIMARY_REF} staircase monotone: {p1}   "
          f"(R_AWAKE was {res['R_AWAKE']['monotone']})")
    print(f"P2 transport  eegmmidb awake {res[PRIMARY_REF]['transport_eegmmidb']:+.4f} "
          f"(margin +-{TRANSPORT_MARGIN}): {p2}")

    if p1 and not p2:
        v = ("RANGE BOUGHT WITH THE ORIGIN -- the span reference restores the staircase and loses the "
             "cross-cohort landmark. A TRADE, not a fix: no scheme tested in this project has both, and "
             "the coordinate cannot be simultaneously comparable across cohorts and graded within one.")
    elif not p1:
        v = ("SPAN DOES NOT FIX IT -- adding a deep anchor does not restore the ordering. STOPPING RULE "
             "APPLIES: percentile referencing is recorded as unable to resolve deep states on the "
             "deposits this project holds, and the line is closed.")
    else:
        v = ("RECOMMENDATION -- a reference spanning the measured range restores the staircase AND keeps "
             "the cross-cohort landmark. The cost is that the reference must contain suppressed "
             "recordings, which an awake-only normative cohort cannot supply, so 'normative' has to mean "
             "'spanning the range' rather than 'healthy and awake'.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
