#!/usr/bin/env python3
"""Fetch, for every VALIDATION-window market, the real trade nearest-after each lead's simulated
entry timestamp. Two leads -> two trade lookups per market."""
import json, os, sys, time, ssl, calendar, urllib.request, urllib.error, datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
CA = "/root/.ccr/ca-bundle.crt"
CTX = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"

CITIES = {
    "KXHIGHDEN": (-7,), "KXHIGHMIA": (-5,), "KXHIGHTSEA": (-8,), "KXHIGHTPHX": (-7,),
}

VAL_START = dt.date(2026, 6, 1)
VAL_END = dt.date(2026, 7, 20)

def _get(url, timeout=25, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as h:
                return json.loads(h.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"trades": []}
            if i == retries - 1:
                return {"__error__": str(e)}
            time.sleep(0.4 * (i + 1))
        except Exception as e:
            if i == retries - 1:
                return {"__error__": str(e)}
            time.sleep(0.4 * (i + 1))
    return {"__error__": "exhausted"}

def entry_utc(settle_date, offset_hours, lead):
    """offset_hours: fixed STANDARD-time UTC offset (e.g. -7 for Denver). local = UTC + offset.
    dayahead entry: previous local evening 21:00. samemorning entry: same-day local 09:00."""
    if lead == "dayahead":
        local_dt = dt.datetime(settle_date.year, settle_date.month, settle_date.day, 21, 0, 0) - dt.timedelta(days=1)
    else:
        local_dt = dt.datetime(settle_date.year, settle_date.month, settle_date.day, 9, 0, 0)
    utc_dt = local_dt - dt.timedelta(hours=offset_hours)  # UTC = local - offset
    return utc_dt

def main():
    events = json.load(open(os.path.join(HERE, "raw_events.json")))

    # build list of (series, date, ticker, floor, cap, result) for VALIDATION window only
    markets = []
    for series, byday in events.items():
        off = CITIES[series][0]
        for dstr, r in byday.items():
            d = dt.date.fromisoformat(dstr)
            if not (VAL_START <= d <= VAL_END):
                continue
            if not r or r.get("__error__"):
                continue
            ev = r.get("event", {})
            for m in ev.get("markets", []):
                if m.get("status") != "finalized" or m.get("result") not in ("yes", "no"):
                    continue
                markets.append({
                    "series": series, "date": dstr, "ticker": m["ticker"],
                    "floor_strike": m.get("floor_strike"), "cap_strike": m.get("cap_strike"),
                    "result": m["result"], "offset": off,
                })
    print(f"VALIDATION finalized markets: {len(markets)}", file=sys.stderr)

    def fetch_one(mrec, lead):
        d = dt.date.fromisoformat(mrec["date"])
        t_entry = entry_utc(d, mrec["offset"], lead)
        t0 = calendar.timegm(t_entry.utctimetuple())
        t1 = t0 + 8 * 3600  # look up to 8h forward for the first real trade after entry
        url = f"{KBASE}/markets/trades?ticker={mrec['ticker']}&min_ts={t0}&max_ts={t1}&limit=200"
        d_ = _get(url)
        trades = d_.get("trades", []) if isinstance(d_, dict) else []
        if not trades:
            return (mrec["ticker"], lead, None)
        # pick min created_time (closest to/after entry)
        best = min(trades, key=lambda tr: tr["created_time"])
        return (mrec["ticker"], lead, {
            "yes_price": float(best["yes_price_dollars"]), "no_price": float(best["no_price_dollars"]),
            "created_time": best["created_time"], "taker_side": best.get("taker_side"),
        })

    results = {}
    tasks = [(m, lead) for m in markets for lead in ("dayahead", "samemorning")]
    print(f"trade lookups to do: {len(tasks)}", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = [ex.submit(fetch_one, m, lead) for m, lead in tasks]
        n = 0
        for f in as_completed(futs):
            tk, lead, val = f.result()
            results.setdefault(tk, {})[lead] = val
            n += 1
            if n % 200 == 0:
                print(f"  trades: {n}/{len(tasks)}", file=sys.stderr)

    json.dump({"markets": markets, "entries": results},
               open(os.path.join(HERE, "raw_trades.json"), "w"))
    print("done", file=sys.stderr)

if __name__ == "__main__":
    main()
