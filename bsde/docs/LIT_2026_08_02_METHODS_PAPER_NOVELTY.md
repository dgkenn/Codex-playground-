# Literature check: does prior art already cover the "specific and enumerable failure modes" line?

*2026-08-02. Literature check only — no analysis run, no registration filed, no ledger row added. Every
citation below was retrieved and read via NCBI E-utilities (`esearch`/`efetch`, `curl`) directly against
MEDLINE; no WebFetch was used on any bibliographic source (catalogue rules 25, 39). PMIDs are given for
everything cited, and every quoted sentence is copied verbatim from the `efetch` abstract text saved to
`/tmp` during this session. Inferences that go beyond what a quotation literally says are labelled as mine
(rule 42).*

---

## VERDICT (one line)

**PARTIALLY PUBLISHED.** The general framing — that EEG/neuroimaging false positives come from specific,
nameable analytic and instrument failures rather than from vague "researcher degrees of freedom" — is
already a crowded genre (Kriegeskorte, Simmons, Button, Eklund, and an EEG-specific entry, Luck & Gaspelin).
**Answering item 3 first, as instructed: the peak-estimator instance's *qualitative* hazard (unconstrained
peak-picking is unreliable and needs a threshold/smoothing step) is well established in the FOOOF/IAF
literature (Corcoran 2018, Donoghue 2020). The *specific number* this programme reports — a measured 87.5–
91.5% false-positive rate on signal-free 1/f noise, and the demonstration that a 93% "detection rate" on
real data is statistically indistinguishable from that noise floor — was not found in any source searched.**
Of the other four instances, two (the fixed-band-manufactures-a-*reversal* finding, and the LOO-conceals-a-
zero/nonzero-split diagnostic) sit adjacent to established general hazards but were not found stated in
that specific, sign-reversing / masking form anywhere in the literature searched. Two (the ceiling-bound
placebo, and the anaesthesia-machine track-key cohort predicate) returned no relevant prior art of any kind
in a biomedical database search and read as genuinely local findings, though for the track-key case the
*category* of problem (differential exposure misclassification from an administrative/device log) is an old
idea in epidemiology that this search could not pin to a specific PubMed record.

---

## 1. General EEG/neuroimaging methodological-pitfall catalogues

Verified directly against MEDLINE, all via `efetch`:

| paper | PMID | what it establishes (quoted) |
|---|---|---|
| Kriegeskorte, Simmons, Bellgowan & Baker, *Nat Neurosci* 2009 | **19396166** | *"'double dipping,' the use of the same dataset for selection and selective analysis, will give distorted descriptive statistics and invalid statistical inference... To demonstrate the problem, we apply widely used analyses to noise data known to not contain the experimental effects in question."* |
| Vul, Harris, Winkielman & Pashler, *Perspect Psychol Sci* 2009 | **26158964** | *"More than half acknowledged using a strategy that computes separate correlations for individual voxels and reports means of only those voxels exceeding chosen thresholds. We show how this nonindependent analysis inflates correlations..."* |
| Simmons, Nelson & Simonsohn, *Psychol Sci* 2011 | **22006061** | *"flexibility in data collection, analysis, and reporting dramatically increases actual false-positive rates. In many cases, a researcher is more likely to falsely find evidence that an effect exists than to correctly find evidence that it does not."* |
| Button, Ioannidis, Mokrysz, Nosek, Flint, Robinson & Munafò, *Nat Rev Neurosci* 2013 | **23571845** | *"low power also reduces the likelihood that a statistically significant result reflects a true effect... the average statistical power of studies in the neurosciences is very low."* |
| Eklund, Nichols & Knutsson, *PNAS* 2016 | **27357684** | *"Cluster failure: Why fMRI inferences for spatial extent have inflated false-positive rates."* (title; body confirms parametric cluster methods measured against 3 million random task-free datasets) |
| **Luck & Gaspelin, *Psychophysiology* 2017 — the EEG-specific entry** | **28000253** | *"using the grand-averaged data to select the time windows and electrode sites for quantifying component amplitudes and latencies... can lead to very high rates of significant but bogus effects, with the likelihood of obtaining at least one such bogus effect exceeding 50% in many experiments."* |

**Per-instance coverage, checked specifically rather than generally:**

1. **Alpha-peak estimator, 91.5% false-positive rate on noise.** Kriegeskorte's "double dipping" is the
   right *genus* (using noise-shaped data to demonstrate a procedure's own failure mode is literally
   Kriegeskorte's method) but it is about *selecting an analysis window from the same data being tested*,
   not about *an unconstrained maximum-finding estimator returning a plausible-looking value from pure
   noise*. **Not covered.** See §3 for the closer, EEG/spectral-specific literature.
2. **Fixed-band reversal, dissolved by peak anchoring, four experiments to catch.** None of the five general
   papers above discuss frequency-band placement at all — they are about selection circularity, correlation
   inflation, sample size, cluster inference and ERP window/electrode selection respectively. **Not
   covered** by this table; see §3–4 for the closer literature.
3. **LOO conceals a zero-vs-nonzero split.** Luck & Gaspelin is the closest in spirit (both are about a
   *procedure that looks like due diligence failing to catch a specific structural artefact*), but their
   worked examples are window/electrode selection and multifactor ANOVA inflation, not a masked subgroup in
   a rank correlation. **Not covered.**
4. **Placebo structurally unable to fire at a ceiling.** None of the five discuss bounded statistics or
   placebo/permutation comparisons at all. **Not covered.**
5. **Track-key cohort predicate, 70/114 cases discarded one-sidedly.** None of the five are about cohort
   construction from device/administrative logs. **Not covered.**

**What I did NOT find**, despite deliberate search: an EEG-specific paper that plays Kriegeskorte's role for
*spectral* (rather than ERP-window/electrode or fMRI-voxel) analyses — i.e., a paper that demonstrates
spectral-analysis-specific circularity on noise data the way Kriegeskorte demonstrates it for fMRI/MVPA and
Luck & Gaspelin demonstrate it for ERP windows. The closest candidates are covered in §3 and none does this.

---

## 2. Registered reports / pre-registration — an empirical account of what was CAUGHT, with counts

Searched specifically for an empirical account (not advocacy) of what pre-registration prevented, in a
*running* programme, with counts — i.e., an object comparable to this programme's 220-registration ledger
and 94-rule catalogue with measured costs attached to each rule.

| paper | PMID | what it actually measures |
|---|---|---|
| Nosek, Ebersole, DeHaven & Mellor, *PNAS* 2018 | **29531091** | Advocacy/overview piece — *"Progress in science relies in part on generating hypotheses with existing observations and testing hypotheses with new observations. This distinction between postdiction and prediction is appreciated conceptually but is not respected in practice."* Argues for the practice; does not report a catalogue of caught errors from one programme. |
| Claesen, Gomes, Tuerlinckx & Vanpaemel, *R Soc Open Sci* 2021 | **34729209** | The closest empirical analogue found. *"we have investigated adherence and disclosure of deviations for all articles published with the Preregistered badge in Psychological Science..."* — this measures whether studies **deviated from** their preregistration and whether they **disclosed** it. It is an audit of *compliance*, not a catalogue of *what the preregistration step caught before publication*. Different object: it answers "did they follow the plan," not "what did following the plan prevent." |
| Yang et al., *BMC Biol* 2023 | **37013585** | Publication-bias effect-size/power simulation in ecology & evolutionary biology — not about what preregistration caught, and not EEG/neuroscience. |
| Smith et al., *R Soc Open Sci* 2023 | **36686547** | A registered report *using* the registered-report format to study COVID-19 trial design quality — an application of the method, not a study of the method's catch rate. |

**Searched and found nothing for:** "registered reports reduce publication bias outcome switching" (0
hits), "case study preregistration prevented researcher degrees of freedom" (0 hits), "lab specific error
catalogue reproducibility neuroscience pitfalls" (0 hits).

**Conclusion on item 2: UNADDRESSED as a genre, at least in what a PubMed search surfaces.** I could not
find a published paper whose content is "here is a running research programme's own count of what its
pre-registration and gate machinery caught, with the measured cost of each catch." Claesen et al. is the
nearest neighbour and answers a different question (adherence/deviation-disclosure rate across many external
studies, not caught-error count within one programme). This is consistent with what
`DECISIONS_2026_08_02_LINES_AND_BLOCKERS.md` already flags as the project's real remaining asset: **the
220-row ledger and 94-rule catalogue, if written up, would be filling a genre gap rather than restating one.**

---

## 3. Aperiodic/spectral-parameterisation pitfalls — the specparam/FOOOF literature (checked first and
   hardest, per instruction)

| paper | PMID | relevant content (quoted) |
|---|---|---|
| Donoghue et al., *Nat Neurosci* 2020 — the FOOOF paper | **33230329** | *"Electrophysiological neural activity is typically analyzed using canonically defined frequency bands, without consideration of the aperiodic (1/f-like) component. We show that standard analytic approaches can conflate periodic parameters (center frequency, power, bandwidth) with aperiodic ones... This algorithm requires no a priori specification of frequency bands."* |
| Donoghue, Dominguez & Voytek, *eNeuro* 2020 — band-ratio critique | **32978216** | *"the commonly applied θ/β ratio is most reflective of differences in aperiodic activity, and not oscillatory θ or β power... band ratio measures are a non-specific measure, conflating multiple possible underlying spectral changes."* |
| Gerster, Waterstraat, Litvak, Lehnertz, Schnitzler, Florin, Curio & Nikulin, *Neuroinformatics* 2022 | **35389160** | Head-to-head evaluation of FOOOF and IRASA on real EEG/MEG/LFP plus simulations; *"Each method and each dataset poses distinct challenges for the extraction of both spectral parts... assess the computational costs, and propose recommendations."* Quantifies parameterisation *error* under adverse conditions but on spectra where a peak is present or absent by simulation design, not a measured false-positive *rate* on pure-noise draws. |
| Corcoran, Alday, Schlesewsky & Bornkessel-Schlesewsky, *Psychophysiology* 2018 | **29357113** | *"there is little consensus on the optimal method for estimating IAF, and many common approaches are prone to bias and inconsistency... The routine [Savitzky-Golay-filtered] consistently outperformed a simpler method of automated peak detection that did not involve spectral smoothing."* |

**This is the closest body of prior art to instance 1, and it is genuinely close on the *qualitative*
claim.** Both Donoghue 2020 and Corcoran 2018 exist specifically because unconstrained/naive peak detection
is known to be unreliable — Donoghue's algorithm ships a peak-height/goodness-of-fit threshold for exactly
this reason, and Corcoran built and validated a smoothing-based alternative because "a simpler method of
automated peak detection" underperforms. **My inference, not stated this way in either abstract:** the
existence of a threshold parameter in FOOOF and a whole paper proposing a smoothed alternative to naive
peak-picking is strong indirect evidence that the field already treats bare maximum-finding as untrustworthy
near the noise floor.

**What none of the four papers do, and what our programme's E237/E239 do:**

* **Quantify a false-positive RATE on signal-free background** — "what fraction of noise-only draws does
  this estimator return a finite, plausible-looking peak for" is not reported as a percentage in any of
  these four abstracts (I could not check every figure/table of the full text under this task's scope, but
  no abstract states such a number, and Gerster's design tests error magnitude on simulated spectra with
  known peak parameters, not a peak-absent null).
* **Show that a real-data "detection rate" (E237/E239's 93% on VitalDB) is statistically indistinguishable
  from the noise-only false-positive rate**, which is the move that converts "93% of windows show a peak"
  from evidence of prevalence into evidence of nothing. This specific argument — detection rate as
  uninformative once measured against the null — was not found.
* **Show the estimator manufacturing a spurious peak at its own search-window edge** in a way later
  identified as a *different real rhythm* (rule 93's spindle correction) — a second-order finding about how
  a widened search window is not merely "wrong," it can be quietly right about something else. Not found
  anywhere searched.

**Answering item (c) directly: the peak-estimator instance is NOT already documented in the specific,
quantified form this programme reports it in.** The field already knows, qualitatively, not to trust naive
peak-picking un-gated (hence FOOOF's threshold and Corcoran's smoothing routine) — so a reviewer familiar
with this literature would not be surprised that the estimator misbehaves. But "the field already suspected
this in general" and "the field has published the number" are different claims, and only the first is true
here. **This instance is PARTIAL: novel in its specific quantification, prior art in its qualitative
direction.**

---

## 4. Fixed-frequency-band criticism — does anyone show a fixed band manufacturing a spurious GROUP
   DIFFERENCE, not merely losing power?

Searched directly for this (several query formulations, see commands below) and found **no PubMed record**
stating that a fixed band produces a *sign-reversed* or otherwise spurious *between-group* contrast, as
opposed to reduced sensitivity or conflated periodic/aperiodic content. The two closest hits:

* **Donoghue et al. 2020 (band-ratio paper, PMID 32978216, quoted in §3)** shows a fixed-band ratio measure
  reflects a *different underlying spectral feature* than intended (aperiodic offset masquerading as θ/β
  oscillatory power). This is a **conflation** finding — the measure means something other than what it is
  assumed to mean — not a **reversal** finding — the measure pointing in the opposite direction between two
  experimental arms because a moving peak crosses a fixed window's edge differently in each arm. Our
  instance 2 (fixed-band `relative_alpha_power` reversing between propofol and sevoflurane, retracted by
  E233 once the band was anchored to each recording's own peak) is the second kind, and I did not find it
  demonstrated anywhere in the literature searched.
* **Corcoran et al. 2018 (PMID 29357113)** motivates individualised alpha frequency as "an empirical basis
  for the definition of individualized frequency bands," which is the standing rationale for why anyone
  anchors a band to a peak at all — but the abstract does not report a case where the fixed-band version
  produced a *reversed* group contrast relative to the individualised version; it reports general
  bias/inconsistency in IAF *estimation* itself.

**Searches run and returning zero relevant hits:** `"individual alpha frequency" AND fixed AND band AND
spurious AND group differences` (0 hits, confirmed above); `"Brake" AND aperiodic AND cautionary AND FOOOF`
(0 hits — I could not locate a paper matching the "Brake et al." critique named in the task prompt via
PubMed under this author/topic combination; it may not be indexed in MEDLINE, may be a preprint, or may be
misremembered by the person who wrote the prompt — flagged rather than guessed at).

**Conclusion on item 4: the specific "fixed band manufactures a spurious/reversed GROUP contrast, caught
only after several confound experiments" finding was not found published anywhere searched.** The adjacent,
well-established point — fixed bands conflate periodic and aperiodic content, and individualising to IAF is
recommended practice — is prior art and should be cited as the reason our finding is *plausible*, not as
the finding itself.

---

## 5. The other three instances — search summary

**LOO conceals a zero-vs-nonzero split (rule 89).** No EEG/neuroimaging-specific match found. The
underlying statistical shape — a small subgroup that a leave-one-out procedure cannot expose because removing
any single member still leaves enough of the subgroup to sustain the effect — is structurally close to
"masking" in the classical multiple-outlier robust-statistics literature (a single low-breakdown-point
diagnostic fails when *several* points, not one, are jointly anomalous). **I could not verify a PubMed
record for this specific idea** — searches for `masking AND multiple AND outliers AND leave-one-out AND
diagnostics` returned zero hits, plausibly because the classical references for the masking phenomenon
(e.g., Rousseeuw's high-breakdown-point work) are largely published in statistics journals not well indexed
under those MeSH-mapped terms, or predate the PubMed-indexed era for that subfield. **This is a gap in what
this search could confirm, not a claim that the idea is unprecedented anywhere** — flagged honestly rather
than asserted either way.

**Placebo structurally unable to fire at a ceiling (rule 94).** No relevant PubMed record found for
`ceiling AND effect AND bounded AND statistic AND permutation AND one-sided AND artifact`, and no adjacent
literature was found in the searches run for §1–4 either. This reads as a genuinely local, instrument-level
finding (a `>=` comparison against a perfect classifier's score) rather than a restatement of a documented
general phenomenon.

**Track-key cohort predicate, differential exclusion of 70 of 114 cases (rule 87).** No relevant PubMed
record found for `differential AND misclassification AND exposure AND electronic health record AND device
AND logging`. **My inference, not verified against a specific source:** the *category* this belongs to —
an exposure variable that is differentially misclassified because of how an instrument or a database
populates a field, rather than because of anything about the patient — is an old and well-known concern in
clinical epidemiology (differential exposure misclassification), but I was not able to locate a specific
PubMed record naming this exact mechanism (a monitoring device logging a channel's *presence* regardless of
whether it was ever used) and I am not asserting one exists. The specific empirical instance — a whole
anaesthesia-machine channel populated for cases where the corresponding drug was never given — reads as
locally novel in the searches run.

---

## (b) Per-instance table

| # | instance | source in this programme | is it novel? | prior art (if any), PMID |
|---|---|---|---|---|
| 1 | Alpha-peak estimator returns a finite peak on signal-free 1/f noise in 91.5% (87.5%) of draws; 93% real-data "detection rate" is statistically indistinguishable from that floor | E237, E239 (rules 90, 91, 93) | **PARTIAL.** Qualitative hazard (unconstrained peak-picking near the noise floor is unreliable) is known and is *why* FOOOF has a threshold and Corcoran built a smoothed alternative. The measured false-positive RATE, and the "detection rate carries no information" argument, were not found published. | Donoghue 2020 (33230329), Corcoran 2018 (29357113), Gerster 2022 (35389160) — qualitative only |
| 2 | Fixed 8–13 Hz band manufactures an apparent propofol/sevoflurane reversal that survived four confound experiments (E224/225/227/229/232 lineage) before a peak-anchored measure (E233) dissolved it | E233, and the "FOURTH CORRECTION" in `NOTE_CHALLENGE_A_REFRAMED.md` | **NOVEL as a sign-reversal finding.** The adjacent, weaker claim (fixed bands conflate periodic/aperiodic content, individualising to IAF is recommended) is prior art. A fixed band manufacturing a *reversed*, not merely attenuated or conflated, between-arm contrast was not found published. | Donoghue 2020 band-ratio paper (32978216) — adjacent, not the same claim |
| 3 | A rank correlation across 15 spectral measures (ρ = +0.61, p = 0.01) is entirely a 4-vs-11 zero-vs-nonzero split; leave-one-out cannot reveal this because removing any one of the four still leaves three | E234/E235 (rule 89) | **Likely novel in EEG context; general statistical shape (masking) could not be confirmed as published via this search** — flagged as a search gap, not a confirmed absence | none confirmed |
| 4 | A `>=` placebo comparison cannot fire when the primary statistic is already at its maximum achievable value (accuracy 1.0000 vs. placebo mean 0.6091) | E244 (rule 94) | **Novel** — no relevant prior art found in any search run | none found |
| 5 | Cohort predicate tested whether a VitalDB track KEY existed rather than whether it was ever nonzero; an anaesthesia machine logs gas channels whether or not the vaporiser is opened, discarding 70 of 114 eligible propofol-only cases one-sidedly | E224/225/227 → corrected by E229 (rule 87) | **Novel as a specific instance.** The general epidemiological category (differential exposure misclassification from instrument/device logging) is old, but no specific matching source was found. | none found; general category unverified by PMID |

---

## (c) Restated: does item 3 show the peak-estimator instance is already known?

**No, not in the form this programme reports it, and this is stated here because it is the instance most
likely to be prior art and the task asked that it be checked first and hardest.** The *practice* of gating
peak detectors (FOOOF's threshold, Corcoran's SGF) already exists because the field already distrusts naive
peak-picking near the noise floor. What does not exist in anything found here is the **quantified
false-positive rate on signal-free background** and the **demonstration that a high real-data "detection
rate" is indistinguishable from that rate** — i.e., the number, and the specific fallacy-naming move, appear
new even though the underlying suspicion is old news to anyone who has read the FOOOF paper.

---

## (d) What remains: full paper, short note, or nothing

**A short methods note, not a full paper, and not nothing.**

Reasons a full paper is not warranted:

* The general genre — "EEG/neuroimaging false positives trace to nameable, checkable failure modes, and
  pre-registration with explicit gates catches them" — is not new; Kriegeskorte, Simmons, Button and Eklund
  collectively occupy exactly this territory for fMRI and general psychology, and Luck & Gaspelin occupy it
  specifically for EEG (ERP window/electrode selection). A paper whose contribution is *the general claim*
  would be restating four to six well-cited papers.
* Three of five concrete instances (2, 3, and the peak-estimator half of 1) sit close enough to existing
  literature (Donoghue's band-ratio and FOOOF papers, Corcoran's IAF paper) that a reviewer familiar with
  that literature would read them as corroboration, not discovery.

Reasons this is not nothing:

* **Item 2 (§2), the empirical-account-of-what-preregistration-caught genre, appears to be a genuine gap.**
  Nosek 2018 advocates; Claesen 2021 audits *compliance*, not *catch rate*; nothing found reports a running
  programme's own quantified catalogue of caught errors with measured cost per catch, which is exactly what
  this programme's 94-rule catalogue and 220-row ledger are.
* **Instances 4 and 5 (the ceiling-bound placebo; the track-key cohort predicate) returned no prior art at
  all** in searches specifically aimed at finding it, and instance 3's specific "LOO cannot see a masked
  subgroup" framing likewise found none, though I could not rule out that the general statistical idea is
  published somewhere outside PubMed's usual coverage.
* **Instance 1's specific number (87.5–91.5% false-positive rate on noise) and instance 2's specific
  shape (reversal, not mere attenuation) were both not found**, despite sitting adjacent to real prior art.

**What that adds up to:** not a paper arguing the general thesis (already argued, repeatedly, by better-cited
authors), but a **short methods note or correspondence-length piece consisting of the worked-example table
in §(b) above** — five to seven concrete, quantified failure modes from one pre-registered EEG discovery
programme, each with its measured cost, framed explicitly against the existing catalogues (cite
Kriegeskorte/Simmons/Button/Eklund/Luck & Gaspelin for the genre, cite Donoghue/Corcoran/Gerster for why the
peak-estimator instance is *not surprising in kind* but *is new in measured degree*) — closing the specific
gap item 2 identified (an empirical, quantified account of what a programme's own registration-and-gate
machinery actually caught) rather than re-arguing that pre-registration is a good idea.

---

## Appendix: search log (for reproducibility)

All queries run via `curl --cacert /root/.ccr/ca-bundle.crt
"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{esearch,efetch}.fcgi?..."`, no WebFetch used at any point.
Representative query strings, in the order run:

```
esearch: Kriegeskorte+circular+analysis+neuroscience                              -> 19396166
esearch: puzzlingly+high+correlations+in+fMRI+studies+of+emotion                  -> 26158964 (+3 comments)
esearch: Simmons+false-positive+psychology+undisclosed+flexibility                -> 22006061
esearch: Button+power+failure+neuroscience+reproducibility                        -> 23571845
esearch: Eklund+cluster+failure+fMRI+inferences                                   -> 27357684
esearch: Luck+Gaspelin+statistically+significant+ERP                              -> 28000253
esearch: Donoghue+parameterizing+neural+power+spectra                             -> 33230329
esearch: (Donoghue candidate sweep)                                               -> 32978216, 35074579
esearch: Gerster+separating+neural+oscillations+aperiodic                         -> 35389160
esearch: Corcoran+individual+alpha+frequency+symptom                              -> 29357113 (+8 others, screened)
esearch: Brake+aperiodic+cautionary+FOOOF                                         -> 0 hits
esearch: individual+alpha+frequency+fixed+band+age                                -> 12 hits, none matching the
                                                                                       specific reversal claim
esearch: preregistration+deviations+registered+reports+empirical                  -> 37013585, 36686547 (screened, off-topic)
esearch: Claesen+comparing+preregistered+studies                                  -> 34729209
esearch: Nosek+preregistration+revolution                                         -> 29531091
esearch: registered+reports+reduce+publication+bias+outcome+switching             -> 0 hits
esearch: masking+multiple+outliers+leave-one-out+deletion+diagnostics             -> 0 hits
esearch: differential+misclassification+exposure+electronic+health+record+device  -> 0 hits
esearch: ceiling+effect+bounded+statistic+permutation+test+one-sided+artifact     -> 0 hits
```

Every PMID quoted in the body above was independently `efetch`-ed in full and the quoted sentence copied
verbatim from that output; none was taken from the `esearch` snippet or a search-engine summary.
