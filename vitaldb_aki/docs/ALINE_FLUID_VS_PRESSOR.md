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

> **PRELIMINARY: False** (analysis N = 165; verdict threshold = 80 cases).

## Axis availability and N at each step

- **Preload / PPV axis:** AVAILABLE -- source `aline_sample.csv`, column `art_ppv_mean`, N = 213.
- **Preload / SVV gold-standard axis:** UNAVAILABLE (SVV column absent/empty in matrix).
- **Vasoplegia / vaso_responsiveness axis:** UNAVAILABLE (vaso_responsiveness column absent/empty in matrix).
- **Management (download-free):** from /cases (`intraop_phe, intraop_eph, intraop_epi, intraop_crystalloid, intraop_colloid, age, sex, asa, preop_htn, preop_dm, preop_cr, intraop_ebl, optype, opstart, opend, anestart, aneend, weight, height, bmi`).
- **Outcomes:** organ_renal, composite, organ_hepatocellular.
- **Recommendation rule used:** `ppv_only_fallback`.

### Merge trace (N at each step)

- `ppv_from_aline_sample`: n=213, ppv_col=art_ppv_mean, ppv_burden_col=art_ppv_burden_min
- `vaso_fluid_axes`: matrix_used=feature_matrix.csv, vaso_available=False, svv_available=False
- `cases_exposures_confounders`: n=213, columns=['intraop_phe', 'intraop_eph', 'intraop_epi', 'intraop_crystalloid', 'intraop_colloid', 'age', 'sex', 'asa', 'preop_htn', 'preop_dm', 'preop_cr', 'intraop_ebl', 'optype', 'opstart', 'opend', 'anestart', 'aneend', 'weight', 'height', 'bmi']
- `outcomes_merged`: n=165, outcomes=['organ_renal', 'composite', 'organ_hepatocellular']

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
  - body size available: True (N weight = 165, N BSA = 165); dose size-normalised: True.

## 1. Axis validation

### (a) PPV / preload axis
- N = 165; preload-responsive (PPV>13) = 130 (0.788).
- PPV distribution: min 7.22, median 17.1, p75 24.03, max 87.58.
- corr(PPV, PPV-burden) = 0.453 (sanity: should be strongly positive).

### (b) Vasoplegia axis
- **UNAVAILABLE.** vaso_responsiveness not in any available matrix (feature_matrix_enriched.csv absent and feature_matrix.csv lacks/empties the column). Vasoplegia axis pending the broader vasoactive-PD extraction; the A-line recommendation falls back to a PPV-only rule.

## 2. Concordance HTE (headline)

- Decidable recommendations: 165 (FLUID=130, PRESSOR=35, undecidable=0).
- Concordant (management matched A-line) = 67 (0.406); discordant = 98.

### organ_renal **[UNDERPOWERED, hypothesis-only]**
- **Pooled concordant vs discordant:** RD = -0.0184 (95% CI -0.0613 to 0.0241); RR = 0.4225 (95% CI 0 to 2.871). n=165, events=5, concordant=67. (Negative RD = concordant had LESS injury.)
  - E-value point = 4.166, E-value CI = 1.
  - Concordance main OR = 0.0005 (p = 0.0521); reco-interaction OR = 1921 (p = 0.2565).
  - _fluid_recommended:_ RD = 0.0001 (CI -0.0505 to 0.0555); n=130, events=4 [underpowered]
  - _pressor_recommended:_ RD = -0.0718 (CI -0.2537 to 0); n=35, events=1 [underpowered]

### composite
- **Pooled concordant vs discordant:** RD = 0.0467 (95% CI -0.0754 to 0.1845); RR = 1.289 (95% CI 0.6044 to 2.629). n=165, events=30, concordant=67. (Negative RD = concordant had LESS injury.)
  - E-value point = 1.899, E-value CI = 1.
  - Concordance main OR = 0.4719 (p = 0.604); reco-interaction OR = 5.959 (p = 0.504).
  - _fluid_recommended:_ RD = 0.1981 (CI 0.0119 to 0.3776); n=130, events=28
  - _pressor_recommended:_ RD = -0.0351 (CI -0.239 to 0.1213); n=35, events=2 [underpowered]

### Negative control (organ_hepatocellular)
- RD = 0.0292 -> **NON-NULL (possible residual confounding)**.

### BH-FDR (concordance main effect, primary outcomes)
- organ_renal: p = 0.0521, FDR-reject = False
- composite: p = 0.604, FDR-reject = False

## GO / NO-GO for the deep-learning version

### Verdict: **INPUTS-PENDING**

- Vasoplegia axis (vaso_responsiveness) UNAVAILABLE in current caches; recommendation used a PPV-only fallback rule.
- Verdict deferred: too few PPV cases and/or the vasoplegia axis is not yet extracted. Re-run after the broader ART-waveform + vasoactive-PD extraction completes.

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
