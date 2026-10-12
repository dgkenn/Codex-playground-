"""E90 -- Is a self-computed aperiodic index AVAILABLE at emergence, where the commercial index is not?

REGISTERED AFTER E89's GATE FAILURE AND BECAUSE OF IT, on the same table, with the endpoint changed from
increment to availability. What was seen first, and it is the whole reason this exists: of 579 VitalDB
windows within 600 s of anaesthesia end, **173 carry a finite BIS (29.9 %) against 5,672 of 6,100
elsewhere (93.0 %)**, while the aperiodic exponent is finite in 435 of the same 579 (75.1 %). Median SQI
is 90.4 at emergence against 92.3 elsewhere, so this is not a quiet signal-quality collapse.

Those counts are descriptive and pooled. **This experiment asks whether the gap survives the two things
that could explain it away: it might be a general availability difference that has nothing to do with
emergence, and it might be driven by a handful of cases.**

=========================================================================================================
THE ESTIMAND -- a difference in differences, because the raw gap is not the claim
=========================================================================================================
Per case, over windows with a finite `meta_rel_aneend_s`:

    gap_emergence = P(exponent finite | within 600 s of end) - P(BIS finite | same windows)
    gap_elsewhere = P(exponent finite | all other windows)  - P(BIS finite | same windows)

    P  DiD = mean_case[ gap_emergence - gap_elsewhere ], case-level bootstrap.

**Differencing is what makes this an emergence claim.** If our exponent is simply computable more often
than BIS everywhere, `gap_elsewhere` absorbs it and the DiD goes to zero -- which would be the correct
answer, and is the outcome the raw counts cannot distinguish from the interesting one.

    PREDICTED: DiD > 0.

VERDICT, wrong direction FIRST (rule 37):

    (a) interval excludes 0 and NEGATIVE -> WORSE AT EMERGENCE. Our index drops out at emergence MORE than
        BIS does. That would make an emergence-trend use case less feasible with a self-computed index,
        not more, and it must print as that rather than as "no difference".
    (b) interval includes 0              -> NO EMERGENCE-SPECIFIC GAP. Any pooled difference is a general
        availability difference, and the emergence framing is dropped.
    (c) interval excludes 0 and POSITIVE -> AVAILABLE AT EMERGENCE. The gap is specific to the peri-
        emergence period.

GATES (rule 40):

    G1  COVERAGE  >= 80 cases contributing at least 3 emergence windows and 3 non-emergence windows. A
                  within-case DiD needs both cells in the same case or it is a between-case comparison
                  wearing a paired name.
    G2  BOTH CELLS VARY. Across cases, both `gap_emergence` and `gap_elsewhere` must have non-zero
                  variance. If every case has an identical gap the bootstrap interval is degenerate and
                  the DiD is a constant, not an estimate.
    G3  PLACEBO LANDMARK, and this is the gate that can kill it. The same DiD is recomputed against a
                  FAKE landmark: a random time point drawn within each case's own recorded span, with the
                  same 600 s half-width and the same minimum cell sizes, 200 draws. **If an arbitrary
                  moment in the case produces the same availability gap, the finding is about time-in-case
                  or about record edges, not about emergence.** Any real DiD inside the placebo's central
                  95 % is WITHDRAWN. Rule 34: the gate is a comparison against the placebo, never a
                  threshold.

=========================================================================================================
THE INTERPRETATION THAT MUST TRAVEL WITH ANY POSITIVE RESULT
=========================================================================================================
**BIS is written by the vendor's device; the exponent is computed here from the raw waveform.** An
availability gap is therefore a fact about DEVICE BEHAVIOUR -- when the monitor stops publishing its index
while the amplifier keeps publishing a wave -- and not a fact about the brain, about consciousness, or
about which measure is more accurate. It is operationally meaningful precisely and only in this sense: an
index you compute yourself exists in periods where the vendor's does not.

It also says nothing about whether the exponent is CORRECT in those windows. Availability is not validity,
and the windows where a monitor withdraws its own index are exactly the windows where an artefact is most
likely. Establishing that the exponent is trustworthy there is a separate experiment and is not attempted
here; E22 and E58 measured that this deposit's light-end windows are overwhelmingly facial EMG, which is a
reason for caution, not encouragement.

    python -m bsde.experiments.e90_emergence_availability
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

TABLE = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e90_emergence_availability.json")

FEATURE = "whole_head_exponent"
HALF_WIDTH = 600.0
MIN_CELL = 3
MIN_CASES = 80
REPS = 4000
PLACEBO_DRAWS = 200
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    by = defaultdict(list)
    for r in csv.DictReader(open(TABLE, newline="")):
        e = _f(r["meta_rel_aneend_s"])
        if not np.isfinite(e):
            continue
        by[r["subject"]].append({"t": e,
                                 "bis": np.isfinite(_f(r["meta_bis"])),
                                 "feat": np.isfinite(_f(r.get(FEATURE, "")))})
    return by


def did(by, centre_fn):
    """centre_fn(case_rows) -> the landmark time in the same units as `t`."""
    vals = []
    for case, rows in by.items():
        t = np.array([r["t"] for r in rows])
        c = centre_fn(rows)
        if c is None:
            continue
        near = np.abs(t - c) <= HALF_WIDTH
        far = ~near
        if near.sum() < MIN_CELL or far.sum() < MIN_CELL:
            continue
        b = np.array([r["bis"] for r in rows], float)
        f = np.array([r["feat"] for r in rows], float)
        g_near = f[near].mean() - b[near].mean()
        g_far = f[far].mean() - b[far].mean()
        vals.append(g_near - g_far)
    return np.asarray(vals, float)


def boot(v, seed, reps=REPS):
    if v.size < 5:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    b = v[rng.integers(0, v.size, size=(reps, v.size))].mean(axis=1)
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE}"); return 2
    by = load()
    res = {"gates": {}}
    print(f"{len(by)} cases with a finite anaesthesia-end offset")

    real = did(by, lambda rows: 0.0)          # rel_aneend_s is 0 AT anaesthesia end
    res["gates"]["G1_cases"] = int(real.size)
    res["gates"]["G1_pass"] = bool(real.size >= MIN_CASES)
    print(f"G1 coverage   {real.size} cases with both cells >= {MIN_CELL} windows   "
          f"{'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    res["gates"]["G2_sd"] = float(np.std(real)) if real.size else 0.0
    res["gates"]["G2_pass"] = bool(real.size and np.std(real) > 1e-9)
    print(f"G2 variation  sd of the per-case DiD = {res['gates']['G2_sd']:.4f}   "
          f"{'PASS' if res['gates']['G2_pass'] else 'FAIL'}")

    if not (res["gates"]["G1_pass"] and res["gates"]["G2_pass"]):
        print("\nGATE FAILED -- the primary is not evaluated. Verdict ABSENT (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    pt = float(real.mean())
    lo, hi = boot(real, SEED)
    print(f"\nPRIMARY  DiD = {pt:+.4f} [{lo:+.4f}, {hi:+.4f}] over {real.size} cases")

    # descriptive: the two halves of the difference, so a reader can see which one moves
    def cell_means(centre_fn):
        gn, gf = [], []
        for case, rows in by.items():
            t = np.array([r["t"] for r in rows])
            c = centre_fn(rows)
            near = np.abs(t - c) <= HALF_WIDTH
            far = ~near
            if near.sum() < MIN_CELL or far.sum() < MIN_CELL:
                continue
            b = np.array([r["bis"] for r in rows], float)
            f = np.array([r["feat"] for r in rows], float)
            gn.append(f[near].mean() - b[near].mean())
            gf.append(f[far].mean() - b[far].mean())
        return float(np.mean(gn)), float(np.mean(gf))
    g_near, g_far = cell_means(lambda rows: 0.0)
    res["descriptive"] = {"gap_emergence": g_near, "gap_elsewhere": g_far}
    print(f"    gap at emergence {g_near:+.4f}; gap elsewhere {g_far:+.4f}")

    rng = np.random.default_rng(SEED + 1)
    pl = []
    for _ in range(PLACEBO_DRAWS):
        def fake(rows, _rng=rng):
            t = np.array([r["t"] for r in rows])
            return float(_rng.uniform(t.min(), t.max()))
        v = did(by, fake)
        if v.size >= 5:
            pl.append(float(v.mean()))
    pl = np.asarray(pl, float)
    p_lo, p_hi = (float(np.percentile(pl, 2.5)), float(np.percentile(pl, 97.5))) if pl.size else (np.nan,) * 2
    inside = bool(pl.size and p_lo <= pt <= p_hi)
    res["placebo"] = {"lo": p_lo, "hi": p_hi, "n_draws": int(pl.size), "inside": inside}
    print(f"G3 placebo    random landmark: [{p_lo:+.4f}, {p_hi:+.4f}] over {pl.size} draws   "
          f"{'primary INSIDE -- withdrawn' if inside else 'primary outside'}")

    if not np.isfinite(lo):
        v = "NOT-COMPUTABLE"
    elif lo < 0 and hi < 0:
        v = ("WORSE AT EMERGENCE -- the self-computed index drops out at emergence MORE than the "
             "commercial one does. This makes an emergence-trend use case less feasible, not more.")
    elif lo > 0 and hi > 0:
        v = ("WITHDRAWN-BY-PLACEBO -- an arbitrary landmark reproduces the gap, so this is about "
             "time-in-case or record edges, not emergence." if inside else
             "AVAILABLE AT EMERGENCE -- the availability gap is specific to the peri-emergence period. "
             "This is a fact about DEVICE BEHAVIOUR, not about the brain, and availability is not "
             "validity: the windows where a monitor withdraws its index are the windows where artefact is "
             "most likely, which is a reason for caution.")
    else:
        v = ("NO EMERGENCE-SPECIFIC GAP -- any pooled difference is a general availability difference and "
             "the emergence framing is dropped.")
    res["primary"] = {"DiD": pt, "lo": lo, "hi": hi, "n_cases": int(real.size)}
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
