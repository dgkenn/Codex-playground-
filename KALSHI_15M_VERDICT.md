# 15-min crypto binary markets — consolidated verdict (2026-06-21)

Goal: "find a viable strategy to trade in the more-liquid 15m markets." Answer after exhaustive,
rigorous testing (with the artifact lessons baked in): **no viable strategy capturable by a slow
cloud participant. Every 15m edge is either eaten by sub-second players or IS the toxic/latency-walled
moment itself.** This is NOT "the market is efficient" -- inefficiencies exist; the capturable-by-us
slice does not.

## What was tested (and how it died)
| Angle | Result | Wall |
|---|---|---|
| Maker box (ATM 2-sided) | dead | QUEUE position -- last behind a 1.2s co-located MM; 18-48% strands vs 4.4% breakeven |
| Directional taker (spot/flow signals) | dead | spot absorbed <1min; all taker tiers -EV after the 60s-timing fix (DIRECTIONAL.md, 5,749 windows) |
| Signal ensemble | dead | OOS AUC worse than just reading the mid (DIRECTIONAL_SIGNALS.md) |
| Polymarket->Kalshi lead-lag | dead | real vs spot (t+27) but only 0.064c vs Kalshi mid, ~40x < cost (PMKT_LEADLAG.md) |
| Favorite-longshot (taker/maker) | dead | the clean signal was a TIME-IN-BAND selection artifact; unbiased test = calibrated (KALSHI_15M_LONGSHOT.md) |
| **Cross-asset relative value** (NEW) | **dead** | laggard binary already priced the common factor; spot arbed <1s; taker EV -2 to -10c, OOS-confirmed (KALSHI_15M_XASSET.md) |
| **Vol-stress spread capture** (NEW) | **dead** | wide spreads 91.8% single-tick (latency-walled) AND markout -3.6c to settle (toxic); both fatal (KALSHI_15M_STRESS.md) |

## The unifying mechanism (the honest "why")
15m crypto binaries are deeply LIQUID (1c spread, ~859-contract touch) and continuously anchored to a
spot price that sub-second arbitrageurs keep correct. So the inefficiencies are real but live on
timescales (<1s-1min) and queue positions a ~1.2s cloud/GHA participant cannot reach. The two NEW 2026-06-21
tests confirm this directly on the tick stream, forward/window-clustered/OOS -- real negatives, not artifacts.

## The only remaining 15m path, and why we don't take it
A viable 15m strategy would require WINNING THE SPEED RACE (same-region cloud + persistent WS + pre-signed
orders + compiled hot path, ~$50-200/mo + weeks of eng). Even if successful it returns the box's ~$10-27/day,
saturates ~$100, has NO moat (anyone rents the same instance), and Kalshi is API-only (no colo/FPGA tier) so
you can JOIN the fast tier but never dominate it. Bad risk/reward for a small operator -- the durable edges
for us are the ones where speed is IRRELEVANT.

## Decision
**Multi-strategy bot = longshot-maker harvest (speed-independent, built) + the trend-overlaid all-weather +
convex barbell portfolio (the capital-scaling engine). NOT a 15m trade.** Re-open 15m only if (a) we choose
to invest in the same-region speed stack (advised against), or (b) Kalshi's market structure changes
(a new tenor, a colo product, or the dominant MM withdraws). Until then, 15m stays retired.
