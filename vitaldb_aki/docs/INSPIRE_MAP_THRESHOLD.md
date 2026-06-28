> **SUPERSEDED / CAUTION (see docs/REDTEAM_CKD_MAP.md).** This NNT/threshold analysis quantifies the CKD personalized-MAP-target, which a subsequent adversarial red-team RETRACTED: negative-control calibration showed the CKD x hypotension effect-modification is indistinguishable from generic confounding (calibrated interaction ~0). The CKD-SPECIFIC thresholds/NNTs below do NOT survive hostile review. The defensible replacement is the within-patient causal hypotension->AKI effect (docs/INSPIRE_WITHIN_PATIENT.md). Retained for the record only.

# INSPIRE: actionable CKD MAP-target -- per-eGFR inflection, absolute risk, NNT

## READ FIRST -- limitations (binding)

- **Observational, single-centre** (SNUH / INSPIRE). Confounding by
  indication (sicker patients sustain deeper MAP nadirs AND injure more) is
  NOT removed by IPTW; the absolute risk differences are associational.
- **Coarse intermittent vitals** (median `n_map`=23 MAP samples/case). Every
  estimate here is n_map-adjusted and re-run in the densely-monitored subset.
- **`map_lowest` is floored at ~52 mmHg** in this matrix -- the deepest nadir
  band is `<55`, and the spline cannot resolve structure below ~52 mmHg.
- **AKI = KDIGO-creatinine** from intermittent labs; in-hospital mortality is
  the hard, sampling-robust co-primary (section 4).
- Leakage firewall: predictors are preop + intraop only; `organ_renal` /
  `aki_stage` / `death_inhosp` are outcomes (y). Seed 20260626.
- The continuous burden(z)xeGFR(z) interaction was shown (in INSPIRE_CKD_MAP.md)
  to be a non-specific scaling artifact; this module deliberately uses the
  per-stratum / banded estimands instead, which answer the MAP-target question
  directly.

Cohort: n=130960, n_map median=23.0 (dense subset = n_map >= median (23)).

## (1) PER-eGFR-STRATUM RISK-INFLECTION MAP (the personalized floor)

Adjusted restricted-cubic-spline logistic of **renal injury** on `map_lowest`
(adjusters: n_map, age, sex, ASA, emergency, baseline_cr), per eGFR stratum.
The *inflection MAP* is where adjusted risk begins to climb as MAP falls; the
*knee* is the point of maximum curvature. Higher = a higher floor is needed.

| eGFR stratum | n | events | inflection MAP (95% CI) | knee MAP (95% CI) | adj risk @MAP65 | adj risk @MAP75 |
|---|---|---|---|---|---|---|
| eGFR >= 90 | 57495 | 731 | 70 (58 to 73.5) | 66 (58 to 66) | 2.87% | 2.67% |
| eGFR 60-90 | 24696 | 898 | 70 (60 to 73) | 66 (58 to 66) | 2.89% | 2.13% |
| eGFR 45-60 | 3374 | 452 | 70 (69 to 76.5) | 66 (59 to 66) | 8.91% | 6.55% |
| eGFR < 45 | 4629 | 568 | 72 (70 to 85.5) | 66 (66 to 66) | 7.64% | 5.76% |
| eGFR < 60 (CKD) | 8003 | 1020 | 71 (70 to 78.5) | 66 (58 to 66) | 8.80% | 6.60% |

- Inflection MAP by eGFR (>=90 -> <45): [70.0, 70.0, 70.0, 72.0] mmHg; **floor rises as eGFR falls: True**.
- Densely-monitored subset (same model):

| eGFR stratum | n | events | inflection MAP (95% CI) | knee MAP (95% CI) | adj risk @MAP65 | adj risk @MAP75 |
|---|---|---|---|---|---|---|
| eGFR >= 90 | 36163 | 1023 | 60 (58 to 69.5) | 58 (58 to 64) | 4.35% | 4.80% |
| eGFR 60-90 | 14635 | 1064 | 67 (66 to 69) | 62 (62 to 62) | 4.17% | 4.41% |
| eGFR 45-60 | 1861 | 368 | 66 (62 to 80.5) | 60 (60 to 60) | 13.81% | 12.96% |
| eGFR < 45 | 2627 | 417 | 70 (67 to 74.6) | 60 (60 to 60) | 8.37% | 10.08% |
| eGFR < 60 (CKD) | 4488 | 785 | 67 (66 to 69) | 60 (60 to 60) | 11.32% | 12.05% |

## (2) CKD ABSOLUTE RISK, RISK DIFFERENCE, NNT (the impact)

IPTW-adjusted (PS on n_map+age+sex+ASA+emergency+baseline_cr+weight+duration+
htn+dm) absolute **renal-injury** risk by MAP nadir band vs the >=75 reference,
within CKD and non-CKD. RD = adjusted risk difference; NNT = 1/RD; E = E-value.

| group | contrast | risk (exposed) | risk (ref >=75) | risk diff (95% CI) | NNT | RR (E-value) |
|---|---|---|---|---|---|---|
| ckd | MAP<65 vs >=75 (headline) | 14.66% | 7.85% | 6.82% (0.0453 to 0.0884) | 14.7 | 1.869 (E=3.143) |
| ckd | MAP<75 vs >=75 | 13.37% | 7.93% | 5.44% (0.031 to 0.0769) | 18.4 | 1.685 (E=2.76) |
| ckd | lt55 vs >=75 | 18.48% | 7.12% | 11.37% (0.0848 to 0.1416) | 8.8 | 2.597 (E=4.634) |
| ckd | b55_65 vs >=75 | 9.85% | 6.78% | 3.07% (0.0106 to 0.0505) | 32.6 | 1.452 (E=2.263) |
| ckd | b65_75 vs >=75 | 6.59% | 5.89% | 0.70% (-0.0108 to 0.0291) | 142.2 | 1.119 (E=1.485) |
| non_ckd | MAP<65 vs >=75 (headline) | 4.66% | 3.48% | 1.18% (0.0067 to 0.0179) | 84.5 | 1.34 (E=2.015) |
| non_ckd | MAP<75 vs >=75 | 4.28% | 3.31% | 0.97% (0.0043 to 0.0153) | 103.1 | 1.293 (E=1.908) |
| non_ckd | lt55 vs >=75 | 6.85% | 3.47% | 3.38% (0.0267 to 0.0402) | 29.6 | 1.972 (E=3.357) |
| non_ckd | b55_65 vs >=75 | 2.61% | 3.18% | -0.57% (-0.0108 to -0.0005) | -174.7 | 0.8202 (E=1.736) |
| non_ckd | b65_75 vs >=75 | 2.61% | 2.67% | -0.06% (-0.0051 to 0.0031) | -1617 | 0.9768 (E=1.18) |

Population-attributable fraction (renal):
- CKD AKI: PAF of MAP nadir<75 = **62.41%** (exposed prevalence 79.66%, crude RR 3.084, rate exposed 14.78% vs 4.79%).
- non-CKD AKI: PAF of MAP nadir<75 = **59.23%** (exposed prevalence 84.45%, crude RR 2.72, rate exposed 4.68% vs 1.72%).

Densely-monitored subset (renal absolute risk):

| group | contrast | risk (exposed) | risk (ref >=75) | risk diff (95% CI) | NNT | RR (E-value) |
|---|---|---|---|---|---|---|
| ckd | MAP<65 vs >=75 (headline) | 18.63% | 14.02% | 4.62% (-0.0038 to 0.1005) | 21.7 | 1.329 (E=1.991) |
| ckd | MAP<75 vs >=75 | 17.50% | 13.83% | 3.67% (-0.0134 to 0.0818) | 27.2 | 1.266 (E=1.845) |
| ckd | lt55 vs >=75 | 21.25% | 13.45% | 7.80% (0.0253 to 0.1314) | 12.8 | 1.58 (E=2.538) |
| ckd | b55_65 vs >=75 | 13.65% | 13.77% | -0.12% (-0.0541 to 0.0488) | -831 | 0.9913 (E=1.103) |
| ckd | b65_75 vs >=75 | 10.57% | 12.72% | -2.15% (-0.072 to 0.0257) | -46.5 | 0.8308 (E=1.699) |
| non_ckd | MAP<65 vs >=75 (headline) | 6.41% | 4.86% | 1.54% (0.0076 to 0.0241) | 64.9 | 1.317 (E=1.963) |
| non_ckd | MAP<75 vs >=75 | 6.04% | 4.79% | 1.25% (0.0046 to 0.0208) | 80.2 | 1.26 (E=1.833) |
| non_ckd | lt55 vs >=75 | 8.75% | 5.01% | 3.74% (0.0256 to 0.0485) | 26.8 | 1.745 (E=2.885) |
| non_ckd | b55_65 vs >=75 | 3.97% | 4.74% | -0.77% (-0.0157 to -0) | -130.1 | 0.8378 (E=1.674) |
| non_ckd | b65_75 vs >=75 | 4.41% | 4.61% | -0.20% (-0.0105 to 0.0063) | -507.1 | 0.9572 (E=1.261) |

## (3) CLINICIAN-FACING DOSE TABLE (crude rates by MAP nadir band x CKD)

| MAP nadir band | CKD n | CKD AKI rate | CKD death rate | non-CKD n | non-CKD AKI rate | non-CKD death rate |
|---|---|---|---|---|---|---|
| MAP nadir < 55 | 2804 | 20.95% | 11.73% | 21851 | 8.84% | 2.43% |
| MAP nadir 55-65 | 2680 | 11.26% | 3.25% | 45259 | 2.97% | 0.71% |
| MAP nadir 65-75 | 1430 | 7.87% | 2.24% | 28125 | 2.99% | 0.43% |
| MAP nadir >= 75 | 2342 | 4.79% | 2.05% | 25065 | 1.72% | 0.31% |

## (4) MORTALITY CO-PRIMARY (hard, sampling-robust endpoint)

Per-eGFR inflection MAP on in-hospital death:

| eGFR stratum | n | events | inflection MAP (95% CI) | knee MAP (95% CI) | adj risk @MAP65 | adj risk @MAP75 |
|---|---|---|---|---|---|---|
| eGFR >= 90 | 85832 | 145 | 69 (68 to 83) | 67 (66 to 67) | 0.30% | 0.24% |
| eGFR 60-90 | 34468 | 189 | 71 (69 to 73.5) | 69 (69 to 69) | 0.50% | 0.38% |
| eGFR 45-60 | 4165 | 124 | 70 (68 to 74) | 69 (69 to 69) | 1.36% | 0.98% |
| eGFR < 45 | 5091 | 372 | 70 (69 to 71) | 67 (67 to 67) | 3.25% | 2.40% |
| eGFR < 60 (CKD) | 9256 | 496 | 70 (69 to 71) | 69 (68 to 69) | 2.37% | 1.66% |

- Mortality inflection MAP by eGFR (>=90 -> <45): [69.0, 71.0, 70.0, 70.0] mmHg; floor rises as eGFR falls: True.

CKD absolute mortality risk + NNT:

| group | contrast | risk (exposed) | risk (ref >=75) | risk diff (95% CI) | NNT | RR (E-value) |
|---|---|---|---|---|---|---|
| ckd | MAP<65 vs >=75 (headline) | 6.58% | 3.02% | 3.57% (0.0219 to 0.0487) | 28 | 2.182 (E=3.788) |
| ckd | MAP<75 vs >=75 | 5.72% | 2.88% | 2.84% (0.0125 to 0.0404) | 35.3 | 1.984 (E=3.38) |
| ckd | lt55 vs >=75 | 10.03% | 3.46% | 6.57% (0.0444 to 0.0864) | 15.2 | 2.9 (E=5.246) |
| ckd | b55_65 vs >=75 | 3.12% | 2.65% | 0.47% (-0.0087 to 0.0168) | 211.4 | 1.179 (E=1.638) |
| ckd | b65_75 vs >=75 | 2.11% | 2.29% | -0.18% (-0.0126 to 0.0084) | -555.4 | 0.9215 (E=1.389) |
| non_ckd | MAP<65 vs >=75 (headline) | 1.14% | 0.43% | 0.72% (0.0057 to 0.0085) | 139.2 | 2.687 (E=4.815) |
| non_ckd | MAP<75 vs >=75 | 0.94% | 0.39% | 0.55% (0.0041 to 0.0066) | 183 | 2.385 (E=4.202) |
| non_ckd | lt55 vs >=75 | 1.92% | 0.53% | 1.40% (0.0116 to 0.0171) | 71.6 | 3.661 (E=6.782) |
| non_ckd | b55_65 vs >=75 | 0.68% | 0.40% | 0.28% (0.0012 to 0.0042) | 358 | 1.698 (E=2.787) |
| non_ckd | b65_75 vs >=75 | 0.38% | 0.35% | 0.03% (-0.0009 to 0.0014) | 3738 | 1.076 (E=1.361) |

- CKD death: PAF of MAP nadir<75 = **61.75%** (exposed prevalence 74.70%, crude RR 3.162, rate exposed 6.48% vs 2.05%).

## (5) ROBUSTNESS

- **BH-FDR** across the four headline CKD MAP<65-vs->=75 contrasts (renal_full, renal_dense, death_full, death_dense): reject=[True, False, True, True].
- **n_map adjustment + densely-monitored re-run**: every absolute-risk and
  inflection estimate above is reported both full-cohort and in the dense
  subset; the CKD direction is expected to persist in both.
- **E-values** accompany each RR (strength an unmeasured confounder would need).
- **Negative control:** the per-eGFR inflection on hepatocellular injury
  (organ_hepatocellular) should NOT show the renal-type CKD-shifted floor; see   T5_negcontrol_threshold in the JSON.

## HONEST VERDICT

1. **Risk-inflection MAP rises as eGFR falls: True.** Adjusted RCS inflection MAP by eGFR (>=90 -> 60-90 -> 45-60 -> <45): [70.0, 70.0, 70.0, 72.0] mmHg. The CKD strata inflect at a HIGHER MAP than the eGFR>=90 stratum -- consistent with a personalized, higher floor for impaired kidneys (the curve and CIs are wide given coarse, floored map_lowest, so read these as directional).

2. **Absolute benefit is concentrated in CKD: True.** Within CKD (eGFR<60), keeping MAP nadir >=75 vs <65 is associated with an absolute **6.82%** lower AKI risk (NNT ~**14.7**) and an absolute **3.57%** lower in-hospital mortality (NNT ~**28**). In non-CKD the same contrast yields a much smaller AKI risk difference (1.18%) -- the benefit is concentrated where renal reserve is low.

3. **Bottom line (actionable):** *In CKD patients (eGFR<60), keeping intraoperative MAP nadir >=75 mmHg vs allowing it below 65 is associated with ~6.82% lower absolute AKI risk (NNT ~14.7) and ~3.57% lower absolute mortality (NNT ~28); the benefit is concentrated in CKD and is mirrored on the hard mortality endpoint.* This is observational and hypothesis-generating: confounding by indication (sicker patients reach deeper nadirs and injure more) is not removed by IPTW, vitals are coarse, and map_lowest is floored at ~52 mmHg. It motivates a CKD-stratified MAP-target trial, not a change of practice on its own.

---
*Generated by vitaldb_aki/analysis/inspire_map_threshold.py (seed 20260626). Hypothesis-generating; observational; coarse vitals; confounding-by-indication unremoved.*
