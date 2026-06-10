"""Fetch executed trade prints (last_trade_price) for the discovered Up tokens.

Needed by the maker simulation (maker_sim.py): a resting order fills only when a
trade crosses its level, so we need the trade tape, not just top-of-book.

    python fetch_trades.py --start 2026-04-14T00 --end 2026-04-17T00

Reuses up_windows.parquet for the asset_ids. Writes up_trades.parquet
(timestamp, asset_id, price, size, side).
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

import pandas as pd

import pmxt_archive as arch


def _parse(h):
    return datetime.strptime(h, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--windows", default="up_windows.parquet")
    ap.add_argument("--out", default="up_trades.parquet")
    a = ap.parse_args()

    win = pd.read_parquet(a.windows)
    asset_ids = win["asset_id"].astype(str).tolist()
    con = arch.connect()
    keys = arch.hour_keys(_parse(a.start), _parse(a.end))
    part_dir = "data_trades"
    os.makedirs(part_dir, exist_ok=True)
    print(f"=== fetch_trades.py {a.start}..{a.end} : {len(keys)} hours, {len(asset_ids)} tokens ===")
    total = 0
    for k in keys:
        out = os.path.join(part_dir, f"{k}.parquet")
        n = arch.fetch_trades_hour_to_parquet(con, k, asset_ids, out)
        total += max(n, 0)
        print(f"    {k}: {n} trades", flush=True)
    if total == 0:
        raise SystemExit("STOP: no trade prints returned.")
    con.execute(
        f"COPY (SELECT timestamp, asset_id, CAST(price AS DOUBLE) price, "
        f"CAST(size AS DOUBLE) size, side FROM read_parquet('{part_dir}/*.parquet') "
        f"ORDER BY timestamp) TO '{a.out}' (FORMAT PARQUET);")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{a.out}')").fetchone()[0]
    print(f"\nwrote {a.out}: {n} trade prints")
    import pyarrow.parquet as pq
    for f in pq.ParquetFile(a.out).schema_arrow:
        print(f"    {f.name}: {f.type}")


if __name__ == "__main__":
    main()
