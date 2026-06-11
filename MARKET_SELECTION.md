# Market selection — does another Kalshi series beat KXBTC15M per DAY?

The decisive metric is **net P&L per DAY**, not per box. A fat box margin is worthless if the
series has few liquid windows or thin volume. We tested two halves: (A) offline per-day economics on
the four underlyings we have history for, (B) a live API breadth scan across tenors/index series.

## ⭐ Part A — cross-underlying, offline, per-DAY (btc/eth/sol/xrp 15m, real book+tape)
Ran our own `collect_fills` machinery per asset at q0=0 (idealized front-of-queue) and q0=2000
(realistic queue displacement), aggregated `settle` per window, scaled to per-day.

**q0=0 (idealized front-of-queue):**

| asset | days | windows/day | %win liquid | box margin ¢ | pair rate | mean ¢/win | **net ¢/DAY** |
|-------|------|-------------|-------------|--------------|-----------|------------|---------------|
| btc   | 29.9 | 38.7 | 97.7% | 1.00 | 0.997 | +1.75 | **+67.8** |
| eth   | 30.0 | 39.4 | 99.8% | 1.00 | 0.999 | −12.3 | −486 |
| sol   | 30.0 | 38.0 | 60.7% | 1.00 | 0.994 | −19.6 | −747 |
| xrp   |  4.2 | 41.1 | 97.7% | 1.50 | 0.994 | −11.7 | −480 |

**q0=2000 (realistic queue):** ALL four negative; ETH pair-rate craters to 0.20, SOL/XRP below 0.07
(fills don't arrive at usable prices); BTC −1693 ¢/day. (q0=2000 is more pessimistic than our LIVE
effective queue — live BTC is viable — so read q0=2000 as the cross-asset *stress* comparison, not
the absolute level.)

### Verdict A — BTC wins per-DAY, decisively; the other underlyings are structurally toxic
- **BTC is the ONLY book that's positive even idealized (+68¢/day at q0=0).** ETH, SOL, XRP LOSE money
  even at front-of-queue — adverse flow is baked into those books, not a queue-position artifact.
  Switching underlying makes us WORSE on both a per-box and per-day basis.
- The operator's intuition is correct and load-bearing: **15-min BTC's liquidity is not just
  convenience — it IS the edge.** The thinner books (sol/xrp: 6–61% of windows even liquid at
  realistic queue) give wider headline margins but can't be filled, and what does fill is toxic.
- So: do NOT migrate to ETH/SOL/XRP. The per-day case for them is strongly negative.

## Part B — live tenor / non-crypto breadth scan (Kalshi REST, ~600 series enumerated, 2026-06-11)
Enumerated the full series catalogue (Crypto, Financials, Economics, Commodities, FX) and sampled
every candidate with open markets:

| series | tenor | 24h vol | OI | touch box ¢ | depth@touch |
|--------|-------|---------|-----|-------------|-------------|
| **KXBTC15M** | 15m | **$240,182** | $147,932 | 1.0 | $914/$137 |
| KXETH15M | 15m | $7,014 | $4,767 | 2.0 | $530/$17 |
| KXCPIYOY | monthly | $1,295 | $461 | 1.0 | $23/$6 |
| KXPCECORE | monthly | $0 | $1,385 | 1.0 | $3/$200 |
| KXEURUSD | daily range | $67 | $67 | 3.0 | $0/$45 |
| KXEURUSDW | weekly | $0 | $2 | (empty book) | — |

The headline finding is what ISN'T tradeable: **every high-frequency non-crypto series — S&P
hourly/daily (KXINXI/KXINXU/KXINXAB/KXINXZ), Nasdaq hourly/daily, FX hourlies (EUR/GBP/AUD), gold
daily, BTC hourly (KXBTCD) and BTC daily range (KXBTC) — had NO open markets at scan time.** The
series exist in the catalogue but are dormant/sunset or only intermittently listed. The few live
non-crypto books (CPI monthly, EUR/USD daily) have 1-3¢ margins on effectively zero volume and
single-digit-dollar depth — a box needs BOTH sides to trade through our prices, which simply does
not happen there.

### Part B2 — dedicated non-crypto / slow-tenor deep scan (second independent agent, same day)
A second scan focused on non-crypto + daily/hourly confirmed and sharpened the picture:
- **Cadence is the structural killer**: KXBTC15M fires 96 windows/day; everything else is 1/day
  (FX, index dailies) or 1/week-month (KXINX, CPI) — a 96-672× collapse in opportunities before
  liquidity even enters.
- **Wide margins are illiquidity artifacts**: KXEURUSD shows 48-59¢ gross box margins ATM — with
  depth of ONE contract per side and zero volume. Even captured, 1 box/day ≈ 51¢ < the 68¢ bench.
- **The both-sides-fill structure breaks outside short tenors**: a daily binary pins near 0 or 1
  for most of the session; both bids fill profitably only while price lingers at the strike —
  briefly, once, unpredictably. The 15-min reset is what keeps both sides live; this is structural,
  not a liquidity accident.
- **Fees**: non-crypto series return fee_type=None from the API; if the standard maker schedule
  applies (~0.44¢ round-trip at p=0.5) it's material against 1-3¢ index margins. Only CRYPTO15M's
  $0 is confirmed.
- Watch items only (no collector warranted): KXNASDAQ100's deep-OTM T29000 (~7.8k/24h real volume,
  1-3¢ margin) and weather dailies if they reopen for hurricane season.

### Verdict B — nothing beats KXBTC15M; the venue question is CLOSED
KXBTC15M has ~34× the volume of the next-most-liquid candidate (its own ETH sibling, which Part A
showed is a structural money-loser anyway). Wider margins elsewhere (2-3¢) are an illiquidity
artifact, not harvestable edge — and maker fees outside CRYPTO15M are unconfirmed, which would only
make those margins worse. 15-min BTC is the sweet spot on BOTH axes: the only tenor with continuous
two-sided flow, and the only underlying whose book isn't structurally toxic.

## Part C — "attack ALL crypto 15-min series, but only on near-certain pairs" (operator idea, TESTED)
Strict pairing + a certainty gate (open only: early window k≤K, |p−0.5|≤D, balanced flow |F|, spread
≤3¢; gate fit on first 60%, scored OOS on last 40%; best-combo per asset):
- **q0=0:** eth −5.3, sol −12.3, xrp −13.6 ¢/day OOS (aggregate **−31.1 ¢/day**) — DESPITE 92-97%
  pair-clean rates and positive mean locks (0.4-1.5¢/box).
- **q0=2000 (realistic queue): eth/sol/xrp capture ZERO boxes** in gated windows (thin books — the
  second side never fills at usable prices); eth still bleeds −21.9 ¢/day from stranded legs.
- The arithmetic that kills it: a clean box earns ~1¢; a straggler loses ~10-16¢. At that 10-16:1
  loss-to-lock ratio, "almost certain" must mean ≥99.4% clean to break even — the best honest gate
  tops out at 92-97%, and live queue reality (BTC: replay 99% → live 61%) only widens the gap.
- One genuine nugget: on BTC at q0=2000 the SAME gate scored +13.6 ¢/day OOS — the gate family has
  merit on the one liquid book. That's already covered prospectively by t01/t03/t06/t18 in the A/B
  tester; no new deployment implied.
**Verdict: REJECTED for eth/sol/xrp. Selectivity can't fix a book where the completing side
structurally doesn't fill. The certainty-gate idea survives only as BTC opening-gate trials.**

## Bottom line — FINAL
**Stay on KXBTC15M. Per-day, nothing else comes close**: other underlyings lose even with idealized
queue position (Part A), and other tenors/asset classes have no liquid markets to quote (Part B).
The per-day profit lever is NOT venue selection — it's (1) second-leg execution (the chase), (2) the
toxicity gates under prospective A/B test, (3) eventual size-up per SCALE_GATE.md. Do not relitigate
market selection unless Kalshi launches a new liquid short-tenor series.
