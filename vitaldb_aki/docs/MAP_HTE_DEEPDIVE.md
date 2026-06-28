# Personalized MAP Target in CKD -- Deep Dive (powered re-test)

## Interpretation & limitations (READ FIRST)

- **Observational, single-centre** (VitalDB / SNUH). MAP target was not
  randomised; **confounding by indication** is the central threat -- sicker /
  more unstable patients sustain deeper intraoperative hypotension AND are
  more likely to sustain renal injury, biasing the burden->injury estimate
  TOWARD harm. This deep-dive sharpens the estimand and the power; it does
  NOT remove that threat.
- **What is new vs `docs/MAP_HTE.md`:** the headline is now a **CONTINUOUS**
  burden(z) x **CONTINUOUS** eGFR(z) interaction in an IPTW-weighted logistic
  model. It uses **all renal events**, not just the ~16 inside the
  dichotomized CKD cell, so it is the *powered* version of the subgroup
  signal. A **NEGATIVE** interaction coefficient = burden-harm rises as eGFR
  falls = the direction the personalized-MAP-target hypothesis predicts.
- The **shifted-threshold** analysis is the clinical headline: at what MAP do
  CKD patients begin accruing **excess** renal risk vs non-CKD? Burden below a
  HIGHER MAP mattering in CKD but not non-CKD = the CKD risk curve is shifted
  toward a higher MAP target.
- IPTW-adjusted for the PREOP+INTRAOP confounder set `['age', 'sex_male', 'asa', 'preop_htn', 'preop_dm', 'baseline_cr', 'intraop_ebl', 'anesthesia_duration_min', 'surgery_duration_min', 'optype_code']`;
  the eGFR / CKD axis that DEFINES the modifier is dropped from the IPTW
  propensity block (never weight by the stratifier); `baseline_cr` is retained.
- **E-values** quantify how strong an unmeasured confounder would have to be
  (risk-ratio scale) to explain a within-stratum result away.
- **Negative control:** `organ_hepatocellular` -- a non-null
  burden x eGFR interaction there would flag residual confounding.
- **Power:** strata / cells with < 15 events are
  reported but flagged **underpowered, hypothesis-only**.
- These remain **HYPOTHESIS-GENERATING for a prospective trial**, not causal
  proof. The remaining limits are explicit: **single-centre, observational,
  confounding-by-indication**, the deepest-MAP/highest-eGFR cells are thin,
  and the spline divergence point is a modelled estimate. **External
  replication of the replication-target `personalized_map_target_hte` on
  INSPIRE is pre-registered in `analysis/external_validation.py`.**

## VERDICT (candid)

- **The powered continuous burden x eGFR interaction did NOT strengthen the finding.** With all 116 renal events (vs ~16 in the CKD cell), the continuous interaction coefficient is 0.033 (p 0.6067), the wrong SIGN for the hypothesis, and does NOT survive BH-FDR. The implied per-SD burden OR actually *falls* as eGFR falls (eGFR 90 -> 30). So the headline power-gain test is NULL: the apparent CKD-specific harm does not generalise to a smooth eGFR x burden effect across the whole cohort.
- **BUT the subgroup picture is internally consistent and non-trivial.** The within-CKD high-vs-low burden RR stays ~2.8-3.6 and EXCEEDS non-CKD at every MAP threshold (excess at all 65/70/75 = True); the eGFR-severity strata show the largest (if underpowered) RR at eGFR<60 (RR ~3.3-3.7, 7-9 events/stratum); the Cochran-Armitage trend of high-burden renal rate across eGFR severity is suggestive (z 1.912, p 0.0558); the negative control stayed null (True).
- **Why the discrepancy?** The CKD signal is concentrated in a thin tail (eGFR<60, n~184, 16 events) and is NOT a smooth gradient: eGFR 60-90 shows little excess (RR 1.14) while eGFR>=90 shows a modest one (RR 1.35), so a single linear burden x eGFR term -- the powered estimand -- averages the tail away. A continuous binary-CKD(<60) x burden interaction is weakly positive (coef 0.0344, p 0.26) but egfr<45 and the creatinine-tertile axis are null/negative -- the effect does not replicate across CKD definitions.
- **Bottom line:** the personalized-MAP-target-in-CKD finding is **NOT strengthened** by the powered analysis; if anything it is partially **falsified** as a smooth dose-response, while surviving only as a thin, underpowered, definition-sensitive subgroup association. The clean negative control and the directionally-consistent shifted-threshold pattern keep it alive as a hypothesis, but it should be carried to INSPIRE replication as EXPLORATORY, not promoted. Honest reporting > a tidier headline.

## Cohort

- N cases = 4335; exposed (any MAP-AUC<65) = 3832.
- CKD definition (primary): egfr_ckdepi < 60.0.
- Higher-threshold burden available: `map_auc_below_70, map_auc_below_75`.

## 1. Powered continuous burden x eGFR interaction (THE POWER GAIN)

- **organ_renal:** interaction coefficient (burden_z x eGFR_z) = **0.033** (95% CI -0.1072 to 0.192; p = **0.6067**, not FDR-significant). n = 2589, events = 116.
  - Observed sign: **positive** (predicted: negative (harm rises as eGFR falls)); consistent with hypothesis = **False**.
  - Implied burden-slope OR per +1 SD burden, by eGFR anchor:
    - eGFR 90: OR/SD = 1.203 (logit slope 0.1847).
    - eGFR 60: OR/SD = 1.139 (logit slope 0.13).
    - eGFR 45: OR/SD = 1.108 (logit slope 0.1026).
    - eGFR 30: OR/SD = 1.078 (logit slope 0.0752).
  - Reading: a NEGATIVE coefficient + a steeper burden-slope OR at lower eGFR would be the dichotomized CKD subgroup signal generalised to all renal events. Here the coefficient is ~0 / wrong-signed and the implied slope does NOT steepen as eGFR falls -- the powered test does not reproduce the subgroup signal (see VERDICT).
- **composite (secondary):** interaction = 0.0007 (p = 1); sign = positive.
- _Negative control (organ_hepatocellular):_ interaction = -0.0891 (p = 0.2067) -> null (reassuring).

## 2. eGFR severity gradient (dose-response of the HTE)

- **eGFR >= 90:** high-vs-low burden RR = 1.348 (95% CI 0.8678 to 2.214); E-value 2.033; n = 2314, events = 87.
- **eGFR 60-90:** high-vs-low burden RR = 1.141 (95% CI 0.4981 to 2.68); E-value 1.542; n = 1108, events = 31.
- **eGFR 45-60:** high-vs-low burden RR = 3.731 (95% CI 0.7053 to 6.251); E-value 6.924; n = 112, events = 7. [UNDERPOWERED]
- **eGFR < 45:** high-vs-low burden RR = 3.283 (95% CI 0.6606 to 10.31); E-value 6.02; n = 72, events = 9. [UNDERPOWERED]
- **eGFR < 60 (combined CKD):** high-vs-low burden RR = 3.644 (95% CI 0.9973 to 16.24); E-value 6.748; n = 184, events = 16.
- RR by severity (normal->severe): [1.348, 1.141, 3.7313, 3.2827]; monotone increasing as eGFR falls = **False**.
- Cochran-Armitage trend (high-burden renal rate across eGFR severity): z = 1.912, p = 0.0558 (renal rate rises as eGFR falls).

## 3. Shifted-threshold headline (the individualized MAP target)

- **MAP < 65:** CKD RR = 3.644 (95% CI 0.9973 to 16.24, events 16); non-CKD RR = 1.292 (events 118); CKD/non-CKD RR ratio = 2.821; E-value(CKD) = 6.748; CKD excess = True.
- **MAP < 70:** CKD RR = 2.907 (95% CI 0.9691 to 14.39, events 16); non-CKD RR = 1.483 (events 118); CKD/non-CKD RR ratio = 1.96; E-value(CKD) = 5.262; CKD excess = True.
- **MAP < 75:** CKD RR = 2.768 (95% CI 0.9648 to 13.55, events 16); non-CKD RR = 1.305 (events 118); CKD/non-CKD RR ratio = 2.121; E-value(CKD) = 4.98; CKD excess = True.

- **DIRECTIONAL HEADLINE (hypothesis-only):** CKD patients show excess renal risk from hypotension below MAP 75 mmHg, vs non-CKD whose excess appears only at deeper thresholds -- the CKD risk curve is shifted toward a higher MAP target.
  - CAVEAT: every CKD cell here is the SAME thin 16-event stratum (the CI includes 1 at all thresholds), so 'CKD excess at MAP<75' is suggestive DIRECTION, not a confirmed higher target. The powered continuous test (section 1) did not corroborate a smooth shift.
- **map_lowest spline (RCS, knots [50.0, 60.0, 70.0, 80.0]):** CKD predicted renal risk exceeds non-CKD (by >=1 abs pp) once the lowest MAP drops below ~60 mmHg; non-CKD risk only rises at lower MAP.
  - CAVEAT: the CKD spline is FRAGILE -- only ~9 CKD cases have lowest MAP > 65 (near-zero events), so the curve extrapolates to ~0 risk there and the divergence is driven by one [60,65] bin (2/10 events). Read the binned rates, not the spline point estimate, as the honest figure.
- Binned renal rates vs lowest MAP per arm are in `cache/map_hte_deepdive_results.json` (`shifted_threshold.maplowest_curve_by_ckd.binned_rates`), the personalized-target figure in tabular form.

## 4. Robustness / falsification

- **Confounder-set sensitivity:** full coef 0.033 (p 0.6067) vs minimal coef 0.144 (p 0); sign stable = True.
- **Alternative CKD cutoffs (burden_z x binary-CKD interaction; harm-in-CKD => positive coef):**
  - egfr_lt60: coef = 0.0344 (OR 1.035, p 0.26, n_CKD 198); consistent with harm-in-CKD = True.
  - egfr_lt45: coef = -0.0056 (OR 0.9945, p 0.8867, n_CKD 75); consistent with harm-in-CKD = False.
  - cr_top_tertile: coef = -0.0743 (OR 0.9284, p 0.44, n_CKD 1388); consistent with harm-in-CKD = False.
- **Bootstrap stability:** renal interaction 95% CI [-0.1072, 0.192]; entirely-negative (stable harm-rises-as-eGFR-falls sign) = False.
- **Negative control:** organ_hepatocellular interaction coef -0.0891 (p 0.2067) -> stayed null = True.
- **BH-FDR (primary continuous interactions, renal + composite):** renal fdr_reject = False (p 0.6067).

## Methods (brief)

- Cohort: `feature_matrix.csv` merged with `cohort_composite.csv` outcomes
  (only columns not already present) + higher-threshold MAP burden
  (`map_auc_below_70/75`) merged from `cache/map_thresholds.csv`. No
  extraction/download is run. Reuses `map_hte.build_cohort`.
- **Continuous interaction:** IPTW-weighted logistic outcome model with a
  continuous burden(z) x continuous eGFR(z) term + the confounder block;
  burden dichotomized at its exposed-median ONLY to reuse the validated
  binary IPTW machinery (`hypotension_treatment.fit_propensity_model` /
  `compute_iptw_weights`), then those stabilised weights applied to the
  continuous-term model. eGFR is the modifier, dropped from the PS block.
  Interaction p + CI by two-sided nonparametric bootstrap of the coefficient.
- **eGFR gradient:** within-stratum IPTW high-vs-low burden RR (fixed
  weights), bootstrap CI; Cochran-Armitage trend of the high-burden renal
  rate across the ordinal eGFR-severity score.
- **Shifted threshold:** high-burden rebuilt at each AUC-below-threshold
  (65/70/75); within-CKD vs within-non-CKD IPTW RR; map_lowest RCS spline
  (statsmodels GLM + patsy `cr()`, knots [50,60,70,80]) + fine binned rates
  per CKD arm.
- E-value: VanderWeele & Ding (2017). Multiplicity: Benjamini-Hochberg FDR
  across the primary continuous-interaction tests (renal + composite).
- Leakage firewall: all confounders / modifiers are PREOP+INTRAOP; postop
  `organ_*` / `composite` are outcomes, never features.

---
*Generated by vitaldb_aki/analysis/map_hte_deepdive.py*
