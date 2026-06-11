# Directional-signal ensemble for the unpaired leg (the "stack many weak signals" approach)

GOAL: predict BTC's move over the remaining 15-min window so we know what to do with an UNPAIRED leg
(hold if it's on the predicted-favorable side, exit/hedge if not). Edges are weak — we stack many.

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
