# LITERATURE_MAP.md — Artifact 2

*Every PMID below was verified against the live NCBI E-utilities record (esearch → esummary/efetch) on
2026-07-29. Titles, journals, years and first authors are taken from the MEDLINE record, not from memory and
not from a web page. Anything I could not verify is marked **UNVERIFIED** and must not be cited until it is.*

*Verification method matters here: in the investigator's sibling project, six fabricated citations were once
produced by fetching PubMed through a web-scraping route that silently returned CAPTCHA pages. E-utilities is
used instead, always.*

---

## 0. THE SINGLE MOST IMPORTANT PAPER FOR THIS PROJECT — read before anything else

**Colombo MA et al. "The spectral exponent of the resting EEG indexes the presence of consciousness during
unresponsiveness induced by propofol, xenon, and ketamine." *NeuroImage* (PMID **30639334**).**

Abstract retrieved and read in full. What it reports:

* Resting-EEG **spectral exponent β**, estimated **after removing oscillatory peaks**, over **1–40 Hz** broad
  band plus 1–20 and 20–40 Hz sub-bands.
* Three groups of healthy participants, **n = 5 each**, before and during anaesthesia with xenon, propofol or
  ketamine, each dosed to unresponsiveness (Ramsay 6). Delayed subjective reports classified states as
  *conscious report* vs *no report*.
* **Xenon and propofol:** loss of consciousness produced a substantially steeper PSD decay in every subject.
* **Ketamine:** PSD decay similar to wakefulness — consistent with preserved consciousness — with a specific
  flattening at 20–40 Hz.
* The spectral exponent was **highly correlated with PCI**, the perturbational complexity index.
* Conclusion: a steeper resting PSD "reliably indexed unconsciousness in anaesthesia, **beyond sheer
  unresponsiveness**".

### Why this must change how the project is framed

1. **The core UCE feature is established prior art, not a new construct.** The aperiodic/spectral exponent has
   already been published as a marker of the *presence of consciousness*, not merely arousal — and it already
   passed the hardest dissociation test in the brief (§H6): **ketamine**.
2. **It also already passed convergent validation against PCI**, which is the perturbational evidence the
   brief wants from the EBRAINS TMS-EEG dataset.
3. **But n = 5 per group.** The result is striking and severely underpowered. **Large-scale external
   validation across etiologies, sites and montages is therefore a genuine and substantial contribution — and
   it is precisely what this project is positioned to do.**
4. **The novelty of UCE cannot rest on the feature.** Combined with `RESEARCH_STRATEGY.md` §0 — which shows
   the frontal/posterior weighting is algebraically vacuous — the honest position is that **UCE v1's
   contribution is validation at scale, not discovery.** That should be stated in any manuscript.
5. **Sign convention must be reconciled explicitly.** Colombo reports β as a negative decay rate ("steeper" =
   more negative). This project's `fit_aperiodic` returns a **positive** exponent for a falling spectrum. In
   this project's convention, **unconsciousness = HIGHER exponent**. Any UCE result whose sign disagrees with
   that is a bug until proven otherwise.

---

## 1. Cognitive motor dissociation and covert consciousness

| PMID | citation (verified) | why it matters |
|---|---|---|
| **39141852** | Bodien YG et al. "Cognitive Motor Dissociation in Disorders of Consciousness." *N Engl J Med* 2024 Aug 15; 391:598–608 (39 authors) | The landmark multicentre CMD cohort the brief refers to. Defines the clinical target. Raw data **not** located in a public repository — see DATASET_REGISTRY. |
| **31242361** | Claassen J et al. "Detection of Brain Activation in Unresponsive Patients with Acute Brain Injury." *N Engl J Med* 2019 Jun 27 | Acute-ICU covert command-following via EEG. The acute counterpart to the chronic-DoC literature. |
| **22078855** | Cruse D et al. "Bedside detection of awareness in the vegetative state: a cohort study." *Lancet* 2011 Dec 17 | The original EEG motor-imagery DoC study — and the subject of a published reanalysis dispute (see below), which is exactly the false-positive problem the analysis plan §7 is built around. |
| **23351803** | Cruse D et al. "Reanalysis of 'Bedside detection of awareness in the vegetative state: a cohort study' — Authors' reply." *Lancet* 2013 Jan 26 | **Read this alongside the original.** A methods dispute over an active-paradigm detection claim is the single best cautionary case for this project. |
| **16959998** | Owen AM et al. "Detecting awareness in the vegetative state." *Science* 2006 Sep 8 | The founding demonstration (fMRI). |
| **39473967** | Bodien YG et al. "Clinical Implementation of fMRI and EEG to Detect Cognitive Motor Dissociation: Lessons Learned in an Acute Care Setting." *Neurol Clin Pract* 2025 Feb | Implementation failure modes — directly relevant to Gate E. |
| **41341544** | Schnakers C et al. "Consensus on covert awareness: a Delphi study." *Brain Commun* 2025 | Current consensus position; use for terminology discipline. |

## 2. Diagnostic standards and misdiagnosis

| PMID | citation (verified) | why it matters |
|---|---|---|
| **19622138** | Schnakers C et al. "Diagnostic accuracy of the vegetative and minimally conscious state: clinical consensus versus standardized neurobehavioral assessment." *BMC Neurol* 2009 Jul 21 | The empirical basis for treating behavioural diagnosis as an imperfect reference standard (brief §9). |
| **30098791** | Giacino JT et al. "Practice Guideline Update Recommendations Summary: Disorders of Consciousness." *Arch Phys Med Rehabil* 2018 Sep | Guideline anchor. |
| **30098792** | Giacino JT et al. "Comprehensive Systematic Review Update Summary: Disorders of Consciousness." *Arch Phys Med Rehabil* 2018 Sep | Companion systematic review. |
| **26865516** | Westhall E et al. "Standardized EEG interpretation accurately predicts prognosis after cardiac arrest." *Neurology* 2016 Apr 19 | The highly-malignant/malignant/benign tiering used in cardiac-arrest prognostication. **Note:** a same-titled record (PMID 27765824, *Neurology* 2016 Oct 11, first author Sethi NK) is a correspondence item, not the primary study — cite 26865516. |

## 3. Perturbational complexity (behaviour-independent reference)

| PMID | citation (verified) | why it matters |
|---|---|---|
| **23946194** | Casali AG et al. "A theoretically based index of consciousness independent of sensory processing and behavior." *Sci Transl Med* 2013 Aug 14 | PCI, the closest thing to a behaviour-independent reference standard. |
| **38440949** | Casarotto S et al. "Dissociations between spontaneous electroencephalographic features and the perturbational complexity index..." *Eur J Neurosci* 2024 Mar | **Critical for this project:** documents where spontaneous EEG features and PCI *dissociate*. Directly tests whether a resting marker such as UCE can stand in for perturbational evidence. |
| **28239544** | Bodart O et al. "Measures of metabolism and complexity in the brain of patients with disorders of consciousness." *NeuroImage Clin* 2017 | Metabolism–complexity convergence (FDG-PET). |
| **29118218** | Storm JF et al. "Consciousness Regained: Disentangling Mechanisms, Brain Systems, and Behavioral Responses." *J Neurosci* 2017 Nov 8 | Conceptual framing of the arousal/awareness/responsiveness separation the brief §2 demands. |
| **42090748** | Fecchio M et al. "Covert brain complexity in the intensive care unit." *Cortex* 2026 Aug | Recent ICU complexity work. |

## 4. Spontaneous-EEG markers and information sharing

| PMID | citation (verified) | why it matters |
|---|---|---|
| **24076243** | King JR et al. "Information sharing in the brain indexes consciousness in noncommunicative patients." *Curr Biology* 2013 Oct 7 | wSMI — a mandatory connectivity baseline (analysis plan §5). |
| **24709604** | Dehaene S et al. "Toward a computational theory of conscious processing." *Curr Opin Neurobiol* 2014 Apr | Theoretical frame for the hierarchical Layer C/D distinction. |
| **26752078** | Sarasso S et al. "Consciousness and Complexity during Unresponsiveness Induced by Propofol, Xenon, and Ketamine." *Curr Biol* 2015 Dec 7 | The complexity companion to Colombo; same three-drug dissociation design. |
| **39011546** | Pérez P et al. "Content-state dimensions characterize different types of neuronal markers of consciousness." *Neurosci Conscious* 2024 | Argues markers occupy different dimensions — direct support for the brief's multidimensional hypothesis (H2). |

## 5. Aperiodic physiology (the feature UCE is built from)

| PMID | citation (verified) | why it matters |
|---|---|---|
| **28676297** | Gao R et al. "Inferring synaptic excitation/inhibition balance from field potentials." *NeuroImage* 2017 Sep | The E/I interpretation of the aperiodic exponent — the mechanistic story UCE would need. |
| **30639334** | Colombo MA et al. (see §0) | The direct precedent. |
| — | Donoghue T et al., "Parameterizing neural power spectra into periodic and aperiodic components" (specparam/FOOOF) | **UNVERIFIED** — the E-utilities query rate-limited and then mis-resolved. Must be verified before citing. |

## 6. Ethics of communicating covert-consciousness results

| PMID | citation (verified) | why it matters |
|---|---|---|
| **39443437** | Heinonen GA et al. "A Survey of Surrogates and Health Care Professionals Indicates Support of Cognitive Motor Dissociation-Assisted Prognostication." *Neurocrit Care* 2025 Jun; 42:786–793 | Stakeholder attitudes — relevant to brief §20. |
| **41540310** | Bhardwaj T et al. "From fMRI to Family Meeting: Clinician and Family Perspectives on Neurotechnology-Informed Shared Decision-Making." *Neurocrit Care* 2026 Aug | How results are actually communicated. |

---

## 7. Gaps in this map — stated rather than hidden

* **specparam/FOOOF primary citation is UNVERIFIED** (rate limit). Verify before use.
* **Bekinschtein local-global primary paper not yet resolved** — my query returned unrelated records. The
  local-global paradigm is central to Layer D and its primary citation must be established.
* **No verified citation yet for EMG contamination of the aperiodic exponent** — the E-utilities search
  returned no match for my query terms. This is a *known* methodological concern that I have asserted in
  `RESEARCH_STRATEGY.md` §4; **until a citation is verified it is my assertion, not established literature**,
  and the synthetic test `test_emg_flattens_the_spectrum_downward` is currently the project's only evidence
  for it. That test demonstrates the direction in simulation, which is not the same as a published empirical
  finding in EEG.
* No systematic search yet for: TMS-EEG methodology, microstates, criticality/metastability, commercial
  indices (BIS/PSI), negative/failed-replication studies. These are required by brief §11 and are scheduled.

---

## 8. What the literature already implies for the project's hypotheses

| hypothesis | prior-art status |
|---|---|
| **H4 (UCE is an arousal marker)** | **Colombo argues against the strong form**: the exponent tracked *reported experience*, not responsiveness — ketamine was unresponsive but conscious and the exponent stayed wake-like. This is the best existing evidence that the feature is more than arousal. It rests on n = 5 per group. |
| **H5 (UCE adds nothing over a single whole-head exponent)** | Colombo used a **single broadband exponent**, not a frontal/posterior combination — consistent with strategy §0 that the two-region structure is unnecessary. |
| **H1 (resting predicts command-following)** | Casarotto 2024 (38440949) documents dissociations between spontaneous features and PCI, which is a warning that resting features may *not* track behaviour-independent evidence. |
| **H2 (multidimensionality)** | Pérez 2024 (39011546) supports it directly. |


---

# ROUND 2 — 2026-07-30. Three parallel reviews, one per challenge.

*Dispatched as three sonnet subagents with one binding method constraint: **no WebFetch for any bibliographic
record or dataset manifest**, only `curl` against NCBI E-utilities with the relied-upon sentence quoted.
**Every PMID below was then re-verified by the orchestrator against the live esummary record** — 47 records,
checked on first author, year, journal and title. Zero mismatches. Delegate the work, never the acceptance.*

*The review's most valuable output was a correction to this project's own writing: see "What the review
overturned" at the end.*

## Challenge A — a representation predicting responsiveness across drugs, minimising drug identity

**The prior art that matters most, and it is 24 years old.**

* **PMID 11517126** — Gugino LD et al., 2001, *Br J Anaesth*. Propofol **and** sevoflurane, volunteers,
  graded steps. Its stated goal: *"to identify those changes that were sensitive to alterations in the state
  of consciousness but independent of anaesthetic protocol."* **That is Challenge A, published in 2001.**
  Findings: *"Light sedation was accompanied by decreased posterior alpha and increased frontal/central beta
  power... With loss of consciousness, delta and theta power increased further in anterior regions and also
  spread to posterior regions."*
* **PMID 23946194** — Casali AG et al., 2013, *Sci Transl Med*. PCI, tested across **midazolam, xenon,
  propofol** plus sleep/wake/DoC — the strongest published claim of a drug-invariant marker. Note it targets
  *consciousness*, not behavioural responsiveness.
* **PMID 25233374** — Akeju O et al., 2014, *Anesthesiology*: sevoflurane and propofol share coherent frontal
  alpha and slow oscillations, but sevoflurane *"also exhibited a distinct theta coherence signature"* —
  **partial invariance only**.
* **PMID 37467269** — Adam E et al., 2023, *PNAS*. A modulation index tracking state transitions continuously
  under **both propofol and sevoflurane**. Closest published thing to "the answer", but targets the
  burst-suppression transition, deeper than the responsiveness threshold Challenge A cares about.

**Documented failures of drug invariance — the adversarial cases any candidate must survive.**

| PMID | drug | what breaks |
|---|---|---|
| 27178861 | ketamine | a *"gamma burst"* pattern with **decreased** alpha/beta — the opposite direction from GABAergic agents |
| 26118489 | nitrous oxide | sevoflurane alpha *"dissipated within 3-12 min"*, replaced by coherent slow-delta |
| 25187999 | dexmedetomidine | spindles peaking ~13 Hz vs propofol's ~11 Hz frontal alpha; *"different brain states"* |
| 29920532 | dexmedetomidine | at **matched sedation depth**, propofol and dexmedetomidine move alpha/beta/gamma in **opposite directions** |
| 26752078 | ketamine | Sarasso 2015: unresponsive but *"long, vivid dreams"* — responsiveness and consciousness are decoupled |

**The direct consequence for this project:** a candidate built on alpha or beta band power is *structurally*
a drug detector (PMID 29920532), and ketamine is the adversarial case that must be run, not avoided.

## Challenge B — resting EEG predicting command-following in DoC

**The canonical CMD literature is all TASK EEG, not resting.**

* **PMID 16959998** Owen 2006 *Science* (fMRI, single case) · **PMID 22078855** Cruse 2011 *Lancet*: *"Three
  (19%) of 16 patients could repeatedly and reliably generate appropriate EEG responses to two distinct
  commands"* · **PMID 31242361** Claassen 2019 *NEJM*: *"16 of 104 unresponsive patients (15%) had brain
  activation detected by EEG"* · **PMID 35841909** Egbebike 2022 *Lancet Neurol*: n=193, CMD in 14%.
* **PMID 39141852** Bodien YG et al., 2024, *NEJM* — the current consensus review.

**THE LOAD-BEARING NEGATIVE FINDING.** There is **no published study predicting command-following
specifically from purely resting, task-free EEG.** The literature predicts *diagnosis* (UWS vs MCS) or
*outcome*, not command-following. Nearest exceptions:

* **PMID 38761713** — Secci S et al., 2024, *Clin Neurophysiol*. 57 MCS patients, 30 min resting closed-eyes
  EEG, α-band connectivity, **79 % cross-validated accuracy** for MCS+/MCS−. **This is the number to beat.**
* **PMID 25329398** — Chennu S et al., 2014, *PLoS Comput Biol*. Descriptive: vegetative patients with covert
  awareness *"had alpha networks that were remarkably well preserved."* Small subgroup, not a designed test.

**A correction this project owes its own E28.** **PMID 21674197** — Bruno MA et al., 2011, *J Neurol*:
*"MCS+ describes high-level behavioural responses (i.e., command following, intelligible verbalizations or
non-functional communication)."* **MCS+ is therefore NOT a pure command-following label** — it also fires on
verbalization and communication. Any MCS+/− label is a noisy proxy; where CRS-R subscale items exist, the
command-following item must be extracted directly.

**Scope note that a reviewer would catch:** PCI (PMID 23946194, 27717082) is computed from **TMS-evoked**
potentials, not spontaneous EEG. It is routinely listed alongside "resting" measures and is not one.

**On the healthy-BCI substitution E28 rests on.** The effect is real and independently replicated —
**PMID 20303409** Blankertz 2010 (*r* = 0.53, n = 80), **PMID 36359646** Wang 2022 (n = 105),
**PMID 24979726** Bamdadian 2014 (n = 17). **But no published work bridges the two literatures.** The
substitution is a defensible analogy that has never been validated in a brain-injured population, and E28
must present it as an assumption under test.

## Challenge C — a trajectory feature ahead of a conventional monitor

**The incumbent's measured weaknesses — better numbers than the folklore.**

* **PMID 16508396** — Pilge S et al., 2006, *Anesthesiology*: *"Time delays between 14 and 155 s were found
  for all indices"* (BIS, Narcotrend, Cerebral State Index), and the delays are **direction-dependent**.
  **Cite this, not a generic "20-30 s".**
* **PMID 32040794** — Zanner R et al., 2021: qCON delays of 21 ± 5 s and 26 ± 5 s around the transition,
  *"similar to other monitoring systems such as bispectral index"*; AUC 0.61-0.90 for detecting LOR/ROR.
* **EMG contamination, which independently confirms what this project measured.** **PMID 37756246**
  Lichtenfeld 2024: *"The indices of all neuromonitoring systems significantly increased when the EEG was
  superimposed with the contraction EMG."* **PMID 22315331** Dahaba 2012: reversing neuromuscular blockade
  alone raised BIS from ~50 to ~62-64 **with no change in hypnotic depth**.
* Ketamine (**PMID 15591328**, BIS rose 33→46 *while anaesthesia deepened*) and N₂O (**PMID 29867405**).

**Burst-suppression onset prediction: no published comparator was found.** The literature covers *tracking*
existing suppression (**PMID 24018288**, Chemali's BSP state-space estimator) and closed-loop *control*
(**PMID 23770601** Ching 2013; **PMID 24204231** Shanechi 2013), both rodent for the control work. Nearest
forecasting analogue is **PMID 39470955** (Tu 2025), which forecasts BIS itself with deep sequence models.
**E26's null therefore has no published bar to beat and appears to fill a genuine gap** — which is a weaker
claim than it sounds, and must be checked against Tu 2025's full text before any novelty is asserted.

**The negative precedent that should temper any early-warning-signal work.** **PMID 31575122** — Wilkat T
et al., 2019, *Chaos*: *"we found no evidence for critical slowing down prior to 105 epileptic seizures"*
(28 subjects, surrogate-based evaluation). Critical slowing down failed rigorously in the closest analogous
brain-transition setting. No equivalent test exists for anaesthetic transitions.

**Delirium/suppression thresholds — a caveat this project must respect.** **PMID 26418126** (Fritz 2016) and
**PMID 25928189** (Soehle 2015) both link suppression to postoperative delirium, but **neither abstract
states a numeric SR % cutoff** — they use cumulative duration or continuous BSR. E26's "SR ≥ 10" was
presented as a literature convention; **that attribution is not verified** and must be softened or
full-texted. And **PMID 30721296** (Wildes 2019, ENGAGES): EEG-guided titration to avoid suppression **did
not reduce delirium** — a caveat any clinical framing has to carry.

---

## What the review overturned in this project's own writing

**E31 and E32 cited Gugino 2001 as fixing the direction of their prediction. It does not.** The abstract
reports beta *rising* in light sedation and delta/theta *rising further* at loss of consciousness; **it never
reports beta falling.** "The fast end is overtaken" was an inference about relative power presented as the
source's content (error-catalogue rule 42, added because of this).

A dedicated search found **no primary source documenting the sedation-to-surgical sign reversal E30
observed.** The nearest published phenomena are different in kind: **saturation-then-plateau** (**PMID
24154602** Ní Mhuircheartaigh 2013: SWA *"rose to saturation and then remained constant despite increasing
drug concentrations"*; **PMID 28665814** Warnaby 2017) and **transient paradoxical excitation** at LOC
(**PMID 38412114** Ostertag 2025, where spectral edge and spectral entropy move the *wrong* way while
permutation entropy tracks correctly through the same transition).

**E30's reversal is therefore either a deposit artefact or original to this project — and original raises
the burden of proof rather than lowering it.**

## Datasets located, with access route

| dataset | source | n | why it matters | access |
|---|---|---|---|---|
| **DOSE-I** | Zenodo 18483292 | 171 recordings, 281 procedures | **1,129 annotated LOC/ROC transitions**, 125 Hz EEG, MOAA/S depth labels. The induction-and-emergence deposit Challenge C has lacked. No branded index — a monitor proxy must be computed and declared. | **Open, CC-BY-4.0** |
| ketamine sub-anaesthetic | Dryad `10.5061/dryad.j9kd51c9q` | 10 | Free adversarial control for Challenge A's drug-identity probe. Sub-anaesthetic, no LOC. | **Open, CC0** |
| `eeg-gaba-anesthesia` | PhysioNet `10.13026/dx44-kw30` | 4 | Only deposit found with continuous graded dose for **two** drugs (propofol + sevoflurane). Tiny n. | credentialed |
| `eeg-power-anesthesia` | PhysioNet `10.13026/m792-h077` | 10 volunteers + 44 OR | Propofol and sevoflurane, behavioural LOC/ROC in the volunteer arm | credentialed |
| propofol spectrograms | Figshare 24777990 | 14 | LOC-aligned, no DUA | **Open, CC BY 4.0** |

**Flagged UNVERIFIED and not to be cited until checked:** opioid co-administration status for the OR cases in
both PhysioNet deposits (not in metadata); exact SR % thresholds in Fritz/Soehle (not in abstracts);
Rampil 1998 (PMID 9778016) has no abstract in PubMed, so its biphasic-curve content is unquotable from the
record; "Curley WT" could not be located in PubMed at all.

---

## Prior art on E35/E36's measure-family split — found AFTER both experiments ran, and it changes their status

All three records below were pulled through NCBI E-utilities and their abstracts read in full, not
summarised by a fetch tool (rules 25 and 39). They are quoted rather than paraphrased where the quotation is
load-bearing (rule 42).

### The finding is not novel, and that is better news than novelty would have been

**Kallionpää RE, Valli K, Scheinin A, Långsjö J, Maksimow A, et al. "Alpha band frontal connectivity is a
state-specific electroencephalographic correlate of unresponsiveness during exposure to dexmedetomidine and
propofol." *Br J Anaesth* 2020;125(4):518-528. PMID 32773216. NCT01889004.**

Forty-seven healthy males, **dexmedetomidine (n = 23) or propofol (n = 24)**, 64-channel EEG, alpha-band
connectivity measured by coherence, **wPLI** and directed PLI. The abstract states:

> "At ROR, prefrontal-frontal connectivity reversed to the level observed before LOR, indicating that
> **connectivity changes were related to unresponsiveness rather than drug concentration**." … "Local
> prefrontal-frontal EEG-based connectivity reflects unresponsiveness induced by propofol **or**
> dexmedetomidine, suggesting its utility in monitoring the anaesthetised state with these agents."

**That is not literally E35's probe, and the difference has to be stated or this note commits rule 42
against itself.** Kallionpaa tested whether connectivity tracks *state rather than concentration* within a
drug, and whether it does so *under either agent*. E35 tested something adjacent: whether a feature can tell
the two agents apart *at matched unresponsiveness*. The two are close and they are not the same statistic.
What Kallionpaa establishes is that the phase-family measure behaves the same way in both drugs, in a larger
and better-designed cohort — healthy volunteers, scalp, and **within-subject LOR/ROR at constant dosing**,
which separates state from concentration in a way the Krause deposit structurally cannot. Combined with
Akeju's spectral result below, the two papers imply the family split; **neither one tests it**, and no
published work sets a capability control beside a drug-leak measurement the way E36 does.

**Akeju O, Pavone KJ, Westover MB, Vazquez R, Prerau MJ, et al. "A comparison of propofol- and
dexmedetomidine-induced electroencephalogram dynamics using spectral and coherence analysis."
*Anesthesiology* 2014;121(5):978-89. PMID 25187999.**

The other half. Dexmedetomidine spindles peak near 13 Hz, propofol frontal alpha near 11 Hz, and the
conclusion is that the two agents "place patients into **different brain states**". Spectral power is
agent-specific; this was already known and E35 cited this paper as its own justification for expecting
opposite-signed effects, without noticing that it also supplies the amplitude half of the family split.

**Hudetz AG, Mashour GA. "Disconnecting Consciousness: Is There a Common Anesthetic End Point?"
*Anesth Analg* 2016;123(5):1228-1240. PMID 27331780.** The review that frames the question, and which asks
for exactly the design this project could not build: "a systematic delineation of connectivity changes with
multiple anesthetics using the same experimental design, and the same analytical method".

### What this does to E35 and E36

**Deflates the novelty and strengthens the evidence, and the second matters more.** E36's binding limitation
was that it ran on E35's own rows and could not replicate externally — "the claim stays unclaimed until an
independent two-agent cohort exists, and none does". Kallionpää 2020 is that external agreement, arrived at
independently, in scalp EEG rather than intracranial, in healthy volunteers rather than epilepsy-surgery
patients, with a within-subject design that removes the nesting of drug arm inside patient identity that
E36 named as its structural limit.

**What E35/E36 still contribute is methodological, and should be stated as that and nothing more:** the two
families are tested *against each other* with a single statistic (Δ, a difference of differences that
separates agent-invariance from insensitivity), against an exhaustive enumeration of all 495 alternative
partitions, with multiplicity control and a nuisance floor. No published version of this comparison sets a
capability control beside the drug-leak measurement.

**One discrepancy, recorded rather than smoothed.** Kallionpää report that "anterior-posterior connectivity
in the alpha band did not differentiate LOR and ROR", while `longwPLI` in the Krause deposit carries state
legibility of 0.315-0.365 and passes both of E35's bars. These may not conflict — LOR-versus-ROR at constant
dosing is not the same contrast as wake-versus-unresponsive — but the difference is real and a successor
should not assume the long-range result transfers.

### The corollary for Q9

Q9 records that no public deposit has two mechanistically distinct agents in patients who share arms.
Kallionpää's cohort has the design; whether the data can be obtained is unknown and untested. **The Turku
group (NCT01889004) is a data-request target on the same footing as WBIC and ds005620**, and a better one
than either for Challenge A specifically.
