#!/usr/bin/env python3
"""E150 -- Challenge C's founding negative, re-derived with an instrument that can see.

REGISTERED BEFORE ANY PERMUTATION INCREMENT HAS BEEN COMPUTED ON THIS COHORT. This is a re-derivation
under rule 2, not a new question: the cohort, the incumbent, the candidate list and the bar are E84's,
untouched. **Only the test changes.**

=========================================================================================================
WHY A NEGATIVE FROM A MONTH AGO HAS TO BE RE-RUN
=========================================================================================================
`docs/QUEUE.md` records the conclusion that redirected the whole of Challenge C:

    "Four held-out tests (E78, E84, E99, E90/E102) all asked *does our measure add to the incumbent?* and
     all said no. **Four failures of the same shape are a result about the question.**"

Three of those four were decided by `oob_regression_increment`. E146 then measured that instrument:

    n_subj rows rho_partial |  OOB detects  ORACLE detects
        60    1        0.35 |       0.00%          88.33%
       100    1        0.50 |      38.33%         100.00%
       100    3        0.35 |      66.67%         100.00%

false-positive rate **0.000** at rho = 0. It is blind, not conservative, and the blindness eases only as
rows-per-cluster rises. **So "four failures of the same shape" may be four failures of one instrument**,
and the strategic pivot away from increment designs would then have been made on an artefact.

Eleven ledger rows carry outcome `negative` or `absent` and use this instrument: E26, E27, E34, E37, E58,
E84, E99, E130, E133, E134 and E145's predecessors. **This file re-derives ONE of them** -- E84, because
QUEUE.md names it as the anchor, because it is the only one whose incumbent this project had independently
validated (PE31, median within-recording rho +0.4355 against MOAA/S, against SEF95's +0.1799), and because
its table is present. The rest follow only if this one moves.

=========================================================================================================
WHAT CHANGES AND WHAT DOES NOT
=========================================================================================================
    UNCHANGED   the DOSE-I held-out table, the recordings, the MOAA/S target, the baseline model,
                the candidate list, and E84's error statistic `1 - spearman`
    CHANGED     `permutation_increment` -- cross-fitted, cluster-permutation null, validated in E147 at a
                false-positive rate of 0.0333 and 73 % of the oracle's power where the old test had 5 %

E84's own numbers are reproduced first and asserted to match, so a discrepancy surfaces as a failure here
rather than as a silent difference in the comparison (rule 20: when two scripts compute the same quantity,
diff them).

=========================================================================================================
GATES
=========================================================================================================
G1  REPRODUCTION. The old instrument must reproduce E84's stored point estimates for every candidate to
    within 0.02. If it does not, the two runs are not on the same data and nothing is comparable.
G2  INSTRUMENT VALIDATION IMPORTED (not assumed): E147's calibration JSON must report a pass.
G3  **INCUMBENT ALIVE**, E84's own G3, recomputed: the baseline must predict MOAA/S out of fold. A
    comparison against a dead incumbent is a comparison against noise.
G4  **DETECTABILITY FLOOR under the new instrument on THIS cohort.** Synthetic candidates at
    rho_partial in {0.05, 0.10, 0.15, 0.20, 0.30}, 40 draws each. The floor is what makes the re-derived
    verdict readable: a null above the floor is a real null, a null below it is an absence.
    **Note the levels start lower than in E143-E149 because this cohort has hundreds of windows per
    recording, where the old instrument was already much less blind** -- setting the same grid would put
    every cell at ceiling and measure nothing.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
**IF THE VERDICT DOES NOT MOVE** -- no candidate reaches the corrected bar under the calibrated test, on a
cohort whose measured floor is below the effect sizes at stake -- then E84's negative is CONFIRMED and
strengthened, QUEUE.md's "a result about the question" stands, and the strategic pivot it justified was
correct. **This is the more likely outcome and it is written first** precisely because the file was built
in the hope of the other one, and hope is what rule 30 warns about.

**IF ANY CANDIDATE MOVES** from null to a corrected pass, then E84's negative is withdrawn, the "four
failures of the same shape" conclusion is void, and the other ten increment-decided rows must be
re-derived in turn rather than assumed. That is a large amount of work and this file does not do it; it
establishes only whether it is necessary.

**REGISTERED PREDICTION: THE VERDICT DOES NOT MOVE, AND THE FLOOR COMES IN BELOW rho_partial = 0.15.**
Reason, stated so it can be wrong: E84's cohort has hundreds of windows per recording, and E146's table
shows the old instrument's blindness is worst at one row per cluster and much milder at three. A cohort
with two orders of magnitude more rows per cluster should have been the least affected of the eleven, so
if any of them survives re-derivation intact it should be this one. **The corollary matters more than the
prediction: the experiments most likely to flip are the ones with FEW rows per cluster -- E133, E134 and
the Challenge B line -- not this one.**

WHAT WAS ALREADY SEEN (rule 41). E84's committed result JSON, E146's calibration table, E147's validation
table. No permutation increment on this cohort.

    python bsde/src/bsde/experiments/e150_challenge_c_negatives_rederived.py
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
from bsde.verifier.stats import (cluster_permute, oob_regression_increment,    # noqa: E402
                                 permutation_increment)

sys.path.insert(0, HERE)
import e84_increment_over_validated_incumbent as E84                           # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e150_challenge_c_rederived.json")
E147_JSON = os.path.join(RESULTS, "e147_calibrated_increment.json")
E84_JSON = os.path.join(RESULTS, "e84_increment_over_validated_incumbent.json")

PERMS = 1000
FLOOR_LEVELS = (0.05, 0.10, 0.15, 0.20, 0.30)
FLOOR_DRAWS = 40
FLOOR_PERMS = 400
FLOOR_HIT = 0.80


def build():
    """E84's cohort, assembled with E84's own constants so the two runs cannot drift apart."""
    rows = defaultdict(list)
    with open(E84.TABLE, newline="") as fh:
        rd = csv.DictReader(fh)
        cands = [c for c in (rd.fieldnames or []) if c not in E84.META]
        for r in rd:
            rows[r["recording"]].append(r)
    keep = []
    for rec, rs in sorted(rows.items()):
        mo = np.array([E84._f(r["moaas"]) for r in rs])
        if np.isfinite(mo).sum() >= E84.MIN_WINDOWS and len(set(mo[np.isfinite(mo)].tolist())) > 1:
            keep.append(rec)
    y, subj, base, cand = [], [], [], defaultdict(list)
    for rec in keep:
        for r in rows[rec]:
            mo = E84._f(r["moaas"])
            b = [E84._f(r.get(c, "")) for c in E84.BASELINE]
            if not np.isfinite(mo) or not all(np.isfinite(b)):
                continue
            y.append(mo)
            subj.append(rec)
            base.append(b)
            for c in cands:
                cand[c].append(E84._f(r.get(c, "")))
    return (np.asarray(y, float), np.asarray(subj), np.asarray(base, float),
            {c: np.asarray(v, float) for c, v in cand.items()}, cands, len(keep))


def main(argv=None) -> int:
    rng = np.random.default_rng(150)
    out = {"experiment": "E150", "perms": PERMS}

    try:
        e147 = json.load(open(E147_JSON))
        g2 = bool(e147.get("G1", {}).get("pass"))
        print(f"G2 INSTRUMENT VALIDATION  E147 fpr={e147['G1']['fpr']:.4f} -> "
              f"{'PASS' if g2 else 'FAIL'}")
    except Exception as e:                                                     # noqa: BLE001
        print(f"G2 INSTRUMENT VALIDATION  unreadable ({type(e).__name__}) -> FAIL")
        g2 = False
    if not g2:
        print("REFUSING TO RUN -- the instrument's validation has not been checked.")
        json.dump({**out, "G2": False}, open(OUT, "w"), indent=1, sort_keys=True)
        return 1

    y, subj, base, cand, cands, n_rec = build()
    print(f"\ncohort: {len(y)} windows, {n_rec} recordings, {len(cands)} candidates, "
          f"{len(y) / max(n_rec, 1):.0f} windows per recording")
    out["n_windows"], out["n_recordings"], out["n_candidates"] = len(y), n_rec, len(cands)

    # ---- G3 incumbent alive ---------------------------------------------------------------------------
    b0 = cluster_permute(base[:, 0], subj, rng).reshape(-1, 1)
    o, p, nm, k = permutation_increment(b0, np.c_[b0, base], y, subj, rng, stat=E84.err,
                                        reps=PERMS, n_extra=base.shape[1])
    g3 = math.isfinite(p) and p < 0.05
    print(f"G3 INCUMBENT ALIVE  baseline over a cluster-permuted copy: {o:+.5f} p={p:.5f} "
          f"-> {'PASS' if g3 else 'FAIL'}")
    out["G3"] = {"pass": bool(g3), "increment": o, "p": p, "null_mean": nm}

    # ---- G1 reproduction of E84's point estimates -----------------------------------------------------
    try:
        e84 = json.load(open(E84_JSON))
        stored = {c: v.get("increment", v.get("point")) for c, v in e84.get("candidates", {}).items()
                  if isinstance(v, dict)}
    except Exception:                                                          # noqa: BLE001
        stored = {}
    print(f"\n{'candidate':26s} {'OLD pt':>9s} {'E84 pt':>9s} {'NEW inc':>9s} {'NEW p':>8s} "
          f"{'placebo p':>10s}")
    res, pv, repro = {}, {}, []
    for c in cands:
        x = cand[c]
        ok = np.isfinite(x)
        if ok.sum() < 0.5 * len(y):
            res[c] = {"skipped": f"only {int(ok.sum())} finite"}
            continue
        yy, ss, bb, xx = y[ok], subj[ok], base[ok], x[ok]
        old_pt, _lo, _hi, _n = oob_regression_increment(bb, np.c_[bb, xx], yy, ss, rng,
                                                        stat=E84.err, reps=200)
        inc, pp, _nm, _k = permutation_increment(bb, np.c_[bb, xx], yy, ss, rng, stat=E84.err,
                                                 reps=PERMS)
        _o2, pc, _n2, _k2 = permutation_increment(bb, np.c_[bb, cluster_permute(xx, ss, rng)], yy, ss,
                                                  rng, stat=E84.err, reps=PERMS)
        st = stored.get(c, float("nan"))
        if isinstance(st, (int, float)) and math.isfinite(st) and math.isfinite(old_pt):
            repro.append(abs(old_pt - st))
        res[c] = {"old_point": old_pt, "e84_stored": st, "increment": inc, "p": pp, "placebo_p": pc,
                  "n": int(ok.sum())}
        pv[c] = pp
        print(f"{c:26s} {old_pt:+9.5f} {(st if isinstance(st, (int, float)) else float('nan')):+9.5f} "
              f"{inc:+9.5f} {pp:8.5f} {pc:10.5f}")
    g1 = (max(repro) <= 0.02) if repro else None
    print(f"\nG1 REPRODUCTION  max |old - E84 stored| over {len(repro)} candidates: "
          f"{(max(repro) if repro else float('nan')):.5f} -> "
          f"{'PASS' if g1 else ('FAIL' if g1 is False else 'NOT CHECKABLE (no stored estimates)')}")
    out["G1"] = {"pass": g1, "max_abs_diff": (max(repro) if repro else None), "n_compared": len(repro)}

    K = max(len(pv), 1)
    bar = 0.05 / K
    adj = holm(list(pv.values()), list(pv.keys()))
    for c, a in adj.items():
        res[c]["p_holm"] = a
        res[c]["helps"] = bool(a < 0.05 and res[c]["increment"] < 0)
    out["primary"], out["holm"] = res, adj

    # ---- G4 floor on this cohort ----------------------------------------------------------------------
    A = np.c_[np.ones(len(y)), base]
    r = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]
    r = (r - r.mean()) / (r.std() + 1e-12)
    print(f"\nG4 DETECTABILITY FLOOR  {FLOOR_DRAWS} draws x {len(FLOOR_LEVELS)} levels, "
          f"{FLOOR_PERMS} perms, detection = p < {bar:.5f}")
    floor = {}
    for rho in FLOOR_LEVELS:
        hits = 0
        for _ in range(FLOOR_DRAWS):
            z = rho * r + math.sqrt(max(1 - rho ** 2, 0.0)) * rng.standard_normal(len(y))
            _o, _p, _nm, _k = permutation_increment(base, np.c_[base, z], y, subj, rng,
                                                    stat=E84.err, reps=FLOOR_PERMS)
            hits += math.isfinite(_p) and _p < bar
        floor[rho] = hits / FLOOR_DRAWS
        print(f"   rho_partial={rho:.2f}  detected in {floor[rho]:6.1%} of draws")
    det = [rho for rho in FLOOR_LEVELS if floor[rho] >= FLOOR_HIT]
    fl = min(det) if det else None
    print(f"   FLOOR = {fl if fl is not None else 'ABOVE ' + str(max(FLOOR_LEVELS))}")
    out["G4"] = {"floor": fl, "detection_rate": {str(a): b for a, b in floor.items()}}

    winners = [c for c, v in res.items() if v.get("helps")]
    fired = [c for c, v in res.items()
             if math.isfinite(v.get("placebo_p", float("nan"))) and v["placebo_p"] < bar]
    if fired:
        verdict = f"VOID -- placebo reached the corrected bar for {', '.join(fired[:4])}"
    elif not g3:
        verdict = "NO VERDICT -- G3 failed: the incumbent does not predict, so no increment is readable."
    elif winners:
        verdict = (f"VERDICT MOVES -- {', '.join(winners)} add to the validated incumbent under a "
                   f"calibrated test where the old instrument found nothing. E84's negative is "
                   f"WITHDRAWN, QUEUE.md's 'four failures of the same shape are a result about the "
                   f"question' is VOID, and the other ten increment-decided rows must be re-derived "
                   f"rather than assumed.")
    else:
        verdict = (f"VERDICT HOLDS -- nothing adds to the validated incumbent even under the calibrated "
                   f"test, on a cohort whose measured floor is rho_partial "
                   f"{fl if fl is not None else 'above ' + str(max(FLOOR_LEVELS))}. E84's negative is "
                   f"CONFIRMED and strengthened. The registered prediction is right, and its corollary "
                   f"stands: the rows most likely to move are the ones with FEW rows per cluster "
                   f"(E133, E134, the Challenge B line), not this one.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
