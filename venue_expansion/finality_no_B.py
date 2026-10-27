#!/usr/bin/env python3
"""finality_no_B.py -- BUILD B (independent replication) of FINALITY_NO_LADDER_SPEC.md (frozen 2026-10-27).

Part 1  FINAL-NO by never-arrival on bracket rungs, 12-cell grid x 3 latency arms.
Part 2  whole-ladder pricing from one finality inference, 3 latency arms.

Written from the spec text only.  Reuses edge_sizing_v2.normalize() for candlestick parsing (and nothing
from kwx_lock_rule.py).  Does not read any finality_no_A.* / finality_A.py / finality_B.py file.

*** SIDE / PRICE RULE (has already invalidated work in this repo) ***
A FINAL-NO fire buys NO.  Its executable cost is 100 - yes_bid.  It is NEVER 100 - yes_ask, which is the
NO *bid* (what a seller would get) and is unfillable by a buyer.  A determined-winner YES fire buys YES at
yes_ask.  See `no_cost_c()` / `yes_cost_c()` below -- the ONLY two places a price is formed.

Sub-commands (all resumable, all cached under cache/finality_no/):
  discover   list settled markets for the 40 program weather series, build the shuffled event work order
  obs        fetch IEM obs (1-minute, plus routine fallback) per station
  candles    fetch Kalshi 1-minute candlesticks per EVENT (one batch call, all rungs), in the shuffled
             work order, NEVER re-sorted -> any prefix of the run is a random sample of city-days
  oracle     fetch the events behind the 40 edge_sizing_v2 oracle markets (sanity anchor a)
  analyze    signal walk + price join + statistics -> out/finality_no_B.json, out/finality_no_B.md
"""
from __future__ import annotations

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
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import edge_sizing_v2 as V2  # noqa: E402  -- normalize() only (handles both candlestick cache formats)

CACHE = os.path.join(HERE, "cache", "finality_no")
MKT_DIR = os.path.join(CACHE, "markets")
OBS_DIR = os.path.join(CACHE, "obs")
CND_DIR = os.path.join(CACHE, "candles")
UNIVERSE = os.path.join(CACHE, "universe.json")
OUT_JSON = os.path.join(HERE, "out", "finality_no_B.json")
OUT_MD = os.path.join(HERE, "out", "finality_no_B.md")
ORACLE_JSON = os.path.join(HERE, "out", "edge_sizing_v2.json")
for d in (MKT_DIR, OBS_DIR, CND_DIR, os.path.dirname(OUT_JSON)):
    os.makedirs(d, exist_ok=True)

KAPI = "https://api.elections.kalshi.com/trade-api/v2"
IEM_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
IEM_ROUTINE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

SEED = 20261027                       # documented sampling seed (work order shuffle)
CLOSE_MIN = dt.datetime(2026, 5, 23, tzinfo=dt.timezone.utc)
CLOSE_MAX = dt.datetime(2026, 10, 21, tzinfo=dt.timezone.utc)   # closes through 2026-10-20 inclusive
CANDLE_BACK_MIN = 150                 # candle window: [close-150min, close]  (W<=120 plus slack)
MAX_PAY_C = 98

# --- frozen grid (spec) ---
GRID_G = (2, 4, 6)
GRID_R = (2, 4)
H_OBS = 3
GRID_W = (60, 120)
LAT = (0, 10, 20)
PRIMARY = dict(G=4, R=2, H=3, W=120)
YES_PRIMARY = dict(M=1.0, R=2, H=3, W=120)        # companion FINAL-YES primary cell (for Part 2 "either signal")
N_COMPARISONS = 39
ALPHA_BONF = 0.05 / N_COMPARISONS

# --- the 40 program weather series -> (IEM station, kind). Own table (station codes = settlement CLI sites).
HIGH_CITY = {
    "KXHIGHDEN": "DEN", "KXHIGHMIA": "MIA", "KXHIGHCHI": "MDW", "KXHIGHTBOS": "BOS", "KXHIGHAUS": "AUS",
    "KXHIGHTSEA": "SEA", "KXHIGHTSFO": "SFO", "KXHIGHTMIN": "MSP", "KXHIGHTDC": "DCA", "KXHIGHTATL": "ATL",
    "KXHIGHTDAL": "DFW", "KXHIGHTSATX": "SAT", "KXHIGHNY": "NYC", "KXHIGHTOKC": "OKC", "KXHIGHTLV": "LAS",
    "KXHIGHTPHX": "PHX", "KXHIGHTHOU": "HOU", "KXHIGHPHIL": "PHL", "KXHIGHTNOLA": "MSY", "KXHIGHLAX": "LAX",
}
LOW_CITY = {
    "KXLOWTDEN": "DEN", "KXLOWTMIA": "MIA", "KXLOWTCHI": "MDW", "KXLOWTBOS": "BOS", "KXLOWTAUS": "AUS",
    "KXLOWTSEA": "SEA", "KXLOWTSFO": "SFO", "KXLOWTMIN": "MSP", "KXLOWTDC": "DCA", "KXLOWTATL": "ATL",
    "KXLOWTDAL": "DFW", "KXLOWTSATX": "SAT", "KXLOWTNYC": "NYC", "KXLOWTOKC": "OKC", "KXLOWTLV": "LAS",
    "KXLOWTPHX": "PHX", "KXLOWTHOU": "HOU", "KXLOWTPHIL": "PHL", "KXLOWTNOLA": "MSY", "KXLOWTLAX": "LAX",
}
SERIES = {**{s: (st, "max") for s, st in HIGH_CITY.items()}, **{s: (st, "min") for s, st in LOW_CITY.items()}}


# =====================================================================================================
# HTTP (sequential, ~1/sec, exponential backoff on 429/5xx)
# =====================================================================================================
_last_call = {"t": 0.0}


def http(url, as_json=True, min_gap=1.1, tries=9, timeout=90):
    for i in range(tries):
        wait = min_gap - (time.time() - _last_call["t"])
        if wait > 0:
            time.sleep(wait)
        _last_call["t"] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "finality-no-B/1.0 (research, polite)"})
            with urllib.request.urlopen(req, timeout=timeout) as fh:
                body = fh.read().decode("utf-8", "replace")
            return json.loads(body) if as_json else body
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(90, (2.0 + random.random() * 2.0) * (1.6 ** i)))     # short first retry, then back off
                continue
            if e.code == 404:
                return None
            if i == tries - 1:
                raise
            time.sleep(2 ** i)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(min(60, 2 ** i))
    raise RuntimeError("unreachable")


# =====================================================================================================
# discover
# =====================================================================================================
KEEP = ("ticker", "event_ticker", "close_time", "result", "strike_type", "floor_strike", "cap_strike",
        "expiration_value", "status", "open_time")


def _page_markets(base, s):
    out, cursor = [], None
    while True:
        u = f"{base}?series_ticker={s}&limit=1000" + ("&status=settled" if "historical" not in base else "") \
            + (f"&cursor={cursor}" if cursor else "")
        r = http(u)
        for m in r.get("markets", []):
            rec = {k: m.get(k) for k in KEEP}
            rp = m.get("rules_primary") or ""
            mm = re.search(r"\(([A-Z0-9]{3,6})\)", rp)
            rec["cli"] = mm.group(1) if mm else None
            out.append(rec)
        cursor = r.get("cursor")
        if not cursor or not r.get("markets"):
            break
        if "historical" in base:                 # historical listing is newest-first: stop once past the window
            oldest = min(m["close_time"] for m in r["markets"])
            if dt.datetime.fromisoformat(oldest.replace("Z", "+00:00")) < CLOSE_MIN - dt.timedelta(days=2):
                break
    return out


def discover():
    """LIVE partition (settled >= ~2026-08-21) from /markets, HISTORICAL partition (settled before the
    2026-08-28 cutoff) from /historical/markets.  Merged by ticker; a ticker present in both is routed LIVE."""
    for s in sorted(SERIES):
        for tag, base in (("", f"{KAPI}/markets"), ("_hist", f"{KAPI}/historical/markets")):
            path = os.path.join(MKT_DIR, s + tag + ".json")
            if os.path.exists(path):
                continue
            out = _page_markets(base, s)
            with open(path, "w") as fh:
                json.dump(out, fh)
            print(f"  {s}{tag}: {len(out)} markets", flush=True)

    allm = {}
    for s in sorted(SERIES):
        for tag, src in (("_hist", "hist"), ("", "live")):          # live overwrites hist on overlap
            for m in json.load(open(os.path.join(MKT_DIR, s + tag + ".json"))):
                m["series"], m["src"] = s, src
                allm[m["ticker"]] = m
    ev = collections.defaultdict(list)
    skips = collections.Counter()
    for m in allm.values():
        ct = dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00"))
        if not (CLOSE_MIN <= ct < CLOSE_MAX):
            skips["outside_close_window"] += 1
            continue
        if m["result"] not in ("yes", "no"):
            skips["no_official_result"] += 1
            continue
        if m["strike_type"] not in ("between", "greater", "less"):
            skips["unknown_strike_type:" + str(m["strike_type"])] += 1
            continue
        ev[m["event_ticker"]].append(m)
    events = []
    for et in sorted(ev):                       # deterministic base order ...
        ms = sorted(ev[et], key=lambda m: m["ticker"])
        s = ms[0]["series"]
        events.append({"event": et, "series": s, "station": SERIES[s][0], "kind": SERIES[s][1],
                       "close_time": ms[0]["close_time"], "rungs": ms})
    random.Random(SEED).shuffle(events)         # ... then ONE seeded shuffle; NEVER re-sorted afterwards
    n_live = sum(1 for e in events if all(r["src"] == "live" for r in e["rungs"]))
    json.dump({"seed": SEED, "n_events": len(events), "n_markets": sum(len(e["rungs"]) for e in events),
               "n_events_all_live": n_live, "skips": dict(skips), "events": events}, open(UNIVERSE, "w"))
    print(f"universe: {len(events)} events ({n_live} all-live), {sum(len(e['rungs']) for e in events)} rungs, "
          f"skips={dict(skips)}")


def load_universe():
    return json.load(open(UNIVERSE))


# =====================================================================================================
# obs
# =====================================================================================================
def fetch_1min(station, a, b):
    u = (f"{IEM_1MIN}?station={station}&vars=tmpf&sts={a.strftime('%Y-%m-%dT%H:%MZ')}"
         f"&ets={b.strftime('%Y-%m-%dT%H:%MZ')}&tz=UTC&format=onlycomma")
    txt = http(u, as_json=False, min_gap=0.6, timeout=180)
    rows = []
    for l in txt.splitlines()[1:]:
        p = l.split(",")
        if len(p) < 4 or p[3] in ("M", ""):
            continue
        try:
            ts = int(dt.datetime.strptime(p[2], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp())
            rows.append((ts, float(p[3])))
        except ValueError:
            continue
    return rows


def fetch_routine(station, a, b):
    u = (f"{IEM_ROUTINE}?station={station}&data=tmpf&year1={a.year}&month1={a.month}&day1={a.day}"
         f"&year2={b.year}&month2={b.month}&day2={b.day}&tz=UTC&format=onlycomma&latlon=no"
         "&report_type=3&report_type=4")
    txt = http(u, as_json=False, min_gap=0.6, timeout=180)
    rows = []
    for l in txt.splitlines()[1:]:
        p = l.split(",")
        if len(p) < 3 or p[2] in ("M", ""):
            continue
        try:
            ts = int(dt.datetime.strptime(p[1], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp())
            rows.append((ts, float(p[2])))
        except ValueError:
            continue
    return rows


def obs():
    uni = load_universe()
    by_st = collections.defaultdict(list)
    for e in uni["events"]:
        by_st[e["station"]].append(int(dt.datetime.fromisoformat(e["close_time"].replace("Z", "+00:00")).timestamp()))
    for st in sorted(by_st):
        lo = dt.datetime.fromtimestamp(min(by_st[st]) - 26 * 3600, tz=dt.timezone.utc)
        hi = dt.datetime.fromtimestamp(max(by_st[st]) + 3600, tz=dt.timezone.utc)
        for kind, fn in (("1min", fetch_1min), ("routine", fetch_routine)):
            path = os.path.join(OBS_DIR, f"{st}_{kind}.json")
            if os.path.exists(path):
                continue
            rows, cur = [], lo
            step = dt.timedelta(days=30) if kind == "1min" else dt.timedelta(days=75)
            while cur < hi:
                nxt = min(cur + step, hi)
                rows.extend(fn(st, cur, nxt))
                cur = nxt
            rows = sorted(set(rows))
            with open(path, "w") as fh:
                json.dump(rows, fh)
            print(f"  {st} {kind}: {len(rows)} obs", flush=True)


# =====================================================================================================
# candles
# =====================================================================================================
def day_end(close_ts):
    """Historical-partition close_time is 23:59 local STANDARD time (e.g. 04:59Z for NYC), the live one is
    exactly 24:00 (05:00Z).  The settlement day ends at the next whole hour in both cases."""
    return -(-close_ts // 3600) * 3600


def event_close_ts(e):
    return int(dt.datetime.fromisoformat(e["close_time"].replace("Z", "+00:00")).timestamp())


ORC_DIR = os.path.join(CACHE, "candles_oracle")     # oracle-anchor events live apart so they never enter the random sample


def fetch_event_candles(e, back_min=CANDLE_BACK_MIN, outdir=None):
    """Live rungs: ONE batch call per event.  Historical rungs (settled before the 2026-08-28 cutoff and not
    in the live listing): one /historical/markets/{ticker}/candlesticks call per rung.  Raw responses are
    cached verbatim with a per-market fmt flag ('live' = *_dollars schema, 'hist' = bare schema)."""
    path = os.path.join(outdir or CND_DIR, e["event"] + ".json")
    if os.path.exists(path):
        return True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    close = event_close_ts(e)
    a, b = close - back_min * 60, close
    mk = []
    live = [r["ticker"] for r in e["rungs"] if r["src"] == "live"]
    if live:
        r = http(f"{KAPI}/markets/candlesticks?market_tickers={','.join(live)}&start_ts={a}&end_ts={b}&period_interval=1")
        if r is None or "markets" not in r:
            return False
        got = {m["market_ticker"]: m for m in r["markets"]}
        for tk in live:
            mk.append({"market_ticker": tk, "fmt": "live",
                       "candlesticks": (got.get(tk) or {}).get("candlesticks") or []})
    for rr in e["rungs"]:
        if rr["src"] == "live":
            continue
        r = http(f"{KAPI}/historical/markets/{rr['ticker']}/candlesticks?start_ts={a}&end_ts={b}&period_interval=1")
        if r is None:                                   # 404: no candle record for this market
            mk.append({"market_ticker": rr["ticker"], "fmt": "hist", "candlesticks": [], "http404": True})
        else:
            mk.append({"market_ticker": rr["ticker"], "fmt": "hist", "candlesticks": r.get("candlesticks") or []})
    with open(path, "w") as fh:
        json.dump({"event": e["event"], "close_ts": close, "markets": mk}, fh)
    return True


def is_live_event(e):
    return all(r["src"] == "live" for r in e["rungs"])


def candles(max_events=10 ** 9, stratum="all"):
    """Fetch candlesticks in the (shuffled, never re-sorted) global work order, optionally restricted to a stratum:
    'live' = events whose rungs are all in the live partition (1 batch call each -> census is cheap),
    'hist' = historical-partition events (1 call per rung -> sampled).  Restricting to a stratum keeps the
    shuffled order WITHIN the stratum, so any prefix of each stratum is a uniform random sample of it."""
    uni = load_universe()
    n = 0
    t0 = time.time()
    for i, e in enumerate(uni["events"]):        # shuffled order, never re-sorted
        if n >= max_events:
            break
        if stratum == "live" and not is_live_event(e):
            continue
        if stratum == "hist" and is_live_event(e):
            continue
        if os.path.exists(os.path.join(CND_DIR, e["event"] + ".json")):
            continue
        try:
            fetch_event_candles(e)
        except Exception as ex:                  # disclosed; the event is simply retried on the next run
            print("  fetch error", e["event"], ex, flush=True)
            continue
        n += 1
        if n % 100 == 0:
            print(f"  [{stratum}] {n} events fetched this run (work-order idx {i}/{len(uni['events'])}) "
                  f"{(time.time() - t0) / n:.2f}s/event", flush=True)


def oracle_fetch():
    """Fetch candles for the events behind the 40 oracle markets (anchor a).  Market metadata is pulled
    from the already-discovered universe; candles use the same event-batch call (back 150 min)."""
    uni = load_universe()
    by_tk = {}
    for e in uni["events"]:
        for r in e["rungs"]:
            by_tk[r["ticker"]] = e
    orc = json.load(open(ORACLE_JSON))["capturable_markets_detail"]
    for o in orc:
        e = by_tk.get(o["ticker"])
        if e is None:
            print("  oracle ticker not in universe:", o["ticker"])
            continue
        fetch_event_candles(e, outdir=ORC_DIR)


# =====================================================================================================
# price mechanics -- the ONLY place a price is formed
# =====================================================================================================
def fee_c(cost_c):
    p = cost_c / 100.0
    return math.ceil(7 * p * (1 - p) - 1e-12)


def no_cost_c(yb, ya):
    """FINAL-NO / determined-loser buy: BUY NO.  Executable cost = 100 - yes_bid.
    NEVER 100 - yes_ask (that is the NO bid: what a seller of NO receives; a buyer cannot fill there)."""
    return None if (yb is None or yb <= 0) else 100 - yb


def yes_cost_c(yb, ya):
    """Determined-winner buy: BUY YES at yes_ask."""
    return ya


def first_entry(rows, side, t_entry):
    """First candle with end_ts >= t_entry whose executable cost <= 98c and fee-inclusive net > 0.
    Returns (ts, cost, fee, vol) or None (UNTRADEABLE: counted, never back-filled from an earlier print)."""
    for ts, yb, ya, vol in rows:
        if ts < t_entry:
            continue
        cost = no_cost_c(yb, ya) if side == "no" else yes_cost_c(yb, ya)
        if cost is None or not (0 < cost <= MAX_PAY_C):
            continue
        fee = fee_c(cost)
        if 100 - cost - fee > 0:
            return ts, cost, fee, vol
    return None


# =====================================================================================================
# observations -> per-event day series
# =====================================================================================================
class ObsStore:
    def __init__(self):
        self.one, self.rt = {}, {}

    def _load(self, st, kind):
        d = self.one if kind == "1min" else self.rt
        if st not in d:
            p = os.path.join(OBS_DIR, f"{st}_{kind}.json")
            if not os.path.exists(p):
                d[st] = None
            else:
                a = np.array(json.load(open(p)), dtype=float).reshape(-1, 2)
                d[st] = a
        return d[st]

    def day(self, st, close_ts):
        """Obs on the station's LOCAL DAY = [close-24h, close) in UTC (close_time is local standard-time
        midnight; verified empirically against Kalshi's expiration_value in the report).
        Returns (ts[], f[], feed).  1-minute preferred; routine fallback if 1-minute coverage is thin."""
        b = day_end(close_ts)
        a = b - 86400
        for kind, minn in (("1min", 1150), ("routine", 8)):
            arr = self._load(st, kind)
            if arr is None or len(arr) == 0:
                continue
            i0, i1 = np.searchsorted(arr[:, 0], a, "left"), np.searchsorted(arr[:, 0], b, "left")
            sub = arr[i0:i1]
            if kind == "1min":
                # require good coverage over the day AND over the terminal 130 min
                tail = np.sum(sub[:, 0] >= b - 130 * 60)
                if len(sub) < minn or tail < 110:
                    continue
            elif len(sub) < minn:
                continue
            f = sub[:, 1]
            ok = (f > -60) & (f < 135)               # physical-bounds glitch filter only
            return sub[ok, 0].astype(np.int64), f[ok], kind
        return None, None, None


# =====================================================================================================
# signal engine (prefix-only)
# =====================================================================================================
def running_extreme(f, kind):
    return np.maximum.accumulate(f) if kind == "max" else np.minimum.accumulate(f)


def reversed_and_held(f, E, kind, R, H):
    """rev[k] True iff obs k-H+1..k ALL lie >= R degrees away from the running extreme at k (HIGH: <= E[k]-R,
    LOW: >= E[k]+R).  Uses only obs 0..k (a backward window) -> no look-ahead by construction; the brute-force
    prefix implementation below re-derives it on a sample and the two are asserted equal (anchor b)."""
    n = len(f)
    rev = np.zeros(n, dtype=bool)
    if n < H:
        return rev
    if kind == "max":
        wext = np.maximum.reduce([f[i:n - H + 1 + i] for i in range(H)])      # window max ending at k=H-1..n-1
        rev[H - 1:] = wext <= E[H - 1:] - R
    else:
        wext = np.minimum.reduce([f[i:n - H + 1 + i] for i in range(H)])
        rev[H - 1:] = wext >= E[H - 1:] + R
    return rev


def signal_times(ts, f, kind, R, H, W, close_ts):
    """Candidate indices k (obs k is the newest obs used) with reversal-held, in terminal window.  The
    signal timestamp is t_k = ts[k] + 60s, so every obs used has timestamp STRICTLY < t_k (anchor b)."""
    E = running_extreme(f, kind)
    rev = reversed_and_held(f, E, kind, R, H)
    t = ts + 60
    inwin = (t >= close_ts - W * 60) & (t <= close_ts)
    ks = np.nonzero(rev & inwin)[0]
    return E, t, ks


def rung_bounds(r):
    """Integer-degree win set [lo, hi] for official integer settlement X.  (floor_strike, cap_strike) for
    brackets, both inclusive; 'greater f' -> X >= f+1 ; 'less c' -> X <= c-1."""
    st = r["strike_type"]
    if st == "between":
        return float(r["floor_strike"]), float(r["cap_strike"])
    if st == "greater":
        return float(r["floor_strike"]) + 1, math.inf
    return -math.inf, float(r["cap_strike"]) - 1


def part1_fire(E, t, ks, kind, lo, hi, G, flavour="never"):
    """First k in ks at which the rung's NO-condition holds.
    never-arrival: HIGH E <= lo-G ; LOW E >= hi+G.   overshoot (mirror, reference only): HIGH E >= hi+G ; LOW E <= lo-G."""
    if len(ks) == 0:
        return None
    Ek = E[ks]
    if flavour == "never":
        m = (Ek <= lo - G) if kind == "max" else (Ek >= hi + G)
    else:
        m = (Ek >= hi + G) if kind == "max" else (Ek <= lo - G)
    idx = np.nonzero(m)[0]
    return int(ks[idx[0]]) if len(idx) else None


def part1_fire_bruteforce(ts, f, kind, lo, hi, G, R, H, W, close_ts):
    """Reference implementation, deliberately naive: walk k, and at each k hand the signal ONLY the prefix
    ts[:k+1], f[:k+1] (a hard copy -- the future literally does not exist).  Used to assert anchor (b)."""
    for k in range(len(ts)):
        pts, pf = ts[:k + 1].copy(), f[:k + 1].copy()
        t = int(pts[-1]) + 60
        assert pts.max() < t                       # every obs used is strictly older than t
        if not (close_ts - W * 60 <= t <= close_ts):
            continue
        if len(pf) < H:
            continue
        E = pf.max() if kind == "max" else pf.min()
        w = pf[-H:]
        rev = bool(np.all(w <= E - R)) if kind == "max" else bool(np.all(w >= E + R))
        if not rev:
            continue
        gap = (E <= lo - G) if kind == "max" else (E >= hi + G)
        if gap:
            return k, t, float(E)
    return None


# =====================================================================================================
# candles access
# =====================================================================================================
def _hist_to_dollars(k):
    """Historical-partition candles use bare keys (close/volume); normalize() reads *_dollars/volume_fp.
    Shim ONLY the key names, never a value."""
    k = dict(k)
    for side in ("yes_bid", "yes_ask"):
        n = k.get(side) or {}
        k[side] = {"close_dollars": n.get("close_dollars", n.get("close"))}
    if "volume_fp" not in k:
        k["volume_fp"] = k.get("volume")
    return k


def load_event_candles(e, alt_dir=None):
    path = os.path.join(CND_DIR, e["event"] + ".json")
    if not os.path.exists(path) and alt_dir:
        path = os.path.join(alt_dir, e["event"] + ".json")
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    close_ts = d["close_ts"]
    V2.WINDOW_MIN = CANDLE_BACK_MIN                 # normalize() keeps [close-WINDOW_MIN*60, close]
    out = {}
    for m in d["markets"]:
        cs = m.get("candlesticks") or []
        if m.get("fmt") == "hist":
            cs = [_hist_to_dollars(k) for k in cs]
        rows = V2.normalize(cs, close_ts)
        rows = [r for r in rows if r[0] is not None]
        rows.sort(key=lambda r: r[0])
        out[m["market_ticker"]] = rows
    return out


# =====================================================================================================
# statistics
# =====================================================================================================
from scipy import stats as sst  # noqa: E402


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, c - h), min(1.0, c + h)


def cluster_stat(x, w, cl):
    """Weighted mean and cluster-robust (CR1) SE of the weighted mean.  Returns (mean, se, t, df, nclusters)."""
    x, w = np.asarray(x, float), np.asarray(w, float)
    sw = w.sum()
    if len(x) == 0 or sw <= 0:
        return (float("nan"),) * 4 + (0,)
    mu = float((w * x).sum() / sw)
    cl = np.asarray(cl)
    uniq, inv = np.unique(cl, return_inverse=True)
    G = len(uniq)
    if G < 2:
        return mu, float("nan"), float("nan"), 0.0, G
    s = np.bincount(inv, weights=w * (x - mu), minlength=G)
    var = G / (G - 1) * float((s ** 2).sum()) / sw ** 2
    se = math.sqrt(var)
    return mu, se, (mu / se if se > 1e-9 else float("nan")), G - 1.0, G


def t_bar(df, alpha=ALPHA_BONF):
    return float(sst.t.ppf(1 - alpha / 2, df)) if df and df > 0 else float("inf")


def t_ub(df, p=0.979):
    return float(sst.t.ppf(p, df)) if df and df > 0 else float("inf")


# =====================================================================================================
# analysis
# =====================================================================================================
def date_from_event(et):
    m = re.search(r"-(\d\d)([A-Z]{3})(\d\d)$", et)
    return dt.datetime.strptime(m.group(1) + m.group(2) + m.group(3), "%y%b%d").date()


def analyze(sample_check=True):
    uni = load_universe()
    store = ObsStore()
    events = uni["events"]
    done = [e for e in events if os.path.exists(os.path.join(CND_DIR, e["event"] + ".json"))]
    n_universe = len(events)
    # contiguous-prefix property: the work order is the shuffled order; "done" is the shuffled prefix
    # (plus any retried stragglers), so it is a uniform random sample of city-days.
    first_missing = next((i for i, e in enumerate(events) if e not in done), n_universe)

    # stratified design weights: live partition is a census-in-progress, hist partition is sampled; weight each
    # event by N_stratum / n_stratum_fetched so the pooled estimate is unbiased for the whole universe.
    N_s = collections.Counter(is_live_event(e) for e in events)
    n_s = collections.Counter(is_live_event(e) for e in done)
    DW = {k: (N_s[k] / n_s[k] if n_s[k] else 0.0) for k in (True, False)}
    skips = collections.Counter()
    fires = []          # Part 1 never-arrival fire records (per rung x cell)
    over_fires = []     # overshoot-mirror reference fires (primary-structure only, anchor d)
    day_rec = []        # per event diagnostics
    p2_days = []        # Part 2 per signalling city-day
    feed_counts = collections.Counter()
    val = collections.Counter()
    tz_alt = collections.Counter()
    mono_viol = 0
    worked = {}
    stations_seen = set()
    bf_checked = 0

    for e in done:
        close = event_close_ts(e)
        dend = day_end(close)                       # nominal local-standard-midnight (window anchor)
        ts, f, feed = store.day(e["station"], close)
        if ts is None:
            skips["no_obs"] += 1
            continue
        cmap = load_event_candles(e)
        if cmap is None:
            skips["no_candles_file"] += 1
            continue
        kind = e["kind"]
        feed_counts[feed] += 1
        stations_seen.add(e["station"])
        # (c) monotonicity of running extreme within the local day
        Efull = running_extreme(f, kind)
        d = np.diff(Efull)
        if (kind == "max" and (d < 0).any()) or (kind == "min" and (d > 0).any()):
            mono_viol += 1
        assert ts.min() >= dend - 86400 and ts.max() < dend and (np.diff(ts) > 0).all()
        # tz / day-window validation against Kalshi's official expiration_value
        ev = e["rungs"][0].get("expiration_value")
        try:
            evf = float(ev)
        except Exception:
            evf = None
        if evf is not None:
            arr = store._load(e["station"], "1min") if feed == "1min" else store._load(e["station"], "routine")
            ext = (np.max if kind == "max" else np.min)
            for tag, (a, b) in (("lst_midnight(dayend-24h..dayend)", (dend - 86400, dend)),
                                ("dst_local_midnight(dayend-25h..dayend-1h)", (dend - 90000, dend - 3600)),
                                ("utc_calendar_day", (None, None))):
                if a is None:
                    cd = dt.datetime.fromtimestamp(dend - 43200, tz=dt.timezone.utc).replace(hour=0, minute=0, second=0)
                    a, b = int(cd.timestamp()), int(cd.timestamp()) + 86400
                i0, i1 = np.searchsorted(arr[:, 0], a, "left"), np.searchsorted(arr[:, 0], b, "left")
                sub = arr[i0:i1, 1]
                sub = sub[(sub > -60) & (sub < 135)]
                if len(sub) >= 8:
                    tz_alt[(tag, "n")] += 1
                    if abs(float(ext(sub)) - evf) < 0.51:
                        tz_alt[(tag, "match")] += 1
            val[("n", feed)] += 1
            if abs(float(Efull[-1]) - evf) < 0.51:
                val[("match", feed)] += 1
            if abs(float(Efull[-1]) - evf) < 1.51:
                val[("within1", feed)] += 1

        dkey = e["station"] + "|" + date_from_event(e["event"]).isoformat()
        rungs = []
        for r in e["rungs"]:
            lo, hi = rung_bounds(r)
            rungs.append({"ticker": r["ticker"], "type": "B" if r["strike_type"] == "between" else "T",
                          "lo": lo, "hi": hi, "result": r["result"], "rows": cmap.get(r["ticker"], [])})
        rungs.sort(key=lambda r: (r["lo"], r["hi"]))
        # exactly-one-winner partition check (official results)
        nyes = sum(1 for r in rungs if r["result"] == "yes")
        part_ok = (nyes == 1)

        # ---- Part 1: never-arrival fires, all cells ----
        for R in GRID_R:
            for W in GRID_W:
                E, t, ks = signal_times(ts, f, kind, R, H_OBS, W, dend)
                for G in GRID_G:
                    for r in rungs:
                        if r["type"] != "B":
                            continue
                        k = part1_fire(E, t, ks, kind, r["lo"], r["hi"], G, "never")
                        if k is not None:
                            fires.append({"ev": e["event"], "dkey": dkey, "stn": e["station"], "kind": kind,
                                          "tk": r["ticker"], "cell": (G, R, W), "t": int(t[k]), "E": float(E[k]),
                                          "res": r["result"], "feed": feed, "rows": r["rows"], "close": close,
                                          "flav": "never", "dw": DW[is_live_event(e)]})
                        # overshoot-mirror reference (anchor d): same shape/timing, other side of the bracket
                        k2 = part1_fire(E, t, ks, kind, r["lo"], r["hi"], G, "over")
                        if k2 is not None:
                            over_fires.append({"ev": e["event"], "dkey": dkey, "stn": e["station"], "kind": kind,
                                               "tk": r["ticker"], "cell": (G, R, W), "t": int(t[k2]),
                                               "E": float(E[k2]), "res": r["result"], "feed": feed,
                                               "rows": r["rows"], "close": close, "flav": "overshoot",
                                               "dw": DW[is_live_event(e)]})
        # ---- anchor (b): brute-force prefix-only implementation agrees with the vectorised one ----
        if sample_check and (zlib.crc32(e["event"].encode()) % 40 == 0) and bf_checked < 150:
            bf_checked += 1
            for (G, R, W) in ((4, 2, 120), (2, 4, 60), (6, 2, 120)):
                E, t, ks = signal_times(ts, f, kind, R, H_OBS, W, dend)
                for r in rungs:
                    if r["type"] != "B":
                        continue
                    k = part1_fire(E, t, ks, kind, r["lo"], r["hi"], G, "never")
                    bf = part1_fire_bruteforce(ts, f, kind, r["lo"], r["hi"], G, R, H_OBS, W, dend)
                    assert (k is None) == (bf is None), (e["event"], r["ticker"], G, R, W, k, bf)
                    if k is not None:
                        assert bf[0] == k and bf[1] == int(t[k]) and abs(bf[2] - float(E[k])) < 1e-9
                    if k is not None and "b" not in worked:
                        worked["b"] = {"event": e["event"], "ticker": r["ticker"], "cell": [G, R, W],
                                       "fire_obs_index": k, "fire_obs_ts_utc": dt.datetime.fromtimestamp(
                                           int(ts[k]), tz=dt.timezone.utc).isoformat(),
                                       "signal_ts_utc": dt.datetime.fromtimestamp(int(t[k]), tz=dt.timezone.utc).isoformat(),
                                       "E_at_fire": float(E[k]), "last_H_obs": f[k - H_OBS + 1:k + 1].tolist(),
                                       "lo": r["lo"], "hi": r["hi"], "n_obs_in_prefix": k + 1,
                                       "n_obs_in_full_day": int(len(ts)),
                                       "max_prefix_obs_ts_lt_signal_ts": bool(ts[:k + 1].max() < t[k])}

        # ---- Part 2: one inference prices the whole ladder ----
        if part_ok:
            E2, t2, ks2 = signal_times(ts, f, kind, PRIMARY["R"], H_OBS, PRIMARY["W"], dend)
            kk = None
            for k in ks2:           # earliest day-level fire of EITHER primary-cell signal
                Ek = E2[k]
                no_any = False
                yes_any = False
                for r in rungs:
                    if r["type"] != "B":
                        continue
                    if (kind == "max" and Ek <= r["lo"] - PRIMARY["G"]) or (kind == "min" and Ek >= r["hi"] + PRIMARY["G"]):
                        no_any = True
                    if r["lo"] + YES_PRIMARY["M"] <= Ek <= r["hi"] - YES_PRIMARY["M"]:
                        yes_any = True
                if no_any or yes_any:
                    kk = int(k)
                    break
            if kk is not None:
                Ek = float(E2[kk])
                xhat = math.floor(Ek + 0.5)
                widx = [i for i, r in enumerate(rungs) if r["lo"] <= xhat <= r["hi"]]
                if len(widx) == 1:
                    wi = widx[0]
                    p2_days.append({"ev": e["event"], "dkey": dkey, "stn": e["station"], "kind": kind, "t": int(t2[kk]),
                                    "E": Ek, "xhat": xhat, "wi": wi, "close": close, "feed": feed, "dw": DW[is_live_event(e)],
                                    "xofficial": evf,
                                    "rungs": [{"tk": r["tk"] if "tk" in r else r["ticker"], "i": i, "type": r["type"],
                                               "lo": r["lo"], "hi": r["hi"], "res": r["result"], "rows": r["rows"]}
                                              for i, r in enumerate(rungs)]})
                else:
                    skips["p2_no_unique_winner_rung_for_xhat"] += 1
        else:
            skips["p2_ladder_not_exactly_one_yes_official"] += 1

    return dict(uni=uni, events=events, done=done, first_missing=first_missing, skips=skips, fires=fires,
                over_fires=over_fires, p2_days=p2_days, feed_counts=feed_counts, val=val, tz_alt=tz_alt,
                mono_viol=mono_viol, worked=worked, DW={str(k): v for k, v in DW.items()}, N_s={str(k): v for k, v in N_s.items()}, n_s={str(k): v for k, v in n_s.items()}, n_universe=n_universe, stations_seen=stations_seen,
                bf_checked=bf_checked)


# ----- pricing a set of fires under a latency arm -----
def price_fires(fires, L, side="no"):
    out = []
    for fr in fires:
        got = first_entry(fr["rows"], side, fr["t"] + L * 60)
        rec = {"dkey": fr["dkey"], "stn": fr["stn"], "res": fr["res"], "ev": fr["ev"], "tk": fr["tk"],
               "cell": fr["cell"], "priced": got is not None, "feed": fr.get("feed"), "kind": fr.get("kind"),
               "dw": fr.get("dw", 1.0)}
        if got is None:
            after = [r for r in fr["rows"] if r[0] >= fr["t"] + L * 60]
            rec["why"] = "no_candle_at_or_after_entry_time" if not after else "candles_exist_but_none_<=98c_net>0"
        if got:
            ts, cost, fee, vol = got
            won = (fr["res"] == "no") if side == "no" else (fr["res"] == "yes")
            rec.update({"ts": ts, "cost": cost, "fee": fee, "vol": vol,
                        "pnl": (100 - cost - fee) if won else (-cost - fee)})
        out.append(rec)
    return out


def cell_stats(fires, L):
    pr = price_fires(fires, L, "no")
    n_fire = len(pr)
    false_all = sum(1 for p in pr if p["res"] == "yes")
    pp = [p for p in pr if p["priced"]]
    n_pr = len(pp)
    false_pr = sum(1 for p in pp if p["res"] == "yes")
    fl_all = wilson(false_all, n_fire)
    fl_pr = wilson(false_pr, n_pr)
    res = {"n_fires": n_fire, "n_priced": n_pr, "untradeable_frac": (1 - n_pr / n_fire) if n_fire else None,
           "untradeable_reasons": dict(collections.Counter(p["why"] for p in pr if not p["priced"])),
           "false_lock_all": {"k": false_all, "n": n_fire, "rate": fl_all[0], "wilson_lo": fl_all[1], "wilson_hi": fl_all[2]},
           "false_lock_priced": {"k": false_pr, "n": n_pr, "rate": fl_pr[0], "wilson_lo": fl_pr[1], "wilson_hi": fl_pr[2]},
           "false_lock_city_days": len({p["dkey"] for p in pr if p["res"] == "yes"}),
           "signalling_city_days": len({p["dkey"] for p in pr}),
           "priced_city_days": len({p["dkey"] for p in pp}),
           "priced_calendar_days": len({p["dkey"].split("|")[1] for p in pp}),
           "priced_stations": len({p["stn"] for p in pp})}
    if n_pr:
        x = np.array([p["pnl"] for p in pp], float)
        dwv = np.array([p["dw"] for p in pp], float)
        v = np.array([p["vol"] for p in pp], float) * dwv         # volume weight x stratified design weight
        res["win_rate_priced"] = float(np.mean([p["res"] == "no" for p in pp]))
        res["mean_cost_c"] = float(np.mean([p["cost"] for p in pp]))
        res["ev_raw_mean_c"] = float(x.mean())                    # no weights at all
        res["ev_unweighted_c"] = float((x * dwv).sum() / dwv.sum())   # design-weighted, volume-unweighted
        for tag, key in (("cityday", lambda p: p["dkey"]), ("calday", lambda p: p["dkey"].split("|")[1])):
            cl = [key(p) for p in pp]
            mu, se, t, df, g = cluster_stat(x, v, cl)
            mu_u, se_u, t_u, df_u, _ = cluster_stat(x, dwv, cl)
            res["vw_" + tag] = {"ev_c": mu, "se": se, "t": t, "df": df, "clusters": g,
                                "t_bar": t_bar(df), "ub979": (mu + t_ub(df) * se) if df else None}
            res["uw_" + tag] = {"ev_c": mu_u, "se": se_u, "t": t_u, "df": df_u, "clusters": g,
                                "t_bar": t_bar(df_u), "ub979": (mu_u + t_ub(df_u) * se_u) if df_u else None}
        res["vol_total_raw"] = float(sum(p["vol"] for p in pp))
        res["n_zero_volume_entry"] = int(sum(1 for p in pp if p["vol"] <= 0))
    return res


def carry_forward_diag(fires, L):
    """DESCRIPTIVE ONLY (never used for the verdict, which forbids back-filling): for primary-cell fires that were
    UNTRADEABLE, what would the book have offered if the last printed quote at/before the entry time were assumed
    to persist through candle-less minutes?  Shows whether sparse candles are hiding capturable entries."""
    n_ut, n_stale_ok, n_no_prior, n_cost_hist = 0, 0, 0, collections.Counter()
    for fr in fires:
        te = fr["t"] + L * 60
        if first_entry(fr["rows"], "no", te):
            continue
        n_ut += 1
        prior = [r for r in fr["rows"] if r[0] < te]
        after = [r for r in fr["rows"] if r[0] >= te]
        if after:
            continue                                  # candles exist after entry and none qualified -> not a sparsity issue
        if not prior:
            n_no_prior += 1
            continue
        _, yb, ya, _ = prior[-1]
        c = no_cost_c(yb, ya)
        n_cost_hist["none" if c is None else ("<=98" if c <= 98 else ">98")] += 1
        if c is not None and 0 < c <= 98 and 100 - c - fee_c(c) > 0:
            n_stale_ok += 1
    return {"untradeable": n_ut, "no_candle_after_entry_and_no_prior_candle": n_no_prior,
            "no_candle_after_entry_prior_quote_cost_class": dict(n_cost_hist), "stale_quote_would_qualify": n_stale_ok}


def entry_cost_classes(fires, L):
    """Why are fires untradeable?  Over candles at/after the entry time: no candle at all / yes_bid<=0 on every candle (NO costs
    100c, nothing to buy) / best NO cost 99c (net 0 after the 1c fee) / priced."""
    c = collections.Counter()
    for fr in fires:
        te = fr["t"] + L * 60
        after = [r for r in fr["rows"] if r[0] >= te]
        if not after:
            c["no_candle_at_or_after_entry"] += 1
            continue
        costs = [x for x in (no_cost_c(r[1], r[2]) for r in after) if x is not None]
        if not costs:
            c["yes_bid_zero_on_every_candle (NO cost 100c)"] += 1
        elif first_entry(fr["rows"], "no", te):
            c["priced (cost<=98c, net>0)"] += 1
        elif min(costs) == 99:
            c["best_NO_cost_99c (net 0 after 1c fee)"] += 1
        else:
            c["other"] += 1
    return dict(c)


def part1_verdict(grid):
    """grid[(G,R,W)][L] -> stats.  Verdict from the L=10 arm only (spec)."""
    passes, notes = [], []
    best_ub, kill_fl = None, False
    ev_pos_cells, ev_pos_fail_n = 0, 0
    for cell, arms in grid.items():
        s = arms[10]
        if s["n_priced"] == 0:
            continue
        v = s["vw_cityday"]
        vc = s["vw_calday"]
        if v["ev_c"] is None or (isinstance(v["ev_c"], float) and math.isnan(v["ev_c"])):
            v, vc = s["uw_cityday"], s["uw_calday"]       # every entry candle had zero volume -> fall back (flagged by n_zero_volume_entry)
        ub = v["ub979"]
        if ub is not None and not math.isnan(ub):
            best_ub = ub if best_ub is None else max(best_ub, ub)
        n_ok = (s["n_priced"] >= 100 and s["priced_calendar_days"] >= 40 and s["priced_stations"] >= 10)
        if v["ev_c"] > 0:
            ev_pos_cells += 1
            if not n_ok:
                ev_pos_fail_n += 1
        fl_ok = (s["false_lock_all"]["rate"] <= 0.02 and s["false_lock_all"]["wilson_hi"] <= 0.05 and
                 s["false_lock_priced"]["rate"] <= 0.02 and s["false_lock_priced"]["wilson_hi"] <= 0.05)
        t_use = min(v["t"], vc["t"])
        bar = max(v["t_bar"], vc["t_bar"])
        ok = (fl_ok and v["ev_c"] >= 2.0 and t_use >= bar and n_ok and s["untradeable_frac"] <= 0.70)
        if ok:
            passes.append(cell)
    prim = grid[(PRIMARY["G"], PRIMARY["R"], PRIMARY["W"])][10]
    if prim["n_fires"] and prim["false_lock_all"]["rate"] > 0.05:
        kill_fl = True
    kill = kill_fl or (best_ub is not None and best_ub < 0.5) or (ev_pos_cells > 0 and ev_pos_fail_n == ev_pos_cells)
    if passes:
        verdict = "PASS"
    elif kill:
        verdict = "KILL"
    else:
        verdict = "INSUFFICIENT"
    return verdict, {"pass_cells": [list(c) for c in passes], "kill_false_lock_primary": kill_fl,
                     "best_one_sided_97.9_ub_vw_ev_c": best_ub,
                     "ev_pos_cells": ev_pos_cells, "ev_pos_cells_failing_n_floor": ev_pos_fail_n,
                     "kill_no_ev_pos_cell_vacuous": ev_pos_cells == 0}


# ----- Part 2 pricing -----
def part2_price(p2_days, L):
    fires, ladders = [], []
    for d in p2_days:
        day_fires = []
        for r in d["rungs"]:
            side = "yes" if r["i"] == d["wi"] else "no"
            got = first_entry(r["rows"], side, d["t"] + L * 60)
            dist = abs(r["i"] - d["wi"])
            # loser flavour vs the inferred extreme: rung entirely below inferred X (HIGH: overshoot) / above (never)
            if side == "no":
                below = r["hi"] < d["xhat"]
                flav = ("overshoot" if below else "never") if d["kind"] == "max" else ("never" if below else "overshoot")
            else:
                flav = "winner"
            rec = {"dkey": d["dkey"], "stn": d["stn"], "tk": r["tk"], "side": side, "dist": dist, "flav": flav,
                   "res": r["res"], "priced": got is not None, "dw": d["dw"]}
            if got:
                ts, cost, fee, vol = got
                won = (r["res"] == "yes") if side == "yes" else (r["res"] == "no")
                rec.update({"cost": cost, "fee": fee, "vol": vol, "pnl": (100 - cost - fee) if won else (-cost - fee)})
            fires.append(rec)
            day_fires.append(rec)
        priced = [x for x in day_fires if x["priced"]]
        wrong = any((x["side"] == "yes" and x["res"] == "no") or (x["side"] == "no" and x["res"] == "yes")
                    for x in day_fires)
        ladders.append({"dkey": d["dkey"], "dw": d["dw"], "n_rungs": len(day_fires), "n_priced": len(priced),
                        "net": float(sum(x["pnl"] for x in priced)), "wrong_inference": wrong,
                        "xhat": d["xhat"], "xofficial": d["xofficial"]})
    # city-day = (station, local date); HIGH and LOW ladders of the same city-day are pooled (conservative)
    agg = {}
    for l in ladders:
        a_ = agg.setdefault(l["dkey"], {"dkey": l["dkey"], "dw": l["dw"], "n_rungs": 0, "n_priced": 0, "net": 0.0,
                                        "wrong_inference": False, "n_ladders": 0, "xhat": [], "xofficial": []})
        a_["n_rungs"] += l["n_rungs"]
        a_["n_priced"] += l["n_priced"]
        a_["net"] += l["net"]
        a_["wrong_inference"] |= l["wrong_inference"]
        a_["n_ladders"] += 1
    days = list(agg.values())
    n_ladders = len(ladders)
    part2_price.last_ladders = ladders
    return fires, days


def part2_stats(p2_days, L):
    fires, days = part2_price(p2_days, L)
    nd = len(days)
    pr = [x for x in fires if x["priced"]]
    dwd = np.array([d["dw"] for d in days], float)
    pri_by_day = np.array([d["n_priced"] for d in days], float)
    res = {"signalling_city_days": nd, "n_rung_evals": len(fires), "n_priced_fires": len(pr),
           "mean_fires_per_signalling_day": float((dwd * pri_by_day).sum() / dwd.sum()) if nd else None,
           "mean_fires_per_signalling_day_raw": len(pr) / nd if nd else None,
           "mean_fires_per_day_with_any_fire": (float((dwd * pri_by_day).sum() / max(1e-9, dwd[pri_by_day > 0].sum()))
                                                if nd and (pri_by_day > 0).any() else None),
           "days_with_any_priced_fire": int((pri_by_day > 0).sum()),
           "untradeable_frac": 1 - len(pr) / len(fires) if fires else None}
    if nd > 1:
        nets = np.array([d["net"] for d in days])
        mu, se, t, df, g = cluster_stat(nets, dwd, [d["dkey"] for d in days])
        res.update({"per_day_net_ev_c": mu, "per_day_net_ev_raw_c": float(nets.mean()), "per_day_net_se": se,
                    "t_cityday": t, "df": df, "t_bar": t_bar(df), "ub979": (mu + t_ub(df) * se) if df else None})
        dates = [d["dkey"].split("|")[1] for d in days]
        mu2, se_c, t_c, df_c, g2 = cluster_stat(nets, dwd, dates)
        res.update({"t_calday": t_c, "df_calday": df_c, "t_bar_calday": t_bar(df_c)})
        lad = part2_price.last_ladders
        lw = np.array([l["dw"] for l in lad], float)
        res["n_ladders"] = len(lad)
        res["wrong_inference_ladder_frac"] = float((lw * np.array([l["wrong_inference"] for l in lad])).sum() / lw.sum())
        res["xhat_vs_official_exact_frac"] = float((lw * np.array([l["xofficial"] is not None and abs(l["xhat"] - l["xofficial"]) < 0.51
                                                                  for l in lad])).sum() / lw.sum())
        res["xhat_vs_official_within1_frac"] = float((lw * np.array([l["xofficial"] is not None and abs(l["xhat"] - l["xofficial"]) < 1.51
                                                                    for l in lad])).sum() / lw.sum())

    def agg(sel):
        s_ = [x for x in pr if sel(x)]
        if not s_:
            return {"n": 0}
        x = np.array([a["pnl"] for a in s_], float)
        w = np.array([a["dw"] for a in s_], float)
        mu, se, t, df, g = cluster_stat(x, w, [a["dkey"] for a in s_])
        n_all = sum(1 for a in fires if sel(a))
        return {"n": len(s_), "of_evaluated": n_all, "ev_c": mu, "se_cityday": se, "t_cityday": t,
                "win_rate": float((w * np.array([(a["res"] == "yes") == (a["side"] == "yes") for a in s_])).sum() / w.sum()),
                "mean_cost_c": float(np.mean([a["cost"] for a in s_]))}
    res["by_abs_distance"] = {str(dd): agg(lambda a, dd=dd: a["dist"] == dd) for dd in range(0, 4)}
    res["by_abs_distance"]["4+"] = agg(lambda a: a["dist"] >= 4)
    res["by_flavour"] = {fl: agg(lambda a, fl=fl: a["flav"] == fl) for fl in ("winner", "never", "overshoot")}
    res["by_side"] = {sd: agg(lambda a, sd=sd: a["side"] == sd) for sd in ("yes", "no")}
    return res, fires, days


# =====================================================================================================
# anchors + report
# =====================================================================================================
def capturable_final60(rows, result, close_ts):
    """edge_sizing_v2 Stage-1 definition, re-implemented on MY candles: winner-side buyable <=98c, net>0, last 60 min."""
    best, n_cap, n_min = None, 0, 0
    for ts, yb, ya, vol in rows:
        if ts < close_ts - 3600 or ts > close_ts:
            continue
        cost = yes_cost_c(yb, ya) if result == "yes" else no_cost_c(yb, ya)
        if cost is None:
            continue
        n_min += 1
        if not (0 < cost <= MAX_PAY_C):
            continue
        net = 100 - cost - fee_c(cost)
        if net <= 0:
            continue
        n_cap += 1
        if best is None or cost < best[0]:
            best = (cost, net)
    return {"n_data_minutes": n_min, "n_capturable_minutes": n_cap, "best_cost": best[0] if best else None,
            "best_net": best[1] if best else None}


def anchor_a(A):
    uni = load_universe()
    by_tk = {r["ticker"]: e for e in uni["events"] for r in e["rungs"]}
    orc = json.load(open(ORACLE_JSON))["capturable_markets_detail"]
    rows_out, ok_cost, ok_net, ok_cap, ok_nmin, have = [], 0, 0, 0, 0, 0
    for o in orc:
        e = by_tk.get(o["ticker"])
        cm = load_event_candles(e, ORC_DIR) if e else None
        if cm is None:
            rows_out.append({"ticker": o["ticker"], "status": "event_candles_not_fetched"})
            continue
        have += 1
        res = next(r["result"] for r in e["rungs"] if r["ticker"] == o["ticker"])
        mine = capturable_final60(cm.get(o["ticker"], []), res, event_close_ts(e))
        c_ok = mine["best_cost"] == o["best_winner_cost_c"]
        n_ok = mine["best_net"] == o["best_net_c"]
        k_ok = mine["n_capturable_minutes"] > 0
        m_ok = abs(mine["n_data_minutes"] - o["n_data_minutes"]) <= 1
        ok_cost += c_ok; ok_net += n_ok; ok_cap += k_ok; ok_nmin += m_ok
        rows_out.append({"ticker": o["ticker"], "oracle_cost": o["best_winner_cost_c"], "my_cost": mine["best_cost"],
                         "oracle_net": o["best_net_c"], "my_net": mine["best_net"],
                         "oracle_nmin": o["n_data_minutes"], "my_nmin": mine["n_data_minutes"],
                         "capturable_mine": k_ok})
    # population rate inside the oracle window on MY sample (oracle: 140/1353 = 10.35% sample, 10.0% weighted)
    lim = int(dt.datetime(2026, 8, 5, tzinfo=dt.timezone.utc).timestamp())
    n_r, n_c = 0, 0
    for e in A["done"]:
        if event_close_ts(e) >= lim:
            continue
        cm = load_event_candles(e)
        for r in e["rungs"]:
            rows = cm.get(r["ticker"], [])
            rr = [x for x in rows if x[0] >= event_close_ts(e) - 3600]
            if not rr:
                continue                       # oracle skipped markets without candles ("no_candles")
            n_r += 1
            n_c += capturable_final60(rows, r["result"], event_close_ts(e))["n_capturable_minutes"] > 0
    return {"oracle_top40_reproduction": {"events_available": have, "of": len(orc), "best_cost_match": int(ok_cost),
                                          "best_net_match": int(ok_net), "capturable_match": int(ok_cap),
                                          "n_data_minutes_within_1": int(ok_nmin), "rows": rows_out},
            "population_rate_in_oracle_window": {"rungs_with_candles": n_r, "capturable": n_c,
                                                 "rate": (n_c / n_r) if n_r else None,
                                                 "oracle_reference_rate": "0.1035 sample (140/1353), 0.100 pop-weighted"}}


def anchor_a_fires(A):
    """Every PRICED fire that was a correct NO and entered inside the oracle's final-60-minute window must be
    oracle-capturable on the same candles (price join sanity).  Also every priced fire's entry candle must exist
    in the rung's candle list, and the NO cost must equal 100 - that candle's yes_bid (never 100 - yes_ask)."""
    bad_join, n, n_orc = 0, 0, 0
    for fr in A["fires"]:
        if fr["cell"] != (PRIMARY["G"], PRIMARY["R"], PRIMARY["W"]):
            continue
        got = first_entry(fr["rows"], "no", fr["t"] + 600)
        if not got:
            continue
        n += 1
        ts, cost, fee, vol = got
        row = next((r for r in fr["rows"] if r[0] == ts), None)
        if row is None or row[1] is None or cost != 100 - row[1]:
            bad_join += 1
        if fr["res"] == "no" and ts >= fr["close"] - 3600:
            n_orc += 1
            if capturable_final60(fr["rows"], "no", fr["close"])["n_capturable_minutes"] == 0:
                bad_join += 1
    return {"priced_primary_L10_fires_checked": n, "correct_NO_entries_in_oracle_window": n_orc,
            "join_violations": bad_join}


TZ = {"DEN": "America/Denver", "MIA": "America/New_York", "MDW": "America/Chicago", "BOS": "America/New_York",
      "AUS": "America/Chicago", "SEA": "America/Los_Angeles", "SFO": "America/Los_Angeles", "MSP": "America/Chicago",
      "DCA": "America/New_York", "ATL": "America/New_York", "DFW": "America/Chicago", "SAT": "America/Chicago",
      "NYC": "America/New_York", "OKC": "America/Chicago", "LAS": "America/Los_Angeles", "PHX": "America/Phoenix",
      "HOU": "America/Chicago", "PHL": "America/New_York", "MSY": "America/Chicago", "LAX": "America/Los_Angeles"}


def tz_worked_example(A):
    """Pick fully-covered days and show the settlement-day window, its local wall-clock meaning, and what a
    one-hour-skewed window (naive DST-clock midnight) or a UTC calendar day would have produced instead.
    Selected by data-quality only (full 1-min coverage + a DST-season date where the skew changes the answer);
    never by anything that touches prices or outcomes."""
    from zoneinfo import ZoneInfo
    uni = load_universe()
    store = ObsStore()
    U = lambda t: dt.datetime.fromtimestamp(t, tz=dt.timezone.utc)
    ex, seen = [], set()
    for e in uni["events"]:
        key = (e["station"], e["kind"])
        if key in seen or e["station"] not in ("NYC", "SEA", "DEN", "MIA", "BOS", "LAX"):
            continue
        close = event_close_ts(e)
        dend = day_end(close)
        arr = store._load(e["station"], "1min")
        i0, i1 = np.searchsorted(arr[:, 0], dend - 86400), np.searchsorted(arr[:, 0], dend)
        sub = arr[i0:i1]
        if len(sub) < 1435:
            continue
        zi = ZoneInfo(TZ[e["station"]])
        off = U(dend - 86400).astimezone(zi).utcoffset().total_seconds() / 3600
        try:
            ev = float(e["rungs"][0].get("expiration_value"))
        except Exception:
            continue
        fn = np.max if e["kind"] == "max" else np.min
        alts = {}
        cd = int(U(dend - 43200).replace(hour=0, minute=0, second=0).timestamp())
        for tag, (x, y) in (("naive DST-clock-midnight window (dayend-25h..dayend-1h)", (dend - 90000, dend - 3600)),
                            ("naive UTC-calendar-day window", (cd, cd + 86400))):
            j0, j1 = np.searchsorted(arr[:, 0], x), np.searchsorted(arr[:, 0], y)
            alts[tag] = float(fn(arr[j0:j1, 1]))
        mine = float(fn(sub[:, 1]))
        dst = off != {"NYC": -5, "MIA": -5, "BOS": -5, "SEA": -8, "LAX": -8, "DEN": -7}[e["station"]]
        if abs(mine - ev) > 0.51 or abs(alts["naive DST-clock-midnight window (dayend-25h..dayend-1h)"] - ev) <= 0.51 or not dst:
            continue                                   # want: DST-season day where the skew WOULD have mattered
        k = int(np.argmax(sub[:, 1])) if e["kind"] == "max" else int(np.argmin(sub[:, 1]))
        seen.add(key)
        ex.append({"event": e["event"], "kind": e["kind"], "station": e["station"],
                   "close_time_listed_utc": e["close_time"], "settlement_day_end_utc": U(dend).isoformat(),
                   "day_window_utc": [U(dend - 86400).isoformat(), U(dend).isoformat()],
                   "day_window_local_wall_clock": [U(dend - 86400).astimezone(zi).isoformat(),
                                                   U(dend).astimezone(zi).isoformat()],
                   "local_utc_offset_in_effect_h": off, "n_obs_in_window": int(len(sub)),
                   "extreme_f": mine, "extreme_at_utc": U(int(sub[k, 0])).isoformat(),
                   "extreme_at_local_wall_clock": U(int(sub[k, 0])).astimezone(zi).isoformat(),
                   "kalshi_expiration_value": ev, "alternative_windows_extreme": alts})
        if len(ex) >= 3:
            break
    return {"examples": ex}


def obs_bias_full_universe():
    """Obs-only profile over the WHOLE universe (needs no candles): day extreme (1-minute, full-coverage days) minus
    Kalshi's official expiration_value, for the settlement-day window and two skewed windows."""
    uni = load_universe()
    store = ObsStore()
    res = collections.defaultdict(collections.Counter)
    for e in uni["events"]:
        try:
            ev = float(e["rungs"][0].get("expiration_value"))
        except Exception:
            continue
        arr = store._load(e["station"], "1min")
        dend = day_end(event_close_ts(e))
        i0, i1 = np.searchsorted(arr[:, 0], dend - 86400), np.searchsorted(arr[:, 0], dend)
        if i1 - i0 < 1435:
            continue
        fn = np.max if e["kind"] == "max" else np.min
        for tag, (x, y) in (("settlement_day[dayend-24h,dayend)", (dend - 86400, dend)),
                            ("dst_clock_midnight[dayend-25h,dayend-1h)", (dend - 90000, dend - 3600)),
                            ("shifted_later[dayend-23h,dayend+1h)", (dend - 82800, dend + 3600))):
            j0, j1 = np.searchsorted(arr[:, 0], x), np.searchsorted(arr[:, 0], y)
            d = float(fn(arr[j0:j1, 1])) - ev
            res[(tag, e["kind"])][int(max(-3, min(3, round(d))))] += 1
    out = {}
    for (tag, kind), c in res.items():
        n = sum(c.values())
        out[f"{tag}|{kind}"] = {"n": n, "diff_obs_minus_official_frac": {str(k): round(v / n, 4) for k, v in sorted(c.items())}}
    return out


def main_analyze():
    A = analyze()
    done, nU = A["done"], A["n_universe"]
    # ---- sampling ----
    src_cnt = collections.Counter()
    for e in done:
        src_cnt["live" if all(r["src"] == "live" for r in e["rungs"]) else "hist"] += 1
    src_all = collections.Counter("live" if all(r["src"] == "live" for r in e["rungs"]) else "hist"
                                  for e in A["events"])
    ser_done = collections.Counter(e["series"] for e in done)
    ser_all = collections.Counter(e["series"] for e in A["events"])
    sampling = {"seed": SEED, "method": "single seeded shuffle of ALL city-day events, never re-sorted; candles fetched "
                "in that order, so the fetched set is a uniform random subsample of the universe",
                "universe_events": nU, "universe_rungs": sum(len(e["rungs"]) for e in A["events"]),
                "events_with_candles": len(done), "fraction": len(done) / nU,
                "contiguous_prefix_of_work_order": A["first_missing"],
                "events_by_partition_done": dict(src_cnt), "events_by_partition_universe": dict(src_all),
                "series_covered": len(ser_done), "series_total": len(ser_all),
                "min_series_n": min(ser_done.values()) if ser_done else 0,
                "max_series_n": max(ser_done.values()) if ser_done else 0,
                "usable_events_after_obs_filter": sum(A["feed_counts"].values()),
                "design_weights_live_hist": A["DW"], "universe_by_stratum": A["N_s"], "fetched_by_stratum": A["n_s"],
                "skips": dict(A["skips"]), "feeds": dict(A["feed_counts"])}
    # ---- Part 1 ----
    grid = {}
    for G in GRID_G:
        for R in GRID_R:
            for W in GRID_W:
                fs = [f for f in A["fires"] if f["cell"] == (G, R, W)]
                grid[(G, R, W)] = {L: cell_stats(fs, L) for L in LAT}
    verdict1, v1 = part1_verdict(grid)
    prim = grid[(PRIMARY["G"], PRIMARY["R"], PRIMARY["W"])]
    over = {}
    for L in LAT:
        fs = [f for f in A["over_fires"] if f["cell"] == (PRIMARY["G"], PRIMARY["R"], PRIMARY["W"])]
        over[L] = cell_stats(fs, L)
    ecc = {k: entry_cost_classes([f for f in A["fires"] if f["cell"] == (PRIMARY["G"], PRIMARY["R"], PRIMARY["W"]) and
                                  (k == "all" or f["kind"] == k)], 10) for k in ("all", "max", "min")}
    cf = carry_forward_diag([f for f in A["fires"] if f["cell"] == (PRIMARY["G"], PRIMARY["R"], PRIMARY["W"])], 10)
    # ---- Part 2 ----
    p2 = {}
    p2_fires = {}
    for L in LAT:
        p2[L], p2_fires[L], _ = part2_stats(A["p2_days"], L)
    # Part 2 verdict
    s10 = p2[10]
    crit_fires = (s10.get("mean_fires_per_signalling_day") or 0) >= 3
    crit_ev = (s10.get("per_day_net_ev_c") or -9e9) >= 4.0
    crit_t = (min(s10.get("t_cityday", -9e9), s10.get("t_calday", -9e9)) >= max(s10.get("t_bar", 9e9), s10.get("t_bar_calday", 9e9)))
    numeric_ok = bool(crit_fires and crit_ev and crit_t)
    neg_sig = (s10.get("t_cityday", 0) <= -s10.get("t_bar", 9e9)) if s10.get("t_bar") else False
    if numeric_ok and verdict1 == "PASS":
        verdict2 = "PASS"
    elif numeric_ok:
        verdict2 = "NOT_EVALUABLE"      # numerics clear, but the Part1-or-TERMINAL precondition is unmet here
    elif neg_sig:
        verdict2 = "KILL"
    else:
        verdict2 = "INSUFFICIENT"
    # ---- anchors ----
    aA = anchor_a(A)
    aA2 = anchor_a_fires(A)
    tz = tz_worked_example(A)
    tz_rates = {}
    for tag in sorted({k[0] for k in A["tz_alt"]}):
        n_ = A["tz_alt"][(tag, "n")]
        tz_rates[tag] = {"n": n_, "match_expiration_value": A["tz_alt"][(tag, "match")],
                         "rate": A["tz_alt"][(tag, "match")] / n_ if n_ else None}
    val = {"n_by_feed": {k[1]: v for k, v in A["val"].items() if k[0] == "n"},
           "final_extreme_equals_expiration_value": {k[1]: v for k, v in A["val"].items() if k[0] == "match"},
           "within_1F": {k[1]: v for k, v in A["val"].items() if k[0] == "within1"}}
    anchors = {"a_oracle": aA, "a_fire_join": aA2,
               "obs_bias_full_universe": obs_bias_full_universe(),
               "b_no_lookahead": {"brute_force_prefix_events_checked": A["bf_checked"], "cells_checked": [[4, 2, 120], [2, 4, 60], [6, 2, 120]],
                                  "assert_result": "vectorised first-fire index/timestamp/E identical to prefix-only brute force on every checked (event, rung, cell)",
                                  "worked_example": A["worked"].get("b")},
               "c_monotonic": {"events_checked": sum(A["feed_counts"].values()), "violations": A["mono_viol"]},
               "tz_day_window_vs_expiration_value": tz_rates, "obs_vs_expiration_value": val,
               "tz_worked_examples": tz}
    # ---- package ----
    def cs(x):
        return json.loads(json.dumps(x, default=lambda o: None if (isinstance(o, float) and math.isnan(o)) else str(o)))
    out = {"spec": "venue_expansion/FINALITY_NO_LADDER_SPEC.md (frozen 2026-10-27)", "build": "B (independent)",
           "bars": {"n_comparisons": N_COMPARISONS, "alpha": ALPHA_BONF, "t_quantile_p": 1 - ALPHA_BONF / 2},
           "sampling": sampling,
           "part1": {"verdict": verdict1, "verdict_detail": v1,
                     "grid": {f"G={k[0]},R={k[1]},H={H_OBS},W={k[2]}": {f"L={L}": v for L, v in arms.items()}
                              for k, arms in grid.items()},
                     "primary_cell": {f"L={L}": v for L, v in prim.items()},
                     "overshoot_mirror_reference_primary_cell": {f"L={L}": v for L, v in over.items()},
                     "carry_forward_sensitivity_primary_L10_descriptive": cf,
                     "why_untradeable_primary_L10": ecc},
           "part2": {"verdict": verdict2, "numeric_criteria_L10": {"fires_per_day_ge_3": crit_fires, "per_day_net_ge_4c": crit_ev,
                                                                 "t_ge_bar": crit_t},
                     "arms": {f"L={L}": v for L, v in p2.items()}},
           "anchors": anchors}
    out = cs(out)
    json.dump(out, open(OUT_JSON, "w"), indent=1)
    write_md(out, A, grid, over, p2, verdict1, verdict2)
    print(json.dumps({"verdict1": verdict1, "verdict2": verdict2, "sampling": sampling}, indent=1, default=str))
    return out


def _f(x, d=2):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def write_md(out, A, grid, over, p2, v1, v2):
    L = []
    sp = out["sampling"]
    P = L.append
    prim = grid[(PRIMARY["G"], PRIMARY["R"], PRIMARY["W"])]
    p10 = prim[10]
    P("# FINALITY-NO + WHOLE-LADDER -- Build B (independent replication)\n")
    P("Spec: `FINALITY_NO_LADDER_SPEC.md` (frozen 2026-10-27; no bar moved). Code: `finality_no_B.py`. "
      "Numbers: `out/finality_no_B.json`. Written from the spec text; no finality_no_A / finality_A / finality_B file was read.\n")
    P("## Verdicts\n")
    P(f"- **Part 1 (FINAL-NO by never-arrival): {v1}**")
    P(f"- **Part 2 (whole-ladder): {v2}**\n")
    dws = sp["design_weights_live_hist"]
    P(f"**SAMPLING FRACTION: {sp['events_with_candles']:,} of {sp['universe_events']:,} city-day events "
      f"({100 * sp['fraction']:.1f}%) have candlesticks and enter the analysis; {sp['events_with_candles'] * 100 // sp['universe_events'] if False else ''}"
      f"LIVE partition (settled ~2026-08-21..10-20): {sp['fetched_by_stratum']['True']}/{sp['universe_by_stratum']['True']} = CENSUS; "
      f"HISTORICAL partition (2026-05-23..~08-20): {sp['fetched_by_stratum']['False']}/{sp['universe_by_stratum']['False']} = "
      f"{100 * sp['fetched_by_stratum']['False'] / sp['universe_by_stratum']['False']:.1f}% random sample.** "
      f"Why stratified: live events cost 1 batch request, historical events ~6 requests (no batch endpoint) at ~1 request/second with 429 backoff, "
      f"so a single uniform prefix could not cover the universe in one session. Within each stratum the work order is the seeded (seed {sp['seed']}) "
      f"shuffle and was NEVER re-sorted, so each stratum's fetched set is a uniform random subsample of that stratum "
      f"(work-order index of first un-fetched event overall: {sp['contiguous_prefix_of_work_order']}). To keep pooled estimates unbiased for the whole "
      f"universe every fire/day carries a stratified design weight N_h/n_h (live {dws['True']:.2f}, historical {dws['False']:.2f}); "
      f"ALL EVs and t-statistics below are design-weighted (and volume-weighted where labelled); counts (n, fires, k/N, Wilson) are raw. "
      f"Series covered {sp['series_covered']}/{sp['series_total']} (per-series n {sp['min_series_n']}..{sp['max_series_n']}). "
      f"Obs feed per usable event: {sp['feeds']}.\n")
    P("## Primary cell (G=4, R=2, H=3, W=120), L=10 -- the deployable arm\n")
    P("| metric | value |\n|---|---|")
    fa, fp = p10["false_lock_all"], p10["false_lock_priced"]
    P(f"| signalled FINAL-NO rung fires (never-arrival, any price) | {p10['n_fires']:,} over {p10['signalling_city_days']} city-days |")
    P(f"| priced fires (n) | {p10['n_priced']:,} over {p10.get('priced_city_days', 0)} city-days / "
      f"{p10.get('priced_calendar_days', 0)} calendar days / {p10.get('priced_stations', 0)} stations |")
    P(f"| false-lock, all fires | {fa['k']}/{fa['n']} = {_f(100 * fa['rate'], 2) if fa['n'] else 'n/a'}%, Wilson 95% UB "
      f"{_f(100 * fa['wilson_hi'], 2) if fa['n'] else 'n/a'}% ({p10['false_lock_city_days']} false-lock city-days) |")
    P(f"| false-lock, priced fires | {fp['k']}/{fp['n']}, Wilson 95% UB {_f(100 * fp['wilson_hi'], 2) if fp['n'] else 'n/a'}% |")
    if p10["n_priced"]:
        P(f"| EV/contract, volume-weighted, fee-inclusive | {_f(p10['vw_cityday']['ev_c'])}c (unweighted {_f(p10['ev_unweighted_c'])}c) |")
        P(f"| signed t, city-day clustered / calendar-day clustered | {_f(p10['vw_cityday']['t'])} (df {_f(p10['vw_cityday']['df'], 0)}) / "
          f"{_f(p10['vw_calday']['t'])} (df {_f(p10['vw_calday']['df'], 0)}); Bonferroni bar {_f(p10['vw_cityday']['t_bar'], 3)} |")
        P(f"| one-sided 97.9% UB on vw EV | {_f(p10['vw_cityday']['ub979'])}c |")
        P(f"| mean NO cost paid | {_f(p10['mean_cost_c'])}c |")
    P(f"| untradeable fraction | {_f(100 * p10['untradeable_frac'], 1)}% {p10['untradeable_reasons']} |")
    P("")
    P("## Part 1 grid (12 cells x 3 latency arms)\n")
    P("Columns: fires = signalled rung fires; n = priced; UT = untradeable %; FL = false-lock k/N all fires (Wilson UB %); "
      "EVvw / EVuw = volume-weighted / unweighted fee-inclusive EV in c per contract; t_cd / t_cal = signed t, city-day / calendar-day "
      "clusters; bar = exact Student-t Bonferroni (39 comparisons) at the realised df; days = priced calendar days; stn = priced stations; "
      "UB = one-sided 97.9% upper bound on EVvw.\n")
    P("| G | R | W | L | fires | n | UT% | FL | EVvw | EVuw | t_cd | t_cal | bar | days | stn | UB |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for (G, R, W), arms in sorted(grid.items()):
        for Lt in LAT:
            s_ = arms[Lt]
            if s_["n_priced"]:
                v, vc = s_["vw_cityday"], s_["vw_calday"]
                evs = (_f(v["ev_c"]), _f(s_["ev_unweighted_c"]), _f(v["t"]), _f(vc["t"]), _f(v["t_bar"]), _f(v["ub979"]))
            else:
                evs = ("n/a",) * 6
            fl = s_["false_lock_all"]
            P(f"| {G} | {R} | {W} | {Lt} | {s_['n_fires']} | {s_['n_priced']} | {_f(100 * s_['untradeable_frac'], 1) if s_['n_fires'] else 'n/a'} | "
              f"{fl['k']}/{fl['n']} ({_f(100 * fl['wilson_hi'], 1) if fl['n'] else 'n/a'}) | {evs[0]} | {evs[1]} | {evs[2]} | {evs[3]} | {evs[4]} | "
              f"{s_.get('priced_calendar_days', 0)} | {s_.get('priced_stations', 0)} | {evs[5]} |")
    P("")
    P(f"Part 1 verdict detail: `{json.dumps(out['part1']['verdict_detail'])}`\n")
    P("PASS needs ALL of (L=10, >=1 cell): false-lock <=2% with Wilson UB <=5% (required of BOTH all-fires and priced-fires); "
      "vw EV >= +2.0c; signed t >= the exact bar under BOTH city-day and calendar-day clustering (the smaller t must clear the larger bar); "
      "n>=100 across >=40 calendar days and >=10 stations; untradeable <=70%.\n")
    P("## Anchor (d): never-arrival vs overshoot reported separately\n")
    P("Part 1 fires are NEVER-ARRIVAL only (HIGH: E <= lo-G; LOW: E >= hi+G). The overshoot flavour is what the deployed rule "
      "already locks; here it is run through the identical timing/entry machinery as a mirror reference "
      "(HIGH: E >= hi+G; LOW: E <= lo-G; same R, H, W, same NO-entry rule) so the two are never pooled:\n")
    P("| flavour (primary cell) | L | fires | n priced | UT% | false-lock k/N | EVvw c | EVuw c | mean cost c |")
    P("|---|---|---|---|---|---|---|---|---|")
    for nm, g in (("never-arrival (the new finding)", prim), ("overshoot (mirror; already deployed shape)", over)):
        for Lt in LAT:
            s_ = g[Lt]
            P(f"| {nm} | {Lt} | {s_['n_fires']} | {s_['n_priced']} | {_f(100 * s_['untradeable_frac'], 1) if s_['n_fires'] else 'n/a'} | "
              f"{s_['false_lock_all']['k']}/{s_['false_lock_all']['n']} | "
              f"{_f(s_['vw_cityday']['ev_c']) if s_['n_priced'] else 'n/a'} | {_f(s_.get('ev_unweighted_c')) if s_['n_priced'] else 'n/a'} | "
              f"{_f(s_.get('mean_cost_c')) if s_['n_priced'] else 'n/a'} |")
    P("")
    pv = prim[10]
    P(f"**Reading the primary cell.** Only {pv['n_priced']} of {pv['n_fires']} never-arrival fires ever offer NO at <=98c with positive net "
      f"({_f(100 * (1 - pv['untradeable_frac']), 2)}%): on {out['part1']['why_untradeable_primary_L10']['all']} (all / HIGH: {out['part1']['why_untradeable_primary_L10']['max']} / LOW: {out['part1']['why_untradeable_primary_L10']['min']}). "
      f"The dead rungs simply have no YES bid (NO costs 100c) -- there is no discount to buy. "
      f"The false-lock rate over ALL fires is {_f(100 * pv['false_lock_all']['rate'], 2)}% but over the PRICED fires it is "
      f"{pv['false_lock_priced']['k']}/{pv['false_lock_priced']['n']} (Wilson UB {_f(100 * pv['false_lock_priced']['wilson_hi'], 1)}%): the minutes at which NO is "
      f"actually cheap are exactly the minutes the book disagrees with the obs-only inference -- adverse selection. The volume-weighted EV "
      f"({_f(pv['vw_cityday']['ev_c'])}c) and the volume-unweighted design-weighted EV ({_f(pv['ev_unweighted_c'])}c; raw mean {_f(pv['ev_raw_mean_c'])}c) "
      f"have opposite signs because a handful of high-volume cheap-NO winners dominate the volume weights while the two false-locks (-94c each) "
      f"dominate the unweighted mean; neither estimate clears its bar. Every priced primary-cell fire is a LOW market (see the HIGH split below: zero priced).\n")
    # descriptive splits of the primary cell
    P("### Primary cell, descriptive splits (L=10; not part of the frozen comparisons)\n")
    P("| split | fires | n priced | false-lock k/N | EVuw c |")
    P("|---|---|---|---|---|")
    pf = [f for f in A["fires"] if f["cell"] == (PRIMARY["G"], PRIMARY["R"], PRIMARY["W"])]
    for nm, sel in (("1-minute feed", lambda f: f["feed"] == "1min"), ("routine feed", lambda f: f["feed"] == "routine"),
                    ("HIGH markets", lambda f: f["kind"] == "max"), ("LOW markets", lambda f: f["kind"] == "min")):
        s_ = cell_stats([f for f in pf if sel(f)], 10)
        P(f"| {nm} | {s_['n_fires']} | {s_['n_priced']} | {s_['false_lock_all']['k']}/{s_['false_lock_all']['n']} | "
          f"{_f(s_.get('ev_unweighted_c')) if s_['n_priced'] else 'n/a'} |")
    P("")
    P("## Part 2 -- whole ladder from one inference\n")
    P("Definition used (the spec leaves it to the builder): a city-day is *signalling* when either primary-cell finality signal fires on any "
      "bracket rung of an event -- FINAL-NO (G=4,R=2,H=3,W=120) or the companion FINAL-YES (M=1.0,R=2,H=3,W=120) -- at the earliest such obs time t*. "
      "The inferred settlement value is X^ = round(E(t*)); the inferred winner is the unique rung (brackets AND the two tail T-rungs, "
      "which complete the partition) containing X^; every other rung is an inferred loser. Winner -> buy YES at yes_ask; "
      "every loser -> buy NO at 100 - yes_bid; each gated independently on first candle >= t*+L with cost <=98c and net >0. "
      "A city-day = (station, local date); HIGH and LOW ladders of the same city-day are pooled (conservative). "
      "Days with no priced fire count as 0 net in the per-day mean.\n")
    P("| L | signalling city-days | rung evals | priced fires | fires / signalling day | fires / day with >=1 fire | per-day net EV c | SE | t (city-day) | t (calendar) | bar | UB97.9 | wrong-inference ladders |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for Lt in LAT:
        s_ = p2[Lt]
        P(f"| {Lt} | {s_['signalling_city_days']} | {s_['n_rung_evals']} | {s_['n_priced_fires']} | {_f(s_['mean_fires_per_signalling_day'])} | "
          f"{_f(s_['mean_fires_per_day_with_any_fire'])} | {_f(s_.get('per_day_net_ev_c'))} | {_f(s_.get('per_day_net_se'))} | "
          f"{_f(s_.get('t_cityday'))} | {_f(s_.get('t_calday'))} | {_f(s_.get('t_bar'), 3)} | {_f(s_.get('ub979'))} | "
          f"{_f(100 * s_['wrong_inference_ladder_frac'], 1) if 'wrong_inference_ladder_frac' in s_ else 'n/a'}% |")
    P("")
    s10 = p2[10]
    P(f"Part 2 PASS criteria at L=10: fires/signalling-day >= 3 -> {out['part2']['numeric_criteria_L10']['fires_per_day_ge_3']}; "
      f"per-day net >= +4.0c -> {out['part2']['numeric_criteria_L10']['per_day_net_ge_4c']}; t >= bar -> "
      f"{out['part2']['numeric_criteria_L10']['t_ge_bar']}; and Part 1 PASS (companion TERMINAL result not visible to this build) -> {v1 == 'PASS'}.\n")
    P("### EV by |distance from the inferred extreme| in rungs (L=10; 0 = the inferred winner rung)\n")
    P("| |d| | priced / evaluated | EV c (unweighted) | SE (city-day) | win % | mean cost c |")
    P("|---|---|---|---|---|---|")
    for k_, g in s10["by_abs_distance"].items():
        if g["n"]:
            P(f"| {k_} | {g['n']} / {g['of_evaluated']} | {_f(g['ev_c'])} | {_f(g['se_cityday'])} | {_f(100 * g['win_rate'], 1)} | {_f(g['mean_cost_c'], 1)} |")
        else:
            P(f"| {k_} | 0 | n/a | n/a | n/a | n/a |")
    P("")
    P("### By flavour (L=10): winner / never-arrival loser / overshoot loser\n")
    P("| flavour | priced / evaluated | EV c | SE | win % | mean cost c |")
    P("|---|---|---|---|---|---|")
    for k_, g in s10["by_flavour"].items():
        if g["n"]:
            P(f"| {k_} | {g['n']} / {g['of_evaluated']} | {_f(g['ev_c'])} | {_f(g['se_cityday'])} | {_f(100 * g['win_rate'], 1)} | {_f(g['mean_cost_c'], 1)} |")
        else:
            P(f"| {k_} | 0 | n/a | n/a | n/a | n/a |")
    P("")
    if "xhat_vs_official_exact_frac" in s10:
        P(f"Inference quality: round(E(t*)) equals Kalshi's official expiration_value on {_f(100 * s10['xhat_vs_official_exact_frac'], 1)}% of ladders "
          f"({_f(100 * s10['xhat_vs_official_within1_frac'], 1)}% within 1F). A ladder is 'wrong' if ANY of its fires would lose "
          f"(winner settled NO or a loser settled YES): {_f(100 * s10['wrong_inference_ladder_frac'], 1)}% of signalling ladders. "
          "One wrong inference loses the whole day's basket -- hence city-day clustering above.\n")
    P("## Sanity anchors\n")
    an = out["anchors"]
    aa = an["a_oracle"]["oracle_top40_reproduction"]
    P("### (a) Oracle reconciliation\n")
    P(f"- Price-join reproduction of `edge_sizing_v2.json`'s 40 highest-net capturable markets, recomputed from MY candles with the "
      f"Stage-1 definition (final 60 min, winner side, <=98c, net>0): events fetched {aa['events_available']}/{aa['of']}; "
      f"best winner cost matches {aa['best_cost_match']}, best net matches {aa['best_net_match']}, still capturable {aa['capturable_match']}, "
      f"n_data_minutes within 1: {aa['n_data_minutes_within_1']}.")
    pr_ = an["a_oracle"]["population_rate_in_oracle_window"]
    P(f"- Population capturable rate on my sample inside the oracle's window (close < 2026-08-05): {pr_['capturable']}/{pr_['rungs_with_candles']} = "
      f"{_f(100 * pr_['rate'], 1) if pr_['rate'] is not None else 'n/a'}% vs oracle {pr_['oracle_reference_rate']}.")
    af = an["a_fire_join"]
    P(f"- Fire-level join check (primary cell, L=10): {af['priced_primary_L10_fires_checked']} priced fires; every NO cost equals 100 - the entry "
      f"candle's yes_bid; {af['correct_NO_entries_in_oracle_window']} correct-NO entries inside the oracle's final-60-minute window all re-derive "
      f"as oracle-capturable; join violations = {af['join_violations']}.")
    P("- Limit, disclosed: the oracle JSON stores only its top-40 capturable detail (the 140-market list and the sampled-market list are not in the "
      "repo; `cache/edge_sizing/` is absent), so the literal subset test (fires subset-of oracle set) is only checkable on that top-40 and by the "
      "rederivation above -- not against the full 140.\n")
    P("### (b) No look-ahead\n")
    bb = an["b_no_lookahead"]
    P(f"- Every obs used for a fire at signal time t has timestamp strictly < t (t = newest obs ts + 60 s; asserted in the vectorised walk "
      f"and in `part1_fire_bruteforce`, which hands the signal ONLY a copied prefix). The vectorised engine and the brute-force prefix engine "
      f"were asserted identical (fire index, timestamp, E) on {bb['brute_force_prefix_events_checked']} events x all bracket rungs x 3 cells.")
    if bb.get("worked_example"):
        w = bb["worked_example"]
        P(f"- Worked example: `{w['ticker']}` cell G,R,W={w['cell']}, rung [{w['lo']:.0f},{w['hi']:.0f}]. Fire at obs #{w['fire_obs_index']} "
          f"(ts {w['fire_obs_ts_utc']}); signal ts {w['signal_ts_utc']}; running extreme E={w['E_at_fire']}; last H=3 obs {w['last_H_obs']}; "
          f"prefix used = {w['n_obs_in_prefix']} of {w['n_obs_in_full_day']} obs of the day; all prefix obs older than the signal ts: "
          f"{w['max_prefix_obs_ts_lt_signal_ts']}.\n")
    P("### (c) Monotonicity\n")
    P(f"- Running max non-decreasing / running min non-increasing: {an['c_monotonic']['violations']} violations in "
      f"{an['c_monotonic']['events_checked']} event-days. Day window asserted: all obs in [dayend-24h, dayend), strictly increasing ts.\n")
    P("## Timezone proof\n")
    P("The running extreme is taken over the station's LOCAL STANDARD-TIME calendar day. Kalshi `close_time` is local standard-time midnight "
      "(05:00Z for NYC all year in the live partition, 04:59Z in the historical partition -> rounded up to the hour), so the day is "
      "`[dayend-24h, dayend)` in UTC and during daylight-saving time that is 01:00 -> 01:00 on the local wall clock. IEM obs are requested with "
      "`tz=UTC` and candlestick `end_period_ts` is a UTC epoch, so all three clocks are epoch seconds and no local conversion enters the signal. "
      "Worked examples (selected only by: full 1-minute coverage, a DST-season date, and the naive DST-clock-midnight window disagreeing with Kalshi's official value while the settlement-day window agrees):\n")
    for e in an["tz_worked_examples"]["examples"]:
        P(f"- `{e['event']}` ({e['kind']}, {e['station']}): listed close {e['close_time_listed_utc']}; window UTC "
          f"{e['day_window_utc'][0]} .. {e['day_window_utc'][1]} = local wall clock {e['day_window_local_wall_clock'][0]} .. "
          f"{e['day_window_local_wall_clock'][1]} (UTC{e['local_utc_offset_in_effect_h']:+.0f}); {e['n_obs_in_window']} obs; extreme "
          f"{e['extreme_f']} at {e['extreme_at_utc']} UTC = {e['extreme_at_local_wall_clock']}; Kalshi expiration_value "
          f"**{e['kalshi_expiration_value']}**; skewed windows would have given {e['alternative_windows_extreme']}.")
    P("")
    P("Aggregate check on every usable event-day of the SAMPLE (extreme of the window == Kalshi `expiration_value` to within 0.5F):\n")
    P("| window | n | exact match |\n|---|---|---|")
    for k_, g in an["tz_day_window_vs_expiration_value"].items():
        P(f"| {k_} | {g['n']} | {g['match_expiration_value']} ({_f(100 * g['rate'], 1)}%) |")
    P("")
    P(f"Feed-level: {an['obs_vs_expiration_value']}\n")
    P("Note: the IEM 1-minute HIGH extreme sits 1F ABOVE the official value on roughly half of days (official Weather Company values are lower than the "
      "1-minute ASOS max); LOW matches to within 1F >99%. Full-universe obs-only profile is in the json (`obs_bias_full_universe`).\n")
    P("## Interpretation choices (spec silent; fixed BEFORE any outcome was read, never tuned)\n")
    for x in (
        "Bracket win set = integer settlement X in [floor_strike, cap_strike] inclusive (verified against official result + expiration_value); "
        "T 'greater f' = X >= f+1; T 'less c' = X <= c-1. Part 1 uses '-B' rungs only; Part 2 uses all rungs (partition).",
        "Obs-only signal time t = (newest obs ts)+60s so every obs used is strictly older than t; window test t in [dayend-W, dayend]; latency L shifts t before seeking entry.",
        "'Reversed and held' = the last H=3 obs ALL lie >= R away from the running extreme at the newest obs.",
        "Entry candle = first candle with end_period_ts >= t+L, cost <=98c, net>0; only printed candles are used (candlesticks are sparse; absent minutes are never back-filled).",
        "Volume weight = entry-candle volume (zero-volume entries carry zero weight in vw EV; unweighted EV reported alongside).",
        "Day-clustered t: SE is CR1 cluster-robust; PASS requires the smaller of {city-day (station,date), calendar-date} t to clear the larger of the two exact Bonferroni bars. UB (KILL) uses the city-day clustering.",
        "Feed: IEM 1-minute if the day has >=1150 obs and >=110 obs in the last 130 min, else routine (disclosed per event; split reported). Physical-bounds glitch filter only (-60..135F).",
        "Part 2 day signal / winner inference as in the Part 2 section. The TERMINAL-spec pass precondition cannot be observed from this build.",
        "Part 2 skips ladders whose official results are not exactly-one-YES (count in json `skips`).",
        "`edge_sizing_v2.normalize()` is reused with its WINDOW_MIN global set to 150 (it hard-filters to the final WINDOW_MIN minutes; the default 60 would silently drop W=120 entries). "
        "The historical-partition candlestick schema uses bare keys (`close`, `volume`); a key-name-only shim maps them to the `*_dollars` names normalize() reads -- no value is altered.",
    ):
        P(f"- {x}")
    P("")
    P(f"Skips: {json.dumps(sp['skips'])}\n")
    P("Reproduce: `python3 venue_expansion/finality_no_B.py discover && ... obs && ... candles && ... oracle && ... analyze`.\n")
    open(OUT_MD, "w").write("\n".join(L))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "discover":
        discover()
    elif cmd == "obs":
        obs()
    elif cmd == "candles":
        candles(int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9, sys.argv[3] if len(sys.argv) > 3 else "all")
    elif cmd == "oracle":
        oracle_fetch()
    elif cmd == "analyze":
        main_analyze()
    else:
        print(__doc__)
