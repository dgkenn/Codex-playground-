# Phase 2c — Confound-Controlled Generative-Counterfactual EEG Biomarker Discovery (HEEDB, Topographic)

**Status: SPECIFIED + GATED. NOT YET RUNNABLE.** The spatial, full-montage HEEDB
sibling of the Phase 2 generative-counterfactual line
(PHASE2_GENERATIVE_COUNTERFACTUAL.md, arterial; PHASE2B_CE_AXIS_DRUG_RESPONSE.md,
Ce-axis). Same Obermeyer ECG–SCD method, lifted to 19-channel clinical EEG where a
counterfactual difference can be **topographic** — regional/connectivity structure
at matched global power, which a single-region sensor physically cannot produce.

**PI:** Dean Kennedy, MD · Pre-register on OSF before any outcome-coupled synthesis.

---

## Two binding principles (non-negotiable)

1. **Validated predictor first.** This is an EXPLANATION tool for an *already-validated,
   leakage-clean* outcome predictor — never a discovery oracle pointed at raw data. It
   amplifies whatever the predictor learned, **including confounds**. On HEEDB, where
   outcomes are leakage-saturated (report text, ICD codes, meds, indication all
   correlate with the outcome), this is the central failure mode the whole design
   exists to prevent.
2. **Interpretive flexibility, not narrative freedom.** The readout form is open
   (topographic, connectivity, microstate, aperiodic), but every interpretation must
   clear the falsifiable bar (§ Safeguard Battery). Free narration of a flexible output
   on a leakage-saturated dataset is HARKing with a generative model attached — the
   confirmation bar RISES, it does not relax.

---

## Objective — feasibility-as-result

Discover EEG structure carrying an EHR outcome **beyond the known markers**, by
synthesizing high- vs low-outcome EEG **at matched known markers**:

- **Constrained shift collapses → clean negative.** Holding the known markers fixed, if
  the achievable outcome shift drops to ~0, the outcome's EEG signal **reduces to the
  known markers** (publishable: "this outcome's EEG signature is explained by
  slowing / MORGOTH findings").
- **Constrained shift survives → candidate biomarker.** A substantial residual outcome
  shift at matched markers is, by construction, **orthogonal to the known markers** — the
  candidate novel (topographic/connectivity) biomarker.

Both outcomes are real results. Distinct from NESI/MORGOTH (discriminative black-box
indices, not interpretable orthogonal-to-power morphologies).

---

## BINDING PREREQUISITE (the gate)

Phase 2c may run only after a HEEDB-EEG outcome predictor has, on the LOCKED test
partition (ideally a held-out hospital):
1. **Passed the full leakage battery** — the EEG report text, ICD codes, medications,
   and indication are NOT inputs; the EEG temporally PRECEDES the outcome; site/device
   probed; performance honest.
2. **Non-circular outcome** — a hard EHR outcome with a mechanistic prior that MORGOTH
   does NOT directly detect (mortality or a neurological outcome are candidates), so the
   discovery cannot be a restatement of a MORGOTH finding.

Gate contract (enforced in `analysis/phase2_prereq_guard.py`, gate `heedb_eeg`): refuses
to start unless `cache/heedb_eeg_predictor_validated.json` exists with
`{"leakage_battery": "pass", "eeg_only_no_ehr": true, "temporal_precedence": true,
"non_circular_outcome": true, "locked_test": true}`. Today this file does NOT exist →
Phase 2c is correctly blocked.

---

## Known-marker set (pre-specified, held fixed)

Delta + the other band powers; the MORGOTH task outputs (17 findings, IIIC, sleep
stages); the NESI severity axis. Plus nuisance variables held/probed: **site/device,
age, sex**. (Because MORGOTH's outputs are AMONG the held-fixed markers, using a
verified-generative MORGOTH-VQ as substrate is coherent — you are explicitly
controlling for what it encodes.)

## Generative model

Self-supervised multichannel 10-20 EEG generator trained on HEEDB (no outcome):
diffusion / VAE / normalizing flow, OR a **verified-generative** MORGOTH-VQ tokenizer.
Requirement: produces REALISTIC full-montage EEG segments so synthesis stays on the
data manifold. EEG generation is harder than 1D-pulse generation — realism validation
is mandatory (not assumed of MORGOTH-VQ).

## The confound-controlled counterfactual (core method)

Optimize the generator latent **z** to push the predictor up and (separately) down,
**subject to holding the known markers at a matched reference**:
- max / min `f(g(z))` (outcome risk), penalizing deviation `||m(g(z)) − m_ref||` for the
  known-marker vector `m` (band powers, MORGOTH outputs, NESI), and
  constraining/penalizing site- and demographic-encoding.
- Optimize **in latent space** (never raw signal — adversarial risk), regularized to
  realism.
- Generate matched-marker high- vs low-outcome exemplars; their difference is ~orthogonal
  to `m` by construction.
- **Feasibility quantity (the result):** achievable outcome shift UNCONSTRAINED vs
  CONSTRAINED-at-matched-markers. Ratio → collapse (reduces to markers) or survives
  (residual biomarker).

## Readout (interpretation free; form open)

Characterize the matched-marker residual difference however is most illuminating —
**topographic** difference maps (where the residual lives spatially), connectivity/phase
structure, microstate dynamics, aperiodic components, temporal microstructure. The
"visible" EEG output is a difference *map*, not a single landmark. Any chosen
interpretation proceeds to the bar below.

## Safeguard battery (the falsifiability bar — every interpretation)

1. **Validated-predictor-first** (gate) — non-negotiable.
2. **Manifold/realism** — synthetic exemplars physiologically plausible (quantitative +
   expert); reject adversarial/off-manifold solutions.
3. **Residual-beyond-known-markers** — enforced by construction; additionally verify the
   residual is not explained by any held-fixed marker.
4. **Unmodeled-confound probe** — the residual must NOT predict site, device, age, sex,
   or the EEG indication. (HEEDB leakage is severe — this is where a laundered confound
   hides.)
5. **Stability** — consistent across seeds, latent inits, predictor CV folds. Unstable →
   artifact.
6. **Permutation noise floor** — run the entire procedure with a SHUFFLED-label
   predictor; the real residual must exceed what pure noise manufactures.
7. **Anti-HARKing** — no post-hoc neuroscience narrative accepted unless the
   operationalized feature survives 2–6 AND confirmation below.

## Confirmation (discovery → hypothesis → test)

- **Operationalize** the residual topography/connectivity as a concrete measurable
  feature.
- **Internal:** incremental value over the known markers for the outcome, on a LOCKED
  HEEDB test partition (held out, opened once; ideally a held-out hospital).
- **External (a real strength here):** confirm on **TUH** — an independent health-system
  full-montage clinical-EEG corpus. Unlike VitalDB/INSPIRE (no external waveforms), real
  external *EEG* validation genuinely exists. A feature that replicates on TUH at matched
  known-markers is a serious candidate.

## What this cannot establish

Causality; that synthetic exemplars map to real patient subtypes; mechanism. It makes
orthogonal association **visible and falsifiable**; it does not validate a mechanism.

## Scope + staging (honesty)

A large, multi-component methods project: a generative EEG model + a separately-validated
leakage-clean predictor (itself a project) + constrained synthesis + dual confirmation.
**Not** a near-term legitimacy paper. Recommended order: finish the simpler work first
(the VitalDB organ-injury benchmark; a clean HEEDB predictor), THEN attempt this once a
validated leakage-clean EEG predictor exists to interpret. Doing it earlier means
interpreting a model not yet proven clean — the exact failure the design prevents.

**Infrastructure:** needs GPU training + the HEEDB EEG corpus staged (and TUH for external
confirmation). Not executable on this CPU-only, ~38 GB, kill-cycled host. Spec + gate are
committed now so the work is ready to run in the right environment, in the right order.

**Non-commercial firewall:** all BDSP/MORGOTH-derived artifacts are
research-and-publication-only; firewall hard from any patent/commercial work; clean-room
re-derivation required to ever commercialize.

## References

- Obermeyer Z, et al. *Nature* (2026) — predictive+generative counterfactual method.
- Sun C, et al. HEEDB, *Epilepsia* (2025); MORGOTH, *Lancet Digital Health* (in press
  2026); NESI (2026) — known-marker set + substrate.
- TUH EEG Corpus — external confirmation set.
- PHASE2_GENERATIVE_COUNTERFACTUAL.md (arterial parent); PHASE2B_CE_AXIS_DRUG_RESPONSE.md
  (Ce-axis sibling); shared gate `analysis/phase2_prereq_guard.py`.
- (Generative EEG model reference — diffusion / VAE / flow — fill at implementation.)
