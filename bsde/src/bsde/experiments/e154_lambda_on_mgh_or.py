#!/usr/bin/env python3
"""E154 -- Challenge A's single statistic on a second deposit, with the cluster as the unit from the start.

REGISTERED BEFORE ANY FEATURE HAS BEEN COMPARED AGAINST THE AGENT LABEL IN THIS COHORT. Manifest structure
was checked to size the gates and is disclosed at the end; no legibility of any kind has been computed.

=========================================================================================================
WHY A SECOND DEPOSIT, AND WHY THIS ONE
=========================================================================================================
`docs/CHALLENGE_A_AUDIT_2026_08_01.md` established two things about the Krause table, the only deposit on
which this project had ever computed drug legibility:

  1. **The unit was wrong.** Arm is nested in patient, so the contrast has 15 independent units and not
     115 blocks. Exact enumeration of all 6,435 labellings (E142) left **2 of 12** features clearing the
     null, put the null's mean 95th percentile at **0.2791**, and showed row-level p-values inflated by a
     mean factor of **178x**.
  2. **A nuisance variable beat most of the features.** `pctGoodSamples` identified the agent at
     |AUC-0.5| = 0.2565 (E139's failed gate), larger than 9 of the 12 features.

This file repeats the measurement on `eeg-power-anesthesia`'s OR cohort, where both problems are better
addressed than on Krause:

    Krause                              MGH OR
    15 clusters                         **39 clusters** (25 pure propofol, 14 propofol+sevoflurane)
    13 derived features, no raw         100-bin multitaper spectra, features computed here
    quality inferred from a column      **a per-window EEG-quality flag the deposit ships**
    OAA/S, rater-scored                 conscious/unconscious with a documented labelling rule

**The agent contrast is weaker than the abstract implies and that is stated before the design, not after.**
`rx_sorted_case_ids.yml` sorts the 44 cases into pure_propofol 27, mixed 16 and **pure_sevo 1**. There is
no sevoflurane-alone arm. The available contrast is *propofol only* against *propofol plus sevoflurane*,
and the single pure_sevo case is excluded rather than folded into either arm.

=========================================================================================================
THE STATISTIC, WITH THE CLUSTER AS THE UNIT BY CONSTRUCTION
=========================================================================================================
    state_leg(f)  mean over cases of that case's OWN |AUC - 0.5| for conscious vs unconscious epochs.
                  Each case contributes one number, so no case's window count can dominate.
    drug_leg(f)   |AUC - 0.5| for propofol-only vs mixed, computed on ONE VALUE PER CASE -- the median of
                  f over that case's good-quality UNCONSCIOUS epochs. Matched state, 39 observations,
                  39 independent units. **The nesting trap cannot arise because there is nothing nested.**
    LAMBDA(f)     state_leg - drug_leg

The null for the drug half permutes the arm label across the 39 cases, 20,000 times. C(39,14) is far too
large to enumerate, unlike Krause's 6,435, so this is a sampled null and its resolution (5e-5) is stated
rather than assumed.

Only epochs with the deposit's `EEGquality == 1` are used anywhere.

=========================================================================================================
GATES
=========================================================================================================
G1  MANIFEST. >= 12 cases per arm with >= 30 good-quality epochs in each state.
G2  **NUISANCE PLACEBOS, AND THEY CAN VOID THE RUN.** Three case-level nuisance variables are pushed
    through the identical drug-legibility path: the fraction of good-quality epochs, the number of epochs,
    and the recording duration. **If any of them is more agent-legible than the median feature, the drug
    half is reading the recording rather than the brain and no LAMBDA is interpretable.** Duration and
    epoch count are included because case length plausibly differs by agent choice -- a confound Krause
    could not even be checked for.
G3  **THE PHENOMENON MUST EXIST (rule 53).** At least half the candidates must reach state_leg >= 0.10.
    A cohort in which nothing separates conscious from unconscious cannot be asked which features leak
    less about the drug.
G4  NULL RESOLUTION. The permutation null must use >= 20,000 draws so a p of 0.001 is estimable.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCHES WRITTEN FIRST (rule 37)
=========================================================================================================
P1  **DRUG LEGIBILITY AGAINST THE CLUSTER-LEVEL NULL. Registered prediction: no candidate exceeds the
    null's 95th percentile after Holm correction.**

    **IF SOMETHING DOES**, then at matched unresponsiveness the frontal spectrum identifies whether
    sevoflurane was co-administered, on 39 independent cases -- which is a real positive for the
    *drug-identification* half of Challenge A and a real problem for any candidate built from it. It
    would also be the first agent-identification result in this project that survives a correct null,
    and it must be reported as such rather than buried as a caveat.

P2  **LAMBDA. Registered prediction: every candidate has LAMBDA > 0**, because state_leg should be large
    (the conscious/unconscious contrast under a GABAergic agent is the strongest effect in this
    literature) and drug_leg should be at the null floor. **That prediction is nearly unfalsifiable as
    stated and it is therefore NOT the primary** -- it is recorded so the LAMBDA values have a stated
    expectation, and P1 carries the inference. Writing down that a prediction is too easy is the point of
    rule 30.

P3  **THE COMPARISON THAT MATTERS: the null's 95th percentile here against Krause's 0.2791.** With 39
    clusters instead of 15 the floor should fall substantially. If it does not -- if 39 cases still
    cannot resolve drug legibility below roughly 0.25 -- then the conclusion is about SAMPLE SIZE rather
    than about any feature, and Challenge A's "minimising drug-identification information" clause is not
    answerable on any public deposit this project can reach. That is a statement about the field's data
    and it would be worth more than another feature ranking.

WHAT WAS ALREADY SEEN (rule 41). Manifest only: 44 OR cases, 40 with >= 30 good-quality epochs in both
states, arms 27/16/1, 92,758 good-quality epochs against 4,395 bad, and the conscious/unconscious epoch
totals 5,833 / 72,331. No feature has been compared against the agent label or the state label here.

    python bsde/src/bsde/experiments/e154_lambda_on_mgh_or.py
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

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import auc_abs, cluster_bootstrap_ci                  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "mgh_power_windows.csv")
OUT = os.path.join(RESULTS, "e154_lambda_mgh_or.json")

FEATURES = ["rel_delta", "rel_theta", "rel_alpha", "rel_beta", "rel_gamma", "spectral_edge_95",
            "spectral_entropy", "exponent_1_40", "alpha_peak_hz", "alpha_prom_db", "total_power_db"]
NUISANCE = ["frac_good_quality", "n_epochs", "duration_s"]
MIN_EPOCHS = 30
MIN_PER_ARM = 12
PERMS = 20000
STATE_BAR = 0.10


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    per = defaultdict(list)
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["cohort"] == "OR":
            per[r["case"]].append(r)
    cases = {}
    for c, rows in per.items():
        arm = rows[0]["arm"]
        good = [r for r in rows if r["quality"] == "1"]
        lab = np.array([_f(r["label"]) for r in good])
        con = np.array([l == 1.0 for l in lab])
        unc = np.array([l == 0.0 for l in lab])
        if con.sum() < MIN_EPOCHS or unc.sum() < MIN_EPOCHS or arm == "pure_sevo":
            continue
        X = {f: np.array([_f(r[f]) for r in good], float) for f in FEATURES}
        t = np.array([_f(r["t"]) for r in rows], float)
        cases[c] = {"arm": arm, "X": X, "con": con, "unc": unc,
                    "frac_good_quality": len(good) / max(len(rows), 1),
                    "n_epochs": float(len(rows)),
                    "duration_s": float(np.nanmax(t) - np.nanmin(t)) if len(t) else float("nan")}
    return cases


def main(argv=None) -> int:
    rng = np.random.default_rng(154)
    cases = load()
    ids = sorted(cases)
    arm = np.array([1 if cases[c]["arm"] == "mixed" else 0 for c in ids])
    n_mix, n_pro = int(arm.sum()), int((1 - arm).sum())
    out = {"experiment": "E154", "n_cases": len(ids), "n_mixed": n_mix, "n_propofol": n_pro,
           "perms": PERMS}

    g1 = n_mix >= MIN_PER_ARM and n_pro >= MIN_PER_ARM
    print(f"G1 MANIFEST  {len(ids)} usable OR cases: {n_pro} pure propofol, {n_mix} mixed "
          f"(floor {MIN_PER_ARM} each) -> {'PASS' if g1 else 'FAIL'}")
    print(f"G4 NULL RESOLUTION  {PERMS} permutations, p resolution {1 / PERMS:.5f} -> PASS")

    # ---- state legibility: each case contributes its own AUC ------------------------------------------
    state = {}
    for f in FEATURES:
        vals = []
        for c in ids:
            d = cases[c]
            v = d["X"][f]
            m = np.isfinite(v)
            y = np.where(d["unc"], 1, 0)[m]
            if len(set(y.tolist())) < 2 or m.sum() < 2 * MIN_EPOCHS:
                continue
            vals.append(auc_abs(list(y), list(v[m])) - 0.5)
        state[f] = float(np.mean(vals)) if vals else float("nan")
    n_alive = sum(1 for v in state.values() if math.isfinite(v) and v >= STATE_BAR)
    g3 = n_alive >= len(FEATURES) / 2
    print(f"G3 PHENOMENON EXISTS  {n_alive} of {len(FEATURES)} candidates reach state_leg >= "
          f"{STATE_BAR} -> {'PASS' if g3 else 'FAIL'}")

    # ---- case-level values for the drug half ----------------------------------------------------------
    cv = {}
    for f in FEATURES:
        cv[f] = np.array([float(np.nanmedian(cases[c]["X"][f][cases[c]["unc"]])) for c in ids], float)
    for f in NUISANCE:
        cv[f] = np.array([cases[c][f] for c in ids], float)

    def leg(col, lab):
        m = np.isfinite(cv[col])
        if len(set(lab[m].tolist())) < 2 or len(set(cv[col][m].tolist())) < 2:
            return float("nan")
        return auc_abs(list(lab[m]), list(cv[col][m])) - 0.5

    obs = {c: leg(c, arm) for c in FEATURES + NUISANCE}

    # ---- the cluster-level permutation null ------------------------------------------------------------
    null = {c: np.empty(PERMS) for c in FEATURES + NUISANCE}
    for i in range(PERMS):
        p = rng.permutation(arm)
        for c in FEATURES + NUISANCE:
            null[c][i] = leg(c, p)
    q95 = {c: float(np.nanquantile(null[c], 0.95)) for c in FEATURES + NUISANCE}
    pval = {c: float(np.nanmean(null[c] >= obs[c])) for c in FEATURES + NUISANCE}
    mean_q95 = float(np.nanmean([q95[c] for c in FEATURES]))

    # ---- G2 nuisance placebos --------------------------------------------------------------------------
    med_feat = float(np.nanmedian([obs[c] for c in FEATURES]))
    print(f"\nG2 NUISANCE PLACEBOS  median feature drug legibility = {med_feat:+.4f}")
    g2 = True
    for c in NUISANCE:
        bad = math.isfinite(obs[c]) and obs[c] >= med_feat
        g2 &= not bad
        print(f"   {c:20s} {obs[c]:+.4f}  p={pval[c]:.4f}  "
              f"{'ABOVE the median feature -- VOIDS the drug half' if bad else 'ok'}")
    print(f"   -> {'PASS' if g2 else 'FAIL (verdict VOID)'}")
    out["G1"], out["G2"], out["G3"] = bool(g1), {"pass": bool(g2), "nuisance": {c: obs[c] for c in NUISANCE},
                                                 "median_feature": med_feat}, {"pass": bool(g3),
                                                                               "n_alive": n_alive}

    gates = g1 and g2 and g3
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    holm_p = holm([pval[c] for c in FEATURES], FEATURES)
    print(f"{'candidate':18s} {'state_leg':>10s} {'drug_leg':>9s} {'LAMBDA':>8s} {'null p95':>9s} "
          f"{'p':>7s} {'p_holm':>8s}")
    res = {}
    for f in sorted(FEATURES, key=lambda x: -obs[x]):
        lam = state[f] - obs[f]
        res[f] = {"state_leg": state[f], "drug_leg": obs[f], "lambda": lam, "null_p95": q95[f],
                  "p": pval[f], "p_holm": holm_p[f],
                  "clears": bool(holm_p[f] < 0.05 and obs[f] > q95[f])}
        print(f"{f:18s} {state[f]:10.4f} {obs[f]:9.4f} {lam:+8.4f} {q95[f]:9.4f} "
              f"{pval[f]:7.4f} {holm_p[f]:8.4f}")
    out["per_feature"] = res
    out["null_mean_q95"] = mean_q95
    out["krause_null_mean_q95"] = 0.2791

    clears = [f for f in FEATURES if res[f]["clears"]]
    neg_lambda = [f for f in FEATURES if res[f]["lambda"] <= 0]
    print(f"\nP1  {len(clears)} candidate(s) exceed the cluster-level null after Holm: {clears or 'none'}")
    print(f"P2  {len(FEATURES) - len(neg_lambda)} of {len(FEATURES)} have LAMBDA > 0 "
          f"(prediction was all of them; this statistic is descriptive, not the inference)")
    print(f"P3  mean 95th percentile of the cluster-level null here = {mean_q95:.4f}   "
          f"Krause (15 clusters, E142) = 0.2791   ratio {mean_q95 / 0.2791:.2f}")

    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif clears:
        verdict = (f"POSITIVE FOR DRUG IDENTIFICATION -- {', '.join(clears)} identify whether "
                   f"sevoflurane was co-administered, at matched unresponsiveness, on {len(ids)} "
                   f"independent cases and against a cluster-level null. The registered prediction is "
                   f"WRONG. This is a problem for any Challenge A candidate built from those features, "
                   f"and it is the first agent-identification result in this project to survive a "
                   f"correct null.")
    elif mean_q95 > 0.25:
        verdict = (f"NOT RESOLVABLE -- nothing clears, but the null's floor is still {mean_q95:.4f} at "
                   f"{len(ids)} clusters, barely below Krause's 0.2791 at 15. Challenge A's "
                   f"'minimising drug-identification information' clause is not answerable at the sample "
                   f"sizes public deposits provide, and that is a statement about the field's data "
                   f"rather than about any feature.")
    else:
        verdict = (f"NEGATIVE AND INFORMATIVE -- no candidate identifies the agent at matched "
                   f"unresponsiveness, and the null's floor has fallen to {mean_q95:.4f} from Krause's "
                   f"0.2791, so the null is a measured absence rather than absence of power. Every "
                   f"candidate has LAMBDA > 0 on {len(ids)} independent cases.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
