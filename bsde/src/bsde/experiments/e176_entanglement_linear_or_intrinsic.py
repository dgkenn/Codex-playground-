#!/usr/bin/env python3
"""E176 — is Challenge A's entanglement a property of LINEARITY, or of the data?

REGISTERED BEFORE ANY RESIDUALISED AGENT LEGIBILITY HAS BEEN COMPUTED.

=========================================================================================================
THE GAP THIS FILLS
=========================================================================================================
Every constructive Challenge A test this project has run is LINEAR — E165, E168 and E169 all fit a weight
vector. The standing objection to an ENTANGLED verdict from any of them is the obvious one: *you only
tried linear combinations.* That objection cannot be answered by fitting a bigger model on 39 or 115
cases, which would overfit and prove nothing.

**It can be answered by asking where the agent information LIVES rather than by searching for a
representation.** If the anaesthetic is legible only through the same axis that carries depth, then no
function of these features — linear or not — can keep depth and drop the agent, because they are the same
number. If the agent is legible in the part of the features ORTHOGONAL to depth, then the linear search
failed for a reason a better search could fix, and Challenge A is open in a way the linear results do not
show.

=========================================================================================================
DESIGN
=========================================================================================================
    cohort     VitalDB clean single-agent cases (44 propofol alone, 71 sevoflurane alone), each summarised
               over its own DEEPEST and LIGHTEST exposure tercile, exactly as E169 builds them; the loader
               is IMPORTED from E169 rather than rewritten (rule 20)
    state      each case's depth score: its position on the leave-one-case-out linear depth axis, which is
               E169's lam = 0 projection -- the best single summary of "how deep does this case look"
    step 1     AGENT LEGIBILITY, unadjusted, by a NON-PARAMETRIC rule: leave-one-case-out k-nearest-
               neighbour in the 11-dimensional rank space of the deep-block vectors. Not linear, and able
               to express any local decision boundary the sample supports.
    step 2     the same, on features RESIDUALISED on the depth score across cases (rank-linear residuals,
               one regression per feature)
    statistic  the DROP in agent legibility from step 1 to step 2, as a fraction of step 1

=========================================================================================================
THE ADJUSTMENT IS A COLLIDER RISK AND IT GETS A LINE OF CODE, NOT A CAVEAT (rules 13, 54)
=========================================================================================================
Depth is not pre-exposure. A clinician chooses the agent and then titrates it, so the depth score sits
DOWNSTREAM of agent identity, and conditioning on a post-exposure variable is exactly what rule 13
forbids. Two things follow and both are implemented:

  * **The association between agent and depth score is measured and printed FIRST.** If the agent is
    strongly legible from the depth score alone, the residualisation is over-adjustment and the experiment
    reports NOT SEPARABLE-BY-DESIGN rather than an entanglement verdict. That is a real gate and it can
    fire.
  * **A PLACEBO ADJUSTMENT.** The same residualisation is run against a score that is a random rotation of
    the depth axis, matched in variance and in its own correlation structure but carrying no depth. If a
    meaningless score removes as much agent legibility as the depth score does, the drop measures the
    arithmetic of residualising eleven features, not entanglement. It GATES the verdict (rule 34), and it
    is a comparison against the placebo's DISTRIBUTION over 500 draws, never against one number.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 40 cases per agent arm (E169's floor, unchanged).
G2  **THE AGENT MUST BE LEGIBLE BEFORE ADJUSTMENT.** Step 1's k-NN legibility must exceed a case-level
    agent-label permutation floor. If the agent is not legible at all, there is nothing to remove and the
    file cannot speak (rule 53 — the E61 trap, and the outcome E168 hit).
G3  **THE DEPTH SCORE MUST BE A DEPTH SCORE.** Its held-out legibility for deep-versus-light must exceed a
    within-case flip floor, or it is not the axis the residualisation claims to remove.
G4  **OVER-ADJUSTMENT CHECK**, as above: the agent's legibility from the depth score ALONE is measured
    against its own permutation floor and printed before anything is residualised.

=========================================================================================================
VERDICT — THE UNINFORMATIVE AND WRONG-DIRECTION CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE      G2 or G3 fails.
  (2) OVER-ADJUSTED          G4 fires: the depth score is itself a strong agent classifier, so removing it
                             removes the agent by construction and the drop means nothing.
  (3) ARITHMETIC             the placebo score removes as much as the depth score does. The drop is a
                             property of residualising eleven features on any score.
  (4) ORTHOGONAL             agent legibility SURVIVES the depth adjustment above the placebo. **The agent
                             information is not carried by the depth axis, so the linear failures are
                             failures of linearity and Challenge A is open** — this is the branch that
                             would most change the programme and it is written before the numbers.
  (5) INTRINSIC              agent legibility collapses with the depth adjustment and the placebo does not
                             reproduce it. The two are the same axis, and no representation of this
                             feature family — of any functional form — can keep one and drop the other.

REGISTERED PREDICTION: **(5) INTRINSIC**, for E161's reason: the features that leak the agent most
(`lempel_ziv`, `relative_theta_power`) are also strong depth discriminators. The prediction is against
Challenge A being tractable in this family, which is the direction that costs the programme most, and
therefore the correct way round.

SCOPE. One deposit, two agents, spectra plus one connectivity column, depth within anaesthesia rather than
consciousness, and a k-NN whose expressiveness is bounded by 115 cases. A collapse here bounds this
feature family on this cohort; it does not bound families the deposit lacks.

    python bsde/src/bsde/experiments/e176_entanglement_linear_or_intrinsic.py
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

from e165_adversarial_challenge_a import fit_w, legibility, ranks               # noqa: E402
from e169_constructive_challenge_a_vitaldb import FEATURES, MIN_PER_ARM, load   # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e176_entanglement_linear_or_intrinsic.json")
SEED = 20260801

K = 7
PERMS = 2000
PLACEBO_DRAWS = 500
ALPHA = 0.05


def knn_score(X, lab, k=K):
    """Leave-one-out k-NN vote share for class 1. Non-parametric: no functional form is assumed."""
    n = len(lab)
    D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(D, np.inf)
    out = np.empty(n)
    kk = min(k, n - 1)
    for i in range(n):
        nb = np.argsort(D[i])[:kk]
        out[i] = float(np.mean(lab[nb]))
    return out


def perm_floor(X, lab, rng, reps=PERMS, k=K):
    """Case-level label permutation, pushed through the SAME k-NN, 95th percentile."""
    vals = []
    for _ in range(reps):
        p = rng.permutation(lab)
        v = legibility(knn_score(X, p, k), p)
        if math.isfinite(v):
            vals.append(v)
    v = np.asarray(vals)
    return float(np.quantile(v, 0.95)), float(v.mean()), int(v.size)


def residualise(X, s):
    """Rank-linear residual of every column on the score `s`, computed across cases."""
    out = np.empty_like(X)
    A = np.column_stack([np.ones(len(s)), s])
    for j in range(X.shape[1]):
        coef, *_ = np.linalg.lstsq(A, X[:, j], rcond=None)
        out[:, j] = X[:, j] - A @ coef
    return out


def main() -> int:
    print("E176 — is Challenge A's entanglement linear or intrinsic?")
    cases = load("exposure")
    ids = sorted(cases)
    if not ids:
        print("ABSENT — no clean-arm cases with a dose join.")
        return 2
    arm = np.array([cases[c]["arm"] for c in ids], float)
    n = len(ids)
    n_sevo, n_prop = int(arm.sum()), int(n - arm.sum())
    res = {"experiment": "E176", "n_cases": n, "n_sevoflurane": n_sevo, "n_propofol": n_prop, "k": K}
    g1 = n_sevo >= MIN_PER_ARM and n_prop >= MIN_PER_ARM
    res["G1_pass"] = bool(g1)
    print(f"G1 MANIFEST  {n} cases: {n_prop} propofol alone, {n_sevo} sevoflurane alone   "
          f"{'PASS' if g1 else '*** FAIL'}")
    if not g1:
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    both = np.column_stack([ranks([cases[c][f"deep_{f}"] for c in ids]
                                  + [cases[c][f"light_{f}"] for c in ids]) for f in FEATURES])
    D, L = both[:n], both[n:]
    rng = np.random.default_rng(SEED)

    # the depth score: E169's lam = 0 axis, fitted leave-one-case-out so no case scores itself
    Xs = np.vstack([D, L])
    ys = np.concatenate([np.full(n, 1.0), np.full(n, -1.0)])
    ya = (arm - arm.mean()) / (arm.std() + 1e-12)
    depth_d, depth_l = np.empty(n), np.empty(n)
    for i in range(n):
        tr = np.array([j for j in range(n) if j != i])
        w = fit_w(Xs[np.concatenate([tr, tr + n])], ys[np.concatenate([tr, tr + n])],
                  D[tr], ya[tr], 0.0, seed=0)
        depth_d[i], depth_l[i] = D[i] @ w, L[i] @ w

    # G3 -- is it a depth score?
    st = legibility(np.concatenate([depth_d, depth_l]), np.concatenate([np.ones(n), np.zeros(n)]))
    snull = []
    for _ in range(PERMS):
        f = rng.integers(0, 2, n).astype(float)
        snull.append(legibility(np.concatenate([depth_d, depth_l]), np.concatenate([f, 1.0 - f])))
    snull = np.asarray([v for v in snull if math.isfinite(v)])
    s_p95 = float(np.quantile(snull, 0.95))
    g3 = st > s_p95
    res["G3"] = {"depth_legibility": float(st), "floor_p95": s_p95, "pass": bool(g3)}
    print(f"G3 depth axis  deep-vs-light legibility {st:+.4f} vs within-case flip floor {s_p95:+.4f}   "
          f"{'PASS' if g3 else '*** FAIL'}")

    # G2 -- is the agent legible before any adjustment?
    a_raw = legibility(knn_score(D, arm), arm)
    a_floor, a_null_mean, a_n = perm_floor(D, arm, np.random.default_rng(SEED + 1))
    g2 = a_raw > a_floor
    res["G2"] = {"agent_legibility": float(a_raw), "floor_p95": a_floor,
                 "null_mean": a_null_mean, "n_null": a_n, "pass": bool(g2)}
    print(f"G2 agent legible, k-NN, UNadjusted: {a_raw:+.4f} vs permutation floor {a_floor:+.4f} "
          f"(null mean {a_null_mean:+.4f}, {a_n} draws)   {'PASS' if g2 else '*** FAIL'}")

    # G4 -- over-adjustment: is the depth score itself an agent classifier?
    dscore = depth_d.reshape(-1, 1)
    a_from_depth = legibility(knn_score(dscore, arm), arm)
    d_floor, _, _ = perm_floor(dscore, arm, np.random.default_rng(SEED + 2), reps=PERMS // 2)
    g4_fires = a_from_depth > d_floor
    res["G4"] = {"agent_from_depth_score": float(a_from_depth), "floor_p95": d_floor,
                 "over_adjusted": bool(g4_fires)}
    print(f"G4 over-adjustment: agent legibility from the DEPTH SCORE ALONE {a_from_depth:+.4f} vs "
          f"floor {d_floor:+.4f}   {'*** FIRES' if g4_fires else 'clear'}")

    if not (g2 and g3):
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "the agent is not legible before adjustment, or the depth score is not a depth score"
        print("\nVERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1
    if g4_fires:
        res["verdict"] = "OVER-ADJUSTED"
        res["why"] = ("the depth score is itself a significant agent classifier, so residualising on it "
                      "removes the agent by construction and any drop is uninterpretable (rule 13)")
        print("\nVERDICT OVER-ADJUSTED — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    # step 2 -- residualise on depth, re-measure
    Dr = residualise(D, depth_d)
    a_adj = legibility(knn_score(Dr, arm), arm)
    r_floor, _, _ = perm_floor(Dr, arm, np.random.default_rng(SEED + 3))
    drop = (a_raw - a_adj) / a_raw if a_raw > 0 else float("nan")
    res["adjusted"] = {"agent_legibility": float(a_adj), "floor_p95": r_floor,
                       "drop_fraction": float(drop)}
    print(f"\nADJUSTED on the depth score: agent legibility {a_adj:+.4f} (floor {r_floor:+.4f}); "
          f"drop {100 * drop:.1f} % of the unadjusted value")

    # placebo -- residualise on a meaningless score of matched variance
    print(f"PLACEBO — residualising on {PLACEBO_DRAWS} random scores of matched variance")
    prng = np.random.default_rng(SEED + 4)
    pdrops = []
    for _ in range(PLACEBO_DRAWS):
        w = prng.standard_normal(D.shape[1])
        w /= np.linalg.norm(w) + 1e-12
        s = D @ w
        s = (s - s.mean()) / (s.std() + 1e-12) * (depth_d.std() + 1e-12) + depth_d.mean()
        v = legibility(knn_score(residualise(D, s), arm), arm)
        if math.isfinite(v) and a_raw > 0:
            pdrops.append((a_raw - v) / a_raw)
    pd_ = np.asarray(pdrops)
    p_placebo = float((pd_ >= drop).mean()) if pd_.size else float("nan")
    res["placebo"] = {"mean_drop": float(pd_.mean()) if pd_.size else float("nan"),
                      "p95_drop": float(np.quantile(pd_, 0.95)) if pd_.size else float("nan"),
                      "fraction_at_or_above_real": p_placebo, "n": int(pd_.size)}
    print(f"   placebo drops: mean {100 * pd_.mean():.1f} %, 95th pct {100 * np.quantile(pd_, 0.95):.1f} %; "
          f"fraction reaching the real drop {p_placebo:.4f}")

    if not (np.isfinite(p_placebo) and p_placebo <= ALPHA):
        v, why = "ARITHMETIC", (f"{p_placebo:.4f} of random scores of matched variance remove as much "
                                "agent legibility as the depth score does, so the drop is a property of "
                                "residualising eleven features and not of entanglement")
    elif a_adj > r_floor:
        v, why = "ORTHOGONAL", ("agent legibility survives the depth adjustment above its own permutation "
                                "floor: the agent information is NOT carried by the depth axis, the "
                                "linear failures are failures of linearity, and Challenge A is open in "
                                "this family")
    else:
        v, why = "INTRINSIC", ("agent legibility falls to its permutation floor once depth is removed, "
                               "and a matched random score does not reproduce that: the two are the same "
                               "axis, and no function of this feature family can keep depth and drop the "
                               "agent")
    res["verdict"], res["why"] = v, why
    print(f"\nVERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
