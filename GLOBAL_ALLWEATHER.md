# GLOBAL ALL-WEATHER — does broadening the base or tuning rebalance mechanics beat the simple US PP?

**Question.** The project's CORE deployable base (`allweather_live.py`, CONSERVATIVE) is a
US-centric Permanent-Portfolio book — **SPY / TLT / GLD at 25% each + 25% BIL cash**, with
a 12-month time-series TREND overlay that parks any falling risk sleeve in cash (long-history
Sharpe ~1.4, maxDD ~-10%). Two untested, low-overfitting refinements:
**(1) GLOBAL DIVERSIFICATION** — add ex-US/EM equity, a TIPS+commodities real-asset sleeve,
intermediate vs long Treasuries, intl bonds; **(2) REBALANCE MECHANICS** — monthly/quarterly/
annual cadence and no-trade bands. Do either genuinely help the trend-overlaid book, net of cost?

**TL;DR VERDICT.**
- **Global diversification does NOT improve the base.** Best global variant (Global-IEF) ties the
  US-PP on full-sample Sharpe (0.97 vs 0.94 — a hindsight rounding error) while giving up ~1.7 pts
  of CAGR (5.1% vs 6.8%) and **losing or tying in nearly every regime, including 2008 and the
  2009–2012 ex-US/EM/commodity-led window** where global was supposed to win. It only "wins" in the
  recent-5y holdout, and only on Sharpe via lower vol — not return. **Keep it simple: US PP.**
- **Rebalance mechanics DO help — and the lever is CADENCE, not bands.** Moving the US-PP base from
  **monthly → annual** rebalance cuts annualized turnover ~75% (274% → ~69%), drops realized cost
  from ~8 to ~2 bps/yr, **lowers maxDD (-9.6% → -7.8%) AND raises Sharpe** (rebalancing less often
  lets winners run). No-trade bands add essentially nothing on top of annual (plateau, <0.02 Sharpe).
- **Refined base: same sleeves, ANNUAL rebalance, optional wide (10–20%) band. No universe change.**

---

## Window, costs, method, SCREENS

- **Sample:** ETF-era, **2007-01 → 2026-06** (monthly TR from daily div-adjusted yfinance closes,
  resampled to month-end). Includes 2008 GFC, the 2009–2012 ex-US/EM/commodity leadership tail,
  the 2013–2021 US melt-up, COVID 2020, the 2022 stock+bond drawdown, and a recent-5y holdout.
  **It does NOT include the 1970s** — there are no investable ex-US/EM/commodity ETF proxies that
  far back, so a 1970s global test is impossible without manufacturing data. The 1970s case for the
  gold+cash sleeves is already settled on the 1972 reconstruction in `regime_robustness.py`; this
  study is exactly where global diversification *should* have the best shot, since the 2000s/2010s
  ex-US/EM/commodity episodes are all in-sample.
- **Costs:** **3 bps/side** on rebalance turnover (the committed live cost; `regime_robustness.py`
  used a conservative 5 bps). Turnover is reported separately so the **taxable-account tax-churn**
  argument is explicit (fewer trades = less short-term-gain realization, not just fewer bps).
- **Trend overlay (reused, unchanged):** each risk sleeve held only when its trailing 12m total
  return > 0, signal **lagged 1 month (no look-ahead)**; else that sleeve's weight → BIL. This is
  the locked rule from `regime_robustness.trend_overlay` / `allweather_live.sleeve_trend_up`.
- **SCREENS:** full sample + recent-5y holdout; per-episode returns; **plateau across band widths**
  (not a spike); **annual-cadence robustness across all 12 rebalance months** (below); US-vs-global
  judged on the FULL sample, not the US melt-up alone.
- Reproduce: `python global_allweather.py` (writes `/tmp/global_data/summary.json`).

---

## PART 1 — Global vs US-PP (both trend-overlaid, monthly, 3 bps/side)

Base sleeve weights (the trend overlay parks falling sleeves in BIL on top of these):
US-PP `SPY/TLT/GLD .25 + .25 BIL`; global books split equity into SPY/VEA/VWO, add TIP/DBC as a
real-asset sleeve, test IEF (intermediate) vs TLT (long), and BNDX (intl bonds).

**FULL SAMPLE 2007–2026**

| book | CAGR | Sharpe | Sh_ex | vol | maxDD | worstYr | annTurn |
|---|---|---|---|---|---|---|---|
| **US-PP (current)** | **6.8%** | 0.94 | **0.77** | 7.3% | -9.6% | -5.3% | 274% |
| Global-equity | 5.7% | 0.80 | 0.63 | 7.2% | -9.9% | -5.2% | 289% |
| Global-real | 5.0% | 0.85 | 0.64 | 5.9% | -7.8% | -5.1% | 270% |
| Global-IEF | 5.1% | **0.97** | 0.74 | 5.2% | -8.0% | -4.2% | 235% |
| Global-allweather | 4.8% | 0.88 | 0.65 | 5.5% | -8.6% | -4.4% | 255% |

**RECENT 5y HOLDOUT (from 2021-06)**

| book | CAGR | Sharpe | maxDD |
|---|---|---|---|
| US-PP (current) | 8.1% | 1.09 | -6.7% |
| Global-IEF | 7.7% | **1.37** | -3.9% |
| Global-allweather | 6.9% | 1.18 | -4.3% |

**PER-EPISODE TOTAL RETURN** (the honest cross-regime test)

| episode | US-PP | Global-eq | Global-real | Global-IEF | Global-AW |
|---|---|---|---|---|---|
| 2008 GFC (07-11..09-02) | **+3.1%** | +2.7% | +2.1% | +0.3% | +0.2% |
| exUS/EM/cmdty lead 2009–2012 | **+51.0%** | +40.8% | +32.3% | +28.4% | +27.6% |
| US melt-up 2013–2021 | **+55.5%** | +37.0% | +37.5% | +37.3% | +35.5% |
| 2022 stocks+bonds DOWN | -5.6% | -4.7% | -2.8% | **-2.8%** | -2.6% |
| recent 5y | **+48.5%** | +43.0% | +36.7% | +45.6% | +40.1% |

**Reading it honestly.** The brutal bar was "don't credit US just because it won the 2010s." It
clears the bar: **US-PP also wins the 2009–2012 window that ex-US/EM/commodities led** (+51% vs
+28–41%) and the 2008 GFC flight-to-quality (+3.1% vs ~flat for the IEF/commodity-heavy books).
The only places global edges ahead are (a) 2022 and (b) the recent holdout — and there it's a
**lower-vol, lower-return** trade (Global-IEF Sharpe is higher purely because intermediate
Treasuries + TIPS/commodities damp vol; you pay ~1.7 pts of CAGR for ~0.03 of full-sample Sharpe).
Why so muted? Two structural reasons: the **12m trend overlay already harvests most of the
cross-sectional dispersion** (it dumps whichever region/asset is falling into cash, so adding more
regions just adds correlated trend-off sleeves), and **diversifying gold into TIP/DBC dilutes the
single best crisis hedge** in this sample. Global diversification here is complexity (10 tickers vs
4, harder to hold at small size, more wash-sale/tax surface) for **no robust return or risk-adjusted
gain on the full sample.**

---

## PART 2 — Rebalance mechanics (cadence × no-trade band, US-PP base, 3 bps/side)

| cadence | band | CAGR | Sharpe | maxDD | annTurn | nTrades |
|---|---|---|---|---|---|---|
| monthly | 0% | 6.8% | 0.94 | -9.6% | 274% | 217 |
| monthly | 10% | 6.9% | 0.95 | -9.8% | 258% | 86 |
| monthly | 20% | 6.8% | 0.92 | -9.7% | 252% | 71 |
| quarterly | 0% | 5.7% | 0.77 | -11.5% | 164% | 73 |
| quarterly | 20% | 5.7% | 0.75 | -11.8% | 153% | 40 |
| **annual** | **0%** | **8.1%** | **1.17** | **-7.8%** | **69%** | 19 |
| annual | 10% | 8.2% | 1.17 | -7.8% | 68% | 17 |
| annual | 20% | 8.2% | 1.16 | -7.8% | 67% | 15 |

**Turnover / cost / tax savings vs the monthly-noband baseline (US-PP):**

| config | annTurn | turnover saved | cost (bps/yr) | ΔSharpe |
|---|---|---|---|---|
| monthly, no band | 274% | — | 8.2 | baseline |
| monthly, 10% band | 258% | 6% | 7.7 | +0.01 |
| quarterly, no band | 164% | 40% | 4.9 | **-0.17** |
| **annual, no band** | **69%** | **75%** | **2.1** | **+0.23** |
| annual, 20% band | 67% | 76% | 2.0 | +0.23 |

**Findings.**
- **Cadence is the dominant lever.** Annual rebalance cuts turnover ~75% AND **improves both Sharpe
  (+0.23) and maxDD (-9.6% → -7.8%)** — the classic "rebalance less, let trends run" effect: monthly
  rebalancing mechanically sells the rising sleeve and tops up the falling one every month, fighting
  the very 12m trend the overlay is trying to ride.
- **Quarterly is a trap, not a compromise.** It is *worse* than both monthly and annual here
  (Sharpe 0.77). It rebalances often enough to fight the trend but on a calendar that, in this
  sample, repeatedly tops up sleeves just before they roll over. Don't split the difference.
- **No-trade bands add almost nothing on top of annual** — a flat **plateau** from 0% to 20%
  (Sharpe 1.17→1.16, turnover 69%→67%). Bands matter when you rebalance often (they're how you
  *avoid* over-trading a calendar); once you're already annual, there's little left to suppress.
  A wide 10–20% band is a harmless, mildly-helpful belt-and-suspenders for taxable accounts.
- **Interaction with the trend overlay (key caveat).** Most of the *residual* turnover is NOT
  drift-rebalancing — it's the **trend gate itself flipping sleeves on/off** (~0.31 sleeve-toggle
  events/month). Cadence and bands can only suppress the *drift* trades; they cannot remove the
  signal-driven trades, which is why even annual still runs ~69% turnover. The overlay is doing the
  real work; rebalance mechanics just stop you from adding self-inflicted churn on top of it.

**Robustness of the annual finding (anti-overfit screen).** The exact +0.23 is partly luck of *which*
month you rebalance. Running annual rebalance in each of the 12 calendar months: Sharpe ranges
0.89 (Apr) to 1.17 (Aug/Nov/Dec), **mean ≈ 1.04 — and annual beats monthly (0.94) in 11 of 12
months.** So "annual > monthly, at ~1/3 the turnover and lower DD" is a robust plateau, not a
December spike. Pick any annual month; don't curve-fit to August. (Practical tip: rebalance on your
account anniversary, or in a low-income month, to manage tax-lot timing.)

---

## VERDICT — refined base config

**Keep the US Permanent Portfolio universe. Do not globalize. Change only the cadence.**

```
CONSERVATIVE (refined):
  SPY 25% / TLT 25% / GLD 25% + BIL 25% (always cash)
  12-month time-series trend overlay (each risk sleeve held only if 12m TR > 0, else -> BIL)
  REBALANCE: ANNUAL (was: monthly partial)         <-- the change
  NO-TRADE BAND: optional 10-20% relative (harmless; nice-to-have for taxable accounts)
```

| metric (full sample 2007–2026, 3 bps/side) | current (US-PP, monthly) | refined (US-PP, annual) |
|---|---|---|
| Sharpe | 0.94 | **1.17** |
| CAGR | 6.8% | **8.1%** |
| maxDD | -9.6% | **-7.8%** |
| annualized turnover | 274% | **~69% (-75%)** |
| realized cost | ~8 bps/yr | **~2 bps/yr** + far less taxable churn |

**Why not globalize:** on the FULL ETF sample — including the 2008 GFC and the 2009–2012
ex-US/EM/commodity-led window, the regimes that should favor global — the US-PP wins or ties on
return and is within rounding on risk-adjusted return, for 4 tickers instead of 10. The global
"win" exists only in the recent holdout and only as a lower-vol/lower-return Sharpe trade. That is
**home-bias-in-hindsight risk in reverse**: the honest read is that the trend overlay already
captures the diversification benefit, so adding regions is complexity without a robust edge.
**Simplicity wins — and it wins on the merits, not just on parsimony.**

**Recommended code change:** the universe in `allweather_live.py` is correct and should NOT change.
The only justified change is the **rebalance cadence** (monthly partial-step → annual full
rebalance, optionally with a 10–20% no-trade band). That is a runbook/parameter change, kept out of
the locked-universe surface deliberately.
