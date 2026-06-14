#!/usr/bin/env python3
"""Snapshot Kalshi daily-high-temp markets: bracket structure, book-implied prob, spread, depth."""
import requests, json, time, sys

BASE = 'https://api.elections.kalshi.com/trade-api/v2'

def get(path, **params):
    r = requests.get(BASE + path, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def parse_book(t):
    """Return (yes_bid, yes_bid_sz, yes_ask, yes_ask_sz) in cents."""
    ob = get(f'/markets/{t}/orderbook').get('orderbook_fp') or {}
    yes = ob.get('yes_dollars') or []
    no  = ob.get('no_dollars') or []
    def best(side):
        if not side: return None, None
        p, s = max(side, key=lambda x: float(x[0]))
        return round(float(p)*100), float(s)
    yb, ybs = best(yes)                 # best yes bid
    nb, nbs = best(no)                  # best no bid
    ya = (100 - nb) if nb is not None else None  # yes ask = 100 - best no bid
    return yb, ybs, ya, nbs

def snapshot(event):
    ms = sorted(get('/markets', event_ticker=event, limit=100).get('markets', []),
                key=lambda m: m['ticker'])
    rows = []
    for m in ms:
        yb, ybs, ya, yas = parse_book(m['ticker'])
        mid = ((yb+ya)/2) if (yb is not None and ya is not None) else None
        spread = (ya-yb) if (yb is not None and ya is not None) else None
        rows.append(dict(ticker=m['ticker'], sub=m.get('subtitle',''),
                         yb=yb, ya=ya, mid=mid, spread=spread,
                         depth_bid=ybs, depth_ask=yas,
                         floor=m.get('floor_strike'), cap=m.get('cap_strike')))
        time.sleep(0.05)
    return rows

if __name__ == '__main__':
    events = sys.argv[1:] or ['KXHIGHNY-26JUN15']
    for ev in events:
        print(f'\n==== {ev} ====')
        rows = snapshot(ev)
        tot_prob = 0
        for r in rows:
            if r['mid'] is not None: tot_prob += r['mid']
            print(f"{r['sub']:<16} bid={str(r['yb']):>4} ask={str(r['ya']):>4} "
                  f"mid={str(r['mid']):>5} spr={str(r['spread']):>4} "
                  f"depthB={str(r['depth_bid']):>6} depthA={str(r['depth_ask']):>6}")
        print(f"  sum(mid)={tot_prob:.0f}c (overround if >100)")
