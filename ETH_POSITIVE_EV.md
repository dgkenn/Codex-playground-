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

## >>> VERDICT (7 angles, all in) — ETH 15-min has NO edge accessible to us <<<
The /goal was pursued exhaustively across the whole strategy space, grounded in the literature.
Every angle is NEGATIVE, each for a structural (not tuning) reason. Commits: lead-lag c0f6cc8,
fav-longshot 4b5afe8, fair-value 532d665, reversion e9adb67, tox-maker 88e6873, A-S fa01ad4, flow b1a5e07.

| Angle (lit-grounded) | Result | Structural reason |
|---|---|---|
| Two-sided box (maker) | -EV | adverse selection: box completes when price ran |
| Favorite-longshot taker | -EV | bias has WRONG sign on ETH; favorites realize below price |
| BTC->ETH lead-lag (taker) | -EV | no minute-scale lead (sub-second only); ETH mid AUC 0.96 |
| Spot-GBM fair-value stat-arb | -EV | the Kalshi MID beats our model (Brier .135<.162); efficient |
| Intra-window reversion (maker) | -EV | binary mid is a martingale (autocorr -.001); moves are info |
| Toxicity-gated 1-sided maker | -EV | adverse selection > spread capture at EVERY gate (both sides) |
| A-S inventory maker | -EV | 0/1 payoff has no continuous inventory to glide down; skew only cuts volume |
| Counterparty flow profiling | -EV | takers lose < spread they pay; sweeps lose WORST; all $ = spread captured by makers |

### Why your dichotomy resolves to a THIRD answer
- NOT "smart players we can follow": the informed-looking flow (sweeps, high-intensity) LOSES HARDEST
  (-1.8 to -3.3c OOS) -- they are urgency/impact payers; the mid reverts against them. Following = -3.2c after fee.
- NOT "naive bettors we can pick off": retail/round-lot flow is the LEAST-bad (~breakeven). There is no
  fat naive loss to harvest as a taker (you pay the same spread+fee), and harvesting it as a MAKER is the
  adverse-selection trap (you get filled exactly when wrong: honest fill model -9.5c/fill, t=-49).
- The TRUTH: takers (naive AND informed) lose ~0.5c/contract, but that is SWAMPED by the ~1.8c spread +
  ~2.7c crypto taker fee they cross. Nearly all the transfer is the SPREAD, captured by RESTING MAKERS
  via QUEUE PRIORITY + sub-second quote management + scale -- the colocation/HFT structure. A seconds-
  latency GitHub-Actions bot is structurally the ADVERSELY-SELECTED counterparty, not the maker who wins.
- The ETH 15-min mid is informationally EFFICIENT (a near-martingale tracking spot ~1:1); the spread is
  FAIR compensation for adverse selection. With no info edge, no speed, no rebate/scale, there is nothing
  left for us to capture. This is the THIRD case (winners win on inaccessible speed/structure).

### Constructive conclusion
- ETH 15-min as a standalone book: CLOSED. Do not deploy capital to trade it (any side).
- ETH's proven, +value use = the cross-asset HEDGE LEG for BTC strands (ETH-hedges-BTC R^2=18.6%).
- Deploy effort where we DEMONSTRABLY have edge: the BTC maker box (our live, profitable strategy) and
  its strand ladder. (NB: re-cost the BTC completion/flatten rungs for the TAKER fee, per FEES.md.)
- Genuinely-different untested directions (need NEW data/venues, not reruns of this efficient-market wall):
  (a) LONGER ETH tenor (hourly/daily) -- more time for legs to pair => less per-edge adverse selection;
  (b) CROSS-VENUE arb (ETH on Kalshi vs Polymarket/Robinhood) -- needs a 2nd venue feed;
  (c) maker-REBATE/scale tier -- changes the economics only at size we don't have.
  Recommendation: pursue these ONLY with the required data; do NOT keep iterating taker/maker variants on
  the 15-min book -- the wall is structural, not a tuning gap.
