#!/usr/bin/env python3
"""Compare Kalshi daily-high-temp book to NBM-implied fair value. Point-in-time snapshot."""
import requests, re, time, json
from math import erf, sqrt
from datetime import datetime, timedelta

H={'User-Agent':'kalshi-weather-research dgkenn@bu.edu'}
KBASE='https://api.elections.kalshi.com/trade-api/v2'

# city -> (NBM station, Kalshi high-temp series, NWS CLI station)
CITIES={
 'NYC':('KNYC','KXHIGHNY'),
 'CHI':('KMDW','KXHIGHCHI'),
 'MIA':('KMIA','KXHIGHMIA'),
 'AUS':('KAUS','KXHIGHAUS'),
 'LAX':('KLAX','KXHIGHLAX'),
 'PHX':('KPHX','KXHIGHTPHX'),
 'DAL':('KDFW','KXHIGHTDAL'),
 'BOS':('KBOS','KXHIGHTBOS'),
}

def norm_cdf(x,mu,s): return 0.5*(1+erf((x-mu)/(s*sqrt(2))))
def bracket_prob(lo,hi,mu,s):
    a=(lo-0.5) if lo is not None else -1e9
    b=(hi+0.5) if hi is not None else 1e9
    return norm_cdf(b,mu,s)-norm_cdf(a,mu,s)

def get_nbs(date,cyc):
    url=f'https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/blend.{date}/{cyc}/text/blend_nbstx.t{cyc}z'
    r=requests.get(url,headers=H,timeout=120)
    return r.text if r.status_code==200 and len(r.text)>1000 else None

def latest_cyc(date):
    base=f'https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/blend.{date}/'
    r=requests.get(base,headers=H,timeout=30)
    return sorted(re.findall(r'href="(\d\d)/"',r.text))

def parse_high(txt, stn, target_date):
    """target_date datetime.date -> (high, sigma) for that local day.
    daytime max = TXN at 00Z of (D+1)."""
    i=txt.find(' '+stn+' ')
    if i<0: return None,None
    lines=txt[i-2:i+1500].splitlines()
    d={ln[1:5].strip():ln for ln in lines if ln[1:5].strip() in ('DT','UTC','TXN','XND')}
    dt=d.get('DT'); utc=d.get('UTC'); txn=d.get('TXN'); xnd=d.get('XND')
    if not all([dt,utc,txn,xnd]): return None,None
    # build per-column (date,hour)
    cols=list(range(5,len(utc),3))
    # Build column-aligned (day_label, txn, xnd). DT row has day digits; propagate forward.
    coldate=[]; cur=None
    for c in cols:
        seg=(dt[c:c+3].strip() if c<len(dt) else '')
        if seg.isdigit(): cur=int(seg)
        coldate.append(cur)
    # Daytime MAX appears at UTC hour '00' (evening of the local day). The NBS DT day-label at
    # that 00Z column equals the local calendar day of the max. Match hour=='00' & day==target.
    for idx,c in enumerate(cols):
        h=utc[c:c+3].strip()
        tv=txn[c:c+3].strip() if c<len(txn) else ''
        xv=xnd[c:c+3].strip() if c<len(xnd) else ''
        if h=='00' and tv and coldate[idx]==target_date.day:
            return int(tv),(max(int(xv),1) if xv else None)
    return None,None

def kalshi_brackets(event):
    ms=sorted(requests.get(KBASE+'/markets',params={'event_ticker':event,'limit':100},timeout=30).json().get('markets',[]),key=lambda m:m.get('floor_strike') or -999)
    out=[]
    for m in ms:
        ob=requests.get(KBASE+f"/markets/{m['ticker']}/orderbook",timeout=30).json().get('orderbook_fp') or {}
        yes=ob.get('yes_dollars') or []; no=ob.get('no_dollars') or []
        yb=round(max([float(p) for p,_ in yes])*100) if yes else None
        nb=max([float(p) for p,_ in no]) if no else None
        ya=round(100-nb*100) if nb is not None else None
        sub=m.get('subtitle') or m.get('yes_sub_title') or ''
        out.append(dict(t=m['ticker'],sub=sub,floor=m.get('floor_strike'),cap=m.get('cap_strike'),yb=yb,ya=ya))
        time.sleep(0.04)
    return out

def bracket_bounds(m):
    """Map floor/cap strikes to integer high range [lo,hi]. Kalshi 'B85.5' bracket = 85-86 with floor 84.5? 
    Use subtitle text which is authoritative."""
    s=m['sub']
    mm=re.match(r'(\d+).*?(?:to|-).*?(\d+)',s)
    if 'below' in s.lower():
        n=int(re.search(r'(\d+)',s).group(1)); return (None,n)
    if 'above' in s.lower():
        n=int(re.search(r'(\d+)',s).group(1)); return (n,None)
    if mm: return (int(mm.group(1)),int(mm.group(2)))
    return (None,None)

if __name__=='__main__':
    today=datetime.utcnow().date()
    tgt=today+timedelta(days=1)  # tomorrow's market = cleanest (full day ahead)
    datestr=today.strftime('%Y%m%d')
    cycs=latest_cyc(datestr); cyc=cycs[-1]
    txt=get_nbs(datestr,cyc)
    print(f'NBM cycle {cyc}Z {datestr} | target local day {tgt} | FEE model: round-trip ~ Kalshi quadratic\n')
    evdate=tgt.strftime('%y%b%d').upper()
    grand=[]
    for city,(stn,series) in CITIES.items():
        high,sig=parse_high(txt,stn,tgt)
        if high is None:
            print(f'{city}: no NBM'); continue
        event=f'{series}-{evdate}'
        try: brs=kalshi_brackets(event)
        except Exception as e: print(city,'kalshi err',e); continue
        if not brs: 
            print(f'{city}: no kalshi event {event}'); continue
        print(f'== {city} ({stn}) NBM high={high}F sigma={sig}F  event={event}')
        print(f'   {"bracket":<14}{"NBM%":>6}{"Kbid":>6}{"Kask":>6}{"Kmid":>6}{"edge(buy)":>10}')
        for m in brs:
            lo,hi=bracket_bounds(m)
            p=bracket_prob(lo,hi,high,sig)*100
            yb,ya=m['yb'],m['ya']
            mid=((yb+ya)/2) if (yb is not None and ya is not None) else None
            # edge buying YES at ask: fair - ask
            edge_buy=(p-ya) if ya is not None else None
            edge_sell=(yb-p) if yb is not None else None
            best_edge=max([e for e in [edge_buy,edge_sell] if e is not None],default=None)
            flag=' <<<' if (best_edge is not None and best_edge>5) else ''
            print(f'   {m["sub"]:<14}{p:>6.1f}{str(yb):>6}{str(ya):>6}{str(mid):>6}{(f"{edge_buy:+.1f}" if edge_buy is not None else "  -"):>10}{flag}')
            grand.append((city,m['sub'],p,yb,ya,edge_buy,edge_sell))
        print()
