# Crypto Mean-Reversion / Stat-Arb Research — Realism & Latency Honesty Check

**Question:** Is mean-reversion / cointegration stat-arb a realistic, capital-scalable,
costs-survivable edge for **our** setup — a cloud bot acting at **seconds-to-minutes**
latency as a **slow taker**, with **modest capital**? NOT a sub-second HFT.

**TL;DR VERDICT: NO.** The reversion that exists in crypto at minute scale is real but
**lives below our latency floor (5–15 min, bid-ask-bounce / HFT territory) and is eaten ~20x
over by taker fees.** At the horizons we can actually act on (1 hour), there is **no reversion
edge even gross** (Sharpe negative). Cointegration is detectable in-sample for a couple of
pairs (LTC/XRP, BTC/ETH) but does **not** mean-revert profitably out-of-sample after costs.
Every strategy that looks good in-sample collapses OOS — classic overfit to a single regime.

---

## Data window & costs

| Bar | Symbols | Bars | Window |
|-----|---------|------|--------|
| 1H  | BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK, LTC (10) | 8,000 | 2025-07-16 → 2026-06-14 (~11 months) |
| 15m | BTC, ETH, SOL, BNB, XRP, DOGE (6) | 8,000 | 2026-03-23 → 2026-06-14 (~83 days) |
| 1D  | same 10 | 1,200 | 2023-03-03 → 2026-06-14 (~3.3 years) |

**Source:** OKX public spot USDT candles (`/api/v5/market/history-candles`). Binance/Bybit
geo-blocked → not used. Coinbase/Kraken/dYdX reachable and cross-checked for sanity; OKX used
for the study (clean USDT spot, deep paginated history).

**Cost model (realistic slow taker):** taker fee **8 bps** + slippage **4 bps** = **12 bps per
side per leg**. A single-asset round trip = 24 bps; a 2-leg pair round trip ≈ 24 bps × (1+|β|)
notional. **Backtest discipline:** signal computed on bar **close**, position held from the
**next bar**, no look-ahead; rolling (causal) hedge ratios and z-scores; IS/OOS = 60/40 time
split; parameters picked on **IS only**, OOS reported honestly.

---

## 1 & 2. Cointegration & Pairs Stat-Arb

**Engle-Granger cointegration screen (1H log prices, full sample, in-sample):**

| Pair | β | EG t | EG p | ADF resid p |
|------|----|------|------|-------------|
| LTC/XRP | 0.96 | -5.09 | **0.0001** | 0.000009 |
| BTC/ETH | 0.67 | -5.01 | **0.0002** | 0.003 |
| ETH/XRP | 0.89 | -3.33 | 0.050 | 0.009 |
| BTC/DOGE | 0.55 | -3.29 | 0.056 | 0.014 |
| ADA/ETH | 1.61 | -3.23 | 0.066 | 0.032 |
| (all 45 pairs)… | | | most p>0.10 | |

Only **2 of 45** pairs are convincingly cointegrated in-sample (LTC/XRP, BTC/ETH). That alone
is a yellow flag: real, persistent crypto cointegration is rare and regime-dependent.

**Pairs backtest — z-score reversion (enter |z|>z_in, exit ~0), params picked by IS Sharpe,
OOS reported. Net of 12bps/side/leg:**

| Pair | IS Sharpe | IS ann | **OOS Sharpe** | OOS ann | OOS maxDD |
|------|-----------|--------|----------------|---------|-----------|
| BTC/ETH | 2.93 | +48% | **0.21** | +2% | -11% |
| ETH/SOL | 1.25 | +41% | **-0.34** | -11% | -21% |
| BTC/SOL | 0.93 | +16% | **-0.83** | -15% | -16% |
| LTC/XRP | 2.55 | +200% | **-0.58** | -17% | -16% |
| ETH/XRP | 0.92 | +35% | **0.65** | +17% | -24% |
| BTC/DOGE | -0.39 | -12% | **-2.00** | -42% | -20% |

**Finding:** in-sample Sharpes of 1–3 evaporate (or invert) out-of-sample. The "best" OOS
result, ETH/XRP at Sharpe 0.65, is one config out of dozens tested and not robust. **The spread
does not mean-revert at hour horizon:** the best pair's OU half-life is **~1,560 hours (~65
days)** — effectively a random walk, not a tradeable reversion. Pairs stat-arb is **not** a
costs-survivable edge for us here.

---

## 3. Time-Series Mean-Reversion (single asset)

Fade overextension via rolling z-score; slow taker, next-bar fill, 24 bps round trip.

| Bar | Sym | IS Sharpe | **OOS Sharpe** | OOS ann | trades |
|-----|-----|-----------|----------------|---------|--------|
| 1H | BTC | -2.17 | **-2.81** | -58% | 466 |
| 1H | ETH | -0.52 | **-1.74** | -41% | 274 |
| 1H | SOL | -0.55 | **-2.32** | -72% | 1315 |
| 15m | BTC | -5.95 | -0.73 | -18% | 357 |
| 15m | ETH | -5.96 | -1.62 | -44% | 233 |
| 15m | SOL | -4.10 | +2.24* | +115%* | 165 |

\*SOL 15m OOS +2.24 is a single lucky config on 83 days / 165 trades — selection noise, not a
real edge. Everything else is firmly negative net of costs.

---

## 4. Residual / Cross-Sectional Reversion (alt regressed on BTC, market-neutral)

Trade the reversion of each alt's residual vs BTC. Net of costs, IS/OOS.

| Alt | IS Sharpe | **OOS Sharpe** | OOS ann |
|-----|-----------|----------------|---------|
| ETH | 1.51 | -0.23 | -7% |
| BNB | 2.45 | 0.05 | -3% |
| XRP | 1.46 | -1.51 | -41% |
| LINK | 2.81 | -1.78 | -32% |
| AVAX | 3.37 | **1.37** | +39% |
| LTC | 1.39 | 0.58 | +9% |

Same story: strong IS, mostly negative OOS. AVAX OOS 1.37 is the best of 9 alts × 9 configs =
81 trials — pure multiple-testing noise, not a deployable signal.

---

## 5. LATENCY HONESTY CHECK — where does the edge live?

**Lag-1 autocorrelation of non-overlapping returns by horizon** (negative = reversion):

| Series | 15m | 30m | 45m | 1.5h | 3h | 6h |
|--------|-----|-----|-----|------|----|----|
| BTC | **-0.046** | -0.039 | -0.036 | -0.020 | -0.050 | -0.030 |
| ETH | **-0.017** | -0.023 | -0.028 | -0.025 | +0.001 | -0.002 |
| SOL | **-0.020** | -0.021 | -0.029 | -0.050 | -0.005 | -0.022 |
| **1H** BTC | +0.003 | -0.012 | +0.017 | +0.018 | -0.008 | +0.001 |
| **1H** ETH | +0.019 | +0.009 | +0.033 | +0.019 | -0.005 | +0.026 |
| **1H** SOL | +0.010 | +0.003 | +0.056 | +0.033 | -0.010 | -0.023 |

**The crossover is decisive:**
- At **15 minutes**, returns are **reliably negatively autocorrelated** (-0.02 to -0.05) → real
  short-horizon reversion exists. **Gross** (zero-cost) it is highly profitable:

  | 15m TS-reversion (lb24, z1.5) | GROSS Sharpe | **NET (24bps) Sharpe** | NET ann |
  |--------|-------------|------------------------|---------|
  | BTC | **+3.64** | **-14.9** | -99% |
  | ETH | **+2.56** | **-11.6** | -99% |
  | SOL | **+1.18** | **-12.2** | -99% |

- At **1 hour** (our actionable horizon), autocorrelation is **~zero / slightly positive** —
  the reversion is gone. Even **gross** 1H reversion is **negative** (Sharpe -0.44/-0.67/-0.65).

**Edge-vs-cost arithmetic (the kill shot):**

| 15m | ρ(lag1) | bar σ | est. gross edge/trade | round-trip cost | result |
|-----|---------|-------|-----------------------|-----------------|--------|
| BTC | -0.046 | 22 bps | ~1.5 bps | 24 bps | **fee-eaten (16×)** |
| ETH | -0.017 | 29 bps | ~0.7 bps | 24 bps | **fee-eaten (34×)** |
| SOL | -0.020 | 31 bps | ~1.0 bps | 24 bps | **fee-eaten (24×)** |

The reversion signal is worth **~1 bp per trade** and we must pay **24 bps** to take it as a
slow taker. This is the textbook signature of an **HFT-mined, bid-ask-bounce** effect: capturable
only by a maker (earning the spread) or a sub-second taker, **neither of which we are**. The edge
literally lives in the price oscillation we cross when we cross the spread.

---

## 5b. Capacity & Feasibility

Capacity is **not** the binding constraint — the edge fails on costs/latency first. For
reference, median daily $-volume on OKX: ETH ~$444M, XRP ~$46M, BTC multi-$B. A pairs book at
hour horizon could absorb low-single-digit $M without material impact. But with OOS Sharpe ≤ ~0
after costs, scalable capacity is moot: **there is no edge to scale.**

---

## 6. VERDICT

**No realistic, costs-survivable, latency-appropriate reversion/stat-arb edge exists for our
setup.**

- **Pairs/cointegration:** only LTC/XRP and BTC/ETH cointegrate in-sample; neither mean-reverts
  profitably OOS after costs (best honest OOS Sharpe ~0.2–0.65 on cherry-picked configs; spread
  half-life ~65 days = random walk). **Not deployable.**
- **Time-series & residual reversion:** strong in-sample, **negative out-of-sample after costs**
  across the board. Lone positives (SOL-15m, AVAX-residual) are multiple-testing noise.
- **The latency truth:** genuine reversion exists at **5–15 min** (gross Sharpe 1.2–3.6) but is
  **fee-eaten ~20–34×** for a slow taker (~1 bp edge vs 24 bp cost). At **1 hour** — the fastest
  horizon our cloud/taker setup can reliably act on — **the reversion is gone even gross.**

**Bottom line:** the reversion edge is real but it is **sub-our-latency and fee-eaten**. To
monetize it you must be a **maker** (post limit orders, earn the spread, manage adverse
selection) or operate **sub-second** — a different business than a seconds-to-minutes cloud
taker. We should **not** pursue mean-reversion / stat-arb as configured.

*Caveats: 11 months of 1H is one macro regime; 15m is only ~83 days. Costs assume retail-ish
OKX taker tiers. A maker-rebate or co-located study is out of scope and is precisely the regime
where the 15m edge might flip positive — but that is not our setup.*
