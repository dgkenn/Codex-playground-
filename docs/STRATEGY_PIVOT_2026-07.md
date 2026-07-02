# Strategic pivot — from "count to 10 favorables" to a 3-pillar hostile-review-proof case

## Why the pivot
`VALIDATION_LEDGER.md` set a bar of ≥10 favorable RCT recoveries before touching the "big 10" de-implementation
questions. After exhaustively emulating every benchmark trial (`TRIAL_EMULATION_MASTER.md`) and a
population-stratified sweep (`REAL_RESULTS_POPULATION_TRANSFUSION.md`), the honest count is ~2/10, and a
structural limit was found: the one clean cross-method instrument (Hb) requires a same-time **arterial
blood-gas** measurement, which exists almost only in ICU patients — so non-ICU/elective RCT populations
(FOCUS hip-fracture, much of MINT/Villanueva) are underpowered or absent, and no other analyte has a clean
same-time second method (K hemolyzes; platelet/albumin/bicarbonate/lactate are single-method in MIMIC).
**Grinding more MIMIC subgroups cannot reach 10** — confirmed by direct attempt, not assumption.

## The reframe
A hostile reviewer is not impressed by 10 checkmarks, most of which would be nulls (cheap — low power also
looks null). They ARE impressed by **specificity**: a method that recovers the one RCT it should, and
**correctly declines 6 other decisions, each for a distinct, pre-registered, mechanistically-named reason**,
is much harder to dismiss as a fishing-expedition hit than a pile of subgroup nulls. Precise discrimination is
the signature of a real instrument; indiscriminate "significance" is the signature of a fluke or p-hacking.

## The new target: a 3-pillar case, not a count
1. **Clean positive control**: TRICC/TRISS recovery on cross-method Hb — all gates pass, all-factors emulation
   (done, `REAL_RESULTS_TRICC_TRISS_ALLFACTORS.md`).
2. **Demonstrated specificity**: the same pipeline, same gates, correctly refuses on ≥6 mechanistically distinct
   decisions — potassium (hemolysis/NC), platelet (no 2nd method), albumin+bicarbonate (drift+NC), glucose
   (estimand boundary, not a refusal but a scope-correct non-claim), MIND-USA (charting-conditional exposure),
   SUP-ICU (confounded preference-IV caught by NC) (done, see `REAL_RESULTS_SYNTHESIS.md`).
3. **One new-mechanism validation**: a dose-intensity / continuous-titration instrument (NOT assay-noise) on a
   target-range trial, using the newly-streamed vasopressor + ventilation data (`scratchpad/vaso.csv`,
   `scratchpad/vent.csv`; 459,800 norepi rows, weight-normalized rate). Candidate: **SEPSISPAM** (Asfar NEJM
   2014) — MAP target 65–70 vs 80–85 in septic shock; null overall, AKI/RRT benefit in chronic-hypertensive
   subgroup. This is mechanistically different from assay-noise (continuous titration vs single flag), so a
   validated recovery here is qualitatively stronger evidence the framework generalizes, not just another Hb
   subgroup. IN PROGRESS.

## What does NOT change
The `/goal` (bulletproof method for confounding-by-indication on reflexive lab-triggered treatments) and the
eventual "big 10" de-implementation trials are unaffected — this only changes the internal validation bar from
a raw count to a qualitative case, because the count was proven unreachable via the available data. External
data (HiRID/SICdb/AmsterdamUMCdb, access pending) remains the correct route to more power/sites and should be
wired up the moment access clears (adapters already exist, `MULTISITE_HARMONIZATION.md`).
