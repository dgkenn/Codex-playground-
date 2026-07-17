#!/usr/bin/env python3
"""
weather_edge.py

Probe for a superior-information edge on Kalshi daily HIGH-TEMPERATURE markets
using free NWS/NOAA forecasts.

Thesis: professional weather forecasts (NWS / NBM MOS) have real skill. If Kalshi's
daily temperature markets are priced by less-informed retail, a forecast-based fair
value could beat the market by more than Kalshi's fee. This tests whether that gap
exists and survives fees+spread, or whether the market already prices the forecast.

Data sources (all free, no auth):
  - Kalshi public API  : api.elections.kalshi.com/trade-api/v2
        events / markets (buckets, strikes, settlement result)
        candlesticks     (historical yes_bid/yes_ask/price, volume, OI)
  - IEM (Iowa Env Mesonet):
        api/1/mos.json               -> archived NBM (NBS) MOS forecasts  (the "forecast")
        cgi-bin/request/daily.py     -> observed daily max temp (obs, for sigma calibration)

Method
  For each settled city-day:
    1. Pull Kalshi buckets + settlement (winning bucket = ground-truth outcome).
    2. Snapshot the MARKET (yes_bid/ask/mid per bucket) at a fixed lead: the morning
       OF the settlement day (13Z), before the afternoon high is realized -> no leakage.
    3. FORECAST high = max of MOS tmp over the local day, from a run issued that morning
       (<= snapshot). Debias + estimate sigma empirically from (forecast - observed).
    4. forecast_P(bucket) = Normal(F, sigma) integrated over the bucket's integer range.
    5. EDGE per bucket vs market. Simulate the +EV trade (buy at ask / sell at bid),
       settle at outcome, NET the Kalshi fee (0.07*p*(1-p)) and the bid/ask spread.
    6. Cluster PnL by day; report t-stat, win rate, mean edge, Brier of market vs forecast.
  Plus a LIVE divergence snapshot on today's OPEN events (forward signal).

Blunt question answered: is there a real, fee-surviving forecast edge, or is the
market already efficient w.r.t. NWS forecasts?
"""

import os, sys, json, time, math, statistics, datetime as dt
from collections import defaultdict
import requests

KBASE = "https://api.elections.kalshi.com/trade-api/v2"
IEM   = "https://mesonet.agron.iastate.edu"
UA    = {"User-Agent": "kalshi-weather-edge-research dgkenn@bu.edu"}
CACHE = "/home/user/Codex-playground-/.weather_cache"
os.makedirs(CACHE, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(UA)

# Kalshi high-temp series -> (MOS/METAR station id, IEM ASOS network, IEM station id, tz offset hrs from UTC in summer)
# station is the best-guess Kalshi settlement station; outcome PnL uses Kalshi's own
# settlement so a station mismatch only degrades the FORECAST (conservative).
CITIES = {
    "KXHIGHNY":   ("KNYC", "NY_ASOS", "NYC", -4),   # Central Park
    "KXHIGHCHI":  ("KMDW", "IL_ASOS", "MDW", -5),   # Chicago Midway
    "KXHIGHMIA":  ("KMIA", "FL_ASOS", "MIA", -4),   # Miami Intl
    "KXHIGHDEN":  ("KDEN", "CO_ASOS", "DEN", -6),   # Denver Intl
    "KXHIGHAUS":  ("KAUS", "TX_ASOS", "AUS", -5),   # Austin (Bergstrom; Kalshi may use Camp Mabry - caveat)
    "KXHIGHLAX":  ("KLAX", "CA_ASOS", "LAX", -7),   # LAX
    "KXHIGHPHIL": ("KPHL", "PA_ASOS", "PHL", -4),   # Philadelphia Intl
}

MONTHS = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,"JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}

SNAPSHOT_HOUR_UTC = 13   # morning-of snapshot (pre-afternoon-high)
FEE_RATE = 0.07          # Kalshi trading fee coefficient: fee = 0.07*p*(1-p) per contract


# ----------------------------- caching http ---------------------------------
def cget(url, params=None, ttl=10**9, tag=None):
    key = tag or (url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items())))
    fn = os.path.join(CACHE, "".join(c if c.isalnum() else "_" for c in key)[:180] + ".json")
    if os.path.exists(fn) and (time.time() - os.path.getmtime(fn)) < ttl:
        try:
            with open(fn) as f: return json.load(f)
        except Exception: pass
    for attempt in range(4):
        try:
            r = SESSION.get(url, params=params, timeout=40)
            if r.status_code == 200:
                try: d = r.json()
                except Exception: d = {"_raw": r.text}
                with open(fn, "w") as f: json.dump(d, f)
                return d
            if r.status_code in (429, 500, 502, 503):
                time.sleep(1.5 * (attempt + 1)); continue
            return {"_status": r.status_code}
        except Exception as e:
            time.sleep(1.0 * (attempt + 1))
    return {"_error": True}


def parse_event_date(ev):
    # KXHIGHNY-26JUL15 -> date(2026,7,15)
    tail = ev.split("-")[-1]
    yy = 2000 + int(tail[:2]); mo = MONTHS[tail[2:5]]; dd = int(tail[5:7])
    return dt.date(yy, mo, dd)


# ----------------------------- Kalshi ---------------------------------------
def list_settled_events(series, max_events=60):
    out, cursor = [], None
    while len(out) < max_events:
        p = {"series_ticker": series, "status": "settled", "limit": 200}
        if cursor: p["cursor"] = cursor
        d = cget(KBASE + "/events", p, ttl=6*3600, tag=f"ev_{series}_{cursor}")
        evs = d.get("events", [])
        out += evs
        cursor = d.get("cursor")
        if not cursor or not evs: break
    # dedup + sort by date desc
    seen = {}
    for e in out:
        seen[e["event_ticker"]] = e
    evs = sorted(seen.values(), key=lambda e: parse_event_date(e["event_ticker"]), reverse=True)
    return evs[:max_events]


def get_buckets(event_ticker):
    d = cget(KBASE + "/markets", {"event_ticker": event_ticker}, ttl=6*3600,
             tag=f"mk_{event_ticker}")
    return d.get("markets", [])


def integer_range_from_market(m):
    """Return (lo, hi) inclusive integer range of winning highs, using subtitle text."""
    sub = (m.get("subtitle") or m.get("yes_sub_title") or "").lower()
    fs, cs = m.get("floor_strike"), m.get("cap_strike")
    # threshold buckets
    if "or below" in sub or "or lower" in sub:
        # cap_strike given, "X or below": winning <= (cap-1) when 'to'? subtitle explicit
        import re
        n = re.search(r"(\d+)", sub)
        v = int(n.group(1)) if n else (int(cs) - 1 if cs is not None else None)
        return (-999, v)
    if "or above" in sub or "or higher" in sub:
        import re
        n = re.search(r"(\d+)", sub)
        v = int(n.group(1)) if n else (int(fs) + 1 if fs is not None else None)
        return (v, 999)
    # range bucket "A to B"
    import re
    nums = [int(x) for x in re.findall(r"(\d+)", sub)]
    if len(nums) >= 2:
        return (min(nums[:2]), max(nums[:2]))
    if fs is not None and cs is not None:
        return (int(fs), int(cs))
    return (None, None)


def candlestick_snapshot(series, ticker, snap_ts):
    """Return dict with yes_bid, yes_ask, price, volume(day), oi at/just-before snap_ts."""
    start = snap_ts - 12*3600
    end   = snap_ts + 2*3600
    d = cget(KBASE + f"/series/{series}/markets/{ticker}/candlesticks",
             {"start_ts": start, "end_ts": end, "period_interval": 60},
             ttl=6*3600, tag=f"cs_{ticker}_{snap_ts}")
    cs = d.get("candlesticks", [])
    if not cs: return None
    def val(node, k):
        if not node: return None
        v = node.get(k)
        return float(v) if v not in (None, "") else None
    # last candle at or before snap_ts with a usable bid or ask
    chosen = None
    for c in cs:
        if c.get("end_period_ts", 0) <= snap_ts:
            yb = val(c.get("yes_bid"), "close_dollars")
            ya = val(c.get("yes_ask"), "close_dollars")
            pr = val(c.get("price"), "close_dollars")
            if yb is not None or ya is not None or pr is not None:
                chosen = c
    if chosen is None: return None
    # day volume = sum of volume_fp over the local day window up to snapshot
    dayvol = 0.0
    for c in cs:
        if c.get("end_period_ts", 0) <= snap_ts:
            v = c.get("volume_fp")
            if v not in (None, ""):
                try: dayvol += float(v)
                except Exception: pass
    yb = val(chosen.get("yes_bid"), "close_dollars")
    ya = val(chosen.get("yes_ask"), "close_dollars")
    pr = val(chosen.get("price"), "close_dollars")
    oi = None
    if chosen.get("open_interest_fp") not in (None, ""):
        try: oi = float(chosen["open_interest_fp"])
        except Exception: oi = None
    return {"yes_bid": yb, "yes_ask": ya, "price": pr, "dayvol": dayvol, "oi": oi}


# ----------------------------- IEM forecast/obs ------------------------------
def mos_forecast_high(station, date_local, tz):
    """Forecast daily high (max of MOS tmp over local calendar day) from a morning run.
    Uses NBS (NBM short) run at 06Z of the settlement date, fallback 00Z / prior 18Z."""
    ymd = date_local.strftime("%Y-%m-%d")
    for rt in [f"{ymd}T06:00:00Z", f"{ymd}T00:00:00Z",
               (date_local - dt.timedelta(days=1)).strftime("%Y-%m-%dT18:00:00Z")]:
        d = cget(IEM + "/api/1/mos.json",
                 {"station": station, "model": "NBS", "runtime": rt},
                 ttl=10**9, tag=f"mos_{station}_{rt}")
        data = d.get("data", [])
        if not data: continue
        # local day window: temps whose ftime local date == date_local (approx via tz)
        vals = []
        for row in data:
            ft = row.get("ftime_utc") or row.get("ftime"); tmp = row.get("tmp")
            if ft is None or tmp in (None, ""): continue
            t = None
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    t = dt.datetime.strptime(ft[:19] if len(ft) >= 19 else ft, fmt); break
                except Exception:
                    continue
            if t is None: continue
            local = t + dt.timedelta(hours=tz)
            if local.date() == date_local and 6 <= local.hour <= 23:
                vals.append(float(tmp))
        if vals:
            return max(vals), rt
    return None, None


_OBS_CACHE = {}
def obs_highs(network, station, y1m1d1, y2m2d2):
    key = (network, station, y1m1d1, y2m2d2)
    if key in _OBS_CACHE: return _OBS_CACHE[key]
    p = {"network": network, "stations": station,
         "year1": y1m1d1[0], "month1": y1m1d1[1], "day1": y1m1d1[2],
         "year2": y2m2d2[0], "month2": y2m2d2[1], "day2": y2m2d2[2],
         "var": "max_temp_f", "format": "comma", "na": "blank"}
    d = cget(IEM + "/cgi-bin/request/daily.py", p, ttl=10**9,
             tag=f"obs_{network}_{station}_{y1m1d1}_{y2m2d2}")
    raw = d.get("_raw", "")
    m = {}
    for line in raw.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 3 and parts[2].strip():
            try: m[parts[1].strip()] = float(parts[2])
            except Exception: pass
    _OBS_CACHE[key] = m
    return m


# ----------------------------- probability model -----------------------------
def normal_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def bucket_prob(lo, hi, F, sigma):
    """P(integer high in [lo,hi]) under Normal(F,sigma), continuity-corrected."""
    a = -1e9 if lo <= -900 else (lo - 0.5)
    b =  1e9 if hi >=  900 else (hi + 0.5)
    return max(0.0, min(1.0, normal_cdf((b - F)/sigma) - normal_cdf((a - F)/sigma)))

def kalshi_fee(p):
    p = min(max(p, 0.0), 1.0)
    return FEE_RATE * p * (1 - p)


# ----------------------------- main backtest ---------------------------------
def run_backtest(cities, max_events, edge_thresh_extra=0.0):
    # pass 1: collect per (city,day) forecast, observed, buckets+snapshot+outcome
    records = []      # per bucket
    daydata = []      # per city-day: forecast F, observed, outcome bucket
    for series, (station, network, iemst, tz) in cities.items():
        evs = list_settled_events(series, max_events=max_events)
        if not evs: continue
        dates = [parse_event_date(e["event_ticker"]) for e in evs]
        y1 = (min(dates).year, min(dates).month, min(dates).day)
        y2 = (max(dates).year, max(dates).month, max(dates).day)
        obs = obs_highs(network, iemst, y1, y2)
        for e in evs:
            ev = e["event_ticker"]
            d_local = parse_event_date(ev)
            F, run = mos_forecast_high(station, d_local, tz)
            if F is None: continue
            snap_ts = int(dt.datetime(d_local.year, d_local.month, d_local.day,
                                      SNAPSHOT_HOUR_UTC, 0, tzinfo=dt.timezone.utc).timestamp())
            mkts = get_buckets(ev)
            if not mkts: continue
            observed = obs.get(d_local.strftime("%Y-%m-%d"))
            # outcome bucket + snapshots
            buckets = []
            outcome_present = False
            for m in mkts:
                lo, hi = integer_range_from_market(m)
                if lo is None: continue
                res = m.get("result")
                won = 1 if res == "yes" else (0 if res == "no" else None)
                if won is None: continue
                outcome_present = True
                snap = candlestick_snapshot(series, m["ticker"], snap_ts)
                buckets.append({"ticker": m["ticker"], "lo": lo, "hi": hi,
                                "won": won, "snap": snap})
            if not outcome_present or not buckets: continue
            daydata.append({"series": series, "ev": ev, "date": d_local,
                            "F": F, "obs": observed, "run": run,
                            "buckets": buckets})

    # calibrate sigma from forecast vs observed (per city pooled)
    resid = [d["F"] - d["obs"] for d in daydata if d["obs"] is not None]
    if len(resid) >= 10:
        bias = statistics.mean(resid)
        sigma = statistics.pstdev([r - bias for r in resid])
        sigma = max(sigma, 1.5)
    else:
        bias, sigma = 0.0, 3.0

    # pass 2: build market/forecast probabilities and trades
    trades = []       # per bucket trade
    diverg = []       # |forecast_P - market_mid| for all liquid buckets
    brier_mkt = []; brier_fc = []
    for d in daydata:
        F = d["F"] - bias
        for b in d["buckets"]:
            snap = b["snap"]
            if not snap: continue
            yb, ya, pr = snap["yes_bid"], snap["yes_ask"], snap["price"]
            # need a two-sided market
            if yb is None or ya is None:
                # fall back to price as mid if present, skip trading (no spread)
                continue
            if ya < yb:  # crossed/garbage
                continue
            mid = (yb + ya) / 2.0
            fP = bucket_prob(b["lo"], b["hi"], F, sigma)
            diverg.append({"series": d["series"], "date": str(d["date"]),
                           "mid": mid, "fP": fP, "absedge": abs(fP - mid),
                           "spread": ya - yb, "dayvol": snap["dayvol"]})
            # Brier contributions (per bucket, market mid vs forecast)
            brier_mkt.append((mid - b["won"])**2)
            brier_fc.append((fP - b["won"])**2)
            # trade logic (taker, net fee + spread already in ask/bid)
            # BUY YES if forecast prob beats ask + fee
            buy_edge = fP - ya - kalshi_fee(ya)
            sell_edge = yb - fP - kalshi_fee(yb)
            thr = edge_thresh_extra
            if buy_edge > thr and buy_edge >= sell_edge:
                pnl = b["won"] - ya - kalshi_fee(ya)      # realized
                trades.append({"series": d["series"], "date": str(d["date"]),
                               "side": "buy", "price": ya, "fP": fP, "won": b["won"],
                               "edge": buy_edge, "pnl": pnl, "dayvol": snap["dayvol"]})
            elif sell_edge > thr:
                pnl = yb - b["won"] - kalshi_fee(yb)
                trades.append({"series": d["series"], "date": str(d["date"]),
                               "side": "sell", "price": yb, "fP": fP, "won": b["won"],
                               "edge": sell_edge, "pnl": pnl, "dayvol": snap["dayvol"]})

    return {"daydata": daydata, "bias": bias, "sigma": sigma,
            "n_resid": len(resid), "trades": trades, "diverg": diverg,
            "brier_mkt": brier_mkt, "brier_fc": brier_fc}


def day_cluster_stats(trades):
    by_day = defaultdict(list)
    for t in trades:
        by_day[(t["series"], t["date"])].append(t["pnl"])
    day_pnls = [statistics.mean(v) for v in by_day.values()]  # mean pnl per contract per day
    n = len(day_pnls)
    if n < 2:
        return {"n_days": n, "n_trades": len(trades), "mean": (day_pnls[0] if n else None),
                "t": None, "win_rate": None}
    mean = statistics.mean(day_pnls)
    sd = statistics.pstdev(day_pnls)
    se = sd / math.sqrt(n) if sd > 0 else float("nan")
    t = mean / se if se and not math.isnan(se) and se > 0 else None
    wr = sum(1 for p in [x["pnl"] for x in trades] if p > 0) / len(trades)
    return {"n_days": n, "n_trades": len(trades), "mean_pnl_per_contract": mean,
            "t": t, "win_rate": wr,
            "total_notional_trades": len(trades)}


def live_snapshot(cities, sigma_live=2.5):
    """Today's OPEN events: forecast_P vs market mid divergence (forward signal)."""
    out = []
    today = dt.date.today()
    for series, (station, network, iemst, tz) in cities.items():
        d = cget(KBASE + "/events", {"series_ticker": series, "status": "open", "limit": 10},
                 ttl=600, tag=f"open_{series}")
        for e in d.get("events", []):
            ev = e["event_ticker"]
            try: d_local = parse_event_date(ev)
            except Exception: continue
            if d_local < today: continue
            F, run = mos_forecast_high(station, d_local, tz)
            if F is None: continue
            mkts = get_buckets(ev)
            for m in mkts:
                lo, hi = integer_range_from_market(m)
                if lo is None: continue
                ob = cget(KBASE + f"/markets/{m['ticker']}/orderbook",
                          ttl=180, tag=f"ob_{m['ticker']}")
                book = ob.get("orderbook_fp") or {}
                yes = book.get("yes_dollars") or []
                no = book.get("no_dollars") or []
                yb = max((float(p) for p, _ in yes), default=None)
                best_no = max((float(p) for p, _ in no), default=None)
                ya = (1.0 - best_no) if best_no is not None else None
                if yb is None or ya is None: continue
                if ya < yb: continue
                mid = (yb + ya)/2.0
                fP = bucket_prob(lo, hi, F, sigma_live)
                out.append({"series": series, "ev": ev, "date": str(d_local),
                            "ticker": m["ticker"], "F": F, "fP": fP, "mid": mid,
                            "yb": yb, "ya": ya, "absedge": abs(fP - mid)})
    return out


def main():
    max_events = int(os.environ.get("MAXEV", "50"))
    print(f"# Kalshi weather forecast-edge probe (max_events/city={max_events})")
    res = run_backtest(CITIES, max_events)
    dd, trades, div = res["daydata"], res["trades"], res["diverg"]
    print(f"\n## Data collected")
    print(f"city-days with forecast+buckets: {len(dd)}")
    print(f"forecast debias (mean F-obs): {res['bias']:+.2f} F over n={res['n_resid']}")
    print(f"forecast sigma (1-day high, debiased): {res['sigma']:.2f} F")
    if res["brier_mkt"]:
        print(f"Brier  market-mid vs outcome: {statistics.mean(res['brier_mkt']):.4f}  "
              f"(n buckets={len(res['brier_mkt'])})")
        print(f"Brier  forecast   vs outcome: {statistics.mean(res['brier_fc']):.4f}")

    print(f"\n## Divergence distribution (liquid two-sided buckets), n={len(div)}")
    if div:
        ae = sorted(x["absedge"] for x in div)
        def pct(q): return ae[min(len(ae)-1, int(q*len(ae)))]
        print(f"|forecast_P - market_mid|: median={statistics.median(ae):.3f} "
              f"p75={pct(.75):.3f} p90={pct(.90):.3f} max={ae[-1]:.3f}")
        for thr in (0.03,0.05,0.10):
            frac = sum(1 for x in ae if x>thr)/len(ae)
            print(f"  frac |edge|>{thr:.2f}: {frac:.3f}")
        sp = [x["spread"] for x in div]
        print(f"typical bid/ask spread: median={statistics.median(sp):.3f}")

    print(f"\n## Backtest: trade the forecast-vs-price divergence (net fee+spread)")
    st = day_cluster_stats(trades)
    print(json.dumps(st, indent=2, default=str))
    if trades:
        tp = [t["pnl"] for t in trades]
        print(f"mean pnl/contract (all trades): {statistics.mean(tp):+.4f}")
        print(f"total pnl (1 contract each): {sum(tp):+.2f} over {len(trades)} trades")
        # capacity proxy: median day-volume on traded buckets
        dv = sorted(t["dayvol"] for t in trades if t["dayvol"])
        if dv:
            print(f"traded-bucket day volume: median={statistics.median(dv):.0f} contracts")

    print(f"\n## LIVE divergence (open events, forward signal)")
    live = live_snapshot(CITIES, sigma_live=res["sigma"])
    print(f"open buckets priced: {len(live)}")
    if live:
        lae = sorted(x["absedge"] for x in live)
        print(f"live |forecast_P - market_mid|: median={statistics.median(lae):.3f} "
              f"p90={lae[min(len(lae)-1,int(0.9*len(lae)))]:.3f} max={lae[-1]:.3f}")
        for thr in (0.05, 0.10):
            print(f"  frac live |edge|>{thr:.2f}: {sum(1 for x in lae if x>thr)/len(lae):.3f}")
        big = sorted(live, key=lambda x: -x["absedge"])[:6]
        for b in big:
            print(f"  {b['ticker']} F={b['F']:.0f} fP={b['fP']:.2f} mid={b['mid']:.2f} edge={b['absedge']:.2f}")
    # save artifacts
    with open("/home/user/Codex-playground-/.weather_cache/_result.json", "w") as f:
        json.dump({"stats": st, "bias": res["bias"], "sigma": res["sigma"],
                   "n_daydays": len(dd), "brier_mkt": statistics.mean(res["brier_mkt"]) if res["brier_mkt"] else None,
                   "brier_fc": statistics.mean(res["brier_fc"]) if res["brier_fc"] else None,
                   "n_div": len(div), "live_n": len(live),
                   "diverg": div[:2000], "trades": trades, "live": live[:500]}, f, default=str)
    print("\nsaved -> .weather_cache/_result.json")


if __name__ == "__main__":
    main()
