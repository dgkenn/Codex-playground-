# Critical-care patient safety: albumin-corrected calcium masks severe ionized hypocalcemia — worse than total

**Status:** Strong, clean, critical-care-focused finding (race-neutral). A patient-safety companion to the calcium
flagship, aligned to anesthesia/critical care. Observable reclassification endpoint, striking magnitude,
actionable message. Honest caveat: the corrected-worse-than-total *direction* is arithmetic in hypoalbuminemia;
the *magnitude at the decision threshold* and the clinical framing are the empirical contribution.

## Question
In critically ill (ICU) patients, does the albumin-corrected calcium — the value clinicians act on — reliably
detect true (ionized) hypocalcemia, or does it falsely reassure? And does the albumin *correction* help or hurt
versus uncorrected total calcium?

## Data / method
MIMIC-IV full labevents; paired ionized (50808) + total (50893) + albumin (50862) within 2 h. **N=31,903 paired
draws.** corrected Ca = total + 0.8×(4.0 − albumin). Ionized-calcium severity bands (mmol/L): critical <0.90,
severe 0.90–1.00, moderate 1.00–1.12. "Masked" = the calcium estimate reads ≥8.5 mg/dL ("normal") despite low
ionized.

## Result — corrected calcium masks severe hypocalcemia, and worse than total
| true ionized band | n | % masked by CORRECTED (≥8.5) | % masked by TOTAL (≥8.5) |
|---|---|---|---|
| critical <0.90 mmol/L | 1,174 | **40.6%** | 20.4% |
| severe 0.90–1.00 | 2,654 | **57.2%** | 22.3% |
| moderate 1.00–1.12 | 11,606 | 81.1% | 33.3% |

**Danger cell:** of 3,828 ICU patients with severe/critical ionized hypocalcemia (ionized <1.00 mmol/L),
corrected Ca reads "normal" (≥8.5) in **52%**, and reads solidly normal (≥9.0) in **34%**.

As a detection statement: for severe ionized hypocalcemia (<1.00), **corrected-Ca sensitivity ≈ 48% vs total-Ca
≈ 78%** — the albumin correction roughly *halves* sensitivity. Mechanism: most ICU patients are hypoalbuminemic,
so the correction adds a large upward adjustment (0.8×(4−albumin)), pushing an already-borderline total into the
"normal" range — i.e., the correction is counterproductive precisely in the population that most needs an accurate
calcium.

## Why this is a critical-care/anesthesia finding (not just the flagship's racial arm)
- **Race-neutral, universal ICU safety issue** (distinct from the flagship's globulin/racial *over*-reading arm).
- High-stakes settings where it bites hardest: **massive transfusion and regional citrate anticoagulation (CRRT)**
  — citrate chelates calcium, ionized falls acutely while total can stay normal/high; relying on total/corrected
  calcium there can miss life-threatening hypocalcemia (arrhythmia, arrest, coagulopathy). Peri-operative and
  ICU relevance is direct.
- Actionable message: **do not use albumin-corrected (or total) calcium to exclude hypocalcemia in critically ill
  or massively-transfused patients — measure ionized calcium.**

## Honest positioning / novelty
- "Corrected calcium is unreliable vs ionized in critical illness" is known (Slomp 2003; Dickerson; Steele et al.).
  The sharper, less-appreciated contributions here are (1) the **severity-stratified masking magnitude** at scale
  (52% of severe ionized hypocalcemia masked), and (2) the **correction-is-counterproductive** result (corrected
  ~halves sensitivity vs total) — a concrete "stop correcting, start measuring ionized" message for ICU/anesthesia.
- The corrected>total *direction* in hypoalbuminemia is arithmetic (not novel); the magnitude and the clinical
  decision framing are the empirical, actionable content. Tier: a strong critical-care/patient-safety /
  anesthesia-journal companion to the flagship, not a standalone NEJM mechanism paper.

## External validation — INSPIRE (Korean surgical/anesthesia cohort, N=72,648 triple-paired)
Replicates and strengthens (independent institution, surgical/peri-operative population — directly anesthesia-relevant):
| true ionized band | n | % masked by CORRECTED | % masked by TOTAL | MIMIC corrected (for ref) |
|---|---|---|---|---|
| critical <0.90 | 1,162 | **77.8%** | 22.7% | 40.6% |
| severe 0.90–1.00 | 4,567 | **68.3%** | 19.2% | 57.2% |
| moderate 1.00–1.12 | 21,619 | 71.2% | 18.9% | 81.1% |

Danger cell (ionized <1.00, n=5,729): corrected reads "normal" (≥8.5) in **70%** (MIMIC 52%). The
corrected-worse-than-total pattern is robust and now cross-national (US-ICU + Korea-surgical), spanning both
**critical care and anesthesia** populations. This makes C7 a validated two-cohort patient-safety finding.

## Next (optional, if developed)
- Identify the citrate/CRRT and massive-transfusion subgroups explicitly (needs inputevents/procedureevents) and
  show the masking is worst there (the highest-stakes cell).
- Do NOT chase the downstream arrhythmia/replacement harm endpoint at scale (flagship red-team showed it is
  event-count-fragile and confounded) — the reclassification/sensitivity magnitude is the defensible finding.

## Files
- Analysis inline; reproducible from `scratchpad/ca_glob_full.csv`.
