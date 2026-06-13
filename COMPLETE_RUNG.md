# RUNG 3 (COMPLETE) -- Phase-C optimization

Strand-handling ladder, rung 3 = pair the stranded leg fast (chase/cross to complete; if it won't pair, sell the cheap stranded leg). Backtest SCREEN on the BTC 15-min tape; **forward-validation required before deploy**.

- Data: BTC 15-min, 549 IS windows / 367 OOS windows (first 60% / last 40%).
- Strands under the combined open-gate stack: IS=189, OOS=139.
- All candidates run on the **combined 5-rung stack** (R1 t36, R2 GBM gate OOS, R4 streak, always-pair) with a pluggable rung-3 strand handler.
- DEPLOYED rung-3 = sell-cheap p_yeq<0.30, give=0.02, force-complete-age=immediate.

## Modeling note

In the fill model, strand handling is end-of-window. The stranded leg's OPEN minute `k` encodes available age: minutes-to-act = max(0, 12-k). "Chase/complete now" realizes the leg at its `exit` (next-minute spread-crossing) value minus `give` cents; "hold" realizes at `settle`. On a binary price=probability, so cheap longshot legs gain from selling and expensive favored legs gain from holding -- the sell-cheap price gate.

## Ranked metric table (OOS, full A/B set)

| Candidate | IS net | OOS net | Sharpe | Sortino | Skew | Kurt | Recov | Ulcer | VaR95 | CVaR95 | AvgW/L | TUW% | MaxDD | Win% | PF | IR_p0 | IR_live | Δ/strand | t_str | Δ/win | t_win |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **DEPLOYED (0.30/0.02/now)** | +2.43 | +2.51 | +0.090 | +0.09 | -0.09 | +2.12 | +1.55 | 272.74 | 43.11 | 64.43 | 0.92 | 87 | 594.41 | 58.3 | 1.29 | -0.009 | -0.011 | 0.00 | - | 0.00 | - |
| S3_fitted_tox>0.50 | +2.52 | +2.68 | +0.093 | +0.09 | -0.11 | +2.04 | +1.71 | 259.01 | 45.51 | 67.23 | 0.92 | 86 | 572.91 | 58.6 | 1.30 | -0.003 | +0.001 | +0.41 | +0.47 | +0.16 | +0.50 |
| S2_give0c | +2.43 | +2.52 | +0.090 | +0.09 | -0.09 | +2.12 | +1.55 | 272.54 | 43.11 | 64.43 | 0.92 | 87 | 594.10 | 58.3 | 1.29 | -0.009 | -0.011 | +0.01 | +10.85 | +0.00 | +8.32 |
| S5_escalate_give0.02 | +2.43 | +2.51 | +0.090 | +0.09 | -0.09 | +2.12 | +1.55 | 272.61 | 43.11 | 64.43 | 0.92 | 87 | 594.20 | 58.3 | 1.29 | -0.009 | -0.011 | +0.01 | +7.93 | +0.00 | +6.61 |
| S2_give1c | +2.43 | +2.51 | +0.090 | +0.09 | -0.09 | +2.12 | +1.55 | 272.64 | 43.11 | 64.43 | 0.92 | 87 | 594.25 | 58.3 | 1.29 | -0.009 | -0.011 | +0.00 | +10.85 | +0.00 | +8.32 |
| S5_escalate_give0.03 | +2.43 | +2.51 | +0.090 | +0.09 | -0.09 | +2.12 | +1.55 | 272.65 | 43.11 | 64.43 | 0.92 | 87 | 594.26 | 58.3 | 1.29 | -0.009 | -0.011 | +0.00 | +4.48 | +0.00 | +3.98 |
| S1_sell_cheap_0.3 | +2.43 | +2.51 | +0.090 | +0.09 | -0.09 | +2.12 | +1.55 | 272.74 | 43.11 | 64.43 | 0.92 | 87 | 594.41 | 58.3 | 1.29 | -0.009 | -0.011 | +nan | +nan | +nan | +nan |
| S2_give2c | +2.43 | +2.51 | +0.090 | +0.09 | -0.09 | +2.12 | +1.55 | 272.74 | 43.11 | 64.43 | 0.92 | 87 | 594.41 | 58.3 | 1.29 | -0.009 | -0.011 | +nan | +nan | +nan | +nan |
| S4_Tstar>=0min | +2.43 | +2.51 | +0.090 | +0.09 | -0.09 | +2.12 | +1.55 | 272.74 | 43.11 | 64.43 | 0.92 | 87 | 594.41 | 58.3 | 1.29 | -0.009 | -0.011 | +nan | +nan | +nan | +nan |
| S2_give3c | +2.43 | +2.51 | +0.090 | +0.09 | -0.09 | +2.12 | +1.55 | 272.83 | 43.11 | 64.43 | 0.92 | 87 | 594.56 | 58.3 | 1.29 | -0.009 | -0.011 | -0.00 | -10.85 | -0.00 | -8.32 |
| S6_partial0.75 | +2.44 | +2.44 | +0.087 | +0.08 | -0.10 | +2.05 | +1.47 | 277.25 | 43.45 | 64.76 | 0.92 | 88 | 608.79 | 58.0 | 1.28 | -0.012 | -0.019 | -0.30 | -0.79 | -0.08 | -0.60 |
| S4_Tstar>=1min | +2.33 | +2.42 | +0.083 | +0.08 | -0.25 | +2.30 | +1.49 | 263.62 | 46.83 | 71.08 | 0.89 | 87 | 598.50 | 58.6 | 1.27 | -0.012 | -0.023 | -0.53 | -0.42 | -0.09 | -0.21 |
| S1_sell_cheap_0.35 | +2.42 | +2.38 | +0.086 | +0.08 | -0.09 | +2.14 | +1.47 | 273.71 | 43.11 | 64.43 | 0.93 | 88 | 594.41 | 57.8 | 1.28 | -0.014 | -0.020 | -0.53 | -1.40 | -0.13 | -1.34 |
| S6_partial0.50 | +2.45 | +2.36 | +0.083 | +0.08 | -0.13 | +1.94 | +1.39 | 282.01 | 46.83 | 66.50 | 0.91 | 89 | 623.18 | 58.0 | 1.26 | -0.015 | -0.029 | -0.60 | -0.79 | -0.16 | -0.60 |
| S1_sell_cheap_0.25 | +2.40 | +2.34 | +0.083 | +0.08 | -0.12 | +2.05 | +1.31 | 308.11 | 45.51 | 66.02 | 0.90 | 88 | 656.52 | 58.3 | 1.27 | -0.016 | -0.024 | -0.43 | -0.94 | -0.17 | -0.98 |
| S6_AC_urgency | +2.44 | +2.34 | +0.082 | +0.08 | -0.14 | +1.92 | +1.37 | 283.47 | 46.83 | 67.33 | 0.90 | 89 | 627.21 | 58.0 | 1.26 | -0.015 | -0.033 | -0.69 | -0.80 | -0.18 | -0.60 |
| S4_Tstar>=2min | +2.36 | +2.28 | +0.077 | +0.07 | -0.27 | +2.21 | +1.26 | 298.58 | 49.34 | 72.39 | 0.88 | 88 | 661.49 | 58.6 | 1.25 | -0.017 | -0.039 | -0.90 | -0.67 | -0.23 | -0.49 |
| S1_sell_cheap_0.4 | +2.42 | +2.25 | +0.082 | +0.08 | -0.11 | +2.08 | +1.39 | 277.90 | 43.11 | 63.71 | 0.92 | 89 | 593.33 | 57.8 | 1.26 | -0.019 | -0.029 | -0.87 | -1.58 | -0.26 | -1.44 |
| S1_sell_cheap_0.2 | +2.41 | +2.25 | +0.077 | +0.07 | -0.21 | +2.20 | +1.19 | 321.36 | 46.83 | 69.38 | 0.89 | 89 | 693.27 | 58.3 | 1.25 | -0.018 | -0.039 | -0.95 | -0.77 | -0.26 | -0.62 |
| S3_combo_tox>0.40 | +2.47 | +2.20 | +0.074 | +0.07 | -0.28 | +2.12 | +1.24 | 292.25 | 50.79 | 72.74 | 0.88 | 89 | 651.95 | 58.3 | 1.23 | -0.019 | -0.053 | -1.21 | -0.79 | -0.31 | -0.60 |
| S3_combo_tox>0.50 | +2.47 | +2.20 | +0.074 | +0.07 | -0.28 | +2.12 | +1.24 | 292.25 | 50.79 | 72.74 | 0.88 | 89 | 651.95 | 58.3 | 1.23 | -0.019 | -0.053 | -1.21 | -0.79 | -0.31 | -0.60 |
| S3_combo_tox>0.40_nocap | +2.47 | +2.20 | +0.074 | +0.07 | -0.28 | +2.12 | +1.24 | 292.25 | 50.79 | 72.74 | 0.88 | 89 | 651.95 | 58.3 | 1.23 | -0.019 | -0.053 | -1.21 | -0.79 | -0.31 | -0.60 |
| S4_Tstar>=3min | +2.40 | +2.14 | +0.072 | +0.07 | -0.27 | +2.13 | +1.19 | 297.96 | 50.79 | 72.74 | 0.87 | 89 | 659.75 | 58.3 | 1.23 | -0.022 | -0.061 | -1.41 | -0.93 | -0.38 | -0.73 |
| S6_AC_urgency_nocap | +2.62 | +2.04 | +0.074 | +0.07 | -0.20 | +2.02 | +1.16 | 305.32 | 46.83 | 66.26 | 0.89 | 89 | 643.56 | 57.8 | 1.23 | -0.027 | -0.056 | -1.51 | -1.39 | -0.48 | -1.30 |
| S1_sell_all | +2.76 | +1.77 | +0.067 | +0.06 | -0.20 | +2.20 | +1.00 | 336.08 | 44.68 | 63.51 | 0.89 | 90 | 649.10 | 57.5 | 1.21 | -0.037 | -0.051 | -2.02 | -1.30 | -0.74 | -1.44 |

(Δ/strand, Δ/win = marginal cents vs DEPLOYED, paired across matched strands/windows OOS.)

## Sub-study verdicts

### 1. Sell-cheap price-threshold sweep
- `S1_sell_cheap_0.3`: OOS +2.51c, Sharpe +0.090, CVaR 64.43c, Δ/win +nanc (t=+nan).
- `S1_sell_cheap_0.35`: OOS +2.38c, Sharpe +0.086, CVaR 64.43c, Δ/win -0.13c (t=-1.34).
- `S1_sell_cheap_0.25`: OOS +2.34c, Sharpe +0.083, CVaR 66.02c, Δ/win -0.17c (t=-0.98).
- `S1_sell_cheap_0.4`: OOS +2.25c, Sharpe +0.082, CVaR 63.71c, Δ/win -0.26c (t=-1.44).
- `S1_sell_cheap_0.2`: OOS +2.25c, Sharpe +0.077, CVaR 69.38c, Δ/win -0.26c (t=-0.62).
- `S1_sell_all`: OOS +1.77c, Sharpe +0.067, CVaR 63.51c, Δ/win -0.74c (t=-1.44).

### 2. Chase give sweep
- `S2_give0c`: OOS +2.52c, Δ/win +0.00c (t=+8.32). 
- `S2_give1c`: OOS +2.51c, Δ/win +0.00c (t=+8.32). 
- `S2_give2c`: OOS +2.51c, Δ/win +nanc (t=+nan). 
- `S2_give3c`: OOS +2.51c, Δ/win -0.00c (t=-8.32). 
- Verdict: give=0/1/2c are a dead-flat plateau (sub-0.01c spread); give=0 marginally tops, give=3c marginally worst. The `exit` field already prices crossing the touch, so extra give is pure cost. Deployed give=0.02 sits inside the plateau (zero measurable cost); give=0 is the cleanest point. Confirms prior give-sweep finding.

### 3. Tox-conditioned sell
- `S3_fitted_tox>0.50`: OOS +2.68c, Δ/win +0.16c (t=+0.50).
- `S3_combo_tox>0.40`: OOS +2.20c, Δ/win -0.31c (t=-0.60).
- `S3_combo_tox>0.50`: OOS +2.20c, Δ/win -0.31c (t=-0.60).
- `S3_combo_tox>0.40_nocap`: OOS +2.20c, Δ/win -0.31c (t=-0.60).

### 4. Force-complete-age T* sweep
- `S4_Tstar>=0min`: OOS +2.51c, Δ/win +nanc (t=+nan).
- `S4_Tstar>=1min`: OOS +2.42c, Δ/win -0.09c (t=-0.21).
- `S4_Tstar>=2min`: OOS +2.28c, Δ/win -0.23c (t=-0.49).
- `S4_Tstar>=3min`: OOS +2.14c, Δ/win -0.38c (t=-0.73).

### 5. Escalating improve vs flat
- `S5_escalate_give0.02`: OOS +2.51c, Δ/win +0.00c (t=+6.61).
- `S5_escalate_give0.03`: OOS +2.51c, Δ/win +0.00c (t=+3.98).

### 6. Partial size / Almgren-Chriss urgency
- `S6_partial0.75`: OOS +2.44c, Δ/win -0.08c (t=-0.60).
- `S6_partial0.50`: OOS +2.36c, Δ/win -0.16c (t=-0.60).
- `S6_AC_urgency`: OOS +2.34c, Δ/win -0.18c (t=-0.60).
- `S6_AC_urgency_nocap`: OOS +2.04c, Δ/win -0.48c (t=-1.30).

## Recommended rung-3 parameterization

**Top-ranked candidate:** `S3_fitted_tox>0.50` -- OOS +2.68c vs deployed +2.51c (marginal +0.16c/win, t_win=+0.50; Δ/strand +0.41c, t_strand=+0.47).

**Keep the deployed parameterization** (sell-cheap 0.30, give 0.02, immediate). No candidate clears a clean OOS bar with significant per-window t-stat; the ladder is flat in this region, consistent with prior findings (give=0/0.02 both ~optimal, T*=immediate best, sell-cheap genuinely earns its place).

### Exact trader flags to deploy

```
--strand-complete           # rung-3 COMPLETE: pair stranded leg fast
--sell-cheap-below 0.30     # sell (cross/exit) only when stranded p_yeq < 0.30; else hold
--chase-max-give 0.02       # cross up to 2c beyond the touch (give=0 is marginally cleanest;
                            #   give 0..2c is a flat plateau -- 0.02 has zero measurable cost)
--force-complete-age 0      # immediate: chase from the strand minute (T*=now best)
# tox-conditioning: OFF (no consistent OOS gain); escalate: OFF; partial/AC-urgency: OFF
```

## IS/OOS stability

- DEPLOYED: IS +2.43c -> OOS +2.51c.
- COMBINED baseline: IS +3.76c -> OOS +3.50c.
- Top candidate `S3_fitted_tox>0.50`: IS +2.52c -> OOS +2.68c.
- The candidate ranking is tightly clustered (sub-cent spread across the price/give grid), indicating the rung-3 frontier is flat -- the deployed point sits inside the optimal plateau.

## Marginal gain vs deployed (with t-stats)

- Best per-window marginal: +0.16c/win (t_win=+0.50) for `S3_fitted_tox>0.50`.
- A |t|<1.96 means the candidate is statistically indistinguishable from deployed on this OOS sample (n=367 windows, 139 strands) -- a SCREEN result, not a deploy mandate.

## Caveats

- Backtest SCREEN: `exit` models a single next-minute touch-crossing; true chase realizes queue position + multi-minute slippage not captured here. Forward-validate before swapping live.
- Small strand sample (OOS n=139); per-bucket t-stats are noisy. Negative locks are ~0.8% of loss, so refusing large completions is not modeled (consistent with prior finding).
- Tox-conditioning and AC-urgency are screened here; combo_tox features are None on some legs (gate no-ops), limiting their reach on the strand subset.

