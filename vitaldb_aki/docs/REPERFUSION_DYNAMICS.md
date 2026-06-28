# Reperfusion-Dynamics Biomarker (recovery velocity, not just burden)

## Interpretation & limitations (READ FIRST)

- **Thesis being tested:** *"It's not the pressure target -- it's how perfusion is
  RESTORED at that pressure."* Static intraoperative-hypotension burden (area /
  time under MAP 65 mmHg) is confounded by surgical magnitude: bigger, longer,
  bloodier operations accrue more burden AND more organ injury. The hypothesis is
  that the **dynamics** of recovery -- how FAST mean arterial pressure (MAP)
  climbs back out of a hypotensive nadir, i.e. the rate of repaying a perfusion
  debt -- carry organ-injury signal **beyond** total burden.

- **DERIVED FROM SUMMARY STATISTICS, NOT RAW SIGNAL (the central limitation).**
  Every recovery feature here is built from per-case **summary** statistics that
  already live in `cache/feature_matrix.csv` (e.g. `map_early_vs_late_mean_delta`,
  `map_slope_per_hr`, `map_auc65_late`). **No track was downloaded and no
  extraction was run.** A *true* per-beat recovery slope -- regressing MAP on time
  over the post-nadir window, or fitting an exponential recovery time-constant --
  would be a far richer operationalisation of "recovery velocity". It requires the
  **raw per-beat MAP series** and is deliberately **out of scope here**; it is
  listed as future work. Treat the summary-derived features as a coarse proxy.

- **Observational, single-centre** (VitalDB / SNUH). Confounding by indication is
  the central threat -- unstable patients both recover more slowly AND are more
  likely to sustain organ injury, so a "slow-recovery -> injury" association can be
  pure confounding.

- **These are HYPOTHESIS-GENERATING, not causal.** External validation (e.g.
  INSPIRE) is pending. Read the E-values: a small E-value (~1-1.5) means weak
  unmeasured confounding could nullify the result.

- **Negative control:** `organ_hepatocellular`. The recovery signal is meant to be
  renal-perfusion-specific; a comparable or stronger signal on the hepatocellular
  control flags **residual confounding** rather than a true perfusion mechanism.

- **Leakage firewall:** all features are **PREOP + INTRAOP only**. The `organ_*`
  and `composite` outcomes are the target `y`; they are **never** used as features.

## Headline result (one paragraph)

Adding the recovery-dynamics feature SET to a static-burden baseline produced a
**small but statistically detectable** incremental AUROC for the **composite**
outcome (ΔAUROC = **+0.0167**, 95% CI [+0.0007, +0.0323], DeLong p = 0.035) and
**no** incremental value for **organ_renal** (ΔAUROC = **-0.018**, p = 0.34) or
the **hepatocellular negative control** (ΔAUROC = **-0.037**, p = 0.076). In the
**fully-adjusted** continuous logistic models (recovery feature per-SD, adjusted
for static burden + preop covariates + optype), **no recovery feature survived
Benjamini-Hochberg FDR for any outcome (0/18)**. The IPTW-binarised analyses show
nominal associations, but several of them appear **just as strongly on the
hepatocellular negative control** -- the signature of residual confounding, not a
renal-specific perfusion-recovery mechanism. **Bottom line: at the
summary-statistic resolution available here, recovery dynamics do NOT robustly add
to static hypotension burden.** The thesis is not supported by these data, but it
is not adequately *tested* either, because the summary features are a weak proxy
for true per-beat recovery velocity (see limitations).

## Recovery-dynamics features (definitions)

All are functions of columns already in `feature_matrix.csv`:

| feature | definition | hypothesised direction |
|---|---|---|
| `recovery_velocity` | `map_early_vs_late_mean_delta / (65 - map_lowest)` (net late-vs-early MAP recovery scaled by nadir depth) | higher = better |
| `debt_repayment_rate` | `map_auc_below_65 / map_longest_hypotension_run_min` (burden concentration: deep-brief vs shallow-smeared) | higher (concentrated) hypothesised better |
| `late_residual_burden` | `map_auc65_late` (un-recovered hypotension in the final third) | higher = worse |
| `recovery_slope` | `map_slope_per_hr` (signed MAP trend) | higher = better |
| `nadir_recovery_frac` | `1 - map_nadir_time_frac` (runway available after the nadir) | higher = better |
| `recovery_lag` | `pfds_clin_recovery_lag` (clinical PFDS recovery-lag summary, minutes) | longer = worse |

`pfds_wf_recovery_lag` is **excluded** (only ~21 non-missing cases).

Static-burden **baseline** (the model the recovery set must beat):
`map_auc_below_65 + map_mean + map_lowest + map_min_below_65`.

## Findings

### Test 1 -- Incremental AUROC over static burden (paired OOF + DeLong)

| outcome | n | events | AUROC base | AUROC base+recovery | ΔAUROC | 95% CI | DeLong p |
|---|---|---|---|---|---|---|---|
| **composite** | 4231 | 649 | 0.595 | 0.612 | **+0.0167** | [+0.0007, +0.0323] | **0.035** |
| **organ_renal** | 3849 | 142 | 0.616 | 0.598 | -0.0180 | [-0.0545, +0.0177] | 0.338 |
| organ_hepatocellular (neg-ctrl) | 3134 | 139 | 0.595 | 0.558 | -0.0365 | [-0.0766, +0.0033] | 0.076 |

- Only **composite** shows a positive, just-significant increment; its CI nearly
  touches zero. For the **renal** primary outcome the recovery set does NOT help
  (point estimate negative).
- **Negative control behaves correctly in sign** (no positive increment), which is
  reassuring -- but the renal null undercuts a renal-perfusion-specific story.

### Test 2 -- Adjusted association (logistic + IPTW), OR + E-value

**Fully-adjusted continuous logistic (per-SD recovery feature; adjusts static
burden + preop covariates + optype):** every recovery feature's OR is close to 1
with CIs spanning 1 for all three outcomes; **none is significant after FDR
(0/18)**. E-values for the point estimates are small (~1.1-1.5), and all CI
E-values are 1.0 (CIs cross the null) -- i.e. essentially no residual confounding
would be needed to explain these away.

**IPTW-binarised ("good recovery" = oriented above median; reuses
`hypotension_treatment.fit_propensity_model` / `compute_iptw_weights`):** several
exposures reach nominal significance (e.g. `debt_repayment_rate`,
`late_residual_burden`, `recovery_lag`), **but the same exposures are nominally
significant on the hepatocellular negative control too** (e.g. `debt_repayment_rate`
OR ~2.3 and `late_residual_burden` OR ~0.61 on hepatocellular). Per the
negative-control logic, that pattern points to **residual confounding**, not a
renal-specific mechanism. **Caveat on the IPTW p-values:** the weighted GLM uses
`freq_weights`, which treats stabilised weights as frequencies and therefore
**understates the standard errors** (anti-conservative p-values). The IPTW ORs
should be read as directional, not as calibrated inference; the continuous
fully-adjusted logistic + FDR is the more trustworthy association test.

### Test 3 -- Negative control (organ_hepatocellular)

- **Incremental AUROC:** hepatocellular ΔAUROC = -0.037 (no positive increment) --
  consistent with "recovery adds nothing spurious here".
- **IPTW associations:** NON-NULL on the hepatocellular control for several
  features -> **possible residual confounding** (same flag the actionable-targets
  analysis raised). This weakens any causal read of the IPTW signals.

### Test 4 -- BH-FDR (across feature × outcome adjusted logistic tests)

**0 of 18** fully-adjusted continuous tests survive Benjamini-Hochberg at q<0.05.

### Test 5 -- Monotonic dose-response (best feature = `recovery_lag`)

The data-driven "best" feature (smallest adjusted-logistic p) was `recovery_lag`.
Its quartile dose-response has a **statistically significant trend but in the
ANTI-hypothesis direction**:

| outcome | Q1 (longest lag) | Q2 | Q3 | Q4 (shortest lag) | trend p | direction |
|---|---|---|---|---|---|---|
| composite | 0.096 | 0.146 | 0.191 | 0.204 | 3.6e-12 | **anti-hypothesis** |
| organ_renal | 0.023 | 0.040 | 0.048 | 0.044 | 0.012 | **anti-hypothesis** |
| organ_hepatocellular | 0.032 | 0.044 | 0.052 | 0.056 | 0.022 | **anti-hypothesis** |

The injury rate **RISES** from Q1 (longest recovery lag) to Q4 (shortest lag) --
the OPPOSITE of "slow recovery is worse". This almost certainly reflects how
`pfds_clin_recovery_lag` is constructed: cases with little or no real hypotensive
event get a trivially tiny "lag", and the overall correlation with composite is
essentially null (r ≈ -0.03). The module records this as `trend_direction:
"ANTI-hypothesis"` so a significant Cochran-Armitage p is not mistaken for support.
This is a cautionary result, not a positive finding.

## Methods (brief)

- **Data:** `cache/feature_matrix.csv` (n=4335) inner-joined to
  `cache/cohort_composite.csv` on `caseid`; outcome columns merged **only if not
  already present** (the feature matrix already carries `composite`/`organ_*`).
- **Test 1:** baseline vs baseline+recovery logistic, fit on **identical
  StratifiedGroupKFold splits grouped by `subjectid`**, paired out-of-fold
  probabilities -> **DeLong** correlated-ROC test (`models/metrics.delong_roc_test`),
  cluster (patient) bootstrap CI (`models/metrics.bootstrap_ci`, 2000 iters).
- **Test 2:** continuous recovery feature **per-SD**; adjusted logistic
  (statsmodels) for static burden + preop covariates (`age, sex_male, asa,
  preop_htn, preop_dm, baseline_cr, surgery_duration_min, anesthesia_duration_min,
  intraop_ebl`) + one-hot `optype`. All continuous predictors z-scored for
  numerical conditioning (recovery OR is scale-invariant). E-value /
  E-value(CI) from `actionable_targets.e_value` / `e_value_ci`.
- **IPTW:** binarise recovery into good/poor (oriented split at the median),
  reuse `hypotension_treatment.fit_propensity_model` + `compute_iptw_weights`
  (stabilised, 1%-trimmed); weighted binomial GLM. (See the `freq_weights` caveat
  above.)
- **Test 4:** Benjamini-Hochberg (`actionable_targets.benjamini_hochberg`) across
  the 18 feature×outcome adjusted-logistic p-values.
- **Test 5:** quartiles of the best feature (oriented Q1=worst..Q4=best recovery),
  **Cochran-Armitage** trend test (implemented in-module), with an explicit
  `trend_direction` flag relative to the protective hypothesis.
- **Seed:** 20260626 (matches `config.yaml`). Heavy deps lazily imported.

## Future work

- **Per-beat recovery slope / time-constant** from the raw MAP series (post-nadir
  regression slope, exponential τ, time-to-return-to-baseline), which is the
  faithful operationalisation of "recovery velocity" the summary statistics only
  approximate.
- Restrict to cases with a **genuine hypotensive event** (true nadir below 65) so
  "recovery" is defined only where there is something to recover from -- this also
  fixes the `recovery_lag` artefact.
- External replication (INSPIRE) of any surviving signal.

## Reproduce

```bash
python3 -m vitaldb_aki.analysis.reperfusion_dynamics
# -> cache/reperfusion_dynamics_results.json
```

---
*Generated by `vitaldb_aki/analysis/reperfusion_dynamics.py`*
