# Publication dossier — all findings, claims, evidence, limitations

Single reference for the four findings, written as the target for a publication-grade red-team.
Each finding states the SCOPED claim, the key numbers, the cross-cohort evidence, and the honest
limitations. Detailed methods live in the per-finding docs (cross-referenced).

## Unifying concept (control theory)
Intraoperative arterial pressure is a feedback-REGULATED variable: clinicians titrate vasopressor
to hold MAP at target, so the hemodynamic insult is encoded in the DOSE (controller effort), not
the (held-normal) pressure. Shown in VitalDB (within-patient MAP CV 0.09 vs dose CV 0.44).
=> measure the vasopressor requirement, not just the blood pressure.

---

## FINDING 1 (primary) — vasopressor requirement is a reliable, early, mortality-graded trait
**Claim (scoped):** the per-kg vasopressor dose-requirement is a reproducible, early-identifiable
patient signal that grades mortality BEYOND measured severity. Risk-stratification, NOT a treatment
effect or practice-changer.
- Reliability split-half 0.82 (VitalDB) / 0.87 (phenylephrine) / 0.95 (MIMIC ICU); early->late 0.5-0.6.
- External: INSPIRE trait-across-ops 0.32; MIMIC ICU reliability 0.95, early->late 0.62 (n~16k).
- Mortality (MIMIC): age-adj OR 3.8/SD -> survives Charlson/Elixhauser (3.7-3.8) -> #vaso (3.0-3.1)
  -> lactate+SOFA labs (**2.4-2.5**, ~3.0 dropping the #vaso mediator). Dose-response Q1 14%->Q4 65%
  monotone, severity-adjusted Q4/Q1 RR 3.27. Confirmed by subsample convergence (38%/46%).
- Confounding by indication ARGUED AGAINST on five fronts: E-value ~6; 8/8 within-severity strata;
  homogeneous/sepsis restriction; propofol negative-control exposure (OR 0.88 vs norepi 3.01);
  prescribing-preference IV (OR ~3.8). Not eliminated (observational).
- Hostile-review: 3 adversarial rounds converged (HOSTILE_REVIEW_FINAL.md).
- **Limits:** observational; selection (arterial-line/on-pressor); two-level replication (dose-ORDERING
  replicates, not the MAP-conditioned phenotype/mechanism); prospective signal is the landmarked
  first-6h OR 1.54; SOFA approximated (no GCS/PaO2-FiO2); single-mechanism setting (VitalDB).
- Refs: PRESSOR_REQUIREMENT.md, EARLY_ID_ROBUSTNESS.md, MIMIC_EXTERNAL_VALIDATION.md,
  MIMIC_SEVERITY_SCORES.md, MIMIC_SOFA_LACTATE.md, CONFOUNDING_BY_INDICATION.md,
  CONFOUNDING_QUASI_EXPERIMENT.md, AUTOCORRELATION_ATTACK.md, FINDINGS_LEDGER.md.

## FINDING 2 — requirement -> AKI (KDIGO): risk-stratifier, not renal-specific causal
**Claim:** the requirement predicts AKI as a dose-response RISK marker; the renal-specific CAUSAL
claim does not hold.
- MIMIC (n=6,421, ESRD excluded): age-adj OR 1.38/SD; gradient Q1 38%->Q4 61%; within-severity
  OR 1.20 (3/3 lactate tertiles OR>1).
- INSPIRE norepi->organ_renal DIES on negative-control calibration (calibrated OR 0.98, z=-0.42).
- VitalDB underpowered (n=219, 17 events).
- **Verdict:** predictive YES, causal/organ-specific NO (reported as-is). Ref: REQUIREMENT_AKI_CROSSVAL.md.

## FINDING 3 — fluid-vs-pressor resuscitation balance -> mortality
**Claim:** a pressor-predominant (vs fluid) resuscitation balance grades mortality.
- MIMIC co-exposed (pressor+fluid, n=28k): tertile mortality 0.065->0.153->0.429; age-adj OR 3.5/SD;
  survives lactate (3.4).
- VitalDB intraop balance -> organ_renal OR 1.18 [0.996,1.394] (concordant, borderline); INSPIRE
  lacks fluid columns (not testable).
- **Verdict:** holds in MIMIC; partial cross-validation. Ref: RESUSCITATION_BALANCE_CROSSVAL.md.

## FINDING 4 — norepinephrine-equivalent total load -> mortality (replicates both ways)
**Claim:** total vasopressor load (all agents, norepi-equivalents) grades mortality, dose-response,
across settings.
- MIMIC: quartile mortality 0.06->0.474 (RR 7.9x), monotone CA p~0, OR 3.18/SD.
- INSPIRE intraop NEE (norepi+epi) -> death_inhosp OR 1.11/SD; tertile 0.057->0.088->0.192 (CA p=2.8e-25).
- **Verdict:** cleanest reverse-validation (MIMIC ICU <-> INSPIRE intraop). Ref: RESUSCITATION_BALANCE_CROSSVAL.md.

---

## Cross-cutting honest scope (applies to all)
Observational; vasopressor exposure co-varies with shock severity; adjustment is age (+lactate/SOFA
labs/comorbidity in MIMIC, +ASA/duration in INSPIRE), not a complete severity score. Arguments rest
on dose-response shape, within-severity persistence, negative-control/IV (finding 1), and cross-cohort
reproduction — NOT causal identification. The honest ceiling (a prospective trial for decision-benefit;
a waveform external cohort for the intraop mechanism) is future work, not a hole.
