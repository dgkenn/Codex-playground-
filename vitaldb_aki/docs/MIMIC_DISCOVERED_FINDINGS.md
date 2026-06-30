# MIMIC-discovered findings, validated the other way (MIMIC ICU -> VitalDB / INSPIRE intraop)

Reverse-direction test of three high-impact ideas: discover in MIMIC-IV's large ICU cohort, then
externally validate intraoperatively in VitalDB and/or INSPIRE. Same rigor as the main finding
(dose-response, within-severity, negative-control calibration). Honest verdicts.

| # | Idea | MIMIC discovery | External (the other way) | Verdict |
|---|---|---|---|---|
| 1 | **Requirement -> AKI (KDIGO)** | Risk marker: age-adj OR 1.38/SD; monotone gradient Q1 38% -> Q4 61%; survives within-severity (age+lactate+comorbidity OR 1.20; 3/3 lactate tertiles OR>1) | INSPIRE norepi->organ_renal **DIES** on negative-control calibration (calibrated OR 0.98, z=-0.42 -- within non-renal-organ null, like Pivot 3); VitalDB underpowered (n=219, 17 events) | **Risk-stratifier YES, renal-specific CAUSAL NO** |
| 2 | **Fluid-vs-pressor balance -> mortality** | Co-exposed (pressor+fluid, n=28k) tertile mortality 0.065 -> 0.153 -> 0.429; age-adj OR 3.5/SD; survives lactate (3.4). High-pressor/low-fluid worse | VitalDB intraop balance -> organ_renal OR 1.18 [0.996,1.394], concordant direction, borderline; INSPIRE has no fluid columns -> not testable | **Holds in MIMIC; intraop AKI concordant but borderline; partial cross-validation** |
| 3 | **Norepinephrine-equivalent total load -> mortality** | Quartile mortality 0.06 -> 0.474 (RR 7.9x), monotone, CA p~0; OR 3.18/SD; reproduces+strengthens norepi-only | INSPIRE intraop NEE (norepi+epi) -> death_inhosp OR 1.11/SD [1.08,1.13]; pressor-exposed tertile death 0.057 -> 0.088 -> 0.192 (CA p=2.8e-25) -> **REPLICATES** | **Cleanest reverse-validation: dose-response replicates MIMIC ICU -> INSPIRE intraop** |

## Reading
- **#3 (all-pressor NEE -> mortality) is the strongest new result:** a steep, monotone dose-response
  discovered in 16-28k MIMIC ICU stays that REPLICATES intraoperatively in 130k INSPIRE operations
  on a hard endpoint (in-hospital death). This is a genuine bidirectional, multi-cohort signal --
  the vasopressor-load -> mortality relationship is not setting-specific.
- **#1 (AKI)** extends the risk-stratification story to a second hard outcome (the project's original
  organ-injury target) but, like the mortality finding, is **not causal/organ-specific** -- the
  INSPIRE negative-control calibration is decisive and is reported as-is.
- **#2 (fluid-vs-pressor balance)** is promising in MIMIC and directionally concordant intraop, but
  the intraop CI is borderline and INSPIRE lacks fluid volumes -- a partial cross-validation.

## Honest caveats (all three)
Observational. Pressor-predominance, high NEE, and high requirement all co-vary with shock severity
(vasoplegic / refractory shock); fluid-restriction vs shock-severity cannot be fully disentangled.
Adjustment is age (+lactate in MIMIC, +ASA/duration in INSPIRE), not a complete severity score. The
argument rests on the **dose-response shape + cross-cohort reproduction**, not causal identification.
The VitalDB pressor index sums drug-specific mg (an index -> read direction not magnitude); the
INSPIRE NEE (norepi+epi, same units) is cleaner. These are risk-stratification findings, consistent
with the scoped main claim, not treatment effects.

Cross-ref: REQUIREMENT_AKI_CROSSVAL.md, RESUSCITATION_BALANCE_CROSSVAL.md; main finding in
HOSTILE_REVIEW_FINAL.md.
