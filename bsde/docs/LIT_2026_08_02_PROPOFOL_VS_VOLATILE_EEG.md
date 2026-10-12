# Literature probe: why does EEG track sevoflurane ~4.6x better than propofol on VitalDB?

*2026-08-02. Literature probe only — no analysis run, no registration written. Every citation below was
pulled from its own MEDLINE record via NCBI E-utilities (`esearch`/`efetch`,
`eutils.ncbi.nlm.nih.gov`) with `curl`/`python urllib`, never WebFetch (catalogue rules 25, 39). PMIDs and
quoted sentences are the literal text returned by `efetch … rettype=abstract`. Where I infer something the
source does not literally say, it is labelled **INFERENCE** with the source sentence quoted alongside it
(rule 42).*

**The fact to explain** (from `bsde/docs/NOTE_CHALLENGE_A_REFRAMED.md`, all numbers already verified in that
note against the raw source):

| exposure | provenance | n cases | mean \|rho\| (within-case, EEG panel vs. exposure) |
|---|---|---|---|
| propofol effect-site Ce | pump's own PK-model output (Orchestra TCI) | 44 | **0.0912** |
| sevoflurane inspired | delivered/vaporiser setting (measured gas, no uptake) | 70 | 0.4192 |
| sevoflurane MAC | monitor-derived from end-tidal | 70 | 0.4392 |
| sevoflurane end-tidal | measured gas, alveolar | 70 | **0.4925** |

Degrading the volatile instrument from measured end-tidal to delivered inspired closes about **15 %** of the
gap (0.4925 → 0.4192, monotone with monitor-MAC in between) and leaves **~85 % unexplained**. This probe
looks for literature bearing on the rest.

---

## Candidate 1 — TCI prediction error (how noisy is a *modelled* Ce)

**This is the best-supported candidate in the literature, and it is a real, well-quantified, and large
source of error — but it needs to be read against what it would have to be, not just what it is.**

Varvel, Donoho & Shafer defined the field's standard vocabulary for this — MDPE (bias) and MDAPE
(inaccuracy) — specifically so PK-driven pump performance could be compared across models (**PMID
1588504**, *J Pharmacokinet Biopharm* 1992):

> "We propose four measures be used to quantitate the performance of CCIPs: median absolute performance
> error (MDAPE), median performance error (MDPE), divergence, and wobble."

Measured MDAPE values for propofol TCI models against arterial/venous assay, across five independent
validation studies:

| population (n) | model | MDPE | MDAPE | PMID |
|---|---|---|---|---|
| brain-tumour patients, adults (n=20) | Schnider | −20.0 % | **23.4 %** | 28549082 |
| " | Marsh | −14.3 % | **41.4 %** | 28549082 |
| " | Eleveld volunteer | −8.58 % | **21.6 %** | 28549082 |
| control adults, no tumour (n=20) | (same study, control arm) | — | — | 28549082 |
| morbidly obese adults, TBW-scaled (n=20) | Eleveld allometric | 18.2 % | **27.5 %** | 24977639 |
| morbidly obese, adjusted body weight | Schnider/Marsh | <10 % | **<25 %** | 24977639 |
| mixed adults, bolus/infusion/TCI datasets (pooled reanalysis) | Schnider | — | best of 4 tested | 19861357 |
| 9 adults, standardized infusion | Schnider (Diprifusor/Marsh compared) | −0.1 % (Schnider) | not stated numerically for MDAPE in abstract | 19297371 |
| Chinese adults (simulation vs. Li PK parameters) | Marsh | −11.9 % | **18.5 %** | 17972616 |
| " | Schnider | −8.6 % | **17.9 %** | 17972616 |
| Chinese elderly (simulation) | Schnider | — | **42.1 %** | 17972616 |
| Chinese elderly (simulation) | Marsh | — | **15.5 %** | 17972616 |

Quoted directly, the brain-tumour-control comparison (Sahinovic et al., **PMID 28549082**, *Br J Anaesth*
2017):

> "Performance of the Schnider model (MdPEpk -20.0%, MdAPEpk 23.4%) and Eleveld volunteer model (MdPEpk
> -8.58%, MdAPEpk 21.6%) were good. The Marsh model performed less well (MdPEpk -14.3%, MdAPEpk 41.4%)."

**Reading this against the fact to explain.** MDAPE of 18–41 % (typically ~20–25 % for a well-behaved model
in the population it was built for, worse in specific populations — obesity, elderly, brain pathology) is
the field's own estimate of how far a modelled Ce sits from measured plasma. That is a large, real error and
it is **entirely plausible as *a* contributor** to weaker within-case tracking. **It does not by itself
predict a 4.6-fold gap against a comparator (sevoflurane end-tidal) that has its own measurement error too**
— nothing in these papers compares propofol MDAPE against an equivalent volatile-agent MDAPE on the same
metric, so the literature cannot supply the ratio directly (see "what the literature cannot adjudicate"
below).

**Internal evidence that bears directly on this and belongs in the record even though it is not a
published citation** (rule 39's corollary — search the project's own record first): `bsde/scripts/
validate_pk_against_pump.py`, documented in `bsde/docs/PK_VALIDATION_NOTE.md`, reproduced the *same* pump's
own `Orchestra/PPF20_CE` from the raw infusion rate using an exponential-basis model, in the identical
VitalDB deposit, and found in-sample function-space fit was excellent (R² = 0.9990) but cross-patient
transfer of a single fitted kernel gave **MDAPE 53.81–66.03 %** — roughly double the published figures
above. This is not the same quantity (it is our reconstruction vs. the pump's own Ce, not the pump's Ce vs.
assayed blood), but it independently corroborates that a fixed population PK/PD kernel misses individual
propofol pharmacokinetics by a wide, clinically-documented margin, and that this margin is systematic
(offset) rather than noisy (wobble ~10 % vs. MDAPE ~54 %, per that note).

**Verdict on Candidate 1: well-supported as a real and large error source, weakly diagnostic of the specific
4.6x ratio.** The literature establishes propofol TCI MDAPE at 18–41 %, occasionally >40 % in the elderly or
obese; it does not supply a matched volatile-agent MDAPE against blood/brain concentration to divide by, so
it cannot itself certify how much of the 4.6x gap it explains.

---

## Candidate 2 — ke0 / hysteresis misspecification

**The clearest quantitative anchor:** Schnider's own foundational PD study established the population
plasma-effect-site equilibration rate constant for propofol (**PMID 10360845**, *Anesthesiology* 1999):

> "The plasma effect-site equilibration rate constant was 0.456 min(-1). The predicted time to peak effect
> after bolus injection ranging was 1.7 min. The time to peak effect assessed visually was 1.6 min (range,
> 1-2.4 min)."

This is the ke0 (or one very close to it) built into essentially every propofol TCI pump's effect-site mode,
including — very likely, though **the deposit does not name the pump's model** (confirmed by grep of
`bsde/src/bsde/ingestion/vitaldb.py` and `PK_VALIDATION_NOTE.md` §5.1: *"The pump's model is not named in
the deposit"*) — the Orchestra device behind `PPF20_CE`.

**A direct within-agent, within-study comparison of BIS ke0 for propofol vs. sevoflurane**, from the same
research group using the same method on separate propofol and sevoflurane cohorts (Mourisse et al., **PMID
17519261**, *Br J Anaesth* 2007):

> "The k(e0) for area-R1 was about half that for BIS in both groups: 0.24 (0.19-0.29) vs 0.48 (0.38-0.60)
> min(-1) for Group S; 0.28 (0.23-0.34) vs 0.46 (0.40-0.54) min(-1) for Group P, geometric mean (95% CI)."

Reading the BIS values only: **sevoflurane group ke0 = 0.48 min⁻¹ [0.38–0.60]; propofol group ke0 = 0.46
min⁻¹ [0.40–0.54]** — essentially the same point estimate and overlapping intervals of similar relative
width. **INFERENCE, not stated by the source:** if hysteresis misspecification were the dominant reason
propofol's own concentration tracks its EEG effect worse than sevoflurane's, one would expect this
comparison — both fitted with the same method, same index (BIS), same era — to show a much larger or much
more variable ke0 for propofol. It does not. This is a comparison against BIS, a proprietary composite
index, not against the raw spectral panel this project uses, so it is not a direct test of the actual
candidates, but it is the most relevant head-to-head number located.

A second data point, from children (Fuentes et al., **PMID 18931214**, *Anesth Analg* 2008), gives the only
between-subject variability (coefficient of variation) figure found for a volatile-agent ke0:

> "the rate of change of sevoflurane's effect expressed as the effect-site equilibration half-life (t(1/2)
> k(e0)) was slower with the CSI [2.0 (14) min] than with BIS [1.2 (53) min] (P < 0.05)."

Sevoflurane's own BIS-based t½ke0 in children carries **53 % CV** — a large between-subject spread in its
own right, undercutting a simple story where sevoflurane's hysteresis is well-behaved and propofol's is not.

**What the literature does NOT supply, searched for specifically and not found:** a paper measuring
between-patient *variability* of an individually-fitted propofol ke0 against a raw quantitative spectral EEG
feature (not BIS), matched head-to-head against the same quantity for a volatile agent, in adults, using
concentration rather than a proprietary index as the dependent variable. Absent that, Candidate 2 cannot be
ranked with confidence either way from published sources — the one number set located (Mourisse, BIS-based)
argues weakly against it being the dominant cause; the between-subject variability figure (Fuentes,
sevoflurane's own CV of 53 %) shows volatile ke0 is not free of the problem either.

**Verdict on Candidate 2: literature thin, and what exists argues weakly against, not for.**

---

## Candidate 3 — restriction of range (is propofol run at a near-constant target while volatile is
continuously adjusted?)

**This project's own internal analysis has already directly measured the two exposures' within-case
variability on the very same VitalDB cohort**, reported in `NOTE_CHALLENGE_A_REFRAMED.md`:

> "the two exposures have *identical* within-case variability — coefficient of variation 0.341 against
> 0.355, interval spanning zero... propofol in fact has MORE distinct values per case (18.5 vs 11.5), so it
> is not a coarse staircase."

That is a strong internal refutation and I did not attempt to re-derive it (out of scope for a literature
probe; catalogue rule 20 — diff, don't recompute, someone else's number without cause). **What I searched
the literature for and could not find:** any published paper directly quantifying the *frequency* with which
clinicians adjust a propofol TCI target versus a volatile vaporiser/end-tidal setting during maintenance
in ordinary (non-closed-loop) practice. Searches for "vaporizer adjustment frequency," "TCI target change
frequency maintenance," and "manual titration frequency propofol volatile" returned either nothing on-topic
or closed-loop-control papers that are about automated systems, not standard manual titration patterns (e.g.
**PMID 30956886**, **23668370**, **18806028**, **11012489** — all closed-loop controllers, not observational
titration-frequency studies). **This is an absent literature**, and given that the internal CV/distinct-value
check already refutes restriction-of-range on the actual VitalDB data, the absence does not weaken the
project's own conclusion — it just means there is no external corroboration or refutation available.

**Verdict on Candidate 3: refuted internally (not by literature); literature on titration frequency is
silent.**

---

## Candidate 4 — genuine pharmacodynamic difference (different EEG magnitude or spectral character at
equipotent dose)

Two lines of evidence, pointing in different directions on different questions.

**(a) Additivity, not asymmetry, at the level of overall potency.** Schumacher et al.'s response-surface
study directly modelled combined propofol+sevoflurane dosing against BIS/entropy suppression (**PMID
19741484**, *Anesthesiology* 2009):

> "Additivity was found for all endpoints, the Ce(50, PROP)/Ce(50, SEVO) for bispectral index suppression
> was 3.68 microg. ml(-1)/ 1.53 vol.%... For both electroencephalographic suppression and tolerance to
> stimulation, the interaction of propofol and sevoflurane was identified as additive."

**INFERENCE:** additivity on a *composite* dose-response surface says the two agents converge on the same
EEG-suppression axis when combined — it says nothing about how tightly *moment-to-moment* concentration
tracks that axis within a single agent's own administration, which is the actual quantity behind the
0.09-vs-0.49 contrast. This paper cannot adjudicate the specific claim.

**(b) A direct, blinded comparison of burst micro-architecture found clear substance-specific differences**
(Fleischmann et al., **PMID 30297992**, *Front Hum Neurosci* 2018):

> "Volatile-induced bursts showed higher burst amplitudes and higher burst power. Propofol-induced bursts
> had significantly higher relative power in the EEG alpha-range. Further, isoflurane-induced bursts had the
> steepest burst slopes."

This is real evidence that the two drug classes produce **qualitatively different EEG signatures** at deep
levels (burst suppression), which is consistent with a genuine PD difference in *what* the EEG does under
each drug — but it is evidence about **burst morphology at one specific, very deep state**, not about how
well continuously-varying concentration tracks a continuously-varying EEG feature across the whole depth
range, which is the actual empirical fact under investigation. It supports "the two agents are not
interchangeable at the EEG level" in general, without directly bearing on the tracking-correlation gap.

**(c) Effect-site sensitivity differs by monitored function, similarly in both drugs** (Mourisse et al.,
**PMID 17519262**, *Br J Anaesth* 2007, companion paper to 17519261):

> "Concentration-dependent depression of TIWR was reasonably well modelled for sevoflurane, but poorly for
> propofol. TIWR was completely suppressed by sevoflurane, but not propofol."

This is a genuine, drug-specific dissociation, but it is between BIS and a *withdrawal reflex* (a spinal/
brainstem measure), not between drug concentration and cortical EEG spectral content — a different pair of
signals than the one in question, and it should not be over-read as bearing directly on our contrast.

**Verdict on Candidate 4: literature confirms the two agents are pharmacodynamically distinguishable in
EEG character (Fleischmann) and confirms differential drug×endpoint sensitivity in general (Mourisse), but
no paper located directly measures within-case concentration-to-spectral-feature tracking strength for both
agents on a comparable scale. This is the closest thing to "genuine biology" support in this search, and it
remains indirect.**

---

## Candidate 5 — end-tidal as a direct surrogate for brain partial pressure (no such surrogate exists for
plasma Ce)

**Physiological grounding for why end-tidal should track brain concentration unusually well for a volatile
agent, quantified:**

Yasuda, Targ & Eger's classic tissue-solubility study gives the sevoflurane brain:blood partition
coefficient directly (**PMID 2774233**, *Anesth Analg* 1989):

> "the respective brain/blood partition coefficients were 1.29 +/- 0.05 (mean +/- SD); 1.57 +/- 0.10; 1.70
> +/- 0.09; and 1.94 +/- 0.17" [for I-653/desflurane, isoflurane, sevoflurane, and halothane respectively]

**INFERENCE, standard pharmacokinetic reasoning not restated verbatim by the source:** a low tissue:blood
partition coefficient (sevoflurane's 1.70 is close to unity relative to older, more soluble agents like
halothane's 1.94) implies rapid blood-brain equilibration because little anaesthetic needs to accumulate in
brain tissue before its partial pressure matches blood — this is the textbook basis for volatile agents'
fast onset/offset, and the paper's own discussion draws exactly this inference for induction/recovery
speed:

> "This indicates that induction of and recovery from anesthesia with I-653 should be more rapid than with
> the other agents."

Separately, and closer to end-tidal specifically as a surrogate for arterial (and hence brain-delivered)
partial pressure, Peyton's direct measurement of alveolar-arterial gradients for a volatile agent found the
gradient to be small and not attributable to a diffusion limitation (**PMID 35503977**, *Anesthesiology*
2022):

> "Mean (SD) measured (PetG - PaG)/FiG for desflurane was significantly smaller than that for N2O (0.86
> [0.37] vs. 1.65 [0.58] mmHg; P < 0.0001)... No evidence was found in measured end-tidal to arterial partial
> pressure gradients and alveolar deadspace to support a clinically significant additional diffusion
> limitation to lung uptake of desflurane."

This paper is about desflurane, not sevoflurane, and about the lung (alveolar→arterial), not the
brain (arterial→brain) — so it corroborates the *first* leg of "end-tidal ≈ brain partial pressure"
(end-tidal ≈ arterial) but does not itself measure the second leg. **No paper directly measuring an
arterial-to-brain sevoflurane partial-pressure gradient, or a time constant for that specific step, was
found** in this search — searches for "brain time constant volatile anesthetic equilibration," "arterial to
brain equilibration inhaled anesthetic," and similar returned nothing.

**Contrast with propofol: there is no analogous physical quantity.** No published clinical PK/PD model
takes an "arterial-to-brain equilibration constant" for propofol from first-principles solubility the way
Candidate 5 does for a gas — propofol's own literature-standard route to "brain concentration" is entirely
through the fitted, population-average ke0 already discussed under Candidate 2, which is a *statistical*
correction fitted to an EEG/BIS endpoint, not a measured physical partition property. **This asymmetry in
the KIND of evidence available for the two agents' brain-concentration estimates is real and is the most
conceptually clean distinction found in this search — but it was not found stated or quantified together, in
one place, in any single source; it is assembled here from separate literatures (volatile solubility
physiology vs. IV PK/PD modelling) rather than read off one paper.**

**Verdict on Candidate 5: physiologically well-grounded for the "why end-tidal is fundamentally a different
kind of measurement than modelled Ce" framing, but the specific brain-equilibration time-constant number for
a volatile agent, and any paper stating the asymmetry explicitly, were not located.**

---

## Ranking, by how well the literature actually supports each candidate

| rank | candidate | literature support | can the literature give a NUMBER on the 4.6x gap? |
|---|---|---|---|
| 1 | **TCI prediction error (Candidate 1)** | Strong and well-quantified (MDAPE 18–41 % across 5 studies); this project's own internal validation corroborates a similar-sized, systematic error on the identical pump | **No** — no paper reports a matched volatile-agent MDAPE against blood/brain assay to form the ratio |
| 2 | **Genuine PD/measurement-kind asymmetry (Candidates 4+5 combined)** | Two independent literatures (burst micro-architecture; volatile solubility physiology) each support a real qualitative difference, but neither was built to answer this question and neither gives a magnitude | **No** |
| 3 | **Restriction of range (Candidate 3)** | Not addressed in the literature at all (searched, absent); already refuted by this project's own internal CV/distinct-value check | **N/A — refuted, not by literature** |
| 4 | **ke0/hysteresis misspecification (Candidate 2)** | Thin, and the one adult head-to-head comparison found (Mourisse, BIS ke0 0.46 vs 0.48 min⁻¹) argues weakly AGAINST this being the dominant driver | **No**, and what exists cuts the wrong way |

**Bottom line.** The literature strongly supports that propofol TCI models carry real, large,
well-documented prediction error (Candidate 1) and offers a genuine physiological reason a measured gas
concentration is a structurally different — and structurally better-grounded — kind of brain-concentration
surrogate than a fitted PK model output (Candidate 5). **Neither, nor any combination found, comes with a
published number that could be combined into an expected tracking-correlation ratio.** The published
MDAPE literature answers "how wrong is a modelled Ce" in isolation (18–41 %) but was never designed to be
divided against a volatile agent's own error to predict a within-case Spearman-correlation gap of 4.6-fold;
that combination does not exist in print and would need to be constructed, which is outside this probe's
scope (no analysis was run, per instruction).

**What the literature can adjudicate:** that propofol TCI inaccuracy is real, large, and worse in some
populations (elderly, obese, brain pathology) than others (18–41+ % MDAPE); that sevoflurane brain
uptake is fast by first-principles solubility (brain:blood partition coefficient 1.70) and that end-tidal
closely tracks arterial partial pressure for at least one volatile agent (desflurane; gradient ~0.86 mmHg,
no diffusion limitation); that the two agents produce distinguishable EEG signatures at burst suppression
(higher relative alpha in propofol bursts, higher amplitude/power in volatile bursts); and that a
composite-index (BIS) hysteresis parameter is *not* obviously worse for propofol than sevoflurane in the one
adult study located.

**What the literature is silent on, and this probe found no paper addressing:**
1. A matched propofol-vs-volatile MDAPE (or equivalent inaccuracy metric) computed against the same
   reference type (e.g., both against an EEG/BIS effect, or both against blood/brain assay) that would let
   the two agents' concentration-estimation errors be compared on one scale.
2. Between-subject variability of an individually-fitted propofol ke0 measured against a raw spectral EEG
   feature (not BIS), matched against the same quantity for a volatile agent, in adults.
3. Observed clinical frequency of TCI-target adjustment vs. vaporiser-setting adjustment during ordinary
   (non-closed-loop) maintenance anaesthesia.
4. A directly measured arterial-to-brain equilibration time constant for sevoflurane (only the lung-level,
   alveolar-to-arterial gradient was found, and only for desflurane).
5. Any single paper stating explicitly that "a measured end-tidal concentration is a fundamentally different
   kind of brain-concentration estimate than a modelled plasma/effect-site concentration" — the asymmetry
   used throughout this note is assembled from two separate literatures, not quoted from one source.

None of these gaps were papered over with an inference dressed as a citation; each is reported here as
absent so a later session does not have to re-run the same searches to discover the same absence.

---

## Full PMID list, verified via E-utilities

1588504 (Varvel — Candidate 1 methodology), 28549082, 24977639, 19861357, 19297371, 17972616
(Candidate 1, TCI MDAPE), 10360845 (Candidate 2, Schnider ke0 = 0.456 min⁻¹), 17519261, 17519262 (Candidate
2/4, Mourisse multi-level BIS/reflex ke0 comparison), 18931213, 18931214 (Candidate 2, sevoflurane ke0 in
children/adults), 19741484 (Candidate 4, response-surface additivity), 30297992 (Candidate 4, burst
micro-architecture by agent), 26174300 (background — EEG spectral form similar in shape across ages for both
agents, not directly load-bearing for the tracking question), 2774233 (Candidate 5, Yasuda brain:blood
partition coefficients), 35503977 (Candidate 5, Peyton alveolar-arterial gradient, desflurane).

Searches run and returning zero or off-topic results (reported per the absent-literature instruction):
"end-tidal concentration volatile anesthetic brain equilibration" (0), "sevoflurane brain uptake blood gas
partition coefficient equilibration" (0), "TCI target adjustment frequency anesthesiologist practice pattern
intraoperative propofol" (0), "propofol effect site equilibration rate constant variability across studies
different values" (0), "propofol ke0 estimates variability different studies range" (0), "test-retest EEG
spectral variability steady state propofol" (0), "within subject variability EEG response propofol repeated
measurement reliability" (0).
