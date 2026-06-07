# CAPTURE.md — logging schema + power rules for the paper run and the live pilot

The rule: **log enough to reconstruct every counterfactual you'll later want**, because queue
position and cancel-race outcomes cannot be re-derived after the fact. Tags:
`[paper-now]` = the GHA `shadow_compare` collector emits it today · `[live]` = only real with
real orders (`live_trader`) · `[calc]` = computed offline from raw logs.

**Honesty up front:** the **decision-grade** data (queue-conditional toxicity = markout by *real*
queue position) is **live-only** — paper queue depth is a model assumption. Paper meaningfully
gives **fill rate, per-window P&L attribution, and the variant comparison** (all clustering-ready);
the full lifecycle/queue/latency schema below is the contract the **live pilot** must satisfy.

---

## 1. Per resting order (lifecycle)  [live] (`live_trader` -> order_log.jsonl + reprice_log.jsonl)
- order_id, asset_id, side, outcome(Up/Down), post_only, tick_size
- **posted: decision_ts AND exchange_ack_ts** (gap = placement latency)
- price, size; mid, microprice, best_bid/ask, spread at post
- **queue_depth_ahead at your price at post** — THE key field (condition on queue position)
- BTC spot + tau (real seconds, verified clock) at post  ← the tau bug lived exactly here
- terminal: filled / partial / cancelled / expired / heartbeat-cancelled
- if cancelled: decision_ts, cancel_sent_ts, cancel_confirmed_ts, reason(reprice/risk/inv/stale)
- taker_hit_old_price_after_decide? (the cancel-race counterfactual)
  *Status:* `reprice_log` already captures cancel_sent/confirmed, queue_ahead_surrendered,
  taker_hit_old, hit_before_confirm. GAP to add for the pilot: a per-PLACE record
  (decision_ts, ack_ts, queue_depth_ahead, mid/micro/spread/spot/tau at post).

## 2. Per fill  [live ground-truth; paper has modeled analogues]
- trade_id, order_id, match_time, **trader_side(MAKER/TAKER) as truth**, fee_rate_bps charged
- fill price/size, **queue_rank at fill + time_resting_before_fill** (queue residence)
- mid/microprice/spread/BTC spot/tau at fill
- **minted-set vs passive-acquisition flag** — resolves the SELL-skew question (sourcing label)
  *Status:* `live_markout.jsonl` logs price/size/markout/net_delta. GAP for pilot: trader_side
  truth, fee charged, queue_rank, time-resting, mint/passive flag.

## 3. Per fill -> markout  [calc from raw + book]
- mid AND microprice at +1s, +5s, +30s, +60s, and **at resolution**
- the window 0/1 outcome and the **realized hold-to-resolution P&L of that fill** (decision metric)
- BTC spot at those stamps (residual-delta / hedge counterfactual)
  Resolution-horizon is the DECISION metric; short horizons only diagnose *why*.

## 4. Per window (the unit of inference)  [paper-now: shadow_windows_*.jsonl]
Emitted today, per variant, keyed by `ws` (the clustering id):
`net, gross, rebate, fills, fill_vol, trade_vol, fill_rate, mk_buy_vol, mk_sell_vol,
end_delta, max_delta`, plus `resolved_up`.
- P&L attribution by source: rebate is exact; gross = spread-capture + adverse-selection +
  inventory-carry (split needs the markout in #3 -> `[calc]`). `[live]` adds hedge P&L.
- GAP for pilot: time-at-cap, cancel_count, capital locked-vs-freed (velocity), signed
  factor-level delta series (so cross-market residual correlation is measured, not proxied).

## 5. System (continuous)  [paper: shadow.log; live: reprice_log + heartbeat log]
- heartbeat gaps (a gap cancels ALL orders -> resets every queue), WS reconnects, rate-limit
  throttles, placement/cancel latency distributions, **and the clock source itself**
  (timestamp provenance is not optional after the tau bug).

---

## Computations
- **microprice** = bb + (ba-bb)·bid_size/(bid_size+ask_size)  (book-imbalance fair).
- **markout(h)** for our fill at price p: our SELL -> (p - mid_{t+h}); our BUY -> (mid_{t+h} - p).
  Resolution markout: SELL -> (p - settle); BUY -> (settle - p), settle = 1 if Up else 0 (token-relative).
- **queue_rank at fill** = (displayed size ahead when posted) − (volume that traded through that
  level between post and fill); rank≈0 => front-of-queue fill, rank≈post-depth => back (toxic).

## POWER — the lesson that bites hardest
**Your unit of independent observation is the WINDOW, not the fill** (fills in a window share one
BTC path/regime). 1,367 fills across 9 windows ≈ n=9, not 1,367. **Every SE clustered by window**
(check by day too). This is the formal decile-0 / leave-one-window-out instinct.

| estimate | needed | note |
|---|---|---|
| **fill rate** (proportion) | **~30–50 windows** (days) | stabilizes ±2%; highest-value early read — the thing the backtest couldn't give |
| **edge>0** (window-Sharpe) | **~150–250 windows, multi-day** | plan for degraded live Sharpe (~0.3, not backtest 0.7); window P&L is heavy-tailed -> ×2–3 the iid n |
| **queue-conditional toxicity** (markout × queue rank) | **hundreds–~1000 indep. windows, ~3–6 weeks** | the binding, decision-grade result; per-fill SNR ~0.05–0.1, fragmented into queue buckets |

**Two gates between window-count and real power:**
1. **Calendar spread, not just count** — 300 windows in one day = one vol regime ≈ correlated draws.
   Need days/weeks across diurnal + multi-day regimes (≥~2–3 weeks wall-clock) for the
   queue-conditional and degradation estimates, even though raw count accrues in days across 4 markets.
2. **Pre-register n and the rule; peek-safely** — fix the target window count and decision rule in
   advance (garden-of-forking-paths is the same trap we avoided offline). Template:
   *"GO if resolution-horizon per-fill markout, clustered by window, is ≥ 0 after costs with a 95%
   CI excluding −X, across ≥N windows spanning ≥3 weeks"*; use alpha-spending for interim looks.

**Bottom line:** fill rate in days; edge-sign in ~1–2 weeks; queue-conditional toxicity (the
decision) in ~3–6 weeks of multi-market, multi-regime running. Method > number: cluster by window,
tail-adjust the Sharpe SE, spread across regimes, pre-commit. Get those right and a few hundred
windows is real power; get them wrong and 10,000 fills in 3 days is still n≈3.
