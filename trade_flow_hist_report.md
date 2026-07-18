# Polymarket weekly crypto SHORT-VOL edge -- PRINT-LEVEL re-confirmation over full history

_Generated 2026-07-18T15:22:50.571800+00:00_

Universe: **6848 settled weekly (4-10d) BTC/ETH 'above $X on <date>?' markets** across **49 resolution-weeks** (2025-01-01 .. 2026-07-18), from ACTUAL executed prints (data-api /trades). 0 markets hit the trade-page cap. Discovery via deterministic slug enumeration (fixes the prior study's 4-week bottleneck).

## Sign sanity check

- Longshots (median YES-long print price <= 0.3): n=3364, YES-resolution rate = **0.0056** (expected well below 0.5). PASS

## (A) Fill realism -- in-band first-half YES-BUY volume a resting seller could fill

- Of 6848 weekly markets, **5044 (74%) had ZERO** in-band first-half YES-buy prints; **1804 (26%) qualify**.

- In-band YES-buy $ notional among QUALIFYING markets: {'0': 0.2, '0.1': 3.0, '0.25': 13.23, '0.5': 81.25, '0.75': 326.95, '0.9': 1014.5, '1.0': 11995.1}

- Median qualifying market: **376.35 shares ($80.72 YES-notional)** fillable.

## (A) Print-level seller edge

- Equal-weight: **0.0589/ct** (week-clustered t=**2.376**, k=49 weeks, n=1804)

- Trade-weighted (by fillable $): **0.121/ct** (week-clustered t=4.166)

- Taker-cost sensitivity (if crossing, fee 0.07p(1-p)): equal-weight 0.047/ct (t=1.895). Backtest reference +0.12/ct.

- By asset: {'BTC': {'n': 1019, 'eq_edge': 0.0606, 't': 2.34, 'yes_rate': 0.1443}, 'ETH': {'n': 785, 'eq_edge': 0.0589, 't': 2.07, 'yes_rate': 0.1401}}

- Adverse selection (split at 376.35 sh): heavy YES-rate=0.1364 (n=902) vs light=0.1486 (n=902); heavy edge=0.0828 vs light=0.0707.

## Calibration (out-of-sample: priced vs realized)

- In-band avg priced YES = **0.2192** vs realized YES rate = **0.1425** among 1804 qualifying markets (EDGE CONFIRMED: realized < priced).

  - fill [0.15,0.20): n=666, priced 0.1753 -> realized YES 0.0691

  - fill [0.20,0.25): n=647, priced 0.2226 -> realized YES 0.1267

  - fill [0.25,0.30): n=491, priced 0.2743 -> realized YES 0.2627

## Capacity (honest deployable $/week)

- Per fillable market: median **$80.72**, mean $372.55 YES-notional. Quantiles: {'0': 0.2, '0.1': 3.0, '0.25': 13.23, '0.5': 81.25, '0.75': 326.95, '0.9': 1014.5, '1.0': 11995.1}

- Per resolution-week (weeks with ANY fill, n=49/49): median **$9360.78**, mean $13715.85. Quantiles: {'0': 1436.54, '0.1': 3840.9, '0.25': 5408.76, '0.5': 9360.78, '0.75': 16031.2, '0.9': 32972.18, '1.0': 62424.37}

- Total fillable in-band YES-buy notional across all history: $672076.87.

- WORST week: 2025-W33 edge=-0.5166/ct (n=9, YES-rate=0.7778, avg fill 0.2612). BEST week: 2025-W38 edge=0.23/ct (n=29).

## BLUNT VERDICT

- **History unlocked:** Enumerated 6848 settled weekly BTC/ETH 'above' markets across 49 resolution-weeks (vs 4 weeks in the prior active-search study); 1804 markets (26%) had fillable in-band first-half YES-buy prints across 49 weeks.

- **Fills real?** YES - fills occur at genuine band prices (avg in-band fill 0.219); qualifying-market YES-resolution rate 0.142 confirms longshots bought cheap resolve NO.

- **Print-level edge:** Equal-weight seller edge 0.059/ct (week-clustered t=2.376, k=49 weeks, n=1804); trade-weighted (by fillable $) 0.121/ct (week-clustered t=4.166). Backtest ref +0.12/ct.

- **Calibration:** In-band priced YES ~0.219 vs realized YES ~0.142 -- edge confirmed (realized < priced).

- **Does it re-confirm?** RE-CONFIRMS at print level: week-clustered t>=2 over real history.

- **Capacity:** Gross in-band fillable YES-buy flow is median ~$9360.78/week (mean ~$13715.85, ~37 fillable markets/week), NOT the ~$128/market the thin 4-week prior sample implied -- capacity comes from BREADTH (many small fills), since per market is small & right-skewed (median $80.72, mean $372.55). Total ~$672076.87 fillable notional over 49 weeks. A lone resting seller who captured, say, a third of that flow could deploy low-single-digit $k/week; at the 0.121/ct trade-weighted edge that is a few hundred $/week gross before maker competition and adverse fills -- a REAL but modest niche, capacity-bound by retail longshot-buy volume rather than by the edge.


_n=6848 markets over 49 weeks; 1804 qualifying; 257 YES resolutions among qualifying._
