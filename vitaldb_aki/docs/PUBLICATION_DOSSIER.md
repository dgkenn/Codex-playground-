# Publication dossier — all findings, claims, evidence, limitations

Single reference for the four findings, written as the target for a publication-grade red-team.
Each finding states the SCOPED claim, the key numbers, the cross-cohort evidence, and the honest
limitations. Detailed methods live in the per-finding docs (cross-referenced).

> **Post-red-team status (8-agent panel — see REDTEAM_PUBLICATION_VERDICT.md):** Finding 1 publishable
> w/ major revisions (IV demoted to supportive — invalid-instrument signature). Finding 4 UPGRADED: the
> landmark first-24h→subsequent-death test (FINDING4_LANDMARK.md) defeats the reverse-causation attack
> (age+lactate OR 2.27 [2.10,2.48]); cross-cohort framing corrected to "directional concordance, different
> estimands" (NOT a quantitative replication). Finding 2 publishable only in scoped predictive form
> (docstring/code baseline contradiction fixed). Finding 3 DEMOTED from co-primary to exploratory
> (not separable from Finding 4 load; thin adjustment; co-exposed collider; null VitalDB test).

> **Round-2 hostile-review RETRACTION (RED_TEAM_ROUND2_SYNTHESIS.md) — the trait reframe DID NOT survive:**
> The Round-1 "stable patient trait" reframe is itself retracted. The settling test (1,712 multi-stay
> MIMIC subjects) shows CROSS-ENCOUNTER reliability ICC **0.074** (r 0.087; gap≥30d 0.049) — the
> requirement does NOT reproduce across separate admissions; the headline 0.95 is within-drip
> autocorrelation. The requirement is an ACUTE ENCOUNTER-LEVEL SEVERITY SIGNAL, not a patient phenotype.
> What survives: within-encounter early→late predictability (0.62, early-warning), the control-theory
> framing (VitalDB intraop only), and the fully-adjusted landmark dose→mortality (OR 1.74, delta-AUC
> 0.024 — but this is the KNOWN VIS literature, not a top-tier novelty). NET: no clean Anesthesiology-tier
> POSITIVE finding survives as framed; honest tiers are BJA/A&A (rigorous dose→outcome + control theory)
> or a methods/cautionary "requirement is not a trait" paper. See RED_TEAM_ROUND2_SYNTHESIS.md "reckoning."

> **Round-1 hostile-review reframe (RED_TEAM_ROUND1_SYNTHESIS.md) — superseded by Round 2 above:**
> Prior-art (PubMed) shows "vasopressor load → mortality" IS the VIS literature (2024 meta-analysis,
> 58 studies; Roberts 2020; Saugel BJA 2025) → that framing is a DESK-REJECT. **The novel, load-bearing
> contribution is RELIABILITY: the vasopressor requirement is a stable, reproducible patient TRAIT
> (split-half 0.82/0.87, ICC 0.95) — unaddressed by prior art.** Lead with the trait + control-theory
> *why*; dose→mortality is the *consequence*; confront VIS in the intro. Corrections: (a) fully-adjusted
> prospective landmark OR **1.74 [1.57, 1.91]**, E-value **~2.1–2.3** (the headline ~6 does NOT transport
> to the landmark); (b) control-theory mechanism is scoped to VitalDB (MAP-conditioned), NOT the MIMIC
> MAP-unconditional quantity that carries the prospective result; (c) propofol negative-control DEMOTED
> to exploratory (collider — restricted to norepi∩propofol) — confounding now rests on E-value +
> within-severity (8/8) + homogeneous restriction. Reliability robustness (subject-clustering) and full
> independent reproduction both PASS. Target tier: Anesthesiology (conditional on reframe) / BJA / A&A.

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
- Confounding by indication ARGUED AGAINST on four robust fronts: E-value ~6; 8/8 within-severity
  strata; homogeneous/sepsis restriction; propofol negative-control exposure (OR 0.88 vs norepi 3.01).
  Not eliminated (observational). NOTE (post-red-team): the prescribing-preference IV is DEMOTED to a
  supportive/hypothesis-generating analysis — IV-OR ~3.8 > naive 2.57 is an invalid-instrument signature
  (exclusion restriction violated by unit case-mix), so it does not carry the argument.
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

## FINDING 3 — fluid-vs-pressor resuscitation balance -> mortality  [DEMOTED: exploratory, post-red-team]
**Claim (re-scoped):** in MIMIC, a pressor-predominant balance tracks mortality — but this is an
EXPLORATORY observation, NOT an independent co-primary finding.
- MIMIC co-exposed (pressor+fluid, n=28k): tertile mortality 0.065->0.153->0.429; age-adj OR 3.5/SD;
  survives lactate (3.4).
- VitalDB intraop balance -> organ_renal OR 1.18 [0.996,1.394] — CI INCLUDES 1.0 (a NULL external test,
  not "concordant support"); INSPIRE lacks fluid columns (not testable).
- **Why demoted (panel):** (i) the balance numerator IS Finding 4's NEE load — no two-predictor model
  shows the fluid denominator adds independent information; (ii) adjustment is age + single lactate
  (lactate barely moves it 3.505->3.398); (iii) co-exposed n=28k selection induces collider bias (OR
  doubles vs full cohort 2.1->3.5); (iv) null VitalDB CI. **Verdict:** exploratory only; a two-predictor
  decomposition + full severity set is future work. Ref: RESUSCITATION_BALANCE_CROSSVAL.md, REDTEAM_PUB_FINDING3.md.

## FINDING 4 — norepinephrine-equivalent total load -> mortality (landmark-confirmed prospective signal)
**Claim:** total vasopressor load (all agents, norepi-equivalents) grades mortality, dose-response;
PROSPECTIVELY (first-24h load predicts SUBSEQUENT death), directionally concordant across settings.
- MIMIC whole-stay: quartile mortality 0.06->0.474 (RR 7.9x), monotone CA p~0, OR 3.18/SD.
- **LANDMARK (post-red-team, the make-or-break test):** first-24h NEE, restricted to patients ALIVE at
  24h, -> SUBSEQUENT in-hospital death: age-adj OR **2.57 [2.45,2.68]** (n=23,925), age+lactate OR
  **2.27 [2.10,2.48]**, monotone Q1->Q4 0.060->0.334. Effect attenuates (3.18->2.57) but does NOT collapse
  -> reverse-causation/tautology REJECTED. Dopamine weight 0.05 sensitivity: 2.60 (no change). (FINDING4_LANDMARK.md)
- INSPIRE intraop NEE (norepi+epi) -> death_inhosp OR 1.11/SD; tertile 0.057->0.088->0.192 (CA p=2.8e-25).
- **Verdict:** prospective dose-response confirmed by landmark. Cross-cohort is DIRECTIONAL CONCORDANCE
  across different estimands (MIMIC 2.57 vs INSPIRE 1.11, CIs do not overlap) — NOT a quantitative
  replication. Ref: RESUSCITATION_BALANCE_CROSSVAL.md, FINDING4_LANDMARK.md, REDTEAM_PUB_FINDING4.md.

---

## Cross-cutting honest scope (applies to all)
Observational; vasopressor exposure co-varies with shock severity; adjustment is age (+lactate/SOFA
labs/comorbidity in MIMIC, +ASA/duration in INSPIRE), not a complete severity score. Arguments rest
on dose-response shape, within-severity persistence, negative-control/IV (finding 1), and cross-cohort
reproduction — NOT causal identification. The honest ceiling (a prospective trial for decision-benefit;
a waveform external cohort for the intraop mechanism) is future work, not a hole.
