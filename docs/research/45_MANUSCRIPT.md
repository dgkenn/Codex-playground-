# Quantitative suppression burden stratifies near-term mortality inside a guideline category that treats all patients within it identically

*Single-document account of the finding, its limits, and its mechanistic reading. Supersedes nothing — the full
test-by-test record is `41_RESULTS_LEDGER.md` (315 results), the gap analysis is `43_GAP_ANALYSIS_BROWN.md`,
and the mechanistic argument is `44_MECHANISM_AND_PRIOR_WORK.md`.*

---

## Abstract

After cardiac arrest, ERC-ESICM prognostication classifies EEG into **highly malignant**, **malignant** and
**benign** tiers (Westhall, *Neurology* 2016, PMID 26865516). The scheme is categorical: every patient inside
the highly-malignant tier formally carries the same information. In 2,951 post-arrest patients with EEG and an
ascertained death across two hospitals, we measured suppression **burden** directly from the raw EEG at each
patient's index recording and found that it stratifies three-day mortality **29.5 % → 73.1 %** within that
single category. Burden adds **+0.100 [+0.082, +0.118]** cross-validated AUC over the category itself
(pre-registered threshold +0.03), is **well calibrated** (intercept −0.013, slope 0.980), and replicates
across hospitals (0.679 / 0.669). Serial recordings show burden behaves as a **fixed quantity measured with
error** (ICC 0.815) rather than a reversible state — consistent with it indexing a cerebral metabolic rate that
is low because tissue has been lost, which extends the metabolic model of burst suppression (Ching *et al.*,
*PNAS* 2012, PMID 22323592) into the post-anoxic setting. **This is a statement about information present in
the recording, not a recommendation to act on it**: 46 % of these patients die within three days, the window in
which withdrawal decisions are made, and four independent instruments failed to separate withdrawal-mediated
from biological death in this data source.

---

## 1. Background

Westhall *et al.* classify post-arrest EEGs as, quoted from the MEDLINE record:

> "highly malignant (suppression, suppression with periodic discharges, burst-suppression), malignant (periodic
> or rhythmic patterns, pathological or nonreactive background), and benign EEG (absence of malignant features)"

reporting 37 % highly malignant and that "all had a poor outcome (specificity 100%, sensitivity 50%)". Whether
burst-suppression patterns are reliably associated with adverse outcome remains actively contested — Shanker,
Abel, Schamberg and Brown (*Front Psychol* 2021, PMID 34177731) frame their review around exactly this
controversy.

The question here is narrower and answerable: **within the tier already used to justify the gravest decisions,
is there quantitative structure that the category discards?**

---

## 2. Methods

**Cohort.** HEEDB (Harvard EEG Database), two hospitals. 2,951 patients with (a) an ICD-coded anoxic/cardiac
arrest condition, (b) at least one EEG, (c) an ascertained death record. Every patient has a death record, so
the outcome is *how soon*, not *whether* — an ascertainment-immune design chosen deliberately.

**Exposure.** Suppression burden = fraction of the record below a 5 µV amplitude threshold in ≥0.5 s runs,
bipolar longitudinal montage, computed over four 2-minute windows sampled across each recording and taken as
the maximum. **All exposures — burden, EEG category, and morphology — are taken from the INDEX recording**, the
one at which the outcome clock starts.

**Outcome.** Death within 3 days (primary) and 30 days of the index recording.

**Analysis.** Logistic regression, 5-fold cross-validation × 5 repeats, bootstrap CIs (patient-level).
Cross-hospital validation fits at one site and evaluates at the other.

---

## 3. Results

### 3.1 The finding (Figure F1)

| burden quintile | n | dead by 3 days | dead by 30 days |
|---|---|---|---|
| Q1 lowest | 193 | **29.5 %** | 59.1 % |
| Q2 | 192 | 35.4 % | 70.3 % |
| Q3 | 193 | 38.9 % | 79.8 % |
| Q4 | 192 | 52.6 % | 87.0 % |
| Q5 highest | 193 | **73.1 %** | **96.4 %** |

A 2.5-fold range of three-day mortality inside one guideline label, monotone across quintiles.

### 3.2 It adds to the guideline rather than restating it (Figure F3)

| model | CV AUC |
|---|---|
| Westhall-style category alone | 0.645 |
| **category + measured burden** | **0.745** |
| **increment** | **+0.100 [+0.082, +0.118]** |

Burden's log-odds coefficient is +1.587 (OR 4.89 across the range). Cross-hospital: **0.679 / 0.669**.

### 3.3 It is calibrated, not merely discriminating (Figure F2)

Mean predicted 3-day risk 0.308 vs observed 0.308; calibration intercept **−0.013** (ideal 0), slope **0.980**
(ideal 1), with observed tracking predicted across all ten deciles.

### 3.4 Morphology adds a further, interpretable increment

Five named morphology features add **+0.047 [+0.011, +0.083]** over burden within the highly-malignant category
(n=604). Comparing outcome extremes:

| | dead ≤3 days | alive >180 days |
|---|---|---|
| suppression burden | 0.746 | 0.386 |
| intra-burst 8–30 Hz fraction | 0.250 | 0.120 |
| burst duration | 1.84 s | 2.87 s |
| generalized slowing present | **29.7 %** | **74.9 %** |
| posterior dominant rhythm present | 12.3 % | 24.3 % |

Short, high-frequency bursts on a background with no slowing and no posterior rhythm mark the patients who die
within days. Every term is a named physiological quantity with a signed coefficient; there is no learned
representation anywhere in this analysis.

### 3.5 Burden behaves as a fixed quantity (Figure F4)

Among patients with serial recordings, averaging two readings predicts death **better (0.787)** than taking the
most recent **(0.747)** — the signature of a constant observed with noise. Decomposing a pair into mean and
difference, the difference carries no signal (coefficient +5.88 pp [−17.13, +26.58]) and adding it makes
prediction worse (−0.013). Direct measurement error: **ICC 0.815** for one window, 0.898 for the average of two.

---

## 4. Mechanistic reading

Ching, Purdon, Vijayan, Kopell and Brown (*PNAS* 2012, PMID 22323592) propose that burst suppression across
anaesthesia, hypothermia, coma and infantile encephalopathy shares one proximate cause: **"a decrease in
cerebral metabolic rate, coupled with the stabilizing properties of ATP-gated potassium channels"**.

If burden indexes cerebral metabolic rate, its reversibility should depend on *why* the rate is low: reversible
under anaesthesia or hypothermia (living neurons, suppressed), **fixed after neuronal death** (no metabolism to
restore). Our cohort is the second case and behaves as that case predicts. This also explains why burden is
brain-specific rather than a whole-body ischaemic dose marker (mediation through organ-injury codes absorbs
2.6 %; cardiac and pressor gradients are *steeper* in sepsis than after arrest), and why morphology and
persistence add so little over burden itself.

**The prediction was made, and then tested.** If burden indexes cerebral metabolic rate, the *same construct*
must behave reversibly when the cause is drug. We tested this in **VitalDB** (1,848 intraoperative cases with a
device suppression-ratio series; 967 suppressing), using **no outcome variable** — a fixed quantity plus noise
and a time-varying state are distinguishable from the series alone:

| test | anaesthetic (VitalDB) | post-anoxic (HEEDB) |
|---|---|---|
| autocorrelation vs lag | 0.973 → **0.484** (decays) | fixed-quantity behaviour |
| ICC of one reading | **0.313** | **0.815** |
| recovery over the case | peak 3.99 % → **1.20 %** (**70 % resolution**) | does not resolve; serial change carries no signal |

**The prediction held where it could have died.** Had VitalDB also shown fixed-quantity behaviour, burden would
have been a stable patient trait and the post-anoxic result would have said nothing about tissue loss.

A fourth arm — whether suppression tracks effect-site concentration — **failed and is reported as failed**. The
within-case level correlation is *negative* (−0.298 [−0.310, −0.287]), which is pharmacologically backwards and
is the signature of a closed loop: anaesthetists turn the agent down when suppression appears, so suppressed
periods are the periods of reduced drug. The exposure is controlled in response to the outcome — structurally
the same confound as withdrawal in the post-anoxic cohort, moved from the outcome to the exposure. It carries no
weight in either direction.

**Limitation.** `devsr` is a device-computed ratio on a frontal montage, not our 5 µV bipolar burden, and
elective surgical patients differ from post-arrest ICU patients in far more than aetiology. This shows
*suppression* is reversible under anaesthesia, not that *our estimator* is.

---

## 4b. External replication (I-CARE)

The primary analysis is cross-**site** but within one health system. **I-CARE** — comatose post-cardiac-arrest
patients at five hospitals in an independent international consortium, with Cerebral Performance Category
outcomes — provides a cross-**system** test. n=561 with both outcome and a suppression measure; 62.0 % poor
(CPC 3–5).

The claim replicated is not "suppression is bad", which is not in dispute. It is that **among patients who are
already suppressed, quantitative burden still stratifies outcome**, so the categorical label discards real
information.

| test | result |
|---|---|
| poor outcome across burden quintiles | 45.1 % → **86.6 %**, monotone |
| **among the suppressed** (burden ≥0.05, n=417) | lowest tertile 49.3 % → highest **83.3 %**, **+34.1 pp [+23.2, +44.2]** |
| same at ≥0.10 / ≥0.20 | +33.3 pp [+23.4, +44.4] / +25.0 pp [+12.7, +36.4] |
| burden over a binary suppression flag | **+0.090 [+0.045, +0.156]** (registered threshold +0.03) |
| cross-hospital (fit one site, test others) | 0.619, 0.716, 0.690, 0.684 |

**Differences that must travel with this.** The outcome is CPC 3–5 at discharge or follow-up, not three-day
mortality; the suppression measure is I-CARE's own at hour 24, not our 5 µV burden at an index recording. This
replicates the *structure* of the claim on an independent cohort, not the identical estimand.

**On TUH**, which the pre-registration names as mandatory: the TUH EEG Corpus carries **no linked outcome
data** — its manifest schema has no outcome field — so a burden→mortality finding cannot be replicated there at
any effort. TUH remains the right target for externally validating the *measurement* against a clinician label
at a different health system, which is a different and lesser claim.

---

## 5. Limitations

1. **Withdrawal cannot be separated from biological death** in the three-day window. 46 % of highly-malignant
   patients die within it. **Four instruments were tried and all four failed**, for one identifiable reason —
   administrative data records what is *billed* or charted as a *state*, and withdrawal is neither: DNR codes
   (chronic status, median 42 d to death); sedation depth (circular); vasopressor discontinuation (the record is
   closed at death — 20.9 % tied to the death timestamp, **zero** patients between 1 min and 1 h before);
   terminal extubation (`procedure_occurrence` is a billing table — 31,324 rows, 7,971 ventilated patients,
   **zero** extubations, since extubation is not separately reimbursable). Acting on this score without a
   prospective study would be the self-fulfilling-prophecy mechanism the field already documents (Elmer,
   *Crit Care Med* 2023, PMID 36752628).
2. **The exposure is a crude estimator.** Thresholding-and-segmentation over 8 sampled minutes is the method
   burst suppression probability was introduced to replace (Chemali *et al.*, *J Neural Eng* 2013,
   PMID 24018288). It agrees with the clinician label at AUC 0.749 [0.747, 0.760] (n=27,948), and its noise
   *attenuates* associations — so the reported effects are, if anything, underestimates.
3. **Reactivity is not recorded**, so the Westhall category is reproduced without its nonreactive arm.
4. **Cross-site, not cross-system** — both hospitals share a health system and reporting infrastructure.
5. **Every patient has an ascertained death**; nothing here estimates the risk of death itself.
6. **Indication bias** — EEG is ordered because someone was worried.
7. **No positive tissue-level identification.** All three external references failed: NSE is absent from the
   database (2 rows in 551 parts), cause of death is 84.9 % blank, and the epileptogenicity test's premise is
   false because post-anoxic status epilepticus arises in severely injured brains (De Stefano, *J Neurol* 2023,
   PMID 36076090). The metabolic reading is an interpretation consistent with the data and an established
   model, **not an independently verified mechanism**.

---

## 6. What was eliminated on the way

Tested and ruled out as explanations: depth of suppression, age and sex, coexisting EEG findings, ceiling and
scale artefacts, reversibility, burst morphology as mediator, inconsistent use of the clinician label,
withdrawal as an explanation of the aetiology gap, "anoxic patients are simply sicker", posterior-rhythm
modification (withdrawn as reverse causation), drug-induced suppression, information redundancy, front-loading
of anoxic death, and whole-body ischaemic dose.

Three claims were **withdrawn after their own control tests failed**: a vasopressor withdrawal signature (a
charting artefact), a reversibility verdict (satisfiable by measurement error alone), and an epileptogenicity
reading (false premise). A look-ahead defect found by self-audit inflated the headline increment by roughly a
quarter and is corrected throughout; the finding survived it.

---

## 7. Next steps, in order

1. **Implement burst suppression probability** (state-space, binomial observation + Gaussian random walk) and
   re-run the headline under it.
2. **External replication on TUH** — cross-system rather than cross-site.
3. **Test the falsifiable prediction** in an anaesthetic cohort, where the metabolic reading requires burden to
   be reversible.
4. **Competing-risks survival** rather than binarised horizons.
