# Literature check: does a decision threshold transport across sites without harmonisation?

*2026-08-02. Literature check only — no analysis, no registration. Written before further investment in
this line, per standing instruction.*

**The sentence under test:** "EEG measures whose distributions differ substantially between recording
sites nonetheless transport a decision THRESHOLD between those sites with negligible accuracy loss, so
distributional harmonisation is not a prerequisite for deploying an EEG index."

---

## VERDICT (one line)

**PARTIALLY PUBLISHED.** The general statistical mechanism behind this sentence — that discrimination
(rank-ordering, and by extension a threshold set on that ranking) transports across settings more readily
than calibration, because case-mix / distributional differences act on the *level* of a risk estimate
without necessarily disturbing its *order* — is **well-established, textbook material in clinical
prediction modelling** (Justice 1999, PMID 10075620; Debray et al. 2015, PMID 25179855; Van Calster et al.
2016, PMID 26772608; Van Calster et al. 2019, PMID 31842878). This is the single most damaging prior-art
finding for this line's novelty and **must be read before registering anything**, per item 3 below. Against
that: no paper I could locate states the EEG-specific, threshold-transport framing directly, tests it as a
registered hypothesis, or does so for a *biomarker's decision threshold on the measurement itself* rather
than a *fitted model's risk-probability threshold*. Items 1, 2 and 4 (EEG harmonisation, EEG domain
adaptation, anaesthesia-depth indices) are **UNADDRESSED** as stated — I found no paper in any of those
three literatures that asks this question, as opposed to assuming the opposite (harmonise/recalibrate
first) and never testing whether that step was necessary.

---

## 1. EEG harmonisation (ComBat / neuroCombat / reComBat / neuroHarmonize)

**What the literature claims harmonisation is necessary for, in every paper found:** improving downstream
classification/diagnostic accuracy and reducing "batch effects" so that pooled multi-site data can be
analysed as if from one population. Every EEG-harmonisation paper located follows the pattern
**harmonise → then classify/compare** and reports harmonisation as a preprocessing step whose value is
assumed, not tested as a null hypothesis.

- **PMID 40967145** (Jaramillo-Jimenez et al., *Comput Biol Med* 2025) — 11-site, 639-subject
  neurodegenerative-disease EEG study. Quote: *"Multicenter studies could tackle these limitations, but
  data pooling might introduce site-related rsEEG differences (batch effects) ... Power spectrum batch
  effects were harmonized using reComBat ... Statistical testing showed reduced batch effects after
  harmonization."* Harmonisation is applied and its reduction of batch effects is confirmed — but the study
  never asks whether the pre-harmonisation, unharmonised classifier would have worked at a fixed threshold
  anyway.
- **PMID 35398285** (Li et al., HarMNqEEG, *NeuroImage* 2022) — 1564 subjects, 9 countries, 12 devices, 14
  studies. Quote: *"We demonstrate qEEG 'batch effects' and provide methods to calculate harmonized
  z-scores ... harmonized Riemannian norms produce z-scores with increased diagnostic accuracy."* Again:
  harmonise, then show the harmonised version is *better* — not a test of whether the un-harmonised
  threshold degrades negligibly or catastrophically.
- **PMID 41811929** (Henao Isaza et al., *PLoS One* 2026) — explicitly harmonises 4 cohorts with
  neuroHarmonize "to reduce site-related variability" before classification; no unharmonised-threshold arm
  reported.
- **PMID 37424962** (Prado et al., *Alzheimers Dement (Amst)* 2023) — same pattern: harmonisation protocol
  is presented as "critical for strengthening ... EEG signatures ... as potential dementia biomarkers,"
  again asserted rather than tested against a no-harmonisation comparator.

**Searched and found nothing:** `"is harmonization necessary"` (1297 hits, none EEG/threshold-specific on
inspection of top results — general biomedical harmonisation literature, not EEG threshold transport);
`ComBat AND (necessary OR needed) AND classification` (126 hits, same pattern — methods papers proposing
harmonisation, not testing its necessity); `"site harmonization" AND unnecessary` (**0 hits**); `batch
effect AND classification AND (without harmonization OR unharmonized)` (12 hits, none of which — on title
inspection — registered a "does the threshold still work" comparison as their primary question).

**Conclusion for item 1:** I found no EEG paper that asks "was harmonisation actually necessary for this
decision to transport," only papers that harmonise and then report improved performance. This is the gap
the sentence would fill, if EEG-specific novelty is what is being assessed — but see item 3, which shows
the *general form* of this question already has a textbook answer outside EEG.

---

## 2. Domain shift / transfer learning in EEG classification

The cross-subject and cross-dataset EEG generalisation literature is large and almost uniformly frames the
problem as **recalibrating a model** (fine-tuning, adaptation layers, subject-specific calibration
sessions, adversarial domain adaptation) rather than **importing a fixed threshold**. That framing choice
is itself informative: the field's default assumption is that the model (and, implicitly, its decision
boundary) does not transport, and effort goes into fixing that.

- Searches `transfer learning AND EEG AND cross-dataset` (11 hits) and `cross-subject AND EEG AND
  calibration-free` (13 hits) returned papers on subject-invariant feature learning, domain-adversarial
  training, and "calibration-free" BCI systems — but "calibration-free" here means "no per-subject
  recalibration session before use," not "no distributional harmonisation was needed and the threshold
  still worked." These are different claims sharing a word.
- I did not find, in the titles/abstracts surfaced, any paper that explicitly separates "did the
  *discriminative ranking* transport" from "did the *decision threshold* transport" as two distinct
  measured quantities, the way clinical prediction modelling routinely separates discrimination from
  calibration (item 3). The EEG domain-adaptation literature does not appear to use the
  discrimination/calibration vocabulary at all in the abstracts inspected.

**Searched and found nothing:** `label shift AND classifier AND threshold` (**0 hits**); `covariate shift
AND decision threshold` (**0 hits**). Both are natural search terms for the general-ML version of this
question and returned nothing in PubMed — consistent with this being more of a general-ML/statistics
literature question (arXiv, ML venues) than a PubMed-indexed one; PubMed coverage of the pure-ML
literature is known to be poor, so absence here is weak evidence at best and should not be read as
absence from the field.

**Conclusion for item 2:** the "threshold transports even when distributions do not" observation is not
stated, in the abstracts located, anywhere in the EEG domain-adaptation literature. This item is
**UNADDRESSED** as searched, with the caveat that PubMed is not the right index for the ML side of this
question and a non-PubMed pass (arXiv, NeurIPS/ICML proceedings) was out of scope for this E-utilities-only
check.

---

## 3. The general statistics — discrimination vs. calibration transportability (checked first, as instructed)

**This is where the sentence is closest to already existing, and it is the reason the line's novelty is in
question.** The relevant literature is the clinical-prediction-model / external-validation literature, and
it has a settled vocabulary for almost exactly this distinction.

### 3a. Justice, Covinsky, Berlin 1999 — the foundational framework

**PMID 10075620**, *Ann Intern Med* 1999, "Assessing the generalizability of prognostic information."
Literal quote from the abstract: *"This paper describes an approach for evaluating prognostic systems
based on the accuracy (calibration and discrimination) and generalizability (reproducibility and
transportability) of the system's predictions ... Transportability is the ability to produce accurate
predictions among patients drawn from a different but plausibly related population."*

This paper is the origin of the four-way vocabulary (calibration, discrimination, reproducibility,
transportability) that every subsequent paper below uses. It treats calibration and discrimination as
**separable properties that can transport differently** — the load-bearing structural fact behind the
sentence under test — though the abstract itself does not state which of the two transports better; that
claim comes from the papers below. (I could not obtain PMC full text for this 1999 Annals article via
E-utilities — it predates PMC's usual open-access coverage and no PMC link was returned by `elink`; the
quote above is from the indexed abstract only, and the full-text argument is not verified here.)

### 3b. Debray et al. 2015 — the three-step case-mix framework

**PMID 25179855**, *J Clin Epidemiol* 2015, "A new framework to enhance the interpretation of external
validation studies of clinical prediction models." Quote: *"We propose to quantify the degree of
relatedness between development and validation samples on a scale ranging from reproducibility to
transportability by evaluating their corresponding case-mix differences. We subsequently assess the
models' performance in the validation sample and interpret the performance in view of the case-mix
differences."* And from the results: *"The performance in all validation samples was adequate, and the
model did not require extensive updating to correct for miscalibration or poor fit to the validation
settings"* — an empirical instance in which case-mix differences across sites did **not** force
recalibration, reported as a positive finding for one specific model (deep venous thrombosis diagnosis),
not as a general law.

### 3c. Van Calster et al. 2016 — the calibration hierarchy, and the threshold-relevant guarantee

**PMID 26772608**, *J Clin Epidemiol* 2016, "A calibration hierarchy for risk models was defined: from
utopia to empirical data." This is the most directly load-bearing citation for the threshold-transport
claim, because it proves a decision-relevant guarantee rather than just describing case-mix. Quote: *"we
prove that moderate calibration guarantees nonharmful decision making ... Strong calibration is desirable
for individualized decision support but unrealistic and counterproductive ... Model development and
external validation should focus on moderate calibration."* **This defines the exact condition — moderate
calibration, a much weaker requirement than full distributional matching — under which acting on a fixed
threshold is safe**, and explicitly downgrades the need for the model to be "fully correct for the
validation setting" (their definition of "strong calibration," which is the closest formal analogue to
"distributions match"). This is an inference on my part, not a quotation: the paper does not use the word
"threshold" in the abstract, and its guarantee is about *decision-making being nonharmful*, which I am
reading as equivalent to "the threshold remains usable" — a reasonable but not verbatim equivalence.

### 3d. Van Calster et al. 2019 — calibration as the fragile property

**PMID 31842878**, *BMC Med* 2019, "Calibration: the Achilles heel of predictive analytics." Quote:
*"poorly calibrated algorithms can be misleading and potentially harmful for clinical decision-making ...
Efforts are required to avoid poor calibration when developing prediction models, to evaluate calibration
when validating models, and to update models when indicated."* I pulled the PMC full text (PMC6912996) and
grepped it directly (not WebFetch, per rule 39): it discusses at length how **incidence/case-mix
differences between settings systematically distort calibration** — quote from the full text: *"When an
algorithm is developed in a setting with a high disease incidence, it may systematically give
overestimated risk estimates when used in a setting where the incidence is lower"* — but the full text I
retrieved does **not** contain the words "transport" or "portable," and does not contain an explicit
sentence of the form "discrimination transports while calibration does not." That specific phrasing, which
I expected to find verbatim, is **not in this paper** — it is a fair paraphrase of the paper's overall
argument (calibration breaks under case-mix shift; the paper's entire point is that this happens *even
when discrimination looks fine*, which is the standard reason discrimination gets checked less often at
validation), but I am flagging that I looked for the literal sentence and it is not there.

### 3e. Decision curve analysis — a related but distinct threshold concept

**PMID 17099194**, Vickers & Elkin 2006, *Med Decis Making*, "Decision curve analysis: a novel method for
evaluating prediction models." This establishes "threshold probability" as a clinical decision concept —
quote: *"the threshold probability of a disease or event at which a patient would opt for treatment is
informative of how the patient weighs the relative harms of a false-positive and a false-negative
prediction."* **This is a different threshold than the one in our sentence**: Vickers's threshold is a
*clinical preference parameter* (how much false-positive harm a patient will tolerate), not a *cutpoint on
an EEG measure's distribution*. Citing it as support for "thresholds transport" would be a rule-42
violation (a quotation supporting only what it literally says) — noted here so it is not mis-cited later.

### What item 3 shows, plainly, per the task's instruction

**Yes, the core general-statistics claim in the target sentence is a known result in clinical prediction
modelling, and this must be stated up front:** the literature already distinguishes discrimination from
calibration as separately-transporting properties (Justice 1999), already frames external validation
around case-mix-driven shifts that primarily damage calibration (Debray 2015, Van Calster 2019), and
already proves a formal decision-safety guarantee (moderate calibration) that is weaker than "the full
distribution transports" (Van Calster 2016). **If the BSDE line's contribution is "EEG-measure
distributions differ across sites, and this is analogous to case-mix, so we should ask about the threshold
rather than the whole distribution" — that reframing already exists as the field's standard external-
validation methodology, just not under the word "harmonisation" and not for EEG specifically.** What does
not already exist, as far as this search reached, is (i) an EEG-specific empirical demonstration of it, and
(ii) the literal statistical statement "a threshold transports whenever both sites' class-conditional
distributions straddle a common value regardless of their means" stated as a standalone lemma — the closest
approach is Van Calster 2016's moderate-calibration guarantee, which is a related but not identical
condition (moderate calibration is about the *predicted-risk-to-observed-event-rate* map, not directly
about *raw feature distributions straddling a cutpoint*).

---

## 4. Anaesthesia / sedation depth indices (BIS, PSI) — threshold transport across sites, devices, populations

**No paper found that directly tests whether the BIS 40–60 "adequate anaesthesia" threshold, or an
equivalent PSI/SedLine threshold, holds across sites/devices/populations despite the underlying EEG
distributions differing.** What exists instead:

- **PMID 33823811** (Jones et al., *BMC Anesthesiol* 2021) — a study *protocol* for simultaneously
  comparing BIS and SedLine (PSI) on the same patients via a shared-electrode interface, motivated by:
  *"Prior studies comparing brain function monitoring devices have applied both sensors on the forehead of
  study subjects simultaneously. With limited space and common sensor locations between devices, it is not
  possible to place both commercial sensor arrays according to the manufacturer's recommendations, thus
  compromising the validity of these comparisons."* This is evidence that even *within-patient,
  simultaneous* cross-device comparison is methodologically difficult, which is adjacent to but not the
  same question as cross-site threshold transport. I did not locate the completed trial's results paper in
  this search (only the protocol was returned).
- Pediatric BIS validation papers (e.g., the cluster around PMID 40638527, comparing frontal permutation
  entropy to standard indices in children) exist and compare indices to each other in a given population,
  but the searches run here (`bispectral index AND (pediatric OR children) AND validation`, 45 hits) did
  not surface, on inspection of the abstracts pulled, a paper that frames its question as "does the
  standard adult threshold require adjustment because the distribution differs in children, or does it
  transport anyway."

**Searched and found nothing:** `bispectral index AND race` (**0 hits** — surprising, since BIS's
sensitivity to skin pigmentation/forehead anatomy is a known clinical concern discussed in commentary
literature; either the framing terms don't match indexed abstracts or this is discussed under different
vocabulary, e.g. "frontal EMG artifact" or "signal quality index," which was not searched here and should
be if this line continues); `processed EEG AND depth of anesthesia AND cross-population` (**0 hits**); `BIS
60 AND cutoff AND validation` (**0 hits**); `sedation index AND threshold AND generaliz*` (**0 hits**).

**Conclusion for item 4:** UNADDRESSED as searched. This is the item with the weakest search coverage in
this check — the vocabulary anaesthesia-depth papers use for cross-population/cross-device concerns
(likely "signal quality," "EMG contamination," "race," "skin type," "pediatric norms") was not fully
explored, and a second pass using those terms specifically is the natural next step if this line proceeds.

---

## Summary table

| item | question | verdict | strongest citation |
|---|---|---|---|
| 1. EEG harmonisation | Does anyone test threshold transport WITHOUT harmonising, as opposed to harmonising and reporting improvement? | UNADDRESSED (norm is harmonise-then-classify; no null test of harmonisation's necessity found) | PMID 40967145, PMID 35398285 |
| 2. EEG domain shift / transfer learning | Is "threshold transports even when distributions don't" stated anywhere? | UNADDRESSED (field's framing is model recalibration, not threshold import; discrimination/calibration vocabulary not used) | none directly on point |
| 3. General statistics of transportability | Is this a known result in clinical prediction modelling? | **YES, substantially** — discrimination/calibration separability and case-mix framing are established; a formal decision-safety guarantee (moderate calibration) exists and is weaker than full distributional matching | PMID 10075620, PMID 25179855, PMID 26772608, PMID 31842878 |
| 4. Anaesthesia/sedation indices | Published work on threshold transport across sites/devices/populations? | UNADDRESSED as searched; vocabulary gap likely, not confirmed absence | PMID 33823811 (adjacent, not on point) |

## What this means for the line

Per the task's framing: **item 3's answer is the one that should stop or reshape this line.** The
statistical mechanism the BSDE result would demonstrate is not new in the abstract; the field already has
the discrimination/calibration split and a formal guarantee (moderate calibration) that is close to, but
not identical with, "the threshold transports because both sites' class-conditional distributions straddle
it." **The remaining, not-yet-published contribution — if there is one — is narrow and specific: an
empirical EEG demonstration, explicitly measured as a raw-feature-distribution shift alongside a
decision-threshold-transport test, which the harmonisation literature (item 1) and the domain-adaptation
literature (item 2) do not currently report, and which the anaesthesia-index literature (item 4) does not
appear to report either (subject to the vocabulary gap noted above).** Any registration that proceeds from
here should cite Van Calster 2016 (PMID 26772608) and Debray 2015 (PMID 25179855) as the prior art it is
either extending to EEG or, more usefully, should state up front the precise sense in which "distributions
differ but the threshold transports" is *not* already covered by "moderate calibration" — because as read
here, it may just be moderate calibration restated on new data, which per rule 60 must be checked before
the design is registered, not after.
