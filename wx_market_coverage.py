#!/usr/bin/env python3
"""wx_market_coverage.py -- are we trading every ACTIVE Kalshi daily-CLI temperature market? (volume check)

The cleanest way to grow volume at the SAME edge and SAME risk is to trade more cities of the identical
product. This enumerates Kalshi's live "Climate and Weather" daily high/low temp series, keeps only those
with OPEN events (deprecated series have none), and flags any active one the bot doesn't cover -- a free
same-EV volume add. Run it periodically: if Kalshi lists a new city, this catches it. Read-only public API.

Finding on 2026-07-19: we cover all 20 active daily cities (high+low). The 13 "uncovered" series (KXLOW*
without the T, KXHIGHHOU vs our KXHIGHTHOU, etc.) all have 0 open events = deprecated naming variants. The
one hourly temp series (KXHIGHNYD) settles on The Weather Company, not NWS CLI -> our lock edge can't track
it. So the daily-CLI edge is volume-MAXED on market count; the remaining volume levers are DEPTH_CAP (fill
more per fire if books are deep -- see kwx-depthprobe) and the paid Synoptic 1-min feed (~2x fires).
"""
import json, os, ssl, urllib.request, urllib.parse
import kwx_runner as R

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KB = "https://api.elections.kalshi.com/trade-api/v2"


def _get(u, to=25):
    try:
        return json.load(urllib.request.urlopen(
            urllib.request.Request(u, headers={"Accept": "application/json"}), timeout=to, context=_CTX))
    except Exception as e:
        return {"__err__": type(e).__name__}


def main():
    ours = set(R.CITY.keys()) | set(R.CITY_LOW_SERIES.values())
    d = _get(f"{KB}/series?category={urllib.parse.quote('Climate and Weather')}")
    sers = d.get("series", [])
    temp = [s for s in sers if s["ticker"].startswith(("KXHIGH", "KXLOW")) and s.get("frequency") == "daily"]
    print(f"Kalshi daily temp series: {len(temp)} | we trade: {len(ours)}\n")
    active_missing = []
    for s in temp:
        t = s["ticker"]
        if t in ours:
            continue
        ev = _get(f"{KB}/events?series_ticker={t}&status=open&limit=1")
        n_open = len(ev.get("events", [])) if "__err__" not in ev else 0
        tag = "ACTIVE -- NOT TRADED (add it!)" if n_open > 0 else "deprecated (0 open events)"
        if n_open > 0:
            active_missing.append(t)
        print(f"  {t:>16} | open_events={n_open} | {s.get('title','')[:38]:38} | {tag}")
    print()
    if active_missing:
        print(f"*** {len(active_missing)} ACTIVE series we should ADD for free same-EV volume: {active_missing}")
    else:
        print("All ACTIVE daily-CLI temp cities are covered -- no free market volume to add (as of last run).")
        print("Remaining volume levers: DEPTH_CAP (kwx-depthprobe) + Synoptic 1-min feed (paid, ~2x fires).")


if __name__ == "__main__":
    main()
