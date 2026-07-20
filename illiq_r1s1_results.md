# Spec 1: Mention-Open Base-Rate Anchor — Backtest Results

**Verdict: INCONCLUSIVE** (pre-registered stop condition triggered — not a pass, no goalpost moved)

## Data reality check (the headline finding)

The pre-registration assumed a census of **KXFEDMENTION = 45 settled markets / 12 events**
and **KXHANNITYMENTION = 29 settled / 2 events**. Real data pulled from
`api.elections.kalshi.com/trade-api/v2` (uncapped `/markets`, `/events`,
`/markets/trades`, no auth) contradicts the FEDMENTION assumption:

- Kalshi's public `/markets` endpoint only returns markets for the **two most
  recent events per series** (current + most recently finalized). Older events
  still appear in `/events` (13 FEDMENTION events back to 2025-01) but querying
  `/markets?event_ticker=<old event>` returns **0 markets** for every event
  older than the most recent. This is a retention/archival limit of the public
  API, not a filter bug on our end (verified with explicit `event_ticker`
  queries per event, and with `min_close_ts`/`max_close_ts`, which the API
  rejects as a bad request on this endpoint).
- Retrievable data: **KXFEDMENTION = 45 finalized markets, but all 45 belong to
  a single event** (`KXFEDMENTION-26JUN`, broadcast 2026-06-17). Zero older
  FEDMENTION events are retrievable.
- **KXHANNITYMENTION = 29 finalized markets / 2 events**
  (`KXHANNITYMENTION-26MAY19`, 13 mkts; `KXHANNITYMENTION-26MAY21`, 16 mkts) —
  this one matches the pre-registration.
- **Total distinct broadcast-event-days retrievable across both series: 3.**
  This is already below the pre-registered minimum of 8 validation event-days,
  before a single trade is simulated.

Full uncapped trade histories were pulled for all 74 finalized markets (sum
2,000+ trade prints); no data was capped or subsampled.

## Fit / validation split

Chronological by event, first `floor(0.4 * n_events)` events = fit, remainder
= validation (pre-registered rule).

- 3 events total → fit = 1 event (`KXHANNITYMENTION-26MAY19`), validation = 2
  events (`KXHANNITYMENTION-26MAY21`, `KXFEDMENTION-26JUN`).

## Signal construction (executed exactly as pre-registered)

- Entry = first trade print of each market.
- `p̂` = expanding-window fraction of prior **same-series** settled markets
  resolving YES, using only markets settled strictly before the entry
  timestamp (no lookahead), spanning full chronological history (not
  restricted to the fit set).
- Because both series' earliest available event has **zero prior settled
  history** in the retrievable data, `p̂` is undefined for:
  - all 45 KXFEDMENTION-26JUN markets (no earlier FEDMENTION event is
    retrievable at all),
  - all 13 KXHANNITYMENTION-26MAY19 markets (it is the earliest retrievable
    HANNITYMENTION event).
- `p̂` is defined only for the 16 markets of `KXHANNITYMENTION-26MAY21`, using
  the 13 settled outcomes of `26MAY19` as the entire expanding window
  (1 YES / 13 settled → `p̂ ≈ 0.077` for every entry in that event).
- **Consequence: zero fit-set entries exist for any θ ∈ {10,15,20}¢** — the
  fit set (`26MAY19`) never has a defined `p̂`. Theta selection therefore had
  no fit-set signal to select on; the script documents this and falls back
  to the pre-registered grid's median point (θ = 15¢) as the
  least-arbitrary default. This fallback is itself evidence the funnel's
  data assumptions don't hold at this sample size — not a passing result.

## Validation-set results (θ = 15¢ fallback)

| Metric | Value |
|---|---|
| n (validation entries) | **16** |
| Distinct validation event-days | **1** (`KXHANNITYMENTION-26MAY21`) |
| Wins | 11 |
| Win rate | 0.6875 |
| Wilson 95% CI (win rate) | [0.444, 0.858] |
| Avg price paid | $0.461 |
| Avg fee | $0.0194 |
| Fee-inclusive breakeven win rate | 0.4806 |
| **Mean net EV/contract** | **+$0.207** |
| Event-day-clustered t-stat | NaN (1 cluster — variance undefined) |
| One-sided p (raw) | NaN |
| One-sided p (Bonferroni ×10) | NaN |

The apparent +$0.21/contract edge and 68.75% win rate are **not statistically
usable**: with all 16 entries clustered on a single broadcast day, the
day-clustered t-test has 1 cluster and no between-cluster variance — no
p-value can be computed, by construction. Every one of the 16 entries fired
the same side (NO) because the entire signal collapsed to "the previous
show's 13-word sample had a low hit rate (1/13), so bet NO on every word this
show too" — this is a naive low-base-rate prior estimated from n=13, not a
demonstrated cross-broadcast anchoring effect.

## Adverse-selection check (mandatory, pre-registered)

**INSUFFICIENT DATA.** All 16 markets with a defined `p̂` fired the signal
(none were left over as a same-series, same-price-bucket "non-fired" control
group), so the required fired-vs-non-fired matched comparison cannot be
computed. Per pre-registration this check must pass for a PASS verdict; it
cannot even be attempted here, which is an independent reason this cannot be
called a pass.

## Pre-registered minimum-n gate

| Requirement | Bar | Actual | Met? |
|---|---|---|---|
| Validation entries | ≥ 30 | 16 | **No** |
| Distinct validation event-days | ≥ 8 | 1 | **No** |

Per pre-registration: *"Min n: ≥30 validation entries over ≥8 distinct
broadcast-event days, else INCONCLUSIVE."* Both conditions fail. Verdict is
therefore fixed at **INCONCLUSIVE** — pre-registered, not a post-hoc call.

## Headline numbers

- **n = 16** validation entries, 1 distinct event-day (need ≥30 / ≥8)
- **Win rate = 68.75%** (Wilson 95% CI [0.444, 0.858])
- **Mean net EV/contract = +$0.207** (not statistically testable — 1 cluster)
- **t-stat / p-value: undefined (NaN)** — cannot compute with 1 cluster
- **Adverse-selection check: could not be run** (no non-fired control markets)
- **Honest capacity: $0/mo.** Verdict is INCONCLUSIVE per pre-registered
  gate; per house rules a null/inconclusive result is not converted to a
  capacity estimate or a sleeve. No paper-only sleeve is proposed from this
  spec as-is.

## The one thing that most worries me

**The public Kalshi API silently truncates historical market listings to the
most recent 1–2 events per series**, and this is easy to miss: `/events`
still lists all 13 historical FEDMENTION events with correct titles and
dates, giving the false impression that the full census is queryable, while
`/markets?event_ticker=<old event>` just returns an empty list for anything
older than the most recent finalized event — no error, no warning, count=0.
A less careful pull would have silently treated "0 markets returned" as "0
markets existed" or, worse, only pulled the single most-recent event without
ever checking event count, and reported a confident PASS/FAIL on an n=16,
single-cluster sample that happens to look good (spuriously, an 11/16 win
rate here is well within the noise of a base rate estimated from only 13
prior markets — swap 1 result in that n=13 window and p̂ moves by 7.7 points,
which would flip several of the 16 signals). Any future run of this spec
needs either (a) a data source with genuine multi-year settled history for
these series, or (b) to accept that these two series simply do not have
enough independent broadcast-days on the public API yet to ever clear the
pre-registered n≥30/≥8-days bar, and should be retired from this funnel
rather than re-attempted on the same stunted data.

## Files

- `backtest_spec1_mention_anchor.py` — runnable script (re-run after
  re-fetching trades; cache directory deleted after this run per
  instructions)
- `results.json` — full machine-readable results incl. all 16 fired trades
- `results.md` — this file
