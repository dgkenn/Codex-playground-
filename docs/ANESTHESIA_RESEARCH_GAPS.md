# Anesthesiology research gaps — landscaping memo (retrospective intraop + EHR)

Status: research-direction memo, not an implementation plan. For internal
scoping only — **not medical advice, not for clinical use.**

Scope: open questions in anesthesiology that are (a) addressable with
retrospective data — intraoperative waveforms (EEG, arterial pressure,
ventilator) plus perioperative EHR — and (b) currently flagged by the field
as evidence-gapped, per a survey of 2022–2026 literature/editorials in
*Anesthesiology*, *British Journal of Anaesthesia* (BJA), *Anesthesia &
Analgesia* (A&A), and *Anaesthesia*, supplemented by PubMed and web search.

**Method note / novelty caveat.** Findings below come from PubMed literature
search (titles/abstracts/MeSH) plus targeted web search, not a systematic
review. "No prior art found" means no matching paper surfaced under the
search terms used — suggestive of a gap, not proof of one. Each item should
get a second, vocabulary-varied search pass before committing real analysis
time, exactly as practiced in `docs/PIVOT_IDEAS_DYNAMICS.md`. Searches were
run independently per theme by parallel research agents in June 2026.

---

## 1. Intraoperative hypotension & end-organ injury

**Open question.** Does *individualizing* the intraoperative MAP target
(to a patient's own baseline/ambulatory pressure) actually beat a simple
fixed threshold (MAP ≥ 65) for preventing AKI, myocardial injury, and
death — and separately, which exposure metric (time-weighted average /
area-under-threshold "dose" of hypotension, absolute nadir, or blood
pressure *variability*) is the right thing to minimize?

**Why high-impact.** Intraoperative hypotension is one of the most common,
modifiable intraoperative exposures in all of surgery; AKI and myocardial
injury after noncardiac surgery (MINS) are leading drivers of postoperative
morbidity. A definitive answer changes bedside vasopressor/fluid practice
across essentially every OR — this is exactly the territory that gets
multicenter RCTs and editorials in NEJM/JAMA/Anesthesiology/BJA.

**State of play (2023–2026).**
- **POISE-3** (Marcucci et al., *NEJM*/*Ann Intern Med* 2023, PMID 37094336):
  hypotension-avoidance (MAP ≥ 80) vs. hypertension-avoidance (MAP ≥ 60,
  continue home antihypertensives) — **no difference** in 30-day vascular
  death/MINS/stroke/cardiac arrest. Settled: neither blanket strategy wins.
- **POISE-3 AKI substudy** (*Kidney International* 2024): higher intraop BP
  did not reduce AKI — still framed as an open question by the authors.
- **IMPROVE-multi** (*JAMA* 2025, PMID 41076588; 15 German university
  hospitals, n=1134) — individualized MAP target (from preop nighttime
  ambulatory MAP) vs. routine MAP ≥ 65: **no reduction** in composite
  AKI/myocardial injury/cardiac arrest/death at 7 days. This is the most
  direct, modern, adequately powered test of the "individualization beats
  fixed threshold" hypothesis raised by the earlier INPRESS trial (Futier
  et al., *JAMA* 2017, PMID 28973220) — and it came back **negative**.
- **SPROUT-4** (*Trials* 2024 protocol, NCT06225453) — ongoing multicenter
  RCT of individualized vs. conventional BP management in high-risk
  noncardiac surgery; results expected ~2026. Still open.
- **Dose (TWA/AUC) vs. nadir**: no 2023–2026 study resolves which exposure
  metric dominates; cohort literature shows both duration and depth
  associate with AKI/MINS, with no head-to-head metric comparison settling
  it. A 2026 *Intensive Care Medicine* narrative review explicitly frames
  this as unresolved ("variability in thresholds and diagnostic criteria
  limits comparability across studies").
- **BP variability** (not just hypotension dose): several 2024–2025 cohort
  studies (including a pediatric cardiac surgery cohort, PMID 39870953, and
  an explainable-ML BPV phenotyping study, PMC12291218) report BPV as
  independently associated with AKI in univariate analysis, but
  significance is inconsistent after multivariable adjustment, and **no
  RCT has tested reducing BPV itself** as an intervention.
- Editorials flagging the gap explicitly: BJA "Managing postinduction
  hypotension: the jury is still out" (Thomsen et al., *BJA* 2025); the
  POQI international consensus statement on perioperative arterial
  pressure management (*BJA* 2024) — a consensus-by-expert-opinion
  document that itself signals the evidence base is thin; a 2024 BJA
  meta-analysis on *controlled* hypotension stating it "remains unclear"
  whether deliberately induced hypotension carries the same harm profile
  as inadvertent hypotension.

**Data needed.** High-resolution intraoperative arterial pressure (or
NIBP) time series + vasopressor/fluid administration + postoperative
troponin/creatinine trajectories + 30/90-day outcomes, ideally across
≥2 hospital sites for generalizability (per the IMPROVE-multi/POISE-3
lesson that single-center findings have not replicated).

**Novelty verdict — OPEN.** The "individualize the threshold" intuition
has now been tested at scale twice (POISE-3, IMPROVE-multi) and **failed**
both times — this undercuts naive individualization as a research angle,
but leaves the *exposure-metric* question (dose vs. nadir vs. variability)
and patient-*subgroup* heterogeneity (who actually benefits from
individualization, if anyone) genuinely open and not yet answered by any
single adequately-powered study.

---

## 2. Depth of anesthesia / EEG, postoperative delirium and POCD

**Open question.** Does titrating anesthetic depth to a raw or processed
EEG target reduce postoperative delirium (POD) or cognitive decline
(POCD) — and separately, do raw EEG *spectral/morphological* features
(beyond what BIS/Patient State Index already summarize) carry additional
predictive signal for postoperative neurocognitive outcomes?

**Why high-impact.** Postoperative delirium affects a large fraction of
older surgical patients, drives length of stay and long-term cognitive
decline, and EEG monitors are already in many ORs — if EEG-guided
titration worked, it would be one of the cheapest, most scalable
interventions in perioperative medicine. This is squarely
*Anesthesiology*/JAMA-tier territory (ENGAGES was published in JAMA).

**State of play (2022–2026).**
- **ENGAGES** (Wildes et al., *JAMA* 2019) — EEG-guided (BIS-targeted)
  anesthesia titration did **not** reduce delirium incidence vs. usual
  care, despite reducing anesthetic dose and burst suppression. This
  remains the field's pivotal negative trial.
- Follow-on/secondary analyses and related trials in 2022–2026 have
  largely **reinforced** the ENGAGES null result rather than overturning
  it: EEG-guided titration reliably reduces anesthetic exposure and burst
  suppression duration but has **not** been shown to reliably reduce POD
  in adequately powered multicenter trials. The live debate has shifted
  from "does EEG-guided titration prevent delirium" (trending settled-null
  for simple depth-titration strategies) to "is burst suppression itself
  causally harmful, or just a marker of brain vulnerability/frailty" —
  i.e., a confounding-by-indication question that observational titration
  trials can't resolve.
- **Burst suppression as a delirium risk factor**: still disputed whether
  it is causal or simply a marker of an already-vulnerable brain (frail,
  older, sicker patients both *generate* more burst suppression at a given
  anesthetic dose and *are* more prone to delirium). No 2023–2026 causal-
  inference study was found that cleanly resolves directionality.
- **Raw EEG spectral/morphological features beyond processed indices**:
  the Purdon/Mashour/Avidan-tradition work on frontal alpha power and an
  "EEG aging signature" continues to be an active frontier, but whether
  raw spectral or connectivity features add predictive value *beyond*
  BIS/PSi/suppression-ratio for delirium/POCD is not yet settled by a
  large external-validation study.
- **DELPHI-EEG** (Ahn, Lee, Gambus, Yoon, Ju, Lee H-C; *npj Digital
  Medicine* 2025, PMID 41249487) — deep-learning model on 6-lead
  intraoperative EEG, 34,550 cases / 267 delirium events, single center
  (Seoul National University Hospital): AUROC 0.870 vs. 0.729 for a
  burst-suppression-ratio logistic-regression baseline. The authors
  themselves state external validation across sites is required — this is
  the closest existing work to "deep learning on intraop EEG → POD," and
  it is **single-center, not yet externally validated**.
- **EEG foundation models for perioperative outcome prediction**: not
  found in the literature as of mid-2026. General-purpose EEG foundation
  models (LaBraM, BIOT, EEGPT, CBraMod, FEMBA) are an active line, but
  target epilepsy/sleep/BCI/psychiatric classification — none target
  intraoperative/perioperative outcome prediction. No "MORGOTH"-branded or
  comparable foundation model validated on perioperative EEG was found.

**Data needed.** Multi-channel intraoperative EEG waveforms (raw, not just
BIS/PSi summary numbers) + anesthetic dosing + perioperative delirium
assessments (CAM-ICU/3D-CAM) + cognitive testing, across multiple
hospitals for external validation — exactly the HEEDB + frozen-foundation-
model + held-out-hospital design this repo is built around.

**Novelty verdict — OPEN, and a clean fit.** "EEG-guided titration
prevents delirium" is trending settled-negative (don't re-litigate it
directly). But "do raw-EEG-derived intraoperative features (via a
self-supervised foundation model) predict postoperative delirium/POCD
better than processed indices, and does this replicate across hospitals"
is genuinely unanswered — DELPHI-EEG is the nearest prior art and is
explicitly single-center/hand-engineered-baseline-only. A held-out-hospital
replication using a pretrained EEG foundation model would be a real
advance over the current state of the art, not a re-run of ENGAGES.

---

## 3. Intraoperative mechanical ventilation

**Open question.** Does individualized PEEP (titrated to best
compliance/lowest driving pressure) reduce postoperative pulmonary
complications (PPCs) versus protocolized/fixed PEEP — and is driving
pressure a true causal target or just an associative marker of lung
mechanics?

**Why high-impact.** PPCs (pneumonia, respiratory failure, ARDS) are major
drivers of postoperative morbidity/mortality and length of stay,
especially after major abdominal/thoracic and laparoscopic surgery in
obese patients — ventilation strategy is one of the few intraoperative
levers anesthesiologists fully control.

**State of play (2023–2026).** Evidence remains mixed/unsettled:
individualized-PEEP trials following the PROVHILO legacy and iPROVE have
not produced a uniformly reproduced outcome benefit across populations,
and meta-analyses continue to disagree on whether driving-pressure-guided
titration changes PPC incidence versus simply correlating with it.
Continuous, high-resolution ventilator waveform data (loop morphology,
breath-by-breath compliance/resistance trends) — as opposed to single
summary driving-pressure values — has not been systematically linked to
outcomes at scale; this remains a recognized gap in recent narrative
reviews calling for richer waveform-level analysis rather than single-
number titration targets.

**Data needed.** Continuous ventilator waveform/flow-pressure-volume loop
data + tidal volume/PEEP/driving pressure trends + postoperative
pulmonary outcomes (pneumonia, reintubation, ARDS, 30-day respiratory
failure), ideally paired with the same multi-hospital EHR cohort used for
EEG/hemodynamic analyses, enabling a genuinely multimodal model.

**Novelty verdict — OPEN, but secondary priority for this project.**
Driving pressure and individualized PEEP are well-trodden territory with
an existing named target (driving pressure) and active trial programs;
the residual novelty here is specifically in *waveform-level* (not
summary-statistic) ventilator analysis combined with other intraop
streams — useful as a secondary/multimodal feature source rather than a
standalone EEG-centric study.

---

## 4. Nociception / analgesia monitoring

**Open question.** Do autonomic-index nociception monitors (ANI, NOL,
SPI, pupillometry) — alone or fused with other intraoperative signals —
meaningfully reduce opioid consumption or improve recovery outcomes, and
is there incremental signal in combining EEG + autonomic + hemodynamic
streams that single-modality monitors miss?

**Why high-impact.** Opioid-sparing intraoperative management is a major
clinical and public-health priority; if a monitor could reliably titrate
analgesia to actual nociceptive state, it would directly affect opioid
stewardship and postoperative pain/PONV outcomes.

**State of play.** ANI (Analgesia Nociception Index), NOL (Nociception
Level Index, Medasense/PMD200), SPI (Surgical Pleth Index, GE), and
pupillometry are **already commercialized, FDA-cleared/CE-marked, and
patented** monitors — flag and exclude any claim of inventing "a
nociception monitor" as non-novel. RCT/meta-analytic evidence for these
monitors reducing opioid consumption is mixed and monitor-specific (some
positive signal for NOL on intraoperative opioid titration in
single-center trials; SPI and ANI evidence is more inconsistent), and
none has demonstrated a robust effect on hard outcomes (persistent pain,
major morbidity) in adequately powered multicenter trials. The
*combination* of EEG + HRV/autonomic + hemodynamic signals as a fused
nociception/inadequate-analgesia predictor — rather than any single
proprietary index — has not been systematically explored in the
literature and is recurrently called for in review-level commentary as an
"integrative" direction without yet being executed at scale.

**Data needed.** Synchronized EEG + ECG/PPG (for HRV) + arterial pressure
+ opioid/anesthetic dosing + intraoperative "nociceptive events" (surgical
stimulation timestamps) + postoperative pain scores and opioid
consumption.

**Novelty verdict — PARTIALLY OPEN.** The individual indices (ANI, NOL,
SPI, pupillometry) are not novel and are commercially locked up. The open,
defensible angle is *multimodal fusion* (EEG + autonomic + hemodynamic) as
a non-proprietary, retrospectively-derived nociception/analgesia-adequacy
signal — but this is a harder data problem (requires precise stimulus
timestamps, which most retrospective EHR + waveform datasets, including
HEEDB, likely lack) and should be treated as exploratory/secondary rather
than a primary study anchor.

---

## 5. Hemodynamic instability prediction — the Hypotension Prediction Index (HPI) controversy

**Open question.** Does intraoperative arterial-waveform morphology
contain predictive information about impending hypotension *beyond* what
simple MAP-trend extrapolation already captures — and does acting on such
predictions (HPI-guided management) improve hard outcomes (AKI, MINS,
mortality), not just reduce hypotension-burden surrogates?

**Why high-impact.** This is a live, high-profile methodological
controversy with direct commercial stakes (Edwards Lifesciences' Acumen
HPI) and a multi-year peer-reviewed back-and-forth — a credible,
independent resolution would be read closely by the field.

**Background (settled facts — not novel to restate).** HPI is a
**proprietary, FDA-cleared, machine-learned** algorithm (Edwards
Lifesciences/Acumen), derived in Hatib et al., *Anesthesiology* 2018
(PMID 29894315), using ~3,022 features per cardiac cycle from the arterial
waveform, reporting AUC 0.95–0.97 for predicting MAP < 65 mmHg 5–15 min
ahead. This is commercial prior art — do not claim novelty for "an
algorithm that predicts hypotension from the arterial waveform."

**The controversy (2020–2024).**
- Enevoldsen & Vistisen, "Performance of the Hypotension Prediction Index
  May Be Overestimated Due to Selection Bias," *Anesthesiology* 2022
  (PMID 35984931) — shows the original derivation's data-selection process
  likely inflated HPI's apparent advantage over raw MAP (a circular-
  reasoning/data-leakage critique).
- Vistisen & Enevoldsen, "CON: The hypotension prediction index is not a
  validated predictor of hypotension," *Eur J Anaesthesiol* 2024
  (PMID 38085015) — argues HPI needs re-validation against a strong,
  simple baseline rather than a naive ΔMAP comparator.
- Jacquet-Lagrèze et al., "Prediction of intraoperative hypotension from
  the linear extrapolation of mean arterial pressure" (*EJA* 2022, PMID
  35695749) — introduces "LepMAP" (simple linear MAP extrapolation) as the
  baseline any future HPI comparison should be benchmarked against,
  implying earlier HPI-vs-comparator studies used a weak straw-man.
- Maheshwari et al. (Edwards-affiliated validation, *J Clin Monit Comput*
  2020, PMID 31989416) is itself one of the papers implicated by the
  selection-bias critique.

**Current status (2023–2026) — outcome-level evidence is now negative.**
Two 2026 meta-analyses of RCTs converge on a null outcome result:
- Ding et al., *Minerva Anestesiologica* 2026 (PMID 41733556; 10 RCTs,
  n=1746): no significant reduction in AKI, MINS, stroke, or 30-day
  mortality with HPI-guided management.
- Wang et al., *A&A Practice* 2026 (PMID 41980015; 14 RCTs, n=2030): no
  significant AKI reduction (RR 0.87); a nominal MINS reduction (RR 0.61)
  that does not survive sensitivity analysis.

**Bottom line.** HPI reliably reduces intraoperative hypotension
*exposure* (a process measure) — that part is settled. It has **not**
been shown, across the accumulated RCT base through 2026, to improve hard
patient-centered outcomes. The deeper methodological question (does
waveform morphology beat simple MAP-trend extrapolation at all, on an
independent non-vendor dataset) remains **open**: no fully independent,
non-Edwards, waveform-feature-level reanalysis on a fresh non-proprietary
dataset has directly arbitrated this. Independent academic efforts exist
on open data (VitalDB-based deep-learning hypotension predictors,
including a 2025 *J Clin Monit Comput* cross-center evaluation explicitly
benchmarking deep learning against MAP-derived baselines), but a
definitive, large-scale, independent verdict has not been published.

**Data needed.** High-fidelity arterial waveform (invasive or
non-invasive) + outcome labels (AKI, MINS, mortality), ideally on a fully
independent, non-Edwards-affiliated, multi-hospital dataset, benchmarked
against both raw MAP trend and LepMAP-style extrapolation as baselines.

**Novelty verdict — OPEN, high-value, but adjacent to this project's EEG
focus.** This is arguably the cleanest, most citable controversy in the
entire survey — but it is an arterial-waveform question, not an EEG
question. Relevant to this project mainly as (a) a secondary signal
stream to fuse with EEG for outcome prediction (Theme 6), or (b) a
methodological cautionary tale (selection bias / leakage in label
construction) directly applicable to how this project should construct
its own Phase-2 outcome labels.

---

## 6. Postoperative outcomes prediction from intraoperative dynamics (delirium, AKI, MINS, mortality)

**Open question.** Does fusing multiple intraoperative signal streams
(EEG + hemodynamic waveforms + ventilation + EHR), via a pretrained
representation, predict postoperative delirium/AKI/MINS/mortality better
than single-modality models — and does it replicate across hospitals?

**Why high-impact.** This is the most directly generalizable and highest
ceiling question in the survey: multimodal, externally-validated
intraoperative-to-postoperative prediction would be a genuine
methodological advance, not an incremental risk-marker paper, and is
exactly the kind of study that lands in *Anesthesiology*/BJA/npj Digital
Medicine.

**State of play (2023–2026).**
- Single-modality is still the norm. EEG-only (DELPHI-EEG, above,
  single-center); arterial-waveform-only (Shim et al. 2025, *Medicina*,
  PMID 41303875 — gradient boosting on VitalDB waveforms for
  intraoperative hypotension, AUROC 0.94, single-center retrospective); or
  the proprietary HPI (Theme 5). True multimodal EEG + hemodynamic +
  ventilator + EHR fusion specifically for delirium/AKI/MINS/mortality was
  **not found** as an established line in the 2023–2026 literature — a
  2025 review on fusion-driven multimodal learning for biomedical time
  series and a late-2025 preprint on wearable-vital-sign multimodal AI for
  postoperative complications both frame multimodal fusion as nascent.
- **External/cross-hospital validation is a recurring, explicit gap.**
  DELPHI-EEG's authors state external validation across sites is required;
  the HPI meta-analyses call for further independent trials; the broader
  pattern across VitalDB-based papers is single-center, retrospective,
  without an external test set. No standalone editorial titled exactly
  "intraoperative EEG-based deep learning is understudied" was found —
  treat the gap as evidenced by absence of large external-validation
  studies, not by an explicit editorial quote.
- **EEG foundation models for perioperative outcome prediction**: not
  found anywhere in PubMed or web search as of June 2026 (see Theme 2) —
  this is a genuine, unclaimed white space, not an overstated one.

**Data needed.** Exactly what this repo is built to assemble: HEEDB
intraoperative EEG (via a frozen foundation-model backbone) + perioperative
EHR outcomes (delirium, AKI, MINS, mortality), with hospital-split
confirmation and external (TUH) replication — i.e., the existing
preregistered protocol's design directly answers this gap, provided the
Phase-2 outcome and held-out-hospital firewall are honored.

**Data needed (richer version).** Adding synchronized arterial-pressure
and ventilator waveforms (Themes 1, 3, 5) as auxiliary modalities, if
available in HEEDB/EHR, would let the same pipeline directly test the
"does multimodal beat single-modality" question, not just the EEG-only
version of it.

**Novelty verdict — OPEN, and the strongest direct fit for this project.**
This is the theme most directly answerable by the existing repo
architecture (frozen EEG backbone + hospital-split confirmation +
TUH external replication) without modification, and the literature
explicitly confirms both (a) no one has applied an EEG foundation model to
perioperative outcome prediction, and (b) cross-hospital external
validation is a stated, unmet need across every adjacent single-modality
effort found.

---

## 7. Cerebral oximetry / NIRS-guided care

**Open question.** Does NIRS-guided correction of intraoperative cerebral
desaturation actually change patient-centered outcomes (delirium, POCD,
end-organ dysfunction) — as opposed to merely detecting desaturation
events — and in which surgical population/subgroup, if any?

**Why high-impact.** NIRS monitors are already widely deployed
(especially in cardiac surgery); a definitive null or positive result at
scale would directly inform whether continued routine use is justified.

**State of play (2022–2026).**
- **Cardiac surgery**: settled-negative-to-marginal for global outcomes.
  NIRS-guided management reduces desaturation episodes but multiple
  2022–2025 meta-analyses give conflicting/borderline pooled results for
  postoperative delirium specifically (one 2024 meta-analysis: OR 0.657,
  95% CI 0.447–0.965, p=0.032 — marginal positive; another in the same
  window: OR 0.75, 95% CI 0.50–1.14, p=0.18 — null). Treat "NIRS reduces
  cardiac-surgery delirium" as contested-marginal, not settled-positive.
- **Noncardiac, high-risk surgery — open, trending negative.** Bieze et
  al., "Role of Cerebral Oximetry in Reducing Postoperative End-Organ
  Dysfunction After Major Non-Cardiac Surgery: A Randomised Controlled
  Trial," *Clinics and Practice* 2025 (PMID 41294644): algorithm-guided
  rSO2 restoration successfully shortened desaturation duration (23±48 vs.
  9±15 min, p=0.01) but **null** on postoperative end-organ
  dysfunction/morbidity. Notably underpowered (n=101 actual vs. n=394
  planned) — suggestive-null, not definitive.
- A 2025 noncardiac-surgery meta-analysis (Qiu et al., *World
  Neurosurgery*, PMID 39701521) found rSO2-guided management reduced
  POCD at 7 days but did **not** reduce POD, did not improve MMSE, and did
  not shorten length of stay — internally inconsistent, authors urge
  caution given heterogeneity.
- A 2024 narrative review ("Cerebral oximetry in high-risk surgical
  patients: where are we?", *Current Opinion in Critical Care*, Dec 2024,
  vol 30(6)) concludes NIRS is useful for neurologic complications in
  cardiac surgery specifically, but evidence in noncardiac surgery/
  nonneurological outcomes needs further confirmation — the closest
  available framing of "NIRS remains unproven outside cardiac/neuro,"
  though not phrased exactly that way in any single editorial found.

**Data needed.** Continuous rSO2 traces + desaturation-correction protocol
adherence + postoperative cognitive and end-organ outcomes, ideally
adequately powered (the existing noncardiac RCT was underpowered) and
stratified by surgical population.

**Novelty verdict — OPEN but a weak fit for this project.** NIRS data is
a separate monitoring modality from EEG and is not part of HEEDB's
intraoperative EEG focus; the open question here ("which intervention
triggered by desaturation actually helps, in which subgroup") would
require its own prospective or NIRS-specific retrospective dataset. Useful
mainly as comparison/context, not a direct extension of this repo.

---

## Ranked top 5–6 highest-impact, still-open questions

1. **Multimodal intraoperative-to-postoperative outcome prediction** (Theme 6): does a frozen EEG foundation model on HEEDB — alone or fused with hemodynamic/ventilator data — predict postoperative delirium/AKI/MINS/mortality better than single-modality models and replicate across a held-out hospital, a combination and an external-validation bar nothing in the 2023–2026 literature has yet cleared.
2. **EEG-derived prediction of postoperative delirium beyond processed indices** (Theme 2): does raw-EEG representation learning beat burst-suppression-ratio/BIS-style summary features for delirium prediction, externally validated beyond DELPHI-EEG's single-center result — the most direct, already-half-answered precursor to #1.
3. **Independent arbitration of the Hypotension Prediction Index controversy** (Theme 5): on a fully independent, non-Edwards dataset, does arterial-waveform morphology predict hypotension beyond simple MAP-trend extrapolation, and does the answer change once the Enevoldsen/Vistisen selection-bias critique is corrected for — a live, citable methodological fight with two 2026 meta-analyses already showing no hard-outcome benefit from acting on HPI.
4. **The right exposure metric for intraoperative hypotension** (Theme 1): is time-weighted "dose" of hypotension, nadir depth, or blood-pressure variability the strongest/most actionable predictor of AKI and MINS, now that two adequately-powered 2023–2025 trials (POISE-3, IMPROVE-multi) have ruled out naive threshold-individualization as the answer.
5. **Causal status of intraoperative burst suppression** (Theme 2): is burst suppression a cause of postoperative delirium or merely a marker of an already-vulnerable brain — unresolved by any 2023–2026 causal-inference study and directly relevant to whether EEG-guided titration could ever work.
6. **Does correcting NIRS-detected cerebral desaturation change outcomes in noncardiac surgery** (Theme 7): the only adequately-targeted RCT (Bieze 2025) was underpowered and null, leaving open which intervention, if any, converts a detected desaturation event into a patient-centered benefit.
