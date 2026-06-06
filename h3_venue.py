"""H3: broaden the venue. Does a different BTC up/down timeframe have a winner?

Cheapest rigorous lens: realized-trade maker/taker economics (every trade has a
real maker counterparty; no fill model), window-clustered (the honest unit). If
neither side shows a clustered edge here either, the negative is venue-robust.

    python h3_venue.py --tf 5m --step 300 --start 2026-04-14T00 --end 2026-04-17T00
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import duckdb
import numpy as np
import pandas as pd
import requests

import pmxt_archive as arch
from fairvalue import fee_per_share

G = "https://gamma-api.polymarket.com"
FEE_BPS = 1000.0


def _parse(h):
    return datetime.strptime(h, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


def discover(tf, step, start_dt, end_dt, sess):
    t0 = int(start_dt.timestamp()); t1 = int(end_dt.timestamp())
    rows, missing = [], 0
    for ts in range(t0 - (t0 % step), t1, step):
        slug = f"btc-updown-{tf}-{ts}"
        try:
            ev = sess.get(G + "/events", params={"slug": slug}, timeout=20).json()
        except Exception:
            ev = None
        if not ev:
            missing += 1; continue
        m = ev[0]["markets"][0]
        outs = json.loads(m["outcomes"]); toks = json.loads(m["clobTokenIds"])
        if str(outs[0]).lower() not in ("up", "yes"):
            raise SystemExit(f"STOP: outcome order {outs} for {slug}")
        prices = json.loads(m.get("outcomePrices") or "[]")
        rup = (1 if float(prices[0]) > 0.5 else 0) if (m.get("closed") and prices) else None
        rows.append({"window_start": ts, "window_end": ts + step,
                     "asset_id": str(toks[0]), "resolved_up": rup})
    df = pd.DataFrame(rows)
    print(f"  discovered {len(df)} {tf} windows (missing {missing})")
    return df


def clustered_t(per_window):
    a = per_window.to_numpy()
    n = len(a); m = a.mean(); s = a.std(ddof=1) if n > 1 else np.nan
    return n, m, (m / s * np.sqrt(n) if s and s > 0 else np.nan)


def analyse(trades_path, win, step):
    con = duckdb.connect()
    win_path = "_h3_win.parquet"; win.to_parquet(win_path, index=False)
    df = con.execute(f"""
        SELECT epoch_ms(t.timestamp)/1000.0 - w.window_start AS t_into,
               w.window_end - epoch_ms(t.timestamp)/1000.0 AS tau,
               t.price, t.size, t.side, w.window_start, w.resolved_up
        FROM read_parquet('{trades_path}') t
        JOIN read_parquet('{win_path}') w ON t.asset_id=w.asset_id
        WHERE w.resolved_up IS NOT NULL
    """).df()
    df = df[(df["t_into"] >= 0) & (df["t_into"] < step)].reset_index(drop=True)
    sell = df["side"] == "SELL"
    df["maker"] = np.where(sell, df["resolved_up"] - df["price"], df["price"] - df["resolved_up"])
    df["taker_net"] = -df["maker"] - fee_per_share(df["price"].to_numpy(), FEE_BPS)
    print(f"  {len(df)} trades across {df['window_start'].nunique()} resolved windows")

    print("  --- window-clustered (honest unit) ---")
    for nm, col in [("MAKER (no fee)", "maker"), ("taker net (10% fee)", "taker_net")]:
        per = df.groupby("window_start").apply(
            lambda x: np.average(x[col], weights=x["size"]), include_groups=False)
        n, m, t = clustered_t(per)
        pooled = np.average(df[col], weights=df["size"])
        print(f"    {nm:22}: n_win={n}  per-win mean={m:+.4f} t={t:+.2f}  pooled size-wtd={pooled:+.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m"); ap.add_argument("--step", type=int, default=300)
    ap.add_argument("--start", required=True); ap.add_argument("--end", required=True)
    a = ap.parse_args()
    sd, ed = _parse(a.start), _parse(a.end)
    print(f"=== H3 venue: BTC {a.tf} up/down  [{sd}..{ed}) ===")

    win_file = f"win_{a.tf}.parquet"
    if os.path.exists(win_file):
        win = pd.read_parquet(win_file); print(f"  reuse {win_file}: {len(win)} windows")
    else:
        win = discover(a.tf, a.step, sd, ed, requests.Session())
        win.to_parquet(win_file, index=False)
    asset_ids = win["asset_id"].astype(str).tolist()

    con = arch.connect()
    keys = arch.hour_keys(sd, _parse(a.end))
    pdir = f"data_trades_{a.tf}"; os.makedirs(pdir, exist_ok=True)
    print(f"  fetching trades from {len(keys)} hours...")
    total = 0
    for k in keys:
        n = arch.fetch_trades_hour_to_parquet(con, k, asset_ids, os.path.join(pdir, f"{k}.parquet"))
        total += max(n, 0)
    out = f"up_trades_{a.tf}.parquet"
    con.execute(f"COPY (SELECT timestamp, asset_id, CAST(price AS DOUBLE) price, "
                f"CAST(size AS DOUBLE) size, side FROM read_parquet('{pdir}/*.parquet')) "
                f"TO '{out}' (FORMAT PARQUET);")
    print(f"  wrote {out}: {total} trades")
    analyse(out, win, a.step)


if __name__ == "__main__":
    main()
