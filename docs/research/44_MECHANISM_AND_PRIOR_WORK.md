# What burden measures, read against the metabolic model of burst suppression

**This closes G1 and G3 of `43_GAP_ANALYSIS_BROWN.md`: the project had engaged none of the existing mechanistic
literature on burst suppression, and its central result had no physiological interpretation.**

All citations below were retrieved and quoted from the MEDLINE record via NCBI E-utilities. WebFetch is not
used for PubMed in this project — it fabricates content when the site serves a CAPTCHA, which cost this project
six wrong citations once already.

---

## 1. The existing mechanistic account

Ching, Purdon, Vijayan, Kopell and Brown, *PNAS* 2012 (**PMID 22323592**) propose a unifying mechanism for
burst suppression across every condition that produces it. Quoted from the abstract:

> "Burst suppression is an electroencepholagram (EEG) pattern in which high-voltage activity alternates with
> isoelectric quiescence. It is characteristic of an inactivated brain and is commonly observed at deep levels
> of general anesthesia, hypothermia, and in pathological conditions such as coma and early infantile
> encephalopathy. We propose a unifying mechanism for burst suppression that accounts for all of these
> conditions... **In each condition, the model suggests that a decrease in cerebral metabolic rate, coupled
> with the stabilizing properties of ATP-gated potassium channels, leads to the characteristic epochs of
> suppression.**"

The claim is strong and specific: burst suppression is not a family of look-alike patterns with different
causes, but **one phenomenon with one proximate cause — reduced cerebral metabolic rate** — reached by
different routes (anaesthetic, hypothermic, anoxic, developmental).

Shanker, Abel, Schamberg and Brown, *Front Psychol* 2021 (**PMID 34177731**) revisit this and note the open
clinical controversy directly:

> "we review the origins of burst-suppression patterns and use recent insights to weigh evidence in the
> controversy regarding **the extent to which burst-suppression patterns observed during profound
> anesthetic-induced brain inactivation are associated with adverse clinical outcomes.**"

That controversy is the context this project's result belongs in, and the project did not know it existed.

---

## 2. The reading this gives our central result

Our trajectory analysis (`41_RESULTS_LEDGER.md` R299–R304) established, without reference to any of this, that
suppression burden **behaves like a fixed quantity measured with error**:

- averaging two readings predicts death better (**0.787**) than taking the most recent (**0.747**) — the
  signature of a constant observed with noise, and the opposite of what a changing state does;
- once the pair is decomposed into mean and difference, the **difference carries no signal** (coefficient
  +5.88 pp [−17.13, +26.58]) and adding it makes prediction slightly worse (−0.013).

Read against the metabolic model, this stops being a statistical curiosity and becomes a statement about
metabolism. **If burden indexes cerebral metabolic rate, then its reversibility should depend entirely on why
the rate is low:**

| cause of reduced CMR | tissue state | expected behaviour of burden | setting |
|---|---|---|---|
| anaesthetic, hypothermia | living neurons, metabolism suppressed | **reversible** — falls as the drug clears or the patient rewarms | operating room, targeted temperature management |
| **neuronal death after anoxia** | tissue gone; no metabolism to restore | **fixed** — a constant, because the substrate is absent | this cohort |

Our cohort is the second row, and the observed behaviour is exactly what that row predicts. So the finding is
**not a contradiction of the metabolic model but an extension of it into the post-anoxic setting**: the same
proximate mechanism, distinguished by whether the metabolic depression is imposed on living tissue or reflects
its absence.

This also explains two otherwise loose results in the project:

1. **Why burden is brain-specific and not a whole-body ischaemic dose marker** (the organ-injury test:
   mediation through organ-injury codes absorbed 2.6 %, and cardiac/pressor gradients were *steeper* in sepsis
   than after arrest). A marker of *cerebral* metabolic rate has no reason to track renal or myocardial injury.
2. **Why persistence and morphology add so little over burden itself** (+0.047 for five morphology features).
   If burden already indexes the quantity that matters, there is no second dynamic quantity left to add.

**The prediction this makes, which would falsify it.** In a cohort where suppression is *anaesthetic* rather
than anoxic — post-operative, or pharmacologic coma for refractory status — burden should behave as a
**reversible** state: the difference between serial readings should carry information that the mean does not,
which is the exact opposite of what we observe here. That is a directional, falsifiable prediction on a
different population, and it is the natural next study.

---

## 3. Where our method sits against the existing one, honestly

Chemali, Ching, Purdon, Solt and Brown, *J Neural Eng* 2013 (**PMID 24018288**) introduced the standard
estimator, and its motivation is a direct criticism of what we currently do:

> "**Although thresholding and segmentation algorithms readily identify burst suppression periods, analysis
> algorithms require long intervals of data to characterize burst suppression at a given time and provide no
> framework for statistical inference.**"
>
> "We introduce the concept of the **burst suppression probability (BSP)** to define the brain's instantaneous
> propensity of being in the suppressed state... a state-space model in which the observation process is a
> binomial model and the state equation is a Gaussian random walk."

Our burden is a thresholding-and-segmentation ratio (5 µV, ≥0.5 s runs), maximised over four 2-minute windows —
8 sampled minutes of recordings that often run for hours. It has no time resolution and no per-recording
uncertainty. **This is the method BSP was written to replace, and the honest position is to say so.**

Two things can be said in mitigation, and neither is a defence of the estimator:

1. **It was validated before this was known.** Against the clinician burst-suppression label on the same
   recording, burden gives AUC **0.749 [0.747, 0.760]** on 27,948 matched recordings
   (`heedb_burden_validity.py`). It is measuring the intended thing, imperfectly.
2. **The measurement error works against us, not for us.** Q2's own result — that averaging two readings beats
   the most recent — is a demonstration that a single reading is noisy. A noisier exposure attenuates
   associations, so the reported gradient (29.5 % → 73.1 %) and increment (+0.100) are, if anything,
   underestimates of what a better estimator would find.

**What remains to be done** is to implement BSP on this cohort and re-run the headline under it (G2). Until
then the result should be described as holding *despite* a crude exposure, not as validated with a good one.

---

## 4. What is claimed, and what is not

**Claimed.** Suppression burden after cardiac arrest behaves as a fixed, brain-specific quantity, consistent
with indexing a cerebral metabolic rate that is low because tissue has been lost. This unifies the project's
Q2 and organ-injury results and sits inside an existing mechanistic framework rather than beside it.

**Not claimed.** No direct measurement of cerebral metabolic rate exists in this cohort. The three available
external references all failed — NSE is absent from the database (2 rows in 551 parts of the merged
`measurement` table), cause of death is 84.9 % blank, and the epileptogenicity test's premise proved false
because post-anoxic status epilepticus arises in severely injured brains (De Stefano, *J Neurol* 2023,
**PMID 36076090**). The metabolic reading is therefore an **interpretation that fits the observed behaviour and
an established model**, not an independently verified mechanism.

That distinction is the difference between a claim that survives review and one that does not.
