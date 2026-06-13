# /goal: positive Sharpe/EV on the ETH 15-min Kalshi market (2026-06-13)

The two-sided maker BOX is DEAD on ETH (intrinsic adverse selection: a box completes precisely when
price ran; wide boxes are MORE toxic; entry-classifier AUC 0.60; strand not hedgeable R^2=4.1%).
So abandon market-making the box and pursue the edges the LITERATURE says actually exist in
betting/prediction/binary markets -- DIRECTIONAL, SELECTION, and STAT-ARB, not two-sided quoting.

## Literature review (box betting & similar) -> angles
- **BOX SPREAD arb** (options): riskless only if both legs lock; our box's "riskless" property BREAKS
  on strands. Box arb is HFT-monitored, needs near-zero fee + perfect execution. -> our box can't win;
  confirms pivot AWAY from two-sided. [chittorgarh/theoptionsguide]
- **FAVORITE-LONGSHOT BIAS** (THE most robust finding; Kalshi-confirmed, Whelan; QuantPedia): longshots
  systematically OVERpriced, favorites UNDERpriced. Buying favorites earns small +returns; longshots
  deeply negative. MATCHES OUR ETH DATA: deep-favorites (>0.70) were ETH's only non-toxic slice. ->
  ANGLE 1: TAKER-buy ETH favorites / one-sided FAVORITE maker; avoid/sell longshots. [Whelan; QuantPedia]
- **STAT-ARB vs fair value** (Kalshi event contracts vs options-implied prob): persistent mispricing
  vs a risk-neutral density. 15-min analog: a SPOT-GBM fair prob from ETH spot + realized vol. ->
  ANGLE 3: trade Kalshi price vs spot-GBM fair value (buy under, sell over), favorite-longshot-aware.
  [fsc.stevens.edu; Sussmeier]
- **BTC->ETH LEAD-LAG**: at >=100ms and ~5-min scales BTC LEADS ETH (liquidity waterfall: flows into
  BTC first, rotates to ETH; "BTC 5-minute leads"). -> ANGLE 2: use BTC's intra-window return to
  predict ETH 15-min settlement; take the ETH binary side when edge>cost. [ScienceDirect S0275531919300522;
  sotofranco; arxiv 2506.08718]
- **A-S optimal MM / toxic-flow** literature explicitly implements binary BTC options w/ Black-Scholes
  fair value + delta-hedge on perps; one-sided quoting + toxicity detection (volume imbalance, trade
  intensity) to AVOID adverse selection. -> ANGLE 4: ONE-SIDED favorite maker (capture theta, no strand)
  + toxicity gate. [arxiv 1605.01862; 1907.12433; hummingbot; arxiv 2407.04510 unwinding toxic flow]

## Angles to EXECUTE (backtest on ETH IS/OOS + live; crypto15m fee=0 so taker pays only the spread)
1. **FAVORITE-LONGSHOT taker / one-sided favorite maker.** Does ETH settle MORE often than its price
   implies for favorites (underpriced) and LESS for longshots (overpriced)? Calibration curve
   (price bucket vs realized win-rate). If favorites are underpriced by > half-spread -> taker-buy
   favorites is +EV. Also test ONE-SIDED maker on the favorite leg only (capture theta, dodge the strand).
2. **BTC->ETH lead-lag directional.** Build BTC intra-window return (and microprice/flow) -> predict
   ETH 15-min settlement direction; take the ETH YES/NO when model edge > crossing cost. OOS Sharpe/EV.
3. **Spot-GBM fair-value stat-arb.** Fair prob = N(d2)-style from ETH spot vs strike + realized vol;
   trade Kalshi - fair gap (buy under / sell over), size ~ edge. OOS Sharpe/EV vs the bias baseline.
4. **One-sided favorite maker + toxicity gate** (folded into #1): quote only the favored side, gate on
   flow-imbalance/|sig| toxicity; theta capture without two-sided strand exposure.

## Method (same discipline as the rest of the program)
Backtest each on ETH parquet IS(60)/OOS(40) + any live ETH windows; realistic taker cost = cross the
spread (fee=0); report net/win, EV/trade, Sharpe, Sortino, hit-rate, #trades/win, IS/OOS stability,
full A/B metrics. Judge vs zero (is it +EV at all) and vs a naive baseline. Winners -> forward A/B
trials (a directional/taker trial class, distinct from the box trials). HONEST: if ETH 15-min is
efficient enough that none clear, say so. Parallelize; delegate.

## Status
Launching execution agents: (A) favorite-longshot + one-sided favorite maker; (B) BTC->ETH lead-lag
directional; (C) spot-GBM fair-value stat-arb. Synthesize into a go/no-go for a positive-EV ETH strategy.
