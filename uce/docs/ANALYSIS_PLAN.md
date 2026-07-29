# ANALYSIS_PLAN.md — Artifact 4

*Pre-specified 2026-07-29. Written before any real EEG was processed. Confirmatory analyses below may not be
altered after looking at their outcomes; exploratory analyses are labelled and carry no confirmatory weight.*

---

## 1. Label ontology (implements brief §8)

Stored as separate columns; **never collapsed into one variable**.

| level | variable | values | notes |
|---|---|---|---|
| L0 | `state` | awake_responsive, sleep_N1/N2/N3/REM, sedated_responsive, unresponsive_anesthesia, emergence, acute_coma, UWS, MCS_minus, MCS_plus, eMCS, LIS | physiologic/experimental state |
| L1 | `crsr_total`, `crsr_subscales`, `crsr_datetime`, `crsr_n_exams`, `crsr_gap_hours` | numeric | `crsr_gap_hours` = \|CRS-R time − EEG time\|; a gap > 24 h downgrades the label's weight |
| L2 | `passive_response` | none / primary_sensory / mismatch / global_rule / semantic | ordered, hierarchical |
| L3 | `command_following` | positive / negative / **indeterminate** | *indeterminate is mandatory*: a failed task is not a negative |
| L4 | `outcome_*` | recovery of command-following, GOSE/mRS, mortality, discharge destination | **never used as a contemporaneous consciousness label** |

**Derived primary endpoint (CMD):** `command_following == positive` AND contemporaneous
(`crsr_gap_hours` ≤ 24) behavioural examination shows no command-following.

---

## 2. Primary outcomes, by stage

| stage | primary outcome | estimand |
|---|---|---|
| S1 | recovery of a **known** simulated aperiodic exponent | absolute error vs ground truth |
| S1 | UCE v1 vs `z(mean exponent)` — strategy R-01 | paired difference in discrimination on the same subjects |
| S2 | UWS vs MCS discrimination | AUROC with subject-level CIs |
| S3 | **command-following (L3)** | within-subject detection rate against a within-subject null |
| S4 | transfer to a held-out dataset | change in AUROC and in calibration slope |
| S5 | incremental value over CRS-R + age + etiology + sedation | ΔAUROC and Δ net benefit |

---

## 3. Predictors

Computed identically for every dataset by the same locked code.

* **Aperiodic:** exponent, offset, fit R², per channel and per region.
* **UCE v1 (frozen):** as specified; plus the mandatory baseline `z(mean exponent across channels)`.
* **Spectral:** absolute and relative band power (δ θ α β γ), spectral edge 95, median frequency.
* **Complexity:** Lempel-Ziv (binarised, normalised), permutation entropy, spectral entropy.
* **Connectivity:** weighted symbolic mutual information (wSMI), debiased wPLI.
* **Suppression:** burden, burst rate, burst duration (reused conceptually from the sibling project).
* **Adequacy (Layer A):** usable duration, usable channels, flat/bridged channels, line-noise index, EMG index, artifact fraction, OOD score.

**EMG index is a predictor of interest, not only a nuisance.** If it predicts the outcome as well as the
aperiodic exponent does, the exponent result is an EMG result (strategy §4).

---

## 4. Splitting strategy (implements brief §13)

1. **Minimum unit: subject.** All windows, epochs, sessions and trials of one subject stay together.
2. **Nested CV** for any tuning: outer folds for performance, inner folds for hyperparameters. Nothing is
   selected on the outer test fold.
3. **Preprocessing and standardisation are fit on training folds only.** z-scoring reference means and SDs
   are passed explicitly (the `zscore(..., mean, sd)` signature exists to force this).
4. **Strongest validation: leave-one-dataset-out**, then leave-one-site-out (I-CARE hospitals), then
   leave-one-drug-out, then leave-one-etiology-out.
5. **Task trials:** no trial overlap across folds; runs within a session are kept together.

**Split manifests are written to `results/splits/` and hashed**, so any reported number can be traced to the
exact partition that produced it.

---

## 5. Mandatory baselines (brief §14, plus strategy R-01)

1. Chance / prevalence only
2. Band power
3. Spectral edge / median frequency
4. Aperiodic exponent + offset
5. **4b. `z(mean aperiodic exponent across channels)`** ← added by strategy R-01
6. **Frozen UCE v1**
7. Entropy / complexity
8. Connectivity summaries
9. Clinical variables alone
10. Clinical + EEG
11. Strong conventional ML (regularised GLM, gradient boosting)
12. Modern EEG encoder — only if 1–11 are exhausted and the gain survives dataset-level testing

---

## 6. Confounder and negative-control analyses (brief §16)

Each is a **probe**: train a model to predict the nuisance variable *from the same representation*.

| probe target | interpretation if it succeeds |
|---|---|
| site / machine | acquisition fingerprint present → hold out sites and re-test |
| drug identity and dose | representation is pharmacological |
| age | demographic confound |
| EMG index | representation is muscle |
| recording duration, artifact burden | representation is data quality |
| injury severity | representation is structural damage |
| outcome (L4) | representation is prognostic, not contemporaneous |

**Decision rule, pre-specified:** if a probe predicts a nuisance variable *better than* the model predicts
command-following, **and** performance drops when that nuisance is held out, the result is reported as a
failure or partial failure — not reframed.

Additional destructive controls: label permutation, phase randomisation, channel shuffling, spatial
permutation, frequency-band ablation, EMG-channel exclusion, reduced-montage simulation.

---

## 7. Command-following analysis (Layer E) — the strictest part of the plan

Because a false positive here is the most dangerous output the system can produce (strategy §8):

* **Within-subject null first.** Detection is declared against a permutation distribution built by shuffling
  cue labels *within* that subject, ≥ 1000 permutations. Group-level AUROC is never sufficient.
* **Pre-specified α and correction** across subjects; report the family-wise or FDR-controlled result.
* **Trial-count sensitivity:** report detection as a function of trials used; a result that appears only at
  full trial count is fragile.
* **Reproducibility across runs** within a session, and **across sessions** where available.
* **Negative-control instructions / rest blocks** must be negative.
* **Positive controls:** the able-bodied benchmark participants must be detected, or the pipeline is broken.
* **Abstention:** if Layer A adequacy fails, output `indeterminate`, never `negative`.

**A failed task is `indeterminate`, not evidence of absent consciousness.** This is encoded in the L3 label.

---

## 8. Calibration and abstention

* Report Brier score, calibration intercept and slope, and calibration plots for every probabilistic output.
* Recalibrate on held-out data only; report both pre- and post-recalibration.
* **Abstention policy is pre-specified**, not tuned to improve headline numbers: abstain when adequacy is
  below threshold or the OOD score exceeds threshold. Report abstention rate alongside every metric, and
  report performance *among non-abstained cases* separately from coverage.

---

## 9. Missing data

* Missing channels → reduced-montage path; **UCE v1 is not computed when a required region is absent**
  (returns NaN, per `regional_exponents`).
* Missing CRS-R → the case can contribute to L0/L2 analyses but not to L1-dependent endpoints.
* No imputation of outcome or of behavioural labels.
* Missingness is reported and tested for outcome-relatedness; if missingness is outcome-related that is a
  finding, not a nuisance.

---

## 10. Statistical inference

* Uncertainty by **subject-level bootstrap** (resample subjects, not windows).
* Repeated measures handled by hierarchical models; site as a random effect when pooling.
* Heterogeneity (I² or between-site SD) reported rather than only a pooled estimate.
* Confirmatory hypotheses (H1–H6) are fixed in `RESEARCH_STRATEGY.md` §3 before testing; everything else is
  labelled exploratory.
* Multiplicity controlled hierarchically: family per hypothesis, not per test.
* For small n, Bayesian partial pooling and regularisation are preferred to high-capacity models.

---

## 11. Stopping rules

* **Stop and report negative** if H4 cannot be rejected — i.e. every candidate marker is indistinguishable
  from an arousal marker after adjustment for arousal and severity.
* **Stop and narrow** if leave-one-dataset-out transfer fails: report per-domain models and abandon the
  universality claim.
* **Halt the command-following arm** if the able-bodied positive controls are not detected — that is a
  pipeline failure and no patient result may be reported until it is fixed.
* **No result is reported from a dataset whose licence or access terms have not been verified.**
