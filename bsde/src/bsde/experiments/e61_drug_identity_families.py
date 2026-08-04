#!/usr/bin/env python3
"""E61 -- Challenge A. Do PHASE-based measures leak less anaesthetic identity than AMPLITUDE-based ones?

REGISTERED BEFORE ANY DRUG-IDENTITY AUC HAS BEEN COMPUTED ON VITALDB. What has been read is a feasibility
probe over the LABEL and the clinical record only (rule 41): `meta_agents_present` is a CASE-level field
with seven values; single-agent cases give propofol 42 and sevoflurane 67 inside BIS [40,60) with SQI >= 50,
1,306 windows across 109 cases; median age 60 vs 58 with overlapping IQRs, female fraction 0.36 vs 0.45. No
candidate has been related to agent identity.

=========================================================================================================
THE PREDICTION BEING TESTED IS THIS PROJECT'S OWN, AND IT IS SHARP
=========================================================================================================
Challenge A asks for a marker that predicts loss and recovery of responsiveness across anaesthetics **while
minimising the information it carries about which drug was used**. E35/E36 found a split by measure family
at matched unresponsiveness on the Krause deposit:

    phase-based coupling (wPLI variants)    drug-identity legibility |AUC - 0.5| = 0.000 - 0.128
    power and complexity                                            |AUC - 0.5| = 0.217 - 0.368

surviving as the unique maximum of all 495 alternative partitions (p = 0.002), with a capability control
excluding "phase measures are simply weaker" to within +/-0.10.

`UCE_AND_THE_THREE_CHALLENGES.md` turns that into a falsifiable prediction: **the aperiodic exponent, a
spectral amplitude summary, should carry agent identity** -- it was not among E36's thirteen features
because the Krause deposit ships no raw traces.

**THIS IS AN EXTENSION OF E36, NOT A REPLICATION, AND THE DIFFERENCE IS LOAD-BEARING.** E36's phase family
was INTER-channel (wPLI between electrodes). VitalDB's adapter carries ONE channel, so `wpli_alpha` and
`icoh_alpha` are NaN here and cannot be tested at all. What can be tested are WITHIN-channel phase
measures -- `bis_sfs`, a bispectrum, which reads phase coupling between frequency pairs, and
`pac_slow_alpha`, phase-amplitude coupling. A failure here therefore does NOT refute E36; it would say the
family split does not generalise from inter-channel to within-channel phase. A success extends it to a
second, independent instantiation of the same idea, on a different deposit, with different drugs.

=========================================================================================================
DESIGN
=========================================================================================================
COHORT. Single-agent cases only -- `meta_agents_present` is exactly one of "propofol" or "sevoflurane".
Windows with device BIS in **[40,60)** so agent identity is read at MATCHED DEPTH, and **SQI >= 50**, the
monitor's own quality flag. (E60 found the [0,20) band carries median SQI 5.1 and no prior experiment had
used this column; using it here is the corollary to rule 52 applied rather than noted.)

**THE CONFOUND IS STRUCTURAL AND IS NOT BEING HIDDEN.** The agents sit in DISJOINT patients -- 0 of 247
cases carry more than one agent label -- so this is a between-subject contrast and anything that differs
between patients given TIVA and patients given a volatile is in it. The probe shows age and sex are
closely matched, which bounds the two obvious ones; it does not bound surgery type. **Challenge A's
acceptance condition is nonetheless well posed under this limitation**, because the question is whether a
measure LEAKS agent identity, and a leak through a correlate of the agent is still a leak. What the design
cannot do is attribute the leak to pharmacology.

FAMILIES, ASSIGNED FROM THE INSTRUMENT AND FIXED HERE (rule 47: a placebo shows a choice is extreme, it
cannot show it was made blind -- so the assignment rule must be structural and written down first):

    PHASE      reads relations between phases            bis_sfs, pac_slow_alpha
    AMPLITUDE  summarises how much power sits where      exponent_low, exponent_high, whole_head_exponent,
                                                         relative_alpha_power, relative_delta_power,
                                                         spectral_edge_95, bis_rbr
    (complexity measures are deliberately EXCLUDED from both -- E36 grouped them with power, and folding
     them in here would import that grouping as an assumption instead of testing the phase/amplitude
     contrast this deposit can actually address.)

STATISTIC. Per candidate, out-of-fold AUC for agent identity with CASES held out whole, then |AUC - 0.5|.

    **|AUC - 0.5| IS BIASED UPWARD UNDER THE NULL** and must never be reported as one measure's effect size
    (rule 46). It is used here only inside a DIFFERENCE taken on the same rows, which is the form that rule
    prescribes:

  M1 CAPABILITY GATE  every candidate must be computable on >= 90 % of analysis windows with non-zero
                      variance. A NaN or constant column cannot leak and would enter the phase family as a
                      free win.
  M2 STATE GATE       **the capability control E36 had, and without it this experiment is worthless.**
                      Each family's mean |AUC - 0.5| for a STATE contrast (BIS < 40 vs BIS in [40,60), same
                      cases) must be comparable. If the phase family cannot discriminate state either, then
                      "leaks less" is "measures less" and the primary means nothing. Gate: the phase
                      family's state discrimination must be at least `STATE_FLOOR` of the amplitude
                      family's.
  PRIMARY             mean |AUC - 0.5| for AGENT IDENTITY, phase family minus amplitude family, with a
                      case-clustered bootstrap. **NEGATIVE means phase leaks less**, i.e. E36's direction.
  P1 PLACEBO          agent labels permuted ACROSS CASES, primary recomputed. Fixes the null level of a
                      folded statistic, which is not zero.
  P2 PARTITION        all partitions of the same sizes (2 vs 7) enumerated; the real split's rank among
                      them. E36's own control, reproduced. This shows the split is extreme, and per rule 47
                      it does NOT show it was chosen blind -- what does that is the structural assignment
                      rule above, written before any AUC existed.

VERDICT RULE, wrong direction first.

  (a) REVERSED        -- the primary CI lies entirely ABOVE zero. Phase measures leak MORE agent identity
                         here. E36's split does not generalise to within-channel phase, and the composite
                         that `UCE_AND_THE_THREE_CHALLENGES.md` proposes for Challenge A would be built on
                         a false premise.
  (b) NO SPLIT        -- the CI includes zero.
  (c) NOT INFORMATIVE -- M2 failed (phase cannot discriminate state, so it cannot be said to leak less),
                         or the placebo reaches the primary.
  (d) SPLIT CONFIRMED -- the CI lies entirely below zero, M2 passed, and the placebo does not reach it.
                         E36's family split extends to within-channel phase measures on a second deposit
                         with different agents, and `bis_sfs` becomes a Challenge A ingredient.

WHAT A CONFIRMATION WOULD NOT LICENCE: any claim that a phase measure PASSES Challenge A. Leaking less than
the amplitude family is a relative statement; passing requires state sensitivity AND agent invariance in
absolute terms, and this deposit cannot supply the within-subject transition Challenge A's first half needs.

    python -m bsde.experiments.e61_drug_identity_families
"""
from __future__ import annotations

import itertools
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import auc, cluster_bootstrap_ci, cv_predict_proba     # noqa: E402
from bsde.experiments.e58_bis_like_index import SUBPARAMS, _f, load             # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e61_drug_identity_families.json")

PHASE = ["bis_sfs", "pac_slow_alpha"]
AMPLITUDE = ["exponent_low", "exponent_high", "whole_head_exponent", "relative_alpha_power",
             "relative_delta_power", "spectral_edge_95", "bis_rbr"]
AGENTS = ("propofol", "sevoflurane")
DEPTH_BAND = (40.0, 60.0)
STATE_BAND = (0.0, 40.0)
MIN_SQI = 50.0
MIN_FINITE = 0.90
STATE_FLOOR = 0.50
REPS = 2000
SEED = 20260731


def _col(grid, sub, rid, name):
    src = sub if name in SUBPARAMS else grid
    return np.array([_f(src[r].get(name, "")) for r in rid], float)


def _oof_abs_auc(x, y, case, rng):
    """|AUC - 0.5| from out-of-fold predictions with cases held out whole."""
    ok = np.isfinite(x)
    if ok.sum() < 50 or len(np.unique(y[ok])) < 2:
        return float("nan")
    p = cv_predict_proba(x[ok], y[ok], case[ok], rng)
    a = auc(y[ok], p)
    return abs(a - 0.5) if np.isfinite(a) else float("nan")


def main() -> int:
    grid, sub, _ = load()
    rid = [r for r in sorted(grid)
           if grid[r].get("status") == "ok"
           and str(grid[r].get("meta_sensor_off", "")).strip().lower() not in ("true", "1")
           and r in sub and sub[r].get("status") == "ok"
           and grid[r].get("meta_agents_present", "") in AGENTS
           and np.isfinite(_f(grid[r].get("meta_bis")))
           and _f(grid[r].get("meta_sqi")) >= MIN_SQI]
    bis = np.array([_f(grid[r]["meta_bis"]) for r in rid])
    agent = np.array([grid[r]["meta_agents_present"] for r in rid])
    case_all = np.array([grid[r]["meta_caseid"] for r in rid])

    depth = (bis >= DEPTH_BAND[0]) & (bis < DEPTH_BAND[1])
    deep = (bis >= STATE_BAND[0]) & (bis < STATE_BAND[1])
    rid_d = [r for r, k in zip(rid, depth) if k]
    y = (agent[depth] == AGENTS[1]).astype(float)
    case = case_all[depth]
    print(f"analysis set: {int(depth.sum())} windows, {len(np.unique(case))} cases "
          f"({int((y == 0).sum())} {AGENTS[0]} / {int((y == 1).sum())} {AGENTS[1]} windows) "
          f"at BIS [{DEPTH_BAND[0]:.0f},{DEPTH_BAND[1]:.0f}) and SQI >= {MIN_SQI:.0f}")

    cands = PHASE + AMPLITUDE
    X = {c: _col(grid, sub, rid_d, c) for c in cands}
    cap = {c: {"finite_fraction": float(np.isfinite(v).mean()),
               "sd": float(np.std(v[np.isfinite(v)])) if np.isfinite(v).any() else float("nan")}
           for c, v in X.items()}
    for c in cands:
        cap[c]["usable"] = bool(cap[c]["finite_fraction"] >= MIN_FINITE
                                and np.isfinite(cap[c]["sd"]) and cap[c]["sd"] > 1e-12)
    m1 = all(cap[c]["usable"] for c in cands)
    for c in cands:
        print(f"   M1 {c:<24s} finite {100 * cap[c]['finite_fraction']:5.1f}%  sd {cap[c]['sd']:.4g}  "
              f"{'usable' if cap[c]['usable'] else 'UNUSABLE'}")
    if not m1:
        print("\nM1 FAILED -- an unusable column cannot leak and would enter a family as a free win. "
              "Verdict ABSENT (rule 31).")
        json.dump({"gate_m1": False, "capability": cap}, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    leak = {c: _oof_abs_auc(X[c], y, case, np.random.default_rng(SEED)) for c in cands}

    # M2 state gate, on the SAME cases: deep vs target band, agent ignored.
    rid_s = [r for r, k in zip(rid, depth | deep) if k]
    ys = np.array([1.0 if _f(grid[r]["meta_bis"]) < DEPTH_BAND[0] else 0.0 for r in rid_s])
    cs = np.array([grid[r]["meta_caseid"] for r in rid_s])
    Xs = {c: _col(grid, sub, rid_s, c) for c in cands}
    state = {c: _oof_abs_auc(Xs[c], ys, cs, np.random.default_rng(SEED)) for c in cands}

    ph_leak = float(np.nanmean([leak[c] for c in PHASE]))
    am_leak = float(np.nanmean([leak[c] for c in AMPLITUDE]))
    ph_state = float(np.nanmean([state[c] for c in PHASE]))
    am_state = float(np.nanmean([state[c] for c in AMPLITUDE]))
    m2 = bool(np.isfinite(ph_state) and np.isfinite(am_state) and am_state > 0
              and ph_state >= STATE_FLOOR * am_state)

    print(f"\n{'candidate':<24s} {'|AUC-.5| agent':>15s} {'|AUC-.5| state':>15s}  family")
    for c in cands:
        print(f"{c:<24s} {leak[c]:>15.4f} {state[c]:>15.4f}  "
              f"{'PHASE' if c in PHASE else 'amplitude'}")
    print(f"\nfamily means   agent leak: phase {ph_leak:.4f}  amplitude {am_leak:.4f}")
    print(f"               state disc: phase {ph_state:.4f}  amplitude {am_state:.4f}   "
          f"M2 {'PASS' if m2 else 'FAIL'} (phase must reach {STATE_FLOOR:.0%} of amplitude)")

    def stat(idx):
        yy, cc = y[idx], case[idx]
        if len(np.unique(yy)) < 2:
            return float("nan")
        r = np.random.default_rng(SEED)
        p = float(np.nanmean([_oof_abs_auc(X[c][idx], yy, cc, r) for c in PHASE]))
        a = float(np.nanmean([_oof_abs_auc(X[c][idx], yy, cc, r) for c in AMPLITUDE]))
        return p - a

    lo, hi, nrep = cluster_bootstrap_ci(stat, case, rng, reps=200)
    obs = ph_leak - am_leak
    print(f"\nPRIMARY  mean |AUC-0.5| phase minus amplitude = {obs:+.4f} [{lo:+.4f}, {hi:+.4f}]  "
          f"({nrep} draws; negative = phase leaks less)")

    # P1 placebo: permute the agent label ACROSS CASES.
    rp = np.random.default_rng(SEED + 1)
    uc = np.unique(case)
    lab = {c: y[case == c][0] for c in uc}
    perm_vals = []
    for _ in range(40):
        vals = rp.permutation([lab[c] for c in uc])
        m = dict(zip(uc, vals))
        yp = np.array([m[c] for c in case])
        r = np.random.default_rng(SEED)
        p = float(np.nanmean([_oof_abs_auc(X[c], yp, case, r) for c in PHASE]))
        a = float(np.nanmean([_oof_abs_auc(X[c], yp, case, r) for c in AMPLITUDE]))
        perm_vals.append(p - a)
    plac = float(np.nanmean(perm_vals))
    print(f"PLACEBO  same statistic, agent permuted across cases = {plac:+.4f} "
          f"(mean of {len(perm_vals)} permutations)")

    # P2 partition control: every 2-vs-7 split of the same nine candidates.
    all_parts = [set(p) for p in itertools.combinations(cands, len(PHASE))]
    diffs = []
    for p in all_parts:
        a_ = [c for c in cands if c not in p]
        diffs.append(float(np.nanmean([leak[c] for c in p])) - float(np.nanmean([leak[c] for c in a_])))
    diffs = np.asarray(diffs, float)
    rank = int((diffs <= obs).sum())
    print(f"P2       real split ranks {rank} of {len(diffs)} same-size partitions "
          f"(1 = most extreme in the predicted direction), p = {rank / len(diffs):.4f}")

    if not np.isfinite(lo):
        verdict = "ABSENT -- the bootstrap could not form an interval."
    elif lo > 0:
        verdict = ("REVERSED -- within-channel phase measures leak MORE agent identity than the amplitude "
                   "family here. E36's split does not generalise from inter-channel phase, and the "
                   "phase+amplitude composite proposed for Challenge A rests on a false premise.")
    elif hi >= 0:
        verdict = ("NO SPLIT -- the interval includes zero. On this deposit the two families are not "
                   "distinguishable by how much agent identity they carry.")
    elif not m2:
        verdict = ("NOT INFORMATIVE -- the phase family cannot discriminate STATE either, so 'leaks less' "
                   "is 'measures less'. This is E36's capability control and it is the difference between "
                   "a result and an artefact.")
    elif plac <= obs:
        verdict = ("NOT INFORMATIVE -- permuting the agent label across cases reproduces the split, so the "
                   "statistic's null level, not the drug, is doing the work.")
    else:
        verdict = ("SPLIT CONFIRMED -- within-channel phase measures leak less agent identity than "
                   "amplitude summaries at matched depth, with state discrimination retained and a "
                   "permutation placebo that does not reach it. E36's family split extends to a second "
                   "instantiation on a different deposit with different agents. This does NOT mean any "
                   "phase measure PASSES Challenge A; leaking less is relative.")
    print(f"\nVERDICT: {verdict}")

    json.dump({"gate_m1": m1, "gate_m2_state": m2, "capability": cap,
               "n_windows": int(depth.sum()), "n_cases": int(len(np.unique(case))),
               "leak_abs_auc": leak, "state_abs_auc": state,
               "family_means": {"phase_leak": ph_leak, "amplitude_leak": am_leak,
                                "phase_state": ph_state, "amplitude_state": am_state},
               "primary": {"obs": obs, "lo": lo, "hi": hi, "reps": nrep},
               "placebo_permuted_agent": plac,
               "partition_rank": {"rank": rank, "n": int(len(diffs)), "p": rank / len(diffs)},
               "verdict": verdict}, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
