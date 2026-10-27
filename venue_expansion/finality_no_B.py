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
                time.sleep(min(90, 3 * 2 ** i))
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


def fetch_event_candles(e, back_min=CANDLE_BACK_MIN):
    """Live rungs: ONE batch call per event.  Historical rungs (settled before the 2026-08-28 cutoff and not
    in the live listing): one /historical/markets/{ticker}/candlesticks call per rung.  Raw responses are
    cached verbatim with a per-market fmt flag ('live' = *_dollars schema, 'hist' = bare schema)."""
    path = os.path.join(CND_DIR, e["event"] + ".json")
    if os.path.exists(path):
        return True
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


def candles(max_events=10 ** 9):
    uni = load_universe()
    n = 0
    t0 = time.time()
    for i, e in enumerate(uni["events"]):        # shuffled order, never re-sorted
        if n >= max_events:
            break
        if os.path.exists(os.path.join(CND_DIR, e["event"] + ".json")):
            continue
        try:
            fetch_event_candles(e)
        except Exception as ex:                  # disclosed; the event is simply retried on the next run
            print("  fetch error", e["event"], ex, flush=True)
            continue
        n += 1
        if n % 100 == 0:
            print(f"  {n} events fetched this run (work-order idx {i}/{len(uni['events'])}) "
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
        fetch_event_candles(e)


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
    """rev[k] True iff obs k-H+1..k ALL lie >= R degrees away from the running extreme at k (HIGH: <= E-R,
    LOW: >= E+R).  Uses only obs 0..k -> no look-ahead by construction (checked by brute force below)."""
    n = len(f)
    rev = np.zeros(n, dtype=bool)
    if n < H:
        return rev
    away = (f <= E - R) if kind == "max" else (f >= E + R)
    # away[j] uses E at k, not at j, so evaluate per-k with a rolling window over raw values:
    for k in range(H - 1, n):
        w = f[k - H + 1:k + 1]
        if kind == "max":
            rev[k] = bool(np.all(w <= E[k] - R))
        else:
            rev[k] = bool(np.all(w >= E[k] + R))
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


def load_event_candles(e):
    path = os.path.join(CND_DIR, e["event"] + ".json")
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
    return mu, se, (mu / se if se > 0 else float("nan")), G - 1.0, G


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
        assert ts.min() >= close - 86400 and ts.max() < close and (np.diff(ts) > 0).all()
        # tz / day-window validation against Kalshi's official expiration_value
        ev = e["rungs"][0].get("expiration_value")
        try:
            evf = float(ev)
        except Exception:
            evf = None
        if evf is not None:
            arr = store._load(e["station"], "1min") if feed == "1min" else store._load(e["station"], "routine")
            ext = (np.max if kind == "max" else np.min)
            for tag, (a, b) in (("lst_midnight(close-24h..close)", (close - 86400, close)),
                                ("edt_midnight(close-25h..close-1h)", (close - 90000, close - 3600)),
                                ("utc_calendar_day", (None, None))):
                if a is None:
                    cd = dt.datetime.fromtimestamp(close - 43200, tz=dt.timezone.utc).replace(hour=0, minute=0, second=0)
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

        dkey = (e["station"], date_from_event(e["event"]).isoformat())
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
                E, t, ks = signal_times(ts, f, kind, R, H_OBS, W, close)
                for G in GRID_G:
                    for r in rungs:
                        if r["type"] != "B":
                            continue
                        k = part1_fire(E, t, ks, kind, r["lo"], r["hi"], G, "never")
                        if k is not None:
                            fires.append({"ev": e["event"], "dkey": dkey, "stn": e["station"], "kind": kind,
                                          "tk": r["ticker"], "cell": (G, R, W), "t": int(t[k]), "E": float(E[k]),
                                          "res": r["result"], "feed": feed, "rows": r["rows"], "close": close,
                                          "flav": "never"})
                        # overshoot-mirror reference (anchor d): same shape/timing, other side of the bracket
                        k2 = part1_fire(E, t, ks, kind, r["lo"], r["hi"], G, "over")
                        if k2 is not None:
                            over_fires.append({"ev": e["event"], "dkey": dkey, "stn": e["station"], "kind": kind,
                                               "tk": r["ticker"], "cell": (G, R, W), "t": int(t[k2]),
                                               "E": float(E[k2]), "res": r["result"], "feed": feed,
                                               "rows": r["rows"], "close": close, "flav": "overshoot"})
        # ---- anchor (b): brute-force prefix-only implementation agrees with the vectorised one ----
        if sample_check and (hash(e["event"]) % 40 == 0) and bf_checked < 150:
            bf_checked += 1
            for (G, R, W) in ((4, 2, 120), (2, 4, 60), (6, 2, 120)):
                E, t, ks = signal_times(ts, f, kind, R, H_OBS, W, close)
                for r in rungs:
                    if r["type"] != "B":
                        continue
                    k = part1_fire(E, t, ks, kind, r["lo"], r["hi"], G, "never")
                    bf = part1_fire_bruteforce(ts, f, kind, r["lo"], r["hi"], G, R, H_OBS, W, close)
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
        if part_ok and not any(r["type"] == "T" and False for r in rungs):
            E2, t2, ks2 = signal_times(ts, f, kind, PRIMARY["R"], H_OBS, PRIMARY["W"], close)
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
                                    "E": Ek, "xhat": xhat, "wi": wi, "close": close, "feed": feed,
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
                mono_viol=mono_viol, worked=worked, n_universe=n_universe, stations_seen=stations_seen,
                bf_checked=bf_checked)


# ----- pricing a set of fires under a latency arm -----
def price_fires(fires, L, side="no"):
    out = []
    for fr in fires:
        got = first_entry(fr["rows"], side, fr["t"] + L * 60)
        rec = {"dkey": fr["dkey"], "stn": fr["stn"], "res": fr["res"], "ev": fr["ev"], "tk": fr["tk"],
               "cell": fr["cell"], "priced": got is not None}
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
           "false_lock_all": {"k": false_all, "n": n_fire, "rate": fl_all[0], "wilson_lo": fl_all[1], "wilson_hi": fl_all[2]},
           "false_lock_priced": {"k": false_pr, "n": n_pr, "rate": fl_pr[0], "wilson_lo": fl_pr[1], "wilson_hi": fl_pr[2]},
           "false_lock_city_days": len({p["dkey"] for p in pr if p["res"] == "yes"}),
           "signalling_city_days": len({p["dkey"] for p in pr}),
           "priced_city_days": len({p["dkey"] for p in pp}),
           "priced_calendar_days": len({p["dkey"][1] for p in pp}),
           "priced_stations": len({p["stn"] for p in pp})}
    if n_pr:
        x = np.array([p["pnl"] for p in pp], float)
        v = np.array([p["vol"] for p in pp], float)
        res["win_rate_priced"] = float(np.mean([p["res"] == "no" for p in pp]))
        res["mean_cost_c"] = float(np.mean([p["cost"] for p in pp]))
        res["ev_unweighted_c"] = float(x.mean())
        for tag, key in (("cityday", lambda p: p["dkey"]), ("calday", lambda p: p["dkey"][1])):
            cl = [key(p) for p in pp]
            mu, se, t, df, g = cluster_stat(x, v, cl)
            mu_u, se_u, t_u, df_u, _ = cluster_stat(x, np.ones_like(x), cl)
            res["vw_" + tag] = {"ev_c": mu, "se": se, "t": t, "df": df, "clusters": g,
                                "t_bar": t_bar(df), "ub979": (mu + t_ub(df) * se) if df else None}
            res["uw_" + tag] = {"ev_c": mu_u, "se": se_u, "t": t_u, "df": df_u, "clusters": g,
                                "t_bar": t_bar(df_u), "ub979": (mu_u + t_ub(df_u) * se_u) if df_u else None}
        res["vol_total"] = float(v.sum())
        res["n_zero_volume_entry"] = int((v <= 0).sum())
    return res


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
    fires, days = [], []
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
                   "res": r["res"], "priced": got is not None}
            if got:
                ts, cost, fee, vol = got
                won = (r["res"] == "yes") if side == "yes" else (r["res"] == "no")
                rec.update({"cost": cost, "fee": fee, "vol": vol, "pnl": (100 - cost - fee) if won else (-cost - fee)})
            fires.append(rec)
            day_fires.append(rec)
        priced = [x for x in day_fires if x["priced"]]
        wrong = any((x["side"] == "yes" and x["res"] == "no") or (x["side"] == "no" and x["res"] == "yes")
                    for x in day_fires)
        days.append({"dkey": d["dkey"], "n_rungs": len(day_fires), "n_priced": len(priced),
                     "net": float(sum(x["pnl"] for x in priced)), "wrong_inference": wrong,
                     "xhat": d["xhat"], "xofficial": d["xofficial"]})
    return fires, days


def part2_stats(p2_days, L):
    fires, days = part2_price(p2_days, L)
    nd = len(days)
    pr = [x for x in fires if x["priced"]]
    res = {"signalling_city_days": nd, "n_rung_evals": len(fires), "n_priced_fires": len(pr),
           "mean_fires_per_signalling_day": len(pr) / nd if nd else None,
           "mean_fires_per_day_with_any_fire": (len(pr) / max(1, sum(1 for d in days if d["n_priced"] > 0))),
           "days_with_any_priced_fire": sum(1 for d in days if d["n_priced"] > 0),
           "untradeable_frac": 1 - len(pr) / len(fires) if fires else None}
    if nd > 1:
        nets = np.array([d["net"] for d in days])
        sd = nets.std(ddof=1)
        se = sd / math.sqrt(nd)
        t = nets.mean() / se if se > 0 else float("nan")
        res.update({"per_day_net_ev_c": float(nets.mean()), "per_day_net_se": float(se), "t_cityday": float(t),
                    "df": nd - 1, "t_bar": t_bar(nd - 1), "ub979": float(nets.mean() + t_ub(nd - 1) * se)})
        # calendar-day cluster (sum nets across cities on the same date)
        bydate = collections.defaultdict(float)
        for d in days:
            bydate[d["dkey"][1]] += d["net"]
        # per-city-day mean with calendar-date clusters: cluster-robust on day-level residuals
        dates = [d["dkey"][1] for d in days]
        mu, se_c, t_c, df_c, g = cluster_stat(nets, np.ones_like(nets), dates)
        res.update({"t_calday": t_c, "df_calday": df_c, "t_bar_calday": t_bar(df_c)})
        res["wrong_inference_day_frac"] = float(np.mean([d["wrong_inference"] for d in days]))
        res["xhat_vs_official_exact_frac"] = float(np.mean([d["xofficial"] is not None and abs(d["xhat"] - d["xofficial"]) < 0.51
                                                            for d in days]))
    # EV by |distance| in rungs and by flavour
    def agg(sel):
        s = [x for x in pr if sel(x)]
        if not s:
            return {"n": 0}
        x = np.array([a["pnl"] for a in s], float)
        v = np.array([a["vol"] for a in s], float)
        mu, se, t, df, g = cluster_stat(x, np.ones_like(x), [a["dkey"] for a in s])
        n_all = sum(1 for a in fires if sel(a))
        return {"n": len(s), "of_evaluated": n_all, "ev_c": float(x.mean()), "se_cityday": se, "t_cityday": t,
                "win_rate": float(np.mean([(a["res"] == "yes") == (a["side"] == "yes") for a in s])),
                "mean_cost_c": float(np.mean([a["cost"] for a in s]))}
    res["by_abs_distance"] = {str(dd): agg(lambda a, dd=dd: a["dist"] == dd) for dd in range(0, 4)}
    res["by_abs_distance"]["4+"] = agg(lambda a: a["dist"] >= 4)
    res["by_flavour"] = {fl: agg(lambda a, fl=fl: a["flav"] == fl) for fl in ("winner", "never", "overshoot")}
    res["by_side"] = {sd: agg(lambda a, sd=sd: a["side"] == sd) for sd in ("yes", "no")}
    return res, fires, days


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "discover":
        discover()
    elif cmd == "obs":
        obs()
    elif cmd == "candles":
        candles(int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9)
    elif cmd == "oracle":
        oracle_fetch()
    elif cmd == "analyze":
        import finality_no_B_report as RPT  # noqa: F401  (report writer lives below via main_analyze)
    else:
        print(__doc__)
