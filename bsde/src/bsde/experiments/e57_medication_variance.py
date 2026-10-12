#!/usr/bin/env python3
"""E57 -- do MEDICATION and COMORBIDITY explain more EEG variance than age and sex?

This is the one test that could justify the full HEEDB reference build, and it was specified in
`bsde/docs/REFERENCE_VALUE_MEASURED.md` before the data existed:

> "Do not commission the full reference build on the general argument -- it has been measured and it is
>  worth single-digit percent. Test the medication/comorbidity hypothesis first."

E54 measured age + sex on 745 open-cohort adults: the best R^2 was 0.147 (`exponent_low_robust`, gain
1.083) and Challenge B's own marker gained 1.000. Every deposit available there carried ONLY age and sex.
`NORMAL_REFERENCE_COVARIATES.md` §2 argues the covariates that matter are medication and comorbidity --
88.9 % of this cohort carries nervous-system drugs, and **no existing normative database corrects for
medication at all**. If those blocks explain substantially more, the arithmetic changes.

=========================================================================================================
THE GATE THAT RUNS FIRST, AND CAN KILL THE ANALYSIS
=========================================================================================================
The extraction searches for a usable 180 s window because HEEDB routine recordings contain long
disconnected stretches, and it emits `window_start_s` -- how far in a usable window was found -- plus a
count of recordings where none was. **Sicker, more heavily medicated patients plausibly have more
artefact.** If artefact burden correlates with the medication or comorbidity blocks, then those blocks
partly index DATA QUALITY rather than brain state, and any R^2 advantage they show is an artefact running
in exactly the direction of the hypothesis.

  G1 CONFOUND GATE. Regress `window_start_s` on each covariate block. If medication or comorbidity
  predicts it with an out-of-fold R^2 above `MAX_ARTEFACT_R2`, the primary is reported as CONFOUNDED and
  the comparison is not interpretable as brain state.

This gate is written before the numbers and is the reason `window_start_s` was emitted at all.

=========================================================================================================
PRIMARY
=========================================================================================================
OUT-OF-FOLD (5-fold cross-validated) R^2 for each covariate block, per measure. **Cross-validated, not
in-sample**: 35 predictors against a few hundred rows would inflate an ordinary R^2 by construction, and
the whole question is whether these covariates GENERALISE. A cross-validated R^2 can be negative, which is
informative -- it means the block predicts worse than the sample mean.

  blocks   AGE_SEX      age, age^2, sex                       (3 predictors, E54's comparator)
           MEDICATION   14 ATC level-1 chapters                (14)
           COMORBIDITY  18 ICD-10 chapters                     (18)
           ALL          the union                              (35)

VERDICT RULE, with the failing case first (rules 37, 49):

  (a) CONFOUNDED         -- G1 fires. No comparison is reported.
  (b) HYPOTHESIS REFUTED -- medication and comorbidity each score at or below AGE_SEX. The covariates
      NORMAL_REFERENCE_COVARIATES §2 nominated do not explain more, the general argument has already been
      measured as small, and **the full reference build is not justified by any evidence now available.**
  (c) HYPOTHESIS SUPPORTED -- either block beats AGE_SEX by a margin whose bootstrap interval excludes
      zero, and the implied gain 1/sqrt(1-R^2) is materially above E54's 1.083.

WHAT THIS CANNOT SHOW. The medication table is per PATIENT and per ATC CHAPTER -- "ever prescribed"
rather than "on board during this recording", pooling a benzodiazepine with a paracetamol. That is a blunt
instrument and it biases toward the NULL, so a positive result is more trustworthy than a negative one.
And the 180 s window is not vigilance-controlled: 94.8 % of these recordings contain sleep and Q21 showed
the metadata cannot locate it, so residual variance is inflated for every block alike. Blocks are
comparable to each other; the absolute R^2 values are floors.

    python -m bsde.experiments.e57_medication_variance
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

SAMPLE = "/tmp/eeg_probe/heedb_reference_sample.csv"
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e57_medication_variance.json")

MEASURES = ("exponent_low", "exponent_low_robust", "whole_head_exponent", "exponent_high",
            "lempel_ziv", "lrtc_alpha", "rel_alpha", "alpha_peak_hz", "sef95")
MAX_ARTEFACT_R2 = 0.05
MIN_ROWS = 150
FOLDS = 5
REPS = 4000
SEED = 20260731


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:                                                        # noqa: BLE001
        return None


def _blocks(rows):
    age = np.array([_f(r["age"]) or 0.0 for r in rows])
    sex = np.array([1.0 if (r["sex"] or "").upper().startswith("M") else 0.0 for r in rows])
    atc = sorted({c for r in rows for c in r if c.startswith("atc_")})
    icd = sorted({c for r in rows for c in r if c.startswith("icd_")})
    A = np.vstack([age, age ** 2, sex]).T
    M = np.vstack([[_f(r.get(c)) or 0.0 for r in rows] for c in atc]).T if atc else np.zeros((len(rows), 0))
    C = np.vstack([[_f(r.get(c)) or 0.0 for r in rows] for c in icd]).T if icd else np.zeros((len(rows), 0))
    return {"AGE_SEX": A, "MEDICATION": M, "COMORBIDITY": C,
            "ALL": np.hstack([A, M, C])}, atc, icd


def _oof_r2(X, y, rng, folds=FOLDS):
    """Out-of-fold R^2. Negative means the block predicts worse than the sample mean."""
    n = len(y)
    if X.shape[1] == 0 or n < 40:
        return float("nan")
    order = rng.permutation(n)
    fold = np.empty(n, int)
    fold[order] = np.arange(n) % folds
    pred = np.full(n, np.nan)
    for k in range(folds):
        te, tr = fold == k, fold != k
        if tr.sum() < X.shape[1] + 5 or te.sum() == 0:
            continue
        Xtr = np.column_stack([np.ones(int(tr.sum())), X[tr]])
        Xte = np.column_stack([np.ones(int(te.sum())), X[te]])
        try:
            beta, *_ = np.linalg.lstsq(Xtr, y[tr], rcond=None)
        except Exception:                                                    # noqa: BLE001
            continue
        pred[te] = Xte @ beta
    ok = np.isfinite(pred)
    if ok.sum() < 30:
        return float("nan")
    ss_res = float(((y[ok] - pred[ok]) ** 2).sum())
    ss_tot = float(((y[ok] - y[ok].mean()) ** 2).sum())
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def main() -> int:
    if not os.path.exists(SAMPLE):
        print(f"{SAMPLE} absent -- extraction has not started."); return 1
    with open(SAMPLE) as fh:
        rows = list(csv.DictReader(fh))
    print("=" * 100)
    print("E57 -- do medication and comorbidity explain more EEG variance than age and sex?")
    print("=" * 100)
    print(f"   rows: {len(rows)}")
    if len(rows) < MIN_ROWS:
        print(f"   G0 FAILED: {len(rows)} < {MIN_ROWS}. No verdict."); return 1
    blocks, atc, icd = _blocks(rows)
    print(f"   blocks: AGE_SEX {blocks['AGE_SEX'].shape[1]}, MEDICATION {len(atc)}, "
          f"COMORBIDITY {len(icd)}, ALL {blocks['ALL'].shape[1]}")
    rng = np.random.default_rng(SEED)

    # ---------------------------------------------------------------- G1 confound gate
    win = np.array([_f(r.get("window_start_s")) or 0.0 for r in rows])
    print(f"\n   G1 CONFOUND GATE -- does artefact burden (window_start_s) track the covariates?")
    print(f"      window_start_s: median {np.median(win):.0f}s, "
          f"{100*np.mean(win > 300):.0f}% needed a later window than the first offset")
    g1 = {}
    for name in ("AGE_SEX", "MEDICATION", "COMORBIDITY"):
        v = _oof_r2(blocks[name], win, np.random.default_rng(SEED))
        g1[name] = v
        flag = "OK" if not (math.isfinite(v) and v > MAX_ARTEFACT_R2) else "FIRES"
        print(f"      {name:14s} oof R2 on window_start_s = {v:+.4f}   {flag}")
    confounded = any(math.isfinite(v) and v > MAX_ARTEFACT_R2
                     for k, v in g1.items() if k in ("MEDICATION", "COMORBIDITY"))

    # ---------------------------------------------------------------- primary
    print(f"\n   {'measure':22s} {'AGE_SEX':>10s} {'MEDICATION':>12s} {'COMORBID':>10s} {'ALL':>9s}"
          f"   {'best block':>12s}")
    print("   " + "-" * 84)
    res = {}
    for m in MEASURES:
        y = np.array([_f(r.get(m)) for r in rows], float)
        ok = np.isfinite(y)
        if ok.sum() < MIN_ROWS:
            print(f"   {m:22s} insufficient ({ok.sum()})")
            continue
        yy = y[ok]
        vals = {}
        for name, X in blocks.items():
            vals[name] = _oof_r2(X[ok], yy, np.random.default_rng(SEED))
        best = max((k for k in ("AGE_SEX", "MEDICATION", "COMORBIDITY") if math.isfinite(vals[k])),
                   key=lambda k: vals[k], default="-")
        res[m] = {**vals, "n": int(ok.sum()), "best_block": best}
        print(f"   {m:22s} {vals['AGE_SEX']:+10.4f} {vals['MEDICATION']:+12.4f} "
              f"{vals['COMORBIDITY']:+10.4f} {vals['ALL']:+9.4f}   {best:>12s}")

    # margin of the best non-age block over AGE_SEX, bootstrapped over rows
    print(f"\n   margin of the best of (MEDICATION, COMORBIDITY) over AGE_SEX, row bootstrap:")
    margins = {}
    idx = np.arange(len(rows))
    for m in list(res):
        y = np.array([_f(r.get(m)) for r in rows], float)
        d = []
        r2 = np.random.default_rng(SEED + 11)
        for _ in range(REPS // 4):
            i = r2.choice(idx, idx.size, replace=True)
            sub = [rows[j] for j in i]
            bl, _a, _c = _blocks(sub)
            ys = y[i]
            o = np.isfinite(ys)
            if o.sum() < MIN_ROWS:
                continue
            a = _oof_r2(bl["AGE_SEX"][o], ys[o], np.random.default_rng(SEED))
            mm = max(_oof_r2(bl["MEDICATION"][o], ys[o], np.random.default_rng(SEED)),
                     _oof_r2(bl["COMORBIDITY"][o], ys[o], np.random.default_rng(SEED)))
            if math.isfinite(a) and math.isfinite(mm):
                d.append(mm - a)
        if d:
            d = np.sort(np.array(d))
            lo, hi = float(np.quantile(d, .025)), float(np.quantile(d, .975))
            pt = max(res[m]["MEDICATION"], res[m]["COMORBIDITY"]) - res[m]["AGE_SEX"]
            margins[m] = {"margin": pt, "ci": [lo, hi]}
            print(f"      {m:22s} {pt:+.4f} [{lo:+.4f}, {hi:+.4f}]")

    wins = [m for m, v in margins.items() if math.isfinite(v["ci"][0]) and v["ci"][0] > 0]
    if confounded:
        verdict = ("CONFOUNDED -- artefact burden tracks the medication or comorbidity block, so their "
                   "R^2 partly indexes data quality rather than brain state. No comparison reported.")
    elif not wins:
        verdict = ("HYPOTHESIS REFUTED -- medication and comorbidity do not out-explain age and sex for "
                   "any measure with an interval excluding zero. Combined with REFERENCE_VALUE_MEASURED's "
                   "finding that the general argument is worth single-digit percent, **the full HEEDB "
                   "reference build is not justified by any evidence now available.**")
    else:
        best_gain = max(max(res[m]['MEDICATION'], res[m]['COMORBIDITY']) for m in wins)
        verdict = (f"HYPOTHESIS SUPPORTED for {len(wins)} measure(s): {wins}. Best block R^2 "
                   f"{best_gain:.4f} -> gain {1/math.sqrt(1-best_gain):.3f} against E54's 1.083.")
    print("\n" + "-" * 100)
    print(f"VERDICT: {verdict}")
    os.makedirs(RESULTS, exist_ok=True)
    json.dump({"n_rows": len(rows), "g1_artefact": g1, "confounded": bool(confounded),
               "results": res, "margins": margins, "verdict": verdict,
               "n_atc": len(atc), "n_icd": len(icd), "seed": SEED},
              open(OUT, "w"), indent=2, default=str)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
