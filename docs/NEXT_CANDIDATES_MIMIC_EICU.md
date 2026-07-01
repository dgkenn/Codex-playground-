# Cycle-6 candidate slate (MIMIC-IV ↔ eICU, externally-validatable) + feasibility reality-check

Vetted by a delegated sonnet idea-gen + PubMed novelty screen under the full trap list. Ranked by the
re-rank principle (external-validation-by-construction + decision/mechanism, not a marginal marker).

## Candidate 1 (agent's TOP pick) — "which channel fires first": vitals-first vs labs-first ward deterioration → outcome
- **Question (MECHANISM, not treatment decision):** for ward patients escalated to ICU, classify the
  pre-transfer trigger as vitals-first (HR/RR/SpO2/BP crosses threshold, labs still normal) vs labs-first
  (lactate/creatinine/WBC abnormal, vitals normal) vs simultaneous; does detection *modality* shape
  time-to-treatment / LOS / 30-day mortality, independent of severity? Novelty: **NOVEL** (0 PubMed hits).
- **Biggest threat:** surveillance-intensity confound → matched-surveillance target-trial + landmark at
  trigger + negative-control outcome/exposure + E-value.
- **FEASIBILITY: BLOCKED on MIMIC-IV (make-or-break gate FAILED).** MIMIC-IV `chartevents` is **ICU-module
  only** — routine *ward* vitals don't exist in MIMIC-IV; the only pre-ICU vitals are in the separate
  **MIMIC-IV-ED** module (ED, not ward). No `transfers`/`chartevents` cached either. The core exposure
  (vitals-first in the ward) is not constructable; reframing to ED breaks the eICU external-validation
  symmetry. **→ Not runnable as designed without an ED reframe that weakens the EV story.** Gate did its job.

## Candidate 2 — active de-resuscitation (diuretic-driven net-negative balance after shock resolution), landmarked
- Landmark target-trial emulation of the *decision* to actively de-resuscitate; MIMIC→eICU.
- Novelty: **INCREMENTAL topic (de-resuscitation is live: ADQI, RADAR-2), but the landmarked causal design +
  eICU replication is close to novel.**
- **Biggest threat = textbook confounding-by-indication** (the exact trap that capped vasopressor +
  liberation-order, both → OR≈1.35). Needs strict shock-resolution landmark, full severity-at-landmark
  vector (SOFA/lactate/UO/creatinine), negative-control exposure+outcome, up-front E-value. **Budget for a
  plausible null.**
- **Feasibility:** needs `inputevents` (fluids/vasopressors/diuretics), `outputevents` (not cached),
  `labevents` (cached); eICU `infusionDrug` (cached) + `intakeOutput` (not cached). Moderate download+eng.

## Candidate 3 — antibiotic de-escalation timing vs CULTURE-TURNAROUND landmark (quasi-natural-experiment)
- Uses microbiology lab turnaround (exogenous to patient severity) as an instrument-like timer for the
  de-escalation decision → C.diff/MDRO acquisition, antibiotic-days, mortality. Cleverest confound dodge.
- Novelty: **NOVEL-leaning** (must confirm PMID 30808257 isn't a direct collision first).
- **Feasibility:** needs `microbiologyevents` (moderate) + `prescriptions` (large, antibiotic-spectrum
  classification work) + `labevents`; eICU `microLab` + `medication`. Cheapest to gate (confirm the 1
  potential prior-art collision), lowest impact ceiling. Infection endpoint ~150–400 events (check MDE).

## BANKED LESSON (bank in LESSONS.md)
The agent's sharpest catch: our two prior properly-adjusted treatment-decision studies (vasopressor
dose→mortality; 3-way liberation-order) converged on the **identical OR ≈ 1.35 / E-value ≈ 1.83**. That
coincidence suggests a **structural ceiling** for observational ICU treatment-decision designs once
severity-at-decision is honestly adjusted — i.e., Candidates 2/3 (both treatment decisions) likely top out
there too. **Mechanism questions (Candidate 1) are the structurally cleaner class** — but Candidate 1 is
blocked by the MIMIC-IV ward-vitals data gap. This is the real strategic bind to resolve.

## Decision needed (data/direction)
Every runnable path needs new credentialed downloads + data engineering. Options:
- **A.** Candidate 1 via **MIMIC-IV-ED** (ED triage+vitals+labs exist there) as discovery — accept a weaker
  external-validation story (eICU has no clean ED analog) or find an ED replication cohort.
- **B.** Candidate 2 (de-resuscitation) — download `inputevents`/`outputevents` + eICU `intakeOutput`;
  strongest EV-by-construction, but budget for the OR≈1.35 ceiling.
- **C.** Candidate 3 (culture-turnaround natural experiment) — cheapest gate, novel design, lower ceiling.
- **D.** Different direction entirely (e.g., provision GPU for the EEG-FM fine-tuning that the evidence says
  is the real lever for the flagship).
