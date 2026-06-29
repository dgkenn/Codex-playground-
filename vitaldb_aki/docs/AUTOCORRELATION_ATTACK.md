# Autocorrelation attack on the vasopressor-requirement reliability

**The attack (hostile methods reviewer):** "The within-encounter reliability (MIMIC split-half 0.95, VitalDB 0.82) and the early->late prediction (MIMIC 0.62, VitalDB 0.54) are TRIVIAL AUTOCORRELATION. A slowly-titrated infusion is piecewise-constant, so an early sample mechanically predicts a late sample. This is mechanical persistence, not a meaningful patient trait."

This document tests, honestly, whether the signal is MORE than mechanical persistence.

**VERDICT: GENUINE BETWEEN-PATIENT TRAIT (attack REJECTED). The reliability/early->late is NOT merely mechanical persistence.**

GENUINE BETWEEN-PATIENT TRAIT (attack REJECTED). The reliability/early->late is NOT merely mechanical persistence. ICC(1) of log-requirement = 0.392 (15137 stays): substantial between-patient variance. Between-patient fold-range (p90/p10) of the requirement = 9.31x. Early->late Spearman: 0.594 at gap=0h vs 0.508 at gap>=6h, 0.422 at >=12h -- SURVIVES a multi-hour gap (not adjacent stickiness). Shuffle-null: reliability -0.012, early->late 0.015 (both ~0 => metric not spuriously inflated). Within-stay rate CV median = 0.51 (rate genuinely MOVES within a stay -- not trivially constant). Early->late in the HIGH-within-stay-CV subset (weakest persistence) = 0.347. VitalDB mirror (N small): ICC(1) log-dose = 0.211, fold-range = 6.25x, time-gapped early->late 0.375 at gap_ge_30min.

## Checks (MIMIC, primary)
- PASS -- icc_substantial(>=0.3)
- PASS -- between_patient_fold_range(>=2)
- PASS -- gap6h_survives(>=0.3)
- PASS -- null_collapses(|r|<=0.1)
- PASS -- within_stay_cv_nontrivial(>=0.15)
- PASS -- early_late_survives_high_cv(>=0.3)

(6/6 checks passed.)

## MIMIC-IV ICU (primary, N huge)
- Stays with norepi: **15949**; >=4 segments: **13585**.
- Baseline (reproduced) reliability split-half: {"r": 0.947, "n": 13585}; early->late adjacent: {"r": 0.617, "n": 13585}.

### Test 1 -- between- vs within-patient variance (ICC)
- ICC(1) of log-rate: **0.392** (between-patient SD 0.5681, within-patient SD 0.7072, 15137 stays).
- Between-patient requirement spread: {"p10": 0.03, "median": 0.08, "p90": 0.2797, "fold_range_p90_p10": 9.31, "between_patient_sd": 0.1391, "between_patient_sd_log": 0.7949, "n": 15949}.
  A real trait needs the variance to live BETWEEN patients (high ICC) and a wide between-patient fold-range. A near-constant signal with no between-patient spread would make reliability trivial.

### Test 2 -- TIME-GAPPED early->late (the decisive test)
- {"gap_ge_0h": {"r": 0.594, "n": 13585}, "gap_ge_1h": {"r": 0.588, "n": 13337}, "gap_ge_3h": {"r": 0.562, "n": 12566}, "gap_ge_6h": {"r": 0.508, "n": 11241}, "gap_ge_12h": {"r": 0.422, "n": 8910}, "gap_ge_24h": {"r": 0.296, "n": 5921}}
  Mechanical adjacent-sample stickiness decays as the gap grows; a genuine trait survives a multi-hour gap between the early window and the late window.

### Test 3 -- NULL / placebo (shuffle the patient link)
- Shuffled reliability: {"r": -0.012, "n": 13585}; shuffled early->late: {"r": 0.015, "n": 13585}.
- Mechanical yardstick: {"spearman_early_tercile_vs_late_tercile": {"r": 0.519, "n": 13585}, "frac_same_tercile": 0.551, "note": "coarse 3-level 'band membership' rank agreement -- a purely mechanical persistence yardstick to compare the continuous reliability against."}.
  Breaking the patient link must collapse the metric to ~0 (confirms it is not spuriously inflated by the estimator).

### Test 4 -- persistence-adjusted (within-stay dynamics)
- Within-stay rate CV: {"median": 0.51, "p25": 0.396, "p75": 0.66, "frac_cv_gt_0p2": 0.973, "frac_cv_gt_0p5": 0.52, "n": 13585, "note": "within-stay coefficient of variation of the norepi rate; CV~0 => trivially constant (mechanical); CV large => rate genuinely moves within the stay."}.
- Early->late split by within-stay CV: {"cv_threshold_median": 0.51, "high_cv": {"r": 0.347, "n": 6793}, "low_cv": {"r": 0.853, "n": 6792}, "note": "early->late split by within-stay CV. Survival in the HIGH-CV subset (rate moves a lot) is evidence the signal is a trait, not flatness."}.
  If the rate barely moves within a stay (CV~0) the reliability is trivially mechanical; if it moves a lot yet early still predicts late, it is a real trait.

## VitalDB (mirror, N small -- intraoperative stable epochs)
- Cases (norepi-only, >=2 epochs): **206**; >=4 epochs: **148**.
- Baseline reliability split-half: {"r": 0.79, "n": 148}; early->late adjacent: {"r": 0.528, "n": 148}.
- ICC(1) log-dose: {"icc1": 0.211, "var_between": 0.55393, "var_within": 2.06754, "between_sd": 0.7443, "within_sd": 1.4379, "n_groups": 206, "k0": 6.6, "msb": 5.72457, "msw": 2.06754}.
- Between-patient spread: {"p10": 0.0593, "median": 0.1787, "p90": 0.3706, "fold_range_p90_p10": 6.25, "between_patient_sd": 0.3459, "between_patient_sd_log": 0.8692, "n": 206}.
- Time-gapped early->late: {"gap_ge_0min": {"r": 0.51, "n": 148}, "gap_ge_10min": {"r": 0.499, "n": 148}, "gap_ge_20min": {"r": 0.435, "n": 141}, "gap_ge_30min": {"r": 0.375, "n": 133}, "gap_ge_45min": {"r": 0.287, "n": 117}}.
- Within-case CV: {"median": 0.524, "p25": 0.36, "p75": 0.685, "frac_cv_gt_0p2": 0.973, "n": 148}.
- Shuffle null reliability: {"r": -0.04, "n": 148}; early->late: {"r": 0.08, "n": 148}.
- Early->late high-CV subset: {"cv_threshold_median": 0.524, "high_cv": {"r": 0.417, "n": 74}, "low_cv": {"r": 0.693, "n": 74}}.

## Honest caveats
- ICC(1) on log-rate treats segments as exchangeable within a stay; serial autocorrelation means the effective within-stay N is smaller than the raw count, so the ICC is a lower bound on the between-patient share if anything.
- The time-gapped test reduces N (stays must span the gap); the reported r at large gaps is on the longer-stay subset, which is itself a selected population.
- The mechanical yardstick (tercile band membership) is a coarse control, not a ground-truth mechanical generator; it bounds, not proves, the persistence baseline.
- VitalDB is single-centre, small N, intra-operative (gaps are minutes not hours); it is a mirror, not an independent confirmation.
