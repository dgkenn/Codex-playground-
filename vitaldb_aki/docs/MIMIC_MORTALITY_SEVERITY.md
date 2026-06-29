# MIMIC-IV requirement -> mortality: severity-adjusted (honest)

Does the norepinephrine-requirement mortality association survive adjustment for illness severity (number of distinct vasopressors = refractory-shock marker, comorbidity burden, ICU LOS, age)? The key reviewer attack: 'the dose is just a severity marker'.

- Complete-case stays: **15935** (5249 deaths, rate 0.329).

- Requirement mortality OR per SD: **3.796 (age-adjusted) -> 3.008 (fully adjusted)**, CI [2.722, 3.366]; **attenuation 28.2%**.
- AUC: severity-only 0.715 -> +requirement 0.778 (**ΔAUC 0.0628**).
- Severity covariates: ['age', 'n_vasopressors', 'comorbidity_count', 'icu_los'].

## Verdict
Requirement->mortality OR 3.796428813966017 (age-adj) -> 3.0075376913835865 (FULLY adjusted for n-vasopressors + comorbidity + ICU-LOS + age), CI [2.722, 3.366]; attenuation 28.2%. SURVIVES severity adjustment -- the requirement carries mortality information BEYOND crude severity (adds AUC +0.0628 over the severity model). The dose is not merely a severity proxy. NOTE: no lactate/SOFA (would attenuate further); observational.

## Caveats
- Severity proxies are crude: distinct-vasopressor COUNT, distinct-ICD COUNT, ICU LOS, age. NO lactate / SOFA / APACHE (not in the manageable tables) -> a full severity score would attenuate the requirement OR FURTHER. So this is an UPPER bound on the independent signal.
- norepinephrine dose is a known ICU severity/mortality marker; this analysis quantifies how much survives crude-severity adjustment, honestly. Observational; not causal.
