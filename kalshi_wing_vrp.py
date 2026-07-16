#!/usr/bin/env python3
"""
Kalshi hourly BTC ladder (KXBTCD) — WING variance-risk-premium / favorite-longshot test.

ONE hypothesis: deep OTM "wing" strikes (entry YES-price in (0, 0.15]) are systematically
OVERPRICED, so SELLING them (buying NO) is profitable net of the rounded Kalshi fee.

Anti-look-ahead core:
  Entry YES-probability = count-weighted VWAP of yes_price over trades in the FIRST HALF of
  [open_time, close_time] (life fraction <= 0.5). Require >= 2 early trades or SKIP.
  Result is taken only from market settlement (cleanly separate from the entry window).

Outputs a calibration table + an OOS (train/test split by close_time) tradeable test,
net of the cent-rounded fee, day-clustered by event close-DATE. Writes a markdown report.

No auth needed. Kalshi public API.
"""
import urllib.request, urllib.error, json, os, sys, math, time, statistics
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = 'https://api.elections.kalshi.com/trade-api/v2'
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.kalshi_cache')
os.makedirs(CACHE, exist_ok=True)
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kalshi_wing_vrp_report.md')

# ---- crawl sizing ----
TARGET_DATES = 55          # distinct event close-dates to sample
EVENTS_PER_DATE = 6        # evenly spaced across the 24 hours of each date (reduces hour-of-day bias)
WING_HI = 0.15             # OTM wing: entry yes-price in (0, WING_HI]
ITM_LO = 0.85              # deep-ITM cross-check: entry yes-price >= ITM_LO
MIN_EARLY_TRADES = 2
HALF_SPREAD = 0.01         # conservative 1c to sell/buy against the book
WORKERS = 20

def http_get(url, tries=5):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'wing-vrp/1.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if k == tries - 1:
                raise
            time.sleep(0.5 * (2 ** k))
    return None

def dt(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))

# ---------------------------------------------------------------- event listing
def list_events():
    """Newest-first settled events, grouped by strike-date; pick EVENTS_PER_DATE per date."""
    cache = os.path.join(CACHE, 'event_list.json')
    if os.path.exists(cache):
        return json.load(open(cache))
    by_date = {}
    cur = None
    pages = 0
    # newest date is likely a partial/in-progress day; skip the single newest date.
    while len(by_date) < TARGET_DATES + 3 and pages < 120:
        u = BASE + '/events?series_ticker=KXBTCD&status=settled&limit=200'
        if cur:
            u += '&cursor=' + cur
        d = http_get(u)
        for e in d.get('events', []):
            sd = e.get('strike_date')
            if not sd:
                continue
            by_date.setdefault(sd[:10], []).append((sd, e['event_ticker']))
        cur = d.get('cursor')
        pages += 1
        if not cur:
            break
    dates = sorted(by_date.keys(), reverse=True)
    dates = dates[1:1 + TARGET_DATES]  # drop newest (possibly partial), take next TARGET_DATES
    selected = []
    for dstr in dates:
        evs = sorted(by_date[dstr])  # by strike time
        n = len(evs)
        if n <= EVENTS_PER_DATE:
            pick = evs
        else:
            idx = [round(i * (n - 1) / (EVENTS_PER_DATE - 1)) for i in range(EVENTS_PER_DATE)]
            pick = [evs[i] for i in sorted(set(idx))]
        for sd, et in pick:
            selected.append(et)
    json.dump(selected, open(cache, 'w'))
    return selected

# ---------------------------------------------------------------- per-market data
def get_markets(et):
    cache = os.path.join(CACHE, f'mkts_{et}.json')
    if os.path.exists(cache):
        return json.load(open(cache))
    d = http_get(BASE + f'/markets?event_ticker={et}&limit=400')
    ms = d.get('markets', [])
    json.dump(ms, open(cache, 'w'))
    return ms

def get_trades(ticker):
    cache = os.path.join(CACHE, f'tr_{ticker}.json')
    if os.path.exists(cache):
        return json.load(open(cache))
    out = []
    cur = None
    for _ in range(30):
        u = BASE + f'/markets/trades?ticker={ticker}&limit=1000'
        if cur:
            u += '&cursor=' + cur
        d = http_get(u)
        out.extend(d.get('trades', []))
        cur = d.get('cursor')
        if not cur:
            break
    json.dump(out, open(cache, 'w'))
    return out

def entry_from_trades(trades, open_t, close_t):
    """Count-weighted VWAP of yes-price over trades in first half of life. None if <2 early."""
    ot, ct = dt(open_t).timestamp(), dt(close_t).timestamp()
    life = ct - ot
    if life <= 0:
        return None, 0
    cutoff = ot + 0.5 * life
    wsum = 0.0
    psum = 0.0
    n = 0
    for t in trades:
        ts = dt(t['created_time']).timestamp()
        if ts < ot or ts > cutoff:
            continue
        y = t.get('yes_price_dollars')
        if y is None:
            no = t.get('no_price_dollars')
            if no is None:
                continue
            y = 1.0 - float(no)
        else:
            y = float(y)
        c = float(t.get('count_fp') or 0)
        if c <= 0:
            continue
        wsum += c
        psum += y * c
        n += 1
    if n < MIN_EARLY_TRADES or wsum <= 0:
        return None, n
    return psum / wsum, n

def process_event(et):
    """Return list of observations for one event."""
    obs = []
    try:
        ms = get_markets(et)
    except Exception as e:
        return obs
    # only markets that actually traded can yield an early VWAP
    volm = [m for m in ms if float(m.get('volume_fp') or 0) > 0]
    for m in volm:
        res = m.get('result')
        if res not in ('yes', 'no'):
            continue
        ot, ct = m.get('open_time'), m.get('close_time')
        if not ot or not ct:
            continue
        try:
            trades = get_trades(m['ticker'])
        except Exception:
            continue
        entry, nearly = entry_from_trades(trades, ot, ct)
        if entry is None:
            continue
        obs.append({
            'event': et,
            'ticker': m['ticker'],
            'close_date': dt(ct).astimezone(timezone.utc).strftime('%Y-%m-%d'),
            'close_ts': dt(ct).timestamp(),
            'strike': float(m.get('floor_strike') or 0),
            'entry': entry,
            'result': 1 if res == 'yes' else 0,
            'n_early': nearly,
        })
    return obs

# ---------------------------------------------------------------- stats helpers
def cluster_stats(values, clusters):
    """Mean of `values` with cluster-robust (by `clusters`) SE and t-stat vs 0.
    Returns (mean, se, t, n, n_clusters)."""
    n = len(values)
    if n == 0:
        return (float('nan'),) * 3 + (0, 0)
    mean = sum(values) / n
    groups = {}
    for v, c in zip(values, clusters):
        groups.setdefault(c, []).append(v)
    G = len(groups)
    # cluster-robust variance of the mean: (1/n^2) * G/(G-1) * sum_g (sum_i (v_i - mean))^2
    ss = 0.0
    for c, vs in groups.items():
        gsum = sum((v - mean) for v in vs)
        ss += gsum * gsum
    if G > 1:
        var = (G / (G - 1.0)) * ss / (n * n)
    else:
        var = float('nan')
    se = math.sqrt(var) if var == var and var >= 0 else float('nan')
    t = mean / se if se and se == se and se > 0 else float('nan')
    return mean, se, t, n, G

def fee(p):
    """Kalshi trading fee per contract at price p, rounded UP to next cent, min 1c."""
    raw = 0.07 * p * (1.0 - p)
    return max(0.01, math.ceil(raw * 100.0) / 100.0)

# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    events = list_events()
    print(f'[crawl] {len(events)} events selected', flush=True)
    all_obs = []
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(process_event, et): et for et in events}
        for f in as_completed(futs):
            all_obs.extend(f.result())
            done += 1
            if done % 25 == 0:
                print(f'[crawl] {done}/{len(events)} events, {len(all_obs)} obs, '
                      f'{time.time()-t0:.0f}s', flush=True)
    print(f'[crawl] done: {len(all_obs)} obs in {time.time()-t0:.0f}s', flush=True)

    # sample summary
    dates = sorted({o['close_date'] for o in all_obs})
    wings = [o for o in all_obs if 0 < o['entry'] <= WING_HI]
    itm = [o for o in all_obs if o['entry'] >= ITM_LO]
    wing_dates = sorted({o['close_date'] for o in wings})

    # ---------------- CALIBRATION (all data) ----------------
    bins = [(0.00, 0.02), (0.02, 0.04), (0.04, 0.06), (0.06, 0.08), (0.08, 0.10),
            (0.10, 0.15), (0.15, 0.25), (0.25, 0.40), (0.40, 0.60), (0.60, 0.75),
            (0.75, 0.85), (0.85, 0.90), (0.90, 0.94), (0.94, 0.96), (0.96, 1.00)]
    calib = []
    for lo, hi in bins:
        grp = [o for o in all_obs if lo < o['entry'] <= hi] if lo > 0 else \
              [o for o in all_obs if lo <= o['entry'] <= hi]
        if not grp:
            calib.append((lo, hi, 0, float('nan'), float('nan'), float('nan'), float('nan'), 0))
            continue
        entry_mean = sum(o['entry'] for o in grp) / len(grp)
        realized = sum(o['result'] for o in grp) / len(grp)
        diff = [o['result'] - o['entry'] for o in grp]  # realized-entry per obs
        m, se, t, n, G = cluster_stats(diff, [o['close_date'] for o in grp])
        calib.append((lo, hi, len(grp), entry_mean, realized, m, t, G))

    # ---------------- TRADEABLE OOS ----------------
    # split events by close_time: earliest 70% -> TRAIN, latest 30% -> TEST
    ev_close = {}
    for o in all_obs:
        ev_close[o['event']] = min(ev_close.get(o['event'], 1e18), o['close_ts'])
    ev_sorted = sorted(ev_close, key=lambda e: ev_close[e])
    n_train = int(round(len(ev_sorted) * 0.70))
    train_ev = set(ev_sorted[:n_train])
    test_ev = set(ev_sorted[n_train:])

    def strat_wings(obs, executed_adj):
        """SELL YES on wings (entry<=WING_HI). executed_adj subtracted from entry (1c to sell)."""
        gross, net, clus = [], [], []
        for o in obs:
            ex_price = o['entry'] - executed_adj
            g = ex_price - o['result']              # sell yes: collect ex_price, pay result
            n_ = g - fee(ex_price)
            gross.append(g); net.append(n_); clus.append(o['close_date'])
        return gross, net, clus

    def strat_itm(obs, executed_adj):
        """BUY YES on deep-ITM (entry>=ITM_LO). executed_adj added to entry (1c to buy)."""
        gross, net, clus = [], [], []
        for o in obs:
            ex_price = o['entry'] + executed_adj
            g = o['result'] - ex_price              # buy yes: pay ex_price, collect result
            n_ = g - fee(ex_price)
            gross.append(g); net.append(n_); clus.append(o['close_date'])
        return gross, net, clus

    def report_leg(name, obs, fn):
        rows = {}
        for adj_name, adj in [('vwap', 0.0), ('vwap-1c', HALF_SPREAD)]:
            g, n_, c = fn(obs, adj)
            rows[('gross', adj_name)] = cluster_stats(g, c)
            rows[('net', adj_name)] = cluster_stats(n_, c)
        return rows

    train_wings = [o for o in wings if o['event'] in train_ev]
    test_wings = [o for o in wings if o['event'] in test_ev]
    train_itm = [o for o in itm if o['event'] in train_ev]
    test_itm = [o for o in itm if o['event'] in test_ev]

    res = {
        'WING SELL - TRAIN': report_leg('wing', train_wings, strat_wings),
        'WING SELL - TEST':  report_leg('wing', test_wings, strat_wings),
        'ITM BUY - TRAIN':   report_leg('itm', train_itm, strat_itm),
        'ITM BUY - TEST':    report_leg('itm', test_itm, strat_itm),
    }

    # ---------------- write report ----------------
    L = []
    def w(s=''):
        L.append(s)
    span = f"{dates[0]} .. {dates[-1]}" if dates else "n/a"
    w("# Kalshi hourly BTC ladder (KXBTCD) — Wing overpricing / VRP test\n")
    w(f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n")
    w("## Hypothesis")
    w("Deep OTM **wing** strikes (entry YES-price in (0, 0.15]) are systematically "
      "OVERPRICED, so SELLING them (buying NO) is profitable net of the cent-rounded Kalshi fee.\n")
    w("## Method (anti-look-ahead)")
    w("- **Entry** = count-weighted VWAP of yes-price over trades in the FIRST HALF of "
      "`[open_time, close_time]` (life fraction <= 0.5); require >= 2 early trades or SKIP.")
    w("- **Result** taken only from settlement (`result` yes/no), cleanly separate from entry window.")
    w("- Only markets with `volume_fp > 0` are queried for trades (others cannot yield an early VWAP).")
    w("- Fee per contract = `max(0.01, ceil(0.07*p*(1-p)*100)/100)` at the executed price.")
    w("- Day-clustered t-stats cluster by event **close-DATE** (cluster-robust SE of the mean).")
    w(f"- OOS split by close_time: earliest 70% events -> TRAIN, latest 30% -> TEST.\n")
    w("## Sample achieved")
    w(f"- Events processed: **{len(events)}**")
    w(f"- Total obs (>=2 early trades, any moneyness): **{len(all_obs)}**")
    w(f"- Distinct close-dates (all obs): **{len(dates)}**  |  span: {span}")
    w(f"- **WING obs (entry in (0,{WING_HI}]): {len(wings)}** across **{len(wing_dates)}** dates")
    w(f"- Deep-ITM obs (entry >= {ITM_LO}): {len(itm)} across "
      f"{len({o['close_date'] for o in itm})} dates")
    w(f"- TRAIN events {len(train_ev)} / TEST events {len(test_ev)}\n")

    w("## Calibration (all obs) — realized YES rate vs entry price")
    w("Longshot overpricing = realized < entry in the low bins (negative realized-entry).\n")
    w("| entry bin | n | dates | mean entry | realized YES | realized-entry | clustered t |")
    w("|---|---|---|---|---|---|---|")
    for lo, hi, n, em, rz, md, t, G in calib:
        if n == 0:
            w(f"| ({lo:.2f},{hi:.2f}] | 0 | - | - | - | - | - |")
        else:
            w(f"| ({lo:.2f},{hi:.2f}] | {n} | {G} | {em:.4f} | {rz:.4f} | {md:+.4f} | {t:+.2f} |")
    w("")

    w("## Tradeable OOS — PnL per contract (dollars), day-clustered by close-date")
    w("SELL YES on wings (profit if it stays OTM). BUY YES on deep-ITM. "
      "`vwap` executes at the entry VWAP; `vwap-1c` pays a conservative 1c half-spread.\n")
    for leg in ['WING SELL - TRAIN', 'WING SELL - TEST', 'ITM BUY - TRAIN', 'ITM BUY - TEST']:
        rows = res[leg]
        w(f"### {leg}")
        w("| variant | mean PnL/contract | clustered t | n obs | n dates |")
        w("|---|---|---|---|---|")
        for kind in ['gross', 'net']:
            for adj in ['vwap', 'vwap-1c']:
                m, se, t, n, G = rows[(kind, adj)]
                if n == 0:
                    w(f"| {kind} ({adj}) | - | - | 0 | 0 |")
                else:
                    w(f"| {kind} ({adj}) | {m:+.4f} | {t:+.2f} | {n} | {G} |")
        w("")

    # ---------------- verdict ----------------
    def get(leg, kind, adj):
        return res[leg][(kind, adj)]
    ws_test_net = get('WING SELL - TEST', 'net', 'vwap-1c')
    ws_train_net = get('WING SELL - TRAIN', 'net', 'vwap-1c')
    ws_test_net0 = get('WING SELL - TEST', 'net', 'vwap')
    ws_train_net0 = get('WING SELL - TRAIN', 'net', 'vwap')
    ws_test_gross = get('WING SELL - TEST', 'gross', 'vwap')

    w("## VERDICT")
    enough = len(wings) >= 1500 and len(wing_dates) >= 40
    thin = len(wing_dates) < 10
    # criterion: survives net (with 1c spread) in BOTH train and test, t>2, on >=10 dates
    surv = (ws_train_net[0] > 0 and ws_train_net[2] > 2 and
            ws_test_net[0] > 0 and ws_test_net[2] > 2 and
            ws_test_net[4] >= 10)
    # also a softer check: net at vwap (no spread)
    surv0 = (ws_train_net0[0] > 0 and ws_train_net0[2] > 2 and
             ws_test_net0[0] > 0 and ws_test_net0[2] > 2 and ws_test_net0[4] >= 10)

    w(f"- Power: {len(wings)} wing obs / {len(wing_dates)} dates "
      f"({'MEETS' if enough else 'BELOW'} the >=1500 obs & >=40 dates target).")
    if thin:
        w("- **WARNING: fewer than 10 wing dates — result is untrustworthy (thin-cluster artifact risk).**")
    w(f"- Gross wing-sell (no fee), TEST: mean {ws_test_gross[0]:+.4f}/contract, "
      f"t={ws_test_gross[2]:+.2f} — shows the raw edge before costs.")
    w(f"- Net wing-sell (1c spread), TRAIN: mean {ws_train_net[0]:+.4f}, t={ws_train_net[2]:+.2f}; "
      f"TEST: mean {ws_test_net[0]:+.4f}, t={ws_test_net[2]:+.2f}.")
    w(f"- Net wing-sell (no spread), TRAIN: mean {ws_train_net0[0]:+.4f}, t={ws_train_net0[2]:+.2f}; "
      f"TEST: mean {ws_test_net0[0]:+.4f}, t={ws_test_net0[2]:+.2f}.")
    if surv:
        w("\n**POSITIVE: a fee-surviving wing-overpricing (VRP) edge is present** — SELL-YES on wings "
          "is profitable net of the rounded fee AND a 1c half-spread in BOTH train and test "
          f"(TEST mean {ws_test_net[0]:+.4f}/contract, t={ws_test_net[2]:+.2f}, "
          f"{ws_test_net[4]} dates).")
    elif surv0:
        w("\n**MARGINAL: survives net of the rounded fee at the VWAP in both train and test, "
          "but NOT after a conservative 1c half-spread.** Edge is real gross of spread but "
          "fragile to execution.")
    else:
        w("\n**NULL: no well-powered, fee-surviving wing-overpricing edge.** Selling wings does not "
          "produce a positive, day-clustered-significant PnL net of the rounded fee "
          "(and 1c spread) in both train and test. Any gross tilt is eaten by the fee/spread "
          "and/or is not robust across the OOS split.")
    w("")

    open(REPORT, 'w').write('\n'.join(L))
    print('\n'.join(L))
    print(f'\n[report] written to {REPORT}')

if __name__ == '__main__':
    main()
