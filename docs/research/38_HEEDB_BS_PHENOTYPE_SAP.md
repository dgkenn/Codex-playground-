# Statistical analysis plan — ICU burst-suppression phenotypes and brain–body coupling (HEEDB + OMOP)

**Written BEFORE the cohort data was assembled.** Extraction is running; no phenotyping or outcome analysis has
been run. This document fixes the design, the primary hypotheses, and the falsification criteria in advance,
because the alternative — assembling and modelling in the same pass — is how this project has already produced
one retracted headline claim.

---

## 1. Why this study

Guay, Agrawal, Tseng, Gallo, Schreier and Brown, *Anesthesiology* 2025;143(6):1595–1618, state three open
problems. All three verified verbatim against the source text:

> "Determining the exact etiology of burst suppression in the ICU can be challenging and likely contributes to
> heterogeneous results in clinical outcomes studies."

> "Future work characterizing distinct burst suppression phenotypes and the underlying mechanisms will help
> refine our understanding of this brain state."

> "Future studies investigating the use of continuous frontal EEG in critically ill patients will provide new
> insights into the bidirectional interactions between the brain and the rest of the body."

This study addresses the first two directly and the third partially.

**The core idea.** ICU burst suppression is aetiologically heterogeneous — sedative-induced, post-anoxic,
metabolic, septic, hypothermic, post-status — and the review's argument is that pooling these is *why* outcome
studies disagree. That heterogeneity is invisible to the EEG alone but largely *recoverable from the linked
clinical record*. HEEDB is unusual in having both.

## 2. Cohort

| | |
|---|---|
| patients with burst suppression labelled on an EEG report | **7,323** |
| burst-suppression reports | 22,057 |
| dominant recording service | LTM (continuous ICU monitoring), 17,711 reports |
| linkage to the OMOP clinical model | **100 %** (verified against the 15M-row person table) |
| patients with a death record | **3,304 (45 %)** |

Comparator group: EEG patients **without** any burst-suppression label (≈41,900), for contrasts requiring one.

## 3. Aetiology assignment — pre-specified, not learned

Assignment uses `condition_occurrence` (ICD-9/10) within the admission containing the EEG, plus `drug_exposure`
in the 24 h preceding the EEG. Categories are fixed here and are **not** mutually exclusive; a patient may carry
more than one, and the count of concurrent aetiologies is itself an exposure.

1. **Sedative/iatrogenic** — propofol, midazolam, pentobarbital, ketamine, dexmedetomidine exposure overlapping
   or immediately preceding the EEG.
2. **Post-anoxic** — cardiac arrest, anoxic brain injury, hypoxic-ischaemic encephalopathy.
3. **Status epilepticus** — status codes, or a treated seizure episode.
4. **Metabolic/organ failure** — hepatic failure/encephalopathy, renal failure, hyperammonaemia, hypoglycaemia.
5. **Sepsis/infection** — sepsis, septic shock, meningitis, encephalitis.
6. **Structural** — traumatic brain injury, intracranial haemorrhage, large infarct.
7. **Hypothermia** — targeted temperature management or recorded hypothermia.
8. **Unexplained** — none of the above. This group is of specific interest: it is where the review's "challenging
   to determine" problem actually bites.

**Why rule-based rather than clustered.** A data-driven clustering would be more fashionable and less
interpretable, and its clusters would be defined partly by the outcome-associated variables we then test against
outcome. Rule-based assignment from prior clinical categories keeps the aetiology definition independent of the
outcome. An unsupervised clustering is pre-specified as a *secondary*, exploratory analysis only, reported as such.

## 4. Primary hypothesis and its falsification

**H1 — aetiology modifies the burst-suppression/mortality association.**
Among patients with burst suppression, mortality differs by aetiology after adjustment for age, sex, and
comorbidity burden.

* Primary estimand: risk difference in mortality across aetiology categories, on the linear probability scale
  (collapsible; odds ratios are not, and this project has already been bitten by treating an OR change as
  mediation).
* Primary test: a **formal interaction/heterogeneity test across categories**, not a series of category-wise
  significance statements. Comparing which categories are individually significant is the
  difference-of-significance error, which has appeared **three times** in this project and caused one retraction.
* **Falsification: if the heterogeneity test is null, the review's premise — that aetiological pooling explains
  heterogeneous outcome findings — is not supported in these data, and that is the result we report.** It would
  be a genuinely useful negative for the field.

**H2 — the sedative/iatrogenic phenotype carries a different prognosis from the injury phenotypes.**
Pre-specified direction: iatrogenic suppression carries **lower** mortality than post-anoxic or structural
suppression, because it reflects a treatment decision rather than the brain's response to injury. This is the
single most clinically consequential contrast, and the one an intensivist would actually act on.

**H3 (exploratory) — brain–body coupling differs by phenotype.**
Using OMOP vitals, test whether burst suppression is followed by a change in mean arterial pressure over the
subsequent charting interval, and whether that coupling differs by aetiology.
**Stated limitation, binding:** ICU vitals are charted every 15–75 min. The VitalDB finding operates at 60–120 s.
**This analysis therefore cannot test the same phenomenon** and must not be described as replicating it. It tests
a coarse, hours-scale analogue, and a null here is uninformative about the sub-minute result.

## 5. Analysis rules fixed in advance

1. **Range-check every physiological value against physiological possibility before modelling.** MAP restricted to
   [30, 150] mmHg. This is not optional: failing to do it inflated every estimate in the VitalDB arm ~3×.
2. **Cluster at the patient level** for all inference. Multiple EEGs per patient are not independent.
3. **A negative-control outcome is mandatory.** Test the exposure against something it cannot cause (e.g. a
   pre-admission value). In the VitalDB arm this is what revealed the AKI association to be confounded.
4. **Report a heterogeneity/interaction test wherever two groups are compared.** Never compare significance.
5. **Every reported number must be regenerable from a committed script.** An independent fact-check of the
   VitalDB summary found figures produced by inline scripts that were never persisted.
6. **Effect sizes on an interpretable scale**, with intervals, and the analysed n stated per result (not the
   extracted n — these differ, and conflating them was an error in the VitalDB write-up).

## 6. What this study cannot do

* It cannot establish causation. Aetiology is not randomised, and sicker patients receive both more sedation and
  more EEG monitoring.
* **Indication bias is severe and unfixable here**: continuous EEG is ordered *because* clinicians are worried.
  The cohort is not a sample of ICU patients but of ICU patients someone was concerned about.
* Burst suppression is a **clinician label** from a report, not a quantified burden. A quantified detector run on
  the raw EDF is a planned extension; the label is the starting point, and label heterogeneity across readers is
  an unmeasured error source.
* It cannot test the sub-minute temporal mechanism (Section 4, H3).

## 7. Relationship to the VitalDB work

The VitalDB analysis establishes, in a controlled setting with sub-minute resolution, that the suppressed state
is followed by a vasodilatory pressure fall specific to suppression rather than to anaesthetic depth. It is the
*motivating physiology*. This study asks the different and larger question the review actually poses: whether ICU
burst suppression is aetiologically separable, and whether that separation explains the field's heterogeneous
outcome literature.

They are complementary, not confirmatory. Neither validates the other.
