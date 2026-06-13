# Hourly Multi-Strike Crypto Ladder — Cross-Strike Arb SCREEN

Markets: Kalshi hourly ladders KX{ETH,SOL,XRP,BTC}D. Each row = one (event-hour, strike)
settled market. YES = (price >= strike at close). 60-min window, ~60 per-minute YES **mids**
(bid/ask NOT stored). Counts: ETH 1308 strike-mkts/40 events, SOL 1040/29, XRP 1481/40,
BTC 1052/13. Only ~7-44 near-money strikes priced per event; rest deep ITM/OTM (trivially 0/1).

**MID-ONLY CAVEAT (applies to every number below):** we store mid only. Every "violation"
here is a SCREEN on mids; a mid-level inversion can vanish at executable bid/ask. As shown
below, essentially ALL detected violations are explained by one-sided-book mid artifacts
(mid defaulting toward 0.5 when the book is one-sided), which is the canonical case where a
mid signal is fake. So nothing here is a claimable arb without a bid/ask re-fetch — and the
analysis predicts a re-fetch would kill it.

Fee model (taker): `fee = ceil(M*P*(1-P)*100)/100` per ct, M=0.07 std / 0.14 crypto-premium;
maker ~0. A 2-leg arb = 2 takers => ~2*(fee + half-spread). Both M values modeled.

---

## 1. Static cross-strike monotonicity arb (headline)

Rule: at every (event, minute) YES mid must be non-increasing in strike. A higher strike with
a higher YES mid = inversion = candidate lock (buy cheap low-strike-equiv / sell rich high-strike).

**Per-minute screen (raw):**

| asset | snaps(>=2 strikes) | snaps w/ violation | adj inversions | gap mean / med / max (c) |
|---|---|---|---|---|
| ETH | 2230 | 116 (5.2%) | 120 | 0.81 / 0.50 / 9.0 |
| SOL | 1678 | 127 (7.6%) | 129 | 8.39 / 2.0 / 49.5 |
| XRP | 2217 | 74 (3.3%) | 77 | 18.65 / 18.0 / 49.5 |
| BTC | 780 | 248 (31.8%) | 455 | 2.63 / 1.5 / 34.0 |

The large SOL/XRP means (8-19c) are a RED FLAG, not opportunity. Drilling in: the big gaps are
driven by the **high-strike leg sitting at exactly mid=0.5** (placeholder when book is one-sided)
while the low strike is correctly ~0.005. mid_hi==0.5 exactly explains 12% of SOL and 35% of XRP
inversions; the rest with mid_lo<=0.02 are the same illiquid-deep-OTM one-sided-book effect.

**Capturability filter — the decisive cut.** Require BOTH legs genuinely near-money (mid in
0.05-0.95, so neither is a stale 0/1 placeholder) AND the violation to persist >=3 consecutive
minutes (so it is capturable, not a 1-tick flicker):

| asset | both-near-money inversions | persisting >=3 consecutive min |
|---|---|---|
| ETH | 0 | **0** |
| SOL | 7 | **0** |
| XRP | 40 | **0** |
| BTC | 15 | **0** |

**Zero** capturable persistent near-money inversions in every asset. The near-money inversions
that exist are single-minute flickers; even the few XRP pairs "violated" on 3-8 (non-consecutive)
minutes are artifacts: e.g. KXXRPD-26JUN1208 pair (1.1599 / 1.1799) both have **median mid 0.005**
(perfectly consistent) but p90=0.45-0.50 — the high strike's mid periodically jumps to 0.5 on a
one-sided book, and that exact tick is logged as the "violation."

**Definitive steady-state test (median window mid per strike, robust to one-sided-book flicks):**

| asset | adjacent pairs | median-mid violations | >3c |
|---|---|---|---|
| ETH | 1268 | **0 (0.00%)** | 0 |
| SOL | 976 | 1 (0.10%) | 1 |
| XRP | 1419 | **0 (0.00%)** | 0 |
| BTC | 1038 | 13 (1.25%) | 2 |

On steady-state prices the ladders are internally consistent to within rounding. The handful of
BTC residuals (13/1038, 2 over 3c) are single illiquid strikes, not persistent locks.

**Net of cost (raw per-minute inversions, the most generous case):** even taking the raw
inversions at face value, after 2 taker fees + 2 half-spreads the play is a loss in the assets
where it matters. ETH: 0-1 of 120 net-profitable at 2c half-spread, none at 4c+. BTC: 36/455 at
2c, mean net -3.4c. SOL/XRP show "profitable" raw inversions (38/129, 46/77) ONLY because the
inflated 0.5-placeholder gaps survive the fee — i.e. the apparent profit IS the artifact, and is
exactly what dies at real bid/ask. **No real, capturable monotonicity arb.**

## 2. Vertical-spread / box consistency

Butterfly on consecutive strikes K1<K2<K3 must cost >=0 (`mid1 - 2*mid2 + mid3`). Raw screen
flags many "negative-cost" butterflies (ETH 2158/16392, SOL 1788, XRP 2188, BTC 2100; mean
cost ~ -28 to -65c). This is NOT box arb — it is the SAME one-sided-book mid artifact compounded
across three legs (any leg flicking to 0.5 breaks convexity). With 3 taker legs (~3x fee+spread)
and median-mid monotonicity holding, there is no real negative-cost butterfly/box. The raw count
is a measure of mid noise, not of mispricing. **No capturable vertical/box arb.**

## 3. Near-money efficiency + favorite-longshot

In the tradeable 0.1-0.9 median-mid band the sample is thin (only ~10-12 markets per asset land
there using median-mid, since most near-money strikes drift to 0/1 by settle). Aggregate
mid-vs-realized bias: ETH -10c, SOL -5c, XRP -0.2c, BTC +15c — but n is 10-12, so these are
noise (1 market = 8-10c swing). No monotone favorite-longshot pattern survives across bins, and
no bin shows a bias that is both stable AND larger than spread+fee on a sample this size.
**Consistent with the 15-min finding: near-money is efficient; no exploitable F-L bias on this data.**
(Needs far more events to make any calibration claim — flagged as low-power, not a signal.)

## 4. Longer-tenor maker box estimate

For near-money markets (median mid 0.2-0.8) over the 60-min window:

| asset | n near-money | mean intra-window mid range | flip (cross 0.5) frac |
|---|---|---|---|
| ETH | 8 | 67.3c | 0.50 |
| SOL | 8 | 68.9c | 0.25 |
| XRP | 7 | 69.7c | 0.29 |
| BTC | 8 | 66.1c | 0.50 |

The 60-min tenor does NOT help a maker box — the opposite. Near-money mids travel a **~67c range**
over the hour and flip across 0.5 in 25-50% of cases. That is a LARGER excursion than the 15-min
market, meaning more adverse selection / higher strand risk for a maker holding to settlement, not
less. The longer horizon gives price more time to run away from a posted level. (Rough; mid-only,
small n, no order-flow — but directionally clear: longer tenor is worse for the maker box, not better.)

## 5. VERDICT

| asset | monotonicity arb | box arb | near-money | maker box | verdict |
|---|---|---|---|---|---|
| ETH | none (0 median-mid viol) | none | efficient (low power) | worse than 15-min | **No edge** |
| SOL | none (1/976 median-mid) | none | efficient (low power) | worse | **No edge** |
| XRP | none (0 median-mid viol) | none | efficient (low power) | worse | **No edge** |
| BTC | none (13/1038, 2>3c, illiquid) | none | efficient (low power) | worse | **No edge** |

**Overall: NO positive-EV ladder strategy after realistic costs.** The hourly multi-strike ladders
are internally consistent (steady-state median mids are monotone non-increasing in strike to within
rounding), so there is no static cross-strike / vertical / box arb. All raw per-minute "violations"
are one-sided-book mid artifacts (mid defaulting toward 0.5) that are exactly what would vanish at
executable bid/ask — and they fail the persistence and net-of-cost tests anyway. Near-money pricing
is efficient (consistent with the proven-efficient 15-min single-strike markets), and the longer
60-min tenor makes a maker box MORE adversely selected (larger price excursion, more flips), not less.

**Structural reason:** the ladder is just a set of binaries on the same underlying at one settle
time; an internally-consistent market maker (which Kalshi's appears to be) prices them off one
implied distribution, so cross-strike monotonicity/convexity hold by construction. There is no
free lunch from inconsistency, and there is no directional edge (proven for 15-min, inherited here).

## What (if anything) warrants a bid/ask re-fetch

**Low priority / unlikely to change verdict, but the only thing left to confirm:** extend
`fetch_ladder_hourly.py` to store `yes_bid`/`yes_ask` paths (it already computes mid from
`yes_bid`/`yes_ask` candle closes — store both instead of collapsing to mid). Then re-check:

1. The ~few BTC steady-state median-mid inversions (13 pairs, 2 over 3c) — confirm they are
   one-sided/illiquid books (expected) rather than two-sided executable inversions.
2. Any XRP/SOL near-money pair that was "violated" on >=3 minutes — verify the high-strike's
   apparent 0.5 mid corresponds to a one-sided book (no real ask to lift), as the p90/median
   split strongly implies.

Prediction: a re-fetch confirms zero two-sided-quote inversions (all are placeholder-0.5 mids),
so this is a verification step, not an expected source of edge. **Do not deploy capital on any
ladder strategy on the basis of mids alone.**

---
SCREEN only (in-sample, mid-based). Forward-validation required before any claim. Mid-only data:
all violation magnitudes are upper bounds; executable edge at bid/ask is expected to be <= 0.
