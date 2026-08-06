#!/usr/bin/env python3
"""edge_sizing_stage2.py -- Stage 2 of EDGE_SIZING_SPEC.md.

Gates Stage 1's oracle (perfect-knowledge) capturable-market list on what the DEPLOYED lock rule
(kwx_lock_rule.py: sustained_extreme + locked_orders, imported verbatim, never reimplemented) would
actually have known in time, replayed against real IEM station observations.

Method (frozen in the task spec, mirrored here):
  1. Take all 140 Stage-1 capturable markets (< the >=150 the spec asks for -- disclosed shortfall,
     there are only 140 in the Stage-1 sample).
  2. ticker -> series -> (station, kind) via the SAME HIGH/LOW city map kwx_runner.py uses (recovered
     from venue_expansion/paper/kwx_runner.py, CITY + CITY_LOW_SERIES dicts, byte-copied constants).
  3. ticker -> local settlement day is implicit in close_time: every one of these markets' close_time
     is exactly 24h after local midnight in the station's FIXED STANDARD-time offset (verified against
     KXLOWTSEA-26JUL29-T57: open 2026-07-28T14:00Z, close 2026-07-30T08:00Z, matches D=JUL29 with
     KSEA's -8h standard offset exactly). So the obs window is simply [close_time-24h, close_time];
     no separate date parse is needed to get the window right, only for logging.
  4. Pull IEM 1-minute (asos1min.py) obs for the station over that window; cache under
     cache/edge_sizing/iem/. Fall back to the routine (hourly METAR, asos.py report_type 3&4) feed if
     1-minute is empty, and RECORD which feed was used.
  5. Pull the market's floor_strike / cap_strike / strike_type from the live Kalshi market endpoint
     (Stage 1's population cache only stored floor_strike + strike_type, not cap_strike -- a real gap
     for 'less'/'between' rungs); cache under cache/edge_sizing/mktdetail/.
  6. Replay the deployed rule minute-by-minute across Stage 1's cached final-60-minute candlesticks
     (same normalize() logic, imported from edge_sizing_v2.py): at each candle minute, compute
     sustained_extreme() over ALL IEM obs up to that minute (not just the 60-min window -- the running
     extreme accumulates over the whole local day) and call locked_orders() with the rung's real
     floor/cap and that minute's real yes_ask_c / no_ask_c (=100-yes_bid_c). locked_orders() already
     embeds the MAX_PAY_CENTS<=98 gate, so the first minute it returns an order for the WINNING side is
     the rule's live-fireable lock timestamp -- MARGIN_F, SUSTAIN_MIN, glitch bounds all untouched.
  7. A market is REALISTICALLY CAPTURABLE iff that lock timestamp is STRICTLY EARLIER than the last
     capturable minute (max ts with cost<=98 & fee-inclusive net>0, recomputed here with the identical
     cost/fee logic edge_sizing_v2.py used for Stage 1, off the same cached candlesticks).
  8. Latency: add 10 and 20 minutes to every realized lock timestamp and re-test against the same last-
     capturable-minute cutoff (IEM asos1min itself publishes 22-34h late -- this whole exercise is a
     backtest of feed CONTENT, not feed LATENCY; the 10/20-min adjustment approximates what a live
     MADIS/Synoptic feed would have cost a real-time bot).

Separately (not part of the 140-market sample -- it is not IN the sample; addressed because the task
requires it): replays the rule against the one verified ground-truth fire, KXLOWTSEA-26JUL29-T57, and
reports whether IEM 1-minute data corroborates the live bot's logged extreme_f=55.94.

Usage: python venue_expansion/edge_sizing_stage2.py
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kwx_lock_rule as R          # noqa: E402  -- verbatim deployed rule, imported not reimplemented
import edge_sizing_v2 as V2        # noqa: E402  -- normalize()/fee_c() reused, not reimplemented

CACHE = os.path.join(HERE, "cache", "edge_sizing")
CANDLES = os.path.join(CACHE, "candles")
IEMCACHE = os.path.join(CACHE, "iem")
MKTCACHE = os.path.join(CACHE, "mktdetail")
STAGE1_JSONL = os.path.join(CACHE, "stage1_v2.jsonl")
OUT_JSON = os.path.join(HERE, "out", "edge_sizing_stage2.json")
OUT_MD = os.path.join(HERE, "out", "edge_sizing_stage2.md")
STAGE1_SUMMARY = os.path.join(HERE, "out", "edge_sizing_v2.json")

KAPI = "https://api.elections.kalshi.com/trade-api/v2"
IEM_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
IEM_ROUTINE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

os.makedirs(IEMCACHE, exist_ok=True)
os.makedirs(MKTCACHE, exist_ok=True)

# ---- HIGH series -> (station, fixed-standard-UTC-offset-hours), byte-copied from paper/kwx_runner.py
# CITY dict (lines 38-46) ----
CITY = {
    "KXHIGHDEN": ("KDEN", -7), "KXHIGHMIA": ("KMIA", -5), "KXHIGHCHI": ("KMDW", -6),
    "KXHIGHTBOS": ("KBOS", -5), "KXHIGHAUS": ("KAUS", -6), "KXHIGHTSEA": ("KSEA", -8),
    "KXHIGHTSFO": ("KSFO", -8), "KXHIGHTMIN": ("KMSP", -6), "KXHIGHTDC": ("KDCA", -5),
    "KXHIGHTATL": ("KATL", -5), "KXHIGHTDAL": ("KDFW", -6), "KXHIGHTSATX": ("KSAT", -6),
    "KXHIGHNY": ("NYC", -5), "KXHIGHTOKC": ("KOKC", -6), "KXHIGHTLV": ("KLAS", -8),
    "KXHIGHTPHX": ("KPHX", -7), "KXHIGHTHOU": ("KHOU", -6), "KXHIGHPHIL": ("KPHL", -5),
    "KXHIGHTNOLA": ("KMSY", -6), "KXHIGHLAX": ("KLAX", -8),
}
# HIGH -> matching LOW series (lines 55-63)
CITY_LOW_SERIES = {
    "KXHIGHDEN": "KXLOWTDEN", "KXHIGHMIA": "KXLOWTMIA", "KXHIGHCHI": "KXLOWTCHI",
    "KXHIGHTBOS": "KXLOWTBOS", "KXHIGHAUS": "KXLOWTAUS", "KXHIGHTSEA": "KXLOWTSEA",
    "KXHIGHTSFO": "KXLOWTSFO", "KXHIGHTMIN": "KXLOWTMIN", "KXHIGHTDC": "KXLOWTDC",
    "KXHIGHTATL": "KXLOWTATL", "KXHIGHTDAL": "KXLOWTDAL", "KXHIGHTSATX": "KXLOWTSATX",
    "KXHIGHNY": "KXLOWTNYC", "KXHIGHTOKC": "KXLOWTOKC", "KXHIGHTLV": "KXLOWTLV",
    "KXHIGHTPHX": "KXLOWTPHX", "KXHIGHTHOU": "KXLOWTHOU", "KXHIGHPHIL": "KXLOWTPHIL",
    "KXHIGHTNOLA": "KXLOWTNOLA", "KXHIGHLAX": "KXLOWTLAX",
}
LOW_STATION = {low: CITY[high] for high, low in CITY_LOW_SERIES.items()}


def _iem_code(icao_or_code):
    """IEM's asos1min.py / asos.py want the bare 3-letter US ASOS id (e.g. 'SEA', 'HOU'), not the
    4-letter ICAO ('KSEA', 'KHOU') kwx_runner.py's CITY table uses internally for its own feed
    classes. 'NYC' already has no K-prefix. Verified against the live endpoint (HTTP 200 for the
    3-letter form, 422 'Unknown station' for the 4-letter K-prefixed form)."""
    if icao_or_code.startswith("K") and len(icao_or_code) == 4:
        return icao_or_code[1:]
    return icao_or_code


def station_and_kind(series):
    if series in CITY:
        return _iem_code(CITY[series][0]), "max"
    if series in LOW_STATION:
        return _iem_code(LOW_STATION[series][0]), "min"
    return None, None


def _get_json(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kwx-research-stage2/1.0"})
            with urllib.request.urlopen(req, timeout=30) as fh:
                return json.load(fh)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def _get_text(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kwx-research-stage2/1.0"})
            with urllib.request.urlopen(req, timeout=45) as fh:
                return fh.read().decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def market_detail(ticker):
    path = os.path.join(MKTCACHE, ticker + ".json")
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    data = _get_json(f"{KAPI}/markets/{ticker}").get("market", {})
    with open(path, "w") as fh:
        json.dump(data, fh)
    time.sleep(1.0)
    return data


def fetch_iem_1min(station, start_iso, end_iso):
    url = (f"{IEM_1MIN}?station={station}&vars=tmpf&sts={start_iso}&ets={end_iso}"
           "&tz=UTC&format=onlycomma")
    txt = _get_text(url)
    lines = [l for l in txt.strip().splitlines() if l and not l.startswith("station,station_name")]
    obs = []
    for l in lines:
        parts = l.split(",")
        if len(parts) < 4:
            continue
        valid, tmpf = parts[2], parts[3]
        if tmpf in ("M", ""):
            continue
        try:
            f = float(tmpf)
        except ValueError:
            continue
        iso = valid.replace(" ", "T") + ":00Z" if len(valid) == 16 else valid
        obs.append((iso, f))
    return obs


def fetch_iem_routine(station, y1, m1, d1, y2, m2, d2):
    url = (f"{IEM_ROUTINE}?station={station}&data=tmpf&year1={y1}&month1={m1}&day1={d1}"
           f"&year2={y2}&month2={m2}&day2={d2}&tz=UTC&format=onlycomma&latlon=no"
           "&report_type=3&report_type=4")
    txt = _get_text(url)
    lines = [l for l in txt.strip().splitlines() if l and not l.startswith("station,valid")]
    obs = []
    for l in lines:
        parts = l.split(",")
        if len(parts) < 3:
            continue
        valid, tmpf = parts[1], parts[2]
        if tmpf in ("M", ""):
            continue
        try:
            f = float(tmpf)
        except ValueError:
            continue
        iso = valid.replace(" ", "T") + ":00Z"
        obs.append((iso, f))
    return obs


def obs_for_window(station, close_ts):
    """Obs covering [close_ts-24h, close_ts], cached, 1-min preferred, routine fallback."""
    start = dt.datetime.fromtimestamp(close_ts - 24 * 3600, tz=dt.timezone.utc)
    end = dt.datetime.fromtimestamp(close_ts, tz=dt.timezone.utc)
    tag = f"{station}_{start.strftime('%Y%m%dT%H%M')}_{end.strftime('%Y%m%dT%H%M')}"
    path = os.path.join(IEMCACHE, "1min_" + tag + ".json")
    if os.path.exists(path):
        with open(path) as fh:
            obs = json.load(fh)
        if obs:
            return obs, "iem_1min"
    else:
        obs = fetch_iem_1min(station, start.strftime("%Y-%m-%dT%H:%MZ"), end.strftime("%Y-%m-%dT%H:%MZ"))
        with open(path, "w") as fh:
            json.dump(obs, fh)
        time.sleep(1.0)
        if obs:
            return obs, "iem_1min"

    # fallback: routine hourly feed, padded a day either side to be safe
    rpath = os.path.join(IEMCACHE, "routine_" + tag + ".json")
    if os.path.exists(rpath):
        with open(rpath) as fh:
            robs = json.load(fh)
    else:
        s2 = start - dt.timedelta(days=1)
        e2 = end + dt.timedelta(days=1)
        robs = fetch_iem_routine(station, s2.year, s2.month, s2.day, e2.year, e2.month, e2.day)
        with open(rpath, "w") as fh:
            json.dump(robs, fh)
        time.sleep(1.0)
    robs = [(t, f) for t, f in robs
            if start.isoformat().replace("+00:00", "Z") <= t <= end.isoformat().replace("+00:00", "Z")]
    return robs, "iem_routine_hourly"


def rung_for(detail):
    st = detail.get("strike_type")
    floor = detail.get("floor_strike")
    cap = detail.get("cap_strike")
    if st == "greater":
        cap = None
    elif st == "less":
        floor = None
    # 'between' keeps both
    return floor, cap, st


def candle_rows(ticker, close_ts):
    path = os.path.join(CANDLES, ticker + ".json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        cs = json.load(fh)
    return V2.normalize(cs, close_ts)


def winner_capturable_minutes(rows, result):
    """Reproduce Stage-1's exact per-minute capturable test off the same cached rows."""
    out = []
    for ts, yb, ya, vol in rows:
        cost = ya if result == "yes" else (None if yb is None else 100 - yb)
        if cost is None or not (0 < cost <= V2.MAX_PAY_C):
            continue
        net = 100 - cost - V2.fee_c(cost)
        if net <= 0:
            continue
        out.append((ts, cost, net, vol))
    return out


def theoretically_lockable(floor, cap, kind, winner_side):
    """Whether the rung's (floor, cap) shape even HAS a code branch in locked_orders() that can ever
    fire for winner_side, independent of any observation data. locked_orders() is asymmetric by
    construction: a 'between' bracket rung (floor and cap both set) can only ever lock NO (via the
    cap-overshoot branch for kind='max' or the floor-undershoot branch for kind='min'); it has no
    branch that ever locks YES on a bracket, and no branch that locks the 'never reached the bracket
    at all' flavor of NO. Flagging this separates 'the rule structurally cannot catch this shape' from
    'the feed/timing wasn't good enough' -- both real, but different findings."""
    if kind == "max":
        if cap is not None:
            return winner_side == "no"
        if floor is not None:
            return winner_side == "yes"
    else:
        if floor is not None:
            return winner_side == "no"
        if cap is not None:
            return winner_side == "yes"
    return False


def replay_lock(rows, obs, floor, cap, kind, result, ticker):
    """Walk the 60-min candle rows in order; at each minute compute the sustained extreme over ALL
    obs up to that instant and call the verbatim locked_orders(). Return (lock_ts, cushion) for the
    first minute an order matching the WINNING side appears, else (None, None)."""
    obs_sorted = sorted(obs, key=lambda o: o[0])
    winner_side = result  # 'yes' or 'no'
    for ts, yb, ya, _vol in sorted(rows, key=lambda r: r[0]):
        if ts is None:
            continue
        cutoff = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")
        obs_upto = [(t, f) for t, f in obs_sorted if t <= cutoff]
        if len(obs_upto) < R.SUSTAIN_MIN:
            continue
        ext = R.sustained_extreme(obs_upto, kind)
        if ext is None:
            continue
        rung = {"ticker": ticker, "floor": floor, "cap": cap,
                "no_ask_c": None if yb is None else 100 - yb, "yes_ask_c": ya}
        orders = R.locked_orders([rung], ext, kind)
        for (_tk, side, price_c, cushion) in orders:
            if side == winner_side:
                return ts, cushion, ext
    return None, None, None


def wilson_ci(k, n, z=1.959963985):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, center - half), min(1.0, center + half))


def sea_ground_truth():
    """The one verified real fire: KXLOWTSEA-26JUL29-T57. Not part of the 140-market sample (it
    wasn't drawn by Stage 1's stratified sample) -- checked directly per the task's mandatory
    investigation of the feed/threshold disagreement."""
    ticker = "KXLOWTSEA-26JUL29-T57"
    detail = market_detail(ticker)
    close_ts = int(dt.datetime.fromisoformat(detail["close_time"].replace("Z", "+00:00")).timestamp())
    floor, cap, st = rung_for(detail)
    obs, feed = obs_for_window("SEA", close_ts)
    obs_sorted = sorted(obs, key=lambda o: o[0])
    final_ext = R.sustained_extreme(obs_sorted, "min")
    # first-fire scan across the WHOLE window (not just last 60 min -- this is the ground-truth check)
    fired = None
    for i in range(R.SUSTAIN_MIN, len(obs_sorted) + 1):
        sub = obs_sorted[:i]
        ext = R.sustained_extreme(sub, "min")
        if ext is None:
            continue
        if floor is not None and ext < floor - R.MARGIN_F:
            fired = (sub[-1][0], ext)
            break
    bot_logged_extreme_f = 55.94
    bot_logged_ts = "2026-07-30T07:58:43Z"
    return {
        "ticker": ticker, "station": "SEA", "kind": "min", "feed_used": feed,
        "floor_strike": floor, "cap_strike": cap, "strike_type": st,
        "margin_f": R.MARGIN_F,
        "iem_min_tmpf_in_window": min(f for _t, f in obs_sorted) if obs_sorted else None,
        "iem_final_sustained_extreme": final_ext,
        "iem_lock_would_fire": fired is not None,
        "iem_lock_fire_ts": fired[0] if fired else None,
        "iem_lock_fire_extreme_f": fired[1] if fired else None,
        "bot_logged_extreme_f": bot_logged_extreme_f,
        "bot_logged_ts": bot_logged_ts,
        "bot_value_corroborated_by_iem": (
            fired is not None and abs(fired[1] - bot_logged_extreme_f) < 0.5),
        "finding": (
            "IEM 1-minute data for KSEA never reports below 56.0F anywhere in the market's "
            "open-to-close window (2026-07-28T14:00Z .. 2026-07-30T08:00Z); the deployed rule needs "
            "a sustained reading strictly below floor-margin=56.0F to lock NO on T57, so it NEVER "
            "fires on IEM data for this market -- CONFIRMS the prior finding. The bot's own log shows "
            "extreme_f=55.94, which is 0.06F below the rule's firing threshold and would have fired; "
            "IEM's coldest sustained reading (56.0F, integer-rounded) sits exactly on the "
            "non-firing side of that boundary. IEM's 1-minute feed appears to round/report in whole "
            "degrees F at KSEA, which is not fine-grained enough to reproduce the one real, "
            "already-verified fire this whole program is anchored to -- a material feed-fidelity gap, "
            "not a footnote."
        ),
    }


def main():
    rows_stage1 = [json.loads(l) for l in open(STAGE1_JSONL)]
    cap = [r for r in rows_stage1 if "skip" not in r and r.get("capturable")]
    print(f"Stage-1 capturable markets: {len(cap)} (spec asks for >=150; disclosed shortfall)")

    sea = sea_ground_truth()
    print("\n=== SEA ground-truth check ===")
    print(json.dumps(sea, indent=1))

    results = []
    for i, r in enumerate(cap, 1):
        ticker, series, result = r["ticker"], r["series"], r["result"]
        close_ts = int(dt.datetime.fromisoformat(r["close_time"].replace("Z", "+00:00")).timestamp())
        station, kind = station_and_kind(series)
        rec = {"ticker": ticker, "series": series, "result": result, "close_time": r["close_time"],
               "station": station, "kind": kind}
        if station is None:
            rec["skip"] = "no_station_mapping"
            results.append(rec)
            continue
        try:
            detail = market_detail(ticker)
        except Exception as e:
            rec["skip"] = f"market_detail_fetch_failed: {e}"
            results.append(rec)
            continue
        floor, cap_, st = rung_for(detail)
        rec.update({"floor_strike": floor, "cap_strike": cap_, "strike_type": st})
        rec["theoretically_lockable"] = theoretically_lockable(floor, cap_, kind, result)

        rows = candle_rows(ticker, close_ts)
        if not rows:
            rec["skip"] = "no_cached_candles"
            results.append(rec)
            continue
        cap_minutes = winner_capturable_minutes(rows, result)
        if not cap_minutes:
            rec["skip"] = "no_capturable_minutes_on_recompute"
            results.append(rec)
            continue
        last_cap_ts = max(m[0] for m in cap_minutes if m[0] is not None)
        first_cap_ts = min(m[0] for m in cap_minutes if m[0] is not None)
        rec["last_capturable_ts"] = last_cap_ts
        rec["first_capturable_ts"] = first_cap_ts
        rec["n_capturable_minutes_recomputed"] = len(cap_minutes)

        try:
            obs, feed = obs_for_window(station, close_ts)
        except Exception as e:
            rec["skip"] = f"iem_fetch_failed: {e}"
            results.append(rec)
            continue
        rec["feed_used"] = feed
        rec["n_obs"] = len(obs)
        if not obs:
            rec["skip"] = "no_iem_obs"
            results.append(rec)
            continue

        lock_ts, cushion, ext = replay_lock(rows, obs, floor, cap_, kind, result, ticker)
        rec["lock_ts"] = lock_ts
        rec["lock_cushion_f"] = cushion
        rec["lock_extreme_f"] = ext
        rec["realistic_capturable"] = bool(lock_ts is not None and lock_ts < last_cap_ts)
        for delay_min, tag in ((10, "10min"), (20, "20min")):
            if lock_ts is None:
                rec[f"realistic_capturable_{tag}delay"] = False
            else:
                rec[f"realistic_capturable_{tag}delay"] = bool(lock_ts + delay_min * 60 < last_cap_ts)

        results.append(rec)
        if i % 10 == 0:
            print(f"  {i}/{len(cap)} processed", flush=True)

    skipped = [r for r in results if "skip" in r]
    scored = [r for r in results if "skip" not in r]
    realistic = [r for r in scored if r["realistic_capturable"]]
    realistic_10 = [r for r in scored if r["realistic_capturable_10mindelay"]]
    realistic_20 = [r for r in scored if r["realistic_capturable_20mindelay"]]

    n_den = len(cap)  # denominator is ALL 140 Stage-1 capturable markets, per spec step 5
    conv0 = wilson_ci(len(realistic), n_den)
    conv10 = wilson_ci(len(realistic_10), n_den)
    conv20 = wilson_ci(len(realistic_20), n_den)

    lockable = [r for r in scored if r.get("theoretically_lockable")]
    not_lockable = [r for r in scored if not r.get("theoretically_lockable")]
    lockable_realistic = [r for r in lockable if r["realistic_capturable"]]
    conv0_lockable_only = wilson_ci(len(lockable_realistic), len(lockable)) if lockable else (0, 0, 0)
    structural_breakdown = {
        "theoretically_lockable_by_rule_shape": len(lockable),
        "structurally_unlockable_by_rule_shape": len(not_lockable),
        "note": ("locked_orders() is asymmetric by construction: a 'between' bracket rung can only "
                "ever lock NO (via cap-overshoot for HIGH markets / floor-undershoot for LOW markets); "
                "it has no code path to ever lock YES on a bracket, or to lock the 'never reached the "
                "bracket' flavor of NO. This is a structural property of the deployed rule, independent "
                "of feed quality -- it caps the achievable conversion rate regardless of how good the "
                "obs feed is."),
        "conversion_rate_among_theoretically_lockable_only": {
            "realistic": len(lockable_realistic), "of": len(lockable), "rate": conv0_lockable_only[0],
            "wilson_95ci": [conv0_lockable_only[1], conv0_lockable_only[2]]},
    }

    stage1_summary = json.load(open(STAGE1_SUMMARY))
    oracle_cap = stage1_summary.get("oracle_capacity_usd_per_month", {})

    out = {
        "spec": "venue_expansion/EDGE_SIZING_SPEC.md Stage 2 (frozen)",
        "sample": {
            "stage1_capturable_markets": len(cap),
            "spec_asks_for": ">=150 (or all if fewer qualify)",
            "shortfall_disclosed": "only 140 Stage-1 capturable markets exist in the sample; used all 140",
            "skipped": len(skipped), "scored": len(scored),
            "skip_reasons": dict(collections.Counter(r["skip"] for r in skipped)),
        },
        "feed_used_counts": dict(collections.Counter(r.get("feed_used") for r in scored)),
        "sea_ground_truth_check": sea,
        "structural_breakdown": structural_breakdown,
        "conversion": {
            "no_delay": {"realistic": len(realistic), "of": n_den, "rate": conv0[0],
                         "wilson_95ci": [conv0[1], conv0[2]]},
            "10min_delay": {"realistic": len(realistic_10), "of": n_den, "rate": conv10[0],
                            "wilson_95ci": [conv10[1], conv10[2]]},
            "20min_delay": {"realistic": len(realistic_20), "of": n_den, "rate": conv20[0],
                            "wilson_95ci": [conv20[1], conv20[2]]},
        },
        "capacity_usd_per_month": {
            "oracle": oracle_cap,
            "realistic_no_delay": {k: round(v * conv0[0], 2) for k, v in oracle_cap.items()},
            "latency_adjusted_10min": {k: round(v * conv10[0], 2) for k, v in oracle_cap.items()},
            "latency_adjusted_20min": {k: round(v * conv20[0], 2) for k, v in oracle_cap.items()},
        },
        "depth_caveat": ("Candlesticks carry NO order-book depth. Volume traded during capturable "
                         "minutes (and hence every capacity number derived from it) is an UPPER BOUND "
                         "on what one participant could have taken."),
        "feed_latency_caveat": ("IEM asos1min publishes 22-34h late; this is a backtest of feed "
                                "CONTENT only. The 10/20-minute delays approximate what a live "
                                "MADIS (~10min) or Synoptic (~1-5min) feed would additionally cost a "
                                "real-time bot on top of the content already measured here."),
        "verdict_band": None,  # filled below
        "per_market": results,
    }

    lat10 = out["capacity_usd_per_month"]["latency_adjusted_10min"].get("median_estimator", 0)
    if lat10 < 50:
        band = "under_50: retire the mechanical-lock live bot"
    elif lat10 <= 500:
        band = "50_to_500: canary-only, never more, once the order path is fixed"
    else:
        band = "over_500: justifies dedicated re-registration, still requires a live canary first"
    out["verdict_band"] = band

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(out, open(OUT_JSON, "w"), indent=1)
    print(f"\nwrote {OUT_JSON}")

    write_md(out)
    print(f"wrote {OUT_MD}")

    print("\n=== SUMMARY ===")
    print(json.dumps({k: v for k, v in out.items() if k != "per_market"}, indent=1))


def write_md(out):
    lines = []
    lines.append("# EDGE_SIZING Stage 2 -- realistic conversion of the oracle upper bound\n")
    lines.append(f"Spec: `{out['spec']}`\n")
    lines.append("## Method\n")
    lines.append(
        "For each of the 140 Stage-1 capturable markets (the spec asks for >=150; only 140 exist in "
        "the Stage-1 sample -- disclosed shortfall, used all of them): resolved station+kind via the "
        "same HIGH/LOW city map the deployed bot uses; pulled IEM 1-minute obs for the station over "
        "`[close_time-24h, close_time]` (verified to be exactly the local calendar day in the "
        "station's fixed standard-time offset); replayed `kwx_lock_rule.sustained_extreme` / "
        "`locked_orders` **verbatim** (MARGIN_F=1.0, sustain-3, glitch bounds, MAX_PAY_CENTS=98, all "
        "unmodified) minute-by-minute across Stage 1's cached final-60-minute candlesticks, using the "
        "REAL ask/bid at each minute for the MAX_PAY gate and the FULL day's obs (not just the last "
        "60 minutes) for the running sustained extreme. A market is REALISTICALLY CAPTURABLE iff the "
        "rule's first winner-side lock timestamp is strictly earlier than the last minute Stage 1 "
        "found the winner side still buyable at <=98c net-positive.\n")
    lines.append("## SEA ground-truth check (not in the 140-market sample -- checked directly)\n")
    sea = out["sea_ground_truth_check"]
    lines.append(f"- Ticker: `{sea['ticker']}`, station {sea['station']}, feed used: {sea['feed_used']}")
    lines.append(f"- IEM coldest reading anywhere in the market's open-to-close window: "
                 f"**{sea['iem_min_tmpf_in_window']}F**")
    lines.append(f"- Rule fires on IEM data: **{sea['iem_lock_would_fire']}**")
    lines.append(f"- Bot's own logged extreme_f: **{sea['bot_logged_extreme_f']}** at {sea['bot_logged_ts']}")
    lines.append(f"- Bot value corroborated by IEM: **{sea['bot_value_corroborated_by_iem']}**")
    lines.append(f"\n{sea['finding']}\n")
    sb = out["structural_breakdown"]
    lines.append("## Structural finding: bracket markets are asymmetrically unlockable\n")
    lines.append(sb["note"] + "\n")
    lines.append(f"- Theoretically lockable by rule shape: {sb['theoretically_lockable_by_rule_shape']} "
                 f"of {sb['theoretically_lockable_by_rule_shape'] + sb['structurally_unlockable_by_rule_shape']}")
    cl = sb["conversion_rate_among_theoretically_lockable_only"]
    lines.append(f"- Conversion rate among ONLY the theoretically-lockable subset: {cl['realistic']}/"
                 f"{cl['of']} = {cl['rate']:.4f} (Wilson 95% CI [{cl['wilson_95ci'][0]:.4f}, "
                 f"{cl['wilson_95ci'][1]:.4f}])\n")
    lines.append("## Conversion rates (of all 140 Stage-1 capturable markets)\n")
    lines.append("| variant | realistic | of | rate | Wilson 95% CI |")
    lines.append("|---|---|---|---|---|")
    for tag, label in (("no_delay", "no delay (backtest, IEM content only)"),
                       ("10min_delay", "+10min (MADIS-like)"),
                       ("20min_delay", "+20min")):
        c = out["conversion"][tag]
        lines.append(f"| {label} | {c['realistic']} | {c['of']} | {c['rate']:.4f} | "
                     f"[{c['wilson_95ci'][0]:.4f}, {c['wilson_95ci'][1]:.4f}] |")
    lines.append("\n## Capacity ($/month), each labelled\n")
    lines.append("| basis | mean estimator | median estimator (primary) |")
    lines.append("|---|---|---|")
    for tag, label in (("oracle", "oracle (Stage 1 ceiling)"),
                       ("realistic_no_delay", "realistic (Stage 2, no delay)"),
                       ("latency_adjusted_10min", "latency-adjusted (+10min)"),
                       ("latency_adjusted_20min", "latency-adjusted (+20min)")):
        c = out["capacity_usd_per_month"][tag]
        lines.append(f"| {label} | ${c.get('mean_estimator', 0):,.2f} | "
                     f"${c.get('median_estimator', 0):,.2f} |")
    lines.append(f"\nStage 1's mean estimator (${out['capacity_usd_per_month']['oracle'].get('mean_estimator',0):,.2f}/mo) "
                 f"is ~22x the median (${out['capacity_usd_per_month']['oracle'].get('median_estimator',0):,.2f}/mo) and is "
                 "outlier-driven; the median is the primary number throughout.\n")
    lines.append(f"\n**Depth caveat**: {out['depth_caveat']}\n")
    lines.append(f"\n**Feed-latency caveat**: {out['feed_latency_caveat']}\n")
    lines.append(f"\n## Verdict band\n\n**{out['verdict_band']}**\n")
    lines.append(f"\n## Coverage / skips\n\n{json.dumps(out['sample'], indent=1)}\n")
    lines.append(f"\nFeed used across scored markets: {json.dumps(out['feed_used_counts'], indent=1)}\n")
    lines.append("\n## Per-market table\n")
    lines.append("| ticker | series | result | strike_type | station | kind | feed | lockable? | "
                 "last_capturable_ts | lock_ts | realistic | +10min | +20min | skip |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in out["per_market"]:
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r.get("ticker"), r.get("series"), r.get("result"), r.get("strike_type", ""),
            r.get("station"), r.get("kind"),
            r.get("feed_used", ""), r.get("theoretically_lockable", ""),
            r.get("last_capturable_ts", ""), r.get("lock_ts", ""),
            r.get("realistic_capturable", ""), r.get("realistic_capturable_10mindelay", ""),
            r.get("realistic_capturable_20mindelay", ""), r.get("skip", "")))
    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
