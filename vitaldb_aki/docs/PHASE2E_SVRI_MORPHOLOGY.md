# Phase 2e — SVRI-Morphology Generative-Counterfactual (interpret a waveform→vascular-tone predictor)

**Status: SPECIFIED + GATED. Feasibility GO; DL predictor not yet built.** The strongest
Phase-2 variant in this project, because its target is a **measured physiologic quantity
(SVRI)**, not a severity-confounded outcome.

**One-line thesis:** Train a black-box DL predictor of measured systemic vascular
resistance index (SVRI) from the arterial waveform, then use the Phase-2
generative-counterfactual method to reveal the waveform **morphology that encodes
vascular tone beyond the known scalar indices** (τ, augmentation index) — a novel,
falsifiable, mechanism-anchored vasoplegia biomarker.

---

## Why this is a BETTER Phase-2 candidate than the organ-injury arm

The original arterial Phase 2 (PHASE2_GENERATIVE_COUNTERFACTUAL.md) interprets a
waveform→**organ-injury** predictor. This project learned repeatedly that organ-injury
prediction is saturated with **confounding by severity** (the negative-control /
specificity battery killed every outcome-prediction biomarker). Interpreting such a
predictor risks laundering "sicker patient" into a fake morphology.

A waveform→**SVRI** predictor has **no severity confound** — SVRI is a measured
resistance, not an outcome. The only leak to guard is **circularity with mean pressure**
(SVRI = 80·(MAP−CVP)/CO, so a predictor that re-reads MAP is cheating), which maps
exactly onto the existing **residual-beyond-scalars** safeguard: the discovered
morphology must survive conditioning on MAP / pulse-pressure. This makes the gate's
hardest requirement — *prove the predictor isn't reading a confound* — far more
tractable.

---

## Feasibility (GO — established CPU-only, no GPU)

`analysis/svri_morphology_feasibility.py` on the direct-EV1000-SVR cohort
(co-extraction of waveform morphology + measured SVRI), N≈131 and growing:
- **(A) Non-circular:** waveform morphology adds **incremental R² ≈ 0.13** for predicting
  SVRI OVER mean pressure → there IS tone-encoding shape beyond MAP.
- **(B) DL-upside:** full morphology (out-of-fold Spearman r ≈ 0.46) beats the hand-built
  scalar vasoplegia index (r ≈ 0.36) → richer signal than τ/AIx alone, room for a
  generative model to discover more. (Ridge on summary features is a *lower bound* on
  what a DL model on the raw waveform could extract.)
→ **GO**: there is non-circular, beyond-scalar waveform signal for vascular tone worth a
DL + generative investment.

---

## BINDING PREREQUISITE (the gate)

A generative-counterfactual engine amplifies whatever the predictor learned. Phase 2e may
run only after the DL waveform→SVRI predictor has, on the LOCKED test partition:
1. **Non-circular** — incremental over MAP + pulse-pressure (not pressure rediscovered).
2. **Incremental over the hand-built scalar index** (τ/diastolic-MAP/form-factor/AIx) —
   else there is nothing beyond known morphology to interpret.
3. **Passed the leakage battery** — waveform-only inputs; no circular CO/SVR covariate.

Gate contract (`analysis/phase2_prereq_guard.py`, gate `svri_morphology`): refuses to
start unless `cache/svri_predictor_validated.json` exists with
`{"waveform_only_incremental_over_pressure": true, "incremental_over_scalar_index": true,
"leakage_battery": "pass", "locked_test": true}`. Today absent → correctly blocked.

---

## Method
1. Self-supervised generative model of the arterial waveform (VAE/diffusion/flow), all
   VitalDB ART, no label (reuse the shared §9 representation / the Phase-2 generator).
2. DL predictor: raw waveform → measured SVRI, trained on the ART∩CO cohort; validated
   per the gate.
3. Latent optimization to max/min predicted SVRI on the realistic-waveform manifold;
   synthesize matched high-tone vs low-tone (vasoplegic) exemplars.
4. Operationalize the difference as a measurable feature (a refined decay/notch/contour
   quantity) — beyond τ and AIx.
5. **Residual-beyond-pressure test:** report only the morphology that survives
   conditioning on MAP + pulse-pressure (tone at matched pressure).

## Confirmation
Compute the operationalized feature on real beats; test incremental value for SVRI (and
secondarily for the vasoplegia/fluid-vs-pressor decision) over MAP + pulse-pressure + the
hand-built index, on the LOCKED test. External waveform+CO cohort = future work (INSPIRE
has no waveforms; the scalar surrogate is the only INSPIRE-testable piece).

## What it cannot establish
Causality; that synthetic exemplars map to real patients; generalization beyond VitalDB.
It reveals what the SVRI predictor reads; it does not prove a mechanism.

## Staging + feasibility (this host)
Feasibility GO is done (CPU). The DL predictor + generative model need a GPU + the ART
waveform corpus staged — not executable on this CPU-only host. Sequence: grow the
co-extraction → train+validate the leakage-clean, non-circular, index-incremental DL
SVRI predictor (write the gate marker) → Phase-2e generative counterfactual.

## References
- Obermeyer Z, et al. *Nature* (2026) — predictive+generative counterfactual method.
- analysis/svri_morphology_feasibility.py (the GO); docs/VASOPLEGIA_VALIDATION.md
  (construct validity r≈−0.34); PHASE2_GENERATIVE_COUNTERFACTUAL.md (shared method+gate).
