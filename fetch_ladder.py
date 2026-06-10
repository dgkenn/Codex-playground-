"""Discover BTC 'above $K' hourly strike-ladder markets and fetch their YES books,
for strike-ladder arbitrage (A): monotonicity + butterfly/convexity no-arb.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

import pandas as pd
import requests

import pmxt_archive as arch

G = "https://gamma-api.polymarket.com"
HOURS = [f"{h}am-et" for h in [12] + list(range(1, 12))] + \
        [f"{h}pm-et" for h in [12] + list(range(1, 12))]
DATES = ["april-14-2026", "april-15-2026", "april-16-2026"]


def main():
    sess = requests.Session()
    rows = []
    for d in DATES:
        for h in HOURS:
            slug = f"bitcoin-above-on-{d}-{h}"
            try:
                ev = sess.get(G + "/events", params={"slug": slug}, timeout=20).json()
            except Exception:
                ev = None
            if not ev:
                continue
            for m in ev[0].get("markets", []):
                git = m.get("groupItemTitle") or ""
                strike = re.sub(r"[^0-9.]", "", git)
                toks = json.loads(m["clobTokenIds"]) if m.get("clobTokenIds") else []
                outs = json.loads(m["outcomes"]) if m.get("outcomes") else []
                if not strike or not toks:
                    continue
                prices = json.loads(m.get("outcomePrices") or "[]")
                yes_res = (1 if float(prices[0]) > 0.5 else 0) if (m.get("closed") and prices) else None
                rows.append({"expiry": slug, "strike": float(strike),
                             "yes_asset": str(toks[0]), "yes_res": yes_res})
    lad = pd.DataFrame(rows)
    lad.to_parquet("ladder_markets.parquet", index=False)
    print(f"discovered {len(lad)} strike markets across {lad['expiry'].nunique()} expiries "
          f"(median {lad.groupby('expiry').size().median():.0f} strikes/expiry)")

    con = arch.connect()
    keys = arch.hour_keys(datetime(2026, 4, 14, tzinfo=timezone.utc),
                          datetime(2026, 4, 17, tzinfo=timezone.utc))
    pdir = "data_ladder"; os.makedirs(pdir, exist_ok=True)
    ids = lad["yes_asset"].tolist()
    print(f"fetching ladder YES books from {len(keys)} hours ({len(ids)} tokens)...")
    total = 0
    for k in keys:
        n = arch.fetch_hour_to_parquet(con, k, ids, os.path.join(pdir, f"{k}.parquet"))
        total += max(n, 0)
        print(f"  {k}: {n}", flush=True)
    n = arch.merge_parquets(con, f"{pdir}/*.parquet", "ladder_book.parquet")
    print(f"wrote ladder_book.parquet: {n} rows")


if __name__ == "__main__":
    main()
