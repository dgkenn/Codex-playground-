"""Find genuinely two-sided ATM strikes in hourly BTC books + measure box economics
and trade cadence/volume. Public API, no auth."""
import requests, datetime, json
BASE = 'https://api.elections.kalshi.com/trade-api/v2'
S = requests.Session()


def get_open(series):
    out, cursor = [], None
    for _ in range(15):
        p = {'series_ticker': series, 'status': 'open', 'limit': 1000}
        if cursor: p['cursor'] = cursor
        d = S.get(BASE + '/markets', params=p, timeout=30).json()
        out += d.get('markets', []); cursor = d.get('cursor')
        if not cursor: break
    return out


def book(t):
    ob = S.get(BASE + '/markets/' + t + '/orderbook', timeout=20).json().get('orderbook_fp', {}) or {}
    yes = sorted((float(p), float(s)) for p, s in (ob.get('yes_dollars') or []))
    no = sorted((float(p), float(s)) for p, s in (ob.get('no_dollars') or []))
    return yes, no


def two_sided(t):
    yes, no = book(t)
    if not yes or not no: return None
    byb, ybsz = yes[-1]
    bnb, bnsz = no[-1]
    yask = round(1 - bnb, 4); nask = round(1 - byb, 4)
    return dict(byb=byb, ybsz=ybsz, bnb=bnb, bnsz=bnsz, yask=yask, nask=nask,
                yspr=round(yask - byb, 4), maker_box=round(byb + bnb, 4),
                taker_box=round(yask + nask, 4))


def trades(ticker, max_pages=8):
    out, cursor = [], None
    for _ in range(max_pages):
        p = {'ticker': ticker, 'limit': 1000}
        if cursor: p['cursor'] = cursor
        d = S.get(BASE + '/markets/trades', params=p, timeout=20).json()
        out += d.get('trades', []); cursor = d.get('cursor')
        if not cursor: break
    return out


def soonest_event(series, now, k=1):
    m = get_open(series); evs = {}
    for x in m:
        ct = x.get('close_time')
        if not ct: continue
        ctd = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00'))
        if ctd > now: evs.setdefault(x.get('event_ticker'), [ctd, []])[1].append(x)
    order = sorted(evs, key=lambda e: evs[e][0])
    return [(e, evs[e][0], evs[e][1]) for e in order[:k]]


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    print('UTC now', now)
    for series in ['KXBTCD', 'KXBTC']:
        for ev, ct, mkts in soonest_event(series, now, k=1):
            mins = round((ct - now).total_seconds() / 60, 1)
            print(f'\n==== {series} {ev} closes_in={mins}min strikes={len(mkts)}')
            ts_rows = []
            for x in mkts:
                ts = two_sided(x['ticker'])
                if ts and 0.05 < ts['byb'] < 0.95:  # genuine two-sided ATM
                    ts['t'] = x['ticker']; ts['fl'] = x.get('floor_strike'); ts['cap'] = x.get('cap_strike')
                    ts_rows.append(ts)
            ts_rows.sort(key=lambda r: abs((r['byb'] + r['yask']) / 2 - 0.5))
            print(f'   genuine two-sided ATM strikes (0.05<bid<0.95): {len(ts_rows)}')
            for r in ts_rows[:12]:
                print(f"   {r['t']:30s} fl={r['fl']} cap={r['cap']} YESbid={r['byb']}(${r['ybsz']:.0f}) "
                      f"NObid={r['bnb']}(${r['bnsz']:.0f}) yspr={r['yspr']} maker_box={r['maker_box']} "
                      f"-> locked={1-r['maker_box']:+.3f} fill$={min(r['ybsz'],r['bnsz']):.0f}")
            # trade volume on the most-ATM strike this event
            if ts_rows:
                tk = ts_rows[0]['t']
                tr = trades(tk)
                vol = sum(float(t.get('count_fp', t.get('count', 0))) for t in tr)
                print(f"   ATM strike {tk} lifetime trades={len(tr)} contracts={vol:.0f}")


if __name__ == '__main__':
    main()
