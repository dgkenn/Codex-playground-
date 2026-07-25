#!/usr/bin/env python3
"""spec_S1.py -- PRE-REGISTERED spec S1: "Polymarket whitelist EV at MEASURED asks (pmxt.dev order-book
archive)". Executed EXACTLY as registered in venue_expansion/out/judge_specs.json. See that file (and this
module's own header comments) for the frozen spec text; nothing here was tuned after seeing results.

WHAT THIS MEASURES: for 4 recon-verified cities (Chicago/KORD, Tokyo/RJTT, London/EGLC, Paris/LFPB), walk
each usable city-day's weather-only signal (kwx_lock_rule.sustained_extreme, glitch-filtered + sustain-3 +
1.0F/0.5C margin, byte-identical shim of the DEPLOYED kwx_runner rule) forward in time. Every first moment
the filtered running extreme enters a rung's margin-adjusted [floor,cap] band is an "item-2b entry" -- this
is the SAME construction pmkt_final_verdict.py / tracka_chicago_1min.py used, just with ALL entries priced
(no 2-per-day win/prior-loss subsample) and priced at a MEASURED pmxt.dev best_ask instead of a last-trade+
half-spread proxy.

DATA SOURCES (all recon-verified in venue_expansion/out/{feedhunt_*,venues_pmkt_product}.json):
  - Chicago:  IEM TRUE 1-minute ASOS archive (asos1min.py), station ORD. REUSES tracka_chicago_1min.py's
              own on-disk cache verbatim (venue_expansion/cache/tracka_chicago_1min/) -- that harness
              already pulled this exact station/feed/date-range combination; re-fetching would violate the
              cache-then-delete politeness non-negotiable for data already on disk. Falls back to a fresh
              fetch (written to this spec's OWN cache dir) only for any date tracka's cache doesn't have.
  - Tokyo:    JMA 10-minute AMeDAS historical viewer (data.jma.go.jp/stats/etrn/view/10min_a1.php),
              prec_no=44/block_no=0371 ("Haneda", co-located with RJTT). One HTML page per JST calendar
              day (144 rows each); no bulk endpoint exists per feedhunt_tokyo.json, so this is a real
              per-day fetch loop, politely paced.
  - London:   IEM global ASOS/METAR mirror (asos.py), station EGLC, report_type=3&report_type=4 (routine
              AND special reports -- feedhunt_london.json's correction to pmkt_final_verdict.py's
              report_type=3-only undercount bug: this gets the true 48 rows/day, not 24-25).
  - Paris:    Same IEM mirror, station LFPB, same report_type=3&4 fix (feedhunt_paris.json).
  London/Paris are fetched in ONE bulk multi-day request each (asos.py supports arbitrary day ranges) --
  cheaper and more polite than 96 separate per-day calls for a feed that already returns the whole window
  in one response.
  - Ladders/outcomes: gamma-api event-slug harness, reused VERBATIM from tracka_chicago_1min.py
    (parse_rung_native, event_rungs_native, fetch_event -- same slug pattern, same bracket parsing).
  - Prices: pmxt.dev hourly order-book parquet archive (r2v2.pmxt.dev/polymarket_orderbook_<hour>.parquet),
    read via pyarrow+fsspec HTTP range reads, column-projected (timestamp_received, asset_id, event_type,
    best_ask) and filtered to the specific asset_ids needed in that hour -- NOT a full-file download.

MIRRORING DIVERGENCE (disclosed, not silent): the data_plan says "mirror every hour-file used into
venue_expansion/cache/". Each pmxt.dev hour-file is ~470MB (measured; see recon and this script's own
probe). At the sample scale this spec's min_n requires (>=120 priced fires, realistically several hundred
candidate hour-files across a 96-day/4-city window), mirroring every FULL hour-file would require tens to
hundreds of GB of disk -- ~30GB is available on this machine, so literal full-file mirroring is physically
infeasible at this scale, not merely impolite. What this script mirrors instead: for every hour-file it
reads, the FILTERED extraction actually used (every matching row for every asset_id on that hour's
watchlist, i.e. every row this spec's own accounting depends on) is cached to
venue_expansion/cache/spec_s1/pmxt_hour_<hour>.json. This is a smaller reproducibility surface than "the
whole file" but a STRICT SUPERSET of "every data point this study's numbers depend on" -- a re-run from
this cache alone (--cached-only) reproduces the exact same ev_results without re-touching pmxt.dev. This
is an infrastructure/disk-practicality adaptation, not a change to the entry rule, EV accounting, sample
universe, or pass bar.

PERFORMANCE NOTE (measured, not assumed): a naive serial column-projected read of one pmxt.dev hour-file
(3 columns out of 16, all 79 row groups) took 64.4s in a live timed probe; a 16-way parallel read of the
SAME file (ThreadPoolExecutor over row groups, each with its own fsspec HTTP handle) took 12.5s -- confirmed
this is network-latency-bound (32/48-way parallelism did not help further, sometimes hurt). This script
uses a 16-worker pool per hour-file fetch throughout.

USAGE:
  python spec_S1.py                  # full run: fetch (or reuse cache), backtest, price, verdict
  python spec_S1.py --cached-only    # recompute entirely from on-disk cache, no network calls at all

Read-only, public APIs/archives only (Gamma, IEM Mesonet, JMA, pmxt.dev). No auth, no orders, no trading
code. Polite: cached, retried with backoff, ~1 req/sec on per-request feeds.
"""
import bisect
import glob
import json
import math
import os
import re
import ssl
import statistics as st
import sys
import time
import urllib.error
import urllib.request
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import fsspec

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kwx_lock_rule as R   # deployed lock-rule shim: sustained_extreme, locked_orders (byte-identical,
                             # see kwx_lock_rule.py's own provenance docstring)

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "*/*", "User-Agent": "Mozilla/5.0 (compatible; spec-s1/1.0)"}

GBASE = "https://gamma-api.polymarket.com"
DAILY_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
ASOS_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
JMA_10MIN = "https://www.data.jma.go.jp/stats/etrn/view/10min_a1.php"
PMXT_TPL = "https://r2v2.pmxt.dev/polymarket_orderbook_{h}.parquet"

CACHE_DIR = os.path.join(HERE, "cache", "spec_s1")
TRACKA_CACHE_DIR = os.path.join(HERE, "cache", "tracka_chicago_1min")
OUT_DIR = os.path.join(HERE, "out")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# --------------------------------------------------------------------------------------------------------
# PRE-REGISTERED constants (frozen before any data was read; see the spec text in judge_specs.json / the
# BACKTEST WORKER task this script was authored against)
# --------------------------------------------------------------------------------------------------------
WINDOW_START = dt.date(2026, 4, 14)
WINDOW_END = dt.date(2026, 7, 18)
PMXT_COVERAGE_START = dt.datetime(2026, 4, 13, 19, 0, tzinfo=dt.timezone.utc)

CITIES = {
    "chicago": dict(station="ORD", unit="F", tz="America/Chicago", margin=1.0, feed="chicago_1min"),
    "tokyo":   dict(station="RJTT", unit="C", tz="Asia/Tokyo",   margin=0.5, feed="jma_10min",
                     jma_prec=44, jma_block="0371"),
    "london":  dict(station="EGLC", unit="C", tz="Europe/London", margin=0.5, feed="iem_30min"),
    "paris":   dict(station="LFPB", unit="C", tz="Europe/Paris",  margin=0.5, feed="iem_30min"),
}

# completeness guards per feed cadence (precedent-consistent with pmkt_final_verdict.py's ~62%-of-native-
# cadence hourly guard and tracka_chicago_1min.py's own established 1-min guard; NOT tuned against this
# spec's own outcomes -- set once, before backtest_day was ever called on real obs).
GUARDS = {
    "chicago_1min": dict(min_day_obs=100, max_end_gap_h=3, pad_pre_h=1, pad_post_h=3),
    "iem_30min":    dict(min_day_obs=30,  max_end_gap_h=4, pad_pre_h=2, pad_post_h=4),   # 48/day native
    "jma_10min":    dict(min_day_obs=90,  max_end_gap_h=4, pad_pre_h=0, pad_post_h=0),   # 144/day native;
                    # JMA fetch is already scoped to the exact local (JST) day, no UTC padding needed
}

PMKT_WEATHER_FEE_RATE = 0.05     # fee = shares * 0.05 * p * (1-p), taker-only (verified live feeSchedule,
                                  # reused unmodified from pmkt_final_verdict.py / GROUNDING.md #3)
ASK_SEARCH_WINDOW_MIN = 60       # entry_rule: no ask event within 60 min => UNPRICEABLE


# ============================================================================================================
# low-level HTTP helpers (byte-identical style to tracka_chicago_1min.py)
# ============================================================================================================
def _get_text(url, timeout=40, retries=6, backoff=2.0):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return urllib.request.urlopen(req, timeout=timeout, context=_CTX).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
        except Exception as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
    print(f"    !! _get_text FAILED after {retries} tries: {url} -- {last_err}", file=sys.stderr)
    return None


def _get_json(url, timeout=25, retries=5, backoff=1.6):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 404:
                return {"__404__": True}
            if e.code not in (429, 500, 502, 503, 504):
                return {"__err__": f"HTTP {e.code}"}
            time.sleep(backoff * (attempt + 1))
        except Exception as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
    return {"__err__": f"{type(last_err).__name__}: {last_err}"}


def _cache_path(name):
    return os.path.join(CACHE_DIR, name)


def _cache_get(name):
    p = _cache_path(name)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        try:
            return json.load(open(p))
        except Exception:
            return None
    return None


def _cache_put(name, obj):
    json.dump(obj, open(_cache_path(name), "w"))


# ============================================================================================================
# bracket parsing + gamma-api ladder harness -- REUSED VERBATIM from tracka_chicago_1min.py
# ============================================================================================================
def parse_rung_native(label):
    s = label.replace("°F", "").replace("°C", "").strip()
    if "or below" in s:
        return None, float(s.split()[0]) + 0.5
    if "or higher" in s or "or above" in s:
        return float(s.split()[0]) - 0.5, None
    if "-" in s:
        lo, hi = s.split("-")
        return float(lo) - 0.5, float(hi) + 0.5
    v = float(s)
    return v - 0.5, v + 0.5


def event_rungs_native(event, unit):
    mkts = event.get("markets", [])
    if not mkts:
        return None
    rungs, titles, winner = [], {}, None
    for m in mkts:
        if not m.get("closed"):
            return None
        label = m.get("groupItemTitle", "")
        floor, cap = parse_rung_native(label)
        try:
            tok_ids = json.loads(m.get("clobTokenIds") or "[]")
        except Exception:
            tok_ids = []
        ticker = m.get("id") or label
        titles[ticker] = label
        try:
            prices = json.loads(m["outcomePrices"]) if isinstance(m["outcomePrices"], str) else m["outcomePrices"]
        except Exception:
            prices = []
        if prices and abs(float(prices[0]) - 1.0) < 1e-6:
            winner = ticker
        rungs.append({"ticker": ticker, "floor": floor, "cap": cap,
                       "yes_ask_c": 50, "no_ask_c": 50,
                       "yes_tok": tok_ids[0] if len(tok_ids) > 0 else None,
                       "no_tok": tok_ids[1] if len(tok_ids) > 1 else None})
    if winner is None:
        return None
    return rungs, titles, winner


def fetch_event(city_slug, d):
    slug = f"highest-temperature-in-{city_slug}-on-{d.strftime('%B').lower()}-{d.day}-{d.year}"
    key = f"event_{slug}.json"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    ev = _get_json(f"{GBASE}/events/slug/{slug}")
    _cache_put(key, ev)
    time.sleep(0.4)
    return ev


# ============================================================================================================
# WEATHER FEEDS
# ============================================================================================================
def _daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


# ---- Chicago: IEM TRUE 1-minute ASOS, reuse tracka_chicago_1min.py's own on-disk cache verbatim ----------
def fetch_chicago_1min_day(d):
    tz = ZoneInfo("America/Chicago")
    day_start = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz).astimezone(dt.timezone.utc)
    day_end = day_start + dt.timedelta(days=1)
    g = GUARDS["chicago_1min"]
    start_utc = day_start - dt.timedelta(hours=g["pad_pre_h"])
    end_utc = day_end + dt.timedelta(hours=g["pad_post_h"])
    key = f"asos1min_ORD_{start_utc:%Y%m%dT%H%M}_{end_utc:%Y%m%dT%H%M}.json"
    tracka_p = os.path.join(TRACKA_CACHE_DIR, key)
    if os.path.exists(tracka_p):
        raw = json.load(open(tracka_p))
        obs = [(dt.datetime.fromisoformat(t), v) for t, v in raw]
        return obs, day_start, day_end, "tracka_cache_reused"
    own_p = _cache_path(key)
    if os.path.exists(own_p):
        raw = json.load(open(own_p))
        obs = [(dt.datetime.fromisoformat(t), v) for t, v in raw]
        return obs, day_start, day_end, "own_cache"
    sts = start_utc.strftime("%Y-%m-%dT%H:%MZ")
    ets = end_utc.strftime("%Y-%m-%dT%H:%MZ")
    q = f"station=ORD&vars=tmpf&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma"
    txt = _get_text(f"{ASOS_1MIN}?{q}")
    out = []
    if txt:
        for line in txt.splitlines():
            if not line or line.startswith("station,"):
                continue
            parts = line.split(",")
            if len(parts) < 4:
                continue
            valid, tmpf = parts[2], parts[3]
            if tmpf in ("", "M"):
                continue
            try:
                t = dt.datetime.strptime(valid.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                v = float(tmpf)
            except ValueError:
                continue
            out.append((t, v))
    out.sort(key=lambda x: x[0])
    _cache_put(key, [(t.isoformat(), v) for t, v in out])
    time.sleep(1.0)
    return out, day_start, day_end, "fetched_live"


# ---- London / Paris: IEM global ASOS mirror, ONE bulk multi-day request each, report_type=3&4 -------------
def fetch_iem_bulk(station):
    key = f"asos_bulk_{station}_{WINDOW_START}_{WINDOW_END}.json"
    cached = _cache_get(key)
    if cached is not None:
        return [(dt.datetime.fromisoformat(t), v) for t, v in cached]
    start = WINDOW_START - dt.timedelta(days=1)
    end_pad = WINDOW_END + dt.timedelta(days=2)   # asos.py day2 is EXCLUSIVE (measured quirk, see
                                                    # pmkt_final_verdict.py) -- +1 for the pad day, +1 more
                                                    # to actually include WINDOW_END itself
    q = (f"station={station}&data=tmpf&year1={start.year}&month1={start.month}&day1={start.day}"
         f"&year2={end_pad.year}&month2={end_pad.month}&day2={end_pad.day}"
         f"&tz=UTC&format=onlycomma&latlon=no&elev=no&missing=M&trace=T&direct=no"
         f"&report_type=3&report_type=4")
    txt = _get_text(f"{DAILY_ASOS}?{q}")
    out = []
    if txt:
        for line in txt.splitlines():
            if not line or line.startswith("station,"):
                continue
            parts = line.split(",")
            if len(parts) < 3:
                continue
            valid, tmpf = parts[1], parts[2]
            if tmpf in ("", "M", "T"):
                continue
            try:
                t = dt.datetime.strptime(valid.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                v = float(tmpf)
            except ValueError:
                continue
            out.append((t, v))
    out.sort(key=lambda x: x[0])
    _cache_put(key, [(t.isoformat(), v) for t, v in out])
    time.sleep(1.0)
    return out


def slice_day(obs_all, tz_name, d, pad_pre_h, pad_post_h):
    tz = ZoneInfo(tz_name)
    day_start = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz).astimezone(dt.timezone.utc)
    day_end = day_start + dt.timedelta(days=1)
    day_obs = [(t, v) for t, v in obs_all if day_start <= t < day_end]
    return day_obs, day_start, day_end


# ---- Tokyo: JMA 10-minute AMeDAS historical viewer, one HTML page per JST calendar day --------------------
_JMA_ROW_RE = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
_JMA_CELL_RE = re.compile(r'<td[^>]*>(.*?)</td>', re.S)


def fetch_jma_day(d, prec_no, block_no):
    key = f"jma_{prec_no}_{block_no}_{d.isoformat()}.json"
    cached = _cache_get(key)
    if cached is not None:
        return [(dt.datetime.fromisoformat(t), v) for t, v in cached]
    url = f"{JMA_10MIN}?prec_no={prec_no}&block_no={block_no}&year={d.year}&month={d.month}&day={d.day}&view="
    html = _get_text(url)
    out = []
    if html:
        m = re.search(r'<table[^>]*id="tablefix1"[^>]*>(.*?)</table>', html, re.S)
        body = m.group(1) if m else html
        tz = ZoneInfo("Asia/Tokyo")
        for rowhtml in _JMA_ROW_RE.findall(body):
            cells = [c.strip() for c in _JMA_CELL_RE.findall(rowhtml)]
            if len(cells) < 3:
                continue
            tstr, temp_s = cells[0], cells[2]
            if temp_s in ("", "///", "--", "-"):
                continue
            try:
                temp_c = float(temp_s)
            except ValueError:
                continue
            try:
                hh, mm = tstr.split(":")
                hh, mm = int(hh), int(mm)
            except ValueError:
                continue
            if hh == 24:   # JMA labels JST 24:00 as the day's final row == next day's 00:00
                local_dt = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz) + dt.timedelta(days=1)
            else:
                local_dt = dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz)
            out.append((local_dt.astimezone(dt.timezone.utc), temp_c))
    out.sort(key=lambda x: x[0])
    _cache_put(key, [(t.isoformat(), v) for t, v in out])
    time.sleep(1.0)
    return out


# ============================================================================================================
# BACKTEST WALK -- IDENTICAL construction to tracka_chicago_1min.py / pmkt_final_verdict.py's backtest_day,
# generalized to record item-2b entries for EVERY rung (not a 2-per-day subsample) as required by this
# spec's entry_rule ("ALL entries in the window priced (no selection among fires)").
# ============================================================================================================
def backtest_day(city_slug, d, cfg, day_obs, min_day_obs, max_end_gap_h, day_start, day_end):
    unit, margin = cfg["unit"], cfg["margin"]
    ev = fetch_event(city_slug, d)
    if not isinstance(ev, dict) or "__err__" in ev or "__404__" in ev:
        return {"skip": "event_not_found"}
    parsed = event_rungs_native(ev, unit)
    if parsed is None:
        return {"skip": "not_resolved_or_unparseable"}
    rungs, titles, winner_ticker = parsed

    if len(day_obs) < min_day_obs:
        return {"skip": f"thin_station_data_{len(day_obs)}obs"}
    if day_obs[-1][0] < day_end - dt.timedelta(hours=max_end_gap_h):
        return {"skip": "station_feed_gap_near_dayend"}

    locked = {}
    entries = {}   # ticker -> {"entry_utc":..., "extreme_native":...} -- ALL rungs, item-2b, unmodified
    obs_stream = list(day_obs)
    for i in range(1, len(obs_stream) + 1):
        window = obs_stream[:i]
        extreme_f = R.sustained_extreme([(t.isoformat(), v) for t, v in window], "max")
        if extreme_f is None:
            continue
        extreme_native = extreme_f if unit == "F" else (extreme_f - 32.0) * 5.0 / 9.0
        ts_iso = window[-1][0].isoformat()

        fires = R.locked_orders(rungs, extreme_native, "max", margin=margin)
        for ticker, side, _cap_c, cushion in fires:
            if ticker not in locked:
                locked[ticker] = {"side": side, "lock_utc": ts_iso,
                                   "extreme_native": round(extreme_native, 2), "cushion": round(cushion, 2)}

        for r in rungs:
            if r["ticker"] in entries:
                continue
            floor, cap = r["floor"], r["cap"]
            in_band = (floor is None or extreme_native > floor + margin) and \
                      (cap is None or extreme_native <= cap + margin)
            if in_band:
                entries[r["ticker"]] = {"entry_utc": ts_iso, "extreme_native": round(extreme_native, 2)}

    if not locked and not entries:
        return {"skip": "no_lock_reached", "winner": winner_ticker}

    lock_records = []
    for ticker, info in locked.items():
        correct = (ticker == winner_ticker) if info["side"] == "yes" else (ticker != winner_ticker)
        lock_records.append({"city": city_slug, "date": d.isoformat(), "ticker": ticker,
                              "label": titles.get(ticker), "side": info["side"],
                              "lock_utc": info["lock_utc"], "correct": correct, "cushion": info["cushion"]})

    entry_records = []
    for ticker, info in entries.items():
        rung = next(r for r in rungs if r["ticker"] == ticker)
        entry_records.append({"city": city_slug, "date": d.isoformat(), "ticker": ticker,
                               "label": titles.get(ticker), "entry_utc": info["entry_utc"],
                               "yes_tok": rung["yes_tok"],
                               "correct": (ticker == winner_ticker), "won": (ticker == winner_ticker)})

    return {"skip": None, "lock_records": lock_records, "entry_records": entry_records,
            "winner": winner_ticker, "n_rungs": len(rungs), "n_day_obs": len(day_obs),
            "winner_never_entered": winner_ticker not in entries}


# ============================================================================================================
# PHASE 1 -- weather-only pass across all 4 cities, full window. NO pmxt/market data touched here (entry_rule:
# "computed ONLY from the weather feed -- no market-price or outcome input" applies to signal detection;
# outcome (winner) is read from gamma-api only to SCORE the fire after the fact, never to shape the signal).
# ============================================================================================================
def run_weather_pass(cached_only=False):
    all_lock_records, all_entry_records, skips = [], [], []
    per_day_log = []
    for city_slug, cfg in CITIES.items():
        feed = cfg["feed"]
        guard = GUARDS[feed]
        print(f"\n[{city_slug}] feed={feed} station={cfg['station']} unit={cfg['unit']} margin={cfg['margin']}")

        bulk_obs = None
        if feed == "iem_30min":
            if cached_only:
                key = f"asos_bulk_{cfg['station']}_{WINDOW_START}_{WINDOW_END}.json"
                cached = _cache_get(key)
                bulk_obs = [(dt.datetime.fromisoformat(t), v) for t, v in cached] if cached else []
            else:
                bulk_obs = fetch_iem_bulk(cfg["station"])
            print(f"    bulk IEM pull: {len(bulk_obs)} rows across the whole window")

        for d in _daterange(WINDOW_START, WINDOW_END):
            if feed == "chicago_1min":
                if cached_only:
                    tz = ZoneInfo(cfg["tz"])
                    day_start = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz).astimezone(dt.timezone.utc)
                    day_end = day_start + dt.timedelta(days=1)
                    g = GUARDS["chicago_1min"]
                    su = day_start - dt.timedelta(hours=g["pad_pre_h"])
                    eu = day_end + dt.timedelta(hours=g["pad_post_h"])
                    key = f"asos1min_ORD_{su:%Y%m%dT%H%M}_{eu:%Y%m%dT%H%M}.json"
                    p = os.path.join(TRACKA_CACHE_DIR, key)
                    if not os.path.exists(p):
                        p = _cache_path(key)
                    raw = json.load(open(p)) if os.path.exists(p) else []
                    day_obs = [(dt.datetime.fromisoformat(t), v) for t, v in raw]
                    day_obs = [(t, v) for t, v in day_obs if day_start <= t < day_end]
                else:
                    day_obs, day_start, day_end, _src = fetch_chicago_1min_day(d)
                    day_obs = [(t, v) for t, v in day_obs if day_start <= t < day_end]
            elif feed == "iem_30min":
                day_obs, day_start, day_end = slice_day(bulk_obs, cfg["tz"], d, guard["pad_pre_h"], guard["pad_post_h"])
            elif feed == "jma_10min":
                if cached_only:
                    key = f"jma_{cfg['jma_prec']}_{cfg['jma_block']}_{d.isoformat()}.json"
                    cached = _cache_get(key)
                    day_obs_c = [(dt.datetime.fromisoformat(t), v) for t, v in cached] if cached else []
                else:
                    day_obs_c = fetch_jma_day(d, cfg["jma_prec"], cfg["jma_block"])
                # kwx_lock_rule.sustained_extreme's glitch-filter constants (GLITCH_HI_F/LO_F=130/-60, the
                # >8.0 single-step jump filter) and this module's own end-of-pipeline unit conversion
                # (extreme_native = (extreme_f-32)*5/9 for unit=="C") are BOTH written assuming the obs
                # stream fed into sustained_extreme is already in Fahrenheit -- exactly matching how every
                # OTHER feed in this script works (Chicago's asos1min and London/Paris's asos.py both
                # request `data=tmpf`/`vars=tmpf`, Fahrenheit, regardless of the city's native display
                # unit; pmkt_final_verdict.py/tracka_chicago_1min.py established this convention). JMA has
                # no Fahrenheit option -- it returns native Celsius -- so convert C->F HERE, at the fetch
                # boundary, to preserve that convention rather than special-casing backtest_day per feed.
                day_obs = [(t, c * 9.0 / 5.0 + 32.0) for t, c in day_obs_c]
                tz = ZoneInfo(cfg["tz"])
                day_start = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz).astimezone(dt.timezone.utc)
                day_end = day_start + dt.timedelta(days=1)
            else:
                raise ValueError(feed)

            r = backtest_day(city_slug, d, cfg, day_obs, guard["min_day_obs"], guard["max_end_gap_h"],
                              day_start, day_end)
            if r.get("skip"):
                skips.append(f"{city_slug} {d}: {r['skip']}")
                continue
            all_lock_records.extend(r["lock_records"])
            all_entry_records.extend(r["entry_records"])
            per_day_log.append({"city": city_slug, "date": d.isoformat(), "n_day_obs": r["n_day_obs"],
                                 "n_entries": len(r["entry_records"]), "winner": r["winner"],
                                 "winner_never_entered": r["winner_never_entered"]})
            print(f"    OK   {d}  {len(r['entry_records'])} entries, {len(r['lock_records'])} pure-rule "
                  f"lock(s), n_obs={r['n_day_obs']}, winner={r['winner']}")

    return all_lock_records, all_entry_records, skips, per_day_log


# ============================================================================================================
# PHASE 2 -- pmxt.dev pricing. Batched, single-pass-per-hour-file strategy: (1) collect the distinct set of
# PRIMARY hours needed (entry_utc's own UTC hour) across every entry_record, fetch+cache each such hour file
# EXACTLY ONCE, extracting only rows for that hour's asset_id watchlist; (2) for entries whose primary hour
# had no qualifying ask (>= entry_utc, within the 60-min window), fetch the CONTINUATION hour (entry_hour+1)
# the same way, again exactly once per distinct hour needed. This turns "one query per fire" (infeasible at
# this file size -- see module docstring's measured 64s/12.5s probe) into "one query per DISTINCT hour-file
# actually touched", with each hour-file's 79 row groups read in parallel (16 workers).
# ============================================================================================================
def _hour_str(dt_utc):
    return dt_utc.strftime("%Y-%m-%dT%H")


# module-level counter (spec-kill check: "pmxt.dev missing/unreadable for >20% of needed hour-files") --
# a plain global is fine here, this script is single-process/single-threaded at the orchestration level
# (only the row-group reads within one hour-file are themselves multi-threaded).
HOUR_FETCH_STATS = {"attempted": 0, "unreadable": 0, "hours": {}}


def fetch_pmxt_hour_filtered(hour_str, asset_ids, cached_only=False):
    """Return list of (asset_id, timestamp_received_iso, best_ask_float) for the given hour, restricted to
    `asset_ids`. Cached per (hour, sorted-asset-id-set) so re-running with a superset of a previously-cached
    watchlist still requires a re-fetch (documented: cache key includes the asset set actually requested)."""
    ids_key = "_".join(sorted(asset_ids))[:200]  # bounded key length; full set also stored inside the file
    cache_name = f"pmxt_hour_{hour_str}_{abs(hash(tuple(sorted(asset_ids)))) % (10**10)}.json"
    cached = _cache_get(cache_name)
    if cached is not None and set(cached.get("asset_ids", [])) >= set(asset_ids):
        if hour_str not in HOUR_FETCH_STATS["hours"]:
            HOUR_FETCH_STATS["hours"][hour_str] = True
            HOUR_FETCH_STATS["attempted"] += 1
            if cached.get("unreadable"):
                HOUR_FETCH_STATS["unreadable"] += 1
        return cached["rows"]
    if cached_only:
        return []

    if hour_str not in HOUR_FETCH_STATS["hours"]:
        HOUR_FETCH_STATS["hours"][hour_str] = True
        HOUR_FETCH_STATS["attempted"] += 1

    url = PMXT_TPL.format(h=hour_str)
    try:
        fs = fsspec.filesystem("https")
        of = fs.open(url, "rb")
        pf = pq.ParquetFile(of)
        n_rg = pf.num_row_groups
    except Exception as e:
        print(f"    !! pmxt hour-file unreadable {hour_str}: {e}", file=sys.stderr)
        HOUR_FETCH_STATS["unreadable"] += 1
        _cache_put(cache_name, {"asset_ids": sorted(asset_ids), "rows": [], "unreadable": True,
                                 "error": str(e)})
        return []

    watch = set(asset_ids)
    watch_arr = pa.array(sorted(watch), type=pa.string())
    cols = ["timestamp_received", "asset_id", "best_ask"]

    def read_rg(i):
        try:
            of_i = fs.open(url, "rb")
            pf_i = pq.ParquetFile(of_i)
            tbl = pf_i.read_row_group(i, columns=cols)
        except Exception:
            return []
        # VECTORIZED filter (pyarrow.compute, not a per-row Python loop -- a per-row .as_py() loop over up
        # to ~1.05M rows/row-group was measured live to dominate wall time, ~40-50s/hour-file vs the raw
        # I/O-only ~12.5s probe in this module's docstring; this is the fix for that measured slowdown).
        mask = pc.and_(pc.is_in(tbl.column("asset_id"), value_set=watch_arr),
                        pc.is_valid(tbl.column("best_ask")))
        sub = tbl.filter(mask)
        if sub.num_rows == 0:
            return []
        aids = sub.column("asset_id").to_pylist()
        bas = sub.column("best_ask").to_pylist()
        trs = sub.column("timestamp_received").to_pylist()
        return [(aid, tr.isoformat(), float(ba)) for aid, tr, ba in zip(aids, trs, bas)]

    t0 = time.time()
    all_rows = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for chunk in ex.map(read_rg, range(n_rg)):
            all_rows.extend(chunk)
    elapsed = time.time() - t0
    print(f"    pmxt hour {hour_str}: {n_rg} row groups, {len(all_rows)} matching rows for "
          f"{len(watch)} asset(s), {elapsed:.1f}s")
    _cache_put(cache_name, {"asset_ids": sorted(asset_ids), "rows": all_rows,
                             "n_row_groups": n_rg, "elapsed_s": round(elapsed, 1)})
    return all_rows


def price_entries(entry_records, cached_only=False):
    """Fills each entry_record dict in-place with pricing fields and returns the same list."""
    # ---- restrict to entries inside pmxt coverage, sorted by entry time so hour-batches are chronological
    priceable_candidates = []
    for e in entry_records:
        entry_dt = dt.datetime.fromisoformat(e["entry_utc"])
        if entry_dt.tzinfo is None:
            entry_dt = entry_dt.replace(tzinfo=dt.timezone.utc)
        e["_entry_dt"] = entry_dt
        if entry_dt < PMXT_COVERAGE_START:
            e["price_status"] = "before_pmxt_coverage"
            continue
        if not e.get("yes_tok"):
            e["price_status"] = "no_yes_token"
            continue
        priceable_candidates.append(e)
    priceable_candidates.sort(key=lambda e: e["_entry_dt"])

    # ---- phase A: primary hour ----
    hour_to_entries = {}
    for e in priceable_candidates:
        h = _hour_str(e["_entry_dt"])
        hour_to_entries.setdefault(h, []).append(e)

    for h in sorted(hour_to_entries):
        ents = hour_to_entries[h]
        asset_ids = sorted({e["yes_tok"] for e in ents})
        rows = fetch_pmxt_hour_filtered(h, asset_ids, cached_only=cached_only)
        by_asset = {}
        for aid, ts_iso, ba in rows:
            by_asset.setdefault(aid, []).append((ts_iso, ba))
        for aid in by_asset:
            by_asset[aid].sort(key=lambda x: x[0])
        for e in ents:
            cand = by_asset.get(e["yes_tok"], [])
            window_end = e["_entry_dt"] + dt.timedelta(minutes=ASK_SEARCH_WINDOW_MIN)
            hit = None
            for ts_iso, ba in cand:
                ts = dt.datetime.fromisoformat(ts_iso)
                if ts >= e["_entry_dt"] and ts < window_end:
                    hit = (ts, ba)
                    break
            if hit is not None:
                e["_priced_ts"] = hit[0].isoformat()
                e["_ask_frac"] = hit[1]
                e["price_status"] = "priced_primary_hour"
            else:
                e["price_status"] = "needs_continuation"

    # ---- phase B: continuation hour, only for entries phase A didn't resolve ----
    need_cont = [e for e in priceable_candidates if e["price_status"] == "needs_continuation"]
    hour_to_cont = {}
    for e in need_cont:
        window_end = e["_entry_dt"] + dt.timedelta(minutes=ASK_SEARCH_WINDOW_MIN)
        cont_hour_dt = e["_entry_dt"].replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
        if cont_hour_dt >= window_end:
            e["price_status"] = "unpriceable_no_ask_in_60min"
            continue
        h = _hour_str(cont_hour_dt)
        hour_to_cont.setdefault(h, []).append(e)

    for h in sorted(hour_to_cont):
        ents = hour_to_cont[h]
        asset_ids = sorted({e["yes_tok"] for e in ents})
        rows = fetch_pmxt_hour_filtered(h, asset_ids, cached_only=cached_only)
        by_asset = {}
        for aid, ts_iso, ba in rows:
            by_asset.setdefault(aid, []).append((ts_iso, ba))
        for aid in by_asset:
            by_asset[aid].sort(key=lambda x: x[0])
        for e in ents:
            cand = by_asset.get(e["yes_tok"], [])
            window_end = e["_entry_dt"] + dt.timedelta(minutes=ASK_SEARCH_WINDOW_MIN)
            hit = None
            for ts_iso, ba in cand:
                ts = dt.datetime.fromisoformat(ts_iso)
                if ts >= e["_entry_dt"] and ts < window_end:
                    hit = (ts, ba)
                    break
            if hit is not None:
                e["_priced_ts"] = hit[0].isoformat()
                e["_ask_frac"] = hit[1]
                e["price_status"] = "priced_continuation_hour"
            else:
                e["price_status"] = "unpriceable_no_ask_in_60min"

    for e in entry_records:
        e.pop("_entry_dt", None)
    return entry_records


def pmkt_fee_cents(ask_cents):
    p = ask_cents / 100.0
    return PMKT_WEATHER_FEE_RATE * p * (1 - p) * 100.0


# ============================================================================================================
# STATS -- Wilson CI (unchanged formula reused across this repo's studies) + day-clustered t-stat (standard
# cluster-robust SE of a mean, Cameron-Gelbach-Miller CR1 form, applied to a constant-only "regression":
# residual_i = y_i - ybar (pooled, per-fire mean); Var_CR = (N/(N-1))*(G/(G-1)) * sum_g(S_g^2) / N^2 where
# S_g is the summed residual within cluster g; t = ybar / sqrt(Var_CR), df = G-1).
# ============================================================================================================
def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def clustered_t(values, cluster_ids):
    n = len(values)
    if n < 2:
        return None
    ybar = st.mean(values)
    resid = [v - ybar for v in values]
    clusters = {}
    for c, r in zip(cluster_ids, resid):
        clusters.setdefault(c, []).append(r)
    G = len(clusters)
    if G < 2:
        return None
    sum_sq = sum(sum(rs) ** 2 for rs in clusters.values())
    var = (n / (n - 1)) * (G / (G - 1)) * sum_sq / (n * n)
    se = math.sqrt(var) if var > 0 else None
    t = (ybar / se) if se and se > 0 else None
    return {"mean": ybar, "se": se, "t": t, "n": n, "n_clusters": G, "df": G - 1}


# ============================================================================================================
# MAIN
# ============================================================================================================
def run(cached_only=False):
    t_start = time.time()
    print("=" * 100)
    print("SPEC S1 -- Polymarket whitelist EV at MEASURED asks (pmxt.dev order-book archive)")
    print(f"Window: {WINDOW_START} .. {WINDOW_END}  (pmxt coverage from {PMXT_COVERAGE_START.isoformat()})")
    print("=" * 100)

    lock_records, entry_records, skips, per_day_log = run_weather_pass(cached_only=cached_only)
    usable_city_days = len({(x["city"], x["date"]) for x in entry_records} |
                            {(x["city"], x["date"]) for x in lock_records} |
                            {(x["city"], x["date"]) for x in per_day_log})
    print("\n" + "=" * 100)
    print(f"PHASE 1 DONE: {usable_city_days} usable city-days ({len(skips)} skipped), "
          f"{len(entry_records)} total item-2b entries, {len(lock_records)} pure-rule locks (non-gating)")
    print("=" * 100)

    print(f"\nPHASE 2 -- pricing all {len(entry_records)} entries at measured pmxt.dev best_ask...")
    entry_records = price_entries(entry_records, cached_only=cached_only)

    status_counts = {}
    for e in entry_records:
        status_counts[e["price_status"]] = status_counts.get(e["price_status"], 0) + 1
    print("\nPricing status breakdown:")
    for k, v in sorted(status_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")

    priced = [e for e in entry_records if e["price_status"] in ("priced_primary_hour", "priced_continuation_hour")]
    unpriceable = [e for e in entry_records if e["price_status"] == "unpriceable_no_ask_in_60min"]
    n_in_window = len(priced) + len(unpriceable)   # denominator for the >40% unpriceable selection-bias flag
                                                     # (excludes entries structurally outside pmxt coverage or
                                                     # missing a yes_tok, which are not pmxt "misses")

    ev_results = []
    for e in priced:
        ask_c = e["_ask_frac"] * 100.0
        fee_c = pmkt_fee_cents(ask_c)
        payout_c = 100.0 if e["won"] else 0.0
        net_c = payout_c - ask_c - fee_c
        ev_results.append({
            "city": e["city"], "date": e["date"], "ticker": e["ticker"], "label": e["label"],
            "entry_utc": e["entry_utc"], "priced_ts": e["_priced_ts"], "won": e["won"],
            "ask_c": round(ask_c, 4), "fee_c": round(fee_c, 5), "payout_c": payout_c,
            "net_ev_c": round(net_c, 5), "price_status": e["price_status"],
        })

    n_priced = len(ev_results)
    n_clusters = len({(x["city"], x["date"]) for x in ev_results})
    frac_unpriceable = (len(unpriceable) / n_in_window) if n_in_window else None

    print("\n" + "=" * 100)
    print(f"PRICED FIRES: n={n_priced} across {n_clusters} city-day clusters "
          f"({len(unpriceable)} unpriceable within pmxt coverage, "
          f"{100*frac_unpriceable:.1f}% of {n_in_window} in-coverage entries)" if n_in_window else
          f"PRICED FIRES: n={n_priced} (no in-coverage entries)")
    print("=" * 100)

    # ---- KILL / SPEC-KILL checks ----
    frac_hour_unreadable = (HOUR_FETCH_STATS["unreadable"] / HOUR_FETCH_STATS["attempted"]) \
        if HOUR_FETCH_STATS["attempted"] else None
    print(f"\npmxt hour-file reads: {HOUR_FETCH_STATS['attempted']} distinct hour-files attempted, "
          f"{HOUR_FETCH_STATS['unreadable']} unreadable "
          f"({f'{100*frac_hour_unreadable:.1f}%' if frac_hour_unreadable is not None else '--'})")

    spec_kill = None
    if frac_hour_unreadable is not None and frac_hour_unreadable > 0.20:
        spec_kill = (f"pmxt.dev unreadable for >20% of needed hour-files "
                     f"({100*frac_hour_unreadable:.1f}% of {HOUR_FETCH_STATS['attempted']})")
    elif n_in_window and frac_unpriceable is not None and frac_unpriceable > 0.40:
        spec_kill = f">40% unpriceable ({100*frac_unpriceable:.1f}% of {n_in_window})"
    if n_priced < 120 or n_clusters < 40:
        thin = True
    else:
        thin = False

    verdict = None
    net_vals = [e["net_ev_c"] for e in ev_results]
    day_clustered = None
    calendar_date_clustered = None
    wilson_win = None
    kill_bound_c = None
    pass_mean_ok = None
    pass_t_ok = None

    if n_priced:
        day_clustered = clustered_t(net_vals, [(e["city"], e["date"]) for e in ev_results])
        calendar_date_clustered = clustered_t(net_vals, [e["date"] for e in ev_results])  # sensitivity:
                                                                                             # pools cities
                                                                                             # sharing a date
        n_win = sum(1 for e in ev_results if e["won"])
        wilson_win = {"n": n_priced, "k": n_win, "rate": n_win / n_priced, "ci95": wilson_ci(n_win, n_priced)}

        mean_ev = day_clustered["mean"]
        t_stat = day_clustered["t"]
        # PRE-REGISTERED KILL bound: one-sided 98.33% UCB (z=2.128) of mean net EV < +0.2c/ct
        if day_clustered["se"] is not None:
            ucb_98_33 = mean_ev + 2.128 * day_clustered["se"]
            kill_bound_c = ucb_98_33
        pass_t_ok = (t_stat is not None) and (t_stat >= 2.25)
        pass_mean_ok = mean_ev >= 0.5

        if spec_kill:
            verdict = f"SPEC-KILL (infrastructure): {spec_kill}"
        elif thin:
            verdict = "THIN/no-verdict (below min_n: need >=120 priced fires AND >=40 clusters)"
        elif kill_bound_c is not None and kill_bound_c < 0.2:
            verdict = f"KILL -- sleeve DEAD at measured prices (98.33% UCB {kill_bound_c:+.3f}c/ct < +0.2c/ct)"
        elif pass_t_ok and pass_mean_ok:
            verdict = f"PASS (t={t_stat:.3f} >= 2.25, mean={mean_ev:+.3f}c/ct >= +0.5c/ct)"
        else:
            verdict = f"INCONCLUSIVE-THIN (t={t_stat if t_stat is not None else '--'}, mean={mean_ev:+.3f}c/ct)"
    else:
        verdict = "SPEC-KILL or THIN (no priced fires at all)" if not spec_kill else f"SPEC-KILL: {spec_kill}"

    print(f"\nVERDICT: {verdict}")
    if day_clustered:
        print(f"  city-day-clustered: mean={day_clustered['mean']:+.4f}c/ct  t={day_clustered['t']}  "
              f"n={day_clustered['n']}  n_clusters={day_clustered['n_clusters']}")
    if calendar_date_clustered:
        print(f"  calendar-date-clustered (sensitivity): mean={calendar_date_clustered['mean']:+.4f}c/ct  "
              f"t={calendar_date_clustered['t']}  n_clusters={calendar_date_clustered['n_clusters']}")
    if kill_bound_c is not None:
        print(f"  98.33% UCB (kill check): {kill_bound_c:+.4f}c/ct  (kill if < +0.2c/ct)")

    elapsed = time.time() - t_start
    out = {
        "run_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "elapsed_s": round(elapsed, 1),
        "spec_id": "S1",
        "window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
        "cities": list(CITIES.keys()),
        "usable_city_days": usable_city_days,
        "n_skipped_city_days": len(skips),
        "skips": skips,
        "n_lock_records_pure_rule_nongating": len(lock_records),
        "n_entries_total": len(entry_records),
        "pricing_status_counts": status_counts,
        "n_in_pmxt_coverage": n_in_window,
        "n_unpriceable": len(unpriceable),
        "frac_unpriceable": frac_unpriceable,
        "n_priced": n_priced,
        "n_clusters_city_day": n_clusters,
        "ev_results": ev_results,
        "unpriceable_examples": [{"city": e["city"], "date": e["date"], "ticker": e["ticker"],
                                   "entry_utc": e["entry_utc"]} for e in unpriceable[:30]],
        "day_clustered_stat": day_clustered,
        "calendar_date_clustered_stat_sensitivity": calendar_date_clustered,
        "wilson_win_rate": wilson_win,
        "kill_bound_98_33_ucb_c": kill_bound_c,
        "pass_bar_t_ge_2_25": pass_t_ok,
        "pass_bar_mean_ge_0_5c": pass_mean_ok,
        "hour_files_attempted": HOUR_FETCH_STATS["attempted"],
        "hour_files_unreadable": HOUR_FETCH_STATS["unreadable"],
        "frac_hour_files_unreadable": frac_hour_unreadable,
        "spec_kill_triggered": spec_kill,
        "thin_below_min_n": thin,
        "verdict": verdict,
        "per_day_log": per_day_log,
        "lock_records_pure_rule": lock_records,
    }
    out_path = os.path.join(OUT_DIR, "spec_S1_results.json")
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"\nwrote {out_path}  ({elapsed:.1f}s total)")
    return out


if __name__ == "__main__":
    run(cached_only="--cached-only" in sys.argv[1:])
