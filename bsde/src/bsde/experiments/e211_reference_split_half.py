#!/usr/bin/env python3
"""E211 — is E198's reference recommendation a property of the SCHEME or of its particular subjects?

REGISTERED BEFORE ANY SPLIT HAS BEEN DRAWN.

=========================================================================================================
WHAT E198 RECOMMENDED, AND THE QUESTION IT LEFT OPEN
=========================================================================================================
E198 measured adjacent-stratum resolution on the sleep ladder W > N1 > N2 > N3, against a floor measured
by within-subject stage permutation (95th percentile 0.00):

    R_AWAKE      215 reference values   resolves **2 of 3**   awake-end spread 0.7674   deep-end 0.0000
    R_SPAN       358                    resolves **3 of 3**                  0.5223            0.0559
    R_SPAN_DEEP  394                    resolves **3 of 3**                  0.4746            0.1142

R_AWAKE fails because N2 and N3 are *identical* on it — an awake-only reference has no resolution below
wakefulness. The recommendation is **R_SPAN**, the shallowest reference achieving the maximum, because
depth is not free: it spends awake-end range to buy deep-end range.

**What that cannot tell us is whether R_SPAN's advantage is a property of ADDING ANAESTHETISED DATA or of
the particular anaesthetised subjects that happened to be in it.** A reference is a normative object
intended for reuse on people who were not in it, so a recommendation that depends on its own constituents
is not a recommendation.

    **P1  Rebuild R_SPAN from two DISJOINT halves of its anaesthetised subjects and re-measure
          adjacent-stratum resolution on the unchanged sleep ladder. Both halves must reproduce
          R_SPAN's count for the recommendation to be about the scheme.**

=========================================================================================================
WHY THIS IS NOT CIRCULAR, AND WHY THE FORWARD TEST IS NOT AVAILABLE
=========================================================================================================
The evaluation cohort is the sleep ladder, which is in no reference. The only local cohorts carrying the
referenced feature (`aperiodic_wholehead`) are LEMON, ds005620, ds004541, eegmmidb and HBN. LEMON and the
two anaesthetised deposits ARE the references; eegmmidb was E198's transport target; **HBN is awake
children, and catalogue rule 54 records that its low values are low because they are children** — so it
cannot serve as an independent graded-depth task. A genuine forward test of the recommendation on a new
cohort is therefore **not available with local data**, and that is stated as a blocker rather than
worked around with a cohort that cannot bear it.

=========================================================================================================
GATES
=========================================================================================================
G1  the two halves must be DISJOINT IN SUBJECTS, asserted on the subject ids, not assumed from the split.
G2  each half must reach at least `MIN_REF_HALF_N` reference values, or a resolution difference between
    halves is a sample-size difference (rule 50).
G3  the measured floor is recomputed for every reference, by permuting stage labels WITHIN subject, as in
    E198. A reference whose null already resolves pairs is refused.
G4  R_AWAKE and full R_SPAN are recomputed here and must reproduce E198's counts of 2 and 3. If they do
    not, the machinery has drifted and nothing else in the file may be read.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3 or G4 fails.
  (2) SUBJECT-DEPENDENT   the two halves DISAGREE with each other. The recommendation is then about which
                          subjects were in the reference, not about the scheme, and E198's advice must
                          carry that caveat.
  (3) HALVES UNDERPOWERED both halves fall short of full R_SPAN but agree with each other. Consistent
                          with a size effect and NOT evidence against the scheme; reported as its own
                          outcome so it is not mistaken for (2).
  (4) SCHEME-ROBUST       both halves reproduce full R_SPAN's count. The recommendation is about adding
                          anaesthetised data, not about these particular subjects.

**REGISTERED PREDICTION: (4) SCHEME-ROBUST.** R_AWAKE's failure is not marginal — its deep-end spread is
exactly 0.0000, N2 and N3 landing on the identical value, which is saturation rather than noise. Halving
the anaesthetised contribution should not restore resolution that a whole awake-only reference lacks
entirely. **If (2) comes back it is the more important outcome**, because every normative-reference
recommendation this programme makes would inherit the caveat.

    python bsde/src/bsde/experiments/e211_reference_split_half.py
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
from e198_reference_depth_resolution import LADDER, resolution                 # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e211_reference_split_half.json")
SEED = 20260802

NULL_DRAWS = 40
MIN_REF_HALF_N = 60
E198_EXPECTED = {"R_AWAKE": 2, "R_SPAN": 3}


def main() -> int:
    print("E211 — does E198's recommendation survive rebuilding its reference from disjoint halves?")
    la, la_s = E95.lemon_awake()
    da, da_s = E95.ds005620_anaes()
    stages = E95.sleep_stages()
    da_s = np.asarray(da_s)
    subs = sorted(set(da_s.tolist()))
    rng = np.random.default_rng(SEED)
    perm = list(rng.permutation(subs))
    hA, hB = set(perm[: len(perm) // 2]), set(perm[len(perm) // 2:])
    mA = np.array([s in hA for s in da_s])
    mB = np.array([s in hB for s in da_s])
    g1 = bool(not (hA & hB)) and bool(hA and hB)
    print(f"   {len(subs)} anaesthetised subjects -> halves of {len(hA)} and {len(hB)}; "
          f"disjoint {'YES' if g1 else 'NO'}")
    print(f"   reference values: LEMON awake {la.size}, anaes half A {int(mA.sum())}, "
          f"half B {int(mB.sum())}")
    g2 = bool(mA.sum() >= MIN_REF_HALF_N and mB.sum() >= MIN_REF_HALF_N)
    print(f"   G1 {'PASS' if g1 else '*** FAIL'}   G2 {'PASS' if g2 else '*** FAIL'} "
          f"(floor {MIN_REF_HALF_N} per half)")

    refs = {"R_AWAKE": np.sort(la),
            "R_SPAN": np.sort(np.concatenate([la, da])),
            "R_SPAN_halfA": np.sort(np.concatenate([la, da[mA]])),
            "R_SPAN_halfB": np.sort(np.concatenate([la, da[mB]]))}
    landmarks = {k: float(np.median(E95.pct(la, r))) for k, r in refs.items()}

    subj_of = {}
    for k in LADDER:
        if k in stages:
            v, s = stages[k]
            for i, sid in enumerate(s):
                subj_of.setdefault(sid, {})[k] = v[i]
    usable = [s for s, d in subj_of.items() if all(k in d and np.isfinite(d[k]) for k in LADDER)]
    print(f"   {len(usable)} sleep subjects with all four strata")

    def score(ref, landmark, assign):
        med, ci = {}, {}
        for k in LADDER:
            vv = np.array([subj_of[s][assign[s][k]] for s in usable], float)
            u = E95.pct(vv, ref) - landmark
            lo, hi = E95.boot_median(u, usable, SEED, reps=400)
            med[k], ci[k] = float(np.median(u)), (float(lo), float(hi))
        return med, ci

    ident = {s: {k: k for k in LADDER} for s in usable}
    res = {"experiment": "E211", "n_anaes_subjects": len(subs),
           "half_sizes": [int(mA.sum()), int(mB.sum())], "g1": g1, "g2": g2, "references": {}}

    print(f"\n{'reference':<14s} {'n':>5s} {'resolved':>9s} {'floor':>6s} {'W-N1':>8s} {'N2-N3':>8s}")
    floors = {}
    for name, ref in refs.items():
        cnt = []
        for d in range(NULL_DRAWS):
            g = np.random.default_rng(SEED + 500 + d)
            pm = {s: dict(zip(LADDER, list(g.permutation(list(LADDER))))) for s in usable}
            m_, c_ = score(ref, landmarks[name], pm)
            cnt.append(sum(resolution(m_, c_)))
        floors[name] = float(np.quantile(cnt, 0.95))
        med, ci = score(ref, landmarks[name], ident)
        got = resolution(med, ci)
        res["references"][name] = {
            "n_reference": int(ref.size), "n_resolved": int(sum(got)), "floor": floors[name],
            "resolved_pairs": got, "medians": med,
            "awake_spread": float(med["W"] - med["N1"]),
            "deep_spread": float(med["N2"] - med["N3"])}
        print(f"{name:<14s} {ref.size:>5d} {sum(got):>6d}/3 {floors[name]:>6.2f} "
              f"{med['W'] - med['N1']:>8.4f} {med['N2'] - med['N3']:>8.4f}", flush=True)

    g3 = all(v["floor"] < 1.0 for v in res["references"].values())
    g4 = all(res["references"][k]["n_resolved"] == v for k, v in E198_EXPECTED.items())
    print(f"G3 nulls resolve nothing: {'PASS' if g3 else '*** FAIL'}   "
          f"G4 reproduces E198 (R_AWAKE 2, R_SPAN 3): "
          f"{ {k: res['references'][k]['n_resolved'] for k in E198_EXPECTED} }  "
          f"{'PASS' if g4 else '*** FAIL'}")
    res["g3"], res["g4"] = g3, g4

    a = res["references"]["R_SPAN_halfA"]["n_resolved"]
    b = res["references"]["R_SPAN_halfB"]["n_resolved"]
    full = res["references"]["R_SPAN"]["n_resolved"]
    print("\n" + "=" * 100)
    if not (g1 and g2 and g3 and g4):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1 disjoint", g1), ("G2 half sizes", g2),
                            ("G3 null floor", g3), ("G4 reproduces E198", g4)) if not ok))
    elif a != b:
        v_, why = "SUBJECT-DEPENDENT", (
            f"the two disjoint halves DISAGREE ({a} vs {b} of 3). E198's recommendation is about which "
            "anaesthetised subjects were in the reference, not about the scheme, and every "
            "normative-reference recommendation in this programme inherits that caveat")
    elif a < full:
        v_, why = "HALVES UNDERPOWERED", (
            f"both halves resolve {a} of 3 against full R_SPAN's {full}, agreeing with each other. That "
            "is consistent with a reference-size effect and is NOT evidence against the scheme")
    else:
        v_, why = "SCHEME-ROBUST", (
            f"both disjoint halves reproduce full R_SPAN's {full} of 3, against R_AWAKE's "
            f"{res['references']['R_AWAKE']['n_resolved']}. The recommendation is about ADDING "
            "anaesthetised data, not about these particular subjects")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print("BLOCKER, stated rather than worked around: a genuine FORWARD test of the recommendation on a\n"
          "  new cohort is not available locally. Of the deposits carrying `aperiodic_wholehead`, LEMON\n"
          "  and the two anaesthetised sets ARE the references, eegmmidb was E198's transport target, and\n"
          "  HBN is awake children whose low values are low because they are children (rule 54).")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
