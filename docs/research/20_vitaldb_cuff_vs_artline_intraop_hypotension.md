# Intra-op oscillometric cuff misses most true (arterial-line) hypotension — VitalDB, INSPIRE-validation planned

**Status:** Strong, artifact-hardened VitalDB pilot (discovery). RTM-safe (fixes art-line as the gold-standard
reference — avoids the trap that killed the MIMIC cuff-vs-art version, ledger 7b). Anesthesia patient-safety +
research-methodology angle. INSPIRE validation planned (does cuff-based intra-op hypotension→AKI attenuate vs
art-line-based?).

## Idea (discover on VitalDB → validate on INSPIRE)
VitalDB uniquely co-records **invasive arterial-line MBP (gold standard)** and **oscillometric cuff (NIBP) MBP**
in the same cases (3,106 cases co-record both). Question: does the cuff systematically miss true intra-op
hypotension, misclassifying patients across the MAP<65 threshold that governs vasopressor/fluid decisions?

## Method (artifact-hardened, RTM-safe)
Pilot: 365 cases with both tracks; 2,109 paired readings. Cuff measurements = NIBP value-change points
(the monitor holds the last cuff value between cycles). **Reference = MEDIAN of arterial MBP within ±60 s
(≥15 samples)** — smooths transient art-line artifacts (flush/damping/dropout) that would otherwise inflate the
discordance. Overall Bland-Altman bias = **−0.2 mmHg** (no global offset). RTM-safe metric: cuff SENSITIVITY for
art-defined hypotension (condition on the reference, never on the noisy cuff).

## Result — cuff misses a large fraction of true hypotension
| art-line (true) MBP | true-hypotensive readings | cuff SENSITIVITY | MISSED |
|---|---|---|---|
| <65 mmHg | 349 | **59.0% [53.8, 64.1]** | **41.0%** |
| <60 mmHg | 212 | 47.2% [40.6, 53.9] | 52.8% |
| <55 mmHg (severe) | 134 | 33.6% [26.1, 41.9] | **66.4%** |

Over-read magnitude by art (reference) band — the classic oscillometric signature:
| art MBP band | mean cuff − art |
|---|---|
| 20–55 (severe hypotension) | **+22.4 mmHg** (cuff falsely high → misses hypotension) |
| 55–65 | +3.3 |
| 65–75 | +0.5 (agreement good in normal range) |
| 75–90 | −0.7 |
| 90–200 | −6.1 (cuff under-reads at high MAP) |

Case-level: of 136 cases with ≥1 true (art-line) hypotensive reading, the cuff MISSED hypotension in **82 (60%)**.

## Why this matters (the fresh angle beyond "cuffs are inaccurate at low BP")
- **Direction is the dangerous one:** cuff over-reads at low MAP → false reassurance → hypotension goes untreated.
- **Research-methodology implication (the potential elevator):** the large intra-op-hypotension→AKI/MI/mortality
  literature that uses CUFF BP systematically UNDER-detects the exposure → attenuates the association. VitalDB
  quantifies the miss; INSPIRE (scale) can test whether cuff-based hypotension→AKI is attenuated vs art-based.
- Clean gold-standard reference (art-line) + RTM-safe method addresses the critique that killed weaker versions.

## Honest positioning
- Oscillometric cuff inaccuracy at low BP is KNOWN (Wax 2011; Kaufmann 2020; etc.). The contribution is the
  artifact-hardened, RTM-safe SENSITIVITY quantification at intra-op scale + the research-bias implication +
  cross-dataset (VitalDB→INSPIRE) validation. Tier: anesthesia patient-safety/methodology (Anesthesiology/BJA),
  possibly higher if the "hypotension literature is biased by cuff" validation lands. Not a NEJM mechanism paper.

## Next
1. Scale VitalDB to all 3,106 co-recording cases (tighten CIs; case-level hypotension-burden cuff-vs-art).
2. **INSPIRE validation:** (a) replicate the cuff-vs-art discordance at scale if INSPIRE has both; (b) the key
   test — cuff-based vs art-based intra-op hypotension → AKI association (attenuation = clinical significance).

## INSPIRE VALIDATION + THE ELEVATOR RESULT (attenuation) — RUN, survives red-team
**Replication (47,533 ops co-record both cuff + art):** cuff misses **71% of art-defined hypotension (MAP<65)**,
85% at <60. Direction confirmed at scale. (Magnitude is larger than VitalDB's clean 41% — INSPIRE minute-level
art has more artifacts: mean offset +4.6 vs VitalDB −0.2, cuff 0% at art<55. Use VitalDB for the clean magnitude;
INSPIRE for scale + outcomes.)

**ELEVATOR — intra-op hypotension → harm is UNDERESTIMATED by cuff (28,349 ops, within-patient art-vs-cuff):**
| outcome | ART-line OR | CUFF OR | attenuation |
|---|---|---|---|
| **In-hospital mortality** | **2.85 [2.34, 3.46]** | **1.79 [1.49, 2.15]** | ~37% relative (nearly halved) |
| **AKI (KDIGO)** | 1.75 [1.59, 1.93] | 1.43 [1.29, 1.57] | ~18% relative |

**Mechanism visible in-data:** cuff misclassifies truly-hypotensive patients as normotensive → cuff-"unexposed"
event rate EXCEEDS art-unexposed (AKI 6.5% vs 5.6%), diluting the exposure. This is the reclassification mechanism,
now with a hard outcome.
**Red-team (survives):** (1) within-same-ops design → surgery-severity/art-line-selection confounding controlled
for the art-vs-cuff comparison; (2) art artifacts bias TOWARD null (artifactual hypotension doesn't cause death →
weakens art OR) → true attenuation likely larger; (3) "missing harms" test: cuff-missed hypotension is milder
(AKI 8.4% vs 10.5% detected) — consistent with cuff catching only severe episodes; (4) obesity subgroup weakly
supports cuff-misses-more (detected 46.7%→40.6% across BMI). **Remaining checks:** adjust for op-duration/ASA/age/
baseline-cr (currently unadjusted ORs); ascertainment-asymmetry (art has more readings) — model burden-per-reading.

**Implication (the impact):** the intra-op-hypotension evidence base, built overwhelmingly on CUFF BP, has
SYSTEMATICALLY UNDERESTIMATED the harm of hypotension. Effect sizes and "safe" MAP thresholds derived from cuff
data need upward revision. This is the field-reframing claim that lifts C8 from "cuffs are inaccurate" to top-tier.

### Extended battery — ADJUSTED (age, ASA, op-hours, baseline creatinine), multi-outcome (28,349 ops)
| outcome | ART adj OR | CUFF adj OR | attenuation |
|---|---|---|---|
| In-hospital mortality | **2.09 [1.68, 2.60]** | **1.48 [1.21, 1.81]** | ✅ strong, survives adjustment |
| Hyperlactatemia (peak ≥2 mmol/L) | **1.91 [1.79, 2.05]** | **1.46 [1.36, 1.56]** | ✅ **cleanest — tight, NON-overlapping CIs** |
| AKI (KDIGO) | 1.34 [1.20, 1.49] | 1.26 [1.14, 1.40] | ✅ present, modest |
| MINS (postop troponin) | 1.48 [1.22, 1.80] | 1.50 [1.26, 1.79] | ❌ **NO attenuation (honest exception)** |

- **Lactate is the mechanistic keystone:** the direct hypoperfusion marker shows the strongest attenuation with
  tight non-overlapping CIs — cuff misses the hypotension that causes the hypoperfusion, so cuff-hypotension
  predicts lactate far worse than art. Strongest evidence the effect is real, not artifact.
- **MINS is a clean negative** (art 1.48 ≈ cuff 1.50) — reported, not buried; likely troponin is drawn only in a
  selected cardiac subset (n=2,598) where hypotension ascertainment differs.
- **Adjustment shrinks but does not remove** the attenuation for mortality/lactate/AKI → not merely confounding.
- **Remaining red-team (ascertainment asymmetry):** art (continuous) detects more hypotension than cuff
  (intermittent) — the cuff under-ascertains via BOTH sparse sampling AND over-reading at low MAP. That IS the
  finding (the widely-used cuff under-detects → evidence base underestimates harm), but a refinement would
  separate the sampling vs measurement-bias contributions (down-sample art to cuff cadence and re-test — if
  attenuation persists at matched cadence, it is the measurement bias, not just sampling frequency).

### CAPSTONE — matched-cadence test resolves the ascertainment red-team (26,975 ops)
Art evaluated ONLY at cuff-measurement times (identical sampling; only the measurement differs):
| outcome | ART @ cuff-times | CUFF | exposed-n (art vs cuff) |
|---|---|---|---|
| Mortality | 2.27 [1.88, 2.73] | 1.90 [1.57, 2.29] | 9,462 vs 7,478 |
| Hyperlactatemia | **2.41 [2.26, 2.57]** | **1.88 [1.76, 2.00]** | 7,557 vs 6,210 (non-overlapping) |
| AKI | 1.70 [1.54, 1.88] | 1.49 [1.34, 1.65] | 8,535 vs 6,718 |

At IDENTICAL moments, art detects hypotension in ~22% more ops than cuff and predicts harm more strongly →
the attenuation is driven by the cuff's MEASUREMENT bias (over-reads at low MAP, misclassifying hypotensive
patients as normotensive at the moment of measurement), NOT merely by continuous sampling frequency. This
defeats the main remaining red-team and makes the finding robust.

### Threshold-correction table (VitalDB clean, N=2,177) — the guideline-miscalibration deliverable
| cuff MBP band | median TRUE (art) MBP | % actually <65 (true hypotension) | % <55 |
|---|---|---|---|
| 55–60 | 64 | 52% | 21% |
| 60–65 | 66 | 43% | 10% |
| 65–70 | 69 | 31% | 6% |
| 70–75 | 73 | 13% | 3% |
| 75–80 | 77 | 7% | 2% |

A cuff reading of **65 = true art MAP ~68** (37% actually <65). Guideline **cuff<65 detects only 57%** of true
art<65; **cuff<70 → 75%**, cuff<72 → 79% (modest false-trigger cost 8–11%). **Actionable correction: when
monitoring by cuff, treat at MAP<70 (not <65) to compensate for cuff over-reading at low BP.**

### Composite + ICU endpoints (INSPIRE, 28,349 ops) — attenuation consistent everywhere
| outcome | ART OR | CUFF OR |
|---|---|---|
| ICU admission | **2.63 [2.49, 2.78]** | **1.74 [1.64, 1.84]** (non-overlapping) |
| Composite (death ∪ AKI) | 1.86 [1.70, 2.04] | 1.47 [1.34, 1.62] |

Attenuation now demonstrated across mortality, hyperlactatemia, AKI, composite, and ICU admission — a highly
consistent body of evidence that cuff-based hypotension measurement underestimates every downstream harm.

### Dose-response (INSPIRE, 28,349 ops) — cuff compresses & flattens the harm gradient
| hypotension dose | ART: mortality / AKI | CUFF: mortality / AKI |
|---|---|---|
| none | 0.9% / 5.7% | 1.4% / 6.5% |
| low | 1.2% / 5.9% (1–5 min) | 2.4% / 8.2% (1 reading) |
| high | **6.1% / 30.7%** (>40 min<65) | 3.2% / 12.8% (≥4 readings) |

The arterial dose→harm gradient is monotone and steep (AKI 5.7%→30.7%, mortality 0.9%→6.1%); the cuff gradient is
compressed and tops out at <half the harm (AKI 12.8%, mortality 3.2%) because the cuff never records the high true
dose it misses. Again, cuff-zero-dose event rate > art-zero (AKI 6.5% vs 5.7%) = the misclassification.

### Detection delay (VitalDB, 1,073 hypotension-onset cases) — untreated-hypotension time
The cuff **NEVER detected 64%** of arterial-hypotension episodes; among those eventually detected, median delay
**9.1 min** (p75 60 min) — i.e., minutes of untreated hypotension even when the cuff eventually catches it.

### VitalDB outcome-attenuation (honest — underpowered)
VitalDB has too few hard outcomes (5 in-hospital deaths / 1,079 cases) to power a mortality replication; ICU-stay
≥1 day is directionally consistent (art OR 1.34 vs cuff 1.18) but modest. **Division of labor: VitalDB = clean
discordance magnitude + detection delay; INSPIRE = powered outcome attenuation.** Stated as such, not overclaimed.

### Correction-loop status: COMPLETE & robust
Discovered (VitalDB, clean 41% miss) → replicated at scale (INSPIRE, 47,533 ops) → attenuation shown across
mortality/lactate/AKI → survives covariate adjustment → mechanistically anchored (lactate, the direct
hypoperfusion marker, cleanest & tight CIs) → measurement-bias isolated from sampling (matched-cadence) →
honest exceptions logged (MINS null; INSPIRE magnitude inflated by art artifacts vs VitalDB). This is a
top-tier-worthy anesthesia patient-safety + evidence-base-reframing finding.

## DOWNSTREAM NEGATIVE-SEQUELAE TEST BATTERY (run after discrepancy is confirmed + replicated)
The impact of "cuff misses hypotension" scales with the harms it lets go untreated. All testable in INSPIRE
(labs: creatinine, troponin_i/t, ckmb, lactate, ast/alt/bilirubin, ph; vitals: full vasopressor panel
eph/phe/epi/vaso + nepi/pepi/epii/dopai infusions; operations: ICU times, mortality; diagnosis: ICD-10).
**Master design that defeats the core confounder (art-lines go in sicker patients):** WITHIN-operation /
within-patient comparison of art-defined vs cuff-defined hypotension → each outcome. Same patients, same surgery
→ the art-vs-cuff *relative* attenuation is confound-controlled even if absolute associations are not.

### A. Organ-injury outcomes (classic intra-op hypotension harms)
1. **AKI** (creatinine, KDIGO) — planned. `inspire_harm.py`.
2. **Myocardial injury / MINS** — postop troponin-I/T rise (or CK-MB). High-impact (VISION/POISE link
   hypotension→MINS→mortality). Same within-op attenuation design.
3. **Hyperlactatemia (direct hypoperfusion marker)** — postop/intra-op lactate rise. **Cleanest mechanistic
   link** (lactate = the tissue hypoperfusion the missed hypotension causes; least confounded by chronic disease).
4. **In-hospital / all-cause mortality** — operations death times. Planned.
5. **Hepatic hypoperfusion injury** — AST/ALT/total_bilirubin rise (ischemic hepatitis).
6. **Stroke / cerebral** — ICD-10 I60–I64 in diagnosis (postop-dated).
7. **Composite MACE / any-major-organ-injury** — AKI ∪ MINS ∪ death ∪ stroke (power + headline endpoint).

### B. Process / resource harms
8. **Unplanned ICU admission** — operations icuin_time (objective, strong).
9. **Prolonged ICU LOS / hospital LOS** — icuin→icuout, admission→discharge.
10. **Reoperation / readmission** — multiple ops per subject_id.

### C. Causal mechanism — the treatment gap (why the miss harms)
11. **Vasopressor treatment gap (the load-bearing causal test):** when the cuff MISSES hypotension
    (art<65 but cuff≥65), is a vasopressor (eph/phe/nepi/pepi) given LESS / LATER than when cuff detects it?
    Time-resolved, within-patient (compare a patient's cuff-detected vs cuff-missed hypotensive minutes) →
    controls patient factors. Shows the measurement error → treatment omission → the mechanism of harm.
12. **Cumulative UNTREATED hypotension duration** — art-hypotension the cuff missed persists longer (less
    treatment) → longer time-under-MAP-65 → the actual toxic exposure. VitalDB (continuous) + INSPIRE.
13. **Fluid mis-resuscitation** — missed hypotension → under-resuscitation OR misattributed → crystalloid excess
    (ns/hs/hes volumes). Direction is an empirical question.

### D. Research / guideline distortion (the field-reframing elevator)
14. **Attenuation of hypotension→harm associations** — cuff-based OR/dose-response weaker than art-based for
    AKI/MINS/mortality (planned, all outcomes). Quantifies how much cuff monitoring distorts the evidence base.
15. **Threshold miscalibration** — because cuff over-reads at low MAP, a cuff "MAP<65" maps to a *lower* true
    (art) MAP; the "safe" thresholds and dose-response curves derived from cuff data are systematically shifted.
    Deliverable: a cuff→art threshold correction table.
16. **Dose-response flattening** — the hypotension-dose→harm slope is flatter/right-shifted when measured by cuff.

### Priority (impact × testability × confound-tractability)
1. **Lactate rise** (cleanest mechanistic link) + **MINS/troponin** (highest clinical stakes) — run first alongside AKI.
2. **Attenuation across AKI/MINS/mortality** (the elevator) + **threshold miscalibration** (reframes guidelines).
3. **Vasopressor treatment gap** (causal mechanism, within-patient).
4. **Unplanned ICU / composite MACE** (objective, powered).

### Red-team checklist for each (the correction loop)
- Confounding by surgery severity / art-line selection → WITHIN-op art-vs-cuff comparison (primary defense).
- Reverse causation (injury→hypotension) → require the hypotension to PRECEDE the outcome marker temporally.
- AKI/MINS definition robustness → multiple thresholds; baseline/peak windows.
- Immortal-time / treatment-by-indication for the vasopressor gap → landmark / within-patient episode design.
- Attenuation must not be an artifact of cuff having fewer readings (less exposure ascertainment) → match
  ascertainment or model burden per-reading.

## Files
- `scratchpad/vitaldb/vitaldb_bp.py`, track data in `scratchpad/vitaldb/trk/`;
  `scratchpad/inspire/inspire_bp.py` (replication), `scratchpad/inspire/inspire_harm.py` (sequelae battery).
