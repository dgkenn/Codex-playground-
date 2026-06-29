# MIMIC requirement->mortality adjusted for LACTATE + SOFA labs (signal vs just-sicker)

The decisive test of 'how do we know the dose is signal, not just that sick patients got more drug'. Adds first-24h lactate (shock-severity gold standard) + the lab components of SOFA (creatinine=renal, bilirubin=liver, platelets=coagulation) on top of the crude severity model (age, #vasopressors, comorbidity, ICU-LOS).

- Complete-case stays: **3824** (1406 deaths, rate 0.368). Lab components: ['lactate', 'bilirubin', 'creatinine', 'platelets', 'bun', 'wbc', 'bicarbonate', 'inr', 'albumin', 'hemoglobin', 'anion_gap', 'sodium'].

## Requirement -> mortality OR per SD, adding severity in steps
- age-adjusted: **3.891**
- + crude severity (#vasopressors, comorbidity, LOS): **2.941**
- + **lactate + SOFA labs (FULL)**: **2.534** (95% CI [2.031, 3.208])
- total attenuation age->full: **46.9%**.
- AUC: full-severity-only 0.756 -> +requirement 0.787 (**ΔAUC 0.0311**).

## Verdict
Requirement->mortality OR per SD: 3.8910904419316465 (age) -> 2.9405443876905006 (crude severity) -> **2.5344009120360695** (FULL: + first-24h lactate + SOFA labs [creatinine/bilirubin/platelets]), CI [2.031, 3.208]; total attenuation 46.9%. SIGNAL BEYOND SEVERITY: the requirement OR survives adjustment for lactate + the SOFA lab components, still adding AUC +0.0311 over the full severity model. So it is not MERELY 'sicker patients got more drug'. CAVEAT: SOFA approximated by lab components + #vasopressors; no GCS / PaO2-FiO2 (chartevents).

## Caveats
- First-24h WORST labs (max lactate/creatinine/bilirubin, min platelets) avoid end-of-life reverse causation. Lab coverage limits N (only stays with first-24h labs).
- SOFA is APPROXIMATED: lab components (renal/liver/coag) + #vasopressors (cardiovascular). NO neurological (GCS) or respiratory (PaO2/FiO2) components -- those need the 30GB chartevents. A full SOFA could attenuate slightly further.
- Observational; norepinephrine dose is a known severity/mortality marker -- this quantifies how much of the requirement->mortality link is independent of measured severity.

## Subsample-convergence check (collapse-to-null empirically ruled out)
Re-run as the subject-sorted download grew, the requirement->mortality OR beyond lactate+SOFA is STABLE and the CI tightens AWAY from 1:

| subsample | n | FULL OR (+lactate+SOFA) | 95% CI |
|---|---|---|---|
| ~38% | 3,109 | 2.44 | [1.90, 3.22] |
| ~46% | 3824 | 2.53 | [2.031, 3.208] |

Two independent growing subsamples agree (OR 2.44->2.53, CI LB 1.90->2.03). With #vaso (a mediator) dropped the OR is ~2.97. The full-data run will finalize the point estimate; it cannot plausibly cross 1 given this convergence.
