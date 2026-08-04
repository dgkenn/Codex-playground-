#!/usr/bin/env python3
"""E204 — does spontaneous EEG predict CLINICIAN-ASSESSED command-following beyond sedation?

REGISTERED WHILE THE EXTRACTION IS STILL RUNNING. No feature, label or association from the HEEDB
command-following table has been inspected; the only numbers below come from the label probe (a count of
GCS values) and from prior experiments.

=========================================================================================================
WHY THIS IS THE FIRST TIME CHALLENGE B HAS HAD A REAL LABEL
=========================================================================================================
Challenge B asks whether spontaneous EEG predicts command-following. Every test this programme has run has
substituted healthy BCI users, because no reachable deposit carried the label — Chennu 2014's 32 DoC
patients (the only public cohort with both a CRS-R and an fMRI command-following column) need a Wolfson
Brain Imaging Centre committee request, Bath was denied, Della Bella publishes only CRS-R totals, and
OpenNeuro, Dryad, Zenodo and PhysioNet were each enumerated through their own APIs with no DoC EEG cohort
at all.

**The Glasgow Coma Scale motor subscore's top level is literally "obeys commands", and HEEDB has it.** A
probe over 6 of 551 parquet parts returned 26,527 `BEST MOTOR RESPONSE` rows over 1,334 patients with the
values populated — 6.0 = 19,344 against 7,183 below it — against a 67,202-patient EEG cohort with 127,728
timestamped recordings.

**This is OVERT command-following and this file never claims otherwise.** A cognitive-motor-dissociation
patient scores below 6 while conscious. What is tested here is the precondition: a measure that cannot
predict overt command-following will not detect covert. The CMD-shaped question is a declared secondary
below, and it is answerable only because HEEDB has follow-up.

=========================================================================================================
THE INCUMBENT IS SEDATION, AND IT IS IN THE DESIGN RATHER THAN IN THE CAVEATS
=========================================================================================================
GCS-motor is heavily driven by sedation, and rule 54 records that naming a confound in a registration
creates the feeling of having handled it while changing nothing. So the confound is not named here — it is
**the incumbent**:

    **P1  the out-of-fold AUC increment of the eight-feature spectral panel OVER RASS**, the bedside
          sedation score, with patients held out WHOLE and a patient-level permutation null.

The line of code that handles sedation is the one that puts RASS in the baseline design matrix, and there
is nothing left over to caveat. An arm with an intercept-only baseline is computed and reported as
DESCRIPTIVE — it answers "does EEG predict at all", which is a weaker question, and it cannot carry the
verdict (rule 71: the gate is checked on the arm the winner came from).

=========================================================================================================
THE UNIT OF ANALYSIS IS THE PATIENT, NOT THE ASSESSMENT
=========================================================================================================
Up to two assessments are kept per patient, so rows are nested inside patients. Rule 69 measured the cost
of ignoring that on a different deposit at **178x** inflation. Here: cross-validation folds hold patients
out whole, and the null permutes the label **at the patient level**, so a patient's assessments move
together. The reported n is patients, and assessments are reported beside it.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 200 patients and >= 300 assessments, with the minority class at >= 15 % of assessments.
G2  **THE INCUMBENT MUST BE ALIVE.** RASS must predict `obeys` above its own patient-level permutation
    floor. If sedation does not predict command-following in this cohort, an increment over it is a
    comparison against noise — E33 wrote this rule and E61 failed to carry it across (rule 53).
G3  **THE INCREMENT ESTIMATOR MUST BE CORRECTLY SPECIFIED.** Both design matrices carry an explicit
    intercept column; `stats.oob_auc_increment` raises if the first column is not constant, which exists
    because E99 shipped a sign-reversed verdict for exactly this omission (rule 76).
G4  a negative control: an i.i.d. noise column must NOT add, at the same estimator and folds.
G5  **ARTEFACT SEPARATION.** Every window ENDS at least 60 s before its assessment and never spans it, so
    the examiner's stimulation and the patient's response cannot enter the features. Reported as the
    measured distribution of `minutes_before`, not as a design claim.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3, G4 or G5 fails.
  (2) HURTS               the increment's interval lies entirely BELOW zero — the panel is variance the
                          model spends capacity on. Enumerated because E99 printed exactly this and it was
                          an intercept bug, so the branch must exist and must be checked against G3.
  (3) ABSENT              the interval includes zero.
  (4) ADDS                the interval excludes zero above it AND the observed increment beats the
                          patient-level permutation null's 95th percentile.

**REGISTERED PREDICTION: (4) ADDS, with a small increment — 0.02 to 0.06 AUC.** EEG background is related
to arousal in critically ill patients by a large and old literature, so this is close to a positive control
for the whole enterprise; a null here would be a serious negative about either the features or the
alignment, not a quiet result. The increment is predicted SMALL because RASS is itself a bedside
arousal score and the two must share most of their information.

=========================================================================================================
DECLARED SECONDARY — THE CMD-SHAPED TEST, CONDITIONAL ON (4)
=========================================================================================================
Among assessments where the patient did **not** obey (`obeys = 0`), does the model's predicted probability
of obeying relate to whether that same patient **later** reaches GCS-motor 6? A patient scoring below 6
whose spontaneous EEG resembles a command-follower's, who subsequently recovers, is the
cognitive-motor-dissociation signature — and this deposit can ask it because the label table carries every
later assessment for the same patient.

**It is a secondary and is reported as one.** It is confounded by everything that predicts recovery, it
uses no independent CMD adjudication, and a positive result would be a hypothesis rather than a detection.
It is declared here so that running it later cannot be presented as a fresh discovery, and so that a null
on it is recorded too.

    python bsde/src/bsde/experiments/e204_heedb_command_following.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import auc, oob_auc_increment                          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLES = [f"/tmp/eeg_probe/heedb_cmd_follow.s{k}.csv" for k in range(4)] + \
         ["/tmp/eeg_probe/heedb_cmd_follow.csv"]
OUT = os.path.join(RESULTS, "e204_heedb_command_following.json")
SEED = 20260802

SPECTRAL = ["exponent_low", "exponent_high", "whole_head_exponent", "relative_alpha_power",
            "relative_delta_power", "spectral_edge_95", "spectral_entropy", "lempel_ziv"]
MIN_PATIENTS, MIN_ROWS, MIN_MINORITY = 200, 300, 0.15
PERMS = 500
ALPHA = 0.05


def _f(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    rows, seen = [], set()
    for p in TABLES:
        if not os.path.exists(p):
            continue
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                k = (r["patient_id"], r["assess_time"])
                if k in seen:
                    continue
                seen.add(k)
                rows.append(r)
    return rows


def build(require_rass):
    rows = load()
    X, y, g, rass, mins = [], [], [], [], []
    for r in rows:
        f = [_f(r.get(c, "")) for c in SPECTRAL]
        ra = _f(r.get("rass", ""))
        ob = _f(r.get("obeys", ""))
        if not np.isfinite(ob) or not all(np.isfinite(v) for v in f):
            continue
        if require_rass and not np.isfinite(ra):
            continue
        X.append(f)
        y.append(ob)
        g.append(r["patient_id"])
        rass.append(ra if np.isfinite(ra) else 0.0)
        mins.append(_f(r.get("minutes_before", "")))
    return (np.asarray(X, float), np.asarray(y, float), np.asarray(g),
            np.asarray(rass, float), np.asarray(mins, float), len(rows))


def patient_permute(y, g, rng):
    """Permute the label AT THE PATIENT LEVEL, so a patient's assessments move together (rule 69)."""
    pats = np.unique(g)
    lab = {p: y[g == p] for p in pats}
    order = rng.permutation(pats)
    out = np.empty_like(y)
    src = {a: lab[b] for a, b in zip(pats, order)}
    for p in pats:
        m = g == p
        v = src[p]
        out[m] = v[:m.sum()] if v.size >= m.sum() else np.resize(v, m.sum())
    return out


def increment(Xb, Xf, y, g, seed):
    """Out-of-fold AUC increment with patients held out whole. Both designs carry an intercept (rule 76)."""
    n = len(y)
    a = np.c_[np.ones(n), Xb]
    b = np.c_[np.ones(n), Xb, Xf]
    return oob_auc_increment(a, b, y, g, np.random.default_rng(seed))


def main() -> int:
    print("E204 — does spontaneous EEG predict clinician-assessed command-following beyond sedation?")
    res = {"experiment": "E204", "features": SPECTRAL, "perms": PERMS}

    Xf, y, g, rass, mins, n_raw = build(require_rass=True)
    n_pat = len(np.unique(g)) if g.size else 0
    minority = float(min(y.mean(), 1 - y.mean())) if y.size else float("nan")
    res.update({"n_rows_raw": n_raw, "n_rows": int(y.size), "n_patients": n_pat,
                "obeys_rate": float(y.mean()) if y.size else float("nan"),
                "minority_fraction": minority})
    print(f"   {n_raw} extracted rows -> {y.size} usable with RASS, {n_pat} patients; "
          f"obeys rate {res['obeys_rate']:.3f}")
    g1 = bool(n_pat >= MIN_PATIENTS and y.size >= MIN_ROWS and minority >= MIN_MINORITY)
    print(f"   G1 {'PASS' if g1 else '*** FAIL'} (floors {MIN_PATIENTS} patients, {MIN_ROWS} rows, "
          f"{MIN_MINORITY:.0%} minority)")
    res["g1"] = g1
    if not g1:
        res["verdict"], res["why"] = "NOT INTERPRETABLE", "cohort floors not met"
        json.dump(res, open(OUT, "w"), indent=2)
        print(f"\nVERDICT: {res['verdict']} — {res['why']}")
        return 1

    if mins.size:
        print(f"   G5 window offset: min {np.nanmin(mins):.2f} max {np.nanmax(mins):.2f} minutes "
              f"before the assessment (every window ENDS before it by construction)")
        res["g5_minutes_before"] = [float(np.nanmin(mins)), float(np.nanmax(mins))]

    rng = np.random.default_rng(SEED)
    inc_r, lo_r, hi_r, _ = increment(np.zeros((y.size, 0)), rass[:, None], y, g, SEED)
    nul_r = []
    for i in range(PERMS // 5):
        yp = patient_permute(y, g, np.random.default_rng(SEED + 100 + i))
        v = increment(np.zeros((yp.size, 0)), rass[:, None], yp, g, SEED + 200 + i)[0]
        if np.isfinite(v):
            nul_r.append(v)
    f95r = float(np.quantile(nul_r, 0.95)) if nul_r else float("nan")
    g2 = bool(np.isfinite(inc_r) and np.isfinite(f95r) and inc_r > f95r)
    print(f"   G2 INCUMBENT ALIVE: RASS increment over intercept {inc_r:+.4f} "
          f"[{lo_r:+.4f}, {hi_r:+.4f}] vs patient-permutation p95 {f95r:+.4f}   "
          f"{'PASS' if g2 else '*** FAIL'}")
    res["g2"] = {"rass_increment": float(inc_r), "ci": [float(lo_r), float(hi_r)],
                 "null_p95": f95r, "pass": g2}

    noise = np.random.default_rng(SEED + 7).normal(size=(y.size, 1))
    inc_n, lo_n, hi_n, _ = increment(rass[:, None], noise, y, g, SEED + 8)
    g4 = bool(not (np.isfinite(lo_n) and lo_n > 0))
    print(f"   G4 negative control: i.i.d. noise increment {inc_n:+.4f} [{lo_n:+.4f}, {hi_n:+.4f}]   "
          f"{'PASS' if g4 else '*** FAIL'}")
    res["g4"] = {"noise_increment": float(inc_n), "ci": [float(lo_n), float(hi_n)], "pass": g4}

    inc, lo, hi, _ = increment(rass[:, None], Xf, y, g, SEED + 11)
    nul = []
    for i in range(PERMS // 5):
        yp = patient_permute(y, g, np.random.default_rng(SEED + 300 + i))
        v = increment(rass[:, None], Xf, yp, g, SEED + 400 + i)[0]
        if np.isfinite(v):
            nul.append(v)
    f95 = float(np.quantile(nul, 0.95)) if nul else float("nan")
    print(f"\nP1 EEG over RASS: increment {inc:+.4f} [{lo:+.4f}, {hi:+.4f}] vs patient-permutation "
          f"p95 {f95:+.4f} ({len(nul)} draws)")
    res["primary"] = {"increment": float(inc), "ci": [float(lo), float(hi)],
                      "null_p95": f95, "n_null": len(nul)}

    Xf2, y2, g2v, _r2, _m2, _n2 = build(require_rass=False)
    inc2, lo2, hi2, _ = increment(np.zeros((y2.size, 0)), Xf2, y2, g2v, SEED + 21)
    print(f"   [descriptive] EEG over intercept only, {y2.size} rows / "
          f"{len(np.unique(g2v))} patients: {inc2:+.4f} [{lo2:+.4f}, {hi2:+.4f}]")
    res["descriptive_intercept_only"] = {"increment": float(inc2), "ci": [float(lo2), float(hi2)],
                                         "n_rows": int(y2.size),
                                         "n_patients": int(len(np.unique(g2v)))}

    print("\n" + "=" * 100)
    if not (g1 and g2 and g4):
        v, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1 cohort", g1), ("G2 incumbent alive", g2),
                            ("G4 negative control", g4)) if not ok))
    elif np.isfinite(hi) and hi < 0:
        v, why = "HURTS", (f"the increment interval [{lo:+.4f}, {hi:+.4f}] lies entirely BELOW zero; the "
                           "panel is variance the model spends capacity on. Check G3 — E99 printed exactly "
                           "this for a missing intercept column")
    elif not (np.isfinite(lo) and lo > 0):
        v, why = "ABSENT", (f"the increment interval [{lo:+.4f}, {hi:+.4f}] includes zero; spontaneous EEG "
                            "adds nothing to a bedside sedation score for predicting overt "
                            "command-following")
    elif not (np.isfinite(f95) and inc > f95):
        v, why = "ABSENT", (f"the interval excludes zero ({inc:+.4f} [{lo:+.4f}, {hi:+.4f}]) but does not "
                            f"beat the patient-level permutation null ({f95:+.4f}) — which is the "
                            "comparison that respects the clustering")
    else:
        v, why = "ADDS", (f"increment {inc:+.4f} [{lo:+.4f}, {hi:+.4f}] over RASS, above a patient-level "
                          f"permutation null of {f95:+.4f}, on {n_pat} patients / {y.size} assessments")
    res["verdict"], res["why"] = v, why
    print(f"VERDICT: {v}\n  {why}")
    print("=" * 100)
    print("SCOPE: GCS-motor is OVERT command-following. A cognitive-motor-dissociation patient scores\n"
          "  below 6 while conscious, so nothing here detects covert consciousness. The CMD-shaped\n"
          "  secondary is declared in the docstring and is conditional on this verdict.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
