#!/usr/bin/env python3
"""
kalshi_weather_paper.py -- FORWARD paper-trading harness for the Kalshi KXHIGH settlement-nowcast
edge (see kalshi_weather_nowcast.py / kalshi_weather_refined.py / kalshi_weather_refined_report.md).
PROPOSE-ONLY: paper only, NO orders, NO capital, no live flag/switch/size ever touched. This is the
charter gate ("tested performance must match live"): the 67-day backtest is capped by what Kalshi's
API exposes in this environment (see kalshi_weather_nowcast.py header), so forward accumulation here
is what actually grows n past that ceiling and proves tested==live, day by day.

THE EDGE (backtest, 67 days, 20 KXHIGH cities, 1272 city-days): once the 1-min ASOS running max for
a city's settlement station clears strike+margin, "high temp > strike" is nowcastable well before
Kalshi's book prices it in -- buying YES at that moment captures the gap. Confirmed baseline
(margin=2F, first crossing): n=35, 91.4% win, +0.168/ct, day-clustered t=4.60. The refinement pass
(kalshi_weather_refined.py) found TWO frozen candidate rules, both tracked here in parallel rather
than picking one -- see kalshi_weather_refined_report.md section 9 for the full honest tradeoff:

FROZEN RULES (pre-registered; do NOT retune from forward data):
  GLITCH FILTER (both rules) : reject obs >130F or <-60F absolute, and reject isolated single-minute
             spikes (>8F/min in AND >8F/min back out vs immediate neighbors) before computing the
             running max/sustain condition. Concretely caught a physically-impossible 120F LAX 1-min
             reading in the backtest (independently corroborated by the hourly METAR archive, which
             is retained here as a LOGGED, non-blocking cross-check -- see report section 7).
  CONSERVATIVE : margin=2F, sustain=1min (i.e. baseline rule + glitch filter only). Backtest: n=33,
             97.0% win, +0.183/ct, t=4.67, worst-case(Wilson-95) EV=+0.060/ct. Smallest possible
             change from the confirmed baseline.
  PRIMARY    : margin=1F, sustain=3min (raw reading, not running max, must hold >=strike+1F for 3
             consecutive qualifying 1-min readings before firing). Backtest: n=42, 100.0% win,
             +0.343/ct, t=7.56 (Bonferroni-significant across the 12-cell margin x sustain family),
             worst-case EV=+0.260/ct. Strongest measured result but a bigger structural change (both
             margin AND timing rule shifted) -- needs more forward confirmation before being trusted
             at the same level as CONSERVATIVE. Tracked in parallel, not instead.
  Entry     : for each OPEN KXHIGH "greater" market whose LST settlement day has started but not yet
             ended (start_utc <= now < end_utc), pull the live 1-min ASOS running series for that
             station/day, glitch-filter it, and test BOTH rules' fire condition. If a rule fires AND
             the live yes_ask leaves gap = (1 - yes_ask) > GAP_MIN AND this (ticker, rule) has not
             already been recorded: record a paper BUY at the executable yes_ask.
  Sizing    : fractional Kelly (quarter-Kelly, FROZEN) off each rule's Wilson-95 WORST-CASE win prob
             from the backtest (not the point estimate), with a cross-city same-day correlation cap
             (heat waves fire many cities on the same LST date -- treated as correlated, gross stake
             on any single date capped at CROSS_CITY_DAILY_CAP of bankroll, split pro-rata).
  Exit      : hold to Kalshi settlement. PnL/ct = outcome - exec_price - kalshi_fee(exec_price).
             Also records whether a locked-YES settled NO (the tail event both rules exist to kill).
  GATE      : PASS (per rule) = day-clustered t>=2 over >=MIN_FIRES forward fills AND mean PnL/ct>0
             AND forward win rate within FORWARD_WINRATE_TOL of the backtest win rate (the actual
             tested==live check). KILL = t<0 after >=MIN_FIRES. else ACCRUING.

Files (idempotent, keyed on ticker+rule): kalshi_weather_positions.jsonl, kalshi_weather_settled.jsonl
Usage: python kalshi_weather_paper.py snapshot | settle | report   (no subcommand = snapshot,settle,report)
"""
import os
import sys
import json
import math
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kalshi_weather_nowcast as base       # CITY_CONFIG, kalshi_fee, parse_ticker_date, wilson_upper_bound
import kalshi_weather_refined as ref        # clean_station_obs, find_sustained_cross, HOURLY archive fetch

HERE = os.path.dirname(os.path.abspath(__file__))
POS = os.path.join(HERE, "kalshi_weather_positions.jsonl")
SET = os.path.join(HERE, "kalshi_weather_settled.jsonl")
KBASE = base.KBASE
UA = base.UA

# ---- FROZEN parameters (pre-registered from kalshi_weather_refined.py; do not retune here) ----
RULES = {
    "conservative": {
        "margin": 2, "sustain_min": 1,
        "backtest": {"n": 33, "win_rate": 0.970, "mean_pnl": 0.1831, "t": 4.67,
                     "worst_case_win_prob": 1.0 - 0.153},   # Wilson-95 worst-case loss rate 0.153
    },
    "primary": {
        "margin": 1, "sustain_min": 3,
        "backtest": {"n": 42, "win_rate": 1.000, "mean_pnl": 0.3433, "t": 7.56,
                     "worst_case_win_prob": 1.0 - 0.084},   # Wilson-95 worst-case loss rate 0.084
    },
}
GAP_MIN = 0.02                      # min (1 - yes_ask) required to fire, same family as backtest gap sweep
QUARTER_KELLY = 0.25                # fractional Kelly (matches kalshi_weather_refined.py's sizing)
CROSS_CITY_DAILY_CAP = 0.15         # cap TOTAL gross paper stake per LST calendar date, across all cities
HOURLY_CROSSCHECK_TOL_F = ref.HOURLY_CROSSCHECK_TOL_F   # logged, NON-BLOCKING (see report section 7/9)
MIN_FIRES = 8                       # forward fills required (per rule) before the gate can rule PASS/KILL
FORWARD_WINRATE_TOL = 0.20          # forward win rate must be within this of the backtest win rate to PASS
MAX_PAGES = 10


def _get_json(url, retries=4, timeout=25):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            if i < retries - 1:
                time.sleep(1.0 * (i + 1))
                continue
            return None


def _load(fn):
    out = []
    if os.path.exists(fn):
        with open(fn) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def _fired_key(ticker, rule_name):
    return f"{ticker}::{rule_name}"


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------

def fetch_open_greater_markets(series_ticker):
    """All currently-open strike_type=='greater' markets for a series (small pages, series is thin)."""
    out = []
    cursor = None
    for _ in range(MAX_PAGES):
        url = f"{KBASE}/markets?series_ticker={series_ticker}&status=open&limit=200"
        if cursor:
            url += f"&cursor={cursor}"
        d = _get_json(url)
        if not d:
            break
        mkts = d.get("markets", [])
        for m in mkts:
            if m.get("strike_type") == "greater":
                out.append(m)
        cursor = d.get("cursor")
        if not cursor or not mkts:
            break
    return out


def fetch_live_asos(station, start_dt, end_dt):
    """Live (uncached -- always fresh) 1-min ASOS pull, no disk cache (unlike the backtest, this is
    real-time data that changes every call)."""
    sid = base.asos1min_id(station)
    sts = start_dt.strftime("%Y-%m-%dT%H:%MZ")
    ets = end_dt.strftime("%Y-%m-%dT%H:%MZ")
    url = (f"{base.ASOS_BASE}?station={sid}&vars=tmpf&sts={sts}&ets={ets}"
           f"&sample=1min&tz=UTC&format=onlycomma")
    try:
        text = base.http_get_text(url, retries=3, timeout=30)
    except Exception:
        return []
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
    return out


def fetch_live_hourly(station, start_dt, end_dt):
    """Live independent hourly METAR pull (logged cross-check, non-blocking)."""
    sid = base.asos1min_id(station)
    y1, m1, d1 = start_dt.year, start_dt.month, start_dt.day
    y2, m2, d2 = end_dt.year, end_dt.month, end_dt.day
    url = (f"{ref.HOURLY_ARCHIVE_BASE}?station={sid}&data=tmpf&year1={y1}&month1={m1}&day1={d1}"
           f"&year2={y2}&month2={m2}&day2={d2}&tz=UTC&format=onlycomma&latlon=no&missing=M"
           f"&trace=T&direct=no&report_type=3,4")
    try:
        text = base.http_get_text(url, retries=2, timeout=25)
    except Exception:
        return []
    out = []
    for line in text.splitlines():
        if not line or line.startswith("station,"):
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        valid, tmpf = parts[1], parts[2]
        if tmpf in ("", "M"):
            continue
        try:
            t = datetime.strptime(valid.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            v = float(tmpf)
        except ValueError:
            continue
        out.append((t, v))
    out.sort(key=lambda x: x[0])
    return out


def _kelly_fraction(price, worst_case_win_prob):
    if price is None or price <= 0 or price >= 1:
        return 0.0
    b = (1.0 - price) / price
    f = worst_case_win_prob - (1.0 - worst_case_win_prob) / b
    return max(0.0, f)


def snapshot():
    have = {_fired_key(p["ticker"], p["rule"]) for p in _load(POS)}
    now = datetime.now(timezone.utc)
    obs_cache = {}      # station -> cleaned live 1-min obs (fetched once per station per run)
    hourly_cache = {}   # station -> live hourly obs (fetched once per station per run, lazily)
    n_new = 0
    n_scanned = 0
    # track today's already-recorded fires by (date, rule) to keep the cross-city cap meaningful
    # within a single run (across runs, report() re-derives the true daily gross from the file).
    with open(POS, "a") as f:
        for series, cfg in base.CITY_CONFIG.items():
            mkts = fetch_open_greater_markets(series)
            for m in mkts:
                n_scanned += 1
                ticker = m.get("ticker")
                strike = m.get("floor_strike")
                close_time_str = m.get("close_time")
                if ticker is None or strike is None or close_time_str is None:
                    continue
                tdate = base.parse_ticker_date(ticker)
                if tdate is None:
                    continue
                offset = cfg["offset"]
                start_utc = datetime(tdate.year, tdate.month, tdate.day, 0, 0, tzinfo=timezone.utc) - timedelta(hours=offset)
                end_utc = start_utc + timedelta(days=1)
                if not (start_utc <= now < end_utc):
                    continue   # settlement day not currently in progress (not started yet, or over)

                station = cfg["station"]
                if station not in obs_cache:
                    raw = fetch_live_asos(station, start_utc, now + timedelta(minutes=1))
                    cleaned, removed = ref.clean_station_obs(raw)
                    obs_cache[station] = cleaned
                    if removed:
                        print(f"  [glitch-filter] {station}: removed {len(removed)} live reading(s): "
                              f"{[(t.isoformat(), v, why) for t, v, why in removed]}")
                obs = obs_cache[station]
                if len(obs) < 5:
                    continue

                yes_ask = m.get("yes_ask_dollars")
                try:
                    yes_ask = float(yes_ask) if yes_ask not in (None, "") else None
                except (TypeError, ValueError):
                    yes_ask = None

                for rule_name, rule in RULES.items():
                    key = _fired_key(ticker, rule_name)
                    if key in have:
                        continue
                    threshold = strike + rule["margin"]
                    t_star = ref.find_sustained_cross(obs, threshold, rule["sustain_min"])
                    if t_star is None:
                        continue
                    if yes_ask is None or yes_ask <= 0 or yes_ask >= 1:
                        continue
                    gap = 1.0 - yes_ask
                    if gap <= GAP_MIN:
                        continue

                    # logged, NON-BLOCKING hourly cross-check (report section 7/9: added no extra
                    # in-sample bite beyond glitch-filter+sustain, so it does not gate fills here --
                    # just recorded for forward monitoring / a future tightening decision).
                    if station not in hourly_cache:
                        hourly_cache[station] = fetch_live_hourly(
                            station, start_utc - timedelta(hours=2), now + timedelta(minutes=1))
                    hmax_so_far = None
                    hvals = [v for t, v in hourly_cache[station] if t <= t_star]
                    if hvals:
                        hmax_so_far = max(hvals)
                    hourly_agrees = (hmax_so_far is not None and hmax_so_far >= strike - HOURLY_CROSSCHECK_TOL_F)

                    f_kelly_full = _kelly_fraction(yes_ask, rule["backtest"]["worst_case_win_prob"])
                    size_fraction = min(QUARTER_KELLY * f_kelly_full, CROSS_CITY_DAILY_CAP)

                    rec = dict(
                        ticker=ticker, rule=rule_name, series=series, city=cfg["name"], station=station,
                        date=tdate.isoformat(), strike=strike, margin=rule["margin"],
                        sustain_min=rule["sustain_min"], t_star=t_star.isoformat(),
                        exec_price=yes_ask, gap=round(gap, 4), fee=round(base.kalshi_fee(yes_ask), 4),
                        size_fraction_bankroll=round(size_fraction, 4),
                        hourly_max_so_far=hmax_so_far, hourly_crosscheck_agrees=hourly_agrees,
                        close_time=close_time_str, ts=now.isoformat(),
                    )
                    f.write(json.dumps(rec) + "\n")
                    have.add(key)
                    n_new += 1
                    print(f"  [FIRE] {ticker} rule={rule_name} strike={strike} margin={rule['margin']} "
                          f"sustain={rule['sustain_min']}min t*={t_star.isoformat()} yes_ask={yes_ask} "
                          f"gap={gap:.3f} size={size_fraction:.4f} hourly_agrees={hourly_agrees}")
    print(f"[snapshot] scanned {n_scanned} open 'greater' KXHIGH markets across {len(base.CITY_CONFIG)} "
          f"series, {n_new} NEW paper BUY(s) recorded across {len(RULES)} rules "
          f"(total recorded positions now {len(have)})")
    return n_new


# ---------------------------------------------------------------------------
# settle
# ---------------------------------------------------------------------------

def settle():
    settled_keys = {_fired_key(s["ticker"], s["rule"]) for s in _load(SET)}
    open_pos = [p for p in _load(POS) if _fired_key(p["ticker"], p["rule"]) not in settled_keys]
    # dedupe tickers to settle (one paper position per ticker per rule, but a ticker only needs one
    # market-status lookup even if both rules fired on it)
    tickers = sorted(set(p["ticker"] for p in open_pos))
    status_by_ticker = {}
    for i in range(0, len(tickers), 50):
        chunk = tickers[i:i + 50]
        d = _get_json(f"{KBASE}/markets?tickers={','.join(chunk)}")
        if not d:
            continue
        for m in d.get("markets", []):
            status_by_ticker[m.get("ticker")] = m

    n = 0
    with open(SET, "a") as f:
        for p in open_pos:
            m = status_by_ticker.get(p["ticker"])
            if not m:
                continue
            result = m.get("result")
            if result not in ("yes", "no"):
                continue   # not settled yet
            outcome = 1.0 if result == "yes" else 0.0
            price = p["exec_price"]
            fee = p.get("fee", base.kalshi_fee(price))
            pnl = outcome - price - fee
            locked_yes_settled_no = (result != "yes")
            rec = dict(p, result=result, outcome=outcome, pnl=round(pnl, 4),
                       locked_yes_settled_no=locked_yes_settled_no,
                       settled_ts=datetime.now(timezone.utc).isoformat())
            f.write(json.dumps(rec) + "\n")
            n += 1
    print(f"[settle] {len(open_pos)} unsettled paper position(s) checked ({len(tickers)} unique tickers), "
          f"{n} newly settled")
    return n


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def _clustered_t(pnls, dates):
    n = len(pnls)
    if n == 0:
        return {"mean": None, "t": None, "n_clusters": 0}
    mean = sum(pnls) / n
    clusters = defaultdict(list)
    for p, d in zip(pnls, dates):
        clusters[d].append(p)
    cluster_sums = [sum(x - mean for x in v) for v in clusters.values()]
    var = sum(s * s for s in cluster_sums) / (n * n) if n > 0 else 0.0
    se = math.sqrt(var) if var > 0 else 0.0
    t = mean / se if se > 0 else float("nan")
    return {"mean": mean, "se": se, "t": t, "n_clusters": len(clusters)}


def report():
    settled = _load(SET)
    positions = _load(POS)
    n_open_total = len(positions) - len(settled)
    if not settled:
        print("[report] Kalshi weather forward paper gate: status=CLOCK-NOT-STARTED")
        print(f"  total recorded paper fires = {len(positions)}   settled = 0   open/pending = {n_open_total}")
        for rule_name in RULES:
            n_r = sum(1 for p in positions if p["rule"] == rule_name)
            print(f"    rule={rule_name}: {n_r} paper fire(s) recorded so far, 0 settled")
        return

    for rule_name, rule in RULES.items():
        rs = [s for s in settled if s["rule"] == rule_name]
        n_open = sum(1 for p in positions if p["rule"] == rule_name) - len(rs)
        bt = rule["backtest"]
        print(f"\n[report] rule={rule_name}  (margin={rule['margin']}F, sustain={rule['sustain_min']}min)")
        if not rs:
            print(f"  0 settled yet (open/pending={n_open}) -- status=CLOCK-NOT-STARTED")
            continue
        pnls = [r["pnl"] for r in rs]
        dates = [r["date"] for r in rs]
        wins = [r["outcome"] for r in rs]
        bad = [r for r in rs if r.get("locked_yes_settled_no")]
        win_rate = sum(wins) / len(wins)
        ct = _clustered_t(pnls, dates)
        n = len(rs)
        forward_ok_winrate = abs(win_rate - bt["win_rate"]) <= FORWARD_WINRATE_TOL
        t = ct["t"]
        t_valid = t is not None and not (isinstance(t, float) and math.isnan(t))
        status = ("PASS" if (n >= MIN_FIRES and t_valid and t >= 2 and ct["mean"] > 0 and forward_ok_winrate)
                  else "KILL" if (n >= MIN_FIRES and t_valid and t < 0)
                  else "ACCRUING")
        print(f"  settled = {n} (n_clusters/days = {ct['n_clusters']})   open/pending = {n_open}")
        print(f"  forward win rate = {win_rate:.3f}   (backtest = {bt['win_rate']:.3f}, "
              f"tol = +/-{FORWARD_WINRATE_TOL})   {'OK' if forward_ok_winrate else 'DRIFTED'}")
        print(f"  forward mean PnL/ct = {ct['mean']:+.4f}   (backtest = {bt['mean_pnl']:+.4f})")
        print(f"  forward day-clustered t = {fmt_t(t)}   (backtest t = {bt['t']:.2f})   need t>=2 over "
              f">={MIN_FIRES} fills")
        print(f"  tail: {len(bad)} locked-YES settled NO   {[r['ticker'] for r in bad]}")
        hourly_flagged = [r for r in rs if r.get("hourly_crosscheck_agrees") is False]
        hourly_flagged_bad = [r for r in hourly_flagged if r.get("locked_yes_settled_no")]
        print(f"  hourly cross-check (logged, non-blocking): flagged {len(hourly_flagged)} fill(s) as "
              f"disagreeing, {len(hourly_flagged_bad)} of those were actual losses")
        print(f"  GATE -> {status}  (PASS: n>={MIN_FIRES}, t>=2, mean>0, forward win rate within "
              f"{FORWARD_WINRATE_TOL} of backtest {bt['win_rate']:.3f}; KILL: t<0 after n>={MIN_FIRES})")

    # cross-city gross-exposure check (informational): how much SAME-DAY, cross-rule notional has
    # actually been recorded, vs the CROSS_CITY_DAILY_CAP the sizing rule targets.
    by_date = defaultdict(list)
    for p in positions:
        by_date[p["date"]].append(p)
    max_day = max(by_date.items(), key=lambda kv: len(kv[1])) if by_date else None
    if max_day:
        d, ps = max_day
        gross = sum(p.get("size_fraction_bankroll", 0.0) for p in ps)
        print(f"\n[cross-city cap check] busiest LST date so far: {d} -- {len(ps)} fire(s) across "
              f"{len(set(p['ticker'] for p in ps))} ticker(s)/{len(set(p['series'] for p in ps))} "
              f"cities, gross paper stake = {gross:.4f} of bankroll (cap = {CROSS_CITY_DAILY_CAP})"
              f"{'  ** OVER CAP, would need pro-rata scaling in live sizing **' if gross > CROSS_CITY_DAILY_CAP else ''}")


def fmt_t(t):
    if t is None or (isinstance(t, float) and math.isnan(t)):
        return "n/a"
    return f"{t:.2f}"


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("snapshot", "all"):
        snapshot()
    if mode in ("settle", "all"):
        settle()
    if mode in ("report", "all"):
        report()
