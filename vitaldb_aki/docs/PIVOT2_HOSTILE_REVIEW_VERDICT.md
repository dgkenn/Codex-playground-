# Pivot 2 — consolidated hostile-review verdict (A-line vascular-tone / SVR signal)

This resolves the standing `/goal have this survive hostile review` for Pivot 2: the
claim that the arterial-line waveform carries a vascular-tone / SVR signal. Every
adversarial test that was run is collected here with its scoped conclusion.

## The claim, scoped to what survived
**An arterial-line-derived estimator that RANKS vascular tone / SVR (a trend monitor /
vasoplegia detector), circularity-clean and dynamically robust — NOT a calibrated
replacement for an SVR monitor, and NOT a novel "pure tone-shape" mechanism beyond
pressure + flow.**

## Tests and verdicts

### 1. Circularity (the central attack) — SURVIVES
EV1000/Vigileo SVR is pulse-contour (FloTrac), computed FROM the arterial waveform, so
an EV1000 correlation could be tautological. Re-tested against SVR built from an
INDEPENDENT cardiac-output source (Vigilance thermodilution / CardioQ oesophageal
Doppler), **N=89 (64 Vigilance, 25 CardioQ)**:
- Waveform tone index vs independent-CO SVR: **Spearman −0.416** (95% CI
  [−0.587, −0.224], permutation p=0.001), in the hypothesised NEGATIVE direction.
- τ (=R·C) partial-Spearman vs independent SVR **given MAP = +0.314** (positive, as the
  windkessel mechanism predicts; on par with EV1000 +0.16).
- Pure-shape (τ, AIx) adds incremental R² **0.045** over all pressure scalars against a
  CO not derived from the arterial waveform.
- **Full-model r: independent 0.52 vs EV1000 0.46** — the EV1000 signal was NOT merely
  circular; the waveform→vascular-resistance measurement is real.

### 2. Pure tone-SHAPE beyond pressure AND flow — does NOT survive (scoping)
τ partial given **MAP+HR ≈ 0.045 (~0)**: the beyond-pressure signal runs largely through
the HR/flow pathway. This replicates the EV1000 airtight test. → the claim is an
**A-line SVR estimator**, not a novel pure-tone-shape mechanism.

### 3. Agreement (measurement-paper standard) — FAILS Critchley → ranking only
Bland-Altman of waveform-estimated vs measured SVR: percentage error **56% (EV1000)** and
**79% (independent CO)**, both far above the Critchley ≤30% bar. → the waveform RANKS
tone well but is **not a calibrated point-estimate** of SVR. Acceptable for a
trend/low-tone detector; not for "replaces the SVR number."

### 4. Dynamic within-case tracking + pressor confound — SURVIVES
Within-case tone↔SVR tracking (docs/DYNAMIC_TONE_TRACKING.md) re-tested for the
vasopressor-administration confound, lead/lag and window length (dynamic_tone_confounds):
- Pressor pumps are **essentially absent** in this EV1000-SVR cohort (onPressor ≈ 0% for
  nearly all cases); where present (one case 21%), **dia|pressor ≈ −0.02** and the
  diastolic carrier **holds adjusting for pressor: dia|MAP,HR,P = +0.57**. → tracking is
  NOT a pressor artifact.
- **Window-length robust:** diastolic carrier dia|MAP,HR = **+0.54 (60s), +0.57 (180s)**;
  tone|MAP,HR = −0.25…−0.29 across windows.
- Diastolic/MAP form factor is the stable carrier of the signal.

### 5. Case-mix / external validity — CAVEAT (not a kill)
The independent-CO cohort is **~72% liver transplantation** (a high-vasoplegia
population). Single-centre (SNUH/VitalDB). External arterial-waveform + independent-CO
replication is stated future work, not done here.

## Bottom line
Pivot 2 **survives hostile review as a scoped claim**: a circularity-clean,
dynamically-robust, window-robust A-line **SVR/vascular-tone ESTIMATOR (ranking / trend /
vasoplegia-detection)**. It is explicitly **not** a calibrated SVR replacement (agreement
fails Critchley) and **not** a novel pure-tone-shape mechanism (signal runs through
pressure+flow). The honest, defensible framing is a cheap continuous vasoplegia/tone
*index* from the routine arterial line — to be externally replicated.

## Link to the pressor-requirement line
This dovetails with the control-theory finding (docs/PRESSOR_REQUIREMENT.md): the A-line
tone estimator is the *static morphology* view of vascular tone, while the vasopressor
dose-REQUIREMENT is the *intervention-anchored* view. The combined ECG×A-line biosignal
(docs/COMBINED_BIOSIGNAL.md) is the build that tests whether morphology predicts the
requirement — i.e., whether the tone estimator and the requirement phenotype are the same
underlying vasoplegia signal seen two ways.
