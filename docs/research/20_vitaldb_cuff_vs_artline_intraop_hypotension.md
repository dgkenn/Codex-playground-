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
