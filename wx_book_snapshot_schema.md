# wx_book_snapshots.jsonl — schema (v1)

Structured order-book snapshots of **near-lock candidate rungs** on Kalshi KXHIGH*/KXLOWT* weather
ladders, sampled at fire-window times by `wx_capacity_probe.py --snapshot` (the kwx-depthprobe
workflow runs it every 30 min through the US afternoon). This is the dataset behind two studies:

1. **DEPTH_CAP calibration** — DEPTH_CAP=25 (the assumed max contracts one fire can absorb, THE
   lever on the monthly capacity ceiling) was a Tier-1 text-log proxy. `depth_at_or_below_98c`
   here is the real fillable number; `wx_capacity_probe.py --report` aggregates it.
2. **Maker study (sibling unit)** — full two-sided ladders (`yes_bid_levels`/`yes_ask_levels`)
   let a maker sleeve estimate queue position, spread capture, and post-vs-take EV.

One JSON object per line, one line per near-lock rung per sweep. Rows are intentionally NOT
deduped across sweeps: the time series through the fire window is the point. Consumers must
tolerate torn/partial trailing lines (append-only file committed from CI).

**Near-lock candidate** = the rung's ladder-quote yes ask is in `[50c, 98c]`: the market already
leans YES (temp approaching/at the strike — the books a mechanical-lock fire will hit) but the
rung is still buyable under the bot's `MAX_PAY_CENTS=98` pay cap.

## Fields

| field | type | meaning |
|---|---|---|
| `schema_v` | int | schema version; bump on ANY breaking change (currently `1`) |
| `ts_utc` | str | ISO-8601 UTC capture time; identical for every row of one sweep (acts as the sweep id) |
| `series` | str | Kalshi series ticker, e.g. `KXHIGHDEN`, `KXLOWTDEN` |
| `event_ticker` | str | city-day event, e.g. `KXHIGHDEN-26JUL19` |
| `ticker` | str | rung market ticker, e.g. `KXHIGHDEN-26JUL19-B90.5` |
| `station` | str | METAR/ASOS station backing settlement, e.g. `KDEN` |
| `kind` | str | `"max"` (daily high) or `"min"` (daily low) |
| `lst_date` | str | market's local-standard-time date, `YYYY-MM-DD` |
| `floor_strike` | float\|null | rung floor in degF (`null` = open-ended below) |
| `cap_strike` | float\|null | rung cap in degF (`null` = open-ended above) |
| `status` | str\|null | market status from the event payload (`active`, ...) |
| `volume` | int\|null | traded contracts (from `volume` or `volume_fp`; `null` if API omits both) |
| `open_interest` | int\|null | open interest (from `open_interest` or `open_interest_fp`) |
| `quote_yes_ask_c` | int | ladder-quote top-of-book YES ask, cents (what gated the near-lock filter) |
| `quote_yes_bid_c` | int\|null | ladder-quote top-of-book YES bid, cents |
| `yes_bid_levels` | [[int,int],...] | FULL ladder of resting YES bids `[price_c, count]`, best-first (price desc) |
| `yes_ask_levels` | [[int,int],...] | FULL ladder of YES asks `[price_c, count]`, best-first (price asc). Derived: a resting NO bid at `q` **is** a YES ask at `100-q` |
| `best_yes_bid` | int\|null | `yes_bid_levels[0][0]` (`null` when that side is empty) |
| `best_yes_ask` | int\|null | `yes_ask_levels[0][0]` (`null` when that side is empty) |
| `depth_at_or_below_98c` | int | sum of `yes_ask_levels` counts at price ≤ 98c — contracts a taker fire could buy right now without walking past the pay cap |
| `running_extreme_f` | float\|null | **(v2)** observed running max/min (degF) for this station/day at capture time, via the same read-only feed `kwx_runner` uses to gate live fires (`feed_for_station(station).running_extreme(...)`) — one feed call per (station, lst_date, kind), reused across every rung of that event. `null` on feed error/outage. This is the field the maker study needs to decide "approaching lock" and place a hypothetical resting bid; without it a row is still valid FILL EVIDENCE (later-ask observations) but can never trigger a placement. |

**schema_v history**: `1` (initial) → `2` (2026-07-20, adds `running_extreme_f`; the maker study was
otherwise permanently blocked — every v1 row had it absent, so 0 hypothetical placements could ever be made
regardless of row count). v1 rows already committed are NOT backfilled; readers must tolerate its absence.

## Guarantees & caveats

- **Both book encodings handled**: Kalshi has served legacy `orderbook` (int cents) and current
  `orderbook_fp` (dollar strings); the logger normalizes both to integer cents/counts.
- An **empty book still logs a row** (empty level lists, depth 0) — the share of empty near-lock
  books is itself DEPTH_CAP evidence. Transient book-fetch failures are skipped, not logged.
- Prices are integer cents `1..99`; counts are integer contracts.
- Read-only public data; no auth, no orders. Produced/committed by `.github/workflows/kwx-depthprobe.yml`.
- **Retention**: `wx_capacity_probe.py --prune-days N` (default 21) rewrites this file to drop rows older
  than N days, keeping committed-file growth bounded now that sweeps run denser during the US-afternoon
  lock window (17:00–01:00 UTC) via `--snapshot-loop`. Both studies only need a rolling 1-2 weeks.
