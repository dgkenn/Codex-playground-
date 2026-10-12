# Persistent vs Transient AKI -- Prognostic Enrichment

## Interpretation & limitations (READ FIRST)

- **Small N, hypothesis-generating only.** Persistent AKI **N = 41** vs transient N = 94 (indeterminate N = 8 excluded). With 41 events the penalised logistic is **underpowered**; ORs are reported **per SD** with **wide bootstrap CIs** and must not be over-interpreted.
- **No correction survives strongly.** BH-FDR is applied across the predictor p-values, but with this N the study is exploratory: treat any 'FDR-reject' flag as a lead for a prospective study, not a confirmed effect.
- **Observational, single-centre** (VitalDB / SNUH). Confounding by indication is the central threat: persistent non-recovery may reflect sicker patients rather than any single intraoperative exposure.
- **Leakage firewall.** Predictors are PREOP+INTRAOP only. The trajectory label is derived from POSTOP creatinine and is used **only as the outcome (y)**. Only `baseline_cr` (preop) enters the predictor set; peak/recovery creatinine (postop) are never predictors.

## Trajectory definitions (from `aki_trajectory_summary.json`)

- **AKI+** = met KDIGO creatinine criteria within 168.0 h.
- **Transient** = recovered within the **24.0-72.0 h** window (< 1.5x baseline AND within 0.3 mg/dL of baseline).
- **Persistent** = AKI+ that did NOT recover in that window (prognostically important -> CKD).
- **Indeterminate** = AKI+ but no creatinine measured in the recovery window (cannot adjudicate) -> **excluded** from the persistent-vs-transient model.

## Q1. Predictors of NON-recovery (persistent vs transient, AKI+)

- Model: L2-penalised logistic (C=1.0), per-SD standardised predictors. Outcome: persistent (1) vs transient (0), among AKI+. N = 111 (persistent 33, transient 78).
- optype reference level = `Others`; dummies = ['Colorectal', 'Biliary/Pancreas', 'Major resection'].

Ranked by |effect| (OR per SD of standardised predictor):

- **baseline_cr**: OR/SD = 0.45 (95% CI 0.30 to 0.82); p = 0.016
- **egfr_ckdepi**: OR/SD = 0.52 (95% CI 0.25 to 1.13); p = 0.104
- **map_auc_below_65**: OR/SD = 0.56 (95% CI 0.31 to 1.45); p = 0.268
- **surgery_duration_min**: OR/SD = 0.64 (95% CI 0.37 to 1.11); p = 0.114
- **map_min_below_65**: OR/SD = 1.52 (95% CI 0.66 to 2.82); p = 0.390
- **intraop_ebl**: OR/SD = 1.47 (95% CI 0.55 to 2.49); p = 0.498
- **optype__Biliary/Pancreas**: OR/SD = 0.82 (95% CI 0.40 to 1.31); p = 0.250
- **preop_dm**: OR/SD = 0.85 (95% CI 0.46 to 1.39); p = 0.516
- **anesthesia_duration_min**: OR/SD = 0.86 (95% CI 0.47 to 1.38); p = 0.418
- **sex_male**: OR/SD = 0.89 (95% CI 0.54 to 1.37); p = 0.548
- **map_lowest**: OR/SD = 1.12 (95% CI 0.64 to 1.96); p = 0.708
- **preop_htn**: OR/SD = 1.12 (95% CI 0.69 to 1.81); p = 0.698
- **asa**: OR/SD = 1.09 (95% CI 0.62 to 1.94); p = 0.802
- **optype__Major resection**: OR/SD = 0.96 (95% CI 0.51 to 1.58); p = 0.824
- **age**: OR/SD = 0.96 (95% CI 0.59 to 1.91); p = 0.986
- **optype__Colorectal**: OR/SD = 1.03 (95% CI 0.56 to 1.83); p = 0.958

## Q2. Does hypotension burden discriminate PERSISTENT more strongly?

For each burden column: OR per SD + AUROC for `persistent vs no-AKI` and `transient vs no-AKI`. A LARGER persistent OR/AUROC = the primary hemodynamic signal tracks the prognostically important phenotype.

### `map_auc_below_65`
- persistent vs no-AKI (n+=41, n-=4091): OR/SD = 1.18 (95% CI 1.01-1.38); AUROC = 0.58 (95% CI 0.49-0.67)
- transient vs no-AKI (n+=93, n-=4091): OR/SD = 1.35 (95% CI 1.17-1.63); AUROC = 0.66 (95% CI 0.60-0.71)
- **stronger for persistent = False** (delta OR/SD = -0.17, delta AUROC = -0.08)

### `map_lowest`
- persistent vs no-AKI (n+=41, n-=4091): OR/SD = 0.98 (95% CI 0.69-1.28); AUROC = 0.50 (95% CI 0.48-0.59)
- transient vs no-AKI (n+=93, n-=4091): OR/SD = 0.74 (95% CI 0.58-0.90); AUROC = 0.57 (95% CI 0.51-0.62)
- **stronger for persistent = False** (delta OR/SD = +0.24, delta AUROC = -0.07)

### `map_min_below_65`
- persistent vs no-AKI (n+=41, n-=4091): OR/SD = 1.22 (95% CI 1.03-1.43); AUROC = 0.59 (95% CI 0.50-0.68)
- transient vs no-AKI (n+=93, n-=4091): OR/SD = 1.40 (95% CI 1.24-1.64); AUROC = 0.66 (95% CI 0.61-0.72)
- **stronger for persistent = False** (delta OR/SD = -0.18, delta AUROC = -0.08)

## Q3. Baseline + intraop characteristics (transient vs persistent)

| feature | transient mean (sd), n | persistent mean (sd), n |
| --- | --- | --- |
| baseline_cr | 0.985 (0.702), n=87 | 0.953 (0.431), n=41 |
| egfr_ckdepi | 91.2 (25.5), n=87 | 85.6 (26.3), n=41 |
| age | 61.2 (12), n=94 | 63.7 (11.9), n=41 |
| asa | 2.29 (0.806), n=92 | 2.49 (0.746), n=41 |
| preop_htn | 0.426 (0.497), n=94 | 0.537 (0.505), n=41 |
| preop_dm | 0.202 (0.404), n=94 | 0.195 (0.401), n=41 |
| intraop_ebl | 825 (1.49e+03), n=84 | 932 (2.4e+03), n=33 |
| anesthesia_duration_min | 303 (163), n=94 | 219 (111), n=41 |
| surgery_duration_min | 236 (149), n=94 | 157 (105), n=41 |
| map_auc_below_65 | 188 (244), n=93 | 134 (163), n=41 |
| map_lowest | 32.4 (14.1), n=93 | 37 (18.1), n=41 |
| map_min_below_65 | 28.1 (31.4), n=93 | 20.7 (23.2), n=41 |

## Methods (brief)

- Join `aki_trajectory.csv` (trajectory label) to `feature_matrix.csv` on `caseid`. AKI+ = present in trajectory file; no-AKI = remaining matrix cases.
- Q1: complete-case L2-penalised logistic (sklearn, C=1.0) of persistent (1) vs transient (0) on standardised PREOP+INTRAOP predictors + optype dummies; ORs per SD; 95% CIs + two-sided p from a 1000-rep case-resampling bootstrap; BH-FDR across predictors.
- Q2: per burden column, unpenalised univariate logistic of trajectory-vs-no-AKI on standardised burden; OR per SD + AUROC with bootstrap CIs; head-to-head flag if persistent OR AND AUROC both exceed transient.
- Seed = 20260626 (config.yaml).

---
*Generated by `vitaldb_aki/analysis/aki_persistence.py`*
