# A-line FLUID-vs-PRESSOR feasibility (Phase-0)

## READ FIRST -- what this is and is not

- **The question.** Can the arterial line tell you whether a hypotensive
  patient needs a **FLUID** bolus or a **PRESSOR**? A preload-responsive
  patient (PPV > 13.0 %, Michard cutpoint) should respond to fluid; a vasoplegic patient (blunted
  MAP-per-pressor `vaso_responsiveness`) needs a pressor.
- **Phase-0 feasibility only.** NO deep learning, NO new heavy extraction.
  It runs on whatever caches exist NOW and reports N + axis availability at
  every step. A gated deep-learning version is a separate decision.
- **Observational, single-centre** (VitalDB / SNUH). Treatment was not
  randomised. **Confounding by indication is SEVERE and runs the OPPOSITE
  way from usual**: clinicians may ALREADY read PPV / pressor-response off
  the same A-line and choose accordingly. If they already optimise,
  concordance is near-universal and a **NULL concordance benefit is
  EXPECTED**. So:
    - a **POSITIVE** concordance benefit (less organ injury when management
      matched the A-line) is the STRONG, GO-supporting result;
    - a **NULL** is consistent with BOTH 'no signal' AND 'clinicians already
      optimal' and does NOT by itself kill the deep-learning idea.
- **Hypothesis-generating** for a prospective/target-trial design; external
  validation (INSPIRE) pending. E-values quantify required unmeasured
  confounding; `organ_hepatocellular` is the negative control.

> **PRELIMINARY: False** (analysis N = 211; verdict threshold = 80 cases).

## Axis availability and N at each step

- **Preload / PPV axis:** AVAILABLE -- source `aline_sample.csv`, column `art_ppv_mean`, N = 276.
- **Preload / SVV gold-standard axis:** AVAILABLE (fluid_svv_mean).
- **Vasoplegia / vaso_responsiveness axis:** AVAILABLE (feature_matrix_enriched.csv).
- **Management (download-free):** from /cases (`intraop_phe, intraop_eph, intraop_epi, intraop_crystalloid, intraop_colloid, age, sex, asa, preop_htn, preop_dm, preop_cr, intraop_ebl, optype, opstart, opend, anestart, aneend, weight, height, bmi`).
- **Outcomes:** organ_renal, composite, organ_hepatocellular.
- **Recommendation rule used:** `ppv_plus_vaso_responsiveness` (SVV-augmented).

### Merge trace (N at each step)

- `ppv_from_aline_sample`: n=276, ppv_col=art_ppv_mean, ppv_burden_col=art_ppv_burden_min
- `vaso_fluid_axes`: matrix_used=feature_matrix_enriched.csv, vaso_available=True, svv_available=True
- `cases_exposures_confounders`: n=276, columns=['intraop_phe', 'intraop_eph', 'intraop_epi', 'intraop_crystalloid', 'intraop_colloid', 'age', 'sex', 'asa', 'preop_htn', 'preop_dm', 'preop_cr', 'intraop_ebl', 'optype', 'opstart', 'opend', 'anestart', 'aneend', 'weight', 'height', 'bmi']
- `outcomes_merged`: n=211, outcomes=['organ_renal', 'composite', 'organ_hepatocellular']

## Axis definitions

- **preload_responsive** = 1 if PPV > 13.0 % (SVV > 13 % overrides where present).
- **vasoplegic** = 1 if `vaso_responsiveness` (OLS MAP-vs-pressor slope) <= 0.0 (NaN if the axis is unavailable).
- **A-line reco** = FLUID if preload-responsive; PRESSOR if vasoplegic-
  and-not-preload-responsive. PPV-only fallback (used here if the
  vasoplegia axis is absent): high PPV -> FLUID, low PPV -> PRESSOR.
- **management (actual)** = top-tertile fluids without pressor -> 'fluid';
  any pressor without top-tertile fluids -> 'pressor'; both / neither.
- **concordant** = 1 if actual management matched the A-line reco.

### Body-size / dosage normalisation

The /cases pressor totals are **RAW** (PHE-equivalent ug, NOT ug/kg) and
fluids are **RAW mL** -- both confounded by body size. Before building the
fluid-/pressor-predominant tertiles we normalise per kg:
  - pressor PHE-equivalent total / weight_kg -> **ug/kg**,
  - fluid mL / weight_kg -> **mL/kg**,
and recompute the tertiles on the weight-normalised values. BSA (Mosteller)
= sqrt(height_cm*weight_kg/3600) is also derived. **weight_kg + age + sex**
are added to the IPTW propensity/adjustment covariate set. PPV/SVV (the
preload axis) are intrinsically size-independent and are left as-is.
  - body size available: True (N weight = 211, N BSA = 211); dose size-normalised: True.

## 1. Axis validation

### (a) PPV / preload axis
- N = 211; preload-responsive (PPV>13) = 138 (0.654).
- PPV distribution: min 4.77, median 17.07, p75 23.88, max 102.
- corr(PPV, PPV-burden) = 0.469 (sanity: should be strongly positive).

### (b) Vasoplegia axis
- N non-null vaso_responsiveness = 13; vasoplegic (blunted) = 8.
  - corr_vaso_responsiveness_vs_vaso_n_agents = 0.048
  - vaso_n_agents_blunted_mean = 2.25
  - vaso_n_agents_responsive_mean = 1.268
  - corr_vaso_responsiveness_vs_vaso_pressor_duration_frac = -0.346
  - vaso_pressor_duration_frac_blunted_mean = 0.998
  - vaso_pressor_duration_frac_responsive_mean = 0.999
  - corr_vaso_responsiveness_vs_vaso_max_infusion_norm = 0.117
  - vaso_max_infusion_norm_blunted_mean = 1.125
  - vaso_max_infusion_norm_responsive_mean = 1.2

## 2. Concordance HTE (headline)

- Decidable recommendations: 140 (FLUID=138, PRESSOR=2, undecidable=71).
- Concordant (management matched A-line) = 44 (0.314); discordant = 96.

### organ_renal **[UNDERPOWERED, hypothesis-only]**
- **Pooled concordant vs discordant:** RD = -0.0126 (95% CI -0.0708 to 0.0531); RR = 0.7235 (95% CI 0 to 3.185). n=140, events=8, concordant=44. (Negative RD = concordant had LESS injury.)
  - E-value point = 2.109, E-value CI = 1.
  - Concordance main OR = 1.931 (p = 0.828); reco-interaction OR = 0.2309 (p = 0.46).
  - _fluid_recommended:_ RD = -0.0246 (CI -0.0718 to 0.03); n=138, events=7 [underpowered]
  - _pressor_recommended:_ RD = n/a (CI n/a to n/a); n=2, events=1 [underpowered]

### composite
- **Pooled concordant vs discordant:** RD = 0.1865 (95% CI -0.051 to 0.4164); RR = 1.979 (95% CI 0.7687 to 4.087). n=140, events=33, concordant=44. (Negative RD = concordant had LESS injury.)
  - E-value point = 3.371, E-value CI = 1.
  - Concordance main OR = 2.027 (p = 0.496); reco-interaction OR = 1.248 (p = 0.796).
  - _fluid_recommended:_ RD = 0.1825 (CI -0.0518 to 0.4139); n=138, events=32
  - _pressor_recommended:_ RD = n/a (CI n/a to n/a); n=2, events=1 [underpowered]

### Negative control (organ_hepatocellular)
- RD = 0.0403 -> **NON-NULL (possible residual confounding)**.

### BH-FDR (concordance main effect, primary outcomes)
- organ_renal: p = 0.828, FDR-reject = False
- composite: p = 0.496, FDR-reject = False

## GO / NO-GO for the deep-learning version

### Verdict: **WEAK-GO (signal in the right direction, CI crosses null)**

- Concordant management trended toward LOWER injury (RD=-0.0126) but the CI crosses 0 at current N.

### Explicit criteria
- **GO** if: concordant management shows a powered, protective renal RD (CI excludes 0) with the negative control null -- i.e. a recoverable gap a model could exploit.
- **INPUTS-PENDING** if: PPV/outcome N < 80 OR the vasoplegia axis (`vaso_responsiveness`) is not yet extracted -- re-run after the broader ART-waveform + vasoactive-PD extraction.
- **NO-GO / NULL** if: no protective concordance association at adequate N (remembering a null can mean 'clinicians already optimal', so weigh it with the descriptive separation of the axes, not in isolation).

**Fuller power needs the broader ART-waveform extraction** (more PPV cases) and the vasoactive-PD enrichment (`vaso_responsiveness`, `vaso_n_agents`, `vaso_pressor_duration_frac`) landing in `feature_matrix_enriched.csv`.

## Methods (brief)
- Preload-responsive from PPV>13 % (`art_ppv_mean`; SVV>13 % overrides where present). Vasoplegic from blunted `vaso_responsiveness` (OLS MAP-vs-pressor slope), where that axis is extracted.
- Management is download-free from /cases (fluid tertiles + any-pressor presence), reusing the actionable_targets derivations. Pressor PHE-equivalent dose and fluid volume are **size-normalised per kg** (ug/kg, mL/kg) before tertiles; weight_kg+age+sex are in the IPTW covariate set.
- IPTW: stabilised, 1%-trimmed weights from a logistic propensity model (reused from hypotension_treatment.py), refit on the concordant exposure; PS covariates = the actionable confounder set.
- Concordance HTE: pooled + within-recommendation-stratum IPTW RD/RR with nonparametric percentile-bootstrap 95% CIs; a (concordant x recommendation) IPTW logistic interaction; E-values (VanderWeele & Ding 2017); organ_hepatocellular negative control; BH-FDR across primary outcomes.

---
*Generated by vitaldb_aki/analysis/aline_fluid_vs_pressor.py*
