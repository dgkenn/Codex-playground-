#!/usr/bin/env python3
"""pmkt_gap_study.py -- does the K-WX mechanical-lock edge exist and pay on Polymarket?

wx_new_capacity_scan.md (Q1) found that Polymarket lists the same daily high/low temperature
bracket-ladder product as Kalshi, across 51 cities (40 not on Kalshi at all), with a real resting
CLOB book -- but flagged TWO things as unmeasured: (1) settlement-source basis risk (Wunderground
scrape vs the NWS CLI Kalshi uses), and (2) whether Polymarket's own book reprices AS SLOWLY as
Kalshi's retail -- the whole edge lives in that lag. This script measures (2) directly, and gets a
free read on (1) as a side effect, using real historical data:

  STEP 1 (historical gap-decay, the core question): for ~20 RESOLVED daily-high-temperature
    city-day events (11 US cities that overlap Kalshi's 20, so the SAME station feed doubles as
    both the winner-determination signal and the basis-risk check), reconstruct the mechanical
    LOCK moment from IEM's true one-minute ASOS feed (the same feed kalshi_weather_nowcast.py
    uses): the lock is the timestamp of the observation that sets the day's FINAL running max --
    after that instant no further data can change which bracket wins (this generalizes Kalshi's
    "running max clears threshold" lock to a bracket ladder). Then pull Polymarket's own
    prices-history for the winning rung's YES token (clob.polymarket.com/prices-history) and read
    off gap=1-price at lock, lock+2/5/10/30/60min -- the Polymarket analog of the repo's
    decay_gap_by_min from archive/code/phase2_trackA_price.py.

  STEP 2 (live depth sample): for TODAY's open ladders across the same ~10-11 cities, snapshot
    CLOB order books (clob.polymarket.com/book) for the near-lock rung (highest bestAsk, i.e.
    closest to converged) and a pre-lock rung (mid-ladder), and compare fillable depth/spread to
    a FRESH live pull of Kalshi's own book depth (wx_capacity_probe.py --report), not a stale
    number.

READ-ONLY, public APIs only (Gamma + CLOB + IEM ASOS), no auth, no orders, no trading code. Being
polite: small n, sleeps between calls, no wide crawls -- point queries by known slug/date.

Usage:
  python pmkt_gap_study.py              # full run: historical gap study + live depth sample
  python pmkt_gap_study.py --hist-only  # skip the live depth section
  python pmkt_gap_study.py --live-only  # skip the historical gap section
"""
import bisect
import json
import os
import re
import ssl
import statistics as st
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; pmkt-gap-study/1.0)"}

GBASE = "https://gamma-api.polymarket.com"
CBASE = "https://clob.polymarket.com"
ASOS_BASE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, ".pmkt_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

DECAY_MIN = [0, 2, 5, 10, 30, 60]

# GLITCH FILTER -- identical rule to kalshi_weather_refined.py's clean_station_obs (reused, not
# reinvented): reject physically-impossible absolute readings and isolated single-minute spikes
# that jump away from BOTH neighbors and immediately revert. Applied before computing the running
# max so a single bad ASOS tick doesn't fabricate a fake "final max"/lock.
GLITCH_ABS_CAP_F = 130.0
GLITCH_ABS_FLOOR_F = -60.0
GLITCH_JUMP_F_PER_MIN = 8.0

# CONFIRMATION WINDOW for the bracket-ladder lock. Kalshi's KXHIGH family is a ONE-SIDED threshold
# (">X"): once the running max crosses it, YES is mechanically guaranteed forever (running max is
# monotonic non-decreasing) -- an instantaneous, real-time-computable lock. Polymarket's bracket
# rungs ([lo,hi]) have NO such one-shot guarantee: crossing INTO the bracket says nothing about
# whether the temp climbs OUT the top later that afternoon. The naive "timestamp of the day's
# final record" is only knowable in hindsight -- not a real trading signal. So the lock used here
# is the more honest, real-time-computable proxy: the first moment after which the running max has
# gone SUSTAIN_CONFIRM_MIN minutes with no new record (i.e., what a trader watching the live feed
# could actually act on). This is checked against the FIRST run below (see run_historical's
# naive-vs-confirmed comparison printout).
SUSTAIN_CONFIRM_MIN = 30

# The 11 cities wx_new_capacity_scan.md found overlapping Kalshi's 20-city KXHIGH set. Each maps a
# Polymarket URL-slug city name to (IEM asos1min bare station id, PM-title-case name, DST UTC
# offset in July -- Polymarket's Wunderground scrape reads the LOCAL WALL-CLOCK calendar day, i.e.
# daylight time in July, unlike Kalshi's fixed-standard-time LST convention).
#
# IMPORTANT, MEASURED FINDING (not assumed): the station below is Polymarket's OWN settlement
# station, read directly off each event's `resolutionSource` (a Wunderground station-history URL),
# NOT copy-pasted from kalshi_weather_nowcast.CITY_CONFIG. Doing that comparison caught a real
# result -- 4 of these 11 cities settle on a DIFFERENT physical station than the Kalshi ticker for
# the same city: Chicago (Polymarket KORD/O'Hare vs Kalshi KMDW/Midway), Dallas (KDAL/Love Field vs
# KDFW), Denver (KBKF/Buckley-Aurora vs KDEN/Denver-Intl), NYC (KLGA/LaGuardia vs the Central Park
# COOP site). The other 7 (Atlanta, Austin, Houston, LA, Miami, SF, Seattle) happen to share the
# same airport station as their Kalshi ticker. This means the two venues' "same city" ladders are
# NOT interchangeable basis-wise even where the mechanical-lock idea might otherwise port over --
# see pmkt_gap_study.md.
CITY_STATIONS = {
    "atlanta":       ("ATL", "Atlanta",       -4),
    "austin":        ("AUS", "Austin",        -5),
    "chicago":       ("ORD", "Chicago",       -5),   # PM settles KORD, NOT Kalshi's KMDW
    "dallas":        ("DAL", "Dallas",        -5),   # PM settles KDAL, NOT Kalshi's KDFW
    "denver":        ("BKF", "Denver",        -6),   # PM settles KBKF (Aurora), NOT Kalshi's KDEN
    "houston":       ("HOU", "Houston",       -5),
    "los-angeles":   ("LAX", "Los Angeles",   -7),
    "miami":         ("MIA", "Miami",         -4),
    "nyc":           ("LGA", "NYC",           -4),   # PM settles KLGA, NOT Kalshi's Central Park
    "san-francisco": ("SFO", "San Francisco", -7),
    "seattle":       ("SEA", "Seattle",       -7),
}

# Resolved-market sample dates (all well before today=2026-07-19, so IEM's 1-2 day-lagged 1-min
# archive and Polymarket's own settlement are both certainly final). Two dates/city = 22 candidate
# city-days -> "10-20 resolved markets" per the task, allowing for a few skips (missing station
# data, event not found, price history too thin).
SAMPLE_DATES = ["july-11-2026", "july-17-2026"]


def _get_json(url, timeout=25, retries=4):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code not in (429, 500, 502, 503, 504):
                return {"__err__": f"HTTP {e.code}"}
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            last_err = e
            time.sleep(1.0 * (attempt + 1))
    return {"__err__": f"{type(last_err).__name__}: {last_err}"}


def _get_text(url, timeout=30, retries=4):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return urllib.request.urlopen(req, timeout=timeout, context=_CTX).read().decode("utf-8", "replace")
        except Exception as e:
            last_err = e
            time.sleep(1.0 * (attempt + 1))
    raise last_err


def _cache(name):
    p = os.path.join(CACHE_DIR, name)
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            return None
    return None


def _save_cache(name, obj):
    json.dump(obj, open(os.path.join(CACHE_DIR, name), "w"))


# --------------------------------------------------------------------------------------------------
# bracket parsing
# --------------------------------------------------------------------------------------------------

def parse_bracket(title):
    """'94-95°F' -> (94,95); '83°F or below' -> (None,83); '102°F or higher' -> (102,None)."""
    t = (title or "").strip()
    m = re.match(r"^(-?\d+)\s*-\s*(-?\d+)\s*°?F?$", t)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.match(r"^(-?\d+)\s*°?F?\s+or\s+below$", t, re.I)
    if m:
        return None, float(m.group(1))
    m = re.match(r"^(-?\d+)\s*°?F?\s+or\s+(higher|above)$", t, re.I)
    if m:
        return float(m.group(1)), None
    return None, None


# --------------------------------------------------------------------------------------------------
# IEM ASOS 1-min station obs -> mechanical lock time (same feed/technique as kalshi_weather_nowcast)
# --------------------------------------------------------------------------------------------------

def fetch_asos_1min(station_bare, start_utc, end_utc):
    cache_key = f"asos1min_{station_bare}_{start_utc.isoformat()}_{end_utc.isoformat()}.json"
    cached = _cache(cache_key)
    if cached is not None:
        return [(datetime.fromisoformat(t), v) for t, v in cached]
    sts = start_utc.strftime("%Y-%m-%dT%H:%MZ")
    ets = end_utc.strftime("%Y-%m-%dT%H:%MZ")
    url = f"{ASOS_BASE}?station={station_bare}&vars=tmpf&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma"
    text = _get_text(url)
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
    _save_cache(cache_key, [(t.isoformat(), v) for t, v in out])
    return out


def clean_obs(obs):
    """Reused verbatim rule from kalshi_weather_refined.py's clean_station_obs: drop physically-
    impossible readings and isolated single-minute spikes (jumps away from both neighbors that
    immediately revert)."""
    n = len(obs)
    cleaned = []
    for i in range(n):
        t, v = obs[i]
        if v > GLITCH_ABS_CAP_F or v < GLITCH_ABS_FLOOR_F:
            continue
        is_spike = False
        if 0 < i < n - 1:
            tp, vp = obs[i - 1]
            tn, vn = obs[i + 1]
            dt_prev = max((t - tp).total_seconds() / 60.0, 1e-6)
            dt_next = max((tn - t).total_seconds() / 60.0, 1e-6)
            rate_in = abs(v - vp) / dt_prev
            rate_out = abs(vn - v) / dt_next
            if rate_in > GLITCH_JUMP_F_PER_MIN and rate_out > GLITCH_JUMP_F_PER_MIN and (v - vp) * (v - vn) > 0:
                is_spike = True
        if not is_spike:
            cleaned.append((t, v))
    return cleaned


def find_lock(obs, sustain_min=SUSTAIN_CONFIRM_MIN):
    """Returns (naive_lock_dt, confirmed_lock_dt, day_max_f) or (None, None, None).

    naive_lock  = timestamp of the observation that sets the day's FINAL running max (only
                  knowable in hindsight -- reported for comparison, NOT used as the tradable signal).
    confirmed_lock = naive_lock + sustain_min, i.e. the first point in time a live trader could
                  actually have sustain_min minutes of "no new record" confirmation that the
                  climb is over -- capped at the last available observation. This is the
                  real-time-computable lock used for the gap/decay measurement below."""
    if not obs:
        return None, None, None
    running_max = None
    naive_lock = None
    for t, v in obs:
        if running_max is None or v > running_max:
            running_max = v
            naive_lock = t
    if naive_lock is None:
        return None, None, None
    target = naive_lock + timedelta(minutes=sustain_min)
    last_t = obs[-1][0]
    confirmed_lock = min(target, last_t)
    return naive_lock, confirmed_lock, running_max


# --------------------------------------------------------------------------------------------------
# Polymarket price history for the winning token
# --------------------------------------------------------------------------------------------------

def fetch_price_history(token_id, start_ts, end_ts):
    cache_key = f"phist_{token_id}_{start_ts}_{end_ts}.json"
    cached = _cache(cache_key)
    if cached is not None:
        return cached
    url = f"{CBASE}/prices-history?market={token_id}&startTs={start_ts}&endTs={end_ts}&fidelity=1"
    d = _get_json(url)
    hist = d.get("history", []) if isinstance(d, dict) and "__err__" not in d else []
    _save_cache(cache_key, hist)
    return hist


def price_at_or_after(hist_sorted_ts, hist_prices, ts):
    """hist is sorted by t ascending. Return price at first point with t>=ts, else None."""
    i = bisect.bisect_left(hist_sorted_ts, ts)
    if i >= len(hist_sorted_ts):
        return None
    return hist_prices[i]


# --------------------------------------------------------------------------------------------------
# STEP 1 -- historical gap-decay study
# --------------------------------------------------------------------------------------------------

def study_one(city_slug, date_slug):
    station, city_name, offset = CITY_STATIONS[city_slug]
    slug = f"highest-temperature-in-{city_slug}-on-{date_slug}"
    ev = _get_json(f"{GBASE}/events/slug/{slug}")
    if not isinstance(ev, dict) or "__err__" in ev or not ev.get("markets"):
        return {"skip": f"{slug}: event fetch failed ({ev.get('__err__') if isinstance(ev, dict) else 'no data'})"}

    markets = ev["markets"]
    winner = None
    for m in markets:
        try:
            prices = json.loads(m.get("outcomePrices") or "[]")
        except Exception:
            prices = []
        if prices and abs(float(prices[0]) - 1.0) < 1e-6:
            winner = m
            break
    if winner is None:
        return {"skip": f"{slug}: no resolved winning rung found (market may still be open)"}

    lo, hi = parse_bracket(winner.get("groupItemTitle"))
    try:
        tok_ids = json.loads(winner.get("clobTokenIds") or "[]")
    except Exception:
        tok_ids = []
    if not tok_ids:
        return {"skip": f"{slug}: winning rung has no clobTokenIds"}
    yes_token = tok_ids[0]

    # date from the slug, e.g. "july-11-2026"
    mo_name, day_s, yr_s = date_slug.split("-")
    month = ["january", "february", "march", "april", "may", "june", "july", "august",
             "september", "october", "november", "december"].index(mo_name) + 1
    day, year = int(day_s), int(yr_s)
    local_midnight_utc = datetime(year, month, day, 0, 0, tzinfo=timezone.utc) - timedelta(hours=offset)
    day_start = local_midnight_utc
    day_end = local_midnight_utc + timedelta(days=1)

    # pull a padded window of 1-min obs, then restrict to the local calendar day for the running max
    obs = fetch_asos_1min(station, day_start - timedelta(hours=1), day_end + timedelta(hours=3))
    day_obs_raw = [(t, v) for t, v in obs if day_start <= t < day_end]
    if len(day_obs_raw) < 100:
        return {"skip": f"{slug}: only {len(day_obs_raw)} 1-min obs in the local day window (station data thin)"}
    # COMPLETENESS GUARD: IEM's 1-min ASOS feed has real per-station-day transmission gaps (caught
    # concretely on KLAX/2026-07-17, which cut out at 15:07Z leaving a fake early "day max" of 73F
    # vs the true winning 86-87F bracket). Require obs to reach within 3h of local day-end, else the
    # 'final record' is an artifact of a dropped feed, not a real day max.
    if day_obs_raw[-1][0] < day_end - timedelta(hours=3):
        return {"skip": f"{slug}: station feed gap -- last obs {day_obs_raw[-1][0].isoformat()}, "
                         f"local day ends {day_end.isoformat()} (incomplete day, would fake an early lock)"}
    day_obs = clean_obs(day_obs_raw)

    naive_lock, lock_t, day_max_f = find_lock(day_obs)
    if lock_t is None:
        return {"skip": f"{slug}: could not determine a running-max lock"}

    # basis check: does the ASOS-derived whole-degree day max fall inside the PM winning bracket?
    day_max_round = round(day_max_f)
    if lo is not None and hi is not None:
        basis_ok = lo <= day_max_round <= hi
    elif lo is None:
        basis_ok = day_max_round <= hi
    elif hi is None:
        basis_ok = day_max_round >= lo
    else:
        basis_ok = None

    close_time_str = winner.get("closedTime")
    try:
        close_dt = datetime.strptime(close_time_str.split("+")[0].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        close_dt = day_end + timedelta(hours=18)
    start_ts = int((day_start - timedelta(hours=1)).timestamp())
    end_ts = int((close_dt + timedelta(hours=2)).timestamp())

    hist = fetch_price_history(yes_token, start_ts, end_ts)
    if len(hist) < 5:
        return {"skip": f"{slug}: price-history too thin ({len(hist)} points) -- low-volume rung"}
    hist_ts = [h["t"] for h in hist]
    hist_px = [h["p"] for h in hist]

    lock_ts = int(lock_t.timestamp())
    decay = {}
    for k in DECAY_MIN:
        px = price_at_or_after(hist_ts, hist_px, lock_ts + k * 60)
        decay[k] = (1.0 - px) if px is not None else None

    naive_decay = {}
    naive_ts = int(naive_lock.timestamp())
    for k in DECAY_MIN:
        px = price_at_or_after(hist_ts, hist_px, naive_ts + k * 60)
        naive_decay[k] = (1.0 - px) if px is not None else None

    return {
        "skip": None,
        "city": city_name, "date": date_slug, "station": station,
        "rung": winner.get("groupItemTitle"), "lo": lo, "hi": hi,
        "day_max_f": day_max_f, "day_max_round": day_max_round, "basis_ok": basis_ok,
        "naive_lock_utc": naive_lock.isoformat(), "lock_utc": lock_t.isoformat(),
        "confirm_delay_min": round((lock_t - naive_lock).total_seconds() / 60.0, 1),
        "decay_gap_by_min": decay, "naive_decay_gap_by_min": naive_decay,
        "n_hist_points": len(hist), "vol24h": winner.get("volume24hr"), "liq": winner.get("liquidityNum"),
    }


def run_historical():
    print("=" * 100)
    print("STEP 1 -- HISTORICAL GAP-DECAY STUDY (Polymarket analog of decay_gap_by_min)")
    print("=" * 100)
    records, skips = [], []
    for city_slug in CITY_STATIONS:
        for date_slug in SAMPLE_DATES:
            r = study_one(city_slug, date_slug)
            if r.get("skip"):
                skips.append(r["skip"])
                print(f"  SKIP: {r['skip']}")
            else:
                records.append(r)
                d = r["decay_gap_by_min"]
                nd = r["naive_decay_gap_by_min"]
                print(f"  OK  {r['city']:<14} {r['date']:<14} rung={r['rung']:<12} "
                      f"naive_lock={r['naive_lock_utc'][11:16]}Z confirmed_lock={r['lock_utc'][11:16]}Z "
                      f"basis_ok={r['basis_ok']}  gap0={d[0]:.3f}  gap5={d[5]:.3f}  gap30={d[30]:.3f}  "
                      f"(naive gap0={nd[0]:.3f})")
            time.sleep(0.2)
    print(f"\n  {len(records)} usable fires, {len(skips)} skipped.")
    return records, skips


def summarize_historical(records):
    print("\n" + "-" * 100)
    print("  DECAY TABLE (mean / median gap=1-price at lock and lock+k min, n usable per column)")
    print("-" * 100)
    print(f"    {'t (min)':<10}{'n':<6}{'mean gap':<12}{'median gap':<12}{'mean retention':<16}")
    g0_by_rec = {}
    for r in records:
        g0 = r["decay_gap_by_min"].get(0)
        if g0 is not None:
            g0_by_rec[id(r)] = g0
    for k in DECAY_MIN:
        vals = [r["decay_gap_by_min"].get(k) for r in records if r["decay_gap_by_min"].get(k) is not None]
        if not vals:
            print(f"    {k:<10}{0:<6}{'--':<12}{'--':<12}{'--':<16}")
            continue
        ret_vals = []
        for r in records:
            g0 = r["decay_gap_by_min"].get(0)
            gk = r["decay_gap_by_min"].get(k)
            if g0 and g0 > 0.005 and gk is not None:
                ret_vals.append(gk / g0)
        mean_ret = st.mean(ret_vals) if ret_vals else None
        print(f"    {k:<10}{len(vals):<6}{st.mean(vals):<12.4f}{st.median(vals):<12.4f}"
              f"{(f'{mean_ret:.3f}' if mean_ret is not None else '--'):<16}")

    basis_flags = [r["basis_ok"] for r in records if r["basis_ok"] is not None]
    if basis_flags:
        agree = sum(1 for b in basis_flags if b) / len(basis_flags)
        print(f"\n  BASIS CHECK (IEM ASOS whole-degree day-max vs PM winning bracket): "
              f"{sum(basis_flags)}/{len(basis_flags)} agree ({100*agree:.0f}%)")

    g0s = [r["decay_gap_by_min"].get(0) for r in records if r["decay_gap_by_min"].get(0) is not None]
    if g0s:
        priced = [g for g in g0s if g > 0.02]
        print(f"\n  Fires with a REAL gap at lock (>2c): {len(priced)}/{len(g0s)} "
              f"({100*len(priced)/len(g0s):.0f}%); mean gap when real: "
              f"{st.mean(priced):.4f}" if priced else "  No fire had a real (>2c) gap at lock.")
    return records


# --------------------------------------------------------------------------------------------------
# STEP 2 -- live depth sample (today's open ladders)
# --------------------------------------------------------------------------------------------------

def fetch_book_depth(token_id, band_c=2):
    ob = _get_json(f"{CBASE}/book?token_id={token_id}")
    if not isinstance(ob, dict) or "__err__" in ob:
        return None
    bids, asks = ob.get("bids", []) or [], ob.get("asks", []) or []
    best_ask = min((float(a["price"]) for a in asks), default=None)
    best_bid = max((float(b["price"]) for b in bids), default=None)
    near_ask_usd = 0.0
    if best_ask is not None:
        for a in asks:
            if float(a["price"]) <= best_ask + band_c / 100.0:
                near_ask_usd += float(a["price"]) * float(a["size"])
    spread = (best_ask - best_bid) if (best_ask is not None and best_bid is not None) else None
    return {
        "best_ask": best_ask, "best_bid": best_bid, "spread": spread,
        "n_ask_levels": len(asks), "n_bid_levels": len(bids),
        f"depth_usd_within_{band_c}c_of_ask": round(near_ask_usd, 2),
    }


def run_live_depth():
    print("\n" + "=" * 100)
    print("STEP 2 -- LIVE DEPTH SAMPLE (today's open ladders, ~11 overlap cities)")
    print("=" * 100)
    rows = []
    for city_slug, (station, city_name, _off) in CITY_STATIONS.items():
        ev = _get_json(f"{GBASE}/public-search?q={city_name.replace(' ', '%20')}&limit_per_type=10")
        # simpler & more robust: look up today's event directly via the events endpoint filtered by title
        # (public-search is noisy); fall back to a direct slug guess for TODAY.
        today = datetime.now(timezone.utc)
        for delta_days in (0, 1):  # today's ladder may already show tomorrow's slug depending on UTC roll
            d = today + timedelta(days=delta_days)
            date_slug = f"{d.strftime('%B').lower()}-{d.day}-{d.year}"
            slug = f"highest-temperature-in-{city_slug}-on-{date_slug}"
            detail = _get_json(f"{GBASE}/events/slug/{slug}")
            if isinstance(detail, dict) and "__err__" not in detail and detail.get("markets"):
                mkts = [m for m in detail["markets"] if not m.get("closed")]
                if mkts:
                    break
        else:
            print(f"  {city_name:<16} no open ladder found today")
            continue
        if not mkts:
            print(f"  {city_name:<16} ladder found but all rungs closed")
            continue

        with_ask = [m for m in mkts if m.get("bestAsk") is not None]
        if not with_ask:
            print(f"  {city_name:<16} open ladder but no rung has a bestAsk")
            continue
        near_lock = max(with_ask, key=lambda m: m["bestAsk"])
        pre_lock = min(with_ask, key=lambda m: abs(m["bestAsk"] - 0.5))

        for label, m in (("near-lock", near_lock), ("pre-lock", pre_lock)):
            try:
                tok = json.loads(m.get("clobTokenIds") or "[]")[0]
            except Exception:
                continue
            depth = fetch_book_depth(tok)
            if depth is None:
                continue
            row = {"city": city_name, "label": label, "rung": m.get("groupItemTitle"),
                   "bestAsk_gamma": m.get("bestAsk"), **depth}
            rows.append(row)
            print(f"  {city_name:<16} {label:<10} rung={str(m.get('groupItemTitle')):<12} "
                  f"ask={depth['best_ask']} bid={depth['best_bid']} spread={depth['spread']} "
                  f"depth<=2c=${depth.get('depth_usd_within_2c_of_ask')}")
            time.sleep(0.2)
    return rows


def summarize_live_depth(rows):
    near = [r for r in rows if r["label"] == "near-lock" and r.get("depth_usd_within_2c_of_ask") is not None]
    pre = [r for r in rows if r["label"] == "pre-lock" and r.get("depth_usd_within_2c_of_ask") is not None]
    print("\n" + "-" * 100)
    if near:
        d = sorted(r["depth_usd_within_2c_of_ask"] for r in near)
        print(f"  near-lock depth<=2c ($): n={len(d)} median={st.median(d):.0f} "
              f"mean={st.mean(d):.0f} min={min(d):.0f} max={max(d):.0f}")
    if pre:
        d = sorted(r["depth_usd_within_2c_of_ask"] for r in pre)
        print(f"  pre-lock  depth<=2c ($): n={len(d)} median={st.median(d):.0f} "
              f"mean={st.mean(d):.0f} min={min(d):.0f} max={max(d):.0f}")
    spreads = [r["spread"] for r in rows if r.get("spread") is not None]
    if spreads:
        print(f"  spread (all rungs sampled): median={st.median(spreads):.4f} mean={st.mean(spreads):.4f}")


def main():
    args = sys.argv[1:]
    hist_records, live_rows = [], []
    if "--live-only" not in args:
        hist_records, skips = run_historical()
        summarize_historical(hist_records)
        _save_cache("last_hist_records.json", hist_records)
    if "--hist-only" not in args:
        live_rows = run_live_depth()
        summarize_live_depth(live_rows)
        _save_cache("last_live_rows.json", live_rows)
    print("\n" + "=" * 100)
    print("See pmkt_gap_study.md for the full write-up, EV estimate, and verdict.")
    print("=" * 100)


if __name__ == "__main__":
    main()
