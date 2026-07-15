# Candidate: Cross-Strike No-Arbitrage in Kalshi Multi-Strike Ladders

**Status: NULL (not a real executable edge).** Orthogonal to FAVLONG (single-contract near-expiry
microstructure); this probes *cross-strike* coherence of "price > K" binary ladders.
Date: 2026-07-15. Read-only, offline archive + gentle public API. No orders, no commits.

## Thesis
A ladder of `greater`-type binaries on the same event/expiry must satisfy:
- **Monotonicity:** `P(>K)` non-increasing in `K`. Executable form: `yes_ask(K_lo) >= yes_bid(K_hi)`
  for `K_lo < K_hi`. A crossable violation `yes_bid(hi) > yes_ask(lo)` is a lock.
- **Butterfly / density >= 0:** for cumulative "greater-than" binaries this reduces to the same
  monotonicity condition (implied density `f(K) ∝ P(>K_-) − P(>K_+) >= 0`). The convex "second
  difference" is the same lock family, so monotonicity is the binding no-arb test.

The lock, if executable: buy `YES(lo)@ask` + buy `NO(hi)@(1−bid_hi)`. Cost `= a_lo + (1 − b_hi) = 1 − gap`
where `gap = b_hi − a_lo`. Payoff is **\$1 outside (lo,hi] and \$2 inside** → guaranteed `>= \$1`.
Gross locked profit `= gap`, **outcome-independent** (so realized-vs-settlement P&L equals the gap
minus fees whenever the fill is real; settlement adds nothing to a properly locked position).

## Data & Method
- **Archive** (`origin/gha-data`, `gha_data/**/ladders_*.jsonl.gz`): 1,065 files, **2026-06-12 → 2026-07-15**.
  These are output of `kalshi_ladder_collect.py` (worktree `agent-aa14daebc1292e1db`), which polls
  `GET /markets?series_ticker=...&status=open` every ~45s for series `KXBTCD, KXETHD, KXINXU,
  KXNASDAQ100U`, computes top-of-book monotonicity on adjacent + up-to-3-apart strike pairs, and
  logs a line per event only when a crossable or near (≤1c) violation exists, plus a heartbeat per cycle.
  Reconstructed all lines: **59,640 poll cycles**, **21,687 event-ladder violation summaries**.
- **Live API** (`https://api.elections.kalshi.com/trade-api/v2`, no keys — the base
  `settle_recorder.py` uses): re-enumerated current `KXBTCD`/`KXETHD` events, rebuilt the full
  bid/ask/size ladder (fields `yes_bid_dollars`, `yes_ask_dollars`, `yes_*_size_fp`), and independently
  ran monotonicity (executable + mid) and butterfly checks. Settlement pulled via
  `GET /markets?event_ticker=...` `result` field.
- **Kalshi fee** (2-leg lock): `fee = ceil(0.07·P·(1−P)·100)` cents/contract, applied to `YES(lo)@a_lo`
  and `NO(hi)@(1−b_hi)`. Range ~1c/leg (extreme P) to 2c/leg (P≈0.5).

## Violation statistics (archive)
- **Crossable-violation entries:** 3,969 with gap detail (5,147 counted), across **367 distinct events**,
  **2,404 distinct (event, strike-pair) instances**. Near-violations (≤1c of crossing): 34,953 entries —
  these are just markets resting exactly at touch (0-width), normal tight-book behaviour, not arb.
- **Gap-size distribution is starkly bimodal:**

  | gap (cents) | entries | share |
  |---|---|---|
  | 1–2 | 1,683 | 42% |
  | 2–10 | 112 | 3% |
  | 10–50 | 137 | 3% |
  | **50–99** | **2,037** | **51%** |

  Median gap = 70c, max = 99c. **A 50–99c "locked arb" is economically impossible** in a live venue —
  it would be lifted instantly. These are **empty-book artifacts**: a 99c gap needs `a_lo ≈ 0`
  (a *missing* ask reported as \$0.00, not an executable \$0 offer) against a deep-ITM `b_hi ≈ 0.99`.
  The collector's own header note confirms the taker race here is "dead (our scan: all phantom)."
- Persistence: median 1 poll; the durable ones are the phantom empty-book states, not real depth.

## Exploitability
- **Small gaps (≤2c, 42% of entries):** killed by fees. Net P&L per contract:
  1c gap @ P≈0.5 → **−3.0c**; 1c @ extreme P → **−1.0c**; 2c @ P≈0.5 → **−2.0c**. All negative.
  A 2-leg lock costs 2–4c in fees, so no gap ≤4c can clear, and *zero* observed gaps sit in 3–4c.
- **Large gaps (≥50c, 51%):** would clear fees easily (net +48–98c) **but are non-executable** —
  `a_lo ≈ 0` means there is no ask to lift; the leg cannot be filled. Phantom.
- **Live cross-check (the decisive test):** a real-time snapshot of 5 events / 360+ quoted strikes
  found **0 crossable violations of any size**. Near-money books were clean, monotone, 1–2c spreads
  with genuine depth (e.g. BTC 64.8k→66.1k rungs stepping 0.97→0.02 in yes-bid). Mid-price
  monotonicity showed **4 tiny inversions**, but **all 4 were sub-spread** (executable-price check = 0) —
  i.e. violations live *inside* the bid/ask spread and vanish at prices you can actually trade.
- **Settlement:** results are perfectly monotone (yes for low K → no for high K, single crossover),
  confirming no settlement-side dislocation. Since the lock is outcome-independent, realized P&L would
  equal `gap − fees` on any real fill — but the count of executable fills is **0**.

## Realized locked-arb P&L
**\$0.00.** No archive or live violation is simultaneously (a) executable (real two-sided depth) and
(b) large enough to survive 2-leg fees. Small gaps net negative after fees; large gaps are phantom
empty-book states with no liftable ask. Nothing to book.

## Verdict: **NULL**
There is **no real, executable post-fee/post-spread cross-strike arbitrage** in these Kalshi ladders.
Apparent violations split cleanly into (1) sub-fee touch-crossings (≤2c, ~42%, net −1 to −3c after
fees) and (2) phantom empty-book artifacts (≥50c, ~51%, no executable ask). A live full-ladder
reconstruction independently found zero crossable violations across 360+ strikes; the only mid-price
inversions were entirely within the spread. This matches the prior collector's "all phantom" finding
and the expected honest NULL: monotonicity dislocations exist at mid but not at prices you can trade.
The maker variant (resting orders that only fill at violating prices) is not evidenced here either —
the gaps that are large enough to matter never correspond to real two-sided liquidity.

### Caveats
- Archive stores only the gap, not raw per-leg prices/sizes, so the empty-book mechanism for large
  gaps is inferred structurally (a `gap≈0.99` forces `a_lo≈0`) and corroborated by the live snapshot,
  not measured leg-by-leg historically.
- Live check is a single point-in-time snapshot (gentle API use); it is corroborative, not a
  full 33-day executable-price replay (the archive lacks the raw quotes needed for that).
- Series `KXINXU`/`KXNASDAQ100U` (most archive violations) are index ladders; conclusion (bimodal
  phantom/sub-fee) is uniform across all four series.
