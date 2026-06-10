"""Discover ETH/SOL/XRP 15m UP tokens and fetch their top-of-book, for the
cross-sectional relative-value (S2) and market-to-market lead-lag (S3) tests.
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
COINS = ["eth", "sol", "xrp"]


def parse(h):
    return datetime.strptime(h, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


def main():
    start, end = parse("2026-04-14T00"), parse("2026-04-17T00")
    t0, t1 = int(start.timestamp()), int(end.timestamp())
    sess = requests.Session()
    rows = []
    for coin in COINS:
        for ts in range(t0 - (t0 % WINDOW_S), t1, WINDOW_S):
            try:
                ev = sess.get(G + "/events", params={"slug": f"{coin}-updown-15m-{ts}"}, timeout=20).json()
            except Exception:
                ev = None
            if not ev:
                continue
            m = ev[0]["markets"][0]
            outs = json.loads(m["outcomes"]); toks = json.loads(m["clobTokenIds"])
            if str(outs[0]).lower() not in ("up", "yes"):
                continue
            prices = json.loads(m.get("outcomePrices") or "[]")
            rup = (1 if float(prices[0]) > 0.5 else 0) if (m.get("closed") and prices) else None
            rows.append({"coin": coin, "window_start": ts, "window_end": ts + WINDOW_S,
                         "asset_id": str(toks[0]), "resolved_up": rup})
    win = pd.DataFrame(rows)
    win.to_parquet("alt_windows.parquet", index=False)
    print(f"discovered {len(win)} alt up tokens ({win.groupby('coin').size().to_dict()})")

    con = arch.connect()
    keys = arch.hour_keys(start, end)
    pdir = "data_alt"; os.makedirs(pdir, exist_ok=True)
    ids = win["asset_id"].tolist()
    print(f"fetching alt books from {len(keys)} hours...")
    total = 0
    for k in keys:
        n = arch.fetch_hour_to_parquet(con, k, ids, os.path.join(pdir, f"{k}.parquet"))
        total += max(n, 0)
        print(f"  {k}: {n}", flush=True)
    n = arch.merge_parquets(con, f"{pdir}/*.parquet", "alt_book.parquet")
    print(f"wrote alt_book.parquet: {n} rows")


if __name__ == "__main__":
    main()
