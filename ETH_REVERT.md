# ETH 15-min Intra-Window Reversion / Overreaction Maker — VERDICT: NO EDGE

**Hypothesis tested:** When the Kalshi ETH 15-min binary YES mid makes a large move between
minute k-1 and k (driven by a spot jump / taker-flow burst), does the price *overreact* and
*revert* before settle? If so, a fee-advantaged MAKER resting a passive quote on the side the
crowd is dumping would earn reversion + spread.

**Answer: NO.** The ETH binary mid is a near-martingale that *tracks spot faithfully*; intra-window
moves are **informational (they stick), not overreaction (they don't revert)**. Any positive EV in
a naive maker backtest is **100% an artifact of the fill model** (assuming we capture the half-spread
for free). Once fills are modeled with realistic adverse selection — a resting fade only gets lifted
when price keeps running against it — EV collapses to **-9 to -10c/fill (t=-49)**. Do not deploy.

Data: 2402 ETH 15-min windows, per-minute mid/bid/ask/vol/spot path + full tape.
IS = first 60% (1441 windows), OOS = last 40% (961). Settlement: YES pays `res_up` (mid→1/0).
Code: `eth_revert_study.py` (Tasks 1-2), `eth_revert_maker.py` (Tasks 3-5).

---

## Task 1 — Reversion / Autocorrelation

**Lag-1 autocorrelation of per-minute mid changes (minutes 1..12, n=28,824): −0.0010.**
Essentially zero. The price *path* is a near-martingale — no mechanical mean-reversion and no
momentum. There is no autocorrelation structure to trade.

**Unconditional subsequent path move after a large move** `post = mid[k+h] − mid[k]`:

| horizon | n(+dk≥5c) | E[post \| +dk] | n(−dk≤−5c) | E[post \| −dk] |
|---|---|---|---|---|
| h=1 | 6383 | **−0.0023** | 6338 | −0.0007 |
| h=2 | 5913 | −0.0066 | 5865 | +0.0000 |
| h=3 | 5360 | −0.0056 | 5330 | −0.0018 |

After a +5c up-move the price drifts back only ~0.2–0.7c over the next 1–3 minutes; after a down-move
it does ~nothing. **E[next-min mid move | up-trigger≥5c] = −0.0008, t=−0.27 → statistically zero.**
The whisper of reversion after up-moves is sub-cent and economically irrelevant vs a 1.6c spread.

**Move vs return-to-settle** is dominated by the binary's pull toward 0/1 (not a reversion signal);
`corr(dk, ret-to-settle) = −0.002`.

## Task 2 — Overreaction vs Information split

**Spot follow-through split (DIAGNOSTIC; uses future spot, not tradeable):**

| group | n | E[mid move k→k+2] | t |
|---|---|---|---|
| +dk & spot continues | 2731 | **+0.130** | +54.5 |
| +dk & spot reverts | 3182 | **−0.124** | −44.9 |
| −dk & spot continues | 2821 | −0.126 | −59.3 |
| −dk & spot reverts | 3044 | +0.117 | +44.6 |

The binary mid moves with spot almost 1:1: it sticks iff spot sticks, reverts iff spot reverts.
This is the signature of an **information-driven, efficient** quote, NOT overreaction. The binary
isn't overshooting a justified probability and snapping back — it is faithfully repricing spot. You
cannot fade it, because at the moment of the move you don't yet know whether spot will revert
(and the binary already reflects the spot move correctly).

**Flow-toxicity split (uses only data at k — the one real, tradeable conditional signal):**

| group | n | E[mid move k→k+2] | t |
|---|---|---|---|
| +dk high one-sided flow | 1707 | −0.0136 | **−2.77** |
| +dk low/balanced flow | 4206 | −0.0037 | −1.31 |
| −dk high one-sided flow | 1617 | −0.0025 | −0.55 |
| −dk low/balanced flow | 4248 | +0.0010 | +0.36 |

The *only* statistically real, causally-valid reversion is: after a sharp **up**-move on heavy
one-sided buying, the mid drifts back ~1.4c (t=−2.77). The down-move side shows nothing. A 1.4c
expected reversion is **below the 1.6c spread**, asymmetric (one side only), and — critically — it
does not survive a realistic fill model (Task 3). There is no symmetric, harvestable overreaction.

## Task 3 — Maker fade-the-move strategy (sweep) + fill-model caveat

Strategy: on a trigger move at minute k, rest a passive quote on the fade side (up-move → rest a
SELL of YES at the offer; down-move → rest a BUY at the bid), maker fee ≈ 0.

**(A) Naive fill model — fill at the touch, unconditional (THE TRAP):**

| trigger | flow cond | exit | OOS n | OOS EV/fill | OOS Sh | OOS t | OOS win% |
|---|---|---|---|---|---|---|---|
| 0.03 | none | touch | 6875 | +0.96c | +0.068 | +5.63 | 46.9% |
| 0.05 | none | touch | 5409 | +0.87c | +0.060 | +4.38 | 46.9% |
| 0.08 | none | touch | 3940 | +1.07c | +0.071 | +4.47 | 47.6% |
| 0.10 | none | settle | 3163 | +1.84c | +0.044 | +2.45 | 33.0% |
| 0.05 | p85 | settle | 1140 | +1.24c | +0.031 | +1.05 | 29.6% |

Looks positive (EV +0.7–1.8c, OOS t up to 5.6, Sharpe ~0.07). **But this is entirely the assumed
half-spread capture (mean spread 1.6c → half-spread ~0.8c ≈ the EV) plus the sub-cent reversion,
under the false assumption that we fill for free.** Sharpe is tiny (~0.05–0.07) even granting that.
Flow conditioning (p70/p85) *raises IS EV* but the lift is IS-only and **vanishes/reverses OOS**
(p85 OOS t≈1.0, several configs negative) — classic in-sample overfit of the toxicity threshold.

**(B) Adverse-selection-aware fill model — a resting fade only fills when a taker crosses, i.e.
price continued toward our quote (we require next-min continuation ≥1c in the move direction):**

| trigger | flow cond | exit | OOS n | OOS EV/fill | OOS Sh | OOS t |
|---|---|---|---|---|---|---|
| 0.05 | none | settle | 2785 | **−9.79c** | −0.268 | −14.15 |
| 0.05 | none | touch | 2785 | **−9.06c** | −0.934 | −49.28 |
| 0.08 | none | settle | 2026 | −10.24c | −0.276 | −12.42 |
| 0.08 | p85 | touch | 500 | −10.23c | −0.855 | −19.12 |

EV flips to **−9 to −10c/fill** with t up to −49. Reason (confirmed): after an up-trigger, the next
minute continues up 55% of the time and reverts 45% — and the continuations are larger. A passive
fade offer is lifted *preferentially on the 55% that run against you* (information), not the 45% that
revert. **The naive model's "edge" was the fill model doing 100% of the work.**

## Task 4 — Exit (hold-to-settle vs flatten-at-touch)

- **Naive model:** `touch` gives much higher Sharpe (+0.07 vs +0.03) and win% (~47% vs ~33%) than
  `settle`, because flattening books the half-spread immediately and avoids binary variance. `settle`
  has occasionally higher mean EV/fill but ~0 Sharpe (huge 0/1 settlement variance).
- **Adverse model:** both exits are deeply negative; `touch` is worse on Sharpe (−0.93) because it
  realizes the adverse continuation immediately. Neither exit rescues the strategy.
- Exit choice is a second-order tweak; it cannot turn a fill-model artifact into real edge.

## Task 5 — VERDICT

**There is NO positive-EV intra-window reversion maker on the ETH 15-min binary.**

- **Exact rule that "works" in backtest:** fade any ≥3–5c minute-to-minute mid move, rest passive,
  flatten at next-minute touch → naive EV +0.9c/fill, OOS t≈5.6, Sharpe 0.068, ~6900 fills/IS-half.
- **Why it is rejected:** that EV is the assumed half-spread (spread 1.6c) under a free-fill
  assumption. The price does not revert (E[next-min move]=−0.0008, t=−0.27; lag-1 AC=−0.001). Moves
  are informational — the binary tracks spot 1:1. Under an honest fill model where a resting fade
  only gets lifted when price keeps running against it, EV = **−9 to −10c/fill, t=−49, Sharpe −0.27
  to −0.93**, OOS. The lone real signal (up-move + toxic flow → −1.4c, t=−2.77) is below spread,
  one-sided, and does not survive fills.

| metric | naive (rejected) | adverse-aware (real) |
|---|---|---|
| EV/fill OOS | +0.9c | −9.5c |
| Sharpe OOS | +0.07 | −0.27 (settle) / −0.93 (touch) |
| t vs zero OOS | +5.6 | −49 |
| #fills (IS half) | ~6,900 | ~2,800 |
| IS/OOS stability | EV decays IS→OOS; flow-cond lift is IS-only | consistently negative |

**Fill-model caveat (the heavy lifter):** the verdict hinges entirely on the fill model. The naive
model is optimistic on (i) queue position (front-of-queue, full half-spread) and (ii) fill
selection (ignores that passive fades are adversely selected). The adverse-aware model is a
conservative lower bound (assumes every fill is followed by ≥1c adverse continuation). Truth lies
between, but the key structural fact is independent of the model: **the binary mid does not revert**
(martingale, tracks spot), so there is no reversion alpha to fund either the spread or the adverse
selection. Consistent with the established structural context (ETH mid efficient, AUC 0.96).

**Recommendation:** Do not deploy. This screens NEGATIVE; the directional/overreaction angle on ETH
15-min is dead. Backtests SCREEN only — but here even the screen fails, so no forward validation is
warranted. If ever revisited, the binding question is empirical maker queue/fill behavior (does our
resting fade fill on reverting ticks or running ticks?), which requires live passive-quote telemetry
— not more historical study.
