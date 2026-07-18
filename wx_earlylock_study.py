#!/usr/bin/env python3
"""wx_earlylock_study.py -- Phase-1 PREDICTABILITY test for an "EARLY-LOCK" refinement of the K-WX nowcast edge.

WHY: the live nowcast bot only buys a rung AFTER the day's running extreme has MECHANICALLY cleared the strike
(obs_max > strike + margin) -> ~99.6% win, but by then the fast rungs have repriced to ~98-99c ("dead on
arrival"; the profit-gap half-life is ~3.3 min). The operator's idea: use the intraday temperature TRAJECTORY
plus a diurnal climatology to PREDICT that the daily max WILL clear a strike EARLIER than the physical
clearance, so we could buy while the gap is still wide. Trade-off: earlier entry = wider gap (more EV) but
LOWER certainty (some days the curve peaks short). This module measures ONLY the PREDICTABILITY half of that
trade -- can we call clearance early, at what lead, and at what false-positive cost. The price-capture (does a
90c rung actually sit there when we signal, vs the 98c we get today) is FORWARD-ONLY and OUT OF SCOPE here.

Method (HIGH / daily-max case; cleaner because temp rises to an afternoon peak):
  1. Per-station DIURNAL CLIMATOLOGY from the sample: for each 15-min local-time bin, the day-to-day
     distribution of the EXPECTED REMAINING RISE = (final_daily_max - running_max_so_far(t)) and its residual
     std. Built LEAVE-ONE-DAY-OUT per prediction so a day's own final max never leaks into its own estimate.
  2. EARLY-LOCK sim: for each (station, day) sweep strikes S at realized_max-{1..5} (cleared) and
     realized_max+{1,2} (not cleared). Walk the LST day in 5-min steps; at each t compute
     predicted_final = running_max(t) + E[remaining_rise | bin(t)] and P(final > S) via Normal(predicted_final,
     residual_std(t)). Record the EARLIEST t where P >= THRESH (0.95/0.97/0.99). Compare to the mechanical lock
     t_lock = first t where running_max(t) > S. lead_gain = t_lock - t_early (minutes earlier we could act).
  3. Frontier per threshold: n signals, median/p25 lead_gain, and WIN RATE = fraction of early signals whose
     strike actually cleared (1 - false-positive-rate), broken out by strike distance below peak, plus how many
     signals fire while temp is still >1F short of the strike (genuinely predictive, not "already there").

Data (all free): IEM ASOS intraday 5-min trajectory + IEM daily realized max/min. Station coords/tz/network
from wx_forecast_model.STATIONS; LST utc-offset per station from kwx_runner.CITY (fixed standard-time offset,
matches Kalshi settlement calendar). stdlib + numpy/scipy only. No credentials, no orders. TLS via CA bundle.

Usage: python wx_earlylock_study.py   (fetches ~20 stations x ~75 days on first run, caches to ./_earlylock_cache/)
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

# --- study knobs ---
N_DAYS = 75                 # trailing LST days to sample
END_DATE = dt.date(2026, 7, 17)   # last full LST day (yesterday relative to run date)
# NOTE on obs density: IEM's asos.py "5-min" archive returns a 5-min TIME grid but the temp field is 'M'
# (missing) on most slots -- valid temps arrive only at the hourly METAR (:53) plus SPECI specials, so a
# station-day has ~24-49 VALID temps, not ~288. Densest during active rising/peak hours (specials trigger on
# change), which is exactly the window we care about. MIN_OBS is therefore tuned to full-daytime coverage
# (~hourly+specials), NOT the literal 50 -- calling that out as the key data caveat (see report).
MIN_OBS = 18                # skip a station-day with < this many valid intraday temps
STEP = 5                    # minute grid for the forward walk
BIN = 15                    # minute-of-day climatology bin width
MIN_LOO_DAYS = 5            # need >= this many OTHER days in a bin to make an out-of-sample prediction
STD_FLOOR = 0.5             # degF floor on residual std (avoid degenerate 0-std -> false certainty)
THRESHOLDS = (0.95, 0.97, 0.99)
CLEAR_OFFSETS = (-1, -2, -3, -4, -5)   # strikes below peak that DID clear (final_max > S)
MISS_OFFSETS = (1, 2)                    # strikes above peak that did NOT clear
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
    """Cache + return raw IEM intraday temp CSV for station `stn` over UTC [start, end+1). One request/station."""
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
    """Cache + return IEM daily realized max/min CSV for cross-check of the intraday-derived daily max."""
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


def parse_daily(txt):
    out = {}
    for ln in txt.splitlines():
        if not ln or ln.startswith("#") or ln.startswith("station"):
            continue
        p = ln.split(",")
        if len(p) < 3:
            continue
        try:
            d = dt.datetime.strptime(p[1].strip(), "%Y-%m-%d").date()
            mx = float(p[2]) if p[2].strip() not in ("", "None", "M") else None
        except (ValueError, IndexError):
            continue
        out[d] = mx
    return out


def running_and_final(obs):
    """From [(minute, tmpf)] for one LST day -> (running_max grid array len NGRID, final_max float).
    running_max[i] = max temp with minute <= i*STEP, or nan if no obs yet. final_max = max over the whole day."""
    obs = sorted(obs)
    grid = np.full(NGRID, np.nan)
    fmax = max(t for _, t in obs)
    j, cur = 0, -np.inf
    for i in range(NGRID):
        tt = i * STEP
        while j < len(obs) and obs[j][0] <= tt:
            cur = max(cur, obs[j][1]); j += 1
        if cur > -np.inf:
            grid[i] = cur
    return grid, fmax


def build_days(stn, start, end):
    """Return {lst_date: {'run': grid, 'final': fmax}} for the station, keeping only in-range days with
    >= MIN_OBS valid obs. Also returns (n_days_kept, n_days_skipped_thin, daily_xcheck_absdiff_list)."""
    offset = STATION_OFFSET[stn]
    raw = parse_intraday(fetch_intraday(stn, start, end), offset)
    dref = parse_daily(fetch_daily(stn, start, end))
    kept, thin, xdiff = {}, 0, []
    d = start
    while d <= end:
        obs = raw.get(d, [])
        if len(obs) >= MIN_OBS:
            grid, fmax = running_and_final(obs)
            kept[d] = {"run": grid, "final": fmax}
            if dref.get(d) is not None:
                xdiff.append(abs(fmax - dref[d]))
        elif obs:
            thin += 1
        d += dt.timedelta(days=1)
    return kept, thin, xdiff


def climatology(days):
    """Per-station remaining-rise climatology, aggregated per (day, bin) so each day weighs equally.
    Returns bin_samples[bin] = list of (lst_date, mean_remaining_rise_that_day_that_bin)."""
    nb = (24 * 60) // BIN
    bin_samples = {b: [] for b in range(nb)}
    tmin = np.arange(NGRID) * STEP
    binof = tmin // BIN
    for d, rec in days.items():
        run, fmax = rec["run"], rec["final"]
        rise = fmax - run                    # nan where run is nan (no obs yet)
        for b in range(nb):
            m = (binof == b) & ~np.isnan(rise)
            if m.any():
                bin_samples[b].append((d, float(np.mean(rise[m]))))
    return bin_samples


def loo_estimate(bin_samples, b, day):
    """Leave-one-day-out expected remaining rise + residual std for a bin, EXCLUDING `day`.
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


def simulate():
    start = END_DATE - dt.timedelta(days=N_DAYS - 1)
    stations = list(CITY.values())
    stations = sorted({s for s, _ in stations})   # 20 unique stations
    # signal records: dict per (threshold, distance_below_peak) and pooled
    recs = []                       # each: (thresh, dist, cleared_bool, lead_gain or nan, predictive_bool)
    meta = {"stations": 0, "day_kept": 0, "day_thin": 0, "xdiff": [], "cov_bins": [], "day_eval": 0}

    for si, stn in enumerate(stations, 1):
        try:
            days, thin, xdiff = build_days(stn, start, END_DATE)
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
            fmax = rec["final"]
            peak = int(round(fmax))
            for off in CLEAR_OFFSETS + MISS_OFFSETS:
                S = peak + off
                cleared = fmax > S
                # mechanical lock: first grid time running_max > S
                lock_idx = np.where(run > S)[0]
                t_lock = int(lock_idx[0] * STEP) if len(lock_idx) else None
                # early signal per threshold
                P = norm.sf(S, pf, sd)          # P(final > S); nan where pf nan
                for th in THRESHOLDS:
                    hit = np.where(valid & (P >= th))[0]
                    if not len(hit):
                        continue
                    ie = int(hit[0]); t_early = ie * STEP
                    lead = (t_lock - t_early) if (cleared and t_lock is not None) else np.nan
                    predictive = bool(run[ie] <= S - 1)   # temp still >1F short of strike when we fired
                    recs.append((th, off, cleared, lead, predictive))
    return recs, meta


def pct(a, q):
    a = np.asarray([x for x in a if not np.isnan(x)])
    return float(np.percentile(a, q)) if len(a) else float("nan")


def report(recs, meta):
    R = np.array([(th, off, int(cl), lead, int(pr)) for (th, off, cl, lead, pr) in recs], dtype=float) \
        if recs else np.empty((0, 5))
    print("=" * 96)
    print("EARLY-LOCK Phase-1 predictability study -- K-WX daily-HIGH case")
    print(f"stations used: {meta['stations']}/20   trailing LST days requested: {N_DAYS}   "
          f"station-days kept: {meta['day_kept']}   thin-day skips (<{MIN_OBS} obs): {meta['day_thin']}")
    xd = np.asarray(meta["xdiff"])
    if len(xd):
        print(f"intraday-vs-IEM-daily max x-check: n={len(xd)}  median|diff|={np.median(xd):.2f}F  "
              f"p90|diff|={np.percentile(xd,90):.2f}F  (self-consistency of our LST daily-max)")
    if len(meta["cov_bins"]):
        print(f"climatology bin coverage (frac 15-min bins with >= {MIN_LOO_DAYS} LOO days): "
              f"mean {np.mean(meta['cov_bins'])*100:.0f}% across stations")
    print(f"total early signals fired: {len(recs)}")
    print("=" * 96)

    print("\nFRONTIER by threshold (pooled over all swept strikes; win rate folds in the +1/+2 miss strikes)")
    print(f"{'thr':>5} {'n_sig':>7} {'win%':>7} {'n_false':>8} {'med_lead':>9} {'p25_lead':>9} "
          f"{'predict%':>9}")
    for th in THRESHOLDS:
        sub = R[R[:, 0] == th] if len(R) else R
        if not len(sub):
            print(f"{th:>5.2f}   (no signals)"); continue
        n = len(sub)
        winr = 100.0 * sub[:, 2].mean()               # frac of signals on strikes that actually cleared
        n_false = int((sub[:, 2] == 0).sum())          # signals on +1/+2 strikes = false locks
        leads = sub[sub[:, 2] == 1][:, 3]
        print(f"{th:>5.2f} {n:>7d} {winr:>6.2f}% {n_false:>8d} {pct(leads,50):>9.1f} "
              f"{pct(leads,25):>9.1f} {100.0*sub[:,4].mean():>8.1f}%")

    print("\nFRONTIER by strike distance below peak (threshold rows within each) -- deeper = safer/earlier")
    print(f"{'thr':>5} {'dist':>5} {'n_sig':>7} {'win%':>7} {'med_lead':>9} {'p25_lead':>9} {'predict%':>9}")
    for th in THRESHOLDS:
        for dist in (1, 3, 5):
            sub = R[(R[:, 0] == th) & (R[:, 1] == -dist)] if len(R) else R
            if not len(sub):
                continue
            leads = sub[:, 3]
            print(f"{th:>5.2f} {('peak-'+str(dist)):>5} {len(sub):>7d} {100.0*sub[:,2].mean():>6.1f}% "
                  f"{pct(leads,50):>9.1f} {pct(leads,25):>9.1f} {100.0*sub[:,4].mean():>8.1f}%")

    ndays = max(1, meta["day_eval"])
    print(f"\nMISS-STRIKE false positives (peak+1, peak+2 -- these NEVER cleared; any signal = false lock). "
          f"FP-rate denom = {ndays} eval station-days")
    print(f"{'thr':>5} {'strike':>7} {'n_false_sig':>12} {'FP_rate':>9}")
    for th in THRESHOLDS:
        for off in MISS_OFFSETS:
            sub = R[(R[:, 0] == th) & (R[:, 1] == off)] if len(R) else R
            print(f"{th:>5.2f} {('peak+'+str(off)):>7} {len(sub):>12d} {100.0*len(sub)/ndays:>8.1f}%")

    # headline number: >=98% win rate on strikes >= 2F below peak -> median lead
    print("\n" + "=" * 96)
    for th in THRESHOLDS:
        deep = R[(R[:, 0] == th) & (np.isin(R[:, 1], [-2, -3, -4, -5]))] if len(R) else R
        if not len(deep):
            continue
        winr = 100.0 * deep[:, 2].mean()
        med = pct(deep[deep[:, 2] == 1][:, 3], 50)
        flag = ">=98% WIN" if winr >= 98 else "below 98%"
        print(f"thr {th:.2f}: strikes >=2F below peak -> win {winr:.2f}% [{flag}], "
              f"median lead {med:.1f} min, n={len(deep)}")
    print("=" * 96)


if __name__ == "__main__":
    t0 = time.time()
    recs, meta = simulate()
    report(recs, meta)
    print(f"\n(done in {time.time()-t0:.0f}s; cache: {CACHE})")
