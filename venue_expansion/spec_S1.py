#!/usr/bin/env python3
"""spec_S1.py -- registered spec S1: "Polymarket whitelist EV at MEASURED asks (pmxt.dev order-book archive)".

Frozen spec: venue_expansion/out/judge_specs.json, id "S1" (registered 2026-07-23, never run until now).
This file is a REWRITE of the dead run's partial draft; the draft was treated as unverified scaffolding.
Nothing here is tuned. Read the .md (out/spec_S1.md) for method, every skip, and the frozen bar.

PIPELINE (each stage is resumable; everything pulled is cached under venue_expansion/cache/spec_s1/):
  python3 spec_S1.py weather            # stage 0/1: gamma ladders + 4 weather feeds -> phase1.json (no pmxt, no prices)
  python3 spec_S1.py plan [A|B]         # list the pmxt hour-files needed (A: hour of each signal; B: continuation hours)
  python3 spec_S1.py fetch A i/n        # mirror hour-files i of n (parallel shards); resumable
  python3 spec_S1.py analyze            # price every fire at the measured best ask, apply the frozen bar, write results

SIGNAL (frozen, weather-only, no market input, no outcome input): kwx_lock_rule.sustained_extreme (byte-identical shim of the
deployed rule) -> running glitch-filtered sustain-3 extreme; an item-2b ENTRY is the first obs at which that extreme falls in
a rung's margin-adjusted band  (floor+margin < extreme <= cap+margin);  item-2a LOCKS come from kwx_lock_rule.locked_orders.
ENTRY PRICE: best ask of the rung's YES token at the first pmxt event at timestamp_received >= signal time that carries an
ask; none inside 60 min => UNPRICEABLE (counted, never back-filled). Hold to the venue's own resolution.
EV: payout(100 if rung resolved YES) - ask_cents - 100*0.05*p*(1-p), p = ask. Cluster = city-day.

Read-only public data only (Gamma, IEM Mesonet, JMA, pmxt.dev). No auth, no orders.
"""
import datetime as dt
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
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kwx_lock_rule as R   # deployed rule, byte-identical (sustained_extreme, locked_orders)

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "*/*", "User-Agent": "Mozilla/5.0 (compatible; spec-s1/2.0)"}

GBASE = "https://gamma-api.polymarket.com"
DAILY_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
ASOS_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
JMA_10MIN = "https://www.data.jma.go.jp/stats/etrn/view/10min_a1.php"
PMXT_TPL = "https://r2v2.pmxt.dev/polymarket_orderbook_{h}.parquet"

CACHE_DIR = os.path.join(HERE, "cache", "spec_s1")
PMXT_DIR = os.path.join(CACHE_DIR, "pmxt")
OUT_DIR = os.path.join(HERE, "out")
for _d in (CACHE_DIR, PMXT_DIR, OUT_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------------------------------------------
# FROZEN by the registration (judge_specs.json S1)
# ---------------------------------------------------------------------------------------------------------------
WINDOW_START = dt.date(2026, 4, 14)
WINDOW_END = dt.date(2026, 7, 18)
PMXT_COVERAGE_START = dt.datetime(2026, 4, 13, 19, 0, tzinfo=dt.timezone.utc)
ASK_SEARCH_WINDOW_MIN = 60
FEE_RATE = 0.05                      # Polymarket weather taker fee: 0.05*p*(1-p), taker-only
PASS_T, PASS_MEAN_C = 2.25, 0.5      # PASS iff cluster-t >= 2.25 AND mean net EV >= +0.5c
KILL_Z, KILL_UCB_C = 2.128, 0.2      # KILL iff one-sided 98.33% UCB of mean net EV < +0.2c
MIN_PRICED, MIN_CLUSTERS = 120, 40
MAX_UNPRICEABLE_FRAC, MAX_UNREADABLE_FRAC = 0.40, 0.20

CITIES = {
    "chicago": dict(station="ORD", unit="F", tz="America/Chicago", margin=1.0, feed="chicago_1min"),
    "tokyo":   dict(station="RJTT", unit="C", tz="Asia/Tokyo", margin=0.5, feed="jma_10min",
                    jma_prec=44, jma_block="0371"),
    "london":  dict(station="EGLC", unit="C", tz="Europe/London", margin=0.5, feed="iem_30min"),
    "paris":   dict(station="LFPB", unit="C", tz="Europe/Paris", margin=0.5, feed="iem_30min"),
}
# Completeness guards (set before any real obs were seen; Chicago values equal tracka_chicago_1min.py's own).
GUARDS = {
    "chicago_1min": dict(min_day_obs=100, max_end_gap_h=3),
    "iem_30min":    dict(min_day_obs=30, max_end_gap_h=4),
    "jma_10min":    dict(min_day_obs=90, max_end_gap_h=4),
}


# ===============================================================================================================
# HTTP + cache helpers
# ===============================================================================================================
def _get_text(url, timeout=60, retries=6, backoff=2.0):
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return urllib.request.urlopen(req, timeout=timeout, context=_CTX).read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            last = e
            time.sleep(backoff * (a + 1))
    print(f"    !! _get_text FAILED after {retries} tries: {url} -- {last}", file=sys.stderr)
    return None


def _get_json(url, timeout=30, retries=6, backoff=1.6):
    """-> parsed json, {"__404__":True}, or {"__err__":...}. Errors are NEVER cached by callers."""
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                return {"__404__": True}
            time.sleep(backoff * (a + 1))
        except Exception as e:  # noqa
            last = e
            time.sleep(backoff * (a + 1))
    return {"__err__": f"{type(last).__name__}: {last}"}


def _cp(name):
    return os.path.join(CACHE_DIR, name)


def _cache_get(name):
    p = _cp(name)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        try:
            return json.load(open(p))
        except Exception:
            return None
    return None


def _cache_put(name, obj):
    tmp = _cp(name) + ".tmp"
    json.dump(obj, open(tmp, "w"))
    os.replace(tmp, _cp(name))


# ===============================================================================================================
# Gamma ladder harness (parse_rung_native / event_rungs_native: tracka_chicago_1min.py logic; token order is now
# CHECKED against the market's own `outcomes` field instead of assumed)
# ===============================================================================================================
def parse_rung_native(label):
    s = label.replace("°F", "").replace("°C", "").strip()
    if "or below" in s:
        return None, float(s.split()[0]) + 0.5
    if "or higher" in s or "or above" in s:
        return float(s.split()[0]) - 0.5, None
    if "-" in s:
        lo, hi = s.split("-")
        return float(lo) - 0.5, float(hi) + 0.5
    v = float(s)
    return v - 0.5, v + 0.5


_KEEP = ["id", "groupItemTitle", "outcomes", "outcomePrices", "clobTokenIds", "closed", "closedTime",
         "umaResolutionStatus", "feeSchedule", "endDate"]


def fetch_event(city_slug, d):
    slug = f"highest-temperature-in-{city_slug}-on-{d.strftime('%B').lower()}-{d.day}-{d.year}"
    key = f"event_{slug}.json"
    c = _cache_get(key)
    if c is not None:
        return c
    ev = _get_json(f"{GBASE}/events/slug/{slug}")
    time.sleep(0.6)
    if "__err__" in ev:
        return ev                       # transient: not cached
    if "__404__" in ev:
        _cache_put(key, ev)
        return ev
    slim = {"slug": slug, "id": ev.get("id"), "closed": ev.get("closed"),
            "markets": [{k: m.get(k) for k in _KEEP} for m in ev.get("markets", [])]}
    _cache_put(key, slim)
    return slim


def event_rungs_native(event):
    """-> (rungs, titles, winner_ticker) or None. Resolution = the venue's own outcomePrices == [1,0] (YES)."""
    mkts = event.get("markets", [])
    if not mkts:
        return None
    rungs, titles, winners = [], {}, []
    for m in mkts:
        if not m.get("closed"):
            return None
        label = m.get("groupItemTitle", "")
        try:
            floor, cap = parse_rung_native(label)
        except Exception:
            return None
        try:
            toks = json.loads(m.get("clobTokenIds") or "[]")
            outs = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
            prices = json.loads(m["outcomePrices"]) if isinstance(m["outcomePrices"], str) else m["outcomePrices"]
        except Exception:
            return None
        if len(toks) != 2 or len(outs) != 2 or len(prices) != 2 or sorted(outs) != ["No", "Yes"]:
            return None
        iy = outs.index("Yes")
        ticker = m.get("id") or label
        titles[ticker] = label
        if abs(float(prices[iy]) - 1.0) < 1e-6:
            winners.append(ticker)
        rungs.append({"ticker": ticker, "floor": floor, "cap": cap, "yes_ask_c": 50, "no_ask_c": 50,
                      "yes_tok": toks[iy], "no_tok": toks[1 - iy]})
    if len(winners) != 1:
        return None
    return rungs, titles, winners[0]


# ===============================================================================================================
# WEATHER FEEDS
# ===============================================================================================================
def _daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


def fetch_chicago_all():
    """IEM true 1-minute ASOS, station ORD, whole window in 8-day chunks (cached per chunk)."""
    out = {}
    d = WINDOW_START - dt.timedelta(days=1)
    last = WINDOW_END + dt.timedelta(days=2)
    while d <= last:
        e = min(d + dt.timedelta(days=8), last + dt.timedelta(days=1))
        sts, ets = f"{d.isoformat()}T00:00Z", f"{e.isoformat()}T00:00Z"
        key = f"asos1min_ORD_{d}_{e}.json"
        raw = _cache_get(key)
        if raw is None:
            txt = _get_text(f"{ASOS_1MIN}?station=ORD&vars=tmpf&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma")
            if txt is None:
                raise RuntimeError(f"IEM 1min fetch failed {sts}..{ets}")
            raw = []
            for line in txt.splitlines():
                if not line or line.startswith("station,"):
                    continue
                p = line.split(",")
                if len(p) < 4 or p[3] in ("", "M"):
                    continue
                try:
                    t = dt.datetime.strptime(p[2].strip(), "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                    v = float(p[3])
                except ValueError:
                    continue
                raw.append((t.isoformat(), v))
            _cache_put(key, raw)
            time.sleep(1.0)
        for t, v in raw:
            out[t] = v
        d = e
    return sorted((dt.datetime.fromisoformat(t), v) for t, v in out.items())


def fetch_iem_bulk(station):
    """London/Paris: IEM asos.py, report_type=3&4 (routine + special => ~48/day), one bulk request.
    day2 is an EXCLUSIVE bound (measured quirk in pmkt_final_verdict.py) -> padded."""
    key = f"asos_bulk_{station}_{WINDOW_START}_{WINDOW_END}.json"
    raw = _cache_get(key)
    if raw is None:
        s = WINDOW_START - dt.timedelta(days=1)
        e = WINDOW_END + dt.timedelta(days=3)
        q = (f"station={station}&data=tmpf&year1={s.year}&month1={s.month}&day1={s.day}"
             f"&year2={e.year}&month2={e.month}&day2={e.day}&tz=UTC&format=onlycomma&latlon=no&elev=no"
             f"&missing=M&trace=T&direct=no&report_type=3&report_type=4")
        txt = _get_text(f"{DAILY_ASOS}?{q}")
        if txt is None:
            raise RuntimeError(f"IEM bulk fetch failed {station}")
        raw = []
        for line in txt.splitlines():
            if not line or line.startswith("station,"):
                continue
            p = line.split(",")
            if len(p) < 3 or p[2] in ("", "M", "T"):
                continue
            try:
                t = dt.datetime.strptime(p[1].strip(), "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                v = float(p[2])
            except ValueError:
                continue
            raw.append((t.isoformat(), v))
        _cache_put(key, raw)
        time.sleep(1.0)
    uniq = {}
    for t, v in raw:
        uniq[t] = v
    return sorted((dt.datetime.fromisoformat(t), v) for t, v in uniq.items())


_ROW = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
_CELL = re.compile(r'<td[^>]*>(.*?)</td>', re.S)


def fetch_jma_day(d, prec_no, block_no):
    """One JMA 10-min AMeDAS page = one JST day: rows 00:10 .. 24:00 (24:00 == next day's 00:00)."""
    key = f"jma_{prec_no}_{block_no}_{d.isoformat()}.json"
    raw = _cache_get(key)
    if raw is None:
        html = _get_text(f"{JMA_10MIN}?prec_no={prec_no}&block_no={block_no}&year={d.year}&month={d.month}&day={d.day}&view=")
        if html is None:
            raise RuntimeError(f"JMA fetch failed {d}")
        m = re.search(r'<table[^>]*id="tablefix1"[^>]*>(.*?)</table>', html, re.S)
        body = m.group(1) if m else html
        tz = ZoneInfo("Asia/Tokyo")
        raw = []
        for rowhtml in _ROW.findall(body):
            cells = [c.strip() for c in _CELL.findall(rowhtml)]
            if len(cells) < 3:
                continue
            tstr, temp_s = cells[0], cells[2]
            if not re.fullmatch(r"\d\d:\d\d", tstr) or temp_s in ("", "///", "--", "-", "×"):
                continue
            try:
                temp_c = float(temp_s)
            except ValueError:
                continue
            hh, mm = int(tstr[:2]), int(tstr[3:])
            base = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz)
            local = base + dt.timedelta(hours=hh, minutes=mm)          # handles 24:00
            raw.append((local.astimezone(dt.timezone.utc).isoformat(), temp_c))
        _cache_put(key, raw)
        time.sleep(1.0)
    return [(dt.datetime.fromisoformat(t), v) for t, v in raw]


def fetch_jma_all(cfg):
    out = {}
    for d in _daterange(WINDOW_START - dt.timedelta(days=1), WINDOW_END):
        for t, c in fetch_jma_day(d, cfg["jma_prec"], cfg["jma_block"]):
            out[t] = c * 9.0 / 5.0 + 32.0     # to degF: every other feed (and the deployed rule's glitch consts) are degF
    return sorted(out.items())


# ===============================================================================================================
# SIGNAL: identical construction to tracka_chicago_1min.py / pmkt_final_verdict.py backtest_day, with ALL entries kept
# ===============================================================================================================
def _round_native(x, unit):
    # F->C->F float noise (e.g. 28.0C -> 82.4F -> 28.000000000000004C) would flip strict comparisons at integer
    # thresholds. Harness-level housekeeping only; the rule itself is untouched. The un-rounded stream is also
    # tracked (entries_raw) purely to count how many entries this changes.
    return round(x, 6) if unit == "C" else x


def backtest_day(city_slug, d, cfg, day_obs, guard, day_start, day_end):
    unit, margin = cfg["unit"], cfg["margin"]
    ev = fetch_event(city_slug, d)
    if not isinstance(ev, dict) or "__err__" in ev:
        return {"skip": "event_fetch_error"}
    if "__404__" in ev:
        return {"skip": "event_not_found"}
    parsed = event_rungs_native(ev)
    if parsed is None:
        return {"skip": "not_resolved_or_unparseable"}
    rungs, titles, winner = parsed
    tokens = [t for r in rungs for t in (r["yes_tok"], r["no_tok"])]

    if len(day_obs) < guard["min_day_obs"]:
        return {"skip": f"thin_station_data_{len(day_obs)}obs", "tokens": tokens}
    if day_obs[-1][0] < day_end - dt.timedelta(hours=guard["max_end_gap_h"]):
        return {"skip": "station_feed_gap_near_dayend", "tokens": tokens}

    locked, entries, entries_raw = {}, {}, {}
    iso = [(t.isoformat(), v) for t, v in day_obs]
    for i in range(1, len(day_obs) + 1):
        extreme_f = R.sustained_extreme(iso[:i], "max")
        if extreme_f is None:
            continue
        raw_native = extreme_f if unit == "F" else (extreme_f - 32.0) * 5.0 / 9.0
        nat = _round_native(raw_native, unit)
        ts = day_obs[i - 1][0].isoformat()
        for ticker, side, _cap, cushion in R.locked_orders(rungs, nat, "max", margin=margin):
            if ticker not in locked:
                locked[ticker] = {"side": side, "lock_utc": ts, "cushion": round(cushion, 3), "extreme": round(nat, 3)}
        for r in rungs:
            fl, cp = r["floor"], r["cap"]
            for store, val in ((entries, nat), (entries_raw, raw_native)):
                if r["ticker"] in store:
                    continue
                if (fl is None or val > fl + margin) and (cp is None or val <= cp + margin):
                    store[r["ticker"]] = {"entry_utc": ts, "extreme": round(val, 3)}

    byt = {r["ticker"]: r for r in rungs}

    def _ent(store):
        return [{"city": city_slug, "date": d.isoformat(), "ticker": t, "label": titles[t],
                 "floor": byt[t]["floor"], "cap": byt[t]["cap"], "entry_utc": i["entry_utc"], "extreme": i["extreme"],
                 "yes_tok": byt[t]["yes_tok"], "no_tok": byt[t]["no_tok"], "won": t == winner}
                for t, i in store.items()]
    ent, ent_raw = _ent(entries), _ent(entries_raw)
    lck = [{"city": city_slug, "date": d.isoformat(), "ticker": t, "label": titles[t], "side": i["side"],
            "lock_utc": i["lock_utc"], "cushion": i["cushion"], "extreme": i["extreme"],
            "tok": byt[t]["yes_tok"] if i["side"] == "yes" else byt[t]["no_tok"],
            "correct": (t == winner) if i["side"] == "yes" else (t != winner)}
           for t, i in locked.items()]
    n_changed = sum(1 for t in set(entries) | set(entries_raw)
                    if (entries.get(t) or {}).get("entry_utc") != (entries_raw.get(t) or {}).get("entry_utc"))
    return {"skip": None, "entries": ent, "entries_raw": ent_raw, "locks": lck, "tokens": tokens, "winner": winner,
            "winner_label": titles[winner], "n_rungs": len(rungs), "n_day_obs": len(day_obs),
            "winner_never_entered": winner not in entries, "n_entries_changed_by_rounding": n_changed}


def run_weather():
    t0 = time.time()
    print("=== STAGE 1: weather-only signal across 4 cities (no pmxt, no prices) ===", flush=True)
    results = {}
    for city, cfg in CITIES.items():
        feed = cfg["feed"]
        g = GUARDS[feed]
        print(f"\n[{city}] feed={feed}", flush=True)
        if feed == "chicago_1min":
            obs_all = fetch_chicago_all()
        elif feed == "iem_30min":
            obs_all = fetch_iem_bulk(cfg["station"])
        else:
            obs_all = fetch_jma_all(cfg)
        print(f"    {len(obs_all)} obs pulled", flush=True)
        tz = ZoneInfo(cfg["tz"])
        for d in _daterange(WINDOW_START, WINDOW_END):
            ck = f"day_{city}_{d}.json"
            c = _cache_get(ck)
            if c is not None:
                results[(city, d.isoformat())] = c
                continue
            ds = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz).astimezone(dt.timezone.utc)
            de = (dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz) + dt.timedelta(days=1)).astimezone(dt.timezone.utc)
            day_obs = [(t, v) for t, v in obs_all if ds <= t < de]
            r = backtest_day(city, d, cfg, day_obs, g, ds, de)
            if r.get("skip") == "event_fetch_error":
                print(f"    {d} ERROR (not cached, rerun)", flush=True)
                continue
            _cache_put(ck, r)
            results[(city, d.isoformat())] = r
            msg = r["skip"] or f"{len(r['entries'])} entries {len(r['locks'])} locks obs={r['n_day_obs']}"
            print(f"    {d} {msg}", flush=True)
    # assemble
    entries, entries_raw, locks, skips, days, tokens = [], [], [], [], [], {}
    for (city, ds), r in sorted(results.items()):
        if r.get("tokens"):
            tokens[f"{city}|{ds}"] = r["tokens"]
        if r.get("skip"):
            skips.append({"city": city, "date": ds, "reason": r["skip"]})
            continue
        entries += r["entries"]
        entries_raw += r["entries_raw"]
        locks += r["locks"]
        days.append({"city": city, "date": ds, "n_entries": len(r["entries"]), "n_locks": len(r["locks"]),
                     "n_day_obs": r["n_day_obs"], "winner": r["winner_label"],
                     "winner_never_entered": r["winner_never_entered"],
                     "n_entries_changed_by_rounding": r["n_entries_changed_by_rounding"]})
    expect = len(CITIES) * ((WINDOW_END - WINDOW_START).days + 1)
    out = {"built_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "expected_city_days": expect,
           "n_city_days_resolved": len(results), "entries": entries, "entries_raw": entries_raw, "locks": locks, "skips": skips,
           "days": days, "tokens": tokens}
    _cache_put("phase1.json", out)
    print(f"\nPHASE 1 done: {len(results)}/{expect} city-days resolved, {len(days)} usable, {len(skips)} skipped, "
          f"{len(entries)} entries, {len(locks)} locks ({time.time()-t0:.0f}s)")
    if len(results) < expect:
        print("!! some city-days not resolved (transient errors) -- rerun `weather`")
    return out


# ===============================================================================================================
# pmxt hour planning + mirror
# ===============================================================================================================
def hstr(t):
    return t.strftime("%Y-%m-%dT%H")


def _parse_t(s):
    t = dt.datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def watchlist_for_hour(p1, hour_str):
    hd = dt.datetime.strptime(hour_str, "%Y-%m-%dT%H").date()
    toks = set()
    for k, tl in p1["tokens"].items():
        city, ds = k.split("|")
        dd = dt.date.fromisoformat(ds)
        if abs((dd - hd).days) <= 1:
            toks.update(tl)
    return sorted(toks)


def fires_of(p1):
    """Every fire we price. kind: entry (rounded-native signal = PRIMARY, gating) | entry_rawdiff (entries that exist only
    under the reference harness's un-rounded float conversion; variant, non-gating) | lock (item-2a, non-gating)."""
    out = []
    prim = {(e["city"], e["date"], e["ticker"], e["entry_utc"]) for e in p1["entries"]}
    for e in p1["entries"]:
        out.append({"kind": "entry", "city": e["city"], "date": e["date"], "ticker": e["ticker"], "tok": e["yes_tok"],
                    "t": _parse_t(e["entry_utc"]), "win": e["won"], "side": "yes"})
    for e in p1.get("entries_raw", []):
        if (e["city"], e["date"], e["ticker"], e["entry_utc"]) not in prim:
            out.append({"kind": "entry_rawdiff", "city": e["city"], "date": e["date"], "ticker": e["ticker"],
                        "tok": e["yes_tok"], "t": _parse_t(e["entry_utc"]), "win": e["won"], "side": "yes"})
    for l in p1["locks"]:
        out.append({"kind": "lock", "city": l["city"], "date": l["date"], "ticker": l["ticker"], "tok": l["tok"],
                    "t": _parse_t(l["lock_utc"]), "win": l["correct"], "side": l["side"]})
    return out


def plan_hours(stage):
    p1 = _cache_get("phase1.json")
    hours = set()
    for f in fires_of(p1):
        if f["t"] < PMXT_COVERAGE_START:
            continue
        hours.add(hstr(f["t"]))
    if stage == "B":
        # continuation hours: only for fires with no ask event at >= t inside t's own hour-file
        ev = load_events(hours_present=True)
        for f in fires_of(p1):
            t, tok = f["t"], f["tok"]
            if t < PMXT_COVERAGE_START:
                continue
            hit = first_ask(ev.get(tok), t, t + dt.timedelta(minutes=ASK_SEARCH_WINDOW_MIN))
            h0 = hstr(t)
            if hit is None and manifest_ok(h0):
                nxt = hstr(t.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1))
                if t + dt.timedelta(minutes=ASK_SEARCH_WINDOW_MIN) > t.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1):
                    hours.add(nxt)
        hours = {h for h in hours if not manifest_exists(h)}
    hl = sorted(hours)
    _cache_put(f"hours_{stage}.json", hl)
    print(f"stage {stage}: {len(hl)} hour-files needed", f"({sum(1 for h in hl if not manifest_exists(h))} not yet mirrored)")
    return hl


def manifest_path(h):
    return os.path.join(PMXT_DIR, f"{h}.manifest.json")


def manifest_exists(h):
    return os.path.exists(manifest_path(h))


def load_manifest(h):
    try:
        return json.load(open(manifest_path(h)))
    except Exception:
        return None


def manifest_ok(h):
    m = load_manifest(h)
    return bool(m) and not m.get("missing")


_PCOLS = ["timestamp_received", "event_type", "asset_id", "best_bid", "best_ask", "bids", "asks"]


def fetch_hour(h, watch):
    """Mirror ONE hour-file: column-projected (timestamp_received,event_type,asset_id,best_bid,best_ask,bids,asks) and
    filtered to the ladder-token watchlist, written as parquet. Every row group is read; a failed row-group read aborts the
    hour (NO manifest) rather than silently dropping rows."""
    import fsspec
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    if manifest_exists(h):
        return
    url = PMXT_TPL.format(h=h)
    # existence check (404 => archive hole, recorded, not an error)
    st_code, size, etag = None, None, None
    for a in range(5):
        try:
            req = urllib.request.Request(url, method="HEAD", headers=_HEADERS)
            r = urllib.request.urlopen(req, timeout=40, context=_CTX)
            st_code, size, etag = r.status, r.headers.get("content-length"), r.headers.get("etag")
            break
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                st_code = e.code
                break
            time.sleep(3 * (a + 1))
        except Exception:
            time.sleep(3 * (a + 1))
    if st_code is None:
        raise RuntimeError(f"HEAD failed (transient) {h}")
    if st_code in (403, 404):
        json.dump({"hour": h, "missing": True, "http": st_code}, open(manifest_path(h), "w"))
        print(f"  {h}: MISSING in archive (HTTP {st_code})", flush=True)
        return
    fs = fsspec.filesystem("https")
    pf0 = pq.ParquetFile(fs.open(url, "rb"))
    n_rg, n_rows = pf0.num_row_groups, pf0.metadata.num_rows
    watch_arr = pa.array(sorted(watch), type=pa.string())

    def rd(i):
        last = None
        for a in range(5):
            try:
                pf = pq.ParquetFile(fs.open(url, "rb"))
                tb = pf.read_row_group(i, columns=_PCOLS, use_threads=False)
                return tb.filter(pc.is_in(tb.column("asset_id"), value_set=watch_arr))
            except Exception as e:  # noqa
                last = e
                time.sleep(2 * (a + 1))
        raise RuntimeError(f"row group {i} of {h} failed: {last}")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=int(os.environ.get("S1_THREADS", "12"))) as ex:
        parts = list(ex.map(rd, range(n_rg)))
    tb = pa.concat_tables(parts)
    idx = pc.sort_indices(tb, sort_keys=[("timestamp_received", "ascending")])
    tb = tb.take(idx)
    outp = os.path.join(PMXT_DIR, f"{h}.parquet")
    pq.write_table(tb, outp + ".tmp", compression="zstd")
    os.replace(outp + ".tmp", outp)
    tsr = tb.column("timestamp_received")
    json.dump({"hour": h, "missing": False, "n_row_groups": n_rg, "n_rows_total": n_rows, "n_rows_kept": tb.num_rows,
               "n_watch": len(watch), "content_length": size, "etag": etag, "elapsed_s": round(time.time() - t0, 1),
               "first_ts": str(tsr[0].as_py()) if tb.num_rows else None,
               "last_ts": str(tsr[-1].as_py()) if tb.num_rows else None,
               "mirror": "column-projected + ladder-token-filtered (see spec_S1.md)"},
              open(manifest_path(h), "w"))
    print(f"  {h}: {n_rows/1e6:.1f}M rows -> kept {tb.num_rows} ({time.time()-t0:.0f}s)", flush=True)


def run_fetch(stage, shard):
    p1 = _cache_get("phase1.json")
    hl = _cache_get(f"hours_{stage}.json")
    i, n = (int(x) for x in shard.split("/"))
    mine = [h for k, h in enumerate(hl) if k % n == i]
    todo = [h for h in mine if not manifest_exists(h)]
    print(f"shard {shard}: {len(todo)} to fetch of {len(mine)}", flush=True)
    fails = 0
    for h in todo:
        try:
            fetch_hour(h, watchlist_for_hour(p1, h))
        except Exception as e:  # noqa
            fails += 1
            print(f"  {h}: FAILED ({e}); will retry on rerun", flush=True)
            time.sleep(5)
    print(f"shard {shard} done, {fails} failures", flush=True)


# ===============================================================================================================
# Pricing + stats
# ===============================================================================================================
def load_events(hours_present=False, only_hours=None):
    """token -> (ts_ms[], ask[], bid[]) arrays over every mirrored hour. Rows without a usable ask are dropped
    (last_trade_price, tick_size_change, empty-ask-side). `book` events: ask = min price in `asks`, bid = max in `bids`."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    per = {}
    for fn in sorted(os.listdir(PMXT_DIR)):
        if not fn.endswith(".parquet"):
            continue
        h = fn[:-8]
        if only_hours is not None and h not in only_hours:
            continue
        tb = pq.read_table(os.path.join(PMXT_DIR, fn))
        if tb.num_rows == 0:
            continue
        ts = pc.cast(tb.column("timestamp_received"), pa.int64()).to_numpy()
        aid = tb.column("asset_id").to_pylist()
        et = tb.column("event_type").to_pylist()
        ba = [None if x is None else float(x) for x in tb.column("best_ask").to_pylist()]
        bb = [None if x is None else float(x) for x in tb.column("best_bid").to_pylist()]
        asks = tb.column("asks").to_pylist()
        bids = tb.column("bids").to_pylist()
        for k in range(len(aid)):
            a, b = ba[k], bb[k]
            if et[k] == "book":
                try:
                    la = json.loads(asks[k]) if asks[k] else []
                    lb = json.loads(bids[k]) if bids[k] else []
                    a = min(float(x[0]) for x in la) if la else None
                    b = max(float(x[0]) for x in lb) if lb else None
                except Exception:
                    a = b = None
            elif et[k] != "price_change":
                continue
            if a is None or not (a > 0):
                continue
            per.setdefault(aid[k], []).append((int(ts[k]), a, b if (b is not None and b > 0) else None))
    out = {}
    for tok, rows in per.items():
        rows.sort(key=lambda r: r[0])
        out[tok] = rows
    return out


def first_ask(rows, t0, t1, tie="high"):
    """First ask-bearing event with t0 <= ts < t1. Ties at the same first ms: primary = upper median of the tied asks
    (row order within a ms is not recoverable from the mirror); 'min'/'max' are reported as bounds. -> dict or None."""
    if not rows:
        return None
    import bisect
    a = int(t0.timestamp() * 1000)
    b = int(t1.timestamp() * 1000)
    keys = [r[0] for r in rows]
    i = bisect.bisect_left(keys, a)
    if i >= len(rows) or rows[i][0] >= b:
        return None
    ts = rows[i][0]
    tied = []
    j = i
    while j < len(rows) and rows[j][0] == ts:
        tied.append(rows[j])
        j += 1
    asks = sorted(r[1] for r in tied)
    pick = {"high": st.median_high(asks), "min": asks[0], "max": asks[-1]}[tie]
    bids = [r[2] for r in tied if r[2] is not None]
    return {"ts_ms": ts, "ask": pick, "ask_min": asks[0], "ask_max": asks[-1], "n_tied": len(tied),
            "bid": (max(bids) if bids else None), "lag_s": (ts - a) / 1000.0}


def fee_c(ask_c):
    p = ask_c / 100.0
    return 100.0 * FEE_RATE * p * (1 - p)


def clustered(values, cl):
    """Cameron-Gelbach-Miller CR1 SE of a mean (constant-only regression); df = G-1."""
    n = len(values)
    if n < 2:
        return None
    m = sum(values) / n
    groups = {}
    for v, c in zip(values, cl):
        groups.setdefault(c, 0.0)
        groups[c] += v - m
    G = len(groups)
    if G < 2:
        return None
    var = (n / (n - 1)) * (G / (G - 1)) * sum(s * s for s in groups.values()) / (n * n)
    se = math.sqrt(var) if var > 0 else None
    return {"mean": m, "se": se, "t": (m / se if se else None), "n": n, "n_clusters": G, "df": G - 1}


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - h) / den), min(1.0, (c + h) / den))


def boot_ci(values, cl, B=4000, seed=7):
    import random
    rnd = random.Random(seed)
    g = {}
    for v, c in zip(values, cl):
        g.setdefault(c, []).append(v)
    keys = list(g)
    sums = {k: (sum(g[k]), len(g[k])) for k in keys}
    ms = []
    for _ in range(B):
        s = n = 0
        for _k in keys:
            a, b = sums[keys[rnd.randrange(len(keys))]]
            s += a
            n += b
        ms.append(s / n)
    ms.sort()
    return ms[int(0.0167 * B)], ms[int(0.5 * B)], ms[int(0.9833 * B)]


def price_all(p1, ev, avail_hours, missing_hours):
    """Price every fire. Status taxonomy (mutually exclusive):
       before_pmxt_coverage | archive_hole (a needed hour-file is missing from the archive and no ask found)
       | not_mirrored (bug guard) | unpriceable_no_ask_in_60min | priced"""
    rows = []
    for f in fires_of(p1):
        t = f["t"]
        rec = {k: f[k] for k in ("kind", "city", "date", "ticker", "tok", "win", "side")}
        rec["t"] = t.isoformat()
        if t < PMXT_COVERAGE_START:
            rec["status"] = "before_pmxt_coverage"
            rows.append(rec)
            continue
        end = t + dt.timedelta(minutes=ASK_SEARCH_WINDOW_MIN)
        hit = first_ask(ev.get(f["tok"]), t, end)
        hours_needed = [hstr(t)]
        top = t.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
        if end > top:
            hours_needed.append(hstr(top))
        if hit is not None:
            rec["status"] = "priced"
            rec["hit"] = hit
        else:
            miss = [h for h in hours_needed if h in missing_hours]
            nm = [h for h in hours_needed if h not in avail_hours and h not in missing_hours]
            rec["status"] = "archive_hole" if miss else ("not_mirrored" if nm else "unpriceable_no_ask_in_60min")
        rows.append(rec)
    return rows


def ev_rows_for(priced_rows, tie="high"):
    out = []
    for r in priced_rows:
        h = r["hit"]
        ask = {"high": h["ask"], "min": h["ask_min"], "max": h["ask_max"]}[tie] * 100.0
        f = fee_c(ask)
        net = (100.0 if r["win"] else 0.0) - ask - f
        bid = h["bid"]
        thin = (bid is None) or (h["ask"] - bid >= 0.10)
        out.append({"kind": r["kind"], "city": r["city"], "date": r["date"], "ticker": r["ticker"], "t": r["t"],
                    "side": r["side"], "ask_c": round(ask, 3), "fee_c": round(f, 4), "won": bool(r["win"]),
                    "net_ev_c": round(net, 4), "lag_s": round(h["lag_s"], 2),
                    "bid_c": None if bid is None else round(bid * 100, 3), "thin_book": bool(thin), "n_tied": h["n_tied"]})
    return out


def summarize(evr, label=""):
    if not evr:
        return {"label": label, "n": 0}
    vals = [x["net_ev_c"] for x in evr]
    cd = clustered(vals, [(x["city"], x["date"]) for x in evr])
    cal = clustered(vals, [x["date"] for x in evr])
    k = sum(1 for x in evr if x["won"])
    s = {"label": label, "n": len(vals), "n_clusters_city_day": cd["n_clusters"] if cd else None,
         "mean_c": sum(vals) / len(vals), "median_c": st.median(vals),
         "win_rate": k / len(vals), "win_rate_wilson95": wilson(k, len(vals)),
         "mean_ask_c": sum(x["ask_c"] for x in evr) / len(evr), "mean_fee_c": sum(x["fee_c"] for x in evr) / len(evr),
         "city_day_clustered": cd, "calendar_date_clustered": cal}
    if cd and cd["se"]:
        s["ucb_98_33_c"] = cd["mean"] + KILL_Z * cd["se"]
        s["lcb_98_33_c"] = cd["mean"] - KILL_Z * cd["se"]
    return s


def run_analyze():
    t0 = time.time()
    p1 = _cache_get("phase1.json")
    if p1 is None:
        sys.exit("run `weather` first")
    from collections import Counter
    avail, missing, mans = set(), set(), {}
    for fn in os.listdir(PMXT_DIR):
        if fn.endswith(".manifest.json"):
            m = json.load(open(os.path.join(PMXT_DIR, fn)))
            mans[m["hour"]] = m
            (missing if m.get("missing") else avail).add(m["hour"])
    print(f"mirror: {len(avail)} hour-files present, {len(missing)} archive holes", flush=True)
    ev = load_events()
    print(f"events loaded for {len(ev)} tokens", flush=True)
    rows = price_all(p1, ev, avail, missing)

    ent = [r for r in rows if r["kind"] == "entry"]
    rawd = [r for r in rows if r["kind"] == "entry_rawdiff"]
    lck = [r for r in rows if r["kind"] == "lock"]
    cnt, cnt_l, cnt_r = (Counter(r["status"] for r in x) for x in (ent, lck, rawd))

    tot = sorted(m["n_rows_total"] for m in mans.values() if not m.get("missing"))
    med_rows = tot[len(tot) // 2] if tot else None
    thin_hours = sorted(h for h, m in mans.items() if not m.get("missing") and med_rows and m["n_rows_total"] < 0.4 * med_rows)

    priced_e = [r for r in ent if r["status"] == "priced"]
    evr = ev_rows_for(priced_e)
    n_unp = cnt.get("unpriceable_no_ask_in_60min", 0)
    n_hole = cnt.get("archive_hole", 0)
    n_notm = cnt.get("not_mirrored", 0)
    n_cov = len(priced_e) + n_unp + n_hole + n_notm          # primary entries inside pmxt coverage
    frac_unp = (n_unp + n_hole) / n_cov if n_cov else None  # archive holes counted AGAINST us (conservative)
    frac_unp_strict = n_unp / n_cov if n_cov else None
    need_h = {hstr(_parse_t(r["t"])) for r in ent if r["status"] != "before_pmxt_coverage"}
    frac_unread = (len([h for h in need_h if h not in avail]) / len(need_h)) if need_h else None

    prim = summarize(evr, "PRIMARY: all priced item-2b entries (4 cities)")
    n_cl = prim.get("n_clusters_city_day", 0) if prim.get("n") else 0
    cd = prim.get("city_day_clustered") or {}
    t_stat, mean_c, ucb = cd.get("t"), prim.get("mean_c"), prim.get("ucb_98_33_c")
    thin = (prim.get("n", 0) < MIN_PRICED) or (n_cl < MIN_CLUSTERS)
    spec_kill = None
    if frac_unread is not None and frac_unread > MAX_UNREADABLE_FRAC:
        spec_kill = f"pmxt.dev missing/unreadable for {frac_unread:.1%} of needed hour-files (> {MAX_UNREADABLE_FRAC:.0%})"
    elif frac_unp is not None and frac_unp > MAX_UNPRICEABLE_FRAC:
        spec_kill = f"{frac_unp:.1%} of in-coverage fires unpriceable (> {MAX_UNPRICEABLE_FRAC:.0%}): EV flagged selection-biased"
    elif n_notm:
        spec_kill = f"{n_notm} fires need hour-files not yet mirrored (run plan B + fetch B)"
    if spec_kill:
        verdict = f"NO-VERDICT (spec infrastructure kill): {spec_kill}"
    elif thin:
        verdict = f"THIN / no-verdict: {prim.get('n', 0)} priced fires, {n_cl} clusters (need >= {MIN_PRICED} and >= {MIN_CLUSTERS})"
    elif ucb is not None and ucb < KILL_UCB_C:
        verdict = (f"KILL -- Polymarket bracket-entry sleeve DEAD at measured prices: mean {mean_c:+.3f}c/ct, "
                   f"98.33% UCB {ucb:+.3f}c < +{KILL_UCB_C}c")
    elif t_stat is not None and t_stat >= PASS_T and mean_c >= PASS_MEAN_C:
        verdict = f"PASS: t={t_stat:.2f} >= {PASS_T} and mean {mean_c:+.3f}c >= +{PASS_MEAN_C}c (geo-blocked: measurement, not deployment)"
    else:
        verdict = f"INCONCLUSIVE-THIN: mean {mean_c:+.3f}c, t={t_stat}, 98.33% UCB {ucb}"

    # ---- non-gating sensitivities (all labelled; none can change the verdict) ----
    sens = {}
    sens["tie_rule_min_ask"] = summarize(ev_rows_for(priced_e, "min"), "tied-ms rows: lowest ask")
    sens["tie_rule_max_ask"] = summarize(ev_rows_for(priced_e, "max"), "tied-ms rows: highest ask")
    sens["ask_within_5min"] = summarize([x for x in evr if x["lag_s"] <= 300], "ask event within 5 min of signal")
    sens["ask_within_60s"] = summarize([x for x in evr if x["lag_s"] <= 60], "ask event within 60 s of signal")
    sens["exclude_thin_book"] = summarize([x for x in evr if not x["thin_book"]], "excl. thin-book (no bid or spread>=10c)")
    sens["only_thin_book"] = summarize([x for x in evr if x["thin_book"]], "thin-book only")
    sens["ask_le_97c"] = summarize([x for x in evr if x["ask_c"] <= 97.0], "ask <= 97c")
    sens["ask_between_3_and_97"] = summarize([x for x in evr if 3.0 < x["ask_c"] < 97.0], "3c < ask < 97c")
    th = set(thin_hours)
    sens["exclude_thin_archive_hours"] = summarize([x for x in evr if hstr(_parse_t(x["t"])) not in th], "excl. thin pmxt hours")
    sens["fee_ignored_diagnostic"] = summarize([dict(x, net_ev_c=x["net_ev_c"] + x["fee_c"]) for x in evr], "fee ignored (diagnostic)")
    sens["ex_chicago"] = summarize([x for x in evr if x["city"] != "chicago"], "excluding Chicago")
    sens["chicago_only"] = summarize([x for x in evr if x["city"] == "chicago"], "Chicago only")
    # reference-harness variant: un-rounded F->C float conversion (entries differ by float noise at integer thresholds)
    raw_keys = {(e["city"], e["date"], e["ticker"], e["entry_utc"]) for e in p1.get("entries_raw", [])}
    var_rows = [r for r in priced_e if (r["city"], r["date"], r["ticker"], r["t"]) in raw_keys or
                (r["city"], r["date"], r["ticker"], _parse_t(r["t"]).isoformat()) in raw_keys]
    var_rows += [r for r in rawd if r["status"] == "priced"]
    sens["reference_harness_unrounded_float_variant"] = summarize(ev_rows_for(var_rows), "un-rounded conversion (reference harness literal)")
    by_city = {c: summarize([x for x in evr if x["city"] == c], c) for c in CITIES}
    by_bucket = {f"{a}-{b}c": summarize([x for x in evr if a <= x["ask_c"] < b], f"ask {a}-{b}c")
                 for a, b in [(0, 10), (10, 30), (30, 60), (60, 90), (90, 101)]}
    # +5 min publication-latency sensitivity (signal timestamp shifted)
    lat = []
    for r in ent:
        if r["status"] == "before_pmxt_coverage":
            continue
        t = _parse_t(r["t"]) + dt.timedelta(minutes=5)
        hit = first_ask(ev.get(r["tok"]), t, t + dt.timedelta(minutes=ASK_SEARCH_WINDOW_MIN))
        if hit is not None:
            lat.append(dict(r, hit=hit))
    sens["signal_plus_5min_latency"] = summarize(ev_rows_for(lat), "signal timestamp + 5 min")

    # ---- item-2a locks: non-gating table; YES locks on the YES token, NO locks on the NO token ----
    lock_ev = ev_rows_for([r for r in lck if r["status"] == "priced"])
    lock_tab = {"n_locks": len(lck), "status_counts": dict(cnt_l),
                "all": summarize(lock_ev, "item-2a locks (non-gating)"),
                "yes_side": summarize([x for x in lock_ev if x["side"] == "yes"], "YES locks"),
                "no_side": summarize([x for x in lock_ev if x["side"] == "no"], "NO locks")}

    days = p1["days"]
    cov = {c: {"usable_days": sum(1 for d in days if d["city"] == c),
               "days_winner_never_entered": sum(1 for d in days if d["city"] == c and d["winner_never_entered"]),
               "n_entries": sum(d["n_entries"] for d in days if d["city"] == c),
               "n_entries_winner": sum(1 for e in p1["entries"] if e["city"] == c and e["won"])} for c in CITIES}
    skip_ct = Counter(f"{s['city']}|{s['reason'] if not s['reason'].startswith('thin_station') else 'thin_station_data_0obs'}" for s in p1["skips"])

    out = {
        "spec_id": "S1", "run_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "elapsed_s": round(time.time() - t0, 1),
        "window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()], "cities": list(CITIES),
        "frozen_bar": {"pass": f"cluster-t >= {PASS_T} AND mean net EV >= +{PASS_MEAN_C}c/ct",
                       "kill": f"one-sided 98.33% UCB (z={KILL_Z}) of mean net EV < +{KILL_UCB_C}c/ct",
                       "min_n": f">= {MIN_PRICED} priced fires AND >= {MIN_CLUSTERS} city-day clusters",
                       "spec_kills": f"> {MAX_UNPRICEABLE_FRAC:.0%} unpriceable OR > {MAX_UNREADABLE_FRAC:.0%} hour-files unreadable"},
        "verdict": verdict,
        "geo_block_disclosure": "Global Polymarket is geo-blocked to US persons: even a PASS is a measurement, not a deployment, for this operator.",
        "primary": prim,
        "gates": {"t_stat": t_stat, "mean_c": mean_c, "ucb_98_33_c": ucb, "n_priced": prim.get("n", 0), "n_clusters": n_cl,
                  "pass_t": bool(t_stat is not None and t_stat >= PASS_T), "pass_mean": bool(mean_c is not None and mean_c >= PASS_MEAN_C),
                  "kill_triggered": bool(ucb is not None and ucb < KILL_UCB_C), "thin": thin, "spec_kill": spec_kill},
        "primary_cluster_bootstrap_98_33_lo_med_hi_c": (boot_ci([x["net_ev_c"] for x in evr], [(x["city"], x["date"]) for x in evr]) if evr else None),
        "fire_accounting": {"entries_total": len(ent), "status_counts": dict(cnt), "entries_in_pmxt_coverage": n_cov,
                            "unpriceable": n_unp, "archive_hole": n_hole, "frac_unpriceable_incl_holes": frac_unp,
                            "frac_unpriceable_strict": frac_unp_strict, "thin_book_priced": sum(1 for x in evr if x["thin_book"]),
                            "thin_archive_hours": thin_hours, "median_hour_rows": med_rows,
                            "needed_hour_files": len(need_h), "unreadable_or_missing_frac": frac_unread,
                            "rawdiff_status_counts": dict(cnt_r)},
        "hour_files": {"mirrored": len(avail), "archive_holes": sorted(missing)},
        "sensitivities_nongating": sens, "by_city": by_city, "by_ask_bucket": by_bucket, "locks_item_2a_nongating": lock_tab,
        "signal_coverage": cov, "usable_city_days": len(days), "skipped_city_days": len(p1["skips"]),
        "skips": p1["skips"], "skip_summary": dict(skip_ct),
        "n_entries_changed_by_float_rounding": sum(d["n_entries_changed_by_rounding"] for d in days),
        "ev_rows": evr,
    }
    json.dump(out, open(os.path.join(OUT_DIR, "spec_S1_results.json"), "w"), indent=1, default=str)
    print("\nVERDICT:", verdict)
    print(f"  priced={prim.get('n')} clusters={n_cl} mean={mean_c} t={t_stat} ucb98={ucb}")
    print(f"  fire status: {dict(cnt)}")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "weather":
        run_weather()
    elif a[0] == "plan":
        plan_hours(a[1] if len(a) > 1 else "A")
    elif a[0] == "fetch":
        run_fetch(a[1], a[2])
    elif a[0] == "analyze":
        run_analyze()
    else:
        sys.exit(__doc__)
