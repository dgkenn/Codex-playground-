#!/usr/bin/env python3
"""
phase2_trackA_price.py

Track A validation: re-run the Kalshi K-WX nowcast edge on the FULL real price history
available in this environment -- ALL ~20 KXHIGH cities x FULL 6-rung ladder (1 greater +
4 between + 1 less) x KXLOW mirror series, for the complete ~10-week live-market window
(discovered dynamically, ~2026-05-12 .. today).

THE RATCHET ARGUMENT, generalized to every rung (not just the top "greater" rung):

  HIGH markets settle YES iff floor_strike < actual_high <= cap_strike (missing bound =
  +-inf). The 1-min ASOS running max only ever increases toward actual_high over the LST
  day, so running_max(t) <= actual_high always (a tightening LOWER bound):
    - rung with a floor and NO cap ("greater", the top rung): once running_max clears
      floor+margin (sustained), actual_high is GUARANTEED >= that -> LOCKED YES. Buy YES.
    - any rung WITH a cap ("less" and "between" rungs): once running_max clears
      cap+margin (sustained), actual_high is GUARANTEED > cap -> LOCKED NO for THAT rung
      (its YES window floor<actual<=cap can no longer be satisfied). Buy NO.
  There is no clean floor-side lock for a "between" rung (clearing the floor does not
  guarantee the max won't keep rising through the cap later) -- so only the cap-side event
  is used, which is the honest, no-lookahead, no-late-day-heuristic version of the edge.

  LOW markets mirror this exactly with running MIN (a tightening UPPER bound on
  actual_low, running_min(t) >= actual_low always):
    - rung with a cap and NO floor ("less", the bottom rung): once running_min falls
      below cap-margin (sustained), actual_low is guaranteed <= that -> LOCKED YES.
    - any rung WITH a floor ("greater" and "between" rungs): once running_min falls below
      floor-margin (sustained), actual_low is guaranteed <= floor -> LOCKED NO. Buy NO.

Verified live before coding this: Kalshi's market objects for KXHIGHNY/KXLOWTNYC (sample
pulled directly) show exactly 6 rungs/city-day: 1 'greater' (floor only), 1 'less' (cap
only), 4 'between' (floor+cap), confirming the "1 greater + 4 between + 1 less" structure
from the task brief.

DISK DISCIPLINE: full-day 1-min Kalshi candlesticks average ~150KB/ticker RAW (nested
bid/ask dicts) and the environment has only ~4.8GB free with ~2.9GB already used by prior
runs' caches. This script does NOT persist raw candlestick JSON for the new
(between/less/LOW) tickers -- it fetches, trims to a compact list-of-lists
[ts, yes_ask_open, yes_bid_open, volume, oi] representation, and caches ONLY that (a new
'lite_' cache key). Existing raw 'candles_*' cache files (from kalshi_weather_nowcast.py /
kalshi_weather_expand.py's HIGH-greater / LOW-greater runs) ARE reused read-only when
present, to avoid re-fetching from the network, but never duplicated in bigger form.

Author: automated research script. Do NOT git commit (per task instructions).
"""

import os
import sys
import json
import math
import time
import bisect
import statistics
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import kalshi_weather_nowcast as base
import kalshi_weather_refined as refined
import kalshi_weather_expand as expand

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = base.CACHE_DIR
OUT_REPORT = os.path.join(HERE, "phase2_trackA_price_results.md")
OUT_SUMMARY = os.path.join(HERE, "phase2_trackA_price_summary.json")

KBASE = base.KBASE
Z95 = 1.959963985

HIGH_CITY_CONFIG = base.CITY_CONFIG
LOW_CITY_CONFIG = expand.LOW_CITY_CONFIG

MARGINS = [1, 2, 3]
SUSTAINS = [1, 2, 3, 5]
DECAY_OFFSETS_MIN = [0, 1, 2, 5, 10, 30, 60]
DOA_THRESHOLDS = [0.97, 0.99]

# ---------------------------------------------------------------------------
# 1. Full-ladder market discovery (ALL strike_types, not just 'greater')
# ---------------------------------------------------------------------------

def fetch_ladder_markets(series_ticker, min_date, max_pages=40):
    out = []
    cursor = None
    for _ in range(max_pages):
        url = f"{KBASE}/markets?series_ticker={series_ticker}&status=settled&limit=200"
        if cursor:
            url += f"&cursor={cursor}"
        d = base.http_get_json(url)
        mkts = d.get("markets", [])
        if not mkts:
            break
        stop = False
        for m in mkts:
            tdate = base.parse_ticker_date(m.get("ticker", ""))
            if tdate is None:
                continue
            if tdate < min_date:
                stop = True
                continue
            if m.get("strike_type") in ("greater", "less", "between") and m.get("result") in ("yes", "no"):
                out.append(m)
        cursor = d.get("cursor")
        if not cursor or stop:
            break
    return out


def discover_ladder(min_date, city_config, tag):
    cache_key = f"ladder2_{tag}_{min_date.isoformat()}.json"
    cached = base.load_cache(cache_key)
    if cached is not None:
        return cached
    all_mkts = {}
    for series, cfg in city_config.items():
        try:
            mkts = fetch_ladder_markets(series, min_date)
        except Exception as e:
            print(f"  [warn] {series}: ladder discovery failed: {e}", file=sys.stderr)
            mkts = []
        all_mkts[series] = mkts
        print(f"  {series:14s} ({cfg['name']:26s}): {len(mkts)} settled ladder markets")
    base.save_cache(cache_key, all_mkts)
    return all_mkts


# ---------------------------------------------------------------------------
# 2. Lite candle fetch (disk-frugal): reuse existing raw cache if present, else fetch
#    live and persist ONLY the trimmed [ts, ya, yb, vol, oi] rows.
# ---------------------------------------------------------------------------

def fetch_candles_lite(series, ticker, start_ts, end_ts):
    lite_key = f"lite2_{ticker}_{start_ts}_{end_ts}.json"
    cached = base.load_cache(lite_key)
    if cached is not None:
        return cached
    raw_key = f"candles_{ticker}_{start_ts}_{end_ts}.json"
    raw_path = base.cache_path(raw_key)
    if os.path.exists(raw_path):
        candles = base.load_cache(raw_key) or []
    else:
        url = (f"{KBASE}/series/{series}/markets/{ticker}/candlesticks"
               f"?start_ts={start_ts}&end_ts={end_ts}&period_interval=1")
        try:
            d = base.http_get_json(url)
        except Exception:
            d = {}
        candles = d.get("candlesticks", [])
    lite = []
    for c in candles:
        ts = base.candle_start_ts(c)
        ya = base.yes_ask_open(c)
        yb = base.yes_bid_open(c)
        vol = float(c.get("volume_fp", 0) or 0)
        oi = float(c.get("open_interest_fp", 0) or 0)
        lite.append([ts, round(ya, 4) if not math.isnan(ya) else None,
                     round(yb, 4) if not math.isnan(yb) else None, vol, oi])
    lite.sort(key=lambda r: r[0])
    base.save_cache(lite_key, lite)
    return lite


def exec_row_at_or_after(lite_candles, t_ts):
    for row in lite_candles:
        if row[0] >= t_ts:
            return row
    return None


def row_near_offset(lite_candles, base_ts, offset_min):
    """Nearest candle row with ts >= base_ts + offset_min*60 (first at/after that
    instant -- no lookahead relative to that later instant either)."""
    target = base_ts + offset_min * 60
    for row in lite_candles:
        if row[0] >= target:
            return row
    return None


# ---------------------------------------------------------------------------
# 3. Rung classification + sustained-cross event detection
# ---------------------------------------------------------------------------

def classify_rung(family, market):
    st = market.get("strike_type")
    lo = market.get("floor_strike")
    hi = market.get("cap_strike")
    if family == "HIGH":
        if st == "greater":
            return {"side": "LONG", "rung_group": "greater", "threshold_field": "lo", "lo": lo, "hi": hi}
        else:  # less or between -- both have a cap
            return {"side": "SHORT", "rung_group": ("less" if st == "less" else "between"),
                    "threshold_field": "hi", "lo": lo, "hi": hi}
    else:  # LOW
        if st == "less":
            return {"side": "LONG", "rung_group": "less", "threshold_field": "hi", "lo": lo, "hi": hi}
        else:  # greater or between -- both have a floor
            return {"side": "SHORT", "rung_group": ("greater" if st == "greater" else "between"),
                    "threshold_field": "lo", "lo": lo, "hi": hi}


def find_cross(family, side, threshold_field, obs, lo, hi, margin, sustain_min):
    """obs: cleaned (t,v) list restricted to LST settlement day. Returns t_star or None."""
    if family == "HIGH":
        threshold = (lo if threshold_field == "lo" else hi) + margin
        return refined.find_sustained_cross(obs, threshold, sustain_min)
    else:
        threshold = (hi if threshold_field == "hi" else lo) - margin
        return expand.find_sustained_cross_below(obs, threshold, sustain_min)


# ---------------------------------------------------------------------------
# 4. Per-market-day-rung analysis across the (margin, sustain) grid
# ---------------------------------------------------------------------------

def analyze_rung(family, series, cfg, market, cleaned_obs):
    ticker = market["ticker"]
    tdate = base.parse_ticker_date(ticker)
    if tdate is None:
        return None
    result = market.get("result")
    if result not in ("yes", "no"):
        return None
    info = classify_rung(family, market)
    lo, hi = info["lo"], info["hi"]
    offset = cfg["offset"]
    start_utc = datetime(tdate.year, tdate.month, tdate.day, 0, 0, tzinfo=timezone.utc) - timedelta(hours=offset)
    end_utc = start_utc + timedelta(days=1)
    obs = base.slice_window(cleaned_obs, start_utc, end_utc)
    if len(obs) < 20:
        return None

    close_time_str = market["close_time"]
    close_dt = datetime.strptime(close_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    cand_end = int(min(close_dt, end_utc + timedelta(minutes=2)).timestamp())
    cand_start = int(start_utc.timestamp())
    try:
        lite_candles = fetch_candles_lite(series, ticker, cand_start, cand_end)
    except Exception:
        return None
    if not lite_candles:
        return None

    rec = {
        "family": family, "series": series, "city": cfg["name"], "station": cfg["station"],
        "ticker": ticker, "date": tdate.isoformat(), "result": result, "official_yes": result == "yes",
        "side": info["side"], "rung_group": info["rung_group"], "lo": lo, "hi": hi,
        "cells": {},
    }
    any_fired = False
    for margin in MARGINS:
        for sustain in SUSTAINS:
            key = f"{margin}_{sustain}"
            t_star = find_cross(family, info["side"], info["threshold_field"], obs, lo, hi, margin, sustain)
            cell = {"fired": t_star is not None}
            if t_star is not None:
                t_ts = int(t_star.timestamp())
                row = exec_row_at_or_after(lite_candles, t_ts)
                if row is not None:
                    ts0, ya, yb, vol, oi = row
                    if info["side"] == "LONG":
                        p = ya
                        pnl_side_ok = p is not None and p > 0
                        exec_price = p
                    else:
                        no_ask = (1.0 - yb) if yb is not None else None
                        pnl_side_ok = no_ask is not None and no_ask > 0
                        exec_price = no_ask
                    if pnl_side_ok:
                        fee = base.kalshi_fee(exec_price)
                        outcome = 1.0 if ((info["side"] == "LONG" and result == "yes") or
                                           (info["side"] == "SHORT" and result == "no")) else 0.0
                        pnl = outcome - exec_price - fee
                        any_fired = True
                        # decay curve: gap = 1 - exec_price_equivalent at t_star+k min
                        decay = {}
                        for k in DECAY_OFFSETS_MIN:
                            r2 = row_near_offset(lite_candles, ts0, k)
                            if r2 is None:
                                decay[str(k)] = None
                                continue
                            _, ya2, yb2, _, _ = r2
                            if info["side"] == "LONG":
                                px2 = ya2
                            else:
                                px2 = (1.0 - yb2) if yb2 is not None else None
                            decay[str(k)] = (1.0 - px2) if px2 is not None else None
                        cell.update({
                            "t_star": t_star.isoformat(), "exec_price": exec_price, "fee": fee,
                            "outcome": outcome, "pnl": pnl, "gap": 1.0 - exec_price,
                            "volume_at_exec": vol, "oi_at_exec": oi,
                            "wrong_way": (outcome == 0.0),
                            "decay_gap_by_min": decay,
                        })
                    else:
                        cell["fired"] = False
                else:
                    cell["fired"] = False
            rec["cells"][key] = cell
    if not any_fired:
        return None
    return rec


# ---------------------------------------------------------------------------
# 5. Stats helpers (reuse base's clustered t-stat / Wilson bound / norm helpers)
# ---------------------------------------------------------------------------

def quantile(sorted_vals, q):
    if not sorted_vals:
        return None
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    idx = q * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def agg_stats(fired):
    """fired: list of (rec, cell) with cell containing pnl/exec_price/outcome/gap/decay."""
    n = len(fired)
    if n == 0:
        return {"n_fired": 0}
    pnls = [c["pnl"] for _, c in fired]
    dates = [r["date"] for r, _ in fired]
    tickers = [r["ticker"] for r, _ in fired]
    prices = [c["exec_price"] for _, c in fired]
    wins = [c["outcome"] for _, c in fired]
    fees = [c["fee"] for _, c in fired]
    gaps = sorted(c["gap"] for _, c in fired)
    bad = [(r, c) for r, c in fired if c.get("wrong_way")]
    win_rate = sum(wins) / n
    mean_price = sum(prices) / n
    mean_fee = sum(fees) / n
    worst_case_loss_rate = base.wilson_upper_bound(len(bad), n, Z95)
    analytic_ev_worst_case = (1.0 - worst_case_loss_rate) - mean_price - mean_fee
    ct = base.clustered_tstat(pnls, dates)
    doa = {}
    for th in DOA_THRESHOLDS:
        doa_n = sum(1 for g in gaps if (1.0 - g) >= th)  # exec_price >= th <=> gap <= 1-th
        doa[str(th)] = {"n_doa": doa_n, "frac_doa": doa_n / n, "n_deployable": n - doa_n}
    return {
        "n_fired": n,
        "win_rate": win_rate,
        "mean_exec_price": mean_price,
        "mean_fee": mean_fee,
        "mean_pnl": sum(pnls) / n,
        "clustered": ct,
        "n_bad": len(bad),
        "bad_tickers": [r["ticker"] for r, _ in bad][:30],
        "worst_case_loss_rate_wilson95": worst_case_loss_rate,
        "analytic_ev_worst_case": analytic_ev_worst_case,
        "worst_trade": base.worst_day(pnls, dates, tickers),
        "gap_quantiles": {
            "p10": quantile(gaps, 0.10), "p25": quantile(gaps, 0.25), "p50": quantile(gaps, 0.50),
            "p75": quantile(gaps, 0.75), "p90": quantile(gaps, 0.90),
        },
        "doa": doa,
    }


def decay_curve(fired):
    """Mean gap at each offset (only over fires where that offset's row existed),
    plus n available at each offset, and half-life estimate via geometric interpolation
    against gap-at-0."""
    out = {}
    n_at = {}
    for k in DECAY_OFFSETS_MIN:
        vals = [c["decay_gap_by_min"].get(str(k)) for _, c in fired if c["decay_gap_by_min"].get(str(k)) is not None]
        out[str(k)] = (sum(vals) / len(vals)) if vals else None
        n_at[str(k)] = len(vals)
    gap0 = out.get("0")
    half_life = None
    if gap0 and gap0 > 0:
        half_target = gap0 / 2.0
        ks = sorted(int(k) for k in out if out[k] is not None)
        for i in range(len(ks) - 1):
            k1, k2 = ks[i], ks[i + 1]
            g1, g2 = out[str(k1)], out[str(k2)]
            if g1 >= half_target >= g2 and g1 != g2:
                frac = (g1 - half_target) / (g1 - g2)
                half_life = k1 + frac * (k2 - k1)
                break
        if half_life is None and ks and out[str(ks[-1])] is not None and out[str(ks[-1])] > half_target:
            half_life = float("inf")  # never decays to half within window
    return {"mean_gap_by_min": out, "n_by_min": n_at, "half_life_min": half_life}


def captured_ev_at_latency(fired, latency_min):
    """Realized PnL if we could only act 'latency_min' after the cross (using the price
    at cross+latency_min instead of cross+0). pnl = outcome - price_then - fee_then."""
    pnls = []
    for r, c in fired:
        g = c["decay_gap_by_min"].get(str(latency_min))
        if g is None:
            continue
        price_then = 1.0 - g
        if price_then <= 0 or price_then >= 1:
            continue
        fee_then = base.kalshi_fee(price_then)
        pnl = c["outcome"] - price_then - fee_then
        pnls.append(pnl)
    if not pnls:
        return {"n": 0, "mean_pnl": None}
    return {"n": len(pnls), "mean_pnl": sum(pnls) / len(pnls)}


def bonferroni_pick(all_cells_flat, min_n=8):
    """all_cells_flat: list of dicts {margin, sustain, n, mean, t, p, ...} pooled across
    ALL sides/rungs for a given (margin,sustain). Family size = len(MARGINS)*len(SUSTAINS).
    Bonferroni-correct, then rank survivors (n>=min_n, Bonferroni-sig, worst-case EV>0) by
    worst-case EV; if none survive, report least-bad."""
    family_size = len(MARGINS) * len(SUSTAINS)
    alpha = 0.05
    corrected_alpha = alpha / family_size
    for c in all_cells_flat:
        c["p_bonferroni"] = min(1.0, c["p"] * family_size) if c["p"] is not None else None
        c["sig_bonferroni"] = (c["p"] is not None and c["p"] < corrected_alpha)
    candidates = []
    for c in all_cells_flat:
        ok_n = c["n"] >= min_n
        ok_sig = bool(c["sig_bonferroni"])
        ok_tail = (c["worst_case_ev"] is not None and c["worst_case_ev"] > 0)
        c2 = dict(c)
        c2.update(ok_n=ok_n, ok_sig=ok_sig, ok_tail=ok_tail, passes_all=(ok_n and ok_sig and ok_tail))
        candidates.append(c2)
    survivors = [c for c in candidates if c["passes_all"]]
    if survivors:
        best = max(survivors, key=lambda c: c["worst_case_ev"])
        verdict = "CONFIRMED"
    else:
        best = max(candidates, key=lambda c: (c["worst_case_ev"] if c["worst_case_ev"] is not None else -999))
        verdict = "KILLED"
    return {"family_size": family_size, "corrected_alpha": corrected_alpha, "candidates": candidates,
            "best": best, "verdict": verdict}


def fmt(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, float) and math.isnan(x):
        return "n/a"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    return f"{x:.{nd}f}"


# ---------------------------------------------------------------------------
# 6. Predexon L2 depth sampling
# ---------------------------------------------------------------------------

def predexon_key():
    try:
        with open(os.path.join(HERE, ".predexon_key")) as f:
            return f.read().strip()
    except Exception:
        return None


def fetch_predexon_snapshot(ticker, ts_ms, key, window_ms=10 * 60 * 1000):
    url = (f"https://api.predexon.com/v2/kalshi/orderbooks?ticker={ticker}"
           f"&start_time={ts_ms}&end_time={ts_ms + window_ms}&limit=2000")
    req = urllib.request.Request(url, headers={"x-api-key": key, "User-Agent": base.UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    snaps = d.get("snapshots", [])
    return snaps[0] if snaps else None


def depth_for_fire(rec, cell, key):
    ticker = rec["ticker"]
    t_star = datetime.fromisoformat(cell["t_star"])
    ts_ms = int(t_star.timestamp() * 1000)
    try:
        snap = fetch_predexon_snapshot(ticker, ts_ms, key)
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}
    if snap is None:
        return {"ticker": ticker, "error": "no_snapshot_in_window"}
    side = rec["side"]
    if side == "LONG":
        book = sorted(snap.get("yes_asks", []), key=lambda r: r["price"])
        if not book:
            return {"ticker": ticker, "error": "empty_book"}
        best = book[0]["price"]
        at_best = sum(r["size"] for r in book if r["price"] == best)
        d1 = sum(r["size"] for r in book if r["price"] <= best + 1)
        d2 = sum(r["size"] for r in book if r["price"] <= best + 2)
        best_price_dollars = best / 100.0
    else:
        book = sorted(snap.get("yes_bids", []), key=lambda r: -r["price"])
        if not book:
            return {"ticker": ticker, "error": "empty_book"}
        best = book[0]["price"]  # best yes_bid -> no_ask = 100-best
        at_best = sum(r["size"] for r in book if r["price"] == best)
        d1 = sum(r["size"] for r in book if r["price"] >= best - 1)
        d2 = sum(r["size"] for r in book if r["price"] >= best - 2)
        best_price_dollars = (100 - best) / 100.0
    return {"ticker": ticker, "side": side, "snapshot_ts_ms": snap.get("timestamp"),
            "requested_ts_ms": ts_ms, "best_price": best_price_dollars,
            "size_at_best": at_best, "depth_within_1c": d1, "depth_within_2c": d2}


# ---------------------------------------------------------------------------
# 7. Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    today = datetime.now(timezone.utc).date()
    min_date = today - timedelta(days=400)

    print("=== phase2_trackA_price.py: FULL-ladder x KXHIGH+KXLOW price-history backtest ===")
    print("\n[1/7] Discovering FULL 6-rung ladder settled markets (HIGH + LOW) ...")
    high_mkts = discover_ladder(min_date, HIGH_CITY_CONFIG, "HIGH")
    low_mkts = discover_ladder(min_date, LOW_CITY_CONFIG, "LOW")
    n_high = sum(len(v) for v in high_mkts.values())
    n_low = sum(len(v) for v in low_mkts.values())
    print(f"  HIGH ladder markets: {n_high}   LOW ladder markets: {n_low}   total: {n_high + n_low}")

    all_dates = []
    for mkts in list(high_mkts.values()) + list(low_mkts.values()):
        for m in mkts:
            d = base.parse_ticker_date(m["ticker"])
            if d:
                all_dates.append(d)
    actual_min = min(all_dates)
    actual_max = max(all_dates)
    print(f"  actual window: {actual_min} .. {actual_max} ({(actual_max-actual_min).days+1} days)")

    print("\n[2/7] Fetching/loading ASOS 1-min station obs + glitch-filtering ...")
    stations = sorted(set(c["station"] for c in HIGH_CITY_CONFIG.values()) |
                       set(c["station"] for c in LOW_CITY_CONFIG.values()))
    start_dt = datetime(actual_min.year, actual_min.month, actual_min.day, tzinfo=timezone.utc) - timedelta(days=1)
    end_dt = datetime(actual_max.year, actual_max.month, actual_max.day, tzinfo=timezone.utc) + timedelta(days=2)
    cleaned_station = {}
    glitch_removed_total = 0
    for st in stations:
        try:
            obs = base.fetch_asos_station(st, start_dt, end_dt)
        except Exception as e:
            print(f"  [warn] ASOS {st} failed: {e}", file=sys.stderr)
            obs = []
        cleaned, removed = refined.clean_station_obs(obs)
        glitch_removed_total += len(removed)
        cleaned_station[st] = cleaned
        print(f"  {st}: {len(obs)} raw -> {len(cleaned)} cleaned ({len(removed)} removed)")
    print(f"  total glitch-removed obs: {glitch_removed_total}")

    print("\n[3/7] Analyzing every ladder rung (HIGH+LOW) across the full margin x sustain grid ...")
    jobs = []
    for series, mkts in high_mkts.items():
        cfg = HIGH_CITY_CONFIG[series]
        for m in mkts:
            jobs.append(("HIGH", series, cfg, m))
    for series, mkts in low_mkts.items():
        cfg = LOW_CITY_CONFIG[series]
        for m in mkts:
            jobs.append(("LOW", series, cfg, m))
    print(f"  total rung-market-days to analyze: {len(jobs)}")

    def worker(job):
        family, series, cfg, m = job
        obs = cleaned_station.get(cfg["station"], [])
        try:
            return analyze_rung(family, series, cfg, m, obs)
        except Exception as e:
            return None

    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=14) as ex:
        futs = {ex.submit(worker, j): j for j in jobs}
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if done % 500 == 0:
                print(f"    processed {done}/{len(jobs)} ({time.time()-t0:.0f}s elapsed) ...")
            if r is not None:
                results.append(r)
    print(f"  done: {len(results)}/{len(jobs)} rung-market-days had >=1 firing cell "
          f"({time.time()-t0:.0f}s elapsed)")

    with open(os.path.join(HERE, "_trackA_results_raw.json"), "w") as f:
        json.dump(results, f)
    print("  raw results checkpoint saved.")

    print("\n[4/7] Walk-forward config selection (train = earliest 60% of days, test = latest 40%) ...")
    uniq_dates = sorted(set(r["date"] for r in results))
    split_idx = int(len(uniq_dates) * 0.6)
    train_dates = set(uniq_dates[:split_idx])
    test_dates = set(uniq_dates[split_idx:])
    print(f"  {len(uniq_dates)} unique fired dates -> train={len(train_dates)} "
          f"({min(train_dates)}..{max(train_dates)}), test={len(test_dates)} "
          f"({min(test_dates)}..{max(test_dates)})")

    def pooled_fired(cell_key, date_filter=None):
        out = []
        for r in results:
            if date_filter is not None and r["date"] not in date_filter:
                continue
            c = r["cells"].get(cell_key)
            if c and c.get("fired") and "pnl" in c:
                out.append((r, c))
        return out

    train_cells = []
    for margin in MARGINS:
        for sustain in SUSTAINS:
            ck = f"{margin}_{sustain}"
            fired = pooled_fired(ck, train_dates)
            s = agg_stats(fired)
            if s["n_fired"] == 0:
                train_cells.append({"margin": margin, "sustain": sustain, "n": 0, "mean": None,
                                     "t": None, "p": None, "worst_case_ev": None})
                continue
            train_cells.append({"margin": margin, "sustain": sustain, "n": s["n_fired"],
                                 "mean": s["clustered"]["mean"], "t": s["clustered"]["t"],
                                 "p": s["clustered"]["p"], "worst_case_ev": s["analytic_ev_worst_case"]})
    bf = bonferroni_pick(train_cells)
    best_margin, best_sustain = bf["best"]["margin"], bf["best"]["sustain"]
    print(f"  TRAIN-selected config: margin={best_margin}, sustain={best_sustain}, "
          f"verdict={bf['verdict']} (n_train={bf['best']['n']})")

    best_key = f"{best_margin}_{best_sustain}"
    cons_key = "2_1"  # margin=2, sustain=1 conservative reference

    def full_view(cell_key):
        return {
            "train": agg_stats(pooled_fired(cell_key, train_dates)),
            "test": agg_stats(pooled_fired(cell_key, test_dates)),
            "full": agg_stats(pooled_fired(cell_key, None)),
        }

    best_view = full_view(best_key)
    cons_view = full_view(cons_key)

    def breakdown(cell_key, date_filter=None):
        fired = pooled_fired(cell_key, date_filter)
        by_family = {}
        for fam in ("HIGH", "LOW"):
            sub = [(r, c) for r, c in fired if r["family"] == fam]
            by_family[fam] = agg_stats(sub)
        by_ruggroup = {}
        for grp_label, grp_set in (("greater", {"greater"}), ("between_or_less", {"between", "less"})):
            sub = [(r, c) for r, c in fired if r["rung_group"] in grp_set]
            by_ruggroup[grp_label] = agg_stats(sub)
        return {"by_family": by_family, "by_rung_group": by_ruggroup}

    best_breakdown_full = breakdown(best_key, None)
    cons_breakdown_full = breakdown(cons_key, None)

    print("\n[5/7] Gap-decay / half-life + captured-EV-at-latency (best config, full sample) ...")
    best_fired_full = pooled_fired(best_key, None)
    decay_best = decay_curve(best_fired_full)
    latency_ev = {}
    for lat in [0, 1, 2, 5, 10, 30, 60]:
        latency_ev[str(lat)] = captured_ev_at_latency(best_fired_full, lat)

    cons_fired_full = pooled_fired(cons_key, None)
    decay_cons = decay_curve(cons_fired_full)

    print("\n[6/7] Predexon L2 depth sampling on a spread of real firing markets ...")
    key = predexon_key()
    depth_samples = []
    if key and best_fired_full:
        import random
        random.seed(42)
        sample_pairs = list(best_fired_full)
        random.shuffle(sample_pairs)
        sample_pairs = sample_pairs[:20]
        for r, c in sample_pairs:
            try:
                d = depth_for_fire(r, c, key)
            except Exception as e:
                d = {"ticker": r["ticker"], "error": str(e)}
            d["family"] = r["family"]
            d["city"] = r["city"]
            d["date"] = r["date"]
            depth_samples.append(d)
            time.sleep(0.05)
        print(f"  {len(depth_samples)} depth samples pulled "
              f"({sum(1 for d in depth_samples if 'error' not in d)} OK)")
    else:
        print("  [warn] no Predexon key or no fired events -- skipping depth sampling")

    print("\n[7/7] Writing report + summary ...")
    summary = {
        "window": {"actual_min": actual_min.isoformat(), "actual_max": actual_max.isoformat(),
                   "n_days": (actual_max - actual_min).days + 1},
        "counts": {"n_high_ladder_markets": n_high, "n_low_ladder_markets": n_low,
                   "n_jobs_analyzed": len(jobs), "n_rung_days_with_fires": len(results)},
        "glitch_removed_total_obs": glitch_removed_total,
        "walk_forward": {"train_dates_n": len(train_dates), "test_dates_n": len(test_dates),
                          "train_grid": train_cells, "bonferroni": bf,
                          "chosen_margin": best_margin, "chosen_sustain": best_sustain},
        "best_config": {"key": best_key, "views": best_view, "breakdown_full": best_breakdown_full,
                         "decay": decay_best, "latency_ev": latency_ev},
        "conservative_margin2_sustain1": {"key": cons_key, "views": cons_view,
                                           "breakdown_full": cons_breakdown_full, "decay": decay_cons},
        "predexon_depth_samples": depth_samples,
    }
    with open(OUT_SUMMARY, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"  wrote {OUT_SUMMARY}")
    print(f"\nDone in {time.time()-t0:.1f}s")
    return summary


if __name__ == "__main__":
    main()
