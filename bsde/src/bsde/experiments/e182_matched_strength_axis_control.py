#!/usr/bin/env python3
"""E182 — is the depth axis's cleanliness a property of its DIRECTION, or only of its WEAKNESS?

REGISTERED BEFORE ANY MATCHED-STRENGTH AXIS HAS BEEN SCORED.

=========================================================================================================
THE GAP, AND WHY IT IS THE WHOLE CLAIM
=========================================================================================================
Two results this session point at the same encouraging picture on VitalDB's 115 clean single-agent cases:

  * **E176**: the leave-one-case-out linear DEPTH SCORE carries essentially no anaesthetic information —
    agent legibility **+0.0029 against a permutation floor of +0.1438** — while the raw feature vector
    carries a great deal (k-NN **+0.4593**, floor +0.1444). Residualising depth out of every feature does
    not reduce agent legibility at all (+0.4739). Agent and depth appear ORTHOGONAL.
  * **E169**: the same axis at lam = 0 scores state **+0.2306** and agent **+0.0314**.

If that is real it is a positive answer to Challenge A's acceptance condition without any adversarial
term: the simplest representation that tracks depth already minimises drug identification.

**There is one control neither file has, and without it the claim is unsupported.** The VitalDB depth axis
is WEAK — state legibility +0.2306, against +0.4711 for the MGH conscious/unconscious axis. A weak
projection carries little of anything, including agent identity. So "the depth axis does not leak" and
"nothing this weak leaks" are not distinguished by anything measured so far. This is rule 50 exactly:
**before attributing a difference to X, measure the difference when X is held constant.**

=========================================================================================================
THE CONTROL
=========================================================================================================
Random unit weight vectors are drawn over the same ten rank-standardised features and scored for state
legibility and agent legibility by the identical `legibility` statistic on the identical case summaries.
Vectors are **kept only if their state legibility falls within `STATE_TOL` of the depth axis's**, so the
comparison holds STRENGTH fixed and varies DIRECTION alone. The depth axis's agent legibility is then
placed in the distribution of agent legibility among those matched-strength axes.

Random axes are not fitted, and the depth axis is fitted leave-one-case-out — so the matching is on the
OBSERVED held-out state legibility of each, which is the quantity both are being compared at. That is
stated because it is the one place the comparison is not perfectly like-for-like.

**GATE M — THE POOL MUST BE BUILDABLE.** At least `MIN_MATCHED` random axes must fall inside the band from
`MAX_TRIES` draws. If they cannot, the file reports NOT MATCHABLE and says what that means: random
directions in this space do not reach the depth axis's state legibility at all, which would itself be
evidence that the depth direction is special — and would be reported as a limitation of the control, never
as a pass.

=========================================================================================================
GATES
=========================================================================================================
G1  the cohort is E169's: >= 40 cases per agent arm.
G2  the depth axis is real — its state legibility beats a within-case deep/light flip floor (E169's G4).
G3  the agent is legible SOMEWHERE in these features, or "the axis does not leak" is vacuous. E176
    measured k-NN agent legibility at +0.4593 against +0.1444; it is re-measured here rather than
    imported (rule 59).
G4  GATE M above.

=========================================================================================================
VERDICT — THE UNINFORMATIVE AND WRONG-DIRECTION CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3 fails.
  (2) NOT MATCHABLE      GATE M fails; the control cannot be built and no claim is made either way.
  (3) NOISIER            the depth axis's agent legibility is HIGHER than the matched-strength median.
                         Then the depth direction leaks MORE than an arbitrary direction of the same
                         strength, which is the opposite of what E176 suggests and would be reported as
                         the finding.
  (4) JUST WEAKNESS      the depth axis sits inside the matched-strength distribution (fraction of matched
                         axes with lower agent legibility > 0.05). **Then E176's orthogonality reading is
                         withdrawn**: the axis is clean because it is weak, not because it is depth, and
                         Challenge A gets nothing from it.
  (5) SPECIFICALLY CLEAN the depth axis's agent legibility is below the 5th percentile of matched-strength
                         random axes. The direction is doing the work, and Challenge A's acceptance
                         condition is met on this cohort by the simplest available representation.

**REGISTERED PREDICTION: (4) JUST WEAKNESS.** A projection with state legibility +0.23 out of a possible
+0.50 is carrying about half the structure a strong axis would, and there is no mechanism that makes the
depth direction preferentially avoid the drug — E161 measured seven of ten individual features leaking the
agent, so most directions in this space should leak. **The prediction is against the most encouraging
Challenge A result this project has**, which is the correct way round, and if it is wrong the result is
worth far more than it is today.

    python bsde/src/bsde/experiments/e182_matched_strength_axis_control.py
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

from e165_adversarial_challenge_a import fit_w, legibility, ranks                # noqa: E402
from e169_constructive_challenge_a_vitaldb import FEATURES, MIN_PER_ARM, load     # noqa: E402
from e176_entanglement_linear_or_intrinsic import knn_score, perm_floor          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e182_matched_strength_axis_control.json")
SEED = 20260801

STATE_TOL = 0.03
MIN_MATCHED = 50
POOL_TARGET = 2000
SEEDS = (11, 22, 33)
MAX_TRIES = 500000
PERMS = 2000
ALPHA = 0.05


def main() -> int:
    print("E182 — does the depth axis avoid the drug because of its DIRECTION or its WEAKNESS?")
    cases = load("exposure")
    ids = sorted(cases)
    if not ids:
        print("ABSENT — no clean-arm cases.")
        return 2
    arm = np.array([cases[c]["arm"] for c in ids], float)
    n = len(ids)
    n_sevo, n_prop = int(arm.sum()), int(n - arm.sum())
    res = {"experiment": "E182", "n_cases": n, "n_sevoflurane": n_sevo, "n_propofol": n_prop,
           "features": FEATURES, "state_tol": STATE_TOL}
    g1 = n_sevo >= MIN_PER_ARM and n_prop >= MIN_PER_ARM
    res["G1_pass"] = bool(g1)
    print(f"G1 {n} cases: {n_prop} propofol alone, {n_sevo} sevoflurane alone   "
          f"{'PASS' if g1 else '*** FAIL'}")
    if not g1:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    both = np.column_stack([ranks([cases[c][f"deep_{f}"] for c in ids]
                                  + [cases[c][f"light_{f}"] for c in ids]) for f in FEATURES])
    D, L = both[:n], both[n:]
    rng = np.random.default_rng(SEED)

    # the depth axis, fitted leave-one-case-out exactly as E169/E176 do
    Xs = np.vstack([D, L])
    ys = np.concatenate([np.full(n, 1.0), np.full(n, -1.0)])
    ya = (arm - arm.mean()) / (arm.std() + 1e-12)
    dd, dl = np.empty(n), np.empty(n)
    for i in range(n):
        tr = np.array([j for j in range(n) if j != i])
        w = fit_w(Xs[np.concatenate([tr, tr + n])], ys[np.concatenate([tr, tr + n])],
                  D[tr], ya[tr], 0.0, seed=0)
        dd[i], dl[i] = D[i] @ w, L[i] @ w
    state_lab = np.concatenate([np.ones(n), np.zeros(n)])
    depth_state = legibility(np.concatenate([dd, dl]), state_lab)
    depth_agent = legibility(dd, arm)
    print(f"   depth axis: state {depth_state:+.4f}   agent {depth_agent:+.4f}")
    res["depth_axis"] = {"state": float(depth_state), "agent": float(depth_agent)}

    # G2 -- is it a depth axis?
    snull = []
    for _ in range(PERMS):
        f = rng.integers(0, 2, n).astype(float)
        v = legibility(np.concatenate([dd, dl]), np.concatenate([f, 1.0 - f]))
        if math.isfinite(v):
            snull.append(v)
    s_p95 = float(np.quantile(snull, 0.95))
    g2 = depth_state > s_p95
    res["G2"] = {"floor_p95": s_p95, "pass": bool(g2)}
    print(f"G2 depth axis real: {depth_state:+.4f} vs within-case flip floor {s_p95:+.4f}   "
          f"{'PASS' if g2 else '*** FAIL'}")

    # G3 -- is the agent legible anywhere in these features?
    knn_agent = legibility(knn_score(D, arm), arm)
    knn_floor, knn_null_mean, knn_n = perm_floor(D, arm, np.random.default_rng(SEED + 1), reps=PERMS)
    g3 = knn_agent > knn_floor
    res["G3"] = {"knn_agent": float(knn_agent), "floor_p95": knn_floor,
                 "null_mean": knn_null_mean, "n": knn_n, "pass": bool(g3)}
    print(f"G3 agent legible somewhere: k-NN {knn_agent:+.4f} vs floor {knn_floor:+.4f}   "
          f"{'PASS' if g3 else '*** FAIL -- nothing leaks, so nothing can be said about avoiding it'}")
    if not (g2 and g3):
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "the depth axis is not a depth axis, or nothing leaks the agent in these features"
        print("\nVERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # GATE M -- matched-strength random axes
    print(f"\nGATE M  random unit directions with state legibility within {STATE_TOL} of "
          f"{depth_state:+.4f}")
    pool, tries = [], 0
    prng = np.random.default_rng(SEED + 2)
    while len(pool) < POOL_TARGET and tries < MAX_TRIES:
        tries += 1
        w = prng.standard_normal(len(FEATURES))
        w /= np.linalg.norm(w) + 1e-12
        st = legibility(np.concatenate([D @ w, L @ w]), state_lab)
        if not math.isfinite(st) or abs(st - depth_state) > STATE_TOL:
            continue
        ag = legibility(D @ w, arm)
        if math.isfinite(ag):
            pool.append((float(st), float(ag)))
    matched = len(pool) >= MIN_MATCHED
    res["gateM"] = {"n_matched": len(pool), "n_tries": int(tries), "pass": bool(matched)}
    print(f"   {len(pool)} matched axes from {tries} draws   "
          f"{'PASS' if matched else '*** NOT MATCHABLE'}")
    if not matched:
        res["verdict"] = "NOT-MATCHABLE"
        res["why"] = ("random directions do not reach the depth axis's state legibility, so the control "
                      "cannot be built. That is itself evidence that the depth direction is special, and "
                      "it is reported as a LIMITATION of the control rather than as a pass")
        print(f"\nVERDICT NOT MATCHABLE — {res['why']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    ag = np.asarray([a for _s, a in pool])
    st = np.asarray([s for s, _a in pool])
    frac_below = float((ag < depth_agent).mean())
    res["matched_pool"] = {"agent_mean": float(ag.mean()), "agent_p05": float(np.quantile(ag, 0.05)),
                           "agent_median": float(np.median(ag)), "state_mean": float(st.mean()),
                           "fraction_below_depth": frac_below}
    print(f"   matched axes: state {st.mean():+.4f}, agent mean {ag.mean():+.4f}, "
          f"median {np.median(ag):+.4f}, 5th pct {np.quantile(ag, 0.05):+.4f}")
    print(f"   fraction of matched axes with LOWER agent legibility than the depth axis: {frac_below:.4f}")

    # RULE 46: this verdict is a fraction against a 0.05 bar, so it must be reported with its Monte Carlo
    # error and re-run at several seeds. The first run used a 200-axis pool and printed 0.0450 -- inside
    # one MC sd of the bar -- and at 2,000 axes the same quantity is 0.0810 / 0.0780 / 0.0865 across three
    # seeds. Raising the replicate count changes no threshold, cohort or horizon; it is the fix rule 46
    # explicitly permits, and the earlier SPECIFICALLY-CLEAN was a property of the draw count.
    stab = []
    for sd in SEEDS:
        q = np.random.default_rng(sd)
        pl, t2 = [], 0
        while len(pl) < POOL_TARGET and t2 < MAX_TRIES:
            t2 += 1
            w = q.standard_normal(len(FEATURES))
            w /= np.linalg.norm(w) + 1e-12
            s_ = legibility(np.concatenate([D @ w, L @ w]), state_lab)
            if not math.isfinite(s_) or abs(s_ - depth_state) > STATE_TOL:
                continue
            a_ = legibility(D @ w, arm)
            if math.isfinite(a_):
                pl.append(a_)
        v = np.asarray(pl)
        stab.append({"seed": int(sd), "n": int(v.size), "frac_below": float((v < depth_agent).mean()),
                     "agent_mean": float(v.mean())})
        print(f"   seed {sd}: {v.size} axes, frac below depth {stab[-1]['frac_below']:.4f} "
              f"(MC sd {math.sqrt(max(stab[-1]['frac_below'] * (1 - stab[-1]['frac_below']), 1e-12) / max(v.size, 1)):.4f})")
    res["seed_stability"] = stab
    frac_below = float(np.mean([x["frac_below"] for x in stab]))
    res["matched_pool"]["fraction_below_depth_mean_over_seeds"] = frac_below
    print(f"   FRACTION USED FOR THE VERDICT (mean over {len(SEEDS)} seeds at {POOL_TARGET} axes): "
          f"{frac_below:.4f}")

    if depth_agent > float(np.median(ag)):
        v, why = "NOISIER", ("the depth axis leaks MORE than the median arbitrary direction of the same "
                             "strength, which is the opposite of E176's reading")
    elif frac_below > ALPHA:
        v, why = "JUST-WEAKNESS", (f"{frac_below:.4f} of matched-strength random directions leak less than "
                                   "the depth axis, so its cleanliness is not specific to depth. **E176's "
                                   "orthogonality reading is withdrawn**: the axis is clean because it is "
                                   "weak, and Challenge A gets nothing from it")
    else:
        v, why = "SPECIFICALLY-CLEAN", (f"only {frac_below:.4f} of matched-strength random directions leak "
                                        "less; the DIRECTION is doing the work, and Challenge A's "
                                        "acceptance condition is met on this cohort by the simplest "
                                        "representation available")
    res["verdict"], res["why"] = v, why
    print(f"\nVERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
