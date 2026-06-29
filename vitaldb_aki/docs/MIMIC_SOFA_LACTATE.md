# MIMIC requirement->mortality adjusted for LACTATE + SOFA labs (signal vs just-sicker)

The decisive test of 'how do we know the dose is signal, not just that sick patients got more drug'. Adds first-24h lactate (shock-severity gold standard) + the lab components of SOFA (creatinine=renal, bilirubin=liver, platelets=coagulation) on top of the crude severity model (age, #vasopressors, comorbidity, ICU-LOS).

- Complete-case stays: **3109** (1160 deaths, rate 0.373). Lab components: ['lactate', 'bilirubin', 'creatinine', 'platelets', 'bun', 'wbc', 'bicarbonate', 'inr', 'albumin', 'hemoglobin', 'anion_gap', 'sodium'].

## Requirement -> mortality OR per SD, adding severity in steps
- age-adjusted: **3.798**
- + crude severity (#vasopressors, comorbidity, LOS): **2.88**
- + **lactate + SOFA labs (FULL)**: **2.438** (95% CI [1.903, 3.222])
- total attenuation age->full: **48.6%**.
- AUC: full-severity-only 0.755 -> +requirement 0.784 (**ΔAUC 0.0286**).

## Verdict
Requirement->mortality OR per SD: 3.7983862358895624 (age) -> 2.8801935477802885 (crude severity) -> **2.4380682605575767** (FULL: + first-24h lactate + SOFA labs [creatinine/bilirubin/platelets]), CI [1.903, 3.222]; total attenuation 48.6%. SIGNAL BEYOND SEVERITY: the requirement OR survives adjustment for lactate + the SOFA lab components, still adding AUC +0.0286 over the full severity model. So it is not MERELY 'sicker patients got more drug'. CAVEAT: SOFA approximated by lab components + #vasopressors; no GCS / PaO2-FiO2 (chartevents).

## Caveats
- First-24h WORST labs (max lactate/creatinine/bilirubin, min platelets) avoid end-of-life reverse causation. Lab coverage limits N (only stays with first-24h labs).
- SOFA is APPROXIMATED: lab components (renal/liver/coag) + #vasopressors (cardiovascular). NO neurological (GCS) or respiratory (PaO2/FiO2) components -- those need the 30GB chartevents. A full SOFA could attenuate slightly further.
- Observational; norepinephrine dose is a known severity/mortality marker -- this quantifies how much of the requirement->mortality link is independent of measured severity.

## Round-3 notes (selection + over-adjustment)
- **Complete-case selection does NOT bias the effect:** the lab-complete subset is sicker (mortality 0.37 vs 0.32), but the age-adjusted requirement OR there (3.80) equals the full cohort (3.80) and the lab-incomplete complement (3.75). Selection moves the base rate, not the requirement effect -> the 3.80->2.44 attenuation is not a subset artefact.
- **#vasopressors is partly a MEDIATOR** (rho +0.46 with the requirement: needing a 2nd/3rd pressor IS a higher requirement). Including it is over-adjustment toward the null. WITHOUT the #vaso term, the requirement OR beyond comorbidity + lactate + SOFA labs is **2.97** (vs the over-adjusted 2.44) -- the 'beyond severity' survival is if anything UNDERSTATED.
