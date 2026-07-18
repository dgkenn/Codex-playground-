# K9: Kalshi THETA / temporal-decay curve mispricing

_generated 2026-07-18T17:22:19.190814+00:00_

## VERDICT (blunt)

**NULL, and actively WRONG-SIGNED (in the specified direction), not merely priced-away.** Reversion-to-the-decay-curve loses money net of fees with day-clustered t=-3.19 pooled (TEST OOS t=-2.83), and the loss is NOT just fee drag -- gross PnL/ct is itself negative (see below). IMPORTANTLY, flipping the trade direction (betting WITH the deviation / continuation, identical entries) is ALSO negative (mean -0.0574/ct, t=-1.75). Neither reversion NOR continuation earns a positive net edge here -- this rules out a clean 'it's just sign-flipped momentum' story and points instead to a structural execution cost (crossing the bid/ask spread at a moment the curve flags as 'stale', which correlates with genuinely elevated realized volatility / information arrival) that eats BOTH directions. Either way there is no tradeable theta-decay edge. Read this as evidence against the mechanism as specified: prices that deviate >=10% from the naive time-decay path do not reliably mean-revert to it.


- Markets used: **398** settled Kalshi markets across 7 categories (Economics, Financials, Climate and Weather, Sports, Politics, Crypto, Entertainment), TRAIN=278 (close 2026-05-22..2026-07-16), TEST=120 (close 2026-07-16..2026-07-18).
- Multiple-testing count: **24** configs (curves=2 x thresholds=3 x horizons=4). Headline config selected by MAX day-clustered t on TRAIN ONLY, then re-evaluated on held-out TEST -- the number below is what survives that filter, not a cherry-pick over the full sample.
- Headline config (TRAIN-selected): **curve=linear, threshold=10%, horizon=resolution**
  - TRAIN: n=198, day-groups=51, mean net PnL/ct=-0.0728, day-clustered t=-2.44
  - TEST (OOS): n=105, day-groups=7, mean net PnL/ct=-0.0832, day-clustered t=-2.83
  - POOLED (train+test, same config): n=303, day-groups=54, mean net PnL/ct=-0.0764, day-clustered t=-3.19, win rate=39.6%
  - POOLED gross/fee split: mean GROSS pnl/ct=-0.0595 (before fee), mean fee/ct=+0.0169 -- genuinely adverse-signed (gross itself negative), NOT just fee-killed
  - **SIGN-FLIP CHECK** (identical entries, opposite direction -- bet WITH the deviation/continuation instead of toward the curve): n=303, mean net PnL/ct=-0.0574, day-clustered t=-1.75, mean gross=-0.0407
  - Worst single day (pooled headline config): 2026-05-27, mean -0.9600/ct over 1 trades

## Novelty check: is this just relabeled moneyness/momentum? (CRITICAL)

- corr(|deviation from theoretical curve|, price level): **-0.108**
- corr(|deviation from theoretical curve|, recent price change [momentum]): **+0.001**
- corr(SIGNED deviation, SIGNED recent price change): **+0.152**
- computed over 23198 candle-level observations (sqrt curve, all markets, no threshold gate).

Interpretation: |corr| >= 0.3 with price level means the 'decay deviation' is largely just moneyness (how far from 0.5) in disguise -- the exact structure already killed under favorite-longshot/calibration work. |corr| >= 0.3 with recent price change (especially the SIGNED version) means the 'reversion to curve' bet is largely a same-direction restatement of a momentum/mean-reversion signal already tested elsewhere (a sign-flip of momentum is exactly what the reversion trade would look like if the curve is doing no real path-specific work).


## Per-category breakdown (headline config, pooled)

| category | n | day-groups | mean net PnL/ct | day-clustered t |
|---|--:|--:|--:|--:|
| Climate and Weather | 118 | 22 | -0.0281 | -0.75
| Crypto | 88 | 10 | -0.1019 | -9.08
| Sports | 39 | 11 | -0.0826 | -1.25
| Financials | 28 | 3 | -0.1579 | -1.76
| Economics | 18 | 9 | -0.0978 | -1.16
| Entertainment | 8 | 5 | -0.0988 | -0.62
| Politics | 4 | 1 | -0.1675 | n/a |

## Top 5 configs by TRAIN day-clustered t (for transparency on the search)

| curve | threshold | horizon | n | day-groups | mean net PnL/ct | day-clustered t |
|---|--:|--:|--:|--:|--:|--:|
| linear | 10% | resolution | 198 | 51 | -0.0728 | -2.44 |
| sqrt | 5% | resolution | 210 | 49 | -0.0768 | -2.55 |
| sqrt | 10% | resolution | 196 | 48 | -0.0836 | -2.56 |
| sqrt | 7% | resolution | 203 | 48 | -0.0891 | -2.80 |
| linear | 5% | resolution | 212 | 48 | -0.0817 | -2.89 |

## Method notes

- Theoretical curve: `theo(t) = target + (initial - target) * r(t)**k`, r=remaining life fraction, target=nearest boundary (0/1) to the FIRST observed candle's mid (fixed once, causal), k=0.5 (homerun sqrt-time reconstruction) or k=1.0 (linear baseline). No use of the true resolution value anywhere in curve construction.
- Fee: ceil_to_cent(0.07*p*(1-p)), min 1c, charged on EVERY taker trade -- horizon exits pay entry+exit fee (real round-trip close); resolution-hold exits pay entry fee only (free settlement).
- Trades are NON-OVERLAPPING per market: after a signal fires, the scan pointer advances past the trade's exit candle before the next signal in that market is considered.
- Day-clustered t on trade-level net PnL (entry calendar date = cluster key), not per-trade t.
- Volume floor 15.0, min candles 8, TRAIN/TEST split 70%/30% by close date.
- Data: public Kalshi API, no auth, read-only.
