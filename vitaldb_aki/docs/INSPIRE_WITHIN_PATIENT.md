> **SPECIFICITY CAVEAT (see docs/WITHIN_PATIENT_SPECIFICITY.md).** The within-patient hypotension->organ-injury effect FAILS the negative-control specificity test: the renal within-RD (0.055) is indistinguishable from the non-perfusion negative-control organs (hepatocellular 0.051 / cholestatic 0.062 / coagulation 0.060; within-null ~0.058), so the renal effect calibrates to ~0. The within-patient design removes time-INVARIANT confounding but the pan-organ pattern means TIME-VARYING confounding (a sicker operation day) is NOT excluded -- OR equivalently a global shock-mediated multi-organ injury (the controls are imperfect: severe hypotension can cause hepatic/coagulation injury too). EITHER way the effect is NOT renal-specific and NOT a clean causal AKI claim. The OR 1.53 stands as a non-specific association; treat the causal-leaning framing with this caveat.

# INSPIRE within-patient (patient fixed-effects) hypotension -> AKI

**Generated:** 2026-06-28 16:41:20  ·  seed 20260626  ·  `analysis/inspire_within_patient.py`

## READ FIRST -- scope and honest limitations
This is the **defensible causal-leaning CORE** for the MAIN intraoperative
hypotension -> postoperative AKI effect. It is **NOT** the failed CKD
personalized-MAP-target finding (see `docs/REDTEAM_CKD_MAP.md`), and it does **not**
and **cannot** rehabilitate it.

A within-patient (patient fixed-effects) design compares a patient's
**higher-hypotension** operation to **their own lower-hypotension** operation. By
construction it removes **all time-invariant confounding**: baseline disease severity,
chronic kidney disease, genetics, sex, chronic comorbidity -- anything that does not
change between a patient's operations is differenced out exactly.

What it does **not** fix, stated plainly:
- **Time-varying confounding remains.** If a patient became sicker *before* their
  higher-hypotension operation (worse acute illness, a more aggressive procedure), that
  acute change can drive both the hypotension and the AKI. Within-patient removes the
  *chronic* baseline, not the *acute* trajectory.
- **Prior-operation AKI can shift the next operation's KDIGO baseline** (each op is
  graded against its own preop creatinine), creating carry-over dependence between a
  subject's operations.
- **Informative subjects are a selected subset.** Only subjects whose operations are
  *discordant* on exposure (FE) and on both exposure and outcome (conditional logit)
  carry information. They are sicker / more operated-on than average; the estimate
  generalizes to that subset.
- **Time-invariant effect-modification is untestable here.** CKD, sex, etc. drop out of
  the model, so this design **CANNOT** test CKD-specificity. That is by design and is the
  reason it is immune to the confounding that sank the CKD finding.
- This is **causal-LEANING**, not a randomized trial. Treat it as the strongest
  observational evidence available in this dataset, not as proof.

## Cohort
Operations belonging to subjects with **>=2 renal-labelable operations** (each operation
KDIGO-graded against its own preoperative creatinine).

| quantity | value |
|---|---|
| operations | 38,850 |
| subjects | 15,497 |
| exposure-discordant subjects (inform the FE LPM) | 5,227 |
| **informative subjects (exposure-AND-outcome discordant, inform the conditional logit)** | **808** |
| ops/subject (mean / median / max) | 2.51 / 2 / 30 |
| overall AKI (organ_renal) rate | 0.0524 |
| HYPO prevalence | 0.2239 |

**Exposure (pre-specified):** `HYPO = 1` iff `map_auc_below_65` exceeds the
exposed-median (median among operations with positive sub-65 AUC), computed in this
cohort. Threshold = **60.0** mmHg·min.

Only the **808** exposure-and-outcome-discordant
subjects contribute to the conditional-logit likelihood; concordant strata condition out.

## PRIMARY -- conditional logistic (stratified by subject_id)
Within-patient odds ratio for HYPO -> AKI (organ_renal), exact conditional likelihood.

| model | OR | 95% CI | p |
|---|---|---|---|
| HYPO only | **2.796** | [2.409, 3.244] | 8.768e-42 |
| HYPO + time-varying cov | 1.532 | [1.290, 1.821] | 1.212e-06 |

Time-varying covariates adjusted: age, surgery_duration, emergency, n_map. Time-invariant
covariates (sex, baseline CKD, baseline creatinine) drop out of the conditional
likelihood automatically.

## EFFECT SIZE -- linear-probability patient fixed-effects (within / demeaning)
Within-patient change in AKI **probability** per HYPO, cluster-bootstrap CI over subjects
(2000 resamples).

| model | within-patient RD (AKI prob) | 95% CI |
|---|---|---|
| HYPO only | **+0.0596** | [0.051, 0.068] |
| HYPO + time-varying cov | +0.0221 | [0.014, 0.031] |

## WITHIN vs BETWEEN -- the headline contrast
| estimate | within-patient | between-patient (naive) |
|---|---|---|
| risk difference (AKI prob) | **+0.0596** | +0.0819 |
| odds ratio | 2.796 (conditional logit) | 3.722 (op-level logit) |

within / between RD ratio = **0.73**.

**Interpretation.** The within-patient risk difference is comparable to the naive between-patient risk difference (ratio near 1). The effect is therefore NOT an artifact of time-invariant confounding: when a patient acts as their own control, a higher-hypotension operation still carries higher AKI risk than that same patient's lower-hypotension operation.

## DOSE-RESPONSE within patient
FE LPM with `map_auc_below_65` coded as bands (0 = no burden; 1-3 = tertiles of positive
burden). Band cut points (AUC65): 30.0, 110.0.

| band | within-patient FE contrast vs band 0 (AKI prob) |
|---|---|
| band 1 | +0.0140 |
| band 2 | +0.0260 |
| band 3 | +0.0881 |

FE linear trend per band = **+0.02487** AKI-prob per band step.

## SECONDARY -- AKI severity (ordinal aki_stage, FE)
Within-patient FE LPM slope on `aki_stage` (0-3) per HYPO =
**+0.0875**
(FE LPM slope on ordinal aki_stage(0-3); linear approximation.)

**Mortality:** death_inhosp NOT analysed within-patient: a patient dies at most once, so in-hospital death has no within-subject variation across a patient's operations -- the FE / conditional likelihood would condition it entirely out.

## Verdict
A **defensible, causal-leaning** intraoperative-hypotension -> postoperative-AKI claim
**survives**
the within-patient design. Removing every time-invariant confounder via patient fixed effects leaves a positive within-patient effect whose CI excludes the null, and it is of the same order as the between-patient effect -- so the association is not merely chronic-severity confounding. Residual risk is time-VARYING confounding, which this design cannot remove; the claim is strong observational evidence, not an RCT.
