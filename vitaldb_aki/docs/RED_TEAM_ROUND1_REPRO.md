# Red-Team Round 1: Independent Reproduction Audit

**Auditor:** independent re-derivation (no code re-use from finding4_landmark.py)
**Date:** 2026-06-30
**Primary finding under scrutiny:** Finding 4 — Landmark NEE-load OR per SD, age-adjusted,
first-24h window, restricted to patients alive at the 24-h landmark.
**Claimed headline:** OR ~2.568 (95% CI 2.452–2.681), Q1 mortality 0.06, Q4 mortality 0.33,
monotone quartile gradient.

---

## Task 1 — Subject vs Stay Count (mimic_norepi.csv)

| Metric | Value |
|--------|-------|
| Distinct subject_id | 13,549 |
| Distinct stay_id | 15,951 |
| Ratio stays/subjects | 1.177 |
| Subjects with > 1 stay | 1,712 (12.6 %) |

**Implication:** The unit of analysis in all MIMIC findings is the ICU *stay*, not the *subject*.
12.6 % of subjects appear more than once. If the primary CI is computed by bootstrapping stays
(the current implementation), observations from the same patient are treated as independent —
a violation of the iid assumption. The magnitude of this bias is quantified in Task 3.

---

## Task 2 — Independent Reproduction of the Landmark OR

All logic was re-implemented from scratch (reading the same three gzipped MIMIC tables and
the pre-filtered `cache/mimic_fluids_pressors.csv`). Vasopressor NEE conversion, 24-h window
gate, landmark alive restriction, and IRLS logistic regression with age co-variate were all
re-coded independently.

### Cohort counts

| | Claimed | Independent |
|-|---------|-------------|
| Stays with any pressor (first 24h) | 25,119 | **25,119** |
| Excluded: dead before landmark | 1,194 | **1,194** |
| Excluded: no age | 0 | **0** |
| N analyzed | 23,925 | **23,925** |
| Post-landmark overall mortality | 0.1602 | **0.1602** |

### OR estimate

| Model | Claimed OR | Repro OR | Claimed 95% CI | Repro 95% CI |
|-------|-----------|---------|---------------|-------------|
| Age-adj (dopa wt 0.01) | 2.568 | **2.568** | [2.452, 2.681] | **[2.452, 2.681]** |

### Quartile gradient

| Quartile | Claimed mortality | Repro mortality | N |
|----------|-----------------|----------------|---|
| Q1 (lowest NEE) | 0.0600 | **0.0600** | 5,981–5,982 |
| Q2 | 0.0973 | **0.0973** | 5,981 |
| Q3 | 0.1491 | **0.1490** | 5,981 |
| Q4 (highest NEE) | 0.3344 | **0.3345** | 5,981–5,982 |
| Monotone non-decreasing | TRUE | **TRUE** | — |

**Verdict: the headline numbers reproduce exactly** (rounding to 3–4 decimal places throughout).
The Q4 value differs by 0.0001 due to rounding direction, not a computation error.

---

## Task 3 — Subject-Clustered Sensitivity

### Bootstrap comparison (1,000 iterations each)

| Method | OR | 95% CI | CI width | Width ratio vs stay-level |
|--------|-----|--------|----------|--------------------------|
| Stay-level bootstrap (current, 1000 iter) | 2.568 | [2.447, 2.690] | 0.243 | 1.000 |
| **Subject-clustered bootstrap (1000 iter)** | 2.568 | **[2.443, 2.691]** | **0.248** | **1.021** |
| First-stay per subject (stay-level BS) | 2.636 | [2.505, 2.775] | 0.270 | 1.111 |

### Interpretation

- **Subject-clustering widens the CI by only ~2 %** (width 0.243 → 0.248). With 12.6 % of
  subjects contributing multiple stays, the actual within-subject correlation in NEE exposure
  is modest enough that the clustering correction is negligible in practice.
- **The OR does not move** (2.568 → 2.568 under clustered bootstrap), confirming the point
  estimate is not distorted by the repeat-subject structure.
- **First-stay restriction raises the OR slightly to 2.636** with a wider CI (fewer
  observations, n = 20,674 vs 23,925), but the direction and magnitude of the effect are
  entirely consistent. The headline number, if anything, is *conservative* relative to the
  first-stay-only analysis.
- **Bottom line:** the stay-level CI published in finding4_landmark.json (2.452–2.681) is
  accurate to within <3 % of the subject-clustered interval. The narrowing is not
  materially misleading. However, the report should note that subject-clustered CIs were
  checked and do not materially differ, for methodological completeness.

---

## Task 4 — MIMIC Reliability 0.95: Is It Inflated by Repeat Stays?

The reported reliability (Spearman r = 0.9467 ≈ 0.95) is computed in
`analysis/autocorrelation_attack.py` as a **within-stay split-half** Spearman correlation:

- Unit: each ICU *stay* (not subject).
- Per stay, odd-indexed segments → median rate; even-indexed segments → median rate.
- Spearman(odd_medians, even_medians) across stays.

### Key facts

| Metric | Value |
|--------|-------|
| Stays contributing to reliability (≥4 norepi segments) | 13,585 |
| Unique subjects contributing | 11,707 |
| Stays from subjects with > 1 stay in this reliability set | 3,238 (23.8 %) |

### Could repeat subjects inflate the r?

The split-half design measures **within-stay segment-to-segment consistency** —
it asks "does the odd-segment median predict the even-segment median for the same stay?"
This is logically independent of whether the same *subject* appeared in a prior stay.
Multiple stays from one subject are treated as independent stay-level data points,
which is correct for the within-stay reliability question.

However, the Spearman r computed across stays implicitly assumes independence of
data rows. With 23.8 % of stays from repeat subjects, rows are not fully independent.
To check whether this artificially inflates r:

| Subset | n_stays | Spearman r |
|--------|---------|-----------|
| All stays | 13,585 | **0.9467** |
| First stay per subject only | 11,504 | **0.9476** |

**The reliability r barely changes (+0.0009) when restricted to first stays only.**
The repeat-stay structure does NOT inflate the 0.95 figure. The reliability is a
genuine within-stay trait, not an artefact of repeated measurements on the same patient.

**Minor caveat (non-critical):** The Spearman test p-value nominally assumes independence.
With ~23.8 % of rows from repeat subjects, the effective N is slightly smaller than 13,585.
Given r = 0.947, statistical significance is not remotely in question. The caveat should
be noted in the methods for completeness but does not change the qualitative conclusion.

---

## Summary Table

| Claim | Claimed value | Independently reproduced | Verdict |
|-------|--------------|--------------------------|---------|
| N analyzed (landmark cohort) | 23,925 | 23,925 | PASS |
| Overall post-landmark mortality | 16.02 % | 16.02 % | PASS |
| Age-adj OR per SD log-NEE | 2.568 | **2.568** | PASS |
| 95% CI (stay-level) | [2.452, 2.681] | **[2.452, 2.681]** | PASS |
| Q1 mortality | 0.0600 | 0.0600 | PASS |
| Q4 mortality | 0.3344 | 0.3345 | PASS (rounding) |
| Monotone quartile gradient | TRUE | TRUE | PASS |
| CI widening under subject-clustering | (not claimed) | +2 % | LOW CONCERN |
| OR shift under subject-clustering | (not claimed) | 0.000 | NO CONCERN |
| Reliability 0.95 inflated by repeat stays | (not claimed) | +0.001 | NO CONCERN |

---

## Integrity Findings

1. **Numbers are reproducible.** Every headline number was independently re-derived and
   matches the existing code output to within rounding.

2. **Subject-level clustering is not a material threat.** The CI widens by only ~2 % under
   subject-clustered resampling. The OR is unchanged. The report should add one sentence
   noting that subject-clustered CIs were verified.

3. **The reliability 0.95 is not inflated by repeat stays.** First-stay-only r = 0.948,
   indistinguishable from 0.947. The within-stay split-half design is appropriate.

4. **Minor disclosure gap:** The published bootstrap (400 iter, stay-level) does not note
   that ~12.6 % of subjects have multiple stays. This should be disclosed, but does not
   invalidate the result given the sensitivity analysis above.

5. **No data integrity holes detected** in the subject/stay linkage, the landmark
   restriction logic, or the NEE conversion gates. The exclusion counts (n=1,194 dead
   before landmark) are reproducible from the raw MIMIC tables.
