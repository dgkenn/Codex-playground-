# A guideline category that is treated as one thing contains a 2.7-fold range of near-term risk

**HEEDB, 2,951 post-cardiac-arrest patients with EEG and an ascertained death, two hospitals.**

*This supersedes the headline framing of `39_HEEDB_FINDINGS.md`. That document's aetiology comparison is
retained and still stands, but the analysis it led to is stronger and more useful than the comparison itself.
The full record of what was tested and eliminated on the way here is `41_RESULTS_LEDGER.md`.*

> ## ⚠ PROVISIONAL — the numbers below require one re-run before they are shown to anyone
>
> A self-audit on 2026-07-26 found **look-ahead in how the exposure was measured**. The outcome clock starts at
> the patient's earliest recording, but `heedb_vs_guideline.py` took suppression burden as the **maximum over
> all** of that patient's recordings, took the EEG category as the **OR over all** of their reports, and took
> morphology from whichever row was read last. A patient who survives accrues more recordings — and more
> chances at a high maximum — than one who dies on day two, so the exposure window was partly a function of the
> outcome.
>
> **How much of the cohort this can touch, measured rather than guessed** (`heedb_burden_lookahead_check.py`,
> n=7,577): 41.0 % of patients have a maximum drawn from a recording later than their first, 21.8 % differ by
> more than 0.10 burden, and mean burden falls from 0.244 (max) to 0.148 (index) — a 65 % relative inflation.
>
> **What this does and does not put at risk.** The direction is *conservative for the gradient*: only survivors
> can accrue extra recordings, so the contamination inflates burden among people who lived and works **against**
> the observed stratification rather than creating it. The existence of the effect is therefore not in doubt.
> What is not yet established is the **magnitude** and the framing of 0.741 as a bedside-prediction AUC — a
> predictor that partly postdates the prediction cannot be described that way.
>
> **The same defect class is in the landmark analysis in §5, and there it does not run conservatively.** A
> codebase sweep found the pattern in **17 scripts**. The worst instance is `heedb_landmark_class.py`, which
> collapsed suppression to a single per-patient flag — *suppressed on any recording, ever* — and then reused
> that one flag at every landmark. A landmark design exists precisely to guarantee the exposure was known at the
> landmark, and this violates it: at the 180-day landmark a patient can be counted as suppressed on the strength
> of a recording made on day 190, and even the day-0 estimate is affected. Worse, the likely direction **favours
> the reported conclusion** — late-labelled patients are survivors by construction, so they dilute the exposed
> group at late landmarks and make the excess look more exhausted than it is. The size of the violation is
> unmeasured, because it needs recording timestamps.
>
> **Status.** Both scripts are fixed and both now print the bias directly. `heedb_vs_guideline.py` defaults to
> `BURDEN_SCOPE=index`, resolving the index recording by timestamp (`BURDEN_SCOPE=max` reproduces the legacy
> run). `heedb_landmark_class.py` defaults to `LANDMARK_EXPOSURE=known-at-landmark` and tabulates, per landmark,
> how many patients' exposure came from their own future (`LANDMARK_EXPOSURE=ever` reproduces the legacy run).
> Both re-runs need HEEDB S3 credentials, which are absent this session. **Every AUC and quintile figure in §2,
> and every landmark figure in §5, is from a legacy run and must be replaced before use.**

---

## 1. The gap in current practice

Westhall et al., *Neurology* 2016 (PMID 26865516) — quoted verbatim from the MEDLINE record — classify
post-arrest EEGs into

> "highly malignant (suppression, suppression with periodic discharges, burst-suppression), malignant (periodic
> or rhythmic patterns, pathological or nonreactive background), and benign EEG (absence of malignant features)"

reporting that 37 % were highly malignant and "all had a poor outcome (specificity 100%, sensitivity 50%)". That
scheme is now embedded in ERC-ESICM prognostication guidance.

It is **categorical**. Every patient inside the highly-malignant tier carries, formally, the same information.

## 2. The finding

**They do not.** Within the highly-malignant category, quantitative suppression **burden** — measured from the
raw EEG by a fixed amplitude threshold, not read off a report — stratifies near-term mortality monotonically:

| burden quintile | n | dead by 3 days | dead by 30 days |
|---|---|---|---|
| Q1 lowest | 235 | **24.7 %** | 52.3 % |
| Q2 | 235 | 26.4 % | 55.7 % |
| Q3 | 234 | 34.2 % | 74.8 % |
| Q4 | 238 | 49.6 % | 80.7 % |
| Q5 highest | 232 | **66.4 %** | **93.1 %** |

A **2.7-fold** range in three-day mortality, and 52 % to 93 % at thirty days, inside a single guideline label.

**It adds to the guideline rather than restating it.** Discrimination for three-day death among the **1,875**
post-anoxic patients who have a measured burden (not all 2,951 — the comparison has to be made on patients for
whom both predictors exist):

| model | cross-validated AUC |
|---|---|
| Westhall-style category alone | 0.648 [0.616, 0.676] |
| **category + measured burden** | **0.741 [0.703, 0.790]** |
| | **increment +0.093** |

Registered threshold was +0.03. The increment is three times that.

**It replicates across hospitals.** Fitted at one site and evaluated at the other: **0.719** and **0.678**.

**There is no optimism to discount.** Burden alone gives in-sample 0.684 against cross-validated 0.682 — the
figures are the same, which is what a single well-behaved continuous predictor should do.

## 3. Burst morphology adds a further increment, and the direction is interpretable

Within the highly-malignant category, five named morphology features add **+0.036 cross-validated AUC** over
burden (0.632 → 0.668, n=662). Comparing the two outcome extremes directly:

| | dead ≤3 days | alive >180 days |
|---|---|---|
| suppression burden | 0.746 | 0.386 |
| intra-burst 8–30 Hz fraction | 0.250 | 0.120 |
| burst duration | 1.84 s | 2.87 s |
| generalized slowing present | **29.7 %** | **74.9 %** |
| posterior dominant rhythm present | 12.3 % | 24.3 % |

Short, high-frequency bursts on a background with **no** slowing and **no** posterior rhythm mark the patients
who die within days. A brain still producing slow activity, or still producing a posterior rhythm, is a brain
still producing something.

Every term is a named physiological quantity with a signed coefficient. There is no learned representation
anywhere in this analysis; the model can be read, checked and disagreed with.

## 4. What this is not, and the caveat that must travel with it

**This is a statement about information present in the recording. It is not a recommendation to act on it.**

Burst suppression is a guideline criterion that informs withdrawal of life-sustaining therapy, and **40.6 % of
these patients die within three days** — precisely the window in which withdrawal decisions are made. This
cohort cannot separate biological death from withdrawal-mediated death in that window, and this is a limit that
was tested rather than assumed: three instruments were tried and all three failed. DNR and palliative-care codes
document chronic care-limitation status, not an acute decision (median 42 days from code to death). Sedation
depth is circular, because burst suppression itself causes unresponsiveness. Vasopressor discontinuation timing
looked decisive and was retracted: the medication record is closed at the recorded time of death, so 20.9 % of
last-pressor ends are exactly tied to it and **not one patient in the database** has one falling between a minute
and an hour before death (`41_RESULTS_LEDGER.md` R279–R284). Answering this needs a source that timestamps the
decision — comfort-care order activation, ventilator termination — which this extraction does not contain. A
score that stratifies
risk inside a category already used to justify withdrawal could make its own predictions come true, which is the
self-fulfilling-prophecy mechanism this field already documents (Elmer, *Crit Care Med* 2023, PMID 36752628;
Mertens, *J Med Ethics* 2022, PMID 34253620). Acting on this without a prospective study would be that
mechanism, not a use of it.

Further limits, all established rather than asserted:
1. **Every patient here has an ascertained death.** The outcome is how soon, not whether. Nothing estimates the
   risk of death itself.
2. **Reactivity is not recorded** in this schema, so the Westhall category is reproduced without its
   nonreactive-background arm. The comparison is to a faithful-but-incomplete version of the guideline.
3. **Indication bias is unfixable.** EEG is ordered because someone was worried.
4. **Cross-site, not cross-system** — both hospitals share a health system and reporting infrastructure.
5. The **"benign" tier shows higher three-day mortality than "malignant"** (14.4 % vs 9.5 %), which is a warning
   that the bottom of this scheme is heterogeneous — it mixes genuinely preserved records with uninformative
   ones. The finding above concerns the top tier and does not depend on the bottom.

## 5. How this was arrived at, and what was eliminated

The route matters because it is the argument for believing the result. Starting from the observation that burst
suppression's prognostic weight differs by aetiology, the following were tested and **eliminated**: depth of
suppression, age and sex, coexisting EEG findings, ceiling and scale artefacts, reversibility, burst morphology
as a mediator, inconsistent use of the clinician label, withdrawal of care as an explanation of the aetiology
gap, "anoxic patients are simply sicker", a posterior-rhythm effect modifier (withdrawn as reverse causation),
drug-induced suppression, information redundancy, and front-loading of anoxic death.

The decisive turn was a landmark analysis: the aetiology excess is **exhausted among 30-day survivors** (gap
+0.832 from the EEG, +0.217 at a day-30 landmark, −0.206 at day 180). That identified the effect as a fixed
subgroup whose outcome is largely settled at the recording — which reframed the question from *why does
suppression mean more after anoxia* to *which of these patients is in that subgroup*, and it is the second
question that has a usable answer.

`41_RESULTS_LEDGER.md` records every test and its numbers, including the failures and the three occasions on
which a claim was withdrawn after a confound test.
