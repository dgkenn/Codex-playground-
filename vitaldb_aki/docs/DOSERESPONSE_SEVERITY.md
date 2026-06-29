# Severity attack on the MIMIC-IV norepinephrine dose-response gradient

HOSTILE review of the headline finding *"ICU norepinephrine requirement mortality climbs Q1 14% -> Q4 65%, monotonic"* (mimic_outcomes_doseresponse.py), which is **age-adjusted only**. The attack: the gradient is just severity -- higher dose marks sicker patients. Here we adjust the quartile gradient for **real comorbidity + cardiovascular severity** (age + Charlson + van Walraven/Elixhauser + #vasopressors) by **g-computation / standardization** and ask whether the monotone Q1->Q4 gradient **survives or flattens**.

Method: fit one logistic model `death ~ C(quartile) + covariates`; for each quartile q, set the WHOLE cohort to quartile q, predict each patient's risk under their real covariates, average -> the covariate-standardized adjusted mortality at dose-quartile q. Requirement = per-stay median norepinephrine rate (0<rate<=5 mcg/kg/min). Charlson + van Walraven reuse the Quan-2005 / vanWalraven-2009 scoring from mimic_severity_scores.py.

- Complete-case stays: **15949** (5258 in-hospital deaths, rate 0.3297).
- Stays per quartile: [3988, 3987, 3987, 3987]; dose range per quartile (mcg/kg/min): [[0.01, 0.05], [0.05, 0.08], [0.08, 0.15], [0.15, 4.0519]].

- Charlson per hadm: mean 2.247 (SD 2.299); van Walraven mean 7.414 (SD 9.119).

## 1+4. Adjusted dose-response gradient (g-computation) and monotonicity

| Quartile | Crude mortality | Adjusted (age only) | Adjusted (age+Charlson+vanWalraven) | Adjusted (FULL +#vaso) |
|---|---|---|---|---|
| Q1 | 0.1399 | 0.141 | 0.1493 | 0.1757 |
| Q2 | 0.2032 | 0.2023 | 0.205 | 0.2252 |
| Q3 | 0.3248 | 0.3255 | 0.32 | 0.3198 |
| Q4 | 0.6509 | 0.6504 | 0.6376 | 0.5744 |

- **Crude Q1 0.1399 -> Q4 0.6509 (risk ratio 4.653x).**
- **FULL-severity-adjusted Q1 0.1757 -> Q4 0.5744 (adjusted risk ratio 3.268x [[3.024, 3.535]]; adjusted risk difference 0.3986 [[0.3761, 0.4204]]).**
- Adjusted gradient monotonic non-decreasing: **True**; strictly increasing: **True**.
- Adjusted ordinal linear-trend (quartile score in the covar model): OR 2.164/quartile-SD, p=2.4564566073473597e-277.

## 2. Adjusted per-SD OR (gradient framing)
- Full severity (age+Charlson+vanWalraven+#vaso): OR **3.047**/SD [2.732, 3.343].
- Age only: OR 3.798/SD [3.442, 4.156].
- (Should reproduce the ~3.0 full-adjustment OR from MIMIC_SEVERITY_SCORES.md.)

## 3. Where does the attenuation come from? (#vasopressors localisation)
- Adjusted Q4/Q1 RR WITHOUT #vasopressors (age+Charlson+vanWalraven): **4.272x**.
- Adjusted Q4/Q1 RR WITH #vasopressors (full): **3.268x**.
- The drop between these two localises how much of the flattening is multi-pressor refractory shock (#vasopressors) vs chronic comorbidity burden.

## Verdict
SEVERITY ATTACK ON THE DOSE-RESPONSE GRADIENT (MIMIC-IV, n=15949 norepi stays, 5258 in-hospital deaths). CRUDE (age-era headline) quartile mortality [0.1399, 0.2032, 0.3248, 0.6509] (Q4/Q1 risk ratio 4.653x). After FULL severity adjustment (age + Charlson + van Walraven/Elixhauser + #vasopressors) by g-computation, the STANDARDIZED quartile mortality is [0.1757, 0.2252, 0.3198, 0.5744] (adjusted Q4/Q1 RR 3.268x [[3.024, 3.535]], adjusted risk difference 0.3986 [[0.3761, 0.4204]]). Adjusted gradient monotonic non-decreasing: True; strictly increasing: True; adjusted ordinal linear-trend p=2.4564566073473597e-277. The excess Q4-vs-Q1 risk ratio above 1 retains 62% of its crude magnitude after full adjustment. LOCALISING THE ATTENUATION: adjusting for comorbidity WITHOUT #vasopressors leaves adjusted Q4/Q1 RR 4.272x ([0.1493, 0.205, 0.32, 0.6376]); ADDING #vasopressors brings it to 3.268x -- so most of the flattening is driven by #vasopressors (multi-pressor refractory shock), not by chronic comorbidity burden. PER-SD OR (gradient framing): full-severity 3.047 [2.732, 3.343] (age-only 3.798). VERDICT: SURVIVES — DOSE-RESPONSE BEYOND SEVERITY. The monotone dose-response is NOT merely severity confounding -- it persists, graded, after standard comorbidity + cardiovascular-severity adjustment. The headline gradient holds in attenuated but real form. CAVEAT: observational; severity captured by Charlson + van Walraven + #vasopressors (a cardiovascular-SOFA proxy) -- no GCS/PaO2-FiO2/lactate here, so residual confounding by acute physiology remains; the requirement marks risk, not a treatment effect.

## Methods / caveats
- G-computation (direct standardization to the pooled covariate distribution) is used instead of reading a coefficient, because the logistic OR is non-collapsible; the standardized marginal risks are the apples-to-apples adjusted gradient.
- Quartiles are rank-based equal-count bins on the median requirement, matching the headline module's binning so the crude column reproduces the published gradient.
- Bootstrap 95% CIs resample stays (400 reps, seed 20260628). The adjusted linear-trend p is a Wald read from the observed information matrix.
- Severity = Charlson + van Walraven (Quan 2005 / vanWalraven 2009, per hadm) + #vasopressors (cardiovascular-SOFA proxy). No GCS / PaO2-FiO2 / lactate (chartevents / labs not used here), so residual confounding by acute physiology remains. Observational; the requirement marks severity/risk, not a treatment effect.
