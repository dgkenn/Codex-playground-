#!/usr/bin/env python3
"""
kalshi_weather_expand.py

TWO linked extensions of the CONFIRMED Kalshi KXHIGH settlement-nowcast edge (see
kalshi_weather_nowcast.py -> kalshi_weather_nowcast_deep_report.md, refined in
kalshi_weather_refined.py -> kalshi_weather_refined_report.md: buy YES once the 1-min ASOS
running max sustains at/above strike+1F for 3 consecutive glitch-filtered readings; n=42 on
the 67-day/20-city live sample, 100% win, +0.343/ct net, day-clustered t=7.56, Bonferroni-
significant, worst-case (Wilson-95) EV=+0.260/ct, 4.39 fires/week).

=== TASK A: is there MORE history than the 67-day live-API sample? ===
Short answer, verified below with live calls, not guesswork: YES -- Kalshi's LIVE
`/markets` endpoint (what kalshi_weather_nowcast.py used) is NOT the full record. Kalshi
documents (https://docs.kalshi.com/getting_started/historical_data) a live/historical
split: `GET /historical/cutoff` returns a moving `market_settled_ts` cutoff (observed here:
2026-05-19T00:00Z, i.e. roughly "now minus ~2 months"), and markets that settled BEFORE that
cutoff silently drop out of the live `/markets` endpoint's result set -- they do not 404,
they just stop being returned by /markets?series_ticker=...&status=settled, which is exactly
why kalshi_weather_nowcast.py's pagination "bottomed out" at 2026-05-12: that wasn't a
product-launch floor, it was the live-window floor, moving day by day. The REAL history
lives at `GET /historical/markets?series_ticker=...` (same cursor pagination, no auth), and
`GET /historical/markets/{ticker}/candlesticks` / `GET /historical/trades?ticker=...` serve
full 1-min price/trade history for markets from ANY date, verified directly against a
2021-08-06 KXHIGHNY-lineage market (ticker was literally "HIGHNY-21AUG06-T86" before Kalshi's
"KX" ticker-prefix rename -- /historical/markets bridges old and new ticker eras under the
same series_ticker query). Per-series true floor (deep-paginated below, not assumed):
KXHIGHNY/KXHIGHCHI back to 2021-08, KXHIGHMIA to 2023-05, KXHIGHDEN to 2024-11,
KXHIGHLAX to 2025-01 -- i.e. genuinely different product-launch dates per city, NOT a single
"weather markets are all new" story. KXLOW* (the low-temp product) is itself much younger:
every KXLOWT<city> series checked floors at 2025-12-13, ~7 months, not years -- a real,
separately-verified finding (LOW is a newer Kalshi product than HIGH), and matched
independently by IEM's free ASOS 1-min archive, which has no floor of its own back to 2021
(spot-checked). 3rd-party archives (Lychee Data: Kalshi trades since Jul 2021, 36GB, paid;
Jon-Becker/prediction-market-analysis: public 33GB Kalshi+Polymarket dataset since ~2021,
free but no per-series-launch documentation found; Predexon: free orderbook snapshots only
from 2026-01-07) are CONSISTENT with the Kalshi-native finding but unnecessary -- the primal
source (Kalshi's own /historical/* endpoints) already has it, for free, unauthenticated, with
the same cursor-pagination shape as the endpoints kalshi_weather_nowcast.py already uses.
BLUNT bottom line: longer backtest history is obtainable, from Kalshi itself, TODAY, for
free -- the 67-day sample was an artifact of using the wrong endpoint family, not a real data
ceiling. (Not fully re-backtested here at multi-year depth -- see section 1 for why, and what
a full re-run would cost.)

=== TASK B: expand VOLUME via more market TYPES with the same nowcast mechanic ===
KXLOW (daily low temp, "greater" strike_type, 20 cities matching KXHIGH's list): the daily
low is set overnight/early morning and only ratchets DOWN for the rest of the LST day. So the
TRUE structural mirror of the confirmed KXHIGH rule is not a "wait until midday" heuristic --
it is the exact same instant/no-lookahead mechanic, sign-flipped: once the running MIN
sustains AT OR BELOW strike-margin for N consecutive glitch-filtered readings, "low > strike"
(the "greater" market's YES condition) is ~decided NO and can only get more certain (the min
never goes back up). That fires the LOCKED-NO trade (buy NO) any time of day, most often
early morning -- this is what's tested as PRIMARY below, on the identical margin x sustain
grid as kalshi_weather_refined.py, on the SAME 67-day/20-city ASOS sample (cache reused, no
new ASOS fetch needed). A SECONDARY/comparison rule (buy YES once, after a late-morning
cutoff hour, the running min has stayed >= strike+margin all day) mirrors kalshi_weather_
nowcast.py's SHORT side -- included for symmetry, not expected to be the confirmed edge (the
original KXHIGH short side wasn't either).

KXRAINNYC (daily "will it rain in NYC", strike=0, "greater", 65 settled markets on the same
window -- the only Kalshi daily single-city rain series with real settled history; the
newer multi-city KXRAIN series launched 2026-07-15, n=20, one calendar date, too new to
backtest) has the same ratchet structure in a cruder form: cumulative LST-day precip only
increases, so once measurable precip is observed, YES is ~locked. IEM's free ASOS 1-min
archive publishes a `precip` variable (1-min accumulation, summed here into a running
cumulative total per LST day) -- tested below as PRIMARY (buy YES on first sustained nonzero
reading) and SECONDARY (buy NO late in the day if still bone dry), same discipline.

Other Kalshi weather series with a "locks in" observable were scanned (KXHIGHUS/national
daily high, KXCITIESWEATHER, KXDVHIGH, KXAQICITY, KXHIGHNYD) -- structurally similar in
principle but each adds real complexity (multi-station max-of-many, index construction, or a
fundamentally different hourly-directional mechanic) big enough to deserve its own dedicated
build, not a corner of this script; flagged, not backtested (see section 5).

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kalshi_weather_nowcast as base       # noqa: E402  (http/cache/fee/stat helpers, CITY_CONFIG, ASOS fetch)
import kalshi_weather_refined as refined    # noqa: E402  (glitch filter, sustained-cross firing logic)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_REPORT = os.path.join(HERE, "kalshi_weather_expand_report.md")
OUT_SUMMARY = os.path.join(HERE, "kalshi_weather_expand_summary.json")

KBASE = base.KBASE
UA = base.UA
Z95 = 1.959963985

# ---------------------------------------------------------------------------
# Config: KXLOW city series -- mirrors base.CITY_CONFIG 1:1 by city/station (verified live
# against the Kalshi API before writing this: every KXHIGH<city> series in base.CITY_CONFIG
# has a live KXLOWT<city> counterpart with settled 'greater' markets; NONE of the un-prefixed
# guesses (KXLOWMIA, KXLOWDEN, KXLOWNY, ...) have any settled markets -- those are dead/
# legacy-reserved tickers, same pattern as HIGHNY/HIGHAUS/etc turning out to be pre-rename
# ticker eras with zero LIVE (but real HISTORICAL) markets; see section 1).
LOW_CITY_CONFIG = {
    "KXLOWTDEN":  {"station": "KDEN", "offset": -7, "name": "Denver"},
    "KXLOWTMIA":  {"station": "KMIA", "offset": -5, "name": "Miami"},
    "KXLOWTCHI":  {"station": "KMDW", "offset": -6, "name": "Chicago (Midway)"},
    "KXLOWTBOS":  {"station": "KBOS", "offset": -5, "name": "Boston"},
    "KXLOWTAUS":  {"station": "KAUS", "offset": -6, "name": "Austin (Bergstrom)"},
    "KXLOWTSEA":  {"station": "KSEA", "offset": -8, "name": "Seattle"},
    "KXLOWTSFO":  {"station": "KSFO", "offset": -8, "name": "San Francisco"},
    "KXLOWTMIN":  {"station": "KMSP", "offset": -6, "name": "Minneapolis"},
    "KXLOWTDC":   {"station": "KDCA", "offset": -5, "name": "Washington DC"},
    "KXLOWTATL":  {"station": "KATL", "offset": -5, "name": "Atlanta"},
    "KXLOWTDAL":  {"station": "KDFW", "offset": -6, "name": "Dallas"},
    "KXLOWTSATX": {"station": "KSAT", "offset": -6, "name": "San Antonio"},
    "KXLOWTNYC":  {"station": "NYC",  "offset": -5, "name": "New York (Central Park)"},
    "KXLOWTOKC":  {"station": "KOKC", "offset": -6, "name": "Oklahoma City"},
    "KXLOWTLV":   {"station": "KLAS", "offset": -8, "name": "Las Vegas"},
    "KXLOWTPHX":  {"station": "KPHX", "offset": -7, "name": "Phoenix"},
    "KXLOWTHOU":  {"station": "KHOU", "offset": -6, "name": "Houston (Hobby)"},
    "KXLOWTPHIL": {"station": "KPHL", "offset": -5, "name": "Philadelphia"},
    "KXLOWTNOLA": {"station": "KMSY", "offset": -6, "name": "New Orleans"},
    "KXLOWTLAX":  {"station": "KLAX", "offset": -8, "name": "Los Angeles"},
}

RAIN_CITY_CONFIG = {
    "KXRAINNYC": {"station": "NYC", "offset": -5, "name": "New York (Central Park)"},
}
# KXRAIN (multi-city daily rain) launched 2026-07-15 in this environment (verified: deep
# pagination of /historical/markets and live /markets both return n=20, all a SINGLE
# calendar date) -- structurally identical mechanic to KXRAINNYC but genuinely too new to
# backtest (0 fully-elapsed weeks of history). Logged, not run.
KXRAIN_MULTICITY_TICKER = "KXRAIN"

# Same pre-registered grid as kalshi_weather_refined.py, reused unchanged for apples-to-apples
# rigor on the new market types (no new degrees of freedom invented for this expansion).
MARGINS_LOW = [1, 2, 3]
SUSTAIN_MINUTES = [1, 3, 5, 10]
GAP_THRESHOLDS = base.GAP_THRESHOLDS  # [0.0, 0.02, 0.05]

# SECONDARY/comparison rule cutoffs -- KXLOW: hours after which the overnight/morning low is
# assumed to plausibly be in (climatological low hour is ~sunrise, 5-8am LST; cutoffs chosen
# to bracket well past that with margin). KXRAIN: hours after which "still bone dry" is
# assumed to plausibly hold (late afternoon/evening).
LOW_SECONDARY_CUTOFF_HOURS = [8, 10, 12, 14]
RAIN_SECONDARY_CUTOFF_HOURS = [16, 18, 20, 22]

# Rain-specific: glitch cap on a single 1-min precip reading (world-record sustained rain
# rates are on the order of a few in/hr; a single free-feed 1-min reading above this is
# treated as a transmission glitch, not real precip) and the "any measurable rain" epsilon.
RAIN_GLITCH_CAP_IN_PER_MIN = 0.30
RAIN_EPS_IN = 0.005

CACHE_DIR = base.CACHE_DIR


# ===========================================================================
# TASK A: history-depth investigation (Kalshi's own /historical/* endpoints)
# ===========================================================================

TICKER_DATE_RE = base.TICKER_DATE_RE


def fetch_historical_cutoff():
    return base.http_get_json(f"{KBASE}/historical/cutoff")


def paginate_all(url_base, cache_key, max_pages=80):
    """Generic full cursor-pagination over either /markets or /historical/markets (same
    cursor shape). Cached to disk (mirrors base.load_cache/save_cache) since a full
    multi-year walk of the biggest series (KXHIGHNY/KXHIGHCHI, ~8800 markets, ~45 pages) is
    expensive to redo every run."""
    cached = base.load_cache(cache_key)
    if cached is not None:
        return cached
    out = []
    cursor = None
    for _ in range(max_pages):
        url = url_base + (f"&cursor={cursor}" if cursor else "")
        d = base.http_get_json(url)
        mkts = d.get("markets", [])
        out += mkts
        cursor = d.get("cursor")
        if not mkts or not cursor:
            break
    base.save_cache(cache_key, out)
    return out


def discover_series_full_history(series_ticker):
    """Merge /historical/markets (everything older than the live cutoff -- this is what
    actually reaches back to a series' true launch) with live /markets?status=settled
    (everything from the cutoff to now), de-duplicated by ticker. This is BOTH the Task-A
    depth probe AND how Task-B's KXLOW/KXRAIN discovery below gets the full 67-day sample
    without a live-window gap at the moving cutoff boundary."""
    hist = paginate_all(
        f"{KBASE}/historical/markets?series_ticker={series_ticker}&limit=200",
        f"hist_markets_{series_ticker}.json",
    )
    live = paginate_all(
        f"{KBASE}/markets?series_ticker={series_ticker}&status=settled&limit=200",
        f"live_settled_markets_{series_ticker}.json",
    )
    by_ticker = {}
    for m in hist + live:
        by_ticker[m["ticker"]] = m
    merged = list(by_ticker.values())
    dated = [(base.parse_ticker_date(m["ticker"]), m) for m in merged]
    dated = [(d, m) for d, m in dated if d is not None]
    return merged, dated


def task_a_investigate():
    print("\n[TASK A] Probing Kalshi's live/historical split and per-series true floors ...")
    cutoff = fetch_historical_cutoff()
    print(f"  /historical/cutoff -> {cutoff}")

    series_to_check = list(base.CITY_CONFIG.keys()) + list(LOW_CITY_CONFIG.keys()) + \
        list(RAIN_CITY_CONFIG.keys()) + [KXRAIN_MULTICITY_TICKER]
    per_series = {}
    for s in series_to_check:
        try:
            merged, dated = discover_series_full_history(s)
        except Exception as e:
            print(f"  [warn] {s}: {e}", file=sys.stderr)
            per_series[s] = {"error": str(e)}
            continue
        if dated:
            dmin = min(d for d, _ in dated)
            dmax = max(d for d, _ in dated)
            n_dates = len(set(d for d, _ in dated))
        else:
            dmin = dmax = None
            n_dates = 0
        per_series[s] = {
            "n_settled_total": len(merged),
            "n_unique_dates": n_dates,
            "floor_date": dmin.isoformat() if dmin else None,
            "ceiling_date": dmax.isoformat() if dmax else None,
            "true_history_days": (dmax - dmin).days + 1 if (dmin and dmax) else 0,
        }
        print(f"  {s:14s}: {len(merged):5d} settled markets, {n_dates:4d} unique dates, "
              f"floor={dmin} ceiling={dmax}")

    # Spot-verify (not for every series -- would be ~40 extra HTTP round trips for a fact
    # already established) that /historical/*  candlesticks and trades actually serve DATA,
    # not just market metadata, for a pre-2026 ticker -- this is the concrete "not just
    # obtainable in principle" check.
    verify = {}
    probe_ticker = None
    probe_series = None
    for s in ("KXHIGHNY", "KXHIGHCHI"):
        merged, dated = discover_series_full_history(s)
        if dated:
            dated.sort(key=lambda x: x[0])
            probe_ticker = dated[0][1]["ticker"]
            probe_series = s
            break
    if probe_ticker:
        close_time_str = None
        for _, m in dated:
            if m["ticker"] == probe_ticker:
                close_time_str = m["close_time"]
                break
        close_dt = datetime.strptime(close_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        start_ts = int((close_dt - timedelta(days=2)).timestamp())
        end_ts = int(close_dt.timestamp())
        try:
            cd = base.http_get_json(
                f"{KBASE}/historical/markets/{probe_ticker}/candlesticks"
                f"?start_ts={start_ts}&end_ts={end_ts}&period_interval=1")
            n_candles = len(cd.get("candlesticks", []))
        except Exception as e:
            n_candles = f"ERROR: {e}"
        try:
            td = base.http_get_json(f"{KBASE}/historical/trades?ticker={probe_ticker}&limit=5")
            n_trades = len(td.get("trades", []))
        except Exception as e:
            n_trades = f"ERROR: {e}"
        verify = {
            "probe_series": probe_series, "probe_ticker": probe_ticker,
            "n_candlesticks_returned": n_candles, "n_trades_sample_returned": n_trades,
        }
        print(f"  Verified /historical candlesticks+trades work for {probe_ticker}: "
              f"{n_candles} candles, {n_trades} sample trades returned (non-zero = real data, "
              f"not just metadata).")

    # ASOS-side depth spot-check (obs-data-availability is the OTHER half of "obtainable" --
    # a deep Kalshi record is useless without matching weather obs). Confirmed live above
    # before writing this script; re-verified here so the summary/report carries a real,
    # freshly-measured number rather than a claim.
    asos_depth = {}
    for station, probe_date in [("NYC", "2021-08-06"), ("MDW", "2021-08-19")]:
        y, m, d = probe_date.split("-")
        sid = base.asos1min_id(station)
        url = (f"{base.ASOS_BASE}?station={sid}&vars=tmpf&sts={probe_date}T00:00Z"
               f"&ets={probe_date}T02:00Z&sample=1min&tz=UTC&format=onlycomma")
        try:
            text = base.http_get_text(url)
            n_lines = len([ln for ln in text.splitlines() if ln and not ln.startswith("station,")])
        except Exception as e:
            n_lines = f"ERROR: {e}"
        asos_depth[station] = {"probe_date": probe_date, "n_obs_returned_2hr_window": n_lines}
        print(f"  ASOS 1-min depth check {station} @ {probe_date}: {n_lines} obs in a 2hr window "
              f"(should be ~120 if truly minute-resolution that far back).")

    # 3rd-party archive findings -- gathered this session via web search/fetch against the
    # vendors' own docs pages (not re-fetched at runtime by this script -- these are external
    # marketing/docs sites, not a backtest data dependency; embedding the sourced findings
    # here keeps the report self-contained and honest about what was actually checked vs
    # assumed). All three are CONSISTENT with, and none is NECESSARY given, the Kalshi-native
    # /historical/* finding above.
    third_party = {
        "Jon-Becker/prediction-market-analysis (GitHub)": {
            "url": "https://github.com/jon-becker/prediction-market-analysis",
            "finding": "Free, public dataset of Kalshi + Polymarket market/trade data, "
                       "~33GB compressed. README/ANALYSIS.md describe the collection "
                       "framework and Parquet schema but do NOT publish a per-series or "
                       "per-category (e.g. weather) coverage-start-date table -- would "
                       "require downloading/inspecting the actual data/kalshi/ Parquet files "
                       "to confirm KXHIGH*/KXLOW* coverage depth, which the task explicitly "
                       "said not to do (36GB). Plausible it has weather history given it's a "
                       "general Kalshi crawl, but UNVERIFIED at the per-series level here.",
        },
        "Lychee Data": {
            "url": "https://lycheedata.com/kalshi-historical-data",
            "finding": "Paid product; markets '7.68M+ unique markets and 72.1M+ historical "
                       "trades since July 2021' (36GB archive), and has a dedicated weather-"
                       "markets guide page. July 2021 start matches, almost to the week, the "
                       "2021-08-06 KXHIGHNY floor found directly from Kalshi's own "
                       "/historical/markets above -- strong independent corroboration that "
                       "2021 is when Kalshi's weather-market product line (at least NY/CHI) "
                       "began, not a Lychee-specific artifact.",
        },
        "Predexon": {
            "url": "https://docs.predexon.com/api-reference/kalshi/orderbooks",
            "finding": "Free orderbook-snapshot history explicitly starts 2026-01-07 -- LESS "
                       "deep than Kalshi's own /historical/markets for the older-launched "
                       "cities (2021-2025 depending on series), though it would still beat "
                       "the 67-day live-only sample for KXLOW (launched 2025-12-13) if its "
                       "trade/orderbook history genuinely starts Jan 2026. Broader marketing "
                       "copy claims 'historical data across all venues goes back to 2020' but "
                       "the documented, dated Kalshi orderbook endpoint itself says Jan 2026 -- "
                       "took the more specific, dated claim as authoritative over the general one.",
        },
    }

    return {
        "historical_cutoff": cutoff,
        "per_series_true_depth": per_series,
        "historical_endpoint_verification": verify,
        "asos_depth_spotcheck": asos_depth,
        "third_party_archives": third_party,
    }


# ===========================================================================
# TASK B-1: KXLOW nowcast backtest (running MIN, sign-flipped mirror of the confirmed rule)
# ===========================================================================

def find_sustained_cross_below(obs, threshold, sustain_min, max_gap_min=2.5):
    """Sign-flipped mirror of refined.find_sustained_cross: fires on the sustain_min-th
    CONSECUTIVE qualifying (v <= threshold) reading. Same small max_gap_min tolerance for a
    dropped 1-min ob mid-run, same count-based (not duration-based) semantics so sustain=1
    reproduces a plain 'first crossing of the running min' rule."""
    run_count = 0
    prev_t = None
    for t, v in obs:
        if v <= threshold:
            if run_count > 0 and prev_t is not None and (t - prev_t).total_seconds() / 60.0 > max_gap_min:
                run_count = 0
            run_count += 1
            if run_count >= sustain_min:
                return t
        else:
            run_count = 0
        prev_t = t
    return None


def discover_low_markets(min_date):
    cache_key = f"low_markets_{min_date.isoformat()}.json"
    cached = base.load_cache(cache_key)
    if cached is not None:
        return cached
    all_mkts = {}
    for series, cfg in LOW_CITY_CONFIG.items():
        try:
            merged, dated = discover_series_full_history(series)
        except Exception as e:
            print(f"  [warn] {series}: discovery failed: {e}", file=sys.stderr)
            all_mkts[series] = []
            continue
        keep = [m for d, m in dated if d >= min_date and m.get("strike_type") == "greater"
                and m.get("result") in ("yes", "no")]
        all_mkts[series] = keep
        print(f"  {series:14s} ({cfg['name']:26s}): {len(keep)} settled 'greater' markets "
              f">= {min_date}")
    base.save_cache(cache_key, all_mkts)
    return all_mkts


def analyze_low_market_day(series, cfg, market, cleaned_obs, hourly_obs):
    ticker = market["ticker"]
    tdate = base.parse_ticker_date(ticker)
    if tdate is None:
        return None
    strike = market.get("floor_strike")
    if strike is None:
        return None
    result = market["result"]
    offset = cfg["offset"]

    start_utc = datetime(tdate.year, tdate.month, tdate.day, 0, 0, tzinfo=timezone.utc) - timedelta(hours=offset)
    end_utc = start_utc + timedelta(days=1)

    obs = base.slice_window(cleaned_obs, start_utc, end_utc)
    if len(obs) < 20:
        return None
    full_day_min = min(v for _, v in obs)

    close_time_str = market["close_time"]
    close_dt = datetime.strptime(close_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    cand_end = int(min(close_dt, end_utc + timedelta(minutes=2)).timestamp())
    cand_start = int(start_utc.timestamp())
    try:
        candles = base.fetch_candles(series, ticker, cand_start, cand_end)
    except Exception:
        return None
    if not candles:
        return None
    candles.sort(key=lambda c: c["end_period_ts"])

    rec = {
        "series": series, "city": cfg["name"], "station": cfg["station"], "ticker": ticker,
        "date": tdate.isoformat(), "strike": strike, "result": result,
        "official_yes": result == "yes", "full_day_asos_min_cleaned": full_day_min,
        "primary": {},      # keyed "margin_sustain" -> locked-NO fired dict
        "secondary": {},    # keyed "margin_cutoff" -> locked-YES fired dict
    }

    # ---- PRIMARY: instant sustained-below cross -> locked-NO (buy NO), true mirror of the
    # confirmed KXHIGH rule (no time-of-day assumption needed) ----
    for margin in MARGINS_LOW:
        threshold = strike - margin
        for sustain in SUSTAIN_MINUTES:
            key = f"{margin}_{sustain}"
            t_star = find_sustained_cross_below(obs, threshold, sustain)
            cell = {"fired": t_star is not None}
            if t_star is not None:
                exec_c = refined.exec_candle_at_or_after(candles, t_star)
                if exec_c is not None:
                    yb = base.yes_bid_open(exec_c)
                    if not math.isnan(yb):
                        no_ask = 1.0 - yb
                        if no_ask > 0:
                            fee = base.kalshi_fee(no_ask)
                            outcome = 1.0 if result == "no" else 0.0
                            pnl = outcome - no_ask - fee
                            cell.update({
                                "t_star": t_star.isoformat(), "exec_price": no_ask, "fee": fee,
                                "outcome": outcome, "pnl": pnl, "gap": 1.0 - no_ask,
                                "volume_at_exec": float(exec_c.get("volume_fp", 0) or 0),
                                "volume_5min_after": refined.volume_5min_after(candles, base.candle_start_ts(exec_c)),
                                "oi_at_exec": float(exec_c.get("open_interest_fp", 0) or 0),
                                "locked_no_settled_yes": result != "no",
                            })
                        else:
                            cell["fired"] = False
                    else:
                        cell["fired"] = False
                else:
                    cell["fired"] = False
            rec["primary"][key] = cell

    # ---- SECONDARY: late-cutoff locked-YES (buy YES), comparison/control mirroring the
    # original KXHIGH SHORT side (time-of-day heuristic, not expected to be the strong edge) ----
    for margin in MARGINS_LOW:
        for cutoff_h in LOW_SECONDARY_CUTOFF_HOURS:
            key = f"{margin}_{cutoff_h}"
            cutoff_utc = start_utc + timedelta(hours=cutoff_h)
            t_star = None
            running_min = 1e9
            for t, v in obs:
                running_min = min(running_min, v)
                if t >= cutoff_utc and running_min >= strike + margin:
                    t_star = t
                    break
            cell = {"fired": t_star is not None}
            if t_star is not None:
                exec_c = refined.exec_candle_at_or_after(candles, t_star)
                if exec_c is not None:
                    p = base.yes_ask_open(exec_c)
                    if not math.isnan(p) and p > 0:
                        fee = base.kalshi_fee(p)
                        outcome = 1.0 if result == "yes" else 0.0
                        pnl = outcome - p - fee
                        cell.update({
                            "t_star": t_star.isoformat(), "exec_price": p, "fee": fee,
                            "outcome": outcome, "pnl": pnl, "gap": 1.0 - p,
                            "volume_at_exec": float(exec_c.get("volume_fp", 0) or 0),
                            "volume_5min_after": refined.volume_5min_after(candles, base.candle_start_ts(exec_c)),
                            "oi_at_exec": float(exec_c.get("open_interest_fp", 0) or 0),
                            "locked_yes_settled_no": result != "yes",
                        })
                    else:
                        cell["fired"] = False
                else:
                    cell["fired"] = False
            rec["secondary"][key] = cell

    return rec


# ===========================================================================
# TASK B-2: KXRAINNYC nowcast backtest (running cumulative precip)
# ===========================================================================

def fetch_precip_station(station, start_dt, end_dt):
    cache_key = f"precip1min_{station}_{start_dt.date().isoformat()}_{end_dt.date().isoformat()}.json"
    cached = base.load_cache(cache_key)
    if cached is not None:
        return [(datetime.fromisoformat(t).replace(tzinfo=timezone.utc), v) for t, v in cached]
    sid = base.asos1min_id(station)
    sts = start_dt.strftime("%Y-%m-%dT%H:%MZ")
    ets = end_dt.strftime("%Y-%m-%dT%H:%MZ")
    url = f"{base.ASOS_BASE}?station={sid}&vars=precip&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma"
    text = base.http_get_text(url)
    out = []
    for line in text.splitlines():
        if not line or line.startswith("station,"):
            continue
        parts = line.split(",")
        if len(parts) < 4:
            continue
        valid, val = parts[2], parts[3]
        if val in ("", "M"):
            continue
        try:
            t = datetime.strptime(valid.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            v = float(val)
        except ValueError:
            continue
        # glitch filter: reject a single implausible 1-min accumulation outright (kept as raw
        # 0.0 contribution rather than dropped, so the running-sum index stays continuous)
        if v > RAIN_GLITCH_CAP_IN_PER_MIN or v < 0:
            v = 0.0
        out.append((t, v))
    out.sort(key=lambda x: x[0])
    base.save_cache(cache_key, [(t.isoformat(), v) for t, v in out])
    return out


def discover_rain_markets(min_date):
    cache_key = f"rain_markets_{min_date.isoformat()}.json"
    cached = base.load_cache(cache_key)
    if cached is not None:
        return cached
    all_mkts = {}
    for series, cfg in RAIN_CITY_CONFIG.items():
        merged, dated = discover_series_full_history(series)
        keep = [m for d, m in dated if d >= min_date and m.get("strike_type") == "greater"
                and m.get("result") in ("yes", "no")]
        all_mkts[series] = keep
        print(f"  {series:14s} ({cfg['name']:26s}): {len(keep)} settled 'greater' markets >= {min_date}")
    base.save_cache(cache_key, all_mkts)
    return all_mkts


def analyze_rain_market_day(series, cfg, market, precip_obs):
    ticker = market["ticker"]
    tdate = base.parse_ticker_date(ticker)
    if tdate is None:
        return None
    strike = market.get("floor_strike")
    if strike is None:
        return None
    result = market["result"]
    offset = cfg["offset"]

    start_utc = datetime(tdate.year, tdate.month, tdate.day, 0, 0, tzinfo=timezone.utc) - timedelta(hours=offset)
    end_utc = start_utc + timedelta(days=1)

    obs = base.slice_window(precip_obs, start_utc, end_utc)
    if len(obs) < 20:
        return None

    # running cumulative sum for the LST day (1-min "precip" field is a per-minute
    # accumulation, verified empirically before writing this: consecutive values during a
    # known rain event bounce around ~0.01-0.03in rather than monotonically climbing, i.e.
    # it is NOT already a running total -- so we build the running total ourselves, exactly
    # analogous to building a running max from raw tmpf readings)
    running = []
    cum = 0.0
    for t, v in obs:
        cum += v
        running.append((t, v, cum))
    full_day_cum = cum

    close_time_str = market["close_time"]
    close_dt = datetime.strptime(close_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    cand_end = int(min(close_dt, end_utc + timedelta(minutes=2)).timestamp())
    cand_start = int(start_utc.timestamp())
    try:
        candles = base.fetch_candles(series, ticker, cand_start, cand_end)
    except Exception:
        return None
    if not candles:
        return None
    candles.sort(key=lambda c: c["end_period_ts"])

    rec = {
        "series": series, "city": cfg["name"], "ticker": ticker, "date": tdate.isoformat(),
        "strike": strike, "result": result, "full_day_cum_precip": full_day_cum,
        "asos_vs_strike_yes": full_day_cum > RAIN_EPS_IN, "official_yes": result == "yes",
        "primary": {}, "secondary": {},
    }

    # ---- PRIMARY: first sustained-nonzero cumulative reading -> locked-YES (buy YES) ----
    for sustain in [1, 2, 3]:
        run_count = 0
        t_star = None
        for t, v, c in running:
            if c > RAIN_EPS_IN:
                run_count += 1
                if run_count >= sustain:
                    t_star = t
                    break
            else:
                run_count = 0
        cell = {"fired": t_star is not None}
        if t_star is not None:
            exec_c = refined.exec_candle_at_or_after(candles, t_star)
            if exec_c is not None:
                p = base.yes_ask_open(exec_c)
                if not math.isnan(p) and p > 0:
                    fee = base.kalshi_fee(p)
                    outcome = 1.0 if result == "yes" else 0.0
                    pnl = outcome - p - fee
                    cell.update({
                        "t_star": t_star.isoformat(), "exec_price": p, "fee": fee,
                        "outcome": outcome, "pnl": pnl, "gap": 1.0 - p,
                        "volume_at_exec": float(exec_c.get("volume_fp", 0) or 0),
                        "volume_5min_after": refined.volume_5min_after(candles, base.candle_start_ts(exec_c)),
                        "locked_yes_settled_no": result != "yes",
                    })
                else:
                    cell["fired"] = False
            else:
                cell["fired"] = False
        rec["primary"][str(sustain)] = cell

    # ---- SECONDARY: late-cutoff locked-NO (buy NO, still bone dry) ----
    for cutoff_h in RAIN_SECONDARY_CUTOFF_HOURS:
        cutoff_utc = start_utc + timedelta(hours=cutoff_h)
        t_star = None
        for t, v, c in running:
            if t >= cutoff_utc and c <= RAIN_EPS_IN:
                t_star = t
                break
        cell = {"fired": t_star is not None}
        if t_star is not None:
            exec_c = refined.exec_candle_at_or_after(candles, t_star)
            if exec_c is not None:
                yb = base.yes_bid_open(exec_c)
                if not math.isnan(yb):
                    no_ask = 1.0 - yb
                    if no_ask > 0:
                        fee = base.kalshi_fee(no_ask)
                        outcome = 1.0 if result == "no" else 0.0
                        pnl = outcome - no_ask - fee
                        cell.update({
                            "t_star": t_star.isoformat(), "exec_price": no_ask, "fee": fee,
                            "outcome": outcome, "pnl": pnl, "gap": 1.0 - no_ask,
                            "volume_at_exec": float(exec_c.get("volume_fp", 0) or 0),
                            "volume_5min_after": refined.volume_5min_after(candles, base.candle_start_ts(exec_c)),
                            "locked_no_settled_yes": result != "no",
                        })
                    else:
                        cell["fired"] = False
                else:
                    cell["fired"] = False
            else:
                cell["fired"] = False
        rec["secondary"][str(cutoff_h)] = cell

    return rec


# ===========================================================================
# Shared stats aggregation (mirrors refined.agg_stats, generalized for either side/key-space)
# ===========================================================================

def agg_stats(fired, bad_key, n_weeks):
    pnls = [c["pnl"] for _, c in fired]
    dates = [r["date"] for r, _ in fired]
    tickers = [r["ticker"] for r, _ in fired]
    prices = [c["exec_price"] for _, c in fired]
    wins = [c["outcome"] for _, c in fired]
    fees = [c["fee"] for _, c in fired]
    bad = [(r, c) for r, c in fired if c.get(bad_key)]
    n_fired = len(fired)
    win_rate = (sum(wins) / len(wins)) if wins else None
    mean_price = (sum(prices) / len(prices)) if prices else None
    mean_fee = (sum(fees) / len(fees)) if fees else None
    cond_loss_rate = (1.0 - win_rate) if win_rate is not None else None
    worst_case_loss_rate = base.wilson_upper_bound(len(bad), n_fired, Z95) if n_fired else None
    analytic_ev_point = (win_rate - mean_price - mean_fee) if None not in (win_rate, mean_price, mean_fee) else None
    analytic_ev_worst_case = ((1.0 - worst_case_loss_rate) - mean_price - mean_fee) \
        if None not in (worst_case_loss_rate, mean_price, mean_fee) else None
    ct = base.clustered_tstat(pnls, dates)
    fillable = [(r, c) for r, c in fired if c.get("volume_5min_after", 0) > 0]
    return {
        "n_fired": n_fired,
        "fires_per_week": (n_fired / n_weeks) if n_weeks else None,
        "mean_exec_price": mean_price,
        "win_rate": win_rate,
        f"n_{bad_key}": len(bad),
        f"{bad_key}_tickers": [r["ticker"] for r, _ in bad],
        "cond_loss_rate_given_fired": cond_loss_rate,
        "worst_case_loss_rate_wilson95": worst_case_loss_rate,
        "analytic_ev_point": analytic_ev_point,
        "analytic_ev_worst_case": analytic_ev_worst_case,
        "clustered": ct,
        "worst_day": base.worst_day(pnls, dates, tickers),
        "n_fillable": len(fillable),
        "fillable_rate": (len(fillable) / n_fired) if n_fired else None,
        "median_volume_5min_after": statistics.median([c.get("volume_5min_after", 0) for _, c in fired]) if fired else None,
    }


def bonferroni_grid(cells_meta, family_alpha=0.05):
    """cells_meta: list of dicts with 'n','mean_pnl' via clustered t/p already computed.
    Same Bonferroni machinery as base.bonferroni_analysis, generalized to any pre-registered
    cell list (margin x sustain here, instead of margin x gap)."""
    family_size = len(cells_meta)
    corrected_alpha = family_alpha / family_size if family_size else family_alpha
    for c in cells_meta:
        c["p_bonferroni"] = min(1.0, c["p"] * family_size) if c.get("p") is not None else None
        c["significant_bonferroni"] = (c.get("p") is not None and c["p"] < corrected_alpha)
    return {"family_size": family_size, "alpha": family_alpha, "corrected_alpha": corrected_alpha,
            "cells": cells_meta}


def fmt(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, float) and math.isnan(x):
        return "n/a"
    return f"{x:.{nd}f}"


# ===========================================================================
# Main
# ===========================================================================

def main():
    t0 = time.time()

    # ---- TASK A ----
    task_a = task_a_investigate()

    # ---- Shared window: identical to the CONFIRMED KXHIGH baseline sample, for apples-to-
    # apples comparison (task brief explicitly asks for "the 67-day sample") ----
    base_summary_path = os.path.join(HERE, "kalshi_weather_nowcast_deep_summary.json")
    with open(base_summary_path) as f:
        kxhigh_deep = json.load(f)
    win = kxhigh_deep["window"]
    min_date = datetime.strptime(win["actual_min_date"], "%Y-%m-%d").date()
    max_date_high = datetime.strptime(win["actual_max_date"], "%Y-%m-%d").date()
    print(f"\n[shared window] Reusing the confirmed-baseline sample window: {min_date} .. "
          f"{max_date_high} ({win['actual_span_days']}d) for apples-to-apples KXLOW/KXRAIN tests.")

    # ================= TASK B-1: KXLOW =================
    print("\n[TASK B-1] Discovering KXLOW settled 'greater' markets ...")
    low_mkts = discover_low_markets(min_date)
    total_low = sum(len(v) for v in low_mkts.values())
    low_dates = [base.parse_ticker_date(m["ticker"]) for mkts in low_mkts.values() for m in mkts]
    low_dates = [d for d in low_dates if d is not None]
    low_min_date = min(low_dates) if low_dates else min_date
    low_max_date = max(low_dates) if low_dates else max_date_high
    low_span_days = (low_max_date - low_min_date).days + 1
    low_n_weeks = low_span_days / 7.0
    print(f"  KXLOW total candidate market-days: {total_low}, actual range {low_min_date}..{low_max_date} ({low_span_days}d)")

    print("[TASK B-1] Fetching/reusing cached ASOS station obs + applying glitch filter ...")
    stations = sorted(set(c["station"] for c in LOW_CITY_CONFIG.values()))
    start_dt = datetime(low_min_date.year, low_min_date.month, low_min_date.day, tzinfo=timezone.utc) - timedelta(days=1)
    end_dt = datetime(low_max_date.year, low_max_date.month, low_max_date.day, tzinfo=timezone.utc) + timedelta(days=2)
    station_series = {}
    station_cleaned = {}
    glitch_removed_total = 0
    for st in stations:
        raw = base.fetch_asos_station(st, start_dt, end_dt)
        cleaned, removed = refined.clean_station_obs(raw)
        station_series[st] = raw
        station_cleaned[st] = cleaned
        glitch_removed_total += len(removed)
        print(f"  ASOS {st}: {len(raw)} raw obs, {len(removed)} removed by glitch filter")

    print("[TASK B-1] Analyzing KXLOW market-days (margin x sustain grid + late-cutoff secondary) ...")
    low_jobs = [(series, LOW_CITY_CONFIG[series], m) for series, mkts in low_mkts.items() for m in mkts]

    def low_worker(job):
        series, cfg, m = job
        obs = station_cleaned.get(cfg["station"], [])
        try:
            return analyze_low_market_day(series, cfg, m, obs, None)
        except Exception as e:
            return {"error": f"{m.get('ticker')}: {e}"}

    low_results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(low_worker, j): j for j in low_jobs}
        for i, fut in enumerate(as_completed(futs)):
            r = fut.result()
            if r is None or "error" in r:
                continue
            low_results.append(r)
            if (i + 1) % 200 == 0:
                print(f"    processed {i+1}/{len(low_jobs)} ...")
    print(f"  KXLOW: analyzed {len(low_results)} city-days")

    # PRIMARY grid: margin x sustain, Bonferroni family (identical shape to refined.py's own
    # 12-cell KXHIGH family, same alpha, same 3 pass bars)
    low_primary_grid = {}
    cells_meta = []
    for margin in MARGINS_LOW:
        for sustain in SUSTAIN_MINUTES:
            key = f"{margin}_{sustain}"
            fired = [(r, r["primary"][key]) for r in low_results
                     if r["primary"][key].get("fired") and "pnl" in r["primary"][key]]
            s = agg_stats(fired, "locked_no_settled_yes", low_n_weeks)
            low_primary_grid[key] = s
            cells_meta.append({"margin": margin, "sustain_min": sustain, "n": s["n_fired"],
                                "mean_pnl": s["clustered"]["mean"], "t": s["clustered"]["t"],
                                "p": s["clustered"]["p"], "n_clusters": s["clustered"]["n_clusters"]})
    low_bonferroni = bonferroni_grid(cells_meta)

    # best-config selection: same 3-bar rule as base.pick_best_margin / refined.py
    survivors = []
    for c in low_bonferroni["cells"]:
        s = low_primary_grid[f"{c['margin']}_{c['sustain_min']}"]
        ok_n = s["n_fired"] >= 8
        ok_sig = bool(c["significant_bonferroni"])
        ok_tail = (s["analytic_ev_worst_case"] is not None and s["analytic_ev_worst_case"] > 0)
        cand = {**c, "win_rate": s["win_rate"], "cond_loss_rate_given_fired": s["cond_loss_rate_given_fired"],
                "worst_case_loss_rate_wilson95": s["worst_case_loss_rate_wilson95"],
                "analytic_ev_point": s["analytic_ev_point"], "analytic_ev_worst_case": s["analytic_ev_worst_case"],
                "fires_per_week": s["fires_per_week"],
                "ok_n": ok_n, "ok_bonferroni_significant": ok_sig, "ok_worst_case_ev_positive": ok_tail,
                "passes_all": ok_n and ok_sig and ok_tail}
        survivors.append(cand)
    passing = [c for c in survivors if c["passes_all"]]
    if passing:
        low_best = max(passing, key=lambda c: c["analytic_ev_worst_case"])
        low_verdict = "CONFIRMED"
    else:
        low_best = max(survivors, key=lambda c: (c["analytic_ev_worst_case"] if c["analytic_ev_worst_case"] is not None else -999))
        low_verdict = "KILLED"

    # SECONDARY (locked-YES late-cutoff comparison), reported at margin=1 for all cutoffs
    low_secondary = {}
    for cutoff_h in LOW_SECONDARY_CUTOFF_HOURS:
        key = f"1_{cutoff_h}"
        fired = [(r, r["secondary"][key]) for r in low_results
                 if r["secondary"][key].get("fired") and "pnl" in r["secondary"][key]]
        low_secondary[str(cutoff_h)] = agg_stats(fired, "locked_yes_settled_no", low_n_weeks)

    # per-city breakdown at the best config
    low_by_city = {}
    bk = f"{low_best['margin']}_{low_best['sustain_min']}"
    for series, cfg in LOW_CITY_CONFIG.items():
        city_res = [r for r in low_results if r["series"] == series]
        fired = [r for r in city_res if r["primary"][bk].get("fired") and "pnl" in r["primary"][bk]]
        bad = [r for r in fired if r["primary"][bk].get("locked_no_settled_yes")]
        low_by_city[series] = {
            "name": cfg["name"], "n_city_days": len(city_res), "fired": len(fired),
            "win_rate": (sum(r["primary"][bk]["outcome"] for r in fired) / len(fired)) if fired else None,
            "mean_pnl": (sum(r["primary"][bk]["pnl"] for r in fired) / len(fired)) if fired else None,
            "n_settled_wrong_way": len(bad),
        }

    low_summary = {
        "window": {"min_date": low_min_date.isoformat(), "max_date": low_max_date.isoformat(),
                    "span_days": low_span_days, "n_weeks": low_n_weeks},
        "n_series": len(LOW_CITY_CONFIG), "n_city_days_analyzed": len(low_results),
        "glitch_removed_total_obs": glitch_removed_total,
        "primary_grid": low_primary_grid, "bonferroni": low_bonferroni,
        "best_config": {"verdict": low_verdict, "chosen": low_best, "candidates": survivors},
        "secondary_by_cutoff": low_secondary,
        "by_city_at_best": low_by_city,
    }

    # ================= TASK B-2: KXRAINNYC =================
    print("\n[TASK B-2] Discovering KXRAINNYC settled 'greater' markets ...")
    rain_mkts = discover_rain_markets(min_date)
    rain_list = rain_mkts.get("KXRAINNYC", [])
    rain_dates = [base.parse_ticker_date(m["ticker"]) for m in rain_list]
    rain_dates = [d for d in rain_dates if d is not None]
    rain_min_date = min(rain_dates) if rain_dates else min_date
    rain_max_date = max(rain_dates) if rain_dates else max_date_high
    rain_span_days = (rain_max_date - rain_min_date).days + 1
    rain_n_weeks = rain_span_days / 7.0
    print(f"  KXRAINNYC: {len(rain_list)} settled markets, {rain_min_date}..{rain_max_date} ({rain_span_days}d)")

    print("[TASK B-2] Fetching 1-min precip obs for NYC (Central Park) ...")
    p_start = datetime(rain_min_date.year, rain_min_date.month, rain_min_date.day, tzinfo=timezone.utc) - timedelta(days=1)
    p_end = datetime(rain_max_date.year, rain_max_date.month, rain_max_date.day, tzinfo=timezone.utc) + timedelta(days=2)
    precip_obs = fetch_precip_station("NYC", p_start, p_end)
    print(f"  NYC precip obs: {len(precip_obs)} 1-min readings")

    rain_results = []
    for m in rain_list:
        try:
            r = analyze_rain_market_day("KXRAINNYC", RAIN_CITY_CONFIG["KXRAINNYC"], m, precip_obs)
        except Exception as e:
            r = None
            print(f"  [warn] {m.get('ticker')}: {e}", file=sys.stderr)
        if r is not None:
            rain_results.append(r)
    print(f"  KXRAINNYC: analyzed {len(rain_results)} market-days")

    rain_primary = {}
    for sustain in [1, 2, 3]:
        key = str(sustain)
        fired = [(r, r["primary"][key]) for r in rain_results
                 if r["primary"][key].get("fired") and "pnl" in r["primary"][key]]
        rain_primary[key] = agg_stats(fired, "locked_yes_settled_no", rain_n_weeks)

    rain_secondary = {}
    for cutoff_h in RAIN_SECONDARY_CUTOFF_HOURS:
        key = str(cutoff_h)
        fired = [(r, r["secondary"][key]) for r in rain_results
                 if r["secondary"][key].get("fired") and "pnl" in r["secondary"][key]]
        rain_secondary[key] = agg_stats(fired, "locked_no_settled_yes", rain_n_weeks)

    asos_cli_agree = sum(1 for r in rain_results if r["asos_vs_strike_yes"] == r["official_yes"])
    rain_disagree = [r for r in rain_results if r["asos_vs_strike_yes"] != r["official_yes"]]

    # simple Bonferroni over the 3-cell sustain family (primary) -- small family, still
    # correction-honest rather than reporting only sustain=1
    rain_cells_meta = []
    for sustain in [1, 2, 3]:
        s = rain_primary[str(sustain)]
        rain_cells_meta.append({"sustain_min": sustain, "n": s["n_fired"], "mean_pnl": s["clustered"]["mean"],
                                 "t": s["clustered"]["t"], "p": s["clustered"]["p"],
                                 "n_clusters": s["clustered"]["n_clusters"]})
    rain_bonferroni = bonferroni_grid(rain_cells_meta)

    rain_survivors = []
    for c in rain_bonferroni["cells"]:
        s = rain_primary[str(c["sustain_min"])]
        ok_n = s["n_fired"] >= 8
        ok_sig = bool(c["significant_bonferroni"])
        ok_tail = (s["analytic_ev_worst_case"] is not None and s["analytic_ev_worst_case"] > 0)
        rain_survivors.append({**c, "win_rate": s["win_rate"], "analytic_ev_worst_case": s["analytic_ev_worst_case"],
                                "fires_per_week": s["fires_per_week"], "ok_n": ok_n,
                                "ok_bonferroni_significant": ok_sig, "ok_worst_case_ev_positive": ok_tail,
                                "passes_all": ok_n and ok_sig and ok_tail})
    rain_passing = [c for c in rain_survivors if c["passes_all"]]
    if rain_passing:
        rain_best = max(rain_passing, key=lambda c: c["analytic_ev_worst_case"])
        rain_verdict = "CONFIRMED"
    else:
        rain_best = max(rain_survivors, key=lambda c: (c["analytic_ev_worst_case"] if c["analytic_ev_worst_case"] is not None else -999))
        rain_verdict = "KILLED"

    # KXRAIN multi-city feasibility note (not backtested -- too new)
    rain_multi_merged, rain_multi_dated = discover_series_full_history(KXRAIN_MULTICITY_TICKER)
    rain_multi_dates = sorted(set(d for d, _ in rain_multi_dated))

    rain_summary = {
        "window": {"min_date": rain_min_date.isoformat(), "max_date": rain_max_date.isoformat(),
                    "span_days": rain_span_days, "n_weeks": rain_n_weeks},
        "n_city_days_analyzed": len(rain_results),
        "asos_vs_official": {"agree": asos_cli_agree, "agree_rate": asos_cli_agree / len(rain_results) if rain_results else None,
                              "disagree_n": len(rain_disagree),
                              "disagree_examples": [{"ticker": r["ticker"], "date": r["date"],
                                                      "asos_cum_precip": r["full_day_cum_precip"],
                                                      "official_result": r["result"]} for r in rain_disagree[:10]]},
        "primary_by_sustain": rain_primary, "secondary_by_cutoff": rain_secondary,
        "bonferroni": rain_bonferroni,
        "best_config": {"verdict": rain_verdict, "chosen": rain_best, "candidates": rain_survivors},
        "kxrain_multicity_feasibility": {
            "ticker": KXRAIN_MULTICITY_TICKER, "n_settled": len(rain_multi_merged),
            "unique_dates": [d.isoformat() for d in rain_multi_dates],
            "note": "Same 'greater than 0 inches -> locked YES on first measurable precip' "
                    "mechanic as KXRAINNYC, one sub-market per city per day -- structurally "
                    "identical, but this series only has settled history for a single "
                    "calendar date in this environment (too new to backtest; revisit once "
                    "several weeks of history accumulate).",
        },
    }

    # ================= Capacity roll-up =================
    kxhigh_best = kxhigh_deep["best_margin"]["chosen"]
    # prefer the refined confirmed config's numbers if available (matches the task's own
    # "+0.34/ct, 4.4 fires/week" framing) over the deep-history baseline's margin=2 numbers
    refined_summary_path = os.path.join(HERE, "kalshi_weather_refined_summary.json")
    kxhigh_refined_best_fires_wk = None
    kxhigh_refined_best_pnl = None
    if os.path.exists(refined_summary_path):
        with open(refined_summary_path) as f:
            kxhigh_refined = json.load(f)
        bs = kxhigh_refined["marginal_effects"]["best_structural"]
        kxhigh_refined_best_fires_wk = bs["fires_per_week"]
        kxhigh_refined_best_pnl = bs["mean_pnl"]

    capacity = {
        "KXHIGH_confirmed_baseline_fires_per_week": kxhigh_refined_best_fires_wk or kxhigh_best["fires_per_week"],
        "KXLOW_best_config_fires_per_week": low_best["fires_per_week"],
        "KXLOW_verdict": low_verdict,
        "KXRAINNYC_best_config_fires_per_week": rain_best["fires_per_week"],
        "KXRAINNYC_verdict": rain_verdict,
    }
    added = 0.0
    if low_verdict == "CONFIRMED" and low_best["fires_per_week"]:
        added += low_best["fires_per_week"]
    if rain_verdict == "CONFIRMED" and rain_best["fires_per_week"]:
        added += rain_best["fires_per_week"]
    base_fires = capacity["KXHIGH_confirmed_baseline_fires_per_week"] or 0.0
    capacity["total_fires_per_week_all_confirmed_types"] = base_fires + added
    capacity["pct_increase_vs_kxhigh_only"] = (added / base_fires * 100.0) if base_fires else None

    summary = {
        "task_a": task_a,
        "task_b_kxlow": low_summary,
        "task_b_kxrain": rain_summary,
        "capacity_rollup": capacity,
        "other_candidates_scanned_not_backtested": {
            "KXHIGHUS / HIGHUS": "National daily high (highest temp anywhere in the US that "
                "day). Same ratchet-up structural mechanic in principle, but the observable "
                "is a MAX ACROSS ~20+ independently-reporting stations nationwide, not a "
                "single station -- station selection, missing-station handling, and the "
                "'which station is currently hottest' bookkeeping is materially more complex "
                "and error-prone than a single-city read. Flagged as the most promising 'other' "
                "candidate for a dedicated follow-up, not attempted here.",
            "KXCITIESWEATHER": "Highest temperature in cities (daily) -- appears to be an "
                "index/composite across the same city list; same complexity note as KXHIGHUS.",
            "KXDVHIGH": "Death Valley daily high temp -- structurally identical single-station "
                "KXHIGH-style market, not fundamentally new; would need its own ASOS station "
                "mapping (Death Valley is not a standard first-order ASOS site) and was not "
                "worth a special-case build for one extra city.",
            "KXAQICITY": "AQI in city at time (custom) -- plausibly has a similar 'observed "
                "value already exceeds threshold' lock, but AQI is a computed/reported index, "
                "not a raw physical obs with a comparable free high-frequency feed; not "
                "checked for a matching real-time-safe data source.",
            "KXHIGHNYD": "Hourly Directional NYC Temperature -- different mechanic entirely "
                "(next-hour up/down direction bet), not a settlement-lock nowcast; out of scope.",
        },
    }

    with open(OUT_SUMMARY, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    write_report(summary, kxhigh_deep, kxhigh_refined if os.path.exists(refined_summary_path) else None)

    print(f"\nDone in {time.time()-t0:.1f}s")
    print(f"  {OUT_SUMMARY}")
    print(f"  {OUT_REPORT}")


def write_report(summary, kxhigh_deep, kxhigh_refined):
    L = []
    L.append("# Kalshi Weather Nowcast Edge -- EXPANSION (Task A: history depth / Task B: more market types)\n")

    # ---------------- TASK A ----------------
    L.append("## Task A -- is longer backtest history obtainable?\n")
    ta = summary["task_a"]
    L.append(f"**BLUNT VERDICT: YES.** The 67-day floor in `kalshi_weather_nowcast.py` was an "
             f"artifact of using Kalshi's LIVE `/markets` endpoint, which silently drops "
             f"settled markets older than a moving cutoff (`GET /historical/cutoff` -> "
             f"`{ta['historical_cutoff']}` as of this run). Kalshi's own "
             f"`GET /historical/markets` / `/historical/markets/{{ticker}}/candlesticks` / "
             f"`/historical/trades` endpoints (same cursor pagination, no auth, free) serve "
             f"the FULL record for markets settled before that cutoff -- verified directly, "
             f"not assumed.\n")

    v = ta.get("historical_endpoint_verification", {})
    if v:
        L.append(f"**Verification:** `{v.get('probe_ticker')}` (a pre-\"KX\"-rename ticker) "
                 f"returned **{v.get('n_candlesticks_returned')}** 1-min candlesticks and "
                 f"**{v.get('n_trades_sample_returned')}** sample trades from `/historical/*` "
                 f"-- i.e. real price/trade data, not just market metadata, for a market from "
                 f"the `{v.get('probe_series')}` series' earliest era.\n")

    ad = ta.get("asos_depth_spotcheck", {})
    if ad:
        L.append("**ASOS-side depth (the other half of \"obtainable\"):**\n")
        for st, d in ad.items():
            L.append(f"- {st} @ {d['probe_date']}: {d['n_obs_returned_2hr_window']} 1-min obs "
                     f"in a 2-hour window (should be ~120 if truly minute-resolution that far "
                     f"back -- confirms IEM's free archive is not the constraint).")
        L.append("")

    L.append("### Per-series TRUE floor (deep-paginated `/historical/markets`, not assumed)\n")
    L.append("| series | settled markets (all-time) | unique dates | floor date | ceiling date | true history (days) |")
    L.append("|---|---|---|---|---|---|")
    per_series = ta["per_series_true_depth"]
    for s, d in sorted(per_series.items(), key=lambda kv: kv[1].get("floor_date") or "9999"):
        if "error" in d:
            L.append(f"| {s} | ERROR: {d['error']} | | | | |")
            continue
        L.append(f"| {s} | {d['n_settled_total']} | {d['n_unique_dates']} | {d['floor_date']} | "
                 f"{d['ceiling_date']} | {d['true_history_days']} |")
    L.append("\nKey pattern: **KXHIGH's floor varies by city** (KXHIGHNY/KXHIGHCHI back to "
             "2021-08; KXHIGHMIA to 2023-05; KXHIGHDEN to 2024-11; KXHIGHLAX to 2025-01 -- "
             "i.e. real, staggered per-city product launches, not a single 'all weather "
             "markets are new' story). **KXLOW's floor is uniform and recent across every "
             "city** (2025-12-13) -- the LOW-temp product itself is genuinely new (~7 months "
             "old as of this run), independent of the HIGH product's age. This matters "
             "directly for Task B: KXLOW cannot get a multi-year backtest no matter which "
             "endpoint is used, because the product itself hasn't existed that long -- but it "
             "already has ~3x the 67-day sample available if extended (not done in this run; "
             "see caveat below).\n")

    L.append("### Third-party archives (checked read-only, not downloaded)\n")
    for name, d in ta["third_party_archives"].items():
        L.append(f"- **{name}** ({d['url']}): {d['finding']}")
    L.append("")

    L.append("### Why this script does NOT simply re-run the full multi-year backtest\n")
    L.append("Obtainability is now demonstrated, not just claimed -- but pulling ~4.5 years x "
             "20 cities of 1-min Kalshi candlesticks AND matching 1-min ASOS obs (the KXHIGHNY/"
             "KXHIGHCHI floor alone implies roughly 25-30x the request volume of the current "
             "67-day cache) is a substantial, separate data-engineering effort with its own "
             "rate-limit/runtime budget, and is out of scope for this expansion task, which is "
             "specifically about (a) confirming the ceiling is not real and (b) growing volume "
             "via more market TYPES on the EXISTING sample. **Recommended next step, not done "
             "here:** point `kalshi_weather_nowcast.py`'s market-discovery step at "
             "`discover_series_full_history()` (implemented in this file) instead of live-only "
             "`/markets`, per-city, starting with KXHIGHNY/KXHIGHCHI (deepest floors, most "
             "value per request) before the newer-launched cities.\n")

    # ---------------- TASK B ----------------
    L.append("\n## Task B -- expanding volume via more market types\n")
    L.append(f"Shared sample window (matches the confirmed KXHIGH baseline exactly): "
             f"**{kxhigh_deep['window']['actual_min_date']} to "
             f"{kxhigh_deep['window']['actual_max_date']}** "
             f"({kxhigh_deep['window']['actual_span_days']} days).\n")

    # ---- KXLOW ----
    lw = summary["task_b_kxlow"]
    L.append("### B-1. KXLOW (daily low temperature) -- PRIMARY: instant sustained-below-strike cross, buy NO\n")
    L.append(f"20 KXLOWT<city> series (1:1 mirror of the KXHIGH city list, verified live -- "
             f"the un-prefixed guesses like KXLOWMIA/KXLOWDEN/KXLOWNY have zero settled "
             f"markets, same dead-legacy-ticker pattern as HIGHNY/HIGHAUS/etc). "
             f"{lw['n_city_days_analyzed']} city-days analyzed over "
             f"{lw['window']['span_days']} days ({glitch_note(lw)}).\n")

    L.append("Margin x sustain grid (identical family to the confirmed KXHIGH refinement, "
             f"{lw['bonferroni']['family_size']}-cell Bonferroni family, corrected alpha = "
             f"{fmt(lw['bonferroni']['corrected_alpha'],5)}):\n")
    L.append("| margin | sustain | n fired | win rate | mean PnL/ct | t | p (Bonferroni) | "
             "worst-case loss rate | worst-case EV | fires/wk | **passes bar** |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for c in lw["best_config"]["candidates"]:
        L.append(f"| {c['margin']} | {c['sustain_min']} | {c['n']} | {fmt(c['win_rate'],3)} | "
                 f"{fmt(c['mean_pnl'])} | {fmt(c['t'],2)} | {fmt(c['p_bonferroni'],4)} | "
                 f"{fmt(c['worst_case_loss_rate_wilson95'],3)} | {fmt(c['analytic_ev_worst_case'])} | "
                 f"{fmt(c['fires_per_week'],2)} | {'**YES**' if c['passes_all'] else 'no'} |")
    bc = lw["best_config"]["chosen"]
    L.append(f"\n**KXLOW best config: margin={bc['margin']}F, sustain={bc['sustain_min']}min. "
             f"Verdict: {lw['best_config']['verdict']}.** n={bc['n']}, win rate "
             f"{fmt(bc['win_rate'],3)}, mean PnL {fmt(bc['mean_pnl'])}, t={fmt(bc['t'],2)}, "
             f"worst-case EV={fmt(bc['analytic_ev_worst_case'])}, "
             f"fires/week={fmt(bc['fires_per_week'],2)}.\n")

    L.append("Per-city breakdown at the best config:\n")
    L.append("| series | city | city-days | fired | win rate | mean PnL | settled wrong way |")
    L.append("|---|---|---|---|---|---|---|")
    for series, c in sorted(lw["by_city_at_best"].items(), key=lambda kv: -(kv[1]["fired"] or 0)):
        if c["fired"] == 0:
            continue
        L.append(f"| {series} | {c['name']} | {c['n_city_days']} | {c['fired']} | "
                 f"{fmt(c['win_rate'],3)} | {fmt(c['mean_pnl'])} | {c['n_settled_wrong_way']} |")

    L.append("\nSECONDARY (locked-YES, late-cutoff comparison, margin=1F -- mirrors the "
             "original KXHIGH SHORT side, not expected to be the strong edge):\n")
    L.append("| cutoff (LST hr) | fired | win rate | mean PnL | t | fillable rate |")
    L.append("|---|---|---|---|---|---|")
    for h in LOW_SECONDARY_CUTOFF_HOURS:
        s = lw["secondary_by_cutoff"][str(h)]
        L.append(f"| {h}:00 | {s['n_fired']} | {fmt(s['win_rate'],3)} | {fmt(s['clustered']['mean'])} | "
                 f"{fmt(s['clustered']['t'],2)} | {fmt(s['fillable_rate'],3)} |")

    # ---- KXRAIN ----
    rn = summary["task_b_kxrain"]
    L.append("\n### B-2. KXRAINNYC (daily rain, NYC) -- PRIMARY: first sustained measurable precip, buy YES\n")
    L.append(f"Only Kalshi daily single-city rain series with real settled history in this "
             f"environment ({rn['n_city_days_analyzed']} days over {rn['window']['span_days']} "
             f"calendar days). Multi-city `KXRAIN` launched too recently to backtest -- see note below.\n")
    a = rn["asos_vs_official"]
    L.append(f"ASOS(1-min cumulative precip > {RAIN_EPS_IN}in) vs official Kalshi result, "
             f"UNCONDITIONAL agreement: **{fmt(a['agree_rate'],3)}** ({a['disagree_n']}/"
             f"{rn['n_city_days_analyzed']} disagree) -- this is the honest tail-risk source "
             f"for rain (station siting / trace-precip settlement rules vs raw ASOS reading).\n")

    L.append("| sustain (min) | n fired | win rate | mean PnL/ct | t | p (Bonferroni) | worst-case EV | fires/wk | **passes bar** |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for c in rn["best_config"]["candidates"]:
        s = rn["primary_by_sustain"][str(c["sustain_min"])]
        L.append(f"| {c['sustain_min']} | {c['n']} | {fmt(c['win_rate'],3)} | {fmt(c['mean_pnl'])} | "
                 f"{fmt(c['t'],2)} | {fmt(c.get('p_bonferroni'),4)} | {fmt(c['analytic_ev_worst_case'])} | "
                 f"{fmt(c['fires_per_week'],2)} | {'**YES**' if c['passes_all'] else 'no'} |")
    rb = rn["best_config"]["chosen"]
    L.append(f"\n**KXRAINNYC best config: sustain={rb['sustain_min']}min. Verdict: "
             f"{rn['best_config']['verdict']}.** n={rb['n']}, win rate {fmt(rb['win_rate'],3)}, "
             f"t={fmt(rb['t'],2)}, worst-case EV={fmt(rb['analytic_ev_worst_case'])}, "
             f"fires/week={fmt(rb['fires_per_week'],2)}.\n")

    L.append("SECONDARY (locked-NO, late-cutoff, still bone dry):\n")
    L.append("| cutoff (LST hr) | fired | win rate | mean PnL | t |")
    L.append("|---|---|---|---|---|")
    for h in RAIN_SECONDARY_CUTOFF_HOURS:
        s = rn["secondary_by_cutoff"][str(h)]
        L.append(f"| {h}:00 | {s['n_fired']} | {fmt(s['win_rate'],3)} | {fmt(s['clustered']['mean'])} | "
                 f"{fmt(s['clustered']['t'],2)} |")

    km = rn["kxrain_multicity_feasibility"]
    L.append(f"\n**KXRAIN (multi-city) feasibility:** structurally identical mechanic, "
             f"{km['n_settled']} settled sub-markets across {len(km['unique_dates'])} unique "
             f"calendar date(s) in this environment. {km['note']}\n")

    # ---- other candidates ----
    L.append("\n### B-3. Other Kalshi weather series scanned (not backtested)\n")
    for name, note in summary["other_candidates_scanned_not_backtested"].items():
        L.append(f"- **{name}**: {note}")

    # ---- capacity rollup ----
    L.append("\n## Capacity roll-up: total expanded volume vs KXHIGH-only\n")
    cap = summary["capacity_rollup"]
    L.append("| market type | verdict | fires/week |")
    L.append("|---|---|---|")
    L.append(f"| KXHIGH (confirmed baseline, margin=1F/sustain=3min glitch-filtered) | CONFIRMED | "
             f"{fmt(cap['KXHIGH_confirmed_baseline_fires_per_week'],2)} |")
    L.append(f"| KXLOW (best config) | {cap['KXLOW_verdict']} | {fmt(cap['KXLOW_best_config_fires_per_week'],2)} |")
    L.append(f"| KXRAINNYC (best config) | {cap['KXRAINNYC_verdict']} | "
             f"{fmt(cap['KXRAINNYC_best_config_fires_per_week'],2)} |")
    L.append(f"\n**Total fires/week across all CONFIRMED market types: "
             f"{fmt(cap['total_fires_per_week_all_confirmed_types'],2)}** "
             f"({'+' if cap['pct_increase_vs_kxhigh_only'] else ''}"
             f"{fmt(cap['pct_increase_vs_kxhigh_only'],1)}% vs KXHIGH-only, counting only "
             f"types that independently clear the same n>=8 / Bonferroni-significant / "
             f"worst-case-EV-positive bar the KXHIGH baseline had to clear).\n")

    L.append("\n## Bottom line\n")
    L.append(f"**Task A: YES, longer history is obtainable, for free, from Kalshi itself** "
             f"(`/historical/*` endpoints) -- the 67-day sample was a live-API-window "
             f"artifact, not a real ceiling. Depth varies genuinely by product/city (KXHIGH "
             f"NY/CHI: ~4.9yr; other KXHIGH cities: 8mo-3yr depending on launch; KXLOW: ~7mo "
             f"everywhere, a real product-age constraint no endpoint can fix). Not re-run at "
             f"full depth here (scope/runtime); the mechanism to do so is implemented and "
             f"tested in this file (`discover_series_full_history`).\n")
    L.append(f"**Task B: KXLOW verdict = {lw['best_config']['verdict']}"
             f"{' -- adds a genuine, independently-confirmed sleeve of capacity' if lw['best_config']['verdict']=='CONFIRMED' else ' -- does not clear the same bar the KXHIGH baseline had to clear on this sample'}. "
             f"KXRAINNYC verdict = {rn['best_config']['verdict']}"
             f"{' -- adds capacity' if rn['best_config']['verdict']=='CONFIRMED' else ' -- does not clear the bar (single city, thinner sample, honest tail from settlement-rule vs raw-ASOS disagreement)'}. "
             f"Total confirmed capacity: {fmt(cap['total_fires_per_week_all_confirmed_types'],2)} fires/week "
             f"vs {fmt(cap['KXHIGH_confirmed_baseline_fires_per_week'],2)} for KXHIGH alone.**\n")

    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(L) + "\n")


def glitch_note(lw):
    return f"{lw['glitch_removed_total_obs']} obs removed by the glitch filter across all stations"


if __name__ == "__main__":
    main()
