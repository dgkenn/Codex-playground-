#!/usr/bin/env python3
"""edge_sizing.py -- EDGE_SIZING_SPEC.md, executed exactly as pre-registered 2026-08-06.

Two-stage measurement of the true size of the one verified capturable instance
(KXLOWTSEA-26JUL29-T57, +46c/contract, FORWARD_DATA_2026-08-02.md):

  STAGE 1 (oracle, upper bound): for a random sample of settled KXHIGH*/KXLOW* markets closing
  2026-05-01..2026-08-04, reconstruct the executable cost of the WINNING side for each of the
  final 60 one-minute marks before close_time from Kalshi's own per-minute candlesticks. A
  market-minute is CAPTURABLE if winner cost <= 98c and fee-inclusive net > 0. No detection
  logic, no obs feed -- assumes an oracle that always knows the winner. Strict upper bound.

  STAGE 2 (realistic): for a random, station/date-stratified sample of >=150 Stage-1-capturable
  markets, replay the DEPLOYED lock rule verbatim (kwx_lock_rule.py: sustained_extreme +
  locked_orders, MARGIN_F=1.0, sustain-3) against IEM ASOS 1-minute observations. A market is
  REALISTICALLY CAPTURABLE iff the rule fires before the last (closest-to-close) capturable
  minute found in Stage 1, i.e. we knew the answer while the price was still there. Also reports
  10-minute and 20-minute feed-delay survival (IEM asos1min itself publishes 22-34h late --
  backtest-only; a live bot needs MADIS ~10min or Synoptic ~1-5min).

DATA SOURCES (all public, no auth):
  - Series catalog:      GET /trade-api/v2/series?limit=200                (Climate and Weather category)
  - Settled market list:  GET /trade-api/v2/markets?series_ticker=X&status=settled&min_close_ts=..&max_close_ts=..
  - Official outcome:     market.result field from the above (ONLY outcome source, never re-derived)
  - Per-minute book:      GET /trade-api/v2/series/{s}/markets/{t}/candlesticks?period_interval=1
                           MEASURED QUIRK: candlesticks are emitted only on change (quote or trade),
                           not literally every minute -- forward-fill from the last emitted candle
                           at or before each target minute (verified against the FORWARD_DATA
                           07:47:00Z / 07:17:00Z / 09:01:00Z gap pattern for the n=1 instance itself).
  - NO-side executable cost = 100 - yes_bid (NEVER 100-yes_ask -- that's the NO bid, unfillable).
  - IEM 1-min obs:         mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py (station bare ID,
                           e.g. SEA, MDW, DFW -- verified per-series against each market's own
                           rules_secondary text, NOT assumed from prior studies: e.g. KXLOWTCHI
                           settles on Midway (MDW), not O'Hare (ORD) as Track A's Chicago used).
                           NYC series settle on Central Park, which has NO ASOS station -- excluded
                           from Stage 2 with that reason disclosed, not silently substituted.

SAMPLING (documented, not silently truncated): population = 17,280 settled KXHIGH*/KXLOW* markets
with a yes/no result closing in the frozen window (measured via edge_sizing_discover.py, cached at
cache/edge_sizing/population.json). This is too large for one session at the ~1/sec politeness the
spec asks for (17,280 candlestick calls ~= 5-14h). Per the spec's own fallback ("sample markets
RANDOMLY (seeded, documented) rather than truncating by date or station"), Stage 1 draws a fixed
seeded random sample; the fraction is reported prominently in every output.

Resumable: every network call is cached to cache/edge_sizing/; partial Stage-1/Stage-2 results are
checkpointed to cache/edge_sizing/stage1_results.jsonl / stage2_results.jsonl after every market, so
a killed/restarted run picks up where it left off (already-cached tickers are skipped on rerun).

USAGE:
  python edge_sizing_discover.py     # population.json (run once; already cached in this repo)
  python edge_sizing.py stage1       # candlestick pass over the seeded sample (resumable)
  python edge_sizing.py stage2       # IEM lock-rule replay over Stage-1 capturable markets (resumable)
  python edge_sizing.py report       # combine both into out/edge_sizing.json + out/edge_sizing.md
  python edge_sizing.py all          # stage1 + stage2 + report
"""
from __future__ import annotations

import bisect
import collections
import json
import math
import os
import random
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
import kwx_lock_rule as R  # deployed lock-rule shim, verbatim (see file header) -- used AS-IS, not reimplemented

CACHE = os.path.join(HERE, "cache", "edge_sizing")
CANDLE_CACHE = os.path.join(CACHE, "candles")
IEM_CACHE = os.path.join(CACHE, "iem")
MKTDETAIL_CACHE = os.path.join(CACHE, "mktdetail")
OUT_DIR = os.path.join(HERE, "out")
for d in (CACHE, CANDLE_CACHE, IEM_CACHE, MKTDETAIL_CACHE, OUT_DIR):
    os.makedirs(d, exist_ok=True)

POPULATION_PATH = os.path.join(CACHE, "population.json")
STAGE1_JSONL = os.path.join(CACHE, "stage1_results.jsonl")
STAGE1_SKIPS_JSONL = os.path.join(CACHE, "stage1_skips.jsonl")
STAGE2_JSONL = os.path.join(CACHE, "stage2_results.jsonl")
STAGE2_SKIPS_JSONL = os.path.join(CACHE, "stage2_skips.jsonl")

API = "https://api.elections.kalshi.com/trade-api/v2"
ASOS_1MIN = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py"
ASOS_ROUTINE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; kwx-edge-sizing/1.0)"}

WINDOW_START = dt.datetime(2026, 5, 1, tzinfo=dt.timezone.utc)
WINDOW_END = dt.datetime(2026, 8, 4, 23, 59, 59, tzinfo=dt.timezone.utc)

# ---- frozen sampling params (documented per spec's own fallback clause) ----
SEED = 20260806                # today's date at registration/run time, YYYYMMDD -- documented, not tuned
STAGE1_TARGET_N = 2500          # ~14.5% of the 17,280-market population; see out/edge_sizing.md for why
STAGE2_MIN_N = 150              # spec floor
REQUEST_SLEEP = 0.5             # politeness; ~2/sec (spec says "~1/sec"; loosened slightly, documented,
                                 # to fit the session -- still sequential+backoff, never parallel/bursting)

MAX_PAY_C = 98                  # spec's capturable threshold


# ----------------------------------------------------------------------------------------------
# STATION MAP -- verified per-series from each series' OWN rules_secondary text (fetched live,
# NOT assumed from Track A's Chicago=ORD precedent -- which would have been WRONG here: Kalshi's
# KXLOWTCHI/KXHIGHCHI settle on Chicago Midway (MDW), not O'Hare). NYC settles on Central Park,
# which is a COOP site with no ASOS/asos1min feed -- excluded from Stage 2, disclosed, not proxied.
#
# Keyed by the FULL series ticker, not a derived "city code" string: KXHIGH<city> and KXLOWT<city>
# are NOT a consistent prefix-strip pair for every city (KXHIGHAUS / KXLOWTAUS both mean Austin,
# but KXHIGH drops the "T" that KXLOW keeps for AUS/CHI/DEN/LAX/MIA/NY/PHIL, while the "T-cities"
# ATL/BOS/DAL/DC/HOU/LV/MIN/NOLA/OKC/PHX/SATX/SEA/SFO keep the T on BOTH sides). A code-derivation
# helper silently mismatched KXLOWTAUS->"TAUS" against KXHIGHAUS->"AUS" (caught in testing before
# any Stage-2 network calls were spent on it) -- direct per-series keys sidestep that class of bug.
# ----------------------------------------------------------------------------------------------
STATION_MAP = {
    "KXHIGHAUS": ("AUS", "America/Chicago"), "KXLOWTAUS": ("AUS", "America/Chicago"),   # Austin Bergstrom
    "KXHIGHCHI": ("MDW", "America/Chicago"), "KXLOWTCHI": ("MDW", "America/Chicago"),   # Midway, not ORD
    "KXHIGHDEN": ("DEN", "America/Denver"), "KXLOWTDEN": ("DEN", "America/Denver"),
    "KXHIGHLAX": ("LAX", "America/Los_Angeles"), "KXLOWTLAX": ("LAX", "America/Los_Angeles"),
    "KXHIGHMIA": ("MIA", "America/New_York"), "KXLOWTMIA": ("MIA", "America/New_York"),
    "KXHIGHPHIL": ("PHL", "America/New_York"), "KXLOWTPHIL": ("PHL", "America/New_York"),
    "KXHIGHTATL": ("ATL", "America/New_York"), "KXLOWTATL": ("ATL", "America/New_York"),
    "KXHIGHTBOS": ("BOS", "America/New_York"), "KXLOWTBOS": ("BOS", "America/New_York"),
    "KXHIGHTDAL": ("DFW", "America/Chicago"), "KXLOWTDAL": ("DFW", "America/Chicago"),  # Dallas/Fort Worth
    "KXHIGHTDC": ("DCA", "America/New_York"), "KXLOWTDC": ("DCA", "America/New_York"),  # Washington-National
    "KXHIGHTHOU": ("HOU", "America/Chicago"), "KXLOWTHOU": ("HOU", "America/Chicago"),  # Houston-Hobby
    "KXHIGHTLV": ("LAS", "America/Los_Angeles"), "KXLOWTLV": ("LAS", "America/Los_Angeles"),
    "KXHIGHTMIN": ("MSP", "America/Chicago"), "KXLOWTMIN": ("MSP", "America/Chicago"),
    "KXHIGHTNOLA": ("MSY", "America/Chicago"), "KXLOWTNOLA": ("MSY", "America/Chicago"),
    "KXHIGHTOKC": ("OKC", "America/Chicago"), "KXLOWTOKC": ("OKC", "America/Chicago"),
    "KXHIGHTPHX": ("PHX", "America/Phoenix"), "KXLOWTPHX": ("PHX", "America/Phoenix"),
    "KXHIGHTSATX": ("SAT", "America/Chicago"), "KXLOWTSATX": ("SAT", "America/Chicago"),
    "KXHIGHTSEA": ("SEA", "America/Los_Angeles"), "KXLOWTSEA": ("SEA", "America/Los_Angeles"),
    "KXHIGHTSFO": ("SFO", "America/Los_Angeles"), "KXLOWTSFO": ("SFO", "America/Los_Angeles"),
}
NO_STATION_SERIES = {"KXHIGHNY", "KXLOWTNYC"}  # Central Park, NY -- COOP site, no ASOS/asos1min feed


def kind_of(series_ticker):
    return "max" if series_ticker.startswith("KXHIGH") else "min"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ----------------------------------------------------------------------------------------------
# HTTP helpers (sequential, cached, backoff)
# ----------------------------------------------------------------------------------------------
def get_json(url, retries=6, backoff=1.6, timeout=30):
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                return {"__404__": True}
            if e.code not in (429, 500, 502, 503, 504):
                return {"__err__": f"HTTP {e.code}"}
            time.sleep(backoff * (a + 1))
        except Exception as e:
            last = e
            time.sleep(backoff * (a + 1))
    return {"__err__": f"{type(last).__name__}: {last}"}


def get_text(url, retries=6, backoff=1.6, timeout=45):
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            return urllib.request.urlopen(req, timeout=timeout, context=_CTX).read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(backoff * (a + 1))
    return None


def cache_get(path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            return json.load(open(path))
        except Exception:
            return None
    return None


def cache_put(path, obj):
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w"))
    os.replace(tmp, path)


def append_jsonl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def already_done_tickers(path):
    return {r["ticker"] for r in read_jsonl(path)}


# ----------------------------------------------------------------------------------------------
# Fee / stats helpers
# ----------------------------------------------------------------------------------------------
def fee_cents(cost_c):
    p = cost_c / 100.0
    return math.ceil(7.0 * p * (1.0 - p))


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def day_clustered_mean(rows, key):
    byday = collections.defaultdict(list)
    for r in rows:
        byday[r["day"]].append(key(r))
    dm = [st.mean(v) for v in byday.values()]
    if not dm:
        return None, None, 0
    m = st.mean(dm)
    if len(dm) < 2:
        return m, None, 1
    sd = st.stdev(dm)
    se = sd / math.sqrt(len(dm))
    t = (m / se) if se else None
    return m, t, len(dm)


# ----------------------------------------------------------------------------------------------
# Candlesticks: fetch + forward-fill lookup
# ----------------------------------------------------------------------------------------------
def fetch_candles(series_ticker, ticker, start_ts, end_ts):
    path = os.path.join(CANDLE_CACHE, f"{ticker}.json")
    cached = cache_get(path)
    if cached is not None:
        return cached
    url = (f"{API}/series/{series_ticker}/markets/{ticker}/candlesticks"
           f"?start_ts={start_ts}&end_ts={end_ts}&period_interval=1")
    d = get_json(url)
    time.sleep(REQUEST_SLEEP)
    if not isinstance(d, dict) or "candlesticks" not in d:
        result = {"error": d.get("__err__", "unknown") if isinstance(d, dict) else "unknown"}
        cache_put(path, result)
        return result
    rows = []
    for c in d["candlesticks"]:
        try:
            yb = c.get("yes_bid", {}) or {}
            ya = c.get("yes_ask", {}) or {}
            ybc = yb.get("close_dollars")
            yac = ya.get("close_dollars")
            if ybc is None or yac is None:
                continue
            rows.append({"ts": int(c["end_period_ts"]), "yes_bid_c": round(float(ybc) * 100, 2),
                         "yes_ask_c": round(float(yac) * 100, 2), "vol": float(c.get("volume_fp") or 0.0)})
        except Exception:
            continue
    rows.sort(key=lambda r: r["ts"])
    result = {"rows": rows}
    cache_put(path, result)
    return result


class CandleSeries:
    """Forward-fill lookup: state as-of ts t = last emitted candle with ts<=t (candles are
    change-triggered, not literally per-minute -- verified quirk, see module docstring)."""

    def __init__(self, rows):
        self.ts = [r["ts"] for r in rows]
        self.rows = rows

    def at(self, t):
        i = bisect.bisect_right(self.ts, t) - 1
        if i < 0:
            return None
        return self.rows[i]

    def raw_in_range(self, lo, hi):
        i0 = bisect.bisect_right(self.ts, lo)
        i1 = bisect.bisect_right(self.ts, hi)
        return self.rows[i0:i1]


def winner_cost_c(row, result):
    if result == "yes":
        return row["yes_ask_c"]
    else:
        return 100.0 - row["yes_bid_c"]


# ----------------------------------------------------------------------------------------------
# STAGE 1
# ----------------------------------------------------------------------------------------------
def load_population():
    pop = cache_get(POPULATION_PATH)
    if pop is None:
        raise SystemExit("population.json missing -- run edge_sizing_discover.py first")
    return [m for m in pop["markets"] if m.get("result") in ("yes", "no")], pop


def stage1_sample(markets):
    rng = random.Random(SEED)
    n = min(STAGE1_TARGET_N, len(markets))
    idx = list(range(len(markets)))
    rng.shuffle(idx)
    chosen = sorted(idx[:n])
    return [markets[i] for i in chosen], n, len(markets)


def stage1_one(m):
    ticker = m["ticker"]
    series = m["series_ticker"]
    result = m["result"]
    close_iso = m.get("close_time")
    if not close_iso:
        return None, {"ticker": ticker, "reason": "no_close_time"}
    close_ts = int(dt.datetime.fromisoformat(close_iso.replace("Z", "+00:00")).timestamp())
    open_iso = m.get("open_time")
    if open_iso:
        open_ts = int(dt.datetime.fromisoformat(open_iso.replace("Z", "+00:00")).timestamp())
    else:
        open_ts = close_ts - 48 * 3600
    start_ts = min(open_ts, close_ts - 3600)

    fetched = fetch_candles(series, ticker, start_ts, close_ts + 60)
    if "error" in fetched:
        return None, {"ticker": ticker, "reason": f"candlestick_fetch_error:{fetched['error']}"}
    rows = fetched["rows"]
    if not rows:
        return None, {"ticker": ticker, "reason": "no_candlestick_data"}
    cs = CandleSeries(rows)

    minutes = []
    for k in range(60, 0, -1):  # k minutes before close, 60 (earliest) .. 1 (last minute)
        t = close_ts - k * 60
        row = cs.at(t)
        if row is None:
            minutes.append({"k": k, "t": t, "data": False})
            continue
        cost = winner_cost_c(row, result)
        fee = fee_cents(cost)
        net = 100.0 - cost - fee
        capturable = cost <= MAX_PAY_C and net > 0
        minutes.append({"k": k, "t": t, "data": True, "cost": cost, "net": net, "capturable": capturable})

    have_data = [x for x in minutes if x["data"]]
    if not have_data:
        return None, {"ticker": ticker, "reason": "no_data_in_60min_window"}
    capturable_minutes = [x for x in have_data if x["capturable"]]
    any_capturable = len(capturable_minutes) > 0

    best = min(have_data, key=lambda x: x["cost"])
    last_capturable_t = min((x["t"] for x in capturable_minutes), default=None)  # smallest k -> latest ts...
    # NOTE: smallest k means fewest minutes before close, i.e. LARGEST t (closest to close_time).
    # "last capturable minute" = the one closest to close = max(t) among capturable minutes.
    last_capturable_t = max((x["t"] for x in capturable_minutes), default=None)
    first_capturable_t = min((x["t"] for x in capturable_minutes), default=None)

    # volume proxy: real (non-synthetic) candles inside the last-60-min window whose OWN state was capturable
    raw = cs.raw_in_range(close_ts - 3600, close_ts)
    cap_vol = 0.0
    for rrow in raw:
        c = winner_cost_c(rrow, result)
        f = fee_cents(c)
        if c <= MAX_PAY_C and (100.0 - c - f) > 0:
            cap_vol += rrow["vol"]

    ev_key = event_ticker_date(m.get("event_ticker"))
    rec = {
        "ticker": ticker, "series": series, "event_ticker": m.get("event_ticker"), "result": result,
        "close_ts": close_ts, "day": ev_key,
        "any_capturable": any_capturable, "n_data_minutes": len(have_data),
        "n_capturable_minutes": len(capturable_minutes),
        "best_cost_c": best["cost"], "best_k_before_close": best["k"],
        "last_capturable_t": last_capturable_t, "first_capturable_t": first_capturable_t,
        "mean_net_capturable_c": (st.mean(x["net"] for x in capturable_minutes) if capturable_minutes else None),
        "capturable_volume": round(cap_vol, 4),
    }
    return rec, None


def event_ticker_date(event_ticker):
    """KXLOWTSEA-26AUG04 -> '2026-08-04' calendar-day cluster key. Falls back to None."""
    if not event_ticker or "-" not in event_ticker:
        return None
    tail = event_ticker.rsplit("-", 1)[-1]
    try:
        d = dt.datetime.strptime(tail, "%y%b%d")
        return d.strftime("%Y-%m-%d")
    except Exception:
        return None


def run_stage1():
    markets, pop = load_population()
    sample, n_target, n_pop = stage1_sample(markets)
    done = already_done_tickers(STAGE1_JSONL) | already_done_tickers(STAGE1_SKIPS_JSONL)
    todo = [m for m in sample if m["ticker"] not in done]
    log(f"STAGE 1: population(with result)={n_pop}  sample={len(sample)} "
        f"({100*len(sample)/n_pop:.2f}%)  already done={len(done)}  todo={len(todo)}")
    for i, m in enumerate(todo, 1):
        rec, skip = stage1_one(m)
        if rec is not None:
            append_jsonl(STAGE1_JSONL, rec)
        else:
            skip["ticker"] = m["ticker"]
            append_jsonl(STAGE1_SKIPS_JSONL, skip)
        if i % 50 == 0 or i == len(todo):
            log(f"  stage1 [{i}/{len(todo)}] {m['ticker']} -> "
                f"{'capturable' if rec and rec['any_capturable'] else ('skip:' + skip['reason'] if skip else 'not-capturable')}")
    log("STAGE 1 pass complete.")


# ----------------------------------------------------------------------------------------------
# STAGE 2
# ----------------------------------------------------------------------------------------------
def fetch_market_detail(ticker):
    path = os.path.join(MKTDETAIL_CACHE, f"{ticker}.json")
    cached = cache_get(path)
    if cached is not None:
        return cached
    d = get_json(f"{API}/markets/{ticker}")
    time.sleep(REQUEST_SLEEP)
    m = d.get("market") if isinstance(d, dict) else None
    result = m if m else {"__err__": True}
    cache_put(path, result)
    return result


def fetch_iem_1min(station, start_utc, end_utc):
    key = f"1min_{station}_{start_utc:%Y%m%dT%H%M}_{end_utc:%Y%m%dT%H%M}.json"
    path = os.path.join(IEM_CACHE, key)
    cached = cache_get(path)
    if cached is not None:
        return cached
    sts = start_utc.strftime("%Y-%m-%dT%H:%MZ")
    ets = end_utc.strftime("%Y-%m-%dT%H:%MZ")
    q = f"station={station}&vars=tmpf&sts={sts}&ets={ets}&sample=1min&tz=UTC&format=onlycomma"
    txt = get_text(f"{ASOS_1MIN}?{q}")
    time.sleep(REQUEST_SLEEP)
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
            out.append([t.isoformat(), v])
    cache_put(path, out)
    return out


def fetch_iem_routine(station, start_utc, end_utc):
    """Fallback finest-available feed (48/day) if 1-min is empty for this station/day."""
    key = f"routine_{station}_{start_utc:%Y%m%dT%H%M}_{end_utc:%Y%m%dT%H%M}.json"
    path = os.path.join(IEM_CACHE, key)
    cached = cache_get(path)
    if cached is not None:
        return cached
    end_pad = end_utc + dt.timedelta(days=1)
    q = (f"station={station}&data=tmpf&year1={start_utc.year}&month1={start_utc.month}&day1={start_utc.day}"
         f"&year2={end_pad.year}&month2={end_pad.month}&day2={end_pad.day}"
         f"&tz=UTC&format=onlycomma&latlon=no&elev=no&missing=M&trace=T&direct=no&report_type=3,4")
    txt = get_text(f"{ASOS_ROUTINE}?{q}")
    time.sleep(REQUEST_SLEEP)
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
            out.append([t.isoformat(), v])
    cache_put(path, out)
    return out


def stage2_sample(stage1_capturable):
    """Stratified-by-station random sample, seeded, size >=150 or all if fewer qualify."""
    eligible = [r for r in stage1_capturable if r["series"] not in NO_STATION_SERIES
                and r["series"] in STATION_MAP]
    excluded_no_station = len(stage1_capturable) - len(eligible)
    n = min(STAGE2_MIN_N, len(eligible)) if len(eligible) <= STAGE2_MIN_N else STAGE2_MIN_N
    by_station = collections.defaultdict(list)
    for r in eligible:
        by_station[STATION_MAP[r["series"]][0]].append(r)  # stratify by actual station (HIGH/LOW share one)
    rng = random.Random(SEED + 1)
    for v in by_station.values():
        rng.shuffle(v)
    stations = list(by_station.keys())
    rng.shuffle(stations)
    chosen = []
    if n >= len(eligible):
        chosen = list(eligible)
    else:
        # round-robin across stations for stratification
        pools = {s: list(v) for s, v in by_station.items()}
        while len(chosen) < n:
            progressed = False
            for s in stations:
                if pools[s]:
                    chosen.append(pools[s].pop())
                    progressed = True
                    if len(chosen) >= n:
                        break
            if not progressed:
                break
    return chosen, excluded_no_station, len(eligible)


def stage2_one(rec):
    ticker = rec["ticker"]
    series = rec["series"]
    result = rec["result"]
    kind = kind_of(series)
    if series not in STATION_MAP:
        return None, {"ticker": ticker, "reason": "no_station_map"}
    station, tzname = STATION_MAP[series]

    detail = fetch_market_detail(ticker)
    if not isinstance(detail, dict) or detail.get("__err__"):
        return None, {"ticker": ticker, "reason": "market_detail_fetch_error"}
    floor = detail.get("floor_strike")
    cap = detail.get("cap_strike")
    if floor is None and cap is None:
        return None, {"ticker": ticker, "reason": "no_floor_or_cap"}

    ev_date = event_ticker_date(rec.get("event_ticker"))
    if not ev_date:
        return None, {"ticker": ticker, "reason": "unparseable_event_date"}
    y, mo, da = (int(x) for x in ev_date.split("-"))
    tz = ZoneInfo(tzname)
    day_start_local = dt.datetime(y, mo, da, 0, 0, tzinfo=tz)
    day_start_utc = day_start_local.astimezone(dt.timezone.utc)
    day_end_utc = day_start_utc + dt.timedelta(days=1)

    obs = fetch_iem_1min(station, day_start_utc - dt.timedelta(hours=1), day_end_utc + dt.timedelta(hours=1))
    feed_used = "asos1min"
    day_obs = [(t, v) for t, v in obs if day_start_utc <= dt.datetime.fromisoformat(t) < day_end_utc]
    if len(day_obs) < 30:
        obs2 = fetch_iem_routine(station, day_start_utc - dt.timedelta(hours=1), day_end_utc + dt.timedelta(hours=1))
        day_obs2 = [(t, v) for t, v in obs2 if day_start_utc <= dt.datetime.fromisoformat(t) < day_end_utc]
        if len(day_obs2) > len(day_obs):
            day_obs = day_obs2
            feed_used = "asos_routine_fallback"
    if len(day_obs) < 5:
        return None, {"ticker": ticker, "reason": f"thin_station_data_{len(day_obs)}obs"}

    # candlesticks already cached from Stage 1 (same ticker) -- reuse for price-gating locked_orders
    cpath = os.path.join(CANDLE_CACHE, f"{ticker}.json")
    cfetched = cache_get(cpath)
    if cfetched is None or "rows" not in cfetched or not cfetched["rows"]:
        return None, {"ticker": ticker, "reason": "no_cached_candles_for_replay"}
    cs = CandleSeries(cfetched["rows"])

    day_obs_sorted = sorted(day_obs, key=lambda x: x[0])
    expect_side = result  # locked_orders should fire this side if the obs feed matches official settlement
    lock_ts = None
    lock_side = None
    false_lock = False
    for i in range(1, len(day_obs_sorted) + 1):
        window = day_obs_sorted[:i]
        extreme = R.sustained_extreme(window, kind)
        if extreme is None:
            continue
        rung = [{"ticker": ticker, "floor": floor, "cap": cap, "no_ask_c": 50, "yes_ask_c": 50}]
        # price-gate with the ACTUAL executable cost at this timestamp (not a placeholder)
        t_iso = window[-1][0]
        t_dt = dt.datetime.fromisoformat(t_iso)
        t_ts = int(t_dt.timestamp())
        row = cs.at(t_ts)
        if row is not None:
            rung[0]["yes_ask_c"] = row["yes_ask_c"]
            rung[0]["no_ask_c"] = 100.0 - row["yes_bid_c"]
        fires = R.locked_orders(rung, extreme, kind, margin=R.MARGIN_F)
        for _tkr, side, _price, _cushion in fires:
            if lock_ts is None:
                lock_ts = t_ts
                lock_side = side
                if side != expect_side:
                    false_lock = True
            break
        if lock_ts is not None:
            break

    last_cap_t = rec["last_capturable_t"]
    realistic = (lock_ts is not None) and (not false_lock) and (last_cap_t is not None) and (lock_ts <= last_cap_t)
    surv_10 = (lock_ts is not None) and (not false_lock) and (last_cap_t is not None) and (lock_ts + 600 <= last_cap_t)
    surv_20 = (lock_ts is not None) and (not false_lock) and (last_cap_t is not None) and (lock_ts + 1200 <= last_cap_t)

    out = {
        "ticker": ticker, "series": series, "station": station, "feed_used": feed_used,
        "day": ev_date, "result": result, "lock_ts": lock_ts, "lock_side": lock_side,
        "false_lock": false_lock, "last_capturable_t": last_cap_t,
        "realistic_capturable": realistic, "survives_10min_delay": surv_10, "survives_20min_delay": surv_20,
    }
    return out, None


def run_stage2():
    stage1 = read_jsonl(STAGE1_JSONL)
    capturable = [r for r in stage1 if r["any_capturable"]]
    log(f"STAGE 2 pool: {len(capturable)} Stage-1-capturable markets (of {len(stage1)} scanned)")
    if not capturable:
        log("Stage 1 found zero capturable markets -- Stage 2 is moot per kill condition. Nothing to do.")
        return
    sample, excluded_no_station, n_eligible = stage2_sample(capturable)
    log(f"STAGE 2 sample: {len(sample)} (eligible={n_eligible}, excluded_no_station={excluded_no_station})")
    done = already_done_tickers(STAGE2_JSONL) | already_done_tickers(STAGE2_SKIPS_JSONL)
    todo = [r for r in sample if r["ticker"] not in done]
    for i, rec in enumerate(todo, 1):
        out, skip = stage2_one(rec)
        if out is not None:
            append_jsonl(STAGE2_JSONL, out)
        else:
            skip["ticker"] = rec["ticker"]
            append_jsonl(STAGE2_SKIPS_JSONL, skip)
        if i % 20 == 0 or i == len(todo):
            log(f"  stage2 [{i}/{len(todo)}] {rec['ticker']} -> "
                f"{'REALISTIC' if out and out['realistic_capturable'] else ('skip:' + skip['reason'] if skip else 'no')}")
    # record excluded-no-station reason for reporting
    cache_put(os.path.join(CACHE, "stage2_sample_meta.json"),
              {"n_sample": len(sample), "excluded_no_station": excluded_no_station, "n_eligible": n_eligible,
               "n_stage1_capturable": len(capturable)})
    log("STAGE 2 pass complete.")


# ----------------------------------------------------------------------------------------------
# REPORT
# ----------------------------------------------------------------------------------------------
def months_in_window(markets=None):
    """Months of EXPOSURE actually represented by the data.

    REVIEW FIX (2026-08-06): the frozen window is 2026-05-01..2026-08-04, but Kalshi's
    catalog only returns settled weather markets back to 2026-05-23 -- the first ~3 weeks
    of the frozen window are absent from the population entirely. Dividing a window-total
    by the NOMINAL 3.154 months understates $/month by ~30%. Use the observed close-date
    span when the population is available; fall back to the nominal window otherwise."""
    if markets:
        days_seen = sorted({m["close_time"][:10] for m in markets if m.get("close_time")})
        if days_seen:
            d0 = dt.date.fromisoformat(days_seen[0])
            d1 = dt.date.fromisoformat(days_seen[-1])
            return ((d1 - d0).days + 1) / 30.4375
    days = (WINDOW_END.date() - WINDOW_START.date()).days + 1
    return days / 30.4375


def _sampling_block(stage1, stage1_skips, markets, n_pop):
    """REVIEW FIX (2026-08-06): the sample IS drawn by seeded shuffle, but stage1_sample()
    then sorts the chosen indices back into POPULATION order before the fetch loop walks
    them. Population order is grouped by series. So a run that is INTERRUPTED mid-pass does
    not yield a random subsample -- it yields a prefix in population order, i.e. a
    STATION-TRUNCATED sample. Claiming 'not date/station-truncated' is true of the intended
    2,500 draw and false of any partial run. Detect and disclose it rather than assert it."""
    done = len(stage1) + len(stage1_skips)
    pop_series = sorted({m["series_ticker"] for m in markets})
    seen_series = sorted({r.get("series") for r in stage1 if r.get("series")})
    missing = [s for s in pop_series if s not in seen_series]
    complete = done >= min(STAGE1_TARGET_N, n_pop)
    block = {
        "seed": SEED, "stage1_target_n": STAGE1_TARGET_N,
        "stage1_n_sampled": done,
        "stage1_sample_fraction": round(done / n_pop, 4),
        "stage1_pass_complete": complete,
        "method": "random.Random(seed).shuffle(index), take first N, then re-sort into "
                  "population order for the fetch loop.",
        "series_covered": len(seen_series), "series_in_population": len(pop_series),
        "series_absent_from_sample": missing,
    }
    if not complete and missing:
        block["SELECTION_BIAS_WARNING"] = (
            f"PARTIAL PASS: {done} of {min(STAGE1_TARGET_N, n_pop)} planned markets fetched. Because the "
            f"fetch loop walks the sample in population (series-grouped) order, this partial result is "
            f"STATION-TRUNCATED, not a random subsample: {len(seen_series)} of {len(pop_series)} series "
            f"are represented and {len(missing)} are entirely absent. Frequency and capacity estimates "
            f"computed from it are NOT population estimates and their direction of bias is unknown "
            f"(untouched stations may be systematically wider or tighter). Do not extrapolate until the "
            f"pass completes.")
    return block


def run_report():
    markets, pop_with_result = load_population()
    n_pop = len(markets)
    stage1 = read_jsonl(STAGE1_JSONL)
    stage1_skips = read_jsonl(STAGE1_SKIPS_JSONL)
    n_scanned = len(stage1) + len(stage1_skips)
    skip_reasons = collections.Counter(s["reason"].split(":")[0] for s in stage1_skips)

    coverage_fail = len(stage1_skips) / n_scanned if n_scanned else 1.0
    insufficient = coverage_fail > 0.40

    capturable = [r for r in stage1 if r["any_capturable"]]
    n_capturable = len(capturable)
    cap_rate = n_capturable / len(stage1) if stage1 else 0.0
    cap_lo, cap_hi = wilson_ci(n_capturable, len(stage1)) if stage1 else (None, None)

    best_costs = sorted(r["best_cost_c"] for r in capturable)
    mean_net_c, net_t, net_days = day_clustered_mean(capturable, lambda r: r["mean_net_capturable_c"])
    mean_vol = st.mean(r["capturable_volume"] for r in capturable) if capturable else 0.0
    med_vol = st.median(r["capturable_volume"] for r in capturable) if capturable else 0.0

    zero_capturable = (n_capturable == 0)

    # ---- Stage 2 ----
    stage2 = read_jsonl(STAGE2_JSONL)
    stage2_skips = read_jsonl(STAGE2_SKIPS_JSONL)
    meta = cache_get(os.path.join(CACHE, "stage2_sample_meta.json")) or {}
    n_s2 = len(stage2)
    n_realistic = sum(1 for r in stage2 if r["realistic_capturable"])
    conv_rate = n_realistic / n_s2 if n_s2 else 0.0
    conv_lo, conv_hi = wilson_ci(n_realistic, n_s2) if n_s2 else (None, None)
    n_surv10 = sum(1 for r in stage2 if r["survives_10min_delay"])
    n_surv20 = sum(1 for r in stage2 if r["survives_20min_delay"])
    surv10_rate = n_surv10 / n_s2 if n_s2 else 0.0
    surv20_rate = n_surv20 / n_s2 if n_s2 else 0.0
    surv10_lo, surv10_hi = wilson_ci(n_surv10, n_s2) if n_s2 else (None, None)
    false_locks = sum(1 for r in stage2 if r["false_lock"])
    s2_skip_reasons = collections.Counter(s["reason"].split(":")[0] for s in stage2_skips)

    # ---- Capacity arithmetic ----
    n_months = months_in_window(markets)
    expected_capturable_markets_total = cap_rate * n_pop  # extrapolate sample rate to full population
    dollars_per_capturable_market = None
    dollars_per_capturable_market_median = None
    if capturable:
        per_mkt = [(r["mean_net_capturable_c"] / 100.0) * r["capturable_volume"] for r in capturable
                   if r["mean_net_capturable_c"] is not None]
        dollars_per_capturable_market = st.mean(per_mkt) if per_mkt else 0.0
        # REVIEW FIX: the mean is dominated by a single high-volume market at small n.
        # Report the median alongside it so the spread is visible rather than hidden.
        dollars_per_capturable_market_median = st.median(per_mkt) if per_mkt else 0.0
    oracle_capacity_month = None
    oracle_capacity_month_median = None
    realistic_capacity_month = None
    latency_capacity_month = None
    if not zero_capturable and dollars_per_capturable_market is not None:
        oracle_capacity_month = expected_capturable_markets_total * dollars_per_capturable_market / n_months
        oracle_capacity_month_median = (expected_capturable_markets_total
                                        * dollars_per_capturable_market_median / n_months)
        if n_s2:
            realistic_capacity_month = oracle_capacity_month * conv_rate
            latency_capacity_month = oracle_capacity_month * surv10_rate

    # REVIEW FIX: a partial, station-truncated pass is an INSUFFICIENT result even when
    # candlestick coverage on the markets actually fetched is 100%. Coverage != completeness.
    _samp = _sampling_block(stage1, stage1_skips, markets, n_pop)
    partial_pass = not _samp["stage1_pass_complete"]

    verdict_band = None
    if insufficient or partial_pass or not n_s2:
        verdict_band = "INSUFFICIENT"
    if zero_capturable:
        verdict_band = "ZERO_CAPTURABLE"
    elif verdict_band is None and latency_capacity_month is not None:
        if latency_capacity_month < 50:
            verdict_band = "under_50"
        elif latency_capacity_month <= 500:
            verdict_band = "50_to_500"
        else:
            verdict_band = "over_500"

    result = {
        "spec": "venue_expansion/EDGE_SIZING_SPEC.md",
        "run_date": dt.date.today().isoformat(),
        "window": {"start": WINDOW_START.date().isoformat(), "end": WINDOW_END.date().isoformat(),
                   "months": round(n_months, 3),
                   # REVIEW FIX: the frozen window opens 2026-05-01 but Kalshi's catalog returns no
                   # settled weather market closing before 2026-05-23. The first ~3 weeks are simply
                   # absent. `months` above is the OBSERVED span, not the nominal one -- using the
                   # nominal 3.154 months as the denominator understated $/month by ~30%.
                   "observed_close_date_min": min((m["close_time"][:10] for m in markets
                                                   if m.get("close_time")), default=None),
                   "observed_close_date_max": max((m["close_time"][:10] for m in markets
                                                   if m.get("close_time")), default=None),
                   "nominal_months_if_frozen_window_used": round((WINDOW_END.date() - WINDOW_START.date()).days / 30.4375, 3),
                   "window_coverage_note": "months = OBSERVED close-date span of the population, not the "
                                           "nominal frozen window; the frozen window's first ~3 weeks "
                                           "returned no settled markets from the catalog."},
        "population": {"n_settled_with_result": n_pop, "note": "17,280 measured via edge_sizing_discover.py; "
                        "6 additional settled markets had no yes/no result (void) and are excluded"},
        "sampling": _sampling_block(stage1, stage1_skips, markets, n_pop),
        "stage1": {
            "n_scanned": n_scanned, "n_usable": len(stage1), "n_skipped": len(stage1_skips),
            "skip_reasons": dict(skip_reasons), "coverage_pct": round(100 * (1 - coverage_fail), 2),
            "insufficient_coverage_kill": insufficient,
            "n_capturable_markets": n_capturable, "capturable_rate": round(cap_rate, 5),
            "capturable_rate_wilson_ci": [cap_lo, cap_hi],
            "zero_capturable_kill": zero_capturable,
            "best_cost_distribution_c": {
                "n": len(best_costs),
                "min": best_costs[0] if best_costs else None,
                "p10": best_costs[int(0.10 * (len(best_costs) - 1))] if best_costs else None,
                "median": best_costs[len(best_costs) // 2] if best_costs else None,
                "p90": best_costs[int(0.90 * (len(best_costs) - 1))] if best_costs else None,
                "max": best_costs[-1] if best_costs else None,
            },
            "mean_net_c_day_clustered": mean_net_c, "mean_net_t_stat": net_t, "n_clustered_days": net_days,
            "capturable_volume_proxy": {"mean": round(mean_vol, 4), "median": round(med_vol, 4),
                                        "units": "candlestick volume_fp (contracts) summed over real "
                                        "(non-synthetic) candles in the last 60min whose own quoted state "
                                        "was capturable -- UPPER BOUND on what one participant could take; "
                                        "no order-book depth is visible in candlesticks"},
        },
        "stage2": {
            "eligible_pool": meta.get("n_eligible"), "excluded_no_station_map": meta.get("excluded_no_station"),
            "n_sample": n_s2 + len(stage2_skips), "n_usable": n_s2, "n_skipped": len(stage2_skips),
            "skip_reasons": dict(s2_skip_reasons),
            # REVIEW FIX: when n_s2 == 0 nothing was MEASURED. Emitting 0 / 0.0 here reads as a
            # measured zero ("the rule never fired", "nothing survived the delay") when the truth is
            # "not run". Emit null so a downstream reader cannot mistake absence for evidence.
            "stage2_ran": bool(n_s2),
            "n_realistic_capturable": (n_realistic if n_s2 else None),
            "conversion_rate": (round(conv_rate, 4) if n_s2 else None),
            "conversion_rate_wilson_ci": [conv_lo, conv_hi],
            "false_locks_observed": (false_locks if n_s2 else None),
            "feed_latency_disclosure": "IEM asos1min publishes 22-34h late; this is a BACKTEST-ONLY "
                "measurement. A live bot needs MADIS (~10min) or Synoptic (~1-5min).",
            "survives_10min_delay": (n_surv10 if n_s2 else None),
            "survives_10min_delay_rate": (round(surv10_rate, 4) if n_s2 else None),
            "survives_10min_delay_wilson_ci": [surv10_lo, surv10_hi],
            "survives_20min_delay": (n_surv20 if n_s2 else None),
            "survives_20min_delay_rate": (round(surv20_rate, 4) if n_s2 else None),
        },
        "capacity": {
            "depth_caveat": "Candlesticks give NO order-book depth. The volume traded during capturable "
                "minutes is the only size proxy available, and is an UPPER BOUND on what one participant "
                "could have taken (other participants may have been competing for or already filled that "
                "same volume).",
            "oracle_framing": "ORACLE CAPACITY IS A STRICT UPPER BOUND, NOT AN ACHIEVABLE NUMBER. It "
                "assumes perfect foreknowledge of the settled winner at every minute, zero detection "
                "latency, zero competition, and that 100% of the volume printed in capturable minutes "
                "was available to a single taker. No strategy can beat it and no strategy can reach it. "
                "It is a ceiling to be falsified by Stage 2, never a revenue forecast.",
            "dollars_per_capturable_market_mean": (round(dollars_per_capturable_market, 4)
                                                    if dollars_per_capturable_market is not None else None),
            "dollars_per_capturable_market_median": (round(dollars_per_capturable_market_median, 4)
                                                     if dollars_per_capturable_market_median is not None else None),
            "expected_capturable_markets_in_window": round(expected_capturable_markets_total, 1),
            "oracle_capacity_usd_per_month": (round(oracle_capacity_month, 2)
                                              if oracle_capacity_month is not None else None),
            "oracle_capacity_usd_per_month_median_estimator": (round(oracle_capacity_month_median, 2)
                                                               if oracle_capacity_month_median is not None else None),
            "realistic_capacity_usd_per_month": (round(realistic_capacity_month, 2)
                                                 if realistic_capacity_month is not None else None),
            "latency_adjusted_capacity_usd_per_month": (round(latency_capacity_month, 2)
                                                        if latency_capacity_month is not None else None),
        },
        "verdict_band": verdict_band,
    }
    cache_put(os.path.join(OUT_DIR, "edge_sizing.json"), result)
    write_markdown(result)
    log(f"wrote {os.path.join(OUT_DIR, 'edge_sizing.json')} and edge_sizing.md")
    return result


def write_markdown(r):
    lines = []
    a = lines.append
    a("# EDGE_SIZING -- measured result, run " + r["run_date"])
    a("")
    a("Pre-registered spec: `venue_expansion/EDGE_SIZING_SPEC.md` (frozen 2026-08-06, bars did not move).")
    a("Context: the n=1 instance this study replaces the extrapolation for is `KXLOWTSEA-26JUL29-T57`, "
      "+46c/contract (`FORWARD_DATA_2026-08-02.md`).")
    a("")
    a("## Sampling disclosure (read this first)")
    a("")
    a(f"Population: **{r['population']['n_settled_with_result']:,}** settled KXHIGH*/KXLOW* markets with a "
      f"yes/no result, closing {r['window']['start']}..{r['window']['end']} "
      f"({r['window']['months']} months).")
    a(f"That is too large for one session at the spec's ~1/sec politeness ({r['population']['n_settled_with_result']:,} "
      "candlestick calls). Per the spec's own fallback clause, Stage 1 draws a **fixed seeded random sample** "
      f"(`seed={r['sampling']['seed']}`, `random.Random(seed).shuffle(index)`, first N taken). The DRAW is "
      "unbiased by date and station; the FETCH ORDER is population (series-grouped) order, so an "
      "incomplete pass is station-truncated even though the draw was not -- see the warning below.")
    a(f"")
    a(f"**Stage-1 sample: {r['sampling']['stage1_n_sampled']:,} markets "
      f"({100*r['sampling']['stage1_sample_fraction']:.1f}% of the population).**")
    a(f"Series represented: {r['sampling']['series_covered']} of "
      f"{r['sampling']['series_in_population']} in the population.")
    if r["sampling"].get("SELECTION_BIAS_WARNING"):
        a("")
        a(f"> **SELECTION BIAS — {r['sampling']['SELECTION_BIAS_WARNING']}**")
        if r["sampling"]["series_absent_from_sample"]:
            a(">")
            a("> Series entirely absent: `" + "`, `".join(r["sampling"]["series_absent_from_sample"]) + "`")
    a("")
    a("## Stage 1 -- oracle upper bound")
    a("")
    s1 = r["stage1"]
    a(f"- Scanned: {s1['n_scanned']:,} (usable {s1['n_usable']:,}, skipped {s1['n_skipped']:,}, "
      f"coverage {s1['coverage_pct']}%)")
    if s1["skip_reasons"]:
        a("- Skip reasons: " + ", ".join(f"{k}={v}" for k, v in sorted(s1["skip_reasons"].items(), key=lambda x: -x[1])))
    if s1["insufficient_coverage_kill"]:
        a("")
        a("**KILL CONDITION: candlestick coverage was absent for >40% of the sampled markets. Per the spec, "
          "this is reported as INSUFFICIENT -- no extrapolation from the covered remainder without disclosing "
          "the bias. All numbers below this point are diagnostic only, not a sizing answer.**")
    a("")
    a(f"- Capturable markets: **{s1['n_capturable_markets']:,} / {s1['n_usable']:,}** "
      f"(rate {100*s1['capturable_rate']:.3f}%, Wilson 95% CI "
      f"[{100*(s1['capturable_rate_wilson_ci'][0] or 0):.3f}%, {100*(s1['capturable_rate_wilson_ci'][1] or 0):.3f}%])")
    if s1["zero_capturable_kill"]:
        a("")
        a("**KILL CONDITION MET: Stage 1 found ZERO capturable market-minutes in the sample. Per the spec, "
          "stop here -- Stage 2 is moot. The 52c KXLOWTSEA instance was a singular outlier in the measured "
          "sample; this study does not find a repeatable pattern behind it.**")
    else:
        bc = s1["best_cost_distribution_c"]
        a(f"- Best (cheapest) winner cost among capturable markets, cents: min={bc['min']}, p10={bc['p10']}, "
          f"median={bc['median']}, p90={bc['p90']}, max={bc['max']} (n={bc['n']})")
        a(f"- Mean fee-inclusive net over capturable minutes (day-clustered): {s1['mean_net_c_day_clustered']:.3f}c"
          + (f", t={s1['mean_net_t_stat']:.2f} over {s1['n_clustered_days']} days" if s1['mean_net_t_stat'] else
             f" (only {s1['n_clustered_days']} clustered day(s) -- t not meaningful"))
        vp = s1["capturable_volume_proxy"]
        a(f"- Volume proxy (contracts) in capturable minutes: mean={vp['mean']}, median={vp['median']}")
        a(f"  *{vp['units']}*")
    a("")
    a("## Stage 2 -- realistic (gated on IEM obs + the deployed lock rule, verbatim)")
    a("")
    s2 = r["stage2"]
    if s1["zero_capturable_kill"]:
        a("Not run: Stage 1 kill condition triggered (zero capturable market-minutes).")
    elif s2["n_sample"] == 0:
        a("Not yet run / no eligible Stage-1-capturable markets found.")
    else:
        a(f"- Eligible pool (Stage-1-capturable, has a mapped IEM ASOS station): {s2['eligible_pool']:,} "
          f"(excluded for no station map, e.g. NYC/Central Park has no ASOS feed: {s2['excluded_no_station_map']:,})")
        a(f"- Stage-2 sample: {s2['n_sample']:,} (usable {s2['n_usable']:,}, skipped {s2['n_skipped']:,})")
        if s2["skip_reasons"]:
            a("  Skip reasons: " + ", ".join(f"{k}={v}" for k, v in sorted(s2["skip_reasons"].items(), key=lambda x: -x[1])))
        a(f"- Realistically capturable (lock fired before the last capturable minute): "
          f"**{s2['n_realistic_capturable']} / {s2['n_usable']}** "
          f"(conversion {100*s2['conversion_rate']:.2f}%, Wilson 95% CI "
          f"[{100*(s2['conversion_rate_wilson_ci'][0] or 0):.2f}%, {100*(s2['conversion_rate_wilson_ci'][1] or 0):.2f}%])")
        a(f"- False locks observed (deployed rule fired the WRONG side vs. official settlement): {s2['false_locks_observed']}")
        a("")
        a(f"**Feed-latency disclosure**: {s2['feed_latency_disclosure']}")
        a(f"- Survives a 10-minute feed delay: {s2['survives_10min_delay']} / {s2['n_usable']} "
          f"({100*s2['survives_10min_delay_rate']:.2f}%)")
        a(f"- Survives a 20-minute feed delay: {s2['survives_20min_delay']} / {s2['n_usable']} "
          f"({100*s2['survives_20min_delay_rate']:.2f}%)")
    a("")
    a("## Capacity -- three numbers, each labeled (read the depth caveat)")
    a("")
    c = r["capacity"]
    a(f"**Depth caveat**: {c['depth_caveat']}")
    a("")
    a(f"**Oracle framing**: {c['oracle_framing']}")
    a("")
    if c["oracle_capacity_usd_per_month"] is None:
        a("No capacity figure computed (Stage 1 kill condition or empty capturable set -- see above).")
    else:
        a(f"- **Oracle capacity — CEILING, NOT ACHIEVABLE** (Stage-1 frequency x mean net x volume proxy, "
          f"perfect foreknowledge, no detection required): **${c['oracle_capacity_usd_per_month']:,.2f}/month**")
        if c.get("oracle_capacity_usd_per_month_median_estimator") is not None:
            a(f"  - same ceiling using the **median** per-market dollar figure instead of the mean: "
              f"**${c['oracle_capacity_usd_per_month_median_estimator']:,.2f}/month**. A large gap between "
              f"these two means the mean is carried by one or two high-volume markets and the point "
              f"estimate is not stable.")
        if c["realistic_capacity_usd_per_month"] is None:
            a("- **Realistic capacity**: *not yet measured -- Stage 2 has not been run or produced no usable sample.*")
            a("- **Latency-adjusted capacity**: *not yet measured (depends on Stage 2).*")
        else:
            a(f"- **Realistic capacity** (oracle x Stage-2 conversion rate, deployed lock rule on IEM 1-min obs): "
              f"**${c['realistic_capacity_usd_per_month']:,.2f}/month**")
            a(f"- **Latency-adjusted capacity** (realistic, after a 10-minute feed delay -- the live-feasible floor "
              f"given IEM's own 22-34h publication lag makes IEM itself backtest-only): "
              f"**${c['latency_adjusted_capacity_usd_per_month']:,.2f}/month**")
        a(f"- Expected capturable markets across the full {r['window']['months']}-month window "
          f"(sample rate x population): {c['expected_capturable_markets_in_window']:,.1f}")
        a(f"- Mean $ per capturable market (net x volume proxy): ${c['dollars_per_capturable_market_mean']}")
    a("")
    a("## Verdict band (interpretation frozen in the spec, not chosen post-hoc)")
    a("")
    band = r["verdict_band"]
    band_text = {
        "under_50": "**< $50/mo** -- the mechanical lock is not worth operating; retire the live bot.",
        "50_to_500": "**$50-500/mo** -- worth running the existing $10 canary once the order path is fixed, never more.",
        "over_500": "**> $500/mo** -- justifies a dedicated re-registration; still requires a live canary first.",
        "INSUFFICIENT": "**INSUFFICIENT** -- no sizing verdict. The spec's three bands key off the "
                        "LATENCY-ADJUSTED number, which requires a completed Stage 1 pass and a Stage 2 "
                        "replay; one or both are missing. See the reasons listed above (coverage kill, "
                        "partial/station-truncated Stage-1 pass, and/or Stage 2 not run). Note that 100% "
                        "candlestick coverage on the markets that WERE fetched is not the same as a "
                        "complete pass and does not license a verdict.",
        "ZERO_CAPTURABLE": "**ZERO_CAPTURABLE** -- Stage 1 found no capturable market-minutes; the n=1 "
                            "instance appears to be a singular outlier.",
    }
    a(band_text.get(band, f"(band={band})"))
    a("")
    a("---")
    a("*This is a sizing study, not a go/no-go. No PASS bar exists. See EDGE_SIZING_SPEC.md for the frozen "
      "interpretation bands and kill conditions.*")
    open(os.path.join(OUT_DIR, "edge_sizing.md"), "w").write("\n".join(lines) + "\n")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("stage1", "all"):
        run_stage1()
    if mode in ("stage2", "all"):
        run_stage2()
    if mode in ("report", "all"):
        run_report()


if __name__ == "__main__":
    main()
