#!/usr/bin/env python3
"""finality_B.py -- BUILD B (independent replication) of TERMINAL_FINALITY_SPEC.md.

Frozen spec executed as written; every interpretation choice is documented inline and in
out/finality_B.md.  Stages (all resumable, all cached under cache/finality/):
  discover  -> settled KXHIGH*/KXLOWT* markets per series (Kalshi, cursor paginated)
  obs       -> IEM 1-minute (asos1min.py) + routine (asos.py rt 3&4) per station, chunked
  signal    -> obs-only FINAL-YES walk for ALL universe bracket rungs x 8 cells (no prices touched)
  candles   -> 1-min candlesticks for fired rungs only (shuffled, seeded work order, never re-sorted)
  analyze   -> entry, P&L, stats, anchors, JSON/MD
Only edge_sizing_v2.normalize() is reused from the other code on disk.
"""
from __future__ import annotations
import collections, datetime as dt, json, math, os, random, sys, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import edge_sizing_v2 as V2   # ONLY normalize() is used (spec-sanctioned)

CACHE = os.path.join(HERE, "cache", "finality", "B")   # own namespace: build A shares cache/finality/
MKT = os.path.join(CACHE, "markets")
OBS = os.path.join(CACHE, "obs")
CAND = os.path.join(CACHE, "candles")
OUT_JSON = os.path.join(HERE, "out", "finality_B.json")
OUT_MD = os.path.join(HERE, "out", "finality_B.md")
API = "https://api.elections.kalshi.com/trade-api/v2"
IEM1 = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
IEMR = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
SEED = 20261027
WIN_START = dt.datetime(2026, 5, 23, tzinfo=dt.timezone.utc)
WIN_END = dt.datetime(2026, 10, 21, tzinfo=dt.timezone.utc)   # exclusive => closes through 2026-10-20 inclusive

# frozen grid
MS, RS, HS, WS, LS = (0.5, 1.0), (2.0, 4.0), (3,), (60, 120), (0, 10, 20)
CELLS = [(M, R, H, W) for M in MS for R in RS for H in HS for W in WS]
PRIMARY = (1.0, 2.0, 3, 120)

_last = [0.0]
def _polite(gap=1.0):
    d = time.time() - _last[0]
    if d < gap:
        time.sleep(gap - d)
    _last[0] = time.time()

def http(url, tries=5, text=False, gap=1.0, timeout=60):
    for i in range(tries):
        _polite(gap)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "finality-B-research/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as fh:
                raw = fh.read().decode("utf-8", "replace")
            return raw if text else json.loads(raw)
        except Exception as e:
            code = getattr(e, "code", None)
            if code in (400, 404, 422):
                raise
            if i == tries - 1:
                raise
            time.sleep(min(60, 2 ** (i + 1)))

def jload(p):
    with open(p) as fh:
        return json.load(fh)

def jdump(o, p):
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(o, fh)
    os.replace(tmp, p)

def iso2ts(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())

# ----------------------------------------------------------------------------- discovery
def list_series():
    p = os.path.join(CACHE, "series_list.json")
    if os.path.exists(p):
        return jload(p)
    d = http(API + "/series?category=Climate%20and%20Weather")
    t = sorted(x["ticker"] for x in d.get("series", []) if x["ticker"].startswith(("KXHIGH", "KXLOWT")))
    jdump(t, p)
    return t

def discover_series(series):
    p = os.path.join(MKT, series + ".json")
    if os.path.exists(p):
        return jload(p)
    out, cur = [], None
    while True:
        u = f"{API}/markets?series_ticker={series}&status=settled&limit=1000" + (f"&cursor={cur}" if cur else "")
        d = http(u)
        out.extend(d.get("markets", []))
        cur = d.get("cursor")
        if not cur or not d.get("markets"):
            break
    keep = ["ticker", "event_ticker", "series_ticker", "strike_type", "floor_strike", "cap_strike", "result",
            "close_time", "open_time", "expiration_value", "status", "can_close_early", "occurrence_datetime",
            "expiration_time", "custom_strike", "volume_fp", "volume"]
    slim = [{k: m.get(k) for k in keep} for m in out]
    jdump(slim, p)
    return slim

def cmd_discover():
    ser = list_series()
    print(len(ser), "series")
    for s in ser:
        ms = discover_series(s)
        print(s, len(ms), flush=True)

KEEP = ["ticker", "event_ticker", "series_ticker", "strike_type", "floor_strike", "cap_strike", "result",
        "close_time", "open_time", "expiration_value", "status", "can_close_early", "volume_fp", "volume"]

def discover_hist(series):
    """Markets settled before Kalshi's historical cutoff are NOT served by /markets; they live under
    /historical/markets.  Merge both sources (dedupe by ticker, keep the row that has a result)."""
    p = os.path.join(CACHE, "markets_hist", series + ".json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p):
        return jload(p)
    out, cur = [], None
    while True:
        u = f"{API}/historical/markets?series_ticker={series}&limit=1000" + (f"&cursor={cur}" if cur else "")
        d = http(u)
        out.extend(d.get("markets", []))
        cur = d.get("cursor")
        if not cur or not d.get("markets"):
            break
    slim = [{k: m.get(k) for k in KEEP} for m in out]
    jdump(slim, p)
    return slim

def cmd_discover_hist(only_mapped=True):
    for s in list_series():
        if only_mapped and s not in SERIES_MAP:
            continue
        print(s, len(discover_hist(s)), flush=True)

# ----------------------------------------------------------------------------- station map
# series -> (IEM station id, standard-time UTC offset hours).  Standard offsets are cross-checked
# against the empirical close_time hour of every series in `cmd_tzcheck` (an assertion, not trust).
HIGH_MAP = {
    "KXHIGHAUS": ("AUS", -6), "KXHIGHCHI": ("MDW", -6), "KXHIGHDEN": ("DEN", -7), "KXHIGHLAX": ("LAX", -8),
    "KXHIGHMIA": ("MIA", -5), "KXHIGHNY": ("NYC", -5), "KXHIGHPHIL": ("PHL", -5), "KXHIGHTATL": ("ATL", -5),
    "KXHIGHTBOS": ("BOS", -5), "KXHIGHTDAL": ("DFW", -6), "KXHIGHTDC": ("DCA", -5), "KXHIGHTHOU": ("HOU", -6),
    "KXHIGHTLV": ("LAS", -8), "KXHIGHTMIN": ("MSP", -6), "KXHIGHTNOLA": ("MSY", -6), "KXHIGHTOKC": ("OKC", -6),
    "KXHIGHTPHX": ("PHX", -7), "KXHIGHTSATX": ("SAT", -6), "KXHIGHTSEA": ("SEA", -8), "KXHIGHTSFO": ("SFO", -8),
}
SERIES_MAP = {}
for _h, (_st, _off) in HIGH_MAP.items():
    SERIES_MAP[_h] = (_st, _off, "max")
    SERIES_MAP[_h.replace("KXHIGHT", "KXLOWT", 1) if _h.startswith("KXHIGHT") else _h.replace("KXHIGH", "KXLOWT", 1)] = (_st, _off, "min")
for _h, _st, _off in (("EWR", "EWR", -5), ("SAN", "SAN", -8), ("SDF", "SDF", -5), ("TTN", "TTN", -5)):
    SERIES_MAP["KXHIGHT" + _h] = (_st, _off, "max")      # US stations added after the first catalog review
    SERIES_MAP["KXLOWT" + _h] = (_st, _off, "min")       # (close-hour check in cmd_tzcheck confirms offsets)
# KXHIGHTBOS->KXLOWTBOS ok; KXHIGHTDC->KXLOWTDC ok; KXHIGHNY->KXLOWTNY (wrong; real is KXLOWTNYC) fix below
SERIES_MAP.pop("KXLOWTNY", None); SERIES_MAP["KXLOWTNYC"] = ("NYC", -5, "min")
# older short-form HIGH series that are not T-prefixed in LOW family: AUS CHI DEN LAX MIA PHIL -> KXLOWT<X>
for _k in ("AUS", "CHI", "DEN", "LAX", "MIA", "PHIL"):
    assert ("KXLOWT" + _k) in SERIES_MAP, _k

def day_end_ts(close_time):
    """Local-standard-day end = close_time rounded to the nearest hour (historical rows close at HH:59)."""
    c = iso2ts(close_time)
    return int(round(c / 3600.0)) * 3600

# ----------------------------------------------------------------------------- observations
def _parse_valid(s):
    return int(dt.datetime.strptime(s.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp())

def _fetch_1min(st, a, b):
    u = f"{IEM1}?station={st}&vars=tmpf&sts={a.strftime('%Y-%m-%dT%H:%MZ')}&ets={b.strftime('%Y-%m-%dT%H:%MZ')}&tz=UTC&format=onlycomma"
    txt = http(u, text=True, gap=1.0, timeout=180)
    out = []
    for l in txt.splitlines():
        p = l.split(",")
        if len(p) < 4 or p[0] == "station":
            continue
        try:
            f = float(p[3])
            out.append((_parse_valid(p[2]), f))
        except Exception:
            continue
    return out

def _fetch_routine(st, a, b):
    u = (f"{IEMR}?station={st}&data=tmpf&year1={a.year}&month1={a.month}&day1={a.day}"
         f"&year2={b.year}&month2={b.month}&day2={b.day}&tz=UTC&format=onlycomma&latlon=no"
         "&report_type=3&report_type=4")
    txt = http(u, text=True, gap=1.0, timeout=180)
    out = []
    for l in txt.splitlines():
        p = l.split(",")
        if len(p) < 3 or p[0] == "station":
            continue
        try:
            f = float(p[2])
            out.append((_parse_valid(p[1]), f))
        except Exception:
            continue
    return out

OBS_A = dt.datetime(2026, 5, 21, tzinfo=dt.timezone.utc)
OBS_B = dt.datetime(2026, 10, 22, tzinfo=dt.timezone.utc)

def station_obs(st, kind):
    """kind in {'1min','routine'}; cached per station; chunked; returns sorted [(ts,f)] deduped."""
    p = os.path.join(OBS, f"{kind}_{st}.json")
    if os.path.exists(p):
        return jload(p)
    rows = []
    if kind == "1min":
        a = OBS_A
        while a < OBS_B:
            b = min(a + dt.timedelta(days=12), OBS_B)
            cp = os.path.join(OBS, f"chunk_1min_{st}_{a:%Y%m%d}.json")
            if os.path.exists(cp):
                part = jload(cp)
            else:
                part = _fetch_1min(st, a, b)
                jdump(part, cp)
            rows.extend(part)
            a = b
    else:
        rows = _fetch_routine(st, OBS_A, OBS_B)
    d = {}
    for ts, f in rows:
        if -60.0 <= f <= 130.0:           # physical sanity bound only (no other glitch filter)
            d[ts] = f
    out = sorted(d.items())
    jdump(out, p)
    return out

def cmd_obs():
    sts = sorted({v[0] for v in SERIES_MAP.values()})
    for st in sts:
        for kind in ("1min", "routine"):
            r = station_obs(st, kind)
            print(st, kind, len(r), flush=True)

# ----------------------------------------------------------------------------- universe
def load_markets():
    rows, src = {}, {}
    for s in list_series():
        for d, tag in ((MKT, "live"), (os.path.join(CACHE, "markets_hist"), "hist")):
            p = os.path.join(d, s + ".json")
            if not os.path.exists(p):
                continue
            for m in jload(p):
                m = dict(m)
                m["series"] = s
                t = m["ticker"]
                if t not in rows or (rows[t].get("result") not in ("yes", "no") and m.get("result") in ("yes", "no")):
                    rows[t] = m
                    src[t] = tag
    return rows, src

def build_universe():
    rows, src = load_markets()
    skip = collections.Counter()
    uni = []
    for t, m in rows.items():
        s = m["series"]
        if s not in SERIES_MAP:
            skip["series_not_in_verified_US_station_map"] += 1
            continue
        if not (m.get("strike_type") == "between" and "-B" in t):
            skip["not_bracket_rung(T_threshold)"] += 1
            continue
        if m.get("floor_strike") is None or m.get("cap_strike") is None:
            skip["bracket_missing_strike"] += 1
            continue
        if m.get("result") not in ("yes", "no"):
            skip["no_official_yes_no_result"] += 1
            continue
        c = dt.datetime.fromtimestamp(iso2ts(m["close_time"]), tz=dt.timezone.utc)
        if not (WIN_START <= c < WIN_END):
            skip["close_outside_2026-05-23..2026-10-20"] += 1
            continue
        st, off, kind = SERIES_MAP[s]
        de = day_end_ts(m["close_time"])
        exp_hour = (-off) % 24
        if (de // 3600) % 24 != exp_hour:
            skip["close_hour_does_not_match_standard_offset"] += 1
            continue
        uni.append({"ticker": t, "series": s, "station": st, "kind": kind, "off": off,
                    "lo": float(m["floor_strike"]), "hi": float(m["cap_strike"]), "result": m["result"],
                    "close_ts": iso2ts(m["close_time"]), "day_end": de, "day_start": de - 86400,
                    "event": m["event_ticker"], "exp_val": m.get("expiration_value"), "src": src[t]})
    uni.sort(key=lambda r: r["ticker"])
    return uni, skip

def cmd_tzcheck():
    rows, _ = load_markets()
    hrs = collections.defaultdict(collections.Counter)
    for t, m in rows.items():
        s = m["series"]
        c = iso2ts(m["close_time"])
        hrs[s][(round(c / 3600.0) * 3600 // 3600) % 24] += 1
    for s in sorted(hrs):
        print(s, SERIES_MAP.get(s, ("?", "?"))[:2], dict(hrs[s]))

# ----------------------------------------------------------------------------- signal (obs only)
import bisect
_OBS_CACHE = {}
def obs_series(st, kind):
    k = (st, kind)
    if k not in _OBS_CACHE:
        rows = jload(os.path.join(OBS, f"{kind}_{st}.json"))
        _OBS_CACHE[k] = ([r[0] for r in rows], [r[1] for r in rows])
    return _OBS_CACHE[k]

def window_obs(st, kind, a, b):
    ts, fs = obs_series(st, kind)
    i, j = bisect.bisect_left(ts, a), bisect.bisect_right(ts, b)
    return ts[i:j], fs[i:j]

def pick_source(st, S, E):
    """1-min if the local day is well covered (>=1000 of 1440 minutes AND >=65 obs in the final 130 min);
    else routine fallback (>=6 obs in the day AND >=2 in the final 130 min); else none.  Recorded per market."""
    t1, f1 = window_obs(st, "1min", S, E)
    n_tail = sum(1 for x in t1 if x >= E - 130 * 60)
    if len(t1) >= 1000 and n_tail >= 65:
        return "1min", t1, f1
    tr, fr = window_obs(st, "routine", S, E)
    n_tail_r = sum(1 for x in tr if x >= E - 130 * 60)
    if len(tr) >= 6 and n_tail_r >= 2:
        return "routine", tr, fr
    return None, [], []

def walk(ts, fs, kind, Rs=RS, H=3):
    """Obs-only walk.  For each obs index i returns (t_sig, E_i, {R: held_i}) with
       t_sig = ts[i] + 60 s  (the first instant at which obs i is STRICTLY in the past, so the signal
       uses only obs with timestamp < t_sig -- anchor (b)).
       E_i = running max (kind 'max') / min ('min') over obs[0..i] of the local day.
       held_R(i) = the last H obs (i-H+1..i) all lie >= R away from E_i on the reversal side."""
    out = []
    E = None
    for i, f in enumerate(fs):
        E = f if E is None else (max(E, f) if kind == "max" else min(E, f))
        held = {}
        if i >= H - 1:
            seg = fs[i - H + 1:i + 1]
            for R in Rs:
                held[R] = (max(seg) <= E - R) if kind == "max" else (min(seg) >= E + R)
        else:
            for R in Rs:
                held[R] = False
        out.append((ts[i] + 60, E, held))
    return out

def fire_for_rung(walkrows, lo, hi, M, R, W, close_ts):
    """First t_sig in [close-W*60, close] with lo+M <= E <= hi-M and reversed-and-held.  Returns (t_sig, E, idx)."""
    a = close_ts - W * 60
    for idx, (t, E, held) in enumerate(walkrows):
        if t < a:
            continue
        if t > close_ts:
            break
        if held[R] and lo + M <= E <= hi - M:
            return t, E, idx
    return None

def signal_bruteforce(ts, fs, kind, t, lo, hi, M, R, H, close_ts, W):
    """Independent re-implementation using ONLY obs with timestamp < t (look-ahead proof)."""
    idx = [i for i, x in enumerate(ts) if x < t]
    if len(idx) < H:
        return False
    sub = [fs[i] for i in idx]
    E = max(sub) if kind == "max" else min(sub)
    seg = sub[-H:]
    ok_rev = (max(seg) <= E - R) if kind == "max" else (min(seg) >= E + R)
    return bool(ok_rev and lo + M <= E <= hi - M and close_ts - W * 60 <= t <= close_ts)

def cmd_signal():
    uni, skip = build_universe()
    # group rungs by (station, kind, day_end) so the walk is shared
    groups = collections.defaultdict(list)
    for r in uni:
        groups[(r["station"], r["kind"], r["day_start"], r["day_end"])].append(r)
    fires, cover = [], collections.Counter()
    monotone_viol = 0
    srcrec = {}
    for (st, kind, S, E), rungs in sorted(groups.items()):
        src, ts, fs = pick_source(st, S, E)
        for r in rungs:
            srcrec[r["ticker"]] = src
        if src is None:
            cover["no_obs_coverage(rungs)"] += len(rungs)
            continue
        cover[f"obs_{src}(rungs)"] += len(rungs)
        # anchor (c): independent running-extreme monotonicity check
        run, prev = None, None
        for f in fs:
            run = f if run is None else (max(run, f) if kind == "max" else min(run, f))
            if prev is not None and ((kind == "max" and run < prev) or (kind == "min" and run > prev)):
                monotone_viol += 1
            prev = run
        wk = walk(ts, fs, kind)
        for r in rungs:
            for variant, (lo, hi) in (("literal", (r["lo"], r["hi"])), ("lattice", (r["lo"] - 1.0, r["hi"] + 1.0))):
                for (M, R, H, W) in CELLS:
                    f = fire_for_rung(wk, lo, hi, M, R, W, r["close_ts"])
                    if f:
                        fires.append({"ticker": r["ticker"], "variant": variant, "cell": [M, R, H, W],
                                      "t_sig": f[0], "E": f[1], "idx": f[2], "src": src, "result": r["result"]})
    res = {"n_universe": len(uni), "skip": dict(skip), "coverage": dict(cover), "monotone_violations": monotone_viol,
           "n_fire_rows": len(fires), "fires": fires, "src": srcrec}
    jdump(res, os.path.join(CACHE, "signal.json"))
    jdump(uni, os.path.join(CACHE, "universe.json"))
    c = collections.Counter((f["variant"], tuple(f["cell"])) for f in fires)
    print("universe", len(uni), "skip", dict(skip), "cover", dict(cover), "monoviol", monotone_viol)
    for k in sorted(c):
        print(k, c[k])

# ----------------------------------------------------------------------------- candles
CUTOFF_TS = iso2ts("2026-08-28T00:00:00Z")
V2.WINDOW_MIN = 130          # normalize() keeps rows in [close-WINDOW_MIN*60, close]; widened from its 60 default

def _adapt(cs):
    """Historical candlesticks use {'close': '0.99'}; live ones use {'close_dollars': '0.99'}.  normalize()
    reads *_dollars, so alias the historical keys (no values are changed)."""
    out = []
    for c in cs:
        c = dict(c)
        for side in ("yes_bid", "yes_ask"):
            n = c.get(side)
            if isinstance(n, dict) and "close_dollars" not in n and "close" in n:
                n = dict(n); n["close_dollars"] = n["close"]; c[side] = n
        out.append(c)
    return out

def fetch_candles(tk, series, close_ts):
    p = os.path.join(CAND, tk + ".json")
    if os.path.exists(p):
        return jload(p)
    a, b = close_ts - 7800, close_ts
    live = f"{API}/series/{series}/markets/{tk}/candlesticks?start_ts={a}&end_ts={b}&period_interval=1"
    hist = f"{API}/historical/markets/{tk}/candlesticks?start_ts={a}&end_ts={b}&period_interval=1"
    order = [("live", live), ("hist", hist)] if close_ts >= CUTOFF_TS else [("hist", hist), ("live", live)]
    rec = {"src": None, "cs": None, "err": None}
    for tag, u in order:
        try:
            d = http(u, tries=4)
            cs = d.get("candlesticks")
            if cs is not None:
                rec = {"src": tag, "cs": cs, "err": None}
                break
        except Exception as e:
            rec["err"] = f"{tag}:{type(e).__name__}:{getattr(e, 'code', '')}"
    jdump(rec, p)
    return rec

def candle_rows(tk, close_ts):
    p = os.path.join(CAND, tk + ".json")
    if not os.path.exists(p):
        return None
    rec = jload(p)
    if rec.get("cs") is None:
        return None
    rows = V2.normalize(_adapt(rec["cs"]), close_ts)      # <-- reused edge_sizing_v2.normalize()
    return sorted(rows, key=lambda r: r[0])

def cmd_candles(limit=None):
    sig = jload(os.path.join(CACHE, "signal.json"))
    uni = {r["ticker"]: r for r in jload(os.path.join(CACHE, "universe.json"))}
    need = sorted({f["ticker"] for f in sig["fires"]})
    rng = random.Random(SEED)
    rng.shuffle(need)                       # SHUFFLED work order -- never re-sorted
    jdump(need, os.path.join(CACHE, "candle_work_order.json"))
    print("fired rungs needing candles:", len(need), flush=True)
    n = 0
    for tk in need:
        if limit is not None and n >= limit:
            break
        if os.path.exists(os.path.join(CAND, tk + ".json")):
            continue
        r = uni[tk]
        fetch_candles(tk, r["series"], r["close_ts"])
        n += 1
        if n % 50 == 0:
            print("fetched", n, flush=True)

# ----------------------------------------------------------------------------- statistics
from scipy import stats as _st

def fee_c(p_c):
    return math.ceil(7.0 * (p_c / 100.0) * (1 - p_c / 100.0) - 1e-12)

def wilson(k, n, z=1.959963985):
    if n == 0:
        return (None, None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))

def cluster_stats(xs, ws, gs):
    """Weighted mean with day-clustered (CR1, linearised ratio estimator) SE.  Returns dict."""
    n = len(xs)
    out = {"n": n}
    if n == 0:
        return out
    sw = sum(ws)
    if sw <= 0:
        out.update({"mean": None})
        return out
    mu = sum(w * x for w, x in zip(ws, xs)) / sw
    cl = collections.defaultdict(float)
    for x, w, g in zip(xs, ws, gs):
        cl[g] += w * (x - mu)
    G = len(cl)
    out.update({"mean": mu, "G": G, "df": G - 1})
    if G < 2:
        return out
    var = (G / (G - 1.0)) * sum(u * u for u in cl.values()) / (sw * sw)
    se = math.sqrt(var)
    out["se"] = se
    out["t"] = (mu / se) if se > 0 else None
    out["ub979"] = mu + _st.t.ppf(0.979, G - 1) * se
    out["tcrit_bonf"] = float(_st.t.ppf(1 - 0.05 / 24 / 2, G - 1))
    return out

# ----------------------------------------------------------------------------- analysis
def local_date(r):
    return dt.datetime.fromtimestamp(r["day_start"] + r["off"] * 3600, tz=dt.timezone.utc).strftime("%Y-%m-%d")

def entry_for(rows, t_search, close_ts):
    """First candle with t_search <= ts <= close whose YES ask <= 98c with net > 0 (YES is the only side
    a FINAL-YES fire ever buys, so cost = yes_ask; NEVER 100 - yes_ask)."""
    if rows is None:
        return None, "no_candles"
    if not rows:
        return None, "no_candles"
    seen = False
    for ts, yb, ya, vol in rows:
        if ts < t_search or ts > close_ts:
            continue
        seen = True
        if ya is None or not (0 < ya <= 98):
            continue
        if 100 - ya - fee_c(ya) <= 0:
            continue
        return (ts, ya, yb, vol), "ok"
    return None, ("no_qualifying_candle" if seen else "no_candle_after_signal")

def cmd_analyze():
    sig = jload(os.path.join(CACHE, "signal.json"))
    uni_list = jload(os.path.join(CACHE, "universe.json"))
    uni = {r["ticker"]: r for r in uni_list}
    rowscache = {}
    def rows_of(tk):
        if tk not in rowscache:
            rowscache[tk] = candle_rows(tk, uni[tk]["close_ts"])
        return rowscache[tk]
    # candle-work sample = the longest COMPLETED PREFIX of the seeded shuffled work order (never re-sorted)
    order = jload(os.path.join(CACHE, "candle_work_order.json")) if os.path.exists(os.path.join(CACHE, "candle_work_order.json")) else []
    prefix = []
    for tk in order:
        if os.path.exists(os.path.join(CAND, tk + ".json")):
            prefix.append(tk)
        else:
            break
    sampled = set(prefix)
    results = {}
    for variant in ("literal", "lattice"):
        for cell in CELLS:
            fl_full = [f for f in sig["fires"] if f["variant"] == variant and tuple(f["cell"]) == cell]
            fl = [f for f in fl_full if f["ticker"] in sampled]
            k_all = len(fl_full)                       # false-lock rate uses EVERY fire (obs + official result only)
            k_fl = sum(1 for f in fl_full if f["result"] == "no")
            fl_all = wilson(k_fl, k_all)
            for L in LS:
                recs, unt = [], collections.Counter()
                for f in fl:
                    r = uni[f["ticker"]]
                    e, why = entry_for(rows_of(f["ticker"]), f["t_sig"] + L * 60, r["close_ts"])
                    if e is None:
                        unt[why] += 1
                        continue
                    ts, ya, yb, vol = e
                    pnl = (100 - ya - fee_c(ya)) if f["result"] == "yes" else (-ya - fee_c(ya))
                    recs.append({"tk": f["ticker"], "pnl": pnl, "cost": ya, "vol": vol, "res": f["result"],
                                 "day": local_date(r), "st": r["station"], "src": f["src"], "ets": ts, "t_sig": f["t_sig"]})
                n = len(recs)
                xs = [x["pnl"] for x in recs]
                st_eq = cluster_stats(xs, [1.0] * n, [x["day"] for x in recs])
                st_vw = cluster_stats(xs, [max(x["vol"], 0.0) for x in recs], [x["day"] for x in recs])
                k_fl_p = sum(1 for x in recs if x["res"] == "no")
                results[(variant, cell, L)] = {
                    "variant": variant, "cell": list(cell), "L": L,
                    "n_fires": k_all, "n_fires_candle_sampled": len(fl), "n_false_lock_all": k_fl,
                    "false_lock_rate_all": fl_all[0], "wilson_ub_all": fl_all[2],
                    "n_priced": n, "n_untradeable": len(fl) - n, "untradeable_breakdown": dict(unt),
                    "untradeable_frac": ((len(fl) - n) / len(fl)) if fl else None,
                    "n_false_lock_priced": k_fl_p,
                    "false_lock_rate_priced": (k_fl_p / n) if n else None,
                    "wilson_ub_priced": wilson(k_fl_p, n)[2],
                    "ev_eq": st_eq, "ev_vw": st_vw,
                    "n_days": len({x["day"] for x in recs}), "n_stations": len({x["st"] for x in recs}),
                    "n_obs_1min": sum(1 for x in recs if x["src"] == "1min"),
                    "n_obs_routine": sum(1 for x in recs if x["src"] == "routine"),
                    "mean_cost_c": (sum(x["cost"] for x in recs) / n) if n else None,
                    "sum_entry_vol": sum(x["vol"] for x in recs),
                    "_recs": recs,
                }
    return results, sig, uni_list, {"order_len": len(order), "prefix_done": len(prefix)}

def evaluate(res):
    """Apply the frozen PASS/KILL bars at L=10 for the literal (spec) variant."""
    cells = {}
    for (variant, cell, L), r in res.items():
        if variant != "literal" or L != 10:
            continue
        ev_vw, ev_eq = r["ev_vw"], r["ev_eq"]
        def tpass(s):
            return s.get("t") is not None and s["t"] >= s.get("tcrit_bonf", 3.3) and s["t"] >= 0
        crit = {
            "1_false_lock<=2%_and_wilsonUB<=5%": (r["false_lock_rate_all"] is not None and r["false_lock_rate_all"] <= 0.02
                                                    and r["wilson_ub_all"] is not None and r["wilson_ub_all"] <= 0.05),
            "2_vwEV>=2.0c": ev_vw.get("mean") is not None and ev_vw["mean"] >= 2.0,
            "3_signed_t>=bonferroni(vw)": tpass(ev_vw),
            "3b_signed_t>=bonferroni(eq)": tpass(ev_eq),
            "4_n>=100_days>=40_stations>=10": r["n_priced"] >= 100 and r["n_days"] >= 40 and r["n_stations"] >= 10,
            "5_untradeable<=70%": r["untradeable_frac"] is not None and r["untradeable_frac"] <= 0.70,
        }
        cells[cell] = {"crit": crit, "all": all(crit.values())}
    passed = [c for c, v in cells.items() if v["all"]]
    # KILL clauses
    prim = res[("literal", PRIMARY, 10)]
    kill_fl = prim["false_lock_rate_all"] is not None and prim["false_lock_rate_all"] > 0.05
    pos = [r for (v, c, L), r in res.items() if v == "literal" and L == 10 and r["ev_vw"].get("mean") is not None and r["ev_vw"]["mean"] > 0]
    kill_n = bool(pos) and all(not (r["n_priced"] >= 100) for r in pos)
    ubs = [r["ev_vw"].get("ub979") for (v, c, L), r in res.items() if v == "literal" and L == 10]
    ubs = [u for u in ubs if u is not None]
    best_ub = max(ubs) if ubs else None
    kill_ub = best_ub is not None and best_ub < 0.5
    if passed:
        verdict = "PASS"
    elif kill_fl or kill_n or kill_ub:
        verdict = "KILL"
    else:
        verdict = "INSUFFICIENT"
    return verdict, {"cells": {str(k): v for k, v in cells.items()}, "pass_cells": [list(c) for c in passed],
                     "kill_false_lock_primary": kill_fl, "kill_all_positive_cells_fail_n": kill_n,
                     "kill_best_ub979_lt_0.5": kill_ub, "best_ub979_ev_vw": best_ub,
                     "n_positive_ev_cells": len(pos)}

# ----------------------------------------------------------------------------- anchors
def oracle_recompute(rows, result, close_ts, window_min=60):
    """EDGE_SIZING Stage-1 capturable definition, recomputed independently: final 60 min, winner-side cost
    (yes_ask if YES else 100 - yes_bid), cost<=98, net>0."""
    cap = []
    for ts, yb, ya, vol in rows:
        if ts < close_ts - window_min * 60 or ts > close_ts:
            continue
        cost = ya if result == "yes" else (None if yb is None else 100 - yb)
        if cost is None or not (0 < cost <= 98):
            continue
        if 100 - cost - fee_c(cost) <= 0:
            continue
        cap.append((ts, cost))
    return cap

def anchor_a(results, uni):
    out = {}
    # (a1) reproduce the 140 EDGE_SIZING-capturable rows from OUR candle pull (price-join integrity)
    s2 = jload(os.path.join(HERE, "out", "edge_sizing_stage2.json"))["per_market"]
    cmp_rows, ok_n, ok_first, ok_last, missing = 0, 0, 0, 0, 0
    detail = []
    for m in s2:
        tk = m["ticker"]
        close_ts = iso2ts(m["close_time"])
        series = tk.split("-")[0]
        rec = fetch_candles(tk, series, close_ts)
        rows = candle_rows(tk, close_ts)
        if rows is None:
            missing += 1
            continue
        cap = oracle_recompute(rows, m["result"], close_ts)
        cmp_rows += 1
        a = len(cap) == m["n_capturable_minutes_recomputed"]
        b = bool(cap) and cap[0][0] == m["first_capturable_ts"]
        c = bool(cap) and cap[-1][0] == m["last_capturable_ts"]
        ok_n += a; ok_first += b; ok_last += c
        if not (a and b and c) and len(detail) < 12:
            detail.append({"ticker": tk, "oracle_n": m["n_capturable_minutes_recomputed"], "my_n": len(cap),
                           "oracle_first": m["first_capturable_ts"], "my_first": cap[0][0] if cap else None})
    out["a1_oracle_rows_reproduced"] = {"oracle_rows": len(s2), "candles_available": cmp_rows, "candles_missing": missing,
                                         "n_minutes_match": ok_n, "first_ts_match": ok_first, "last_ts_match": ok_last,
                                         "mismatch_examples": detail}
    # (a2) every priced YES-settled fire (L=0) whose entry lies in the final 60 min must be oracle-capturable
    viol, checked, outside, false_lock_priced = [], 0, 0, 0
    for (variant, cell, L), r in results.items():
        if L != 0:
            continue
        for x in r["_recs"]:
            u = uni[x["tk"]]
            if x["res"] == "no":
                false_lock_priced += 1
                continue
            if x["ets"] < u["close_ts"] - 3600:
                outside += 1
                continue
            checked += 1
            rows = candle_rows(x["tk"], u["close_ts"])
            if not oracle_recompute(rows, "yes", u["close_ts"]):
                viol.append({"variant": variant, "cell": list(cell), "ticker": x["tk"]})
    out["a2_subset_check"] = {"priced_yes_fires_checked_(entry_in_final_60m)": checked,
                              "violations": viol[:20], "n_violations": len(viol),
                              "yes_fires_entered_before_final_60m_(outside_oracle_window)": outside,
                              "false_locks_priced_(not_applicable_to_winner_side_oracle)": false_lock_priced}
    return out

def anchor_b(sig, uni, nmax=300):
    """No-look-ahead proof: brute-force re-evaluation with obs ts < t only, 'firstness', and a perturbation test."""
    rng = random.Random(SEED + 1)
    fl = [f for f in sig["fires"]]
    prim = [f for f in fl if f["variant"] == "literal" and tuple(f["cell"]) == PRIMARY]
    pick = prim + rng.sample(fl, min(nmax, len(fl)))
    n_ok, bad, ex = 0, [], None
    for f in pick:
        r = uni[f["ticker"]]
        M, R, H, W = f["cell"]
        lo, hi = (r["lo"], r["hi"]) if f["variant"] == "literal" else (r["lo"] - 1.0, r["hi"] + 1.0)
        src, ts, fs = pick_source(r["station"], r["day_start"], r["day_end"])
        t = f["t_sig"]
        # 1) fires under strict ts<t brute force
        ok1 = signal_bruteforce(ts, fs, r["kind"], t, lo, hi, M, R, H, r["close_ts"], W)
        # 2) no earlier decision time qualifies
        ok2 = True
        for j, x in enumerate(ts):
            tj = x + 60
            if tj >= t:
                break
            if signal_bruteforce(ts, fs, r["kind"], tj, lo, hi, M, R, H, r["close_ts"], W):
                ok2 = False
                break
        # 3) perturbation: corrupt every obs with ts >= t; the walk's decision at t must not change
        fs2 = [(v if x < t else (130.0 if rng.random() < .5 else -60.0)) for x, v in zip(ts, fs)]
        wk = walk(ts, fs2, r["kind"])
        g = fire_for_rung(wk, lo, hi, M, R, W, r["close_ts"])
        ok3 = g is not None and g[0] == t
        if ok1 and ok2 and ok3:
            n_ok += 1
            if ex is None:
                ex = {"ticker": f["ticker"], "variant": f["variant"], "cell": f["cell"], "t_sig_utc": utc(t),
                      "last_obs_used_utc": utc(max(x for x in ts if x < t)),
                      "n_obs_with_ts_lt_t": sum(1 for x in ts if x < t), "n_obs_ge_t_ignored": sum(1 for x in ts if x >= t)}
        else:
            bad.append({"ticker": f["ticker"], "cell": f["cell"], "ok1": ok1, "ok2": ok2, "ok3": ok3})
    return {"checked": len(pick), "passed": n_ok, "failures": bad[:10], "worked_example": ex}

def utc(ts):
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")

# ----------------------------------------------------------------------------- tz / station diagnostics
def cmd_tzdiag(uni=None):
    """Validate the local-day window and station map WITHOUT touching outcomes: compare the obs-derived day
    extreme with the market's published numeric expiration_value (the NWS value the market settled on), under window
    shifts of -3..+3 hours, on the SAME events for every shift (events whose selected feed is 1-min and whose shifted
    windows are all >=1000 1-min obs deep).  The true window should dominate, sharply for LOW markets."""
    if uni is None:
        uni = jload(os.path.join(CACHE, "universe.json"))
    seen = set()
    per = {"max": collections.defaultdict(list), "min": collections.defaultdict(list)}
    hist_hour = collections.defaultdict(collections.Counter)
    diffd = collections.defaultdict(collections.Counter)
    for r in uni:
        k = (r["series"], r["day_end"])
        if k in seen or r["exp_val"] in (None, ""):
            continue
        try:
            ev = float(r["exp_val"])
        except Exception:
            continue
        seen.add(k)
        src, ts0, fs0 = pick_source(r["station"], r["day_start"], r["day_end"])
        if not fs0:
            continue
        ext0 = max(fs0) if r["kind"] == "max" else min(fs0)
        diffd[f"{r['kind']}|{src}"][int(max(-3, min(3, round(ext0 - ev))))] += 1
        i0 = fs0.index(ext0)
        hist_hour[r["kind"]][int(((ts0[i0] + r["off"] * 3600) // 3600) % 24)] += 1
        if src != "1min":
            continue
        row = {}
        for dh in range(-3, 4):
            _t, f = window_obs(r["station"], "1min", r["day_start"] + dh * 3600, r["day_end"] + dh * 3600)
            if len(f) < 1000:
                row = None
                break
            e = max(f) if r["kind"] == "max" else min(f)
            row[dh] = abs(e - ev) < 0.5
        if row:
            for dh, v in row.items():
                per[r["kind"]][dh].append(v)
    rate = {kind: {str(dh): [round(sum(v) / len(v), 4), len(v)] for dh, v in sorted(d.items())} for kind, d in per.items()}
    return {"match_rate_by_window_shift_hours": rate,
            "feed_minus_official_extreme_degF_dist": {k: {str(a): b for a, b in sorted(v.items())} for k, v in diffd.items()},
            "argext_local_std_hour_hist": {k: dict(sorted(v.items())) for k, v in hist_hour.items()}}


def cmd_oracle_fetch():
    s2 = jload(os.path.join(HERE, "out", "edge_sizing_stage2.json"))["per_market"]
    for m in s2:
        fetch_candles(m["ticker"], m["ticker"].split("-")[0], iso2ts(m["close_time"]))
    print("oracle candles fetched", len(s2))

def worked_example(results, uni):
    """Concrete timezone walk-through on a real priced fire (DST month, standard-offset day, UTC epochs)."""
    sig = jload(os.path.join(CACHE, "signal.json"))
    cands = []
    for x in results[("lattice", PRIMARY, 10)]["_recs"]:
        r = uni[x["tk"]]
        try:
            float(r["exp_val"])
        except Exception:
            continue
        if r["kind"] == "max" and r["station"] == "SEA" and sig["src"].get(x["tk"]) == "1min":
            cands.append((x["tk"], x))
    if not cands:
        for x in results[("lattice", PRIMARY, 10)]["_recs"]:
            r = uni[x["tk"]]
            if sig["src"].get(x["tk"]) == "1min":
                cands.append((x["tk"], x))
    if not cands:
        return None
    tk, x = sorted(cands)[0]
    r = uni[tk]
    src, ts, fs = pick_source(r["station"], r["day_start"], r["day_end"])
    ext = max(fs) if r["kind"] == "max" else min(fs)
    i_ext = fs.index(ext)
    off = r["off"]
    def loc(t, o):
        return dt.datetime.fromtimestamp(t + o * 3600, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    f = [q for q in sig["fires"] if q["ticker"] == tk and q["variant"] == "lattice" and tuple(q["cell"]) == PRIMARY][0]
    mk = jload(os.path.join(MKT, r["series"] + ".json")) if os.path.exists(os.path.join(MKT, r["series"] + ".json")) else []
    return {"ticker": tk, "station": r["station"], "kind": r["kind"], "bracket": [r["lo"], r["hi"]], "official_result": r["result"],
            "expiration_value": r["exp_val"], "close_time_utc": utc(r["close_ts"]), "local_day_end_utc": utc(r["day_end"]),
            "local_day_start_utc": utc(r["day_start"]), "std_offset_h": off,
            "local_day_in_standard_time": f"{loc(r['day_start'], off)} .. {loc(r['day_end'], off)} (LST, UTC{off:+d})",
            "same_day_on_the_wall_clock_in_DST": f"{loc(r['day_start'], off + 1)} .. {loc(r['day_end'], off + 1)} (LDT, UTC{off + 1:+d})",
            "n_obs_in_window": len(ts), "obs_source": src, "running_extreme_F": ext,
            "extreme_obs_utc": utc(ts[i_ext]), "extreme_obs_LST": loc(ts[i_ext], off),
            "t_sig_utc": utc(f["t_sig"]), "t_sig_LST": loc(f["t_sig"], off), "t_sig_epoch": f["t_sig"],
            "minutes_before_close": round((r["close_ts"] - f["t_sig"]) / 60.0, 1),
            "entry_candle_end_ts_epoch@L10": x["ets"], "entry_candle_utc@L10": utc(x["ets"]),
            "entry_yes_ask_c": x["cost"], "pnl_c": x["pnl"], "pnl_note": "(100 - ask - fee) if settled YES else (-ask - fee)"}

S_FRAC = [0.0]

def cmd_report():
    results, sig, uni_list, info = cmd_analyze()
    uni = {r["ticker"]: r for r in uni_list}
    verdict, ev = evaluate(results)
    a_a = anchor_a(results, uni)
    a_b = anchor_b(sig, uni)
    tz = cmd_tzdiag(uni_list)
    geo = geometry_diag(uni_list)
    wex = worked_example(results, uni)
    S_FRAC[0] = info["prefix_done"] / max(1, len({f['ticker'] for f in sig['fires']}))
    _rows, _src = load_markets()
    unm = collections.Counter(m["series"] for m in _rows.values() if m["series"] not in SERIES_MAP)
    rep = {"spec": "venue_expansion/TERMINAL_FINALITY_SPEC.md (frozen 2026-10-27)", "build": "B (independent replication)",
           "verdict": verdict, "evaluation": ev,
           "universe": {"n_bracket_rungs": len(uni_list), "skip": sig["skip"], "obs_coverage": sig["coverage"],
                        "n_events": len({(r['series'], r['day_end']) for r in uni_list}), "unmapped_series_rows": dict(unm),
                        "n_series": len({r['series'] for r in uni_list}), "n_stations": len({r['station'] for r in uni_list}),
                        "n_days": len({r['day_end'] for r in uni_list}),
                        "close_span": [utc(min(r['close_ts'] for r in uni_list)), utc(max(r['close_ts'] for r in uni_list))]},
           "sampling": {"signal_walk": "FULL universe (obs-only, no price needed)", "candle_work_order": "seeded shuffle, seed=%d, never re-sorted" % SEED,
                        "fired_rungs_total": len({f['ticker'] for f in sig['fires']}), **info,
                        "sampling_fraction_of_fired_rungs": round(info["prefix_done"] / max(1, len({f['ticker'] for f in sig['fires']})), 4)},
           "geometry": geo, "anchors": {"a": a_a, "b": a_b, "c": {"monotone_violations": sig["monotone_violations"]}},
           "tz_diag": tz, "worked_example": wex,
           "cells": [{k: v for k, v in r.items() if k != "_recs"} for r in results.values()]}
    rep["subgroups"] = subgroup_table(sig, uni, results)
    pp = results[("lattice", PRIMARY, 10)]
    def split(recs):
        out = {}
        for tag, sel in (("settled_YES_wins", [x for x in recs if x["res"] == "yes"]), ("settled_NO_false_locks", [x for x in recs if x["res"] == "no"])):
            n = len(sel)
            out[tag] = {"n": n, "mean_entry_ask_c": (sum(x["cost"] for x in sel) / n) if n else None,
                        "mean_net_pnl_c": (sum(x["pnl"] for x in sel) / n) if n else None,
                        "share_entered_at_ask>=90c": (sum(1 for x in sel if x["cost"] >= 90) / n) if n else None,
                        "share_entered_at_ask<=10c": (sum(1 for x in sel if x["cost"] <= 10) / n) if n else None}
        return out
    rep["lattice_primary_L10_split"] = split(pp["_recs"])
    rep["lattice_primary_L10_priced_false_lock_rate"] = pp["false_lock_rate_priced"]
    # entries at ask>=90 only (the 'market still shows near-certain winner' tail) -- descriptive
    hi = [x for x in pp["_recs"] if x["cost"] >= 90]
    rep["lattice_primary_L10_entries_ask_ge_90"] = {"n": len(hi), "false_locks": sum(1 for x in hi if x["res"] == "no"),
                                                    "mean_net_pnl_c": (sum(x["pnl"] for x in hi) / len(hi)) if hi else None}
    rep["headline"] = (
        f"Executed literally, the frozen spec produces **zero fires in all 8 cells x 3 latency arms**: brackets are 1 degF wide in (floor, cap) terms "
        f"(a 2-whole-degree rung), so `lo+M <= E <= hi-M` is empty for M=1.0 and needs a half-degree extreme for M=0.5; observed extremes are whole degrees. "
        f"No PASS is possible and I did not move any bar. Under the one charitable reading that lets the rule fire (exploratory 'lattice' variant, primary cell, "
        f"{pp['n_fires']:,} fires over the full universe) the finality inference is **wrong {pp['n_false_lock_all']:,} times = {100 * pp['false_lock_rate_all']:.1f}% "
        f"(Wilson UB {100 * pp['wilson_ub_all']:.1f}%)** against a 2% / 5% bar. The cause is data-source disagreement, not timezone: IEM's day extreme differs from the official "
        f"settlement value by 1 degF on about half of HIGH days (15-40% of LOW days), one-sidedly, and a rung is only 2 degF wide. "
        f"Priced on a random {100 * S_FRAC[0]:.0f}% subsample of fired rungs (L=10): n priced {pp['n_priced']}, untradeable {100 * (pp['untradeable_frac'] or 0):.0f}%, "
        f"EV {pp['ev_eq'].get('mean') if pp['ev_eq'].get('mean') is None else round(pp['ev_eq']['mean'], 2)}c/contract equal-weight "
        f"(signed day-clustered t {pp['ev_eq'].get('t') if pp['ev_eq'].get('t') is None else round(pp['ev_eq']['t'], 2)}).")
    rep["choices"] = [
        "**Bracket geometry literal**: `[lo,hi] = [floor_strike, cap_strike]` exactly as carried on the rung. Widening it is the exploratory 'lattice' variant only (PASS-ineligible).",
        "**Signal timestamp** `t_sig = ts(obs_i) + 60 s` (strict `< t` look-ahead rule, anchor b). A build that uses `t_sig = ts(obs_i)` shifts every signal by 1 minute; immaterial at L>=10.",
        "**Reversed-and-held**: the last H=3 observations *including the current one* all satisfy `temp <= E(t)-R` (HIGH) / `>= E(t)+R` (LOW), with E(t) the running extreme at t. On 1-min feed H=3 means 3 minutes; on routine feed it means 3 METAR obs (~2-3 h).",
        "**Local day** = [round(close_time to hour) - 24 h, that hour], i.e. NWS standard-time midnight-to-midnight (see section 9). E accumulates from day start.",
        "**Terminal window** `close - W*60 <= t_sig <= close`; first qualifying t only; one fire per rung per cell.",
        "**Feed selection per market** (recorded in `signal.json: src`): 1-min if >=1000 of 1440 minutes AND >=65 obs in the last 130 min; else routine (`asos.py` report_type 3&4) if >=6 obs in the day and >=2 in the last 130 min; else the rung is skipped (8 rungs). Only a physical bound filter (-60..130 degF) is applied; no deployed-rule glitch filter.",
        "**Entry cost is `yes_ask`** for every fire (FINAL-YES always buys YES). For YES-settled rungs this equals the spec's winner-side cost. For false locks the spec's 'winner-side = 100 - yes_bid' is the NO price, which a YES buyer cannot pay; I charge the real YES ask and the loss `-(ask+fee)`. Using the winner-side cost for false locks would have *hidden* losses; the gate here is outcome-independent (deployable).",
        "**Entry** = first candle with `t_sig+L <= end_period_ts <= close_time`, `0 < yes_ask <= 98`, and `100-ask-fee > 0`; none -> UNTRADEABLE (candle-less rungs are counted untradeable, conservative). Candles are sparse (trade/quote-change minutes only), so 'first candle at or after' can be several minutes later.",
        "**EV**: per-contract net cents; equal-weight (one contract per fire, as the spec's accounting) and volume-weighted by the entry candle's traded volume. The Bonferroni t uses the day-clustered (CR1, linearised ratio) SE, df = G-1 (G = distinct local days); a PASS would have to clear the bar on BOTH weightings (the stricter reading of an ambiguous spec). One-sided 97.9% UB = mean + t_{0.979,G-1} * SE.",
        "**False-lock rate** is over ALL fires (a property of obs + official result), not just priced ones; the priced-only rate is also in the JSON.",
        "**Clusters** = local calendar day of the market.",
    ]
    sgd = {(r["kind"], r["E_position"], r["feed"]): r for r in rep["subgroups"]}
    hh, ll = sgd[("max", "E==hi", "1min")], sgd[("min", "E==lo", "1min")]
    hl, lh = sgd[("max", "E==lo", "1min")], sgd[("min", "E==hi", "1min")]
    h90 = rep["lattice_primary_L10_entries_ask_ge_90"]
    rep["closing"] = (
        "**What this says.** The frozen rule, as parameterised, selects the empty set (spec defect, section 3). The reading that lets it fire has a ~24% false-lock rate "
        "because the feed's day extreme and the official settlement value differ by one whole degree (about half of HIGH days on the 1-min feed, 15-40% of LOW days), in a feed-specific direction, and a rung is only two "
        "whole degrees wide. The prices agree with the diagnosis: among fires that can actually be entered at L=10 "
        f"the false-lock rate is {100 * (rep['lattice_primary_L10_priced_false_lock_rate'] or 0):.0f}%, because YES is still offered at <=98c mostly when the market already knows the feed extreme "
        f"is not the official one (those losers are bought at ~4c, so the loss per false lock is small, but they are not the trades the thesis imagined). "
        f"Where the market does agree with the signal (entry ask >= 90c, n={h90['n']}) the signal is right {100 * (1 - h90['false_locks'] / max(1, h90['n'])):.1f}% of the time "
        f"and pays {_f(h90['mean_net_pnl_c'])}c/contract net of fees: priced to the penny, no edge.\n\n"
        "**What this does not say.** It does not say that finality as an idea is dead. The descriptive table (section 7, no prices, all 4,734 fires) shows the false-lock rate depends "
        f"on which side of the rung the extreme sits relative to the feed's one-sided bias: on the 1-min feed, HIGH with E==hi {100 * hh['rate']:.1f}% (n={hh['n']}) vs E==lo {100 * hl['rate']:.1f}% (n={hl['n']}); "
        f"LOW with E==lo {100 * ll['rate']:.1f}% (n={ll['n']}) vs E==hi {100 * lh['rate']:.1f}% (n={lh['n']}). That is an *outcome-informed, post-hoc* observation on the same data, so it is a "
        "hypothesis for a new pre-registration with its own forward holdout, not a result; and since a winner nets only +1c..+5c while a loser costs up to ~98c, break-even "
        "needs a false-lock rate near 1-5% **at the prices actually offered**, which the ask>=90c row above says the market already enforces. "
        "A PASS would have been necessary-but-not-sufficient; there is no PASS, so nothing here supports a canary.\n\n"
        "**Disagreement guide for the A/B comparison.** If Build A fires on the frozen grid at M=1.0, it has widened the bracket (or used a different [lo,hi]); compare against my 'lattice' rows. "
        "If it fires at M=0.5 with E on whole degrees, it has taken lo/hi as something other than floor/cap. If its false-lock rate is far from ~24%, check feed selection (1-min vs routine) and the "
        "local-day window first (section 9).")
    jdump(rep, OUT_JSON)
    write_md(rep, results, sig, uni)
    jdump({"%s|%s|%s" % (k[0], list(k[1]), k[2]): r["_recs"] for k, r in results.items() if k[2] == 10 and k[0] == "lattice"},
          os.path.join(CACHE, "priced_recs_lattice_L10.json"))
    print(json.dumps({"verdict": verdict, "evaluation": ev, "sampling": rep["sampling"]}, indent=1, default=str))
    return rep, results

# ----------------------------------------------------------------------------- geometry diagnostic
def geometry_diag(uni_list):
    """How many rungs could the LITERAL rule ever fire on, as a function of M?  (spec-geometry audit)
    Brackets are cap-floor = 1 wide (e.g. B64.5 = floor 64, cap 65), so lo+M <= E <= hi-M needs M <= 0.5 and, at 1-minute
    (integer-degree) resolution, E == lo+0.5 which an integer can never equal."""
    groups = collections.defaultdict(list)
    for r in uni_list:
        groups[(r["station"], r["kind"], r["day_start"], r["day_end"])].append(r)
    cnt = collections.Counter()
    widths = collections.Counter(round(r["hi"] - r["lo"], 3) for r in uni_list)
    frac_E = collections.Counter()
    for (st, kind, S, E), rungs in groups.items():
        src, ts, fs = pick_source(st, S, E)
        if not fs:
            continue
        wk = walk(ts, fs, kind)
        for r in rungs:
            for M in (0.0, 0.25, 0.5, 1.0):
                if fire_for_rung(wk, r["lo"], r["hi"], M, 2.0, 120, r["close_ts"]):
                    cnt[(src, M)] += 1
        # fractional-degree share of final extremes
        ext = max(fs) if kind == "max" else min(fs)
        frac_E[(src, "integer" if abs(ext - round(ext)) < 1e-9 else "fractional")] += 1
    return {"bracket_width_cap_minus_floor_counts": {str(k): v for k, v in widths.items()},
            "literal_fires_R2_W120_by_source_and_M": {f"{k[0]}|M={k[1]}": v for k, v in sorted(cnt.items())},
            "final_extreme_is_integer_degree": {f"{k[0]}|{k[1]}": v for k, v in sorted(frac_E.items())}}

# ----------------------------------------------------------------------------- markdown
def _f(x, nd=2, pct=False):
    if x is None:
        return "n/a"
    if pct:
        return f"{100 * x:.1f}%"
    return f"{x:.{nd}f}"

def _row(r):
    e, v = r["ev_eq"], r["ev_vw"]
    return (f"| {r['cell'][0]} | {r['cell'][1]:.0f} | {r['cell'][3]} | {r['L']} | {r['n_fires']} | {r['n_fires_candle_sampled']} | "
            f"{r['n_priced']} | {_f(r['untradeable_frac'], pct=True)} | {_f(r['false_lock_rate_all'], pct=True)} "
            f"(UB {_f(r['wilson_ub_all'], pct=True)}) | {_f(e.get('mean'))} | {_f(v.get('mean'))} | "
            f"{_f(e.get('t'))} / {_f(v.get('t'))} | {r['n_days']} | {r['n_stations']} |")

def subgroup_table(sig, uni, results):
    """Descriptive only (obs + official result; no prices): false-lock by where E sits and by feed."""
    fl = [f for f in sig["fires"] if f["variant"] == "lattice" and tuple(f["cell"]) == PRIMARY]
    c = collections.defaultdict(lambda: [0, 0])
    for f in fl:
        r = uni[f["ticker"]]
        pos = "E==lo" if f["E"] == r["lo"] else ("E==hi" if f["E"] == r["hi"] else "E fractional")
        c[(r["kind"], pos, f["src"])][0] += 1
        c[(r["kind"], pos, f["src"])][1] += f["result"] == "no"
    rows = []
    for k, (n, kf) in sorted(c.items()):
        p, lo_, hi_ = wilson(kf, n)
        rows.append({"kind": k[0], "E_position": k[1], "feed": k[2], "n": n, "false_locks": kf, "rate": p, "wilson_ub": hi_})
    return rows

def write_md(rep, results, sig, uni):
    L = []
    A = L.append
    ev = rep["evaluation"]
    U = rep["universe"]
    S = rep["sampling"]
    A("# TERMINAL FINALITY -- Build B (independent replication) -- RESULT\n")
    A(f"**Verdict (frozen spec, literal reading): `{rep['verdict']}`** -- see 'Why INSUFFICIENT and not PASS or KILL'. "
      "No PASS under any reading; the only reading under which the rule fires at all fails the false-lock bar by ~5x.\n")
    A("Reproduce: `python venue_expansion/finality_B.py discover|obs|signal|oracle|candles` then "
      "`python -c \"import finality_B as F; F.cmd_report()\"`. Cache: `cache/finality/B/` (own namespace). "
      "Numbers: `out/finality_B.json`.\n")
    A("## 0. Headline\n")
    A(rep["headline"] + "\n")
    A("## 1. SAMPLING -- read this first\n")
    A(f"* **Signal walk: 100% of the universe** ({U['n_bracket_rungs']:,} bracket rungs, {U['n_events']:,} event-days, "
      f"{U['n_series']} series, {U['n_stations']} stations, closes {U['close_span'][0]} .. {U['close_span'][1]}). The FINAL-YES signal needs "
      "observations only, so no sampling was needed for signals, false-lock rates or the geometry audit.\n"
      f"* **Candlestick (price) pulls: {S['prefix_done']:,} of {S['fired_rungs_total']:,} fired rungs = "
      f"{100 * S['sampling_fraction_of_fired_rungs']:.1f}%.** Fired rungs were put in a **seeded shuffled order** (seed {SEED}), saved to "
      "`cache/finality/B/candle_work_order.json`, and **never re-sorted**; pricing statistics use the longest completed prefix of that order, "
      "so the priced set is itself a uniform random subsample of fires (an earlier study here produced a biased series-ordered prefix; this one cannot). "
      "Precision, not validity, is what the truncation costs.\n"
      "* Pricing statistics apply only to the **exploratory** 'lattice' variant (the literal variant never fires, so nothing needs pricing).\n")
    A("## 2. Universe, skips, feed coverage\n")
    A("| item | count |\n|---|---:|")
    A(f"| settled bracket rungs in universe (48 US series, closes 2026-05-23..2026-10-20, official yes/no) | {U['n_bracket_rungs']:,} |")
    for k, v in sorted(U["skip"].items()):
        A(f"| skipped: {k} | {v:,} |")
    for k, v in sorted(U["obs_coverage"].items()):
        A(f"| obs coverage: {k} | {v:,} |")
    A("\nSources: live `/markets?status=settled` (Kalshi serves only ~2026-08-21 onward there) **plus** `/historical/markets` "
      "(everything settled before the 2026-08-28 historical cutoff). Candles come from `/series/.../candlesticks` after the cutoff and "
      "`/historical/markets/{ticker}/candlesticks` before it (historical rows use `close` rather than `close_dollars`; "
      "aliased, values untouched, then parsed by the reused `edge_sizing_v2.normalize()`). International series (EGLL, LFPG, RJTT, ...) have no "
      "settled markets in the live listing and no verified IEM 1-minute station map; 'series_not_in_verified_US_station_map' counts only what "
      "the live listing returned (" + ", ".join(f"{k}:{v}" for k, v in sorted(U.get("unmapped_series_rows", {}).items())) + "). Four US series not in the old stage-2 city map (EWR, SAN, SDF, TTN) were added with standard offsets confirmed by close-hour.\n")
    A("## 3. The frozen geometry cannot fire (spec defect, found by audit)\n")
    g = rep["geometry"]
    A(f"Every one of the {U['n_bracket_rungs']:,} bracket rungs has `cap_strike - floor_strike = 1` (e.g. `B64.5` = floor 64, cap 65; it settles YES on "
      "whole-degree values 64 or 65). The spec's condition `lo+M <= E <= hi-M` with `[lo,hi]=[floor,cap]` therefore needs `M <= 0.5`, and at `M=0.5` "
      "it needs `E = lo+0.5` exactly. Observed day extremes are whole degrees " + "(" + ", ".join(f"{k}: {v}" for k, v in g["final_extreme_is_integer_degree"].items()) + " event-days), so:\n")
    A("| literal rule, R=2, W=120 | rungs that ever fire |\n|---|---:|")
    for k, v in g["literal_fires_R2_W120_by_source_and_M"].items():
        A(f"| {k} | {v:,} |")
    A("| any source, M=0.5 | 0 |\n| any source, M=1.0 (primary cell) | 0 |\n")
    A("**All 8 frozen cells x 3 latency arms have n = 0 fires under the literal reading.** M=0 would fire (" + f"{sum(v for k, v in g['literal_fires_R2_W120_by_source_and_M'].items() if k.endswith('M=0.0')):,}" + " rungs at R=2, W=120) but M=0 is not in the frozen grid and "
      "is exactly what the margin was meant to exclude. I did not alter the grid. As a clearly-labelled, PASS-ineligible **post-hoc** reading I also ran the 'lattice' "
      "variant: bracket widened by one whole degree each side (`[lo-1, hi+1]`), i.e. the margin M is measured from the nearest whole-degree value that would flip the "
      "outcome. Under it M=1.0 means `E in {lo, hi}` (and M=0.5 is the same set on integer data). Everything below labelled 'lattice' is exploratory.\n")
    A("## 4. Primary cell (M=1.0, R=2, H=3, W=120)\n")
    pl = results[("literal", PRIMARY, 10)]
    A(f"* **Literal (the frozen spec): n fires = {pl['n_fires']}, priced = 0, untradeable = n/a at L=0/10/20.** False-lock rate undefined (0/0). Nothing to test.")
    pp = results[("lattice", PRIMARY, 10)]
    A(f"* **Lattice (exploratory) at L=10:** fires {pp['n_fires']:,}; **false locks {pp['n_false_lock_all']:,} = {_f(pp['false_lock_rate_all'], pct=True)} "
      f"(Wilson 95% UB {_f(pp['wilson_ub_all'], pct=True)})** vs bars of <=2% / <=5% -> the finality inference is wrong on 1 in 4 rungs. "
      f"Priced {pp['n_priced']:,} of {pp['n_fires_candle_sampled']:,} sampled fires "
      f"(untradeable {_f(pp['untradeable_frac'], pct=True)}); EV equal-weight {_f(pp['ev_eq'].get('mean'))}c, volume-weighted {_f(pp['ev_vw'].get('mean'))}c; "
      f"signed day-clustered t = {_f(pp['ev_eq'].get('t'))} (eq) / {_f(pp['ev_vw'].get('t'))} (vw); days {pp['n_days']}, stations {pp['n_stations']}.\n")
    sp = rep["lattice_primary_L10_split"]
    A("Adverse selection among the priced fires (lattice, primary cell, L=10; descriptive):\n")
    A("| priced fires that settled | n | mean entry ask (c) | mean net P&L (c) | share entered at ask>=90c | share entered at ask<=10c |\n|---|---:|---:|---:|---:|---:|")
    for k, v in sp.items():
        A(f"| {k} | {v['n']} | {_f(v['mean_entry_ask_c'], 1)} | {_f(v['mean_net_pnl_c'], 1)} | {_f(v['share_entered_at_ask>=90c'], pct=True)} | {_f(v['share_entered_at_ask<=10c'], pct=True)} |")
    h90 = rep["lattice_primary_L10_entries_ask_ge_90"]
    A(f"\nFalse-lock rate among ALL fires {_f(pp['false_lock_rate_all'], pct=True)} but among PRICED fires {_f(rep['lattice_primary_L10_priced_false_lock_rate'], pct=True)}: "
      "the minutes at which YES is still offered at <=98c are disproportionately the minutes at which the market already knows the feed extreme is not the official one "
      f"(cheap YES asks on rungs that then lose). Entries at ask>=90c (market agrees with the signal): n={h90['n']}, false locks {h90['false_locks']}, mean net {_f(h90['mean_net_pnl_c'])}c.\n")
    A("## 5. All cells\n")
    hdr = ("| M | R | W | L | fires (all) | fires (candle-sampled) | priced | untradeable | false-lock (Wilson UB) | EV eq c | EV vw c | t eq / vw | days | stations |\n"
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for variant in ("literal", "lattice"):
        A(f"### {variant} variant" + (" (frozen spec)" if variant == "literal" else " (EXPLORATORY, not eligible for PASS)") + "\n")
        A(hdr)
        for cell in CELLS:
            for Lx in LS:
                A(_row(results[(variant, cell, Lx)]))
        A("")
    A("## 6. Bars at L=10 (literal variant = frozen spec)\n")
    A(f"* PASS cells: {ev['pass_cells'] or 'none'}\n* KILL clause 1 (false-lock > 5% in primary cell): {ev['kill_false_lock_primary']} (primary cell has 0 fires: not evaluable)\n"
      f"* KILL clause 2 (every cell with EV>0 fails n>=100): {ev['kill_all_positive_cells_fail_n']} (no literal cell has an EV at all, so it is vacuous, not met on evidence)\n"
      f"* KILL clause 3 (best one-sided 97.9% UB on EV < +0.5c): {ev['kill_best_ub979_lt_0.5']} (best UB = {ev['best_ub979_ev_vw']}; undefined with n=0)\n")
    A("### Why INSUFFICIENT and not PASS or KILL\n")
    A("Zero literal fires: PASS is impossible, and each KILL clause is either unevaluable (no fires, no EV, no UB) or vacuously true on an empty set -- a KILL on "
      "vacuity would be a verdict by technicality, not evidence. The spec says 'anything else -> INSUFFICIENT', and that is the only honest label for a rule whose "
      "frozen parameters select the empty set. **But do not read INSUFFICIENT as 'maybe'.** The single reading under which the rule fires fails clause 1 of KILL by a wide margin "
      "(lattice primary-cell false-lock rate above), and its EV (section 5, lattice) is what the bars would call a KILL as well.\n")
    A("## 7. Descriptive follow-up (obs + official result only; no price; NOT a test)\n")
    A("Lattice primary-cell fires split by where the extreme sits in the bracket and by feed. This is post-hoc description of why the false-lock rate is ~24%, "
      "not a candidate strategy; any rule built from it would need a fresh pre-registration and forward data.\n")
    A("| kind | E position | feed | n | false locks | rate | Wilson UB |\n|---|---|---|---:|---:|---:|---:|")
    for r in rep["subgroups"]:
        A(f"| {r['kind']} | {r['E_position']} | {r['feed']} | {r['n']} | {r['false_locks']} | {_f(r['rate'], pct=True)} | {_f(r['wilson_ub'], pct=True)} |")
    A("\nFeed extreme minus official `expiration_value` (whole degF, numeric-value markets only, i.e. settled after the 2026-08-28 cutoff; no outcomes of rungs used):\n")
    A("| kind|feed | " + " | ".join(["-3", "-2", "-1", "0", "+1", "+2", "+3"]) + " |\n|---|---|---|---|---|---|---|---|")
    for k, v in rep["tz_diag"]["feed_minus_official_extreme_degF_dist"].items():
        tot = sum(v.values())
        A(f"| {k} (n={tot}) | " + " | ".join(f"{100 * v.get(str(i), 0) / tot:.0f}%" for i in range(-3, 4)) + " |")
    A("\nMechanism: the IEM/ASOS day extreme and the official settlement value disagree by 1 degF on about half of HIGH days and 15-40% of LOW days (table above) and the bias is one-sided "
      "(HIGH: IEM 1-min max is >= official; routine hourly max is <= official because hourly sampling misses the peak). Rungs are only 2 whole degrees wide, so a "
      "1-degree feed disagreement flips the winner. A symmetric margin cannot fix a one-sided bias.\n")
    A("## 8. Anchors\n")
    a = rep["anchors"]
    A("**(a) Oracle reconciliation.**\n")
    a1 = a["a"]["a1_oracle_rows_reproduced"]
    A(f"* The 140 EDGE_SIZING-capturable rows (`out/edge_sizing_stage2.json: per_market`) were re-priced from my own candle pull with an independent "
      f"recomputation of the Stage-1 rule: {a1['candles_available']} had candles; minute-count matches {a1['n_minutes_match']}, first-capturable-ts matches {a1['first_ts_match']}, "
      f"last-capturable-ts matches {a1['last_ts_match']}. Mismatch examples (if any): {a1['mismatch_examples'][:3]}.")
    a2 = a["a"]["a2_subset_check"]
    A(f"* Subset check: every priced YES-settled lattice fire (L=0) whose entry lies in the final 60 min -- {a2['priced_yes_fires_checked_(entry_in_final_60m)']} checked -- must be "
      f"oracle-capturable on that rung; violations: **{a2['n_violations']}**. Fires entered 60-120 min before close ({a2['yes_fires_entered_before_final_60m_(outside_oracle_window)']}) are outside "
      f"the oracle's 60-min window by construction; priced false locks ({a2['false_locks_priced_(not_applicable_to_winner_side_oracle)']}) are not winner-side events.")
    A("* **Limit, disclosed:** the oracle's own sample membership (`stage1_v2.jsonl`, `population.json`) is not on disk in this checkout, so the check cannot enumerate which "
      "rungs the oracle *sampled and found non-capturable*; the reproduction of the 140 rows is the strongest available test of the price join.\n")
    b = a["b"]
    A(f"**(b) No look-ahead.** The signal decision time is `t_sig = ts(obs_i) + 60 s`, so every input has timestamp < t_sig. In code (`anchor_b`), {b['checked']} fires "
      f"(all primary-cell fires + a seeded random sample) were re-evaluated by an independent brute-force function that sees ONLY obs with ts < t, "
      f"confirmed *first* (no earlier decision time qualifies), and survived a perturbation test (every obs with ts >= t replaced by +/-extreme garbage -> same fire). "
      f"Passed {b['passed']}/{b['checked']}; failures: {b['failures']}. Worked example: {b['worked_example']}\n")
    A(f"**(c) Monotonicity.** Running max non-decreasing / running min non-increasing within every local day: **{a['c']['monotone_violations']} violations** over all walked days.\n")
    A("## 9. Timezone handling, proven\n")
    A("The market day is the NWS local **standard-time** day. Kalshi's `close_time` is exactly local-standard-midnight + 24 h year-round "
      "(e.g. `06:00Z` for CST cities all year, `08:00Z` for Seattle in July even though the wall clock there is PDT), verified for every series by close-hour "
      "(`cmd_tzcheck`; the universe builder *drops* any rung whose close-hour disagrees with the station's standard offset). Historical rows close at `HH:59Z`, so the day end is "
      "`round(close_time to nearest hour)`; day start = day end - 24 h; the extreme is accumulated only over that window; obs are UTC epochs; candle `end_period_ts` are UTC epochs; "
      "the terminal window is `[close_time - W min, close_time]` in the same UTC epochs.\n")
    w = rep["worked_example"]
    if w:
        A("Worked example (real priced fire):\n")
        A("```")
        for k, v in w.items():
            A(f"{k}: {v}")
        A("```")
    A("\nIndependent check that the window is right (no outcomes used): obs-derived day extreme vs the market's numeric `expiration_value` "
      "(available for markets settled after the historical cutoff), under window shifts of -3..+3 h. Share within 0.5 degF:\n")
    A("| window shift (h) | HIGH match share (n) | LOW match share (n) |\n|---:|---:|---:|")
    tzm = rep["tz_diag"]["match_rate_by_window_shift_hours"]
    for k in sorted(tzm["max"], key=int):
        hv, lv = tzm["max"][k], tzm["min"].get(k, [None, 0])
        A(f"| {k} | {hv[0]:.3f} ({hv[1]}) | {_f(lv[0], 3)} ({lv[1]}) |")
    A("\n(Same events for every shift, 1-min feed only. The unshifted window is the maximum for both kinds. HIGH is nearly flat (the afternoon plateau is broad and the 1 degF feed bias dominates the match rate); "
      "LOW markets, whose extreme sits in a narrow pre-dawn band, lose 6-22 points when the window is shifted, which is what a wrong timezone would look like. "
      "The extreme's local-standard hour (below) is physically right: HIGH mode 14:00 LST (=15:00 DST), LOW mode 04:00-05:00 LST. The residual mismatch at shift 0 is the 1 degF feed bias tabulated above, not a timezone error.)\n")
    A("Local-standard hour of the day's extreme (shift 0): " + json.dumps(rep["tz_diag"]["argext_local_std_hour_hist"]) + "\n")
    A("## 10. Interpretation choices (where Build A may differ -- this is where a disagreement would come from)\n")
    for s_ in rep["choices"]:
        A("* " + s_)
    A("\n## 11. What this does and does not say\n")
    A(rep["closing"] + "\n")
    open(OUT_MD, "w").write("\n".join(L))


if __name__ == "__main__":
    cmds = {"discover": lambda: (cmd_discover(), cmd_discover_hist()), "obs": cmd_obs, "signal": cmd_signal,
            "candles": lambda: cmd_candles(), "oracle": cmd_oracle_fetch, "tz": cmd_tzcheck, "analyze": lambda: cmd_report()}
    cmds[sys.argv[1]]()
