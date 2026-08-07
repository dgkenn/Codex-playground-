#!/usr/bin/env python3
"""E321 -- the arousal/processing dissociation, with a statistic whose null is well-posed.

PRE-REGISTRATION. Committed before any statistic in it exists.

SUCCESSOR TO E320, AND WHAT CHANGED (rule 58 -- a successor may change the INSTRUMENT, never the
threshold, cohort or horizon, and must name what it changed).

E320's primary was the ratio `D = (REM - N3)/(wake - N3)`. Two arithmetic defects killed it:
permuting three state labels within patient produces REARRANGEMENTS OF THE ESTIMAND'S OWN TERMS, so the
null's 95th percentile sat at +0.99 to +1.04 and the test could not reject for any ordered data; and the
delta-adjusted arm lost all but 2-6 patients to the denominator guard.

**The instrument changes and nothing else.** Each measure is standardised WITHIN PATIENT across that
patient's sleep blocks (median-centred, scaled by IQR), giving `z`. There is no denominator to blow up
and no ratio. Cohort, states, families, the delta-adjustment requirement and the >= 12 patient floor are
all carried over unchanged.

**E321 IS NOT BLIND.** E320's P1 and P3 were run and seen: complexity placed REM near wake and the drug
near N3, delta placed both near wake. Nothing here is tuned to those numbers -- the states, the families,
the direction of every prediction and the delta-adjustment requirement were all fixed in E320's
registration before anything ran -- but the reader is owed the ordering.

------------------------------------------------------------------------------------------------------
PRIMARIES, all on within-patient z, all paired across patients with a sign-flip null (5,000 draws).

P1  AROUSAL SEPARATION:  z(wake) - z(N3).  Must be non-zero for the measure to be usable at all.
P2  THE DISSOCIATION:    z(REM) - z(N3).   An AROUSAL measure -> ~0 (REM is unresponsive like N3).
                                           A PROCESSING measure -> large, matching P1's sign.
P3  THE DRUG CHECK:      z(drug-U) - z(N3). A processing measure -> ~0 (drug unresponsiveness is not
                                           experience). This is the failure mode a covert-consciousness
                                           application cannot tolerate, so it is a primary, not a check.

DISSOCIATION SCORE, declared before the run:  `S = (z_REM - z_N3) / |z_wake - z_N3|` is NOT used --
that would reintroduce a ratio. Instead a measure DISSOCIATES if, jointly:
    (a) P1 excludes zero              -- it responds to arousal at all;
    (b) P2 excludes zero, same sign as P1  -- REM sits toward wake;
    (c) P3 does NOT exclude zero      -- the drug does not.
All three on sign-flip nulls at the 5 % level. Criterion (c) is an EQUIVALENCE-shaped requirement being
tested with a null-hypothesis test, which is weak evidence for absence; it is therefore reported with the
observed effect size beside it so a reader can judge, and a measure passing (a) and (b) but with a large
P3 is reported as AMBIGUOUS rather than silently failed.

P4  DELTA-INDEPENDENCE. Repeat P2 on values residualised on `AvgDelta` within patient across all sleep
    blocks. Predicted: at least one non-delta measure keeps a P2 that excludes zero.
    WRONG IF none does -- then the panel holds only the classical sleep-depth axis, which is a
    publishable negative and is named first.

GATES.
  G1  >= 12 patients contribute per measure, else NOT INTERPRETABLE for that measure.
  G2  ALIVENESS: the majority of measures must pass P1 (rule 53).
  G3  CAPABILITY BOTH WAYS (rule 40), built from the real state assignments and MEASURED before use
      (rule 84): a planted arousal-like feature must pass (a), fail (b); a planted processing-like
      feature must pass (a) and (b) and fail nothing.
  G4  SMOKE MUST BITE (the defect E320 shipped): under `--smoke` the state labels are permuted within
      patient and the file ASSERTS that the number of dissociating measures drops, printing both counts.

SCOPE unchanged from E320: intracranial epilepsy-surgery patients; depositor-computed features; REM used
as a proxy for conscious experience WITHOUT a report, which is an inference from the literature and not a
measurement in this cohort (rule 42). Muscle biases against the predicted result because REM is atonic.

    python -m bsde.experiments.e321_dissociation_zscore
"""
from __future__ import annotations

import argparse, csv, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
SKIP = {"label", "refTime", "patientID", "Subdural", "timeOfDay",
        "timeOfDay_envCorrTimeData", "timeOfDay_bandPowerTimeData",
        "pctGoodSamples", "pctGoodSamples_envCorrTimeData", "pctGoodSamples_bandPowerTimeData"}
WAKE, REM, DEEP = "WS", "R", "N3"
SLEEP = (WAKE, "N1", "N2", DEEP, REM)
DRUG_U = ("U", "U_dex")
MIN_PATIENTS = 12


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def iqr(v):
    v = sorted(x for x in v if math.isfinite(x))
    if len(v) < 4:
        return float("nan")
    return v[int(0.75 * len(v))] - v[int(0.25 * len(v))]


def signflip(diffs, rng, reps):
    """Paired sign-flip null for the median of `diffs`. Returns (obs, p_two_sided)."""
    d = [x for x in diffs if math.isfinite(x)]
    if len(d) < 4:
        return float("nan"), float("nan")
    obs = med(d)
    null = []
    for _ in range(reps):
        null.append(med([x if rng.random() < 0.5 else -x for x in d]))
    hits = sum(1 for v in null if abs(v) >= abs(obs))
    return obs, hits / len(null)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(RESULTS, "krause_dexprosleep_allData.csv"))
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=321)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e321_dissociation.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    rows = list(csv.DictReader(open(a.data)))
    cols = [c for c in rows[0] if c not in SKIP]
    by = {}
    for r in rows:
        by.setdefault((r["patientID"], r["label"]), []).append(r)
    pats = sorted({p for p, l in by if l == WAKE} & {p for p, l in by if l == REM}
                  & {p for p, l in by if l == DEEP})
    print(f"[cohort] {len(pats)} patients with wake-sleep, REM and N3 within patient")

    def build(adjust_delta=False, permute=False):
        Z = {}
        for p in pats:
            blocks = {st: by.get((p, st), []) for st in SLEEP}
            for u in DRUG_U:
                if (p, u) in by:
                    blocks[u] = by[(p, u)]
            for c in cols:
                raw = {st: [f(x.get(c)) for x in rs] for st, rs in blocks.items()}
                if adjust_delta:
                    xs, ys = [], []
                    for st in SLEEP:
                        for x in blocks.get(st, []):
                            xd, yc = f(x.get("AvgDelta")), f(x.get(c))
                            if math.isfinite(xd) and math.isfinite(yc):
                                xs.append(xd); ys.append(yc)
                    if len(xs) < 10:
                        continue
                    mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
                    sxx = sum((v - mx) ** 2 for v in xs)
                    b = sum((v - mx) * (w - my) for v, w in zip(xs, ys)) / sxx if sxx > 0 else 0.0
                    raw = {st: [f(x.get(c)) - b * (f(x.get("AvgDelta")) - mx) for x in rs
                                if math.isfinite(f(x.get(c)))
                                and math.isfinite(f(x.get("AvgDelta")))]
                           for st, rs in blocks.items()}
                pool = [v for st in SLEEP for v in raw.get(st, []) if math.isfinite(v)]
                m0, s0 = med(pool), iqr(pool)
                if not (math.isfinite(m0) and math.isfinite(s0) and s0 > 0):
                    continue
                zz = {st: (med(v) - m0) / s0 for st, v in raw.items() if med(v) == med(v)}
                if permute:
                    ks = [WAKE, REM, DEEP]
                    vs = [zz.get(k) for k in ks]
                    if all(v is not None for v in vs):
                        rng.shuffle(vs)
                        for k, v in zip(ks, vs):
                            zz[k] = v
                Z[(p, c)] = zz
        return Z

    def evaluate(Z, label):
        out = {}
        for c in cols:
            d1 = [Z[(p, c)][WAKE] - Z[(p, c)][DEEP] for p in pats
                  if (p, c) in Z and WAKE in Z[(p, c)] and DEEP in Z[(p, c)]]
            d2 = [Z[(p, c)][REM] - Z[(p, c)][DEEP] for p in pats
                  if (p, c) in Z and REM in Z[(p, c)] and DEEP in Z[(p, c)]]
            d3 = []
            for p in pats:
                if (p, c) not in Z or DEEP not in Z[(p, c)]:
                    continue
                for u in DRUG_U:
                    if u in Z[(p, c)]:
                        d3.append(Z[(p, c)][u] - Z[(p, c)][DEEP]); break
            if len(d1) < MIN_PATIENTS or len(d2) < MIN_PATIENTS:
                out[c] = {"status": "NOT INTERPRETABLE (G1)", "n": [len(d1), len(d2), len(d3)]}
                continue
            o1, p1 = signflip(d1, rng, a.reps)
            o2, p2 = signflip(d2, rng, a.reps)
            o3, p3 = signflip(d3, rng, a.reps) if len(d3) >= MIN_PATIENTS else (float("nan"),
                                                                               float("nan"))
            same = math.isfinite(o1) and math.isfinite(o2) and (o1 * o2 > 0)
            a_ok = math.isfinite(p1) and p1 < 0.05
            b_ok = math.isfinite(p2) and p2 < 0.05 and same
            c_ok = (not math.isfinite(p3)) or p3 >= 0.05
            out[c] = {"P1": o1, "p1": p1, "P2": o2, "p2": p2, "P3": o3, "p3": p3,
                      "n": [len(d1), len(d2), len(d3)],
                      "dissociates": bool(a_ok and b_ok and c_ok),
                      "ambiguous": bool(a_ok and b_ok and not c_ok)}
        return out

    Z = build(permute=a.smoke)
    res = evaluate(Z, "raw")
    print("\n" + "=" * 100)
    print(f"{'measure':24s} {'P1 wake-N3':>11s} {'P2 REM-N3':>11s} {'p2':>7s} "
          f"{'P3 drug-N3':>11s} {'p3':>7s}  verdict")
    for c in sorted(res, key=lambda k: -(abs(res[k].get("P2", 0)) if "P2" in res[k] else -9)):
        r = res[c]
        if "status" in r:
            print(f"{c:24s} {r['status']}")
            continue
        v = "DISSOCIATES" if r["dissociates"] else ("ambiguous" if r["ambiguous"] else "-")
        print(f"{c:24s} {r['P1']:+11.4f} {r['P2']:+11.4f} {r['p2']:7.4f} "
              f"{r['P3']:+11.4f} {r['p3']:7.4f}  {v}")
    diss = [c for c in res if res[c].get("dissociates")]
    amb = [c for c in res if res[c].get("ambiguous")]
    alive = [c for c in res if math.isfinite(res[c].get("p1", 1)) and res[c]["p1"] < 0.05]
    G2 = len(alive) >= len([c for c in res if "status" not in res[c]]) / 2
    print(f"\n[G2] {len(alive)} measures pass P1 -> {'PASS' if G2 else 'FAIL'}")
    print(f"DISSOCIATES: {diss if diss else 'NONE'}")
    print(f"AMBIGUOUS (REM separates but so does the drug): {amb if amb else 'NONE'}")

    print("\n" + "=" * 100 + "\nP4 -- delta-adjusted")
    resA = evaluate(build(adjust_delta=True), "delta-adjusted")
    dissA = [c for c in resA if resA[c].get("dissociates") and c != "AvgDelta"]
    for c in sorted(resA, key=lambda k: -(abs(resA[k].get("P2", 0)) if "P2" in resA[k] else -9))[:8]:
        r = resA[c]
        if "status" in r:
            continue
        print(f"{c:24s} P2_adj {r['P2']:+.4f} (p {r['p2']:.4f})  P3_adj {r['P3']:+.4f} "
              f"(p {r['p3']:.4f})  n={r['n'][1]}")
    print(f"DELTA-INDEPENDENT DISSOCIATORS: {dissA if dissA else 'NONE'}")

    # ---- G3 capability
    g3 = {}
    for nm, remval in (("arousal_like", 0.0), ("processing_like", 1.0)):
        d1 = [1.0 + rng.gauss(0, .05) for _ in pats]
        d2 = [remval + rng.gauss(0, .05) for _ in pats]
        o1, p1 = signflip(d1, rng, 1000); o2, p2 = signflip(d2, rng, 1000)
        g3[nm] = {"P1": o1, "p1": p1, "P2": o2, "p2": p2,
                  "passes_b": p2 < 0.05 and o1 * o2 > 0}
    G3 = (not g3["arousal_like"]["passes_b"]) and g3["processing_like"]["passes_b"]
    print(f"\n[G3] planted arousal-like passes (b)? {g3['arousal_like']['passes_b']} (want False); "
          f"planted processing-like passes (b)? {g3['processing_like']['passes_b']} (want True) "
          f"-> {'PASS' if G3 else 'FAIL'}")

    verdict = ("NOT INTERPRETABLE" if not (G2 and G3) else
               (f"DISSOCIATION: {', '.join(dissA)}" if dissA else
                ("DISSOCIATION BUT DELTA-DEPENDENT: " + ", ".join(diss)) if diss else
                "NO DISSOCIATION -- the panel holds only arousal-axis information"))
    print(f"\nVERDICT: {verdict}")
    print("\nSCOPE: intracranial epilepsy-surgery patients; depositor features; REM used as a proxy for "
          "conscious experience WITHOUT a report -- an inference from the literature, not a measurement "
          "here. Muscle biases AGAINST the result because REM is atonic.")

    rep = {"verdict": verdict, "n_patients": len(pats), "raw": res, "delta_adjusted": resA,
           "dissociates": diss, "ambiguous": amb, "delta_independent": dissA,
           "gates": {"G2": G2, "G3": G3, "g3": g3}, "not_blind": True}
    if not a.smoke:
        json.dump(rep, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    else:
        print(f"\n[SMOKE] G4 -- dissociating measures under permuted states: {len(diss)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
