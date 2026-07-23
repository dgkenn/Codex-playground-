#!/usr/bin/env python3
"""
BACKTEST A -- ENSEMBLE PROBABILITY vs KALSHI (K-WX research funnel)

For each settled Kalshi weather market (KXHIGH*/KXLOWT*), compute
  ensemble_P = fraction of 50 ECMWF ensemble members (ecmwf_ifs025, open-meteo
               ensemble-api) whose local-day extreme (max for HIGH, min for LOW)
               clears the market's strike.
Signal: enter on Kalshi's side implied by the mispricing when
  |ensemble_P - kalshi_crossing_price| > threshold
at the REAL crossing price (last trade at/before a fixed local entry cutoff, not
mid/last), fee = ceil(7*p*(1-p))/100 at that price, settled against the market's
actual `result`.

DATA CONSTRAINT (see ../recon.md for full recon): open-meteo's ensemble-api only
retains non-null member data for the trailing ~3-4 days from whenever it is queried.
There is no free endpoint anywhere that combines a genuine PAST fixed forecast lead
with member/spread granularity. So this backtest can only be run, right now, against
the ~3 most recent SETTLED Kalshi days for which ensemble-api also has non-null
member data: 2026-07-20, 2026-07-21, 2026-07-22 (2026-07-23 is today / unsettled).
This is a severe, structural sample-size ceiling, not a bug in this script -- see
results.md "biggest self-doubt" for the look-ahead-verifiability caveat this implies.

Pre-registered (BEFORE reading any join output) pass bar, per CLAUDE.md / task spec:
  - mean EV/contract > 0 net of fee
  - day-clustered t >= 3
  - OOS on a later split (fit vs validation)
  - Wilson lower bound on win rate positive
  - primary threshold = 0.08 (8 percentage points of |ensemble_P - kalshi_price|),
    chosen ex ante to match this repo's house convention for a mispricing large
    enough to plausibly clear spread+fee; results also reported swept over
    {0.03,0.05,0.08,0.10,0.15,0.20} for informational EV-vs-threshold reporting only.
"""
import json, math, ssl, subprocess, statistics, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SCRATCH = "/tmp/claude-0/-home-user-Codex-playground-/a1344cbd-0d6d-5d88-b275-43c6164c3448/scratchpad/wxens"
OUTDIR = SCRATCH + "/bt_ens"
CA = "/root/.ccr/ca-bundle.crt"
KBASE = "https://api.elections.kalshi.com/trade-api/v2"

SETTLED_DATES = ["2026-07-20", "2026-07-21", "2026-07-22"]  # only dates w/ BOTH settled
                                                              # Kalshi outcome AND non-null
                                                              # ensemble members (see header)
PRIMARY_THRESH = 0.08
SWEEP_THRESH = [0.03, 0.05, 0.08, 0.10, 0.15, 0.20]
ENTRY_LOCAL_HOUR = 7  # fixed local-clock entry cutoff each settlement morning (07:00
                       # local) -- well before the typical afternoon high, still gives
                       # the market ~17h of open trading (opens prior-day ~14:00 local)

CITY = {
    "KXHIGHDEN": ("KDEN", 39.8617, -104.6731), "KXHIGHMIA": ("KMIA", 25.7959, -80.2870),
    "KXHIGHCHI": ("KMDW", 41.7868, -87.7522), "KXHIGHTBOS": ("KBOS", 42.3656, -71.0096),
    "KXHIGHAUS": ("KAUS", 30.1975, -97.6664), "KXHIGHTSEA": ("KSEA", 47.4502, -122.3088),
    "KXHIGHTSFO": ("KSFO", 37.6213, -122.3790), "KXHIGHTMIN": ("KMSP", 44.8848, -93.2223),
    "KXHIGHTDC": ("KDCA", 38.8512, -77.0402), "KXHIGHTATL": ("KATL", 33.6407, -84.4277),
    "KXHIGHTDAL": ("KDFW", 32.8998, -97.0403), "KXHIGHTSATX": ("KSAT", 29.5337, -98.4698),
    "KXHIGHNY": ("NYC", 40.7794, -73.9632), "KXHIGHTOKC": ("KOKC", 35.3931, -97.6007),
    "KXHIGHTLV": ("KLAS", 36.0840, -115.1537), "KXHIGHTPHX": ("KPHX", 33.4342, -112.0116),
    "KXHIGHTHOU": ("KHOU", 29.6454, -95.2789), "KXHIGHPHIL": ("KPHL", 39.8744, -75.2424),
    "KXHIGHTNOLA": ("KMSY", 29.9934, -90.2580), "KXHIGHLAX": ("KLAX", 33.9416, -118.4085),
}
CITY_LOW_SERIES = {
    "KXHIGHDEN": "KXLOWTDEN", "KXHIGHMIA": "KXLOWTMIA", "KXHIGHCHI": "KXLOWTCHI",
    "KXHIGHTBOS": "KXLOWTBOS", "KXHIGHAUS": "KXLOWTAUS", "KXHIGHTSEA": "KXLOWTSEA",
    "KXHIGHTSFO": "KXLOWTSFO", "KXHIGHTMIN": "KXLOWTMIN", "KXHIGHTDC": "KXLOWTDC",
    "KXHIGHTATL": "KXLOWTATL", "KXHIGHTDAL": "KXLOWTDAL", "KXHIGHTSATX": "KXLOWTSATX",
    "KXHIGHNY": "KXLOWTNYC", "KXHIGHTOKC": "KXLOWTOKC", "KXHIGHTLV": "KXLOWTLV",
    "KXHIGHTPHX": "KXLOWTPHX", "KXHIGHTHOU": "KXLOWTHOU", "KXHIGHPHIL": "KXLOWTPHIL",
    "KXHIGHTNOLA": "KXLOWTNOLA", "KXHIGHLAX": "KXLOWTLAX",
}


def curl_json(url, timeout=25):
    r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), "--cacert", CA, url],
                        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}: {r.stderr[:300]}")
    return json.loads(r.stdout)


def fee_dollars(p):
    return math.ceil(7.0 * p * (1.0 - p)) / 100.0


def c_to_f(c):
    return c * 9.0 / 5.0 + 32.0


def round_nwsF(f):
    # standard round-half-away-from-zero to whole degF, matching NWS CLI convention
    return math.floor(f + 0.5) if f >= 0 else math.ceil(f - 0.5)


# ---------- 1. ensemble members: per city, per local date -> {kind: [50 member extremes F]} ----------
def load_ensemble():
    ens = json.load(open(SCRATCH + "/ens_all20.json"))
    order = list(CITY.keys())
    assert len(ens) == len(order), (len(ens), len(order))
    out = {}  # series -> {date -> {"max": [50 vals F], "min": [50 vals F], "tz": str}
    for series, loc in zip(order, ens):
        tz = loc["timezone"]
        h = loc["hourly"]
        times = h["time"]
        members = [h[f"temperature_2m_member{i:02d}"] for i in range(1, 51)]
        by_date = {}
        for idx, t in enumerate(times):
            date = t[:10]
            by_date.setdefault(date, []).append(idx)
        out[series] = {"tz": tz, "days": {}}
        for date, idxs in by_date.items():
            per_member_max, per_member_min = [], []
            ok = True
            for m in members:
                vals = [m[i] for i in idxs if m[i] is not None]
                if not vals:
                    ok = False
                    break
                per_member_max.append(round_nwsF(c_to_f(max(vals))))
                per_member_min.append(round_nwsF(c_to_f(min(vals))))
            if ok and len(idxs) >= 20:  # require a near-complete local day (>=20/24h)
                out[series]["days"][date] = {"max": per_member_max, "min": per_member_min,
                                              "n_hours": len(idxs)}
    return out


def ensemble_p(members, strike_type, floor_strike, cap_strike):
    n = len(members)
    if strike_type == "greater":
        k = sum(1 for v in members if v > floor_strike)
    elif strike_type == "less":
        k = sum(1 for v in members if v < cap_strike)
    elif strike_type == "between":
        k = sum(1 for v in members if floor_strike <= v <= cap_strike)
    else:
        raise ValueError(strike_type)
    return k / n


# ---------- 2. Kalshi settled markets for the 3 dates, both HIGH and LOW series ----------
def fetch_settled_markets():
    date_tags = {d: "26" + datetime.strptime(d, "%Y-%m-%d").strftime("%b%d").upper() for d in SETTLED_DATES}
    # e.g. 2026-07-20 -> "26JUL20"
    out = []
    all_series = list(CITY.keys()) + list(CITY_LOW_SERIES.values())
    for series in all_series:
        try:
            d = curl_json(f"{KBASE}/markets?series_ticker={series}&status=settled&limit=1000")
        except Exception as e:
            print(f"  WARN fetch {series}: {e}", file=sys.stderr)
            continue
        ms = d.get("markets", [])
        for m in ms:
            tick = m.get("ticker", "")
            match = None
            for date, tag in date_tags.items():
                if f"-{tag}-" in tick:
                    match = date
                    break
            if match:
                m["_settle_date"] = match
                m["_series"] = series
                out.append(m)
    return out


# ---------- 3. crossing price: last trade at/before local ENTRY_LOCAL_HOUR on settle date ----------
def entry_cutoff_utc(settle_date, tz_name):
    tz = ZoneInfo(tz_name)
    local_dt = datetime.strptime(settle_date, "%Y-%m-%d").replace(
        hour=ENTRY_LOCAL_HOUR, tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


def last_trade_before(ticker, cutoff_utc, max_pages=15):
    cursor = None
    best = None
    for _ in range(max_pages):
        url = f"{KBASE}/markets/trades?ticker={ticker}&limit=1000"
        if cursor:
            url += f"&cursor={cursor}"
        try:
            d = curl_json(url)
        except Exception:
            break
        trades = d.get("trades", [])
        if not trades:
            break
        for t in trades:
            ct = datetime.fromisoformat(t["created_time"].replace("Z", "+00:00"))
            if ct <= cutoff_utc:
                if best is None or ct > best[0]:
                    best = (ct, t)
        oldest = datetime.fromisoformat(trades[-1]["created_time"].replace("Z", "+00:00"))
        cursor = d.get("cursor")
        if oldest <= cutoff_utc or not cursor:
            break
    return best[1] if best else None


def main():
    print("loading ensemble...", file=sys.stderr)
    ens = load_ensemble()
    print("fetching settled Kalshi markets for", SETTLED_DATES, file=sys.stderr)
    markets = fetch_settled_markets()
    print(f"  {len(markets)} settled markets matched to target dates", file=sys.stderr)

    rows = []
    trade_cache_path = OUTDIR + "/trade_cache.json"
    try:
        trade_cache = json.load(open(trade_cache_path))
    except Exception:
        trade_cache = {}

    for m in markets:
        series = m["_series"]
        date = m["_settle_date"]
        is_low = series in CITY_LOW_SERIES.values()
        high_series = series if not is_low else [k for k, v in CITY_LOW_SERIES.items() if v == series][0]
        station, lat, lon = CITY[high_series]
        kind = "min" if is_low else "max"
        eday = ens.get(high_series, {}).get("days", {}).get(date)
        if eday is None:
            continue  # incomplete/null ensemble day (shouldn't happen for our 3 target dates, but guard)
        members = eday[kind]

        strike_type = m.get("strike_type")
        floor_strike = m.get("floor_strike")
        cap_strike = m.get("cap_strike")
        result = m.get("result")
        if result not in ("yes", "no"):
            continue
        try:
            p_ens = ensemble_p(members, strike_type, floor_strike, cap_strike)
        except Exception:
            continue

        ticker = m["ticker"]
        tz_name = ens[high_series]["tz"]
        cutoff = entry_cutoff_utc(date, tz_name)
        if ticker in trade_cache:
            trade = trade_cache[ticker]
        else:
            t = last_trade_before(ticker, cutoff)
            trade = t
            trade_cache[ticker] = trade
        if trade is None:
            continue
        yes_price = float(trade["yes_price_dollars"])
        no_price = float(trade["no_price_dollars"])

        rows.append({
            "ticker": ticker, "series": series, "high_series": high_series, "date": date,
            "kind": kind, "strike_type": strike_type, "floor_strike": floor_strike,
            "cap_strike": cap_strike, "result": result, "p_ens": p_ens,
            "yes_price": yes_price, "no_price": no_price,
            "trade_time": trade["created_time"], "n_hours": eday["n_hours"],
        })

    json.dump(trade_cache, open(trade_cache_path, "w"))
    json.dump(rows, open(OUTDIR + "/joined_rows.json", "w"), indent=1)
    print(f"joined {len(rows)} rows", file=sys.stderr)
    return rows


if __name__ == "__main__":
    main()
