#!/usr/bin/env python3
"""spec_S3_A.py -- BUILD A, PRE-REGISTERED spec S3: "ForecastEx daily-temperature lock study: false-lock
rate + flat-fee EV on the venue's own trade tape". Executed against the frozen spec text (see task header
this was authored against) with the orchestrator-verified WINDOW CORRECTION (2026-02-17..2026-07-26) --
every pass/kill bar, margin, sustain, fee and slippage constant is copied verbatim and UNCHANGED.

READ venue_expansion/GROUNDING.md and venue_expansion/PAPER_TRADER_AUDIT.md before trusting this file --
this script exists specifically to avoid PAPER_TRADER_AUDIT's two bugs:
  (1) NEVER prices one side of a book off the other side's price -- every fill and every settlement below
      is read from its own YES-subtype row (ForecastEx's yes_price / YES settlement_price columns); the NO
      side is never touched because every lock this rule produces is mechanically a YES lock (see "WHY ALL
      LOCKS ARE YES" below).
  (2) NEVER decides an outcome itself -- settlement truth is ALWAYS the venue's own `settlement_price`
      field from prices/daily_prices_*.csv, read only once a contract's `open_interest` has gone to 0 in a
      forward-scanned file (see `find_settlement`), never computed from IEM obs or any other derivation.

WHY ALL LOCKS ARE YES: ForecastEx UH<STA>_<D>_<K> ("highest temp exceeds K") and UL<STA>_<D>_<K> ("lowest
temp is below K") are single-sided thresholds -- in kwx_lock_rule's rung vocabulary that is floor=K,cap=None
(UH) or floor=None,cap=K (UL). Re-reading kwx_lock_rule.locked_orders: the cap-not-None "NO" branches (a
capped/bracket rung locking NO) can only fire when a rung has BOTH a floor and a cap (a bracket), which
these contracts never have. So every fire this signal produces is the floor(UH)/cap(UL) "YES" branch --
confirmed by an assertion in the code below (aborts loudly if a NO ever appears).

LOCK RULE FIDELITY: kwx_lock_rule.sustained_extreme and kwx_lock_rule.locked_orders are called VERBATIM,
unedited, exactly as required. sustained_extreme(obs, kind) is monotonic in the length of `obs` (proof:
adding an observation can only ever raise the best qualifying window-min for kind='max', or lower it for
kind='min' -- earlier qualifying windows remain valid candidates), so the first index at which a station-day
crosses a given contract's lock threshold is found by BINARY SEARCH over the (already monotonic) boolean
sequence "is locked_orders(...) non-empty at prefix i", calling the two real functions unmodified at each
probe -- no reimplementation of the sustain/glitch/margin math, only a search strategy over repeated calls
to it. A same-run self-check (`_selftest_monotonic`) brute-force-verifies monotonicity on real fetched data
before any study number is trusted.

locked_orders() also gates on a live yes_ask_c/no_ask_c (<=98c, MAX_PAY_CENTS) -- a price input. Per the
spec's own "Signal uses obs ONLY; no tape, no price, no outcome input" clause and GROUNDING.md non-negotiable
#4 ("must NOT condition on ... market price"), every rung passed into locked_orders() carries a FIXED,
disclosed dummy ask of 1c on both sides -- unconditionally satisfies the <=98c filter regardless of any real
market price, so the filter can never gate the signal on real price data. This is disclosed here rather than
silently reimplementing locked_orders without its price argument.

DATA SOURCES:
  - Obs: IEM TRUE 1-minute ASOS archive (asos1min.py), same endpoint/semantics Track A verified for KORD.
  - Rungs, fill prices, settlement: forecastex-public-data.s3.amazonaws.com {pairs,prices}/*.csv, joined on
    event_contract (NEVER on filename -- see DATE ALIGNMENT TRAP in module docstring below for why).

Read-only, public APIs only (IEM Mesonet + forecastex-public-data S3), no auth, no orders, no trading code.
Polite: cached under venue_expansion/cache/ (shared with other read-only studies in this repo), retried
with backoff, ~1 req/sec.

USAGE:
  python spec_S3_A.py --guard          # phase 1: inclusion guard only
  python spec_S3_A.py --tripwire       # phase 1+2: guard, then early tripwire (first 30 window days)
  python spec_S3_A.py --full           # phase 1-4: guard, tripwire, full pull, verdict
  python spec_S3_A.py --cached-only    # any phase above, no network, cache must already be complete
"""
import bisect
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
import kwx_lock_rule as R  # deployed lock-rule shim -- sustained_extreme + locked_orders, called verbatim

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "*/*", "User-Agent": "Mozilla/5.0 (compatible; spec-S3-A/1.0; research, read-only)"}

ASOS_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
FX_BASE = "https://forecastex-public-data.s3.amazonaws.com"

CACHE_IEM = os.path.join(HERE, "cache", "forecastex_study")   # shared cache, reused from an earlier pull
CACHE_FX = os.path.join(HERE, "cache", "forecastex")           # shared cache, reused from an earlier pull
os.makedirs(CACHE_IEM, exist_ok=True)
os.makedirs(CACHE_FX, exist_ok=True)

OUT_JSON = os.path.join(HERE, "out", "spec_S3_A.json")
OUT_MD = os.path.join(HERE, "out", "spec_S3_A.md")

CACHED_ONLY = "--cached-only" in sys.argv

# ------------------------------------------------------------------------------------------------------
# STATION UNIVERSE -- candidate cities = the 10 highest-volume UH/UL products named in the orchestrator's
# 2026-07-26 CITY VOLUME table (BKF excluded from that raw list's name confusion resolved below). Each
# station's Weather-Underground settlement station was NOT enumerable from ForecastEx's own filed contract
# terms (venue_expansion/cache/fx_daily_temp.pdf and cache/forecastex/UTermsandConditions.pdf are both
# generic "the applicable station" boilerplate with no per-city table -- confirmed by direct text extraction,
# see spec_S3_A.md "Station mapping" section for the verbatim quote). Instead each mapping below is the
# specific station named in that city's own ForecastEx contract as reproduced verbatim in Robinhood's (a
# CFTC-registered ForecastEx member broker) per-contract resolution text, cross-checked across 10
# independent WebSearch pulls on 2026-07-29 (one per city) -- every single one names an airport ICAO whose
# 3-letter tail is EXACTLY the ticker's region code with its leading K stripped (LAX->KLAX, ..., and
# critically BKF->KBKF "Buckley Space Force Base", NOT KDEN -- the one case where the naive "guess the
# obvious airport" rule the orchestrator warned against would have been silently wrong).
# ------------------------------------------------------------------------------------------------------
STATIONS = {
    "LAX": dict(icao="KLAX", tz="America/Los_Angeles", wu_name="Los Angeles Intl Airport Station"),
    "LAS": dict(icao="KLAS", tz="America/Los_Angeles", wu_name="Harry Reid Intl Airport Station"),
    "LGA": dict(icao="KLGA", tz="America/New_York", wu_name="LaGuardia Airport Station"),
    "SEA": dict(icao="KSEA", tz="America/Los_Angeles", wu_name="Seattle-Tacoma Intl Airport Station"),
    "SFO": dict(icao="KSFO", tz="America/Los_Angeles", wu_name="San Francisco Intl Airport Station"),
    "MIA": dict(icao="KMIA", tz="America/New_York", wu_name="Miami Intl Airport Station"),
    "PHX": dict(icao="KPHX", tz="America/Phoenix", wu_name="Phoenix Sky Harbor Intl Airport Station"),
    "MDW": dict(icao="KMDW", tz="America/Chicago", wu_name="Chicago Midway Intl Airport Station"),
    "AUS": dict(icao="KAUS", tz="America/Chicago", wu_name="Austin Bergstrom Intl Airport Station"),
    "BKF": dict(icao="KBKF", tz="America/Denver", wu_name="Buckley Space Force Base Station"),
}
CT_TZ = ZoneInfo("America/Chicago")

# ------------------------------------------------------------------------------------------------------
# WINDOW -- orchestrator-corrected (2026-07-27): temperature contracts did not exist before 2026-02-17.
# This is the ONLY change to the frozen spec; no bar below moved. Independently re-verified here (not just
# taken on faith): pairs_20260210.csv has 0 UH/UL fills; pairs_20260211..0217 already show thousands (temp
# trading in fact started ~2026-02-10/11, a few days earlier than the orchestrator's spot-check found) --
# see spec_S3_A.md "Window" section. The orchestrator's instruction is to USE 2026-02-17..2026-07-26, not to
# extend it based on this finding, so WINDOW_START stays 2026-02-17 as directed; the earlier-start finding
# is disclosed, not acted on (extending the window myself would be exactly the "improvise a replacement
# rule" the task prohibits).
# ------------------------------------------------------------------------------------------------------
WINDOW_START = dt.date(2026, 2, 17)
WINDOW_END = dt.date(2026, 7, 26)
TRIPWIRE_END = WINDOW_START + dt.timedelta(days=29)  # first 30 window days, inclusive

GUARD_MIN_OBS_PER_DAY = 100
GUARD_MIN_DAY_FRACTION = 0.70

MARGIN_F = R.MARGIN_F           # 1.0F, byte-identical import, unmodified
SLIPPAGE_C = 1.0
FEE_C = 1.0
MAX_FILL_WAIT_MIN = 60
TRIPWIRE_PRICE_C = 98.5
FALSE_LOCK_UB_PCT = 2.5
Z_9833 = 2.128                  # one-sided 98.33%, Bonferroni-3
T_BAR = 2.25
EV_FLOOR_C = 0.5
EV_KILL_UB_C = 0.2
FALSE_LOCK_KILL_N = 4
FILL_COVERAGE_KILL = 0.30
MIN_N_FALSE_LOCK = 150
MIN_N_PRICED = 100
MIN_CLUSTERS = 50
MIN_STATIONS = 2

TICKER_RE = re.compile(r"^(UH|UL)([A-Z]{3})_(\d{6})_(-?\d+(?:\.\d+)?)$")

FULL = "--full" in sys.argv
TRIPWIRE_ONLY = "--tripwire" in sys.argv
GUARD_ONLY = "--guard" in sys.argv


# ============================================================================================================
# HTTP + cache plumbing
# ============================================================================================================
def _get_text(url, timeout=90, retries=5, backoff=2.0):
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


def _cache_get_json(path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            return json.load(open(path))
        except Exception:
            return None
    return None


def _cache_put_json(path, obj):
    json.dump(obj, open(path, "w"))


def _cache_get_csv(path):
    if os.path.exists(path):
        if os.path.getsize(path) == 0:
            return None  # cached-empty sentinel: prior 404 / no data that day
        return open(path, "r", encoding="utf-8", errors="replace").read()
    return None


def _cache_put_csv(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text or "")


# ============================================================================================================
# FEED A -- IEM TRUE 1-minute ASOS archive
# ============================================================================================================
def fetch_iem_1min_chunk(station, start_utc, end_utc):
    key = f"iem1min_{station}_{start_utc:%Y%m%dT%H%M}_{end_utc:%Y%m%dT%H%M}.json"
    path = os.path.join(CACHE_IEM, key)
    cached = _cache_get_json(path)
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
    _cache_put_json(path, [(t.isoformat(), v) for t, v in out])
    time.sleep(1.0)
    return out


def fetch_station_stream(station):
    """Full padded-window 1-min stream, 28-day chunks (matches the pre-existing cache's chunk boundaries so
    already-fetched chunks are reused verbatim), deduped+sorted."""
    span_start = dt.datetime.combine(WINDOW_START - dt.timedelta(days=1), dt.time(0, 0), tzinfo=dt.timezone.utc)
    span_end = dt.datetime.combine(WINDOW_END + dt.timedelta(days=2), dt.time(0, 0), tzinfo=dt.timezone.utc)
    anchor = dt.datetime(2025, 7, 31, tzinfo=dt.timezone.utc)  # matches pre-existing cache chunk grid
    chunk = dt.timedelta(days=28)
    by_ts = {}
    c = anchor
    while c < span_end:
        c_end = c + chunk
        if c_end > span_start and c < span_end:
            rows = fetch_iem_1min_chunk(station, c, c_end)
            for t, v in rows:
                if span_start <= t <= span_end:
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
# FEED B -- ForecastEx pairs/prices CSVs. Cached under the pre-existing shared cache/forecastex/ dir.
# ============================================================================================================
def fx_cache_path(kind, date_str):
    return os.path.join(CACHE_FX, f"{kind}_{date_str}.csv")


def fetch_fx_csv(kind, date_str):
    subdir = "prices" if kind == "prices" else "pairs"
    fname_prefix = "daily_prices" if kind == "prices" else "pairs"
    path = fx_cache_path(kind, date_str)
    cached = _cache_get_csv(path)
    if cached is not None:
        return cached
    if CACHED_ONLY:
        return None
    url = f"{FX_BASE}/{subdir}/{fname_prefix}_{date_str}.csv"
    txt = _get_text(url)
    _cache_put_csv(path, txt or "")
    time.sleep(1.0)
    return txt


_PRICES_CACHE = {}   # date_str -> parsed rows: ticker -> {"subtype": {...fields...}}  (None = fetch failed)
_PAIRS_CACHE = {}    # date_str -> ticker -> sorted [(utc_dt, yes_price_c)]             (None = fetch failed)


def load_prices_index(date_str):
    if date_str in _PRICES_CACHE:
        return _PRICES_CACHE[date_str]
    txt = fetch_fx_csv("prices", date_str)
    if not txt:
        _PRICES_CACHE[date_str] = None
        return None
    idx = {}
    rdr = csv.reader(io.StringIO(txt))
    header = next(rdr, None)
    for row in rdr:
        if len(row) < 9:
            continue
        event_contract, subtype, expiration_date, date_ = row[0], row[1], row[2], row[3]
        try:
            settlement_price = float(row[8]) if row[8] not in ("", None) else None
        except ValueError:
            settlement_price = None
        try:
            open_interest = int(float(row[10])) if row[10] not in ("", None) else None
        except ValueError:
            open_interest = None
        idx.setdefault(event_contract, {})[subtype] = dict(
            expiration_date=expiration_date, date=date_, settlement_price=settlement_price,
            open_interest=open_interest, pair_quantity=row[9])
    _PRICES_CACHE[date_str] = idx
    return idx


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


def dstr(d):
    return d.strftime("%Y%m%d")


def discover_contracts(station, side, mmddyy, search_dates):
    """side: 'UH' or 'UL'. Returns {ticker: {'strike':float,'expiration_date':iso str,'ES':date}} by scanning
    prices files on `search_dates` (a small list of candidate calendar dates -- NOT assumed to be D+1; the
    expiration_date field itself, not a hardcoded offset, is what tells us ES) for tickers matching
    <side><station>_<mmddyy>_<strike>. fetch_ok=False on any date means that day's prices pull failed
    (network), distinct from the date simply having no matching contracts."""
    prefix = f"{side}{station}_{mmddyy}_"
    found = {}
    fetch_ok = True
    for ds in search_dates:
        idx = load_prices_index(ds)
        if idx is None:
            fetch_ok = False
            continue
        for ticker, subtypes in idx.items():
            if not ticker.startswith(prefix):
                continue
            m = TICKER_RE.match(ticker)
            if not m:
                continue
            strike = float(m.group(4))
            yes = subtypes.get("YES")
            if not yes:
                continue
            es = yes["expiration_date"][:10]
            found.setdefault(ticker, {"strike": strike, "expiration_date": yes["expiration_date"], "ES": es})
    return found, fetch_ok


def find_settlement(ticker, es_date_str, max_forward_days=6):
    """Forward-scan prices files starting at the contract's own ES calendar date (never a hardcoded D+1 --
    ES itself came from the contract's real expiration_date field) until the YES row's open_interest hits 0
    -- the venue's own signal that the contract has closed and settlement_price is now final, not an interim
    mark (verified directly: mid-trading rows carry a non-terminal settlement_price with open_interest>0;
    see spec_S3_A.md 'Settlement basis' section for the worked SFO example). Returns
    (settlement_price_or_None, found_es_str_or_None, fetch_ok). settlement_price is read verbatim from the
    venue's own field -- this script NEVER computes an outcome itself."""
    d0 = dt.datetime.strptime(es_date_str, "%Y-%m-%d").date()
    fetch_ok = True
    for i in range(max_forward_days):
        ds = dstr(d0 + dt.timedelta(days=i))
        idx = load_prices_index(ds)
        if idx is None:
            fetch_ok = False
            continue
        rec = idx.get(ticker, {}).get("YES")
        if rec is None:
            continue
        if rec["open_interest"] == 0 and rec["settlement_price"] is not None:
            return rec["settlement_price"], ds, fetch_ok
    return None, None, fetch_ok


def pairs_dates_needed(es_date_str):
    """ES-1, ES, ES+1 -- covers the full [D 00:00, D 23:59]+60min local window regardless of what time of
    day within local day D the lock fires, given the MEASURED pairs-file convention (file dated X spans
    fills timestamped [X-1 16:15 CT, X 16:14 CT], confirmed in the module docstring's DATE ALIGNMENT TRAP)
    and the MEASURED fact (this script, both Pacific- and Eastern-station contracts checked directly) that a
    contract's own ES is generally D+1 but is read from the real expiration_date field, never assumed."""
    d0 = dt.datetime.strptime(es_date_str, "%Y-%m-%d").date()
    return [dstr(d0 - dt.timedelta(days=1)), dstr(d0), dstr(d0 + dt.timedelta(days=1))]


def first_fill_after_lock(ticker, lock_utc, es_date_str):
    candidates = []
    fetch_ok = True
    for ds in pairs_dates_needed(es_date_str):
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
# LOCK DETECTION -- binary search over prefixes of a station-day's obs, calling R.sustained_extreme and
# R.locked_orders VERBATIM at each probe. No reimplementation of the sustain/glitch/margin comparisons.
# ============================================================================================================
DUMMY_ASK_C = 1  # fixed, disclosed, never-blocking dummy price so locked_orders' <=98c filter cannot gate
                  # the signal on real market price (GROUNDING #4 / "signal uses obs only").


def probe_locked(obs_prefix, kind, floor, cap, ticker):
    """Call the REAL R.sustained_extreme + R.locked_orders on `obs_prefix`. Returns (is_locked, cushion_f)."""
    extreme = R.sustained_extreme(obs_prefix, kind)
    if extreme is None:
        return False, None
    rung = {"ticker": ticker, "floor": floor, "cap": cap,
            "yes_ask_c": DUMMY_ASK_C, "no_ask_c": DUMMY_ASK_C}
    orders = R.locked_orders([rung], extreme, kind, margin=MARGIN_F)
    if not orders:
        return False, None
    tkr, side, _, cushion = orders[0]
    assert side == "yes", f"unexpected NO-side lock on a one-sided contract: {orders}"  # see module docstring
    return True, cushion


def find_lock_index(obs_day, kind, floor, cap, ticker):
    """Binary search the monotonic boolean sequence i -> probe_locked(obs_day[:i+1], ...). Returns
    (index, ts, cushion) of the first qualifying prefix, or None if the day never locks this contract."""
    n = len(obs_day)
    if n == 0:
        return None
    ok_n, cushion_n = probe_locked(obs_day, kind, floor, cap, ticker)
    if not ok_n:
        return None
    lo, hi = 0, n - 1  # find minimal hi-index i (0-based) such that obs_day[:i+1] is locked
    while lo < hi:
        mid = (lo + hi) // 2
        ok, _ = probe_locked(obs_day[:mid + 1], kind, floor, cap, ticker)
        if ok:
            hi = mid
        else:
            lo = mid + 1
    ok_lo, cushion_lo = probe_locked(obs_day[:lo + 1], kind, floor, cap, ticker)
    assert ok_lo
    return lo, obs_day[lo][0], cushion_lo


def _selftest_monotonic(obs_day, kind, n_checks=25):
    """Brute-force sanity check: probe_locked(obs_day[:i+1]) must be a monotonic non-decreasing boolean
    sequence in i (True can never flip back to False as more obs arrive), on REAL fetched data, for an
    arbitrary threshold near the day's own extreme. Aborts loudly (raises) if it ever disagrees."""
    if len(obs_day) < 5:
        return
    vals = [v for _, v in obs_day]
    if kind == "max":
        thresh = min(vals) + 0.6 * (max(vals) - min(vals))
        floor, cap = thresh - MARGIN_F, None
    else:
        thresh = max(vals) - 0.6 * (max(vals) - min(vals))
        floor, cap = None, thresh + MARGIN_F
    idxs = sorted(set(int(x) for x in [0] + [len(obs_day) * k // n_checks for k in range(1, n_checks)] +
                       [len(obs_day) - 1]))
    seen_true = False
    for i in idxs:
        ok, _ = probe_locked(obs_day[:i + 1], kind, floor, cap, "SELFTEST")
        if seen_true and not ok:
            raise AssertionError(f"monotonicity violated at prefix {i} (kind={kind})")
        seen_true = seen_true or ok


# ============================================================================================================
# STATS
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
        return {"mean": (st.mean(values) if values else None), "se": None, "t": None, "n": n,
                "n_clusters": len(set(cluster_ids)), "df": None}
    ybar = st.mean(values)
    resid = [v - ybar for v in values]
    clusters = {}
    for c, r in zip(cluster_ids, resid):
        clusters.setdefault(c, []).append(r)
    G = len(clusters)
    if G < 2:
        return {"mean": ybar, "se": None, "t": None, "n": n, "n_clusters": G, "df": None}
    sum_sq = sum(sum(rs) ** 2 for rs in clusters.values())
    var = (n / (n - 1)) * (G / (G - 1)) * sum_sq / (n * n)
    se = math.sqrt(var) if var > 0 else None
    t = (ybar / se) if se and se > 0 else None
    return {"mean": ybar, "se": se, "t": t, "n": n, "n_clusters": G, "df": G - 1}


# ============================================================================================================
# PER STATION-DAY PROCESSING
# ============================================================================================================
def process_station_day(station, D, obs_day, need_settlement):
    """Returns list of lock-fire records for local day D at `station`. Discovers UH/UL contracts by scanning
    prices files on candidate ES dates {D, D+1, D+2} (never assumed == D+1; read from expiration_date), runs
    the verbatim lock rule against `obs_day`, prices the first tape fill >=60min after lock, and (if
    need_settlement) forward-scans for the venue's own settlement_price. No price or outcome data is read
    before the lock decision is made -- discovery only reveals which strikes/tickers EXIST, not their price
    history or outcome, and the lock threshold check runs on `obs_day` alone."""
    mmddyy = D.strftime("%m%d%y")
    search_dates = [dstr(D), dstr(D + dt.timedelta(days=1)), dstr(D + dt.timedelta(days=2))]
    recs = []
    for side, kind in (("UH", "max"), ("UL", "min")):
        contracts, fetch_ok = discover_contracts(station, side, mmddyy, search_dates)
        if not contracts:
            continue
        for ticker, meta in contracts.items():
            strike = meta["strike"]
            es = meta["ES"]
            floor, cap = (strike, None) if side == "UH" else (None, strike)
            found = find_lock_index(obs_day, kind, floor, cap, ticker)
            if found is None:
                continue
            idx, lock_ts, cushion = found
            rec = {"station": station, "icao": STATIONS[station]["icao"], "side": side, "ticker": ticker,
                   "local_date": D.isoformat(), "strike": strike, "es_date": es,
                   "lock_ts_utc": lock_ts.isoformat(), "cushion_f": cushion,
                   "obs_fetch_ok": True, "n_obs_day": len(obs_day)}
            fts, fpx, pairs_ok = first_fill_after_lock(ticker, lock_ts, es)
            rec["pairs_fetch_ok"] = pairs_ok
            if fts is not None:
                rec["fill_ts_utc"] = fts.isoformat()
                rec["fill_price_c"] = fpx
                rec["wait_min"] = round((fts - lock_ts).total_seconds() / 60.0, 2)
                rec["priced"] = True
            else:
                rec["priced"] = False
            if need_settlement:
                settle_px, settle_es, settle_ok = find_settlement(ticker, es)
                rec["settlement_fetch_ok"] = settle_ok
                if settle_px is not None:
                    rec["settlement_price"] = settle_px
                    rec["settlement_found_in"] = settle_es
                    rec["outcome_confirms_yes"] = (settle_px >= 0.5)
                    rec["false_lock"] = (settle_px < 0.5)
                    if rec.get("priced"):
                        payout_c = 100.0 if settle_px >= 0.5 else 0.0
                        rec["net_ev_c"] = payout_c - rec["fill_price_c"] - SLIPPAGE_C - FEE_C
                else:
                    rec["settlement_price"] = None
            recs.append(rec)
    return recs


# ============================================================================================================
# PHASE 1 -- asos1min inclusion guard
# ============================================================================================================
def run_guard():
    print("=" * 100)
    print("PHASE 1 -- asos1min inclusion guard")
    print("=" * 100)
    n_days_window = (WINDOW_END - WINDOW_START).days + 1
    guard_results = {}
    station_day_obs = {}  # station -> {date: obs_day list}
    for station, meta in STATIONS.items():
        icao = meta["icao"]
        tz = ZoneInfo(meta["tz"])
        print(f"  fetching {station} ({icao}) 1-min ASOS stream...")
        # NOTE: IEM's asos1min.py endpoint takes the BARE 3-letter station id (e.g. "SFO"), not the
        # 4-letter ICAO ("KSFO") -- confirmed directly: KSFO returns "Unknown station provided"; SFO
        # returns data. This matches the pre-existing cache's own file-naming convention (iem1min_SFO_*,
        # not iem1min_KSFO_*), which this fetch reuses unmodified.
        stream = fetch_station_stream(station)
        days = bucket_by_local_day(stream, tz)
        n_ok = 0
        counts = []
        for k in range(n_days_window):
            d = WINDOW_START + dt.timedelta(days=k)
            n = len(days.get(d, []))
            counts.append(n)
            if n >= GUARD_MIN_OBS_PER_DAY:
                n_ok += 1
        frac = n_ok / n_days_window if n_days_window else 0.0
        passed = frac >= GUARD_MIN_DAY_FRACTION
        guard_results[station] = {
            "icao": icao, "n_days_window": n_days_window, "n_days_ge_min_obs": n_ok,
            "fraction_days_ge_min_obs": round(frac, 4), "passed": passed,
            "median_obs_per_day": (st.median(counts) if counts else 0),
            "total_obs": sum(counts),
        }
        station_day_obs[station] = {d: days.get(d, []) for d in
                                     (WINDOW_START + dt.timedelta(days=k) for k in range(n_days_window))}
        print(f"    {station}: {n_ok}/{n_days_window} days >= {GUARD_MIN_OBS_PER_DAY} obs "
              f"({frac:.1%})  -> {'PASS' if passed else 'FAIL'}")
    surviving = [s for s, r in guard_results.items() if r["passed"]]
    print(f"\n  surviving stations ({len(surviving)}): {surviving}")
    return guard_results, surviving, station_day_obs


# ============================================================================================================
# PHASE 2 -- early tripwire (first 30 window days, price only, outcomes NOT read)
# ============================================================================================================
def run_tripwire(surviving, station_day_obs):
    print("\n" + "=" * 100)
    print(f"PHASE 2 -- early tripwire ({WINDOW_START} .. {TRIPWIRE_END}, price data only, outcomes NOT read)")
    print("=" * 100)
    fill_prices = []
    n_locks = 0
    n_priced = 0
    d = WINDOW_START
    while d <= TRIPWIRE_END:
        for station in surviving:
            obs_day = station_day_obs[station].get(d, [])
            if len(obs_day) < GUARD_MIN_OBS_PER_DAY:
                continue
            recs = process_station_day(station, d, obs_day, need_settlement=False)
            for r in recs:
                n_locks += 1
                if r.get("priced"):
                    n_priced += 1
                    fill_prices.append(r["fill_price_c"])
        d += dt.timedelta(days=1)
    median_px = st.median(fill_prices) if fill_prices else None
    tripwire_kill = (median_px is not None and median_px >= TRIPWIRE_PRICE_C)
    print(f"  tripwire window locks: {n_locks}  priced (fill within 60min): {n_priced}")
    print(f"  median first-fill-after-lock price: {median_px}")
    print(f"  TRIPWIRE-KILL: {tripwire_kill}  (threshold {TRIPWIRE_PRICE_C}c)")
    return {"n_locks": n_locks, "n_priced": n_priced, "median_first_fill_price_c": median_px,
            "tripwire_kill": tripwire_kill, "fill_prices_sample": fill_prices[:50]}


# ============================================================================================================
# PHASE 3+4 -- full pull + false-lock/EV compute + verdict
# ============================================================================================================
def run_full(surviving, station_day_obs):
    print("\n" + "=" * 100)
    print(f"PHASE 3 -- full pull ({WINDOW_START} .. {WINDOW_END}), false-lock + EV compute")
    print("=" * 100)
    all_recs = []
    n_days_window = (WINDOW_END - WINDOW_START).days + 1
    for k in range(n_days_window):
        d = WINDOW_START + dt.timedelta(days=k)
        for station in surviving:
            obs_day = station_day_obs[station].get(d, [])
            if len(obs_day) < GUARD_MIN_OBS_PER_DAY:
                continue
            if len(obs_day) >= 5:
                _selftest_monotonic(obs_day, "max")
                _selftest_monotonic(obs_day, "min")
            recs = process_station_day(station, d, obs_day, need_settlement=True)
            all_recs.extend(recs)
        if (k + 1) % 20 == 0 or k == n_days_window - 1:
            print(f"  ...processed {k + 1}/{n_days_window} days, {len(all_recs)} lock-fires so far")
    return all_recs


def compute_verdict(all_recs, guard_results, surviving, tripwire):
    locks_with_outcome = [r for r in all_recs if r.get("settlement_price") is not None]
    n_locks = len(locks_with_outcome)
    false_locks = [r for r in locks_with_outcome if r["false_lock"]]
    n_false = len(false_locks)
    fl_lb, fl_ub = wilson_ci(n_false, n_locks, z=Z_9833) if n_locks else (None, None)

    priced = [r for r in locks_with_outcome if r.get("priced") and "net_ev_c" in r]
    n_priced = len(priced)
    ev_vals = [r["net_ev_c"] for r in priced]
    sd_ids = [f"{r['station']}|{r['local_date']}" for r in priced]
    cal_ids = [r["local_date"] for r in priced]
    sd_stat = clustered_t(ev_vals, sd_ids)
    cal_stat = clustered_t(ev_vals, cal_ids)
    n_sd_clusters = len(set(sd_ids))
    n_stations_priced = len(set(r["station"] for r in priced))

    mean_ev = sd_stat["mean"]
    t_sd = sd_stat["t"]
    ev_ub = None
    if mean_ev is not None and sd_stat["se"] is not None:
        ev_ub = mean_ev + Z_9833 * sd_stat["se"]

    # fill coverage across all lock station-days (whole window, not just priced/settled ones)
    lock_station_days = set((r["station"], r["local_date"]) for r in all_recs)
    priced_station_days = set((r["station"], r["local_date"]) for r in all_recs if r.get("priced"))
    fill_coverage = (len(priced_station_days) / len(lock_station_days)) if lock_station_days else 0.0

    kill_reasons = []
    if len(surviving) < MIN_STATIONS:
        kill_reasons.append(f"<2 stations survive asos1min guard ({len(surviving)} survive)")
    if tripwire["tripwire_kill"]:
        kill_reasons.append(f"early tripwire: median first-fill price "
                             f"{tripwire['median_first_fill_price_c']}c >= {TRIPWIRE_PRICE_C}c on first 30 days")
    if fill_coverage < FILL_COVERAGE_KILL:
        kill_reasons.append(f"fills within 60min post-lock exist on {fill_coverage:.1%} of lock "
                             f"station-days (<{FILL_COVERAGE_KILL:.0%})")
    if n_false > FALSE_LOCK_KILL_N:
        kill_reasons.append(f"{n_false} false locks (>4) -- basis to WU settlement unsound")
    min_n_reached = (n_locks >= MIN_N_FALSE_LOCK and n_priced >= MIN_N_PRICED and
                     n_sd_clusters >= MIN_CLUSTERS and n_stations_priced >= MIN_STATIONS)
    if not min_n_reached:
        kill_reasons.append(f"min_n unreachable: n_locks={n_locks} (need>={MIN_N_FALSE_LOCK}), "
                             f"n_priced={n_priced} (need>={MIN_N_PRICED}), "
                             f"n_sd_clusters={n_sd_clusters} (need>={MIN_CLUSTERS}), "
                             f"n_stations_priced={n_stations_priced} (need>={MIN_STATIONS})")

    if kill_reasons:
        if any("min_n unreachable" in r for r in kill_reasons) and len(kill_reasons) == 1:
            verdict = "THIN"
        else:
            verdict = "KILL" if not tripwire["tripwire_kill"] else "TRIPWIRE-KILL"
    else:
        pass_false_lock = (n_false <= 1) and (fl_ub is not None) and (fl_ub <= FALSE_LOCK_UB_PCT / 100.0)
        pass_ev = (t_sd is not None) and (t_sd >= T_BAR) and (mean_ev is not None) and (mean_ev >= EV_FLOOR_C)
        symmetric_kill_ev = (ev_ub is not None) and (ev_ub < EV_KILL_UB_C)
        if symmetric_kill_ev:
            verdict = "KILL"
            kill_reasons.append(f"one-sided 98.33% UB of mean net EV {ev_ub:.4f}c < {EV_KILL_UB_C}c -- "
                                 f"fee-dead")
        elif pass_false_lock and pass_ev:
            verdict = "GO"
        else:
            verdict = "FAIL"
            if not pass_false_lock:
                kill_reasons.append(f"false-lock bar not met: n_false={n_false}, "
                                     f"wilson_ub={fl_ub}")
            if not pass_ev:
                kill_reasons.append(f"EV bar not met: t={t_sd}, mean_ev_c={mean_ev}")

    summary = {
        "verdict": verdict, "kill_reasons": kill_reasons,
        "n_locks": n_locks, "n_false_locks": n_false,
        "false_lock_rate": (n_false / n_locks if n_locks else None),
        "false_lock_wilson_ub_pct_z2128": (fl_ub * 100 if fl_ub is not None else None),
        "n_priced": n_priced, "n_station_day_clusters": n_sd_clusters,
        "n_stations_priced": n_stations_priced,
        "mean_net_ev_c_station_day": mean_ev, "se_station_day": sd_stat["se"],
        "t_stat_station_day": t_sd, "df_station_day": sd_stat["df"],
        "one_sided_9833_ub_ev_c": ev_ub,
        "calendar_date_sensitivity": cal_stat,
        "fill_coverage_lock_station_days": fill_coverage,
        "untradeable_n": len(all_recs) - sum(1 for r in all_recs if r.get("priced")),
        "untradeable_pct": (1 - (sum(1 for r in all_recs if r.get("priced")) / len(all_recs))
                             if all_recs else None),
        "min_n_reached": min_n_reached,
    }
    return summary


def main():
    guard_results, surviving, station_day_obs = run_guard()
    if len(surviving) < MIN_STATIONS:
        out = {"phase_reached": "guard", "guard": guard_results, "surviving_stations": surviving,
               "verdict": "KILL", "reason": "<2 stations survive asos1min inclusion guard"}
        write_outputs(out, guard_results, surviving, None, [], None)
        print("\nKILL: <2 stations survive the asos1min inclusion guard.")
        return
    if GUARD_ONLY:
        out = {"phase_reached": "guard", "guard": guard_results, "surviving_stations": surviving}
        write_outputs(out, guard_results, surviving, None, [], None)
        return

    tripwire = run_tripwire(surviving, station_day_obs)
    if tripwire["tripwire_kill"]:
        out = {"phase_reached": "tripwire", "guard": guard_results, "surviving_stations": surviving,
               "tripwire": tripwire, "verdict": "TRIPWIRE-KILL",
               "reason": f"median first-fill price {tripwire['median_first_fill_price_c']}c "
                         f">= {TRIPWIRE_PRICE_C}c on first 30 window days"}
        write_outputs(out, guard_results, surviving, tripwire, [], None)
        print(f"\nTRIPWIRE-KILL: median first-fill price {tripwire['median_first_fill_price_c']}c "
              f">= {TRIPWIRE_PRICE_C}c. Stopping before full pull, per spec.")
        return
    if TRIPWIRE_ONLY:
        out = {"phase_reached": "tripwire", "guard": guard_results, "surviving_stations": surviving,
               "tripwire": tripwire}
        write_outputs(out, guard_results, surviving, tripwire, [], None)
        return

    all_recs = run_full(surviving, station_day_obs)
    summary = compute_verdict(all_recs, guard_results, surviving, tripwire)
    print("\n" + "=" * 100)
    print("VERDICT:", summary["verdict"])
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("=" * 100)
    out = {"phase_reached": "full", "guard": guard_results, "surviving_stations": surviving,
           "tripwire": tripwire, "summary": summary}
    write_outputs(out, guard_results, surviving, tripwire, all_recs, summary)


def write_outputs(out, guard_results, surviving, tripwire, all_recs, summary):
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    payload = dict(out)
    payload["window_start"] = WINDOW_START.isoformat()
    payload["window_end"] = WINDOW_END.isoformat()
    payload["station_universe"] = STATIONS
    payload["records"] = all_recs
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=1, default=str)
    print(f"\nwrote {OUT_JSON}  ({len(all_recs)} records)")


if __name__ == "__main__":
    main()
