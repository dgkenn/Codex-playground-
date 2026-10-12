# RESEARCH PROGRAM BRIEF — investigator-supplied, verbatim, IMMUTABLE

> **Status: this is the source document for the entire `uce/` project.** It was supplied by the investigator
> (D. Kennedy) on 2026-07-29 and is reproduced here **verbatim and unedited**. It must not be revised to match
> later findings. Every other document in this project cites it as `RESEARCH_PROGRAM_BRIEF.md`.
>
> Where the project departs from this brief — and §25 of the brief explicitly permits departure — the
> departure is recorded in `RESEARCH_STRATEGY.md` under "Documented revisions to the brief", with the reason.
> Silent drift from this document is a process failure.

---

## Framing supplied with the brief

The central strategic decision is not to claim that resting EEG directly measures consciousness. The project
should instead build and falsify a multidimensional model separating arousal, sensory/cognitive processing
capacity, command-following, and behavioral output. Cognitive motor dissociation has been demonstrated in a
large multicenter cohort, but current methods remain inconsistent, task-dependent, and poorly standardized —
leaving room for a more generalizable framework.

---

# Research Program: A Generalizable EEG Framework for Detecting Preserved Consciousness and Cognitive Capacity

You are acting as an autonomous senior computational neuroscientist, EEG methods expert, machine-learning
researcher, biostatistician, and research software engineer.

Your assignment is to design and begin implementing a rigorous research program aimed at solving one of the
most consequential problems in clinical neuroscience:

Can EEG identify preserved conscious cognitive capacity in patients or experimental subjects who cannot
reliably demonstrate it behaviorally?

This is not a request to build another generic consciousness classifier. The goal is to develop, test,
falsify, and eventually prospectively validate a clinically useful EEG framework that distinguishes preserved
cognition or awareness from arousal, motor responsiveness, sedation, neurologic injury severity, and technical
artifact.

You have substantial methodological freedom. Do not blindly implement the first proposed model. Inspect the
available data, literature, labels, confounders, and feasibility, then revise the plan when justified.

## 1. Ultimate objective

Develop an EEG-based system that can estimate several separable latent properties:

1. Arousal or wakefulness
2. Capacity for organized cortical information processing
3. Preservation of higher-order cognitive processing
4. Evidence of intentional command-following
5. Observable behavioral responsiveness
6. Confidence that the EEG contains sufficient information to make any of these judgments

The system should eventually identify cases in which cognitive processing or command-following is preserved
despite absent behavioral responsiveness, including cognitive motor dissociation.

The long-term clinical objective is not simply better discrimination statistics. It is to produce a method
that could change:

* Diagnostic classification
* Prognostic counseling
* Rehabilitation decisions
* Decisions about continued treatment
* Selection for neuromodulation
* Communication attempts
* Longitudinal tracking of recovery

## 2. Critical conceptual constraint

Do not treat "consciousness" as a single clean binary label.

Behavioral responsiveness is an imperfect proxy for consciousness because it depends on:

* Arousal
* Language comprehension
* Attention
* Working memory
* Motor planning
* Motor execution
* Hearing or vision
* Fluctuation over time
* Medication effects
* Examiner technique
* Injury location

Likewise, an EEG feature that separates wakefulness from propofol anesthesia does not necessarily detect
awareness. A feature that predicts outcome does not necessarily measure consciousness. A feature that
distinguishes minimally conscious state from unresponsive wakefulness may merely measure global injury
severity.

Maintain explicit separation between:

* Consciousness
* Arousal
* Responsiveness
* Cognition
* Command-following
* Prognosis
* Brain injury severity

Never use one as an unqualified synonym or ground truth for another.

## 3. Core scientific hypothesis

The working hypothesis is:

Preserved conscious cognitive capacity is not represented by one spectral feature. It is reflected in a
reproducible combination of spontaneous cortical dynamics, effective responsiveness to perturbation,
hierarchical stimulus processing, and — when testable — intentional modulation of brain activity.

The project should determine whether a low-dimensional representation can capture this combination across
different causes of unresponsiveness.

A strong result would establish a representation that generalizes across:

* Natural sleep
* Multiple anesthetic drugs
* Healthy wakefulness
* Acute brain injury
* Chronic disorders of consciousness
* Sedated ICU patients
* Recovery trajectories

A negative result showing that no single cross-domain axis exists would also be scientifically important. Do
not force the data to support universality.

## 4. Relevant context from the investigator's existing work

The investigator has developed a candidate EEG construct called the Universal Consciousness Equation, or UCE.

The frozen initial version is:

UCE = 0.696 × z(frontal aperiodic exponent) + 0.718 × z(posterior aperiodic exponent)

The underlying two-feature PCA reportedly explained approximately 96.8% of variance in its derivation setting.

Preliminary retrospective results reportedly include:

* Loss-of-consciousness discrimination under anesthesia
* Strong wake-versus-maintenance discrimination in propofol and sevoflurane datasets
* Temporal lead over BIS during some transitions
* Burst-suppression discrimination
* Sleep-stage performance
* Associations with delirium severity
* Associations with coma outcome
* Inconsistent but potentially informative seizure behavior

Treat all of these as provisional investigator-supplied findings, not established truths.

UCE may be:

* A genuine cross-domain coordinate
* A measure of cortical activation
* An arousal marker
* A drug-sensitive spectral marker
* A marker of brain dysfunction
* A proxy for signal quality or muscle artifact
* Useful as one component of a larger framework
* Fundamentally inadequate for detecting conscious awareness

Test these alternatives aggressively.

Do not redefine UCE after looking at final test outcomes. Preserve the frozen version as a locked baseline.
Any new model must be labeled as a separate version and evaluated independently.

## 5. Primary research question

Can a model using EEG demonstrate preserved cognitive processing or intentional brain modulation in
behaviorally unresponsive subjects while remaining robust to:

* Etiology
* Sedative exposure
* Age
* Structural injury
* Recording system
* Electrode montage
* Referencing
* Signal quality
* Site
* Dataset
* Level of arousal
* Presence or absence of motor output?

## 6. Proposed architecture of the solution

Consider a hierarchical system rather than a single score.

**Layer A: Data adequacy**

Determine whether the recording is interpretable.

Outputs might include:

* Usable duration
* Usable channels
* Artifact burden
* Electrode bridging
* Flat channels
* Line noise
* Movement or EMG contamination
* Suppression burden
* Confidence in preprocessing
* Out-of-distribution score

The system must be permitted to abstain.

**Layer B: Background brain state**

Estimate spontaneous-state properties such as:

* Spectral power
* Aperiodic exponent and offset
* Spectral peaks
* Suppression
* Burst structure
* Entropy and complexity
* Long-range temporal structure
* Microstates
* Connectivity
* Network integration or segregation
* Temporal stability and metastability
* Spatial differentiation
* Cross-frequency relationships

These characterize the substrate but must not automatically be interpreted as awareness.

**Layer C: Cortical reactivity**

Measure responses to external stimulation, potentially including:

* Auditory clicks
* Names or personally salient stimuli
* Standard and deviant tones
* Speech
* Semantic violations
* Tactile stimulation
* Eye opening
* Noxious or clinically indicated stimulation

Assess whether responses progress from primary sensory processing to higher-order or late responses.

**Layer D: Hierarchical cognitive processing**

Look for evidence of:

* Auditory discrimination
* Local-global processing
* Semantic processing
* Language comprehension
* Working-memory engagement
* Temporal prediction
* Context updating
* Attention

Do not treat a low-level evoked response as evidence of consciousness.

**Layer E: Intentional modulation**

Use task-based paradigms where subjects are instructed to alter brain activity through:

* Motor imagery
* Spatial navigation imagery
* Auditory attention
* Selective counting
* Mental arithmetic
* Music imagery
* Other paradigms supported by available datasets

Intentional, instruction-locked modulation should be treated as the strongest EEG evidence of
command-following, provided that leakage and false-positive controls are rigorous.

**Layer F: Longitudinal consistency**

Where serial EEG exists, estimate whether the patient is:

* Improving
* Declining
* Fluctuating
* Stable
* Becoming more or less testable

A trajectory may be more informative than a single recording.

## 7. Do not assume the final model form

Candidate approaches may include:

* Prespecified physiological scores
* Regularized generalized linear models
* Generalized additive models
* Bayesian hierarchical latent-variable models
* State-space models
* Hidden Markov or switching-state models
* Multiview representation learning
* Contrastive learning
* Self-supervised EEG encoders
* Domain-adversarial learning
* Invariant risk minimization
* Mixture-of-experts models
* Multitask learning
* Calibrated ensembles
* Causal representation approaches
* Weak supervision
* Positive-unlabeled learning

Favor the simplest model that survives stringent external validation.

Deep learning is justified only when it delivers meaningful gains over strong feature-based baselines and the
gain survives dataset-level external testing.

## 8. Label hierarchy

Construct an explicit label ontology before modeling.

Possible label levels include:

**Level 0: Physiologic or experimental state**

* Awake and responsive
* Natural sleep stage
* Sedated but responsive
* Unresponsive under anesthesia
* Emergence
* Acute coma
* Unresponsive wakefulness syndrome
* Minimally conscious state minus
* Minimally conscious state plus
* Emerged from minimally conscious state
* Locked-in syndrome

**Level 1: Behavioral assessment**

Prefer structured measures such as repeated Coma Recovery Scale–Revised assessments when available.

Record:

* Exact examination date and time
* Proximity to EEG
* Number of repeated examinations
* Best and contemporaneous diagnosis
* Sedation status
* Sensory or motor limitations
* Examiner confidence

**Level 2: Passive cortical processing**

Examples:

* Preserved sensory evoked response
* Mismatch response
* Local-global response
* Semantic response
* Higher-order association response

**Level 3: Active command-following**

Examples:

* Positive task-based EEG
* Positive task-based fMRI
* Reproducible intentional modulation
* Successful EEG-based communication

**Level 4: Outcome**

Keep outcome separate from contemporaneous consciousness.

Potential outcomes:

* Recovery of command-following
* Functional status
* Disability scale
* Communication recovery
* Mortality
* Discharge destination
* Long-term quality of life

## 9. Ground-truth policy

There is no perfect ground truth. Use triangulation.

Potential evidence sources include:

* Repeated expert behavioral examination
* Task-based EEG
* Task-based fMRI
* FDG-PET
* TMS-EEG or perturbational measures
* Longitudinal recovery
* Eventual communication
* Clinician consensus

Build analyses under multiple defensible label definitions.

Use latent-class or Bayesian models if appropriate to estimate the unobserved state from several imperfect
tests.

Do not use future recovery as if it proves that the patient was conscious at the earlier time point. It is
prognostic supporting evidence, not direct contemporaneous ground truth.

## 10. Dataset discovery

Search systematically for accessible datasets covering as many of these domains as possible:

* Disorders of consciousness
* Acute coma and ICU EEG
* Cardiac arrest
* Traumatic brain injury
* Stroke
* Task-based cognitive motor dissociation
* TMS-EEG
* Propofol anesthesia
* Volatile anesthesia
* Ketamine
* Dexmedetomidine
* Xenon, if available
* Natural sleep
* Locked-in syndrome
* Healthy command-following paradigms

Prioritize datasets with:

* Raw EEG
* Subject-level identifiers
* Precise state labels
* Medication timing
* Repeated behavioral assessments
* Stimulus or task event markers
* Longitudinal outcomes
* Multiple sites
* Publicly documented acquisition details

Create a dataset registry containing:

* Dataset name
* Access route
* License
* Citation
* Population
* Number of participants
* Number of recordings
* EEG channels
* Sampling rate
* Reference
* Recording duration
* Available labels
* Event markers
* Sedation data
* Behavioral examinations
* Outcome data
* Site structure
* Known limitations
* Potential leakage risks

Do not download massive datasets indiscriminately. First establish scientific value, licensing, expected
storage, and computational cost.

## 11. Literature review goals

Build an evidence table covering:

* Cognitive motor dissociation
* Covert consciousness
* Disorders-of-consciousness diagnostic standards
* Active EEG paradigms
* Passive EEG paradigms
* TMS-EEG and perturbational complexity
* EEG complexity metrics
* Anesthesia and consciousness
* Sleep–anesthesia–coma comparisons
* Criticality and metastability
* Aperiodic EEG physiology
* Existing commercial or clinical EEG indices
* Prognostic EEG models
* Multicenter external-validation studies
* Failed replication or negative studies
* Ethical guidance on communicating covert-consciousness results

For every candidate biomarker, record:

* Intended construct
* Actual label used
* Population
* Sample size
* Internal validation
* External validation
* Effect size
* Calibration
* Confounder handling
* Availability of code
* Availability of data
* Replication status
* Primary limitations

Focus especially on cases where a proposed consciousness marker failed under:

* Ketamine
* REM dreaming
* Neuromuscular blockade
* Locked-in syndrome
* Severe cortical injury
* Drug changes
* Cross-site testing

These dissociations are useful tests, not nuisances.

## 12. Preprocessing requirements

Create a modular, version-controlled EEG pipeline.

It should support:

* EDF/BDF/BrainVision and other common formats
* Channel-name harmonization
* Unit normalization
* Sampling-rate harmonization
* Configurable referencing
* Filtering with explicit edge handling
* Line-noise treatment
* Bad-channel detection
* Artifact annotation
* Optional ICA with auditable component decisions
* Epoching around events
* Continuous-window analysis
* Missing-channel handling
* Reduced-montage simulation
* Quality-control reports
* Reproducible parameter manifests

Avoid preprocessing choices that remove clinically meaningful suppression, slow activity, or transient
responses.

Run sensitivity analyses across reasonable preprocessing variants. A valid biomarker should not depend on one
arbitrary filter, reference, or artifact-removal setting.

## 13. Leakage prevention

Leakage is a central threat.

Prevent:

* Windows from one patient appearing in train and test sets
* Recordings from one patient appearing across folds
* Site-specific acquisition signatures determining labels
* File names or metadata entering models
* Post-outcome information entering predictors
* Duplicate recordings across datasets
* Overlapping task trials across train and test
* Hyperparameter selection on the external test set
* Preprocessing fit on combined train and test data
* Subject-specific baselines calculated using future periods

Primary splitting should occur at the patient level.

The strongest validation should hold out entire:

* Hospitals
* Datasets
* Recording systems
* Etiologies
* Drug classes

## 14. Mandatory baselines

Every advanced model must be compared with:

1. Chance and prevalence-only prediction
2. Basic spectral power
3. Spectral edge or median frequency
4. Aperiodic exponent and offset
5. The frozen UCE v1
6. Entropy or complexity baselines
7. Standard connectivity summaries
8. Clinical variables alone
9. Clinical variables plus EEG
10. A strong conventional machine-learning model
11. A strong modern EEG encoder, when feasible

Report whether the new method adds value beyond injury severity, age, sedation, and behavioral examination.

## 15. Evaluation framework

Do not optimize only AUROC.

Report as appropriate:

* AUROC
* AUPRC
* Sensitivity
* Specificity
* Positive predictive value
* Negative predictive value
* Likelihood ratios
* Brier score
* Calibration slope
* Calibration intercept
* Calibration plots
* Decision curves
* Confidence intervals
* Abstention rate
* Performance by subgroup
* Test–retest reliability
* Within-subject responsiveness
* Cross-site heterogeneity

For active command-following paradigms, emphasize:

* Prespecified within-subject null tests
* Permutation testing
* False-positive control
* Trial-count sensitivity
* Reproducibility across runs
* Replication with a second task
* Negative control instructions
* Positive control subjects

A clinically dangerous false positive must not be hidden by a favorable group-level AUROC.

## 16. Critical negative controls

Test whether the model is actually detecting:

* EMG
* Eye opening
* Mechanical ventilation artifact
* Electrode impedance
* Recording duration
* ICU versus laboratory environment
* Age
* Skull defects
* Sedative drug identity
* Drug concentration
* Injury severity
* Presence of sleep-like rhythms
* Time since injury
* Outcome rather than current cognitive state
* Site or machine identity

Use:

* Artifact-only models
* Channel-shuffled models
* Phase-randomized data
* Spatially permuted data
* Label permutations
* Frequency-band ablations
* EMG-heavy-channel exclusions
* Reduced-montage analyses
* Site-prediction probes
* Drug-prediction probes
* Injury-severity probes

If the latent representation strongly predicts site or drug but poorly transfers across them, treat this as
failure or partial failure.

## 17. Causal and mechanistic strategy

Pure association is insufficient for the strongest claims.

Seek convergent perturbations:

* Loss and recovery of responsiveness within the same person
* Different anesthetic mechanisms
* Neuromuscular blockade without loss of awareness
* Sleep transitions
* Auditory or cognitive task perturbations
* TMS or electrical stimulation
* Pharmacologic arousal interventions
* DBS or focused-ultrasound interventions
* Longitudinal emergence from coma

The ideal biomarker should change with genuine changes in cognitive capacity and not merely with changes in
motor output.

Explicitly evaluate whether the candidate representation mediates or predicts responses to interventions,
while avoiding unsupported causal language.

## 18. Desired end product

The eventual system may output a profile such as:

* Recording adequacy: high
* Arousal substrate: low to moderate
* Organized cortical dynamics: preserved
* Higher-order passive processing: probable
* Intentional command-following: detected
* Behavioral responsiveness: absent
* Overall interpretation: EEG evidence consistent with cognitive motor dissociation
* Uncertainty: quantified
* Recommended next step: repeat testing, alternative task, multimodal confirmation, or no conclusion

Do not collapse this profile into a binary "conscious/not conscious" output unless strong evidence ultimately
supports doing so.

## 19. Clinical development sequence

Structure the program in stages.

**Stage 1: Feasibility and falsification**

* Reproduce established effects
* Validate preprocessing
* Evaluate UCE as a frozen baseline
* Identify construct overlap and confounding
* Determine whether cross-domain transfer is plausible

**Stage 2: Retrospective model development**

* Develop the multidimensional framework
* Lock definitions and pipelines
* Use nested patient-level validation
* Establish calibration and abstention

**Stage 3: Dataset-level external validation**

* Hold out entire datasets and sites
* Test different etiologies and drugs
* Test reduced montages
* Conduct subgroup analyses

**Stage 4: Multimodal validation**

* Compare with behavioral examination
* Task EEG
* fMRI
* PET
* TMS-EEG
* Longitudinal outcome

**Stage 5: Silent prospective study**

Run the model prospectively without influencing care.

Assess:

* Feasibility
* Data failure
* Turnaround time
* Calibration drift
* Discordance with clinicians
* Added diagnostic yield

**Stage 6: Clinical impact study**

Test whether using the result changes:

* Diagnostic accuracy
* Prognostic calibration
* Communication attempts
* Rehabilitation selection
* Treatment decisions
* Family understanding
* Patient-centered outcomes

Do not jump directly from retrospective AUROC to clinical deployment.

## 20. Ethical constraints

This project involves exceptionally high-stakes inference.

A false negative could contribute to withdrawal of treatment from a conscious patient. A false positive could
create false hope, prolong nonbeneficial treatment, or distort surrogate decision-making.

Therefore:

* Never describe an experimental output as definitive proof of consciousness
* Quantify uncertainty
* Permit abstention
* Require independent confirmation for major decisions
* Preserve raw data and analysis provenance
* Document model version and failure modes
* Do not use race, insurance status, socioeconomic status, or hospital identity as shortcuts
* Assess subgroup performance
* Include neurocritical care, rehabilitation, EEG, ethics, patient-family, and biostatistical expertise in
  eventual clinical design

## 21. Statistical constraints

* Predefine primary hypotheses before final testing
* Lock preprocessing before external validation
* Use nested cross-validation for model selection
* Bootstrap or otherwise appropriately estimate uncertainty
* Account for repeated measurements within subjects
* Use hierarchical models when combining sites
* Report heterogeneity rather than merely pooled performance
* Correct or hierarchically control multiple comparisons
* Distinguish confirmatory from exploratory analysis
* Avoid selecting features on the full dataset
* Conduct sample-size and precision analyses
* Publish null and contradictory results

For small datasets, favor Bayesian partial pooling, regularization, and honest uncertainty over high-capacity
models.

## 22. Reproducibility requirements

Use a repository structure approximately like:

```
project/
  README.md
  CITATION.cff
  LICENSE
  pyproject.toml
  configs/
  data_registry/
  docs/
  notebooks/
  src/
    ingestion/
    preprocessing/
    quality_control/
    features/
    tasks/
    models/
    evaluation/
    visualization/
  tests/
  reports/
  results/
  references/
```

Requirements:

* Configuration-driven experiments
* Fixed random seeds where applicable
* Environment locking
* Unit tests
* Synthetic EEG tests
* Data provenance
* Subject-level split manifests
* Model cards
* Dataset cards
* Automated quality-control reports
* Machine-readable results
* No manual undocumented correction of results

Do not commit protected patient data.

## 23. Immediate assignment

Begin by producing the following artifacts in order:

**Artifact 1: RESEARCH_STRATEGY.md** — precise problem definition, construct definitions, testable
hypotheses, competing explanations, proposed staged study design, go/no-go criteria, major failure modes,
what evidence would falsify the central hypothesis.

**Artifact 2: LITERATURE_MAP.md** — a structured review and evidence table. Prioritize primary literature and
authoritative consensus or guideline documents. Clearly distinguish established evidence from theory and
speculation.

**Artifact 3: DATASET_REGISTRY.csv** — realistic candidate datasets with access, labels, size, modalities,
licensing, and suitability. Do not invent access or variables. Mark uncertain fields as requiring
verification.

**Artifact 4: ANALYSIS_PLAN.md** — outcomes, predictors, label hierarchy, splitting strategy, baselines,
model families, confounder analyses, negative controls, external validation, calibration, missing data,
statistical inference, stopping rules.

**Artifact 5: Code scaffold** — repository scaffold implementing configuration loading, EEG file interface,
synthetic-data generator, basic preprocessing, quality metrics, aperiodic-feature extraction, frozen UCE v1
calculation, basic spectral baselines, subject-level splitting, evaluation and calibration utilities, unit
tests. Do not pretend to have processed datasets that are not locally available.

**Artifact 6: NEXT_ACTIONS.md** — prioritized by scientific value, feasibility, data availability, cost,
time, dependency, and risk of invalidating the project.

## 24. Decision gates

* **Gate A: Technical validity** — can the pipeline reliably reproduce known EEG effects and survive
  preprocessing sensitivity tests?
* **Gate B: Construct validity** — does the model distinguish cognitive capacity from arousal, responsiveness,
  injury severity, drug exposure, and artifact?
* **Gate C: External validity** — does performance survive held-out datasets, sites, etiologies, and
  acquisition systems?
* **Gate D: Incremental utility** — does EEG add clinically meaningful information beyond structured
  behavioral examination and standard clinical variables?
* **Gate E: Prospective feasibility** — can the system produce reliable, interpretable results in real
  clinical recordings with a useful abstention policy?
* **Gate F: Clinical utility** — does access to the result improve decisions or outcomes without causing
  disproportionate harm?

Failure at a gate should trigger redesign, narrowing of the claim, or termination — not cosmetic reframing.

## 25. Freedom to revise the strategy

You may challenge any assumption in this document.

Specifically, you may conclude that:

* A universal one-dimensional EEG coordinate is not biologically plausible
* UCE is primarily an arousal marker
* Resting EEG cannot establish awareness
* Active paradigms should be the primary endpoint
* A hierarchical profile is better than one index
* Separate models are required for acute and chronic injury
* Cross-domain pretraining helps only representation learning, not final interpretation
* The best first paper should be methodological, negative, or benchmarking-focused
* Available public data are inadequate and a prospective acquisition protocol is required

Explain and document revisions rather than silently changing the objective.

## 26. Working style

Act autonomously but remain skeptical.

* Inspect before implementing
* Record assumptions
* Search for contradictory evidence
* Prefer robust conclusions over dramatic claims
* Avoid anthropomorphic or metaphysical language
* Do not confuse prediction with explanation
* Do not exaggerate preliminary findings
* Do not optimize a manuscript narrative at the expense of validity
* Surface blockers clearly
* Make reasonable decisions independently when details are unspecified

At the end of each major work cycle, report:

1. What was completed
2. What was learned
3. What failed
4. What assumptions changed
5. What the strongest next experiment is
6. Whether the overarching claim should be preserved, narrowed, or abandoned

## 27. Standard for success

A technically successful project is not necessarily a scientifically successful one.

The program succeeds only if it produces a result that is:

* Reproducible
* Externally validated
* Calibrated
* Resistant to obvious confounders
* Conceptually precise
* Clinically interpretable
* Honest about uncertainty
* More informative than standard examination and clinical variables
* Capable of changing an appropriate clinical action

Begin with the research strategy, literature map, and dataset feasibility assessment. Do not begin by training
a large neural network.

The most important design choice in this brief is making intentional command-following the strongest evidence
tier, while treating spontaneous EEG as evidence about the brain's capacity to support cognition — not as
direct proof of subjective experience. That distinction addresses one of the major definitional problems in
the covert-consciousness literature.

---

## Investigator's dataset feasibility assessment (supplied with the brief, verbatim summary)

The investigator searched OpenNeuro, PhysioNet, EBRAINS, Figshare, institutional repositories, VitalDB and
2025–2026 releases, and concluded:

> You can build a strong retrospective proof-of-concept entirely from public data, but public data alone still
> cannot fully validate a clinical covert-consciousness detector. The main bottleneck is not raw EEG volume.
> It is the scarcity of public datasets combining behavioral unresponsiveness, repeated CRS-R assessments,
> task EEG, contemporaneous medication data, and an independent consciousness reference such as fMRI, PET, or
> TMS-EEG.

**Tier 1 (essential):** Bath prolonged-DoC motor-imagery dataset (DOI 10.15125/BATH-01632, released
2026-06-17); Figshare 59-patient resting DoC EEG (DOI 10.6084/m9.figshare.23552964); EBRAINS TMS-EEG DoC
(12 patients); I-CARE (PhysioNet, 607 public patients, ~23.7 GB, 18 bipolar channels at 100 Hz); Chennu
propofol sedation (Cambridge, 20 adults, 91 channels, 4 conditions); OpenNeuro ds005620 (propofol repeated
awakenings / dreaming).

**Tier 2 (scale and robustness):** VitalDB (6,388 surgical cases); PhysioNet multitaper spectra under
GABAergic anaesthesia.

**Tier 3 (sleep):** Sleep-EDF Expanded; Sleep Heart Health Study; MESA Sleep; optionally MASS / ISRUC / CAP /
HMC / Dreem.

**Tier 4 (healthy active command-following):** PhysioNet EEG Motor Movement/Imagery Database; BNCI Horizon /
BCI Competition IV 2a and 2b; OpenNeuro ds007554 (2026 multimodal, 30 participants, 3 sessions, motor
imagery + arithmetic + n-back + fNIRS).

**Tier 5 (passive cognitive processing):** OpenNeuro/BNCI datasets with oddball, mismatch negativity,
local-global, N400, auditory attention, speech tracking — at least two independent datasets per construct.

**Stated public-data gaps:** no large public dataset combining raw task EEG + task fMRI + repeated CRS-R +
resting EEG + etiology + sedatives + longitudinal outcome + independent adjudication; no public acute-ICU
active-task command-following cohort; few DoC datasets with multiple active paradigms; incomplete drug
metadata in chronic DoC datasets; behavioral assessments often not contemporaneous with EEG.

**Recommended first paper:** a multimodal, cross-domain falsification study testing whether spontaneous EEG
measures of organized cortical dynamics predict independently detected intentional command-following,
perturbational complexity, and subjective experience — while remaining separable from arousal, injury
severity, medication state, and prognosis.
