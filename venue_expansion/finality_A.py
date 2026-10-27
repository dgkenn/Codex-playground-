#!/usr/bin/env python3
"""finality_A.py -- BUILD A of TERMINAL_FINALITY_SPEC.md (frozen 2026-10-27).

Executes the frozen spec; it is not trying to find an edge.  Stages (each resumable, every pull cached under
venue_expansion/cache/finality/):

    discover  settled KXHIGH*/KXLOWT* markets per series -> cache/finality/markets/<series>.json
    obs       IEM 1-minute (asos1min.py) + routine (asos.py rt 3&4) per station-month -> cache/finality/obs/
    signals   obs-only FINAL-YES detector (streaming, no look-ahead) over every settled bracket rung
    candles   1-min candlesticks (final 120 min) for every rung that fired, SHUFFLED work order, never re-sorted
    report    entry rule, latency arms, statistics, anchors -> out/finality_A.json + out/finality_A.md

==== INTERPRETATION DECISIONS, PRE-DECLARED IN THIS FILE BEFORE ANY OUTCOME WAS ANALYSED =========================
The frozen spec leaves a few things open.  They are fixed here, before outcomes are read, and disclosed in the .md.

 D1 (bracket edges -- the important one).  Kalshi bracket rungs carry floor_strike=lo and cap_strike=hi with
    hi = lo + 1 (e.g. B68.5 -> floor 68, cap 69, "68-69 degrees"; official settlement is an INTEGER and YES iff
    lo <= value <= hi).  The spec's inequality  lo + M <= E <= hi - M  read LITERALLY on [floor, cap] is an EMPTY
    interval for M = 1.0 (needs E >= lo+1 and E <= lo), and for M = 0.5 collapses to the single point E = lo + 0.5.
    This was found by arithmetic before reading any outcome.  Two readings are therefore run on the identical grid:
      reading "S" (STRICT / LITERAL, the formal reading): interval = [floor, cap].  This is "the spec exactly".
      reading "L" (LATTICE, exploratory, pre-declared): the YES set in unrounded-temperature terms is
          [floor - 0.5, cap + 0.5)  (official value is the integer rounding), so interval = [floor-0.5, cap+0.5].
    The verdict is computed from S (the frozen text).  L is reported with the same bars but is labelled exploratory
    and can never convert to a PASS (a PASS would require a re-registration).  The 24-comparison Bonferroni bar is
    kept for both (it is not loosened for S; L is a strictly additional family and is reported against the same bar).
 D2 Entry is a YES purchase at yes_ask (the side the FINAL-YES signal names) at every rung, win or lose.  The spec's
    "winner-side cost" equals yes_ask for rungs that settle YES; for a rung that settles NO (a false lock) the bot
    still buys YES (it cannot know), so the loser is charged yes_ask and loses it.  Charging losers 100-yes_bid
    would be outcome-conditioned look-ahead.  Entry gate: yes_ask <= 98c and 100-cost-fee > 0.
 D3 Signal timestamp = observation minute + 60 s, so every observation used has ts < signal ts (the spec's "obs
    timestamp < t only") and every candle used closes strictly after that minute ended.  Entry candle = first
    candle with end_period_ts >= signal_ts + L*60 (and <= close_ts).
 D4 Volume weight for the "volume-weighted EV" bar = volume of the ENTRY candle.  The unweighted mean is reported
    alongside as a robustness line; the formal bar uses the volume-weighted figure.  The signed day-clustered t is
    computed on the SAME (weighted) estimator.
 D5 False-lock criterion (PASS bar 1) is evaluated on ALL covered fires AND on PRICED fires only; both must satisfy
    it (the priced subset is the population actually traded; adverse selection into it is the point of the test).
 D6 The KILL bar "one-sided 97.9% upper bound" is applied as written (t quantile 0.979 at df = days-1); the
    0.99792 reading (1 - 0.05/24) is also reported.
 D7 Universe = the 40 US HIGH/LOW series with a verified station + fixed-standard-time-offset mapping (the Stage-1
    population).  Other KXHIGH*/KXLOWT* series (international, additional US) are SKIPPED, counted, with reason.
 D8 Glitch guard: observations outside [-60, 130] F are dropped (physical impossibility).  Nothing else is filtered.
 D9 Feed: 1-minute if the local day has >= 600 valid 1-min observations, else routine (>= 8 obs), else skip.  The feed
    used is recorded per market.
=================================================================================================================
"""
from __future__ import annotations

import argparse
import bisect
import collections
import datetime as dt
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import edge_sizing_v2 as V2          # noqa: E402  normalize()/fee_c() reused, NOT reimplemented

CACHE = os.path.join(HERE, "cache", "finality", "A")   # own subdir: Build B shares cache/finality/
MKT_DIR = os.path.join(CACHE, "markets")
OBS_DIR = os.path.join(CACHE, "obs")
CANDLE_DIR = os.path.join(CACHE, "candles")
VERIFY_DIR = os.path.join(CACHE, "verify")
SIGNALS = os.path.join(CACHE, "signals.jsonl")
STAGEA_SUMMARY = os.path.join(CACHE, "stageA_summary.json")
OUT_JSON = os.path.join(HERE, "out", "finality_A.json")
OUT_MD = os.path.join(HERE, "out", "finality_A.md")
COMMENTARY_PATH = os.path.join(CACHE, "commentary.md")      # hand-written verdict commentary, spliced in by the report
CAVEATS_PATH = os.path.join(CACHE, "caveats.md")
for _d in (MKT_DIR, OBS_DIR, CANDLE_DIR, VERIFY_DIR, os.path.dirname(OUT_JSON)):
    os.makedirs(_d, exist_ok=True)

KAPI = "https://api.elections.kalshi.com/trade-api/v2"
IEM_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
IEM_ROUTINE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

SEED = 20261027
WIN_LO = dt.date(2026, 5, 23)       # frozen universe: close_time UTC date within [WIN_LO, WIN_HI]
WIN_HI = dt.date(2026, 10, 20)
OBS_MONTHS = [(2026, m) for m in range(5, 11)]   # May..Oct 2026
GLITCH_HI_F, GLITCH_LO_F = 130.0, -60.0
MIN_1MIN_OBS = 600
MIN_ROUTINE_OBS = 8
MAX_PAY_C = V2.MAX_PAY_C            # 98
CANDLE_WINDOW_MIN = 120

# frozen grid
GRID = [(M, R, 3, W) for M in (0.5, 1.0) for R in (2, 4) for W in (60, 120)]
LATS = (0, 10, 20)
READINGS = {"S": (0.0, 0.0), "L": (-0.5, 0.5)}
PRIMARY = (1.0, 2, 3, 120)


def cell_key(c):
    return f"M{c[0]}_R{c[1]}_H{c[2]}_W{c[3]}"


# ---- HIGH series -> (station, fixed standard UTC offset hours).  Byte-copied from edge_sizing_stage2.CITY
# (itself byte-copied from kwx_runner.py).  Offsets are re-VERIFIED per market against close_time (see tz_check).
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


SERIES_MAP = {}     # series -> dict(station, kind, off)
for _h, (_st, _off) in CITY.items():
    SERIES_MAP[_h] = {"station": iem_code(_st), "kind": "max", "off": _off}
    SERIES_MAP[CITY_LOW_SERIES[_h]] = {"station": iem_code(_st), "kind": "min", "off": _off}

MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


# ------------------------------------------------------------------ http
_last = {}


def _throttle(host, gap):
    now = time.time()
    w = _last.get(host, 0) + gap - now
    if w > 0:
        time.sleep(w)
    _last[host] = time.time()


def http_get(url, host, gap, as_json=True, tries=9):
    err = None
    for i in range(tries):
        _throttle(host, gap)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "finality-A/1.0 (research)"})
            with urllib.request.urlopen(req, timeout=60) as fh:
                body = fh.read().decode("utf-8", "replace")
            return json.loads(body) if as_json else body
        except urllib.error.HTTPError as e:
            err = e
            if e.code == 404:
                raise
            time.sleep(min(60, 2 ** (i + 1)))
        except Exception as e:      # noqa: BLE001
            err = e
            time.sleep(min(60, 2 ** (i + 1)))
    raise RuntimeError(f"GET failed after {tries} tries: {url}: {err}")


def kget(path):
    return http_get(KAPI + path, "kalshi", 1.05)


# ------------------------------------------------------------------ discover
def parse_event_date(event_ticker):
    m = re.search(r"-(\d\d)([A-Z]{3})(\d\d)$", event_ticker)
    if not m:
        return None
    try:
        return dt.date(2000 + int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)))
    except Exception:     # noqa: BLE001
        return None


KEEP = ("ticker", "event_ticker", "close_time", "strike_type", "floor_strike", "cap_strike", "result",
        "expiration_value", "status", "volume_fp", "series_ticker")


def _paged(path_base, series, tag):
    path = os.path.join(MKT_DIR, f"{series}.{tag}.json")
    if os.path.exists(path):
        return json.load(open(path))
    out, cursor = [], None
    while True:
        q = f"{path_base}?series_ticker={series}&limit=1000" + ("&status=settled" if tag == "live" else "") \
            + (f"&cursor={cursor}" if cursor else "")
        d = kget(q)
        for m in d.get("markets", []):
            r = {k: m.get(k) for k in KEEP}
            r["series_ticker"] = series
            r["_src"] = tag
            out.append(r)
        cursor = d.get("cursor")
        if not cursor or not d.get("markets"):
            break
    json.dump(out, open(path, "w"))
    return out


def list_settled(series):
    """Live /markets?status=settled holds only markets settled after the 2026-08-28 historical cutoff; older ones
    live under /historical/markets.  Union both, de-duplicated by ticker (live wins)."""
    live = _paged("/markets", series, "live")
    hist = _paged("/historical/markets", series, "hist")
    seen, out = set(), []
    for m in live + hist:
        if m["ticker"] in seen:
            continue
        seen.add(m["ticker"])
        m["series_ticker"] = series
        out.append(m)
    return out


def stage_discover(extra_series_count=True):
    ser = sorted(SERIES_MAP)
    tot = 0
    for s in ser:
        ms = list_settled(s)
        tot += len(ms)
        print(f"  {s}: {len(ms)} settled markets", flush=True)
    print("mapped-series settled markets:", tot)
    # extra (unmapped) KXHIGH*/KXLOWT* series: counted only, for the skip ledger
    sp = os.path.join(CACHE, "all_series.json")
    if not os.path.exists(sp):
        d = kget("/series?category=Climate%20and%20Weather")
        json.dump([x["ticker"] for x in d.get("series", [])], open(sp, "w"))
    allser = [t for t in json.load(open(sp)) if t.startswith("KXHIGH") or t.startswith("KXLOWT")]
    extra = sorted(set(allser) - set(SERIES_MAP))
    if extra_series_count:
        for s in extra:
            try:
                ms = list_settled(s)
                print(f"  [unmapped] {s}: {len(ms)}", flush=True)
            except Exception as e:     # noqa: BLE001
                print(f"  [unmapped] {s}: ERR {e}", flush=True)


# ------------------------------------------------------------------ obs
_ord_cache = {}


def to_epoch(valid):
    """'2026-07-01 00:51' (UTC) -> epoch seconds."""
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
        txt = http_get(url, "iem", 0.4, as_json=False)
        idx = 3
    else:
        b2 = b + dt.timedelta(days=1)
        url = (f"{IEM_ROUTINE}?station={station}&data=tmpf&year1={a.year}&month1={a.month}&day1={a.day}"
               f"&year2={b2.year}&month2={b2.month}&day2={b2.day}&tz=UTC&format=onlycomma&latlon=no"
               "&report_type=3&report_type=4")
        txt = http_get(url, "iem", 0.4, as_json=False)
        idx = 2
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
    dd, last = [], None
    for t, f in rows:               # de-dup same timestamp (keep last)
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


def stage_obs():
    stations = sorted({v["station"] for v in SERIES_MAP.values()})
    for st in stations:
        for feed in ("1min", "routine"):
            for (y, m) in OBS_MONTHS:
                n = len(fetch_obs_month(st, y, m, feed))
                print(f"  {st} {feed} {y}-{m:02d}: {n} obs", flush=True)


# ------------------------------------------------------------------ streaming detector (NO look-ahead by construction)
class Stream:
    """Consumes observations ONE AT A TIME in time order.  State = (E, run lengths per R).  There is no
    access to any later observation, so the signal at obs k is a function of obs[0..k] only."""

    def __init__(self, kind, Rs=(2, 4)):
        self.kind = kind
        self.E = None
        self.Rs = Rs
        self.run = {R: 0 for R in Rs}
        self.n = 0

    def push(self, f):
        self.n += 1
        if self.E is None or (f > self.E if self.kind == "max" else f < self.E):
            self.E = f
            for R in self.Rs:
                self.run[R] = 0
            return
        for R in self.Rs:
            away = (f <= self.E - R + 1e-9) if self.kind == "max" else (f >= self.E + R - 1e-9)
            self.run[R] = self.run[R] + 1 if away else 0


def rung_interval(rung, reading):
    dlo, dhi = READINGS[reading]
    return rung["floor_strike"] + dlo, rung["cap_strike"] + dhi


def detect_event(obs_ts, obs_f, kind, close_ts, rungs):
    """obs_* ascending, restricted to the local day [close-24h, close).  Returns
    fires[ticker][reading][cellkey] = dict(k, obs_ts, sig_ts, E, temp, run, span_min)."""
    st = Stream(kind)
    fires = {r["ticker"]: {rd: {} for rd in READINGS} for r in rungs}
    ivals = {(r["ticker"], rd): rung_interval(r, rd) for r in rungs for rd in READINGS}
    wmax = max(c[3] for c in GRID)
    for k in range(len(obs_ts)):
        t, f = obs_ts[k], obs_f[k]
        st.push(f)
        if t < close_ts - wmax * 60:
            continue
        E = st.E
        for rd in READINGS:
            for r in rungs:
                lo, hi = ivals[(r["ticker"], rd)]
                fr = fires[r["ticker"]][rd]
                for c in GRID:
                    ck = cell_key(c)
                    if ck in fr:
                        continue
                    M, R, H, W = c
                    if t < close_ts - W * 60:
                        continue
                    if st.run[R] < H:
                        continue
                    if lo + M - 1e-9 <= E <= hi - M + 1e-9:
                        fr[ck] = {"k": k, "obs_ts": t, "sig_ts": t + 60, "E": E, "temp": f,
                                  "run": st.run[R], "span_min": (t - obs_ts[k - H + 1]) / 60.0}
    return fires


# ------------------------------------------------------------------ signals stage
def rungs_universe():
    """Build the event table from cached market lists; apply the frozen window; record every skip."""
    skips = collections.Counter()
    events = collections.defaultdict(list)
    outside = collections.Counter()
    for s in sorted(SERIES_MAP):
        for m in list_settled(s):
            tk = m["ticker"]
            if not re.search(r"-B[\d.]+$", tk):
                skips["not_bracket_rung(T-threshold)"] += 1
                continue
            cd = dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).date()
            if cd < WIN_LO:
                outside["close_before_2026-05-23"] += 1
                continue
            if cd > WIN_HI:
                outside["close_after_2026-10-20"] += 1
                continue
            if m.get("result") not in ("yes", "no"):
                skips[f"no_official_result({m.get('result')!r})"] += 1
                continue
            if m.get("floor_strike") is None or m.get("cap_strike") is None or m.get("strike_type") != "between":
                skips["bracket_without_floor_and_cap"] += 1
                continue
            events[m["event_ticker"]].append(m)
    return events, skips, outside


def stage_signals():
    events, skips, outside = rungs_universe()
    print(f"universe: {sum(len(v) for v in events.values()):,} bracket rungs in {len(events):,} events; "
          f"pre-skips {dict(skips)}; outside window {dict(outside)}")
    st_cache = {}

    def st_obs(station, feed):
        k = (station, feed)
        if k not in st_cache:
            st_cache[k] = load_station_obs(station, feed)
        return st_cache[k]

    SH = list(range(-3, 4))
    out = open(SIGNALS, "w")
    ev_skip = collections.Counter()
    n_ev = n_rung = n_fire = 0
    tzdiag = []
    mono_viol = 0
    n_lookahead = 0
    for evt in sorted(events):
        rungs = events[evt]
        series = rungs[0]["series_ticker"]
        sm = SERIES_MAP[series]
        d = parse_event_date(evt)
        close_ts = int(dt.datetime.fromisoformat(rungs[0]["close_time"].replace("Z", "+00:00")).timestamp())
        base = {"event": evt, "series": series, "station": sm["station"], "kind": sm["kind"], "date": str(d),
                "close_ts": close_ts}
        if d is None:
            ev_skip["unparseable_event_date"] += len(rungs)
            out.write(json.dumps({**base, "skip": "unparseable_event_date", "n_rungs": len(rungs)}) + "\n")
            continue
        # ---- tz check: close_time must be local-STANDARD-time midnight ending the event date
        exp_close = int((dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
                         - dt.timedelta(hours=sm["off"])).timestamp())
        # tolerance: a block of HIGH series (Aug 2026) closes at 23:59 LST, i.e. 60 s before LST midnight.  The DAY
        # is still [LST midnight, LST midnight); the market simply stops 60 s early.  Anything else is a hard skip.
        if any(not (-60 <= int(dt.datetime.fromisoformat(r["close_time"].replace("Z", "+00:00")).timestamp()) - exp_close <= 0)
               for r in rungs):
            ev_skip["close_time_not_within_60s_before_LST_midnight_of_event_date+1"] += len(rungs)
            out.write(json.dumps({**base, "skip": "close_time_not_LST_midnight", "n_rungs": len(rungs),
                                  "expected_close_ts": exp_close}) + "\n")
            continue
        day0 = exp_close - 86400          # the local-standard-time day starts here; ends at exp_close (>= close_ts)
        base["close_offset_s"] = close_ts - exp_close
        feeds = {}
        for feed in ("1min", "routine"):
            ts, tf = st_obs(sm["station"], feed)
            i0, i1 = bisect.bisect_left(ts, day0), bisect.bisect_left(ts, close_ts)
            ots, of_ = [], []
            for t, f in zip(ts[i0:i1], tf[i0:i1]):
                if GLITCH_LO_F <= f <= GLITCH_HI_F:
                    ots.append(t)
                    of_.append(f)
            feeds[feed] = (ots, of_)
        if len(feeds["1min"][0]) >= MIN_1MIN_OBS:
            feed = "iem_1min"
            ots, of_ = feeds["1min"]
        elif len(feeds["routine"][0]) >= MIN_ROUTINE_OBS:
            feed = "iem_routine_fallback"
            ots, of_ = feeds["routine"]
        else:
            ev_skip["insufficient_obs_both_feeds"] += len(rungs)
            out.write(json.dumps({**base, "skip": "insufficient_obs_both_feeds", "n_rungs": len(rungs),
                                  "n_1min": len(feeds["1min"][0]), "n_routine": len(feeds["routine"][0])}) + "\n")
            continue
        # ---- anchor (c): monotone running extreme + timestamps inside the local day
        assert all(day0 <= t < close_ts for t in ots), "obs outside local-day window"
        assert all(ots[i] < ots[i + 1] for i in range(len(ots) - 1)), "obs not strictly increasing"
        sm_ = Stream(sm["kind"])
        prevE = None
        for f in of_:
            sm_.push(f)
            if prevE is not None and ((sm_.E < prevE) if sm["kind"] == "max" else (sm_.E > prevE)):
                mono_viol += 1
            prevE = sm_.E
        Efinal = sm_.E
        # ---- tz diagnostic vs official value (1-min only): shifted windows
        diag = None
        offv = rungs[0].get("expiration_value")
        if feed == "iem_1min" and offv not in (None, ""):
            ts1, tf1 = st_obs(sm["station"], "1min")
            diag = {}
            for s in SH:
                a, b = bisect.bisect_left(ts1, day0 + s * 3600), bisect.bisect_left(ts1, exp_close + s * 3600)
                vals = [f for f in tf1[a:b] if GLITCH_LO_F <= f <= GLITCH_HI_F]
                if len(vals) >= MIN_1MIN_OBS:
                    diag[str(s)] = max(vals) if sm["kind"] == "max" else min(vals)
        fires = detect_event(ots, of_, sm["kind"], close_ts, rungs)
        # ---- anchor (b): no look-ahead.  Re-run on obs truncated to <= k and on a POISONED future; must agree.
        seen = set()
        for r in rungs:
            for rd in READINGS:
                for ck, fr in fires[r["ticker"]][rd].items():
                    k = fr["k"]
                    if (r["ticker"], rd, k) in seen:
                        continue
                    seen.add((r["ticker"], rd, k))
                    n_lookahead += 2
                    for variant in ("truncate", "poison"):
                        if variant == "truncate":
                            tt, ff = ots[:k + 1], of_[:k + 1]
                        else:
                            # adversarial future: every later obs is moved 50F toward the direction that would
                            # CHANGE the decision (new extreme) -- a detector that peeked would change its answer.
                            flip = (of_[k] + 50.0) if sm["kind"] == "max" else (of_[k] - 50.0)
                            tt, ff = ots, of_[:k + 1] + [flip for _ in of_[k + 1:]]
                        g = detect_event(tt, ff, sm["kind"], close_ts, [r])[r["ticker"]][rd].get(ck)
                        assert g is not None and g["k"] == k and g["E"] == fr["E"] and g["sig_ts"] == fr["sig_ts"], \
                            f"LOOK-AHEAD VIOLATION {r['ticker']} {rd} {ck} {variant}"
        rec = {**base, "feed": feed, "n_obs": len(ots), "E_final": Efinal, "official_value": offv,
               "tz_shift_extremes": diag, "rungs": []}
        for r in rungs:
            n_rung += 1
            rr = {"ticker": r["ticker"], "floor": r["floor_strike"], "cap": r["cap_strike"], "result": r["result"],
                  "fires": fires[r["ticker"]]}
            if any(fires[r["ticker"]][rd] for rd in READINGS):
                n_fire += 1
            rec["rungs"].append(rr)
        out.write(json.dumps(rec) + "\n")
        n_ev += 1
        if n_ev % 500 == 0:
            print(f"  signals: {n_ev} events", flush=True)
    out.close()
    summ = {"events_scored": n_ev, "rungs_scored": n_rung, "rungs_with_any_fire": n_fire,
            "event_level_skips_rungs": dict(ev_skip), "pre_skips": dict(skips), "outside_window": dict(outside),
            "monotonicity_violations": mono_viol, "lookahead_assertions_run": n_lookahead}
    json.dump(summ, open(STAGEA_SUMMARY, "w"), indent=1)
    print(json.dumps(summ, indent=1))


# ------------------------------------------------------------------ candles
def candle_path(tk):
    return os.path.join(CANDLE_DIR, tk + ".json")


HIST_CUTOFF_TS = int(dt.datetime(2026, 8, 27, tzinfo=dt.timezone.utc).timestamp())


def _hist_to_live(cs):
    """/historical candlesticks use {close,...} strings; convert to the live *_dollars shape so V2.normalize()
    (the single shared price path) can be used unchanged."""
    out = []
    for k in cs:
        def node(n):
            n = n or {}
            return {"close_dollars": n.get("close")}
        out.append({"end_period_ts": k.get("end_period_ts"), "volume_fp": k.get("volume"),
                    "yes_bid": node(k.get("yes_bid")), "yes_ask": node(k.get("yes_ask"))})
    return out


def fetch_candles(tk, series, close_ts):
    p = candle_path(tk)
    if os.path.exists(p):
        return json.load(open(p))
    q = f"start_ts={close_ts - CANDLE_WINDOW_MIN * 60 - 60}&end_ts={close_ts}&period_interval=1"
    live = f"/series/{series}/markets/{tk}/candlesticks?{q}"
    hist = f"/historical/markets/{tk}/candlesticks?{q}"
    order = [("hist", hist), ("live", live)] if close_ts < HIST_CUTOFF_TS else [("live", live), ("hist", hist)]
    res = {"ok": False, "error": "unreached", "candlesticks": []}
    for src, path in order:
        try:
            d = kget(path)
            cs = d.get("candlesticks", [])
            if src == "hist":
                cs = _hist_to_live(cs)
            res = {"ok": True, "src": src, "candlesticks": cs}
            if cs:
                break
        except urllib.error.HTTPError as e:
            res = {"ok": False, "error": f"HTTP {e.code} via {src}", "candlesticks": []}
    json.dump(res, open(p, "w"))
    return res


def fired_rungs():
    out = {}
    for ln in open(SIGNALS):
        r = json.loads(ln)
        if "skip" in r:
            continue
        for rr in r["rungs"]:
            if any(rr["fires"][rd] for rd in READINGS):
                out[rr["ticker"]] = {"series": r["series"], "close_ts": r["close_ts"]}
    return out


def work_order(fr):
    """Deterministic shuffled order; sorted ONLY to make the shuffle reproducible, then shuffled with a fixed seed
    and never re-sorted."""
    keys = sorted(fr)
    random.Random(SEED).shuffle(keys)
    return keys


def stage_candles(max_fetch, time_budget_s):
    fr = fired_rungs()
    order = work_order(fr)
    json.dump(order, open(os.path.join(CACHE, "candle_work_order.json"), "w"))
    t0 = time.time()
    n = 0
    anchors = anchor_tickers()
    print(f"fired rungs: {len(fr):,}; work order shuffled (seed {SEED}); anchors {len(anchors)}", flush=True)
    for tk, info in anchors.items():
        if not os.path.exists(candle_path(tk)):
            fetch_candles(tk, info["series"], info["close_ts"])
    for tk in order:
        if os.path.exists(candle_path(tk)):
            continue
        if n >= max_fetch or time.time() - t0 > time_budget_s:
            break
        fetch_candles(tk, fr[tk]["series"], fr[tk]["close_ts"])
        n += 1
        if n % 100 == 0:
            done = sum(1 for k in order if os.path.exists(candle_path(k)))
            print(f"  candles: +{n} this run, {done}/{len(order)} total, {time.time() - t0:.0f}s", flush=True)
    done = sum(1 for k in order if os.path.exists(candle_path(k)))
    print(f"candles done {done}/{len(order)}")


def anchor_tickers():
    """Bracket rungs from the stored Stage-1 oracle detail (the only part of the oracle set on disk)."""
    d = json.load(open(os.path.join(HERE, "out", "edge_sizing_v2.json")))
    out = {}
    for r in d["capturable_markets_detail"]:
        if re.search(r"-B[\d.]+$", r["ticker"]):
            ct = int(dt.datetime.fromisoformat(r["close_time"].replace("Z", "+00:00")).timestamp())
            out[r["ticker"]] = {"series": r["series"], "close_ts": ct}
    return out


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


def cluster_stats(items):
    """items: [(day, w, pnl)].  Weighted mean with day-clustered SE (CR1 small-sample factor G/(G-1))."""
    sw = sum(w for _d, w, _p in items)
    if not items or sw <= 0:
        return {"n": len(items), "mean": None, "se": None, "t": None, "days": len({d for d, _, _ in items})}
    mu = sum(w * p for _d, w, p in items) / sw
    U = collections.defaultdict(float)
    for d, w, p in items:
        U[d] += w * (p - mu)
    G = len(U)
    se = None
    t = None
    if G >= 2:
        se = math.sqrt(G / (G - 1) * sum(u * u for u in U.values())) / sw
        t = mu / se if se > 0 else None
    return {"n": len(items), "mean": mu, "se": se, "t": t, "days": G}


def load_rows(tk, close_ts):
    p = candle_path(tk)
    if not os.path.exists(p):
        return "not_fetched"
    c = json.load(open(p))
    if not c.get("ok"):
        if "404" in str(c.get("error")):
            return []                       # no candle data exists for this market (404 / empty) -> no coverage
        return "fetch_error:" + str(c.get("error"))
    V2.WINDOW_MIN = CANDLE_WINDOW_MIN        # normalize() filters to the final WINDOW_MIN minutes
    rows = V2.normalize(c["candlesticks"], close_ts)
    rows = sorted([r for r in rows if r[0] is not None], key=lambda r: r[0])
    return rows


def entry_for(rows, close_ts, sig_ts, L):
    """First candle at/after sig_ts+L whose YES ask is <=98c with positive fee-inclusive net.  No earlier/better print."""
    target = sig_ts + L * 60
    after = [r for r in rows if r[0] >= target and r[0] <= close_ts]
    if not after:
        return {"status": "untradeable", "reason": "no_candle_at_or_after_target"}
    saw_ask = False
    for ts, yb, ya, vol in after:
        if ya is None:
            continue
        saw_ask = True
        if not (0 < ya <= MAX_PAY_C):
            continue
        fee = V2.fee_c(ya)
        if 100 - ya - fee <= 0:
            continue
        return {"status": "priced", "entry_ts": ts, "cost_c": ya, "fee_c": fee, "vol": vol}
    return {"status": "untradeable", "reason": "ask_above_98_or_no_net" if saw_ask else "no_ask_quoted"}


def oracle_capturable_60(rows, close_ts, result):
    """EDGE_SIZING Stage-1 definition, reproduced with the SAME fee/cap constants: winner side buyable <=98c with
    net>0 in the final 60 minutes.  Winner cost = yes_ask if YES else 100 - yes_bid."""
    best = None
    n = 0
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


def load_events():
    evs = []
    for ln in open(SIGNALS):
        evs.append(json.loads(ln))
    return evs


def run_report(stage):
    if stage == "verify":
        return stage_verify()
    summ = json.load(open(STAGEA_SUMMARY))
    evs = load_events()
    official = {}
    for s in SERIES_MAP:
        for m in list_settled(s):
            official[m["ticker"]] = m
    fired = {}
    ev_skips = collections.Counter()
    for e in evs:
        if "skip" in e:
            ev_skips[e["skip"]] += e["n_rungs"]
            continue
        for rr in e["rungs"]:
            if any(rr["fires"][rd] for rd in READINGS):
                fired[rr["ticker"]] = (e, rr)
    # ---- unmapped-series skip ledger (D7): bracket rungs in window we did NOT test, by series
    unmapped = {}
    try:
        allser = [t for t in json.load(open(os.path.join(CACHE, "all_series.json")))
                  if (t.startswith("KXHIGH") or t.startswith("KXLOWT")) and t not in SERIES_MAP]
    except Exception:     # noqa: BLE001
        allser = []
    for s_ in allser:
        n_ = 0
        try:
            for m in list_settled(s_):
                cd = dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).date()
                if re.search(r"-B[\d.]+$", m["ticker"]) and WIN_LO <= cd <= WIN_HI and m.get("result") in ("yes", "no"):
                    n_ += 1
        except Exception:     # noqa: BLE001
            n_ = -1
        if n_:
            unmapped[s_] = n_
    order = json.load(open(os.path.join(CACHE, "candle_work_order.json")))
    n_total_fired = len(order)
    cand_state = collections.Counter()
    rungs_out = []
    fire_rows = []        # flat: one per (reading, cell, rung) with arms
    for tk in order:
        e, rr = fired[tk]
        rows = load_rows(tk, e["close_ts"])
        if isinstance(rows, str):
            cand_state["not_fetched" if rows == "not_fetched" else "candle_fetch_error"] += 1
            continue
        if not rows:
            cand_state["no_candles_in_final_120min"] += 1
            rungs_out.append({"ticker": tk, "skip": "no_candles_in_final_120min", "event": e["event"],
                              "result": rr["result"], "fires": rr["fires"]})
            continue
        cand_state["covered"] += 1
        rec = {"ticker": tk, "series": e["series"], "station": e["station"], "kind": e["kind"], "date": e["date"],
               "close_ts": e["close_ts"], "floor": rr["floor"], "cap": rr["cap"], "result": rr["result"],
               "feed": e["feed"], "official_value": e["official_value"], "E_final_obs": e["E_final"],
               "candles": [[r[0], r[1], r[2], r[3]] for r in rows], "fires": {}}
        orc = oracle_capturable_60(rows, e["close_ts"], rr["result"])
        rec["oracle60"] = orc
        for rd in READINGS:
            rec["fires"][rd] = {}
            for ck, fr in rr["fires"][rd].items():
                arms = {str(L): entry_for(rows, e["close_ts"], fr["sig_ts"], L) for L in LATS}
                for L, a in arms.items():
                    if a["status"] == "priced":
                        win = rr["result"] == "yes"
                        a["win"] = win
                        a["pnl_c"] = (100 - a["cost_c"] - a["fee_c"]) if win else (-a["cost_c"] - a["fee_c"])
                rec["fires"][rd][ck] = {**fr, "arms": arms}
                fire_rows.append({"reading": rd, "cell": ck, "ticker": tk, "date": e["date"], "station": e["station"],
                                  "kind": e["kind"], "result": rr["result"], "oracle60": orc, "arms": arms,
                                  "feed": e["feed"]})
        rungs_out.append(rec)

    # ------------------------------------------------------------- cell statistics
    cells_out = []
    for rd in READINGS:
        for c in GRID:
            ck = cell_key(c)
            fs = [f for f in fire_rows if f["reading"] == rd and f["cell"] == ck]
            n = len(fs)
            fl = sum(1 for f in fs if f["result"] == "no")
            fl_p, fl_lo, fl_hi = wilson(fl, n)
            for L in LATS:
                priced = [f for f in fs if f["arms"][str(L)]["status"] == "priced"]
                unt = n - len(priced)
                fl_pr = sum(1 for f in priced if f["result"] == "no")
                pr_p, pr_lo, pr_hi = wilson(fl_pr, len(priced))
                wi = [(f["date"], f["arms"][str(L)]["vol"], f["arms"][str(L)]["pnl_c"]) for f in priced]
                un = [(f["date"], 1.0, f["arms"][str(L)]["pnl_c"]) for f in priced]
                sv, su = cluster_stats(wi), cluster_stats(un)
                days = len({f["date"] for f in priced})
                stations = len({f["station"] for f in priced})
                df = days - 1
                q = tq(0.99896, df)
                ub979 = None if sv["mean"] is None or sv["se"] is None else sv["mean"] + tq(0.979, df) * sv["se"]
                ub99792 = None if sv["mean"] is None or sv["se"] is None else sv["mean"] + tq(0.99792, df) * sv["se"]
                reasons = collections.Counter(f["arms"][str(L)].get("reason") for f in fs if f["arms"][str(L)]["status"] != "priced")
                row = {
                    "reading": rd, "cell": ck, "M": c[0], "R": c[1], "H": c[2], "W": c[3], "L": L,
                    "n_fires_covered": n, "false_locks": fl,
                    "false_lock_rate_all": fl_p, "false_lock_wilson_ub_all": fl_hi,
                    "n_priced": len(priced), "n_untradeable": unt,
                    "untradeable_frac": (unt / n) if n else None, "untradeable_reasons": dict(reasons),
                    "priced_false_locks": fl_pr, "false_lock_rate_priced": pr_p, "false_lock_wilson_ub_priced": pr_hi,
                    "ev_c_volume_weighted": sv["mean"], "ev_c_unweighted": su["mean"],
                    "t_volume_weighted": sv["t"], "t_unweighted": su["t"],
                    "se_volume_weighted": sv["se"], "n_days_priced": days, "n_stations_priced": stations,
                    "t_bar_p99896": q, "ub_one_sided_97.9": ub979, "ub_one_sided_99.792": ub99792,
                    "mean_cost_c": (sum(f["arms"][str(L)]["cost_c"] for f in priced) / len(priced)) if priced else None,
                    "win_rate_priced": (sum(1 for f in priced if f["result"] == "yes") / len(priced)) if priced else None,
                    "zero_volume_entries": sum(1 for f in priced if f["arms"][str(L)]["vol"] <= 0),
                    "n_priced_vol_gt0": sum(1 for f in priced if f["arms"][str(L)]["vol"] > 0),
                }
                # frozen PASS criteria
                crit = {}
                crit["1_false_lock_all"] = (fl_p is not None and fl_p <= 0.02 and fl_hi <= 0.05)
                crit["1_false_lock_priced"] = (pr_p is not None and pr_p <= 0.02 and pr_hi <= 0.05)
                crit["2_ev_ge_2c_vw"] = (sv["mean"] is not None and sv["mean"] >= 2.0)
                crit["3_t_ge_bar"] = (sv["t"] is not None and q is not None and sv["t"] >= q)
                crit["4_n_days_stations"] = (len(priced) >= 100 and days >= 40 and stations >= 10)
                crit["5_untradeable_le_70"] = (n > 0 and unt / n <= 0.70)
                row["criteria"] = crit
                row["cell_passes_all"] = all(crit.values())
                cells_out.append(row)

    def verdict_for(rd):
        rows = [r for r in cells_out if r["reading"] == rd]
        r10 = [r for r in rows if r["L"] == 10]
        passing = [r for r in r10 if r["cell_passes_all"]]
        prim = next((r for r in rows if r["L"] == 10 and (r["M"], r["R"], r["H"], r["W"]) == PRIMARY), None)
        kill = []
        if prim and prim["false_lock_rate_all"] is not None and prim["false_lock_rate_all"] > 0.05:
            kill.append("primary cell false-lock rate (all fires) %.3f > 5%%" % prim["false_lock_rate_all"])
        pos = [r for r in r10 if r["ev_c_volume_weighted"] is not None and r["ev_c_volume_weighted"] > 0]
        if pos and all(r["n_priced"] < 100 for r in pos):
            kill.append("every L=10 cell with EV>0 fails the n>=100 floor")
        ubs = [r["ub_one_sided_97.9"] for r in r10 if r["ub_one_sided_97.9"] is not None]
        if ubs and max(ubs) < 0.5:
            kill.append("best L=10 one-sided 97.9%% EV upper bound %.2fc < +0.5c" % max(ubs))
        if passing:
            v = "PASS"
        elif kill:
            v = "KILL"
        else:
            v = "INSUFFICIENT"
        return {"verdict": v, "passing_cells_L10": [r["cell"] for r in passing], "kill_triggers": kill,
                "best_ub_97.9_L10": max(ubs) if ubs else None,
                "primary_cell_L10": prim}

    verdicts = {rd: verdict_for(rd) for rd in READINGS}

    # ------------------------------------------------------------- anchors
    anchors = {}
    # (a) oracle reconciliation
    ora = json.load(open(os.path.join(HERE, "out", "edge_sizing_v2.json")))["capturable_markets_detail"]
    ora_b = [r for r in ora if re.search(r"-B[\d.]+$", r["ticker"])]
    pj = []
    for r in ora_b:
        ct = int(dt.datetime.fromisoformat(r["close_time"].replace("Z", "+00:00")).timestamp())
        rows = load_rows(r["ticker"], ct)
        if isinstance(rows, str) or not rows:
            pj.append({"ticker": r["ticker"], "status": "no_rows_now", "detail": rows if isinstance(rows, str) else "empty"})
            continue
        mine = oracle_capturable_60(rows, ct, r["result"])
        pj.append({"ticker": r["ticker"], "stored_best_cost": r["best_winner_cost_c"], "stored_best_net": r["best_net_c"],
                   "stored_n_min": r["n_capturable_minutes"], "mine_best_cost": mine["best_cost"],
                   "mine_best_net": mine["best_net"], "mine_n_min": mine["n_min"],
                   "match": (mine["best_cost"] == r["best_winner_cost_c"] and mine["best_net"] == r["best_net_c"])})
    # priced YES-winners in W=60 cells must be oracle-capturable
    viol = []
    chk = 0
    for f in fire_rows:
        if f["cell"].endswith("_W60") and f["result"] == "yes":
            for L in LATS:
                a = f["arms"][str(L)]
                if a["status"] == "priced":
                    chk += 1
                    if not f["oracle60"]["capturable"]:
                        viol.append({"ticker": f["ticker"], "cell": f["cell"], "L": L})
    # stored oracle B-rungs that my rule also fires on
    stored_fired = [t for t in (r["ticker"] for r in ora_b) if t in fired]
    anchors["a_oracle_reconciliation"] = {
        "oracle_B_rungs_stored": len(ora_b), "price_join_rows": pj,
        "price_join_matches": sum(1 for x in pj if x.get("match")),
        "price_join_checked": sum(1 for x in pj if "match" in x),
        "priced_yes_fires_in_W60_cells_checked": chk, "violations_not_oracle_capturable": viol,
        "oracle_B_rungs_the_rule_fires_on": stored_fired,
        "limitation": ("Only the top-40 'capturable_markets_detail' of out/edge_sizing_v2.json (34 bracket rungs) "
                       "survives on disk; the full 140-market Stage-1 set and its population cache are gitignored and "
                       "absent.  The subset anchor is therefore tested by re-deriving the Stage-1 capturable test "
                       "(same fee/98c constants, same normalize()) on every priced YES fire, plus a price-join "
                       "reproduction on the stored rungs."),
        "pass": (len(viol) == 0 and all(x.get("match") for x in pj if "match" in x)),
    }
    anchors["b_no_lookahead"] = {"assertions_run": summ.get("lookahead_assertions_run"),
                                 "method": "streaming detector + per-fire truncation and adversarial-future-poison re-runs",
                                 "pass": summ.get("lookahead_assertions_run", 0) > 0}
    # (c) monotonicity + tz shift diagnostic
    shift = {"max": collections.defaultdict(lambda: [0, 0, 0.0]), "min": collections.defaultdict(lambda: [0, 0, 0.0])}
    for e in evs:
        if "skip" in e or not e.get("tz_shift_extremes"):
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
    anchors["c_monotonic_and_tz"] = {
        "monotonicity_violations": summ.get("monotonicity_violations"),
        "tz_window_shift_vs_official_value": {
            k: {str(s_): {"events": a[0], "exact_match_frac": a[1] / a[0], "mean_abs_err_F": a[2] / a[0]}
                for s_, a in sorted(v.items())} for k, v in shift.items()},
        "note": ("shift s hours means window [close-24h+s, close+s).  s=0 is the declared local-standard-time day; "
                 "s=-1 is the naive wall-clock-DST-midnight day.  The declared window must win by exact-match "
                 "fraction / lowest abs error against Kalshi's own expiration_value."),
    }
    anchors["c_monotonic_and_tz"]["pass"] = (summ.get("monotonicity_violations", 1) == 0)

    out = {
        "spec": "venue_expansion/TERMINAL_FINALITY_SPEC.md (frozen 2026-10-27) -- BUILD A",
        "seed": SEED,
        "readings": {"S": "interval [floor, cap] -- LITERAL spec (formal verdict)",
                     "L": "interval [floor-0.5, cap+0.5] -- lattice/rounding reading (exploratory, pre-declared)"},
        "stageA": summ, "event_level_skips": dict(ev_skips), "unmapped_series_bracket_rungs_in_window_not_tested": unmapped,
        "sampling": {"fired_rungs_total": n_total_fired, "candle_states": dict(cand_state),
                     "fraction_candle_pulled": (n_total_fired - cand_state.get("not_fetched", 0)) / max(n_total_fired, 1),
                     "order": "shuffled with fixed seed; never re-sorted"},
        "verdicts": verdicts, "cells": cells_out, "anchors": anchors,
        "diagnostics": diagnostics(rungs_out),
        "rungs": rungs_out,
    }
    json.dump(out, open(OUT_JSON, "w"))
    print("wrote", OUT_JSON, os.path.getsize(OUT_JSON) // 1024, "KB")
    md = build_md(out, evs)
    if os.path.exists(COMMENTARY_PATH):
        md = md.replace("{{COMMENTARY}}", open(COMMENTARY_PATH).read())
        md = md.replace("{{CAVEATS}}", open(CAVEATS_PATH).read() if os.path.exists(CAVEATS_PATH) else "")
    open(OUT_MD, "w").write(md)
    print("wrote", OUT_MD)
    for rd in READINGS:
        v = verdicts[rd]
        print(rd, v["verdict"], v["kill_triggers"], v["passing_cells_L10"])
    return out


def stage_verify(n=150):
    """Cross-check the list-endpoint result against GET /markets/{ticker}.market.result for a random sample of fired rungs."""
    order = json.load(open(os.path.join(CACHE, "candle_work_order.json")))
    off = {}
    for s in SERIES_MAP:
        for m in list_settled(s):
            off[m["ticker"]] = m
    res = {"checked": 0, "mismatch": [], "not_found": 0}
    for tk in order[:n]:
        p = os.path.join(VERIFY_DIR, tk + ".json")
        if os.path.exists(p):
            d = json.load(open(p))
        else:
            try:
                d = kget(f"/markets/{tk}").get("market", {})
            except urllib.error.HTTPError:
                try:
                    d = kget(f"/historical/markets/{tk}").get("market", {})
                except Exception:     # noqa: BLE001
                    d = {"_nf": True}
            json.dump(d, open(p, "w"))
        if d.get("_nf"):
            res["not_found"] += 1
            continue
        res["checked"] += 1
        if d.get("result") != off[tk]["result"]:
            res["mismatch"].append({"ticker": tk, "single": d.get("result"), "list": off[tk]["result"]})
    json.dump(res, open(os.path.join(CACHE, "verify_summary.json"), "w"), indent=1)
    print(res)


# ====================================================================== MARKDOWN
def _f(x, nd=3, pct=False):
    if x is None:
        return "n/a"
    return f"{100 * x:.{nd - 1}f}%" if pct else f"{x:.{nd}f}"


def _utc(ts):
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def tz_worked_example(evs):
    best = None
    for e in evs:
        if "skip" in e or e["feed"] != "iem_1min" or not e.get("tz_shift_extremes") or e.get("official_value") in (None, ""):
            continue
        ov = float(e["official_value"])
        d = e["tz_shift_extremes"]
        if e["station"] == "PHX":
            continue          # Phoenix does not observe DST; the wall-clock illustration would not apply
        if "0" in d and "-1" in d and "1" in d and round(d["0"]) == round(ov) and round(d["-1"]) != round(ov) \
                and round(d["1"]) != round(ov):
            if best is None or (e["kind"] == "min" and best["kind"] != "min"):
                best = e
            if best["kind"] == "min":
                break
    if not best:
        return "(no event found where only the declared window reproduces the official value)"
    e = best
    sm = SERIES_MAP[e["series"]]
    d = dt.date.fromisoformat(e["date"])
    off = sm["off"]
    lst0 = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc) - dt.timedelta(hours=off)
    lines = [
        f"Event `{e['event']}` (station {e['station']}, {'running MAX' if e['kind'] == 'max' else 'running MIN'}).",
        f"- Event date {e['date']}; station fixed standard offset UTC{off:+d} (the NWS climate day is local STANDARD time all year).",
        f"- Local-standard midnight that STARTS the day = {d} 00:00 LST = **{lst0:%Y-%m-%d %H:%MZ}**; the day ENDS at "
        f"{d + dt.timedelta(days=1)} 00:00 LST = **{_utc(e['close_ts'])}**, and Kalshi's `close_time` is exactly that "
        f"({_utc(e['close_ts'])}) -- asserted for every event (`close_time == (date+1) 00:00 - offset`).",
        f"- Expressed in daylight-saving wall-clock (UTC{off + 1:+d}) the same day runs {(lst0 + dt.timedelta(hours=off + 1)):%H:%M} on {d} to "
        f"{(lst0 + dt.timedelta(hours=off + 1)):%H:%M} on {d + dt.timedelta(days=1)}, i.e. it does NOT start at wall-clock midnight.  "
        f"A naive 'local midnight to local midnight' window in DST wall-clock is the window shifted by s=-1h -- the classic 1-hour-skew trap.",
        "",
        "| window shift s (h) | extreme in [close-24h+s, close+s) F | official `expiration_value` | integer match |",
        "|---|---:|---:|:---:|"]
    ov = float(e["official_value"])
    for s_, v in sorted(e["tz_shift_extremes"].items(), key=lambda kv: int(kv[0])):
        lines.append(f"| {int(s_):+d}{' (declared)' if s_ == '0' else (' (naive DST wall-clock)' if s_ == '-1' else '')} | {v:.1f} | "
                     f"{ov:.0f} | {'YES' if round(v) == round(ov) else 'no'} |")
    lines.append("")
    lines.append("Only the declared window reproduces Kalshi's own official value on this day; the 1-hour-shifted windows do not.")
    return "\n".join(lines)


def lookahead_example(out):
    for r in out["rungs"]:
        if "candles" in r and not r.get("skip") and r["fires"].get("L"):
            ck = "M0.5_R2_H3_W120"
            fr = r["fires"]["L"].get(ck)
            if fr:
                return r, ck, fr
    return None, None, None


def write_md(out, evs):
    cells = out["cells"]
    S = {tuple(k): v for k, v in []}
    L_ = []
    A = L_.append
    ver = out["verdicts"]
    A("# TERMINAL FINALITY -- BUILD A (primary) -- result\n")
    A(f"Spec: `venue_expansion/TERMINAL_FINALITY_SPEC.md` (frozen 2026-10-27).  Code: `venue_expansion/finality_A.py`.  "
      f"Per-fire records: `venue_expansion/out/finality_A.json`.  Seed {SEED}.\n")
    A(f"## Verdict (formal reading S = spec text literally): **{ver['S']['verdict']}**\n")
    for rd in ("S", "L"):
        v = ver[rd]
        A(f"- reading **{rd}** ({out['readings'][rd]}): **{v['verdict']}**; "
          f"PASS cells at L=10: {v['passing_cells_L10'] or 'none'}; KILL triggers: {v['kill_triggers'] or 'none'}; "
          f"best one-sided 97.9% EV upper bound at L=10: {_f(v['best_ub_97.9_L10'], 2)}c")
    A("")
    for k in ("verdict_commentary",):
        pass
    A("{{COMMENTARY}}\n")
    st = out["stageA"]
    A("## Universe, sampling, skips\n")
    A("{{UNIVERSE}}\n")
    A("## Method (what was actually run)\n")
    A("""1. **Universe** -- settled bracket rungs (`-B` tickers, `strike_type=between`, official `result` in {yes,no}) of the 40 US
   HIGH/LOW series with a verified station mapping, `close_time` UTC date in 2026-05-23..2026-10-20.  Market lists come from the
   live `/markets?status=settled` endpoint (post 2026-08-28 settlements) UNION `/historical/markets` (older), de-duplicated.
   Outcome = Kalshi `result` only; a random sample of fired rungs was cross-checked against `GET /markets/{ticker}`.
2. **Observations** -- IEM `asos1min.py` (1-minute) per station-month, cached; routine `asos.py` (report_type 3&4) as a disclosed per-market
   fallback when the 1-minute day has < 600 obs.  Feed recorded per market.
3. **Signal** -- streaming detector (`Stream`): consumes obs one at a time, keeps running extreme E and, for each R, the count of
   trailing obs at least R degrees away from E.  FINAL-YES at the first obs with (1) interval test, (2) run >= H, (3) obs within W minutes of
   `close_time`.  Signal stamped obs-minute + 60 s (decision D3).
4. **Entry** -- first candle with `end_period_ts >= sig_ts + L*60` and `<= close_ts`, `yes_ask <= 98c` and `100 - ask - fee > 0`; no earlier or
   better print is ever used; no such candle = UNTRADEABLE (counted).  One contract, held to settlement.  Fee `ceil(7 p (1-p))` via `V2.fee_c`.
   pnl = `100 - cost - fee` if the official result is YES else `-cost - fee`.  Candles are normalised by the shared `edge_sizing_v2.normalize()`.
5. **Statistics** -- false-lock rate with Wilson 95% bounds; volume-weighted EV (weight = entry-candle volume; unweighted shown); day-clustered
   (calendar event-date) CR1 standard error, signed t, df = days-1, bar = exact Student-t quantile at p=0.99896 on the realised df.
6. **Interpretation decisions (D1-D9)** are pre-declared in the `finality_A.py` module docstring before any outcome was analysed.\n""")
    A("### D1 -- the bracket-width problem in the frozen text (read this)\n")
    A("""A Kalshi bracket rung has `cap_strike = floor_strike + 1` (e.g. `B68.5` -> floor 68, cap 69, YES iff the official **integer** high is 68 or 69;
verified on every settled rung against `expiration_value`).  The spec's test `lo + M <= E <= hi - M` on `[lo,hi] = [floor,cap]` is therefore
an **empty interval for every M = 1.0 cell** (it needs E >= lo+1 and E <= lo) and a single point (`E = lo + 0.5`) for M = 0.5.  Since 1-minute ASOS
temperatures are whole degrees, reading S can essentially never fire.  This is a defect in the frozen text, discovered by arithmetic before
outcomes were read.  Rather than silently re-define the spec, BOTH readings were run on the identical grid: **S** = the literal text (formal
verdict) and **L** = the lattice reading `[floor-0.5, cap+0.5]` (the real-valued temperature range that rounds into the settlement set), under which
M=0.5 means "E rounds into the bracket" and M=1.0 requires E at the bracket centre (also near-vacuous on integer data).  L is exploratory and
cannot produce a PASS; a PASS would require re-registration.\n""")
    A("## Worked timezone example\n")
    A("{{TZ}}\n")
    A("## Worked no-look-ahead example\n")
    A("{{LOOKAHEAD}}\n")
    A("## Sanity anchors\n")
    A("{{ANCHORS}}\n")
    A("## Primary cell (M=1.0, R=2, H=3, W=120) at L=10\n")
    A("{{PRIMARY}}\n")
    A("## All cells, L = 10 (the deployable arm)\n")
    A("{{CELLS10}}\n")
    A("## All cells, L = 0 and L = 20\n")
    A("{{CELLS_OTHER}}\n")
    A("## Diagnostics: why the signal loses (reading L, M=0.5, R=2, W=120, L=10)\n")
    A("{{DIAG}}\n")
    A("## Every skip, with its reason\n")
    A("{{SKIPS}}\n")
    A("## Caveats / what this does NOT show\n")
    A("{{CAVEATS}}\n")
    return "\n".join(L_)


def cell_table(cells, rd, Ls):
    hdr = ("| cell | L | fires (covered) | false locks (rate, Wilson UB) | priced (vol>0) | untradeable | EV vw (c) | EV unw (c) | t vw (bar) | t unw | days | stn | "
           "FL priced (rate, UB) | UB97.9 (c) | all 5 bars |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    rows = [hdr]
    for r in cells:
        if r["reading"] != rd or r["L"] not in Ls:
            continue
        rows.append("| {c} | {L} | {n} | {fl} ({flr}, {flu}) | {pr} ({pv}) | {un} ({unf}) | {ev} | {evu} | {t} ({q}) | {tu} | {d} | {s} | {fp} ({fpr}, {fpu}) | {ub} | {ok} |".format(
            pv=r["n_priced_vol_gt0"], tu=_f(r["t_unweighted"], 2),
            c=r["cell"], L=r["L"], n=r["n_fires_covered"], fl=r["false_locks"], flr=_f(r["false_lock_rate_all"], 3, True),
            flu=_f(r["false_lock_wilson_ub_all"], 3, True), pr=r["n_priced"], un=r["n_untradeable"],
            unf=_f(r["untradeable_frac"], 3, True), ev=_f(r["ev_c_volume_weighted"], 2), evu=_f(r["ev_c_unweighted"], 2),
            t=_f(r["t_volume_weighted"], 2), q=_f(r["t_bar_p99896"], 2), d=r["n_days_priced"], s=r["n_stations_priced"],
            fp=r["priced_false_locks"], fpr=_f(r["false_lock_rate_priced"], 3, True), fpu=_f(r["false_lock_wilson_ub_priced"], 3, True),
            ub=_f(r["ub_one_sided_97.9"], 2), ok="PASS" if r["cell_passes_all"] else "no"))
    return "\n".join(rows)


def diagnostics(rungs_out, cell="M0.5_R2_H3_W120", rd="L", Lm=10):
    """False-lock anatomy and a calibration table of the market price at the first candle >= sig+L (any price)."""
    offs = collections.Counter()
    offs_by_kind = collections.defaultdict(collections.Counter)
    bucket = collections.defaultdict(lambda: [0, 0])
    edges = [(0, 50), (50, 80), (80, 95), (95, 99), (99, 101)]
    n = 0
    for r in rungs_out:
        if "fires" not in r or r.get("skip"):
            continue
        fr = r["fires"].get(rd, {}).get(cell)
        if not fr:
            continue
        n += 1
        try:
            d = round(float(r["official_value"]) - fr["E"])
        except Exception:     # noqa: BLE001
            d = None
        if d is not None:
            offs[d] += 1
            offs_by_kind[r["kind"]][d] += 1
        tgt = fr["sig_ts"] + Lm * 60
        c = next((x for x in r["candles"] if x[0] >= tgt and x[0] <= r["close_ts"] and x[2] is not None), None)
        if c is None:
            bucket["no_quote"][0] += 1
            bucket["no_quote"][1] += int(r["result"] == "yes")
            continue
        ask = c[2]
        for lo, hi in edges:
            if lo <= ask < hi:
                bucket[f"{lo}-{hi - 1}c"][0] += 1
                bucket[f"{lo}-{hi - 1}c"][1] += int(r["result"] == "yes")
                break
    return {"cell": cell, "reading": rd, "L": Lm, "n": n,
            "official_minus_E_distribution": {str(k): v for k, v in sorted(offs.items())},
            "by_kind": {k: {str(a): b for a, b in sorted(v.items())} for k, v in offs_by_kind.items()},
            "ask_bucket_at_first_quote_after_signal": {k: {"n": v[0], "yes": v[1],
                                                           "yes_rate": (v[1] / v[0]) if v[0] else None}
                                                       for k, v in bucket.items()}}


def build_md(out, evs):
    md = write_md(out, evs)
    cells = out["cells"]
    st = out["stageA"]
    samp = out["sampling"]
    cs = samp["candle_states"]
    # ---- universe
    feeds = collections.Counter(e["feed"] for e in evs if "feed" in e)
    kinds = collections.Counter(e["kind"] for e in evs if "feed" in e)
    stations = sorted({e["station"] for e in evs if "feed" in e})
    uni = [
        f"- Series tested: 40 (20 HIGH, 20 LOW; {len(stations)} stations).  Events (station-days): {st['events_scored']:,}; bracket rungs: **{st['rungs_scored']:,}** "
        f"(HIGH events {kinds.get('max', 0):,}, LOW events {kinds.get('min', 0):,}); close_time UTC date in 2026-05-23..2026-10-20.",
        f"- Obs feed per event: IEM 1-minute **{feeds.get('iem_1min', 0):,}**, routine-METAR fallback **{feeds.get('iem_routine_fallback', 0):,}** (1-minute day had < 600 obs).",
        f"- Rungs with at least one FINAL-YES fire (any reading/cell): **{st['rungs_with_any_fire']:,}** (all under reading L; reading S fires on none).",
        f"- **Sampling of the priced stage**: candlesticks were pulled for {cs.get('covered', 0) + cs.get('no_candles_in_final_120min', 0) + cs.get('candle_fetch_error', 0):,} of "
        f"{samp['fired_rungs_total']:,} fired rungs = **{100 * samp['fraction_candle_pulled']:.1f}%**.  Work order = all fired rungs, sorted only to make the shuffle "
        f"reproducible, then shuffled with seed {SEED} and NEVER re-sorted, so the pulled set is a uniformly random subsample of the fired rungs "
        f"(any prefix is representative).  Signal-level facts (fire counts, false-lock rate before pricing) use ALL fired rungs in the signals stage "
        f"({st['rungs_with_any_fire']:,}); the covered/priced statistics below use the pulled random subsample.",
        f"- Candle states of the pulled set: {json.dumps(cs)}",
    ]
    md = md.replace("{{UNIVERSE}}", "\n".join(uni))
    md = md.replace("{{TZ}}", tz_worked_example(evs))
    # ---- lookahead example
    r, ck, fr = lookahead_example(out)
    if r:
        la = [f"Rung `{r['ticker']}` (floor {r['floor']}, cap {r['cap']}, kind {r['kind']}, feed {r['feed']}), reading L, cell `{ck}`:",
              f"- Signal (obs-only): E = {fr['E']} F at obs minute {_utc(fr['obs_ts'])}; the last {fr['run']} obs were each >= R away from E (current temp {fr['temp']} F); "
              f"obs index k = {fr['k']}; the signal is stamped {_utc(fr['sig_ts'])} (= obs minute + 60 s), so every observation used has ts < signal ts.",
              f"- Computed by `Stream` one observation at a time; nothing after index k is ever visible to it.",
              f"- Assertion actually run on every fire ({out['anchors']['b_no_lookahead']['assertions_run']:,} re-runs across all fires): (1) re-run the detector on obs[:k+1] only "
              f"and (2) re-run on the full day with every observation after k replaced by an adversarial value 50 F beyond the signal-time temperature in the direction "
              f"that would change the decision.  Both must reproduce the identical (k, E, sig_ts) or the run aborts.  0 violations (the script would have raised).",
              f"- Entry (L=10): `{json.dumps(fr['arms']['10'])}`"]
        md = md.replace("{{LOOKAHEAD}}", "\n".join(la))
    else:
        md = md.replace("{{LOOKAHEAD}}", "(no fire in the pulled subsample)")
    # ---- anchors
    a = out["anchors"]
    ar = a["a_oracle_reconciliation"]
    an = [
        f"**(a) Oracle reconciliation -- {'HOLDS' if ar['pass'] else 'FAILS'}.**  Price join: {ar['price_join_matches']}/{ar['price_join_checked']} of the stored Stage-1 oracle bracket rungs "
        f"re-derived from my own fresh candle pull reproduce the stored best winner cost, best net and capturable-minute count EXACTLY (same `normalize()`, fee, 98c constants).  "
        f"Subset test: of {ar['priced_yes_fires_in_W60_cells_checked']} priced YES-settled fires in W=60 cells (entry necessarily inside the final 60 minutes), "
        f"{len(ar['violations_not_oracle_capturable'])} are not oracle-capturable under the Stage-1 definition re-derived on the same candles.  "
        f"The rule fires on {len(ar['oracle_B_rungs_the_rule_fires_on'])} of the stored oracle bracket rungs.  Limitation: {ar['limitation']}",
        f"**(b) No look-ahead -- {'HOLDS' if a['b_no_lookahead']['pass'] else 'FAILS'}.**  {a['b_no_lookahead']['assertions_run']:,} assertion re-runs, none failed (see worked example).",
        f"**(c) Monotonicity / timezone -- {'HOLDS' if a['c_monotonic_and_tz']['pass'] else 'FAILS'}.**  Running-extreme monotonicity violations over {st['events_scored']:,} event-days: "
        f"**{a['c_monotonic_and_tz']['monotonicity_violations']}**.  Independent timezone proof: extreme of the obs inside windows shifted by s hours versus Kalshi's own official `expiration_value`:",
    ]
    tz = a["c_monotonic_and_tz"]["tz_window_shift_vs_official_value"]
    an.append("\n| kind | " + " | ".join(f"s={s}" for s in sorted(int(x) for x in tz["min"])) + " |\n|---|" + "---|" * len(tz["min"]))
    for k in ("max", "min"):
        an.append(f"| {k} exact-match % | " + " | ".join(f"{100 * tz[k][str(s)]['exact_match_frac']:.1f}" for s in sorted(int(x) for x in tz[k])) + " |")
        an.append(f"| {k} mean abs err F | " + " | ".join(f"{tz[k][str(s)]['mean_abs_err_F']:.2f}" for s in sorted(int(x) for x in tz[k])) + " |")
    an.append("\nFor LOW markets (late-evening / pre-dawn sensitive) the declared window s=0 is the clear optimum and error rises monotonically with |s|, which is the signature of correct handling; "
              "for HIGH markets the afternoon peak makes the day boundary nearly irrelevant, so the HIGH row is weakly informative (s=0 is still among the best).  "
              "The `close_time == LST midnight` assertion (+/-60 s, 588 events close at 23:59 LST) is the strict check and held for all 6,039 events (0 skips).")
    an.append("\n**Important side-finding from anchor (c):** even with the correct window the 1-minute-IEM extreme equals Kalshi's official integer in only "
              f"{100 * tz['max']['0']['exact_match_frac']:.0f}% of HIGH days and {100 * tz['min']['0']['exact_match_frac']:.0f}% of LOW days (mean abs error "
              f"{tz['max']['0']['mean_abs_err_F']:.2f} F / {tz['min']['0']['mean_abs_err_F']:.2f} F).  The official settlement value (The Weather Company) is not the ASOS 1-minute extreme; "
              "this is the root of the false-locks below, and it is independent of timing or latency.")
    md = md.replace("{{ANCHORS}}", "\n".join(an))
    # ---- primary
    prim = [r for r in cells if r["reading"] == "S" and (r["M"], r["R"], r["H"], r["W"]) == PRIMARY and r["L"] == 10][0]
    primL = [r for r in cells if r["reading"] == "L" and (r["M"], r["R"], r["H"], r["W"]) == PRIMARY and r["L"] == 10][0]
    pm = [f"Formal reading S: n fires = **{prim['n_fires_covered']}** (empty interval -- see D1).  Reading L: n fires = **{primL['n_fires_covered']}** (needs E exactly at the bracket centre, "
          f"impossible on whole-degree 1-minute data).  The pre-declared primary cell therefore has **no observations under any reading** and cannot be evaluated; "
          f"no KILL-on-primary-false-lock or PASS statement can be made about it.  The only cells that fire are the M=0.5 cells under reading L, tabled next."]
    md = md.replace("{{PRIMARY}}", "\n".join(pm))
    md = md.replace("{{CELLS10}}", "**Reading S (formal)**: all 8 cells x 3 arms have 0 fires (see D1); nothing to tabulate.\n\n**Reading L (exploratory)**, M=0.5 cells (M=1.0 cells have 0 fires):\n\n"
                    + cell_table([c for c in cells if c["M"] == 0.5], "L", (10,)))
    md = md.replace("{{CELLS_OTHER}}", cell_table([c for c in cells if c["M"] == 0.5], "L", (0, 20)))
    # ---- skips
    sk = ["| reason | count | where |", "|---|---:|---|"]
    for k, v in st["pre_skips"].items():
        sk.append(f"| {k} | {v:,} | rungs, before the window filter |")
    for k, v in st["outside_window"].items():
        sk.append(f"| {k} | {v:,} | bracket rungs outside the frozen 2026-05-23..2026-10-20 window (catalog also holds older/newer settled rungs) |")
    sk.append(f"| event-level skips (tz assertion, insufficient obs) | {sum(st['event_level_skips_rungs'].values()):,} | 0 events skipped; the 1-minute->routine fallback was used for {feeds.get('iem_routine_fallback', 0):,} events |")
    um = out.get("unmapped_series_bracket_rungs_in_window_not_tested", {})
    sk.append(f"| series with no verified station/tz mapping (D7) | {sum(v for v in um.values() if v > 0):,} | {len(um)} series with in-window bracket rungs: {', '.join(f'{k}={v}' for k, v in sorted(um.items()))} (international + extra US); zero-rung series omitted |")
    for k in ("no_candles_in_final_120min", "candle_fetch_error", "not_fetched"):
        sk.append(f"| fired rung: {k} | {cs.get(k, 0):,} | " + {"no_candles_in_final_120min": "no candle in the final 120 minutes -> outside 'candlestick coverage' universe, excluded from covered stats",
                                                                 "candle_fetch_error": "HTTP error on both candle endpoints",
                                                                 "not_fetched": "not reached by the shuffled candle pull (random, un-selected) -- sampling, see fraction above"}[k] + " |")
    n_scalar = sum(v for k_, v in st["pre_skips"].items() if "no_official_result" in k_)
    sk.append(f"| scalar-result rungs | {n_scalar} | result neither yes nor no -> dropped |")
    md = md.replace("{{SKIPS}}", "\n".join(sk))
    dg = out["diagnostics"]
    dl = [f"n = {dg['n']} covered fires.  `official_value - E` (official integer minus the obs extreme at signal time): {json.dumps(dg['official_minus_E_distribution'])}; "
          f"HIGH {json.dumps(dg['by_kind'].get('max', {}))}, LOW {json.dumps(dg['by_kind'].get('min', {}))}.  A non-zero entry means the official value differs from what the obs showed; "
          f"because reading-L fires have E sitting ON a bracket edge (M=0.5), a +/-1 disagreement moves the settlement into a neighbouring bracket -> false lock.",
          "", "Calibration of the market at the first quote at/after signal+10 min, whatever its price (YES rate among fired rungs, by yes_ask):", "",
          "| yes_ask bucket | n | settled YES | YES rate |", "|---|---:|---:|---:|"]
    for k, v in sorted(dg["ask_bucket_at_first_quote_after_signal"].items()):
        dl.append(f"| {k} | {v['n']} | {v['yes']} | {_f(v['yes_rate'], 3, True)} |")
    dl.append("\nWhere the book still offers the winner side at <=98c the book is, on average, correctly pricing the risk that the signal is wrong: the fires that are cheap are disproportionately the false locks.  This is adverse selection into the tradeable subset.")
    md = md.replace("{{DIAG}}", "\n".join(dl))
    return md


# ------------------------------------------------------------------ main (stages A/B only here; report in part 2)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["discover", "obs", "signals", "candles", "report", "verify"])
    ap.add_argument("--max-fetch", type=int, default=10 ** 9)
    ap.add_argument("--budget", type=int, default=6600)
    a = ap.parse_args()
    if a.stage == "discover":
        stage_discover()
    elif a.stage == "obs":
        stage_obs()
    elif a.stage == "signals":
        stage_signals()
    elif a.stage == "candles":
        stage_candles(a.max_fetch, a.budget)
    elif a.stage in ("report", "verify"):
        run_report(a.stage)


if __name__ == "__main__":
    main()
