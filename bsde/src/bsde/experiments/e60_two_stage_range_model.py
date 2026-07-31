#!/usr/bin/env python3
"""E60 -- Q22. Does a range-specific fit, selected from a PREDICTION, beat one global fit?

REGISTERED BEFORE ANY TWO-STAGE MODEL HAS BEEN FITTED. Everything read from `vitaldb_grid.csv` /
`vitaldb_bis.csv` at the time of writing is E58's output, which is committed: the one-stage arm fidelities
and the per-band table. No two-stage prediction exists.

=========================================================================================================
WHY, AND WHY THE TARGET BAND MOVED TWICE -- STATED SO IT IS NOT A QUIET DRIFT
=========================================================================================================
Lee et al. (PMID 31551487) fit RANGE-SPECIFIC models because one linear relationship does not hold across
anaesthetic depth. E58 deliberately refused to, because its ranges are defined by the device BIS, which is
the regression target: **choosing which model to apply using the true value of the target is leakage.** The
legitimate version selects the range from a first-pass PREDICTION, and that is what this file does.

Q22 left this open aimed at the **[80,100)** failure, where E58's median absolute error is 29.84.
`docs/BIS_FAITHFUL_OR_BRAIN_FAITHFUL.md` then redirected it to **[60,80)** at most, because 98.2 % of the
[80,100) windows are facial-EMG artefact and any fit that improves agreement there is fitting muscle.
**This file redirects once more, to [0,40), and the reason is the same principle applied one step further.**
[60,80) is itself 35.0 % above E46's artefact threshold, and the decision document's own rule is to fit only
where the reference is measuring brain. Applying that rule leaves two clean bands -- [40,60) at 4.6 %
contamination and [0,40) at 5.6 % -- and of those, **[0,40) is where the one global fit does worst**
(median |err| 5.48 against 3.47), on 2,330 windows. It is also where a separate relationship is expected
physiologically rather than merely hoped for: burst suppression exists in that band and nowhere else.

**Two redirections is one more than is comfortable, so the falsification condition is fixed to the band
named here and nowhere else.** A gain appearing in some other band is not this experiment's result.

=========================================================================================================
DESIGN
=========================================================================================================
STAGE 1 is E58's arm C (every feature this repo computes, plus the four BIS subparameters), fitted by ridge
with case-grouped folds.

STAGE 2 partitions rows by the band their STAGE-1 PREDICTION falls in -- never by their true BIS -- and
fits one ridge per band. Training rows get their stage-1 predictions from an INNER case-grouped CV inside
the training set, so a row's band assignment never comes from a model that saw it.

BANDS for the sub-models: [0,40), [40,60), [60,100]. The top two are merged because E58 found 468 and 168
windows there; splitting them further would fit noise. A band with fewer than `MIN_BAND_TRAIN` training rows
falls back to the stage-1 model, and how often that happens is reported.

  M1 SEPARATION GATE  the predicted-band assignment must be non-trivial: every band must receive at least
                      `MIN_BAND_FRAC` of rows. **If nearly everything lands in one band the two-stage model
                      IS the one-stage model**, and any difference between them is refit noise rather than
                      range specificity. This is the gate that stops a null being read as a result.

  PRIMARY             change in median absolute error **evaluated on rows whose TRUE BIS lies in [0,40)**,
                      two-stage minus one-stage, out-of-bag with cases resampled and both models refitted
                      per draw (rule 9). **NEGATIVE means the two-stage model is better.**
                      The evaluation rows are selected by true BIS, which is legitimate BECAUSE BOTH ARMS
                      ARE SCORED ON THE SAME ROWS -- the selection cannot advantage either (rule 49: before
                      running a comparison, ask what the selection rule forces; here it forces nothing,
                      because it is applied identically to both sides and neither model sees it).
                      Pooled median error is NOT the primary: it is dominated by the 2,879 target-band rows
                      where the global fit already does well, and would be insensitive to exactly the
                      mis-specification this experiment exists to find (rule 51, which E58 paid for).

  P1 PLACEBO          stage 2 refitted on a RANDOM partition of the same sizes instead of the predicted
                      band. Same number of sub-models, same parameter count, no range information. **If the
                      random partition gains as much, the effect is extra parameters, not range
                      specificity** -- a comparison against the real effect, never a threshold (rule 34),
                      and NOT INFORMATIVE if the primary itself spans zero (rule 48).

VERDICT RULE -- wrong direction first.

  (a) WORSE           -- the increment CI lies entirely ABOVE zero. Range-specific fitting hurts in the
                         band it was aimed at; the global fit is the right model and Lee's range-specific
                         structure does not transfer to this feature set.
  (b) NO GAIN         -- the CI includes zero.
  (c) NOT INFORMATIVE -- the primary spans zero (so there is nothing for the placebo to be compared
                         against), or the random partition matches the real one.
  (d) GAIN            -- the CI lies entirely below zero and the random partition does not match it.

WHAT A GAIN WOULD LICENCE: a two-stage index reported in [0,40) with the measured error, under the same
refusal above BIS 60 that `BIS_FAITHFUL_OR_BRAIN_FAITHFUL.md` fixes. It would NOT reopen the top of the
scale, and no result here bears on it.

    python -m bsde.experiments.e60_two_stage_range_model
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import _standardise, grouped_cv_predict, ridge_fit    # noqa: E402
from bsde.experiments.e58_bis_like_index import SUBPARAMS, _f, load            # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e60_two_stage_range_model.json")

SUB_BANDS = [(0.0, 40.0), (40.0, 60.0), (60.0, 1e9)]
TARGET_BAND = (0.0, 40.0)          # the band the primary is evaluated on; fixed here, not chosen later
MIN_BAND_FRAC = 0.05
MIN_BAND_TRAIN = 200
FOLDS = 5
REPS = 400
MIN_OOB_CASES = 5
SEED = 20260731


def _band_of(v):
    for k, (lo, hi) in enumerate(SUB_BANDS):
        if lo <= v < hi:
            return k
    return len(SUB_BANDS) - 1


def _fit_predict_one_stage(Xtr, ytr, Xte):
    Ztr, Zte = _standardise(Xtr, Xte)
    return Zte @ ridge_fit(Ztr, ytr, 1.0)


def two_stage_predict(X, y, case, rng, assign=None):
    """Out-of-fold two-stage predictions with cases held out whole.

    `assign` overrides the band assignment with a caller-supplied per-row integer, which is how the placebo
    substitutes a random partition of the same sizes while changing nothing else.
    """
    X, y, case = np.asarray(X, float), np.asarray(y, float), np.asarray(case)
    uniq = np.unique(case)
    order = rng.permutation(len(uniq))
    fold = {uniq[order[i]]: i % FOLDS for i in range(len(uniq))}
    fold_of = np.array([fold[c] for c in case])
    pred = np.full(len(y), np.nan)
    n_fallback = 0
    for k in range(FOLDS):
        te, tr = np.flatnonzero(fold_of == k), np.flatnonzero(fold_of != k)
        if te.size == 0 or tr.size < X.shape[1] + 2:
            continue
        # stage 1: honest band for TEST rows, and for TRAIN rows via an inner grouped CV
        p_te = _fit_predict_one_stage(X[tr], y[tr], X[te])
        p_tr = grouped_cv_predict(X[tr], y[tr], case[tr], np.random.default_rng(SEED + 17 + k),
                                  folds=FOLDS)
        if assign is None:
            b_tr = np.array([_band_of(v) if np.isfinite(v) else 1 for v in p_tr])
            b_te = np.array([_band_of(v) if np.isfinite(v) else 1 for v in p_te])
        else:
            b_tr, b_te = assign[tr], assign[te]
        for b in range(len(SUB_BANDS)):
            sel_te = te[b_te == b]
            sel_tr = tr[b_tr == b]
            if sel_te.size == 0:
                continue
            if sel_tr.size < MIN_BAND_TRAIN:
                pred[sel_te] = p_te[b_te == b]      # fall back to stage 1
                n_fallback += int(sel_te.size)
                continue
            pred[sel_te] = _fit_predict_one_stage(X[sel_tr], y[sel_tr], X[sel_te])
    return pred, n_fallback


def _med_err(y, p, m):
    ok = m & np.isfinite(p) & np.isfinite(y)
    return float(np.median(np.abs(y[ok] - p[ok]))) if ok.sum() else float("nan")


def oob_two_stage_increment(X, y, case, rng, target, assign=None, reps=REPS):
    """Cases resampled; BOTH models refitted per draw and scored on the cases NOT drawn (rule 9)."""
    uniq = np.unique(case)
    idx = {u: np.flatnonzero(case == u) for u in uniq}
    diffs = []
    for _ in range(reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        oob = [u for u in uniq if u not in set(drawn.tolist())]
        if len(oob) < MIN_OOB_CASES:
            continue
        tr = np.concatenate([idx[u] for u in drawn])
        te = np.concatenate([idx[u] for u in oob])
        m = target[te]
        if m.sum() < 30:
            continue
        try:
            p1 = _fit_predict_one_stage(X[tr], y[tr], X[te])
            if assign is None:
                p1_tr = grouped_cv_predict(X[tr], y[tr], case[tr], rng, folds=FOLDS)
                b_tr = np.array([_band_of(v) if np.isfinite(v) else 1 for v in p1_tr])
                b_te = np.array([_band_of(v) if np.isfinite(v) else 1 for v in p1])
            else:
                b_tr, b_te = assign[tr], assign[te]
            p2 = p1.copy()
            for b in range(len(SUB_BANDS)):
                s_te, s_tr = np.flatnonzero(b_te == b), tr[b_tr == b]
                if s_te.size and s_tr.size >= MIN_BAND_TRAIN:
                    p2[s_te] = _fit_predict_one_stage(X[s_tr], y[tr][b_tr == b], X[te][s_te])
            e1 = _med_err(y[te], p1, m)
            e2 = _med_err(y[te], p2, m)
        except Exception:                                              # noqa: BLE001
            continue
        if np.isfinite(e1) and np.isfinite(e2):
            diffs.append(e2 - e1)
    if len(diffs) < 30:
        return float("nan"), float("nan"), float("nan"), len(diffs)
    d = np.asarray(diffs, float)
    return float(d.mean()), float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975)), len(d)


def main() -> int:
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
    X = np.column_stack([np.array([[_f(grid[r][c]) for c in ours] for r in rid], float),
                         np.array([[_f(sub[r][c]) for c in SUBPARAMS] for r in rid], float)])
    target = (y >= TARGET_BAND[0]) & (y < TARGET_BAND[1])
    print(f"{len(y)} windows, {len(np.unique(case))} cases; "
          f"target band [{TARGET_BAND[0]:.0f},{TARGET_BAND[1]:.0f}) holds {int(target.sum())}")

    rng = np.random.default_rng(SEED)
    p1 = grouped_cv_predict(X, y, case, np.random.default_rng(SEED))
    p2, n_fb = two_stage_predict(X, y, case, np.random.default_rng(SEED))

    b_all = np.array([_band_of(v) if np.isfinite(v) else 1 for v in p1])
    frac = np.array([float((b_all == b).mean()) for b in range(len(SUB_BANDS))])
    m1 = bool((frac >= MIN_BAND_FRAC).all())
    print("M1 separation  predicted-band shares: "
          + "  ".join(f"[{lo:.0f},{min(hi, 100):.0f}) {f:.3f}" for (lo, hi), f in zip(SUB_BANDS, frac))
          + f"   {'PASS' if m1 else 'FAIL'} (need every band >= {MIN_BAND_FRAC})")
    print(f"   stage-2 fell back to stage 1 on {n_fb} of {len(y)} rows "
          f"({100 * n_fb / len(y):.1f}%) for want of {MIN_BAND_TRAIN} training rows")

    if not m1:
        print("\nM1 FAILED -- the assignment is degenerate, so the two-stage model IS the one-stage model "
              "and any difference is refit noise. Verdict ABSENT (rule 31).")
        json.dump({"gate_m1": False, "band_shares": frac.tolist()}, open(OUT, "w"), indent=2)
        return 1

    print(f"\n{'':<14s} {'target band':>12s} {'pooled':>10s}")
    for lab, p in (("one-stage", p1), ("two-stage", p2)):
        print(f"{lab:<14s} {_med_err(y, p, target):>12.3f} "
              f"{_med_err(y, p, np.ones(len(y), bool)):>10.3f}")

    mean_d, lo_d, hi_d, nrep = oob_two_stage_increment(
        X, y, case, np.random.default_rng(SEED + 1), target)
    print(f"\nPRIMARY  median|err| on [{TARGET_BAND[0]:.0f},{TARGET_BAND[1]:.0f}), two-stage minus "
          f"one-stage = {mean_d:+.3f} [{lo_d:+.3f}, {hi_d:+.3f}]  ({nrep} oob reps; negative = better)")

    # P1 placebo: same partition SIZES, no range information.
    rp = np.random.default_rng(SEED + 2)
    sizes = [int((b_all == b).sum()) for b in range(len(SUB_BANDS))]
    lab = np.concatenate([np.full(n, b) for b, n in enumerate(sizes)])
    rp.shuffle(lab)
    mean_p, lo_p, hi_p, nrep_p = oob_two_stage_increment(
        X, y, case, np.random.default_rng(SEED + 1), target, assign=lab)
    print(f"PLACEBO  same sub-model sizes, RANDOM partition        = {mean_p:+.3f} "
          f"[{lo_p:+.3f}, {hi_p:+.3f}]  ({nrep_p} reps)")

    if not np.isfinite(lo_d):
        verdict = "ABSENT -- too few usable out-of-bag draws to form an interval."
    elif lo_d > 0:
        verdict = ("WORSE -- range-specific fitting hurts in the band it was aimed at. The global fit is "
                   "the right model here and Lee's range-specific structure does not transfer to this "
                   "feature set.")
    elif hi_d >= 0:
        verdict = ("NO GAIN -- the increment CI includes zero. Selecting a sub-model from a first-pass "
                   "prediction buys nothing in the deep clean band, so one global relationship is "
                   "adequate over the range this deposit actually covers.")
    elif np.isfinite(mean_p) and mean_p <= mean_d:
        verdict = ("NOT INFORMATIVE -- a RANDOM partition of the same sizes gains as much, so the effect "
                   "is extra parameters rather than range specificity.")
    else:
        verdict = ("GAIN -- a sub-model selected from a first-pass prediction beats one global fit in "
                   "[0,40), and a random partition of the same sizes does not. This does NOT reopen the "
                   "top of the scale; the refusal above BIS 60 stands on separate evidence.")
    print(f"\nVERDICT: {verdict}")

    json.dump({"gate_m1": True, "band_shares": frac.tolist(), "n_windows": len(y),
               "n_cases": int(len(np.unique(case))), "n_target": int(target.sum()),
               "n_fallback_rows": n_fb,
               "one_stage": {"target": _med_err(y, p1, target),
                             "pooled": _med_err(y, p1, np.ones(len(y), bool))},
               "two_stage": {"target": _med_err(y, p2, target),
                             "pooled": _med_err(y, p2, np.ones(len(y), bool))},
               "primary_increment": {"mean": mean_d, "lo": lo_d, "hi": hi_d, "reps": nrep},
               "placebo_random_partition": {"mean": mean_p, "lo": lo_p, "hi": hi_p, "reps": nrep_p},
               "verdict": verdict}, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
