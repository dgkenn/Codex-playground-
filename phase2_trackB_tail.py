#!/usr/bin/env python3
"""
Phase 2 / Track B -- multi-year, all-season obs-vs-CLI "lock failure" tail measurement.

WHY: Kalshi KXHIGH price history is ~10 weeks, warm-season-only (May-Jul 2026), so the
price-based backtest (kalshi_weather_refined.py / kalshi_wx_settlement_basis.py) cannot see
what happens in winter (radiational cooling, frontal passages, big diurnal swings). But raw
ASOS 1-minute obs and NWS CLI daily-max reports are both available multi-year, independent of
whether Kalshi ever listed a market that day. This script measures, directly from those two
public datasets across 2021-2026 and all four seasons, how often the ASOS-observed "running
max cleared strike+margin, sustained" signal disagrees with the officially-settled CLI daily
high -- the mechanism behind the price-backtest's measured tail (conditional loss ~38% @
margin=1, ~8.6% @ margin=2 on the warm-season-only sample).

DESIGN NOTE ON SYNTHETIC STRIKES: unlike the real-market backtest, there is no historical
record of which integer strikes Kalshi would have listed on any given day in 2021-2025 (Kalshi
KXHIGH did not exist that far back). We approximate the population of "plausible pre-set
strikes a market-maker would have listed based on a day-ahead forecast" with a ladder of
integers anchored on the *actual* CLI high C for that day (a reasonable proxy for a skillful
forecast, which is unbiased around the eventual outcome on average): a NEAR_MONEY ladder
{C-3,C-2,C-1,C,C+1} and a WIDE ladder {C-6..C+3} for sensitivity. This is a modeling choice,
stated explicitly, not a fact -- see the report for the sensitivity table. We ALSO report the
ladder-width-independent day-level flag (did the obs sustained value clear C+margin at all,
i.e. would the single most-exposed at-the-money strike have failed) as a cross-check.

DISK DISCIPLINE: raw 1-minute ASOS / METAR text for a station-year (~20MB / ~3MB) is fetched
into memory, reduced immediately to one compact JSON record per station-day (~200 bytes), and
the raw arrays are discarded (go out of scope) before the next station-year is fetched. Only
the compact per-station-year summaries are cached to disk (.tailrisk_cache/), a few KB each.
"""
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kalshi_weather_nowcast as base          # noqa: E402  (CITY_CONFIG, http fetch, slice_window, wilson bound)
import kalshi_weather_refined as refined        # noqa: E402  (glitch filter)
import kalshi_wx_settlement_basis as basis      # noqa: E402  (CLI fetch/cache)

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, ".tailrisk_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

OUT_MD = os.path.join(HERE, "phase2_trackB_tail_results.md")

ASOS_METAR_BASE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
MARGINS = [1, 2, 3]
CANDIDATES = ["raw1min", "glitch1", "glitch_sustain3", "roll3", "metar_gated"]
LADDERS = {
    "near_money": [-3, -2, -1, 0, 1],
    "wide": [-6, -5, -4, -3, -2, -1, 0, 1, 2, 3],
}

SEASON_OF_MONTH = {12: "DJF", 1: "DJF", 2: "DJF",
                    3: "MAM", 4: "MAM", 5: "MAM",
                    6: "JJA", 7: "JJA", 8: "JJA",
                    9: "SON", 10: "SON", 11: "SON"}


def cpath(name):
    return os.path.join(CACHE_DIR, name)


def load_compact(name):
    p = cpath(name)
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_compact(name, obj):
    with open(cpath(name), "w") as f:
        json.dump(obj, f)


def station_offset_map():
    m = {}
    for series, cfg in base.CITY_CONFIG.items():
        m[cfg["station"]] = {"offset": cfg["offset"], "name": cfg["name"]}
    return m


def parse_onlycomma(text, time_col, val_col, min_cols):
    out = []
    for line in text.splitlines():
        if not line or line.startswith("station,"):
            continue
        parts = line.split(",")
        if len(parts) < min_cols:
            continue
        valid, val = parts[time_col], parts[val_col]
        if val in ("", "M"):
            continue
        try:
            t = datetime.strptime(valid.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            v = float(val)
        except ValueError:
            continue
        out.append((t, v))
    out.sort(key=lambda x: x[0])
    return out


def fetch_asos1min_year_raw(station, year):
    """In-memory only -- NOT cached to disk (that's the .nowcast_cache's job for the live
    warm-season window; here we'd blow the disk budget caching 6 years x 20 stations of raw
    1-min text). Returns sorted (dt, tmpf) list."""
    sid = base.asos1min_id(station)
    today = datetime.now(timezone.utc).date()
    end_date = min(date(year + 1, 1, 1), today + timedelta(days=1))
    sts = f"{year}-01-01T00:00Z"
    ets = end_date.strftime("%Y-%m-%dT%H:%MZ")
    url = f"{base.ASOS_BASE}?station={sid}&vars=tmpf&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma"
    text = base.http_get_text(url, timeout=90)
    return parse_onlycomma(text, 2, 3, 4)


def fetch_metar_year_raw(station, year):
    today = datetime.now(timezone.utc).date()
    end_date = min(date(year + 1, 1, 1), today + timedelta(days=1))
    sts = f"{year}-01-01T00:00Z"
    ets = end_date.strftime("%Y-%m-%dT%H:%MZ")
    url = (f"{ASOS_METAR_BASE}?station={station}&data=tmpf&sts={sts}&ets={ets}"
           f"&tz=UTC&format=onlycomma&missing=M&latlon=no")
    text = base.http_get_text(url, timeout=90)
    return parse_onlycomma(text, 1, 2, 3)


def rolling_mean_series(obs_sorted, window_minutes):
    from collections import deque
    dq = deque()
    total = 0.0
    out = []
    for t, v in obs_sorted:
        dq.append((t, v))
        total += v
        cutoff = t - timedelta(minutes=window_minutes)
        while dq and dq[0][0] < cutoff:
            _, vv = dq.popleft()
            total -= vv
        out.append((t, total / len(dq)))
    return out


def sustained_max_k(obs_day, k, max_gap_min=2.5):
    """Largest threshold T such that a run of >=k consecutive (gap-tolerant) obs is all >= T.
    Equivalent to max-over-valid-windows-of-window-min. k=1 -> plain max."""
    if not obs_day:
        return None
    if k <= 1:
        return max(v for _, v in obs_day)
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
        wmin = min(obs_day[j][1] for j in range(i - k + 1, i + 1))
        if best is None or wmin > best:
            best = wmin
    return best


def daterange(y):
    d0 = date(y, 1, 1)
    today = datetime.now(timezone.utc).date()
    d1 = date(y, 12, 31) if y < today.year else (today - timedelta(days=1))
    d = d0
    out = []
    while d <= d1:
        out.append(d)
        d += timedelta(days=1)
    return out


def process_station_year(station, year, offset, cli_map):
    cache_name = f"daily_{station}_{year}.json"
    cached = load_compact(cache_name)
    if cached is not None:
        return cached

    t0 = time.time()
    try:
        raw_obs = fetch_asos1min_year_raw(station, year)
    except Exception as e:
        print(f"    [warn] ASOS fetch failed {station} {year}: {e}", file=sys.stderr)
        raw_obs = []
    try:
        metar_obs = fetch_metar_year_raw(station, year)
    except Exception as e:
        print(f"    [warn] METAR fetch failed {station} {year}: {e}", file=sys.stderr)
        metar_obs = []

    cleaned_obs, removed = refined.clean_station_obs(raw_obs) if raw_obs else ([], [])
    roll3_series = rolling_mean_series(cleaned_obs, 3) if cleaned_obs else []

    records = []
    for d in daterange(year):
        start_utc = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) - timedelta(hours=offset)
        end_utc = start_utc + timedelta(days=1)
        raw_day = base.slice_window(raw_obs, start_utc, end_utc) if raw_obs else []
        clean_day = base.slice_window(cleaned_obs, start_utc, end_utc) if cleaned_obs else []
        roll3_day = base.slice_window(roll3_series, start_utc, end_utc) if roll3_series else []
        metar_day = base.slice_window(metar_obs, start_utc, end_utc) if metar_obs else []
        if not raw_day and not metar_day:
            continue
        cli_high = cli_map.get(d.isoformat())
        raw_max = max(v for _, v in raw_day) if raw_day else None
        clean_max = max(v for _, v in clean_day) if clean_day else None
        sustain3_max = sustained_max_k(clean_day, 3)
        roll3_max = max(v for _, v in roll3_day) if roll3_day else None
        metar_max = max(v for _, v in metar_day) if metar_day else None
        records.append({
            "date": d.isoformat(), "cli_high": cli_high,
            "raw_max": raw_max, "clean_max": clean_max, "sustain3_max": sustain3_max,
            "roll3_max": roll3_max, "metar_max": metar_max,
            "n_raw": len(raw_day), "n_metar": len(metar_day),
        })

    save_compact(cache_name, records)
    print(f"    {station} {year}: {len(records)} days  "
          f"(raw_obs={len(raw_obs)}, metar_obs={len(metar_obs)}, glitch_removed={len(removed)})  "
          f"[{time.time()-t0:.1f}s]")
    # explicitly drop references (helps peak-memory bookkeeping even though GC would anyway)
    del raw_obs, metar_obs, cleaned_obs, roll3_series
    return records


def wilson95(k, n):
    if n == 0:
        return None
    return base.wilson_upper_bound(k, n, 1.959963985)


def season_of(iso_date):
    m = int(iso_date[5:7])
    return SEASON_OF_MONTH[m]


CAND_FIELD = {
    "raw1min": "raw_max",
    "glitch1": "clean_max",
    "glitch_sustain3": "sustain3_max",
    "roll3": "roll3_max",
}


def evaluate_record(rec, station, agg):
    cli_high = rec.get("cli_high")
    if cli_high is None:
        return
    try:
        C = int(round(cli_high))
    except Exception:
        return
    season = season_of(rec["date"])
    raw_max = rec.get("raw_max")
    metar_max = rec.get("metar_max")

    for cand in CANDIDATES:
        if cand == "metar_gated":
            val = raw_max
        else:
            val = rec.get(CAND_FIELD[cand])
        if val is None:
            continue
        for margin in MARGINS:
            for ladder_name, offsets in LADDERS.items():
                for off in offsets:
                    K = C + off
                    if cand == "metar_gated":
                        fired = (raw_max is not None and raw_max >= K + margin
                                  and metar_max is not None and metar_max >= K)
                    else:
                        fired = val >= K + margin
                    if not fired:
                        continue
                    lockfail = (K >= C)  # deterministic given off>=0
                    for scope in (("ALL",), (season,), (season, station), ("STA", station)):
                        key = (cand, margin, ladder_name) + scope
                        a = agg[key]
                        a["n_fired"] += 1
                        if lockfail:
                            a["n_lockfail"] += 1

    # ladder-independent day-level ATM-boundary flag (near_money-consistent: uses K=C exactly,
    # i.e. "would obs sustained value clear C+margin", the single most-exposed strike, no
    # ladder-width assumption at all)
    for cand in CANDIDATES:
        if cand == "metar_gated":
            val = raw_max
        else:
            val = rec.get(CAND_FIELD[cand])
        if val is None:
            continue
        for margin in MARGINS:
            if cand == "metar_gated":
                would_fail = (raw_max is not None and raw_max >= C + margin
                              and metar_max is not None and metar_max >= C)
            else:
                would_fail = val >= C + margin
            for scope in (("ALL",), (season,), (season, station)):
                key = ("DAYFLAG", cand, margin) + scope
                a = agg[key]
                a["n_days"] += 1
                if would_fail:
                    a["n_fail_days"] += 1


def main():
    t0 = time.time()
    print("=== Phase 2 / Track B: multi-year all-season obs-vs-CLI tail measurement ===")
    stmap = station_offset_map()
    stations = sorted(stmap.keys())
    print(f"Stations ({len(stations)}): {stations}")
    print(f"Years requested: {YEARS}")

    cli_tables = {}
    print("\n[1/3] CLI daily-max (settlement ground truth), all station-years ...")
    for st in stations:
        merged = {}
        for yr in YEARS:
            try:
                merged.update(basis.fetch_cli_year(st, yr))
            except Exception as e:
                print(f"  [warn] CLI {st} {yr} failed: {e}", file=sys.stderr)
        cli_tables[st] = merged
        print(f"  CLI {st}: {len(merged)} daily reports across {len(YEARS)} requested years")

    print("\n[2/3] Per-station-year ASOS 1-min + METAR fetch -> compact daily features "
          "(cached, raw discarded after each station-year) ...")
    all_records = []  # (station, record)
    n_sy = 0
    for st in stations:
        offset = stmap[st]["offset"]
        for yr in YEARS:
            n_sy += 1
            recs = process_station_year(st, yr, offset, cli_tables[st])
            for r in recs:
                all_records.append((st, r))
    print(f"\n  total station-years processed: {n_sy}")
    print(f"  total compact station-day records: {len(all_records)}")

    print("\n[3/3] Aggregating lock-failure / conditional-loss statistics ...")
    agg = defaultdict(lambda: defaultdict(int))
    n_with_cli = 0
    years_seen = set()
    for st, rec in all_records:
        if rec.get("cli_high") is not None:
            n_with_cli += 1
            years_seen.add(rec["date"][:4])
        evaluate_record(rec, st, agg)

    print(f"  station-days with CLI ground truth: {n_with_cli}")
    print(f"  years actually present in data: {sorted(years_seen)}")

    write_report(agg, stations, stmap, n_sy, len(all_records), n_with_cli, sorted(years_seen))
    print(f"\nDone in {time.time()-t0:.1f}s -> {OUT_MD}")


def fmt_pct(x, nd=1):
    if x is None:
        return "n/a"
    return f"{100*x:.{nd}f}%"


def cell(agg, cand, margin, ladder, *scope):
    key = (cand, margin, ladder) + scope
    a = agg.get(key)
    if a is None or a["n_fired"] == 0:
        return {"n_fired": 0, "n_lockfail": 0, "cond_loss": None, "wilson95": None}
    n_fired, n_lockfail = a["n_fired"], a["n_lockfail"]
    return {"n_fired": n_fired, "n_lockfail": n_lockfail,
            "cond_loss": n_lockfail / n_fired, "wilson95": wilson95(n_lockfail, n_fired)}


def dayflag_cell(agg, cand, margin, *scope):
    key = ("DAYFLAG", cand, margin) + scope
    a = agg.get(key)
    if a is None or a["n_days"] == 0:
        return {"n_days": 0, "n_fail_days": 0, "rate": None}
    return {"n_days": a["n_days"], "n_fail_days": a["n_fail_days"],
            "rate": a["n_fail_days"] / a["n_days"]}


def write_report(agg, stations, stmap, n_sy, n_records, n_with_cli, years_seen):
    L = []
    L.append("# Phase 2 / Track B -- Multi-Year, All-Season Obs-vs-CLI Tail Risk\n")
    L.append(f"Run date: {datetime.now(timezone.utc).isoformat()}\n")
    L.append("Measures the ASOS-observed-vs-official-CLI-settlement disagreement ('lock failure') "
              "that drives the Kalshi KXHIGH nowcast strategy's tail, across as many years and all "
              "four seasons as ASOS 1-min + NWS CLI data allow -- independent of Kalshi's own ~10-week, "
              "warm-season-only price history, which structurally cannot see this.\n")
    L.append(f"\n**Coverage:** {len(stations)} stations x years requested {YEARS} -> years actually "
             f"present in data: **{years_seen}**. Station-years processed: {n_sy}. Total compact "
             f"station-day records: {n_records}. Station-days with CLI ground truth: {n_with_cli}.\n")

    L.append("\n## Methodology notes\n")
    L.append("- **Candidates**: `raw1min` (unfiltered running max, sustain=1 -- the original live rule), "
              "`glitch1` (glitch-filter only, sustain=1), `glitch_sustain3` (glitch filter + 3-consecutive-"
              "minute sustain requirement), `roll3` (3-min trailing rolling MEAN of glitch-filtered obs), "
              "`metar_gated` (raw1min trigger, withheld until independently-published METAR max reaches "
              "the BARE strike).\n")
    L.append("- **Synthetic strike ladders** (no historical KXHIGH listings exist before 2026): "
              "`near_money` = strikes {C-3,C-2,C-1,C,C+1} anchored on the actual CLI high C for that day "
              "(a proxy for a day-ahead forecast, which is unbiased around the eventual outcome on "
              "average); `wide` = {C-6..C+3}. Widening the ladder mechanically DILUTES the conditional "
              "loss rate (adds strikes that are deep-in-the-money and essentially always correctly win), "
              "so `near_money` is the more representative number and `wide` is reported only as a "
              "sensitivity check -- both are shown below, be explicit this is a stated modeling choice.\n")
    L.append("- **Lock-failure**: for strike K, margin m: fired iff candidate's sustained value >= K+m "
              "(metar_gated additionally requires published METAR max >= K, bare); lock-failure iff fired "
              "AND K >= CLI_high (i.e. the strike settles NO under the official record).\n")
    L.append("- **DAYFLAG** (ladder-width-independent cross-check): per station-day, did the candidate's "
              "sustained value clear CLI_high+margin at all (equivalent to the single most-exposed "
              "at-the-money strike K=CLI_high)? This needs no ladder-width assumption.\n")

    # ---- Headline: raw1min, near_money, all margins, ALL seasons pooled ----
    L.append("\n## 1. Headline: raw1min baseline, all years/seasons pooled (near_money ladder)\n")
    L.append("| margin | n fired | n lock-fail | conditional loss (point) | Wilson-95 worst-case |\n")
    L.append("|---|---|---|---|---|\n")
    for m in MARGINS:
        c = cell(agg, "raw1min", m, "near_money", "ALL")
        L.append(f"| {m} | {c['n_fired']} | {c['n_lockfail']} | {fmt_pct(c['cond_loss'])} | "
                 f"{fmt_pct(c['wilson95'])} |\n")

    L.append("\nSame, `wide` ladder (sensitivity -- expect materially lower due to dilution):\n\n")
    L.append("| margin | n fired | n lock-fail | conditional loss (point) | Wilson-95 worst-case |\n")
    L.append("|---|---|---|---|---|\n")
    for m in MARGINS:
        c = cell(agg, "raw1min", m, "wide", "ALL")
        L.append(f"| {m} | {c['n_fired']} | {c['n_lockfail']} | {fmt_pct(c['cond_loss'])} | "
                 f"{fmt_pct(c['wilson95'])} |\n")

    # ---- All candidates x margin, near_money, pooled ----
    L.append("\n## 2. All candidates x margin, near_money ladder, all years/seasons pooled\n")
    L.append("| candidate | margin | n fired | n lock-fail | cond. loss | Wilson-95 |\n")
    L.append("|---|---|---|---|---|---|\n")
    for cand in CANDIDATES:
        for m in MARGINS:
            c = cell(agg, cand, m, "near_money", "ALL")
            L.append(f"| {cand} | {m} | {c['n_fired']} | {c['n_lockfail']} | "
                     f"{fmt_pct(c['cond_loss'])} | {fmt_pct(c['wilson95'])} |\n")

    # ---- DAYFLAG (ladder-free) ----
    L.append("\n## 3. Ladder-independent DAYFLAG cross-check (single ATM boundary strike K=CLI_high)\n")
    L.append("Fraction of ALL station-days (unconditional, not conditional on firing) where the "
              "candidate's sustained value cleared CLI_high+margin -- i.e. the single most-exposed "
              "at-the-money strike would have fired-and-lost, by definition (K=C always settles NO).\n\n")
    L.append("| candidate | margin | n days | n exposure-days | rate |\n")
    L.append("|---|---|---|---|---|\n")
    for cand in CANDIDATES:
        for m in MARGINS:
            c = dayflag_cell(agg, cand, m, "ALL")
            L.append(f"| {cand} | {m} | {c['n_days']} | {c['n_fail_days']} | {fmt_pct(c['rate'], 3)} |\n")

    # ---- Seasonal breakdown, raw1min + glitch_sustain3 + metar_gated, near_money ----
    L.append("\n## 4. Seasonal breakdown (near_money ladder)\n")
    for cand in ("raw1min", "glitch_sustain3", "metar_gated"):
        L.append(f"\n### {cand}\n")
        L.append("| season | margin | n fired | n lock-fail | cond. loss | Wilson-95 |\n")
        L.append("|---|---|---|---|---|---|\n")
        for season in ("DJF", "MAM", "JJA", "SON"):
            for m in MARGINS:
                c = cell(agg, cand, m, "near_money", season)
                L.append(f"| {season} | {m} | {c['n_fired']} | {c['n_lockfail']} | "
                         f"{fmt_pct(c['cond_loss'])} | {fmt_pct(c['wilson95'])} |\n")

    # ---- Winter vs Summer explicit comparison, raw1min, margin=1 and 2 ----
    L.append("\n## 5. Winter (DJF) vs Summer (JJA) explicit comparison, raw1min\n")
    L.append("| margin | DJF cond. loss | DJF Wilson-95 | JJA cond. loss | JJA Wilson-95 | "
             "DJF/JJA ratio (point) |\n")
    L.append("|---|---|---|---|---|---|\n")
    for m in MARGINS:
        djf = cell(agg, "raw1min", m, "near_money", "DJF")
        jja = cell(agg, "raw1min", m, "near_money", "JJA")
        ratio = (djf["cond_loss"] / jja["cond_loss"]) if (djf["cond_loss"] and jja["cond_loss"]) else None
        L.append(f"| {m} | {fmt_pct(djf['cond_loss'])} | {fmt_pct(djf['wilson95'])} | "
                 f"{fmt_pct(jja['cond_loss'])} | {fmt_pct(jja['wilson95'])} | "
                 f"{(f'{ratio:.2f}x' if ratio else 'n/a')} |\n")
    L.append("\nSame DAYFLAG (unconditional exposure-day rate), winter vs summer:\n\n")
    L.append("| margin | DJF rate | JJA rate | DJF/JJA ratio |\n")
    L.append("|---|---|---|---|\n")
    for m in MARGINS:
        djf = dayflag_cell(agg, "raw1min", m, "DJF")
        jja = dayflag_cell(agg, "raw1min", m, "JJA")
        ratio = (djf["rate"] / jja["rate"]) if (djf["rate"] and jja["rate"]) else None
        L.append(f"| {m} | {fmt_pct(djf['rate'],3)} | {fmt_pct(jja['rate'],3)} | "
                 f"{(f'{ratio:.2f}x' if ratio else 'n/a')} |\n")

    # ---- Per-station worst offenders, raw1min margin=1, near_money ----
    L.append("\n## 6. Per-station worst offenders (raw1min, margin=1, near_money ladder)\n")
    L.append("| station | n fired | n lock-fail | cond. loss | Wilson-95 |\n")
    L.append("|---|---|---|---|---|\n")
    rows = []
    for st in stations:
        c = cell(agg, "raw1min", 1, "near_money", "STA", st)
        if c["n_fired"] >= 5:
            rows.append((st, c))
    rows.sort(key=lambda x: -(x[1]["cond_loss"] or 0))
    for st, c in rows:
        L.append(f"| {st} | {c['n_fired']} | {c['n_lockfail']} | {fmt_pct(c['cond_loss'])} | "
                 f"{fmt_pct(c['wilson95'])} |\n")
    if not rows:
        L.append("| (no station reached n_fired>=5 at margin=1) | | | | |\n")

    L.append("\nSame at margin=2:\n\n")
    L.append("| station | n fired | n lock-fail | cond. loss | Wilson-95 |\n")
    L.append("|---|---|---|---|---|\n")
    rows2 = []
    for st in stations:
        c = cell(agg, "raw1min", 2, "near_money", "STA", st)
        if c["n_fired"] >= 5:
            rows2.append((st, c))
    rows2.sort(key=lambda x: -(x[1]["cond_loss"] or 0))
    for st, c in rows2:
        L.append(f"| {st} | {c['n_fired']} | {c['n_lockfail']} | {fmt_pct(c['cond_loss'])} | "
                 f"{fmt_pct(c['wilson95'])} |\n")

    # ---- Recommended rule evaluation ----
    L.append("\n## 7. Candidate deployable rules -- all-season worst-case conditional loss\n")
    L.append("| rule | margin | n fired | cond. loss | Wilson-95 worst-case |\n")
    L.append("|---|---|---|---|---|\n")
    rule_rows = [
        ("raw1min (baseline)", "raw1min", 2),
        ("glitch-filtered only", "glitch1", 2),
        ("glitch + sustain3", "glitch_sustain3", 1),
        ("glitch + sustain3", "glitch_sustain3", 2),
        ("roll3 smoothing", "roll3", 1),
        ("roll3 smoothing", "roll3", 2),
        ("METAR-gated", "metar_gated", 1),
        ("METAR-gated", "metar_gated", 2),
    ]
    for label, cand, m in rule_rows:
        c = cell(agg, cand, m, "near_money", "ALL")
        L.append(f"| {label} | {m} | {c['n_fired']} | {fmt_pct(c['cond_loss'])} | {fmt_pct(c['wilson95'])} |\n")

    with open(OUT_MD, "w") as f:
        f.writelines(L)


if __name__ == "__main__":
    main()
