# REDTEAM VERIFY FINDING 3 — Data Integrity Audit

**Date:** 2026-06-30  
**Auditor:** Independent Data Integrity Auditor  
**Task:** Verify FINDING 3 claimed numbers against code outputs/cache  

## FINDING 3 Claims (from PUBLICATION_DOSSIER.md + RESUSCITATION_BALANCE_CROSSVAL.md)

1. MIMIC co-exposed (pressor+fluid) n=28k; tertile mortality 0.065→0.153→0.429; age-adj OR 3.5/SD; survives lactate (3.4).
2. VitalDB intraop balance → organ_renal OR 1.18 [0.996,1.394].
3. INSPIRE lacks fluid columns (not testable).

---

## Verification Table: Claim | Source File | Status | Evidence

| # | Claim | Source Files | Status | Found Value(s) | Match? |
|---|-------|--------------|--------|-----------------|--------|
| 1a | MIMIC co-exposed n=28k | `analysis/resuscitation_balance_crossval.py` L439, `cache/resuscitation_balance_crossval.json` | **FOUND** | n_coexposed = 28124 | ✓ YES (28,124 ≈ 28k) |
| 1b | Tertile mortality 0.065→0.153→0.429 | `cache/resuscitation_balance_crossval.json` L76-79 | **FOUND** | [0.0649, 0.1531, 0.4294] | ✓ YES (exact match: 0.0649≈0.065, 0.1531≈0.153, 0.4294≈0.429) |
| 1c | Age-adj OR 3.5/SD | `cache/resuscitation_balance_crossval.json` L54-68 | **FOUND** | adj_or_per_sd = 3.505 | ✓ YES (3.505 ≈ 3.5) |
| 1d | Survives lactate (3.4) | `cache/resuscitation_balance_crossval.json` L103-118 | **FOUND** | balance_coexposed_age_lactate_adj: adj_or_per_sd = 3.398 | ✓ YES (3.398 ≈ 3.4) |
| 2a | VitalDB intraop balance → organ_renal OR 1.18 | `cache/resuscitation_balance_crossval.json` L124-138 | **FOUND** | adj_or_per_sd = 1.183 | ✓ YES (1.183 ≈ 1.18) |
| 2b | CI [0.996, 1.394] | `cache/resuscitation_balance_crossval.json` L129-131 | **FOUND** | ci = [0.996, 1.394] | ✓ YES (exact match) |
| 3 | INSPIRE lacks fluid columns (not testable) | `cache/resuscitation_balance_crossval.json` L156-158 + `analysis/resuscitation_balance_crossval.py` L707-709 | **FOUND** | A_balance_inspire: "note": "INSPIRE matrix has NO intra-op fluid volume columns (only 'ebl')..." | ✓ YES |

---

## Internal Consistency Checks

### Cross-check 1: MIMIC co-exposed tertile mortalities vs rounded doc claims
- **Doc claim (PUBLICATION_DOSSIER.md):** tertile mortality 0.065→0.153→0.429
- **Cache actual (tertiles_coexposed):** [0.0649, 0.1531, 0.4294]
- **Rounding consistency:** Claimed values are exact 3-4 SF decimal truncations/roundings of cached values
- **Status:** ✓ CONSISTENT (no contradiction)

### Cross-check 2: Age-adj OR claims across lactate subgroups
- **Full balance_coexposed_age_adj (n=28124):** OR = 3.505, CI [3.345, 3.689]
- **Lactate-adjusted co-exposed (n=8623):** OR = 3.398, CI [3.142, 3.698]
- **Doc summary:** "age-adj OR 3.5/SD; survives lactate (3.4)"
- **Interpretation:** Claims report ORs to 1 decimal place (3.5, 3.4); actual values are 3.505 and 3.398
- **Status:** ✓ CONSISTENT (lactate adjustment attenuates minimally, supports "survives" language)

### Cross-check 3: VitalDB balance outcome and direction
- **Cache outcome:** organ_renal (post-op AKI), n=3924, AKI events=143
- **OR = 1.183 > 1.0:** direction is pressor-predominant → MORE AKI (concordant with MIMIC direction)
- **CI [0.996, 1.394]:** lower bound 0.996 < 1.0, upper bound > 1.0 (borderline, as described)
- **Doc verdict:** "concordant, borderline"
- **Status:** ✓ CONSISTENT (agrees with stated borderline conclusion)

### Cross-check 4: INSPIRE FINDINGS 3 vs FINDING 4
- **FINDING 3 (fluid-vs-pressor balance):** INSPIRE lacks intra-op fluid volume → NOT TESTABLE
- **FINDING 4 (NEE load):** INSPIRE has intraop_norepi + intraop_epi → TESTED (OR 1.106/SD)
- **Code logic:** Line 707-709 explicitly notes balance cannot be replicated; FINDING 4 cross-validation separate (B_nee_inspire)
- **Status:** ✓ CONSISTENT (no contradiction, correct scope boundaries)

### Cross-check 5: Numerical continuity within MIMIC balance analyses
- **Full cohort (n=76374):** age-adj OR 2.144/SD [2.095, 2.201]; tertile mortality [0.0702, 0.0663, 0.2357] (non-monotone)
- **Co-exposed subset (n=28124):** age-adj OR 3.505/SD [3.345, 3.689]; tertile mortality [0.0649, 0.1531, 0.4294] (monotone)
- **Explanation in code:** Lowest tertile of raw balance dominated by no-pressor stays (frac_no_pressor_in_lowest_tertile=1.0), so co-exposed filter removes confound
- **Status:** ✓ CONSISTENT (correctly documented, no numerical error)

### Cross-check 6: FINDING 3 vs FINDING 4 outcome endpoints
- **FINDING 3 (this report):** MIMIC → in-hospital mortality; VitalDB → post-op AKI (organ_renal)
- **FINDING 4 (separate):** MIMIC → in-hospital mortality; INSPIRE → death_inhosp (intra-op)
- **Different endpoints acknowledged:** docs/RESUSCITATION_BALANCE_CROSSVAL.md L57-58 states "concordant direction across endpoints is the cross-validation signal"
- **Status:** ✓ CONSISTENT (endpoints appropriately acknowledged)

---

## Summary of Verification

### All Claims Located: 7/7 (100%)
- ✓ MIMIC co-exposed n=28,124 (claimed ~28k)
- ✓ Tertile mortalities [0.0649, 0.1531, 0.4294] (claimed [0.065, 0.153, 0.429])
- ✓ Age-adj OR 3.505/SD (claimed 3.5/SD)
- ✓ Lactate-adjusted co-exposed OR 3.398/SD (claimed 3.4/SD)
- ✓ VitalDB balance→organ_renal OR 1.183 [0.996, 1.394] (exact match)
- ✓ INSPIRE fluid-volume absence documented and explicit

### All Numbers Match or Are Internally Consistent: 7/7 (100%)
- No mismatches; claimed rounding/truncations align with cached precision
- Lactate adjustment attenuation (3.505→3.398) matches "survives" language
- Direction and CI overlap consistent with stated borderline status for VitalDB

### Internal Contradictions: NONE DETECTED
- Subgroup relationships (full vs co-exposed) correctly explained in code & docs
- Endpoint choices appropriately scoped and documented
- INSPIRE data limitation correctly stated and applied only to FINDING 3, not FINDING 4

### Data Provenance Trail: COMPLETE
- Claimed numbers traceable to:
  - `analysis/resuscitation_balance_crossval.py` (code logic, lines 439, 514, 597-608)
  - `cache/resuscitation_balance_crossval.json` (computed outputs, verified via model() function)
  - `docs/RESUSCITATION_BALANCE_CROSSVAL.md` (auto-generated from JSON via _doc() function, line 796)
  - `docs/PUBLICATION_DOSSIER.md` (manual summary, all claims backed by above sources)

---

## Conclusion

**Integrity Status: PASS — Numbers verified and internally consistent.**

All FINDING 3 claimed numbers are present in code-generated cache/outputs with no numerical discrepancies. Rounding and truncation are consistent across documentation layers. Scope statements (INSPIRE limitation, endpoint differences) are accurate and properly applied. No data fabrication, calculation errors, or silent scope changes detected.

**Count Summary:**
- 7 specific numeric claims: 7 FOUND
- 7 specific numeric claims: 7 MATCH (no mismatches, no NOT FOUND)
- 0 internal contradictions
- 0 suspicious gaps or scope creep
