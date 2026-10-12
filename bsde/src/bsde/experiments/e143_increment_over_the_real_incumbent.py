#!/usr/bin/env python3
"""E143 -- Challenge B: does ANYTHING add to `relative_alpha_power`, and what could this design have found?

REGISTERED BEFORE ANY INCREMENT HAS BEEN COMPUTED. The marginal correlations of most of these candidates
against this label are already in E41's P5 table and are not re-derived here; **no increment over the
incumbent has ever been computed on this target**, which is the gap `CHALLENGE_DEFINITIONS_CORRECTION.md`
names.

=========================================================================================================
WHY, AND A CORRECTION TO THE CORRECTION
=========================================================================================================
`CHALLENGE_DEFINITIONS_CORRECTION.md` restated Challenge B from the brief -- *"spontaneous EEG predicting
command-following"* -- and identified `relative_alpha_power` (**+0.2018 [+0.0050, +0.3857]**, n = 104,
E41) as the real incumbent, adding that *"nothing has been tested against this on the target"*.

**That document is also slightly wrong about E41 and the correction belongs here rather than left
standing.** It says E41 "measured it directly", implying E41's label is command-following while the
Stieger/Dreyer line is a proxy. E41's label is `imagery_auc` -- how well a classifier separates left from
right *motor imagery* in a healthy volunteer -- which is BCI aptitude, the same class of proxy. What is
true, and is the defensible version, is that **the task is the same task**: motor imagery performed on
instruction is the assay Owen's covert-consciousness paradigm uses, so the construct distance from
eegmmidb to a brain-injured patient is population and severity, not task. That is a smaller gap than
"BCI aptitude versus command-following" suggests and a real one nonetheless, and it is a transport
question this file does not settle.

=========================================================================================================
WHAT IS COMPUTED
=========================================================================================================
    y            `imagery_auc`, one value per subject                             (eegmmidb_bci.csv)
    A            [`relative_alpha_power`]                                          the incumbent alone
    B            [`relative_alpha_power`, candidate]                               for each of 32 candidates
    statistic    `oob_regression_increment(A, B, y, subject, ...)`, median absolute error

**The sign convention is stated because reading it backwards inverts the verdict: the returned value is
B minus A on an ERROR statistic, so NEGATIVE means the candidate HELPS.**

One row per subject after E41's reduction (the mean of a subject's resting rows), so the cluster and the
row coincide and rule 69's nesting trap does not arise here -- asserted in G4 rather than assumed.

Candidates: the 19 non-incumbent columns of `eegmmidb_rest_v2` (which adds `icoh_alpha` and `lrtc_alpha`
over the v1 file E41 read), the 10 graph columns of `eegmmidb_graph`, and the 3 regional aperiodic
columns. **32 comparisons, corrected by Bonferroni** -- the interval is taken at alpha = 0.05/32, which is
why `oob_regression_increment` grew an `alpha` argument in this commit (default unchanged, so no existing
caller moves).

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE. >= 90 subjects with the label, the incumbent and the candidate.
G2  **THE INCUMBENT MUST BE ALIVE OUT OF BAG, AND THIS CAN FAIL.** `relative_alpha_power` correlates with
    the label at +0.2018 in-sample; that does not guarantee it beats an intercept out of bag at n = 104.
    If it does not, then "adding to the incumbent" is not the question anyone should be asking and no
    increment below is interpretable. A comparison against a dead incumbent is a comparison against noise
    (rule 48's shape: a placebo cannot validate a null; here, an incumbent cannot anchor one).
G3  **THE DETECTABILITY FLOOR, AND IT IS THE POINT OF THIS FILE.** Synthetic candidates are constructed
    with a KNOWN partial correlation with y given the incumbent, at rho_partial in
    {0.10, 0.15, 0.20, 0.25, 0.30, 0.40}, 100 independent draws each, pushed through the identical code
    path. Report the smallest rho_partial at which >= 80 % of draws return an interval excluding zero.

    `PROGRAMME_ROADMAP.md` lists this as an adjunct the project keeps needing and has never built:
    *"E130 and E108 both burned effort on designs that could not have won"*. **A null result is only
    evidence when the floor is known**, and the floor -- not the null -- is what this file is for. It is a
    gate rather than a footnote because if the floor exceeds every plausible effect, the primary should
    not be reported as a negative at all.
G4  ONE ROW PER SUBJECT after reduction, asserted (rule 69).

PLACEBO. Each candidate is re-run with its values permuted across subjects. A permuted candidate that
"adds" at the corrected interval means the machinery manufactures increments and the run is void.

=========================================================================================================
PRIMARY, WRONG-DIRECTION BRANCH FIRST (rule 37)
=========================================================================================================
**IF SOMETHING ADDS** -- any candidate with a Bonferroni-corrected interval entirely below zero -- that is
the first thing this project has found that improves on the real Challenge B incumbent on its own target,
and it must be reported as such and immediately queued for split-half replication inside eegmmidb before
any transport claim is made.

**REGISTERED PREDICTION: NOTHING ADDS, AND THE FLOOR IS ABOVE rho_partial = 0.25.** E134 established that
nothing beats the SMR predictor on the Dreyer proxy; E41's P5 found no candidate's marginal correlation
clearing the incumbent's; E131 found the working predictors in two BCI cohorts to be disjoint. The
substantive claim in this prediction is the second half: that this design could only ever have found large
increments, so a null is close to uninformative about small ones. If the floor comes in at or below 0.15,
the null is strong and this project has a genuinely negative Challenge B result rather than an
underpowered one.

WHAT WAS ALREADY SEEN (rule 41). Manifest only: 104 subjects have a label and every feature table; 105
subjects have two resting rows each (eyes_open, eyes_closed); the column names. E41's published numbers,
quoted above. No increment, and no relationship between any candidate and the label beyond E41's P5.

    python bsde/src/bsde/experiments/e143_increment_over_the_real_incumbent.py
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import oob_regression_increment, spearman             # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e143_increment_over_incumbent.json")

INCUMBENT = "relative_alpha_power"
LABEL = "imagery_auc"
MIN_SUBJECTS = 90
REPS = 400
FLOOR_LEVELS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40)
FLOOR_DRAWS = 100
FLOOR_REPS = 150
FLOOR_HIT = 0.80

SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples",
        "meta_run", "meta_condition", "meta_sfreq", "run", "n_frontal", "n_posterior"}


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _numeric_cols(rows):
    cols = []
    for c in rows[0]:
        if c in SKIP:
            continue
        vals = [_f(r.get(c, "")) for r in rows]
        if sum(math.isfinite(v) for v in vals) >= 0.8 * len(vals) and len(set(vals)) > 2:
            cols.append(c)
    return cols


def load():
    """Per subject: the mean of that subject's rows in each table. E41's reduction, applied to all three."""
    per = defaultdict(dict)
    tables = {}
    rest = []
    for p in sorted(glob.glob(os.path.join(RESULTS, "eegmmidb_rest_v2.s*.csv"))):
        rest += [r for r in csv.DictReader(open(p, newline="")) if r.get("status") == "ok"]
    tables["rest_v2"] = rest
    for name, fn in (("graph", "eegmmidb_graph.csv"), ("regional", "eegmmidb_regional_aperiodic.csv")):
        tables[name] = [r for r in csv.DictReader(open(os.path.join(RESULTS, fn), newline=""))
                        if r.get("status") == "ok"]
    cols = {}
    for name, rows in tables.items():
        cols[name] = _numeric_cols(rows)
        acc = defaultdict(lambda: defaultdict(list))
        for r in rows:
            for c in cols[name]:
                v = _f(r.get(c, ""))
                if math.isfinite(v):
                    acc[r["subject"]][c].append(v)
        for s, d in acc.items():
            for c, v in d.items():
                per[s][c] = float(np.mean(v))
    lab = {r["subject"]: _f(r[LABEL]) for r in
           csv.DictReader(open(os.path.join(RESULTS, "eegmmidb_bci.csv"), newline=""))
           if r.get("status") == "ok" and math.isfinite(_f(r.get(LABEL, "")))}
    return per, lab, cols


def main(argv=None) -> int:
    rng = np.random.default_rng(143)
    per, lab, cols = load()
    cand = sorted({c for v in cols.values() for c in v} - {INCUMBENT})
    subs = sorted(s for s in per
                  if s in lab and math.isfinite(per[s].get(INCUMBENT, float("nan"))))
    y = np.array([lab[s] for s in subs], float)
    inc = np.array([[per[s][INCUMBENT]] for s in subs], float)
    sid = np.array(subs)
    out = {"experiment": "E143", "n_subjects": len(subs), "n_candidates": len(cand),
           "candidates": cand}

    g1 = len(subs) >= MIN_SUBJECTS
    g4 = len(set(subs)) == len(subs)
    print(f"G1 COVERAGE   {len(subs)} subjects with label + incumbent (floor {MIN_SUBJECTS})  "
          f"-> {'PASS' if g1 else 'FAIL'}")
    print(f"G4 ONE ROW PER SUBJECT after reduction -> {'PASS' if g4 else 'FAIL'}")
    print(f"   {len(cand)} candidates -> Bonferroni alpha = 0.05/{len(cand)} = {0.05 / len(cand):.5f}")
    print(f"   incumbent marginal rho(label, {INCUMBENT}) = "
          f"{spearman(list(inc[:, 0]), list(y)):+.4f}   (E41 reported +0.2018)")

    # ---- G2 the incumbent must be alive out of bag ---------------------------------------------------
    null_col = np.ones((len(subs), 1))
    m, lo, hi, n = oob_regression_increment(null_col, inc, y, sid, rng, reps=REPS)
    g2 = math.isfinite(hi) and hi < 0
    print(f"G2 INCUMBENT ALIVE  intercept -> incumbent: {m:+.5f} [{lo:+.5f}, {hi:+.5f}] over {n} reps "
          f"(negative = the incumbent helps)  -> {'PASS' if g2 else 'FAIL'}")
    out["G1"] = {"pass": bool(g1), "n": len(subs)}
    out["G2"] = {"pass": bool(g2), "increment": m, "ci": [lo, hi], "n_reps": n}
    out["G4"] = {"pass": bool(g4)}

    # ---- G3 the detectability floor ------------------------------------------------------------------
    # A synthetic candidate is built as a mix of the residual of y on the incumbent and fresh noise, so
    # its partial correlation with y GIVEN the incumbent is the mixing weight by construction.
    r = y - inc[:, 0] * (np.cov(inc[:, 0], y)[0, 1] / (np.var(inc[:, 0]) + 1e-12))
    r = (r - r.mean()) / (r.std() + 1e-12)
    print(f"\nG3 DETECTABILITY FLOOR  {FLOOR_DRAWS} draws x {len(FLOOR_LEVELS)} levels, "
          f"identical code path, Bonferroni interval")
    floor = {}
    a_corr = 0.05 / len(cand)
    for rho in FLOOR_LEVELS:
        hits = 0
        for d in range(FLOOR_DRAWS):
            z = rho * r + math.sqrt(max(1 - rho ** 2, 0.0)) * rng.standard_normal(len(subs))
            B = np.c_[inc, z]
            _m, _lo, _hi, _n = oob_regression_increment(inc, B, y, sid, rng, reps=FLOOR_REPS,
                                                        alpha=a_corr)
            if math.isfinite(_hi) and _hi < 0:
                hits += 1
        floor[rho] = hits / FLOOR_DRAWS
        print(f"   rho_partial={rho:.2f}  detected in {floor[rho]:6.1%} of draws")
    detectable = [rho for rho in FLOOR_LEVELS if floor[rho] >= FLOOR_HIT]
    fl = min(detectable) if detectable else None
    g3 = fl is not None
    print(f"   FLOOR = {fl if fl is not None else 'ABOVE ' + str(max(FLOOR_LEVELS))}"
          f"  (smallest rho_partial detected in >= {FLOOR_HIT:.0%} of draws)  "
          f"-> {'PASS' if g3 else 'FAIL: this design could not have detected any tested effect'}")
    out["G3"] = {"pass": bool(g3), "floor": fl, "detection_rate": {str(k): v for k, v in floor.items()},
                 "levels": list(FLOOR_LEVELS), "draws": FLOOR_DRAWS, "bar": FLOOR_HIT}

    gates = g1 and g2 and g3 and g4
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    # ---- primary --------------------------------------------------------------------------------------
    print(f"{'candidate':30s} {'rho(y,cand)':>12s} {'increment':>10s}  Bonferroni interval   placebo")
    res = {}
    for c in cand:
        ok = [i for i, s in enumerate(subs) if math.isfinite(per[s].get(c, float("nan")))]
        if len(ok) < MIN_SUBJECTS:
            res[c] = {"skipped": f"only {len(ok)} subjects"}
            print(f"{c:30s} {'--':>12s} {'skipped':>10s}  only {len(ok)} subjects")
            continue
        yy, ii = y[ok], inc[ok]
        ss = sid[ok]
        x = np.array([per[subs[i]][c] for i in ok], float)
        B = np.c_[ii, x]
        m, lo, hi, n = oob_regression_increment(ii, B, yy, ss, rng, reps=REPS, alpha=a_corr)
        xp = rng.permutation(x)
        pm, plo, phi, _ = oob_regression_increment(ii, np.c_[ii, xp], yy, ss, rng, reps=REPS,
                                                   alpha=a_corr)
        helps = math.isfinite(hi) and hi < 0
        placebo_fires = math.isfinite(phi) and phi < 0
        res[c] = {"rho": spearman(list(x), list(yy)), "increment": m, "ci": [lo, hi], "n_reps": n,
                  "helps": bool(helps), "placebo_increment": pm, "placebo_ci": [plo, phi],
                  "placebo_fires": bool(placebo_fires), "n_subjects": len(ok)}
        print(f"{c:30s} {res[c]['rho']:+12.4f} {m:+10.5f}  [{lo:+.5f}, {hi:+.5f}] "
              f"{'HELPS' if helps else '     '}  {'PLACEBO FIRED' if placebo_fires else ''}")
    out["primary"] = res

    fired = [c for c, v in res.items() if v.get("placebo_fires")]
    winners = [c for c, v in res.items() if v.get("helps")]
    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif fired:
        verdict = (f"VOID -- the placebo fired for {len(fired)} candidate(s) ({', '.join(fired[:4])}), so "
                   f"the machinery manufactures increments at this n and no positive is interpretable.")
    elif winners:
        verdict = (f"POSITIVE -- {len(winners)} candidate(s) add to the real Challenge B incumbent at the "
                   f"Bonferroni-corrected interval: {', '.join(winners)}. Queue split-half replication "
                   f"inside eegmmidb before any transport claim.")
    else:
        verdict = (f"NEGATIVE -- nothing adds to {INCUMBENT} on its own target, and the design's "
                   f"detectability floor is rho_partial = "
                   f"{fl if fl is not None else 'above ' + str(max(FLOOR_LEVELS))}. "
                   f"The null is informative for increments above that floor and uninformative below it. "
                   f"The registered prediction was NOTHING ADDS with a floor above 0.25; the floor "
                   f"measured {fl}.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict

    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
