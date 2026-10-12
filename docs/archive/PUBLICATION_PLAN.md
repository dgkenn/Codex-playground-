# Publication plan — the de-confounding program (what the papers are, their claims, and gaps)

The work has cohered into a clear, sequenced set of deliverables. This is the map: each paper, its core claim,
what is DONE vs PENDING (data only vs method), and the venue. Index of supporting docs at the bottom.

## Paper 1 (METHODS FLAGSHIP) — "A trigger-matched toolkit for de-confounding reflexive inpatient care"
**Claim:** confounding-by-indication for reflexive care is not defeated by one instrument but by MATCHING the
instrument to how the treatment is triggered — and the resulting toolkit, calibrated against known-truth RCTs,
recovers the established answers from data whose naive analysis shows confounding.
**Contents:** the trigger taxonomy (lab-flag→assay-noise; contraindication-gate→gate-noise-IV; gestalt→
provider-IV; +nurse-PRN IV; +attending-rotation RDD); the mandatory-negative-control result (balance is
insufficient — sim-proven); RCT-anchored certification (4 known-truth cases: TRICC/TRISS, DKA-bicarb, Stanworth,
MIND-USA); triangulation bounds; deployed across the 10-trial portfolio.
**DONE:** taxonomy, all 5 instruments coded, NC-mandatory proof, known-truth sim, triangulation, pre-registration.
**PENDING (data only):** the real naive-vs-method table on the 4 certification cases + portfolio.
**Novel pieces (defensible):** contraindication-gate noise-IV, nurse-PRN administration IV, attending-rotation
time-RDD; the trigger-matching framework itself; the "balance-insufficient / NC-mandatory" demonstration.
**Venue:** a top methods-forward clinical journal / methods journal.

## Paper 2 (STATISTICAL METHODS) — "Assay-noise instrumental variables for lab-triggered treatment"
**Claim:** measurement noise at a clinical decision threshold is a formal, estimable instrument (built from assay
CV / serial-pair variance), extended to a renewal structure of repeated noise-randomized decisions with a
terminal outcome; identifies the flag-policy effect precisely and the per-patient LATE weakly.
**Contents:** identification + renewal derivation; the leaky-control simulation (which control is valid, and why
the midpoint is unbiased under equal-variance noise while M1-only is not); power/MDE (LATE weak, flag-ITT
decisive); validation on transfusion vs Bosch 2022 (formal noise model extends their fuzzy RDD).
**DONE:** identification, renewal, simulation, power/MDE, prior-art position.
**PENDING (data only):** the real Mg + Hb battery numbers.
**Venue:** Biometrics / AJE / Statistics in Medicine.

## Paper 3 series (CLINICAL de-implementation) — one per vacuum trial that passes the gates
Each evidence-vacuum trial that clears the bulletproof battery + NC calibration + triangulation is a clinical
paper (null or effect, both publishable per the operating principle). Priority:
- **Mg/K repletion** (huge scale, zero RCTs) — the flagship clinical target; RESTRAINT RCT protocol already drafted.
- **Benzodiazepine-for-sleep in older inpatients** (provider-IV, cleanest indication).
- **Opioid intensity, post-op within-procedure** (provider-IV).
- **Mild bicarbonate / phosphate / calcium repletion** (gate/lab-flag).
**PENDING:** data + gate results decide which qualify.
**Venue:** JAMA IM / Annals / specialty journals; RESTRAINT trial itself → NEJM/JAMA.

## The certification logic that underwrites all three (the reviewer-proof spine)
1. Run the 4 known-truth cases → method must recover the RCT answers while naive shows false harm
   (`VALIDATION_KNOWN_TRUTH.md`). This is the gate; without it nothing else is trusted.
2. Every estimate carries its falsification battery + NC empirical-null calibration (`BULLETPROOF_CHECKLIST.md`).
3. Vacuum estimates are triangulated into convergent bounds; a passed trial is publishable whatever its sign,
   a failed gate is a publishable methods result.

## Immediate critical path
Only the throttled MIMIC download blocks the real numbers. Order of results as data lands:
labevents → (Paper 2 Mg battery + Paper 1 certification cases RBC/platelet/bicarb) ; prescriptions →
(provider-IV: antipsychotic certification + gestalt trials) ; emar → (nurse-PRN IV). NC panel already built.

## Doc index
- Taxonomy + 10 trials: `PORTFOLIO_10_TRIALS.md`; bespoke methods for the 6: `BESPOKE_METHODS_6_TRIALS.md`
- Method core: `ASSAY_NOISE_IV_METHODOLOGY.md`, `ASSAY_NOISE_IV_SIMULATION.md`, `DECONFOUNDING_GAP_ANALYSIS.md`
- Bulletproofing: `BULLETPROOF_CHECKLIST.md`, `SIM_INSTRUMENTS_RESULTS.md`, `VALIDATION_KNOWN_TRUTH.md`
- Packaging: `DECONFOUNDING_TRIANGULATION.md`, `DECONFOUNDING_PREREGISTRATION.md`
- Engines (code): `portfolio_run.py`, `gate_run.py`, `provider_iv.py`, `attending_rdd.py`, `nurse_prn_iv.py`,
  `negcontrol.py`, `nc_panel.py`, `triangulate.py`, `sim_*.py`, `validation_sim.py`
- Clinical: `ELECTROLYTE_DEIMPLEMENTATION_RCT_PROTOCOL.md`, `ELECTROLYTE_CASE_FOR_RCT.md`
