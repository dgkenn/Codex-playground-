# Phase 2b — Ce-Axis Drug-Response Counterfactual (Interpretable Depth Beyond Delta)

**Status: SPECIFIED + GATED. NOT YET RUNNABLE.** A short variant of the Phase 2
generative-counterfactual method (see PHASE2_GENERATIVE_COUNTERFACTUAL.md) that
pushes the latent along a **drug-exposure axis** instead of an outcome axis.

**One-line thesis:** Pair a generative model of the EEG with a *validated* predictor
of propofol effect-site concentration (Ce), synthesize the EEG morphology at HIGH vs
LOW Ce, and test whether any interpretable morphology survives **after matching delta
power**. If yes → the interpretable depth biomarker UCE was reaching for, on rigorous
footing. If no → a clean, publishable proof that depth-of-anaesthesia reduces to
delta. Either outcome is a real result, and both are distinct from NESI/MORGOTH
(supervised black-box indices, not interpretable drug-effect morphologies).

---

## The binding caveat (inherited, non-negotiable)

A generative-counterfactual engine **amplifies whatever the predictor learned,
including its confounds.** This is an explanation tool for an *already-validated*
predictor, NOT a discovery oracle. Pointed at raw signal/exposure pairs to "harvest
biomarkers," it manufactures plausible spurious features at scale (forking paths in a
visualization). Broadening the axis multiplies, not removes, the obligation to
validate the predictor first.

**Gate (binding).** The Ce predictor must be shown leakage-clean BEFORE synthesis:
- It predicts Ce **from the EEG only** — NOT from the infusion pump rate, drug-total
  covariates, or any non-EEG channel (the obvious leak: "reading the syringe").
- Negative controls ~chance on shuffled/duplicate-time data; no postop leakage.
- Held-out / locked-test predictive validity established.
Enforced via `phase2_prereq_guard` with marker `ce_predictor_validated.json`
(`{"ce_from_eeg_only": true, "leakage_battery": "pass", "locked_test": true}`).
Today: absent → blocked.

---

## Signal + models
- **Signal:** intraop EEG (VitalDB `BIS/EEG1_WAV` / `EEG2_WAV`, ~500 Hz, ~5871 cases).
  (The same machinery transfers to the a-line for an anaesthetic-haemodynamic-effect
  axis, but EEG is the depth case.)
- **Generative model:** self-supervised EEG generator (VAE / diffusion / flow),
  pretrained on ALL VitalDB EEG, no label. (Reuse as the §9 representation.)
- **Predictor:** Ce-from-EEG regressor (propofol `Orchestra/PPF20_CE`), validated
  leakage-clean per the gate.

## Procedure
1. Pretrain the EEG generator (self-supervised, all cases).
2. Validate the Ce-from-EEG predictor → write the gate marker.
3. **Latent-space** optimization to maximize / minimize predicted Ce, regularized to
   the realistic-EEG manifold (never raw-signal space).
4. Synthesize matched HIGH-Ce vs LOW-Ce EEG exemplars; visualize the morphology
   trajectory as Ce rises.
5. **Operationalize** the difference as a concrete EEG feature (spectral-edge shift,
   alpha-spindle/anteriorization morphology, burst-suppression onset, phase-amplitude
   coupling) — a measurable quantity, not a picture.

## The Residual-Beyond-Delta Test (the whole point)
Delta power is the canonical scalar correlate of anaesthetic depth — the EEG analog
of "the hypotension scalar."
- Synthesize HIGH-vs-LOW Ce **at MATCHED delta power** (condition the generation /
  re-weight on delta).
- Quantify how much of the counterfactual Ce shift is carried by delta vs **residual
  morphology** at matched delta.
- **Outcome A (residual survives):** a novel, interpretable depth-of-anaesthesia
  morphology beyond delta — what UCE was supposed to be, now generatively derived and
  scalar-residualized.
- **Outcome B (nothing survives):** depth-of-anaesthesia reduces to delta — a rigorous
  publishable negative that closes the question.

## Safeguards (same as Phase 2)
Manifold/realism constraint; adversarial check (Ce shift survives small
perturbations); stability across seeds, latent inits, predictor CV folds.

## Confirmation
Compute the operationalized feature on REAL EEG; test incremental value for predicting
Ce (and, secondarily, depth-related outcomes / delirium) over delta power + standard
EEG features, on the LOCKED test partition. No external EEG-with-Ce cohort assumed;
state plainly. Hypothesis-generating, not mechanism.

## What it cannot establish
Causality; that synthetic EEG exemplars map to real patient states; generalization
beyond VitalDB. It explains what the Ce predictor uses; it does not prove a mechanism
of anaesthetic action.

## Staging + feasibility (this host)
Same as Phase 2: needs a GPU + the full EEG corpus staged; not executable on this
CPU-only, flaky-proxy, ~38 GB, kill-cycled host. Sequence: validated leakage-clean
Ce-from-EEG predictor (a small paper in itself) → write the gate marker → Ce-axis
generative counterfactual. Distinct from, and complementary to, the a-line Phase 2.

## References
- Obermeyer Z, et al. *Nature* (2026) — predictive+generative counterfactual method.
- UCE / NESI / MORGOTH — the supervised depth-index lineage this reframes generatively.
- PHASE2_GENERATIVE_COUNTERFACTUAL.md (parent method + shared gate).
