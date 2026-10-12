#!/usr/bin/env python3
"""E144 -- E143's question with a decision rule that can resolve an answer, and in the incumbent's own units.

REGISTERED BEFORE ANY INCREMENT UNDER THE NEW RULE HAS BEEN COMPUTED. Successor to E143, which returned
NO VERDICT. The cohort, the incumbent, the 32 candidates and the bar are E143's untouched; two instruments
changed and both are named below and in the ledger row.

=========================================================================================================
WHAT E143 ESTABLISHED AND WHAT IT BROKE
=========================================================================================================
**G2 failed and it is trustworthy.** `relative_alpha_power` -- the Challenge B incumbent, marginal
rho **+0.2018** against `imagery_auc`, reproduced here to four decimals -- does **not** beat an
intercept-only model out of bag: increment **-0.01021 [-0.02838, +0.01392]** over 400 reps at the default
alpha, where the 2.5th and 97.5th percentiles are perfectly estimable. That result stands and this file
does not relitigate it.

**G3 failed at 0.0 % detection for every injected effect up to rho_partial = 0.40**, which is not
credible as a statement about the data and is mostly a statement about the rule. The Bonferroni interval
E143 registered required the **0.078th percentile** of the bootstrap distribution; with 400 draws that
percentile IS the minimum, and with the 150 draws used in the floor sweep it is the minimum of 150. An
extreme quantile is not estimable at those rep counts -- roughly 2,600 would be needed before the number
means anything. My defect, the third gate-mechanics defect of the day after E140's GATE Q and E141's
GATE N, and the same lesson each time: rule 30 says check the rule's own mechanics, not only its bar.

=========================================================================================================
THE TWO INSTRUMENT CHANGES
=========================================================================================================
**1. THE DECISION RULE. A one-sided tail FRACTION replaces an extreme quantile.** The out-of-bag
difference array is now returned and the statistic is `p = fraction of out-of-bag differences >= 0`
(help is negative). A tail fraction is estimable to 1/reps; at **3,000 reps** the resolution is 0.00033,
comfortably finer than the corrected bar of 0.05/32 = 0.00156. Multiplicity is **Holm** across the 32
candidates rather than Bonferroni intervals, which is uniformly more powerful and identical in the worst
case.

**2. THE ERROR STATISTIC, and this one is a correction rather than a repair.** E41's incumbent claim is a
**Spearman correlation**; E143 judged "does it help" by **median absolute error**. Those are different
quantities, and a model can improve rank ordering while leaving median absolute error alone -- which for a
bounded target like an AUC in a narrow band is not a corner case but the expected case. This file uses
`stat(y, pred) = -spearman(y, pred)`, so lower is still better and "negative increment means B helps"
survives unchanged.

**G2 IS RE-ASKED IN THE NEW UNITS AND CAN STILL FAIL.** An intercept-only model has constant predictions
and no rank, so the baseline becomes the incumbent against a **permuted copy of itself** -- a proper
placebo baseline that is well defined for a rank statistic. If the incumbent cannot beat its own
permutation out of bag, then Challenge B's incumbent is not predictive on its own target in its own units
either, and that is a finding rather than an obstacle: it would mean this deposit has no incumbent to add
to, and the whole "increment over the incumbent" framing must be replaced rather than repeated.

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE >= 90 subjects (observed 104).
G2  INCUMBENT ALIVE in rank units, against its own permutation, Holm-uncorrected p < 0.05.
G3  DETECTABILITY FLOOR, unchanged in construction and re-measured under the new rule: synthetic
    candidates with known partial correlation given the incumbent, rho_partial in
    {0.10, 0.15, 0.20, 0.25, 0.30, 0.40}, 60 draws each, detection = corrected p < 0.05/32. Report the
    smallest level detected in >= 80 % of draws. **If the floor is again above 0.40, the conclusion is
    that this target cannot support an increment test at n = 104 under ANY rule, and Challenge B needs a
    different design or a different deposit -- which would be a real finding about the programme's
    Challenge B line rather than another null.**
G4  ONE ROW PER SUBJECT after reduction (rule 69).

PLACEBO. Each candidate re-run permuted. A firing placebo voids the run.

=========================================================================================================
PRIMARY, WRONG-DIRECTION BRANCH FIRST (rule 37)
=========================================================================================================
**IF SOMETHING ADDS** at Holm-corrected p < 0.05, it is the first thing this project has found that
improves on the Challenge B incumbent on its own target, and it goes straight to split-half replication
inside eegmmidb before any word about transport.

**REGISTERED PREDICTION: NOTHING ADDS, AND G2 FAILS AGAIN.** The reasoning is E143's own G2 plus the
marginal table it produced: three candidates already correlate with the label ABOVE the incumbent
(`cl_norm` +0.2626, `lrtc_alpha` +0.2446, `alpha_prom` +0.2221) and none of them converted into an
increment under any rule. If a candidate that out-correlates the incumbent marginally cannot beat it in an
increment, the limiting factor is the label, not the feature set -- and E38 measured that limit directly:
split-half reliability r_sb = +0.2918, ceiling sqrt(r_sb) = **0.5402**, with the incumbent at 0.2018
sitting at 37 % of it.

**IF G2 PASSES this time**, then the MAE-versus-rank mismatch was the whole of E143's G2 failure, the
incumbent is alive after all, and the increment test is worth running properly -- which is the more
favourable branch and is written first so it cannot be claimed afterwards as expected.

WHAT WAS ALREADY SEEN (rule 41). All of E143's output: its marginal correlations, its 32 null increments
under the MAE rule, its zero-power floor, and its G2 failure. No increment under the rank rule and no
floor under the new decision rule.

    python bsde/src/bsde/experiments/e144_increment_over_incumbent_rank.py
"""
from __future__ import annotations

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
from e143_increment_over_the_real_incumbent import (INCUMBENT, LABEL,          # noqa: E402
                                                    MIN_SUBJECTS, load)

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e144_increment_over_incumbent_rank.json")

REPS = 3000
FLOOR_LEVELS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40)
FLOOR_DRAWS = 60
FLOOR_REPS = 1500
FLOOR_HIT = 0.80


def rank_stat(t, p):
    """-Spearman, so lower is better and the B-minus-A convention still means 'negative helps'."""
    r = spearman(list(np.asarray(t, float)), list(np.asarray(p, float)))
    return -r if math.isfinite(r) else float("nan")


def inc_p(Xa, Xb, y, sid, rng, reps=REPS):
    """Out-of-bag increment plus the one-sided tail fraction, which is what E143 could not resolve."""
    m, lo, hi, n, d = oob_regression_increment(Xa, Xb, y, sid, rng, stat=rank_stat, reps=reps,
                                               return_diffs=True)
    p = float((d >= 0).mean()) if len(d) else float("nan")
    return m, lo, hi, n, p


def main(argv=None) -> int:
    rng = np.random.default_rng(144)
    per, lab, cols = load()
    cand = sorted({c for v in cols.values() for c in v} - {INCUMBENT})
    subs = sorted(s for s in per if s in lab and math.isfinite(per[s].get(INCUMBENT, float("nan"))))
    y = np.array([lab[s] for s in subs], float)
    inc = np.array([[per[s][INCUMBENT]] for s in subs], float)
    sid = np.array(subs)
    K = len(cand)
    bar = 0.05 / K
    out = {"experiment": "E144", "n_subjects": len(subs), "n_candidates": K, "reps": REPS}

    g1 = len(subs) >= MIN_SUBJECTS
    g4 = len(set(subs)) == len(subs)
    print(f"G1 COVERAGE {len(subs)} subjects (floor {MIN_SUBJECTS}) -> {'PASS' if g1 else 'FAIL'}")
    print(f"G4 ONE ROW PER SUBJECT -> {'PASS' if g4 else 'FAIL'}")
    print(f"   {K} candidates, Holm across them; the floor's detection bar is {bar:.5f}")
    print(f"   incumbent marginal rho = {spearman(list(inc[:, 0]), list(y)):+.4f}")

    # ---- G2 incumbent against its own permutation, in rank units --------------------------------------
    perm = inc[rng.permutation(len(subs))]
    m, lo, hi, n, p = inc_p(perm, inc, y, sid, rng)
    g2 = math.isfinite(p) and p < 0.05
    print(f"G2 INCUMBENT ALIVE (rank units, vs its own permutation): {m:+.5f} "
          f"[{lo:+.5f}, {hi:+.5f}] p={p:.5f} over {n} reps -> {'PASS' if g2 else 'FAIL'}")
    out["G1"] = {"pass": bool(g1), "n": len(subs)}
    out["G2"] = {"pass": bool(g2), "increment": m, "ci": [lo, hi], "p": p, "n_reps": n}
    out["G4"] = {"pass": bool(g4)}

    # ---- G3 detectability floor under the new rule -----------------------------------------------------
    r = y - inc[:, 0] * (np.cov(inc[:, 0], y)[0, 1] / (np.var(inc[:, 0]) + 1e-12))
    r = (r - r.mean()) / (r.std() + 1e-12)
    print(f"\nG3 DETECTABILITY FLOOR  {FLOOR_DRAWS} draws x {len(FLOOR_LEVELS)} levels, "
          f"{FLOOR_REPS} reps, detection = p < {bar:.5f}")
    floor = {}
    for rho in FLOOR_LEVELS:
        hits = 0
        for _ in range(FLOOR_DRAWS):
            z = rho * r + math.sqrt(max(1 - rho ** 2, 0.0)) * rng.standard_normal(len(subs))
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

    # ---- primary -----------------------------------------------------------------------------------------
    print(f"{'candidate':30s} {'rho(y,c)':>9s} {'increment':>10s} {'p':>8s} {'placebo p':>10s}")
    res, pvals = {}, {}
    for c in cand:
        ok = [i for i, s in enumerate(subs) if math.isfinite(per[s].get(c, float("nan")))]
        if len(ok) < MIN_SUBJECTS:
            res[c] = {"skipped": f"only {len(ok)} subjects"}
            continue
        yy, ii, ss = y[ok], inc[ok], sid[ok]
        x = np.array([per[subs[i]][c] for i in ok], float)
        m, lo, hi, n, p = inc_p(ii, np.c_[ii, x], yy, ss, rng)
        _pm, _plo, _phi, _pn, pp = inc_p(ii, np.c_[ii, rng.permutation(x)], yy, ss, rng)
        res[c] = {"rho": spearman(list(x), list(yy)), "increment": m, "ci": [lo, hi], "p": p,
                  "placebo_p": pp, "n_subjects": len(ok), "n_reps": n}
        pvals[c] = p
        print(f"{c:30s} {res[c]['rho']:+9.4f} {m:+10.5f} {p:8.5f} {pp:10.5f}")
    adj = holm(list(pvals.values()), list(pvals.keys()))
    for c, a in adj.items():
        res[c]["p_holm"] = a
        res[c]["helps"] = bool(a < 0.05)
    out["primary"] = res
    out["holm"] = adj

    winners = [c for c, v in res.items() if v.get("helps")]
    fired = [c for c, v in res.items() if math.isfinite(v.get("placebo_p", float("nan")))
             and v["placebo_p"] < bar]
    print(f"\nHolm-corrected: {len(winners)} candidate(s) with p_holm < 0.05  "
          f"{'-> ' + ', '.join(winners) if winners else ''}")
    print(f"Placebo fired for {len(fired)} candidate(s) {fired if fired else ''}")

    if not gates:
        verdict = ("NO VERDICT -- " +
                   ("G2 failed: the Challenge B incumbent does not beat its own permutation out of bag in "
                    "rank units either, so this deposit has no incumbent to add to and the "
                    "'increment over the incumbent' framing must be replaced rather than repeated. "
                    if not g2 else "") +
                   ("G3 failed: no injected effect up to rho_partial 0.40 is detectable, so this target "
                    "cannot support an increment test at n=104 under any rule and Challenge B needs a "
                    "different design or deposit." if not g3 else ""))
    elif fired:
        verdict = f"VOID -- the placebo fired for {', '.join(fired[:4])}"
    elif winners:
        verdict = (f"POSITIVE -- {', '.join(winners)} add to the Challenge B incumbent on its own target "
                   f"at Holm-corrected p < 0.05, with a measured detectability floor of rho_partial "
                   f"{fl}. Queue split-half replication inside eegmmidb.")
    else:
        verdict = (f"NEGATIVE -- nothing of {K} adds to {INCUMBENT}, and the floor is rho_partial {fl}, "
                   f"so the null is informative above that and uninformative below it.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
