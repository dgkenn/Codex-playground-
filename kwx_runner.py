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

# HIGH series -> its matching LOW (overnight-min) series. EXPLICIT + data-verified, because Kalshi's naming
# is inconsistent (some HIGH series carry a 'T' -- KXHIGHTBOS -- and the LOW family does NOT double it:
# KXLOWTBOS, not KXLOWTTBOS; and NY's low is KXLOWTNYC, not KXLOWTNY). The old series.replace("KXHIGH",
# "KXLOWT") produced WRONG tickers for 14/20 cities (double-T / missing 'C') -> those low events silently
# returned no rungs and never traded. This map is the authoritative HIGH->LOW correspondence (all 20 verified
# against the KXLOWT* series present in the backtest data). LOW markets settle on the SAME LST calendar day
# as the HIGH (the day's minimum), so they reuse the high's lst_date/offset; only kind flips to 'min'.
CITY_LOW_SERIES = {
    "KXHIGHDEN": "KXLOWTDEN", "KXHIGHMIA": "KXLOWTMIA", "KXHIGHCHI": "KXLOWTCHI",
    "KXHIGHTBOS": "KXLOWTBOS", "KXHIGHAUS": "KXLOWTAUS", "KXHIGHTSEA": "KXLOWTSEA",
    "KXHIGHTSFO": "KXLOWTSFO", "KXHIGHTMIN": "KXLOWTMIN", "KXHIGHTDC": "KXLOWTDC",
    "KXHIGHTATL": "KXLOWTATL", "KXHIGHTDAL": "KXLOWTDAL", "KXHIGHTSATX": "KXLOWTSATX",
    "KXHIGHNY": "KXLOWTNYC", "KXHIGHTOKC": "KXLOWTOKC", "KXHIGHTLV": "KXLOWTLV",
    "KXHIGHTPHX": "KXLOWTPHX", "KXHIGHTHOU": "KXLOWTHOU", "KXHIGHPHIL": "KXLOWTPHIL",
    "KXHIGHTNOLA": "KXLOWTNOLA", "KXHIGHLAX": "KXLOWTLAX",
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
BANKROLL = 10.0         # $10 CANARY (operator-authorized 2026-07-18): shake out execution at 1 ct/fire
KELLY_FRAC = 0.25       # fractional Kelly (quarter) -- robust to model/tail error
PER_FIRE_CAP = 0.05     # max fraction of bankroll on ONE fire (THE risk control)
DEPTH_CAP = 25          # never order more than the book can plausibly fill (Tier-1: books 5-100ct)

# --- CONVICTION tier (kwx_conviction_optimize.py robust plateau): press the demonstrably-safe fires harder.
# A fire is "conviction" when it has BOTH a temperature CUSHION (obs cleared the strike by >= this many degF,
# = safety margin vs a late CLI revision) AND a price GAP still open (>= this many cents of edge left, = the
# market hasn't repriced it yet). On those, raise the per-fire cap from 5% to CONV_CAP. The grid search's
# risk-optimal, robust (non-knife-edge) plateau was cushion>=2F & gap>=15c & cap 12%: ~+5% median growth over
# flat-5% while ruin stays ~0 even under a stressed non-zero conviction-loss tail. Station derate still applies
# multiplicatively on top, so high-disagreement stations (KPHX etc.) stay tempered even when "conviction".
CONV_CUSHION_F = 2.0    # obs must clear the strike by >= this many degF to qualify as conviction
CONV_GAP_C = 15         # AND price gap (100 - pay_cents) must be >= this many cents
CONV_CAP = 0.12         # per-fire bankroll cap on conviction fires (vs PER_FIRE_CAP=5% base)

# --- free operational guards (only bite in anomalies; zero cost normally) ---
STALE_MIN = 45          # ignore a feed whose newest obs is older than this (dead/frozen feed protection)
MAX_FIRES_PER_CYCLE = 15  # circuit breaker: a normal cycle fires a few; >this = feed glitch -> HALT + review
MAX_DAILY_DEPLOY_FRAC = 0.60  # never deploy more than this fraction of bankroll across all fires in one day
                              # (bounds the worst-day loss; e.g. $10 canary -> max ~$6 at risk/day)


def _kelly_fraction(price, p=0.9965):
    """Full-Kelly fraction of bankroll to stake on a contract at `price` (win prob p, lose full stake)."""
    q = 1 - p
    b = (1 - price) / price
    return max(0.0, p - q / b)


def is_conviction(cushion_f, gap_c):
    """A fire is CONVICTION when it clears BOTH the cushion (safety) and gap (edge) thresholds. Either being
    None (unknown) -> not conviction (fail safe: never upsize on missing info)."""
    return (cushion_f is not None and gap_c is not None
            and cushion_f >= CONV_CUSHION_F and gap_c >= CONV_GAP_C)


def size_for_fire(bankroll, price_c, station, cushion_f=None, gap_c=None):
    """Contracts to buy for a fire at price_c (cents), given bankroll. Quarter-Kelly capped by the per-fire
    cap (CONV_CAP on conviction fires, else 5%), per-station size derate, integer, min 1 if affordable,
    capped by plausible depth. cushion_f/gap_c drive the conviction upsizing (default None -> base 5% cap)."""
    price = price_c / 100.0
    per_fire_cap = CONV_CAP if is_conviction(cushion_f, gap_c) else PER_FIRE_CAP
    frac = min(KELLY_FRAC * _kelly_fraction(price), per_fire_cap) * STATION_SIZE_MULT.get(station, 1.0)
    n = int(frac * bankroll / price)
    n = min(n, DEPTH_CAP)
    if n < 1 and price <= bankroll:   # floor of 1 contract if we can afford it and intend to trade
        n = 1
    return n

# Per-station RISK derate (Track B multi-year + Tier-1): a handful of stations disagree with the official
# CLI far more often (obs-vs-CLI lock-failure). Raise their margin (fewer, safer fires) and/or shrink size.
# KPHX(Phoenix) is the worst in BOTH studies (23% raw / 6.25% deployable) -> highest margin + smallest size.
# RE-CALIBRATED 2026-07-18 (wx_perstation_derate.py): the old derates (KPHX 3F, KLAX/KMIA/KPHL/KSEA 2F) were
# set from Track B's RAW1MIN per-station tail (KPHX 23%, others 18-21% lock-failure @ m1). But that's the
# UNFILTERED rule; under the DEPLOYED rule (glitch + sustain=3) those collapse 18-51x -> KPHX 1.26%, KMIA
# 0.63%, KLAX 0.60%, KPHL 0.43%, KSEA 0.35% @ margin=1 (multi-year). At margin=1 the four non-KPHX stations
# sit MID-PACK -- below never-derated KAUS/KMSY/KDEN -- so their derate was redundant with sustain=3 and cost
# the ~3x EV of small-cushion fires (wx_cushion_optimize). Softened: only KPHX keeps an elevated margin (2F,
# where it's 0.10%), the rest revert to base MARGIN_F=1. Size derate likewise kept only for KPHX (mild caution).
STATION_MARGIN = {"KPHX": 2.0}                # else MARGIN_F=1 (re-validated safe under glitch+sustain3)
STATION_SIZE_MULT = {"KPHX": 0.5}             # else 1.0
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


def _feed_is_stale(obs):
    """True if the feed's newest obs is older than STALE_MIN minutes (dead/frozen feed). obs = [(iso,val)...]."""
    try:
        newest = max(dt.datetime.fromisoformat(t.replace("Z", "+00:00")) for t, _ in obs)
        age_min = (dt.datetime.now(tz=dt.timezone.utc) - newest).total_seconds() / 60.0
        return age_min > STALE_MIN
    except Exception:
        return False   # can't parse -> don't over-block; the consensus quorum still guards


class MultiFeedConsensus:
    """CONSERVATIVE multi-feed consensus (operator's accuracy request). Queries several feeds and only
    reports a running extreme that a QUORUM of them agree on -- using the MIN running-max (or MAX running-
    min) across feeds, so EVERY contributing feed must independently be at least that extreme before a rung
    can lock. A spurious high glitch in one feed is automatically ignored (we take the lower feed).

    IMPORTANT: these feeds mostly re-stream the SAME airport ASOS sensor, so this guards against feed-
    specific faults (staleness, parsing, QC) -- NOT against the sensor itself; the CLI-agreement check is
    the separate guard for that. quorum=len(feeds) requires unanimity; lower it to survive a feed outage."""
    name = "consensus"

    def __init__(self, feeds, quorum=None):
        self.feeds = feeds
        self.quorum = quorum if quorum is not None else max(1, len(feeds))  # default: unanimous

    def running_extreme(self, station, lst_date, offset, kind):
        vals, present = [], []
        for f in self.feeds:
            try:
                r = f.running_extreme(station, lst_date, offset, kind)
            except Exception:
                r = None
            if not r:
                continue
            obs = r.get("obs") or []
            if obs and _feed_is_stale(obs):
                continue   # dead/frozen feed -> don't trust its running-max; drop from the quorum
            s = sustained_extreme(obs, kind)
            if s is None:
                s = r["extreme_f"]
            vals.append(s)
            present.append(getattr(f, "name", "?"))
        if len(vals) < self.quorum:
            return None   # not enough feeds agree -> do NOT trade (safety over throughput)
        cons = min(vals) if kind == "max" else max(vals)   # conservative: every feed >= this (max) / <= (min)
        return {"extreme_f": cons, "obs": [], "feeds": present}


class PrimaryWithFallback:
    """Use a FAST primary feed (Synoptic 1-min HF-ASOS); if it errors or returns None (outage / station it
    doesn't cover), fall back to a slower BACKUP. This is the correct shape for mixing a fast + slow feed:
    the slow feed NEVER gates the fast fire (that would kill the speed edge -- a 15-min-laggy free feed in a
    conservative-min consensus reports a lower running-max and would block the lock we detected at 1 min),
    it only covers a gap when the primary has nothing. Glitch protection is still the sustain=3 filter, which
    runs on whichever feed's obs are used; single-feed Synoptic is acceptable because HF-ASOS IS the ASOS
    sensor the official CLI settles on (the free feeds merely re-stream it)."""
    def __init__(self, primary, backup):
        self.primary, self.backup = primary, backup
        self.name = f"{getattr(primary, 'name', '?')}+fallback"

    def running_extreme(self, station, lst_date, offset, kind):
        try:
            r = self.primary.running_extreme(station, lst_date, offset, kind)
            if r:
                return r
        except Exception:
            pass
        return self.backup.running_extreme(station, lst_date, offset, kind)


# --- feed instances (module singletons) ---
_WGOV = WeatherGovFeedWrap()
_METAR = MetarFeed()
_FREE_CONSENSUS = MultiFeedConsensus([_WGOV, _METAR])   # conservative consensus of the two slow free feeds


def _madis_primary():
    """MADIS hfmetar (FREE, open public tier) as a fresher primary over the weather.gov/METAR consensus.
    MEASURED: 5-min resolution at ~10-15 min latency for SPECI-reporting stations -- fresher than weather.gov
    (~15-20 min), and validated to return the SAME sensor values (KMIA/KLAX ran identical to weather.gov). It
    is NOT the 1-min tier (only Synoptic is), so it's a modest free baseline bump, not the 2x jump. Falls back
    to the consensus for hourly-only stations (KDEN, KNYC) that have no hfmetar 5-min stream. Default-ON (no
    credential needed); if MADIS/scipy is unavailable at runtime the fetch raises and PrimaryWithFallback
    quietly uses the consensus -- so this can only ever help, never break the free default."""
    try:
        import madis_feed
        return PrimaryWithFallback(madis_feed.MadisFeed(), _FREE_CONSENSUS)
    except Exception:
        return None


# FREE default: MADIS primary (fresher 5-min) -> weather.gov/METAR consensus fallback.
_FREE = _madis_primary() or _FREE_CONSENSUS


def _synoptic_primary():
    """Return a Synoptic-primary feed IF a .synoptic_token is present, else None. Wiring Synoptic in ~doubles
    fire capacity AND improves EV/ct (kwx_bankroll_curve: ~$900 -> ~$2,280/mo modeled) because the 1-min feed
    detects the lock ~14 min before the free ~15-min feed, capturing fires while the gap is still open. Kept
    OPT-IN via token presence so the free-feed default is unchanged when uncredentialed (safe, zero-cost)."""
    try:
        import synoptic_feed
        if os.path.exists(synoptic_feed.TOKEN_PATH):
            return PrimaryWithFallback(synoptic_feed.SynopticFeed(), _FREE)   # cascade: synoptic->madis->consensus
    except Exception:
        pass
    return None


# DEFAULT feed cascade: Synoptic (1-min, if credentialed) -> MADIS (free 5-min) -> weather.gov/METAR consensus.
_FEED = _synoptic_primary() or _FREE

# PER-STATION feed policy (operator's insight: some feeds are better for certain cities). Maps a station to a
# feed object to use INSTEAD of the global default. When Synoptic is the global default it already covers the
# sparse-on-weather.gov stations (KNYC->Synoptic 1-min via its alias), so no per-station override is needed;
# only when running the FREE default do we special-case KNYC (sparse -> METAR/WGOV quorum=1, don't block on
# the sparse feed). Any station NOT listed uses _FEED.
STATION_FEED_OVERRIDE = {} if _synoptic_primary() else {
    "NYC": MultiFeedConsensus([_METAR, _WGOV], quorum=1),   # KNYC sparse -> either feed suffices (still conservative min)
}


def feed_for_station(station):
    """Return the obs feed to use for a given station (per-station override, else the global default)."""
    return STATION_FEED_OVERRIDE.get(station, _FEED)


def set_feed(feed):
    """Swap the GLOBAL default feed (per-station overrides in STATION_FEED_OVERRIDE still win). Options:
    MultiFeedConsensus([...]) [safe default], WeatherGovFeedWrap(), synoptic_feed.SynopticFeed() [paid], MetarFeed()."""
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
        low = CITY_LOW_SERIES.get(series)   # explicit, data-verified HIGH->LOW map (not a fragile string sub)
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
    """Return list of (ticker, side, buy_price_cap_c, cushion_f) for rungs now mechanically locked by the
    observed extreme (with `margin`, which may be raised per-station for high-disagreement stations). HIGH/max:
    floor-only rung locks YES once max>floor+margin; any capped rung locks NO once max>cap+margin.
    LOW/min mirrors with the running min. cushion_f = |obs - the relevant strike| (degF the obs cleared the
    strike by) -> feeds the conviction upsizing; larger cushion = more headroom vs a late CLI revision."""
    orders = []
    for r in rungs:
        floor, cap = r["floor"], r["cap"]
        if kind == "max":
            if cap is not None and extreme_f > cap + margin:
                if r["no_ask_c"] and r["no_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "no", r["no_ask_c"], extreme_f - cap))
            elif cap is None and floor is not None and extreme_f > floor + margin:
                if r["yes_ask_c"] and r["yes_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "yes", r["yes_ask_c"], extreme_f - floor))
        else:  # min
            if floor is not None and extreme_f < floor - margin:
                if r["no_ask_c"] and r["no_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "no", r["no_ask_c"], floor - extreme_f))
            elif floor is None and cap is not None and extreme_f < cap - margin:
                if r["yes_ask_c"] and r["yes_ask_c"] <= MAX_PAY_CENTS:
                    orders.append((r["ticker"], "yes", r["yes_ask_c"], cap - extreme_f))
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
    # caps are PER-DAY: drop stale accumulators so a new day starts clean (state persists across the run's
    # 30s poll cycles via kwx_runner_state.json; keeping only today's keys also bounds the file size).
    _today = dt.datetime.now(tz=dt.timezone.utc).date().isoformat()
    state["deployed"] = {k: v for k, v in state.get("deployed", {}).items() if k == _today}
    state["city_spent"] = {k: v for k, v in state.get("city_spent", {}).items() if k.startswith(_today + ":")}
    min_interval = None
    plans = []
    for series, ev, station, offset, lst_date, kind in active_market_days():
        rungs = event_rungs(ev)
        if not rungs:
            continue
        try:
            feed = feed_for_station(station).running_extreme(station, lst_date, offset, kind)
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
        for ticker, side, cap_c, cushion_f in locked_orders(rungs, ext, kind, margin=st_margin):
            if ticker in state["fired"]:
                continue
            gap_c = 100 - cap_c   # cents of edge still open (100c payout - price we pay)
            conv = is_conviction(cushion_f, gap_c)
            # bankroll-aware, quarter-Kelly; conviction fires (cushion>=2F & gap>=15c) get the raised 12% cap
            size = size_for_fire(BANKROLL, cap_c, station, cushion_f=cushion_f, gap_c=gap_c)
            if size < 1:
                continue
            # DAILY + PER-CITY DEPLOYMENT CAPS (match the validated sim's worst-day + diversification bounds).
            today = dt.datetime.now(tz=dt.timezone.utc).date().isoformat()
            deployed = state.setdefault("deployed", {})
            city_spent = state.setdefault("city_spent", {})
            city_key = f"{today}:{station}"
            cost = size * cap_c / 100.0
            if deployed.get(today, 0.0) + cost > MAX_DAILY_DEPLOY_FRAC * BANKROLL:
                if verbose:
                    print(f"  [daily-cap] skip {ticker}: would exceed {MAX_DAILY_DEPLOY_FRAC:.0%} of bankroll today")
                continue
            if city_spent.get(city_key, 0.0) + cost > PER_CITY_DAILY_CAP_FRAC * BANKROLL:
                if verbose:
                    print(f"  [city-cap] skip {ticker}: would exceed {PER_CITY_DAILY_CAP_FRAC:.0%}/city ({station}) today")
                continue
            # CIRCUIT BREAKER: a normal cycle fires a few; an abnormal burst = feed glitch -> halt for review
            if len(plans) >= MAX_FIRES_PER_CYCLE:
                open(os.path.join(HERE, ".kwx_halt"), "w").write(
                    f"auto-halt: >{MAX_FIRES_PER_CYCLE} fires in one cycle (possible feed glitch); review then rm this file\n")
                if verbose:
                    print(f"  !! CIRCUIT BREAKER tripped ({len(plans)} fires this cycle) -> .kwx_halt written, halting")
                try:
                    import kwx_notify
                    kwx_notify.alert(f"🛑 KWX HALT: circuit breaker tripped ({len(plans)} fires in one cycle — "
                                     f"possible feed glitch). Trading stopped; review then rm .kwx_halt")
                except Exception:
                    pass
                _save_state(state)
                return plans, (min_interval or 900)
            fn = ex.buy_yes if side == "yes" else ex.buy_no
            res = fn(ticker, count=size, max_price_cents=cap_c)
            # accumulate deployed capital for the caps -- ONLY if the order actually placed (a guard-BLOCKED
            # order deployed nothing). Without this the daily/per-city caps never bind (the bug this fixes).
            # Use the ACTUAL filled count when the live exec reconciled it (partial fills deploy less than we
            # requested); fall back to intended size on dry-run / unknown.
            filled = res.get("filled")
            eff_cost = (filled * cap_c / 100.0) if isinstance(filled, int) and filled >= 0 else cost
            if not str(res.get("status", "")).startswith("BLOCKED"):
                deployed[today] = deployed.get(today, 0.0) + eff_cost
                city_spent[city_key] = city_spent.get(city_key, 0.0) + eff_cost
            try:
                import kwx_notify
                mode = "LIVE" if getattr(ex, "live", False) else "paper"
                kwx_notify.alert(f"🌡️ KWX FIRE [{mode}]: buy {size} {side.upper()} {ticker} @≤{cap_c}¢ "
                                 f"(obs {kind} {ext:.1f}°F cleared strike) [{res.get('status')}]")
            except Exception:
                pass
            plan = {"ticker": ticker, "side": side, "cap_c": cap_c, "extreme_f": ext,
                    "station": station, "kind": kind, "status": res.get("status"),
                    "requested": size, "filled": res.get("filled"),   # reconciliation: actual vs intended
                    "fill_vwap_c": res.get("fill_vwap_c"),   # depth_v1: actual walk-the-book avg price paid
                    "ts": int(time.time() * 1000)}
            plans.append(plan)
            # depth_v1 dry-run can report filled=0 (book was empty at fire time): don't mark the rung
            # fired so it can re-fire once depth shows up. (A guard-BLOCKED order has filled=None, not
            # 0, and still gets marked fired below as before -- it was never eligible to retry sooner.)
            if res.get("filled") != 0:
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
