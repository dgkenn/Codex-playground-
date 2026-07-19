# Participant Fingerprint — Kalshi 15m crypto binaries (btc/eth/sol)

**Node:** FAVLONG-FINGERPRINT · **Scope:** offline, archived data only (branch `origin/gha-data`,
`gha_data/<day>/`, 35 days 2026-06-10…07-15). No orders, no live changes. **Propose-only.**
**Goal:** behaviorally cluster the *other* participants that FAVLONG trades against, to test the
edge's durability and sharpen entry. Kalshi is **anonymous** — this is statistical clustering of
order flow, **not** identification of actors. Every "who" below is a *behavioral signature*, not a
named counterparty.

Scripts (scratchpad, uncommitted): `an_fills.py` (our footprint, all 35 days), `an_trades.py`
(external flow, 12 sampled days), `an_book.py` (ticks latency/persistence, 12 days), `an_tox.py`
(taker toxicity split, 4 days), `joint.py` (shares + decay regressions). Sampled days are
evenly spaced across the archive; 2026-06-10 is a partial start day and is excluded where noted.

---

## 0. What is fingerprint-able — and what anonymity/aggregation forbids

Field inventory actually present in the archive:

| stream | key fields | resolution |
|---|---|---|
| `trades_*` | `tid`, `ts_exch`, `ws`, `up`, `side` (aggressor BUY/SELL), `p`, `sz` | per **print**; **anonymous** |
| `book_*` | full `yes` bid ladder + `no` bid ladder (=yes asks via 1−p), `spot`, `rtt_ms` | **aggregated depth per price level** |
| `ticks_*` | `[t_in_win, mid, spot, micro, bid, bidq, ask, askq]` every **~1.2 s** | top-of-book trajectory |
| `fills_*` | **OUR OWN** box-maker fills: `tk_side`, `tk_sz` (taker who hit us), `mo5/mo30/mo_res` (markouts), `tox`, `box_bid/box_ask`, `var`, `res_up`, `pnl` | per fill, fully attributed to us |

**Fingerprint-able:** (a) aggressor trade **size distribution** and **timing** (parent sweeps
reconstructed by grouping prints on `ts_exch+side+up`); (b) **quote-update latency** and
**staleness** of the top of book after spot moves (from 1.2 s ticks); (c) **inside depth** and its
churn; (d) our **own** footprint and the **toxicity of takers that hit us**, exactly, from fills.

**NOT inferable (hard limits — state plainly):**
1. **No counterparty IDs.** Cannot name or count distinct actors. "Concentration" is inferred only
   from depth-chunk homogeneity and round-lot structure — weak proxies.
2. **Book depth is aggregated per price level.** Individual resting orders are invisible; we see
   only net depth and its changes. "Order-size distribution of resting quotes" is therefore
   **reconstructed from depth deltas**, not observed directly.
3. **Tick cadence ~1.2 s** floors all latency measurement — sub-1.2 s repricing is unresolvable.
   (Verified constant at 1.2 s across the whole archive, so latency *trends* are not a recorder
   artifact — see §4.)
4. FAVLONG's *maker* counterparties (who post the underpriced quote it lifts) are only observable
   through the **aggregated book**, not through trades (trades only expose the aggressor).

---

## 1. Participant archetypes (behavioral clusters)

**A. Aggressor (taker) flow — fat-tailed, naive-dominated.** Near-expiry (t≥600 s) parent sweeps:

| asset | median sweep | p90 | p99 | max | "big" (≥500 ct) | levels/sweep |
|---|--:|--:|--:|--:|--:|--:|
| btc | ~28 ct | ~350 | ~2,100 | 30k–80k | ~7% | 1 (median) |
| eth | ~19 ct | ~150 | ~970 | — | ~3% | 1 |
| sol | ~12 ct | ~150 | ~780 | — | ~2.5% | 1 |

A **small-lot core** (median 12–28 ct, single price level — retail / small algos) plus a thin
**heavy tail** of 2k–80k-ct sweeps. Most sweeps take a single level (nlev median = 1) → not deep
book-sweeping; the whales are rare, discrete events.

**B. Resting-quote / maker signatures — asset-differentiated (from ticks, near-expiry):**

| asset | reprice lat median | reprice lat p90 | wide-spread median | inside ask depth | stale-run p90 |
|---|--:|--:|--:|--:|--:|
| **btc** | 1.2 s (tick floor) | 3.8 s | 1.0 c | ~810 ct | 4 ticks |
| **eth** | 1.3 s | 5.5 s | 1.7 c | ~86 ct | 4.8 ticks |
| **sol** | 2.0 s | 8.1 s | 2.6 c | ~167 ct | 6 ticks |

- **btc = fast, deep, tight**: quotes reprice at the next tick, deep inside size — an efficient
  automated-maker signature. Little stale liquidity.
- **sol = slow, thin, wide, stale**: p90 reprice 8 s, wide 2.6 c spreads, stale runs to 6 ticks
  (~7 s) — the classic FAVLONG-friendly dislocated book. **eth is intermediate.**

This asset ordering (sol most dislocated → btc least) is the microstructure behind FAVLONG being a
*wide-book* effect, and cross-cuts the odd fact that sol's realized *edge* is the weakest OOS
(t=0.55 in the docstring): sol books are the stalest but too **thin** to capture much (inside depth
~167 ct, and much thinner at the near-ATM level FAVLONG lifts).

---

## 2. WHO FEEDS FAVLONG + concentration (priority 1)

FAVLONG is a near-expiry taker that lifts the **underpriced cheap side of WIDE books**. Its
counterparty is whoever **posts** that stale wide quote. Findings:

- **The feed is overwhelmingly EXTERNAL, not us.** Our box-maker executes only **~0.6% (btc),
  ~1.0% (eth), ~0.8% (sol)** of near-expiry contract volume, and **0.2–0.7%** of wide-book
  near-expiry volume (§5). FAVLONG's counterparties are external makers.
- **Signature of the fed liquidity:** wide (>1 c) inside markets with **elevated staleness** — the
  quote does not reprice for multiple ticks after spot moves. That lag *is* the edge (consistent
  with the mechanism report's "selective convergence-lag in wide books").
- **Concentration — one dominant provider or many? (weak-inference, anonymity limit).** Using
  inside-ask **depth-change chunk sizes** as a proxy:
  - **btc/eth:** depth churns in **large, non-round increments** (median Δ ~600–1,000 ct, only
    3–4% land on round 50/100 lots) → **broad, fragmented, continuous** liquidity from *many*
    overlapping participants. **Low fragility.**
  - **sol:** small, **round-lot** chunks (median Δ ~80–100 ct; 11–22% round 50/100) → a **thinner,
    fewer-maker** character; more identifiable single-order behavior → **higher concentration /
    fragility**, but on small absolute size.
  - **Confidence: LOW–MEDIUM.** With no order IDs this cannot be proven; the read is "btc/eth feed
    looks durable and many-sourced; sol feed looks thin and more fragile."

---

## 3. DECAY / early-warning (priority 2) — the most important finding

Per-day metrics regressed on calendar-day index (slope per day, t-stat):

| signature metric | slope/day | t | direction | read |
|---|--:|--:|---|---|
| **reprice latency, median** | −0.0122 | **−7.45** | falling | **counterparty repricing FASTER** |
| reprice latency, p90 (stale tail) | −0.0347 | **−2.61** | falling | stale episodes shrinking |
| inside ask depth (median) | +4.66 | **+2.50** | rising | more liquidity posted inside |
| taker size hitting our box (median) | −0.197 | **−3.59** | falling | flow fragmenting to smaller lots |
| wide-spread median | −1.2e-5 | −0.21 | flat | spreads **not** tightening (yet) |
| big-sweep fraction | +0.0007 | +2.57 | rising slightly | whales marginally more frequent |
| our box 30 s markout | −7.3e-5 | −1.13 | flat/down | insignificant |
| our share of volume | −3.4e-5 | −1.56 | flat/down | insignificant |

**The counterparty is measurably wising up.** Reprice latency is falling with a very strong
t=−7.45 (and the stale-tail p90 with t=−2.61), while inside depth grows — the market is becoming
more efficient and less stale near expiry. Tick cadence is constant (1.2 s), so this is **market
behavior, not a data artifact**. The median is near the 1.2 s floor, so the median-trend really
means *a rising share of quotes that reprice on the very next tick*; the p90 trend is the more
robust evidence and points the same way.

**Why this matters:** FAVLONG's own backtest P&L slope is flat (mechanism report: +0.0007/day,
t=1.1 — "no decay"). But the **microstructure that generates the edge is decaying faster than the
P&L reveals it.** Faster repricing + deeper inside quotes + no spread widening = the stale-quote
lag is eroding. **This is a leading indicator of P&L decay that the P&L regression cannot yet
see.** Treat it as an early-warning: monitor reprice-latency-p90 forward; if it keeps falling, the
edge window is closing even while backtest t-stats still look fine.

---

## 4. Toxicity split (priority 3)

From our own fills, markout of the **taker that hit our box**, by taker size (positive = we
profit → taker was **naive**; negative = they picked us off → **informed**):

| taker bucket | n (near-expiry) | our mo30 | our mo_res (to settlement) |
|---|--:|--:|--:|
| tiny (≤20 ct) | 12,102 | +0.0047 | +0.0076 |
| small (20–100) | 9,345 | +0.0050 | +0.0008 |
| med (100–500) | 5,157 | +0.0011 | +0.0045 |
| large (500–5k) | 1,390 | +0.0036 | +0.0192 |
| **whale (>5k)** | **11** | +0.0027 | **−0.083** |

**Informed/toxic flow is a rare whale tail (>5,000 ct): only 11 near-expiry fills, but strongly
adverse to settlement (−0.083).** Everything ≤5,000 ct is benign — the near-expiry ecosystem is
**naive-dominated**. This is a *taker*-side toxicity map (FAVLONG's counterparties are makers, so
it's a mirror, not a direct read), but it says the informed money moves in **rare, very large
sweeps**, which are detectable in real time. FAVLONG can plausibly **avoid the toxic subset** by
standing down when a whale sweep is active in the window (see §6).

---

## 5. Box-maker-OFF ecosystem estimate (priority 5)

Our box-maker was **ON every day of the archive** (`box_bid/box_ask` non-degenerate on 100% of
day-asset rows). Its near-expiry footprint:

- **Share of near-expiry executed volume: ~0.6% btc, ~1.0% eth, ~0.8% sol.** In wide books
  specifically, **0.2–0.7%**. (Denominator is inflated by the settlement-rush volume at 0.99/0.01;
  even generously, our box is a **low-single-digit-percent** slice of the near-ATM wide segment.)
- Our absolute near-expiry fill volume (btc ~120k–250k ct/day) is large in isolation but tiny
  against ~17–34M ct/day of total near-expiry prints.

**Implication for forward ≠ archive:** turning the box **OFF** removes ≲1% of near-expiry
liquidity. FAVLONG's counterparty feed is **external and essentially unchanged** by the box going
dark. This corroborates the mechanism report's "low cannibalization / complementary" verdict from
the opposite direction: our box is not a material supplier of FAVLONG's feed, so **forward ≈
archive for FAVLONG's counterparty environment.** *Caveat:* the denominator is noisy and this is a
volume share, not a resting-liquidity share at the exact near-ATM level FAVLONG lifts; confidence
**MEDIUM**. The one residual risk is indirect — if our box being off changes *other* makers'
behavior (e.g., they widen further) — which is unobservable from archive data.

---

## 6. Actionable signals

**FAVLONG durability verdict: INTACT NOW, but on an early-warning watch.** The edge's counterparty
environment (external, wide, stale, naive-dominated, many-sourced on btc/eth) is healthy and is
**not** our own box (box-off doesn't change the feed). **But** the counterparty is demonstrably
repricing faster over the 35 days (reprice-latency p90 t=−2.61, median t=−7.45; inside depth
rising t=+2.50) with **spreads not yet tightening** — a genuine leading indicator that the
stale-quote lag is closing. **Net: keep it PROPOSE-ONLY behind the forward gate, and add the
latency trend as a decay tripwire** — do not rely on the flat P&L slope alone.

Concrete proposals (all propose-only; require the forward gate + operator sign-off):

1. **Entry filter — prefer stale, wide books.** Condition entries on *observed staleness*: inside
   quote unchanged for ≥2–3 ticks (~2.5–3.5 s) AND spread >1 c. This targets exactly the
   slow-repricing counterparty; it should raise mean edge and shed the fast-repricer (informed
   maker) cases where lifting is toxic.
2. **Regime flag — whale detector / stand-down.** Suppress FAVLONG in any window where a ≥5,000-ct
   (or, softer, ≥2,000-ct) parent sweep prints — that is the only reliably *informed* cohort
   (mo_res −0.083). Rare, so low opportunity cost.
3. **Asset weighting.** btc's feed is the most durable (deep, fragmented, many-sourced) → safest to
   scale. sol's feed is the stalest but **thin and more concentrated/round-lot** → highest
   fragility and thinnest capture; size sol smallest and watch its round-lot chunking as a
   concentration alarm.
4. **Forward decay tripwire.** Track near-expiry **reprice-latency p90** and **inside-depth**
   forward; a continued fall in latency-p90 or rise in inside depth = counterparty efficiency
   catching up → pre-emptively de-size, ahead of any P&L-visible decay.

---

## Honesty ledger

- Anonymity is the binding constraint: **no actor identification, no true participant count.**
  Concentration is a weak depth-chunk proxy (confidence LOW–MEDIUM).
- Latency is floored at the 1.2 s tick cadence; median-latency results are floor-limited (p90 is
  the trustworthy metric).
- Toxicity split is *taker*-side (from our fills); FAVLONG's counterparties are makers, so it is a
  mirror, not a direct measurement.
- Trades/book analyses use 12 evenly-spaced sampled days (fills use all 35). Sampling adds noise to
  the sampled-day regressions (n=12–13) but the strongest signal (reprice latency) is far from the
  significance boundary.
- Volume-share (§5) uses total executed volume as denominator, which over-counts settlement-rush
  extremes; the true near-ATM resting-liquidity share is not directly measurable.
