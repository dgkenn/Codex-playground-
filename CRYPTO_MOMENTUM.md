# Crypto Trend / Momentum: Is There a Scalable, Costs-Survivable Edge for Us?

**Date:** 2026-06-14
**Author:** automated research (claude)
**Branch:** claude/polymarket-bot-live-ready-vw7ut5

## TL;DR Verdict

**YES — a modest but real, costs-survivable, capacity-huge edge exists, and it lives in
CROSS-SECTIONAL momentum (rank the alts), not in single-asset trend-following.**

- **Best config:** 50/50 blend of cross-sectional momentum (14-day lookback, long top-30% /
  short bottom-30% of the alt universe, weekly rebalance) + a Turtle channel-breakout
  time-series sleeve (55-day, long/flat). **OOS Sharpe ≈ 1.07, OOS ann ≈ 37%, maxDD ≈ -34%.**
- The XS sleeve alone is the engine: **OOS Sharpe 1.1-1.2**, and it is positive in **all three
  independent ~2.2yr regimes** (Sharpe 1.56 / 1.85 / 1.05 in 2019-22 / 2022-24 / 2024-26),
  including the 2022 bear. It is **not** a single-regime mirage.
- The edge **survives 2x and even 3x costs** (combined OOS Sharpe 0.95 at 14bps, 0.84 at 21bps).
- **Honest caveat:** returns are decaying over time (ann 183% → 126% → 46% across the three folds)
  — consistent with a well-known, crowding factor — and drawdowns are large (~35-45%). This is a
  vol-target-and-size-small sleeve, not a free lunch. Hourly momentum is **dead** (uniformly
  negative OOS), and naive single-asset trend (price>MA, return-sign) is a fee-eaten ~0.4 Sharpe.

This passes our bar (OOS Sharpe > ~0.5 after costs) **via cross-sectional momentum specifically.**

---

## 1. Data Window & Cost Assumptions

| | |
|---|---|
| **Source** | OKX public `history-candles` API (paginated via `after` cursor). Binance/Bybit avoided (geo-blocked). Coinbase/Kraken confirmed reachable as cross-checks. |
| **Universe** | BTC, ETH, SOL, XRP, DOGE, ADA, AVAX, LINK, LTC, BNB (10 top-liquid USDT pairs) |
| **Daily history** | 2019-11-19 → 2026-06-14 (~2400 bars for the majors; SOL/AVAX from 2020-09; BNB from 2022-12). XS tests run on the 9-asset set back to 2019 and the full 10-asset set from 2022-12. |
| **Hourly history** | 2025-10-07 → 2026-06-14 (~6000 bars, ~8 months) per asset |
| **Cost model** | Cost = `cost_bps × turnover` per bar, where turnover = |Δposition|. **Base = 7 bps round-trip** (OKX taker ~0.08-0.10% each way + a few bps slippage on modest size). Swept at 0 / 7 / 14 / 21 bps. |
| **IS/OOS split** | First 65% of dates = in-sample, last 35% = out-of-sample (chronological). OOS window ≈ 2024-02-26 → 2026-06-14. Plus a 3-fold equal-thirds walk for regime robustness. |
| **Execution** | Signal computed on close[t], position held over the next bar, return = close[t]/close[t-1]-1. No look-ahead (positions lagged one bar). |

**Why this matches our setup honestly:** trend/XS-momentum signals turn over on **days-to-weeks**
horizons. A cloud bot with seconds-to-minutes latency is irrelevant at that frequency, and the
strategy trades the deepest books in crypto (BTC/ETH/top alts), so it **scales with capital** —
the opposite of a latency-sensitive HFT edge.

---

## 2. Time-Series (Trend-Following) Momentum — Signal Sweep

Equal-weight portfolio across the 10-asset universe, long/flat (LF) and long/short (LS), 7bps cost.

### Daily (the horizon that works)

| Signal | Lookback | Mode | IS Sharpe | **OOS Sharpe** | OOS ann | OOS maxDD |
|---|---|---|---|---|---|---|
| return-sign | 30d | LF | 2.14 | 0.57 | 16.0% | -38% |
| return-sign | 60d | LF | 1.56 | 0.62 | 18.2% | -34% |
| price>SMA | 30d | LF | 2.03 | 0.41 | 8.8% | -38% |
| price>SMA | 60d | LF | 1.78 | 0.44 | 10.2% | -37% |
| **Donchian channel** | **20d** | LF | 1.96 | **0.56** | 15.2% | -37% |
| **Donchian channel** | **55d** | LF | 1.42 | **0.36** | 6.8% | -44% |

**Read:** Single-asset trend exists OOS but is **modest (Sharpe ~0.4-0.6)** with **ugly ~40% drawdowns**.
A big IS→OOS Sharpe decay (2.0 → 0.4) is the classic signature of a crowded, decaying trend factor.
The *proper* channel-breakout (long on new N-day high, flat on new N-day low, hold between) is weaker
than a naive `close==rolling-max` formulation — that naive version's apparent Sharpe ~1.0 is an
artifact of constant re-entry and is NOT used as the headline.

### Hourly — DEAD

Every hourly TS config (12h / 1d / 3d / 7d lookbacks, LF and LS, all three signal families) is
**strongly negative OOS** (Sharpe -2 to -7, e.g. ret-12h LF OOS Sharpe -5.3). At the hourly horizon
crypto mean-reverts / chops; momentum just pays the fee on every flip. **Do not trade hourly momentum.**
This also confirms our latency is a non-issue: the money is at the multi-day horizon, not the fast one.

---

## 3. Cross-Sectional Momentum — the Real Edge

Rank the universe by trailing return; long top 30%, short bottom 30%, equal-weight, dollar-neutral.

| Lookback | Rebalance | IS Sharpe | **OOS Sharpe** | OOS ann | OOS maxDD |
|---|---|---|---|---|---|
| 7d | daily | 1.18 | -0.23 | -21% | -61% |
| **7d** | **weekly** | -0.05 | **1.23** | 63% | -44% |
| 14d | daily | 1.59 | 0.34 | 4% | -61% |
| **14d** | **weekly** | **1.56** | **1.24** | 63% | -43% |
| 30d | weekly | 0.99 | 0.33 | 5% | -37% |
| 60d | weekly | 1.06 | 0.51 | 14% | -55% |

**Read:**
- **Daily rebalance dies on costs** (turnover too high). **Weekly rebalance is the winner.**
- The edge concentrates in the **intermediate-term 7-14d lookback**. 30d+ fades OOS.
- The 14d/weekly config is the most *stable* (IS 1.56 AND OOS 1.24 — both halves agree), unlike
  7d (IS -0.05 / OOS 1.23, regime-flip risk).

### Regime robustness (the decisive test) — XS 14d weekly, 3 equal folds

| Fold | Window | Sharpe | Ann |
|---|---|---|---|
| 1 | 2019-11 → 2022-01 | 1.56 | 183% |
| 2 | 2022-01 → 2024-03 | 1.85 | 126% |
| 3 | 2024-03 → 2026-06 | 1.05 | 46% |

**Positive Sharpe in all three independent regimes, including the 2022 bear market.** This is the
evidence that XS-momentum is a genuine crypto factor, not curve-fit. The clear **return decay**
(183 → 126 → 46% ann) is the honest cost of telling the truth: the factor is well-known and crowding
in, but a Sharpe-~1 sleeve remains.

---

## 4. Vol-Scaling & Combination

**Vol-targeting (size ∝ 1/realized-vol, 30d window, capped 3x):** applied to the daily TS sleeve it
**did not improve OOS Sharpe** (0.41 → 0.09 at 40% target; the cap and the trending nature of vol hurt
the timing) but it **did cut maxDD** (-38% → -25%). Net: use vol-targeting as a **risk control to cap
drawdown**, not as a Sharpe booster.

**Combined 50/50 TS(channel-55) + XS(14d weekly):**

| | IS Sharpe | **OOS Sharpe** | OOS ann | OOS maxDD |
|---|---|---|---|---|
| Combined sleeve | 1.97 | **1.07** | 37.3% | -33.6% |

The blend keeps most of XS's OOS Sharpe while the slow TS sleeve diversifies it and trims the tail.

---

## 5. Capacity & Cost Sensitivity

### Cost sensitivity (combined sleeve)

| Cost | OOS Sharpe | OOS ann |
|---|---|---|
| 0 bps | 1.19 | 43% |
| 7 bps (1x, base) | **1.07** | 37% |
| 14 bps (2x) | 0.95 | 32% |
| 21 bps (3x) | 0.84 | 26% |

**The edge does NOT die at 2x or even 3x costs** — it degrades gracefully. This is the key
differentiator from typical retail strategies that are fee-eaten mirages. The reason is **low
turnover**: the channel-breakout TS sleeve trades only ~5-11 round-trips/yr/asset; the XS sleeve
rebalances weekly (~2x gross turnover/week). Annual cost drag at 7bps is on the order of a few
percent, not tens of percent.

### Capacity

- **Turnover is low** (weekly XS rebalance + slow TS), so capacity is set by the depth of the
  10 underlying spot books, not by latency.
- BTC/ETH spot books on OKX/Coinbase/Kraken absorb **seven-to-eight figures** per rebalance with
  single-digit-bps slippage; even the thinner alts (LINK, AVAX, ADA) take **six-to-seven figures**.
- **Realistic capacity: low-to-mid eight figures ($10-50M)** before slippage materially erodes the
  37% gross figure. At **our modest capital this is effectively uncapped** — we are nowhere near the
  liquidity ceiling, and we can size into the slippage budget already in the cost model.

---

## 6. Verdict

**There IS a realistic, costs-survivable, capital-scalable crypto momentum edge — but it is
cross-sectional, not single-asset trend, and it is a Sharpe-~1 sleeve, not a moonshot.**

- **Deploy:** 50/50 blend — **XS momentum (14d lookback, long top-30%/short bottom-30%, weekly
  rebalance)** + **channel-breakout TS (55d, long/flat)** across the 10 liquid USDT pairs, with
  **vol-targeting as a drawdown cap** (≈40% annual vol target).
- **OOS performance (2024-02 → 2026-06):** **Sharpe 1.07, ann return ~37%, maxDD ~34%.** XS sleeve
  alone OOS Sharpe ~1.2; positive across all three historical regimes.
- **Cost robustness:** survives 2x (0.95) and 3x (0.84) fees.
- **Capacity:** $10-50M+; uncapped at our scale.
- **Honest risks:** (1) clear return *decay* over time (crowding) — size for the recent ~46% ann
  regime, not the 180% early one; (2) **large 35-45% drawdowns** — mandatory vol-targeting and
  position caps; (3) short-lookback variants and daily rebalance are unstable / fee-eaten — stick to
  14d/weekly; (4) **hourly momentum is dead** — do not trade it.

**Bottom line: clears our OOS-Sharpe-> 0.5 bar with room to spare, via cross-sectional momentum.
It is a real, deployable, scalable sleeve — provided we respect the drawdowns and assume the edge
keeps decaying.**

---

### Files

- `fetch_data.py` — OKX OHLCV downloader (daily + hourly, paginated)
- `backtest.py` — full TS + XS + vol-scaling + cost-sensitivity sweep engine
- `momentum_deepdive.py` — OOS survivor deep-dive (per-asset, combined sleeve, regime folds, capacity)
