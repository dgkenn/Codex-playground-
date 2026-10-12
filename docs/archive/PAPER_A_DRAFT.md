# Paper A (flagship clinical) — DRAFT

**Target venue:** JAMA / JAMA Internal Medicine (clinical, methods-forward).
**Status:** DRAFT skeleton — real prose in the load-bearing sections; `[PLACEHOLDER]`
marks every quantity that must be filled from the real MIMIC-IV / eICU runs. Nothing
below is a reportable result until the pre-registered falsification battery
(`docs/BULLETPROOF_CHECKLIST.md`) and negative-control calibration pass.

---

## 1. Candidate titles

1. **Recovering Landmark Trial Results From Electronic Health Records Using Assay Noise
   as a Natural Randomizer, With Application to Reflexive Electrolyte Repletion**
2. **A Benchmark-Validated Causal Method for De-Implementation Questions: Reproducing
   Five ICU Trials From Routine Data, Then Answering One No Trial Has**
3. **Assay-Noise Instrumental Variables for Reflexive Lab-Triggered Treatment: RCT-Anchored
   Emulation and the Case of Magnesium and Potassium Repletion**

*(Working preference: Title 1 — leads with the mechanism and the application; Title 2 is
the sharpest one-line pitch if the editor wants the RCT-DUPLICATE frame foregrounded.)*

---

## 2. Structured abstract

**Importance.** Reflexive, laboratory-triggered treatments — transfusion at a hemoglobin
threshold, electrolyte repletion at a magnesium or potassium flag, bicarbonate for
acidosis — are administered millions of times a year in inpatient care, largely on habit
and order-set convention rather than trial evidence. Observational studies cannot settle
whether these treatments help, because the treatment is a near-deterministic function of
the same severity that drives the outcome (confounding by indication), and randomized
trials are unlikely to be run for most of them.

**Objective.** To develop and validate a causal method that exploits analytic assay noise
at the decision threshold as a natural randomizer, benchmark it against a library of
landmark intensive care unit (ICU) randomized trials whose answers are known, and then
apply it to the largest unanswered reflexive de-implementation question.

**Design.** Retrospective cohort with an instrumental-variable / intention-to-treat-style
design ("flag-ITT"), benchmarked against published randomized controlled trial (RCT)
truth (the RCT-DUPLICATE emulation paradigm), with pre-registered thresholds, a
falsification battery, negative-control empirical-null calibration, and external
replication.

**Setting.** Two US critical care databases: MIMIC-IV (single academic center,
derivation) and eICU-CRD (multicenter, external replication).

**Participants.** Adult ICU admissions with at least two pre-treatment measurements of the
relevant analyte within the eligibility window. `[N derivation]` admissions in MIMIC-IV;
`[N external]` admissions across `[N hospitals]` hospitals in eICU. `[CONSORT/STROBE flow
counts]`.

**Exposures.** Reflexive treatment triggered when a measured laboratory value crossed a
clinical flag: red blood cell (RBC) transfusion at hemoglobin < 7 g/dL; platelet
transfusion at platelet count < 10 000/µL; sodium bicarbonate for metabolic acidosis;
intensive insulin/glucose control; antipsychotic for delirium (contraindication-gate and
provider-preference variants); and, in the application, intravenous magnesium repletion at
magnesium < 2.0 mg/dL and potassium repletion at potassium < 3.5 mEq/L.

**Main outcomes and measures.** Primary outcome: in-hospital mortality (with 30-/90-day
mortality where linkage allowed). Primary estimand: the flag-ITT (the reduced-form effect
of noise-induced flag-crossing — the threshold-policy / de-implementation contrast),
reported with its implied local average treatment effect (LATE) interval under
weak-instrument-robust (Anderson–Rubin) inference. The primary validation metric was
calibration of the method's estimate to established RCT truth versus the naive
association.

**Results.** `[PLACEHOLDER — killer calibration figure: method estimates fall on the
RCT-truth diagonal; naive estimates fall off-diagonal toward spurious harm.]` Across the
benchmark library, the naive association indicated apparent harm of `[X]` to `[Y]`
percentage points in cases where the RCTs found no benefit; the assay-noise flag-ITT
collapsed these to `[≈0, CI]`, recovering trial truth, and reproduced the one benchmark
where a trial found harm (intensive glucose control, NICE-SUGAR). Results replicated in
eICU (`[concordance metric]`). In the application, the flag-ITT for magnesium repletion on
in-hospital mortality was `[point, AR CI]`; for potassium, `[point, AR CI]`; both
negative-control-calibrated and triangulation-bracketed.

**Conclusions and relevance.** `[If confirmed]` A method that reproduces the results of
`[k]` landmark ICU trials from routine EHR data — where the naive analysis shows the
opposite — and replicates across two hospital systems provides `[null / bounded /
supportive]` evidence on reflexive electrolyte repletion, a high-volume practice with no
trial evidence, and supplies a generalizable template for evaluating de-implementation
candidates ahead of definitive trials.

---

## 3. Introduction

Inpatient medicine runs on reflex. When a monitored laboratory value crosses a familiar
number — hemoglobin below 7, magnesium below 2.0, potassium below 3.5, platelets below
10 000 — a treatment is ordered, frequently through a standing order set, frequently
without a specific clinical decision at all. These reflexive, lab-triggered interventions
are among the highest-volume acts in hospital care: electrolyte repletion alone is ordered
tens of millions of times a year in the United States, and most of it rests on
pathophysiologic reasoning and habit rather than on evidence that treating the number
improves a patient outcome. For a small number of these reflexes, landmark trials exist
and have overturned the reasoning — restrictive transfusion is non-inferior to liberal
(TRICC, TRISS), a platelet threshold of 10 000/µL is safe (TOPPS), tight glucose control
harms rather than helps (NICE-SUGAR), bicarbonate does not benefit diabetic ketoacidosis,
and antipsychotics do not reduce mortality in delirium (MIND-USA). For the large majority,
including the single highest-volume reflex (electrolyte repletion), there is no trial at
all, and none is likely to be funded.

The natural instinct is to answer these questions observationally, from the vast
electronic health record (EHR) data that captures every threshold crossing and every
order. That instinct fails, and it fails in a specific, unusually severe way. Reflexive
treatment is a near-deterministic function of the measured severity signal — the whole
point of a reflex is that low values get treated — and that same severity drives the
outcome. This is confounding by indication in its purest and most intractable form: the
patients who get transfused, repleted, or bicarbonated are the sicker patients, so the
naive association between treatment and outcome is contaminated by the reason for
treatment, typically manufacturing an apparent harm of several to ten percentage points on
mortality where the truth is null. It is precisely this artifact that makes a reviewer
dismiss any observational claim in this space out of hand ("confounding by indication is
observationally unsolvable — that is why we do trials"), and no amount of covariate
adjustment, propensity weighting, or within-patient design removes it, because the
confounder is the continuous severity the clinician is reacting to and the analyst cannot
fully measure.

The escape is hiding in the measurement itself. A measured laboratory value `W` is not the
true latent severity `T`; it is `W = T + ε`, where `ε` is analytic assay noise plus
short-term biologic fluctuation. Chemistry assays have a characterized, auditable
coefficient of variation, and repeated draws on the same platform let that noise be
estimated directly from serial-pair variance. Now consider the patients whose *true* value
sits near the clinical flag. Conditional on that true severity, which side of the flag the
*noisy* measured value happens to land on is driven by lab error, not prognosis — it is
as-good-as-random. The noise thus supplies an exogenous, severity-independent nudge into
or out of treatment: a valid instrument, whose identifying assumption is the analytic
imprecision of a chemistry assay rather than the far weaker assumptions behind
provider-preference instruments (habit is correlated with overall care intensity) or
regression-discontinuity smoothness (there is no true discontinuity in a reflex). Because
a per-patient treatment effect scaled through this weak first stage is intrinsically
imprecise, we do not lead with it. We lead with the **flag-ITT**: the reduced-form effect
of noise-induced flag-crossing, which is exactly the de-implementation policy contrast a
health system actually sets (move or remove the threshold) and is well-powered to a
sub-percentage-point resolution — reported always with its implied-LATE interval so a null
is never silently over-read.

A single clever instrument, however, is not a paper a clinical journal should trust, and
we do not ask it to be. We adopt the RCT-benchmarked-emulation paradigm (RCT-DUPLICATE;
Franklin, Schneeweiss and colleagues): before applying the method to any question we
cannot check, we require it to *reproduce trials we already believe*. We assemble a
library of landmark ICU RCTs with settled answers, show that the naive EHR analysis of
each produces the characteristic spurious harm, and then show that the assay-noise flag-ITT
recovers the trial result — the null where the trial found a null, and the harm where the
trial (NICE-SUGAR) found harm. Only after the method passes this calibration, replicates
in a second, multicenter database (eICU), and survives a pre-registered falsification
battery with negative-control empirical-null calibration on every estimate, do we turn it
on the unanswered question: reflexive magnesium and potassium repletion. The contribution
is therefore twofold — a generalizable, benchmark-validated method for the reflexive-care
class of de-implementation questions, and a concrete, precise answer to the largest such
question that no trial has addressed.

---

## 4. Methods

### 4.1 Study design and reporting

Retrospective cohort study using an assay-noise instrumental-variable design, structured as
an RCT-benchmarked emulation (RCT-DUPLICATE paradigm). We report per STROBE (observational)
and the target-trial-emulation reporting conventions. All primary specifications,
thresholds, bandwidths, severity controls, estimands, outcomes, and analysis order were
pre-registered before any outcome regression was examined
(`docs/DECONFOUNDING_PREREGISTRATION.md`); deviations are labeled post-hoc/exploratory.

### 4.2 Data sources and cohort

- **Derivation:** MIMIC-IV (Beth Israel Deaconess Medical Center), adult ICU admissions.
- **External replication:** eICU-CRD (`[~200]` hospitals across the US), adult ICU stays,
  used to re-run the identical benchmark library and the application in independent
  hospitals with different case-mix, equipment, and ordering culture.

Eligibility for each analyte required at least two pre-treatment measurements within the
decision window (needed to construct the noise-free severity control; §4.4). We report a
STROBE/CONSORT-style flow diagram of exclusions and characterize the excluded
single-draw-then-treat cohort (which selects out the sickest, immediately-treated patients)
so external validity is bounded to "decisions preceded by a confirmatory draw."
`[Table 1 = cohort characteristics by database and by benchmark case.]`

### 4.3 The benchmark library (validation spine) and the application

Benchmark cases were chosen to have clean, settled RCT truth and a plausible naive
confounding artifact, and their thresholds were pre-registered:

| Case | Trigger / flag | RCT truth (benchmark) |
|---|---|---|
| RBC transfusion | hemoglobin < 7 g/dL | restrictive non-inferior (TRICC, Hébert *NEJM* 1999; TRISS, Holst *NEJM* 2014) — **null** |
| Platelet transfusion | platelet < 10 000/µL | 10k threshold safe (TOPPS, Stanworth *NEJM* 2013) — **null** |
| Bicarbonate in DKA | HCO₃ / pH flag | settled no mortality benefit — **null** |
| Intensive glucose control | glucose / insulin protocol | intensive control **harms** (NICE-SUGAR *NEJM* 2009) |
| Antipsychotic for delirium | delirium (gate: QTc; provider-preference) | no mortality benefit (MIND-USA, Girard *NEJM* 2018) — **null** |

The graded truth matters: recovering both the nulls **and** the NICE-SUGAR harm (and, in a
pre-registered stratified sub-test, the *contested* liberal-favoring signal in cardiac
surgery / acute MI transfusion — TITRe2, MINT — against the general-ICU null) is a stronger
validation than recovering a single null.

**Application (evidence vacuum):** intravenous magnesium repletion at magnesium < 2.0
mg/dL, and potassium repletion at potassium < 3.5 mEq/L — high-volume, trial-infeasible,
no prior RDD/IV literature.

### 4.4 The instrument and identification intuition

For an analyte with measured value `W = T + ε` (true severity `T`, analytic + short-term
noise `ε`) and clinical flag `c`, the instrument at a decision draw is

  `Z = 1(W < c)`  — did the *measured* value land below the flag.

Conditional on the true value `T`, `Z` varies only through `ε`, which is assay error and is
independent of prognosis. The identification therefore requires a severity control that
captures `T` without sharing the noise `ε` that drives `Z`:

- **Primary control (two-draw case):** the midpoint `(M1 + M2)/2`. A known-truth
  Monte-Carlo simulation (`docs/sim_assay_noise_iv.py`) shows that under equal-variance
  Gaussian noise the instrument driver `∝ (ε₂ − ε₁)` is orthogonal to the true-severity
  driver `∝ (ε₁ + ε₂)` — `Cov = Var(ε₂) − Var(ε₁) = 0` — so the midpoint control exactly
  balances `Z ⟂ T`. Crucially, the intuitive "fix" of controlling on `M1` alone is the
  *biased* choice (it leaves `ε₁` in both `Z` and the residual). The equal-draw-variance
  premise is **tested**, not assumed (σ by draw context and inter-draw interval).
- **Robust control (renewal case):** a local leave-one-out proxy `T̂_{i,-t}` built from all
  of a patient's *other* pre-treatment draws (nearest-neighbor / local-linear smoother),
  whose bias → 0 as draws accumulate and which also buys precision.

Noise is estimated **from the data**: assay coefficient of variation and serial-pair
variance, re-estimated by inter-draw interval to separate analytic imprecision from
biologic drift (drift signature = σ growing with Δt; lag-1 autocorrelation of detrended
residuals ≈ 0 is the classical-error check).

### 4.5 Estimand: the flag-ITT (and why not the LATE)

The decisive estimand is the **flag-ITT** — the reduced-form effect on the outcome of
noise-induced flag-crossing, `Y ~ Z | control`. This is the threshold-policy /
de-implementation contrast (what happens if the flag is moved or removed) and, unlike a
scaled LATE, it is well-powered (sub-percentage-point minimum detectable effect on
mortality). A power/MDE analysis (`docs/power_mde_assay_noise_iv.py`) shows the per-patient
mortality LATE is *not* identifiable in practice (MDE 5–12 pp at a realistic 3–6 pp first
stage), so scaling a weak first stage into a precise mortality LATE is a Type-I illusion.
Two disciplines follow and are pre-registered: (1) the flag-ITT is **always** reported with
its implied-LATE interval (ITT ÷ first stage, Anderson–Rubin CI), so a null ITT reads
explicitly as "no effect **or** underpowered," never silently as "no effect"; (2) we state
plainly whether a given claim is about *the threshold as a bundled policy lever* (clean) or
*the specific treatment* (which re-inherits the exclusion restriction) — it cannot be both.

### 4.6 Falsification battery (pre-specified, run in order; failing #1 stops the analysis)

1. **Density / heaping test** (McCrary; Cattaneo–Jansson–Ma) at the round flag; an atom or
   density jump falsifies local continuity → **donut hole** (drop `W = c ±` one reporting
   unit) and test `<` vs `≤`.
2. **Equal-variance / noise-structure check:** σ by inter-draw interval and severity
   stratum; lag-1 autocorrelation of detrended residuals ≈ 0 (analytic, not biologic).
3. **Covariate balance on `Z`** (age, sex, prior-severity proxies, comorbidity proxies)
   conditional on the severity control; all |std. diff.| < 0.05.
4. **Bundle-balance battery** — the substantive exclusion threat. Regress on `Z`:
   co-repletion (Mg+K+Phos ordered together), time-to-next-panel, number of labs in 24 h,
   telemetry/monitoring cadence, ICU transfer, LOS. Any discontinuity ⇒ the flag triggers a
   *care bundle*, not just the treatment, and the reduced form is an intent-to-flag effect,
   not a treatment effect. We disclose that ward-level bundle balance is untestable in
   MIMIC (chartevents are ICU-only).
5. **Weak-IV-robust inference:** Olea–Pflueger effective F; Anderson–Rubin / Fieller
   confidence sets replace the delta-method CI as the headline.
6. **Selection-into-eligibility:** characterize the excluded single-draw cohort; test
   whether provider / time-of-day predicts having a second pre-treatment draw; test
   `Z ⟂ n_i^E`.
7. **Competing-risks / LOS robustness:** balance LOS and discharge-to-hospice on `Z`;
   re-run with 30-/90-day mortality; Fine–Gray (death vs discharge-alive).
8. **Bandwidth × functional-form sensitivity surface** (pre-registered grid, not one spec).

### 4.7 Negative-control empirical-null calibration (mandatory on every estimate)

Every estimate is calibrated against an empirical null built from ≥ `[20–50]` negative-
control outcomes the treatment cannot plausibly affect (Schuemie–Madigan). This *measures*
residual bias rather than assuming it away: if the negative-control null is centered at
zero with small spread, the target estimate's calibrated p-value and interval are reported;
if the null is shifted, the design is declared biased and the estimate is corrected to (or
rejected against) the empirical null. A known-truth simulation (`docs/sim_instruments.py`)
established that for preference-type instruments covariate balance can look clean while the
estimate is badly biased, and the negative-control-outcome coefficient tracks that bias
almost exactly — so negative-control calibration is a **required** gate, not an optional
robustness check.

### 4.8 Triangulation into convergent bounds

Each application estimate is bracketed by designs of known bias sign (`docs/triangulate.py`):
harm-biased designs (naive/IPTW, provider-preference IV, within-patient FE; sicker → more
treatment → worse) give an upper bound; a benefit-biased design (strata where the sickest
are *withheld* treatment, e.g., renal impairment / comfort-care) gives a lower bound; the
assay-noise flag-ITT is the ~unbiased anchor that must sit **inside** the bracket (a
falsifiable check). We report the interval, and are explicit that decisiveness comes from
the anchor's own precision, not from the (often wide) bracket.

### 4.9 External replication

The identical benchmark library and application are re-run in eICU-CRD, a multicenter
database with independent hospitals, equipment, and ordering conventions. Concordant
recovery of RCT truth across two data ecosystems — same method, different hospitals — is
the single largest lift in perceived rigor and the reply to "this is a MIMIC artifact."

### 4.10 Pre-registration and statistics

Thresholds, bandwidths (e.g., magnesium ±0.15 primary, ±0.10/±0.20 sensitivity), severity
control (midpoint primary; leave-one-out for renewal; M1-only labeled sensitivity),
estimand (flag-ITT + implied-LATE), primary/secondary outcomes, and strata are locked
before unblinding. Inference: HC1 for single-decision; patient-clustered (CR2 / wild
bootstrap) for the renewal design; effective F reported throughout. Multiplicity across the
benchmark-plus-application family is controlled by a pre-registered primary outcome per
case and Benjamini–Hochberg FDR across the family. Analyses in Python (numpy/scipy/
statsmodels); code and pre-registration are versioned in the study repository.

---

## 5. Results (outline + figure/table specs)

*(All quantities `[PLACEHOLDER]` pending the real MIMIC-IV + eICU runs; the engines emit
each table row and figure series directly.)*

### 5.1 Cohort and flow
- STROBE/CONSORT flow (`[N screened → N eligible → N with ≥2 pre-tx draws]`), by database
  and case; excluded single-draw cohort characterized (severity, mortality).
- **Table 1** — cohort characteristics by database (MIMIC-IV vs eICU) and by benchmark case.

### 5.2 THE KILLER FIGURE — calibration plot (the paper *is* this figure)

**Figure 1. Method calibration against randomized-trial truth.**
- **Axes:** x = RCT truth (effect size, risk-difference scale) for each benchmark case;
  y = the estimate recovered from EHR data. A 45° diagonal = perfect recovery.
- **Series A (method):** assay-noise flag-ITT per case, with Anderson–Rubin 95% CI —
  expected to sit **on the diagonal** (nulls near 0; NICE-SUGAR harm at its true positive
  value).
- **Series B (naive):** the naive treatment–outcome association per case — expected to fall
  **off the diagonal**, systematically displaced toward spurious harm (the 8–11 pp artifact
  for bicarbonate/platelet/antipsychotic; smaller for RBC).
- **Overlay:** eICU replication points (open markers) beside MIMIC (filled) to show
  cross-database concordance on the same diagonal.
- **One-glance message:** naive is confounded (off-diagonal, false harm); the method is
  calibrated (on-diagonal); it holds in two databases.

**Figure 2 (companion). Per-case forest plot** — naive vs method (flag-ITT) vs RCT 95% CI,
stacked by case, both databases.

### 5.3 Benchmark validation — Table 2

**Table 2. Benchmark library: recovery of trial truth.**

| Case | RCT truth (source) | Naive assoc. (RD, CI) | Method flag-ITT (RD, AR CI) | Implied LATE (AR CI) | NC-calibrated p | eICU concordance |
|---|---|---|---|---|---|---|
| RBC @ Hb<7 | null (TRICC/TRISS) | `[+X]` | `[≈0]` | `[…]` | `[…]` | `[…]` |
| Platelet @ <10k | null (TOPPS) | `[+X false harm]` | `[≈0]` | `[…]` | `[…]` | `[…]` |
| Bicarbonate (DKA) | null | `[+X false harm]` | `[≈0]` | `[…]` | `[…]` | `[…]` |
| Intensive glucose | **harm** (NICE-SUGAR) | `[+X]` | `[+ (recovers harm)]` | `[…]` | `[…]` | `[…]` |
| Antipsychotic (delirium) | null (MIND-USA) | `[+X false harm]` | `[≈0]` | `[…]` | `[…]` | `[…]` |

Narrative: where naive shows spurious harm of `[X–Y]` pp, the method collapses it to `[≈0]`,
matching the trials; the one true-harm case (NICE-SUGAR) is recovered as harm; results
replicate in eICU. Falsification battery outcomes reported per case (density/heaping pass,
bundle-balance pass/fail-with-disclosure, effective F, competing-risks stability).

### 5.4 Application — Table 3

**Table 3. Reflexive electrolyte repletion (evidence vacuum).**

| Analyte / flag | First-stage F | Flag-ITT (RD, AR CI) | Implied LATE (AR CI) | Triangulation bracket [lower, upper] (anchor inside?) | NC-calibrated | eICU |
|---|---|---|---|---|---|---|
| Magnesium < 2.0 | `[…]` | `[…]` | `[…]` | `[…]` (`✓`/`✗`) | `[…]` | `[…]` |
| Potassium < 3.5 | `[…]` | `[…]` | `[…]` | `[…]` (`✓`/`✗`) | `[…]` | `[…]` |

Secondary outcomes: arrhythmia proxy, ICU transfer, LOS, over-repletion (hyper-Mg/hyper-K).
Interpretation is stated in the pre-registered decision frame (precise null → consistent
with de-implementation; bounded benefit excluded by the triangulation bracket → supports
de-implementation; wide interval → inconclusive, RESTRAINT-type trial motivated).

### 5.5 Robustness
- Bandwidth × functional-form × control sensitivity surface (stable / spec-dependent).
- Renewal vs single-decision estimates; effective noise-complier count vs single-draw count
  (the headline power statistic).
- Bidirectional / multi-hospital eICU checks.

---

## 6. Discussion

**What it means for practice.** `[If the benchmark calibration holds and the application
lands as a precise null or a benefit-excluding bracket]` reflexive electrolyte repletion —
one of the highest-volume acts in hospital medicine — would join transfusion, platelet, and
glucose control as a reflex that pathophysiology recommends but outcomes do not support at
the treated margin, strengthening the case for de-implementation or a higher/absent
threshold, and directly motivating a pragmatic confirmatory trial (RESTRAINT). The result
is expressed in the contrast health systems can actually set — move or remove the flag —
which is the flag-ITT, not an abstract per-patient effect.

**The generalizable method.** The larger contribution is a template for the entire class of
reflexive, lab-triggered de-implementation questions, of which we have catalogued ten
(`docs/PORTFOLIO_10_TRIALS.md`). Confounding by indication is not defeated by one trick; it
is defeated by matching the source of exogenous variation to *how the treatment is actually
decided* — assay noise for lab-flag triggers, and, in companion work, contraindication-gate
noise, nurse-PRN-administration and provider-preference instruments for symptom-triggered
care — all disciplined by RCT-anchored calibration, negative-control empirical nulls, and
triangulation bounds. The benchmark-then-apply structure converts "trust my weak
instrument" into "watch it reproduce trials you already believe," which is the credibility
paradigm clinical journals now accept for observational causal claims.

**Limitations (stated honestly).**
1. **Weak per-patient LATE.** The instrument's first stage is small; the per-patient
   mortality LATE is not identifiable in practice. We therefore make claims at the
   well-powered flag-ITT / threshold-policy level and report implied-LATE intervals so no
   null is over-read. A null flag-ITT with a weak first stage does not by itself prove the
   treatment inert.
2. **Exclusion restriction (bundle).** The flag may trigger a care bundle (co-repletion,
   monitoring, attention), not the treatment alone; the flag-ITT inherits this. We test it
   (bundle-balance battery) but cannot test ward-level bundles in MIMIC (chartevents are
   ICU-only) — disclosed, not hidden.
3. **ICU-only, and selection into ≥2 draws.** Findings generalize to ICU decisions preceded
   by a confirmatory draw; the sickest single-draw-then-treat patients are excluded and
   characterized separately.
4. **Outcome ascertainment.** Secondary outcomes (arrhythmia, some benchmark endpoints) are
   subject to ascertainment bias (sicker → more testing); negative-control calibration is
   the mitigation.
5. **MIMIC calendar obfuscation** precludes shortage/guideline difference-in-differences
   designs; eICU replication and the assay-noise design are the substitutes.
6. **Assay-noise magnitude varies by analyte** — magnesium ~6.7% of the flag gap (adequate),
   hemoglobin only 1–2% (weak noise slice; the RBC benchmark leans on the well-documented
   near-threshold first stage rather than the noise slice alone).

---

## 7. Novelty statement (precise, versus Eckles 2025 and Bosch 2022)

Noise-induced randomization at a decision threshold is not, in itself, new, and we state so
plainly. **Eckles, Ignatiadis, Wager and Wu (*Biometrika* 2025)** formalized treating a
running variable's *known* measurement noise as the randomization device in regression
discontinuity and reweighting to balance the latent variable — this is our foundational
methods citation, not our invention. **Bosch et al. (*Ann Am Thorac Soc* 2022;19(7):
1177–1184)** ran a fuzzy regression discontinuity at hemoglobin 7.0 g/dL *in MIMIC-IV*
(and eICU/Premier), justified verbatim by the argument that "measurement noise
pseudorandomizes" patients on either side of the threshold, finding transfusion mostly
null on organ dysfunction — so noise-at-a-clinical-threshold has a direct precedent in our
exact database, and we cannot and do not claim it as novel. Our defensible, narrower
contribution is fivefold: (1) a **formal, estimable noise model** — the instrument is built
*from* the analytic assay coefficient of variation and serial-pair variance, an auditable
CLIA-grounded quantity, rather than invoked as prose to justify RDD smoothness; (2) a
**renewal / repeated-decision extension** — a sequence of noise-randomized decisions per
patient with an absorbing treatment (predictably censored to avoid collider conditioning),
a terminal shared outcome, and a within-subject leave-one-out control for a
serially-correlated latent severity, which has no prior art and recovers ~√(mean draws per
patient) of the power the single-decision design discards; (3) explicit
**contraindication-gate, nurse-PRN and provider-preference instruments** with a
trigger-matching framework that routes each treatment to the instrument fitting how it is
actually decided; (4) the **benchmark-then-apply, RCT-DUPLICATE validation** across a
library of trials with negative-control empirical-null calibration on every estimate and
external replication in a second database; and (5) the substantive result that for this
design **covariate balance is insufficient and negative-control calibration is mandatory**,
plus application to magnesium and potassium repletion — questions with *no* RCT — where
Bosch studied hemoglobin, a question multiple definitive trials had already settled. In
short: Eckles gives the estimator, Bosch gives the clinical precedent, and our novelty is
the estimable noise model, the renewal machinery, the matched-instrument framework, and the
benchmark-validated deployment to trial-infeasible reflexive care.

---

*Cross-references: `docs/PATH_TO_TOP_TIER.md` (narrative + figure spec),
`docs/VALIDATION_KNOWN_TRUTH.md` (benchmark logic), `docs/BULLETPROOF_CHECKLIST.md`
(gates), `docs/PORTFOLIO_10_TRIALS.md` (trigger taxonomy), `docs/ASSAY_NOISE_IV_METHODOLOGY.md`
(identification + renewal), `docs/DECONFOUNDING_GAP_ANALYSIS.md` (honest ledger, power,
prior art), `docs/DECONFOUNDING_TRIANGULATION.md` (bounds),
`docs/DECONFOUNDING_PREREGISTRATION.md` (locks). Companion methods paper (Paper B) carries
the renewal derivation and new instruments; RESTRAINT protocol (Paper C) is the confirmatory
trial.*
