# Actionable Intraoperative Management Targets (High-Risk Phenotype)

## Interpretation & limitations (READ FIRST)

- **Observational, single-centre** (VitalDB / SNUH). Treatment was not
  randomised; **confounding by indication** is the central threat -- sicker,
  more unstable patients receive different management AND are more likely to
  sustain organ injury.
- Effects below are the **within-high-risk-phenotype** association of each
  MODIFIABLE intraoperative decision with organ injury, IPTW-adjusted for the
  confounder set `['age', 'sex', 'asa', 'preop_htn', 'preop_dm', 'preop_cr', 'intraop_ebl', 'anesthesia_duration_min', 'op_duration_min', 'optype_code']`.
- These are **HYPOTHESIS-GENERATING for a prospective trial**, not causal
  proof. **External validation on INSPIRE is pending.**
- **E-values** quantify how strong an unmeasured confounder would have to be
  (risk-ratio scale) to explain a result away. A small E-value (~1-1.5) means
  weak residual confounding could nullify the finding.
- **Negative control:** `organ_hepatocellular` -- management
  should not plausibly cause it; a non-null effect there flags residual
  confounding.
- **Power:** high-risk-phenotype cells with < 15
  events are reported but marked **underpowered, hypothesis-only**.

## Cohort

- Confirmatory phenotypes regenerated deterministically (best k = 2; seed 20260626).
- High-risk cluster = **0** (selected by organ_renal rate).
- N cases = 4335; N in high-risk phenotype = 438.
- Pressor unit assumption: intraop_phe (ug), intraop_eph (mg, x10.0 -> PHE-ug equiv), intraop_epi (ug); fluids (mL).

## The five modifiable exposures (definitions)

1. **Vasopressor- vs fluid-predominant management** (`vasopressor_predominant`):
   pressor dose in the TOP tertile (PHE-equivalent, among pressor-treated) AND
   fluids NOT in the top tertile. Also reported: `any_vasopressor` (any pressor).
2. **Phenylephrine-predominant** vs ephedrine (`phenylephrine_predominant`):
   phe (ug) > ephedrine PHE-equivalent. Better-powered secondary to #3.
3. **Phenylephrine vs NOREPINEPHRINE** (`phe_vs_norepi`) -- MECHANISTIC HEADLINE:
   among pressor-exposed, phe-dominant (1) vs norepi-dominant (0). Norepi from
   Orchestra/NEPI pump tracks (~88 VitalDB cases) -> SMALL-N, hypothesis-only.
   Phe alpha-constriction raises MAP but may not restore renal perfusion.
4. **Arterial line** (`arterial_line`): invasive continuous BP -- SNUADC/ART
   present in the trks index.
5. **Time-to-treat hypotension** (`slow_treat`): lag from first MAP<65 to first
   pump pressor onset; SLOW (>median) vs FAST (<median); hypotension-but-no-
   pressor is a separate 'untreated' level. Derivation: matrix_approx; median lag = nan min.
   Plus the **fluid U-shape** (`high_fluid` top tertile / `low_fluid` bottom
   tertile; `fluid_level` 0/1/2): overload (venous congestion) vs hypovolemia.

## Findings (led by best-powered + most actionable)

### phe_vs_norepi
- **organ_renal:** within high-risk phenotype RD = -0.55 (95% CI -0.9148 to 0.1199); RR = 0.1751 (95% CI 0.0838 to 0.4225). n = 218, events = 27.
  - Phenotype interaction OR = 0.4533 (p = 0.564); E-value (point) = 10.9, E-value (CI) = 4.166.
- **composite:** within high-risk phenotype RD = -0.5788 (95% CI -0.6474 to -0.5175); RR = 0.4212 (95% CI 0.3526 to 0.4825). n = 228, events = 98.
  - Phenotype interaction OR = 0.0004 (p = 0.044); E-value (point) = 4.18, E-value (CI) = 3.563.
- _Negative control (organ_hepatocellular):_ RD = -0.2088 -> NON-NULL (possible residual confounding).

### any_vasopressor
- **organ_renal:** within high-risk phenotype RD = -0.1935 (95% CI -0.4303 to 0.0297); RR = 0.3113 (95% CI 0.1462 to 1.292). n = 416, events = 40.
  - Phenotype interaction OR = 0.2416 (p = 0.12); E-value (point) = 5.878, E-value (CI) = 1.
- **composite:** within high-risk phenotype RD = -0.209 (95% CI -0.4193 to 0.0688); RR = 0.6075 (95% CI 0.4194 to 1.259). n = 438, events = 153.
  - Phenotype interaction OR = 0.4054 (p = 0.104); E-value (point) = 2.677, E-value (CI) = 1.
- _Negative control (organ_hepatocellular):_ RD = -0.2921 -> NON-NULL (possible residual confounding).

### arterial_line
- **organ_renal:** within high-risk phenotype RD = -0.053 (95% CI -0.16 to 0.0712); RR = 0.6364 (95% CI 0.3319 to 2.61). n = 416, events = 40.
  - Phenotype interaction OR = 0.6696 (p = 0.58); E-value (point) = 2.519, E-value (CI) = 1.
- **composite:** within high-risk phenotype RD = 0.1567 (95% CI 0.0249 to 0.3052); RR = 1.714 (95% CI 1.074 to 4.193). n = 438, events = 153.
  - Phenotype interaction OR = 1.877 (p = 0.108); E-value (point) = 2.82, E-value (CI) = 1.357.
- _Negative control (organ_hepatocellular):_ RD = 0.0419 -> NON-NULL (possible residual confounding).

### high_fluid
- **organ_renal:** within high-risk phenotype RD = -0.0307 (95% CI -0.1576 to 0.0886); RR = 0.7458 (95% CI 0.25 to 4.725). n = 416, events = 40.
  - Phenotype interaction OR = 0.4209 (p = 0.296); E-value (point) = 2.017, E-value (CI) = 1.
- **composite:** within high-risk phenotype RD = 0.0815 (95% CI -0.0631 to 0.2494); RR = 1.302 (95% CI 0.8176 to 2.596). n = 438, events = 153.
  - Phenotype interaction OR = 1.151 (p = 0.724); E-value (point) = 1.928, E-value (CI) = 1.
- _Negative control (organ_hepatocellular):_ RD = -0.0477 -> NON-NULL (possible residual confounding).

### low_fluid
- **organ_renal:** within high-risk phenotype RD = -0.0303 (95% CI -0.1053 to 0.0986); RR = 0.6778 (95% CI 0 to 2.141). n = 416, events = 40.
  - Phenotype interaction OR = 1.086 (p = 0.78); E-value (point) = 2.313, E-value (CI) = 1.
- **composite:** within high-risk phenotype RD = 0.0309 (95% CI -0.2315 to 0.3063); RR = 1.096 (95% CI 0.3014 to 1.996). n = 438, events = 153.
  - Phenotype interaction OR = 1.659 (p = 0.576); E-value (point) = 1.421, E-value (CI) = 1.
- _Negative control (organ_hepatocellular):_ RD = -0.0559 -> NON-NULL (possible residual confounding).

### vasopressor_predominant
- **organ_renal:** within high-risk phenotype RD = 0.0232 (95% CI -0.0744 to 0.1273); RR = 1.246 (95% CI 0.2576 to 2.526). n = 416, events = 40.
  - Phenotype interaction OR = 1.877 (p = 0.356); E-value (point) = 1.801, E-value (CI) = 1.
- **composite:** within high-risk phenotype RD = -0.1283 (95% CI -0.262 to -0.0032); RR = 0.6458 (95% CI 0.3053 to 0.99). n = 438, events = 153.
  - Phenotype interaction OR = 0.6584 (p = 0.332); E-value (point) = 2.47, E-value (CI) = 1.111.
- _Negative control (organ_hepatocellular):_ RD = 0.0093 -> null (reassuring).

### phenylephrine_predominant
- **organ_renal:** within high-risk phenotype RD = 0.0077 (95% CI -0.0472 to 0.0692); RR = 1.098 (95% CI 0.5782 to 2.39). n = 416, events = 40.
  - Phenotype interaction OR = 0.8758 (p = 0.932); E-value (point) = 1.427, E-value (CI) = 1.
- **composite:** within high-risk phenotype RD = 0.1541 (95% CI 0.0539 to 0.2613); RR = 1.572 (95% CI 1.18 to 2.091). n = 438, events = 153.
  - Phenotype interaction OR = 1.267 (p = 0.436); E-value (point) = 2.521, E-value (CI) = 1.642.
- _Negative control (organ_hepatocellular):_ RD = 0.0469 -> NON-NULL (possible residual confounding).

## Exposures not analysable

- **slow_treat:** exposure 'slow_treat' unavailable (missing/all-NaN)

## Methods (brief)

- Phenotype labels regenerated via `phenotypes.load_physiology_matrix` +
  `discover_phenotypes` (k in 2..7, seed from config); high-risk = highest
  organ_renal rate (fallback composite).
- IPTW: stabilised, 1%-trimmed weights from a logistic propensity model
  (reused from `hypotension_treatment.py`), refit per exposure.
- PRIMARY model: full-cohort IPTW logistic outcome model with an
  exposure x high_risk_phenotype interaction term.
- Within-phenotype RD/RR: IPTW-weighted arm risks; 95% CI by nonparametric
  percentile bootstrap (weights fixed).
- E-value: VanderWeele & Ding (2017), point + null-nearest CI bound.
- Multiplicity: Benjamini-Hochberg FDR across interaction tests.

---
*Generated by vitaldb_aki/analysis/actionable_targets.py*
