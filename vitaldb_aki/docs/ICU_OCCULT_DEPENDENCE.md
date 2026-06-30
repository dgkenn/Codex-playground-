# Occult vasopressor dependence at normal pressure (ICU) — the novel finding

The control-theory claim, tested where the mechanism actually holds (the ICU, where pressors are
titrated to a MAP target so MAP is held near-constant), on a hard outcome at scale, using per-stay
MAP stream-filtered from MIMIC-IV chartevents (7.58 M MAP rows, 76,500 cohort stays; itemids 220052
ABPm / 225312 ART BP mean / 220181 NBPm). Code: `analysis/icu_occult_dependence.py` →
`cache/icu_occult_dependence.json`. Landmark design throughout (first-24h exposure, alive at 24h,
post-24h death).

## The claim
**Among ICU patients whose MAP is AT TARGET, the vasopressor REQUIREMENT — the dose needed to hold
that normal pressure — strongly stratifies mortality, while the pressure itself does not.** The
reassuring number on the monitor conceals risk that lives in the controller effort. This is distinct
from VIS (which never conditions on MAP being regulated) and from a patient "trait" (this is an acute,
within-encounter signal).

## Result

### (A) Control-theory premise — now CONFIRMED in the ICU (was VitalDB-only; closes Round-1 causal Issue 1)
First-24h within-stay variability (n=21,154 stays with both signals):

| | median CV |
|---|---|
| MAP (the regulated variable) | **0.125** |
| NEE infusion rate (controller effort) | **0.440** |
| ratio dose / MAP | **3.5** |

This replicates the VitalDB observation (MAP CV 0.09 ≪ dose CV 0.44, ratio 5.2) in an independent
ICU cohort. The hemodynamic insult is carried by the dose, not the held-constant pressure — now
shown where the mortality result lives, not only intraoperatively.

### (B) Occult dependence in the at-target-MAP stratum
At-target = median first-24h MAP in [65, 85] AND <10% of readings below 65 (n=7,841; mortality 12.4%):

| Requirement quartile | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| post-24h mortality | **3.1%** | 7.4% | 11.4% | **27.8%** | (monotone, 9×) |

- age-adjusted OR per SD (log NEE-load) = **2.82 [2.58, 3.09]**
- age + lactate adjusted = **2.59 [2.23, 3.12]** (n=2,590)

All of these patients have a normal, at-goal mean arterial pressure. Their pressure does not tell them
apart; their requirement separates a 3% from a 28% mortality.

### (C) Information content — the decisive contrast
Out-of-fold AUC for post-24h mortality:

| | overall cohort (n=23,920) | within at-target band (n=7,841) |
|---|---|---|
| MAP alone | 0.558 | **0.475** |
| Requirement alone | **0.723** | **0.743** |

Within the at-target band the requirement carries strong mortality information (AUC 0.74) while MAP
carries essentially none (AUC 0.47).

## Honest caveats (to be hardened by red-team)
1. **Restriction-of-range for MAP (important):** within the [65,85] band MAP variance is small by
   construction, so MAP's low within-band AUC (0.47) is *partly* a restriction-of-range artifact, not
   purely "MAP is uninformative." The load-bearing, non-artifactual claim is the **requirement** side:
   requirement is NOT range-restricted, and its within-band AUC 0.74 + monotone 9× gradient are real.
   The honest framing is "within the normal-MAP population, the requirement stratifies risk that the
   pressure cannot," not "MAP is literally worthless."
2. **Confounding by indication / severity:** at-target-with-high-requirement may still be sicker
   (vasoplegic/septic). age+lactate OR 2.59 partially addresses; FULL severity adjustment (SOFA labs +
   comorbidity), E-value, and within-severity stratification are required (next: red-team round).
3. **Complete-case:** lactate-adjusted n=2,590 of 7,841 — informative missingness (see the landmark's
   IPCW lesson); multiple imputation needed for the primary.
4. **At-target definition is one choice:** band [65,85] + <10% below 65; sensitivity across bands needed.
5. **MAP source mixes invasive (ABPm) and NBP:** module prefers invasive (≥3 readings) and falls back
   to NBP; an invasive-only sensitivity is needed (the regulated-to-target claim is strongest for art-line).
6. Observational; landmark defeats reverse-causation temporally but not confounding.

## Why this is the novel, top-tier candidate
- **Not VIS:** VIS summarizes dose as severity; this conditions on MAP being *at target* and shows the
  dose is the hidden signal precisely when the pressure is reassuring — a monitoring-error claim.
- **Not the dead trait:** this is an acute, within-encounter, outcome-linked signal, not a cross-encounter
  phenotype (which failed at ICC 0.07).
- **Mechanism + outcome together:** the control-theory premise (A) and the outcome consequence (B,C) are
  shown in the same cohort, on a hard endpoint, at scale.

Cross-ref: FINDING4_LANDMARK.md (the landmark machinery), RED_TEAM_ROUND2_SYNTHESIS.md (why trait/VIS
framings were retracted), OCCULT_DEPENDENCE_FEASIBILITY.md (why intraop INSPIRE could not test this).
