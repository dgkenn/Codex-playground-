#!/usr/bin/env python3
"""E52 -- the confirmatory test of E50's registered prediction. Committed BEFORE the data existed.

E50 (exploratory) proposed that E49's sign flips are an artefact of the broadband 1-45 Hz fit rather than
genuine disagreement between studies: on chennu's dose-response the two halves of that band move in
OPPOSITE directions with plasma propofol (`exponent_low` rho = -0.810 +/- 0.051, `exponent_high`
rho = +0.710 +/- 0.076) while the mixture retains rho = -0.130 +/- 0.129. If that is right, the sub-bands
should behave consistently across deposits exactly where the broadband did not.

THE REGISTERED PREDICTION, copied verbatim from E50's ledger entry:

    "Re-extract ds005620 and ds004541 through analysis/eeg_features_common.py (chennu already carries both
    sub-bands) and re-run E49 on exponent_low and exponent_high SEPARATELY. PREDICTION: the two sub-bands
    AGREE in sign across deposits where whole_head_exponent flipped, and their E49 resolvability R exceeds
    the broadband's. FALSIFICATION: if the sub-bands flip sign across deposits too, the mixture explanation
    is wrong and E49's floor is genuine study noise."

=========================================================================================================
PRIMARY
=========================================================================================================
E49's statistic, unchanged: within-subject awake->deep displacement expressed in units of the deposit's own
BETWEEN-SUBJECT awake spread (Delta), for chennu and ds005620 -- both PROPOFOL, so the drug contrast is
exactly zero and any disagreement is study, pipeline or noise.

    agreement   sign(Delta_chennu) == sign(Delta_ds005620)
    floor       |Delta_chennu - Delta_ds005620|
    R           mean(|Delta|) / floor

reported for `exponent_low`, `exponent_high` and, as the INCUMBENT, `whole_head_exponent` -- the measure
that flipped. Subject-level bootstrap, floor recomputed inside every draw.

=========================================================================================================
VERDICT RULE -- wrong direction named first (rules 37, 49)
=========================================================================================================
  (a) FALSIFIED -- either sub-band flips sign between the two deposits, or the bootstrapped probability of
      a sign disagreement exceeds 0.05. E50's mixture explanation is wrong and E49's floor is genuine
      study noise. **This is a live outcome and the experiment exists because it can occur.**
  (b) NOT INFORMATIVE -- whole_head_exponent does NOT flip sign in this re-extraction, so there is no
      flip for the sub-bands to explain. The comparison would be vacuous and must not be read as support.
  (c) CONFIRMED -- both sub-bands agree in sign across deposits, whole_head_exponent flips, AND at least
      one sub-band's R exceeds the broadband's.

Branch (b) matters and is easy to overlook: the whole prediction is conditional on the broadband flipping,
and the broadband value here comes from a DIFFERENT extraction of ds005620 than E49 used. If the flip does
not reproduce, nothing about the sub-bands is evidence for anything.

=========================================================================================================
THE PIPELINE CAVEAT, STATED BEFORE THE RESULT
=========================================================================================================
chennu's sub-bands come from the earlier per-deposit extraction; ds005620's come from
`analysis/eeg_features_common.py`. **The ESTIMATOR is identical** -- both call `subband_exponents` from
`bsde.features.exotic`, so the fits are the same function over the same bands. What differs is
preprocessing: montage, the 180 s analysis window, and the 250 Hz resample.

That is a real limitation and it is why the claim under test is about SIGN rather than magnitude: a
preprocessing difference would have to be large enough to reverse a within-subject displacement to
invalidate the test, which is a much higher bar than shifting one. **The clean version re-extracts chennu
through the shared path too** -- it is reachable at `CHENNU_ARCHIVE_URL` in `ingestion/chennu.py` -- and
that should be done before this result is used anywhere load-bearing.

A second limitation inherited from E49: chennu and ds005620 are both SEDATION studies (chennu subjects
still score 26.9/40 at the deepest level), so nothing here speaks to loss of consciousness.

    python -m bsde.experiments.e52_subband_sign_agreement
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

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e52_subband_sign_agreement.json")
STATE_CSV = "/tmp/eeg_probe/state_cohorts.csv"

FEATURES = ("exponent_low", "exponent_high", "whole_head_exponent")
INCUMBENT = "whole_head_exponent"
MIN_SUBJECTS = 6
REPS = 20000
SEED = 20260731


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:                                                        # noqa: BLE001
        return None


def _chennu():
    """(awake_rows, deep_rows) keyed by subject. Level 1 is awake; level 3 is DEEPEST -- level 4 is
    RECOVERY (plasma 0 / 447 / 900 / 290 ug/L), a trap E49 documents."""
    with open(os.path.join(RESULTS, "chennu_features_v3.csv")) as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("status", "ok") == "ok"]
    aw = {r["subject"]: r for r in rows if r.get("meta_sedation_level") == "1.0"}
    dp = {r["subject"]: r for r in rows if r.get("meta_sedation_level") == "3.0"}
    return aw, dp


def _ds005620():
    """Shared-path re-extraction. `task-awake` vs `task-sed`; several recordings per subject are averaged."""
    if not os.path.exists(STATE_CSV):
        return {}, {}
    with open(STATE_CSV) as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("cohort") == "ds005620"]
    aw, dp = {}, {}
    for r in rows:
        (aw if r.get("task") == "awake" else dp if r.get("task") == "sed" else {}).setdefault(
            r["subject"], []).append(r)
    return aw, dp


def _delta(aw, dp, feat):
    """Within-subject displacement in units of the between-subject AWAKE spread. Returns (value, n)."""
    subs = sorted(set(aw) & set(dp))
    a, d = [], []
    for s in subs:
        av = aw[s] if isinstance(aw[s], list) else [aw[s]]
        dv = dp[s] if isinstance(dp[s], list) else [dp[s]]
        x = [_f(r.get(feat)) for r in av]
        y = [_f(r.get(feat)) for r in dv]
        x = [z for z in x if z is not None]
        y = [z for z in y if z is not None]
        if not x or not y:
            continue
        a.append(float(np.mean(x)))
        d.append(float(np.mean(y)))
    a, d = np.array(a), np.array(d)
    if a.size < MIN_SUBJECTS:
        return None, None, a.size
    sd = float(np.std(a, ddof=1))
    if sd <= 0:
        return None, None, a.size
    return a, d, a.size


def _stat(a, d):
    return float(np.mean(d - a) / np.std(a, ddof=1))


def main() -> int:
    ca, cd = _chennu()
    sa, sd = _ds005620()
    if not sa or not sd:
        print(f"ds005620 rows not available at {STATE_CSV} -- extraction still running. No verdict.")
        return 1

    rng = np.random.default_rng(SEED)
    print("=" * 100)
    print("E52 -- confirmatory test of E50's registered prediction")
    print("=" * 100)
    res = {}
    for feat in FEATURES:
        ca_a, ca_d, n1 = _delta(ca, cd, feat)
        sa_a, sa_d, n2 = _delta(sa, sd, feat)
        if ca_a is None or sa_a is None:
            print(f"   {feat:22s} insufficient paired subjects ({n1} chennu, {n2} ds005620)")
            res[feat] = {"verdict": "SKIPPED", "n": [n1, n2]}
            continue
        d1, d2 = _stat(ca_a, ca_d), _stat(sa_a, sa_d)
        floor = abs(d1 - d2)
        mean_abs = (abs(d1) + abs(d2)) / 2.0
        disagree, fl = 0, []
        for _ in range(REPS):
            i1 = rng.integers(0, ca_a.size, ca_a.size)
            i2 = rng.integers(0, sa_a.size, sa_a.size)
            try:
                b1, b2 = _stat(ca_a[i1], ca_d[i1]), _stat(sa_a[i2], sa_d[i2])
            except Exception:                                                # noqa: BLE001
                continue
            if not (math.isfinite(b1) and math.isfinite(b2)):
                continue
            fl.append(abs(b1 - b2))
            if (b1 > 0) != (b2 > 0):
                disagree += 1
        p_disagree = disagree / max(len(fl), 1)
        fl = np.sort(np.array(fl))
        fhi = float(np.quantile(fl, 0.975)) if fl.size else float("nan")
        R = mean_abs / floor if floor > 0 else float("inf")
        agree = (d1 > 0) == (d2 > 0)
        res[feat] = {"delta_chennu": d1, "delta_ds005620": d2, "same_sign": bool(agree),
                     "p_sign_disagreement": p_disagree, "floor": floor, "floor_hi": fhi,
                     "R": R, "n": [n1, n2]}
        print(f"   {feat:22s} chennu {d1:+7.3f}   ds005620 {d2:+7.3f}   "
              f"same sign {str(agree):5s}  P(disagree) {p_disagree:.4f}  R {R:6.2f}  n {n1}/{n2}")

    inc = res.get(INCUMBENT, {})
    print("\n" + "-" * 100)
    if not inc.get("delta_chennu") and inc.get("verdict") == "SKIPPED":
        verdict = "NOT INFORMATIVE (incumbent not evaluable)"
    elif inc.get("same_sign"):
        verdict = ("NOT INFORMATIVE -- whole_head_exponent did NOT flip sign in this re-extraction, "
                   "so there is no flip for the sub-bands to explain. E50 is neither supported nor "
                   "refuted by this run.")
    else:
        subs = [res[f] for f in ("exponent_low", "exponent_high") if "same_sign" in res[f]]
        if len(subs) < 2:
            verdict = "NOT INFORMATIVE (a sub-band was not evaluable)"
        elif not all(s["same_sign"] for s in subs):
            verdict = ("FALSIFIED -- a sub-band flips sign across deposits too. The mixture explanation "
                       "is wrong and E49's floor is genuine study noise.")
        elif any(s["p_sign_disagreement"] > 0.05 for s in subs):
            verdict = ("FALSIFIED -- sign agreement is not stable under resampling "
                       f"(max P(disagree) = {max(s['p_sign_disagreement'] for s in subs):.4f}).")
        elif not any(s["R"] > inc.get("R", float("inf")) for s in subs):
            verdict = ("PARTIAL -- signs agree but neither sub-band's resolvability exceeds the "
                       "broadband's, which the prediction also required.")
        else:
            verdict = "CONFIRMED -- sub-bands agree in sign where the broadband flips, and resolve better."
    print(f"VERDICT: {verdict}")
    json.dump({"features": res, "verdict": verdict, "reps": REPS, "seed": SEED},
              open(OUT, "w"), indent=2, default=str)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
