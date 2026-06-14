#!/usr/bin/env python3
"""Fair-value model: NBM NBS bulletin (TXN max + XND sigma) -> calibrated P(high in Kalshi bracket).

Pipeline:
 1. Pull NBM NBS text bulletin from NOMADS (hourly cycles).
 2. Parse station block -> daytime TXN max for target date + XND sigma.
 3. Model high ~ Normal(mu=TXN, sigma=XND) (NBM's own calibrated spread).
    NBM observed daily-max sigma ~1.6-4 F; XND IS the per-day calibrated sd.
 4. Integrate the Normal over each Kalshi 2-degree bracket -> fair prob.
 5. Compare to Kalshi book mid -> edge (after spread+fee).

Settlement = integer F (NWS CLI rounds to whole degree). Bracket "85 to 86" = high in {85,86}.
We integrate the continuous Normal over [a-0.5, b+0.5] to account for rounding.
"""
import requests, re
from math import erf, sqrt

H = {'User-Agent': 'kalshi-weather-research dgkenn@bu.edu'}

def latest_nbs(date_yyyymmdd, prefer_cycle=None):
    base = f'https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/blend.{date_yyyymmdd}/'
    # find available cycles
    r = requests.get(base, headers=H, timeout=30)
    cycles = sorted(re.findall(r'href="(\d\d)/"', r.text))
    if prefer_cycle and prefer_cycle in cycles:
        cycles = [prefer_cycle]
    for cyc in reversed(cycles):
        url = f'{base}{cyc}/text/blend_nbstx.t{cyc}z'
        rr = requests.get(url, headers=H, timeout=120)
        if rr.status_code == 200 and len(rr.text) > 1000:
            return rr.text, cyc
    raise RuntimeError('no NBS found')

def parse_station(txt, stn):
    i = txt.find(' '+stn+' ')
    if i < 0: i = txt.find(stn)
    block = txt[i-2:i+1500]
    lines = block.splitlines()
    out = {}
    for ln in lines:
        key = ln[1:5].strip()
        if key in ('DT','UTC','FHR','TXN','XND','TMP','TSD'):
            out.setdefault(key, ln)
    return out, lines

def parse_txn_for_date(blocklines, target_md):
    """Return list of (is_max, value, sigma) aligned to date headers.
    NBS TXN row holds alternating min(night)/max(day). We use the DT row to find
    which 3-hr columns belong to target date, and pick the daytime max within."""
    dt = utc = txn = xnd = None
    for ln in blocklines:
        k = ln[1:5].strip()
        if k=='DT': dt=ln
        elif k=='UTC': utc=ln
        elif k=='TXN': txn=ln
        elif k=='XND': xnd=ln
    return dt, utc, txn, xnd

def norm_cdf(x, mu, sigma):
    return 0.5*(1+erf((x-mu)/(sigma*sqrt(2))))

def bracket_prob(lo, hi, mu, sigma):
    """P(integer high in [lo,hi]) with rounding -> continuous [lo-0.5, hi+0.5]."""
    a = (lo-0.5) if lo is not None else -1e9
    b = (hi+0.5) if hi is not None else 1e9
    return norm_cdf(b,mu,sigma)-norm_cdf(a,mu,sigma)

if __name__ == '__main__':
    txt, cyc = latest_nbs('20260614')
    print('NBS cycle', cyc)
    for stn in ['KNYC','KMDW','KMIA','KAUS']:
        out, lines = parse_station(txt, stn)
        print('\n===', stn, '===')
        for k in ('DT','UTC','TXN','XND'):
            print(out.get(k,''))
