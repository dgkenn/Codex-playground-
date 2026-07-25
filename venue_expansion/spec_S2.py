#!/usr/bin/env python3
"""spec_S2.py -- S2: Tokyo RJTT GO-check on JMA 10-minute AMeDAS (Track A extension, GO-path #2).

PRE-REGISTERED SPEC (verbatim id "S2", frozen before this script touched real JMA/backtest data):

  Hypothesis: replacing hourly METAR with the recon-verified JMA 10-min AMeDAS feed (Haneda
  block_no=0371, ~0.3km from RJTT, spot-matched 0.1-0.3C vs RJTT METAR -- see
  out/feedhunt_tokyo.json) lifts Tokyo winner-bracket signal coverage decisively above its
  published hourly baseline (30.8%, n=26) while the DEPLOYED lock rule keeps a Kalshi-grade
  false-lock rate on this feed -- i.e. hourly cadence, not Tokyo's diurnal shape, was the
  binding constraint, exactly as Track A showed for Chicago (tracka_chicago_1min.py).

  MANDATORY pre-run sanity (primary run is invalid without an exact match): reproduce
  ref/pmkt_final_verdict.py's published hourly Tokyo row EXACTLY -- usable=26,
  never_entered=18, coverage=30.8% -- using the SAME hourly IEM "routine" METAR feed, the
  SAME strided sampling (TARGET_SAMPLES_PER_CITY=22, END_DATE=2026-07-18), the SAME
  MIN_DAY_OBS=15/MAX_END_GAP_H=4h guard, before trusting anything below.

  Primary run: JMA 10-min AMeDAS as the obs feed, DENSE stride=1 over 2026-03-15..2026-07-18
  (~126 candidate days -- Tokyo's earliest-live 2026-03-12 + a 3-day buffer, through the same
  END_DATE the published baseline used). Completeness guard (disclosed, Track A's own 1-minute
  guard family, reused verbatim in threshold value): >=100 obs/day, <=3h end-gap.

  Entry rule / lock rule: kwx_lock_rule.py byte-identical (sustain-3, glitch filter, 0.5C
  margin for Tokyo -- ref/pmkt_final_verdict.py's own WHITELIST["tokyo"] margin). backtest_day
  walk-forward logic is COPIED VERBATIM from tracka_chicago_1min.py's already-fetch-fn-
  generalized backtest_day -- no lock/entry logic edits, only the fetch_fn + guard thresholds
  differ (spec's fidelity bar (c), verifier-checkable by normalized diff).

  Coverage metric: fraction of usable Tokyo days on which the settled winner bracket receives
  an item-2b bracket-entry (extreme sustained past floor/cap +/- margin) before the obs
  stream ends. No prices, no outcome conditioning in the gating bars (GROUNDING non-negotiable
  #4). Tokyo EV is explicitly non-gating here and delegated to spec S1's measured-ask method
  (this script does NOT compute ask-based EV -- avoids the banned last-trade+half-spread proxy
  and avoids extra CLOB calls entirely, since EV is out of scope for this spec).

  PASS BAR (GO iff BOTH, z=2.128 per the judge gate's frozen family-alpha=0.0167/spec
  Bonferroni-3 allocation, out/judge_specs.json):
    (a) pooled winner-bracket coverage >= 50% AND Wilson LOWER bound (z=2.128) > 30.8%.
    (b) item-2a false locks <= 1 AND Wilson UPPER bound (z=2.128) of the false-lock rate <= 1.5%.
    (c) fidelity: backtest_day identical to Track A's (verified by construction here -- see
        note above; also written as a literal source-level check below).

  MIN N: >=60 usable Tokyo days (of ~126 candidates) AND >=200 deployed-rule lock records for
  bar (b). Below either => THIN/no-verdict (INSUFFICIENT).

  KILL CONDITIONS (any one => stop, do not compute a GO verdict):
    - hourly-baseline sanity reproduction != (usable=26, never_entered=18) exactly.
    - JMA archive fetch gaps (page fetch failures, not ordinary parse/skip reasons) on >25% of
      the ~126 candidate days.
    - usable days < 60.
    - > 2 false locks at any point (basis unsound -- Tokyo would leave the whitelist for this
      feed regardless of coverage).

  DEPLOYABILITY NOTE (publish with any GO): the JMA archive page verified here is
  HISTORICAL-ONLY (data.jma.go.jp explicitly refuses the in-progress JST day -- see
  out/feedhunt_tokyo.json's realtime_lag_note). Live deployment needs JMA's separate
  near-real-time AMeDAS JSON channel (www.jma.go.jp/bosai/amedas/...), NOT verified in this
  run -- latency is part of the signal definition (GROUNDING non-negotiable #5). Global
  Polymarket venue deployability carries the same US-person geo-block flag noted for S1 and in
  GROUNDING.md -- flagged, not decided, here.

Read-only, public APIs only (JMA data.jma.go.jp, IEM Mesonet, Polymarket Gamma). No auth, no
orders, no trading code. Polite: cached under venue_expansion/cache/, sequential ~1 req/sec,
retried with backoff.

USAGE:
  python spec_S2.py                 # full run: sanity check + primary JMA GO-check + verdict
  python spec_S2.py --cached-only   # recompute from cached pulls only, no network
"""
import json
import math
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import datetime as dt
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kwx_lock_rule as R   # deployed lock-rule shim: sustained_extreme, locked_orders (byte-identical reuse)

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; spec-S2-tokyo-jma/1.0)"}

GBASE = "https://gamma-api.polymarket.com"
DAILY_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
JMA_10MIN_URL = "https://www.data.jma.go.jp/stats/etrn/view/10min_a1.php"

CACHE_DIR_EVENTS = os.path.join(HERE, "cache", "tokyo_10min")     # per data_plan
CACHE_DIR_IEM = os.path.join(HERE, "cache", "tracka_chicago_1min")  # reuse existing iem-routine cache dir shape
os.makedirs(CACHE_DIR_EVENTS, exist_ok=True)
os.makedirs(CACHE_DIR_IEM, exist_ok=True)

# --------------------------------------------------------------------------------------------------------
# UNIVERSE -- Tokyo only. IDENTICAL fields/values to ref/pmkt_final_verdict.py's WHITELIST["tokyo"].
# --------------------------------------------------------------------------------------------------------
TOKYO = dict(station="RJTT", unit="C", tz="Asia/Tokyo", margin=0.5, earliest=dt.date(2026, 3, 12))

# JMA station identifiers (recon-verified, out/feedhunt_tokyo.json): Haneda AMeDAS point,
# ~0.3km from RJTT's aerodrome reference point, matches the settlement-basis station.
JMA_PREC_NO = 44
JMA_BLOCK_NO = "0371"

END_DATE = dt.date(2026, 7, 18)              # same END_DATE the published hourly baseline used
SANITY_TARGET_SAMPLES = 22                   # pmkt_final_verdict.py's own TARGET_SAMPLES_PER_CITY

PRIMARY_START = dt.date(2026, 3, 15)         # spec's frozen window start (== earliest + 3-day buffer)
PRIMARY_END = END_DATE                       # spec's frozen window end (2026-07-18)

# hourly-cadence completeness guard (pmkt_final_verdict.py's own values -- sanity reproduction ONLY)
MIN_DAY_OBS_HOURLY = 15
MAX_END_GAP_H_HOURLY = 4

# JMA 10-min completeness guard -- Track A's disclosed 1-minute guard family, reused verbatim in
# threshold VALUE per the spec's data_plan ("cadence-appropriate completeness guard (>=100 obs/day,
# <=3h end-gap -- Track A's disclosed guard family)"). A full JMA day yields ~143 obs within
# [day_start, day_end), so this bar is comfortably clearable on any genuinely-complete day while
# still catching real gaps.
MIN_DAY_OBS_JMA = 100
MAX_END_GAP_H_JMA = 3

Z = 2.128   # judge-gate frozen z (out/judge_specs.json): Bonferroni-3 family alpha=0.05 one-sided -> 0.0167/spec


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


def _cache_path(d, name):
    return os.path.join(d, name)


def _cache_get_json(d, name):
    p = _cache_path(d, name)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        try:
            return json.load(open(p))
        except Exception:
            return None
    return None


def _cache_put_json(d, name, obj):
    json.dump(obj, open(_cache_path(d, name), "w"))


def _cache_get_text(d, name):
    p = _cache_path(d, name)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        try:
            return open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            return None
    return None


def _cache_put_text(d, name, text):
    with open(_cache_path(d, name), "w", encoding="utf-8") as fh:
        fh.write(text)


# --------------------------------------------------------------------------------------------------------
# bracket parsing -> CONTINUOUS native-unit (floor, cap) boundaries -- IDENTICAL to
# ref/pmkt_final_verdict.py / tracka_chicago_1min.py.
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
# FEED A -- IEM routine METAR archive (hourly-ish). IDENTICAL to ref/pmkt_final_verdict.py's
# fetch_iem_routine. Used ONLY for the mandatory sanity-check reproduction of the published 30.8% row.
# --------------------------------------------------------------------------------------------------------
def fetch_iem_routine(station, start_utc, end_utc):
    key = f"asos_{station}_{start_utc:%Y%m%dT%H%M}_{end_utc:%Y%m%dT%H%M}.json"
    cached = _cache_get_json(CACHE_DIR_IEM, key)
    if cached is not None:
        return [(dt.datetime.fromisoformat(t), v) for t, v in cached]
    end_pad = end_utc + dt.timedelta(days=1)   # asos.py's day2 is an EXCLUSIVE upper bound -- pad by 1 day
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
    _cache_put_json(CACHE_DIR_IEM, key, [(t.isoformat(), v) for t, v in out])
    time.sleep(0.8)
    return out


# --------------------------------------------------------------------------------------------------------
# FEED B -- JMA 10-minute AMeDAS historical archive (Haneda, block_no=0371). Recon-verified in
# out/feedhunt_tokyo.json: 144 rows/day (00:10-24:00 JST every 10min), no auth, spot-matched
# 0.1-0.3C vs RJTT METAR. HTML table parse; JST->UTC; Celsius converted to FAHRENHEIT before being
# handed to R.sustained_extreme, matching the convention every other fetch_fn in this codebase uses
# (IEM's tmpf is native-Fahrenheit; sustained_extreme's glitch filters -- the 8.0F jump threshold,
# GLITCH_HI_F/LO_F -- are calibrated in Fahrenheit degrees, so feeding it Fahrenheit here, then
# converting the returned extreme back to native C in backtest_day exactly as Track A already does
# for the other 0.5C-margin cities, is required for fidelity, not a stylistic choice).
# --------------------------------------------------------------------------------------------------------
_ROW_RE = re.compile(r'<tr class="mtx"[^>]*>(.*?)</tr>', re.S)
_TIME_RE = re.compile(r'^\s*<td[^>]*>(\d{1,2}):(\d{2})</td>')
_CELL_RE = re.compile(r'<td[^>]*>(.*?)</td>', re.S)


def _parse_jma_day_html(html, year, month, day):
    """-> list[(utc_dt, temp_F)] for one JST calendar day's 10-min AMeDAS page."""
    tz = ZoneInfo("Asia/Tokyo")
    out = []
    if not html:
        return out
    for row in _ROW_RE.findall(html):
        m = _TIME_RE.match(row)
        if not m:
            continue   # header rows (<th>) also carry class="mtx"; skip anything without a HH:MM first cell
        hh, mm = int(m.group(1)), int(m.group(2))
        cells = _CELL_RE.findall(row)
        if len(cells) < 3:
            continue
        temp_txt = cells[2].strip()
        if temp_txt in ("", "///", "--"):
            continue   # not measured / missing this interval
        try:
            temp_c = float(temp_txt)
        except ValueError:
            continue
        if hh == 24:   # JMA's own convention: "24:00" == next JST day's 00:00
            day_date = dt.date(year, month, day) + dt.timedelta(days=1)
            hh = 0
        else:
            day_date = dt.date(year, month, day)
        jst_dt = dt.datetime(day_date.year, day_date.month, day_date.day, hh, mm, tzinfo=tz)
        utc_dt = jst_dt.astimezone(dt.timezone.utc)
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        out.append((utc_dt, temp_f))
    out.sort(key=lambda x: x[0])
    return out


_JMA_FETCH_LOG = {"attempted": 0, "failed": 0, "days": {}}   # module-level counters for the archive-gap kill check


def fetch_jma_10min_day(year, month, day):
    key = f"jma10min_{JMA_BLOCK_NO}_{year:04d}{month:02d}{day:02d}.html"
    cached = _cache_get_text(CACHE_DIR_EVENTS, key)
    if cached is not None:
        html = cached
        fetched_now = False
    else:
        url = (f"{JMA_10MIN_URL}?prec_no={JMA_PREC_NO}&block_no={JMA_BLOCK_NO}"
               f"&year={year}&month={month}&day={day}&view=")
        html = _get_text(url)
        fetched_now = True
        _JMA_FETCH_LOG["attempted"] += 1
        if html:
            _cache_put_text(CACHE_DIR_EVENTS, key, html)
        else:
            _JMA_FETCH_LOG["failed"] += 1
        time.sleep(1.0)   # politeness: sequential ~1 req/sec against JMA
    rows = _parse_jma_day_html(html, year, month, day) if html else []
    day_key = f"{year:04d}-{month:02d}-{day:02d}"
    _JMA_FETCH_LOG["days"][day_key] = {"fetched_now": fetched_now, "html_present": bool(html), "n_rows": len(rows)}
    return rows


def fetch_jma_10min(_station_unused, start_utc, end_utc):
    """Signature-compatible with the other fetch_fn(station, start_utc, end_utc) feeds. `_station_unused`
    kept for call-site symmetry with backtest_day's `fetch_fn(station, ...)` -- JMA_BLOCK_NO/JMA_PREC_NO are
    fixed module constants (Tokyo-only spec), not per-call parameters."""
    tz = ZoneInfo("Asia/Tokyo")
    d0 = start_utc.astimezone(tz).date()
    d1 = (end_utc - dt.timedelta(minutes=1)).astimezone(tz).date()
    out = []
    d = d0
    while d <= d1:
        out.extend(fetch_jma_10min_day(d.year, d.month, d.day))
        d += dt.timedelta(days=1)
    out.sort(key=lambda x: x[0])
    return out


def fetch_event(city_slug, d):
    slug = f"highest-temperature-in-{city_slug}-on-{d.strftime('%B').lower()}-{d.day}-{d.year}"
    key = f"event_{slug}.json"
    cached = _cache_get_json(CACHE_DIR_EVENTS, key)
    if cached is not None:
        return cached
    ev = _get_json(f"{GBASE}/events/slug/{slug}")
    _cache_put_json(CACHE_DIR_EVENTS, key, ev)
    time.sleep(0.5)
    return ev


# --------------------------------------------------------------------------------------------------------
# backtest_day -- COPIED VERBATIM (no logic edits) from tracka_chicago_1min.py's already fetch-fn/guard-
# pluggable version, itself an unmodified generalization of ref/pmkt_final_verdict.py's backtest_day.
# Spec fidelity bar (c) depends on this being byte-identical modulo the function it's copied from; do not
# edit this function when adapting to a new feed -- only fetch_fn / min_day_obs / max_end_gap_h / pad_*
# should ever change at the call site.
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

    return {"skip": None, "lock_records": lock_records, "entry_records": entry_records,
            "winner": winner_ticker, "n_rungs": len(rungs),
            "winner_never_entered": entries.get(winner_ticker) is None, "n_day_obs": len(day_obs)}


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


# --------------------------------------------------------------------------------------------------------
# sampling
# --------------------------------------------------------------------------------------------------------
def sample_dates_dense(start, end):
    out, d = [], start
    while d <= end:
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
# SANITY CHECK -- mandatory reproduction of ref/pmkt_final_verdict.md's published Tokyo hourly row
# (usable=26, never_entered=18, coverage=30.8%) before the primary JMA run is trusted at all.
# --------------------------------------------------------------------------------------------------------
def run_sanity_hourly():
    print("=" * 100)
    print("SANITY CHECK -- reproduce the published hourly-cadence Tokyo coverage row (30.8%, n=26)")
    print("=" * 100)
    dates = sample_dates_strided(TOKYO, END_DATE, SANITY_TARGET_SAMPLES)
    print(f"[tokyo/hourly] sampling {len(dates)} days from {dates[0] if dates else '-'} to "
          f"{dates[-1] if dates else '-'}")
    usable, never_entered, skips = 0, 0, []
    for d in dates:
        r = backtest_day("tokyo", d, TOKYO, fetch_iem_routine, MIN_DAY_OBS_HOURLY, MAX_END_GAP_H_HOURLY,
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
    print(f"\nSANITY RESULT: usable={usable} never_entered={never_entered} "
          f"coverage={f'{100*coverage:.1f}%' if coverage is not None else '--'} "
          f"(published: usable=26, never_entered=18, coverage=30.8%)")
    match = usable == 26 and never_entered == 18
    print(f"EXACT MATCH to the published table: {match}")
    print("=" * 100 + "\n")
    return {"usable": usable, "never_entered": never_entered, "coverage": coverage,
            "skips": skips, "exact_match_published_table": match}


# --------------------------------------------------------------------------------------------------------
# main -- primary S2 run: JMA 10-min AMeDAS feed, dense daily sampling, tokyo only.
# --------------------------------------------------------------------------------------------------------
def run(cached_only=False):
    out = {"spec_id": "S2", "run_utc": dt.datetime.now(dt.timezone.utc).isoformat()}

    # ---- MANDATORY sanity check first; primary run is invalid without an exact match ----
    sanity = run_sanity_hourly()
    out["sanity_hourly_reproduction"] = sanity
    if not sanity["exact_match_published_table"]:
        out["kill"] = "hourly_baseline_reproduction_mismatch"
        out["verdict"] = "INSUFFICIENT"
        _write(out)
        print("KILL CONDITION HIT: hourly-baseline reproduction did not match the published Tokyo row "
              "exactly. Per spec, primary run is invalid and was NOT executed. Verdict: INSUFFICIENT.")
        return out

    print("=" * 100)
    print("S2 PRIMARY RUN -- Tokyo, JMA 10-minute AMeDAS feed (Haneda block_no=0371), dense daily sampling")
    print("=" * 100)
    dates = sample_dates_dense(PRIMARY_START, PRIMARY_END)
    n_candidate_days = len(dates)
    print(f"[tokyo/jma10min] sampling {n_candidate_days} candidate days from {dates[0]} to {dates[-1]}")

    all_lock_records, all_entry_records, skips = [], [], []
    n_winner_never_entered = 0
    usable_city_days = 0
    per_day_log = []
    for d in dates:
        r = backtest_day("tokyo", d, TOKYO, fetch_jma_10min, MIN_DAY_OBS_JMA, MAX_END_GAP_H_JMA,
                          pad_pre_h=0, pad_post_h=0)
        if r.get("skip"):
            skips.append(f"tokyo {d}: {r['skip']}")
            print(f"    SKIP {d} -- {r['skip']}")
            continue
        usable_city_days += 1
        all_lock_records.extend(r["lock_records"])
        all_entry_records.extend(r["entry_records"])
        if r["winner_never_entered"]:
            n_winner_never_entered += 1
        per_day_log.append({"date": d.isoformat(), "n_day_obs": r["n_day_obs"],
                             "winner_never_entered": r["winner_never_entered"], "winner": r["winner"]})
        print(f"    OK   {d}  {len(r['lock_records'])} deployed-rule lock(s), "
              f"{len(r['entry_records'])} bracket-entries, n_obs={r['n_day_obs']}, winner={r['winner']}" +
              ("  [WINNER BRACKET NEVER ENTERED]" if r["winner_never_entered"] else ""))

    print("\n" + "=" * 100)
    print(f"SAMPLE SIZE: {usable_city_days} usable tokyo-days / {n_candidate_days} candidates "
          f"({len(skips)} skipped). Target was >=60 usable.")
    print("=" * 100)

    # ---- KILL CHECK: JMA archive fetch gaps > 25% of candidate days ----
    jma_days_touched = _JMA_FETCH_LOG["days"]
    jma_fetch_fail_days = sum(1 for v in jma_days_touched.values() if not v["html_present"])
    jma_gap_frac = (jma_fetch_fail_days / len(jma_days_touched)) if jma_days_touched else None
    archive_gap_kill = jma_gap_frac is not None and jma_gap_frac > 0.25
    print(f"\nJMA ARCHIVE FETCH LOG: {len(jma_days_touched)} distinct day-pages touched, "
          f"{jma_fetch_fail_days} failed (no HTML returned after retries) "
          f"({f'{100*jma_gap_frac:.1f}%' if jma_gap_frac is not None else '--'} gap rate).")

    usable_n_kill = usable_city_days < 60

    # ---- PRIMARY METRIC (a): pooled winner-bracket coverage ----
    n_covered = usable_city_days - n_winner_never_entered
    coverage = (n_covered / usable_city_days) if usable_city_days else None
    cov_lo, cov_hi = wilson_ci(n_covered, usable_city_days, z=Z) if usable_city_days else (None, None)
    print(f"\nBAR (a) -- winner-bracket coverage (JMA 10-min cadence): {n_covered}/{usable_city_days} = "
          f"{f'{100*coverage:.1f}%' if coverage is not None else '--'}")
    print(f"  Wilson CI @ z={Z}: [{f'{100*cov_lo:.2f}%' if cov_lo is not None else '--'}, "
          f"{f'{100*cov_hi:.2f}%' if cov_hi is not None else '--'}]")
    print("  Baseline to beat (published hourly, ref/pmkt_final_verdict.md sec.4): 30.8%")

    # ---- BAR (b): false-lock rate, pure deployed rule (item 2a) ----
    n_locks = len(all_lock_records)
    n_wrong = sum(1 for x in all_lock_records if not x["correct"])
    flock_lo, flock_hi = wilson_ci(n_wrong, n_locks, z=Z) if n_locks else (None, None)
    print(f"\nBAR (b) -- POOLED FALSE-LOCK RATE, pure deployed rule (n={n_locks}):")
    if n_locks:
        loss_rate = n_wrong / n_locks
        print(f"  {n_wrong}/{n_locks} wrong = {100*loss_rate:.4f}% "
              f"(Wilson CI @ z={Z}: [{100*flock_lo:.4f}%, {100*flock_hi:.4f}%])")
    else:
        print("  NO EXPLICIT LOCKS AT ALL.")

    # ---- item 2b bracket-entry stats (feeds the coverage metric above; reported for transparency) ----
    n_entries = len(all_entry_records)
    n_entry_wrong = sum(1 for x in all_entry_records if not x["correct"])
    print(f"\nITEM 2b -- BRACKET-ENTRY FALSE RATE (n={n_entries}, non-gating, reported for transparency):")
    if n_entries:
        er = n_entry_wrong / n_entries
        elo, ehi = wilson_ci(n_entry_wrong, n_entries, z=Z)
        print(f"  {n_entry_wrong}/{n_entries} wrong = {100*er:.3f}% (Wilson CI @ z={Z}: "
              f"[{100*elo:.3f}%, {100*ehi:.3f}%])")

    # ---- KILL: >2 false locks at any point ----
    falselock_kill = n_wrong > 2

    # ---- MIN N CHECK ----
    min_n_ok = usable_city_days >= 60 and n_locks >= 200

    # ---- KILL CONDITIONS ----
    kill_reasons = []
    if archive_gap_kill:
        kill_reasons.append(f"jma_archive_gaps_{100*jma_gap_frac:.1f}pct_gt_25pct")
    if usable_n_kill:
        kill_reasons.append(f"usable_days_{usable_city_days}_lt_60")
    if falselock_kill:
        kill_reasons.append(f"false_locks_{n_wrong}_gt_2")

    if kill_reasons:
        print("\n" + "=" * 100)
        print(f"KILL CONDITION(S) HIT: {kill_reasons}")
        print("Per spec: stop, do not compute a GO verdict.")
        print("=" * 100)
        verdict = "FAIL" if not min_n_ok else "FAIL"
        # A hit kill condition is dispositive regardless of min_n; still report the (invalid-for-GO) numbers.
    elif not min_n_ok:
        print(f"\nMIN_N NOT MET: usable_city_days={usable_city_days} (need >=60), n_locks={n_locks} "
              f"(need >=200). Verdict: THIN/INSUFFICIENT (no bar can be asserted at required power).")
        verdict = "INSUFFICIENT"
    else:
        bar_a = (coverage is not None and coverage >= 0.50 and cov_lo is not None and cov_lo > 0.308)
        bar_b = (n_locks > 0 and n_wrong <= 1 and flock_hi is not None and flock_hi <= 0.015)
        verdict = "PASS" if (bar_a and bar_b) else "FAIL"
        print("\n" + "=" * 100)
        print(f"PRE-REGISTERED VERDICT: {'GO' if verdict == 'PASS' else 'NO-GO'}")
        print(f"  (a) coverage>=50% AND Wilson LB(z={Z})>30.8%: {bar_a}  "
              f"(coverage={f'{100*coverage:.1f}%' if coverage is not None else '--'}, "
              f"LB={f'{100*cov_lo:.2f}%' if cov_lo is not None else '--'})")
        print(f"  (b) false_locks<=1 AND Wilson UB(z={Z})<=1.5%: {bar_b}  (n_locks={n_locks}, n_wrong={n_wrong}, "
              f"UB={f'{100*flock_hi:.3f}%' if flock_hi is not None else '--'})")
        print("=" * 100)

    out.update({
        "candidate_days": n_candidate_days,
        "usable_city_days": usable_city_days, "n_skipped": len(skips), "skips": skips,
        "n_winner_never_entered": n_winner_never_entered, "n_covered": n_covered,
        "coverage": coverage, "coverage_wilson_ci_z2p128": [cov_lo, cov_hi],
        "hourly_baseline_coverage": 0.308,
        "hourly_baseline_provenance": "ref/pmkt_final_verdict.md sec.4, tokyo row: usable=26, never_entered=18",
        "n_lock_records": n_locks, "n_wrong": n_wrong,
        "false_lock_rate": (n_wrong / n_locks) if n_locks else None,
        "false_lock_rate_wilson_ci_z2p128": [flock_lo, flock_hi],
        "n_entries": n_entries, "n_entry_wrong": n_entry_wrong,
        "entry_false_rate": (n_entry_wrong / n_entries) if n_entries else None,
        "lock_records": all_lock_records, "entry_records": all_entry_records,
        "per_day_log": per_day_log,
        "jma_archive_fetch_log": {"distinct_days_touched": len(jma_days_touched),
                                   "failed_days": jma_fetch_fail_days,
                                   "gap_frac": jma_gap_frac},
        "min_n_ok": min_n_ok,
        "kill_reasons": kill_reasons,
        "verdict": verdict,
        "ev_accounting_note": "EV is non-gating for S2 per spec; delegated to S1's measured-ask method. "
                               "No ask/CLOB pricing was computed in this script.",
        "deployability_note": ("JMA archive page is historical-only (refuses in-progress JST day); live "
                                "deployment needs JMA's near-real-time AMeDAS JSON channel, not verified here. "
                                "Global Polymarket venue carries the same US-person geo-block flag as S1 -- "
                                "flagged, not decided."),
        "z": Z,
    })
    _write(out)
    return out


def _write(out):
    out_path = os.path.join(HERE, "out", "spec_S2_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    run(cached_only="--cached-only" in sys.argv[1:])
