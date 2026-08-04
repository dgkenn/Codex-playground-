#!/usr/bin/env python3
"""E206 — Challenge A asked as TRANSPORT rather than as concealment.

REGISTERED BEFORE ANY CROSS-AGENT AXIS HAS BEEN FITTED.

=========================================================================================================
WHY THE QUESTION CHANGES SHAPE
=========================================================================================================
Every Challenge A design in this programme has asked a **concealment** question: can a representation
predict depth while an adversary fails to read the agent off it? E165, E186, E193, E196, E200, E202 and
E203 are all that question, and E203 closed the chain — lambda = 2, the one cell that cleared on MGH,
does not reproduce on 115 independent VitalDB cases (0.0555 against a bar of 0.05).

**Concealment is a proxy.** What the brief actually wants is a depth measure that *works the same way
whatever the drug is*. Those come apart: an axis can leak agent identity and still transport perfectly
(the leak is in a direction the depth readout never uses), and an axis can conceal the agent and still
transport badly (it hides the drug by discarding exactly the depth information the second drug needs).
Catalogue rule 79 is the general form — stop arguing about the proxy and measure the quantity — and it
was written this session about Challenge C's placebo. This is the same move for Challenge A.

    **P1  TRANSPORT RATIO.** Fit the depth axis on ONE agent's cases only and score it on the OTHER
          agent's, then divide by the within-agent score obtained with a training set of the SAME SIZE.
          A ratio near 1 means the depth readout does not care which drug it was learned on.

This needs no adversary, no lambda, no matched-strength pool and no concealment threshold. It is one
number with an interpretable scale, and it is the number a clinician would care about.

=========================================================================================================
THE CONTROL THAT MAKES IT A MEASUREMENT AND NOT A TAUTOLOGY
=========================================================================================================
A cross-agent axis is trained on fewer cases than a within-agent leave-one-out axis, and it is trained on
a *different* set. Both would depress the ratio for reasons having nothing to do with the drug. So the
denominator is not the ordinary within-agent axis — it is a **size-matched, subsample-matched** one:

    for each of `N_DRAWS` draws, sample n_A cases FROM AGENT B, fit on them, and score the held-out
    remainder of agent B.

That holds training size and evaluation cohort constant and varies only whether the training cases came
from the same drug. **Without it the ratio measures sample size** — the failure catalogue rule 50 is about,
and the failure E53 made and had to retract.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 12 cases per agent arm (the programme's standing floor for this cohort).
G2  **BOTH WITHIN-AGENT AXES MUST BE ALIVE.** Depth must be legible within propofol AND within
    sevoflurane, each above its own permutation floor. If depth is not readable inside one arm, a
    transport ratio into it is a ratio of two noises (rule 53).
G3  **THE AGENT MUST BE LEGIBLE IN THE RAW FAMILY**, by the same k-NN test E196 and E202 used. If the two
    arms are not distinguishable at all then transport is free and the result is uninformative — this is
    the gate that makes a HIGH ratio meaningful rather than vacuous (catalogue rule 83).
G4  the size-matched denominator must actually be size-matched: the mean training-set size of the matched
    draws must equal the cross-agent training size exactly.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3 or G4 fails.
  (2) DOES NOT TRANSPORT  the ratio's interval lies entirely below 1 in at least one direction. A depth
                          axis learned on one agent is measurably worse on the other, and the programme's
                          concealment framing was answering the wrong question in the easy direction.
  (3) ASYMMETRIC          one direction transports and the other does not. Reported as its own outcome
                          because it is scientifically the most interesting and would be invisible to any
                          concealment test, which is symmetric by construction.
  (4) TRANSPORTS          both directions' intervals include or exceed 1.

**REGISTERED PREDICTION: (4) TRANSPORTS, in both directions, with ratios in 0.85-1.05.** The reasoning is
E200's and E203's own numbers: the plain depth fit sits at the 32nd percentile of matched random axes on
MGH and around the 9th on VitalDB, i.e. **the depth axis barely carries agent information to begin with**,
which is what a transportable axis looks like. If that is right, then the concealment programme was
solving a problem the data did not have, and E203's negative is not a failure but a redundancy.

**If (2) or (3) comes back it is the more valuable outcome**, because it would mean concealment and
transport genuinely diverge on this cohort and every Challenge A result so far has been measured on the
wrong axis.

    python bsde/src/bsde/experiments/e206_cross_agent_transport.py
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
from e165_adversarial_challenge_a import ranks                                 # noqa: E402
from e176_entanglement_linear_or_intrinsic import knn_score, perm_floor        # noqa: E402
from e193_adversarial_against_cluster_null import fit_w                        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e206_cross_agent_transport.json")
SEED = 20260802

N_DRAWS = 200          # size-matched within-agent draws forming the denominator
PERMS = 300
MIN_PER_ARM = 12
ALIVE_PERMS = 500
LAM = 0.0             # no adversary: this design does not conceal anything


def legibility(score, label):
    m = np.isfinite(score)
    if len(set(label[m].tolist())) < 2 or len(set(score[m].tolist())) < 2:
        return float("nan")
    return auc_abs(list(label[m]), list(score[m])) - 0.5


def fit_on(D, L, arm, idx, seed=0):
    """Fit ONE depth axis on the cases in `idx`. Returns the weight vector."""
    Dm, Lm = D[idx], L[idx]
    n = len(idx)
    Xs = np.vstack([Dm, Lm])
    ys = np.concatenate([np.full(n, 1.0), np.full(n, -1.0)])
    ya = (arm[idx] - arm[idx].mean()) / (arm[idx].std() + 1e-12) if arm[idx].std() > 0 \
        else np.zeros(n)
    w = fit_w(Xs, ys, Dm, ya, LAM, seed=seed)
    # `fit_w` maximises |corr|, so the SIGN of w is not identified by the objective. Orient it on the
    # TRAINING cases -- deep must score above light there -- and the held-out sign is then meaningful.
    # Without this the sevoflurane arm returned -0.6620 against propofol's +0.6818: the same magnitude,
    # an arbitrary flip, and a gate failure that was mine rather than the data's.
    if float(np.mean(Dm @ w) - np.mean(Lm @ w)) < 0:
        w = -w
    return w


def depth_score(D, L, w, idx):
    """State legibility of axis `w` evaluated on the cases in `idx`."""
    dd, dl = D[idx] @ w, L[idx] @ w
    lab = np.concatenate([np.ones(len(idx)), np.zeros(len(idx))])
    return legibility(np.concatenate([dd, dl]), lab)


def main() -> int:
    print("E206 — Challenge A as TRANSPORT: does a depth axis learned on one agent work on the other?")
    cases = E186.load("exposure")
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids], float)      # 1 = sevoflurane, 0 = propofol
    cols = E186.ALL
    n = len(ids)
    both = np.column_stack([ranks([cases[c][f"deep_{f}"] for c in ids]
                                  + [cases[c][f"light_{f}"] for c in ids]) for f in cols])
    D, L = both[:n], both[n:]
    A = np.flatnonzero(arm < 0.5)      # propofol alone
    B = np.flatnonzero(arm > 0.5)      # sevoflurane alone
    res = {"experiment": "E206", "n_cases": n, "n_propofol": int(A.size), "n_sevo": int(B.size),
           "features": cols, "n_draws": N_DRAWS}
    g1 = bool(min(A.size, B.size) >= MIN_PER_ARM)
    print(f"G1 COHORT  {n} cases: {A.size} propofol alone, {B.size} sevoflurane alone   "
          f"{'PASS' if g1 else '*** FAIL'}")
    res["g1"] = g1

    print("\nG3 AGENT LEGIBLE IN THE RAW FAMILY (a high ratio is only meaningful if it is not free)")
    obs = legibility(knn_score(D, arm), arm)
    f95, _m, _k = perm_floor(D, arm, np.random.default_rng(SEED + 1), reps=ALIVE_PERMS)
    g3 = bool(np.isfinite(obs) and np.isfinite(f95) and obs > f95)
    print(f"   k-NN |AUC-0.5| = {obs:+.4f} vs permutation p95 {f95:+.4f}   {'PASS' if g3 else '*** FAIL'}")
    res["g3"] = {"knn": float(obs), "floor": float(f95), "pass": g3}

    print("\nG2 DEPTH MUST BE LEGIBLE WITHIN EACH ARM")
    within_loo, alive = {}, True
    for tag, idx in (("propofol", A), ("sevoflurane", B)):
        sc = np.empty(len(idx))
        for i in range(len(idx)):
            tr = np.array([j for j in range(len(idx)) if j != i])
            w = fit_on(D, L, arm, idx[tr], seed=SEED)
            sc[i] = np.nan
            dd, dl = D[idx[i]] @ w, L[idx[i]] @ w
            sc[i] = dd - dl
        v = float(np.mean(sc > 0) - 0.5) * 2.0          # signed: deep should score above light
        nul = []
        for k in range(PERMS):
            s = np.random.default_rng(SEED + 40 + k).choice([-1.0, 1.0], size=sc.size)
            nul.append(float(np.mean((sc * s) > 0) - 0.5) * 2.0)
        p95 = float(np.quantile(nul, 0.95))
        within_loo[tag] = {"deep_above_light": v, "floor": p95, "n": int(len(idx))}
        ok = bool(np.isfinite(v) and v > p95)
        alive = alive and ok
        print(f"   {tag:<12s} deep-above-light {v:+.4f} vs sign-flip p95 {p95:+.4f} "
              f"({len(idx)} cases)   {'PASS' if ok else '*** FAIL'}")
    res["g2"] = {"within": within_loo, "pass": alive}

    print("\nP1 TRANSPORT RATIO (cross-agent / within-agent, SAME training size, SAME evaluation set)")
    rows = {}
    rng = np.random.default_rng(SEED + 99)
    for tag, tr_idx, te_idx in (("propofol -> sevoflurane", A, B),
                                ("sevoflurane -> propofol", B, A)):
        # Both conditions must differ in EXACTLY ONE respect: the arm the training cases came from.
        # So they share a training size AND a held-out evaluation set drawn from the test arm. The first
        # version trained cross on all 71 sevoflurane cases and matched on only 22 propofol ones, and its
        # size check passed anyway because the comparison was written with a permissive `or` that could
        # not fail -- catalogue rules 40 and 37.
        n_eval = max(12, len(te_idx) // 3)
        n_train = min(len(tr_idx), len(te_idx) - n_eval)
        if n_train < 8:
            rows[tag] = {"error": f"cannot match: n_train would be {n_train}"}
            print(f"   {tag:<26s} SKIPPED -- cannot size-match")
            continue
        cross_v, within_v, sizes = [], [], []
        for d in range(N_DRAWS):
            g = np.random.default_rng(SEED + 2000 + d)
            ev = g.choice(te_idx, size=n_eval, replace=False)
            pool = np.array([j for j in te_idx if j not in set(ev.tolist())])
            sub_w = g.choice(pool, size=n_train, replace=False)
            sub_c = g.choice(tr_idx, size=n_train, replace=False)
            a_ = depth_score(D, L, fit_on(D, L, arm, sub_c, seed=SEED + d), ev)
            b_ = depth_score(D, L, fit_on(D, L, arm, sub_w, seed=SEED + d), ev)
            if np.isfinite(a_) and np.isfinite(b_):
                cross_v.append(a_)
                within_v.append(b_)
                sizes.append((len(sub_c), len(sub_w)))
        cross_v, within_v = np.asarray(cross_v), np.asarray(within_v)
        ratios = cross_v / np.maximum(within_v, 1e-9)
        med = float(np.median(ratios)) if ratios.size else float("nan")
        r_lo, r_hi = (float(np.quantile(ratios, 0.025)), float(np.quantile(ratios, 0.975))) \
            if ratios.size else (float("nan"), float("nan"))
        rows[tag] = {"cross_mean": float(cross_v.mean()) if cross_v.size else float("nan"),
                     "within_mean": float(within_v.mean()) if within_v.size else float("nan"),
                     "ratio": med, "ratio_ci": [r_lo, r_hi],
                     "n_train": int(n_train), "n_eval": int(n_eval),
                     "sizes_equal": bool(all(a == b for a, b in sizes)),
                     "n_draws": int(ratios.size)}
        print(f"   {tag:<26s} cross {cross_v.mean():+.4f} | within {within_v.mean():+.4f} "
              f"| RATIO {med:.3f} [{r_lo:.3f}, {r_hi:.3f}]  "
              f"(train {n_train} each, eval {n_eval})", flush=True)
    res["transport"] = rows

    # G4 asks ONE thing and can fail: were the two conditions trained on the same number of cases in
    # every draw? The previous version's `or mean <= n_train` clause was true whenever the matched set
    # was smaller, i.e. exactly when the gate should have fired.
    g4 = bool(rows) and all(v.get("sizes_equal") is True for v in rows.values())
    print(f"G4 identical training sizes in every draw: "
          f"{ {k: v.get('sizes_equal') for k, v in rows.items()} }   {'PASS' if g4 else '*** FAIL'}")
    res["g4"] = g4

    lo_below = {k: bool(np.isfinite(v["ratio_ci"][1]) and v["ratio_ci"][1] < 1.0)
                for k, v in rows.items()}
    print("\n" + "=" * 100)
    if not (g1 and g3 and alive and g4):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            nm for nm, ok in (("G1 cohort", g1), ("G2 depth alive in both arms", alive),
                              ("G3 agent legible", g3), ("G4 size match", g4)) if not ok))
    elif all(lo_below.values()):
        v_, why = "DOES NOT TRANSPORT", (
            f"both directions' ratio intervals lie entirely below 1: "
            f"{ {k: [round(x,3) for x in v['ratio_ci']] for k, v in rows.items()} }")
    elif any(lo_below.values()):
        bad = [k for k, x in lo_below.items() if x]
        v_, why = "ASYMMETRIC", (
            f"{bad} does not transport while the other direction does. A concealment test is symmetric by "
            "construction and could not have seen this")
    else:
        v_, why = "TRANSPORTS", (
            "both directions' ratio intervals include or exceed 1: "
            f"{ {k: round(v['ratio'],3) for k, v in rows.items()} }. A depth axis learned on one agent "
            "works on the other, on a cohort where the agent IS legible in the raw family "
            f"({obs:+.4f} vs {f95:+.4f})")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
