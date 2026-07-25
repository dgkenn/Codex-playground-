# Hardened re-analysis of the burst-suppression → hypotension claim — what survives and what does not

**Status: this document supersedes the headline numbers in `34_BS_hypotension_manuscript.md`.**
Nothing here is a new dataset. It is the same VitalDB data re-analysed under specifications that remove artefacts
the original models did not control. Two of the three headline claims do not survive. They are retracted below.

The trigger was a negative control. Frontal EMG — recorded by the same BIS sensor, but not a measure of cortical
suppression — reproduced the *sign pattern* of the two-phenotype result under the original model specification
(OR 1.05 above baseline, 0.91 below). A negative control that "works" means the model, not the physiology, is
producing part of the signal. Everything below follows from chasing that down.

---

## 1. What was wrong with the original specification

`analysis/vitaldb_two_phenotype.py` — and every model built on it, including the sevoflurane replication —
has three defects, in increasing order of severity:

1. **No case-level clustering.** Confidence intervals were model-based on ~600,000 bins drawn from ~1,700
   patients. Bins within a case are strongly autocorrelated; the effective sample size is the *cases*. Every
   interval in the original draft is far too narrow.
2. **Mean arterial pressure entered linearly.** The phenotype strata are *defined* by current MAP relative to the
   patient's own baseline, and the outcome is MAP at *t+k*. Conditioning on a value being high makes the next
   value tend to fall (regression to the mean). A linear covariate does not remove this; exact stratification does.
3. **No anaesthetic-dose matching within patient.** Deep anaesthesia causes both suppression and vasodilation.
   Adjusting for effect-site concentration as a linear covariate across patients does not support a claim of
   dose-independence.

## 2. The hardened specifications

| | pressure control | dose control | patient control | inference |
|---|---|---|---|---|
| **A** original | linear covariate | linear covariate | none | model-based SE |
| **B** exact-stratified | exact 2 mmHg strata (Mantel–Haenszel) | none | none | case cluster bootstrap |
| **C** self-controlled | exact 4 mmHg strata | exact 0.5-unit strata | **case fixed** | case cluster bootstrap |
| **D** within-case Δ | linear, within case | linear, within case | **case fixed** | case cluster bootstrap |

C is the strictest: every comparison is a patient against *themselves*, at the same arterial pressure, at the same
drug concentration. All time-invariant patient characteristics — age, comorbidity, frailty, surgery, baseline
vascular tone, anything unmeasured — are differenced out by construction rather than modelled.
D trades that exact matching for a continuous outcome (signed ΔMAP in mmHg) and is much better powered.

Code: `vitaldb_rtm_hardening.py`, `vitaldb_scale_and_interaction.py`, `vitaldb_self_controlled.py`,
`vitaldb_within_case_delta.py`, `vitaldb_detector_independence.py`, `vitaldb_sevo_rtm.py`.

---

## 3. RETRACTED — the two-phenotype dissociation

The claim was: burst suppression predicts subsequent hypotension in patients whose MAP is at/above their own
baseline (a "sensitivity phenotype") but not in those already below it (a "hypoperfusion phenotype"). It rested
entirely on *one stratum being significant and the other not*. That is the difference-of-significance fallacy: the
below-baseline stratum has **14× fewer bins** (44,006 vs 611,656), so it is underpowered by construction.

Tested properly, as a formal interaction — the ratio of the two Mantel–Haenszel odds ratios, with both recomputed
inside each case-level bootstrap replicate so they are correctly correlated:

| stratum | MH OR (exact 2 mmHg strata) | bins |
|---|---|---|
| MAP ≥ own baseline | 1.18 [1.10, 1.26] | 611,656 |
| MAP < own baseline | 1.10 [0.90, 1.29] | 44,006 |
| **ratio of odds ratios (the interaction)** | **1.08 [0.89, 1.32]** | — |

**The interval includes 1. The dissociation is not established.** The two strata are statistically
indistinguishable. The apparent contrast was a power artefact.

This also disposes of the sevoflurane "external validation": it replicated the *significant / not-significant*
pattern, which is what an underpowered second stratum will do in any dataset. It did not replicate an interaction,
because there is no established interaction to replicate. **Do not present the two-phenotype finding, and do not
spend effort externally validating it on further datasets.**

## 4. Effect size — most of the apparent shrinkage was a scale change, not an artefact

Care is needed comparing the specifications, because the exposure scale changed at the same time as the model. The
original reports an OR "per full suppression" (a 0 → 1 change in the bin's suppressed fraction); the stratified
analyses report "any suppression vs none". Suppression is present in 41.7 % of bins, and among those the mean
suppressed fraction is only **0.140** — so the two contrasts are not comparable. Run on identical rows:

| specification (lag +120 s, MAP ≥ baseline) | OR |
|---|---|
| A continuous exposure, MAP linear | 2.06 [1.64, 2.62] per full suppression |
| A rescaled to the any-vs-none contrast | ≈1.11 |
| B binary exposure, MAP linear | 1.20 [1.10, 1.30] |
| C binary exposure, exact 2 mmHg MAP strata | 1.18 [1.10, 1.25] |

B versus C is the honest test of regression to the mean, and it is **1.20 → 1.18**: the artefact is real but small.
The functional form was not the main problem — **the reporting scale was.** An OR of 2.06 "per full suppression"
describes a contrast (a completely suppressed 30-second bin versus a completely unsuppressed one) that is far more
extreme than anything the phrase conveys to a reader. That is the number in the current draft abstract, and it must
be re-expressed on an interpretable scale.

## 5. What survives: a small, self-controlled, dose-matched association in propofol

Specification C, propofol, 1,859 cases — each patient compared against themselves at the same pressure and dose:

| lag | MH OR | 95 % CI (case bootstrap) |
|---|---|---|
| +60 s | 1.08 | [1.03, 1.12] * |
| +120 s | 1.08 | [1.03, 1.12] * |
| −60 s | 1.03 | [0.98, 1.07] ns |
| −120 s | 1.01 | [0.97, 1.05] ns |
| **temporal asymmetry, +120 s vs −120 s** | **1.07** | **[1.02, 1.12] — precedence supported** |
| temporal asymmetry, +60 s vs −60 s | 1.05 | [0.99, 1.10] — not significant |

This is the strongest defensible version of the finding: **within the same patient, at the same arterial pressure
and the same propofol concentration, bins containing burst suppression are followed by hypotension slightly more
often than bins that are not — and the forward association exceeds the backward one.** The asymmetry is what
distinguishes a cascade from a shared contemporaneous state, and it clears zero at 120 s.

Supporting it:
* **Instrument independence.** Swapping our raw-EEG detector for the BIS monitor's own suppression ratio — different
  electrodes, different signal chain, different proprietary algorithm — reproduces the pooled association
  (OR 1.15–1.16 under exact MAP stratification).
* **The negative control now behaves.** Under exact stratification, frontal EMG is null at every lag
  (0.95–1.00). The 1.05 that triggered this whole re-analysis was the regression-to-the-mean artefact, and exact
  stratification removes it. This is the cleanest evidence that specification C is measuring physiology.

**But the effect is small.** OR 1.08 on a binary exposure, against a background hypotension rate of roughly 8 %,
is on the order of half a percentage point of absolute risk. It is not an early-warning signal of clinical utility
on its own, and it must not be described as one.

## 6. Two findings that point the other way — both must be reported

**(a) The monitor-based exposure shows no precedence.** Under exact MAP stratification the BIS suppression ratio
gives backward associations (−60 s OR 1.18, −120 s 1.20) at least as large as forward (1.15, 1.16). There is a
mechanical explanation — the BIS suppression ratio is computed over a *trailing* ~63-second window, so the value at
time *t* reflects EEG from before *t*, which shifts its apparent timing backwards by roughly two bins. That
explanation is physically correct and is why the instantaneous raw-EEG detector is the right instrument for a
precedence claim. It is nonetheless an explanation offered after seeing the result, and it should be presented as
such rather than as a defence.

**(b) Sevoflurane does not replicate under the hardened specification.** The volatile cohort replicated under the
original model (MH pooled OR 1.31 [1.01, 1.68] at +120 s) but is null once matched within patient on pressure and
dose:

| sevoflurane, specification C | OR |
|---|---|
| +60 s | 1.02 [0.89, 1.17] ns |
| +120 s | 0.99 [0.88, 1.12] ns |
| asymmetry +120 vs −120 s | 0.93 [0.80, 1.09] — symmetric |

The continuous within-case version (specification D) agrees and shows why: a fully suppressed bin sits in a trough
of about **−3.8 mmHg looking forward and −3.3 mmHg looking backward** (difference −0.47 mmHg [−3.17, +2.36]).
Burst suppression and low pressure travel together in time in sevoflurane, with **no directional ordering at all**.

This is an underpowered null — 274 cases with usable within-case variation, and the CI cannot exclude an OR of
1.12 — so it does not refute the propofol result. But it does mean the finding is currently **propofol-only and
unreplicated**, and the sevoflurane analysis can no longer be cited as external validation. It is the opposite.

---

## 7. Where this leaves the project

**Retract:** the two-phenotype dissociation; the sevoflurane replication; the abstract's "OR 4.96" and "OR 1.68"
figures (no case clustering, linear pressure control, and a scale that overstates the contrast).

**Keep, with the effect size stated honestly:** a small within-patient, dose-matched, pressure-matched temporal
association in propofol, with a clean negative control and an independent instrument reproducing the pooled
association. That is a real and carefully-established observation. It is a sound methods-and-measurement
contribution. It is not, on this evidence, a clinically actionable early-warning signal.

**Unresolved and now the highest-value question:** why propofol and not sevoflurane? That is a genuine
pharmacological hypothesis with a direction — propofol's sympatholysis and venodilation give a plausible route from
a deep-suppression state to a delayed pressure fall that a volatile agent's more immediate SVR reduction would not
produce. It is testable, and it is the kind of mechanism question worth putting to a senior advisor. But it needs
a properly powered volatile cohort before it is more than a hypothesis.

**Untouched by this re-analysis:** the burst-suppression → AKI arm is a *case-level* analysis (per-case burden →
per-case outcome) and is not subject to the bin-level regression-to-the-mean problem. Its own stated limits — a
proportion-mediated interval of [29 %, 184 %] whose upper bound is out of range, and the absence of a formal
marginal structural model — still stand and are unaddressed.

## 8. Lesson

The negative control is what caught this. A control that was expected to be null came back at 1.05, and following
that 5 % discrepancy overturned two of three headline claims. **Every future bin-level analysis in this project
ships with (i) a negative-control exposure, (ii) exact stratification on any variable used to define the strata,
(iii) case-level cluster bootstrap intervals, and (iv) a backward-lag control — before any result is written up.**

---

# PART II — gap-closing results (all under the hardened estimator)

Everything below uses the corrected specification throughout: within-case fixed effects, adjustment for MAP(t),
anaesthetic dose, dose *kinetics* (dCe) and a pre-trend measured over `[t-2k, t-k]`, on bins holding both a forward
and a backward neighbour, with case-level cluster bootstrap intervals. The reported statistic is always
**forward minus backward** — a shared contemporaneous state is symmetric in time, a cascade is not.

## II.1 SPECIFICITY — is it suppression, or just anaesthetic depth? (the make-or-break test)

Brown and Purdon's central claim about the anaesthetic EEG is that it is not a one-dimensional depth axis: propofol
produces specific oscillatory signatures (frontal alpha, slow-delta) and burst suppression is a distinct dynamical
state rather than "more slowing". If slow-wave power carried the same lead as suppression, this whole finding would
be about depth, the EEG would add nothing beyond the dose, and the specific claim would collapse.

694,762 bins, 1,771 cases. Continuous markers dichotomised at each patient's OWN median (absolute spectral power
varies by an order of magnitude across patients, so a cohort-wide cut would encode who the patient is and the case
fixed effects would then absorb the exposure itself).

| marker | alone | mutually adjusted | all four |
|---|---|---|---|
| **burst suppression** | **−0.734** [−0.914, −0.577] * | **−0.721** [−0.874, −0.571] * | **−0.729** [−0.863, −0.564] * |
| slow-delta power | −0.224 [−0.335, −0.114] * | −0.222 [−0.346, −0.114] * | −0.242 [−0.347, −0.123] * |
| frontal alpha | +0.119 [+0.007, +0.238] * | +0.065 [−0.042, +0.191] ns | +0.046 [−0.078, +0.163] ns |
| frontal EMG | +0.499 [+0.279, +0.715] * | — | +0.521 [+0.300, +0.768] * |

**The test passes.** Suppression's lead is *completely unattenuated* by adjusting for simultaneous slow and alpha
power (−0.734 → −0.721 → −0.729). Depth-related spectral power and suppression are strongly correlated, so this was
expected to be a demanding test and the coefficient was expected to shrink. It does not move at all.

Three further readings, all pointing the same way:
* **Slow-delta carries its own, smaller, independent lead** (−0.22, unattenuated by suppression). Two separate EEG
  channels of information, not one depth axis with two noisy measurements of it.
* **Alpha loses significance once adjusted.** Its marginal +0.119 was collinearity with the other two.
* **The signs are physiologically coherent.** Frontal alpha marks intact thalamocortical dynamics under propofol and
  frontal EMG marks arousal; both precede a pressure *rise*. Only suppression precedes a fall. A monotone depth
  axis cannot produce that pattern.

Code: `analysis/vitaldb_eeg_specificity.py`.

## II.2 MECHANISM — vasodilation, confirmed with MEASURED cardiac output

The pulse-pressure decomposition suggested vasodilation but could not quantify it (PP is a poor stroke-volume
surrogate under vasopressor titration, and the SVR proxy carries MAP in its numerator). Re-run against EV1000
measured cardiac output, 704 cases, 322,739 bins:

| outcome | forward | forward − backward |
|---|---|---|
| MAP | −0.507 mmHg | −0.257 [−0.400, −0.124] * |
| **cardiac output (log)** | −0.006 % | **+0.268 %** [+0.140, +0.421] * |
| SVR (log) | −0.163 % | −0.340 % [−0.669, −0.029] * |

**Pressure falls, resistance falls, and cardiac output does not fall — it rises slightly.** That is what dropping
afterload does to an unloaded ventricle, and it excludes the competing mechanism outright: myocardial depression
*requires* CO to fall. The surrogate could only say "PP is flat"; measured CO says the ventricle is doing marginally
more work while pressure drops.

Limits: CO is the independently informative column (702 cases) — EV1000 computes its SVR *from* MAP, and that column
rests on only 214 cases with CVP. The subcohort is sicker by selection (clinicians place CO monitors on higher-risk
operations), which is the likely reason the MAP effect is smaller here (−0.26) than in the full cohort (−1.08).
Code: `analysis/vitaldb_measured_co.py`.

## II.3 The full-cohort haemodynamic decomposition (surrogate, for comparison)

1,780 cases. Same estimator, pulse pressure and heart rate as the stroke-volume and chronotropic channels:

| outcome | forward | forward − backward |
|---|---|---|
| MAP | −1.278 mmHg | −1.076 [−1.290, −0.879] * |
| pulse pressure | −0.028 mmHg | −0.062 [−0.142, +0.013] ns |
| heart rate | **+0.132 bpm** | −0.013 [−0.065, +0.043] ns |
| SVR proxy (log) | −0.756 % | −0.400 [−0.525, −0.277] * |

Same pattern, and the EMG negative control is **mirror-image on every column** (MAP +0.499, SVR proxy +0.213, both
significant). A pipeline returning opposite-signed, physiologically coherent answers for an arousal marker and a
suppression marker is doing more work than a null control could.
Code: `analysis/vitaldb_mechanism_decomposition.py`.

## II.4 Confound falsification (corrected pre-trend)

Propofol, ±60 s, any-vs-none contrast:

| model | forward − backward |
|---|---|
| M0 MAP(t) + dose(t) | −0.779 [−0.929, −0.634] |
| M1 + dCe over the same window | −0.829 [−0.974, −0.679] |
| M2 + pre-existing pressure trend | −0.779 [−0.931, −0.636] |
| M3 + both | −0.827 [−0.994, −0.666] |
| M4 stable-infusion bins only (50 %) | −0.306 [−0.484, −0.159] |

Neither the rate of change of effect-site concentration nor a pre-existing pressure trend attenuates the effect. It
halves in the stable-infusion subgroup but its interval still excludes zero, so roughly half the association is tied
to moments when the dose is moving and half is present at a perfectly fixed concentration.
Code: `analysis/vitaldb_pretrend_dosekinetics.py`.

## II.5 Still open

* **Autonomic intermediate.** 1,850 of 1,859 cases carry 500 Hz `SNUADC/ECG_II`, so HRV and spontaneous baroreflex
  sensitivity are measurable and the three-node chain (suppression → autonomic withdrawal → pressure fall) can be
  tested directly. Extraction in progress.
* **Anaesthetic-free replication.** `ICARE_train` (BDSP restricted AP): **607 post-cardiac-arrest patients, 7
  hospitals**, 19-channel EEG at 500 Hz *plus continuous 500 Hz ECG*, with CPC outcome and TTM recorded. Burst
  suppression is the classic post-anoxic pattern. Critically these patients receive **no anaesthetic**, so the
  dose-confound that every VitalDB analysis has to adjust away is absent by construction. Its `_OTHER` channel is
  **SpO2 only — no blood pressure**, so it tests EEG → autonomic, not the full chain. Confounders to handle:
  targeted temperature management (33 °C alters both EEG and HRV), sedation, and deranged post-arrest autonomics.
* **Sympatholysis gradient.** Prediction registered before running: the lead should be larger under high
  remifentanil, smaller under low, and abolished while a vasopressor infusion runs. Extraction in progress.
* **Sevoflurane at full power.** The null rests on 274 usable cases against ~2,100 available. Extraction in progress.
* **State-space BSP.** Implementation currently FAILS simulation recovery (correlations 0.002–0.226, process-noise
  estimates ~9.4e5 against a truth of 0.005–0.5); returned for repair. Not wired into any analysis.
* **Not closable with these data:** direct sympathetic outflow (microneurography) and brainstem circuit involvement.
