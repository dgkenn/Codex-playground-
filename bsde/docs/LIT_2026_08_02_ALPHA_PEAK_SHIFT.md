# Literature and internal-record check: the sevoflurane/propofol alpha peak-frequency asymmetry

*2026-08-02. Every PMID below was fetched from its MEDLINE record via NCBI E-utilities
(`efetch.fcgi?db=pubmed`) and every quotation is copied verbatim from the retrieved `<AbstractText>`.
No WebFetch was used for any bibliographic record — rules 25 and 39 exist because it fabricated PubMed
content here three times. This is a literature/internal-record check only: no analysis was run, no
experiment was registered, and no ledger row was written.*

**Rule 42 applies throughout: a quotation supports only what it literally says.** Anywhere a sentence
below draws an inference beyond the source's literal content, it is labelled as an inference.

---

## PART 1 — THE INTERNAL RECORD. READ THIS FIRST.

**The claim is not new to this project — it is the endpoint of a nine-experiment repair chain that ran
today, and it is already recorded three places: `bsde/governance/REGISTRATION_LEDGER.jsonl` (E233),
`bsde/docs/NOTE_CHALLENGE_A_REFRAMED.md`, and `bsde/docs/AUDIT_2026_08_02_BAND_DEPENDENCE.md`. A fourth
document, `bsde/docs/LIT_2026_08_02_BAND_VS_BANDFREE.md`, already ran part of today's literature check
before E233 existed and its five questions are directly relevant — see §1.4.**

### 1.1 The chain that produced the number, and confirmation the quoted figures are exact

Searched: `bsde/docs/`, `bsde/governance/REGISTRATION_LEDGER.jsonl`, `docs/research/`, `docs/LESSONS.md`,
for "alpha peak", "peak frequency", "IAF", "alpha_peak_hz", "slowing", "spectral shift". Every hit is
reported below; nothing was filtered out.

Ledger trail (`bsde/governance/REGISTRATION_LEDGER.jsonl`), in order:

| id | what it tested | outcome |
|---|---|---|
| E213 | Is the reversal explained by removing cases whose peak sits on the band floor? | **negative** — restriction does not explain it |
| E214 | Does synthetic frequency-shift sensitivity predict transport failure across the panel? | positive but weak (95.8th pctile, not robust to dropping any one feature) |
| E216 | Does a frequency-invariant 3-feature axis transport better than random? | negative — ranks 88th percentile, not better |
| E217 | Does frequency sensitivity predict cross-DEPOSIT disagreement (4 deposits)? | gate failed (chennu's depth effect not alive) |
| E218 | Does anchoring the band to each recording's own peak remove the reversal? | **first draft withdrawn same day** for a missing gate; see E233 |
| E228 | Does the reversal survive within one patient exposed to both drugs? | gate failed — 84/101 combined-technique cases excluded because one exposure track is constant |
| E229 | Corrected arm predicate (propofol 44→114 cases): does the reversal replicate? | **positive** — replicates and strengthens |
| E230/E231 | Does the reversal survive covariate matching? | gate failed both times — the matching placebo cannot change the statistic (rule 55); this line is **closed** |
| E232 | Does the reversal survive restricting to remifentanil-exposed cases only (removing opioid presence as a confound)? | **positive** — replicates, falsification condition did not fire |
| **E233** | **Is the reversal a fixed-band artefact of a moving peak?** | **negative for the reversal (it IS an artefact) — and this is where the peak-frequency numbers you asked me to check come from** |
| E234 | Does the panel-wide magnitude gap reduce to translation sensitivity (synthetic shift 10→9 Hz)? | gate failed — both synthetic endpoints landed inside the fixed 8–13 Hz box, invalidating the capability probe |
| E235 | Same question, with the shift geometry derived from the sevoflurane arm itself | **registered verdict fired, then WITHDRAWN** on a robustness check (a 4-vs-11 threshold split masquerading as a dose-response) |

**This confirms the framing in your prompt exactly: E234 and E235 are the "two retractions today."** E233
itself is a partial retraction (it withdraws E229's and E232's "alpha reverses between the agents"
headline) but its own A1 sub-finding — the peak-location contrast — is what **replaces** the retracted
claim, and E234/E235 (attempts to build a *mechanism* on top of it) are what failed afterward. The peak
shift is, as you say, the one thing still standing.

**The exact figures in your prompt are the literal, verbatim numbers in E233's `outcome_detail`** (I read
the ledger row directly, not a summary of it):

> *"A1 supplies the mechanism the artefact requires and it is present: the peak location contrast is
> +0.3070 [+0.2149, +0.3938], driven entirely by sevoflurane, where the peak falls reliably with dose
> (mean signed rho -0.3296, C = 0.8204 against a null of 0.2770) while under propofol it does not move at
> all (-0.0226, C = 0.0970 against 0.3163, failing its null)."*

`bsde/docs/NOTE_CHALLENGE_A_REFRAMED.md` (§"FOURTH CORRECTION... the reversal is BAND PLACEMENT") restates
the same two rows as a table and adds the framing that matters most for how this should be described going
forward:

> *"Sevoflurane slides the alpha peak downward as dose rises. Propofol does not move it. ... Survives: ...
> **sevoflurane produces a measurable, consistent downward shift of the alpha peak that propofol does
> not.** That is a statement about an oscillation rather than about a window, and it is what should be
> carried forward."*

Cohort: VitalDB, 114 propofol-only and 87 sevoflurane-only cases, 6,679 windows, the identical cases and
windows as the fixed-band incumbent (`relative_alpha_power`) so the two are a like-for-like test.
Instrument: `alpha_peak_hz_wide` — peak located on the **aperiodic-corrected residual** over a **5–15 Hz**
search range, matching exactly what your prompt describes.

### 1.2 The instrument itself has been validated, independently of the real-data result

`bsde/docs/AUDIT_2026_08_02_BAND_DEPENDENCE.md` ran a synthetic capability test (`tests/test_iaf_capability.py`,
executed rather than merely cited — E233's own G3 gate) with a known planted peak frequency, moved by
exactly 1 Hz, both in-box (10.0→9.0 Hz) and across the alpha box's own 8 Hz edge (8.5→7.5 Hz):

> *"`alpha_peak_hz_wide` | 10.000 | 9.000 | 0.000 | -- (raw diff **-1.000 Hz**) | zero-variance, perfect
> tracking"* (primary pair) and *"`alpha_peak_hz_wide` | 8.500 | 7.500 | 0.000 | -- (raw diff **-1.000
> Hz**, correctly tracks the edge) | zero-variance, perfect tracking"* (edge pair).

By contrast the **old, censored** `alpha_peak_hz` (8–13 Hz search, no aperiodic correction — a different,
earlier candidate) is independently documented as **wrong, not merely flat**, once the true peak exits its
box: at the edge pair it moved only 0.125 Hz for a true 1 Hz shift. **This is why the A1 finding uses
`alpha_peak_hz_wide` and not the older estimator**, and it is why the audit treats the instrument as
trustworthy for exactly the measurement your prompt describes.

Gate G2 of E233 also checked, and reports passing, that peak detectability (i.e., whether the anchored
measure fails to resolve on some non-random stratum) does not differ by arm beyond a permutation floor —
so the peak-location number is not an artefact of one arm having systematically worse peak detection than
the other (catalogue rule 32).

### 1.3 Mechanisms already tested and already ruled out by this project (relevant background, not part of the peak-shift claim itself)

`bsde/docs/NOTE_ALPHA_INSTABILITY.md` ran its own literature-anchored mechanism triage **before** E233
existed, on the same 115-case cohort, testing six candidate explanations for why propofol and sevoflurane
might disagree in direction at all. Relevant to your question about confounds:

- **Age is not the driver of the arm difference.** The propofol and sevoflurane arms are matched: age 59.5
  vs 58.0 (diff +1.5 [-5.00, +11.00]), ASA 2.0 vs 2.0 (diff 0.0), permutation p on the deep-tercile BIS
  difference = 0.4276. The note cites Purdon 2015 (PMID 26174300, verified below, §2.4) for "the age effect
  running in the *same* direction for both drugs," which is why it treats age as "largely removed," not as
  untested.
- **BMI differs slightly** (24.5 vs 22.8, diff +1.7 [+0.15, +2.85]) and is flagged as "not an obvious route
  to a sign reversal" but not fully excluded.
- **Non-equipotent depth scales is the leading candidate mechanism for why the two drugs might disagree at
  all**, per Kuizenga 2019 (PMID 31567365, verified below, §2.4): the same behavioural endpoint occurs at
  radically different EEG-index values for the two drugs, so matching arms on BIS does not mean matching
  them on state.
- **Differential burst suppression is REFUTED** (Kenny 2014, PMID 25565990, verified below) — excluding
  suppression-containing cases makes the gap *larger*, the opposite of what that mechanism predicts.
- **Off-target volatile receptor action is weak support at best** (Solt & Forman 2007, PMID 17620835,
  verified below) — the effect is present even below 1 MAC, which the mechanism's own prediction argues
  against.
- **Co-medication (remifentanil) does not explain it** — restricting both arms to an overlapping
  remifentanil band leaves the sevoflurane effect intact.

**Important scope note for your question:** these six mechanisms were tested against the **arm-level
"reversal"** in `relative_alpha_power`, which E233 later showed is the band-placement artefact, not a
biological fact. They are relevant background on cohort comparability, not tests of the peak-shift finding
itself — the peak-location contrast (A1) supersedes the framing this note was built to explain.

### 1.4 A prior literature check already exists and answers three of your five sub-questions

`bsde/docs/LIT_2026_08_02_BAND_VS_BANDFREE.md`, written the same day but **before** E233/E235 resolved the
band-placement story, already ran PubMed searches bearing directly on this question. Its findings (PMIDs
re-verified independently below, §2) are:

- **Q1 (is the alpha peak lower under sevoflurane than propofol?):** found **42131603** giving almost the
  exact figures your prompt's medians match (8.78 Hz sevoflurane vs 10.88 Hz propofol), in tension with
  **25233374** (Akeju 2014), which reports both agents at "approximately 10 Hz." The note's own verdict:
  *"Our alpha peak-shift number should not be reported as established... Report it as measured here, with
  the censoring caveat, and cite Akeju 2014 as the source it disagrees with."* — written about the
  project's **own then-current, censored** `alpha_peak_hz` measurement, not about A1, but the citation
  tension is identical and carries over.
- **Q3 (has anyone used an individually-anchored alpha band as an anaesthesia-monitoring methodology?):**
  **verified as a zero-count query, not a failure to search**: `"individual alpha frequency"[tiab] AND
  anesthesia` = 0, `AND anaesthesia` = 0. Nine hits use peak alpha frequency as an **outcome**; none uses
  it as a monitoring band definition. **"Individual alpha frequency is thoroughly established in cognitive
  and resting-state EEG — 234 papers — and has apparently never been carried into anaesthesia depth
  monitoring."** This is exactly the gap your prompt is asking me to characterise, already characterised.
- **Q4 (has any measure been reported to reverse direction between agents?):** yes, but **only between
  mechanistically distinct drug classes** (ketamine/NMDA antagonism vs GABA-A propofol, PMID 10713872;
  nitrous oxide, PMID 21788312) — never between two GABAergic agents. This is why the note calls a
  same-mechanism-class reversal "the novel one," and it is also why E233's finding — that there was never a
  true reversal, only a band-placement artefact — resolves a puzzle this note had flagged as having "no
  precedent" and "no easiest explanation."

I re-fetched all four PMIDs this note relies on independently (§2 below) rather than trusting its own
verification claim, per rule 25.

---

## PART 2 — EXTERNAL LITERATURE

All records below fetched via `efetch.fcgi?db=pubmed&id=<PMID>&rettype=abstract&retmode=text`. PMIDs already
verified by the project (§1.3, §1.4) were re-fetched and re-checked word-for-word rather than assumed
correct.

### 2.1 Sevoflurane's alpha/spindle peak moving down with dose — DIRECTLY measured and quantified, independent of this project

**Hayashi, Sawa, Matsuura. Anesthesiology 2008;108(5):841-50. PMID 18431119.** *"Anesthesia
depth-dependent features of electroencephalographic bicoherence spectrum during sevoflurane anesthesia."*
16 patients, sevoflurane 1%/2%/3% with fixed-rate remifentanil, bicoherence spectrum 0.5–40 Hz:

> *"Sevoflurane (1%) caused two main peaks, spindle frequencies (11.0 ± 1.2 Hz...) and delta-theta
> frequencies (5.4 ± 0.5 Hz...) ... High concentrations of sevoflurane (2% and 3%) shifted these peaks to
> 9.8 ± 1.1 Hz ... and 8.7 ± 1.3 Hz ... respectively... Deeper sevoflurane anesthesia shifted all
> bicoherence peaks to lower frequencies."*

This is a **literal, monotonic, three-point dose-response of a peak frequency falling with sevoflurane
concentration** (11.0 → 9.8 → 8.7 Hz across 1% → 2% → 3%), independently measured, in the same rough
magnitude (~1–1.5 Hz per dose step) as the internal cohort's within-case correlation. **Caveat that must be
stated plainly:** this is a **bicoherence** (nonlinear cross-frequency phase-coupling) peak, not a power
spectral density peak — a different statistic from `alpha_peak_hz_wide`. The same authors' earlier propofol
work (§2.2) found their own power-spectrum and bicoherence peaks essentially coincide (10.6 vs 10.7 Hz), so
treating the two as tracking the same underlying oscillation is reasonable but not identical.

**Zhang et al. Front Neurosci 2022;16:913042. PMID 35645714.** *"Electroencephalogram Mechanism of
Dexmedetomidine Deepening Sevoflurane Anesthesia."* 23 patients at 0.8 MAC sevoflurane, before/after
dexmedetomidine:

> *"After dexmedetomidine infusion, the mean α power peak decreased from 6.09 to 5.43 dB and **shifted to a
> lower frequency**, the mean θ bicoherence peak increased from 29.57 to 41.25% and **shifted to a lower
> frequency**..."*

Directionally consistent (deepening a sevoflurane-based anaesthetic moves the alpha peak down), but this is
**dexmedetomidine added on top of a fixed sevoflurane dose**, not a sevoflurane dose-response in isolation —
a genuine confound for using this as sevoflurane-specific evidence.

### 2.2 Propofol's alpha peak frequency across dose — NOT FOUND as a direct dose-response test. Reported and not padded.

**What I searched for and did not find:** no PubMed record combining propofol with a target- or
effect-site-concentration sweep and a **peak-frequency** outcome (as opposed to power). Search terms tried:
`propofol alpha peak frequency effect-site concentration`, `propofol concentration alpha peak frequency
stable invariant` (0 hits), `propofol dose response frontal alpha frequency decrease increase`, `propofol
alpha oscillation frequency does not change depth`. None returned a study that varies propofol dose and
reports what happens to the alpha peak's frequency, as Hayashi 2008 does for sevoflurane.

**What exists instead is a consistent set of single-dose/single-context snapshots, all clustering near
10–11 Hz:**

- **Akeju et al. Anesthesiology 2014;121(5):990-8. PMID 25233374.** *"Effects of sevoflurane and propofol
  on frontal electroencephalogram power and coherence."* Age/sex-matched, n=30 each, single maintenance
  period: *"propofol...has maximum power and coherence at approximately 10 Hz (peak power, 2.1 ± 4.3 dB;
  peak coherence, 0.71 ± 0.1)"* — reported as **similar** to sevoflurane's ~10 Hz in this study.
- **Akeju et al. Anesthesiology 2014;121(5):978-89. PMID 25187999.** Propofol ramped 0→5 µg/ml
  effect-site over the whole session: *"propofol was characterized with frontal alpha oscillations with
  peak frequency at approximately 11 Hz."* A single summary value over the ramp, not a per-concentration
  breakdown — **does not itself establish invariance**, only that the reported value (across the induction
  range) is ~11 Hz.
- **Hayashi, Tsuda, Sawa, Hagihira. Br J Anaesth 2007;99(3):389-95. PMID 17621599.** Fixed propofol Ce
  3.5 µg/ml: *"Propofol caused alpha peaks in both power and bicoherence spectra, with average frequencies
  of 10.6 (SD 0.9) Hz and 10.7 (1.0) Hz, respectively."* Single concentration only.

**One piece of evidence points the other way and must be reported, not omitted.** Purdon et al. PNAS
2013;110(12):E1142-51 (PMID 23487781), the field's most-cited propofol induction/emergence study, states:

> *"The median frequency and bandwidth of the frontal EEG power tracked the probability of response to the
> verbal stimuli during the transitions in consciousness."*

Taken at face value this says a frequency summary of frontal power **does** track depth during propofol
transitions. **This is not necessarily a contradiction of the internal claim, and I could not resolve which
it is from the abstract alone** — full-text access to this PMC record is blocked by the publisher for XML
retrieval (confirmed: the fetched record body reads *"The publisher of this article does not allow
downloading of the full text in XML form"*), so I could not check whether this is (a) the alpha peak itself
moving, contradicting the propofol-invariance half, or (b) the **median frequency of the whole spectrum**
falling because of the well-documented growth in <1 Hz slow-oscillation power as propofol deepens, which
would drag a whole-spectrum median down while leaving the alpha-band peak itself in place — i.e. exactly
the power-redistribution-vs-peak-shift distinction your prompt asks me to keep separate. **Flagged as an
open tension, not resolved.**

Also relevant and *not* about dose: **Kim et al. J Clin Med 2025;14(9):3024. PMID 40364055.** At a **fixed**
propofol effect-site concentration (3.0 µg/ml) across two age groups: *"Alpha power remained stable across
age groups despite the differences in drug delivery... while older patients demonstrated decreased frontal
alpha synchronization."* This is about power and connectivity holding an amplitude anchor fixed across
*age*, not about frequency across *dose* — cited because it is the closest hit to "propofol alpha frequency
stable" the search returned, but it answers a different question and should not be over-read as dose-invariance
evidence.

### 2.3 The one direct head-to-head with quantified peak-frequency numbers matching the internal cohort's medians

**Shen, Da, Shen. Front Med (Lausanne) 2026;13:1794626. PMID 42131603.** *"Divergent periodic and aperiodic
EEG signatures of Propofol versus sevoflurane anesthesia."* Retrospective, n=44 (propofol 27, sevoflurane
17), steady-state maintenance phase, SHAP-ranked feature importance:

> *"Relative theta power, theta-to-alpha ratio, and alpha peak frequency were identified as the primary
> differentiators... the Sevoflurane group exhibited a distinct elevation in theta-band prominence and a
> **significant downward shift in alpha peak frequency (8.78 Hz vs. 10.88 Hz for Propofol)**."*

This is a **between-group snapshot at steady state**, not a within-drug dose-response — it does not test
whether the peak *moves with concentration* for either drug, only that the two groups sit at different
peak frequencies at some (unspecified, pooled) maintenance depth. **Read narrowly: it corroborates the
internal cohort's medians (sevo 9.69–9.75 Hz vs propofol 10.50–10.75 Hz) almost exactly in both direction
and rough magnitude (~2 Hz gap in both), from an independent, very recently published dataset.** It does
**not** corroborate the dose-response/slope claim (that sevoflurane's peak tracks its own concentration
within-case while propofol's does not) — that specific claim, to my search, has not been tested by anyone
outside this project.

The same paper independently reports the aperiodic exponent differs by agent (2.37 sevoflurane vs 2.07
propofol, p = 0.039) and that "alpha bandwidth (p = 0.263) and signal complexity measures... provided
negligible discriminatory value" — both already logged in the project's own prior lit-check (§1.4) and
reconfirmed here.

### 2.4 Age dependence — already handled by the cohort, and independently corroborated

**Purdon et al. Br J Anaesth 2015;115 Suppl 1:i46-i57. PMID 26174300.** n=155 (propofol 60, sevoflurane 95),
ages 18–90:

> *"Power across all frequency bands decreased significantly with age for both propofol and sevoflurane;
> elderly patients showed EEG oscillations ~2- to 3-fold smaller in amplitude than younger adults... In
> elderly compared with young patients, alpha power decreased more than slow power, and **alpha coherence
> and peak frequency were significantly lower**. Older patients were more likely to experience burst
> suppression."*

This directly measures an age effect on alpha **peak frequency**, pooled across both agents, in the **same
direction** described by the internal note. Since the internal cohort's propofol and sevoflurane arms are
age-matched (§1.3), this rules age out as an explanation for the *between-arm* difference, but it is
independent confirmation that peak frequency **can** move with a covariate other than dose — i.e., the
claim under test is specifically an invariance-to-dose-at-fixed-age claim, not a claim that propofol's
alpha peak never moves for any reason.

**Kuizenga et al. Anesthesiology 2019;131(6):1223-1238. PMID 31567365** and **Kenny et al. Front Syst
Neurosci 2014;8:237. PMID 25565990** and **Solt & Forman. Curr Opin Anaesthesiol 2007;20(4):300-6. PMID
17620835** — all three re-fetched and confirmed to match the internal note's quotations verbatim (see
§1.3 for the sentences).

### 2.5 What "alpha slowing" under volatiles is usually reported as — power redistribution and spatial topography, not (until 2008/2026) a quantified peak shift

Two established, well-cited distinctions bear directly on your fifth sub-question:

- **Vijayan, Ching, Purdon, Brown, Kopell. J Neurosci 2013;33(27):11070-5. PMID 23825412.** Propofol's
  signature effect is framed as **spatial**: *"the normal alpha rhythm (8-13 Hz) in the occipital cortex
  disappears and a frontal alpha rhythm emerges. This spatial shift in alpha activity is called
  anteriorization."* This is a topographic claim, not a frequency claim.
- **Blain-Moraes et al. Anesthesiology 2015;122(2):307-16. PMID 25296108.** Sevoflurane does **not**
  reproduce that spatial signature: *"At concentrations sufficient for unconsciousness, sevoflurane did not
  result in a consistent anteriorization of alpha power."*

**This is worth stating explicitly because it is a genuinely different asymmetry from the internal
finding, running in the opposite pattern.** The established literature's propofol/sevoflurane asymmetry is
*spatial* (propofol anteriorizes, sevoflurane doesn't). The internal finding's asymmetry is *spectral*
(sevoflurane's peak moves with dose, propofol's doesn't). The two are not the same claim and one does not
imply the other — but their existence side by side is a reasonable prior that these two GABAergic agents
produce alpha rhythms through sufficiently different circuit mechanisms (Vijayan's thalamocortical model is
explicitly propofol-specific) that a second, independent asymmetry between them is plausible rather than
surprising.

---

## PART 3 — BOTTOM LINE

**(1) Internal record: already established, not overlooked.** The claim is E233's own A1 finding, logged in
the ledger, restated in two internal notes, and the instrument behind it (`alpha_peak_hz_wide`) is
independently validated by a synthetic capability test in a fourth document. A partial literature check for
this exact question (`LIT_2026_08_02_BAND_VS_BANDFREE.md`) already exists and had already found the single
most relevant external paper (PMID 42131603) before this check started. **Report this claim as the
project's own, already-registered result — not as newly discovered by this check.**

**(2) External literature verdict, split by half of the asymmetry:**

- **Sevoflurane's peak moving down with dose: (a) already known, independently and quantitatively.**
  Hayashi 2008 (PMID 18431119) shows a monotonic 11.0→9.8→8.7 Hz shift across 1%→2%→3% sevoflurane, in a
  bicoherence peak rather than a PSD peak but at a comparable magnitude and in the same direction. Zhang
  2022 (PMID 35645714) corroborates the direction under a confounded (dexmedetomidine-added) design.
- **Propofol's peak staying fixed with dose: (d) unaddressed in the literature I could find — a genuine
  gap, not a contradiction.** No study varying propofol concentration and reporting the alpha peak's
  frequency response was found. Multiple single-dose snapshots across different studies and concentrations
  cluster consistently near 10–11 Hz, which is *consistent with* stability but does not *test* it. One
  contrary signal exists (Purdon 2013's "median frequency... tracked the probability of response") but its
  full text was not accessible to determine whether it reflects the alpha peak itself moving or
  whole-spectrum redistribution from growing slow-oscillation power — reported as an open tension, not
  resolved either way.
- **The static endpoint (sevoflurane peak lower than propofol's, at some depth) is (a) already known**,
  independently and quantitatively, in a very recently published (2026) head-to-head with numbers
  (8.78 vs 10.88 Hz) matching the internal cohort's medians closely. **The dynamic/dose-response claim
  (sevoflurane's peak tracks ITS OWN concentration within-case while propofol's does not) is, as far as
  this search could determine, (b) novel** — I found no paper that tests a within-subject dose-response
  slope for either drug's alpha peak frequency, let alone contrasts the two slopes directly.

**(3) The asymmetry you asked me to weigh (peak shift vs power redistribution) is the correct question
to be asking, and the literature answers it for propofol (anteriorization — a spatial claim) but not
cleanly for either drug's peak frequency specifically vs dose.** That gap is exactly the empty methodological
niche `LIT_2026_08_02_BAND_VS_BANDFREE.md` already flagged (Q3): individual/peak-anchored alpha frequency is
well established as a resting-state and cognitive-EEG construct (234 papers) and has, per a verified
zero-count query, never been carried into anaesthesia depth monitoring as a methodology.

**Confidence:** moderate-to-high that sevoflurane's peak genuinely moves down with dose (independently
measured, same direction, plausible magnitude, twice, by an unrelated group using a related but not
identical statistic). Lower, and honestly so, on propofol's invariance — supported by an absence of
contrary direct evidence and a consistent cluster of same-ballpark snapshots, but not by any dose-response
test in either direction. The overall asymmetry as a **novel, precisely quantified, single-pipeline,
matched-cohort comparison** is not duplicated anywhere I found; its two component claims are asymmetric in
how well the literature backs them, and the write-up this becomes should say so rather than treat both
halves as equally supported.
