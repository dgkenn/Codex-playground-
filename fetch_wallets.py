"""Pull wallet-attributed trades (proxyWallet) for all BTC 15m markets from the
free, no-auth Polymarket data-api, for the copy-the-informed-minority test.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

API = "https://data-api.polymarket.com/trades"


def fetch_market(cid, sess):
    out, off = [], 0
    while True:
        j = None
        for attempt in range(4):
            try:
                j = sess.get(API, params={"market": cid, "limit": 500, "offset": off}, timeout=30).json()
                break
            except Exception:
                time.sleep(2 ** attempt)
        if not isinstance(j, list):     # error dict / null -> stop this market
            break
        out += j
        off += 500
        if len(j) < 500 or off > 20000:
            break
    return out


def main():
    w = pd.read_parquet("up_windows.parquet").dropna(subset=["condition_id"])
    sess = requests.Session()
    rows = []
    for i, cid in enumerate(w["condition_id"].unique()):
        for t in fetch_market(cid, sess):
            rows.append((t["proxyWallet"], t["conditionId"], t["asset"], t["side"],
                         float(t["size"]), float(t["price"]), int(t["timestamp"]),
                         int(t.get("outcomeIndex", -1))))
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{w['condition_id'].nunique()} markets, {len(rows)} trades", flush=True)
    df = pd.DataFrame(rows, columns=["wallet", "condition_id", "asset", "side", "size",
                                     "price", "ts", "outcome_index"])
    df.to_parquet("wallet_trades.parquet", index=False)
    print(f"wrote wallet_trades.parquet: {len(df)} trades, {df['wallet'].nunique()} wallets")


if __name__ == "__main__":
    main()
