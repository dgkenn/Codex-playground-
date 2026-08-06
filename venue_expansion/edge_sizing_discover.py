#!/usr/bin/env python3
"""edge_sizing_discover.py -- discovery-only pass for edge_sizing.py: enumerate every KXHIGH*/KXLOW*
series from the Kalshi series catalog, then list every SETTLED market in each series with close_time
in the frozen window [2026-05-01, 2026-08-04]. No candlesticks here (cheap: series list ~1 call,
markets list ~1-3 calls/series via server-side min_close_ts/max_close_ts filtering). Writes the full
population to cache/edge_sizing/population.json so edge_sizing.py can sample/iterate without re-listing.
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "edge_sizing")
os.makedirs(CACHE, exist_ok=True)

API = "https://api.elections.kalshi.com/trade-api/v2"
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; kwx-edge-sizing/1.0)"}

WINDOW_START = dt.datetime(2026, 5, 1, tzinfo=dt.timezone.utc)
WINDOW_END = dt.datetime(2026, 8, 4, 23, 59, 59, tzinfo=dt.timezone.utc)


def get_json(url, retries=6, backoff=1.6, timeout=30):
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                return {"__404__": True}
            if e.code not in (429, 500, 502, 503, 504):
                return {"__err__": f"HTTP {e.code}"}
            time.sleep(backoff * (a + 1))
        except Exception as e:
            last = e
            time.sleep(backoff * (a + 1))
    return {"__err__": f"{type(last).__name__}: {last}"}


def fetch_series_catalog():
    p = os.path.join(CACHE, "series_catalog.json")
    if os.path.exists(p):
        return json.load(open(p))
    out = []
    cursor = ""
    while True:
        url = f"{API}/series?limit=200" + (f"&cursor={cursor}" if cursor else "")
        d = get_json(url)
        if not isinstance(d, dict) or "series" not in d:
            break
        out.extend(d["series"])
        cursor = d.get("cursor") or ""
        if not cursor:
            break
        time.sleep(0.3)
    json.dump(out, open(p, "w"))
    return out


def wx_series_tickers(catalog):
    wx = [s for s in catalog if s.get("category") == "Climate and Weather"]
    kx = sorted({s["ticker"] for s in wx if s["ticker"].startswith("KXHIGH") or s["ticker"].startswith("KXLOW")})
    return kx


def fetch_settled_markets(series_ticker, start_ts, end_ts):
    key = os.path.join(CACHE, f"markets_{series_ticker}.json")
    if os.path.exists(key):
        return json.load(open(key))
    out = []
    cursor = ""
    while True:
        url = (f"{API}/markets?series_ticker={series_ticker}&status=settled&limit=1000"
               f"&min_close_ts={start_ts}&max_close_ts={end_ts}" + (f"&cursor={cursor}" if cursor else ""))
        d = get_json(url)
        if not isinstance(d, dict) or "markets" not in d:
            out_err = {"__err__": d.get("__err__", "unknown") if isinstance(d, dict) else "unknown"}
            json.dump({"error": out_err, "markets": out}, open(key + ".partial", "w"))
            print(f"  ERROR listing {series_ticker}: {out_err}", file=sys.stderr)
            break
        out.extend(d["markets"])
        cursor = d.get("cursor") or ""
        if not cursor:
            break
        time.sleep(0.3)
    slim = [{"ticker": m["ticker"], "event_ticker": m.get("event_ticker"), "close_time": m.get("close_time"),
             "open_time": m.get("open_time"), "result": m.get("result"), "status": m.get("status"),
             "series_ticker": series_ticker, "floor_strike": m.get("floor_strike"),
             "strike_type": m.get("strike_type")} for m in out]
    json.dump(slim, open(key, "w"))
    return slim


def main():
    catalog = fetch_series_catalog()
    kx = wx_series_tickers(catalog)
    print(f"discovered {len(kx)} KXHIGH*/KXLOW* series in Climate and Weather category")
    start_ts = int(WINDOW_START.timestamp())
    end_ts = int(WINDOW_END.timestamp())
    pop = []
    per_series_counts = {}
    for i, s in enumerate(kx, 1):
        mkts = fetch_settled_markets(s, start_ts, end_ts)
        per_series_counts[s] = len(mkts)
        pop.extend(mkts)
        print(f"  [{i}/{len(kx)}] {s}: {len(mkts)} settled markets in window (running total {len(pop)})")
        time.sleep(0.2)
    json.dump({"series": kx, "per_series_counts": per_series_counts, "n_total": len(pop), "markets": pop},
               open(os.path.join(CACHE, "population.json"), "w"))
    with_result = [m for m in pop if m.get("result") in ("yes", "no")]
    print(f"\nTOTAL settled markets in window: {len(pop)}")
    print(f"  with yes/no result: {len(with_result)}")
    print(f"  other/void/null result: {len(pop) - len(with_result)}")


if __name__ == "__main__":
    main()
