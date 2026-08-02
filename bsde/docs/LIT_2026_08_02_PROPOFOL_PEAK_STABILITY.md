# Literature check: "Propofol alpha peak frequency is dose-invariant; sevoflurane slows monotonically with dose"

*2026-08-02. Pre-registration/analysis-stopping literature check, per instruction. All PMIDs below were
retrieved and verified via `eutils.ncbi.nlm.nih.gov` (esearch/esummary/efetch) using `curl`, never WebFetch.
Full text was pulled via `efetch db=pmc` where the publisher permits NCBI to redistribute it (Frontiers
papers below); PNAS/Anesthesiology/Anesth Analg full text is blocked from bulk XML export by the publisher
("This publisher does not allow downloading of the full text in XML form") and only the MEDLINE abstract
was available for those — noted per-citation below.*

## (a) Verdict: **PARTIALLY PUBLISHED — and the published half runs against the hypothesis's premise, not for it**

The sevoflurane/volatile half of the sentence (monotonic slowing with dose) is already directly,
quantitatively established. The propofol half (frequency invariance across dose) is **not** established as
stated — and the closest existing evidence, a secondary characterization of Purdon et al. 2013 by an
independent group, plus a mean-field modeling line descending from Ching/Cimenser/Purdon/Brown, both point
the **opposite** direction: propofol's frequency is reported to *fall with depth and then plateau at a floor*,
not to sit flat across the range. Nobody has published a clean within-drug regression of periodic/aperiodic-
decomposed alpha peak frequency against propofol effect-site concentration across the clinical range — that
specific measurement is the open, testable piece, and it is narrower than the sentence as given. This is not
a "the line stops" result; it is a "the premise needs re-stating before it is tested" result.

---

## (b) Evidence per item

### 1. Propofol alpha peak frequency versus DOSE

**No direct dose-response regression of periodic-component alpha peak frequency against propofol
concentration was found.** Every propofol study located either (i) reports **power**, not frequency, across
dose steps, or (ii) reports frequency only as a transition-tracking variable during induction/emergence, not
as a function of a titrated concentration across the maintenance range.

- **PMID 33060553** (Gutiérrez et al., *J Neurosurg Anesthesiol* 2022) — a genuine propofol dose-step design
  (LOC → middle-dose → burst suppression, n=16): *"Peak alpha power was significantly higher during the LOC
  (5.4±2.6 dB) compared with middle-dose (2.6±3.6; P=0.04) and BS (0.7±3.2; P=0.0002) steps."* **No peak
  frequency value is reported anywhere in this paper** — "peak alpha power," not peak alpha *frequency*, despite
  the similar name. Not evidence either way on the frequency question.

- **PMID 23487781** (Purdon et al., *PNAS* 2013, "Electroencephalogram signatures of loss and recovery of
  consciousness from propofol") — the classic induction/emergence dose-ramp study. Its own abstract states:
  *"The median frequency and bandwidth of the frontal EEG power tracked the probability of response to the
  verbal stimuli during the transitions in consciousness."* This is a transition-tracking claim (does median
  frequency predict responsiveness during the LOC/ROC crossing), not a report of frequency's value as a
  function of concentration in steady maintenance. Full text was not retrievable (PNAS blocks bulk XML
  export from PMC), so I cannot check its figures for a concentration-frequency curve directly.

- **The clearest available characterization of what Purdon 2013 actually shows comes from a different,
  independent group's paper** — **PMID 28611600** (Hight, Voss, García, Sleigh, *Front Syst Neurosci* 2017),
  full text obtained (open-access, PMCID PMC5446988). Quoting directly:
  > *"The frequency of the alpha oscillation shifts according to anaesthetic concentration, as observed by
  > Long et al. (1989) and more recently by Purdon et al. (2013). **The latter work shows that with propofol,
  > the spectral median, a close approximation to peak frequency, reaches a lower frequency limit during
  > deeper stages of anesthesia.**"*
  and, more explicitly, contrasting propofol against volatiles:
  > *"alpha frequency does not seem to reach a lower frequency bound under volatile based anesthesia, as it
  > does with propofol (Purdon et al., 2013)."*
  **This is the single most load-bearing sentence found in this search, and it says the opposite of the
  hypothesis's premise**: propofol's frequency is characterized here as decreasing with depth and then
  *saturating at a floor* — not as staying flat across the clinical range. Caveat, flagged per rule 42: this
  is Hight et al.'s own interpretation/paraphrase of Purdon 2013's spectral-median results, not a sentence
  from Purdon 2013 itself (Purdon's own abstract does not use the words "lower frequency limit"). It is a
  secondary source's reading of a primary result I could not independently pull in full text. It should be
  treated as strong but not primary-sourced evidence.

- **Modeling literature agrees with Hight's characterization, not with the hypothesis.** **PMID 33316393**
  (Noroozbabaee, Steyn-Ross, Steyn-Ross, Sleigh, *NeuroImage* 2021 — an extension of the Hindriks & van Putten
  2012 thalamocortical mean-field model for propofol) states in its own abstract:
  > *"the revised model shows **a decrease in the intensity and frequency of alpha-band fluctuations**,
  > transitioning to delta-band dominance, **with deepening anesthesia**. These predicted **drug
  > concentration-dependent** changes in EEG dynamics are consistent with clinical reports."*
  This is an explicit model prediction of propofol dose-dependent alpha slowing, claimed (not demonstrated in
  the abstract with a citation) to match "clinical reports." It directly contradicts "does not change with
  dose."

- **PMID 41698186** (Sepúlveda et al., *Anesth Analg* 2026) — a genuine propofol dose-response/perturbation
  study (n=23) testing Eleveld PKPD model predictions around a burst-suppression episode. It reports BIS,
  alpha **power**, and delta-alpha phase-amplitude coupling before/after a pharmacological perturbation, but
  **no peak frequency value**. Its finding — that alpha power and phase-amplitude coupling show hysteresis
  (do not return to baseline despite effect-site concentration returning to baseline) even though BIS also
  fails to return — is a caution that propofol's spectral state is not a simple function of instantaneous
  concentration at all, which complicates a clean "X versus dose" framing for *any* propofol EEG feature,
  frequency included.

- **PMID 12163794** (Theilen et al., *Crit Care Med* 2002, ICU sedation at constant Ramsay-3 level over
  48 h) is tangential but relevant as a caution: *"Relative power of beta- and alpha-wavebands showed a
  constant and significant decrease over time... relative delta power increased... spectral edge frequency
  90 and 95 and spectral median frequency decreased significantly"* **despite constant clinical depth** and a
  propofol plasma concentration that was itself rising over part of that window. This shows spectral
  *summary* frequency measures (median, SEF90/95 — not the alpha peak specifically) fall over time in
  propofol sedation, entangling duration and concentration. It is evidence that propofol's frequency content
  is not simply flat, but it measures broadband summary statistics, not the alpha peak itself, so it does not
  directly speak to "peak frequency."

**Searches that specifically returned nothing for this item:**
`propofol AND "alpha peak frequency" AND "dose-response"` (0), `propofol AND "individual alpha frequency"`
(0), `propofol AND "peak frequency" AND "clinical range"` (0), `propofol AND "MAC-equivalent" AND alpha AND
frequency` (0), `Cimenser A[Author] AND propofol AND (dose OR concentration) AND frequency` (0).

### 2. Direct propofol-versus-volatile comparisons of peak frequency

**PMID 42131603** (Shen, Da, Shen, *Front Med* 2026, already known to the project) is confirmed via full text
(PMC13161752, open access, retrieved in full) to be a **snapshot**, not a dose-response contrast. Its own
Limitations section states outright:
> *"the retrospective dataset did not provide detailed anesthetic concentration data (e.g., MAC or TCI
> targets), **limiting the ability to standardize pharmacological depth**. While the analysis was strictly
> confined to the steady-state maintenance phase to approximate functional equivalence, it cannot be ruled
> out that the observed spectral differences may partly re[flect uncontrolled depth]."*
and calls, in its own future-directions paragraph, for exactly the design this project is contemplating:
> *"future prospective studies utilizing age-matched cohorts and controlled anesthetic concentrations are
> necessary to confirm the generalizability of these neural signatures."*
Reported numbers: alpha peak frequency **8.78 Hz (sevoflurane) vs 10.88 Hz (propofol)**, n = 44 (27 propofol,
17 sevoflurane).

**A second, independent snapshot comparison exists and was not previously known to the project: PMID
40327549** (Dragovic, Ostertag, Baumann, García, Kratzer, Schneider, Schwerin, Sleigh, Kreuzer, *Anesth Analg*
2026, "Spectral Differences of Anesthetic Agents"). n = 108 (fluranes vs propofol), **also a snapshot** —
"at clinically guided hypnotic and analgesic levels," not a titrated dose series. Quantitatively (two
decomposition methods, two SEF sub-ranges):
> *"'Fitting oscillations & one-over-f' produced a 2.04 Hz higher center frequency (AUC 0.82 [0.72–0.91],
> P<.001) in the propofol group (10.6 Hz [9.8–11.3]) compared to the flurane group (8.56 Hz [8.02–9.69])."*
Shen 2026 explicitly cross-cites this paper (as "Dragovic et al., ref 43") and notes the near-identical
numbers: *"the fact that the alpha peak in the older Sevoflurane group (8.78 Hz) is nearly identical to their
age-matched sevoflurane group (8.56 Hz) suggests that the observed downshift reflects a pharmacological
effect of sevoflurane beyond what would be expected from age alone."* — i.e., the two snapshot papers
corroborate each other's magnitude but neither is a dose-response design, and Shen 2026's own text flags this
as an open question requiring a **future, concentration-controlled** study.

**No paper found reports a propofol-vs-volatile comparison as a function of matched, titrated dose or
potency (e.g., matched MAC-equivalent steps).** The closest is Hight et al. 2017 (item 1, above), which ran
a real concentration-response regression **but excluded propofol patients from the cohort entirely**
("10 excluded as they received a non-volatile based anesthesia (propofol)") — it is a volatile-only dose
series with a propofol observation imported secondhand from Purdon 2013's transition data, not measured on
the same cohort or protocol.

**Searches that returned nothing:** `propofol AND sevoflurane AND "matched potency" AND EEG` (0).

### 3. Age-related alpha peak slowing under anaesthesia (competing explanation)

This is well documented and sizable, both under propofol and under volatiles, and should be treated as a
real confound for any between-patient aetiology-style comparison.

- **PMID 26174300** (Purdon et al., *Br J Anaesth* 2015, "The Ageing Brain," n=155: propofol n=60,
  sevoflurane n=95). Abstract, quoted directly: *"In elderly compared with young patients, alpha power
  decreased more than slow power, and **alpha coherence and peak frequency were significantly lower**."*
  This is pooled across propofol and sevoflurane in the abstract; full text was not retrievable via efetch
  (PNAS-style publisher block did not apply here — this is BJA/Elsevier and it *also* blocked bulk XML;
  confirmed by the "does not allow downloading of the full text" marker), so I could not confirm whether the
  peak-frequency effect is reported separately by drug in the body text, nor extract its numeric size
  directly from this source.

- **The numeric size comes secondhand, via Hight et al. 2017's citation of it, and is drug-specific
  (sevoflurane):** *"A decrease in alpha frequency under sevoflurane anesthesia with increasing age has been
  previously noted by Purdon et al. (2015a) who observed **a 0.5 Hz slowing between the group means of young
  (18–38 years) and elderly (70–90 years) patients** who all received approximately 1 MAC when age-adjusted."*
  Flagged as a secondary citation, same caveat as item 1.

- **Hight et al. 2017's own primary data (volatile only, n=305) independently measured the same effect and
  separated it from dose**, which is the strongest single piece of evidence on this item:
  > *"Increasing age was associated with decreased sensitivity to volatile anesthesia concentrations, and
  > with decreased alpha frequency, which sometimes transitioned into the theta range (5–7 Hz)... **The
  > alpha oscillation becomes slower with increasing age, even when the decreased anesthetic needs of older
  > patients were taken into account.**"*
  And, mechanistically, on why the *slope* itself changes with age, not just the intercept:
  > *"the sensitivity of the frequency change to anesthetic concentration also decreases with age, i.e., the
  > concentration-response slopes become less steep with increasing age."*
  This means age is a confound on **two** axes for any between-patient design: the baseline frequency, and
  the *responsiveness* of frequency to dose — both matter if age is not tightly matched between arms.

- **Hindriks & van Putten's population, as characterized by Hight et al. 2017, gives a population-specific
  anchor for propofol**: *"Hindriks and van Putten (2012) noted that when giving a propofol anesthetic for
  cardiac surgery (which involves mostly older patients) **peak alpha frequency was slower than the classic
  8–12 Hz band**, and chose 6 Hz as the lower frequency bound for alpha power."* This is again a secondary
  paraphrase (I could not retrieve Hindriks & van Putten 2012's full text; PMID 22394672's own abstract does
  not mention this age/frequency detail).

- **Developmental (paediatric) direction is opposite in sign and worth naming as a non-monotonicity**:
  Purdon-group paediatric papers (PMID 28657957, *Anesthesiology* 2017, "A Prospective Study of Age-dependent
  Changes in Propofol-induced EEG Oscillations in Children"; PMID 29988455, autism-spectrum children) were
  found in the search but not read in full for this check — flagged only as evidence that the age-frequency
  relationship under propofol is known to be studied across the *whole* lifespan, not just the aging-adult
  end, so "age-related slowing" is not a single monotonic line from birth to 90.

- **Two propofol-specific age papers found report POWER, not frequency, and should not be over-read as
  peak-frequency evidence:** PMID 40364055 (Kim et al. 2025, TCI matched at Ce 3.0 µg/mL across young/old)
  found *"alpha power remained stable across age groups despite the differences in drug delivery"* — power,
  not frequency, and directly contradicts nothing here since it is a different variable. PMID 32108685
  (Kreuzer et al. 2020, sevoflurane, n=180) similarly found *"no significant impact of age on relative alpha
  [power]"* (AUC 0.52) while entropy measures did shift with age — again power/entropy, not the peak
  frequency location itself.

### 4. The Purdon/Brown/Ching/Cimenser thalamocortical/anteriorization literature

**No paper in this lineage states peak-frequency stability with dose explicitly — it is at most an unstated
assumption, and where the mechanism is made explicit (via a lineal descendant of Hindriks & van Putten rather
than the Purdon/Brown/Ching line itself), the *opposite* is asserted.**

- **PMID 21149695** (Ching, Cimenser, Purdon, Brown, Kopell, *PNAS* 2010, "Thalamocortical model for a
  propofol-induced alpha-rhythm") — the foundational model. Abstract available only; states the model
  reproduces "persistent and synchronous α-activity" at doses sufficient for LOC but says nothing in the
  abstract about how the rhythm's frequency should behave as dose increases further. Full text blocked from
  bulk export ("does not allow downloading of the full text in XML form" — confirmed on this PMCID).

- **PMID 23825412** (Vijayan, Ching, Purdon, Brown, Kopell, *J Neurosci* 2013, "Thalamocortical mechanisms
  for the anteriorization of α rhythms") — explains the spatial (posterior→anterior) shift via GABA_A
  potentiation and reduced I_h, not the frequency-vs-dose question. Abstract only; no frequency-dose
  statement.

- **PMID 36897972** (Weiner, Zhou, ... Purdon, *PNAS* 2023) — the most recent paper in this exact lineage,
  using human intracranial recordings; concerns the spatial/network identity of anteriorization (which
  thalamic nuclei connect to which anteriorized regions), not frequency's dependence on dose. Abstract only.

- **The one place a frequency-dose mechanism is stated explicitly comes from a different, non-Purdon
  modeling lineage that nonetheless descends from the same physiological premise (GABA_A-kinetics-sets-
  rhythm-timescale) that Ching/Vijayan/Purdon's models also use**: Hindriks & van Putten 2012 (PMID 22394672,
  abstract only, no explicit frequency-dose statement found) and its 2021 re-analysis, PMID 33316393
  (quoted fully in item 1), which explicitly predicts propofol alpha frequency **decreases** with dose. Since
  the mechanism (prolongation of the GABA_A-mediated inhibitory post-synaptic potential sets the network's
  oscillation timescale) is shared with the Ching/Vijayan models, and prolonging an inhibitory time constant
  is a textbook way to slow a network's characteristic frequency, **the physiological assumption underlying
  the whole modeling tradition points toward dose-dependent slowing, not invariance** — this project's
  premise would need to argue why propofol's alpha generator is an exception to a mechanism its own reference
  models rely on for other predictions (anteriorization, burst suppression onset).

**Searches that returned nothing for this item:** none of the direct searches (`Purdon PL[Author] AND
propofol AND alpha`, count 17; `Hindriks R[Author] AND van Putten MJ[Author] AND propofol`, count 1) failed
outright, but none of the 17+ hits in the Purdon lineage state frequency-dose stability, so the absence is in
the *content*, not the search yield — logged as UNADDRESSED rather than a failed search.

---

## (c) What is novel and what is not, if treated as PARTIALLY PUBLISHED

**Not novel:** that sevoflurane/volatile alpha peak frequency slows with increasing anesthetic concentration.
Hight et al. 2017 measured this directly and quantitatively in 305 patients with fitted concentration-response
curves, in ~90% of patients. Also not novel: that age slows alpha frequency under anaesthesia (both drugs,
with at least one specific number — 0.5 Hz young-vs-elderly under sevoflurane at matched age-adjusted MAC —
already in print), and that age additionally *flattens the dose-response slope itself*, which is a second and
separate confound this project would need to control for, not just a level shift.

**Novel, if it holds:** a *direct, within-drug, concentration-titrated* regression of periodic-component
("FOOOF"-style) alpha peak frequency against propofol effect-site/plasma concentration, spanning the clinical
range, run on the same cohort/protocol as an equivalent volatile-agent series — i.e., exactly the
"controlled anesthetic concentrations" study that Shen et al. 2026 itself calls for in its limitations
section. That measurement does not exist yet in the literature searched here.

**Working against the hypothesis as currently stated, and this is the important part:** the one place an
existing source characterizes propofol's frequency behavior across depth (Hight et al. 2017's reading of
Purdon 2013), and the one explicit model prediction found (Noroozbabaee et al. 2021's extension of Hindriks &
van Putten), **both describe propofol frequency as decreasing with depth**, differing from volatiles only in
*where it stops* (a floor around a lower bound, versus volatiles which "seamlessly" continue into the theta
range with no apparent floor). If that characterization holds up under direct examination, the correct
registered hypothesis is not "propofol is flat, sevoflurane slopes" but something like "propofol's alpha
peak frequency saturates at a floor within the clinical range while sevoflurane's does not" — a materially
different and more specific claim, and one that argues for measuring **where propofol's dose-response curve
plateaus**, not for treating propofol as a flat reference condition.

## (d) Searches that returned nothing (full list)

- `propofol AND "alpha peak frequency" AND "dose-response"` — 0
- `propofol AND "individual alpha frequency"` — 0
- `propofol AND "peak frequency" AND "clinical range"` — 0
- `propofol AND "MAC-equivalent" AND alpha AND frequency` — 0
- `propofol AND sevoflurane AND "matched potency" AND EEG` — 0
- `Cimenser A[Author] AND propofol AND (dose OR concentration) AND frequency` — 0

## Full PMID list verified this session (via eutils esearch/esummary/efetch, curl only)

42131603, 40327549, 28611600, 26174300, 25233374, 23487781, 23825412, 21149695, 36897972, 22394672, 33316393,
33060553, 41698186, 40364055, 40655488, 32108685, 12163794, 35721144, 38105166 (retracted, not used as
evidence), 34677164.
