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

=== DEEP-HISTORY RERUN (v2) ===
A first pass (42 calendar days, see kalshi_weather_nowcast_report.md /
kalshi_weather_nowcast_summary.json, both left untouched as the historical record of that
run) found a promising but unconfirmed LONG-side edge at margin=2F (n=15, 93% win,
+24.5c/ct, t=3.83) -- too thin and a single cherry-picked margin. This v2 extends to the
FULL available history and:
  1. Pulls ALL settled KXHIGH "greater" markets Kalshi's API exposes, not just N days.
     IMPORTANT FINDING: in this environment, Kalshi's /markets endpoint for every KXHIGH*
     series bottoms out at 2026-05-12 (identical oldest ticker, identical 402-market total
     per series, and `max_close_ts` before that returns zero results) -- confirmed by
     direct pagination probing before writing this rerun. So "deep history" here means the
     full ~67-day window from 2026-05-12 to "yesterday" LST, NOT the 6-18 months a mature
     real-world Kalshi weather book would have. IEM's ASOS 1-min archive itself goes back
     decades (verified independently), so the ceiling is entirely on the Kalshi market
     side in this environment, not the weather-obs side. LOOKBACK_DAYS is therefore set
     large (comfortably past the true floor) and the discovery step naturally caps at
     whatever the API actually returns -- see the printed window in the report.
  2. Tests ALL margins {1,2,3,4,5}F x ALL gap thresholds on the FULL sample with a
     Bonferroni correction across the resulting family of LONG-side tests (no
     post-hoc margin cherry-pick).
  3. Reports the CONDITIONAL ASOS-vs-CLI disagreement rate given the decision event fires
     (the true loss probability), plus a Wilson-score worst-case upper bound on that rate
     given the still-modest fired-event counts, and an honest/worst-case expected PnL
     recomputed from it (not just the point-estimate empirical win rate).
  4. Adds day-clustered t per margin on the big sample, a full per-city breakdown, worst
     trade, and a capacity estimate (fires/week x fillable volume).
  5. Explicitly checks whether margin 4-5F finally kills the CLI-disagreement tail while
     keeping EV positive, and picks a single recommended deployable margin.

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
# v2 (deep-history) outputs -- distinct from the original 42-day
# kalshi_weather_nowcast_report.md / _summary.json, which are left on disk untouched as
# the record of the original (thin, cherry-picked-margin) finding.
OUT_REPORT = os.path.join(HERE, "kalshi_weather_nowcast_deep_report.md")
OUT_SUMMARY = os.path.join(HERE, "kalshi_weather_nowcast_deep_summary.json")

# Backtest window: last N days of settled KXHIGH markets ending "yesterday" LST. Set
# deliberately larger than any plausible true history so market discovery naturally
# fetches ALL settled markets the API has (it stops paginating once it runs out, or once
# max_close_ts before the true floor returns zero -- see header note: in this environment
# that floor is 2026-05-12 for every KXHIGH series, i.e. ~67 real days, well short of the
# 400 requested here. We do NOT hardcode 67 -- the script re-discovers the true floor
# every run so it stays correct if more history becomes available later).
LOOKBACK_DAYS = 400

# Decision-event margins to test (deg F on top of the strike; strike itself already
# requires actual > strike since Kalshi "greater" markets are strict inequality).
# PRE-REGISTERED, tested identically and reported for ALL of them (no post-hoc pick):
# 1-3F per the original brief, plus 4-5F specifically to test whether a bigger buffer
# finally kills the ASOS-vs-official-CLI tail risk found at margin=1-2F while EV stays
# positive.
MARGINS = [1, 2, 3, 4, 5]

# Minimum required gap (1 - exec_price for YES-side, or exec_price for NO-side is the
# "already-priced-in" cost; gap = distance from certainty) to count as an actionable edge.
# Combined with MARGINS below into the pre-registered Bonferroni test family (see
# BONFERRONI_ALPHA / bonferroni section) -- every (margin, gap) LONG-side cell is tested
# and reported, not just the best-looking one.
GAP_THRESHOLDS = [0.0, 0.02, 0.05]

# Family-wise alpha for the Bonferroni correction across the pre-registered LONG-side
# margin x gap-threshold test family (len(MARGINS) * len(GAP_THRESHOLDS) cells).
BONFERRONI_ALPHA = 0.05

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

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p, lo=-12.0, hi=12.0, iters=200):
    """Inverse standard-normal CDF via bisection (no scipy available). Accurate to
    ~1e-9 in the tail ranges we use (p in [1e-6, 1-1e-6])."""
    if p <= 0.0:
        return -float("inf")
    if p >= 1.0:
        return float("inf")
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def two_sided_pvalue(t):
    """Two-sided p-value for a t-stat using the normal approximation (day-cluster
    counts here run into the dozens-to-~60s, close enough to normal that this is a
    reasonable stand-in for a true t-distribution p-value without scipy; noted as an
    approximation wherever reported)."""
    if t is None or (isinstance(t, float) and math.isnan(t)):
        return None
    return 2.0 * (1.0 - norm_cdf(abs(t)))


def wilson_upper_bound(k, n, z):
    """Upper bound of the Wilson score confidence interval for a binomial proportion
    k/n at the two-sided confidence implied by z (e.g. z=1.96 for 95%). Used to turn a
    small-n empirical loss rate into an honest, uncertainty-aware WORST-CASE loss rate
    for the tail-risk / expected-PnL recompute, rather than trusting the small-n point
    estimate at face value."""
    if n <= 0:
        return None
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return min(1.0, (center + half) / denom)


def clustered_tstat(pnls, cluster_keys):
    """Cluster-robust t-stat for the mean of pnls, clustered by cluster_keys
    (typically calendar date, since weather is correlated across cities same-day)."""
    n = len(pnls)
    if n == 0:
        return {"mean": None, "se": None, "t": None, "p": None, "n": 0, "n_clusters": 0}
    mean = sum(pnls) / n
    clusters = {}
    for p, k in zip(pnls, cluster_keys):
        clusters.setdefault(k, []).append(p)
    cluster_sums = [sum(x - mean for x in v) for v in clusters.values()]
    var = sum(s * s for s in cluster_sums) / (n * n) if n > 0 else 0.0
    se = math.sqrt(var) if var > 0 else 0.0
    t = mean / se if se > 0 else float("nan")
    p_two_sided = two_sided_pvalue(t) if se > 0 else None
    return {"mean": mean, "se": se, "t": t, "p": p_two_sided, "n": n, "n_clusters": len(clusters)}


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

    print(f"=== Kalshi KXHIGH settlement-nowcast backtest (DEEP HISTORY v2) ===")
    print(f"Requested window (upper bound): {min_date} .. {max_date} ({LOOKBACK_DAYS}d), {len(CITY_CONFIG)} cities")

    print("\n[1/4] Discovering settled 'greater than X' KXHIGH markets (paginating to the true API floor) ...")
    all_mkts = discover_all_markets(min_date)
    total_mkts = sum(len(v) for v in all_mkts.values())
    print(f"  total candidate market-days: {total_mkts}")

    # ASOS fetch range should track the ACTUAL discovered market dates, not the
    # deliberately-oversized LOOKBACK_DAYS request -- otherwise we'd pull ~400 days of
    # unneeded 1-min ASOS data per station (bandwidth + disk) when the real Kalshi
    # history floor (rediscovered above) is much shallower.
    all_tickers_dates = [parse_ticker_date(m["ticker"]) for mkts in all_mkts.values() for m in mkts]
    all_tickers_dates = [d for d in all_tickers_dates if d is not None]
    if all_tickers_dates:
        asos_min_date = min(all_tickers_dates)
        asos_max_date = max(all_tickers_dates)
    else:
        asos_min_date, asos_max_date = min_date, max_date
    print(f"  actual discovered market-date range: {asos_min_date} .. {asos_max_date} "
          f"({(asos_max_date - asos_min_date).days + 1} days) -- this is the TRUE depth of KXHIGH "
          f"history exposed by the API in this environment, and what ASOS is fetched for below.")

    print("\n[2/4] Fetching ASOS station obs (one bulk request per station, actual-range only) ...")
    station_series = build_station_series(asos_min_date, asos_max_date)
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


def side_stats(fired, side_key, bad_key, n_city_days, n_weeks=None):
    """fired = list of (record, side_dict) pairs where side_dict has pnl/exec_price/etc."""
    pnls = [sd["pnl"] for _, sd in fired]
    dates = [r["date"] for r, _ in fired]
    tickers = [r["ticker"] for r, _ in fired]
    prices = [sd["exec_price"] for _, sd in fired]
    wins = [sd["outcome"] for _, sd in fired]
    fees = [sd["fee"] for _, sd in fired]
    vols = [sd["volume_at_exec"] for _, sd in fired]
    ois = [sd["oi_at_exec"] for _, sd in fired]
    fillable_vols_5 = [sd["volume_5min_after"] for _, sd in fired]
    bad = [(r, sd) for r, sd in fired if sd.get(bad_key)]
    fillable = [(r, sd) for r, sd in fired if sd.get("fillable")]

    n_fired = len(fired)
    mean_price = (sum(prices) / len(prices)) if prices else None
    mean_fee = (sum(fees) / len(fees)) if fees else None
    win_rate = (sum(wins) / len(wins)) if wins else None
    # the REAL loss mode for the LONG side is exactly "fired but settled the other way",
    # i.e. cond_loss_rate == 1-win_rate here; kept as an explicit, separately-labeled key
    # per the task's request to report the CONDITIONAL disagreement rate given fired.
    cond_loss_rate = (1.0 - win_rate) if win_rate is not None else None
    n_bad = len(bad)

    # Wilson-score UPPER bound on the true loss rate given only n_fired observed events
    # (95% one-sided-equivalent via z=1.96 two-sided Wilson interval) -- an honest,
    # uncertainty-aware stand-in for "how bad could the tail really be" given the still
    # modest fired-event counts, rather than trusting the small-n point estimate.
    z95 = 1.959963985
    worst_case_loss_rate = wilson_upper_bound(n_bad, n_fired, z95) if n_fired else None

    # Analytic EV decomposition: E[pnl] = win_rate - mean_price - mean_fee (since
    # outcome in {0,1} and pnl = outcome - price - fee). Reported both at the point
    # estimate (should equal empirical mean pnl, sanity check) and at the Wilson
    # worst-case loss rate (honest-tail / worst-case expected PnL).
    analytic_ev_point = (win_rate - mean_price - mean_fee) if (win_rate is not None and mean_price is not None and mean_fee is not None) else None
    analytic_ev_worst_case = ((1.0 - worst_case_loss_rate) - mean_price - mean_fee) if (worst_case_loss_rate is not None and mean_price is not None and mean_fee is not None) else None

    gap_sens = {}
    for gt in GAP_THRESHOLDS:
        sub_pairs = [(r, sd) for r, sd in fired if sd["gap"] > gt]
        sub_pnls = [sd["pnl"] for _, sd in sub_pairs]
        sub_dates = [r["date"] for r, _ in sub_pairs]
        ct = clustered_tstat(sub_pnls, sub_dates)
        gap_sens[str(gt)] = {
            "n": len(sub_pairs),
            "mean_pnl": (sum(sub_pnls) / len(sub_pnls)) if sub_pnls else None,
            "t": ct["t"], "p": ct["p"], "n_clusters": ct["n_clusters"], "se": ct["se"],
        }

    stats = {
        "n_fired": n_fired,
        "fire_rate": n_fired / n_city_days if n_city_days else None,
        "fires_per_week": (n_fired / n_weeks) if (n_weeks and n_weeks > 0) else None,
        "mean_exec_price": mean_price,
        "median_exec_price": statistics.median(prices) if prices else None,
        "mean_fee": mean_fee,
        "win_rate": win_rate,
        f"n_{bad_key}": n_bad,
        f"{bad_key}_tickers": [r["ticker"] for r, _ in bad],
        "cond_loss_rate_given_fired": cond_loss_rate,
        "worst_case_loss_rate_wilson95": worst_case_loss_rate,
        "analytic_ev_point": analytic_ev_point,
        "analytic_ev_worst_case": analytic_ev_worst_case,
        "clustered": clustered_tstat(pnls, dates),
        "worst_day": worst_day(pnls, dates, tickers),
        "mean_volume_at_exec": (sum(vols) / len(vols)) if vols else None,
        "median_volume_at_exec": statistics.median(vols) if vols else None,
        "mean_oi_at_exec": (sum(ois) / len(ois)) if ois else None,
        "mean_volume_5min_after": (sum(fillable_vols_5) / len(fillable_vols_5)) if fillable_vols_5 else None,
        "median_volume_5min_after": statistics.median(fillable_vols_5) if fillable_vols_5 else None,
        "gap_sensitivity": gap_sens,
        "n_fillable": len(fillable),
        "fillable_rate": (len(fillable) / len(fired)) if fired else None,
        "fillable_clustered": clustered_tstat([sd["pnl"] for _, sd in fillable], [r["date"] for r, _ in fillable]),
        "fillable_mean_exec_price": (sum(sd["exec_price"] for _, sd in fillable) / len(fillable)) if fillable else None,
    }
    return stats


def bonferroni_analysis(by_margin, family_side="long"):
    """Build the pre-registered LONG-side margin x gap-threshold test family and apply a
    Bonferroni correction across ALL of it (no post-hoc pick of the single best-looking
    cell). family size = len(MARGINS) * len(GAP_THRESHOLDS)."""
    cells = []
    for margin in MARGINS:
        s = by_margin[str(margin)][family_side]
        for gt in GAP_THRESHOLDS:
            gs = s["gap_sensitivity"][str(gt)]
            cells.append({
                "margin": margin, "gap_threshold": gt, "n": gs["n"], "mean_pnl": gs["mean_pnl"],
                "t": gs["t"], "p_uncorrected": gs["p"], "n_clusters": gs["n_clusters"],
            })
    family_size = len(cells)
    corrected_alpha = BONFERRONI_ALPHA / family_size if family_size else BONFERRONI_ALPHA
    z_crit = norm_ppf(1.0 - corrected_alpha / 2.0)
    for c in cells:
        c["p_bonferroni"] = min(1.0, c["p_uncorrected"] * family_size) if c["p_uncorrected"] is not None else None
        c["significant_uncorrected_a05"] = (c["p_uncorrected"] is not None and c["p_uncorrected"] < 0.05)
        c["significant_bonferroni"] = (c["p_uncorrected"] is not None and c["p_uncorrected"] < corrected_alpha)
    return {
        "family_side": family_side,
        "family_size": family_size,
        "alpha": BONFERRONI_ALPHA,
        "corrected_alpha": corrected_alpha,
        "z_crit_two_sided": z_crit,
        "cells": cells,
    }


def pick_best_margin(by_margin, bonferroni, min_n=8):
    """Deployable-margin recommendation: among LONG-side margins with the primary
    (gap_threshold=0) spec, require (a) Bonferroni-significant at the family-corrected
    alpha, (b) worst-case (Wilson-95 upper-bound loss rate) analytic EV still positive,
    and (c) n_fired >= min_n. Rank survivors by worst-case EV (the honest, tail-aware
    number) rather than by raw mean PnL, then fall back to the least-bad candidate with
    a clear reason if nothing clears the bar."""
    sig_by_cell = {(c["margin"], c["gap_threshold"]): c for c in bonferroni["cells"]}
    candidates = []
    for margin in MARGINS:
        s = by_margin[str(margin)]["long"]
        cell = sig_by_cell.get((margin, 0.0))
        ok_n = s["n_fired"] >= min_n
        ok_sig = bool(cell and cell["significant_bonferroni"])
        ok_tail = (s["analytic_ev_worst_case"] is not None and s["analytic_ev_worst_case"] > 0)
        candidates.append({
            "margin": margin, "n_fired": s["n_fired"], "win_rate": s["win_rate"],
            "mean_pnl": s["clustered"]["mean"], "t": s["clustered"]["t"],
            "p_bonferroni": cell["p_bonferroni"] if cell else None,
            "cond_loss_rate_given_fired": s["cond_loss_rate_given_fired"],
            "worst_case_loss_rate_wilson95": s["worst_case_loss_rate_wilson95"],
            "analytic_ev_point": s["analytic_ev_point"],
            "analytic_ev_worst_case": s["analytic_ev_worst_case"],
            "fires_per_week": s["fires_per_week"],
            "ok_n": ok_n, "ok_bonferroni_significant": ok_sig, "ok_worst_case_ev_positive": ok_tail,
            "passes_all": ok_n and ok_sig and ok_tail,
        })
    survivors = [c for c in candidates if c["passes_all"]]
    if survivors:
        best = max(survivors, key=lambda c: c["analytic_ev_worst_case"])
        verdict = "CONFIRMED"
    else:
        # no margin clears every bar -- report the least-bad candidate for transparency
        # but the verdict is a kill, not a soft pass.
        best = max(candidates, key=lambda c: (c["analytic_ev_worst_case"] if c["analytic_ev_worst_case"] is not None else -999))
        verdict = "KILLED"
    return {"verdict": verdict, "recommended_margin": best["margin"] if best else None,
            "candidates": candidates, "chosen": best}


def build_summary(results, skipped, min_date, max_date, station_resolution=None):
    n_city_days = len(results)

    # Use the ACTUAL discovered date range (not the requested LOOKBACK_DAYS floor) for
    # window reporting and capacity (fires/week) math -- LOOKBACK_DAYS=400 is just an
    # upper bound; the real Kalshi-side floor in this environment is 2026-05-12 (see
    # header note), rediscovered here from the data itself so the script stays correct
    # if the API exposes more/less history in the future.
    if results:
        actual_min_date = min(datetime.strptime(r["date"], "%Y-%m-%d").date() for r in results)
        actual_max_date = max(datetime.strptime(r["date"], "%Y-%m-%d").date() for r in results)
    else:
        actual_min_date, actual_max_date = min_date, max_date
    span_days = (actual_max_date - actual_min_date).days + 1
    n_weeks = span_days / 7.0

    asos_cli_agree = sum(1 for r in results if r["asos_vs_strike_yes"] == r["official_yes"])
    asos_cli_disagree = [r for r in results if r["asos_vs_strike_yes"] != r["official_yes"]]

    by_margin = {}
    for margin in MARGINS:
        mk = str(margin)
        long_fired = [(r, r["long"][mk]) for r in results if r["long"][mk].get("fired") and "pnl" in r["long"][mk]]
        short_fired = [(r, r["short"][mk]) for r in results if r["short"][mk].get("fired") and "pnl" in r["short"][mk]]

        by_margin[mk] = {
            "long": side_stats(long_fired, "long", "locked_yes_settled_no", n_city_days, n_weeks),
            "short": side_stats(short_fired, "short", "locked_no_settled_yes", n_city_days, n_weeks),
        }

    bonferroni = bonferroni_analysis(by_margin, "long")
    best_margin = pick_best_margin(by_margin, bonferroni)

    # short-side sensitivity to the late-day cutoff hour (computed for margins[0])
    cutoff_sens = {}
    for h in LATE_DAY_CUTOFF_HOURS:
        hk = str(h)
        fired = [(r, r["short_by_cutoff"][hk]) for r in results
                 if r.get("short_by_cutoff", {}).get(hk, {}).get("fired") and "pnl" in r["short_by_cutoff"][hk]]
        cutoff_sens[hk] = side_stats(fired, "short", "locked_no_settled_yes", n_city_days, n_weeks)

    by_city = {}
    for series, cfg in CITY_CONFIG.items():
        city_res = [r for r in results if r["series"] == series]
        if not city_res:
            continue
        entry = {"name": cfg["name"], "station": cfg["station"], "n_city_days": len(city_res), "by_margin": {}}
        for margin in MARGINS:
            mk = str(margin)
            lf = [r for r in city_res if r["long"][mk].get("fired") and "pnl" in r["long"][mk]]
            bad = [r for r in lf if r["long"][mk].get("locked_yes_settled_no")]
            entry["by_margin"][mk] = {
                "fired": len(lf),
                "mean_pnl": (sum(r["long"][mk]["pnl"] for r in lf) / len(lf)) if lf else None,
                "win_rate": (sum(r["long"][mk]["outcome"] for r in lf) / len(lf)) if lf else None,
                "n_settled_wrong_way": len(bad),
            }
        by_city[series] = entry

    # capacity: recommended-margin fire rate/week x fillable size, as a rough weekly
    # deployable-notional proxy (median fillable contracts/event x mean entry price).
    capacity = {}
    for margin in MARGINS:
        s = by_margin[str(margin)]["long"]
        med_fill_vol = s.get("median_volume_5min_after")
        capacity[str(margin)] = {
            "fires_per_week": s["fires_per_week"],
            "fillable_rate": s["fillable_rate"],
            "median_fillable_volume_5min": med_fill_vol,
            "mean_entry_price": s["mean_exec_price"],
            "rough_weekly_notional_usd": (
                s["fires_per_week"] * s["fillable_rate"] * med_fill_vol * s["mean_exec_price"]
                if all(x is not None for x in (s["fires_per_week"], s["fillable_rate"], med_fill_vol, s["mean_exec_price"]))
                else None
            ),
        }

    summary = {
        "window": {
            "requested_min_date": min_date.isoformat(), "requested_max_date": max_date.isoformat(),
            "requested_lookback_days": LOOKBACK_DAYS,
            "actual_min_date": actual_min_date.isoformat(), "actual_max_date": actual_max_date.isoformat(),
            "actual_span_days": span_days,
            "note": "actual_* is the TRUE full history the Kalshi API exposed in this environment "
                    "(discovery pages back until max_close_ts returns zero) -- see script header. "
                    "requested_lookback_days=400 was an upper bound, not the real depth achieved.",
        },
        "n_series": len(CITY_CONFIG),
        "n_city_days_analyzed": n_city_days,
        "n_city_days_skipped": len(skipped),
        "asos_vs_official_cli": {
            "agree": asos_cli_agree,
            "agree_rate": asos_cli_agree / n_city_days if n_city_days else None,
            "disagree_n": len(asos_cli_disagree),
            "disagree_rate_unconditional": len(asos_cli_disagree) / n_city_days if n_city_days else None,
            "disagree_examples": [
                {"ticker": r["ticker"], "date": r["date"], "strike": r["strike"],
                 "asos_full_day_max": r["full_day_asos_max"], "official_result": r["result"]}
                for r in asos_cli_disagree[:20]
            ],
        },
        "margins_tested": MARGINS,
        "gap_thresholds_tested": GAP_THRESHOLDS,
        "late_day_cutoff_lst_hour": LATE_DAY_CUTOFF_HOUR,
        "late_day_cutoff_hours_tested": LATE_DAY_CUTOFF_HOURS,
        "fee_model": "0.07 * p * (1-p) per contract",
        "station_resolution_min_gap": station_resolution or {},
        "by_margin": by_margin,
        "bonferroni": bonferroni,
        "best_margin": best_margin,
        "capacity": capacity,
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
    w = summary["window"]
    lines = []
    lines.append("# Kalshi KXHIGH Weather Settlement-Nowcast Backtest -- DEEP HISTORY RERUN (v2)\n")
    lines.append("## Executive summary\n")
    lines.append(verdict_text(summary))
    lines.append("\n---\n")
    lines.append(f"**Requested** lookback: {w['requested_lookback_days']} days (an intentionally large upper "
                 f"bound). **Actual** history available and used: **{w['actual_min_date']} to "
                 f"{w['actual_max_date']}** ({w['actual_span_days']} calendar days), {summary['n_series']} "
                 f"KXHIGH city series.\n")
    lines.append("**Data-depth finding (read this first):** direct pagination probing of Kalshi's "
                 "`/markets?series_ticker=...&status=settled` endpoint (and confirming with "
                 "`max_close_ts` filters before the apparent floor) shows every KXHIGH* series in this "
                 "environment starts at the SAME date, 2026-05-12, with the SAME market count. That is a "
                 "hard floor on the Kalshi side, not a self-imposed limit -- this script fetches ALL of it "
                 "(`LOOKBACK_DAYS=400` as an upper bound, real depth rediscovered from the data every run). "
                 "IEM's ASOS 1-min archive was independently checked back to 2020 and has no such limit, so "
                 "the ceiling here is specifically \"how much settled KXHIGH history Kalshi exposes\", not "
                 "weather-data availability. This means the 'deep history' rerun is ~1.6x the original 42-day "
                 "sample, not the 6-18 months / hundreds-of-events scale the task brief anticipated -- reported "
                 "honestly below rather than working around it.\n")
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

    lines.append("\n## 1. ASOS-observed vs official CLI settlement agreement -- the true tail risk\n")
    a = summary["asos_vs_official_cli"]
    lines.append(f"UNCONDITIONAL: comparing (full-LST-day ASOS max at the settlement station > strike) to the "
                 f"official Kalshi result across ALL city-days (not just fired events): agreement = "
                 f"**{a['agree']}/{summary['n_city_days_analyzed']}** ({fmt(a['agree_rate'], 3)}). "
                 f"Disagreements: **{a['disagree_n']}** ({fmt(a['disagree_rate_unconditional'],3)}).\n")
    lines.append("CONDITIONAL (the real loss probability): given the LONG decision event actually FIRES "
                 "(running ASOS max clears strike+margin), the loss rate is `cond_loss_rate_given_fired` "
                 "reported per margin in section 2 below -- this is what matters for sizing the trade, not the "
                 "unconditional rate above, since firing already selects for days where ASOS ran hot relative "
                 "to strike.\n")
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
                         f"**t = {fmt(c['t'],2)}**, p (normal-approx, uncorrected) = {fmt(c['p'],4)} "
                         f"(n={c['n']}, n_clusters={c['n_clusters']})")
            if side == "long":
                lines.append(f"- **Conditional loss rate given fired (the real tail risk): "
                             f"{fmt(s['cond_loss_rate_given_fired'],3)}** | Wilson-95 worst-case upper bound on "
                             f"that loss rate given only n={s['n_fired']} fired events: "
                             f"**{fmt(s['worst_case_loss_rate_wilson95'],3)}**")
                lines.append(f"- Analytic EV/contract at point-estimate loss rate: {fmt(s['analytic_ev_point'])} "
                             f"(sanity check vs. empirical mean PnL above) | at Wilson-95 **worst-case** loss rate: "
                             f"**{fmt(s['analytic_ev_worst_case'])}**")
                lines.append(f"- Fires/week (over the {summary['window']['actual_span_days']}-day window): "
                             f"{fmt(s['fires_per_week'],2)}")
            if s["worst_day"]:
                w = s["worst_day"]
                lines.append(f"- Worst trade: {fmt(w['pnl'])} on {w['date']} ({w['ticker']})")
            lines.append(f"- Capacity proxy: mean volume at execution candle = {fmt(s['mean_volume_at_exec'],1)} "
                         f"contracts/min (median {fmt(s['median_volume_at_exec'],1)}); mean open interest = "
                         f"{fmt(s['mean_oi_at_exec'],1)}; median fillable volume in the 5min after t* = "
                         f"{fmt(s['median_volume_5min_after'],1)} contracts")
            lines.append(f"- **Fillable (>0 volume in the 5min after t*): {s['n_fillable']}/{s['n_fired']} "
                         f"({fmt(s['fillable_rate'],3)})**, mean exec price when fillable = "
                         f"{fmt(s['fillable_mean_exec_price'])}, day-clustered t (fillable-only) = "
                         f"{fmt(s['fillable_clustered']['t'],2)} (mean {fmt(s['fillable_clustered']['mean'])}, "
                         f"n={s['fillable_clustered']['n']})")
            lines.append(f"- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered "
                         f"Bonferroni test family for the LONG side, see section 2c):")
            for gt in summary["gap_thresholds_tested"]:
                gs = s["gap_sensitivity"][str(gt)]
                lines.append(f"  - gap > {gt}: n={gs['n']}, mean PnL = {fmt(gs['mean_pnl'])}, "
                             f"t={fmt(gs['t'],2)}, p={fmt(gs['p'],4)}")

    lines.append("\n## 2b. SHORT side sensitivity to late-day cutoff hour (margin=%s°F)\n" % summary["margins_tested"][0])
    lines.append("| cutoff (LST hr) | fired | fire rate | mean price | win rate | mean PnL | t (all) | fillable n | t (fillable) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for h in summary["late_day_cutoff_hours_tested"]:
        cs = summary["short_cutoff_sensitivity"][str(h)]
        c = cs["clustered"]
        fc = cs["fillable_clustered"]
        lines.append(f"| {h}:00 | {cs['n_fired']} | {fmt(cs['fire_rate'],3)} | {fmt(cs['mean_exec_price'])} | "
                     f"{fmt(cs['win_rate'],3)} | {fmt(c['mean'])} | {fmt(c['t'],2)} | {cs['n_fillable']} | {fmt(fc['t'],2)} |")

    bf = summary["bonferroni"]
    lines.append("\n## 2c. Multiple-testing correction (Bonferroni) -- LONG side, margin x gap-threshold\n")
    lines.append(f"Pre-registered test family: **{bf['family_size']} cells** = "
                 f"{len(summary['margins_tested'])} margins x {len(summary['gap_thresholds_tested'])} gap "
                 f"thresholds, ALL tested and reported (no post-hoc pick of the best-looking cell). "
                 f"Family-wise alpha = {bf['alpha']}, Bonferroni-corrected per-cell alpha = "
                 f"**{fmt(bf['corrected_alpha'],5)}** (two-sided normal-approx |t| >= "
                 f"{fmt(bf['z_crit_two_sided'],2)} required for significance).\n")
    lines.append("| margin | gap thr | n | mean PnL | t | p (uncorrected) | p (Bonferroni) | sig @ .05 uncorr. | **sig @ Bonferroni** |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for c in bf["cells"]:
        lines.append(f"| {c['margin']} | {c['gap_threshold']} | {c['n']} | {fmt(c['mean_pnl'])} | "
                     f"{fmt(c['t'],2)} | {fmt(c['p_uncorrected'],4)} | {fmt(c['p_bonferroni'],4)} | "
                     f"{'yes' if c['significant_uncorrected_a05'] else 'no'} | "
                     f"{'**YES**' if c['significant_bonferroni'] else 'no'} |")

    lines.append("\n## 3. By city, by margin (LONG side)\n")
    for margin in summary["margins_tested"]:
        mk = str(margin)
        lines.append(f"\n### Margin = {margin}°F\n")
        lines.append("| series | city | station | city-days | fired | win rate | mean PnL | settled wrong way |")
        lines.append("|---|---|---|---|---|---|---|---|")
        rows = sorted(summary["by_city"].items(), key=lambda kv: -(kv[1]["by_margin"][mk]["fired"] or 0))
        for series, c in rows:
            bm = c["by_margin"][mk]
            if bm["fired"] == 0:
                continue
            lines.append(f"| {series} | {c['name']} | {c['station']} | {c['n_city_days']} | "
                         f"{bm['fired']} | {fmt(bm['win_rate'],3)} | {fmt(bm['mean_pnl'])} | "
                         f"{bm['n_settled_wrong_way']} |")
        n_zero = sum(1 for _, c in rows if c["by_margin"][mk]["fired"] == 0)
        if n_zero:
            lines.append(f"\n({n_zero} of {len(rows)} cities never fired at this margin over the full window.)\n")

    lines.append("\n## 3b. Capacity (fires/week x fillable size), by margin -- LONG side\n")
    lines.append("| margin | fires/week (all 20 cities) | fillable rate | median fillable vol (5min) | "
                 "mean entry price | rough weekly notional (USD) |")
    lines.append("|---|---|---|---|---|---|")
    for margin in summary["margins_tested"]:
        cap = summary["capacity"][str(margin)]
        lines.append(f"| {margin} | {fmt(cap['fires_per_week'],2)} | {fmt(cap['fillable_rate'],3)} | "
                     f"{fmt(cap['median_fillable_volume_5min'],1)} | {fmt(cap['mean_entry_price'])} | "
                     f"{fmt(cap['rough_weekly_notional_usd'],0)} |")

    lines.append("\n## 4. Best-margin selection and verdict\n")
    bm_sel = summary["best_margin"]
    lines.append(f"Selection rule (pre-specified): among margins {summary['margins_tested']} at gap-threshold=0, "
                 f"require (a) n_fired >= 8, (b) Bonferroni-significant at the corrected alpha above, and "
                 f"(c) worst-case (Wilson-95 upper-bound loss rate) analytic EV still positive. Survivors ranked "
                 f"by worst-case EV, not raw mean PnL.\n")
    lines.append("| margin | n | win rate | mean PnL | t | p (Bonferroni) | cond. loss rate | worst-case loss rate | "
                 "EV (point) | **EV (worst-case)** | fires/wk | passes all bars |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in bm_sel["candidates"]:
        lines.append(f"| {c['margin']} | {c['n_fired']} | {fmt(c['win_rate'],3)} | {fmt(c['mean_pnl'])} | "
                     f"{fmt(c['t'],2)} | {fmt(c['p_bonferroni'],4)} | {fmt(c['cond_loss_rate_given_fired'],3)} | "
                     f"{fmt(c['worst_case_loss_rate_wilson95'],3)} | {fmt(c['analytic_ev_point'])} | "
                     f"**{fmt(c['analytic_ev_worst_case'])}** | {fmt(c['fires_per_week'],2)} | "
                     f"{'YES' if c['passes_all'] else 'no'} |")
    lines.append(f"\n**Recommended margin: {bm_sel['recommended_margin']}°F. Verdict: {bm_sel['verdict']}.**\n")
    lines.append("(Full narrative verdict is in the Executive Summary at the top of this document.)")

    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(lines) + "\n")


def verdict_text(summary):
    w = summary["window"]
    a = summary["asos_vs_official_cli"]
    bf = summary["bonferroni"]
    bm_sel = summary["best_margin"]
    out = []
    out.append(f"**n = {summary['n_city_days_analyzed']} city-days, {summary['n_series']} cities, "
               f"{w['actual_span_days']} days ({w['actual_min_date']} to {w['actual_max_date']} -- the FULL "
               f"history Kalshi's API exposes for KXHIGH in this environment; see data-depth note below the "
               f"table of contents).** ASOS(1-min)-vs-official-CLI full-day UNCONDITIONAL agreement = "
               f"{fmt(a['agree_rate'],3)} ({a['disagree_n']}/{summary['n_city_days_analyzed']} city-days disagree).\n")

    out.append("**LONG side (buy YES once running max clears strike+margin), ALL 5 pre-registered margins x "
               "3 gap thresholds tested and Bonferroni-corrected, no cherry-pick:**\n")
    for m in summary["margins_tested"]:
        l = summary["by_margin"][str(m)]["long"]
        out.append(f"- margin={m}°F: fired {l['n_fired']}x ({fmt(l['fire_rate'],3)} of city-days, "
                   f"{fmt(l['fires_per_week'],2)}/week), mean entry {fmt(l['mean_exec_price'])}, "
                   f"**win rate {fmt(l['win_rate'],3)}**, cond. loss rate given fired "
                   f"{fmt(l['cond_loss_rate_given_fired'],3)} (Wilson-95 worst-case {fmt(l['worst_case_loss_rate_wilson95'],3)}), "
                   f"mean net PnL/ct {fmt(l['clustered']['mean'])}, day-clustered t={fmt(l['clustered']['t'],2)} "
                   f"(n_clusters={l['clustered']['n_clusters']}), worst-case analytic EV="
                   f"{fmt(l['analytic_ev_worst_case'])}, settled-wrong-way={l.get('n_locked_yes_settled_no')}, "
                   f"fillable {l['n_fillable']}/{l['n_fired']}.")
    out.append("")
    out.append(f"**Bonferroni correction:** {bf['family_size']}-cell pre-registered family (margin x gap "
               f"threshold), corrected per-cell alpha = {fmt(bf['corrected_alpha'],5)} "
               f"(|t| >= {fmt(bf['z_crit_two_sided'],2)} required). See section 2c of the report for the full "
               f"cell-by-cell table -- this determines which margins survive multiple-testing scrutiny versus "
               f"which only looked significant under an uncorrected single-test alpha of 0.05.")
    out.append("")

    out.append("**SHORT side (buy NO late in the day, well below strike):**\n")
    s1 = summary["by_margin"][str(summary["margins_tested"][0])]["short"]
    out.append(f"- At margin={summary['margins_tested'][0]}°F, fires on {fmt(s1['fire_rate'],3)} of city-days "
               f"but mean entry price is already {fmt(s1['mean_exec_price'])} (little gap left) by the time it "
               f"fires; mean net PnL/ct is {fmt(s1['clustered']['mean'])} (t={fmt(s1['clustered']['t'],2)}). Only "
               f"{fmt(s1['fillable_rate'],3)} of fired events have any volume in the following 5 minutes -- most "
               f"of any apparent 'edge' here is not fillable. This side is priced efficiently by Kalshi's book; "
               f"see section 2b for the late-day-cutoff sweep. Kept as a comparison/control, not the object of "
               f"this rerun (task brief is specifically about the LONG side).")
    out.append("")

    cap1 = summary["capacity"].get(str(bm_sel["recommended_margin"]), {})
    out.append(f"**Capacity at the recommended margin ({bm_sel['recommended_margin']}°F):** "
               f"~{fmt(cap1.get('fires_per_week'),2)} fires/week across all {summary['n_series']} cities, "
               f"{fmt(cap1.get('fillable_rate'),3)} fillable, median fillable size "
               f"{fmt(cap1.get('median_fillable_volume_5min'),1)} contracts, mean entry "
               f"{fmt(cap1.get('mean_entry_price'))} -- a rough weekly notional throughput of "
               f"${fmt(cap1.get('rough_weekly_notional_usd'),0)}. This is inherently a low-frequency, "
               f"small-book strategy, not a scalable one, regardless of verdict.")
    out.append("")

    out.append(f"**BLUNT VERDICT: {bm_sel['verdict']}.** ")
    if bm_sel["verdict"] == "CONFIRMED":
        c = bm_sel["chosen"]
        out.append(f"Margin={c['margin']}°F survives ALL three pre-specified bars on the full-history sample: "
                   f"n_fired={c['n_fired']} >= 8, Bonferroni-significant (p_bonferroni={fmt(c['p_bonferroni'],4)} "
                   f"vs corrected alpha {fmt(bf['corrected_alpha'],5)}), and worst-case "
                   f"(Wilson-95-upper-bound loss rate {fmt(c['worst_case_loss_rate_wilson95'],3)}) analytic EV "
                   f"still positive at {fmt(c['analytic_ev_worst_case'])}/contract. The original 42-day, "
                   f"margin=2-only finding is now backed by a larger, honestly-corrected sample rather than a "
                   f"single cherry-picked cell. Deployable as a small, per-trade-capped position sized to the "
                   f"capacity figures above -- still not a scalable book, and should keep accumulating live "
                   f"data given the sample is still bounded by this environment's ~"
                   f"{w['actual_span_days']}-day Kalshi history ceiling.")
    else:
        best = bm_sel["chosen"]
        failed_bars = []
        if not best["ok_n"]:
            failed_bars.append(f"n_fired={best['n_fired']} < 8 (too thin)")
        if not best["ok_bonferroni_significant"]:
            failed_bars.append(f"p_bonferroni={fmt(best['p_bonferroni'],4)} not below corrected alpha "
                               f"{fmt(bf['corrected_alpha'],5)} (not significant once corrected for the "
                               f"{bf['family_size']}-cell test family)")
        if not best["ok_worst_case_ev_positive"]:
            failed_bars.append(f"worst-case (Wilson-95) analytic EV = {fmt(best['analytic_ev_worst_case'])} "
                               f"<= 0 (tail risk eats the edge under a realistic pessimistic loss-rate bound)")
        out.append(f"Even the best surviving candidate (margin={best['margin']}°F, "
                   f"mean PnL={fmt(best['mean_pnl'])}, t={fmt(best['t'],2)}) fails at least one pre-specified "
                   f"bar on the full-history sample: {'; '.join(failed_bars)}. The original 42-day, "
                   f"margin=2-only result (n=15, 93% win, t=3.83) does NOT survive honest n + multiple-testing "
                   f"correction + a tail-aware worst-case loss estimate over the deep-history sample -- it was "
                   f"small-n / cherry-picked-margin luck, not a confirmed structural edge. No margin is "
                   f"recommended for deployment as specified.")
    return "\n".join(out)


if __name__ == "__main__":
    main()
