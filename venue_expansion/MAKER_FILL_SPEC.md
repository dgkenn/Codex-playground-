# MAKER FILL — pre-registered spec (REGISTERED 2026-10-27, before any fill is measured)

## What the tail-pricing study established, and the door it left open

`TAIL_PRICING_SPEC` returned **INSUFFICIENT** with strong scientific content, on 199,178 priced
sales across all 60 days:

**Kalshi BTC-hourly longshots are calibrated at the executable `yes_bid`.** At T=15 minutes:

| bid bucket | n | realised YES rate [Wilson 95%] | mean bid |
|---|---:|---|---:|
| 1c | 400 | 0.50% [0.14, 1.80] | 1.00c |
| 2c | 175 | 1.14% [0.31, 4.07] | 2.00c |
| 3c | 149 | 2.68% [1.05, 6.70] | 3.00c |
| 4–5c | 158 | 3.80% [1.75, 8.04] | 4.45c |
| 6–10c | 234 | 5.13% [2.96, 8.75] | 7.71c |

The mean bid lies **inside the Wilson interval in 27 of 28 longshot cells**, and the sign of the gap
flips across buckets and entry times. There is **no favorite–longshot bias here.** That closes the
risk-premium hypothesis on the taker path.

**And the study named exactly why the taker path cannot work:** `ceil(7·p·(1−p))` is **1 cent for
every bid up to 17c**. Selling at 1c can never net more than zero. In the longshot zone the
quantized minimum fee *is* the entire gross edge.

**The door: that fee applies only to the taker path, which is all I pre-registered.** The per-series
fee survey (2026-10-27, Kalshi API, 9,191 series) settles the question I had flip-flopped on:

| `fee_type` × `fee_multiplier` | series |
|---|---|
| `quadratic`, 1 — **taker only, no maker fee** | **9,029** |
| `quadratic_with_maker_fees`, 1 | 131 |
| `quadratic`, 0.5 | 18 |
| `quadratic`, 0 — zero fees entirely | 12 |

`KXBTCD` is `quadratic`. **A resting order on BTC hourlies pays no fee.**

## The hypothesis

If the market is calibrated at the **bid** and a maker pays **no fee**, then **resting an ask one or
more cents above the bid has a gross edge equal to the spread it captures.** From the table above:
rest an ask at 2c where the realised YES rate is 0.50% and the gross EV is `2 − 0.50 = +1.5c` per
filled contract, with zero fee.

**This is not a signal, an information advantage, or a speed advantage.** It is being paid the
spread for providing immediacy in a market whose fair value we have now measured. That is why the
weather kill (the market's forecast beats our observation) does not reach it.

## Why it will probably still fail, stated before measuring

Study #42 (maker) died on **adverse selection**, and the mechanism applies here with full force: a
resting ask at 2c on a far-from-spot strike gets lifted **precisely when BTC starts moving toward
that strike.** Conditional on being filled, the realised YES rate should be *worse* than
unconditional. If it is worse by more than the spread captured, the strategy is dead and the
calibration table above is irrelevant.

**That single comparison is the primary measurement of this spec**, not EV:

> `P(YES | filled)` versus `P(YES | quoted)` at the same price level.

## Design — frozen

- **Universe**: settled `KXBTCD` strikes in the **existing `cache/tail_pricing/` candle cache**
  (503 hourly events, 60 UTC days, closes 2026-08-22..10-20). **No new API fetching is required**;
  if more hours are added they must come from the same saved seed-20261027 shuffle order, never
  re-sorted.
- **Quote placement, frozen**: at each entry time `T ∈ {5, 15, 30, 45}` minutes before close, rest a
  **sell order on YES** at price `a = yes_bid + k` cents for `k ∈ {1, 2, 3}`, provided `a ≤ 20c`
  (longshot zone only; above 20c is reported but cannot PASS). Quote is placed once and held to
  close. No re-quoting, no cancels, no "best k" search.
- **Fill model — report BOTH bounds, neither alone is the answer:**
  - **OPTIMISTIC (ceiling)**: filled if any traded volume occurs at a price ≥ `a` in any candle
    between `T` and close. This assumes front-of-queue, which this program has already shown is an
    optimistic bound.
  - **PESSIMISTIC (floor)**: filled only once cumulative volume at a price ≥ `a` after `T` exceeds
    `N` contracts resting ahead, for `N ∈ {25, 100}` (25 = the deployed `DEPTH_CAP`). Book depth is
    not in the candle archive, so `N` is an explicit assumption, labelled as such.
  - A quote that is never filled earns **zero**, is counted, and is never imputed a profit.
- **P&L per filled contract**, zero maker fee: `+a` if the strike settles NO, `−(100 − a)` if YES.
- **Cluster unit = calendar day.** One BTC move hits every strike in every hour of that day.
- Outcome = Kalshi official `result` only.

## PASS / KILL — frozen now

Bonferroni over 3 `k` values × 4 entry times × 2 fill models = **24 comparisons**; two-sided
α = 0.05/24 = 0.00208 ⇒ bar is the exact Student-t quantile at p = 0.99896 on realised day-count df.
**Signed** t: a negative t clearing the magnitude is evidence for KILL, never PASS.

**PASS** requires ALL, in ≥1 cell, **under the PESSIMISTIC fill model at N=25**:
1. **Adverse-selection test passes**: the Wilson 95% upper bound on `P(YES | filled)` is below
   `a/100` — i.e. the fill-conditional loss rate is still under the price collected
2. fee-free **EV ≥ +0.5c per quoted contract** (not per filled contract — unfilled quotes are in the
   denominator, because a strategy that fills rarely cannot pay for itself)
3. signed day-clustered **t ≥ the exact Bonferroni bar**
4. **n ≥ 500 filled contracts across ≥ 40 distinct days**
5. **fill rate ≥ 5%** of quotes

**KILL** if `P(YES | filled)` exceeds `P(YES | quoted)` by a factor ≥ 2 with non-overlapping Wilson
95% intervals, in every cell meeting the n floor. *(KILL is written on the adverse-selection ratio,
not on an EV upper bound. In #44 the noisiest cell shielded the hypothesis from its own KILL clause;
in `TAIL_PRICING` I over-corrected and froze an EV-upper-bound KILL that **could never fire** —
with a 1:33 payoff the day-clustered SE is 1.5–2.6c, so the 97.9% bound sits near +1.7c even at
100% coverage. A KILL clause must be written on a quantity that converges.)*

**Anything else → INSUFFICIENT.**

## Mandatory anchors (each must hold or the result is void)

- **(a) Primary comparison reported first.** `P(YES | filled)` vs `P(YES | quoted)`, per cell, with
  Wilson intervals, before any EV number appears in the report.
- **(b) Unfilled quotes in the denominator.** Show the quote count, fill count and fill rate for
  every cell. Per-filled-contract EV may be shown only beside per-quoted EV, never instead of it.
- **(c) No look-ahead in placement.** The quote price depends only on the candle at or before `T`.
  Assert in code; hand-work 10 placements.
- **(d) Queue assumption disclosed.** State plainly that book depth is absent from the archive, that
  `N` is an assumption, and how the verdict changes between `N=25`, `N=100` and the optimistic
  bound.
- **(e) Tail risk.** Worst single day's aggregate P&L and maximum simultaneous short exposure.
  Selling tails loses many small and few large; `TAIL_PRICING` measured a worst day of −1,573c on
  sampled hours alone.
- **(f) Volume provenance.** Candle `volume` is total traded volume in the minute, not volume at or
  above a given price. State exactly how price-conditional volume was attributed and what that
  approximation can and cannot support. If it cannot be done honestly from this archive, say so and
  return NOT-MEASURABLE rather than guessing.

No bar in this document may move after 2026-10-27. A PASS is necessary-but-not-sufficient; the only
permitted next step is a separately-registered 1-contract live canary.
