"""Discover BTC 15m DOWN tokens (clobTokenIds[1]) and fetch their top-of-book, for
the overround / near-riskless arbitrage test (Up_ask+Down_ask<1, or Up_bid+Down_bid>1).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd
import requests

import pmxt_archive as arch

G = "https://gamma-api.polymarket.com"
WINDOW_S = 900


def parse(h):
    return datetime.strptime(h, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


def main():
    start, end = parse("2026-04-14T00"), parse("2026-04-17T00")
    t0, t1 = int(start.timestamp()), int(end.timestamp())
    sess = requests.Session()
    rows = []
    for ts in range(t0 - (t0 % WINDOW_S), t1, WINDOW_S):
        try:
            ev = sess.get(G + "/events", params={"slug": f"btc-updown-15m-{ts}"}, timeout=20).json()
        except Exception:
            ev = None
        if not ev:
            continue
        m = ev[0]["markets"][0]
        toks = json.loads(m["clobTokenIds"])
        rows.append({"window_start": ts, "window_end": ts + WINDOW_S,
                     "down_asset": str(toks[1])})
    dmap = pd.DataFrame(rows)
    dmap.to_parquet("down_map.parquet", index=False)
    print(f"discovered {len(dmap)} down tokens")

    con = arch.connect()
    keys = arch.hour_keys(start, end)
    pdir = "data_down"; os.makedirs(pdir, exist_ok=True)
    ids = dmap["down_asset"].tolist()
    print(f"fetching down books from {len(keys)} hours...")
    total = 0
    for k in keys:
        n = arch.fetch_hour_to_parquet(con, k, ids, os.path.join(pdir, f"{k}.parquet"))
        total += max(n, 0)
        print(f"  {k}: {n}", flush=True)
    n = arch.merge_parquets(con, f"{pdir}/*.parquet", "down_book.parquet")
    print(f"wrote down_book.parquet: {n} rows")


if __name__ == "__main__":
    main()
