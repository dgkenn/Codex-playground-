# Literature check — "detects the transition before the conventional monitor" (Challenge C, BIS as comparator)

*2026-08-02. Pre-registration/analysis gate. No data touched. All citations verified live via NCBI
E-utilities (`eutils.ncbi.nlm.nih.gov`, esearch/esummary/efetch, curl), never WebFetch (rules 25, 39).
Raw XML/JSON/text of every query and every fetched record is retained in the scratchpad this session
ran from, in case a citation needs re-verification.*

**Target sentence under test:** *"A spectral EEG measure computed from the raw signal detects the
transition into and out of anaesthesia earlier than BIS, the deployed depth-of-anaesthesia monitor."*

---

## (a) One-line verdict

**PARTIALLY PUBLISHED.** The premise (BIS lags a true state change, by a well-characterized amount) is
thoroughly established. The specific empirical claim (a raw/derived spectral measure demonstrably beats
BIS on timing, not just accuracy) has been published **once**, on a small single-center cohort, in one
transition direction only, with a feature-selection procedure that has a plausible circularity concern —
and it has not been replicated on a large multi-site cohort such as VitalDB. **The "earlier detection"
framing is not absent from the field** — it is a live, actively worked idea (a directly-on-point paper
using VitalDB itself for EEG-based transition *prediction*, motivated explicitly by BIS's lag, appeared
in June 2026) — but no one has yet run the disciplined version of this project's exact comparison
(simple spectral measure vs. BIS, timing as the primary outcome, both directions, large N, proper
placebo/controls per this project's own error catalogue). That gap is real and is the opportunity.

---

## (b) The BIS lag figure — this is the bar any candidate must beat

**Primary source: Pilge S, Zanner R, Schneider G, Blum J, Kreuzer M, Kochs EF. "Time delay of index
calculation: analysis of cerebral state, bispectral, and narcotrend indices." Anesthesiology. 2006
Mar;104(3):488-94. PMID: 16508396.**

Quote (from the abstract, verified via efetch):

> "RESULTS: Time delays between 14 and 155 s were found for all indices. These delays were not
> constant. Results were different for decreasing and increasing values and between the full-step and
> the stepwise approaches. Calculation time depended on the particular starting and target index value."

Method: artificially generated EEG signals producing step transitions between "awake," "general
anesthesia," and "deep anesthesia" states, replayed into the monitors; time-to-adapt measured directly.
**This is a synthetic/simulated-signal design, not real patients** — flagged explicitly because it bears
on how much weight the number carries.

**Replication on real EEG: Zanner R, Pilge S, Kochs EF, Kreuzer M, Schneider G. "Time delay of
electroencephalogram index calculation: analysis of cerebral state, bispectral, and Narcotrend indices
using perioperatively recorded electroencephalographic signals." Br J Anaesth. 2009
Sep;103(3):394-9. PMID: 19648154.**

Quote:

> "RESULTS: We found time delays for all indices between 24 (7) and 122 (23) s before the new state was
> indicated... these time delays were not constant and depended on the particular starting and target
> index value. Results were different for decreasing and increasing values."

Same group, same method, but replayed **perioperatively-recorded real EEG** (awake / general anaesthesia
/ cortical suppression) instead of synthetic signals. This is the stronger of the two numbers for setting
a bar: **~24–122 s**, asymmetric by direction of transition.

**Third instalment, different monitors (State Entropy, Index of Consciousness), same design:
Kreuzer M, Zanner R, Pilge S, Paprotny S, Kochs EF, Schneider G. "Time delay of monitors of the hypnotic
component of anesthesia: analysis of state entropy and index of consciousness." Anesth Analg. 2012
Aug;115(2):315-9. PMID: 22584557.**

Quote:

> "Time delays were not constant and ranged from 18 to 152 seconds. They were also different for
> increasing and decreasing values. Time delays were dependent on starting and target index values."

**Fourth instalment, extending to qCON: Zanner R, Schneider G, Meyer A, Kochs E, Kreuzer M. "Time delay
of the qCON monitor and its performance during state transitions." J Clin Monit Comput. 2021
Apr;35(2):379-386. PMID: 32040794.**

Quote:

> "The delays for the important transition between awake/sedation and adequate anesthesia were 21(5) s
> from awake/sedation to adequate anesthesia and 26(5) s in the other direction... Time delay and
> performance during state transitions of the qCON were similar to other monitoring systems such as
> bispectral index."

**Bar to set, stated plainly:** the literature converges on BIS-family monitors needing **roughly
20–160 seconds** to reflect a step change in the underlying EEG state, with the number depending on
transition direction (ascending vs. descending) and how far the index has to travel — this is not a
single constant to beat, it is a **range conditioned on transition type**, which any registered design
must respect (rule 43-style: don't collapse this into one number).

**General/textbook confirmation this is a recognized limitation, not a niche finding:
Bowdle TA. "Depth of anesthesia monitoring." Anesthesiol Clin. 2006 Dec;24(4):793-822. PMID: 17342965.**

Quote:

> "Data processing time produces a lag in the computation of the depth-of-anesthesia monitoring index."

Listed alongside EMG artifact and drug-coverage gaps as one of the standard, textbook-level limitations
of BIS-class monitoring.

---

## (c) Per-item evidence

### Item 1 — BIS processing delay / lag: quantified, see (b) above.

Four independent papers from one group (Munich: Pilge, Zanner, Kreuzer, Kochs, Schneider), spanning
2006–2021 and covering CSI/BIS/Narcotrend (2006, 2009), State Entropy/Index of Consciousness (2012), and
qCON (2021), all using the same replay-a-known-transition design. **Delay is well characterized: ~20 to
~160 s, asymmetric by direction.** This closes item 1 decisively — the lag is not an open question.

### Item 2 — Direct comparisons of a raw/spectral measure against BIS for TIMING (not agreement)

This is where the field is thin, and where the one load-bearing hit lives:

**Ra JS, Li T, Li Y. "A novel spectral entropy-based index for assessing the depth of anaesthesia."
Brain Inform. 2021 May 12;8(1):10. PMID: 33978842. PMCID: PMC8116386 (open access, full text pulled).**

Abstract quote:

> "In addition, the proposed index shows an earlier reaction than the BIS index when the patient goes
> from deep anaesthesia to moderate anaesthesia, which means it is more suitable for the real-time DoA
> assessment."

Full-text quote (Results, quantified):

> "The new proposed index shows a high correlation with the BIS throughout the states of consciousness,
> light anaesthesia and deep anaesthesia. It shows an earlier reaction than the BIS index when the
> patient [goes] from deep anaesthesia to moderate anaesthesia. This type of earlier reaction exists in
> all the cases of the 14 subjects... Comparing with the new index, BIS values show an average 158 s time
> delay of anaesthetic states changes for 14 patients."

Table 3 (per-patient lead time in seconds, n=14): range **6 to 331 s**, mean **158 s**.

**This is the closest existing precedent to the target sentence, and it is a genuine partial hit.**
Method: EEG split into 10 frequency sub-bands (α, β1–β4, β, βγ, γ, δ, θ); spectral entropy computed per
band; the two bands whose entropy correlated best with BIS (beta-gamma, R²=0.8458; beta, R²=0.7312) were
combined into a novel index; that index was then shown, on the same 14 patients, to react earlier than
BIS during a deep→moderate anesthesia transition (i.e., **emergence direction only** — ascending BIS).

**Why this doesn't fully close the question, and what would need to differ in a registered design here:**
- **n = 14** usable patients (24 total, single center, Toowoomba, Australia). Small.
- **One transition direction only** (deep→moderate). The Pilge/Zanner series established BIS's delay is
  *asymmetric by direction* — nothing here speaks to induction (awake→anaesthetized).
- **The candidate index was tuned by correlating against BIS first**, then tested for lead time against
  the same BIS. That is not automatically circular (correlation-in-level and lead-in-time are different
  properties), but it is exactly the kind of construction this project's rule 60 asks to be checked
  against: has anyone verified the "earlier reaction" isn't simply an artifact of picking narrower,
  less-smoothed frequency content than BIS's own (documented, asymmetric) smoothing algorithm produces —
  i.e., is this a genuine physiological lead, or a mechanical consequence of comparing a less-smoothed
  quantity to a more-smoothed one? The paper does not address this, and it is exactly the sort of
  question a downstream registration here should ask before claiming novelty is closed.
- **No placebo/negative control** in the rule-40/rule-79 sense of this project. No permutation test, no
  synthetic system with a known true lead time, no report of a false-positive rate.
- **Not replicated.** Six PubMed-indexed citations exist (checked via elink `pubmed_pubmed_citedin`); none
  of them re-tests or extends the timing claim — they cite it for its entropy methodology
  (e.g., a 2024 entropy-methods review, a 2024 seizure-prediction feature-selection paper), not its
  latency finding.

**Entropy/PSI/Narcotrend vs. BIS literature more broadly** (query set on state/response entropy vs. BIS,
Patient State Index vs. BIS, Narcotrend vs. BIS — PMIDs 21512777, 19945300, 30625900, 16368823, 12456436,
12401620, and the Cochrane review 26976247) is uniformly about **agreement/correlation and clinical
outcome** (time to awakening, drug consumption, recall) — **never about which monitor reacts first.**
The Cochrane review on spectral entropy (PMID 26976247) is representative: its stated objectives are
"faster recovery," "recall," "amount of anaesthetic drugs," "cost," "time to PACU readiness" — timing of
*detection* is not one of the outcomes the field asks about in RCT-level evidence. This corroborates
item 4 below.

### Item 3 — LOC/ROC detection latency against a behavioural/clinical marker

**Nothing found that times EEG-index detection of loss/return of consciousness against a behavioural
marker (e.g., loss of eyelash reflex, verbal responsiveness) in seconds, in the sense the brief asks
for.** Searches combining "loss of consciousness"/"loss of responsiveness"/"return of responsiveness"
with EEG, BIS, timing, latency, and "seconds before" returned either nothing or off-topic hits (checked
and discarded: PMID 30925309 is a cortical-response-variability attention study, PMID 27885969 is a
conference-abstracts compilation).

One tangentially relevant hit: **Fernández-Candil JL et al. "Predicting unconsciousness after propofol
administration: qCON, BIS, and ALPHA band frequency power." J Clin Monit Comput. 2021
Aug;35(4):723-729. PMID: 32409934.** This times **alpha anteriorization** (a spatial EEG signature)
relative to loss of consciousness, and computes Pk (predictive) values for BIS/qCON/alpha power — closer
to a *prediction* framing than a *timing-race* framing, and does not report a lead time in seconds
against BIS. Not a hit for item 3, but adjacent and worth knowing about if a downstream design touches
alpha anteriorization.

### Item 4 — Is "earlier detection" a recognized claim, or does the field frame this as pure accuracy?

**Mostly the latter (accuracy/agreement), but the framing is not absent, and it is current.** Two
findings bear directly on this:

1. **The Cochrane review and the entropy-vs-BIS comparison literature (item 2) confirm the field's
   default framing is accuracy/agreement/clinical-outcome, not timing** — consistent with the brief's
   suspicion.

2. **A directly on-point counter-example exists and is very recent — on VitalDB itself:**
   **Kavuncu SK, Yalvac M, Basturk A. "A Multitask Time-Frequency Deep Learning Approach for Anesthesia
   Depth Monitoring and Transition Prediction." Diagnostics (Basel). 2026 Jun 22;16(12):1937.
   PMID: 42351597. PMCID: PMC13298125 (open access, full text pulled).**

   Uses **5,471 surgical cases from VitalDB**, dual-channel EEG, STFT + ResNet-SE deep network, to
   (a) estimate BIS continuously, (b) classify anesthesia state, and (c) **predict transitions toward
   light anesthesia 3/5/10 minutes ahead of the BIS-defined threshold crossing (BIS=60)**, reporting AUC
   0.94 / 0.91 / 0.85 respectively at those horizons. Full-text quotes:

   > "Current commercial indicators are largely closed-source and may reflect dynamic changes with some
   > delay." (Abstract)

   > "...index values are affected by complex brain changes during the deepening of anesthesia and
   > awakening, and calculation delays may occur [6,7]." (Introduction — ref [6] is the Park 2020
   > compute-speed paper, PMID 32746339; ref [7] is the Ra 2021 spectral-entropy paper above, PMID
   > 33978842 — so this paper explicitly builds on the same lead this check found.)

   > "There is a need to develop AI-supported systems capable of accurately monitoring brain activity and
   > predicting upcoming anesthesia-state transitions. These systems may support surgical safety by
   > providing earlier situational awareness regarding dynamic anesthetic shifts."

   > "Earlier identification of transitions toward light anesthesia may provide additional temporal
   > context for anesthetic management... This model extends conventional retrospective BIS estimation
   > by incorporating transition-oriented temporal risk analysis that allows for earlier and more
   > controlled anesthesia adjustments."

   **This establishes that the "earlier detection" framing is explicitly alive in the literature, on the
   exact dataset this project would use, as of June 2026** — the motivating premise, the dataset, and the
   "earlier situational awareness" framing are all already published. **What it does NOT establish is
   this project's specific claim.** Its ground-truth label for "transition" is **BIS crossing 60** —
   i.e., it forecasts BIS's own future value from current EEG, which is a claim about *predictability of
   BIS ahead of time*, not a claim that an independent, simply-computed spectral measure reacts to the
   *true* underlying state change before BIS does. Those are related but distinct claims (the same
   distinction rule 28 exists to prevent conflating): forecasting a lagging label is not the same as
   showing your own measure is not itself lagging. It also uses a complex multitask deep model, not a
   "spectral EEG measure" in the sense of the brief. **A one-line "comment" response to this paper was
   already published one week later** (J Anesth 2026 Jun 30, referenced in the record but not itself
   fetched/verified here as it wasn't load-bearing to this check) — worth knowing this is an active,
   contested area, not a settled one.

---

## (d) If PARTIALLY — what exactly is left novel

Given (b)+(c), the following remain genuinely open and would be the honest scope of a registration here:

1. **No large-cohort (VitalDB-scale), pre-registered, placebo-controlled test of "a simple spectral
   measure reacts to a true state transition before BIS does"** exists. The one paper that tested this
   (Ra 2021) did so on 14 patients, one direction, with no negative control and a construction (band
   selection tuned to BIS correlation) that has not been checked for the mechanical-smoothing confound
   described in (c).
2. **No test of BOTH directions** (induction AND emergence) in the same design — the BIS delay literature
   says the two are asymmetric, so a candidate that leads on one direction and not the other is exactly
   the failure mode rule 43/64-style controls in this project's catalogue are built to catch.
3. **No test using an independently-timed ground truth** rather than BIS's own threshold as the label —
   this project would need to define "the transition" independent of BIS (e.g., from a documented dose
   event or a behavioural marker) to avoid the label-shares-the-comparator problem the VitalDB 2026 paper
   has.
4. **No mechanistic control ruling out "less smoothing" as the entire explanation.** Given BIS's
   documented epoch/smoothing-driven delay (Pilge, Zanner, Kreuzer series), any candidate that is
   computed on a shorter window than BIS's internal smoothing will *mechanically* appear to lead it on a
   step change, regardless of anything neurophysiological — this needs to be the first thing a
   registration here rules out (compare the candidate's own delay against a matched-smoothing-window
   ablation), or the "earlier detection" result reduces to "our window is shorter than BIS's window,"
   which is engineering, not discovery.

Point 4 is the sharpest version of the opportunity and the sharpest version of the risk: it is exactly
the kind of thing rule 50 in this project's catalogue would flag — *measuring a difference is not
measuring its cause* — applied in advance, before any run.

---

## (e) Searches that returned nothing (recorded per instructions — absence is itself informative)

- `"loss of consciousness" AND EEG AND "before" AND "bispectral index" AND "change"` — 0
- `EEG index AND anesthesia AND "earlier detection" AND transition` — 0
- `"processed EEG" AND anesthesia AND lag AND monitor AND raw signal` — 0
- `burst suppression detection AND bispectral index AND delay` — 0
- `consciousness transition AND EEG AND latency AND monitor AND "real time"` — 0
- `deep learning AND EEG AND anesthesia depth AND real-time AND bispectral index AND lag` — 0
- `Brown Purdon Van Dort general anesthesia review EEG spectrogram bispectral index limitations` — 0
  (the MGH/Purdon spectrogram literature did not surface via these term combinations; if their reviews
  discuss BIS lag it was not found by this search and would need a separate pass by author name alone)
- `spectrogram AND anesthesia AND "real-time" AND "bispectral index" AND lag` — 0
- `"BIS" AND "averaging window" AND anesthesia depth` — 0
- `"loss of responsiveness" AND EEG AND "bispectral index" AND seconds AND before` — 0
- `"index of consciousness" AND "faster" AND "BIS" AND "detects"` — 0
- `"transition into" AND anesthesia AND EEG AND "before BIS"` — 0
- `"detect" AND "unconsciousness" AND EEG AND "faster than" AND monitor` — 0

None of these zero-hit searches is itself conclusive (PubMed indexing and phrase-matching are strict —
absence of an exact phrase match is weaker evidence than a topic search), but the pattern across all of
them is consistent with item 4's conclusion: **nobody has published this as a named, titled research
question** ("does X detect the transition earlier than BIS") outside the one Ra 2021 result and the one
VitalDB 2026 forecasting paper, both surfaced above by broader queries.

---

## Bottom line for whoever reads this before registering

- **Do not spend effort re-deriving that BIS lags** — cite Pilge 2006 / Zanner 2009 / Kreuzer 2012 /
  Zanner 2021 (PMIDs 16508396, 19648154, 22584557, 32040794) and move on. Bar: ~20–160 s, direction-dependent.
- **Do not present "raw spectral measure beats BIS on timing" as new** without engaging Ra 2021
  (PMID 33978842, 158 s mean lead, n=14, one direction) as prior art — it is small and un-replicated, not
  absent.
- **Do not ignore the VitalDB 2026 paper** (PMID 42351597) — it is on the exact dataset, motivated by the
  exact premise, and published seven weeks before this check. A registration here needs to say explicitly
  how it differs (independent ground truth vs. BIS-as-label; simple measure vs. deep multitask model; both
  transition directions; a smoothing-window-matched control) or it will read as a re-run.
- **The load-bearing missing control, if this line is pursued, is the smoothing-window ablation** (item
  (d)-4) — without it, "earlier" cannot be distinguished from "less smoothed," and that distinction is the
  entire scientific content of the claim.
