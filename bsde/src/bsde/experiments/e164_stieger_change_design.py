#!/usr/bin/env python3
"""E164 -- Challenge B asked WITHIN a person: does a change in the EEG track a change in performance?

REGISTERED BEFORE ANY CHANGE-SCORE CORRELATION HAS BEEN COMPUTED. `docs/QUEUE.md` Q31 endorsed this design
on 2026-07-31, measured its reliability, and it was never run.

=========================================================================================================
WHY A CHANGE DESIGN IS A DIFFERENT QUESTION, NOT MORE OF THE SAME
=========================================================================================================
Every Challenge B test this project has run is BETWEEN subjects: does a resting measure separate people
who decode well from people who decode badly. Those have now been pushed as far as the data allows and
the answer is bounded rather than negative:

    E149  eegmmidb, 104 subjects   incumbent alive (p = 0.034), **0 of 32 candidates add**
    E163  Dreyer, 87 subjects      0 of 10 add, but the floor is **above rho_partial 0.4** -- the design
                                   cannot see a small increment at that n whatever test is used
    E131                           the working predictors in two BCI cohorts are DISJOINT

A between-subject correlation is confounded by everything time-invariant about a person: skull thickness,
electrode placement habit, trait alpha frequency, age, motivation. **A within-person change removes all of
it by construction.** If a feature's session-to-session change tracks the same subject's change in
accuracy, that is a claim no between-subject correlation can make, and it is the claim a *marker* needs.

**And on this deposit the change score is nearly noiseless, which is the unusual part.** Q31 measured it
on labels only: within-session reliability **0.9652** (ceiling 0.9825), and the consecutive-session change
score at **0.8983** (ceiling 0.9478), against eegmmidb's 0.2918 (ceiling 0.5402). Q31 explicitly retracted
its own earlier warning that "a change score is noisier than a level" for this deposit: with ~356 scored
trials per session, differencing two near-noiseless measurements costs almost nothing. **28.6 % of session
variance is within-subject**, which is what a change design has to work with.

=========================================================================================================
COHORT AND STATISTIC
=========================================================================================================
Checked before registration and disclosed: **62 subjects, 61 with three sessions and one with two, giving
123 consecutive session pairs.** Change in accuracy has mean **+0.0375** (Q31 reported +0.0386 from the
label pass, so the join reproduces it), sd **0.1110**, range −0.184 to +0.313 -- real learning with real
spread.

    unit        the consecutive session pair (k, k+1); the CLUSTER is the SUBJECT (rule 69)
    target      delta accuracy
    candidates  the delta of every numeric feature in `stieger_features.csv` and `stieger_graph62.csv`,
                excluding the outcome family and `mean_triallength`, which rule 70 established is the
                outcome renamed (trials end on target-hit and otherwise time out, rho = -0.3492)
    primary     Spearman(delta feature, delta accuracy), against a **subject-clustered permutation null**
                -- the subject's whole block of deltas is reassigned, so the null preserves the nesting

**The primary is the MARGINAL correlation, not an increment**, and that is a deliberate consequence of
E163: increments are power-hungry, and on a cohort this size a floor above 0.4 is what an increment test
delivers. The increment over the change in `relative_alpha_power` is reported as a secondary with its own
floor, so it can be read for what it is.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 100 pairs from >= 50 subjects.
G2  **THE OUTCOME MUST VARY.** sd of delta accuracy >= 0.05. A cohort that all improved by the same
    amount has nothing for any feature to track.
G3  **THE CEILING IS QUOTED, NOT ASSUMED.** Q31's change-score reliability 0.8983 caps any correlation at
    0.9478 by attenuation. This is recorded so a null here is a real null rather than an attenuation
    artefact -- the condition Q14 required before any Challenge B correlation is run, and the reason this
    deposit was chosen over eegmmidb.
G4  **DETECTABILITY FLOOR** under the permutation null: synthetic deltas at known correlation with the
    target, 60 draws at each of five levels. A null is only evidence above its floor, which E163 showed
    is where the Dreyer result quietly failed.

PLACEBO. Each candidate re-run with its delta column cluster-permuted. A placebo reaching the corrected
bar voids the run.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
**IF SOMETHING TRACKS THE CHANGE**, it is the first within-person EEG correlate of BCI performance this
project has found, and it is a stronger kind of evidence than anything in the between-subject record
because no time-invariant trait can produce it. It goes immediately to split-half replication using
`accuracy_odd` and `accuracy_even`, which this deposit ships and which makes that free.

**REGISTERED PREDICTION: NOTHING TRACKS IT, AND THE FLOOR WILL BE LOW ENOUGH FOR THAT TO MEAN
SOMETHING.** The reasoning is specific rather than pessimistic: Blankertz's SMR predictor and the whole
between-subject family are **trait** measures -- they predict who will decode well, and a trait cannot
explain why the same person improves between sessions. E129 replicated that trait effect at +0.4440;
nothing in the literature claims the trait measure tracks within-person learning. So a null here is the
expected outcome and its value lies entirely in the floor being low enough to make it informative.

**The complementary possibility is what makes it worth running**: if within-person change is tracked by
something the between-subject analyses missed, that measure is a *state* marker rather than a trait one --
and Challenge B's real target, command-following in a brain-injured patient, is a state question.

WHAT WAS ALREADY SEEN (rule 41). Q31's reliability numbers, the session structure (62 subjects, 123
pairs) and the delta-accuracy distribution quoted above. No feature delta has been correlated with any
outcome delta.

    python bsde/src/bsde/experiments/e164_stieger_change_design.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import cluster_permute, spearman                      # noqa: E402

sys.path.insert(0, HERE)
import e145_incumbent_where_the_label_is_reliable as E145                      # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e164_stieger_change.json")

TARGET = "accuracy"
INCUMBENT = "relative_alpha_power"
PERMS = 20000
FLOOR_LEVELS = (0.15, 0.20, 0.25, 0.30, 0.40)
FLOOR_DRAWS = 60
FLOOR_PERMS = 2000
FLOOR_HIT = 0.80
MIN_PAIRS, MIN_SUBJ = 100, 50
CEILING = 0.9478          # Q31: sqrt(change-score reliability 0.8983)


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def main(argv=None) -> int:
    rng = np.random.default_rng(164)
    rows, cols = E145.load()
    by = defaultdict(list)
    for r in rows:
        by[r["subject"]].append(r)
    cand = [c for c in cols if c != TARGET]
    subj, dy, dx = [], [], defaultdict(list)
    for s, v in by.items():
        v.sort(key=lambda r: _f(r["session"]))
        for a, b in zip(v, v[1:]):
            t = _f(b[TARGET]) - _f(a[TARGET])
            if not math.isfinite(t):
                continue
            subj.append(s)
            dy.append(t)
            for c in cand:
                dx[c].append(_f(b.get(c, "")) - _f(a.get(c, "")))
    subj = np.array(subj)
    dy = np.array(dy, float)
    dx = {c: np.array(v, float) for c, v in dx.items()}
    K = len(cand)
    bar = 0.05 / max(K, 1)
    out = {"experiment": "E164", "n_pairs": int(len(dy)), "n_subjects": int(len(set(subj.tolist()))),
           "n_candidates": K, "perms": PERMS, "ceiling": CEILING}

    g1 = len(dy) >= MIN_PAIRS and len(set(subj.tolist())) >= MIN_SUBJ
    print(f"G1 COVERAGE  {len(dy)} consecutive session pairs from {len(set(subj.tolist()))} subjects "
          f"(floors {MIN_PAIRS}/{MIN_SUBJ}) -> {'PASS' if g1 else 'FAIL'}")
    g2 = float(dy.std(ddof=1)) >= 0.05
    print(f"G2 OUTCOME VARIES  delta accuracy mean {dy.mean():+.4f} sd {dy.std(ddof=1):.4f} "
          f"range [{dy.min():+.3f}, {dy.max():+.3f}] -> {'PASS' if g2 else 'FAIL'}")
    print(f"G3 CEILING QUOTED  change-score reliability 0.8983 (Q31) caps any correlation at "
          f"{CEILING:.4f} -- so a null here is a real null, not attenuation")

    def null_frac(v, obs, reps=PERMS):
        m = np.isfinite(v) & np.isfinite(dy)
        if m.sum() < 20:
            return float("nan")
        hits = 0
        for _ in range(reps):
            p = cluster_permute(dy[m], subj[m], rng)
            r = spearman(list(v[m]), list(p))
            hits += math.isfinite(r) and abs(r) >= abs(obs)
        return hits / reps

    # ---- G4 detectability floor -------------------------------------------------------------------------
    print(f"\nG4 DETECTABILITY FLOOR  {FLOOR_DRAWS} draws x {len(FLOOR_LEVELS)} levels, "
          f"{FLOOR_PERMS} perms, detection = p < {bar:.5f}")
    z0 = (dy - dy.mean()) / (dy.std() + 1e-12)
    floor = {}
    for rho in FLOOR_LEVELS:
        hits = 0
        for _ in range(FLOOR_DRAWS):
            v = rho * z0 + math.sqrt(max(1 - rho ** 2, 0.0)) * rng.standard_normal(len(dy))
            obs = spearman(list(v), list(dy))
            hits += null_frac(v, obs, reps=FLOOR_PERMS) < bar
        floor[rho] = hits / FLOOR_DRAWS
        print(f"   rho={rho:.2f}  detected in {floor[rho]:6.1%} of draws")
    det = [r for r in FLOOR_LEVELS if floor[r] >= FLOOR_HIT]
    fl = min(det) if det else None
    g4 = fl is not None
    print(f"   FLOOR = {fl if fl is not None else 'above ' + str(max(FLOOR_LEVELS))} -> "
          f"{'PASS' if g4 else 'FAIL'}")
    out["G1"], out["G2"] = bool(g1), {"pass": bool(g2), "sd": float(dy.std(ddof=1))}
    out["G4"] = {"pass": bool(g4), "floor": fl, "rates": {str(k): v for k, v in floor.items()}}

    gates = g1 and g2 and g4
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    print(f"{'candidate':32s} {'rho(dx,dy)':>11s} {'p':>8s} {'p_holm':>8s} {'placebo p':>10s}")
    res, pv = {}, {}
    for c in sorted(cand):
        v = dx[c]
        m = np.isfinite(v) & np.isfinite(dy)
        if m.sum() < MIN_PAIRS * 0.8:
            res[c] = {"skipped": int(m.sum())}
            continue
        obs = spearman(list(v[m]), list(dy[m]))
        p = null_frac(v, obs)
        # The placebo is the identical test on a cluster-permuted copy of the candidate: same values,
        # same nesting, association destroyed. Built as a full-length column so `null_frac`'s own finite
        # mask picks out exactly the rows the real test used.
        vp = np.full(len(dy), np.nan)
        vp[m] = cluster_permute(v[m], subj[m], rng)
        pc = null_frac(vp, spearman(list(vp[m]), list(dy[m])))
        res[c] = {"rho": obs, "p": p, "placebo_p": pc, "n": int(m.sum())}
        pv[c] = p
        print(f"{c:32s} {obs:+11.4f} {p:8.5f} {'':8s} {pc:10.5f}")
    adj = holm(list(pv.values()), list(pv.keys()))
    for c, a in adj.items():
        res[c]["p_holm"] = a
        res[c]["tracks"] = bool(a < 0.05)
    out["primary"], out["holm"] = res, adj

    win = [c for c, v in res.items() if v.get("tracks")]
    fired = [c for c, v in res.items()
             if math.isfinite(v.get("placebo_p", float("nan"))) and v["placebo_p"] < bar]
    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif fired:
        verdict = f"VOID -- the placebo reached the corrected bar for {', '.join(fired[:4])}"
    elif win:
        verdict = (f"WITHIN-PERSON TRACKING -- {', '.join(win)} correlate with the change in BCI accuracy "
                   f"across consecutive sessions in the same subject, Holm-corrected, against a "
                   f"subject-clustered permutation null with a measured floor of rho {fl}. No "
                   f"time-invariant trait can produce this. Replicate on accuracy_odd vs accuracy_even "
                   f"before anything else is said, and note that a STATE marker is what Challenge B's "
                   f"real target needs.")
    else:
        verdict = (f"NEGATIVE, AND INFORMATIVE -- none of {K} feature changes tracks the change in "
                   f"accuracy, on a label whose change-score reliability is 0.8983 (ceiling {CEILING}) "
                   f"and with a measured floor of rho {fl}. The between-subject family is a TRAIT family "
                   f"and does not become a state marker by being differenced. Registered prediction "
                   f"confirmed.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
