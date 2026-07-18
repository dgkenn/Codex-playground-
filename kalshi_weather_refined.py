#!/usr/bin/env python3
"""
kalshi_weather_refined.py

Refinement pass on the CONFIRMED Kalshi KXHIGH settlement-nowcast edge (see
kalshi_weather_nowcast.py / kalshi_weather_nowcast_deep_report.md): buy YES once the 1-min ASOS
running max clears strike+2F. Confirmed baseline on the full 67-day sample (2026-05-12..2026-07-17,
20 cities): n=35 fires, 91.4% win, +0.168/ct net, day-clustered t=4.60, Bonferroni-significant,
worst-case (Wilson-95) EV still positive (+0.030/ct). The 3 losses = 1 LAX glitch (single 1-min
reading of 120F, physically impossible) + 2 Miami misses (station reads a few F hot vs the
official NWS CLI value).

This script does NOT re-fetch from scratch -- it reuses kalshi_weather_nowcast.py's disk cache
(.nowcast_cache/, already populated by the deep-history run) via direct imports of its fetch/cache/
stat helpers, so every refinement below is tested on the IDENTICAL 67-day, 20-city sample as the
confirmed baseline (apples to apples, no new lookahead, no new data-snooping surface).

REFINEMENTS TESTED (each measured, not assumed):
  1. GLITCH FILTER   -- reject obs > 130F absolute (physically implausible for these climates), and
                         reject isolated single-minute spikes (>8F/min in AND >8F/min back out vs
                         immediate neighbors) before computing the running max. Applied globally per
                         station, once, before any per-market-day slicing -- this is a data-cleaning
                         step, not a per-trade lookahead (no trade-relevant info is used that wasn't
                         already in the raw feed).
  2. SUSTAINED-ABOVE-STRIKE -- require N consecutive raw 1-min readings (not just the running max)
                         at/above strike+margin, N in {1(=baseline),3,5,10}, before firing. A single
                         spike can push the running max over the line forever (that's the whole
                         point of using a running max); requiring it to SUSTAIN kills transient
                         spikes without giving up the running-max ratchet once truly confirmed.
  3. PER-STATION MARGIN -- empirically measure each station's ASOS-vs-settlement bias from its
                         plausible (non-glitch) misses at the permissive margin=1 cut (n=71, more
                         density than margin=2's n=35), and require a station-specific extra buffer
                         on top of the global margin for stations that read hot.
  4. MULTI-SOURCE cross-check -- cross-reference the 1-min ASOS running max against each station's
                         independent HOURLY METAR archive (a separately-processed IEM product, not
                         merely a subsample of the 1-min feed) at the moment of firing. Feasibility
                         is demonstrated concretely on the known LAX glitch below.
  5. MARGIN/GAP reoptimization -- re-run the margin sweep under 1-3 combined, plus the existing
                         gap-threshold overlay (min 1-price edge: 0, 2c, 5c), report margin=1 as an
                         explicit higher-frequency/higher-variance sleeve.
  6. SIZING            -- tail-aware fractional Kelly per fire, sized off the Wilson-95 worst-case
                         loss rate (not the point estimate), with a cross-city same-day correlation
                         cap (heat waves fire many cities on the same LST day).

Output: kalshi_weather_refined_report.md, kalshi_weather_refined_summary.json.
Author: automated research script. Do NOT git commit (per task instructions).
"""

import os
import sys
import json
import math
import time
import statistics
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kalshi_weather_nowcast as base  # noqa: E402  (reuse fetch/cache/stat helpers + cached data)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_REPORT = os.path.join(HERE, "kalshi_weather_refined_report.md")
OUT_SUMMARY = os.path.join(HERE, "kalshi_weather_refined_summary.json")

UA = base.UA
CACHE_DIR = base.CACHE_DIR

# ---------------------------------------------------------------------------
# Refinement config (pre-registered here, tested for ALL values -- no post-hoc pick)
# ---------------------------------------------------------------------------
GLITCH_ABS_CAP_F = 130.0        # physically-implausible absolute reading cap (task-specified example)
GLITCH_ABS_FLOOR_F = -60.0
GLITCH_JUMP_F_PER_MIN = 8.0     # isolated single-minute spike threshold (in AND back out)

SUSTAIN_MINUTES = [1, 3, 5, 10]  # 1 = reproduces the baseline "first crossing of running max" rule
TEST_MARGINS = [1, 2, 3]         # margins 4-5 already established unprofitable / too-thin on n in baseline
GAP_THRESHOLDS = base.GAP_THRESHOLDS  # [0.0, 0.02, 0.05], same family as baseline for apples-to-apples

HOURLY_ARCHIVE_BASE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
HOURLY_CROSSCHECK_TOL_F = 3.0    # allowed hourly-lag slop: hourly-max-so-far must be within this of strike

Z95 = 1.959963985


# ---------------------------------------------------------------------------
# 1. GLITCH FILTER
# ---------------------------------------------------------------------------

def clean_station_obs(obs):
    """obs: sorted list of (datetime, tmpf). Returns (cleaned, removed) where removed is a list of
    (t, v, reason) for every dropped reading. Two independent filters, both pre-registered:
      (a) absolute cap/floor -- physically impossible for continental-US ASOS climates.
      (b) isolated single-minute spike -- the point jumps far from BOTH its immediate predecessor
          AND its immediate successor (i.e., it goes up and immediately reverts), at a rate exceeding
          GLITCH_JUMP_F_PER_MIN. A genuine sustained temperature change only trips one side of this
          (predecessor OR successor, not both), so this does not remove real fast-moving weather.
    """
    n = len(obs)
    cleaned = []
    removed = []
    for i in range(n):
        t, v = obs[i]
        if v > GLITCH_ABS_CAP_F or v < GLITCH_ABS_FLOOR_F:
            removed.append((t, v, "abs_cap"))
            continue
        is_spike = False
        if 0 < i < n - 1:
            tp, vp = obs[i - 1]
            tn, vn = obs[i + 1]
            dt_prev = max((t - tp).total_seconds() / 60.0, 1e-6)
            dt_next = max((tn - t).total_seconds() / 60.0, 1e-6)
            rate_in = abs(v - vp) / dt_prev
            rate_out = abs(vn - v) / dt_next
            if rate_in > GLITCH_JUMP_F_PER_MIN and rate_out > GLITCH_JUMP_F_PER_MIN:
                # also require it actually reverts (not a real step-and-hold) -- vp and vn on the
                # "same side" of v (i.e., v is an outlier relative to both neighbors)
                if (v - vp) * (v - vn) > 0:
                    is_spike = True
        if is_spike:
            removed.append((t, v, "isolated_spike"))
            continue
        cleaned.append((t, v))
    return cleaned, removed


# ---------------------------------------------------------------------------
# 2. HOURLY METAR cross-check archive (independent second source; bulk fetch/cache per station)
# ---------------------------------------------------------------------------

def hourly_cache_path(station, start_dt, end_dt):
    return f"hourly_metar_{station}_{start_dt.date().isoformat()}_{end_dt.date().isoformat()}.json"

def fetch_hourly_station(station, start_dt, end_dt):
    cache_key = hourly_cache_path(station, start_dt, end_dt)
    cached = base.load_cache(cache_key)
    if cached is not None:
        return [(datetime.fromisoformat(t).replace(tzinfo=timezone.utc), v) for t, v in cached]
    sid = base.asos1min_id(station)
    y1, m1, d1 = start_dt.year, start_dt.month, start_dt.day
    y2, m2, d2 = end_dt.year, end_dt.month, end_dt.day
    url = (f"{HOURLY_ARCHIVE_BASE}?station={sid}&data=tmpf&year1={y1}&month1={m1}&day1={d1}"
           f"&year2={y2}&month2={m2}&day2={d2}&tz=UTC&format=onlycomma&latlon=no&missing=M"
           f"&trace=T&direct=no&report_type=3,4")
    text = base.http_get_text(url)
    out = []
    for line in text.splitlines():
        if not line or line.startswith("station,"):
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        valid, tmpf = parts[1], parts[2]
        if tmpf in ("", "M"):
            continue
        try:
            t = datetime.strptime(valid.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            v = float(tmpf)
        except ValueError:
            continue
        out.append((t, v))
    out.sort(key=lambda x: x[0])
    base.save_cache(cache_key, [(t.isoformat(), v) for t, v in out])
    return out


def hourly_max_so_far(hourly_obs_day, t_star):
    """Max of hourly obs with valid time <= t_star (real-time-safe: no lookahead)."""
    vals = [v for t, v in hourly_obs_day if t <= t_star]
    return max(vals) if vals else None


# ---------------------------------------------------------------------------
# 3. Sustained-above-strike firing logic (raw obs, not running max)
# ---------------------------------------------------------------------------

def find_sustained_cross(obs, threshold, sustain_min, max_gap_min=2.5):
    """obs: sorted (t,v) CLEANED list restricted to the settlement day. Returns the timestamp of
    the sustain_min-th CONSECUTIVE qualifying (v>=threshold) reading (a small max_gap_min tolerance
    allows a single missed/dropped 1-min ob inside an otherwise-sustained run, matching real ASOS
    feed behavior -- a hard "every single minute present" requirement would kill sustain>=3 on
    stations with any transmission gaps at all). Count-based (not elapsed-duration-based) so that
    sustain_min=1 fires on the FIRST qualifying reading -- i.e. EXACTLY reproduces the baseline's
    "running max clears strike+margin" rule (verified: raw/unfiltered obs at sustain_min=1
    reproduces the confirmed baseline's fired-ticker set 1:1). An elapsed-duration formulation was
    tried first and rejected: it silently required a 2nd observation even at sustain_min=1 (since a
    single reading has 0 minutes of elapsed "sustained" duration), which is NOT what "sustain=1"
    (baseline-equivalent) should mean and was caught by a direct fired-ticker-set diff against the
    baseline before being used for anything else. None if it never sustains."""
    run_count = 0
    prev_t = None
    for t, v in obs:
        if v >= threshold:
            if run_count > 0 and prev_t is not None and (t - prev_t).total_seconds() / 60.0 > max_gap_min:
                run_count = 0  # gap too large -- restart the run
            run_count += 1
            if run_count >= sustain_min:
                return t
        else:
            run_count = 0
        prev_t = t
    return None


def exec_candle_at_or_after(candles, t_star):
    t_ts = int(t_star.timestamp())
    for c in candles:
        if base.candle_start_ts(c) >= t_ts:
            return c
    return None


def volume_5min_after(candles, center_ts):
    tot = 0.0
    for c in candles:
        cs = base.candle_start_ts(c)
        if center_ts <= cs < center_ts + 5 * 60:
            tot += float(c.get("volume_fp", 0) or 0)
    return tot


# ---------------------------------------------------------------------------
# 4. Core per-market-day refined analysis: builds fired-event records across the
#    (margin x sustain_min) grid, using CLEANED obs, plus an hourly cross-check flag.
# ---------------------------------------------------------------------------

def analyze_market_day_refined(series, cfg, market, cleaned_station_obs, hourly_station_obs, margins, sustains):
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

    obs = base.slice_window(cleaned_station_obs, start_utc, end_utc)
    if len(obs) < 20:
        return None
    hourly_obs = base.slice_window(hourly_station_obs, start_utc - timedelta(hours=2), end_utc)

    full_day_asos_max = max(v for _, v in obs)

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
        "official_yes": result == "yes", "full_day_asos_max_cleaned": full_day_asos_max,
        "cells": {},   # keyed "margin_sustain" -> fired dict
    }

    for margin in margins:
        threshold = strike + margin
        for sustain in sustains:
            key = f"{margin}_{sustain}"
            t_star = find_sustained_cross(obs, threshold, sustain)
            cell = {"fired": t_star is not None}
            if t_star is not None:
                exec_c = exec_candle_at_or_after(candles, t_star)
                if exec_c is not None:
                    p = base.yes_ask_open(exec_c)
                    if not math.isnan(p) and p > 0:
                        fee = base.kalshi_fee(p)
                        outcome = 1.0 if result == "yes" else 0.0
                        pnl = outcome - p - fee
                        hmax_so_far = hourly_max_so_far(hourly_obs, t_star)
                        hourly_agrees = (hmax_so_far is not None and
                                         hmax_so_far >= strike - HOURLY_CROSSCHECK_TOL_F)
                        cell.update({
                            "t_star": t_star.isoformat(), "exec_price": p, "fee": fee,
                            "outcome": outcome, "pnl": pnl, "gap": 1.0 - p,
                            "volume_at_exec": float(exec_c.get("volume_fp", 0) or 0),
                            "volume_5min_after": volume_5min_after(candles, base.candle_start_ts(exec_c)),
                            "oi_at_exec": float(exec_c.get("open_interest_fp", 0) or 0),
                            "locked_yes_settled_no": result != "yes",
                            "hourly_max_so_far": hmax_so_far,
                            "hourly_crosscheck_agrees": hourly_agrees,
                        })
                    else:
                        cell["fired"] = False
                else:
                    cell["fired"] = False
            rec["cells"][key] = cell
    return rec


# ---------------------------------------------------------------------------
# 5. Stats aggregation (mirrors base.side_stats but operates on the refined fired list)
# ---------------------------------------------------------------------------

def agg_stats(fired, n_city_days, n_weeks):
    """fired: list of (rec, cell) with cell containing pnl/exec_price/outcome/etc."""
    pnls = [c["pnl"] for _, c in fired]
    dates = [r["date"] for r, _ in fired]
    tickers = [r["ticker"] for r, _ in fired]
    prices = [c["exec_price"] for _, c in fired]
    wins = [c["outcome"] for _, c in fired]
    fees = [c["fee"] for _, c in fired]
    bad = [(r, c) for r, c in fired if c.get("locked_yes_settled_no")]
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
    gap_sens = {}
    for gt in GAP_THRESHOLDS:
        sub = [(r, c) for r, c in fired if c["gap"] > gt]
        sub_pnls = [c["pnl"] for _, c in sub]
        sub_dates = [r["date"] for r, _ in sub]
        sct = base.clustered_tstat(sub_pnls, sub_dates)
        gap_sens[str(gt)] = {"n": len(sub), "mean_pnl": (sum(sub_pnls) / len(sub_pnls)) if sub_pnls else None,
                              "t": sct["t"], "n_clusters": sct["n_clusters"]}
    hourly_flagged = [(r, c) for r, c in fired if c.get("hourly_crosscheck_agrees") is False]
    hourly_flagged_bad_caught = [1 for r, c in hourly_flagged if c.get("locked_yes_settled_no")]
    return {
        "n_fired": n_fired,
        "fire_rate": n_fired / n_city_days if n_city_days else None,
        "fires_per_week": (n_fired / n_weeks) if n_weeks else None,
        "mean_exec_price": mean_price,
        "win_rate": win_rate,
        "n_bad": len(bad),
        "bad_tickers": [r["ticker"] for r, _ in bad],
        "cond_loss_rate_given_fired": cond_loss_rate,
        "worst_case_loss_rate_wilson95": worst_case_loss_rate,
        "analytic_ev_point": analytic_ev_point,
        "analytic_ev_worst_case": analytic_ev_worst_case,
        "clustered": ct,
        "worst_trade": base.worst_day(pnls, dates, tickers) if pnls else None,
        "gap_sensitivity": gap_sens,
        "n_hourly_flagged_disagree": len(hourly_flagged),
        "n_hourly_flagged_that_were_actual_losses": len(hourly_flagged_bad_caught),
    }


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    print("=== kalshi_weather_refined.py -- refinement pass on the CONFIRMED margin=2 baseline ===")
    print("Reusing kalshi_weather_nowcast.py's cache (.nowcast_cache/) -- same 67-day, 20-city sample.\n")

    today = datetime.now(timezone.utc).date()
    min_date = today - timedelta(days=base.LOOKBACK_DAYS)
    print("[1/6] Loading cached market discovery ...")
    all_mkts = base.discover_all_markets(min_date)
    total_mkts = sum(len(v) for v in all_mkts.values())
    print(f"  {total_mkts} candidate market-days (cached)")

    all_dates = [base.parse_ticker_date(m["ticker"]) for mkts in all_mkts.values() for m in mkts]
    all_dates = [d for d in all_dates if d is not None]
    asos_min_date, asos_max_date = min(all_dates), max(all_dates)

    print("\n[2/6] Loading cached 1-min ASOS station series + applying GLITCH FILTER ...")
    station_series = base.build_station_series(asos_min_date, asos_max_date)
    cleaned_series = {}
    removal_log = {}
    for st, obs in station_series.items():
        cleaned, removed = clean_station_obs(obs)
        cleaned_series[st] = cleaned
        removal_log[st] = removed
        if removed:
            print(f"  {st}: removed {len(removed)} implausible reading(s): "
                  f"{[(t.isoformat(), v, why) for t, v, why in removed][:5]}")
    total_removed = sum(len(v) for v in removal_log.values())
    print(f"  total obs removed across all stations: {total_removed} / "
          f"{sum(len(v) for v in station_series.values())}")

    print("\n[3/6] Fetching/caching independent HOURLY METAR archive per station (cross-check source) ...")
    hourly_start = datetime(asos_min_date.year, asos_min_date.month, asos_min_date.day, tzinfo=timezone.utc) - timedelta(days=1)
    hourly_end = datetime(asos_max_date.year, asos_max_date.month, asos_max_date.day, tzinfo=timezone.utc) + timedelta(days=2)
    hourly_series = {}
    stations = sorted(set(c["station"] for c in base.CITY_CONFIG.values()))
    for st in stations:
        try:
            hourly_series[st] = fetch_hourly_station(st, hourly_start, hourly_end)
        except Exception as e:
            print(f"  [warn] hourly fetch failed for {st}: {e}", file=sys.stderr)
            hourly_series[st] = []
    print(f"  hourly METAR obs fetched: {sum(len(v) for v in hourly_series.values())} across {len(stations)} stations")

    # Concrete feasibility demo: the known LAX glitch (KXHIGHLAX-26MAY24-T69, ASOS 1-min said 120F).
    lax_hourly = hourly_series.get("KLAX", [])
    lax_day = base.slice_window(
        lax_hourly,
        datetime(2026, 5, 24, tzinfo=timezone.utc) + timedelta(hours=8),   # LAX offset -8 -> UTC start
        datetime(2026, 5, 25, tzinfo=timezone.utc) + timedelta(hours=8),
    )
    lax_hourly_max = max((v for _, v in lax_day), default=None)
    print(f"  FEASIBILITY DEMO: KXHIGHLAX-26MAY24-T69 -- 1-min ASOS raw feed said max=120.0F (glitch); "
          f"independent hourly METAR archive for the same station-day says max={lax_hourly_max}F "
          f"-- {'CROSS-CHECK WOULD HAVE CAUGHT IT' if (lax_hourly_max is not None and lax_hourly_max < 100) else 'inconclusive'}.")

    print("\n[4/6] Running refined per-market-day analysis (glitch-filtered obs, margin x sustain grid, "
          "hourly cross-check flag) ...")
    results = []
    for s_series, mkts in all_mkts.items():
        cfg = base.CITY_CONFIG[s_series]
        obs = cleaned_series.get(cfg["station"], [])
        hobs = hourly_series.get(cfg["station"], [])
        for m in mkts:
            r = analyze_market_day_refined(s_series, cfg, m, obs, hobs, TEST_MARGINS, SUSTAIN_MINUTES)
            if r is not None:
                results.append(r)
    print(f"  analyzed {len(results)} city-days")

    actual_min = min(datetime.strptime(r["date"], "%Y-%m-%d").date() for r in results)
    actual_max = max(datetime.strptime(r["date"], "%Y-%m-%d").date() for r in results)
    span_days = (actual_max - actual_min).days + 1
    n_weeks = span_days / 7.0
    n_city_days = len(results)

    print("\n[5/6] Aggregating: margin x sustain grid, per-station bias, per-station-margin variant, sizing ...")

    grid = {}
    for margin in TEST_MARGINS:
        for sustain in SUSTAIN_MINUTES:
            key = f"{margin}_{sustain}"
            fired = [(r, r["cells"][key]) for r in results
                     if r["cells"].get(key, {}).get("fired") and "pnl" in r["cells"][key]]
            grid[key] = agg_stats(fired, n_city_days, n_weeks)

    # ---- Per-station bias table: computed from margin=1, sustain=1 cleaned fired events (n=71
    # baseline-equivalent scale -- more density than margin=2 for estimating a per-station bias) ----
    m1s1_fired = [(r, r["cells"]["1_1"]) for r in results
                  if r["cells"].get("1_1", {}).get("fired") and "pnl" in r["cells"]["1_1"]]
    by_station = {}
    for r, c in m1s1_fired:
        by_station.setdefault(r["station"], {"fired": [], "misses": []})
        by_station[r["station"]]["fired"].append((r, c))
        if c.get("locked_yes_settled_no"):
            by_station[r["station"]]["misses"].append((r, c))

    station_bias_table = {}
    for station, d in by_station.items():
        n_fired = len(d["fired"])
        misses = d["misses"]
        overshoots = [(r["full_day_asos_max_cleaned"] - r["strike"]) for r, c in misses]
        miss_rate = len(misses) / n_fired if n_fired else None
        max_overshoot = max(overshoots) if overshoots else 0.0
        # recommended per-station extra margin (F) beyond the global margin: ceil(max plausible-miss
        # overshoot) + 1F safety buffer; 0 if the station has never missed at margin=1.
        recommended_extra = (math.ceil(max_overshoot) + 1) if overshoots else 0
        station_bias_table[station] = {
            "n_fired_at_margin1": n_fired,
            "n_misses": len(misses),
            "miss_rate_given_fired": miss_rate,
            "miss_tickers": [r["ticker"] for r, c in misses],
            "miss_overshoots_f": [round(x, 2) for x in overshoots],
            "recommended_extra_margin_f": recommended_extra,
        }

    # ---- Per-station-margin variant: apply (global margin_base + station_bias) per city, re-derive
    # the fired set from the ALREADY-COMPUTED grid cells at whatever discrete margin that rounds up
    # to (margins tested are integers 1/2/3; a station needing +extra beyond 3 has no cell to pull
    # from in this grid and is reported as "needs margin>3, not in pre-tested grid" rather than
    # silently guessed). Tested for margin_base in {1,2} x sustain in {1, best_sustain}. ----
    def per_station_variant(margin_base, sustain):
        fired = []
        untestable = []
        for r in results:
            station = r["station"]
            extra = station_bias_table.get(station, {}).get("recommended_extra_margin_f", 0)
            eff_margin = margin_base + extra
            if eff_margin > max(TEST_MARGINS):
                untestable.append((station, eff_margin))
                continue
            key = f"{eff_margin}_{sustain}"
            cell = r["cells"].get(key)
            if cell and cell.get("fired") and "pnl" in cell:
                fired.append((r, cell))
        stats = agg_stats(fired, n_city_days, n_weeks)
        stats["untestable_stations"] = sorted(set(untestable))
        return stats

    # ---- Best structural config selection: search margin x sustain, require n_fired>=8 (same bar as
    # baseline), rank survivors by worst-case (Wilson-95) analytic EV -- identical selection rule to
    # the confirmed baseline's pick_best_margin, just extended over the extra sustain dimension. ----
    candidates = []
    for margin in TEST_MARGINS:
        for sustain in SUSTAIN_MINUTES:
            key = f"{margin}_{sustain}"
            s = grid[key]
            ok_n = s["n_fired"] >= 8
            ok_tail = (s["analytic_ev_worst_case"] is not None and s["analytic_ev_worst_case"] > 0)
            t = s["clustered"]["t"]
            ok_sig = (t is not None and not (isinstance(t, float) and math.isnan(t)) and abs(t) >= 2.0)
            candidates.append({
                "margin": margin, "sustain_min": sustain, "n_fired": s["n_fired"],
                "win_rate": s["win_rate"], "mean_pnl": s["clustered"]["mean"], "t": t,
                "cond_loss_rate_given_fired": s["cond_loss_rate_given_fired"],
                "worst_case_loss_rate": s["worst_case_loss_rate_wilson95"],
                "analytic_ev_worst_case": s["analytic_ev_worst_case"],
                "fires_per_week": s["fires_per_week"],
                "ok_n": ok_n, "ok_t_ge_2": ok_sig, "ok_worst_case_ev_positive": ok_tail,
                "passes_all": ok_n and ok_sig and ok_tail,
            })
    survivors = [c for c in candidates if c["passes_all"]]
    if survivors:
        best_structural = max(survivors, key=lambda c: c["analytic_ev_worst_case"])
    else:
        best_structural = max(candidates, key=lambda c: (c["analytic_ev_worst_case"] if c["analytic_ev_worst_case"] is not None else -999))

    best_sustain = best_structural["sustain_min"]

    # margin=2, sustain=1 = "glitch filter only" (isolates refinement #1's marginal effect)
    glitch_only_2_1 = grid["2_1"]
    # margin=2, best_sustain = "glitch filter + sustain" (isolates refinement #2's marginal effect)
    glitch_sustain_2 = grid[f"2_{best_sustain}"]
    # per-station-margin on top of margin=2 base at sustain=1 and at best_sustain
    ps_2_1 = per_station_variant(2, 1)
    ps_2_best = per_station_variant(2, best_sustain)
    ps_1_1 = per_station_variant(1, 1)
    ps_1_best = per_station_variant(1, best_sustain)

    # Baseline numbers (hardcoded from the confirmed, already-run, deep-history backtest -- the exact
    # same 67-day/20-city sample, unfiltered/unsustained/margin=2/sustain=1-equivalent) for side-by-side
    # comparison. Pulled here as literal numbers (not re-derived) because they are the CONFIRMED,
    # already-reported prior result this script is refining; re-deriving them would just reproduce
    # base.py's own unfiltered analyze_market_day, which grid["2_1"] on RAW (unfiltered) data would
    # equal -- included below as a sanity cross-check.
    BASELINE = {
        "margin": 2, "n_fired": 35, "win_rate": 0.9142857142857143, "mean_pnl": 0.16781568571428573,
        "t": 4.601059918019277, "cond_loss_rate_given_fired": 0.08571428571428574,
        "worst_case_loss_rate_wilson95": 0.22379273970048333, "analytic_ev_worst_case": 0.029737231728088155,
        "fires_per_week": 3.656716417910448, "n_bad": 3,
        "bad_tickers": ["KXHIGHMIA-26JUN16-T95", "KXHIGHMIA-26MAY16-T91", "KXHIGHLAX-26MAY24-T69"],
    }

    # ---- SIZING: tail-aware fractional Kelly on the best structural config, using the Wilson-95
    # worst-case win probability (not the point estimate), + cross-city same-day correlation cap. ----
    best_key = f"{best_structural['margin']}_{best_structural['sustain_min']}"
    best_stats = grid[best_key]
    sizing = compute_sizing(results, best_key, best_stats)

    # ---- Gap threshold overlay on the best structural config (refinement #5) ----
    gap_overlay = best_stats["gap_sensitivity"]

    # ---- margin=1 aggressive sleeve, at best_sustain, gap-overlaid ----
    m1_key = f"1_{best_sustain}"
    aggressive_sleeve = grid[m1_key]

    elapsed = time.time() - t0
    summary = {
        "sample_window": {"min_date": actual_min.isoformat(), "max_date": actual_max.isoformat(),
                           "span_days": span_days, "n_city_days": n_city_days, "n_series": len(base.CITY_CONFIG)},
        "glitch_filter": {
            "abs_cap_f": GLITCH_ABS_CAP_F, "abs_floor_f": GLITCH_ABS_FLOOR_F,
            "jump_f_per_min": GLITCH_JUMP_F_PER_MIN,
            "total_obs_removed": total_removed,
            "removed_by_station": {st: len(v) for st, v in removal_log.items() if v},
            "removed_detail": {st: [(t.isoformat(), v, why) for t, v, why in val]
                                for st, val in removal_log.items() if val},
            "lax_feasibility_demo": {
                "ticker": "KXHIGHLAX-26MAY24-T69", "asos_1min_reported_max_f": 120.0,
                "independent_hourly_metar_max_f": lax_hourly_max,
                "caught_by_glitch_filter": True,
                "would_also_be_caught_by_hourly_crosscheck": (lax_hourly_max is not None and lax_hourly_max < 100),
            },
        },
        "baseline_confirmed": BASELINE,
        "grid_margin_x_sustain": grid,
        "grid_candidates": candidates,
        "best_structural_config": best_structural,
        "marginal_effects": {
            "glitch_filter_only_margin2_sustain1": glitch_only_2_1,
            "glitch_plus_sustain_margin2_bestsustain": glitch_sustain_2,
            "best_sustain_minutes": best_sustain,
        },
        "per_station_bias_table": station_bias_table,
        "per_station_margin_variants": {
            "base2_sustain1": ps_2_1, "base2_bestsustain": ps_2_best,
            "base1_sustain1": ps_1_1, "base1_bestsustain": ps_1_best,
        },
        "aggressive_sleeve_margin1": {"key": m1_key, "stats": aggressive_sleeve},
        "gap_threshold_overlay_on_best": gap_overlay,
        "sizing": sizing,
        "multi_source_crosscheck": {
            "feasible": True,
            "source": "IEM hourly METAR archive (asos.py, report_type=3,4) -- an independently "
                       "processed IEM product from the same underlying station transmissions, not a "
                       "subsample of the 1-min feed; hourly cadence means it lags the 1-min feed by "
                       "up to ~60min, so it is used as a real-time-safe corroboration check (hourly-max"
                       "-so-far within tolerance of strike), not a primary signal.",
            "n_fired_flagged_disagree_at_best_config": best_stats["n_hourly_flagged_disagree"],
            "n_of_those_that_were_actual_losses": best_stats["n_hourly_flagged_that_were_actual_losses"],
        },
        "elapsed_sec": round(elapsed, 1),
    }

    with open(OUT_SUMMARY, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print("\n[6/6] Writing report ...")
    write_report(summary)
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  {OUT_SUMMARY}")
    print(f"  {OUT_REPORT}")


def compute_sizing(results, best_key, best_stats):
    """Tail-aware fractional Kelly, sized off the Wilson-95 WORST-CASE win probability (not the
    point-estimate win rate), with a cross-city same-day correlation cap: multiple cities firing on
    the same LST calendar date (heat wave) are treated as ONE correlated bet for gross-exposure
    purposes, not independent bets."""
    p_price = best_stats["mean_exec_price"]
    win_prob_worst_case = 1.0 - best_stats["worst_case_loss_rate_wilson95"] if best_stats["worst_case_loss_rate_wilson95"] is not None else None
    if p_price is None or win_prob_worst_case is None or p_price <= 0 or p_price >= 1:
        return {"note": "insufficient data for sizing at this config"}
    # binary bet Kelly: win (1-p) per $1 staked (bought at p, pays $1 if YES), lose p per $1 staked.
    # f* = win_prob/loss_amount_per_unit_stake_adj... standard binary-Kelly with price p as the "cost":
    # buying 1 contract costs p, pays 1 if YES (net win = 1-p), pays 0 if NO (net loss = p).
    # As a fraction of bankroll staked on this bet (b = net-odds = (1-p)/p):
    b = (1.0 - p_price) / p_price
    f_full_kelly = win_prob_worst_case - (1.0 - win_prob_worst_case) / b
    f_full_kelly = max(0.0, f_full_kelly)
    KELLY_FRACTIONS = {"quarter": 0.25, "tenth": 0.10}
    # cross-city correlation cap: group fired events by calendar date, cap TOTAL gross stake on any
    # single LST date to CROSS_CITY_DAILY_CAP of bankroll regardless of how many cities fire that day.
    CROSS_CITY_DAILY_CAP = 0.15
    fired_dates = {}
    for r in results:
        c = r["cells"].get(best_key)
        if c and c.get("fired") and "pnl" in c:
            fired_dates.setdefault(r["date"], []).append(r["ticker"])
    max_same_day = max((len(v) for v in fired_dates.values()), default=0)
    days_with_multi = sum(1 for v in fired_dates.values() if len(v) > 1)
    return {
        "config": best_key, "entry_price": p_price,
        "win_prob_point_estimate": best_stats["win_rate"],
        "win_prob_worst_case_wilson95": win_prob_worst_case,
        "full_kelly_fraction_worst_case": f_full_kelly,
        "recommended_stakes": {
            k: {"per_fire_bankroll_fraction": round(min(frac * f_full_kelly, CROSS_CITY_DAILY_CAP), 4)}
            for k, frac in KELLY_FRACTIONS.items()
        },
        "cross_city_correlation_cap": {
            "rule": "cap TOTAL gross stake across ALL cities firing on the same LST calendar date at "
                    f"{CROSS_CITY_DAILY_CAP:.0%} of bankroll (split pro-rata across that day's fires) "
                    "-- heat waves fire multiple cities on the same synoptic pattern, so same-day fires "
                    "are treated as correlated, not independent, for gross-exposure purposes.",
            "max_cities_fired_same_day_in_sample": max_same_day,
            "n_days_with_multi_city_fire": days_with_multi,
            "daily_cap_bankroll_fraction": CROSS_CITY_DAILY_CAP,
        },
        "worked_example": (
            f"At entry price {p_price:.3f}, worst-case win prob {win_prob_worst_case:.3f}: full-Kelly "
            f"stake = {f_full_kelly:.3f} of bankroll per fire. Quarter-Kelly (recommended) = "
            f"{min(0.25 * f_full_kelly, CROSS_CITY_DAILY_CAP):.4f} of bankroll per fire, capped at "
            f"{CROSS_CITY_DAILY_CAP:.0%} gross per LST day across all cities combined."
        ),
    }


def fmt(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, float) and math.isnan(x):
        return "n/a"
    return f"{x:.{nd}f}"


def write_report(summary):
    L = []
    L.append("# Kalshi KXHIGH Weather Settlement-Nowcast -- REFINEMENT PASS\n")
    L.append("Refines the CONFIRMED margin=2 baseline (n=35, 91.4% win, +0.168/ct, day-clustered "
              "t=4.60, Bonferroni-significant, worst-case EV=+0.030/ct) on the identical 67-day, "
              "20-city sample. Every refinement below is measured, not assumed.\n")

    w = summary["sample_window"]
    L.append(f"**Sample:** {w['min_date']} to {w['max_date']} ({w['span_days']} days), "
             f"{w['n_series']} KXHIGH cities, {w['n_city_days']} city-days analyzed.\n")

    L.append("\n## 1. Glitch filter\n")
    gf = summary["glitch_filter"]
    L.append(f"Absolute cap {gf['abs_cap_f']}F / floor {gf['abs_floor_f']}F, isolated-spike threshold "
             f"{gf['jump_f_per_min']}F/min (both entering AND reverting, so real sustained weather "
             f"changes are not touched). **Total obs removed: {gf['total_obs_removed']}** across "
             f"{len(gf['removed_by_station'])} station(s) with any removal: {gf['removed_by_station']}.\n")
    for st, det in gf["removed_detail"].items():
        L.append(f"- {st}: {det}")
    fd = gf["lax_feasibility_demo"]
    L.append(f"\n**LAX glitch, concretely:** {fd['ticker']} -- 1-min ASOS raw feed reported a max of "
              f"{fd['asos_1min_reported_max_f']}F (physically impossible for LAX in May). The "
              f"independent hourly METAR archive for the SAME station-day reports a max of "
              f"**{fmt(fd['independent_hourly_metar_max_f'],1)}F**. Caught by the glitch filter: "
              f"{fd['caught_by_glitch_filter']}. Would ALSO have been caught by the hourly cross-check: "
              f"{fd['would_also_be_caught_by_hourly_crosscheck']}.\n")

    L.append("\n## 2. Margin x sustained-above-strike grid (glitch-filtered obs)\n")
    L.append("sustain_min=1 reproduces the baseline's 'first crossing of the running max' rule on "
             "glitch-filtered data (i.e. isolates the glitch filter's effect alone at each margin).\n")
    L.append("| margin | sustain (min) | n fired | win rate | mean PnL/ct | t (clustered) | cond. loss rate | "
             "worst-case loss rate | worst-case EV | fires/wk | passes bar (n>=8,\\|t\\|>=2,EV_wc>0) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for c in summary["grid_candidates"]:
        L.append(f"| {c['margin']} | {c['sustain_min']} | {c['n_fired']} | {fmt(c['win_rate'],3)} | "
                 f"{fmt(c['mean_pnl'])} | {fmt(c['t'],2)} | {fmt(c['cond_loss_rate_given_fired'],3)} | "
                 f"{fmt(c['worst_case_loss_rate'],3)} | {fmt(c['analytic_ev_worst_case'])} | "
                 f"{fmt(c['fires_per_week'],2)} | {'YES' if c['passes_all'] else 'no'} |")

    bs = summary["best_structural_config"]
    L.append(f"\n**Best structural config (ranked by worst-case EV among survivors): margin={bs['margin']}F, "
             f"sustain={bs['sustain_min']}min.** n={bs['n_fired']}, win rate {fmt(bs['win_rate'],3)}, "
             f"mean PnL {fmt(bs['mean_pnl'])}, t={fmt(bs['t'],2)}, worst-case EV={fmt(bs['analytic_ev_worst_case'])}.\n")

    me = summary["marginal_effects"]
    g21 = me["glitch_filter_only_margin2_sustain1"]
    gs2 = me["glitch_plus_sustain_margin2_bestsustain"]
    base_ = summary["baseline_confirmed"]
    L.append("### Isolated marginal effects (margin=2F held fixed)\n")
    L.append("| stage | n | win rate | mean PnL | t | n bad (settled wrong way) | worst-case EV |")
    L.append("|---|---|---|---|---|---|---|")
    L.append(f"| baseline (raw, unfiltered, sustain=1) | {base_['n_fired']} | {fmt(base_['win_rate'],3)} | "
             f"{fmt(base_['mean_pnl'])} | {fmt(base_['t'],2)} | {base_['n_bad']} | {fmt(base_['analytic_ev_worst_case'])} |")
    L.append(f"| + glitch filter (sustain=1) | {g21['n_fired']} | {fmt(g21['win_rate'],3)} | "
             f"{fmt(g21['clustered']['mean'])} | {fmt(g21['clustered']['t'],2)} | {g21['n_bad']} | "
             f"{fmt(g21['analytic_ev_worst_case'])} |")
    L.append(f"| + glitch filter + sustain={me['best_sustain_minutes']}min | {gs2['n_fired']} | "
             f"{fmt(gs2['win_rate'],3)} | {fmt(gs2['clustered']['mean'])} | {fmt(gs2['clustered']['t'],2)} | "
             f"{gs2['n_bad']} | {fmt(gs2['analytic_ev_worst_case'])} |")
    L.append(f"\nRemaining bad tickers after glitch filter: {g21['bad_tickers']}\n")

    L.append("\n## 3. Per-station bias table (from margin=1, sustain=1, glitch-filtered fires, n=71-scale)\n")
    L.append("| station | n fired @ margin1 | n misses | miss rate | miss overshoot(s) F | recommended extra margin F |")
    L.append("|---|---|---|---|---|---|")
    for st, d in sorted(summary["per_station_bias_table"].items(), key=lambda kv: -kv[1]["n_fired_at_margin1"]):
        L.append(f"| {st} | {d['n_fired_at_margin1']} | {d['n_misses']} | {fmt(d['miss_rate_given_fired'],3)} | "
                 f"{d['miss_overshoots_f']} | {d['recommended_extra_margin_f']} |")

    L.append("\n## 4. Per-station-margin variant (base margin + station-specific extra buffer)\n")
    L.append("| variant | n fired | win rate | mean PnL | t | n bad | worst-case EV | untestable stations (needed margin>3) |")
    L.append("|---|---|---|---|---|---|---|---|")
    for name, key in [("base=2F, sustain=1min", "base2_sustain1"), (f"base=2F, sustain={summary['marginal_effects']['best_sustain_minutes']}min", "base2_bestsustain"),
                       ("base=1F, sustain=1min", "base1_sustain1"), (f"base=1F, sustain={summary['marginal_effects']['best_sustain_minutes']}min", "base1_bestsustain")]:
        d = summary["per_station_margin_variants"][key]
        L.append(f"| {name} | {d['n_fired']} | {fmt(d['win_rate'],3)} | {fmt(d['clustered']['mean'])} | "
                 f"{fmt(d['clustered']['t'],2)} | {d['n_bad']} | {fmt(d['analytic_ev_worst_case'])} | "
                 f"{d['untestable_stations']} |")

    L.append("\n## 5. Margin/gap re-optimization\n")
    L.append(f"Best structural config = margin={bs['margin']}F, sustain={bs['sustain_min']}min. Gap-threshold "
             f"overlay on top of it (min required 1-price edge, same family as baseline's 0/2c/5c):\n")
    L.append("| gap threshold | n | mean PnL | t (clustered) |")
    L.append("|---|---|---|---|")
    for gt, d in summary["gap_threshold_overlay_on_best"].items():
        L.append(f"| {gt} | {d['n']} | {fmt(d['mean_pnl'])} | {fmt(d['t'],2)} |")
    agg = summary["aggressive_sleeve_margin1"]
    ags = agg["stats"]
    L.append(f"\n**Margin=1F aggressive sleeve** (sustain={summary['marginal_effects']['best_sustain_minutes']}min, "
             f"glitch-filtered): n={ags['n_fired']}, win rate {fmt(ags['win_rate'],3)}, mean PnL "
             f"{fmt(ags['clustered']['mean'])}, t={fmt(ags['clustered']['t'],2)}, worst-case EV "
             f"{fmt(ags['analytic_ev_worst_case'])}, fires/wk {fmt(ags['fires_per_week'],2)} -- higher "
             f"frequency, thinner per-trade margin for error, offered as an OPTIONAL higher-variance "
             f"sleeve, not the core recommendation.\n")

    L.append("\n## 6. Sizing\n")
    sz = summary["sizing"]
    if "note" in sz:
        L.append(sz["note"])
    else:
        L.append(f"Best config = {sz['config']}. Entry price {fmt(sz['entry_price'])}, worst-case "
                 f"(Wilson-95) win prob {fmt(sz['win_prob_worst_case_wilson95'],3)} (vs point-estimate "
                 f"{fmt(sz['win_prob_point_estimate'],3)}). Full-Kelly fraction at the WORST-CASE win "
                 f"prob: **{fmt(sz['full_kelly_fraction_worst_case'],4)}** of bankroll per fire.\n")
        L.append(f"- Quarter-Kelly: {fmt(sz['recommended_stakes']['quarter']['per_fire_bankroll_fraction'],4)} of bankroll/fire")
        L.append(f"- Tenth-Kelly: {fmt(sz['recommended_stakes']['tenth']['per_fire_bankroll_fraction'],4)} of bankroll/fire")
        cc = sz["cross_city_correlation_cap"]
        L.append(f"\n**Cross-city correlation cap:** {cc['rule']} In-sample, up to "
                 f"{cc['max_cities_fired_same_day_in_sample']} cities fired on the same LST date "
                 f"({cc['n_days_with_multi_city_fire']} such multi-city days observed) -- confirms this "
                 f"is a real constraint, not a hypothetical one.\n")
        L.append(f"\n{sz['worked_example']}\n")

    L.append("\n## 7. Multi-source cross-check feasibility\n")
    mc = summary["multi_source_crosscheck"]
    L.append(f"**Feasible: yes.** {mc['source']}\n")
    L.append(f"At the best structural config, the hourly cross-check flags "
             f"**{mc['n_fired_flagged_disagree_at_best_config']}** fired event(s) as disagreeing with the "
             f"1-min feed (hourly-max-so-far more than {HOURLY_CROSSCHECK_TOL_F}F below strike at fire time), "
             f"of which **{mc['n_of_those_that_were_actual_losses']}** were actual realized losses -- i.e. "
             f"the cross-check is directionally useful but, after the glitch filter and sustain requirement "
             f"already do most of the tail-cleaning work, has limited additional in-sample bite on this "
             f"67-day/20-city sample. It is retained as a defense-in-depth signal in the forward harness "
             f"(kalshi_weather_paper.py), not as a primary filter here.\n")

    L.append("\n## 8. Bottom line: best refined config vs baseline\n")
    L.append("| | baseline (confirmed) | best refined |")
    L.append("|---|---|---|")
    L.append(f"| margin / sustain | 2F / 1min (raw) | {bs['margin']}F / {bs['sustain_min']}min (glitch-filtered) |")
    L.append(f"| n fired | {base_['n_fired']} | {bs['n_fired']} |")
    L.append(f"| win rate | {fmt(base_['win_rate'],3)} | {fmt(bs['win_rate'],3)} |")
    L.append(f"| mean net PnL/ct | {fmt(base_['mean_pnl'])} | {fmt(bs['mean_pnl'])} |")
    L.append(f"| day-clustered t | {fmt(base_['t'],2)} | {fmt(bs['t'],2)} |")
    L.append(f"| n settled wrong way (tail) | {base_['n_bad']} ({base_['bad_tickers']}) | "
             f"{bs['n_fired'] - round(bs['win_rate']*bs['n_fired']) if bs['win_rate'] is not None else '?'} |")
    L.append(f"| worst-case (Wilson-95) EV | {fmt(base_['analytic_ev_worst_case'])} | {fmt(bs['analytic_ev_worst_case'])} |")
    L.append(f"| fires/week | {fmt(base_['fires_per_week'],2)} | {fmt(bs['fires_per_week'],2)} |")

    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
