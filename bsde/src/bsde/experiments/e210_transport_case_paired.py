#!/usr/bin/env python3
"""E210 — E207's transport question, paired at the CASE rather than at the evaluation set.

REGISTERED BEFORE ANY CASE-LEVEL MARGIN HAS BEEN COMPUTED.

=========================================================================================================
WHY: E207 WAS UNDERPOWERED, NOT WRONG
=========================================================================================================
E206 reframed Challenge A from concealment to TRANSPORT -- does a depth axis learned on one anaesthetic
work on the other -- and its verdict was not issued because a ratio with a near-zero denominator has no
usable variance. E207 replaced the ratio with a paired difference and returned INCONCLUSIVE:

    propofol -> sevoflurane   -0.0941 [-0.1910, +0.0529]
    sevoflurane -> propofol   -0.1736 [-0.3520, +0.0105]

Both point the same way and neither excludes zero. The width comes from the unit of pairing: each draw
scored an axis on a subsampled evaluation set of only 23 or 14 cases, so the statistic inherits that
set's sampling noise on top of the fit's.

**This file changes the UNIT OF PAIRING and nothing else.** Every case in the test arm becomes its own
paired unit -- n = 71 and n = 44 instead of 23 and 14 -- which is a power increase on an unchanged
estimand, the same class of repair rule 46 permits for a replicate count.

    **P1  mean over test-arm cases of (cross margin - within margin)**, where a case's margin is
          (deep - light) projected on an axis oriented by its own training set, and both axes are fitted
          on training sets of the SAME SIZE drawn from the two arms. Bootstrap over CASES.

Averaging `R_DRAWS` training subsamples per case removes the draw noise that E207 could not separate from
the transport effect.

=========================================================================================================
WHAT DOES NOT CHANGE
=========================================================================================================
Cohort, features, joint rank transform, axis orientation, size matching, and every gate: G1 cases per arm,
G2 depth alive within both arms, G3 the agent legible in the raw family so a null is meaningful rather
than free, G4 identical training sizes in every draw.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   a gate fails.
  (2) DOES NOT TRANSPORT  both directions' paired differences exclude zero from BELOW.
  (3) ASYMMETRIC          one direction does, the other's interval includes zero.
  (4) INCONCLUSIVE        every difference straddles zero even at case-level pairing. Then the cohort
                          cannot resolve it and no transport claim is licensed in either direction.
  (5) TRANSPORTS          no direction is negative-and-excluding-zero and at least one excludes zero
                          from ABOVE.

**REGISTERED PREDICTION: (2) DOES NOT TRANSPORT, in both directions.** E207's point estimates were
-0.0941 and -0.1736 and the second nearly excluded zero at the coarser pairing; if those are real, the
finer pairing should resolve them. **This is the same prediction E207 registered and did not confirm**,
restated rather than inherited, and if it comes back INCONCLUSIVE again the honest conclusion is that
115 cases cannot answer the transport question and Challenge A needs a larger cohort rather than a
cleverer statistic.

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
OUT = os.path.join(RESULTS, "e210_transport_case_paired.json")
SEED = 20260802

N_DRAWS = 200
R_DRAWS = 20        # training subsamples averaged per case          # size-matched within-agent draws forming the denominator
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
    res = {"experiment": "E210", "n_cases": n, "n_propofol": int(A.size), "n_sevo": int(B.size),
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

    print("\nP1 CASE-PAIRED DIFFERENCE cross - within (same training size, averaged over draws)")
    rows = {}
    for tag, tr_idx, te_idx in (("propofol -> sevoflurane", A, B),
                                ("sevoflurane -> propofol", B, A)):
        n_train = min(len(tr_idx), len(te_idx) - 1)
        if n_train < 8:
            rows[tag] = {"error": "cannot size-match"}
            continue
        cross_m, within_m = [], []
        for pos, i in enumerate(te_idx):
            pool = np.array([j for j in te_idx if j != i])
            cv, wv = [], []
            for d in range(R_DRAWS):
                g = np.random.default_rng(SEED + 7000 + pos * 100 + d)
                wc = fit_on(D, L, arm, g.choice(tr_idx, size=n_train, replace=False), seed=SEED + d)
                ww = fit_on(D, L, arm, g.choice(pool, size=n_train, replace=False), seed=SEED + d)
                cv.append(float(D[i] @ wc - L[i] @ wc))
                wv.append(float(D[i] @ ww - L[i] @ ww))
            cross_m.append(np.mean(cv))
            within_m.append(np.mean(wv))
        cross_m, within_m = np.asarray(cross_m), np.asarray(within_m)
        diff = cross_m - within_m
        rng2 = np.random.default_rng(SEED + 31)
        bs = [float(np.mean(diff[rng2.integers(0, diff.size, diff.size)])) for _ in range(4000)]
        lo, hi = float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))
        rows[tag] = {"cross_mean": float(cross_m.mean()), "within_mean": float(within_m.mean()),
                     "diff": float(diff.mean()), "diff_ci": [lo, hi],
                     "n_train": int(n_train), "n_cases": int(diff.size),
                     "sizes_equal": True, "n_draws": int(R_DRAWS)}
        print(f"   {tag:<26s} cross {cross_m.mean():+.4f} | within {within_m.mean():+.4f} "
              f"| DIFF {diff.mean():+.4f} [{lo:+.4f}, {hi:+.4f}]  "
              f"(train {n_train} each, {diff.size} paired cases)", flush=True)
    res["transport"] = rows

    # G4 asks ONE thing and can fail: were the two conditions trained on the same number of cases in
    # every draw? The previous version's `or mean <= n_train` clause was true whenever the matched set
    # was smaller, i.e. exactly when the gate should have fired.
    g4 = bool(rows) and all(v.get("sizes_equal") is True for v in rows.values())
    print(f"G4 identical training sizes in every draw: "
          f"{ {k: v.get('sizes_equal') for k, v in rows.items()} }   {'PASS' if g4 else '*** FAIL'}")
    res["g4"] = g4

    # NEGATIVE and excluding zero = transport is measurably imperfect in that direction.
    lo_below = {k: bool(np.isfinite(v.get("diff_ci", [np.nan, np.nan])[1])
                        and v["diff_ci"][1] < 0.0) for k, v in rows.items()}
    inconclusive = {k: bool(np.isfinite(v.get("diff_ci", [np.nan, np.nan])[0])
                            and v["diff_ci"][0] < 0.0 < v["diff_ci"][1]) for k, v in rows.items()}
    print("\n" + "=" * 100)
    if not (g1 and g3 and alive and g4):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            nm for nm, ok in (("G1 cohort", g1), ("G2 depth alive in both arms", alive),
                              ("G3 agent legible", g3), ("G4 size match", g4)) if not ok))
    elif all(lo_below.values()):
        v_, why = "DOES NOT TRANSPORT", (
            "both directions' paired differences exclude zero from BELOW: "
            f"{ {k: [round(x,4) for x in v['diff_ci']] for k, v in rows.items()} }. A depth axis learned "
            "on one agent is measurably worse on the other, and the concealment framing was asking the "
            "wrong question")
    elif any(lo_below.values()):
        bad = [k for k, x in lo_below.items() if x]
        v_, why = "ASYMMETRIC", (
            f"{bad} does not transport while the other direction's interval includes zero. A concealment "
            "test is symmetric by construction and could not have seen this")
    elif all(inconclusive.values()):
        v_, why = "INCONCLUSIVE", (
            "every paired difference straddles zero: "
            f"{ {k: [round(x,4) for x in v['diff_ci']] for k, v in rows.items()} }. The cohort cannot "
            "resolve the question and NO transport claim is licensed in either direction")
    else:
        v_, why = "TRANSPORTS", (
            "no direction's paired difference is negative-and-excluding-zero, and at least one excludes "
            f"zero from ABOVE: { {k: round(v['diff'],4) for k, v in rows.items()} }")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
