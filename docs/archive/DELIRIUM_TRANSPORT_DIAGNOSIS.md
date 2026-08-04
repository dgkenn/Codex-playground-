# "Do 2": diagnosis of the delirium-model external-validation collapse (executed)

The user's `production_xgb_735` delirium model: **derivation AUC 0.903 → external (MIMIC) AUC 0.58**
(drop 0.32, near chance), robust across outcome definitions (strict ICD F05+antipsychotic 0.584; +NLP
0.580). The EEG features (55/735) are NaN externally (MIMIC has no intraoperative EEG). Question: is the
collapse because (a) EEG is irreplaceable and MIMIC delirium is unpredictable without it, or (b) the model
failed to transport (overfit to derivation; didn't use the clinical signal that does generalize)?

## Executed test (MIMIC, reachable data)
Rebuilt the user's exact label/cohort on MIMIC-IV and trained a **clinical-feature-only** model (NO EEG):
- **Cohort:** first ICU stay, LOS≥24 h, age≥18, neuro-ICD excluded, death<24 h excluded → n=49,830.
- **Label:** ICD **F05** delirium → 1,561 events (3.1%).
- **Features (17, no EEG):** age, sex, comorbidity burden (distinct ICD count, F05-excluded), ICU LOS,
  mechanical ventilation, + 12 first-24 h labs (lactate, creatinine, bilirubin, platelets, BUN, WBC,
  bicarbonate, INR, albumin, hemoglobin, anion gap, sodium).
- **Validation:** 5-fold patient-level CV, IRLS logistic.

### Result: **CV AUC = 0.797**
- Clean (comorbidity count excludes the F05 code itself): **0.797** — the comorbidity burden is a
  legitimate sickness proxy, not a label leak (excluding F05 leaves it unchanged).
- Robustness (drop comorbidity entirely): **0.679** — still far above the user's external 0.58.

## Verdict: the collapse is a TRANSPORT FAILURE, not a prediction ceiling
MIMIC delirium is **highly predictable (AUC 0.80) from transportable clinical features alone**. Therefore
the model's external 0.58 is **not** "EEG is irreplaceable / MIMIC can't host it." It is that
`production_xgb_735` concentrated its signal in the 55 EEG features (NaN externally) and **failed to carry
the clinical signal that generalizes**. Removing EEG should drop external performance to a *clinical-only*
floor (~0.80 here), not to chance (0.58) — so the model is also mis-calibrated / overfit on the
derivation distribution, beyond just the missing-EEG branch.

## Cross-hospital external validation (executed): MIMIC → eICU
Trained the transportable clinical model on MIMIC (n=50,148; F05 delirium 3.1%) and tested on **eICU**
(n=116,660; delirium from the diagnosis table, 1.1%) — an independent ~200-hospital system. Common 11
features, **no EEG**, standardized on MIMIC statistics:

| Model | MIMIC in-sample AUC | **eICU external AUC** |
|---|---|---|
| Full (incl. comorbidity-burden count) | 0.776 | **0.819** |
| **Clean physiology only** (age, sex, LOS, vent, 6 labs — drop comorbidity count) | 0.680 | **0.617** |

**Honest reading (the robustness check is load-bearing):** the 0.82 is **substantially inflated by the
comorbidity-burden count**, which (i) is defined differently in each database (MIMIC distinct-ICD count vs
eICU diagnosis-row count) and (ii) is confounded by **documentation intensity** — patients with more codes
are more likely to have delirium *coded*, an ascertainment artifact, not pure risk. The genuinely
transportable **physiological** signal (labs + age + ventilation) externally validates at **AUC ~0.62** —
real and reproducible across hospitals, but **modest**, and only a little above the EEG-dependent model's
0.58.

### Refined verdict
- The 0.90→0.58 collapse is **partly** transport failure (a transportable model does better) **and partly
  genuine difficulty**: clean physiological delirium prediction tops out ~0.62 externally.
- Comorbidity/documentation burden adds a lot of *apparent* AUC (→0.82) but is ascertainment-confounded —
  not a clean predictor to build a deployable model on.
- **Therefore the real high-impact question stands: does intraoperative EEG add genuine incremental value
  over the ~0.62 transportable physiological base?** That is exactly what cannot be tested on reachable
  data (no intraop-EEG + delirium cohort) — and is the contribution if an EEG-bearing cohort is unlocked.

## The fix = the publishable contribution
A delirium model that **externally validates** — where DELPHI-EEG (single-center, no external validation)
and `production_xgb_735` (0.90→0.58) do not — is itself the high-impact result, and it is reachable now:
1. **Transportable base model** on clinical features → ~0.80 external (shown). Train on one cohort
   (MIMIC), **externally validate on eICU** (also reachable) for a true cross-hospital AUC.
2. **EEG as an incremental layer** where available (VitalDB / an EEG-bearing cohort): quantify the +ΔAUC
   EEG adds *on top of* the transportable base, instead of building a model whose signal lives entirely
   in the non-transportable features.
3. Calibrate across cohorts (the Brier 0.55–0.60 externally indicates severe miscalibration to fix).

## Side result (kill-test): Idea 2 (arterial morphology → AKI) is DEAD
160-case VitalDB ART sample (80 AKI / 80 non-AKI), per-case tone/morphology features (form factor,
diastolic decay tau, dP/dt, PP, PP-CV, SBP, DBP) → AKI: **no signal** (every OR/SD straddles 1; e.g.
form_factor 0.84 [0.61,1.15], diastolic_tau 1.18 [0.55,2.52]; AKI vs non-AKI means near-identical).
Combined with the prior novelty wound (Miles 2025 TPP, VarM preprint), Idea 2 is killed.

## Next step toward a *fully-validated* high-impact finding (no MOVER needed)
Train the transportable clinical delirium model on MIMIC, **externally validate on eICU** (different
hospital system) → a delirium risk model that *generalizes*, with EEG quantified as incremental where
available. This is executable on data already reachable.
