# Polymarket short-vol longshot edge -- trade-level hardening

_Generated 2026-07-18T14:49:29.468787+00:00_

Universe: **66 settled weekly (4-10d) BTC/ETH 'above $X' markets** across **4 resolution-weeks**, analyzed from ACTUAL executed prints (data-api /trades). 0 markets hit the trade-page cap.

## Sign sanity check

- Longshots (median YES-long print price <= 0.3): n=32, YES-resolution rate = **0** (expected well below 0.5 -> longshots mostly get BOUGHT cheap and resolve NO). PASS

## (A) Fill realism -- in-band first-half YES-BUY volume a resting seller could fill

- Of 66 weekly markets, **54 (82%) had ZERO** in-band first-half YES-buy prints; **12 (18%) qualify** (some fillable flow).

- In-band YES-buy volume among QUALIFYING markets (shares): {'0': 5.0, '0.1': 19.0, '0.25': 99.0, '0.5': 870.79, '0.75': 1712.41, '0.9': 6171.68, '1.0': 6697.78}

- In-band YES-buy volume among QUALIFYING markets ($ YES-notional): {'0': 1.3, '0.1': 3.23, '0.25': 17.73, '0.5': 154.99, '0.75': 386.58, '0.9': 1103.64, '1.0': 1538.62}

- Median qualifying market offered **611.38 shares ($128.5 YES-notional)** of fillable in-band YES-buy flow.

## (A) True trade-weighted edge vs equal-weight

- Equal-weight seller edge: **0.0906/ct** (week-clustered t=0.702, k=4 weeks, n=12)

- TRUE trade-weighted edge (weighted by fillable YES-buy shares): **0.1662/ct** (week-clustered t=-0.111)

- Backtest reference: +0.12/ct.

- Adverse selection (split at 611.38 shares): heavy-flow YES-rate=0.1667 (n=6) vs light-flow YES-rate=0 (n=6); heavy-flow seller edge=0.0407 vs light=0.2274.

## (B) Native order-flow imbalance signal

- Regression outcome ~ 1 + price + flow_imbalance (n=12, 4 week clusters):

  - coef_price=-4.849 (t=-1.927), coef_flow=**-0.6927** (week-clustered t=**-2.134**)

- Multiple-testing: 3 hypotheses, Bonferroni |t| threshold ~2.39. Flow t=-2.134 FAILS this bar; OOS chrono fold too thin to test.

## BLUNT VERDICT

- **Fills real?** YES - the fills that occur are at genuine band prices and 11/12 resolved NO; point-estimate seller edge +0.09 (equal-wt) to +0.17 (trade-wt), bracketing backtest +0.12.

- **Capacity:** BINDING - only 12/66 (18%) of weekly markets had ANY in-band first-half YES-buy prints for a resting seller to fill; 54 (82%) had ZERO.

- **Significance on live prints:** NOT reproducible on live prints: only 4 distinct resolution-weeks queryable and just 1 of 12 qualifying markets resolved YES, so week-clustered t~0.7 (not >=2). Backtest t~4.6 needs its 50-week sample.

- **Adverse selection:** DIRECTIONAL but single-event: the lone YES resolution sat at mid/heavy in-band volume; heavy-flow YES-rate 0.167 vs light 0.0 - suggestive of informed buyers but rests on n=1 YES event. Inconclusive.

- **Native order-flow edge:** NULL - flow-imbalance coef is NEGATIVE (net YES-buying -> LESS YES), driven entirely by the one YES market (imb=-0.47); fails Bonferroni |t|>=2.39; OOS fold too thin (3 mkts). Consistent with prior: flow IS the retail overpricing the short-vol edge already harvests, not a stackable signal.

- **BOTTOM LINE:** Trade-level prints CONFIRM fills are real and correctly signed (longshots bought cheap, resolve NO) and do NOT expose a fill/adverse-selection problem that kills the edge. They DO expose (1) a hard capacity/selectivity constraint (seller fills materialize in ~18% of markets) and (2) that the multi-week significance CANNOT be re-confirmed on the ~4 weeks of live-queryable prints. No native order-flow edge to stack.


_Thin-n flags: 66 weekly markets over 4 weeks; 12 qualifying; 1 YES resolution(s) among them. All inference below the discipline bar; treat point estimates as directional only._
