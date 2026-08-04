#!/usr/bin/env python3
"""E62 -- Q22. Is the deep-band failure the INDEX's or the REFERENCE's? The monitor's own flag decides.

REGISTERED BEFORE ANY SQI-FILTERED FIDELITY HAS BEEN COMPUTED. What is known and committed: E58's and
E60's unfiltered per-band tables, and E60's post-hoc observation that the [0,20) sub-band carries median
|err| 39.96 under both models with **median SQI 5.1 of 100** and EMG 38.2, on 90 windows from 68 cases.
Nothing has been recomputed on a filtered cohort.

=========================================================================================================
THE QUESTION, AND WHY IT IS A TEST RATHER THAN A CLEAN-UP
=========================================================================================================
E58's inclusion criterion was "device BIS present, sensor not off". `meta_sqi` shipped in the same table
from the start and no experiment in this project had ever used it. Applying it now is a change of cohort,
so it is registered rather than folded quietly into the existing numbers.

**The two possible explanations make OPPOSITE predictions, which is what makes this worth running.**

    REFERENCE COLLAPSE   the deep-band error is large because the device is reporting values it
                         simultaneously flags as unreliable. Then excluding low-SQI windows should remove
                         most of that band's error, and should barely touch [40,60), whose median SQI is
                         93.7.
    INDEX FAILURE        the deep-band error is ours -- the fit genuinely cannot read deep anaesthesia.
                         Then filtering on the reference's quality flag changes little anywhere.

PRIMARY is therefore a DIFFERENCE OF RELATIVE CHANGES, not a level: the relative change in median |err| in
[0,20) minus the relative change in [40,60). **Predicted strongly negative** under reference collapse, and
near zero under index failure. Taking the difference is what stops a global improvement -- filtering
removes noisy windows everywhere -- from being read as a deep-band explanation.

**G1 SURVIVAL GATE, AND IT IS EVALUATED AND REPORTED BEFORE THE PRIMARY.** If the filter empties a band
rather than cleaning it, a fidelity number computed on the remnant is a selection effect and nothing else.
The gate requires `MIN_SURVIVORS` windows and `MIN_CASES` cases to remain in [0,20). **If it fails, that IS
the result** -- "this band consists almost entirely of windows the monitor disowns" is a stronger and more
useful statement than any error figure, and the file must say so rather than printing a fidelity.

THRESHOLD. `SQI_MAIN = 50` is the primary and was fixed before any of this was computed -- it is the value
E61 had already used for a different question, chosen as the conventional midpoint of the device's own
0-100 scale rather than from any fidelity result. `SQI_ALT` are declared SENSITIVITY arms, reported
alongside so the choice is visible; **they are not candidates to select from** (rule 30: a rule set before
the run can still be set wrong, but moving it afterwards is a different and worse failure).

MODELS. Both arms of the deliverable as it now stands: E58's one-stage arm C, and E60's two-stage fit.
Each is refitted inside each cohort -- a model fitted on the unfiltered cohort and evaluated on the
filtered one would confound the cohort change with a train/test mismatch.

VERDICT RULE, wrong direction first.

  (a) INDEX FAILURE     -- the differential is >= 0, or the primary's interval includes zero. The deep-band
                           error survives the reference's own quality filter, so it is the index's problem.
                           The refusal below BIS 20 stands, and stands for a different reason than assumed.
  (b) BAND EMPTIED      -- G1 failed. Not a fidelity result at all: the band is almost entirely windows the
                           monitor disowns, which settles the refusal more decisively than a number would.
  (c) REFERENCE COLLAPSE-- the differential is negative with an interval excluding zero, AND the [40,60)
                           relative change is small. The deep-band failure is the reference's.

WHAT IT CHANGES EITHER WAY. `BIS_FAITHFUL_OR_BRAIN_FAITHFUL.md` already refuses below BIS 20 and above 60.
**No outcome here reopens either refusal** -- this experiment decides what the refusal is FOR, and fixes
which error bars ride with the bands that remain. A REFERENCE COLLAPSE verdict would also mean the reported
fidelities elsewhere are pessimistic, because they were measured over windows including ones the monitor
disowned.

    python -m bsde.experiments.e62_sqi_sensitivity
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import grouped_cv_predict                            # noqa: E402
from bsde.experiments.e58_bis_like_index import SUBPARAMS, _f, load           # noqa: E402
from bsde.experiments.e60_two_stage_range_model import _med_err, two_stage_predict   # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e62_sqi_sensitivity.json")

SQI_MAIN = 50.0
SQI_ALT = (0.0, 80.0)
DEEP = (0.0, 20.0)
TARGET = (40.0, 60.0)
BANDS = [(0.0, 20.0), (20.0, 40.0), (40.0, 60.0), (60.0, 80.0), (80.0, 101.0)]
MIN_SURVIVORS = 30
MIN_CASES = 15
REPS = 400
SEED = 20260731


def build():
    grid, sub, gfields = load()
    keys = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
    ours = [c for c in gfields if c not in keys and not c.startswith("meta_") and c not in SUBPARAMS]
    rid = [r for r in sorted(grid)
           if grid[r].get("status") == "ok"
           and str(grid[r].get("meta_sensor_off", "")).strip().lower() not in ("true", "1")
           and np.isfinite(_f(grid[r].get("meta_bis")))
           and r in sub and sub[r].get("status") == "ok"]
    y = np.array([_f(grid[r]["meta_bis"]) for r in rid])
    case = np.array([grid[r]["meta_caseid"] for r in rid])
    sqi = np.array([_f(grid[r].get("meta_sqi")) for r in rid])
    X = np.column_stack([np.array([[_f(grid[r][c]) for c in ours] for r in rid], float),
                         np.array([[_f(sub[r][c]) for c in SUBPARAMS] for r in rid], float)])
    return X, y, case, sqi


def fidelities(X, y, case):
    """Per-band median |err| for both deliverable arms, refitted inside this cohort."""
    p1 = grouped_cv_predict(X, y, case, np.random.default_rng(SEED))
    p2, _ = two_stage_predict(X, y, case, np.random.default_rng(SEED))
    out = {}
    for lo, hi in BANDS:
        m = (y >= lo) & (y < hi)
        out[f"[{lo:.0f},{min(hi, 100):.0f})"] = {
            "n": int(m.sum()), "one_stage": _med_err(y, p1, m), "two_stage": _med_err(y, p2, m)}
    return out


def main() -> int:
    X, y, case, sqi = build()
    ok_sqi = np.isfinite(sqi)
    print(f"{len(y)} windows, {len(np.unique(case))} cases; meta_sqi finite on "
          f"{100 * ok_sqi.mean():.1f}%")

    # G1 first: survival per band, before any fidelity is printed.
    print(f"\nG1 survival at SQI >= {SQI_MAIN:.0f}")
    surv = {}
    for lo, hi in BANDS:
        m = (y >= lo) & (y < hi)
        k = m & ok_sqi & (sqi >= SQI_MAIN)
        surv[f"[{lo:.0f},{min(hi, 100):.0f})"] = {
            "n_before": int(m.sum()), "n_after": int(k.sum()),
            "cases_after": int(len(np.unique(case[k]))) if k.any() else 0,
            "frac": float(k.sum() / max(1, m.sum())),
            "median_sqi": float(np.nanmedian(sqi[m])) if m.any() else float("nan")}
        s = surv[f"[{lo:.0f},{min(hi, 100):.0f})"]
        print(f"   [{lo:3.0f},{min(hi, 100):3.0f})  {s['n_before']:5d} -> {s['n_after']:5d} "
              f"({100 * s['frac']:5.1f}%)  {s['cases_after']:3d} cases   median SQI "
              f"{s['median_sqi']:5.1f}")

    deep_key = f"[{DEEP[0]:.0f},{DEEP[1]:.0f})"
    g1 = (surv[deep_key]["n_after"] >= MIN_SURVIVORS and surv[deep_key]["cases_after"] >= MIN_CASES)
    print(f"   G1 {'PASS' if g1 else 'FAIL'} (need >= {MIN_SURVIVORS} windows and {MIN_CASES} cases "
          f"in {deep_key})")

    res = {"survival": surv, "gate_g1": g1}
    if not g1:
        verdict = (f"BAND EMPTIED -- the SQI >= {SQI_MAIN:.0f} filter leaves "
                   f"{surv[deep_key]['n_after']} windows in {deep_key}, from "
                   f"{surv[deep_key]['cases_after']} cases. This is not a fidelity result and no error "
                   f"figure may be quoted on the remnant. It settles the refusal below BIS 20 more "
                   f"decisively than a number would: that band consists almost entirely of windows the "
                   f"monitor itself disowns, and the index was being scored against readings the device "
                   f"declares unreliable.")
        print(f"\nVERDICT: {verdict}")
        res["verdict"] = verdict
        json.dump(res, open(OUT, "w"), indent=2)
        print(f"wrote {OUT}")
        return 0

    base = fidelities(X, y, case)
    arms = {"unfiltered": base}
    for thr in (SQI_MAIN,) + SQI_ALT:
        if thr == 0.0:
            continue
        k = ok_sqi & (sqi >= thr)
        arms[f"sqi>={thr:.0f}"] = fidelities(X[k], y[k], case[k])

    print(f"\n{'band':<12s} " + "  ".join(f"{a:>18s}" for a in arms))
    for b in base:
        print(f"{b:<12s} " + "  ".join(
            f"{arms[a][b]['one_stage']:8.2f}/{arms[a][b]['two_stage']:<8.2f}" for a in arms))
    print("   (each cell is one-stage / two-stage median |err|)")

    def rel(band, arm):
        b0, b1 = base[band]["one_stage"], arms[arm][band]["one_stage"]
        return (b1 - b0) / b0 if np.isfinite(b0) and b0 > 0 else float("nan")

    main_arm = f"sqi>={SQI_MAIN:.0f}"
    tgt_key = f"[{TARGET[0]:.0f},{TARGET[1]:.0f})"
    d_deep, d_tgt = rel(deep_key, main_arm), rel(tgt_key, main_arm)
    diff = d_deep - d_tgt
    print(f"\nPRIMARY  relative change {deep_key} {d_deep:+.3f} minus {tgt_key} {d_tgt:+.3f} "
          f"= {diff:+.3f}   (negative = reference collapse)")

    res["arms"] = arms
    res["primary"] = {"rel_deep": d_deep, "rel_target": d_tgt, "differential": diff}
    if not np.isfinite(diff) or diff >= 0:
        verdict = ("INDEX FAILURE -- the deep-band error survives the reference's own quality filter, so "
                   "it is the index's problem and not the monitor's. The refusal below BIS 20 stands, for "
                   "a different reason than E60 assumed.")
    elif abs(d_tgt) > 0.10:
        verdict = (f"NOT INTERPRETABLE -- the target band moved by {d_tgt:+.1%} under the filter, so the "
                   f"differential is comparing two moving quantities rather than isolating the deep band.")
    else:
        verdict = ("REFERENCE COLLAPSE -- excluding windows the monitor disowns removes most of the "
                   "deep-band error while leaving the target band alone. The failure below BIS 20 is the "
                   "reference's, not the index's. This does NOT reopen the refusal: those windows still "
                   "cannot be scored against anything. It does mean fidelities reported elsewhere are "
                   "pessimistic, having been measured over windows the device declared unreliable.")
    print(f"\nVERDICT: {verdict}")
    res["verdict"] = verdict
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
