#!/usr/bin/env python3
"""E203 — E202 at a pool size that can decide it.

REGISTERED BEFORE ANY DRAW AT THE LARGER POOL.

=========================================================================================================
WHY: E202'S VERDICT WAS ITS OWN MONTE CARLO ERROR
=========================================================================================================
E202 tested lambda = 2 as a single pre-registered hypothesis on E186's 115 VitalDB cases and returned
UNSTABLE at its seed-stability gate. `frac_below` came in at **0.0490, 0.0535, 0.0535** — straddling the
0.05 decision. At a pool of 2,000 the Monte Carlo standard error at p = 0.05 is
sqrt(0.05 * 0.95 / 2000) = **0.0049**, so the spread across seeds IS the sampling error of the estimate and
the binary was a property of the RNG. Rule 46's repair applies exactly: raise the replicate count, which
changes no threshold, cohort, estimand or hypothesis.

**POOL 2,000 -> 40,000.** The standard error falls to 0.0011, so a true value of 0.052 and a true value of
0.048 become distinguishable, which is the whole question. Nothing else in the file moves: the same single
lambda = 2, the same cohort, the same ten features, the same joint rank transform, the same gates, the same
descriptive lambda = 0 row that cannot rescue the verdict, and the same wrong-direction-first branches.

=========================================================================================================
WHAT E202 ALREADY ESTABLISHED, AND THE TWO READINGS E203 MUST SEPARATE
=========================================================================================================
Consistent across all three seeds, and unlicensed by E202's verdict:

    G1b   agent legible in the raw family at k-NN |AUC-0.5| = **+0.4593** vs a floor of +0.1338,
          reproducing E186's published +0.4593 / +0.1444 on the same cases — hiding it is not free
    lambda = 2   state +0.2130, agent +0.0230, frac_below ~ **0.052**
    lambda = 0   state +0.2305, agent +0.0330, frac_below **0.0940 / 0.1040 / 0.0845**, reproducing
                 E186's own 0.0785-0.0888 for the same arm

So the adversarial term helps here too — 0.094 down to 0.052 — but **nowhere near the MGH effect**, where
E200 measured 0.3247 down to 0.0235. Two readings survive and this file exists to separate them:

    (a) lambda = 2 is a real but SMALL effect, and MGH's 0.0235 was inflated by testing four lambdas;
    (b) the MGH cell was a lucky draw, and the modest gain seen here is the true size.

**Note that both readings agree the effect is smaller than E200 reported**, and neither is rescued by this
run — a `frac_below` of 0.048 would be a technical pass at the registered bar and would still be an effect
a twentieth the size of the one that motivated it. That is stated now so a marginal pass cannot later be
written up as confirmation of E200.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G1b or G2 fails.
  (2) UNSTABLE            G3 fails even at 40,000 axes; then the instability is not Monte Carlo error and
                          something else is wrong.
  (3) REVERSED            lambda = 2 leaks MORE than the lambda = 0 reference.
  (4) NOT CONFIRMED       `frac_below` >= 0.05.
  (5) CONFIRMED           `frac_below` < 0.05, on a cohort that never saw the number — and to be reported
                          WITH its effect size beside E200's, never as a bare pass.

**REGISTERED PREDICTION: (4) NOT CONFIRMED, at a value near 0.052.** E202's three seeds average 0.0520 and
their spread is exactly the Monte Carlo error, so the best estimate of the true value already sits above
the bar. This prediction is nearly a point estimate rather than a guess, which is the honest position after
E202 — and it is written down because if the answer comes back at 0.045 I want the surprise on record.
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
OUT = os.path.join(RESULTS, "e203_lambda2_at_resolution.json")
SEED = 20260802

LAMBDA = 2.0                # THE single pre-registered value, from E200 on MGH. No sweep.
LAMBDA_REF = 0.0            # descriptive only; cannot rescue the file
POOL = 40000
MAX_TRIES = 4000000
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
    res = {"experiment": "E203", "lambda": LAMBDA, "n_cases": n,
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
