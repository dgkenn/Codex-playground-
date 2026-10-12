#!/usr/bin/env python3
"""E186 — Challenge A from a PRE-SPECIFIED clean subset rather than a fitted projection.

REGISTERED BEFORE ANY AXIS HAS BEEN FITTED ON A SUBSET OF THESE FEATURES.

=========================================================================================================
THE SUBSET WAS FIXED BY A PRIOR EXPERIMENT, ON A DIFFERENT QUESTION
=========================================================================================================
E161 screened ten VitalDB measures for anaesthetic legibility against a cluster-level null and published
the full table. **Seven separate the agents** — `lempel_ziv` 0.3266, `relative_theta_power` 0.3263,
`alpha_peak_hz` 0.2990, `exponent_low` 0.2559, `whole_head_exponent` 0.2265, `relative_alpha_power`
0.1994, `spectral_edge_95` 0.1690 — and **three do not: `spectral_entropy`, `relative_delta_power`,
`exponent_high`.**

E185's aliveness gate then measured, for the first time, whether those three track DEPTH, and all three
do. The numbers side by side are the reason this file exists:

    measure                depth legibility (floor)     agent legibility
    spectral_entropy          +0.1606 (+0.0627)            **+0.0285**
    relative_delta_power      +0.1581 (+0.0593)            **+0.0813**
    exponent_high             +0.0744 (+0.0606)            **+0.0810**
    ------------------------------------------------------------------
    whole_head_exponent       +0.1729 (+0.0635)              +0.2823
    lempel_ziv                +0.1708 (+0.0493)              +0.3228
    exponent_low              +0.1675 (+0.0597)              +0.3089

`spectral_entropy` and `relative_delta_power` track depth as well as the strongest leakers (+0.16 against
+0.17) while leaking **four to ten times less**. That is a dissociation at the single-feature level, and
it is not obviously the weakness explanation E182 used to withdraw E176 — these are not weak axes.

**THE SELECTION IS CLEAN AND THAT IS THE POINT.** The three were chosen by E161 for their agent legibility,
before anyone measured their depth legibility, and this file does not choose anything. Rule 47 asks for a
partition that is a property of the instruments rather than an arbitrary grouping, drawn where it could not
have been peeked at; this one was drawn in a different experiment on a different outcome.

=========================================================================================================
DESIGN, AND E182'S CONTROL IS BUILT IN FROM THE START
=========================================================================================================
Three arms, each fitting E169's lam = 0 depth axis leave-one-case-out **within that arm's features only**:

    NONLEAK  the three above          LEAK  E161's seven          ALL  the ten
    (`exponent_gamma` is excluded: E185 measured it not alive for depth.)

Each arm's held-out agent legibility is judged against **two** floors:

    (a) a case-level agent-label permutation pushed through the entire fit and score, as E168/E169;
    (b) **matched-strength random directions inside that arm's own feature space** — random unit vectors
        kept only if their state legibility falls within `STATE_TOL` of that arm's fitted axis.

(b) is E182's control and it is the one that matters. E176 read low leakage as orthogonality and E182
withdrew it because 0.0818 of matched-strength random directions leaked less. **A three-feature axis is
weaker still, so without (b) this file would repeat that mistake exactly.**

PRIMARY: does NONLEAK keep at least `STATE_TOL_FRAC` of ALL's state legibility while its agent legibility
sits below BOTH floors?

=========================================================================================================
GATES
=========================================================================================================
G1  E169's cohort: >= 40 cases per agent arm.
G2  each arm's axis must be a depth axis — state legibility above a within-case deep/light flip floor.
G3  the agent must be legible in the ALL arm's features, or "NONLEAK does not leak" is vacuous (rule 53).
G4  the matched-strength pool must be buildable per arm (>= `MIN_MATCHED`), or that arm reports
    NOT MATCHABLE and the limitation is stated rather than read as a pass.
G5  **the fraction against the matched-strength pool is reported with its Monte Carlo error and at three
    seeds** (rule 46). E182's first run printed the opposite verdict at 200 draws because the margin was
    the size of its own MC error; the pool here is `POOL_TARGET` and the verdict takes the seed mean.

=========================================================================================================
VERDICT — THE WITHDRAWING AND WRONG-DIRECTION CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2 or G3 fails.
  (2) NOT MATCHABLE       G4 fails for NONLEAK.
  (3) LEAKS MORE          NONLEAK's agent legibility exceeds ALL's. The subset selected for not leaking
                          individually leaks more in combination, which would be a real finding about
                          how leakage combines and is enumerated before the numbers.
  (4) JUST WEAKNESS       NONLEAK sits inside its matched-strength distribution. Same withdrawal as E182:
                          clean because weak, and Challenge A gets nothing.
  (5) STATE TOO LOW       NONLEAK's agent legibility is below both floors but it keeps less than
                          `STATE_TOL_FRAC` of ALL's state legibility. Then the trade is real and the price
                          is stated in the only unit that matters — how much depth tracking is given up.
  (6) SEPARABLE           NONLEAK keeps the state axis AND sits below both floors. **The first Challenge A
                          candidate in this ledger with the matched-strength control behind it**, and it
                          must then be carried to a cohort with loss and recovery before it is called
                          anything.

**REGISTERED PREDICTION: (5) STATE TOO LOW.** Three features cannot span what ten do, and E185's own table
gives NONLEAK's members depth legibilities of +0.1606, +0.1581 and +0.0744 against a ten-feature fitted
axis at +0.2306. The prediction says the dissociation is real and the price is too high, which is the
least convenient of the informative outcomes.

    python bsde/src/bsde/experiments/e186_prespecified_clean_subset.py
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

from e165_adversarial_challenge_a import fit_w, legibility, ranks                 # noqa: E402
from e169_constructive_challenge_a_vitaldb import MIN_PER_ARM, load               # noqa: E402
from e176_entanglement_linear_or_intrinsic import knn_score, perm_floor           # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e186_prespecified_clean_subset.json")
SEED = 20260801

NONLEAK = ["spectral_entropy", "relative_delta_power", "exponent_high"]
LEAK = ["lempel_ziv", "relative_theta_power", "alpha_peak_hz", "exponent_low",
        "whole_head_exponent", "relative_alpha_power", "spectral_edge_95"]
ALL = LEAK + NONLEAK

STATE_TOL = 0.03
STATE_TOL_FRAC = 0.80
POOL_TARGET = 2000
SEEDS = (11, 22, 33)
MIN_MATCHED = 50
MAX_TRIES = 500000
N_PERM = 100
PERMS = 2000
ALPHA = 0.05


def fit_axis(D, L, arm, cols, feats):
    """Leave-one-case-out lam = 0 depth axis inside `feats` only. Returns (deep score, light score)."""
    j = [cols.index(f) for f in feats]
    Dm, Lm = D[:, j], L[:, j]
    n = Dm.shape[0]
    Xs = np.vstack([Dm, Lm])
    ys = np.concatenate([np.full(n, 1.0), np.full(n, -1.0)])
    ya = (arm - arm.mean()) / (arm.std() + 1e-12)
    dd, dl = np.empty(n), np.empty(n)
    for i in range(n):
        tr = np.array([k for k in range(n) if k != i])
        w = fit_w(Xs[np.concatenate([tr, tr + n])], ys[np.concatenate([tr, tr + n])],
                  Dm[tr], ya[tr], 0.0, seed=0)
        dd[i], dl[i] = Dm[i] @ w, Lm[i] @ w
    return dd, dl, Dm, Lm


def pipeline_floor(D, L, arm, cols, feats, rng, n_perm=N_PERM):
    vals = []
    for _ in range(n_perm):
        a = rng.permutation(arm)
        dd, _dl, _Dm, _Lm = fit_axis(D, L, a, cols, feats)
        v = legibility(dd, a)
        if math.isfinite(v):
            vals.append(v)
    v = np.asarray(vals)
    return float(np.quantile(v, 0.95)) if v.size >= 30 else float("nan"), int(v.size)


def matched_pool(Dm, Lm, arm, state_lab, target_state, seed, pool=POOL_TARGET):
    q = np.random.default_rng(seed)
    got, tries = [], 0
    while len(got) < pool and tries < MAX_TRIES:
        tries += 1
        w = q.standard_normal(Dm.shape[1])
        w /= np.linalg.norm(w) + 1e-12
        s = legibility(np.concatenate([Dm @ w, Lm @ w]), state_lab)
        if not math.isfinite(s) or abs(s - target_state) > STATE_TOL:
            continue
        a = legibility(Dm @ w, arm)
        if math.isfinite(a):
            got.append(a)
    return np.asarray(got), tries


def main() -> int:
    print("E186 — Challenge A from E161's pre-specified non-leaking subset")
    cases = load("exposure")
    ids = sorted(cases)
    if not ids:
        print("ABSENT — no clean-arm cases.")
        return 2
    arm = np.array([cases[c]["arm"] for c in ids], float)
    n = len(ids)
    res = {"experiment": "E186", "n_cases": n, "n_sevoflurane": int(arm.sum()),
           "n_propofol": int(n - arm.sum()), "nonleak": NONLEAK, "leak": LEAK}
    g1 = arm.sum() >= MIN_PER_ARM and (n - arm.sum()) >= MIN_PER_ARM
    res["G1_pass"] = bool(g1)
    print(f"G1 {n} cases: {int(n - arm.sum())} propofol alone, {int(arm.sum())} sevoflurane alone   "
          f"{'PASS' if g1 else '*** FAIL'}")
    if not g1:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    cols = ALL
    both = np.column_stack([ranks([cases[c][f"deep_{f}"] for c in ids]
                                  + [cases[c][f"light_{f}"] for c in ids]) for f in cols])
    D, L = both[:n], both[n:]
    state_lab = np.concatenate([np.ones(n), np.zeros(n)])
    rng = np.random.default_rng(SEED)

    # G3 -- is the agent legible in the full feature set at all?
    knn = legibility(knn_score(D, arm), arm)
    kf, _km, _kn = perm_floor(D, arm, np.random.default_rng(SEED + 1), reps=PERMS)
    g3 = knn > kf
    res["G3"] = {"knn_agent": float(knn), "floor_p95": float(kf), "pass": bool(g3)}
    print(f"G3 agent legible in ALL: k-NN {knn:+.4f} vs floor {kf:+.4f}   "
          f"{'PASS' if g3 else '*** FAIL'}")
    if not g3:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "nothing leaks the agent, so a clean subset is vacuous"
        print(f"\nVERDICT NOT INTERPRETABLE — {res['why']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    arms = {}
    for name, feats in (("ALL", ALL), ("LEAK", LEAK), ("NONLEAK", NONLEAK)):
        dd, dl, Dm, Lm = fit_axis(D, L, arm, cols, feats)
        st = legibility(np.concatenate([dd, dl]), state_lab)
        ag = legibility(dd, arm)
        flips = [rng.integers(0, 2, n).astype(float) for _ in range(PERMS)]
        snull = np.asarray([legibility(np.concatenate([dd, dl]), np.concatenate([f, 1.0 - f]))
                            for f in flips])
        s95 = float(np.quantile(snull[np.isfinite(snull)], 0.95))
        pf, npf = pipeline_floor(D, L, arm, cols, feats, np.random.default_rng(SEED + 7))
        stab, tries = [], 0
        for sd in SEEDS:
            pool, t = matched_pool(Dm, Lm, arm, state_lab, st, sd)
            tries += t
            if pool.size >= MIN_MATCHED:
                stab.append({"seed": int(sd), "n": int(pool.size),
                             "frac_below": float((pool < ag).mean()),
                             "agent_mean": float(pool.mean())})
        frac = float(np.mean([x["frac_below"] for x in stab])) if stab else float("nan")
        arms[name] = {"features": feats, "state": float(st), "agent": float(ag),
                      "state_floor_p95": s95, "state_alive": bool(st > s95),
                      "pipeline_floor_p95": float(pf), "pipeline_n": npf,
                      "below_pipeline_floor": bool(np.isfinite(pf) and ag < pf),
                      "matched_seeds": stab, "matched_frac_below": frac,
                      "matched_n_tries": int(tries),
                      "matched_pool_mean": float(np.mean([x["agent_mean"] for x in stab]))
                      if stab else float("nan"),
                      "matchable": bool(len(stab) == len(SEEDS))}
        print(f"\nARM {name} ({len(feats)} features)")
        print(f"   state {st:+.4f} (flip floor {s95:+.4f}) -> "
              f"{'ALIVE' if arms[name]['state_alive'] else '*** not a depth axis'}")
        print(f"   agent {ag:+.4f} vs permutation floor {pf:+.4f} ({npf} draws) -> "
              f"{'below' if arms[name]['below_pipeline_floor'] else 'ABOVE'}")
        if stab:
            for x in stab:
                print(f"   matched-strength seed {x['seed']}: {x['n']} axes, mean agent "
                      f"{x['agent_mean']:+.4f}, frac below {x['frac_below']:.4f}")
            print(f"   matched-strength fraction below (mean over seeds): {frac:.4f}")
        else:
            print(f"   *** matched-strength pool NOT BUILDABLE ({tries} draws)")
    res["arms"] = arms

    A, N = arms["ALL"], arms["NONLEAK"]
    if not (A["state_alive"] and N["state_alive"]):
        v, why = "NOT-INTERPRETABLE", "one of the arms is not a depth axis"
    elif not N["matchable"]:
        v, why = "NOT-MATCHABLE", ("random directions do not reach NONLEAK's state legibility, so E182's "
                                   "control cannot be built. That is a limitation of the control and is "
                                   "NOT a pass")
    elif N["agent"] > A["agent"]:
        v, why = "LEAKS-MORE", (f"NONLEAK leaks {N['agent']:+.4f} against ALL's {A['agent']:+.4f} -- the "
                                "subset selected for not leaking individually leaks more in combination")
    elif N["matched_frac_below"] > ALPHA:
        v, why = "JUST-WEAKNESS", (f"{N['matched_frac_below']:.4f} of matched-strength random directions "
                                   "inside NONLEAK's own feature space leak less, so its cleanliness is "
                                   "not specific to it -- the same withdrawal as E182")
    elif not N["below_pipeline_floor"]:
        v, why = "JUST-WEAKNESS", ("NONLEAK's agent legibility is not below its own case-permutation "
                                   "floor")
    elif N["state"] < STATE_TOL_FRAC * A["state"]:
        v, why = "STATE-TOO-LOW", (f"NONLEAK sits below both floors but keeps only "
                                   f"{100 * N['state'] / A['state']:.0f} % of ALL's state legibility "
                                   f"({N['state']:+.4f} against {A['state']:+.4f}) -- the dissociation is "
                                   "real and the price is most of the depth tracking")
    else:
        v, why = "SEPARABLE", (f"NONLEAK keeps {100 * N['state'] / A['state']:.0f} % of ALL's state "
                               f"legibility at agent legibility {N['agent']:+.4f}, below its "
                               f"permutation floor and below {N['matched_frac_below']:.4f} of "
                               "matched-strength random directions. The first Challenge A candidate here "
                               "with E182's control behind it, and it must be carried to a cohort with "
                               "loss and recovery before it is called anything")
    res["verdict"], res["why"] = v, why
    print(f"\nVERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
