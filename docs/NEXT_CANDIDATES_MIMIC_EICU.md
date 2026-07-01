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

## SELECTED: Candidate 3 — make-or-break gate PASSED (streamed, disk-sparing)
User: "keep moving the cycle, stream disk-sparing." Picked Candidate 3 (natural-experiment class beats the
OR≈1.35 treatment-decision ceiling; novelty survived — the one potential collision PMID 30808257 is a
narrative review, not this design). Streamed MIMIC-IV v3.1 `microbiologyevents` (400k-row sample) via
`wget --netrc | python` (no raw data to disk):
- **charttime + storetime present on 91.5% of rows** → the order→result timer is well-populated.
- **Culture turnaround varies 8×**: p10 18 h / p50 60 h / p90 143 h — the exogenous variation the
  quasi-instrument needs (driven by organism growth kinetics + lab logistics, not patient severity).
- **Susceptibility at scale**: S/R/I interpretations (113k S / 24k R / 3.8k I) + org_name on ~41% of rows;
  blood cultures 80k, urine 135k. 20,041 distinct admissions in the first 400k rows alone.
- **VERDICT: feasible.** Next streamed sub-gates: (1) antibiotic exposure + de-escalation from
  `prescriptions`/`emar` (broad-spectrum empiric → narrowing after storetime); (2) outcomes (mortality =
  cached `admissions.hospital_expire_flag`; C.diff/MDRO from later cultures/`diagnoses_icd`); (3) confirm
  eICU `microLab` has the analog order/result timestamps for external validation.

### Antibiotic sub-gate — PASSED (streamed `prescriptions` 500k-row sample, disk-sparing)
- 23,140 antibiotic courses in the sample (15,840 broad-spectrum, 7,300 narrow); **99.8% have both
  `starttime` and `stoptime`** → course timing fully available for de-escalation detection.
- Broad-spectrum empiric agents well-represented: vancomycin 6,325; ciprofloxacin 1,899; ceftriaxone 1,860;
  cefepime 1,851; piperacillin(-tazo) 1,374; meropenem 647; ceftazidime, daptomycin, linezolid. 5,832
  distinct admissions with antibiotics in the first 500k rows alone → large abx cohort in the full table.
- **BOTH halves of the natural experiment confirmed in MIMIC-IV.** Design is fully constructable.

### NEXT STEP (in progress) — build the linked per-admission cohort (disk-sparing, two streamed passes)
Stream `microbiologyevents` once → keep only compact per-hadm culture summary (first blood/urine culture
order time, its storetime=result-available, organism, any Resistant flag). Stream `prescriptions` once →
compact per-hadm antibiotic course list (drug, broad/narrow, start, stop). Join in memory on hadm_id.
Exposure = de-escalation (broad→narrow or stop) within Δh of the culture storetime; instrument = culture
turnaround (storetime−charttime); outcomes = in-hospital mortality (cached admissions) + antibiotic-days.
Then eICU `microLab`+`medication` replication. Keep only the compact joined table on disk, never raw.

### Instrument cohort BUILT (streamed full `microbiologyevents`, 3.99M rows, disk-sparing)
**201,009 admissions with an index culture** (of 201,096 with any culture) — per-admission summary
(index charttime, storetime, turnaround_h, organism-grew, any-Resistant, specimen) kept in scratchpad only
(MIMIC-derived row-level → never committed). This is the natural-experiment substrate: the culture-turnaround
instrument is available for ~201k admissions. `prescriptions` (~17M rows) streaming to add the antibiotic
exposure side; then in-memory join on hadm_id → first de-escalation-vs-turnaround signal + in-hospital
mortality (cached `admissions`). Proxy bandwidth ~300k rows/min → prescriptions is the slow step (~50 min).

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
