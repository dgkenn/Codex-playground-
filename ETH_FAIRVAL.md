# ETH 15-min Binary — Spot-GBM Fair-Value Stat-Arb

**Verdict: NO positive-EV edge. The Kalshi mid is a *better* probability estimate than a
spot-GBM fair value, the gap lives inside the spread, and the faint OOS positivity is a
vol-misspecification artifact that dies at the empirically correct vol. DO NOT DEPLOY.**

Harness: `eth_fairval_study.py` (reuses `ladder_baseline_study.load_parquet_windows` schema;
builds the tradeable bid/ask/spot/strike surface directly from `hist_kalshi_eth15m.parquet`).
Data: 26,174 (window, minute) rows across 2,389 ETH 15-min windows. IS = first 60% of windows
by time (15,706 rows), OOS = last 40% (10,468 rows). `res_up` rate 0.482.

---

## 1. Fair-value model

For the up/down (YES = "settle above strike") 15-min binary:

```
fair_yes = N(d2),  d2 = ( ln(S/K) - 0.5*sigma^2*tau ) / ( sigma*sqrt(tau) ),  mu = 0 (rf~0 over 15m)
  S      = ETH spot at decision minute k  (spot_path[k-1])
  K      = strike = spot_prev[-1]  (ETH spot at window open)
  tau    = (15 - k) minutes to expiry
  sigma  = per-minute realized vol
```

**Strike identification.** The binary strike is the spot at window open. `K = spot_prev[-1]`
reproduces `res_up` for **93.6%** of windows; 96.8% of the residual mismatches have
`|sset - K| < $2` — i.e. boundary near-ties where our spot feed differs slightly from Kalshi's
settlement feed, not a model error. (`spot_path[0]` only matches 87%; `K` is the better proxy.)

**Vol calibration.** Empirical ETH per-minute log-return sigma = **0.00078** (~7.8 bps/min),
scaling random-walk-consistently to ~30 bps over the full 15 min — so GBM is structurally
appropriate. IS Brier is *minimized at an artificially low sigma=0.0004* (Brier 0.1683), which
is already a warning sign (see §5).

## 2. Calibration — fair_p vs realized (and vs the market)

OOS reliability (fair_yes bin → realized res_up) tracks the diagonal reasonably, **but the
Kalshi mid tracks it better:**

| metric (OOS)        | fair (GBM) | Kalshi MID |
|---------------------|-----------:|-----------:|
| Brier               | 0.1616     | **0.1355** |
| LogLoss             | 0.5459     | **0.4151** |

The Kalshi **mid is essentially perfectly calibrated** (0.038→0.973 across deciles, realized
0.036→0.973) and shows **no favorite-longshot distortion**. The market already prices this
binary correctly; the spot-GBM is a *worse* estimate of the same probability. There is no
mispricing for fair-value to exploit — fair is the thing that's wrong, not the price.

## 3. Gap distribution

`gap = mid - fair`: mean +0.0045, std 0.177, q10/q50/q90 = −0.205 / +0.004 / +0.210.
Mean half-spread = **0.86c** (full YES spread mean 1.91c, median 1.80c — the book is THIN).
The gap is roughly symmetric and centered at zero; its sign flips with moneyness only because
the *fair model* mis-estimates the tails (over-confident at 0/1), not because the price is biased.

## 4. Stat-arb taker (TRUE crossed prices, FEE=0)

A taker must **cross the spread**: buy YES at the YES *ask*, buy NO at `1 - bid`. Fire the side
whose post-cross edge (`fair - ask` for YES, `bid - fair` for NO) exceeds a threshold.

| thr  | IS n   | IS EV/tr | IS t   | OOS n  | OOS EV/tr | OOS wr | OOS Sharpe | OOS t |
|-----:|-------:|---------:|-------:|-------:|----------:|-------:|-----------:|------:|
| 0.00 | 14,661 | −1.01c   | −3.19  | 10,094 | +0.54c    | 58.0%  | 0.015      | 1.47  |
| 0.02 | 11,918 | −1.07c   | −2.91  |  8,257 | +0.76c    | 54.2%  | 0.020      | 1.78  |
| 0.05 |  9,312 | −1.38c   | −3.26  |  6,518 | +0.67c    | 50.8%  | 0.017      | 1.33  |
| 0.12 |  4,980 | −1.28c   | −2.24  |  3,872 | +0.63c    | 46.1%  | 0.015      | 0.93  |

- **IS EV is significantly NEGATIVE** (~−1c/trade, t≈−3) at every threshold — in-sample the gap
  is entirely swallowed by the crossed half-spread.
- **OOS EV is a tiny ~+0.5–0.8c but never significant** (t = 0.9–1.8, **Sharpe ≈ 0.02**). The
  IS→OOS *sign flip* with insignificant t is the signature of noise, not edge.
- By minute: positive at mid-window but **negative at the close** (k=12: −2.8c, wr 28.7%) where
  the model is most over-confident — the opposite of a deployable structure.

## 5. Robustness — the positive OOS sliver is a vol artifact

**Vol mis-spec (OOS, thr=0.02):** EV is positive *only* below the realized vol and vanishes/inverts
at it and above:

| sigma/min | 0.0005 | 0.0006 | 0.00078 (realized) | 0.0009 | 0.0011 | 0.0014 |
|-----------|-------:|-------:|-------------------:|-------:|-------:|-------:|
| OOS EV/tr | +0.69c | +0.46c | **+0.41c (t=0.98)** | −0.13c | −0.53c | −0.72c |

The faint OOS positivity requires *under-stating* vol (which fattens the model's tail edges into
the price). At the correct vol it is statistically zero; at any reasonable over-estimate it is
negative. Not robust.

**Favorite-longshot benchmark (no GBM, true crossed price, OOS):** flatly **negative at every
margin** (−1.5c/trade, t≈−4). So (a) there is no favorite-longshot bias to harvest, and (b) the
GBM is not even recovering one — both the model and the raw-bias play lose after crossing.

**Realism:** thin ETH book (1.8c median spread → 0.9c half-spread). 96% of gaps exceed the
half-spread, but they exceed it because the *fair model is noisier than the mid*, not because the
price is wrong — so crossing the spread to trade on them is value-destroying in-sample.

---

## Decision

| Question | Answer |
|---|---|
| Positive-EV spot-GBM stat-arb on ETH 15-min? | **No.** |
| Exact rule, if forced | best sliver: thr≈0.02, sigma=0.0004–0.0006, mid-window k (4–9) |
| EV/trade | IS **−1.0c (t≈−3)**, OOS +0.5–0.8c **(t≈1.5, NOT significant)** |
| Sharpe (OOS, per-trade) | ≈ **0.02** |
| #trades / win | ~8,000 OOS trades at thr=0.02; wr 54% (drops below 50% as thr rises) |
| IS/OOS stability | **Fails** — sign flips IS(−)→OOS(+); positivity needs wrong (low) vol |
| t vs zero | IS t = −2.9 to −3.3; OOS t = 0.9–1.8 (insignificant) |

**Why there is no edge:** the Kalshi ETH 15-min mid is *better calibrated than a Black-Scholes
fair value* (Brier 0.1355 vs 0.1616; LogLoss 0.415 vs 0.546) and carries no favorite-longshot
distortion. A spot-GBM cannot beat a price that already embeds the same spot information plus the
market's own (tighter) vol/skew view. The only apparent "edge" comes from deliberately
mis-specifying vol low, and it evaporates under the crossed spread and out of sample.

**Fee note:** this study assumed crypto15m FEE=0 (per task spec). The branch's latest fee model
suggests Kalshi crypto taker may carry a premium fee (~ceil(0.14·P·(1−P)) cents). If real, it only
deepens the loss — a taker would need ~2–4c *more* edge to clear spread+fee, and there is no edge
even at zero fee. The negative verdict is robust to (and strengthened by) any taker fee.

This is a screening backtest on historical tape; it would still require forward paper-validation
before any capital — but the screen result is clearly negative, so no forward test is warranted.
Consistent with the prior finding that ETH is structurally adverse-selected; fair-value stat-arb
does not rescue it.
