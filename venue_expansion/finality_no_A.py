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

CACHE = os.path.join(HERE, "cache", "finality_no", "A")   # own subdir: Build B shares cache/finality_no/
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
_stat = collections.Counter()


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
            _stat[host + "_ok"] += 1
            if _stat[host + "_ok"] % 50 == 0:
                print(f"    [http {host}] ok={_stat[host + '_ok']} 429={_stat[host + '_429']} gap_extra={_gap_extra.get(host)}", flush=True)
            if host in _gap_extra:
                _gap_extra[host] = max(0.0, _gap_extra[host] - 0.03)      # slow decay after success
            return json.loads(body) if as_json else body
        except urllib.error.HTTPError as e:
            err = e
            if e.code == 404:
                raise
            _stat[host + "_" + str(e.code)] += 1
            if e.code == 429 and host in _gap_extra:
                _gap_extra[host] = min(0.5, _gap_extra[host] + 0.1)
            time.sleep(min(30, 1.5 + 1.0 * i) if e.code == 429 else min(60, 2 ** (i + 1)))
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
                # (an empty live result is final: in the first 148 live-settled rungs the hist endpoint never held data
                #  for a live-settled market, so the fallback only burned rate-limit budget)
                json.dump({"ok": True, "src": "live_batch", "candlesticks": _slim_live(cs)},
                          open(candle_path(r["ticker"]), "w"))
        else:
            hist.extend(live)
    for r in hist:
        # hist-settled rungs: the historical endpoint only (in the first 230 such rungs, 45 were empty and the live
        # endpoint returned 404 for every one of them, so a second attempt never yields data)
        order = ("hist",) if r.get("_src") != "live" else ("live",)
        res = single_fetch(r["ticker"], series, close_ts, order)
        if res is None:
            return False
        json.dump(res, open(candle_path(r["ticker"]), "w"))
    return all(os.path.exists(candle_path(r["ticker"])) for r in rungs)


def stage_candles(budget_s, max_events):
    """Two tiers, both in the SHUFFLED event order (never re-sorted):
       tier 1 (Part 1, FULL universe): for every event, only the bracket rungs that have >=1 never-arrival fire in ANY
               cell (obs-only decision, independent of price and outcome).
       tier 2 (Part 2, full ladders): every rung of every event that has a day-level primary-cell signal.
       Tier 2 only starts once tier 1 is complete (or the budget ends first; the report states the fractions)."""
    events, _ = universe()
    order = json.load(open(ORDER_PATH))["events"]
    sig = {}
    for ln in open(SIGNALS):
        r = json.loads(ln)
        sig[r["event"]] = r
    t0 = time.time()
    n_new = 0
    for r in oracle_detail():       # anchor (a): the stored oracle detail rungs, fetched up front, per market
        tk = r["ticker"]
        if not os.path.exists(candle_path(tk)):
            ct = utc_ts(r["close_time"])
            res = single_fetch(tk, r["series"], ct, ("hist", "live") if ct < 1788000000 else ("live", "hist"))
            if res is not None:
                json.dump(res, open(candle_path(tk), "w"))
    check_batch(events, order)
    for tier in (1, 2):
        done = 0
        for evt in order:                                # shuffled order, never re-sorted
            sg = sig.get(evt)
            if sg is None or "skip" in sg:
                continue
            if tier == 1:
                want = {rg["ticker"] for rg in sg["rungs"] if rg["fires"]["na"]}
            else:
                want = {rg["ticker"] for rg in sg["rungs"]} if sg["day_signal"] else set()
            if not want:
                continue
            rungs = [r for r in events[evt] if r["ticker"] in want]
            if all(os.path.exists(candle_path(r["ticker"])) for r in rungs):
                done += 1
                continue
            if time.time() - t0 > budget_s or n_new >= max_events:
                print(f"tier {tier}: budget reached, {done} events complete so far", flush=True)
                return
            if fetch_event(rungs):
                done += 1
                n_new += 1
            if n_new and n_new % 25 == 0:
                print(f"  tier {tier}: +{n_new} events this run, {done} complete, {time.time() - t0:.0f}s", flush=True)
        print(f"tier {tier} COMPLETE: {done} events", flush=True)


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


# ====================================================================== REPORT
def wilson(k, n, z=1.959963985):
    if n == 0:
        return (None, None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (p, max(0.0, c - h), min(1.0, c + h))


def tq(p, df):
    from scipy import stats as _st
    return float(_st.t.ppf(p, df)) if df and df >= 1 else None


BAR_P = 1 - 0.05 / 39 / 2        # 0.99936 : two-sided alpha = 0.05/39 across both parts (frozen)


def cluster_stats(items):
    """items: [(cluster, weight, pnl)].  Weighted mean with cluster-robust SE (CR1 factor G/(G-1)); signed t."""
    sw = sum(w for _c, w, _p in items)
    clusters = {c for c, _, _ in items}
    if not items or sw <= 0:
        return {"n": len(items), "mean": None, "se": None, "t": None, "clusters": len(clusters)}
    mu = sum(w * p for _c, w, p in items) / sw
    U = collections.defaultdict(float)
    for c, w, p in items:
        U[c] += w * (p - mu)
    G = len(U)
    se = t = None
    if G >= 2:
        se = math.sqrt(G / (G - 1) * sum(u * u for u in U.values())) / sw
        t = mu / se if se > 0 else None
    return {"n": len(items), "mean": mu, "se": se, "t": t, "clusters": G}


def load_rows(tk, close_ts):
    """'not_fetched' | [] (no candle data exists: 404/empty) | rows [(ts, yes_bid_c, yes_ask_c, vol)] sorted."""
    p = candle_path(tk)
    if not os.path.exists(p):
        return "not_fetched"
    c = json.load(open(p))
    if not c.get("ok"):
        return []
    V2.WINDOW_MIN = CANDLE_WINDOW_MIN
    rows = V2.normalize(c["candlesticks"], close_ts)
    return sorted([r for r in rows if r[0] is not None], key=lambda r: r[0])


def entry(rows, close_ts, sig_ts, L, side):
    """First candle at/after sig_ts+L*60 (and <= close) whose executable cost is <=98c with fee-inclusive net > 0.
       side 'NO'  : cost = 100 - yes_bid     <-- a buyer of NO pays 100 - yes_bid.  NEVER 100 - yes_ask (that is the
                                                NO *bid*, unfillable by a buyer).
       side 'YES' : cost = yes_ask.
       No earlier or better print is ever used; no qualifying candle = untradeable."""
    if not rows:
        return {"status": "U", "reason": "no_candles"}
    target = sig_ts + L * 60
    after = [r for r in rows if target <= r[0] <= close_ts]
    if not after:
        return {"status": "U", "reason": "no_candle_at_or_after_target"}
    quoted = False
    for ts, yb, ya, vol in after:
        if side == "NO":
            cost = None if yb is None else 100 - yb
        else:
            cost = ya
        if cost is None:
            continue
        quoted = True
        if not (0 < cost <= MAX_PAY_C):
            continue
        fee = V2.fee_c(cost)
        if 100 - cost - fee <= 0:
            continue
        return {"status": "P", "ts": ts, "cost": cost, "fee": fee, "vol": vol}
    return {"status": "U", "reason": "cost_above_98_or_no_net" if quoted else "no_quote_on_side"}


def pnl_of(side, result, a):
    won = (result == "no") if side == "NO" else (result == "yes")
    return (100 - a["cost"] - a["fee"]) if won else (-a["cost"] - a["fee"])


def arms_for(rows, close_ts, sig_ts, side, result):
    out = {}
    for L in LATS:
        a = entry(rows, close_ts, sig_ts, L, side)
        if a["status"] == "P":
            a["pnl"] = pnl_of(side, result, a)
        out[L] = a
    return out


def compact_arm(a):
    if a["status"] == "P":
        return ["P", a["ts"], a["cost"], a["fee"], a["vol"], a["pnl"]]
    return ["U", a["reason"]]


def settle_class(kind, flavor_signal, lo, hi, offv, result):
    """Outcome class of a NO-side fire from the official integer value (anchor d)."""
    if result == "yes":
        return "false_lock_YES"
    try:
        v = float(offv)
    except Exception:     # noqa: BLE001
        return "NO_value_unknown"
    if lo <= v <= hi:
        return "NO_but_value_inside_bracket"
    short = (v < lo) if kind == "max" else (v > hi)
    if flavor_signal == "na":
        return "NO_never_arrival" if short else "NO_overshoot_after_signal"
    return "NO_overshoot" if not short else "NO_never_arrival_after_signal"


def yes_set(rg):
    t, f, c = rg["type"], rg["floor"], rg["cap"]
    if t == "between":
        return f, c
    if t == "greater":
        return f + 1, 1e9
    return -1e9, c - 1


def sem_result(rg, v):
    lo, hi = yes_set(rg)
    return "yes" if lo <= v <= hi else "no"


def lst_str(ts, off):
    return (dt.datetime.fromtimestamp(ts, dt.timezone.utc) + dt.timedelta(hours=off)).strftime("%Y-%m-%d %H:%M LST")


def utc_str(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def terminal_status():
    """Read the companion FINAL-YES build verdicts from disk (frozen spec text says Part 2 needs Part 1 OR that spec)."""
    res = {}
    for nm in ("finality_A", "finality_B"):
        p = os.path.join(HERE, "out", nm + ".md")
        v = "unavailable"
        if os.path.exists(p):
            v = "unparsed"
            for ln in open(p).read().splitlines():
                if "Verdict" in ln and ":" in ln:
                    m = re.search(r"\b(PASS|KILL|INSUFFICIENT)\b", ln.rsplit(":", 1)[1])
                    if m:
                        v = m.group(1)
                        break
        res[nm] = v
    return res


def run_report():
    t_start = time.time()
    evs = [json.loads(l) for l in open(SIGNALS)]
    summ = json.load(open(SIG_SUMMARY))
    ev_ok = [e for e in evs if "skip" not in e]
    meta = {}
    for e in ev_ok:
        for rg in e["rungs"]:
            meta[rg["ticker"]] = (e, rg)
    rows_cache = {}

    def rows_of(tk):
        if tk not in rows_cache:
            rows_cache[tk] = load_rows(tk, meta[tk][0]["close_ts"])
        return rows_cache[tk]

    # ---------------------------------------------------------------- coverage
    n_na_rungs = sum(1 for e in ev_ok for rg in e["rungs"] if rg["fires"]["na"])
    na_cov = sum(1 for e in ev_ok for rg in e["rungs"] if rg["fires"]["na"] and rows_of(rg["ticker"]) != "not_fetched")
    day_events = [e for e in ev_ok if e["day_signal"]]
    day_full = [e for e in day_events if all(rows_of(rg["ticker"]) != "not_fetched" for rg in e["rungs"])]
    coverage = {"na_fired_bracket_rungs_universe": n_na_rungs, "na_fired_bracket_rungs_candle_covered": na_cov,
                "part1_priced_fraction": na_cov / max(n_na_rungs, 1),
                "day_signal_events_universe": len(day_events), "day_signal_events_full_ladder_covered": len(day_full),
                "part2_fraction": len(day_full) / max(len(day_events), 1),
                "events_universe": len(ev_ok)}

    # ---------------------------------------------------------------- Part 1 fires (+ pricing where covered)
    fires1 = []
    sem_chk = collections.Counter()
    for e in ev_ok:
        for rg in e["rungs"]:
            try:
                v = float(e["official_value"])
                sem_chk[(rg["type"], sem_result(rg, v) == rg["result"])] += 1
            except Exception:     # noqa: BLE001
                sem_chk[(rg["type"], "no_value")] += 1
            if rg["type"] != "between":
                continue
            rows = None
            for fl in FLAVORS:
                for ck, fr in rg["fires"][fl].items():
                    if rows is None:
                        rows = rows_of(rg["ticker"])
                    rec = {"ticker": rg["ticker"], "flavor": fl, "cell": ck, "event": e["event"], "date": e["date"],
                           "station": e["station"], "series": e["series"], "kind": e["kind"], "feed": e["feed"],
                           "floor": rg["floor"], "cap": rg["cap"], "result": rg["result"],
                           "official_value": e["official_value"], "close_ts": e["close_ts"], "k": fr["k"],
                           "obs_ts": fr["obs_ts"], "sig_ts": fr["sig_ts"], "E": fr["E"],
                           "class": settle_class(e["kind"], fl, rg["floor"], rg["cap"], e["official_value"], rg["result"]),
                           "covered": rows != "not_fetched"}
                    if rec["covered"]:
                        # *** SIDE/PRICE RULE: both flavours of FINAL-NO buy NO at 100 - yes_bid ***
                        rec["arms"] = arms_for(rows, e["close_ts"], fr["sig_ts"], "NO", rg["result"])
                    fires1.append(rec)

    # ---------------------------------------------------------------- universe-level signal facts (no pricing)
    univ = {}
    for fl in FLAVORS:
        for ck in CELLKEYS:
            fs = [f for f in fires1 if f["flavor"] == fl and f["cell"] == ck]
            n = len(fs)
            fl_k = sum(1 for f in fs if f["result"] == "yes")
            p, lo_, hi_ = wilson(fl_k, n)
            univ[(fl, ck)] = {"n_fires": n, "n_yes": fl_k, "rate": p, "wilson_ub": hi_,
                              "days": len({f["date"] for f in fs}), "stations": len({f["station"] for f in fs}),
                              "classes": dict(collections.Counter(f["class"] for f in fs))}

    def stats_cell(fl, ck, L, cluster_key="date"):
        fs = [f for f in fires1 if f["flavor"] == fl and f["cell"] == ck and f["covered"]]
        n = len(fs)
        priced = [f for f in fs if f["arms"][L]["status"] == "P"]
        unt = n - len(priced)
        fl_k = sum(1 for f in fs if f["result"] == "yes")
        fl_p = sum(1 for f in priced if f["result"] == "yes")
        a_p, _a_lo, a_hi = wilson(fl_k, n)
        p_p, _p_lo, p_hi = wilson(fl_p, len(priced))
        ck_ = (lambda f: f["date"]) if cluster_key == "date" else (lambda f: f["event"])
        wi = [(ck_(f), f["arms"][L]["vol"], f["arms"][L]["pnl"]) for f in priced]
        un = [(ck_(f), 1.0, f["arms"][L]["pnl"]) for f in priced]
        sv, su = cluster_stats(wi), cluster_stats(un)
        ndays = len({f["date"] for f in priced})
        nev = len({f["event"] for f in priced})
        nst = len({f["station"] for f in priced})
        df = (ndays - 1) if cluster_key == "date" else (nev - 1)
        bar = tq(BAR_P, df)
        ub979 = ub99792 = ub979_unw = None
        if sv["mean"] is not None and sv["se"] is not None and df >= 1:
            ub979 = sv["mean"] + tq(0.979, df) * sv["se"]
            ub99792 = sv["mean"] + tq(1 - 0.05 / 24, df) * sv["se"]
        if su["mean"] is not None and su["se"] is not None and df >= 1:
            ub979_unw = su["mean"] + tq(0.979, df) * su["se"]
        reasons = collections.Counter(f["arms"][L].get("reason") for f in fs if f["arms"][L]["status"] != "P")
        row = {"flavor": fl, "cell": ck, "G": int(ck.split("_")[0][1:]), "R": int(ck.split("_")[1][1:]),
               "W": int(ck.split("_")[3][1:]), "L": L, "cluster": cluster_key,
               "n_fires_covered": n, "n_priced": len(priced), "n_untradeable": unt,
               "untradeable_frac": (unt / n) if n else None, "untradeable_reasons": dict(reasons),
               "false_locks_all_covered": fl_k, "false_lock_rate_all_covered": a_p, "false_lock_wilson_ub_all_covered": a_hi,
               "false_locks_priced": fl_p, "false_lock_rate_priced": p_p, "false_lock_wilson_ub_priced": p_hi,
               "ev_c_vw": sv["mean"], "se_vw": sv["se"], "t_vw": sv["t"], "ev_c_unw": su["mean"], "t_unw": su["t"],
               "n_priced_vol_gt0": sum(1 for f in priced if f["arms"][L]["vol"] > 0),
               "days_priced": ndays, "events_priced": nev, "stations_priced": nst, "df": df, "t_bar": bar,
               "ub_one_sided_97.9": ub979, "ub_one_sided_99.792": ub99792, "ub_one_sided_97.9_unw": ub979_unw,
               "mean_cost_c": (sum(f["arms"][L]["cost"] for f in priced) / len(priced)) if priced else None,
               "no_win_rate_priced": (sum(1 for f in priced if f["result"] == "no") / len(priced)) if priced else None}
        U = univ[(fl, ck)]
        crit = {
            "1_false_lock_all_fires_universe": U["rate"] is not None and U["rate"] <= 0.02 and U["wilson_ub"] <= 0.05,
            "1_false_lock_priced": p_p is not None and p_p <= 0.02 and p_hi <= 0.05,
            "2_ev_ge_2c_vw": sv["mean"] is not None and sv["mean"] >= 2.0,
            "3_t_ge_bar": sv["t"] is not None and bar is not None and sv["t"] >= bar,
            "4_n_ge_100_days_ge_40_stations_ge_10": len(priced) >= 100 and ndays >= 40 and nst >= 10,
            "5_untradeable_le_70": n > 0 and unt / n <= 0.70,
        }
        row["criteria"] = crit
        row["passes_all"] = all(crit.values())
        return row

    cells = []
    for fl in FLAVORS:
        for ck in CELLKEYS:
            for L in LATS:
                cells.append(stats_cell(fl, ck, L, "date"))
    cells_cityday = [stats_cell("na", ck, L, "event") for ck in CELLKEYS for L in LATS]

    na10 = [r for r in cells if r["flavor"] == "na" and r["L"] == 10]
    passing = [r for r in na10 if r["passes_all"]]
    prim10 = next(r for r in na10 if r["cell"] == PRIMARY_KEY)
    Uprim = univ[("na", PRIMARY_KEY)]
    kill = []
    if Uprim["rate"] is not None and Uprim["rate"] > 0.05:
        kill.append("primary-cell false-lock rate (all fires, full universe) %.2f%% > 5%%" % (100 * Uprim["rate"]))
    pos = [r for r in na10 if r["ev_c_vw"] is not None and r["ev_c_vw"] > 0]
    if pos and all(r["n_priced"] < 100 for r in pos):
        kill.append("every L=10 cell with EV>0 fails the n>=100 floor")
    ubs = [r["ub_one_sided_97.9"] for r in na10 if r["ub_one_sided_97.9"] is not None]
    ubs_unw = [r["ub_one_sided_97.9_unw"] for r in na10 if r["ub_one_sided_97.9_unw"] is not None]
    if ubs and max(ubs) < 0.5:
        kill.append("best L=10 one-sided 97.9%% EV upper bound %.2fc < +0.5c (volume-weighted, formal)" % max(ubs))
    complete = coverage["part1_priced_fraction"] >= 0.999
    verdict1 = "PASS" if passing else ("KILL" if kill else "INSUFFICIENT")

    # ---------------------------------------------------------------- Part 2 (whole ladder)
    days2 = []
    skipped2 = collections.Counter()
    for e in day_events:
        if not all(rows_of(rg["ticker"]) != "not_fetched" for rg in e["rungs"]):
            skipped2["ladder_not_fully_candle_covered"] += 1
            continue
        ds = e["day_signal"]
        vstar = int(math.floor(ds["E"] + 0.5))
        rgs = e["rungs"]
        preds = [yes_set(rg)[0] <= vstar <= yes_set(rg)[1] for rg in rgs]
        if len(rgs) < 5 or sum(preds) != 1:
            skipped2["incomplete_ladder_(not_exactly_one_inferred_winner)"] += 1
            continue
        order_ = sorted(range(len(rgs)), key=lambda i: yes_set(rgs[i])[0])
        pos_ = {i: j for j, i in enumerate(order_)}
        iw = pos_[preds.index(True)]
        recs = []
        for i, rg in enumerate(rgs):
            lyi, hyi = yes_set(rg)
            if preds[i]:
                flav, side = "winner", "YES"
            else:
                side = "NO"        # *** inferred loser: buy NO at 100 - yes_bid, never 100 - yes_ask ***
                above = lyi > vstar
                flav = "na" if (above == (e["kind"] == "max")) else "os"
            arms = arms_for(rows_of(rg["ticker"]), e["close_ts"], ds["sig_ts"], side, rg["result"])
            recs.append({"ticker": rg["ticker"], "type": rg["type"], "side": side, "flavor": flav,
                         "dist": abs(pos_[i] - iw), "result": rg["result"], "arms": arms})
        wrong = [r for r in recs if r["flavor"] == "winner"][0]["result"] == "no"
        days2.append({"event": e["event"], "date": e["date"], "station": e["station"], "kind": e["kind"],
                      "series": e["series"], "feed": e["feed"], "E_star": ds["E"], "v_star": vstar,
                      "obs_ts": ds["obs_ts"], "sig_ts": ds["sig_ts"], "close_ts": e["close_ts"],
                      "official_value": e["official_value"], "inference_wrong": wrong, "rungs": recs})
    part2 = {}
    for L in LATS:
        per_day = []
        for d in days2:
            pr = [r["arms"][L]["pnl"] for r in d["rungs"] if r["arms"][L]["status"] == "P"]
            per_day.append((d, len(pr), sum(pr)))
        nd = len(per_day)
        if nd < 2:
            part2[L] = {"n_days": nd}
            continue
        nets = [x[2] for x in per_day]
        fcs = [x[1] for x in per_day]
        mu = sum(nets) / nd
        sd = math.sqrt(sum((x - mu) ** 2 for x in nets) / (nd - 1))
        t = mu / (sd / math.sqrt(nd)) if sd > 0 else None
        pos_days = [x for x in per_day if x[1] > 0]
        # fire-level (naive) t, to show how much the independence assumption would inflate it
        allp = [(d["event"], 1.0, r["arms"][L]["pnl"]) for d in days2 for r in d["rungs"] if r["arms"][L]["status"] == "P"]
        naive = [(i, 1.0, p) for i, (_c, _w, p) in enumerate(allp)]
        wrong_days = [x for x in per_day if x[0]["inference_wrong"]]
        right_days = [x for x in per_day if not x[0]["inference_wrong"]]
        by_dist, by_flav = {}, {}
        for key, sel, store in (("dist", lambda r: r["dist"], by_dist), ("flavor", lambda r: r["flavor"], by_flav)):
            groups = collections.defaultdict(list)
            for d in days2:
                for r in d["rungs"]:
                    groups[sel(r)].append((d["event"], r))
            for g, lst in sorted(groups.items()):
                pr = [(c, 1.0, r["arms"][L]["pnl"]) for c, r in lst if r["arms"][L]["status"] == "P"]
                cs_ = cluster_stats(pr)
                store[str(g)] = {"n_rungs": len(lst), "n_priced": len(pr),
                                 "untradeable_frac": 1 - len(pr) / len(lst) if lst else None,
                                 "ev_c": cs_["mean"], "t_cityday": cs_["t"], "cityday_clusters": cs_["clusters"],
                                 "win_rate": (sum(1 for c, r in lst if r["arms"][L]["status"] == "P" and
                                                  ((r["result"] == "no") if r["side"] == "NO" else (r["result"] == "yes")))
                                              / len(pr)) if pr else None,
                                 "mean_cost_c": (sum(r["arms"][L]["cost"] for c, r in lst if r["arms"][L]["status"] == "P")
                                                 / len(pr)) if pr else None}
        part2[L] = {
            "n_days": nd, "df": nd - 1, "t_bar": tq(BAR_P, nd - 1),
            "mean_fires_per_signalling_day": sum(fcs) / nd, "mean_fires_per_day_with_>=1_fire": (
                sum(x[1] for x in pos_days) / len(pos_days)) if pos_days else None,
            "days_with_>=1_fire": len(pos_days), "frac_days_with_>=1_fire": len(pos_days) / nd,
            "mean_net_c_per_day": mu, "sd_net_c_per_day": sd, "t_cityday_clustered": t,
            "mean_net_c_per_day_given_>=1_fire": (sum(x[2] for x in pos_days) / len(pos_days)) if pos_days else None,
            "total_fires": sum(fcs), "total_net_c": sum(nets),
            "naive_fire_level_t_(wrong:independence)": cluster_stats(naive)["t"],
            "frac_days_inference_wrong": len(wrong_days) / nd,
            "mean_net_c_inference_right_days": (sum(x[2] for x in right_days) / len(right_days)) if right_days else None,
            "mean_net_c_inference_wrong_days": (sum(x[2] for x in wrong_days) / len(wrong_days)) if wrong_days else None,
            "worst_day_net_c": min(nets), "best_day_net_c": max(nets),
            "by_distance_rungs": by_dist, "by_flavor": by_flav,
        }
    term = terminal_status()
    gate = (verdict1 == "PASS") or any(v == "PASS" for v in term.values())
    p2_10 = part2.get(10, {})
    p2_pass_stats = (p2_10.get("n_days", 0) >= 2 and p2_10.get("mean_fires_per_signalling_day", 0) >= 3
                     and p2_10.get("mean_net_c_per_day", -1e9) >= 4.0 and p2_10.get("t_cityday_clustered") is not None
                     and p2_10["t_cityday_clustered"] >= p2_10["t_bar"])
    if gate and p2_pass_stats:
        verdict2 = "PASS"
    elif not gate:
        verdict2 = "NOT_EVALUABLE"      # the frozen gate (Part 1 or TERMINAL_FINALITY passes) is unmet; no PASS is possible
    else:
        verdict2 = "INSUFFICIENT"

    # ---------------------------------------------------------------- anchors
    anchors = build_anchors(evs, ev_ok, summ, fires1, rows_of, meta, sem_chk, days2)
    out = {
        "spec": "venue_expansion/FINALITY_NO_LADDER_SPEC.md (frozen 2026-10-27) -- BUILD A (primary)",
        "seed": SEED, "grid": CELLKEYS, "primary_cell": PRIMARY_KEY,
        "side_price_rule": "FINAL-NO buys NO at cost 100 - yes_bid (NEVER 100 - yes_ask); winner-YES buys YES at yes_ask",
        "coverage": coverage, "signals_summary": summ,
        "universe_signal_level": {f"{fl}|{ck}": v for (fl, ck), v in univ.items()},
        "verdict_part1": verdict1, "part1_passing_cells_L10": [r["cell"] for r in passing], "part1_kill_triggers": kill,
        "part1_best_ub979_L10": max(ubs) if ubs else None,
        "part1_best_ub979_L10_unweighted": max(ubs_unw) if ubs_unw else None,
        "verdict_part2": verdict2, "terminal_finality_status": term, "part2_gate_met": gate,
        "cells_date_clustered": cells, "cells_cityday_clustered_na": cells_cityday,
        "part2": {str(L): v for L, v in part2.items()}, "part2_skips": dict(skipped2),
        "anchors": anchors,
        "schema": {
            "part1_fires": "per rung+flavor: cells{cellkey:[k,obs_ts,sig_ts,E,[arm L0,arm L10,arm L20]]}; arm = "
                           "['P',entry_candle_end_ts,cost_c,fee_c,entry_volume,pnl_c] | ['U',reason]; NO side: cost=100-yes_bid",
            "part2_days": "per signalling city-day: rungs[{ticker,side,flavor,dist,result,arms[L0,L10,L20]}]; "
                          "winner side YES cost=yes_ask, losers side NO cost=100-yes_bid",
            "recompute": "cost/fee/pnl are fully determined by the arm fields and the official result; signal fields "
                         "are reproducible from cache/finality_no/A/obs via `finality_no_A.py signals`."},
    }
    pf = collections.defaultdict(lambda: None)
    p1 = {}
    for f in fires1:
        if not f["covered"]:
            continue
        key = (f["ticker"], f["flavor"])
        r = p1.get(key)
        if r is None:
            r = p1[key] = {"ticker": f["ticker"], "flavor": f["flavor"], "event": f["event"], "date": f["date"],
                           "station": f["station"], "series": f["series"], "kind": f["kind"], "feed": f["feed"],
                           "floor": f["floor"], "cap": f["cap"], "result": f["result"],
                           "official_value": f["official_value"], "close_ts": f["close_ts"], "class": f["class"],
                           "cells": {}}
        r["cells"][f["cell"]] = [f["k"], f["obs_ts"], f["sig_ts"], f["E"], [compact_arm(f["arms"][L]) for L in LATS]]
    out["part1_fires"] = list(p1.values())
    out["part2_days"] = [{**{k: v for k, v in d.items() if k != "rungs"},
                          "rungs": [{**{k: v for k, v in r.items() if k != "arms"},
                                     "arms": [compact_arm(r["arms"][L]) for L in LATS]} for r in d["rungs"]]}
                         for d in days2]
    json.dump(out, open(OUT_JSON, "w"), default=str)
    print("wrote", OUT_JSON, os.path.getsize(OUT_JSON) // 1024, "KB;", f"report {time.time() - t_start:.0f}s")
    md = build_md(out, univ, cells, cells_cityday, part2, days2, fires1, complete)
    open(OUT_MD, "w").write(md)
    print("wrote", OUT_MD)
    return out


def oracle_capturable_60(rows, close_ts, result):
    """EDGE_SIZING Stage-1 definition, re-derived with the SAME fee/98c constants and normalize(): the WINNER side is
    buyable <=98c with net>0 in the final 60 minutes.  Winner cost = yes_ask if YES else 100 - yes_bid."""
    best, n = None, 0
    for ts, yb, ya, vol in rows:
        if ts < close_ts - 3600:
            continue
        cost = ya if result == "yes" else (None if yb is None else 100 - yb)
        if cost is None or not (0 < cost <= MAX_PAY_C):
            continue
        net = 100 - cost - V2.fee_c(cost)
        if net <= 0:
            continue
        n += 1
        if best is None or cost < best[0]:
            best = (cost, net)
    return {"capturable": n > 0, "n_min": n, "best_cost": best[0] if best else None, "best_net": best[1] if best else None}


def worked_examples(ev_ok, fires1):
    """One real fire, shown end to end: timezone handling (anchor c) and prefix-only evaluation (anchor b)."""
    cand = [f for f in fires1 if f["flavor"] == "na" and f["cell"] == PRIMARY_KEY and f["covered"]
            and f["arms"][10]["status"] == "P" and f["feed"] == "iem_1min"]
    def _discriminating(f):
        e_ = next(x for x in ev_ok if x["event"] == f["event"])
        sh = e_.get("tz_shift_extremes") or {}
        try:
            ov = round(float(e_["official_value"]))
        except Exception:     # noqa: BLE001
            return False
        return (all(k in sh for k in ("-1", "0", "1")) and round(sh["0"]) == ov and round(sh["-1"]) != ov
                and round(sh["1"]) != ov)
    cand.sort(key=lambda f: (0 if _discriminating(f) else 1, 0 if f["kind"] == "min" else 1, f["ticker"]))
    if not cand:
        cand = sorted([f for f in fires1 if f["flavor"] == "na" and f["cell"] == PRIMARY_KEY and f["feed"] == "iem_1min"],
                      key=lambda f: f["ticker"])
    if not cand:
        return None
    f = cand[0]
    e = next(x for x in ev_ok if x["event"] == f["event"])
    sm = SERIES_MAP[e["series"]]
    off = sm["off"]
    d = parse_event_date(e["event"])
    exp_close = int((dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
                     - dt.timedelta(hours=off)).timestamp())
    day0 = exp_close - 86400
    ts, tf = load_station_obs(sm["station"], "1min")
    i0, i1 = bisect.bisect_left(ts, day0), bisect.bisect_left(ts, e["close_ts"])
    ots = [t for t, v in zip(ts[i0:i1], tf[i0:i1]) if GLITCH_LO_F <= v <= GLITCH_HI_F]
    of_ = [v for t, v in zip(ts[i0:i1], tf[i0:i1]) if GLITCH_LO_F <= v <= GLITCH_HI_F]
    k = f["k"]
    st = Stream(sm["kind"])
    first_ts = None
    for j in range(k + 1):
        before = st.E
        st.push(of_[j])
        if st.E != before:
            first_ts = ots[j]
    brackets = [(rg["ticker"], rg["floor"], rg["cap"]) for rg in e["rungs"] if rg["type"] == "between"]
    f_pre, d_pre = detect_event(ots[:k + 1], of_[:k + 1], sm["kind"], e["close_ts"], brackets)
    key = (f["ticker"], "na", PRIMARY_KEY)
    poison = of_[:k + 1] + [of_[k] + (50.0 if sm["kind"] == "max" else -50.0)] * (len(of_) - k - 1)
    f_poi, _ = detect_event(ots, poison, sm["kind"], e["close_ts"], brackets)
    shifts = {}
    offv = e["official_value"]
    if e.get("tz_shift_extremes"):
        shifts = e["tz_shift_extremes"]
    a10 = f["arms"][10]
    return {
        "ticker": f["ticker"], "event": e["event"], "station": sm["station"], "kind": sm["kind"], "off": off,
        "floor": f["floor"], "cap": f["cap"], "result": f["result"], "official_value": offv,
        "day0": day0, "exp_close": exp_close, "close_ts": e["close_ts"], "day0_utc": utc_str(day0),
        "day0_lst": lst_str(day0, off), "close_utc": utc_str(e["close_ts"]), "close_lst": lst_str(e["close_ts"], off),
        "close_wall_dst": (dt.datetime.fromtimestamp(e["close_ts"], dt.timezone.utc) + dt.timedelta(hours=off + 1)).strftime("%Y-%m-%d %H:%M (DST wall clock)"),
        "k": k, "n_obs_day": len(ots), "E": f["E"], "E_first_ts": first_ts,
        "E_first_utc": utc_str(first_ts) if first_ts else None, "E_first_lst": lst_str(first_ts, off) if first_ts else None,
        "obs_ts": f["obs_ts"], "obs_utc": utc_str(f["obs_ts"]), "obs_lst": lst_str(f["obs_ts"], off),
        "sig_ts": f["sig_ts"], "sig_utc": utc_str(f["sig_ts"]), "sig_lst": lst_str(f["sig_ts"], off),
        "mins_to_close_at_obs": (e["close_ts"] - f["obs_ts"]) / 60.0,
        "temp_at_signal": of_[k], "run_len": None, "max_prefix_ts": max(ots[:k + 1]),
        "prefix_ts_lt_sig": max(ots[:k + 1]) < f["sig_ts"],
        "prefix_rerun_same": key in f_pre and f_pre[key]["k"] == k and f_pre[key]["E"] == f["E"],
        "poison_rerun_same": key in f_poi and f_poi[key]["k"] == k and f_poi[key]["E"] == f["E"],
        "entry_L10": a10, "entry_ts_utc": utc_str(a10["ts"]) if a10["status"] == "P" else None,
        "entry_ts_lst": lst_str(a10["ts"], off) if a10["status"] == "P" else None,
        "shifts": shifts, "poison_value": of_[k] + (50.0 if sm["kind"] == "max" else -50.0),
    }


def build_anchors(evs, ev_ok, summ, fires1, rows_of, meta, sem_chk, days2):
    A = {}
    # ---------------- (a) oracle subset / price join
    ora = oracle_detail()
    pj = []
    ora_fired = []
    for r in ora:
        ct = utc_ts(r["close_time"])
        rows = load_rows(r["ticker"], ct)
        if isinstance(rows, str) or not rows:
            pj.append({"ticker": r["ticker"], "status": "no_rows"})
            continue
        mine = oracle_capturable_60(rows, ct, r["result"])
        pj.append({"ticker": r["ticker"], "result": r["result"], "stored_cost": r["best_winner_cost_c"],
                   "stored_net": r["best_net_c"], "stored_n_min": r["n_capturable_minutes"],
                   "mine_cost": mine["best_cost"], "mine_net": mine["best_net"], "mine_n_min": mine["n_min"],
                   "match": mine["best_cost"] == r["best_winner_cost_c"] and mine["best_net"] == r["best_net_c"]
                   and mine["n_min"] == r["n_capturable_minutes"]})
        if r["ticker"] in meta:
            e, rg = meta[r["ticker"]]
            fl = {f"{fl}:{ck}" for fl in FLAVORS for ck in rg["fires"][fl]}
            if fl:
                ora_fired.append({"ticker": r["ticker"], "result": r["result"], "fires": sorted(fl)[:6]})
    # every priced NO-side fire whose side WON and whose entry lies in the oracle window must be oracle-capturable
    chk, viol, outside = 0, [], 0
    for f in fires1:
        if not f["covered"] or f["result"] != "no":
            continue
        rows = rows_of(f["ticker"])
        orc = None
        for L in LATS:
            a = f["arms"][L]
            if a["status"] != "P":
                continue
            if a["ts"] < f["close_ts"] - 3600:
                outside += 1
                continue
            orc = orc or oracle_capturable_60(rows, f["close_ts"], f["result"])
            chk += 1
            if not orc["capturable"]:
                viol.append({"ticker": f["ticker"], "cell": f["cell"], "flavor": f["flavor"], "L": L})
    chk2, viol2 = 0, []
    for d in days2:
        for r in d["rungs"]:
            won = (r["result"] == "no") if r["side"] == "NO" else (r["result"] == "yes")
            for L in LATS:
                a = r["arms"][L]
                if a["status"] == "P" and won and a["ts"] >= d["close_ts"] - 3600:
                    chk2 += 1
                    if not oracle_capturable_60(rows_of(r["ticker"]), d["close_ts"], r["result"])["capturable"]:
                        viol2.append({"ticker": r["ticker"], "L": L})
    A["a_oracle"] = {
        "oracle_detail_rungs_stored": len(ora), "price_join_rows": pj,
        "price_join_matches": sum(1 for x in pj if x.get("match")),
        "price_join_checked": sum(1 for x in pj if "match" in x),
        "winning_priced_part1_fires_in_oracle_window_checked": chk, "part1_violations": viol,
        "part1_winning_fires_with_entry_before_final_60min_(oracle_window_cannot_speak)": outside,
        "winning_priced_part2_fires_in_oracle_window_checked": chk2, "part2_violations": viol2,
        "stored_oracle_rungs_on_which_the_rule_fires": ora_fired,
        "limitation": ("Only the top-40 'capturable_markets_detail' of out/edge_sizing_v2.json survives on disk; the full "
                       "140-market Stage-1 set is absent.  The subset test is therefore (i) a price-join reproduction on "
                       "those 40 rungs from my own fresh pull, and (ii) the Stage-1 capturable test re-derived on the same "
                       "candles for every priced fire whose side won and whose entry is inside the oracle's final 60 min."),
    }
    A["a_oracle"]["pass"] = (not viol and not viol2 and all(x.get("match") for x in pj if "match" in x))
    # ---------------- (b) no look-ahead
    A["b_no_lookahead"] = {"reruns_asserted_all_events": summ.get("lookahead_reruns"),
                           "method": ("for every distinct signal index k0 of every event: re-run the detector on obs[:k0+1] "
                                      "and on the full day with all later obs replaced by +50F / -50F from the k0 temperature; "
                                      "all decisions at indices <= k0 must be identical (assert; the script aborts otherwise)"),
                           "pass": bool(summ.get("lookahead_reruns"))}
    # ---------------- (c) monotonicity + timezone
    shift = {"max": collections.defaultdict(lambda: [0, 0, 0.0]), "min": collections.defaultdict(lambda: [0, 0, 0.0])}
    for e in ev_ok:
        if not e.get("tz_shift_extremes"):
            continue
        try:
            ov = float(e["official_value"])
        except Exception:     # noqa: BLE001
            continue
        for s_, v in e["tz_shift_extremes"].items():
            a = shift[e["kind"]][int(s_)]
            a[0] += 1
            a[1] += int(round(v) == round(ov))
            a[2] += abs(v - ov)
    A["c_monotonic_tz"] = {
        "monotonicity_violations": summ.get("monotonicity_violations"),
        "close_time_assertion": "close_time == LST midnight ending the event date (or 60 s earlier) for every event; skips: %s" % summ.get("event_skips"),
        "tz_window_shift_vs_official_value": {k: {str(s_): {"events": a[0], "exact_match_frac": a[1] / a[0],
                                                          "mean_abs_err_F": a[2] / a[0]} for s_, a in sorted(v.items())}
                                              for k, v in shift.items()},
        "settlement_semantics_vs_official_value": {f"{t}|{ok}": n for (t, ok), n in sorted(sem_chk.items(), key=str)},
    }
    A["c_monotonic_tz"]["pass"] = summ.get("monotonicity_violations", 1) == 0
    return A


def pct(x, d=2):
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


def f2(x, d=2):
    return "n/a" if x is None else f"{x:.{d}f}"


def cell_row_md(r):
    return (f"| {r['cell']} | {r['L']} | {r['n_fires_covered']} | {r['n_priced']} ({r['n_priced_vol_gt0']}) | "
            f"{pct(r['untradeable_frac'], 1)} | {r['false_locks_priced']} ({pct(r['false_lock_rate_priced'], 1)}, "
            f"{pct(r['false_lock_wilson_ub_priced'], 1)}) | {f2(r['mean_cost_c'], 1)} | {f2(r['ev_c_vw'])} | {f2(r['ev_c_unw'])} | "
            f"{f2(r['t_vw'])} ({f2(r['t_bar'])}) | {r['days_priced']}/{r['stations_priced']} | {f2(r['ub_one_sided_97.9'])} / "
            f"{f2(r['ub_one_sided_97.9_unw'])} | {'PASS' if r['passes_all'] else 'fails ' + ','.join(BAR_LABEL[k] for k, v in r['criteria'].items() if not v)} |")


BAR_LABEL = {"1_false_lock_all_fires_universe": "1u", "1_false_lock_priced": "1p", "2_ev_ge_2c_vw": "2",
             "3_t_ge_bar": "3", "4_n_ge_100_days_ge_40_stations_ge_10": "4", "5_untradeable_le_70": "5"}
CELL_HDR = ("| cell | L | fires (covered) | priced (vol>0) | untradeable | false locks priced (rate, Wilson UB) | mean NO cost c | "
            "EV vw c | EV unw c | t vw (bar) | days/stn | UB97.9 c (vw / unw) | bars |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def build_md(out, univ, cells, cells_cityday, part2, days2, fires1, complete):
    cov = out["coverage"]
    ev_ok = [json.loads(l) for l in open(SIGNALS)]
    ev_ok = [e for e in ev_ok if "skip" not in e]
    ex = worked_examples(ev_ok, fires1)
    W = []
    w = W.append
    w("# FINALITY-NO + WHOLE-LADDER -- BUILD A (primary) -- result\n")
    w("Spec: `venue_expansion/FINALITY_NO_LADDER_SPEC.md` (frozen 2026-10-27).  Code: `venue_expansion/finality_no_A.py`.  "
      "Per-fire records: `venue_expansion/out/finality_no_A.json`.  Seed %d.  Reproduce: `python venue_expansion/finality_no_A.py "
      "setup && ... order && ... candles && ... signals && ... report`.\n" % SEED)
    w("## Verdicts\n")
    w(f"- **Part 1 (FINAL-NO by never-arrival): {out['verdict_part1']}**  -- PASS cells at L=10: "
      f"{out['part1_passing_cells_L10'] or 'none'}; KILL triggers: {out['part1_kill_triggers'] or 'none'}; best L=10 one-sided "
      f"97.9% EV upper bound over the 12 cells: {f2(out['part1_best_ub979_L10'])}c volume-weighted (formal) / "
      f"{f2(out['part1_best_ub979_L10_unweighted'])}c unweighted.")
    w(f"- **Part 2 (whole ladder): {out['verdict_part2']}**  -- gate (Part 1 PASS or TERMINAL_FINALITY PASS): "
      f"{'met' if out['part2_gate_met'] else 'NOT met'}; companion FINAL-YES builds on disk: {out['terminal_finality_status']}.\n")
    w("{{COMMENTARY}}\n")
    w("## Sampling / coverage (read this first)\n")
    w(f"- **Part 1 priced stage: {cov['na_fired_bracket_rungs_candle_covered']:,} of {cov['na_fired_bracket_rungs_universe']:,} "
      f"never-arrival-fired bracket rungs have candlesticks = {pct(cov['part1_priced_fraction'])} "
      f"({'FULL UNIVERSE, no sampling' if complete else 'PARTIAL: a random prefix of a shuffled event order, seed ' + str(SEED)}).**  "
      f"Signal-level facts (fire counts, false-lock rates) always use all {cov['events_universe']:,} scored events.")
    w(f"- **Part 2 ladder stage: {cov['day_signal_events_full_ladder_covered']:,} of {cov['day_signal_events_universe']:,} "
      f"signalling city-days have the whole 6-rung ladder priced = {pct(cov['part2_fraction'])}** "
      f"({'full universe' if cov['part2_fraction'] >= 0.999 else 'a random prefix of the shuffled event order (seed %d), never re-sorted' % SEED}).")
    w("- Work order = sorted event list shuffled once with a fixed seed (`cache/finality_no/A/event_work_order.json`), never "
      "re-sorted.  Tier 1 (Part 1) prices only the bracket rungs that have a never-arrival fire in some cell (an obs-only "
      "decision made before any price or outcome was read); tier 2 (Part 2) prices every rung of every event with a day-level "
      "primary-cell signal.  The overshoot reference arm (anchor d) therefore only exists where tier 2 reached.\n")
    s = out["signals_summary"]
    w("## Universe, feeds, skips\n")
    w(f"- 40 US HIGH/LOW series (20 stations), settled rungs with official `result` and close_time UTC date in "
      f"2026-05-23..2026-10-20: **{cov['events_universe']:,} city-day events x 6 rungs (4 brackets `-B`, 2 thresholds `-T`)**.  "
      f"Event-level skips: {s['event_skips'] or 'none'}; pre-filter skips (counted, not tested): {s['universe_prefilter_skips']} "
      f"(`outside_window` = settled rungs of these series outside the frozen close-date window; `no_official_result` = 6 rungs "
      f"with no yes/no result).  Series outside the 40 mapped ones are not tested (no verified station / fixed LST offset).")
    feeds = collections.Counter(e["feed"] for e in ev_ok)
    w(f"- Obs feed per event: {dict(feeds)}.  Market lists and IEM obs were COPIED from the sibling FINAL-YES build's cache "
      f"(same universe, same sources; copying avoided re-pulling ~40k market rows and 240 IEM station-month files) and "
      f"spot-verified against the live API (batch-vs-single candle check below; every settled event has exactly 6 rungs).")
    bc = os.path.join(CACHE, "batch_vs_single_check.json")
    if os.path.exists(bc):
        bj = json.load(open(bc))
        w(f"- Candle pull: live-settled rungs use the batch endpoint `GET /markets/candlesticks?market_tickers=...` (one call per "
          f"event); verified byte-identical to the per-market endpoint on {sum(x['identical'] for x in bj)}/{len(bj)} rungs "
          f"(`cache/finality_no/A/batch_vs_single_check.json`).  Hist-settled rungs use `/historical/markets/{{ticker}}/candlesticks`.  "
          f"All parsed by the shared `edge_sizing_v2.normalize()`.\n")
    # ------------------------------------------------------------ timezone example
    w("## Worked timezone example (anchor c)\n")
    if ex:
        w(f"Fire `{ex['ticker']}` (station {ex['station']}, running {ex['kind'].upper()}, fixed standard offset UTC{ex['off']:+d}; "
          f"bracket [{ex['floor']},{ex['cap']}], official result `{ex['result']}`, official value {ex['official_value']}).\n")
        w(f"- Local-STANDARD day starts **{ex['day0_utc']}** (= {ex['day0_lst']}, epoch {ex['day0']}) and ends at LST midnight "
          f"**{ex['close_utc']}** (= {ex['close_lst']}, epoch {ex['close_ts']}); Kalshi's own `close_time` equals this (asserted for every "
          f"event, tolerance 60 s).  In DST wall-clock the same instant is {ex['close_wall_dst']}: the 'local day' is NOT wall-clock "
          f"midnight-to-midnight in summer (the classic 1-hour-skew trap).")
        w(f"- The running extreme E = {ex['E']} was last set at **{ex['E_first_utc']}** (= {ex['E_first_lst']}).  The signal observation "
          f"(index k={ex['k']} of {ex['n_obs_day']} obs that day) is **{ex['obs_utc']}** = {ex['obs_lst']}, "
          f"{ex['mins_to_close_at_obs']:.0f} min before close; signal stamped obs + 60 s = **{ex['sig_utc']}** (epoch {ex['sig_ts']}).  "
          f"Candle epochs are UTC `end_period_ts`, same clock as the obs epochs and `close_time`, so all three compare directly.")
        a = ex["entry_L10"]
        if a["status"] == "P":
            w(f"- L=10 entry: first candle with end_period_ts >= sig_ts + 600 s = {utc_str(ex['sig_ts'] + 600)}; found "
              f"**{ex['entry_ts_utc']}** (= {ex['entry_ts_lst']}), NO cost = 100 - yes_bid = {a['cost']}c, fee {a['fee']}c, "
              f"volume {a['vol']}; settles `{ex['result']}` -> pnl {a['pnl']}c.")
        w("\nProof the day window is right: the extreme of the 1-minute obs inside the window shifted by s hours, versus Kalshi's own "
          "`expiration_value` for this event:\n")
        if ex["shifts"]:
            w("| s (h) | " + " | ".join(f"{s_:+d}" for s_ in range(-3, 4)) + " |\n|---|" + "---|" * 7)
            w("| extreme F | " + " | ".join(f2(ex["shifts"].get(str(s_)), 1) if str(s_) in ex["shifts"] else "n/a" for s_ in range(-3, 4)) + " |")
            w("| = official? | " + " | ".join(("**YES**" if str(s_) in ex["shifts"] and round(ex["shifts"][str(s_)]) == round(float(ex["official_value"])) else "no") for s_ in range(-3, 4)) + " |")
        w("")
    c = out["anchors"]["c_monotonic_tz"]
    w("Across ALL events, exact-match fraction of the shifted-window extreme against the official integer (1-min feed):\n")
    w("| kind | " + " | ".join(f"s={s_:+d}" for s_ in range(-3, 4)) + " |\n|---|" + "---|" * 7)
    for kind in ("max", "min"):
        d = c["tz_window_shift_vs_official_value"].get(kind, {})
        w(f"| {kind} exact-match % | " + " | ".join(pct(d[str(s_)]["exact_match_frac"], 1) if str(s_) in d else "n/a" for s_ in range(-3, 4)) + " |")
        w(f"| {kind} mean abs err F | " + " | ".join(f2(d[str(s_)]["mean_abs_err_F"]) if str(s_) in d else "n/a" for s_ in range(-3, 4)) + " |")
    w("\nThe declared window (s=0) is the optimum for LOW markets and error grows with |s|; HIGH markets peak in the afternoon so the day "
      "boundary is nearly irrelevant for them (weakly informative).  The strict check is the `close_time == LST midnight` assertion.  "
      "Note the 1-minute IEM extreme equals Kalshi's official integer in well under 100% of days (official value is a different "
      "feed / rounding); that is exactly why `G >= 2` is in the spec.\n")
    # ------------------------------------------------------------ no look-ahead example
    w("## Worked no-look-ahead example (anchor b)\n")
    if ex:
        w(f"Same fire (`{ex['ticker']}`, primary cell {PRIMARY_KEY}, never-arrival): at obs index k={ex['k']}, E = {ex['E']}F, "
          f"current temp {ex['temp_at_signal']}F; the detector is a `Stream` that consumes one obs at a time, so state after obs k is a "
          f"function of obs[0..k] only.  max obs ts in the prefix = {utc_str(ex['max_prefix_ts'])} < signal ts {ex['sig_utc']}: "
          f"{ex['prefix_ts_lt_sig']}.  Re-running the detector on obs[:k+1] only reproduces the fire: {ex['prefix_rerun_same']}; "
          f"re-running on the full day with every later obs replaced by {ex['poison_value']}F (an adversarial +/-50F move) "
          f"reproduces it: {ex['poison_rerun_same']}.")
    la = out["anchors"]["b_no_lookahead"]
    w(f"\nAsserted in code for **every** distinct signal index of **every** event ({la['reruns_asserted_all_events']:,} detector re-runs: "
      f"truncated prefix, +50F future, -50F future); the script aborts on any difference.  0 violations (the run completed).\n")
    # ------------------------------------------------------------ Part 1
    w("## Part 1 -- FINAL-NO by never-arrival (bracket rungs)\n")
    na10 = [r for r in cells if r["flavor"] == "na" and r["L"] == 10]
    prim = next(r for r in na10 if r["cell"] == PRIMARY_KEY)
    Up = univ[("na", PRIMARY_KEY)]
    w(f"**Primary cell {PRIMARY_KEY} at L=10:** universe fires {Up['n_fires']:,} (false locks {Up['n_yes']} = {pct(Up['rate'])}, "
      f"Wilson UB {pct(Up['wilson_ub'])}, over {Up['days']} days / {Up['stations']} stations); priced stage: n priced = **{prim['n_priced']}** "
      f"of {prim['n_fires_covered']} covered fires (untradeable {pct(prim['untradeable_frac'], 1)}), priced false locks "
      f"{prim['false_locks_priced']} ({pct(prim['false_lock_rate_priced'])}, Wilson UB {pct(prim['false_lock_wilson_ub_priced'])}), "
      f"EV/contract volume-weighted **{f2(prim['ev_c_vw'])}c** (unweighted {f2(prim['ev_c_unw'])}c), signed day-clustered t "
      f"**{f2(prim['t_vw'])}** (bar {f2(prim['t_bar'])}), {prim['days_priced']} days, {prim['stations_priced']} stations; "
      f"entries with volume > 0: {prim['n_priced_vol_gt0']} (zero-volume entries carry zero weight in the weighted estimator).\n")
    w("### All 12 cells, L = 10 (the deployable arm), formal day-clustered statistics (calendar event-date clusters)\n")
    w(CELL_HDR)
    for r in na10:
        w(cell_row_md(r))
    w("\nUniverse-level (signal-only, every event, no pricing needed) false-lock rate per cell -- bar 1 is evaluated on this AND on the priced subset:\n")
    w("| cell | fires | settled YES (false lock) | rate | Wilson UB | days | stations | NO via never-arrival | NO via overshoot-after-signal | other |\n|---|---|---|---|---|---|---|---|---|---|")
    for ck in CELLKEYS:
        U = univ[("na", ck)]
        cl = U["classes"]
        oth = U["n_fires"] - U["n_yes"] - cl.get("NO_never_arrival", 0) - cl.get("NO_overshoot_after_signal", 0)
        w(f"| {ck} | {U['n_fires']:,} | {U['n_yes']} | {pct(U['rate'])} | {pct(U['wilson_ub'])} | {U['days']} | {U['stations']} | "
          f"{cl.get('NO_never_arrival', 0):,} | {cl.get('NO_overshoot_after_signal', 0)} | {oth} |")
    w("\n### L = 0 and L = 20 (reference arms), same statistics\n")
    w(CELL_HDR)
    for r in cells:
        if r["flavor"] == "na" and r["L"] in (0, 20):
            w(cell_row_md(r))
    w("\n### Robustness: city-day clustering (cluster = event, finer than calendar date) at L=10\n")
    w("| cell | n priced | EV vw c | t vw (city-day) | bar (df=events-1) | t vw (calendar day, formal) |\n|---|---|---|---|---|---|")
    for r in cells_cityday:
        if r["L"] == 10:
            fm = next(x for x in na10 if x["cell"] == r["cell"])
            w(f"| {r['cell']} | {r['n_priced']} | {f2(r['ev_c_vw'])} | {f2(r['t_vw'])} | {f2(r['t_bar'])} | {f2(fm['t_vw'])} |")
    # calibration of what is tradeable
    w("\n### Why tradeable fires are what they are (primary cell, L=10): market calibration at the entry price\n")
    pr = [f for f in fires1 if f["flavor"] == "na" and f["cell"] == PRIMARY_KEY and f["covered"] and f["arms"][10]["status"] == "P"]
    b = collections.defaultdict(lambda: [0, 0, 0.0])
    for f in pr:
        c_ = f["arms"][10]["cost"]
        key = "<=50c" if c_ <= 50 else "51-80c" if c_ <= 80 else "81-90c" if c_ <= 90 else "91-95c" if c_ <= 95 else "96-98c"
        b[key][0] += 1
        b[key][1] += int(f["result"] == "no")
        b[key][2] += f["arms"][10]["pnl"]
    w("| NO cost bucket | n | NO wins | NO win rate | mean pnl c |\n|---|---|---|---|---|")
    for key in ("<=50c", "51-80c", "81-90c", "91-95c", "96-98c"):
        if key in b:
            n_, k_, p_ = b[key]
            w(f"| {key} | {n_} | {k_} | {pct(k_ / n_, 1)} | {f2(p_ / n_)} |")
    w("\nUntradeable reasons, primary cell L=10: " + json.dumps(prim["untradeable_reasons"]) + ".\n")
    # ------------------------------------------------------------ anchor d
    w("## Anchor (d) -- never-arrival and overshoot reported separately\n")
    w("Part 1 (the spec's new shape) is the never-arrival signal.  Overshoot is what the deployed rule can already lock; the same "
      "G/R/H/W gating applied to it is shown ONLY as a separate reference (not part of any bar, not Bonferroni-counted, and only over "
      "events whose full ladder was priced).\n")
    w("| flavor | cell | L | fires (covered) | priced | untradeable | false locks (all covered) | EV vw c | EV unw c | t vw |\n|---|---|---|---|---|---|---|---|---|---|")
    for fl in FLAVORS:
        for r in cells:
            if r["flavor"] == fl and r["L"] == 10 and r["cell"] in (PRIMARY_KEY, "G2_R2_H3_W120", "G6_R2_H3_W120"):
                w(f"| {'never-arrival' if fl == 'na' else 'overshoot (ref)'} | {r['cell']} | 10 | {r['n_fires_covered']} | {r['n_priced']} | "
                  f"{pct(r['untradeable_frac'], 1)} | {r['false_locks_all_covered']} ({pct(r['false_lock_rate_all_covered'])}) | "
                  f"{f2(r['ev_c_vw'])} | {f2(r['ev_c_unw'])} | {f2(r['t_vw'])} |")
    w("\nSettlement class of every never-arrival fire (universe level), by official integer value: see the table above "
      "(`NO via never-arrival` = official value stayed short of the bracket; `NO via overshoot-after-signal` = the official value "
      "ended past the bracket after the signal, i.e. NO for the other reason).\n")
    # ------------------------------------------------------------ Part 2
    w("## Part 2 -- whole-ladder pricing from one inference\n")
    w(f"Signal = primary-cell FINAL-NO on any bracket rung of the city-day (the companion FINAL-YES primary cell cannot fire on integer "
      f"data, so the union equals this set), t* = earliest such obs, v* = round(E*), inferred winner = the rung whose YES set contains v*; "
      f"every other rung is an inferred loser.  Winner: buy YES at yes_ask; losers: buy NO at **100 - yes_bid**; each gated "
      f"independently at the first qualifying candle at/after t*+L.  Skips: {out['part2_skips'] or 'none'}.\n")
    w("| L | signalling days | mean fires / signalling day | days with >=1 fire | mean net c / day | sd | day-clustered t (bar) | "
      "total fires | naive fire-level t (invalid) |\n|---|---|---|---|---|---|---|---|---|")
    for L in LATS:
        p = part2.get(L, {})
        if p.get("n_days", 0) < 2:
            w(f"| {L} | {p.get('n_days', 0)} | n/a | | | | | | |")
            continue
        w(f"| {L} | {p['n_days']} | {f2(p['mean_fires_per_signalling_day'])} | {p['days_with_>=1_fire']} ({pct(p['frac_days_with_>=1_fire'], 1)}) | "
          f"{f2(p['mean_net_c_per_day'])} | {f2(p['sd_net_c_per_day'])} | {f2(p['t_cityday_clustered'])} ({f2(p['t_bar'])}) | "
          f"{p['total_fires']} | {f2(p['naive_fire_level_t_(wrong:independence)'])} |")
    p10 = part2.get(10, {})
    if p10.get("n_days", 0) >= 2:
        w(f"\nL=10: mean fires per signalling city-day **{f2(p10['mean_fires_per_signalling_day'])}** (spec needs >= 3), per-day net EV "
          f"**{f2(p10['mean_net_c_per_day'])}c** (needs >= +4.0c), day-clustered t **{f2(p10['t_cityday_clustered'])}** (bar {f2(p10['t_bar'])}).  "
          f"Days where the inference was wrong (inferred winner settled NO): {pct(p10['frac_days_inference_wrong'], 1)}; mean day net "
          f"{f2(p10['mean_net_c_inference_right_days'])}c when right vs {f2(p10['mean_net_c_inference_wrong_days'])}c when wrong; "
          f"worst day {f2(p10['worst_day_net_c'], 0)}c, best {f2(p10['best_day_net_c'], 0)}c.\n")
        w("### EV by |distance from the inferred extreme| in rungs (L=10; cluster = city-day)\n")
        w("| distance (rungs) | rungs | priced | untradeable | win rate | mean cost c | EV c/fire | t (city-day) |\n|---|---|---|---|---|---|---|---|")
        for dkey, v in sorted(p10["by_distance_rungs"].items(), key=lambda kv: int(kv[0])):
            w(f"| {dkey} | {v['n_rungs']} | {v['n_priced']} | {pct(v['untradeable_frac'], 1)} | {pct(v['win_rate'], 1)} | "
              f"{f2(v['mean_cost_c'], 1)} | {f2(v['ev_c'])} | {f2(v['t_cityday'])} |")
        w("\n### EV by side/flavor (L=10): winner = inferred-winner YES; na = never-arrival-side losers; os = overshoot-side losers\n")
        w("| flavor | rungs | priced | untradeable | win rate | mean cost c | EV c/fire | t (city-day) |\n|---|---|---|---|---|---|---|---|")
        for fk, v in sorted(p10["by_flavor"].items()):
            w(f"| {fk} | {v['n_rungs']} | {v['n_priced']} | {pct(v['untradeable_frac'], 1)} | {pct(v['win_rate'], 1)} | "
              f"{f2(v['mean_cost_c'], 1)} | {f2(v['ev_c'])} | {f2(v['t_cityday'])} |")
    w("\nCorrelation structure: all rungs of a city-day share one inference, so one wrong inference loses the day's basket; the "
      "t above treats the city-day as the unit.  The 'naive fire-level t' column treats every fire as independent and is shown only "
      "to quantify how badly that would overstate significance.\n")
    # ------------------------------------------------------------ anchors
    A = out["anchors"]
    w("## Sanity anchors\n")
    a = A["a_oracle"]
    w(f"**(a) Oracle subset / price join -- {'HOLDS' if a['pass'] else 'FAILS'}.**  Price join: {a['price_join_matches']}/{a['price_join_checked']} of the "
      f"stored Stage-1 oracle rungs re-derived from my own fresh candle pull reproduce the stored best winner cost, best net and "
      f"capturable-minute count exactly.  Subset test: of {a['winning_priced_part1_fires_in_oracle_window_checked']} winning priced Part-1 fires "
      f"(NO side, entry inside the oracle's final-60-min window) {len(a['part1_violations'])} are not oracle-capturable; of "
      f"{a['winning_priced_part2_fires_in_oracle_window_checked']} winning priced Part-2 fires {len(a['part2_violations'])}.  "
      f"({a['part1_winning_fires_with_entry_before_final_60min_(oracle_window_cannot_speak)']} winning fires entered before the final 60 min, "
      f"outside the oracle's window.)  The rule fires on {len(a['stored_oracle_rungs_on_which_the_rule_fires'])} of the stored oracle rungs.  "
      f"Limitation: {a['limitation']}")
    w(f"\n**(b) No look-ahead -- {'HOLDS' if A['b_no_lookahead']['pass'] else 'FAILS'}.**  See worked example; {A['b_no_lookahead']['method']}.")
    w(f"\n**(c) Monotonicity / timezone -- {'HOLDS' if c['pass'] else 'FAILS'}.**  Running-extreme monotonicity violations over all event-days: "
      f"**{c['monotonicity_violations']}**.  {c['close_time_assertion']}.  Settlement semantics check (official integer value reproduces "
      f"the official `result` under between: floor<=v<=cap, greater: v>floor, less: v<cap): {c['settlement_semantics_vs_official_value']}.")
    w("\n**(d) Overshoot separation** -- see the anchor (d) section: never-arrival and overshoot are separate rows, and the verdict uses never-arrival only.\n")
    w("{{CAVEATS}}\n")
    return "\n".join(W)


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
        run_report()
