#!/usr/bin/env python3
"""
Backtest B -- independent cross-check of the ensemble-prob-vs-Kalshi edge, with lead sensitivity.

INDEPENDENT of the sibling backtest (bt_ens1 in the parent wxens/ dir) -- this is a fresh
implementation written without reading that sibling's code or results.

Design (pre-registered before reading VALIDATION-window results):
  - 4 cities (diverse climate): KDEN (semi-arid continental), KMIA (tropical), KSEA (marine),
    KPHX (desert). HIGH-temp series only (KXHIGH*). LOW series and other 16 cities out of scope
    for this cross-check (documented limitation, not cherry-picked -- chosen for climate diversity
    before any data was pulled).
  - Two leads, both from Open-Meteo's `previous-runs-api` (a genuine archived-forecast-run product,
    NOT reanalysis -- see NOTE below on why the `ensemble-api` historical path was abandoned):
      * "dayahead"   = temperature_2m_previous_day1 (~24h lead: the run that was ~24h old at each
                        valid hour). Simulated entry: previous local evening 21:00.
      * "samemorning"= temperature_2m_previous_day0 (freshest run available at each valid hour,
                        ~0-9h lead for afternoon peak hours). Simulated entry: same day 09:00 local.
    Entry timestamps are always BEFORE the observed daily high/settlement by construction, and the
    previous_dayN archive is a genuine historical forecast-run product (issue-time tagged), not a
    reanalysis/truth series -- so no look-ahead.
  - FIT window: 2026-04-24 .. 2026-05-31 (used ONLY to fit a per-city, per-lead bias + residual sigma
    against ERA5 truth; NEVER touches Kalshi prices or trade decisions).
  - VALIDATION (OOS) window: 2026-06-01 .. 2026-07-20 (strictly after FIT, no overlap). This is where
    the Kalshi trading simulation and edge test run.
  - Model probability: Gaussian(mean = previous_dayN forecast + FIT-window bias, sigma = FIT-window
    residual std), continuity-corrected, evaluated against each market's floor/cap strike bucket.
  - Entry price: the REAL trade closest at-or-after the simulated entry timestamp, pulled from the
    Kalshi trade tape (yes_price_dollars) via /markets/trades with min_ts/max_ts -- not mid, not last.
  - Fee: ceil(7*p*(1-p))/100 per contract at the entry price (house formula).
  - Settlement: market.result ('yes'/'no'), both sides accounted (NO payoff = 100 - no_price).
  - Day-clustered by settlement date (all 4 cities on the same calendar day are correlated through
    synoptic-scale weather).

NOTE on why previous-runs-api (deterministic + fitted spread) instead of raw ensemble members:
  Empirically verified 2026-07-23: the `ensemble-api.open-meteo.com` "historical" path
  (start_date/end_date in the past) returns ALL-NULL for every ensemble member (ecmwf_ifs025,
  gfs_seamless, icon_seamless, gem_global, ecmwf_aifs025, ukmo_global_ensemble_20km all tested) for
  any date older than ~92 HOURS before the request time, regardless of `past_days` requested (tested
  1..100). This contradicts the informal note this task started from ("historical ensemble ... works,
  confirmed"), which was apparently only ever tested against the live/near-term window. True
  multi-member ensemble history is NOT available via this free API beyond ~3.8 days back -- too short
  for any day-clustered OOS test. `previous-runs-api` IS a genuine, longer-archived (>90 days),
  lead-tagged forecast-run product, so it is used instead, with the ensemble's probabilistic character
  reconstructed via a fitted Gaussian (bias + residual sigma from the FIT window) rather than true
  member spread. This is flagged again in the self-doubt section of the results.
"""
import json, math, os, sys, time, ssl, urllib.request, urllib.error, datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
CA = "/root/.ccr/ca-bundle.crt"
CTX = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"

# ---- scope: 4 cities, HIGH series only ----
# (station ICAO, lat, lon, fixed STANDARD-time UTC offset [house convention: never DST])
CITIES = {
    "KXHIGHDEN": ("KDEN", 39.8617, -104.6731, -7, "America/Denver"),
    "KXHIGHMIA": ("KMIA", 25.7959, -80.2870, -5, "America/New_York"),
    "KXHIGHTSEA": ("KSEA", 47.4502, -122.3088, -8, "America/Los_Angeles"),
    "KXHIGHTPHX": ("KPHX", 33.4342, -112.0116, -7, "America/Phoenix"),
}

FIT_START = dt.date(2026, 4, 24)
FIT_END = dt.date(2026, 5, 31)
VAL_START = dt.date(2026, 6, 1)
VAL_END = dt.date(2026, 7, 20)

MONTHS = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)

def event_ticker(series, d):
    return f"{series}-{d.year % 100:02d}{MONTHS[d.month]}{d.day:02d}"

# ---------------- HTTP helpers ----------------
def _get(url, timeout=30, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as h:
                return json.loads(h.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if i == retries - 1:
                return {"__error__": str(e)}
            time.sleep(0.5 * (i + 1))
        except Exception as e:
            if i == retries - 1:
                return {"__error__": str(e)}
            time.sleep(0.5 * (i + 1))
    return {"__error__": "exhausted"}

def kalshi_api(path):
    return _get(KBASE + path)

# ---------------- 1. forecast (previous-runs-api) ----------------
def fetch_forecast(series, station):
    _, lat, lon, off, tz = CITIES[series]
    url = (f"https://previous-runs-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&models=ecmwf_ifs025&hourly=temperature_2m,temperature_2m_previous_day0,"
           f"temperature_2m_previous_day1&past_days=95&forecast_days=1"
           f"&temperature_unit=fahrenheit&timezone={urllib.parse.quote(tz)}")
    d = _get(url)
    return d

# ---------------- 2. ERA5 truth (archive-api) ----------------
def fetch_era5(series):
    _, lat, lon, off, tz = CITIES[series]
    url = (f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
           f"&start_date={FIT_START.isoformat()}&end_date={VAL_END.isoformat()}"
           f"&daily=temperature_2m_max&temperature_unit=fahrenheit&timezone={urllib.parse.quote(tz)}")
    d = _get(url)
    return d

import urllib.parse

def main():
    os.makedirs(HERE, exist_ok=True)

    print("== fetching forecast + ERA5 per city ==", file=sys.stderr)
    fc_cache, era5_cache = {}, {}
    for series in CITIES:
        fc_cache[series] = fetch_forecast(series, CITIES[series][0])
        era5_cache[series] = fetch_era5(series)
        print(series, "forecast err?", fc_cache[series].get("__error__") if fc_cache[series] else "NONE",
              "era5 err?", era5_cache[series].get("__error__") if era5_cache[series] else "NONE",
              file=sys.stderr)
    json.dump(fc_cache, open(os.path.join(HERE, "raw_forecast.json"), "w"))
    json.dump(era5_cache, open(os.path.join(HERE, "raw_era5.json"), "w"))

    print("== fetching Kalshi events (FIT+VALIDATION range) ==", file=sys.stderr)
    all_days = list(daterange(FIT_START, VAL_END))
    tasks = [(series, d) for series in CITIES for d in all_days]

    def fetch_event(args):
        series, d = args
        tk = event_ticker(series, d)
        r = kalshi_api(f"/events/{tk}?with_nested_markets=true")
        return (series, d.isoformat(), r)

    events = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(fetch_event, t) for t in tasks]
        n_done = 0
        for f in as_completed(futs):
            series, dstr, r = f.result()
            events.setdefault(series, {})[dstr] = r
            n_done += 1
            if n_done % 50 == 0:
                print(f"  events: {n_done}/{len(tasks)}", file=sys.stderr)
    json.dump(events, open(os.path.join(HERE, "raw_events.json"), "w"))
    print("done events fetch", file=sys.stderr)

if __name__ == "__main__":
    main()
