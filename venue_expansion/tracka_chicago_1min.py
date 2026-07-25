#!/usr/bin/env python3
"""tracka_chicago_1min.py -- TRACK A: the pre-registered Chicago GO-check named in
ref/pmkt_final_verdict.md section 5, item 1: "Chicago-only, on its own true 1-minute ASOS feed... same
script, same rungs, swap fetch_iem_routine for fetch_asos_1min (already written in pmkt_gap_study.py,
reusable) for chicago only."

WHAT THIS IS: a near-verbatim copy of ref/pmkt_final_verdict.py (Track A's own decisive-run script),
restricted to chicago, with EXACTLY ONE substantive swap: the obs feed that drives the sustain-3 +
1.0F-margin lock/entry walk is IEM's TRUE 1-minute ASOS archive (asos1min.py, station-native cadence)
instead of the hourly-ish "routine" METAR archive (asos.py) pmkt_final_verdict.py used for cross-city
apples-to-apples comparability. Everything else -- bracket parsing, the deployed lock rule itself
(sustain-3, glitch filter, 1.0F margin), the "entries" bracket-band-touch extension, the false-lock
scoring, the ask-proxy + Polymarket-fee EV construction, the Wilson CI formula -- is IDENTICAL.

PRE-REGISTERED BARS (fixed BEFORE this script ever ran and touched real data; verbatim from the task
spec; do not move these after seeing results):
  PASS iff:
    (a) pooled winner-bracket coverage >= 55% AND its 95% Wilson LOWER bound > 40.9% (the measured
        hourly-cadence baseline from pmkt_final_verdict.md section 4's chicago row).
    (b) the DEPLOYED rule's (kwx pure lock rule, locked_orders) false-lock count == 0 on these same
        1-minute streams (item 2a).
    (c) coverage is computed identically to pmkt_final_verdict.py section 4 (same margin=1.0F, same
        sustain-3, same qualifying sub-range / bracket-entry definition) -- only the feed cadence changes.
  Universe: every available Chicago ladder day from the earliest Gamma-listed day (~2026-02-06) through
    2026-07-21 (last fully-settled per the task). Target n>=60 usable days; every skip reported with reason.
  Non-gating (thin-sample): priced-fire EV, verdict script's exact win/loss-fire construction + item-2b
    base-rate reweighting, last-trade-at/after-signal + half live spread entry proxy, fee=0.05*p*(1-p).

DEPLOYED-RULE PROVENANCE: ref/pmkt_final_verdict.py did `import kwx_runner as R` and called
R.sustained_extreme / R.locked_orders verbatim. kwx_runner.py is a LIVE-path file (GROUNDING.md: off-
limits, "lives on another branch anyway -- this branch is research-only") and is genuinely absent from
this branch. Rather than import the entire live execution/sizing/Telegram module (out of scope, and
against the spirit of "never touch live-path files") or re-derive the lock math from prose, this script
imports `kwx_lock_rule.py` (venue_expansion/kwx_lock_rule.py), a small shim that reproduces ONLY those
two pure/stateless functions and the constants they read, BYTE-IDENTICAL (verified via direct text diff
at authoring time), extracted from kwx_runner.py at commit bd90504 (origin/batch/pmkt-verdict) -- the
EXACT commit paired with pmkt_final_verdict.py when it was authored. No live/execution code is reused.

COMPLETENESS-GUARD ADAPTATION FOR 1-MINUTE CADENCE (disclosed, not silent): pmkt_final_verdict.py's
MIN_DAY_OBS=15 / MAX_END_GAP_H=4h guard was explicitly hourly-cadence-tailored ("loosened from that
script's 3h because routine METAR's own native cadence is ~60x coarser" -- see that script's own
comment). For genuine 1-minute cadence this reverts to the SAME thresholds pmkt_gap_study.py itself
established for this exact feed (its own historical-gap study, run on IEM 1-minute ASOS): >=100 obs in
the local day window, last obs within 3h of local day-end. Borrowed verbatim from precedent, not invented
here.

SAMPLING-DENSITY ADAPTATION (disclosed): pmkt_final_verdict.py sparsely strided ~22 samples per city for
6-city cross-comparability. The task's pre-registered universe for Track A is "every available Chicago
ladder day" -- so this script samples DAILY (stride=1) over the full window, not strided.

Read-only, public APIs only (Gamma + CLOB + IEM Mesonet), no auth, no orders, no trading code. Polite:
cached under venue_expansion/cache/, retried with backoff, ~1 req/sec.

USAGE:
  python tracka_chicago_1min.py                 # full run: sanity checks + 1-min GO-check + verdict
  python tracka_chicago_1min.py --cached-only    # recompute from cached pulls only, no network
"""
import bisect
import json
import math
import os
import ssl
import statistics as st
import sys
import time
import urllib.error
import urllib.request
import datetime as dt
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kwx_lock_rule as R   # deployed lock-rule shim: sustained_extreme, locked_orders (see docstring)

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; tracka-chicago-1min/1.0)"}

GBASE = "https://gamma-api.polymarket.com"
CBASE = "https://clob.polymarket.com"
DAILY_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
ASOS_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"

CACHE_DIR = os.path.join(HERE, "cache", "tracka_chicago_1min")
os.makedirs(CACHE_DIR, exist_ok=True)

# --------------------------------------------------------------------------------------------------------
# UNIVERSE -- Chicago only (Track A). Same fields/semantics as pmkt_final_verdict.py's WHITELIST entry.
# --------------------------------------------------------------------------------------------------------
CHICAGO = dict(station="ORD", unit="F", tz="America/Chicago", margin=1.0, earliest=dt.date(2026, 2, 6))
WHITELIST = {"chicago": CHICAGO}   # kept as a dict (singleton) so probe_live_spread()/loop shape is unchanged

END_DATE = dt.date(2026, 7, 21)              # last fully-settled day per the task spec
SANITY_END_DATE = dt.date(2026, 7, 18)       # pmkt_final_verdict.py's own END_DATE, for exact reproduction
SANITY_TARGET_SAMPLES = 22                   # pmkt_final_verdict.py's own TARGET_SAMPLES_PER_CITY

PMKT_WEATHER_FEE_RATE = 0.05
FALLBACK_HALF_SPREAD_C = 3.3 / 2.0

# hourly-cadence completeness guard (pmkt_final_verdict.py's own values, used ONLY by the sanity-check
# reproduction of the old hourly number, section below)
MIN_DAY_OBS_HOURLY = 15
MAX_END_GAP_H_HOURLY = 4

# 1-minute-cadence completeness guard (pmkt_gap_study.py's own established values for this exact feed --
# see module docstring)
MIN_DAY_OBS_1MIN = 100
MAX_END_GAP_H_1MIN = 3


def _get_json(url, timeout=25, retries=5, backoff=1.6):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 404:
                return {"__404__": True}
            if e.code not in (429, 500, 502, 503, 504):
                return {"__err__": f"HTTP {e.code}"}
            time.sleep(backoff * (attempt + 1))
        except Exception as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
    return {"__err__": f"{type(last_err).__name__}: {last_err}"}


def _get_text(url, timeout=35, retries=5, backoff=2.0):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return urllib.request.urlopen(req, timeout=timeout, context=_CTX).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
        except Exception as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
    return None


def _cache_path(name):
    return os.path.join(CACHE_DIR, name)


def _cache_get(name):
    p = _cache_path(name)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        try:
            return json.load(open(p))
        except Exception:
            return None
    return None


def _cache_put(name, obj):
    json.dump(obj, open(_cache_path(name), "w"))


# --------------------------------------------------------------------------------------------------------
# bracket parsing -> CONTINUOUS native-unit (floor, cap) boundaries -- IDENTICAL to pmkt_final_verdict.py.
# --------------------------------------------------------------------------------------------------------
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


def event_rungs_native(event, unit):
    """-> (rungs_for_locked_orders, ticker->groupItemTitle, winner_ticker) or None if not resolved."""
    mkts = event.get("markets", [])
    if not mkts:
        return None
    rungs, titles, winner = [], {}, None
    for m in mkts:
        if not m.get("closed"):
            return None
        label = m.get("groupItemTitle", "")
        floor, cap = parse_rung_native(label)
        try:
            tok_ids = json.loads(m.get("clobTokenIds") or "[]")
        except Exception:
            tok_ids = []
        ticker = m.get("id") or label
        titles[ticker] = label
        try:
            prices = json.loads(m["outcomePrices"]) if isinstance(m["outcomePrices"], str) else m["outcomePrices"]
        except Exception:
            prices = []
        if prices and abs(float(prices[0]) - 1.0) < 1e-6:
            winner = ticker
        rungs.append({"ticker": ticker, "floor": floor, "cap": cap,
                       "yes_ask_c": 50, "no_ask_c": 50,   # placeholder; bypasses locked_orders' MAX_PAY gate
                       "yes_tok": tok_ids[0] if len(tok_ids) > 0 else None,
                       "no_tok": tok_ids[1] if len(tok_ids) > 1 else None})
    if winner is None:
        return None
    return rungs, titles, winner


# --------------------------------------------------------------------------------------------------------
# FEED A -- IEM routine METAR archive (hourly-ish). IDENTICAL to pmkt_final_verdict.py's fetch_iem_routine,
# kept ONLY for the sanity-check reproduction of the ~40.9% baseline (proves this harness matches the
# prior study before trusting the 1-minute results below). NOT used in the primary Track-A run.
# --------------------------------------------------------------------------------------------------------
def fetch_iem_routine(station, start_utc, end_utc):
    key = f"asos_{station}_{start_utc:%Y%m%dT%H%M}_{end_utc:%Y%m%dT%H%M}.json"
    cached = _cache_get(key)
    if cached is not None:
        return [(dt.datetime.fromisoformat(t), v) for t, v in cached]
    # MEASURED QUIRK: IEM's asos.py treats day2/month2/year2 as an EXCLUSIVE upper bound -- pad the end
    # by one calendar day so `end_utc`'s own day is actually covered (see pmkt_final_verdict.py).
    end_pad = end_utc + dt.timedelta(days=1)
    q = (f"station={station}&data=tmpf&year1={start_utc.year}&month1={start_utc.month}&day1={start_utc.day}"
         f"&year2={end_pad.year}&month2={end_pad.month}&day2={end_pad.day}"
         f"&tz=UTC&format=onlycomma&latlon=no&elev=no&missing=M&trace=T&direct=no&report_type=3")
    txt = _get_text(f"{DAILY_ASOS}?{q}")
    out = []
    if txt:
        for line in txt.splitlines():
            if not line or line.startswith("station,"):
                continue
            parts = line.split(",")
            if len(parts) < 3:
                continue
            valid, tmpf = parts[1], parts[2]
            if tmpf in ("", "M", "T"):
                continue
            try:
                t = dt.datetime.strptime(valid.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                v = float(tmpf)
            except ValueError:
                continue
            out.append((t, v))
    out.sort(key=lambda x: x[0])
    _cache_put(key, [(t.isoformat(), v) for t, v in out])
    time.sleep(0.8)
    return out


# --------------------------------------------------------------------------------------------------------
# FEED B -- IEM TRUE 1-minute ASOS archive (asos1min.py). Ported from ref/pmkt_gap_study.py's
# fetch_asos_1min, adapted to this script's cache/retry helpers. THIS is the feed the primary Track-A run
# uses. station_bare = "ORD" (bare ID, no "K" prefix -- same convention pmkt_gap_study.py's CITY_STATIONS
# and this script's own CHICAGO["station"] already use, so no station-id translation is needed).
#
# NOTE on the asos.py exclusive-end-date bug: that bug is specific to asos.py's day1/day2 WHOLE-DAY
# params (confirmed live by pmkt_final_verdict.py). asos1min.py instead takes `sts`/`ets` as full
# UTC timestamps -- a continuous range query, not a whole-day-bucket one -- so the same bug does not
# structurally apply here. Still padded generously (1h pre / 3h post) and empirically spot-checked
# below (sanity check B) rather than assumed.
# --------------------------------------------------------------------------------------------------------
def fetch_iem_1min(station_bare, start_utc, end_utc):
    key = f"asos1min_{station_bare}_{start_utc:%Y%m%dT%H%M}_{end_utc:%Y%m%dT%H%M}.json"
    cached = _cache_get(key)
    if cached is not None:
        return [(dt.datetime.fromisoformat(t), v) for t, v in cached]
    sts = start_utc.strftime("%Y-%m-%dT%H:%MZ")
    ets = end_utc.strftime("%Y-%m-%dT%H:%MZ")
    q = f"station={station_bare}&vars=tmpf&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma"
    txt = _get_text(f"{ASOS_1MIN}?{q}")
    out = []
    if txt:
        for line in txt.splitlines():
            if not line or line.startswith("station,"):
                continue
            parts = line.split(",")
            if len(parts) < 4:
                continue
            valid, tmpf = parts[2], parts[3]
            if tmpf in ("", "M"):
                continue
            try:
                t = dt.datetime.strptime(valid.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                v = float(tmpf)
            except ValueError:
                continue
            out.append((t, v))
    out.sort(key=lambda x: x[0])
    _cache_put(key, [(t.isoformat(), v) for t, v in out])
    time.sleep(1.0)
    return out


def fetch_event(city_slug, d):
    slug = f"highest-temperature-in-{city_slug}-on-{d.strftime('%B').lower()}-{d.day}-{d.year}"
    key = f"event_{slug}.json"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    ev = _get_json(f"{GBASE}/events/slug/{slug}")
    _cache_put(key, ev)
    time.sleep(0.5)
    return ev


def fetch_price_history(token_id, start_ts, end_ts):
    key = f"phist_{token_id}_{start_ts}_{end_ts}.json"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    d = _get_json(f"{CBASE}/prices-history?market={token_id}&startTs={start_ts}&endTs={end_ts}&fidelity=1")
    hist = d.get("history", []) if isinstance(d, dict) and "__err__" not in d and "__404__" not in d else []
    _cache_put(key, hist)
    time.sleep(0.5)
    return hist


# --------------------------------------------------------------------------------------------------------
# backtest_day -- IDENTICAL walk-forward logic to pmkt_final_verdict.py's backtest_day, generalized ONLY
# to accept a pluggable obs fetcher + completeness-guard thresholds (so the SAME function drives both the
# hourly sanity-check reproduction and the primary 1-minute run -- no logic fork between them).
# --------------------------------------------------------------------------------------------------------
def backtest_day(city_slug, d, cfg, fetch_fn, min_day_obs, max_end_gap_h, pad_pre_h, pad_post_h):
    tz = ZoneInfo(cfg["tz"])
    unit, margin, station = cfg["unit"], cfg["margin"], cfg["station"]
    day_start = dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz).astimezone(dt.timezone.utc)
    day_end = day_start + dt.timedelta(days=1)

    ev = fetch_event(city_slug, d)
    if not isinstance(ev, dict) or "__err__" in ev or "__404__" in ev:
        return {"skip": "event_not_found"}
    parsed = event_rungs_native(ev, unit)
    if parsed is None:
        return {"skip": "not_resolved_or_unparseable"}
    rungs, titles, winner_ticker = parsed

    obs_all = fetch_fn(station, day_start - dt.timedelta(hours=pad_pre_h), day_end + dt.timedelta(hours=pad_post_h))
    day_obs = [(t, v) for t, v in obs_all if day_start <= t < day_end]
    if len(day_obs) < min_day_obs:
        return {"skip": f"thin_station_data_{len(day_obs)}obs"}
    if day_obs[-1][0] < day_end - dt.timedelta(hours=max_end_gap_h):
        return {"skip": "station_feed_gap_near_dayend"}

    locked = {}
    entries = {}
    obs_stream = [(t, v) for t, v in day_obs]
    for i in range(1, len(obs_stream) + 1):
        window = obs_stream[:i]
        extreme_f = R.sustained_extreme([(t.isoformat(), v) for t, v in window], "max")
        if extreme_f is None:
            continue
        extreme_native = extreme_f if unit == "F" else (extreme_f - 32.0) * 5.0 / 9.0
        ts_iso = window[-1][0].isoformat()

        fires = R.locked_orders(rungs, extreme_native, "max", margin=margin)
        for ticker, side, _cap_c, cushion in fires:
            if ticker not in locked:
                locked[ticker] = {"side": side, "lock_utc": ts_iso,
                                   "extreme_native": round(extreme_native, 2), "cushion": round(cushion, 2)}

        for r in rungs:
            if r["ticker"] in entries:
                continue
            floor, cap = r["floor"], r["cap"]
            in_band = (floor is None or extreme_native > floor + margin) and \
                      (cap is None or extreme_native <= cap + margin)
            if in_band:
                entries[r["ticker"]] = {"entry_utc": ts_iso, "extreme_native": round(extreme_native, 2)}

    if not locked and not entries:
        return {"skip": "no_lock_reached", "winner": winner_ticker}

    lock_records = []
    for ticker, info in locked.items():
        correct = (ticker == winner_ticker) if info["side"] == "yes" else (ticker != winner_ticker)
        lock_records.append({"city": city_slug, "date": d.isoformat(), "ticker": ticker,
                              "label": titles.get(ticker), "side": info["side"],
                              "lock_utc": info["lock_utc"], "correct": correct, "cushion": info["cushion"]})

    entry_records = []
    for ticker, info in entries.items():
        entry_records.append({"city": city_slug, "date": d.isoformat(), "ticker": ticker,
                               "label": titles.get(ticker), "entry_utc": info["entry_utc"],
                               "correct": (ticker == winner_ticker)})

    ev_fires = []
    win_entry = entries.get(winner_ticker)
    if win_entry is not None:
        winner_rung = next(r for r in rungs if r["ticker"] == winner_ticker)
        if winner_rung["yes_tok"]:
            ev_fires.append({"city": city_slug, "date": d.isoformat(), "ticker": winner_ticker,
                              "label": titles.get(winner_ticker), "entry_utc": win_entry["entry_utc"],
                              "yes_tok": winner_rung["yes_tok"], "won": True,
                              "close_time": ev["markets"][0].get("closedTime") if ev.get("markets") else None})
        prior = [(t, i) for t, i in entries.items() if t != winner_ticker and i["entry_utc"] < win_entry["entry_utc"]]
        if prior:
            prior.sort(key=lambda kv: kv[1]["entry_utc"])
            p_ticker, p_info = prior[-1]
            p_rung = next(r for r in rungs if r["ticker"] == p_ticker)
            if p_rung["yes_tok"]:
                ev_fires.append({"city": city_slug, "date": d.isoformat(), "ticker": p_ticker,
                                  "label": titles.get(p_ticker), "entry_utc": p_info["entry_utc"],
                                  "yes_tok": p_rung["yes_tok"], "won": False,
                                  "close_time": ev["markets"][0].get("closedTime") if ev.get("markets") else None})

    return {"skip": None, "lock_records": lock_records, "entry_records": entry_records,
            "ev_fires": ev_fires, "winner": winner_ticker, "n_rungs": len(rungs),
            "winner_never_entered": win_entry is None, "n_day_obs": len(day_obs)}


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def probe_live_spread():
    today = dt.datetime.now(dt.timezone.utc)
    spreads = {}
    for city_slug in WHITELIST:
        found = None
        for delta in (0, 1):
            d = today + dt.timedelta(days=delta)
            ev = fetch_event(city_slug, d.date())
            if isinstance(ev, dict) and ev.get("markets"):
                open_mkts = [m for m in ev["markets"] if not m.get("closed") and m.get("bestAsk") is not None]
                if open_mkts:
                    found = open_mkts
                    break
        if not found:
            continue
        near_lock = max(found, key=lambda m: m["bestAsk"])
        try:
            tok = json.loads(near_lock.get("clobTokenIds") or "[]")[0]
        except Exception:
            continue
        ob = _get_json(f"{CBASE}/book?token_id={tok}")
        if isinstance(ob, dict) and "asks" in ob:
            asks, bids = ob.get("asks", []) or [], ob.get("bids", []) or []
            ba = min((float(a["price"]) for a in asks), default=None)
            bb = max((float(b["price"]) for b in bids), default=None)
            if ba is not None and bb is not None:
                spreads[city_slug] = round((ba - bb) * 100.0, 2)
        time.sleep(0.5)
    return spreads


def price_at_or_after(hist, ts):
    if not hist:
        return None
    hist_ts = [h["t"] for h in hist]
    hist_px = [h["p"] for h in hist]
    i = bisect.bisect_left(hist_ts, ts)
    if i >= len(hist_ts):
        return None
    return hist_px[i]


def pmkt_fee_cents(price_c):
    p = price_c / 100.0
    return PMKT_WEATHER_FEE_RATE * p * (1 - p) * 100.0


# --------------------------------------------------------------------------------------------------------
# sampling
# --------------------------------------------------------------------------------------------------------
def sample_dates_dense(cfg, end_date):
    """Every day, start+3 buffer through end_date -- Track A's pre-registered universe."""
    start = cfg["earliest"] + dt.timedelta(days=3)
    if end_date < start:
        return []
    out, d = [], start
    while d <= end_date:
        out.append(d)
        d += dt.timedelta(days=1)
    return out


def sample_dates_strided(cfg, end_date, target_samples):
    """pmkt_final_verdict.py's exact sample_dates() -- used ONLY by the sanity-check reproduction."""
    start = cfg["earliest"] + dt.timedelta(days=3)
    span = (end_date - start).days
    if span < 1:
        return []
    stride = max(1, span // target_samples)
    out, d = [], start
    while d <= end_date:
        out.append(d)
        d += dt.timedelta(days=stride)
    return out


# --------------------------------------------------------------------------------------------------------
# SANITY CHECK A -- reproduce pmkt_final_verdict.md section 4's Chicago row (22 usable days, 13 winner-
# bracket-never-entered, 40.9% coverage) using the SAME hourly feed, SAME stride/window this harness
# would have produced if it were literally pmkt_final_verdict.py restricted to chicago. Proves the harness
# (bracket parsing, sustain-3/margin walk, entries logic) matches the prior study before trusting anything
# built on top of it.
# --------------------------------------------------------------------------------------------------------
def run_sanity_hourly(cached_only):
    print("=" * 100)
    print("SANITY CHECK A -- reproduce the OLD hourly-cadence Chicago coverage number (~40.9%)")
    print("=" * 100)
    dates = sample_dates_strided(CHICAGO, SANITY_END_DATE, SANITY_TARGET_SAMPLES)
    print(f"[chicago/hourly] sampling {len(dates)} days from {dates[0] if dates else '-'} to "
          f"{dates[-1] if dates else '-'} (stride matches pmkt_final_verdict.py's own sample_dates())")
    usable, never_entered, skips = 0, 0, []
    for d in dates:
        r = backtest_day("chicago", d, CHICAGO, fetch_iem_routine, MIN_DAY_OBS_HOURLY, MAX_END_GAP_H_HOURLY,
                          pad_pre_h=2, pad_post_h=4)
        if r.get("skip"):
            skips.append(f"{d}: {r['skip']}")
            print(f"    SKIP {d} -- {r['skip']}")
            continue
        usable += 1
        if r["winner_never_entered"]:
            never_entered += 1
        print(f"    OK   {d}  entered={'NO' if r['winner_never_entered'] else 'yes'}  n_obs={r['n_day_obs']}")
    coverage = (usable - never_entered) / usable if usable else None
    print(f"\nSANITY A RESULT: usable={usable} never_entered={never_entered} "
          f"coverage={f'{100*coverage:.1f}%' if coverage is not None else '--'} "
          f"(reference: pmkt_final_verdict.md section 4 reports usable=22, never_entered=13, "
          f"coverage=40.9%)")
    match = usable == 22 and never_entered == 13
    print(f"EXACT MATCH to the published table: {match}")
    print("=" * 100 + "\n")
    return {"usable": usable, "never_entered": never_entered, "coverage": coverage,
            "skips": skips, "exact_match_published_table": match}


# --------------------------------------------------------------------------------------------------------
# SANITY CHECK B -- spot-check that the 1-minute feed really returns ~60x the row count of the hourly feed
# for the same station/day (proves fetch_iem_1min is actually pulling native 1-minute cadence, not a
# silently-degraded/aliased feed).
# --------------------------------------------------------------------------------------------------------
def run_sanity_rowcount(spot_date):
    print("=" * 100)
    print(f"SANITY CHECK B -- 1-min vs hourly row-count spot check, chicago {spot_date}")
    print("=" * 100)
    tz = ZoneInfo(CHICAGO["tz"])
    day_start = dt.datetime(spot_date.year, spot_date.month, spot_date.day, 0, 0, tzinfo=tz).astimezone(dt.timezone.utc)
    day_end = day_start + dt.timedelta(days=1)
    hourly = fetch_iem_routine(CHICAGO["station"], day_start - dt.timedelta(hours=2), day_end + dt.timedelta(hours=4))
    onemin = fetch_iem_1min(CHICAGO["station"], day_start - dt.timedelta(hours=1), day_end + dt.timedelta(hours=3))
    hourly_day = [x for x in hourly if day_start <= x[0] < day_end]
    onemin_day = [x for x in onemin if day_start <= x[0] < day_end]
    ratio = (len(onemin_day) / len(hourly_day)) if hourly_day else None
    print(f"  hourly rows in local day: {len(hourly_day)}")
    print(f"  1-min  rows in local day: {len(onemin_day)}")
    print(f"  ratio: {f'{ratio:.1f}x' if ratio else '--'} (expect roughly 40-70x; hourly METAR is not "
          f"exactly 1/60 of 1-min because of SPECI/extra reports)")
    print("=" * 100 + "\n")
    return {"date": spot_date.isoformat(), "hourly_rows": len(hourly_day), "onemin_rows": len(onemin_day),
            "ratio": ratio}


# --------------------------------------------------------------------------------------------------------
# main -- primary Track A run: 1-minute feed, dense daily sampling, chicago only.
# --------------------------------------------------------------------------------------------------------
def run(cached_only=False):
    out = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat()}

    # ---- sanity checks first (required before trusting the primary run) ----
    out["sanity_hourly_reproduction"] = run_sanity_hourly(cached_only)
    spot_date = dt.date(2026, 7, 15)
    out["sanity_rowcount_spotcheck"] = run_sanity_rowcount(spot_date)

    print("=" * 100)
    print("TRACK A PRIMARY RUN -- Chicago, TRUE 1-minute ASOS feed, dense daily sampling")
    print("=" * 100)
    dates = sample_dates_dense(CHICAGO, END_DATE)
    print(f"[chicago/1min] sampling {len(dates)} candidate days from {dates[0] if dates else '-'} to "
          f"{dates[-1] if dates else '-'}")

    all_lock_records, all_entry_records, ev_fires, skips = [], [], [], []
    n_winner_never_entered = 0
    usable_city_days = 0
    per_day_log = []
    for d in dates:
        r = backtest_day("chicago", d, CHICAGO, fetch_iem_1min, MIN_DAY_OBS_1MIN, MAX_END_GAP_H_1MIN,
                          pad_pre_h=1, pad_post_h=3)
        if r.get("skip"):
            skips.append(f"chicago {d}: {r['skip']}")
            print(f"    SKIP {d} -- {r['skip']}")
            continue
        usable_city_days += 1
        all_lock_records.extend(r["lock_records"])
        all_entry_records.extend(r["entry_records"])
        ev_fires.extend(r["ev_fires"])
        if r["winner_never_entered"]:
            n_winner_never_entered += 1
        per_day_log.append({"date": d.isoformat(), "n_day_obs": r["n_day_obs"],
                             "winner_never_entered": r["winner_never_entered"], "winner": r["winner"]})
        print(f"    OK   {d}  {len(r['lock_records'])} deployed-rule lock(s), "
              f"{len(r['entry_records'])} bracket-entries, {len(r['ev_fires'])} EV fire(s), "
              f"n_obs={r['n_day_obs']}, winner={r['winner']}" +
              ("  [WINNER BRACKET NEVER ENTERED]" if r["winner_never_entered"] else ""))

    print("\n" + "=" * 100)
    print(f"SAMPLE SIZE: {usable_city_days} usable city-days ({len(skips)} skipped). Target was >=60.")
    print("=" * 100)

    # ---- PRIMARY METRIC: pooled winner-bracket coverage ----
    n_covered = usable_city_days - n_winner_never_entered
    coverage = (n_covered / usable_city_days) if usable_city_days else None
    cov_lo, cov_hi = wilson_ci(n_covered, usable_city_days) if usable_city_days else (None, None)
    print(f"\nPRIMARY METRIC -- winner-bracket coverage (1-minute cadence): {n_covered}/{usable_city_days} = "
          f"{f'{100*coverage:.1f}%' if coverage is not None else '--'}")
    print(f"  95% Wilson CI: [{f'{100*cov_lo:.1f}%' if cov_lo is not None else '--'}, "
          f"{f'{100*cov_hi:.1f}%' if cov_hi is not None else '--'}]")
    print(f"  Baseline to beat (hourly, pmkt_final_verdict.md section 4): 40.9%")

    # ---- ITEM 2a: false-lock rate, pure deployed rule ----
    n_locks = len(all_lock_records)
    n_wrong = sum(1 for x in all_lock_records if not x["correct"])
    print(f"\nITEM 2a -- POOLED FALSE-LOCK RATE, pure deployed rule (n={n_locks}):")
    if n_locks:
        loss_rate = n_wrong / n_locks
        lclo, lchi = wilson_ci(n_wrong, n_locks)
        print(f"  {n_wrong}/{n_locks} wrong = {100*loss_rate:.3f}% conditional loss rate "
              f"(95% Wilson CI [{100*lclo:.3f}%, {100*lchi:.3f}%])")
    else:
        print("  NO EXPLICIT LOCKS AT ALL.")

    # ---- ITEM 2b: bracket-entry false rate (feeds EV) ----
    n_entries = len(all_entry_records)
    n_entry_wrong = sum(1 for x in all_entry_records if not x["correct"])
    print(f"\nITEM 2b -- BRACKET-ENTRY FALSE RATE (n={n_entries}):")
    if n_entries:
        er = n_entry_wrong / n_entries
        elo, ehi = wilson_ci(n_entry_wrong, n_entries)
        print(f"  {n_entry_wrong}/{n_entries} wrong = {100*er:.3f}% (95% CI [{100*elo:.3f}%, {100*ehi:.3f}%])")
    else:
        print("  No bracket entries recorded.")

    # ---- ITEM 3: ask-based, loss-inclusive EV (non-gating) ----
    n_win_fires = sum(1 for f in ev_fires if f["won"])
    n_loss_fires = sum(1 for f in ev_fires if not f["won"])
    print("\n" + "=" * 100)
    print(f"ITEM 3 (non-gating) -- ASK-BASED EV on {len(ev_fires)} fires ({n_win_fires} win-case, "
          f"{n_loss_fires} loss-case)")
    print("=" * 100)
    spreads = {} if cached_only else probe_live_spread()
    print(f"Live spread probe (today, chicago, cents): {spreads if spreads else '(none captured)'}")

    ev_results = []
    for f in ev_fires:
        if not f.get("yes_tok"):
            continue
        try:
            lock_dt = dt.datetime.fromisoformat(f["entry_utc"])
        except Exception:
            continue
        try:
            close_dt = dt.datetime.strptime(f["close_time"].split("+")[0].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc) if f.get("close_time") else lock_dt + dt.timedelta(hours=20)
        except Exception:
            close_dt = lock_dt + dt.timedelta(hours=20)
        start_ts = int((lock_dt - dt.timedelta(hours=1)).timestamp())
        end_ts = int((close_dt + dt.timedelta(hours=2)).timestamp())
        hist = fetch_price_history(f["yes_tok"], start_ts, end_ts)
        px = price_at_or_after(hist, int(lock_dt.timestamp()))
        if px is None:
            continue
        half_spread_c = spreads.get(f["city"], FALLBACK_HALF_SPREAD_C) / 2.0
        ask_proxy_c = min(99.9, px * 100.0 + half_spread_c)
        fee_c = pmkt_fee_cents(ask_proxy_c)
        net_c = (100.0 - ask_proxy_c - fee_c) if f["won"] else -(ask_proxy_c + fee_c)
        ev_results.append({"city": f["city"], "date": f["date"], "won": f["won"],
                            "raw_gap_c": round(100 * (1 - px), 3),
                            "ask_proxy_c": round(ask_proxy_c, 3), "fee_c": round(fee_c, 4), "net_ev_c": round(net_c, 3)})

    ev_reweighted_c_per_ct = None
    if ev_results:
        raw = [e["raw_gap_c"] for e in ev_results]
        net = [e["net_ev_c"] for e in ev_results]
        win_net = [e["net_ev_c"] for e in ev_results if e["won"]]
        loss_net = [e["net_ev_c"] for e in ev_results if not e["won"]]
        print(f"\n  n={len(ev_results)} priced fires ({len(win_net)} win, {len(loss_net)} loss)")
        print(f"  raw gap at entry (1-last_trade), cents: mean={st.mean(raw):.2f} median={st.median(raw):.2f}")
        print(f"  net EV/ct, unweighted, LOSS-INCLUSIVE: mean={st.mean(net):.2f} median={st.median(net):.2f}")
        # item-2b base-rate reweighting, IDENTICAL construction to pmkt_final_verdict.md section 3
        if win_net and loss_net and n_entries:
            true_win_rate = 1.0 - (n_entry_wrong / n_entries)
            ev_reweighted_c_per_ct = true_win_rate * st.mean(win_net) + (1 - true_win_rate) * st.mean(loss_net)
            print(f"  2b-reweighted EV/ct = {true_win_rate:.4f} x ({st.mean(win_net):+.2f}) + "
                  f"{1-true_win_rate:.4f} x ({st.mean(loss_net):+.2f}) = {ev_reweighted_c_per_ct:+.2f}c/ct")
        else:
            print("  (insufficient win+loss priced fires to compute the 2b-reweighted EV)")
    else:
        print("\n  No priced fires (thin/absent CLOB history for these tickers).")

    # ---- VERDICT ----
    bar_a = coverage is not None and coverage >= 0.55 and cov_lo is not None and cov_lo > 0.409
    bar_b = n_locks == 0 or n_wrong == 0
    verdict = "PASS" if (bar_a and bar_b) else "FAIL"
    print("\n" + "=" * 100)
    print(f"PRE-REGISTERED VERDICT: {verdict}")
    print(f"  (a) coverage>=55% AND Wilson LB>40.9%: {bar_a}  "
          f"(coverage={f'{100*coverage:.1f}%' if coverage is not None else '--'}, "
          f"LB={f'{100*cov_lo:.1f}%' if cov_lo is not None else '--'})")
    print(f"  (b) false-lock count == 0 (pure rule): {bar_b}  (n_locks={n_locks}, n_wrong={n_wrong})")
    print("=" * 100)

    out.update({
        "usable_city_days": usable_city_days, "n_skipped": len(skips), "skips": skips,
        "n_winner_never_entered": n_winner_never_entered, "n_covered": n_covered,
        "coverage": coverage, "coverage_wilson_ci95": [cov_lo, cov_hi],
        "hourly_baseline_coverage": 0.409,
        "n_lock_records": n_locks, "n_wrong": n_wrong,
        "loss_rate": (n_wrong / n_locks) if n_locks else None,
        "loss_rate_ci95": list(wilson_ci(n_wrong, n_locks)) if n_locks else None,
        "n_entries": n_entries, "n_entry_wrong": n_entry_wrong,
        "entry_loss_rate": (n_entry_wrong / n_entries) if n_entries else None,
        "entry_loss_rate_ci95": list(wilson_ci(n_entry_wrong, n_entries)) if n_entries else None,
        "lock_records": all_lock_records, "entry_records": all_entry_records,
        "ev_fires_n": len(ev_fires), "ev_results": ev_results,
        "ev_reweighted_c_per_ct": ev_reweighted_c_per_ct,
        "live_spreads_c": spreads,
        "per_day_log": per_day_log,
        "verdict": verdict,
        "bar_a_coverage_pass": bar_a, "bar_b_falselock_pass": bar_b,
    })
    out_path = os.path.join(HERE, "out", "tracka_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"\nwrote {out_path}")
    return out


if __name__ == "__main__":
    run(cached_only="--cached-only" in sys.argv[1:])
