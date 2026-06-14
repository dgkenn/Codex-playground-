# Crypto Perp Funding-Rate Carry — Realism Screen

**Date:** 2026-06-14  **Author:** research agent  **Branch:** claude/polymarket-bot-live-ready-vw7ut5

## Question
Is delta-neutral perp **funding-rate carry** (cash-and-carry / funding harvest) a realistic,
costs-survivable, capital-scalable edge for *our* setup — a cloud bot with **seconds latency**
(not HFT), modest capital, API keys + capital on 1–2 venues? The appeal: funding is *slow*
(paid every 8h on OKX), needs no speed, and scales with notional. The risk: crypto is efficient
and this trade is crowded.

## Data (state explicitly — this is a SCREEN)
- **Source:** OKX public `funding-rate-history` (USDT perps) + `market/candles` (spot). dYdX
  `indexer` for a cross-venue OI/funding snapshot. **Binance/Bybit deliberately NOT used (geo-blocked 451/403).**
- **Window:** **94 days, 2026-03-12 → 2026-06-14**, 283 funding payments/asset.
  OKX's public funding-history **hard-caps at ~3 months** (paging past 2026-03-12 returns 0 rows),
  and dYdX's public indexer only exposes *next* funding, no long history. So this is **one quarter**,
  and it happens to be a **calm / low-funding regime**. 2024–2025 bull-market funding ran far hotter
  (8–20%+ annualized); this screen is therefore conservative-to-pessimistic on the rate, but the
  *cost structure conclusions are regime-independent*.
- **Funding interval:** 8h → **1,095 payments/yr**. Annualization = mean(8h rate) × 1095.
- **Assets:** BTC, ETH, SOL, XRP, DOGE, AVAX, LINK, ADA.
- **Scripts:** `fetch_funding.py` (data), `analyze_funding.py` (characterization + backtests),
  `carry_economics.py` (holding-period / breakeven economics).

## Cost model (per delta-neutral position)
A delta-neutral carry = **2 legs** (long spot + short perp). Open = 2 fills, close = 2 fills →
**4 fills round-trip**. Per-fill cost = exchange fee + basis slippage. Scenarios:

| Scenario | per-fill | round-trip (4 fills) |
|---|---|---|
| Taker both legs + slip | 8 bps | **32 bps** |
| Taker/maker mix | 5 bps | 20 bps |
| Maker both + slip (passive, seconds latency OK) | 3 bps | **12 bps** |

We do **not** churn — the realistic strategy is *enter once, hold, collect cumulative funding, exit.*

---

## TASK 1 — Funding characterization (annualized)

| asset | mean_ann | median_ann | std_ann | %positive | autocorr(1) | sign-persist | mean 8h (bps) |
|---|---|---|---|---|---|---|---|
| BTC  | 1.54% | 1.47% | 0.15% | 61% | 0.47 | 0.68 | 0.14 |
| ETH  | 2.05% | 3.04% | 0.19% | 64% | 0.52 | 0.71 | 0.19 |
| SOL  | **−0.84%** | −0.14% | 0.28% | 49% | 0.55 | 0.62 | −0.08 |
| XRP  | 2.50% | 3.14% | 0.23% | 62% | 0.26 | 0.62 | 0.23 |
| DOGE | **3.99%** | 4.86% | 0.20% | 73% | 0.27 | 0.68 | 0.36 |
| AVAX | 1.42% | 3.79% | 0.31% | 63% | 0.33 | 0.66 | 0.13 |
| LINK | 2.63% | 4.09% | 0.24% | 67% | 0.31 | 0.68 | 0.24 |
| ADA  | 2.09% | 8.02% | 0.36% | 67% | 0.38 | 0.66 | 0.19 |

**Findings.** (1) Funding is **mostly positive** (~60–73% of periods) for everything except SOL,
which went net-negative this window — confirming the long-pays-short bias that makes
short-perp/long-spot the natural carry. (2) **Persistence is high**: lag-1 autocorrelation 0.26–0.55 and
same-sign-next-period 0.62–0.71 — funding does *not* whipsaw randomly; once positive it tends to stay
positive. This is good for a *hold* strategy and terrible justification for churning. (3) **Magnitudes are
tiny** in this regime: mean 8h funding **0.13–0.36 bps**; annualized **1.5–4%** (DOGE best, SOL negative).

---

## TASK 2 — Net carry after costs (buy-&-hold, single round trip)

Hold short-perp/long-spot the full 94d, collect cumulative funding, pay ONE round trip:

| asset | gross_ann | net@32bps | net@20bps | net@12bps | breakeven hold (12bps) |
|---|---|---|---|---|---|
| BTC  | 1.54% | 0.3% | 0.8% | 1.1% | 28 d |
| ETH  | 2.05% | 0.8% | 1.3% | 1.6% | 21 d |
| SOL  | −0.84% | −2.1% | −1.6% | −1.3% | never |
| XRP  | 2.50% | 1.3% | 1.7% | 2.0% | 18 d |
| DOGE | **3.99%** | 2.8% | 3.2% | **3.5%** | 11 d |
| AVAX | 1.42% | 0.2% | 0.6% | 1.0% | 31 d |
| LINK | 2.63% | 1.4% | 1.9% | 2.2% | 17 d |
| ADA  | 2.09% | 0.9% | 1.3% | 1.6% | 21 d |
| **BASKET (eq-wt)** | **1.92%** | **0.68%** | **1.15%** | **1.46%** | ~21 d |

**The decisive fact:** 8h funding (0.13–0.36 bps) is **~30–250× smaller than one round trip**
(12–32 bps). You must **hold for 11–82 days** just to cover entry+exit. So the trade only works as a
*slow buy-and-hold of the carry* — and any turnover is fatal.

**What turnover does to it (`analyze_funding.py`, "mode A thr=0" = flip whenever sign flips):**
flipping the 2-leg book on every funding sign-change generates **700–830 round trips/yr** and turns a
+2% gross into **−100%+/yr net**. Threshold/hysteresis "fixes" it only by trading almost never
(thresholds above mean funding ⇒ 0 trades). **Cross-sectional rotation** (harvest top-K highest-|funding|
assets, re-selecting each period) is also strongly **net-negative** (−75% to −91%/yr) for the same
turnover reason. Conclusion for Task 3: **conditional/cross-sectional harvesting does NOT beat
buy-and-hold here — it loses to costs.** The only viable form is *pick persistently-positive assets,
enter once, hold.*

---

## TASK 3 — Conditional / cross-sectional carry
- **Threshold ("only when |funding| high")**: in this regime mean funding (~0.2 bps/8h) is far below
  any threshold that would reduce turnover, so thresholds either (a) trade like always-on and bleed costs,
  or (b) set above the mean and trade ~never. No improvement.
- **Cross-sectional top-K rotation**: net **−75% to −91%/yr** — the re-selection churn dominates.
- **What actually helps:** select assets with **high %-positive + high persistence** (DOGE 73%/0.68,
  LINK 67%/0.68, XRP 62%) and **avoid SOL** (49%, went negative). Static asset selection + hold beats
  every dynamic variant after costs.

---

## TASK 4 — Capacity & feasibility

**Capacity is NOT the binding constraint.** OKX BTC-USDT-SWAP open interest ≈ **$2.0B**, top-of-book
≈ $8M; even $100k is a rounding error with negligible impact. Funding is paid on full notional, so the
edge scales **linearly with capital** with no meaningful slippage penalty at our scale. The binding
constraint is the **rate**, not depth.

**$/day at realistic net rates (funding paid on notional):**

| capital | basket net ~1.0%/yr | best-asset (DOGE) net ~3.5%/yr | hot-regime gross ~12%/yr (2024-style) |
|---|---|---|---|
| $1,000   | $0.03/day | $0.10/day | $0.33/day |
| $10,000  | $0.27/day | $0.96/day | $3.29/day |
| $100,000 | $2.74/day | $9.59/day | $32.9/day |

**Benchmark: the Kalshi box ≈ $27/day.** To match it via funding carry you need roughly:
**~$1M** at the basket rate, **~$280k** at the best-asset rate, or **~$80k only if funding returns to a
hot 2024-style regime.** At $1k–$10k of capital, carry yields **cents to <$1/day** in this regime.

**Operational reality (the hidden costs the table doesn't show):**
- **Two legs, two risk surfaces.** Spot + perp must stay matched. A perp **liquidation** (if the short
  perp's margin is exhausted by an up-move while spot collateral sits elsewhere) breaks delta-neutrality
  and can wipe weeks of carry in one candle. Requires conservative leverage (≤2–3×) and active margin
  top-ups → *more* operational latency-sensitivity than the "slow" framing implies.
- **Funding-flip risk.** SOL demonstrates funding can go *negative* and stay there; a held short-perp then
  *pays* funding. You must monitor and be willing to exit (paying another round trip).
- **Capital efficiency.** Delta-neutral ties up capital on both legs (full spot notional + perp margin),
  so realized return on *deployed* capital is below the headline notional rate.
- **Venue/KYC/custody.** Real keys + real capital on a non-US-friendly exchange (OKX) — the very venues
  with deep perps are the ones with geo/KYC friction; the reachable-here ones (dYdX/Hyperliquid) have
  thinner books and their own funding dynamics.

---

## TASK 5 — VERDICT

**Funding carry is REAL but NOT a worthwhile edge for our setup at our capital.** It is genuinely
slow, latency-insensitive, and infinitely capital-scalable on the venue side — it fails on **rate**, not
on feasibility or capacity.

- **Net annualized:** ~**1.0% basket / ~3.5% best single asset (DOGE)** after realistic costs, in this
  94-day calm regime. Gross only 1.5–4%/yr.
- **Sharpe:** the carry itself is near-riskless when held delta-neutral (8h vol ~0.5–1 bp → annualized
  return/vol is high *in theory*), **but** the realized Sharpe is dominated by the un-modeled tail risks
  (liquidation, funding flip, depeg, leg-break), which a 94-day screen cannot capture. Do **not** trust a
  headline Sharpe here.
- **Capacity:** effectively unlimited at our scale ($2B OI). To clear the **$27/day Kalshi bar** you need
  **~$1M** (basket) / **~$280k** (best asset) — far beyond "modest capital." At $1k–$10k it's **cents/day.**
- **Why it under-delivers:** funding per period (0.1–0.4 bps) is ~30–250× smaller than one round trip
  (12–32 bps), forcing multi-week holds; any churn (threshold/cross-sectional rotation) goes deeply
  net-negative; and the trade is crowded, so the rate is compressed precisely in calm regimes like this one.

**Recommendation: NO — do not build funding carry as a primary edge.** It does not beat the Kalshi box
unless (a) we deploy **6-figure+ capital** AND (b) funding returns to a hot regime — neither of which fits
"modest capital, costs-survivable now."

**If revisited later, the concrete next step is data, not code:**
1. Get a **longer, multi-regime funding history** (12–24 months across a full bull/bear cycle) — paid data
   (Coinglass/Amberdata) or scrape Hyperliquid's historical funding, since OKX's public window is capped at
   3 months. The 2024 bull regime is where the edge actually lived.
2. Add **basis** (perp − spot price) history to model true entry/exit slippage and convergence risk, not a
   flat bps assumption.
3. Only then re-screen with a **liquidation-aware** P&L (model margin, leverage, max adverse excursion).
Until that data exists and a hot regime returns, **keep the capital on the Kalshi box.**
