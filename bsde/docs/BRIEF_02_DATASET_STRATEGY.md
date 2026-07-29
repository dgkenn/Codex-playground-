# BRIEF 02 — DATASET STRATEGY (investigator, 2026-07-29)

> **THIS DOCUMENT IS SAVED VERBATIM AND IS IMMUTABLE.** It is the investigator's own words. It must never be
> revised to match later findings, and no claim in it may be softened, strengthened, or "corrected" here.
> Where analysis contradicts it, the contradiction is recorded in `MASTER_PLAN.md` and in the results ledger,
> never by editing this file. Companion to `RESEARCH_PROGRAM_BRIEF.md` (Brief 01) and
> `BRIEF_03_AI_DISCOVERY_LAB.md` (Brief 03).
>
> **Verification status of the factual claims below is tracked separately** in
> `../data_registry/DATASET_REGISTRY.csv` and `../data_registry/LICENSE_TABLE.csv`. Several dataset
> attributes stated here are the investigator's understanding and are marked REQUIRES VERIFICATION there.
> Discrepancies found by verification are recorded in those files and in `MASTER_PLAN.md` §Corrections — not
> here.

---

I searched broadly across OpenNeuro, PhysioNet, EBRAINS, Figshare, institutional repositories, VitalDB, and newer 2025–2026 releases. The result is encouraging but important:

You can build a strong retrospective proof-of-concept entirely from public data, but public data alone still cannot fully validate a clinical covert-consciousness detector.

The main bottleneck is not raw EEG volume. It is the scarcity of public datasets combining behavioral unresponsiveness, repeated CRS-R assessments, task EEG, contemporaneous medication data, and an independent consciousness reference such as fMRI, PET, or TMS-EEG.

However, a newly released 2026 dataset substantially improves feasibility.

## The datasets you actually need

### Tier 1: Essential datasets

These should form the core of the project.

#### 1. Bath prolonged disorders-of-consciousness motor-imagery dataset

Dataset: Motor-imagery brain-computer interface EEG and behavioural assessment datasets in prolonged disorders of consciousness
Repository: University of Bath Research Data Archive
DOI: 10.15125/BATH-01632
Released: June 17, 2026

This is now probably the single most important public dataset for your project.

It contains:

* Continuous task-based EEG
* Auditory motor-imagery commands
* Event triggers for cue onset and task periods
* Multiple sessions per participant
* Session-linked CRS-R scores
* Session-linked Wessex Head Injury Matrix scores
* UWS, MCS, and locked-in participants
* Two able-bodied benchmark participants
* Calibration, training, feedback, and question-and-answer runs
* Reproduction code for portions of the original analysis

The behavioral records are linked to EEG by participant and session, making it possible to test whether EEG detects intentional modulation beyond contemporaneous bedside behavior.

**Why you need it**

This is your primary dataset for:

* Intentional command-following
* Cognitive motor dissociation
* Within-person permutation testing
* Longitudinal repeatability
* Comparison against CRS-R
* Testing whether UCE or spontaneous features predict task detectability
* Separating motor output from motor imagery

**Limitations**

* Likely modest patient sample size
* Heterogeneous recording histories
* Repeated sessions create dependence
* Active-task performance can fail because of language, attention, hearing, working memory, fatigue, or paradigm difficulty
* A negative motor-imagery result does not establish absence of consciousness

**Role in the project**

Primary task-positive development dataset.

---

#### 2. Figshare prolonged disorders-of-consciousness resting EEG dataset

Dataset: The raw data of resting EEG of patients with prolonged disorders of consciousness
Repository: Figshare
DOI: 10.6084/m9.figshare.23552964

It contains:

* 59 patients with disorders of consciousness
* 32 healthy controls
* 62 EEG channels
* 250-Hz sampling
* Sixty 2-second epochs per subject
* Approximately 697 MB
* CC BY 4.0 license

The associated clinical study enrolled patients evaluated using resting EEG and behavioral diagnosis, although you must inspect the accompanying files carefully to confirm exactly which subject-level labels and CRS-R components are exposed.

**Why you need it**

This is the most immediately usable public dataset for:

* UWS-versus-MCS resting-state benchmarking
* Frozen UCE testing
* Aperiodic analyses
* Spectral and complexity baselines
* Connectivity analyses
* Patient-versus-control domain separation
* Reduced-montage simulation

**Limitations**

The public description guarantees diagnostic categories and EEG but does not clearly establish that complete item-level CRS-R, medication timing, etiology, or longitudinal outcome is available for every subject.

**Role**

Primary resting-state DoC development dataset.

---

#### 3. EBRAINS TMS-EEG disorders-of-consciousness dataset

Dataset: TMS-EEG perturbation in patients with disorders of consciousness v1
Repository: EBRAINS
Population: 12 DoC patients

The EBRAINS record describes TMS-EEG stimulation over frontal and parietal cortical regions in 12 patients with disorders of consciousness.

**Why you need it**

This is essential because spontaneous EEG and task EEG answer different questions.

TMS-EEG gives you a behavior-independent measure of:

* Cortical reactivity
* Effective propagation
* Complexity of the evoked response
* OFF periods
* Local-versus-distributed response patterns

You can test whether:

* UCE predicts perturbational complexity
* Spontaneous dynamics and TMS responses carry complementary information
* A proposed latent "capacity" axis agrees with perturbational evidence
* The resting EEG model detects anything beyond global injury severity

**Limitations**

* Only 12 patients
* TMS artifacts are severe
* Preprocessing choices can dominate results
* Small sample size permits validation of convergence, not model training
* You should not train a deep model on this dataset

**Role**

Mechanistic and convergent-validation dataset.

---

#### 4. I-CARE cardiac-arrest coma EEG

Dataset: International Cardiac Arrest REsearch Consortium Database
Repository: PhysioNet
Public cohort: 607 patients
Size: Approximately 23.7 GB

I-CARE contains multicenter continuous EEG-derived samples from comatose cardiac-arrest patients at seven hospitals in the United States and Europe. It provides up to five minutes of EEG per hour, extending to 72 hours after return of spontaneous circulation, along with demographics, arrest variables, temperature management, CPC outcome, and signal-quality scores.

EEG is represented by 18 bipolar channels downsampled to 100 Hz. The public cohort contains 607 patients; an additional challenge validation/test cohort was retained privately.

**Why you need it**

This gives you:

* A large, multicenter acute-coma cohort
* Longitudinal EEG trajectories
* Hospital-level domain shifts
* Severe brain-injury physiology
* Recovery-outcome associations
* Suppression and burst-suppression states
* A setting where behavioral command-following is absent at enrollment

It is critical for testing whether your model is merely detecting:

* Prognosis
* Suppression
* Sedation
* Injury severity
* Time after injury
* Site-specific recording characteristics

**Critical conceptual warning**

I-CARE does not provide direct evidence of contemporaneous awareness. CPC outcome is prognostic, not a consciousness label.

Do not train a "consciousness classifier" using good-versus-poor CPC. Use I-CARE to study:

* Longitudinal recovery physiology
* Prognostic validity
* Domain transfer
* Abstention
* Confounder resistance

**Role**

Primary acute-coma external-validation and trajectory dataset.

---

#### 5. Chennu propofol sedation EEG

Dataset: Data supporting Brain connectivity during propofol sedation
Repository: University of Cambridge Research Repository
Participants: 20 healthy adults

It contains approximately seven minutes of 91-channel EEG for each of four conditions:

* Baseline
* Mild propofol sedation
* Moderate sedation
* Recovery

The deposited data are preprocessed, filtered, artifact-cleaned, segmented, and average-referenced.

**Why you need it**

It provides a controlled reversible perturbation with:

* Same-subject state transitions
* High-density EEG
* Dose-related reduction in responsiveness
* Recovery
* Prior connectivity benchmarks

Use it to test whether a model trained in brain injury simply recognizes globally slow EEG, and whether DoC-derived representations transfer to pharmacologic unresponsiveness.

**Limitations**

* Preprocessed rather than raw
* Only propofol
* Responsiveness and consciousness remain partially conflated
* Small sample
* Healthy volunteers differ dramatically from patients with structural brain injury

**Role**

Controlled pharmacologic perturbation dataset.

---

#### 6. OpenNeuro repeated-awakening propofol/dreaming dataset

Dataset ID: ds005620
Dataset: A repeated awakening study exploring the capacity of propofol sedation and sleep EEG complexity to reflect subjective experiences

This dataset contains EEG collected during propofol sedation with repeated awakenings and reports relating to subjective experience or dreaming.

**Why it is unusually valuable**

This dataset helps break a major conceptual error:

Unresponsiveness is not necessarily absence of experience.

It allows you to investigate whether candidate EEG measures distinguish:

* Responsive wakefulness
* Unresponsive sedation with later reported experience
* Unresponsive sedation without reported experience
* Sleep-associated experience
* Different levels of complexity

This is more relevant to consciousness than simply classifying anesthetic concentration.

**Role**

Primary subjective-experience dissociation dataset.

---

### Tier 2: Essential scale and robustness datasets

These are not direct consciousness datasets, but they are needed to prevent overfitting and establish generalizability.

#### 7. VitalDB

Repository: VitalDB / AWS Open Data
Cases: 6,388 surgical patients

VitalDB contains high-resolution intraoperative waveforms and clinical variables from 6,388 surgical cases. Signals can include 500-Hz waveforms, numerical monitor outputs, anesthetic concentrations, infusion information, BIS-related channels in subsets, hemodynamics, and perioperative metadata.

**What it can do**

Use VitalDB for:

* Large-scale intraoperative external testing
* Propofol-versus-sevoflurane analyses
* Dose-response relationships
* Emergence and maintenance trajectories
* Burst suppression
* Comparison against BIS
* Drug and age confounding
* Reduced frontal montage testing
* Physiologic artifact robustness
* Testing real-world signal dropout

**What it cannot do**

VitalDB generally does not provide precise behavioral consciousness testing throughout surgery. Surgical timestamps or BIS values must not be treated as perfect awareness labels.

**Role**

Real-world anesthesia robustness and scale dataset.

---

#### 8. PhysioNet EEG power under anesthesia

Dataset: Multitaper spectra recorded during GABAergic anesthetic unconsciousness
Repository: PhysioNet

This resource includes processed spectral data linked to established propofol and sevoflurane anesthesia studies, including loss and recovery of consciousness and age-related anesthetic EEG analyses.

**Why use it**

* Reproduce canonical anesthetic spectral findings
* Validate baseline implementation
* Compare UCE-related spectral effects against published analyses
* Test age effects
* Benchmark expected frontal alpha and slow-wave behavior

**Limitation**

These are spectra, not necessarily full raw multichannel EEG.

**Role**

Reproduction and spectral sanity-check dataset.

---

### Tier 3: Sleep datasets

You should not download every available sleep cohort. Use three strategically different cohorts.

#### 9. Sleep-EDF Expanded

Use for:

* Easily reproducible baseline development
* Wake/N1/N2/N3/REM transitions
* Comparison with previous UCE results
* Rapid pipeline debugging
* Reduced-channel analysis

#### 10. Sleep Heart Health Study

Use for:

* Large-scale validation
* Age and medical comorbidity
* Respiratory disturbance
* Sleep fragmentation
* Real-world PSG heterogeneity
* Testing whether the model mainly tracks age or sleep pathology

Access generally requires registration and an approved data-use process, but it is publicly available to qualified researchers through the National Sleep Research Resource.

#### 11. MESA Sleep

Use for:

* Independent cohort validation
* Older and medically diverse participants
* Cardiometabolic confounding
* Racial and demographic heterogeneity
* Testing generalization beyond healthy laboratory subjects

**Optional sleep datasets**

Add one of:

* MASS
* ISRUC-Sleep
* CAP Sleep Database
* HMC Sleep Staging Database
* Dreem Open Datasets

**Why sleep matters**

Sleep contributes crucial counterexamples:

* NREM unresponsiveness
* REM dreaming with behavioral disconnection
* State transitions without structural brain injury
* Spontaneous rather than drug-induced state change

But sleep stages are not levels of consciousness. Use sleep as a perturbational domain, not as direct ground truth.

---

### Tier 4: Healthy active-command and cognitive-processing datasets

The Bath dataset is too small to develop all active-task methods from scratch. You need large healthy datasets to validate the signal-processing machinery.

#### 12. PhysioNet EEG Motor Movement/Imagery Database

This includes more than 100 healthy participants performing real and imagined movements.

Use it for:

* Motor-imagery decoder development
* Trial-level permutation methodology
* Minimum-trial analyses
* Cross-subject decoding
* False-positive calibration
* Reduced-electrode testing
* Testing CSP, Riemannian, spectral and deep-learning baselines

Do not use healthy motor imagery as proof that a method transfers to DoC.

#### 13. BNCI Horizon motor-imagery datasets

Recommended:

* BCI Competition IV Dataset 2a
* BCI Competition IV Dataset 2b
* Other BNCI motor-imagery datasets with multiple sessions

Use them for:

* Session-to-session transfer
* Subject adaptation
* Calibration burden
* Motor-imagery paradigm robustness
* Decoder benchmarking

#### 14. OpenNeuro ds007554

This 2026 multimodal dataset includes 30 healthy participants over three sessions performing:

* Motor imagery
* Passive movement
* Mental arithmetic
* N-back
* Motor tasks
* Combined cognitive-motor tasks

It includes EEG, fNIRS, ECG, behavioral and subjective measures.

**Why this is especially useful**

It permits development of a multitask intentional-modulation detector rather than overcommitting to motor imagery.

That matters because some conscious DoC patients may fail motor imagery but retain:

* Auditory attention
* Mental arithmetic
* Working-memory engagement
* Selective counting

**Role**

Healthy active-task development and negative-control dataset.

---

### Tier 5: Passive cognitive-processing datasets

A strong system should not depend entirely on active command-following.

You need public healthy datasets with:

* Auditory oddball
* Local-global paradigms
* Mismatch negativity
* P300
* Semantic violations or N400
* Natural speech tracking

Search OpenNeuro and BNCI for BIDS datasets containing:

* oddball
* mismatch
* local-global
* semantic
* N400
* auditory attention
* speech tracking

Use these to create and validate modules for:

1. Primary auditory response
2. Deviance detection
3. Global-rule violation
4. Semantic processing
5. Instruction-dependent attention

The exact dataset matters less than choosing at least two independent datasets per cognitive construct.

**Why this tier matters**

An active task has low sensitivity because it requires sustained comprehension and cooperation. Passive hierarchical processing can provide intermediate evidence when active command-following is absent.

---

## Recommended minimum viable dataset stack

To begin the project, download or request access to these first:

| Priority | Dataset | Core purpose |
|---|---|---|
| 1 | Bath PDoC MI-BCI | Direct task-based command-following |
| 2 | Figshare 59-patient DoC EEG | Resting-state UWS/MCS modeling |
| 3 | I-CARE | Acute coma trajectories and multicenter validation |
| 4 | EBRAINS DoC TMS-EEG | Perturbational validation |
| 5 | OpenNeuro ds005620 | Experience despite unresponsiveness |
| 6 | Chennu propofol | Controlled sedation and recovery |
| 7 | VitalDB | Real-world anesthesia scale |
| 8 | EEGMMIDB | Healthy motor-imagery method development |
| 9 | OpenNeuro ds007554 | Multitask intentional modulation |
| 10 | Sleep-EDF | Pipeline and state-transition baseline |
| 11 | SHHS | Large-scale sleep validation |
| 12 | MESA Sleep | Independent demographic/medical validation |

## What each dataset contributes to the central claim

### Claim component 1: "The EEG preserves evidence of intentional command-following"

Use:

* Bath PDoC MI-BCI
* EEGMMIDB
* BNCI motor imagery
* OpenNeuro ds007554

The decisive clinical evidence comes from Bath. The healthy datasets only develop and calibrate the methods.

### Claim component 2: "A resting-state substrate predicts the capacity to perform the task"

Use:

* Bath resting or pre-cue intervals
* Figshare DoC resting EEG
* EBRAINS TMS-EEG baseline periods
* Chennu propofol
* Sleep datasets

Test whether UCE, complexity, connectivity, and related features predict task positivity without defining task positivity circularly.

### Claim component 3: "The representation is not merely arousal"

Use:

* REM dreaming
* Propofol dream reports in ds005620
* Mild versus moderate Chennu sedation
* MCS versus UWS
* Locked-in participants
* Healthy eyes-open/eyes-closed data

Locked-in syndrome is especially important because motor behavior can be severely restricted while awareness is preserved.

### Claim component 4: "It is not merely prognosis or injury severity"

Use:

* I-CARE
* Figshare DoC EEG
* Bath repeated CRS-R sessions

Model separately:

* Current behavioral diagnosis
* Task positivity
* Subsequent recovery
* Mortality
* Injury etiology
* EEG suppression

### Claim component 5: "It survives drug and etiologic shifts"

Use:

* Propofol
* Volatile anesthesia via VitalDB
* Natural sleep
* Cardiac-arrest coma
* Chronic traumatic and nontraumatic DoC
* Locked-in syndrome

## Datasets that are valuable but not sufficient

Several famous consciousness studies appear to have data available only by investigator request, restricted collaboration, or not at all. That includes much of the multicenter data behind large cognitive motor dissociation studies and several major PCI studies.

The 2024 multicenter CMD cohort included 241 behaviorally unresponsive participants and detected CMD in 25%, but I did not find a public repository exposing the full raw EEG/fMRI cohort for unrestricted analysis.

You should cite that study and use it to design validation, but do not list it as available data unless the investigators subsequently release it.

Likewise, the large 2025 three-site study of 237 acute and chronic DoC patients is highly relevant scientifically, but I did not identify a public raw-data download attached to the paper.

## The biggest public-data gaps

### 1. Multimodal CMD ground truth

There is no large, clearly public dataset containing all of:

* Raw task EEG
* Task fMRI
* Repeated CRS-R
* Resting EEG
* Etiology
* Sedatives
* Longitudinal outcomes
* Independent adjudication

The Bath dataset is the closest direct public resource I found, but it does not replace a large multicenter CMD cohort.

### 2. Acute brain injury with active tasks

I-CARE is large but mainly prognostic and resting/continuous EEG. Bath is active-task based but focused on prolonged DoC.

A definitive model will eventually need acute ICU command-following EEG.

### 3. Multiple active paradigms in DoC patients

Motor imagery alone is inadequate. You eventually need patient data with several tasks:

* Motor imagery
* Auditory selective attention
* Mental arithmetic
* Spatial navigation
* Word counting
* Attempted communication

### 4. Drug metadata in DoC datasets

Sedatives, antiepileptic medications, baclofen, stimulants, and sleep-wake timing can substantially alter EEG. Public chronic DoC datasets often incompletely expose these variables.

### 5. Truly contemporaneous behavioral assessment

A CRS-R collected days from the EEG is much weaker than a CRS-R performed immediately before and after recording.

## Best research sequence using only public data

### Paper 1: Public benchmark and falsification study

Question:

Do spontaneous EEG markers that classify behavioral DoC diagnosis also predict independently detected intentional command-following?

Datasets:

* Bath
* Figshare DoC
* Chennu propofol
* ds005620
* EBRAINS TMS-EEG

Primary endpoints:

* Task-positive MI detection
* CRS-R diagnosis
* Perturbational response
* Reported experience after unresponsiveness

Compare:

* UCE v1
* Aperiodic exponent and offset
* Delta/alpha power
* Spectral entropy
* Lempel–Ziv complexity
* wSMI/connectivity
* Microstates
* Modern pretrained representations

This should be framed as a construct-validity benchmark, not as clinical deployment.

### Paper 2: Cross-domain latent-state model

Add:

* I-CARE
* VitalDB
* Sleep-EDF
* SHHS
* MESA
* Healthy task datasets

Ask whether separable latent dimensions emerge for:

* Arousal
* Suppression/injury
* Organized spontaneous dynamics
* Sensory processing
* Intentional modulation
* Prognosis

The desired result is not necessarily one universal axis. A two- or three-dimensional model may be more scientifically credible.

### Paper 3: Prospective acquisition

Public data will probably take you through Papers 1 and 2. It will not complete clinical validation.

A later prospective protocol should collect:

* Repeated CRS-R immediately around EEG
* Resting EEG
* Auditory local-global task
* Motor imagery
* Auditory counting task
* TMS-EEG where feasible
* Medication levels and timing
* Hearing and visual integrity
* Structural imaging
* Longitudinal recovery
* Independent blinded adjudication

## My bottom-line recommendation

Start with these six immediately:

1. Bath PDoC motor-imagery/CRS-R dataset
2. Figshare 59-patient resting DoC dataset
3. I-CARE
4. EBRAINS DoC TMS-EEG
5. OpenNeuro ds005620 propofol/dreaming
6. Cambridge Chennu propofol dataset

Then add:

7. VitalDB
8. EEGMMIDB
9. OpenNeuro ds007554
10. Sleep-EDF
11. SHHS
12. MESA Sleep

The Bath release changes the project materially. Before June 2026, the publicly available active-task DoC evidence base was too sparse to make a serious CMD-focused project independently. The Bath dataset now gives you a credible starting point, especially because the event-coded EEG is linked at the session level to CRS-R and WHIM assessments.

The strongest defensible public-data project is therefore:

A multimodal, cross-domain falsification study testing whether spontaneous EEG measures of organized cortical dynamics predict independently detected intentional command-following, perturbational complexity, and subjective experience—while remaining separable from arousal, injury severity, medication state, and prognosis.
