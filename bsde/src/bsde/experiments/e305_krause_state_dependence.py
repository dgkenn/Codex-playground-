#!/usr/bin/env python3
"""E305 -- does drug leakage grow with depth on a BEHAVIOURAL axis, in an independent deposit?

PRE-REGISTRATION. Committed before any statistic in it exists.

WHY THIS IS THE EXTERNAL TEST THE MANUSCRIPT NEEDS. The VitalDB result -- agent identity is far larger at
maintenance than near emergence, graded with depth -- has two unresolved weaknesses (manuscript sect. 7):

  (a) CIRCULARITY. Depth was indexed by BIS, computed from the same EEG as the candidates. Two escapes
      failed: a muscle stratifier was not independent of depth (E295), and the drug-concentration axis
      failed its own validity check (E302).
  (b) ONE DRUG-CLASS CONTRAST. The whole effect is volatile-versus-propofol; removing propofol collapses
      it (E299).

The Krause/Banks deposit answers both at once, and it is already in the repository.

  * **The state label is BEHAVIOURAL** -- an OAA/S ladder scored at the bedside (wake / sedated /
    unresponsive), not derived from the EEG. A gradient on this axis cannot be circular in the way (a)
    describes.
  * **The drug pair is mechanistically distinct** -- propofol (GABA-A) versus dexmedetomidine (alpha-2
    agonist), the furthest reachable pair, with published opposite-signed EEG effects at matched sedation
    depth. Not another volatile-versus-intravenous instance.
  * **Independent deposit**, different institution, different recording modality.

======================================================================================================
COHORT. `results/krause_dexprosleep_allData.csv`, 12,313 rows, 34 patients, 22 derived features.
Propofol arm `WA`/`S`/`U`; dexmedetomidine arm `WA_dex`/`S_dex`/`U_dex`. Natural sleep is present and is
NOT used here -- it has no drug and cannot carry a drug contrast.

**THE POWER LIMIT, STATED BEFORE THE RUN AND NOT DISCOVERED AFTER IT.** Drug is nested in patient: 19
propofol patients against 10 dexmedetomidine. Rule 69 -- the effective n is the number of PATIENTS, and
E142 measured the patient-level permutation null's 95th percentile at **0.2791** for 15 patients on this
very deposit. So absolute leakage values here are almost uninterpretable, and **this experiment does not
attempt to measure leakage**. It measures the DIFFERENCE in leakage between two behavioural states in the
same patients, which is a paired contrast and far better powered than either level.

PRIMARY. For each feature, leakage between arms at the unresponsive state minus leakage at the wake
state:  `D = |AUC-0.5|(U vs U_dex) - |AUC-0.5|(WA vs WA_dex)`, aggregated as the median across features.

NULL. Permute the DRUG label across the 29 patients (cluster-level, rule 69), recompute both leakages and
their difference, 5,000 draws. The exact enumeration C(29,10) is too large; 5,000 draws resolve p to
0.0002, ample for the threshold used.

PREDICTION: **D > 0 with p < 0.05** -- leakage is larger at the deeper behavioural state, the same
direction as VitalDB.
WRONG IF: D <= 0 or p >= 0.05. **That outcome would confine the VitalDB gradient to a BIS-indexed axis
and a volatile contrast, and the manuscript's central claim would have to be narrowed to exactly that.**
It is named first because it is the outcome that changes what may be said.

GATES.
  G1  BOTH STATES POPULATED: >= 5 patients per arm at each of the two states, else NOT INTERPRETABLE.
  G2  THE STATE AXIS IS ALIVE: at least half the features must separate wake from unresponsive
      WITHIN the propofol arm (the larger one), else a leakage difference between states is a difference
      between two arbitrary subsets (rule 53 / rule 83).
  G3  CAPABILITY: a synthetic feature constructed to BE the drug label must be detected at both states;
      an independent Gaussian must not be. Its independence from the drug label is measured before use
      (rule 77).

SECONDARY (descriptive, no threshold): the same D computed with the SEDATED state in place of
unresponsive, to see whether the gradient is monotone across the three-level ladder.

SCOPE, carried into any sentence that uses this result: **intracranial electrodes in epilepsy-surgery
patients, features computed by the depositors' pipeline** (so rule 23's independent-implementation check
is unavailable -- the deposit ships no raw traces), block-level OAA/S rather than per-second, and 10
dexmedetomidine patients. This is a replication of a DIRECTION, not of a magnitude.

    python -m bsde.experiments.e305_krause_state_dependence
"""
from __future__ import annotations

import argparse, csv, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
SKIP = {"label", "refTime", "patientID", "Subdural", "timeOfDay",
        "timeOfDay_envCorrTimeData", "timeOfDay_bandPowerTimeData",
        "pctGoodSamples", "pctGoodSamples_envCorrTimeData", "pctGoodSamples_bandPowerTimeData"}
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


def pear(x, y):
    q = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(q) < 3:
        return float("nan")
    n = len(q); mx = sum(t[0] for t in q) / n; my = sum(t[1] for t in q) / n
    sxy = sum((t[0] - mx) * (t[1] - my) for t in q)
    sxx = sum((t[0] - mx) ** 2 for t in q); syy = sum((t[1] - my) ** 2 for t in q)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(RESULTS, "krause_dexprosleep_allData.csv"))
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=305)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e305_krause_state_dependence.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    rows = list(csv.DictReader(open(a.data)))
    cols = [c for c in rows[0] if c not in SKIP]
    # per patient x state medians, per arm
    val = {}          # (patient, arm, state) -> {feature: median}
    pat_arm = {}
    acc = {}
    for r in rows:
        lab = r["label"]
        if lab in PPF:
            arm, st = "ppf", PPF[lab]
        elif lab in DEX:
            arm, st = "dex", DEX[lab]
        else:
            continue
        pid = r["patientID"]
        pat_arm[pid] = arm
        acc.setdefault((pid, st), []).append(r)
    for (pid, st), rs in acc.items():
        val[(pid, st)] = {c: med([f(x.get(c)) for x in rs]) for c in cols}

    pats = sorted(pat_arm)
    if a.smoke:
        arms = [pat_arm[p] for p in pats]; rng.shuffle(arms)
        pat_arm = dict(zip(pats, arms))
        print("[SMOKE] drug labels permuted across patients (cluster level, rule 69)")
    n_arm = {x: sum(1 for p in pats if pat_arm[p] == x) for x in ("ppf", "dex")}
    print(f"[cohort] {len(pats)} patients: {n_arm}; {len(cols)} features")

    def arm_vals(state, arm, feat):
        return [val[(p, state)][feat] for p in pats
                if pat_arm[p] == arm and (p, state) in val
                and math.isfinite(val[(p, state)][feat])]

    # ---- G1
    g1 = {}
    for st in ("wake", "unresponsive"):
        g1[st] = {x: len(set(p for p in pats if pat_arm[p] == x and (p, st) in val))
                  for x in ("ppf", "dex")}
        print(f"[G1] {st:13s} patients per arm: {g1[st]}")
    G1 = all(v >= 5 for st in g1 for v in g1[st].values())
    print(f"[G1] both states >= 5 per arm -> {'PASS' if G1 else 'FAIL'}")

    # ---- G2 state axis alive within the propofol arm
    alive = 0
    for c in cols:
        w = arm_vals("wake", "ppf", c); u = arm_vals("unresponsive", "ppf", c)
        A = auc(u, w)
        if math.isfinite(A) and abs(A - 0.5) >= 0.25:
            alive += 1
    G2 = alive >= len(cols) / 2
    print(f"[G2] state axis alive within propofol: {alive} of {len(cols)} features "
          f"separate wake from unresponsive at |AUC-0.5| >= 0.25 -> {'PASS' if G2 else 'FAIL'}")

    # ---- G3 capability
    synth_pos = {p: (1.0 if pat_arm[p] == "dex" else 0.0) + rng.gauss(0, 0.2) for p in pats}
    synth_neg = {p: rng.gauss(0, 1.0) for p in pats}
    r_neg = pear([1.0 if pat_arm[p] == "dex" else 0.0 for p in pats],
                 [synth_neg[p] for p in pats])
    pos_ok, neg_ok = True, True
    for st in ("wake", "unresponsive"):
        ids = [p for p in pats if (p, st) in val]
        pp = [synth_pos[p] for p in ids if pat_arm[p] == "ppf"]
        pd = [synth_pos[p] for p in ids if pat_arm[p] == "dex"]
        np_ = [synth_neg[p] for p in ids if pat_arm[p] == "ppf"]
        nd = [synth_neg[p] for p in ids if pat_arm[p] == "dex"]
        lp, ln = leak(pp, pd), leak(np_, nd)
        print(f"[G3] {st:13s} planted positive {lp:.4f} | planted negative {ln:.4f}")
        if not (math.isfinite(lp) and lp > 0.35):
            pos_ok = False
        if math.isfinite(ln) and ln > 0.35:
            neg_ok = False
    G3 = pos_ok and neg_ok and math.isfinite(r_neg) and abs(r_neg) < 0.20
    print(f"[G3] corr(drug, negative control) = {r_neg:+.4f} (rule 77) -> {'PASS' if G3 else 'FAIL'}")

    # ---- PRIMARY
    def D_for(labelmap, state_hi="unresponsive"):
        hi, lo = [], []
        for c in cols:
            a_hi = leak([val[(p, state_hi)][c] for p in pats
                         if labelmap[p] == "ppf" and (p, state_hi) in val],
                        [val[(p, state_hi)][c] for p in pats
                         if labelmap[p] == "dex" and (p, state_hi) in val])
            a_lo = leak([val[(p, "wake")][c] for p in pats
                         if labelmap[p] == "ppf" and (p, "wake") in val],
                        [val[(p, "wake")][c] for p in pats
                         if labelmap[p] == "dex" and (p, "wake") in val])
            if math.isfinite(a_hi) and math.isfinite(a_lo):
                hi.append(a_hi); lo.append(a_lo)
        return (med(hi) - med(lo), med(hi), med(lo), len(hi))

    D, Lhi, Llo, nfeat = D_for(pat_arm)
    print(f"\n[P1] leakage at UNRESPONSIVE = {Lhi:.4f}; at WAKE = {Llo:.4f}; "
          f"D = {D:+.4f} over {nfeat} features")
    null = []
    for _ in range(a.reps):
        arms = [pat_arm[p] for p in pats]; rng.shuffle(arms)
        lm = dict(zip(pats, arms))
        d, *_ = D_for(lm)
        if math.isfinite(d):
            null.append(d)
    null.sort()
    p = sum(1 for v in null if v >= D) / len(null) if null else float("nan")
    print(f"[P1] cluster-level permutation null: 95th = {null[int(0.95*len(null))]:+.4f}, "
          f"median {med(null):+.4f}; p(>= observed) = {p:.4f}  ({len(null)} draws)")

    Ds, Shi, Slo, _ = D_for(pat_arm, "sedated")
    print(f"[secondary] sedated vs wake: leakage {Shi:.4f} vs {Slo:.4f}, D = {Ds:+.4f}")

    gates = G1 and G2 and G3
    if not gates:
        verdict = "NOT INTERPRETABLE"
        why = "a gate failed: " + ", ".join(g for g, ok in
                                            (("G1", G1), ("G2", G2), ("G3", G3)) if not ok)
    elif D > 0 and p < 0.05:
        verdict = "REPLICATES"
        why = ("leakage is larger at the deeper BEHAVIOURAL state, in an independent deposit, with a "
               "mechanistically distinct drug pair -- the VitalDB gradient is not confined to a "
               "BIS-indexed axis or a volatile contrast")
    else:
        verdict = "DOES NOT REPLICATE"
        why = ("the VitalDB gradient must be narrowed to a BIS-indexed depth axis and a "
               "volatile-versus-propofol contrast")
    print(f"\nVERDICT: {verdict}\n  {why}")
    print("\nSCOPE: intracranial, epilepsy-surgery patients, depositor-computed features (no raw traces, "
          "so rule 23's independent check is unavailable), block-level OAA/S, 10 dexmedetomidine "
          "patients. A replication of DIRECTION, not of magnitude.")

    rep = {"verdict": verdict, "why": why, "D": D, "leak_unresponsive": Lhi, "leak_wake": Llo,
           "p": p, "null_p95": null[int(0.95 * len(null))] if null else None,
           "n_features": nfeat, "n_patients": n_arm, "reps": len(null),
           "secondary_sedated": {"D": Ds, "leak_sedated": Shi, "leak_wake": Slo},
           "gates": {"G1": G1, "G2": G2, "G3": G3, "g2_alive": alive,
                     "corr_drug_negative": r_neg}}
    if not a.smoke:
        json.dump(rep, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    else:
        print("\n[SMOKE] complete; nothing above is a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
