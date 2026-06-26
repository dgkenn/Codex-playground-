# Strategy: Pressure–Flow Dissociation / Anesthetic Response Fragility

**North-star thesis (the paper we are aiming for):**
> *Beyond hypotension* — a pharmacology-informed intraoperative **fragility
> phenotype**, discovered from high-resolution VitalDB waveforms and externally
> validated in ~130k INSPIRE surgeries using routinely-captured perioperative
> data, identifies **occult** risk for postoperative AKI *beyond* conventional
> MAP-<65 burden and baseline clinical risk. **Pressure is not perfusion.**

This reframes the project from "deep learning predicts AKI better" (incremental,
mid-tier) to a discovery→distillation→external-validation story (NEJM-AI /
Nature Medicine / Lancet Digital Health tier).

## Two-dataset design

| Role | Dataset | Why |
|---|---|---|
| **Discovery** | **VitalDB** (open, 500 Hz waveforms + TCI pump tracks) | Train the pharmacology-informed multimodal model; discover high-risk interaction states. |
| **External validation** | **INSPIRE** (~130k SNUH surgeries, EHR @ 1–5 min) | Validate the *distilled, clinically-computable* biomarker — NOT the raw-waveform net (INSPIRE has no 500 Hz waveforms / pump Ce). |

**Binding caveat (do not overclaim):** the deep waveform/PK model is the
*discovery engine*; only the **distilled** biomarker is externally validated in
INSPIRE. Language must be: "high-resolution VitalDB waveforms were used for
biomarker discovery; the resulting clinically-computable biomarker was externally
validated in INSPIRE using routinely-captured perioperative data."

## The three escalating claims
1. **Discovery** — in VitalDB, a pharmacology-informed waveform model identifies
   latent physiologic states associated with end-organ injury.
2. **Distillation** — those latent states become interpretable, EHR-computable
   biomarkers (the PFDS family below).
3. **External validation** — a simplified biomarker predicts AKI/mortality in
   INSPIRE beyond age/ASA/emergency/surgery-type/baseline-cr/Hb/DM/HTN/duration/
   MAP-<65 burden/pressor exposure/fluid+EBL proxies.

## The biomarker stack (PFDS family) — two versions each

| Biomarker | Core idea | VitalDB (PFDS-Waveform) | INSPIRE (PFDS-Clinical) |
|---|---|---|---|
| **Pressure–Flow Dissociation** | MAP preserved while flow/perfusion surrogates deteriorate | ART + pleth amplitude/morphology + EtCO₂ + pulse pressure + HR + pressor | MAP + EtCO₂/vent vars + HR + SpO₂ + pressor timing/dose + UO/fluids |
| **Pressor-Adjusted Perfusion Stress** | normal MAP on heavy pressor ≠ normal MAP | pressor tracks + MAP/waveform/EtCO₂ response | medication admin + MAP trajectory + duration |
| **Anesthetic Response Fragility** | physiology deteriorates more than expected for anesthetic exposure | propofol/remi Ce/rate + volatile MAC + MAP/HR/BIS/EtCO₂ response | anesthesia type + gas/vitals + meds + low-res vitals |
| **Recovery Lag** | risk encoded in failure to *recover*, not just depth of insult | recovery of MAP/EtCO₂/pleth/BIS as Ce falls | recovery of MAP/HR/EtCO₂ @ 5-min; postop ward/ICU trajectory |

Two computable scores ship: **PFDS-Waveform** (VitalDB best-case) and
**PFDS-Clinical** (the distilled, INSPIRE-compatible score). Showing PFDS-Clinical
retains predictive value externally proves the signal is not waveform overfitting.

## Model distillation (the bridge)
1. Deep multimodal model in VitalDB → latent **fragility score** + important
   windows/interactions.
2. **Sparse "translation" model** trained to approximate the latent score using
   only INSPIRE-available variables (1–5 min EHR) → PFDS-Clinical.
3. Validate PFDS-Clinical in INSPIRE: AKI association, incremental value, subgroups.

## Outcomes
- **Primary:** KDIGO creatinine AKI within 7 days (48 h as sensitivity). Objective,
  common, perfusion-tied, available in both cohorts. *(We already build this.)*
- **Secondary:** severe AKI, ICU admission/LOS, prolonged LOS, in-hospital
  mortality, postop lactate/base deficit, CRRT/organ-support (INSPIRE has device
  vars), myocardial injury *only if* troponin coverage is adequate (VitalDB: no
  troponin — INSPIRE may differ; check).

## The statistics that matter (not AUROC-chasing)
Baseline risk already predicts AKI reasonably, so lead with:
1. **Risk reclassification** (NRI/IDI) over baseline + MAP-<65 + pressor + duration.
2. **Decision-curve analysis** (net benefit across realistic thresholds).
3. **Matched-risk** stratification (same age/ASA/cr/surgery/duration/MAP-burden).
4. **The "acceptable MAP" subgroup — the killer result:** among patients whose MAP
   never breaches conventional thresholds, does high PFDS still flag a subgroup
   with 2–3× AKI risk? That is the NEJM hook: *MAP thresholds miss occult injury.*

## Reporting / governance
- **TRIPOD+AI** (2024) from day one: external validation, calibration,
  fairness/bias subgroups, transparent prediction computation.
- **Pre-register** the distilled biomarker definitions before touching INSPIRE
  outcomes (no outcome peeking). Recalibrate if needed but report before/after.
- Separate confirmatory from exploratory; archive splits + artifacts with hashes
  (same discipline as the rest of this repo).

## Path to "main-NEJM plausible" (added layers, future)
- **A.** Prospective silent validation on live OR data (MGH/BWH/BMC/Brown).
- **B.** Clinical-utility simulation (the acceptable-MAP subgroup).
- **C.** Trial-ready intervention pathway (what the clinician *does*).
- **D.** External validation + decision-curve net benefit.

## Build order (concrete)
1. Confirm VitalDB↔INSPIRE variable overlap (MAP/HR/EtCO₂/SpO₂/FiO₂/volatile/
   vent/pressors/fluids/EBL/UO/baseline-cr/postop-cr/ICU-LOS/mortality).
2. Define AKI **identically** in both datasets.
3. PFDS biomarker family in VitalDB (`features/pfds.py`) — both versions.
4. Distill deep latent → sparse PFDS-Clinical.
5. INSPIRE stage (`inspire/`): client + harmonized AKI label + PFDS-Clinical +
   external-validation harness (no outcome peeking).
6. The decisive subgroup: acceptable-MAP-burden × high-PFDS AKI risk.

> Bottom line: the AI is the **microscope, not the disease**. Lead with the
> clinical biomarker; the deep model lives in Methods/Supplement.
