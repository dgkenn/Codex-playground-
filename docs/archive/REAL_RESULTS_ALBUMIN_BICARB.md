# ALBIOS (albumin) & BICAR-ICU (bicarbonate) — single-method temporal IV fails both gates (honest retirement)

Two lab-triggered trials whose analyte has **no second same-time method**, so the cross-method discordance
instrument is unavailable and only the temporal (single-method) design is possible. Both are gated honestly.

- **ALBIOS** (Caironi NEJM 2014): give 20% albumin when serum albumin <30 g/L (3.0 g/dL). RCT truth: **null**
  (90-day mortality RR 0.94).
- **BICAR-ICU** (Jaber Lancet 2018): give NaHCO₃ for severe metabolic acidaemia (pH≤7.20 — proxied here by
  HCO₃<15). RCT truth: **null overall**, benefit in the a-priori AKIN 2–3 subgroup.

## Design and gates
Temporal design: prior draw = severity control, current draw crosses the flag; D = albumin / NaHCO₃ infusion
≤6h; Y = in-hospital / 30-day mortality. Two mandatory gates: (1) **drift diagnostic** — short-gap vs long-gap
repeat-draw sigma near the flag (temporal noise is analytic only if short ≪ long and near the assay CV);
(2) **NC** — does the flag predict RBC transfusion (unrelated)?

## Result — both fail
| analyte | drift: short σ / long σ | first stage (F) | flag-ITT (30-day) | NC-RBC |
|---|---|---|---|---|
| Albumin (<3.0) | 0.305 / 0.264 = **1.15** (FAIL) | +0.008 (F 4, weak) | +0.048 [+0.029, +0.067] | **+0.034 FIRES** |
| HCO₃ (<15) | 3.289 / 2.593 = **1.27** (FAIL) | +0.099 (F 141) | +0.109 [+0.082, +0.136] | **+0.061 FIRES** |
| HCO₃, AKI proxy (creat≥2) | — | +0.094 (F 69) | +0.093 [+0.054, +0.133] | **+0.059 FIRES** |

**Drift fails in both** — and the short-gap sigma is actually *larger* than the long-gap sigma, because a
repeat draw within a few hours is **selected for clinical instability** (active resuscitation/treatment), so
the "short-interval noise" is drift + selection, not analytic. **NC fires in every stratum** — the flag
predicts RBC transfusion, i.e. carries acuity beyond the analyte. Albumin additionally has a weak first stage
(albumin infusion is rare, 1.6%). The large positive flag-ITTs (bicarbonate +0.11 to +0.20) are **confounded,
not causal** — reflexive bicarbonate/albumin is given to the sickest patients, and the temporal instrument does
not break that. The AKI-subgroup bicarbonate estimate also fails NC, so it does not recover the BICAR-ICU AKIN
benefit either.

## Fidelity follow-up: BICAR-ICU's REAL 3-way gate (pH≤7.20 AND PaCO2≤45 AND HCO3≤20)
The original run used HCO3<15 alone as an eligibility proxy. Per the user's push to replicate trial
methodology exactly, we now have pH (itemid 50820) and PaCO2 (50818), freshly streamed from labevents, plus
blood-gas HCO3 (50811bg-family, `lab_hco3bg.csv`). Building the REAL joint criterion (all three from the same
blood-gas draw, matched within 30 min) gives a cohort of **n=182** — an order of magnitude smaller than the
single-lab proxy. This is **fidelity, not a bug**: BICAR-ICU's inclusion is deliberately narrow (severe,
compensated respiratory-normal acidemia), and the honest joint gate reflects that. The cohort is too small for
a reliable instrument-based estimate (design-only for causal inference), but it is the methodologically correct
eligibility definition, and is used for any future attempt (e.g. if HiRID/SICdb access adds cases). The
underlying instrument problem is unchanged: no cross-method pH/PaCO2/HCO3 triple exists (single measurement
method each), so the temporal-noise IV already failed drift+NC gates in the wider proxy cohort — a valid
instrument for BICAR-ICU's real gate is still not available in MIMIC-IV alone.

## Verdict — RETIRED (both)
No valid assay-noise instrument exists on this data for albumin or bicarbonate: single-method → no cross-method
discordance; temporal noise is drift-contaminated (and selection-contaminated at short gaps); NC confirms
residual confounding. Logged honestly. A valid emulation would need a design-based instrument (provider/unit
practice-variation in albumin/bicarbonate thresholds) or arterial-pH streaming with a genuinely independent
second acid-base method — not a repurposed temporal-noise instrument.
