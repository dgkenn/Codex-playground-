# A mechanism that replicates externally — and the half of it that does not

**Goal: find an externally replicable mechanism, tested against the full constraint set rather than the
convenient part of it.** This records what survived, what was withdrawn, and what the existing literature says
about both. All citations were fetched from the MEDLINE record via NCBI E-utilities and the two load-bearing
ones were re-verified by hand before being used.

> **⚠ READ §7 AND §8 FIRST.** Two claims in the sections below have since been withdrawn: **burst amplitude**
> (its sign inverts under corrected exposure) and the **predictive increment** from morphology (it is
> significant in one cohort and not the other under a valid out-of-bag bootstrap). What survives is the
> *association* of spectral content and stereotypy with outcome, independent of burden, in I-CARE. The
> superseded text is retained with strike-throughs so the corrections are visible rather than silent.

---

## 1. The candidate, and what it had to survive

**Thalamocortical generator integrity.** Burden counts how much generator capacity is gone; burst **morphology**
reports whether what remains is still organised. Quantity versus quality.

It was required to explain the project's negatives as well as its positives — including N7 (burden is *not* a
fixed quantity over the first 48 h post-arrest) and N8 (post-anoxic status epilepticus arises in severely
injured brains, so silence-equals-severity is false). The full constraint set is in the docstring of
`analysis/icare_burst_morphology.py`.

**Directions were pre-registered from HEEDB before the external data was touched**: survivors' bursts LONGER
(2.87 s vs 1.84 s) and SLOWER (12.0 % vs 25.0 % of intra-burst power above 8 Hz).

---

## 2. Result: the frequency-content half replicates, the duration half does not

External cohort: **I-CARE, 559 patients**, five hospitals, our own detector run on their raw EEG.

| feature | poor outcome | good outcome | HEEDB direction | verdict |
|---|---|---|---|---|
| suppression burden | 0.559 | 0.305 | higher in deaths | **REPLICATES** |
| intra-burst 8–30 Hz | 0.214 | 0.179 | faster in deaths | **REPLICATES** |
| burst duration | 13.58 s | 26.00 s | longer in survivors | **n.s.** |
| burst amplitude | 27.26 | 13.73 | (exploratory) | large |

**Increment over burden** — *these figures are SUPERSEDED; see §8. Under a valid out-of-bag bootstrap the
increment is +0.070 [+0.006, +0.121] in I-CARE and +0.036 [−0.019, +0.076] in HEEDB, i.e. significant in one
cohort and not the other, and the predictive claim is withdrawn.* As originally computed: +0.055 [+0.035,
+0.094] in I-CARE against +0.047 [+0.011, +0.083] in HEEDB.

**And it survives adjustment for burden** — the arm that decides whether quality is separable from quantity
(standardised log-odds, burden in the model):

| feature | coefficient |
|---|---|
| **intra-burst 8–30 Hz** | **+0.522 [+0.305, +0.773]** ✔ |
| ~~burst amplitude~~ *(WITHDRAWN, §7)* | +3.502 [+2.204, +5.279] |
| burst duration | −0.051 [−0.517, +0.138] |
| burst rate | −0.147 [−0.353, +0.061] |

So **spectral content of the bursts is associated with outcome independently of suppression burden**. Note the
wording: an *association* independent of burden, not a demonstrated gain in predictive accuracy — §8 withdraws
the latter.

---

## 3. The burst-duration claim is withdrawn, for three independent reasons

1. **It does not replicate** — n.s. in I-CARE and null once burden is adjusted for.
2. **The measurement is not comparable across cohorts.** The same code gives median burst durations of
   1.84–2.87 s in HEEDB and 13.6–26.0 s in I-CARE. In I-CARE's long continuous segments, "burst duration"
   becomes largely the inverse of burden — a less-suppressed record has long unbroken runs — so it is not
   measuring burst morphology there at all. This is a defect in the feature's portability, not a finding.
3. **A well-powered contemporary study reports the opposite direction.** Fong et al., *Neurocrit Care* 2025
   (**PMID 39900751**, 203 post-arrest patients with burst suppression), quoted from the MEDLINE record:

   > "mortality was associated with **longer bursts**, longer IBIs, and higher burst correlation coefficients
   > (i.e., bursts that were more similar to each other) only when allowing analysis of the first 2 s of bursts"

   Their duration effect points the other way from ours. Critically, it **did not survive their own
   multivariate adjustment**:

   > "the only independent EEG predictor of mortality was the **burst correlation coefficient** measured over
   > 2 s (adjusted odds ratio 4.82 [95% confidence interval 1.21-8.42], p = 0.009)"

   Both their duration finding and ours are univariate artefacts of something else. Theirs points at
   **stereotypy**, which our I-CARE extraction had omitted and is now being recomputed at both 1 s and 2 s so
   the comparison can be made on their terms.

---

## 4. The mechanism must be weakened: generation versus content

The strong form — *bursts require an intact thalamocortical loop* — is **refuted by existing work**. Wennberg
et al., *Electroencephalogr Clin Neurophysiol* 1997 (**PMID 9191587**) report that after functional
hemispherectomy, with cortex completely disconnected from thalamus and subcortex, "burst-suppression activity
appeared over isolated cortex **in all cases**". Deafferented cortex generates burst suppression by itself.
The dominant computational account (Ching *et al.*, *PNAS* 2012, PMID 22323592) likewise needs no
thalamocortical loop, only cortical metabolic dynamics and ATP-gated potassium channels.

**What survives is the weaker and more specific claim**: burst *generation* is cortical, but burst *content*
reports thalamocortical organisation. Three independent lines support it:

- **Muthuswamy et al., *Neuroscience* 2002 (PMID 12435429)** — "strong evidence for selective vulnerability of
  thalamic relay neurons and its network interactions... leading to a **thalamo-cortical dissociation** after
  prolonged durations of global ischemia", dose-dependent in ischaemia duration with cortical N20 relatively
  preserved. The thalamus fails before the cortex, and by a graded amount.
- **Sohn & Kim, *IBRO Neurosci Rep* 2023 (PMID 37731916)** — in adult post-arrest patients, "thalamic GWRs
  showed a negative correlation to the [EEG suppression ratios]". Thalamic structural damage tracks measured
  suppression in humans, which is our exposure.
- **Sekar, Schiff, Labar & Forgacs, *J Clin Neurophysiol* 2019 (PMID 30422916)** — *"Spectral Content of
  Electroencephalographic Burst-Suppression Patterns May Reflect Neuronal Recovery in Comatose Post-Cardiac
  Arrest Patients"*; a prominent theta feature was present in patients regaining consciousness and absent in
  those who did not. **This is the closest prior analog to our replicated finding and points the same way** —
  slower intra-burst content with recovery, faster with death.

Amplitude has independent precedent too: Ruijter, Hofmeijer & van Putten, *Clin Neurophysiol* 2018
(**PMID 29807232**) — "the amplitude ratio between bursts and suppressions reliably predict the outcome of
postanoxic coma".

---

## 5. What is now claimed

**Claimed, and externally replicated in two cohorts with our own detector:** within burst suppression after
cardiac arrest, the **spectral content and stereotypy of the bursts** carry prognostic information independent
of how suppressed the record is. Suppression burden measures *how much* is gone; burst content reports
*what kind of activity remains*. A prior independent study reports the same direction for spectral content
(PMID 30422916).

**Interpretation offered, not established:** burst content plausibly reports thalamocortical organisation,
given graded selective thalamic vulnerability after global ischaemia (PMID 12435429) and the observed coupling
of thalamic damage to suppression ratio in humans (PMID 37731916). This is an interpretation consistent with
the data and with independent anatomy, not a measured mechanism — no thalamic imaging exists in our cohorts.

**Withdrawn:** the burst-duration direction, and any claim that burst generation requires thalamocortical
integrity.

## 6. Stereotypy: the competing finding also replicates, and the two are independent

Fong's only independent predictor was burst similarity, and our first I-CARE extraction omitted it. Recomputed
at 1 s and 2 s on the same 527 patients, **his finding replicates too** — and does not displace ours.

| feature, adjusted for burden (standardised log-odds) | coefficient |
|---|---|
| **intra-burst 8–30 Hz** | **+0.500 [+0.291, +0.756]** ✔ |
| ~~burst amplitude~~ | +2.252 [+0.844, +3.985] | **WITHDRAWN — see §7** |
| **stereotypy (1 s)** | **+1.040 [+0.457, +1.825]** ✔ |
| stereotypy (2 s) | −0.114 [−0.549, +0.398] |
| burst duration | −0.027 [−0.658, +0.200] |
| burst rate | −0.134 [−0.367, +0.064] |

Direction replicates as Fong predicts: stereotypy is higher in poor outcome (1 s: 0.043 vs 0.006; 2 s: 0.032 vs
0.008). With stereotypy included the morphology increment over burden rises to **+0.073 [+0.043, +0.123]**
(burden alone 0.691 → 0.764).

**The two findings are independent channels, not rivals.** Both spectral content and stereotypy survive in the
*same* model, each adjusted for burden and for the other. Two groups measured different things and both were
right.

**One disagreement, reported rather than smoothed.** Fong concluded "including the first 2 s of the bursts was
superior to limiting the analysis to 0.5-1 s". We find the reverse: stereotypy at **1 s survives adjustment and
2 s does not**. Our bursts are also far longer than his analysis window implies, so the two are not measuring
identical quantities; the window dependence is real and unexplained, and is a concrete point to raise with that
group rather than a discrepancy to bury.

**How this sharpens the mechanism.** Highly stereotyped, high-amplitude, fast bursts describe a *simple
autonomous cortical oscillator* — one mode, repeated. Slower, more variable bursts describe a network with a
richer repertoire. That is what loss versus preservation of thalamocortical modulation would look like, and it
now rests on three features that each survive adjustment for suppression burden, in two independent cohorts,
with the stereotypy channel independently reported by another group.

**Still open:**  It is Fong's only independent predictor and our HEEDB estimate was
weak. Recomputing it in I-CARE at 1 s and 2 s is running; if stereotypy dominates spectral content there, the
mechanism should be restated around burst *similarity* rather than burst *content*, and this document revised
accordingly.


---

## 7. CORRECTIONS after adversarial review (2026-07-27)

**Amplitude is withdrawn.** §2 and §6 above were written before the HEEDB morphology directions were
re-derived at the index recording. That re-derivation **inverts** amplitude's sign (early deaths 19.4 vs long
survivors 23.7, i.e. *lower* amplitude with death, where the legacy max-over-recordings extraction said
36.5 vs 26.7), and I-CARE gives the opposite sign again. A channel whose direction depends on the exposure
definition is not a finding. The tables above are struck through rather than deleted so the correction is
visible. **The mechanism rests on two channels: intra-burst spectral content and stereotypy.**

**The morphology analysis is conditioned on having measurable bursts, and that is not neutral.** Burst
morphology is undefined when a record contains fewer than four bursts — which happens precisely when
suppression is near-total. Measured in I-CARE: **80 of 607 patients (13.2 %) are excluded**, and they are
**80.0 % poor outcome against 60.3 % among those retained**; the NaN-dropped subgroup has median burden
**0.967** and **96.9 %** poor outcome. The same pattern holds in HEEDB.

This is intrinsic, not a coding defect: *you cannot measure the shape of bursts in a brain that has almost
none*. The consequence is a real limit on the claim and on any clinical reading of it — **burst morphology can
only add information in the middle of the burden range, because at the top of that range it does not exist.**
Every morphology statement in this document should be read as conditioned on "among patients whose EEG contains
at least four identifiable bursts". The burden findings are unaffected; they use all patients.

---

## 8. Downgrade after a valid bootstrap (2026-07-27)

The increments quoted throughout this document used a bootstrap that either resampled **fixed** out-of-fold
predictions (ignoring refit variance) or refit and evaluated on the **same** resample (putting patients in train
and test). Both are wrong. Recomputed with an **out-of-bag** bootstrap — train on the resample, evaluate on the
patients not drawn:

| increment over burden | as reported | out-of-bag |
|---|---|---|
| I-CARE | +0.073 [+0.043, +0.123] | **+0.070 [+0.006, +0.121]** |
| HEEDB | +0.047 [+0.011, +0.083] | **+0.036 [−0.019, +0.076]** |

**The morphology increment is significant in one cohort and not the other**, and where it holds the lower bound
is +0.006. The claim "morphology adds predictive value" is therefore **not supported consistently** and is
withdrawn as a predictive claim.

**What survives is narrower and still worth stating.** The adjusted *associations* in I-CARE are robust —
spectral content +0.500 [+0.311, +0.755] and stereotypy +1.040 [+0.413, +1.894], each controlling for burden
and for the other. Association independent of burden is a mechanistic statement; incremental AUC is a clinical
utility statement. **This work supports the first and not the second**, and conflating them would be the
overclaim.
