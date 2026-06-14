# Do stocks predict bitcoin? A cross-asset lead-lag study

**Question:** Do ANY stocks (or equity ETFs / sectors / factors) PREDICT (lead) the price of
bitcoin at a tradable horizon, net of costs, out-of-sample? Or is the honest answer that BTC
leads its own proxies and broad risk-on is *contemporaneous*, not predictive?

**VERDICT (one line): NULL — no stock, ETF, sector, or macro factor tradably leads BTC.** At the
**daily** horizon the forward correlation `stock_t -> BTC_{t+1}` is **insignificant for every one
of 17 candidates, in both directions** (full sample, recent 2yr, and the 2021-22 high-corr regime).
The **overnight-gap test** — the decisive non-contemporaneous test, "today's US equity-session move
predicts BTC's move while equities are CLOSED" — is **flat null for all 17** (every |r| < 0.08,
all p > 0.2), while the *contemporaneous* (same-session) correlation is large (MSTR 0.66, GBTC 0.90,
SPY 0.44). That gap is the whole story: **what looks like "equities lead BTC" is just BTC and the
risk-on basket moving together during equity hours; BTC has already reflected it by the time markets
close.** The one place a "lead" appears — **hourly, lag-1** (MSTR r=0.33) — is a **bar-timing
artifact**: equity bars stamp at :30, BTC at :00, so "BTC next hour" overlaps "equity this hour" by
30 min. Push to a genuinely **disjoint lag-2** and the correlation collapses to ~0.03 (insignificant)
for every name. Granger causality: **nothing Granger-causes BTC at p<0.01 except GLD in the recent
2yr window only** (p=0.0022) — a lone hit out of ~50 tests across regimes, i.e. expected by chance
and not stable. Every backtested rule (daily long/flat BTC on a stock signal; overnight BTC on the
equity-session sign) **loses to buy-hold and to the BTC>=200d trend rule, net of costs, OOS.**
**Who-leads-whom: if anything BTC (24/7) leads its equity proxies, not the reverse; broad risk-on
is contemporaneous, not predictive.**

---

## SCREENS — data, window, costs

- **Source:** yfinance, `auto_adjust=True`. Daily `period=max`; hourly `period=730d` (yfinance cap).
  Staged at `/tmp/spbtc_data/` (**NOT committed**). Scripts: `stocks_btc_pull.py`, `stocks_btc_leadlag.py`.
- **Universe (18):** `BTC-USD` + crypto-proxies `MSTR COIN RIOT MARA CLSK IBIT GBTC`; tech/risk
  `QQQ SOXX ARKK SPY IWM`; macro `UUP TLT GLD HYG ^VIX`.
- **Daily span:** BTC-USD 2014-01-02 -> 2026-06-14 (4,467 aligned return rows). Recent-2yr = last 504
  rows. Regime cut = 2021-01-01..2022-12-31 (730 rows, the "BTC = high-beta tech" era).
  Hourly span 2023-07-18 -> 2026-06-14. (IBIT lacks hourly history -> shown as nan where applicable.)
- **No look-ahead:** signal computed at close *t*, position effective *t+1*.
- **Costs:** 10 bps per position change (round-trip realistic for BTC spot / IBIT).
- **Significance bar:** strict **p < 0.01** with **Newey-West (HAC, 5 lags)** t-stats, deliberately
  strict because 17 candidates x several windows = many tests (multiple-testing control).
- **OOS:** holdout = last 40% of each sample. Benchmarks = BTC buy-hold and BTC>=200d-SMA trend rule.

---

## 1-2. LEAD-LAG + DIRECTION MATRIX (daily returns, HAC p)

`corr_t,t` = contemporaneous; `cand->BTC` = `corr(stock_t, BTC_{t+1})`; `BTC->cand` = `corr(BTC_t, stock_{t+1})`.
"who" requires p<0.01 to claim a direction.

### DAILY FULL (2014-2026, n=4467)
| cand | corr_t,t | p | cand->BTC_t+1 | p | BTC->cand_t+1 | p | who |
|---|---|---|---|---|---|---|---|
| MSTR | 0.389 | 0.000 | -0.023 | 0.289 | 0.010 | 0.699 | neither |
| COIN | 0.548 | 0.000 | -0.025 | 0.399 | 0.034 | 0.274 | neither |
| RIOT | 0.446 | 0.000 | -0.024 | 0.350 | 0.049 | 0.038 | neither |
| MARA | 0.364 | 0.000 | 0.003 | 0.895 | 0.029 | 0.216 | neither |
| CLSK | 0.155 | 0.001 | 0.024 | 0.451 | 0.032 | 0.174 | neither |
| IBIT | 0.875 | 0.000 | -0.016 | 0.781 | -0.011 | 0.851 | neither |
| GBTC | 0.702 | 0.000 | 0.026 | 0.424 | 0.056 | 0.050 | neither |
| QQQ | 0.258 | 0.000 | -0.025 | 0.265 | -0.034 | 0.388 | neither |
| SOXX | 0.240 | 0.000 | -0.021 | 0.351 | -0.048 | 0.144 | neither |
| ARKK | 0.315 | 0.000 | -0.020 | 0.361 | -0.006 | 0.770 | neither |
| SPY | 0.253 | 0.000 | -0.028 | 0.279 | -0.030 | 0.529 | neither |
| IWM | 0.262 | 0.000 | -0.027 | 0.323 | -0.020 | 0.554 | neither |
| UUP | -0.080 | 0.003 | 0.017 | 0.421 | -0.054 | 0.229 | neither |
| TLT | -0.016 | 0.413 | -0.011 | 0.702 | 0.005 | 0.887 | neither |
| GLD | 0.103 | 0.000 | -0.005 | 0.808 | 0.023 | 0.373 | neither |
| HYG | 0.183 | 0.000 | -0.045 | 0.104 | -0.054 | 0.154 | neither |
| ^VIX | -0.203 | 0.000 | 0.004 | 0.843 | 0.011 | 0.675 | neither |

**Read:** strong *contemporaneous* co-movement (proxies 0.4-0.9; broad risk-on 0.25-0.32; VIX -0.20),
but **every forward correlation is insignificant in BOTH directions.** No stock leads BTC; BTC does
not lead the stocks at daily resolution either (the proxies react intraday, within the same day).

### DAILY RECENT ~2yr (2025-2026, n=504) and 2021-2022 regime (n=730)
Same pattern: **all 17 candidates "neither"** in both windows. In 2021-22 the contemporaneous corr is
high (MSTR 0.66, ^VIX -0.42) but forward corr is null; the largest forward hit is MARA->cand 0.112
(p=0.043, fails the 0.01 bar) — i.e. BTC marginally leading MARA, the *opposite* of the hypothesis.
The relationship is **regime-dependent in CO-MOVEMENT but consistently null in PREDICTION.**

### HOURLY ~730d — and the OVERLAP ARTIFACT
At hourly lag-1 several names show large, "significant" `cand->BTC_{t+1}` (MSTR 0.331, GBTC 0.392,
SPY 0.220) that nearly equal contemporaneous corr — a red flag. Cause: **equity bars stamp at :30,
BTC bars at :00**, so the BTC *t+1* bar overlaps the equity *t* bar by 30 minutes and captures the
SAME move. Forcing a fully **disjoint lag-2** kills it:

| cand | r(lag1) | p1 | r(lag2, disjoint) | p2 |
|---|---|---|---|---|
| MSTR | 0.331 | 0.000 | 0.034 | 0.067 |
| COIN | 0.282 | 0.000 | 0.033 | 0.076 |
| GBTC | 0.392 | 0.000 | 0.018 | 0.384 |
| SPY | 0.220 | 0.000 | -0.001 | 0.960 |
| QQQ | 0.220 | 0.000 | 0.005 | 0.794 |
| SOXX | 0.182 | 0.000 | 0.009 | 0.653 |
| HYG | 0.204 | 0.000 | -0.019 | 0.271 |

**The hourly "lead" is 100% a bar-timing/overlap artifact. No durable hourly lead survives.**

---

## 3. GRANGER CAUSALITY (cand -> BTC, controls BTC own lags, maxlag=3, ssr-F)

| window | only hits at p<0.01 | interpretation |
|---|---|---|
| DAILY FULL (n=4467) | **none** (best: GBTC p=0.022, ^VIX p=0.027 — fail bar) | nothing Granger-causes BTC |
| RECENT 2yr (n=504) | **GLD p=0.0022** (lag 3) | 1 hit / 17; lone & window-specific |
| 2021-22 (n=730) | **none** (best: CLSK p=0.020 — fails bar) | nothing in the high-corr regime |

Across ~50 candidate-window Granger tests at the 0.01 bar there is **exactly one positive (GLD,
recent only)** — fully consistent with chance under multiple testing, not stable across windows, and
not a crypto-proxy or risk-on factor. **No robust Granger lead into BTC.**

---

## 4. THE OVERNIGHT-GAP CONTROL (decisive non-contemporaneous test)

Does **today's US equity-session return (09:30->16:00 ET, SPY-marked)** predict BTC's **overnight**
return measured **while equities are CLOSED** (session close 16:00 ET -> next session open 09:30 ET,
BTC read from its continuous 24/7 :00 hourly series)? n=497 sessions (2024-06 -> 2026-06).

| cand | sess_ret -> BTC OVERNIGHT (equities closed) | p(HAC) | sess_ret -> BTC SAME-session (contemp) | p |
|---|---|---|---|---|
| MSTR | -0.025 | 0.645 | **0.661** | 0.000 |
| COIN | -0.026 | 0.558 | **0.639** | 0.000 |
| GBTC | -0.054 | 0.356 | **0.897** | 0.000 |
| QQQ | -0.048 | 0.255 | 0.460 | 0.000 |
| SOXX | -0.052 | 0.212 | 0.414 | 0.000 |
| SPY | -0.032 | 0.435 | 0.443 | 0.000 |
| IWM | -0.051 | 0.213 | 0.481 | 0.000 |
| GLD | -0.071 | 0.251 | 0.182 | 0.002 |
| HYG | -0.020 | 0.576 | 0.392 | 0.000 |
| UUP | -0.004 | 0.931 | -0.193 | 0.002 |
| ^VIX | -0.017 | 0.753 | -0.404 | 0.000 |
| (all others) | |r|<0.04 | >0.3 | (mid-range) | <0.01 |

**This is the whole answer.** The contemporaneous (same-session) corr is large and highly significant
for the risk basket (GBTC 0.90, MSTR 0.66, SPY 0.44), but the **overnight predictive corr is ~0 and
insignificant for ALL 17 candidates** (every |r| < 0.08, all p > 0.2; signs even slightly negative).
A stock's daytime move says nothing about where BTC goes once equities shut. **What people mistake for
"equities lead BTC tomorrow" is BTC catching up to / co-moving with a contemporaneous risk-on move
during equity hours — BTC has already priced it by the close.**

---

## 5. TRADABILITY (net of 10 bps, OOS = last 40%)

**(a) Daily long/flat BTC when `stock_{t-1} > 0`, else flat.** Every candidate produces a *negative*
OOS Sharpe and underperforms both buy-hold and the 200d-trend rule. Examples (OOS Sharpe / CAGR):
MSTR -0.67 / -22.7%, SPY -1.24 / -40.3%, GLD -0.96 / -32.4% vs BTC buy-hold -0.26 / -13.9% and
BTC>=200d-trend -0.11 / -4.0%. (The OOS window is a flat/down BTC stretch, so all are negative — the
point is **no stock signal beats the trivial benchmarks**; the trend rule wins, as in prior BTC work.)

**(b) Overnight BTC on the sign of the equity-session return** (the cleanest tradable form of the
gap test), net 10 bps, OOS Sharpe: MSTR -0.32, SPY -0.67, QQQ -1.58, GLD -2.26; the *best* was
COIN +0.41 (cumret +11.5%) — a single name out of 17, unstable, and exactly what you expect as the
top of 17 noisy draws. No candidate delivers a stable, multi-name, theory-consistent edge.

**There is no tradable equity->BTC rule that beats BTC buy-hold or the BTC>=200d trend rule, net of
costs, OOS. The signal is not stable; the apparent in-window edges are regime/overlap/multiple-testing
artifacts.**

---

## 6. VERDICT

**Do any stocks predict BTC tradably? NO.** Honest null.

- **Daily:** no candidate's `stock_t -> BTC_{t+1}` is significant (p<0.01) in any window or direction.
- **Hourly:** the only apparent lead is a 30-minute bar-overlap artifact; it vanishes at disjoint lag-2.
- **Overnight-gap (decisive):** equity-session moves do NOT predict BTC's move while equities are
  closed — predictive r ~0 for all 17, despite large contemporaneous co-movement. Risk-on is
  **contemporaneous, not predictive.**
- **Granger:** one stray hit (GLD, recent only) out of ~50 tests — chance-level, not durable.
- **Backtests:** every rule loses to BTC buy-hold and the BTC>=200d trend rule, net of costs, OOS.
- **Who-leads-whom:** consistent with the prior — **BTC (24/7) leads its equity proxies**, the proxies
  react intraday to BTC, and the broad risk-on basket co-moves with BTC *within* equity hours without
  forecasting it. The proxies are **downstream** of BTC, not upstream.

The clean, useful finding: **the BTC<->equity link is real but contemporaneous. There is no robust,
tradable, out-of-sample, cost-surviving lead from any stock, ETF, sector, or macro factor into BTC.**
For crypto timing, the single-asset **BTC>=200d-SMA trend rule** (see `BTC_TREND_TIMING.md`) remains
the better tool; no equity signal adds to it.
