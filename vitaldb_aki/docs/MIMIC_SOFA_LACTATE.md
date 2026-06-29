> **PRELIMINARY (subsample).** Computed on the ~38% of the labevents file downloaded so far (labevents is subject_id-sorted -> a coherent random subsample). Complete-case n=3,109 (1,160 deaths). The FULL-data run auto-replaces this when the 2.4GB download completes; the point estimate may tighten/shift slightly but the CI margin (OR 2.44 [1.90,3.22]) is wide.

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
