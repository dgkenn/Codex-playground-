# edge_informed_flow.md — Informed aggressive (taker) flow on Kalshi 15m crypto binaries

**Node:** INFORMED-FLOW (2026-07-15). **Status: NULL** (directionally disconfirmed).
**Verdict:** The operator's hypothesis — that large / one-sided / clustered AGGRESSIVE (taker) bets are
informed, so heavy taker flow to one side signals an exploitable side to FOLLOW — is **rejected**.
Following heavy aggressive flow *loses* money out-of-sample, and the raw directional diagnostic shows
the followed side is *right less than half the time*. If anything, heavy early aggressive flow is a
weak CONTRARIAN indicator, and even that adds nothing beyond simply trading the book favorite
(which is FAVLONG's territory). PROPOSE-ONLY research; no live change made.

Distinct from the prior resting-quote/book-imbalance NULL: here the signal is EXECUTED aggressive
trades (the public trade tape's taker side), not resting book depth.

## Data & fields available
- Trade tape `trades_kalshi_<asset>15m_*.jsonl.gz`, fields per print:
  `t` (recv ts), `ts_exch`, `tid`, `ws` (window-start epoch), `asset`, `tenor_min`, `venue`,
  `up` (always 1 — single YES=above-strike contract), **`side` (BUY/SELL = the AGGRESSOR/taker side)**,
  `p` (YES price 0.001–0.999), `sz` (contracts). **Aggressor side IS identifiable** (`side` = taker_side),
  which is exactly what the hypothesis needs. Deduped by `tid`, grouped by `ws`.
- Ticks `ticks_kalshi_<asset>15m_*` give `[t,mid,spot,micro,bid,bidq,ask,askq]` per window — used for
  decision-time executable price (buy@ask / sell@bid) and settlement reconstruction (terminal mid>0.5),
  identical clean-label convention to FAVLONG (`favlongshot_edge.py`): outcome = market's own terminal
  mid, and windows where the spot-proxy disagrees with that label are dropped.
- `fills_kalshi_*` (OUR fills): not separately excluded. Our live bot is a MAKER (box); on the taker
  tape our resting fills appear as the *counterparty's* taker side, not our decisions, so bias is
  negligible — and the result is null/negative, which our own flow could not manufacture.
- **Days used (robust subset after container restart): 19 days, 11 train + 8 test.**
  Train (≤2026-06-30): 06-11,13,15,17,19,21,23,25,27,29,30. Test (>2026-06-30): 07-02,04,06,08,10,12,14,15.
  Windows after clean-label: btc 1550, eth 1557, sol 1584 (pooled across the 3 assets; day-clustered by (asset,day)).

## Tests (train-select / test-once; executable price; hold to settle; net Kalshi fee; day-clustered t)
| # | Test | Train pick (of N configs) | **OOS day-clustered t** | **OOS mean $/ct** | Verdict |
|---|------|---------------------------|-------------------------|-------------------|---------|
| 2 | Net taker-flow imbalance, follow heavy side (horizons 300/450/600/720s × thr) | dt=300, |imb|≥2000 (of 24); train t already **−1.27** | **−1.93** | **−0.037** | NULL (loses) |
| 1 | Large-trade informativeness, follow each large print (sz≥100…2000) | sz≥2000 (of 5); train t=1.73 | **−0.14** | **−0.005** | NULL |
| 3 | Directional consensus, K+ large same-side prints in 120s (of 5) | K≥2, sz≥1000; train t=0.94 | **−0.42** | +0.004 | NULL |
| 4 | Smart-money signature, largest late (t≥600) large print (of 6) | t≥600, sz≥1000; train t=1.96 | **+0.70** | **+0.0001** | NULL |

**Multiple testing:** 40 configurations searched across the 4 families. None is positive OOS. The only
nominally-significant train pick (Test 4, t=1.96) collapses to t=0.70 / \$0.0001 OOS — in-sample noise.
Test 2's "best" train config was already *negative* (t=−1.27): every net-flow-follow config loses even in-sample.

## Why it fails — raw directional diagnostic (Test-2 heavy-flow windows, |imb|≥2000 @300s)
| set | n | followed-flow-side settlement hit | book mid>0.5 hit | flow agrees w/ mid |
|-----|---|-----------------------------------|------------------|--------------------|
| TRAIN | 1262 | **0.365** | 0.743 | 0.313 |
| TEST  |  952 | **0.375** | 0.709 | 0.305 |

Heavy aggressive flow points **against** the settlement ~63% of the time; the book mid alone predicts
settlement at ~71–74%. Aggressive flow agrees with the mid only ~31% of the time — i.e. the heavy takers
are usually lifting the *underdog* (cheap up-bets), the side the market correctly prices low and that
tends to lose. This is the mirror image of FAVLONG: the aggressive underdog-buying flow *is* the losing
side. Following it means paying the spread + fee to chase an already-priced, usually-wrong direction.
Consistent with the operator's own note that a 15m crypto binary tracks spot near-instantly, so informed
information is already in the mid; the residual taker flow is dominated by uninformed longshot chasing.

## Orthogonality vs FAVLONG
Per-window return correlation (Test-2 net-flow strategy vs FAVLONG on 532 overlapping OOS windows):
**corr = +0.199** — low. Moot for deployment since the flow strategy has no positive edge, but it confirms
the two are not the same trade. (FAVLONG fades the mispriced favorite in dislocated books; flow-follow
mostly buys the underdog with the takers — hence a mild positive but far-from-collinear relationship.)

## Bottom line
**NULL / disconfirmed.** No followable directional edge in executed aggressive taker flow on the 15m
crypto binary (btc/eth/sol, 19 days). Large, one-sided, and clustered taker prints do NOT lead the
binary price in a followable way; heavy early flow is if anything a weak *fade* signal, and the book mid
already captures direction better than any flow signature. Do not build a flow-following taker strategy.
The only place aggressive flow carries information is the already-known FAVLONG channel (fade the
dislocated favorite), not "follow the informed size."

---

## FADE (direct test) — take the side OPPOSITE heavy flow at ITS executable price

Follow-up (2026-07-15): follow-flow was NULL because heavy takers lift the losing underdog. Operator's
point: a reliably-wrong signal inverted should be reliably right. So this section tests **FADING as a
standalone strategy** — take the OPPOSITE side of heavy flow at ITS OWN executable price (cross the
spread, pay the Kalshi fee). This is NOT the negative of the follow P&L: fading buys the favorite at its
ask / sells the underdog at its bid, so it still eats a half-spread + fee. Same 19-day split
(11 train ≤06-30 / 8 test), btc/eth/sol, clean realized-settlement labels, day-clustered by (asset,day).

### Task 1 — Fade each flow signal (train-select / test-once)
| Signal (fade) | Train pick (of N) | **OOS pooled t** | **OOS pooled mean $/ct** | Verdict |
|---|---|---|---|---|
| A. Net taker-flow imbalance (dt 300/450/600/720 × 6 thr = 24) | dt=300, |imb|≥4000; train t=1.00 | **−0.50** | **−0.0030** | NULL |
| B. Large-trade, fade every large print (5 thr) | sz≥600; train t=**−2.06** | **−1.77** | **−0.0151** | NULL (loses) |
| C. Directional consensus, fade the consensus (5) | K≥3, sz≥300; train t=−0.01 | +1.01 (n=131) | +0.0189 | NULL (insig., sparse) |

Per-asset OOS for Signal A (best config): btc t=−0.50 (−0.0106/ct, n=557), eth t=+1.35 (+0.0479/ct, n=124),
sol t=−1.15 (−0.0596/ct, n=37). Only eth is positive and it is not significant on tiny n; no pooled edge.
**Multiple-testing count: 34 fade configs across the 3 families; none clears OOS t≥2 (max pooled OOS t=+1.01
on the sparsest, n=131).** Signal B is *actively negative in-sample* (train t=−2.06): fading all 133k large
prints crosses the spread 133k times and the cost buries any edge.

### Task 2 — THE DECISIVE ECONOMICS (anti-flow / favorite side, Signal-A best config dt=300, |imb|≥4000)
| | TRAIN (n=927) | **TEST/OOS (n=718)** |
|---|---|---|
| anti-flow side win-rate | 0.661 | **0.641** |
| avg executable price paid | 0.644 | 0.630 |
| avg mid-implied price | 0.639 | 0.625 |
| spread cost (exec − mid) | +0.005 | +0.005 |
| GROSS edge vs mid (winrate − mid) | +0.0225 | **+0.0156** |
| GROSS edge vs EXEC (winrate − exec, after crossing spread) | +0.0175 | **+0.0102** |
| Kalshi fee | 0.0129 | 0.0133 |
| **NET $/ct (gross_exec − fee)** | **+0.0045** | **−0.0030** |

**This is the crux.** The anti-flow (favorite) side DOES carry a genuine small GROSS directional edge:
it wins ~64% at an executable price of ~0.63, i.e. **+1.0¢/ct gross even after crossing the spread** OOS.
But the Kalshi fee at these ~0.63 prices is **~1.3¢/ct**, which is LARGER than the gross edge, so the trade
**NETS −0.3¢/ct out-of-sample. The fade does NOT clear cost** — the fee, not the direction, kills it.
The signal is real (favorite mildly underpriced) but too small to monetize as an unconditional taker at 300s.

### Task 3 — Does heavy flow give a BETTER favorite entry than unconditional favorite-buy?
OOS favorite-buy, ALL windows: t=−2.07, mean **−0.0181**/ct (n=1773).
OOS favorite-buy, HEAVY-flow windows only: t=+0.09, mean **−0.0242**/ct (n=717).
Conditioning on heavy flow does **not** improve the favorite-buy *mean* (it is if anything slightly worse
per contract; the day-clustered t is less negative only because of higher day-to-day variance on the smaller
sample). Heavy flow does not select systematically cheaper/righter favorites — both variants lose net of fee.

### Task 4 — FADE vs FAVLONG correlation
Per-window return corr(FADE Signal-A, FAVLONG) on 399 overlapping OOS windows = **−0.220** — confirms the
predicted low/mild-negative, mostly-orthogonal relationship (follow was +0.199, fade is its rough mirror in
*direction* but not in P&L). Orthogonality holds, but it is **moot**: a strategy that does not clear cost is
not a stack candidate no matter how orthogonal.

### FADE verdict: **NULL (net of cost).**
Inverting the wrong signal recovers a real but tiny gross directional edge (favorite wins ~1¢/ct more than
its executable price OOS), yet the ~1.3¢/ct Kalshi fee swamps it, leaving **−0.3¢/ct net OOS, pooled t=−0.50**.
It also fails to beat an unconditional favorite-buy. Why FAVLONG clears cost and this does not: FAVLONG only
fires on the rare *dislocated wide-book, near-expiry* windows where the model-vs-price edge exceeds 5%
(gross ≫ fee), whereas fading ALL heavy-flow at 300s harvests a ~1¢ gross edge that cannot beat the fee.
The fade is essentially an unfiltered, fee-dominated version of FAVLONG's favorite-side logic, not a new
orthogonal edge. **Do not deploy a flow-fade taker strategy; the only monetizable form of this direction is
FAVLONG's edge-gated favorite trade.**
