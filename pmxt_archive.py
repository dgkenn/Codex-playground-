"""Read the FREE pmxt v2 Polymarket order-book archive over HTTP with DuckDB.

The archive (https://archive.pmxt.dev, powered by pmxt -- https://github.com/pmxt-dev/pmxt)
publishes one Parquet file per UTC hour at:

    https://r2v2.pmxt.dev/polymarket_orderbook_<YYYY-MM-DDTHH>.parquet

Each file is event-level (NOT a single hourly snapshot): tens of millions of rows
across all Polymarket markets, columns include
    timestamp (ms, UTC), asset_id (CLOB token id, string), event_type,
    best_bid, best_ask (decimal), fee_rate_bps, bids/asks (JSON), price/size/side.

We pull only top-of-book for a given set of "Up" token asset_ids using DuckDB's
httpfs reader, which projects just the columns we need and reads byte-ranges, so
we never download the full ~300-500 MB/hour files. CC-BY-4.0 data.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import duckdb

URL = "https://r2v2.pmxt.dev/polymarket_orderbook_{h}.parquet"
TOP_OF_BOOK_EVENTS = ("price_change", "book")     # carry best_bid/best_ask


def hour_keys(start_dt, end_dt):
    """UTC hour strings YYYY-MM-DDTHH for [start_dt, end_dt) inclusive of the end hour."""
    h = start_dt.replace(minute=0, second=0, microsecond=0)
    end = end_dt
    keys = []
    while h <= end:
        keys.append(h.strftime("%Y-%m-%dT%H"))
        h += timedelta(hours=1)
    return keys


def connect():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET enable_progress_bar=false;")
    # Stream to disk; never materialise the full result in memory (avoids OOM on
    # the ~29M-row, 70-char-asset_id join).
    con.execute("SET preserve_insertion_order=false;")
    con.execute("SET memory_limit='10GB';")
    con.execute("SET threads=4;")
    return con


def _id_filter(asset_ids):
    ids = ",".join("'" + a + "'" for a in asset_ids)
    evs = ",".join("'" + e + "'" for e in TOP_OF_BOOK_EVENTS)
    return ids, evs


def fetch_hour_to_parquet(con, hour_key, asset_ids, out_path):
    """COPY one hour's top-of-book for asset_ids straight to a local parquet.

    Returns row count, or -1 if the hourly file is missing/unreadable (so a gap
    doesn't abort the whole run). Resumable: an existing non-empty out_path is
    reused.
    """
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        try:
            return con.execute(f"SELECT count(*) FROM read_parquet('{out_path}')").fetchone()[0]
        except Exception:
            pass
    url = URL.format(h=hour_key)
    ids, evs = _id_filter(asset_ids)
    q = f"""
        COPY (
            SELECT timestamp, asset_id, best_bid, best_ask, fee_rate_bps
            FROM read_parquet('{url}')
            WHERE asset_id IN ({ids})
              AND event_type IN ({evs})
              AND best_bid IS NOT NULL AND best_ask IS NOT NULL
        ) TO '{out_path}' (FORMAT PARQUET);
    """
    try:
        con.execute(q)
    except Exception as e:                       # noqa: BLE001 -- report and skip
        print(f"    [warn] {hour_key}: {str(e)[:120]}")
        return -1
    return con.execute(f"SELECT count(*) FROM read_parquet('{out_path}')").fetchone()[0]


def merge_parquets(con, glob_path, out_path):
    """Merge per-hour parquets into one, dropping exact-duplicate top-of-book rows
    (same ts/asset/bid/ask), streaming through DuckDB (low memory)."""
    # Cast decimal best_bid/best_ask to DOUBLE so downstream pandas reads floats,
    # not 27M Python Decimal objects (which would blow memory).
    con.execute(
        f"COPY (SELECT DISTINCT timestamp, asset_id, "
        f"       CAST(best_bid AS DOUBLE) AS best_bid, CAST(best_ask AS DOUBLE) AS best_ask, "
        f"       fee_rate_bps "
        f"FROM read_parquet('{glob_path}') ORDER BY timestamp) "
        f"TO '{out_path}' (FORMAT PARQUET);")
    return con.execute(f"SELECT count(*) FROM read_parquet('{out_path}')").fetchone()[0]


def trade_print_fee(con, hour_key, asset_ids):
    """Median fee_rate_bps from trade prints (fee is null on top-of-book rows)."""
    url = URL.format(h=hour_key)
    ids = ",".join("'" + a + "'" for a in asset_ids[:32])
    try:
        v = con.execute(
            f"SELECT median(fee_rate_bps) FROM read_parquet('{url}') "
            f"WHERE asset_id IN ({ids}) AND event_type='last_trade_price' "
            f"AND fee_rate_bps IS NOT NULL").fetchone()[0]
        return float(v) if v is not None else None
    except Exception:
        return None
