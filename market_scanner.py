#!/usr/bin/env python3
"""market_scanner.py -- venue-wide niche scanner for Kalshi market-making opportunities.

The validated engine (kalshi_trader.py / BOX_PLAYBOOK.md) is a settlement-hedged maker-box
harvester on KXBTC15M/KXETH15M. This script asks the next question: where ELSE on the whole
Kalshi venue does the same "rest both sides, capture the spread" shape look attractive?

For every currently-open market it records ticker/series/category, close_time, yes/no top-of-
book bid & ask, spread (in ticks), top-of-book depth, 24h volume, and open interest -- then
rolls those up per SERIES (median spread in ticks, median depth, total volume, market count,
hours-to-close spread) and ranks series by (median_spread_ticks x daily volume): wide spread x
real volume x thin depth is exactly the maker_box opportunity shape, just possibly on a
different underlying/series.

Data source: Kalshi's PUBLIC market data API -- no auth needed for market/orderbook reads (see
kalshi_preflight.py's chk_market()/chk_latency() and kalshi_trader.py's discover()/get_book(),
both unauthenticated GETs against BASE = https://api.elections.kalshi.com/trade-api/v2).

Batching: rather than paginating raw GET /markets (which is ~99.9% dominated by hundreds of
thousands of auto-generated KXMVE* combinatorial "multivariate event" markets with zero real
liquidity -- confirmed by manual probe before writing this) and then hitting /markets/{t}/
orderbook per market (way too many round trips for a polite ~2-3 minute run), this scanner uses
the batch endpoint GET /events?status=open&with_nested_markets=true. Each page returns events
(which already carry series_ticker + category) with every nested OPEN market embedded, INCLUDING
its top-of-book bid/ask/size/volume/open-interest -- so one paginated call sequence (~35-45
pages at limit=200, paced with a politeness sleep) is enough for the whole venue; no per-market
orderbook fetch required. The KXMVE* combinatorial junk does not appear in this status=open
event listing at all, so the output is naturally clean.

Usage:
    python market_scanner.py [outdir] [--top N]

Writes:  <outdir>/venue_scan_<YYYY-MM-DD>.jsonl.gz  (one gzip-JSON-lines row per liquid-enough
         market; appended to, so re-runs same day accumulate rather than clobber)
Prints:  a ranked opportunity table (top N series by opportunity_score).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"  # public, unauthenticated (matches
                                                          # kalshi_preflight.py / kalshi_trader.py)
PAGE_LIMIT = 200        # events per page (max the API accepts for /events)
PAGE_SLEEP_S = 1.2      # politeness delay between pages (observed venue needs ~35-45 pages)
MAX_PAGES = 150         # safety valve well above the observed page count
REQUEST_TIMEOUT = 20
DEFAULT_TICK = 0.01     # Kalshi's standard cent tick; overridden per-market via price_ranges


def f(x, default=0.0):
    """Kalshi's public API returns *_dollars/*_fp fields as strings; coerce defensively."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def tick_size_for(price_ranges, price):
    """Kalshi markets can have variable tick size by price band (e.g. deci-cent 0.001 near 0/1,
    cent 0.01 in the 0.10-0.90 body). Look up the band containing `price`; fall back to 1 cent."""
    for band in price_ranges or []:
        lo, hi, step = f(band.get("start")), f(band.get("end")), f(band.get("step"))
        if step > 0 and lo - 1e-9 <= price <= hi + 1e-9:
            return step
    return DEFAULT_TICK


def fetch_open_events(sess):
    """Paginate GET /events?status=open&with_nested_markets=true -- see module docstring for why
    this (not raw /markets) is the batch endpoint of choice here."""
    events = []
    cursor = None
    page = 0
    while page < MAX_PAGES:
        params = {"status": "open", "limit": PAGE_LIMIT, "with_nested_markets": "true"}
        if cursor:
            params["cursor"] = cursor
        try:
            r = sess.get(f"{BASE}/events", params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            d = r.json()
        except Exception as e:  # noqa: BLE001 -- keep scanning best-effort, log and stop
            print(f"  [warn] page {page + 1} fetch failed: {type(e).__name__}: {e}",
                  file=sys.stderr)
            break
        batch = d.get("events") or []
        events.extend(batch)
        page += 1
        cursor = d.get("cursor")
        print(f"  page {page}: +{len(batch)} events (total {len(events)})", flush=True)
        if not cursor or not batch:
            break
        time.sleep(PAGE_SLEEP_S)
    return events


def is_liquid_enough(m):
    """Real two-sided quote (not a degenerate 0/1 dead market) AND some evidence of actual
    trading interest (24h volume, lifetime volume, or open interest > 0)."""
    yb, ya = f(m.get("yes_bid_dollars")), f(m.get("yes_ask_dollars"))
    if not (yb > 0 and ya < 1 and ya > yb):
        return False
    return (f(m.get("volume_24h_fp")) > 0 or f(m.get("volume_fp")) > 0
            or f(m.get("open_interest_fp")) > 0)


def parse_close_time(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def build_rows(events, now=None):
    now = now or datetime.now(timezone.utc)
    rows = []
    for e in events:
        series = e.get("series_ticker") or (e.get("event_ticker") or "?").split("-")[0]
        category = e.get("category") or "Unknown"
        for m in e.get("markets") or []:
            if m.get("status") != "active":
                continue
            if not is_liquid_enough(m):
                continue
            yb, ya = f(m.get("yes_bid_dollars")), f(m.get("yes_ask_dollars"))
            nb, na = f(m.get("no_bid_dollars")), f(m.get("no_ask_dollars"))
            ybs, yas = f(m.get("yes_bid_size_fp")), f(m.get("yes_ask_size_fp"))
            mid = (yb + ya) / 2.0
            tick = tick_size_for(m.get("price_ranges"), mid)
            spread = max(0.0, ya - yb)
            spread_ticks = (spread / tick) if tick > 0 else 0.0
            depth = min(ybs, yas)  # tradable both-sides top-of-book size
            ct = parse_close_time(m.get("close_time"))
            hrs = (ct - now).total_seconds() / 3600.0 if ct else None
            rows.append({
                "ticker": m.get("ticker"),
                "event_ticker": e.get("event_ticker"),
                "series_ticker": series,
                "category": category,
                "close_time": m.get("close_time"),
                "hours_to_close": round(hrs, 2) if hrs is not None else None,
                "yes_bid": yb, "yes_ask": ya, "no_bid": nb, "no_ask": na,
                "yes_bid_size": ybs, "yes_ask_size": yas,
                "tick_size": tick,
                "spread": round(spread, 4),
                "spread_ticks": round(spread_ticks, 2),
                "top_depth": round(depth, 2),
                "volume_24h": f(m.get("volume_24h_fp")),
                "volume_total": f(m.get("volume_fp")),
                "open_interest": f(m.get("open_interest_fp")),
                "scanned_at": now.isoformat(),
            })
    return rows


def aggregate(rows):
    by_series = defaultdict(list)
    for r in rows:
        by_series[r["series_ticker"]].append(r)
    aggs = []
    for series, rs in by_series.items():
        spreads = [r["spread_ticks"] for r in rs]
        depths = [r["top_depth"] for r in rs]
        hrs = [r["hours_to_close"] for r in rs if r["hours_to_close"] is not None]
        vol = sum(r["volume_24h"] for r in rs)
        med_spread = statistics.median(spreads) if spreads else 0.0
        med_depth = statistics.median(depths) if depths else 0.0
        aggs.append({
            "series_ticker": series,
            "category": rs[0]["category"],
            "market_count": len(rs),
            "median_spread_ticks": round(med_spread, 2),
            "median_depth": round(med_depth, 1),
            "total_volume_24h": round(vol, 1),
            "opportunity_score": round(med_spread * vol, 1),
            "hours_to_close_min": round(min(hrs), 1) if hrs else None,
            "hours_to_close_median": round(statistics.median(hrs), 1) if hrs else None,
            "hours_to_close_max": round(max(hrs), 1) if hrs else None,
        })
    aggs.sort(key=lambda a: -a["opportunity_score"])
    return aggs


def write_jsonl_gz(rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    mode = "ab" if os.path.exists(path) else "wb"
    with gzip.open(path, mode) as fh:
        for r in rows:
            fh.write((json.dumps(r, separators=(",", ":")) + "\n").encode("utf-8"))


def format_table(aggs, n=15):
    lines = []
    lines.append("=" * 104)
    lines.append(f"{'RANK':<5}{'SERIES':<24}{'CATEGORY':<18}{'#MKT':<6}"
                  f"{'MED_SPR(t)':<12}{'MED_DEPTH':<12}{'VOL_24H':<14}{'SCORE':<14}")
    lines.append("-" * 104)
    for i, a in enumerate(aggs[:n], 1):
        lines.append(f"{i:<5}{a['series_ticker']:<24}{a['category'][:17]:<18}{a['market_count']:<6}"
                      f"{a['median_spread_ticks']:<12}{a['median_depth']:<12}"
                      f"{a['total_volume_24h']:<14}{a['opportunity_score']:<14}")
    lines.append("=" * 104)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir", nargs="?", default="gha_data",
                     help="directory to write venue_scan_<date>.jsonl.gz into (default gha_data)")
    ap.add_argument("--top", type=int, default=15, help="rows to print in the ranked table")
    a = ap.parse_args()

    t0 = time.time()
    sess = requests.Session()
    print("market_scanner: paginating GET /trade-api/v2/events?status=open&with_nested_markets=true ...")
    events = fetch_open_events(sess)
    print(f"fetched {len(events)} open events in {time.time() - t0:.1f}s")

    now = datetime.now(timezone.utc)
    rows = build_rows(events, now)
    n_series = len({r["series_ticker"] for r in rows})
    print(f"liquid-enough markets: {len(rows)} across {n_series} series")

    today = now.strftime("%Y-%m-%d")
    out_path = os.path.join(a.outdir, f"venue_scan_{today}.jsonl.gz")
    write_jsonl_gz(rows, out_path)
    print(f"wrote {len(rows)} rows -> {out_path}")

    aggs = aggregate(rows)
    print()
    print(format_table(aggs, a.top))
    print(f"\ntotal runtime: {time.time() - t0:.1f}s")
    return aggs, rows


if __name__ == "__main__":
    main()
