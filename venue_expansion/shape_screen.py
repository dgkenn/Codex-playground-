#!/usr/bin/env python3
"""shape_screen.py -- systematic, DESCRIPTIVE screen for the one structural property that survived the graveyard:

    "the market stays open for hours after the outcome is physically determined."

THIS IS NOT A HYPOTHESIS TEST. It carries no pass bar. Nothing it suggests may be promoted without a NEW
pre-registration (frozen spec, frozen bars, adversarial verify). It exists to replace family-by-family guessing with a
direct look at the whole Kalshi catalog.

Stages (each resumable; every pull cached under venue_expansion/cache/shape_screen/; politely paced ~1 req/s):
    catalog   full /series list + every settled non-MVE market in the live API window (global cursor, slimmed)
    classify  per series with >=20 settled markets: DETERMINED-EARLY / DETERMINED-AT-CLOSE / CLOSES-AT-DECISION /
              BULLETIN-PACED, from metadata + rules text (rules cited), plus a gap estimate
    sample    seeded, stratified-by-series, SHUFFLED work order (never re-sorted) of settled markets to pull
    candles   1-minute candlesticks for the final 2 hours of each sampled market (cached per ticker)
    report    oracle-capturable rate (edge_sizing_v2.normalize + winner-cost logic, window = 120 min), ranking,
              graveyard cross-check -> out/shape_screen.json, out/shape_screen.md

Run:  python3 venue_expansion/shape_screen.py <stage> [...]      (or `all`)

Outcome source: market.result from the Kalshi market object (the same object GET /markets/{ticker} returns); a random
subset of sampled tickers is re-fetched through GET /markets/{ticker} and compared (reported as agreement).
NO buy cost = 100 - yes_bid (never 100 - yes_ask). Fee = ceil(7*p*(1-p)) cents at the crossing price.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import os
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CACHE = os.path.join(HERE, "cache", "shape_screen")
CANDLES = os.path.join(CACHE, "candles")
OUTDIR = os.path.join(HERE, "out")
API = "https://api.elections.kalshi.com/trade-api/v2"
SEED = 20261027
WINDOW_MIN = 120          # final 2 hours (task spec); edge_sizing_v2 used 60
MIN_SETTLED = 20
PACE_S = 1.0
_last_call = [0.0]


# --------------------------------------------------------------------------------------------------------------------
# polite HTTP
# --------------------------------------------------------------------------------------------------------------------
def http_get(url: str, tries: int = 8):
    """Sequential, ~1/s, adaptive: on 429/5xx back off exponentially and widen the pacing, relax slowly on success."""
    global PACE_S
    for i in range(tries):
        wait = PACE_S - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kwx-research/1.0"})
            with urllib.request.urlopen(req, timeout=60) as fh:
                out = json.load(fh)
            PACE_S = max(1.0, PACE_S - 0.05)
            return out
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            PACE_S = min(3.0, PACE_S + 0.25)
            time.sleep(min(60, 2 * 2 ** i))
        except Exception:
            time.sleep(min(60, 2 * 2 ** i))
    raise RuntimeError("giving up: " + url)


def jload(path, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return default


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh)
    os.replace(tmp, path)


def parse_ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def fee_c(cost_c: float) -> int:
    p = cost_c / 100.0
    return math.ceil(7 * p * (1 - p))


# --------------------------------------------------------------------------------------------------------------------
# STAGE 1: catalog.  (a) /series (one call, ~15k series)  (b) every settled event in the live window, slim, global cursor
#   (events are ~100x lighter than markets; the first attempt -- a global settled-MARKET walk -- was abandoned after
#   ~32k markets because hourly/15-min crypto ladders put millions of markets in the window; partial kept under
#   cache/shape_screen/global_partial/ and not used)  (c) per-series settled-market pull for series with enough events.
# --------------------------------------------------------------------------------------------------------------------
SLIM = ["ticker", "event_ticker", "open_time", "close_time", "expected_expiration_time", "occurrence_datetime",
        "settlement_ts", "can_close_early", "result", "volume_fp", "open_interest_fp", "strike_type",
        "settlement_timer_seconds", "floor_strike", "cap_strike"]


def stage_events(max_pages=10 ** 9):
    os.makedirs(CACHE, exist_ok=True)
    sp = os.path.join(CACHE, "series_catalog.json")
    if not os.path.exists(sp):
        print("pulling /series ...", flush=True)
        d = http_get(f"{API}/series")
        jdump(d["series"], sp)
        print(f"  {len(d['series']):,} series", flush=True)
    ep = os.path.join(CACHE, "events_slim.jsonl")
    cp = os.path.join(CACHE, "events_cursor.json")
    st = jload(cp, {"cursor": None, "pages": 0, "done": False})
    if st.get("done"):
        print("events already complete:", st)
        return
    pages = 0
    with open(ep, "a") as out:
        while pages < max_pages:
            url = f"{API}/events?status=settled&limit=200"
            if st["cursor"]:
                url += "&cursor=" + st["cursor"]
            d = http_get(url)
            evs = d.get("events", [])
            for e in evs:
                out.write(json.dumps({"s": e["series_ticker"], "e": e["event_ticker"]}) + "\n")
            out.flush()
            st["pages"] += 1
            pages += 1
            st["cursor"] = d.get("cursor") or None
            jdump(st, cp)
            if st["pages"] % 25 == 0:
                print(f"  events page {st['pages']}", flush=True)
            if not st["cursor"] or not evs:
                st["done"] = True
                jdump(st, cp)
                break


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="+")
    ap.add_argument("--max-pages", type=int, default=10 ** 9)
    a = ap.parse_args()
    for s in a.stage:
        if s in ("events", "all"):
            stage_events(a.max_pages)
