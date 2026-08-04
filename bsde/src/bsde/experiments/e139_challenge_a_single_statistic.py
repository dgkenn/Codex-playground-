#!/usr/bin/env python3
"""E139 -- Challenge A's acceptance condition as ONE statistic, computed for the first time.

REGISTERED BEFORE ANY AUC IN THIS FILE HAS BEEN COMPUTED. What has been looked at is disclosed in
"WHAT WAS ALREADY SEEN" below, and it is manifest structure only.

=========================================================================================================
WHY THIS FILE EXISTS
=========================================================================================================
`docs/CHALLENGE_DEFINITIONS_CORRECTION.md` restated Challenge A from the brief, verbatim:

    "predicts loss and recovery across anaesthetics while MINIMISING drug-identification information"

and recorded the gap that correction exposed:

    "E122 supplies the state-tracking half and E113/E120 supply the drug-audit half; **they have never
     been combined into the single statistic the brief asks for.**"

That is exactly right, and it is worse than it sounds. `docs/REFERENCE_AGAINST_ALL_THREE.md` records that
**every** previous attempt -- E21, E22, E25, E29, E35, E36 -- asked only "can a classifier tell the two
agents apart?" and answered with an AUC. The state half was measured in different files, on different
deposits, on different scales, and the two halves were never put in the same expression. A candidate that
tracks state superbly and leaks agent identity superbly has been *passing* half of the tests we ran.

This file computes the difference, per feature, on one deposit, in one bootstrap.

=========================================================================================================
THE STATISTIC
=========================================================================================================
Both halves are direction-free `|AUC - 0.5|`, which is the reason they can be subtracted at all: each is a
legibility in [0, 0.5] and neither carries a sign convention that would have to be reconciled.

    state_leg(f)  =  |AUC(f ; awake vs unresponsive)| - 0.5      pooled over BOTH drug arms
    drug_leg(f)   =  |AUC(f ; propofol vs dexmedetomidine)| - 0.5   WITHIN the unresponsive stratum
    LAMBDA(f)     =  state_leg(f) - drug_leg(f)                   in [-0.5, +0.5]

LAMBDA > 0 is the brief's acceptance condition made arithmetic: the feature says more about whether the
patient is responsive than about which drug produced the unresponsiveness. LAMBDA < 0 is a feature that is
principally an assay for the agent.

Pooling the state contrast over both arms is what makes it "across anaesthetics" rather than "in propofol".
Matching the drug contrast on unresponsiveness is E35's contrast and is what stops the drug half from
trivially re-measuring the state half.

=========================================================================================================
THE DEPOSIT, AND THE ONE THING IT CANNOT DO
=========================================================================================================
Krause dexmedetomidine/propofol/sleep (10.5281/zenodo.15497531), the derived-feature table E35 and E36
already ran on. It is the only reachable deposit carrying two mechanistically distinct anaesthetics with a
behavioural responsiveness label, and constraint A1 of `CONSOLIDATION_2026_07_31.md` -- agents in disjoint
patients -- is confirmed here: 19 propofol patients, 10 dexmedetomidine patients, **zero overlap**.

**IT CONTAINS NO RECOVERY.** Checked before registration, and it is stated here rather than discovered by a
reader: in **0 of 27** patients with both an awake and an unresponsive block does an awake block occur
after the last unresponsive block. The drug arms run one way only. So this file tests

    "predicts LOSS across anaesthetics while minimising drug-identification information"

and is silent on recovery. E05 has recovery and one drug; this has two drugs and no recovery. **No
reachable deposit has both**, which is a structural statement about Challenge A rather than about this
experiment, and it is the sharpest existing argument for the Turku/Kallionpaa request (within-subject LOR
*and* ROR at constant dosing) recorded in `docs/DATA_REQUEST_TURKU_KALLIONPAA.md`.

=========================================================================================================
THE ELECTRODE CONFOUND, WHICH WOULD OTHERWISE PRODUCE THE WHOLE RESULT
=========================================================================================================
`Subdural` splits the table 8,092 scalp / 4,221 intracranial, and it is **not balanced across arms**: the
unresponsive dexmedetomidine blocks are 56 scalp / 10 subdural while the unresponsive propofol blocks are
59 / 70. A drug-identification AUC computed across that would be substantially an electrode-type AUC
wearing a drug label. E36 named this and could not remove it.

**Everything primary in this file is restricted to `Subdural == 0`.** The intracranial arm is computed and
reported separately and enters no verdict. Scalp rows: 296 in the drug arms, 6,359 in sleep.

=========================================================================================================
REGISTERED GATES -- evaluated and printed BEFORE the primary (rules 34, 37)
=========================================================================================================
G1  MANIFEST. Each drug arm must contribute >= 8 patients with at least one awake and one unresponsive
    scalp block. Fewer, and no verdict is issued.
G2  QUALITY PLACEBO, and it is the gate that can void the run. `pctGoodSamples` is carried as a
    fourteenth "feature". If recording quality identifies the agent at or above the MEDIAN feature's drug
    legibility, then the drug half is reading the recording rather than the brain and **no LAMBDA is
    interpretable**. A test with no placebo is a test with no denominator (rule 34).
G3  LABEL PLACEBO. Drug labels permuted across patients within the unresponsive stratum must collapse
    drug legibility; state labels permuted within patient must collapse state legibility. Reported as the
    fraction of 2,000 permutations reaching the observed value, for the best feature of each half.
G4  VARIATION (rule 32). Every feature must vary within every stratum it is compared in. A feature that is
    constant in one arm is dropped and named, never silently carried.

=========================================================================================================
PRIMARY, AND THE WRONG-DIRECTION BRANCH IS WRITTEN FIRST (rule 37)
=========================================================================================================
P1  E36 established, on this same table, that phase-coupling features leak drug identity at |AUC-0.5| of
    0.000-0.128 while amplitude and complexity features leak 0.217-0.368, as the unique maximum of all 495
    partitions (p = 0.002). **E36 measured only the leak.** The registered prediction here is that the
    split survives when the state half is subtracted:

        mean LAMBDA(PHASE) - mean LAMBDA(AMPLITUDE)  >  0

    **IF IT IS NEGATIVE**, that is a refutation of E36's extrapolation and must be reported as one. It
    would mean the phase family buys its agent-invariance by being blind to state as well -- the "phase
    measures are just weaker" explanation that E36's capability control bounded only to +-0.10. This
    branch is written before the run so that it cannot be reframed as "the split is about leakage, not
    LAMBDA" afterwards.

    Families are E36's, fixed and NOT revisable:
        PHASE      frontwPLI, backwPLI, longwPLI, allwPLI
        AMPLITUDE  EffDim, NmlzCmplx, allEnvCorr, AvgDelta, AvgAlpha, AvgGamma, frontalDelta, frontalAlpha
    `InsAwPLI` and `frontBias` are excluded exactly as E36 excluded them (insular coverage is not present
    in most scalp records; frontBias is frontwPLI - backwPLI to 9.2e-16).

P2  THE COMPOSITE E36 RECOMMENDED, tested as a family claim rather than a chosen pair. E36's verdict was
    that a single spectral amplitude summary is structurally unable to pass, and that the repair is a
    composite pairing state sensitivity (amplitude) with agent-invariance (phase). **All 4 x 8 = 32
    amplitude-phase pairs are fitted**, out-of-bag on held-out patients, and the distribution of composite
    LAMBDA is compared against the distribution of the 12 single-feature LAMBDAs. Reporting the whole grid
    rather than the best pair is deliberate: picking the best pair and quoting it would be selection on
    the same data, and the family claim is the one E36 actually made.

    PREDICTION: median composite LAMBDA > max single-feature LAMBDA. This is a demanding bar and is
    expected to be the more likely of the two failures.

P3  THE DRUG-FREE TRANSFER TEST, which is new to this file and is the part that makes "minimising
    drug-identification information" operational rather than rhetorical.

    An AUC on agent labels answers "can it tell the drugs apart". It does not answer "does it know
    anything except drugs". **Natural sleep does.** The same 19 propofol patients also have full sleep
    recordings in this table -- within subject, same electrodes, same pipeline, and no drug at all. So:
    score each feature's unresponsiveness direction as fitted in the DRUG arms, and evaluate it on
    WS vs N2/N3 in sleep.

    PREDICTION: across the 12 features, rho(transfer AUC, -drug_leg) > 0 -- the features that leak least
    agent identity are the ones whose unresponsiveness direction survives into drug-free unresponsiveness.
    A feature that is really an assay for propofol has nothing to say about N3.

    LIMIT, stated because it bounds the claim: dexmedetomidine patients have no sleep recordings
    (dex-and-sleep overlap is 0 patients), so the transfer is trained on the pooled drug arms and tested in
    propofol patients only. This tests generalisation to drug-free unresponsiveness; it does not test
    generalisation across agents, which P1 does.

FALSIFICATION. If every feature's LAMBDA interval spans 0, the honest report is that this deposit cannot
separate the two halves at this n -- 296 scalp blocks in 29 patients -- and that is a real negative for
Challenge A on public data, reported as such and not reframed.

=========================================================================================================
WHAT WAS ALREADY SEEN (rule 41)
=========================================================================================================
Manifest structure only, all of it checked to design the gates above and none of it an outcome: the label
vocabulary and its counts, patient counts per arm, arm overlap (0 propofol-dex, 19 drug-sleep), the
Subdural imbalance, per-column finite counts, the absence of recovery blocks, and the MEDIANS of
`pctGoodSamples` per arm-and-state cell (0.976-0.998). No feature has been correlated with any label.

    python bsde/src/bsde/experiments/e139_challenge_a_single_statistic.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import (auc, auc_abs, cluster_bootstrap_ci,          # noqa: E402
                                 logit_fit, predict_proba, spearman)

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "krause_dexprosleep_allData.csv")
OUT = os.path.join(RESULTS, "e139_challenge_a_single_statistic.json")

PHASE = ["frontwPLI", "backwPLI", "longwPLI", "allwPLI"]
AMPLITUDE = ["EffDim", "NmlzCmplx", "allEnvCorr", "AvgDelta", "AvgAlpha", "AvgGamma",
             "frontalDelta", "frontalAlpha"]
FEATURES = AMPLITUDE + PHASE
QUALITY = "pctGoodSamples"

AWAKE = {"WA": "prop", "WA_dex": "dex"}
UNRESP = {"U": "prop", "U_dex": "dex"}
SLEEP_WAKE = {"WS"}
SLEEP_DEEP = {"N2", "N3"}


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load(subdural: str = "0"):
    """Rows split into the three blocks the design needs. `subdural` selects the electrode arm."""
    rows = [r for r in csv.DictReader(open(TABLE, newline="")) if r["Subdural"] == subdural]
    drug, sleep = [], []
    for r in rows:
        lab = r["label"]
        rec = {"pid": r["patientID"], **{c: _f(r.get(c, "")) for c in FEATURES + [QUALITY]}}
        if lab in AWAKE:
            drug.append({**rec, "state": 0, "arm": AWAKE[lab]})
        elif lab in UNRESP:
            drug.append({**rec, "state": 1, "arm": UNRESP[lab]})
        elif lab in SLEEP_WAKE:
            sleep.append({**rec, "state": 0})
        elif lab in SLEEP_DEEP:
            sleep.append({**rec, "state": 1})
    return drug, sleep


def _leg(rows, col, key, idx=None):
    """|AUC - 0.5| of `col` against binary `key`, over `idx` (all rows if None). NaN if degenerate."""
    rs = rows if idx is None else [rows[i] for i in idx]
    y, x = [], []
    for r in rs:
        v = r[col]
        if math.isfinite(v):
            y.append(r[key]); x.append(v)
    if len(set(y)) < 2 or len(x) < 6 or len(set(x)) < 2:
        return float("nan")
    return auc_abs(y, x) - 0.5


def _direction(rows, col):
    """+1 if higher `col` means unresponsive, -1 otherwise. Fitted in the drug arms only."""
    y = [r["state"] for r in rows if math.isfinite(r[col])]
    x = [r[col] for r in rows if math.isfinite(r[col])]
    if len(set(y)) < 2:
        return 0.0
    return 1.0 if auc(y, x) >= 0.5 else -1.0


def main(argv=None) -> int:
    rng = np.random.default_rng(139)
    out = {"experiment": "E139", "deposit": "krause_dexprosleep", "electrode_arm": "scalp"}
    drug, sleep = load("0")
    dr_idx = list(range(len(drug)))
    unresp = [i for i in dr_idx if drug[i]["state"] == 1]

    # ---------------- G1 MANIFEST -------------------------------------------------------------------
    have = defaultdict(set)
    for r in drug:
        have[(r["arm"], r["state"])].add(r["pid"])
    both = {a: len(have[(a, 0)] & have[(a, 1)]) for a in ("prop", "dex")}
    g1 = both["prop"] >= 8 and both["dex"] >= 8
    print(f"G1 MANIFEST  patients with BOTH awake and unresponsive scalp blocks: "
          f"prop={both['prop']} dex={both['dex']}  -> {'PASS' if g1 else 'FAIL'}")
    print(f"             scalp drug blocks={len(drug)} (unresponsive={len(unresp)}), "
          f"scalp sleep blocks={len(sleep)}")
    out["G1"] = {"pass": bool(g1), "patients_both": both, "n_drug_blocks": len(drug),
                 "n_unresp_blocks": len(unresp), "n_sleep_blocks": len(sleep)}

    # ---------------- G4 VARIATION (before anything is compared) --------------------------------------
    dropped = []
    for c in list(FEATURES):
        ok = True
        for a in ("prop", "dex"):
            for s in (0, 1):
                v = [r[c] for r in drug if r["arm"] == a and r["state"] == s and math.isfinite(r[c])]
                if len(set(v)) < 2:
                    ok = False
        if not ok:
            dropped.append(c)
    feats = [c for c in FEATURES if c not in dropped]
    print(f"G4 VARIATION  dropped for being constant in a stratum: {dropped or 'none'}")
    out["G4"] = {"dropped": dropped, "n_features": len(feats)}

    # ---------------- the two halves ------------------------------------------------------------------
    for r in drug:
        r["armbin"] = 1 if r["arm"] == "dex" else 0

    def state_leg(col, idx=None):
        return _leg(drug, col, "state", idx)

    def drug_leg(col, idx=None):
        ix = unresp if idx is None else [i for i in idx if drug[i]["state"] == 1]
        return _leg(drug, col, "armbin", ix)

    # ---------------- G2 QUALITY PLACEBO --------------------------------------------------------------
    q_drug = drug_leg(QUALITY)
    feat_drug = {c: drug_leg(c) for c in feats}
    med = float(np.nanmedian([v for v in feat_drug.values()]))
    g2 = math.isfinite(q_drug) and q_drug < med
    print(f"G2 QUALITY PLACEBO  pctGoodSamples drug legibility={q_drug:+.4f} vs median feature "
          f"{med:+.4f}  -> {'PASS' if g2 else 'FAIL (verdict VOID)'}")
    out["G2"] = {"pass": bool(g2), "quality_drug_leg": q_drug, "median_feature_drug_leg": med}

    # ---------------- G3 LABEL PLACEBO ----------------------------------------------------------------
    best_state = max(feats, key=lambda c: (state_leg(c) if math.isfinite(state_leg(c)) else -9))
    best_drug = max(feats, key=lambda c: (feat_drug[c] if math.isfinite(feat_drug[c]) else -9))
    obs_s, obs_d = state_leg(best_state), feat_drug[best_drug]
    REPS = 2000
    # state labels permuted WITHIN patient (preserves each patient's block count and arm)
    by_pid = defaultdict(list)
    for i in dr_idx:
        by_pid[drug[i]["pid"]].append(i)
    hits_s = 0
    real_state = [r["state"] for r in drug]
    for _ in range(REPS):
        for ix in by_pid.values():
            perm = rng.permutation([drug[i]["state"] for i in ix])
            for i, v in zip(ix, perm):
                drug[i]["state"] = int(v)
        if (state_leg(best_state) or 0) >= obs_s:
            hits_s += 1
    for i, v in zip(dr_idx, real_state):
        drug[i]["state"] = v
    # drug labels permuted ACROSS patients within the unresponsive stratum, whole patients at a time
    up = sorted({drug[i]["pid"] for i in unresp})
    arm_of = {p: drug[[i for i in unresp if drug[i]["pid"] == p][0]]["armbin"] for p in up}
    real_arm = [drug[i]["armbin"] for i in dr_idx]
    hits_d = 0
    labels = [arm_of[p] for p in up]
    for _ in range(REPS):
        perm = rng.permutation(labels)
        m = dict(zip(up, perm))
        for i in unresp:
            drug[i]["armbin"] = int(m[drug[i]["pid"]])
        if (drug_leg(best_drug) or 0) >= obs_d:
            hits_d += 1
    for i, v in zip(dr_idx, real_arm):
        drug[i]["armbin"] = v
    fs, fd = hits_s / REPS, hits_d / REPS
    g3 = fs < 0.05 and fd < 0.05
    print(f"G3 LABEL PLACEBO  state({best_state}) obs={obs_s:+.4f} frac_null>=obs={fs:.4f} | "
          f"drug({best_drug}) obs={obs_d:+.4f} frac_null>=obs={fd:.4f}  -> {'PASS' if g3 else 'FAIL'}")
    out["G3"] = {"pass": bool(g3), "state_feature": best_state, "state_obs": obs_s, "state_frac": fs,
                 "drug_feature": best_drug, "drug_obs": obs_d, "drug_frac": fd}

    gates_ok = g1 and g2 and g3
    print(f"\nGATES {'ALL PASS' if gates_ok else 'NOT ALL PASSED -- no verdict is issued below'}\n")

    # ---------------- P1: LAMBDA per feature ----------------------------------------------------------
    pids = np.array([r["pid"] for r in drug])
    lam = {}
    print(f"{'feature':16s} {'family':10s} {'state_leg':>10s} {'drug_leg':>9s} {'LAMBDA':>8s}  95% CI")
    for c in feats:
        s, d = state_leg(c), feat_drug[c]
        lo, hi, nok = cluster_bootstrap_ci(lambda ix, c=c: (state_leg(c, list(ix)) or float("nan"))
                                           - (drug_leg(c, list(ix)) or float("nan")),
                                           pids, rng, reps=1000)
        lam[c] = {"state_leg": s, "drug_leg": d, "lambda": s - d, "ci": [lo, hi], "n_ok": nok,
                  "family": "PHASE" if c in PHASE else "AMPLITUDE"}
        print(f"{c:16s} {lam[c]['family']:10s} {s:+10.4f} {d:+9.4f} {s - d:+8.4f}  "
              f"[{lo:+.4f}, {hi:+.4f}]")
    out["P1_lambda"] = lam

    ph = [lam[c]["lambda"] for c in PHASE if c in lam]
    am = [lam[c]["lambda"] for c in AMPLITUDE if c in lam]
    diff = float(np.mean(ph) - np.mean(am))

    def _fam(ix):
        ix = list(ix)
        p = [(state_leg(c, ix) or np.nan) - (drug_leg(c, ix) or np.nan) for c in PHASE if c in lam]
        a = [(state_leg(c, ix) or np.nan) - (drug_leg(c, ix) or np.nan) for c in AMPLITUDE if c in lam]
        return float(np.nanmean(p) - np.nanmean(a))

    dlo, dhi, dn = cluster_bootstrap_ci(_fam, pids, rng, reps=1000)
    print(f"\nP1  mean LAMBDA(PHASE) - mean LAMBDA(AMPLITUDE) = {diff:+.4f} [{dlo:+.4f}, {dhi:+.4f}]")
    if not gates_ok:
        p1 = "VOID -- a gate failed"
    elif dlo > 0:
        p1 = "CONFIRMED -- the phase family wins on the combined statistic, as E36 predicted"
    elif dhi < 0:
        p1 = ("REFUTED -- the AMPLITUDE family wins on the combined statistic. E36's extrapolation from "
              "leakage to LAMBDA does not hold: the phase family's agent-invariance is bought with state "
              "blindness. Reported as a refutation, not a refinement (rule 17).")
    else:
        p1 = "INDETERMINATE -- interval spans zero"
    print(f"    -> {p1}")
    out["P1"] = {"family_diff": diff, "ci": [dlo, dhi], "verdict": p1}

    # ---------------- P2: the 32 composites -----------------------------------------------------------
    comp = []
    for a in [c for c in AMPLITUDE if c in lam]:
        for p in [c for c in PHASE if c in lam]:
            keep = [i for i in dr_idx if math.isfinite(drug[i][a]) and math.isfinite(drug[i][p])]
            if len({drug[i]["pid"] for i in keep}) < 6:
                continue
            score = np.full(len(drug), np.nan)
            sub = np.array([drug[i]["pid"] for i in keep])
            for held in np.unique(sub):                      # leave-one-patient-out, out of bag
                tr = [i for i in keep if drug[i]["pid"] != held]
                te = [i for i in keep if drug[i]["pid"] == held]
                ytr = np.array([drug[i]["state"] for i in tr], float)
                if len(set(ytr)) < 2:
                    continue
                Xtr = np.array([[drug[i][a], drug[i][p]] for i in tr], float)
                mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-12
                b = logit_fit(np.c_[np.ones(len(Xtr)), (Xtr - mu) / sd], ytr)
                Xte = (np.array([[drug[i][a], drug[i][p]] for i in te], float) - mu) / sd
                score[te] = predict_proba(np.c_[np.ones(len(Xte)), Xte], b)
            for i in dr_idx:
                drug[i]["_comp"] = float(score[i])
            s, d = state_leg("_comp"), drug_leg("_comp")
            if math.isfinite(s) and math.isfinite(d):
                comp.append({"amp": a, "phase": p, "state_leg": s, "drug_leg": d, "lambda": s - d})
    max_single = max(v["lambda"] for v in lam.values() if math.isfinite(v["lambda"]))
    med_comp = float(np.median([c["lambda"] for c in comp])) if comp else float("nan")
    best_comp = max(comp, key=lambda c: c["lambda"]) if comp else None
    print(f"\nP2  {len(comp)} amplitude x phase composites, out-of-bag (leave-one-patient-out)")
    print(f"    median composite LAMBDA = {med_comp:+.4f}   max single-feature LAMBDA = {max_single:+.4f}")
    if best_comp:
        print(f"    best pair {best_comp['amp']} + {best_comp['phase']}: LAMBDA={best_comp['lambda']:+.4f} "
              f"(state {best_comp['state_leg']:+.4f}, drug {best_comp['drug_leg']:+.4f}) "
              f"-- selected on this data, quoted for description only")
    p2 = ("VOID -- a gate failed" if not gates_ok else
          "CONFIRMED -- the composite repair beats every single feature" if med_comp > max_single else
          "FAILED -- the composite does not beat the best single feature")
    print(f"    -> {p2}")
    out["P2"] = {"n_composites": len(comp), "median_lambda": med_comp, "max_single_lambda": max_single,
                 "best": best_comp, "verdict": p2, "grid": comp}

    # ---------------- P3: drug-free transfer ----------------------------------------------------------
    tr_auc = {}
    for c in feats:
        sgn = _direction(drug, c)
        y = [r["state"] for r in sleep if math.isfinite(r[c])]
        x = [sgn * r[c] for r in sleep if math.isfinite(r[c])]
        tr_auc[c] = auc(y, x) if len(set(y)) > 1 and len(x) > 20 else float("nan")
    ok = [c for c in feats if math.isfinite(tr_auc[c]) and math.isfinite(feat_drug[c])]
    rho = spearman([tr_auc[c] for c in ok], [-feat_drug[c] for c in ok])
    spids = np.array([r["pid"] for r in sleep])
    print(f"\nP3  drug-free transfer -- direction fitted in the drug arms, evaluated on WS vs N2/N3")
    print(f"{'feature':16s} {'family':10s} {'drug_leg':>9s} {'sleep AUC':>10s}")
    for c in sorted(ok, key=lambda c: -tr_auc[c]):
        print(f"{c:16s} {lam[c]['family']:10s} {feat_drug[c]:+9.4f} {tr_auc[c]:10.4f}")
    print(f"    rho(sleep AUC, -drug_leg) over {len(ok)} features = {rho:+.4f}")
    p3 = ("VOID -- a gate failed" if not gates_ok else
          "CONFIRMED -- least agent-legible features transfer best to drug-free unresponsiveness"
          if rho > 0 else
          "FAILED -- agent legibility does not predict transfer to natural sleep")
    print(f"    -> {p3}")
    out["P3"] = {"transfer_auc": tr_auc, "rho_transfer_vs_neg_drug_leg": rho, "n": len(ok),
                 "verdict": p3, "n_sleep_patients": int(len(set(spids)))}

    # ---------------- secondary: the intracranial arm, no verdict --------------------------------------
    try:
        d2, _ = load("1")
        u2 = [i for i, r in enumerate(d2) if r["state"] == 1]
        for r in d2:
            r["armbin"] = 1 if r["arm"] == "dex" else 0
        sec = {}
        for c in feats:
            s = _leg(d2, c, "state")
            dd = _leg(d2, c, "armbin", u2)
            sec[c] = {"state_leg": s, "drug_leg": dd, "lambda": s - dd}
        out["secondary_subdural"] = sec
        print(f"\nSECONDARY (intracranial, {len(d2)} blocks) -- reported, enters no verdict. "
              f"LAMBDA range {min(v['lambda'] for v in sec.values()):+.4f} to "
              f"{max(v['lambda'] for v in sec.values()):+.4f}")
    except Exception as e:                                                       # noqa: BLE001
        out["secondary_subdural"] = {"error": f"{type(e).__name__}: {e}"}

    out["scope_limit"] = ("No recovery blocks exist in this deposit (0 of 27 patients have an awake block "
                          "after the last unresponsive block), so this tests LOSS across anaesthetics "
                          "only. Challenge A's 'and recovery' clause is untested here and untestable on "
                          "any reachable deposit that also has two agents.")
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
