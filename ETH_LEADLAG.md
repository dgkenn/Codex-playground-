# ETH 15-min binary: BTC→ETH lead-lag directional study

**Verdict: NEGATIVE. No positive-EV BTC→ETH lead-lag strategy on the Kalshi ETH 15-min binary.**
The lead-lag co-movement is real but (a) carries *zero* incremental information beyond ETH's
own spot move at minute resolution, and (b) is already fully priced into the ETH binary's quote,
so net edge after the crossed half-spread is ~0 to negative. Honest read: **ETH 15m is efficient
at this horizon; the directional edge < spread.**

Data: `hist_kalshi_{btc,eth}15m.parquet`. BTC & ETH share the same 15-min grid (`ws % 900 == 0`);
**1426 windows** present in both. IS = first 60% (855), OOS = last 40% (571). Base rate
`res_up` (ETH settles up) = 0.481. Signal sampled at minute resolution from `spot_path[0..14]`;
ETH binary YES quotes from `bid_path`/`ask_path`. Kalshi crypto15m FEE=0 → taker pays only the
crossed half-spread. Script: `eth_leadlag_study.py`.

---

## TASK 1 — Lead-lag predictiveness (OOS)

AUC of *BTC's* intra-window return (open→minute k) vs ETH settlement, and *ETH's own* return:

| k | BTC→ETH AUC | ETH-self AUC | BTC sign hit-rate |
|---|---|---|---|
| 3 | 0.698 | 0.716 | 64.6% |
| 5 | 0.760 | 0.793 | 70.9% |
| 7 | 0.786 | 0.837 | 72.5% |
| 9 | 0.818 | 0.873 | 75.2% |
| 11 | 0.849 | 0.907 | 76.8% |
| 13 | 0.889 | 0.950 | 80.5% |

BTC's move *does* predict ETH settlement (AUC well above 0.5, rising with k as the window resolves).
**But ETH's own move predicts at least as well at every k** — there is no BTC *lead* at this horizon.

**Incremental value of BTC beyond ETH-self momentum** (logit fit IS, eval OOS):

| k | ETH-self OOS-AUC | ETH+BTC OOS-AUC | ΔAUC | BTC logit beta |
|---|---|---|---|---|
| 5 | 0.793 | 0.793 | +0.000 | +0.14 |
| 7 | 0.836 | 0.836 | −0.001 | +0.18 |
| 9 | 0.872 | 0.872 | −0.002 | +0.18 |
| 11 | 0.906 | 0.906 | −0.001 | +0.48 |
| 13 | 0.950 | 0.950 | +0.000 | +0.38 |

**ΔAUC ≈ 0.000 at every k.** BTC adds nothing once ETH's own spot move is known. The literature's
"BTC 5-minute leads ETH" is a sub-second / few-second microstructure (liquidity-waterfall) effect;
at minute-resolution over a 15-min window the two assets move contemporaneously and ETH's own tape
already contains the information. **No exploitable lead at the 15-min binary horizon.**

---

## TASK 2+3 — Directional model + taker strategy sweep (OOS)

Model: logistic on standardized (ETH move-to-k, BTC move-to-k), fit IS, applied OOS. At minute k,
take ETH YES if `P(up) − ask > thr`, take NO if `bid − P(up) > thr`. Net PnL/contract: win `+(1−price)`,
lose `−price`. `#tr` = OOS windows traded; `tr/win%` = fraction of OOS windows that trade.

| k | thr | #tr | tr/win% | net EV | hit% | Sharpe/tr | t | IS EV |
|---|---|---|---|---|---|---|---|---|
| 3 | 0.02 | 463 | 81% | +0.66c | 46.2% | +0.015 | +0.33 | −3.14c |
| 5 | 0.08 | 303 | 53% | +0.42c | 39.6% | +0.010 | +0.17 | −0.61c |
| 5 | 0.10 | 258 | 45% | +2.06c | 39.9% | +0.049 | +0.79 | −1.97c |
| 7 | 0.04 | 392 | 69% | −1.14c | 41.3% | −0.029 | −0.58 | −0.64c |
| 9 | 0.08 | 278 | 49% | −2.28c | 34.9% | −0.062 | −1.03 | −1.03c |
| 11 | 0.02 | 368 | 64% | +0.27c | 31.8% | +0.008 | +0.16 | +0.55c |

(Full 25-cell grid in script output.) **No cell is significant.** The best OOS cell (k=5, thr=0.10:
+2.06c, t=+0.79) is *insignificant* and its IS counterpart is strongly **negative (−1.97c)** — a textbook
IS/OOS sign flip = noise. No (k, thr) shows IS and OOS both positive with |t| > 1. Net EV/trade clusters
around zero-to-negative across the entire grid; per-trade Sharpe |·| < 0.07 everywhere.

---

## TASK 4 — Realism: spread cost + efficiency + BTC replication

**ETH binary spread is thin-market wide** (OOS, cents):

| k | median spread | mean | half-spread |
|---|---|---|---|
| 3 | 2.0c | 1.9c | 1.0c |
| 7 | 1.7c | 1.8c | 0.85c |
| 11 | 1.0c | 1.6c | 0.5c |

The directional edge must clear ~0.5–1.0c of crossed half-spread; it does not.

**The market already prices the move.** AUC of the ETH binary's *own mid* vs settlement:

| k | binary-mid AUC | mid Brier |
|---|---|---|
| 3 | 0.782 | 0.190 |
| 5 | 0.839 | 0.163 |
| 7 | 0.893 | 0.132 |
| 9 | 0.934 | 0.102 |
| 11 | 0.958 | 0.078 |

**The binary mid's AUC (0.78→0.96) equals or BEATS the BTC+ETH spot model (0.72→0.91) at every k.**
The quote is a *better* settlement predictor than any spot-derived signal — the market has already
absorbed the spot move. There is no residual edge to cross the spread for.

**BTC-only replication** (trade the same signal on BTC's own binary): best cell k=11/thr=0.02 →
net EV −2.06c, t=−1.20. So the signal is not "cheaper on BTC" either — it is unprofitable on both.
The ETH binary adds nothing, and neither does BTC.

---

## Final verdict

- **Is there a positive-EV BTC→ETH lead-lag strategy on ETH 15-min?** **No.**
- **Exact rule / EV:** No rule qualifies. Best OOS cell (k=5, thr=0.10) = +2.06c/trade but
  t=+0.79 (insignificant) and IS = −1.97c (sign flip). All significant cells are ≤ 0.
- **Sharpe / #trades-per-window / t vs zero:** per-trade Sharpe |·|<0.07; t ∈ [−1.2, +0.8]; never
  significant. IS/OOS unstable (sign flips).
- **Why it fails:** (1) BTC adds ~0 AUC beyond ETH's own minute-resolution move — no real *lead* at
  this horizon (lead-lag lives at sub-second scale). (2) The ETH binary quote is already a better
  predictor of settlement than the spot model, so net edge < crossed half-spread (~0.8–1.0c).
- **Caveat:** Backtest SCREENS only. Even if a microsecond BTC→ETH lead exists, capturing it would
  require tick-level execution and would still face the spread already pricing the move. Not worth
  forward-validating as a directional taker on ETH 15m.

*Like the two-sided ETH maker box (dead to adverse selection), the directional ETH 15m taker is
killed by the same thin-book / efficient-quote reality. ETH 15m offers no exploitable directional edge.*
