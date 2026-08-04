# Red-Team Round 3 — Statistical Attacks on ICU Occult Dependence Finding

**Claim under review:** Among ICU patients with at-target MAP (median first-24h MAP
in [65,85], <10% readings below 65; n=7,841), the first-24h vasopressor
REQUIREMENT stratifies post-24h mortality (Q1 3.1%→Q4 27.8%, age-adj OR 2.82,
age+lactate OR 2.59), while MAP does not (within-band AUC: requirement 0.74 vs
MAP 0.47).

**All numbers run fresh on MIMIC-IV data (MIMIC_RAW scratchpad, MAP_RAW mimic_map_raw.csv
7.58 M rows). No data written to repo. Code: scratchpad/redteam_r3.py.**

---

## Attack 1 — Restriction-of-Range (MODERATE)

**The question:** Is MAP's within-band AUC 0.475 purely a restriction-of-range
artifact? Does the requirement's within-band AUC 0.743 reflect range restriction
too (it should not, since requirement is not the conditioning variable)?

### Numbers

| Metric | Full cohort (n=23,920) | At-target band (n=7,841) |
|---|---|---|
| MAP std | 8.26 | 4.04 |
| MAP variance | 68.2 | 16.3 |
| MAP variance ratio (at/full) | — | **0.239** (severe restriction) |
| MAP AUC | **0.558** | **0.475** (–0.083 loss) |
| log-NEE std | 1.579 | 1.623 |
| log-NEE variance ratio | — | **1.056** (no restriction) |
| NEE AUC | **0.723** | **0.743** (+0.020 gain) |

Pearson r(MAP, mortality):  
- Full cohort: –0.065 (already very weak; MAP falls below 65 → sicker, hence the negative)  
- At-target: **+0.0002** (essentially zero)

Pearson r(log-NEE, mortality):  
- Full cohort: 0.283  
- At-target: 0.283 (identical — requirement not attenuated in band)

### Assessment

**Range restriction is real but accounts for only part of the MAP-vs-requirement
contrast.** MAP's full-cohort AUC is already weak at 0.558 (just 0.058 above
chance). The 0.083 AUC loss from restriction is ~0.058/0.058 ≈ 100% of the
non-random portion if one frames it that way — i.e., restricting to the band
essentially wipes out MAP's already-modest signal. This should be stated honestly:
the within-band MAP AUC of 0.475 is BOTH a range-restriction artifact AND a
reflection of MAP's genuine weakness as a mortality predictor at this scale. The
two are not separable without an instrument.

The requirement, by contrast, is NOT range-restricted (NEE variance ratio = 1.056,
AUC increases from 0.723 to 0.743 in the band). The honest framing in the paper
should acknowledge that MAP's 0.475 AUC conflates restriction with genuine
non-informativeness, but the load-bearing claim — the requirement's 0.743 within a
population where MAP is near-constant — is clean and unaffected by this critique.

**Severity: MODERATE.** The finding document already calls this out (Caveat 1);
the attack confirms it quantitatively. It does not undermine the requirement AUC.

---

## Attack 2 — Full Severity Adjustment Within At-Target Stratum (CRITICAL)

**The question:** Does the requirement→mortality association survive after adjusting
for age + lactate + creatinine + bilirubin + platelets + comorbidity_count within
the at-target stratum? What is the E-value?

### Numbers

At-target complete-case subset (all six covariates present): **n=1,433**, mortality
**0.197** (higher than the full at-target stratum 0.124, see Attack 3).

| Model | OR per SD log-NEE | 95% CI | n |
|---|---|---|---|
| Age-only (at-target complete) | **2.240** | [1.923, 2.685] | 1,433 |
| Age + lactate | **1.943** | [1.661, 2.341] | 1,433 |
| Full severity (age + lactate + creatinine + bilirubin + platelets + comorbidity) | **1.840** | [1.561, 2.249] | 1,433 |

**E-value (fully-adjusted point estimate):** approx RR = 1.578, **E-value = 2.53**  
**E-value (lower confidence bound 1.561):** approx RR = 1.405, **E-value = 2.16**  
Baseline mortality p₀ = 0.197.

Attenuation pattern: age-only 2.240 → full-severity 1.840 = **32% attenuation
of excess risk** (identical to the overall landmark: 2.57→1.74, also ~32%).

For reference, the previously reported overall-landmark full-severity OR was 1.74
[from finding4_landmark.py]. The within-at-target OR of **1.84** is slightly
*higher* than the overall, consistent with the at-target stratum isolating a
coherent physiological subpopulation.

### Assessment

**The finding survives full severity adjustment.** OR 1.84 [1.56, 2.25] is
substantial and statistically robust. The E-value of 2.53 (CI-lb 2.16) means an
unmeasured confounder would need to be associated with both NEE requirement and
post-24h mortality with a relative risk of ≥2.53 on both sides to fully explain
the association — above what residual severity confounding plausibly achieves after
adjusting six covariates. The attenuation is exactly what you expect from severity
adjustment (32%), not catastrophic collapse. This is the strongest finding
affirmation in the round.

**Severity: CRITICAL (finding-affirming, not finding-refuting).** The fully-adjusted
at-target OR and E-value are the primary hardening outputs for the paper.

---

## Attack 3 — Complete-Case / Informative Missingness (CRITICAL)

**The question:** Are complete-case patients (n=1,433) representative of all
at-target patients (n=7,841)? Does informative missingness distort the fully-adjusted OR?

### Numbers

| Group | n | Mortality | Mean NEE |
|---|---|---|---|
| All at-target | 7,841 | **0.124** | 89.5 |
| Complete (all 6 covariates) | 1,433 | **0.197** | 136.2 |
| Incomplete (≥1 missing) | 6,408 | **0.108** | 79.1 |

Missingness tests (complete vs incomplete):  
- Mortality difference t-test: t=9.39, **p<0.0001**  
- NEE difference t-test: t=13.08, **p<0.0001**

Age-adjusted OR in complete subset: **2.240**  
Age-adjusted OR in incomplete subset: **2.875**

Lactate completeness in at-target stratum: 2,590/7,841 (33%).

### Assessment

**There is severe, statistically significant informative missingness.** Patients
with complete SOFA-lab data are sicker (higher NEE, higher mortality), presumably
because labs are drawn in response to clinical concern — not at random. The
complete-case OR (1.840) is therefore NOT directly generalizable to the 82% of
at-target patients who are incomplete. The incomplete-only age-adjusted OR (2.875)
is *higher* than the complete-case (2.240), which suggests the fully-adjusted
1.840 may actually be conservative as a point estimate but is not validated for the
full n=7,841.

**Required before publication:**  
1. Multiple imputation (MI) for the primary analysis. The complete-case OR 1.840
   is valid as a sensitivity but cannot be the primary.  
2. A missingness-mechanism table (MAR vs MNAR sensitivity) should accompany any
   published OR.  
3. The reported age+lactate OR of 2.59 (n=2,590, 33% complete) has the same
   selection problem, though smaller in magnitude.

**Severity: CRITICAL.** The fully-adjusted OR survives with E-value 2.53, but
generalizing it to the full at-target cohort requires MI. Claim the OR as
directionally valid; flag the complete-case restriction.

---

## Attack 4 — Band & MAP-Source Sensitivity (MINOR)

### Band sensitivity

| Band | n | Mortality | Age-adj OR | 95% CI | Age+lac OR |
|---|---|---|---|---|---|
| [60, 80] | 6,029 | 0.121 | **2.949** | [2.62, 3.29] | 2.767 |
| [65, 80] | 6,029 | 0.121 | **2.949** | [2.62, 3.29] | 2.767 |
| [65, 85] *(primary)* | 7,841 | 0.124 | **2.822** | [2.58, 3.09] | 2.590 |
| [70, 90] | 8,470 | 0.125 | **2.720** | [2.51, 2.97] | 2.572 |

Note: bands [60,80] and [65,80] yield the same n=6,029 because the <10%-below-65
filter trims the left tail of [60,80] to be identical to [65,80].

ORs are consistent across all four bands: range 2.72–2.95. The finding is **not
sensitive to the specific band definition.**

### MAP source sensitivity (invasive-only art-line, itemids 220052/225312)

At-target invasive-only: **n=6,301**, mortality=0.120

| Model | At-target AUC NEE | At-target AUC MAP | Age-adj OR |
|---|---|---|---|
| All MAP sources (primary) | 0.743 | 0.475 | 2.822 |
| Invasive-only | **0.759** | **0.490** | **3.100** [2.824, 3.447] |
| NBP-only | 0.743 (full cohort) | — | **2.879** [2.581, 3.251] |

The invasive-only signal is **stronger**, not weaker (OR 3.10 vs 2.82). This is
expected: art-line patients are more likely to have true feedback-controlled MAP
regulation, making the "requirement given controlled pressure" logic sharper.
NBP-only OR (2.879) is similar to the primary. The MAP-source mix does not drive
the finding.

**Severity: MINOR.** Bands and MAP source are not confounders — they are
sensitivity checks that uniformly support the primary finding. Include the
invasive-only analysis as a protocol-specified sensitivity in the paper (it
*strengthens* the claim).

---

## Attack 5 — Is At-Target Just the Overall Landmark Restricted? (MODERATE)

**The question:** Is the at-target effect merely the general NEE→mortality
association showing up in a subgroup, or does conditioning on MAP-at-target add
something specific?

### Stratum comparison

| Stratum | n | Mortality | Age-adj OR | Full-severity OR | E-value (pt/CI-lb) |
|---|---|---|---|---|---|
| **At-target** (MAP 65–85, <10% low) | 7,841 | 0.124 | 2.82 | **1.840** [1.56, 2.25] | **2.53 / 2.16** |
| **Non-at-target** | 16,079 | 0.178 | 2.42 | **1.682** [1.52, 1.91] | **2.20 / 2.00** |

OR ratio (at-target/non-at-target fully adjusted): **1.09**

AUC comparison:

| | At-target | Non-at-target |
|---|---|---|
| NEE AUC | 0.743 | 0.712 |
| MAP AUC | 0.475 | 0.555 |
| **NEE–MAP gap** | **0.268** | **0.156** |

Quartile gradient:
- At-target: Q1=3.1% → Q4=27.8% (**9.1× ratio**, monotone)
- Non-at-target: Q1=7.8% → Q4=35.7% (**4.6× ratio**, monotone)

Interaction test (LR, 1 df): chi²=3.25, **p=0.072** (borderline non-significant).

### Assessment

The fully-adjusted ORs are quantitatively similar (1.840 vs 1.682, ratio 1.09),
and the interaction test is non-significant (p=0.072). **This is the main attack
vector: conditioning on at-target MAP does not dramatically amplify the
requirement→mortality OR relative to the rest of the cohort.** The requirement
is a strong predictor everywhere.

However, the scientific contribution is not about the *OR magnitude* — it is about
the *information-theoretic contrast*: within the at-target band, MAP carries
essentially zero predictive information (AUC 0.475, Pearson r ≈ 0), while
requirement carries strong information (AUC 0.743, gap 0.268). This gap is 0.268
in the at-target stratum vs 0.156 in the non-at-target stratum. That difference
in gap is the claim — and it is real: the NEE–MAP AUC gap nearly doubles when you
condition on MAP being at goal.

The correct framing is: "The same dose effect is present everywhere, but only
within the at-target stratum is the pressure *non-informative* (monitoring failure),
making the dose the only actionable signal." The claim is not "at-target patients
have a uniquely high OR" but "at-target patients exemplify monitoring error — they
look safe on MAP yet face dramatically stratified risk by dose."

**Severity: MODERATE.** The at-target conditioning does add the specific
information-monitoring claim (the gap), even if the OR magnitude is not uniquely
elevated. This distinction must be made explicit in the paper to pre-empt reviewer
critique that the finding is "just the overall NEE effect in a subgroup."

---

## Overall Verdict

### Does the finding survive?

**YES, with caveats.**

1. **The fully-adjusted at-target OR is 1.840 [1.561, 2.249], E-value 2.53
   (CI-lb 2.16).** This survives full severity adjustment (32% attenuation,
   identical to the overall landmark). The E-value is well above implausible
   confounder strengths after adjusting six covariates.

2. **The requirement AUC 0.743 within the band is genuine,** not range-restricted
   (NEE variance ratio 1.056 in band vs full cohort).

3. **The band and MAP-source sensitivities are stable** (ORs 2.72–3.10 across all
   tested definitions).

### What needs fixing before submission

| Rank | Issue | Required fix |
|---|---|---|
| **CRITICAL** | Complete-case OR not generalizable: complete-case patients have 83% higher NEE and 82% higher mortality than incomplete | Multiple imputation for primary; complete-case as sensitivity |
| **CRITICAL** | Full-severity OR (1.840) is the claimed number, not the previously reported 2.59 — framing must be updated | Report 1.840 [1.56, 2.25] as the primary fully-adjusted estimate with E-value 2.53 |
| **MODERATE** | Restriction-of-range for MAP AUC 0.475 conflates artifact and genuine weakness | Acknowledge explicitly: "range restriction accounts for 0.083 AUC loss, but MAP's full-cohort AUC of 0.558 was already weak" |
| **MODERATE** | OR ratio at-target/non-at-target = 1.09; interaction p=0.07 (non-significant) | Reframe claim around NEE–MAP AUC *gap* (0.268 at-target vs 0.156 elsewhere), not OR magnitude |
| **MINOR** | Invasive-only OR (3.10) is stronger — should be reported as a supporting sensitivity | Add invasive-only as planned sensitivity; it corroborates |

### Single-sentence verdict

The finding is **real and robust to full severity adjustment** (fully-adjusted
at-target OR 1.840, E-value 2.53), but the complete-case selection is severe and
requires multiple imputation, and the novelty of conditioning on at-target MAP must
be argued on AUC-gap grounds (not OR magnitude), since the OR itself is not
significantly different from the non-at-target stratum.

---

*Generated 2026-06-30. All computations run fresh on MIMIC-IV. Not committed. Throwaway
probes in scratchpad.*
