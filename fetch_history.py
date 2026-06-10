"""fetch_history.py -- assemble the DEEP historical 15-min dataset (no collector needed).

Sources (all public, read-only):
  * Gamma slugs are PREDICTABLE ({asset}-updown-15m-<window_start>): enumerate every 900s window
    back as far as the series exists (~240 days for BTC) -> resolution + token ids. Batched
    (repeated slug params), ~10 windows/request.
  * CLOB /prices-history (fidelity=1): the Up token's 1-minute price path -- retained even for
    months-old resolved markets (verified).
  * Spot 1m candles: Coinbase Exchange (public, months of depth, reachable from US runners) with
    Binance as fallback -- the spot path + pre-window realized vol. (Settlement uses the
    Chainlink/Binance number; the Coinbase basis is negligible at 1m feature scale.)

Output: hist_<asset>15m.parquet, one row per window:
  ws, res_up, mid_path (15 x 1-min), spot_path (15 x 1-min closes), spot_prev (60 x 1-min closes
  before the open, for decision-time sigma). Consumed by directional_deep.py.

    python fetch_history.py --asset btc --days 60 [--out hist_btc15m.parquet]
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

G = "https://gamma-api.polymarket.com/events"
PH = "https://clob.polymarket.com/prices-history"
BK = "https://api.binance.com/api/v3/klines"
CB = "https://api.exchange.coinbase.com/products/{sym}-USD/candles"
BIN_SYM = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT", "xrp": "XRPUSDT",
           "doge": "DOGEUSDT", "bnb": "BNBUSDT"}


def discover(sess, asset, ws_list):
    """Batched Gamma slug lookup -> {ws: (res_up, up_token)} for closed windows."""
    out = {}
    for i in range(0, len(ws_list), 10):
        chunk = ws_list[i:i + 10]
        params = [("slug", f"{asset}-updown-15m-{w}") for w in chunk]
        for attempt in range(3):
            try:
                evs = sess.get(G, params=params, timeout=15).json()
                break
            except Exception:
                time.sleep(2 * (attempt + 1)); evs = []
        for ev in evs or []:
            try:
                slug = ev.get("slug", ""); w = int(slug.rsplit("-", 1)[1])
                m = ev["markets"][0]
                if not m.get("closed"):
                    continue
                op = m.get("outcomePrices")
                op = json.loads(op) if isinstance(op, str) else op
                res = 1 if float(op[0]) > 0.5 else 0
                tok = str(json.loads(m["clobTokenIds"])[0])
                out[w] = (res, tok)
            except Exception:
                continue
        if i % 500 == 0:
            print(f"  discover: {i}/{len(ws_list)} ({len(out)} closed)", flush=True)
    return out


def price_path(sess, tok, ws):
    """15 x 1-min Up-token prices (NaN-padded by minute index)."""
    try:
        r = sess.get(PH, params={"market": tok, "startTs": ws, "endTs": ws + 900,
                                 "fidelity": 1}, timeout=12).json()
        path = [float("nan")] * 15
        for pt in r.get("history", []):
            k = min(int((pt["t"] - ws) // 60), 14)
            if 0 <= k:
                path[k] = float(pt["p"])
        return path
    except Exception:
        return None


def spot_closes(sess, asset, t0, t1):
    """1m close series covering [t0, t1) -> {minute_ts: close}. Coinbase Exchange primary
    (300 bars/request), Binance fallback (geo-blocked on some runners)."""
    out = {}
    sym = asset.upper()
    t = t0
    while t < t1:
        seg_end = min(t + 300 * 60, t1)
        kl = None
        for attempt in range(3):
            try:
                r = sess.get(CB.format(sym=sym),
                             params={"granularity": 60, "start": t, "end": seg_end}, timeout=15)
                if r.status_code == 200:
                    kl = r.json(); break
            except Exception:
                pass
            time.sleep(1.5 * (attempt + 1))
        if isinstance(kl, list) and kl:
            for c in kl:                      # [time, low, high, open, close, volume]
                out[int(c[0])] = float(c[4])
        t = seg_end
        time.sleep(0.12)
    if out:
        return out
    # fallback: Binance (works outside restricted regions)
    bsym = BIN_SYM.get(asset, f"{sym}USDT")
    t = t0
    while t < t1:
        try:
            kl = sess.get(BK, params={"symbol": bsym, "interval": "1m",
                                      "startTime": t * 1000, "limit": 1000}, timeout=15).json()
        except Exception:
            kl = []
        if not isinstance(kl, list) or not kl:
            break
        for k in kl:
            out[int(k[0] // 1000)] = float(k[4])
        t = int(kl[-1][0] // 1000) + 60
        time.sleep(0.15)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out_path = a.out or f"hist_{a.asset}15m.parquet"
    sess = requests.Session()
    now = int(time.time()); end = now - (now % 900) - 1800
    ws_list = list(range(end - a.days * 86400, end, 900))
    print(f"{a.asset}: enumerating {len(ws_list)} windows over {a.days}d ...", flush=True)
    disc = discover(sess, a.asset, ws_list)
    print(f"closed windows with resolution: {len(disc)}", flush=True)

    print("spot 1m candles (coinbase primary) ...", flush=True)
    spot = spot_closes(sess, a.asset, ws_list[0] - 4500, end + 900)
    print(f"  {len(spot)} bars", flush=True)

    print("CLOB price paths (threaded) ...", flush=True)
    items = sorted(disc.items())
    rows = []
    def fetch_one(item):
        w, (res, tok) = item
        return w, res, price_path(requests.Session(), tok, w)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for w, res, path in ex.map(fetch_one, items):
            done += 1
            if done % 250 == 0:
                print(f"  paths: {done}/{len(items)}", flush=True)
            if path is None or all(np.isnan(path)):
                continue
            sp = [spot.get(w + 60 * k, float("nan")) for k in range(15)]
            spv = [spot.get(w - 60 * (60 - k), float("nan")) for k in range(60)]
            rows.append({"ws": w, "res_up": res, "mid_path": path, "spot_path": sp,
                         "spot_prev": spv})
    df = pd.DataFrame(rows).sort_values("ws")
    df.to_parquet(out_path, index=False)
    print(f"wrote {out_path}: {len(df)} windows "
          f"({df.ws.min()}..{df.ws.max()})", flush=True)


if __name__ == "__main__":
    main()
