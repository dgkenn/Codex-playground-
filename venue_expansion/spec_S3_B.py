#!/usr/bin/env python3
"""spec_S3_B.py -- BUILD B, independent replication of pre-registered SPEC S3.

"ForecastEx daily-temperature lock study: false-lock rate + flat-fee EV on the venue's own trade
tape." See task spec text (reproduced in venue_expansion/out/spec_S3_B.md) for the frozen bars.

THIS IS AN INDEPENDENT BUILD. It does not import, read, or otherwise consult venue_expansion/spec_S3.py
or any spec_S3_A.* file. It writes its own CSV parser, its own lock walk, its own tape/settlement join,
and its own clustered statistics from the spec text. The one piece of code it DOES reuse verbatim is
venue_expansion/kwx_lock_rule.py -- the deployed sustain-3/margin lock rule -- because the spec
explicitly requires that exact rule, byte-identical, not a reimplementation.

DATA SOURCES (all read-only, public, no auth):
  - https://forecastex-public-data.s3.amazonaws.com  (pairs/, prices/, daily_summary/ -- the venue's
    own trade tape and settlement records)
  - https://forecastex.com/api/products  (the venue's OWN live product catalog -- used to identify the
    Weather Underground / METAR station for each city; see STATION MAPPING section below for why this,
    not the cached CFTC PDF, is the operative source)
  - https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py  (IEM true 1-minute ASOS archive --
    the obs feed that drives the lock rule; same endpoint/semantics as tracka_chicago_1min.py)

CACHING: raw pulls are cached under venue_expansion/cache/ and never re-fetched once on disk:
  - venue_expansion/cache/forecastex/            -- raw pairs_YYYYMMDD.csv / prices_YYYYMMDD.csv /
                                                     summary_YYYYMMDD.csv (shared raw-bytes cache; these
                                                     are the venue's own public files, not analysis, so
                                                     reusing whatever of them already happened to be on
                                                     disk from earlier probing is a cache hit, not a
                                                     dependency on another build)
  - venue_expansion/cache/forecastex/api_products/ -- venue's live product-catalog API, paginated
  - venue_expansion/cache/forecastex_study/       -- a legacy raw IEM-1min cache (station, date-range)
                                                     left on disk from earlier probing in this repo.
                                                     Read-only reuse of raw NOAA/IEM observations (never
                                                     re-pulled) for LAX/LGA/MDW/SEA/SFO; the missing tail
                                                     of the window is fetched fresh into this build's own
                                                     cache dir below. This is public weather data, not
                                                     another build's analysis -- reusing it is exactly
                                                     the "cache aggressively, never re-pull" instruction.
  - venue_expansion/cache/spec_S3_B/              -- this build's OWN fresh pulls (1-min obs deltas for
                                                     stations/ranges not already cached elsewhere).

STATION MAPPING -- WHY THE LIVE PRODUCTS API, NOT THE PDF:
GROUNDING said "the contract terms PDF ... and the per-product filings under product_filings/ name the
Weather Underground station." We read fx_daily_temp.pdf (the CFTC 40.2(a) self-certification, all 6
pages, cached) in full: it is entirely generic ("region", "the designated weather observation station
for the specified city" -- no station table, just instructions for a human to look it up on
wunderground.com by city name). We also enumerated product_filings/ (255 keys): the only Daily
Temperature filings are "Daily Temperature Forecast Contract.pdf" (== the cached fx_daily_temp.pdf) and
a Celsius sibling -- neither has a per-city table either. So the literal claim in GROUNDING does not
hold; disclosed here rather than silently worked around.
We also checked notices_to_members/NTM_2026-45 (Feb 10, 2026, "Changing Source Agency for Daily
Temperature Contracts") -- it confirms the WU/METAR switch effective for contracts referencing Feb 11,
2026 onward (consistent with our Feb 17 window start) but again gives no per-city list.
The station identity is authoritatively published by ForecastEx itself at runtime, in its own live
product-catalog API (https://forecastex.com/api/products, paginated, cached under
cache/forecastex/api_products/products_p*.json). Each Daily-Temperature product's `description` field
states e.g. "...as reported by the Weather Underground for the Hartsfield-Jackson Atlanta Intl Airport
Station (KATL)." -- an explicit ICAO station code. This is the SAME fact the PDF defers to (WU's
station page for the named city), just published by the venue directly instead of requiring a human to
click through wunderground.com. We parse the station code from this field programmatically (see
build_station_map()) rather than hand-typing it, so the mapping is reproducible from the cached JSON on
disk. Crucially, this is what catches the Denver trap: UHBKF's description says "Buckley Space Force
Base Station (KBKF)" -- NOT Denver International (KDEN) -- matching GROUNDING's explicit warning not to
guess. KBKF, verified below, is not in IEM's 1-minute archive at all (0 rows on 3 spot-checked dates
despite existing in the hourly METAR archive) and is dropped by the inclusion guard on that basis.

TIMEZONE / DATE-ALIGNMENT HANDLING -- see build_tz_map() and the worked example in
venue_expansion/out/spec_S3_B.md. Summary: pairs_YYYYMMDD.csv is bucketed by the CT calendar date of
`expiration_date`, NOT by the fill's own date, and NOT by the ticker's own embedded observation date --
confirmed empirically (pairs_20260722.csv holds fills timestamped both 2026-07-21 and 2026-07-22 for a
ticker whose own date suffix is 072126). We therefore never assume file date == observation date == fill
date; we join purely on event_contract across a padded range of daily files, exactly as instructed.

SETTLEMENT -- see build_settlement_index(). daily_prices rows for a contract's OWN trading day carry a
non-final `settlement_price` (e.g. 0.83) with nonzero `open_interest` -- that is a provisional mark, NOT
the outcome. The TRUE settlement only appears in the row where open_interest == 0 (verified: the same
ticker's row one file-day later shows settlement_price flipping to exactly 1.00 or 0.00 with
open_interest == 0). We use ONLY the open_interest==0 row as settlement ground truth, per GROUNDING's
"never decide an outcome yourself" rule -- this field is the venue's own published settlement, we just
have to pick the right row for it.

LOCK SIGNAL vs kwx_lock_rule's PRICE GATE -- see run_lock_walk(). kwx_lock_rule.locked_orders bundles a
price gate (rung["yes_ask_c"]/["no_ask_c"] must be truthy and <= MAX_PAY_CENTS=98) into the SAME
function as the geometric margin/sustain lock decision. The spec's entry_rule requires "Signal uses obs
ONLY; no tape, no price, no outcome input," and separately names only MARGIN_F / sustain-3 / glitch
bounds as the frozen parameters to reuse verbatim. We therefore call locked_orders with placeholder
yes_ask_c=no_ask_c=1 (both always <=98 and truthy) for every rung, so the price gate is structurally
inert and every "lock" decision is governed solely by extreme_f vs. floor/cap +/- margin. This is
disclosed, not silent, and does not touch the sustain-3/glitch/margin math, which is used byte-verbatim.
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
import kwx_lock_rule as R  # byte-verbatim shim; see module docstring of that file.

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "*/*", "User-Agent": "Mozilla/5.0 (compatible; spec-S3-B/1.0; research, read-only)"}

S3_BASE = "https://forecastex-public-data.s3.amazonaws.com"
ASOS_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
ASOS_ROUTINE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
PRODUCTS_API = "https://forecastex.com/api/products"

CACHE_RAW = os.path.join(HERE, "cache", "forecastex")            # shared raw pairs_/prices_/summary_
CACHE_API = os.path.join(CACHE_RAW, "api_products")               # products API pages
CACHE_LEGACY_1MIN = os.path.join(HERE, "cache", "forecastex_study")  # legacy raw IEM 1-min (read-only reuse)
CACHE_B = os.path.join(HERE, "cache", "spec_S3_B")                 # this build's own fresh pulls
for d in (CACHE_RAW, CACHE_API, CACHE_B):
    os.makedirs(d, exist_ok=True)

# ------------------------------------------------------------------------------------------------------
# WINDOW -- corrected per orchestrator note (temperature contracts did not exist before 2026-02-17).
# Every pass bar below is otherwise FROZEN from the pre-registered spec text.
# ------------------------------------------------------------------------------------------------------
WINDOW_START = dt.date(2026, 2, 17)
WINDOW_END = dt.date(2026, 7, 26)

# candidate stations: EXACTLY the bare IEM station codes named in the orchestrator's verified
# "CITY VOLUME" list (pre-specified before any lock/tape data was read here, to avoid picking winners
# after the fact). BKF is included deliberately -- it is expected, from the orchestrator's own warning,
# to be a live candidate for guard failure, and dropping it only via the mechanical guard (not by
# eyeballing the warning and excluding it by hand) is the point.
CANDIDATE_STATIONS = ["LAX", "LAS", "LGA", "SEA", "SFO", "MIA", "PHX", "MDW", "AUS", "BKF"]

MIN_DAY_OBS_1MIN = 100     # spec's own inclusion-guard obs/day floor
MIN_DAY_FRAC = 0.70        # spec's own inclusion-guard day-coverage floor
UNTRADEABLE_MAX_MIN = 60   # spec: no fill within 60 min of lock => untradeable
SLIPPAGE_C = 1.0
FEE_C = 1.0
EARLY_TRIPWIRE_DAYS = 30
EARLY_TRIPWIRE_PRICE_C = 98.5

WILSON_Z_FALSELOCK = 2.128   # spec: one-sided 98.33%, Bonferroni-3
FALSELOCK_UB_BAR = 0.025
EV_T_BAR = 2.25
EV_MEAN_BAR_C = 0.5
EV_KILL_UB_C = 0.2

# --------------------------------------------------------------------------------------------------------
# small HTTP helpers -- polite: sequential, ~1 req/sec, retry w/ backoff.
# --------------------------------------------------------------------------------------------------------
def _get_bytes(url, timeout=40, retries=5, backoff=1.7):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
                return resp.read(), resp.status
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 404:
                return None, 404
            if e.code not in (429, 500, 502, 503, 504):
                return None, e.code
            time.sleep(backoff * (attempt + 1))
        except Exception as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
    return None, f"ERR:{last_err}"


def _cache_file_get_or_fetch(cache_path, url, is_json=False, polite_sleep=1.0):
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        with open(cache_path, "rb") as f:
            raw = f.read()
        return raw
    raw, status = _get_bytes(url)
    if raw is None:
        return None
    with open(cache_path, "wb") as f:
        f.write(raw)
    time.sleep(polite_sleep)
    return raw


# ==========================================================================================================
# STEP 1 -- STATION MAPPING (from ForecastEx's own live product API; see module docstring)
# ==========================================================================================================
def fetch_products_api():
    """Paginate https://forecastex.com/api/products, cache each page, return the merged product list."""
    all_products = []
    page = 1
    total_pages = None
    while total_pages is None or page <= total_pages:
        cache_path = os.path.join(CACHE_API, f"products_p{page}.json")
        raw = _cache_file_get_or_fetch(cache_path, f"{PRODUCTS_API}?page={page}", polite_sleep=0.3)
        if raw is None:
            break
        d = json.loads(raw)
        body = d.get("body")
        if isinstance(body, str):
            body = json.loads(body)
        data = body.get("data")
        if isinstance(data, str):
            data = json.loads(data)
        if data:
            all_products.extend(data)
        total_pages = body.get("total_pages", page)
        page += 1
    return all_products


# Station -> IANA timezone. Standard geographic fact about each airport, not sourced from any API field
# (the products API gives the ICAO station, not its timezone). Needed to (a) run the lock walk on the
# station's own local day and (b) interpret the ticker's embedded MMDDYY as that local calendar date.
STATION_TZ = {
    "LAX": "America/Los_Angeles", "LAS": "America/Los_Angeles", "SEA": "America/Los_Angeles",
    "SFO": "America/Los_Angeles", "PHX": "America/Phoenix",  # AZ does not observe DST
    "BKF": "America/Denver", "MDW": "America/Chicago", "AUS": "America/Chicago",
    "LGA": "America/New_York", "MIA": "America/New_York", "ATL": "America/New_York",
    "BOS": "America/New_York", "CLT": "America/New_York", "DCA": "America/New_York",
    "BNA": "America/Chicago", "DFW": "America/Chicago", "DTW": "America/New_York",
    "HOU": "America/Chicago", "JAX": "America/New_York", "MSP": "America/Chicago",
    "MSY": "America/Chicago", "OKC": "America/Chicago", "PHL": "America/New_York",
    "SAT": "America/Chicago",
}


def build_station_map():
    """Returns {bare_station: {icao, city_name, wu_url, tz, product_hi, product_lo}} parsed from the
    venue's own live product catalog (cached JSON). Deterministic / reproducible from disk."""
    products = fetch_products_api()
    temp = [p for p in products if p["product_id"].startswith(("UH", "UL"))]
    station_map = {}
    for p in temp:
        pid = p["product_id"]
        kind = pid[:2]  # UH or UL
        bare = pid[2:]
        m = re.search(r"Station \(K([A-Z0-9]+)\)", p.get("description", ""))
        if not m:
            continue
        icao = "K" + m.group(1)
        rec = station_map.setdefault(bare, {
            "bare": bare, "icao": icao, "city_name": p["name"].replace(" Daily Temperature High", "")
                                                                .replace(" Daily Temperature Low", ""),
            "wu_url": p.get("source_agency_url"), "tz": STATION_TZ.get(bare),
        })
        rec["product_hi" if kind == "UH" else "product_lo"] = pid
    return station_map


# ==========================================================================================================
# STEP 2 -- IEM 1-MINUTE ASOS FEED + INCLUSION GUARD
# ==========================================================================================================
def _load_legacy_1min(station):
    """Read-only reuse of a pre-existing raw IEM-1min cache dump (public NOAA/IEM data, not analysis)
    left on disk from earlier probing in this repo. Returns sorted [(dt_utc, tempF), ...] or [] if this
    station has no legacy cache."""
    pattern = os.path.join(CACHE_LEGACY_1MIN, f"iem1min_{station}_*.json")
    import glob
    files = sorted(glob.glob(pattern))
    out = []
    for fp in files:
        try:
            arr = json.load(open(fp))
        except Exception:
            continue
        for t, v in arr:
            try:
                out.append((dt.datetime.fromisoformat(t), float(v)))
            except Exception:
                continue
    out.sort(key=lambda x: x[0])
    return out


def fetch_iem_1min_range(station, start_utc, end_utc):
    """Fetch [start_utc, end_utc) 1-min ASOS obs for `station` (bare code), using legacy cache where it
    already covers the range and this build's own cache (venue_expansion/cache/spec_S3_B/) for the rest.
    Returns sorted [(datetime_utc, tempF), ...]."""
    legacy = _load_legacy_1min(station)
    if legacy:
        legacy_start, legacy_end = legacy[0][0], legacy[-1][0]
    else:
        legacy_start = legacy_end = None

    chunks = [(start_utc, end_utc)]
    # if legacy covers a leading sub-range, only fetch fresh what's left (the trailing gap).
    if legacy and legacy_start <= start_utc and legacy_end >= start_utc:
        remaining_start = legacy_end
        if remaining_start < end_utc:
            chunks = [(remaining_start, end_utc)]
        else:
            chunks = []
    fresh = []
    for cs, ce in chunks:
        key = f"iem1min_{station}_{cs:%Y%m%dT%H%M}_{ce:%Y%m%dT%H%M}.json"
        cache_path = os.path.join(CACHE_B, key)
        if os.path.exists(cache_path):
            arr = json.load(open(cache_path))
        else:
            sts = cs.strftime("%Y-%m-%dT%H:%MZ")
            ets = ce.strftime("%Y-%m-%dT%H:%MZ")
            q = f"station={station}&vars=tmpf&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma"
            raw, status = _get_bytes(f"{ASOS_1MIN}?{q}")
            arr = []
            if raw:
                txt = raw.decode("utf-8", "replace")
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
                    arr.append([t.isoformat(), v])
            json.dump(arr, open(cache_path, "w"))
            time.sleep(1.0)
        for t, v in arr:
            fresh.append((dt.datetime.fromisoformat(t), float(v)))
    combined = legacy + fresh if legacy else fresh
    combined = [(t, v) for t, v in combined if start_utc <= t < end_utc]
    combined.sort(key=lambda x: x[0])
    return combined


def run_inclusion_guard(station_map, log=print):
    """Pre-registered mechanical guard: station enters iff asos1min returns >=100 obs/day on >=70% of
    window days. Per-day is counted on the STATION'S OWN LOCAL calendar day (not UTC), since that's the
    day the lock walk/obs coverage actually matters for."""
    results = {}
    for station in CANDIDATE_STATIONS:
        info = station_map.get(station)
        if info is None or info.get("tz") is None:
            results[station] = {"pass": False, "reason": "no_station_map_entry"}
            continue
        tz = ZoneInfo(info["tz"])
        day0_local = dt.datetime(WINDOW_START.year, WINDOW_START.month, WINDOW_START.day, 0, 0, tzinfo=tz)
        dayN_local = dt.datetime(WINDOW_END.year, WINDOW_END.month, WINDOW_END.day, 0, 0, tzinfo=tz) + dt.timedelta(days=1)
        start_utc = day0_local.astimezone(dt.timezone.utc)
        end_utc = dayN_local.astimezone(dt.timezone.utc)
        obs = fetch_iem_1min_range(station, start_utc, end_utc)
        # bucket by local calendar day
        per_day = {}
        for t, v in obs:
            local_day = t.astimezone(tz).date()
            per_day[local_day] = per_day.get(local_day, 0) + 1
        n_days_total = (WINDOW_END - WINDOW_START).days + 1
        n_days_ok = sum(1 for d, n in per_day.items() if WINDOW_START <= d <= WINDOW_END and n >= MIN_DAY_OBS_1MIN)
        frac = n_days_ok / n_days_total
        passed = frac >= MIN_DAY_FRAC
        results[station] = {
            "icao": info["icao"], "n_days_total": n_days_total, "n_days_ok": n_days_ok,
            "frac_days_ok": round(frac, 4), "n_obs_total": len(obs), "pass": passed,
        }
        log(f"  guard {station:4s} ({info['icao']}): {n_days_ok}/{n_days_total} days >= {MIN_DAY_OBS_1MIN} obs "
            f"({100*frac:.1f}%)  {'PASS' if passed else 'FAIL'}")
    return results


# ==========================================================================================================
# STEP 3/4 -- RAW TAPE (pairs/) AND SETTLEMENT (prices/) PULL, GLOBAL JOIN BY event_contract
# ==========================================================================================================
def _daterange(d0, d1):
    d = d0
    while d <= d1:
        yield d
        d += dt.timedelta(days=1)


def _fetch_day_csv_rows(kind, d, prefixes):
    """kind: 'pairs' or 'prices'. Downloads (or reads cached) raw CSV for calendar day `d`, filters rows
    whose event_contract starts with one of `prefixes` (our candidate cities' UH.../UL... product ids),
    returns list of dict rows. The FULL raw file is cached to disk regardless of filtering (provenance /
    honors "cache all pulls", not just the post-filter slice).

    NOTE on prices/ naming: bucket listing (verified live) shows the actual S3 object key is
    "prices/daily_prices_YYYYMMDD.csv", NOT "prices/prices_YYYYMMDD.csv" -- "prices_YYYYMMDD.csv" 404s
    live. (A short-named "prices_20260721.csv"/"prices_20260722.csv" already sat in the shared cache
    dir from earlier probing in this repo, fetched correctly under the real key by whatever pulled them
    first and saved locally under a shortened name; we treat those as a valid cache hit below rather
    than re-fetching, but every NEW day is fetched from the real key and cached under the real
    filename.) pairs/ objects, by contrast, really are named "pairs_YYYYMMDD.csv" (verified).
    """
    real_fn = f"daily_prices_{d:%Y%m%d}.csv" if kind == "prices" else f"pairs_{d:%Y%m%d}.csv"
    cache_path = os.path.join(CACHE_RAW, real_fn)
    legacy_short_path = os.path.join(CACHE_RAW, f"{kind}_{d:%Y%m%d}.csv")  # pre-existing shortened name
    if os.path.exists(legacy_short_path) and os.path.getsize(legacy_short_path) > 0 and not os.path.exists(cache_path):
        cache_path = legacy_short_path
    if not (os.path.exists(cache_path) and os.path.getsize(cache_path) > 0):
        raw, status = _get_bytes(f"{S3_BASE}/{kind}/{real_fn}")
        if raw is None:
            return None  # missing day (e.g. outside published range) -- caller decides how to treat
        with open(cache_path, "wb") as f:
            f.write(raw)
        time.sleep(1.0)
    out = []
    with open(cache_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ec = row.get("event_contract", "")
            if ec.startswith(prefixes):
                out.append(row)
    return out


def build_prefixes(surviving_stations, station_map):
    prefixes = []
    for st_ in surviving_stations:
        info = station_map[st_]
        if info.get("product_hi"):
            prefixes.append(info["product_hi"] + "_")
        if info.get("product_lo"):
            prefixes.append(info["product_lo"] + "_")
    return tuple(prefixes)


def build_fills_index(surviving_stations, station_map, d0, d1, log=print):
    """Global event_contract -> sorted [(pair_time_utc, yes_price, no_price), ...] index, built by
    scanning every pairs_YYYYMMDD.csv in [d0,d1] and keeping only rows for our candidate tickers. Padded
    by the caller to catch the venue's expiration-CT-date file bucketing (see module docstring)."""
    prefixes = build_prefixes(surviving_stations, station_map)
    idx = {}
    n_days = (d1 - d0).days + 1
    for i, d in enumerate(_daterange(d0, d1)):
        rows = _fetch_day_csv_rows("pairs", d, prefixes)
        if rows is None:
            log(f"  pairs {d} -- MISSING (no file published for this day)")
            continue
        for row in rows:
            ec = row["event_contract"]
            try:
                pt = dt.datetime.fromisoformat(row["pair_time"])
                yp = float(row["yes_price"])
                np_ = float(row["no_price"])
            except Exception:
                continue
            idx.setdefault(ec, []).append((pt.astimezone(dt.timezone.utc), yp, np_))
        if (i + 1) % 20 == 0:
            log(f"  pairs pull progress: {i+1}/{n_days} days, {len(idx)} tickers indexed so far")
    for ec in idx:
        idx[ec].sort(key=lambda x: x[0])
    return idx


def build_settlement_index(surviving_stations, station_map, d0, d1, log=print):
    """Global event_contract -> {'yes_settlement': 0.0/1.0/None, 'source_date': date, 'open_interest': int}
    using ONLY the row where open_interest == 0 (the true final-settlement row; see module docstring for
    why the contract's own trading-day row is NOT this). subtype='YES' row's settlement_price is used
    directly, cross-checked against the NO row (must sum to 1.0)."""
    prefixes = build_prefixes(surviving_stations, station_map)
    raw_rows = {}  # event_contract -> list of (date, subtype, settlement_price, open_interest)
    n_days = (d1 - d0).days + 1
    for i, d in enumerate(_daterange(d0, d1)):
        rows = _fetch_day_csv_rows("prices", d, prefixes)
        if rows is None:
            log(f"  prices {d} -- MISSING (no file published for this day)")
            continue
        for row in rows:
            ec = row["event_contract"]
            try:
                oi = int(float(row["open_interest"]))
                sp = float(row["settlement_price"])
            except Exception:
                continue
            raw_rows.setdefault(ec, []).append((d, row["subtype"], sp, oi))
        if (i + 1) % 20 == 0:
            log(f"  prices pull progress: {i+1}/{n_days} days, {len(raw_rows)} tickers indexed so far")

    out = {}
    n_inconsistent = 0
    for ec, rows in raw_rows.items():
        yes_final = [(d, sp, oi) for d, sub, sp, oi in rows if sub == "YES" and oi == 0]
        no_final = [(d, sp, oi) for d, sub, sp, oi in rows if sub == "NO" and oi == 0]
        if not yes_final:
            out[ec] = {"yes_settlement": None, "reason": "no_open_interest_zero_row_in_pulled_range"}
            continue
        yes_final.sort(key=lambda x: x[0])
        d_settle, sp_yes, _ = yes_final[0]
        ok = abs(sp_yes - 0.0) < 1e-6 or abs(sp_yes - 1.0) < 1e-6
        if not ok:
            out[ec] = {"yes_settlement": None, "reason": f"settlement_price_not_binary_{sp_yes}"}
            continue
        if no_final:
            sp_no = sorted(no_final, key=lambda x: x[0])[0][1]
            if abs((sp_yes + sp_no) - 1.0) > 1e-6:
                n_inconsistent += 1
        out[ec] = {"yes_settlement": sp_yes, "settle_date": d_settle.isoformat()}
    if n_inconsistent:
        log(f"  WARNING: {n_inconsistent} tickers have YES+NO settlement_price != 1.0 at open_interest==0")
    return out


# ==========================================================================================================
# LOCK WALK -- per station, per local observation date, per kind (UH=max / UL=min)
# ==========================================================================================================
def parse_rungs_for_day(fills_idx, settle_idx, product_prefix, local_date_str):
    """Enumerate every distinct strike listed for `product_prefix` on `local_date_str` (MMDDYY, matching
    the ticker's own embedded date) by scanning ticker names present in EITHER the fills or settlement
    index (a contract can settle with zero trades and still be a real rung). Rung floor/cap value comes
    ONLY from parsing the ticker string -- never from any price field."""
    seen = set()
    for ec in list(fills_idx.keys()) + list(settle_idx.keys()):
        if ec.startswith(product_prefix + "_" + local_date_str + "_"):
            seen.add(ec)
    rungs = []
    for ec in seen:
        m = re.match(rf"^{re.escape(product_prefix)}_{local_date_str}_([0-9.]+)$", ec)
        if not m:
            continue
        strike = float(m.group(1))
        rungs.append({"ticker": ec, "strike": strike})
    rungs.sort(key=lambda r: r["strike"])
    return rungs


def run_lock_walk_for_station_day(station, local_date, station_map, obs_by_station, fills_idx, settle_idx,
                                   tripwire_only=False):
    """Runs the byte-verbatim sustain-3/margin lock rule over the station's own local day, for BOTH the
    UH (kind=max, floor=strike) and UL (kind=min, cap=strike) product families. Returns a list of fire
    dicts (one per ticker that ever locks that station-day)."""
    info = station_map[station]
    tz = ZoneInfo(info["tz"])
    mmddyy = f"{local_date.month:02d}{local_date.day:02d}{local_date.year % 100:02d}"
    day_start_local = dt.datetime(local_date.year, local_date.month, local_date.day, 0, 0, tzinfo=tz)
    day_end_local = day_start_local + dt.timedelta(days=1)
    day_start_utc = day_start_local.astimezone(dt.timezone.utc)
    day_end_utc = day_end_local.astimezone(dt.timezone.utc)

    obs_all = obs_by_station.get(station, [])
    # obs_all is sorted [(dt_utc, tempF)]; slice to this local day (station's own local calendar day).
    lo = _bisect_left_dt(obs_all, day_start_utc)
    hi = _bisect_left_dt(obs_all, day_end_utc)
    day_obs = obs_all[lo:hi]
    if len(day_obs) < MIN_DAY_OBS_1MIN:
        return [], "thin_station_data"

    fires = []
    for kind, product_key, is_max in (("max", "product_hi", True), ("min", "product_lo", False)):
        product_prefix = info.get(product_key)
        if not product_prefix:
            continue
        rungs_meta = parse_rungs_for_day(fills_idx, settle_idx, product_prefix, mmddyy)
        if not rungs_meta:
            continue
        rungs = []
        for rm in rungs_meta:
            if is_max:
                rungs.append({"ticker": rm["ticker"], "floor": rm["strike"], "cap": None,
                               "yes_ask_c": 1, "no_ask_c": 1})
            else:
                rungs.append({"ticker": rm["ticker"], "floor": None, "cap": rm["strike"],
                               "yes_ask_c": 1, "no_ask_c": 1})
        locked = {}
        obs_stream = day_obs
        iso_strs = [t.isoformat() for t, _ in obs_stream]
        vals = [v for _, v in obs_stream]
        n = len(obs_stream)

        # PERFORMANCE NOTE (does not touch the frozen rule's math): R.sustained_extreme(prefix_i, kind) is
        # monotonic non-decreasing in i for kind="max" (non-increasing for "min") -- once a qualifying
        # sustain-3 window exists in a prefix, it still exists in every longer prefix, so the best
        # achievable windowed extreme can only improve as more of the day's obs arrive. Calling the
        # verbatim function once per MINUTE (naive walk) is O(n^2) purely from re-scanning the growing
        # prefix n times; on 160 days x 9 stations x 2 kinds x ~1440 min/day this does not finish in
        # reasonable time. We instead binary-search, per rung, for the first index at which
        # R.sustained_extreme(prefix_i, kind) crosses that rung's own floor/cap+margin threshold --
        # exploiting the monotonicity to cut ~1440 calls/day down to ~O(log n) calls per rung, while still
        # calling the exact same byte-verbatim function as the sole source of truth for every value used.
        def extreme_at(i):
            return R.sustained_extreme(list(zip(iso_strs[:i], vals[:i])), kind)

        # cache to avoid recomputing the same prefix index across different rungs' binary searches
        _cache = {}
        def extreme_at_cached(i):
            v = _cache.get(i, "_MISS_")
            if v == "_MISS_":
                v = extreme_at(i)
                _cache[i] = v
            return v

        final_extreme = extreme_at_cached(n)
        for rung in rungs:
            floor, cap = rung["floor"], rung["cap"]
            if kind == "max":
                threshold = floor + R.MARGIN_F  # only the floor-only (uncapped) branch is reachable; see
                                                  # locked_orders -- ForecastEx UH rungs are cap=None.
            else:
                threshold = cap - R.MARGIN_F
            crosses = (final_extreme is not None) and (
                (kind == "max" and final_extreme > threshold) or (kind == "min" and final_extreme < threshold))
            if not crosses:
                continue
            lo, hi = 1, n
            while lo < hi:
                mid = (lo + hi) // 2
                v = extreme_at_cached(mid)
                ok = (v is not None) and ((kind == "max" and v > threshold) or (kind == "min" and v < threshold))
                if ok:
                    hi = mid
                else:
                    lo = mid + 1
            i_cross = lo
            extreme_f = extreme_at_cached(i_cross)
            ts_iso = iso_strs[i_cross - 1]
            orders = R.locked_orders([rung], extreme_f, kind, margin=R.MARGIN_F)
            for ticker, side, _cap_c, cushion in orders:
                if ticker not in locked:
                    locked[ticker] = {"side": side, "lock_utc": ts_iso, "extreme_f": round(extreme_f, 2),
                                       "cushion_f": round(cushion, 2)}
        for ticker, linfo in locked.items():
            fires.append({
                "station": station, "icao": info["icao"], "local_date": local_date.isoformat(),
                "kind": kind, "ticker": ticker, "side": linfo["side"], "lock_utc": linfo["lock_utc"],
                "extreme_f": linfo["extreme_f"], "cushion_f": linfo["cushion_f"],
            })
    return fires, None


def _bisect_left_dt(seq, target):
    import bisect
    keys = [x[0] for x in seq]
    return bisect.bisect_left(keys, target)


# ==========================================================================================================
# PRICING / EV
# ==========================================================================================================
def price_fire(fire, fills_idx):
    """First tape fill with pair_time >= lock_utc for this ticker. Untradeable if none within 60 min.
    NEVER uses the other side's price: yes-side lock always uses the fill's own yes_price."""
    ticker = fire["ticker"]
    lock_utc = dt.datetime.fromisoformat(fire["lock_utc"])
    fills = fills_idx.get(ticker, [])
    for pt, yp, np_ in fills:
        if pt >= lock_utc:
            gap_min = (pt - lock_utc).total_seconds() / 60.0
            if gap_min > UNTRADEABLE_MAX_MIN:
                return {"tradeable": False, "reason": "no_fill_within_60min", "gap_min": round(gap_min, 1)}
            return {"tradeable": True, "fill_price_c": round(yp * 100.0, 4), "gap_min": round(gap_min, 2),
                    "fill_time_utc": pt.isoformat()}
    return {"tradeable": False, "reason": "no_fill_at_or_after_lock"}


def wilson_upper(k, n, z):
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, (center + half) / denom)


def clustered_mean_tstat(values, cluster_ids):
    """CR1 sandwich SE for a simple sample mean, clustered by `cluster_ids`. Standard formula: treat the
    mean as OLS-on-intercept; Var(mean) = (1/n^2) * sum_c (sum_{i in c} residual_i)^2, with the usual
    C/(C-1) small-sample cluster correction."""
    n = len(values)
    if n == 0:
        return None
    grand_mean = sum(values) / n
    clusters = {}
    for v, c in zip(values, cluster_ids):
        clusters.setdefault(c, []).append(v)
    C = len(clusters)
    if C < 2:
        return {"mean": grand_mean, "se": None, "t": None, "n_clusters": C, "n": n}
    ssum = 0.0
    for c, vals in clusters.items():
        u = sum(v - grand_mean for v in vals)
        ssum += u * u
    var = ssum / (n * n) * (C / (C - 1))
    se = math.sqrt(var) if var > 0 else 0.0
    t = grand_mean / se if se > 0 else float("inf")
    return {"mean": grand_mean, "se": se, "t": t, "n_clusters": C, "n": n}


# ==========================================================================================================
# MAIN
# ==========================================================================================================
def main():
    out = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "window_start": WINDOW_START.isoformat(),
           "window_end": WINDOW_END.isoformat()}

    print("=" * 100)
    print("STEP 1 -- STATION MAPPING (from ForecastEx's own live product-catalog API)")
    print("=" * 100)
    station_map = build_station_map()
    mapping_report = []
    for st_ in CANDIDATE_STATIONS:
        info = station_map.get(st_)
        if info is None:
            print(f"  {st_}: NOT FOUND in product catalog -- dropped")
            mapping_report.append({"station": st_, "found": False})
            continue
        print(f"  {st_:4s} -> {info['icao']}  {info['city_name']:24s} tz={info['tz']}  "
              f"hi={info.get('product_hi')}  lo={info.get('product_lo')}  src={info['wu_url']}")
        mapping_report.append({"station": st_, "found": True, **info})
    out["station_mapping"] = mapping_report
    out["station_mapping_source"] = ("ForecastEx live product-catalog API (https://forecastex.com/api/products), "
                                      "field `description`, regex-parsed for 'Station (KXXX)'. See module "
                                      "docstring for why this supersedes the generic CFTC filing PDF.")

    print("\n" + "=" * 100)
    print("STEP 2 -- ASOS1MIN INCLUSION GUARD")
    print("=" * 100)
    guard = run_inclusion_guard(station_map)
    out["inclusion_guard"] = guard
    surviving = [s for s in CANDIDATE_STATIONS if guard.get(s, {}).get("pass")]
    print(f"\nSurviving stations: {surviving}  (n={len(surviving)})")
    out["surviving_stations"] = surviving
    if len(surviving) < 2:
        out["verdict"] = "KILL"
        out["kill_reason"] = f"<2 stations survive the asos1min inclusion guard (n={len(surviving)})"
        write_out(out)
        print("\nKILL:", out["kill_reason"])
        return out

    # cache obs for surviving stations for reuse in tripwire + full run (already fetched during guard,
    # for the FULL window -- refetch here is a no-op cache hit).
    obs_by_station = {}
    for st_ in surviving:
        info = station_map[st_]
        tz = ZoneInfo(info["tz"])
        day0_local = dt.datetime(WINDOW_START.year, WINDOW_START.month, WINDOW_START.day, 0, 0, tzinfo=tz)
        dayN_local = dt.datetime(WINDOW_END.year, WINDOW_END.month, WINDOW_END.day, 0, 0, tzinfo=tz) + dt.timedelta(days=1)
        obs_by_station[st_] = fetch_iem_1min_range(st_, day0_local.astimezone(dt.timezone.utc),
                                                     dayN_local.astimezone(dt.timezone.utc))

    print("\n" + "=" * 100)
    print("STEP 3 -- EARLY TRIPWIRE (price data only; settlement/outcome NOT read at this step)")
    print("=" * 100)
    tw_end = WINDOW_START + dt.timedelta(days=EARLY_TRIPWIRE_DAYS - 1)
    print(f"  tripwire window: {WINDOW_START} .. {tw_end} ({EARLY_TRIPWIRE_DAYS} days)")
    # pairs pull padded by [-1, +2] days around the tripwire window per the CT-expiration-date bucketing.
    pad0 = WINDOW_START - dt.timedelta(days=1)
    pad1 = tw_end + dt.timedelta(days=2)
    tw_fills_idx = build_fills_index(surviving, station_map, pad0, pad1)
    tw_fills = []
    all_days = [WINDOW_START + dt.timedelta(days=k) for k in range(EARLY_TRIPWIRE_DAYS)]
    tw_fire_records = []
    for st_ in surviving:
        for d in all_days:
            fires, skip = run_lock_walk_for_station_day(st_, d, station_map, obs_by_station, tw_fills_idx, {})
            if skip:
                continue
            for fire in fires:
                px = price_fire(fire, tw_fills_idx)
                tw_fire_records.append({**fire, **px})
                if px.get("tradeable"):
                    tw_fills.append(px["fill_price_c"])
    out["tripwire"] = {
        "n_locks": len(tw_fire_records), "n_tradeable": len(tw_fills),
        "median_first_fill_price_c": st.median(tw_fills) if tw_fills else None,
    }
    print(f"  tripwire locks={len(tw_fire_records)} tradeable={len(tw_fills)} "
          f"median_first_fill_c={out['tripwire']['median_first_fill_price_c']}")
    if tw_fills and st.median(tw_fills) >= EARLY_TRIPWIRE_PRICE_C:
        out["verdict"] = "TRIPWIRE-KILL"
        out["kill_reason"] = (f"median first-fill-after-lock price over first {EARLY_TRIPWIRE_DAYS} days = "
                               f"{st.median(tw_fills):.2f}c >= {EARLY_TRIPWIRE_PRICE_C}c")
        write_out(out)
        print("\nTRIPWIRE-KILL:", out["kill_reason"])
        return out
    if not tw_fills:
        print("  NOTE: zero tradeable tripwire fires -- tripwire itself is not gating (nothing to compare "
              "to 98.5c), proceeding to full run per spec (tripwire only fires KILL on a measured >=98.5c).")

    print("\n" + "=" * 100)
    print("STEP 4 -- FULL WINDOW PULL: false-lock rate + fee-inclusive EV")
    print("=" * 100)
    full_pad0 = WINDOW_START - dt.timedelta(days=1)
    full_pad1_pairs = WINDOW_END + dt.timedelta(days=2)
    full_pad1_prices = WINDOW_END + dt.timedelta(days=6)  # generous settlement-finalization tail
    print("  building global fills index (pairs/)...")
    fills_idx = build_fills_index(surviving, station_map, full_pad0, full_pad1_pairs)
    print(f"  fills index: {len(fills_idx)} tickers, {sum(len(v) for v in fills_idx.values())} fills total")
    print("  building global settlement index (prices/)...")
    settle_idx = build_settlement_index(surviving, station_map, full_pad0, full_pad1_prices)
    print(f"  settlement index: {len(settle_idx)} tickers")

    all_locks = []
    all_days_full = [WINDOW_START + dt.timedelta(days=k) for k in range((WINDOW_END - WINDOW_START).days + 1)]
    skips = []
    for st_ in surviving:
        for d in all_days_full:
            fires, skip = run_lock_walk_for_station_day(st_, d, station_map, obs_by_station, fills_idx, settle_idx)
            if skip:
                skips.append({"station": st_, "date": d.isoformat(), "reason": skip})
                continue
            all_locks.extend(fires)
    print(f"  total lock fires (pre-settlement-join): {len(all_locks)}  ({len(skips)} station-day skips)")

    # join settlement + price
    records = []
    n_missing_settlement = 0
    for fire in all_locks:
        settle = settle_idx.get(fire["ticker"])
        px = price_fire(fire, fills_idx)
        rec = {**fire, **{f"px_{k}": v for k, v in px.items()}}
        if settle is None or settle.get("yes_settlement") is None:
            rec["settlement_known"] = False
            rec["settlement_reason"] = (settle or {}).get("reason", "ticker_not_in_settlement_index")
            n_missing_settlement += 1
        else:
            rec["settlement_known"] = True
            rec["yes_settlement"] = settle["yes_settlement"]
            assert fire["side"] == "yes", f"unexpected non-yes lock side: {fire}"
            rec["correct"] = (settle["yes_settlement"] == 1.0)
        records.append(rec)
    out["n_missing_settlement"] = n_missing_settlement
    out["skips"] = skips

    known = [r for r in records if r["settlement_known"]]
    n_locks = len(known)
    n_false = sum(1 for r in known if not r["correct"])
    fl_ub = wilson_upper(n_false, n_locks, WILSON_Z_FALSELOCK) if n_locks else None
    out["false_lock"] = {
        "n_locks": n_locks, "n_false": n_false,
        "false_rate": (n_false / n_locks) if n_locks else None,
        "wilson_upper_98_33": fl_ub, "z": WILSON_Z_FALSELOCK,
        "n_missing_settlement_excluded": n_missing_settlement,
    }
    print(f"\n  FALSE-LOCK RATE: {n_false}/{n_locks} ({100*n_false/n_locks:.3f}% if n_locks else '--'), "
          f"Wilson UB(z={WILSON_Z_FALSELOCK})={fl_ub}")
    print(f"  ({n_missing_settlement} lock records excluded: settlement not resolvable in pulled window)")

    tradeable = [r for r in known if r.get("px_tradeable")]
    n_untradeable = sum(1 for r in known if not r.get("px_tradeable"))
    ev_records = []
    for r in tradeable:
        payout_c = 100.0 if r["yes_settlement"] == 1.0 else 0.0
        fill_c = r["px_fill_price_c"]
        net_c = payout_c - fill_c - SLIPPAGE_C - FEE_C
        ev_records.append({**r, "payout_c": payout_c, "net_ev_c": net_c,
                            "cluster_station_day": f"{r['station']}|{r['local_date']}",
                            "cluster_calendar_day": r["local_date"]})
    out["n_untradeable"] = n_untradeable
    out["untradeable_pct"] = round(100 * n_untradeable / n_locks, 3) if n_locks else None

    n_priced = len(ev_records)
    n_station_day_clusters = len({r["cluster_station_day"] for r in ev_records})
    n_stations_priced = len({r["station"] for r in ev_records})
    stats_stationday = clustered_mean_tstat([r["net_ev_c"] for r in ev_records],
                                             [r["cluster_station_day"] for r in ev_records]) if ev_records else None
    stats_calday = clustered_mean_tstat([r["net_ev_c"] for r in ev_records],
                                         [r["cluster_calendar_day"] for r in ev_records]) if ev_records else None
    out["ev"] = {
        "n_priced": n_priced, "n_station_day_clusters": n_station_day_clusters,
        "n_stations": n_stations_priced,
        "stationday_clustered": stats_stationday, "calendarday_clustered_sensitivity": stats_calday,
    }
    print(f"\n  EV: n_priced={n_priced}  station-day clusters={n_station_day_clusters}  stations={n_stations_priced}")
    if stats_stationday:
        print(f"  mean net EV = {stats_stationday['mean']:.4f}c/ct  se={stats_stationday['se']:.4f}  "
              f"t={stats_stationday['t']:.3f}  (C={stats_stationday['n_clusters']} station-day clusters)")

    # ---- VERDICT against the spec's own frozen bars ----
    min_n_falselock_ok = n_locks >= 150
    min_n_ev_ok = (n_priced >= 100 and n_station_day_clusters >= 50 and n_stations_priced >= 2)
    if not (min_n_falselock_ok and min_n_ev_ok):
        out["verdict"] = "THIN"
        out["thin_reason"] = (f"min_n not reached: n_locks={n_locks} (need>=150), n_priced={n_priced} "
                               f"(need>=100), n_station_day_clusters={n_station_day_clusters} (need>=50), "
                               f"n_stations_priced={n_stations_priced} (need>=2)")
        write_out(out)
        print("\nTHIN:", out["thin_reason"])
        return out

    if n_false > 4:
        out["verdict"] = "KILL"
        out["kill_reason"] = f">4 false locks ({n_false}) -- basis to WU settlement unsound, stop pricing"
        write_out(out)
        print("\nKILL:", out["kill_reason"])
        return out

    # kill condition: "fills within 60 min post-lock exist on <30% of lock station-days"
    sd_has_lock = {}
    sd_has_tradeable = {}
    for r in known:
        sd = f"{r['station']}|{r['local_date']}"
        sd_has_lock[sd] = True
        if r.get("px_tradeable"):
            sd_has_tradeable[sd] = True
    n_sd_locks = len(sd_has_lock)
    n_sd_tradeable = len(sd_has_tradeable)
    frac_sd_tradeable = (n_sd_tradeable / n_sd_locks) if n_sd_locks else 0.0
    out["tradeable_station_day_frac"] = round(frac_sd_tradeable, 4)
    print(f"  station-days with >=1 tradeable (within-60min) fire: {n_sd_tradeable}/{n_sd_locks} "
          f"({100*frac_sd_tradeable:.1f}%)")
    if frac_sd_tradeable < 0.30:
        out["verdict"] = "KILL"
        out["kill_reason"] = (f"fills within 60min post-lock exist on only {100*frac_sd_tradeable:.1f}% of "
                               f"lock station-days (<30%)")
        write_out(out)
        print("\nKILL:", out["kill_reason"])
        return out

    bar_i = (n_false <= 1) and (fl_ub is not None) and (fl_ub <= FALSELOCK_UB_BAR)
    t = stats_stationday["t"] if stats_stationday and stats_stationday["t"] is not None else -math.inf
    mean_ev = stats_stationday["mean"] if stats_stationday else -math.inf
    bar_ii = (t >= EV_T_BAR) and (mean_ev >= EV_MEAN_BAR_C)
    go = bar_i and bar_ii

    ev_ub = None
    if stats_stationday and stats_stationday["se"] is not None:
        ev_ub = stats_stationday["mean"] + WILSON_Z_FALSELOCK * stats_stationday["se"]  # one-sided 98.33% UB, same z
    kill_ev = (ev_ub is not None) and (ev_ub < EV_KILL_UB_C)

    if go:
        out["verdict"] = "GO"
    elif kill_ev:
        out["verdict"] = "KILL"
        out["kill_reason"] = f"one-sided 98.33% UB of mean net EV = {ev_ub:.4f}c < {EV_KILL_UB_C}c"
    else:
        out["verdict"] = "FAIL"
        out["fail_reason"] = f"bar_i(false-lock)={bar_i}  bar_ii(EV)={bar_ii}"
    out["bar_i_falselock_pass"] = bar_i
    out["bar_ii_ev_pass"] = bar_ii
    out["ev_one_sided_98_33_ub_c"] = ev_ub

    write_out(out)
    print("\n" + "=" * 100)
    print(f"VERDICT: {out['verdict']}")
    print("=" * 100)
    return out


def write_out(out):
    out_dir = os.path.join(HERE, "out")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "spec_S3_B.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
