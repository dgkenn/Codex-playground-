# BTC_DEEP — Deep BTC direction signal -> Kalshi BTC 15-min transfer test

**Verdict (one line): NO transferable edge. The Kalshi mid already prices everything,
and the residual is sub-cost (negative, in fact) at every decision minute.**

The single biggest finding makes the result almost a foregone conclusion:

> **The Kalshi BTC settle index (`spot_path`) is EXACTLY the Coinbase BTC-USD 1-min close**
> — identical at every minute of every window (median |diff| = 0.0, corr = 1.0,
> 37,755 minute-level comparisons, 100% exact match). The thing we'd "lead" IS Coinbase.

So the only conceivable residual edges are (a) a *different* venue (OKX-USDT) leading
Coinbase intra-window, or (b) Coinbase sub-1-min flow the 1-min sampling misses. Both fail.

---

## Data

| Source | What | Coverage | Limit |
|---|---|---|---|
| Kalshi parquet | 2,534 windows, 2026-04-29 → 2026-06-13 (~46d), 15×1-min mid/bid/ask/vol/spot paths + 60-min pre-spot, `res_up` | full | `res_up` 48.3% up (balanced) |
| Coinbase BTC-USD 1m | OHLCV+vol, **full range** (64,441 candles) | 99.3% window-start hit | == settle index (no lead-lag possible) |
| OKX BTC-USDT 1m | OHLCV+vol, **full range** (64,900 candles) | 100% | contemporaneous w/ Coinbase, no lead |
| OKX funding | funding-rate-history (BTC-USDT-SWAP) | full | slow (8h cadence) → near-constant within 15m |
| OKX OI / liquidations | open-interest-volume | **recent-only (~2 days)** | NOT usable over the 46-day range — excluded, stated honestly |

CEX **trade-level** history is recent-only on these public endpoints, so deep order-flow
(true CVD, large-trade imbalance) is approximated by **1-min candle signed volume**
(`sign(ret)*vol`) — a coarse CVD proxy. This is a genuine data limit; a true tick CVD
*could* in principle differ, but see the lead-lag result below for why it almost certainly
wouldn't help: there's no 1-min predictive structure to refine.

Binance/Bybit geo-blocked (not pulled), as expected.

---

## Lead-lag test (the premise the whole edge rests on)

- `corr( OKX_ret[t], index_ret[t] )` = **0.9874** (contemporaneous — they move together)
- `corr( OKX_ret[t], index_ret[t+1] )` = **0.0052** (OKX prior minute vs index next minute)

OKX-USDT does **not lead** Coinbase at the 1-min resolution that matters for settlement.
Coinbase IS the settle reference, so it cannot lead itself. **No exploitable lead-lag.**

---

## Model

Decision minutes k = 2..12. Label = `res_up`. Time-ordered split: first 65% train
(2,534 → 1,647), last 35% OOS (887 windows, 2026-05-28 → 2026-06-13).

Features (info available by minute k only):
- **A. Spot-path** (from `spot_path[0..k]` + 60-min `spot_prev`): multi-horizon momentum
  (1/2/3/5-min), acceleration, realized vol (window + prior-60), distance-to-strike,
  range-position microstructure, minutes-left, Kalshi book spread/volume.
- **B. CEX**: Coinbase & OKX window returns, cross-venue basis, 1-min "lead" delta,
  cumulative volume, signed-volume CVD proxy.
- **C. Derivatives**: OKX funding level/sign.

Models: HistGradientBoosting (GBM) and L2 logistic. Mid baseline = `mid_path[k]` directly.

**Mid is already an excellent forecast** (OOS AUC): k2 0.740 → k6 0.857 → k9 0.907 →
k12 0.973. This is the bar.

The standalone signal tracks the spot move (AUC 0.71 → 0.96) but is **strictly worse
than the mid at every k** — it's re-deriving what the mid already knows, with noise.

---

## THE KEY NUMBER — incremental AUC over the mid (OOS)

Two framings, both **negative at every decision minute**:

| k | mid AUC | sig AUC | **dAUC_clean** = AUC[logit(mid)+sig] − AUC[mid] | best EV/trade (net 3c) | t |
|--:|--:|--:|--:|--:|--:|
| 2 | 0.740 | 0.709 | **−0.056** | −0.021 | −1.2 |
| 3 | 0.757 | 0.726 | **−0.065** | −0.020 | −1.3 |
| 4 | 0.778 | 0.738 | **−0.077** | −0.048 | −3.1 |
| 5 | 0.818 | 0.775 | **−0.080** | −0.026 | −1.7 |
| 6 | 0.857 | 0.816 | **−0.072** | −0.034 | −2.2 |
| 7 | 0.867 | 0.830 | **−0.068** | −0.044 | −1.9 |
| 8 | 0.886 | 0.857 | **−0.053** | −0.033 | −2.0 |
| 9 | 0.907 | 0.884 | **−0.034** | −0.042 | −2.8 |
| 10 | 0.933 | 0.918 | **−0.020** | −0.028 | −1.6 |
| 11 | 0.953 | 0.930 | **−0.028** | −0.058 | −3.5 |
| 12 | 0.973 | 0.960 | **−0.013** | −0.044 | −1.8 |

- **dAUC_clean mean = −0.0516; max (least bad) = −0.0134.** Adding the full deep signal to
  the mid never improves OOS AUC — it degrades it (the model overweights a noisy signal
  the mid already absorbed). The GBM-blend framing (`dauc`) is also negative everywhere.

**This is the decisive answer: the residual over the mid is ≤ 0. There is nothing to clear the cost.**

---

## Directional-taker EV vs cost

When the blended model disagrees with the mid by > threshold, take the binary side it
favors; pay ~mid, net **3c** cost (mid of the stated 2–4c band).

- **EV/trade is negative at every k and every threshold tested (0.03–0.15).**
  Mean best-case EV = **−0.036/contract**; several are statistically significant losses
  (t < −2.5, e.g. k4 −0.048 t=−3.1; k11 −0.058 t=−3.5).
- The disagreements between model and mid are the **model being wrong**, not the mid.
  Even at **zero cost** the directional bet does not have positive expectancy.

**Directional taker: dead. EV < 0 before costs; nowhere near clearing 2–4c.**

---

## Channel B — box improvement (the lower bar)

Tested at an early open minute (k=3) whether the signal helps strand-avoidance / skew:

- Signal directional acc 0.672 < mid 0.687.
- Wrong-side (strand-proxy) rate on **signal-confident** subset: 0.301 / 0.287 / 0.257
  (for |p−.5| > .10/.15/.20). But the **mid-confident** subset is strictly better:
  **0.271 / 0.227 / 0.182**. The mid is a *better* filter than the signal.
- Conditioning on signal–mid agreement (0.295 vs 0.442 disagree) only reflects the mid
  doing the work; the signal adds no separation the mid lacks.

**No box improvement.** It cannot push strand below what conditioning on the mid alone
already achieves (the pair-gate's 1.9% strand floor keys off the mid, which dominates).

---

## OOS stability (walk-forward, 3 expanding folds)

dAUC_clean stays negative in all folds, both horizons:

| fold | k=6 dAUC | k=9 dAUC |
|--:|--:|--:|
| 0 | −0.042 | −0.040 |
| 1 | −0.082 | −0.028 |
| 2 | −0.053 | −0.047 |

Stable negative — not a single-period artifact.

---

## Honest verdict

1. **Directional taker:** EV/trade negative at every k (mean −0.036, several t<−2.5),
   negative even at zero cost. Does not clear 2–4c. **NO.**
2. **Box improvement:** signal is a *worse* strand/skew filter than the mid; zero delta. **NO.**
3. **Incremental AUC over the mid (the key number):** **negative at every decision minute,
   mean −0.052, best −0.013.** The mid already prices the deep CEX signal.
4. **Why it's airtight:** the Kalshi settle index *is* Coinbase 1-min close, and OKX does
   not lead Coinbase at 1-min (next-min corr 0.005). There is no slow-book residual for the
   thin Kalshi 15-min market to misprice, because the reference series is the very CEX series
   we're mining — and the mid tracks it to AUC 0.97 by minute 12.

**Concrete next step (if pursued):** the only untested crevice is **sub-1-minute** Coinbase
order-flow in the *final ~30–60 seconds* before settlement (tick CVD / book imbalance), pulled
**live** going forward (history is recent-only). Even there the prior is hostile: the mid at
k=12–13 is already AUC 0.97–0.99, leaving almost no headroom above a 2–4c cost. Recommend
**not** building a directional BTC taker and **not** conditioning the box on this signal;
the mid is the sufficient statistic.

---
*Backtests SCREEN, they don't confirm. The numbers above are OOS with realistic 3c cost and
walk-forward checks, and they all point the same way. Held the honesty bar: in-sample AUC of
the signal looks fine (0.7–0.96) but that's the signal re-deriving the mid; incremental over
the mid is what matters, and it is ≤ 0.*
