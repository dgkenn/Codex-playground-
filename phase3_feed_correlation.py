#!/usr/bin/env python3
"""
phase3_feed_correlation.py

TASK: validate that the LIVE observation feeds the Kalshi weather bot will actually run
on in production -- api.weather.gov 5-min (weathergov_feed.py) and aviationweather.gov
METAR (aviationweather_metar.py) -- HIGHLY CORRELATE with the OFFICIAL NWS CLI daily
max/min Kalshi settles on (KXHIGH/KXLOW), and to recalibrate the safe margin PER FEED.

WHY: the edge buys a Kalshi rung once the OBSERVED feed's running-max clears a strike,
trusting the official NWS CLI daily-max will also clear it. Track B (phase2_trackB_tail.py)
proved this is safe (~0.4% lock-failure) but used IEM 1-minute ASOS as the observed
source -- an archive with a 1-2 day publication lag that CANNOT be watched live. The two
candidates that CAN actually be polled live are api.weather.gov (5-min, ~7-day retention)
and aviationweather.gov METAR (hourly+specials, ~15-day retention). Both ultimately source
the same airport ASOS sensor as IEM's 1-min feed, but are different redistributions with
different resolution/rounding/QC -- this script measures whether that matters.

METHOD:
  1. Official NWS CLI daily high/low, THE SETTLEMENT GROUND TRUTH, fetched fresh from IEM's
     parsed-CLI-product JSON service (same source kalshi_wx_settlement_basis.py uses),
     re-parsed here to also keep the "low" field (that script only kept "high"). Only LST
     days that have FULLY ELAPSED as of the run time are used (so CLI is guaranteed
     finalized, not a mid-day partial value) -- computed per-station from each station's own
     UTC offset, not a single global cutoff.
  2. Three observed candidates, each reduced immediately to a compact per-station-day
     LST-day max/min (no raw-obs hoarding):
       - weathergov : api.weather.gov 5-min obs (weathergov_feed.fetch_obs), live-fetched,
                       actual retention ~7 days (measured below).
       - metar      : aviationweather.gov METAR (aviationweather_metar.fetch_metar),
                       live-fetched, actual retention ~15 days (measured below).
       - iem_raw1min / iem_glitch_sustain3 : IEM 1-min ASOS (kalshi_weather_nowcast.fetch_
                       asos_station, mostly cache-hit), RE-COMPUTED OVER THE SAME SHORT
                       OVERLAP WINDOW as the two live feeds (not the 6-year Track-B sample)
                       so the "0.4% baseline" comparison is apples-to-apples on identical
                       station-days, not just cited from a different, longer sample.
  3. Day-max/day-min accuracy vs official CLI: Pearson correlation, MAE, max AE, fraction of
     days |err|>=1F (the lock-relevant threshold), and signed bias (feed - CLI).
  4. Lock-failure re-measurement using the LIVE feeds as the trigger: same synthetic
     strike-ladder methodology as Track B (ladder anchored on the actual CLI value C,
     because there is no historical record of which exact strikes Kalshi would have listed
     on every day in this window) -- fired iff candidate's day-extreme clears K+/-margin;
     lock-failure iff fired AND the strike would NOT have been confirmed by the official CLI.
  5. Per-feed margin recommendation to hit Track B's ~0.4% Wilson-95 worst-case bar.

DISK DISCIPLINE: raw obs are fetched into memory, reduced to per-station-day compact
records, and the raw arrays are dropped; only the compact per-station-day JSON goes to
disk cache (a few KB/station), matching phase2_trackB_tail.py's approach.

Do NOT git commit (per task instructions). Author: automated research script.
"""
import os
import sys
import json
import math
import time
import statistics
from datetime import datetime, timedelta, timezone, date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import urllib.request                          # noqa: E402
import kalshi_weather_nowcast as base          # noqa: E402  CITY_CONFIG, ASOS fetch, slice_window, wilson bound
import kalshi_weather_refined as refined        # noqa: E402  glitch filter (clean_station_obs)
import kalshi_weather_expand as expand          # noqa: E402  LOW_CITY_CONFIG (KXLOW station map)
import weathergov_feed as wg                    # noqa: E402  LIVE feed #1: api.weather.gov 5-min
import aviationweather_metar as av              # noqa: E402  LIVE feed #2: aviationweather.gov METAR

CACHE_DIR = os.path.join(HERE, ".phase3_feed_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

OUT_MD = os.path.join(HERE, "phase3_feed_correlation.md")
OUT_JSON = os.path.join(HERE, "phase3_feed_correlation_summary.json")

CLI_BASE = "https://mesonet.agron.iastate.edu/json/cli.py"
CLI_STATION_OVERRIDE = {"NYC": "KNYC"}

MARGINS = [1, 2, 3, 4, 5, 6]
LADDER = [-3, -2, -1, 0, 1]          # near-money ladder anchored on CLI actual value (Track B's "near_money")
TARGET_LOCKFAIL = 0.004               # Track B's confirmed IEM baseline (glitch+sustain3 @ margin=1: 0.4%)
Z95 = 1.959963985

STATIONS = sorted(set(c["station"] for c in base.CITY_CONFIG.values()))
OFFSET_OF = {c["station"]: c["offset"] for c in base.CITY_CONFIG.values()}
NAME_OF = {c["station"]: c["name"] for c in base.CITY_CONFIG.values()}
# sanity: LOW_CITY_CONFIG must map to the identical station/offset set (verified, not assumed)
_low_offset = {c["station"]: c["offset"] for c in expand.LOW_CITY_CONFIG.values()}
assert _low_offset == OFFSET_OF, "KXLOW station/offset map diverges from KXHIGH map"


def cpath(name):
    return os.path.join(CACHE_DIR, name)


def load_c(name):
    p = cpath(name)
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_c(name, obj):
    with open(cpath(name), "w") as f:
        json.dump(obj, f)


# ---------------------------------------------------------------------------
# 1. Official CLI daily high+low (settlement ground truth), fresh fetch (keeps "low" too --
#    kalshi_wx_settlement_basis.py's cache only kept "high").
# ---------------------------------------------------------------------------

def fetch_cli_hilo_year(station, year):
    cli_station = CLI_STATION_OVERRIDE.get(station, station)
    cache_key = f"cli_hilo_{cli_station}_{year}.json"
    cached = load_c(cache_key)
    if cached is not None:
        return cached
    url = f"{CLI_BASE}?station={cli_station}&year={year}"
    d = base.http_get_json(url)
    out = {}
    for r in d.get("results", []):
        v = r.get("valid")
        if v is None:
            continue
        h = r.get("high")
        lo = r.get("low")
        out[v] = {
            "high": h if isinstance(h, (int, float)) else None,
            "low": lo if isinstance(lo, (int, float)) else None,
        }
    save_c(cache_key, out)
    return out


def last_complete_lst_date(offset, now_utc):
    """Latest LST calendar date for this station's UTC offset whose 24h window has fully
    elapsed as of now_utc -- i.e. the newest date the official CLI can possibly have
    finalized. Prevents scoring a mid-day partial value as if it were the settled high/low."""
    d = now_utc.date()
    while True:
        start_local = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        start_utc = start_local - timedelta(hours=offset)
        end_utc = start_utc + timedelta(days=1)
        if end_utc <= now_utc:
            return d
        d -= timedelta(days=1)


def lst_bounds(d, offset):
    start_local = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    start_utc = start_local - timedelta(hours=offset)
    return start_utc, start_utc + timedelta(days=1)


# ---------------------------------------------------------------------------
# 2. Glitch-filtered + sustain-3 IEM candidate (Track B's confirmed-0.4% recipe), local copy
# ---------------------------------------------------------------------------

def sustained_extreme_k(obs_day, k, kind, max_gap_min=2.5):
    """Largest (max) / smallest (min) threshold T such that a run of >=k consecutive
    (gap-tolerant) obs all satisfy the T bound. k<=1 -> plain max/min. Identical logic to
    phase2_trackB_tail.sustained_max_k, generalized to min via a sign flip."""
    if not obs_day:
        return None
    if k <= 1:
        return max(v for _, v in obs_day) if kind == "max" else min(v for _, v in obs_day)
    n = len(obs_day)
    best = None
    for i in range(k - 1, n):
        ok = True
        for j in range(i - k + 2, i + 1):
            gap = (obs_day[j][0] - obs_day[j - 1][0]).total_seconds() / 60.0
            if gap > max_gap_min:
                ok = False
                break
        if not ok:
            continue
        window_vals = [obs_day[j][1] for j in range(i - k + 1, i + 1)]
        if kind == "max":
            wextreme = min(window_vals)  # weakest member of the run bounds the sustained max
            if best is None or wextreme > best:
                best = wextreme
        else:
            wextreme = max(window_vals)
            if best is None or wextreme < best:
                best = wextreme
    return best


# ---------------------------------------------------------------------------
# 3. Per-station fetch: weathergov (live), metar (live), IEM 1-min (mostly cache-hit)
# ---------------------------------------------------------------------------

def fetch_weathergov_station(station, start_utc, end_utc):
    """CHUNKED fetch, one calendar-day-ish window per HTTP call. IMPORTANT OPERATIONAL FINDING
    (measured, not documented anywhere in weathergov_feed.py): api.weather.gov's /observations
    endpoint SILENTLY CAPS at 500 records per request -- a single request spanning the full
    ~7-day window returns only the most recent ~500 obs (for a 5-min-cadence station that's
    ~1.7 days, NOT 7), with no error/warning. A wide single-shot call therefore silently
    truncates history. Chunking in <=24h windows (well under the 288 obs/day a 5-min station
    can produce) avoids the cap and recovers the true ~7-day retention."""
    out = []
    t = start_utc
    while t < end_utc:
        t_next = min(t + timedelta(hours=24), end_utc)
        for attempt in range(3):
            try:
                chunk = wg.fetch_obs(station, t, t_next)
                out.extend(chunk)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"    [warn] weathergov chunk fetch failed {station} {t}: {e}", file=sys.stderr)
                else:
                    time.sleep(1.0)
        t = t_next
    out = sorted(set(out), key=lambda x: x[0])
    return out


def fetch_metar_chunk(station, end_utc, hours=48):
    """Direct aviationweather.gov call using its `date` (end-of-window) + `hours` (lookback)
    params -- aviationweather_metar.fetch_metar() only exposes `hours` relative to NOW, so it
    cannot reach further back than its own 400-record-per-request cap (measured: a single
    hours=15*24 call truncates at 400 rows, ~14 days for a busy-METAR station like KATL, not
    the full window). Chunking with explicit `date` recovers the true retention. Reuses
    aviationweather_metar's alias/UA/SSL-context internals so behavior matches the live module."""
    sid = av._STATION_ALIAS.get(station, station)
    if len(sid) == 3 and not sid.startswith("K"):
        sid = "K" + sid
    ds = end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{av._API}?ids={sid}&format=json&date={ds}&hours={int(hours)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "wx-research"})
    data = json.load(urllib.request.urlopen(req, timeout=30, context=av._CTX))
    out = []
    for r in data:
        t = r.get("temp")
        ts = r.get("reportTime") or r.get("obsTime")
        if t is None or ts is None:
            continue
        try:
            if isinstance(ts, (int, float)):
                when = datetime.fromtimestamp(ts, tz=timezone.utc)
            else:
                when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        out.append((when, av._c_to_f(float(t))))
    return out


def fetch_metar_station_live(station, start_utc, end_utc):
    out = []
    t = start_utc
    while t < end_utc:
        t_next = min(t + timedelta(hours=48), end_utc)
        for attempt in range(3):
            try:
                out.extend(fetch_metar_chunk(station, t_next, hours=48))
                break
            except Exception as e:
                if attempt == 2:
                    print(f"    [warn] metar chunk fetch failed {station} {t_next}: {e}", file=sys.stderr)
                else:
                    time.sleep(1.0)
        t = t_next
    out = sorted(set(out), key=lambda x: x[0])
    return out


def day_extreme(series, start_utc, end_utc, kind):
    obs = base.slice_window(series, start_utc, end_utc)
    if not obs:
        return None, 0
    vals = [v for _, v in obs]
    return (max(vals) if kind == "max" else min(vals)), len(obs)


# ---------------------------------------------------------------------------
# 4. Main data build: one compact record per (station, date)
# ---------------------------------------------------------------------------

def build_station_records(station, now_utc):
    offset = OFFSET_OF[station]
    cutoff = last_complete_lst_date(offset, now_utc)

    # generous fetch windows; actual usable days are whatever each feed truly returns
    wg_start = now_utc - timedelta(days=10)
    wg_obs = fetch_weathergov_station(station, wg_start, now_utc + timedelta(hours=2))

    metar_start = now_utc - timedelta(days=18)
    metar_obs = fetch_metar_station_live(station, metar_start, now_utc + timedelta(hours=2))

    iem_start = now_utc - timedelta(days=18)
    iem_raw = base.fetch_asos_station(station, iem_start, now_utc + timedelta(days=1))
    iem_clean, iem_removed = refined.clean_station_obs(iem_raw) if iem_raw else ([], [])

    if wg_obs:
        wg_first_date = wg_obs[0][0].date()
    else:
        wg_first_date = None
    if metar_obs:
        metar_first_date = metar_obs[0][0].date()
    else:
        metar_first_date = None

    cli_hilo = fetch_cli_hilo_year(station, now_utc.year)
    # also pull prior year in case window straddles Jan 1 (harmless if not needed)
    if now_utc.month == 1:
        cli_hilo_prev = fetch_cli_hilo_year(station, now_utc.year - 1)
        merged = dict(cli_hilo_prev)
        merged.update(cli_hilo)
        cli_hilo = merged

    records = []
    # scan back up to 20 days from cutoff -- covers both the wg (~7d) and metar (~15d) windows
    d = cutoff
    for _ in range(20):
        start_utc, end_utc = lst_bounds(d, offset)
        cli = cli_hilo.get(d.isoformat())
        cli_high = cli.get("high") if cli else None
        cli_low = cli.get("low") if cli else None

        wg_max, wg_n = day_extreme(wg_obs, start_utc, end_utc, "max")
        wg_min, _ = day_extreme(wg_obs, start_utc, end_utc, "min")
        metar_max, metar_n = day_extreme(metar_obs, start_utc, end_utc, "max")
        metar_min, _ = day_extreme(metar_obs, start_utc, end_utc, "min")

        iem_raw_day = base.slice_window(iem_raw, start_utc, end_utc) if iem_raw else []
        iem_clean_day = base.slice_window(iem_clean, start_utc, end_utc) if iem_clean else []
        iem_raw_max = max((v for _, v in iem_raw_day), default=None)
        iem_raw_min = min((v for _, v in iem_raw_day), default=None)
        iem_s3_max = sustained_extreme_k(iem_clean_day, 3, "max")
        iem_s3_min = sustained_extreme_k(iem_clean_day, 3, "min")

        records.append({
            "station": station, "date": d.isoformat(),
            "cli_high": cli_high, "cli_low": cli_low,
            "wg_max": wg_max, "wg_min": wg_min, "wg_n": wg_n,
            "metar_max": metar_max, "metar_min": metar_min, "metar_n": metar_n,
            "iem_raw_max": iem_raw_max, "iem_raw_min": iem_raw_min,
            "iem_s3_max": iem_s3_max, "iem_s3_min": iem_s3_min,
            "iem_n": len(iem_raw_day),
        })
        d -= timedelta(days=1)

    return records, {
        "wg_first_obs_date": wg_first_date.isoformat() if wg_first_date else None,
        "metar_first_obs_date": metar_first_date.isoformat() if metar_first_date else None,
        "cutoff_date": cutoff.isoformat(),
        "iem_glitch_removed": len(iem_removed) if iem_raw else 0,
        "iem_n_raw": len(iem_raw) if iem_raw else 0,
    }


# ---------------------------------------------------------------------------
# 5. Accuracy stats (correlation / MAE / bias / %days>=1F) vs official CLI
# ---------------------------------------------------------------------------

def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def accuracy_stats(pairs):
    """pairs: list of (feed_val, cli_val). Returns dict or None if empty."""
    if not pairs:
        return None
    feed = [p[0] for p in pairs]
    cli = [p[1] for p in pairs]
    errs = [f - c for f, c in pairs]
    abs_errs = [abs(e) for e in errs]
    n = len(pairs)
    return {
        "n": n,
        "pearson_r": pearson(feed, cli),
        "mean_bias_F": sum(errs) / n,
        "mean_abs_error_F": sum(abs_errs) / n,
        "max_abs_error_F": max(abs_errs),
        "median_abs_error_F": statistics.median(abs_errs),
        "frac_days_abs_err_ge_1F": sum(1 for e in abs_errs if e >= 1.0) / n,
        "frac_days_exact": sum(1 for e in errs if e == 0) / n,
        "frac_over_read": sum(1 for e in errs if e > 0) / n,
        "frac_under_read": sum(1 for e in errs if e < 0) / n,
    }


def gather_pairs(records, feed_field, cli_field, min_n_obs=None, n_field=None):
    pairs = []
    for r in records:
        fv = r.get(feed_field)
        cv = r.get(cli_field)
        if fv is None or cv is None:
            continue
        if min_n_obs is not None and n_field is not None and (r.get(n_field) or 0) < min_n_obs:
            continue
        pairs.append((fv, cv))
    return pairs


# ---------------------------------------------------------------------------
# 6. Lock-failure ladder test (Track B methodology, applied to each candidate)
# ---------------------------------------------------------------------------

def lockfail_eval(records, feed_field, cli_field, kind, margins=MARGINS, ladder=LADDER):
    """For each record with both feed value and CLI ground truth, sweep the near-money
    ladder anchored on C=round(CLI actual). fired iff feed's day-extreme clears K by margin;
    lockfail iff fired AND CLI would NOT confirm strike K."""
    agg = {m: {"n_fired": 0, "n_lockfail": 0} for m in margins}
    for r in records:
        val = r.get(feed_field)
        cli_v = r.get(cli_field)
        if val is None or cli_v is None:
            continue
        C = int(round(cli_v))
        for m in margins:
            for off in ladder:
                K = C + off
                if kind == "max":
                    fired = val >= K + m
                    lockfail = fired and (K >= C)
                else:
                    fired = val <= K - m
                    lockfail = fired and (K <= C)
                if fired:
                    agg[m]["n_fired"] += 1
                    if lockfail:
                        agg[m]["n_lockfail"] += 1
    out = {}
    for m in margins:
        n = agg[m]["n_fired"]
        k = agg[m]["n_lockfail"]
        out[m] = {
            "n_fired": n, "n_lockfail": k,
            "cond_loss_rate": (k / n) if n else None,
            "worst_case_wilson95": base.wilson_upper_bound(k, n, Z95) if n else None,
        }
    return out


def margin_needed_for_target(lockfail_by_margin, target=TARGET_LOCKFAIL, min_n=20):
    for m in sorted(lockfail_by_margin.keys()):
        c = lockfail_by_margin[m]
        if c["n_fired"] >= min_n and c["worst_case_wilson95"] is not None and c["worst_case_wilson95"] <= target:
            return m
    return None


# ---------------------------------------------------------------------------
# 7. Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    now_utc = datetime.now(timezone.utc)
    print("=== Phase 3: LIVE feed (api.weather.gov, aviationweather.gov METAR) vs official CLI ===")
    print(f"Run time (UTC): {now_utc.isoformat()}")
    print(f"Stations ({len(STATIONS)}): {STATIONS}\n")

    all_records = []
    meta = {}
    for i, st in enumerate(STATIONS, 1):
        t1 = time.time()
        recs, m = build_station_records(st, now_utc)
        meta[st] = m
        all_records.extend(recs)
        print(f"  [{i}/{len(STATIONS)}] {st:5s} ({NAME_OF[st]:26s}) wg_first={m['wg_first_obs_date']} "
              f"metar_first={m['metar_first_obs_date']} cutoff={m['cutoff_date']} "
              f"iem_glitch_removed={m['iem_glitch_removed']} [{time.time()-t1:.1f}s]")

    print(f"\nTotal compact station-day records: {len(all_records)}")

    # windows: weathergov usable days require wg_n>0 (and by construction, station-days
    # beyond wg's true retention naturally have wg_n=0 and are excluded via gather_pairs).
    # Use a coverage floor to avoid single-obs noise days (weathergov falls back to hourly
    # for some stations per its own docstring -- floor=3 obs/day is permissive enough to
    # keep those stations while excluding true no-data days).
    WG_MIN_OBS = 3
    METAR_MIN_OBS = 3

    summary = {"run_time_utc": now_utc.isoformat(), "n_stations": len(STATIONS),
               "station_meta": meta, "n_records": len(all_records)}

    # ---- 3. Day-max / day-min accuracy vs CLI, pooled + per-station -----------------
    feeds_max = {
        "weathergov_5min": ("wg_max", "wg_n", WG_MIN_OBS),
        "metar_aviationwx": ("metar_max", "metar_n", METAR_MIN_OBS),
        "iem_raw1min": ("iem_raw_max", "iem_n", 1),
        "iem_glitch_sustain3": ("iem_s3_max", "iem_n", 1),
    }
    feeds_min = {
        "weathergov_5min": ("wg_min", "wg_n", WG_MIN_OBS),
        "metar_aviationwx": ("metar_min", "metar_n", METAR_MIN_OBS),
        "iem_raw1min": ("iem_raw_min", "iem_n", 1),
        "iem_glitch_sustain3": ("iem_s3_min", "iem_n", 1),
    }

    def pooled_and_per_station(feeds_map, cli_field):
        pooled = {}
        per_station = {}
        for label, (field, nfield, minobs) in feeds_map.items():
            pooled[label] = accuracy_stats(gather_pairs(all_records, field, cli_field, minobs, nfield))
            per_station[label] = {}
            for st in STATIONS:
                st_recs = [r for r in all_records if r["station"] == st]
                pairs = gather_pairs(st_recs, field, cli_field, minobs, nfield)
                per_station[label][st] = accuracy_stats(pairs)
        return pooled, per_station

    pooled_max, per_station_max = pooled_and_per_station(feeds_max, "cli_high")
    pooled_min, per_station_min = pooled_and_per_station(feeds_min, "cli_low")
    summary["accuracy_vs_cli_max_pooled"] = pooled_max
    summary["accuracy_vs_cli_max_per_station"] = per_station_max
    summary["accuracy_vs_cli_min_pooled"] = pooled_min
    summary["accuracy_vs_cli_min_per_station"] = per_station_min

    # ---- 4. Lock-failure ladder test, pooled ------------------------------------
    lockfail_max = {}
    lockfail_min = {}
    for label, (field, nfield, minobs) in feeds_max.items():
        recs_ok = [r for r in all_records if (r.get(nfield) or 0) >= minobs]
        lockfail_max[label] = lockfail_eval(recs_ok, field, "cli_high", "max")
    for label, (field, nfield, minobs) in feeds_min.items():
        recs_ok = [r for r in all_records if (r.get(nfield) or 0) >= minobs]
        lockfail_min[label] = lockfail_eval(recs_ok, field, "cli_low", "min")
    summary["lockfail_max_by_feed_margin"] = lockfail_max
    summary["lockfail_min_by_feed_margin"] = lockfail_min

    # ---- 5. Margin needed per feed for ~0.4% target -------------------------------
    summary["margin_needed_max"] = {label: margin_needed_for_target(lockfail_max[label]) for label in feeds_max}
    summary["margin_needed_min"] = {label: margin_needed_for_target(lockfail_min[label]) for label in feeds_min}

    with open(OUT_JSON, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    write_report(summary, feeds_max, feeds_min)
    print(f"\nDone in {time.time()-t0:.1f}s")
    print(f"  {OUT_JSON}")
    print(f"  {OUT_MD}")


# ---------------------------------------------------------------------------
# 8. Report
# ---------------------------------------------------------------------------

def fmt(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, float) and math.isnan(x):
        return "n/a"
    return f"{x:.{nd}f}"


def pct(x, nd=2):
    if x is None:
        return "n/a"
    return f"{100*x:.{nd}f}%"


def write_report(summary, feeds_max, feeds_min):
    L = []
    L.append("# Phase 3: Live-Feed vs Official-CLI Correlation + Lock-Failure Recalibration\n")
    L.append(f"Run time (UTC): {summary['run_time_utc']}. Stations: {summary['n_stations']}. "
             f"Compact station-day records built: {summary['n_records']}.\n")

    L.append("## Per-station feed coverage (proves/disproves the retention-window claims)\n")
    L.append("| station | city | wg first obs | metar first obs | LST cutoff date | IEM glitch-removed | IEM raw n |")
    L.append("|---|---|---|---|---|---|---|")
    for st, m in summary["station_meta"].items():
        L.append(f"| {st} | {NAME_OF[st]} | {m['wg_first_obs_date']} | {m['metar_first_obs_date']} | "
                 f"{m['cutoff_date']} | {m['iem_glitch_removed']} | {m['iem_n_raw']} |")

    def acc_table(pooled, title):
        L.append(f"\n### {title}\n")
        L.append("| feed | n days | Pearson r | mean bias (F) | MAE (F) | median AE (F) | max AE (F) | "
                 "%days &#124;err&#124;>=1F | over-read % | under-read % |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for label, a in pooled.items():
            if a is None:
                L.append(f"| {label} | 0 | - | - | - | - | - | - | - | - |")
                continue
            L.append(f"| {label} | {a['n']} | {fmt(a['pearson_r'],4)} | {fmt(a['mean_bias_F'],3)} | "
                     f"{fmt(a['mean_abs_error_F'],3)} | {fmt(a['median_abs_error_F'],2)} | "
                     f"{fmt(a['max_abs_error_F'],1)} | {pct(a['frac_days_abs_err_ge_1F'])} | "
                     f"{pct(a['frac_over_read'])} | {pct(a['frac_under_read'])} |")
        L.append("\n(bias > 0 = feed reads HIGH vs official CLI -- the dangerous direction; "
                 "bias < 0 = feed reads LOW -- the safe/conservative direction.)\n")

    L.append("\n## 1+2. Day-max/day-min accuracy vs official CLI + direction of bias (POOLED, all stations)\n")
    acc_table(summary["accuracy_vs_cli_max_pooled"], "KXHIGH (day MAX) -- pooled across stations")
    acc_table(summary["accuracy_vs_cli_min_pooled"], "KXLOW (day MIN) -- pooled across stations")

    L.append("\n## Per-station worst offenders (KXHIGH / day-max), weathergov and metar\n")
    for label in ("weathergov_5min", "metar_aviationwx"):
        rows = []
        for st, a in summary["accuracy_vs_cli_max_per_station"][label].items():
            if a is None or a["n"] < 2:
                continue
            rows.append((st, a))
        rows.sort(key=lambda x: -(x[1]["mean_abs_error_F"] or 0))
        L.append(f"\n### {label} -- ranked by MAE, worst first\n")
        L.append("| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |")
        L.append("|---|---|---|---|---|---|---|")
        for st, a in rows:
            L.append(f"| {st} | {a['n']} | {fmt(a['pearson_r'],3)} | {fmt(a['mean_bias_F'],2)} | "
                     f"{fmt(a['mean_abs_error_F'],2)} | {fmt(a['max_abs_error_F'],1)} | "
                     f"{pct(a['frac_days_abs_err_ge_1F'])} |")

    L.append("\n## Per-station worst offenders (KXLOW / day-min), weathergov and metar\n")
    for label in ("weathergov_5min", "metar_aviationwx"):
        rows = []
        for st, a in summary["accuracy_vs_cli_min_per_station"][label].items():
            if a is None or a["n"] < 2:
                continue
            rows.append((st, a))
        rows.sort(key=lambda x: -(x[1]["mean_abs_error_F"] or 0))
        L.append(f"\n### {label} -- ranked by MAE, worst first\n")
        L.append("| station | n days | Pearson r | mean bias (F) | MAE (F) | max AE (F) | %days>=1F |")
        L.append("|---|---|---|---|---|---|---|")
        for st, a in rows:
            L.append(f"| {st} | {a['n']} | {fmt(a['pearson_r'],3)} | {fmt(a['mean_bias_F'],2)} | "
                     f"{fmt(a['mean_abs_error_F'],2)} | {fmt(a['max_abs_error_F'],1)} | "
                     f"{pct(a['frac_days_abs_err_ge_1F'])} |")

    def lockfail_table(lockfail, title):
        L.append(f"\n### {title}\n")
        L.append("| feed | margin | n fired | n lock-fail | cond. loss rate | worst-case (Wilson-95) |")
        L.append("|---|---|---|---|---|---|")
        for label, by_m in lockfail.items():
            for m, c in by_m.items():
                if c["n_fired"] == 0:
                    L.append(f"| {label} | {m} | 0 | - | - | - |")
                    continue
                L.append(f"| {label} | {m} | {c['n_fired']} | {c['n_lockfail']} | "
                         f"{pct(c['cond_loss_rate'])} | {pct(c['worst_case_wilson95'])} |")

    L.append("\n## 3. Live-feed lock-failure test (near-money ladder C-3..C+1 anchored on official CLI)\n")
    L.append("fired iff feed's LST-day running extreme clears strike K by the margin; lock-failure iff "
             "fired AND the official CLI would NOT have confirmed strike K. Track B's published IEM "
             "6-year multi-season baseline for context: glitch+sustain3 @ margin=1 -> 0.4% cond. loss, "
             "0.4% Wilson-95 worst case (n=93785). Below: SAME ladder methodology, but IEM recomputed on "
             "the IDENTICAL short overlap window as the two live feeds (not the 6-year sample), for a "
             "true apples-to-apples comparison.\n")
    lockfail_table(summary["lockfail_max_by_feed_margin"], "KXHIGH (day MAX)")
    lockfail_table(summary["lockfail_min_by_feed_margin"], "KXLOW (day MIN)")

    L.append("\n## 4. Margin needed per feed to hit the ~0.4% Wilson-95 safety bar (min n_fired=20)\n")
    L.append("| feed | margin needed (KXHIGH) | margin needed (KXLOW) |")
    L.append("|---|---|---|")
    for label in feeds_max:
        mh = summary["margin_needed_max"].get(label)
        ml = summary["margin_needed_min"].get(label)
        L.append(f"| {label} | {mh if mh is not None else 'NOT REACHED in 1-6F tested'} | "
                 f"{ml if ml is not None else 'NOT REACHED in 1-6F tested'} |")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
