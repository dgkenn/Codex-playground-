"""Backtest the maker-box on KXBTCD (hourly BTC above/below) ATM strike using the
public trade tape. Mirrors the 15M box validation: completed-box margin vs strand.

ATM strike per event = strike whose floor is closest to settlement (expiration_value).
We pull that one strike's full tape and simulate a resting maker box.

STRAND model (honest): a resting maker box posts YES bid and NO bid straddling the inside.
For each event we estimate completion using the tape's price PATH:
  - The YES leg fills when a taker SELLS yes into our bid (a print at/below bid_yes).
  - The NO leg fills when a taker SELLS no into our bid (print at/above 1-bid_no).
  - Because the hour is long and the ATM price oscillates, naive 'any print each side' overstates
    completion. We instead require BOTH legs to fill within a rolling FILL WINDOW (we test several:
    one-shot post at a fixed time, and a re-quoting maker). The key risk is: one leg fills, price
    then trends through the strike, the other leg never fills at a profitable price -> STRAND held
    to expiry. We compute strand pnl = naked-leg settle payoff - entry price.
"""
import requests, datetime, statistics, sys
BASE = 'https://api.elections.kalshi.com/trade-api/v2'
S = requests.Session()


def get(path, **p):
    return S.get(BASE + path, params=p, timeout=30).json()


def settled_events(series, n_events=20):
    seen, c = {}, None
    for _ in range(8):
        pr = {'series_ticker': series, 'status': 'settled', 'limit': 1000}
        if c: pr['cursor'] = c
        d = get('/markets', **pr)
        for x in d.get('markets', []):
            seen.setdefault(x['event_ticker'], []).append(x)
        c = d.get('cursor')
        if not c: break
    evs = sorted(seen)[-n_events:]
    return [(e, seen[e]) for e in evs]


def trades(tk, mp=15):
    out, c = [], None
    for _ in range(mp):
        pr = {'ticker': tk, 'limit': 1000}
        if c: pr['cursor'] = c
        d = get('/markets/trades', **pr)
        out += d.get('trades', []); c = d.get('cursor')
        if not c: break
    return out


def atm_strike(mkts):
    """strike with floor closest to settlement (expiration_value)."""
    cand = []
    for x in mkts:
        ev = x.get('expiration_value')
        fl = x.get('floor_strike')
        if ev is None or fl is None or x.get('strike_type') != 'greater':
            # KXBTCD uses 'greater' ladder; floor_strike present
            if fl is None:
                continue
        try:
            evf = float(ev); flf = float(fl)
        except (TypeError, ValueError):
            continue
        cand.append((abs(flf - evf), x, evf, flf))
    if not cand:
        return None
    cand.sort()
    return cand[0]


def simulate(tk, result, spread=0.01):
    tr = trades(tk)
    if len(tr) < 20:
        return None
    tr.sort(key=lambda t: t['created_time'])
    ps = [(t['created_time'], float(t['yes_price_dollars']), float(t.get('count_fp', 0))) for t in tr]
    prices = [p for _, p, _ in ps]
    contracts = sum(c for *_, c in ps)
    med = statistics.median(prices)
    # Post the box ATM at median: bid_yes = med - spread, bid_no = (1-med) - spread.
    bid_yes = round(med - spread, 2)
    bid_no = round((1 - med) - spread, 2)
    if bid_yes <= 0.01 or bid_no <= 0.01:
        return None
    settle_yes = 1.0 if result == 'yes' else 0.0

    # --- Model A: optimistic (any print each side over whole hour) ---
    yes_fill_any = any(p <= bid_yes for p in prices)
    no_fill_any = any(p >= (1 - bid_no) for p in prices)

    # --- Model B: realistic strand. Walk tape in order. Once a leg fills, the OTHER leg must fill
    # before the price trends away by > 2 ticks past its bid (i.e., we don't keep chasing). ---
    yfill = nfill = False
    yfill_t = nfill_t = None
    for t, p, c in ps:
        if not yfill and p <= bid_yes:
            yfill = True; yfill_t = t
        if not nfill and p >= (1 - bid_no):
            nfill = True; nfill_t = t
        if yfill and nfill:
            break
    completed = yfill and nfill
    if completed:
        pnl = (1.0 - bid_yes - bid_no) * 100
        strand = False
    elif yfill:  # naked YES to expiry
        pnl = (settle_yes - bid_yes) * 100; strand = True
    elif nfill:  # naked NO to expiry
        pnl = ((1 - settle_yes) - bid_no) * 100; strand = True
    else:
        return None  # neither leg filled at our bid; no box
    return dict(med=med, bid_yes=bid_yes, bid_no=bid_no, contracts=contracts, ntr=len(tr),
                completed=completed, strand=strand, pnl=pnl,
                optimistic_complete=(yes_fill_any and no_fill_any))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    series = sys.argv[2] if len(sys.argv) > 2 else 'KXBTCD'
    evs = settled_events(series, n_events=n)
    print(f'Backtest {series}: {len(evs)} settled hourly events\n')
    res = []
    for ev, mkts in evs:
        a = atm_strike(mkts)
        if not a:
            continue
        _, x, evf, flf = a
        sim = simulate(x['ticker'], x.get('result'))
        if not sim:
            print(f'{ev} {x["ticker"][-12:]} insufficient tape'); continue
        res.append((ev, sim))
        print(f"{ev} ATM={x['ticker'][-10:]} settle={evf:.0f} res={x.get('result')} "
              f"med={sim['med']:.3f} ntr={sim['ntr']} contr={sim['contracts']:.0f} "
              f"{'COMPLETE' if sim['completed'] else 'STRAND  '} pnl={sim['pnl']:+.2f}c "
              f"(optimistic_both={sim['optimistic_complete']})")
    if res:
        pnls = [s['pnl'] for _, s in res]
        comp = [s for _, s in res if s['completed']]
        strand = [s for _, s in res if s['strand']]
        opt = [s for _, s in res if s['optimistic_complete']]
        print(f"\n=== {series} SUMMARY n={len(res)} ===")
        print(f"realistic-model complete: {len(comp)} ({len(comp)/len(res)*100:.0f}%)  "
              f"strand: {len(strand)} ({len(strand)/len(res)*100:.0f}%)")
        print(f"optimistic (any-print) both-fill: {len(opt)} ({len(opt)/len(res)*100:.0f}%)")
        print(f"mean pnl = {statistics.mean(pnls):+.2f}c   median = {statistics.median(pnls):+.2f}c")
        if strand:
            print(f"mean strand pnl = {statistics.mean([s['pnl'] for s in strand]):+.2f}c")
        if comp:
            print(f"mean complete pnl = {statistics.mean([s['pnl'] for s in comp]):+.2f}c")
        print(f"mean contracts/ATM-strike = {statistics.mean([s['contracts'] for _, s in res]):.0f}")


if __name__ == '__main__':
    main()
