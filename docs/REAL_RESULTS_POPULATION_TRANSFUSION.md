# One clean Hb instrument across the transfusion-RCT landscape — partial sign-recovery, power-limited

Tests whether the clean cross-method Hb instrument recovers the DIFFERENT known truths of the transfusion RCTs
by selecting each trial's population (ICD/service) and reading the transfusion LATE sign. RCT truths:
general ICU neutral (TRICC); cardiac surgery contested (TITRe2 mortality-harm signal vs TRICS-III non-inferior);
acute MI liberal-trend (MINT) / non-inferior (REALITY); hip fracture null (FOCUS); upper GI bleed
restrictive-superior = transfusion harmful (Villanueva).

## Result (band CBC Hb 6–8, bloodgas-Hb<7 flag, D=RBC≤24h)
| population | n | first-stage F | flag-ITT [95% CI] | LATE | balance | NC | vs RCT truth |
|---|---|---|---|---|---|---|---|
| general ICU (TRICC) | 4,412 | 13 | −0.012 [−0.039, +0.015] | −0.16 | +0.91 | ok | ✅ neutral recovered |
| acute MI (MINT/REALITY) | 766 | 10 | −0.029 [−0.088, +0.029] | −0.18 | +1.59 | ok | ~ correct sign (liberal-trend), n.s. |
| cardiac surgery (TITRe2/TRICS) | 2,881 | 12 | +0.020 [−0.007, +0.047] | +0.23 | +1.46 | ok | ~ n.s.; matches TRICS-III NI, not TITRe2 harm |
| upper GI bleed (Villanueva) | 336 | **0** | +0.073 [−0.074, +0.221] | +2.24 | **+4.05** | ok | ✗ instrument invalid (drift in bleeders) |
| hip fracture (FOCUS) | **23** | — | — | — | — | — | ✗ no arterial blood-gas Hb in elective ortho |

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
