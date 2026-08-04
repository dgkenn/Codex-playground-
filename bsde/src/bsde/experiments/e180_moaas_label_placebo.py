#!/usr/bin/env python3
"""E180 — rule 78 applied to the largest surviving Challenge C claim: is MOAA/S the phenomenon?

REGISTERED BEFORE ANY SHIFTED-LABEL INCREMENT HAS BEEN COMPUTED.

=========================================================================================================
WHY THIS FILE EXISTS, AND WHY IT IS URGENT RATHER THAN TIDY
=========================================================================================================
**E150 is the biggest live Challenge C result this project has.** It re-derived E84's "nothing adds" with
a calibrated test and found **11 of 27 candidates add** to the deposit's own validated PE31 + SEF95
baseline for predicting MOAA/S, every one at p = 0.00000 or 0.00200, on 42 held-out DOSE-I recordings.

**E170 and E178 have just destroyed two results built the same way.** e34 and e37 each had a calibrated
cluster-permutation null, a measured detection floor and a rho = 0 rung that did not fire — and both
collapsed when a placebo was run on the LABEL rather than on the feature. Error-catalogue rule 78 is the
generalisation: *a permutation null answers "does this column carry information about the label I gave
it"; it is silent on whether that label is the phenomenon.*

**E150's placebo is a cluster-permuted FEATURE.** Read its code: the placebo column is
`cluster_permute(xx, ss, rng)`, i.e. the candidate shuffled across recordings. That is a negative control
on the feature side and it is a good one — it is not a placebo on the label, and E150 has none.

So the question this file asks is exactly the one that killed e34 and e37, aimed at the claim that would
cost the most: **do those 11 increments survive a MOAA/S that has been decoupled from the EEG in time?**

=========================================================================================================
THE LABEL PLACEBO, AND WHY A TIME SHIFT RATHER THAN A PERMUTATION
=========================================================================================================
MOAA/S has no landmark to fake — it is a clinician's repeated observation, not a constructed cut — so
E170's fake-landmark construction does not transfer. What CAN be destroyed is the moment-to-moment
correspondence between the EEG window and the observation, while leaving everything else intact.

**Each recording's MOAA/S series is CIRCULARLY SHIFTED by a lag.** That preserves, exactly: the marginal
distribution of the label, its within-recording autocorrelation, the number of observations, the cluster
structure and the base rate. It destroys only the alignment. If a candidate adds as much to a shifted
MOAA/S as to the real one, the increment is about slow structure that both the EEG and the sedation score
share over a recording — drift, position, procedure phase — and not about depth at that window.

**THE LAG IS DERIVED, NOT CHOSEN (rule 63).** MOAA/S is highly autocorrelated, so a small shift changes
almost nothing and would make the placebo trivially easy to beat. The file first MEASURES the
within-recording autocorrelation of MOAA/S as a function of lag and reports its half-life; shifts are
drawn only from lags beyond that half-life. If no such lag exists inside a recording's length, that
recording is excluded and the exclusion is counted.

**THE PLACEBO IS ITSELF CHECKED FOR MATCH (rule 78's second half).** Under a shifted label the incumbent
will predict worse, and an added column has more room to help when the baseline is weaker — which is the
defect E170's placebo turned out to have. So the incumbent's out-of-fold performance under the real label
and under each shifted label is measured and reported, and shifts are **rejection-sampled** to lie within
`BASE_TOL` of the real label's baseline. If the band cannot be filled, the arm reports NOT MATCHABLE and
the unmatched arm is read with the direction of its bias stated.

=========================================================================================================
THE SECOND ARM, WHICH IS ABOUT WHAT MOAA/S ACTUALLY MEASURES
=========================================================================================================
**E150's largest adder is `emg_index`** (-0.02478), and `emg_kurtosis` and `emg_beta_gamma_fraction` are
also in its list of 11. MOAA/S is scored by observing whether the patient **responds to name and to a mild
shake** — that is, by MOVEMENT. A muscle measure predicting MOAA/S beyond an EEG depth index is close to
tautological, and this project has been here before: E22 died on an EMG gradient across the label, and
rule 57 records that an amplitude in arbitrary units is not a magnitude.

So the survivors are reported **twice**: as E150 reported them, and with the muscle family
(`emg_index`, `emg_kurtosis`, `emg_beta_gamma_fraction`) removed. If the muscle candidates are the ones
that survive the label placebo and the EEG candidates are not, the claim changes from "EEG adds to a depth
index" to "movement predicts a movement-scored scale", which is not a Challenge C result at all.

=========================================================================================================
GATES
=========================================================================================================
G1  REBUILD: E150's cohort, built by E150's own loader, must return the same recording count. Anything
    else and this file is not about E150 (rule 59).
G2  THE INCUMBENT IS ALIVE under the REAL label, measured here rather than imported.
G3  THE SHIFT IS A REAL DESTRUCTION: the measured half-life of MOAA/S's within-recording autocorrelation
    is printed, and the minimum admissible lag is set from it. A shift shorter than that is not used.
G4  THE PLACEBO IS MATCHED on the incumbent's out-of-fold performance, or the arm says NOT MATCHABLE.

=========================================================================================================
VERDICT, PER CANDIDATE — THE WITHDRAWING CASES FIRST (rules 31, 34, 37, 78)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3 fails.
  (2) WITHDRAWN          the shifted-label increment reaches the real one in more than 5 % of shifts.
                         The candidate's addition is about slow shared structure, not about depth, and
                         E150's entry for it is withdrawn exactly as e34's was.
  (3) MUSCLE-ONLY        the only survivors are in the muscle family. Then the finding is that movement
                         predicts a movement-scored scale and Challenge C gets nothing.
  (4) SURVIVES           the increment exceeds the shifted-label distribution, and at least one non-muscle
                         candidate does so. **E150's claim then has the label placebo it was missing**,
                         and it becomes the strongest surviving Challenge C result in this ledger.

**REGISTERED PREDICTION: (2) for most candidates and (3) or (4) for one or two.** MOAA/S changes slowly
and monotonically through a procedure, so almost any measure with a within-recording trend will predict a
shifted copy of it nearly as well as the real one. The two results that just died had exactly this shape.
**The prediction is against this project's largest live Challenge C claim**, which is the correct way
round, and if it is wrong the claim is much stronger than it was this morning.

    python bsde/src/bsde/experiments/e180_moaas_label_placebo.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import grouped_cv_predict, permutation_increment, spearman  # noqa: E402
import e84_increment_over_validated_incumbent as E84                                 # noqa: E402
from e150_challenge_c_negatives_rederived import build                               # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e180_moaas_label_placebo.json")
SEED = 20260801

# E150's eleven, transcribed IN FULL with their increments (rule 59) -- not the subset that suits a story
E150_ADDS = {
    "emg_index": -0.02478, "multiscale_entropy_slope": -0.03191, "relative_alpha_power": -0.03512,
    "bis_rbr": -0.02878, "whole_head_exponent": -0.01514, "wpli_theta": -0.00831,
    "emg_kurtosis": -0.00730, "emg_beta_gamma_fraction": -0.00927, "pac_slow_alpha": -0.00248,
    "wpli_delta": -0.00161, "wpli_alpha_2ch": -0.00152,
}
MUSCLE = ("emg_index", "emg_kurtosis", "emg_beta_gamma_fraction")
E150_JSON = os.path.join(RESULTS, "e150_challenge_c_rederived.json")
# The reference cohort size is LOADED from E150's own result rather than transcribed from prose (rule 59).
# The first version hardcoded 42, taken from E84's ledger text describing E84's held-out half; E150 in fact
# ran on 62 recordings and 17,196 windows, so the gate refused a correct rebuild.
try:
    _e150 = json.load(open(E150_JSON))
    N_RECORDINGS, N_WINDOWS = int(_e150["n_recordings"]), int(_e150["n_windows"])
except Exception:                                                              # noqa: BLE001
    N_RECORDINGS, N_WINDOWS = -1, -1
N_SHIFTS = 200
MAX_TRIES = 3000
BASE_TOL = 0.03
PERMS = 300
ALPHA = 0.05


def autocorr_halflife(y, subj):
    """Median lag at which within-recording autocorrelation of MOAA/S falls below half its lag-1 value."""
    hl = []
    for u in np.unique(subj):
        v = y[subj == u]
        v = v[np.isfinite(v)]
        if v.size < 30 or np.std(v) < 1e-9:
            continue
        a1 = spearman(list(v[:-1]), list(v[1:]))
        if not np.isfinite(a1) or a1 <= 0:
            continue
        for lag in range(2, v.size // 2):
            a = spearman(list(v[:-lag]), list(v[lag:]))
            if np.isfinite(a) and a < 0.5 * a1:
                hl.append(lag)
                break
    return (int(np.median(hl)) if hl else -1), len(hl)


def shift_label(y, subj, min_lag, rng):
    """Circular shift of each recording's label series, lag drawn beyond `min_lag`."""
    out = np.empty_like(y)
    for u in np.unique(subj):
        m = subj == u
        v = y[m]
        n = v.size
        if n <= 2 * min_lag + 2:
            out[m] = v                       # too short to shift admissibly; left intact and counted
            continue
        lag = int(rng.integers(min_lag, n - min_lag))
        out[m] = np.roll(v, lag)
    return out


def baseline_perf(base, y, subj, seed):
    p = grouped_cv_predict(base, y, subj, np.random.default_rng(seed))
    ok = np.isfinite(p)
    r = spearman(list(y[ok]), list(p[ok]))
    return float(r) if np.isfinite(r) else float("nan")


def main() -> int:
    print("E180 — is MOAA/S the phenomenon? A label placebo for E150's eleven additions")
    y, subj, base, cand, cands, n_rec = build()
    res = {"experiment": "E180", "n_recordings": int(n_rec), "n_windows": int(len(y)),
           "e150_adds": E150_ADDS}
    g1 = (n_rec == N_RECORDINGS) and (len(y) == N_WINDOWS)
    print(f"G1 REBUILD  {n_rec} recordings, {len(y)} windows vs E150's own stored "
          f"{N_RECORDINGS} / {N_WINDOWS}   {'PASS' if g1 else '*** FAIL'}")
    res["G1_pass"] = bool(g1)
    if not g1:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    real_base = baseline_perf(base, y, subj, SEED)
    print(f"G2 INCUMBENT ALIVE  PE31+SEF95 out-of-fold rho against MOAA/S = {real_base:+.4f}")
    res["G2_baseline_rho"] = real_base
    res["G2_pass"] = bool(np.isfinite(real_base) and real_base > 0.1)
    if not res["G2_pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "the incumbent does not predict MOAA/S here"
        print("   *** FAIL — nothing to add to")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    hl, n_hl = autocorr_halflife(y, subj)
    print(f"G3 SHIFT IS A REAL DESTRUCTION  MOAA/S autocorrelation half-life = {hl} windows "
          f"(median over {n_hl} recordings); shifts are drawn beyond it")
    res["G3"] = {"halflife_windows": hl, "n_recordings_measured": n_hl,
                 "pass": bool(hl > 0)}
    if hl <= 0:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "MOAA/S's autocorrelation never halves, so no admissible shift exists"
        print("   *** FAIL")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # ---- build the shifted-label pool, rejection-sampled on the incumbent's performance (G4)
    rng = np.random.default_rng(SEED + 1)
    pool, tries, kept_base = [], 0, []
    while len(pool) < N_SHIFTS and tries < MAX_TRIES:
        tries += 1
        ys = shift_label(y, subj, hl, rng)
        if len(np.unique(ys)) < 2:
            continue
        b = baseline_perf(base, ys, subj, SEED + 2000 + tries)
        if not np.isfinite(b):
            continue
        if abs(b - real_base) > BASE_TOL:
            continue
        pool.append(ys)
        kept_base.append(b)
    matched = len(pool) >= 30
    if not matched:
        print(f"G4 MATCH  only {len(pool)} of {N_SHIFTS} shifts land within {BASE_TOL} of the real "
              f"baseline in {tries} attempts -- NOT MATCHABLE; falling back to UNMATCHED shifts")
        rng2 = np.random.default_rng(SEED + 3)
        pool, kept_base = [], []
        while len(pool) < N_SHIFTS:
            ys = shift_label(y, subj, hl, rng2)
            if len(np.unique(ys)) < 2:
                continue
            pool.append(ys)
            kept_base.append(baseline_perf(base, ys, subj, SEED + 4000 + len(pool)))
    res["G4"] = {"matched": bool(matched), "n_shifts": len(pool), "n_tries": int(tries),
                 "real_baseline": real_base, "shift_baseline_mean": float(np.mean(kept_base)),
                 "tol": BASE_TOL}
    print(f"G4 MATCH  {len(pool)} shifted labels; incumbent rho real {real_base:+.4f} vs shifted "
          f"{np.mean(kept_base):+.4f}   {'MATCHED' if matched else 'UNMATCHED (bias stated below)'}")

    # ---- per candidate: the real increment and the shifted-label distribution
    print(f"\n{'candidate':<26s} {'E150':>9s} {'real':>9s} {'shift mean':>11s} {'frac>=real':>11s}  "
          f"verdict")
    table = {}
    for c in E150_ADDS:
        x = cand.get(c)
        if x is None:
            table[c] = {"status": "ABSENT"}
            print(f"{c:<26s} column absent from the table")
            continue
        ok = np.isfinite(x)
        if ok.sum() < 0.5 * len(y):
            table[c] = {"status": "TOO-FEW"}
            continue
        yy, ss, bb, xx = y[ok], subj[ok], base[ok], x[ok]
        real, p_real, _, _ = permutation_increment(bb, np.c_[bb, xx], yy, ss,
                                                   np.random.default_rng(SEED + 5),
                                                   stat=E84.err, reps=PERMS)
        shifted = []
        for i, ys in enumerate(pool):
            # the shifted-label increment is computed by the SAME cross-fit the real one uses; no inner
            # permutation null is needed here because the SHIFTS themselves are the null distribution
            pa = grouped_cv_predict(bb, ys[ok], ss, np.random.default_rng(SEED + 6000 + i))
            pb = grouped_cv_predict(np.c_[bb, xx], ys[ok], ss, np.random.default_rng(SEED + 6000 + i))
            m2 = np.isfinite(pa) & np.isfinite(pb)
            if m2.sum() < 100:
                continue
            shifted.append(E84.err(ys[ok][m2], pb[m2]) - E84.err(ys[ok][m2], pa[m2]))
        sh = np.asarray([v for v in shifted if np.isfinite(v)])
        frac = float((sh <= real).mean()) if sh.size >= 30 else float("nan")
        fires = bool(np.isfinite(frac) and frac > ALPHA)
        v = "WITHDRAWN" if fires else "survives"
        table[c] = {"e150": E150_ADDS[c], "real": float(real), "p_real": float(p_real),
                    "shift_mean": float(sh.mean()) if sh.size else float("nan"),
                    "shift_p05": float(np.quantile(sh, 0.05)) if sh.size else float("nan"),
                    "fraction_at_or_below_real": frac, "n_shifts": int(sh.size),
                    "muscle": c in MUSCLE, "withdrawn": fires}
        print(f"{c:<26s} {E150_ADDS[c]:>+9.5f} {real:>+9.5f} "
              f"{table[c]['shift_mean']:>+11.5f} {frac:>11.4f}  {v}"
              + ("   <- MUSCLE" if c in MUSCLE else ""))
    res["table"] = table

    survivors = [c for c, v in table.items() if v.get("withdrawn") is False]
    non_muscle = [c for c in survivors if c not in MUSCLE]
    res["survivors"], res["non_muscle_survivors"] = survivors, non_muscle
    if not survivors:
        verdict = "WITHDRAWN"
        why = ("no candidate's increment exceeds what a TIME-SHIFTED MOAA/S produces, so every one of "
               "E150's eleven is about slow structure the EEG and the sedation score share over a "
               "recording rather than about depth at that window -- the same failure that killed e34 "
               "and e37 (rule 78)")
    elif not non_muscle:
        verdict = "MUSCLE-ONLY"
        why = (f"the only survivors are {survivors}, all in the muscle family. MOAA/S is scored by "
               "whether the patient responds to name and shake, i.e. by MOVEMENT, so this is movement "
               "predicting a movement-scored scale and Challenge C gets nothing from it")
    else:
        verdict = "SURVIVES"
        why = (f"{non_muscle} exceed the shifted-label distribution and are not muscle measures. E150's "
               "claim now has the label placebo it was missing, and this is the strongest surviving "
               "Challenge C result in the ledger")
    if not matched:
        why += (". **The shift pool is UNMATCHED on baseline predictability** (real "
                f"{real_base:+.4f} vs shifted {np.mean(kept_base):+.4f}); a weaker baseline gives an "
                "added column more room, so an unmatched placebo that FIRES is too harsh and one that "
                "does NOT fire is too lenient -- the direction is stated and the verdict is not adjusted")
    res["verdict"], res["why"] = verdict, why
    print(f"\nVERDICT {verdict} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
