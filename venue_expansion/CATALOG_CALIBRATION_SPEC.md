# CATALOG CALIBRATION — pre-registered spec (REGISTERED 2026-10-29, before any outcome is read)

## The gap

`TAIL_PRICING` measured calibration on **one** product family — `KXBTCD`, BTC hourly — and found the
market fair at the executable bid in **27 of 28 longshot cells**. That is the most informative single
measurement this program has produced, and it covers **1 of 9,191 series.**

Everything else closed for reasons specific to its mechanism: weather because the market forecasts
faster than we observe; the determined-early family because the venue designs it out; arbitrage
because the crossings live under 100 ms; market making because adverse selection matches the spread;
incentive pots because they are capital-weighted. **None of those closures says anything about
whether prices are well calibrated anywhere else in the catalog.**

This spec asks the one question that generalises: **is there any corner of Kalshi where the executable
price and the realised frequency differ by more than the fee?**

## Prior, stated honestly so a null is not a surprise

The favourite–longshot bias is best documented in **bookmaker** odds, where a book *sets* prices and
embeds a margin. Kalshi is an **exchange** — prices come from participants, and `TAIL_PRICING` already
found crypto fair. So the prior for finding exploitable miscalibration is **weak**, and the most
likely outcome is a catalog-wide null that closes the mispricing hypothesis generally rather than one
product at a time. That would be a real result and must be reported as plainly as a hit.

Sports is the largest category (**4,067 series**) and the place the bias is most documented in the
literature, so it is the single most interesting stratum — but it is also the most liquid and most
heavily analysed by other participants, which argues the other way.

## The executable rule — non-negotiable, it has invalidated work here twice

Per direction, with `fee = ceil(7·p·(1−p))` cents at the crossing price:

- **Buying YES** executes at **`yes_ask`**. Edge iff `100·f > yes_ask + fee`.
- **Selling YES** executes at **`yes_bid`** (equivalently buying NO at `100 − yes_bid`). Edge iff
  `100·f < yes_bid − fee`.
- **`100 − yes_ask` is never computed.** AST-assert it. No mid prices anywhere.

A market-minute with the relevant side absent (`yes_ask = 0`/absent for a buy, `yes_bid = 0` for a
sell) is **UNTRADEABLE** — counted in the denominator, never priced, never back-filled.

## Design — frozen

- **Universe**: settled Kalshi markets with an official `result` of yes/no and candlestick coverage,
  across the categories **Sports, Politics, Financials, Economics, Climate and Weather, Commodities,
  Crypto**. Crypto is retained as a **replication control** — it must reproduce `TAIL_PRICING`'s
  finding of fairness, or the pipeline is wrong.
- **Sampling, frozen**: sample **whole events** (so every market of an event is priced together,
  preserving its partition structure) in a **seeded shuffled order (seed 20261029), saved and never
  re-sorted**. Report the covered fraction per category and whether it is an exact prefix. Reuse
  `shape_screen.py`'s catalog/probe machinery and `edge_sizing_v2.normalize()` for candles.
- **Entry times, frozen**: `T ∈ {15, 60}` minutes before `close_time`; the **last candle at or before
  `close − T`**. **No best-minute search.**
- **Price buckets, frozen** on the executable price: `{1–2, 3–5, 6–10, 11–20, 21–40, 41–59, 60–79,
  80–89, 90–94, 95–98}` cents. Both directions are evaluated in every bucket.
- **Cluster unit**: the **event** (markets in one event share a single outcome draw), with
  calendar-day clustering also reported. The event is the gate's cluster.
- Outcome = Kalshi official `result` only, never self-computed.

## PASS / KILL — frozen now, on proportions only

Comparisons: 10 buckets × 2 directions × 2 entry times × 7 categories = **280**. Bonferroni
two-sided α = 0.05/280 = **1.786e-4**, so bounds are **99.982%** Wilson intervals.

**No EV t-statistic gate.** `TAIL_PRICING` froze a KILL clause that could never fire and
`MAKER_FILL`/`FAVOURITE_MAKER` ended power-bound; with binary payoffs and event clustering an EV
t-bar is not reachable at catalog sample sizes. Gating on proportions is the lesson applied.

**PASS** requires ALL, in ≥1 category × bucket × direction × T cell:
1. the **99.982% Wilson bound on `f` clears the executable price in the profitable direction** —
   lower bound `> (ask + fee)/100` for a buy, upper bound `< (bid − fee)/100` for a sell
2. **n ≥ 1,000 priced observations across ≥ 100 distinct events and ≥ 20 distinct calendar days**
3. **untradeable fraction ≤ 70%** in that cell
4. **≥ 50% of priced observations have non-zero traded volume** in the entry candle
5. the cell is **not concentrated**: no single event > 5% and no single day > 25% of its observations

**KILL** if, in every cell meeting the n floor in criterion 2, the 99.982% Wilson interval on `f`
**contains** the executable price in both directions — i.e. the catalog is fair everywhere it can be
measured. This is written on a proportion, which converges.

**Anything else → INSUFFICIENT.**

## Mandatory anchors (each must hold or the result is void)

- **(a) Crypto replication control, reported FIRST.** The `KXBTCD` stratum must reproduce
  `TAIL_PRICING`: mean executable bid inside the Wilson interval in the large majority of longshot
  cells. **If it does not, the pipeline is broken and no other number in the report may be believed.**
- **(b) Calibration curves reported whatever the verdict** — realised `f` with Wilson intervals
  against the executable price, per category × bucket × direction × T. This is the scientific content
  and the deliverable even on a KILL.
- **(c) Executable sides only.** AST scan for `100 - *ask` and for any mid-price computation; plus 10
  hand-worked observations per direction re-parsed from raw candle JSON.
- **(d) No outcome in the entry path.** `result` must be unread until the P&L/frequency step;
  AST-assert, with a negative control on a doctored copy that must raise.
- **(e) Partition sanity.** For events that are complete partitions, verify exactly one YES. Report
  any event failing this with its ticker — it means the structure assumed is wrong.
- **(f) Size is not measured.** Candles carry no depth. Report entry-candle volume as an **upper
  bound** and state plainly that realisable size is unknown. Note that
  `yes_bid_size_fp`/`yes_ask_size_fp` exist on **open** markets only, so this gap cannot be
  backfilled.

## Interpretation, frozen in advance

A PASS is **necessary but not sufficient**: it would locate miscalibration, not establish that this
operator can bank it. Queue position, competition and size all remain unmeasured, and
`ARBITRAGE_CLOSED.md` established that participants on this venue act at the same microsecond. The
only permitted next step on a PASS is a separately-registered 1-contract canary.

A catalog-wide KILL is the expected outcome and the more valuable one: it would close the
"prices are wrong somewhere" hypothesis across the venue, rather than one product at a time.

No bar in this document may move after 2026-10-29.
