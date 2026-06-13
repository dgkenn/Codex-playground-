# /goal: positive EV/Sharpe in ANY non-BTC crypto market — VERDICT (2026-06-13)

Tested the ENTIRE non-BTC 15-min crypto complex on Kalshi. ALL NEGATIVE. Commits: ETH 7-angle suite
(c0e337f verdict); SOL b9964a9; XRP de7c2e1; cross-asset 8bfe16e.

| Market | Mid efficiency | Box/maker | Best edge found | Verdict |
|---|---|---|---|---|
| ETH 15m | EFFICIENT (mid beats BS, Brier .135<.162; martingale) | -EV (adverse sel) | none (7 angles) | DEAD |
| SOL 15m | EFFICIENT (Brier .160<.203; martingale) | -EV (-13.8c, 59% strand) | deep-fav bias +3pp BUT IS/OOS UNSTABLE | DEAD (1 flicker) |
| XRP 15m | EFFICIENT (Brier .144<.153; martingale) | -EV (-15c, ~60% strand) | fav bias <= 4c spread | DEAD (worse: 2x spread) |
| Cross-asset | alts already price the BTC-led factor (delta-AUC ~0) | n/a | none (multi-leg cost > divergence) | DEAD |

## The structural law (now confirmed across 4 markets + 10 angles)
1. EVERY 15-min crypto binary mid is informationally EFFICIENT — a near-martingale that BEATS a
   spot-GBM/BS fair value. We have NO predictive edge over the mid at our (seconds) latency.
2. The bid-ask spread is FAIR compensation for adverse selection. A resting maker fills exactly when
   wrong (honest fill model). Spread capture is real but ALWAYS swamped by the 0/1-payoff inventory loss.
3. THINNER ≠ more exploitable. XRP (thinnest) is WORSE: ~2x spread (4.07c vs ETH 1.90c) and more
   adverse selection. The "retail-dominated alt = easy money" hypothesis is REFUTED by data.
4. Co-movement is huge (PC1=77%, settlement corr .59-.75) but the alt binaries ALREADY embed the
   common factor -> no residual cross-asset divergence to capture after multi-leg cost.
5. Taker fee (crypto premium, ceil(M*P*(1-P)), M~0.07-0.14) + crossed spread = a 2-4c wall that no
   edge in any market clears. Makers are fee-free but face the adverse-selection trap.
=> The winners here are HFT makers (queue priority, sub-second pull, scale) — inaccessible to a
   seconds-latency GitHub-Actions bot. This is the THIRD case, now multiply confirmed.

## The ONE flicker (not deployable, but the only non-dead signal)
SOL deep-favorites (mid >= 0.85) realize ~3pp ABOVE quote (right-signed favorite bias, unlike ETH/XRP).
The only cost-clearing taker cell (buy YES at ask, mid in [0.90,0.97)) is OOS +2.3c (t=2.8) but IS-flat
(t=0.7) with 1 of 4 quartiles at -2.76c -> regime/tail trade, NOT a repeatable edge. Watch, don't deploy.

## BTC completion/flatten fee re-cost (FEES.md action item — done)
BTC completion crosses (taker) pay ~1.15c (M=0.07) / ~1.62c (M=0.14) per contract (strand price mean
0.39, clusters low). The prior "complete beats hold +4.63c/strand" becomes ~+3.0-3.4c after fee ->
COMPLETION REMAINS OPTIMAL (conclusion stands, benefit smaller). ETH flatten-all (+0.91c) is WIPED by
the fee (moot; ETH closed). The live BTC maker box itself is post-only ~fee-free; only the crossing
rungs take the haircut. No live change needed; completion stays on.

## Recommendation
- The 15-min crypto complex (BTC excepted, where we MAKE money) is EFFICIENT for us: CLOSE non-BTC
  15-min as standalone books. Keep ETH as the BTC-strand hedge leg.
- The ONLY mechanistically-motivated UNTESTED direction: LONGER TENORS (hourly/daily alt markets).
  Rationale: the killer is the 0/1 payoff's adverse selection + no continuous inventory to manage; a
  LONGER window gives more time for both legs to pair (lower strand rate) and a larger edge-per-trade
  vs the same spread. Data is fetchable (fetch_kalshi.py with the hourly/daily series). This is the
  next test worth running; more 15-min variants are not (structural wall, not a tuning gap).
