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
| **Landmark + FULL severity (age+lactate+creatinine+bilirubin+platelets+comorbidity)** | **1.74** | **[1.57, 1.91]** | 4,260 | — |
| Dopamine NEE weight 0.05 (vs 0.01) sensitivity | 2.60 | [2.49, 2.72] | 23,925 | 0.058 → 0.097 → 0.153 → 0.333 |

Cohort: 25,119 stays with any pressor in the first 24 h; **1,194 (4.8%) excluded for dying before
the 24 h landmark**; post-landmark in-hospital mortality 16.0%.

### Severity-adjustment depth (Round-1 red-team: causal Issue 3 + stats S2)
The first-24 h→post-landmark dose-response **survives progressive severity adjustment**, and the
attenuation is real adjustment, not complete-case selection:
- **S2 selection check** — age-only OR *within* the n=7,452 lactate-complete subset is **2.649
  [2.44, 2.91]** (≥ the full-cohort 2.57); adding lactate moves it to **2.272** → the 2.57→2.27 step is
  genuine lactate attenuation, not a lab-complete selection artifact.
- **Full SOFA-lab + comorbidity adjustment** (n=4,260 complete cases) — age-only **2.176** within that
  subset → fully adjusted **1.743 [1.573, 1.906]**; CI lower bound stays well above 1.0.
- **E-value of the fully-adjusted landmark** (p0=0.243): point 1.74 → **E-value 2.31**; CI lower bound
  1.57 → **E-value 2.11**. An unmeasured confounder would need RR ~2.1–2.3 with both first-24 h load and
  death, beyond age+lactate+SOFA-labs+comorbidity, to null it. **Correction:** the headline E-value ~6
  (full-cohort RR 3.27) does NOT transport to the landmark — cite **~2.1–2.3** for the prospective claim.
- **Residual SOFA gap (S4, disclosed):** still no GCS / PaO2-FiO2 (need chartevents ~30 GB); a complete
  SOFA could attenuate 1.74 modestly further.
- **Lactate temporal anchor (S6, disclosed):** `mimic_labs24h.csv` lactate is anchored to hospital
  admittime+24 h, not ICU intime+24 h; ward-to-ICU transfers can differ → possible mild under-adjustment.

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
