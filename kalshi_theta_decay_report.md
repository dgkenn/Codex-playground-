# K9: Kalshi THETA / temporal-decay curve mispricing

_generated 2026-07-18T17:18:10.136670+00:00_

## VERDICT (blunt)

**NULL / PRICED.** No curve x threshold x horizon configuration produces a fee-surviving, day-clustered-significant edge that replicates out-of-sample. This is consistent with the program's prior: Kalshi is efficiently priced against naive path-shape signals, mirroring the VRP/timing NULL.


- Markets used: **15** settled Kalshi markets across 7 categories (Economics, Financials, Climate and Weather, Sports, Politics, Crypto, Entertainment), TRAIN=10 (close 2026-06-30..2026-06-30), TEST=5 (close 2026-06-30..2026-06-30).
- Multiple-testing count: **24** configs (curves=2 x thresholds=3 x horizons=4). Headline config selected by MAX day-clustered t on TRAIN ONLY, then re-evaluated on held-out TEST -- the number below is what survives that filter, not a cherry-pick over the full sample.
- Headline config (TRAIN-selected): **curve=linear, threshold=10%, horizon=6 candle-steps**
  - TRAIN: n=77, day-groups=15, mean net PnL/ct=-0.0464, day-clustered t=-2.04
  - TEST (OOS): n=41, day-groups=12, mean net PnL/ct=-0.0420, day-clustered t=-1.03
  - POOLED (train+test, same config): n=118, day-groups=15, mean net PnL/ct=-0.0448, day-clustered t=-1.97, win rate=10.2%
  - Worst single day (pooled headline config): 2026-06-14, mean -0.5300/ct over 1 trades

## Novelty check: is this just relabeled moneyness/momentum? (CRITICAL)

- corr(|deviation from theoretical curve|, price level): **-0.422**
- corr(|deviation from theoretical curve|, recent price change [momentum]): **-0.058**
- corr(SIGNED deviation, SIGNED recent price change): **+0.172**
- computed over 1128 candle-level observations (sqrt curve, all markets, no threshold gate).

Interpretation: |corr| >= 0.3 with price level means the 'decay deviation' is largely just moneyness (how far from 0.5) in disguise -- the exact structure already killed under favorite-longshot/calibration work. |corr| >= 0.3 with recent price change (especially the SIGNED version) means the 'reversion to curve' bet is largely a same-direction restatement of a momentum/mean-reversion signal already tested elsewhere (a sign-flip of momentum is exactly what the reversion trade would look like if the curve is doing no real path-specific work).


## Per-category breakdown (headline config, pooled)

| category | n | day-groups | mean net PnL/ct | day-clustered t |
|---|--:|--:|--:|--:|
| Economics | 118 | 15 | -0.0448 | -1.97

## Top 5 configs by TRAIN day-clustered t (for transparency on the search)

| curve | threshold | horizon | n | day-groups | mean net PnL/ct | day-clustered t |
|---|--:|--:|--:|--:|--:|--:|
| linear | 10% | 6 steps | 77 | 15 | -0.0464 | -2.04 |
| linear | 7% | 6 steps | 83 | 16 | -0.0445 | -2.14 |
| linear | 5% | 6 steps | 88 | 17 | -0.0486 | -2.27 |
| sqrt | 7% | 6 steps | 93 | 17 | -0.0457 | -2.30 |
| sqrt | 5% | 6 steps | 94 | 17 | -0.0517 | -2.37 |

## Method notes

- Theoretical curve: `theo(t) = target + (initial - target) * r(t)**k`, r=remaining life fraction, target=nearest boundary (0/1) to the FIRST observed candle's mid (fixed once, causal), k=0.5 (homerun sqrt-time reconstruction) or k=1.0 (linear baseline). No use of the true resolution value anywhere in curve construction.
- Fee: ceil_to_cent(0.07*p*(1-p)), min 1c, charged on EVERY taker trade -- horizon exits pay entry+exit fee (real round-trip close); resolution-hold exits pay entry fee only (free settlement).
- Trades are NON-OVERLAPPING per market: after a signal fires, the scan pointer advances past the trade's exit candle before the next signal in that market is considered.
- Day-clustered t on trade-level net PnL (entry calendar date = cluster key), not per-trade t.
- Volume floor 15.0, min candles 8, TRAIN/TEST split 70%/30% by close date.
- Data: public Kalshi API, no auth, read-only.
