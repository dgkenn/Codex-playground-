# The 10 de-implementation trials — methodology, matched instrument, and reviewer attacks

**The central realization (drives everything).** These 10 do **not** share a trigger structure, so they cannot
share one instrument. Confounding-by-indication is not defeated by a single trick — it is defeated by **matching
the source of exogenous variation to HOW the treatment is actually decided.** Our assay-noise IV is the new,
bulletproof tool for the *lab-flag-triggered* class only (~4 of 10). The near-universal solvent is a **matched
toolkit + RCT-anchored calibration + triangulation**, not one instrument. This document logs all 10, classifies
each by trigger structure → correct instrument, and lists the sharpest journal-reviewer attacks + defenses.

## Trigger-structure taxonomy → instrument (the framework)
| Trigger structure | Mechanism | Correct instrument | Exclusion restriction |
|---|---|---|---|
| **Lab-flag** | reflexive at a measured-lab threshold | **assay-noise IV / flag-ITT** (ours) | STRONG (analytic imprecision, auditable) |
| **Symptom/gestalt** | clinician judgment on symptoms | **provider/prescriber-preference IV** | WEAK (habit ~ care intensity) — must harden |
| **Risk-score/protocol** | deterministic-ish on a risk score | **score-RDD** (if a hard cutoff) | MED (score is gestalt-adjusted) |
| **Any** | — | **negative-control calibration + triangulation bounds + guideline-change DiD** (if calendar) | — |

## The 10 trials

### 1. Electrolyte repletion (Mg/K) — LAB-FLAG → assay-noise IV — **RUN NOW (flagship)**
- Trigger: Mg 50960 < 2.0; K 50971 < 3.5. Treatment: Mg 222011/227523/227524; KCl 225166. Outcome: arrhythmia,
  mortality, LOS. Evidence vacuum (novel).
- **Attacks:** (a) weak first stage → lead with flag-ITT + implied-LATE (AR CI); (b) **co-repletion bundle**
  (Mg+K+Phos ordered together) breaks exclusion → bundle-balance test on Z; (c) heaping at round values → donut;
  (d) "noise" = biologic drift not assay → σ-by-interval + lag-1 autocorr; (e) selection into ≥2 pre-tx draws;
  (f) competing risks (in-hosp mortality ~ LOS) → 30/90-day. **Status:** built, running.

### 2. PPI/H2 stress-ulcer prophylaxis → GI bleed vs C.diff/pneumonia — MIXED → assay-noise (coagulopathy arm) + provider-IV — **GAP-CLOSE**
- Trigger is **Cook criteria**: mechanical ventilation ≥48 h (NOT lab) OR coagulopathy (platelet<50k / INR>1.5 —
  **LAB-FLAG!**). So the coagulopathy criterion is assay-noise-amenable; the vent criterion needs provider/unit-IV.
- Treatment: PPI/H2 are **oral/scheduled → in `prescriptions`/`emar`, NOT inputevents** → ICU-inputevents misses
  them (first-stage understated). **Gap-close:** pull `prescriptions`. RCT context: PEPTIC (2020), REVISE (2024).
- **Attacks:** (a) the C.diff/pneumonia outcomes are **ascertainment-biased** (sicker → more testing) → use
  negative-control outcomes + calibrate; (b) provider/unit exclusion (SUP-happy units sicker); (c) indication =
  the risk factors that also drive bleeding. **Novel angle:** assay-noise IV on the platelet<50k / INR>1.5 SUP
  trigger is clean and unexploited.

### 3. RBC transfusion → mortality/cardiac — LAB-FLAG → assay-noise IV — **RUN NOW (validation)**
- Hb 51222/51221 < 7.0. Treatment RBC 225168+220996. RCT-SETTLED (TRICC/TRISS restrictive non-inferior;
  contested in cardiac/MI: TITRe2/MINT). **Validation anchor**, benchmarks Bosch 2022 (fuzzy RDD at Hb 7 in
  MIMIC-IV). **Attacks:** (a) weak Hb noise (CV 1–2%) → wide CIs, supplement with POC-vs-central discordance;
  (b) Bosch precedent → novelty = formal noise model, not the application; (c) cardiac stratum exclusion (bundle).

### 4. Benzodiazepines in older inpatients → delirium/falls/mortality — SYMPTOM → provider-IV (+ CIWA-RDD subgroup) — **GAP-CLOSE (hard)**
- Trigger: agitation/insomnia/alcohol-withdrawal (gestalt, NOT lab). Treatment: `prescriptions`/`emar`. 
- **Attacks (severe):** (a) **reverse causation** — delirium → benzo, not just benzo → delirium (landmark/lag
  design needed); (b) indication confounding is extreme (agitated/withdrawing ≠ calm); (c) provider-preference
  exclusion (benzo-happy prescribers differ in whole style); (d) delirium **ascertainment** (CAM inconsistently
  charted). **Cleaner sub-design:** alcohol-withdrawal **CIWA-score-triggered** benzo → score-RDD (but CIWA is
  subjective → soft cutoff). This is the hardest of the 10; honest framing = provider-IV + heavy negative-control
  calibration, or restrict to the CIWA-protocol subgroup.

### 5. IV albumin → mortality/AKI — WEAK LAB-FLAG → provider-IV / drop — **GAP-CLOSE or DROP**
- Trigger: albumin 50862 < 2.5 (weak) but mostly **indication-bundled** (SBP prophylaxis, HRS, large-volume
  paracentesis — the RCT-supported uses). Albumin drawn **sparsely** → weak leave-one-out control. 
- RCT context: SAFE/ALBIOS (resuscitation albumin ≈ neutral) settle the *fluid-choice* question, not the
  low-albumin-number reflex. **Attacks:** (a) sparse serial draws undermine the noise design; (b) near-inseparable
  from settled bundled indications. **Weakest candidate** — run only if a non-cirrhotic, non-SBP subgroup isolates.

### 6. Sodium bicarbonate for metabolic acidosis → mortality/renal — LAB-FLAG → assay-noise IV — **GAP-CLOSE**
- HCO3 50882 < 15 (or pH < 7.2). Treatment 220995/227533. RCT: BICAR-ICU (benefit only in AKIN 2–3 subgroup);
  DKA-bicarb settled = no benefit. **Attacks:** (a) HCO3 is **calculated** from pH/pCO2 → measurement error is
  correlated, not iid (breaks the noise model — must use directly-measured HCO3 or model the correlation); (b)
  **bundle** — bicarb in shock comes with fluids/pressors → exclude concurrent DKA/sepsis-bundle activation;
  (c) stratify by AKI to test the BICAR-ICU subgroup. Gap-close = bundle-exclusion filter.

### 7. Opioid intensity → respiratory failure/LOS — SYMPTOM → provider-IV (post-op subgroup) — **GAP-CLOSE**
- Trigger: pain (gestalt, NOT lab). Treatment: `prescriptions`/`emar` + PCA. **Attacks:** (a) **pain severity
  unmeasured** = the confounder; (b) reverse causation (the painful condition drives both dose and outcome);
  (c) crowded opioid-epidemic literature. **Cleaner design:** **post-operative** opioid dosing where the surgery
  fixes the pain indication → anesthesiologist/prescriber-preference IV *within procedure type* (procedure = the
  natural stratifier). Respiratory-failure outcome has good face validity (naloxone/reintubation).

### 8. Antipsychotics for delirium → mortality — SYMPTOM → provider-IV — **RUN (validation)**
- Trigger: delirium/agitation (gestalt). Treatment: `prescriptions`/`emar` (haloperidol, quetiapine, olanzapine).
- **RCT-SETTLED:** MIND-USA (haloperidol no mortality/delirium benefit in ICU), AID-ICU → **validation case**
  (toolkit should recover the null). **Attacks:** (a) delirium severity confounding + ascertainment; (b) reverse
  causation; (c) the QTc→antipsychotic-withholding is a lab-linked contraindication (partial assay-noise angle).

### 9. VTE-prophylaxis intensity → bleeding vs VTE — RISK-SCORE → score-RDD + provider-IV — **GAP-CLOSE**
- Trigger: Padua/Caprini risk score + renal function (CrCl for enoxaparin dosing) + platelet<50k contraindication.
  Treatment: heparin ppx 225975 / enoxaparin 225906 / fondaparinux 225908 (inputevents) + `prescriptions`.
- **Attacks:** (a) bleeding & VTE **ascertainment** (more imaging in sicker); (b) the risk score is
  gestalt-adjusted (soft cutoff); (c) contraindication confounding (frail → withheld → looks protective).
  **Angle:** CrCl<30 dose-reduction threshold = a clean RDD; platelet<50k withholding = assay-noise.

### 10. Systemic corticosteroids in acute illness → outcomes — SYMPTOM/DISEASE → provider-IV within indication — **GAP-CLOSE**
- Trigger: disease (COPD exac, sepsis, ARDS, COVID…) — **wildly heterogeneous**, NOT lab. Treatment:
  `prescriptions`/`emar` + inputevents (hydrocortisone/methylprednisolone). Many RCTs exist per indication
  (RECOVERY/COVID; ADRENAL/APROCCHSS/sepsis; REDUCE/COPD-duration). **Attacks:** (a) **indication heterogeneity**
  — must FIX one indication (e.g., COPD exacerbation) or the estimand is meaningless; (b) severity confounding;
  (c) many sub-questions already RCT-settled → validation on those, novelty only in the untested indications.
  Gap-close = restrict to one indication cohort (COPD exac is cleanest + REDUCE gives a duration benchmark).

## Split by runnability
- **RUN-NOW (assay-noise IV, lab-flag, clean):** #1 Mg/K, #3 RBC (validation), + the lab-flag *sub-triggers* of
  #2 (platelet/INR SUP) and #9 (platelet withholding, CrCl dose-RDD).
- **RUN-NOW (provider-IV, validation):** #8 antipsychotics (recover MIND-USA null).
- **GAP-CLOSE then run:** #2 PPI (pull `prescriptions`; provider/unit-IV + coagulopathy assay-noise), #4 benzo
  (provider-IV + CIWA subgroup + landmark for reverse causation), #6 bicarb (bundle-exclude; measured not
  calculated HCO3), #7 opioid (post-op subgroup + prescriber-IV), #9 VTE (score-RDD + provider-IV), #10 steroids
  (fix to COPD-exacerbation indication).
- **DROP/niche:** #5 albumin (sparse draws + inseparable settled bundles) unless a clean subgroup isolates.

## The methodology gap and how to close it (the real work)
**Gap:** the assay-noise IV covers only lab-flag triggers (#1, #3, and sub-parts of #2/#6/#9). The 6
symptom/gestalt/disease-triggered trials (#2 vent-arm, #4, #7, #8, #10, #5) need a DIFFERENT instrument.
**Closure = the provider/prescriber-preference IV, hardened** against its weak exclusion restriction by:
(1) conditioning **within service/unit** (compare prescribers treating the same case-mix); (2) **negative-control
outcome calibration** (Schuemie/Madigan — ~50 controls → empirical null → correct residual bias); (3) **near-far
matching** on the preference instrument; (4) **landmark/lag** designs to kill reverse causation (#4, #7); (5)
**fixing the indication** (#7 post-op, #10 COPD) so the estimand is well-defined. Data need: `prescriptions`
(drug exposures) + `order_provider_id` (prescriber) — pulling now.

## The near-universal solvent (the unifying claim, honest)
No single instrument is universal. The **framework** is: (i) a **trigger-mechanism taxonomy** that routes each
treatment to its correct instrument (lab→assay-noise, symptom→provider-IV, score→RDD); (ii) **RCT-anchored
calibration** — prove the toolkit recovers the KNOWN answers (transfusion, glucose, antipsychotics, COPD-steroid
duration) before trusting it on the vacuums; (iii) **triangulation into convergent bounds** so no single weak
design carries a claim; (iv) **negative-control empirical calibration** on every estimate. That package — not a
lone estimator — is the near-universal solvent, and it directly answers the deepest reviewer attack
("confounding-by-indication is observationally unsolvable, that's why we do RCTs"): we *calibrate against the
RCTs we have* and only then extrapolate to the ones we don't.
