#!/usr/bin/env python3
"""E145 -- Challenge B: does the incumbent come alive when the LABEL stops being the limit?

REGISTERED BEFORE ANY INCREMENT ON STIEGER HAS BEEN COMPUTED. Successor to E144. The design is E144's,
line for line -- same incumbent, same statistic, same decision rule, same floor construction. **The only
thing that changes is the deposit**, which makes this a forward transport prediction rather than another
attempt at the same question.

=========================================================================================================
THE PREDICTION THIS FILE EXISTS TO MAKE, AND WHY IT IS FALSIFIABLE
=========================================================================================================
E143 and E144 both failed G2 on eegmmidb: `relative_alpha_power` -- the Challenge B incumbent named in
`CHALLENGE_DEFINITIONS_CORRECTION.md`, marginal rho **+0.2018 [+0.0050, +0.3857]** -- does not beat an
intercept (MAE units, p at the default alpha) nor its own permutation (rank units, **p = 0.192**) out of
bag at n = 104. E144 also measured a detectability floor of **0.0 % at every injected effect up to
rho_partial = 0.40**, under a decision rule whose resolution was verified adequate. So eegmmidb cannot
support an increment test at all, whatever the feature.

**Q31 measured why, on labels only, and nobody carried it forward.** Split-half reliability:

    eegmmidb (E38)         r_sb 0.2918 [0.1163, 0.4345]   ceiling sqrt(r_sb) = 0.5402
    Stieger  (E68)         r_sb 0.9652 [0.9568, 0.9706]   ceiling                0.9825

450 trials per session against eegmmidb's 45 in total. Q31's closing line -- *"Next: the Stieger feature
pass ... then both designs -- between-subject against `relative_alpha_power` as the named incumbent"* --
was written on 2026-07-31 and the feature tables have existed since; the design was never run.

**REGISTERED PREDICTION: G2 PASSES HERE.** The incumbent that is dead on a label with a 0.54 ceiling
should be alive on the same construct measured with a 0.98 ceiling. This is a construct-match prediction
of exactly the shape `CHALLENGE_D_PREREGISTRATION.md` demands the transport rule start making, and it is
committed before the run.

**IF G2 FAILS HERE TOO** -- the branch written first, because it is the one that costs -- then
`relative_alpha_power` is not a Challenge B incumbent on any deposit this project can measure, its +0.2018
was a single marginal correlation whose interval barely excluded zero, and
`CHALLENGE_DEFINITIONS_CORRECTION.md`'s "the real Challenge B incumbent" must be **withdrawn** rather than
softened. That would also mean the whole increment framing is wrong for Challenge B and the question has
to be re-posed against an absolute bar rather than a comparative one.

=========================================================================================================
DEPOSIT AND THE CLUSTER, WHICH IS RULE 69's TRAP
=========================================================================================================
Stieger: **186 sessions from 62 subjects** -- roughly three sessions each. **The cluster is the SUBJECT,
not the session**, and every bootstrap here resamples subjects. E142 established, at a cost of three
experiments, that treating nested rows as independent inflated significance 178-fold; this file states the
unit before the design rather than after it. G4 asserts the nesting is real (more rows than subjects) so
that the assertion cannot silently pass on a table that happens to be one row per subject.

    target      `accuracy`, per session
    incumbent   `relative_alpha_power`
    candidates  every other numeric column of `stieger_features.csv` and `stieger_graph62.csv`
    statistic   out-of-bag increment, stat = -Spearman, decided by the one-sided tail fraction at
                3,000 reps, Holm-corrected across candidates -- E144's rule, unchanged

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE >= 120 sessions from >= 50 subjects with the target and the incumbent.
G2  **INCUMBENT ALIVE**, against its own permutation, out of bag, subject-clustered, p < 0.05. This is the
    prediction and it can fail.
G3  DETECTABILITY FLOOR, E144's construction: synthetic candidates with known partial correlation given
    the incumbent, rho_partial in {0.10, 0.15, 0.20, 0.25, 0.30, 0.40}, 60 draws each, detection at
    p < 0.05/K. Report the smallest level reached in >= 80 % of draws. **This is reported whether or not
    G2 passes**, because a floor is a property of the design and the deposit, not of the incumbent, and
    the eegmmidb-versus-Stieger floor comparison is the quantitative form of the label-reliability claim.
G4  NESTING ASSERTED (rule 69): more rows than subjects, and the resampling unit is the subject.

PLACEBO. Each candidate re-run with its values permuted **within subject-preserving order across
sessions**, i.e. permuted across rows. A firing placebo voids the run.

=========================================================================================================
PRIMARY, WRONG-DIRECTION BRANCH FIRST (rule 37)
=========================================================================================================
**IF NOTHING ADDS** even with a live incumbent and a floor low enough to have found something, that is the
strongest Challenge B negative this project can produce on public data: a nearly noiseless label, 62
subjects, 33 candidates, and no increment. It would be reported as a real negative and not as an
underpowered one -- which is the entire reason G3 is a gate.

**IF SOMETHING ADDS**, it goes to split-half replication using `accuracy_odd` / `accuracy_even`, which
this deposit ships and which makes an internal replication free.

**REGISTERED PREDICTION: G2 PASSES, THE FLOOR LANDS BELOW 0.25, AND NOTHING ADDS.** The last clause rests
on E131 (Stieger's working predictors were `ge_norm`/`iaf`, and neither survived its own permutation
interval), E134 (nothing beat the SMR predictor on Dreyer) and E144's marginal table (three candidates
out-correlated the incumbent and none converted).

WHAT WAS ALREADY SEEN (rule 41). All of E143's and E144's output. On Stieger: the column names, 186 rows,
62 subjects, and E131's published primary (`ge_norm` rho +0.0747 [-0.1968, +0.3294], inside its
permutation interval) and E68's reliability numbers quoted above. No increment over any incumbent on this
deposit, and no correlation between the incumbent and `accuracy` here.

    python bsde/src/bsde/experiments/e145_incumbent_where_the_label_is_reliable.py
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
from bsde.verifier.stats import oob_regression_increment, spearman             # noqa: E402

sys.path.insert(0, HERE)
from e144_increment_over_incumbent_rank import (FLOOR_DRAWS, FLOOR_HIT,        # noqa: E402
                                                FLOOR_LEVELS, FLOOR_REPS, REPS,
                                                inc_p)

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e145_stieger_increment.json")

INCUMBENT = "relative_alpha_power"
TARGET = "accuracy"
MIN_ROWS, MIN_SUBJ = 120, 50
SKIP = {"subject", "session", "n_trials", "n_scored", "n_epochs", "n_channels_used", "n_artifact",
        "accuracy", "accuracy_odd", "accuracy_even", "accuracy_forced", "gender", "handedness"}


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    """Join the two Stieger tables on (subject, session). One row per session; the cluster is subject."""
    def rd(fn):
        return list(csv.DictReader(open(os.path.join(RESULTS, fn), newline="")))
    feat = rd("stieger_features.csv")
    graph = {(r["subject"], r["session"]): r for r in rd("stieger_graph62.csv")}
    rows = []
    for r in feat:
        k = (r["subject"], r["session"])
        merged = dict(r)
        merged.update({c: v for c, v in graph.get(k, {}).items() if c not in merged})
        rows.append(merged)
    cols = []
    for c in rows[0]:
        if c in SKIP:
            continue
        vals = [_f(r.get(c, "")) for r in rows]
        if sum(math.isfinite(v) for v in vals) >= 0.8 * len(vals) and len(set(vals)) > 2:
            cols.append(c)
    return rows, cols


def main(argv=None) -> int:
    rng = np.random.default_rng(145)
    rows, cols = load()
    rows = [r for r in rows
            if math.isfinite(_f(r.get(TARGET, ""))) and math.isfinite(_f(r.get(INCUMBENT, "")))]
    cand = [c for c in cols if c != INCUMBENT]
    y = np.array([_f(r[TARGET]) for r in rows], float)
    inc = np.array([[_f(r[INCUMBENT])] for r in rows], float)
    sid = np.array([r["subject"] for r in rows])
    K = len(cand)
    bar = 0.05 / K
    out = {"experiment": "E145", "n_rows": len(rows), "n_subjects": int(len(set(sid))),
           "n_candidates": K, "reps": REPS, "candidates": cand}

    g1 = len(rows) >= MIN_ROWS and len(set(sid)) >= MIN_SUBJ
    g4 = len(rows) > len(set(sid))
    print(f"G1 COVERAGE {len(rows)} sessions from {len(set(sid))} subjects "
          f"(floors {MIN_ROWS}/{MIN_SUBJ}) -> {'PASS' if g1 else 'FAIL'}")
    print(f"G4 NESTING  rows > subjects, resampling unit is the SUBJECT -> {'PASS' if g4 else 'FAIL'}")
    print(f"   {K} candidates, Holm; the floor's detection bar is {bar:.5f}")
    print(f"   marginal rho({TARGET}, {INCUMBENT}) = {spearman(list(inc[:, 0]), list(y)):+.4f}")

    perm = inc[rng.permutation(len(rows))]
    m, lo, hi, n, p = inc_p(perm, inc, y, sid, rng)
    g2 = math.isfinite(p) and p < 0.05
    print(f"G2 INCUMBENT ALIVE (rank units, vs its own permutation, subject-clustered): {m:+.5f} "
          f"[{lo:+.5f}, {hi:+.5f}] p={p:.5f} over {n} reps -> {'PASS' if g2 else 'FAIL'}")
    print("   (eegmmidb, E144: p = 0.19200 -- the prediction is that this passes where that failed)")
    out["G1"] = {"pass": bool(g1)}
    out["G2"] = {"pass": bool(g2), "increment": m, "ci": [lo, hi], "p": p, "n_reps": n,
                 "eegmmidb_p": 0.192}
    out["G4"] = {"pass": bool(g4)}

    r = y - inc[:, 0] * (np.cov(inc[:, 0], y)[0, 1] / (np.var(inc[:, 0]) + 1e-12))
    r = (r - r.mean()) / (r.std() + 1e-12)
    print(f"\nG3 DETECTABILITY FLOOR  {FLOOR_DRAWS} draws x {len(FLOOR_LEVELS)} levels, "
          f"{FLOOR_REPS} reps, detection = p < {bar:.5f}   (eegmmidb floor: ABOVE 0.40)")
    floor = {}
    for rho in FLOOR_LEVELS:
        hits = 0
        for _ in range(FLOOR_DRAWS):
            z = rho * r + math.sqrt(max(1 - rho ** 2, 0.0)) * rng.standard_normal(len(rows))
            _m, _lo, _hi, _n, _p = inc_p(inc, np.c_[inc, z], y, sid, rng, reps=FLOOR_REPS)
            hits += math.isfinite(_p) and _p < bar
        floor[rho] = hits / FLOOR_DRAWS
        print(f"   rho_partial={rho:.2f}  detected in {floor[rho]:6.1%} of draws")
    det = [rho for rho in FLOOR_LEVELS if floor[rho] >= FLOOR_HIT]
    fl = min(det) if det else None
    g3 = fl is not None
    print(f"   FLOOR = {fl if fl is not None else 'ABOVE ' + str(max(FLOOR_LEVELS))} "
          f"-> {'PASS' if g3 else 'FAIL'}")
    out["G3"] = {"pass": bool(g3), "floor": fl,
                 "detection_rate": {str(k): v for k, v in floor.items()}}

    gates = g1 and g2 and g3 and g4
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    print(f"{'candidate':32s} {'rho(y,c)':>9s} {'increment':>10s} {'p':>8s} {'placebo p':>10s}")
    res, pv = {}, {}
    for c in cand:
        ok = [i for i, rr in enumerate(rows) if math.isfinite(_f(rr.get(c, "")))]
        if len(ok) < MIN_ROWS:
            res[c] = {"skipped": f"only {len(ok)} rows"}
            continue
        yy, ii, ss = y[ok], inc[ok], sid[ok]
        x = np.array([_f(rows[i][c]) for i in ok], float)
        m, lo, hi, n, p = inc_p(ii, np.c_[ii, x], yy, ss, rng)
        *_ignored, pp = inc_p(ii, np.c_[ii, rng.permutation(x)], yy, ss, rng)
        res[c] = {"rho": spearman(list(x), list(yy)), "increment": m, "ci": [lo, hi], "p": p,
                  "placebo_p": pp, "n_rows": len(ok)}
        pv[c] = p
        print(f"{c:32s} {res[c]['rho']:+9.4f} {m:+10.5f} {p:8.5f} {pp:10.5f}")
    adj = holm(list(pv.values()), list(pv.keys()))
    for c, a in adj.items():
        res[c]["p_holm"] = a
        res[c]["helps"] = bool(a < 0.05)
    out["primary"] = res
    out["holm"] = adj

    winners = [c for c, v in res.items() if v.get("helps")]
    fired = [c for c, v in res.items()
             if math.isfinite(v.get("placebo_p", float("nan"))) and v["placebo_p"] < bar]
    print(f"\nHolm: {len(winners)} candidate(s) < 0.05 {winners if winners else ''}")
    print(f"Placebo fired for {len(fired)} {fired if fired else ''}")

    if not g2:
        verdict = ("NO VERDICT, AND THE INCUMBENT IS WITHDRAWN -- relative_alpha_power fails against its "
                   "own permutation on the deposit with a 0.98 label ceiling as well as on the one with "
                   "0.54. It is not a Challenge B incumbent on any deposit this project can measure, and "
                   "CHALLENGE_DEFINITIONS_CORRECTION.md's claim that it is must be withdrawn rather than "
                   "softened. The registered prediction (G2 PASSES) is WRONG.")
    elif not gates:
        verdict = (f"NO VERDICT -- G3 failed: the floor is above {max(FLOOR_LEVELS)} even here, so no "
                   f"deposit available to this project can support an increment test for Challenge B.")
    elif fired:
        verdict = f"VOID -- the placebo fired for {', '.join(fired[:4])}"
    elif winners:
        verdict = (f"POSITIVE -- {', '.join(winners)} add to the incumbent where the label is nearly "
                   f"noiseless, floor rho_partial {fl}. Replicate immediately on accuracy_odd vs "
                   f"accuracy_even, which this deposit ships.")
    else:
        verdict = (f"NEGATIVE, AND IT IS A REAL ONE -- the incumbent is alive (p={out['G2']['p']:.4f}), "
                   f"the floor is rho_partial {fl}, the label ceiling is 0.9825, and none of {K} "
                   f"candidates adds. This is the strongest Challenge B negative available on public "
                   f"data and is not an underpowered null.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
