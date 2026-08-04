# One clean Hb instrument across the transfusion-RCT landscape — partial sign-recovery, power-limited

Tests whether the clean cross-method Hb instrument recovers the DIFFERENT known truths of the transfusion RCTs
by selecting each trial's population (ICD/service) and reading the transfusion LATE sign. RCT truths:
general ICU neutral (TRICC); cardiac surgery contested (TITRe2 mortality-harm signal vs TRICS-III non-inferior);
acute MI liberal-trend (MINT) / non-inferior (REALITY); hip fracture null (FOCUS); upper GI bleed
restrictive-superior = transfusion harmful (Villanueva).

## Result — individual trial builds, each with its EXACT primary-outcome horizon
(band CBC Hb 6–8, bloodgas-Hb<7 flag, D=RBC≤24h; LATE = transfusion effect on that trial's outcome)
| trial (population, exact horizon) | n | F | flag-ITT [95% CI] | LATE | bal | NC | vs RCT truth |
|---|---|---|---|---|---|---|---|
| **TRICC** (general ICU, 30d) | 4,412 | 13 | −0.012 [−0.039, +0.015] | −0.16 | +0.91 | ok | ✅ null recovered |
| **TITRe2** (cardiac surgery, 90d) | 2,881 | 12 | +0.020 [−0.007, +0.047] | +0.23 | +1.46 | ok | ~ n.s.; consistent with TRICS-III NI, not TITRe2's borderline harm |
| **MINT** (acute MI, 30d) | 766 | 10 | −0.029 [−0.088, +0.029] | −0.18 | +1.59 | ok | ~ correct sign (liberal-trend), n.s. |
| **REALITY** (acute MI, 30d MACE) | 766 | 10 | −0.029 [−0.088, +0.029] | −0.18 | +1.59 | ok | ~ consistent with restrictive-non-inferior (CI incl 0) |
| **FOCUS** (hip fracture, 60d) | **23** | — | — | — | — | — | ✗ untestable — no arterial blood-gas Hb in elective ortho |
| **Villanueva** (upper GI bleed, 45d) | 336 | **0** | +0.071 [−0.087, +0.229] | +2.17 | **+4.05** | ok | ✗ instrument invalid (drift in bleeders); point sign correct (harmful) |

Note MINT and REALITY share the same MIMIC cohort (acute MI + arterial blood-gas Hb) and same 30-day horizon, so
they return the same estimate — it is consistent with both trials' (compatible) conclusions.

## Reading (honest)
- **Only the general-ICU null is a clean favorable** (well-powered, NC ok, balance ok) — the TRICC anchor.
- **MI shows the correct protective sign** (LATE −0.18, matching MINT's liberal-favoring direction) but the CI
  includes 0 (n=766) — a suggestive, not confirmatory, directional match.
- **Cardiac surgery is n.s.** and its point sign (+0.23) contradicts TITRe2's borderline mortality-harm signal
  while being consistent with the much larger TRICS-III (restrictive non-inferior). The RCT "truth" here is itself
  contested, so this is not a clean test either way.
- **GI bleed and hip fracture are not testable** with this instrument: bleeders violate the cross-method analytic
  assumption (drift; F=0, balance +4 yr — predicted), and elective hip-fracture patients have no arterial
  blood-gas Hb at all (n=23).

## The structural limit (why this path does not reach 10 favorables)
The cross-method Hb instrument **requires a same-time arterial blood-gas Hb**, which exists almost only in
ICU/critically-ill patients. So the transfusion RCTs run in **non-ICU or elective** populations (FOCUS ortho,
much of MINT/REALITY, Villanueva ward GI-bleed) are either absent or badly underpowered, and the bleeding
populations violate the instrument's core assumption. The landscape looked like ~5 extra validations; in
practice it yields **one robust favorable (ICU) + one directional match (MI)**. Data-getting did not rescue it:
chemistry lactate (53154) is essentially absent in MIMIC (0 rows), so there is no lactate cross-method pair to
open a new clean analyte either.

## Ledger impact
+1 robust (already counted as TRICC) and +1 weak directional (MI). Net new favorables ≈ 1 weak. The honest
conclusion: reaching ≥10 favorables needs either (a) external ICU datasets (HiRID/SICdb/AmsterdamUMCdb) to
power the subpopulations and add sites, or (b) a different instrument family (dose-intensity IV — now enabled by
the newly-streamed vasopressor + ventilation data), not more slicing of a single ICU-restricted Hb instrument.
