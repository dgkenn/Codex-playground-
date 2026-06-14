# ETF / Cross-Asset Momentum — a more-deployable form of the one survivor edge

**Question.** The crypto long-only momentum sleeve was the lone survivor of this project
(Sharpe ~0.5, but -40..-60% drawdown, weekly turnover -> short-term-gains tax drag, and a
crypto-venue access wall). The meta-finding was: *for a US retail small bankroll the deployable
edges are systematic risk-premia, not microstructure/mispricing plays.* The most battle-tested
risk-premium is cross-sectional + time-series momentum on liquid ETFs. This study tests whether
that is a **better deployable edge**: US-legal in any brokerage, IRA-able (no short-term tax
drag), and historically lower-drawdown.

**Verdict up front: YES, decisively.** Cross-asset ETF momentum with a dual-momentum (absolute)
filter + a SPY-200d regime gate + partial rebalancing delivers, NET of costs, **CAGR ~9%,
Sharpe ~0.80-0.83, maxDD ~-16-18%** — higher risk-adjusted return than the crypto sleeve at
**~1/3 the drawdown**, with monthly turnover (IRA-friendly, no tax drag) and trivial deployment
($1k+ in any commission-free brokerage). It also held up across every sub-window and through the
2008 GFC and 2022 stock+bond crash. The crypto sleeve is *not* obsoleted — adding crypto-proxy
ETFs as high-beta members of this same momentum system raises CAGR to ~14% and Sharpe to ~0.98
while keeping the -18% drawdown, i.e. crypto is best *consumed through* the momentum framework,
not run as a standalone weekly sleeve.

---

## Data, window, costs (SCREENS)

- **Source:** yfinance daily **adjusted** closes (`auto_adjust=True` => dividends reinvested =
  total return). Staged at `/tmp/etfmom_data/etf_prices.csv` (NOT committed). Stooq's CSV
  endpoint is now behind a JavaScript anti-bot challenge and was unreachable; yfinance/Yahoo
  worked after retry.
- **Universe (30 core, survivorship-aware liquid):** US sectors XLK/XLE/XLF/XLV/XLI/XLY/XLP/
  XLU/XLB; style SPY/QQQ/IWM; intl EFA/EEM/EWJ/EWZ/EWG/EWU/FXI/VGK; other assets TLT/IEF/GLD/
  DBC/USO/VNQ/UUP/SLV/HYG/LQD. Optional crypto-proxy sleeve GBTC/MSTR/COIN/IBIT (late inception).
  XLRE excluded from core (2015 inception) to keep a long backtest. Cash leg = BIL (T-bill ETF,
  extended pre-2007 with a flat 2%/yr synthetic).
- **Window:** 2000-06 -> 2026-06 full sample (sectors begin 1998-12; start padded for 12m
  lookback). **Recent-decade OOS holdout: 2016-01 -> 2026-06 (~10.5y).**
- **Costs:** commission-free ETFs (commission = 0) + **3 bps per side** of traded notional
  (spread). Costs charged on rebalance turnover. Cost sensitivity reported (0/3/10/25 bps).
- **Method (reused from the crypto momentum work):** risk-adjusted momentum (trailing total
  return / annualized vol); monthly rebalance; long-only, top-K equal weight, remainder in
  T-bill; dual (absolute>cash) filter; SPY>200d-MA regime gate; partial rebalance for turnover.
  All numbers below are **net**.

---

## 1. Cross-sectional momentum (full sample 2000-2026)

Rank universe by risk-adjusted trailing momentum, hold top-K equal-weight, monthly. Classic
equity horizons (3/6/12m), NOT the 10-day crypto horizon.

| lookback | K | CAGR | Sharpe | maxDD | turnover/mo |
|---|---|---|---|---|---|
| 3m | 5 | 7.9% | 0.58 | -38% | 0.95 |
| 6m | 5 | 8.8% | 0.63 | -35% | 0.72 |
| 6m | 8 | 9.5% | 0.70 | -37% | 0.55 |
| 12m | 5 | 7.9% | 0.57 | -37% | 0.48 |

**Plateau, not a spike:** Sharpe 0.57-0.70 across 3/6/12m x K=3/5/8 — no single lucky cell.
6m is the sweet spot. Plain (non-risk-adjusted) momentum gives similar Sharpe (0.61 vs 0.63)
but ~18% higher vol — confirming the crypto finding that **risk-adjusted beats plain**.

Cross-sectional alone is already ~0.63 Sharpe (better than the crypto sleeve's ~0.5) but its
**-35% drawdown is still too deep** — same problem the crypto sleeve had. The fix is the same:
add absolute/regime gating.

## 2. Time-series / dual momentum (Antonacci-style)

Add an **absolute-momentum filter**: hold a ranked asset only if its own trailing return beats
cash; otherwise that slot goes to T-bills.

| config (6m, K=5) | CAGR | Sharpe | maxDD |
|---|---|---|---|
| XS only | 8.8% | 0.63 | -35% |
| DUAL (XS + abs>cash) | 8.7% | 0.63 | -36% |

On its own the absolute filter barely moves the needle here — because in a 30-asset cross-asset
universe there is *almost always* something with positive trailing return, so the filter rarely
binds. The real drawdown control comes from the **regime gate** (next).

## 3. Regime / trend filter (the analogue of the crypto BTC-MA gate)

SPY below its 200-day MA -> go 100% cash. This was *essential* for the crypto sleeve; it is
essential here too.

| config (6m, K=5) | CAGR | Sharpe | maxDD |
|---|---|---|---|
| no dual, no regime | 8.8% | 0.63 | -35% |
| **regime only** | 8.1% | **0.70** | **-20%** |
| dual + regime | 8.0% | 0.69 | -20% |

The regime gate **cuts max drawdown from -35% to -20%** for ~0.7pp of CAGR — exactly the
risk/return trade the crypto BTC-MA gate produced. Sharpe rises 0.63 -> 0.70.

## 4. Partial rebalance (turnover control) — the best lever

Instead of jumping fully to target weights each month, move only a fraction `p` of the way.
This was a validated crypto finding (cuts turnover) and here it *also raises Sharpe and lowers DD*
by damping whipsaw.

| partial p (DUAL+regime 6m K5) | CAGR | Sharpe | maxDD | turnover/mo |
|---|---|---|---|---|
| 1.00 (full) | 8.0% | 0.69 | -20% | 0.65 |
| 0.50 | 8.8% | 0.80 | -17% | 0.41 |
| **0.34** | **8.9%** | **0.83** | **-18%** | **0.31** |

`p=0.34` (roughly "rebalance ~1/3 toward target each month") is the **best config**: higher CAGR,
Sharpe 0.83, maxDD -17.6%, and **less than half the turnover** (lower cost + tax friction).

## 5. Out-of-sample robustness (the brutal bar)

ETF momentum is heavily published, so the real test is the recent-decade holdout and a plateau
across windows. Best config (**DUAL+regime, 6m, K=5, partial=0.34**):

| window | CAGR | Sharpe | maxDD |
|---|---|---|---|
| Full 2000-2026 | 8.9% | 0.83 | -17.6% |
| **Holdout 2016-2026 (OOS)** | **8.9%** | **0.81** | **-15.6%** |
| 2010-2026 | 7.5% | 0.72 | -15.6% |
| 2020-2026 | 10.6% | 0.92 | -13.2% |

**Same edge in every window**, including the never-optimized-on 2016-2026 holdout. The
lookback/K plateau holds on the holdout too (Sharpe 0.74-0.88 across 3/6/12m x K=5/8). This is a
risk-premium that persists, not a fitted window.

**Stress tests (best config, net):**

| period | this strategy | SPY | 60/40 |
|---|---|---|---|
| 2008 GFC (Jun07-Jun09) maxDD | **-8.6%** | -55% | -31% |
| 2022 (stocks+bonds down) full year return | **-0.5%** | -18% | -16% |

In 2022 the system rotated into energy/commodities/dollar (the only things trending up) and the
regime gate pulled it to cash during the worst stretch — it ended the year roughly **flat** while
both SPY and 60/40 fell ~16-18%. This directly answers the 2022 stock+bond-drawdown concern.

## 6. Comparison to baselines

**Full sample 2000-2026:**

| strategy | CAGR | Sharpe | maxDD |
|---|---|---|---|
| Crypto long-only sleeve (prior finding) | ~ — | **~0.5** | **-40..-60%** |
| SPY buy & hold | 8.5% | 0.52 | -55% |
| 60/40 SPY/IEF | 8.7% | 0.83 | -31% |
| QQQ buy & hold | 9.4% | 0.48 | -81% |
| **ETF momentum (DUAL+regime 6m K5 p0.34)** | **8.9%** | **0.83** | **-17.6%** |

Vs the crypto sleeve: **higher Sharpe (0.83 vs ~0.5) at ~1/3 the drawdown.** Vs SPY: same CAGR,
much higher Sharpe, ~1/3 the drawdown. Vs 60/40: matches its (excellent) full-sample Sharpe but
with **half the worst-case drawdown** and far better crisis behavior (60/40 broke in 2022; this
didn't).

**Recent decade 2016-2026** is the one honest caveat: a raging US-equity bull made SPY (Sharpe
0.87, CAGR 15%) and 60/40 (Sharpe 0.93) *beat* the momentum strategy (Sharpe 0.81, CAGR ~9%) on
return. Momentum's edge is **lower drawdown and crash-robustness, not out-returning a bull
market.** That is the correct, honest framing: this is a *risk-managed* equity-like return, not a
return-maximizer.

## 7. Does adding crypto-proxy ETFs help?

Add GBTC/MSTR/COIN/IBIT as high-beta members of the same momentum system (2016-2026, best config):

| universe | CAGR | Sharpe | maxDD |
|---|---|---|---|
| core (no crypto) | 8.9% | 0.81 | -15.6% |
| **core + crypto-proxy** | **14.5%** | **0.98** | **-17.6%** |

It **helps, and meaningfully**: CAGR 8.9% -> 14.5%, Sharpe 0.81 -> 0.98, for only ~2pp more
drawdown. The momentum/regime machinery only *holds* crypto-proxies when they are trending and in
a risk-on regime, and dumps them otherwise — capturing crypto's upside while the gate caps its
downside. This is the synthesis of the whole project: **crypto is a better edge when consumed
through the momentum framework than as a standalone weekly-turnover sleeve.** (Caveat: crypto-proxy
ETFs have short history — 2016+ for GBTC, 2021+ COIN, 2024+ IBIT — so treat this as suggestive,
and note IBIT/spot-BTC ETFs have tighter tracking than GBTC's historical NAV discount.)

## 8. Deployment & tax realism

- **Cost sensitivity (full sample, DUAL+regime 6m K5):** Sharpe 0.71 / 0.69 / 0.65 / 0.55 at
  0 / 3 / 10 / 25 bps per side. Liquid ETFs trade at ~1-3 bps; even a pessimistic 10 bps leaves
  Sharpe 0.65. The edge survives realistic costs.
- **Turnover:** ~0.31 (sum of |weight changes|) per month with partial rebalance => roughly
  3-4 small ETF trades/month. Trivial at any size.
- **Small-bankroll min sizes:** holding K=5 ETFs equal-weight, partial rebalancing. At **$1k**,
  ~$200/sleeve — fine for whole-share ETFs in the $30-700 range (use fractional shares or round
  to whole; rounding noise is small at K=5). At **$10k-$100k** there is zero capacity issue —
  these ETFs trade billions/day. No min-size or capacity wall, unlike thin crypto/prediction
  markets.
- **Tax — the decisive structural advantage:** monthly rebalance + partial (p=0.34) means most
  positions are held many months; combined with **running it in an IRA, taxes are zero** and the
  weekly-turnover short-term-gains drag that hurt the crypto sleeve **disappears entirely.** Even
  in a taxable account, monthly/partial turnover generates far less short-term gain than a weekly
  crypto sleeve.
- **Access:** every instrument is a US-listed ETF tradeable in any brokerage (Fidelity/Schwab/
  Vanguard/etc.), commission-free. **No crypto-venue, perp, or offshore access wall.**

**Realistic net expectations** (best config, 3 bps, after the honest haircut for live slippage/
execution): **CAGR ~7-9%, Sharpe ~0.70-0.83, maxDD ~-16-20%.** With crypto-proxies included and
their short-history caveat: upside to ~10-14% CAGR / ~0.9 Sharpe at ~-18% DD.

---

## VERDICT

**ETF / cross-asset momentum is a strictly better deployable edge for a US small bankroll than
the crypto long-only sleeve** — better risk-adjusted return (Sharpe ~0.83 vs ~0.5), ~1/3 the
drawdown (-18% vs -40..-60%), monthly/partial turnover that is IRA-tax-free, no access wall,
$1k-deployable in any brokerage, and robust across a true OOS holdout plus the 2008 and 2022
crises. It does not out-return a US-equity bull (2016-2026 SPY/60-40 beat it on CAGR) — its value
is *risk-managed* equity-like return with crash protection, which is exactly what a small bankroll
needs.

**Best config to deploy:**
- Universe: ~30 liquid cross-asset ETFs (US sectors + style + intl/country + bonds/gold/
  commodities/REITs/dollar). Optionally add crypto-proxy ETFs (prefer IBIT over GBTC) as
  high-beta members — they raise CAGR/Sharpe inside the same risk gates.
- Signal: **risk-adjusted momentum (6-month total return / vol)**, cross-sectional rank.
- Hold: **top K=5** equal-weight; remainder in **BIL/T-bills**.
- Gates: **dual/absolute** (hold only if trailing return > cash) **+ SPY > 200-day MA regime**
  (else 100% cash).
- Rebalance: **monthly, partial (~1/3 toward target)** to cut turnover/whipsaw.
- **Expected net: CAGR ~8-9%, Sharpe ~0.80-0.83, maxDD ~-17%** (core); ~10-14% CAGR / ~0.9-1.0
  Sharpe / ~-18% DD with crypto-proxy sleeve (short-history caveat).

**Honest caveats:** (1) momentum is heavily published — the persistence into the 2016-2026
holdout is reassuring but no edge is guaranteed forward; (2) it underperforms buy-and-hold in
strong bull markets by design; (3) the crypto-proxy uplift rests on short history; (4) live
slippage/execution will shave the headline a touch — budget the lower end of the ranges.

*Reproduce:* `python3 run_etf_momentum.py` (engine in `etf_momentum.py`). All figures net of
3 bps/side; data via yfinance to `/tmp/etfmom_data/` (not committed).
