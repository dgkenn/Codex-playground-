# RESEARCH_STRATEGY.md — Artifact 1

*Source of authority: `RESEARCH_PROGRAM_BRIEF.md` (investigator-supplied, immutable). This document is the
project's own strategy and may be revised; the brief may not. Every departure from the brief is recorded in
§9 with its reason, per brief §25.*

*Status: written 2026-07-29, before any dataset was downloaded or any EEG processed. Nothing in this document
is a result.*

---

## 0. FINDING BEFORE DATA — what UCE v1 actually is, established by algebra alone

**This section exists because it changes the baseline the whole project is measured against, and it required
no data to establish.**

The frozen construct is

```
UCE v1 = 0.696 × z(frontal aperiodic exponent) + 0.718 × z(posterior aperiodic exponent)
```

reportedly derived from a two-feature PCA explaining ≈ 96.8 % of variance.

Three facts follow immediately, and all three are arithmetic rather than empirical:

**(a) The weights carry no information.** For two *standardized* variables the correlation matrix is
`[[1, r], [r, 1]]`, whose eigenvectors are **always** `(1/√2)(1, 1)` and `(1/√2)(1, −1)` — *independent of r*.
So PC1 of any two z-scored variables that are positively correlated has equal loadings by symmetry, not by
discovery. The stated weights are a unit vector (‖w‖ = 1.0000) whose mean is **0.7070**, against
1/√2 = **0.7071**. The 0.696/0.718 asymmetry (ratio 1.032) is consistent with rounding or a covariance-rather-
than-correlation PCA; it is not a finding about frontal versus posterior cortex.

**(b) "96.8 % of variance" is a restatement of one correlation.** PC1 variance-explained for two standardized
variables is exactly `(1 + r)/2`. Therefore 0.968 ⟹ **r(frontal, posterior) = 0.936**. The headline number is
not evidence that a latent consciousness axis was found; it is evidence that **the two inputs are nearly the
same measurement**.

**(c) Consequently UCE v1 ≈ a one-feature model.** To a very good approximation it is the mean of two z-scored,
94 %-correlated quantities — i.e. **a whole-head aperiodic exponent**.

This is not a claim that UCE v1 is useless. A whole-head aperiodic exponent may well be an excellent arousal
marker, and several of the investigator's provisional results are exactly what a good arousal marker would
produce. It is a claim about **how UCE v1 must be described and what it must be benchmarked against**.

> **Operational consequence, binding on this project.** The frozen UCE v1 must be evaluated against
> `z(mean aperiodic exponent across all available channels)` as a mandatory baseline (added to the brief's
> §14 list as baseline 4b). **If UCE v1 does not measurably beat that single-feature baseline, the
> frontal/posterior structure is decorative and must be dropped from all descriptions of the construct.**
> This is a cheap, decisive test and it is scheduled first (see `NEXT_ACTIONS.md`, action N2).

**Prior-art note.** This pattern — two measurements taken in different *places* turning out to be the same
*thing* — is documented three times in this investigator's other project (see
`../CLAUDE.md`, error-catalogue rule 28: background vs intra-burst spectrum, and topography vs
median-across-channels, both predicted to be independent and both redundant). Frontal versus posterior
aperiodic exponent is the third instance. Treating it as such at the outset is the single most useful thing
this document can do.

---

## 1. Precise problem definition

**The question the project must answer.** In a subject who cannot reliably demonstrate cognition behaviorally,
does the EEG contain evidence of (i) preserved capacity for organized cortical processing, (ii) hierarchical
stimulus processing, or (iii) intentional, instruction-locked modulation — and can that evidence be separated
from arousal, sedation, injury severity, artifact, site, and prognosis?

**What the project is not.** It is not an attempt to measure subjective experience. Nothing in EEG can
establish phenomenal consciousness; the brief's §26 prohibition on metaphysical language is adopted without
qualification. The programme's object is **capacity and command-following**, which are behaviourally and
physiologically defined.

**The unit of inference is the recording-in-context**, not the patient. A patient may be command-following at
one session and not at the next; the framework must represent that as fluctuation, not as measurement error.

---

## 2. Construct definitions (binding — used identically in code and prose)

These are deliberately operational. Where a construct cannot be operationalised in available data, that is
recorded rather than fudged.

| construct | operational definition in this project | what it is NOT |
|---|---|---|
| **Arousal** | position on a wake–sleep–anaesthesia axis; behaviourally, eye opening and stimulus-induced state change | not awareness; not cognition |
| **Responsiveness** | observable, examiner-elicited motor or verbal output (CRS-R subscales) | not consciousness; requires intact effectors |
| **Organized cortical dynamics** | spontaneous-EEG properties indicating differentiated, integrated, non-stereotyped activity (complexity, connectivity, metastability) | not proof of cognition; a *capacity* claim only |
| **Hierarchical processing** | graded evidence that responses progress from primary sensory → deviance detection → global-rule/semantic | a low-level ERP is **not** evidence of consciousness |
| **Command-following** | intentional, instruction-locked modulation of brain activity, detected against a within-subject null | not the same as behavioural response |
| **Cognitive motor dissociation (CMD)** | command-following detected by brain measure **while** contemporaneous behavioural examination shows none | not "covert consciousness" in general |
| **Injury severity** | structural/clinical burden (etiology, imaging, clinical scores) | a strong confounder of every EEG marker above |
| **Prognosis** | future functional state | **never** used as a contemporaneous consciousness label |

**Rule adopted from the brief §2 and enforced in code review:** no function, variable, column, or figure label
may use one of these words for another. A column called `conscious` is prohibited.

---

## 3. Testable hypotheses

Stated so that each can fail. H1–H3 are the confirmatory spine; H4–H6 are the falsification tests that make
the spine meaningful.

**H1 (capacity → command-following).** Spontaneous-EEG measures of organized cortical dynamics, measured in
task-free periods, predict independently detected intentional command-following in the same subject.
*Falsified if* task-positivity is not predictable above chance from resting features, patient-level, in the
Bath dataset.

**H2 (dimensionality).** The joint space of arousal, organized dynamics, and command-following requires **more
than one** dimension; a single axis (of which UCE v1 is a candidate) is insufficient.
*Falsified if* a single component explains command-following as well as the multidimensional model does.
**Note the asymmetry deliberately built in: the brief's own hypothesis is that one dimension is not enough, so
H2 is framed to be falsifiable in the direction that would embarrass the project's premise.**

**H3 (separability).** The representation that predicts command-following is separable from one that predicts
arousal and from one that predicts injury severity/prognosis.
*Falsified if* a probe trained on the representation predicts drug, site, or prognosis as well as it predicts
command-following.

**H4 (UCE construct test).** UCE v1 is an **arousal** marker, not a **cognitive-capacity** marker.
*This is stated as the DEFAULT hypothesis, not the alternative.* It is rejected only if UCE v1 predicts
command-following or perturbational complexity **after** adjustment for arousal state and injury severity.

**H5 (redundancy).** UCE v1 adds nothing over `z(mean aperiodic exponent)` — see §0.
*Rejected if* UCE v1 beats the single-channel-average baseline on any pre-specified endpoint.

**H6 (dissociation survival).** Any surviving marker must behave correctly in the known dissociations:
preserved in **locked-in syndrome** (awareness with no motor output), preserved in **ketamine** (unresponsive
with experience), preserved in **REM/propofol dreaming** (unresponsive with reported experience).
*A marker that collapses in any of these is an arousal or responsiveness marker, whatever else it predicts.*

---

## 4. Competing explanations to be excluded (each mapped to a control)

| competing explanation | why plausible | control |
|---|---|---|
| **EMG/muscle** | aperiodic exponent is strongly contaminated by broadband EMG; awake patients move more | EMG-heavy channel exclusion; high-band ablation; paralysed-subject data where obtainable |
| **Fitting-range artifact** | the aperiodic exponent depends heavily on the fit range and on whether oscillatory peaks are modelled | sensitivity sweep over fit ranges and fitting methods; pre-registered primary range |
| **Filter/reference choice** | exponent and complexity both move with referencing and high-pass | preprocessing-variant sensitivity analysis (brief §12) |
| **Arousal alone** | the easiest thing EEG measures | adjust for and stratify by arousal; H4 default |
| **Injury severity** | separates MCS from UWS without any consciousness content | severity probe; I-CARE |
| **Sedation** | drives spectrum directly | drug probe; drug-held-out validation |
| **Site/machine signature** | acquisition fingerprints leak | site-prediction probe; dataset-held-out validation |
| **Prognosis** | outcome correlates with everything | outcome kept at Level 4, never used as contemporaneous label |
| **Signal quality** | good recordings come from calmer, less sick patients | Layer A adequacy model reported alongside every result |

---

## 5. Why the first paper should be a falsification benchmark

The brief permits (in §25) concluding that the best first paper is methodological or negative. **This project
adopts that position now**, for three reasons:

1. The only public dataset that can supply the strongest evidence tier (command-following) is the Bath PDoC
   release, and it is small. It can *validate* a hypothesis; it cannot *train* a general model.
2. The strongest available claim is therefore a **construct-validity claim**: whether resting-state markers
   that classify behavioural DoC diagnosis also predict independently detected command-following. That is
   exactly the question the field has not answered cleanly.
3. A negative answer is publishable and useful, and the project must not be structured so that only a positive
   answer is reportable.

---

## 6. Staged design (mapped to the brief's §19 and §24 gates)

| stage | question | key data | gate |
|---|---|---|---|
| **S1 Feasibility** | does the pipeline recover known effects? does UCE v1 beat its own one-feature baseline? | synthetic EEG (known ground truth); Sleep-EDF; Chennu propofol | **A** |
| **S2 Construct validity** | is the marker arousal, severity, or capacity? | Figshare DoC; Chennu; ds005620; EBRAINS TMS-EEG | **B** |
| **S3 Command-following** | does resting capacity predict task positivity? | **Bath PDoC** (primary); EEGMMIDB + ds007554 for method development only | **B/C** |
| **S4 External validity** | does it survive held-out dataset/site/drug/etiology? | I-CARE; VitalDB; SHHS/MESA | **C** |
| **S5 Incremental utility** | does EEG add over CRS-R + clinical variables? | Bath; Figshare | **D** |
| **S6+** | prospective | not achievable with public data | **E/F** |

**Stage 1 must complete before any dataset-level modelling.** The synthetic-EEG test is the foundation: a
pipeline that cannot recover a *known* aperiodic exponent from simulated data has no business estimating one
from a patient.

---

## 7. Go / no-go criteria (pre-specified)

| gate | GO if | NO-GO / narrow if |
|---|---|---|
| **A** | aperiodic fitter recovers simulated exponents within a pre-set tolerance across SNR and fit ranges; known sleep/anaesthesia spectral effects reproduce | fitter is range-dependent beyond tolerance → restrict claims to a fixed montage/range and say so |
| **B** | a marker predicts command-following or perturbational complexity **after** adjusting for arousal and severity | marker predicts only arousal → **reclassify the project as an arousal-index paper** and stop using consciousness language |
| **C** | performance survives holding out an entire dataset | fails → separate models for acute vs chronic; abandon universality claim (permitted by brief §3) |
| **D** | adds over CRS-R + age + etiology + sedation | fails → report as a negative incremental-utility study |
| **E/F** | not reachable with public data | state so explicitly rather than implying readiness |

**Termination criterion.** If H4 cannot be rejected — i.e. UCE v1 and its successors are indistinguishable
from arousal markers after adjustment — the correct output is a **benchmark-and-negative paper**, not a
reframing. This is written down now so it cannot be renegotiated later.

---

## 8. Major failure modes, ranked by how much damage they would do

1. **Calling an arousal marker a consciousness marker.** The single most likely failure and the most harmful.
   Mitigated by H4-as-default and by the construct table in §2.
2. **A false-positive command-following detection.** Clinically dangerous; a family could be told a patient is
   aware when they are not. Mitigated by within-subject nulls, permutation, negative-control instructions, and
   an explicit abstention output.
3. **Leakage across sessions of the same patient.** Bath has repeated sessions; naive splitting would inflate
   everything. Mitigated by patient-level splitting as the *minimum* and session-aware nesting.
4. **Reading the aperiodic exponent as physiology when it is EMG.** Mitigated by §4 controls.
5. **Circularity in H1** — defining task positivity using features that also enter the predictor. Mitigated by
   strict separation of task-window and resting-window data.
6. **Over-reading a 12-patient TMS-EEG dataset.** Used for convergent validation only; never for training.

---

## 9. Documented revisions to the brief (per §25)

| # | revision | reason |
|---|---|---|
| R-01 | **Add mandatory baseline 4b: `z(mean aperiodic exponent across channels)`** | §0 — UCE v1 is approximately a one-feature model and must be shown to beat one |
| R-02 | **Promote H4 ("UCE is an arousal marker") from an alternative to the DEFAULT hypothesis** | it is the most parsimonious explanation of every provisional result listed in brief §4; the burden of proof belongs on the consciousness interpretation |
| R-03 | **Declare the first paper to be a falsification/benchmark study** | brief §25 explicitly permits; the only command-following dataset is too small to train on |
| R-04 | **Treat "96.8 % variance explained" as retired** — it may not be quoted as evidence for the construct | §0(b): it is a restatement of r = 0.936 |

---

## 10. What would falsify the central hypothesis

The central hypothesis (brief §3) is that preserved cognitive capacity is reflected in a *reproducible
combination* of spontaneous dynamics, perturbational response, hierarchical processing, and intentional
modulation.

It is falsified if **any** of the following hold after honest analysis:

* Resting features predict command-following no better than chance at the patient level (kills H1).
* Every candidate representation predicts arousal, drug, site, or injury severity **as well as or better than**
  it predicts command-following, and loses its command-following signal once those are adjusted for (kills H3
  and H4 together).
* Cross-dataset transfer fails so completely that separate per-domain models are required, with no shared axis
  (kills the "universal" premise; the brief anticipates and accepts this outcome).
* Any surviving marker collapses in locked-in syndrome, ketamine, or dreaming states (kills the capacity
  interpretation and leaves an arousal/responsiveness marker).

**All four are realistic.** The project is designed so that reaching any of them produces a publishable
result rather than a crisis.
