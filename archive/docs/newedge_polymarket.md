# FAVLONG mechanism on Polymarket btc up/down — research note

Node: NEWEDGE-POLYMARKET (2026-07-15). Offline research, propose-only. No live action.
Data: `origin/gha-data:gha_data/<day>/pmkt_btc_updown_*.jsonl.gz` (35 days, 2026-06-11..07-15).
Verdict up front: **NULL — in fact negative.** The near-expiry repricing-lag edge does NOT
replicate on Polymarket btc up/down. Cross-venue arb vs Kalshi btc15m is **not clean** (tenor
and strike definitions don't align).

---

## 1. Schema & tenor

Each JSONL row (one order-book snapshot):
```
{"t":1781220426.65, "end":1781220600.0, "venue":"polymarket", "asset":"btc",
 "slug":"btc-updown-5m-1781220300",
 "up_bid":0.74,"up_ask":0.75,"up_bsz":44760.2,"up_asz":37178.7,
 "down_bid":0.25,"down_ask":0.26}
```
- `t` = snapshot unix time; `end` = settlement unix time; `slug` timestamp = window START.
- **Tenor: exclusively 5-minute** (`end - start = 300s`; confirmed across all sampled days, 0
  non-5m slugs). ~288 windows/day, ~34 GHA runs/day, ~285 usable windows/day after filtering.
- **Event type: "up/down from open"** — `up` pays $1 if the underlying is higher at `end` than at
  window open (strike = spot at window start). Verified: at window start `up` mid ≈ 0.47–0.57 (a
  coin-flip), not centered on a fixed dollar strike. This is a DIFFERENT contract from Kalshi
  15m "above a fixed strike."
- **No spot in the file, no explicit settlement field.** Both must be reconstructed.
- Book is quoted on `up` and `down` legs; `up_bid/up_ask` are the executable taker prices
  (`up_bsz/up_asz` = size on each side, in shares/$).

**Spot reconstruction:** Kalshi `ticks_kalshi_btc15m` rows carry `ws` (window-start unix) and per-tick
`spot` (the Kalshi index), so `abs_time = ws + t_sec`. Concatenating all runs gives a BTC spot
series at ~1.2s density, ~73% second-level coverage/day — time-aligned with the Polymarket runs
(same GHA jobs). This is the causal fair-value driver (same math as `favlongshot_edge`).

**Settlement recoverability — the crux.** Two independent labels:
- `label(pmkt)` = terminal Polymarket price (`mid_close > 0.5`). This is what actually PAYS OUT —
  the honest, market-native settlement label, exactly analogous to FAVLONG's clean label.
- `label(spot)` = Kalshi `spot_end > strike`. A proxy using our (foreign) spot feed.
- **These disagree 12.1% of the time** and Polymarket's true resolution source is its own feed,
  not Kalshi's. Scoring on `label(spot)` is a markout illusion because the fair value and the
  outcome then share the same spot series.

---

## 2. FAVLONG mechanism test on Polymarket

Methodology (identical taker mechanics to `favlong_model_v2`, only venue/label changed):
- strike = spot at window start; near-expiry decision tick = last snapshot with `end - t >= tau_dec`.
- causal spot & vol up to the decision tick only (no look-ahead); `fair = NORM((spot-strike)/(spot·σ·√τ))`.
- take the side the EXECUTABLE price underprices by `> edge`: buy `up` at `up_ask`, sell `up` at
  `up_bid` (cross the spread). **Polymarket CLOB fee = 0** (gasless off-chain matching, on-chain
  settlement subsidized by the operator's relayer) → structurally cheaper than Kalshi's
  `0.07·p·(1-p)`. Fee=0 is a GENEROUS assumption and the edge is still negative.
- P&L on REALIZED SETTLEMENT; per-day clustered t; train = days ≤2026-06-30 (20d), test >2026-06-30 (15d).

### 2a. The label flip (why rigor matters)
All-trades, `tau_dec=60`, `edge=-9` (take everything), **train**:

| settlement label | n | winrate | mean $/ct | day-clustered t |
|---|---|---|---|---|
| `label(spot)`  (proxy, shares spot feed) | 4516 | 0.428 | **+0.0428** | **+5.69** |
| `label(pmkt)`  (real payout)             | 4595 | 0.368 | **−0.0180** | **−3.43** |

The spot-label "edge" (t=+5.69) is a **data-mismatch artifact** and REVERSES to a loss under the
real payout label. This is precisely the markout-illusion failure mode the program died on; the
honest label governs.

### 2b. Train-select / test-confirm grid (honest `label(pmkt)`, fee=0)
Grid = {tau_dec ∈ 30,45,60,90} × {edge ∈ 0.03,0.05,0.08} × {segment: all / wide≥2c / tight=1c}.
**Multiple-testing count = 36 train variants scored.**

- **Not one of the 36 variants has a positive mean.** Train t ranges −5.83 … +0.23; every mean is
  negative (−0.005 to −0.051 $/ct).
- Best train variant (`wide≥2c/tau90/e0.08`, train_t=+0.23 but mean −0.025) → **OOS t=−2.24,
  mean=−0.061 $/ct**, 5/15 positive days. Selection picked noise; it loses OOS.
- FAVLONG-faithful config (`wide≥2c/tau45/e0.05`): train t=−1.31 / test t=−0.44, both negative mean.
- Full-sample (`all/tau60/e0.03`, n=4884): **t=−4.22, mean=−0.027 $/ct**, 10/35 positive days.

**Why it fails structurally:** Polymarket btc-updown books are **tight and deep** — median spread
= exactly 1c (>95% of near-expiry snapshots at 0.01) with size in the tens of thousands. FAVLONG's
edge lived specifically in WIDE/dislocated books (spread >1c: +3.6c/ct) and was ~zero in
tight-and-deep books. Polymarket is uniformly the regime where FAVLONG has no edge. Crossing a 1c
spread into an efficient book with a foreign, noisier spot-derived fair value is a systematic loss.

**Verdict Task 2: NULL / negative. The near-expiry repricing-lag edge does not exist on Polymarket
btc up/down.** Polymarket is NOT a viable new market for the FAVLONG mechanism.

---

## 3. Cross-venue (Kalshi btc15m vs Polymarket btc-updown)

**Not a clean arb — the events don't match.**
- **Tenor:** Kalshi 15m vs Polymarket 5m.
- **Strike definition:** Kalshi = "spot ABOVE a FIXED dollar strike at expiry"; Polymarket = "spot
  UP vs its own window-open". Different payoff conditions on the same underlying.
- Even where boundaries coincide (every :00/:15/:30/:45 the 15m Kalshi window shares a start with a
  5m Polymarket window), the two contracts resolve on **different events** — a 15m-above-fixed-strike
  and a 5m-up-from-open are not offsetting legs, so you cannot buy the cheap venue and sell the rich
  venue as a hedged pair. Any price "divergence" is expected (different distributions), not arbitrage.
- **Lead/lag:** both venues are priced off the same BTC spot, and Kalshi's own index IS the spot
  feed used here — there is no clean informational lead of one binary venue over the other to harvest;
  the mover is spot itself, available to both.

**Verdict Task 3: cross-venue arb is not clean and no exploitable divergence/lead was pursued —
the tenors and strikes don't align. Stated explicitly rather than manufactured.**

---

## 4. Bottom line
Polymarket btc up/down is a **NULL (negative) for the FAVLONG mechanism** and offers **no clean
cross-venue edge** vs Kalshi btc15m. The one apparently-positive result (t=+5.69) is a settlement-
label illusion that reverses under real payouts (t=−3.43); under the honest label the effect is
negative across the full 36-variant grid, train and OOS, even with zero fees assumed. Root cause:
Polymarket's books are tight/deep (1c spreads, huge size) — the efficient regime where FAVLONG was
already ~zero on Kalshi — and its resolution feed differs from our reconstructed spot. Recommend:
do NOT pursue Polymarket for this mechanism; keep FAVLONG scoped to Kalshi wide/dislocated books.
