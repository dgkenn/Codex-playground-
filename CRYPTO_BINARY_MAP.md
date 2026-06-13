# Complete map: positive-EV search across Kalshi crypto binaries (2026-06-13)

Operator /goal: find positive EV/Sharpe in non-BTC crypto. We iterated exhaustively. This is the
complete surface tested — every asset x tenor x structure x strategy — with the unifying reason.

## What was tested (≈14 distinct strategies, 4 assets, 2 tenors, 3 structures)
| Surface | Strategies tried | Result |
|---|---|---|
| BTC 15-min single-strike | maker box + full strand ladder (our LIVE strategy) | the ONE with edge; deployed |
| ETH 15-min single-strike | box, favorite-longshot, BTC lead-lag, spot-GBM fair-value, reversion maker, toxicity-gated maker, A-S inventory maker, counterparty follow/fade | ALL -EV (7+ angles) |
| SOL 15-min single-strike | efficiency, favorite-longshot, box/maker, best-EV attempt | -EV (1 unstable deep-fav flicker) |
| XRP 15-min single-strike | same battery | -EV (wider spread = worse) |
| Cross-asset (4) relative value | basket/common-factor, lead-lag pairs, RV mispricing | -EV (factor already priced) |
| Hourly MULTI-STRIKE ladder (ETH/SOL/XRP/BTC) | monotonicity arb, vertical/box/butterfly arb, near-money F-L, longer-tenor maker box | -EV (ladders internally consistent; longer tenor WORSE) |

## The unifying structural law (why everything except BTC-box is closed to US)
1. EVERY crypto-binary mid is informationally EFFICIENT at our timescale — beats a spot-GBM/BS fair
   value, near-martingale. We have NO predictive edge (no faster data than the market).
2. The bid-ask spread is FAIR compensation for adverse selection. A resting maker fills exactly when
   wrong; spread capture is real but swamped by the 0/1-payoff inventory loss when price crosses.
3. THINNER alts are WORSE, not better (XRP 2x spread + more adverse sel) — refutes "retail = easy".
4. The common factor is already priced (cross-asset delta-AUC ~0) — no relative-value residual.
5. Multi-strike ladders are internally CONSISTENT — no static cross-strike/box arb (violations are
   one-sided-book mid artifacts that die at bid/ask; 0 capturable after a persistence filter).
6. LONGER tenor makes the binary box WORSE: more time => more chance price crosses the strike =>
   MORE adverse selection. (Refutes the longer-tenor hypothesis directly.)
7. Crypto TAKER fee (ceil(M*P*(1-P)), M~0.07-0.14) + crossed spread = a 2-4c wall no edge clears;
   makers are fee-free but face the adverse-selection trap.

=> The operator's dichotomy resolves to a THIRD answer, now exhaustively confirmed: the winners are
   HFT MAKERS (queue priority, sub-second quote-pull, scale) capturing the spread off both naive AND
   "informed" takers (who all lose net of the spread they pay). That edge requires speed/structure a
   seconds-latency GitHub-Actions bot CANNOT access. A winning strategy exists — it just isn't ours.

## The honest conclusion + where we DO have edge
- NON-BTC crypto binaries (15-min and hourly, single- and multi-strike): NO accessible positive-EV
  strategy. Stop iterating this surface — the wall is structural, not a tuning gap, and is consistent
  across ~14 strategies. ETH's only durable use = the BTC-strand cross-asset hedge leg.
- The ONE place we have demonstrated edge is the BTC 15-min MAKER BOX (our deployed strategy) + its
  locked strand ladder. The productive path is to MAKE THAT BETTER AND BIGGER (the box-yield + ladder
  + forward-A/B work), and SCALE per SCALE_GATE — not to chase efficient alt markets.
- Only re-open an alt market if we acquire a STRUCTURAL edge we currently lack: lower latency / direct
  feed (be the fast maker), a maker-rebate/scale tier, or a genuinely new data source. Absent that, alts
  stay closed. (Watch-only: SOL deep-favorite +3pp flicker, if it ever stabilizes in forward data.)
