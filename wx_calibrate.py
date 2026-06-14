#!/usr/bin/env python3
"""wx_calibrate.py -- assemble forecast-vs-realized data and VALIDATE calibration.

DATA
  forecast (no lookahead): Open-Meteo historical-forecast-api archived operational forecast
    (daily temperature_2m_max), per Kalshi settlement (lat,lon). This is the stored short-range
    (~day-ahead) forecast -- the lead Kalshi's next-day market trades. Multi-year.
  ensemble: Open-Meteo ensemble-api (GEFS 31 members) -- only ~92 days archived, used for the
    ensemble-model calibration sample.
  realized (truth): IEM ASOS daily max_tmpf at the EXACT Kalshi settlement station (Central Park,
    Midway, Camp Mabry, ...). NOT ERA5 (urban cool bias).

OUTPUT
  - per-city next-day forecast-error bias & sigma (the bracket-width driver)
  - calibration of each model on a HOLDOUT: PIT histogram, reliability (predicted-prob vs
    hit-rate), Brier, CRPS-proxy, log-loss
  - the decisive test: can the best model reliably call the warm-tail / above-mode brackets?

Caches raw pulls to wx_cache/ so re-runs cost no API calls.
"""
from __future__ import annotations
import json, os, time, math, sys
from datetime import date
import numpy as np
import requests

from wx_fairvalue import STATIONS, normal_probs, ensemble_probs, skewt_probs

H = {'User-Agent': 'kalshi-wx-calibration dgkenn@bu.edu'}
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wx_cache')
os.makedirs(CACHE, exist_ok=True)

HIST_FC = 'https://historical-forecast-api.open-meteo.com/v1/forecast'
ENS = 'https://ensemble-api.open-meteo.com/v1/ensemble'
IEM = 'https://mesonet.agron.iastate.edu/api/1/daily.json'


def _get(url, params, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=H, timeout=120)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                return {'_429': True, 'reason': r.text[:200]}
            time.sleep(1.5 * (i + 1))
        except Exception as e:
            time.sleep(1.5 * (i + 1))
    return None


def fetch_forecast(st, start, end):
    fp = os.path.join(CACHE, f'fc_{st.city}_{start}_{end}.json')
    if os.path.exists(fp):
        return json.load(open(fp))
    j = _get(HIST_FC, dict(latitude=st.lat, longitude=st.lon, start_date=start, end_date=end,
                           daily='temperature_2m_max', temperature_unit='fahrenheit',
                           timezone='America/New_York', models='gfs_seamless'))
    if j and 'daily' in j:
        out = dict(zip(j['daily']['time'], j['daily']['temperature_2m_max']))
        json.dump(out, open(fp, 'w'))
        return out
    print(f'  forecast fetch failed {st.city}:', (j or {}).get('reason'))
    return {}


def fetch_actuals(st, years):
    """IEM ASOS daily max per month; cached. Returns {date_str: max_tmpf}."""
    out = {}
    for y in years:
        for m in range(1, 13):
            fp = os.path.join(CACHE, f'iem_{st.iem_id}_{y}_{m:02d}.json')
            if os.path.exists(fp):
                rows = json.load(open(fp))
            else:
                j = _get(IEM, dict(station=st.iem_id, network=st.iem_network, year=y, month=m))
                rows = (j or {}).get('data', [])
                json.dump(rows, open(fp, 'w'))
                time.sleep(0.15)
            for d in rows:
                v = d.get('max_tmpf')
                if v is not None:
                    out[d['date']] = float(v)
    return out


def fetch_ensemble(st):
    """GEFS members for the recent ~92d window (only archive available). {date: [members]}."""
    fp = os.path.join(CACHE, f'ens_{st.city}.json')
    if os.path.exists(fp):
        return json.load(open(fp))
    j = _get(ENS, dict(latitude=st.lat, longitude=st.lon, models='gfs025',
                       past_days=92, forecast_days=1,
                       daily='temperature_2m_max', temperature_unit='fahrenheit',
                       timezone='America/New_York'))
    out = {}
    if j and 'daily' in j:
        d = j['daily']
        mem_keys = [k for k in d if k.startswith('temperature_2m_max_member')]
        for i, t in enumerate(d['time']):
            vals = [d[k][i] for k in mem_keys if d[k][i] is not None]
            if vals:
                out[t] = vals
    else:
        print(f'  ensemble fetch failed {st.city}:', (j or {}).get('reason'))
    json.dump(out, open(fp, 'w'))
    return out


# ---------------------------------------------------------------------------------------------
# Calibration metrics
# ---------------------------------------------------------------------------------------------
def pit_values(mu, sigma, actual):
    """Probability Integral Transform: F(actual). Uniform if calibrated. Uses rounding band."""
    from scipy.stats import norm
    # randomized PIT for discrete obs: U over [F(a-0.5), F(a+0.5)]
    lo = norm.cdf(actual - 0.5, mu, sigma)
    hi = norm.cdf(actual + 0.5, mu, sigma)
    return 0.5 * (lo + hi)


def crps_normal(mu, sigma, y):
    """Closed-form CRPS for a Normal forecast (lower is better)."""
    from scipy.stats import norm
    sigma = max(sigma, 0.3)
    z = (y - mu) / sigma
    return sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / math.sqrt(math.pi))


def reliability(probs, hits, nbins=10):
    """probs: predicted P for a set of (event,bracket) cells; hits: 0/1 outcomes.
    Returns list of (bin_mid, mean_pred, hit_rate, n)."""
    probs = np.asarray(probs); hits = np.asarray(hits)
    edges = np.linspace(0, 1, nbins + 1)
    rows = []
    for i in range(nbins):
        m = (probs >= edges[i]) & (probs < edges[i + 1] if i < nbins - 1 else probs <= 1.0)
        if m.sum() >= 5:
            rows.append((0.5 * (edges[i] + edges[i + 1]), float(probs[m].mean()),
                         float(hits[m].mean()), int(m.sum())))
    return rows


def ladder_for(actual_center):
    """Build a Kalshi-style ladder of (lo,hi) integer brackets centered near the forecast."""
    c = int(round(actual_center))
    lo0 = c - 6  # 6F below
    brs = [(None, lo0 - 1)]
    x = lo0
    for _ in range(7):  # seven 2F bins span +/-7F
        brs.append((x, x + 1)); x += 2
    brs.append((x, None))
    return brs


def main():
    years = [2023, 2024, 2025]
    start, end = '2023-01-01', '2025-12-31'
    cities = list(STATIONS)
    print(f'Assembling forecast-vs-realized for {cities}\n window {start}..{end} (+recent ensemble)\n')

    rows = []  # (city, date, fc, actual, err, month)
    per_city_err = {}
    for c in cities:
        st = STATIONS[c]
        fc = fetch_forecast(st, start, end)
        ac = fetch_actuals(st, years)
        errs = []
        for ds, f in fc.items():
            a = ac.get(ds)
            if a is None or f is None:
                continue
            err = f - a
            mo = int(ds[5:7])
            rows.append((c, ds, f, a, err, mo))
            errs.append(err)
        if errs:
            errs = np.array(errs)
            per_city_err[c] = dict(n=len(errs), bias=float(errs.mean()),
                                   sigma=float(errs.std(ddof=1)),
                                   mae=float(np.mean(np.abs(errs))))
        print(f'  {c}: {len(errs)} paired days  bias={per_city_err.get(c,{}).get("bias",float("nan")):+.2f}F '
              f'sigma={per_city_err.get(c,{}).get("sigma",float("nan")):.2f}F '
              f'mae={per_city_err.get(c,{}).get("mae",float("nan")):.2f}F')

    if not rows:
        print('NO DATA assembled (API quota?). Cache dir:', CACHE)
        return

    # ----- per-season sigma (warm vs cool) -----
    print('\nPer-city seasonal next-day forecast error (sigma, F):')
    print(f'  {"city":<5}{"warm(MJJAS)":>13}{"cool(NDJFM)":>13}{"all":>8}')
    season_params = {}
    for c in cities:
        cr = [r for r in rows if r[0] == c]
        if not cr:
            continue
        warm = np.array([r[4] for r in cr if r[5] in (5,6,7,8,9)])
        cool = np.array([r[4] for r in cr if r[5] in (11,12,1,2,3)])
        allc = np.array([r[4] for r in cr])
        sw = warm.std(ddof=1) if warm.size>2 else float('nan')
        sc = cool.std(ddof=1) if cool.size>2 else float('nan')
        season_params[c] = dict(warm_bias=float(np.nanmean(warm)) if warm.size else 0.0,
                                 warm_sigma=float(sw) if sw==sw else allc.std(ddof=1),
                                 cool_bias=float(np.nanmean(cool)) if cool.size else 0.0,
                                 cool_sigma=float(sc) if sc==sc else allc.std(ddof=1),
                                 all_bias=float(allc.mean()), all_sigma=float(allc.std(ddof=1)))
        print(f'  {c:<5}{sw:>13.2f}{sc:>13.2f}{allc.std(ddof=1):>8.2f}')

    # ----- CALIBRATION on holdout (train 2023-24, test 2025) -----
    print('\n=== CALIBRATION (train 2023-2024, holdout TEST 2025) ===')
    train = [r for r in rows if r[1] < '2025-01-01']
    test  = [r for r in rows if r[1] >= '2025-01-01']
    print(f'train n={len(train)}  test n={len(test)}')

    # fit per-city bias+sigma on train (overall + seasonal)
    fit = {}
    for c in cities:
        tr = [r for r in train if r[0]==c]
        if len(tr) < 30:
            continue
        e = np.array([r[4] for r in tr])
        # seasonal sigma model
        ew = np.array([r[4] for r in tr if r[5] in (5,6,7,8,9)])
        ec = np.array([r[4] for r in tr if r[5] in (11,12,1,2,3)])
        fit[c] = dict(bias=float(e.mean()), sigma=float(e.std(ddof=1)),
                      warm_b=float(ew.mean()) if ew.size>2 else float(e.mean()),
                      warm_s=float(ew.std(ddof=1)) if ew.size>2 else float(e.std(ddof=1)),
                      cool_b=float(ec.mean()) if ec.size>2 else float(e.mean()),
                      cool_s=float(ec.std(ddof=1)) if ec.size>2 else float(e.std(ddof=1)))

    # evaluate models on TEST: build a bracket ladder per day around the (bias-corrected) forecast,
    # score each bracket's predicted prob vs realized hit.
    from scipy.stats import norm as N
    def seas(c, mo):
        f = fit[c]
        if mo in (5,6,7,8,9): return f['warm_b'], f['warm_s']
        if mo in (11,12,1,2,3): return f['cool_b'], f['cool_s']
        return f['bias'], f['sigma']

    results = {}
    for model in ('normal_fixed','normal_seasonal','skewt_seasonal'):
        P, Hh, pit, crps = [], [], [], []
        for c, ds, f, a, err, mo in test:
            if c not in fit:
                continue
            if model == 'normal_fixed':
                b, s = fit[c]['bias'], fit[c]['sigma']
            else:
                b, s = seas(c, mo)
            mu = f - b
            brs = ladder_for(mu)
            if model == 'skewt_seasonal':
                probs = skewt_probs(brs, mu, s, skew=0.6)
            else:
                probs = normal_probs(brs, mu, s)
            # which bracket did actual land in?
            ai = int(round(a))
            for (lo, hi), p in zip(brs, probs):
                lo_ok = (lo is None) or (ai >= lo)
                hi_ok = (hi is None) or (ai <= hi)
                hit = 1 if (lo_ok and hi_ok) else 0
                P.append(p); Hh.append(hit)
            pit.append(pit_values(mu, s, a))
            crps.append(crps_normal(mu, s, a))
        P = np.array(P); Hh = np.array(Hh)
        brier = float(np.mean((P - Hh) ** 2))
        # log-loss with clip
        Pc = np.clip(P, 1e-6, 1-1e-6)
        ll = float(-np.mean(Hh*np.log(Pc) + (1-Hh)*np.log(1-Pc)))
        rel = reliability(P, Hh, nbins=10)
        pit = np.array(pit)
        # PIT uniformity: std should be ~1/sqrt(12)=0.289; mean ~0.5
        results[model] = dict(brier=brier, logloss=ll, crps=float(np.mean(crps)),
                              pit_mean=float(pit.mean()), pit_std=float(pit.std()),
                              rel=rel, n_cells=len(P))
        print(f'\n-- {model} --  Brier={brier:.4f}  LogLoss={ll:.4f}  CRPS={np.mean(crps):.3f}F '
              f'PITmean={pit.mean():.3f} PITstd={pit.std():.3f}  cells={len(P)}')
        print('   reliability (pred -> actual hit-rate, n):')
        for mid, mp, hr, n in rel:
            print(f'     pred~{mp*100:5.1f}%  ->  hit {hr*100:5.1f}%  (n={n})')

    # ----- DECISIVE TEST: warm-tail / above-mode bracket calibration -----
    print('\n=== DECISIVE TEST: warm-tail & above-mode bracket reliability (best model) ===')
    best = min(results, key=lambda m: results[m]['brier'])
    print(f'best by Brier: {best}')
    # recompute, tagging bracket position relative to forecast mode
    tail_P, tail_H = [], []     # >= +3F above corrected forecast (warm tail / above-mode)
    mode_P, mode_H = [], []
    for c, ds, f, a, err, mo in test:
        if c not in fit:
            continue
        if best == 'normal_fixed':
            b, s = fit[c]['bias'], fit[c]['sigma']
        else:
            b, s = seas(c, mo)
        mu = f - b
        brs = ladder_for(mu)
        probs = (skewt_probs(brs, mu, s, 0.6) if best=='skewt_seasonal'
                 else normal_probs(brs, mu, s))
        ai = int(round(a))
        for (lo, hi), p in zip(brs, probs):
            lo_ok = (lo is None) or (ai >= lo)
            hi_ok = (hi is None) or (ai <= hi)
            hit = 1 if (lo_ok and hi_ok) else 0
            center = (mu)
            blo = lo if lo is not None else (hi-1 if hi is not None else center)
            # above-mode / warm tail: bracket lower edge >= mu+2
            if (lo is not None) and (lo >= mu + 2):
                tail_P.append(p); tail_H.append(hit)
            elif (lo is not None and hi is not None) and (lo <= mu <= hi):
                mode_P.append(p); mode_H.append(hit)
    for name, Pp, Hp in [('modal bin', mode_P, mode_H), ('above-mode/warm tail', tail_P, tail_H)]:
        Pp = np.array(Pp); Hp = np.array(Hp)
        if Pp.size:
            print(f'  {name:<22} n={Pp.size:4d}  mean_pred={Pp.mean()*100:5.1f}%  '
                  f'actual_hit={Hp.mean()*100:5.1f}%  (Brier={np.mean((Pp-Hp)**2):.4f})')

    # save summary
    summ = dict(window=f'{start}..{end}', per_city_err=per_city_err,
                season=season_params, holdout=results, best=best,
                tail=dict(n=len(tail_P), mean_pred=float(np.mean(tail_P)) if tail_P else None,
                          hit=float(np.mean(tail_H)) if tail_H else None),
                mode=dict(n=len(mode_P), mean_pred=float(np.mean(mode_P)) if mode_P else None,
                          hit=float(np.mean(mode_H)) if mode_H else None))
    json.dump(summ, open(os.path.join(CACHE, 'summary.json'), 'w'), indent=2)
    print('\nsaved', os.path.join(CACHE, 'summary.json'))


if __name__ == '__main__':
    main()
