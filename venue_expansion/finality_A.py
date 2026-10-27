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

CACHE = os.path.join(HERE, "cache", "finality")
MKT_DIR = os.path.join(CACHE, "markets")
OBS_DIR = os.path.join(CACHE, "obs")
CANDLE_DIR = os.path.join(CACHE, "candles")
VERIFY_DIR = os.path.join(CACHE, "verify")
SIGNALS = os.path.join(CACHE, "signals.jsonl")
STAGEA_SUMMARY = os.path.join(CACHE, "stageA_summary.json")
OUT_JSON = os.path.join(HERE, "out", "finality_A.json")
OUT_MD = os.path.join(HERE, "out", "finality_A.md")
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
        if any(int(dt.datetime.fromisoformat(r["close_time"].replace("Z", "+00:00")).timestamp()) != exp_close
               for r in rungs):
            ev_skip["close_time_is_not_LST_midnight_of_event_date+1"] += len(rungs)
            out.write(json.dumps({**base, "skip": "close_time_not_LST_midnight", "n_rungs": len(rungs),
                                  "expected_close_ts": exp_close}) + "\n")
            continue
        day0 = close_ts - 86400
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
                a, b = bisect.bisect_left(ts1, day0 + s * 3600), bisect.bisect_left(ts1, close_ts + s * 3600)
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
            "monotonicity_violations": mono_viol}
    json.dump(summ, open(STAGEA_SUMMARY, "w"), indent=1)
    print(json.dumps(summ, indent=1))


# ------------------------------------------------------------------ candles
def candle_path(tk):
    return os.path.join(CANDLE_DIR, tk + ".json")


def fetch_candles(tk, series, close_ts):
    p = candle_path(tk)
    if os.path.exists(p):
        return json.load(open(p))
    url = (f"/series/{series}/markets/{tk}/candlesticks?start_ts={close_ts - CANDLE_WINDOW_MIN * 60 - 60}"
           f"&end_ts={close_ts}&period_interval=1")
    try:
        d = kget(url)
        res = {"ok": True, "candlesticks": d.get("candlesticks", [])}
    except urllib.error.HTTPError as e:
        res = {"ok": False, "error": f"HTTP {e.code}", "candlesticks": []}
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
