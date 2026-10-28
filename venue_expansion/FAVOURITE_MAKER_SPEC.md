# FAVOURITE-SIDE MAKER — pre-registered spec (REGISTERED 2026-10-28, before any fill is measured)

## The untested half, and the measured effect that motivates it

`MAKER_FILL` tested resting **asks on longshots** and found adverse selection ratios of 1.12–2.29,
with the day-bootstrap CI of the difference positive in all 36 cells, eating essentially the whole
spread. It never tested the **mirror**: resting **bids on favourites**.

`TAIL_PRICING` measured, as a reported-but-outside-the-frozen-family observation:

> At `yes_bid ≥ 81c` the realised YES rate **exceeds** the bid by about **1.0c** at every entry
> time. Selling favourites loses about 2c per contract (t between −55 and −180).

It explicitly did not test buying, because taking the ask is dead on arithmetic: if `100f ≈ b + 1`
and `ask = b + s`, then a taker buy nets `(b+1) − (b+s) − fee = −s − fee + 1 < 0` for any spread.

**But a resting bid pays no fee** (`KXBTCD` is `fee_type: quadratic`, taker-only, confirmed in the
2026-10-27 survey of 9,191 series). Resting a buy at `d` and being filled nets
`100·P(YES | filled) − d` with **zero fee**. If the realised rate really sits ~1c above the bid,
that is a positive gross edge on the one side of the book this program has never measured.

## Why it will probably fail, stated before measuring

Exactly the mirror mechanism: **your bid gets hit when someone wants to sell**, i.e. when YES is
becoming *less* likely. So the adverse direction here is `P(YES | filled) < P(YES | quoted)`, and if
the shortfall exceeds the ~1c of edge, the strategy is dead.

## Power ceiling — computed in advance, which the last two specs failed to do

`TAIL_PRICING` froze a KILL clause that **could never fire**, and `MAKER_FILL` ended INSUFFICIENT
because the cluster count saturates. Both are my errors. Applying the lesson here *before* freezing:

- The cluster unit is the calendar day and the window holds **60 days**; `MAKER_FILL` covered 59 of
  them. **The day count is saturated and cannot be increased** by adding hours.
- Per-contract sd on the favourite side is `√(f(1−f))·100 ≈ √(0.85·0.15)·100 ≈ 36c`, **larger** than
  the longshot side's ≈22c. So the day-clustered SE on EV will be **worse** than `MAKER_FILL`'s
  1.0–1.8c, roughly 1.6–3.0c.
- Clearing a Bonferroni t-bar near 3.2 would therefore require **EV ≈ +5 to +10c per quoted
  contract**, against an expected effect of ~1c per fill.

**Conclusion, frozen in advance: an EV t-statistic gate is unreachable here, so this spec does not
use one.** A gate that cannot be met is a defect, not rigour. The gates below are written on
**proportions**, which converge at these sample sizes (n ≈ 500–900 fills gives Wilson widths of
±2–3pp).

## Design — frozen

- **Universe**: the same `KXBTCD` hours and the same microsecond trade tape as `MAKER_FILL`
  (`cache/maker_fill/tape/`, `GET /markets/trades`, validated there at 22,529 of 22,529 candle-minutes
  matching tape volume exactly). Same saved **seed-20261027 hour order, never re-sorted**; report the
  covered fraction and whether it is an exact prefix.
- **Favourite zone, frozen**: strike-minutes with `yes_ask ≥ 80c`.
- **Quote placement, frozen**: at each entry time `T ∈ {5, 15, 30, 45}` minutes before close, rest a
  **buy on YES** at `d = yes_ask − k` for `k ∈ {1, 2, 3}`, held to close. One quote per strike-T.
  No re-quoting, no cancels, **no best-k and no best-minute search**.
- **Fill**: a tape print with `taker_side = no` (a taker selling YES) at `yes_price ≤ d`. Fill models
  mirror `MAKER_FILL`: **optimistic** (front of queue) and **pessimistic** with `N ∈ {25, 100}`
  contracts resting ahead. Book depth is absent from the archive, so `N` is an explicit assumption.
- **P&L per filled contract, fee-free**: `+(100 − d)` if the strike settles YES, `−d` if NO.
- **Unfilled quotes earn zero and stay in every denominator.** Per-filled EV may be reported only
  beside per-quoted EV, never instead of it.
- **Cluster unit = calendar day.** Outcome = Kalshi official `result` only.

## PASS / KILL — frozen now, on converging quantities only

Bonferroni over 3 `k` × 4 `T` × 2 fill models = **24 comparisons**; α = 0.05/24 = 0.00208, applied
to the proportion tests (Wilson intervals at the Bonferroni-adjusted level, i.e. 99.79% two-sided).

**PASS** requires ALL, under the **pessimistic `N=25`** model, in ≥1 cell:
1. **The Bonferroni-adjusted (99.79%) Wilson LOWER bound on `P(YES | filled)` exceeds `mean(d)/100`**
   — i.e. profitability per fill is established at the corrected level, not merely estimated
2. **adverse selection does not reverse the edge**: the day-bootstrap 95% CI for
   `P(YES|filled) − P(YES|quoted)` must not have an upper bound below `−1.0` percentage points
3. **n ≥ 500 filled contracts across ≥ 40 distinct days**
4. **fill rate ≥ 5%** of quotes
5. **per-quoted EV > 0** (sign only — no t-statistic, per the power ceiling above)

**KILL** if, in every cell meeting the n floor, the Bonferroni-adjusted Wilson **upper** bound on
`P(YES | filled)` is **below** `mean(d)/100` — i.e. unprofitability per fill is established. This is
written on a proportion, which converges.

**Anything else → INSUFFICIENT.**

## Mandatory anchors (each must hold or the result is void)

- **(a) Primary comparison first.** `P(YES|filled)` vs `P(YES|quoted)` vs break-even `mean(d)/100`,
  per cell, with Wilson intervals and the day-bootstrap CI, **before any EV number appears**.
- **(b) Unfilled quotes in the denominator.** Quote count, fill count, fill rate for every cell.
- **(c) Correct side of the book.** A resting **buy** fills against a taker **sell**. Assert that only
  prints with `taker_side = no` at `yes_price ≤ d` are counted, and hand-work 10 fills from raw tape
  JSON. Counting taker buys would invert the whole study.
- **(d) No look-ahead in placement.** `d` depends only on the candle at or before `T`; assert in code.
- **(e) Composition control.** Report `P(YES|quoted)` re-weighted to the price mix of filled quotes,
  so a mixed-price cell cannot create a spurious gap.
- **(f) Tail risk.** Worst single day's aggregate P&L and max simultaneous long exposure. Buying
  favourites wins many small and loses few large — the mirror of the longshot profile, and the
  losses are the ones that matter.

No bar in this document may move after 2026-10-28. A PASS is necessary-but-not-sufficient; the only
permitted next step is a separately-registered 1-contract live canary.
