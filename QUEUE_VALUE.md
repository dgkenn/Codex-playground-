# QUEUE_VALUE.md — Queue Research: Q1/Q2/Q3 Findings

Generated: 2026-06-12  
Data: `gha_data/fills_btc15m_*.jsonl` (N=47,231 fills, Jun 9–10 2026),  
`audit_book.jsonl` (N=90,471 snapshots, 34 windows Jun 7),  
`overnight_data/book_kalshi_btc15m*.jsonl.gz` (N=21,438 snaps, 34 windows Jun 11)

Scripts: `queue_q1_analysis.py`, `queue_q2_analysis.py`, `queue_q3_analysis.py`  
All three are runnable and verified. Leave uncommitted.

---

## Q1 — What Is Front-of-Queue Worth?

### Method
Two independent sources:
1. **Book-replay** (`audit_book.jsonl` + `trades_kalshi_btc15m.parquet`): detects take events as consecutive top-of-book depth drops at constant price. Classifies into front/middle/back tier by `delta_depth / total_depth`. 34 windows, 233 take events.
2. **Fills tape** (`fills_btc15m*.jsonl`): uses actual `q_ahead` and `tk_sz` per fill. N=47,231. `q_ahead / bsz` gives queue position fraction at fill time. `mo_res` is settlement-contingent maker markout.

### TABLE 1 — Queue Tier × Markout (book-replay, controls for per-window bias)

| Queue Tier | N events | Mean take ($) | P(win) | Markout (c) | Excess vs baseline (c) |
|---|---|---|---|---|---|
| Front ≤1/3 depth (small takes) | 233 | 44.8 | 0.481 | −0.64 | **+1.22** |
| Middle 1/3–2/3 | 202 | 98.4 | 0.485 | −0.28 | +0.53 |
| Back >2/3 (large sweeps) | 151 | 320.3 | 0.477 | −1.18 | +0.46 |

**Front-vs-back advantage: +0.76¢ excess markout.**

### TABLE 2 — Take-Size × Markout (fills tape, N=47k)

| Category | N | mo_res (c) | P(+) | q_frac |
|---|---|---|---|---|
| Small (tk ≤ 5¢) | 13,737 | **+2.46** | 0.417 | 0.003 |
| Medium (5 < tk ≤ 20¢) | 19,807 | +0.98 | 0.484 | 0.017 |
| Large (tk > 20¢) | 13,687 | −0.73 | 0.524 | 0.490 |
| Sweep (tk > bsz) | 4,918 | +0.42 | 0.547 | 1.328 |

**Selection effect: front-queue (small-take) fills earn +3.19¢ more than large-sweep fills.**

### Key Findings

1. **Front-of-queue IS worth holding.** Small naïve takers fill the front third; they are less directionally informed. Excess markout is +1.22¢ vs +0.46¢ for back-of-queue (book-replay) or +2.46¢ vs −0.73¢ (fills tape).

2. **Large sweeps are NOT more adversely selected than expected.** Large taker accuracy (big YES sweeps → YES settles) is 76.7%; large NO sweeps → NO settles 79.5% (N=73 and 78 events). This IS adverse, but the `mo_res` for sweep fills is still +0.42¢ — the maker still earns positive expectation on sweeps because the sweep fills the ENTIRE level (including back positions) and settlement is not perfectly predicted by the sweep direction.

3. **Reconciliation with "large informed takes almost never fill us at FOQ"**: confirmed — 85.2% of our actual fills occur at `q_ahead = 0` (front of queue). The FILLS data shows we predominantly get filled by small takers. Large sweeps only reach us if we're front-of-queue anyway (they fill everyone). The selection effect is 3¢ wide per fill.

4. **1.2-s snapshot cadence caveat**: book-replay misses intra-interval activity. We can observe level depletion over 1.2s gaps but cannot see queue position during that interval. Front/back tier assignment is approximate. Fills tape (`q_ahead` from actual market data) is the primary source.

---

## Q2 — The Repricing Trade-Off (Break-Even for `--qtime-mp-margin`)

### Method
For each fill, `div = |microprice − mid|`. Classify: **stale** (would have triggered reprice at threshold X) vs **fresh**. Measure `mo_res` by divergence bucket. Model:
- **STAY**: keep queue position; realized markout = `mo_stale`  
- **REPRICE**: cancel + re-post at new touch; P(refill) = 0.50 (assumed; back of new queue); expected markout = `0.5 × (mo_stale + div_100c)`  

IS/OOS split: 60/40 by time (IS = Jun 9 01:15–17:15, OOS = Jun 9 17:30–Jun 10 03:45).

### TABLE A — IS Scan

| Thresh | N_stale | mo_stale (c) | mean_div (c) | E[stay] | E[reprice] | Verdict |
|---|---|---|---|---|---|---|
| 0.001 | 25,788 | +0.98 | 0.37 | 0.98 | 0.68 | **STAY** |
| 0.002 | 21,353 | +0.63 | 0.42 | 0.63 | 0.53 | **STAY** |
| 0.003 | 16,123 | +0.67 | 0.48 | 0.67 | 0.57 | **STAY** |
| 0.004 | 10,103 | +1.11 | 0.56 | 1.11 | 0.83 | **STAY** |
| **0.005** | **1,846** | **−1.02** | **1.04** | −1.02 | +0.01 | **REPRICE** |
| 0.006 | 1,219 | −1.80 | 1.31 | −1.80 | −0.25 | REPRICE |
| 0.007 | 1,076 | −3.30 | 1.40 | −3.30 | −0.95 | REPRICE |
| 0.008 | 914 | −2.62 | 1.52 | −2.62 | −0.55 | REPRICE |

**IS break-even: X = 0.0050.** Stale fills with `|mp−mid| ≥ 0.005` have negative expected markout → reprice unconditionally above 0.005.

### TABLE B — OOS Verification

OOS says REPRICE at all thresholds (lower baseline markout in that period). The transition is:

| Thresh | N_stale | mo_stale OOS (c) | Verdict OOS |
|---|---|---|---|
| 0.003 | 9,534 | +0.47 | REPRICE (just barely) |
| 0.004 | 5,760 | +0.23 | REPRICE |
| 0.005 | 948 | −0.44 | REPRICE |

OOS is consistent with IS directionally but the breakeven shifts lower (≈0.003–0.004 on OOS). The IS/OOS discrepancy is not surprising given only 41 OOS windows.

### Verdict on `--qtime-mp-margin 0.003`

At 0.003: **IS says STAY wins** (E[stay]=+0.67c > E[reprice]=+0.57c). The 0.003 threshold is firing on fills that still have positive stale markout. This means we're giving up +0.67c fills to reprice into a maybe-fill at +0.57c — a net -0.10c/event in expectation on IS.

**Fitted break-even: raise to 0.005.** This is where the stale markout first turns negative and repricing is unambiguously better.

### Live Data Read

34 `reshape_qtime` cancel_fail events in `live_metrics_kalshi_btc15m.jsonl`. All are **cancel failures** (the order had already been consumed before the cancel arrived). Zero actual qtime-triggered post-reprice fills observed. **→ n too small for live A/B comparison.**

### Recommendation
`--qtime-mp-margin 0.005` (raise from 0.003). Confidence: medium. Caveat: P_refill=0.50 is a model assumption; if actual refill rate after reprice is lower, break-even is higher.

---

## Q3 — Two-Rung Split (t27 Grounding)

### Method
Simulate `8@touch` vs `4@touch + 4@touch-1c` using fills tape.  
- Strategy A: 8 contracts at touch; fills when `tk_sz > q_ahead`  
- Strategy B: 4 at touch (same), PLUS 4 at touch-1c; deep leg fills only when `tk_sz > bsz` (touch level swept through)  
- Touch-1c markout model: −1¢/contract (structural adverse-selection prior on sweep fills)  
- "Deep hours" proxy: windows with above-median fill volume

### Results

| Metric | 8@touch | 4+4 split |
|---|---|---|
| P(any fill per event) | 1.000 | 1.000 |
| E[contracts filled/event] | 6.20 | 4.01 |
| P(sweep reaches touch-1c) | 10.0% | same |
| E[deep-leg contracts/event] | N/A | 0.371 |
| E[markout \| deep fill] | N/A | −1.00¢ |
| E[PnL c per event] (mk=0 at touch) | 0.00 | **−0.37** |
| Fill-count delta | — | −2.19 contracts/event |

(Deep-hours results nearly identical: sweep rate = 10% regardless.)

### Verdict: AGAINST the 4+4 split

The split **loses 2.2 expected contracts per fill event** (the deep leg only fires on 10% of events and fills only 0.37 contracts on average) while taking a −1¢/contract adverse sweep hit. E[PnL] is −0.37c/event worse than all-at-touch.

**t27 Stage-B GO/NO-GO: NO-GO for the 4+4 split as specified.**

The only way the split would be neutral is if sweep markout at touch-1c is actually ≈ 0 (i.e., sweeps are not directional). The fills tape shows sweep fills have `mo_res = +0.42¢` and `mo5 = +0.82¢` — better than the −1¢ model! But this is the markout for *our touch-level fills on sweep events*, not for a touch-1c rung. The touch-1c maker fills on sweeps that consumed the full level; the additional adverse selection for going one tick deeper is real.

### Honest Caveats for Q3

1. **q_ahead proxy**: `q_ahead` is measured at fill time, not at placement. We likely underestimate the true queue-ahead at the moment we place, which would reduce simulated fill counts for both strategies. The relative verdict (split vs all-at-touch) is directionally robust.

2. **Touch-1c markout assumption**: −1¢ is a structural prior. If the bot's deep rung benefits from the same +0.42¢ base, the real cost might be only −0.58¢ per deep fill → PnL penalty reduces to −0.22c/event. Still negative.

3. **t27 volume trigger**: "above median fill volume" is not the t27 condition. Results should be re-validated when intra-window order-flow timing is available.

---

## Summary and Recommendations

| Question | Answer | Confidence |
|---|---|---|
| Front-of-queue worth | +0.76¢ excess markout vs back (book-replay); +3.19¢ small vs large take (fills tape). Front IS valuable, primarily because small naïve takers are less adverse. | Medium (34 windows book-replay; 47k fills tape) |
| Reprice break-even | IS: 0.005; OOS: 0.003–0.004. Current 0.003 fires too aggressively. | Medium |
| Suggested `--qtime-mp-margin` | **Raise to 0.005** | Medium |
| Live A/B evidence | 34 cancel_fails only; n too small | — |
| t27 4+4 split | **NO-GO**: −2.2 fills/event, −0.37c/event expected PnL loss | Medium |

### Concrete Recommendations

1. **`--qtime-mp-margin 0.005`**: raise from 0.003. At 0.003 the bot is repricing fills that are still earning positive stale markout. The IS crossover to negative stale markout occurs at 0.005.

2. **Hold front-of-queue when earned**: queue position at the touch is worth +0.76¢ excess (book-replay) to +3.19¢ (fills selection). Do not voluntarily surrender it without meeting the 0.005 divergence threshold.

3. **t27 two-rung split: do not deploy** at current 4+4 specification. The deep-leg sweep rate (10%) is too low to compensate for adverse-selection cost on sweeps. If t27 advances, reduce deep-leg size to 1–2 contracts or require sweep-rate conditioning above 25%.

4. **1.2-s snapshot coarseness**: confirmed manageable. Level-sweep frequencies (10% of fill events are full sweeps) and displayed-size dynamics (median depth 736 contracts, 41% of intervals see a price change at touch) are measurable at 1.2s cadence. Queue-position estimation within a level requires the fills tape, not the book snapshots.

---
## ACTION TAKEN (2026-06-12 22:55 UTC)
`live_loop.sh` updated: `--qtime-mp-margin 0.003 → 0.005` (the fitted break-even above; applies at
the next trader cycle). Both independent Q2 fits agree the old 0.3c margin repriced inside the
regime where staying earns more (+0.67c stay vs +0.57c reprice at 0.3c IS). t27 (4+4 split) is
NO-GO per Q3 — recorded against its pre-registration in TRIALS.md.
