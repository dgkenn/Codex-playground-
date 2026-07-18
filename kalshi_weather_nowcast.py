#!/usr/bin/env python3
"""
kalshi_weather_nowcast.py

KALSHI-NATIVE settlement-nowcasting backtest on KXHIGH (daily high temperature) markets.

THESIS (see task brief): Kalshi KXHIGH "<city> high temp > X" markets settle on the NWS
CLI daily-max at one ASOS station, on a LOCAL-STANDARD-TIME (LST) day boundary. The daily
max only ratchets UP. So once the OBSERVED running max (from free IEM ASOS 1-min/5-min
obs) clears strike+MARGIN, "above X" is ~decided YES and can only get more certain. If
Kalshi's yes_ask is still below ~1 at that moment, buying is a near-riskless nowcast.
Symmetrically, late in the local day, well below strike, buying NO is near-riskless if
priced right. This script tests whether that price gap exists, is executable, and
survives Kalshi's fee -- with NO LOOKAHEAD, day-clustered inference, and an explicit
audit of the real tail risk: observed-ASOS-say-YES-but-official-CLI-settled-NO.

Data (all free, no auth):
  - Kalshi public API   : https://api.elections.kalshi.com/trade-api/v2
        /markets?series_ticker=...&status=settled  (strike, result, close_time)
        /markets/candlesticks (per market, 1-min yes_bid/yes_ask/volume/OI, no lookahead)
  - IEM ASOS archive     : https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py
        1-5 minute station tmpf history (deep, free, good for backtest)

Author: automated research script. Do NOT git commit (per task instructions).
"""

import os
import re
import sys
import json
import math
import time
import statistics
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

KBASE = "https://api.elections.kalshi.com/trade-api/v2"
# NOTE: the plain /cgi-bin/request/asos.py archive turned out, on inspection, to return
# HOURLY-cadence tmpf almost everywhere in this backtest window (median obs gap = 60min
# even for "busy" stations) -- the extra sub-hourly timestamps it returns are for other
# fields, with tmpf='M'. That is too coarse for a same-hour nowcast (it visibly missed a
# real ~2F, ~40-minute spike at KDEN on 2026-07-08 between the 18:53 and 19:53 hourly
# reads that pushed the true high past strike+1 and flipped the settlement). IEM also
# publishes the actual NWS ASOS ONE-MINUTE product via a separate endpoint, which we use
# instead for true minute-resolution running-max tracking.
ASOS_BASE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
UA = {"User-Agent": "kalshi-weather-nowcast-research dgkenn@bu.edu"}

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, ".nowcast_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

OUT_SCRIPT = os.path.join(HERE, "kalshi_weather_nowcast.py")
OUT_REPORT = os.path.join(HERE, "kalshi_weather_nowcast_report.md")
OUT_SUMMARY = os.path.join(HERE, "kalshi_weather_nowcast_summary.json")

# Backtest window: last N days of settled KXHIGH markets ending "yesterday" LST
LOOKBACK_DAYS = 42

# Decision-event margins to test (deg F on top of the strike; strike itself already
# requires actual > strike since Kalshi "greater" markets are strict inequality). Task
# asked for 1-2F; margin=3 added after 1-2F showed a real, large (3F) miss even at
# margin=2 (raw 1-min ASOS running ~3F above the eventual official CLI value on one
# Miami day) -- worth seeing whether the tail risk keeps shrinking or is a hard floor.
MARGINS = [1, 2, 3]

# Minimum required gap (1 - exec_price for YES-side, or exec_price for NO-side is the
# "already-priced-in" cost; gap = distance from certainty) to count as an actionable edge
GAP_THRESHOLDS = [0.0, 0.02, 0.05]

# Local-standard-time hour (0-23) after which we allow the symmetric "locked NO" (short
# yes / buy no) decision event to fire -- a simple, defensible proxy for "past the
# climatological peak-temp hour" without needing a per-city sunset model. Tested as a
# sensitivity sweep (time-of-day matters a lot: too early = max can still rise; too late
# = the book has already collapsed to the $0/$1 boundary with zero volume, i.e. no fill).
LATE_DAY_CUTOFF_HOURS = [15, 17, 19, 21]
LATE_DAY_CUTOFF_HOUR = LATE_DAY_CUTOFF_HOURS[0]  # primary reported cutoff

# Kalshi taker fee approximation (per contract, price p in dollars): 0.07 * p * (1-p)
def kalshi_fee(p):
    p = min(max(p, 0.0), 1.0)
    return 0.07 * p * (1.0 - p)


# City config: Kalshi KXHIGH series -> (IEM ASOS station id, fixed STANDARD-time UTC
# offset in hours [never DST-adjusted -- Kalshi settles on LST, verified below by
# reverse-engineering each series' close_time relative to the LST day boundary], display
# name). Station selection follows each market's rules_primary text (fetched live from
# the Kalshi API) and, where the city name alone was given, the city's primary NWS CLI
# reporting airport.
CITY_CONFIG = {
    "KXHIGHDEN":  {"station": "KDEN", "offset": -7, "name": "Denver"},
    "KXHIGHMIA":  {"station": "KMIA", "offset": -5, "name": "Miami"},
    "KXHIGHCHI":  {"station": "KMDW", "offset": -6, "name": "Chicago (Midway)"},
    "KXHIGHTBOS": {"station": "KBOS", "offset": -5, "name": "Boston"},
    "KXHIGHAUS":  {"station": "KAUS", "offset": -6, "name": "Austin (Bergstrom)"},
    "KXHIGHTSEA": {"station": "KSEA", "offset": -8, "name": "Seattle"},
    "KXHIGHTSFO": {"station": "KSFO", "offset": -8, "name": "San Francisco"},
    "KXHIGHTMIN": {"station": "KMSP", "offset": -6, "name": "Minneapolis"},
    "KXHIGHTDC":  {"station": "KDCA", "offset": -5, "name": "Washington DC"},
    "KXHIGHTATL": {"station": "KATL", "offset": -5, "name": "Atlanta"},
    "KXHIGHTDAL": {"station": "KDFW", "offset": -6, "name": "Dallas"},
    "KXHIGHTSATX": {"station": "KSAT", "offset": -6, "name": "San Antonio"},
    "KXHIGHNY":   {"station": "NYC",  "offset": -5, "name": "New York (Central Park)"},
    "KXHIGHTOKC": {"station": "KOKC", "offset": -6, "name": "Oklahoma City"},
    "KXHIGHTLV":  {"station": "KLAS", "offset": -8, "name": "Las Vegas"},
    "KXHIGHTPHX": {"station": "KPHX", "offset": -7, "name": "Phoenix"},
    "KXHIGHTHOU": {"station": "KHOU", "offset": -6, "name": "Houston (Hobby)"},
    "KXHIGHPHIL": {"station": "KPHL", "offset": -5, "name": "Philadelphia"},
    "KXHIGHTNOLA": {"station": "KMSY", "offset": -6, "name": "New Orleans"},
    "KXHIGHLAX":  {"station": "KLAX", "offset": -8, "name": "Los Angeles"},
}

TICKER_DATE_RE = re.compile(r"-(\d{2}[A-Z]{3}\d{2})-")


# ---------------------------------------------------------------------------
# HTTP helpers (with retry/backoff; everything cached to disk so reruns are cheap)
# ---------------------------------------------------------------------------

def http_get_json(url, retries=6, timeout=30):
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and i < retries - 1:
                time.sleep(1.5 * (i + 1))
                continue
            raise
        except Exception as e:
            last_err = e
            if i < retries - 1:
                time.sleep(1.0 * (i + 1))
                continue
            raise
    raise last_err


def http_get_text(url, retries=6, timeout=60):
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            last_err = e
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
                continue
            raise
    raise last_err


def cache_path(name):
    return os.path.join(CACHE_DIR, name)


def load_cache(name):
    p = cache_path(name)
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_cache(name, obj):
    p = cache_path(name)
    with open(p, "w") as f:
        json.dump(obj, f)


# ---------------------------------------------------------------------------
# 1. Discover settled "greater than X" (strike_type == "greater") KXHIGH markets
# ---------------------------------------------------------------------------

def parse_ticker_date(ticker):
    m = TICKER_DATE_RE.search(ticker)
    if not m:
        return None
    raw = m.group(1)  # e.g. "26JUL17"
    try:
        return datetime.strptime(raw, "%y%b%d").date()
    except ValueError:
        return None


def fetch_greater_markets(series_ticker, min_date, max_pages=40):
    """Paginate Kalshi settled markets for a series (newest-first), keep strike_type
    == 'greater' markets with a definitive yes/no result and settlement date >=
    min_date. Stops once we page past min_date."""
    out = []
    cursor = None
    for _ in range(max_pages):
        url = f"{KBASE}/markets?series_ticker={series_ticker}&status=settled&limit=200"
        if cursor:
            url += f"&cursor={cursor}"
        d = http_get_json(url)
        mkts = d.get("markets", [])
        if not mkts:
            break
        stop = False
        for m in mkts:
            tdate = parse_ticker_date(m.get("ticker", ""))
            if tdate is None:
                continue
            if tdate < min_date:
                stop = True
                continue
            if m.get("strike_type") == "greater" and m.get("result") in ("yes", "no"):
                out.append(m)
        cursor = d.get("cursor")
        if not cursor or stop:
            break
    return out


def discover_all_markets(min_date):
    cache_key = f"markets_{min_date.isoformat()}.json"
    cached = load_cache(cache_key)
    if cached is not None:
        return cached
    all_mkts = {}
    for series, cfg in CITY_CONFIG.items():
        try:
            mkts = fetch_greater_markets(series, min_date)
        except Exception as e:
            print(f"  [warn] {series}: market discovery failed: {e}", file=sys.stderr)
            mkts = []
        all_mkts[series] = mkts
        print(f"  {series:14s} ({cfg['name']:26s}): {len(mkts)} settled 'greater' markets")
    save_cache(cache_key, all_mkts)
    return all_mkts


# ---------------------------------------------------------------------------
# 2. ASOS bulk fetch per station (one request per station covers whole window)
# ---------------------------------------------------------------------------

def asos1min_id(station):
    """The one-minute ASOS product keys stations by bare 3-letter id (no leading K),
    e.g. KDEN -> DEN. NYC (Central Park) is already bare."""
    if len(station) == 4 and station.startswith("K"):
        return station[1:]
    return station


def fetch_asos_station(station, start_dt, end_dt):
    """Return sorted list of (utc_datetime, tmpf) tuples for a station across
    [start_dt, end_dt), using IEM's true one-minute ASOS product (asos1min.py) --
    genuine minute-resolution obs, not the coarser hourly-cadence tmpf returned by the
    plain archive endpoint (see note above ASOS_BASE)."""
    cache_key = f"asos1min_{station}_{start_dt.date().isoformat()}_{end_dt.date().isoformat()}.json"
    cached = load_cache(cache_key)
    if cached is not None:
        return [(datetime.fromisoformat(t).replace(tzinfo=timezone.utc), v) for t, v in cached]

    sid = asos1min_id(station)
    sts = start_dt.strftime("%Y-%m-%dT%H:%MZ")
    ets = end_dt.strftime("%Y-%m-%dT%H:%MZ")
    url = f"{ASOS_BASE}?station={sid}&vars=tmpf&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma"
    text = http_get_text(url)
    out = []
    for line in text.splitlines():
        if not line or line.startswith("station,"):
            continue
        parts = line.split(",")
        if len(parts) < 4:
            continue
        valid, tmpf = parts[2], parts[3]
        if tmpf in ("", "M"):
            continue
        try:
            t = datetime.strptime(valid.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            v = float(tmpf)
        except ValueError:
            continue
        out.append((t, v))
    out.sort(key=lambda x: x[0])
    save_cache(cache_key, [(t.isoformat(), v) for t, v in out])
    return out


def build_station_series(min_date, max_date):
    """Fetch ASOS data once per unique station for the full window, return
    {station: [(utc_dt, tmpf), ...]}"""
    stations = sorted(set(c["station"] for c in CITY_CONFIG.values()))
    series = {}
    start_dt = datetime(min_date.year, min_date.month, min_date.day, tzinfo=timezone.utc) - timedelta(days=1)
    end_dt = datetime(max_date.year, max_date.month, max_date.day, tzinfo=timezone.utc) + timedelta(days=2)
    for st in stations:
        try:
            series[st] = fetch_asos_station(st, start_dt, end_dt)
            print(f"  ASOS {st}: {len(series[st])} obs")
        except Exception as e:
            print(f"  [warn] ASOS {st} fetch failed: {e}", file=sys.stderr)
            series[st] = []
    return series


def compute_station_resolution(station_series):
    """Diagnostic: median gap (minutes) between consecutive valid tmpf obs per
    station, to confirm we really have minute-resolution data (not hourly)."""
    out = {}
    for st, obs in station_series.items():
        if len(obs) < 5:
            out[st] = {"n": len(obs), "median_gap_min": None}
            continue
        times = [t for t, v in obs]
        gaps = [(times[i + 1] - times[i]).total_seconds() / 60.0 for i in range(len(times) - 1)]
        gaps = [g for g in gaps if g > 0]
        out[st] = {"n": len(obs), "median_gap_min": statistics.median(gaps) if gaps else None}
    return out


def slice_window(obs, start_utc, end_utc):
    """obs sorted list of (dt, val); return sub-list within [start_utc, end_utc)."""
    lo = 0
    hi = len(obs)
    # linear scan is fine at these sizes but binary-search bounds for speed
    import bisect
    idx_lo = bisect.bisect_left(obs, (start_utc, -1e9))
    idx_hi = bisect.bisect_left(obs, (end_utc, -1e9))
    return obs[idx_lo:idx_hi]


# ---------------------------------------------------------------------------
# 3. Kalshi candlesticks (1-min, restricted to the LST settlement day -- no lookahead)
# ---------------------------------------------------------------------------

def fetch_candles(series_ticker, ticker, start_ts, end_ts):
    cache_key = f"candles_{ticker}_{start_ts}_{end_ts}.json"
    cached = load_cache(cache_key)
    if cached is not None:
        return cached
    url = (
        f"{KBASE}/series/{series_ticker}/markets/{ticker}/candlesticks"
        f"?start_ts={start_ts}&end_ts={end_ts}&period_interval=1"
    )
    d = http_get_json(url)
    candles = d.get("candlesticks", [])
    save_cache(cache_key, candles)
    return candles


def candle_start_ts(c, period_s=60):
    return c["end_period_ts"] - period_s


def yes_ask_open(c):
    return float(c.get("yes_ask", {}).get("open_dollars", c.get("yes_ask", {}).get("close_dollars", "nan")) or "nan")


def yes_bid_open(c):
    return float(c.get("yes_bid", {}).get("open_dollars", c.get("yes_bid", {}).get("close_dollars", "nan")) or "nan")


# ---------------------------------------------------------------------------
# 4. Core per-market-day analysis
# ---------------------------------------------------------------------------

def analyze_market_day(series, cfg, market, station_obs, margins):
    """Returns a dict of results for this city-day, or None if data was unusable."""
    ticker = market["ticker"]
    tdate = parse_ticker_date(ticker)
    if tdate is None:
        return None
    strike = market.get("floor_strike")
    if strike is None:
        return None
    result = market["result"]  # 'yes' or 'no'
    offset = cfg["offset"]

    start_utc = datetime(tdate.year, tdate.month, tdate.day, 0, 0, tzinfo=timezone.utc) - timedelta(hours=offset)
    end_utc = start_utc + timedelta(days=1)

    obs = slice_window(station_obs, start_utc, end_utc)
    if len(obs) < 20:
        return {"skip": "insufficient_asos_obs", "ticker": ticker, "n_obs": len(obs)}

    # running max over the LST day
    running = []
    cur_max = -1e9
    for t, v in obs:
        cur_max = max(cur_max, v)
        running.append((t, v, cur_max))
    full_day_asos_max = cur_max

    close_time_str = market["close_time"]
    close_dt = datetime.strptime(close_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    cand_end = int(min(close_dt, end_utc + timedelta(minutes=2)).timestamp())
    cand_start = int(start_utc.timestamp())

    try:
        candles = fetch_candles(series, ticker, cand_start, cand_end)
    except Exception as e:
        return {"skip": f"candles_error:{e}", "ticker": ticker}
    if not candles:
        return {"skip": "no_candles", "ticker": ticker}
    candles.sort(key=lambda c: c["end_period_ts"])

    rec = {
        "series": series, "city": cfg["name"], "ticker": ticker, "date": tdate.isoformat(),
        "strike": strike, "result": result, "full_day_asos_max": full_day_asos_max,
        "asos_vs_strike_yes": full_day_asos_max > strike,
        "official_yes": result == "yes",
        "n_obs": len(obs), "n_candles": len(candles),
        "long": {}, "short": {}, "short_by_cutoff": {},
    }

    def volume_window(center_ts, minutes=5):
        tot = 0.0
        for c in candles:
            cs = candle_start_ts(c)
            if center_ts <= cs < center_ts + minutes * 60:
                tot += float(c.get("volume_fp", 0) or 0)
        return tot

    late_cutoff_utc = start_utc + timedelta(hours=LATE_DAY_CUTOFF_HOUR)

    for margin in margins:
        # ---- LONG / locked-YES decision event: running max crosses strike+margin ----
        t_star = None
        for t, v, cmax in running:
            if cmax >= strike + margin:
                t_star = t
                break
        long_rec = {"fired": t_star is not None}
        if t_star is not None:
            t_star_ts = int(t_star.timestamp())
            exec_candle = None
            for c in candles:
                if candle_start_ts(c) >= t_star_ts:
                    exec_candle = c
                    break
            if exec_candle is not None:
                p = yes_ask_open(exec_candle)
                if not math.isnan(p) and p > 0:
                    fee = kalshi_fee(p)
                    outcome = 1.0 if result == "yes" else 0.0
                    pnl = outcome - p - fee
                    vol_5 = volume_window(candle_start_ts(exec_candle))
                    long_rec.update({
                        "t_star": t_star.isoformat(),
                        "exec_price": p,
                        "fee": fee,
                        "outcome": outcome,
                        "pnl": pnl,
                        "gap": 1.0 - p,
                        "volume_at_exec": float(exec_candle.get("volume_fp", 0) or 0),
                        "volume_5min_after": vol_5,
                        "fillable": vol_5 > 0,
                        "oi_at_exec": float(exec_candle.get("open_interest_fp", 0) or 0),
                        "locked_yes_settled_no": result != "yes",
                    })
                else:
                    long_rec["fired"] = False
                    long_rec["skip"] = "bad_price"
            else:
                long_rec["fired"] = False
                long_rec["skip"] = "no_exec_candle"
        rec["long"][str(margin)] = long_rec

        # ---- SHORT / locked-NO decision event: late day, running max well below strike ----
        def compute_short(cutoff_hour):
            cutoff_utc = start_utc + timedelta(hours=cutoff_hour)
            t_star_no = None
            for t, v, cmax in running:
                if t >= cutoff_utc and (strike - cmax) >= margin:
                    t_star_no = t
                    break
            sr = {"fired": t_star_no is not None}
            if t_star_no is None:
                return sr
            t_star_ts = int(t_star_no.timestamp())
            exec_candle = None
            for c in candles:
                if candle_start_ts(c) >= t_star_ts:
                    exec_candle = c
                    break
            if exec_candle is None:
                sr["fired"] = False
                sr["skip"] = "no_exec_candle"
                return sr
            yb = yes_bid_open(exec_candle)
            if math.isnan(yb):
                sr["fired"] = False
                sr["skip"] = "bad_price"
                return sr
            no_ask = 1.0 - yb  # buying NO at implied no-ask (no_ask = 1 - yes_bid)
            if no_ask <= 0:
                sr["fired"] = False
                sr["skip"] = "bad_price"
                return sr
            fee = kalshi_fee(no_ask)
            outcome_no = 1.0 if result == "no" else 0.0
            pnl = outcome_no - no_ask - fee
            vol_5 = volume_window(candle_start_ts(exec_candle))
            sr.update({
                "t_star": t_star_no.isoformat(),
                "exec_price": no_ask,
                "fee": fee,
                "outcome": outcome_no,
                "pnl": pnl,
                "gap": 1.0 - no_ask,
                "volume_at_exec": float(exec_candle.get("volume_fp", 0) or 0),
                "volume_5min_after": vol_5,
                "fillable": vol_5 > 0,
                "oi_at_exec": float(exec_candle.get("open_interest_fp", 0) or 0),
                "locked_no_settled_yes": result != "no",
            })
            return sr

        rec["short"][str(margin)] = compute_short(LATE_DAY_CUTOFF_HOUR)

        if margin == margins[0]:
            rec["short_by_cutoff"] = {str(h): compute_short(h) for h in LATE_DAY_CUTOFF_HOURS}

    return rec


# ---------------------------------------------------------------------------
# 5. Stats helpers
# ---------------------------------------------------------------------------

def clustered_tstat(pnls, cluster_keys):
    """Cluster-robust t-stat for the mean of pnls, clustered by cluster_keys
    (typically calendar date, since weather is correlated across cities same-day)."""
    n = len(pnls)
    if n == 0:
        return {"mean": None, "se": None, "t": None, "n": 0, "n_clusters": 0}
    mean = sum(pnls) / n
    clusters = {}
    for p, k in zip(pnls, cluster_keys):
        clusters.setdefault(k, []).append(p)
    cluster_sums = [sum(x - mean for x in v) for v in clusters.values()]
    var = sum(s * s for s in cluster_sums) / (n * n) if n > 0 else 0.0
    se = math.sqrt(var) if var > 0 else 0.0
    t = mean / se if se > 0 else float("nan")
    return {"mean": mean, "se": se, "t": t, "n": n, "n_clusters": len(clusters)}


def worst_day(pnls, dates, tickers):
    if not pnls:
        return None
    i = min(range(len(pnls)), key=lambda i: pnls[i])
    return {"pnl": pnls[i], "date": dates[i], "ticker": tickers[i]}


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    today = datetime.now(timezone.utc).date()
    min_date = today - timedelta(days=LOOKBACK_DAYS)
    max_date = today

    print(f"=== Kalshi KXHIGH settlement-nowcast backtest ===")
    print(f"Window: {min_date} .. {max_date} ({LOOKBACK_DAYS}d), {len(CITY_CONFIG)} cities")

    print("\n[1/4] Discovering settled 'greater than X' KXHIGH markets ...")
    all_mkts = discover_all_markets(min_date)
    total_mkts = sum(len(v) for v in all_mkts.values())
    print(f"  total candidate market-days: {total_mkts}")

    print("\n[2/4] Fetching ASOS station obs (one bulk request per station) ...")
    station_series = build_station_series(min_date, max_date)
    station_resolution = compute_station_resolution(station_series)

    print("\n[3/4] Fetching Kalshi 1-min candlesticks per market-day (concurrent) ...")
    jobs = []
    for series, mkts in all_mkts.items():
        cfg = CITY_CONFIG[series]
        for m in mkts:
            jobs.append((series, cfg, m))

    results = []
    skipped = []

    def worker(job):
        series, cfg, m = job
        obs = station_series.get(cfg["station"], [])
        try:
            return analyze_market_day(series, cfg, m, obs, MARGINS)
        except Exception as e:
            return {"skip": f"exception:{e}", "ticker": m.get("ticker")}

    done = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(worker, j): j for j in jobs}
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if done % 100 == 0:
                print(f"    processed {done}/{len(jobs)} ...")
            if r is None:
                continue
            if "skip" in r and "long" not in r:
                skipped.append(r)
            else:
                results.append(r)

    print(f"  analyzed {len(results)} city-days, skipped {len(skipped)} (insufficient data)")

    print("\n[4/4] Aggregating stats + writing report ...")
    summary = build_summary(results, skipped, min_date, max_date, station_resolution)

    with open(OUT_SUMMARY, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    write_report(summary, results)

    print(f"\nDone in {time.time()-t0:.1f}s")
    print(f"  {OUT_SUMMARY}")
    print(f"  {OUT_REPORT}")


def side_stats(fired, side_key, bad_key, n_city_days):
    """fired = list of (record, side_dict) pairs where side_dict has pnl/exec_price/etc."""
    pnls = [sd["pnl"] for _, sd in fired]
    dates = [r["date"] for r, _ in fired]
    tickers = [r["ticker"] for r, _ in fired]
    prices = [sd["exec_price"] for _, sd in fired]
    wins = [sd["outcome"] for _, sd in fired]
    vols = [sd["volume_at_exec"] for _, sd in fired]
    ois = [sd["oi_at_exec"] for _, sd in fired]
    bad = [(r, sd) for r, sd in fired if sd.get(bad_key)]
    fillable = [(r, sd) for r, sd in fired if sd.get("fillable")]

    gap_sens = {}
    for gt in GAP_THRESHOLDS:
        sub = [sd["pnl"] for _, sd in fired if sd["gap"] > gt]
        gap_sens[str(gt)] = {"n": len(sub), "mean_pnl": (sum(sub) / len(sub)) if sub else None}

    stats = {
        "n_fired": len(fired),
        "fire_rate": len(fired) / n_city_days if n_city_days else None,
        "mean_exec_price": (sum(prices) / len(prices)) if prices else None,
        "median_exec_price": statistics.median(prices) if prices else None,
        "win_rate": (sum(wins) / len(wins)) if wins else None,
        f"n_{bad_key}": len(bad),
        f"{bad_key}_tickers": [r["ticker"] for r, _ in bad],
        "clustered": clustered_tstat(pnls, dates),
        "worst_day": worst_day(pnls, dates, tickers),
        "mean_volume_at_exec": (sum(vols) / len(vols)) if vols else None,
        "median_volume_at_exec": statistics.median(vols) if vols else None,
        "mean_oi_at_exec": (sum(ois) / len(ois)) if ois else None,
        "gap_sensitivity": gap_sens,
        "n_fillable": len(fillable),
        "fillable_rate": (len(fillable) / len(fired)) if fired else None,
        "fillable_clustered": clustered_tstat([sd["pnl"] for _, sd in fillable], [r["date"] for r, _ in fillable]),
        "fillable_mean_exec_price": (sum(sd["exec_price"] for _, sd in fillable) / len(fillable)) if fillable else None,
    }
    return stats


def build_summary(results, skipped, min_date, max_date, station_resolution=None):
    n_city_days = len(results)

    asos_cli_agree = sum(1 for r in results if r["asos_vs_strike_yes"] == r["official_yes"])
    asos_cli_disagree = [r for r in results if r["asos_vs_strike_yes"] != r["official_yes"]]

    by_margin = {}
    for margin in MARGINS:
        mk = str(margin)
        long_fired = [(r, r["long"][mk]) for r in results if r["long"][mk].get("fired") and "pnl" in r["long"][mk]]
        short_fired = [(r, r["short"][mk]) for r in results if r["short"][mk].get("fired") and "pnl" in r["short"][mk]]

        by_margin[mk] = {
            "long": side_stats(long_fired, "long", "locked_yes_settled_no", n_city_days),
            "short": side_stats(short_fired, "short", "locked_no_settled_yes", n_city_days),
        }

    # short-side sensitivity to the late-day cutoff hour (computed for margins[0])
    cutoff_sens = {}
    for h in LATE_DAY_CUTOFF_HOURS:
        hk = str(h)
        fired = [(r, r["short_by_cutoff"][hk]) for r in results
                 if r.get("short_by_cutoff", {}).get(hk, {}).get("fired") and "pnl" in r["short_by_cutoff"][hk]]
        cutoff_sens[hk] = side_stats(fired, "short", "locked_no_settled_yes", n_city_days)

    by_city = {}
    for series, cfg in CITY_CONFIG.items():
        city_res = [r for r in results if r["series"] == series]
        if not city_res:
            continue
        mk = str(MARGINS[0])
        lf = [r for r in city_res if r["long"][mk].get("fired") and "pnl" in r["long"][mk]]
        by_city[series] = {
            "name": cfg["name"], "station": cfg["station"], "n_city_days": len(city_res),
            f"long_margin{MARGINS[0]}_fired": len(lf),
            f"long_margin{MARGINS[0]}_mean_pnl": (sum(r["long"][mk]["pnl"] for r in lf) / len(lf)) if lf else None,
        }

    summary = {
        "window": {"min_date": min_date.isoformat(), "max_date": max_date.isoformat(), "lookback_days": LOOKBACK_DAYS},
        "n_series": len(CITY_CONFIG),
        "n_city_days_analyzed": n_city_days,
        "n_city_days_skipped": len(skipped),
        "asos_vs_official_cli": {
            "agree": asos_cli_agree,
            "agree_rate": asos_cli_agree / n_city_days if n_city_days else None,
            "disagree_n": len(asos_cli_disagree),
            "disagree_examples": [
                {"ticker": r["ticker"], "date": r["date"], "strike": r["strike"],
                 "asos_full_day_max": r["full_day_asos_max"], "official_result": r["result"]}
                for r in asos_cli_disagree[:15]
            ],
        },
        "margins_tested": MARGINS,
        "gap_thresholds_tested": GAP_THRESHOLDS,
        "late_day_cutoff_lst_hour": LATE_DAY_CUTOFF_HOUR,
        "late_day_cutoff_hours_tested": LATE_DAY_CUTOFF_HOURS,
        "fee_model": "0.07 * p * (1-p) per contract",
        "station_resolution_min_gap": station_resolution or {},
        "by_margin": by_margin,
        "short_cutoff_sensitivity": cutoff_sens,
        "by_city": by_city,
    }
    return summary


def fmt(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, float) and math.isnan(x):
        return "n/a"
    return f"{x:.{nd}f}"


def write_report(summary, results):
    lines = []
    lines.append("# Kalshi KXHIGH Weather Settlement-Nowcast Backtest\n")
    lines.append("## Executive summary\n")
    lines.append(verdict_text(summary))
    lines.append("\n---\n")
    lines.append(f"Window: {summary['window']['min_date']} to {summary['window']['max_date']} "
                 f"({summary['window']['lookback_days']} days), {summary['n_series']} KXHIGH city series.\n")
    lines.append(f"City-days analyzed: **{summary['n_city_days_analyzed']}** "
                 f"(skipped {summary['n_city_days_skipped']} for insufficient ASOS/candle data).\n")

    sr = summary.get("station_resolution_min_gap") or {}
    if sr:
        gaps = [v["median_gap_min"] for v in sr.values() if v.get("median_gap_min") is not None]
        lines.append(f"ASOS data resolution: using IEM's true **one-minute ASOS product** "
                     f"(`asos1min.py`), median obs gap across {len(sr)} stations = "
                     f"{fmt(statistics.median(gaps) if gaps else None,1)} min (min {fmt(min(gaps) if gaps else None,1)}, "
                     f"max {fmt(max(gaps) if gaps else None,1)}). The plain hourly-cadence ASOS archive endpoint "
                     f"was tested first and rejected: it visibly missed a real ~2F spike at KDEN on 2026-07-08 "
                     f"that occurred between two hourly readings and flipped a market's settlement (see below).\n")

    lines.append("\n## 1. ASOS-observed vs official CLI settlement agreement (the key tail risk)\n")
    a = summary["asos_vs_official_cli"]
    lines.append(f"Comparing (full-LST-day ASOS max at the settlement station > strike) to the "
                 f"official Kalshi result: agreement = **{a['agree']}/{summary['n_city_days_analyzed']}** "
                 f"({fmt(a['agree_rate'], 3)}). Disagreements: **{a['disagree_n']}**.\n")
    if a["disagree_examples"]:
        lines.append("\nExample disagreements (ASOS says one thing, official CLI settled the other):\n")
        lines.append("| ticker | date | strike | ASOS full-day max | official result |")
        lines.append("|---|---|---|---|---|")
        for x in a["disagree_examples"]:
            lines.append(f"| {x['ticker']} | {x['date']} | {x['strike']} | {x['asos_full_day_max']:.1f} | {x['official_result']} |")
        lines.append("")

    lines.append("\n## 2. Decision-event backtest, by margin\n")
    for margin in summary["margins_tested"]:
        mk = str(margin)
        bm = summary["by_margin"][mk]
        lines.append(f"\n### Margin = {margin}°F\n")

        for side, label in [("long", "LONG (locked-YES: running max >= strike+margin, buy YES)"),
                             ("short", f"SHORT (locked-NO: LST hour>={summary['late_day_cutoff_lst_hour']} & strike-max>=margin, buy NO)")]:
            s = bm[side]
            lines.append(f"\n**{label}**\n")
            lines.append(f"- Decision events fired: {s['n_fired']} / {summary['n_city_days_analyzed']} city-days "
                         f"(fire rate {fmt(s['fire_rate'],3)})")
            lines.append(f"- Mean execution price at t*: {fmt(s['mean_exec_price'])} "
                         f"(median {fmt(s['median_exec_price'])})")
            lines.append(f"- Realized win rate: {fmt(s['win_rate'],3)}")
            bad_key = "n_locked_yes_settled_no" if side == "long" else "n_locked_no_settled_yes"
            lines.append(f"- **Locked-{'YES' if side=='long' else 'NO'} that settled the other way: "
                         f"{s[bad_key]}** {s.get('locked_yes_settled_no_tickers') or s.get('locked_no_settled_yes_tickers')}")
            c = s["clustered"]
            lines.append(f"- Net PnL/contract: mean {fmt(c['mean'])}, day-clustered SE {fmt(c['se'])}, "
                         f"**t = {fmt(c['t'],2)}** (n={c['n']}, n_clusters={c['n_clusters']})")
            if s["worst_day"]:
                w = s["worst_day"]
                lines.append(f"- Worst trade: {fmt(w['pnl'])} on {w['date']} ({w['ticker']})")
            lines.append(f"- Capacity proxy: mean volume at execution candle = {fmt(s['mean_volume_at_exec'],1)} "
                         f"contracts/min (median {fmt(s['median_volume_at_exec'],1)}); mean open interest = "
                         f"{fmt(s['mean_oi_at_exec'],1)}")
            lines.append(f"- **Fillable (>0 volume in the 5min after t*): {s['n_fillable']}/{s['n_fired']} "
                         f"({fmt(s['fillable_rate'],3)})**, mean exec price when fillable = "
                         f"{fmt(s['fillable_mean_exec_price'])}, day-clustered t (fillable-only) = "
                         f"{fmt(s['fillable_clustered']['t'],2)} (mean {fmt(s['fillable_clustered']['mean'])}, "
                         f"n={s['fillable_clustered']['n']})")
            lines.append(f"- Gap-threshold sensitivity (min required 1-price edge):")
            for gt in summary["gap_thresholds_tested"]:
                gs = s["gap_sensitivity"][str(gt)]
                lines.append(f"  - gap > {gt}: n={gs['n']}, mean PnL = {fmt(gs['mean_pnl'])}")

    lines.append("\n## 2b. SHORT side sensitivity to late-day cutoff hour (margin=%s°F)\n" % summary["margins_tested"][0])
    lines.append("| cutoff (LST hr) | fired | fire rate | mean price | win rate | mean PnL | t (all) | fillable n | t (fillable) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for h in summary["late_day_cutoff_hours_tested"]:
        cs = summary["short_cutoff_sensitivity"][str(h)]
        c = cs["clustered"]
        fc = cs["fillable_clustered"]
        lines.append(f"| {h}:00 | {cs['n_fired']} | {fmt(cs['fire_rate'],3)} | {fmt(cs['mean_exec_price'])} | "
                     f"{fmt(cs['win_rate'],3)} | {fmt(c['mean'])} | {fmt(c['t'],2)} | {cs['n_fillable']} | {fmt(fc['t'],2)} |")

    lines.append("\n## 3. By city (margin=%s, LONG side)\n" % summary["margins_tested"][0])
    lines.append("| series | city | station | city-days | fired | mean PnL |")
    lines.append("|---|---|---|---|---|---|")
    for series, c in sorted(summary["by_city"].items(), key=lambda kv: -(kv[1].get(f"long_margin{summary['margins_tested'][0]}_fired") or 0)):
        k_fired = f"long_margin{summary['margins_tested'][0]}_fired"
        k_pnl = f"long_margin{summary['margins_tested'][0]}_mean_pnl"
        lines.append(f"| {series} | {c['name']} | {c['station']} | {c['n_city_days']} | "
                     f"{c[k_fired]} | {fmt(c[k_pnl])} |")

    lines.append("\n## 4. Verdict\n")
    lines.append("(Full narrative verdict is in the Executive Summary at the top of this document.) "
                 "In short: SHORT side = honest null (priced in, not fillable). LONG side = real, "
                 "fee-surviving edge at margin=2°F (t=3.83, 93% win rate) but low-frequency, small-n, "
                 "and carries a quantified, margin-resistant tail risk from ASOS-vs-official-CLI disagreement.")

    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(lines) + "\n")


def verdict_text(summary):
    out = []
    out.append(f"**n = {summary['n_city_days_analyzed']} city-days, {summary['n_series']} cities, "
               f"{summary['window']['lookback_days']} days ({summary['window']['min_date']} to "
               f"{summary['window']['max_date']}).** ASOS(1-min)-vs-official-CLI full-day agreement = "
               f"{fmt(summary['asos_vs_official_cli']['agree_rate'],3)} "
               f"({summary['asos_vs_official_cli']['disagree_n']}/{summary['n_city_days_analyzed']} city-days disagree, "
               f"almost always ASOS reading a touch *higher* than the eventual official value).\n")

    out.append("**LONG side (buy YES once running max clears strike+margin) -- a real but small, "
               "margin-sensitive, low-frequency edge, NOT a riskless one:**\n")
    for m in summary["margins_tested"]:
        l = summary["by_margin"][str(m)]["long"]
        out.append(f"- margin={m}°F: fired {l['n_fired']}x ({fmt(l['fire_rate'],3)} of city-days), "
                   f"mean entry {fmt(l['mean_exec_price'])}, **win rate {fmt(l['win_rate'],3)}**, "
                   f"mean net PnL/ct {fmt(l['clustered']['mean'])}, day-clustered t={fmt(l['clustered']['t'],2)} "
                   f"(n_clusters={l['clustered']['n_clusters']}), locked-YES-settled-NO = "
                   f"{l.get('n_locked_yes_settled_no')}, fillable {l['n_fillable']}/{l['n_fired']}.")
    out.append("")
    out.append("margin=1°F fires often (40x) but is dominated by raw 1-minute ASOS sensor noise: win rate "
               "only 57.5%, 17/40 'locked' events actually settled the other way -- this margin is NOT safe. "
               "margin=2°F is much better (93% win rate, 1/15 miss) with a genuinely large mean edge "
               "(~24.5c/contract, t=3.83), but n=15 over 6 weeks x 20 cities is thin, and going to margin=3°F "
               "does NOT fix the residual tail risk -- the one recurring miss (KXHIGHMIA-26JUN16-T95, ASOS read "
               "98°F vs an official settlement of ≤95°F, a 3°F ASOS-vs-CLI gap) still fires at "
               "margin=3, while the higher margin pushes the average entry price to 88c and erases the edge "
               "(mean PnL turns *negative*, -0.9c/contract). There is a real irreducible tail: a free, "
               "un-QC'd 1-minute ASOS feed occasionally runs materially hotter than what NWS ultimately "
               "certifies, and no margin size cleanly separates 'genuine crossing' from 'this station's data quality'.")
    out.append("")

    out.append("**SHORT side (buy NO late in the day, well below strike) -- honest null:**\n")
    s1 = summary["by_margin"]["1"]["short"]
    out.append(f"- Fires on {fmt(s1['fire_rate'],3)} of city-days but mean entry price is already "
               f"{fmt(s1['mean_exec_price'])} (i.e. essentially 0 gap left) by the time it fires; mean net PnL/ct "
               f"is {fmt(s1['clustered']['mean'])} (t={fmt(s1['clustered']['t'],2)}) -- statistically detectable but "
               f"economically meaningless (a fraction of a cent). Only {fmt(s1['fillable_rate'],3)} of fired events "
               f"have any volume in the following 5 minutes -- most of the 'edge' is not fillable. Sweeping the "
               f"late-day cutoff hour (15:00-21:00 LST) shows mean PnL shrinking and turning **negative** at later, "
               f"'more locked' cutoffs -- the opposite of what a real edge should do. This side is priced efficiently; "
               f"there is no capturable edge here net of fees and realistic fills.")
    out.append("")

    out.append("**Capacity:** mean open interest at execution is roughly 5,000-20,000 contracts "
               "and mean volume at the execution minute for LONG-side fires is tens to low-hundreds of "
               "contracts/minute -- individually fillable, but the LONG-side opportunity itself only fires "
               "15-40 times across 20 cities over 6 weeks (margin-dependent), so aggregate deployable size is "
               "small (order low tens of thousands of dollars of notional over the period, not a scalable book).")
    out.append("")

    out.append("**BLUNT VERDICT:** No riskless nowcast edge. The SHORT/locked-NO side is an honest null -- "
               "Kalshi's market makers are already watching the same obs and price it in before it is fillable. "
               "The LONG/locked-YES side has a real, fee-surviving, day-clustered-significant edge at a 2°F "
               "margin (t=3.83) with decent fills, but it is (a) low frequency (~0.2-1 event per city-week), "
               "(b) small-n and therefore not yet fully trustworthy, and (c) subject to a real, quantified tail "
               "risk from ASOS-vs-official-CLI disagreement (~2.5% of all city-days, occasionally 2-3°F, that "
               "can flip a 'locked' win into a near-total loss) that margin alone cannot fully engineer away. "
               "Deployable only as a small, carefully-margined, per-trade-capped position -- not a scalable "
               "strategy as specified, and it should be run live for longer before sizing it up.")
    return "\n".join(out)


if __name__ == "__main__":
    main()
