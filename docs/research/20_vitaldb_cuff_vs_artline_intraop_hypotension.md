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

## Files
- `scratchpad/vitaldb/vitaldb_bp.py`, track data in `scratchpad/vitaldb/trk/`.
