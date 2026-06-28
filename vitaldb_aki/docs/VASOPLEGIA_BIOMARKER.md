# Vasoplegia / Pressor-Responsiveness Biomarker (VitalDB-AKI)

## READ FIRST -- what this is and what it is NOT

This is the **pressor-side analog of SVV**. SVV/PPV index FLUID
responsiveness; this biomarker indexes **PRESSOR responsiveness /
VASOPLEGIA** -- whether the vasculature still holds arterial TONE or has
lost it. It is the second axis of the arterial-line *fluid vs pressor*
decision.

- **Observational, single-centre** (VitalDB / SNUH). Everything here is
  **HYPOTHESIS-GENERATING**, not causal proof. External validation pending.
- **Leakage firewall:** every biomarker is PREOP+INTRAOP only; `organ_*`
  outcomes are y, never predictors.
- The novel **waveform-only tone surrogate** is SVR-free *by construction*;
  its validity depends on the construct-validity check below.

## THE HEADLINE -- waveform tone surrogate vs MEASURED SVR

> **NOT AVAILABLE -- no measured-SVR (EV1000/Vigileo) cases overlap the A-line waveform subset in the present caches. This is the KEY validation and CANNOT be run until the EV1000 SVR subset is extracted onto the same cases as the ART-waveform pilot. The SVR-free vasoplegia-index claim is therefore UNVALIDATED so far.**

The measured-SVR reference standard (EV1000/Vigileo `fluid_svr_*`) is
**not present** on the same cases as the A-line waveform pilot in the
current caches, so the surrogate-vs-SVR correlation **could not be**
**computed**. This is the single validation that would license calling
the waveform index an *SVR-free vasoplegia* marker. Until the EV1000
SVR subset is extracted onto the ART-waveform cases, the claim is
**UNVALIDATED**.

## Axis availability (N)

- **A. Pump+MAP requirement/gain** (full cohort, download-free): N = 4335 (with outcomes 3924).
- **B. Measured SVR / SVRI** (EV1000/Vigileo reference standard): N = 0  **<- NOT extracted; validation deferred**.
- **C. Waveform-only tone surrogate** (A-line pilot cache/aline_sample.csv): N = 175.
- Feature-matrix source: `feature_matrix.csv`.

## Body-size & dose normalization (READ -- key methodological control)

A raw-dose requirement marker is **confounded by body size** (a larger
patient needs more drug for the same effect). To avoid measuring body
size instead of vasoplegia:
- **BSA** (Mosteller) = `sqrt(height_cm * weight_kg / 3600)` m^2 is computed
  per case.
- **Family A** doses are **weight-normalised (per kg)**: the norepinephrine-
  equivalent total is divided by `weight_kg` -> **ug-NEE / kg**. UNIT NOTE:
  the matrix dose totals are CUMULATIVE amounts, so this is a cumulative
  ug-NEE/kg; the clinically familiar norepi-equivalent is ug/kg/**min** (a
  rate) -- we lack a clean per-case infusion-minutes denominator in the flat
  matrix, so the cumulative-per-kg assumption is stated explicitly. The
  `vaso_responsiveness` slope (features/vasoactive_pd.py) is in RAW dose
  units (documented limitation); we therefore also carry `weight_kg`/BSA as
  covariates in the requirement analyses.
- **Family B** uses the **BSA-indexed SVRI** (= SVR x BSA), the size-
  normalised vascular-resistance index, as the gold standard (not raw SVR).
- **Family C** (tau, diastolic/MAP, form factor, augmentation index) is
  **intrinsically size-INDEPENDENT** -- these are waveform SHAPE / TIME-
  CONSTANT quantities needing no weight or dose. **That is a key advantage**
  of the waveform vasoplegia index: an SVR-free AND dose/size-free tone
  read. Even so, the criterion regressions still adjust for `weight_kg`/BSA
  + age + sex so the surrogate's value cannot be a body-size proxy.
- All incremental-AUROC / IPTW / dose-response adjustment sets include
  `weight_kg` (and BSA) + age + sex.

## Biomarker definitions

**Family A -- requirement / gain (HIGH = vasoplegia; WEIGHT-NORMALISED):**
- `nee_total_ug_per_kg` -- norepinephrine-equivalent total dose per kg (phe/10 + epi + eph + nepi on a ug-NEE axis, / weight_kg).
- `nee_peak_rate_per_kg` -- peak NEE infusion intensity per kg.
- `pressor_dur_min` -- total pressor infusion duration (size-independent).
- `pressor_n_agents` -- distinct vasoactive agents (size-independent).
- (`vaso_responsiveness` from features/vasoactive_pd.py is the MAP-per-dose
  GAIN; blunted = vasoplegia. Not in the flat matrix cache; raw dose units
  -> noted as the v1 gain signal feeding this family.)

**Family B -- measured SVR / SVRI (reference standard):** `fluid_svr_mean`, `fluid_svr_min`, `fluid_svr_low_frac` from features/fluid_responsiveness.py (SVR < 800 dyn*s*cm^-5 = vasoplegia), indexed to **`svri_indexed` = SVR x BSA** (the size-normalised standard used for validation).

**Family C -- waveform-only tone surrogate (the novel one; HIGH = vasoplegia; SIZE-INDEPENDENT):** z-scored mean of orientation-signed components from the A-line morphology pilot --
- `art_tau_decay_mean` -- diastolic decay tau = R*C; **LOW tau = fast runoff = lost tone**.
- diastolic/MAP ratio (LOW = poor tone), (MAP-DBP)/PP form factor (LOW = decay-dominated), augmentation index (LOW = low wave reflection / tone).
- combined -> **`waveform_vasoplegia_index`** (pre-specified simple z-mean; no outcome fitting; no weight/dose input).

## Convergent validity (requirement A vs waveform C)

- N (joint A-line subset) = 175; Spearman r = **0.0166**; Cohen kappa (median split) = -0.0515.
- 2x2 (median split): {'both_high': 41, 'req_high_wave_low': 46, 'req_low_wave_high': 46, 'both_low': 42}.
- Both indices oriented HIGH = vasoplegia; positive r / agreement = convergent. Small N on the A-line pilot -> hypothesis-generating.

## Criterion 3a -- predicts high pressor REQUIREMENT

- High-requirement label N = 4335, events = 629.
- _Caveat:_ high_requirement is derived from NEE/kg, which is a COMPONENT of requirement_vasoplegia_index -> that index's AUROC here is partly TAUTOLOGICAL and is shown only as a sanity check. The INFORMATIVE rows are the WAVEFORM markers (C), which are independent of the dose label.
  - `waveform_vasoplegia_index` (waveform tone surrogate (C)): AUROC vs high-requirement = **0.542** (N=175, events=36).
  - `art_tau_decay_mean` (diastolic decay tau (C)): AUROC vs high-requirement = **0.4211** (N=175, events=36).
  - `requirement_vasoplegia_index` (requirement index (A)): AUROC vs high-requirement = **0.9731** (N=4335, events=629).

## Criterion 3b -- organ injury INCREMENTAL over MAP burden

Baseline = `['map_auc_below_65', 'weight_kg', 'bsa_m2', 'age', 'sex_male']`; incremental AUROC (delta), LR p, patient-clustered bootstrap CI. BH-FDR across primary outcomes.

### `waveform_vasoplegia_index` -- waveform vasoplegia index (C)
- organ_renal: dAUROC = **-0.0012** (base 0.845 -> 0.8438; 95% CI -0.0069 to 0); LR p = 0.9879; n=165, events=5. *[underpowered]* FDR-reject=False
- composite: dAUROC = **0.041** (base 0.6703 -> 0.7112; 95% CI -0.0218 to 0.1003); LR p = 0.016; n=175, events=31. FDR-reject=True
- organ_hepatocellular **[negative control]**: dAUROC = **0.0106** (base 0.9894 -> 1; 95% CI 0 to 0.0317); LR p = 0.00181; n=129, events=3. *[underpowered]*

### `art_tau_decay_mean` -- diastolic decay tau (C)
- organ_renal: dAUROC = **0.0138** (base 0.845 -> 0.8588; 95% CI -0.0307 to 0.0771); LR p = 0.5708; n=165, events=5. *[underpowered]* FDR-reject=False
- composite: dAUROC = **0.0004** (base 0.6703 -> 0.6707; 95% CI -0.0331 to 0.0379); LR p = 0.383; n=175, events=31. FDR-reject=False
- organ_hepatocellular **[negative control]**: dAUROC = **0** (base 0.9894 -> 0.9894; 95% CI 0 to 0); LR p = 0.5938; n=129, events=3. *[underpowered]*

### `requirement_vasoplegia_index` -- requirement vasoplegia index (A)
- organ_renal: dAUROC = **0.0042** (base 0.6813 -> 0.6855; 95% CI -0.005 to 0.0142); LR p = 0.04188; n=3850, events=142. FDR-reject=False
- composite: dAUROC = **0.0218** (base 0.6419 -> 0.6637; 95% CI 0.0116 to 0.0337); LR p = 8.438e-15; n=4233, events=649. FDR-reject=True
- organ_hepatocellular **[negative control]**: dAUROC = **0.013** (base 0.6205 -> 0.6335; 95% CI -0.0011 to 0.0284); LR p = 0.01198; n=3135, events=139.

### `nee_total_ug_per_kg` -- NEE total dose per kg (A)
- organ_renal: dAUROC = **0.0058** (base 0.6813 -> 0.6871; 95% CI -0.0003 to 0.0127); LR p = 0.1762; n=3850, events=142. FDR-reject=False
- composite: dAUROC = **0.0175** (base 0.6419 -> 0.6594; 95% CI 0.0105 to 0.0264); LR p = 2.3e-13; n=4233, events=649. FDR-reject=True
- organ_hepatocellular **[negative control]**: dAUROC = **0.0114** (base 0.6205 -> 0.6319; 95% CI 0.0002 to 0.0231); LR p = 0.002656; n=3135, events=139.

### `pressor_dur_min` -- pressor duration (A)
- organ_renal: dAUROC = **0.0014** (base 0.6813 -> 0.6827; 95% CI -0.0043 to 0.008); LR p = 0.2765; n=3850, events=142. FDR-reject=False
- composite: dAUROC = **0.0138** (base 0.6419 -> 0.6557; 95% CI 0.0067 to 0.0212); LR p = 3.373e-09; n=4233, events=649. FDR-reject=True
- organ_hepatocellular **[negative control]**: dAUROC = **-0.0001** (base 0.6205 -> 0.6204; 95% CI -0.0015 to 0.001); LR p = 0.9091; n=3135, events=139.

## Criterion 3c -- IPTW-adjusted OR (primary index, vasoplegic vs not)

- Exposure: vasoplegic (index > median) on `requirement_vasoplegia_index`; PS covariates ['map_auc_below_65', 'map_mean', 'weight_kg', 'bsa_m2', 'age', 'sex_male'].
- PS adjusts for MAP burden + body size (weight, BSA) + age + sex (download-free frame); residual confounding by preop SEVERITY (labs/comorbidity) is NOT removed -> hypothesis-generating.
  - organ_renal: OR = **1.149** (95% CI 0.8132-1.624); p = 0.4306; E-value(point) = 1.563, E-value(CI) = 1.
  - composite: OR = **1.386** (95% CI 1.166-1.647); p = 0.00021; E-value(point) = 2.117, E-value(CI) = 1.606.
  - organ_hepatocellular **[negative control]**: OR = **1.293** (95% CI 0.9142-1.829); p = 0.1462; E-value(point) = 1.909, E-value(CI) = 1. -> null (reassuring)

## Validation 4 -- dose-response (quartiles of the vasoplegia index)

### requirement index (A; full cohort) (`requirement_vasoplegia_index`)
- organ_renal: rates by quantile = [0.0275, 0.033, 0.0224, 0.0663] (n/q [1598, 364, 981, 981], ev/q [44, 12, 22, 65]); Cochran-Armitage z = 4.05, p = 0.0001; monotone-increasing = False.
- composite: rates by quantile = [0.1181, 0.1239, 0.1181, 0.253] (n/q [1821, 347, 1084, 1083], ev/q [215, 43, 128, 274]); Cochran-Armitage z = 8.238, p = 0; monotone-increasing = False.

### waveform index (C; A-line pilot) (`waveform_vasoplegia_index`)
- organ_renal: rates by quantile = [0.0182, 0.0545, 0.0182] (n/q [55, 55, 55], ev/q [1, 3, 1]); Cochran-Armitage z = -0, p = 1; monotone-increasing = False.
- composite: rates by quantile = [0.25, 0.1136, 0.2093, 0.1364] (n/q [44, 44, 43, 44], ev/q [11, 5, 9, 6]); Cochran-Armitage z = -0.9561, p = 0.339; monotone-increasing = False.

## Bottom line

- Axis A (requirement/gain) is available cohort-wide and is the best-powered vasoplegia signal today.
- Axis C (waveform-only tone surrogate) is computable on the A-line pilot and is the novel SVR-free candidate, but the pilot carries very few renal events -> criterion estimates are feasibility-scale.
- **Axis B (measured SVR) is the missing keystone:** without it on the same cases, the surrogate's construct validity is unproven. **Fuller power needs the broader ART-waveform + EV1000/SVR extraction.**

---
*Generated by vitaldb_aki/analysis/vasoplegia_biomarker.py*
