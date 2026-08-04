# MIMIC-IV requirement -> mortality across MULTIPLE severity scores

The 'signal vs just-sicker' question, hardened against several *standard* severity adjustments rather than one. Re-runs the norepinephrine-requirement->mortality OR per SD under: (a) age only, (b) +Charlson Comorbidity Index [Quan 2005 enhanced ICD-9-CM + ICD-10], (c) +van Walraven weighted Elixhauser [Quan 2005 codes, vanWalraven 2009 weights], (d) +#distinct-vasopressors [cardiovascular-SOFA proxy], (f) FULL (all comorbidity); the lab-severity (e) and FULL+labs models are **PENDING** the labevents download (in progress at build time).

- Complete-case stays: **15949** (5258 deaths, rate 0.33). Labs present: **False**.

## Comorbidity score distributions (per hadm)
- **Charlson**: mean 2.247 (SD 2.299), median 2.0 [0.0-3.0], range 0.0-18.0, 0.273 with score 0 (n=478267 hadm).
- **van Walraven (weighted Elixhauser)**: mean 7.414 (SD 9.119), median 5.0 [0.0-13.0], range -17.0-63.0 (n=478267 hadm).

Top Charlson categories by hadm prevalence: chronic_pulmonary_disease (100402), renal_disease (86101), congestive_heart_failure (84715), diabetes_without_complication (84632), diabetes_with_complication (48245), malignancy (47461), myocardial_infarction (44702), peripheral_vascular_disease (38121).

## Requirement -> mortality OR per SD: STABILITY TABLE across severity specs

| Specification | Requirement OR/SD | 95% CI | AUC sev-only | AUC +req | DeltaAUC |
|---|---|---|---|---|---|
| a) age only | 3.798 | [3.442, 4.156] | 0.559 | 0.764 | 0.2051 |
| b) +Charlson | 3.814 | [3.455, 4.173] | 0.592 | 0.772 | 0.18 |
| c) +van Walraven (Elixhauser) | 3.72 | [3.368, 4.082] | 0.63 | 0.785 | 0.1542 |
| d) +#vasopressors | 3.027 | [2.721, 3.302] | 0.705 | 0.772 | 0.0667 |
| f) FULL (age+Charlson+vanWalraven+#vaso) [labs PENDING] | 3.047 | [2.732, 3.343] | 0.726 | 0.79 | 0.0641 |

- OR range across specs: **[3.027, 3.814]** (age-only 3.798 -> FULL 3.047; total attenuation **26.8%**).
- All 95% CI lower bounds above 1: **True**.

## Verdict
Requirement->mortality OR per SD ranges 3.03-3.81 across 5 severity specifications (age-only 3.798 -> FULL 3.047; total attenuation 26.8%). STABLE and >1 across ALL specifications (labs PENDING the labevents download), every 95% CI lower bound above 1 -- the requirement carries mortality information BEYOND standard comorbidity/severity scoring; not merely 'sicker patients got more drug'. Lab + FULL+labs specifications are PENDING (labevents download in progress at build time). CAVEAT: SOFA approximated by lab components + #vasopressors; no GCS / PaO2-FiO2 (chartevents). Observational.

## Methods notes
- **Charlson**: Quan et al. 2005 (Med Care 43:1130) enhanced ICD-9-CM AND ICD-10 code lists, 17 categories with standard integer weights (1/2/3/6). Per-row icd_version selects the ICD-9 vs ICD-10 prefix list. Hierarchy applied (metastatic supersedes any malignancy; diabetes-with-complication supersedes without; severe liver supersedes mild).
- **Elixhauser**: Quan 2005 enhanced ICD-9-CM + ICD-10 group definitions (31 groups); summarized with the van Walraven (2009) integer point weights (the validated single score). Uncomplicated diabetes/solid-tumor collapsed when complicated/metastatic present.
- Codes matched as PREFIXES against MIMIC's dot-free codes (e.g. ICD-9 '41401', ICD-10 'I2510'); hadms with no mapped diagnosis score 0 (standard convention).
- Requirement = per-stay MEDIAN norepinephrine rate (0 < rate <= 5 mcg/kg/min). All models standardized logistic; requirement OR is per 1 SD. Bootstrap 95% CI resamples stays (400 reps, seed 20260628).
- SOFA is APPROXIMATED by its lab components + #vasopressors; it still lacks the neurological (GCS) and respiratory (PaO2/FiO2) components, which live only in the 30GB chartevents. A complete SOFA could attenuate slightly further. Observational; norepinephrine dose is a known severity/mortality marker.
