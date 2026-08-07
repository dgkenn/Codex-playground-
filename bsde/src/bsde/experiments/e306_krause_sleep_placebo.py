#!/usr/bin/env python3
"""E306 -- the no-drug placebo for E305. Does "leakage" grow with depth when NO drug is present?

PRE-REGISTRATION. Committed before any statistic in it exists.

THE ALTERNATIVE EXPLANATION E305 DID NOT EXCLUDE, and it is the serious one. E305 found that
propofol-arm and dexmedetomidine-arm patients are more separable at the unresponsive state than at wake
(D = +0.1648, p = 0.0016), and read that as agent identity growing with depth. **But the two arms are
different PEOPLE** -- different electrode coverage, different epileptic foci, different anatomy. If
between-patient differences of any kind become more legible at deeper states -- more signal, less
movement artefact, less arousal-driven variability -- then arm separability would rise with depth **with
no drug involved at all**, and E305's interpretation would be wrong.

**The Krause deposit contains the control that settles this**: 24 of its patients also have staged
natural overnight sleep, including patients from both drug arms. During sleep **neither group is
receiving any drug**, yet they are still the same two groups of people, with the same electrodes, moving
through a graded depth ladder (W -> N1 -> N2 -> N3).

So the identical statistic can be computed with the drug removed and everything else held.

PRIMARY. `D_sleep = |AUC-0.5|(deep sleep) - |AUC-0.5|(wake sleep)`, between the same two patient groups
(those assigned to propofol versus those assigned to dexmedetomidine), computed over the same 17
features, with the same cluster-level permutation null over patients.
    deep sleep  = N2 and N3 pooled;  wake = WS.

PREDICTION: **D_sleep is at or below its null (p >= 0.05), and materially smaller than E305's +0.1648.**
That is the outcome that licenses E305's drug interpretation.
WRONG IF: D_sleep is comparable to D_drug. **Then E305 measures state-dependent between-patient
separability, not agent identity, and the Krause replication in the manuscript must be withdrawn** --
along with the claim that the behavioural-axis result answers the circularity objection. This outcome is
named first because it is the one that costs the most.

SECONDARY (descriptive): the absolute separability between the two patient groups during wake sleep,
which estimates how different these two groups of people are before any state or drug enters.

GATES.
  G1  COVERAGE: >= 4 patients per arm with both a wake-sleep and a deep-sleep block, else NOT
      INTERPRETABLE. **Power is poor by construction here** -- with roughly 13 versus 6 patients the
      patient-level null for a single |AUC-0.5| sits near 0.29 (rule 69, E142's measurement on this same
      deposit). The PAIRED difference is better powered than either level, which is why D and not the
      level is the primary, but this experiment can only detect a LARGE D_sleep. **A null here is
      therefore weak evidence, and that is stated in advance rather than discovered after.**
  G2  THE SLEEP DEPTH AXIS IS ALIVE: at least half the features must separate wake sleep from deep sleep
      within the larger group, else "deep" and "wake" are not distinguishable states here and the
      contrast is meaningless (rule 53).

SCOPE. Same as E305: intracranial, epilepsy-surgery patients, depositor-computed features, block-level
staging. Additionally, natural sleep is not pharmacological unconsciousness -- it is the appropriate
no-drug control for THIS question (are the groups separable absent a drug?) and is not a claim that
sleep and anaesthesia are equivalent.

    python -m bsde.experiments.e306_krause_sleep_placebo
"""
from __future__ import annotations

import argparse, csv, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
SKIP = {"label", "refTime", "patientID", "Subdural", "timeOfDay",
        "timeOfDay_envCorrTimeData", "timeOfDay_bandPowerTimeData",
        "pctGoodSamples", "pctGoodSamples_envCorrTimeData", "pctGoodSamples_bandPowerTimeData"}
PPF = {"WA", "S", "U"}
DEX = {"WA_dex", "S_dex", "U_dex"}
WAKE_SLEEP = {"WS"}
DEEP_SLEEP = {"N2", "N3"}


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
    ap.add_argument("--seed", type=int, default=306)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e306_krause_sleep_placebo.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    rows = list(csv.DictReader(open(a.data)))
    cols = [c for c in rows[0] if c not in SKIP]

    # which arm does each patient belong to, from their DRUG blocks
    arm = {}
    for r in rows:
        if r["label"] in PPF:
            arm[r["patientID"]] = "ppf"
        elif r["label"] in DEX:
            arm[r["patientID"]] = "dex"
    # sleep blocks, per patient per sleep-state
    acc = {}
    for r in rows:
        lab = r["label"]
        st = "wake" if lab in WAKE_SLEEP else ("deep" if lab in DEEP_SLEEP else None)
        if st and r["patientID"] in arm:
            acc.setdefault((r["patientID"], st), []).append(r)
    val = {k: {c: med([f(x.get(c)) for x in rs]) for c in cols} for k, rs in acc.items()}
    pats = sorted({p for p, _ in val})
    pats = [p for p in pats if (p, "wake") in val and (p, "deep") in val]
    if a.smoke:
        arms = [arm[p] for p in pats]; rng.shuffle(arms)
        for p, x in zip(pats, arms):
            arm[p] = x
        print("[SMOKE] arm labels permuted across patients (cluster level)")

    n_arm = {x: sum(1 for p in pats if arm[p] == x) for x in ("ppf", "dex")}
    print(f"[cohort] {len(pats)} patients with BOTH wake-sleep and deep-sleep blocks: {n_arm}")
    print(f"[cohort] {len(cols)} features")

    G1 = all(v >= 4 for v in n_arm.values())
    print(f"[G1] >= 4 per arm -> {'PASS' if G1 else 'FAIL'}")

    alive = 0
    big = "ppf" if n_arm["ppf"] >= n_arm["dex"] else "dex"
    for c in cols:
        w = [val[(p, "wake")][c] for p in pats if arm[p] == big]
        d = [val[(p, "deep")][c] for p in pats if arm[p] == big]
        A = auc(d, w)
        if math.isfinite(A) and abs(A - 0.5) >= 0.25:
            alive += 1
    G2 = alive >= len(cols) / 2
    print(f"[G2] sleep depth axis alive within {big}: {alive} of {len(cols)} features "
          f"separate wake from deep sleep -> {'PASS' if G2 else 'FAIL'}")

    def D_for(labelmap):
        hi, lo = [], []
        for c in cols:
            h = leak([val[(p, "deep")][c] for p in pats if labelmap[p] == "ppf"],
                     [val[(p, "deep")][c] for p in pats if labelmap[p] == "dex"])
            l = leak([val[(p, "wake")][c] for p in pats if labelmap[p] == "ppf"],
                     [val[(p, "wake")][c] for p in pats if labelmap[p] == "dex"])
            if math.isfinite(h) and math.isfinite(l):
                hi.append(h); lo.append(l)
        return (med(hi) - med(lo)) if hi else float("nan"), med(hi), med(lo), len(hi)

    D, Lhi, Llo, nfeat = D_for(arm)
    print(f"\n[P1 no-drug placebo] separability at DEEP SLEEP = {Lhi:.4f}; at WAKE SLEEP = {Llo:.4f}")
    print(f"[P1] D_sleep = {D:+.4f} over {nfeat} features   (E305's drug D was +0.1648)")
    null = []
    for _ in range(a.reps):
        arms = [arm[p] for p in pats]; rng.shuffle(arms)
        lm = dict(zip(pats, arms))
        d, *_ = D_for(lm)
        if math.isfinite(d):
            null.append(d)
    null.sort()
    p = sum(1 for v in null if v >= D) / len(null) if null else float("nan")
    print(f"[P1] cluster permutation null: 95th = {null[int(0.95*len(null))]:+.4f}, "
          f"median {med(null):+.4f}; p = {p:.4f} ({len(null)} draws)")
    print(f"[secondary] absolute separability of the two patient groups at WAKE SLEEP = {Llo:.4f} "
          f"-- how different these people are before state or drug enters")

    gates = G1 and G2
    if not gates:
        verdict = "NOT INTERPRETABLE"
        why = "gate failed: " + ", ".join(g for g, ok in (("G1", G1), ("G2", G2)) if not ok)
    elif math.isfinite(p) and p >= 0.05:
        verdict = "PLACEBO CLEAN -- E305's drug interpretation is licensed"
        why = (f"with no drug present the same statistic gives D_sleep = {D:+.4f} (p = {p:.4f}), "
               f"against D_drug = +0.1648 (p = 0.0016). State-dependent between-patient separability "
               f"does not reproduce the drug result.")
    else:
        verdict = "PLACEBO FIRES -- E305 MUST BE WITHDRAWN"
        why = (f"D_sleep = {D:+.4f} (p = {p:.4f}) reproduces the drug result with no drug present, so "
               f"E305 measures state-dependent between-patient separability, not agent identity.")
    print(f"\nVERDICT: {verdict}\n  {why}")
    print("\nPOWER CAVEAT, registered in advance: with these arm sizes only a LARGE D_sleep is "
          "detectable, so a null here is weak evidence rather than strong.")

    rep = {"verdict": verdict, "why": why, "D_sleep": D, "deep": Lhi, "wake": Llo,
           "p": p, "null_p95": null[int(0.95 * len(null))] if null else None,
           "n_patients": n_arm, "n_features": nfeat,
           "gates": {"G1": G1, "G2": G2, "g2_alive": alive},
           "D_drug_reference": 0.1648}
    if not a.smoke:
        json.dump(rep, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
