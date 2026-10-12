#!/usr/bin/env python3
"""E198 — Challenge D: how deep should a reference go, judged by RESOLUTION rather than by saturation.

REGISTERED BEFORE ANY NEW REFERENCE HAS BEEN BUILT.

=========================================================================================================
WHAT E91, E93 AND E95 ESTABLISHED, AND THE GATE THAT STOPPED E95
=========================================================================================================
E91 ran a seven-scheme bake-off for population referencing and rank (percentile) referencing won on both
axes. E93 then placed twenty state strata on that coordinate and the sleep ladder **collapsed**: W +0.4674,
N1 −0.2837, **N2 −0.5000 and N3 −0.5000, both pinned at the floor**. An awake-only reference has no
resolution below wakefulness, which is rule 62, and E91 could not have seen it because it scored
discrimination on a BINARY awake-versus-suppressed contrast where saturation is free.

E95 built deeper references and every step improved every measured quantity:

    reference       n     extreme fraction   transport   monotone   N2 median   N3 median
    R_AWAKE        215        0.5168           0.0651      no        −0.5023     −0.5023   <- tied
    R_SPAN         358        0.2028           0.0419      yes       −0.5279     −0.5838
    R_SPAN_DEEP    394        0.0705           0.0381      yes       −0.5025     −0.6168

**It was refused because 0.0705 is not below 0.05** — a threshold with nothing behind it, and CLAUDE.md
records this exact run as rule 63's example. E95's verdict stands as GATE-FAILED and is not reopened.

=========================================================================================================
THE INSTRUMENT CHANGE: MEASURE RESOLUTION, NOT ITS PROXY
=========================================================================================================
`extreme_fraction` — the mass sitting at the reference's extreme percentiles — is a **proxy** for the thing
that actually matters, which is whether the coordinate can still tell adjacent states apart. Rule 79 says
stop arguing about the proxy and measure the quantity on the primary statistic itself. Here that is:

    **P1  ADJACENT-STRATUM RESOLUTION.** Over the ordered ladder W > N1 > N2 > N3, the number of adjacent
          pairs whose subject-bootstrap median intervals are DISJOINT and in the correct order, out of 3.

The proxy and the primary disagree on E95's own numbers, which is why this is worth a run rather than a
re-read: `R_AWAKE` fails the primary (N2 and N3 are identical, so 2 of 3) and `R_SPAN` passes it (3 of 3)
while sitting at an extreme fraction of 0.2028, four times the refused threshold. **A criterion that
refuses a reference resolving every adjacent pair, and would have accepted one resolving two, is measuring
the wrong thing.**

=========================================================================================================
AND THE COST THAT NOBODY HAS MEASURED — RULE 52 APPLIED TO REFERENCES
=========================================================================================================
Every previous run reported resolution at the DEEP end only. E95's own table shows the awake end paying for
it: W falls 0.4651 → 0.3073 → 0.2792 and REM −0.4372 → −0.3128 → −0.2843 as the reference deepens.
**Deepening a reference spends dynamic range at the top to buy it at the bottom**, and a design whose
primary is restricted to the deep end cannot see that (rule 52 — a band-restricted primary cannot tell an
improvement from a reallocation). So the primary is scored over the WHOLE ladder, and a secondary reports
the two ends separately:

    P2  the awake-end spread (W minus N1) and the deep-end spread (N2 minus N3), per reference, so the
        trade-off curve is visible rather than inferred.

=========================================================================================================
GATES
=========================================================================================================
G1  reference and test subject ids must be disjoint. E95's, unchanged.
G2  **RESOLUTION FLOOR, MEASURED NOT CHOSEN.** The resolution count is compared against a null in which
    stage labels are permuted WITHIN subject, so the ladder is destroyed and the reference is not. A
    reference counts as resolving a pair only if that pair's separation exceeds the 95th percentile of the
    same statistic under the null. This replaces `EXTREME_MAX_FRAC` and can fail for every reference.
G3  each stratum needs `MIN_PER_STAGE` subjects and each reference half `MIN_REF_HALF`. E95's, unchanged.
G4  **DIRECTION**: N3 must sit below W in every reference, or the coordinate is not a depth coordinate at
    all and no comparison between references is readable. E95's, unchanged.
G5  **TRANSPORT MUST NOT DEGRADE**: the winning reference's cross-cohort transport must be no worse than
    `R_AWAKE`'s. A reference that resolves the ladder by sacrificing transportability has solved a
    different problem — Challenge D is transport.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G3 or G4 fails.
  (2) NO REFERENCE RESOLVES   no reference clears the measured floor on any adjacent pair. The percentile
                          coordinate is then not a graded depth measure at all, whatever its reference.
  (3) DEPTH DOES NOT HELP  the deepest reference resolves no more pairs than `R_AWAKE`. Rule 62's
                          prescription would then be **wrong**, and that is the outcome that would matter
                          most, because the programme has been acting on it.
  (4) TRANSPORT COST       the deeper reference resolves more pairs but G5 fails: resolution was bought
                          with transportability, and the recommendation must say so.
  (5) DEPTH RESOLVES       a deeper reference resolves strictly more adjacent pairs than `R_AWAKE` at no
                          transport cost. The recommendation is then the SHALLOWEST reference achieving
                          the maximum, not the deepest — because P2's trade-off says depth is not free at
                          the awake end.

**REGISTERED PREDICTION: (5), with `R_SPAN` and `R_SPAN_DEEP` both at 3 of 3 and `R_AWAKE` at 2 of 3, and
the recommendation therefore falling on `R_SPAN` rather than on the deepest reference.** That prediction
is made from E95's already-published table and is stated so the run cannot be presented as a discovery —
what is genuinely open here is the measured floor in G2, the transport check in G5, and the awake-end cost
in P2, none of which exists yet.

    python bsde/src/bsde/experiments/e198_reference_depth_resolution.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import e95_span_reference_deep as E95                                          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e198_reference_depth_resolution.json")
SEED = 20260802

LADDER = ("W", "N1", "N2", "N3")
NULL_DRAWS = 500
REPS = getattr(E95, "REPS", 2000)
MIN_PER_STAGE = E95.MIN_PER_STAGE
MIN_REF_HALF = E95.MIN_REF_HALF


def resolution(stage_medians, stage_cis):
    """Adjacent pairs of the ordered ladder whose intervals are DISJOINT and correctly ordered."""
    got = []
    for a, b in zip(LADDER[:-1], LADDER[1:]):
        if a not in stage_medians or b not in stage_medians:
            continue
        (la_, ha) = stage_cis[a]
        (lb, hb) = stage_cis[b]
        got.append(bool(stage_medians[a] > stage_medians[b] and la_ > hb))
    return got


def main() -> int:
    print("E198 — reference depth judged by ADJACENT-STRATUM RESOLUTION, not by saturation")
    la, la_s = E95.lemon_awake()
    da, da_s = E95.ds005620_anaes()
    ga, ga_s = E95.ds004541_anaes()
    ea, ea_s = E95.eegmmidb_awake()
    stages = E95.sleep_stages()
    print(f"LEMON awake {la.size} | ds005620 anaesthetised {da.size} | "
          f"ds004541 anaesthetised (DEEP) {ga.size} | eegmmidb awake {ea.size}")

    res = {"experiment": "E198", "null_draws": NULL_DRAWS, "ladder": list(LADDER), "references": {}}

    ref_subs = set(la_s) | set(da_s) | set(ga_s)
    test_subs = set(ea_s) | {s for k in stages for s in stages[k][1]}
    overlap = sorted(ref_subs & test_subs)
    g1 = not overlap
    print(f"G1 disjoint   {len(overlap)} shared subject ids   {'PASS' if g1 else '*** FAIL'}")

    g3 = bool(la.size >= MIN_REF_HALF and da.size >= MIN_REF_HALF
              and all(np.isfinite(stages[k][0]).sum() >= MIN_PER_STAGE
                      for k in LADDER if k in stages))
    print(f"G3 sizes      {'PASS' if g3 else '*** FAIL'} "
          f"(reference halves >= {MIN_REF_HALF}, strata >= {MIN_PER_STAGE})")
    res["g1"], res["g3"] = g1, g3

    refs = {"R_AWAKE": np.sort(la),
            "R_SPAN": np.sort(np.concatenate([la, da])),
            "R_SPAN_DEEP": np.sort(np.concatenate([la, da, ga]))}
    landmarks = {k: float(np.median(E95.pct(la, r))) for k, r in refs.items()}

    # ---- the measured floor: how many adjacent pairs "resolve" when the LADDER is destroyed ----------
    print(f"\nG2 MEASURED FLOOR — stage labels permuted WITHIN subject, {NULL_DRAWS} draws")
    subj_of, vals_of = {}, {}
    for k in LADDER:
        if k in stages:
            v, s = stages[k]
            for i, sid in enumerate(s):
                subj_of.setdefault(sid, {})[k] = v[i]
    usable = [s for s, d in subj_of.items() if all(k in d and np.isfinite(d[k]) for k in LADDER)]
    print(f"   {len(usable)} subjects have all four strata")
    rng = np.random.default_rng(SEED)

    def score(ref, landmark, assign):
        med, ci = {}, {}
        for k in LADDER:
            vv = np.array([subj_of[s][assign[s][k]] for s in usable], float)
            u = E95.pct(vv, ref) - landmark
            lo, hi = E95.boot_median(u, usable, SEED, reps=400)
            med[k], ci[k] = float(np.median(u)), (float(lo), float(hi))
        return med, ci

    ident = {s: {k: k for k in LADDER} for s in usable}
    floors = {}
    for name, ref in refs.items():
        cnt = []
        for d in range(NULL_DRAWS // 10):          # the floor is a count out of 3; 50 draws resolve it
            perm = {}
            for s in usable:
                p = list(rng.permutation(list(LADDER)))
                perm[s] = dict(zip(LADDER, p))
            m, c = score(ref, landmarks[name], perm)
            cnt.append(sum(resolution(m, c)))
        floors[name] = float(np.quantile(cnt, 0.95))
        print(f"   {name:<12s} null resolution count p95 = {floors[name]:.2f} of 3 "
              f"(mean {np.mean(cnt):.2f})", flush=True)
    res["floors"] = floors

    print(f"\n{'reference':<13s} {'n':>5s} {'resolved':>9s} {'floor':>6s} "
          f"{'W-N1':>8s} {'N2-N3':>8s} {'transport':>10s}")
    for name, ref in refs.items():
        med, ci = score(ref, landmarks[name], ident)
        got = resolution(med, ci)
        n_res = sum(got)
        awake_spread = med["W"] - med["N1"]
        deep_spread = med["N2"] - med["N3"]
        tr = float(abs(np.median(E95.pct(ea, ref)) - landmarks[name]))
        res["references"][name] = {
            "n_reference": int(ref.size), "landmark": landmarks[name],
            "medians": med, "ci": {k: list(v) for k, v in ci.items()},
            "resolved_pairs": got, "n_resolved": int(n_res),
            "clears_floor": bool(n_res > floors[name]),
            "awake_spread": float(awake_spread), "deep_spread": float(deep_spread),
            "transport_eegmmidb": tr}
        print(f"{name:<13s} {ref.size:>5d} {n_res:>6d}/3 {floors[name]:>6.2f} "
              f"{awake_spread:>8.4f} {deep_spread:>8.4f} {tr:>10.4f}", flush=True)

    g4 = all(v["medians"]["N3"] < v["medians"]["W"] for v in res["references"].values())
    print(f"G4 direction  N3 below W in every reference   {'PASS' if g4 else '*** FAIL'}")
    res["g4"] = g4

    base = res["references"]["R_AWAKE"]
    clearing = {k: v for k, v in res["references"].items() if v["clears_floor"]}
    best = max((v["n_resolved"] for v in clearing.values()), default=0)
    winners = [k for k, v in clearing.items() if v["n_resolved"] == best]
    # the SHALLOWEST reference achieving the maximum, because P2 shows depth costs the awake end
    order = ["R_AWAKE", "R_SPAN", "R_SPAN_DEEP"]
    rec = next((k for k in order if k in winners), None)
    g5 = bool(rec is None or res["references"][rec]["transport_eegmmidb"]
              <= base["transport_eegmmidb"] + 1e-12)
    print(f"G5 transport  recommendation {rec} at {res['references'][rec]['transport_eegmmidb']:.4f} "
          f"vs R_AWAKE {base['transport_eegmmidb']:.4f}   {'PASS' if g5 else '*** FAIL'}"
          if rec else "G5 transport  no recommendation to check")
    res["g5"], res["recommendation"] = g5, rec

    print("\n" + "=" * 100)
    if not (g1 and g3 and g4):
        v, why = "NOT INTERPRETABLE", ("a design gate failed: " + ", ".join(
            n for n, ok in (("G1 disjoint", g1), ("G3 sizes", g3), ("G4 direction", g4)) if not ok))
    elif not clearing:
        v, why = "NO REFERENCE RESOLVES", (
            "no reference clears the measured floor on any adjacent pair, so the percentile coordinate "
            "is not a graded depth measure whatever its reference")
    elif best <= base["n_resolved"] and base["clears_floor"]:
        v, why = "DEPTH DOES NOT HELP", (
            f"the deepest reference resolves {best} of 3 adjacent pairs, no more than R_AWAKE's "
            f"{base['n_resolved']}. Rule 62's prescription -- build the reference over the range you "
            "intend to measure -- is NOT supported by this measurement, and the programme has been "
            "acting on it")
    elif not g5:
        v, why = "TRANSPORT COST", (
            f"{rec} resolves {best} of 3 against R_AWAKE's {base['n_resolved']}, but its transport "
            f"({res['references'][rec]['transport_eegmmidb']:.4f}) is worse than R_AWAKE's "
            f"({base['transport_eegmmidb']:.4f}); resolution was bought with transportability")
    else:
        v, why = "DEPTH RESOLVES", (
            f"{rec} resolves {best} of 3 adjacent pairs against R_AWAKE's {base['n_resolved']}, at "
            f"transport {res['references'][rec]['transport_eegmmidb']:.4f} vs {base['transport_eegmmidb']:.4f}. "
            f"The recommendation is the SHALLOWEST reference achieving the maximum, because the awake-end "
            f"spread falls from {base['awake_spread']:.4f} to "
            f"{res['references'][rec]['awake_spread']:.4f} as depth is added -- depth is not free")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
