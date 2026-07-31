"""E93 -- Is the Goldilocks axis an inverted U, or a floor? Does anything ever sit ABOVE the awake centre?

REGISTERED BEFORE ANY STRATUM IS PLACED. Every table it reads already exists; what has been read of them
is their row counts, their `whole_head_exponent` completeness and their state vocabularies -- no exponent
has been related to any state.

=========================================================================================================
THE CLAIM, AND THE PART OF IT THAT HAS NEVER BEEN TESTED
=========================================================================================================
The Goldilocks framing says consciousness is maximised in a middle zone: wakefulness near an awake
reference centre, sleep and GABAergic anaesthesia displaced in the suppressive direction, and
hyperexcitable states displaced the OTHER way. **The two-armed shape is what makes it "Goldilocks"
rather than "a suppression scale."**

If nothing ever sits above the awake centre, then the coordinate has one arm and a floor, and "just
right" is unearned language for a monotone axis -- the middle would be an ENDPOINT, not an optimum. That
distinction is testable, it decides how the phenomenon may be described in print, and **it has never been
tested here.** This experiment tests it on every state stratum this project can reach.

=========================================================================================================
THE COORDINATE, AND WHY IT IS THIS ONE
=========================================================================================================
    UCE-R  =  0.5 - percentile( whole-head aperiodic exponent | LEMON awake reference )

Each choice is forced by a result in this repository, not by preference:

* **Whole-head, not frontal/posterior.** E92: on the deposit that cleared every gate, DELTA-R =
  -0.0208 [-0.2395, +0.1797] -- the regions are as collinear under anaesthesia as awake, so the second
  coefficient does not earn its place. `uce_v1.py`'s algebra says the same before any data.
* **Percentile, not z-score.** E88: 0 of 6 adult awake pairs transport under z-referencing; the awake
  centre moves up to 1.6 weighted SD depending only on which cohort supplied the reference. E91: rank
  referencing is the ONLY autonomous scheme inside the margin (worst 0.298) and it discriminates BEST
  (mean d +1.126 against the z-scheme's +1.009). **So "zero" here means the awake reference MEDIAN, not
  the awake mean, and that is a different and more defensible landmark.**
* **LEMON as the reference.** 215 healthy adults, purpose-built normative resting-state cohort. Every
  other awake cohort this project holds is a by-product of a task or an anaesthetic.

**THE SIGN IS FLIPPED ON PURPOSE AND THIS IS THE MOST LIKELY PLACE TO GET IT WRONG.** This repository
stores the aperiodic exponent as a POSITIVE steepness, so a HIGHER stored value means a STEEPER spectrum
means MORE suppressed. The Goldilocks convention wants suppressed to be NEGATIVE. Hence `0.5 - percentile`
rather than `percentile - 0.5`. A construction check below asserts the direction on the sleep staircase
before any verdict is read.

=========================================================================================================
PRIMARY
=========================================================================================================
    P1  THE POSITIVE ARM. Across every non-reference stratum, does ANY have a median UCE-R **above zero**
        with a bootstrap interval excluding zero? Clustered on subject/case wherever a subject
        contributes more than one recording.

VERDICT, wrong direction first (rule 37):

    (a) the sleep staircase is NOT monotone (G2 fails)
            -> NOT A DEPTH AXIS. The coordinate does not order states by depth at all, and neither arm of
               Goldilocks is testable with it. ABSENT, not a null.
    (b) at least one stratum sits ABOVE zero, interval excluding it
            -> TWO-SIDED. The positive arm is populated and the inverted-U framing has something to stand
               on. Name the strata; do not generalise beyond them.
    (c) no stratum sits above zero
            -> ONE-SIDED. **The coordinate is a suppression floor.** Wakefulness is the top of the range,
               not the middle of it, and the phenomenon must be described as a one-sided suppressive axis.
               This is the predicted outcome.

PREDICTED: **(c) ONE-SIDED.** Every state this project can reach is either awake or suppressed; the
deposits that might populate a hyperexcitable arm (seizure) are not held here, and the one prior probe
of a positive direction in this programme -- intra-burst content by aetiology -- found the sign REVERSES
between aetiologies rather than pointing one way.

SECONDARY, both reported whatever P1 does:

    P2  IS WAKE A ZONE OR AN ENDPOINT? "Just right" implies the awake distribution is TIGHTER than what
        surrounds it. Compared: the IQR of UCE-R among awake recordings against the IQR within each
        suppressed stratum. **If wake is the WIDEST, "zone" is the wrong word** and the language has to
        change even if the ordering holds.
    P3  WHERE DOES REM FALL? REM is behaviourally unresponsive with vivid report and a wake-like
        desynchronised EEG, so a coordinate tracking CONSCIOUSNESS should put it near the awake centre
        while one tracking AROUSAL should put it with sleep. Prior evidence in this repository points the
        second way and says why: E69 found `exponent_high` places REM with deep sleep in 88.7 % of
        subjects, and E70 measured that placement as **58.7 % attributable to submental muscle** against
        a 27.6 % mechanical placebo. P3 is therefore reported WITH that caveat attached, and a REM
        placement near wake would need a muscle control before it meant anything.

GATES (rule 40), all of which return before P1:

    G1  TRANSPORT HOLDS HERE. eegmmidb -- awake, adult, and NOT the reference -- must have a median UCE-R
        within +-0.1 (percentile units). E91 established rank transport in weighted-SD units; this
        re-establishes it in the units this experiment actually uses, on a cohort the reference never saw.
    G2  MONOTONE STAIRCASE. On Sleep-EDFx, median UCE-R must fall monotonically W > N1 > N2 > N3. REM is
        EXCLUDED from this gate: its placement is the question in P3, and gating on it would assume the
        answer.
    G3  COVERAGE. >= 30 recordings in every stratum reported.
    G4  DIRECTION CHECK. N3's median UCE-R must be NEGATIVE. If the sign convention is inverted this fires
        before any verdict is read, which is the cheapest possible guard against the error this design is
        most exposed to.

SCOPE. This places states on a measurement axis. It is not a claim that any state is or is not conscious,
and a stratum's position says nothing about a patient's experience. The VitalDB strata are BIS bands and
BIS is a device output, not a state label; they are included because they span a depth range no other
deposit here does, and E22/E58 measured that the BIS >= 80 band is 98.2 % facial-EMG artefact, so that
band is reported and explicitly not interpreted.

    python -m bsde.experiments.e93_goldilocks_one_sided
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.experiments.e92_two_region_information_v2 import (state_ds004541,   # noqa: E402
                                                            state_ds005620)

OUT = os.path.join(RESULTS, "e93_goldilocks_one_sided.json")
REFERENCE = "lemon_regional_aperiodic.csv"
MIN_PER_STRATUM = 30
TRANSPORT_MARGIN = 0.10
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


def build_strata():
    """(stratum name) -> (values of the whole-head exponent, cluster ids). Labels PARSED, never
    substring-matched (rule 61)."""
    S = defaultdict(lambda: ([], []))

    def add(name, v, cid):
        if np.isfinite(v):
            S[name][0].append(v)
            S[name][1].append(cid)

    for r in rows_of("eegmmidb_regional_aperiodic.csv"):
        if r.get("status") == "ok":
            add("eegmmidb awake", _f(r["aperiodic_wholehead"]), r.get("subject", ""))

    for tbl, parser, tag in (("ds004541_regional_aperiodic.csv", state_ds004541, "ds004541"),
                             ("ds005620_regional_aperiodic_w20.csv", state_ds005620, "ds005620")):
        for r in rows_of(tbl):
            if r.get("status") != "ok" or r.get("subject") == "sub-02":
                continue
            st = parser(r["recording_id"])
            if st:
                add(f"{tag} {st}", _f(r["aperiodic_wholehead"]), r.get("subject", ""))

    for r in rows_of("sleep_edfx_five_stage.csv"):
        rid = r.get("recording_id", "")
        if "@" not in rid:
            continue
        stage = rid.rsplit("@", 1)[1]
        if stage in ("W", "N1", "N2", "N3", "REM"):
            add(f"sleep {stage}", _f(r.get("whole_head_exponent", "")), r.get("subject", ""))

    for r in rows_of("vitaldb_grid.csv"):
        b = _f(r.get("meta_bis", ""))
        if not np.isfinite(b):
            continue
        band = min(int(b // 20) * 20, 80)
        add(f"vitaldb BIS [{band},{band + 20})", _f(r.get("whole_head_exponent", "")),
            r.get("subject", ""))

    for r in rows_of("dosei_holdout_features.csv"):
        m = _f(r.get("moaas", ""))
        if np.isfinite(m):
            add(f"dosei MOAA/S {int(m)}", _f(r.get("whole_head_exponent", "")), r.get("recording", ""))

    return {k: (np.asarray(v, float), np.asarray(c)) for k, (v, c) in S.items()}


def uce_r(values, ref_sorted):
    """0.5 - percentile in the reference. Stored exponents are POSITIVE steepness, so steeper (more
    suppressed) must map NEGATIVE -- hence the subtraction, not the addition."""
    pct = np.searchsorted(ref_sorted, values, side="left") / max(len(ref_sorted), 1)
    return 0.5 - pct


def boot_median(v, clusters, seed, reps=REPS):
    uniq = np.unique(clusters)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        drawn = rng.choice(uniq, size=uniq.size, replace=True)
        idx = np.concatenate([np.flatnonzero(clusters == g) for g in drawn])
        if idx.size:
            out.append(float(np.median(v[idx])))
    if len(out) < 50:
        return float("nan"), float("nan")
    out = np.sort(out)
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def main() -> int:
    ref_rows = [r for r in rows_of(REFERENCE) if r.get("status") == "ok"]
    ref = np.sort(np.asarray([_f(r["aperiodic_wholehead"]) for r in ref_rows], float))
    ref = ref[np.isfinite(ref)]
    res = {"reference": {"table": REFERENCE, "n": int(ref.size)}, "gates": {}, "strata": {}}
    print(f"reference: {REFERENCE}, n = {ref.size} awake adults")
    if ref.size < 50:
        print("ABSENT: reference too small"); return 2

    strata = build_strata()
    print(f"{len(strata)} strata built\n")
    print(f"{'stratum':<28s} {'n':>5s} {'clusters':>8s} {'median UCE-R':>13s} {'95% CI':>20s} {'IQR':>7s}")
    for name in sorted(strata):
        v, c = strata[name]
        if v.size < MIN_PER_STRATUM:
            print(f"{name:<28s} {v.size:5d}  -- below the {MIN_PER_STRATUM}-recording floor, not reported")
            continue
        u = uce_r(v, ref)
        lo, hi = boot_median(u, c, SEED)
        iqr = float(np.subtract(*np.percentile(u, [75, 25])))
        res["strata"][name] = {"n": int(v.size), "n_clusters": int(np.unique(c).size),
                               "median": float(np.median(u)), "lo": lo, "hi": hi, "iqr": iqr}
        print(f"{name:<28s} {v.size:5d} {np.unique(c).size:8d} {np.median(u):+13.4f} "
              f"[{lo:+8.4f}, {hi:+8.4f}] {iqr:7.4f}")

    S = res["strata"]

    g1 = "eegmmidb awake" in S and abs(S["eegmmidb awake"]["median"]) <= TRANSPORT_MARGIN
    res["gates"]["G1_transport"] = S.get("eegmmidb awake", {}).get("median")
    res["gates"]["G1_pass"] = bool(g1)
    print(f"\nG1 transport   eegmmidb awake median "
          f"{S.get('eegmmidb awake', {}).get('median', float('nan')):+.4f} "
          f"(margin +-{TRANSPORT_MARGIN})   {'PASS' if g1 else 'FAIL'}")

    stair = [S.get(f"sleep {k}", {}).get("median") for k in ("W", "N1", "N2", "N3")]
    g2 = all(x is not None for x in stair) and all(stair[i] > stair[i + 1] for i in range(3))
    res["gates"].update({"G2_staircase": stair, "G2_pass": bool(g2)})
    print(f"G2 staircase   W>N1>N2>N3 medians {['%+.4f' % x if x is not None else 'NA' for x in stair]}"
          f"   {'PASS' if g2 else 'FAIL'}")

    g4 = S.get("sleep N3", {}).get("median", 1.0) < 0
    res["gates"]["G4_pass"] = bool(g4)
    print(f"G4 direction   N3 median {S.get('sleep N3', {}).get('median', float('nan')):+.4f} "
          f"must be negative   {'PASS' if g4 else 'FAIL'}")

    if not (g1 and g2 and g4):
        why = ("the sleep staircase is not monotone -- the coordinate does not order states by depth"
               if not g2 else "transport fails in these units" if not g1 else "the sign convention is inverted")
        print(f"\nGATE FAILED ({why}) -- P1 is not evaluated. ABSENT, not a null (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    above = [k for k, d in S.items()
             if k not in ("eegmmidb awake",) and d["lo"] > 0]
    res["P1_above_zero"] = above

    awake_iqrs = {k: S[k]["iqr"] for k in S if "awake" in k or k == "sleep W"}
    other_iqrs = {k: S[k]["iqr"] for k in S if k not in awake_iqrs}
    widest_awake = max(awake_iqrs.values()) if awake_iqrs else float("nan")
    res["P2"] = {"awake_iqrs": awake_iqrs, "other_iqrs": other_iqrs,
                 "awake_is_tightest": bool(other_iqrs and widest_awake <= min(other_iqrs.values()))}
    print(f"\nP2 zone width  awake IQRs {['%s %.3f' % (k, v) for k, v in awake_iqrs.items()]}")
    print(f"               narrowest non-awake IQR "
          f"{min(other_iqrs.values()) if other_iqrs else float('nan'):.3f}   "
          f"awake tightest: {res['P2']['awake_is_tightest']}")

    rem = S.get("sleep REM", {})
    w, n3 = S.get("sleep W", {}).get("median"), S.get("sleep N3", {}).get("median")
    pos = ((rem.get("median") - w) / (n3 - w)) if (rem and w is not None and n3 is not None and n3 != w) else None
    res["P3_REM"] = {"median": rem.get("median"), "lo": rem.get("lo"), "hi": rem.get("hi"),
                     "position_on_W_to_N3_axis": pos}
    print(f"P3 REM         median {rem.get('median', float('nan')):+.4f} "
          f"[{rem.get('lo', float('nan')):+.4f}, {rem.get('hi', float('nan')):+.4f}], "
          f"position on the W->N3 axis {pos if pos is None else round(pos, 3)}")
    print("               CAVEAT CARRIED: E70 measured REM's placement on a related measure as 58.7 % "
          "submental muscle against a 27.6 % mechanical placebo.")

    if above:
        verdict = (f"TWO-SIDED -- {above} sit ABOVE the awake reference median with intervals excluding "
                   f"zero. The positive arm is populated in these strata and nowhere else; do not "
                   f"generalise past them.")
    else:
        verdict = ("ONE-SIDED -- no stratum sits above the awake reference median. **The coordinate is a "
                   "suppression floor, not an inverted U.** Wakefulness is the TOP of the range this "
                   "project can reach, not the middle of it, so the phenomenon must be described as a "
                   "one-sided suppressive axis and 'just right' is unearned language for it. The deposits "
                   "that could populate a hyperexcitable arm are not held here; this is a statement about "
                   "what has been measured, not a proof that no such arm exists.")
    res["verdict"] = verdict
    print(f"\nVERDICT: {verdict}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
