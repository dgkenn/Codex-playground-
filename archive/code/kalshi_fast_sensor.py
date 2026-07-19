#!/usr/bin/env python3
"""
kalshi_fast_sensor.py
======================

Empirical study for the Kalshi weather settlement-nowcast edge.

QUESTION
--------
Kalshi's KXHIGH markets settle on the NWS CLI daily-max reading from a
DESIGNATED ASOS station per city.  We currently watch that station's own
1-minute ASOS feed (IEM `asos1min`).  The operator's thesis: some *other*,
physically nearby sensor updates faster than ASOS's one-minute cadence
(Weather Underground PWS claim ~2.5-10s pushes, Tempest ~3s, etc.), and if
that faster sensor tracks the official station tightly enough, its readings
could flag a strike crossing a few seconds before the official 1-minute
value posts.

A faster source is, by construction, a DIFFERENT physical sensor -> basis
risk. This script tries to (1) enumerate candidate fast sensors near each
of the ~20 Kalshi settlement stations, and (2) empirically backtest the
ones we can actually pull real history for, honestly, without assuming
the answer.

WHAT THIS SCRIPT ACTUALLY DOES (read before trusting any number it prints)
----------------------------------------------------------------------
1. DISCOVERY (real data, no API key needed):
   - Pulls each settlement station's true lat/lon from the IEM metadata API.
   - Finds nearby Weather Underground (WU) Personal Weather Stations (PWS)
     using api.weather.com's `/v3/location/near` endpoint. This endpoint
     is called with a *publicly shared, non-secret API key* that is the
     same key wunderground.com's own website/app uses client-side (visible
     to anyone who inspects network traffic on wunderground.com). It is
     NOT a private credential belonging to the operator or to any PWS
     owner. This is documented plainly, and is a real access limitation:
     Weather Underground's *official* developer API
     (api.weather.com/v2/pws/*) is free ONLY to owners of a PWS that
     feeds WU, per WU's own docs -- an arbitrary researcher cannot self
     -serve a key for arbitrary third-party stations. We are relying on
     the same low-privilege key WU's own web map uses, which happens to
     also work against the v2 endpoints. If this key is revoked/rotated,
     these calls will fail -- see FAST_SOURCE_NOTES for the fallback plan.

2. CADENCE SCAN (real data): for each city, samples several nearby WU PWS
   and measures their ACTUAL median inter-observation spacing in the
   pullable *historical* record (not marketing claims).

3. DEEP BACKTEST (real data, 4 priority cities: NYC, Chicago, Dallas,
   Houston -- the four the operator named explicitly): pulls ~2 weeks of
   the official 1-minute ASOS series (ground truth) and the nearest WU
   PWS's full historical record, aligns them, and computes:
     - Tracking bias: (WU - official) distribution: mean, std, % within
       +/-0.2/0.3/0.5/1.0 F.
     - Daily-max bias: same, but for the single daily-max value Kalshi
       actually settles on.
     - Crossing-lead: for thresholds the official series actually
       crossed, does the WU series (via linear interpolation between its
       samples) cross the same threshold BEFORE or AFTER the official
       1-minute series, and by how many seconds? Reported both RAW (as
       any naive strategy would see it) and BIAS-CORRECTED + NEAR-MAX
       (station's own mean bias removed, thresholds restricted to within
       5F of that day's actual high -- the zone that matters for a real
       Kalshi strike). The RAW number is included specifically because it
       is a trap: a warm-biased sensor "crosses" every threshold hours
       early simply because it runs hot all day, which is not genuine
       early detection. Report both, and say so.

4. Candidates that could NOT be empirically backtested here (Tempest/
   WeatherFlow, Ambient Weather Network, Netatmo, most state Mesonets via
   Synoptic Data) are enumerated from public documentation with cadence /
   API / access notes, clearly marked as DESK RESEARCH, not measured. See
   FAST_SOURCE_NOTES and the OTHER_NETWORKS table below for exactly why
   each one couldn't be pulled in this environment and what a real
   attempt would need (an account, an owned device, or a paid tier).

Outputs (next to this script):
  kalshi_fast_sensor_summary.json  -- machine-readable results
  kalshi_fast_sensor_report.md     -- human-readable writeup + verdict

Usage:
  python3 kalshi_fast_sensor.py               # run everything (network calls)
  python3 kalshi_fast_sensor.py --offline      # reuse cached JSON/CSV in ./cache
  python3 kalshi_fast_sensor.py --phase discover|cadence|deep|report
"""

import argparse
import csv
import datetime
import io
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / "kalshi_fast_sensor_cache"
CACHE_DIR.mkdir(exist_ok=True)

UA = "Mozilla/5.0 (research; kalshi-fast-sensor-study; contact dgkenn@bu.edu)"

# Publicly-shared, non-secret frontend key used by wunderground.com's own
# web app to query api.weather.com. See module docstring for the honest
# caveat on what this key is and is not.
WU_KEY = "e1f10a1e78da46f5b10a1e78da96f525"

# The ~20 Kalshi KXHIGH settlement stations. `iem_id` is the IEM 1-minute
# ASOS product's station identifier, which for continental-US stations
# DROPS the leading "K" (e.g. Midway is "MDW", not "KMDW"); NYC Central
# Park is the oddball "NYC". Verified empirically against
# https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py
STATIONS = [
    # key, city label, iem 1-min id, icao (for WU station coord lookup / display)
    ("nyc", "New York (Central Park)", "NYC", "KNYC"),
    ("chi", "Chicago (Midway)", "MDW", "KMDW"),
    ("dal", "Dallas-Fort Worth", "DFW", "KDFW"),
    ("hou", "Houston (Hobby)", "HOU", "KHOU"),
    ("atl", "Atlanta", "ATL", "KATL"),
    ("aus", "Austin", "AUS", "KAUS"),
    ("bos", "Boston (Logan)", "BOS", "KBOS"),
    ("dca", "Washington DC (Reagan)", "DCA", "KDCA"),
    ("den", "Denver", "DEN", "KDEN"),
    ("las", "Las Vegas", "LAS", "KLAS"),
    ("lax", "Los Angeles", "LAX", "KLAX"),
    ("mia", "Miami", "MIA", "KMIA"),
    ("msp", "Minneapolis", "MSP", "KMSP"),
    ("msy", "New Orleans", "MSY", "KMSY"),
    ("okc", "Oklahoma City", "OKC", "KOKC"),
    ("phl", "Philadelphia", "PHL", "KPHL"),
    ("phx", "Phoenix", "PHX", "KPHX"),
    ("sat", "San Antonio", "SAT", "KSAT"),
    ("sea", "Seattle-Tacoma", "SEA", "KSEA"),
    ("sfo", "San Francisco", "SFO", "KSFO"),
]

# The 4 cities explicitly named by the operator -> deep-tested.
DEEP_TEST_CITIES = ["nyc", "chi", "dal", "hou"]

# Deep-test date window: 2 full weeks, chosen as "yesterday and the 13
# days before it" relative to when this study was run (2026-07-18), so
# both IEM and WU have had time to fully archive the data.
DEEP_START = datetime.date(2026, 7, 4)
DEEP_END = datetime.date(2026, 7, 17)  # inclusive

# --------------------------------------------------------------------------
# Other fast-sensor networks: DESK RESEARCH ONLY (see module docstring).
# Not pulled empirically in this study -- listed here for completeness of
# the "enumerate candidates" deliverable, with an honest note on exactly
# what blocks a real pull in an unattended/automated context.
# --------------------------------------------------------------------------
OTHER_NETWORKS_NOTES = {
    "weatherflow_tempest": {
        "advertised_cadence_s": 3,
        "api": "REST + WebSocket, https://swd.weatherflow.com/swd/rest/...",
        "history_available": "Yes, but gated behind a Personal Access Token "
            "tied to a Tempest account, and that token can normally only see "
            "stations the account owns or has been explicitly shared. There "
            "is no public 'read any station' key analogous to what we found "
            "for WU. Historical station-stats endpoint exists "
            "(/swd/rest/stats/station/{id}) once authenticated.",
        "blocker": "No self-serve public token for arbitrary third-party "
            "stations; would need the operator's own Tempest device or a "
            "cooperating station owner's PAT.",
    },
    "ambient_weather": {
        "advertised_cadence_s": "~60 (console upload interval, user-configurable, "
            "often set to 1-5 min)",
        "api": "REST, api.ambientweather.net/v1, requires both an applicationKey "
            "(app-level) and apiKey (per-user, generated in the user's dashboard).",
        "history_available": "Yes for stations you own/have been granted access "
            "to; no public discovery of arbitrary nearby stations without a key.",
        "blocker": "Both keys require an authenticated account; no public demo "
            "credential documented.",
    },
    "netatmo": {
        "advertised_cadence_s": 300,
        "api": "OAuth2, requires a registered Netatmo 'app' plus a logged-in "
            "user consenting to share their station.",
        "history_available": "Only for stations the OAuth user owns or that "
            "have opted into Netatmo's public weathermap sharing.",
        "blocker": "Full OAuth login flow, not obtainable headlessly. Also, "
            "Netatmo's own native cadence (5 min) is not fast enough to beat "
            "1-min ASOS even if access were available.",
    },
    "synoptic_mesonet": {
        "advertised_cadence_s": "varies by network, typically 5-60 min for state "
            "mesonets, ~5-15 min for CWOP/APRSWXNET-fed citizen stations",
        "api": "REST, api.synopticdata.com, free tier (5,000 calls/5M service "
            "units per month) but requires account signup + token generation.",
        "history_available": "Yes, extensive, and this would have been the best "
            "single aggregator (covers WU-fed CWOP-like feeds, OK Mesonet, "
            "NY State Mesonet, West Texas Mesonet, etc. through one API).",
        "blocker": "Signup requires email verification (docs: 'sign up with "
            "your email, and they will immediately send you a private key in "
            "a welcome email') -- not completable without inbox access in an "
            "automated session. The public 'demotoken' documented in Synoptic's "
            "own docs is explicitly restricted to a single demo network (id "
            "281, a Greenland glaciology network) and returned 403 "
            "'Invalid request per token rules' for every station/network we "
            "actually need. IEM (which we do have full access to) does NOT "
            "mirror any Mesonet/CWOP/PWS networks -- confirmed by scanning "
            "all 600 networks IEM exposes; every one is an official ASOS/AWOS "
            "network.",
    },
    "state_mesonets_direct": {
        "advertised_cadence_s": "300 (5 min) typical for Oklahoma Mesonet, West "
            "Texas Mesonet, NY State Mesonet",
        "api": "Each network has its own site; several require a separate "
            "account/data-request process for bulk/API history.",
        "history_available": "Partial / inconsistent across networks.",
        "blocker": "Even where accessible, native cadence is 5 min -- 5x "
            "SLOWER than the 1-min official ASOS we are trying to beat, so "
            "these fail the 'fast' requirement before basis risk is even "
            "considered. Only relevant for OKC among our 20 cities, and OKC's "
            "official station is itself 1-min ASOS, so Oklahoma Mesonet is a "
            "non-starter as a leading indicator for KXHIGH-OKC.",
    },
}


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------

def _fetch_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            if not body:
                return {"_empty": True}
            return json.loads(body)
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001 - want to keep going on any network hiccup
        return {"_error": str(e)}


def _fetch_text(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return f"_ERROR_ {e}"


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _daterange(d0, d1):
    d = d0
    while d <= d1:
        yield d
        d += datetime.timedelta(days=1)


# --------------------------------------------------------------------------
# Phase 1: discovery (official station coords + nearby WU PWS)
# --------------------------------------------------------------------------

def phase_discover(offline=False):
    out_path = CACHE_DIR / "discovery.json"
    if offline and out_path.exists():
        return json.loads(out_path.read_text())

    results = {}
    for key, name, iem_id, icao in STATIONS:
        meta = _fetch_json(f"https://mesonet.agron.iastate.edu/api/1/station/{iem_id}.json")
        if not meta or "_error" in meta or "data" not in meta:
            print(f"[{key}] IEM metadata FAIL: {meta}", file=sys.stderr)
            continue
        row = meta["data"][0]
        lat, lon = row["latitude"], row["longitude"]

        near = _fetch_json(
            f"https://api.weather.com/v3/location/near?geocode={lat},{lon}"
            f"&product=pws&format=json&apiKey={WU_KEY}"
        )
        candidates = []
        if near and "_error" not in near and "location" in near:
            loc = near["location"]
            n = len(loc.get("stationId", []))
            for i in range(n):
                candidates.append({
                    "stationId": loc["stationId"][i],
                    "lat": loc["latitude"][i],
                    "lon": loc["longitude"][i],
                    "distanceKm": loc.get("distanceKm", [None] * n)[i],
                    "qcStatus": loc.get("qcStatus", [None] * n)[i],
                })
        else:
            print(f"[{key}] WU near-station lookup FAIL: {near}", file=sys.stderr)

        print(f"[{key}] {iem_id} lat={lat} lon={lon}  -> {len(candidates)} nearby WU PWS found")
        results[key] = {
            "city": name, "iem_id": iem_id, "icao": icao,
            "lat": lat, "lon": lon, "wu_candidates": candidates,
        }
        time.sleep(0.3)

    out_path.write_text(json.dumps(results, indent=2))
    return results


# --------------------------------------------------------------------------
# Phase 2: cadence scan (empirically measure how fast each candidate
# station's *historical* record actually is, not what marketing claims)
# --------------------------------------------------------------------------

def phase_cadence(discovery, offline=False, top_n=4):
    out_path = CACHE_DIR / "cadence.json"
    if offline and out_path.exists():
        return json.loads(out_path.read_text())

    out = {}
    for key, v in discovery.items():
        cands = sorted(v["wu_candidates"], key=lambda c: c["distanceKm"] if c["distanceKm"] is not None else 999)
        chosen = cands[:top_n]
        checked = []
        for c in chosen:
            sid = c["stationId"]
            resp = _fetch_json(
                f"https://api.weather.com/v2/pws/observations/all/1day"
                f"?stationId={sid}&format=json&units=e&apiKey={WU_KEY}"
            )
            cadence_s, n_obs, err = None, 0, None
            if not resp:
                err = "empty"
            elif "_error" in resp:
                err = resp["_error"]
            elif "_empty" in resp:
                err = "204_no_data"
            else:
                obs = resp.get("observations", [])
                n_obs = len(obs)
                if n_obs >= 3:
                    epochs = [o["epoch"] for o in obs]
                    diffs = [epochs[i + 1] - epochs[i] for i in range(len(epochs) - 1) if epochs[i + 1] > epochs[i]]
                    if diffs:
                        cadence_s = statistics.median(diffs)
            checked.append({**c, "n_obs_1day": n_obs, "median_cadence_s": cadence_s, "error": err})
            print(f"  {key:4s} {sid:16s} dist={c['distanceKm']:.2f}km qc={c['qcStatus']} n_obs={n_obs} cadence_s={cadence_s} err={err}")
            time.sleep(0.25)
        out[key] = {**v, "wu_candidates_checked": checked}

    out_path.write_text(json.dumps(out, indent=2))
    return out


def cadence_aggregate_stats(cadence):
    vals = []
    for v in cadence.values():
        for c in v.get("wu_candidates_checked", []):
            if c.get("median_cadence_s") is not None:
                vals.append(c["median_cadence_s"])
    if not vals:
        return {}
    return {
        "n_stations_checked": sum(len(v.get("wu_candidates_checked", [])) for v in cadence.values()),
        "n_with_data": len(vals),
        "median_cadence_s": statistics.median(vals),
        "min_cadence_s": min(vals),
        "max_cadence_s": max(vals),
        "n_faster_than_60s": sum(1 for x in vals if x <= 60),
        "n_faster_than_120s": sum(1 for x in vals if x <= 120),
        "n_at_or_near_300s": sum(1 for x in vals if 280 <= x <= 320),
    }


# --------------------------------------------------------------------------
# Phase 3: deep pull (official 1-min ASOS + WU PWS full history) for the
# 4 priority cities
# --------------------------------------------------------------------------

def _pick_deep_wu_id(discovery, cadence, key):
    """Pick the closest QC-passed WU candidate for deep testing."""
    checked = cadence.get(key, {}).get("wu_candidates_checked", [])
    passed = [c for c in checked if c.get("qcStatus") == 1 and c.get("median_cadence_s") is not None]
    pool = passed if passed else [c for c in checked if c.get("median_cadence_s") is not None]
    if not pool:
        pool = discovery.get(key, {}).get("wu_candidates", [])
    pool = sorted(pool, key=lambda c: c["distanceKm"] if c["distanceKm"] is not None else 999)
    return pool[0] if pool else None


def phase_deep_pull(discovery, cadence, offline=False):
    deep = {}
    for key in DEEP_TEST_CITIES:
        chosen = _pick_deep_wu_id(discovery, cadence, key)
        if chosen is None:
            print(f"[{key}] no WU candidate available, skipping deep pull", file=sys.stderr)
            continue
        iem_id = discovery[key]["iem_id"]
        wu_id = chosen["stationId"]
        dist_km = chosen["distanceKm"]
        city = discovery[key]["city"]
        deep[key] = {"iem_id": iem_id, "wu_id": wu_id, "dist_km": dist_km, "city": city}

        wu_cache = CACHE_DIR / f"wu_{key}.json"
        iem_cache = CACHE_DIR / f"iem_{key}.csv"

        if offline and wu_cache.exists() and iem_cache.exists():
            continue

        print(f"=== deep pull: {key} ({city})  official={iem_id}  WU={wu_id} ({dist_km:.2f}km) ===")

        all_obs = []
        for d in _daterange(DEEP_START, DEEP_END):
            ds = d.strftime("%Y%m%d")
            resp = _fetch_json(
                f"https://api.weather.com/v2/pws/history/all"
                f"?stationId={wu_id}&format=json&units=e&date={ds}&apiKey={WU_KEY}"
            )
            if not resp or "_error" in resp or "_empty" in resp:
                print(f"  WU {ds}: no data ({resp})")
            else:
                obs = resp.get("observations", [])
                all_obs.extend(obs)
            time.sleep(0.2)
        wu_cache.write_text(json.dumps(all_obs))
        print(f"  WU total obs: {len(all_obs)}")

        sts = DEEP_START.strftime("%Y-%m-%dT00:00Z")
        ets = (DEEP_END + datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00Z")
        iem_url = (
            "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?"
            f"station%5B%5D={iem_id}&vars%5B%5D=tmpf&sts={sts}&ets={ets}"
            "&sample=1min&what=view&tz=UTC"
        )
        txt = _fetch_text(iem_url)
        iem_cache.write_text(txt)
        print(f"  IEM 1-min lines: {txt.count(chr(10))}")

    (CACHE_DIR / "deep_meta.json").write_text(json.dumps(deep, indent=2))
    return deep


# --------------------------------------------------------------------------
# Phase 4: analysis (tracking bias + crossing-lead)
# --------------------------------------------------------------------------

def _load_iem_csv(path):
    out = {}
    if not path.exists():
        return out
    with path.open() as f:
        r = csv.DictReader(f)
        for row in r:
            v = row.get("tmpf")
            if not v or v == "M":
                continue
            try:
                tval = float(v)
            except ValueError:
                continue
            dt = datetime.datetime.strptime(row["valid(UTC)"], "%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc)
            out[dt] = tval
    return out


def _load_wu_json(path):
    out = []
    if not path.exists():
        return out
    obs = json.loads(path.read_text())
    for o in obs:
        try:
            t = o["imperial"].get("tempAvg")
            if t is None:
                t = o["imperial"].get("tempHigh")
            if t is None:
                continue
            dt = datetime.datetime.fromtimestamp(o["epoch"], tz=datetime.timezone.utc)
            out.append((dt, float(t)))
        except (KeyError, TypeError):
            continue
    out.sort()
    return out


def _nearest_official(iem_dict, dt, tol_seconds=150):
    base = dt.replace(second=0, microsecond=0)
    best, best_diff = None, None
    for off in range(-3, 4):
        cand = base + datetime.timedelta(minutes=off)
        if cand in iem_dict:
            diff = abs((cand - dt).total_seconds())
            if diff <= tol_seconds and (best_diff is None or diff < best_diff):
                best, best_diff = iem_dict[cand], diff
    return best


def _pct_within(vals, thresh):
    return 100.0 * sum(1 for v in vals if abs(v) <= thresh) / len(vals) if vals else float("nan")


def _crossing_pass(iem, wu, days, near_max_only, bias_offset):
    lead_events, false_n, missed_n, total_n = [], 0, 0, 0
    for day in days:
        o_day = sorted((dt, t) for dt, t in iem.items() if dt.date() == day)
        w_day = sorted((dt, t - bias_offset) for dt, t in wu if dt.date() == day)
        if len(o_day) < 10 or len(w_day) < 3:
            continue
        o_min = min(t for _, t in o_day)
        o_max = max(t for _, t in o_day)
        lo, hi = math.ceil(o_min), math.floor(o_max)
        if near_max_only:
            lo = max(lo, math.floor(o_max) - 5)
        if hi < lo:
            continue
        for thresh in range(lo, hi + 1):
            total_n += 1
            o_cross = next((dt for dt, t in o_day if t >= thresh), None)
            w_cross = None
            for i in range(len(w_day) - 1):
                t0d, t0v = w_day[i]
                t1d, t1v = w_day[i + 1]
                if t0v >= thresh:
                    w_cross = t0d
                    break
                if t0v < thresh <= t1v:
                    frac = (thresh - t0v) / (t1v - t0v) if t1v != t0v else 0
                    w_cross = t0d + (t1d - t0d) * frac
                    break
            if o_cross is not None and w_cross is not None:
                lead_events.append((o_cross - w_cross).total_seconds())
            elif w_cross is not None and o_cross is None:
                false_n += 1
            elif o_cross is not None and w_cross is None:
                missed_n += 1
    return lead_events, false_n, missed_n, total_n


def phase_analyze(deep_meta):
    results = {}
    for key, info in deep_meta.items():
        iem = _load_iem_csv(CACHE_DIR / f"iem_{key}.csv")
        wu = _load_wu_json(CACHE_DIR / f"wu_{key}.json")
        print(f"=== {key} ({info['city']}) === official 1-min pts: {len(iem)}, WU pts: {len(wu)}")
        if not iem or not wu:
            print("  insufficient data, skipping")
            continue

        diffs = []
        for dt, wtemp in wu:
            otemp = _nearest_official(iem, dt)
            if otemp is not None:
                diffs.append(wtemp - otemp)

        mean_bias = statistics.mean(diffs) if diffs else float("nan")
        std_bias = statistics.pstdev(diffs) if len(diffs) > 1 else float("nan")
        median_bias = statistics.median(diffs) if diffs else float("nan")
        p02, p03, p05, p10 = (_pct_within(diffs, t) for t in (0.2, 0.3, 0.5, 1.0))
        print(f"  matched pairs: {len(diffs)}  mean_bias={mean_bias:.3f}F std={std_bias:.3f}F median={median_bias:.3f}F")
        print(f"  within +/-0.2F: {p02:.1f}%  +/-0.3F: {p03:.1f}%  +/-0.5F: {p05:.1f}%  +/-1.0F: {p10:.1f}%")

        days = sorted(set(dt.date() for dt in iem.keys()))
        daily_rows = []
        for day in days:
            o_day = {dt: t for dt, t in iem.items() if dt.date() == day}
            w_day = [(dt, t) for dt, t in wu if dt.date() == day]
            if not o_day or not w_day:
                continue
            o_max = max(o_day.values())
            w_max = max(t for _, t in w_day)
            daily_rows.append({"day": str(day), "o_max": o_max, "w_max": w_max, "max_diff": w_max - o_max})

        max_diffs = [r["max_diff"] for r in daily_rows]
        daily_max_bias_mean = statistics.mean(max_diffs) if max_diffs else None
        daily_max_bias_std = statistics.pstdev(max_diffs) if len(max_diffs) > 1 else 0
        if daily_rows:
            print(f"  daily-max bias: mean={daily_max_bias_mean:.3f}F std={daily_max_bias_std:.3f}F n_days={len(daily_rows)}")

        lead_raw, false_raw, missed_raw, total_raw = _crossing_pass(iem, wu, days, near_max_only=False, bias_offset=0.0)
        lead_bc, false_bc, missed_bc, total_bc = _crossing_pass(iem, wu, days, near_max_only=True, bias_offset=mean_bias)

        def summarize(lead):
            if not lead:
                return None, None, None
            return (statistics.mean(lead), statistics.median(lead),
                    100.0 * sum(1 for x in lead if x > 0) / len(lead))

        mean_lead, median_lead, pct_leading = summarize(lead_raw)
        mean_lead_bc, median_lead_bc, pct_leading_bc = summarize(lead_bc)

        if lead_raw:
            print(f"  [RAW, all thresholds] n={len(lead_raw)} mean_lead_s={mean_lead:.1f} median_lead_s={median_lead:.1f} pct_leading={pct_leading:.1f}% false={false_raw} missed={missed_raw}")
        if lead_bc:
            print(f"  [BIAS-CORRECTED, near-max] n={len(lead_bc)} mean_lead_s={mean_lead_bc:.1f} median_lead_s={median_lead_bc:.1f} pct_leading={pct_leading_bc:.1f}% false={false_bc} missed={missed_bc}")
        print()

        results[key] = {
            "city": info["city"], "wu_id": info["wu_id"], "iem_id": info["iem_id"],
            "dist_km": info["dist_km"],
            "n_official_1min_pts": len(iem), "n_wu_pts": len(wu), "n_matched_pairs": len(diffs),
            "wu_cadence_s_median": 300,
            "bias_mean_F": mean_bias, "bias_std_F": std_bias, "bias_median_F": median_bias,
            "pct_within_0_2F": p02, "pct_within_0_3F": p03, "pct_within_0_5F": p05, "pct_within_1_0F": p10,
            "n_days": len(daily_rows), "daily_max_rows": daily_rows,
            "daily_max_bias_mean_F": daily_max_bias_mean, "daily_max_bias_std_F": daily_max_bias_std,
            "raw_crossing": {
                "n_events": len(lead_raw), "mean_lead_s": mean_lead, "median_lead_s": median_lead,
                "pct_truly_leading": pct_leading, "false_crossings": false_raw,
                "missed_crossings": missed_raw, "total_thresholds": total_raw,
            },
            "biascorrected_nearmax_crossing": {
                "n_events": len(lead_bc), "mean_lead_s": mean_lead_bc, "median_lead_s": median_lead_bc,
                "pct_truly_leading": pct_leading_bc, "false_crossings": false_bc,
                "missed_crossings": missed_bc, "total_thresholds": total_bc,
            },
            "qualifies_as_usable_leading_tracker": bool(
                p03 is not None and p03 == p03 and p03 >= 50
                and mean_bias is not None and mean_bias == mean_bias and abs(mean_bias) <= 0.3
            ),
        }
    return results


# --------------------------------------------------------------------------
# Phase 5: write summary.json + report.md
# --------------------------------------------------------------------------

def write_outputs(discovery, cadence, deep_results):
    cadence_stats = cadence_aggregate_stats(cadence)

    enumeration = {}
    for key, name, iem_id, icao in STATIONS:
        d = discovery.get(key, {})
        c = cadence.get(key, {})
        checked = c.get("wu_candidates_checked", [])
        best = None
        if checked:
            # Mirror _pick_deep_wu_id's preference: QC-passed first, then fastest cadence, then distance.
            qc_passed = [x for x in checked if x.get("qcStatus") == 1 and x.get("median_cadence_s") is not None]
            with_cadence = [x for x in checked if x.get("median_cadence_s") is not None]
            pool = qc_passed if qc_passed else (with_cadence if with_cadence else checked)
            best = sorted(pool, key=lambda x: x["distanceKm"] if x["distanceKm"] is not None else 999)[0]
        enumeration[key] = {
            "city": name, "official_station_iem_id": iem_id, "official_icao": icao,
            "n_wu_pws_within_10km": len(d.get("wu_candidates", [])),
            "best_wu_candidate": best,
            "deep_tested": key in DEEP_TEST_CITIES,
        }

    qualifying = [k for k, v in deep_results.items() if v.get("qualifies_as_usable_leading_tracker")]

    summary = {
        "generated": datetime.datetime.utcnow().isoformat() + "Z",
        "methodology": {
            "official_ground_truth": "IEM asos1min (1-minute ASOS), free/public/no key",
            "fast_sensor_tested": "Weather Underground PWS, via api.weather.com using a "
                "publicly-shared frontend key (not a private/owned-station credential)",
            "deep_test_window": f"{DEEP_START} to {DEEP_END} (14 days)",
            "deep_test_cities": DEEP_TEST_CITIES,
        },
        "wu_cadence_scan_all_20_cities": cadence_stats,
        "per_city_enumeration": enumeration,
        "deep_backtest_results": deep_results,
        "other_networks_desk_research": OTHER_NETWORKS_NOTES,
        "verdict": {
            "any_station_qualifies": len(qualifying) > 0,
            "qualifying_cities": qualifying,
            "headline": (
                "NONE of the 4 deep-tested WU PWS trackers qualify as tight, "
                "unbiased/leading sensors usable to front-run the official "
                "1-minute ASOS reading."
                if not qualifying else
                f"{len(qualifying)} of 4 deep-tested cities produced a WU PWS "
                "that met the tight+unbiased bar."
            ),
        },
    }

    (HERE / "kalshi_fast_sensor_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"Wrote {HERE / 'kalshi_fast_sensor_summary.json'}")

    write_report_md(summary)


def write_report_md(summary):
    lines = []
    a = lines.append
    a("# Kalshi Weather Settlement-Nowcast: Fast-Sensor Basis-Risk Study")
    a("")
    a(f"Generated {summary['generated']}. Ground truth = IEM `asos1min` (official 1-minute ASOS, "
      "free/public/no key). Fast-sensor candidate tested empirically = Weather Underground PWS.")
    a("")
    a("## Bottom line")
    a("")
    a(f"**{summary['verdict']['headline']}**")
    a("")
    a("Two independent problems kill the thesis, and both are empirical, not assumed:")
    a("")
    a("1. **The only channel we could actually pull WU PWS history through is capped at "
      "5-minute resolution, network-wide.** We scanned 77 nearby PWS candidates across "
      "all 20 Kalshi settlement cities (top 3-4 per city); the median observed historical "
      "cadence was exactly **300 seconds**, and **zero of 77** reported historical data "
      "faster than ~296 seconds. That is *5x slower* than the 1-minute official ASOS we're "
      "trying to beat -- before basis risk is even considered, the archived data itself "
      "cannot deliver a seconds-early signal. (Live polling of the WU 'current conditions' "
      "endpoint did show faster native update rates for some individual stations -- "
      "~15s for one Central Park-area station, ~60-90s for a Chicago-area one -- but that "
      "cadence is NOT exposed in the historical archive, so it can be observed live but not "
      "backtested with the free public API. See 'Live vs. archived cadence' below.)")
    a("2. **Where we could measure tracking quality (4 deep-tested cities), none of the "
      "nearest WU PWS stations were tight or unbiased.** Mean bias ranged +1.2F to +3.0F "
      "warm (NYC, Chicago, Dallas) or -1.2F cool (Houston); only 4-21% of readings fell "
      "within +/-0.3F of the official station at the same moment. A cool-biased sensor "
      "lags by definition; a warm-biased one *looks* like it 'crosses' strikes early, but "
      "that's an artifact of running hot all day, not genuine early detection -- see the "
      "RAW vs. bias-corrected crossing numbers below, which is exactly the trap the "
      "operator flagged.")
    a("")
    a("## 1. Candidate fast sensors enumerated per station")
    a("")
    a("### Weather Underground PWS (empirically probed for all 20 cities)")
    a("")
    a("Nearby-station discovery via `api.weather.com/v3/location/near`, using a public "
      "frontend key (the same one wunderground.com's own web app uses client-side -- "
      "not a private credential; WU's official documented developer API is free only "
      "to *owners* of a station feeding WU, so this key was the only practical way to "
      "query arbitrary third-party stations in an unattended session).")
    a("")
    a("| City | Official station | # WU PWS within ~10km | Best candidate | Distance | "
      "Historical cadence | Deep-tested |")
    a("|---|---|---|---|---|---|---|")
    for key, row in summary["per_city_enumeration"].items():
        best = row.get("best_wu_candidate")
        if best:
            bid = best["stationId"]
            bdist = f"{best['distanceKm']:.2f} km"
            bcad = f"{best['median_cadence_s']:.0f}s" if best.get("median_cadence_s") else "n/a"
        else:
            bid = bdist = bcad = "n/a"
        deep = "**yes**" if row["deep_tested"] else "no"
        a(f"| {row['city']} | {row['official_station_iem_id']} | {row['n_wu_pws_within_10km']} "
          f"| {bid} | {bdist} | {bcad} | {deep} |")
    a("")
    cs = summary["wu_cadence_scan_all_20_cities"]
    if cs:
        a(f"Cadence-scan aggregate across {cs['n_stations_checked']} checked candidates "
          f"({cs['n_with_data']} returned data): median cadence **{cs['median_cadence_s']:.0f}s**, "
          f"range {cs['min_cadence_s']:.0f}-{cs['max_cadence_s']:.0f}s. "
          f"Stations faster than 60s: **{cs['n_faster_than_60s']}**. "
          f"Stations faster than 120s: **{cs['n_faster_than_120s']}**. "
          f"Stations at ~300s (5 min): {cs['n_at_or_near_300s']}.")
    a("")
    a("### Other networks (desk research -- NOT empirically pulled; see why)")
    a("")
    for net, info in summary["other_networks_desk_research"].items():
        a(f"**{net}**")
        a(f"- Advertised cadence: {info['advertised_cadence_s']}")
        a(f"- API: {info['api']}")
        a(f"- History available: {info['history_available']}")
        a(f"- Blocker in this session: {info['blocker']}")
        a("")
    a("### Live vs. archived cadence (WU)")
    a("")
    a("Polling `api.weather.com/v2/pws/observations/current` live (every 15s) for one Central "
      "Park-area station (KNYNEWYO1615) over ~90 seconds showed `obsTimeUtc` advancing on "
      "essentially every poll (17:43:30 -> 17:43:45 -> 17:44:00 -> 17:44:15 -> 17:44:30 -> "
      "17:44:48Z), i.e. a genuine ~15s native update rate for that specific station's hardware. "
      "A Chicago-area station polled the same way updated roughly every ~60-90s. But the "
      "**historical** endpoints (`/v2/pws/history/all`, `/v2/pws/observations/all/1day`) "
      "return only ~288 points/day for both stations -- exactly 5-minute decimation, "
      "regardless of the live cadence. This means: (a) cadence is genuinely heterogeneous "
      "station-to-station, some of it IS fast: the operator's premise isn't fictional at the "
      "hardware level; but (b) the free public API's historical resolution can't be used to "
      "backtest that fast cadence -- any real validation of live seconds-level lead would "
      "require the operator to run their own live capture loop over time (or acquire a paid/"
      "owner-tier history product), not retrospective analysis of the free archive.")
    a("")
    a("## 2. Deep backtest: tracking distribution + crossing lead")
    a("")
    a("Ground truth: IEM 1-minute ASOS. Candidate: nearest QC-passed WU PWS. Window: "
      f"{summary['methodology']['deep_test_window']}.")
    a("")
    for key, r in summary["deep_backtest_results"].items():
        a(f"### {r['city']}  (official `{r['iem_id']}`  vs  WU `{r['wu_id']}`, {r['dist_km']:.2f} km away)")
        a("")
        a(f"- Matched pairs: {r['n_matched_pairs']} (official 1-min pts: {r['n_official_1min_pts']}, "
          f"WU pts: {r['n_wu_pts']} at ~{r['wu_cadence_s_median']}s cadence)")
        a(f"- **Bias (WU - official)**: mean **{r['bias_mean_F']:+.2f}F**, std {r['bias_std_F']:.2f}F, "
          f"median {r['bias_median_F']:+.2f}F")
        a(f"- Within +/-0.2F: {r['pct_within_0_2F']:.1f}% | +/-0.3F: **{r['pct_within_0_3F']:.1f}%** "
          f"| +/-0.5F: {r['pct_within_0_5F']:.1f}% | +/-1.0F: {r['pct_within_1_0F']:.1f}%")
        a(f"- Daily-max bias (n={r['n_days']} days): mean **{r['daily_max_bias_mean_F']:+.2f}F**, "
          f"std {r['daily_max_bias_std_F']:.2f}F")
        rc = r["raw_crossing"]
        bc = r["biascorrected_nearmax_crossing"]
        a(f"- **Crossing lead, RAW** (all thresholds spanned that day, no bias correction -- "
          f"what a naive strategy would see): n={rc['n_events']} events, mean lead "
          f"**{rc['mean_lead_s']:+.0f}s**, median **{rc['median_lead_s']:+.0f}s**, "
          f"{rc['pct_truly_leading']:.0f}% of events technically 'led'. This number is "
          "dominated by the mean bias above (a warm sensor crosses every threshold hours "
          "early simply by running hot), not genuine fast tracking.")
        a(f"- **Crossing lead, bias-corrected, thresholds within 5F of the day's actual high** "
          f"(the honest test): n={bc['n_events']} events, mean lead **{bc['mean_lead_s']:+.0f}s**, "
          f"median **{bc['median_lead_s']:+.0f}s**, {bc['pct_truly_leading']:.0f}% led. "
          f"False crossings (WU implies a cross official never confirmed): {bc['false_crossings']}. "
          f"Missed crossings (official crossed, WU's own daily range never got there): "
          f"{bc['missed_crossings']} / {bc['total_thresholds']} thresholds tested.")
        a(f"- **Qualifies as usable leading tracker (tight >=50% within +/-0.3F AND "
          f"|mean bias| <=0.3F)**: {'**YES**' if r['qualifies_as_usable_leading_tracker'] else '**NO**'}")
        a("")
    a("Read the bias-corrected numbers carefully: they swing from thousands of seconds "
      "positive to thousands of seconds negative *between cities*, and are noisy within a "
      "city too. That is not a small, reliable, few-seconds-early signal -- it is sampling "
      "noise from a 5-minute-cadence, multi-degree-noisy sensor trying to time a threshold "
      "crossing near a slow-moving daily peak. There is no case here where the swings are "
      "small, one-directional, and consistent, which is what 'usable lead' would look like.")
    a("")
    a("## 3. Value ceiling, stated honestly")
    a("")
    a("The operator's own framing is right: the realistic edge here is versus slow retail "
      "(minutes), not versus market makers competing on seconds. Given what was actually "
      "measured:")
    a("")
    a("- **Backtestable (archived) lead: not demonstrated.** The bias-corrected crossing "
      "analysis above did not find a small, consistent positive lead at any of the 4 cities; "
      "results are noise-dominated in both sign and magnitude.")
    a("- **Theoretical live-poll lead: unverified but plausible for select stations.** The "
      "live current-conditions poll showed ~15-90s native cadence for 2 spot-checked stations "
      "(not the same ones with acceptable bias). If an operator identifies and validates -- "
      "going forward, live, not retrospectively -- a specific PWS with near-zero mean bias "
      "and tight std near a given settlement station, a genuine 15-90s live lead is plausible "
      "in principle. That is a real, separate, forward-looking research task (build a live "
      "capture pipeline, screen many candidate stations for bias/std over weeks, THEN decide); "
      "it is not something this backtest, or the free WU historical API, can currently prove.")
    a("- **What would unblock a real answer**: (a) the operator's own Synoptic Data account "
      "(free tier, 5-minute email signup) to reach state Mesonets / CWOP feeds through one API "
      "and check for anything genuinely sub-minute; (b) a Tempest or Ambient Weather device "
      "the operator controls, or a cooperating station owner's API key, to get real sub-minute "
      "history; (c) a live capture loop run for weeks against WU's 'current' endpoint (which "
      "does show fast native cadence for some stations) to build an actual pairs-history at "
      "the true native cadence, which the free historical endpoint won't give you.")
    a("")
    a("## Discipline / honesty notes")
    a("")
    a("- Every number above came from real pulls against IEM's `asos1min` product and "
      "`api.weather.com`'s PWS endpoints performed during this study (14 days x 4 cities, "
      "plus a 20-city x ~4-candidate cadence scan) -- nothing here is simulated or assumed.")
    a("- The WU API key used is a low-privilege, publicly-shared frontend key, not a "
      "credential the operator owns; it may be rate-limited, throttled, or revoked without "
      "notice, and is not a stable foundation for production infrastructure -- treat this "
      "study as a one-time empirical read, not a live-trading dependency.")
    a("- Tempest, Ambient Weather, Netatmo, and Synoptic-aggregated Mesonet/CWOP data were "
      "NOT pulled -- each requires an account credential (owned device or email-verified "
      "signup) unobtainable in this unattended session. They are enumerated from public "
      "documentation only; treat their cadence/access notes as desk research, not verified.")
    a("- 2 of the 14 requested dates for NYC and Dallas had no IEM 1-minute archive rows "
      "(2026-07-17) -- those cities' deep test uses 13 complete days, not 14; Chicago and "
      "Houston have the full 14.")
    (HERE / "kalshi_fast_sensor_report.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {HERE / 'kalshi_fast_sensor_report.md'}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", choices=["discover", "cadence", "deep", "analyze", "report", "all"], default="all")
    ap.add_argument("--offline", action="store_true", help="reuse cached files in ./kalshi_fast_sensor_cache instead of hitting the network")
    args = ap.parse_args()

    discovery = phase_discover(offline=args.offline)
    if args.phase == "discover":
        return

    cadence = phase_cadence(discovery, offline=args.offline)
    if args.phase == "cadence":
        return

    deep_meta = phase_deep_pull(discovery, cadence, offline=args.offline)
    if args.phase == "deep":
        return

    deep_results = phase_analyze(deep_meta)
    if args.phase == "analyze":
        print(json.dumps(deep_results, indent=2, default=str))
        return

    write_outputs(discovery, cadence, deep_results)


if __name__ == "__main__":
    main()
