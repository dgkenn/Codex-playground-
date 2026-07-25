#!/usr/bin/env python3
"""spec_S3.py -- PRE-REGISTERED spec S3: "ForecastEx daily-temperature lock study: false-lock rate +
flat-fee EV on the venue's own trade tape". Executed EXACTLY as registered in
venue_expansion/out/judge_specs.json (id "S3"). Nothing below was tuned after seeing real ForecastEx or
IEM 1-minute data -- every threshold, margin, window and bar is copied verbatim from that frozen text.

WHAT THIS MEASURES: ForecastEx's Daily Temperature Forecast Contracts (product codes UH<STA>/UL<STA>,
"highest/lowest temperature [exceeds/is below] X F") are UNCAPPED one-sided thresholds -- the native shape
of the deployed Kalshi mechanical-lock rule (kwx_lock_rule.py, byte-identical shim, see that file's own
docstring for provenance). This script walks each candidate station's TRUE 1-minute IEM ASOS stream
forward in time, fires the deployed sustain-3 / 1.0F-margin lock rule OBS-ONLY (no price or outcome input
in the signal, per the spec's own "Signal uses obs only" clause -- this is why the lock check below does
NOT call kwx_lock_rule.locked_orders() directly: that function's floor/cap branches are pure obs-vs-strike
math but it ALSO gates on a live ask price (`MAX_PAY_CENTS` check) which is exactly the price-conditioned
signal GROUNDING.md non-negotiable #4 forbids -- the branch is reproduced here as `obs_only_fire()`,
IDENTICAL floor+margin / cap-margin comparison, price-gate removed, disclosed here rather than silently),
prices every lock off the venue's own pairs-tape (first fill at/after lock + 1.0c disclosed slippage
proxy), and scores every lock against the venue's own daily_prices settlement (no WU scraping).

DATA SOURCES (recon-verified in venue_expansion/out/venues_us.json):
  - Obs:  IEM TRUE 1-minute ASOS archive (asos1min.py), bare station codes MDW/LGA/LAX/SFO/SEA/PHX --
          same endpoint/semantics Track A verified for ORD (tracka_chicago_1min.py), reused unmodified.
  - Rungs + settlement ground truth: forecastex-public-data.s3.amazonaws.com/prices/daily_prices_*.csv.
    MEASURED (not assumed) file-date convention, disclosed: a contract embedding forecast-day D in its
    ticker (UH<STA>_<mmddyy(D)>_<strike>) reaches its TRUE settlement_price (1.00/0.00) in the file dated
    D+1, not D -- verified directly (UHSFO_072126_74 read 0.98 mid-day-close in prices_20260721.csv but
    1.00 in prices_20260722.csv), consistent with the contract text's "resolution time = when the first
    obs of the SUBSEQUENT calendar day is published" (~03:00 local next day). This script always reads
    settlement from the D+1 file.
  - Entry fills: forecastex-public-data.s3.amazonaws.com/pairs/pairs_*.csv. MEASURED (not assumed) file-
    date convention, disclosed: pair_time inside file pairs_YYYYMMDD.csv spans roughly
    [YYYYMMDD-1 16:15 America/Chicago, YYYYMMDD 16:14 America/Chicago] -- i.e. an exchange trading-day
    convention keyed to Chicago local time, NOT the UTC or station-local calendar date of the fill
    (verified directly: pairs_20260722.csv contains 5,913 fills timestamped 2026-07-21 16:15-23:59 CT and
    15,097 timestamped 2026-07-22 00:00-16:14 CT). To guarantee a lock's full [lock, lock+60min] search
    window is covered regardless of this offset, every lock's fill search pulls BOTH pairs files dated
    {chicago_date(lock_utc), chicago_date(lock_utc)+1} -- provably sufficient given the measured boundary
    (see in-line comment on `pairs_dates_needed`).

FIDELITY: kwx_lock_rule.sustained_extreme is called THROUGH an O(1)-amortized incremental wrapper
(`IncrementalSustain`) instead of literally re-invoking it on the ever-growing obs-so-far window at every
minute (O(n^2), infeasible at this study's ~350-day x 6-station x ~1440 obs/day scale). The wrapper
reproduces sustained_extreme's own per-endpoint window-growth math verbatim (same GLITCH_HI/LO/jump
filter, same span_need/max_gap) and exploits that sustained_extreme(window[:i]) is monotonic
non-decreasing in i (adding a point can only ever raise or hold the best qualifying window-min already
found, never lower it -- earlier candidates stay valid). A same-script self-test (`_validate_incremental`)
brute-force-calls the REAL R.sustained_extreme() at 40 sampled checkpoints on a real fetched day and
asserts byte-for-byte numeric equality before any study number is trusted; the run aborts loudly if it
ever disagrees. No lock-rule math is changed, only its evaluation is restructured for O(n) total time.

Read-only, public APIs only (IEM Mesonet + forecastex-public-data S3), no auth, no orders, no trading
code. Polite: cached under venue_expansion/cache/forecastex_study/, retried with backoff, ~1 req/sec.

USAGE:
  python spec_S3.py                 # full run (guard -> tripwire -> full backtest -> verdict)
  python spec_S3.py --cached-only   # recompute from cached pulls only, no network
"""
import csv
import io
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
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kwx_lock_rule as R  # deployed lock-rule shim: sustained_extreme + frozen constants (see its docstring)

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "*/*", "User-Agent": "Mozilla/5.0 (compatible; spec-S3/1.0; research, read-only)"}

ASOS_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
FX_BASE = "https://forecastex-public-data.s3.amazonaws.com"

CACHE_DIR = os.path.join(HERE, "cache", "forecastex_study")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHED_ONLY = "--cached-only" in sys.argv

# ------------------------------------------------------------------------------------------------------
# UNIVERSE -- verbatim from the spec's candidate-station list.
# ------------------------------------------------------------------------------------------------------
STATIONS = {
    "MDW": dict(tz="America/Chicago"),
    "LGA": dict(tz="America/New_York"),
    "LAX": dict(tz="America/Los_Angeles"),
    "SFO": dict(tz="America/Los_Angeles"),
    "SEA": dict(tz="America/Los_Angeles"),
    "PHX": dict(tz="America/Phoenix"),
}
CT_TZ = ZoneInfo("America/Chicago")

WINDOW_START = dt.date(2025, 8, 1)
WINDOW_END = dt.date(2026, 7, 18)
WINDOW_DAYS = (WINDOW_END - WINDOW_START).days + 1  # 352

TRIPWIRE_END = WINDOW_START + dt.timedelta(days=29)  # first 30 window days, inclusive

GUARD_MIN_OBS_PER_DAY = 100     # verbatim, spec + Track A precedent (pmkt_gap_study established value)
GUARD_MIN_DAY_FRACTION = 0.70   # verbatim, spec
DAY_USABLE_MAX_END_GAP_H = 3    # Track A precedent (MAX_END_GAP_H_1MIN), reused for per-day usability only
                                 # (NOT part of the station-level guard test itself, which is obs-count-only
                                 # per the spec's literal wording -- disclosed, not silently added to the guard)

MARGIN_F = R.MARGIN_F           # 1.0, byte-identical import
SLIPPAGE_C = 1.0
FEE_C = 1.0
MAX_FILL_WAIT_MIN = 60

Z_9833 = 2.128                  # one-sided 98.33%, Bonferroni-3 family (out/judge_specs.json)
T_BAR = 2.25

TICKER_RE = re.compile(r"^(UH|UL)([A-Z]{3})_(\d{6})_(-?\d+(?:\.\d+)?)$")


# ============================================================================================================
# HTTP + cache plumbing (same shape as tracka_chicago_1min.py / spec_S1.py / spec_S2.py)
# ============================================================================================================
def _get_text(url, timeout=60, retries=5, backoff=2.0):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            r = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
            return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 404:
                return None
            if e.code not in (429, 500, 502, 503, 504):
                return None
            time.sleep(backoff * (attempt + 1))
        except Exception as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
    print(f"    [fetch FAILED after retries] {url} :: {last_err}", file=sys.stderr)
    return None


def _cache_path(name):
    return os.path.join(CACHE_DIR, name)


def _cache_get_json(name):
    p = _cache_path(name)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        try:
            return json.load(open(p))
        except Exception:
            return None
    return None


def _cache_put_json(name, obj):
    json.dump(obj, open(_cache_path(name), "w"))


def _cache_get_csv(name):
    p = _cache_path(name)
    if os.path.exists(p):
        if os.path.getsize(p) == 0:
            return None  # cached-empty sentinel (404 / no listing that day)
        return open(p, "r", encoding="utf-8", errors="replace").read()
    return None


def _cache_put_csv(name, text):
    with open(_cache_path(name), "w", encoding="utf-8") as f:
        f.write(text or "")


# ============================================================================================================
# FEED A -- IEM TRUE 1-minute ASOS archive. Fetched in ~28-day chunks per station, padded 1 day each side of
# the window for correct local-day bucketing at the edges. Cached per chunk.
# ============================================================================================================
def fetch_iem_1min_chunk(station, start_utc, end_utc):
    key = f"iem1min_{station}_{start_utc:%Y%m%dT%H%M}_{end_utc:%Y%m%dT%H%M}.json"
    cached = _cache_get_json(key)
    if cached is not None:
        return [(dt.datetime.fromisoformat(t), v) for t, v in cached]
    if CACHED_ONLY:
        return []
    sts = start_utc.strftime("%Y-%m-%dT%H:%MZ")
    ets = end_utc.strftime("%Y-%m-%dT%H:%MZ")
    q = f"station={station}&vars=tmpf&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma"
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
    _cache_put_json(key, [(t.isoformat(), v) for t, v in out])
    time.sleep(1.0)
    return out


def fetch_station_stream(station):
    """Full padded-window 1-min stream for one station, ~28-day chunks, deduped+sorted."""
    span_start = dt.datetime.combine(WINDOW_START - dt.timedelta(days=1), dt.time(0, 0), tzinfo=dt.timezone.utc)
    span_end = dt.datetime.combine(WINDOW_END + dt.timedelta(days=2), dt.time(0, 0), tzinfo=dt.timezone.utc)
    chunk = dt.timedelta(days=28)
    by_ts = {}
    c = span_start
    while c < span_end:
        c_end = min(c + chunk, span_end)
        rows = fetch_iem_1min_chunk(station, c, c_end)
        for t, v in rows:
            by_ts[t] = v
        c = c_end
    return sorted(by_ts.items())


def bucket_by_local_day(stream, tz):
    days = {}
    for t, v in stream:
        d = t.astimezone(tz).date()
        days.setdefault(d, []).append((t, v))
    for d in days:
        days[d].sort(key=lambda x: x[0])
    return days


# ============================================================================================================
# FEED B -- ForecastEx pairs/prices CSVs.
# ============================================================================================================
def fetch_fx_csv(kind, date_str):
    subdir = "prices" if kind == "prices" else "pairs"
    fname_prefix = "daily_prices" if kind == "prices" else "pairs"
    cache_name = f"{kind}_{date_str}.csv"
    cached = _cache_get_csv(cache_name)
    if cached is not None:
        return cached
    if CACHED_ONLY:
        return None
    url = f"{FX_BASE}/{subdir}/{fname_prefix}_{date_str}.csv"
    txt = _get_text(url)
    _cache_put_csv(cache_name, txt or "")
    time.sleep(1.0)
    return txt


_PRICES_CACHE = {}   # date_str -> (settlement_by_ticker dict, rungs_by_group dict) or None (fetch failed)
_PAIRS_CACHE = {}    # date_str -> (ticker -> sorted [(utc_dt, yes_price_c)]) or None (fetch failed)


def load_prices_index(date_str):
    if date_str in _PRICES_CACHE:
        return _PRICES_CACHE[date_str]
    txt = fetch_fx_csv("prices", date_str)
    if not txt:
        _PRICES_CACHE[date_str] = None
        return None
    settle = {}
    groups = {}
    rdr = csv.reader(io.StringIO(txt))
    header = next(rdr, None)
    for row in rdr:
        if len(row) < 9:
            continue
        event_contract, subtype = row[0], row[1]
        if subtype != "YES":
            continue
        m = TICKER_RE.match(event_contract)
        if not m:
            continue
        side, sta, mmddyy, strike_s = m.groups()
        if sta not in STATIONS:
            continue
        settlement_raw = row[8]
        try:
            settle_v = float(settlement_raw)
        except ValueError:
            settle_v = None
        settle[event_contract] = settle_v
        groups.setdefault((side, sta, mmddyy), []).append((float(strike_s), event_contract))
    result = (settle, groups)
    _PRICES_CACHE[date_str] = result
    return result


def load_pairs_index(date_str):
    if date_str in _PAIRS_CACHE:
        return _PAIRS_CACHE[date_str]
    txt = fetch_fx_csv("pairs", date_str)
    if not txt:
        _PAIRS_CACHE[date_str] = None
        return None
    idx = {}
    rdr = csv.reader(io.StringIO(txt))
    header = next(rdr, None)
    for row in rdr:
        if len(row) < 7:
            continue
        event_contract, yes_price, pair_time = row[1], row[4], row[6]
        m = TICKER_RE.match(event_contract)
        if not m or m.group(2) not in STATIONS:
            continue
        try:
            ts = dt.datetime.fromisoformat(pair_time.strip())
            ts_utc = ts.astimezone(dt.timezone.utc)
            price_c = float(yes_price) * 100.0
        except (ValueError, TypeError):
            continue
        idx.setdefault(event_contract, []).append((ts_utc, price_c))
    for k in idx:
        idx[k].sort(key=lambda x: x[0])
    _PAIRS_CACHE[date_str] = idx
    return idx


def rungs_for_day(station, d, side):
    """side: 'UH' or 'UL'. Settlement/rung menu is read from the D+1 file (see module docstring). Returns
    (rungs, fetch_ok) where rungs = [{'ticker','strike','settlement'}], fetch_ok=False means the prices
    pull itself failed (network) -- distinct from an empty listing (station simply not listed that day)."""
    d1 = d + dt.timedelta(days=1)
    date_str = d1.strftime("%Y%m%d")
    idx = load_prices_index(date_str)
    if idx is None:
        return [], False
    settle, groups = idx
    key = (side, station, d.strftime("%m%d%y"))
    lst = groups.get(key, [])
    rungs = [{"ticker": tk, "strike": strike, "settlement": settle.get(tk)} for strike, tk in lst]
    return rungs, True


def pairs_dates_needed(lock_utc):
    """MEASURED boundary: file pairs_YYYYMMDD.csv spans roughly [YYYYMMDD-1 16:15 CT, YYYYMMDD 16:14 CT].
    For any lock_utc whose Chicago-local calendar date is `ct`, file `ct` covers ct's own 00:00-16:14 CT
    and file `ct+1` covers ct 16:15 CT through ct+1 16:14 CT -- together a strict superset of
    [00:00 ct, 23:59:59 ct] + 60 minutes forward. Sufficient; no third file needed."""
    ct = lock_utc.astimezone(CT_TZ).date()
    return [ct.strftime("%Y%m%d"), (ct + dt.timedelta(days=1)).strftime("%Y%m%d")]


def first_fill_after_lock(ticker, lock_utc):
    candidates = []
    fetch_ok = True
    for ds in pairs_dates_needed(lock_utc):
        idx = load_pairs_index(ds)
        if idx is None:
            fetch_ok = False
            continue
        candidates.extend(idx.get(ticker, []))
    candidates.sort(key=lambda x: x[0])
    end = lock_utc + dt.timedelta(minutes=MAX_FILL_WAIT_MIN)
    for ts, price_c in candidates:
        if lock_utc <= ts <= end:
            return ts, price_c, fetch_ok
    return None, None, fetch_ok


# ============================================================================================================
# INCREMENTAL sustained_extreme -- see module docstring "FIDELITY". Reproduces R.sustained_extreme's own
# per-endpoint window-growth math verbatim; validated against the real function below before use.
# ============================================================================================================
def clean_obs(obs):
    """obs: [(dt, f)] ascending. IDENTICAL glitch filter to R.sustained_extreme's own `clean` construction."""
    clean = []
    prev = None
    for t, f in obs:
        if f is None or f > R.GLITCH_HI_F or f < R.GLITCH_LO_F:
            continue
        if prev is not None and abs(f - prev) > 8.0:
            prev = f
            continue
        prev = f
        clean.append((t, f))
    return clean


class IncrementalSustain:
    """Maintains running_best for one kind ('max' or 'min') across a monotonically-growing `clean` list.
    advance_to(j) must be called with j increasing by exactly 1 each time (0-based index into `clean`)."""

    def __init__(self, kind):
        self.sign = 1.0 if kind == "max" else -1.0
        self.span_need = dt.timedelta(minutes=max(0, R.SUSTAIN_MIN - 1))
        self.max_gap = dt.timedelta(minutes=R.SUSTAIN_MAX_GAP_MIN)
        self.best = None

    def advance_to(self, clean, j):
        tj = clean[j][0]
        wmin = self.sign * clean[j][1]
        i = j
        while tj - clean[i][0] < self.span_need and i > 0 and clean[i][0] - clean[i - 1][0] <= self.max_gap:
            i -= 1
            v = self.sign * clean[i][1]
            if v < wmin:
                wmin = v
        if tj - clean[i][0] >= self.span_need:
            if self.best is None or wmin > self.best:
                self.best = wmin
        return None if self.best is None else self.sign * self.best


def _validate_incremental(clean, kind, sample_idxs):
    """Brute-force cross-check against the REAL R.sustained_extreme() at sampled checkpoints. Aborts the
    run if any mismatch is found -- fidelity is load-bearing, not decorative."""
    inc = IncrementalSustain(kind)
    j = 0
    results_inc = {}
    for idx in range(len(clean)):
        val = inc.advance_to(clean, idx)
        if idx in sample_idxs:
            results_inc[idx] = val
    for idx in sample_idxs:
        if idx >= len(clean):
            continue
        window = [(t.isoformat(), f) for t, f in clean[: idx + 1]]
        brute = R.sustained_extreme(window, kind)
        inc_val = results_inc.get(idx)
        ok = (brute is None and inc_val is None) or (
            brute is not None and inc_val is not None and abs(brute - inc_val) < 1e-9
        )
        if not ok:
            raise RuntimeError(
                f"INCREMENTAL-SUSTAIN FIDELITY MISMATCH kind={kind} idx={idx}: brute={brute} inc={inc_val}"
            )
    return True


# ============================================================================================================
# Wilson CI + day-clustered t-stat -- IDENTICAL formulas to spec_S1.py / spec_S2.py (reused, not reinvented).
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
# PHASE 1 -- inclusion guard
# ============================================================================================================
def run_guard():
    print("=" * 100)
    print("PHASE 1 -- asos1min inclusion guard (>=100 obs/day on >=70% of window days)")
    print("=" * 100)
    guard = {}
    day_indices = {}  # station -> {date: [(t,v)...]}
    for sta in STATIONS:
        t0 = time.time()
        stream = fetch_station_stream(sta)
        days = bucket_by_local_day(stream, ZoneInfo(STATIONS[sta]["tz"]))
        day_indices[sta] = days
        n_total = WINDOW_DAYS
        n_ok = 0
        d = WINDOW_START
        while d <= WINDOW_END:
            if len(days.get(d, [])) >= GUARD_MIN_OBS_PER_DAY:
                n_ok += 1
            d += dt.timedelta(days=1)
        frac = n_ok / n_total
        survives = frac >= GUARD_MIN_DAY_FRACTION
        guard[sta] = {"days_ok": n_ok, "days_total": n_total, "fraction": round(frac, 4), "survives": survives}
        print(f"  {sta}: {n_ok}/{n_total} days >= {GUARD_MIN_OBS_PER_DAY} obs ({frac:.1%}) "
              f"-> {'SURVIVES' if survives else 'DROPPED'}  [{time.time()-t0:.1f}s]")
    survivors = [s for s in STATIONS if guard[s]["survives"]]
    print(f"\nSurvivors: {survivors} ({len(survivors)}/{len(STATIONS)})")
    return guard, survivors, day_indices


# ============================================================================================================
# Per-day lock walk (shared by tripwire + full backtest)
# ============================================================================================================
def walk_day_locks(station, d, day_obs, validate=False):
    """Returns list of lock dicts for one station-local day, using ONLY obs (no price/outcome input),
    for BOTH sides (UH via running max, UL via running min). Rungs (with settlement) are fetched from the
    ForecastEx prices file dated d+1. Returns (locks, fetch_ok, rung_counts)."""
    rungs_high, ok_h = rungs_for_day(station, d, "UH")
    rungs_low, ok_l = rungs_for_day(station, d, "UL")
    if not ok_h or not ok_l:
        return [], False, (0, 0)
    if not rungs_high and not rungs_low:
        return [], True, (0, 0)  # fetch fine, station simply not listed that day

    clean = clean_obs(day_obs)
    if not clean:
        return [], True, (len(rungs_high), len(rungs_low))

    if validate:
        sample_idxs = sorted(set(list(range(0, len(clean), max(1, len(clean) // 20)))[:20]))
        _validate_incremental(clean, "max", sample_idxs)
        _validate_incremental(clean, "min", sample_idxs)

    inc_max = IncrementalSustain("max")
    inc_min = IncrementalSustain("min")
    locked_high = {}  # ticker -> (lock_utc, extreme)
    locked_low = {}
    for j in range(len(clean)):
        ts = clean[j][0]
        ex_max = inc_max.advance_to(clean, j)
        ex_min = inc_min.advance_to(clean, j)
        if ex_max is not None and rungs_high:
            for r in rungs_high:
                if r["ticker"] in locked_high:
                    continue
                if ex_max > r["strike"] + MARGIN_F:
                    locked_high[r["ticker"]] = (ts, ex_max)
        if ex_min is not None and rungs_low:
            for r in rungs_low:
                if r["ticker"] in locked_low:
                    continue
                if ex_min < r["strike"] - MARGIN_F:
                    locked_low[r["ticker"]] = (ts, ex_min)

    locks = []
    for r in rungs_high:
        if r["ticker"] in locked_high:
            ts, ex = locked_high[r["ticker"]]
            locks.append({"station": station, "date": d.isoformat(), "ticker": r["ticker"], "kind": "max",
                          "strike": r["strike"], "settlement": r["settlement"], "lock_utc": ts.isoformat(),
                          "extreme_at_lock": round(ex, 2), "cushion": round(ex - r["strike"], 2)})
    for r in rungs_low:
        if r["ticker"] in locked_low:
            ts, ex = locked_low[r["ticker"]]
            locks.append({"station": station, "date": d.isoformat(), "ticker": r["ticker"], "kind": "min",
                          "strike": r["strike"], "settlement": r["settlement"], "lock_utc": ts.isoformat(),
                          "extreme_at_lock": round(ex, 2), "cushion": round(r["strike"] - ex, 2)})
    return locks, True, (len(rungs_high), len(rungs_low))


def day_is_usable(days_idx, d, tz):
    obs = days_idx.get(d, [])
    if len(obs) < GUARD_MIN_OBS_PER_DAY:
        return False, f"thin_station_data_{len(obs)}obs"
    day_end_utc = dt.datetime.combine(d + dt.timedelta(days=1), dt.time(0, 0), tzinfo=tz).astimezone(dt.timezone.utc)
    if obs[-1][0] < day_end_utc - dt.timedelta(hours=DAY_USABLE_MAX_END_GAP_H):
        return False, "station_feed_gap_near_dayend"
    return True, None


def price_lock(lock):
    ticker = lock["ticker"]
    lock_utc = dt.datetime.fromisoformat(lock["lock_utc"])
    settlement = lock["settlement"]
    ts, price_c, fetch_ok = first_fill_after_lock(ticker, lock_utc)
    rec = dict(lock)
    rec["pairs_fetch_ok"] = fetch_ok
    if settlement not in (0.0, 1.0):
        rec["priceable"] = False
        rec["skip_reason"] = "ambiguous_settlement"
        return rec
    rec["correct"] = (settlement == 1.0)
    if ts is None:
        rec["priceable"] = False
        rec["skip_reason"] = "no_fill_60min" if fetch_ok else "pairs_fetch_failed"
        return rec
    fill_price_c = price_c + SLIPPAGE_C
    payout_c = 100.0 if rec["correct"] else 0.0
    net_ev_c = payout_c - fill_price_c - FEE_C
    rec["priceable"] = True
    rec["entry_utc"] = ts.isoformat()
    rec["raw_fill_price_c"] = round(price_c, 3)
    rec["fill_price_c"] = round(fill_price_c, 3)
    rec["net_ev_c"] = round(net_ev_c, 3)
    return rec


# ============================================================================================================
# PHASE 2 -- early tripwire (prices data only for entry search; settlement/outcome NOT read/used here)
# ============================================================================================================
def run_tripwire(survivors, day_indices):
    print("\n" + "=" * 100)
    print(f"PHASE 2 -- early tripwire: first-fill-after-lock price distribution, "
          f"{WINDOW_START}..{TRIPWIRE_END} (first 30 window days)")
    print("=" * 100)
    fill_prices = []
    n_locks = 0
    n_fetch_fail_days = 0
    for sta in survivors:
        tz = ZoneInfo(STATIONS[sta]["tz"])
        d = WINDOW_START
        while d <= TRIPWIRE_END:
            usable, _ = day_is_usable(day_indices[sta], d, tz)
            if usable:
                locks, ok, _ = walk_day_locks(sta, d, day_indices[sta].get(d, []))
                if not ok:
                    n_fetch_fail_days += 1
                else:
                    for lk in locks:
                        n_locks += 1
                        lock_utc = dt.datetime.fromisoformat(lk["lock_utc"])
                        ts, price_c, fetch_ok = first_fill_after_lock(lk["ticker"], lock_utc)
                        if ts is not None:
                            fill_prices.append(price_c + SLIPPAGE_C)
            d += dt.timedelta(days=1)
    median_price = st.median(fill_prices) if fill_prices else None
    print(f"  locks encountered: {n_locks}  priced (had a <=60min fill): {len(fill_prices)}  "
          f"prices-fetch-failed days: {n_fetch_fail_days}")
    print(f"  median first-fill-after-lock price (incl. 1.0c slippage): "
          f"{median_price if median_price is None else round(median_price,3)}c")
    killed = median_price is not None and median_price >= 98.5
    return {
        "n_locks": n_locks, "n_priced": len(fill_prices), "median_fill_price_c": median_price,
        "killed": killed, "n_fetch_fail_days": n_fetch_fail_days,
    }


# ============================================================================================================
# PHASE 3 -- full-window backtest
# ============================================================================================================
def run_full_backtest(survivors, day_indices):
    print("\n" + "=" * 100)
    print(f"PHASE 3 -- full-window backtest, {WINDOW_START}..{WINDOW_END}, stations={survivors}")
    print("=" * 100)
    all_locks = []
    skips = []
    validated_stations = set()
    for sta in survivors:
        tz = ZoneInfo(STATIONS[sta]["tz"])
        d = WINDOW_START
        n_days_used = 0
        while d <= WINDOW_END:
            usable, reason = day_is_usable(day_indices[sta], d, tz)
            if not usable:
                skips.append({"station": sta, "date": d.isoformat(), "reason": reason})
                d += dt.timedelta(days=1)
                continue
            validate = sta not in validated_stations
            try:
                locks, ok, rung_counts = walk_day_locks(sta, d, day_indices[sta][d], validate=validate)
            except RuntimeError as e:
                print(f"    ABORT: {e}")
                raise
            if validate:
                validated_stations.add(sta)
            if not ok:
                skips.append({"station": sta, "date": d.isoformat(), "reason": "forecastex_fetch_failed"})
                d += dt.timedelta(days=1)
                continue
            if not locks:
                if rung_counts == (0, 0):
                    skips.append({"station": sta, "date": d.isoformat(), "reason": "no_forecastex_listing"})
                else:
                    skips.append({"station": sta, "date": d.isoformat(), "reason": "no_lock_reached"})
                d += dt.timedelta(days=1)
                continue
            n_days_used += 1
            all_locks.extend(locks)
            d += dt.timedelta(days=1)
        print(f"  {sta}: {n_days_used} days produced >=1 lock, {len(skips)} cumulative skips so far, "
              f"{sum(1 for l in all_locks if l['station']==sta)} total locks")
    print(f"\nTotal lock records: {len(all_locks)}  Total day-skips: {len(skips)}")
    return all_locks, skips


def price_all_locks(all_locks):
    print("\nPricing every lock off the pairs tape (first fill in [lock, lock+60min])...")
    priced = []
    for i, lk in enumerate(all_locks):
        priced.append(price_lock(lk))
        if (i + 1) % 200 == 0:
            print(f"  ...{i+1}/{len(all_locks)} priced")
    return priced


# ============================================================================================================
# VERDICT
# ============================================================================================================
def compute_verdict(guard, survivors, tripwire, priced_locks, skips):
    out = {"spec_id": "S3", "guard": guard, "survivors": survivors, "tripwire": tripwire}

    if len(survivors) < 2:
        out["verdict"] = "FAIL"
        out["kill_reason"] = "guard_lt_2_stations_survived"
        return out

    if tripwire["killed"]:
        out["verdict"] = "FAIL"
        out["kill_reason"] = f"early_tripwire_median_{tripwire['median_fill_price_c']:.3f}c_>=98.5c"
        return out

    n_locks = len(priced_locks)
    false_locks = [l for l in priced_locks if l.get("correct") is False]
    ambiguous = [l for l in priced_locks if l.get("skip_reason") == "ambiguous_settlement"]
    n_false = len(false_locks)

    # tape-thinness kill: fraction of lock station-days with >=1 priced fire
    by_station_day = {}
    for l in priced_locks:
        key = (l["station"], l["date"])
        by_station_day.setdefault(key, []).append(l)
    n_lock_station_days = len(by_station_day)
    n_station_days_with_fill = sum(1 for recs in by_station_day.values() if any(r.get("priceable") for r in recs))
    fill_frac = (n_station_days_with_fill / n_lock_station_days) if n_lock_station_days else 0.0

    priced = [l for l in priced_locks if l.get("priceable")]
    n_priced = len(priced)
    priced_station_days = len({(l["station"], l["date"]) for l in priced})
    priced_stations = len({l["station"] for l in priced})

    false_wilson_lo, false_wilson_hi = wilson_ci(n_false, n_locks, z=Z_9833) if n_locks else (None, None)

    net_vals = [l["net_ev_c"] for l in priced]
    day_clustered = clustered_t(net_vals, [(l["station"], l["date"]) for l in priced]) if len(priced) >= 2 else None
    caldate_clustered = clustered_t(net_vals, [l["date"] for l in priced]) if len(priced) >= 2 else None
    ev_ucb = None
    if day_clustered and day_clustered["se"] is not None:
        ev_ucb = day_clustered["mean"] + Z_9833 * day_clustered["se"]

    stats = {
        "n_locks": n_locks, "n_false_locks": n_false, "n_ambiguous_settlement": len(ambiguous),
        "false_lock_rate": (n_false / n_locks) if n_locks else None,
        "false_lock_wilson_upper_9833": false_wilson_hi,
        "n_lock_station_days": n_lock_station_days,
        "fill_within_60min_fraction_of_lock_station_days": round(fill_frac, 4),
        "n_priced_fires": n_priced, "n_priced_station_day_clusters": priced_station_days,
        "n_priced_stations": priced_stations,
        "mean_net_ev_c": day_clustered["mean"] if day_clustered else None,
        "day_clustered_t": day_clustered["t"] if day_clustered else None,
        "day_clustered_se": day_clustered["se"] if day_clustered else None,
        "day_clustered_n_clusters": day_clustered["n_clusters"] if day_clustered else None,
        "ev_upper_bound_9833": ev_ucb,
        "calendar_date_clustered_sensitivity": caldate_clustered,
    }
    out["stats"] = stats

    if fill_frac < 0.30:
        out["verdict"] = "FAIL"
        out["kill_reason"] = f"tape_too_thin_fill_frac_{fill_frac:.3f}_<0.30"
        return out

    if n_false > 4:
        out["verdict"] = "FAIL"
        out["kill_reason"] = f"basis_failure_{n_false}_false_locks_>4"
        return out

    thin_false = n_locks < 150
    thin_ev = n_priced < 100 or priced_station_days < 50 or priced_stations < 2
    if thin_false or thin_ev:
        out["verdict"] = "INSUFFICIENT"
        out["kill_reason"] = (
            f"min_n_unreachable: n_locks={n_locks}(need>=150) "
            f"n_priced={n_priced}(need>=100) station_day_clusters={priced_station_days}(need>=50) "
            f"stations={priced_stations}(need>=2)"
        )
        return out

    bar_i = (n_false <= 1) and (false_wilson_hi is not None and false_wilson_hi <= 0.025)
    bar_ii = (
        day_clustered is not None and day_clustered["t"] is not None and day_clustered["t"] >= T_BAR
        and day_clustered["mean"] >= 0.5
    )
    out["pass_bar_i_false_lock"] = bar_i
    out["pass_bar_ii_ev"] = bar_ii

    if bar_i and bar_ii:
        out["verdict"] = "PASS"
        out["kill_reason"] = None
        return out

    if ev_ucb is not None and ev_ucb < 0.2:
        out["verdict"] = "FAIL"
        out["kill_reason"] = f"symmetric_kill_ev_ucb_{ev_ucb:.3f}c_<0.2c_fee_economics_dead"
        return out

    out["verdict"] = "FAIL"
    out["kill_reason"] = "did_not_clear_pass_bar_" + (
        "false_lock_bar_failed" if not bar_i else "ev_bar_failed"
    )
    return out


# ============================================================================================================
# MAIN
# ============================================================================================================
def main():
    t_start = time.time()
    guard, survivors, day_indices = run_guard()

    if len(survivors) < 2:
        result = {
            "spec_id": "S3", "verdict": "FAIL", "kill_reason": "guard_lt_2_stations_survived",
            "guard": guard, "survivors": survivors, "window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
            "elapsed_sec": round(time.time() - t_start, 1),
        }
        json.dump(result, open(os.path.join(HERE, "out", "spec_S3_results.json"), "w"), indent=2, default=str)
        print(json.dumps({k: v for k, v in result.items() if k != "guard"}, indent=2, default=str))
        return result

    tripwire = run_tripwire(survivors, day_indices)

    if tripwire["killed"]:
        result = {
            "spec_id": "S3", "verdict": "FAIL",
            "kill_reason": f"early_tripwire_median_{tripwire['median_fill_price_c']:.3f}c_>=98.5c",
            "guard": guard, "survivors": survivors, "tripwire": tripwire,
            "window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
            "elapsed_sec": round(time.time() - t_start, 1),
        }
        json.dump(result, open(os.path.join(HERE, "out", "spec_S3_results.json"), "w"), indent=2, default=str)
        print(json.dumps({k: v for k, v in result.items() if k not in ("guard",)}, indent=2, default=str))
        return result

    all_locks, skips = run_full_backtest(survivors, day_indices)
    priced_locks = price_all_locks(all_locks)
    verdict = compute_verdict(guard, survivors, tripwire, priced_locks, skips)

    skip_reason_counts = {}
    for s in skips:
        skip_reason_counts[s["reason"]] = skip_reason_counts.get(s["reason"], 0) + 1

    result = dict(verdict)
    result["window"] = [WINDOW_START.isoformat(), WINDOW_END.isoformat()]
    result["skip_reason_counts"] = skip_reason_counts
    result["n_day_skips"] = len(skips)
    result["elapsed_sec"] = round(time.time() - t_start, 1)
    result["lock_records"] = priced_locks
    result["day_skips_sample"] = skips[:200]

    out_path = os.path.join(HERE, "out", "spec_S3_results.json")
    json.dump(result, open(out_path, "w"), indent=2, default=str)
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    print(json.dumps({k: v for k, v in result.items()
                       if k not in ("lock_records", "day_skips_sample", "guard")}, indent=2, default=str))
    print(f"\nFull results -> {out_path}")
    return result


if __name__ == "__main__":
    main()
