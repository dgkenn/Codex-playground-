# RED_TEAM_ROUND1_STATS.md — Statistical Review (Round 1)

**Reviewer role:** Statistical reviewer, top anesthesiology/critical-care journal  
**Date:** 2026-06-30  
**Scope:** Focused statistical-methodology critique of the unified claim: vasopressor requirement is a reliable, prospectively-validated, mortality-graded patient trait. Central numbers: reliability split-half 0.82/0.87/0.95; landmark prospective OR 2.27 [2.10,2.48] (n=23,925); beyond-severity OR 2.4–2.5 (adj lactate+SOFA).

Evidence base: `analysis/finding4_landmark.py`, `analysis/mimic_sofa_lactate.py`, `analysis/pressor_requirement.py`, `cache/mimic_norepi.csv`, `cache/mimic_external_validation.json`, `cache/finding4_landmark.json`, `cache/mimic_sofa_lactate.json`, `cache/autocorrelation_attack.json`, `docs/STATS_CODE_AUDIT.md`, `docs/IMMORTAL_TIME_AUDIT.md`, `docs/ROUND3_COMPLETENESS.md`.

---

## Findings table

| # | Issue | Severity | NEW / DISCLOSED |
|---|-------|----------|-----------------|
| S1 | MIMIC split-half reliability 0.947 inflated by multi-stay subject clustering — unprobed | **CRITICAL** | **NEW** |
| S2 | Landmark age+lactate OR 2.27 compares incompatible denominators (n=7,452 vs n=23,925) without the within-subset age-only OR | **CRITICAL** | **NEW** |
| S3 | Bootstrap in finding4_landmark.py resamples stays, not subjects — for the landmark-specific CI (23,925 stays, ~20,322 subjects) | **MODERATE** | PARTIALLY DISCLOSED |
| S4 | SOFA approximation "bounded risk" argument: "slightly" understates attenuation risk from missing GCS + respiratory (0–8 additional SOFA points, both commonly impaired in vasopressor ICU patients) | **MODERATE** | PARTIALLY DISCLOSED |
| S5 | Multiplicity across the unified claim: four findings, three cohorts, multiple outcome specifications — no single pre-registered primary with a multiplicity-corrected CI | **MODERATE** | ALREADY-DISCLOSED (as framing debt) |
| S6 | Temporal window mismatch: lactate adjuster in landmark uses hospital admittime +24h; NEE exposure uses ICU intime +24h — unacknowledged | **MODERATE** | **NEW** |
| S7 | Split-half reliability method: Spearman of odd/even epoch medians, not ICC(2,1) — acknowledged but unmotivated | **MINOR** | ALREADY-DISCLOSED |
| S8 | Autocorrelation rebuttal (time-gapped early→late): sound | — | ALREADY-DISCLOSED, SOUND |

---

## S1 — CRITICAL — NEW
### MIMIC split-half reliability 0.947 is inflated by multi-stay subject clustering

**The specific hole.**  
`mimic_external_validation.py` computes the split-half reliability as: for each ICU stay with ≥4 norepinephrine segments, compute `median(rates[0::2])` (odd epochs) and `median(rates[1::2])` (even epochs); then `Spearman(rel_odd, rel_even)` across **n=13,585 stays** → `r=0.947`, reported as MIMIC ICU reliability.

From `cache/mimic_norepi.csv` (the source population): **13,549 distinct subjects across 15,951 stays**, yielding a stays-to-subjects ratio of **1.177**. Of 15,951 stays, **4,114 (25.8%) come from 1,712 subjects with ≥2 stays**. For the 13,585-stay reliability cohort (stays with ≥4 segments), this implies approximately **3,503 stays (~25.8%) from multi-stay subjects**, or equivalently roughly **~1,453 subjects contributing >1 row to the correlation**.

**Why this inflates r.**  
The Spearman is computed across 13,585 (ODD, EVEN) pairs. A patient with chronically high vasopressor requirement contributes multiple stays, each with high ODD and high EVEN medians. These extra concordant pairs shift the pooled Spearman upward relative to the true within-stay measurement reliability. Formally: the observed Spearman conflates (a) within-stay consistency of segment medians (the quantity of interest) with (b) between-patient variance in the pooled requirement level, which is amplified by repeated stays. The between-patient ICC(1) is **0.392** (`cache/autocorrelation_attack.json`), confirming substantial between-patient variance that systematically inflates both ODD and EVEN medians for high-requirement patients across all their stays.

**What was and was not probed.**  
`STATS_CODE_AUDIT.md` item 4 states: *"Reliability, early→late, and mortality treat stays as independent; 2,402 of 15,949 rows are repeat subjects."* It then probes only the **mortality** clustering (patient-clustered OR CI [3.45,4.19] vs reported [3.44,4.17] — robust). The document does NOT probe whether the **reliability r=0.947** holds up when restricted to one stay per subject. The `IMMORTAL_TIME_AUDIT.md` confirms the survivorship dependence of reliability (0.947 vs 0.971 in long survivors, a +0.024 difference) but does not address multi-stay subject clustering at all.

**The VitalDB comparison compounds the problem.**  
VitalDB is surgical (one operating-room case per patient, zero multi-stay contamination). The gap between MIMIC 0.947 and VitalDB 0.817 is partly attributable to this methodological asymmetry, not only to a genuine ICU vs OR physiological difference.

**Resolution.**  
Run `mimic_external_validation.py` restricted to one (randomly selected or first) stay per subject (n_unique_subjects ≈ 11,540–13,549 depending on ≥4-segment gate), recompute `Spearman(rel_odd, rel_even)`. If the result is materially below 0.947 (e.g., 0.85–0.90), the reported MIMIC reliability overstates within-stay consistency and the paper must correct it. Alternatively, compute the split-half ICC(2,1) (two-way mixed effects, absolute agreement) with subject as a random effect, which properly partitions between-patient and within-stay variance.

---

## S2 — CRITICAL — NEW
### Landmark age+lactate OR 2.27 [2.10,2.48] compares incompatible denominators

**The specific hole.**  
`finding4_landmark.py` reports:

| Model | n | OR/SD | 95% CI |
|---|---|---|---|
| Age-only | 23,925 | **2.568** | [2.452, 2.681] |
| Age + lactate | **7,452** | **2.272** | [2.104, 2.479] |

The n=7,452 lactate-complete subset is 31.1% of the age-only cohort (7,452/23,925). The attenuation from 2.568 → 2.272 (11.5% reduction) is interpreted as lactate *adjusting away* some of the OR — i.e., that the requirement's mortality signal attenuates when controlling for lactate severity.

**The inferential problem.**  
The age-only OR of 2.568 is computed on n=23,925. The age+lactate OR of 2.272 is computed on the **different and smaller** n=7,452 subset. These two numbers are not comparable: we do not know the age-only OR in the n=7,452 subset. If the lactate-complete patients are sicker (they are — lactate is ordered in suspected shock), their age-only OR within n=7,452 could be lower than 2.568 (e.g., 2.1–2.3) because the high-severity stratum is already more compressed. Under this scenario, the transition 2.57 → 2.27 reflects **selection, not adjustment**.

`ROUND3_COMPLETENESS.md` Section A0 correctly handles this for the **full-cohort SOFA model**: it reports the age-adjusted OR in the lab-complete (n=3,111) vs lab-incomplete (n=12,838) MIMIC mortality subsets and shows the OR is 3.80 in both, proving selection does not confound the adjustment effect. **This exact check is NOT performed for the landmark.** The landmark `model()` function does not compute the age-only OR on the n=7,452 subset.

The published FINDING4_LANDMARK.md presents the 2.57→2.27 transition as evidence that lactate "does not eliminate" the OR (correct), but the framing implies that 2.27 is the *lactate-adjusted* estimate corresponding to the 2.57 *unadjusted* baseline. This is only valid if the age-only OR in the n=7,452 is itself ≈2.57. That has not been checked.

**Resolution.**  
Add four lines to `model()` in `finding4_landmark.py`: compute `_adj_or_per_sd(ll, yy, [aa])` (age-only, no lactate) on the n=7,452 lactate-complete subset and report it alongside the full OR. The reported table should be:

| Model | n | OR/SD | CI |
|---|---|---|---|
| Age-only (full landmark cohort) | 23,925 | 2.57 | [2.45, 2.68] |
| Age-only (lactate-complete subset) | 7,452 | ? | — |
| Age + lactate (lactate-complete subset) | 7,452 | 2.27 | [2.10, 2.48] |

If the middle row is, say, 2.3–2.5, the lactate attenuation is real and ≈5–15%. If it is 2.1–2.2, the 2.57→2.27 narrative is largely a selection artifact. **Until this is computed, the attenuation argument for the landmark is unverified.**

---

## S3 — MODERATE — PARTIALLY DISCLOSED
### Landmark bootstrap resamples stays, not subjects — CI precision overstated

**The issue.**  
`finding4_landmark.py`, function `_adj_or_per_sd`, line 198: *"bootstrap CI (subject-agnostic stay-level; matches headline method)"* — the code explicitly acknowledges the stay-level resample. For n=23,925 stays from an estimated ~20,322 unique subjects (ratio 1.177), the design effect from subject clustering is:

DEFF = 1 + (m-1)×ICC, where m=1.177, ICC ≈ 0.3–0.5 (mortality of same subject correlated across stays)

This gives DEFF ≈ 1.05–1.09, shrinking the effective N to ≈21,980–22,719. The bootstrap 95% CI [2.452, 2.681] is approximately **√DEFF = 1.03–1.04× too narrow**.

**What has been probed.**  
`STATS_CODE_AUDIT.md` item 4 probed the **mortality model** in `mimic_external_validation.py` and found patient-clustered CI [3.45,4.19] vs reported [3.44,4.17] — difference is negligible. The landmark analysis uses the same methodology ("matches headline method") but is not separately probed. Given the modest DEFF (1.05–1.09) the conclusion is unlikely to be overturned. However, the CI [2.10, 2.48] for the n=7,452 lactate subset is narrower and more sensitive to clustering.

**Resolution.**  
Run a subject-clustered bootstrap for the landmark (group stays by subject_id from the icustays→subject mapping; resample subjects, include all their stays). Expected CI widening: 3–4%. If confirmed negligible, add a one-line note in the methods. This is standard for cluster-correlated ICU data. Already labeled MINOR in the prior audit for the headline mortality model; the same label applies here given the expected effect size.

---

## S4 — MODERATE — PARTIALLY DISCLOSED
### SOFA approximation "slightly" understates the attenuation risk from missing GCS and respiratory SOFA components

**The issue.**  
`HOSTILE_REVIEW_FINAL.md` disclosure #6: *"a complete SOFA could attenuate slightly more, but the subsample-convergence bounds the risk."* The word "slightly" requires scrutiny.

**What is missing from the SOFA.**  
The neurological (GCS-derived, 0–4 points) and respiratory (PaO2/FiO2-derived, 0–4 points) SOFA components are absent, together comprising 0–8 of the full 0–24 SOFA range. In a **vasopressor-requiring ICU population** (the analysis cohort):
- Most patients who require vasopressors for septic shock are mechanically ventilated (respiratory SOFA component likely 2–4 for the majority).
- Mechanically ventilated patients under sedation have suppressed GCS (neurological SOFA component typically 2–4 under propofol/midazolam).
- Therefore the **expected value of missing SOFA points** is not near 0; it is likely 4–6 points for the median vasopressor patient.

**Quantitative consequence.**  
The observed attenuation from adding 3 SOFA labs + lactate is: OR 3.89 → 2.53 (35% reduction, n=3,824 complete-case). This is on a mortality base rate of 0.368 (the complete-case is already a sicker stratum). Adding 2 additional high-valued SOFA components (each carrying 2–4 points) could plausibly attenuate by another 15–25%, yielding a projected OR of approximately 1.9–2.1 and a CI lower bound in the range [1.2, 3.0]. The claim that the CI lower bound 1.90 (current estimate from the 3-lab+lactate model) is "bounded away from 1" by the full SOFA becomes less secure: if full SOFA attenuates the point estimate toward OR=1.9 and widens the CI to [1.0, 3.5], the null cannot be rejected.

**What is disclosed vs new.**  
The SOFA approximation limitation is DISCLOSED throughout (`HOSTILE_REVIEW_FINAL.md`, `PUBLICATION_DOSSIER.md`, `MIMIC_SOFA_LACTATE.md`). The NEW contribution here is a **quantitative argument** that in the specific population studied (vasopressor-requiring ICU, with universal near-intubation and sedation), the missing components are not small perturbations: they are likely 4–6 points of systematic unmeasured severity, and the resulting additional attenuation could push the CI lower bound within or near 1. The claim that the evidence "bounds the risk" is weaker than currently stated.

**Resolution.**  
One of: (a) Download chartevents (30 GB), extract GCS and SpO2/PaO2, compute full SOFA, re-run the OR. This is the definitive test. (b) Report a sensitivity: if two missing components each contribute 3 points of SOFA, what OR attenuation would be expected proportionally? State this as a quantitative bound on the residual, not a narrative "slightly." The current language gives false comfort.

---

## S5 — MODERATE — ALREADY-DISCLOSED (framing debt)
### Multiplicity across the unified claim

Four findings, three external cohorts (VitalDB, MIMIC, INSPIRE), multiple outcome specifications (reliability, early→late, mortality quartiles, OR/SD, landmark), and multiple adjustment models. The primary statistics on the reliability are multiplicity-immune by Fisher z-transform (z~84/210 for n=13,585 at r=0.95), as documented in `ROUND3_COMPLETENESS.md` A5. The mortality ORs do not have this protection. The MIMIC secondary surface (13 subgroups, 5 severity specs) is not in any formal correction.

`REDTEAM_PUBLICATION_VERDICT.md` says: *"Declare ONE pre-specified primary (Finding 1) + label 2–4 exploratory; the MIMIC secondary surface is not in the original ~30-test Bonferroni."* This is ALREADY DISCLOSED as a required revision. No new analysis needed; the fix is editorial. Labeled here for completeness as a required pre-submission action: a single pre-specified primary must be declared with a multiplicity-corrected CI for that analysis only.

---

## S6 — MODERATE — NEW
### Temporal window mismatch: lactate adjuster uses hospital admittime; NEE exposure uses ICU intime

**The specific hole.**  
`mimic_sofa_lactate.py` builds `LABS_CSV` (`cache/mimic_labs24h.csv`) using `admittime` (hospital admission time) as the anchor for the 24-hour lab window (line 88: `if t < admit[h] or t > admit[h] + 86400`).

`finding4_landmark.py` constructs the first-24h NEE exposure using `intime` (ICU admission time) as anchor (lines 103–104: `hrs = (t0 - link["intime"]).total_seconds() / 3600.0`; `if hrs < 0 or hrs > LANDMARK_H`).

In MIMIC-IV, `admittime` (hospital admission) is often earlier than `intime` (ICU admission) — sometimes by days (hospital wards, step-down units, post-operative recovery). For ward-to-ICU transfers, the lactate used to adjust the landmark OR may be:
- A **pre-ICU ward lactate** (not reflecting ICU admission severity) if measured in the first 24h of hospitalization.
- **Missing entirely** from the ICU period if the lab window (admittime+24h) closed before the ICU stay began.

**Consequences for the landmark OR 2.27.**  
The lactate adjuster in the landmark regression is indexed to a window that does not necessarily overlap with the exposure window (ICU intime + 24h). For delayed-to-ICU patients:
- The lactate may reflect a milder pre-ICU state → **underadjustment** → OR 2.27 is inflated relative to what full-severity adjustment would give.
- Alternatively, if the ward lactate is elevated (deteriorating patient), it may over-adjust relative to ICU-specific severity.

The direction is ambiguous but the **mismatch itself is undisclosed** and affects the interpretation of "adjusted for lactate" in the landmark context. Unlike `ROUND3_COMPLETENESS.md` A0 (which demonstrates selection-invariance for the SOFA model), this is a structural coding inconsistency between two distinct time anchors.

**Resolution.**  
In `finding4_landmark.py`, the `_load_lactate()` function reads from `LABS_CSV` keyed by `hadm_id`. Re-build `LABS_CSV` (or a landmark-specific variant) using `intime` + 24h from `icustays.csv.gz` rather than `admittime` + 24h from `admissions.csv.gz`. Rerun and compare the age+lactate OR. If it changes materially, the mismatch is quantitatively important. If it is stable (expected for predominantly ED-to-ICU direct admissions), document the sensitivity. In any case, the mismatch must be noted in the Methods: "lactate was extracted from the first 24 hours of **hospital** admission (not ICU admission)."

---

## S7 — MINOR — ALREADY-DISCLOSED
### Split-half reliability: Spearman of epoch medians, not ICC(2,1)

The VitalDB reliability (`_icc_splithalf` in `pressor_requirement.py`) and MIMIC reliability (`_spear_ci` on rel_odd / rel_even in `mimic_external_validation.py`) both use **Spearman correlation of half-medians**, not a formal ICC. Spearman captures rank consistency but does not account for systematic level differences between halves (e.g., dose escalation during a stay makes later epochs systematically higher than earlier, causing the ODD half median to diverge from the EVEN half median even in a reliable patient). ICC(2,1) (two-way mixed effects, consistency) is the psychometric standard for split-half reliability and corrects for this. The MIMIC `autocorrelation_attack.json` separately reports ICC(1)=0.392 (a different estimand: between-stay vs within-stay), not the ICC of the split-half. The Spearman r=0.947 likely overstates reliability by not accounting for within-stay dose trends. This is acknowledged as a "Spearman" measure throughout but the specific biasing direction from within-stay escalation is not stated. Fix: compute ICC(2,1) for the split-half, noting that Spearman was used as a rank-robust alternative and report both.

---

## S8 — ALREADY-DISCLOSED, SOUND
### Autocorrelation / autocorrelated infusion rebuttal

Time-gapped early→late at ≥12h gap: r=0.422 (`autocorrelation_attack.json`); shuffle-null: r≈−0.012; within-stay CV median=0.51 (rate genuinely moves). These tests are correctly designed and defeat the autocorrelation concern. The rebuttal is methodologically sound. No new issue.

---

## Cross-cutting notes

### log1p(NEE) transform in landmark
`logload = [float(np.log1p(v)) for v in nee_load]`. When NEE load >> 1 (cumulative dose in mcg/kg units, which is typically 10–500+ for a 24h period), `log1p(NEE) ≈ log(NEE)`. The +1 shift matters only for near-zero loads (very brief infusions). The per-SD OR is a function of the SD of `log1p(NEE)` across the 23,925 stays; as long as the distribution is reasonably symmetric after transformation, the logistic model assumption is approximately met. This is a standard and appropriate transform for cumulative dose data. **NOT a methodological hole.**

### IRB / pre-registration
No pre-registration. The sequential adaptive search is disclosed in `FINDINGS_LEDGER.md`. The primary Finding 1 reliability claim is multiplicity-immune (z=84–210); the prospective landmark was generated as a make-or-break response to a reviewer attack (post-hoc). The paper should state clearly that all analyses are exploratory except a single pre-specified primary.

---

## Priority ranking (top 3 for the editor)

**S1 (CRITICAL, NEW):** The MIMIC reliability 0.947 has not been verified to be independent of multi-stay subject clustering. Approximately 3,500 of 13,585 stay-rows (25.8%) come from subjects appearing 2+ times, each adding a correlated concordant pair. This is the single most important statistical correction before publication: a first-stay-per-subject restricted analysis or subject-level ICC must be reported. If the reliability drops from 0.947 to, say, 0.85, the headline "MIMIC ICU reliability 0.95" in the central claim must be corrected.

**S2 (CRITICAL, NEW):** The landmark OR 2.27 [2.10,2.48] is not a properly controlled severity-adjusted estimate because the age-only OR in the n=7,452 lactate-complete subset has not been computed. Without it, the 2.57→2.27 attenuation cannot be attributed to lactate adjustment vs sample selection. The fix is four lines of code in `finding4_landmark.py`. Until completed, the prospective claim rests on an incomplete comparison.

**S6 (MODERATE, NEW):** The lactate adjuster in the landmark is built from hospital admittime +24h, while the NEE exposure is from ICU intime +24h. This undisclosed window mismatch means "adjusted for lactate" in the landmark methods section is misleading if interpreted as first-24h-of-ICU lactate. Requires either a code fix or an explicit methods disclosure.

---

## Overall statistical-soundness verdict

**The headline prospective claim (OR 2.27) and the reliability claim (0.95) each have at least one unverified statistical assumption that could meaningfully shift the reported number.**

- The 0.95 MIMIC reliability is likely inflated by multi-stay subject clustering (S1); the magnitude is unknown but plausibly 0.03–0.05 units.
- The OR 2.27 attenuation narrative is incomplete without the age-only OR in the n=7,452 subset (S2); the finding may be sound but cannot be verified as stated.
- A temporal window mismatch in the lactate covariate is undisclosed (S6).
- None of these issues necessarily flips the qualitative conclusion (the OR and reliability are large enough to survive modest downward correction), but all three would be flagged by a careful statistical reviewer and require either a code fix or an explicit quantitative disclosure before publication.

The prior adversarial rounds correctly identified the major structural concerns (confounding by indication, SOFA approximation, selection, multiplicity framing). The three issues above are **new statistical-methodology holes** that were not probed in the prior rounds and that are resolvable with targeted code additions of modest effort.

_Cross-ref: STATS_CODE_AUDIT.md (items 4–5), ROUND3_COMPLETENESS.md (A0, A3), IMMORTAL_TIME_AUDIT.md, HOSTILE_REVIEW_FINAL.md (limitation 6), REDTEAM_PUBLICATION_VERDICT.md (cross-cutting)._
