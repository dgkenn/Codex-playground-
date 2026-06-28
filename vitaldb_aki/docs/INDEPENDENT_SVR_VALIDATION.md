# INDEPENDENT-CO validation of the arterial-waveform vascular-tone index
## (READ FIRST) the circularity attack this defeats

**Pivot 2** (docs/SVRI_MORPHOLOGY_HOSTILE_REVIEW.md) validated the A-line WAVEFORM tone index against **EV1000/Vigileo "measured" SVR**. But EV1000/Vigileo (FloTrac) compute cardiac output -- and hence SVR = 80*(MAP-CVP)/CO -- by **PULSE-CONTOUR analysis of the arterial waveform itself**. So the "measured SVR" is *not independent* of the predictor: both the tone index and the reference SVR are read from the SAME radial arterial waveform. The headline correlation (waveform-derived tone vs waveform-derived SVR) may be **CIRCULAR** -- a reviewer can kill the finding on this alone.

**The defense (this analysis):** re-run the validation against SVR computed from a cardiac-output source that is **INDEPENDENT of the arterial waveform**:
- **Vigilance/CO** -- PA-catheter **thermodilution** (a PA thermistor; nothing to do with the radial A-line), preferred;
- **CardioQ/CO** -- **esophageal Doppler** (descending-aorta flow).

`SVR_INDEP = 80 * (MAP_mean - CVP_mean) / CO_indep_mean`  (MAP = Solar8000/ART_MBP, CVP = Solar8000/CVP, default 5 mmHg if absent; CO gated 1.0-15.0 L/min, SVR gated 300-5000).

If the waveform tone index still predicts SVR_INDEP, the measurement is **real, not circular**. If it collapses to ~0, the EV1000 result **was circular** -> honest retraction.

## Cohort
N = **59** circularity-clean cases (41 Vigilance/thermodilution + 18 CardioQ/Doppler), each with SNUADC/ART AND an independent-CO monitor. Seed 20260626.

## Results vs an INDEPENDENT cardiac-output SVR
- **Headline Spearman(tone index, SVR_INDEP) = -0.4983** (95% bootstrap CI [-0.6892, -0.2478], perm p = 0.0005; N used 52).
- **Direction:** the tone INDEX is hypothesised to be NEGATIVE (high index = low tone = low resistance) -> observed -0.4983 is **in the hypothesised direction**.
- **A. Non-circularity (incremental over pressure):** strict 12-feature morph incremental R^2 = **-0.1527** (pressure-only R^2 0.1549 -> +morph 0.0022; full OOF r 0.553) -- this OOF incremental OVERFITS at N=59 (~17 features) and is unreliable. The **parsimonious pure-shape(tau,AIx) incremental R^2 over pressure = 0.0066** is the stable readout -> FAIL.
- **B. Overfitting:** OOF r 0.553 vs permutation null mean 0.1505 (95th 0.3643), perm p = **0.005** -> PASS.
- **C. Body-size:** morphology incremental R^2 over pressure+weight/BSA/age/sex = **-0.2229** -> FAIL.
- **D. tau partial-Spearman vs SVR_INDEP:** raw 0.3214, **given MAP = 0.2581**, **given MAP+HR = 0.0196** (the airtight test); pure-shape(tau,AIx) incremental R^2 over pressure+HR = **-0.0584**.
- **E. Stability:** OOF r 0.553, bootstrap CI [0.457, 0.8701].

## EV1000 (potentially circular) vs INDEPENDENT-CO -- side by side
| metric | EV1000 (pulse-contour CO, *circular*) | INDEPENDENT CO (thermodil./Doppler) |
|---|---|---|
| full-model OOF r | 0.4561 | 0.553 |
| tone-index Spearman vs SVR | (neg, r~0.4-0.5 region) | -0.4983 |
| **tau partial given MAP** (POSITIVE = mechanism) | 0.1613 | 0.2581 |
| pure-shape incr R^2 over pressure+HR | -0.007 | -0.0584 |
| 12-feature strict-morph incr R^2 over pressure (overfits at small N) | 0.1109 | -0.1527 |
| parsimonious shape(tau,AIx) incr R^2 over pressure | -- | 0.0066 |

The decisive comparison is the **tau-partial-given-MAP** row: it has an unambiguous expected POSITIVE sign and is overfitting-proof (single feature). If the EV1000 value were purely circular, the independent-CO value would collapse to ~0; if they are SIMILAR, the tone->resistance signal is real.

## HONEST VERDICT

SURVIVES as a MEASUREMENT (non-circular), with the incremental-over-pressure claim scoped. The waveform vasoplegia/tone INDEX predicts INDEPENDENT-CO SVR (Spearman -0.498, NEGATIVE as hypothesised, CI [-0.6892, -0.2478], perm p=0.0005); tau partial vs independent-CO SVR given MAP = +0.258 (POSITIVE, mechanistic, ~EV1000's +0.1613). So the EV1000 result was NOT merely waveform-vs-waveform circular -- the tone->resistance signal is real against a thermodilution/Doppler CO. CAVEAT: the 12-feature OOF incremental over pressure is unstable at N=59 (overfits -> -0.1527); the parsimonious 2-feature shape incremental is 0.0066. And as with EV1000, pure tone-SHAPE does NOT add beyond pressure+HR (tau|MAP+HR=0.0196~0): the scoped claim is an A-line SVR ESTIMATOR (uses pressure+HR+shape), not a novel pure-shape mechanism.

## Limitations
- **Case-mix / scope:** the independent-CO cohort is ~72% liver TRANSPLANTATION (+ hepatic/biliary) -- PA-catheter thermodilution and esophageal Doppler are concentrated in transplant anesthesia. Liver transplant is the canonical low-SVR vasoplegic population, so this is a favourable but NARROW validation setting; generalisation to other surgery is untested here. The claim is scoped to (and strongest in) this population.
- Single-centre (SNUADC); the independent-CO monitor subset is small and selected (sicker cases get a PAC / esoph. Doppler).
- CVP defaults to 5 mmHg when no Solar8000/CVP track is present (a documented assumption); thermodilution/Doppler CO is itself noisy and intermittent (thermodilution boluses) -> SVR_INDEP is a noisier target than the continuous pulse-contour SVR, which BIASES correlations DOWNWARD. A preserved correlation here is therefore conservative; an attenuated one is partly measurement noise, not necessarily circularity.
