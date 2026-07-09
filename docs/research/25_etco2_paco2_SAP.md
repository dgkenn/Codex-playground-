# Pre-registration / SAP — etCO₂ systematically misreads PaCO₂ → occult intraoperative hypercapnia

**Written before modeling** (mirrors the C8 SAP, doc 22). Candidate anesthesiology flagship #1. The finding must
clear the same bar C8 cleared across three adversarial rounds: a routine monitor systematically misleads → clinical
mis-titration → hard-outcome consequence, with a ground-truth reference in the data and a direction-predicting
mechanism.

## Hypothesis
End-tidal CO₂ (etCO₂), used intraoperatively to titrate ventilation on the assumption etCO₂ ≈ PaCO₂,
**systematically under-reads arterial PaCO₂**, so a subset of patients are called "normocapnic" while truly
hypercapnic/acidotic. The gap is driven by alveolar **dead space** and its named determinants; the misclassification
propagates to a ventilation-response gap and worse outcomes.

## Data & ground truth
- **INSPIRE** (~130k ops): intraop `etco2`, `rr`, `minvol`, `fio2`, `peep`, `pip` (from vitals.csv) + arterial
  blood gas `paco2`, `ph`, `hco3`, `be` (from labs.csv) + operations (age, sex, weight/height→BMI, department,
  op window, CPB, ICU, mortality). **Ground-truth reference = arterial PaCO₂.**
- **VitalDB**: capnography (`Primus/ETCO2`, `Solar8000/ETCO2`) + ABG → external replication of direction.
- (Stretch) eICU/MIMIC ventilated ICU patients with etCO₂ + ABG.

## Primary target (reclassification, RTM-safe)
- **etCO₂-missed hypercapnia** = an ABG with PaCO₂ ≥ 50 mmHg (severe: ≥ 60) where the paired etCO₂ (windowed
  median within ±X min of the draw) is in the "reassuring" range (≤ 45, i.e. would not prompt escalation).
- **RTM-safe:** condition on the arterial value; report etCO₂ **sensitivity/miss-rate for ABG-defined
  hypercapnia** (never bin on etCO₂). Bland-Altman (etCO₂−PaCO₂) reported **by PaCO₂ stratum**.
- Pairing: ABG (subject_id, chart_time) → op whose window contains chart_time → etCO₂ readings for that op within
  ±X min; sensitivity of X via window-width analysis (±2/3/5 min).

## Analyses (pre-specified)
1. **Discordance/magnitude:** etCO₂ sensitivity for PaCO₂≥50/≥60; Bland-Altman gap by PaCO₂ stratum; window-width
   robustness; % of ABGs that are "normocapnic-by-etCO₂ but hypercapnic-by-ABG."
2. **Mechanism (direction-predicting):** etCO₂−PaCO₂ gap regressed on dead-space markers (age, BMI, low
   MAP/cardiac index proxy, long duration, one-lung/thoracic, steep-Trendelenburg/pneumoperitoneum proxy via
   procedure type). Prediction: gap widens with each; the sign is pre-committed.
3. **Consequence (treatment-gap analog):** among ABG-defined hypercapnia, compare etCO₂-detected vs etCO₂-missed
   on subsequent **minute-ventilation increase** (Δminvol/RR after the ABG) and on hard outcomes
   (postop AKI, arrhythmia proxy, reintubation/ICU, mortality), within-operation where possible, adjusted.
4. **Tautology guard (the C8 lesson):** condition outcome on **continuous true PaCO₂/pH burden**; if the etCO₂-flag
   OR → null once true burden is included, present the attenuation as the quantified *consequence* of undercounting
   (a strength), not an independent effect.
5. **Leakage/confounder guards:** no realized-duration-style look-ahead in any predictor; report the analysis at
   the ABG-event level with per-subject clustering; note that ABG draws are non-random (sicker patients) →
   selection stated, mechanism (dead-space physics) is selection-independent.

## Threat model (pre-committed responses, from the C8 review experience)
- "The etCO₂–PaCO₂ gradient is textbook" → novelty is the **systematic subgroup bias + reclassification rate +
  outcome propagation at 130k-op scale**, not the gradient's existence. Quantify how often it flips management.
- "ABG draws are selected" → report as within-op / conditioned on true PaCO₂; mechanism is device/physiology, not
  selection.
- "Direction not magnitude across cohorts" → report INSPIRE vs VitalDB as direction + order-of-magnitude.
- Kill criteria: if etCO₂ miss-rate for true hypercapnia is small, or the gap does not track dead-space markers, or
  the tautology test shows no consequence — **log as a negative result and stop** (cheap kill).

## Success criteria (gate)
PASS if (a) etCO₂ misses a clinically meaningful fraction of ABG-defined hypercapnia, (b) in the dead-space
direction, (c) with a ventilation-response gap and/or hard-outcome signal, (d) surviving RTM + tautology + external
replication. Otherwise negative-result lesson.

## RESULTS (INSPIRE, 93,178 stable etCO₂↔PaCO₂ pairs; window-robust ±2/3/5 min)
**Discordance (robust to a capnography-validity filter — plausibility range 15–70 excludes disconnection, gives
the identical 93,178 pairs, so NOT a non-ventilation artifact):**
- Mean etCO₂−PaCO₂ = **−7.5 mmHg** (etCO₂ under-reads). Gap by PaCO₂ stratum: −2.6 (10–35) → −6.8 (35–45) →
  −12.7 (45–50) → −19.6 (50–60) → **−25.7 (60–150)**. etCO₂ stays nearly flat (median 30→39) as PaCO₂ climbs.
- **Reclassification: 4.1%** of intra-op ABGs are "reassuring etCO₂ ≤45 but hypercapnic PaCO₂ ≥50."

**Mechanism (dead-space markers, adjusted OLS) — PARTIAL support:**
- **Age** widens the gap: −6.0→−9.3 across age bands; adj β=−0.023/yr (p=1e-207). ✓
- **Cardiothoracic/one-lung (CTS)** widens it most: gap −10.1; adj β=−0.53 (p=1.8e-73). ✓ (one-lung → dead space)
- **Duration** weak-but-significant (adj β=−0.08/hr). ✓
- **BMI null** (β≈0, p=0.40) — obesity does NOT widen it (against naive prediction).
- **Abdominal (GS) narrows** the gap (β=+0.40) — laparoscopic CO₂ absorption raises both etCO₂ and PaCO₂.

**⚠️ STATISTICAL CAVEAT (self-caught, Oldham's fallacy):** the dominant PaCO₂ coefficient (β=−0.726) and the
"flat-etCO₂ / −25 gap at high PaCO₂" are **partly a mathematical artifact** of regressing a difference on one of
its own components. The artifact-free mechanistic evidence is the **age + thoracic** signals (adjusted for PaCO₂).
Any Bland-Altman-by-PaCO₂-stratum plot must be interpreted with this coupling in mind; the honest magnitude of the
occult-hypercapnia effect is smaller than the raw stratum gaps suggest.

## Verdict (interim): PROMISING but MEDIUM — not yet flagship-grade
Real, window-robust, validity-robust discordance with a partially-confirmed dead-space mechanism (age, one-lung),
but (i) BMI-null and abdominal-reversal temper the universality, and (ii) the headline magnitude is inflated by
Oldham's fallacy. Next before any claim: (a) **consequence** — do etCO₂-missed hypercapnic patients get a
ventilation-response gap / worse outcomes (with the tautology guard)? (b) reframe the magnitude artifact-free;
(c) external replication (VitalDB capnography + ABG). If consequence is null or the artifact-free effect is small,
log as a solid negative/'measurement-nuance' result rather than a flagship.
