#!/usr/bin/env python3
"""wx_earlylock_study.py -- Phase-1 PREDICTABILITY test for an "EARLY-LOCK" refinement of the K-WX nowcast edge.

WHY: the live nowcast bot only buys a rung AFTER the day's running extreme has MECHANICALLY cleared the strike
(obs_max > strike + margin) -> ~99.6% win, but by then the fast rungs have repriced to ~98-99c ("dead on
arrival"; the profit-gap half-life is ~3.3 min). The operator's idea: use the intraday temperature TRAJECTORY
plus a diurnal climatology to PREDICT that the daily extreme WILL clear a strike EARLIER than the physical
clearance, so we could buy while the gap is still wide. Trade-off: earlier entry = wider gap (more EV) but
LOWER certainty (some days the curve peaks short). This module measures ONLY the PREDICTABILITY half of that
trade -- can we call clearance early, at what lead, and at what false-positive cost. The price-capture (does a
90c rung actually sit there when we signal, vs the 98c we get today) is FORWARD-ONLY and OUT OF SCOPE here.

Method -- BOTH cases, sharing one engine because they are exact mirrors:
  HIGH / daily-max ("max"): temp rises to an afternoon peak; running_max only ever rises toward final_max.
  LOW  / daily-min ("min"): temp falls overnight to a pre-dawn trough; running_min only ever falls toward
     final_min. Kalshi KXLOWT settles on the CALENDAR-DAY CLI minimum on the SAME LST date as the HIGH
     (kwx_runner.CITY_LOW_SERIES: lows reuse the high's lst_date/offset; only kind flips to 'min'), so the
     same midnight-to-midnight LST grid applies -- the overnight cooling into the trough happens 00:00->~sunrise
     WITHIN the same LST calendar day, and any rare late-evening frontal drop that resets the day's min also
     lands inside it. No date-boundary shift is needed (verified against the runner's day-window definition).
  1. Per-station DIURNAL CLIMATOLOGY from the sample: for each 15-min local-time bin, the day-to-day
     distribution of the EXPECTED REMAINING CHANGE = (final_extreme - running_extreme_so_far(t)) and its
     residual std. For the max case that's the remaining RISE (>=0); for the min case the remaining FALL
     (<=0) -- one signed quantity, so the identical estimator serves both. Built LEAVE-ONE-DAY-OUT per
     prediction so a day's own final extreme never leaks into its own estimate.
  2. EARLY-LOCK sim: for each (station, day) sweep strikes S around the realized extreme. HIGH: S =
     peak-{1..5} (cleared: final_max > S) and peak+{1,2} (never cleared). LOW mirror: S = trough+{1..5}
     (cleared: final_min < S -- LOW strikes that clear sit ABOVE the trough) and trough-{1,2} (never
     cleared). Walk the LST day in 5-min steps; at each t compute predicted_final = running(t) +
     E[remaining_change | bin(t)] and P(clear) via Normal(predicted_final, residual_std(t)) -- sf for max
     ("final > S"), cdf for min ("final < S"). Record the EARLIEST t where P >= THRESH (0.95/0.97/0.99).
     Compare to the mechanical lock t_lock = first t where running crosses S (above for max, below for min).
     lead_gain = t_lock - t_early (minutes earlier we could act).
  3. Frontier per threshold: n signals, median/p25 lead_gain, and WIN RATE = fraction of early signals whose
     strike actually cleared (1 - false-positive-rate), broken out by strike distance from the extreme, plus
     how many signals fire while temp is still >1F short of the strike (genuinely predictive, not "already
     there" -- for min, "short" means still >1F ABOVE the strike).

Data (all free): IEM ASOS intraday 5-min trajectory + IEM daily realized max/min. Station coords/tz/network
from wx_forecast_model.STATIONS; LST utc-offset per station from kwx_runner.CITY (fixed standard-time offset,
matches Kalshi settlement calendar). stdlib + numpy/scipy only. No credentials, no orders. TLS via CA bundle.

Usage: python wx_earlylock_study.py            # HIGH / daily-max case (the original study)
       python wx_earlylock_study.py --low      # LOW / daily-min mirror
       python wx_earlylock_study.py --dump-climatology   # persist the FIXED live climatology (BOTH cases)
       (fetches ~20 stations x ~75 days on first run, caches to ./_earlylock_cache/ -- shared by both cases)
"""
import os, ssl, sys, time, datetime as dt, urllib.request, urllib.parse, urllib.error
import numpy as np
from scipy.stats import norm

from wx_forecast_model import STATIONS, iem_station
from kwx_runner import CITY

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
DAILY = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_earlylock_cache")
CLIMO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_earlylock_climatology.json")

# --- study knobs ---
N_DAYS = 75                 # trailing LST days to sample
END_DATE = dt.date(2026, 7, 17)   # last full LST day (yesterday relative to run date)
# NOTE on obs density: IEM's asos.py "5-min" archive returns a 5-min TIME grid but the temp field is 'M'
# (missing) on most slots -- valid temps arrive only at the hourly METAR (:53) plus SPECI specials, so a
# station-day has ~24-49 VALID temps, not ~288. Densest during active rising/peak hours (specials trigger on
# change), which is exactly the window we care about. MIN_OBS is therefore tuned to full-daytime coverage
# (~hourly+specials), NOT the literal 50 -- calling that out as the key data caveat (see report). The LOW
# case leans on the pre-dawn hours, where specials are sparser than the afternoon; MIN_OBS is a full-day
# floor so both cases share it, and the report's bin-coverage line shows how well the night bins are served.
MIN_OBS = 18                # skip a station-day with < this many valid intraday temps
STEP = 5                    # minute grid for the forward walk
BIN = 15                    # minute-of-day climatology bin width
MIN_LOO_DAYS = 5            # need >= this many OTHER days in a bin to make an out-of-sample prediction
STD_FLOOR = 0.5             # degF floor on residual std (avoid degenerate 0-std -> false certainty)
THRESHOLDS = (0.95, 0.97, 0.99)
# HIGH case: strikes below the peak DID clear (final_max > S); above it never did.
CLEAR_OFFSETS = (-1, -2, -3, -4, -5)   # strikes below peak that DID clear (final_max > S)
MISS_OFFSETS = (1, 2)                    # strikes above peak that did NOT clear
# LOW mirror: the signs FLIP -- strikes ABOVE the trough clear (final_min < S), below it never do.
CLEAR_OFFSETS_LOW = (1, 2, 3, 4, 5)      # strikes above trough that DID clear (final_min < S)
MISS_OFFSETS_LOW = (-1, -2)              # strikes below trough that did NOT clear
NGRID = (24 * 60) // STEP                 # 288 grid points

# station -> LST utc offset (hours), inverted from kwx_runner.CITY (series -> (station, offset)).
STATION_OFFSET = {stn: off for (stn, off) in CITY.values()}


_LAST_FETCH = [0.0]
MIN_GAP = 2.0   # s between IEM requests (be a polite client; IEM 429s aggressive bursts)


def _fetch(url, to=90, tries=5):
    """GET with a min inter-request gap + exponential backoff on 429/5xx (IEM rate-limits bursts)."""
    for k in range(tries):
        wait = MIN_GAP - (time.time() - _LAST_FETCH[0])
        if wait > 0:
            time.sleep(wait)
        _LAST_FETCH[0] = time.time()
        try:
            return urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": "kwx-earlylock-study/1.0"}), timeout=to,
                context=_CTX).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and k < tries - 1:
                time.sleep(3 * (2 ** k)); continue
            raise


def fetch_intraday(stn, start, end):
    """Cache + return raw IEM intraday temp CSV for station `stn` over UTC [start, end+1). One request/station.
    The SAME cached file serves both the max and min cases (it's the full trajectory), so adding the LOW study
    costs zero extra IEM load once the HIGH cache is warm."""
    os.makedirs(CACHE, exist_ok=True)
    stid = iem_station(stn)
    fp = os.path.join(CACHE, f"asos_{stid}_{start:%Y%m%d}_{end:%Y%m%d}.csv")
    if os.path.exists(fp) and os.path.getsize(fp) > 200:
        return open(fp, encoding="utf-8").read()
    e2 = end + dt.timedelta(days=1)   # LST days at negative offsets spill into the next UTC day
    q = urllib.parse.urlencode({"station": stid, "data": "tmpf",
        "year1": start.year, "month1": start.month, "day1": start.day,
        "year2": e2.year, "month2": e2.month, "day2": e2.day,
        "tz": "UTC", "format": "comma", "missing": "M", "trace": "T"})
    txt = _fetch(f"{ASOS}?{q}")
    open(fp, "w", encoding="utf-8").write(txt)
    return txt


def fetch_daily(stn, start, end):
    """Cache + return IEM daily realized max/min CSV for cross-check of the intraday-derived daily extreme.
    Requests BOTH max_temp_f and min_temp_f, so one cached file serves both cases."""
    os.makedirs(CACHE, exist_ok=True)
    stid = iem_station(stn)
    net = STATIONS[stn][3]
    fp = os.path.join(CACHE, f"daily_{stid}_{start:%Y%m%d}_{end:%Y%m%d}.csv")
    if os.path.exists(fp) and os.path.getsize(fp) > 50:
        return open(fp, encoding="utf-8").read()
    q = urllib.parse.urlencode({"network": net, "stations": stid,
        "year1": start.year, "month1": start.month, "day1": start.day,
        "year2": end.year, "month2": end.month, "day2": end.day,
        "var": "max_temp_f,min_temp_f", "format": "comma"})
    txt = _fetch(f"{DAILY}?{q}")
    open(fp, "w", encoding="utf-8").write(txt)
    return txt


def parse_intraday(txt, offset):
    """Parse IEM CSV -> {lst_date: [(minute_of_day, tmpf), ...]} using the station's fixed LST utc offset."""
    days = {}
    for ln in txt.splitlines():
        if not ln or ln.startswith("#") or ln.startswith("station"):
            continue
        p = ln.split(",")
        if len(p) < 3:
            continue
        v, t = p[1].strip(), p[2].strip()
        if t in ("M", "", "T"):
            continue
        try:
            utc = dt.datetime.strptime(v, "%Y-%m-%d %H:%M")
            tmpf = float(t)
        except ValueError:
            continue
        loc = utc + dt.timedelta(hours=offset)
        days.setdefault(loc.date(), []).append((loc.hour * 60 + loc.minute, tmpf))
    return days


def parse_daily(txt, field="max"):
    """Parse the IEM daily CSV (columns: station, day, max_temp_f, min_temp_f -- the var order we request)
    -> {date: value}. field='max' reads max_temp_f (col 2), field='min' reads min_temp_f (col 3)."""
    idx = 2 if field == "max" else 3
    out = {}
    for ln in txt.splitlines():
        if not ln or ln.startswith("#") or ln.startswith("station"):
            continue
        p = ln.split(",")
        if len(p) <= idx:
            continue
        try:
            d = dt.datetime.strptime(p[1].strip(), "%Y-%m-%d").date()
            val = float(p[idx]) if p[idx].strip() not in ("", "None", "M") else None
        except (ValueError, IndexError):
            continue
        out[d] = val
    return out


def running_and_final(obs, kind="max"):
    """From [(minute, tmpf)] for one LST day -> (running_extreme grid array len NGRID, final_extreme float).
    kind='max': grid[i] = max temp with minute <= i*STEP (running max only ever RISES toward the peak).
    kind='min': grid[i] = min temp with minute <= i*STEP (running min only ever FALLS toward the trough).
    nan where no obs yet. final = the extreme over the whole LST calendar day (= what Kalshi settles on)."""
    obs = sorted(obs)
    grid = np.full(NGRID, np.nan)
    vals = [t for _, t in obs]
    fext = max(vals) if kind == "max" else min(vals)
    j = 0
    cur = -np.inf if kind == "max" else np.inf
    for i in range(NGRID):
        tt = i * STEP
        while j < len(obs) and obs[j][0] <= tt:
            cur = max(cur, obs[j][1]) if kind == "max" else min(cur, obs[j][1])
            j += 1
        if np.isfinite(cur):
            grid[i] = cur
    return grid, fext


def build_days(stn, start, end, kind="max"):
    """Return {lst_date: {'run': grid, 'final': fext}} for the station and case, keeping only in-range days
    with >= MIN_OBS valid obs. Also returns (n_days_skipped_thin, daily_xcheck_absdiff_list) where the
    x-check compares our intraday-derived extreme to IEM's official daily max/min for the same date."""
    offset = STATION_OFFSET[stn]
    raw = parse_intraday(fetch_intraday(stn, start, end), offset)
    dref = parse_daily(fetch_daily(stn, start, end), field=("max" if kind == "max" else "min"))
    kept, thin, xdiff = {}, 0, []
    d = start
    while d <= end:
        obs = raw.get(d, [])
        if len(obs) >= MIN_OBS:
            grid, fext = running_and_final(obs, kind=kind)
            kept[d] = {"run": grid, "final": fext}
            if dref.get(d) is not None:
                xdiff.append(abs(fext - dref[d]))
        elif obs:
            thin += 1
        d += dt.timedelta(days=1)
    return kept, thin, xdiff


def climatology(days):
    """Per-station remaining-CHANGE climatology, aggregated per (day, bin) so each day weighs equally.
    remaining_change = final_extreme - running_extreme(t): the remaining RISE (>=0) for the max case, the
    remaining FALL (<=0) for the min case -- one signed quantity, so this function serves both unchanged.
    Returns bin_samples[bin] = list of (lst_date, mean_remaining_change_that_day_that_bin)."""
    nb = (24 * 60) // BIN
    bin_samples = {b: [] for b in range(nb)}
    tmin = np.arange(NGRID) * STEP
    binof = tmin // BIN
    for d, rec in days.items():
        run, fext = rec["run"], rec["final"]
        chg = fext - run                     # nan where run is nan (no obs yet)
        for b in range(nb):
            m = (binof == b) & ~np.isnan(chg)
            if m.any():
                bin_samples[b].append((d, float(np.mean(chg[m]))))
    return bin_samples


def loo_estimate(bin_samples, b, day):
    """Leave-one-day-out expected remaining change + residual std for a bin, EXCLUDING `day`.
    Returns (mean, std) or None if too few other days."""
    vals = [v for (dd, v) in bin_samples.get(b, []) if dd != day]
    if len(vals) < MIN_LOO_DAYS:
        return None
    a = np.asarray(vals)
    return float(a.mean()), float(max(STD_FLOOR, a.std(ddof=1)))


def predicted_series(days, bin_samples, day):
    """For one day: arrays predicted_final[NGRID] and resid_std[NGRID] (nan where run unknown or no LOO)."""
    run = days[day]["run"]
    pf = np.full(NGRID, np.nan); sd = np.full(NGRID, np.nan)
    for i in range(NGRID):
        if np.isnan(run[i]):
            continue
        est = loo_estimate(bin_samples, (i * STEP) // BIN, day)
        if est is None:
            continue
        pf[i] = run[i] + est[0]; sd[i] = est[1]
    return pf, run, sd


def simulate(kind="max"):
    start = END_DATE - dt.timedelta(days=N_DAYS - 1)
    stations = list(CITY.values())
    stations = sorted({s for s, _ in stations})   # 20 unique stations
    clear_offs, miss_offs = ((CLEAR_OFFSETS, MISS_OFFSETS) if kind == "max"
                             else (CLEAR_OFFSETS_LOW, MISS_OFFSETS_LOW))
    # signal records: dict per (threshold, strike offset from extreme) and pooled
    recs = []                       # each: (thresh, offset, cleared_bool, lead_gain or nan, predictive_bool)
    meta = {"stations": 0, "day_kept": 0, "day_thin": 0, "xdiff": [], "cov_bins": [], "day_eval": 0}

    for si, stn in enumerate(stations, 1):
        try:
            days, thin, xdiff = build_days(stn, start, END_DATE, kind=kind)
        except Exception as e:
            print(f"  [{stn}] fetch/parse failed: {e}", file=sys.stderr); continue
        if len(days) < MIN_LOO_DAYS + 1:
            print(f"  [{stn}] only {len(days)} usable days -- skipped", file=sys.stderr); continue
        meta["stations"] += 1; meta["day_kept"] += len(days); meta["day_thin"] += thin
        meta["xdiff"] += xdiff
        bin_samples = climatology(days)
        # bin coverage: fraction of bins with enough days (informational)
        nb = (24 * 60) // BIN
        meta["cov_bins"].append(np.mean([len(bin_samples[b]) >= MIN_LOO_DAYS for b in range(nb)]))

        for day, rec in days.items():
            pf, run, sd = predicted_series(days, bin_samples, day)
            valid = ~np.isnan(pf)
            if not valid.any():
                continue
            meta["day_eval"] += 1          # station-days with >=1 usable prediction (miss-FP denominator)
            fext = rec["final"]
            anchor = int(round(fext))      # the realized peak (max) / trough (min), whole degrees
            for off in clear_offs + miss_offs:
                S = anchor + off
                cleared = (fext > S) if kind == "max" else (fext < S)
                # mechanical lock: first grid time the running extreme crosses S (above for max, below for min)
                lock_idx = np.where(run > S)[0] if kind == "max" else np.where(run < S)[0]
                t_lock = int(lock_idx[0] * STEP) if len(lock_idx) else None
                # early signal per threshold. P(clear): max -> P(final > S) = sf; min -> P(final < S) = cdf.
                P = norm.sf(S, pf, sd) if kind == "max" else norm.cdf(S, pf, sd)   # nan where pf nan
                for th in THRESHOLDS:
                    hit = np.where(valid & (P >= th))[0]
                    if not len(hit):
                        continue
                    ie = int(hit[0]); t_early = ie * STEP
                    lead = (t_lock - t_early) if (cleared and t_lock is not None) else np.nan
                    # "predictive" = temp still >1F SHORT of the strike when we fired: below it for a max,
                    # ABOVE it for a min (the mirror of "not already there").
                    predictive = bool(run[ie] <= S - 1) if kind == "max" else bool(run[ie] >= S + 1)
                    recs.append((th, off, cleared, lead, predictive))
    return recs, meta


def build_fixed_climatology(end_date=END_DATE, n_days=N_DAYS, verbose=True):
    """FIXED (ALL historical days, NOT leave-one-out) per-station per-15min-bin (E[remaining_change],
    resid_std) for LIVE forward use -- BOTH cases. LOO exists only to prevent a day's own final extreme
    leaking into its own backtest estimate; a live forward day is a genuinely new day never in the sample, so
    pooling ALL cached days is correct (more support, no self-leak). Reuses the exact study machinery
    (build_days -> climatology) so the persisted numbers match the backtested ones. Returns the climatology
    dict and writes it to CLIMO_PATH.

    Shape: {"meta": {...},
            "stations":     {stn: {"<bin_index>": [mean_remaining_rise, resid_std, n_days], ...}, ...},
            "stations_low": {stn: {"<bin_index>": [mean_remaining_fall, resid_std, n_days], ...}, ...}}
    "stations" is the HIGH/max map -- SAME top-level key as the original HIGH-only schema, so any existing
    consumer that reads climo["stations"] keeps working untouched; the LOW/min map is ADDED alongside under
    "stations_low" (its means are <= 0: the expected remaining FALL to the trough). bin_index b covers local
    minute-of-day [b*BIN, (b+1)*BIN); at snapshot time look up b = lst_minute // BIN."""
    import json as _json
    start = end_date - dt.timedelta(days=n_days - 1)
    stations = sorted({s for s, _ in CITY.values()})
    nb = (24 * 60) // BIN
    out = {"meta": {"built_utc": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
                    "end_date": end_date.isoformat(), "n_days": n_days, "bin_min": BIN, "step_min": STEP,
                    "std_floor": STD_FLOOR, "min_days": MIN_LOO_DAYS, "n_bins": nb,
                    "note": "FIXED all-days (no LOO) remaining-change climatology for live early-lock; "
                            "'stations'=HIGH remaining rise, 'stations_low'=LOW remaining fall"},
           "stations": {}, "stations_low": {}}
    for stn in stations:
        # both cases share the SAME cached intraday fetch (build_days re-reads the cache on the second pass),
        # so covering lows costs zero extra IEM requests.
        for kind, key in (("max", "stations"), ("min", "stations_low")):
            try:
                days, thin, xdiff = build_days(stn, start, end_date, kind=kind)
            except Exception as e:
                if verbose:
                    print(f"  [{stn}/{kind}] fetch/parse failed: {e}", file=sys.stderr)
                continue
            if len(days) < MIN_LOO_DAYS + 1:
                if verbose:
                    print(f"  [{stn}/{kind}] only {len(days)} usable days -- skipped", file=sys.stderr)
                continue
            bin_samples = climatology(days)
            binmap = {}
            for b in range(nb):
                vals = [v for (_d, v) in bin_samples.get(b, [])]
                if len(vals) < MIN_LOO_DAYS:
                    continue                   # too few days in this bin -> no live prediction (fail safe)
                a = np.asarray(vals)
                binmap[str(b)] = [round(float(a.mean()), 4),
                                  round(float(max(STD_FLOOR, a.std(ddof=1))), 4), len(vals)]
            if binmap:
                out[key][stn] = binmap
                if verbose:
                    print(f"  [{stn}/{kind}] {len(days)} days -> {len(binmap)}/{nb} bins with climatology")
    with open(CLIMO_PATH, "w") as f:
        _json.dump(out, f)
    if verbose:
        print(f"wrote fixed climatology: {len(out['stations'])} HIGH + {len(out['stations_low'])} LOW "
              f"stations -> {CLIMO_PATH}")
    return out


def pct(a, q):
    a = np.asarray([x for x in a if not np.isnan(x)])
    return float(np.percentile(a, q)) if len(a) else float("nan")


def report(recs, meta, kind="max"):
    R = np.array([(th, off, int(cl), lead, int(pr)) for (th, off, cl, lead, pr) in recs], dtype=float) \
        if recs else np.empty((0, 5))
    case = "daily-HIGH" if kind == "max" else "daily-LOW"
    ext_name = "peak" if kind == "max" else "trough"
    # offsets, oriented so "dist" = degrees on the CLEARING side of the extreme (below peak / above trough)
    clear_sign = -1 if kind == "max" else 1
    miss_offs = MISS_OFFSETS if kind == "max" else MISS_OFFSETS_LOW
    print("=" * 96)
    print(f"EARLY-LOCK Phase-1 predictability study -- K-WX {case} case")
    print(f"stations used: {meta['stations']}/20   trailing LST days requested: {N_DAYS}   "
          f"station-days kept: {meta['day_kept']}   thin-day skips (<{MIN_OBS} obs): {meta['day_thin']}")
    xd = np.asarray(meta["xdiff"])
    if len(xd):
        print(f"intraday-vs-IEM-daily {kind} x-check: n={len(xd)}  median|diff|={np.median(xd):.2f}F  "
              f"p90|diff|={np.percentile(xd,90):.2f}F  (self-consistency of our LST daily-{kind})")
    if len(meta["cov_bins"]):
        print(f"climatology bin coverage (frac 15-min bins with >= {MIN_LOO_DAYS} LOO days): "
              f"mean {np.mean(meta['cov_bins'])*100:.0f}% across stations")
    print(f"total early signals fired: {len(recs)}")
    print("=" * 96)

    print(f"\nFRONTIER by threshold (pooled over all swept strikes; win rate folds in the "
          f"{ext_name}{'+1/+2' if kind == 'max' else '-1/-2'} miss strikes)")
    print(f"{'thr':>5} {'n_sig':>7} {'win%':>7} {'n_false':>8} {'med_lead':>9} {'p25_lead':>9} "
          f"{'predict%':>9}")
    for th in THRESHOLDS:
        sub = R[R[:, 0] == th] if len(R) else R
        if not len(sub):
            print(f"{th:>5.2f}   (no signals)"); continue
        n = len(sub)
        winr = 100.0 * sub[:, 2].mean()               # frac of signals on strikes that actually cleared
        n_false = int((sub[:, 2] == 0).sum())          # signals on miss strikes = false locks
        leads = sub[sub[:, 2] == 1][:, 3]
        print(f"{th:>5.2f} {n:>7d} {winr:>6.2f}% {n_false:>8d} {pct(leads,50):>9.1f} "
              f"{pct(leads,25):>9.1f} {100.0*sub[:,4].mean():>8.1f}%")

    print(f"\nFRONTIER by strike distance from the {ext_name} (threshold rows within each) -- "
          f"deeper = safer/earlier")
    print(f"{'thr':>5} {'dist':>9} {'n_sig':>7} {'win%':>7} {'med_lead':>9} {'p25_lead':>9} {'predict%':>9}")
    for th in THRESHOLDS:
        for dist in (1, 3, 5):
            off = clear_sign * dist
            sub = R[(R[:, 0] == th) & (R[:, 1] == off)] if len(R) else R
            if not len(sub):
                continue
            leads = sub[:, 3]
            lbl = f"{ext_name}{off:+d}"
            print(f"{th:>5.2f} {lbl:>9} {len(sub):>7d} {100.0*sub[:,2].mean():>6.1f}% "
                  f"{pct(leads,50):>9.1f} {pct(leads,25):>9.1f} {100.0*sub[:,4].mean():>8.1f}%")

    ndays = max(1, meta["day_eval"])
    print(f"\nMISS-STRIKE false positives ({ext_name}{miss_offs[0]:+d}, {ext_name}{miss_offs[1]:+d} -- these "
          f"NEVER cleared; any signal = false lock). FP-rate denom = {ndays} eval station-days")
    print(f"{'thr':>5} {'strike':>9} {'n_false_sig':>12} {'FP_rate':>9}")
    for th in THRESHOLDS:
        for off in miss_offs:
            sub = R[(R[:, 0] == th) & (R[:, 1] == off)] if len(R) else R
            print(f"{th:>5.2f} {(ext_name + format(off, '+d')):>9} {len(sub):>12d} "
                  f"{100.0*len(sub)/ndays:>8.1f}%")

    # headline number: >=98% win rate on strikes >= 2F beyond the extreme -> median lead
    deep_offs = [clear_sign * d for d in (2, 3, 4, 5)]
    print("\n" + "=" * 96)
    for th in THRESHOLDS:
        deep = R[(R[:, 0] == th) & (np.isin(R[:, 1], deep_offs))] if len(R) else R
        if not len(deep):
            continue
        winr = 100.0 * deep[:, 2].mean()
        med = pct(deep[deep[:, 2] == 1][:, 3], 50)
        flag = ">=98% WIN" if winr >= 98 else "below 98%"
        side = "below peak" if kind == "max" else "above trough"
        print(f"thr {th:.2f}: strikes >=2F {side} -> win {winr:.2f}% [{flag}], "
              f"median lead {med:.1f} min, n={len(deep)}")
    print("=" * 96)


if __name__ == "__main__":
    t0 = time.time()
    if "--dump-climatology" in sys.argv:
        build_fixed_climatology()
        print(f"\n(done in {time.time()-t0:.0f}s; cache: {CACHE})")
    else:
        kind = "min" if "--low" in sys.argv else "max"
        recs, meta = simulate(kind=kind)
        report(recs, meta, kind=kind)
        print(f"\n(done in {time.time()-t0:.0f}s; cache: {CACHE})")
