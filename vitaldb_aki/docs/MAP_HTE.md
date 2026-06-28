# Personalized MAP Target -- Heterogeneous Treatment Effect (HTE)

## Interpretation & limitations (READ FIRST)

- **Observational, single-centre** (VitalDB / SNUH). MAP target was not
  randomised; **confounding by indication** is the central threat -- sicker /
  more unstable patients sustain deeper intraoperative hypotension AND are
  more likely to sustain organ injury, biasing the burden->injury estimate
  TOWARD harm.
- The HEADLINE is the **exposure x subgroup INTERACTION**: an interaction
  OR **> 1** means the hypotension-burden -> organ-injury association is
  **stronger** inside the right-shifted-autoregulation arm (chronic HTN /
  CKD / older) -- i.e. those patients are hypothesised to **need a higher
  MAP** while normotensive patients tolerate 65 (the INPRESS /
  individualized-BP-target controversy).
- Within-arm effects are IPTW-adjusted for the PREOP+INTRAOP confounder set
  `['age', 'sex_male', 'asa', 'preop_htn', 'preop_dm', 'baseline_cr', 'egfr_ckdepi', 'intraop_ebl', 'anesthesia_duration_min', 'surgery_duration_min', 'optype_code']`; the variable that DEFINES a subgroup is
  dropped from that subgroup's confounder set (never condition on the
  stratifier).
- **E-values** quantify how strong an unmeasured confounder would have to be
  (risk-ratio scale) to explain a within-arm result away. A small E-value
  (~1-1.5) means weak residual confounding could nullify the finding.
- **Negative control:** `organ_hepatocellular` -- intraoperative
  perfusion/management is not a plausible cause of hepatocellular injury;
  a non-null INTERACTION there flags residual confounding.
- **Power:** subgroup x outcome cells with < 15 events
  (right-shifted arm) are reported but marked **underpowered, hypothesis-only**.
- These are **HYPOTHESIS-GENERATING for a prospective trial**, not causal
  proof. **External validation on INSPIRE is pending.**
- Higher-threshold burden available and used: `map_auc_below_70, map_auc_below_75` (from the cached map-threshold extract).

## Cohort & exposure

- N cases = 4335; exposed (any MAP-AUC<65) = 3832.
- PRIMARY exposure = `map_auc_below_65` (continuous);
  dichotomized HIGH vs LOW at the median burden among exposed = 56.11 mmHg.min.
- Burden gradient columns: `map_auc_below_65, map_auc_below_60, map_auc_below_55, map_auc_below_50, map_auc_below_70, map_auc_below_75`.
- CKD definition: egfr_ckdepi < 60.0; age median split = 61 y.

## Subgroups (pre-specified)

- **htn** -- chronic hypertension (preop_htn=1 vs 0) (dropped from its confounder set: `['preop_htn']`).
- **ckd** -- CKD (egfr_ckdepi<60 vs >=60; fallback top baseline_cr tertile) (dropped from its confounder set: `['egfr_ckdepi', 'baseline_cr']`).
- **older** -- older age (age >= median vs <) (dropped from its confounder set: `['age']`).

## Findings (led by best-powered + strongest HTE)

### ckd -- CKD (egfr_ckdepi<60 vs >=60; fallback top baseline_cr tertile)
- Arm sizes: right-shifted n = 198, reference n = 3863.
- **composite:** interaction OR = 1.283 (p = 0.448). Within RIGHT-SHIFTED arm: high-vs-low burden RD = 0.0686 (95% CI -0.063 to 0.1921); RR = 1.317 (95% CI 0.7607 to 2.201). n = 193, events = 53.
  - Reference arm (for contrast): RD = 0.0143, RR = 1.104, n = 3772, events = 545.
  - E-value (right-shifted RR, point) = 1.962, E-value (CI) = 1.
  - Right-shifted-arm RR gradient across thresholds: <65: RR=1.317; <60: RR=1.318; <55: RR=1.546; <50: RR=1.596; <70: RR=1.273; <75: RR=1.145.
- **organ_renal:** interaction OR = 3.112 (p = 0.08). Within RIGHT-SHIFTED arm: high-vs-low burden RD = 0.0903 (95% CI 0.012 to 0.1689); RR = 3.673 (95% CI 1.148 to 14.7). n = 184, events = 16.
  - Reference arm (for contrast): RD = 0.0088, RR = 1.291, n = 3422, events = 118.
  - E-value (right-shifted RR, point) = 6.807, E-value (CI) = 1.561.
  - Right-shifted-arm RR gradient across thresholds: <65: RR=3.673; <60: RR=3.445; <55: RR=2.496; <50: RR=2.442; <70: RR=2.371; <75: RR=2.003.
- _Negative control (organ_hepatocellular):_ interaction OR = 1.674 (p = 0.4) -> null (reassuring).

### older -- older age (age >= median vs <)
- Arm sizes: right-shifted n = 2241, reference n = 2094.
- **composite:** interaction OR = 1.157 (p = 0.424). Within RIGHT-SHIFTED arm: high-vs-low burden RD = 0.029 (95% CI -0.0014 to 0.0598); RR = 1.205 (95% CI 0.9911 to 1.498). n = 2192, events = 350.
  - Reference arm (for contrast): RD = 0.0094, RR = 1.066, n = 2041, events = 299.
  - E-value (right-shifted RR, point) = 1.703, E-value (CI) = 1.
  - Right-shifted-arm RR gradient across thresholds: <65: RR=1.205; <60: RR=1.08; <55: RR=1.111; <50: RR=1.073; <70: RR=1.443; <75: RR=1.345.
- **organ_renal:** interaction OR = 0.9778 (p = 1). Within RIGHT-SHIFTED arm: high-vs-low burden RD = 0.016 (95% CI -0.0008 to 0.0329); RR = 1.505 (95% CI 0.9806 to 2.569). n = 2097, events = 81.
  - Reference arm (for contrast): RD = 0.0146, RR = 1.54, n = 1753, events = 61.
  - E-value (right-shifted RR, point) = 2.376, E-value (CI) = 1.
  - Right-shifted-arm RR gradient across thresholds: <65: RR=1.505; <60: RR=1.278; <55: RR=1.258; <50: RR=1.051; <70: RR=1.929; <75: RR=1.562.
- _Negative control (organ_hepatocellular):_ interaction OR = 1.25 (p = 0.532) -> null (reassuring).

### htn -- chronic hypertension (preop_htn=1 vs 0)
- Arm sizes: right-shifted n = 1401, reference n = 2934.
- **composite:** interaction OR = 0.8647 (p = 0.456). Within RIGHT-SHIFTED arm: high-vs-low burden RD = 0.0072 (95% CI -0.0356 to 0.0527); RR = 1.045 (95% CI 0.8137 to 1.389). n = 1370, events = 232.
  - Reference arm (for contrast): RD = 0.0247, RR = 1.184, n = 2863, events = 417.
  - E-value (right-shifted RR, point) = 1.262, E-value (CI) = 1.
  - Right-shifted-arm RR gradient across thresholds: <65: RR=1.045; <60: RR=0.9101; <55: RR=0.9619; <50: RR=0.9974; <70: RR=1.215; <75: RR=1.143.
- **organ_renal:** interaction OR = 1.075 (p = 0.876). Within RIGHT-SHIFTED arm: high-vs-low burden RD = 0.0211 (95% CI -0.0039 to 0.0459); RR = 1.548 (95% CI 0.9222 to 2.821). n = 1293, events = 66.
  - Reference arm (for contrast): RD = 0.0112, RR = 1.452, n = 2557, events = 76.
  - E-value (right-shifted RR, point) = 2.468, E-value (CI) = 1.
  - Right-shifted-arm RR gradient across thresholds: <65: RR=1.548; <60: RR=0.9048; <55: RR=1.128; <50: RR=0.9674; <70: RR=1.54; <75: RR=1.38.
- _Negative control (organ_hepatocellular):_ interaction OR = 0.8748 (p = 0.78) -> null (reassuring).

## Methods (brief)

- Cohort: `feature_matrix.csv` merged with `cohort_composite.csv` outcomes
  (only columns not already present). Subgroup indicators + the dichotomized
  high-burden exposure derived from preop / intraop columns only.
- Exposure: PRIMARY = `map_auc_below_65` (continuous); dichotomized HIGH vs
  LOW at the median burden among exposed (burden==0 -> low reference). The
  burden gradient re-dichotomizes each successive AUC threshold.
- IPTW: stabilised, 1%-trimmed weights from a logistic propensity model
  (reused from `hypotension_treatment.py`), refit per subgroup (the
  stratifier variable dropped from the PS covariates).
- PRIMARY model: IPTW-weighted logistic outcome model with an
  exposure x subgroup interaction term; interaction OR > 1 = stronger
  hypotension->injury association in the right-shifted arm.
- Within-arm RD/RR: IPTW-weighted arm risks; 95% CI by nonparametric
  percentile bootstrap (weights fixed).
- E-value: VanderWeele & Ding (2017), point + null-nearest CI bound.
- Multiplicity: Benjamini-Hochberg FDR across the subgroup x primary-outcome
  interaction tests.

---
*Generated by vitaldb_aki/analysis/map_hte.py*
