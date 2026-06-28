# External validation in MIMIC-IV ICU (independent cohort, timestamps + mortality)

Validates the vasopressor-requirement finding in a DIFFERENT population (ICU critical-illness vasoplegia, not anaesthesia), with real infusion timestamps and a HARD endpoint (in-hospital death). Norepinephrine (mcg/kg/min) from icu/inputevents.

- ICU stays with norepinephrine (kg-normalised rate): **15949**; >=4 segments: 13585; multi-stay subjects: 1712.

## Replication of the core properties
- **Reliability (split-half across infusion segments):** {'r': 0.947, 'ci': [0.944, 0.95], 'n': 13585}.
- **Early -> late requirement within stay:** {'r': 0.617, 'ci': [0.605, 0.628], 'n': 13585}.
- **Trait across ICU stays (within-subject):** {'r': 0.123, 'ci': [0.074, 0.168], 'n': 1712}.

## Requirement -> in-hospital mortality (age-adjusted)
- {'n': 15949, 'deaths': 5258, 'mortality_rate': 0.33, 'adj_or_per_sd': 3.798, 'ci': [3.441, 4.174], 'auc_age_alone': 0.559, 'auc_age_plus_requirement': 0.764, 'delta_auc': 0.2051}

## Verdict
EXTERNAL (MIMIC-IV ICU, 15949 norepi stays): REPLICATES -- reliability 0.947 [0.944, 0.95]; early->late 0.617 [0.605, 0.628]. Requirement->mortality age-adjusted OR 3.798 [3.441, 4.174] (AUC +0.2051 over age). Independent ICU population (critical-illness vasoplegia) + hard endpoint + real timestamps -> strong generalisation of the requirement concept. Does NOT validate the arterial-waveform tone estimator (needs MIMIC-IV-Waveform).

## Caveats
- ICU norepinephrine context differs from intraoperative (sepsis/critical illness) -- replication here is GENERALISATION across populations (a strength if it holds), not an identical-setting check.
- Requirement = median of segment rates (mcg/kg/min); MIMIC rate is already per-kg.
- Mortality association is observational + confounded by illness severity (only age adjusted here); it shows the requirement marks risk, not a treatment effect.
- Does NOT validate the arterial-waveform tone estimator (needs MIMIC-IV-Waveform).
