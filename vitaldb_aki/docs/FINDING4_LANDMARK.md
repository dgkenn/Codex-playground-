# Finding 4 landmark test — the red-team "make-or-break" analysis

**Reviewer attack (REDTEAM_PUB_FINDING4.md, CRITICAL-1):** the headline NEE total load is
integrated over the **whole ICU stay**, so dying patients accumulate vasopressor-minutes up to
the moment of death — exposure and outcome are coterminous, and the OR 3.18/SD might be a
near-identity ("dying patients get more pressor"). The mandatory missing analysis is a **landmark**
design: measure NEE over the **first 24 h only**, keep only patients **alive at the 24 h landmark**,
and predict **subsequent** in-hospital death. The reviewer called this "the make-or-break test."

**Result: SURVIVES.** Code: `analysis/finding4_landmark.py` → `cache/finding4_landmark.json`.

| Specification | OR/SD (log NEE-load) | 95% CI | n | Q1→Q4 mortality |
|---|---|---|---|---|
| Headline (whole-stay NEE, contemporaneous) | 3.18 | [3.04, …] | ~16k | 0.06 → 0.474 |
| **Landmark first-24 h NEE → post-landmark death (age-adj)** | **2.57** | **[2.45, 2.68]** | 23,925 | **0.060 → 0.097 → 0.149 → 0.334** (monotone) |
| **Landmark + age + lactate** | **2.27** | **[2.10, 2.48]** | 7,452 | — |
| Dopamine NEE weight 0.05 (vs 0.01) sensitivity | 2.60 | [2.49, 2.72] | 23,925 | 0.058 → 0.097 → 0.153 → 0.333 |

Cohort: 25,119 stays with any pressor in the first 24 h; **1,194 (4.8%) excluded for dying before
the 24 h landmark**; post-landmark in-hospital mortality 16.0%.

## Reading
- The exposure (NEE) is measured **entirely within the first 24 h**, and the outcome (death) is
  restricted to **after** that window. Reverse causation / end-of-life dose escalation cannot
  generate this association — the dose is fixed before the outcome clock starts.
- The effect **attenuates modestly but does not collapse**: whole-stay OR 3.18 → landmarked 2.57
  (age) → 2.27 (age + lactate). A tautology would have collapsed toward 1.0; instead a steep,
  monotone, severity-adjusted dose-response remains.
- **Dopamine-weight critique neutralized:** OR 2.57 (weight 0.01) vs 2.60 (weight 0.05) — the
  MODERATE concern about dopamine underweighting changes nothing.
- This converts Finding 4 from "possibly descriptive epidemiology (dying patients get more
  pressor)" into a **genuine prospective risk-stratifier**: first-24 h vasopressor burden grades
  later mortality, beyond age and lactate.

## Honest scope (unchanged)
Still observational; NEE co-varies with shock severity; lactate is a single severity handle (not a
full SOFA). The landmark defeats the *temporal/tautology* attack specifically. The cross-cohort
"replication" framing is separately corrected (see REDTEAM_PUBLICATION_VERDICT.md): MIMIC OR 2.57
and INSPIRE OR 1.11 are **directionally concordant across different estimands**, not numerically
equal — do not call them a quantitative replication.
