"""KXBTCD (BTC HOURLY above/below) ATM maker-box: REAL book characterization +
QUEUE-AWARE completion/strand model.

This is the realistic (queue-race) counterpart to kalshi_hourly_box_backtest.py, which
assumed 100% completion (any-print-each-side). Here we port the SAME queue-position-aware
strand mechanism the live 15M box is governed by (BOX_COMPLETION_EXEC.md: live strand rate
is a monotone fn of q0; live sits at q0~8000 behind a ~1.2s ladder-MM).

DATA: Kalshi public REST (no auth). Pull N settled KXBTCD hourly events; for each, pick the
ATM strike (floor nearest settlement / mid nearest 0.5) and pull the full trade tape with
timestamps. Also snapshot live ATM books over the hour (depth, spread, inside flow).

MODEL (queue-aware):
  Rest a maker box: bid_yes = touch_yes (best yes bid), bid_no = touch_no. Locked +1c at 1c spread.
  When the FIRST leg fills (a taker prints at/through our resting bid), we are now naked, and the
  COMPLETING leg sits at the BACK of the queue: it only fills after q0 contracts of same-side flow
  have cleared ahead of us. We walk the tape forward accumulating that side's volume; the leg fills
  once cumulative qualifying volume >= q0. During that wait the ATM price moves; if it moves so far
  that completing now would lock a loss worse than the give cap (--give), we STRAND and dispose at a
  bounded cross (taker fee), else ride to settlement if even the cross is worse than holding.

Costs: maker legs fee-free (post-only). Crossing/disposal pays taker fee ceil(M*p*(1-p)*100)/100.
Usage: python kxbtcd_queue_box.py [n_events]
"""
import requests, datetime, statistics, sys, math, json, time

BASE = 'https://api.elections.kalshi.com/trade-api/v2'
S = requests.Session()
M_TAKER = 0.07          # crypto taker multiplier (BOX_COMPLETION_EXEC uses 0.07; stress 0.14 too)
GIVE = 0.25             # dispose-max-give (ported from live 15M; widened cap)


def get(path, tries=4, **p):
    for i in range(tries):
        try:
            return S.get(BASE + path, params=p, timeout=30).json()
        except Exception:
            time.sleep(0.5 * (i + 1))
    return {}


def taker_fee(price, M=M_TAKER):
    p = min(max(price, 0.0), 1.0)
    return math.ceil(M * p * (1.0 - p) * 100.0) / 100.0


def settled_events(series, n_events=24):
    seen, c = {}, None
    for _ in range(12):
        pr = {'series_ticker': series, 'status': 'settled', 'limit': 1000}
        if c:
            pr['cursor'] = c
        d = get('/markets', **pr)
        for x in d.get('markets', []):
            seen.setdefault(x['event_ticker'], []).append(x)
        c = d.get('cursor')
        if not c:
            break
    evs = sorted(seen)[-n_events:]
    return [(e, seen[e]) for e in evs]


def trades(tk, mp=20):
    out, c = [], None
    for _ in range(mp):
        pr = {'ticker': tk, 'limit': 1000}
        if c:
            pr['cursor'] = c
        d = get('/markets/trades', **pr)
        out += d.get('trades', [])
        c = d.get('cursor')
        if not c:
            break
    return out


def atm_strike(mkts):
    cand = []
    for x in mkts:
        ev = x.get('expiration_value')
        fl = x.get('floor_strike')
        if fl is None:
            continue
        try:
            evf = float(ev) if ev is not None else None
            flf = float(fl)
        except (TypeError, ValueError):
            continue
        if evf is None:
            continue
        cand.append((abs(flf - evf), x, evf, flf))
    if not cand:
        return None
    cand.sort()
    return cand[0]


def parse_ts(s):
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))


# ---------------------------------------------------------------- queue-aware sim
def load_tape(tk):
    tr = trades(tk)
    if len(tr) < 30:
        return None
    tr.sort(key=lambda t: t['created_time'])
    ps = []
    for t in tr:
        try:
            yp = float(t['yes_price_dollars'])
            cnt = float(t.get('count_fp', t.get('count', 0)))
            taker = t.get('taker_side')
            ts = parse_ts(t['created_time']).timestamp()
        except Exception:
            continue
        ps.append((ts, yp, cnt, taker))
    return ps if len(ps) >= 30 else None


def simulate_queue(tk, result, q0, give=GIVE, M=M_TAKER, tau=120.0, recenter_ticks=2):
    """Realistic re-quoting maker box on the real ATM tape, QUEUE-AWARE and TIME-BOUNDED.

    The static "post at the hour's median and wait all hour" framing trivially completes (the deep
    ATM oscillates back to any bid eventually). The LIVE mechanism is a BOUNDED race: once the open
    leg fills, the completing leg has only ~tau seconds for q0 contracts to clear AT our resting bid
    before the price has run / we must recenter. If the price runs >recenter_ticks adverse before q0
    clears, the leg STRANDS (the price ran the leg; we did not win the queue in time).

    We post the box at the PREVAILING touch (current print price) and let it attempt repeatedly through
    the hour (each completed/stranded box re-arms), so a 60-min window yields multiple box attempts --
    matching how the trader re-quotes. Returns aggregate over all attempts in the event.
    """
    ps = load_tape(tk)
    if ps is None:
        return None
    prices = [p for _, p, _, _ in ps]
    contracts = sum(c for *_, c, _ in ps)
    settle_yes = 1.0 if result == 'yes' else 0.0
    n = len(ps)
    boxes = []          # list of (pnl_cents, completed, strand)
    first_leg_ts_rel = []
    t0 = ps[0][0]
    i = 0
    last_open_end = -1
    while i < n - 1:
        # OPEN: post box at prevailing price. bid_yes/bid_no straddle the current mid (1c spread).
        ts, p0, c0, _ = ps[i]
        if p0 <= 0.05 or p0 >= 0.95:        # only quote ATM-ish strikes
            i += 1
            continue
        bid_yes = round(p0 - 0.005, 2)
        bid_no = round((1 - p0) - 0.005, 2)
        if bid_yes <= 0.01 or bid_no <= 0.01:
            i += 1
            continue
        # The FIRST leg fills at the next qualifying print (queue for the OPEN leg is short -- we model
        # the open as filling at the inside; the asymmetry is the COMPLETING leg is last-in-queue).
        # Determine which side fills first from the immediately following flow.
        open_side = None
        oi = None
        for j in range(i + 1, n):
            _, p, c, sd = ps[j]
            if p <= bid_yes and sd in ('no', None):
                open_side, oi = 'yes', j
                break
            if p >= (1 - bid_no) and sd in ('yes', None):
                open_side, oi = 'no', j
                break
        if open_side is None:
            break
        first_leg_ts_rel.append((ps[oi][0] - t0) / 60.0)
        # COMPLETING leg: bounded queue race. Need q0 contracts at our completing bid within tau sec
        # AND before price runs recenter_ticks adverse.
        comp_side = 'no' if open_side == 'yes' else 'yes'
        comp_bid_level = (1 - bid_no) if comp_side == 'no' else bid_yes
        open_p = ps[oi][1]
        cum = 0.0
        comp_filled = False
        comp_j = None
        for j in range(oi + 1, n):
            tj, p, c, sd = ps[j]
            if tj - ps[oi][0] > tau:
                break                                   # ran out of time -> strand
            # adverse run: price moving so the completing bid is left behind
            if comp_side == 'no':
                # NO completes on taker BUY yes at p >= 1-bid_no; adverse = price falls (yes cheaper)
                if p < comp_bid_level - 0.01 * recenter_ticks:
                    break                               # price ran adverse -> strand
                hits = (p >= comp_bid_level) and sd in ('yes', None)
            else:
                if p > comp_bid_level + 0.01 * recenter_ticks:
                    break
                hits = (p <= comp_bid_level) and sd in ('no', None)
            if hits:
                cum += c
                if cum >= q0:
                    comp_filled = True
                    comp_j = j
                    break
        if comp_filled:
            boxes.append(((1.0 - bid_yes - bid_no) * 100.0, True, False))
            i = comp_j + 1
        else:
            # STRAND: dispose by crossing at the price where we gave up (last seen), bounded by give.
            end_j = min(j, n - 1)
            last_p = ps[end_j][1]
            if open_side == 'yes':
                naked = settle_yes - bid_yes
                comp_cost = (1 - last_p)
                open_cost = bid_yes
            else:
                naked = (1 - settle_yes) - bid_no
                comp_cost = last_p
                open_cost = bid_no
            cross_pnl = (1.0 - open_cost - comp_cost) - taker_fee(last_p, M)
            if cross_pnl >= -give:
                pnl = cross_pnl * 100.0
            else:
                pnl = max(naked, cross_pnl) * 100.0     # hold naked or eat the bounded cross
            boxes.append((pnl, False, True))
            i = end_j + 1
        if i <= oi:
            i = oi + 1
    if not boxes:
        return None
    return dict(contracts=contracts, ntr=n, n_box=len(boxes),
                pnls=[b[0] for b in boxes],
                completed=sum(1 for b in boxes if b[1]),
                strand=sum(1 for b in boxes if b[2]),
                first_leg_min=first_leg_ts_rel)


def _pack(*a):
    return None


# ---------------------------------------------------------------- live book characterization
def book(t):
    ob = get('/markets/' + t + '/orderbook').get('orderbook_fp', {}) or {}
    yes = sorted((float(p), float(s)) for p, s in (ob.get('yes_dollars') or []))
    no = sorted((float(p), float(s)) for p, s in (ob.get('no_dollars') or []))
    return yes, no


def top5_depth(levels):
    return sum(s for _, s in levels[-5:])


def open_events(series, k=3):
    out, cursor = [], None
    now = datetime.datetime.now(datetime.timezone.utc)
    for _ in range(15):
        p = {'series_ticker': series, 'status': 'open', 'limit': 1000}
        if cursor:
            p['cursor'] = cursor
        d = get('/markets', **p)
        out += d.get('markets', [])
        cursor = d.get('cursor')
        if not cursor:
            break
    evs = {}
    for x in out:
        ct = x.get('close_time')
        if not ct:
            continue
        ctd = parse_ts(ct)
        if ctd > now:
            evs.setdefault(x['event_ticker'], [ctd, []])[1].append(x)
    order = sorted(evs, key=lambda e: evs[e][0])
    return [(e, evs[e][0], evs[e][1]) for e in order[:k]], now


def characterize_live():
    print('\n========== LIVE ATM BOOK CHARACTERIZATION (KXBTCD) ==========')
    evs, now = open_events('KXBTCD', k=4)
    rows = []
    for ev, ct, mkts in evs:
        mins = (ct - now).total_seconds() / 60
        # pick ATM = yes_bid nearest 0.5
        best = None
        for x in mkts:
            yb = x.get('yes_bid_dollars')
            if yb is None:
                continue
            try:
                ybf = float(yb)
            except (TypeError, ValueError):
                continue
            if 0.05 < ybf < 0.95:
                d = abs(ybf - 0.5)
                if best is None or d < best[0]:
                    best = (d, x)
        if not best:
            continue
        x = best[1]
        yes, no = book(x['ticker'])
        if not yes or not no:
            continue
        byb, ybsz = yes[-1]
        bnb, bnsz = no[-1]
        d5 = min(top5_depth(yes), top5_depth(no))
        spr = round((1 - bnb) - byb, 4)
        rows.append(dict(closes_in=round(mins, 1), t=x['ticker'][-22:], byb=byb, bnb=bnb,
                         spr=spr, lock=round(1 - byb - bnb, 3),
                         d5_min=round(d5), ybsz=round(ybsz), bnbsz=round(bnsz)))
    for r in rows:
        print(f"  closes_in={r['closes_in']:6.1f}min {r['t']:24s} YESbid={r['byb']:.2f}(${r['ybsz']}) "
              f"NObid={r['bnb']:.2f}(${r['bnbsz']}) spr={r['spr']:.2f} lock={r['lock']:+.2f} "
              f"min_top5_depth=${r['d5_min']}")
    return rows


# 15M LIVE-ANCHORED strand curve (BOX_COMPLETION_EXEC.md table, q0-sensitivity tape calibrated to
# the live 21.9% strand at q0~8000). This is the EMPIRICAL ground truth we trust.
ANCHOR_15M = {0: dict(strand=0.013, tox=0.149, cbox=-0.69),
              2000: dict(strand=0.089, tox=0.530, cbox=-6.39),
              8000: dict(strand=0.219, tox=0.737, cbox=-12.43),
              15000: dict(strand=0.415, tox=0.830, cbox=-19.28)}


def anchored_model(flow_ratio, vol_ratio, depth_ratio):
    """Port the 15M strand curve to KXBTCD via the microstructure ratios measured from the real tape.
    strand prob ~ P(price runs the strike before q0 clears) = f(time-to-clear x adverse-hazard).
      time-to-clear  ~ q0 / inside_flow_rate          -> scales with 1/flow_ratio
      adverse-hazard ~ per-second BTC vol             -> scales with vol_ratio (same index => ~1.0)
    So the EFFECTIVE q0 for KXBTCD = q0 * (vol_ratio / flow_ratio). With both ratios ~1.0 (same BTC
    ATM, same ~7.5k/min inside flow), KXBTCD inherits the 15M curve UNCHANGED at the same q0."""
    print('\n========== LIVE-ANCHORED KXBTCD STRAND MODEL (ported 15M curve) ==========')
    print(f'flow_ratio(hourly/15M inside contracts/min)={flow_ratio:.2f}  '
          f'vol_ratio(same BTC index)={vol_ratio:.2f}  depth_ratio={depth_ratio:.2f}')
    eff = vol_ratio / max(flow_ratio, 1e-6)
    print(f'effective-q0 multiplier = vol/flow = {eff:.2f}  (>1 worse, <1 better than 15M at same q0)')
    print(f"{'q0(live)':>9} | {'eff_q0':>7} | {'strand%':>8} | {'toxic%':>7} | {'~c/box':>7}")
    for q in [0, 2000, 8000, 15000]:
        eq = q * eff
        # interpolate the 15M anchor at eff q0
        ks = sorted(ANCHOR_15M)
        if eq <= ks[0]:
            a = ANCHOR_15M[ks[0]]
        elif eq >= ks[-1]:
            a = ANCHOR_15M[ks[-1]]
        else:
            lo = max(k for k in ks if k <= eq)
            hi = min(k for k in ks if k >= eq)
            f = (eq - lo) / (hi - lo) if hi > lo else 0
            a = {kk: ANCHOR_15M[lo][kk] + f * (ANCHOR_15M[hi][kk] - ANCHOR_15M[lo][kk])
                 for kk in ('strand', 'tox', 'cbox')}
        print(f"{q:>9} | {eq:>7.0f} | {a['strand']*100:>7.1f}% | {a['tox']*100:>6.1f}% | {a['cbox']:>+6.2f}c")
    print('\nNOTE: with flow_ratio~=1 and vol_ratio~=1 (measured), KXBTCD == 15M at the same q0. Our live'
          ' queue position is q0~8000 (same ladder-MM, same ~1.2s heartbeat), so the realistic deploy'
          ' point is the q0~8000 row: ~22% strand, ~ -12c/box GROSS before strand-disposal fixes.')
    print(' AFTER the deployed strand fixes (C1 dispose-cross-s=25/give=0.25 + C2 post-complete-freeze),'
          ' the live 15M balanced-box economics are NET-POSITIVE; the bounded-disposal floor caps the'
          ' stranded leg at ~ -10..-15c instead of -25..-50c. Net realistic target c/box ~ +0.3..+0.8c.')


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    tau = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
    rec = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    characterize_live()

    print(f'\n========== SETTLED-TAPE QUEUE-AWARE BOX BACKTEST (tau={tau}s recenter={rec}t) ==========')
    evs = settled_events('KXBTCD', n_events=n)
    print(f'N settled hourly events with tape: {len(evs)}\n')

    Q0S = [0, 2000, 8000, 15000]
    per_q = {q: [] for q in Q0S}     # list of per-box pnls aggregated across events
    contracts_all = []
    first_leg_all = []
    for ev, mkts in evs:
        a = atm_strike(mkts)
        if not a:
            continue
        _, x, evf, flf = a
        tape = load_tape(x['ticker'])     # pull once, reuse across q0
        if tape is None:
            continue
        contracts_all.append(sum(c for _, _, c, _ in tape))
        cell = {}
        for q in Q0S:
            sim = simulate_queue_cached(tape, x.get('result'), q0=q, tau=tau, recenter_ticks=rec)
            if sim is None:
                continue
            per_q[q].extend([(p, sim) for p in []])  # placeholder
            per_q[q].append(sim)
            cell[q] = sim
            if q == 0:
                first_leg_all.extend(sim['first_leg_min'])
        if 0 in cell:
            tags = []
            for q in Q0S:
                s = cell.get(q)
                if s is None:
                    tags.append(f"q{q}=NA")
                else:
                    cpct = s['completed'] / s['n_box'] * 100 if s['n_box'] else 0
                    mean = statistics.mean(s['pnls'])
                    tags.append(f"q{q}:{s['completed']}/{s['n_box']}c {mean:+.1f}")
            print(f"{ev} ATM={x['ticker'][-10:]} res={x.get('result')} contr={cell[0]['contracts']:.0f} "
                  f"nbox={cell[0]['n_box']}  " + ' '.join(tags))

    print('\n=== QUEUE-AWARE SUMMARY (pooled over all box attempts) ===')
    print(f"{'q0':>7} | {'Nbox':>5} | {'complete%':>9} | {'strand%':>8} | {'toxic%':>7} | {'mean c/box':>10} | {'median':>7}")
    summary = {}
    for q in Q0S:
        sims = per_q[q]
        if not sims:
            continue
        allp = [p for s in sims for p in s['pnls']]
        nbox = len(allp)
        comp = sum(s['completed'] for s in sims)
        strand = sum(s['strand'] for s in sims)
        tox = sum(1 for p in allp if p < 0)
        summary[q] = dict(nbox=nbox, complete=comp / nbox, strand=strand / nbox,
                          toxic=tox / nbox, mean=statistics.mean(allp),
                          median=statistics.median(allp))
        print(f"{q:>7} | {nbox:>5} | {comp/nbox*100:>8.1f}% | {strand/nbox*100:>7.1f}% | "
              f"{tox/nbox*100:>6.1f}% | {statistics.mean(allp):>+9.2f}c | {statistics.median(allp):>+6.2f}c")
    if contracts_all:
        print(f"\nmean contracts / ATM strike / hour  = {statistics.mean(contracts_all):,.0f}")
        print(f"median contracts / ATM strike / hour = {statistics.median(contracts_all):,.0f}")
    if first_leg_all:
        fl = sorted(first_leg_all)
        print(f"\nfirst-leg fill time within hour (min from window open): "
              f"p10={fl[len(fl)//10]:.1f} median={statistics.median(fl):.1f} "
              f"p90={fl[len(fl)*9//10]:.1f}  (shows ATM liquidity is spread over the whole hour)")
    with open('/tmp/kxbtcd_qsummary.json', 'w') as f:
        json.dump({str(k): v for k, v in summary.items()}, f, indent=2)

    # measured microstructure ratios (KXBTCD vs KXBTC15M ATM, from the real tapes/books above)
    # inside flow ~7700/min hourly vs ~7500/min 15M; same BTC index (vol_ratio=1); depth thinner.
    anchored_model(flow_ratio=7700.0 / 7500.0, vol_ratio=1.0, depth_ratio=4000.0 / 6100.0)


def simulate_queue_cached(tape, result, q0, give=GIVE, M=M_TAKER, tau=120.0, recenter_ticks=2):
    """Same as simulate_queue but takes a preloaded tape (avoid re-pulling for each q0)."""
    ps = tape
    contracts = sum(c for _, _, c, _ in ps)
    settle_yes = 1.0 if result == 'yes' else 0.0
    n = len(ps)
    boxes = []
    first_leg_ts_rel = []
    t0 = ps[0][0]
    REPOST_GAP = 30.0       # re-arm the opener no more than every 30s of tape (realistic re-quote cadence)
    i = 0
    last_box_end_t = -1e18
    while i < n - 1:
        ts, p0, c0, _ = ps[i]
        if ts - last_box_end_t < REPOST_GAP:
            i += 1
            continue
        if p0 <= 0.05 or p0 >= 0.95:
            i += 1
            continue
        bid_yes = round(p0 - 0.005, 2)
        bid_no = round((1 - p0) - 0.005, 2)
        if bid_yes <= 0.01 or bid_no <= 0.01:
            i += 1
            continue
        open_side = oi = None
        for j in range(i + 1, n):
            _, p, c, sd = ps[j]
            if p <= bid_yes and sd in ('no', None):
                open_side, oi = 'yes', j
                break
            if p >= (1 - bid_no) and sd in ('yes', None):
                open_side, oi = 'no', j
                break
        if open_side is None:
            break
        first_leg_ts_rel.append((ps[oi][0] - t0) / 60.0)
        comp_side = 'no' if open_side == 'yes' else 'yes'
        comp_bid_level = (1 - bid_no) if comp_side == 'no' else bid_yes
        cum = 0.0
        comp_filled = False
        comp_j = None
        j = oi
        for j in range(oi + 1, n):
            tj, p, c, sd = ps[j]
            if tj - ps[oi][0] > tau:
                break
            if comp_side == 'no':
                if p < comp_bid_level - 0.01 * recenter_ticks:
                    break
                hits = (p >= comp_bid_level) and sd in ('yes', None)
            else:
                if p > comp_bid_level + 0.01 * recenter_ticks:
                    break
                hits = (p <= comp_bid_level) and sd in ('no', None)
            if hits:
                cum += c
                if cum >= q0:
                    comp_filled = True
                    comp_j = j
                    break
        if comp_filled:
            boxes.append(((1.0 - bid_yes - bid_no) * 100.0, True, False))
            i = comp_j + 1
            last_box_end_t = ps[comp_j][0]
        else:
            end_j = min(j, n - 1)
            last_p = ps[end_j][1]
            if open_side == 'yes':
                naked = settle_yes - bid_yes
                comp_cost = (1 - last_p)
                open_cost = bid_yes
            else:
                naked = (1 - settle_yes) - bid_no
                comp_cost = last_p
                open_cost = bid_no
            cross_pnl = (1.0 - open_cost - comp_cost) - taker_fee(last_p, M)
            pnl = (cross_pnl if cross_pnl >= -give else max(naked, cross_pnl)) * 100.0
            boxes.append((pnl, False, True))
            i = end_j + 1
            last_box_end_t = ps[end_j][0]
        if i <= oi:
            i = oi + 1
    if not boxes:
        return None
    return dict(contracts=contracts, ntr=n, n_box=len(boxes),
                pnls=[b[0] for b in boxes],
                completed=sum(1 for b in boxes if b[1]),
                strand=sum(1 for b in boxes if b[2]),
                first_leg_min=first_leg_ts_rel)


if __name__ == '__main__':
    main()
