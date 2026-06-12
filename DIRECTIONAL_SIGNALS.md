# Directional-signal ensemble for the unpaired leg (the "stack many weak signals" approach)

GOAL: predict BTC's move over the remaining 15-min window so we know what to do with an UNPAIRED leg
(hold if it's on the predicted-favorable side, exit/hedge if not). Edges are weak — we stack many.

## ⭐ TESTED VERDICT (k=7 decision point, 1158 windows, IS/OOS): NO incremental edge
We built and rigorously tested the stack. **Result: there is no OOS directional edge beyond what the
Kalshi binary's own mid-window price already tells you.**
- The spot/flow signals (mom1/3/5, MACD, z-score, CVD, aggressor, kalshi_drift) ARE statistically
  significant predictors of `res_up` (OOS IC up to 0.50, survive Bonferroni) — but they are all
  collinear proxies for "has BTC moved since the open / is the binary above 50c", which the binary
  price already aggregates.
- **Ensemble OOS AUC 0.859 vs the baseline `mid[7]` alone AUC 0.883 — the stack is WORSE than just
  reading the current price.** Incremental lift is negative.
- Unpaired-leg use: gating the hold/exit on the ensemble modestly cuts wrong-sided YES-leg losses
  (−0.021→−0.010/window OOS) but also halves profitable NO-leg holds — a wash, driven by the same
  info as the price.
- **The correct, simple rule: read the binary's own mid. If an unpaired YES leg has mid<0.5, the
  market itself says it's disfavored — a better exit signal than any computed feature stack.**

This is the efficient-market result for THIS prediction: the Kalshi price is already efficient vs
spot-derived signals at the 7-min mark. The RenTech method was executed correctly; the data says the
edge isn't there. **Do NOT build a directional-signal-gated rule on this stack.**

What still might work (NOT refuted here, because it needs data we don't yet have): the **cross-venue
Polymarket lead-lag** (#21). The test used only Kalshi+spot; the open question is whether Polymarket's
deeper 5-min book *leads* Kalshi (incorporates info FASTER), which would beat Kalshi's own price. High
bar, but it's the one remaining directional candidate — worth the collection effort, nothing else is.

## The honest frame (read first)
15-min BTC direction is near-efficient. The Renaissance approach earns its edge through **breadth**:
many tiny signals (IC 0.02–0.08), high rebalancing, massive data. We have limited data, so the only
thing that matters is **rigorous out-of-sample validation** — in-sample Sharpe is meaningless. We
deploy signals only if they survive walk-forward OOS and the **Deflated Sharpe Ratio** (López de
Prado-Bailey: penalize for the number of trials). Done loosely this is a way to fool ourselves; done
with discipline it's a small, real edge that improves the unpaired-leg decision.

Grinold's Fundamental Law: `IR ≈ IC × √breadth`. 30 signals at IC 0.03 → IR ≈ 0.16 — tradeable IF
the signals are orthogonal and the IC is real OOS.

## How the top shops do it (signal philosophy)
Renaissance: hundreds of transient anomalies, breadth IS the edge. Two Sigma: ML factor zoo + decay
monitoring. Jane Street/XTX: cross-venue/instrument coherence (arb-first, not directional). Jump/HRT:
microstructure (queue, flow) at huge breadth + low latency. DRW/Cumberland/Wintermute: flow toxicity
+ funding/CVD skew to lean quotes. Citadel Sec/DE Shaw: regularized multi-factor ensembles weighted
by vol regime. **Common thread: every signal is weak; alpha = stacking many orthogonal ones.**

## The 30-signal menu (grouped; * = computable from data we already collect)
- **Momentum/trend:** *short-window return (5m), *multi-scale momentum vote (1/5/15/60m), *MACD-proxy
  (EMA3−EMA10), breakout flag, *return skew.
- **Mean-reversion:** *Bollinger z-score, *RSI(7), VWAP-gap reversion, funding-basis deviation.
- **Order-flow:** OFI (L1), 5-level OFI, *CVD (taker buy−sell cumsum), *aggressor ratio,
  *Kalshi trade imbalance, Kalshi OFI.
- **Microstructure:** *microprice drift, *queue imbalance (L1), spread regime (shrinker), depth slope,
  VWAP-to-mid.
- **Cross-venue/asset:** **Polymarket−Kalshi divergence** (the standout once the feed is wired),
  *ETH lead, *SOL/BTC beta divergence, cross-exchange funding skew, BTC dominance delta.
- **Vol/regime:** *realized vol (RV5, shrinker), *vol-of-vol (shrinker), implied-vol proxy.
- **Calendar:** *time-of-day return bias, *day-of-week effect.

(* signals are testable now from spot_path + the trade tape; the depth/cross-venue ones need the live
book stream + the Polymarket collector, which are accumulating.)

## Ensembling rules (anti-overfit, frozen)
1. **Orthogonalize:** drop/merge signal pairs with |ρ|>0.7; PCA/Gram-Schmidt the rest.
2. **Ridge, never OLS** (L2 penalty tuned by time-series CV) — shrinks correlated signals, prevents
   weight explosion on short history.
3. **Sign-agreement gate:** act only when ≥40–50% of signals agree (no free params, kills
   regime-transition false positives).
4. **Walk-forward only**, retrain weekly. In-sample is ignored.
5. **Deflated Sharpe > 1.0 OOS** before any deployment (adjust for # trials).
- Minimum viable: start with 6–8 highest-SNR signals (OFI, CVD, queue imbalance, MACD-proxy,
  funding basis, Polymarket/Kalshi divergence), expand only as data accumulates.

## How we use it on the unpaired leg
At the decision point (a leg is unpaired, mid-window), compute the ensemble's predicted P(up) for the
remaining window. If the unpaired leg is on the favorable side (e.g., unpaired YES and P(up) high) →
HOLD it (it's a +EV directional position). If unfavorable → exit (the validated VPIN-style cut) or
hedge (cross-strike/correlated binary). This generalizes the VPIN-conditioned exit we already proved
(OOS t=3.4 on the toxic subset) to a full directional ensemble.

Sources: Grinold (fundamental law); López de Prado & Bailey 2014 (deflated Sharpe, arXiv:1906.00573);
Cont-Kukanov-Stoikov (OFI); Stoikov (microprice); plus the crypto-microstructure refs in the dive.

## ⭐ DEFINITIVE CLOSE (2026-06-12): six tests deep, no exploitable directional/mispricing edge
The operator asked: any mispricing at any price/threshold/side, and any directional edge to manage
unpaired legs? Ran the most rigorous pass yet (4 assets pooled ~4500 windows, FDR-corrected,
strict IS/OOS):
- **Full-range mispricing calibration scan** (every YES-mid bucket 0.01-0.99 x minute 2-14 x both
  sides, Wilson CIs, Benjamini-Hochberg FDR): the 3 buckets that survive FDR *pooled* all FLIP sign
  between the IS and OOS halves -- e.g. minute-3 YES@0.60-0.65 was -0.3% (calibrated) IS but -18.9%
  OOS, a recent-regime artifact, not a stable edge. The favorite-longshot tails show the documented
  direction (favorites win slightly less than priced early) but it is NOT OOS-stable in magnitude.
  **VERDICT: the market is calibrated; no mispricing persists across time halves.**
- **Spot-lag / stale-mid directional test** (does spot momentum predict res_up BEYOND mid_k, OOS):
  adding the 3-min spot move to the Kalshi mid changes OOS AUC by -0.0006 to -0.0022 at every minute
  (5,7,9,11) -- it HURTS. Pooled 0.8984 -> 0.8983. Residual-by-spot-sign: a spot move UP leaves YES
  slightly OVER-priced (-2.4%), the opposite of a lag. **The Kalshi mid FULLY reflects spot at every
  minute-granularity we can act on.** Any "Kalshi lags spot" effect lives only at sub-second HFT
  timescales we cannot see (1Hz book) or profitably chase (no colocation) at $5-1000 scale.
- **This is the 6th consecutive null** (directional ensemble, p2-hold, t08, late-favorite calibration,
  the asymmetry-sweep holds, now spot-lag). The unpaired-leg answer is settled: PREVENTION (t02/t29
  -- don't open toxic/longshot legs) + EXECUTION (the completion chase), NOT prediction. Stop hunting
  a directional signal; the binary's own mid is the efficient forecast and nothing beats it OOS.
- The ONE microstructure angle with real IS signal is t31 (counterparty/flow: maker +1.09c vs
  contrarians IS t=19.5) -- registered, OOS pending; it conditions on WHO fills us, not price
  prediction, so it may survive where price-signals didn't. The other live candidate is cross-venue
  Polymarket lead-lag (data accumulating) -- the only place a real lag is documented.

## Exploitative-plays backtest (2026-06-12) — no clean survivor; the "stale-snipe" is fee-killed
A full legal-edge backtest (stale-quote snipe, new-window opening, flow-fade, flow-toxicity,
cross-venue) returned ONE nominal survivor (stale-maker snipe, OOS +1.5c t=2.4) — but it does NOT
hold up:
1. **It's a TAKER play** (lift the lagging quote), so it pays the TAKER fee = ceil(0.07*p*(1-p)) ≈
   **2c/contract at mid prices** — the agent wrongly assumed fee=0 (that's the MAKER rate). 1.5c
   edge − 2c taker fee = NET NEGATIVE everywhere except deep tails (p≥0.9, where fee=1c). Dead.
2. Its IS t=1.58 is NOT significant; only OOS t=2.40 — the same flips-between-halves non-robustness
   we see everywhere, and it CONTRADICTS the direct spot-lag test (spot adds −0.002 AUC over mid).
3. It needs taker capability + low-latency infra we don't have (we're post-only maker).
The agent's rigor was good on the kills: the "+17c flow-fade" is a price-level ARTIFACT (imbalance
just proxies who-overpaid), and the "+57c spot-divergence" is LOOK-AHEAD (spot_path is contemporaneous
with settlement — top-quartile spot move => 98% YES). The flow-incremental skew (#2) is real but tiny
(+0.3c) and vanishes (OOS t=0.11) in the uncertain-price regime where it'd matter. NET: confirms the
efficient-market verdict; the only edges are maker positioning (t29/t31) + the untested cross-venue
Polymarket lag (data accumulating).

## Unpaired-leg directional test (2026-06-12) — flow > spot, but still loses to always-cut
The focused unpaired-leg signal test (5 signals x k{5,7,9,11}, IS/OOS, bootstrap, economic hold/cut):
- **spot_lag dAUC = 0.0000 at every k** — independently confirms my spot-lag null. Spot is inert.
- FLOW signals (cumulative imbalance, vol-regime interaction) DO add marginal early-window OOS lift
  (dAUC +0.03-0.04 at k=5,7, fading to ~0 by k=11; combined p=0.038 AVG, not multiple-test-adjusted,
  carried by early k). This is the t31 flow family — the one angle with any signal, consistent.
- **THE ECONOMIC TELL: always-CUT an unpaired leg = $0; always-HOLD = -7.6c/leg; the signal filter
  = -3.6c.** The signal HALVES the hold-loss but still LOSES to simply cutting. So even the best
  flow signal does not beat the trivial "cut the unpaired leg" benchmark.
**Unpaired-leg answer, now triple-confirmed: PREVENT (t29 don't open toxic legs) + CUT (t11/t17 sell
the cheap toxic strands) beats any PREDICT-and-hold. Flow-conditioning (t31) is marginally real early
but not enough to hold losers profitably. Directional prediction is closed.**
