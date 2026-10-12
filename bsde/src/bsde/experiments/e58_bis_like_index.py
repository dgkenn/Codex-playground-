#!/usr/bin/env python3
"""E58 -- Q22. How faithfully can a BIS-LIKE INDEX be computed from EEG this project already has?

REGISTERED BEFORE `results/vitaldb_bis.csv` HAS BEEN JOINED TO ANYTHING. What has been read of that table
at the time of writing is a 40-window pilot on ONE case (case1), used only to confirm the four columns are
finite and that `bis_bsr` rises where the device's own `meta_sr` rises. No fit, no fold, no error statistic
and no second case has been looked at.

=========================================================================================================
WHY THIS MATTERS AND WHAT IT IS NOT
=========================================================================================================
`docs/QUEUE.md` Q22: BIS is the incumbent Challenge C actually needs, and it exists only where a monitor
recorded it -- which is why E26, E34 and E37 all fell back on SEF95 as a proxy and scoped themselves "never
ahead of BIS". A computable stand-in turns BIS into a universal comparator, available on chennu, ds005620,
ds004541, HEEDB and ds005385, none of which carry a monitor.

**Whatever this produces is a BIS-LIKE INDEX and must never be called BIS.** It is fitted to reproduce one
manufacturer's index on 250 cases from one hospital, from two frontal channels at 128 Hz, in maintenance
only. Lee et al. (PMID 31551487) report median absolute error 4.1 on their own development data; the
honest question here is how close a from-scratch reimplementation gets, and where it fails.

THE FEASIBILITY PROBE THIS FOLLOWS (rule 41, recorded in QUEUE.md Q22 on 2026-07-31). Features this repo
already computes reached a case-grouped median absolute error of **5.01 BIS units**, and did so while
missing three of BIS's four real ingredients. This experiment adds those three -- relative beta ratio,
QUAZI and SyncFastSlow -- and asks whether they buy anything.

=========================================================================================================
DESIGN
=========================================================================================================
DATA. `vitaldb_bis.csv` (the four subparameters) joined to `vitaldb_grid.csv` (every other feature, plus
the device's own BIS/SQI/SR/EMG) on `recording_id`, which encodes caseid and window start time. The join
was verified at 100.0 % overlap before extraction began.

INCLUSION, fixed here: device BIS present, `meta_sensor_off` false. Nothing is filtered on any value of any
of the four new columns -- that would select the stratum on the thing being tested (rule 32).

FOLDS. Case-grouped 5-fold. Windows inside one case are highly correlated; ungrouped folds would put the
same case on both sides and inflate every number below.

ARMS. All fitted by ridge on standardised features, standardisation computed on training rows only.

  A  OURS          every EEG feature this repo computed before today. The 5.01 baseline.
  B  SUBPARAMS     the four BIS subparameters alone.
  C  OURS+SUBPARAMS  A + B. **The primary comparison is C against A.**
  D  DEVICE        `meta_sr` + `meta_emg`, the monitor's own reported subparameters. A reference point,
                   not a computable index -- it needs the monitor it is trying to replace.
  E  C+DEVICE      an upper bound on what this window of data supports at all.

GATES, IN ORDER. A gate that fails stops the verdict; it does not soften it.

  M1 JOIN INTEGRITY   `meta_bis` must agree EXACTLY between the two tables on every joined row. Both read
                      it from the same source, so any disagreement means the join is wrong, not that the
                      monitor is noisy. Also requires >= 90 % of grid analysis windows to be joined.
  M2 CAPABILITY       each of the four new columns must be finite on >= 50 % of analysis windows AND have
                      non-zero variance. **`bis_bsr` is expected to fail the variance half of this in
                      maintenance windows** -- burst suppression is a deep-anaesthesia phenomenon and this
                      deposit is maintenance only (device BIS IQR 36.1-49.6). A column that is constant
                      here CANNOT contribute and is reported as unusable rather than quietly carried; that
                      is rule 32, and the whole reason this gate is written before the run.
  P1 PLACEBO          the four subparameter columns permuted ACROSS WINDOWS WITHIN EACH CASE, arm C
                      refitted. This destroys window-level alignment while preserving each case's marginal
                      distribution and every between-case difference, so it isolates the part of any
                      improvement that comes from the subparameters tracking the monitor MOMENT TO MOMENT
                      rather than from four extra columns of case-level information. **If the placebo
                      reaches the real improvement, the verdict is NOT INFORMATIVE, not a pass** (rule 34).

PRIMARY STATISTIC. Change in median absolute error, arm C minus arm A, with an OUT-OF-BAG case-clustered
bootstrap: each draw refits BOTH arms on the drawn cases and scores both on the cases not drawn
(`oob_regression_increment`; rule 9 -- bootstrapping fixed out-of-fold predictions would ignore refit
variance and give an interval that is too narrow). **NEGATIVE means C is better.**

VERDICT RULE, wrong direction enumerated first.

  (a) WORSE          -- the increment CI lies entirely ABOVE zero. The subparameters make fidelity worse,
                        which for a superset model means the extra columns are noise the ridge cannot
                        shrink away, and the reimplementation should be built from arm A alone.
  (b) NO GAIN        -- the CI includes zero. The three missing ingredients buy nothing measurable here.
                        This is a real possibility and not a failure of the experiment: it would mean the
                        information BIS's bispectral machinery extracts is already present in the spectral
                        features, which is worth knowing on its own (rule 28).
  (c) NOT INFORMATIVE-- the placebo's improvement reaches the real one.
  (d) GAIN           -- the CI lies entirely BELOW zero and the placebo does not reach it.

FIDELITY IS REPORTED PER BIS RANGE, ALWAYS, whatever the verdict. Bands [0,40) [40,60) [60,80) [80,100],
with n per band. This is Q22's third caveat and it is not optional: a depth monitor's disagreements matter
most at the extremes, and the pooled median hides them.

**RANGE-SPECIFIC MODELS ARE DELIBERATELY NOT FITTED, although Lee et al. fitted them.** The range is
defined by the device BIS, which is the regression target. Choosing which model to apply using the true
value of the target is leakage, and it would make the reported fidelity uninterpretable. Stratifying the
EVALUATION by true BIS is fine and is what happens below; stratifying the FIT is not. A legitimate
range-specific model would have to select the range from a first-pass PREDICTION, and that is a separate
experiment, not a tweak to this one.

WHAT A PASS HERE WOULD AND WOULD NOT LICENCE. It would licence computing the index on deposits with no
monitor, WITH the measured error attached to every use of it. It would NOT licence any claim about
fidelity at BIS < 30 or > 70, because this deposit contains almost none of either; those bands are
reported so the gap is visible, not so it can be filled in.

    python -m bsde.experiments.e58_bis_like_index
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import (grouped_cv_predict, oob_regression_increment)   # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
BIS = os.path.join(RESULTS, "vitaldb_bis.csv")
OUT = os.path.join(RESULTS, "e58_bis_like_index.json")

SUBPARAMS = ["bis_rbr", "bis_bsr", "bis_quazi", "bis_sfs"]
DEVICE = ["meta_sr", "meta_emg"]
BANDS = [(0.0, 40.0), (40.0, 60.0), (60.0, 80.0), (80.0, 100.0)]
SEED = 20260731


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return x


def load():
    with open(GRID, newline="") as fh:
        grid = {r["recording_id"]: r for r in csv.DictReader(fh)}
        gfields = list(csv.DictReader(open(GRID, newline="")).fieldnames or [])
    with open(BIS, newline="") as fh:
        sub = {r["recording_id"]: r for r in csv.DictReader(fh)}
    return grid, sub, gfields


def main() -> int:
    for p in (GRID, BIS):
        if not os.path.exists(p):
            print(f"MISSING {p}")
            return 2
    grid, sub, gfields = load()
    rng = np.random.default_rng(SEED)

    # ---- the feature set that existed before today: every non-meta column that is not a key or a subparam
    keys = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
    ours = [c for c in gfields if c not in keys and not c.startswith("meta_") and c not in SUBPARAMS]

    # ---- inclusion, applied to the GRID first so the join rate is measured against the intended cohort
    def usable(r):
        if r.get("status") != "ok":
            return False
        if str(r.get("meta_sensor_off", "")).strip().lower() in ("true", "1"):
            return False
        return np.isfinite(_f(r.get("meta_bis")))

    grid_ok = [rid for rid, r in grid.items() if usable(r)]
    joined = [rid for rid in grid_ok if rid in sub and sub[rid].get("status") == "ok"]
    join_rate = len(joined) / max(1, len(grid_ok))

    # M1 join integrity: the two tables read meta_bis from the same source, so it must match exactly.
    mism = [rid for rid in joined
            if abs(_f(grid[rid]["meta_bis"]) - _f(sub[rid].get("meta_bis", "nan"))) > 1e-9]
    m1 = (len(mism) == 0) and (join_rate >= 0.90)

    rid_list = sorted(joined)
    y = np.array([_f(grid[r]["meta_bis"]) for r in rid_list], float)
    case = np.array([grid[r].get("meta_caseid", grid[r].get("subject", "")) for r in rid_list])
    Xours = np.array([[_f(grid[r][c]) for c in ours] for r in rid_list], float)
    Xsub = np.array([[_f(sub[r][c]) for c in SUBPARAMS] for r in rid_list], float)
    Xdev = np.array([[_f(grid[r][c]) for c in DEVICE] for r in rid_list], float)

    # M2 capability, per subparameter. Reported whatever it says.
    cap = {}
    for j, name in enumerate(SUBPARAMS):
        v = Xsub[:, j]
        fin = np.isfinite(v)
        sd = float(np.std(v[fin])) if fin.any() else float("nan")
        cap[name] = {"finite_fraction": float(fin.mean()), "sd": sd,
                     "usable": bool(fin.mean() >= 0.50 and np.isfinite(sd) and sd > 1e-9)}
    m2_all = all(c["usable"] for c in cap.values())
    usable_sub = [j for j, n in enumerate(SUBPARAMS) if cap[n]["usable"]]

    print(f"n windows joined  : {len(rid_list)}  ({len(np.unique(case))} cases), "
          f"join rate {100 * join_rate:.1f}%")
    print(f"device BIS        : median {np.median(y):.1f}  IQR "
          f"{np.quantile(y, .25):.1f}-{np.quantile(y, .75):.1f}")
    print(f"M1 join integrity : {'PASS' if m1 else 'FAIL'}  ({len(mism)} meta_bis mismatches)")
    for n, c in cap.items():
        print(f"   M2 {n:<10s} finite {100 * c['finite_fraction']:5.1f}%  sd {c['sd']:.4g}  "
              f"{'usable' if c['usable'] else 'UNUSABLE'}")

    if not m1:
        print("\nM1 FAILED -- the join is wrong. No fidelity number from this table means anything.")
        json.dump({"gate_m1": False, "n_mismatch": len(mism), "join_rate": join_rate},
                  open(OUT, "w"), indent=2)
        return 1

    Xsub_use = Xsub[:, usable_sub] if usable_sub else np.zeros((len(y), 0))

    arms = {
        "A_ours": Xours,
        "B_subparams": Xsub_use,
        "C_ours_plus_subparams": np.column_stack([Xours, Xsub_use]) if usable_sub else Xours,
        "D_device": Xdev,
        "E_all": np.column_stack([Xours, Xsub_use, Xdev]) if usable_sub
        else np.column_stack([Xours, Xdev]),
    }

    def err_table(pred):
        ok = np.isfinite(pred) & np.isfinite(y)
        e = np.abs(y[ok] - pred[ok])
        ss = float(np.sum((y[ok] - pred[ok]) ** 2))
        st = float(np.sum((y[ok] - y[ok].mean()) ** 2))
        out = {"n": int(ok.sum()), "median_abs_err": float(np.median(e)),
               "mean_abs_err": float(e.mean()), "r2": float(1 - ss / st) if st > 0 else float("nan")}
        out["by_band"] = []
        for lo, hi in BANDS:
            m = ok & (y >= lo) & (y < hi if hi < 100 else y <= hi)
            eb = np.abs(y[m] - pred[m])
            out["by_band"].append({"band": f"[{lo:.0f},{hi:.0f})", "n": int(m.sum()),
                                   "median_abs_err": float(np.median(eb)) if m.sum() else float("nan"),
                                   "mean_abs_err": float(eb.mean()) if m.sum() else float("nan")})
        return out

    res = {}
    print(f"\n{'arm':<24s} {'n':>6s} {'median|err|':>12s} {'mean|err|':>10s} {'R2':>8s}")
    for name, X in arms.items():
        pred = grouped_cv_predict(X, y, case, np.random.default_rng(SEED))
        res[name] = err_table(pred)
        r = res[name]
        print(f"{name:<24s} {r['n']:>6d} {r['median_abs_err']:>12.2f} "
              f"{r['mean_abs_err']:>10.2f} {r['r2']:>8.3f}")

    print(f"\nfidelity per DEVICE BIS band (arm C), evaluation-stratified only, never fit-stratified")
    print(f"{'band':<12s} {'n':>6s} {'median|err|':>12s} {'mean|err|':>10s}")
    for b in res["C_ours_plus_subparams"]["by_band"]:
        print(f"{b['band']:<12s} {b['n']:>6d} {b['median_abs_err']:>12.2f} {b['mean_abs_err']:>10.2f}")

    # ---- PRIMARY: out-of-bag increment, C minus A. Negative = better.
    mean_d, lo_d, hi_d, nrep = oob_regression_increment(
        arms["A_ours"], arms["C_ours_plus_subparams"], y, case, np.random.default_rng(SEED + 1))
    print(f"\nPRIMARY  median|err| increment C-A = {mean_d:+.3f} BIS units "
          f"[{lo_d:+.3f}, {hi_d:+.3f}]  ({nrep} oob reps; negative = C better)")

    # ---- P1 PLACEBO: permute the subparameter block WITHIN case, refit C, same increment.
    rp = np.random.default_rng(SEED + 2)
    Xsub_perm = Xsub_use.copy()
    for u in np.unique(case):
        m = np.flatnonzero(case == u)
        Xsub_perm[m] = Xsub_use[rp.permutation(m)]
    Cperm = np.column_stack([Xours, Xsub_perm]) if usable_sub else Xours
    mean_p, lo_p, hi_p, nrep_p = oob_regression_increment(
        arms["A_ours"], Cperm, y, case, np.random.default_rng(SEED + 1))
    print(f"PLACEBO  same increment, subparams shuffled within case = {mean_p:+.3f} "
          f"[{lo_p:+.3f}, {hi_p:+.3f}]  ({nrep_p} reps)")

    # ---- verdict, wrong direction first
    if not np.isfinite(lo_d):
        verdict = "NOT INFORMATIVE -- the out-of-bag bootstrap did not produce enough usable draws."
    elif lo_d > 0:
        verdict = ("WORSE -- the four subparameters make fidelity worse. For a superset model that means "
                   "they are noise the ridge cannot shrink away; build the index from arm A alone.")
    elif hi_d >= 0:
        verdict = ("NO GAIN -- the increment CI includes zero. The three ingredients BIS has and this repo "
                   "did not buy nothing measurable here, which says the information is already present in "
                   "the spectral features (rule 28).")
    elif np.isfinite(mean_p) and mean_p <= mean_d:
        verdict = ("NOT INFORMATIVE -- the within-case placebo matches or beats the real improvement, so "
                   "the gain is extra columns rather than moment-to-moment tracking.")
    else:
        verdict = ("GAIN -- adding the four subparameters improves out-of-bag fidelity, and a within-case "
                   "shuffle of the same columns does not. Fidelity per BIS band above is the number that "
                   "must ride with every downstream use; it is NOT uniform and the extremes are thin.")
    print(f"\nVERDICT: {verdict}")
    if not m2_all:
        print("NOTE: gate M2 marked "
              f"{[n for n in SUBPARAMS if not cap[n]['usable']]} unusable in this cohort; they were "
              "dropped from every arm. That is a property of maintenance-only windows, not of the "
              "measures (rule 32).")

    json.dump({"gate_m1": True, "join_rate": join_rate, "n_windows": len(rid_list),
               "n_cases": int(len(np.unique(case))), "capability": cap, "gate_m2_all": m2_all,
               "arms": res, "n_ours_features": len(ours), "ours_features": ours,
               "primary_increment_C_minus_A": {"mean": mean_d, "lo": lo_d, "hi": hi_d, "reps": nrep},
               "placebo_within_case": {"mean": mean_p, "lo": lo_p, "hi": hi_p, "reps": nrep_p},
               "verdict": verdict}, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
