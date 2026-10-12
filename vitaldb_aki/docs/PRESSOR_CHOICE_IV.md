# Pressor-Choice Target Trial with an Instrumental Variable

## READ FIRST -- limitations & assumptions

- **Observational, single-centre** (VitalDB / SNUH). This is an
  active-comparator *target-trial emulation*, **not** a randomised trial.
- **TINY norepinephrine arm.** The comparator (any-norepinephrine) is
  ~56 cases vs
  ~614 phenylephrine-dominant. Every
  estimate here is **HYPOTHESIS-ONLY**; absolute risks in the small arm are
  unstable and CIs are wide.
- **Confounding by indication is the central threat.** Sicker / more
  unstable / differently-managed patients are preferentially given
  norepinephrine AND are more likely to sustain organ injury. The *naive*
  contrast can therefore even REVERSE sign (norepi cases look worse).
- **Instrumental-variable assumptions:**
  1. **Relevance** (testable): the instrument must shift pressor choice. We
     report the first-stage partial F / R^2; an F < 10 (Staiger-Stock) is
     labelled a **WEAK instrument** and its IV estimate must not be
     interpreted.
  2. **Exclusion** (**UNTESTABLE**): the instrument affects the outcome ONLY
     through pressor choice. For calendar-era this is violated if ANY other
     co-evolving practice (surgical technique, fluid strategy, KDIGO assay)
     also changed over time. We **cannot** test this; we assume it and flag
     it as the binding limitation.
  3. **Monotonicity** (untestable): the instrument moves everyone's choice in
     one direction (no 'defiers'). Assumed.
- **Negative control** (`organ_hepatocellular`): pressor *choice* should not
  plausibly cause hepatocellular injury. A non-null effect flags residual
  confounding. **The IV estimate's negative control is the key credibility
  check** -- a valid IV that has broken confounding by indication should
  yield a NULL negative control.
- **E-values** (VanderWeele & Ding 2017) quantify how strong unmeasured
  confounding would need to be (RR scale) to nullify a result.
- **Leakage firewall:** confounders are PREOP + INTRAOP only; `organ_*` are
  outcomes. Pressor exposure is the download-free, presence-based derivation
  reused verbatim from `actionable_targets.add_phe_vs_norepi` (cached /trks
  index; no track download).

## Cohort & arms

- N cases = 4335; high-risk cluster = 0 (regenerated, seed 20260626).
- **Broad active comparator** (`pressor_choice`; 1 = phenylephrine-only,
  0 = any norepinephrine): N = 670 (614 phe / 56 norepi).
- **Strict sensitivity** (`phe_vs_norepi`; norepi-ONLY arm): N = 625 (614 phe / 11 norepi-only).

## First-stage instrument strength (relevance)

- **primary_era** (era_z): partial F = 7.372, R^2 = 0.01146 -> **WEAK (F<10) -- IV underpowered, do not interpret**.
- **dept_preference** (dept_pref_z): partial F = 3.153, R^2 = 0.00493 -> **WEAK (F<10) -- IV underpowered, do not interpret**.
- **sensitivity_strict_era** (era_z_strict): partial F = 0.539, R^2 = 0.00091 -> **WEAK (F<10) -- IV underpowered, do not interpret**.

## Estimates per outcome (naive vs IPTW vs IV)

### primary_era  (exposure = `pressor_choice`, instrument = `era_z`)
- **organ_renal** (phe arm n=585, events=44; norepi arm n=53, events=10):
  - **naive:** RD = -0.1135 (95% CI -0.2337 to -0.00875); RR = 0.3986; E-value(point) = 4.454, E-value(CI) = 1.479. **[UNDERPOWERED]**
  - **IPTW:** RD = -0.08221 (95% CI -0.2084 to 0.01507); RR = 0.4895; E-value(point) = 3.503, E-value(CI) = 1. **[UNDERPOWERED]**
  - **IV (Wald-RD):** RD = -0.8696 (95% CI -2.693 to -0.2061); RR~ = -3.609; E-value(point) = n/a, E-value(CI) = n/a. **[UNDERPOWERED]**
- **composite** (phe arm n=614, events=185; norepi arm n=56, events=34):
  - **naive:** RD = -0.3058 (95% CI -0.4407 to -0.1687); RR = 0.4963; E-value(point) = 3.445, E-value(CI) = 2.468.
  - **IPTW:** RD = -0.2605 (95% CI -0.42 to -0.1111); RR = 0.5431; E-value(point) = 3.086, E-value(CI) = 2.006.
  - **IV (Wald-RD):** RD = -2.459 (95% CI -7.634 to -1.088); RR~ = -3.049; E-value(point) = n/a, E-value(CI) = n/a. **[UNDERPOWERED]**
- _Negative control (organ_hepatocellular):_ naive RD = -0.1025 -> NON-NULL (possible residual confounding); IPTW RD = -0.02656 -> NON-NULL (possible residual confounding); **IV RD = -0.8278 -> NON-NULL (possible residual confounding)**.

### dept_preference  (exposure = `pressor_choice`, instrument = `dept_pref_z`)
- **organ_renal** (phe arm n=585, events=44; norepi arm n=53, events=10):
  - **naive:** RD = -0.1135 (95% CI -0.2337 to -0.00875); RR = 0.3986; E-value(point) = 4.454, E-value(CI) = 1.479. **[UNDERPOWERED]**
  - **IPTW:** RD = -0.08221 (95% CI -0.2084 to 0.01507); RR = 0.4895; E-value(point) = 3.503, E-value(CI) = 1. **[UNDERPOWERED]**
  - **IV (Wald-RD):** RD = 0.4464 (95% CI -1.085 to 3.626); RR~ = 3.366; E-value(point) = 6.188, E-value(CI) = n/a. **[UNDERPOWERED]**
- **composite** (phe arm n=614, events=185; norepi arm n=56, events=34):
  - **naive:** RD = -0.3058 (95% CI -0.4407 to -0.1687); RR = 0.4963; E-value(point) = 3.445, E-value(CI) = 2.468.
  - **IPTW:** RD = -0.2605 (95% CI -0.42 to -0.1111); RR = 0.5431; E-value(point) = 3.086, E-value(CI) = 2.006.
  - **IV (Wald-RD):** RD = -2.078 (95% CI -6.74 to -0.3703); RR~ = -2.423; E-value(point) = n/a, E-value(CI) = n/a. **[UNDERPOWERED]**
- _Negative control (organ_hepatocellular):_ naive RD = -0.1025 -> NON-NULL (possible residual confounding); IPTW RD = -0.02656 -> NON-NULL (possible residual confounding); **IV RD = -1.183 -> NON-NULL (possible residual confounding)**.

### sensitivity_strict_era  (exposure = `phe_vs_norepi`, instrument = `era_z_strict`)
- **organ_renal** (phe arm n=585, events=44; norepi arm n=10, events=4):
  - **naive:** RD = -0.3248 (95% CI -0.6751 to -0.03082); RR = 0.188; E-value(point) = 10.11, E-value(CI) = 2.564. **[UNDERPOWERED]**
  - **IPTW:** RD = -0.2931 (95% CI -0.6627 to -0.00866); RR = 0.2054; E-value(point) = 9.208, E-value(CI) = 2.14. **[UNDERPOWERED]**
  - **IV (Wald-RD):** RD = -6.075 (95% CI -60.67 to 89.26); RR~ = -14.19; E-value(point) = n/a, E-value(CI) = n/a. **[UNDERPOWERED]**
- **composite** (phe arm n=614, events=185; norepi arm n=11, events=7):
  - **naive:** RD = -0.3351 (95% CI -0.6312 to -0.03308); RR = 0.4735; E-value(point) = 3.644, E-value(CI) = 1.481. **[UNDERPOWERED]**
  - **IPTW:** RD = -0.2818 (95% CI -0.6326 to 0.02048); RR = 0.5176; E-value(point) = 3.274, E-value(CI) = 1. **[UNDERPOWERED]**
  - **IV (Wald-RD):** RD = -30.22 (95% CI -201.1 to 209.6); RR~ = -46.5; E-value(point) = n/a, E-value(CI) = n/a. **[UNDERPOWERED]**
- _Negative control (organ_hepatocellular):_ naive RD = -0.111 -> NON-NULL (possible residual confounding); IPTW RD = -0.0507 -> NON-NULL (possible residual confounding); **IV RD = -5.207 -> NON-NULL (possible residual confounding)**.

## Verdict

- Primary instrument (calendar era) first stage: partial F = 7.372 -> **WEAK**.
- IV negative-control (organ_hepatocellular): NON-NULL (possible residual confounding).
- See the per-analysis blocks above for the renal point estimates. With a
  ~56-case norepinephrine arm the IV CIs are wide and -- where the first
  stage is weak -- the IV point estimate is not interpretable. The
  norepinephrine>phenylephrine renal-protection signal should be treated as
  **confounded / underpowered, hypothesis-generating only**, pending an
  external cohort (INSPIRE) with a larger norepinephrine population and a
  stronger, defensible instrument.

## Methods (brief)

- Active comparator: among pressor-exposed cases (cached /trks presence),
  phenylephrine-only (1) vs any-norepinephrine (0). Strict `phe_vs_norepi`
  (norepi-only) run as a sensitivity.
- Naive: unadjusted arm RD/RR, bootstrap 95% CI.
- IPTW: stabilised, 1%-trimmed weights from a logistic propensity model
  (reused from `hypotension_treatment.py`); confounders PREOP+INTRAOP only.
- IV: Wald-ratio RD = ITT(Z->outcome) / ITT(Z->exposure) via OLS slopes
  (just-identified 2SLS on the RD scale); first-stage partial F from the
  first-stage R^2; bootstrap 95% CI on the Wald-RD. Instruments: calendar
  era (caseid tertiles) and leave-one-out department norepi preference.
- E-value: VanderWeele & Ding (2017), point + null-nearest CI bound.
- Multiplicity: Benjamini-Hochberg FDR across the primary IV tests.

---
*Generated by vitaldb_aki/analysis/pressor_choice_iv.py*
