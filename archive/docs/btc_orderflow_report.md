# BTC Order-Flow Short-Horizon Predictability — Backtest Report (corrected)

**Question:** does signed order-flow imbalance (OFI) predict short-horizon BTC spot returns
out-of-sample over years, net of cost — the necessary upstream condition for a flow→15m-binary edge?

**Data:** Binance Vision spot aggTrades, **164 days sampled across 2022-01-01 .. 2026-07-11**
(1st/11th/21st of each month), signed via isBuyerMaker, aggregated to 1-min bars. TRAIN = earliest
115 days, TEST = recent 49 days. Features S_L = trailing-L-min OFI / trailing-60-min median|OFI|
(scale-free, causal), L∈{1,3}; targets = forward log-return at H∈{3,15} min.

**NOTE (bug fixed):** the initial agent aggregation reindexed each day to a contiguous *absolute
epoch-minute* range; timestamp outliers exploded this to 80.8M fabricated empty-minute rows and
OOM-killed the run. Fabricated rows have vol=0, so filtering `vol>0` recovers the true ~1,440
real minutes/day. The trade grid is computed only on genuine signal rows (|S|≥1), so it is unaffected.

## Gross momentum signal (bps/trade, no cost), day-clustered
| L | H | TRAIN mean (t) | TEST mean (t) |
|---|---|---|---|
| 1 | 3  | +0.037 (t=0.6) | +0.122 (t=13.6) |
| 1 | 15 | +0.098 (t=0.8) | +0.257 (t=17.3) |
| 3 | 3  | +0.008 (t=0.1) | +0.127 (t=16.3) |
| 3 | 15 | −0.031 (t=−0.2)| +0.288 (t=21.3) |

The gross OFI→return relationship is **positive (momentum) but microscopic (0.1–0.3 bps) and
era-unstable**: ≈ZERO in TRAIN (t<1, one cell negative), small-positive in TEST. The large TEST
t-stats come only from millions of observations, not from magnitude.

## Net of cost — the verdict
| L | H | MOM net 1bp (TRAIN/TEST) | REV net 1bp (TRAIN/TEST) |
|---|---|---|---|
| 1 | 3  | −0.96 / −0.88 | −1.04 / −1.12 |
| 1 | 15 | −0.90 / −0.74 | −1.10 / −1.26 |
| 3 | 3  | −0.99 / −0.87 | −1.01 / −1.13 |
| 3 | 15 | −1.03 / −0.71 | −0.97 / −1.29 |

Every cell, both directions, both splits, is **negative even at a 1 bp round-trip cost** (test
t-stats ≈ −50 to −145). Momentum loses ~0.7–1.0 bps/trade; reversion loses ~1.0–1.3 bps/trade.

## Verdict: NULL (well-powered)
Signed order flow has **no cost-surviving short-horizon return predictability**. The gross edge is
≤0.3 bps/trade (and ~0 in the 2022–2024 training era), obliterated by a token 1 bp cost — and the
15-min binary requires crossing a ~2–4¢ spread, i.e. **hundreds of bps** on a ~50¢ contract. The
flow does nudge price (as expected), but not exploitably, and not stably across regimes. This kills
the momentum/OFI-leads-price thesis at the tradeable level, and by extension makes the forward
EXO-OFI experiment's downstream prospects poor. Remaining untested exogenous angles: derivatives
positioning stress (running), options GEX/skew/DVOL (wave 2), and sub-second flow (not backtestable).
