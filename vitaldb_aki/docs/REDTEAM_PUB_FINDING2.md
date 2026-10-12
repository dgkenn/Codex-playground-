# Reviewer 2 Red-Team — FINDING 2: Vasopressor Requirement → AKI (KDIGO)

**Role:** Adversarial publication-grade review, Critical Care Medicine / Anesthesiology /
Intensive Care Medicine tier. Date: 2026-06-30.

**Scoped claim under review:** Intraoperative/ICU vasopressor dose-requirement predicts
KDIGO AKI as a dose-response RISK MARKER (predictive risk-stratification); the renal-specific
CAUSAL claim explicitly does NOT hold (negative-control calibration kills it). Review is of
whether THAT scoped claim, in THAT honest framing, is publishable.

---

## CRITICAL CONCERNS (would-reject / conclusion-changing)

### CRITICAL-1: KDIGO baseline creatinine — code says MIN but docstring says FIRST (fatal internal inconsistency in the module header; partially resolved but audit trail is poisoned)

The docstring at the TOP of `requirement_aki_crossval.py` (lines 12–14) describes the primary
baseline as:

> "per-hadm baseline = min creatinine over the admission (a robust pre-injury floor)"

The `derive_aki()` function (line 133) then contradicts this by using `baseline_mode="first"`
as the primary, and correctly explains that `min` pushes the AKI rate to a ceiling (~0.87).
The final JSON confirms `baseline_mode: "first (admission); min reported as sensitivity"` and
the observed AKI rate is 0.482 (not 0.87), confirming FIRST is what was actually computed.

**Why this is CRITICAL:** The module-level docstring and the function are directly contradictory.
A reviewer or referee reading the file — or any attempt to reproduce — would find a document
that states one method and executes another. Even if the right choice was ultimately made,
**the audit trail is corrupted.** A reproducibility check by a journal statistical reviewer
would flag this immediately. The dossier and the crossval markdown correctly state FIRST
(admission), but the code artifact the manuscript would cite as the analysis script contains
a false description of the primary method. This is not a minor typo; it concerns the single
most consequential methodological choice in the AKI definition (see CRITICAL-2 below), and
it appears in the first thing any reader verifying the code will read.

**What this means:** Either the min-based run was run at some point and the docstring was not
updated, or the docstring was drafted for a prior version. Either way: **a serious journal
reviewer or statistical editor who audits the code will perceive a bait-and-switch.** This
alone could trigger a desk reject or a formal misconduct query even if the final numbers are
correct.

**Verdict: Must be corrected before submission. The docstring (lines 10–20 of the module) must
match the function. This is not cosmetic.**

---

### CRITICAL-2: KDIGO baseline creatinine is ADMISSION (first) creatinine — this is NOT the KDIGO 2012 standard; the standard requires a 7-day prior outpatient value or the lowest inpatient value if prior is unavailable

KDIGO 2012 (Kidney International Supplements 2012;2:1–138, Definition section 2.1) specifies:
baseline SCr is the **lowest value within the prior 3 months** (preferably outpatient). When
prior values are unavailable, KDIGO recommends using the **lowest inpatient value** as a
surrogate (the "back-calculation" approach), NOT the admission (first) value.

The authors have made the opposite choice. They use the admission (first) creatinine as
the primary baseline and explicitly reject the minimum as "over-calling AKI present on
admission." This is defensible as a clinical judgment — the first ICU creatinine on an
already-sick patient may itself be elevated — but it is a **material deviation from KDIGO
2012 guidance** that requires explicit justification, not just a sensitivity analysis.
The specific problem is:

1. The first-ICU creatinine on a norepi patient is often taken after resuscitation has
   already begun; it may already reflect partial injury, meaning it OVER-ESTIMATES the
   true baseline and UNDER-CALLS AKI (stated in the caveats, but not quantified).

2. Critically: the min-over-admission sensitivity gives AKI rate 0.87, which the authors
   attribute to "AKI present on admission" and "ceiling artifact." But this characterization
   is circular — if patients were admitted with AKI (very plausible in ICU norepi patients),
   the KDIGO standard would require a pre-admission value to detect it, not the admission
   value. Using the admission value as baseline in THAT case is precisely the under-call
   bias. The 0.87 rate may be more correct (AKI almost universal in critically ill patients
   on vasopressors), not an artifact.

3. The 48% AKI rate (FIRST baseline) vs 87% (min baseline) is a 1.8-fold swing in event
   rate. The dose-response gradient (Q1 38% → Q4 61%) sits against a background of 48%
   overall AKI. If the "true" rate is closer to 87%, the gradient still exists but the
   effect scale is very different. The gradient's interpretation — "requirement marks renal
   risk beyond measured severity" — is acutely sensitive to this choice because it changes
   who is in the reference (AKI-free) group.

**No external creatinine (prior 7-day ambulatory) was used.** In a database study of MIMIC-IV
this is feasible (outpatient_labs table exists). The authors did not use it, and the dossier
does not mention this omission. A reviewer will ask: "Did you check for pre-admission
creatinine in MIMIC-IV to construct a proper KDIGO baseline?"

**Verdict: MAJOR methodological concern. The deviation from the KDIGO 2012 standard must be
explicitly stated, justified on clinical grounds (not just because it avoids ceiling), and a
sensitivity using the recommended minimum-inpatient approach must be reported as primary (or
the first-creatinine must be defended with reference to the KDIGO guidance and the specific
cited paper). The current framing (min = sensitivity that "over-calls") is an inversion of
the KDIGO guidance, not a conservative choice.**

---

### CRITICAL-3: ESRD exclusion is ICD-code-only; baseline-creatinine threshold (≥4.0 mg/dL) is the only quantitative gate — CKD3-4 patients (eGFR 15–45) are INCLUDED and their creatinine dynamics are fundamentally different

The ESRD exclusion correctly captures ESRD/dialysis-dependent patients (ICD codes N18.6,
Z99.2, etc. and baseline ≥4.0 mg/dL). However:

1. **CKD stage 3b/4 (eGFR 15–44, SCr approximately 1.4–4.0 mg/dL) are fully included.**
   The KDIGO AKI threshold of +0.3 mg/dL absolute rise is much more easily met at a
   creatinine of 1.4 mg/dL (21% rise) than at 0.7 mg/dL (43% rise). CKD patients have
   attenuated creatinine kinetics (lower muscle mass, tubular secretion loss) and are at
   far higher baseline AKI risk. Their presence in the dataset inflates both overall AKI
   rate AND the apparent severity-gradient (high-dose vasopressor patients are more likely
   to have CKD, which is independently associated with AKI risk and with requiring higher
   vasopressor doses). A sensitivity excluding CKD (eGFR <60 at baseline, derivable from
   the first creatinine + age via CKD-EPI if sex is available) is standard.

2. **The comorbidity count used in the within-severity analysis is a raw ICD chapter count**
   (number of distinct ICD codes, not a Charlson or Elixhauser score). This is NOT a
   validated severity instrument. Charlson and Elixhauser both weight CKD differently from
   DM or heart failure. Using raw code count means a patient with 20 minor ICD codes looks
   "sicker" than a patient with 3 major ones. This is a significant limitation for the
   within-severity claim.

3. **No adjustment for pre-existing renal function (eGFR) is included in the within-severity
   model** (age + first-24h lactate + comorbidity count). eGFR is the primary predictor of
   AKI susceptibility and is strongly associated with vasopressor requirement (CKD is a risk
   for vasoplegia). This omission is the strongest residual confounder. A within-severity OR
   of 1.198 that does not adjust for baseline eGFR is not a severity-adjusted OR in the renal
   sense — it is an age/lactate/comorbidity-adjusted OR that leaves the most relevant
   confounder (renal function) uncontrolled.

**Verdict: CRITICAL for the within-severity claim. The 1.198 OR within severity is the pivotal
number defending the scoped claim. It has residual confounding by baseline renal function that
the analysis does not acknowledge as a specific limitation, let alone test. A sensitivity with
eGFR adjustment (even approximate) is required.**

---

### CRITICAL-4: Competing risk of death is not addressed — in a critically ill population (norepi ICU, mortality ~20–35%), competing risk of death before AKI event is NOT informative censoring; it changes the estimand

The analysis uses standard logistic regression (binary outcome: AKI yes/no per ICU stay).
In a population where a substantial fraction die before developing measurable AKI — or die
so rapidly that creatinine kinetics never manifest a detectable rise — the standard "any AKI
during admission" outcome is NOT equivalent to the KDIGO AKI incidence probability. Death
truncates the observation window before AKI can occur.

The problem for FINDING 2 specifically:
- High-requirement patients (Q4) are more likely to die (this is the whole point of FINDING 1).
- If Q4 patients die before AKI develops (or die WITH AKI that is indistinguishable from
  fatal organ failure), the AKI outcome in Q4 is a mixture of: (a) survived with AKI, and
  (b) died with evidence of renal injury on charts. If the creatinine was measured near death,
  it may be elevated and coded as AKI.
- Conversely, patients who die within 24–48h may have no post-admission creatinine measurement
  at all (missing-not-at-random), inflating the AKI UNDER-call in that subgroup.
- The net result is that the dose-response gradient (38%→61%) is a mixture of competing risk
  artifacts: higher death rate in Q4 increases both (a) observed AKI (death with rising SCr)
  and (b) missing AKI data (death before measurement). These effects partially cancel but
  in an unquantified way.

**No Fine-Gray competing risk analysis or cause-specific hazard model is reported.** This is
the standard approach in AKI literature in ICU populations (e.g., Hoste et al., JAMA 2015;
Kellum et al., Critical Care Medicine 2021). Any top-tier CCM or Anesthesiology reviewer will
ask for this. The currently reported AKI rate differences may reflect differential death
patterns rather than differential AKI risk.

**Verdict: CRITICAL for the dose-response gradient. The 38%→61% gradient across quartiles
cannot be interpreted without competing risk analysis. This is not a minor revision — it
requires re-analysis with appropriate methods (Fine-Gray or cause-specific hazard) or at
minimum a sensitivity restricted to survivors, with an honest statement that the gradient
may be inflated by competing risk.**

---

### CRITICAL-5: The INSPIRE negative-control calibration uses only 3 non-renal organ outcomes — this is an N=3 empirical null with one standard deviation computed on 3 points (ddof=1 gives 2 effective df); the z-score is unreliable

The calibration in `inspire_validation()` (lines 463–477) computes:
- null_mean = mean of 3 logORs (hepatocellular, cholestatic, coagulation)
- null_sd = std with ddof=1 on 3 points
- z = (renal_logOR - null_mean) / null_sd

With N=3 controls, the sample standard deviation has 2 degrees of freedom and very wide
uncertainty. The null_sd in the JSON is 0.0385 for the dose analysis. A z-score of −0.42
means the renal estimate is 0.42 null-SDs below the mean of 3 control estimates. The
claimed conclusion ("DIES within the null") rests on this z-statistic from a 3-point
distribution with unknown shape.

Specific concerns:
1. The three "negative control" outcomes (hepatocellular, cholestatic, coagulation injury)
   are not truly independent non-renal controls for norepi effect — norepi causes
   vasoconstriction of the hepatic artery and splanchnic circulation, so hepatic injury
   may itself be a plausible causal downstream effect of norepi, not a pure null.
   Cholestatic injury in ICU is often multifactorial but IS associated with hypoperfusion.
   If the controls are not truly null, the "empirical null" is contaminated upward, and the
   z-score calibration will over-reject the renal signal.

2. In the norepi_any (binary) analysis, null_sd is 0.4535 on 3 controls — enormous variance.
   This makes the calibration nearly uninformative (anything within 2 SDs of the mean
   "survives," and the mean itself is 0.93 logOR). This is not reported as a limitation
   of the calibration method.

3. There is no uncertainty quantification around the null distribution itself. A parametric
   z-score from 3 observations cannot be assumed normally distributed without justification.
   A permutation-based or bootstrap-based calibration would be more honest.

4. The INSPIRE subset restriction (n=50,546 medicated cases out of 130k total) is not tested
   for selection bias — were cases with medication records systematically different from
   those without? The organ_renal event rate in the restricted subset (2475/38963 = 6.4%)
   vs the full INSPIRE population is not reported.

**Verdict: CRITICAL for the causal arm. The "calibrated OR 0.98, z=−0.42 → DIES" conclusion
is the anchor of the whole scoping decision. If the calibration is methodologically weak (3-
point null, potentially contaminated controls, no uncertainty around the null), the "DIES"
verdict has no more statistical credibility than the "SURVIVES" verdict would have. The
dossier currently treats the calibration as definitive. It is not.**

---

## MODERATE CONCERNS (major revision required)

### MODERATE-1: The gradient (Q1 38% → Q4 61%) conflates severity with requirement — the test is age-adjusted only in the primary dose-response table

The primary dose-response table reports crude AKI rates per quartile with no covariate
adjustment. The text correctly notes that within-severity adjustment gives OR 1.198, but the
headline gradient (Q1 38% → Q4 61%, delta 22.3 percentage points) is unadjusted. Readers
will fixate on the raw gradient. Is this gradient driven by the higher age in Q4 patients?
By higher CKD prevalence? By higher SOFA? The table as reported confounds the dose-response
signal with a severity gradient.

A severity-adjusted dose-response table (e.g., crude AKI rate and severity-adjusted RR per
quartile) is the standard presentation. Reporting the within-severity OR as a separate section
without showing the gradient within severity strata obscures whether the gradient flattens.

### MODERATE-2: "Comorbidity count" as a severity adjustment is not a validated instrument

The within-severity model conditions on "comorbidity_count" which is derived in the code as
the total number of ICD codes (not chapters, as the docstring says — it increments 1 per row
of diagnoses_icd, which contains one code per row). This is a raw diagnosis code count, not
the Charlson Comorbidity Index, not Elixhauser, and not an ICD-chapter count. It ranges from
single-digit to potentially hundreds for complex patients. This is not cited or validated as
a severity instrument in any reference. A reviewer will ask: why was the Charlson or Elixhauser
score not computed? These are standard in MIMIC-IV analyses (the `icd_charlson` table in the
MIMIC-IV derived tables exists and was presumably used in FINDING 1 for mortality). The
inconsistency between findings (Charlson used for mortality, raw count used for AKI) is a
red flag.

### MODERATE-3: The AKI outcome requires ≥2 creatinine measurements; ~46% labevents snapshot means selection for "creatinine-measurable" patients is non-random

The code requires `len(sv) >= 2` (at least 2 creatinine values) to derive AKI. In a 46%
labevents snapshot, patients with only 1 creatinine available are excluded from the AKI
derivation entirely. These patients are likely: (a) very short stays (early death or rapid
discharge), or (b) cases where lab ordering was limited. Both scenarios correlate with
vasopressor requirement. If short-stay, early-death patients — who are in Q4 by requirement —
are excluded from the AKI denominator because they have <2 creatinine measurements, this
deflates the AKI rate in Q4 relative to the true value. This direction of bias ATTENUATES
the observed gradient.

The caveat is briefly mentioned ("missing-not-quite-at-random") but the direction and
magnitude are not analyzed. A Monte Carlo missing-data sensitivity would be appropriate;
the current "bias toward null" claim is asserted, not demonstrated.

### MODERATE-4: The within-lactate-tertile analysis — tertile T2 CI just barely excludes 1 (lower bound 1.005); this is not robust evidence of within-severity persistence

The within-lactate-tertile ORs in the JSON:
- T1: OR 1.273 [1.099, 1.501] — solid
- T2: OR 1.165 [1.005, 1.546] — lower CI 1.005, essentially touching 1
- T3: OR 1.136 [1.031, 1.304] — modest

The dossier reports "3/3 lactate strata keep OR>1 (CI excl 1)" but the T2 lower CI of 1.005
is barely above 1. In a bootstrap CI (400 bootstrap samples, as used here), small changes in
the bootstrap seed or inclusion criteria can flip this to "includes 1." The CI width for T2
is also notably wide [1.005, 1.546], consistent with a within-tertile N of only 1569 and
events of 674. Calling this a robust demonstration of within-severity persistence across 3/3
strata is overstated. Two of three strata have overlapping CIs (T2 and T3). The claim should
be moderated to "2/3 strata show clear within-severity signal; T2 borderline."

### MODERATE-5: Multiplicity — Finding 2 is one of 4 findings from the same MIMIC-IV/INSPIRE/VitalDB dataset, plus hundreds of exploratory analyses visible in the FINDINGS_LEDGER; no family-wise error rate correction for the 4-finding paper is reported

The HOSTILE_REVIEW_FINAL.md notes "multiplicity-immune" for the PRIMARY finding (Fisher-z
84/210) but Finding 2 is a SECONDARY discovery-from-MIMIC finding, not a pre-registered
primary. The PUBLICATION_DOSSIER presents 4 findings jointly. The family-wise alpha for 4
tests at 0.05 is 0.185 by Bonferroni. The age-adjusted OR 1.377 [1.248, 1.504] is significant
at any reasonable threshold, but the within-severity OR 1.198 [1.069, 1.362] with a lower CI
barely above 1.07 would require more careful multiplicity accounting, especially since the
overall MIMIC analysis searched multiple outcomes (mortality, AKI, fluid-pressor balance, NEE
load). The ledger discloses extensive search but no formal multiplicity correction framework
specific to the 4-finding paper's joint alpha is presented.

### MODERATE-6: INSPIRE estimand mismatch — intraoperative norepi in elective/semi-elective surgical patients is not the same estimand as ICU vasopressor requirement in critically ill norepi patients

The MIMIC discovery is in ICU norepi patients — critically ill, shock or near-shock,
median requirement 0.04–0.22 mcg/kg/min, AKI rate 48%. The INSPIRE "external validation"
is in intraoperative norepi use during anesthesia — a fundamentally different clinical
context (intentional vasopressor use for anesthesia-induced vasodilation, elective or
semi-elective surgery, very different AKI base rates). The INSPIRE organ_renal event rate
is 2475/38963 = 6.4%, vs MIMIC's 48%. This 7.5-fold difference in event rate alone suggests
these are different phenotypes.

Using INSPIRE as the "external validation of the AKI claim" when the event rate differs
by 7.5-fold and the clinical context is entirely different is not standard external
validation. It is at best a cross-context check. The failure to replicate in INSPIRE may
not reflect "causal arm dies" — it may reflect "the signal only exists at high doses in
truly vasopressor-dependent patients, not in anesthetic vasopressors at low doses." The
calibrated OR dying in INSPIRE is over-interpreted as evidence against the ICU-specific
causal claim.

---

## MINOR CONCERNS

### MINOR-1: Creatinine physiologic gate (0 < SCr ≤ 30 mg/dL) is too permissive

Values up to 30 mg/dL are included. Any value above ~15 mg/dL in a non-dialyzed patient
is almost certainly a transcription error or unit conversion artifact. A gate of ≤12 mg/dL
is more standard and should be used, with sensitivity at ≤15.

### MINOR-2: VitalDB validation uses Mann-Whitney without correction for covariates

The VitalDB NEPI-requirement analysis is a crude Mann-Whitney (requirement in renal+ vs
renal-), not age- or anesthesia-duration-adjusted. With N=157 and 17 events, this is
acknowledged as "directional only" — but the p=0.2574 is presented alongside MIMIC and
INSPIRE results in the overall table as if it "fails to replicate" when in fact 17 events
has approximately 15–20% power to detect OR=1.3 at α=0.05. This should be framed as
"underpowered to confirm or deny" rather than a neutral non-replication.

### MINOR-3: The VitalDB AKI definition for the composite cohort (organ_renal in the composite
outcome) may not be KDIGO-equivalent; no documentation of how organ_renal is defined in
the VitalDB composite

The any-pressor analysis uses organ_renal from cohort_composite.csv. How organ_renal is
derived in that composite (which already combines multiple feature modules) is not documented
in this file or in REQUIREMENT_AKI_CROSSVAL.md. If it is not KDIGO-aligned, the comparison
to the MIMIC KDIGO AKI is not same-construct validation.

### MINOR-4: Bootstrap CI uses 400 samples with no multiple-testing correction; CIs reported
to 3 decimal places (false precision)

Bootstrap CIs from 400 samples have quantile standard errors of approximately 0.0025–0.005
for typical OR ranges. Reporting lower bounds like "1.005" to three decimal places implies
precision that 400-sample bootstrap does not provide. 2000+ samples with bias-corrected
acceleration is the standard for publication-grade bootstrap inference.

### MINOR-5: The code `_hadm_comorbidity()` counts ALL ICD code rows, including duplicate
codes for the same condition across multiple claims

The function counts `cnt[hadm_id] += 1` for every row in diagnoses_icd.csv, which contains
one row per diagnosis per claim. A patient with the same ICD code appearing 5 times (once
per day, or across multiple claims) would have that code counted 5 times. This is not a
comorbidity index — it is a raw row count that captures coding intensity more than actual
comorbidity burden.

---

## Assessment of the INSPIRE Negative-Control Calibration Specifically

This is the lynchpin of the entire "predictive YES / causal NO" scoping. If the calibration
is sound, the honest scoping is defensible and even commendable. If it is weak, the paper is
claiming a methodologically sophisticated null result on shaky ground, which a reviewer will
see as falsely reassuring.

**What works:**
- The concept is correct: using non-renal organ injuries as a confounding null exploiting
  shared indication bias is a legitimate epidemiological design (similar to Wang et al.
  negative-control outcomes framework; Lipsitch et al. 2010 Epidemiology).
- The INSPIRE dataset is large (38,963 for the renal analysis), providing adequate power to
  detect dose-OR signals of this magnitude.
- The calibrated OR of 0.984 (z=−0.42) is directionally consistent with "no renal-specific
  signal beyond indication bias."

**What does NOT work:**
- The null is built from 3 controls. The precision of the null distribution is inadequate
  (2 df for sd). The "survives = z > 1.96" threshold applied to a z-score built on 3 data
  points ignores the uncertainty in the null estimate itself.
- The negative controls (hepatocellular, cholestatic, coagulation) are not biologically
  neutral to norepi — splanchnic vasoconstriction from norepi is a plausible mechanism for
  hepatic injury, which would contaminate the null upward, biasing toward the null and
  over-rejecting the renal signal.
- The dose metric in INSPIRE (continuous norepi dose per SD) is measured in an intraop
  setting where doses are typically 1/10 to 1/5 of ICU doses; the per-SD shift in INSPIRE
  is a different dose range than in MIMIC, making the two estimates non-commensurable.
- No uncertainty around the calibration (e.g., a 95% CI on the calibrated OR) is reported.
  If the null_sd has uncertainty (plausible given N=3 controls), the calibrated OR could be
  anywhere from meaningfully positive to meaningfully negative.

**Net assessment:** The calibration provides soft evidence against a renal-specific causal
claim, but not definitive evidence. The honest statement should be: "the point estimate of
the renal-specific effect is consistent with zero after calibration to the non-renal null,
but the calibration is based on 3 control outcomes and cannot rule out either a moderate
renal-specific effect or over-calibration from contaminated controls." The current binary
framing ("DIES") is over-confident.

---

## Statistical Power and Sample Size Assessment

- n=6,421, events=3,093 (AKI rate 48%): ADEQUATE for the primary OR per SD (well-powered).
- Within-severity n=4,549, events=2,084: ADEQUATE for the adjusted OR, though the attrition
  from 6,421 to 4,549 (29% loss to complete-case) is not characterized by exposure quartile.
  If lactate missingness correlates with requirement (plausible: sicker patients may have
  more/less lactate data), this is informative missing data.
- Within-tertile strata (n~1,450–1,570 each): ADEQUATE for T1 and T3; T2 barely adequate
  given the CI width.
- VitalDB (n=157, events=17): INADEQUATE, correctly disclosed.
- INSPIRE (n=38,963, events=2,475): ADEQUATE for the calibration but calibration precision
  limited by 3-point null.

---

## Publishability Verdict

**Scoped claim (predictive risk-stratifier, not causal):** CONDITIONAL — not as-is; requires
substantive revision.

**Explicitly:**

The honest framing of the finding — predictive YES, causal NO — is commendable and unusual
for a positive-result paper. Reporting that the cross-cohort negative-control calibration
kills the causal arm is intellectually honest and adds scientific value. In principle, a
well-executed paper with this framing is publishable.

However, the current manuscript/dossier has **three issues that require major revision before
a top-tier journal will accept it:**

1. **CRITICAL-1 + CRITICAL-2 (KDIGO baseline):** The code documentation contradicts itself,
   and the baseline creatinine choice deviates from KDIGO 2012 guidance in a way that is
   neither acknowledged as a deviation nor compared to the standard approach in a primary
   sensitivity. The correct comparison (prior-outpatient creatinine where available in MIMIC-IV,
   or minimum-inpatient as the KDIGO-endorsed fallback) must be the primary or a co-primary.

2. **CRITICAL-4 (competing risk):** AKI vs death in a high-mortality vasopressor population
   without competing risk analysis is a fundamental methodological gap for any ICU-AKI paper
   in 2026. Fine-Gray or cause-specific hazard, or at minimum a survivor-restricted sensitivity,
   is required.

3. **CRITICAL-5 (calibration precision):** The "DIES" verdict from a 3-point empirical null
   with 2 df must be moderated. The calibration provides directional evidence, not a definitive
   null. The paper's strongest claim — that it honestly reports the causal arm's failure — is
   undermined if the test used to declare failure is itself fragile. Either more control outcomes
   must be added to stabilize the null, or the language must shift from "DIES" to "is not
   distinguishable from the non-renal confounding null given the available controls."

**Secondary revisions (MODERATE):**
- CKD/eGFR exclusion and adjustment (CRITICAL-3 / MODERATE)
- Replace raw ICD code count with validated Charlson or Elixhauser score
- Bootstrap CI precision (2000 samples, bias-corrected acceleration)
- Severity-adjusted dose-response table (not just crude rates per quartile)
- Lactate T2 CI limitation acknowledged explicitly

**With these revisions, the scoped claim is likely publishable in a mid-to-high-tier
critical care or nephrology journal (Critical Care Medicine, AJKD, Clinical Journal of the
American Society of Nephrology).** It would face significant resistance at Anesthesiology or
JAMA-ICM without also addressing the INSPIRE estimand mismatch (MODERATE-6) and presenting
a cleaner competing-risk analysis.

**Without these revisions, the finding should be rejected at any top-tier journal, not for
its honest negative framing, but because the methods underlying both the positive MIMIC
finding and the negative INSPIRE calibration are too fragile to support the confidence of
the stated conclusions.**

---

*Review by: Reviewer 2 (adversarial, publication-grade). No code was modified. No other
documents were altered. Findings above are based on code audit of
`analysis/requirement_aki_crossval.py`, `docs/PUBLICATION_DOSSIER.md`,
`docs/REQUIREMENT_AKI_CROSSVAL.md`, `docs/MIMIC_DISCOVERED_FINDINGS.md`, and
`cache/requirement_aki_crossval.json`.*
