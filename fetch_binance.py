"""Fetch Binance spot 1-second klines into an npz, from the FREE public dumps.

The Binance REST API (api.binance.com) returns HTTP 451 from many hosts, so we
use the official historical dumps at data.binance.vision instead -- one zipped
CSV of 1-second klines per UTC day, no key, no rate limit.

    python fetch_binance.py BTCUSDT 2026-04-14 2026-04-16 btc.npz

writes btc.npz with arrays:  ts (int64, ms UTC, = kline open time),  price (close).
The end date is exclusive (matches the [start, end) convention used elsewhere).
"""
from __future__ import annotations

import io
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone

import numpy as np
import requests

BASE = "https://data.binance.vision/data/spot/daily/klines/{sym}/1s/{sym}-1s-{day}.zip"


def _days(start, end):
    d = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    while d < e:
        yield d.isoformat()
        d += timedelta(days=1)


def _to_ms(v):
    v = int(v)
    # data.binance.vision switched some files to microseconds; normalise to ms.
    return v // 1000 if v > 10**14 else v


def fetch_day(sym, day):
    url = BASE.format(sym=sym, day=day)
    r = requests.get(url, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"{url} -> HTTP {r.status_code}")
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    name = zf.namelist()[0]
    ts, close = [], []
    for line in zf.read(name).decode().splitlines():
        c = line.split(",")
        # openTime, open, high, low, close, volume, closeTime, ...
        ts.append(_to_ms(c[0]))
        close.append(float(c[4]))
    return np.asarray(ts, dtype=np.int64), np.asarray(close, dtype=float)


def main():
    if len(sys.argv) != 5:
        print("usage: fetch_binance.py SYMBOL START(YYYY-MM-DD) END(YYYY-MM-DD,excl) OUT.npz")
        raise SystemExit(2)
    sym, start, end, out = sys.argv[1:]
    all_ts, all_px = [], []
    for day in _days(start, end):
        ts, px = fetch_day(sym, day)
        all_ts.append(ts); all_px.append(px)
        print(f"  {day}: {len(ts)} klines  "
              f"({datetime.fromtimestamp(ts[0]/1000,timezone.utc)} .. "
              f"{datetime.fromtimestamp(ts[-1]/1000,timezone.utc)})")
    ts = np.concatenate(all_ts); px = np.concatenate(all_px)
    order = np.argsort(ts)
    ts, px = ts[order], px[order]
    np.savez(out, ts=ts, price=px)
    print(f"wrote {out}: {len(ts)} points, ts unit = ms (UTC), "
          f"{datetime.fromtimestamp(ts[0]/1000,timezone.utc)} .. "
          f"{datetime.fromtimestamp(ts[-1]/1000,timezone.utc)}")


if __name__ == "__main__":
    main()
