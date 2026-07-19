# Kalshi longer-horizon crypto ONE-TOUCH mispricing test

Generated 2026-07-16T13:14:03.194211+00:00  (analysis date 2026-07-16)

## Sample

- Settled markets pulled: 31 (BTC 15, ETH 16)
- Distinct close-months (all): 3 -> ['26JUL31', '26JUN30', '26MAY31']
- GENUINE upside barriers (strike>spot at open): 30 across 3 distinct close-months ['26JUL31', '26JUN30', '26MAY31']
- Trivial (strike<=spot, already-touched): 1
- No KXBTCMAXW (weekly) settled markets exist on the venue.
- GENUINE realized touch count: 1 / 30

## Genuine upside-barrier markets (causal spot/vol, entry VWAP, fair value)

| series | month | strike | spot | B/S | sigma | T(yr) | entry_yes | n_trd | FV(touch) | FV-entry | result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC | 26JUL31 | 65000 | 58625 | 1.109 | 0.43 | 0.084 | 0.698 | 2207 | 0.410 | -0.288 | yes |
| BTC | 26JUN30 | 75000 | 73674 | 1.018 | 0.25 | 0.081 | 0.139 | 3596 | 0.799 | +0.660 | no |
| BTC | 26JUN30 | 77500 | 73674 | 1.052 | 0.25 | 0.081 | 0.084 | 1868 | 0.470 | +0.386 | no |
| BTC | 26JUN30 | 80000 | 73674 | 1.086 | 0.25 | 0.081 | 0.070 | 878 | 0.240 | +0.170 | no |
| BTC | 26JUN30 | 82500 | 73674 | 1.120 | 0.25 | 0.081 | 0.056 | 374 | 0.106 | +0.050 | no |
| BTC | 26JUN30 | 85000 | 73674 | 1.154 | 0.25 | 0.081 | 0.031 | 389 | 0.041 | +0.010 | no |
| BTC | 26JUN30 | 87500 | 73674 | 1.188 | 0.25 | 0.081 | 0.025 | 99 | 0.014 | -0.011 | no |
| BTC | 26JUN30 | 90000 | 73674 | 1.222 | 0.25 | 0.081 | 0.016 | 68 | 0.004 | -0.012 | no |
| BTC | 26JUN30 | 92500 | 73674 | 1.256 | 0.25 | 0.081 | 0.043 | 80 | 0.001 | -0.042 | no |
| BTC | 26MAY31 | 85000 | 76347 | 1.113 | 0.36 | 0.084 | 0.412 | 1665 | 0.300 | -0.112 | no |
| BTC | 26MAY31 | 87500 | 76347 | 1.146 | 0.36 | 0.084 | 0.228 | 661 | 0.188 | -0.040 | no |
| BTC | 26MAY31 | 90000 | 76347 | 1.179 | 0.36 | 0.084 | 0.121 | 717 | 0.112 | -0.009 | no |
| BTC | 26MAY31 | 92500 | 76347 | 1.212 | 0.36 | 0.084 | 0.064 | 185 | 0.064 | +0.000 | no |
| BTC | 26MAY31 | 95000 | 76347 | 1.244 | 0.36 | 0.084 | 0.046 | 179 | 0.035 | -0.011 | no |
| BTC | 26MAY31 | 97500 | 76347 | 1.277 | 0.36 | 0.084 | 0.038 | 258 | 0.018 | -0.020 | no |
| ETH | 26JUN30 | 2250 | 2007 | 1.121 | 0.28 | 0.081 | 0.083 | 715 | 0.154 | +0.072 | no |
| ETH | 26JUN30 | 2500 | 2007 | 1.246 | 0.28 | 0.081 | 0.037 | 134 | 0.006 | -0.031 | no |
| ETH | 26JUN30 | 2750 | 2007 | 1.370 | 0.28 | 0.081 | 0.023 | 71 | 0.000 | -0.023 | no |
| ETH | 26JUN30 | 3000 | 2007 | 1.495 | 0.28 | 0.081 | 0.013 | 47 | 0.000 | -0.013 | no |
| ETH | 26JUN30 | 3250 | 2007 | 1.619 | 0.28 | 0.081 | 0.011 | 25 | 0.000 | -0.011 | no |
| ETH | 26JUN30 | 3500 | 2007 | 1.744 | 0.28 | 0.081 | 0.016 | 19 | 0.000 | -0.016 | no |
| ETH | 26JUN30 | 3750 | 2007 | 1.868 | 0.28 | 0.081 | 0.012 | 15 | 0.000 | -0.012 | no |
| ETH | 26MAY31 | 2500 | 2258 | 1.107 | 0.52 | 0.084 | 0.397 | 324 | 0.494 | +0.097 | no |
| ETH | 26MAY31 | 2750 | 2258 | 1.218 | 0.52 | 0.084 | 0.073 | 155 | 0.186 | +0.113 | no |
| ETH | 26MAY31 | 3000 | 2258 | 1.329 | 0.52 | 0.084 | 0.027 | 34 | 0.057 | +0.029 | no |
| ETH | 26MAY31 | 3250 | 2258 | 1.440 | 0.52 | 0.084 | 0.020 | 89 | 0.015 | -0.005 | no |
| ETH | 26MAY31 | 3500 | 2258 | 1.550 | 0.52 | 0.084 | 0.026 | 5 | 0.003 | -0.022 | no |
| ETH | 26MAY31 | 3750 | 2258 | 1.661 | 0.52 | 0.084 |   -   | 1 | 0.001 |   -   | no |
| ETH | 26MAY31 | 4000 | 2258 | 1.772 | 0.52 | 0.084 |   -   | 0 | 0.000 |   -   | no |
| ETH | 26MAY31 | 4250 | 2258 | 1.883 | 0.52 | 0.084 |   -   | 0 | 0.000 |   -   | no |

## Test 1 - Calibration (realized touch-rate vs entry price)

| entry-price bin | n markets | mean entry | realized touch-rate |
|---|---|---|---|
| [0.00,0.05) | 15 | 0.026 | 0.000 |
| [0.05,0.10) | 6 | 0.071 | 0.000 |
| [0.10,0.20) | 2 | 0.130 | 0.000 |
| [0.20,0.40) | 2 | 0.313 | 0.000 |
| [0.40,1.01) | 2 | 0.555 | 0.500 |

Distinct close-months among calibrated genuine markets: 3 (power is minimal).

## Test 2 - Fair-value mispricing (does FV-entry predict outcome?)

- Mean (FV - entry) across 27 genuine markets: +0.0336 (month-clustered t=1.10, 3 clusters)
- Mean (realized_touch - entry): -0.0670 (month-clustered t=-2.07)  [>0 => Kalshi underpriced touch; <0 => overpriced]
- Mean (realized_touch - FV): -0.1007 (month-clustered t=-3.21)  [<0 => reflection-FV OVER-predicted touch]

## Test 3 - Tradeable PnL: MARKET-weighted vs TRADE-weighted

Strategy from the hypothesis: when FV > entry (model says touch is underpriced) we BUY YES(touch); when FV < entry we BUY NO(sell touch). Simulate being the taker on that side at each real fill on that side, net of Kalshi taker fee. Settlement: YES pays 1 if touched else 0; NO pays the complement.

- MARKET-weighted PnL/contract: -0.0202 (month-clustered t=-1.04, n=27, 3 clusters)
- TRADE-weighted PnL/contract (fill-weighted within market, equal across markets): -0.0214 (month-clustered t=-1.20, n=26)
- TRADE-weighted PnL/contract (ALL real contracts, volume-weighted): -0.0472 (month-clustered t=-0.72, total contracts=998856)

## Test 4 - Adverse selection (touch-rate: market- vs volume-weighted)

- genuine only: market-weighted touch-rate=0.033, volume-weighted touch-rate=0.115 (n=30)
- all settled: market-weighted touch-rate=0.065, volume-weighted touch-rate=0.115 (n=31)
  (volume-weighted >> market-weighted would indicate buyers piling into soon-to-touch barriers; here compare the two.)

## Structural caveat (READ BEFORE the verdict)

- 26JUL31: 1 settled genuine markets, 1 touched.
- 26JUN30: 15 settled genuine markets, 0 touched.
- 26MAY31: 14 settled genuine markets, 0 touched.
- July contributes only ONE settled market (the 65000 strike that touched and closed early); the rest of the July ladder is still active/unsettled. So the effective sample is TWO full monthly BTC path draws (May, Jun, both all-NO) + one early-touch July point + two ETH ladders sharing the same two months. This is ~2-3 correlated macro draws, NOT 30 independent bets.

## VERDICT

NULL / NEGATIVE for the stated hypothesis, and severely underpowered.

- Retail did NOT systematically underprice touch. Realized_touch - entry = -0.067 (t=-2.07): if anything Kalshi's traded price was ABOVE the realized touch frequency (touch happened LESS than priced).
- The driftless reflection 'fair value' OVER-predicted touch badly (realized - FV = -0.101, t=-3.21). Ignoring drift/mean-reversion, 2*N(...) overstated upside-barrier probability during a falling BTC market. The 'smart' FV was the LESS accurate of the two.
- Trading the FV-vs-price signal LOSES money at every weighting: market-weighted -0.020/contract, fill-weighted -0.021, fully volume-weighted -0.047. No market-vs-trade divergence that hides an edge; trade-weighting makes it WORSE, exactly the adverse-selection signature (volume-weighted touch-rate 0.115 >> market-weighted 0.033).
- Power: 3 close-months, effectively ~2 independent BTC monthly paths. All upside barriers in May & June missed simply because BTC fell. No t-stat here is trustworthy; a 3-month all-NO run is a path realization, not a harvestable edge.
- CONCLUSION: There is NO real, cost-surviving, trade-weighted one-touch mispricing edge detectable in the liquid monthly Kalshi crypto barriers. The longer-horizon markets look as efficient (given sampling noise) as the 15-minute ones. Do not deploy.
