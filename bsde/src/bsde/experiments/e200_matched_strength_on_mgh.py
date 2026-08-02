#!/usr/bin/env python3
"""E200 — is E196's separating axis better than a RANDOM axis of the same depth strength?

REGISTERED BEFORE ANY MATCHED POOL HAS BEEN DRAWN.

=========================================================================================================
WHY E196'S POSITIVE NEEDS THIS BEFORE IT IS BELIEVED
=========================================================================================================
E196 returned CONSTRUCTED — the first constructive Challenge A positive in this programme — on 39 MGH OR
cases with a **behavioural** loss-of-consciousness label. Every gate passed, including a negative
capability gate proving the success rule can fail, and lambdas 0.5 to 4.0 kept at least 80 % of the
lambda = 0 state legibility (+0.4698) while agent legibility fell below the per-lambda cluster-permutation
floor (+0.1744 to +0.3382).

**Two things about it are unresolved, and the same control settles both.**

1. **The success rule also fires at lambda = 0**, with no adversarial term in the objective: state
   +0.4698, agent +0.0914, floor +0.1744. So the adversarial machinery is not load-bearing, and what was
   actually measured is that a plain depth-discriminative fit already carries little agent information.
2. **A single linear direction can carry far less of a multivariate signal than a k-NN over eleven
   dimensions finds.** G1b measured the arm at k-NN |AUC-0.5| = +0.4343 in the raw block; the fitted axis
   carries +0.0914. Part of that drop may be **dimensionality rather than construction** — any one
   direction would lose most of it.

The cluster-permutation floor cannot separate these, because it asks *could this legibility arise with no
association*, not *is this less than a comparable axis would carry*. **E186 already ran the control that
can, on VitalDB, and it changed the reading of that experiment completely**: three axes all sat below
their permutation floors, and only the matched-strength pool revealed that the one built from
individually-non-leaking features was **indistinguishable from a random axis** (leaking less than 39 % of
matched draws) while the other two sat at the 8th-9th percentile.

=========================================================================================================
THE CONTROL, WHICH IS E186'S, APPLIED TO E196'S COHORT
=========================================================================================================
Draw random unit weight vectors over the same eleven features. Keep those whose **state** legibility
matches the fitted axis's within `STATE_TOL`, so the pool is matched on exactly the quantity that would
otherwise explain a low agent score. Report the fraction of that pool whose |agent legibility| is **below**
the fitted axis's.

    **P1  `frac_below` for the lambda = 0 axis**, and for each lambda that E196 reported as succeeding.

A fitted axis that is genuinely constructed to discard the agent should sit far into the lower tail. One
that is merely a direction in an eleven-dimensional space should sit near the middle. **`frac_below` near
0.5 refutes the construction reading without touching E196's verdict**, which was correct as registered.

Three seeds, because E182's first verdict on this same statistic was a Monte Carlo artefact at 200 axes
and moved when the pool was raised to 2,000 (rule 46). `POOL` is 2,000 here for the same reason.

=========================================================================================================
GATES
=========================================================================================================
G1  the pool must be BUILDABLE: at least `MIN_MATCHED` random axes matching the target state legibility
    within tolerance, for every axis tested. E186 reports this and it can fail — a fitted axis whose state
    legibility is unreachable by random directions has no matched comparison, and that is a finding rather
    than a pass.
G2  **the pool's own state legibility must actually match**: mean |state(pool) − state(fitted)| below
    `STATE_TOL`. Gated rather than assumed, because a matched control that is not matched is the failure
    rule 50 is about — a baseline of the wrong shape carries the authority of a measurement.
G3  seed stability: `frac_below` must not straddle the 0.05 decision across the three seeds. If it does,
    the pool is too small for the claim and that is reported instead of a verdict (rule 46).

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1 or G2 fails; no matched comparison exists.
  (2) UNSTABLE            G3 fails; `frac_below` moves across the decision boundary between seeds.
  (3) NOT BETTER THAN RANDOM   `frac_below` >= 0.05 for every succeeding lambda INCLUDING lambda = 0.
                          E196's low agent legibility is then a property of projecting eleven dimensions
                          onto one, and the CONSTRUCTED verdict — correct as registered — must be read as
                          "already separable" with no claim that the axis is special.
  (4) BETTER THAN RANDOM, WITHOUT AN ADVERSARY   `frac_below` < 0.05 at lambda = 0. The depth objective
                          alone finds a direction that discards the agent better than chance directions do.
  (5) THE ADVERSARY ADDS  `frac_below` at some lambda > 0 is below 0.05 **and** below the lambda = 0 value
                          by more than the seed spread. Only this licenses the adversarial term.

**REGISTERED PREDICTION: (3) NOT BETTER THAN RANDOM.** E186 measured 0.0785 and 0.0888 for its two
comparable arms on a larger cohort (115 cases against 39), both above 0.05, and this cohort has a third of
the cases with the same feature count. Predicting (4) or (5) would be predicting a cleaner result on less
data than the programme has ever obtained on more. **If (3) is the outcome it does not overturn E196 —
it fixes what E196 may be claimed to show**, and the pair of experiments together is the answer to
Challenge A on this cohort: depth is separable from agent identity in the sense that a depth axis does not
carry the agent, and there is no evidence that any particular construction is responsible.

    python bsde/src/bsde/experiments/e200_matched_strength_on_mgh.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from e154_lambda_on_mgh_or import FEATURES                                     # noqa: E402
from e165_adversarial_challenge_a import build                                 # noqa: E402
from e193_adversarial_against_cluster_null import (LAMBDAS, add_duration,      # noqa: E402
                                                   blocks, evaluate, legibility)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
E196_JSON = os.path.join(RESULTS, "e196_adversarial_agent_aliveness.json")
OUT = os.path.join(RESULTS, "e200_matched_strength_on_mgh.json")
SEED = 20260802

POOL = 2000              # E182's verdict on this statistic moved between 200 and 2,000 axes (rule 46)
MAX_TRIES = 500000
STATE_TOL = 0.02         # a matched axis's state legibility must be within this of the fitted axis's
SEEDS = (11, 22, 33)
MIN_MATCHED = 200
ALPHA = 0.05


def matched_pool(S, U, arm, state_lab, target_state, seed, pool=POOL):
    """Random unit axes whose STATE legibility matches the fitted axis's; return their agent legibility."""
    q = np.random.default_rng(seed)
    got, states, tries = [], [], 0
    while len(got) < pool and tries < MAX_TRIES:
        tries += 1
        w = q.standard_normal(S.shape[1])
        w /= np.linalg.norm(w) + 1e-12
        s = legibility(np.concatenate([S @ w, U @ w]), state_lab)
        if not np.isfinite(s) or abs(s - target_state) > STATE_TOL:
            continue
        a = legibility(U @ w, arm)
        if np.isfinite(a):
            got.append(abs(a))
            states.append(s)
    return np.asarray(got), np.asarray(states), tries


def main() -> int:
    print("E200 — is E196's axis better than a RANDOM axis of the same depth strength?")
    cases, _miss = add_duration(build())
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids], float)
    S, U = blocks(cases, ids)
    state_lab = np.concatenate([np.zeros(len(ids)), np.ones(len(ids))])
    res = {"experiment": "E200", "n_cases": len(ids), "pool_target": POOL,
           "state_tol": STATE_TOL, "seeds": list(SEEDS), "features": FEATURES, "axes": {}}
    print(f"   {len(ids)} cases, {int(arm.sum())} mixed / {int(len(arm) - arm.sum())} propofol alone")

    try:
        e196 = json.load(open(E196_JSON))
        succeeding = [float(k) for k, v in e196["table"].items() if v["succeeds"]]
    except Exception:                                                          # noqa: BLE001
        e196, succeeding = None, list(LAMBDAS)
    tested = sorted(set([0.0] + succeeding))
    print(f"   lambdas tested (E196's succeeding set plus 0.0): {tested}")

    all_buildable, all_matched, unstable = True, True, []
    for lam in tested:
        st, ag, ax = evaluate(S, U, arm, lam, seed=SEED)
        row = {"state": float(st), "agent": float(ag), "frac_below": {}, "pool_n": {},
               "pool_agent_mean": {}, "pool_state_gap": {}}
        print(f"\n   lambda {lam:>4.1f}: fitted state {st:+.4f}  agent {ag:+.4f}")
        for sd in SEEDS:
            pool, pstates, tries = matched_pool(S, U, arm, state_lab, st, SEED + sd)
            if pool.size < MIN_MATCHED:
                all_buildable = False
                print(f"      seed {sd}: *** POOL NOT BUILDABLE ({pool.size} in {tries} draws)")
                row["pool_n"][str(sd)] = int(pool.size)
                continue
            gap = float(np.mean(np.abs(pstates - st)))
            fb = float((pool < abs(ag)).mean())
            row["frac_below"][str(sd)] = fb
            row["pool_n"][str(sd)] = int(pool.size)
            row["pool_agent_mean"][str(sd)] = float(pool.mean())
            row["pool_state_gap"][str(sd)] = gap
            if gap > STATE_TOL:
                all_matched = False
            print(f"      seed {sd}: {pool.size} axes in {tries} draws, pool mean |agent| "
                  f"{pool.mean():+.4f}, state gap {gap:.4f}, frac_below {fb:.4f}", flush=True)
        fbs = list(row["frac_below"].values())
        if fbs and (min(fbs) < ALPHA) != (max(fbs) < ALPHA):
            unstable.append(lam)
        row["frac_below_mean"] = float(np.mean(fbs)) if fbs else float("nan")
        res["axes"][str(lam)] = row

    res["g1_buildable"], res["g2_matched"], res["g3_unstable"] = all_buildable, all_matched, unstable
    zero = res["axes"]["0.0"]
    fb0 = zero.get("frac_below_mean", float("nan"))
    pos = {k: v["frac_below_mean"] for k, v in res["axes"].items()
           if float(k) > 0 and np.isfinite(v.get("frac_below_mean", np.nan))}
    spread = float(np.std(list(zero["frac_below"].values()))) if zero["frac_below"] else float("nan")

    print("\n" + "=" * 100)
    if not all_buildable or not all_matched:
        v, why = "NOT INTERPRETABLE", (
            "no matched comparison exists: " + ("the pool could not be built for some axis"
                                                if not all_buildable else
                                                "the pool's state legibility does not match the "
                                                "fitted axis's (rule 50 — a baseline of the wrong shape)"))
    elif unstable:
        v, why = "UNSTABLE", (f"frac_below straddles {ALPHA} across seeds at lambda {unstable}; the pool "
                              "is too small for the claim (rule 46)")
    elif np.isfinite(fb0) and fb0 >= ALPHA and all(x >= ALPHA for x in pos.values()):
        v, why = "NOT BETTER THAN RANDOM", (
            f"frac_below is {fb0:.4f} at lambda = 0 and "
            f"{ {k: round(x, 4) for k, x in pos.items()} } at the succeeding lambdas, none below "
            f"{ALPHA}. E196's low agent legibility is a property of projecting {len(FEATURES)} dimensions "
            "onto one; its CONSTRUCTED verdict was correct as registered and must be read as 'already "
            "separable', with no claim that the axis is special")
    elif pos and min(pos.values()) < ALPHA and np.isfinite(fb0) and \
            min(pos.values()) < fb0 - max(spread, 1e-9):
        best = min(pos, key=pos.get)
        v, why = "THE ADVERSARY ADDS", (
            f"lambda {best} reaches frac_below {pos[best]:.4f}, below {ALPHA} and below lambda = 0's "
            f"{fb0:.4f} by more than the seed spread ({spread:.4f}); the adversarial term is doing work")
    elif np.isfinite(fb0) and fb0 < ALPHA:
        v, why = "BETTER THAN RANDOM, WITHOUT AN ADVERSARY", (
            f"the plain depth objective reaches frac_below {fb0:.4f} at lambda = 0, below {ALPHA}, and no "
            "lambda > 0 improves on it beyond the seed spread — the depth fit alone finds a direction "
            "that discards the agent better than chance directions do")
    else:
        v, why = "NOT BETTER THAN RANDOM", (
            f"frac_below {fb0:.4f} at lambda = 0 with succeeding lambdas at "
            f"{ {k: round(x, 4) for k, x in pos.items()} }")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)
    print("SCOPE: this file does not revisit E196's verdict, which was correct as registered. It settles\n"
          "  what that verdict may be CLAIMED to show.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
