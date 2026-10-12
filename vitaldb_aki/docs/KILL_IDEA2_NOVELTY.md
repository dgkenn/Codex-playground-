# Novelty kill-attempt: arterial waveform morphology / wave-reflection recovery kinetics → postoperative AKI (VitalDB)

**Idea under test:** Intraoperative arterial blood-pressure waveform morphology
— specifically the *recovery kinetics* of wave reflection/augmentation after a
hemodynamic perturbation (a vasoregulatory-reserve marker) — predicts
postoperative AKI on VitalDB (n~3,100 arterial-line cases, ~320 AKI events),
claimed to be invisible to TWA-MAP / AUC-MAP<65.

**Method:** PubMed (via MCP), targeted web search, attempted medRxiv full-text
fetch (blocked, 403; relied on search-result snippets + abstract). Also
cross-checked against this repo's sibling self-novelty memo
(`/home/user/Codex-playground-/docs/INTRAOP_WAVEFORM_CONSTRUCTS.md`, "Idea 1
(TOP RANK)"), which already proposed almost exactly this construct and ran its
own (less targeted) novelty pass that missed the papers found below.

---

## VERDICT: **WOUNDED** (bordering on DEAD for the AKI outcome as stated; survives only with a sharp, narrow differentiator)

The core causal story — "arterial-waveform-derived dynamic vascular-tone
metric beats time-integrated MAP at predicting postoperative AKI, including
on/near VitalDB-style perioperative cohorts" — has already been published,
multiple times, in 2024–2025, by groups working the *identical* mechanistic
angle (vascular tone / wave reflection / perfusion-pressure dynamics as the
thing TWA-MAP can't see). One preprint is close enough in title and design
that it should be treated as a near-direct collision on methodology (though
on a different, smaller, single-center cohort, not VitalDB).

---

## The three most threatening papers

### 1. Tissue Perfusion Pressure (TPP) predicts AKI after cardiac surgery — closest mechanistic collision
Miles TJ, Guinn MT, Tan X, et al. "Tissue perfusion pressure: A novel
hemodynamic measure to assess risk of acute kidney injury after cardiac
surgery." *J Thorac Cardiovasc Surg.* 2025;171(2):455-462.e3.
PMID: 40680825. [DOI](https://doi.org/10.1016/j.jtcvs.2025.07.009)

- TPP = MAP − critical closing pressure (Pcrit), where **Pcrit is itself
  estimated from the arterial pressure waveform** (vascular-tone-dependent
  closing pressure, not a static threshold).
- n = 1,224 cardiac surgery patients; AKI in 17.6%.
- TPP < 38 mmHg predicted AKI **independent of average MAP** (adjusted OR
  1.69, 95% CI 1.17–2.45, in vasopressor-requiring patients).
- Used **unsupervised clustering (K-means)** on hemodynamic phenotypes —
  the same "discover a vascular-tone phenotype that MAP misses" framing the
  idea proposes.
- This is a *waveform-derived, vascular-tone, dynamic* metric, explicitly
  positioned against plain MAP, predicting AKI, on a comparable-size
  perioperative cohort. It is not "augmentation index" or "wave reflection"
  by name, but it is mechanistically the same claim: **a waveform-derived
  measure of how "tight" the vasculature is dynamically predicts AKI beyond
  pressure dose.**

A companion/earlier paper from a related group: Ayers BC et al., "Prebypass
Critical Closing Pressure Predicts Acute Kidney Injury After Cardiopulmonary
Bypass." *J Cardiothorac Vasc Anesth.* 2024;39(2):437-446. PMID: 39645444.
[DOI](https://doi.org/10.1053/j.jvca.2024.11.010) — n=1,038, Pcrit computed
from arterial waveform data, 16% increased AKI risk per 5 mmHg Pcrit increase,
independent of MAP. This establishes the "waveform-derived vascular tone >
MAP for AKI" claim was already live in the literature a year before the TPP
paper above, i.e., it's a developing program, not a one-off.

### 2. Direct title/design collision — intraoperative ABP waveform *morphology variation* predicts AKI, explicitly benchmarked against standard vital-sign metrics
"Intraoperative arterial blood pressure waveform variation predicts
short-term acute kidney injury after cardiac surgery." medRxiv preprint,
DOI: 10.1101/2025.10.12.25337819 (posted October 2025).
https://www.medrxiv.org/content/10.1101/2025.10.12.25337819v1

- Prospective single-center cohort, elective cardiac surgery with CPB,
  n = 101.
- Defines **"VarM" — variation of arterial waveform morphology** quantified
  beat-to-beat from the ABP pulse contour (i.e., waveform shape dynamics,
  not a static single-beat index and not raw MAP/pulse-pressure level).
- Explicitly frames the question as: conventional BP measures (systolic,
  diastolic, pulse pressure) capture only partial information; **waveform
  morphology potentially reflects additional cardiovascular regulatory
  information** invisible to those measures — i.e., the *exact* framing of
  the idea under test.
- Found: **lower VarM, and a falling VarM trend after CPB weaning**, were
  associated with postoperative AKI (KDIGO-defined).
- Combining VarM with baseline eGFR + EuroSCORE + CPB time gave **AUC 0.775**,
  and the paper reports this **outperformed standard vital-sign metrics**
  (i.e., it directly benchmarks against and beats TWA-style MAP summary
  statistics — precisely the comparison the idea proposes to make on
  VitalDB).
- This is title-for-title, framing-for-framing the same study design,
  missing only the explicit "wave reflection / augmentation index" vocabulary
  and the VitalDB dataset. The "post-CPB-weaning trend" language is also a
  dynamic/trajectory framing, not purely static — it edges toward the
  "recovery kinetics after a perturbation" angle (CPB weaning is itself a
  major hemodynamic perturbation).
- Caveat: this is a preprint (not yet peer-reviewed), single-center, n=101 —
  far smaller and less generalizable than the proposed VitalDB study (n~3,100,
  ~320 AKI events), and full-text was not retrievable (medRxiv blocked
  automated fetch with HTTP 403; this assessment relies on the abstract/title
  and indexed summary, not a full methods read). It could not be confirmed
  whether VarM operationalizes "recovery half-life after a discrete
  perturbation via wave-reflection decomposition" or a simpler beat-to-beat
  variability/dispersion statistic — these are different constructs, and the
  gap between them is exactly where any surviving differentiator would have
  to live.

### 3. Conceptual prior art establishing the mechanism as already well-rehearsed
Al-Qamari A, Adeleke I, Kretzer A, Hogue CW. "Pulse pressure and perioperative
stroke." *Curr Opin Anaesthesiol.* 2019;32(1):57-63. PMID: 30543556.
[DOI](https://doi.org/10.1097/ACO.0000000000000673)

- Review explicitly states that **pulse wave velocity and augmentation
  index** (wave-reflection-based measures) are **more sensitive than
  peripheral pulse pressure** for detecting vascular stiffness, and that
  vascular stiffness/wave reflection physiology predisposes to AKI via
  altered renal (and cerebral) autoregulation — i.e., the field has already
  articulated "wave-reflection-based vascular stiffness, not blood pressure
  level, drives perioperative organ injury including AKI" as a stated
  mechanistic hypothesis, six years before the idea under test. It does not
  test *recovery kinetics after a perturbation* specifically (it is about
  static/baseline stiffness), but it forecloses the claim that "wave
  reflection as an AKI mechanism" itself is a novel idea — only the
  *dynamic/recovery-kinetics* framing could still be new.

---

## Saturation check: is "intraoperative BP → AKI" via TWA-MAP/AUC<65 already exhausted?

Yes, decisively. Evidence:
- A 2025 systematic review and meta-analysis of the Hypotension Prediction
  Index (HPI) — itself a waveform-derived (proprietary ML on arterial
  waveform features) early-warning signal — pooled **22 studies**, AUC 0.90
  for IOH prediction, explicitly testing whether reducing
  TWA-hypotension improves AKI/renal outcomes, concluding benefit is
  "uncertain." Shirmohamadi E et al., *BMC Anesthesiol.* 2025;25(1):388.
  PMID: 40745629. [DOI](https://doi.org/10.1186/s12871-025-03250-4)
- A March 2026 PLoS Medicine paper trained a Transformer on 319,699 surgical
  cases (+ external Korean validation) specifically linking IOH burden
  (cumulative MAP≤65/60/55 mmHg·min — exactly TWA/AUC-style dosing) to
  postoperative AKI/AKD, with significant dose-response ORs. Zhu S et al.
  PMID: 41880331. [DOI](https://doi.org/10.1371/journal.pmed.1005024)
- VitalDB itself is already a standard external-validation dataset for
  AKI-after-noncardiac-surgery ML models (n=5,512 VitalDB patients used for
  external validation in a published internal/external AKI model comparison,
  PMC11204685), so "AKI prediction on VitalDB" per se is not new; novelty can
  only come from the *feature class* (waveform morphology dynamics vs.
  tabular/EHR features), and that feature class is the part already colonized
  by papers #1 and #2 above.
- HPI itself is already a waveform-morphology-derived (not raw-MAP) predictor
  in routine clinical and trial use (PMID 38439069, 41510867, 41745362),
  meaning "use arterial waveform features beyond MAP to anticipate
  hemodynamic compromise relevant to AKI" is an established commercial and
  academic product category, not a vacant niche — though HPI predicts
  *upcoming hypotension*, not AKI directly, and does not (publicly) use a
  wave-reflection-recovery-kinetics construct, so it is adjacent rather than
  identical.

The TWA-MAP/AUC<65 → AKI literature is saturated to the point of supporting
meta-analyses; a paper whose sole differentiator is "we used VitalDB and
beat TWA-MAP" is incremental on its own.

---

## What, if anything, survives

The literature search did **not** find a study that:
1. Decomposes the arterial waveform into forward/backward (reflected) wave
   components or augmentation index **per beat**, AND
2. Fits a **recovery time-constant/half-life** to that quantity following a
   **discrete, identifiable hemodynamic perturbation** (anesthesia induction,
   pneumoperitoneum insufflation, aortic cross-clamp/declamp, vasopressor
   bolus) — i.e., a repeated-measures, perturbation-triggered kinetic
   construct generalizable across perturbation types and surgeries, AND
3. Tests this specifically against AKI on a multi-thousand-patient, mixed
   noncardiac VitalDB-scale cohort, head-to-head against TWA-MAP/AUC-MAP<65.

The closest precedents (TPP/Pcrit, VarM) target **vascular tone level or
beat-to-beat variability**, not **post-perturbation recovery kinetics** of a
wave-reflection-specific quantity. The liver-transplant anhepatic-phase study
(noted in the sibling memo, ClinicalTrials.gov NCT03694301) found *binary*
reflected-wave presence/absence at one fixed surgical moment (reperfusion) —
not a fitted recovery curve.

**The surviving differentiator, if the idea is pursued, must be narrowed to:**
*recovery-kinetics* (a fitted time-constant after a defined perturbation),
explicitly contrasted against (a) static augmentation index/wave reflection
(PMID 30543556), (b) static or trend-level vascular-tone metrics like Pcrit/
TPP (PMID 39645444, 40680825), and (c) beat-to-beat morphology variability
without perturbation-locking (the medRxiv VarM preprint). The framing must
state up front, as a related-work paragraph, that "waveform-derived dynamic
vascular metrics beat MAP-dose metrics for AKI" is **already published
twice** in 2024–2025 cardiac-surgery cohorts (TPP, Pcrit) and that a
TWA-MAP-beating waveform-morphology metric for cardiac-surgery AKI is **already
in preprint** (VarM) — and then argue that *recovery kinetics specifically*,
on a broader noncardiac VitalDB cohort at 30x the preprint's sample size, is
the new contribution, not "waveform beats MAP" in general.

This is a materially weaker claim than the one as originally stated ("the
claim is that this waveform-derived dynamic is invisible to standard
TWA-MAP/AUC-MAP<65 metrics" — false as a general proposition; specific
dynamic-vascular-tone and waveform-morphology constructs have already been
shown to add information beyond MAP-dose metrics for AKI, twice, in the last
18 months).

## Note on internal prior art
This exact construct ("wave-reflection recovery half-life after a discrete
perturbation, AKI as outcome, contrasted with TWA-MAP/AUC-MAP<65") was
already independently proposed as "Idea 1 (TOP RANK)" in this repo's sibling
file `/home/user/Codex-playground-/docs/INTRAOP_WAVEFORM_CONSTRUCTS.md`. That
memo's own novelty pass found only the liver-transplant anhepatic-phase
precedent and called the construct "plausibly novel." The present, more
targeted PubMed pass found three additional, more threatening papers (TPP,
Pcrit, and the VarM medRxiv preprint) that the prior memo's general web
search missed — those should be treated as supersession of that memo's
novelty verdict, not a duplicate confirmation of it.
