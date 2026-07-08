# The "A-LINES" tool — a bedside decision aid for arterial-line placement to prevent cuff-missed intra-op hypotension

**Status:** Proposed clinical decision tool derived from C8 (doc 20) + literature. Fills a documented gap: there is
"considerable variation in practice and no clear consensus" on arterial-line placement in non-cardiac surgery,
especially ASA-2 major and ASA-3 moderate-major cases, and **no standardized decision tool exists**. Needs
prospective validation.

## Rationale (what's new)
Standard A-line indications (beat-to-beat BP, frequent ABGs, difficult NIBP) are qualitative and inconsistently
applied. C8 adds a specific, quantitative rationale: the oscillometric cuff **misses ~half of harm-associated
intra-op hypotension** (and the hypotension→mortality association is nearly double when measured by art-line:
adj OR 2.09 vs 1.48). So an A-line is not merely for convenience — in the right patient it **prevents undetected,
untreated hypotension** that the cuff cannot see. The number-needed-to-monitor (art-lines per one harm-associated
missed hypotension surfaced, INSPIRE) is favorable in identifiable groups: urology 18, ASA≥3 21, general surgery
/ >4 h 30 — versus 83–198 in low-risk groups.

## The tool — "A-LINES" (consider an arterial line if ≥2 factors, or any one MAJOR trigger)
| Letter | Factor | Basis |
|---|---|---|
| **A** | **ASA ≥ III** (or major cardiopulmonary comorbidity) | data: NNM 21 |
| **L** | **Long case** — anticipated > 3–4 h | data: >4 h NNM 30 |
| **I** | **Instability anticipated** — major fluid shifts, hemorrhage risk, or expected vasopressor need | literature + C8 treatment-gap |
| **N** | **NIBP unreliable** — morbid obesity, atrial fibrillation/arrhythmia, severe PAD, or positioning limiting cuff cycling (prone/lateral, arms tucked) | literature (cuff accuracy) |
| **E** | **Extraction of frequent labs/ABGs** — respiratory failure, one-lung ventilation, acid–base/glucose lability | standard indication |
| **S** | **Serious / high-yield surgery** — major abdominal, urologic, vascular, cardiac, neuro, transplant | data: urology NNM 18, GS 30 |

**Decision rule**
- **0–1 factors:** cuff acceptable — but **cycle every ≤2–3 min** and **treat at MAP < 70** (offsets the cuff's
  over-reading; captures 68% vs 52% of harm-associated hypotension).
- **≥2 factors:** **strongly consider an arterial line preoperatively** (favorable number-needed-to-monitor).
- **Any single MAJOR trigger** — cardiac/major-vascular surgery, active hemodynamic instability, or NIBP known
  unreliable in a case where hypotension is likely — **place an arterial line.**

**Why preoperative, not reactive:** an early intra-op cuff signal is a weak trigger (early cuff<75 → later
hypotension PPV 40%, sensitivity for harm 39%) because the cuff misses hypotension early too — so the decision
should be made preoperatively from the A-LINES factors, not by waiting for the cuff to alarm.

## Honest positioning
- Derived (not yet prospectively validated) from a two-cohort observational study (VitalDB/INSPIRE, one
  institution); external and prospective validation required before adoption.
- NNM is per harm-associated missed hypotension SURFACED, not per harm PREVENTED (prevention also depends on
  treatment efficacy).
- Complements, not replaces, clinical judgment and established indications; contraindications (e.g., inadequate
  collateral flow) still apply.

## Manuscript use
Include as a boxed clinical tool / figure in the C8 manuscript's clinical-implications section, paired with the
threshold-correction (MAP<70) and cuff-cycling (≤2–3 min) recommendations — the three-part actionable package:
detect (cycle + threshold), and when yield is high, measure directly (A-LINES → arterial line).

## VALIDATION 1 — INSPIRE (28,349 co-recording ops): the tool discriminates and beats single factors
A-LINES score (A=ASA≥III, L=>4h, I=emergency, N=BMI≥35, S=high-yield surgery [UR/GS/VS/CTS/NS/OS]) vs
harm-associated cuff-missed hypotension:
| score | harmful-missed | any harm |
|---|---|---|
| 0 | 0.2% | 0.8% |
| 1 | 1.2% | 5.4% |
| 2 | 3.7% | 10.5% |
| 3 | 5.9% | 19.9% |
| 4 | 11.2% | 37.9% |

- **AUC 0.70** (harm-assoc missed hypotension), 0.67 (any harm) — vs best single factor 0.60 (duration), 0.59
  (ASA). The composite adds discrimination over any one criterion.
- **Threshold ≥2:** flags 37% of ops, **captures 71%** of all harm-associated missed hypotension, **NNM 24**.
  vs ASA≥3-alone (flags 13%, captures 31%, NNM 19 — misses 69%) and serious-surgery-alone (flags 81%, captures
  94%, NNM 39 — impractical). A-LINES≥2 is the balanced operating point.
- **Tangible benefit:** placing arterial lines per A-LINES≥2 would surface 71% of the harm-associated hypotension
  the cuff currently misses, in 37% of patients — enabling the detection→treatment step (treatment-gap OR 1.34)
  that the attenuation shows is otherwise skipped.

## REVISION 2 — optimized score + COMPOSITE A-line benefit (two-tier tool)

### (a) Mnemonic optimization (INSPIRE, n=27,140; target = harm-associated cuff-missed hypotension, 2.1%)
Rigorous per-factor test (univariate AUC, multivariable independence, cutoff scan, drop-one):
- **DROP "N" (BMI/obesity):** AUC 0.485 (below chance); multivariable p=0.86. Does not earn its place. (Low
  BMI<20 also non-discriminating.) Clinically obesity degrades cuff accuracy but does NOT translate to more
  harm-associated missed hypotension here.
- **ADD "Age ≥65":** independent (OR 1.57, z=8.7); drop-one AUC loss 0.075. Was missing.
- **ASA ≥3, Long >4h, Serious surgery** — all independent, each earns its place (drop-one loss 0.06–0.11).
  Optimal cutoffs: ASA≥3 (OR 3.16), duration >4h (>5h slightly better), age≥65 (OR 2.63).
- **Refine "Serious surgery":** high-yield = urology (cmh 4.5%), general/major-abdominal (3.2%), cardiothoracic
  (2.6%), + major vascular/transplant. **Remove neurosurgery (0.7%) and OB/gyn (0.2%)** from the risk list.
- **Emergency:** independent but marginal (drop-one 0.752→0.741). Optional.
- **Male sex:** strongest univariate (AUC 0.74) BUT redundant — adding it to the score *lowers* AUC (0.752→0.743),
  collinear with age/ASA/surgery. Do not include.
- **Result:** optimized score (ASA≥3, Age≥65, Long>4h, Serious-surgery-refined, ±Emergency) **AUC 0.752 vs
  original 0.687**; at ≥2, flags 44%, **captures 84%** of harm-associated missed hypotension, NNM 25.

### (b) The A-line does far more than catch hypotension — COMPOSITE benefit
Brainstormed full A-line uses (each a benefit the tool should weigh against the <1% complication risk):
1. **Beat-to-beat BP control** for high-stakes perfusion — cardiac, major vascular (aortic cross-clamp),
   intracranial/neuro (cerebral perfusion), carotid, pheochromocytoma, deliberate hypo/hypertension.
2. **Frequent ABG / serial labs** — respiratory failure, one-lung ventilation, major hemorrhage/massive
   transfusion (serial Hb/coags), severe acid–base/glucose/electrolyte lability.
3. **NIBP unreliable/impossible** — morbid obesity (poor fit), arrhythmia/AF, severe PAD, burns, lymphedema,
   both arms inaccessible/positioning.
4. **Precise vasoactive titration** — ongoing/anticipated vasopressor or inotrope infusion.
5. **Dynamic hemodynamics** — PPV/SVV/pulse-contour cardiac output for goal-directed therapy.
6. **(our finding) Detection of cuff-missed hypotension** → prevention of AKI/MINS/mortality/hyperlactatemia.
Current practice reflects this: NS 95% / CTS 97% get A-lines for uses 1–2 (NOT hypotension — NS cmh 0.7%), while
the ASA2–3 major-abdominal/urologic gray zone (30–45%) is variable — where use #6 (our data) guides.

### (c) The two-tier tool (composite benefit-guided)
**TIER 1 — place an arterial line for a specific established benefit (any one; independent of hypotension risk):**
beat-to-beat control case (cardiac/major-vascular/neuro/carotid/pheo) · frequent ABG needs (resp failure/one-lung/
massive transfusion) · NIBP unreliable (morbid obesity/arrhythmia/PAD/positioning) · active vasoactive titration ·
dynamic-monitoring/GDT.
**TIER 2 — no Tier-1 indication (the gray zone): risk-based score for the hypotension-harm benefit.** Consider an
A-line if ≥2 of: **ASA≥III · Age≥65 · Long case >4 h · Serious surgery (urologic/major-abdominal/cardiothoracic/
major-vascular/transplant) · Emergency.** (AUC 0.75; ≥2 → NNM 25, captures 84%.) Below threshold: cuff cycled
≤2–3 min, treat at MAP<70.

### (d) Existing tools / what the data says
Literature: NO validated scoring tool exists for A-line placement; guidelines list qualitative indications
(major surgery, comorbidity, difficult NIBP, frequent ABG, titrated vasoactives) with "no clear consensus" in the
ASA2-major / ASA3-moderate gray zone. Current practice (38% overall; ASA-graded; near-universal cardiac/neuro)
matches the Tier-1 uses well but is variable in the Tier-2 gray zone — the specific void this tool fills with a
data-backed risk score. The tool complements (does not replace) the established Tier-1 indications.
