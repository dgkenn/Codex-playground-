# Fluids emulation scoping — conservative vs liberal resuscitation (the biggest open ICU question)

## The open question
CLASSIC (Meyhoff, NEJM 2022) and CLOVERS (NHLBI, NEJM 2023) both came out **neutral/underpowered**; the field
is genuinely split on whether restrictive fluid resuscitation in sepsis/septic shock improves outcomes. This is
practice-defining, affects nearly every ICU patient, and is exactly the kind of unsettled question a rigorous
cross-national emulation could move.

## The exposure (what "restrictive vs liberal" means operationally)
Primary exposure = **cumulative resuscitation-fluid volume in the first 24h** (crystalloid + colloid), and
secondarily **net fluid balance** (in − out) at 24/72h. CLASSIC/CLOVERS differ mainly in *volume given* and
*vasopressor-first vs fluid-first*, so volume + early-pressor timing are the key exposure axes.

## Cross-site data map
| site | fluid IN | fluid OUT (for balance) | verdict |
|---|---|---|---|
| **MIMIC-IV** | `inputevents` crystalloid/colloid itemids **CONFIRMED**: NaCl 0.9% 225158, NaCl 0.45% 225159, LR 225828, D5 220949, D50 220952, Free Water 225797, Albumin5% 220864, Hetastarch 225174 (all mL, timestamped, with rate) | `outputevents` (urine/drains) — **not yet downloaded** (small table, fetchable) | **input ready now; balance needs 1 download** |
| **eICU** | `intakeOutput.csv.gz` (celllabel/cellvaluenumeric, I/O events) + `infusionDrug` for fluids | same `intakeOutput` gives outputs | **feasible after download** |
| **SICdb** | fluids in `medication`/`data_*` (e.g. NaCl3% 220962, D5 already mapped); volume via medication.Amount | outputs via `data_range`/`unitlog` | **needs table-column confirmation on access (day-one grep, like the Hb IDs)** |

## Design (target-trial emulation, since there is NO clean IV)
Be explicit and honest: **fluid volume has no assay-noise or cross-method instrument** — it is confounded-by-
severity (sicker patients get more fluid AND do worse). So this is a **g-methods target-trial emulation**, not an
IV:
- **Time-zero:** sepsis/septic-shock onset (first vasopressor or lactate≥2 + infection), per SEPSISPAM/CLOVERS.
- **Eligibility:** adult ICU, septic shock, within 24h of onset (mirror CLOVERS/CLASSIC inclusion).
- **Strategies:** restrictive (≤ site-median 24h volume, pressor-first) vs liberal (> median, fluid-first) —
  or the CLOVERS-style protocolized arms operationalized from the data.
- **Confounding control:** **time-varying** — baseline (age, comorbidity, SOFA/SAPS3, source) + time-varying
  (MAP, lactate, pressor dose, urine output, mech-vent) via **IPTW with time-varying weights / marginal
  structural model** (g-formula sensitivity).
- **Outcome:** 28-/90-day mortality (primary); AKI/RRT, ventilator-free days (secondary).
- **Bias battery (our standard):** negative-control outcome the fluid strategy should not cause; E-value;
  and — critically — **cross-national convergence** (MIMIC + eICU + SICdb) as the external-validity anchor.

## Honest ceiling
No IV means residual confounding can never be fully excluded — so the deliverable is a **rigorously-controlled,
cross-nationally-convergent observational answer + a bias battery**, framed as strong evidence and a
hypothesis-sharpening result for the next trial, not proof. Its impact rides on (a) the size of the open
question, (b) three-country convergence, and (c) methodological rigor (time-varying confounding + negative
controls) — the same honest posture as the SEPSISPAM MAP battery.

## Feasibility verdict
- **MIMIC arm: buildable now** (fluid inputs on hand; fetch `outputevents` for balance). Start here.
- **eICU arm:** buildable after the queued eICU download (`intakeOutput`, `patient`, `apachePatientResult`).
- **SICdb arm:** buildable after confirming the fluid/output columns in `medication`/`data_*` on access.
- Recommended first step: MIMIC septic-shock fluid target-trial emulation (input-volume exposure + IPTW),
  reusing the `sepsispam_mimic.py` cohort/severity machinery, then add balance once `outputevents` lands.
