# DATA SOURCES — verified register of historical market data (2026-07-25)

Every claim below was checked with a real query on 2026-07-25, not taken from a dataset card.
Reproduce: `python venue_expansion/probe_datasets.py` (writes `out/datasets_probe.json`).

**Headline finding: `kx_history.py` has been reading 9 of the archive's 16 trade shards. 44% of the
Kalshi trade archive — roughly 70M trades — has been invisible to every backtest in this repo.**

---

## 1. TrevorJS/kalshi-trades (HF) — the primary archive, ALREADY WIRED IN

Used by `kx_history.py` on the live branch. CC-BY-4.0, ~2.6k downloads/30d, last modified
2026-01-30.

| | verified |
|---|---|
| Trade shards | **16** (`trades-0000..0015`), ~10M rows each → **~160M trades** |
| Market shards | 4 (`markets-0000..0003`) = 5M+5M+5M+2,464,713 = **17,464,713 markets** |
| Coverage | **2021-06-30 → 2026-01-28** (verified min/max `created_time`) |
| Trades schema | `trade_id, ticker, count, yes_price, no_price, taker_side, created_time` |
| Markets schema | `ticker, event_ticker, market_type, title, yes_sub_title, no_sub_title, status, yes_bid, yes_ask, no_bid, no_ask, last_price, volume, volume_24h, open_interest, result, created_time, open_time, close_time` |

The 17.5M-market figure in the public description checks out exactly. Date range checks out.

### 1a. THE BUG — 7 shards are invisible

```python
# kx_history.py:83-84
N_MARKET_SHARDS = 4   # markets-0000..0003 as of 2026-07-20; bump if the archive grows   <- correct
N_TRADE_SHARDS  = 9   # trades-0000..0008                                                 <- WRONG, there are 16
```

`trades-0009` through `trades-0015` exist and each holds 10M rows. Any study that enumerated
shards (which is all of them — see 1b) has been running on a 56% sample of the tape while
believing it had the whole archive.

This is worth re-checking against **graveyard entry #31** (favorite-longshot Spec 2), which was
scored `deployable=NO` purely because "the candidates × 172M-trade join did not complete in
economy-mode budget". The 172M figure implies a full-archive intent that the shard constant never
delivered. It does not resurrect the edge — Specs 1 and 3 of that funnel completed and were
negative — but the stated reason for the kill was infrastructure, not evidence.

### 1b. Globs do not work — you must enumerate

```
read_parquet('.../trades-*.parquet')  ->  HTTP 404
```
DuckDB cannot glob a generic HTTPS path (`SET allow_asterisks_in_http_paths=true` only permits the
literal `*` in the URL, which then 404s on HF). So `kx_history.TRADES('*')` is dead code, and every
caller falls back to explicit shard numbers — which is exactly how the 9-vs-16 gap stayed hidden.
Either enumerate all 16 explicitly, or switch to `hf://datasets/TrevorJS/kalshi-trades/trades-*.parquet`.

### 1c. Sharding is NOT time-partitioned and NOT a clean ticker range — read this before subsampling

Measured, per shard (`out/shard_ordering.json`) — **every** shard spans essentially the full ticker
alphabet, and distinct-ticker counts vary 34× between shards:

| shard | distinct tickers | ticker range |
|---|---:|---|
| 0000 | 331,443 | `-23MAR-T2` .. `WRECSS-26-UK` |
| 0001–0005 | 306,948–411,184 | `AMAZONFTC-29DEC31` .. `WRECSS-26-UK` (all five identical endpoints) |
| 0006 | 71,566 | `538APPROVE-22NOV30-B42.4` .. `USCLIMATE-2025` |
| 0007 | 282,407 | `538APPROVE-22SEP28-B43.2` .. `KXNBAGAME-25NOV09OKCMEM-MEM` |
| 0008 | **11,996** | `538APPROVE-23JUL05-B40.4` .. `KXNCAAFGAME-25OCT18CONNBC-BC` |
| 0009 | 37,361 | `538APPROVE-23OCT04-B40.5` .. `KXNFLGAME-25OCT05NEBUF-BUF` |
| 0010 | 20,001 | `CPICORE-23JUN-T0.2` .. `KXOSCARPIC-25-EP` |
| 0011 | 49,283 | `538APPROVE-24JUN26-B38.4` .. `MCDAWNTRAIL-89` |
| 0012–0015 | 189,384–354,323 | `538APPROVEMIN-…`/`AAAGASW-…`/`ACPI-…`/`AILEGISLATION-…` .. `ZYNBAN-24`/`WTAX-25-DEC31` |

Plus:
- Shards 0000–0006 reach **2026-01**; shards 0007+ stop at **2025-11-25**.
- A single high-volume market's tape is **split across shards**: `KXNFLGAME-26JAN17BUFDEN-BUF` has
  4,199 trades in shard 0002 and 206,564 in shard 0003.

The wildly uneven ticker counts (0008 holds 11,996; 0005 holds 411,184) mean the shards are not even
a uniform random partition — so "some shards" is never a defensible stand-in for "the archive".

**Consequence: taking K of N shards is not a time slice and not a clean market cohort — it is a
partial, non-random sample of each market's own trade tape, with an end date that depends on which
shards you picked.** That silently breaks anything order-dependent: first-trade-after-signal entry,
VWAP, fill sequencing, "N real trading days per series". `PER_SERIES_SCAN.md` (graveyard #34) ran on
"3/9 archive shards = 13–22 real trading days per series" — that day count is a sampling artifact of
this layout, not a property of the market.

Rule going forward: **for any per-market or order-sensitive work, read all 16 shards for the tickers
of interest** (predicate-pushdown on `ticker` makes this cheap — you are not downloading 160M rows).
Only use a shard subset for population-level scans where per-market completeness does not matter.

---

## 2. thomaswmitch/kalshi-prediction-markets-betting (HF) — cross-check source

MIT licensed, 2 parquet files, **5,076,511 trades** verified (2,538,256 + 2,538,255).

Schema: `trade_id, ticker, count, created_time(VARCHAR), yes_price, no_price, taker_side, market_ticker`.

Two notes:
- It is **~3% the size of TrevorJS**, not a comparable alternative. Its value here is as an
  **independent second source for the same trades** — the single most useful thing it can do for
  this repo is confirm or refute a TrevorJS-derived result on the overlapping window, since every
  study in the graveyard rests on one archive.
- It carries `market_ticker` **in addition to** `ticker`, which TrevorJS's trade table lacks. That
  distinction is exactly the `^[A-Z]+` **family-conflation bug** named in graveyard #34 as one of the
  two artifacts that killed the per-series scan. Worth checking whether this field makes the
  series→market mapping unambiguous without the regexp.
- `created_time` is a **string** here, not a timestamp — cast before comparing.

---

## 3. Kalshi official API — the only source for RECENT data

The archive ends **2026-01-28**. Today is **2026-07-25**, so there is a **~6-month hole** the HF
datasets cannot fill — including the entire window the live bot and paper sleeves have been running.

Filling it (verified working this session, public, no auth):

```
GET /trade-api/v2/series/{series}/markets/{ticker}/candlesticks
    ?start_ts=&end_ts=&period_interval=1
-> per-minute yes_bid / yes_ask / price OHLC + open_interest + volume
```

**This endpoint returns real 1-minute bid AND ask history.** It is what made the forecast-sleeve
audit possible (`PAPER_TRADER_AUDIT.md`): it priced 261 paper trades at their true executable cost
at each signal timestamp, with zero look-ahead. Measured weather-rung spreads: median 1c, p75 2c.

Also verified working:
- `GET /trade-api/v2/markets/{ticker}` → `result` field = **Kalshi's official settlement outcome**.
  This is settlement ground truth and it is the check that killed the forecast sleeve (14.2% of its
  self-scored outcomes were wrong). **Any study that decides outcomes itself must be reconciled
  against this field.** Cheap: ~0.12s/ticker.
- `GET /trade-api/v2/markets?series_ticker=…&status=…` for the live catalog.

**Standing rule: archive for history, candlesticks + official `result` for anything after
2026-01-28 and for every settlement claim.**

---

## 4. Aggregate/convenience sources (not research-grade)

| Source | Status | Use |
|---|---|---|
| kalshidata.com | reachable (307 redirect) | Daily volume/trade-count dashboards. Aggregates only — no tape |
| kingsets.com | reachable (200) | CSV/BigQuery convenience access to Kalshi + Polymarket; Kalshi ingest reportedly partial. Useful only if you want BigQuery-side joins instead of DuckDB |
| kalshi.com/market-data | official | Summary metrics |

None of these replace the parquet archive or the candlestick API for backtesting. Their value is
monitoring, not research. **Unverified in this session:** neither kingsets' Kalshi completeness nor
kalshidata's coverage was probed beyond an HTTP reachability check — do not cite coverage numbers
from them without checking first.

---

## 5. Polymarket (for the venue-expansion work)

From the prior studies (`ref/pmkt_*.md`), verified reachable this session:
- `gamma-api.polymarket.com` — catalog/events (200)
- `clob.polymarket.com` — live order book (200)
- `prices-history` returns **last-trade/midpoint only** — there is **no public historical order-book
  endpoint**, so Polymarket EV numbers rest on a spread proxy, unlike Kalshi where candlesticks give
  the real bid/ask. This asymmetry matters when comparing the venues' measured edges: Kalshi numbers
  are measured, Polymarket numbers are proxied.

---

## 6. Action items this register generates

1. **Fix `N_TRADE_SHARDS = 9` → `16`** in `kx_history.py`, and make it derive from the HF file
   listing rather than a hardcoded constant so it cannot silently drift again.
2. **Re-run any per-market/order-sensitive study on all 16 shards** — the shard-subset hazard in
   §1c applies to `PER_SERIES_SCAN.md` and to the favorite-longshot join.
3. **Add the official-`result` reconciliation** (§3) as a standard step in the study-audit checklist;
   it is the check that caught a 14.2% outcome error the same day it was first applied.
4. Use thomaswmitch as an **independent replication source** for at least one graveyard result, so
   the program's conclusions do not all rest on a single archive.
