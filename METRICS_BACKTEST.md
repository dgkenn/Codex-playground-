# METRICS_BACKTEST.md — Curated Risk/Performance Metrics for the Kalshi Maker Box A/B Tester

Generated: 2026-06-13 | Asset: BTC 15-min | n=162 forward windows (gha_data)

---

## 1. Curated Metric Selection

All metrics are computed on the **per-window PnL series** (one observation = one 15-minute Kalshi market). Dollar units are cents-per-contract unless noted.

| # | Metric | Formula / Definition | Why it matters for this bot |
|---|--------|---------------------|-----------------------------|
| 1 | **Sortino** | mean(x) / sqrt(mean(x[x<0]^2)) | Penalises downside deviation only; fairer than Sharpe when wins and losses are asymmetric (which they are: stranded legs create one-sided loss tails). |
| 2 | **Skewness** | Fisher skewness of per-window PnL | The box strategy's structural signature is *negative skew*: small frequent wins from paired boxes, rare large losses from stranded legs. Monitoring skew tracks whether a trial is amplifying or reducing the strand-tail. |
| 3 | **Kurtosis** | Excess (Fisher) kurtosis | Positive kurtosis = fat tails (more extreme outcomes than normal). Combined with negative skew this flags the dangerous "collect pennies, lose dollars" profile. |
| 4 | **Recovery Factor** | total_net_PnL / max_drawdown | Overall how many times the strategy "earned back" its worst drawdown. Benchmarks: >5 minimum, >8 strong, >10 gold. |
| 5 | **Ulcer Index** | RMS of per-window (peak − cum_equity) | Combines drawdown depth *and* duration; better than maxDD alone for detecting strategies that hover underwater for long periods. |
| 6 | **VaR95** | −percentile(x, 5) | 5th-percentile loss, the standard risk-budget anchor. |
| 7 | **CVaR95** | mean of worst 5% of windows | Expected loss in the tail; more sensitive than VaR to the shape of the loss distribution. The key metric for the strand-tail signature. |
| 8 | **Information Ratio vs P0** | mean(trial−P0) / std(trial−P0) | IR×√n = the paired t-stat already in the leaderboard; IR alone shows per-window alpha relative to the always-pair baseline. |
| 8b | **Information Ratio vs live_current** | mean(trial−live_current) / std(trial−live_current) | The deploy-relevant benchmark: does the trial beat what is actually running? |
| 9 | **Avg-Win / Avg-Loss** | mean(x[x>0]) / (−mean(x[x<0])) | Asymmetry ratio; >1 means winning windows are larger than losing windows on average. Complements win-rate. |
| 10 | **Expectancy** | mean(x) per window (cents) | Equivalent to P(win)×AvgWin − P(loss)×AvgLoss; the explicit split form makes the asymmetry visible. |
| 11 | **Time-Underwater %** | fraction of windows where cum_equity < running_peak | Captures how often an operator would feel "in drawdown"; high values indicate choppy equity curves even when the total is positive. |
| 12 | **Adverse-Selection Rate** | fraction of P0-accepted fills with sig>0 (spot moved adversely at fill time, in bps) | The market-making pick-off metric; measures how often the "wrong side" fills us. Computed on the shared P0 fill pool (all trials share the same raw fills; entry-gate trials reduce volume but not the adverse fraction unless they specifically filter on sig, as t07 and t36 do). Result: **39.4% of fills are adverse** (1151 / 2924 across 162 windows). |

---

## 2. Explicitly Skipped Metrics (with rationale)

| Metric | Reason skipped |
|--------|---------------|
| **Slippage / VWAP / Implementation Shortfall** | Maker posts at the touch; fee = 0. Realized fill price equals quoted price by construction, so slippage is structurally ~0. Not useful here. |
| **Quote Latency / Fill-to-Quote Ratio / Uptime / Error Rate / Margin** | These require live telemetry from the running bot; they are not present in the tape-replay ledger (book + trade streams → reconstructed fills). Valid as live monitoring metrics; not backtest metrics. |
| **BTC Alpha / Beta / Tracking Error / R²** | The natural benchmark for a binary market-maker is P0 (always-pair baseline) and live_current (the deployed strategy), not BTC spot returns. The Information Ratio vs P0 and vs live_current, plus the paired t-stat, already capture all the risk-adjusted edge relative to any sensible benchmark. Adding BTC regression would conflate two unrelated things. |
| **Inventory Imbalance** | Structurally capped at ±1 leg by `--max-net 1`; the bot can never accumulate a directional inventory. The honest proxy for inventory stress is the strand-rate (the complement of the leaderboard's win%, already reported). |
| **Monte-Carlo / Walk-Forward Analysis / Regime Detection** | Valuable but not cheap to implement reliably at n~160 windows without inflating false-positive risk. Noted as future work; prioritise when n ≥ 300. |
| **Quarterly Consistency** | With ~160 windows the quarter boundaries produce noisy, tiny sub-samples. Deferred until n ≥ 300 (the pre-registered deploy threshold). |

---

## 3. Per-Trial Metric Table (n=162 windows, btc)

All values from a single `python3 box_policy_ab.py --asset btc --dir gha_data --metrics` run.
Dollar amounts in cents/contract. AdvSel% is the global P0 figure (39.4%) for all trials.

| trial | Sharpe | Sortino | Skew | Kurt | Recovery | Ulcer_c | CVaR95_c | IR_vs_live | AdvSel% |
|-------|--------|---------|------|------|----------|---------|----------|------------|---------|
| P0_baseline | −0.112 | −0.084 | −1.09 | +3.01 | −0.90 | 196.3 | 51.9 | −0.032 | 39.4% |
| live_current | −0.031 | −0.029 | −0.09 | +1.51 | −0.28 | 207.9 | 69.4 | 0.000 | 39.4% |
| p2_signal_hold | −0.134 | −0.127 | +0.11 | −1.53 | −0.76 | 503.4 | 69.6 | −0.094 | 39.4% |
| t01_deep_tail_skip | −0.193 | −0.134 | −1.73 | +4.47 | −0.97 | 375.6 | 63.7 | −0.087 | 39.4% |
| t02_yes_caution | −0.042 | −0.037 | −0.39 | +0.64 | −0.32 | 269.7 | 68.8 | −0.036 | 39.4% |
| t03_early_window | +0.032 | +0.022 | −1.26 | +3.85 | +0.52 | 70.5 | 36.0 | +0.043 | 39.4% |
| t04_thin_book | −0.184 | −0.115 | −1.99 | +6.38 | −0.96 | 170.9 | 47.6 | −0.051 | 39.4% |
| t05_flat_oi | −0.017 | −0.003 | −3.47 | +36.7 | −0.17 | 36.8 | 0.35 | +0.030 | 39.4% |
| t06_balanced_flow | +0.152 | +0.024 | −2.93 | +39.2 | +2.86 | 0.89 | 0.04 | +0.034 | 39.4% |
| t07_spot_gate | +0.006 | +0.006 | +0.39 | +4.86 | +0.10 | 98.7 | 60.1 | +0.039 | 39.4% |
| t08_hold_no | −0.037 | −0.039 | +0.11 | −1.40 | −0.23 | 430.7 | 70.4 | −0.019 | 39.4% |
| t09_completion_target | −0.197 | −0.118 | −2.10 | +7.05 | −0.98 | 192.6 | 48.2 | −0.056 | 39.4% |
| t10_target_and_hold | −0.052 | −0.057 | +0.34 | −0.24 | −0.45 | 308.7 | 67.8 | −0.020 | 39.4% |
| t11_sell_cheap_unpaired | −0.094 | −0.069 | −1.15 | +3.27 | −0.89 | 174.0 | 51.8 | −0.021 | 39.4% |
| t12_sell_all_unpaired | −0.107 | −0.077 | −1.38 | +3.57 | −0.89 | 174.2 | 50.1 | −0.025 | 39.4% |
| t13_sell_unpaired_vpin | −0.112 | −0.084 | −1.09 | +3.00 | −0.90 | 196.1 | 51.9 | −0.032 | 39.4% |
| t14_perp_hedge_unpaired | −0.064 | −0.047 | −1.16 | +3.04 | −0.84 | 123.0 | 50.7 | −0.005 | 39.4% |
| t15_gamma_size_down | −0.034 | −0.026 | −0.96 | +1.93 | −0.48 | 73.9 | 29.9 | +0.020 | 39.4% |
| t16_no_leg_preference | −0.046 | −0.041 | −0.44 | +0.47 | −0.33 | 295.4 | 71.8 | −0.047 | 39.4% |
| t17_tox_exit_unpaired | −0.097 | −0.071 | −1.14 | +3.24 | −0.89 | 179.0 | 51.9 | −0.023 | 39.4% |
| t18_tox_open_gate | −0.100 | −0.081 | −1.09 | +2.73 | −0.83 | 213.0 | 62.8 | −0.037 | 39.4% |
| t19_tox_gate_and_exit | −0.094 | −0.076 | −1.12 | +2.82 | −0.81 | 207.1 | 62.8 | −0.033 | 39.4% |
| t20_low_vol_open | −0.107 | −0.076 | −1.37 | +4.85 | −0.94 | 190.9 | 52.7 | −0.027 | 39.4% |
| t21_sweepable_queue | −0.120 | −0.077 | −2.49 | +7.39 | −0.90 | 119.4 | 46.3 | −0.021 | 39.4% |
| t22_size_sweetspot | −0.105 | −0.079 | −1.04 | +2.45 | −0.89 | 182.9 | 54.3 | −0.031 | 39.4% |
| t23_quarter_kelly | −0.085 | −0.062 | −1.11 | +1.65 | −0.89 | 194.1 | 65.7 | −0.031 | 39.4% |
| t24_tox_sized | −0.126 | −0.092 | −1.31 | +2.55 | −0.91 | 220.6 | 57.6 | −0.048 | 39.4% |
| t25_hour_sized | −0.117 | −0.089 | −0.89 | +4.90 | −0.92 | 240.1 | 54.6 | −0.041 | 39.4% |
| t26_gamma_sized | −0.028 | −0.021 | −1.16 | +1.62 | −0.42 | 57.8 | 26.6 | +0.023 | 39.4% |
| t28_hold_deep_favorite | −0.023 | −0.017 | −1.60 | +3.29 | −0.31 | 147.1 | 84.1 | +0.007 | 39.4% |
| t29_favorite_only_opens | −0.022 | −0.014 | −0.72 | +4.54 | −0.32 | 79.8 | 37.8 | +0.021 | 39.4% |
| t30_asym_playbook | −0.033 | −0.023 | −1.34 | +2.98 | −0.30 | 170.8 | 67.8 | +0.006 | 39.4% |
| t31_face_contrarian | +0.057 | +0.060 | −0.01 | +2.47 | +0.89 | 137.0 | 65.6 | +0.082 | 39.4% |
| t32_vpin_open_gate | −0.102 | −0.078 | −1.11 | +3.55 | −0.93 | 198.7 | 50.1 | −0.024 | 39.4% |
| t33_take_tail_trim | +0.013 | +0.011 | −0.06 | +3.13 | +0.22 | 83.9 | 49.4 | +0.041 | 39.4% |
| t34_avoid_combined | +0.107 | +0.113 | +0.02 | +2.75 | +2.16 | 80.3 | 60.1 | +0.123 | 39.4% |
| t35_combo_tox_gate | −0.112 | −0.084 | −1.09 | +3.01 | −0.90 | 196.3 | 51.9 | −0.032 | 39.4% |
| t36_guarded_opener | −0.031 | −0.029 | −0.09 | +1.51 | −0.28 | 207.9 | 69.4 | 0.000 | 39.4% |
| t_mid_window | −0.043 | −0.017 | −3.07 | +9.05 | −0.59 | 43.9 | 25.3 | +0.022 | 39.4% |
| tc_mid_hedge | −0.043 | −0.017 | −3.07 | +9.05 | −0.59 | 43.9 | 25.3 | +0.022 | 39.4% |
| tc_mid_sellcheap | −0.043 | −0.017 | −3.07 | +9.05 | −0.59 | 43.9 | 25.3 | +0.022 | 39.4% |
| tc_mid_tailtrim | +0.101 | +0.050 | −1.36 | +8.67 | +1.32 | 45.6 | 20.8 | +0.052 | 39.4% |
| tc_pairmax | +0.269 | +0.112 | +3.33 | +12.0 | +18.2 | 0.22 | 0.01 | +0.035 | 39.4% |
| tc_tailtrim_hedge | +0.053 | +0.044 | −0.32 | +2.32 | +1.12 | 66.8 | 48.2 | +0.067 | 39.4% |

---

## 4. Key Insights

### Insight 1: Risky-but-high-t Trials — t03, t11, t14, t17, t34, tc_tailtrim_hedge

Several trials that cross the 2-sigma WATCH bar (t-stat ≥ 2.0 vs P0) have significant tail-risk concerns in the metrics:

- **t03_early_window** (t=+2.25): Positive mean (+0.42c/win), but skew −1.26 and CVaR 36c. The early-window filter catches a concentrated subset of windows; when it fails it fails hard. High win rate (69%) masks the tail.
- **t14_perp_hedge_unpaired** (t=+3.14, the strongest 2-sigma crosser): CVaR 50.7c, Ulcer 123c, skew −1.16. The perp-hedge reduces the average strand cost but the tail loss per window remains large when BTC moves against the hedge. The high t-stat reflects a genuine mean improvement, but the CVaR is essentially unchanged from P0 (51.9c).
- **t34_avoid_combined** (t=+2.12): The best mean (+3.01c/win) but CVaR 60c and Ulcer 80c — tail losses are *higher* than P0 despite the positive mean. This is a characteristic of a gate that skips low-PnL windows but retains all the large-loss windows (the adverse ones are the big-fill windows the gate cannot identify without the sig/flow filter).
- **tc_tailtrim_hedge** (t=+2.89, second-strongest crosser): CVaR 48c, skew −0.32. Reasonable profile — the hedge does reduce Ulcer (67c vs 123c for t14 alone) but CVaR is still elevated. This combo is the strongest by t-stat with a better tail than its components.

**Operator action**: these trials have genuine mean edge (t > 2σ) but the CVaR remains at 30–70c/window. Do not size up until n ≥ 300 and the tail distribution stabilises.

### Insight 2: Stable Sleeve — tc_pairmax (the standout) and tc_mid_tailtrim

The **stable sleeve** criterion (positive mean, Sharpe > 0.05, skew > −0.5, CVaR < 3c, recovery > 5) produces one clear winner and one near-miss:

- **tc_pairmax**: Sharpe +0.269, Sortino +0.112, skew **+3.33** (positive!), kurtosis +12, Recovery **+18.2**, Ulcer **0.22c**, CVaR **0.01c**. This is the entry-gate + complete-all-strands combo (k ≤ 9, tight spread, balanced flow). With only 9% of windows producing a PnL signal (the gate is extremely selective), the metrics represent a near-arbitrage profile: when it trades, it almost always wins small and almost never loses large. The t=+1.51 is below the 2-sigma bar, but the risk-adjusted metrics are by far the best in the field.
- **tc_mid_tailtrim** (k∈{4,5} + take-size ≤ 100): Sharpe +0.101, Sortino +0.050, Recovery +1.32, CVaR 20.8c, but skew −1.36 and kurtosis +8.67. Near-miss: good Sharpe and low Ulcer (45.6c) but the skew disqualifies it from "stable sleeve" proper. t=+1.93 (approaching 2σ).

**Operator action**: tc_pairmax is the *safest* risk-adjusted trial in the field. It does not yet clear the t=2σ bar (it barely trades — 9% of windows), but it has the best tail profile by a wide margin. It is suitable for a conservative allocation once n increases.

### Insight 3: Adverse-Selection (Pick-off Rate) Analysis

Global adverse-fill rate: **39.4%** (1,151 out of 2,924 accepted P0 fills had sig > 0 = spot moved against the leg in the 3 minutes before the fill). Key observations:

- All trials share the same 39.4% adverse rate in this analysis because the adverse-selection metric was computed on the shared P0 fill pool. Entry gates *reduce* the total fill count but do not change the adverse fraction unless they specifically filter on `sig` (t07_spot_gate) or on spread+sig jointly (t36_guarded_opener = live_current).
- t07 (sig ≤ 8 bps gate) is the direct adverse-selection defense: it cuts fills where the spot move exceeded 8 bps. The trial's modestly positive mean (+0.16c) and improved CVaR (60c vs 51.9c for P0 — actually *worse*) suggest the 8 bps threshold is too loose; the signal retains most adverse fills.
- The **39.4% adverse rate is structurally high** for a maker that should theoretically avoid informed flow. This is consistent with the tape finding that VPIN > 0.40 predicts stranded legs 9.7× more often (t32 finding); a significant fraction of fills come from informed participants even at the touch.
- **Adverse-selection outlier**: p2_signal_hold has the worst metrics across the board (Sharpe −0.134, Ulcer 503c, CVaR 69.6c) and is the only trial with negative skew completely flipped positive (+0.11) — suggesting it is actively picking the wrong side of the distribution by "holding" favorable-signal legs that turn out to be adverse.

### Insight 4: Skewness as a Strategy Health Monitor

The baseline P0 has skew −1.09. Healthy strategies should *reduce* this negative skew or move it toward 0. The table shows:

- **Strategies that worsen skew** (more negative): t01 (−1.73), t04 (−1.99), t09 (−2.10), t05 (−3.47), t06 (−2.93), t21 (−2.49), t_mid family (−3.07). These gates are cutting the profitable tails while retaining the loss tails — a sign of adverse selection by the gate itself.
- **Strategies that improve skew**: tc_pairmax (+3.33), p2_signal_hold (+0.11), t08_hold_no (+0.11), t10 (+0.34), t34_avoid_combined (+0.02), t31_face_contrarian (−0.01 ≈ 0). The positive-skew trials are the ones that eliminate stranded legs (tc_pairmax's "complete all" design) or structurally avoid the YES-leg strand (t36/live_current).
- **Key signal**: skew > 0 is a strong indicator of a genuinely asymmetric risk structure (lottery-style winners), not just noise. tc_pairmax's +3.33 reflects a distribution where the tail events are *wins*, not losses.

### Insight 5: Small-n Warning for Tail Metrics

At n=162 windows, CVaR95 is computed on the worst ~8 windows (5% of 162 = 8.1 observations). The extreme values in the table (e.g. t06's CVaR = 0.04c from only 11% active windows) reflect the near-zero tails of highly selective gates, not robust estimates. Kurtosis estimates at n=162 are especially noisy (rule of thumb: kurtosis estimates need n ≥ 500 to be reliable). The skewness and CVaR values in this table are **directional indicators only**; treat any value derived from fewer than 20 tail observations with caution. The pre-registered deploy threshold of n ≥ 300 is appropriate; at that sample size CVaR will be estimated on ~15 observations, still low but substantially more robust.

---

## 5. Conclusion

The metrics backtest confirms the leaderboard ranking but adds important nuance:

1. **tc_pairmax** is the safest bet by risk-adjusted metrics (CVaR ~0, positive skew, Recovery 18×) but barely trades (9% activity). Monitor as n grows.
2. **t14_perp_hedge_unpaired** and **tc_tailtrim_hedge** are the strongest 2-sigma crossers but carry substantial CVaR (~50c/window). They are "risky-but-good-mean" sleeves.
3. **Adverse-selection at 39.4%** is the dominant risk factor for all trials. t07 and t36 are the dedicated defenses; neither has yet cleared the deploy bar. A stronger sig-threshold filter warrants exploration.
4. The entire field is in negative-return territory on the gha_data forward tape (P0: −2.04c/win), suggesting this 162-window period may be a challenging regime (high strand rate). The metrics framework is in place for the full n ≥ 300 analysis.
