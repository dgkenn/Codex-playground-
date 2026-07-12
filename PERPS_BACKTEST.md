# PERPS_BACKTEST.md — post-cost backtests of candidate perp strategies, on real data

**Date:** 2026-07-12. **Script:** `perps_backtest.py` (reproducible — re-run it to regenerate every
number in this doc). **Companion doc:** `PERPS_RESEARCH.md` (desk survey of the same question from
literature + this repo's prior screens; this doc supplies the new piece — an actual backtest on a
longer, real, single-venue price+funding series). Read `PERPS_RESEARCH.md` first for the
capital/venue framing; this doc is the numbers.

## Headline verdicts (read this first)

| Strategy | Post-cost full-sample | OOS half | Clears `t≥3` day-clustered bar? | Verdict |
|---|---|---|---|---|
| **1. Funding carry — BTC** | Sharpe 8.8, ann +6.0%/yr | Sharpe 5.4, ann +2.5%/yr, **t=+6.67** | **YES** | Real, tiny, low-vol edge. Statistically solid but economically small (2.5%/yr on a delta-neutral book) — matches `PERPS_RESEARCH.md`'s "needs six-figure capital to matter in $/day" conclusion. |
| **1. Funding carry — ETH** | Sharpe 4.7, ann +3.4%/yr | Sharpe **−2.7**, ann **−1.3%/yr**, **t=−3.25** | **NO — edge reversed OOS** | The IS half looked great (Sharpe 9.8); the OOS half is a statistically significant **loss**. This is exactly the failure mode this repo is built to catch. **Flagged as a reversal, not a null result.** |
| **2. Daily TS momentum — BTC** (MA cross / Donchian / 24d mom, w/ vol-scaling) | Sharpe 0.2–0.6 | best OOS t=+0.41 | **NO** | Indistinguishable from noise post-cost; drawdowns 35–68%. |
| **2. Daily TS momentum — ETH** (best: 24d mom, vol-scaled) | Sharpe 0.98, ann +49%/yr | Sharpe **1.71**, ann +132%/yr, **t=+2.09** | **NO (close, but short of 3, and selection-biased — see §4 caveat)** | Promising-looking OOS number, but IS was flat-to-negative (sign reversal the other direction from carry/ETH) and it was the *post-hoc best of 12 daily configs* — treat as an unconfirmed candidate for a genuinely fresh forward test, not a validated edge. |
| **2b. Hourly 12h/24h momentum** (both assets) | Sharpe −1.1 to −3.6 | OOS t as low as **−4.20** | **NO — statistically significant losses** | Short-horizon momentum is **anti-persistent** after realistic hourly funding+fee costs on this venue. Confidently do not trade this. |
| **3. Hourly mean reversion** (RSI14 fade, z-score20h fade) | Sharpe −1.1 to −2.0 | OOS t −0.30 to −2.67, all negative | **NO — no config was profitable, several significantly negative** | Naive hourly fade loses to costs on both assets, both variants. No exceptions found. |
| **4. SL/TP overlay** (on ETH 24d-mom vol-scaled, the best OOS momentum config) | Best variant (3% SL only): Sharpe 0.98→1.03 | not separately re-split | **Immaterial** | SL/TP neither meaningfully helps nor hurts this particular config — most SL/TP levels tested were never binding (vol-scaled daily moves rarely breach 5–8%). The one binding level (tight 3% SL) gave a small, not clearly significant, improvement. **No exit-rule fixes a marginal signal here — consistent with this repo's own prior finding on the box bot** (`CLAUDE.md`: "Stop-loss exits LOSE... risk control is SIZE, never exits"). |

**Bottom line:** of 4 strategy families × 2 assets × multiple parameterizations, exactly **one**
configuration clears the repo's own `day-clustered t≥3` forward bar out-of-sample: **BTC funding
carry**, and its economic size is small (≈2.5%/yr on a delta-neutral book — this matches
`PERPS_RESEARCH.md`'s independent desk-research conclusion that carry only matters in $/day at
six-figure+ capital). Every directional strategy (momentum, mean-reversion, SL/TP) either fails to
clear the bar or is actively, significantly negative post-cost. ETH funding carry is the standout
negative finding: it looks good in-sample and **reverses sign** out-of-sample.

---

## 1. Data — sources, what's real, what's not available

| Need | Source used | Depth confirmed | Why not the "obvious" venue |
|---|---|---|---|
| BTC/ETH perp price (daily) | Deribit `get_tradingview_chart_data`, `BTC-PERPETUAL`/`ETH-PERPETUAL` | 1,096 daily bars/asset, **2023-07-13 → 2026-07-12** (full 3y in one request; verified depth back to 2021-12-31, i.e. 4.5y available) | Binance: HTTP 451 (geo-blocked). Bybit: CloudFront geo-block ("configured to block access from your country" — confirmed directly this session on `/v5/market/kline` and `/v5/market/funding/history`). |
| BTC/ETH perp price (hourly) | Same Deribit endpoint, `resolution=60`, chunked ~190d/request | 26,281 hourly bars/asset (full 3y) | — |
| BTC/ETH funding rate history | Deribit `get_funding_rate_history`, `interest_1h` field (the rate **actually charged** for that hour; `interest_8h` is a smoothed display value, not used) | 26,280 hourly funding observations/asset, same 3y window, chunked at ~28d (Deribit hard-caps 744 rows/call) | OKX: candles go back years and were confirmed working, but `funding-rate-history` **hard-caps at ~90 days server-side** — paging with `before=` past that point silently returns *recent*, not older, data (confirmed both in this session and previously in `CRYPTO_FUNDING.md`). Not usable for a multi-year backtest. Bybit funding: same geo-block as above. |

**Why Deribit for both legs, not a blend:** using Deribit's own perpetual for price *and* funding
keeps the two internally consistent — no cross-venue basis artifact from pairing, say, OKX price
with Binance funding. The tradeoff, stated plainly: **this is one venue's specific funding
regime**, not a cross-exchange average. Deribit is a real, liquid, institutional venue (not a toy
testnet), and funding tends to move in the same *sign* across venues (all perps arbitrage toward
similar funding when basis diverges), but *levels* can differ from Binance/OKX/Bybit's. Anyone
deploying this on a different venue should re-pull that venue's own funding before trusting the
$/day numbers — the qualitative conclusions (carry is small; momentum/mean-reversion fail post-cost)
are much more likely to transfer than the exact percentages.

**Cost assumptions used throughout** (documented, not fit to the data):
- Taker: **6 bps/fill**. Maker: **1.5 bps/fill**. (Task spec's 5–10bps taker / 1–2bps maker range,
  midpoint-ish — not Deribit's own fee schedule, which is sometimes more favorable; using a
  conservative generic retail assumption so results aren't an artifact of one venue's best tier.)
- Funding carry round-trip (2-leg: spot + perp, open + close = 4 fills): **24 bps (taker)** / **6
  bps (maker)**.
- Momentum/mean-reversion: **6 bps per position change** (one perp leg, taker), applied every time
  the position size changes (not just direction flips — a vol-scaling resize also pays turnover).

---

## 2. Strategy 1 — Funding-rate carry (delta-neutral)

**Mechanism:** trailing 7-day mean funding, annualized, lagged 1 day (decided on data through
yesterday only). Short-perp/long-spot (collect funding) when the trailing signal is above
`+entry_thr`; long-perp/short-spot when below `-entry_thr`; flat in a hysteresis band down to
`exit_thr` (avoids churning at the threshold — this repo's own prior carry screen found churn is
what kills this trade). P&L = `-position × funding_rate_that_day − cost × |Δposition| / 2`.

**Funding regime over this 3y window** (real, not the 94-day screen in `CRYPTO_FUNDING.md`):
- BTC: mean **7.08%/yr annualized**, positive 81.0% of days.
- ETH: mean **5.25%/yr annualized**, positive 70.3% of days.

Both hotter than the prior 94-day calm-regime screen (BTC 1.54%, ETH 2.05%) — this 3-year window
captures more of the 2024–2025 bull-market funding spike `PERPS_RESEARCH.md` flagged as real but
not the base rate.

### Threshold sensitivity (full 3y sample, post-cost)

| Asset | entry/exit (ann) | cost | Sharpe | Calmar | maxDD | annRet | %profMo | t (day-clu) |
|---|---|---|---|---|---|---|---|---|
| BTC | 2%/0% | taker | 8.44 | 6.82 | −0.9% | +6.1% | 64.9% | +14.63 |
| BTC | 2%/0% | maker | 11.62 | 38.66 | −0.2% | +7.1% | 81.1% | +20.14 |
| BTC | 5%/1% | taker | 8.75 | 14.66 | −0.4% | +6.0% | 56.8% | +15.16 |
| BTC | 5%/1% | maker | 11.03 | 40.50 | −0.2% | +6.6% | 64.9% | +19.11 |
| BTC | 10%/2% | taker | 7.94 | 14.96 | −0.3% | +5.2% | 48.6% | +13.76 |
| BTC | 20%/5% | taker | 5.25 | 11.22 | −0.3% | +2.8% | 24.3% | +9.11 |
| ETH | 2%/0% | taker | 4.38 | 1.02 | −3.4% | +3.5% | 51.4% | +7.59 |
| ETH | 5%/1% | taker | 4.65 | 1.53 | −2.3% | +3.4% | 40.5% | +8.05 |
| ETH | 10%/2% | taker | 6.15 | 4.55 | −0.8% | +3.8% | 29.7% | +10.66 |
| ETH | 20%/5% | taker | 5.10 | 12.76 | −0.2% | +2.8% | 27.0% | +8.84 |

**Reading it honestly:** every threshold, both assets, is full-sample positive at both cost tiers —
this alone would look like a slam dunk. It isn't one, because of the IS/OOS split below. Note also
the (very large) Sharpe ratios are typical of *any* low-variance delta-neutral carry book (funding
P&L barely moves day to day) — a Sharpe of 8–11 here does **not** mean "amazing strategy," it means
"small, steady, low-volatility payoff," which is exactly the 2–7%/yr annualized return column shows.

### IS/OOS split (entry=5%/exit=1%, taker costs — the middle-of-the-road config)

| Asset | Half | Sharpe | Calmar | maxDD | annRet | %profMo | t (day-clu) | n_days |
|---|---|---|---|---|---|---|---|---|
| BTC | IS (2023-07→2025-01) | 11.66 | 23.45 | −0.4% | +9.6% | 73.7% | +14.28 | 548 |
| BTC | **OOS (2025-01→2026-07)** | **5.44** | 10.23 | −0.2% | **+2.5%** | 42.1% | **+6.67** | 548 |
| ETH | IS (2023-07→2025-01) | 9.76 | 11.40 | −0.7% | +8.4% | 68.4% | +11.96 | 548 |
| ETH | **OOS (2025-01→2026-07)** | **−2.66** | −0.59 | −2.3% | **−1.3%** | 15.8% | **−3.25** | 548 |

**BTC carry clears the bar OOS** (t=6.67 ≥ 3), but the economic size is small: **+2.5%/yr** on a
fully delta-neutral book. To make this "matter" in $/day (echoing `PERPS_RESEARCH.md`'s
independent framing), a $100K book earns ≈$6.8/day gross of the operational overhead of running two
legs.

**ETH carry does NOT clear the bar — it fails the other direction.** The in-sample half looked
excellent (Sharpe 9.76); the out-of-sample half is a statistically significant **loss** (t=−3.25).
This is the single most important finding in this document: a naive backtester who only looked at
the IS half, or the full-sample table above, would have shipped a strategy that *loses* money
forward. **This is exactly the "every lab winner failed forward" pattern this repo's discipline
exists to catch — flagged explicitly, not glossed over.**

---

## 3. Strategy 2 — Time-series momentum (daily bars), long+short, w/ and w/o vol-scaling

Signals: 20/50-day MA cross, Donchian-20 breakout, 24-day momentum. All signals `.shift(1)`-ed
(decided on data through the prior close only). Vol-scaling targets 50% annualized vol using a
trailing 20-day realized-vol estimate, capped at 2x leverage, also lagged 1 bar.

| Asset | Config | Sharpe (full) | maxDD (full) | IS Sharpe / t | OOS Sharpe / t |
|---|---|---|---|---|---|
| BTC | MA20/50 [raw] | +0.33 | −53.0% | +0.64 / +0.79 | +0.00 / +0.00 |
| BTC | MA20/50 [vol-scaled] | +0.54 | −57.4% | +0.75 / +0.92 | +0.34 / +0.41 |
| BTC | Donchian-20 [raw] | +0.42 | −60.5% | +1.07 / +1.30 | −0.27 / −0.33 |
| BTC | Donchian-20 [vol-scaled] | +0.56 | −68.5% | +1.48 / +1.81 | −0.37 / −0.46 |
| BTC | 24d mom [raw] | +0.24 | −66.5% | +0.38 / +0.46 | +0.09 / +0.11 |
| BTC | 24d mom [vol-scaled] | +0.60 | −61.6% | +0.94 / +1.15 | +0.25 / +0.31 |
| ETH | MA20/50 [raw] | +0.37 | −60.8% | +0.26 / +0.32 | +0.46 / +0.56 |
| ETH | MA20/50 [vol-scaled] | +0.34 | −53.1% | +0.31 / +0.38 | +0.36 / +0.44 |
| ETH | Donchian-20 [raw] | +0.78 | −62.1% | −0.02 / −0.02 | +1.43 / +1.75 |
| ETH | Donchian-20 [vol-scaled] | +1.00 | −52.7% | +0.34 / +0.41 | **+1.64 / +2.01** |
| ETH | 24d mom [raw] | +0.67 | −59.3% | −0.09 / −0.11 | +1.29 / +1.59 |
| ETH | 24d mom [vol-scaled] | +0.98 | −50.7% | +0.21 / +0.26 | **+1.71 / +2.09** |

**BTC: no config clears any meaningful bar** (OOS t ≤ 0.41). Post-cost daily TSMOM on BTC over this
window is indistinguishable from zero.

**ETH: none of the 4 "raw"/"vol-scaled" pairs reach t≥3, but two get to t≈2.0–2.1 OOS** (Donchian-20
vol-scaled, 24d-mom vol-scaled). Two things temper this before calling it an edge:
1. **The IS half was flat-to-negative for the same configs** (Donchian raw IS Sharpe −0.02, 24d mom
   raw IS Sharpe −0.09) — the sign of "which half looks good" flipped between BTC and ETH and
   between carry and momentum, which is the signature of **regime-dependence** (ETH had a
   specific strong trending run in the back half of this window), not a stable cross-asset edge.
2. **12 configurations were screened** (3 signals × 2 vol-scaling variants × 2 assets) before
   picking out these two — a mild multiple-comparisons problem. With 12 draws, seeing 2 hit
   t≈2 is not surprising even under a null of no true edge.

**Verdict: does not clear the bar.** Flagged as a candidate worth a genuinely fresh forward test
(not a backtest re-run on the same data), not as a validated strategy.

---

## 3b. Strategy 2b — Short-horizon momentum (hourly bars, 12h/24h lookback)

Same long/short momentum signal, hourly bars, hourly funding applied per bar.

| Asset | Config | Sharpe (full) | maxDD (full) | OOS Sharpe / t |
|---|---|---|---|---|
| BTC | 12h mom [raw] | −3.08 | −99.1% | −3.00 / **−3.57** |
| BTC | 12h mom [vol-scaled] | −3.58 | −99.8% | −3.64 / **−4.20** |
| BTC | 24h mom [raw] | −2.55 | −98.3% | −2.38 / −2.86 |
| BTC | 24h mom [vol-scaled] | −2.74 | −99.4% | −2.49 / −2.90 |
| ETH | 12h mom [raw] | −1.14 | −94.8% | −0.33 / −0.38 |
| ETH | 12h mom [vol-scaled] | −1.43 | −95.4% | −0.66 / −0.78 |
| ETH | 24h mom [raw] | −2.46 | −99.6% | −2.31 / −2.72 |
| ETH | 24h mom [vol-scaled] | −2.29 | −98.8% | −2.06 / −2.37 |

**Every single hourly momentum config is negative, full-sample and OOS, both assets.** BTC 12h
momentum reaches **OOS t=−3.57 (raw) / −4.20 (vol-scaled)** — a statistically confident *loss*, not
a null result. At hourly resolution, "continuation" trading loses to realistic 6bps taker costs +
hourly funding on both assets; this reads as the market being locally mean-reverting at that
timescale once frictions are counted, consistent with the literature note in `PERPS_RESEARCH.md`
that even the *academic* TSMOM edge is a slower-horizon (12-month-lookback futures) phenomenon, not
an hourly one. **Do not trade hourly momentum on this venue/cost structure.**

---

## 4. Strategy 3 — Mean reversion (hourly RSI(14) fade, z-score(20h) fade)

RSI14: short when RSI>70, long when RSI<30, exit at RSI crossing 50. Z-score(20h): short when
z>1.0σ, long when z<−1.0σ, exit inside ±0.25σ. Both signals lagged 1 bar.

| Asset | Config | Sharpe (full) | maxDD (full) | OOS Sharpe / t |
|---|---|---|---|---|
| BTC | RSI14 fade (70/30) | −1.42 | −86.1% | −0.24 / −0.30 |
| BTC | z-score20h fade (1.0/0.25) | −1.78 | −92.9% | −1.38 / −1.76 |
| ETH | RSI14 fade (70/30) | −1.12 | −90.0% | −0.79 / −0.98 |
| ETH | z-score20h fade (1.0/0.25) | −1.98 | −98.1% | **−2.13 / −2.67** |

**No config is profitable, full-sample or OOS, either asset, either variant.** The z-score fade is
uniformly worse than RSI. This directly answers the task's ask for "actual numbers, not intuition":
the popular retail heuristic ("fade RSI extremes on the hourly") **loses money after realistic
costs** on real BTC/ETH perp data over this 3-year window — none of the 4 configurations came close
to break-even, let alone a positive edge.

---

## 5. Strategy 4 — Stop-loss / take-profit overlay

Applied to the single best post-cost OOS performer surfaced by strategies #2/#2b/#3
(`ETH 24d momentum, vol-scaled`, OOS Sharpe 1.71 — see the caveat in §3 about this being a
post-hoc pick across 12+ configs, i.e. this overlay test inherits that same selection bias).
SL/TP checked on close-to-close moves since entry (approximate — no intrabar high/low fill
assumed, since only close prices were fetched at this resolution; documented limitation).

| SL | TP | Sharpe (full) | Calmar | maxDD | annRet | t (day-clu) |
|---|---|---|---|---|---|---|
| — | — (base) | +0.98 | +0.97 | −50.7% | +49.3% | +1.69 |
| 3% | — | **+1.03** | **+1.06** | −50.7% | +53.9% | +1.78 |
| 5% | — | +0.98 | +0.97 | −50.7% | +49.3% | +1.69 |
| 8% | — | +0.98 | +0.97 | −50.7% | +49.3% | +1.69 |
| — | 5% | +0.98 | +0.97 | −50.7% | +49.3% | +1.69 |
| — | 10% | +0.98 | +0.97 | −50.7% | +49.3% | +1.69 |
| 3% | 6% | **+1.03** | **+1.06** | −50.7% | +53.9% | +1.78 |
| 5% | 10% | +0.98 | +0.97 | −50.7% | +49.3% | +1.69 |

**Finding:** most SL/TP levels tested are simply never binding — this is a *vol-scaled* daily
strategy, so single-day adverse/favorable moves rarely reach 5–8% while a position is open, meaning
the stop/target never fires and the row is identical to the base case. Only the tightest stop
tested (3%) binds occasionally, and it gives a small improvement (Sharpe 0.98→1.03, maxDD
unchanged). **Net: SL/TP overlay is immaterial-to-mildly-positive here, not clearly negative, but
also not a meaningful improvement** — consistent with this repo's broader stance (`CLAUDE.md`:
"Stop-loss exits LOSE... risk control is SIZE/pairing, never exits") in the sense that exit
heuristics are not doing real work; here they're just rarely triggered rather than actively harmful.

---

## 6. Honest limitations

1. **Single venue for both price and funding (Deribit).** Chosen deliberately for internal
   consistency (see §1), but this is one venue's funding regime. Binance/OKX/Bybit funding *levels*
   can differ; direction/sign tends to correlate across venues but was not independently verified
   here (those venues were unreachable from this sandbox — see §1 for the specific geo-block/API-cap
   evidence). Re-pull venue-specific funding before deploying capital on a different exchange.
2. **3-year window, two assets.** This spans one clear bull leg and assorted chop, but not a full
   multi-cycle bear market on this specific data pull. The BTC-vs-ETH carry sign reversal and the
   ETH-vs-BTC momentum asymmetry both suggest results are regime- and asset-specific, not a stable
   cross-market law — treat every number here as "true for BTC/ETH-on-Deribit, 2023–2026," not as a
   universal crypto-perp constant.
3. **Parameter choice was fixed a priori** (20/50 MA, Donchian-20, 24d momentum, RSI14 70/30,
   z-score20h 1.0/0.25, 50%-vol target) — these are standard textbook defaults, **not fit to this
   data**, which is the right way to avoid in-sample overfitting. But the *strategy family itself*
   (which of 2/2b/3/4 to feature, and which of 12+ configs to run SL/TP on) was chosen by looking at
   results — a milder, but real, form of selection. Flagged explicitly wherever it applies (§3, §5).
4. **SL/TP fills are close-to-close, not intrabar.** Only hourly/daily close prices were fetched;
   a true stop could fill mid-bar at a worse price than the close-based approximation used here,
   meaning realized SL slippage in live trading would likely be worse than modeled.
5. **No slippage/market-impact model beyond the flat bps assumption** — real fills, especially
   during the exact volatile moments a momentum or SL signal fires, would likely cost more than a
   constant 6bps taker assumption. All "clears the bar" verdicts above should be read as upper
   bounds on real, executed edge.
6. **Funding carry's operational risk is not modeled here** (margin calls on the short leg,
   liquidation risk breaking delta-neutrality) — `PERPS_RESEARCH.md` §4.1 covers that qualitatively;
   this doc only backtests the funding P&L + fee arithmetic, not liquidation tail risk.
7. **The day-clustered t-stat here uses one observation per calendar day** (summing intraday P&L
   for hourly strategies into daily buckets first) specifically to avoid the inflated significance
   that comes from treating 24 autocorrelated hourly observations as 24 independent ones. This
   matches this repo's own `promotion_check.py` day-clustered-t methodology, reused rather than
   inventing a laxer standard.

## 7. How to reproduce

```
python perps_backtest.py                 # uses cache at /tmp/perps_backtest_cache if present
python perps_backtest.py --refresh       # force re-fetch from Deribit
python perps_backtest.py --years 2       # shorter window
```

Cache directory (`/tmp/perps_backtest_cache/*.parquet`, override with `PERPS_CACHE_DIR`) is
**not committed** — first run fetches ~79K rows total from Deribit's public API (~2–3 min), later
runs reuse the parquet cache.
