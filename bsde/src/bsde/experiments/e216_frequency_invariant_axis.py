#!/usr/bin/env python3
"""E216 — CONSTRUCTIVE: does a depth axis built only from FREQUENCY-INVARIANT features transport better?

REGISTERED BEFORE THE PRIMARY STATISTIC HAS BEEN COMPUTED FOR ANY FEATURE SUBSET.

=========================================================================================================
WHY THIS, AND WHY IT IS STRONGER THAN ITS PARENT
=========================================================================================================
E214 found that a measure's frequency-shift sensitivity predicts its propofol/sevoflurane disagreement,
and the finding was **weak**: rho +0.5706 at p = 0.046 over a panel of ten points, not robust to dropping
any single feature, with a placebo that was neither matched on rows nor independent of the primary axis
(they correlate -0.6500). The ledger row says all of that.

The weakness is a POWER problem, not a conceptual one. E214 threw away every case and reduced each feature
to one number, then correlated ten numbers. This file asks the same question **constructively**, on the
case-level data, where the evidence actually lives:

    **P1  Take the features whose synthetic frequency sensitivity falls BELOW the measured S-null, build a
          depth axis from those alone, and ask whether it transports between agents better than a
          same-sized axis built from features chosen at random.**

Two things make this a real test rather than a re-run.

  * **THE PARTITION IS NOT DRAWN ON THE OUTCOME.** Membership is decided by `S`, measured on synthetic pink
    noise plus a swept oscillation — no patient, no agent, no deposit. Rule 47 says a placebo can show a
    choice was extreme but cannot show it was made blind, and that the answer has to be structural. Here it
    is: there is no channel through which any transport number could have influenced `S`.
  * **THE THRESHOLD IS DERIVED, NOT CHOSEN** (rule 63). A feature is frequency-invariant if `S` falls below
    the 95th percentile of the S null measured by permuting `f0` against real feature values, which E214
    measured at **0.2315**. On the ten features present in the case table that yields exactly three:
    `spectral_entropy` (0.0840), `relative_delta_power` (0.0458), `exponent_high` (0.0045).

=========================================================================================================
THE NULL IS THE FULL ENUMERATION, NOT A SAMPLE
=========================================================================================================
Three features is a thin axis, and a thin axis differs from a seven-feature one for reasons that have
nothing to do with frequency. So the reference is **every one of the C(10,3) = 120 three-feature subsets**,
scored by the identical statistic — the size-matched control rule 35 demands, computed exhaustively rather
than sampled, so there is no Monte Carlo error in the null at all (which is the fix rule 85 asks for when a
verdict sits near a threshold).

=========================================================================================================
STATISTIC
=========================================================================================================
E210's transport contrast, per feature subset, in both directions:

    cross   = fit the depth axis on ALL cases of one agent, score every case of the OTHER agent on whether
              its deep tercile lands above its light tercile
    within  = the same quantity for the evaluation arm's own leave-one-case-out axis
    T       = mean over the two directions of (cross - within)

`T` is negative when an axis learned on one agent works worse on the other. **The primary is `T` for the
frequency-invariant subset, read as its rank among the 120.** A subset that transports well has `T` near
zero or above.

Axes are oriented on their TRAINING cases before being applied — E206 shipped a gate failure that was an
unidentified sign, not a data fact, and the orientation line is kept for that reason.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 12 cases per agent arm (the programme's standing floor for this cohort).
G2  **DEPTH MUST BE LEGIBLE WITHIN EACH ARM FOR THE FREQUENCY-INVARIANT SUBSET** (rule 53). If a
    three-feature axis cannot read depth inside one agent, its failure to transport is not about transport.
G3  **THE AGENT MUST BE LEGIBLE IN THE RAW FAMILY** (rule 83). If the two arms are indistinguishable then
    transporting between them is free, and a good `T` would mean nothing.
G4  the enumeration must be complete: exactly C(10,3) subsets scored, and the frequency-invariant subset
    must be one of them.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2, G3 or G4 fails.
  (2) INVERTED           the frequency-invariant axis ranks in the BOTTOM 5 % of the 120 — it transports
                         WORSE than a random three-feature axis. That refutes E214's reading outright and
                         is reported as its own outcome, never as a weak version of support.
  (3) ABSENT             its rank falls inside the middle of the enumeration. Choosing features for
                         frequency invariance buys nothing, and E214's correlation does not survive being
                         asked constructively.
  (4) TRANSPORTS BETTER  it ranks in the TOP 5 % of the 120.

**REGISTERED PREDICTION: (3) ABSENT.** E214 is a weak result whose significance evaporates when any single
feature is removed, and three features is a very thin axis. I expect the enumeration to swallow it.
**(4) would be the most consequential outcome this challenge has produced**, because it would be a
constructive recipe — choose measures by a synthetic property, get an axis that survives a change of
anaesthetic — rather than another description of a failure. **(2) would be nearly as valuable**, because it
would mean frequency-invariant measures are invariant by being uninformative, which is a different and
testable story.

**DISCLOSURE (rule 47), carried forward and now larger than it was.** By the time this file was written I
had seen the transport statistic for all ten of these features, not six. What I had NOT seen, and what this
file computes, is any subset-level transport number, the enumeration, or where the frequency-invariant
subset falls in it. The partition remains synthetic and uncontaminated; my decision to run the test is not.

**SCOPE.** One deposit, two agents, ten features. `T` is a difference of sign-rates and inherits their
granularity, so the enumeration is reported in full rather than summarised by a p-value alone.

    python bsde/src/bsde/experiments/e216_frequency_invariant_axis.py
"""

from __future__ import annotations

import itertools
import json
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
OUT = os.path.join(RESULTS, "e216_frequency_invariant_axis.json")
E214_JSON = os.path.join(RESULTS, "e214_frequency_sensitivity_transport.json")

SEED = 20260802
LAM = 0.0
MIN_PER_ARM = 12
PERMS = 300
ALIVE_PERMS = 500
SUBSET_SIZE = 3


def legibility(score, label):
    m = np.isfinite(score)
    if len(set(label[m].tolist())) < 2 or len(set(score[m].tolist())) < 2:
        return float("nan")
    return auc_abs(list(label[m]), list(score[m])) - 0.5


def fit_axis(D, L, arm, idx, seed=0):
    Dm, Lm = D[idx], L[idx]
    n = len(idx)
    Xs = np.vstack([Dm, Lm])
    ys = np.concatenate([np.full(n, 1.0), np.full(n, -1.0)])
    ya = (arm[idx] - arm[idx].mean()) / (arm[idx].std() + 1e-12) if arm[idx].std() > 0 \
        else np.zeros(n)
    w = fit_w(Xs, ys, Dm, ya, LAM, seed=seed)
    # the objective maximises |corr|, so the sign is not identified; orient on the TRAINING cases
    if float(np.mean(Dm @ w) - np.mean(Lm @ w)) < 0:
        w = -w
    return w


def deep_above_light(D, L, w, idx):
    return float(np.mean((D[idx] @ w - L[idx] @ w) > 0) - 0.5) * 2.0


def transport_T(D, L, arm, A, B):
    """mean over both directions of (cross - within), each a signed deep-above-light rate."""
    out = {}
    for tag, tr, te in (("propofol -> sevoflurane", A, B), ("sevoflurane -> propofol", B, A)):
        w = fit_axis(D, L, arm, tr, seed=SEED)
        cross = deep_above_light(D, L, w, te)
        sc = np.empty(len(te))
        for i in range(len(te)):
            loo = np.array([j for j in range(len(te)) if j != i])
            wl = fit_axis(D, L, arm, te[loo], seed=SEED)
            sc[i] = float(D[te[i]] @ wl - L[te[i]] @ wl)
        within = float(np.mean(sc > 0) - 0.5) * 2.0
        out[tag] = {"cross": cross, "within": within, "diff": cross - within}
    return float(np.mean([v["diff"] for v in out.values()])), out


def main() -> int:
    print("E216 — does a FREQUENCY-INVARIANT depth axis transport better than a random one?")
    e214 = json.load(open(E214_JSON))
    S, s95 = e214["S"], e214["s_null_p95"]

    cases = E186.load("exposure")
    ids = sorted(cases)
    n = len(ids)
    arm = np.array([cases[c]["arm"] for c in ids], float)
    cols = [c for c in E186.ALL if c in S]
    both = np.column_stack([ranks([cases[c][f"deep_{f}"] for c in ids]
                                  + [cases[c][f"light_{f}"] for c in ids]) for f in cols])
    Dall, Lall = both[:n], both[n:]
    A = np.flatnonzero(arm < 0.5)
    B = np.flatnonzero(arm > 0.5)

    # membership is checked against the ENUMERATION's key convention -- itertools.combinations
    # emits tuples in `cols` order, so sorting here made G4 look up a key that never exists.
    invariant = tuple(c for c in cols if S[c] < s95)
    print(f"   {len(cols)} features present on both sides; S-null p95 = {s95:.4f} (derived in E214)")
    print(f"   FREQUENCY-INVARIANT subset ({len(invariant)}): "
          + ", ".join(f"{c} S={S[c]:.4f}" for c in invariant))
    print(f"   the other {len(cols) - len(invariant)}: "
          + ", ".join(f"{c} S={S[c]:.4f}" for c in cols if c not in invariant))

    g1 = bool(min(A.size, B.size) >= MIN_PER_ARM)
    print(f"G1 COHORT  {n} cases: {A.size} propofol alone, {B.size} sevoflurane alone   "
          f"{'PASS' if g1 else '*** FAIL'}")

    obs = legibility(knn_score(Dall, arm), arm)
    f95, _m, _k = perm_floor(Dall, arm, np.random.default_rng(SEED + 1), reps=ALIVE_PERMS)
    g3 = bool(np.isfinite(obs) and np.isfinite(f95) and obs > f95)
    print(f"G3 AGENT LEGIBLE IN THE RAW FAMILY  k-NN |AUC-0.5| {obs:+.4f} vs permutation p95 {f95:+.4f}"
          f"   {'PASS' if g3 else '*** FAIL'}")

    idx_of = {c: i for i, c in enumerate(cols)}
    inv_cols = [idx_of[c] for c in invariant]
    Di, Li = Dall[:, inv_cols], Lall[:, inv_cols]

    alive = True
    print("G2 DEPTH LEGIBLE WITHIN EACH ARM FOR THE FREQUENCY-INVARIANT SUBSET")
    within_arm = {}
    for tag, idx in (("propofol", A), ("sevoflurane", B)):
        sc = np.empty(len(idx))
        for i in range(len(idx)):
            loo = np.array([j for j in range(len(idx)) if j != i])
            w = fit_axis(Di, Li, arm, idx[loo], seed=SEED)
            sc[i] = float(Di[idx[i]] @ w - Li[idx[i]] @ w)
        v = float(np.mean(sc > 0) - 0.5) * 2.0
        nul = [float(np.mean((sc * np.random.default_rng(SEED + 40 + k)
                              .choice([-1.0, 1.0], size=sc.size)) > 0) - 0.5) * 2.0
               for k in range(PERMS)]
        p95 = float(np.quantile(nul, 0.95))
        ok = bool(np.isfinite(v) and v > p95)
        alive = alive and ok
        within_arm[tag] = {"deep_above_light": v, "floor": p95, "n": int(len(idx)), "pass": ok}
        print(f"   {tag:<12s} deep-above-light {v:+.4f} vs sign-flip p95 {p95:+.4f} "
              f"({len(idx)} cases)   {'PASS' if ok else '*** FAIL'}")
    g2 = alive

    print(f"\nEnumerating ALL C({len(cols)},{SUBSET_SIZE}) subsets — an exhaustive null has no Monte Carlo "
          f"error (rule 85)")
    subsets = list(itertools.combinations(cols, SUBSET_SIZE))
    scores = {}
    for k, sub in enumerate(subsets):
        j = [idx_of[c] for c in sub]
        T, _ = transport_T(Dall[:, j], Lall[:, j], arm, A, B)
        scores[sub] = T
        if (k + 1) % 20 == 0:
            print(f"   {k + 1}/{len(subsets)} subsets scored", flush=True)
    g4 = bool(len(subsets) == 120 and invariant in scores)
    print(f"G4 ENUMERATION COMPLETE  {len(subsets)} subsets, invariant subset present: "
          f"{invariant in scores}   {'PASS' if g4 else '*** FAIL'}")

    T_inv, detail = transport_T(Di, Li, arm, A, B)
    vals = np.array(sorted(scores.values()))
    rank = int(np.sum(vals < T_inv))
    pct = 100.0 * rank / len(vals)
    print(f"\nFREQUENCY-INVARIANT subset T = {T_inv:+.4f}")
    for tag, d in detail.items():
        print(f"   {tag:<26s} cross {d['cross']:+.4f}  within {d['within']:+.4f}  "
              f"diff {d['diff']:+.4f}")
    print(f"   enumeration: min {vals.min():+.4f}  median {np.median(vals):+.4f}  max {vals.max():+.4f}")
    print(f"   RANK {rank} of {len(vals)}  =  {pct:.1f}th percentile")

    top = sorted(scores.items(), key=lambda kv: -kv[1])[:5]
    print("   best-transporting subsets:")
    for sub, T in top:
        print(f"     {T:+.4f}  {', '.join(sub)}")

    res = {"experiment": "E216", "n_cases": n, "n_propofol": int(A.size), "n_sevo": int(B.size),
           "features": cols, "s_null_p95": s95, "invariant_subset": list(invariant),
           "S": {c: S[c] for c in cols}, "T_invariant": T_inv, "directions": detail,
           "enumeration": {",".join(k): v for k, v in scores.items()},
           "rank": rank, "percentile": pct, "n_subsets": len(vals),
           "g1": g1, "g2": g2, "g3": g3, "g4": g4, "within_arm": within_arm,
           "disclosure": ("the partition is set by a SYNTHETIC sensitivity measured in E214 and cannot have "
                          "been influenced by any transport number; the decision to run this test was made "
                          "after seeing all ten features' transport statistics")}

    print("\n" + "=" * 100)
    if not (g1 and g2 and g3 and g4):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            nm for nm, ok in (("G1 cohort", g1), ("G2 depth legible within arm", g2),
                              ("G3 agent legible", g3), ("G4 enumeration", g4)) if not ok))
    elif pct <= 5.0:
        v_, why = "INVERTED", (
            f"the frequency-invariant axis transports WORSE than a random three-feature axis "
            f"(T {T_inv:+.4f}, rank {rank} of {len(vals)}, {pct:.1f}th percentile). E214's reading is "
            "refuted: choosing measures for frequency invariance actively hurts transport here")
    elif pct < 95.0:
        v_, why = "ABSENT", (
            f"T {T_inv:+.4f} ranks {rank} of {len(vals)} ({pct:.1f}th percentile), inside the "
            "enumeration's middle. Choosing features for frequency invariance buys nothing, and E214's "
            "correlation does not survive being asked constructively on case-level data")
    else:
        v_, why = "TRANSPORTS BETTER", (
            f"T {T_inv:+.4f} ranks {rank} of {len(vals)} ({pct:.1f}th percentile) against an EXHAUSTIVE "
            "size-matched enumeration. An axis built from measures chosen by a synthetic frequency "
            "property -- with no patient, agent or deposit involved in the choice -- survives a change of "
            "anaesthetic better than one built from features chosen at random")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print("SCOPE: one deposit, two agents, ten features. T is a difference of sign-rates and inherits\n"
          "  their granularity, so the full enumeration is written to the result rather than reduced to\n"
          "  a p-value.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
