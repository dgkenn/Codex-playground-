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
