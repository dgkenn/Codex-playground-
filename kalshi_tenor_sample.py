"""Sample live Kalshi BTC crypto books across tenors to screen maker-box viability.

Public API (https://api.elections.kalshi.com), no auth. Parses orderbook_fp
(price_dollars, size_dollars). Computes the maker-box economics for the single-strike
15M binary and the hourly bracket (KXBTC 'between') / ladder (KXBTCD 'greater') structures.

Box on a single binary = buy YES + buy NO. Cost = ask_yes + ask_no. Margin = 1 - cost.
As a MAKER you post bid_yes and bid_no; if both fill, locked = 1 - bid_yes - bid_no.
We report both the taker-cross box cost (immediate) and the maker mid/touch picture.
"""
import requests, datetime, json, sys, time
BASE = 'https://api.elections.kalshi.com/trade-api/v2'
S = requests.Session()


def get_open(series):
    out, cursor = [], None
    for _ in range(15):
        p = {'series_ticker': series, 'status': 'open', 'limit': 1000}
        if cursor:
            p['cursor'] = cursor
        d = S.get(BASE + '/markets', params=p, timeout=30).json()
        out += d.get('markets', [])
        cursor = d.get('cursor')
        if not cursor:
            break
    return out


def book(t):
    """Return (yes_levels, no_levels) as sorted lists of (price, size_dollars).

    orderbook_fp gives 'yes_dollars' and 'no_dollars': resting BIDs for each outcome.
    A YES bid at p and a NO bid at q are the two sides. Best YES bid = max yes price.
    YES ask = 1 - best NO bid. Best NO bid = max no price.
    """
    ob = S.get(BASE + '/markets/' + t + '/orderbook', timeout=20).json().get('orderbook_fp', {}) or {}
    yes = [(float(p), float(s)) for p, s in (ob.get('yes_dollars') or [])]
    no = [(float(p), float(s)) for p, s in (ob.get('no_dollars') or [])]
    yes.sort(); no.sort()
    return yes, no


def touch(yes, no):
    """best_yes_bid, best_no_bid, yes_ask(=1-best_no_bid), no_ask(=1-best_yes_bid)."""
    byb = yes[-1][0] if yes else None
    bnb = no[-1][0] if no else None
    byb_sz = yes[-1][1] if yes else 0.0
    bnb_sz = no[-1][1] if no else 0.0
    yes_ask = round(1 - bnb, 4) if bnb is not None else None
    no_ask = round(1 - byb, 4) if byb is not None else None
    return byb, bnb, byb_sz, bnb_sz, yes_ask, no_ask


def trades(ticker, limit=1000, max_pages=5):
    out, cursor = [], None
    for _ in range(max_pages):
        p = {'ticker': ticker, 'limit': limit}
        if cursor:
            p['cursor'] = cursor
        d = S.get(BASE + '/markets/trades', params=p, timeout=20).json()
        out += d.get('trades', [])
        cursor = d.get('cursor')
        if not cursor:
            break
    return out


def soonest_event(series, now):
    m = get_open(series)
    evs = {}
    for x in m:
        ct = x.get('close_time')
        if not ct:
            continue
        ctd = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00'))
        if ctd > now:
            evs.setdefault(x.get('event_ticker'), [ctd, []])[1].append(x)
    if not evs:
        return None, None, []
    ev = sorted(evs, key=lambda e: evs[e][0])[0]
    return ev, evs[ev][0], evs[ev][1]


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    print('UTC now', now)
    for series in ['KXBTC15M', 'KXBTCD', 'KXBTC']:
        ev, ct, mkts = soonest_event(series, now)
        mins = round((ct - now).total_seconds() / 60, 1) if ct else None
        print(f'\n==== {series}  event={ev}  closes_in={mins}min  strikes={len(mkts)}')
        rows = []
        for x in mkts:
            yes, no = book(x['ticker'])
            byb, bnb, ybsz, bnsz, yask, nask = touch(yes, no)
            if byb is None and bnb is None:
                continue
            mid = (byb + (yask if yask is not None else byb)) / 2 if byb is not None and yask is not None else None
            box_taker = (yask + nask) if (yask is not None and nask is not None) else None  # buy both at ask
            box_maker = (byb + bnb) if (byb is not None and bnb is not None) else None      # post both bids
            rows.append((x, byb, bnb, ybsz, bnsz, yask, nask, mid, box_taker, box_maker))
        # near-50c first
        rows.sort(key=lambda r: abs((r[7] or 0.5) - 0.5))
        print(f'   strikes with a resting book: {len(rows)}')
        for r in rows[:10]:
            x, byb, bnb, ybsz, bnsz, yask, nask, mid, bt, bm = r
            spr = round((yask - byb), 4) if (yask is not None and byb is not None) else None
            print(f"   {x['ticker']:34s} fl={x.get('floor_strike')} cap={x.get('cap_strike')} "
                  f"YESbid={byb}({ybsz:.0f}$) NObid={bnb}({bnsz:.0f}$) spr={spr} "
                  f"box_taker_cost={bt} box_maker_cost={bm}")
        # box margin if maker fills both at bid:
        for r in rows[:5]:
            x, byb, bnb, ybsz, bnsz, yask, nask, mid, bt, bm = r
            if bm is not None:
                print(f"      MAKER box {x['ticker'][-12:]}: post YES@{byb}+NO@{bnb} cost={bm:.4f} -> locked margin={1-bm:+.4f}  (min fillable=${min(ybsz,bnsz):.0f})")


if __name__ == '__main__':
    main()
