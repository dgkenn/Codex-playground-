# Racial Measurement Bias in Clinical Laboratory Tests — Research Repository

**A central, publication-oriented archive of a multi-cohort investigation into how
plasma-protein / immunoglobulin differences between racial groups produce
*systematic measurement bias* in routine clinical chemistry — and what that means
for diagnosis, disparities epidemiology, and patient safety.**

Author working repo: `docs/research/`. Authoritative raw analysis log (every exact
number, every review round): [`../REAL_RESULTS_SODIUM_RACE_BIAS.md`](../REAL_RESULTS_SODIUM_RACE_BIAS.md).
All statistics in these documents are copied verbatim from that log.

---

## The through-line (one paragraph)

Higher plasma globulins / immunoglobulins in non-White populations perturb several
routine assays *through their measurement physics*, not through any true
physiological difference. The extra plasma solid phase makes **indirect-ISE sodium
and chloride read falsely low** (electrolyte-exclusion / water-displacement), while
globulin binding makes **total calcium read falsely high** (protein-bound calcium).
A separate, pre-analytic mechanism makes **serum/chemistry potassium read falsely
high** (pseudohyperkalemia). These are not four coincidences: three of them share
**one mechanism** (excess plasma protein) with directions that match known
chemistry, and each is measured at matched *true* value (blood-gas / ionized
reference) so the bias cannot be a real physiological difference. The consequence is
**differential diagnostic misclassification by race** — false-hyponatremia labels,
masked hypocalcemia, false-hyperkalemia alarms — and a reframing of parts of the
published racial dyselectrolytemia literature as *measurement artifact*.

---

## Documents in this repository

| # | File | What it establishes | Evidentiary standing |
|---|------|--------------------|----------------------|
| — | [`README.md`](README.md) | This index + through-line + roadmap | — |
| 01 | [`01_FLAGSHIP_calcium_and_panel.md`](01_FLAGSHIP_calcium_and_panel.md) | Total-calcium reads falsely high at matched ionized Ca (MIMIC z=+11.6); replicates across sites; corrected-calcium formula fails by race; the coordinated panel (Na↓, Cl↓, Ca↑) | **Durable / multi-site.** The wall-breaker: ionized Ca exists in eICU/SICdb, so calcium escaped the single-center ceiling that capped sodium. |
| 02 | [`02_potassium_pseudohyperkalemia.md`](02_potassium_pseudohyperkalemia.md) | Chemistry K reads falsely high vs blood-gas K; false-hyperkalemia OR 2.36 (Black 13.5% vs White 6.3%); a *distinct* pre-analytic mechanism (opposite sign from protein) | **Durable, single-center; mechanism inferred.** ECG partially corroborates spuriousness. |
| 03 | [`03_sodium_and_artifactual_disparities.md`](03_sodium_and_artifactual_disparities.md) | The original sodium finding (chem−bloodgas −1.18 mEq/L, z=−12.6); the single-center ceiling; **known racial electrolyte disparities are partly measurement artifact** (hypocalcemia ~90%, hyperchloremia ~100%) | **Racial axis single-center; mechanism cross-national (SICdb).** The disparities-reframe is the scientific payload. |
| 04 | [`04_mechanism_immunoglobulins.md`](04_mechanism_immunoglobulins.md) | The upstream biology: globulin / IgG / cholesterol dose-response; cross-ethnic replication (Hispanic, Asian); literature; myeloma/paraprotein link | **Mechanism is the most robust layer** — cross-national (SICdb z=−28.6/−39.6), graded, cross-reference. |
| 05 | [`05_consequences_outcomes_and_limits.md`](05_consequences_outcomes_and_limits.md) | Misclassification consequences (solid); ECG arbitration; the hard arrhythmia/mortality outcome chain; consolidated review history | **Consequences durable; hard-outcome chain HYPOTHESIS-GENERATING** (fragile, does not replicate in eICU). |
| M | [`METHODS_AND_REPRODUCIBILITY.md`](METHODS_AND_REPRODUCIBILITY.md) | Data sources, cohort construction, statistical methods, script inventory | — |
| P | [`MANUSCRIPT_OUTLINE.md`](MANUSCRIPT_OUTLINE.md) | Proposed papers, target journals, figure/table plan, what is submission-ready vs not | — |

---

## What is durable vs what is hypothesis-generating

**This distinction is load-bearing. Do not blur it in any downstream write-up.**

### Durable (multi-site and/or mechanistically airtight)
- **Total calcium is racially miscalibrated at matched ionized calcium** (MIMIC z=+11.6;
  survives albumin correction z=+7.3; mechanism replicates SICdb z=+39.6). *(Doc 01)*
- **The protein → indirect-ISE mechanism** — graded dose-response, monotone across
  protein quartiles, replicated cross-nationally in SICdb (−0.843 mEq/L per g/dL,
  z=−28.6) and against an independent osmolality reference (z=−9.3). *(Docs 03, 04)*
- **Differential misclassification**: false-hyponatremia label (adj OR 1.68, z=+3.0);
  masked mild hypocalcemia (26.2% vs 18.1%); false-hyperkalemia (adj OR 2.36). *(Docs 01, 02, 05)*
- **The artifactual-disparities reframe**: ~90% of the reported Black−White hypocalcemia
  gap and ~100% of the hyperchloremia gap disappear when the *true* (ionized / blood-gas)
  value is used. *(Doc 03)*

### Single-center (racial axis) — mechanism portable, race gap not yet multi-site
- The **sodium racial differential** exists cleanly only in MIMIC (paired chem +
  blood-gas + race). eICU/SICdb lack paired blood-gas sodium *with* race, so the
  sodium *race* gap is not multi-site. Calcium (Doc 01) is what solved this. *(Doc 03)*

### Hypothesis-generating (explicitly NOT confirmatory)
- The **hard clinical-outcome chain** — masked hypocalcemia → unrecognized long QT →
  ventricular arrhythmia / mortality — is **fragile**: tiny event counts (e.g. 26 vs 3),
  extreme selection, unverifiable temporality, and **eICU mortality does not replicate**.
  Red-team tempered. Report as hypothesis-generating only. *(Doc 05)*
- The **treatment/overcorrection harm** (e.g. hypertonic saline given on a false-low
  sodium) is underpowered (n=21, CI crosses 1). *(Docs 03, 05)*

---

## Publication roadmap (short version — full detail in `MANUSCRIPT_OUTLINE.md`)

1. **Flagship methods/equity paper — "Corrected calcium is racially miscalibrated."**
   The strongest standalone: a formula in every EHR (albumin-corrected calcium) omits
   globulin and therefore over-reads calcium by race; the fix is ionized calcium or a
   globulin-inclusive correction. Multi-site, actionable, an *inverted* analog of the
   race-in-eGFR story (here the correction *creates* rather than removes bias).
2. **Companion / research-letter — "Racial electrolyte disparities are partly a
   measurement artifact"** (sodium + chloride + the disparities reframe).
3. **Mechanism note** — the immunoglobulin dose-response tying the panel together.
4. **Hypothesis-generating letter** — pseudohyperkalemia false-alarm burden by race,
   framed as a safety signal requiring prospective confirmation.

---

## Data sources (see `METHODS_AND_REPRODUCIBILITY.md` for detail)

| Cohort | Role | Race? | Key paired reference |
|--------|------|-------|----------------------|
| **MIMIC-IV** (Boston) | Primary — racial differential | Yes | blood-gas Na/K/Cl, ionized Ca |
| **eICU-CRD** (208 hospitals) | Multi-site — calcium racial replication; sodium mechanism | Yes | ionized Ca; osmolality-reconstructed Na |
| **SICdb** (Salzburg, Austria) | Cross-national mechanism | No | dual-method protein dose-response |
| **MIMIC-IV-ECG** (800,036 ECGs) | Independent physiological arbiter | via link | machine QTc / QRS / PR |

---

## Integrity notes (do not weaken)

- **No PHI / raw patient data is committed.** Raw extracts and analysis scripts live in
  the gitignored `scratchpad/`; only these aggregate, de-identified documents and (where
  useful) code are versioned.
- **Every number is copied from the authoritative log**, not re-derived from memory.
  Where the log carries two related figures (e.g. mechanism slope in two units), both
  are preserved rather than silently reconciled.
- **Honest caveats are mandatory.** The single-center / hypothesis-generating boundaries
  above are part of the finding, not a disclaimer to be trimmed for impact.
