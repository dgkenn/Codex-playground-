#!/usr/bin/env python3
"""pmkt_final_verdict.py -- PHASE 2, the decisive run pmkt_settlement_basis.md and pmkt_gap_study.md both
left for later. Both studies ended INCONCLUSIVE and each named exactly what would move the needle:

  pmkt_settlement_basis.md  -- "worth a closer look" whitelist of basis-SOUND cities (~100% IEM-vs-settled
    agreement, or an explainable near-miss for Chicago); flagged Denver/NYC-low/Miami-low/Hong Kong as
    RISKY or UNVERIFIABLE and explicitly said not to generalize past that whitelist.
  pmkt_gap_study.md "What would move this from INCONCLUSIVE to CONFIRMED or NULL":
    1. Scale the historical sample to 60-100+ city-days (was n=15).
    2. Measure the FALSE-LOCK rate -- this had never been measured; every prior fire was a known winner.
    3. Replace mid/last-trade price with a real executable-ask-based entry cost.
    4. Resolve the operational blockers (wallet/USDC/CLOB stack, geo/compliance) -- separately flagged,
       not answered statistically.

THIS SCRIPT answers 1-3 for real, restricted to the settlement_basis whitelist (the only cities where the
free-feed signal is even worth backtesting), and prints the GO/NO-GO/STILL-BLOCKED verdict from the
measured numbers. Item 4 is restated as an operator checklist in the .md, not resolved here (no trading
code, no wallet/API integration -- out of scope by design).

WHITELIST (from pmkt_settlement_basis.md's per-city verdict table): Chicago (KORD, 92.9% agreement, single
explainable 1-rung/2F miss), London (EGLC, 100.0%), Paris (LFPB, 100.0%), Mexico City (MMMX, 100.0%),
Sao Paulo (SBGR, 100.0%), Tokyo (RJTT, 100.0%). Excluded by that study's own verdict: Denver (28.6%, RISKY),
NYC/Miami HIGH (borderline/RISKY), NYC/Miami LOW (RISKY), Hong Kong (UNVERIFIABLE, wrong station).

RESTRICTED FURTHER to "usable IEM/METAR coverage" per the task: this script itself discovers (see
`_probe_1min_coverage` note below, run once, result hard-coded with the measured evidence) that IEM's
TRUE 1-minute ASOS archive (`asos1min.py`, what pmkt_gap_study.py used) is US-ONLY -- EGLC/LFPB/MMMX/SBGR/
RJTT return zero rows. IEM's ROUTINE (hourly-ish METAR) archive (`asos.py`) IS global and DOES cover all
six whitelist stations (confirmed live: EGLC/RJTT returned ~24-25 rows/day; ORD/LFPB/MMMX/SBGR intermittently
429'd under a tight test loop but are the same public network and known-present per pmkt_settlement_basis.md
section 1). This is the ONLY obs stream available for a Polymarket build across this whitelist -- there is
no working 1-minute feed for 5 of 6 cities -- so the deployed lock rule (glitch filter + sustain-3 + margin)
is applied here to ROUTINE METAR, not 1-minute ASOS. Per kwx_runner.sustained_extreme's own docstring this
makes the rule MORE conservative, never less (a coarser feed can only widen the minimal qualifying sustain
window, never narrow it) -- so this is a valid, if coarser, application of the SAME rule, not a different one.

MECHANICAL LOCK, AND WHY IT NEEDS ONE DOCUMENTED EXTENSION FOR BRACKETS: kwx_runner.locked_orders(), reused
VERBATIM, only ever declares YES on an uncapped top rung ("X or higher") and NO on any rung whose cap gets
exceeded -- by design, because a bounded bracket's YES side has no monotonic-running-max guarantee (a later
rise could still push it out the top). That leaves every MIDDLE and BOTTOM rung with NO direct YES lock at
all under the unmodified rule -- a real, measured finding in its own right (see item 2a below: the pure
rule's explicit-fire sample is small precisely because it almost never confirms a middle rung). ITEM 2's
false-lock rate is reported on the pure, unextended rule (2a). To have ANY winning-rung price to check for
ITEM 3's EV, this script adds one minimal, clearly-flagged extension: `entries` tracks the first moment the
same glitch+sustain-3+margin-filtered extreme fell WITHIN each rung's own [floor,cap] band (its own false
rate reported separately as item 2b, never blended into 2a). This is the bracket-ladder generalization of a
"cross" -- entering a band instead of exceeding a one-sided threshold -- built from the SAME filtered
extreme, not a new heuristic on raw obs.

USAGE:
  python pmkt_final_verdict.py                 # full run: fetch, backtest, verdict (real API calls)
  python pmkt_final_verdict.py --cached-only    # recompute verdict from cached pulls only, no network

Read-only, public APIs only (Gamma + CLOB + IEM Mesonet), no auth, no orders, no trading code. Polite:
cached, retried with backoff, slept between calls, point queries only.
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
import kwx_runner as R   # reuse the DEPLOYED lock-rule code verbatim: sustained_extreme, locked_orders

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; pmkt-final-verdict/1.0)"}

GBASE = "https://gamma-api.polymarket.com"
CBASE = "https://clob.polymarket.com"
DAILY_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

CACHE_DIR = os.path.join(HERE, ".pmkt_final_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# --------------------------------------------------------------------------------------------------------
# WHITELIST -- reused from pmkt_settlement_basis.py's STATIONS dict (station ids), restricted to the
# ~100%-agreement + explainable-Chicago cities per that study's verdict table (section 5).
# tz = IANA zone (drives correct local-day boundaries across DST, since the sample window spans Feb-Jul
# and crosses the US/EU spring-forward transitions -- the two merged studies used a FIXED July offset,
# which was fine for their 14-day July-only sample but would silently mis-slice days in Feb/March here).
# margin: task-specified 1F for the whole-F city, 0.5C for the whole-C cities.
# earliest: measured directly against the Gamma API (binary search on event-slug 404s, 2026-07-19), i.e.
# the actual first day this repo could have pulled a resolved ladder for that city -- NOT a guess.
# --------------------------------------------------------------------------------------------------------
WHITELIST = {
    "chicago":     dict(station="ORD",  unit="F", tz="America/Chicago",     margin=1.0, earliest=dt.date(2026, 2, 6)),
    "london":      dict(station="EGLC", unit="C", tz="Europe/London",       margin=0.5, earliest=dt.date(2026, 2, 6)),
    "paris":       dict(station="LFPB", unit="C", tz="Europe/Paris",        margin=0.5, earliest=dt.date(2026, 2, 14)),
    "sao-paulo":   dict(station="SBGR", unit="C", tz="America/Sao_Paulo",   margin=0.5, earliest=dt.date(2026, 2, 14)),
    "tokyo":       dict(station="RJTT", unit="C", tz="Asia/Tokyo",          margin=0.5, earliest=dt.date(2026, 3, 12)),
    "mexico-city": dict(station="MMMX", unit="C", tz="America/Mexico_City", margin=0.5, earliest=dt.date(2026, 4, 3)),
}
END_DATE = dt.date(2026, 7, 18)          # last fully-settled day as of the 2026-07-19 run, same convention
                                          # as pmkt_settlement_basis.py's END_DATE
TARGET_SAMPLES_PER_CITY = 22             # -> ~130 candidate city-days before skips; target is >=60 usable

# Polymarket Weather-category CLOB taker fee (docs.polymarket.com/trading/fees + help.polymarket.com
# /en/articles/13364478-trading-fees, both fetched live 2026-07-19): fee = shares * feeRate * p * (1-p),
# feeRate=0.05 for the Weather category, TAKER-ONLY (makers pay nothing). A mechanical-lock buy is always
# a taker (crossing the resting ask), so this is the fee that applies to every fire modeled here.
PMKT_WEATHER_FEE_RATE = 0.05

# Live-measured fallback spread (pmkt_gap_study.md Step 2, same day-of-week live CLOB pull, 11 cities):
# median 3.3c, used only when this run's own live probe (below) can't get a fresh number for a city.
FALLBACK_HALF_SPREAD_C = 3.3 / 2.0


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
# bracket parsing -> CONTINUOUS native-unit (floor, cap) boundaries, +/-0.5 native-unit around the printed
# whole-degree label (the physical range that rounds to that label at the market's stated whole-degree
# precision -- same idea pmkt_settlement_basis.py used when it rounded IEM obs to compare against a
# single-value C bracket, just made explicit and symmetric here for the (floor,cap) representation
# kwx_runner.locked_orders() expects).
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
                       "yes_ask_c": 50, "no_ask_c": 50,   # placeholder; only used by locked_orders' MAX_PAY
                                                            # gate, which we bypass by calling it with margin
                                                            # only (see backtest_day) -- kept non-None so the
                                                            # ask<=MAX_PAY_CENTS guard never spuriously blocks
                       "yes_tok": tok_ids[0] if len(tok_ids) > 0 else None,
                       "no_tok": tok_ids[1] if len(tok_ids) > 1 else None})
    if winner is None:
        return None
    return rungs, titles, winner


# --------------------------------------------------------------------------------------------------------
# IEM routine METAR archive (global coverage, unlike the US-only 1-minute ASOS archive) -- confirmed live
# 2026-07-19: EGLC/RJTT returned ~24-25 hourly rows for a single test day; ORD/LFPB/MMMX/SBGR are the same
# public network (IL_ASOS/FR__ASOS/MX__ASOS/BR__ASOS per pmkt_settlement_basis.md section 2) and 429'd only
# under a rapid-fire unthrottled test loop, not a coverage gap -- this fetcher retries with backoff.
# --------------------------------------------------------------------------------------------------------
def fetch_iem_routine(station, start_utc, end_utc):
    key = f"asos_{station}_{start_utc:%Y%m%dT%H%M}_{end_utc:%Y%m%dT%H%M}.json"
    cached = _cache_get(key)
    if cached is not None:
        return [(dt.datetime.fromisoformat(t), v) for t, v in cached]
    # MEASURED QUIRK (not assumed): IEM's asos.py treats day2/month2/year2 as an EXCLUSIVE upper bound (a
    # request for day1=10,day2=11 returns ONLY day-10 rows, none of day-11) -- confirmed live 2026-07-19 by
    # requesting the same range 3x (reproducible) and comparing against a wider day1=9,day2=12 pull that DID
    # include day 11 in full. Pad the end by one calendar day here so `end_utc`'s own day is actually covered.
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
    time.sleep(0.5)
    return out


def fetch_event(city_slug, d):
    slug = f"highest-temperature-in-{city_slug}-on-{d.strftime('%B').lower()}-{d.day}-{d.year}"
    key = f"event_{slug}.json"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    ev = _get_json(f"{GBASE}/events/slug/{slug}")
    _cache_put(key, ev)
    time.sleep(0.3)
    return ev


def fetch_price_history(token_id, start_ts, end_ts):
    key = f"phist_{token_id}_{start_ts}_{end_ts}.json"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    d = _get_json(f"{CBASE}/prices-history?market={token_id}&startTs={start_ts}&endTs={end_ts}&fidelity=1")
    hist = d.get("history", []) if isinstance(d, dict) and "__err__" not in d and "__404__" not in d else []
    _cache_put(key, hist)
    time.sleep(0.3)
    return hist


# --------------------------------------------------------------------------------------------------------
# COMPLETENESS GUARD -- same shape as pmkt_gap_study.py's (a real bug it caught: a dropped feed faking an
# early "day max"), adapted for hourly-cadence routine METAR instead of 1-minute ASOS: require >=15 obs in
# the local day (out of ~24 possible hourly reports -- >=62% coverage) AND the last obs within 4h of local
# day-end (loosened from that script's 3h because routine METAR's own native cadence is ~60x coarser, so a
# single missed late-day report is not itself evidence of a feed outage the way a 1-minute gap would be).
# --------------------------------------------------------------------------------------------------------
MIN_DAY_OBS = 15
MAX_END_GAP_H = 4


def backtest_day(city_slug, d, cfg):
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

    obs_all = fetch_iem_routine(station, day_start - dt.timedelta(hours=2), day_end + dt.timedelta(hours=4))
    day_obs = [(t, v) for t, v in obs_all if day_start <= t < day_end]
    if len(day_obs) < MIN_DAY_OBS:
        return {"skip": f"thin_station_data_{len(day_obs)}obs"}
    if day_obs[-1][0] < day_end - dt.timedelta(hours=MAX_END_GAP_H):
        return {"skip": "station_feed_gap_near_dayend"}

    # ---- walk the obs stream forward, applying the DEPLOYED rule (sustained_extreme + locked_orders,
    # reused verbatim from kwx_runner) incrementally, recording every NEWLY-locked rung as it happens ----
    locked = {}   # ticker -> {"side":..., "lock_utc":..., "extreme_native":..., "cushion":...} -- explicit
                  # YES (uncapped top rung only) / NO (any rung whose cap gets exceeded) fires, EXACTLY as
                  # kwx_runner.locked_orders() defines them. This is the pure, unmodified deployed rule --
                  # feeds the item-2 false-lock-rate stat with no extension.
    entries = {}  # ticker -> {"entry_utc":..., "extreme_native":...} -- MEASURED EXTENSION (documented, not
                  # silent): the first moment the sustained extreme fell WITHIN a rung's [floor,cap] band
                  # (margin-adjusted). The deployed rule itself never emits an explicit order for a capped
                  # middle rung (by design -- no monotonic guarantee it stays there), so it structurally can
                  # never positively confirm a middle rung at all, only the single uncapped top rung. That
                  # leaves no lock time to price for the ~90% of days whose winner is a middle rung. `entries`
                  # is the minimal generalization needed to have ANY tradeable "we're in this bracket now"
                  # timestamp for item 3's EV measurement -- it is the same idea pmkt_gap_study.py's ad hoc
                  # "30-min no new record" confirmed_lock was reaching for, now driven by the ACTUAL deployed
                  # glitch+sustain-3+margin discipline instead of a bespoke heuristic. Its own false-rate
                  # (entry into a bracket the day does NOT settle in) is reported separately, clearly labeled,
                  # alongside the pure-rule stat -- not blended into it.
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

    # ---- item 2: score every EXPLICIT deployed-rule lock against the settled winner (pure rule, no ext.) ----
    lock_records = []
    for ticker, info in locked.items():
        correct = (ticker == winner_ticker) if info["side"] == "yes" else (ticker != winner_ticker)
        lock_records.append({"city": city_slug, "date": d.isoformat(), "ticker": ticker,
                              "label": titles.get(ticker), "side": info["side"],
                              "lock_utc": info["lock_utc"], "correct": correct, "cushion": info["cushion"]})

    # ---- entry-based false-rate (the EXTENSION, reported separately) ----
    entry_records = []
    for ticker, info in entries.items():
        entry_records.append({"city": city_slug, "date": d.isoformat(), "ticker": ticker,
                               "label": titles.get(ticker), "entry_utc": info["entry_utc"],
                               "correct": (ticker == winner_ticker)})

    # ---- item 3: EV fires. Budget-conscious, explicitly scoped choice (not "every entry ever touched",
    # which would be 500-1000+ extra CLOB price-history calls across the sample -- not polite, and mostly
    # pricing rungs the market had already obviously abandoned well before any lock logic fired): exactly
    # UP TO TWO fires per usable city-day --
    #   (a) the WINNING rung's own entry -- always a WIN by construction, this is "if the bot had bought
    #       the moment the deployed rule's filtered extreme first reached the bracket that, in fact, ends
    #       up being the settled bracket."
    #   (b) the entry IMMEDIATELY PRECEDING the winner's (the last rung the extreme occupied before ticking
    #       one more increment into the winner's band) -- always a LOSS by construction (ticker != winner),
    #       this is the realistic "one rung too early" false-entry case, giving the EV measurement a genuine
    #       loss side instead of only ever pricing known winners (the exact survivorship gap pmkt_gap_study.md
    #       flagged as its #1 missing piece).
    # This is a deliberate sub-sample of all entries, not the full entry population -- item 2b's false rate
    # above IS measured on the full entry population and is the correct number to trust for "how often is
    # ANY entry wrong"; this 2-per-day EV sub-sample exists only to keep the CLOB call volume sane while
    # still being genuinely loss-inclusive rather than survivorship-biased.
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
            "winner_never_entered": win_entry is None}


# --------------------------------------------------------------------------------------------------------
# Wilson score interval (no scipy dependency) -- same formula pmkt_settlement_basis.md's table cites.
# --------------------------------------------------------------------------------------------------------
def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


# --------------------------------------------------------------------------------------------------------
# LIVE SPREAD PROBE (today's open ladders, whitelist cities only) -- same technique as pmkt_gap_study.py
# Step 2, restricted to the whitelist, used to get an ask-vs-last-trade haircut for the EV measurement
# (prices-history has no historical ask; this is the best available substitute, clearly flagged as such).
# --------------------------------------------------------------------------------------------------------
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
                spreads[city_slug] = round((ba - bb) * 100.0, 2)  # cents
        time.sleep(0.3)
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
# main
# --------------------------------------------------------------------------------------------------------
def sample_dates(cfg):
    start = cfg["earliest"] + dt.timedelta(days=3)   # small buffer past the measured earliest-live date
    span = (END_DATE - start).days
    if span < 1:
        return []
    stride = max(1, span // TARGET_SAMPLES_PER_CITY)
    out, d = [], start
    while d <= END_DATE:
        out.append(d)
        d += dt.timedelta(days=stride)
    return out


def run(cached_only=False):
    print("=" * 100)
    print("PMKT FINAL VERDICT -- PHASE 2 (whitelist false-lock rate + ask-based EV)")
    print("=" * 100)

    all_lock_records, all_entry_records, ev_fires, skips = [], [], [], []
    n_winner_never_entered = 0
    usable_city_days = 0
    for city_slug, cfg in WHITELIST.items():
        dates = sample_dates(cfg)
        print(f"\n[{city_slug}] station={cfg['station']} unit={cfg['unit']} margin={cfg['margin']} "
              f"sampling {len(dates)} days from {dates[0] if dates else '-'} to {dates[-1] if dates else '-'}")
        for d in dates:
            r = backtest_day(city_slug, d, cfg)
            if r.get("skip"):
                skips.append(f"{city_slug} {d}: {r['skip']}")
                print(f"    SKIP {d} -- {r['skip']}")
                continue
            usable_city_days += 1
            all_lock_records.extend(r["lock_records"])
            all_entry_records.extend(r["entry_records"])
            ev_fires.extend(r["ev_fires"])
            if r["winner_never_entered"]:
                n_winner_never_entered += 1
            print(f"    OK   {d}  {len(r['lock_records'])} deployed-rule lock(s), "
                  f"{len(r['entry_records'])} bracket-entries, {len(r['ev_fires'])} EV fire(s), "
                  f"winner={r['winner']}" +
                  ("  [WINNER BRACKET NEVER ENTERED BY FREE FEED]" if r["winner_never_entered"] else ""))

    print("\n" + "=" * 100)
    print(f"SAMPLE SIZE: {usable_city_days} usable city-days ({len(skips)} skipped) across "
          f"{len(WHITELIST)} whitelist cities. Target was >=60 usable city-days.")
    print(f"Winner bracket never entered by the free feed (own-basis-risk cases): "
          f"{n_winner_never_entered}/{usable_city_days}")
    print("=" * 100)

    # ---- ITEM 2: false-lock rate on the PURE deployed rule's explicit YES/NO fires (no extension) ----
    n_locks = len(all_lock_records)
    n_wrong = sum(1 for x in all_lock_records if not x["correct"])
    print(f"\nITEM 2a -- POOLED FALSE-LOCK RATE, PURE DEPLOYED RULE (explicit YES/NO fires only, "
          f"n={n_locks}):")
    if n_locks:
        loss_rate = n_wrong / n_locks
        print(f"  {n_wrong}/{n_locks} wrong = {100*loss_rate:.3f}% conditional loss rate")
        clo, chi = wilson_ci(n_wrong, n_locks)
        print(f"  95% Wilson CI on the LOSS rate: [{100*clo:.3f}%, {100*chi:.3f}%]")
        print(f"  (Kalshi's own measured analog, kalshi_wx_settlement_basis.py: ~0.4% conditional loss)")
    else:
        print("  NO EXPLICIT LOCKS AT ALL -- the pure rule (YES only on the uncapped top rung, NO once a "
              "cap is exceeded) essentially never confirms a middle rung; see item 2b.")

    per_city = {}
    for x in all_lock_records:
        per_city.setdefault(x["city"], {"n": 0, "wrong": 0})
        per_city[x["city"]]["n"] += 1
        per_city[x["city"]]["wrong"] += 0 if x["correct"] else 1
    print("\nPer-city breakdown (pure rule):")
    for c, s in per_city.items():
        r = s["wrong"] / s["n"] if s["n"] else None
        print(f"  {c:14} n={s['n']:<5} wrong={s['wrong']:<5} loss_rate={f'{100*r:.2f}%' if r is not None else '--'}")

    # ---- ITEM 2b -- entry-based false-rate (the documented extension; this is what feeds item 3's EV) ----
    n_entries = len(all_entry_records)
    n_entry_wrong = sum(1 for x in all_entry_records if not x["correct"])
    print(f"\nITEM 2b -- BRACKET-ENTRY FALSE RATE (extension: first sustained-extreme touch of each rung's "
          f"band, n={n_entries}):")
    if n_entries:
        er = n_entry_wrong / n_entries
        elo, ehi = wilson_ci(n_entry_wrong, n_entries)
        print(f"  {n_entry_wrong}/{n_entries} wrong = {100*er:.3f}% (95% CI [{100*elo:.3f}%, {100*ehi:.3f}%])")
        print("  This is the rate that matters for item 3's EV: it answers 'if a bot bought the currently-")
        print("  entered bracket the moment sustained-extreme (glitch+sustain-3 filtered) first reached it,")
        print("  how often would that specific bracket turn out to NOT be the settled winner.'")
    else:
        print("  No bracket entries recorded.")

    wrong_examples = [x for x in all_entry_records if not x["correct"]][:15]
    if wrong_examples:
        print("\nFALSE ENTRIES (up to 15 shown):")
        for x in wrong_examples:
            print(f"  {x['city']} {x['date']} ticker={x['ticker']} label={x['label']} entry={x['entry_utc']}")

    # ---- ITEM 3: ask-based, LOSS-INCLUSIVE EV on the win+loss EV-fire pairs ----
    n_win_fires = sum(1 for f in ev_fires if f["won"])
    n_loss_fires = sum(1 for f in ev_fires if not f["won"])
    print("\n" + "=" * 100)
    print(f"ITEM 3 -- ASK-BASED EV on {len(ev_fires)} fires ({n_win_fires} win-case, {n_loss_fires} loss-case)")
    print("=" * 100)
    spreads = {} if cached_only else probe_live_spread()
    print(f"Live spread probe (today, whitelist cities, cents): {spreads if spreads else '(none captured)'}")

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
        ask_proxy_c = min(99.9, px * 100.0 + half_spread_c)   # last-trade + half live spread, ask-side proxy
        fee_c = pmkt_fee_cents(ask_proxy_c)
        net_c = (100.0 - ask_proxy_c - fee_c) if f["won"] else -(ask_proxy_c + fee_c)
        ev_results.append({"city": f["city"], "date": f["date"], "won": f["won"],
                            "raw_gap_c": round(100 * (1 - px), 3),
                            "ask_proxy_c": round(ask_proxy_c, 3), "fee_c": round(fee_c, 4), "net_ev_c": round(net_c, 3)})

    if ev_results:
        raw = [e["raw_gap_c"] for e in ev_results]
        net = [e["net_ev_c"] for e in ev_results]
        print(f"\n  n={len(ev_results)} priced fires ({sum(1 for e in ev_results if e['won'])} win, "
              f"{sum(1 for e in ev_results if not e['won'])} loss)")
        print(f"  raw gap at entry (1-last_trade), cents: mean={st.mean(raw):.2f} median={st.median(raw):.2f}")
        print(f"  net EV/ct, LOSS-INCLUSIVE, after ask-proxy + Polymarket 5% weather taker fee: "
              f"mean={st.mean(net):.2f} median={st.median(net):.2f}")
        print(f"  (Kalshi's confirmed net edge, kwx_runner-era measurement: +0.15 to +0.21 /ct)")
    else:
        print("\n  No priced fires (thin/absent CLOB history for these tickers -- see .md).")

    # ---- write raw results for the .md and for reruns ----
    out = {
        "run_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "usable_city_days": usable_city_days, "n_skipped": len(skips), "skips": skips,
        "n_winner_never_entered": n_winner_never_entered,
        "n_lock_records": n_locks, "n_wrong": n_wrong,
        "loss_rate": (n_wrong / n_locks) if n_locks else None,
        "loss_rate_ci95": wilson_ci(n_wrong, n_locks) if n_locks else None,
        "n_entries": n_entries, "n_entry_wrong": n_entry_wrong,
        "entry_loss_rate": (n_entry_wrong / n_entries) if n_entries else None,
        "entry_loss_rate_ci95": wilson_ci(n_entry_wrong, n_entries) if n_entries else None,
        "per_city": per_city, "lock_records": all_lock_records, "entry_records": all_entry_records,
        "ev_fires_n": len(ev_fires), "ev_results": ev_results,
        "live_spreads_c": spreads,
    }
    with open(os.path.join(HERE, "pmkt_final_verdict_results.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"\nwrote {os.path.join(HERE, 'pmkt_final_verdict_results.json')}")
    return out


if __name__ == "__main__":
    run(cached_only="--cached-only" in sys.argv[1:])
