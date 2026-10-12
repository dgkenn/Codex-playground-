# Eleven interpretable numbers against a published 1,280-dimensional learned representation

*Technical note, 2026-08-01. Source: E158 and E159, `results/e159_cnn_vs_spectrum.json`. Written up
because it is finished, gate-clean, and directly usable by the anaesthesia/perioperative wedge — unlike
most of what this project has produced, which is negative or blocked.*

---

## The question, and why it had an incumbent for once

`INCUMBENT_REGISTRY.md` and error-catalogue rule 45 require every registration to name what it must beat.
For Challenge C that has meant **SEF95** (median within-recording ρ +0.1799 against MOAA/S, E79), **BIS**
(circular — computed from the same EEG) and **PE31**. None is a modern learned representation, and the
standard objection to a hand-built spectral panel had never been tested here at all: *a neural network
trained on the spectrogram would do better.*

PhysioNet `eeg-power-anesthesia` ships one. `Volunteer_CNN/btlncks.feather` is **46,948 windows ×
1,280 features** — MobileNet bottlenecks over 30 s spectrogram images, the representation the deposit's
own paper built its classifiers from, with the paper's stated reduction being **the first ten principal
components**. It comes with `is_conscious` on the same 2 s grid as our features.

**So for the first time a candidate family here could be scored against a published learned incumbent on
the same rows, the same subjects and the same label.**

---

## Design

| | |
|---|---|
| cohort | 10 healthy volunteers, stereotyped propofol infusion, behavioural LOC and ROC |
| target | `is_conscious`, the deposit's own label (23,639 / 23,309) |
| A | 10 principal components of the CNN bottlenecks — the paper's reduction |
| B | the 11 hand-built spectral features |
| evaluation | subject-grouped 5-fold cross-fitting; **subjects held out whole** |
| increments | `permutation_increment` — cross-fitted, cluster-permutation null — **in both directions** |

**PCA is fitted leave-one-subject-out.** A 1,280-dimensional representation reduced on all the data and
then scored on it will separate anything, including noise; no held-out subject contributes to its own
basis.

**Both directions are run** because "does the spectrum add to the CNN" and "does the CNN add to the
spectrum" are different questions, and reporting only the flattering one is how incumbents get chosen.

---

## The gate that mattered, and what it taught

E158's leakage control asked for the permuted-label out-of-fold AUC to lie in [0.45, 0.55] and got
**0.4400**, which reads as memorisation. It is not. Measured over 50 within-subject permutations:

| | mean | sd | range |
|---|---|---|---|
| CNN, 10 PCs | **0.4463** | 0.0158 | 0.4187 – 0.4796 |
| spectral, 11 features | **0.4486** | 0.0126 | 0.4231 – 0.4988 |

**Two unrelated feature families, the same centre, and 54 % of draws outside the nominal gate.** The null
of a cross-validated *pooled* AUC under within-subject permutation is not 0.5 — pooling within-subject and
between-subject comparisons while the folds hold subjects out biases it low. This is now error-catalogue
rule 72, and its corollary governs how the table below is read: **the AUC *level* is biased, so the
*difference* between representations is the trustworthy quantity**, which is exactly what the increments
measure.

E159's repaired gate passes both parts: the two families' nulls agree to **0.00724** (bar 0.02), so there
is no differential memorisation by the wider representation, and each real AUC exceeds its own 50-draw
null maximum.

---

## Result

| | out-of-fold AUC, subjects held out whole |
|---|---|
| published CNN, 10 PCs | 0.8092 |
| **eleven hand-built spectral features** | **0.9426** |
| both | 0.9485 |

| increment (negative = the addition helps) | | |
|---|---|---|
| spectrum added to the CNN | **−0.12980** | p = 0.0000 |
| CNN added to the spectrum | **−0.00296** | p = 0.0100 |

**Both are statistically detectable at 46,948 windows; only one is materially large. The spectrum adds
44× more.**

The file's own printed label — "BOTH ADD — neither dominates" — is wrong for these magnitudes, and that
defect was written into E158's ledger row **before** E159 ran rather than corrected after it: a verdict
branch keyed on significance alone is blind to effect size at large n, which is the same family of error
as rules 37 and 71.

---

## What this does and does not license

**Does.** On this cohort, a panel of eleven quantities that each mean something outperforms the deposit's
own published learned representation of the same spectrograms, under a leakage control judged against its
measured null, with subjects held out whole and both directions tested. For a clinical monitor that is the
relevant comparison: interpretability is usually argued as a trade against accuracy, and here it is not a
trade at all.

**Does not.** Ten subjects, propofol only, one label. And the reduction tested is **the paper's stated ten
components fitted by ridge here** — not necessarily the classifier the paper itself used, and not the best
possible use of 1,280 bottlenecks. A different reduction or a different learner could close the gap; what
is refuted is the *published* reduction, not learned representations in general.

**One internal inconsistency, reported rather than resolved.** Leave-one-feature-out disagrees between the
two runs about which feature carries the panel — `exponent_1_40` at +0.04915 in E158, `spectral_entropy`
at +0.00465 in E159. That is what leave-one-out does when features are collinear, and neither is claimed.

---

## Reproduction

```
python bsde/scripts/extract_eeg_power_anesthesia.py --cohort Volunteer
python bsde/src/bsde/experiments/e159_cnn_vs_spectrum_measured_null.py
```

The extractor is validated by physiology on every case it processes: relative frontal alpha rises 0.03 →
0.12–0.19 and the aperiodic exponent steepens 0.88 → 2.2–2.6 from conscious to unconscious, which is the
canonical GABAergic signature and a positive control on the dB→linear conversion, the frequency axis and
the band edges.
