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

## Queue-replay verdict (REAL trade tape, `kalshi_replay.py`, ~1,170 windows/asset)

| net/win (¢), OOS | q_ahead=0 (front) | q=500 | q=2000 |
|---|---|---|---|
| **BTC** ungated / gated | **+2.6 / +4.7** | −16.4 / −7.8 | −32.6 / −18.5 |
| **ETH** ungated / gated | −6.3 / −4.5 | −27.4 / −17.2 | −11.0 / −8.8 |

Three geared conclusions:
1. **Queue position is the whole game**: back-of-queue fills are the adverse ones (strongly negative
   at any realistic joined depth). Kalshi's **0.1¢ sub-cent tick buys the front** — improving one
   micro-tick inside the 1¢ book costs ~1.75¢/win and swings the result by +20¢/win. The deployable
   expression is **micro-tick price-improvement + toxicity gate** (the gate adds value at every
   depth tested, both assets).
2. **BTC-first, not breadth** (reversing the Polymarket lever AND this doc's earlier spread-based
   guess): ETH's thin book (820/min vs BTC's 26.5k) has no benign touch traffic to harvest — every
   fill model shows it negative even at the front. Start BTC-only; re-test alts from the live
   shadow A/B as their volume grows.
3. With no rebate, Insight-10 reverses: stricter gates (`micro_strict`/`micro_asym`) are the
   first-line candidates in the A/B (see strategies.py KALSHI GEARING note).

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
