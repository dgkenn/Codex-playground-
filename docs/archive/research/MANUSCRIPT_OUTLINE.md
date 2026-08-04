# Manuscript Outline & Publication Plan

How the findings in this repository map to submittable papers, what is ready, and what
still gates the highest-tier claims. Numbers are in the findings docs and the
authoritative log; this document is the packaging plan.

---

## Paper 1 (FLAGSHIP) — "Corrected calcium is racially miscalibrated: a measurement artifact of plasma globulins"

**Thesis.** The albumin-corrected-calcium formula built into every EHR omits globulin-bound
calcium and therefore **over-reads total calcium in Black patients at matched ionized
(true) calcium** — the *inverse* of the race-in-eGFR story: here the "correction" clinicians
trust *creates* racial bias rather than removing it. The deployable fix is ionized calcium
or a globulin-inclusive correction.

**Why this is the flagship.** It (a) is multi-site — ionized calcium exists in eICU/SICdb, so
it clears the single-center ceiling that caps sodium; (b) implicates a *specific formula in
production use*, making it actionable and equity-framed; (c) is well-powered (MIMIC n=25,163,
3,442 Black; z=+11.6) and survives albumin correction (z=+7.3).

**Target:** JAMA / NEJM (methods-equity) or a high-tier clinical-chemistry / informatics
journal. **Status: strongest submission-ready core**, pending final multi-site table polish.

| Element | Content | Source |
|---------|---------|--------|
| Fig 1 | Total Ca − ionized Ca bias by race at matched ionized (MIMIC) | Doc 01 |
| Fig 2 | Multi-site mechanism (MIMIC + SICdb protein dose-response) | Docs 01, 04 |
| Fig 3 | Corrected-calcium residual bias: raw vs albumin-corrected vs globulin-inclusive | `correction_tool.py`, Doc 01 |
| Table 1 | Cohort characteristics, masked-hypocalcemia prevalence by race | Doc 01 |
| Limits | Threshold-dependence (mild vs severe reversal), Berkson selection | Doc 01 |

---

## Paper 2 (COMPANION) — "Racial electrolyte disparities are partly a measurement artifact"

**Thesis.** Published racial differences in dyselectrolytemia (hyponatremia, hyperchloremia,
hypocalcemia) are **partly artifacts of indirect-ISE measurement physics**: when the *true*
(blood-gas / ionized) value is used, ~90% of the hypocalcemia gap and ~100% of the
hyperchloremia gap disappear, and the hyponatremia disparity attenuates/reverses.

**Why it matters.** This reframes an existing epidemiology literature, not just one assay —
the highest-leverage scientific payload of the sodium/chloride line.

**Target:** research letter / methods paper. **Status:** core numbers solid; the *racial*
sodium axis is single-center (MIMIC), so honesty about the ceiling is required (the mechanism
is cross-national via SICdb; the disparities-reframe rests on MIMIC + independent osmolality).

| Element | Content | Source |
|---------|---------|--------|
| Fig 1 | Sodium bias by race, chem vs blood-gas and vs osmolality | Doc 03 |
| Fig 2 | Disparity gap by *reported* vs *true* value (Na, Cl, Ca) | Doc 03 |
| Table 1 | Robustness ladder (confounders, IPW, clustering, Hct, disease-exclusion) | Doc 03 |

---

## Paper 3 (MECHANISM NOTE) — "Immunoglobulins as a shared driver of panel-wide racial assay bias"

**Thesis.** One mechanism — higher plasma globulins/immunoglobulins — produces a
**coordinated** signature: Na↓, Cl↓ (water displacement / indirect ISE), Ca↑ (protein
binding), with directions matching known chemistry. Graded protein/IgG/cholesterol
dose-response; cross-ethnic (Hispanic, Asian); cross-national (SICdb).

**Target:** clinical-chemistry / laboratory-medicine journal, or fused into Paper 1's mechanism
section. **Status:** the **most robust layer** (SICdb z=−28.6 / z=+39.6, monotone quartiles).

| Element | Content | Source |
|---------|---------|--------|
| Fig 1 | Protein-quartile dose-response, MIMIC + SICdb | Doc 04 |
| Fig 2 | IgG-by-race + cross-ethnic sodium bias | Doc 04 |
| Table 1 | Coordinated panel (Na/Cl/Ca directions, one mechanism) | Docs 01, 04 |

---

## Paper 4 (SAFETY LETTER, hypothesis-generating) — "Racial disparity in false-hyperkalemia alarms"

**Thesis.** Chemistry potassium reads falsely high vs blood-gas potassium more often in Black
patients (false-hyperkalemia OR 2.36; 13.5% vs 6.3%) — a *distinct*, pre-analytic mechanism
(opposite sign from the protein effect). False alarms can trigger insulin/dextrose,
cation-exchange resin, or dialysis. The ECG partially corroborates that the flagged values are
electrically silent (no hyperkalemic changes).

**Target:** safety/quality letter. **Status: hypothesis-generating** — mechanism inferred
(hemolysis/pre-analytic, not directly confirmed); the treatment-harm chain is untested.

---

## What is NOT ready (do not submit as confirmatory)

- **The hard clinical-outcome harm** (masked hypocalcemia → unrecognized long QT →
  ventricular arrhythmia / mortality). Red-team-fragile: tiny event counts (e.g. 26 vs 3),
  extreme selection, unverifiable temporality; **eICU mortality does not replicate.** Belongs
  in a paper only as a clearly-labeled hypothesis motivating prospective work. *(Doc 05)*
- **Treatment/overcorrection harm** for sodium (hypertonic saline on false-low Na): n=21,
  CI crosses 1. *(Docs 03, 05)*
- **A second cohort showing the *race* gap for sodium directly** — structurally requires a
  US multi-hospital dataset with race + paired blood-gas sodium, which does not currently
  exist in the accessed sources. This is why calcium, not sodium, leads.

---

## Cross-cutting framing assets

- **The eGFR-inversion hook.** Race-in-eGFR was removed because a *race term* biased results;
  here a race-*neutral* formula (albumin-corrected calcium) is *already* biased because it
  omits globulin. Same equity conversation, opposite mechanism — a strong narrative frame for
  Paper 1.
- **The "measure the quantity directly" principle.** Every finding points the same way: prefer
  direct measurement of the physiological quantity (direct-ISE Na/Cl, ionized Ca, free drug
  levels) over protein-sensitive inference. A clean discussion-section throughline.

---

## Submission-readiness summary

| Paper | Core evidence | Multi-site? | Ready? |
|-------|--------------|-------------|--------|
| 1 — Corrected calcium | Durable, well-powered | **Yes** (MIMIC+eICU+SICdb) | **Closest to ready** |
| 2 — Disparities artifact | Durable core; race axis single-center | Mechanism yes, race no | Ready as research letter w/ honest ceiling |
| 3 — Mechanism | Most robust layer | **Yes** (SICdb) | Ready (standalone or fused) |
| 4 — Pseudohyperkalemia | Solid cross-section; mechanism inferred | Single-center | Ready as hypothesis-generating letter |
| — Hard outcome | Fragile | No (eICU null) | **Not ready** — hypothesis only |
