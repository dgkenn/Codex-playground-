# Completion-model feature engineering — the exhaustive spec

## ⭐ v2 — the CORRECT framing: "will THIS bought leg ever pair?" (per-leg, strict temporal lockout)
The right prediction target is per-LEG and forward-looking: at the instant a leg fills at time T
(minute k, side S), predict whether the OPPOSITE leg fills in the half-open interval (T, window_end].
- **Label:** for a bid(YES) fill at minute k → 1 iff an ask(NO) fill occurs at any minute > k that
  window; symmetric for ask fills. (= "does this bought leg ever pair?")
- **STRICT TEMPORAL LOCKOUT (no leakage):** every feature uses ONLY data timestamped ≤ T. The label
  uses ONLY fills timestamped > T on the opposite side. NO markout, NO future spot, NO window-end
  info, NO same-window aggregate that peeks past T. One row per fill event.
- This matches the live decision exactly (you hold a leg; will it pair?) and produces a BALANCED
  label (live ~39% unpaired), unlike the degenerate window-level "did a box ever form" (97-99%).

### Exhaustive second-round feature set (per-leg, all ≤ T; * needs the live book stream)
**A. Leg & moment:** side(YES/NO bought), fill_price, |price−0.5|, deep_tail flag, k, tau=(15−k)/15,
seconds_remaining.
**B. Completing side's state (how hard the OTHER leg is to fill):** opposite-touch price, opposite
spread-to-mid, *opposite displayed depth, *opposite depth/our-size, lock_if_complete_now =
1−(our_price+opposite_touch), opposite-side recent fill count (≤T), time-since-last-opposite-trade.
**C. Adverse selection / "why did THIS fill":** spot move 1m/3m before T, signed spot move vs the
leg's favorable direction, *microprice−fill_price at T (adverse-selection magnitude), VPIN at T,
recent taker-flow sign vs our leg (flow hitting our side = adverse), |flow imbalance| pre-T,
aggressor ratio pre-T.
**D. Book dynamics ≤T (resiliency):** *completing-side depth trajectory (rebuild vs drain, last
30-60s), *our-side depth (were we swept?), *spread trajectory (widening=toxic), *cancel activity
pre-T, *microprice drift ≤T, *queue imbalance at T.
**E. Momentum/vol/regime ≤T:** spot returns 1m/3m/5m, realized vol, vol-of-vol, spot acceleration,
trend monotonicity, return skew.
**F. Window context (≤T only):** #legs already filled this window (same vs opposite side),
accumulation flag (multiple same-side), trade count so far, time-of-day, day-of-week.
**G. Cross-venue/asset:** *Polymarket BTC-up prob − Kalshi at T (divergence), ETH/SOL spot move ≤T,
funding skew.
**H. Interactions:** tau×opposite-depth, spot-move×leg-side, VPIN×spot-move, opposite-touch-dist×tau,
flow-adverse×tau.

The tape (candle book + trades) supports A, B(partial), C, E, F now; the depth/microprice/QI/cross-
venue features (D, parts of B/C/G) come from the live book stream + Polymarket feed (accumulating).

---
## v1 — window-level spec (kept for reference; superseded by the per-leg framing above)

The priority. Goal: predict whether OUR resting legs will both fill (box pairs) under REALISTIC
execution — not the idealized front-of-queue tape (which is 97–99% complete and has no lift to give).

## First, the label fix (this is what makes lift possible)
The prior model predicted "did the market trade both sides" (97–99% yes — degenerate). The right
label is "will OUR specific legs pair given queue position + market drift" — the live ~39%-unpaired
reality. Two sources, used together:
1. **Realistic-queue tape reconstruction** — re-run `collect_fills` at q0>0 (join BEHIND realistic
   displayed depth, e.g. q0 ∈ {500, 2000, 5000}); fewer fills, balanced completion label, matches
   live. THIS is the prediction problem with real lift.
2. **Live `window_audit` data** — the actual unpaired outcomes (now durably accumulating). The
   ground-truth label as data builds.

## The exhaustive feature set (~50, grouped; * = needs the live book stream, accumulating)

**Price / level (the binary's own state):**
p_yeq (YES-equiv price), |p−0.5| (distance from ATM), deep-tail flag (p<0.2 | >0.8), mid drift
(mid_k−mid_2), spot−strike normalized, price percentile vs trailing windows, last-trade vs mid.

**Spread / liquidity:**
spread, spread / trailing-median-spread (regime), *top-5 YES depth, *top-5 NO depth, *min(YES,NO
depth) (bilateral thinness), *depth imbalance (Q_bid−Q_ask)/(Q_bid+Q_ask), *depth slope (Σ qty×dist
over levels), *one-sided-book flag.

**Order flow (the strongest validated family):**
early signed flow (buy−sell, min 0–3), CVD (cumulative volume delta), aggressor ratio (buy/total),
**early_trade_count** (the dominant predictor, OOS AUC 0.985), trade-count acceleration,
**ofi_sign_agreement** (YES-side vs NO-side flow direction; the #2 predictor), OFI L1 (Δbid−Δask),
avg trade size, large-trade flag (>N× median), flow/depth ratio.

**Microstructure:**
*microprice, *microprice−mid (drift), *microprice-mid divergence / (spread/2), *queue imbalance L1,
**VPIN** (equal-volume flow toxicity), *spread volatility.

**Momentum / spot / vol:**
spot returns 1m/3m/5m (multi-scale), realized vol (σ of 1-min returns), vol-of-vol, spot
acceleration (2nd diff), |spot move| bps (toxicity), spot−VWAP, 1-min return skew.

**Time / calendar:**
minute-in-window / tau, time-of-day (hour UTC), day-of-week, seconds-since-open.

**Cross-venue / cross-asset:**
ETH spot lead (lagged ETH return), SOL/BTC beta divergence, **Polymarket−Kalshi divergence** (the
deeper 5-min book; accumulating via pmkt_collect), funding-rate skew.

**Engineered interactions (where the nonlinear lift hides):**
depth×flow, spread×vol, |p−0.5|×tau, flow×ofi_agreement, early_trade_count×|spot move|.

## Model + the RIGHT statistical lift tests
- **Models:** regularized logistic (L2, the robust baseline) AND gradient-boosting (LightGBM/sklearn
  GBM) for nonlinear interactions; **class-weighted** (completion is imbalanced); **probability
  calibration** (isotonic/Platt) since we act on P(complete) thresholds.
- **Validation:** time-series WALK-FORWARD (expanding window, retrain), never random CV — prices
  autocorrelate.
- **Lift tests (imbalance-aware, the part the user flagged):**
  1. **PR-AUC / average precision** (not just ROC-AUC — ROC is optimistic under 97% base rate).
  2. **DeLong test** for ROC-AUC difference: model vs (a) the binary's own price baseline, (b) the
     best single feature. Is the lift statistically significant?
  3. **Bootstrap CI on the ECONOMIC objective** — does gating on P(complete)>τ improve net/window
     and cut the unpaired-leg rate OOS, with a 95% CI that excludes zero? (Lift = money, not AUC.)
  4. **Multiple-testing guard** — with ~50 features and many thresholds, apply a Bonferroni/deflated
     adjustment (López de Prado) before believing any single result. In-sample AUC means nothing.
- **Feature selection:** drop |ρ|>0.7 pairs; rank by walk-forward permutation importance; keep the
  stable-OOS ones (the directional-test lesson: many significant features are collinear proxies).

## Honest expectation
On the realistic-queue label there SHOULD be real lift (the live problem has 39% failures to predict,
vs 1.9% on the idealized tape). But per the directional-test result, much of the "signal" may be the
binary's own price/early-activity — the model must beat THAT baseline OOS, by the DeLong + economic
bootstrap, or it's not worth deploying.
