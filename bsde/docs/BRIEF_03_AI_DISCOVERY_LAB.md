# BRIEF 03 — THE AI-DRIVEN EEG DISCOVERY LABORATORY (investigator, 2026-07-29)

> **THIS DOCUMENT IS SAVED VERBATIM AND IS IMMUTABLE.** It is the investigator's own words. It must never be
> revised to match later findings. Companion to `RESEARCH_PROGRAM_BRIEF.md` (Brief 01) and
> `BRIEF_02_DATASET_STRATEGY.md` (Brief 02). The synthesis that reconciles all three, and records where
> analysis has contradicted them, is `MASTER_PLAN.md`.
>
> This brief is the governing document for **how** the project works. Brief 02 governs **what data** it
> works on. Brief 01 governs **what question** it asks.

---

Your intuition is directionally right. Recent AI-assisted mathematics breakthroughs show that modern reasoning systems can do more than summarize literature or write code: they can search enormous spaces of possible constructions, combine ideas from distant fields, pursue approaches humans dismiss, and repeatedly revise against a hard verifier. In 2026, AI systems reportedly resolved several open Erdős problems through formal proof search, disproved a central unit-distance conjecture, and helped produce solutions to other longstanding problems. The crucial ingredient was not simply "ask a chatbot for an insight." It was massive parallel exploration plus rigorous automated verification.

EEG does not have a perfect equivalent of a Lean proof checker. Your opportunity is to build one.

## The core idea

Create an AI-driven EEG discovery laboratory that repeatedly performs this loop:

Propose a physiologic hypothesis → derive measurable predictions → implement it → test across multiple datasets → search for confounders → attempt to falsify it → revise or discard it.

Most EEG laboratories use AI near the end:

Select a known outcome → train a model → report AUROC.

You should use AI across the entire scientific process:

Literature reconstruction → hypothesis generation → mathematical representation → experiment design → implementation → falsification → mechanistic interpretation → prospective testing → closed-loop intervention.

That is the asymmetric advantage.

## What AI can do that traditional EEG labs usually cannot

### 1. Search a vastly larger hypothesis space

Human EEG researchers typically evaluate a few familiar features:

* Band power
* Coherence
* Entropy
* Aperiodic exponent
* Connectivity
* Microstates
* A chosen neural network

An AI research system can systematically generate and test thousands of structured hypotheses involving:

* Spatial gradients
* Nonlinear combinations
* Temporal derivatives
* State-transition geometry
* Cross-frequency interactions
* Scale-free behavior
* Network topology
* Phase-amplitude relationships
* Perturbational responses
* Drug-response functions
* Multiscale complexity
* Subject-relative normalization
* Cross-domain invariant features

The system should not merely optimize arbitrary mathematical expressions. It should attach each proposed representation to:

1. A physiological interpretation
2. A predicted direction of change
3. Conditions under which it should fail
4. Alternative explanations
5. Datasets capable of distinguishing those explanations

This turns feature engineering into automated scientific theory search.

---

### 2. Make symbolic discovery a central capability

Deep neural networks can predict well while giving you almost nothing patentable, interpretable, or scientifically memorable.

Use AI to search for compact mathematical structures:

S_t = f(x_t, x_{t-1}, Δx_t, drug, age, baseline)

where S_t may represent:

* State
* Stability
* Transition probability
* Perturbational responsiveness
* Individual sensitivity
* Cerebral resilience

Candidate tools include:

* Symbolic regression
* Sparse identification of nonlinear dynamics
* Equation discovery
* Genetic programming
* Bayesian program synthesis
* Differentiable equation search
* Neural-to-symbolic distillation
* Causal state-space discovery

The objective should penalize:

* Complexity
* Site dependence
* Device dependence
* Drug-specific shortcuts
* Instability across preprocessing
* Poor calibration
* Physiologically implausible behavior

Reward:

* Cross-dataset transfer
* Temporal consistency
* Mechanistic plausibility
* Prospective prediction
* Reduced-channel preservation
* Incremental value over standard metrics

A compact law-like representation that survives multiple perturbations could be much more valuable than another transformer with a small performance gain.

---

### 3. Build an automated adversarial scientist

This may be your biggest advantage.

For every apparent result, create AI agents whose sole job is to destroy it.

One agent proposes the biomarker. Independent agents ask:

* Is this EMG?
* Is it age?
* Is it sedation dose?
* Is it montage?
* Is it preprocessing?
* Is it reference choice?
* Is it hospital identity?
* Is it outcome leakage?
* Is it merely spectral slowing?
* Does it fail under ketamine?
* Does it fail during REM dreaming?
* Does it fail in locked-in syndrome?
* Does it fail after neuromuscular blockade?
* Does it survive leave-one-dataset-out testing?
* Can a trivial baseline reproduce it?

Then automatically run:

* Label permutations
* Channel permutations
* Phase randomization
* Temporal scrambling
* Artifact-only models
* Site probes
* Drug probes
* Demographic probes
* Negative-control outcomes
* Alternative preprocessing pipelines
* Leave-one-hospital-out analyses
* Leave-one-drug-out analyses
* Leave-one-etiology-out analyses

Most academic projects do a fraction of this because it is labor-intensive and threatens publication. AI can make aggressive falsification routine.

Your commercial advantage will come from being the group whose biomarkers survive hostile testing, not from producing the largest number of positive findings.

---

### 4. Treat public EEG datasets as one giant virtual laboratory

Most investigators work within one dataset and one clinical domain. You can create a standardized data layer spanning:

* Sleep
* Anesthesia
* Coma
* Delirium
* Seizures
* Cognitive tasks
* TMS-EEG
* Motor imagery
* Psychiatric disease
* Neurodegeneration
* Wearable EEG

The AI system can test every proposed feature across a matrix:

| Dimension | Tests |
|---|---|
| Physiology | sleep, wakefulness, dreaming |
| Pharmacology | propofol, volatile agents, dexmedetomidine, ketamine |
| Pathology | coma, epilepsy, neurodegeneration |
| Cognition | attention, memory, motor imagery |
| Acquisition | high-density, clinical 10–20, frontal, single-channel |
| Timescale | milliseconds, minutes, hours, days |
| Outcome | state, transition, behavior, recovery, treatment response |

A candidate measure that only works in one cell is an application-specific biomarker.

A candidate that preserves a predictable structure across the matrix may be a platform technology.

Current EEG foundation-model studies show why this remains unsolved: specialist models are still competitive, larger models do not reliably generalize better, and performance often deteriorates under clinical distribution shifts.

That means the field has not yet found the correct representation.

---

### 5. Search for invariants, not merely accuracy

The breakthrough question is not:

Which model classifies these recordings most accurately?

It is:

Which properties of EEG remain meaningfully related across different ways of changing brain state?

For example, ask AI to identify features whose trajectories are conserved across:

* Sleep onset
* Propofol induction
* Sevoflurane induction
* Emergence
* Recovery from coma
* Seizure onset
* Burst suppression
* Cognitive engagement

The absolute EEG signature will differ. The deeper invariant might involve:

* Dimensional collapse
* Loss of spatial differentiation
* Transition instability
* Reduced response propagation
* Altered timescale hierarchy
* Changes in attractor geometry
* Reduced controllability
* Hysteresis
* Critical slowing
* Loss of complexity at particular spatial or temporal scales

AI is especially valuable for identifying these higher-order correspondences because no individual researcher can simultaneously retain every result across anesthesia, sleep, epilepsy, coma, dynamical systems, and machine learning.

## Seven breakthrough programs worth attacking

### Program 1: The EEG periodic table of brain states

Build a representation that organizes all major EEG states into a common geometry.

Instead of forcing one scalar "depth," determine whether brain states occupy a low-dimensional manifold with axes such as:

* Activation
* Integration
* Stability
* Responsiveness
* Suppression
* Cognitive modulation
* Pathologic synchronization

Train AI to discover the smallest coordinate system that predicts transitions and perturbational responses across datasets.

Potential IP:

* Brain-state embedding
* Cross-device transformation
* State-transition engine
* Patient-relative positioning
* Clinical interpretation layer

Scientific payoff:

A new taxonomy of EEG states.

---

### Program 2: Cerebral resilience as a latent phenotype

Use anesthesia as a controlled physiologic stress test.

AI would search for patient-specific features of:

* Induction trajectory
* Dose-response sensitivity
* Suppression threshold
* Recovery dynamics
* Hysteresis
* Response to stimulation
* Postoperative cognitive outcomes

The breakthrough could be:

Two patients at the same anesthetic concentration and behavioral state may have fundamentally different cerebral reserve.

AI can model individual response curves rather than population-average thresholds.

Applications:

* Delirium prediction
* Personalized dosing
* Frailty
* Dementia risk
* ICU vulnerability
* Drug development
* Perioperative risk stratification

This may be your strongest near-term proprietary program.

---

### Program 3: A neural transition forecaster

Most EEG systems describe the present. Build one that forecasts the next clinically important transition.

Examples:

* Loss of responsiveness in 30 seconds
* Emergence in five minutes
* Burst suppression in two minutes
* Seizure in one hour
* Awakening during sleep
* Neurologic deterioration in the ICU
* Recovery of command-following over days

Use:

* Neural state-space models
* Survival models
* Neural differential equations
* Change-point detection
* Hazard models
* Conformal prediction
* Patient-specific online adaptation

Transition forecasting is more valuable than classification because it enables intervention.

Commercial value: very high.
IP value: likely stronger when connected to an action or control system.

---

### Program 4: AI-discovered stimulation protocols

Instead of merely reading EEG, use AI to discover how to change it.

Possible interventions:

* Auditory stimulation
* TMS
* tACS
* DBS
* Vagus nerve stimulation
* Temperature
* Anesthetic delivery
* Wake-promoting drugs
* Sleep interventions

The system would learn:

1. Current brain state
2. Response to prior perturbations
3. Expected effect of candidate interventions
4. Safest action under uncertainty
5. Whether the intervention moved the subject toward the target state

This is analogous to automated theorem search, except the verifier is experimental response.

Use:

* Bayesian optimization
* Safe reinforcement learning
* Model-predictive control
* Causal bandits
* Offline reinforcement learning
* Digital-twin simulation

A defensible brain-state controller may ultimately be more valuable than the measurement alone.

---

### Program 5: Automated mechanistic experiment generation

Give AI access to:

* Papers
* Dataset metadata
* Existing results
* Your hypothesis library
* Available signals
* Known pharmacology
* Model failures

Ask it to propose the experiment that best separates two competing explanations.

Example:

UCE predicts unconsciousness because it measures reduced cortical excitation.

Versus:

UCE predicts unresponsiveness because it tracks frontal spectral slowing caused by GABAergic drugs.

The AI might select:

* Ketamine as a dissociating drug
* REM dreaming as a behavioral-disconnection counterexample
* Locked-in syndrome as a motor-output counterexample
* Neuromuscular blockade as a responsiveness counterexample
* TMS-EEG as an independent perturbational measure

This is active scientific learning: choose the next dataset or experiment by expected information gain rather than convenience.

---

### Program 6: Automated biomarker composition

Individual EEG biomarkers often fail because they each capture only one component.

Let AI discover hierarchical combinations:

* Signal adequacy
* Spontaneous substrate
* Cortical reactivity
* Cognitive processing
* Intentional modulation
* Transition trajectory

The model should return a profile rather than a single opaque score.

Then search for combinations that are:

* Modular
* Interpretable
* Calibrated
* Device-compatible
* Useful under missing modalities
* Able to abstain

This could become a common EEG "operating layer" used by multiple products.

---

### Program 7: The EEG experimental compiler

Build software that translates a scientific question into a reproducible analysis.

Input:

Does aperiodic slope predict emergence independently of age and anesthetic concentration?

The system would:

1. Identify compatible datasets
2. Map required variables
3. Generate a preregistration-style analysis plan
4. Harmonize channels and units
5. Create patient-level splits
6. Implement baselines
7. Run sensitivity analyses
8. Test confounders
9. Generate plots and tables
10. Draft a methods and results report
11. Record all provenance
12. Refuse conclusions unsupported by the data

This can let a small group operate at the throughput of a large consortium.

The platform itself could also become a commercial or collaborative asset.

## The key lesson from AI mathematics

The transferable lesson is verification-guided search.

Mathematics has unusually strong verifiers:

* A proof compiles or it does not.
* A construction satisfies the required property or it does not.
* A bound is improved or it is not.

EEG has noisy labels, hidden confounding, and biological heterogeneity. Therefore, you must create a layered verifier.

## Your EEG verifier stack

A candidate discovery passes only if it clears:

### 1. Computational verification

* Correct implementation
* Unit tests
* Synthetic signal recovery
* Reproduction of known effects

### 2. Statistical verification

* Nested validation
* Confidence intervals
* Calibration
* Multiple-comparison control
* Subject-level independence

### 3. Adversarial verification

* Artifact tests
* Site tests
* Drug tests
* Leakage tests
* Preprocessing sensitivity

### 4. Cross-domain verification

* Held-out datasets
* Held-out devices
* Held-out drugs
* Held-out etiologies

### 5. Temporal verification

* Predicts future transitions
* Preserves direction within subjects
* Works prospectively

### 6. Mechanistic verification

* Responds appropriately to controlled perturbations
* Dissociates from motor output
* Dissociates from simple arousal
* Agrees with independent modalities where appropriate

### 7. Clinical verification

* Adds value over clinicians and existing monitors
* Changes a useful decision
* Improves an outcome or workflow

This verifier is your equivalent of formal proof checking.

## How to structure the AI system

Do not use one giant agent. Use a research organization of specialized agents.

**Research-director agent**

* Maintains the scientific thesis
* Selects priorities
* Prevents scope drift
* Decides go/no-go gates

**Literature agent**

* Builds claim–evidence graphs
* Finds contradictory studies
* Tracks datasets, methods, and replication status
* Identifies abandoned ideas worth revisiting

**Hypothesis agent**

* Generates mechanistic candidate hypotheses
* States predicted effects and failure conditions
* Ranks by expected value

**Mathematical-discovery agent**

* Searches equations and latent representations
* Enforces simplicity and invariance
* Distills black-box models into compact structures

**Data-curator agent**

* Harmonizes datasets
* Tracks licenses
* Detects duplicate subjects and recordings
* Maintains provenance

**Experimentalist agent**

* Selects decisive comparisons
* Calculates information gain
* Designs prospective perturbations

**Engineering agent**

* Implements pipelines
* Writes tests
* Profiles computational cost
* Maintains reproducibility

**Skeptic agent**

* Searches for leakage and confounding
* Runs negative controls
* Attempts to reproduce results with trivial baselines

**Statistician agent**

* Locks analysis plans
* Reviews repeated measures
* Enforces proper validation
* Prevents post hoc claim inflation

**IP agent**

* Identifies potentially novel claim families
* Separates publishable findings from trade secrets
* Produces invention disclosures
* Tracks public-disclosure dates

The final scientific decision remains yours and your collaborators'. Agents should never be allowed to approve their own findings.

## Your proprietary advantage

Do not aim to own an "AI model for EEG." That category is already becoming crowded. At least one startup has publicly described training an EEG foundation model on nearly one million hours of public and proprietary ICU data, and current benchmarks already compare many open EEG foundation models.

Your moat should instead be:

An autonomous discovery-and-validation system that identifies compact, physiologically grounded, cross-domain brain-state representations and converts them into prospective control products.

The proprietary layers would be:

* Harmonized multi-domain data architecture
* Hypothesis-generation framework
* Automated adversarial verifier
* Discovered representations
* Patient-specific adaptation
* Transition forecasting
* Prospective drug-response data
* Closed-loop policies
* Device-specific calibration
* Regulatory evidence

## What you should build first

### First 90-day objective

Build a Brain-State Discovery Engine v0.1.

It should take a candidate EEG feature or equation and automatically produce:

1. Performance across multiple datasets
2. Within-subject state-response plots
3. Leave-one-dataset-out results
4. Age, sex, drug, site, and signal-quality probes
5. Preprocessing sensitivity
6. Comparisons against trivial and established baselines
7. Temporal transition performance
8. Complexity and interpretability score
9. Reduced-channel performance
10. A standardized "survive/revise/reject" report

Start with:

* Frozen UCE v1
* Aperiodic exponent and offset
* Spectral power
* Spectral entropy
* Lempel–Ziv complexity
* Basic connectivity
* Existing processed anesthesia indices where available

Do not begin by asking AI to invent 100,000 features. First build the verifier.

### Then give the system three discovery challenges

**Challenge A**

Discover the simplest representation that predicts loss and recovery of responsiveness across multiple anesthetic drugs while minimizing drug-identification information.

**Challenge B**

Discover spontaneous EEG features associated with active command-following in disorders of consciousness, controlling for CRS-R diagnosis and global injury severity.

**Challenge C**

Discover a patient-specific trajectory feature that predicts burst suppression or delayed emergence before conventional monitors.

Each challenge has:

* A measurable endpoint
* Multiple datasets
* Strong negative controls
* Clear commercial relevance
* Potential mechanistic meaning
* A path to prospective testing

## Where your human advantage remains essential

AI can search, code, compare, and falsify at extraordinary scale. It still needs you for:

* Choosing questions that matter clinically
* Recognizing implausible labels
* Understanding anesthetic pharmacology
* Distinguishing consciousness from responsiveness
* Designing safe perturbations
* Accessing prospective patients
* Building clinical collaborations
* Deciding what is commercially actionable
* Establishing trust with physicians and regulators

Your ideal role is not manually producing every analysis.

It is:

Founder-scientist, clinical theorist, experiment designer, and final scientific judge of an AI-accelerated EEG laboratory.

## The biggest danger

The same machinery that can discover a breakthrough can generate thousands of false discoveries.

With enough datasets, preprocessing choices, outcomes, models, and feature combinations, AI can always find impressive-looking results.

Therefore:

* Keep immutable external test sets.
* Register primary hypotheses.
* Require replication across datasets.
* Separate exploration from confirmation.
* Track every attempted analysis.
* Report the size of the search space.
* Penalize complexity.
* Demand prospective prediction.
* Allow the system to return "nothing survived."
* Never let the AI rewrite the hypothesis after seeing the test result.

Without those constraints, AI does not create scientific genius. It creates industrialized p-hacking.

## My strongest recommendation

Your first breakthrough should not be "an EEG foundation model."

It should be one of these:

1. A compact cross-domain mathematical representation of brain-state dynamics
2. A cerebral-resilience phenotype revealed by anesthetic perturbation
3. A general neural transition forecaster
4. A safe closed-loop controller that improves a clinical state
5. An automated falsification framework that becomes the standard for EEG biomarkers

The first three create intellectual property. The fourth creates the highest-value product. The fifth establishes you as a field leader and gives every subsequent claim greater credibility.

The laboratories that merely become less hesitant about AI will eventually catch up on coding and model training. Your durable lead comes from building the closed scientific loop—discovery, verification, prospective perturbation, and control—before they reorganize how they conduct research.
