# REGIME ROBUSTNESS — is the static recommendation durable, or a 2007-2024 bond-bull artifact?

**Question.** The honesty-gate found dead-simple static portfolios beat the active
momentum+trend book risk-adjusted (Permanent Portfolio Sharpe ~0.93, risk-parity ~0.84
vs active ~0.81) — but flagged that the statics rode a 17-year (2007-2024) BOND+GOLD
TAILWIND (falling rates, negative stock-bond correlation) that may not repeat. If the next
decade is rising-rate / stock-bond-POSITIVE-correlation (2022-like) / stagflation, is the
bond-heavy static fragile, and does the active book's "rotate out of falling assets" win
forward? The ETF-era backtests only reach ~2007 — almost entirely the bond bull. **So this
study goes back to 1972** and re-runs the candidates through the regimes the modern sample
never saw.

**Headline finding (TL;DR).**
- The static does **NOT** uniformly collapse when rates rise. In the 1972-1981 RISING-RATE
  bond bear the **Permanent Portfolio returned +175%** — because its **gold and cash** sleeves
  (gold +34%/yr in the 1970s; T-bills 11-15%/yr) carried it while bonds went nowhere. The
  member that breaks in rising rates is **60/40** (no gold, no cash): -23% in the 1973-74 bear.
- **The static's real kryptonite is 2022-type months — stocks AND bonds AND (sometimes) gold
  down together with positive stock-bond correlation.** There the PP (-12%), risk-parity (-15%)
  and 60/40 (-15%) all lose. A **time-series TREND overlay cuts that loss to ~-4% to -5%**.
- **A trend overlay dominates the raw static across essentially every regime AND the full
  sample**: Sharpe ~1.4-1.5 vs PP 1.25, max drawdown roughly **halved** (-9% to -10% vs -16.5%
  to -27%), and it wins in both subperiod halves and across lookbacks 6-15m.
- **Verdict: REFINE the headline.** "Just hold the Permanent Portfolio" → **"hold a
  trend-overlaid / risk-managed all-weather portfolio."** The static's *raw* edge is partly a
  negative-correlation + one-time-gold-repricing artifact; a cheap trend overlay materially
  improves regime-robustness and is the most deployable choice across all regimes tested.

---

## 1. Long-history reconstruction — sources, method, caveats

**Window: 1972-01 → 2023-06, monthly (618 months).** All series are monthly TOTAL returns.
Built by `regime_data.py`; raw inputs staged NON-repo to `/tmp/regime_data/` (not committed).

| Sleeve | Series | Source | Coverage |
|---|---|---|---|
| **STOCKS** | S&P 500 total return (price + reinvested dividends) | **Robert Shiller** `ie_data.xls` (Yale), monthly 1871-2023; extended past 2023-09 with **Ken French** total US market (Mkt = Mkt-RF + RF) | 1871- |
| **UST10** | 10y Treasury total return, **reconstructed from the GS10 yield** | Shiller GS10 (FRED GS10 if reachable) | 1953- |
| **UST30** | Long-bond ("PP long bond") total return, reconstructed from a 30y yield | FRED GS30 (1977-) if cached; here proxied as **GS10 + 0.40pp** fixed term premium | proxy |
| **GOLD** | London gold price, monthly | **datahub `gold-prices`** (LBMA/Bundesbank lineage), 1833-2026 | 1833- |
| **CASH** | 1-month T-bill | **Ken French** RF (Ibbotson/CRSP), monthly 1926-2026 | 1926- |
| **CPI_infl** | CPI inflation | Shiller CPI (FRED CPIAUCNS if reachable) | 1871- |

**Bond total-return reconstruction (stated method).** We have no free clean constant-maturity
Treasury TR index back to 1972, so we reconstruct one from the yield. For a par bond of maturity
*m* held one month and re-marked at the new yield:

> monthly TR ≈ y_{t-1}/12  +  (−D · Δy)  +  ½ · C · Δy²

where *y* is the yield (decimal), Δy the monthly yield change, *D* the modified duration and *C*
the convexity of a par bond at that yield/maturity (standard yield-plus-price decomposition; cf.
Swinkels 2019, Damodaran's reconstruction approach). UST10 uses m=10, UST30 uses m=30.

**Caveats / SCREENS (do not overclaim precision pre-1990).**
- The bond series is a **duration/convexity mark-to-market**, ignoring roll-down and exact
  coupon-reinvestment timing. It is accurate enough to capture the **regime pattern** (does the
  long bond lose money when rates rise?) — **not** basis-point TR precision.
- **UST30 is a proxy** (GS10 + 0.40pp) because FRED was unreachable during this build (503 on
  every series/retry); with GS30 it would track ~0.4pp higher carry and somewhat more duration.
  The PP "long bond" is therefore mildly conservative on carry.
- **FRED was down for the whole build**; the pipeline falls back to Shiller's own GS10/CPI and
  Ken French RF (all authoritative). This caps the BOND-dependent common window at Shiller's
  2023-06 cutoff — which still **fully covers all five key regimes including 2022**. (Stocks,
  cash and gold individually extend to 2026; only the bond reconstruction needs FRED to go further.)
- Costs: **5 bps/side on rebalance turnover** (≥ the committed 3 bps, to be conservative on the
  higher-turnover trend overlay). Monthly rebalance. No leverage, no shorting (US-deployable).

**Validation (reconstruction matches known history):** 1973-74 stocks -17%/-26%, gold +67%/+72%;
1979 gold +189%; 1980 long bond -8%; 1982 long bond +40% (Volcker peak); 1994 long bond -15%;
2008 long bond +37% / stocks -39%; 2022 long bond -33% / stocks -15%. Stock-bond rolling
correlation flips from positive (1970s-90s) to negative (2000s-2010s) and back toward zero in 2022.

---

## 2. Full-sample results (1972-2023, monthly, net 5 bps/side)

| Candidate | CAGR | Sharpe | Sharpe(excess) | Vol | maxDD | Worst yr |
|---|---|---|---|---|---|---|
| Permanent Portfolio (25 stk/long-bond/gold/cash) | 7.9% | 1.25 | 0.56 | 6.2% | -16.5% | -12.2% |
| 60/40 (stocks/10y) | 9.1% | 1.12 | 0.59 | 8.1% | -27.3% | -19.7% |
| Risk-Parity (inv-vol, stk/10y/30y/gold) | 7.3% | 1.12 | 0.45 | 6.5% | -21.1% | -15.4% |
| 100% Stocks | 10.6% | 0.87 | 0.53 | 12.6% | -49.0% | -39.2% |
| **PP + Trend overlay** | **9.9%** | **1.43** | **0.80** | 6.8% | **-10.1%** | **-5.3%** |
| **Trend (4-asset)** | 9.0% | **1.51** | 0.77 | 5.8% | **-8.7%** | **-3.8%** |
| Risk-Parity + Trend filter | 8.7% | 1.15 | 0.57 | 7.5% | -19.4% | -13.7% |

*(Total Sharpe is higher than the project's ETF-era numbers mainly because cash yields averaged
~4.4%/yr over 1972-2023; the **excess-over-cash** Sharpe is the honest cross-era metric and still
shows the trend overlay on top: 0.77-0.80 vs PP 0.56.)*

The two **time-series trend overlays** post the highest Sharpe AND the smallest drawdowns. The PP
beats 60/40 and plain risk-parity risk-adjusted (as the honesty-gate found), but a trend overlay
beats the PP.

---

## 3. The key regimes — per-candidate TOTAL RETURN over each window

| Regime | PP | 60/40 | Risk-Parity | 100% Stk | **PP+Trend** | **Trend 4-asset** | RP+TrendFilter |
|---|---|---|---|---|---|---|---|
| (a) 1973-74 stagflation bear | **+23.6%** | -22.7% | +4.3% | -38.6% | **+41.3%** | +32.1% | +1.6% |
| (a') full 1970s 1972-79 | +150.3% | +48.2% | +38.5% | +51.2% | **+169.6%** | +129.1% | +60.0% |
| **(b) RISING-RATE bond bear 1972-81** | **+174.6%** | +63.8% | +44.5% | +81.0% | **+245.0%** | +178.5% | +58.9% |
| (c) 1994 bond crash | -3.1% | -2.4% | -4.7% | +0.5% | -1.0% | -1.6% | -1.2% |
| (d) 2008 GFC (2007-11→2009-02) | +0.2% | -24.9% | +10.8% | -46.0% | +10.7% | +12.9% | **+19.1%** |
| **(e) 2022 stocks+bonds DOWN** | **-12.2%** | -14.7% | -15.4% | -15.0% | **-5.3%** | **-3.6%** | -13.7% |
| Bond bull 2007-2024 (the tailwind) | +142.9% | +202.4% | +152.9% | +324.1% | +193.7% | +158.1% | +206.0% |

**maxDD within each regime** (the durability lens):

| Regime | PP | 60/40 | Risk-Parity | 100% Stk | PP+Trend | Trend 4-asset | RP+TrendFilter |
|---|---|---|---|---|---|---|---|
| 1973-74 bear | -10.2% | -24.8% | -7.5% | -39.2% | **-7.7%** | **-4.7%** | -8.5% |
| RISING-RATE 1972-81 | -10.2% | -24.8% | -9.1% | -39.2% | -10.1% | **-7.4%** | -13.5% |
| 2008 GFC | -12.9% | -24.5% | -8.0% | -43.9% | -6.4% | **-4.9%** | -5.9% |
| **2022** | -15.1% | -16.6% | -18.1% | -17.6% | **-6.1%** | **-4.5%** | -12.9% |

**Reading the regimes.**
- **(b) Does the static collapse when rates rise? NO — the PP doesn't.** Its **gold + cash**
  sleeves are precisely the rising-rate/inflation hedge; long bonds going sideways was offset by
  gold +34%/yr and T-bills 11-15%/yr. The static member that *does* break in rising rates is the
  bond-heavy, gold-less **60/40** (-23% in 1973-74). So the warning "rising rates kill the static"
  is **half right**: it kills 60/40, not the (gold+cash-diversified) Permanent Portfolio.
- **(e) The static's true failure mode is 2022** — stocks and bonds (and a flat gold) down
  *together* under positive correlation. PP -12%, RP -15%, 60/40 -15%. **This is the regime the
  warning is really about, and here the trend overlay earns its keep: -5% / -4% vs -12% to -15%**,
  because by early-2022 the 12-month trend in both stocks and long bonds had turned down and the
  overlay had already rotated those sleeves to cash.
- **The trend overlay protects where the static can't, and gives up almost nothing where the
  static is fine** — it still made +245% in the 1972-81 bond bear (it was in gold 71% of the 1970s)
  and +11-13% through the GFC.

---

## 4. Correlation regime — how much of the static's edge is a negative-correlation phenomenon?

**Stock-bond correlation by decade (STOCKS vs UST10 monthly):**

| 1970s | 1980s | 1990s | 2000s | 2010s | 2020s |
|---|---|---|---|---|---|
| +0.33 | +0.27 | +0.25 | **-0.19** | **-0.45** | -0.07 |

The bond's diversifying power (negative correlation) is a **2000s-2010s phenomenon**. For three
decades before that, stocks and bonds were *positively* correlated — the world the warning says we
may be returning to (2022 = +; 2020s avg back near zero).

**Excess-over-cash Sharpe in POSITIVE vs NEGATIVE correlation months** (36-month rolling sign;
316 positive months, 267 negative):

| Candidate | Sharpe (pos-corr) | Sharpe (neg-corr) | neg − pos |
|---|---|---|---|
| Permanent Portfolio | 0.43 | 0.67 | **+0.24** |
| Risk-Parity | 0.39 | 0.68 | **+0.29** |
| 60/40 | 0.74 | 0.66 | -0.08 |
| **PP + Trend overlay** | **0.73** | **0.91** | +0.18 |
| **Trend (4-asset)** | **0.73** | **0.85** | +0.12 |
| Risk-Parity + Trend filter | 0.53 | 0.78 | +0.25 |

**Quantified answer to the warning:** the bond-diversified statics (PP, risk-parity) **do** earn a
materially higher Sharpe in negative-correlation months (+0.24 / +0.29). **A meaningful slice of
their edge is structurally a negative-correlation phenomenon** — i.e., partly the 2007-2024
tailwind. In a positive-correlation world the PP's excess Sharpe falls to ~0.43 (near 60/40's
range), confirming the caveat. **But the trend overlays keep a high Sharpe in BOTH regimes**
(0.73 positive / 0.85-0.91 negative) — they don't *depend* on the bond hedge working, because when
the bond hedge stops working (rates rising / positive corr) the overlay simply isn't holding bonds.

**One more honesty point — the PP's 1970s survival leaned on a non-repeatable gold spike.** Gold
returned **+34%/yr in the 1970s** (a one-time Bretton-Woods/end-of-gold-standard repricing,
$35→$850) vs **+7.7%/yr** over the full sample. Replace the PP's gold with cash and its 1970s
return drops from +150% to +51%. So the static's rising-rate resilience is partly a *gold-repricing*
artifact, just as its 2007-2024 edge is partly a *negative-correlation* artifact. The trend
overlay, which adapts rather than betting on any single sleeve, is less exposed to either artifact
(it captured 71% of the 1970s gold run while retaining the ability to exit).

---

## 5. Robustness SCREENS

- **Lookback insensitivity (not overfit):** PP+Trend full-sample Sharpe = 1.38 / 1.45 / 1.44 /
  1.43 / 1.36 / 1.24 for 6 / 9 / 10 / 12 / 15 / 18-month trend lookbacks; the 2022 loss stays
  ~-4% to -10% across all. The result is a property of trend-following, not one magic parameter.
- **Subperiod stability (Sharpe, 1972-97 vs 1998-2023):** PP 1.42 → 1.06; Trend(4-asset)
  1.76 → 1.23; PP+Trend 1.60 → 1.25. The trend overlay **wins in both halves**, and the *static's*
  Sharpe decays more between halves than the overlay's.
- **Cost robustness:** PP+Trend Sharpe = 1.45 / 1.43 / 1.40 / 1.35 at 0 / 5 / 15 / 30 bps/side.
  Average one-way turnover ≈ **215%/yr** — modest, fully absorbable with commission-free ETFs.

---

## 6. Verdict — updated recommendation (honest)

1. **Is the raw static recommendation durable? Partially.** It is more durable than the warning
   implied — the **Permanent Portfolio survived the 1970s rising-rate bond bear** because gold +
   cash, not bonds, are its inflation/rising-rate hedge. The fragile static is **60/40**, not the PP.
2. **But the static's *risk-adjusted edge* is partly an artifact.** A measurable chunk of the PP /
   risk-parity Sharpe is the **negative stock-bond correlation of 2007-2024** (Sharpe drops ~0.24-0.29
   in positive-correlation months), and its 1970s resilience leaned on a **one-time gold repricing**.
   In a forward rising-rate / positive-correlation / 2022-repeat world, the raw static is exposed:
   2022 is exactly where PP/RP/60-40 all lost double digits together.
3. **Does a trend/momentum overlay win forward? Yes, on the evidence.** A simple 12-month
   time-series trend overlay (hold each sleeve only when its own trend is up, else cash — the active
   book's spirit, computable back to 1972) **beats the raw static on Sharpe (1.43-1.51 vs 1.25),
   halves max drawdown, cuts the 2022 loss from ~-13% to ~-4%, and still wins across the 1970s
   bond bear and the GFC** — and it does so robustly to lookback, subperiod and cost.
4. **Most regime-robust DEPLOYABLE portfolio:** a **static all-weather base WITH a trend overlay
   that can de-risk bonds/stocks to cash** — concretely a **Permanent-Portfolio-style 4-sleeve base
   (stocks / long Treasuries / gold / cash) with a 6-12m time-series-trend filter on each risk
   sleeve** (the "PP + Trend overlay" / "Trend 4-asset" candidate). Plain risk-parity-with-trend-filter
   also helps but less (it stays more bond-heavy). The pure static is the runner-up; pure 60/40 is
   the least regime-robust of the diversified set.

**Refined headline:** not *"just hold the Permanent Portfolio,"* but **"hold a trend-overlaid /
risk-managed all-weather portfolio (PP-style base + a 6-12m trend filter that parks falling sleeves
in cash)."** The static is a solid base; the trend overlay is what makes it durable across the
rising-rate / positive-correlation regime the warning is about — at ~215%/yr turnover and a few bps
of cost, well within reach of a small commission-free-ETF investor.

*Window 1972-01..2023-06 (618 months), monthly. Sources: Shiller ie_data.xls, FRED (fallback
Shiller GS10/CPI), datahub gold-prices, Ken French RF/Mkt. Costs 5 bps/side on turnover. Bond TR
reconstructed from yields (duration/convexity); UST30 proxied GS10+0.40pp (FRED unreachable at build).
Long-history proxies are imperfect — the load-bearing claim is the REGIME PATTERN, not pre-1990
basis-point precision. Code: `regime_data.py`, `regime_robustness.py`.*
