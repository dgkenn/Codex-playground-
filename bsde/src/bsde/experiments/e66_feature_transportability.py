#!/usr/bin/env python3
"""E66 -- cross-cutting. Which of this project's features survive a change of deposit, and which do not?

REGISTERED BEFORE ANY CROSS-DEPOSIT RATIO HAS BEEN COMPUTED. What is known and committed is E65's pre-fit
check on TWO deposits: `exponent_gamma` reads -2.675 on VitalDB and +29.651 on DOSE-I, `exponent_high`
+4.804 against +0.004, `whole_head_exponent` +2.196 against +0.820, while `exponent_low` agrees at +1.387
against +1.435. No third deposit has been looked at and no ratio computed.

=========================================================================================================
WHY THIS MATTERS MORE THAN ANY SINGLE EXPERIMENT
=========================================================================================================
The BSDE programme wants a **normative reference** -- a per-person expectation a measure can be scored
against. E47 showed the pipeline is calibrated, E48 showed aperiodic correction reduces between-cohort
disagreement but costs signal, E51 priced that cost, E53 attributed part of the floor to the pipeline. All
four assume the features themselves are comparable across deposits. **E65 found one that is not, and found
it by accident, while checking something else.**

A feature whose value depends more on WHICH DEPOSIT it came from than on WHICH PERSON it came from cannot
carry a normative reference, cannot be pooled, and cannot be transported to a deposit the model was not
fitted on -- whatever the cause. That is the quantity measured here.

=========================================================================================================
THE STATISTIC, AND WHAT IT DELIBERATELY DOES NOT CLAIM
=========================================================================================================
Per feature:

    R = (IQR of the per-deposit medians) / (median of the within-deposit between-subject IQRs)

**R > 1 means the deposit moves the feature more than the person does.** Rows are aggregated to one value
per subject within each deposit first, so deposits contributing many windows per subject (VitalDB, DOSE-I)
do not dominate through pseudo-replication.

**R DOES NOT IDENTIFY A CAUSE, AND THIS FILE DOES NOT PRETEND OTHERWISE (rule 50).** Between-deposit spread
confounds device, montage, reference, sampling rate, preprocessing pipeline AND population -- HBN is
paediatric (5-20), VitalDB is surgical adults, DOSE-I is endoscopy patients, chennu is young volunteers.
A high R is a statement about USABILITY, which is decision-relevant on its own; it is not a statement about
hardware.

**One mechanism IS separately testable, and it is the reason E65 caught `exponent_gamma`.** A feature whose
analysis band approaches the acquisition Nyquist is fitting the anti-alias rolloff, and rolloff is
device-specific. That predicts a RANKING, not just a list:

  H1  R correlates POSITIVELY with the feature's upper band edge expressed as a fraction of the LOWEST
      native Nyquist across deposits. **PREDICTED POSITIVE, and it is falsifiable**: if the worst-
      transporting features are not the highest-band ones, the rolloff story is wrong and the failure is
      population or pipeline instead.

  G1 COVERAGE GATE  a feature is scored only if at least `MIN_DEPOSITS` deposits carry it with at least
                    `MIN_SUBJECTS` subjects each. A ratio over three deposits is not a ratio.
  P1 PLACEBO        deposit labels shuffled across all subject-level rows, R recomputed. **R has no natural
                    null at 1** -- it is a ratio of two spreads estimated from different sample sizes -- so
                    the shuffled value is what "no deposit effect" actually looks like for this statistic,
                    and every R is reported against it rather than against 1.

VERDICT RULE, wrong direction first.

  (a) H1 REVERSED  -- the band-edge correlation is negative with an interval excluding zero: the
                      worst-transporting features are the LOW-band ones, which refutes the rolloff account
                      and points at population or pipeline.
  (b) H1 ABSENT    -- the interval includes zero. The audit still stands as a usability ranking; the
                      mechanism does not.
  (c) H1 SUPPORTED -- positive, excluding zero. High-band features transport worst, consistent with
                      anti-alias rolloff being device-specific, and the practical rule follows: exclude
                      features whose band approaches the lowest Nyquist in any pooled analysis.

WHATEVER H1 DOES, the per-feature table is the deliverable and it is reported in full -- including for
features that transport well, since a normative reference needs to know what it CAN use.

    python -m bsde.experiments.e66_feature_transportability
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
from bsde.verifier.stats import spearman                                     # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e66_feature_transportability.json")

# deposit -> (table, subject column, native acquisition sampling rate in Hz)
DEPOSITS = {
    "chennu":   ("chennu_features_v3.csv", "subject", 250.0),
    "ds004541": ("ds004541_v2.csv", "subject", 500.0),
    "eegmmidb": ("eegmmidb_rest.csv", "subject", 160.0),
    "hbn":      ("hbn_r1_resting.csv", "subject", 500.0),
    "dosei":    ("dosei_features.csv", "recording", 125.0),
    "vitaldb":  ("vitaldb_grid.csv", "meta_caseid", 128.0),
}

# feature -> upper edge of the band it analyses, in Hz. Taken from each feature's own definition, not
# from any result: the fit range for the aperiodic family, the band for the power ratios, the low-pass
# for the broadband measures.
BAND_HI = {
    "exponent_low": 20.0, "exponent_high": 40.0, "whole_head_exponent": 40.0,
    "exponent_gamma": 90.0, "spectral_edge_95": 40.0, "relative_alpha_power": 13.0,
    "relative_delta_power": 4.0, "spectral_entropy": 40.0, "lempel_ziv": 45.0,
    "pac_slow_alpha": 13.0, "emg_index": 45.0, "critical_slowing_ar1": 45.0,
    "multiscale_entropy_slope": 45.0,
}
MIN_DEPOSITS = 4
MIN_SUBJECTS = 15
REPS = 400
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def subject_level():
    """One value per (deposit, subject, feature): the subject's median across their rows."""
    acc = defaultdict(lambda: defaultdict(list))
    for dep, (fn, scol, _) in DEPOSITS.items():
        p = os.path.join(RESULTS, fn)
        if not os.path.exists(p):
            print(f"   {dep}: MISSING {fn}")
            continue
        with open(p, newline="") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            s = r.get(scol, "")
            if not s:
                continue
            for feat in BAND_HI:
                v = _f(r.get(feat, ""))
                if np.isfinite(v):
                    acc[(dep, feat)][s].append(v)
    return {k: {s: float(np.median(v)) for s, v in d.items()} for k, d in acc.items()}


def ratios(sub, assign=None):
    """R per feature. `assign` remaps (dep, subject) -> deposit, which is how the placebo shuffles."""
    out = {}
    for feat in BAND_HI:
        per = defaultdict(list)
        for (dep, f2), d in sub.items():
            if f2 != feat:
                continue
            for s, v in d.items():
                per[assign[(dep, s)] if assign else dep].append(v)
        per = {d: np.asarray(v, float) for d, v in per.items() if len(v) >= MIN_SUBJECTS}
        if len(per) < MIN_DEPOSITS:
            out[feat] = {"R": float("nan"), "n_deposits": len(per)}
            continue
        meds = np.array([np.median(v) for v in per.values()])
        within = np.median([np.quantile(v, .75) - np.quantile(v, .25) for v in per.values()])
        between = float(np.quantile(meds, .75) - np.quantile(meds, .25))
        out[feat] = {"R": float(between / within) if within > 1e-12 else float("inf"),
                     "between_iqr": between, "within_iqr": float(within),
                     "n_deposits": len(per),
                     "n_subjects": {d: int(v.size) for d, v in per.items()},
                     "medians": {d: float(np.median(v)) for d, v in per.items()}}
    return out


def main() -> int:
    print("building subject-level values ...")
    sub = subject_level()
    obs = ratios(sub)
    scored = [f for f in BAND_HI if np.isfinite(obs[f].get("R", np.nan))]
    print(f"\nG1: {len(scored)} of {len(BAND_HI)} features scored "
          f"(need {MIN_DEPOSITS} deposits x {MIN_SUBJECTS} subjects)")
    if len(scored) < 4:
        print("G1 FAILED -- too few features clear coverage for a ranking. Verdict ABSENT (rule 31).")
        json.dump({"gate_g1": False, "features": obs}, open(OUT, "w"), indent=2)
        return 1

    # P1 placebo: shuffle deposit labels across subject-level rows.
    rng = np.random.default_rng(SEED)
    pairs = sorted({(dep, s) for (dep, _), d in sub.items() for s in d})
    deps = [p[0] for p in pairs]
    null = defaultdict(list)
    for _ in range(REPS // 20):
        perm = dict(zip(pairs, rng.permutation(deps)))
        r = ratios(sub, assign=perm)
        for f in scored:
            if np.isfinite(r[f].get("R", np.nan)):
                null[f].append(r[f]["R"])
    nullmed = {f: float(np.median(null[f])) if null[f] else float("nan") for f in scored}

    lo_nyq = min(v[2] for v in DEPOSITS.values()) / 2.0
    print(f"\nlowest native Nyquist across deposits: {lo_nyq:.1f} Hz")
    print(f"\n{'feature':<26s} {'R':>7s} {'null R':>7s} {'R/null':>7s} {'band_hi':>8s} "
          f"{'hi/Nyq':>7s} {'dep':>4s}")
    rows = []
    for f in sorted(scored, key=lambda k: -obs[k]["R"]):
        rel = BAND_HI[f] / lo_nyq
        ratio = obs[f]["R"] / nullmed[f] if nullmed[f] and np.isfinite(nullmed[f]) else float("nan")
        print(f"{f:<26s} {obs[f]['R']:>7.3f} {nullmed[f]:>7.3f} {ratio:>7.2f} "
              f"{BAND_HI[f]:>8.0f} {rel:>7.2f} {obs[f]['n_deposits']:>4d}")
        rows.append((f, obs[f]["R"], rel, ratio))

    # H1: does R rank with band edge?
    R = np.array([r[1] for r in rows])
    E = np.array([r[2] for r in rows])
    rho = spearman(R, E)
    boot = []
    for _ in range(2000):
        i = rng.integers(0, len(R), len(R))
        if np.unique(E[i]).size > 2:
            v = spearman(R[i], E[i])
            if np.isfinite(v):
                boot.append(v)
    b = np.sort(boot)
    h_lo, h_hi = (float(np.quantile(b, .025)), float(np.quantile(b, .975))) if len(b) > 100 else (
        float("nan"), float("nan"))
    print(f"\nH1  Spearman(R, band_hi / lowest Nyquist) = {rho:+.4f} [{h_lo:+.4f}, {h_hi:+.4f}] "
          f"over {len(rows)} features")

    if not np.isfinite(h_lo):
        verdict = "H1 ABSENT -- too few features to bootstrap a correlation."
    elif h_hi < 0:
        verdict = ("H1 REVERSED -- the worst-transporting features are the LOW-band ones, which refutes "
                   "the anti-alias-rolloff account and points at population or pipeline instead.")
    elif h_lo <= 0:
        verdict = ("H1 ABSENT -- the band-edge correlation includes zero. The usability ranking below "
                   "stands; the mechanism does not, and the transport failures are not explained by "
                   "where a feature's band sits.")
    else:
        verdict = ("H1 SUPPORTED -- features whose band reaches nearer the lowest acquisition Nyquist "
                   "transport worst, consistent with anti-alias rolloff being device-specific. Practical "
                   "rule: exclude high-band features from any pooled or transported analysis.")
    print(f"\nVERDICT: {verdict}")
    print("\nNOTE: R measures USABILITY, not cause. Between-deposit spread confounds device, montage, "
          "reference, sampling rate, pipeline AND population (rule 50). H1 is the only part of this that "
          "speaks to a mechanism.")

    json.dump({"gate_g1": True, "features": obs, "null_R": nullmed,
               "lowest_nyquist_hz": lo_nyq, "band_hi": BAND_HI,
               "h1": {"rho": rho, "lo": h_lo, "hi": h_hi, "n_features": len(rows)},
               "verdict": verdict}, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
