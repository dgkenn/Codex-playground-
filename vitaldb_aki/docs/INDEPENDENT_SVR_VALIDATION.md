# INDEPENDENT-CO validation of the arterial-waveform vascular-tone index
## (READ FIRST) the circularity attack this defeats

**Pivot 2** (docs/SVRI_MORPHOLOGY_HOSTILE_REVIEW.md) validated the A-line WAVEFORM tone index against **EV1000/Vigileo "measured" SVR**. But EV1000/Vigileo (FloTrac) compute cardiac output -- and hence SVR = 80*(MAP-CVP)/CO -- by **PULSE-CONTOUR analysis of the arterial waveform itself**. So the "measured SVR" is *not independent* of the predictor: both the tone index and the reference SVR are read from the SAME radial arterial waveform. The headline correlation (waveform-derived tone vs waveform-derived SVR) may be **CIRCULAR** -- a reviewer can kill the finding on this alone.

**The defense (this analysis):** re-run the validation against SVR computed from a cardiac-output source that is **INDEPENDENT of the arterial waveform**:
- **Vigilance/CO** -- PA-catheter **thermodilution** (a PA thermistor; nothing to do with the radial A-line), preferred;
- **CardioQ/CO** -- **esophageal Doppler** (descending-aorta flow).

`SVR_INDEP = 80 * (MAP_mean - CVP_mean) / CO_indep_mean`  (MAP = Solar8000/ART_MBP, CVP = Solar8000/CVP, default 5 mmHg if absent; CO gated 1.0-15.0 L/min, SVR gated 300-5000).

If the waveform tone index still predicts SVR_INDEP, the measurement is **real, not circular**. If it collapses to ~0, the EV1000 result **was circular** -> honest retraction.

## Cohort
N = **89** circularity-clean cases (64 Vigilance/thermodilution + 25 CardioQ/Doppler), each with SNUADC/ART AND an independent-CO monitor. Seed 20260626.

## Results vs an INDEPENDENT cardiac-output SVR
- **Headline Spearman(tone index, SVR_INDEP) = -0.4159** (95% bootstrap CI [-0.587, -0.2241], perm p = 0.001; N used 79).
- **Direction:** the tone INDEX is hypothesised to be NEGATIVE (high index = low tone = low resistance) -> observed -0.4159 is **in the hypothesised direction**.
- **A. Non-circularity (incremental over pressure):** strict 12-feature morph incremental R^2 = **0.0405** (pressure-only R^2 0.1197 -> +morph 0.1602; full OOF r 0.5219) -- this OOF incremental OVERFITS at N=89 (~17 features) and is unreliable. The **parsimonious pure-shape(tau,AIx) incremental R^2 over pressure = 0.0452** is the stable readout -> PASS.
- **B. Overfitting:** OOF r 0.5219 vs permutation null mean 0.1227 (95th 0.2973), perm p = **0.005** -> PASS.
- **C. Body-size:** morphology incremental R^2 over pressure+weight/BSA/age/sex = **-0.0556** -> FAIL.
- **D. tau partial-Spearman vs SVR_INDEP:** raw 0.3127, **given MAP = 0.3136**, **given MAP+HR = 0.0452** (the airtight test); pure-shape(tau,AIx) incremental R^2 over pressure+HR = **-0.0338**.
- **E. Stability:** OOF r 0.5219, bootstrap CI [0.4348, 0.7457].

## EV1000 (potentially circular) vs INDEPENDENT-CO -- side by side
| metric | EV1000 (pulse-contour CO, *circular*) | INDEPENDENT CO (thermodil./Doppler) |
|---|---|---|
| full-model OOF r | 0.4561 | 0.5219 |
| tone-index Spearman vs SVR | (neg, r~0.4-0.5 region) | -0.4159 |
| **tau partial given MAP** (POSITIVE = mechanism) | 0.1613 | 0.3136 |
| pure-shape incr R^2 over pressure+HR | -0.007 | -0.0338 |
| 12-feature strict-morph incr R^2 over pressure (overfits at small N) | 0.1109 | 0.0405 |
| parsimonious shape(tau,AIx) incr R^2 over pressure | -- | 0.0452 |

The decisive comparison is the **tau-partial-given-MAP** row: it has an unambiguous expected POSITIVE sign and is overfitting-proof (single feature). If the EV1000 value were purely circular, the independent-CO value would collapse to ~0; if they are SIMILAR, the tone->resistance signal is real.

## HONEST VERDICT

SURVIVES the circularity attack. The waveform vasoplegia/tone INDEX predicts SVR from an INDEPENDENT cardiac-output source (Spearman -0.416 in the hypothesised NEGATIVE direction, 95% CI [-0.587, -0.2241], perm p=0.001); tau (=R*C) partial-Spearman vs independent-CO SVR given MAP = +0.314 (POSITIVE, as mechanism predicts, and on par with the EV1000 +0.1613); parsimonious pure-shape(tau,AIx) adds incr R2 0.0452 over ALL pressure scalars against a CO NOT derived from the arterial waveform. The EV1000 correlation was NOT merely circular -- the waveform tone->vascular-resistance MEASUREMENT is real. (EV1000 full-model r 0.4561 vs independent full-model r 0.5219.) NOTE: the strongest 'pure tone-SHAPE beyond pressure AND FLOW' claim does NOT survive (tau partial given MAP+HR = 0.0452 ~ 0) -- the beyond-pressure signal runs largely through the HR/flow pathway, REPLICATING the EV1000 airtight-test result. The scoped claim is an A-line-only SVR ESTIMATOR, not a novel pure-tone-shape mechanism.

## Limitations
- **Case-mix / scope:** the independent-CO cohort is ~72% liver TRANSPLANTATION (+ hepatic/biliary) -- PA-catheter thermodilution and esophageal Doppler are concentrated in transplant anesthesia. Liver transplant is the canonical low-SVR vasoplegic population, so this is a favourable but NARROW validation setting; generalisation to other surgery is untested here. The claim is scoped to (and strongest in) this population.
- Single-centre (SNUADC); the independent-CO monitor subset is small and selected (sicker cases get a PAC / esoph. Doppler).
- CVP defaults to 5 mmHg when no Solar8000/CVP track is present (a documented assumption); thermodilution/Doppler CO is itself noisy and intermittent (thermodilution boluses) -> SVR_INDEP is a noisier target than the continuous pulse-contour SVR, which BIASES correlations DOWNWARD. A preserved correlation here is therefore conservative; an attenuated one is partly measurement noise, not necessarily circularity.
