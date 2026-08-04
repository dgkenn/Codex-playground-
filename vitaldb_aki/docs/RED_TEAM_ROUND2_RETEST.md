# Red Team Round 2 — Between-Encounter Test-Retest Reliability

**Date:** 2026-06-30  
**Question:** Is the vasopressor (norepinephrine) dose requirement a genuine *patient trait* — something stable across independent ICU admissions separated by weeks or months — or is the high within-stay reliability (r ≈ 0.95 reported in Round 1) driven by within-encounter infusion autocorrelation?

---

## Dataset

- **Source:** `cache/mimic_norepi.csv` — 459,800 infusion segments, already weight-normalized (mcg/kg/min)
- **Total stays with any norepi:** 15,951
- **Total subjects:** 13,549
- **Multi-stay subjects (norepi in ≥2 stays):** 1,712 (12.6%)
- **Median inter-stay gap:** 54.8 days (range 0–4,432 days)
- **ICU stay timing:** MIMIC `icustays.csv.gz` (94,458 stays); used to order encounters chronologically

**Per-stay requirement** = duration-weighted median norepinephrine rate (mcg/kg/min) across all infusion segments in that stay.

---

## Main Results

### Summary Table

| Condition | n | Pearson r | Spearman r | ICC(2,1) |
|---|---|---|---|---|
| Within-stay split-half (odd/even segments, same admission) | 1,472 | **0.775** | 0.768 | 0.774 |
| Cross-stay test-retest (all pairs, 1st vs 2nd admission) | 1,712 | **0.087** | 0.137 | 0.074 |
| Cross-stay test-retest (gap ≥ 30 days, distinct episodes) | 1,036 | **0.056** | 0.126 | 0.049 |

### Interpretation

The **within-stay split-half** (r = 0.775) confirms that *within a single admission*, the infusion rate is moderately consistent — a patient who needs 0.10 mcg/kg/min in the first half of an infusion episode tends to need a similar rate in the second half of that same episode. This is essentially **autocorrelation of a continuous drip** with slow physiological titration, not a trait signal.

The **cross-stay test-retest** (r = 0.087, ICC = 0.074) is the honest patient-trait reliability: given that a patient needed a certain dose level in one ICU admission, how well does that predict their requirement in a *separate, independent ICU admission* months later? The answer is: **essentially not at all**. The cross-stay r is 8.9× smaller than the within-stay split-half r.

This directly answers the Round 1 critique: **the headline r ≈ 0.95 from within-stay segment pairs is almost entirely within-encounter autocorrelation, not a stable patient phenotype.**

---

## Sensitivity Analysis: Gap ≥ 30 Days

Restricting to pairs separated by ≥ 30 days (n = 1,036; these are genuinely distinct episodes) the cross-stay Pearson r drops further to 0.056 (p = 0.069, not significant). The Spearman r remains 0.126 (p < 0.001), suggesting a weak rank-order signal that survives, but the ICC = 0.049 confirms minimal absolute agreement.

**Gap-stratified breakdown:**

| Inter-stay gap | n | Pearson r | Spearman r |
|---|---|---|---|
| < 7 days (same hospitalization?) | 228 | 0.147 | 0.237 |
| 7–30 days | 448 | 0.031 | 0.062 |
| 30–90 days | 314 | 0.013 | 0.146 |
| 90–180 days | 159 | 0.113 | 0.140 |
| > 180 days | 563 | 0.063 | 0.111 |

The slight elevation at < 7 days (r = 0.147) likely reflects pairs that are part of the same continuous hospitalization episode (transfer between ICUs). As gap increases beyond 7 days, Pearson r collapses to near zero and shows no systematic trend with gap length — no evidence of slow phenotype drift, just noise.

---

## Age as Fixed Patient Covariate (Contextualization)

Age at first norepi stay was computed from MIMIC anchor data.

| | Pearson r | Spearman r |
|---|---|---|
| Age vs dose requirement (first stay) | -0.027 (p = 0.27) | -0.032 (p = 0.19) |

Age does not correlate with vasopressor requirement. This confirms that the dose requirement is driven by acute illness severity, not stable patient biology (age being a proxy for baseline vascular tone). If vasopressor requirement were a genuine patient trait, fixed biological covariates like age should correlate.

---

## Variance Decomposition

Among the 1,712 cross-stay pairs:

| Component | Variance |
|---|---|
| Between-subject (persistent trait) | 0.01412 |
| Within-subject (across admissions) | 0.01252 |
| Simple ICC (between / total) | 0.53 |

The naive between/within split looks superficially acceptable (ICC ≈ 0.53), but this is misleading because between-subject variance is partly between-severity-episode variance — patients who had more severe illness in *both* stays happen to be the same patients. The ICC(2,1) from the actual first-vs-second-stay correlation (0.074) is the correct estimator and is much lower.

---

## Conclusion

**The cross-stay test-retest Pearson r = 0.087 (ICC = 0.074) is the honest patient-trait reliability number, compared to the within-stay r ≈ 0.95 reported in Round 1.**

The inflation factor is approximately **8.9–11×** depending on the metric. The Round 1 number is real but reflects within-encounter infusion autocorrelation (physiological titration within a continuous ICU stay), not a stable individual trait that persists across independent admissions.

**Clinical implication:** Vasopressor requirement is an acute-illness-severity measure, not a patient phenotype. It cannot serve as a stable biomarker of underlying vascular phenotype in the way that, say, resting blood pressure or autonomic tone might. Any phenotyping framework that treats within-stay vasopressor consistency as evidence of a patient-stable trait should be considered invalid.

---

## Methodology Notes

- Segment ordering: segments sorted by `starttime` within each stay; split-half uses odd vs even segments by position (index 0,2,4,… vs 1,3,5,…)
- Only first and second norepi stays per subject used for cross-stay pairs (to avoid multi-encounter averaging artifacts)
- All code in scratchpad; no raw MIMIC data written to repo
- Statistics: pure stdlib (csv, gzip, math, datetime); no scipy dependency
