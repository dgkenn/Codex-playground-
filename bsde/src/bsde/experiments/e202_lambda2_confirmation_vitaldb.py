#!/usr/bin/env python3
"""E202 — lambda = 2 as a SINGLE pre-registered hypothesis, on an independent cohort.

REGISTERED BEFORE ANY VITALDB AXIS HAS BEEN FITTED AT LAMBDA = 2.

=========================================================================================================
WHAT E200 FOUND AND WHAT IT DID NOT EARN
=========================================================================================================
E200 measured E196's fitted axes against 2,000 random unit axes **matched on depth strength** — the control
E186 showed is decisive, because a cluster-permutation floor asks *could this arise with no association*
and cannot ask *would a comparable axis carry less*. On 39 MGH OR cases with a behavioural
loss-of-consciousness label, all gates passing and three seeds stable:

    lambda   state legibility   agent legibility   frac_below (matched random axes)
     0.0         +0.4691            +0.0743                **0.3247**
     0.5         +0.4711            +0.0400                  0.1775
     1.0         +0.4776            +0.0486                  0.2240
     2.0         +0.4698            +0.0057                **0.0235**
     4.0         +0.3922            +0.0886                  0.2497

Two things follow, and only one of them is a result.

**Established:** the PLAIN depth fit is not special. At lambda = 0 the axis sits at the 32nd percentile of
matched random axes, so E196's CONSTRUCTED verdict — correct as registered — must not be read as "a depth
axis already discards the agent". That reading is refuted.

**Not established:** that lambda = 2 is. Four lambdas were tested and one cleared, giving a
multiplicity-corrected value of about **0.094**; and the lambda profile is **not monotone**
(0.32, 0.18, 0.22, 0.024, 0.25), which is not the shape a smooth adversarial trade-off produces and is
exactly the shape one lucky draw produces. The three-seed stability (0.0195-0.0280) says the *estimate* is
solid, not that the *lambda* is.

=========================================================================================================
THIS FILE TESTS ONE NUMBER ON A COHORT THAT HAS NEVER SEEN IT
=========================================================================================================
**lambda = 2.0 and nothing else.** No sweep, no second-best, no "best lambda". The value comes from E200 on
MGH and is applied to **E186's 115 VitalDB cases** — 44 propofol alone, 71 sevoflurane alone, a different
hospital system, a different label (BIS-derived depth rather than behavioural), and a different feature
extraction. If lambda = 2 was a lucky cell in a five-cell table, it has no reason to reappear here.

The internal lambda = 0 reference is computed and reported **for description only**. It is not a second
hypothesis and it cannot rescue the file: if lambda = 2 fails and lambda = 0 succeeds, the verdict is
still NOT CONFIRMED, and that branch is written first so it cannot be re-read afterwards (rule 37).

=========================================================================================================
GATES
=========================================================================================================
G1  E186's cohort, at least 12 cases per arm.
G1b **AGENT ALIVENESS**, as in E196: the arm must be recoverable from the raw feature family above a
    cluster-permutation floor, or hiding it is free (rule 53, catalogue rule 83). E186 measured this on
    the same cases at k-NN +0.4593 against +0.1444, so it is expected to pass — and it is gated anyway,
    because a check that is expected to pass and is not run is how E22 and E29 shipped gates that could
    not fail.
G2  the matched pool must be buildable (>= 200 axes) AND its state legibility must actually match the
    fitted axis's within tolerance. A matched control that is not matched is rule 50's failure.
G3  seed stability: `frac_below` must not straddle 0.05 across three seeds.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G1b or G2 fails.
  (2) UNSTABLE            G3 fails; the pool is too small for the claim.
  (3) REVERSED            lambda = 2 leaks MORE than the lambda = 0 reference. The adversarial term is
                          actively harmful on this cohort and E200's result does not generalise.
  (4) NOT CONFIRMED       `frac_below` at lambda = 2 is >= 0.05. E200's cell was a lucky draw from a
                          five-cell table and the Challenge A positive does not survive its first
                          independent test.
  (5) CONFIRMED           `frac_below` at lambda = 2 is < 0.05 on a cohort that never saw the number.

**REGISTERED PREDICTION: (4) NOT CONFIRMED, held weakly, and the reasoning is given so the weakness is
visible.** For (5): E200's effect was large (0.0235 against a 0.3247 baseline) and the seed spread was
tiny. For (4): one cell of five cleared, the corrected value is 0.094, the profile is non-monotone, and
E186 measured this very cohort's lambda = 0 axis at 0.0785-0.0888 — already close to 0.05, so a large
further gain has less room here. **This project's recorded calibration failure is over-predicting positives
for redundant measures**, so where the evidence is balanced the prediction goes to the null. If (5) comes
back, the Challenge A positive has survived a genuine out-of-cohort test of a single number and should be
written up as such.

    python bsde/src/bsde/experiments/e202_lambda2_confirmation_vitaldb.py
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import auc_abs                                        # noqa: E402
import e186_prespecified_clean_subset as E186                                  # noqa: E402
from e193_adversarial_against_cluster_null import fit_w                        # noqa: E402
from e165_adversarial_challenge_a import ranks                                 # noqa: E402
from e176_entanglement_linear_or_intrinsic import knn_score, perm_floor        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e202_lambda2_confirmation_vitaldb.json")
SEED = 20260802

LAMBDA = 2.0                # THE single pre-registered value, from E200 on MGH. No sweep.
LAMBDA_REF = 0.0            # descriptive only; cannot rescue the file
POOL = 2000
MAX_TRIES = 500000
STATE_TOL = 0.02
SEEDS = (11, 22, 33)
MIN_MATCHED = 200
MIN_PER_ARM = 12
ALIVE_PERMS = 500
ALPHA = 0.05


def legibility(score, label):
    m = np.isfinite(score)
    if len(set(label[m].tolist())) < 2 or len(set(score[m].tolist())) < 2:
        return float("nan")
    return auc_abs(list(label[m]), list(score[m])) - 0.5


def fit_axis(Dm, Lm, arm, lam, seed=0):
    """Leave-one-case-out axis at `lam`, using the ANALYTIC-gradient fit verified in E193.

    E186 called E165's finite-difference version at lam = 0. The objective is identical and the analytic
    gradient was checked against finite differences to 9e-8; using one optimiser for both lambdas here is
    what makes the lambda = 2 versus lambda = 0 comparison internally consistent.
    """
    n = Dm.shape[0]
    Xs = np.vstack([Dm, Lm])
    ys = np.concatenate([np.full(n, 1.0), np.full(n, -1.0)])
    ya = (arm - arm.mean()) / (arm.std() + 1e-12)
    dd, dl = np.empty(n), np.empty(n)
    for i in range(n):
        tr = np.array([k for k in range(n) if k != i])
        trs = np.concatenate([tr, tr + n])
        w = fit_w(Xs[trs], ys[trs], Dm[tr], ya[tr], lam, seed=seed)
        dd[i], dl[i] = Dm[i] @ w, Lm[i] @ w
    return dd, dl


def matched_pool(Dm, Lm, arm, state_lab, target_state, seed, pool=POOL):
    q = np.random.default_rng(seed)
    got, states, tries = [], [], 0
    while len(got) < pool and tries < MAX_TRIES:
        tries += 1
        w = q.standard_normal(Dm.shape[1])
        w /= np.linalg.norm(w) + 1e-12
        s = legibility(np.concatenate([Dm @ w, Lm @ w]), state_lab)
        if not math.isfinite(s) or abs(s - target_state) > STATE_TOL:
            continue
        a = legibility(Dm @ w, arm)
        if math.isfinite(a):
            got.append(abs(a))
            states.append(s)
    return np.asarray(got), np.asarray(states), tries


def score_lambda(Dm, Lm, arm, state_lab, lam, tag):
    dd, dl = fit_axis(Dm, Lm, arm, lam, seed=SEED)
    st = legibility(np.concatenate([dd, dl]), state_lab)
    ag = legibility(dd, arm)
    row = {"lambda": lam, "state": float(st), "agent": float(ag),
           "frac_below": {}, "pool_n": {}, "pool_state_gap": {}, "pool_agent_mean": {}}
    print(f"\n   [{tag}] lambda {lam}: state {st:+.4f}  agent {ag:+.4f}")
    for sd in SEEDS:
        pool, pstates, tries = matched_pool(Dm, Lm, arm, state_lab, st, SEED + sd)
        row["pool_n"][str(sd)] = int(pool.size)
        if pool.size < MIN_MATCHED:
            print(f"      seed {sd}: *** POOL NOT BUILDABLE ({pool.size} in {tries} draws)")
            continue
        row["pool_state_gap"][str(sd)] = float(np.mean(np.abs(pstates - st)))
        row["pool_agent_mean"][str(sd)] = float(pool.mean())
        row["frac_below"][str(sd)] = float((pool < abs(ag)).mean())
        print(f"      seed {sd}: {pool.size} axes in {tries} draws, pool mean |agent| "
              f"{pool.mean():+.4f}, state gap {row['pool_state_gap'][str(sd)]:.4f}, "
              f"frac_below {row['frac_below'][str(sd)]:.4f}", flush=True)
    fbs = list(row["frac_below"].values())
    row["frac_below_mean"] = float(np.mean(fbs)) if fbs else float("nan")
    row["unstable"] = bool(fbs and (min(fbs) < ALPHA) != (max(fbs) < ALPHA))
    return row


def main() -> int:
    print("E202 — lambda = 2 as ONE pre-registered hypothesis, on E186's VitalDB cohort")
    cases = E186.load("exposure")
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids], float)
    cols = E186.ALL
    n = len(ids)
    # JOINTLY rank the stacked deep+light values, then split -- E186's construction exactly. Ranking the
    # two blocks separately would annihilate the deep-versus-light offset, which is the contrast the whole
    # file is about (catalogue rule 73, caught there by a capability gate).
    both = np.column_stack([ranks([cases[c][f"deep_{f}"] for c in ids]
                                  + [cases[c][f"light_{f}"] for c in ids]) for f in cols])
    D, L = both[:n], both[n:]
    state_lab = np.concatenate([np.ones(n), np.zeros(n)])
    res = {"experiment": "E202", "lambda": LAMBDA, "n_cases": n,
           "n_sevo": int(arm.sum()), "n_propofol": int(n - arm.sum()),
           "features": cols, "pool_target": POOL, "seeds": list(SEEDS)}
    g1 = bool(min(int(arm.sum()), int(n - arm.sum())) >= MIN_PER_ARM)
    print(f"G1 COHORT  {n} cases: {int(n - arm.sum())} propofol alone, {int(arm.sum())} sevoflurane "
          f"alone   {'PASS' if g1 else '*** FAIL'}")
    res["g1"] = g1

    print("\nG1b AGENT ALIVENESS — the arm must be recoverable from the RAW family")
    # E186's own aliveness machinery, so the number is comparable to its published +0.4593 / +0.1444
    obs = legibility(knn_score(D, arm), arm)
    f95, _m, _k = perm_floor(D, arm, np.random.default_rng(SEED + 4242), reps=ALIVE_PERMS)
    p = float("nan")
    g1b = bool(np.isfinite(obs) and np.isfinite(f95) and obs > f95)
    print(f"   k-NN |AUC-0.5| = {obs:+.4f} vs cluster-permutation p95 {f95:+.4f} "
          f"({ALIVE_PERMS} draws)   {'PASS' if g1b else '*** FAIL'}   (E186 published +0.4593 vs +0.1444 on these cases)")
    res["g1b"] = {"knn": float(obs), "null_p95": f95, "p": p, "pass": g1b}

    res["primary"] = score_lambda(D, L, arm, state_lab, LAMBDA, "PRIMARY")
    res["reference"] = score_lambda(D, L, arm, state_lab, LAMBDA_REF, "descriptive")

    pr, ref = res["primary"], res["reference"]
    g2 = bool(pr["frac_below"] and all(v >= MIN_MATCHED for v in pr["pool_n"].values())
              and all(v <= STATE_TOL for v in pr["pool_state_gap"].values()))
    res["g2"] = g2
    fb, fb0 = pr["frac_below_mean"], ref["frac_below_mean"]

    print("\n" + "=" * 100)
    if not (g1 and g1b and g2):
        v, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            nm for nm, ok in (("G1 cohort", g1), ("G1b agent aliveness", g1b),
                              ("G2 matched pool", g2)) if not ok))
    elif pr["unstable"]:
        v, why = "UNSTABLE", (f"frac_below straddles {ALPHA} across seeds "
                              f"({sorted(pr['frac_below'].values())}); the pool is too small")
    elif np.isfinite(fb) and np.isfinite(fb0) and fb > fb0:
        v, why = "REVERSED", (
            f"lambda = {LAMBDA} leaks MORE than the lambda = 0 reference "
            f"(frac_below {fb:.4f} against {fb0:.4f}); the adversarial term is actively harmful here and "
            "E200's result does not generalise")
    elif not np.isfinite(fb) or fb >= ALPHA:
        v, why = "NOT CONFIRMED", (
            f"frac_below at lambda = {LAMBDA} is {fb:.4f}, not below {ALPHA} "
            f"(lambda = 0 reference {fb0:.4f}). E200's cell does not reproduce on a cohort that never "
            "saw the number, and the Challenge A positive does not survive its first independent test")
    else:
        v, why = "CONFIRMED", (
            f"frac_below at lambda = {LAMBDA} is {fb:.4f}, below {ALPHA}, on 115 VitalDB cases that never "
            f"saw the number (lambda = 0 reference {fb0:.4f}). E200's MGH result reproduces out of "
            "cohort as a single pre-registered hypothesis")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)
    print("SCOPE: the lambda = 0 row is DESCRIPTIVE and is not a second hypothesis. If lambda = 2 fails\n"
          "  and lambda = 0 succeeds, the verdict is still NOT CONFIRMED.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
