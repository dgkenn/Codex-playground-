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

from datetime import datetime, timedelta, timezone

import duckdb
import pandas as pd

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
    return con


def fetch_top_of_book(con, hour_key, asset_ids):
    """Return top-of-book rows for asset_ids in one hourly file (best-effort).

    Missing/unreadable files return an empty frame so a gap doesn't abort a run.
    """
    url = URL.format(h=hour_key)
    ids = ",".join("'" + a + "'" for a in asset_ids)
    evs = ",".join("'" + e + "'" for e in TOP_OF_BOOK_EVENTS)
    q = f"""
        SELECT timestamp, asset_id, best_bid, best_ask, fee_rate_bps
        FROM read_parquet('{url}')
        WHERE asset_id IN ({ids})
          AND event_type IN ({evs})
          AND best_bid IS NOT NULL AND best_ask IS NOT NULL
    """
    try:
        df = con.execute(q).df()
    except Exception as e:                       # noqa: BLE001 -- report and skip
        print(f"    [warn] {hour_key}: {str(e)[:120]}")
        return pd.DataFrame(columns=["timestamp", "asset_id", "best_bid", "best_ask", "fee_rate_bps"])
    return df
