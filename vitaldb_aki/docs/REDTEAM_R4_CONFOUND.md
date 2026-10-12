# Red-Team Round 4 — Confounding and Statistical-Completeness Audit

**Scope:** Within-at-target-stratum confounding defense; MICE validity; E-value
correctness; band cherry-picking; AUC gap formal CI.

**Primary finding under review:** Among ICU patients with at-target MAP (first-24h
median MAP in [65,85] AND <10% readings below 65), vasopressor REQUIREMENT →
post-24h mortality; fully-adjusted MICE-pooled OR **2.04 [1.85, 2.24]** (n=7,836).

**All computations run fresh with numpy/scipy from MIMIC-IV cached data.**
Scratchpad probes only; no raw data in repo.

---

## Summary table

| # | Issue | Severity | Verdict |
|---|---|---|---|
| R4-1 | E-value stated as "~2.5" but MICE at correct p0=0.124 gives 3.01 | **CRITICAL** | Correct to 3.01 / CI-lb 2.74 |
| R4-2 | MICE t-distribution vs z-approximation (m=10, high missingness) | **MODERATE** | CI is ~6-9% too narrow; correct with t-dist |
| R4-3 | Linear imputation of skewed labs (lactate, creatinine, bilirubin, platelets) | **MODERATE** | Approximation; can generate negatives; systematic bias direction unclear |
| R4-4 | m=10 insufficient for 67% missingness (lactate) | **MODERATE** | Rules of thumb require m≥50; rerun with m≥25 |
| R4-5 | Shock etiology unmeasured; plausibly reaches E-value threshold | **CRITICAL** | Plausible RR ~2-5 with both exposure and outcome |
| R4-6 | PaO2/FiO2 (P/F ratio) unmeasured; plausibly reaches E-value threshold | **CRITICAL** | Plausible RR ~2-4 with mortality, ~1.5-3 with NEE |
| R4-7 | Within-at-target lactate-tertile ORs attenuated vs full cohort | **MODERATE** | All 3 tertiles CI excludes 1; T3 OR=1.682 — robust |
| R4-8 | Norepi-only restriction: lower OR (1.378) vs full multi-pressor cohort | **MODERATE** | Homogeneous population drives attenuation; age+lac 1.635 |
| R4-9 | Band sensitivity: [60,80] and [65,80] produce identical cohorts | **MINOR** | Only 3 distinct independent bands; adequate |
| R4-10 | Collider interaction p=0.072 overstated as "passed" | **MINOR** | NS ≠ absent; rephrase as no detectable collider amplification |
| R4-11 | AUC gap 0.268–0.156=0.112 had no formal CI | **MINOR** | Fixed: gap diff=0.111, 95% CI [0.080, 0.142], z=6.96, p<0.0001 |
| R4-12 | MICE outcome-in-imputation model; Rubin's formula correctness | **OK** | Both CORRECT per best practice |

---

## Item R4-1 — E-value CORRECTION (CRITICAL)

**The stated "E-value ~2.5" was computed using complete-case baseline mortality
p0=0.197, not the correct at-target stratum mortality p0=0.124.**

Fresh calculation (VanderWeele & Ding 2017, OR→RR→E-value):

| Estimate | OR | p0 | RR_approx | E-value |
|---|---|---|---|---|
| MICE point | 2.036 | 0.124 (at-target, n=7,836) | **1.804** | **3.01** |
| MICE CI-lb | 1.852 | 0.124 | **1.675** | **2.74** |
| MICE point | 2.036 | 0.197 (complete-case used in R3) | 1.691 | 2.77 |
| MICE CI-lb | 1.852 | 0.197 | 1.586 | 2.55 |
| CC point | 1.840 | 0.197 | 1.579 | 2.54 |
| CC CI-lb | 1.561 | 0.197 | 1.406 | **2.16** |

**Required correction:** Report E-value as **3.01 (point), 2.74 (CI-lb)** for the
MICE primary estimate. The "~2.5" description applied to the complete-case CC
OR 1.84 at the complete-case mortality p0=0.197. Using the correct MICE estimate
and the correct at-target denominator p0=0.124 raises the E-value, strengthening
the finding. Do NOT continue to state "E-value ~2.5" when the primary MICE OR is
2.04; the correct statement is "E-value 3.01 (CI-lb 2.74)."

---

## Item R4-2 — MICE CI uses z=1.96 instead of t-distribution (MODERATE)

Rubin's rules with m=10 imputations require a t-distribution with degrees-of-freedom:

```
nu = (m-1) * (1 + U_bar / ((1 + 1/m) * B))^2
```

With m=10, even if nu is as large as 20 (optimistic), the correct multiplier is
t(20, 0.975) = 2.086 vs z = 1.96, widening the 95% CI by **6.4%**. With nu=15
(more likely for 67% missingness), widening is 8.7%.

Corrected CI (nu~20): [exp(0.711 − 2.086×0.0483), exp(0.711 + 2.086×0.0483)] =
**[1.841, 2.252]** vs currently reported [1.852, 2.238].

The lower bound shifts from 1.852 → **1.841** with t-correction. The E-value
for the corrected lower bound:

RR(OR=1.841, p0=0.124) = 1.634, E-value = **2.74** (unchanged to 2 dp).

**Net effect:** The corrected CI is slightly wider; E-value at the CI-lb remains
2.74. The code in `_mice_or()` should replace the hardcoded `1.96` with the
t-quantile `scipy.stats.t.ppf(0.975, df=nu)` where nu is computed from the
ratio of within- to between-imputation variance per Barnard & Rubin (1999).

---

## Item R4-3 & R4-4 — MICE Implementation Review (MODERATE)

**Code reviewed:** `analysis/icu_occult_dependence.py`, function `_mice_or()`.

### What is correct

1. **Outcome (died) included in imputation model:** CORRECT per Rubin (1996)
   and van Buuren (2018). Omitting the outcome would attenuate associations —
   this is a common published MICE error; this code avoids it.

2. **Chained imputation with residual draw:** standard MICE approach; `pred =
   X[miss[k]] @ beta + rng.normal(0, sd, miss[k].sum())` — correct stochastic
   imputation.

3. **Rubin's rules pooling formula:** `Q_bar = mean(log_ors)`, `U_bar =
   nanmean(vars_)`, `B = var(log_ors, ddof=1)`, `Total = U_bar + (1+1/m)*B`
   — formula is correct (Rubin 1987, eq. 3.1.5).

4. **Sanity check — MICE OR 2.04 > CC OR 1.84:** DIRECTIONALLY CORRECT.
   Complete cases were sicker (higher NEE mean 136 vs 79; higher mortality 19.7%
   vs 10.8%). The OR in the sicker complete-case subset was attenuated because
   severity confounders were stronger there, making the fully-adjusted residual
   smaller. MICE recovers the signal from the less-sick majority. This is not a
   contradiction — it is the expected behaviour of MICE under informative
   missingness where complete cases are a selected sick stratum.

### Issues

**R4-3 (MODERATE): Linear imputation of skewed labs.** Lactate, creatinine,
bilirubin, and platelets are non-negative and right-skewed. Chained linear
imputation can generate negative predicted values for the most extreme missing
cases (the code does not clip to [0, ∞)). Standard remediation: log-transform
before imputation, then exponentiate the imputed value. Systematic direction of
bias: imputed labs that are spuriously negative or near-zero would compress the
lab range, possibly attenuating the OR slightly (making it conservative). The
magnitude is small for most labs except bilirubin (most skewed).

**R4-4 (MODERATE): m=10 insufficient for 67% missingness.** White et al. (2011,
Stat Med) recommend m ≥ percent missing. Lactate is missing in 67% of at-target
patients, so m ≥ 67 is the strict rule of thumb. With m=10, the between-
imputation variance B has a relative SE of sqrt(2/(m-1)) = sqrt(2/9) = 47%,
making B itself highly uncertain and the total SE estimate noisy. This inflates
the posterior uncertainty of the CI estimate itself. The point estimate (Q_bar)
is unbiased with even m=5, but the CI width is unreliable. Recommend m=25–50.

### Bug search — does any code error systematically bias OR=2.04?

- `design(k)` returns columns [1, age, lognee, mapm, comorb, died, other_labs] —
  correct; outcome is in the imputation model.
- `resid = labs[k][obs] - X[obs] @ beta` and `sd = resid.std()` — computed on
  observed rows only; correct.
- `Z = np.column_stack([( (f - f.mean()) / (f.std() or 1.0) ) for f in feats])`:
  lognee is re-standardized per imputed dataset. Since NEE is not imputed, its
  mean/SD are constant across datasets; re-standardization is harmless.
- No bug identified that would systematically inflate OR to 2.04. The OR is
  plausible and internally consistent.

**MICE VALIDITY VERDICT:** Structurally valid. Three implementation improvements
needed (t-quantile CI; log-transform labs; m≥25). No directional bias identified.
The OR 2.04 is a reliable approximation.

---

## Item R4-5 & R4-6 — Is E-value 2.74 Adequate? (CRITICAL)

### Named missing confounders

**GCS / Depth of sedation (MODERATE threat)**

Sedation-induced vasodilation requires more norepinephrine (plausible residual RR
with NEE ~1.5–2.5 after adjusting our 6 covariates). Low GCS / deep sedation
predicts mortality independently (~RR 2–4). If residual RR with each arm is ~1.7,
the product reaches the threshold. This is a marginal threat; deep sedation is
partially correlated with SOFA-component severity (high bilirubin/creatinine in
multi-organ failure states that accompany deep sedation), so the 6-covariate
adjustment absorbs some of this variance. Assessment: marginal, not certain.

**PaO2/FiO2 ratio (MODERATE-HIGH threat) — CRITICAL**

Hypoxemia/ARDS causes vasoplegia (via hypoxic pulmonary vasoconstriction,
right ventricular failure) and predicts mortality strongly (RR ~2–4 in critically
ill cohorts). P/F ratio is NOT captured by our 6-covariate adjustment. Residual
association with NEE requirement (~1.5–3) and mortality (~2–4) each plausibly
remains after conditioning on lactate + SOFA labs (which don't include a
respiratory variable). The product of residual RRs could individually exceed 2.74.

**This is the most credible single E-value-breaking threat.**

**Shock etiology (HIGH threat) — CRITICAL**

Within the at-target stratum, shock etiology drives both the vasopressor requirement
(septic >> cardiogenic >> vasodilatory) and mortality (cardiogenic/mixed >> septic >>
distributive). The comorbidity_count partially encodes etiology through ICD codes
but not as a direct clinical variable. Residual RR with both arms is plausibly ~2–5
for a septic vs cardiogenic contrast, exceeding the threshold.

**This is the second most credible E-value-breaking threat.**

**Corticosteroids (NOT a threat — negative confounder)**

Steroids reduce vasopressor requirements ~30–40% (ADRENAL, APROCCHSS) AND reduce
mortality in septic shock. Steroid use → lower NEE AND lower mortality. This is a
negative confounder that attenuates the OR below its true value. If corticosteroids
are the unmeasured variable, the true OR is *higher* than 2.04, not lower.

**Fluid resuscitation adequacy (MINOR threat)**

Inadequate fluids → more pressors, worse outcomes. But RRs with both sides
individually (~1.3–2.0 each) are likely insufficient to breach the E-value
threshold of 2.74 alone.

### Verdict

**E-value 2.74 (CI-lb) is an adequate threshold for reporting and benchmarking
but does NOT exclude confounding.** PaO2/FiO2 and shock etiology are individually
plausible E-value-breakers. The counterargument (32% attenuation absorbed by
6 covariates; residual RR ≤1.7 each after adjustment) is reasonable but untestable.

**Required disclosure:** "Unmeasured confounders including PaO2/FiO2 ratio and
shock etiology were not directly adjusted. Each may have a residual association
with both vasopressor requirement and mortality sufficient to approach or exceed
the E-value threshold of 2.74 (CI-lb). Confounding-by-indication is bounded
by the E-value analysis, not excluded. The finding is presented as risk-
stratification information, not a causal treatment effect."

---

## Item R4-7 — Within-Stratum Lactate Tertile Analyses (NEW, MODERATE)

**Requirement→mortality WITHIN lactate tertiles INSIDE the at-target stratum.**
Lactate-measured subset: n=2,278 of 7,841 (29%). Tertile cutpoints: 1.90, 3.10
mmol/L.

| Tertile | n | Mortality | Age-adj OR | 95% CI |
|---|---|---|---|---|
| T1 (lactate <1.90, low severity) | 713 | 0.080 | **1.454** | [1.138, 1.806] |
| T2 (lactate 1.90–3.10, mid) | 791 | 0.062 | **1.514** | [1.195, 1.913] |
| T3 (lactate ≥3.10, high severity) | 774 | 0.140 | **1.682** | [1.419, 2.039] |

All three tertiles: CI excludes 1; ORs increase monotonically from T1→T3 (trend).
The finding persists within-severity-stratum across the full lactate range.

**Strength of evidence:** The low-lactate tertile (T1, OR 1.454) is the strongest
within-stratum confounding defense: among at-target patients with near-normal
lactate (<1.90, indicating lower illness burden), the requirement STILL discriminates
mortality. The T3 result (OR 1.682) at high lactate confirms the finding holds at
high severity too, but confounding is hardest to rule out there.

**Caveat:** These ORs (~1.45–1.68) are attenuated relative to the age-only at-target
OR of 2.82 because (a) only 29% have lactate and they are a sicker selected subset,
and (b) within-tertile conditioning absorbs some variance. Full-severity MICE within
tertiles is underpowered (n~700 per tertile; labs incomplete within already-selected
subset).

---

## Item R4-8 — Norepi-Only Sensitivity Within At-Target (NEW, MODERATE)

**Norepinephrine-only patients** (single-pressor, more homogeneous sepsis-enriched
population) within the at-target stratum:

| Model | OR | 95% CI | n |
|---|---|---|---|
| Age-adjusted | **1.378** | [1.181, 1.577] | 1,844 |
| Age + lactate | **1.635** | [1.254, 2.169] | 652 |

The OR is attenuated relative to the multi-pressor at-target cohort (OR 2.82),
which is expected: norepi-only patients have compressed inter-patient NEE variance
(no additive vasopressin/phenylephrine contributions). Despite attenuation, the
association remains positive with CI excluding 1.

**The age+lactate OR of 1.635 [1.254, 2.169] in a homogeneous single-pressor
population is the most confounding-resistant within-stratum estimate available.**
Within a population with a single vasopressor and measured lactate, the indication-
for-treatment is more uniform, making residual confounding-by-indication less
tenable as the sole explanation.

---

## Item R4-9 — Band Cherry-Picking (MINOR)

**[65,85] was the pre-specified primary band** (documented in ICU_OCCULT_DEPENDENCE.md
before analysis). Band sensitivity from R3 (full multi-pressor NEE pipeline):

| Band | n | Age-adj OR |
|---|---|---|
| [60,80] | 6,029 | 2.949 [2.62, 3.29] |
| [65,80] | 6,029 | 2.949 — identical to [60,80] (see note) |
| [65,85] **PRIMARY** | 7,841 | **2.822 [2.58, 3.09]** |
| [70,90] | 8,470 | 2.720 [2.51, 2.97] |

**Note:** [60,80] and [65,80] produce the SAME cohort (n=6,029) because the
<10%-below-65 filter removes left-tail [60,65) stays. These are not independent
sensitivities. Only **3 genuinely independent bands** were tested.

The primary band [65,85] yields a LOWER OR (2.822) than the narrower alternatives
(2.949), inconsistent with cherry-picking. ORs range 2.72–2.95 (8% spread);
the trend is monotone: wider band → more heterogeneous population → slight OR
attenuation.

**Verdict:** Not cherry-picked. Add one genuinely independent intermediate band
(e.g., [65,82] or [67,84]) to expand to 4 truly distinct checks.

---

## Item R4-10 — Collider Test Overstated (MINOR)

The interaction test at-target × NEE → mortality with χ²=3.25, p=0.072 was
described as "PASSED" (collider bias defeated).

**Correct interpretation:** The interaction is non-significant at α=0.05. This
means no statistically detectable collider amplification within this sample.
p=0.072 is NOT "proof the collider is absent" — it is absence of detectable
evidence. The 95% CI of the interaction OR ratio (1.09) easily spans 1.0.

**Required re-wording:** "No statistically significant collider amplification was
detected (interaction χ²=3.25, p=0.072, NS). This does not prove the absence of
collider bias; it establishes that any such bias is not detectable at this sample
size. The post-treatment conditioning caveat should be acknowledged."

---

## Item R4-11 — AUC Gap: Formal CI (MINOR → FIXED)

The AUC gap 0.268 − 0.157 = 0.111 was reported without a formal CI.
Computed here via Hanley-McNeil (1982) SE, treating the two AUCs within each
stratum as independent (conservative upper bound on SE for the gap):

**AT-TARGET** (n=7,841, mort=0.124; n_pos=971, n_neg=6,870):

| | AUC | SE |
|---|---|---|
| NEE requirement | 0.743 | 0.0095 |
| MAP | 0.475 | 0.0098 |
| Gap | **0.268** | 0.0136 |
| **95% CI gap** | **[0.241, 0.295]** | |

**NOT-AT-TARGET** (n=16,079, mort=0.178; n_pos=2,862, n_neg=13,217):

| | AUC | SE |
|---|---|---|
| NEE requirement | 0.712 | 0.0058 |
| MAP | 0.555 | 0.0060 |
| Gap | **0.157** | 0.0084 |
| **95% CI gap** | **[0.141, 0.173]** | |

**DIFFERENCE IN GAPS** (at-target minus not-at-target):
- Difference = **0.111**
- SE = 0.0159 (propagated)
- **z = 6.96, p < 0.0001**
- **95% CI = [0.080, 0.142]**

The across-stratum doubling of the AUC gap (0.157→0.268) is highly statistically
significant. The Hanley-McNeil SE is slightly conservative (ignores within-patient
correlation between AUC_NEE and AUC_MAP), so [0.080, 0.142] is a conservative
lower bound on the precision; the true CI would be tighter.

---

## Item R4-12 — MICE outcome-in-imputation model (OK)

Including `died` in the imputation design matrix is CORRECT (van Buuren 2018,
Flexible Imputation, p. 45; Rubin 1996). Omitting the outcome is the common
mistake; the code avoids it. Rubin's formula Total = U_bar + (1+1/m)*B is the
correct Rubin (1987) formulation. No issue.

---

## Overall assessment

### Is the within-stratum confounding defense adequate?

**Partially adequate; two gaps remain open.**

**Strengths:**
1. Lactate tertile persistence: OR > 1 (CI excludes 1) in ALL three tertiles
   within the at-target stratum, including the low-lactate (low-severity) tertile
   (T1 OR 1.454 [1.138, 1.806]).
2. Norepi-only: age+lac OR 1.635 [1.254, 2.169] in a homogeneous single-pressor
   subset — the most confounding-resistant within-stratum number.
3. E-value is HIGHER than reported: 3.01 (point), 2.74 (CI-lb) for the MICE
   primary estimate at the correct p0=0.124.

**Gaps that remain:**
- PaO2/FiO2 and shock etiology are each credible individual threats to the E-value
  2.74 threshold. The 6-covariate adjustment absorbs ~32% of the association but
  cannot rule out residual RR of ~1.7 from these unmeasured variables.
- The norepi-only age+lactate OR (1.635) is the tightest confounding-controlled
  estimate and represents the minimum reliable signal.

### Is the MICE valid?

**Structurally correct; three implementation improvements required:**

1. Replace z=1.96 with t-quantile (CI is ~6–9% too narrow)
2. Increase m from 10 to 25–50 (required for 67% missingness)
3. Log-transform skewed labs (lactate, bilirubin) before imputation

None introduce directional bias; OR 2.04 is a reliable approximation. CI is
slightly underestimated; the E-value at the corrected CI-lb remains 2.74.

### Remaining CRITICAL issues

| ID | Issue | Action |
|---|---|---|
| **R4-1** | E-value "~2.5" is wrong for MICE primary; correct is 3.01/2.74 | Update ICU_OCCULT_DEPENDENCE.md, REDTEAM_R3_SYNTHESIS.md, and any abstract draft |
| **R4-5** | Shock etiology not adjusted; plausible individual E-value threat | Add required disclosure sentence (see above); flag as primary limitation |
| **R4-6** | PaO2/FiO2 not adjusted; plausible individual E-value threat | Same disclosure; add as second primary limitation; suggest respiratory subgroup as future work |

---

*Generated 2026-06-30. All computations run from scratch with numpy/scipy on
MIMIC-IV cached data (cache/mimic_labs24h.csv, cache/mimic_fluids_pressors.csv,
scratchpad/mimic_map_raw.csv, scratchpad/mimic_icustays_test.csv.gz). Probes
in scratchpad only. File not committed per instructions.*
