# Separability probe, 2026-08-02 — quantifying E215's "cohort separability" diagnosis

*DIAGNOSTIC, not a registered experiment. No ledger row, no registration file. Numbers only, no verdict
about Challenge D.*

---

## 0. What this is answering

E215 (`bsde/src/bsde/experiments/e215_reference_forward_test.py`) tried both `R_AWAKE` and `R_SPAN` on
capslpdb and got **NEITHER RESOLVES** — both references' `W-N1` / `N2-N3` spreads collapsed relative to the
deposits they were built on (0.378 / 1.366 / 0.460 on one deposit set against 1.794 / 1.750 / 1.869 on
another, quoting the task). The diagnosis on offer was **cohort separability**, not the reference scheme.
This probe measures that directly, per catalogue rules 62 (percentile resolution needs range), 63 (derive
gates from measured quantities, not round numbers), 54 (a named confound needs a line of code or it's
unhandled) and 5 (empty groups raise, never silently NaN).

For every deposit carrying a genuine awake state and a genuine extreme non-awake state, this computes:

- **(a)** WITHIN-deposit effect size between its two most extreme labelled states — Cohen's *d* (signed,
  pooled-SD) and a scale-free rank effect size (`auc_abs(y, score) − 0.5`, from
  `bsde.verifier.stats.auc_abs`, range 0–0.5);
- **(b)** BETWEEN-deposit shift of the awake state only, same Cohen's-*d* units, reference = sleep-EDFx `W`
  (the largest healthy-adult awake cohort available, n = 142 subjects);
- **(c)** the ratio `|b| / mean(|a_ref|, |a_dep|)` — the transport problem's magnitude in the same units the
  challenge will have to beat.

`bsde.verifier.stats.read_rows` and `auc_abs` are imported, not reimplemented (rule 20). State parsing for
ds004541 and ds005620 reuses `e92_two_region_information_v2.state_ds004541` / `state_ds005620` verbatim
(rule 61: these are the parsers that already handle the signed-offset and BIDS-entity structure correctly).

The script lives at `/tmp/.../scratchpad/probe_separability.py` for this session only — it is a diagnostic,
not a committed experiment, matching how the three prior `PROBE_2026_08_02_*.md` notes were produced.

---

## 1. Deposits, what "awake" and "deep" mean in each, and why

| deposit | population | montage (n_channels) | unit of analysis | "awake" | "deep" |
|---|---|---|---|---|---|
| `sleep_edfx` (`sleep_edfx_five_stage.csv`) | healthy adult/elderly volunteers, ambulatory PSG | **2** | subject (n=142 awake, 141 deep) | stage `W` | stage `N3` (deepest AASM stage this table carries) |
| `capslpdb` (`capslpdb_stages.s*.csv`) | **sleep-clinic referrals**: narcolepsy, REM behaviour disorder, nocturnal frontal-lobe epilepsy, periodic limb movement, insomnia, sleep-disordered breathing, bruxism, plus normal controls — **not a healthy population** | 2–13 (median 13) | record (n=106/106) | stage `W` | `S3`+`S4` pooled by mean (R&K→AASM correspondence, matching E215's declared mapping) |
| `chennu` (`chennu_features_v3.csv`) | healthy volunteers, propofol titration, **task-engaged** (2-choice reaction-time task running throughout) | 91 | subject (n=20/20) | `sedation_level=1.0` ("baseline", per the deposit's own label comment) | `sedation_level=3.0` ("moderate sedation" — level 4 is "recovery", i.e. *returning toward* baseline, and is excluded from "deep" for that reason) |
| `vitaldb` (`vitaldb_grid.csv`) | surgical patients, **intraoperative EEG only** | **1** | case (n=213/156) | **NONE — see §2** | bottom BIS decile (BIS ≤ 30.4) vs top BIS decile (BIS ≥ 60.9), deciles measured on the pooled finite-BIS distribution (5,845 rows), not a round number (rule 63) |
| `ds004541` (`ds004541_v2.csv`) | healthy volunteers, propofol induction to loss of consciousness, resting | 62 | subject-window (n=69/41) | `state_ds004541() == "awake"` (baseline, pre-infusion, pre-LOC) | `state_ds004541() == "anaesthetised"` (post-LOC) |
| `ds005620` (`ds005620_features.csv`) | healthy volunteers, TMS-EEG sedation study | 64–65 | recording (n=59/143) | `state_ds005620() == "awake"` (BIDS `task-awake`) | `state_ds005620() == "anaesthetised"` (`task-sed` / `task-sed2` pooled) |

**Header-row filtering (`read_rows`): 0 shard-concatenation header rows dropped in any of the six tables** —
the defect rule 74 guards against was checked for and not present here.

---

## 2. Mandatory check: vitaldb has no awake state, and it is excluded, not substituted

Checked directly rather than assumed: of the 6,679 `status=ok` rows in `vitaldb_grid.csv`, only **16** have
`meta_rel_anestart_s <= 0` (at or before anaesthesia start), and of those only **4** carry a finite
`meta_bis`. VitalDB's EEG deposit is intraoperative-only; there is no pre-drug baseline in this table.

**vitaldb is therefore excluded from (b), the between-deposit awake comparison, and reported separately in
(a)** using its own graded BIS signal (lightest-observed-state vs deepest-observed-state, both still under
anaesthesia). This is stated in the loader's own docstring and printed at run time
(`EXCLUDED: no genuine awake state in this deposit`) — it is not silently dropped, and no lighter-anaesthesia
row was substituted for "awake".

---

## 3. Confound flagged loudly, per rule 54: channel count spans 1 to 91, and nothing in this probe adjusts for it

Measured directly on the analysed rows, not assumed:

| deposit | n_channels used |
|---|---|
| vitaldb | **1** |
| sleep_edfx | **2** |
| capslpdb | 2–13 (mixed clinical bipolar montage) |
| ds004541 | 62 |
| ds005620 | 64–65 |
| chennu | **91** |

**There is no line of code anywhere in this probe, or in the underlying feature-extraction scripts it reads
from, that adjusts a candidate's value for the recording's channel count.** This is not a hidden confound —
it is an *unhandled* one, named here explicitly per rule 54's requirement ("point at the line of code that
handles it, or say there isn't one"). It matters concretely for at least one candidate below
(`spatial_participation_ratio`), and probably others: any measure whose definition involves counting or
comparing channels (participation ratio, `wpli_alpha`, `uce_v1`'s frontal/posterior split) is a plausible
casualty of montage difference rather than of population or state, and the between-deposit numbers in §5
cannot distinguish the two explanations.

`uce_v1`, `wpli_alpha` and `spatial_participation_ratio` are **all-NaN in `vitaldb`** (1-channel montage —
consistent with, though not proof of, a channel-count dependency) and `uce_v1` is **all-NaN in
`sleep_edfx`** (2-channel montage). Both are reported as EXCLUDED (§6), never scored, per rule 74.

---

## 4. (a) WITHIN-deposit effect size — extreme-state contrast, all available columns

Cohen's *d* is signed **deep − awake** (e.g. positive `whole_head_exponent` means the exponent rises from
awake to the deep state). `auc-0.5` is the scale-free, direction-free rank effect size
(`auc_abs − 0.5`, range 0–0.5; 0 = no separation, 0.5 = perfect).

<details><summary><b>sleep_edfx</b> (W vs N3, n=142/141) — click to expand</summary>

| column | d | auc−0.5 |
|---|---:|---:|
| critical_slowing_ar1 | +3.960 | +0.489 |
| emg_beta_gamma_fraction | −2.607 | +0.489 |
| emg_index | −2.771 | +0.461 |
| emg_kurtosis | −0.974 | +0.411 |
| exponent_high | +1.401 | +0.373 |
| exponent_low | +3.620 | +0.491 |
| lempel_ziv | −2.882 | +0.474 |
| multiscale_entropy_slope | +4.407 | +0.498 |
| pac_slow_alpha | −0.530 | +0.133 |
| relative_alpha_power | −0.694 | +0.302 |
| relative_delta_power | +1.973 | +0.451 |
| spatial_participation_ratio | +0.482 | +0.197 |
| spectral_edge_95 | −3.854 | +0.478 |
| spectral_entropy | −2.665 | +0.481 |
| whole_head_exponent | +4.673 | +0.492 |
| wpli_alpha | +1.124 | +0.317 |

</details>

<details><summary><b>capslpdb</b> (W vs S3+S4, n=106/106) — click to expand</summary>

| column | d | auc−0.5 |
|---|---:|---:|
| lempel_ziv | −1.290 | +0.316 |
| relative_alpha_power | −0.751 | +0.233 |
| relative_delta_power | +1.417 | +0.347 |
| spectral_edge_95 | −1.252 | +0.336 |
| spectral_entropy | −1.336 | +0.328 |
| whole_head_exponent | +1.191 | +0.312 |

*(capslpdb's extracted panel carries only these 6 candidate columns.)*

</details>

<details><summary><b>chennu</b> (sedation_level 1 vs 3, n=20/20) — click to expand</summary>

| column | d | auc−0.5 |
|---|---:|---:|
| critical_slowing_ar1 | −0.215 | +0.078 |
| emg_beta_gamma_fraction | +0.765 | +0.208 |
| emg_index | −0.206 | +0.085 |
| emg_kurtosis | −0.518 | +0.182 |
| exponent_high | +1.565 | +0.363 |
| exponent_low | −1.353 | +0.333 |
| lempel_ziv | +1.084 | +0.277 |
| multiscale_entropy_slope | −1.721 | +0.395 |
| pac_slow_alpha | −0.761 | +0.167 |
| relative_alpha_power | −0.494 | +0.127 |
| relative_delta_power | −0.489 | +0.180 |
| spatial_participation_ratio | +0.177 | +0.125 |
| spectral_edge_95 | +0.338 | +0.110 |
| spectral_entropy | +0.766 | +0.208 |
| uce_v1 | −0.213 | +0.055 |
| whole_head_exponent | −0.340 | +0.107 |
| wpli_alpha | −0.114 | +0.135 |

</details>

<details><summary><b>vitaldb</b> (bottom vs top BIS decile, NOT awake — n=213/156) — click to expand</summary>

| column | d | auc−0.5 |
|---|---:|---:|
| critical_slowing_ar1 | +0.808 | +0.241 |
| emg_beta_gamma_fraction | −0.563 | +0.202 |
| emg_index | −0.351 | +0.100 |
| emg_kurtosis | +0.108 | +0.026 |
| exponent_high | +0.568 | +0.166 |
| exponent_low | +0.342 | +0.109 |
| lempel_ziv | −0.846 | +0.256 |
| multiscale_entropy_slope | +1.088 | +0.270 |
| pac_slow_alpha | +0.487 | +0.151 |
| relative_alpha_power | +0.027 | +0.025 |
| relative_delta_power | +0.203 | +0.058 |
| spectral_edge_95 | −0.433 | +0.153 |
| spectral_entropy | −0.230 | +0.086 |
| whole_head_exponent | +0.905 | +0.269 |

*(`spatial_participation_ratio`, `uce_v1`, `wpli_alpha` all-NaN here — see §3, §6.)*

</details>

<details><summary><b>ds004541</b> (awake vs anaesthetised, n=69/41) — click to expand</summary>

| column | d | auc−0.5 |
|---|---:|---:|
| critical_slowing_ar1 | +0.311 | +0.097 |
| emg_beta_gamma_fraction | −0.751 | +0.206 |
| emg_index | +0.029 | +0.011 |
| emg_kurtosis | +0.072 | +0.084 |
| exponent_high | +0.610 | +0.166 |
| exponent_low | +0.086 | +0.016 |
| lempel_ziv | −0.061 | +0.021 |
| multiscale_entropy_slope | +0.835 | +0.220 |
| pac_slow_alpha | +0.274 | +0.088 |
| relative_alpha_power | −0.199 | +0.050 |
| relative_delta_power | +0.107 | +0.027 |
| spatial_participation_ratio | +0.373 | +0.118 |
| spectral_edge_95 | +0.045 | +0.013 |
| spectral_entropy | −0.087 | +0.014 |
| uce_v1 | +1.347 | +0.329 |
| whole_head_exponent | +0.975 | +0.277 |
| wpli_alpha | −0.242 | +0.042 |

</details>

<details><summary><b>ds005620</b> (awake vs anaesthetised, n=59/143) — click to expand</summary>

| column | d | auc−0.5 |
|---|---:|---:|
| lempel_ziv | +1.016 | +0.279 |
| relative_alpha_power | +0.559 | +0.218 |
| relative_delta_power | −0.329 | +0.074 |
| spectral_edge_95 | −0.214 | +0.059 |
| spectral_entropy | +0.069 | +0.016 |
| uce_v1 | +0.497 | +0.162 |
| whole_head_exponent | +0.474 | +0.154 |
| wpli_alpha | +0.504 | +0.148 |

*(ds005620's extracted panel carries only these 8 candidate columns.)*

</details>

**Observation without a verdict:** every deposit has real within-deposit signal on most columns — the state
labels are not vacuous anywhere. `sleep_edfx` (2-channel PSG, N3 is unambiguous slow-wave sleep) has by far
the largest within-deposit effect sizes of any deposit (several \|d\| > 3); `chennu`, `ds004541`, `vitaldb`
and `ds005620` — all lighter, graded or intraoperative contrasts — sit mostly in the \|d\| 0.1–1.5 range.

---

## 5. (b) BETWEEN-deposit shift of the awake state (reference = sleep_edfx `W`)

Same Cohen's-*d* units as (a): pooled-SD standardised difference, signed **(deposit's awake) − (sleep_edfx's
awake)**. vitaldb excluded per §2.

<details><summary><b>sleep_edfx(W) vs capslpdb(awake)</b> — click to expand</summary>

| column | shift | n_ref | n_dep |
|---|---:|---:|---:|
| lempel_ziv | −0.090 | 142 | 106 |
| relative_alpha_power | +0.808 | 142 | 106 |
| relative_delta_power | −0.816 | 142 | 106 |
| spectral_edge_95 | −1.021 | 142 | 106 |
| spectral_entropy | +0.219 | 142 | 106 |
| whole_head_exponent | +1.410 | 142 | 106 |

</details>

<details><summary><b>sleep_edfx(W) vs chennu(awake)</b> — click to expand</summary>

| column | shift | n_ref | n_dep |
|---|---:|---:|---:|
| critical_slowing_ar1 | +4.226 | 142 | 20 |
| emg_beta_gamma_fraction | −1.217 | 142 | 20 |
| emg_index | −2.215 | 142 | 20 |
| emg_kurtosis | −0.778 | 141 | 20 |
| exponent_high | +4.425 | 142 | 20 |
| exponent_low | −1.092 | 142 | 20 |
| lempel_ziv | +0.554 | 142 | 20 |
| multiscale_entropy_slope | +3.640 | 142 | 20 |
| pac_slow_alpha | +0.539 | 142 | 20 |
| relative_alpha_power | +3.508 | 142 | 20 |
| relative_delta_power | −1.787 | 142 | 20 |
| spatial_participation_ratio | −5.295 | 141 | 20 |
| spectral_edge_95 | −1.209 | 142 | 20 |
| spectral_entropy | +0.346 | 142 | 20 |
| whole_head_exponent | +1.801 | 142 | 20 |
| wpli_alpha | +0.714 | 141 | 20 |

*(`uce_v1` excluded — all-NaN in sleep_edfx, §3.)*

</details>

<details><summary><b>sleep_edfx(W) vs ds004541(awake)</b> — click to expand</summary>

| column | shift | n_ref | n_dep |
|---|---:|---:|---:|
| critical_slowing_ar1 | +1.928 | 142 | 69 |
| emg_beta_gamma_fraction | −1.049 | 142 | 69 |
| emg_index | −3.751 | 142 | 69 |
| emg_kurtosis | −1.083 | 141 | 69 |
| exponent_high | +1.889 | 142 | 69 |
| exponent_low | +1.370 | 142 | 69 |
| lempel_ziv | −2.698 | 142 | 69 |
| multiscale_entropy_slope | +1.271 | 142 | 69 |
| pac_slow_alpha | **+19.528** | 142 | 69 |
| relative_alpha_power | −0.836 | 142 | 69 |
| relative_delta_power | +1.169 | 142 | 69 |
| spatial_participation_ratio | −6.136 | 141 | 69 |
| spectral_edge_95 | −2.096 | 142 | 69 |
| spectral_entropy | −2.624 | 142 | 69 |
| whole_head_exponent | +2.683 | 142 | 69 |
| wpli_alpha | +0.946 | 141 | 69 |

*(`uce_v1` excluded — all-NaN in sleep_edfx, §3.)*

</details>

<details><summary><b>sleep_edfx(W) vs ds005620(awake)</b> — click to expand</summary>

| column | shift | n_ref | n_dep |
|---|---:|---:|---:|
| lempel_ziv | −1.955 | 142 | 59 |
| relative_alpha_power | +0.621 | 142 | 59 |
| relative_delta_power | −0.411 | 142 | 59 |
| spectral_edge_95 | −0.696 | 142 | 59 |
| spectral_entropy | −0.003 | 142 | 59 |
| whole_head_exponent | +0.695 | 142 | 59 |
| wpli_alpha | +0.441 | 141 | 59 |

*(`uce_v1` excluded — all-NaN in sleep_edfx, §3.)*

</details>

**Flagged separately, not folded into the ranking below:** `pac_slow_alpha`'s shift of **+19.5** and
`spatial_participation_ratio`'s shifts of −5.3 / −6.1 are not ordinary "large effects" — see §7. Measured
directly: sleep_edfx's `pac_slow_alpha` sits at mean 0.0011 (sd 0.0010, n=142) while ds004541's sits at mean
0.260 (sd 0.023, n=69), a **~236× mean ratio and ~24× sd ratio**. `spatial_participation_ratio` similarly:
sleep_edfx mean 0.667 (sd 0.125) against ds004541 mean 0.037 (sd 0.011) and chennu mean 0.046 (sd 0.013) — an
~18× scale gap that tracks the channel-count gap in §3 (2 vs 62 vs 91 channels) far more plausibly than it
tracks wakefulness.

---

## 6. Excluded columns (never scored, per rule 74)

### (a) within-deposit
| deposit | column | reason |
|---|---|---|
| sleep_edfx | uce_v1 | all-NaN (0 of 709 status=ok rows finite) |
| vitaldb | spatial_participation_ratio | all-NaN (0 of 6,439 finite) |
| vitaldb | uce_v1 | all-NaN (0 of 6,439 finite) |
| vitaldb | wpli_alpha | all-NaN (0 of 6,439 finite) |

### (b) between-deposit
| deposit | column | reason |
|---|---|---|
| chennu | uce_v1 | reference (sleep_edfx) awake group empty for this column |
| ds004541 | uce_v1 | reference (sleep_edfx) awake group empty for this column |
| ds005620 | uce_v1 | reference (sleep_edfx) awake group empty for this column |
| vitaldb | (all columns) | no genuine awake state in this deposit (§2) |

No column was constant across both compared states (the other exclusion reason the code checks for) in any
deposit pairing tested.

---

## 7. (c) the ratio — the number the challenge turns on

`ratio = |b| / mean(|a_ref (sleep_edfx)|, |a_dep|)`. Sorted ascending — **small is good** (the awake-state
shift is small relative to the signal a within-deposit contrast can produce). 45 column×deposit cells were
scored (vitaldb excluded per §2; `uce_v1` excluded per §6).

| deposit | column | a(sleep_edfx) | a(dep) | b (shift) | **ratio (c)** |
|---|---|---:|---:|---:|---:|
| ds005620 | spectral_entropy | −2.665 | +0.069 | −0.003 | **0.002** |
| capslpdb | lempel_ziv | −2.882 | −1.290 | −0.090 | **0.043** |
| capslpdb | spectral_entropy | −2.665 | −1.336 | +0.219 | **0.109** |
| chennu | spectral_entropy | −2.665 | +0.766 | +0.346 | **0.202** |
| ds005620 | whole_head_exponent | +4.673 | +0.474 | +0.695 | 0.270 |
| chennu | lempel_ziv | −2.882 | +1.084 | +0.554 | 0.279 |
| ds005620 | spectral_edge_95 | −3.854 | −0.214 | −0.696 | 0.342 |
| ds005620 | relative_delta_power | +1.973 | −0.329 | −0.411 | 0.357 |
| capslpdb | spectral_edge_95 | −3.854 | −1.252 | −1.021 | 0.400 |
| chennu | exponent_low | +3.620 | −1.353 | −1.092 | 0.439 |
| capslpdb | whole_head_exponent | +4.673 | +1.191 | +1.410 | 0.481 |
| capslpdb | relative_delta_power | +1.973 | +1.417 | −0.816 | 0.481 |
| ds004541 | multiscale_entropy_slope | +4.407 | +0.835 | +1.271 | 0.485 |
| ds005620 | wpli_alpha | +1.124 | +0.504 | +0.441 | 0.542 |
| chennu | spectral_edge_95 | −3.854 | +0.338 | −1.209 | 0.577 |
| ds004541 | emg_beta_gamma_fraction | −2.607 | −0.751 | −1.049 | 0.625 |
| chennu | whole_head_exponent | +4.673 | −0.340 | +1.801 | 0.718 |
| chennu | emg_beta_gamma_fraction | −2.607 | +0.765 | −1.217 | 0.722 |
| ds004541 | exponent_low | +3.620 | +0.086 | +1.370 | 0.740 |
| chennu | pac_slow_alpha | −0.530 | −0.761 | +0.539 | 0.836 |
| ds004541 | critical_slowing_ar1 | +3.960 | +0.311 | +1.928 | 0.903 |
| ds004541 | whole_head_exponent | +4.673 | +0.975 | +2.683 | 0.950 |
| ds005620 | relative_alpha_power | −0.694 | +0.559 | +0.621 | 0.992 |
| ds005620 | lempel_ziv | −2.882 | +1.016 | −1.955 | 1.003 |
| chennu | emg_kurtosis | −0.974 | −0.518 | −0.778 | 1.044 |
| ds004541 | spectral_edge_95 | −3.854 | +0.045 | −2.096 | 1.075 |
| capslpdb | relative_alpha_power | −0.694 | −0.751 | +0.808 | 1.118 |
| ds004541 | relative_delta_power | +1.973 | +0.107 | +1.169 | 1.124 |
| chennu | wpli_alpha | +1.124 | −0.114 | +0.714 | 1.153 |
| chennu | multiscale_entropy_slope | +4.407 | −1.721 | +3.640 | 1.188 |
| ds004541 | wpli_alpha | +1.124 | −0.242 | +0.946 | 1.386 |
| chennu | relative_delta_power | +1.973 | −0.489 | −1.787 | 1.451 |
| chennu | emg_index | −2.771 | −0.206 | −2.215 | 1.488 |
| ds004541 | lempel_ziv | −2.882 | −0.061 | −2.698 | 1.833 |
| ds004541 | relative_alpha_power | −0.694 | −0.199 | −0.836 | 1.871 |
| ds004541 | exponent_high | +1.401 | +0.610 | +1.889 | 1.879 |
| ds004541 | spectral_entropy | −2.665 | −0.087 | −2.624 | 1.907 |
| chennu | critical_slowing_ar1 | +3.960 | −0.215 | +4.226 | 2.025 |
| ds004541 | emg_kurtosis | −0.974 | +0.072 | −1.083 | 2.071 |
| ds004541 | emg_index | −2.771 | +0.029 | −3.751 | 2.679 |
| chennu | exponent_high | +1.401 | +1.565 | +4.425 | 2.984 |
| chennu | relative_alpha_power | −0.694 | −0.494 | +3.508 | 5.907 |
| ds004541 | spatial_participation_ratio | +0.482 | +0.373 | −6.136 | 14.353 |
| chennu | spatial_participation_ratio | +0.482 | +0.177 | −5.295 | 16.083 |
| ds004541 | pac_slow_alpha | −0.530 | +0.274 | +19.528 | 48.595 |

---

## 8. Columns with (c) < 0.25 — the candidate transportable measures

**Four cells clear (c) < 0.25:**

| deposit pair | column | ratio |
|---|---|---:|
| sleep_edfx vs ds005620 | **spectral_entropy** | 0.002 |
| sleep_edfx vs capslpdb | **lempel_ziv** | 0.043 |
| sleep_edfx vs capslpdb | **spectral_entropy** | 0.109 |
| sleep_edfx vs chennu | **spectral_entropy** | 0.202 |

**`spectral_entropy` clears the bar against three of the four comparable deposits** (capslpdb, chennu,
ds005620) — the only column that does so more than once. It misses only against ds004541, where it scores
1.907 (§7) — the highest ratio ds004541 produces for any column other than the two flagged as scale-mismatch
artefacts (§7, §9). **`lempel_ziv`** clears the bar against capslpdb (0.043) but scores 0.279–1.833 against
the other three deposits — it is not a general pass, it is one strong cell.

No column clears (c) < 0.25 against **both** ds004541 and chennu simultaneously; no column clears it against
**every** deposit it was scored on.

---

## 9. Scale-mismatch caveat, separate from the ranking

Three cells in §7 (`pac_slow_alpha` at ratio 48.6, `spatial_participation_ratio` at 14.4 and 16.1) are not read as
"this measure fails to transport" in the ordinary sense. Cohen's-*d* assumes the two groups have comparable
variance; here they do not — sleep_edfx's `pac_slow_alpha` sd is ~24× smaller than ds004541's, and
`spatial_participation_ratio`'s scale gap tracks the channel-count gap in §3 almost exactly (2 vs
62/91 channels, ~18× value gap). **These two ratios describe a probable measurement/montage-scale mismatch,
not a graded "harder to transport"** — they are reported because the ratio computation makes no exception for
them, and flagging them here is what stops that computation from being read as "these are just the two worst
cases on a continuum with everything else."

---

## 10. Plain statement

- **Every deposit's state labels carry real within-deposit signal** (§4) — none of the six extreme-state
  contrasts is degenerate.
- **The between-deposit awake-state shift (§5) is large relative to that signal for most columns**: of 42
  scored cells excluding the three flagged scale-mismatch cells (§9), **33 have ratio ≥ 0.4** and **19 have
  ratio ≥ 1.0** (the awake-vs-awake shift alone is as large as, or larger than, the deposit's own state
  contrast).
- **`spectral_entropy` is the standout**: ratio 0.002 (vs ds005620), 0.109 (vs capslpdb) and 0.202 (vs
  chennu) — three of four comparisons under 0.25 — though it does not clear the bar against ds004541
  (ratio 1.907).
- **`lempel_ziv` clears the bar once** (vs capslpdb, 0.043) but not against chennu or ds004541.
- **Channel count is a confound named but not adjusted for anywhere in this codebase** (§3): it ranges 1–91
  across the six deposits, and at least `spatial_participation_ratio` (and plausibly `wpli_alpha`, `uce_v1`)
  is a likely casualty of that rather than of population or state.
- **Population differs alongside device on every pairing**: sleep_edfx (healthy, ambulatory, asleep) vs
  capslpdb (sleep-clinic referrals, mostly pathological) vs chennu (healthy, task-engaged under the drug) vs
  ds004541 (healthy, resting, propofol induction) vs ds005620 (healthy, TMS-EEG) vs vitaldb (surgical
  patients, intraoperative only, excluded from this section). No covariate adjustment for any of this exists
  in the loaders above; it is stated as a limitation, not solved.

No verdict about Challenge D is drawn here, per the task's instruction.

---

## 11. OPUS VERIFICATION, 2026-08-02 — two of the four sub-0.25 cells are artefacts of the ratio metric

Recomputed independently from `sleep_edfx_five_stage.csv` and `capslpdb_stages.s*.csv`, parsing the stage
out of `recording_id` as a field (`split('@')[-1]`) rather than substring-matching it (rule 61):

| pair | sleep_edfx d | target d | same sign | awake-vs-awake shift | ratio |
|---|---:|---:|:--:|---:|---:|
| `spectral_entropy`, capslpdb | −2.6681 | −1.2815 | YES | +0.2514 | **0.1273** |
| `lempel_ziv`, capslpdb | −2.8864 | −1.2521 | YES | −0.1070 | **0.0517** |

Those reproduce §7 to within rounding (0.109 and 0.043 there) and they stand.

**The other two do not, and the ratio cannot see why.** `ratio = |b| / mean(|a_ref|, |a_dep|)` is small
when the shift is small *or* when either deposit's own contrast is large — and it is blind to the SIGN of
`a_dep`:

* **`spectral_entropy` vs chennu, ratio 0.202.** `a_ref = −2.665` against `a_dep = **+0.766**`. The measure
  falls with depth in sleep and RISES with depth under sedation. Catalogue rule 16: when two arms of the
  same test disagree in sign, the definition is doing the work. A reversing measure has not transported.
* **`spectral_entropy` vs ds005620, ratio 0.002.** `a_dep = **+0.069**` — no state signal in the target
  deposit at all, so there is nothing for a shift to be small *relative to*. Rule 53: the phenomenon must
  exist in the cohort you are asking about before "it agrees there" means anything. A dead measure
  transports perfectly and is worthless.

**Corrected reading.** Transport succeeds **within a modality and fails across one**. Both surviving cells
are sleep-deposit-to-sleep-deposit (Sleep-EDFx W/N3 against CAP W/S3+S4) — the same state contrast in
similar populations, which is the easy case. Every sleep-to-anaesthesia cell is either large (ratio ≥ 0.27)
or a sign reversal. That is a sharper statement of Challenge D than "45 cells, 4 winners", and it is worse
news: the transport that a deployable index needs is exactly the one that fails.

**Method note for successors.** A transport ratio must be gated on the TARGET deposit's own effect —
require `|a_dep|` above a floor and `sign(a_dep) == sign(a_ref)` before the ratio is computed at all.
Without that gate the metric ranks dead and reversed measures at the top, which is what happened here.

---

## 12. Gated re-ranking (Task 1) and within-subject referencing (Task 2), 2026-08-02

*DIAGNOSTIC follow-up, same status as §0: no ledger row, no registration file, no verdict about
Challenge D. Script: `/tmp/.../scratchpad/probe_gate_and_withinsubj.py` (this session only),
reusing `probe_separability.py`'s loaders unchanged and importing `bsde.verifier.stats.read_rows`
rather than reimplementing it (rule 20).*

### 12.1 Task 1 — gate applied to the 45-cell ratio table

Gate, applied per cell, **ratio definition unchanged**:
(i) `|a_dep| >= 0.5` (rule 53 — the target deposit must actually carry the effect);
(ii) `sign(a_dep) == sign(a_ref)` (rule 16 — a reversal is not transport).

**14 of 45 cells survive both gates.** Sorted ascending:

| deposit | column | a(sleep_edfx) | a(dep) | b (shift) | ratio |
|---|---|---:|---:|---:|---:|
| capslpdb | lempel_ziv | −2.882 | −1.290 | −0.090 | **0.043** |
| capslpdb | spectral_entropy | −2.665 | −1.336 | +0.219 | **0.109** |
| capslpdb | spectral_edge_95 | −3.854 | −1.252 | −1.021 | 0.400 |
| capslpdb | whole_head_exponent | +4.673 | +1.191 | +1.410 | 0.481 |
| capslpdb | relative_delta_power | +1.973 | +1.417 | −0.816 | 0.481 |
| ds004541 | multiscale_entropy_slope | +4.407 | +0.835 | +1.271 | 0.485 |
| ds005620 | wpli_alpha | +1.124 | +0.504 | +0.441 | 0.542 |
| ds004541 | emg_beta_gamma_fraction | −2.607 | −0.751 | −1.049 | 0.625 |
| chennu | pac_slow_alpha | −0.530 | −0.761 | +0.539 | 0.836 |
| ds004541 | whole_head_exponent | +4.673 | +0.975 | +2.683 | 0.950 |
| chennu | emg_kurtosis | −0.974 | −0.518 | −0.778 | 1.044 |
| capslpdb | relative_alpha_power | −0.694 | −0.751 | +0.808 | 1.118 |
| ds004541 | exponent_high | +1.401 | +0.610 | +1.889 | 1.879 |
| chennu | exponent_high | +1.401 | +1.565 | +4.425 | 2.984 |

**Every surviving cell is either capslpdb (sleep-clinic PSG, same modality as the sleep_edfx
reference — 6 of 14) or a cross-modality cell whose ratio is ≥ 0.485 (8 of 14, none below the
original 0.25 bar).** This confirms §11's reading with the full table rather than four cherry-picked
cells: gating removes both artefacts §11 flagged (`spectral_entropy` vs ds005620 — dead in the target,
`a_dep`=+0.069 — and `spectral_entropy` vs chennu — reversed, `a_dep`=+0.766) and they do not
reappear; nothing cross-modality clears 0.25 once the gate is applied.

**31 of 45 cells refused.** Refusal-reason tally: **12 failed on magnitude alone** (`|a_dep| < 0.5`),
**7 failed on sign alone**, **12 failed on both**. Full list, sorted by deposit then column:

| deposit | column | a(sleep_edfx) | a(dep) | b (shift) | ratio | reason(s) refused |
|---|---|---:|---:|---:|---:|---|
| chennu | critical_slowing_ar1 | +3.960 | −0.215 | +4.226 | 2.025 | \|a_dep\|<0.5; sign mismatch |
| chennu | emg_beta_gamma_fraction | −2.607 | +0.765 | −1.217 | 0.722 | sign mismatch |
| chennu | emg_index | −2.771 | −0.206 | −2.215 | 1.488 | \|a_dep\|<0.5 |
| chennu | exponent_low | +3.620 | −1.353 | −1.092 | 0.439 | sign mismatch |
| chennu | lempel_ziv | −2.882 | +1.084 | +0.554 | 0.279 | sign mismatch |
| chennu | multiscale_entropy_slope | +4.407 | −1.721 | +3.640 | 1.188 | sign mismatch |
| chennu | relative_alpha_power | −0.694 | −0.494 | +3.508 | 5.907 | \|a_dep\|<0.5 |
| chennu | relative_delta_power | +1.973 | −0.489 | −1.787 | 1.451 | \|a_dep\|<0.5; sign mismatch |
| chennu | spatial_participation_ratio | +0.482 | +0.177 | −5.295 | 16.083 | \|a_dep\|<0.5 |
| chennu | spectral_edge_95 | −3.854 | +0.338 | −1.209 | 0.577 | \|a_dep\|<0.5; sign mismatch |
| chennu | spectral_entropy | −2.665 | +0.766 | +0.346 | 0.202 | sign mismatch |
| chennu | whole_head_exponent | +4.673 | −0.340 | +1.801 | 0.718 | \|a_dep\|<0.5; sign mismatch |
| chennu | wpli_alpha | +1.124 | −0.114 | +0.714 | 1.153 | \|a_dep\|<0.5; sign mismatch |
| ds004541 | critical_slowing_ar1 | +3.960 | +0.311 | +1.928 | 0.903 | \|a_dep\|<0.5 |
| ds004541 | emg_index | −2.771 | +0.029 | −3.751 | 2.679 | \|a_dep\|<0.5; sign mismatch |
| ds004541 | emg_kurtosis | −0.974 | +0.072 | −1.083 | 2.071 | \|a_dep\|<0.5; sign mismatch |
| ds004541 | exponent_low | +3.620 | +0.086 | +1.370 | 0.740 | \|a_dep\|<0.5 |
| ds004541 | lempel_ziv | −2.882 | −0.061 | −2.698 | 1.833 | \|a_dep\|<0.5 |
| ds004541 | pac_slow_alpha | −0.530 | +0.274 | +19.528 | 48.595 | \|a_dep\|<0.5; sign mismatch |
| ds004541 | relative_alpha_power | −0.694 | −0.199 | −0.836 | 1.871 | \|a_dep\|<0.5 |
| ds004541 | relative_delta_power | +1.973 | +0.107 | +1.169 | 1.124 | \|a_dep\|<0.5 |
| ds004541 | spatial_participation_ratio | +0.482 | +0.373 | −6.136 | 14.353 | \|a_dep\|<0.5 |
| ds004541 | spectral_edge_95 | −3.854 | +0.045 | −2.096 | 1.075 | \|a_dep\|<0.5; sign mismatch |
| ds004541 | spectral_entropy | −2.665 | −0.087 | −2.624 | 1.907 | \|a_dep\|<0.5 |
| ds004541 | wpli_alpha | +1.124 | −0.242 | +0.946 | 1.386 | \|a_dep\|<0.5; sign mismatch |
| ds005620 | lempel_ziv | −2.882 | +1.016 | −1.955 | 1.003 | sign mismatch |
| ds005620 | relative_alpha_power | −0.694 | +0.559 | +0.621 | 0.992 | sign mismatch |
| ds005620 | relative_delta_power | +1.973 | −0.329 | −0.411 | 0.357 | \|a_dep\|<0.5; sign mismatch |
| ds005620 | spectral_edge_95 | −3.854 | −0.214 | −0.696 | 0.342 | \|a_dep\|<0.5 |
| ds005620 | spectral_entropy | −2.665 | +0.069 | −0.003 | 0.002 | \|a_dep\|<0.5; sign mismatch |
| ds005620 | whole_head_exponent | +4.673 | +0.474 | +0.695 | 0.270 | \|a_dep\|<0.5 |

### 12.2 Task 2 — within-subject referencing

**Method.** For each of the five deposits with repeated states per subject (sleep_edfx, capslpdb,
chennu, ds004541, ds005620), every candidate is re-expressed as one number per subject:
`ref = (that subject's own deep-state mean) − (that same subject's own awake-state mean)`.
On that per-subject delta:
(a) within-deposit effect = **paired Cohen's dz** = `mean(diff) / sd(diff)` (one-sample, not the
original two-sample pooled-SD d — averaging out between-subject variance is the entire point of
referencing);
(b) between-deposit shift = **the same two-sample `cohen_d()`** used everywhere else in this probe,
applied to the two deposits' per-subject delta *distributions* (sleep_edfx's own N3−W delta vs the
target deposit's own deep−awake delta) rather than to raw awake values;
(c) ratio = `|b| / mean(|a_ref|, |a_dep|)` — identical formula, unchanged.

vitaldb has no awake anchor (§2) and is reported for (a) only, informationally, using its
"lightest-recorded" state as the anchor per the task's own allowance ("or lightest available") — it
does **not** enter the between-deposit comparison, for the same structural reason it did not in Task 1.

**Rule 73 (no separate-group normalisation).** The subtraction is per **individual** (each subject's
own two states), computed in `subject_level()` / `load_ds005620_by_subject()`
(`probe_gate_and_withinsubj.py` lines ~95–150) — no deposit-level or group-level mean or scale is
touched anywhere in that code path, so it does not annihilate the between-deposit contrast the way a
per-group z-score would.

**Rule 5/14 — subject coverage, asserted and reported, not silently dropped:**

| deposit | subjects w/ awake | subjects w/ deep | BOTH (used) | missing (reported) |
|---|---:|---:|---:|---|
| sleep_edfx | 142 | 141 | **141** | `SC4531E0-PSG` (has N1/N2/REM/W, no N3) |
| capslpdb | 106 | 106 | **106** | none |
| chennu | 20 | 20 | **20** | none |
| ds004541 | 8 | 7 | **7** | `sub-11` (awake only) |
| ds005620 | 21 | 20 | **20** | `sub-1037` (awake only) |
| vitaldb (informational) | 213 | 156 | **132** | 81 lightest-only cases, 24 deepest-only cases (both listed in the script's stdout, e.g. `104,106,107,…` / `101,12,126,…`) |

**ds004541's paired analysis runs on n=7 subjects, not the n=69/41 windows §4 reports** — the raw
table has multiple windows per subject, and referencing collapses them to one subject-level value
per state before differencing. That is a real loss of resolution and the widest dz's below should be
read with n=7 in mind.

**Rule 74 — all-NaN/constant columns, excluded not scored:** `sleep_edfx.uce_v1`,
`vitaldb.spatial_participation_ratio`, `vitaldb.uce_v1`, `vitaldb.wpli_alpha` — all four `EXCLUDED:
n too small after per-subject pairing (n=0)`, the same all-NaN columns §3/§6 already excluded. No
column was constant (nonzero n, zero variance) after pairing.

**Before/after, on the 14 cells that were gated in Task 1** (ratio unchanged in definition, both
computed the same way otherwise):

| deposit | column | ratio BEFORE | ratio AFTER | change |
|---|---|---:|---:|---|
| capslpdb | relative_alpha_power | 1.118 | **0.240** | IMPROVED (−0.878) |
| capslpdb | relative_delta_power | 0.481 | 0.309 | IMPROVED (−0.172) |
| chennu | exponent_high | 2.984 | 0.321 | IMPROVED (−2.663) |
| chennu | pac_slow_alpha | 0.836 | 0.251 | IMPROVED (−0.586) |
| ds004541 | exponent_high | 1.879 | 0.741 | IMPROVED (−1.137) |
| capslpdb | lempel_ziv | 0.043 | 0.910 | WORSENED (+0.867) |
| capslpdb | spectral_edge_95 | 0.400 | 0.932 | WORSENED (+0.532) |
| capslpdb | spectral_entropy | 0.109 | 0.798 | WORSENED (+0.689) |
| capslpdb | whole_head_exponent | 0.481 | 0.824 | WORSENED (+0.343) |
| chennu | emg_kurtosis | 1.044 | 1.310 | WORSENED (+0.267) |
| ds004541 | emg_beta_gamma_fraction | 0.625 | 1.111 | WORSENED (+0.486) |
| ds004541 | multiscale_entropy_slope | 0.485 | 1.258 | WORSENED (+0.773) |
| ds004541 | whole_head_exponent | 0.950 | 1.320 | WORSENED (+0.370) |
| ds005620 | wpli_alpha | 0.542 | 0.995 | WORSENED (+0.453) |

**Tally: 5 improved, 9 worsened, 0 unchanged, of 14.** Split by whether the cell is same-modality
(capslpdb, sleep-vs-sleep) or cross-modality (chennu/ds004541/ds005620, sleep-vs-anaesthesia — the
transport a deployable index actually needs, per the task):

- **Same-modality (capslpdb, 6 cells): 2 improved, 4 worsened.**
- **Cross-modality (8 cells): 3 improved** (`chennu.exponent_high` 2.984→0.321,
  `chennu.pac_slow_alpha` 0.836→0.251, `ds004541.exponent_high` 1.879→0.741),
  **5 worsened** (`ds004541.multiscale_entropy_slope`, `ds004541.emg_beta_gamma_fraction`,
  `ds004541.whole_head_exponent`, `chennu.emg_kurtosis`, `ds005620.wpli_alpha`).

**The improvement rate is not meaningfully different between same- and cross-modality (33% vs 38%),
but the DESTINATION is**: referencing produces exactly **one** cell anywhere below the 0.25 bar after
gating — `capslpdb.relative_alpha_power` at 0.240 — and it is same-modality (sleep-vs-sleep). **No
cross-modality cell reaches 0.25 either before or after referencing**; the closest is
`chennu.pac_slow_alpha` at 0.251, one thousandth away from the bar and still carrying the scale-mismatch
caveat §9 raised for `pac_slow_alpha` generally (a ~236× mean-scale gap between sleep_edfx's and
ds004541's raw values makes any pooled-SD statistic on that column suspect regardless of referencing;
this same-column risk was not separately re-checked for the chennu pairing here and is flagged, not
resolved).

**Applying the SAME two-part gate (§12.1's rule 53 + rule 16 criteria, magnitude and sign only — no
ratio threshold) to the referenced quantities themselves**, across all 45 originally-scored
deposit×column combinations recomputed under referencing: **16 of 45 pass** (vs 14 of 45 before
referencing). All 6 capslpdb cells that passed before still pass after (unsurprising — capslpdb's
per-subject pairing is closest to a like-for-like reduction of the same test). **Of the 8
cross-modality cells that passed the sign/magnitude gate before, 6 still pass it after** —
`chennu.exponent_high`, `chennu.pac_slow_alpha`, `ds004541.emg_beta_gamma_fraction`,
`ds004541.exponent_high`, `ds004541.multiscale_entropy_slope`, `ds004541.whole_head_exponent` — and 2
now fail (`chennu.emg_kurtosis`: dz_ref −0.751, dz_dep −0.379, below the 0.5 floor;
`ds005620.wpli_alpha`: dz_ref +0.755, dz_dep +0.459, likewise below floor). Four cross-modality cells
newly pass that had failed pre-referencing — `ds004541.critical_slowing_ar1`,
`ds004541.spatial_participation_ratio` (the latter is the channel-count-flagged column from §3, and its
pass here, dz_ref=+0.339/dz_dep=+0.709, should be read with that confound in mind, not as a clean
transport success), `ds005620.spectral_edge_95` and `ds005620.whole_head_exponent` — giving **10 of the
39 cross-modality cells passing sign+magnitude after referencing, against 8 before.**
**This is the split worth naming precisely: referencing leaves MORE cross-modality cells with a
correctly-signed, non-trivial state effect (10 vs 8) — but the ratio computed from those same cells
does not improve on the whole (§12.2's tally: 3 improved, 5 worsened among the original 8), and not one
of them, before or after, reaches the 0.25 deployability bar.** Passing the sign/magnitude gate answers
"does the state effect still exist and point the right way"; it does not answer "is the between-deposit
offset small relative to it", which is what the ratio measures and what actually matters for transport.

### 12.3 Plain statement

- **Within-subject referencing does not rescue cross-modality transport at the deployability bar
  used throughout this probe (ratio < 0.25).** Zero cross-modality cells clear it before referencing;
  zero clear it after. The nearest miss, `chennu.pac_slow_alpha` at 0.251, carries an independent
  scale-mismatch flag on that same column from §9.
- **Referencing helps some cells and hurts more of them**, in both the same-modality and
  cross-modality groups: 5 improved against 9 worsened overall (2 vs 4 same-modality, 3 vs 5
  cross-modality) — there is no clear directional benefit, and the one cell that crossed the bar
  (`capslpdb.relative_alpha_power`, 1.118→0.240) is the easy sleep-vs-sleep case, not a
  sleep-vs-anaesthesia one.
- **The state signal itself does not survive referencing intact in most cross-modality cells**: of
  the 8 originally-gated cross-modality cells, the *within-deposit* paired dz (`a_dep` in the new
  units) drops noticeably for several — e.g. `ds004541.multiscale_entropy_slope` +0.835→+1.149 (paired
  dz rose here, on n=7), `ds004541.whole_head_exponent` +0.975→+1.247 (also rose) — but per-subject
  pairing simultaneously changed sleep_edfx's own reference dz for several columns in ways that moved
  the RATIO the wrong direction even where the deposit's own signal held or grew, because the
  between-deposit shift (b) also changed under referencing and did not shrink proportionally.
- **ds004541's referenced numbers rest on n=7 subjects** (not the 69/41 windows the raw table
  reports), because referencing collapses repeated within-subject windows to one value per subject
  per state before differencing — a real resolution cost worth weighing against any apparent
  improvement there (e.g. `ds004541.exponent_high` 1.879→0.741 is built on 7 paired subjects).

No verdict about Challenge D is drawn here, per the task's instruction.
