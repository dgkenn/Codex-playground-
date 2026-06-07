"""Pull TOUCH SIZES (queue depth at best bid/ask) from the pmxt archive, to build a TRUE
queue-model fill backtest (replace the phi assumption with measured depth).

Efficient trick: a price_change with price==best_bid (side BUY) is a bid-touch-size update;
price==best_ask (side SELL) is an ask-touch-size update. Filtering to those gives the exact
touch-size stream (~157k/hr for our tokens vs 66.9M total price_change/hr). Streamed per hour
to parquet (resumable), low memory.

    python fetch_depth.py 2026-04-14T00 2026-04-14T23      # one day (default)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import duckdb
import pandas as pd

from pmxt_archive import URL

OUT = "depth_parts"


def tokens_for_hour(up, dn, h0):
    h1 = h0 + 3600
    u = up[(up.window_start >= h0) & (up.window_start < h1)].asset_id.astype(str).tolist()
    d = dn[(dn.window_start >= h0) & (dn.window_start < h1)].down_asset.astype(str).tolist()
    return u + d


def fetch_hour(con, hour_key, toks, out_path):
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return con.execute(f"SELECT count(*) FROM read_parquet('{out_path}')").fetchone()[0]
    if not toks:
        return 0
    ids = ",".join("'" + a + "'" for a in toks)
    url = URL.format(h=hour_key)
    q = f"""
        COPY (
          SELECT timestamp, asset_id,
                 CAST(best_bid AS DOUBLE) AS best_bid, CAST(best_ask AS DOUBLE) AS best_ask,
                 CAST(price AS DOUBLE) AS price, CAST(size AS DOUBLE) AS size, side
          FROM read_parquet('{url}')
          WHERE asset_id IN ({ids}) AND event_type='price_change'
            AND (price=best_bid OR price=best_ask)
        ) TO '{out_path}' (FORMAT PARQUET);
    """
    try:
        con.execute(q)
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] {hour_key}: {str(e)[:100]}"); return -1
    return con.execute(f"SELECT count(*) FROM read_parquet('{out_path}')").fetchone()[0]


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-04-14T00"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-04-14T23"
    s = datetime.strptime(start, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
    e = datetime.strptime(end, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
    up = pd.read_parquet("up_windows.parquet"); dn = pd.read_parquet("down_map.parquet")
    os.makedirs(OUT, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET enable_progress_bar=false; SET preserve_insertion_order=false; SET memory_limit='8GB'; SET threads=4;")
    h = s; total = 0
    while h <= e:
        hk = h.strftime("%Y-%m-%dT%H")
        toks = tokens_for_hour(up, dn, int(h.timestamp()))
        n = fetch_hour(con, hk, toks, f"{OUT}/depth_{hk}.parquet")
        print(f"  {hk}: {n} touch events ({len(toks)} tokens)", flush=True)
        if n > 0:
            total += n
        h += timedelta(hours=1)
    print(f"DONE: {total} touch events -> {OUT}/")


if __name__ == "__main__":
    main()
