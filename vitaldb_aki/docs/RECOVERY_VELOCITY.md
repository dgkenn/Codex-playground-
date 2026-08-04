# Recovery Velocity vs Static Hypotension Burden (raw MAP series)

## Interpretation & limitations (READ FIRST)

- **Observational, single-centre** (VitalDB / SNUH). Confounding by indication remains; this is **hypothesis-generating**, external validation on INSPIRE pending (INSPIRE has numeric MAP, so this IS externally testable).
- Recovery velocity is measured from the **raw numeric MAP time-series** (`Solar8000/ART_MBP`, ~0.5-2 Hz) -- the per-episode rate at which MAP climbs back out of each hypotensive nadir -- NOT a per-case summary proxy. This is the properly-powered re-test of the reperfusion thesis (cf. docs/REPERFUSION_DYNAMICS.md, which used summary stats and was under-powered).
- **Cohort = cases with a recovered MAP<65 episode** (recovery velocity is undefined without one). Static burden and recovery velocity are compared on the SAME hypotensive cases -- a fair 'at matched burden' contrast.
- `rv_depthwt_slope` (mmHg/min) = total mmHg recovered / total minutes recovering = the overall debt-repayment RATE. **Higher = faster recovery.** Hypothesis: faster recovery -> LESS injury.
- **Negative control:** `organ_hepatocellular` -- recovery dynamics should not plausibly cause it; a signal there flags residual confounding.
- **Cohort N = 3743**; features: rv_depthwt_slope, rv_min_slope, rv_median_slope, rv_max_time_to_recover, rv_frac_unrecovered, rv_total_unrecovered_min, rv_median_tau, rv_n_episodes.

## Incremental AUROC over static burden (DeLong)

Static-burden baseline: `map_auc_below_65, map_mean, map_lowest, map_min_below_65`.

- **composite:** base AUROC 0.5832 -> +recovery 0.6622; **ΔAUROC = +0.0790** (95% CI [0.0526, 0.1046]), DeLong p = 2.6253061946590606e-09.
- **organ_renal:** base AUROC 0.588 -> +recovery 0.6217; **ΔAUROC = +0.0336** (95% CI [-0.0138, 0.0825]), DeLong p = 0.15736861414496772.
- **organ_hepatocellular:** base AUROC 0.5819 -> +recovery 0.6285; **ΔAUROC = +0.0466** (95% CI [-0.0005, 0.0928]), DeLong p = 0.053073871686134755.

## IPTW-adjusted per-SD association + FDR

BH-FDR across primary-outcome tests: **11 survive** at q<0.05.

### composite
- `rv_depthwt_slope`: OR (good-recovery vs not) = 1.4585, p = 3.718536769054898e-05, E-value(point) = 2.276, E-value(CI) = 1.736.
- `rv_min_slope`: OR (good-recovery vs not) = 1.6744, p = 1.8406266935754649e-09, E-value(point) = 2.737, E-value(CI) = 2.182.
- `rv_median_slope`: OR (good-recovery vs not) = 1.6257, p = 2.9215507016941135e-08, E-value(point) = 2.634, E-value(CI) = 2.08.
- `rv_max_time_to_recover`: OR (good-recovery vs not) = 0.5337, p = 8.248214190979632e-13, E-value(point) = 3.153, E-value(CI) = 2.532.
- `rv_frac_unrecovered`: OR (good-recovery vs not) = 0.9355, p = 0.4509495360201662, E-value(point) = 1.341, E-value(CI) = 1.0.
- `rv_total_unrecovered_min`: OR (good-recovery vs not) = 1.012, p = 0.8990088212706026, E-value(point) = 1.122, E-value(CI) = 1.0.
- `rv_median_tau`: OR (good-recovery vs not) = 0.7215, p = 0.000442806275687389, E-value(point) = 2.117, E-value(CI) = 1.579.
- `rv_n_episodes`: OR (good-recovery vs not) = 1.6593, p = 8.78698416393155e-08, E-value(point) = 2.705, E-value(CI) = 2.101.

### organ_renal
- `rv_depthwt_slope`: OR (good-recovery vs not) = 1.4831, p = 0.03253683319437896, E-value(point) = 2.33, E-value(CI) = 1.219.
- `rv_min_slope`: OR (good-recovery vs not) = 1.9477, p = 0.00019353442760053317, E-value(point) = 3.306, E-value(CI) = 2.086.
- `rv_median_slope`: OR (good-recovery vs not) = 1.7808, p = 0.0004720252912716955, E-value(point) = 2.96, E-value(CI) = 1.898.
- `rv_max_time_to_recover`: OR (good-recovery vs not) = 1.076, p = 0.6923156648469303, E-value(point) = 1.362, E-value(CI) = 1.0.
- `rv_frac_unrecovered`: OR (good-recovery vs not) = 1.3313, p = 0.0927830499827742, E-value(point) = 1.995, E-value(CI) = 1.0.
- `rv_total_unrecovered_min`: OR (good-recovery vs not) = 1.3569, p = 0.08940366367266975, E-value(point) = 2.053, E-value(CI) = 1.0.
- `rv_median_tau`: OR (good-recovery vs not) = 0.5999, p = 0.0041270001226475644, E-value(point) = 2.722, E-value(CI) = 1.63.
- `rv_n_episodes`: OR (good-recovery vs not) = 2.1406, p = 1.9826438742585075e-05, E-value(point) = 3.703, E-value(CI) = 2.386.

## Dose-response (primary: rv_depthwt_slope quartiles)

- **composite:** injury rate by recovery-rate quartile (slowest→fastest) = [0.1004, 0.2212, 0.1711, 0.1474] (n [936, 936, 935, 936]); trend p = 0.0896; direction = **ANTI-hypothesis**.
- **organ_renal:** injury rate by recovery-rate quartile (slowest→fastest) = [0.0256, 0.0558, 0.0442, 0.0291] (n [860, 860, 860, 860]); trend p = 0.968; direction = **ANTI-hypothesis**.

## Methods (brief)

- Recovery features from raw `Solar8000/ART_MBP` (fallback NIBP/EV1000), intraop window, physiologic filter 20-200 mmHg, 10 s gap cap. Per MAP<65 episode: depth = 65 - nadir; time-to-recover to 65; slope = depth/time; exponential tau of the recovery limb. Aggregated per case.
- Incremental AUROC: paired out-of-fold logistic, StratifiedGroupKFold; DeLong test + bootstrap CI (`models/metrics.py`). IPTW per-SD logistic reuses `hypotension_treatment` propensity weights; E-values per VanderWeele & Ding; BH-FDR across primary tests. Seed 20260626.

---
*Generated by vitaldb_aki/analysis/recovery_velocity_screen.py*
