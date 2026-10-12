#!/usr/bin/env python3
"""E215 — the FORWARD test E211 declared unavailable: does the reference recommendation hold on a cohort
from a different deposit, montage and population?

REGISTERED BEFORE ITS DATA EXISTS. The capslpdb extraction that feeds this file is running as it is
written and no row of it has been read.

=========================================================================================================
WHAT E211 ESTABLISHED, AND THE EXACT SENTENCE IT COULD NOT WRITE
=========================================================================================================
E198 recommended `R_SPAN` — a normative reference built from awake LEMON values PLUS anaesthetised
ds005620 values — over the awake-only `R_AWAKE`, because an awake-only reference has no resolution below
wakefulness (its deep-end spread is exactly 0.0000: N2 and N3 land on the identical value, which is
saturation rather than noise). E211 then showed the recommendation is about the SCHEME and not about the
particular anaesthetised subjects: both disjoint halves of them reproduce 3 of 3 adjacent strata against
R_AWAKE's 2 of 3.

Both results are **internal**. E211 said so and recorded the reason rather than working around it:

    *a genuine FORWARD test of the recommendation on a new cohort is not available with local data.*

A normative reference's entire claim is that it transports to people who were not in it. Until it is
scored on a cohort from a different deposit, a different montage and a different population, everything
above is consistency.

    **P1  On capslpdb — 108 subjects across eight diagnostic groups plus healthy controls, a clinical PSG
          montage, none of them in any reference — does R_SPAN resolve MORE adjacent sleep strata than
          R_AWAKE, reproducing E198's ordering?**

=========================================================================================================
WHY capslpdb AND NOT sleep-edfx
=========================================================================================================
Sleep-EDF Expanded is bigger, cleaner and better known, and it is **disqualified**: `e95_span_reference_deep
.sleep_stages()` already reads it, so it IS the ladder E198 and E211 resolve. Scoring a recommendation on
its own evaluation cohort would be the circularity E211 declined. Recorded because the deposit looks ideal
on every axis a dataset search scores, and only this project's own record disqualifies it — rule 50's
corollary, that an internal record is a source like any other.

capslpdb differs from the evaluation ladder on every axis that matters for a transport claim: different
deposit, different scoring vocabulary (R&K S1-S4 rather than AASM N1-N3), clinical PSG bipolar montage
rather than a research cap, and a population selected for sleep pathology rather than health.

**THE LADDER MAPPING IS DECLARED HERE, BEFORE THE DATA IS READ.** R&K splits deep sleep into S3 and S4
where AASM merges them into N3, so:

    W -> W      S1 -> N1      S2 -> N2      S3 and S4 pooled -> N3

This is the standard correspondence and is not a choice made to help any hypothesis; it is stated in
advance because it is the only degree of freedom in constructing the ladder.

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE: at least `MIN_RECORDS` records carrying all four mapped strata.
G2  **ALIGNMENT.** The scoring is wall-clock text and the signal is an EDF with its own start time, so the
    stage labels are only meaningful if the two were aligned correctly. The extractor writes its own
    control into every row — mean relative delta power in S3+S4 minus that in W — and a record whose
    alignment is scrambled cannot produce a positive one. Records with a control at or below zero are
    EXCLUDED AND COUNTED, never silently dropped (rules 14, 27, 65). This is a DIRECTIONAL check, not a
    calibrated one: the sign is predicted by physiology rather than chosen, but no floor is claimed for
    the magnitude, and that limitation is stated rather than papered over.
G3  **RANGE, NOT SATURATION** (rule 62). A percentile coordinate is only informative inside the support of
    its reference. If the capslpdb values fall wholly outside the reference's range they all map to 0 or 1
    and the comparison is vacuous — and this is a live risk here, because a bipolar clinical montage is not
    the montage either reference was built on. The fraction of values at an extreme percentile is reported
    for BOTH references and must be below `MAX_EXTREME` for the run to be readable.
G4  **NULL FLOOR**, recomputed exactly as E198 and E211 did: stage labels permuted WITHIN record. A
    reference whose null already resolves adjacent pairs is refused.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3 or G4 fails.
  (2) REVERSED            R_AWAKE resolves MORE strata than R_SPAN on this cohort. The recommendation is
                          refuted by its first forward test, and that is reported as its own outcome and
                          not as a weak version of anything.
  (3) NEITHER RESOLVES    both resolve 0 or 1 pairs. The coordinate does not transport to this deposit at
                          all — a montage or population failure rather than a verdict on the reference —
                          and it is reported separately because confusing it with (4) would be the
                          discrimination-versus-equivalence error.
  (4) NO ADVANTAGE        both resolve equally and at least 2. The scheme's advantage does not reproduce
                          forward, and E198's recommendation must carry that.
  (5) FORWARD-CONFIRMED   R_SPAN resolves strictly more than R_AWAKE.

**REGISTERED PREDICTION: (5) FORWARD-CONFIRMED, held with real uncertainty, and (3) is the outcome I would
bet on second.** The mechanism behind R_AWAKE's failure is structural — an awake-only reference has no
values below wakefulness, so anything below wakefulness saturates at its floor — and structural facts
usually travel. What may not travel is the coordinate itself: `whole_head_exponent` on 13 bipolar clinical
derivations is not obviously the same measurement as on a research cap, which is rule 60 run in reverse and
exactly what G3 exists to detect. **If (3) comes back it is a finding about montage transportability and
not a failure of this experiment**, and it would matter more to the programme than a confirmation, because
every normative claim this project makes assumes the measurement survives a change of montage.

**SCOPE.** This tests the ORDERING of two references on a new cohort. It does not test absolute
calibration, and it cannot: no capslpdb subject has an anaesthetic exposure, so the deep end of the
reference is never exercised by this cohort.

    python bsde/src/bsde/experiments/e215_reference_forward_test.py
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import e95_span_reference_deep as E95                                          # noqa: E402
from e198_reference_depth_resolution import LADDER, resolution                 # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e215_reference_forward_test.json")
SHARDS = os.path.join(RESULTS, "capslpdb_stages.s*.csv")

SEED = 20260802
NULL_DRAWS = 60
MIN_RECORDS = 30
MAX_EXTREME = 0.50
STAGE_MAP = {"W": "W", "S1": "N1", "S2": "N2", "S3": "N3", "S4": "N3"}
FEATURE = "whole_head_exponent"


def load_capslpdb():
    """Per record, the mapped ladder value for each stratum, plus its alignment control.

    S3 and S4 are pooled into N3 by averaging, which is the R&K to AASM correspondence declared in the
    docstring before any row was read. De-duplicated on (record, stage) at load, because more than one
    writer has appended to a shard file in this project before (rule 56).
    """
    seen, rows = set(), []
    for p in sorted(glob.glob(SHARDS)):
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                k = (r.get("record", ""), r.get("stage", ""))
                if not k[1] or k in seen:
                    continue
                seen.add(k)
                rows.append(r)
    by = {}
    for r in rows:
        st = STAGE_MAP.get(r["stage"])
        if st is None:
            continue
        try:
            v = float(r[FEATURE])
            c = float(r["delta_ratio_deep_minus_wake"])
        except Exception:
            continue
        if not np.isfinite(v):
            continue
        d = by.setdefault(r["record"], {"vals": {}, "ctrl": c})
        d["vals"].setdefault(st, []).append(v)
    out = {}
    for rec, d in by.items():
        out[rec] = {"ctrl": d["ctrl"],
                    "vals": {k: float(np.mean(v)) for k, v in d["vals"].items()}}
    return out, len(rows)


def main() -> int:
    print("E215 — the FORWARD test: does R_SPAN beat R_AWAKE on a cohort in NO reference?")
    recs, n_rows = load_capslpdb()
    print(f"   {n_rows} extracted rows over {len(recs)} records")

    bad = sorted(r for r, d in recs.items() if not (np.isfinite(d["ctrl"]) and d["ctrl"] > 0))
    print(f"   G2 ALIGNMENT: {len(bad)} records excluded for a non-positive control"
          + (f" ({', '.join(bad[:8])}{'...' if len(bad) > 8 else ''})" if bad else ""))
    keep = {r: d for r, d in recs.items() if r not in bad}
    usable = sorted(r for r, d in keep.items() if all(k in d["vals"] for k in LADDER))
    print(f"   {len(usable)} records carry all four mapped strata")
    ctrls = np.array([keep[r]["ctrl"] for r in usable], float)
    if ctrls.size:
        print(f"   alignment control over the kept records: median {np.median(ctrls):+.4f}  "
              f"range [{ctrls.min():+.4f}, {ctrls.max():+.4f}]")
    g1 = bool(len(usable) >= MIN_RECORDS)
    g2 = bool(len(usable) > 0)
    print(f"G1 COVERAGE >= {MIN_RECORDS} records   {'PASS' if g1 else '*** FAIL'}")

    la, _ = E95.lemon_awake()
    da, _ = E95.ds005620_anaes()
    refs = {"R_AWAKE": np.sort(la), "R_SPAN": np.sort(np.concatenate([la, da]))}
    landmarks = {k: float(np.median(E95.pct(la, r))) for k, r in refs.items()}
    print(f"   references: R_AWAKE {refs['R_AWAKE'].size} values, R_SPAN {refs['R_SPAN'].size}")

    def score(ref, landmark, assign):
        med, ci = {}, {}
        for k in LADDER:
            vv = np.array([keep[r]["vals"][assign[r][k]] for r in usable], float)
            u = E95.pct(vv, ref) - landmark
            lo, hi = E95.boot_median(u, usable, SEED, reps=400)
            med[k], ci[k] = float(np.median(u)), (float(lo), float(hi))
        return med, ci

    ident = {r: {k: k for k in LADDER} for r in usable}
    res = {"experiment": "E215", "n_rows": n_rows, "n_records": len(recs),
           "n_excluded_alignment": len(bad), "excluded_alignment": bad,
           "n_usable": len(usable), "references": {}}

    print(f"\n{'reference':<10s} {'n_ref':>6s} {'resolved':>9s} {'floor':>6s} {'extreme':>8s} "
          f"{'W-N1':>8s} {'N2-N3':>8s}")
    extremes = {}
    for name, ref in refs.items():
        allv = np.array([keep[r]["vals"][k] for r in usable for k in LADDER], float)
        p = E95.pct(allv, ref)
        extremes[name] = float(np.mean((p <= 0.0) | (p >= 1.0)))
        cnt = []
        for d in range(NULL_DRAWS):
            g = np.random.default_rng(SEED + 700 + d)
            pm = {r: dict(zip(LADDER, list(g.permutation(list(LADDER))))) for r in usable}
            m_, c_ = score(ref, landmarks[name], pm)
            cnt.append(sum(resolution(m_, c_)))
        floor = float(np.quantile(cnt, 0.95))
        med, ci = score(ref, landmarks[name], ident)
        got = resolution(med, ci)
        res["references"][name] = {"n_reference": int(ref.size), "n_resolved": int(sum(got)),
                                   "floor": floor, "extreme_fraction": extremes[name],
                                   "resolved_pairs": got, "medians": med,
                                   "awake_spread": float(med["W"] - med["N1"]),
                                   "deep_spread": float(med["N2"] - med["N3"])}
        print(f"{name:<10s} {ref.size:>6d} {sum(got):>6d}/3 {floor:>6.2f} {extremes[name]:>8.4f} "
              f"{med['W'] - med['N1']:>8.4f} {med['N2'] - med['N3']:>8.4f}", flush=True)

    g3 = all(v <= MAX_EXTREME for v in extremes.values())
    g4 = all(v["floor"] < 1.0 for v in res["references"].values())
    print(f"G3 RANGE not saturation (extreme fraction <= {MAX_EXTREME})   "
          f"{'PASS' if g3 else '*** FAIL'}")
    print(f"G4 nulls resolve nothing   {'PASS' if g4 else '*** FAIL'}")
    res["g1"], res["g2"], res["g3"], res["g4"] = g1, g2, g3, g4

    a = res["references"]["R_AWAKE"]["n_resolved"]
    s = res["references"]["R_SPAN"]["n_resolved"]
    print("\n" + "=" * 100)
    if not (g1 and g2 and g3 and g4):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1 coverage", g1), ("G2 alignment", g2),
                            ("G3 range", g3), ("G4 null floor", g4)) if not ok))
    elif a > s:
        v_, why = "REVERSED", (
            f"the awake-only reference resolves MORE than R_SPAN on this cohort ({a} vs {s} of 3). E198's "
            "recommendation is refuted by its first forward test")
    elif max(a, s) <= 1:
        v_, why = "NEITHER RESOLVES", (
            f"both references resolve at most one adjacent pair ({a} and {s} of 3). The coordinate does "
            "not transport to this deposit at all, which is a montage or population finding rather than a "
            "verdict on either reference, and must not be read as the two being equivalent")
    elif a == s:
        v_, why = "NO ADVANTAGE", (
            f"both references resolve {a} of 3. The scheme's advantage, which held internally in E198 and "
            "survived E211's split-half, does NOT reproduce on a cohort in no reference")
    else:
        v_, why = "FORWARD-CONFIRMED", (
            f"R_SPAN resolves {s} of 3 against R_AWAKE's {a} on {len(usable)} records from a different "
            "deposit, montage and population, none of them in either reference. The recommendation "
            "transports")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print("SCOPE: this tests the ORDERING of two references on a new cohort, not absolute calibration,\n"
          "  and it cannot test the deep end of the reference because no capslpdb subject has an\n"
          "  anaesthetic exposure. G2 is a DIRECTIONAL alignment check with no calibrated floor.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
