#!/usr/bin/env python3
"""E196 — E195 plus the gate without which "the agent is hidden" cannot be distinguished from "the agent
was never there". E195 is CLOSED UNRUN and superseded by this file.

REGISTERED BEFORE ANY RUN OF THIS FILE. The provenance is stated plainly below because part of the reason
for this gate was visible in E193's partial output, and hiding that would be worse than the delay.

=========================================================================================================
WHY E195 IS SUPERSEDED BEFORE IT RAN
=========================================================================================================
E193 (E195's predecessor, whose negative capability gate failed and whose verdict is NOT INTERPRETABLE)
printed its real-data rows before E195 was launched, and they show the success rule firing at
**lambda = 0**: state legibility +0.4698, agent legibility +0.0914, cluster-permutation floor +0.1744.
The axis fitted with **no adversarial term at all** already sits below the agent floor.

There are two readings and the design as registered could not tell them apart:

  (a) depth and agent identity really are separable in this family on this cohort, or
  (b) **the agent was never legible in this family on this cohort**, so nothing had to be hidden.

Reading (b) is not speculative here. E154 ran on this exact cohort and found the MEDIAN feature
identifying the agent at |AUC-0.5| = 0.1000, with only `rel_theta` and the nuisance variable
`recording duration` (0.3771) standing above. **A cohort where the agent is barely legible makes "the
agent is hidden" free**, which is rule 69's failure — absence of power reported as measured absence — and
rule 53's, which this project already wrote down as "THE INCUMBENT MUST BE ALIVE" in E33 and then did not
carry across to E61.

=========================================================================================================
THE ADDED GATE, AND WHY ADDING IT NOW IS THE SAFE DIRECTION
=========================================================================================================
    **G1b  AGENT ALIVENESS.** Before any axis is fitted, the agent must be legible in the RAW feature
          family: a leave-one-case-out k-nearest-neighbour classifier over the eleven unconscious-block
          features must identify the arm above the 95th percentile of a cluster-level permutation null
          over case arm labels. **If it cannot, no verdict about hiding the agent is issued.**

This gate can only make the experiment harder to pass, and it was added after seeing a PASS in the
predecessor's partial output. That is the one direction in which a mid-flight change is safe and needs no
permission — the same call CLAUDE.md records for E75, where a broken branch was tightened after a pass —
and it is the opposite of the move `DISCOVERY_LOOP.md` §2 forbids, which is loosening a gate after a
failure. **E195 is marked CLOSED and unrun rather than silently edited**, so the ledger's denominator
still counts the design that was superseded.

Everything else is E195's, unchanged, which is E193's with the negative control repaired: the same
cohort, features, fixed-epoch summarisation, leave-one-case-out objective, 80 % state-retention
tolerance, per-lambda cluster-permutation floor, and the G0 measurement gate that refuses a synthetic
control lacking the separability it is built to have.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) CONTROL REFUSED       G0: the synthetic systems lack their intended separability. Nothing is run.
  (2) AGENT NOT ALIVE       G1b: the agent is not legible in the raw family, so hiding it is free and
                            **no verdict about Challenge A is issued on this cohort** — the result is a
                            statement about the cohort's power, not about separability.
  (3) NOT INTERPRETABLE     G1, G2a, G2b or G4 fails.
  (4) VACUOUS               the success rule fires at lambda = 0, with no adversarial term. Reported as
                            E165's failure mode, NOT as a construction.
  (5) NOT CONSTRUCTED       no lambda > 0 satisfies the success rule.
  (6) CONSTRUCTED           some lambda > 0 does, on a cohort where the agent was demonstrably legible.

**REGISTERED PREDICTION: (2) AGENT NOT ALIVE.** This is a change from E193's and E195's prediction of NOT
CONSTRUCTED, and the reason is the evidence above rather than a preference: E154's median feature sits at
0.1000 on this cohort against a cluster-null 95th percentile near 0.17-0.19, and E193's fitted axis at
lambda = 0 already lands below the floor. If instead G1b passes, I predict (5) for the reasons E193 gave —
E161 found two spectral features each identifying the agent far above a cluster null on VitalDB, and E186
finds the agent legible in every pre-specified subset of the same family.

**If (2) is the outcome, it is a finding about the deposit and not a null result about Challenge A**, and
it says something the programme needs: the cohort with the non-circular BEHAVIOURAL state label is too
small or too homogeneous to carry an agent contrast, so Challenge A's two reachable cohorts are bounded
for opposite and now fully-measured reasons — VitalDB has the agent contrast and a circular depth axis,
MGH has the honest depth label and no agent contrast.

    python bsde/src/bsde/experiments/e196_adversarial_with_agent_aliveness.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import auc_abs                                        # noqa: E402
from e154_lambda_on_mgh_or import FEATURES                                     # noqa: E402
from e165_adversarial_challenge_a import build                                 # noqa: E402
from e193_adversarial_against_cluster_null import (CORR_MAX, LAMBDAS, MIN_PER_ARM,   # noqa: E402
                                                   PERMS, STATE_TOL, add_duration,
                                                   blocks, evaluate)
from e195_adversarial_with_verified_control import (COS_ENTANGLED_MIN,          # noqa: E402
                                                    COS_SEPARABLE_MAX,
                                                    NULL_DRAWS_CONTROL,
                                                    synthetic, sweep)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e196_adversarial_agent_aliveness.json")
SEED = 20260801
KNN_K = 5
ALIVE_PERMS = 500


def knn_legibility(X, arm, k=KNN_K):
    """Leave-one-case-out k-NN agent legibility over the raw feature block, as |AUC - 0.5|.

    Multivariate on purpose: the question G1b asks is whether the arm is recoverable from the FAMILY,
    not from any one feature. A per-feature test would miss an arm that is legible only in combination,
    and that is exactly the arm an adversarial axis would have to hide.
    """
    X = np.asarray(X, float)
    n = len(arm)
    D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(D, np.inf)
    sc = np.empty(n)
    for i in range(n):
        nb = np.argsort(D[i])[:k]
        sc[i] = float(np.mean(arm[nb]))
    return auc_abs(list(arm.astype(int)), list(sc)) - 0.5


def main() -> int:
    print("E196 — Challenge A constructively, with BOTH capability controls and an AGENT-ALIVENESS gate")
    res = {"experiment": "E196", "lambdas": list(LAMBDAS), "perms": PERMS,
           "state_tol": STATE_TOL, "features": FEATURES, "supersedes": "E195 (closed unrun)"}

    cases, _miss = add_duration(build())
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids], float)
    n_mix, n_pro = int(arm.sum()), int(len(arm) - arm.sum())
    g1 = bool(min(n_mix, n_pro) >= MIN_PER_ARM)
    print(f"G1 COHORT  {len(ids)} OR cases: {n_pro} propofol alone, {n_mix} mixed   "
          f"{'PASS' if g1 else '*** FAIL'}")
    res.update({"n_cases": len(ids), "n_mixed": n_mix, "n_propofol": n_pro, "g1": g1})

    S, U = blocks(cases, ids)

    print("\nG1b AGENT ALIVENESS — the arm must be recoverable from the RAW family before hiding it "
          "means anything")
    obs = knn_legibility(U, arm)
    rng = np.random.default_rng(SEED + 4242)
    nul = np.array([knn_legibility(U, rng.permutation(arm)) for _ in range(ALIVE_PERMS)])
    f95 = float(np.quantile(nul[np.isfinite(nul)], 0.95))
    p = float(np.mean(nul >= obs))
    g1b = bool(np.isfinite(obs) and obs > f95)
    print(f"   k-NN(k={KNN_K}) |AUC-0.5| = {obs:+.4f} vs cluster-permutation p95 {f95:+.4f} "
          f"({ALIVE_PERMS} draws), p = {p:.4f}   {'PASS' if g1b else '*** FAIL'}")
    res["g1b"] = {"knn": float(obs), "null_p95": f95, "p": p, "pass": g1b}

    print("\nG0 CONTROL VERIFICATION — the constructed systems must HAVE their intended separability")
    Sp, Up, ap, cos_sep = synthetic(len(ids), False, np.random.default_rng(SEED + 1))
    Se, Ue, ae, cos_ent = synthetic(len(ids), True, np.random.default_rng(SEED + 2))
    g0 = bool(cos_sep < COS_SEPARABLE_MAX and cos_ent >= COS_ENTANGLED_MIN)
    print(f"   |cos(ws, wa)|  separable {cos_sep:.4f} (< {COS_SEPARABLE_MAX});  "
          f"entangled {cos_ent:.4f} (>= {COS_ENTANGLED_MIN})   {'PASS' if g0 else '*** FAIL'}")
    res["g0"] = {"cos_separable": cos_sep, "cos_entangled": cos_ent, "pass": g0}

    if not g0:
        res["verdict"], res["why"] = "CONTROL REFUSED", (
            "the synthetic systems lack the separability they are built to have (rule 77)")
    elif not g1b:
        res["verdict"], res["why"] = "AGENT NOT ALIVE", (
            f"the arm is not recoverable from the raw eleven-feature family: k-NN |AUC-0.5| = {obs:+.4f} "
            f"against a cluster-permutation 95th percentile of {f95:+.4f} (p = {p:.4f}). Hiding an agent "
            "that is not legible is free, so NO verdict about separability is issued. E154 measured the "
            "median single feature at 0.1000 on this cohort, which is the same message. This is a "
            "statement about the deposit's power, not about Challenge A")
    if res.get("verdict"):
        json.dump(res, open(OUT, "w"), indent=2)
        print("\n" + "=" * 100)
        print(f"VERDICT: {res['verdict']}\n  {res['why']}")
        print("=" * 100)
        return 0

    print("\nG2a POSITIVE capability — independent directions, a separating axis EXISTS")
    tp, pos_p, _z, s0p = sweep(Sp, Up, ap, "sep", NULL_DRAWS_CONTROL, SEED)
    g2a = bool(np.isfinite(s0p) and s0p > 0.20)
    print(f"   lam=0 state {s0p:+.4f}   {'PASS' if g2a else '*** FAIL'}  (separating: {pos_p or 'none'})")

    print("\nG2b NEGATIVE capability — ONE direction carries both, so NO axis can separate them")
    te, pos_e, _z2, s0e = sweep(Se, Ue, ae, "ent", NULL_DRAWS_CONTROL, SEED)
    g2b = not pos_e
    print(f"   {'PASS — the success rule can FAIL' if g2b else '*** FAIL — unfalsifiable: ' + str(pos_e)}")
    res.update({"g2a": g2a, "g2b": g2b, "separable_control": tp, "entangled_control": te})

    print("\nREAL DATA — MGH OR, behavioural loss-of-consciousness label")
    dur = np.array([cases[c]["n_epochs"] for c in ids], float)
    tab, pos, zero, s0 = sweep(S, U, arm, "real", PERMS, SEED)
    res.update({"table": tab, "state_lam0": s0})

    _s, _a, ax = evaluate(S, U, arm, pos[0] if pos else 0.0, seed=SEED)
    m = np.isfinite(dur) & np.isfinite(ax)
    rho = (float(np.corrcoef(np.argsort(np.argsort(dur[m])), np.argsort(np.argsort(ax[m])))[0, 1])
           if m.sum() > 10 else float("nan"))
    g4 = bool(not np.isfinite(rho) or abs(rho) < CORR_MAX)
    res["g4_axis_vs_duration_rho"], res["g4"] = rho, g4
    print(f"\nG4 axis vs recording length: rho = {rho:+.4f}   {'PASS' if g4 else '*** FAIL'}")

    print("\n" + "=" * 100)
    if not (g1 and g2a and g2b and g4):
        v, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1 cohort", g1), ("G2a positive", g2a),
                            ("G2b negative", g2b), ("G4 duration", g4)) if not ok))
    elif zero and not pos:
        v, why = "VACUOUS", ("the success rule fires only at lambda = 0, with no adversarial term. "
                             "That is E165's failure mode and it is not a construction")
    elif pos:
        v, why = "CONSTRUCTED", (
            f"lambda {pos} keeps >= {STATE_TOL:.0%} of the lambda=0 state legibility ({s0:+.4f}) while "
            f"putting agent legibility below the cluster-permutation floor, on a cohort where the agent "
            f"WAS legible in the raw family ({obs:+.4f} vs {f95:+.4f})")
    else:
        v, why = "NOT CONSTRUCTED", (
            f"no lambda keeps >= {STATE_TOL:.0%} of the lambda=0 state legibility ({s0:+.4f}) while "
            "dropping agent legibility below the cluster-permutation floor")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
