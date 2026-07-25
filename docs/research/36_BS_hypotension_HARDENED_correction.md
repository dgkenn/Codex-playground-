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
