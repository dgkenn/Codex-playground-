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

## Part B — live tenor / index breadth scan (15m vs hourly vs daily vs index)
[PENDING — live Kalshi REST enumeration of crypto + index series across tenors, ranking by
estimated box-¢/DAY with the liquidity/competition caveat. Results appended when the scan lands.]

## Bottom line so far
Among underlyings, BTC15M is the right venue per-day — the alternatives lose even idealized. The only
open market-selection question is TENOR (could BTC hourly/daily offer wider margins worth fewer
windows?) and whether any non-crypto intraday index binary is cleaner — that's Part B.
