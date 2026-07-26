# A mechanism that replicates externally — and the half of it that does not

**Goal: find an externally replicable mechanism, tested against the full constraint set rather than the
convenient part of it.** This records what survived, what was withdrawn, and what the existing literature says
about both. All citations were fetched from the MEDLINE record via NCBI E-utilities and the two load-bearing
ones were re-verified by hand before being used.

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

**Increment over burden replicates**: +0.055 [+0.035, +0.094] in I-CARE against **+0.047 [+0.011, +0.083]** in
HEEDB. Burden alone 0.713 → burden + morphology 0.768.

**And it survives adjustment for burden** — the arm that decides whether quality is separable from quantity
(standardised log-odds, burden in the model):

| feature | coefficient |
|---|---|
| **intra-burst 8–30 Hz** | **+0.522 [+0.305, +0.773]** ✔ |
| **burst amplitude** | **+3.502 [+2.204, +5.279]** ✔ |
| burst duration | −0.051 [−0.517, +0.138] |
| burst rate | −0.147 [−0.353, +0.061] |

So **spectral content and amplitude of the bursts carry outcome information that suppression burden does not**,
in two independent cohorts. That is the externally replicable mechanism component.

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
cardiac arrest, the **spectral content and amplitude of the bursts** carry prognostic information independent
of how suppressed the record is. Suppression burden measures *how much* is gone; burst content reports
*what kind of activity remains*. A prior independent study reports the same direction for spectral content
(PMID 30422916).

**Interpretation offered, not established:** burst content plausibly reports thalamocortical organisation,
given graded selective thalamic vulnerability after global ischaemia (PMID 12435429) and the observed coupling
of thalamic damage to suppression ratio in humans (PMID 37731916). This is an interpretation consistent with
the data and with independent anatomy, not a measured mechanism — no thalamic imaging exists in our cohorts.

**Withdrawn:** the burst-duration direction, and any claim that burst generation requires thalamocortical
integrity.

**Open, and the next test:** stereotypy. It is Fong's only independent predictor and our HEEDB estimate was
weak. Recomputing it in I-CARE at 1 s and 2 s is running; if stereotypy dominates spectral content there, the
mechanism should be restated around burst *similarity* rather than burst *content*, and this document revised
accordingly.
