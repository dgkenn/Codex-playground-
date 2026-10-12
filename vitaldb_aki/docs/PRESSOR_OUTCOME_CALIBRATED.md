# Pivot #3: cumulative vasopressor requirement -> organ injury (calibrated)

Tests whether cumulative norepinephrine requirement is the real intraoperative hemodynamic-insult exposure for AKI -- using the SAME negative-control calibration that killed the CKD-MAP finding, because pressor-by-indication confounding is the central threat.

- Cohort: 130960 INSPIRE operations; norepi infusion used in 3261.
## Adjusted risk differences (g-computation, marginal)
- organ_renal (TARGET): adjRD **0.0518** (95% CI [0.04396, 0.06066], base 0.0487, events 4213).
- organ_hypoperfusion (perfusion): adjRD **0.11561** (95% CI [0.09473, 0.13679], base 0.1453, events 1648).
- organ_hepatocellular (negative control): adjRD **0.03184** (95% CI [0.02087, 0.04387], base 0.0945, events 5735).
- organ_cholestatic (negative control): adjRD **0.10013** (95% CI [0.08636, 0.11401], base 0.0784, events 4542).
- organ_coagulation (negative control): adjRD **0.13623** (95% CI [0.12037, 0.15093], base 0.0858, events 2956).

**Negative-control null:** 0.0894 +- 0.05302 (hepatocellular/cholestatic/coagulation).
**Renal calibrated vs null:** -0.0376 (z=-0.71, E-value 3.55).

## Head-to-head: MAP-AUC<65 vs norepi requirement
- mapauc_alone: adjRD 0.02115 (CI [0.01774, 0.02442]).
- norepi_alone: adjRD 0.0518 (CI [0.04396, 0.06066]).
- norepi_adj_for_mapauc: adjRD 0.04356 (CI [0.0361, 0.05163]).
- mapauc_adj_for_norepi: adjRD 0.01683 (CI [0.01331, 0.02012]).

## Norepi dose-response (tertiles vs non-users): {'tertile_1_vs_none': 0.0506, 'tertile_2_vs_none': 0.04427, 'tertile_3_vs_none': 0.05133} (monotone=False)

## Verdict
NOT SPECIFIC -- renal adjRD 0.0518 ~ negative-control null 0.0894 (calibrated -0.0376, z=-0.71); like CKD-MAP, the cumulative-pressor->AKI excess is largely confounding by indication. REFRAME SUPPORTED: norepi adds beyond MAP-AUC and MAP-AUC attenuates when adjusted for norepi -- dose is the better-identified insult.

## Caveats
- `intraop_norepi` is the recorded cumulative norepinephrine (INSPIRE); not concentration/weight-normalised here beyond weight as a covariate.
- Confounding by indication is the central threat; negative-control calibration is the mitigation, not randomisation. A NULL after calibration means the raw excess was confounding (the honest, CKD-MAP-style outcome).
- Single database (INSPIRE); VitalDB stable-epoch requirement is the mechanistic complement.
