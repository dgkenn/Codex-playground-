# LADDER ARBITRAGE — pre-registered spec (REGISTERED 2026-10-28, before any price pair is examined)

## Why this is categorically different from all 51 prior studies

Every study in this repo has been a bet on **being right about something**: an outcome (47 weather
studies), a probability (`TAIL_PRICING`), or the cost of immediacy (`MAKER_FILL`). All are now
closed. This one is not a bet at all.

A Kalshi hourly BTC event carries two structures, both verified live 2026-10-28:

- **`KXBTCD`** — **188 threshold strikes** per hour, `strike_type=greater`. `P(BTC > K)` must be
  **non-increasing in K**. Verified on `KXBTCD-26OCT2800`: every strike below the settlement value
  (80,997.54) resolved YES and every strike above it resolved NO, with no interleaving.
- **`KXBTC`** — **100 range markets** per hour, `strike_type=less`, forming a **complete partition**:
  verified exactly 1 of 100 settled YES on `KXBTC-26OCT2800`.

Both structures exist on the **same event hour**. The constraints they impose hold **in every state
of the world**, so a violation is profit that does not depend on forecasting, observing, or being
faster than anyone.

**The core trade (Part A).** For strikes `K1 < K2`, buy `YES(K1)` at its ask and sell `YES(K2)` at
its bid. The position pays, at settlement:

| state | long YES(K1) | short YES(K2) | net |
|---|---|---|---|
| BTC > K2 | +100 | −100 | 0 |
| K1 < BTC ≤ K2 | +100 | 0 | **+100** |
| BTC ≤ K1 | 0 | 0 | 0 |

The payoff is **never negative**. So if the position is opened for a net credit, that credit is
**state-independent profit** and no outcome is needed to establish it. A credit requires
`yes_bid(K2) > yes_ask(K1)` — the ladder quoted *crossed*.

## The fee arithmetic, applied forward instead of rediscovered

`ceil(7·p·(1−p))` has a **1-cent minimum per leg**. This program has now had that arithmetic close
four separate studies, so it is applied *before* testing rather than after:

**An N-leg arbitrage pays ≥ N cents in fees.** Therefore:

- **The 100-leg dutch book on `KXBTC` is dead by arithmetic and will not be tested as a strategy.**
  Buying all 100 legs costs `Σ asks + ~100c` in fees; profit requires `Σ asks < 0`, which is
  impossible. It is reported only as a **diagnostic** of how far the partition sums from 100c, which
  is a useful efficiency measurement and nothing more.
- Only **low-leg-count** arbitrages can survive. This spec tests **2-leg (Part A)** and **3-leg
  (Part C)** constructions and nothing wider.

**Part A net:** `yes_bid(K2) − yes_ask(K1) − fee(ask(K1)) − fee(bid(K2))`, requiring roughly a
**>2c crossing** to clear.

**Part C (cross-series, 3 legs):** a `KXBTC` range `[a,b]` must price as
`P(>a) − P(>b)` from `KXBTCD` on the same hour. Buy the cheaper construction, sell the richer, with
three legs and ~3c of fees.

## The trap that would manufacture a false positive — and the rule against it

A 1-minute candle reports `yes_bid` and `yes_ask` as **open/high/low/close** over that minute. Taking
`yes_bid.high` of one strike and `yes_ask.low` of another **within the same minute** compares two
different instants and is **not a simultaneous observation**. A "crossing" built that way is an
artifact, not an arbitrage. This is the single most likely way for this study to produce a fake
result.

**Frozen rule:** the primary measurement uses **`close` for every leg, in the same minute** — all
legs are then end-of-minute snapshots of the same instant. The `high`/`low` construction is reported
**separately and labelled NON-SIMULTANEOUS**, and **cannot produce a PASS**.

**Tape confirmation is mandatory for any surviving violation.** `GET /markets/trades` carries every
print with `yes_price`, `count_fp`, `taker_side` and a microsecond `created_time` (validated in
`MAKER_FILL`: 22,529 of 22,529 candle-minutes matched tape volume exactly). Every candidate must be
re-checked against the tape, and the report must state how many survive.

## Design — frozen

- **Universe**: the **503 `KXBTCD` hours already cached** in `cache/tail_pricing/` (60 UTC days,
  closes 2026-08-22..10-20) for Parts A and B. Part C additionally needs `KXBTC` candles for the
  same hours, fetched in the **same saved seed-20261027 hour order, never re-sorted**. Report
  coverage as a fraction.
- **Scan**: every minute of every hour for which candles exist; all ordered strike pairs `K1 < K2`
  in Part A. No minute selection, no "best pair" search beyond taking the maximum-net violation per
  minute (which must be reported alongside the count of all violations).
- **Executable sides only**: buy at `yes_ask`, sell at `yes_bid`. **Never mid, never the wrong side.**
  Assert in code that no mid price is computed anywhere.
- **Size is NOT measured.** Candles carry no book depth. Report the minute's traded volume on both
  legs as an **upper bound** and state plainly that realisable size is unknown. A violation with
  zero volume on either leg is counted separately and treated as a doubtful fill.
- **Cluster unit = calendar day** (one BTC regime affects every hour in a day).
- Outcome = Kalshi official `result`, used **only** for the anchor-(b) verification below, never to
  compute P&L.

## PASS / KILL — frozen now

A state-independent arbitrage needs no statistical test of *profitability* — the credit is the
profit. What must be established statistically is that violations **exist, are simultaneous, are
fee-clearing, and carry size**. Bonferroni over 3 parts × 2 simultaneity readings = **6
comparisons**; α = 0.05/6 = 0.00833.

**PASS** requires ALL, in the **`close`-only simultaneous** reading, in ≥1 part:
1. **≥ 100 fee-clearing violations** across **≥ 20 distinct calendar days**
2. **≥ 50% of those violations confirmed against the trade tape** as simultaneously quoted
3. **median net ≥ +2.0c** per 2-leg arbitrage after all legs' fees
4. **≥ 50% of violations have non-zero traded volume on BOTH legs** in the violating minute
5. the violation rate is **not concentrated in one day or one hour** (no single day > 25% of total)

**KILL** if the `close`-only reading yields **zero fee-clearing violations** across the covered
universe, or if **fewer than 10%** of candidates survive tape confirmation (i.e. the apparent
crossings are a candle artifact).

**Anything else → INSUFFICIENT.**

## Mandatory anchors (each must hold or the result is void)

- **(a) No outcome in the P&L path.** The arbitrage credit must be computable with `result` unread.
  Assert via AST scan that the P&L function never references the outcome. *(This is the strongest
  anchor this program has ever had available: if the profit needs the outcome, it is not an
  arbitrage.)*
- **(b) Payoff-dominance proof.** For a sample of ≥20 violations, verify against the **official
  settlement** that the realised payoff was ≥ 0 in every case — i.e. the state table above is
  correct in practice and not just in theory. A single negative realised payoff means the
  construction is wrong.
- **(c) Monotonicity sanity on settled outcomes.** On every covered event, every strike below
  `expiration_value` must settle YES and every strike above must settle NO. Any interleaving means
  the ladder is not the structure assumed. Report violations with tickers.
- **(d) No mid prices, executable sides only.** AST scan; plus 10 hand-worked violations re-parsed
  from raw candle JSON showing the exact `yes_ask` bought and `yes_bid` sold.
- **(e) Simultaneity disclosure.** Report `close`-only and `high`/`low` counts side by side. If the
  `high`/`low` count is large and the `close` count is ~0, say explicitly that the apparent
  opportunity is a within-minute timing artifact — that is a finding, not a failure.
- **(f) Fee provenance.** Show the fee charged on each leg of 10 worked examples, and confirm
  `KXBTCD`/`KXBTC` are `fee_type: quadratic` (taker-only) with `fee_multiplier: 1` as surveyed
  2026-10-27.

No bar in this document may move after 2026-10-28. A PASS is necessary-but-not-sufficient; the only
permitted next step is a separately-registered 1-contract live canary, and the binding unknown after
any PASS is **size**, which this spec explicitly does not measure.
