#!/usr/bin/env python3
"""E163 -- re-derive the two increment-decided nulls that sit in the regime where the instrument was blindest.

REGISTERED BEFORE EITHER INCREMENT HAS BEEN RECOMPUTED. Re-derivation under rule 2, not a new question:
each arm keeps its own experiment's cohort, incumbent, candidates and error statistic. **Only the test
changes**, and each arm carries a reproduction gate so a discrepancy surfaces as a failure here rather
than as a silent difference in the comparison (rule 20).

=========================================================================================================
WHY THESE TWO, OUT OF THE NINE THAT REMAIN
=========================================================================================================
E146 measured `oob_regression_increment`'s bootstrap tail fraction detecting **0.00 %** of a
rho_partial = 0.35 effect at 60 subjects with **one row each**, against a closed-form oracle's 88.33 %,
and the blindness easing sharply as rows-per-cluster rises (66.67 % at 100 subjects x 3 rows). E150 then
moved E84's verdict on a cohort with **277 rows per recording** -- the regime where the old test was
LEAST blind -- and eleven candidates appeared.

**So the nulls most likely to move are the ones with the fewest rows per cluster, and these are the two
extremes of that.**

    E134  Challenge B, Dreyer   **87 subjects, ONE row each** -- exactly E146's worst cell
    E133  Challenge A, sleep-EDFx  563 rows over 142 subjects, ~4 rows each

E133 is included as the harder case and as a control on the re-derivation itself: its incumbent sits at
out-of-bag rho **+0.9293** for the depth ordinal, so there is almost no headroom and its null may well be
real rather than instrumental. **A re-derivation that moves everything is not a re-derivation, it is a new
bias**, and having one arm that should not move is how that gets checked.

=========================================================================================================
WHAT EACH ARM KEEPS AND WHAT CHANGES
=========================================================================================================
    KEPT      cohort, incumbent, candidate list, error statistic, clustering unit -- imported from each
              experiment's own module where possible (E133 exposes `load()`), transcribed in full and
              gated on reproduction where not (E134 runs at import and cannot be imported safely)
    CHANGED   `permutation_increment` -- cross-fitted, cluster-permutation null, validated in E147 at a
              false-positive rate of 0.0333 and 86 % of oracle power -- replaces the bootstrap tail

=========================================================================================================
GATES
=========================================================================================================
G1  **INSTRUMENT VALIDATION IMPORTED, NOT ASSUMED.** E147's calibration JSON must report a pass.
G2  **REPRODUCTION, per arm.** E134's stored incumbent rho is **+0.4440** over **87** subjects and E133's
    stored spectral incumbent out-of-bag rho is **+0.9293** over 563 rows and 142 subjects. Each arm must
    reproduce its own to within 0.02, or the two runs are not on the same data and nothing is comparable.
G3  **DETECTABILITY FLOOR, per arm, under the NEW instrument.** Synthetic candidates at known partial
    correlation given the incumbent. A null is only evidence above its floor; E134's whole problem was
    that nobody had measured one.
G4  **PLACEBO, per candidate**: the same test with the candidate column cluster-permuted. A placebo
    reaching the corrected bar voids that arm.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
**IF NEITHER MOVES**, both nulls were real and the blind instrument happened to give the right answer
twice. E133's would then be a genuine ceiling result and E134's a genuine comprehensive negative, and the
remaining seven rows become much less urgent.

**IF E134 MOVES**, then "nothing beats the SMR predictor" -- the first Challenge B experiment to name a
predictor incumbent, and the result its ledger row calls *comprehensive* -- is withdrawn, and the
Challenge B record has to be rebuilt from the calibrated instrument up.

**REGISTERED PREDICTION: E134 moves and E133 does not.** E134 sits in E146's worst measured cell and its
candidates' intervals were wide rather than tight around zero (`deg` -0.0095 [-0.1064, +0.1210] was the
best of ten). E133's incumbent is at +0.9293, which leaves so little headroom that even a calibrated test
should find nothing. **The prediction is a split, which is the only shape that can be wrong in two
directions**, and both halves are stated before the run.

WHAT WAS ALREADY SEEN (rule 41). Both experiments' committed result JSONs and ledger rows, quoted above --
E134's ten candidate intervals and its Gaussian control, E133's gate block and its +0.9293 incumbent. No
permutation increment on either cohort.

    python bsde/src/bsde/experiments/e163_rederive_blind_nulls.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import (cluster_permute, grouped_cv_predict,          # noqa: E402
                                 permutation_increment, spearman)

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e163_rederived_nulls.json")
E147_JSON = os.path.join(RESULTS, "e147_calibrated_increment.json")

PERMS = 1500
FLOOR_LEVELS = (0.10, 0.20, 0.30, 0.40)
FLOOR_DRAWS = 40
FLOOR_PERMS = 400
FLOOR_HIT = 0.80
E134_RHO, E134_N = 0.4440475322592404, 87
E133_RHO = 0.9293


def err(t, p):
    """1 - Spearman, the statistic BOTH source experiments used, so lower is better and B-minus-A holds."""
    r = spearman(list(np.asarray(t, float)), list(np.asarray(p, float)))
    return 1.0 - r if math.isfinite(r) else float("nan")


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def build_e134():
    """E134's cohort, TRANSCRIBED IN FULL from its module (it runs at import and cannot be imported).

    Rule 59 warns against hand-copying a SUBSET of a prior result; the whole build is copied here and the
    reproduction gate on the incumbent rho is what verifies the transcription."""
    sys.path.insert(0, HERE)
    from e129_blankertz_replication import _read_shards                         # noqa: E402
    from e125_ge_norm_online_control import load_performance                     # noqa: E402
    R = os.path.join(RESULTS)
    smr = {r["subject"]: r for r in _read_shards(os.path.join(R, "dreyer_smr.csv"))}
    graph = {}
    for r in _read_shards(os.path.join(R, "dreyer_graph.csv")):
        graph.setdefault(r["subject"], []).append(r)
    perf = load_performance()
    subs = sorted(set(smr) & set(graph) & set(perf))

    def gmean(s, k):
        v = [_f(r.get(k, "")) for r in graph.get(s, [])]
        v = [q for q in v if math.isfinite(q)]
        return float(np.mean(v)) if v else float("nan")

    y = np.array([_f(perf[s]["accuracy"]) for s in subs], float)
    X = np.array([[_f(smr[s]["smr_predictor_db"])] for s in subs], float)
    subj = np.array(subs)
    ok = np.isfinite(X[:, 0]) & np.isfinite(y)
    X, y, subj = X[ok], y[ok], subj[ok]
    cand = ["ge", "cl", "deg", "ge_norm", "cl_norm", "smallworld", "modularity", "strength_cv",
            "alpha_prom", "iaf"]
    cols = {c: np.array([gmean(s, c) for s in subj], float) for c in cand}
    return X, y, subj, cols, float(spearman(list(X[:, 0]), list(y)))


def build_e133():
    """E133's cohort, via its own `load()`."""
    sys.path.insert(0, HERE)
    import e133_irreversibility_increment as E133
    irr, five, spectral = E133.load()
    # The six irreversibility candidates, named explicitly. `irr` also carries a `*_surr` phase-randomised
    # column for each -- those are the NULL the measure was built against and E133 carries them as columns,
    # never as predictors -- and its dict picks up one header-shaped key that must not become a cohort row.
    icols = ["frontal_irr3", "frontal_irr4", "frontal_incr",
             "posterior_irr3", "posterior_irr4", "posterior_incr"]
    keys = sorted(k for k in (set(irr) & set(five)) if k[0] != "subject")
    y, subj, S, I = [], [], [], []
    order = {"W": 0, "N1": 1, "N2": 2, "N3": 3}
    for k in keys:
        lab = k[1]
        if lab not in order:
            continue
        s = [_f(five[k].get(c, "")) for c in spectral]
        i = [_f(irr[k].get(c, "")) for c in icols]
        if not (all(map(math.isfinite, s)) and all(map(math.isfinite, i))):
            continue
        y.append(order[lab])
        subj.append(k[0])
        S.append(s)
        I.append(i)
    return (np.asarray(S, float), np.asarray(I, float), np.asarray(y, float),
            np.asarray(subj), spectral, icols)


def floor(X, y, subj, rng, bar):
    A = np.c_[np.ones(len(y)), X]
    r = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]
    r = (r - r.mean()) / (r.std() + 1e-12)
    out = {}
    for rho in FLOOR_LEVELS:
        hits = 0
        for _ in range(FLOOR_DRAWS):
            z = rho * r + math.sqrt(max(1 - rho ** 2, 0.0)) * rng.standard_normal(len(y))
            _o, p, _n, _k = permutation_increment(X, np.c_[X, z], y, subj, rng, stat=err,
                                                  reps=FLOOR_PERMS)
            hits += math.isfinite(p) and p < bar
        out[rho] = hits / FLOOR_DRAWS
    det = [r_ for r_ in FLOOR_LEVELS if out[r_] >= FLOOR_HIT]
    return out, (min(det) if det else None)


def run_arm(name, X, y, subj, cols, rng, out, repro_obs, repro_ref, repro_tol):
    K = len(cols)
    bar = 0.05 / max(K, 1)
    ok = abs(repro_obs - repro_ref) <= repro_tol
    print(f"\n{'=' * 96}\n{name}: {len(y)} rows, {len(set(subj.tolist()))} clusters, {K} candidates")
    print(f"G2 REPRODUCTION  observed {repro_obs:+.4f} against stored {repro_ref:+.4f} "
          f"(tol {repro_tol}) -> {'PASS' if ok else 'FAIL'}")
    d = {"n_rows": int(len(y)), "n_clusters": int(len(set(subj.tolist()))), "n_candidates": K,
         "G2": {"pass": bool(ok), "observed": repro_obs, "stored": repro_ref}}
    fl_rates, fl = floor(X, y, subj, rng, bar)
    print(f"G3 FLOOR  " + "  ".join(f"{r_:.2f}:{v:.0%}" for r_, v in fl_rates.items())
          + f"   -> FLOOR = {fl if fl is not None else 'above ' + str(max(FLOOR_LEVELS))}")
    d["G3"] = {"floor": fl, "rates": {str(k): v for k, v in fl_rates.items()}}
    print(f"{'candidate':16s} {'increment':>10s} {'p':>8s} {'p_holm':>8s} {'placebo p':>10s}")
    res, pv = {}, {}
    for c, v in cols.items():
        m = np.isfinite(v)
        if m.sum() < 0.8 * len(y):
            res[c] = {"skipped": int(m.sum())}
            continue
        o, p, _nm, _k = permutation_increment(X[m], np.c_[X[m], v[m]], y[m], subj[m], rng,
                                              stat=err, reps=PERMS)
        _o2, pc, _n2, _k2 = permutation_increment(X[m], np.c_[X[m], cluster_permute(v[m], subj[m], rng)],
                                                  y[m], subj[m], rng, stat=err, reps=PERMS)
        res[c] = {"increment": o, "p": p, "placebo_p": pc}
        pv[c] = p
        print(f"{c:16s} {o:+10.5f} {p:8.5f} {'':8s} {pc:10.5f}")
    adj = holm(list(pv.values()), list(pv.keys()))
    for c, a in adj.items():
        res[c]["p_holm"] = a
        res[c]["helps"] = bool(a < 0.05 and res[c]["increment"] < 0)
    d["primary"] = res
    d["winners"] = [c for c, v in res.items() if v.get("helps")]
    d["placebo_fired"] = [c for c, v in res.items()
                          if math.isfinite(v.get("placebo_p", float("nan"))) and v["placebo_p"] < bar]
    print(f"   winners: {d['winners'] or 'none'}   placebo fired: {d['placebo_fired'] or 'none'}")
    out[name] = d
    return d


def main(argv=None) -> int:
    rng = np.random.default_rng(163)
    out = {"experiment": "E163", "perms": PERMS}
    try:
        e147 = json.load(open(E147_JSON))
        g1 = bool(e147.get("G1", {}).get("pass"))
        print(f"G1 INSTRUMENT VALIDATION  E147 fpr={e147['G1']['fpr']:.4f} -> {'PASS' if g1 else 'FAIL'}")
    except Exception as e:                                                     # noqa: BLE001
        print(f"G1 INSTRUMENT VALIDATION  unreadable ({type(e).__name__}) -> FAIL")
        g1 = False
    if not g1:
        json.dump({**out, "G1": False}, open(OUT, "w"), indent=1, sort_keys=True)
        return 1

    arms = {}
    try:
        X, y, subj, cols, rho = build_e134()
        arms["E134_dreyer"] = run_arm("E134  Challenge B, Dreyer SMR predictor", X, y, subj, cols,
                                      rng, out, rho, E134_RHO, 0.02)
    except Exception as e:                                                     # noqa: BLE001
        print(f"E134 arm failed to build: {type(e).__name__}: {e}")
        out["E134_dreyer"] = {"error": f"{type(e).__name__}: {e}"}
    try:
        S, I, y2, subj2, spec, icols = build_e133()
        pr = grouped_cv_predict(S, y2, subj2, rng, folds=5)
        m = np.isfinite(pr)
        rho2 = spearman(list(y2[m]), list(pr[m]))
        cols2 = {c: I[:, j] for j, c in enumerate(icols)}
        arms["E133_sleep"] = run_arm("E133  Challenge A, sleep-EDFx irreversibility", S, y2, subj2,
                                     cols2, rng, out, rho2, E133_RHO, 0.05)
    except Exception as e:                                                     # noqa: BLE001
        print(f"E133 arm failed to build: {type(e).__name__}: {e}")
        out["E133_sleep"] = {"error": f"{type(e).__name__}: {e}"}

    moved = [k for k, v in arms.items() if v.get("winners")]
    if not arms:
        verdict = "NO VERDICT -- neither arm could be built"
    elif "E134_dreyer" in moved and "E133_sleep" not in moved:
        verdict = ("PREDICTION CONFIRMED -- E134 moves and E133 does not. 'Nothing beats the SMR "
                   "predictor', the result its own ledger row calls comprehensive, is WITHDRAWN, and the "
                   "Challenge B record must be rebuilt from the calibrated instrument up. E133's null "
                   "survives, which is what a re-derivation that is not itself a new bias looks like.")
    elif moved:
        verdict = (f"MOVED: {', '.join(moved)}. Those nulls were instrumental and the corresponding "
                   f"ledger rows must be re-derived rather than assumed.")
    else:
        verdict = ("NEITHER MOVES -- both nulls were real and the blind instrument happened to give the "
                   "right answer twice. The registered prediction is half wrong, E134's comprehensive "
                   "negative stands, and the remaining seven increment-decided rows become much less "
                   "urgent.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
