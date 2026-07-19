# EDGE-CAPTURE — how much MORE of the confirmed weekly crypto short-vol edge is capturable?

**Question.** The confirmed edge (SELL far-OTM weekly "BTC/ETH above $X on <date>" YES
longshots == buy NO; executable YES-mid band [0.15,0.30]; first-half entry; resting
MAKER; ~ **+10.6c/ct eq, +12.0c/ct bv, week-clustered t≈4.6**) is fixed. Can we capture
**more of it** via two real levers — (1) the maker **REBATE** now paid on crypto markets,
and (2) optimal **STRIKE/timing selection** within the band? This is not a new edge.

**Data.** `scratchpad/advsel_rows.json` — 601 settled markets, 49 ISO-weeks, BTC+ETH,
entry YES-mid ∈ [0.15,0.30], first-half snapshot, 2025-08-11 → 2026-07-15, YES-settle
rate 10.3% (vs ~22% priced). Seller PnL/ct = `(entry − half_spread) − yes_win`, sell at
bid, zero-fee baseline. This is the same recovered settled sample the edge was confirmed
on (baseline reproduces: pooled eq **+10.57c**, bv **+11.97c**). Timing uses the
LONGSHOT-TIMING study's 2626-market entry-fraction grid, re-derived here.
Code: `edge_capture.py`. All read-only, no orders, no capital.

---

## LEVER 1 — the maker rebate: REAL, deterministic, +2.2% of the edge

**Mechanics (verified live fields + Polymarket docs).** Crypto markets carry
`feeType=crypto_fees_v2`, `feeSchedule{rate:0.07, exponent:1, takerOnly:true,
rebateRate:0.2}`. Taker fee `= C·0.07·p·(1−p)`; makers pay **zero**. The Maker Rebates
Program pays, per market per day:

> `rebate = (your_fee_equiv / total_fee_equiv) · rebate_pool`,
> `fee_equiv = C·0.07·p·(1−p)`, `rebate_pool = 0.20 · (taker fees collected in that market)`.

**The pro-rata form self-normalizes to a flat per-fill pass-through.** Every fill has
exactly one maker and one taker at the same `(C,p)`, so the sum of maker fee-equivalents
equals total taker fees — the very base the pool is 20% of. Therefore
`rebate = 0.20 · (your own fee_equiv) = 0.20 · 0.07 · p·(1−p)` per share, **deterministic**.

This is the key correction to the earlier internal LP-REWARDS note, which conflated **two
different programs**: (a) this **Maker Rebate** (`rebateRate:0.2`) — deterministic 20%
fee pass-through, **no min-size, no two-sided quoting, no midpoint/requote requirement**;
and (b) the separate **CLOB Liquidity-Rewards pool** (`clobRewards`, `rewardsMinSize`,
quadratic Q-score at the mid) — the latency-bound market-making arms race. **Lever 1 is
(a), and (a) has none of (b)'s requirements.** The only gate is a $1 accrual before
payout, which rolls over — a small book still earns it, just paid less often.

**Magnitude for the resting short-vol seller** (rebate `= 0.014·p·(1−p)`, integrated over
the 601-market entry distribution):

| quantity | value |
|---|---|
| mean rebate / contract | **+0.236c** (bv-weighted +0.234c) |
| range over band [0.15,0.30] | +0.18c (at 0.15/0.30 wings) → +0.29c (near 0.30 mid-side) |
| as % of the +10.57c eq edge | **+2.23%** |
| as % of the +11.97c bv edge | **+1.95%** |

**The bigger fee lesson is a sign, not a size.** The rebate is only earned on **maker**
fills. If you instead **cross the spread (take)**, you *pay* the taker fee
`= 0.07·p·(1−p)` ≈ **−1.18c/ct** — which would erase **~11%** of the edge. So the
fee-regime swing between "rest and collect" and "cross and pay" is ~1.4c/ct. The strategy
is already specified as a resting maker; the operational discipline is simply
**never cross** (and the forward gate must confirm fills are maker).

**Verdict L1:** real, deterministic, feasible for a small book, **+2.2% of the edge**
(~+0.24c/ct). Small but free, with no adverse-selection cost of its own.

---

## LEVER 2 — strike/timing selection within the band: NULL (no robust improvement)

### 2a. Sub-band (in-sample) — looks tempting, and that is the trap

| slice | n | eq mean (t) | bv mean (t) | eq lift | bv lift |
|---|---|---|---|---|---|
| BLANKET [0.15,0.30] | 601 | +9.02c (3.73) | +9.00c (2.88) | — | — |
| 0.15–0.20 | 242 | +8.92c (4.10) | +7.97c (2.44) | −0.10c | −1.03c |
| 0.20–0.25 | 194 | +7.71c (2.07) | +10.51c (2.83) | −1.31c | +1.51c |
| 0.25–0.30 | 165 | +13.43c (3.90) | +15.02c (3.94) | **+4.41c** | **+6.02c** |

(means here are mean-of-week-means, the week-clustered convention; pooled blanket = +10.57c.)

In THIS sample the **0.25–0.30** sub-band looks strong (+4–6c lift, t≈3.9). But the prior
LONGSHOT-CONDITIONAL study (different, earlier sample) found **0.20–0.25** best in-sample
and **0.25–0.30 among the WORST in TRAIN** (bv lift −4.5c). **The "best sub-band" flips
between samples** — the textbook signature of an in-sample artifact, not a mechanism.

### 2b. Walk-forward selection (the real test) — insignificant on eq, strictly worse on fills

Expanding-window: at each test week, pick the sub-band with the best mean edge over all
prior weeks, realize its actual edge that week, compare to the blanket over the same weeks.
Sensitivity across training windows (min_train ∈ {8,12,16,20} weeks):

| metric | adaptive mean | blanket mean | mean diff | diff t | adaptive Sharpe(wk) | blanket Sharpe(wk) |
|---|---|---|---|---|---|---|
| **eq** (min_train 12) | +12.44c | +11.09c | +1.35c | **0.57** | 0.711 | 0.740 |
| eq (range over 8–20) | +11.85…+12.32c | — | +0.84…+2.60c | 0.39…0.90 | 0.64…0.71 | lower–higher |
| **bv** (min_train 12) | +8.43c | +11.92c | **−3.49c** | −0.82 | **0.297** | 0.662 |
| bv (range over 8–20) | +5.95…+8.01c | — | −3.49…−3.86c | −0.70…−0.99 | 0.19…0.29 | 0.49–0.67 |

- **Equal-weight:** adaptive mean is marginally higher (+0.8 to +2.6c) but **never
  significant** (t ≤ 0.90) and its Sharpe is **at or below** the blanket in 3 of 4 windows.
  A Sharpe-neutral, insignificant wash.
- **Realistic fill-weighted (bv):** adaptive is **consistently and substantially worse** —
  mean −3.5 to −3.9c, negative t, and roughly **HALF the Sharpe** of the blanket in every
  window. On the metric that matters (you fill in proportion to YES-buy volume), sub-band
  selection **destroys** edge and risk-adjustment.

### 2c. Fixed pre-registered pick (prior in-sample winner 0.20–0.25), OOS once

Evaluated on the held-out last 40% of weeks: eq lift **−6.7c**, bv lift **−4.6c** vs
blanket. The prior sample's in-sample winner **loses** out-of-sample — same result the
LONGSHOT-CONDITIONAL study reported for its disciplined pick.

### 2d. Moneyness normalization — isolates nothing

Using price-implied standardized moneyness `m = −Φ⁻¹(entry)` (higher = further OTM):
regression of per-contract edge on `m` has slope −0.075 and **Pearson r = −0.036**
(essentially zero). Moneyness terciles: near +12.8c, mid +5.3c, far +9.3c — **non-monotone
noise**. `edge/m` is 0.21 / 0.11 / 0.11 — not a stable per-unit-moneyness constant you
could exploit, and no cleaner selection than the raw price. Expressing the edge per unit of
moneyness adds nothing.

### 2e. Entry timing — earliest (already the rule) is best; no later sweet spot

From the LONGSHOT-TIMING 2626-market grid (entry fraction f of market life):

| f | edge/ct (t_eq) | bv edge/ct (t_bv) |
|---|---|---|
| **0.20** | **+6.11c (1.56)** | −2.49c (1.49) |
| 0.35 | +5.69c (1.60) | −3.27c (0.29) |
| 0.50 | +3.23c (0.51) | −6.47c (−0.70) |
| 0.65 | +2.21c (0.36) | −12.7c (−0.46) |
| 0.80 | +0.96c (−0.03) | −4.70c (−0.76) |

Equal-weight edge **decays monotonically** with later entry; the earliest first-half
fraction (0.20) is already the best cell, and the fill-weighted edge is **negative at every
fraction** (adverse selection). Entering later to harvest a "fatter late premium" does not
exist. The current first-half rule already sits at the optimum; **no timing lever**.

### 2f. Multiple-testing accounting

Sub-band candidates: 3 (×2 metrics). Timing fractions: 5. Prior conditioning searches on
the same edge: LONGSHOT-CONDITIONAL (25 rules) and VRP-REGIME (27 tests) — **both null**.
Across ~60 cumulative conditioning tests on this edge, **zero** robust walk-forward winners
survive. With even 3 fresh sub-band candidates the Bonferroni bar is |t|≈2.5; the best
walk-forward diff here is t≈0.9. Nothing clears a haircut.

**Verdict L2:** **NULL.** No sub-band, moneyness, or timing selection robustly beats the
blanket band. In-sample sub-band gains (+4–6c on 0.25–0.30) are non-reproducible (the best
band flips across samples), vanish to an insignificant Sharpe-neutral wash walk-forward on
equal weight, and **reverse to ~−3.7c at half the Sharpe** on the realistic fill-weighted
metric. Third independent confirmation that this edge is effectively **unconditional**.

---

## BLUNT VERDICT — how much MORE is capturable?

| lever | capturable | robust? | feasible for small book? |
|---|---|---|---|
| **Maker rebate** | **+0.24c/ct ≈ +2.2% of edge** | Yes — deterministic 20% fee pass-through | **Yes** — no min-size/two-sided; $1 accrual rolls over |
| **Strike/timing selection** | **≈ 0% (−3.7% on the fill-weighted metric)** | **No** — insignificant on eq, worse on bv, flips across samples | n/a |
| **(discipline) avoid crossing** | avoids −11% taker drag | — | rest, never take; gate must confirm maker fills |

**Bottom line: ~+2% of the confirmed edge is capturable, and all of it is the maker
rebate (~+0.24c/ct).** Strike/timing selection adds **nothing robust** — on the metric that
governs real fills it *subtracts* ~3.7c and halves the Sharpe, exactly as the two prior
conditioning nulls predicted. The one execution rule with real leverage is *negative*
protection: **stay a resting maker and never cross the spread**, or the new 7% taker fee
quietly costs ~11% of the edge — ~50× larger than the rebate it would forgo.

*Artifacts: `edge_capture.py`, `edge_capture_summary.json`.*
