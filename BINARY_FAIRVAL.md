# BTC 15-min Binary — Spot-Implied Fair-Value vs Price (Taker Mispricing Test)

**VERDICT: NO takeable mispricing. The Kalshi BTC 15-min PRICE is efficient vs spot — in
fact the Kalshi mid is a *better* probability estimate than any spot-implied fair value, the
distortion lives in the MODEL not the price, and a taker who crosses the spread + pays the
crypto fee loses −2 to −4 c/contract OOS at every threshold, tau and price band. There is no
favorite-longshot bias in the price to harvest. DO NOT DEPLOY a fair-value taker. The
maker-box (spread harvest) remains the only crypto angle near break-even.**

Harness: `btc_fairval_study.py`. Data: `hist_kalshi_btc15m.parquet` (read-only, NOT committed),
**2,534** BTC 15-min windows, **2026-04-29 14:30 → 2026-06-13 14:15 UTC** (~46 days), `res_up`
rate 0.483. Decision rows = one per (window, minute k=1..13) = **32,661** (S/K/tau/sigma/book
all known at decision time). Time-ordered split: IS = first 60% by `ws` (19,602 rows), OOS =
last 40% (13,059 rows; cut 2026-05-26 09:30 UTC).

---

## 0. Settle mechanic (exact) — no feed mismatch in S

Kalshi BTC15m settles on **Coinbase BTC-USD 1-min close vs strike**. Prior branch work
(`BTC_DEEP.md`) established `spot_path` == Coinbase 1-min close **exactly** (median |diff|=0,
corr=1.0, 37,755 minute comparisons). So the fair-value computation uses the *literal*
settlement series for S — there is no spot-feed error to manufacture a fake gap.

**Strike = spot at window open = `spot_prev[-1]`.** `mid[k0]` mean = **0.504** (ATM at open),
and `(settle ≥ spot_prev[-1])` reproduces `res_up` for **92.3%** of windows (n=2,515). The 7.7%
residual is boundary near-ties / exact-settle-minute feed jitter (same structure as the ETH
study's 93.6%), not a model error. This is the cleanest possible setup for the test.

## 1. Fair-value model (no lookahead)

YES = "settle ≥ strike". Driftless GBM digital (rf≈0 over 15 min):

```
fair = N(d2),  d2 = ( ln(S/K) − 0.5 σ² τ ) / ( σ·√τ )
  S = spot_path[k]  (spot at decision minute k)
  K = spot_prev[-1] (strike = open spot, known at decision time)
  τ = 15 − k        (minutes to settle)
  σ = per-minute realized vol from the PRIOR 60 minutes (spot_prev), known at open
```

Per-minute realized σ (prior-60) median = **0.000395** (~4.0 bps/min), in-window realized σ
≈ 0.00056. Both scale random-walk-consistently to ~15–22 bps over 15 min, so GBM is
structurally appropriate. I also Brier-calibrated a *single best* σ in-sample (§5).

## 2. Calibration — the price beats the model

OOS reliability + scoring (probability vs realized `res`):

| metric (OOS) | fair (GBM, prior-60 σ) | **Kalshi MID** |
|---|---:|---:|
| Brier | 0.1503 | **0.1398** |
| LogLoss | 0.4535 | **0.4240** |

The **mid is essentially perfectly calibrated** (reliability 0.01→0.01, 0.41→0.42, 0.90→0.91,
0.99→0.99) and shows **no favorite-longshot distortion**. The GBM fair value is calibrated
*ish* but strictly worse, and its error is at the **tails** (it is over-confident: fair 0.84→
real 0.91, fair 0.13→real 0.09). The market already prices this binary correctly; the
fair-value is the thing that's wrong.

## 3. Where the "deviation" lives — in the MODEL, not the PRICE

`gap = mid − fair` over all 32,661 rows: overall mean **+0.0006**, std 0.103 (centered at zero).
But split by price band it is large and **signed by moneyness**:

| price band (mid) | mean gap | n |
|---|---:|---:|
| longshot <0.15 | **−0.060** | 6,959 |
| 0.15–0.35 | −0.060 | 5,331 |
| ATM 0.35–0.65 | +0.001 | 8,659 |
| 0.65–0.85 | +0.064 | 5,113 |
| favorite >0.85 | +0.064 | 6,599 |

This *looks* like a harvestable bias — until you check **which series is right**. The
favorite-longshot table (bin by mid → realized vs fair) settles it:

| mid bin | mid | **realized** | fair | n |
|---|---:|---:|---:|---:|
| 0.0–0.1 | 0.033 | **0.027** | 0.090 | 5,648 |
| 0.4–0.5 | 0.451 | **0.431** | 0.462 | 2,861 |
| 0.5–0.6 | 0.551 | **0.521** | 0.537 | 2,932 |
| 0.9–1.0 | 0.967 | **0.971** | 0.907 | 5,325 |

The **mid tracks realized almost exactly** (0.033→0.027, 0.967→0.971). The **fair value is the
distorted one** — it pulls longshots UP (0.090 vs 0.027 real) and favorites DOWN (0.907 vs 0.971
real). So the signed gap is the GBM *under-pricing the market's confidence at the tails*, i.e.
the model under-states how decisive the late spot move is. A taker trading the gap is betting on
a model error against a correct price. This is the exact inverse of a harvestable bias.

## 4. Taker backtest — cross the spread, hold to settle (OOS)

Taker buys YES at the **ask** (or NO at **1−bid**) on whichever side `fair` says is cheap by
> thr, holds to settlement. PnL = payoff − price paid − **crypto taker fee**
`ceil(M·P·(1−P)·100)/100` (M=0.07 std, M=0.14 crypto-premium). BTC book is tight: median YES
spread **1.0 c**, half-spread ~0.43 c.

**M=0.14 (crypto premium):**

| thr | IS n | IS EV/tr | IS t | OOS n | OOS EV/tr | OOS t | OOS wr |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 18,390 | −2.81 c | −10.1 | 12,239 | **−3.24 c** | −9.5 | 0.316 |
| 0.02 | 13,612 | −2.78 c | −8.3 | 9,053 | **−3.68 c** | −9.1 | 0.291 |
| 0.03 | 12,054 | −2.66 c | −7.5 | 7,918 | **−3.79 c** | −8.8 | 0.275 |
| 0.05 | 9,380 | −2.70 c | −6.8 | 6,012 | **−4.10 c** | −8.3 | 0.245 |
| 0.12 | 3,548 | −2.29 c | −3.7 | 2,087 | **−3.15 c** | −2.8 | 0.187 |

**M=0.07 (standard, a lower bound on the fee):** OOS EV −2.2 to −3.1 c, t = −2.8 to −6.5 — still
deeply negative at every threshold.

- **Negative IS *and* OOS**, t ≈ −7 to −10, monotonically *worse* as the threshold rises (raising
  thr selects rows where the model disagrees with the price MORE — i.e. where the model is most
  wrong). Win-rate *falls* with thr (0.32→0.19). This is the signature of trading model error.
- **Edge location (OOS, thr=0.03, M=0.14):** negative in every tau band (t1-3 −1.2 c, t12-14
  −6.6 c) and every price band (longshot −0.0 c, ATM **−8.6 c**, low/high −3 to −5 c). The loss is
  worst at ATM and near settle — exactly where the model's tail mis-estimate bites hardest. There
  is no tau/price pocket where it is positive.

## 5. Robustness — it is NOT a recoverable vol-misspecification

The ETH study's positive sliver came from *under-stating* vol; here even the calibrated vol loses:

- **IS-Brier-min single σ = 0.000300** (even lower than prior-60). At that σ the fair value is
  *still* worse than the mid (OOS Brier **0.1567** vs mid 0.1398) and the taker loses **MORE**
  (OOS EV **−4.2 c**, t −10). Calibrating the model does not rescue it — it cannot beat a price
  that already embeds the same spot plus the market's tighter vol/skew view.
- **Vol sensitivity (OOS, thr=0.02, M=0.14):** σ×0.6 → −4.0 c, σ×1.0 → −3.7 c, σ×1.5 → −3.4 c.
  **Negative at every vol** — there is no σ (high or low) that flips it positive. Unlike ETH (where
  a low-σ sliver briefly turned positive at fee=0), BTC has no such crevice even before the fee.

## 6. Capacity vs the maker-box

The taker question is "is there edge to scale," and the answer is no edge, so capacity is moot —
but for completeness: the BTC15m tape is **liquid** (median ~7,400 executions/window, median trade
20 contracts, up to 97k; ~$12–26k notional/window), so a taker is *not* queue-limited the way the
maker-box is (the box saturates ~$500/book, ~$2–10/day and only if strand <5%). A taker could lift
far more size and carries **no strand risk** (you take, you're filled). That is genuinely the
attractive part of the premise — but it is attached to a **negative-EV** signal, so the capacity
and strand-free properties buy nothing. A bigger, strand-free way to lose money is still a loss.

## 7. Comparison & decision

| Question | Answer |
|---|---|
| Systematic signed price-vs-fair deviation? | Yes by moneyness (±6 c), but it is the **model** wrong, not the price |
| Favorite-longshot bias in the PRICE? | **None** — mid is calibrated (0.033→0.027, 0.967→0.971) |
| Taker +EV OOS net of spread+fee? | **No.** −2.2 to −4.1 c/contract, t −3 to −10, every thr/tau/band |
| Recoverable by re-calibrating vol? | **No.** Best-Brier σ loses more; negative at all σ |
| Capacity / strand vs maker-box? | Bigger & strand-free — but on a losing signal, irrelevant |
| Run alongside / instead of the box? | **No.** The box (maker, ~fee-free) is the only viable crypto angle |
| Takeable rule + c/contract | **None exists.** Expected ≈ **−3 to −4 c/contract** at any rule |

**Why it's airtight:** the Kalshi BTC settle index *is* the Coinbase 1-min close, the Kalshi mid
tracks realized to Brier 0.140 / perfect reliability with zero favorite-longshot distortion, and a
spot-GBM (even optimally calibrated) is a strictly worse estimate of the same probability. The
price is efficient vs spot. Crossing a 1 c spread + a 2–4 c crypto fee to bet a model that the
price already beats is value-destroying by construction, and the data confirm −3 to −4 c OOS with
t ≈ −10.

---
*Screening backtest on historical tape (OOS + walk-forward-consistent split + vol-robustness).
Costs: crossed half-spread (true ask / 1−bid) + crypto taker fee at M=0.07 and M=0.14. The result
is decisively negative, so no forward paper test is warranted. Consistent with `ETH_FAIRVAL.md`
(efficient) and `BTC_DEEP.md` (mid is the sufficient statistic). SCREENS, doesn't confirm — but
nothing here is near deployable.*
