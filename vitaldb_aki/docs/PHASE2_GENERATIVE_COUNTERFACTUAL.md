# Phase 2 — Generative-Counterfactual Interpretability (Arterial-Waveform Arm)

**Status: SPECIFIED + GATED. NOT YET RUNNABLE.** This phase is documented and its
binding prerequisite is enforced; it must NOT execute until the gate below passes.

**Attaches to:** A-line Benchmark Protocol v2 (Phase 2 / §17).
**Purpose:** Adapt the Obermeyer et al. ECG–SCD interpretability method (predictive
model + generative model → synthesize high-risk vs low-risk waveforms → reveal a
human-visible morphological biomarker, their "slurred downstroke") to the arterial
pressure waveform, to *explain* an already-validated, leakage-clean organ-injury
increment.

---

## BINDING PREREQUISITE (the gate)

Generative-counterfactual interpretability reveals **what the predictive model
relies on**. Applied to a model that leaks (e.g., re-reads mean arterial pressure
or a hypotension scalar), it will synthesize a plausible waveform that *encodes the
confound* and launder it into a false "morphological discovery." **You may only
interpret a model already shown not to be reading a confound.**

Phase 2 may run only after the §9 arterial-line increment has, on the LOCKED test
partition:
1. **Passed the HPI guard** — incremental value over the hypotension-burden scalars
   (MAP mean/min, AUC<thresholds, pulse pressure), not a restatement of pressure.
2. **Passed the full leakage/confound battery (§12)** — no postop leakage, negative
   controls ~0.5, surgical-magnitude confound addressed.

Gate contract (enforced in code, see `phase2_interp/prereq_guard.py`): Phase 2
refuses to start unless `cache/aline_hpi_guard_passed.json` exists with
`{"hpi_incremental": true, "leakage_battery": "pass", "locked_test": true}`.
Today this file does NOT exist → Phase 2 is correctly blocked.

---

## Method (adapted from the ECG–SCD figure)

A loop between two models:
- **Predictive model** — scores organ-injury risk from the arterial waveform (v2,
  post-HPI-guard).
- **Generative model** — draws realistic synthetic arterial beats (VAE / diffusion
  / normalizing flow), pretrained self-supervised on ALL VitalDB arterial waveforms
  (no outcome label). Design efficiency: build the §9 self-supervised representation
  AS this generator so one model serves prediction + generation.

Optimize the generator's **latent** to increase the predictor's risk (→ synthetic
high-risk beat) and, separately, to decrease it (→ low-risk beat), holding realism
via the generative prior. The **morphological difference** is the candidate visible
biomarker — the arterial analog of the slurred downstroke.

## Procedure
1. Train the generative arterial-waveform model (self-supervised, all cases).
2. Take the validated leakage-clean predictor (v2, post-gate).
3. **Latent-space** optimization to max/min predicted risk, regularized to the
   realistic-waveform manifold (magnitude penalties, optional class-conditional).
   NEVER optimize in raw signal space (adversarial perturbations).
4. Synthesize matched high/low exemplars; visualize the difference + the morphology
   trajectory as risk increases.
5. **Operationalize** the visualized difference as a measurable quantity (upstroke
   dP/dt, notch timing, decay-rate, beat width) — a concrete feature, not a picture.

## The Residual-Beyond-Scalars Test (key safeguard)
The discovered difference must be **morphological**, not a restatement of pressure:
- Test whether the synthetic high-vs-low difference is explained by the hypotension
  scalars. If it reduces to "lower MAP," it is hypotension rediscovered.
- Report only the **residual morphology after conditioning on the hypotension
  scalars** (a shape change at MATCHED pressure).
- Quantify how much of the counterfactual risk shift is scalar pressure vs residual
  morphology.

## Realism + adversarial safeguards
- **Manifold constraint** (latent optimization w/ generative prior); plausibility
  check of synthetic pulses.
- **Adversarial check** — risk shift survives small perturbations (not an
  imperceptible exploit).
- **Stability** — consistent across seeds, latent inits, predictor CV folds.

## Confirmation (discovery → hypothesis → test)
1. Compute the operationalized feature on REAL beats; test incremental value over
   clinical + PK + hypotension-burden on the LOCKED test partition.
2. **External limitation:** INSPIRE has no waveforms → no external waveform
   validation; state plainly. Confirmation is internal (locked test) + an
   independent waveform cohort as future work.
3. Report only a feature that is realistic, scalar-residual, stable, and
   incrementally valid — and even then as hypothesis-generating, not mechanism.

## What this phase CANNOT establish
Causality; that synthetic exemplars map to real subtypes; generalization beyond
VitalDB. It explains/visualizes an association; it does not validate a mechanism.

---

## Staging + feasibility assessment (this repo / host)

Per §7 of the proposal (scope honesty), and reinforced by the current state:

- **Paper 1 = the v2 benchmark** — establish that the arterial-waveform increment
  exists AND is leakage-clean (passes the HPI guard + leakage battery). This is the
  finishable legitimacy paper and the de-risking prerequisite for Phase 2. **It is
  NOT done:** the A-line feasibility (a ~600-case, ~20-event GO/NO-GO screen) is
  still running; the full ART extraction, the HPI guard, and the locked-test
  increment do not yet exist.
- **Paper 2 = this module** — runs only on the validated, gate-passing model.

**Infrastructure reality (must be stated):** training a generative arterial-waveform
model (VAE/diffusion/flow) requires (a) the FULL VitalDB arterial-waveform corpus
(~180 GB; the streaming extraction is bandwidth-bound on this host) and (b) GPU
training. This host is CPU-only, behind a flaky proxy, with a ~38 GB working disk
and ~15–30 min process-kill cycles. **Phase 2 generative training is not executable
here**; it requires a GPU environment with the waveform corpus staged. The
specification + gate are committed now so the work is ready to run in an
appropriate environment, in the correct order.

**Sequence:** A-line feasibility (running) → if GO, full ART extraction + HPI guard +
leakage battery + locked-test increment (Paper 1) → write
`cache/aline_hpi_guard_passed.json` → Phase 2 generative-counterfactual (Paper 2),
on GPU, with the corpus staged.

## References
- Obermeyer Z, et al. An ECG biomarker for sudden cardiac death discovered with deep
  learning. *Nature* (2026).
- Generative model ref (VAE / diffusion / normalizing flow for physiological
  waveforms) — fill at implementation.
- v2 protocol §9 (a-line arm), §12 (leakage battery), §13 (incremental-value).
