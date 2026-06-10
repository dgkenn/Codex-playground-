# Kalshi: the viable strategy, the evidence, and the path

**Why Kalshi:** CFTC-regulated, legal for US persons — it removes the jurisdiction problem entirely.
And it runs the **same product**: `KX{BTC,ETH,SOL,XRP}15M` — "price up in next 15 mins?", 96
windows/day/asset, settling on **CF Benchmarks** (Coinbase-family index, so our Coinbase spot feed
is nearly the settlement source itself). Public no-auth market data: full order book, trade tape,
per-minute candles with bid/ask OHLC + volume, and settled-market history (`fetch_kalshi.py`).

## The verdict: the SAME strategy transfers — toxicity-gated passive market making —
## with the edge coming from SPREAD CAPTURE instead of the rebate.

**What the deep data says (1,185 windows/asset, May 11 – Jun 10, `kalshi_econ.py`):**

| | BTC 15m | ETH 15m |
|---|---|---|
| spread (mean / % minutes ≤1¢) | 0.83¢ / 91% | 1.83¢ / 48% |
| volume/min (median) | 26,500 contracts | 820 contracts |
| maker capture UPPER bound (gated, OOS) | +3.9¢/win | +7.3¢/win |
| maker capture LOWER bound (gated, OOS) | −0.51¢/win | −0.53¢/win |

- The **upper bound** (both sides fill every rested minute — plausible-ish in BTC's 26k/min book)
  is strongly positive; the **lower bound** (you fill ONLY when the touch moves into you — the
  zero-queue-traffic worst case) is mildly negative. **Real capture lives between**, and where it
  lands is decided by queue traffic share — exactly what candles cannot see and a live shadow
  collector can. This is the same epistemic position Polymarket was in before its paper phase.
- **The gate works on Kalshi too**: the honest past-spot gate (8bps/3min) cuts the adverse-only
  loss by ~30% on both assets while keeping the capture bound strongly positive — the
  adverse-selection mechanism (stale book vs spot) is venue-independent, as expected.
- **No rebate** (fee_type=quadratic ≈ 0.07·C·P·(1−P) on takers; maker fee assumed 0 — *verify the
  current published fee schedule before arming*). So Kalshi viability = our GROSS line, which the
  latest Polymarket data already shows positive for the gated family (micro_ufat gross +3.8/win,
  t≈7) — the mechanism that must pay here is already paying there.
- **No directional edge on Kalshi either** (`directional_deep.py` on the same parquet: 0 of 36
  tests; favorite-longshot/momentum/serial all null) — consistent with Polymarket and the
  12k-window deep study. The maker seat is the edge here too.
- **Asset ranking flips vs Polymarket**: ETH/SOL/XRP's wider spreads (1.3–4¢) mean ~2× capture per
  fill at lower queue competition; BTC has the traffic. Run breadth across all four, judge by the
  same Calmar discipline.

## The decision instrument is BUILT and VERIFIED: `kalshi_collect.py`

A live shadow collector that REUSES the existing engine — `shadow_compare.Variant` (queue model,
all 25 registered gates, fill logging) and the strategies registry — against Kalshi's public REST
(order book + trades ~1Hz, settlement from market results). YES/NO map to up/down tokens (one
physical book, two views; one trade feeds both). Output is the **same fills/windows schema**
(venue-tagged `kalshi`, net == gross), so `gate_lab` / `leaderboard` / `strategy_opt` /
`metrics` run on Kalshi data unchanged — set the rebate to 0 in analysis.

## The path (mirrors the Polymarket playbook)

1. **Paper phase (now):** run `kalshi_collect.py` continuously (a GH-Actions workflow like
   `collect.yml` works as-is — public API, no keys) for 1–2 weeks → the leaderboard answers
   "is gated spread capture net-positive, and which gate/asset?" with real queue traffic.
2. **If positive:** the live bot needs a Kalshi execution adapter (REST/WS with API key — simpler
   than Polymarket: no EIP-712, no proxy wallets, no on-chain; same OMS architecture, dead-man =
   cancel-all via API). Colo target: Kalshi matches in AWS **us-east**; same latency playbook.
3. **Same discipline:** preflight → tiny pilot → reconcile (fill rate, maker integrity, live-vs-
   shadow markout) → scale by breadth first. Fee schedule verification is the A1-equivalent
   unknown: confirm maker fee = 0 on CRYPTO15M *from the published schedule + a real fill*.

Tools: `fetch_kalshi.py` (deep history) · `kalshi_econ.py` (bounds) · `kalshi_collect.py` (live
shadow) · `directional_deep.py hist_kalshi_*.parquet` (directional null).
