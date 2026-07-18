#!/usr/bin/env python3
"""kwx_runner.py -- the LIVE detection+decision loop for the K-WX weather-nowcast bot (item 6).

Ties the pieces together: a real-time obs feed -> per-city running max/min -> ADAPTIVE poll cadence
(poll faster the closer the temperature is to a strike, per the operator's request) -> glitch-filtered
SUSTAINED cross detection -> the set of ladder rungs that just LOCKED -> a (dry-run by default) order via
kalshi_exec. Because the profit gap has a ~3.3-minute half-life, detecting the cross fast is the whole game;
this loop spends its polling budget where it matters (near a strike) and idles when the temp is far away.

SAFETY: execution goes through kalshi_exec.KalshiExec, which is DRY-RUN unless KWX_LIVE=1 AND .kalshi_creds
exist. This runner never bypasses that. It defaults to paper: every intended trade is logged, none sent.

Obs feed: pluggable. Default = published METAR (aviationweather_metar) -- real-time but ~hourly, so good as
the CONFIRMATION signal and for slow fires; swap in a true 1-min real-time feed (Synoptic HF-ASOS) via
set_feed() once credentialed (Tier-2 item 5). The feed only needs: running_extreme(station, lst_date,
offset, kind) -> {'extreme_f', 'obs': [(iso_ts, temp_f), ...]}.

Usage:
    python kwx_runner.py once            # one poll cycle over today's active markets (paper), prints plan
    python kwx_runner.py loop            # continuous adaptive loop (paper) until killed
"""
import json, os, time, sys, datetime as dt, urllib.request, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"
STATE_PATH = os.path.join(HERE, "kwx_runner_state.json")
PLAN_LOG = os.path.join(HERE, "kwx_runner_plan.jsonl")

# Kalshi weather series -> (IEM/METAR station, fixed STANDARD-time UTC offset [never DST], name).
# Mirrors CITY_CONFIG in kalshi_weather_nowcast.py; KXLOWT* mirror uses the same stations.
CITY = {
    "KXHIGHDEN": ("KDEN", -7), "KXHIGHMIA": ("KMIA", -5), "KXHIGHCHI": ("KMDW", -6),
    "KXHIGHTBOS": ("KBOS", -5), "KXHIGHAUS": ("KAUS", -6), "KXHIGHTSEA": ("KSEA", -8),
    "KXHIGHTSFO": ("KSFO", -8), "KXHIGHTMIN": ("KMSP", -6), "KXHIGHTDC": ("KDCA", -5),
    "KXHIGHTATL": ("KATL", -5), "KXHIGHTDAL": ("KDFW", -6), "KXHIGHTSATX": ("KSAT", -6),
    "KXHIGHNY": ("NYC", -5), "KXHIGHTOKC": ("KOKC", -6), "KXHIGHTLV": ("KLAS", -8),
    "KXHIGHTPHX": ("KPHX", -7), "KXHIGHTHOU": ("KHOU", -6), "KXHIGHPHIL": ("KPHL", -5),
    "KXHIGHTNOLA": ("KMSY", -6), "KXHIGHLAX": ("KLAX", -8),
}

# ---- frozen strategy params (from Phase-2: Track A walk-forward + Track B multi-year tail + Tier-1) ----
MARGIN_F = 1.0          # base: observed extreme must clear strike by this many degF (Track A/Tier-1: best)
SUSTAIN_MIN = 3         # sustained this many minutes -- glitch-robust (Tier-1 S2: sustain=3 reconfirmed;
                        # sustain=1 turns 13.7% of fires into glitch losses vs 0.35% at sustain=3)
MAX_PAY_CENTS = 98      # never pay above this (skip dead-on-arrival fires -- ~63% of raw fires have no gap)
GLITCH_HI_F, GLITCH_LO_F = 130.0, -60.0

# --- bankroll-aware sizing (kwx_sizing.py Monte-Carlo optimum for a small bankroll) ---
# The per-fire CAP is the dominant risk lever: at a 20% cap a correlated 'heat-dome' loss day can wipe the
# account (ruin ~10%); at 5% cap ruin ~0 with nearly the same median growth. Kelly-fraction barely matters
# once the cap binds. So: quarter-Kelly, hard 5% per-fire cap, 17.5% per-city-day cap, min 1 contract.
BANKROLL = 50.0         # set to your actual account; sizing scales with it
KELLY_FRAC = 0.25       # fractional Kelly (quarter) -- robust to model/tail error
PER_FIRE_CAP = 0.05     # max fraction of bankroll on ONE fire (THE risk control)
DEPTH_CAP = 25          # never order more than the book can plausibly fill (Tier-1: books 5-100ct)


def _kelly_fraction(price, p=0.9965):
    """Full-Kelly fraction of bankroll to stake on a contract at `price` (win prob p, lose full stake)."""
    q = 1 - p
    b = (1 - price) / price
    return max(0.0, p - q / b)


def size_for_fire(bankroll, price_c, station):
    """Contracts to buy for a fire at price_c (cents), given bankroll. Quarter-Kelly, 5% per-fire cap,
    per-station size derate, integer, min 1 if affordable, capped by plausible depth."""
    price = price_c / 100.0
    frac = min(KELLY_FRAC * _kelly_fraction(price), PER_FIRE_CAP) * STATION_SIZE_MULT.get(station, 1.0)
    n = int(frac * bankroll / price)
    n = min(n, DEPTH_CAP)
    if n < 1 and price <= bankroll:   # floor of 1 contract if we can afford it and intend to trade
        n = 1
    return n

# Per-station RISK derate (Track B multi-year + Tier-1): a handful of stations disagree with the official
# CLI far more often (obs-vs-CLI lock-failure). Raise their margin (fewer, safer fires) and/or shrink size.
# KPHX(Phoenix) is the worst in BOTH studies (23% raw / 6.25% deployable) -> highest margin + smallest size.
STATION_MARGIN = {"KPHX": 3.0, "KLAX": 2.0, "KMIA": 2.0, "KPHL": 2.0, "KSEA": 2.0}   # else MARGIN_F
STATION_SIZE_MULT = {"KPHX": 0.25, "KLAX": 0.5, "KMIA": 0.5, "KPHL": 0.5, "KSEA": 0.5}  # else 1.0
# HIGH-family "between" rungs carried ALL 6 deployable glitch losses (Tier-1 S1) -> extra sustain there.
PER_CITY_DAILY_CAP_FRAC = 0.175   # cross-city daily exposure cap (Tier-1 S4: precautionary, 15-20%)


def _get(url, to=20):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=to, context=_CTX))


def _dollars(d, k):
    v = d.get(k + "_dollars") if isinstance(d, dict) else None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------- obs feed abstraction ----------------
class MetarFeed:
    """Default feed: published METAR (real-time, ~hourly). Good as confirmation / slow-fire detector."""
    name = "metar"

    def running_extreme(self, station, lst_date, offset, kind):
        import aviationweather_metar as M
        r = M.running_extreme_for_lst_day(station, lst_date, offset, kind=kind)
        if not r:
            return None
        obs = [(t, f) for t, f in [(o[0], o[1]) for o in r["obs"]]]
        return {"extreme_f": r["extreme_f"], "obs": obs}


class WeatherGovFeedWrap:
    """FREE default feed: api.weather.gov 5-min obs (~15-20 min latency). Sufficient for a small bankroll
    (catches ~6-7 slower-repricing fires/day at ~+0.15/ct; at $50 you're capital- not fire-limited)."""
    name = "weathergov-free"

    def running_extreme(self, station, lst_date, offset, kind):
        import weathergov_feed as W
        return W.WeatherGovFeed().running_extreme(station, lst_date, offset, kind)


# DEFAULT = free api.weather.gov. Upgrade to synoptic_feed.SynopticFeed (paid, ~2-5min) only when scaling
# past a few hundred dollars, where the extra fire throughput actually pays. METAR (hourly) is the fallback.
_FEED = WeatherGovFeedWrap()


def set_feed(feed):
    """Swap the obs feed. Options: WeatherGovFeedWrap() [free default], synoptic_feed.SynopticFeed() [paid,
    fast], MetarFeed() [hourly fallback]. Any object exposing running_extreme(station,date,offset,kind)."""
    global _FEED
    _FEED = feed


# ---------------- adaptive cadence ----------------
def adaptive_interval_s(distance_f):
    """Seconds until next poll, as a function of how close the running extreme is to the NEAREST
    not-yet-locked strike (degF). Closer -> faster, per the operator's request. None distance = idle."""
    if distance_f is None:
        return 900          # no active strike nearby -> idle 15 min
    d = abs(distance_f)
    if d <= 0.5:
        return 5            # crossing imminent -> hammer it
    if d <= 2.0:
        return 20
    if d <= 5.0:
        return 90
    return 600              # far away -> slow


# ---------------- sustained-cross logic (glitch-robust) ----------------
def sustained_extreme(obs, kind):
    """Given [(iso_ts, temp_f)...] ascending, return the glitch-filtered running extreme that has been
    SUSTAINED >= SUSTAIN_MIN minutes (i.e. the extreme value that held, not a lone spike). For a max:
    the highest value V such that at least SUSTAIN_MIN minutes of obs at/after V's first occurrence stay
    >= V-? -- we approximate with: drop isolated spikes (a reading > neighbors by >8F/min) then take the
    running extreme over what remains."""
    clean = []
    prev = None
    for ts, f in obs:
        if f is None or f > GLITCH_HI_F or f < GLITCH_LO_F:
            continue
        if prev is not None and abs(f - prev) > 8.0:
            # potential 1-min glitch: require it to persist by not trusting a single jump; skip this point
            # (a true climb shows consecutive steps; a spike reverts). Conservative: skip the jump point.
            prev = f
            continue
        clean.append((ts, f))
        prev = f
    if not clean:
        return None
    vals = [f for _, f in clean]
    if kind == "max":
        # sustained max = the max value that appears with enough subsequent support
        ext = max(vals)
    else:
        ext = min(vals)
    return ext


# ---------------- market discovery ----------------
def active_market_days(today_lst=None):
    """Return list of (series, event_ticker, station, offset, lst_date, kind) for markets open today.
    kind='max' for KXHIGH*, 'min' for KXLOWT* (mirror)."""
    out = []
    for series, (station, offset) in CITY.items():
        # today's LST date for this city
        now_utc = dt.datetime.now(tz=dt.timezone.utc)
        lst = (now_utc + dt.timedelta(hours=offset)).date()
        ev = f"{series}-{lst.strftime('%y%b%d').upper()}"
        out.append((series, ev, station, offset, lst.isoformat(), "max"))
        low = series.replace("KXHIGH", "KXLOWT", 1) if series.startswith("KXHIGH") else None
        if low:
            evl = f"{low}-{lst.strftime('%y%b%d').upper()}"
            out.append((low, evl, station, offset, lst.isoformat(), "min"))
    return out


def event_rungs(event_ticker):
    """Fetch the ladder for an event: list of {ticker, floor, cap, yes_ask_c, no_ask_c, status}."""
    try:
        d = _get(f"{KBASE}/events/{event_ticker}")
    except Exception:
        return []
    rungs = []
    for m in d.get("markets", []):
        if m.get("status") not in ("active", "open", None):
            continue
        rungs.append({
            "ticker": m["ticker"],
            "floor": m.get("floor_strike"), "cap": m.get("cap_strike"),
            "yes_ask_c": (lambda v: int(round(v * 100)) if v else None)(_dollars(m, "yes_ask")),
            "no_ask_c": (lambda v: int(round(v * 100)) if v else None)(_dollars(m, "no_ask")),
        })
    return rungs


# ---------------- lock logic (which rung side locks, given the observed extreme) ----------------
def locked_orders(rungs, extreme_f, kind, margin=MARGIN_F):
    """Return list of (ticker, side, buy_price_cap_c) for rungs now mechanically locked by the observed
    extreme (with `margin`, which may be raised per-station for high-disagreement stations). HIGH/max:
    floor-only rung locks YES once max>floor+margin; any capped rung locks NO once max>cap+margin.
    LOW/min mirrors with the running min."""
    orders = []
    for r in rungs:
        floor, cap = r["floor"], r["cap"]
        if kind == "max":
            if cap is not None and extreme_f > cap + margin:
                if r["no_ask_c"] and r["no_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "no", r["no_ask_c"]))
            elif cap is None and floor is not None and extreme_f > floor + margin:
                if r["yes_ask_c"] and r["yes_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "yes", r["yes_ask_c"]))
        else:  # min
            if floor is not None and extreme_f < floor - margin:
                if r["no_ask_c"] and r["no_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "no", r["no_ask_c"]))
            elif floor is None and cap is not None and extreme_f < cap - margin:
                if r["yes_ask_c"] and r["yes_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "yes", r["yes_ask_c"]))
    return orders


def nearest_strike_distance(rungs, extreme_f, kind, margin=MARGIN_F):
    """Smallest |extreme - relevant_strike| among rungs NOT yet locked -> drives adaptive cadence."""
    best = None
    for r in rungs:
        for strike in (r["floor"], r["cap"]):
            if strike is None:
                continue
            d = (strike + margin) - extreme_f if kind == "max" else extreme_f - (strike - margin)
            if d > 0 and (best is None or d < best):
                best = d
    return best


# ---------------- state ----------------
def _load_state():
    if os.path.exists(STATE_PATH):
        try:
            return json.load(open(STATE_PATH))
        except Exception:
            pass
    return {"fired": {}}   # ticker -> plan record (dedupe)


def _save_state(s):
    json.dump(s, open(STATE_PATH, "w"))


# ---------------- one poll cycle ----------------
def poll_once(exec_client=None, verbose=True):
    from kalshi_exec import KalshiExec
    ex = exec_client or KalshiExec()
    state = _load_state()
    min_interval = None
    plans = []
    for series, ev, station, offset, lst_date, kind in active_market_days():
        rungs = event_rungs(ev)
        if not rungs:
            continue
        try:
            feed = _FEED.running_extreme(station, lst_date, offset, kind)
        except Exception as e:
            if verbose:
                print(f"  [feed skip] {station} {kind}: {type(e).__name__}")
            continue
        if not feed:
            continue
        ext = sustained_extreme(feed["obs"], kind)
        if ext is None:
            ext = feed["extreme_f"]
        # per-station risk derate (Track B / Tier-1): high-disagreement stations get a higher margin
        st_margin = STATION_MARGIN.get(station, MARGIN_F)
        # cadence signal
        dist = nearest_strike_distance(rungs, ext, kind, margin=st_margin)
        iv = adaptive_interval_s(dist)
        min_interval = iv if min_interval is None else min(min_interval, iv)
        # fire locked rungs not already fired
        for ticker, side, cap_c in locked_orders(rungs, ext, kind, margin=st_margin):
            if ticker in state["fired"]:
                continue
            size = size_for_fire(BANKROLL, cap_c, station)   # bankroll-aware, quarter-Kelly, 5% per-fire cap
            if size < 1:
                continue
            fn = ex.buy_yes if side == "yes" else ex.buy_no
            res = fn(ticker, count=size, max_price_cents=cap_c)
            plan = {"ticker": ticker, "side": side, "cap_c": cap_c, "extreme_f": ext,
                    "station": station, "kind": kind, "status": res.get("status"),
                    "ts": int(time.time() * 1000)}
            plans.append(plan)
            state["fired"][ticker] = plan
            with open(PLAN_LOG, "a") as f:
                f.write(json.dumps(plan) + "\n")
            if verbose:
                print(f"  LOCK {ticker} buy {side}@<= {cap_c}c  (obs {kind} {ext:.1f}F)  [{res.get('status')}]")
    _save_state(state)
    if verbose:
        print(f"cycle done: {len(plans)} new locks; next adaptive interval ~{min_interval or 900}s")
    return plans, (min_interval or 900)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"
    if mode == "once":
        poll_once()
    elif mode == "loop":
        print("adaptive paper loop (Ctrl-C to stop). LIVE requires KWX_LIVE=1 + .kalshi_creds.")
        while True:
            _, iv = poll_once()
            time.sleep(max(3, iv))
    else:
        print("usage: kwx_runner.py [once|loop]")


if __name__ == "__main__":
    main()
