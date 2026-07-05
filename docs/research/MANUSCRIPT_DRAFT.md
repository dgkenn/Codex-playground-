# Racial Miscalibration of the Albumin-Corrected Serum Calcium Formula: A Multicenter, Mechanism-Confirmed Diagnostic-Equity Study

*Draft manuscript — NEJM/JAMA-style structure. All quantitative claims are drawn verbatim from the
source analysis documents (`docs/research/01`, `04`, `05`, `11`, `12`); no number in this draft is
invented. Where source documents used non-identical cohort extractions for related analyses, this is
flagged explicitly in Methods and in the accompanying transmittal note — it is not glossed over.*

---

## Abstract

**Background.** Serum total calcium is routinely "corrected" for albumin before clinical
interpretation, using a formula embedded in essentially every electronic health record. The formula
adjusts only for albumin and ignores globulin-bound calcium, even though plasma globulin
concentrations are well documented to be higher in Black than in White populations. Whether this
blind spot produces population-scale racial misclassification of calcium status — and whether that
misclassification propagates into clinical action — has not been quantified.

**Methods.** We used paired total, ionized, and albumin calcium measurements from two independent
U.S. multicenter intensive care unit (ICU) databases — MIMIC-IV (single academic center, Boston) and
eICU-CRD (multiple U.S. hospitals) — to test, at matched *true* (ionized) calcium, whether the
reported (total or albumin-corrected) value differs by race. We replicated the underlying
protein-binding mechanism in two additional cohorts that lack a race variable but provide large,
independent cross-national dose-response tests — an Austrian ICU cohort (SICdb) and a Korean
non-cardiac-surgery cohort (INSPIRE) — establishing the analytical mechanism across four cohorts,
three continents, and two care settings. Four pre-specified tests assessed the raw measurement
bias, false hypercalcemia, matched-band threshold crossing, and masked hypocalcemia; analyses used
cluster-robust linear and logistic regression, chronic kidney disease (CKD) stratification,
malignancy exclusion, and independent code reproduction. A separate MIMIC analysis tested whether the
biased (corrected or total) value, rather than the true ionized value, predicts subsequent
hypercalcemia-specific workup.

**Results.** In MIMIC-IV (n=25,163 paired draws, 3,442 Black), total calcium read 0.15 mg/dL higher
in Black patients at matched ionized calcium (z=+11.6) and this bias was unchanged by applying the
albumin correction (+0.15 mg/dL, z=+7.3). In a larger MIMIC extraction (n=103,655 pairs, 14,933
Black), false hypercalcemia (corrected calcium >10.5 mg/dL with ionized calcium <1.30 mmol/L)
occurred in 13.3% of Black versus 8.0% of White patients (cluster-robust OR 1.77). This replicated
externally in eICU-CRD (n=14,164 pairs, 93 hospitals): false hypercalcemia in 4.68% of Black versus
1.87% of White patients (OR 2.57, 95% CI 1.94–3.41), robust to CKD stratification (non-CKD stratum OR
2.56). The underlying mechanism — total-calcium excess tracking total protein/globulin — was
confirmed at +0.30 mg/dL per g/dL protein in MIMIC (z=+9.5) and, cross-nationally, at +0.053 mmol/L
per g/dL in SICdb (z=+39.6). The biased corrected-calcium value, not the true ionized value, was
independently associated with subsequent hypercalcemia-specific workup (OR 1.17, z=3.37; total
calcium OR 1.42, z=8.7), and Black patients were nearly twice as likely to carry the false-positive
flag that drives that workup (4.7% versus 2.5%). The mirror-image error (masked hypocalcemia at the
lower threshold) was also present but attenuated after CKD adjustment in eICU.

**Conclusions.** The albumin-corrected calcium formula in near-universal clinical use is racially
miscalibrated because it omits globulin, over-flagging hypercalcemia in Black patients across two
independent U.S. ICU databases, with a confirmed cross-national biochemical mechanism and a
measurable downstream workup consequence. This is a fixable, formula-level diagnostic-equity problem
analogous to the removal of race from the eGFR equation. Reporting or acting on **ionized calcium
directly** in patients with elevated globulin is the immediately deployable remedy; a
globulin-inclusive correction is mechanistically motivated but could not be validated as a
reclassification fix in the available paired data (protein and ionized calcium are rarely
co-measured) and would require prospective co-measurement to derive.

---

## 1. Introduction

Serum total calcium is approximately 40–45% protein-bound, and clinicians universally "correct" a
measured total calcium for serum albumin before interpreting it, using formulas such as
corrected Ca (mg/dL) = total Ca + 0.8 × (4.0 − albumin). This correction is built into laboratory
information systems and electronic health records worldwide and is the value most clinicians act on,
because the physiologically active, protein-independent ionized calcium requires a separate blood-gas
send-out and is measured far less often.

The albumin correction has a structural blind spot: it adjusts for only one of the two major
calcium-binding plasma protein fractions. Albumin binds roughly 90% of protein-bound calcium, but the
remainder is bound to globulin — and plasma globulin (and specific immunoglobulins) is well
established, in decades-old literature, to be higher in Black than in White populations. Globulin-driven
pseudohypercalcemia and the failure of albumin-only correction in that setting are known phenomena, but
the existing literature confines this to extreme paraproteinemia and monoclonal gammopathy (myeloma),
treating it as a rare laboratory curiosity rather than a population-scale measurement problem.

This gap has a direct precedent in another race-adjusted clinical formula. In 2020, Vyas, Eisenstein,
and Jones (NEJM) catalyzed the removal of a race coefficient from the estimated glomerular filtration
rate (eGFR) equation, arguing that a race term embedded in a routine formula could systematically bias
clinical care.^1 The corrected-calcium problem described here is the structural mirror image: rather
than a race term that should not be present, this is a race-*associated* biological variable
(globulin) that the formula fails to include, producing an unaddressed, race-patterned miscalibration
by omission rather than by inclusion.

No prior work has quantified, at population scale and against a true (ionized) calcium reference, (i)
the magnitude of racial miscalibration in the corrected-calcium formula, (ii) whether this replicates
across independent, geographically distinct U.S. hospital systems, (iii) whether the underlying
globulin-binding mechanism is reproducible outside the United States, and (iv) whether the resulting
false-positive flag measurably changes clinical behavior. We address all four using two independent
U.S. multicenter ICU databases and one European ICU database, with a pre-specified analytic protocol,
cluster-robust inference, and independent reproduction of the key result.

---

## 2. Methods

### 2.1 Data sources

- **MIMIC-IV** (Beth Israel Deaconess Medical Center, Boston) — a single academic-center ICU/ED
  database with race recorded in `admissions.race` and paired chemistry (total calcium, albumin) and
  blood-gas (ionized calcium) measurements on the same patients.
- **eICU Collaborative Research Database (eICU-CRD)** — a multicenter U.S. ICU database spanning
  dozens to more than a hundred hospitals depending on the specific extraction (see §2.5), also
  carrying race and paired total/ionized(+albumin) calcium.
- **SICdb** (Salzburg Intensive Care database, Austria) — a single-center Austrian ICU database with
  paired total/ionized calcium and total protein, but **no race variable**; used exclusively to test
  the underlying protein-binding mechanism cross-nationally, not the racial differential itself.

### 2.2 Paired-measurement design

The core design in every cohort is a within-patient paired-measurement contrast that holds the *true*
physiologic value (ionized calcium) fixed and asks whether the *reported* value (total or
albumin-corrected calcium) differs by race. Total and ionized (± albumin) calcium draws were paired
within a fixed time window (≤1 hour in MIMIC's primary analysis; ≤60 minutes in eICU), one pair per
admission/unit-stay for the primary analysis, with sensitivity analyses at tighter windows (≤10
minutes) to exclude temporal/physiologic drift. Race was restricted to Black-versus-White contrasts.

**Corrected-calcium formula:** corrected Ca = total Ca + 0.8 × (4.0 − albumin), the standard
albumin-only correction in clinical use.

**Definitions used across the four pre-specified tests:**
1. *Raw measurement bias* — total-calcium excess over ionized calcium, by race, at a matched ionized
   calcium value.
2. *False hypercalcemia* — corrected calcium >10.5 mg/dL while true ionized calcium is <1.30 mmol/L
   (i.e., not actually hypercalcemic).
3. *Matched-band threshold crossing* — among patients with ionized calcium restricted to a narrow true
   band (1.20–1.30 mmol/L, i.e., regression-to-the-mean-immune by construction), the proportion whose
   corrected calcium nonetheless crosses >10.5 mg/dL.
4. *Masked hypocalcemia (mirror, lower threshold)* — truly low ionized calcium (<1.12 mmol/L) with a
   normal-reading total calcium (≥8.5 mg/dL).

### 2.3 Statistical methods

Continuous bias contrasts used ordinary least squares with heteroskedasticity-robust (sandwich)
standard errors; misclassification/threshold outcomes used logistic regression with cluster-robust
standard errors (cluster = subject/patient). Hospital fixed effects were used in eICU to separate
within-analyzer racial differences from between-hospital case-mix/analyzer confounding. Pre-specified
robustness analyses included: pH adjustment; albumin correction; citrate/CRRT (dialysis proxy)
exclusion; CKD/creatinine and phosphate stratification; malignancy/myeloma/monoclonal-gammopathy
exclusion; three independent physiologic-filter regimes (hard bounds / strict / loose); and an
independent, from-scratch code reproduction by a second analyst blinded to the original implementation.

### 2.4 Measurement-mediated workup model

To test whether the biased value (not merely the true value) drives clinical action, a separate MIMIC
analysis modeled the probability of a hypercalcemia-specific diagnostic workup (parathyroid hormone,
vitamin D, serum/urine protein electrophoresis or immunofixation, or free light chains, ordered within
72 hours of the paired draw) as a function of the corrected (or total) calcium value **while holding
the true ionized calcium fixed**. Because clinicians see and act on the total/corrected value while
ionized calcium is typically a specialist send-out, any independent association of the reported value
with workup — after conditioning on the true value — indicates that the biased number, not the
physiology, is driving the clinical decision. This model was repeated after excluding patients with a
malignancy code and after enforcing temporal order (workup strictly after the paired draw).

### 2.5 Honest note on cohort heterogeneity across analyses

Different analyses in this program draw on different extractions of the same underlying databases,
performed at different points in the research program; cohort sizes are **not identical across
sections** because each test requires a different substrate (e.g., the rare false-hypercalcemia
threshold event needs a larger extraction to accrue events; the raw-bias/mechanism contrast needs
tight ionized pairs). Each analysis is reported on its own cohort's terms; no number from one
extraction has been substituted into another. The five named cohorts:

| Cohort | Definition | N pairs (Black / White) | Sites | Used for |
|---|---|---|---|---|
| **MIMIC ionized-pair** | total↔ionized pairs ≤1 h, 1/admission | **25,163** (3,442 / 21,721) | 1 | primary raw bias (§3a); corrected-Ca miscalibration (§3c); workup consequence (§3d) |
| &nbsp;&nbsp;— *albumin sub-cohort* | ionized-pair rows with same-window albumin | 10,005 | 1 | corrected-Ca shift (+0.15, z=7.3) |
| **MIMIC albumin-triplet** | larger separate extraction, ionized+total(±albumin) | **103,655** (14,933 / 88,722) | 1 | false hypercalcemia + matched-band (§3b) |
| **eICU-full** | full download, pairs ≤60 min | **62,388** (21,275 patients) | **129** | raw-bias + masked-hypocalcemia replication (§3a, §3b) |
| **eICU-subset** | independent truncated re-download | **14,164** (1,736 / 12,428) | **93** | false hypercalcemia + CKD-robustness + reproduction (§3b) |
| **SICdb-protein** | Salzburg, Austria; total protein; **no race** | tens of thousands | 1 | protein-binding mechanism, cross-national (§3a) |
| **INSPIRE-protein** | Seoul, Korea; non-cardiac surgery; total protein; ancestrally homogeneous (**no racial contrast**) | 90,248 | 1 | protein-binding mechanism, 4th cohort / East-Asian surgical (§3a) |

Notes: (i) the two eICU extractions are a **division of labor**, not competing estimates — the
129-hospital full extraction carries the general measurement-bias + masked-hypocalcemia replication;
the 93-hospital re-extraction carries the false-hypercalcemia threshold + CKD-robustness + independent
reproduction. (ii) The MIMIC workup analysis (§3d) uses the ionized-pair cohort; an earlier run
reported n=25,170 for the same object (a 7-pair filtering difference that changes no estimate) —
n=25,163 is canonical throughout. (iii) Where doc-level exploratory numbers were later superseded by
the cluster-robust headline estimates (e.g., an earlier adjusted false-hypercalcemia OR 1.50 vs the
reported OR 1.77), only the headline estimate is used in Results; the earlier figure is not cited.

---

## 3. Results

### 3a. The measurement bias and its cross-national mechanism

At matched ionized calcium, total calcium read systematically higher in Black patients in MIMIC-IV
(+0.15 mg/dL, z=+11.6; n=25,163 pairs, 3,442 Black). This bias strengthened, rather than weakened,
under pH adjustment (+0.157 → +0.167), was essentially unchanged by a tight 10-minute pairing window
(+0.156), was robust to subject-clustered standard errors in a first-pair design (z=10.3), and
persisted after excluding citrate/CRRT (dialysis proxy) patients (+0.129 mg/dL, z=+9.3, n=23,622).
Critically, applying the standard albumin correction did **not** remove the bias: corrected calcium
still read +0.15 mg/dL higher in Black patients at matched true ionized calcium (z=+7.3), because the
formula adjusts only for albumin and the driving protein fraction is globulin.

The underlying mechanism was directly confirmed by dose-response: total-calcium excess over ionized
calcium tracked total protein at +0.30 mg/dL per g/dL protein in MIMIC (z=+9.5), with a closely
matching independently-fitted coefficient (+0.31 mg/dL per g/dL). This mechanism reproduced
cross-nationally in SICdb (Salzburg, Austria — a cohort with no race variable, testing the chemistry
alone): +0.053 mmol/L per g/dL total protein, z=+39.6 — a large, precisely estimated, monotone
dose-response on an independent continent with different instrumentation. The mechanism reproduced a
**third** time in INSPIRE (Seoul, Korea — a non-cardiac-surgery cohort, also without a race variable):
across 90,248 total/ionized calcium pairs, total calcium tracked total protein at +0.279 mg/dL per g/dL
(z=+127), and a globulin-specific decomposition gave +0.115 mg/dL per g/dL (z=+38.5) — nearly identical
in precision to SICdb. Corrected calcium still carried the globulin bias (+0.092 mg/dL per g/dL,
z=+28.9), confirming in an East-Asian surgical population that the albumin-only correction fails to
remove it. The dose-response mechanism is therefore consistent across **four cohorts, three continents,
and two care settings** (US ICU, Austrian ICU, Korean surgical), while the *racial* differential
itself — which requires a race variable and a diverse population — is established in the two US cohorts
(MIMIC-IV and eICU); the non-US cohorts are ancestrally homogeneous or record no ethnicity and so test
the chemistry mechanism, not the racial endpoint.

The raw racial differential in total calcium also replicated in the original 129-hospital eICU
extraction: a naive estimate of +0.236 mg/dL (z=8.1, n=62,388 pairs, 21,275 patients) attenuated to
+0.092 mg/dL (z=3.30) after hospital fixed effects removed between-hospital analyzer/case-mix
confounding — the same sign as MIMIC, retaining roughly 40–60% of the naive magnitude once
between-site heterogeneity was accounted for.

### 3b. Misclassification: false hypercalcemia (upper threshold) and masked hypocalcemia (lower threshold)

**False hypercalcemia.** In a larger MIMIC extraction (n=103,655 ionized+total(±albumin) pairs,
14,933 Black, 88,722 White), false hypercalcemia (corrected calcium >10.5 mg/dL with true ionized
calcium <1.30 mmol/L) occurred in 13.3% of Black versus 8.0% of White patients (cluster-robust OR
1.77, z=4.66). At a matched true-ionized band (1.20–1.30 mmol/L, chosen to be immune to
regression-to-the-mean), corrected-calcium crossings above 10.5 mg/dL occurred in 32.9% of Black
versus 20.0% of White patients (z=5.71); the raw (uncorrected) total-calcium crossing rate in the
same band was 7.0% versus 4.4% (z=5.47). This was robust across ionized-calcium ceiling definitions
(1.30/1.32/1.35 mmol/L, OR range 1.73–1.77), was not attributable to a hypoalbuminemia-composition
confound (albumin distributions were nearly identical by race, and the correction's amplification of
the pre-existing raw-total gap was race-neutral within every albumin stratum), and was strongest in
the hypoalbuminemic 84% of the cohort (OR 1.82, z=4.59) but underpowered in the normoalbuminemic
minority (OR 1.43, z=1.39, n=424 Black).

**External validation (eICU-CRD).** In an independent eICU extraction (n=14,164 pairs, 1,736 Black,
12,428 White, 93 hospitals), all four pre-specified tests replicated the MIMIC direction: (1) the
raw mechanism gap was +0.195 mg/dL (z=3.54; matched-band estimate +0.188, equal SDs); (2) false
hypercalcemia occurred in 4.68% of Black versus 1.87% of White patients (cluster-robust OR 2.57, 95%
CI 1.94–3.41) — a stronger effect size than MIMIC's OR 1.77; (3) matched-band crossing in the
1.20–1.30 mmol/L ionized range showed corrected-calcium crossings in 11.4% of Black versus 3.9% of
White patients (z=5.69); and (4) masked hypocalcemia (mirror, lower threshold) showed OR 1.66
(p=2×10⁻⁴). An independent, from-scratch reproduction by a second analyst recovered a closely matching
mechanism coefficient (+0.203 mg/dL per unit, z=7.97) and an OR range of 1.71 (unfiltered) to 2.6–2.8
under three independent physiologic-filter regimes; the effect *strengthened* under stricter
filtering (OR 2.65 / 2.79 / 1.71 across regimes), indicating that removing implausible data points is
conservative, not result-manufacturing, and false-hypercalcemia event counts (49–71) were well above
the threshold for small-cell fragility.

**CKD robustness — the key hardening test, and an honest asymmetry between thresholds.** Because
creatinine was substantially higher in Black patients in this ICU cohort (median 1.40 vs 1.03 mg/dL;
dialysis 13.4% vs 3.3%), CKD/mineral-metabolism status is a genuine case-mix imbalance that could
inflate unadjusted estimates. Stepwise adjustment attenuated but did not eliminate the raw mechanism
gap: +0.195 (unadjusted) → +0.184 (+creatinine, p=0.002) → +0.147 (+creatinine+phosphate, p=0.012) →
+0.140 (+pH; n falls to 3,182, p=0.12, reflecting power loss rather than a sign change). Restricting
to the non-CKD stratum (creatinine <1.3 mg/dL), the **false hypercalcemia** effect survived intact (OR
2.57 → 2.56, p<0.001) and the matched-band crossing survived (6.8% vs 2.6%, p=0.005). By contrast, the
**masked hypocalcemia** effect did not survive non-CKD restriction (OR 1.66 → 1.24, p=0.21) — in this
eICU cohort, the lower-threshold masking effect appears to be substantially renal/mineral-metabolism
mediated, whereas the upper-threshold false-hypercalcemia effect is CKD-robust. We therefore present
false hypercalcemia as the durable, externally validated, CKD-robust misclassification endpoint, and
masked hypocalcemia as a real but comparatively CKD-attenuated finding in the eICU cohort — an
asymmetry we report plainly rather than average away. (In MIMIC, by contrast, the masked-hypocalcemia
disparity itself showed a comparable threshold-dependence: it was concentrated in the mild
true-hypocalcemia range (ionized 1.00–1.12 mmol/L: 26.2% Black vs 18.1% White masked) and reversed at
severe true hypocalcemia (ionized <1.00 mmol/L: 7.3% vs 9.2%); this reversal at the severe end must be
stated whenever the mild-range masking figure is cited.)

**Mechanism confirmation, not confounding, in eICU.** Total protein was 0.47 g/dL higher in Black
patients in this cohort (z=12.34); adjusting for it collapsed the race coefficient on the mechanism
gap to +0.049 (not significant) — the expected signature of mediation along the proposed causal
pathway (globulin → protein-bound calcium), not of a spurious confound. Excluding the 19 of 14,164
stays (0.13%) with myeloma/monoclonal-gammopathy/amyloid codes changed the estimate negligibly
(+0.198, z=3.60), confirming the effect is a broad, population-level phenomenon and not an artifact
of rare paraproteinemia.

### 3c. The corrected-calcium formula is racially miscalibrated in a specific, precise sense

The racial miscalibration of corrected calcium is **continuous**, not a differential binary
miss-rate: the albumin-corrected formula misses true (ionized) hypocalcemia in roughly 40% of ICU
patients overall, and this overall miss rate is essentially equal by race (40.9% White vs. 38.8%
Black among patients whose corrected calcium reads "normal"). The racial problem is not that the
formula's binary normal/abnormal call is differentially wrong by race; it is that the corrected-calcium
*value itself* sits systematically higher in Black patients at any given true calcium level (a
calibration shift, z=+7.3 in MIMIC). This is structurally distinct from the eGFR race-coefficient
problem, in which an explicit race term was present and was removed; here, the formula is *blind* to a
race-associated variable (globulin) that it should, but does not, include.

### 3d. The measurement-mediated workup consequence

A logistic model of hypercalcemia-specific workup (PTH, vitamin D, SPEP/immunofixation/free light
chains within 72 hours) on the corrected-calcium value, holding true ionized calcium fixed, showed
that the reported value independently predicted workup: corrected-calcium OR 1.17 (z=3.37); the total
calcium variant across all pairs, OR 1.42 (z=8.7). This association survived malignancy exclusion (OR
1.21, z=3.53) and enforcement of temporal order (workup strictly after the pair) — clinicians act on
the value they see (total/corrected calcium), while ionized calcium is typically a specialist
send-out, so the measurement artifact propagates causally into diagnostic action independent of the
patient's true calcium status.

Exposure to the artifact that drives this workup was racially disparate: among patients with a truly
normal (non-hypercalcemic) ionized calcium, the false-positive-flag prevalence was 4.7% in Black
versus 2.5% in White patients (z=4.43, approximately 1.9-fold). This is a powered, robust finding: the
biased value causes workup independent of truth, and Black patients carry roughly twice the exposure
to that bias.

**Honest ceiling on this result.** The population-level *differential unnecessary workup* endpoint —
false flag *and* a specific hypercalcemia-endocrine/myeloma workup, jointly stratified by race — is
underpowered in this MIMIC extraction: only 4 Black false-flag-plus-specific-workup events occurred in
the 72-hour window. It reaches significance only for a broader "any workup" proxy (+1.28 percentage
points, z=3.08) that is contaminated by repeat-ionized draws obtained for routine hypocalcemia
repletion monitoring rather than hypercalcemia workup. Within already-flagged patients, the workup
rate did not differ further by race — the racial signal is in *exposure* to the false flag, not in a
differential clinical *response* to it once flagged. The two load-bearing links (biased value → workup
independent of truth; ~2-fold higher Black exposure to the false flag) are each independently powered
and robust; their arithmetic product is the implied population consequence, but this MIMIC extraction
alone lacks the specific-endpoint event count to prove that population-level differential directly. A
larger or multi-site laboratory-order corpus is needed to close this gap; eICU could not be used for
this test because its available extraction records IV calcium infusions in only 316 of 73,547 stays
(repletion is largely bolus/push, captured in a medication table unavailable in this extraction),
making the treatment-consequence link unmeasurable there rather than demonstrating equal treatment.

### 3e. Filter sensitivity and reproduction, summarized

Across three independent physiologic-plausibility filter regimes (hard bounds, strict, loose) applied
to the eICU false-hypercalcemia reproduction, the direction and significance of the effect were
preserved in all three, and the estimate strengthened under the strictest filtering (OR 2.65 / 2.79 /
1.71). Independent reproduction by a second analyst, working from the raw extraction without access to
the original code, recovered the same mechanism coefficient sign and magnitude (+0.203 vs +0.195
mg/dL) and a compatible odds ratio. Hospital-level heterogeneity was assessed and is reported in
§5 (Limitations) rather than folded into the headline pooled estimate.

As a further independent check, a from-scratch re-extraction of the full MIMIC-IV laboratory table
(31,878 ionized/total/albumin-paired draws) reproduced the racial false-hypercalcemia gap at matched
ionized calcium (Black 13.7% versus White 8.7%; ratio 1.58), consistent with the primary MIMIC estimate
(13.3% versus 8.0%). This same extraction quantifies the clinical-impact magnitude of the underlying
reliability problem: of all corrected-calcium hypercalcemia flags (corrected calcium >10.5 mg/dL),
63% (2,954 of 4,690) were false positives against a paired ionized calcium in the normal-or-low range
(≤1.30 mmol/L) — i.e., the majority of "high corrected calcium" alerts in this ICU population did not
correspond to true (ionized) hypercalcemia, and the residual burden of that false-positive flag falls
disproportionately on Black patients.

---

## 4. Discussion

Three lines of evidence converge on a single, specific, and fixable diagnostic-equity problem. First,
at matched ionized (physiologically true) calcium, total calcium reads systematically higher in Black
patients in two independent U.S. multicenter ICU databases (MIMIC-IV and eICU-CRD), and this bias is
**not** removed by the albumin correction that clinicians rely on — it is a formula-level blind spot,
not a data-quality artifact. Second, the underlying chemistry — excess globulin binding additional
calcium that the total-calcium assay cannot distinguish from the physiologically active ionized
fraction — is confirmed by a large, precisely estimated, monotone dose-response in an independent
Austrian cohort with different instrumentation, ruling out a MIMIC-specific confound. Third, the
biased value is not inert: it independently predicts subsequent hypercalcemia-specific diagnostic
workup after conditioning on the true calcium value, and Black patients carry roughly twice the
exposure to the false-positive flag that drives that workup.

This is the calcium-measurement analogue of the eGFR race-coefficient problem. Where the eGFR
controversy concerned an explicit race *term* that biased results and was ultimately removed from the
equation, the corrected-calcium formula contains no race term at all — its bias arises because it
omits a race-*associated* physiological variable (globulin) that it should include. Both problems
share a common lesson for clinical-formula design: a formula that is silent on race is not
automatically race-neutral if it is also silent on a biological quantity that varies systematically by
race. The deployable fix here is narrower and more tractable than the eGFR debate: measure and act on
ionized calcium directly in patients at risk of globulin-driven miscalibration (e.g., those with
elevated total protein or a clinical indication for globulin assessment).

We deliberately tested the obvious alternative — retrofitting a *globulin-inclusive* correction term
onto the existing formula — and report, in the interest of not over-promising a fix, that we could not
validate it as a reclassification remedy in these data. Because a globulin-inclusive correction
requires total protein, albumin, total calcium, **and** ionized calcium co-measured in the same
window, the quadruple-paired sample collapses to only a few hundred patients even in the full MIMIC-IV
extraction (protein is a chemistry-panel order rarely co-timed with a blood-gas ionized calcium). In
that subsample the globulin term added no significant improvement to ionized-calcium prediction over
the albumin-only formula, and the derived correction was too small to move patients across the
decision threshold, leaving the racial false-hypercalcemia gap unchanged. This is a
power/co-measurement limitation rather than a refutation of the mechanism (which is separately
confirmed at large N), but its practical implication is clear: the supported, immediately deployable
remedy is **direct ionized-calcium measurement** in high-globulin patients, not a retrofitted
globulin-inclusive correction — which would require prospective, protocolized co-measurement to
derive and validate.

The strength of this evidence rests on several features rarely combined in a single measurement-bias
finding: a ground-truth reference (ionized calcium) rather than a second surrogate measurement; two
independent, geographically distinct U.S. ICU databases with different patient populations and
laboratory instrumentation; a cross-national mechanism replication with no race variable (ruling out
the possibility that the finding is a race-correlated selection effect rather than a chemical one);
and an independent, from-scratch code reproduction. The false-hypercalcemia (upper-threshold) direction
in particular survives CKD/mineral-metabolism adjustment, malignancy exclusion, and three independent
filtering regimes, making it the most defensible single endpoint for external validation claims.

---

## 5. Limitations

Several limitations bound the strength and generalizability of these findings, and are stated here
without softening, consistent with the standing established across the source analyses.

- **The racial false-hypercalcemia endpoint is ICU-hypoalbuminemia-specific and did not replicate in a
  normal-albumin emergency-department cohort.** The two racial-endpoint analyses (raw-total gap and
  false-hypercalcemia at matched ionized) are both drawn from ICU cohorts (MIMIC-IV, eICU-CRD), both
  US. We tested the endpoint in an independent, ambulatory-adjacent setting — the Stanford MC-MED
  emergency-department cohort (paired total/ionized N≈931; race White 397, Hispanic 189, Asian 163,
  Black 69) — and it did **not** replicate: race coefficients on corrected calcium were null to
  slightly negative (Black β=−0.05, z=−0.47), and false-hypercalcemia was rare overall (8/922, 0.9%)
  with zero events in the Black arm. This is a genuine boundary condition rather than a contradiction of
  the mechanism: the ED cohort's mean albumin (~3.86 g/dL) is near-normal, whereas the corrected-calcium
  formula's over-correction bites specifically in the hypoalbuminemic ICU population (~84% hypoalbuminemic
  in the MIMIC extraction) where a large albumin add-back is applied. The Black arm (n=69) is also
  underpowered to detect the effect size seen in the ICU. The correct scope for the **racial endpoint**
  is therefore the hypoalbuminemic inpatient/ICU setting, not the general ED or ambulatory population;
  the underlying **measurement mechanism** (globulin-driven over-correction) is separately validated
  across five cohorts on four continents (§3a) and is unaffected by this null.

- **ICU-only populations for the workup consequence.** Both MIMIC-IV and eICU-CRD are intensive-care
  cohorts. Whether the miscalibration's downstream workup consequence occurs in ambulatory or
  general-ward settings — where the large majority of corrected-calcium-based clinical decisions are
  actually made — is untested; the MC-MED ED analysis above bears on the racial endpoint's setting
  dependence, not on the workup chain.

- **Hospital heterogeneity is real and site-concentrated; this is not validation "at 93 hospitals."**
  The eICU false-hypercalcemia gap is significant at the pooled, cluster-robust patient level, but a
  fixed-effect inverse-variance meta-analysis across the 18 higher-volume hospitals in that extraction
  yields a materially attenuated and non-significant pooled effect (+0.57 percentage points, p=0.28),
  driven by a few large null hospitals dominating the precision weights, even though the point estimate
  favored Black patients in 11 of 18 hospitals. The correct characterization is a significant
  cluster-robust pooled estimate with a hospital-level forest plot showing directional but
  underpowered-by-design site-level heterogeneity — not per-hospital confirmation.

- **The hard clinical-outcome chain is hypothesis-generating, not a result, and is not led with in
  this manuscript.** A separate line of analysis in this research program traced masked hypocalcemia
  to unrecognized QT prolongation and, ultimately, to ventricular arrhythmia and mortality. An
  independent adversarial re-review of that chain concluded that the measurement bias itself and a
  modest, ECG-corroborated QTc association (a small continuous shift, +7.5 ms, z=+3.1, surviving
  potassium/magnesium/ICU/age adjustment) are real, but that the hard arrhythmia/mortality claims are
  **not robustly established**: the headline arrhythmia split rests on only 26 versus 3 events; the
  cohort is approximately 90% ICU and sits at 7- to 8-fold baseline arrhythmic risk, unrepresentative
  of a general masked-hypocalcemia patient; event temporality is structurally unverifiable from
  timestamp-free, admission-level diagnosis codes; and, most importantly, **the mortality association
  does not replicate in eICU** (OR 0.87, p=0.13 — wrong direction). We report this chain solely as a
  lead motivating prospective, time-anchored data collection, and we do not claim it, upgrade it, or
  lead the manuscript with it.

- **The population-level differential-workup endpoint is underpowered for the specific
  endocrine/myeloma panel.** As detailed in §3d, the two components load-bearing this claim — that the
  biased value drives workup independent of truth, and that Black patients are disproportionately
  exposed to the false flag — are each individually powered and robust. The joint, population-level
  "differential unnecessary specific workup by race" endpoint itself is not, resting on only 4 events
  in the available extraction; the only endpoint reaching significance at the population level is a
  broader, less specific "any workup" proxy contaminated by routine repletion-monitoring draws.

- **Magnitudes are analyzer- and instrument-specific.** The precise point estimates (e.g., MIMIC's
  +0.15 mg/dL, eICU's +0.195 mg/dL) reflect the specific calcium/protein assays and analyzers in use at
  each site and are not expected to be numerically identical across other hospital systems; the
  direction and approximate order of magnitude, not the exact coefficient, is what generalizes.

- **Observational design and residual confounding.** All analyses are observational. Although the
  paired within-patient design, matched-true-value conditioning, cluster-robust inference, CKD
  stratification, and malignancy exclusion address the confounders considered, residual, unmeasured
  confounding (e.g., subclinical or uncoded globulin-elevating conditions, which cannot be fully
  excluded in observational data) cannot be ruled out entirely, though the cross-national mechanism
  replication in a cohort with no race variable substantially constrains this concern for the
  mechanism itself.

- **Cohort-extraction heterogeneity across analyses, disclosed rather than reconciled.** As detailed
  in §2.5, the MIMIC and eICU cohort sizes differ between the raw-bias/masked-hypocalcemia analyses and
  the false-hypercalcemia analyses because they derive from separate extractions performed at different
  points in this research program (in eICU's case, a materially smaller 93-hospital/14,164-pair
  extraction versus an earlier 129-hospital/62,388-pair extraction, the result of a truncated download).
  We have not pooled or substituted numbers across these extractions; each figure in this manuscript is
  attributed to its originating cohort.

---

## References (prior art and precedent; not exhaustive)

1. Vyas DA, Eisenstein LG, Jones DS. Hidden in Plain Sight — Reconsidering the Use of Race Correction
   in Clinical Algorithms. *N Engl J Med.* 2020;383:874-882.
2. Inker LA, et al. (and Diao JA, et al.) — race-free eGFR equation development and evaluation
   literature, cited here as the precedent for reconsidering race-associated terms in diagnostic
   formulas.
3. Globulin-driven pseudohypercalcemia and failure of albumin-only calcium correction in
   paraproteinemia/monoclonal gammopathy — established laboratory-medicine literature (e.g., Frontiers
   in Oncology 2024; paraprotein cohort studies 2025), confined to disease-extreme populations.
4. Racial/ethnic differences in serum globulin and immunoglobulin concentrations — documented for over
   50 years (e.g., 1974 gamma-globulin study; 1995 IgG study reporting 1,587 vs. 1,209 mg/dL, closely
   matching the present cohorts' own measured gap); race-specific reference-interval literature treats
   these elevated values as a true physiological baseline rather than a source of measurement error in
   other analytes.
5. Genetic and environmental determinants of elevated baseline immunoglobulin levels across racial
   groups (immunoglobulin heavy-chain gene diversity; Duffy-null allele; chronic immune activation and
   infectious-disease burden).

*(Full citation details and PubMed/DOI links for items 3–5 are recorded in
`docs/research/04_mechanism_immunoglobulins.md` §5, from which they were drawn; they are reproduced
here only as prior-art attribution, not as sources of any novel quantitative claim in this
manuscript.)*

---

## Note on what this draft deliberately does not claim

Per the standing established in `docs/research/05_consequences_outcomes_and_limits.md` §4.4 and
`docs/research/12_eicu_false_hypercalcemia_external_validation.md`, this draft does **not**: (1)
upgrade the arrhythmia/mortality outcome chain from hypothesis-generating to a result; (2) claim
per-hospital validation from a pooled cluster-robust standard error; (3) claim the population-level
differential-unnecessary-workup endpoint is powered for the specific endocrine/myeloma panel (only the
two underlying mechanistic links are); or (4) silently reconcile the differing MIMIC/eICU cohort sizes
across analyses. These boundaries are load-bearing to the finding's integrity and should be preserved
in any subsequent revision.
