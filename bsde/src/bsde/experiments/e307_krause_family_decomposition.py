#!/usr/bin/env python3
"""E307 -- WHICH measures carry the state-dependence, and is the ladder graded or threshold-like?

PRE-REGISTRATION, with one honest exception declared up front (see P2).

WHY. E305 established that propofol/dexmedetomidine separability is larger at the unresponsive state than
at wake (D = +0.1648, p = 0.0016) and E306's no-drug placebo excluded the between-patient explanation
(D_sleep = +0.0000, p = 0.5148). Both are aggregate statements over 17 features. Neither says WHAT is
doing the work, and that is what decides whether the phenomenon has a mechanism or is a curiosity.

VitalDB's answer was that leakage is a spectral/complexity phenomenon: it lives in the LEVEL rather than
the change (19 of 19 candidates at maintenance), a per-drug median shift removes 51-98 % of it, and the
strongest carriers are the aperiodic exponent, multiscale entropy slope and alpha peak. **VitalDB could
not test connectivity at all** -- two frontal channels make every connectivity and spatial measure NaN.
Krause has five wPLI variants and an envelope-correlation measure, so it can.

FAMILIES, assigned by instrument BEFORE any statistic is computed:
    complexity   EffDim, NmlzCmplx
    spectral     AvgDelta, AvgAlpha, AvgGamma, temporalDelta, parietalDelta, limbicDelta,
                 frontalDelta, frontalAlpha
    connectivity allEnvCorr, frontwPLI, backwPLI, longwPLI, allwPLI, InsAwPLI
    spatial      frontBias

P1 -- FAMILY DECOMPOSITION. Per family, D = median over its members of
`|AUC-0.5|(unresponsive) - |AUC-0.5|(wake)`, with the same cluster-level permutation null over the 29
patients used in E305.

PREDICTION: **spectral and complexity carry it; connectivity carries materially less.** Specifically
`D(spectral or complexity) > D(connectivity)`, and the aggregate is not driven by the connectivity family.
The reasoning is VitalDB's mechanism -- agents differ in where they park the power spectrum, and a
phase-based connectivity measure is by construction insensitive to amplitude level.
WRONG IF: connectivity carries as much or more, which would mean the phenomenon is not the spectral-level
effect VitalDB described and the two deposits are showing different things under one name.

P2 -- THE SHAPE OF THE LADDER. **DECLARED NOT BLIND.** E305's registered secondary already reported
sedated-versus-wake at D = +0.0138 against unresponsive-versus-wake at +0.1648, and I have seen it. So
this is **confirmatory description, not a prediction**, and it is reported with that label rather than
dressed as a test. What is added here is the cluster-level null for the sedated contrast, which E305 did
not compute, so that "the middle rung is flat" becomes a measured statement instead of a point estimate.

GATES.
  G1  Every family must have >= 2 members with a computable D, else that family is reported as
      NOT COMPUTABLE rather than as a low value (rule 74: report the exclusion, never score the absence).
  G2  The state axis must be alive within the larger arm, as in E305.

SCOPE. As E305/E306: intracranial, epilepsy-surgery patients, depositor-computed features, block-level
OAA/S, 19 propofol against 10 dexmedetomidine patients. Family-level medians over 2-8 members are coarse
and the per-family intervals are wide; this experiment ranks families, it does not estimate their effects
precisely.

    python -m bsde.experiments.e307_krause_family_decomposition
"""
from __future__ import annotations

import argparse, csv, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")

FAMILY = {
    "complexity":   ["EffDim", "NmlzCmplx"],
    "spectral":     ["AvgDelta", "AvgAlpha", "AvgGamma", "temporalDelta", "parietalDelta",
                     "limbicDelta", "frontalDelta", "frontalAlpha"],
    "connectivity": ["allEnvCorr", "frontwPLI", "backwPLI", "longwPLI", "allwPLI", "InsAwPLI"],
    "spatial":      ["frontBias"],
}
PPF = {"WA": "wake", "S": "sedated", "U": "unresponsive"}
DEX = {"WA_dex": "wake", "S_dex": "sedated", "U_dex": "unresponsive"}


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def midranks(vals):
    o = sorted(range(len(vals)), key=lambda i: vals[i]); r = [0.0] * len(vals); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and vals[o[j + 1]] == vals[o[i]]:
            j += 1
        av = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[o[k]] = av
        i = j + 1
    return r


def auc(p, n):
    p = [x for x in p if math.isfinite(x)]; n = [x for x in n if math.isfinite(x)]
    if not p or not n:
        return float("nan")
    r = midranks(p + n)
    return (sum(r[:len(p)]) - len(p) * (len(p) + 1) / 2.0) / (len(p) * len(n))


def leak(p, n, minn=4):
    p = [x for x in p if math.isfinite(x)]; n = [x for x in n if math.isfinite(x)]
    if len(p) < minn or len(n) < minn:
        return float("nan")
    return abs(auc(p, n) - 0.5)


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(RESULTS, "krause_dexprosleep_allData.csv"))
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=307)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e307_krause_families.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    rows = list(csv.DictReader(open(a.data)))
    present = set(rows[0])
    fam = {k: [c for c in v if c in present] for k, v in FAMILY.items()}
    allf = [c for v in fam.values() for c in v]

    arm, acc = {}, {}
    for r in rows:
        lab = r["label"]
        if lab in PPF:
            st, ar = PPF[lab], "ppf"
        elif lab in DEX:
            st, ar = DEX[lab], "dex"
        else:
            continue
        arm[r["patientID"]] = ar
        acc.setdefault((r["patientID"], st), []).append(r)
    val = {k: {c: med([f(x.get(c)) for x in rs]) for c in allf} for k, rs in acc.items()}
    pats = sorted(arm)
    if a.smoke:
        arms = [arm[p] for p in pats]; rng.shuffle(arms)
        arm = dict(zip(pats, arms))
        print("[SMOKE] drug labels permuted across patients")
    n_arm = {x: sum(1 for p in pats if arm[p] == x) for x in ("ppf", "dex")}
    print(f"[cohort] {len(pats)} patients {n_arm}; families "
          f"{ {k: len(v) for k, v in fam.items()} }")

    # G2
    alive = 0
    for c in allf:
        w = [val[(p, "wake")][c] for p in pats if arm[p] == "ppf" and (p, "wake") in val]
        u = [val[(p, "unresponsive")][c] for p in pats
             if arm[p] == "ppf" and (p, "unresponsive") in val]
        A = auc(u, w)
        if math.isfinite(A) and abs(A - 0.5) >= 0.25:
            alive += 1
    G2 = alive >= len(allf) / 2
    print(f"[G2] state axis alive within propofol: {alive} of {len(allf)} -> "
          f"{'PASS' if G2 else 'FAIL'}")

    def D_feat(labelmap, c, hi_state):
        h = leak([val[(p, hi_state)][c] for p in pats
                  if labelmap[p] == "ppf" and (p, hi_state) in val],
                 [val[(p, hi_state)][c] for p in pats
                  if labelmap[p] == "dex" and (p, hi_state) in val])
        l = leak([val[(p, "wake")][c] for p in pats
                  if labelmap[p] == "ppf" and (p, "wake") in val],
                 [val[(p, "wake")][c] for p in pats
                  if labelmap[p] == "dex" and (p, "wake") in val])
        return (h - l) if math.isfinite(h) and math.isfinite(l) else float("nan")

    def D_fam(labelmap, hi_state="unresponsive"):
        return {k: med([D_feat(labelmap, c, hi_state) for c in v]) for k, v in fam.items()}

    obs = D_fam(arm)
    n_ok = {k: sum(1 for c in v if math.isfinite(D_feat(arm, c, "unresponsive")))
            for k, v in fam.items()}
    print("\n[P1] family decomposition, unresponsive minus wake")
    null = []
    for _ in range(a.reps):
        arms = [arm[p] for p in pats]; rng.shuffle(arms)
        null.append(D_fam(dict(zip(pats, arms))))
    res = {}
    for k in fam:
        if n_ok[k] < 2:
            print(f"  {k:13s} NOT COMPUTABLE ({n_ok[k]} member(s) with a finite D)  [rule 74]")
            res[k] = {"D": obs[k], "n_ok": n_ok[k], "status": "NOT COMPUTABLE"}
            continue
        nl = sorted(x[k] for x in null if math.isfinite(x[k]))
        p = sum(1 for v in nl if v >= obs[k]) / len(nl) if nl else float("nan")
        res[k] = {"D": obs[k], "n_ok": n_ok[k], "null_p95": nl[int(0.95 * len(nl))] if nl else None,
                  "p": p, "status": "ok"}
        print(f"  {k:13s} D = {obs[k]:+.4f}   null95 = {res[k]['null_p95']:+.4f}   "
              f"p = {p:.4f}   ({n_ok[k]} features)")
    # per-feature detail
    print("\n  per-feature D (unresponsive - wake):")
    for k, v in fam.items():
        for c in v:
            d = D_feat(arm, c, "unresponsive")
            print(f"    {k:13s} {c:16s} {d:+.4f}")

    ok = [k for k in res if res[k]["status"] == "ok"]
    sc = [res[k]["D"] for k in ("spectral", "complexity") if k in ok]
    cn = res["connectivity"]["D"] if "connectivity" in ok else float("nan")
    met = math.isfinite(cn) and sc and max(sc) > cn
    print(f"\n  PREDICTED spectral/complexity > connectivity  ->  "
          f"{'MET' if met else 'NOT MET'}")

    # P2 -- declared not blind
    print("\n[P2] the shape of the ladder  **CONFIRMATORY, NOT BLIND** "
          "(E305's secondary was seen before this was written)")
    obs_s = D_fam(arm, "sedated")
    null_s = []
    for _ in range(a.reps):
        arms = [arm[p] for p in pats]; rng.shuffle(arms)
        null_s.append(D_fam(dict(zip(pats, arms)), "sedated"))
    p2 = {}
    for k in fam:
        if n_ok[k] < 2:
            continue
        nl = sorted(x[k] for x in null_s if math.isfinite(x[k]))
        p = sum(1 for v in nl if v >= obs_s[k]) / len(nl) if nl else float("nan")
        p2[k] = {"D_sedated": obs_s[k], "p": p}
        print(f"  {k:13s} sedated-vs-wake D = {obs_s[k]:+.4f}   p = {p:.4f}")
    print("  Reading: if the sedated rung sits at its null while unresponsive does not, the ladder is "
          "THRESHOLD-LIKE at loss of responsiveness rather than graded.")

    rep = {"families": res, "per_feature": {c: D_feat(arm, c, "unresponsive") for c in allf},
           "sedated": p2, "n_patients": n_arm, "gates": {"G2": G2, "alive": alive},
           "prediction_met": met, "p2_declared_not_blind": True}
    if not a.smoke:
        json.dump(rep, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
