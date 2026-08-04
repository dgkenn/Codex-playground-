# REDTEAM_VERIFY_FINDING2 — Numerical Integrity Audit

**Audit scope:** FINDING 2 claims in PUBLICATION_DOSSIER.md and REQUIREMENT_AKI_CROSSVAL.md  
**Task:** Verify all numbers exist in code/cache and are internally consistent.  
**Sources audited:**
- `analysis/requirement_aki_crossval.py` (code logic)
- `cache/requirement_aki_crossval.json` (computed outputs)
- `docs/PUBLICATION_DOSSIER.md` (summary claims)
- `docs/REQUIREMENT_AKI_CROSSVAL.md` (detailed results)

---

## Claim Verification Table

| # | Claim | Claimed Value | Source File | Cache/Code Location | Actual Value | Status |
|---|-------|---------------|-------------|---------------------|--------------|--------|
| 1 | MIMIC n (norepi stays) | 6,421 | PUBLICATION_DOSSIER.md:38 | `requirement_aki_crossval.json` > `mimic_discovery.n_linked_stays` | 6421 | **FOUND** |
| 2 | MIMIC ESRD excluded | 883 | REQUIREMENT_AKI_CROSSVAL.md:8 | `requirement_aki_crossval.json` > `mimic_discovery.n_esrd_excluded` | 883 | **FOUND** |
| 3 | MIMIC AKI rate | 0.482 (48.2%) | REQUIREMENT_AKI_CROSSVAL.md:8 | `requirement_aki_crossval.json` > `mimic_discovery.aki_rate` | 0.482 | **FOUND** |
| 4 | Age-adjusted OR per SD | 1.38/SD | PUBLICATION_DOSSIER.md:38 | `requirement_aki_crossval.json` > `mimic_discovery.age_adjusted_OR_per_SD.or` | 1.377 | **FOUND** (rounds to 1.38) |
| 5 | Age-adjusted OR CI | [1.248, 1.504] | REQUIREMENT_AKI_CROSSVAL.md:9 | `requirement_aki_crossval.json` > `mimic_discovery.age_adjusted_OR_per_SD.ci` | [1.248, 1.504] | **FOUND** |
| 6 | Dose-response Q1 AKI rate | 38% | PUBLICATION_DOSSIER.md:38 | `requirement_aki_crossval.json` > `mimic_discovery.dose_response_quartiles[0].aki_rate` | 0.384 (38.4%) | **FOUND** |
| 7 | Dose-response Q4 AKI rate | 61% | PUBLICATION_DOSSIER.md:38 | `requirement_aki_crossval.json` > `mimic_discovery.dose_response_quartiles[3].aki_rate` | 0.607 (60.7%) | **FOUND** |
| 8 | Q4-Q1 gradient | 0.223 | REQUIREMENT_AKI_CROSSVAL.md:10 | `requirement_aki_crossval.json` > `mimic_discovery.dose_response_q4_minus_q1` | 0.223 | **FOUND** |
| 9 | Monotone dose-response | Yes | REQUIREMENT_AKI_CROSSVAL.md:10 | `requirement_aki_crossval.json` > `mimic_discovery.dose_response_monotone` | true | **FOUND** |
| 10 | Within-severity OR per SD | 1.20 | PUBLICATION_DOSSIER.md:38-39 | `requirement_aki_crossval.json` > `mimic_discovery.within_severity_adjusted_OR_per_SD.or` | 1.198 | **FOUND** (rounds to 1.20) |
| 11 | Within-severity OR CI | [1.069, 1.362] | REQUIREMENT_AKI_CROSSVAL.md:15 | `requirement_aki_crossval.json` > `mimic_discovery.within_severity_adjusted_OR_per_SD.ci` | [1.069, 1.362] | **FOUND** |
| 12 | Lactate T1 OR | 1.273 [1.099, 1.501] | REQUIREMENT_AKI_CROSSVAL.md:17 | `requirement_aki_crossval.json` > `mimic_discovery.within_lactate_tertile_OR[0]` | 1.273 [1.099, 1.501] | **FOUND** |
| 13 | Lactate T2 OR | 1.165 [1.005, 1.546] | REQUIREMENT_AKI_CROSSVAL.md:18 | `requirement_aki_crossval.json` > `mimic_discovery.within_lactate_tertile_OR[1]` | 1.165 [1.005, 1.546] | **FOUND** |
| 14 | Lactate T3 OR | 1.136 [1.031, 1.304] | REQUIREMENT_AKI_CROSSVAL.md:19 | `requirement_aki_crossval.json` > `mimic_discovery.within_lactate_tertile_OR[2]` | 1.136 [1.031, 1.304] | **FOUND** |
| 15 | 3/3 lactate strata OR>1 | Yes | PUBLICATION_DOSSIER.md:39 | All three tertile CIs exclude 1.0 | T1/T2/T3 all CI > 1 | **FOUND** |
| 16 | INSPIRE calibrated OR | 0.98 | PUBLICATION_DOSSIER.md:40 | `requirement_aki_crossval.json` > `inspire_validation.intraop_norepi.renal_calibrated_OR` | 0.984 | **FOUND** (rounds to 0.98) |
| 17 | INSPIRE z-score | −0.42 | PUBLICATION_DOSSIER.md:40 | `requirement_aki_crossval.json` > `inspire_validation.intraop_norepi.renal_z_vs_null` | -0.42 | **FOUND** |
| 18 | INSPIRE calibrated logOR | −0.016 | REQUIREMENT_AKI_CROSSVAL.md:31 | `requirement_aki_crossval.json` > `inspire_validation.intraop_norepi.renal_calibrated_logor` | -0.016 | **FOUND** |
| 19 | INSPIRE null mean logOR | 0.0633 | REQUIREMENT_AKI_CROSSVAL.md:31 | `requirement_aki_crossval.json` > `inspire_validation.intraop_norepi.null_mean_logor` | 0.0633 | **FOUND** |
| 20 | INSPIRE null sd logOR | 0.0385 | REQUIREMENT_AKI_CROSSVAL.md:31 | `requirement_aki_crossval.json` > `inspire_validation.intraop_norepi.null_sd_logor` | 0.0385 | **FOUND** |
| 21 | INSPIRE survives calibration | No (dies) | PUBLICATION_DOSSIER.md:40 | `requirement_aki_crossval.json` > `inspire_validation.intraop_norepi.survives` | false | **FOUND** |
| 22 | VitalDB n (NEPI-requirement cases) | 219 | PUBLICATION_DOSSIER.md:41 | `requirement_aki_crossval.json` > `vitaldb_validation.n_nepi_requirement_cases` | 219 | **FOUND** |
| 23 | VitalDB renal events | 17 | PUBLICATION_DOSSIER.md:41 | `requirement_aki_crossval.json` > `vitaldb_validation.requirement_vs_renal.renal_events` | 17 | **FOUND** |
| 24 | VitalDB Mann-Whitney p | 0.2574 | REQUIREMENT_AKI_CROSSVAL.md:43 | `requirement_aki_crossval.json` > `vitaldb_validation.requirement_vs_renal.mannwhitney_p` | 0.2574 | **FOUND** |
| 25 | VitalDB status | Underpowered | PUBLICATION_DOSSIER.md:41 | `requirement_aki_crossval.json` > `vitaldb_validation.verdict` | "Underpowered -- directional only." | **FOUND** |

---

## Internal Consistency Checks

| Check | Test | Result | Status |
|-------|------|--------|--------|
| Monotone gradient | AKI rates Q1→Q4: 0.384 < 0.435 < 0.500 < 0.607 | True | **CONSISTENT** |
| Lactate tertile consistency | All 3 tertiles: OR CI excludes 1.0 | T1 [1.099, 1.501], T2 [1.005, 1.546], T3 [1.031, 1.304] | **CONSISTENT** |
| INSPIRE calibration logic | Calibrated logOR = raw logOR − null mean (0.0473 − 0.0633 = −0.016) | -0.016 ✓ | **CONSISTENT** |
| INSPIRE z-calculation | z = (raw logOR − null mean) / null sd = (0.0473 − 0.0633) / 0.0385 = −0.416 ≈ −0.42 | -0.42 ✓ | **CONSISTENT** |
| INSPIRE "dies" logic | z-score |−0.42| < 1.96 → survives=false | survives=false ✓ | **CONSISTENT** |
| VitalDB power assessment | n=219 with only 17 events (7.8%) → low power for effect detection | Verdict: "Underpowered" | **CONSISTENT** |

---

## Cross-Document Consistency

| Comparison | PUBLICATION_DOSSIER.md | REQUIREMENT_AKI_CROSSVAL.md | Cache/Code | Status |
|------------|------------------------|----------------------------|-----------|--------|
| MIMIC n | 6,421 | 6,421 | 6421 | **MATCH** |
| MIMIC ESRD excl | (implied) | 883 | 883 | **MATCH** |
| Age-adj OR | 1.38/SD | 1.377 [1.248, 1.504] | 1.377 | **MATCH** (rounding) |
| Q1 AKI rate | 38% | 0.384 | 0.384 | **MATCH** |
| Q4 AKI rate | 61% | 0.607 | 0.607 | **MATCH** |
| Within-severity OR | 1.20 | 1.198 [1.069, 1.362] | 1.198 | **MATCH** (rounding) |
| Lactate T1-T3 OR>1 | 3/3 OR>1 | [1.273, 1.165, 1.136] | all CIs exclude 1.0 | **MATCH** |
| INSPIRE calib OR | 0.98 | 0.984 | 0.984 | **MATCH** (rounding) |
| INSPIRE z | −0.42 | −0.42 | -0.42 | **MATCH** |
| VitalDB n | 219 | 219 | 219 | **MATCH** |
| VitalDB events | 17 | 17 | 17 | **MATCH** |

---

## Verdict Summary

**All 25 numerical claims verified FOUND in code/cache.**  
**All internal consistency checks: CONSISTENT.**  
**Cross-document consistency: NO CONTRADICTIONS** (only minor rounding: 1.377→1.38, 1.198→1.20, 0.984→0.98).

**Integrity status: PASSED — FINDING 2 numbers are grounded in runnable analysis code, outputs are internally coherent, and documentation is numerically faithful to source computations.**
