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
- ~~Asset ranking: wider alt spreads look attractive~~ — **OVERTURNED by the trade-tape replay
  below: BTC-first** (thin alt books have no benign traffic; see the queue-replay verdict).

## ✅ RESOLVED LIVE: maker fee = $0.00 on KXBTC15M (the load-bearing unknown)

Kalshi's official formula (kalshi.com/fee-schedule, help center): **taker = ceil(0.07·p·(1−p)) /
contract; maker ≈ 0.0175·p·(1−p)** (~0.44¢ at p=0.5) **on markets that charge maker fees** — and
"in some cases markets have maker fees." The API confirms KXBTC15M is `fee_type=quadratic,
fee_multiplier=1` (standard rate). Whether crypto-15m is *in the maker-fee list* is the per-series
detail in the (rate-limited) fee PDF — and is settled definitively by the fee on one real maker fill.

**It is decisive (`kalshi_replay.py`, BTC, front-of-queue gated, OOS):**

| scenario | net/win | OOS t |
|---|---|---|
| maker fee = 0 (fee-exempt) | **+4.7¢** | 1.6 |
| maker fee = 0.0175·p(1−p) (standard) | **+1.8¢** | 0.6 |

**CONFIRMED by 16 real maker fills (2026-06-10, $10 acct): `fee_cost = 0.000000` on every fill,
including p=0.35 and p=0.94 where a standard maker fee would be clearly non-zero.** Crypto-15m is NOT
in Kalshi's maker-fee list → the operative economics are the **fee-exempt row above (+4.7¢/win gated
front-of-queue)**, not the degraded one. The Kalshi A1 is closed favorably; the gate still matters
(it lifts ungated +2.6¢ → gated +4.7¢ OOS).

**Live end-to-end validation (same session):** auth → startup reconciliation → live placement →
**16/16 MAKER fills, 0 taker** (post-only + sub-cent improve held) → correct settlement (window
booked, account returned FLAT) → dead-man cancel-all at exit. The full money path executed cleanly.
⚠ **Pre-scale risk found:** under rapid fill→re-quote the gate can lean the book DIRECTIONAL (it
accumulated ~9 one-sided contracts in one window; the per-placement notional cap didn't tightly bind
the resulting inventory). At 1-contract scale this was ~$2 and it happened to win (+$5 of LUCK, NOT
edge) — but a tighter inventory cap / balanced-quoting fix is required before sizing up. The shadow
A/B + a hard inventory clamp address it.

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

## SMART BET SIZING — the strategy that has an edge WITH OR WITHOUT fees (`kalshi_sizing.py`)

The Kalshi fee (where charged) is `mult·p·(1−p)` — quadratic, maximal at p=0.5, ~0 at the tails — so
the fee itself dictates that sizing must not be flat. Backtested on the **real trade tape** (~20k BTC
+ ~19k ETH fills, front-of-queue, IS/OOS, hold-to-settlement):

**Per-fill rule:  `size ∝ max(0, m̂(features) − fee(p))`**, fractional-Kelly scaled, inventory/notional
capped. `m̂` is a markout model on tape features (spread dominates, +0.38; the per-fill markout is
barely forecastable, OOS R²≈0 — the edge is a *selection* effect: bet wide-spread benign fee-cheap
fills, refuse the rest).

| | flat | gate | level | **edge_kelly** |
|---|---|---|---|---|
| **BTC fee=0** net/win · Sharpe · OOS Calmar | +1.75¢ · 2.1 · 0.5 | −0.4¢ | +1.75¢ · 2.2 · 0.8 | **+1.58¢ · 2.7 · 0.9** |
| **BTC fee=0.0175·p(1−p)** | −3.4¢ | −5.1¢ | −2.8¢ | **+0.96¢ · 2.6 · 1.5** |
| **ETH fee=0** | −12.3¢ | −9.5¢ | −10.5¢ | **+0.42¢ · 1.7 · 4.2** |
| **ETH fee=0.0175·p(1−p)** | −16.9¢ | −13.6¢ | −14.7¢ | **+0.29¢ · 1.4 · 2.8** |

**Verdict (the goal):** `edge_kelly` (fee-aware Kelly sizing) is the **only rule positive across both
assets AND both fee regimes**. Flat/gate/level sizing is positive *only* on BTC fee-free and loses to
any fee or to ETH's thin/toxic book. The mechanism is exactly the fee-conditional lever: size shrinks
where the quadratic fee bites (mid prices) and on toxic fills, and concentrates on the few benign,
wide-spread, fee-cheap fills where net edge `m̂ − fee` is genuinely positive. It is **~14× more
capital-efficient** than flat (1.1 vs 17.5 units/win on BTC) — critical under the inventory clamp.

**Honest limits:** the edge is THIN (~1.6¢/win BTC fee-free, sub-cent under fees) and selective
(low volume → needs many windows, the months-of-data plan); it assumes front-of-queue execution
(the sub-cent improve) and held-to-settlement. **Deploy as the live A/B size-mode** alongside the
gate; the shadow collector certifies it prospectively before sizing up.

## Position EXITS (stop-losses): possible, explored, and REJECTED by the data

Mechanically exiting is easy on Kalshi (sell the position, or buy the opposite side — they net at
the clearinghouse). Cost: a maker exit is free but may not fill; a taker exit pays half-spread +
0.07·p(1−p) ≈ 2.25¢ at p=0.5. Tested on **20,318 real tape fills** (exit when the mark is T¢
underwater vs hold to settlement):

| policy | net/fill | tail (p5) |
|---|---|---|
| HOLD to settlement | **+0.10¢** | −67¢ |
| stop-loss 3¢ | −0.99¢ | −32¢ |
| stop-loss 8¢ | −0.65¢ | −36¢ |
| stop-loss 20¢ | −0.18¢ | −45¢ |

Every stop level destroys the edge: a 15-min binary that is a few cents underwater still recovers
often enough that stops systematically sell the bottom AND pay the exit tax. Stops do thin the tail
(−67→−32¢ p5) but at ~10× the edge in expectation. **Tail risk is instead bounded by SIZE** (1-lot
clips, notional cap, sticky session kill) — structural, free. Re-confirms the Polymarket
`hedge_backtest` refutation from the exit side. The profitable "exit" remains the preventive one:
the gate refusing the toxic fill, and the cooldown not re-quoting into trends.

## FEE-CONDITIONAL STRATEGY TABLE (the "if the markets have fees" answer, tuned + deployable)

The fee landscape, resolved: all four CRYPTO15M series share identical fee config
(`fee_type=quadratic, fee_multiplier=1`) and one contract certification; **BTC AND ETH maker fee =
$0.00 proven on real fills** (ETH at p=0.42/0.45/0.59 — mid prices where a charged maker fee would be
clearly non-zero); SOL/XRP share identical config → the whole CRYPTO15M family is fee-exempt.
Index series (KXINX etc.) differ (`mult=0.5`) and some series DO charge maker fees per Kalshi's
schedule. The strategy is tuned PER REGIME and deployable via `kalshi_trader --fee-mult`:

| regime | where | tuned config | OOS edge (real-tape backtest) |
|---|---|---|---|
| maker fee = 0 | CRYPTO15M (BTC+ETH proven) | kelly base-1 + gate + ≥2¢ spread + cooldown + τ-guard, front-of-queue | **+2.2–3.0¢/win**, Calmar 1.4–3.4 |
| maker fee = 0.0175·p(1−p) | any maker-fee series | SAME bot, `--fee-mult 0.0175` (kelly auto-tightens selection around p=0.5, threshold T 0.004–0.010 all OOS-positive) | **+2.5–2.8¢/win**, Calmar 1.8–2.3 |
| thin book (ETH/alt-like) | any fee regime | **do not trade** (negative even at front-of-queue, fee or no fee) | −2.5 to −6¢/win |

Key structural fact: the quadratic fee is ~0 at the price tails, so the fee-aware sizing rule keeps
the SAME positive-edge fills (benign, wide-spread, often tail-priced) and drops exactly the fills
the fee makes marginal — which is why the edge survives the fee regime nearly intact.
