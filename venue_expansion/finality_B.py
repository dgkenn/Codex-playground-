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

CACHE = os.path.join(HERE, "cache", "finality")
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
            for variant, (lo, hi) in (("literal", (r["lo"], r["hi"])), ("rounded", (r["lo"] - 0.5, r["hi"] + 0.5))):
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
    results = {}
    for variant in ("literal", "rounded"):
        for cell in CELLS:
            fl = [f for f in sig["fires"] if f["variant"] == variant and tuple(f["cell"]) == cell]
            k_all = len(fl)
            k_fl = sum(1 for f in fl if f["result"] == "no")
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
                    "n_fires": k_all, "n_false_lock_all": k_fl,
                    "false_lock_rate_all": fl_all[0], "wilson_ub_all": fl_all[2],
                    "n_priced": n, "n_untradeable": k_all - n, "untradeable_breakdown": dict(unt),
                    "untradeable_frac": ((k_all - n) / k_all) if k_all else None,
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
    return results, sig, uni_list

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
        lo, hi = (r["lo"], r["hi"]) if f["variant"] == "literal" else (r["lo"] - 0.5, r["hi"] + 0.5)
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
            if ex is None and f["variant"] == "literal" or (ex is None and f["variant"] == "rounded"):
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
    extreme with the market's published expiration_value (the NWS value the market settled on), under window
    shifts of -3..+3 hours.  The true window should dominate the match rate."""
    if uni is None:
        uni = jload(os.path.join(CACHE, "universe.json"))
    seen, per = set(), collections.defaultdict(lambda: collections.defaultdict(list))
    hist_hour = collections.defaultdict(collections.Counter)
    for r in uni:
        k = (r["series"], r["day_end"])
        if k in seen or r["exp_val"] in (None, ""):
            continue
        seen.add(k)
        try:
            ev = float(r["exp_val"])
        except Exception:
            continue
        for dh in range(-3, 4):
            S, E = r["day_start"] + dh * 3600, r["day_end"] + dh * 3600
            src, ts, fs = pick_source(r["station"], S, E) if dh == 0 else ("1min",) + window_obs(r["station"], "1min", S, E)
            if not fs:
                continue
            ext = max(fs) if r["kind"] == "max" else min(fs)
            per[r["series"]][dh].append(abs(ext - ev) < 0.5)
            if dh == 0:
                i = fs.index(ext)
                lh = ((ts[i] + r["off"] * 3600) // 3600) % 24
                hist_hour[r["kind"]][lh] += 1
    tot = collections.defaultdict(list)
    for s, d in per.items():
        for dh, v in d.items():
            tot[dh].extend(v)
    rate = {dh: (sum(v) / len(v), len(v)) for dh, v in sorted(tot.items())}
    by_series = {s: {"n": len(d[0]), "match_dh0": round(sum(d[0]) / len(d[0]), 3) if d.get(0) else None} for s, d in per.items()}
    return {"match_rate_by_window_shift_hours": {str(k): [round(v[0], 4), v[1]] for k, v in rate.items()},
            "by_series_dh0": by_series, "argext_local_std_hour_hist": {k: dict(sorted(v.items())) for k, v in hist_hour.items()}}
