"""fetch_kalshi.py -- deep history for Kalshi's 15-min crypto up/down series (KX{BTC,ETH,SOL,XRP}15M).

Kalshi's public (NO auth) API serves, for every SETTLED 15-minute market:
  * the result (yes/no) and metadata        GET /markets?series_ticker=..&status=settled
  * per-minute candlesticks with YES bid/ask OHLC + traded volume + open interest
                                            GET /series/{s}/markets/{ticker}/candlesticks
Series launched ~May 2026 -> ~3,000 windows/asset and growing 96/day.

Output hist_kalshi_<asset>15m.parquet, one row per window:
  ws, res_up, mid_path/bid_path/ask_path/vol_path (15 x 1-min), spot_path (15), spot_prev (60)
(mid/spot/res columns match fetch_history's shape so directional_deep.py runs UNCHANGED; the
bid/ask/vol columns feed the maker-economics study.)

    python fetch_kalshi.py --asset btc --days 30
"""
from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from fetch_history import spot_closes

B = "https://api.elections.kalshi.com/trade-api/v2"


def list_settled(sess, series, days):
    """All settled markets of the series newer than `days` -> [(ws, ticker, res_up)]."""
    out = []
    cursor = None
    min_ts = int(time.time()) - days * 86400
    while True:
        params = {"series_ticker": series, "status": "settled", "limit": 200,
                  "min_close_ts": min_ts}
        if cursor:
            params["cursor"] = cursor
        for attempt in range(3):
            try:
                d = sess.get(f"{B}/markets", params=params, timeout=15).json()
                break
            except Exception:
                time.sleep(2 * (attempt + 1)); d = {}
        ms = d.get("markets") or []
        for m in ms:
            res = m.get("result")
            if res not in ("yes", "no"):
                continue
            try:
                ct = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00"))
                ws = int(ct.timestamp()) - 900           # close = window end
            except Exception:
                continue
            out.append((ws, m["ticker"], 1 if res == "yes" else 0))
        cursor = d.get("cursor")
        if not cursor or not ms:
            break
        time.sleep(0.1)
    return sorted(set(out))


def candles(sess, series, ticker, ws):
    """15 x 1-min (mid, bid, ask, vol) from the public candlestick endpoint."""
    try:
        d = sess.get(f"{B}/series/{series}/markets/{ticker}/candlesticks",
                     params={"start_ts": ws - 60, "end_ts": ws + 900,
                             "period_interval": 1}, timeout=12).json()
    except Exception:
        return None
    mid = [float("nan")] * 15; bid = [float("nan")] * 15
    ask = [float("nan")] * 15; vol = [0.0] * 15
    for c in d.get("candlesticks") or []:
        k = int((int(c["end_period_ts"]) - ws) // 60) - 1   # end_ts of minute k+1
        if not (0 <= k < 15):
            continue
        try:
            b = c.get("yes_bid") or {}; a = c.get("yes_ask") or {}
            bc = b.get("close_dollars"); ac = a.get("close_dollars")
            if bc is not None:
                bid[k] = float(bc)
            if ac is not None:
                ask[k] = float(ac)
            if bc is not None and ac is not None:
                mid[k] = (float(bc) + float(ac)) / 2
            vol[k] = float(c.get("volume_fp") or c.get("volume") or 0)
        except Exception:
            continue
    if all(np.isnan(mid)):
        return None
    return mid, bid, ask, vol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    series = f"KX{a.asset.upper()}15M"
    out_path = a.out or f"hist_kalshi_{a.asset}15m.parquet"
    sess = requests.Session()
    print(f"{series}: listing settled markets ({a.days}d) ...", flush=True)
    mkts = list_settled(sess, series, a.days)
    print(f"  {len(mkts)} settled windows", flush=True)

    print("spot 1m candles (coinbase) ...", flush=True)
    t0 = min(w for w, _, _ in mkts); t1 = max(w for w, _, _ in mkts) + 900
    spot = spot_closes(sess, a.asset, t0 - 4500, t1)
    print(f"  {len(spot)} bars", flush=True)

    rows = []
    def one(item):
        w, tk, res = item
        return w, res, candles(requests.Session(), series, tk, w)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for w, res, c in ex.map(one, mkts):
            done += 1
            if done % 250 == 0:
                print(f"  candles: {done}/{len(mkts)}", flush=True)
            if c is None:
                continue
            mid, bid, ask, vol = c
            sp = [spot.get(w + 60 * k, float("nan")) for k in range(15)]
            spv = [spot.get(w - 60 * (60 - k), float("nan")) for k in range(60)]
            rows.append({"ws": w, "res_up": res, "mid_path": mid, "bid_path": bid,
                         "ask_path": ask, "vol_path": vol, "spot_path": sp, "spot_prev": spv})
    df = pd.DataFrame(rows).sort_values("ws")
    df.to_parquet(out_path, index=False)
    print(f"wrote {out_path}: {len(df)} windows", flush=True)


if __name__ == "__main__":
    main()
