# A-line Fluid-vs-Pressor Decision Model (deep learning) — SPECIFIED + GATED

**Status: SPECIFIED + GATED behind Phase-0 feasibility. NOT YET RUNNABLE** (needs a
GPU + the arterial-waveform corpus, and the feasibility GO marker, neither of which
exists today).

**One-line thesis:** From the arterial pressure waveform of a hypotensive patient,
predict whether a **fluid bolus** or a **vasopressor** will better restore perfusion —
a point-of-care, per-patient personalization of the fluid-vs-pressor decision that is
the clinical embodiment of this project's central finding ("it's not the pressure
target, it's how perfusion is restored").

---

## Why this is tractable (building blocks already exist)

- **`features/aline_morphology.py`** — computes **PPV** (pulse-pressure variation, the
  validated dynamic preload / fluid-responsiveness index; >13% = preload-responsive,
  Michard cutpoint) and other waveform morphology from the arterial line. The
  "will fluid help?" axis.
- **`features/vasoactive_pd.py`** — **`vaso_responsiveness`** = OLS slope of MAP vs total
  pressor-infusion rate (a blunted slope = vasoplegia, "pressor isn't restoring
  perfusion"), plus agent count / pressor duration. The "is this a pressor problem?" axis.
- **`features/fluid_responsiveness.py`** — SVV/CO/SVR from the EV1000/Vigileo/CardioQ
  subset (stroke-volume gold standard where available).
- **`analysis/actionable_targets.py`** — the actual management (fluid- vs
  pressor-predominant), download-free.

The deep-learning model is the step BEYOND these hand-built scalars: learn a finer,
per-beat waveform representation that predicts the *differential* response (uplift) to
fluid vs pressor — beyond PPV alone.

---

## BINDING PREREQUISITE (the gate)

A policy / uplift model that *recommends* a treatment **amplifies whatever the
feasibility signal encodes, including confounds** — most dangerously, the model could
learn to read the management it is meant to recommend (the clinician's choice leaks via
artifacts of pumps/fluids on the trace), laundering "what was done" into "what to do."

Phase 1 (this DL model) may run only after Phase 0
(`analysis/aline_fluid_vs_pressor.py`) has, on the LOCKED test partition:
1. **Shown a concordance signal** — an A-line phenotype (preload-responsive vs
   vasoplegic) whose *indicated* treatment tracks better organ-injury outcomes than the
   discordant choice (IPTW-adjusted, E-value-supported).
2. **Waveform-only, no management leak** — the phenotype is computed from the arterial
   waveform BEFORE/independent of the treatment, and does not encode the pump/fluid
   management it is meant to recommend.
3. **Passed the leakage/confound battery** — negative control null, no postop leakage.

Gate contract (enforced in `analysis/phase2_prereq_guard.py`, gate
`aline_fluid_pressor`): refuses to start unless
`cache/aline_fluid_pressor_feasibility_passed.json` exists with
`{"feasibility_go": true, "waveform_only_no_management_leak": true,
"leakage_battery": "pass", "locked_test": true}`. Today this file does NOT exist →
the DL model is correctly blocked.

---

## Method (the DL / policy version)

- **Signal:** intraop arterial waveform (`SNUADC/ART`, 500 Hz) windows preceding a
  hemodynamic intervention (a fluid bolus or a vasopressor step-up), labeled by the
  **response** (ΔMAP, and ΔSV/ΔCO where EV1000 is present) over the following minutes.
- **Representation:** self-supervised arterial-waveform encoder (reuse the Phase-2
  generative arterial model as the representation — design efficiency).
- **Target — the differential (uplift):** per patient, predict response-to-fluid and
  response-to-pressor; the *recommendation* is the larger predicted restoration. Because
  each episode received only one treatment, this is causal-inference-under-one-arm:
  use an uplift / T-learner / doubly-robust policy estimator with IPTW for treatment
  choice, NOT a naive two-head regression.
- **Evaluation:** policy value via inverse-propensity / doubly-robust off-policy
  estimation on the LOCKED test (would following the model's recommendation have
  improved outcomes?), against the standard-of-care policy. Calibration of predicted
  vs observed response within the treated arm.

## Safeguards
- Waveform-only inputs; explicit probe that the representation does NOT predict which
  treatment was given from pre-treatment data (no management leak).
- Confounding-by-indication is the central threat: clinicians may already use PPV /
  pressor-response, so the standard-of-care policy is itself informed → a *null* uplift
  is an honest, expected possibility, and is reported as such (the decision is already
  near-optimal), NOT spun.
- Negative-control response (an outcome the choice should not affect); stability across
  seeds / CV folds; manifold/realism if synthesis is used.

## What it cannot establish
Causality of the recommended policy (off-policy estimates rest on no-unmeasured-
confounding within the IPTW model); that VitalDB management patterns generalize. It is
decision-support hypothesis generation toward a prospective trial, not proof.

## Staging + feasibility (this host)
- **Phase 0 = `analysis/aline_fluid_vs_pressor.py`** (runnable now, CPU-only): the
  concordance feasibility on existing PPV / vaso_responsiveness / management / outcome
  features. Produces the GO/NO-GO and, if GO + leakage-clean on locked test, writes the
  gate marker. **This is the legitimacy precursor.**
- **Phase 1 = this DL model** — needs a GPU + the 500 Hz arterial-waveform corpus
  staged (bandwidth-bound here). Not executable on this CPU-only, ~38 GB, kill-cycled
  host. Spec + gate committed now so it is ready to run in the right environment, in
  the right order.
- **External validation:** INSPIRE has numeric MAP + pressors/fluids but NO continuous
  arterial waveform → the *scalar* concordance phenotype is externally testable on
  INSPIRE; the *waveform* DL model is not (note plainly; an independent waveform cohort
  is future work).

## References
- Michard F. Pulse pressure variation and fluid responsiveness. (PPV physiology.)
- Obermeyer Z, et al. *Nature* (2026) — predictive+generative waveform method (the
  representation lineage).
- PHASE2_GENERATIVE_COUNTERFACTUAL.md (arterial representation); docs/ACTIONABLE_RESULTS.md
  (management exposures); analysis/aline_fluid_vs_pressor.py (Phase-0 feasibility).
