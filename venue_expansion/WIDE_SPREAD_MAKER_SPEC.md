# WIDE-SPREAD MAKER — pre-registered spec (REGISTERED 2026-10-29, before any fill is measured)

## The accident in the program's design

Both maker studies ran on `KXBTCD` — BTC hourly. Looking back at the fee survey and the calibration
sweep together, **that was the hardest possible case and we picked it first by accident:**

- BTC hourlies are the **tightest, most competitive** books on the venue. `ARBITRAGE_CLOSED.md` found
  participants taking two legs at the **same microsecond** there.
- `MAKER_FILL`/`FAVOURITE_MAKER` consequently measured adverse selection eating essentially the whole
  spread, because the spread was ~1–3c to begin with.
- Meanwhile `CATALOG_CALIBRATION` measured **enormous** spreads elsewhere. Economics: buy at ask 70c
  against a realised 13%; sell at bid 28c against a realised 80%. Sports: ask 71c against 33%. Those
  gaps are the spread, and on a **taker** they are a cost.

**On a maker they are the revenue.** And the fee survey established that **9,029 of 9,191 series are
`fee_type: quadratic` — taker-only, no maker fee.** So a resting quote on a wide-spread product pays
nothing and stands to capture several times the 1–3c that BTC hourlies offered.

This is the direct extension of the only thread this program has not closed.

## Why it will probably still fail, stated before measuring

Wide spreads usually mean **thin flow** — and the two failure modes are opposite and both fatal:

1. **No fills.** A wide quote nobody crosses earns zero. The 12 zero-fee series are the limit case:
   **0 of 200 order books carried a single resting order.** Wide spread, no counterparty, no business.
2. **Worse adverse selection.** In an illiquid book, the rare person who trades is disproportionately
   someone who knows something. The fill-conditional loss rate could be *higher* than the 1.1–2.3
   ratios measured on liquid BTC hourlies, not lower.

So the real question is whether a **sweet spot** exists: enough flow to fill, enough spread to pay,
and adverse selection that does not consume the difference. That is an empirical question with a
plausible negative answer, which is why it is being asked with frozen bars rather than built.

## Product selection — mechanical, to prevent cherry-picking

The selection rule is frozen and arithmetic. **No "best product" search.** From the non-crypto
categories (Sports, Politics, Financials, Economics, Climate and Weather, Commodities, Elections —
**Elections included, correcting its omission from `CATALOG_CALIBRATION_SPEC`**):

Include a series iff, over its settled markets in the window:
1. **≥ 50 settled markets** with official `result` and candlestick coverage, AND
2. **median quoted spread (`yes_ask − yes_bid`) ≥ 5c** at T=15 among minutes with **both sides
   quoted**, AND
3. **median entry-candle traded volume > 0** — i.e. the book actually trades.

Criterion 3 is the one that excludes the zero-fee graveyard. Report every series that passes, every
series excluded, and which criterion excluded it. Rank the passing set by nothing — all of them are
tested, and the Bonferroni correction is over all of them.

## Design — frozen

- **Universe**: settled markets of the passing series, closing in the widest window the API serves.
  Outcome = Kalshi official `result` only.
- **Quote placement, frozen**: at `T ∈ {15, 60}` minutes before close, rest **both**:
  - a **sell on YES** at `yes_bid + k`, and
  - a **buy on YES** at `yes_ask − k`,
  for `k ∈ {1, 2}`, each held to close, each requiring both sides quoted at placement. One quote per
  market-T-side. **No re-quoting, no cancels, no best-k or best-minute search.**
- **Fill**: from the microsecond tape (`GET /markets/trades`). A resting **sell** fills on a taker
  **buy** (`taker_side = "yes"`) at `yes_price ≥` our ask; a resting **buy** fills on a taker **sell**
  (`taker_side = "no"`) at `yes_price ≤` our bid. `FAVOURITE_MAKER` verified this convention at
  **100.0%** across 129,539 prints — reuse it, and **do not copy a side blind** (getting it backwards
  inverts the study).
- **Fill models**: optimistic (front of queue) and pessimistic `N ∈ {25, 100}` resting ahead. Depth is
  absent historically, so `N` is an explicit assumption.
- **P&L, fee-free**: a filled sell at `a` pays `+a` if NO else `−(100 − a)`; a filled buy at `d` pays
  `+(100 − d)` if YES else `−d`.
- **Unfilled quotes earn zero and stay in every denominator.**
- **Cluster unit = the event** (markets in one event share one outcome draw), with day clustering also
  reported. The event is the gate's cluster.
- **Sampling**: seeded shuffle over **events** (seed 20261029), saved, never re-sorted. Report the
  covered fraction per series and whether it is an exact prefix.

## PASS / KILL — frozen now, on converging quantities only

Bonferroni over (passing series) × 2 `k` × 2 `T` × 2 sides × 2 fill models; the exact comparison count
is fixed once the mechanical selection runs and must be stated in the report **before** any gate is
evaluated. Bounds are Wilson intervals at the Bonferroni-adjusted level.

**No EV t-statistic gate.** This is the fourth spec in a row to say so, because three of mine froze
gates that could not fire. Gates are on proportions.

**PASS** requires ALL, under the **pessimistic `N=25`** model, in ≥1 cell:
1. the **Bonferroni-adjusted Wilson bound on the fill-conditional outcome rate clears break-even** —
   for a sell, upper bound on `P(YES|filled)` below `a/100`; for a buy, lower bound on `P(YES|filled)`
   above `d/100`
2. **fill rate ≥ 5%** of quotes
3. **n ≥ 500 filled contracts across ≥ 100 distinct events and ≥ 20 distinct days**
4. **per-quoted EV > 0** by sign
5. **no single event > 5%** and **no single day > 25%** of the cell's fills

**KILL** if, in every cell meeting the n floor, the Bonferroni-adjusted Wilson bound **fails to clear
break-even in the profitable direction.** *(Stated as a one-sided failure-to-clear, NOT as two-sided
containment — `CATALOG_CALIBRATION`'s KILL was unfireable precisely because spread and tick structure
break containment automatically. That is the corrected form.)*

**Anything else → INSUFFICIENT.**

## Mandatory anchors (each must hold or the result is void)

- **(a) Adverse selection first.** `P(YES|filled)` vs `P(YES|quoted)` vs break-even, per cell, with
  Wilson intervals and a day/event bootstrap, **before any EV number appears.**
- **(b) Unfilled quotes in the denominator.** Quote, fill and fill-rate counts per cell.
- **(c) Correct taker side per direction.** Assert both mappings; hand-work 10 fills per side from raw
  tape JSON.
- **(d) No look-ahead, no outcome in placement.** AST-assert with **negative controls on doctored
  copies that must raise** (this caught four real defects in `CATALOG_CALIBRATION`).
- **(e) Both-sides-quoted requirement.** A quote anchored on an absent side is void. Note that an
  empty ask prints as **`100c`, not `0`** — the trap `CATALOG_CALIBRATION` found.
- **(f) Flow vs spread, reported jointly.** For every passing series give median spread, median
  volume, fill rate and the adverse-selection ratio in one table. This is the sweet-spot question and
  the deliverable even on a KILL.
- **(g) Size not measured.** Candles carry no depth; `yes_bid_size_fp`/`yes_ask_size_fp` exist on
  **open** markets only, so it cannot be backfilled. Volume is an upper bound.

No bar in this document may move after 2026-10-29. A PASS is necessary-but-not-sufficient; the only
permitted next step is a separately-registered 1-contract canary.
