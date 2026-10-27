#!/usr/bin/env python3
"""finality_no_A.py -- BUILD A (primary) of FINALITY_NO_LADDER_SPEC.md (registered 2026-10-27).

Executes the frozen spec; it is NOT hunting for an edge.  Stages (each resumable; all pulls cached under
venue_expansion/cache/finality_no/):

    setup     copy the already-pulled market lists + IEM obs from the sibling FINAL-YES build cache (disclosed reuse)
    order     SHUFFLED event work order (fixed seed), written ONCE, NEVER re-sorted
    candles   1-min candlesticks (final 120 min) for EVERY rung of each event, in that shuffled order
    signals   obs-only FINAL-NO detector (streaming, no look-ahead) over the FULL universe (no pricing needed)
    report    entry rule, latency arms, statistics, Part 2 ladder, anchors -> out/finality_no_A.{json,md}

==== THE SIDE / PRICE RULE (it has already invalidated work in this repo) ======================================
 A FINAL-NO fire buys NO.  Its executable cost is   100 - yes_bid   .  It is NEVER   100 - yes_ask   (that is the NO
 *bid*, the price a seller of NO receives; a buyer cannot fill there).  A determined-winner YES fire (Part 2) buys
 YES at yes_ask.  Every price below is built from those two expressions and nothing else.

==== INTERPRETATION DECISIONS, PRE-DECLARED IN THIS FILE BEFORE ANY OUTCOME WAS ANALYSED ===========================
 D1  Bracket [lo, hi] = [floor_strike, cap_strike] (hi = lo + 1; official value is an INTEGER and YES iff lo <= v <=
     hi).  Never-arrival gap:  HIGH  E <= lo - G ;  LOW  E >= hi + G   (spec text, literally).  Overshoot (exploratory
     reference arm only, anchor d):  HIGH  E >= hi + G ;  LOW  E <= lo - G, with the same R/H/W gating.  Part 1 is
     BRACKET rungs only (spec: "A bracket [lo, hi] settles NO two ways").  T rungs enter only in Part 2.
 D2  Signal timestamp = observation minute + 60 s (so every observation used has ts < signal ts; spec anchor b).  Entry
     candle = first candle with end_period_ts >= signal_ts + L*60 and <= close_ts whose executable cost is <= 98c with
     fee-inclusive net > 0.  No earlier/better print is ever used.  No such candle (including: no candle at all) =
     UNTRADEABLE, counted in the untradeable fraction, never back-filled.
 D3  Fee = V2.fee_c(cost) = ceil(7 p (1-p)) cents at the crossing price (cost/100).  pnl: NO buy: 100-cost-fee if
     official result is 'no', else -cost-fee.  YES buy: 100-cost-fee if 'yes' else -cost-fee.  Outcome = Kalshi
     `result` only.
 D4  "Volume-weighted EV" weight = volume of the ENTRY candle (same convention as the sibling FINAL-YES build);
     the unweighted mean and the count of weight>0 entries are reported alongside.  The formal bar uses the
     volume-weighted estimator and its own day-clustered (CR1) standard error.
 D5  Cluster for Part 1 "day-clustered t" = the calendar EVENT DATE (all cities on one date share a cluster; weather is
     cross-city correlated, so this is the conservative reading and matches "distinct days").  City-day clustering is
     reported alongside.  Part 2 cluster = the city-day (the spec says so explicitly).  df = clusters - 1; bar = exact
     Student-t quantile at p = 0.99936 on the realised df.
 D6  Bar 1 (false-lock <= 2%, Wilson upper <= 5%) must hold on BOTH all fires (full universe, no pricing needed) and
     on PRICED fires.  The KILL trigger "false-lock > 5% in the primary cell" is evaluated on the all-fires rate
     (the finality inference being wrong is a property of the signal, not of what was tradeable); the priced rate is
     reported next to it.
 D7  KILL bound: one-sided 97.9% upper bound = mean + t_{0.979, days-1} * se (also 0.99792 shown), best over the 12
     L=10 cells.
 D8  Part 2 signal = the PRIMARY cell (G=4,R=2,H=3,W=120) FINAL-NO on ANY bracket rung of the city-day; t* = earliest
     such obs.  The companion FINAL-YES primary cell cannot fire on integer data under the literal reading (the
     sibling build documents an empty interval), so the "either" union equals the FINAL-NO day set; disclosed.  E* = running
     extreme at t*, v* = floor(E*+0.5) is the inferred final integer.  Every rung whose YES set contains v* is the
     inferred winner (buy YES at yes_ask); every other rung is an inferred loser (buy NO at 100-yes_bid); each gated
     independently (<=98c and net>0) at the first qualifying candle at/after t*+L.  A day needs a complete ladder
     (exactly one inferred winner and >= 5 rungs with official results) or it is skipped (counted).
 D9  Settlement semantics (verified against expiration_value in the report): between: floor<=v<=cap; greater: v>floor;
     less: v<cap.
 D10 Universe/feeds/glitch guard identical to the sibling build: 40 US HIGH/LOW series with a verified station and a fixed
     local-STANDARD-time offset; obs outside [-60,130]F dropped; 1-minute feed if >= 600 valid obs on the local day,
     else routine (>= 8), else skip; feed recorded per event.  The local day is [close-24h(-60s), close) in LST.
 D11 Sampling.  Pricing is expensive (1 call/s, 6 rungs/event, ~40k rungs), so the priced stage is a SHUFFLED
     EVENT sample (an event is only counted once ALL its rungs are cached; Part 2 needs the whole ladder).  Signal-level
     facts (fire counts, false-lock rates) use the FULL universe.  Sampling fraction is reported at the top of the .md.
=====================================================================================================================
"""
from __future__ import annotations

import argparse
import bisect
import collections
import datetime as dt
import json
import math
import multiprocessing as mp
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import edge_sizing_v2 as V2          # noqa: E402  normalize()/fee_c() reused, NOT reimplemented

CACHE = os.path.join(HERE, "cache", "finality_no")
SIB = os.path.join(HERE, "cache", "finality", "A")        # sibling FINAL-YES build cache (read-only reuse)
MKT_DIR = os.path.join(CACHE, "markets")
OBS_DIR = os.path.join(CACHE, "obs")
CANDLE_DIR = os.path.join(CACHE, "candles")
SIGNALS = os.path.join(CACHE, "signals.jsonl")
SIG_SUMMARY = os.path.join(CACHE, "signals_summary.json")
ORDER_PATH = os.path.join(CACHE, "event_work_order.json")
BATCHCHECK = os.path.join(CACHE, "batch_vs_single_check.json")
OUT_JSON = os.path.join(HERE, "out", "finality_no_A.json")
OUT_MD = os.path.join(HERE, "out", "finality_no_A.md")
for _d in (MKT_DIR, OBS_DIR, CANDLE_DIR, os.path.dirname(OUT_JSON)):
    os.makedirs(_d, exist_ok=True)

KAPI = "https://api.elections.kalshi.com/trade-api/v2"
IEM_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
IEM_ROUTINE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

SEED = 20261028
WIN_LO = dt.date(2026, 5, 23)
WIN_HI = dt.date(2026, 10, 20)
OBS_MONTHS = [(2026, m) for m in range(5, 11)]
GLITCH_HI_F, GLITCH_LO_F = 130.0, -60.0
MIN_1MIN_OBS, MIN_ROUTINE_OBS = 600, 8
MAX_PAY_C = V2.MAX_PAY_C            # 98
CANDLE_WINDOW_MIN = 120

GRID = [(G, R, 3, W) for G in (2, 4, 6) for R in (2, 4) for W in (60, 120)]      # 12 cells (frozen)
LATS = (0, 10, 20)
PRIMARY = (4, 2, 3, 120)
FLAVORS = ("na", "os")        # never-arrival (the spec's Part 1) ; overshoot (exploratory reference, anchor d)


def cell_key(c):
    return f"G{c[0]}_R{c[1]}_H{c[2]}_W{c[3]}"


CELLKEYS = [cell_key(c) for c in GRID]
PRIMARY_KEY = cell_key(PRIMARY)

# ---- HIGH series -> (station, fixed standard UTC offset hours).  Same table as the sibling build / edge_sizing_stage2.
CITY = {
    "KXHIGHDEN": ("KDEN", -7), "KXHIGHMIA": ("KMIA", -5), "KXHIGHCHI": ("KMDW", -6),
    "KXHIGHTBOS": ("KBOS", -5), "KXHIGHAUS": ("KAUS", -6), "KXHIGHTSEA": ("KSEA", -8),
    "KXHIGHTSFO": ("KSFO", -8), "KXHIGHTMIN": ("KMSP", -6), "KXHIGHTDC": ("KDCA", -5),
    "KXHIGHTATL": ("KATL", -5), "KXHIGHTDAL": ("KDFW", -6), "KXHIGHTSATX": ("KSAT", -6),
    "KXHIGHNY": ("NYC", -5), "KXHIGHTOKC": ("KOKC", -6), "KXHIGHTLV": ("KLAS", -8),
    "KXHIGHTPHX": ("KPHX", -7), "KXHIGHTHOU": ("KHOU", -6), "KXHIGHPHIL": ("KPHL", -5),
    "KXHIGHTNOLA": ("KMSY", -6), "KXHIGHLAX": ("KLAX", -8),
}
CITY_LOW_SERIES = {
    "KXHIGHDEN": "KXLOWTDEN", "KXHIGHMIA": "KXLOWTMIA", "KXHIGHCHI": "KXLOWTCHI",
    "KXHIGHTBOS": "KXLOWTBOS", "KXHIGHAUS": "KXLOWTAUS", "KXHIGHTSEA": "KXLOWTSEA",
    "KXHIGHTSFO": "KXLOWTSFO", "KXHIGHTMIN": "KXLOWTMIN", "KXHIGHTDC": "KXLOWTDC",
    "KXHIGHTATL": "KXLOWTATL", "KXHIGHTDAL": "KXLOWTDAL", "KXHIGHTSATX": "KXLOWTSATX",
    "KXHIGHNY": "KXLOWTNYC", "KXHIGHTOKC": "KXLOWTOKC", "KXHIGHTLV": "KXLOWTLV",
    "KXHIGHTPHX": "KXLOWTPHX", "KXHIGHTHOU": "KXLOWTHOU", "KXHIGHPHIL": "KXLOWTPHIL",
    "KXHIGHTNOLA": "KXLOWTNOLA", "KXHIGHLAX": "KXLOWTLAX",
}


def iem_code(icao):
    return icao[1:] if (icao.startswith("K") and len(icao) == 4) else icao


SERIES_MAP = {}
for _h, (_st, _off) in CITY.items():
    SERIES_MAP[_h] = {"station": iem_code(_st), "kind": "max", "off": _off}
    SERIES_MAP[CITY_LOW_SERIES[_h]] = {"station": iem_code(_st), "kind": "min", "off": _off}

MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


# ------------------------------------------------------------------ http (sequential, polite, adaptive backoff)
_last = {}
_gap_extra = {"kalshi": 0.0}


def _throttle(host, gap):
    now = time.time()
    w = _last.get(host, 0) + gap + _gap_extra.get(host, 0.0) - now
    if w > 0:
        time.sleep(w)
    _last[host] = time.time()


def http_get(url, host, gap, as_json=True, tries=10):
    err = None
    for i in range(tries):
        _throttle(host, gap)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "finality-no-A/1.0 (research)"})
            with urllib.request.urlopen(req, timeout=60) as fh:
                body = fh.read().decode("utf-8", "replace")
            if host in _gap_extra:
                _gap_extra[host] = max(0.0, _gap_extra[host] - 0.02)      # slow decay after success
            return json.loads(body) if as_json else body
        except urllib.error.HTTPError as e:
            err = e
            if e.code == 404:
                raise
            if e.code == 429 and host in _gap_extra:
                _gap_extra[host] = min(3.0, _gap_extra[host] + 0.4)
            time.sleep(min(90, 3 * 2 ** i if e.code == 429 else 2 ** (i + 1)))
        except Exception as e:      # noqa: BLE001
            err = e
            time.sleep(min(60, 2 ** (i + 1)))
    raise RuntimeError(f"GET failed after {tries} tries: {url}: {err}")


def kget(path):
    return http_get(KAPI + path, "kalshi", 1.05)


# ------------------------------------------------------------------ setup / universe
def parse_event_date(event_ticker):
    m = re.search(r"-(\d\d)([A-Z]{3})(\d\d)$", event_ticker)
    if not m:
        return None
    try:
        return dt.date(2000 + int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)))
    except Exception:     # noqa: BLE001
        return None


def stage_setup():
    """Reuse the market lists and IEM obs already pulled by the sibling build (same universe, same sources).
    Copy, do not symlink, so this cache is self-contained."""
    n = 0
    for sub, dst in (("markets", MKT_DIR), ("obs", OBS_DIR)):
        for f in sorted(os.listdir(os.path.join(SIB, sub))):
            if f == "all_series.json":
                continue
            p = os.path.join(dst, f)
            if not os.path.exists(p):
                shutil.copyfile(os.path.join(SIB, sub, f), p)
                n += 1
    print("copied", n, "files from sibling cache")


def list_settled(series):
    seen, out = set(), []
    for tag in ("live", "hist"):
        p = os.path.join(MKT_DIR, f"{series}.{tag}.json")
        if not os.path.exists(p):
            raise SystemExit(f"missing market cache {p}; run setup")
        for m in json.load(open(p)):
            if m["ticker"] in seen:
                continue
            seen.add(m["ticker"])
            m["series_ticker"] = series
            m["_src"] = tag
            out.append(m)
    return out


def utc_ts(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def universe():
    """events[event_ticker] = list of rung dicts (B and T), in-window, with official result."""
    events = collections.defaultdict(list)
    skips = collections.Counter()
    for s in sorted(SERIES_MAP):
        for m in list_settled(s):
            cd = dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).date()
            if not (WIN_LO <= cd <= WIN_HI):
                skips["outside_window"] += 1
                continue
            if m.get("result") not in ("yes", "no"):
                skips["no_official_result"] += 1
                continue
            if m["strike_type"] not in ("between", "greater", "less"):
                skips["other_strike_type:" + str(m["strike_type"])] += 1
                continue
            events[m["event_ticker"]].append(m)
    return events, skips


def stage_order():
    if os.path.exists(ORDER_PATH):
        print("work order already exists (never regenerated):", ORDER_PATH)
        return
    events, skips = universe()
    keys = sorted(events)          # sorted ONLY so the seeded shuffle is reproducible
    random.Random(SEED).shuffle(keys)   # ... then shuffled and NEVER re-sorted
    json.dump({"seed": SEED, "n_events": len(keys), "events": keys}, open(ORDER_PATH, "w"))
    print(f"work order: {len(keys)} events, seed {SEED}; skips {dict(skips)}")


# ------------------------------------------------------------------ candles
def candle_path(tk):
    return os.path.join(CANDLE_DIR, tk + ".json")


def _hist_to_live(cs):
    """/historical candlesticks use {close,...} strings; convert to the live *_dollars shape so V2.normalize()
    (the single shared price path) is used unchanged."""
    out = []
    for k in cs:
        def node(n):
            n = n or {}
            return {"close_dollars": n.get("close")}
        out.append({"end_period_ts": k.get("end_period_ts"), "volume_fp": k.get("volume"),
                    "yes_bid": node(k.get("yes_bid")), "yes_ask": node(k.get("yes_ask"))})
    return out


def _slim_live(cs):
    return [{"end_period_ts": k.get("end_period_ts"), "volume_fp": k.get("volume_fp"),
             "yes_bid": {"close_dollars": (k.get("yes_bid") or {}).get("close_dollars")},
             "yes_ask": {"close_dollars": (k.get("yes_ask") or {}).get("close_dollars")}} for k in cs]


def _qs(close_ts):
    return f"start_ts={close_ts - CANDLE_WINDOW_MIN * 60 - 60}&end_ts={close_ts}&period_interval=1"


def single_fetch(tk, series, close_ts, order):
    """Per-market fetch, trying sources in `order` until one returns candles.  Returns cache dict (None = transient)."""
    res = {"ok": False, "error": "unreached", "candlesticks": []}
    q = _qs(close_ts)
    for src in order:
        path = (f"/series/{series}/markets/{tk}/candlesticks?{q}" if src == "live"
                else f"/historical/markets/{tk}/candlesticks?{q}")
        try:
            d = kget(path)
            cs = d.get("candlesticks", [])
            cs = _hist_to_live(cs) if src == "hist" else _slim_live(cs)
            res = {"ok": True, "src": src, "candlesticks": cs}
            if cs:
                break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                res = {"ok": False, "error": f"HTTP 404 via {src}", "candlesticks": []}
            else:
                return None
        except RuntimeError:
            return None
    return res


def reuse_sibling(tk):
    sp = os.path.join(SIB, "candles", tk + ".json")
    if not os.path.exists(sp):
        return False
    try:
        c = json.load(open(sp))
        if "candlesticks" not in c:
            return False
        c["reused_from"] = "sibling FINAL-YES build cache (same window: close-121min..close)"
        json.dump(c, open(candle_path(tk), "w"))
        return True
    except Exception:     # noqa: BLE001
        return False


def fetch_event(rungs):
    """Fetch every rung of one event.  Live-settled rungs go through ONE batch call per event
    (GET /markets/candlesticks?market_tickers=...; verified identical to the per-market endpoint, see
    batch_vs_single_check.json); hist-settled rungs per market.  Returns True if all rungs are cached after."""
    need = []
    for r in rungs:
        if os.path.exists(candle_path(r["ticker"])):
            continue
        if reuse_sibling(r["ticker"]):
            continue
        need.append(r)
    live = [r for r in need if r.get("_src") == "live"]
    hist = [r for r in need if r.get("_src") != "live"]
    close_ts = utc_ts(rungs[0]["close_time"])
    series = rungs[0]["series_ticker"]
    if live:
        try:
            d = kget(f"/markets/candlesticks?market_tickers={','.join(r['ticker'] for r in live)}&{_qs(close_ts)}")
            got = {m["market_ticker"]: m.get("candlesticks", []) for m in d.get("markets", [])}
        except Exception:     # noqa: BLE001
            got = None
        if got is not None:
            for r in live:
                cs = got.get(r["ticker"])
                if cs is None:
                    cs = []
                if cs:
                    json.dump({"ok": True, "src": "live_batch", "candlesticks": _slim_live(cs)},
                              open(candle_path(r["ticker"]), "w"))
                else:
                    hist.append(r)           # empty on live -> try the other source once (same rule as sibling)
        else:
            hist.extend(live)
    for r in hist:
        order = ("hist", "live") if r.get("_src") != "live" else ("live", "hist")
        res = single_fetch(r["ticker"], series, close_ts, order)
        if res is None:
            return False
        json.dump(res, open(candle_path(r["ticker"]), "w"))
    return all(os.path.exists(candle_path(r["ticker"])) for r in rungs)


def stage_candles(budget_s, max_events):
    events, _ = universe()
    order = json.load(open(ORDER_PATH))["events"]
    t0 = time.time()
    done = n_new = 0
    # anchor (a): the stored oracle detail rungs, fetched up front (per-market), independent of the sample
    for r in oracle_detail():
        tk = r["ticker"]
        if not os.path.exists(candle_path(tk)):
            ct = utc_ts(r["close_time"])
            res = single_fetch(tk, r["series"], ct, ("hist", "live") if ct < 1788000000 else ("live", "hist"))
            if res is not None:
                json.dump(res, open(candle_path(tk), "w"))
    # one-off live-batch vs per-market equality check on the first few live events
    check_batch(events, order)
    for evt in order:                                # shuffled order, never re-sorted
        rungs = events[evt]
        if all(os.path.exists(candle_path(r["ticker"])) for r in rungs):
            done += 1
            continue
        if time.time() - t0 > budget_s or n_new >= max_events:
            break
        ok = fetch_event(rungs)
        if ok:
            done += 1
            n_new += 1
        if n_new and n_new % 25 == 0 and ok:
            print(f"  candles: +{n_new} events this run, {done}/{len(order)} events complete, "
                  f"{time.time() - t0:.0f}s", flush=True)
    print(f"candles: {done}/{len(order)} events complete (+{n_new} this run)", flush=True)


def oracle_detail():
    d = json.load(open(os.path.join(HERE, "out", "edge_sizing_v2.json")))
    return d["capturable_markets_detail"]


def check_batch(events, order):
    if os.path.exists(BATCHCHECK):
        return
    res = []
    for evt in order:
        rs = events[evt]
        if rs[0].get("_src") != "live":
            continue
        close_ts = utc_ts(rs[0]["close_time"])
        series = rs[0]["series_ticker"]
        d = kget(f"/markets/candlesticks?market_tickers={','.join(r['ticker'] for r in rs)}&{_qs(close_ts)}")
        got = {m["market_ticker"]: m.get("candlesticks", []) for m in d.get("markets", [])}
        for r in rs[:2]:
            single = kget(f"/series/{series}/markets/{r['ticker']}/candlesticks?{_qs(close_ts)}").get("candlesticks", [])
            res.append({"ticker": r["ticker"], "n_batch": len(got.get(r["ticker"], [])), "n_single": len(single),
                        "identical": got.get(r["ticker"], []) == single})
        if len(res) >= 8:
            break
    json.dump(res, open(BATCHCHECK, "w"), indent=1)
    print("batch vs single check:", sum(x["identical"] for x in res), "/", len(res), "identical")


# ------------------------------------------------------------------ obs
_ord_cache = {}


def to_epoch(valid):
    d = valid[:10]
    o = _ord_cache.get(d)
    if o is None:
        o = (dt.date(int(d[0:4]), int(d[5:7]), int(d[8:10])) - dt.date(1970, 1, 1)).days
        _ord_cache[d] = o
    return o * 86400 + int(valid[11:13]) * 3600 + int(valid[14:16]) * 60


def month_bounds(y, m):
    a = dt.datetime(y, m, 1, tzinfo=dt.timezone.utc)
    b = dt.datetime(y + (m == 12), 1 if m == 12 else m + 1, 1, tzinfo=dt.timezone.utc)
    return a, b


def fetch_obs_month(station, y, m, feed):
    path = os.path.join(OBS_DIR, f"{feed}_{station}_{y}-{m:02d}.json")
    if os.path.exists(path):
        return json.load(open(path))
    a, b = month_bounds(y, m)
    if feed == "1min":
        url = (f"{IEM_1MIN}?station={station}&vars=tmpf&sts={a:%Y-%m-%dT%H:%MZ}&ets={b:%Y-%m-%dT%H:%MZ}"
               "&tz=UTC&format=onlycomma")
        idx = 3
    else:
        b2 = b + dt.timedelta(days=1)
        url = (f"{IEM_ROUTINE}?station={station}&data=tmpf&year1={a.year}&month1={a.month}&day1={a.day}"
               f"&year2={b2.year}&month2={b2.month}&day2={b2.day}&tz=UTC&format=onlycomma&latlon=no"
               "&report_type=3&report_type=4")
        idx = 2
    txt = http_get(url, "iem", 0.4, as_json=False)
    rows = []
    for ln in txt.splitlines():
        p = ln.split(",")
        if len(p) <= idx or p[0] == "station":
            continue
        v = p[idx]
        if v in ("M", ""):
            continue
        try:
            f = float(v)
        except ValueError:
            continue
        valid = p[idx - 1]
        if len(valid) < 16:
            continue
        rows.append((to_epoch(valid), f))
    rows.sort()
    dd = []
    for t, f in rows:
        if dd and dd[-1][0] == t:
            dd[-1] = [t, f]
        else:
            dd.append([t, f])
    json.dump(dd, open(path, "w"))
    return dd


def load_station_obs(station, feed):
    allr = []
    for (y, m) in OBS_MONTHS:
        allr.extend(fetch_obs_month(station, y, m, feed))
    allr.sort()
    ts, tf, last = [], [], None
    for t, f in allr:
        if last == t:
            tf[-1] = f
            continue
        ts.append(t)
        tf.append(f)
        last = t
    return ts, tf


# ------------------------------------------------------------------ streaming detector (NO look-ahead by construction)
class Stream:
    """Consumes observations ONE AT A TIME in time order.  State = (E, run length per R).  There is no access to any
    later observation, so the state after obs k is a function of obs[0..k] only.
    run[R] = number of trailing consecutive obs that are at least R degrees away from the CURRENT extreme E
    (reset to 0 whenever a new extreme is set or an obs is closer than R to E)."""

    def __init__(self, kind, Rs=(2, 4)):
        self.kind = kind
        self.E = None
        self.Rs = Rs
        self.run = {R: 0 for R in Rs}

    def push(self, f):
        if self.E is None or (f > self.E if self.kind == "max" else f < self.E):
            self.E = f
            for R in self.Rs:
                self.run[R] = 0
            return
        for R in self.Rs:
            away = (f <= self.E - R + 1e-9) if self.kind == "max" else (f >= self.E + R - 1e-9)
            self.run[R] = self.run[R] + 1 if away else 0


def flavor_cond(kind, flavor, E, lo, hi, G):
    """never-arrival ('na'):  HIGH E <= lo-G ; LOW E >= hi+G .   overshoot ('os'): HIGH E >= hi+G ; LOW E <= lo-G."""
    e = 1e-9
    if flavor == "na":
        return (E <= lo - G + e) if kind == "max" else (E >= hi + G - e)
    return (E >= hi + G - e) if kind == "max" else (E <= lo - G + e)


def detect_event(obs_ts, obs_f, kind, close_ts, brackets):
    """obs_* ascending, restricted to the local day [day0, close).  brackets = [(ticker, lo, hi)].
    Returns (fires, day) ; fires[(ticker, flavor, cellkey)] = dict(k, obs_ts, sig_ts, E, temp, run, span_min);
    day = Part 2 day-level signal (primary cell, any bracket, never-arrival) = dict(k, obs_ts, sig_ts, E) or None.
    Each obs k contributes only through the Stream state after obs k (obs[0..k]) -> no look-ahead."""
    st = Stream(kind)
    fires = {}
    day = None
    wmax = max(c[3] for c in GRID)
    for k in range(len(obs_ts)):
        t, f = obs_ts[k], obs_f[k]
        st.push(f)
        if t < close_ts - wmax * 60:
            continue
        E = st.E
        for c in GRID:
            G, R, H, W = c
            if t < close_ts - W * 60 or st.run[R] < H:
                continue
            ck = cell_key(c)
            for (tk, lo, hi) in brackets:
                for fl in FLAVORS:
                    key = (tk, fl, ck)
                    if key in fires:
                        continue
                    if flavor_cond(kind, fl, E, lo, hi, G):
                        fires[key] = {"k": k, "obs_ts": t, "sig_ts": t + 60, "E": E, "temp": f,
                                      "run": st.run[R], "span_min": (t - obs_ts[k - H + 1]) / 60.0}
                        if fl == "na" and ck == PRIMARY_KEY and day is None:
                            day = {"k": k, "obs_ts": t, "sig_ts": t + 60, "E": E, "temp": f}
    return fires, day


def signature(fires, day, kmax):
    s = {key: (v["k"], v["E"], v["sig_ts"]) for key, v in fires.items() if v["k"] <= kmax}
    d = None if (day is None or day["k"] > kmax) else (day["k"], day["E"], day["sig_ts"])
    return s, d


def lookahead_assert(obs_ts, obs_f, kind, close_ts, brackets, fires, day):
    """Anchor (b).  For every distinct signal index k0: re-run the detector on obs[:k0+1] only, and on the full day
    with every obs after k0 replaced by an adversarial value (+50F and -50F from the k0 temperature).  Decisions at
    indices <= k0 must be identical.  Raises on any violation.  Returns the number of re-runs."""
    ks = sorted({v["k"] for v in fires.values()} | ({day["k"]} if day else set()))
    n = 0
    for k0 in ks:
        ref = signature(fires, day, k0)
        variants = [(obs_ts[:k0 + 1], obs_f[:k0 + 1])]
        for delta in (50.0, -50.0):
            variants.append((obs_ts, obs_f[:k0 + 1] + [obs_f[k0] + delta] * (len(obs_f) - k0 - 1)))
        for tt, ff in variants:
            f2, d2 = detect_event(tt, ff, kind, close_ts, brackets)
            n += 1
            assert signature(f2, d2, k0) == ref, f"LOOK-AHEAD VIOLATION at k0={k0}"
    return n


# ------------------------------------------------------------------ signals stage (full universe, parallel by station)
def _process_station(args):
    station, evlist = args
    obs = {feed: load_station_obs(station, feed) for feed in ("1min", "routine")}
    SH = list(range(-3, 4))
    out = []
    for (evt, rungs) in evlist:
        series = rungs[0]["series_ticker"]
        sm = SERIES_MAP[series]
        d = parse_event_date(evt)
        close_ts = utc_ts(rungs[0]["close_time"])
        base = {"event": evt, "series": series, "station": sm["station"], "kind": sm["kind"], "date": str(d),
                "close_ts": close_ts}
        if d is None:
            out.append({**base, "skip": "unparseable_event_date", "n_rungs": len(rungs)})
            continue
        exp_close = int((dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
                         - dt.timedelta(hours=sm["off"])).timestamp())
        # tolerance: a block of HIGH series closes at 23:59 LST (60 s before LST midnight).  Anything else = hard skip.
        if any(not (-60 <= utc_ts(r["close_time"]) - exp_close <= 0) for r in rungs):
            out.append({**base, "skip": "close_time_not_LST_midnight", "n_rungs": len(rungs)})
            continue
        day0 = exp_close - 86400
        base["close_offset_s"] = close_ts - exp_close
        feeds = {}
        for feed in ("1min", "routine"):
            ts, tf = obs[feed]
            i0, i1 = bisect.bisect_left(ts, day0), bisect.bisect_left(ts, close_ts)
            ots, of_ = [], []
            for t, f in zip(ts[i0:i1], tf[i0:i1]):
                if GLITCH_LO_F <= f <= GLITCH_HI_F:
                    ots.append(t)
                    of_.append(f)
            feeds[feed] = (ots, of_)
        if len(feeds["1min"][0]) >= MIN_1MIN_OBS:
            feed, (ots, of_) = "iem_1min", feeds["1min"]
        elif len(feeds["routine"][0]) >= MIN_ROUTINE_OBS:
            feed, (ots, of_) = "iem_routine_fallback", feeds["routine"]
        else:
            out.append({**base, "skip": "insufficient_obs_both_feeds", "n_rungs": len(rungs),
                        "n_1min": len(feeds["1min"][0]), "n_routine": len(feeds["routine"][0])})
            continue
        # ---- anchor (c): obs inside the local day; running extreme monotone
        assert all(day0 <= t < close_ts for t in ots), "obs outside local-day window"
        assert all(ots[i] < ots[i + 1] for i in range(len(ots) - 1)), "obs not strictly increasing"
        sm_ = Stream(sm["kind"])
        prevE, mono = None, 0
        for f in of_:
            sm_.push(f)
            if prevE is not None and ((sm_.E < prevE) if sm["kind"] == "max" else (sm_.E > prevE)):
                mono += 1
            prevE = sm_.E
        # ---- timezone diagnostic vs official expiration_value (1-min only): shifted windows
        diag = None
        offv = rungs[0].get("expiration_value")
        if feed == "iem_1min" and offv not in (None, ""):
            ts1, tf1 = obs["1min"]
            diag = {}
            for s in SH:
                a, b = bisect.bisect_left(ts1, day0 + s * 3600), bisect.bisect_left(ts1, exp_close + s * 3600)
                vals = [f for f in tf1[a:b] if GLITCH_LO_F <= f <= GLITCH_HI_F]
                if len(vals) >= MIN_1MIN_OBS:
                    diag[str(s)] = max(vals) if sm["kind"] == "max" else min(vals)
        brackets = [(r["ticker"], r["floor_strike"], r["cap_strike"]) for r in rungs
                    if r["strike_type"] == "between" and r.get("floor_strike") is not None
                    and r.get("cap_strike") is not None]
        fires, dayfire = detect_event(ots, of_, sm["kind"], close_ts, brackets)
        n_la = lookahead_assert(ots, of_, sm["kind"], close_ts, brackets, fires, dayfire)
        rec = {**base, "feed": feed, "n_obs": len(ots), "E_final": sm_.E, "official_value": offv,
               "tz_shift_extremes": diag, "mono_viol": mono, "n_lookahead": n_la, "day_signal": dayfire,
               "first_obs_ts": ots[0], "last_obs_ts": ots[-1],
               "rungs": [{"ticker": r["ticker"], "type": r["strike_type"], "floor": r.get("floor_strike"),
                          "cap": r.get("cap_strike"), "result": r["result"], "src": r.get("_src"),
                          "fires": {fl: {ck: fires[(r["ticker"], fl, ck)] for ck in CELLKEYS
                                         if (r["ticker"], fl, ck) in fires} for fl in FLAVORS}}
                         for r in rungs]}
        out.append(rec)
    return out


def stage_signals(procs):
    events, skips = universe()
    by_station = collections.defaultdict(list)
    for evt in sorted(events):
        rs = events[evt]
        by_station[SERIES_MAP[rs[0]["series_ticker"]]["station"]].append((evt, rs))
    work = sorted(by_station.items(), key=lambda kv: -len(kv[1]))
    n = 0
    with open(SIGNALS + ".tmp", "w") as fh, mp.Pool(procs) as pool:
        for recs in pool.imap_unordered(_process_station, work):
            for r in recs:
                fh.write(json.dumps(r) + "\n")
                n += 1
            fh.flush()
            print(f"  signals: {n} events written", flush=True)
    # deterministic order on disk
    rows = [json.loads(l) for l in open(SIGNALS + ".tmp")]
    rows.sort(key=lambda r: r["event"])
    with open(SIGNALS, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    os.remove(SIGNALS + ".tmp")
    ok = [r for r in rows if "skip" not in r]
    summ = {"events_total": len(rows), "events_scored": len(ok),
            "event_skips": dict(collections.Counter(r["skip"] for r in rows if "skip" in r)),
            "universe_prefilter_skips": dict(skips),
            "monotonicity_violations": sum(r["mono_viol"] for r in ok),
            "lookahead_reruns": sum(r["n_lookahead"] for r in ok)}
    json.dump(summ, open(SIG_SUMMARY, "w"), indent=1)
    print(json.dumps(summ, indent=1))


# ====================================================================== REPORT (appended below)
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["setup", "order", "candles", "signals", "report"])
    ap.add_argument("--budget-s", type=float, default=3600.0)
    ap.add_argument("--max-events", type=int, default=10 ** 9)
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    if a.stage == "setup":
        stage_setup()
    elif a.stage == "order":
        stage_order()
    elif a.stage == "candles":
        stage_candles(a.budget_s, a.max_events)
    elif a.stage == "signals":
        stage_signals(a.procs)
    elif a.stage == "report":
        from finality_no_A_report import run_report      # noqa: F401  (defined in the report section)
        run_report()
