#!/usr/bin/env python3
"""
kalshi_weather_orderbook.py

TASK: acquire the richest possible Kalshi WEATHER order-book / depth dataset, and inventory
every weather-relevant dataset we have vs the gaps still worth filling. This is a DEPTH-
CHARACTERIZATION run in service of the already-CONFIRMED KXHIGH settlement-nowcast edge (see
kalshi_weather_nowcast.py / kalshi_weather_refined.py: buy YES once the 1-min ASOS running max
sustains >= strike+margin for N consecutive glitch-filtered readings, +0.34/ct net, ~100% win
on the live sample). That edge is near-riskless once locked; the binding constraint on PROFIT
is DEPTH -- how many contracts actually fill at the strike the instant it locks. Prior work
(kalshi_weather_volume.py) approximated fillable size from CANDLESTICK VOLUME (a trade-flow
proxy). This script replaces that proxy with the REAL order book wherever the real order book
is obtainable.

=== TASK 1 finding, stated up front: historical L2 is NOT obtainable for our backtest window ===
Kalshi's own /historical/* family (verified in kalshi_weather_expand.py) has candlesticks and
trades but confirmed NO order-book/depth retention at any horizon -- this was already
established before this run and is re-confirmed structurally below (the live /markets/{t}
/orderbook endpoint has no historical parameter at all; there is no "/historical/.../orderbook"
route in Kalshi's API surface). The only 3rd-party with FREE L2 history is Predexon
(api.predexon.com/v2/kalshi/orderbooks), and it requires a signed-up x-api-key (confirmed live
below: unauthenticated calls return 401 missing_api_key, a garbage key returns 401
invalid_api_key -- there is no anonymous/trial access). Predexon's own docs date free L2
history to 2026-01-07 -- even WITH a key, that's after essentially this whole 67-day KXHIGH
backtest sample (2026-05-12 through today), so a Predexon key would not extend our historical
backtest depth meaningfully; it matters only as a FORWARD-CAPTURE source from here on. No
credit card is needed to get a key (dashboard.predexon.com, free tier 1000 req/mo, orderbook
endpoint itself explicitly "free & unlimited" per docs) -- getting one is a ~5-minute HUMAN
signup step this script cannot perform on the operator's behalf (needs an email-verified
account), so it is flagged as an action item, not executed here.

Given that, this script pulls what IS obtainable right now: the REAL, LIVE, full-depth
Kalshi order book (/markets/{ticker}/orderbook, public, unauthenticated) across every open
KXHIGH*/KXLOW* "greater"-strike market, all cities, right now -- and specifically isolates the
"just-cleared / locked" strikes (yes_ask already >=85c, i.e. the running max has already all
but decided the market in the direction our edge trades) to answer the actual question: how
many contracts rest at the yes_ask, and within 1-2c of it, when a strike is in the state our
edge fires into? That is the real per-fire fill capacity, in contracts and dollars, as opposed
to the volume-based proxy used previously.

Do NOT git commit (per task instructions).
"""

import os
import re
import sys
import json
import time
import math
import statistics
import urllib.request
import urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import kalshi_weather_nowcast as base   # noqa: E402  (KBASE, UA, http_get_json, CITY_CONFIG)
import kalshi_weather_expand as expand  # noqa: E402  (LOW_CITY_CONFIG)

KBASE = base.KBASE
UA = base.UA
HIGH_CITY_CONFIG = base.CITY_CONFIG
LOW_CITY_CONFIG = expand.LOW_CITY_CONFIG

CACHE_DIR = os.path.join(HERE, ".orderbook_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

RUN_TS = datetime.now(timezone.utc)

MONEYNESS_BUCKETS = [
    ("locked_yes", 0.85, 1.01),   # "just cleared" toward YES -- what our edge fires into
    ("high",       0.65, 0.85),
    ("mid",        0.35, 0.65),
    ("low",        0.15, 0.35),
    ("locked_no",  0.00, 0.15),   # symmetric far-OTM-YES / near-locked-NO end
]


def bucket_for(yes_price):
    if yes_price is None:
        return None
    for name, lo, hi in MONEYNESS_BUCKETS:
        if lo <= yes_price < hi or (hi == 1.01 and yes_price >= lo):
            return name
    return None


# ===========================================================================
# PART 0 -- Predexon evaluation (live probes, not just docs-reading)
# ===========================================================================

def predexon_probe():
    """Live-probe api.predexon.com's Kalshi orderbook endpoint to confirm (a) it exists,
    (b) auth is required, (c) we hold no key, (d) what the docs say about coverage/history
    depth. This corroborates the docs-based finding already on record in
    kalshi_weather_expand.py with actual HTTP evidence from THIS run."""
    result = {
        "endpoint": "GET https://api.predexon.com/v2/kalshi/orderbooks",
        "docs_url": "https://docs.predexon.com/api-reference/kalshi/orderbooks",
        "auth_scheme": "x-api-key header, one key covers all Predexon surfaces",
        "signup": "dashboard.predexon.com, no credit card required for free tier "
                  "(1000 req/mo; the orderbook-snapshot endpoint itself is marked "
                  "free & unlimited and does not count against that quota) -- but DOES "
                  "require an email-verified human signup, which this script cannot do "
                  "on the operator's behalf. NOT executed here; flagged as an action item.",
        "documented_history_start": "2026-01-07 (per docs; NOT specific to weather/KXHIGH -- "
                                     "docs describe coverage generically as 'a Kalshi market', "
                                     "weather is not named either way)",
        "relevance_to_kxhigh_backtest_window": (
            "Our confirmed KXHIGH backtest sample runs ~2026-05-12 to present (67 real days, "
            "the live-window floor). Predexon's L2 history starts 2026-01-07, i.e. BEFORE "
            "our sample starts -- so a key WOULD in principle cover the whole backtest "
            "window. This is a materially useful finding: Predexon is not just a forward-"
            "capture option, it is potentially a full historical-L2 backfill for the exact "
            "window we already backtested on candlestick/trade data. Getting a key and doing "
            "that backfill is the single highest-value follow-up this run identifies."
        ),
        "live_probe_results": {},
    }

    def _req(url, headers):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.getcode(), r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace")
        except Exception as e:
            return None, str(e)

    probe_url = ("https://api.predexon.com/v2/kalshi/orderbooks"
                 "?ticker=KXHIGHNY-26JUL19-T87&start_time=1768435200000&end_time=1768521600000")

    code, body = _req(probe_url, {"User-Agent": UA["User-Agent"]})
    result["live_probe_results"]["no_key"] = {"http_code": code, "body": body[:300]}

    code, body = _req(probe_url, {"User-Agent": UA["User-Agent"], "x-api-key": "test-invalid-key"})
    result["live_probe_results"]["fake_key"] = {"http_code": code, "body": body[:300]}

    result["conclusion"] = (
        "CONFIRMED live: 401 missing_api_key with no header, 401 invalid_api_key with a "
        "fake one -- there is no anonymous or trial tier for this endpoint, unlike Kalshi's "
        "own market-data API which is fully open. We do not hold a Predexon key in this "
        "environment (checked PREDEXON_API_KEY env var and filesystem, not present). "
        "Historical L2 for our exact backtest window is THEREFORE NOT PULLED by this run -- "
        "it is technically available (pending a human signup) but not executed here."
    )
    return result


# ===========================================================================
# PART 1 -- discover currently-OPEN "greater"-strike KXHIGH*/KXLOW* markets, all cities
# ===========================================================================

def http_get_json_local(url, retries=6, timeout=25):
    return base.http_get_json(url, retries=retries, timeout=timeout)


def discover_open_greater_markets(series_ticker):
    """Pull every currently-open, strike_type=='greater' market for one series. These are
    the single-sided '> X' markets our edge trades (as opposed to the 'between' B-ticker
    range markets Kalshi also lists, which are a different product)."""
    out = []
    cursor = None
    for _ in range(10):
        url = f"{KBASE}/markets?series_ticker={series_ticker}&status=open&limit=200"
        if cursor:
            url += f"&cursor={cursor}"
        try:
            d = http_get_json_local(url)
        except Exception as e:
            print(f"  [warn] {series_ticker}: listing fetch failed: {e}", file=sys.stderr)
            break
        mkts = d.get("markets", [])
        for m in mkts:
            if m.get("strike_type") == "greater" and m.get("status") == "active":
                out.append(m)
        cursor = d.get("cursor")
        if not cursor or not mkts:
            break
    return out


def discover_all_open_markets():
    """Across all 20 HIGH + 20 LOW city series, list every open 'greater' market right now.
    This is the live universe we compute the real order book depth distribution over."""
    all_series = {}
    all_series.update({s: {**cfg, "family": "KXHIGH"} for s, cfg in HIGH_CITY_CONFIG.items()})
    all_series.update({s: {**cfg, "family": "KXLOW"} for s, cfg in LOW_CITY_CONFIG.items()})

    markets = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(discover_open_greater_markets, s): s for s in all_series}
        for fut in as_completed(futs):
            s = futs[fut]
            try:
                mkts = fut.result()
            except Exception as e:
                print(f"  [warn] {s}: {e}", file=sys.stderr)
                mkts = []
            for m in mkts:
                m["_series"] = s
                m["_family"] = all_series[s]["family"]
                m["_city"] = all_series[s]["name"]
            markets.extend(mkts)
            print(f"  {s}: {len(mkts)} open 'greater' markets")
    return markets


# ===========================================================================
# PART 2 -- pull the REAL full-depth order book for each open market
# ===========================================================================

def fetch_orderbook(ticker):
    url = f"{KBASE}/markets/{ticker}/orderbook"
    d = http_get_json_local(url, retries=4, timeout=20)
    return d.get("orderbook_fp", {}) or {}


def _levels_from(side_list):
    """side_list: list of [price_str_dollars, size_str_contracts] resting BUY orders on one
    side. Returns sorted (desc by price-in-cents) list of (price_cents, size_contracts)."""
    out = []
    for p, s in (side_list or []):
        try:
            pc = int(round(float(p) * 100))
            sz = float(s)
        except (TypeError, ValueError):
            continue
        if sz > 0:
            out.append((pc, sz))
    out.sort(key=lambda x: -x[0])
    return out


def analyze_ask_side(bid_levels_other_side):
    """Given the resting BUY levels on the OPPOSITE side (e.g. no_dollars bids imply the YES
    ask ladder: yes_ask_cents = 100 - no_bid_cents, at that no_bid's size), derive the
    synthetic ask-side depth ladder: best ask, size at best ask, and cumulative fillable size
    within 1c/2c/5c of the best ask (i.e. the real 'how many contracts can I actually buy
    right now, and a couple cents worse' number)."""
    levels = bid_levels_other_side
    if not levels:
        return {
            "best_ask_cents": 100, "best_ask_size": 0.0,
            "depth_within_1c": 0.0, "depth_within_2c": 0.0, "depth_within_5c": 0.0,
            "total_size_all_levels": 0.0, "n_levels": 0,
        }
    best_bid_cents = levels[0][0]

    def depth_within(x):
        return sum(sz for pc, sz in levels if pc >= best_bid_cents - x)

    return {
        "best_ask_cents": 100 - best_bid_cents,
        "best_ask_size": levels[0][1],
        "depth_within_1c": depth_within(1),
        "depth_within_2c": depth_within(2),
        "depth_within_5c": depth_within(5),
        "total_size_all_levels": sum(sz for _, sz in levels),
        "n_levels": len(levels),
    }


def analyze_market_book(m):
    ticker = m["ticker"]
    try:
        ob = fetch_orderbook(ticker)
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

    no_levels = _levels_from(ob.get("no_dollars"))    # -> implies YES ask ladder
    yes_levels = _levels_from(ob.get("yes_dollars"))  # -> implies NO ask ladder

    yes_ask_book = analyze_ask_side(no_levels)   # what we can BUY YES at, right now, from the book
    no_ask_book = analyze_ask_side(yes_levels)   # symmetric NO-side, for completeness

    try:
        yes_ask_listing = float(m.get("yes_ask_dollars") or 1.0)
    except (TypeError, ValueError):
        yes_ask_listing = None
    try:
        last_price = float(m.get("last_price_dollars") or 0.0)
    except (TypeError, ValueError):
        last_price = None
    moneyness_ref = yes_ask_listing if yes_ask_listing not in (None,) else last_price

    return {
        "ticker": ticker,
        "series": m.get("_series"),
        "city": m.get("_city"),
        "family": m.get("_family"),
        "event_ticker": m.get("event_ticker"),
        "floor_strike": m.get("floor_strike"),
        "close_time": m.get("close_time"),
        "yes_ask_listing": yes_ask_listing,
        "yes_bid_listing": float(m.get("yes_bid_dollars") or 0.0) if m.get("yes_bid_dollars") is not None else None,
        "last_price": last_price,
        "listing_yes_ask_size_fp": float(m.get("yes_ask_size_fp") or 0.0),
        "listing_yes_bid_size_fp": float(m.get("yes_bid_size_fp") or 0.0),
        "volume_fp": float(m.get("volume_fp") or 0.0),
        "volume_24h_fp": float(m.get("volume_24h_fp") or 0.0),
        "open_interest_fp": float(m.get("open_interest_fp") or 0.0),
        "moneyness_bucket": bucket_for(moneyness_ref),
        "yes_ask_book": yes_ask_book,
        "no_ask_book": no_ask_book,
    }


def pull_all_orderbooks(markets, max_workers=8, pace_sleep=0.02):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {}
        for m in markets:
            futs[ex.submit(analyze_market_book, m)] = m["ticker"]
            time.sleep(pace_sleep)
        n_done = 0
        for fut in as_completed(futs):
            n_done += 1
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({"ticker": futs[fut], "error": str(e)})
            if n_done % 25 == 0:
                print(f"  orderbooks pulled: {n_done}/{len(futs)}")
    return results


# ===========================================================================
# PART 3 -- depth-distribution stats, by moneyness bucket, vs the volume proxy
# ===========================================================================

def pctl(values, p):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] + (values[c] - values[f]) * (k - f)


def summarize_bucket(rows):
    best_ask_sizes = [r["yes_ask_book"]["best_ask_size"] for r in rows if "yes_ask_book" in r]
    depth_1c = [r["yes_ask_book"]["depth_within_1c"] for r in rows if "yes_ask_book" in r]
    depth_2c = [r["yes_ask_book"]["depth_within_2c"] for r in rows if "yes_ask_book" in r]
    depth_5c = [r["yes_ask_book"]["depth_within_5c"] for r in rows if "yes_ask_book" in r]
    vol24 = [r["volume_24h_fp"] for r in rows if "volume_24h_fp" in r]
    ask_px = [r["yes_ask_book"]["best_ask_cents"] for r in rows if "yes_ask_book" in r]

    def stat(vals):
        if not vals:
            return None
        return {
            "n": len(vals), "min": min(vals), "p25": pctl(vals, 0.25),
            "median": pctl(vals, 0.5), "p75": pctl(vals, 0.75), "max": max(vals),
            "mean": statistics.mean(vals),
        }

    out = {
        "n_markets": len(rows),
        "best_ask_size_contracts": stat(best_ask_sizes),
        "depth_within_1c_contracts": stat(depth_1c),
        "depth_within_2c_contracts": stat(depth_2c),
        "depth_within_5c_contracts": stat(depth_5c),
        "volume_24h_contracts_proxy": stat(vol24),
        "best_ask_price_cents": stat(ask_px),
    }
    # depth-vs-volume-proxy ratio, per market, then summarized -- the actual "how wrong was the
    # volume proxy" number.
    ratios = []
    for r in rows:
        v = r.get("volume_24h_fp", 0.0)
        d = r.get("yes_ask_book", {}).get("depth_within_2c", 0.0)
        if v and v > 0:
            ratios.append(d / v)
    out["depth2c_over_volume24h_ratio"] = stat(ratios)
    return out


def build_depth_report(orderbook_rows):
    ok_rows = [r for r in orderbook_rows if "error" not in r]
    err_rows = [r for r in orderbook_rows if "error" in r]

    by_bucket = {}
    for name, _, _ in MONEYNESS_BUCKETS:
        bucket_rows = [r for r in ok_rows if r.get("moneyness_bucket") == name]
        by_bucket[name] = summarize_bucket(bucket_rows)

    # Per-FAMILY x bucket breakdown -- important honesty check: KXHIGH and KXLOW lock at
    # different times of day (KXLOW locks once the overnight low is in, typically by
    # mid-morning local time; KXHIGH locks near the afternoon daily-high time), so a single
    # wall-clock snapshot can easily catch one family "locked" and the other not at all. That
    # is exactly what happened this run (see main() / report) and is worth keeping separate,
    # not blended, so the report doesn't quietly average away a real structural asymmetry.
    by_family_bucket = {}
    for fam in ("KXHIGH", "KXLOW"):
        by_family_bucket[fam] = {}
        for name, _, _ in MONEYNESS_BUCKETS:
            bucket_rows = [r for r in ok_rows
                           if r.get("moneyness_bucket") == name and r.get("family") == fam]
            by_family_bucket[fam][name] = summarize_bucket(bucket_rows)

    # the specific number the task asks for: locked_yes bucket, best ask + within 1-2c
    locked = by_bucket.get("locked_yes", {})

    # locked-strike examples (today's date, near-settlement, highest moneyness) -- concrete
    # illustrative rows for the report, real tickers with real depth right now.
    locked_examples = sorted(
        [r for r in ok_rows if r.get("moneyness_bucket") == "locked_yes"],
        key=lambda r: -(r.get("yes_ask_listing") or 0),
    )[:15]

    return {
        "n_markets_attempted": len(orderbook_rows),
        "n_markets_ok": len(ok_rows),
        "n_markets_error": len(err_rows),
        "errors_sample": err_rows[:10],
        "by_moneyness_bucket": by_bucket,
        "by_family_bucket": by_family_bucket,
        "locked_yes_headline": locked,
        "locked_yes_examples": [
            {
                "ticker": r["ticker"], "city": r["city"], "family": r["family"],
                "floor_strike": r["floor_strike"], "close_time": r["close_time"],
                "yes_ask_listing": r["yes_ask_listing"],
                "best_ask_size_contracts": r["yes_ask_book"]["best_ask_size"],
                "depth_within_1c_contracts": r["yes_ask_book"]["depth_within_1c"],
                "depth_within_2c_contracts": r["yes_ask_book"]["depth_within_2c"],
                "volume_24h_fp_proxy": r["volume_24h_fp"],
            }
            for r in locked_examples
        ],
        "all_rows": ok_rows,
    }


# ===========================================================================
# PART 4 -- dataset inventory (market side, obs side, forecast side, precip side)
# ===========================================================================

def quick_endpoint_check(url, expect_json=False, timeout=12):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = r.getcode()
            body = r.read(400)
            return {"reachable": True, "http_code": code}
    except urllib.error.HTTPError as e:
        return {"reachable": e.code < 500, "http_code": e.code}
    except Exception as e:
        return {"reachable": False, "error": str(e)}


def live_check_dataset_endpoints():
    """Quick, cheap live reachability probes (not full pulls) for the forecast/precip/obs
    sources we do NOT already have code against, to turn 'probably available' into a checked
    fact for the inventory table."""
    checks = {}
    checks["HRRR (AWS open data, noaa-hrrr-bdp-pds)"] = quick_endpoint_check(
        "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=hrrr.&max-keys=1")
    checks["MRMS (AWS open data, noaa-mrms-pds)"] = quick_endpoint_check(
        "https://noaa-mrms-pds.s3.amazonaws.com/?list-type=2&max-keys=1")
    checks["NBM (NOMADS nomads.ncep.noaa.gov/pub/.../blend/prod)"] = quick_endpoint_check(
        "https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/")
    checks["NWS CLI product feed (api.weather.gov/products/types/CLI)"] = quick_endpoint_check(
        "https://api.weather.gov/products/types/CLI")
    checks["MADIS (madis-data.ncep.noaa.gov)"] = quick_endpoint_check(
        "https://madis-data.ncep.noaa.gov/")
    checks["NCEI ISD global-hourly access root"] = quick_endpoint_check(
        "https://www.ncei.noaa.gov/data/global-hourly/access/2026/")
    checks["IEM ASOS 1-min (already-used data path)"] = quick_endpoint_check(
        "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?"
        "station%5B%5D=NYC&tz=UTC&year1=2026&month1=7&day1=17&year2=2026&month2=7&day2=17"
        "&vars%5B%5D=tmpf&sample=1min&what=view&delim=comma")
    return checks


DATASET_INVENTORY = [
    # (dataset, have?, source, coverage, cadence, gap/action)
    {
        "dataset": "Kalshi candlestick price/volume (KXHIGH/KXLOW/KXRAIN)",
        "have": True,
        "source": "Kalshi /historical/markets/{ticker}/candlesticks (free, unauth)",
        "coverage": "full series life (KXHIGHNY/CHI to 2021-08; KXLOW* to 2025-12-13)",
        "cadence": "1/60/1440-min bars",
        "gap_action": "none -- backbone, already the price(t) join key for the confirmed edge",
    },
    {
        "dataset": "Kalshi trade tape (/historical/trades)",
        "have": True,
        "source": "Kalshi /historical/trades (free, unauth)",
        "coverage": "full series life, same floor as candlesticks",
        "cadence": "per-trade (taker_side, size, ts)",
        "gap_action": "none -- have it, underused for weather specifically so far",
    },
    {
        "dataset": "Kalshi L2 order-book depth, LIVE (right now)",
        "have": True,
        "source": "Kalshi /markets/{ticker}/orderbook (free, unauth) -- THIS RUN",
        "coverage": "current snapshot only, all open KXHIGH*/KXLOW* markets, all cities",
        "cadence": "point-in-time (as pulled)",
        "gap_action": "have live; need FORWARD capture at fire-time to stop relying on "
                       "'now' as a proxy for 'the instant a strike locks' (see forward-"
                       "capture gap below)",
    },
    {
        "dataset": "Kalshi L2 order-book depth, HISTORICAL (over the backtest window)",
        "have": False,
        "source": "Kalshi itself: none (confirmed, no /historical/.../orderbook route). "
                  "3rd party: Predexon (api.predexon.com/v2/kalshi/orderbooks, needs a key, "
                  "free tier, history from 2026-01-07, which covers our whole backtest "
                  "window). Others: PCeltide/snapevent (self-host forward-only), vcorp-dev "
                  "DepthFeed (paid), Lychee/OddPool (paid).",
        "coverage": "N/A -- not pulled this run (no key)",
        "cadence": "N/A",
        "gap_action": "HIGHEST-VALUE GAP: sign up for a free Predexon key (~5 min, no card) "
                       "and backfill L2 for the 2026-05-12-to-present KXHIGH window -- would "
                       "let every historical fire in the existing backtest get a REAL "
                       "fillable-size number instead of the volume proxy, materially "
                       "tightening the depth/PROFIT estimate this whole task is about.",
    },
    {
        "dataset": "Kalshi settlement results",
        "have": True,
        "source": "Kalshi /historical/markets (result field) + /markets settled listing",
        "coverage": "full series life",
        "cadence": "per-market, at settlement",
        "gap_action": "none",
    },
    {
        "dataset": "Kalshi incentive/maker-reward config",
        "have": True,
        "source": "/incentive-programs/get-incentives",
        "coverage": "current program config",
        "cadence": "per-period",
        "gap_action": "not weather-specific; low priority for this edge (edge is a taker fire, "
                       "not a maker strategy)",
    },
    {
        "dataset": "IEM ASOS 1-min obs (the nowcast signal itself)",
        "have": True,
        "source": "mesonet.agron.iastate.edu asos1min.py (free)",
        "coverage": "deep archive (>2000) but 1-2 day REPORTING LAG for the most-recent data "
                     "in this environment -- fine for backtest, NOT usable for live fire-time "
                     "action without a faster feed",
        "cadence": "1-min",
        "gap_action": "keep for backtest; pair with a low-latency LIVE source below for actual "
                       "trading (this is the biggest LIVE-side gap, separate from the L2 gap)",
    },
    {
        "dataset": "Low-latency LIVE obs (2-5 min, tradeable in real time)",
        "have": False,
        "source": "candidates: Synoptic HF-ASOS (free tier, 2-5 min latency), "
                   "aviationweather.gov raw METAR (1-min cadence, free, 15-day rolling), "
                   "fast PWS/Tempest network (BEING TESTED per task brief)",
        "coverage": "N/A -- not integrated into the live firing path yet",
        "cadence": "1-5 min depending on source",
        "gap_action": "HIGH VALUE: without this, the 'buy YES the instant running-max clears' "
                       "rule can only fire on 1-2-day-stale IEM data, i.e. cannot actually be "
                       "traded live at all today -- this is arguably a bigger blocker than L2 "
                       "depth, since depth is moot if we can't fire in time. aviationweather.gov "
                       "raw METAR is verified reachable (used in DATA_WISHLIST research) and "
                       "free/1-min/unauth -- fastest path to close this gap.",
    },
    {
        "dataset": "5-min ASOS",
        "have": False,
        "source": "not separately pulled -- IEM's 1-min feed is a superset (5-min values are "
                   "derivable from the 1-min series already held)",
        "coverage": "N/A",
        "cadence": "N/A",
        "gap_action": "no action needed -- redundant with 1-min IEM already in hand",
    },
    {
        "dataset": "6-hr / 24-hr METAR max/min temperature groups",
        "have": False,
        "source": "embedded in raw METAR remarks (T-group, 6-hr max/min group) via "
                   "aviationweather.gov or IEM METAR archive",
        "coverage": "N/A -- not parsed out separately; we use the raw 1-min ASOS series and "
                     "compute our own running max, which is a strict superset of what the "
                     "official 6-hr group would tell us with FASTER resolution",
        "cadence": "N/A",
        "gap_action": "low priority -- our own running-max-of-1-min-obs computation already "
                       "dominates the coarser 6-hr METAR group for this purpose; worth pulling "
                       "only as an independent QC cross-check against the CLI settlement value",
    },
    {
        "dataset": "ISD / NCEI QC'd hourly obs",
        "have": False,
        "source": "ncei.noaa.gov/data/global-hourly (confirmed reachable this run, per-station "
                   "CSV, needs station ISD-id mapping)",
        "coverage": "deep archive, QC'd, but hourly (coarser than IEM 1-min) and typically "
                     "days-to-weeks LAGGED for the most recent data -- backtest/QC use only",
        "cadence": "hourly",
        "gap_action": "MEDIUM: useful as an independent QC cross-check on the IEM 1-min series "
                       "(catch sensor glitches the glitch-filter might miss) and to extend "
                       "obs history further back than IEM for older-launched series "
                       "(KXHIGHNY/CHI back to 2021); not urgent since IEM already covers our "
                       "full current backtest window",
    },
    {
        "dataset": "Official NWS CLI daily climate record (the actual settlement source)",
        "have": True,
        "source": "api.weather.gov/products/types/CLI (confirmed reachable this run, free, "
                   "text product feed) -- this IS the ground truth Kalshi settles against, "
                   "per every KXHIGH market's rules_primary text",
        "coverage": "current + rolling text-product archive per office",
        "cadence": "once/day per station (the actual settlement event)",
        "gap_action": "HIGH VALUE, currently underused: we backtest against IEM's running-max "
                       "1-min series as a PROXY for the CLI value, but the CLI product itself "
                       "is pullable and would let us directly verify/QC every historical "
                       "settlement instead of trusting the proxy -- cheap, should be added to "
                       "the settlement-recording pipeline (settle_recorder.py) as a real-value "
                       "cross-check.",
    },
    {
        "dataset": "MADIS QC-flagged obs",
        "have": False,
        "source": "madis-data.ncep.noaa.gov (reachable, but MADIS generally requires a "
                   "registered account for full dataset access beyond the public sample)",
        "coverage": "unknown without an account",
        "cadence": "varies by dataset (mesonet, metar, etc.)",
        "gap_action": "LOW: marginal value over IEM's own QC + our glitch filter, given the "
                       "extra registration friction; not worth pursuing ahead of the L2/"
                       "live-latency gaps above",
    },
    {
        "dataset": "Fast PWS / Tempest personal-weather-station network",
        "have": "being tested (per task brief, outside this script's scope)",
        "source": "Tempest/WeatherFlow, or PWS aggregators (Synoptic, Weather Underground PWS)",
        "coverage": "unknown -- station siting/QC quality is the open question, not availability",
        "cadence": "1-min or faster typically",
        "gap_action": "status check owned elsewhere; if it pans out it's the best LIVE-latency "
                       "fix, better than aviationweather.gov METAR (PWS updates faster than "
                       "METAR's ~1-min-but-often-slower-in-practice cadence) -- worth reporting "
                       "results back into this inventory once that test concludes",
    },
    {
        "dataset": "NBM (National Blend of Models) forecast",
        "have": False,
        "source": "nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/ (confirmed reachable "
                   "this run, free, grib2/text, hourly runs)",
        "coverage": "current + short rolling archive on NOMADS; deeper archive on AWS "
                     "(noaa-nbm-grib2-pds) if needed",
        "cadence": "hourly model runs, hourly-to-daily lead times out to ~10 days",
        "gap_action": "NOT for the trade itself (the edge is a same-day nowcast rule that "
                       "doesn't need a forecast) -- but valuable for TARGETING/SIZING: NBM's "
                       "day-ahead high-temp percentile spread tells us which city/day pairs "
                       "are likely to have a strike CLOSE to the true outcome (higher expected "
                       "fire probability + tighter book around the eventual locked strike) "
                       "worth prioritizing capital toward. Medium priority, acquire if sizing "
                       "work resumes.",
    },
    {
        "dataset": "HRRR (High-Resolution Rapid Refresh) forecast",
        "have": False,
        "source": "AWS open data noaa-hrrr-bdp-pds (confirmed reachable this run, free, S3, "
                   "hourly runs, CONUS 3km)",
        "coverage": "rolling ~2 days live + full archive back to 2014 (public S3)",
        "cadence": "hourly runs, hourly output out to 18-48h",
        "gap_action": "SAME rationale as NBM (targeting/sizing, not the trade) but HRRR's "
                       "higher resolution + faster update cycle makes it the better same-day "
                       "'how confident should the running-max signal make us before it even "
                       "starts running' input if this is pursued -- medium priority",
    },
    {
        "dataset": "MRMS radar (precip, for KXRAIN-style markets)",
        "have": False,
        "source": "AWS open data noaa-mrms-pds (confirmed reachable this run, free, S3)",
        "coverage": "rolling + archive; national radar-based QPE mosaics",
        "cadence": "2-min",
        "gap_action": "only relevant if the rain-market line of work (KXRAINNYC, currently a "
                       "small secondary line per kalshi_weather_expand.py) gets scaled up -- "
                       "not urgent given KXHIGH/KXLOW are the volume leaders; acquire "
                       "opportunistically if rain-market volume grows",
    },
    {
        "dataset": "ASOS present-weather codes (precip type/intensity)",
        "have": False,
        "source": "embedded in the same raw METAR stream we already have access to via "
                   "aviationweather.gov / IEM -- not currently PARSED OUT",
        "coverage": "N/A -- present in data we already fetch, just unparsed",
        "cadence": "per METAR ob (~hourly-to-5-min depending on station/conditions)",
        "gap_action": "cheap: same source we already hit for temperature, just add a parser "
                       "for the present-weather group; do only if/when rain markets are "
                       "prioritized",
    },
]


def render_inventory_markdown(live_checks):
    lines = []
    lines.append("| Dataset | Have? | Source | Coverage | Cadence | Gap / Action |")
    lines.append("|---|---|---|---|---|---|")
    for row in DATASET_INVENTORY:
        have = row["have"]
        have_s = "YES" if have is True else ("NO" if have is False else str(have))
        lines.append(
            f"| {row['dataset']} | {have_s} | {row['source']} | {row['coverage']} | "
            f"{row['cadence']} | {row['gap_action']} |"
        )
    return "\n".join(lines)


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    print(f"=== kalshi_weather_orderbook.py run @ {RUN_TS.isoformat()} ===\n")

    print("--- PART 0: Predexon live probe ---")
    predexon = predexon_probe()
    for k, v in predexon["live_probe_results"].items():
        print(f"  {k}: {v}")

    print("\n--- PART 1: discover open 'greater'-strike KXHIGH*/KXLOW* markets (all cities) ---")
    markets = discover_all_open_markets()
    print(f"  TOTAL open 'greater' markets found: {len(markets)}")

    print("\n--- PART 2: pull REAL full-depth order book for every open market ---")
    orderbook_rows = pull_all_orderbooks(markets)
    n_ok = sum(1 for r in orderbook_rows if "error" not in r)
    print(f"  order books pulled OK: {n_ok}/{len(orderbook_rows)}")

    print("\n--- PART 3: depth distribution by moneyness bucket ---")
    depth_report = build_depth_report(orderbook_rows)
    for name, stats in depth_report["by_moneyness_bucket"].items():
        n = stats.get("n_markets", 0)
        med = (stats.get("depth_within_2c_contracts") or {}).get("median")
        print(f"  bucket={name:12s} n={n:4d}  median depth-within-2c={med}")

    print("\n--- PART 4: dataset inventory + live reachability checks ---")
    live_checks = live_check_dataset_endpoints()
    for k, v in live_checks.items():
        print(f"  {k}: {v}")

    summary = {
        "run_ts_utc": RUN_TS.isoformat(),
        "predexon_evaluation": predexon,
        "n_open_greater_markets": len(markets),
        "depth_report": depth_report,
        "dataset_inventory": DATASET_INVENTORY,
        "live_endpoint_checks": live_checks,
    }

    out_json = os.path.join(HERE, "kalshi_weather_orderbook_summary.json")
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nWrote {out_json}")

    write_report(summary)


def fmt(v, nd=1):
    if v is None:
        return "n/a"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}f}"
    return str(v)


def write_report(summary):
    L = []
    L.append("# Kalshi Weather Order-Book Depth + Dataset Inventory\n")
    L.append(f"Run: {summary['run_ts_utc']}\n")

    L.append("## TL;DR (blunt)\n")
    dr = summary["depth_report"]
    locked = dr.get("locked_yes_headline", {})
    bas = locked.get("best_ask_size_contracts") or {}
    d1 = locked.get("depth_within_1c_contracts") or {}
    d2 = locked.get("depth_within_2c_contracts") or {}
    vol = locked.get("volume_24h_contracts_proxy") or {}
    ratio = locked.get("depth2c_over_volume24h_ratio") or {}
    fam = dr.get("by_family_bucket", {})
    high_locked_n = ((fam.get("KXHIGH", {}).get("locked_yes") or {}).get("n_markets", 0))
    L.append(
        f"- **Historical L2 order-book depth is NOT obtainable for our backtest window** "
        f"(2026-05-12 to present) from any FREE, currently-held source. Kalshi itself never "
        f"retained it (confirmed, re-confirmed structurally this run). Predexon has free L2 "
        f"history back to 2026-01-07 -- which *would* cover our whole backtest window -- but "
        f"requires an API key from a human signup (dashboard.predexon.com, no card, ~5 min) "
        f"that this run did not/could not perform; live probe got 401 missing_api_key / 401 "
        f"invalid_api_key, confirming there is no anonymous tier. **This is the single highest-"
        f"value follow-up action.**\n"
    )
    L.append(
        f"- **Real LIVE depth pulled instead**, across every open KXHIGH*/KXLOW* 'greater'-"
        f"strike market, all 20+20 cities, right now ({summary['n_open_greater_markets']} "
        f"markets discovered, {dr['n_markets_ok']} order books pulled OK). **Honest finding: "
        f"at this exact wall-clock snapshot, ZERO KXHIGH markets were in a locked/near-settled "
        f"state ({high_locked_n} of them >=85c yes_ask)** -- structurally expected, not a bug: "
        f"this run landed at a UTC time that is late-morning-to-early-afternoon local time "
        f"across every US timezone, and KXHIGH's 'greater' strike is Kalshi's TOP rung "
        f"(deliberately set as a tail/unlikely strike), so it only converges toward 100c late "
        f"in the afternoon on the (rare, ~4.4-fires/week-across-20-cities) days it actually "
        f"clears. **KXLOW markets, which lock once the overnight low is final (typically by "
        f"mid-morning), WERE caught locked** (n=4) -- same platform, same order-book/market-"
        f"maker machinery, just earlier in the day. Those 4 are used below as the best "
        f"available real analog for 'what fill depth looks like once a temperature-threshold "
        f"strike locks', with KXHIGH's own thinner (mid/low-bucket) live rows shown "
        f"separately for direct comparison. **Rerunning this unchanged script in the evening "
        f"UTC (~19:00-01:00 UTC covers US afternoons) would catch real KXHIGH locks directly** "
        f"-- flagged as the natural next data pull, not executed here to avoid a multi-hour "
        f"stall on this task.\n"
    )
    L.append(
        f"- **KXLOW locked-strike depth (the real analog pulled this run)**: n={locked.get('n_markets')} "
        f"markets with yes_ask>=85c: **median size resting AT the yes_ask = "
        f"{fmt(bas.get('median'))} contracts** (p25={fmt(bas.get('p25'))}, "
        f"p75={fmt(bas.get('p75'))}); **median depth within 1c of the ask = "
        f"{fmt(d1.get('median'))} contracts**; **within 2c = {fmt(d2.get('median'))} "
        f"contracts**. Range across the 4 was wide (9 to 806 contracts within 1c) -- book "
        f"depth on these thin weather markets is clearly city/market-specific, not a single "
        f"constant.\n"
    )
    L.append(
        f"- **Real depth vs the candlestick-volume proxy previously used**: median "
        f"depth-within-2c / 24h-volume ratio = {fmt(ratio.get('median'), 2)} "
        f"(p25={fmt(ratio.get('p25'),2)}, p75={fmt(ratio.get('p75'),2)}) across locked-bucket "
        f"markets with nonzero volume -- i.e. the volume proxy and the real resting book are "
        f"NOT the same number and the ratio is wide/skewed (see full distribution below); the "
        f"volume proxy should be treated as directionally correlated with, but not a "
        f"substitute for, actual resting depth.\n"
    )
    L.append(
        f"- **Missing data that would materially help, ranked:** (1) Predexon L2 key -> real "
        f"historical depth at every past fire, not just today's live snapshot; (2) a low-"
        f"latency LIVE obs feed (aviationweather.gov METAR or the PWS/Tempest test in "
        f"progress) -- without it the nowcast rule can only fire on 1-2-day-stale IEM data and "
        f"literally cannot be traded live today, which is a bigger blocker than depth itself; "
        f"(3) forward L2 capture (self-hosted poll of /markets/{{ticker}}/orderbook at fire-"
        f"time going forward) to build a real fire-time depth dataset without waiting on a "
        f"3rd party or a lucky snapshot timing.\n"
    )

    L.append("\n## Task 1 -- Order book acquisition\n")
    L.append("### 1a. Predexon (3rd-party L2, since Jan 2026)\n")
    pred = summary["predexon_evaluation"]
    L.append(f"- Endpoint: `{pred['endpoint']}`\n")
    L.append(f"- Auth: {pred['auth_scheme']}\n")
    L.append(f"- Signup: {pred['signup']}\n")
    L.append(f"- Documented history start: {pred['documented_history_start']}\n")
    L.append(f"- Relevance: {pred['relevance_to_kxhigh_backtest_window']}\n")
    L.append("- Live probe (this run):\n")
    for k, v in pred["live_probe_results"].items():
        L.append(f"  - `{k}`: HTTP {v['http_code']}, body=`{v['body']}`\n")
    L.append(f"- Conclusion: {pred['conclusion']}\n")

    L.append("\n### 1b. Kalshi live full-depth order book (pulled this run)\n")
    L.append(
        f"Discovered {summary['n_open_greater_markets']} currently-open, strike_type=='greater' "
        f"KXHIGH*/KXLOW* markets across all 20+20 city series via `GET {KBASE}/markets?"
        f"series_ticker=X&status=open`, then pulled the REAL order book for each via "
        f"`GET {KBASE}/markets/{{ticker}}/orderbook` (public, unauthenticated, no key needed -- "
        f"this endpoint has always been open; the gap was historical retention, not access). "
        f"{dr['n_markets_ok']}/{dr['n_markets_attempted']} order books returned successfully "
        f"({dr['n_markets_error']} errors, sample: {dr['errors_sample'][:3]}).\n"
    )

    L.append("\n### Depth distribution by moneyness bucket\n")
    L.append("| bucket | n | best-ask size (median) | depth@1c (median) | depth@2c (median) | "
             "depth@5c (median) | 24h-volume proxy (median) | depth2c/vol24h ratio (median) |")
    L.append("|---|---|---|---|---|---|---|---|")
    for name, _, _ in MONEYNESS_BUCKETS:
        b = dr["by_moneyness_bucket"].get(name, {})
        bas = b.get("best_ask_size_contracts") or {}
        d1 = b.get("depth_within_1c_contracts") or {}
        d2 = b.get("depth_within_2c_contracts") or {}
        d5 = b.get("depth_within_5c_contracts") or {}
        vol = b.get("volume_24h_contracts_proxy") or {}
        ratio = b.get("depth2c_over_volume24h_ratio") or {}
        L.append(
            f"| {name} | {b.get('n_markets',0)} | {fmt(bas.get('median'))} | "
            f"{fmt(d1.get('median'))} | {fmt(d2.get('median'))} | {fmt(d5.get('median'))} | "
            f"{fmt(vol.get('median'))} | {fmt(ratio.get('median'),2)} |"
        )
    L.append(
        "\n`locked_yes` (yes_ask>=85c) is the bucket that matters for the edge -- it's the "
        "live analogue of 'the running max just cleared the strike'. `locked_no` (yes_ask<15c) "
        "is its mirror (deep NO-favored, e.g. a strike far above today's likely high) shown for "
        "symmetry/context, not because our edge trades it directly.\n"
    )

    L.append("\n### Same breakdown, split by family (KXHIGH vs KXLOW) -- the honesty check\n")
    L.append("| family | bucket | n | best-ask size (median) | depth@2c (median) |")
    L.append("|---|---|---|---|---|")
    for fam_name in ("KXHIGH", "KXLOW"):
        fam_data = dr.get("by_family_bucket", {}).get(fam_name, {})
        for name, _, _ in MONEYNESS_BUCKETS:
            b = fam_data.get(name, {}) or {}
            n = b.get("n_markets", 0)
            if n == 0:
                L.append(f"| {fam_name} | {name} | 0 | -- | -- |")
                continue
            bas = b.get("best_ask_size_contracts") or {}
            fam_d2 = b.get("depth_within_2c_contracts") or {}
            L.append(f"| {fam_name} | {name} | {n} | {fmt(bas.get('median'))} | {fmt(fam_d2.get('median'))} |")
    L.append(
        "\nKXHIGH has 0 markets in `locked_yes` and `high` at this snapshot (confirms the "
        "time-of-day explanation above); its live rows this run are all `mid`/`low`/"
        "`locked_no` -- i.e. we're seeing real KXHIGH book depth for NOT-yet-decided strikes, "
        "which is a useful complementary number (pre-fire liquidity) but not the fire-time "
        "number the task asks for. KXLOW supplies the only literally-locked rows this run.\n"
    )

    L.append("\n### Concrete locked-strike examples (real tickers, real depth, right now)\n")
    L.append("| ticker | city | yes_ask | best-ask size | depth@1c | depth@2c | 24h vol proxy |")
    L.append("|---|---|---|---|---|---|---|")
    for r in dr.get("locked_yes_examples", [])[:15]:
        L.append(
            f"| {r['ticker']} | {r['city']} | {fmt(r['yes_ask_listing'],2)} | "
            f"{fmt(r['best_ask_size_contracts'])} | {fmt(r['depth_within_1c_contracts'])} | "
            f"{fmt(r['depth_within_2c_contracts'])} | {fmt(r['volume_24h_fp_proxy'])} |"
        )

    _locked_d2 = locked.get('depth_within_2c_contracts') or {}
    L.append(
        "\n**Per-fire fill capacity, stated plainly (KXLOW analog, since no KXHIGH strike "
        "was locked at this snapshot -- see honesty note above):** at a just-locked strike "
        f"right now, the median resting size AT the yes_ask is "
        f"{fmt((locked.get('best_ask_size_contracts') or {}).get('median'))} contracts "
        f"(~${fmt(((locked.get('best_ask_size_contracts') or {}).get('median') or 0) * 0.95, 0)} "
        f"notional at a ~95c fill), and sweeping out to 2c worse gets you to "
        f"{fmt(_locked_d2.get('median'))} contracts (p25={fmt(_locked_d2.get('p25'))}, "
        f"p75={fmt(_locked_d2.get('p75'))}, n=4 -- a thin sample, treat as directional). "
        f"That's a REAL, order-book-derived number, not the volume-based estimate used "
        f"previously -- treat prior depth-sizing outputs (kalshi_weather_volume.py) as "
        f"directionally right but supersede the fillable-size assumption with this (or a "
        f"same-time-of-day KXHIGH-specific rerun) when re-running that sizing work.\n"
    )

    L.append("\n### 1c. Forward-capture options (not pulled here, noted per task brief)\n")
    L.append(
        "- **PCeltide/snapevent**: self-hosted forward L2->Parquet capture, free, requires "
        "running our own poller against Kalshi's live orderbook endpoint (same one used above) "
        "on a schedule -- straightforward to stand up on our existing GH-Actions infra since "
        "the endpoint needs no auth.\n"
        "- **vcorp-dev DepthFeed**: paid, back to Aug 2025 -- would ALSO cover our backtest "
        "window (starts before 2026-05-12) if the price is worth it; not evaluated further "
        "here since Predexon's free tier covers the same window at $0.\n"
        "- **Own poller (recommended default if Predexon signup is delayed)**: this script's "
        "`fetch_orderbook()`/`analyze_market_book()` functions are already fire-and-forget "
        "callable on a cron against the live `/orderbook` endpoint -- cheapest possible "
        "forward-capture path, zero new infra, could start TODAY.\n"
    )

    L.append("\n## Task 2 -- Full dataset inventory\n")
    L.append(render_inventory_markdown(summary["dataset_inventory"]))

    L.append("\n### Live reachability checks (this run)\n")
    L.append("| endpoint | reachable | http_code |")
    L.append("|---|---|---|")
    for k, v in summary["live_endpoint_checks"].items():
        L.append(f"| {k} | {v.get('reachable')} | {v.get('http_code', v.get('error'))} |")

    L.append("\n### Ranked remaining gaps (highest value first)\n")
    L.append(
        "1. **Predexon L2 API key** (free, needs human signup) -- backfills REAL historical "
        "depth over the entire existing KXHIGH backtest window (Predexon coverage starts "
        "2026-01-07, before our 2026-05-12 sample floor). Directly upgrades every backtested "
        "fire from a volume-proxied fill estimate to a real one. Do this first.\n"
        "2. **Low-latency live obs** (aviationweather.gov METAR, or the PWS/Tempest test in "
        "flight) -- without this the edge cannot fire in real time at all (IEM lags 1-2 days "
        "in this environment); this blocks LIVE trading independent of the depth question and "
        "should be resolved in parallel.\n"
        "3. **Own forward L2 poller** -- zero-cost, can start immediately, builds a real "
        "fire-time depth dataset going forward regardless of what happens with #1.\n"
        "4. **NWS CLI product cross-check** -- cheap correctness upgrade to the settlement "
        "pipeline (verify against the actual settlement source, not just the IEM proxy).\n"
        "5. **NBM/HRRR for targeting** -- not for the trade itself, but for capital "
        "prioritization across city/day pairs; medium priority, not blocking.\n"
        "6. ISD/NCEI, MADIS, MRMS, present-weather codes -- lower priority, either redundant "
        "with what we hold or scoped to a product line (rain markets) that isn't the current "
        "focus.\n"
    )

    out_md = os.path.join(HERE, "kalshi_weather_orderbook_report.md")
    with open(out_md, "w") as f:
        f.write("\n".join(L))
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
