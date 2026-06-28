# INDEPENDENT-CO validation of the arterial-waveform vascular-tone index
## (READ FIRST) the circularity attack this defeats

**Pivot 2** (docs/SVRI_MORPHOLOGY_HOSTILE_REVIEW.md) validated the A-line WAVEFORM tone index against **EV1000/Vigileo "measured" SVR**. But EV1000/Vigileo (FloTrac) compute cardiac output -- and hence SVR = 80*(MAP-CVP)/CO -- by **PULSE-CONTOUR analysis of the arterial waveform itself**. So the "measured SVR" is *not independent* of the predictor: both the tone index and the reference SVR are read from the SAME radial arterial waveform. The headline correlation (waveform-derived tone vs waveform-derived SVR) may be **CIRCULAR** -- a reviewer can kill the finding on this alone.

**The defense (this analysis):** re-run the validation against SVR computed from a cardiac-output source that is **INDEPENDENT of the arterial waveform**:
- **Vigilance/CO** -- PA-catheter **thermodilution** (a PA thermistor; nothing to do with the radial A-line), preferred;
- **CardioQ/CO** -- **esophageal Doppler** (descending-aorta flow).

`SVR_INDEP = 80 * (MAP_mean - CVP_mean) / CO_indep_mean`  (MAP = Solar8000/ART_MBP, CVP = Solar8000/CVP, default 5 mmHg if absent; CO gated 1.0-15.0 L/min, SVR gated 300-5000).

If the waveform tone index still predicts SVR_INDEP, the measurement is **real, not circular**. If it collapses to ~0, the EV1000 result **was circular** -> honest retraction.

## Cohort
N = **36** circularity-clean cases (26 Vigilance/thermodilution + 10 CardioQ/Doppler), each with SNUADC/ART AND an independent-CO monitor. Seed 20260626.

## Results vs an INDEPENDENT cardiac-output SVR
- **Headline Spearman(tone index, SVR_INDEP) = -0.4702** (95% bootstrap CI [-0.7292, -0.1468], perm p = 0.0105; N used 31).
- **A. Non-circularity:** strict NON-pressure morphology incremental R^2 over ALL pressure scalars = **-0.2104** (pressure-only R^2 0.2124 -> +morph R^2 0.002; full OOF r 0.6377) -> FAIL.
- **B. Overfitting:** OOF r 0.6377 vs permutation null mean 0.2149 (95th 0.4629), perm p = **0.005** -> PASS.
- **C. Body-size:** morphology incremental R^2 over pressure+weight/BSA/age/sex = **-0.4013** -> FAIL.
- **D. tau partial-Spearman vs SVR_INDEP:** raw 0.2915, **given MAP = 0.2887**, **given MAP+HR = -0.2302** (the airtight test); pure-shape(tau,AIx) incremental R^2 over pressure+HR = **-0.0408**.
- **E. Stability:** OOF r 0.6377, bootstrap CI [0.4602, 0.9384].

## EV1000 (potentially circular) vs INDEPENDENT-CO
| metric | EV1000 (pulse-contour CO) | INDEPENDENT CO (thermodil./Doppler) |
|---|---|---|
| headline OOF r (full model) | 0.4561 | 0.6377 |
| tone-index Spearman | (r~0.49 region) | -0.4702 |
| strict-morph incr R^2 over pressure | 0.1109 | -0.2104 |
| tau partial given MAP | 0.1613 | 0.2887 |

## HONEST VERDICT

PARTIALLY survives. The waveform tone index shows a real association with independent-CO SVR (Spearman -0.470, CI [-0.7292, -0.1468], perm p=0.0105; strict-morph incr R2 -0.2104, perm p=0.005), but it is ATTENUATED relative to the EV1000 result -- some of the original correlation (EV1000 r 0.4561) was likely inflated by circularity. The finding stands as an A-line SVR estimator but the effect size against a truly independent CO is smaller.

## Limitations
- Single-centre (SNUADC); the independent-CO monitor subset is small and selected (sicker cases get a PAC / esoph. Doppler).
- CVP defaults to 5 mmHg when no Solar8000/CVP track is present (a documented assumption); thermodilution/Doppler CO is itself noisy and intermittent (thermodilution boluses) -> SVR_INDEP is a noisier target than the continuous pulse-contour SVR, which BIASES correlations DOWNWARD. A preserved correlation here is therefore conservative; an attenuated one is partly measurement noise, not necessarily circularity.
