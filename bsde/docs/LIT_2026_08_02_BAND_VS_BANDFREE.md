# Where the fixed-band / band-free finding sits in the literature

*2026-08-02. Every PMID below was fetched from its MEDLINE record via NCBI E-utilities and the quoted
sentences are copied verbatim from the `<AbstractText>` field. A delegated agent ran the searches; Opus
re-fetched the four load-bearing records independently and re-ran the zero-count query. Rule 25 exists
because WebFetch fabricated six PubMed citations for this project once; no WebFetch summary was used here.*

**Rule 42 applies throughout: a quotation supports only what it literally says.** Where a sentence below is
an inference from a source rather than the source's content, it is labelled as one.

---

## The five questions, and what the record actually supports

### Q1 — Is the alpha peak lower under sevoflurane than propofol? **CONTESTED, and this matters to us.**

| PMID | what it says | bearing |
|---|---|---|
| **42131603** (Front Med, 2026, n=44) | *"the Sevoflurane group exhibited a distinct elevation in theta-band prominence and a significant downward shift in alpha peak frequency (8.78 Hz vs. 10.88 Hz for Propofol)"* | supports, and is the only source giving a Hz figure for this exact pair |
| **30112395** (BioMed Res Int, 2018) | *"a shift to relatively lower values for alpha band (propofol: 9.94 Hz to 10.33 Hz, desflurane 8.44 Hz to 8.84 Hz)"* | supports by extension — a different volatile, same direction, ~1.5 Hz |
| **25233374** (Akeju, Anesthesiology, 2014, n=60) | *"Sevoflurane general anesthesia is characterized by alpha oscillations with maximum power and coherence at approximately 10 Hz... These alpha oscillations are similar to those observed during propofol general anesthesia, which also has maximum power and coherence at approximately 10 Hz"* | **contradicts the magnitude**, from a larger and far better established source |

**Our own measurement lands with the minority.** At BIS < 40 the case-level medians are propofol 9.75-10.00 Hz
against volatile 8.50 Hz. Two qualifications belong beside that, and both cut against over-claiming:

* **Our estimator is censored and Akeju's is not.** `alpha_peak_hz` is the raw PSD maximum inside 8-13 Hz,
  so it cannot report a peak below 8 Hz — 28.74 % of volatile windows at BIS < 40 pin at the floor against
  8.91 % of propofol. That makes our shift a **lower bound**, which widens rather than narrows the
  disagreement with Akeju.
* Akeju's claim is about where power and coherence are maximal, stated as "approximately 10 Hz" — a coarse
  statement that a 1-1.5 Hz difference would not obviously violate. *(This sentence is an inference about
  what the source's phrasing can bear, not something the source says.)*

**Do not cite the peak shift as settled.** Cite it as our measurement, with the censoring caveat and the
Akeju tension stated.

### Q2 — Are fixed-band measures less transportable across agents than band-free ones? **NOT DIRECTLY TESTED ANYWHERE. This is the load-bearing question and it appears to be open.**

No paper found registers this contrast as its research question. Three converge on it obliquely:

* **42131603** reports, in the same SHAP-ranked panel where alpha peak frequency discriminates agent
  identity, that *"alpha bandwidth (p = 0.263) and signal complexity measures (e.g., spectral entropy,
  p = 0.721) provided negligible discriminatory value."* Band-anchored measures separate the agents; a
  band-free one does not. *(That this is the same phenomenon as a depth-relationship disagreement is our
  inference, not the paper's claim — the paper is about discriminating agents, not about depth.)*
* **34081045** (Anesth Analg, 2021, xenon vs sevoflurane) concludes: *"these findings suggest that
  appropriate depth-of-anesthesia monitoring may require the development of agent-specific spectral
  measures of unconsciousness."* This is the clearest statement of the general problem, and it is **silent
  on which class of measure is responsible.**
* **39609175** (BJA, 2025) pools **sevoflurane, desflurane and propofol** (125 anaesthesia, 62 wake):
  *"We observed an increase in the spectral exponent from consciousness to unconsciousness (AUC=0.98
  (0.94-1))... Using aperiodic EEG activity instead of the entire spectrum for spectral parameter
  calculation improved the separation between consciousness and unconsciousness for all parameters."*
  A band-free measure at near-ceiling discrimination **pooled across three agents without agent-specific
  correction** — which a badly-transporting measure could not achieve.

**Consequence for this programme.** E214's finding is a synthesis of scattered evidence rather than a
re-discovery, which raises its value — and raises the bar, because E214 is weak (p = 0.046, not robust to
dropping any single feature). A novel claim needs the stronger evidence E216 and E217 are built to provide,
not the weaker.

### Q3 — Peak-anchored / individual-alpha-frequency bands in anaesthesia monitoring? **NOTHING. Verified as a count, not as a failure to search.**

    "individual alpha frequency"[tiab]                          234 papers
    "individual alpha frequency"[tiab] AND anesthesia             0
    "individual alpha frequency"[tiab] AND anaesthesia            0
    "peak alpha frequency"[tiab] AND (anesthesia OR anaesthesia)  9

Those counts were re-run by Opus against E-utilities. The nine hits *measure* peak alpha frequency as an
outcome (xenon lowering it; lower alpha frequency associated with postoperative delirium); none uses an
individually-anchored band as a **monitoring methodology**. Individual alpha frequency is thoroughly
established in cognitive and resting-state EEG — 234 papers — and has apparently never been carried into
anaesthesia depth monitoring.

**This is the most actionable finding in the search.** E213 refuted the *case-removal* version of the
band-placement story and its scope section says explicitly what it could not test: no per-window spectra were
stored, so a genuinely peak-ANCHORED measure was never built. The literature now says nobody else has built
one here either.

### Q4 — Has any EEG measure been reported to REVERSE direction between agents? **Yes, but only across drug classes — which makes our case the novel one.**

* **10713872** (Eur J Anaesthesiol, 1999): adding ketamine to a fixed propofol-fentanyl infusion, at a dose
  that clinically deepens anaesthesia, *raised* BIS and 95 % spectral edge — from 44.1 and 16.0 to 58.6 and
  19.5 (P < 0.01) — the direction lightening would produce.
* **21788312** (Anesth Analg, 2011): *"Because increases in low-frequency power typically indicate
  increasing anesthesia, N2O's suppression of such activity and its rebound during washout would
  paradoxically influence EEG monitoring parameters."*

Both precedents involve agents that are **mechanistically distinct** from propofol — NMDA antagonism rather
than GABA-A potentiation — so a reversal is explicable by receptor pharmacology and is unsurprising. **No
precedent was found for a reversal between two GABAergic agents.** Propofol and sevoflurane both act largely
through GABA-A, so the mechanism that explains the known reversals is not available to explain ours. That
makes the finding more novel and also **removes its easiest explanation**, which is a reason to hold it more
sceptically rather than less.

### Q5 — Is the aperiodic exponent an agent-invariant depth marker? **Established cross-STATE; only supportively cross-AGENT; and its LEVEL is not invariant.**

* **32720644** (Lendner, eLife, 2020), the seminal paper: *"the 1/f spectral slope of the electrophysiological
  power spectrum, which reflects the non-oscillatory, scale-free component of neural activity, delineates
  wakefulness from propofol anesthesia, NREM and REM sleep."* Note the anaesthesia arm is **propofol only** —
  this establishes invariance across *states*, not across *agents*.
* **39609175** pools three agents and is the closest direct evidence (Q2 above).
* **42131603** reports the exponent's absolute value differing by agent — steeper under sevoflurane than
  propofol, 2.37 vs 2.07, p = 0.039.

**Precision the write-up must keep:** the exponent is not invariant in LEVEL. What our results and 39609175
support is that its depth relationship does not REVERSE. Those are different claims and only the second is
ours to make.

---

## What this changes about the programme's priorities

1. **The peak-anchored measure is now the highest-value open Challenge A experiment**, not merely a
   successor E213 gestured at. It is a verified empty niche (Q3), it is the one thing that would convert a
   description of a failure into a constructive fix, and it needs a re-extraction that stores enough
   spectrum to integrate an arbitrary band.
2. **Our alpha peak-shift number should not be reported as established** (Q1). Report it as measured here,
   with the censoring caveat, and cite Akeju 2014 as the source it disagrees with.
3. **The reversal's novelty is real and it removes an explanation** (Q4). The known reversals come with a
   receptor-level story that our agent pair cannot borrow. E213 has already refuted the arithmetic story.
   That leaves the mechanism genuinely open, which is where a claim should be when neither of the two
   obvious explanations survives.
4. **E209's ordering is consistent with the outside literature** and that is worth stating: the measure
   that replicated across deposits was `whole_head_exponent`, the measure that failed was
   `relative_alpha_power`, and 39609175 independently reports the aperiodic component carrying
   near-ceiling discrimination pooled across three agents.
