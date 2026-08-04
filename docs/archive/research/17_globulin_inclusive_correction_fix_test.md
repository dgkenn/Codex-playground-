# Testing the proposed globulin-inclusive corrected-calcium fix (MIMIC-IV): does NOT validate at achievable N

**Status:** Honest NEGATIVE / power-limited. The manuscript proposed a globulin-inclusive correction as an
alternative fix. We built and tested it against ionized-calcium ground truth. It does not validate as a
reclassification remedy in the achievable paired data → manuscript recommendation tempered to "measure ionized
directly." Integrity win (self-tested our own proposed fix before a reviewer would).

## Design
Quadruple-paired (within 2h, per patient) ionized Ca (50808, mmol/L truth), total Ca (50893, mg/dL), albumin
(50862, g/dL), total protein (50976, g/dL). globulin = total protein − albumin. Race from admissions.
Full MIMIC-IV labevents stream-filtered (4.59M rows for the 4 itemids).

Two tests, honoring the PIC lesson (check the correction actually improves ionized-tracking BEFORE claiming a fix):
1. **Pre-check:** does a globulin term improve prediction of ionized over Payne-0.8? (ion ~ payne + globulin).
2. **Racial fix:** does the globulin-corrected value shrink the Black-vs-White false-hypercalcemia gap?

## Result — the fix does NOT validate (and the pilot signal was small-sample noise)
| | N=327 (truncated pilot) | **N=693 (full labevents)** |
|---|---|---|
| quadruple-paired N | 327 | **693** |
| globulin coef z (ion prediction) | −2.63 (sig) | **−1.53 (NS)** |
| ionized-tracking gain (residual SD ↓) | 1.0% | **0.2%** |
| derived globulin term c (mg/dL per g/dL) | +0.180 | **+0.073** |
| false-hyperCa Black/White ratio, Payne | 3.64 | 1.62 |
| false-hyperCa ratio, globulin-corrected | 2.27 | **1.62 (unchanged)** |

At proper N the globulin term is not a significant predictor of ionized calcium beyond Payne (z=−1.53), improves
ionized-tracking by 0.2%, and — with a derived term of only 0.073 mg/dL per g/dL globulin — moves no one across
the 10.5 mg/dL decision threshold, leaving the racial gap literally unchanged (1.62 → 1.62). The N=327 pilot
(z=−2.63, gap 3.64→2.27, Black 4→3 events) was underpowered noise.

## Why (not a mechanism refutation)
The mechanism (total Ca tracks globulin) is confirmed at LARGE N in the manuscript because total Ca + total
protein are both chemistry-panel orders, co-drawn in thousands. But the FIX additionally needs **ionized calcium
(a blood gas) co-timed** → the quadruple co-occurrence collapses to N=693 even in the full extraction. This is a
co-measurement/power limitation (same class as our logged "itemid existence ≠ co-occurrence" lesson), not a
refutation. But its practical consequence stands: a globulin-inclusive correction cannot be derived/validated as
a reclassification remedy from routinely-collected paired data.

## Manuscript impact (applied)
- Discussion §4 and Abstract conclusion tempered: **direct ionized-calcium measurement** is the supported,
  deployable remedy; the globulin-inclusive correction is mechanistically motivated but unvalidated as a fix and
  would need prospective co-measurement. This removes an over-promise a reviewer would have caught.
- The flagship's core claims (bias, mechanism, misclassification, workup consequence) are unaffected.

## Files
- `scratchpad/ca_glob_fix.py`, `scratchpad/ca_glob_full.csv` (full-labevents 4-itemid filter).
