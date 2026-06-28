# Recovery Velocity -- Specificity & Robustness De-risking

## READ FIRST -- what this document does and its limitations

This is a **de-risking / falsification** analysis of the recovery-velocity finding in `docs/RECOVERY_VELOCITY.md` (raw-MAP per-episode recovery velocity adds incremental discrimination for organ injury over static hypotension burden: COMPOSITE dAUROC +0.079, DeLong p=2.6e-9). It does **not** re-establish the finding; it stress-tests TWO specific threats:

1. **Non-specificity:** the negative control `organ_hepatocellular` ALSO showed incremental AUROC (+0.047, p=0.053), so part of the signal may be a generic 'unstable/sick patient' axis rather than perfusion-recovery-specific.

2. **Severity confounding:** the UNADJUSTED quartile dose-response of the primary feature `rv_depthwt_slope` was non-monotone / anti-hypothesis; only burden+covariate-adjusted models showed the hypothesised direction.

**Limitations (unchanged from the parent screen):** observational, single-centre (VitalDB/SNUH); confounding by indication remains; cohort = cases with a recovered MAP<65 episode; hypothesis-generating; external replication on INSPIRE pending. The IPTW/within-stratum directions point the *surprising* way (faster/better measured recovery -> MORE injury after adjustment), which is itself most consistent with residual confounding by episode severity / reverse causation, and is flagged below.

**Cohort N = 3743**, seed 20260626, difference-bootstrap N = 600 (reduced from the parent's 2000 because each resample refits a full paired-OOF model per control on a loaded box; CIs remain tight at the dAUROC-difference scale).


## VERDICT (candid)

**MIXED -- discriminates within burden but NOT clearly distinguishable from generic-severity controls**

- Composite's incremental dAUROC significantly exceeds **0 of 4** negative controls (CI-lower>0): none.
- Within-burden-stratum pooled survivors (p<0.05): ['rv_median_tau'].
- Survives a generic-severity proxy baseline (n_episodes+burden+map_lowest+duration): **False**.


## (1) Negative-control panel + composite-exceeds-control test

Incremental dAUROC of the recovery-feature SET over the static-burden baseline, per outcome (DeLong on shared grouped OOF folds):

| outcome | dAUROC | DeLong p |
|---|---|---|
| composite | +0.0790 | 2.63e-09 |
| organ_hepatocellular | +0.0466 | 0.0531 |
| organ_cholestatic | +0.0532 | 0.0323 |
| organ_coagulation_inr | +0.0134 | 0.574 |
| organ_coagulation_plt | +0.0488 | 0.00254 |

Formal specificity test -- bootstrap of the DIFFERENCE of paired dAUROCs (composite - control) on the SHARED cases/folds. `exceeds=YES` iff the 95% CI lower bound > 0:

| control | dAUROC diff (comp-ctrl) | 95% CI | exceeds? | 1-sided p |
|---|---|---|---|---|
| organ_hepatocellular | +0.0359 | [-0.0006, +0.0742] | no | 0.0267 |
| organ_cholestatic | +0.0053 | [-0.0406, +0.0471] | no | 0.402 |
| organ_coagulation_inr | +0.0143 | [-0.0236, +0.0547] | no | 0.255 |
| organ_coagulation_plt | +0.0265 | [-0.0008, +0.0558] | no | 0.0317 |

Interpretation: if composite does NOT clearly exceed the controls, the incremental recovery signal is largely a **generic severity** axis shared by outcomes that MAP-recovery dynamics should not mechanistically drive.


## (2) Within-burden-stratum test ('at matched burden')

Stratified by static-burden quartile (`map_auc_below_65`). Per-SD logistic OR of the ORIENTED clean feature (larger = faster/better recovery) on composite, WITHIN each stratum, plus an inverse-variance pooled estimate. **OR>1 means faster/better measured recovery -> MORE injury at matched burden** (the screen's post-adjustment direction).

- `rv_min_slope`: pooled OR/SD = **0.9761** (95% CI [0.8821, 1.0802]), p = 0.64, E-value(point) = 1.183, E-value(CI) = 1.0; heterogeneity Cochran-Q p = 0.9208894025845659 (n strata used 4).
- `rv_median_tau`: pooled OR/SD = **1.2164** (95% CI [1.0346, 1.43]), p = 0.0177, E-value(point) = 1.729, E-value(CI) = 1.224; heterogeneity Cochran-Q p = 0.17723359860029653 (n strata used 4).

If recovery velocity still discriminates injury WITHIN burden strata, it is not *merely* burden re-expressed. NOTE: a within-stratum OR>1 (faster recovery -> more injury) is the anti-hypothesis sign and most plausibly reflects residual severity confounding within the stratum, not protection.


## (3) Severity-confounding diagnostics

Severity axes: ['burden', 'n_episodes', 'duration']. For each recovery feature: max |Spearman r| with those axes, and the univariate per-SD oriented OR on composite.

| feature | max abs r (severity) | univ OR/SD (oriented) | univ p |
|---|---|---|---|
| rv_depthwt_slope | 0.310 | 0.9404 | 0.20241725103429065 |
| rv_min_slope | 0.441 | 0.9066 | 0.06606367599689052 |
| rv_median_slope | 0.238 | 0.9674 | 0.4743219141109909 |
| rv_max_time_to_recover | 0.648 | 0.957 | 0.2999554858468607 |
| rv_frac_unrecovered | 0.228 | 1.2711 | 1.0836388087056277e-05 |
| rv_total_unrecovered_min | 0.344 | 0.9003 | 0.003202991167001273 |
| rv_median_tau | 0.307 | 1.4184 | 0.013182930335717644 |
| rv_n_episodes | 0.639 | 0.6058 | 2.721830321362209e-33 |

**Cleanest least-severity-confounded yet injury-associated feature: `rv_frac_unrecovered`** (min max|Spearman r| with {burden, n_episodes, duration} among features with univariate p<0.05).

Within-burden-stratum quartile dose-response of the cleanest feature (does the anti-hypothesis raw pattern flip once burden is matched?):

- burden stratum 0: rates slow->fast [0.0983, 0.1197, 0.1325, 0.1795] (n [234, 234, 234, 234]) -> ANTI-hypothesis (rate rises slow->fast)
- burden stratum 1: rates slow->fast [0.1111, 0.0983, 0.1496, 0.1581] (n [234, 234, 234, 234]) -> ANTI-hypothesis (rate rises slow->fast)
- burden stratum 2: rates slow->fast [0.094, 0.1496, 0.2017, 0.141] (n [234, 234, 233, 234]) -> ANTI-hypothesis (rate rises slow->fast)
- burden stratum 3: rates slow->fast [0.1752, 0.2479, 0.3248, 0.1795] (n [234, 234, 234, 234]) -> ANTI-hypothesis (rate rises slow->fast)

For reference, the same within-stratum dose-response of the PRIMARY feature `rv_depthwt_slope` (whose RAW quartile pattern was anti-hypothesis):

- burden stratum 0: rates slow->fast [0.1154, 0.1282, 0.1624, 0.1239] -> ANTI-hypothesis (rate rises slow->fast)
- burden stratum 1: rates slow->fast [0.0641, 0.1581, 0.1368, 0.1581] -> ANTI-hypothesis (rate rises slow->fast)
- burden stratum 2: rates slow->fast [0.0897, 0.1752, 0.176, 0.1453] -> ANTI-hypothesis (rate rises slow->fast)
- burden stratum 3: rates slow->fast [0.1282, 0.2308, 0.3291, 0.2393] -> ANTI-hypothesis (rate rises slow->fast)

## (4) Incremental over a generic-severity proxy

Baseline = severity proxy `['rv_n_episodes', 'map_auc_below_65', 'map_lowest', 'anesthesia_duration_min']` (AUROC 0.6642). Adding the recovery features: AUROC -> 0.6773; **dAUROC = +0.0132** (95% CI [-0.0002, 0.0263]), DeLong p = 0.0515.

If recovery velocity were just generic severity, this incremental signal over an explicit severity proxy should largely vanish.


## (5) BH-FDR across the new specificity tests

0/7 survive BH at q<0.05.

| family | label | p | survives |
|---|---|---|---|
| composite_exceeds | organ_hepatocellular | 0.0267 | False |
| composite_exceeds | organ_cholestatic | 0.402 | False |
| composite_exceeds | organ_coagulation_inr | 0.255 | False |
| composite_exceeds | organ_coagulation_plt | 0.0317 | False |
| within_stratum_pooled | rv_min_slope | 0.64 | False |
| within_stratum_pooled | rv_median_tau | 0.0177 | False |
| incremental_over_severity_proxy | composite | 0.0515 | False |

## Methods (brief)

- Reuses `reperfusion_dynamics` (load_merged, incremental_auroc, _paired_oof_logistic, static-burden baseline, preop covariates), `models.metrics` (DeLong + cluster bootstrap), and `actionable_targets` (E-value, BH-FDR). Difference-of-dAUROC: both outcomes fit on the SAME StratifiedGroupKFold folds and the SAME shared cases, then a patient-cluster bootstrap of (dAUROC_composite - dAUROC_control).
- Within-stratum: static-burden quartiles; per-SD logistic OR within each; inverse-variance pooling + Cochran-Q heterogeneity; E-value on the pooled OR.
- Leakage firewall: all predictors preop+intraop; organ_* only as outcomes. Seed 20260626.

---
*Generated by vitaldb_aki/analysis/recovery_velocity_specificity.py*
