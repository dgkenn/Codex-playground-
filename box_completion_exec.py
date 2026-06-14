#!/usr/bin/env python3
"""box_completion_exec.py -- SECOND-LEG COMPLETION / EXECUTION layer of the BTC 15m maker-box.

Sibling BOX_ADVERSE_OPEN.md proved toxicity is INTRINSIC to completion and INVISIBLE at open
(OOS AUC 0.56). It also found LIVE toxic 31% vs BACKTEST 5.7% -> the dominant remaining lever is
LIVE EXECUTION QUALITY of the SECOND leg, not opening selection. This script:

  1. CHARACTERIZE second-leg completion from LIVE fills + winrecs: legging_gap distribution for
     CLEAN vs TOXIC boxes, spot move during the gap, strand vs chase-completion split, c/box per
     second of gap.
  2. EXPLAIN the live-31% vs backtest-5.7% gap: optimistic fill model vs queue/latency vs over-chasing.
  3. TEST completion levers offline on the tape (paired/simultaneous quoting; second-leg-moved
     completion model that the q0=0 reconstruction IGNORES; chase-vs-hold on the spot move) -- and
     STRESS them (the backtest fill model is known-optimistic).

LIVE: walk every commit of origin/live-state, dedup fills by trade_id + winrecs by ws, settle via
Kalshi API. TAPE: hist/trades parquet via box_policy_ab.window_fills (q0=0 SCREEN).
"""
from __future__ import annotations
import subprocess, json, math, sys
import numpy as np
import pandas as pd

HIST = 'hist_kalshi_btc15m.parquet'
TRADES = 'trades_kalshi_btc15m.parquet'
DAYS = ['2026-06-13', '2026-06-14']
M_TAKER = 0.07


def walk(path):
    commits = subprocess.check_output(['git', 'log', '--format=%H', 'origin/live-state']).decode().split()
    out = []
    for c in commits:
        try:
            blob = subprocess.check_output(['git', 'show', f'{c}:{path}'], stderr=subprocess.DEVNULL).decode()
        except Exception:
            continue
        for ln in blob.splitlines():
            if ln.strip():
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    return out


def taker_fee(price, M=M_TAKER):
    p = min(max(price, 0.0), 1.0)
    return math.ceil(M * p * (1.0 - p) * 100.0) / 100.0


# ---------------------------------------------------------------- LIVE settle
def settle_map(tickers):
    import requests
    B = 'https://api.elections.kalshi.com/trade-api/v2'
    ses = requests.Session()
    sc = {}
    for tk in tickers:
        s = None
        for _ in range(3):
            try:
                s = ses.get(f'{B}/markets/{tk}', timeout=8).json().get('market', {}).get('result')
                break
            except Exception:
                pass
        sc[tk] = s if s in ('yes', 'no') else None
    return sc


def load_live():
    """Per-ticker box reconstruction from raw fills with fill-level ctx (spot/sig/t_in_win/role)."""
    fl = {}
    for day in DAYS:
        for r in walk(f'live_state/{day}/kalshi_fees_btc15m.jsonl'):
            tid = (r.get('raw') or {}).get('trade_id')
            if tid:
                fl[tid] = r
    wr = {}
    for day in DAYS:
        for r in walk(f'live_state/{day}/kalshi_winrec_btc15m.jsonl'):
            if 'ws' in r:
                wr[r['ws']] = r
    byc = {}
    for r in fl.values():
        byc.setdefault(r['ticker'], []).append(r)
    sc = settle_map(list(byc))
    rows = []
    for tk, fills in byc.items():
        s = sc.get(tk)
        if s not in ('yes', 'no'):
            continue
        fills = sorted(fills, key=lambda r: (r['raw'].get('ts_ms') or r['raw'].get('ts', 0)))
        ny = sum(r['count'] for r in fills if r['side'] == 'yes')
        nn = sum(r['count'] for r in fills if r['side'] == 'no')
        cost = sum(r['price'] * r['count'] for r in fills)
        payout = sum(r['count'] for r in fills if r['side'] == s)
        nbox = min(ny, nn) if min(ny, nn) > 0 else max(ny, nn)
        pnl = (payout - cost) / max(nbox, 1)
        # first YES fill ts and first NO fill ts -> legging gap (fill-level truth)
        def first(side):
            xs = [r for r in fills if r['side'] == side]
            if not xs:
                return None
            return min((r['raw'].get('ts_ms') or 0) / 1000.0 or r['raw'].get('ts', 0) for r in xs)
        ty, tn = first('yes'), first('no')
        gap = abs(ty - tn) if (ty and tn) else None
        # spot at first YES vs first NO (ctx.spot)
        def ctx_spot(side):
            xs = [r for r in fills if r['side'] == side and (r.get('ctx') or {}).get('spot')]
            if not xs:
                return None
            xs = sorted(xs, key=lambda r: (r['raw'].get('ts_ms') or 0))
            return xs[0]['ctx']['spot']
        sy, sn = ctx_spot('yes'), ctx_spot('no')
        spot_mv = abs(sy - sn) / sy * 1e4 if (sy and sn and sy > 0) else None
        n_taker = sum(1 for r in fills if (r['raw'] or {}).get('is_taker'))
        n_maker = sum(1 for r in fills if not (r['raw'] or {}).get('is_taker'))
        rows.append(dict(tk=tk, ny=ny, nn=nn, pnl=pnl, cost=cost, payout=payout,
                         gap=gap, spot_mv=spot_mv, n_taker=n_taker, n_maker=n_maker,
                         stranded=(ny != nn), settle=s))
    return pd.DataFrame(rows), wr, fl


# ---------------------------------------------------------------- TAPE (SCREEN)
def parse_arr(v):
    if isinstance(v, np.ndarray):
        return v.astype(float)
    if isinstance(v, list):
        return np.array(v, float)
    import ast
    return np.array(ast.literal_eval(str(v)), float)


def load_tape():
    from box_policy_ab import window_fills
    hist = pd.read_parquet(HIST)
    trades = pd.read_parquet(TRADES)
    hi = {r['ws']: r for _, r in hist.iterrows()}
    ti = {r['ws']: r for _, r in trades.iterrows()}
    common = sorted(set(hi) & set(ti))
    out = {}
    for ws in common:
        h, t = hi[ws], ti[ws]
        try:
            fills = window_fills(ws, int(h['res_up']),
                                 parse_arr(h['bid_path']), parse_arr(h['ask_path']),
                                 parse_arr(h['spot_path']), parse_arr(h['vol_path']),
                                 (parse_arr(t['t']), parse_arr(t['p']), parse_arr(t['sz']),
                                  parse_arr(t['buy']).astype(bool)), oi_slope=None, q0=0.0)
        except Exception:
            fills = []
        if fills:
            out[ws] = (fills, h, t)
    return out


GATE_DEPTH, GATE_K, GATE_SIG = 33000.0, 10, 10.0


def open_gate(f):
    d = f.get('depth')
    d = 0.0 if (d is None or (isinstance(d, float) and np.isnan(d))) else float(d)
    return d >= GATE_DEPTH and f.get('k', 99) <= GATE_K and abs(f.get('sig', 0.0) or 0.0) < GATE_SIG


def p_yeq(f):
    return f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)


def col(h, name):
    return parse_arr(h[name])


# ============================================================================
def main():
    print('=' * 80)
    print('BOX SECOND-LEG COMPLETION / EXECUTION -- BTC 15m maker-box')
    print('=' * 80)

    # ----------------------------------------------------- 1. LIVE characterization
    print('\n[LIVE] loading fills + winrecs, settle via Kalshi API ...')
    live, wr, fl = load_live()
    n = len(live)
    tox = live['pnl'] < 0
    print(f'  settled live markets: N={n}  toxic(P&L<0)={tox.sum()} ({tox.mean()*100:.0f}%)  '
          f'mean {live.pnl.mean()*100:+.1f}c  median {live.pnl.median()*100:+.1f}c')
    bal = live[live.ny == live.nn]
    strd = live[live.ny != live.nn]
    print(f'  BALANCED (ny==nn): N={len(bal)}  toxic={ (bal.pnl<0).sum() } '
          f'(mean {bal.pnl.mean()*100:+.1f}c)   STRANDED: N={len(strd)} toxic={ (strd.pnl<0).sum() } '
          f'(mean {strd.pnl.mean()*100:+.1f}c)')
    tox_b = (bal.pnl < 0).sum()
    tox_s = (strd.pnl < 0).sum()
    print(f'  TOXIC decomposition: completed-but-toxic(balanced)={tox_b}  strand-toxic={tox_s}  '
          f'-> strand share of toxicity = {100*tox_s/max(tox_b+tox_s,1):.0f}%')

    # legging gap: CLEAN vs TOXIC (fill-level gap from raw fills)
    print('\n[1] LEGGING GAP -- CLEAN vs TOXIC boxes (fill-level, first-YES vs first-NO ts)')
    g = live.dropna(subset=['gap'])
    for lab, sub in [('CLEAN', g[g.pnl >= 0]), ('TOXIC', g[g.pnl < 0]), ('ALL', g)]:
        gs = sub['gap'].values
        if len(gs):
            print(f'  {lab:6s} N={len(gs):3d}  gap median {np.median(gs):6.1f}s  mean {np.mean(gs):6.1f}s  '
                  f'p90 {np.percentile(gs,90):6.1f}s  max {gs.max():6.1f}s')
    # winrec-reported gap (independent source)
    legs = [w['legging_gap_s'] for w in wr.values() if w.get('legging_gap_s') is not None]
    if legs:
        legs = np.array(legs)
        print(f'  [winrec gap, all windows] N={len(legs)} median {np.median(legs):.1f}s '
              f'mean {legs.mean():.1f}s p90 {np.percentile(legs,90):.1f}s')
        # toxic winrecs (use winrec realized/cost if settle present, else skip)

    # spot move during gap
    print('\n[1b] SPOT MOVE during the legging gap (|spot@firstNO - spot@firstYES|, bps of spot)')
    gm = live.dropna(subset=['spot_mv'])
    for lab, sub in [('CLEAN', gm[gm.pnl >= 0]), ('TOXIC', gm[gm.pnl < 0])]:
        v = sub['spot_mv'].values
        if len(v):
            print(f'  {lab:6s} N={len(v):3d}  spot-move median {np.median(v):5.1f}bps  mean {np.mean(v):5.1f}bps  '
                  f'p90 {np.percentile(v,90):5.1f}bps')

    # c/box per second of gap (regression)
    print('\n[1c] c/box lost per second of legging gap (OLS, live)')
    gg = live.dropna(subset=['gap'])
    if len(gg) >= 8:
        x = gg['gap'].values
        y = gg['pnl'].values * 100.0
        b1, b0 = np.polyfit(x, y, 1)
        r = np.corrcoef(x, y)[0, 1]
        print(f'  N={len(gg)}  slope = {b1:+.3f} c/box per second  intercept {b0:+.2f}c  corr {r:+.2f}')
        # binned
        gg = gg.copy(); gg['bin'] = pd.cut(gg['gap'], [0, 3, 10, 30, 1e9],
                                           labels=['<3s', '3-10s', '10-30s', '>30s'])
        print('  binned mean c/box by gap:')
        for bn, sub in gg.groupby('bin', observed=True):
            print(f'    {str(bn):8s} N={len(sub):3d}  mean {sub.pnl.mean()*100:+.1f}c  toxic {100*(sub.pnl<0).mean():.0f}%')

    # taker fills as the chase-completion signature
    print('\n[1d] TAKER (chase/cross) fills -- completed-by-crossing signature')
    lt = live.copy()
    lt['taker_frac'] = lt['n_taker'] / (lt['n_taker'] + lt['n_maker']).clip(lower=1)
    for lab, sub in [('CLEAN', lt[lt.pnl >= 0]), ('TOXIC', lt[lt.pnl < 0])]:
        print(f'  {lab:6s} N={len(sub):3d}  taker_frac mean {sub.taker_frac.mean()*100:.0f}%  '
              f'mean takers/box {sub.n_taker.mean():.2f}')
    tkc = lt[lt.n_taker > 0]; tk0 = lt[lt.n_taker == 0]
    print(f'  boxes with >=1 TAKER fill: N={len(tkc)} mean {tkc.pnl.mean()*100:+.1f}c toxic {100*(tkc.pnl<0).mean():.0f}%')
    print(f'  boxes ALL-MAKER (no taker):  N={len(tk0)} mean {tk0.pnl.mean()*100:+.1f}c toxic {100*(tk0.pnl<0).mean():.0f}%')

    # ----------------------------------------------------- 2 + 3. TAPE
    print('\n[TAPE] loading hist/trades parquet (q0=0 SCREEN) ...')
    tape = load_tape()
    ws_list = sorted(tape)
    import datetime as dt
    span = f"{dt.datetime.utcfromtimestamp(ws_list[0]):%Y-%m-%d}..{dt.datetime.utcfromtimestamp(ws_list[-1]):%Y-%m-%d}"
    print(f'  windows w/ book+tape: {len(ws_list)}  span {span}')

    print('\n[2] LIVE-31% vs BACKTEST-5.7% gap: the q0=0 model fills the completing leg at the')
    print('    SAME-MINUTE resting touch. Re-price the completing leg at the MOVED touch g minutes')
    print('    later (the legging gap) -- the cost the optimistic model omits.')
    # Reconstruct boxes on the tape with the deployed pair-gate, but model the completing leg paying
    # the touch g minutes after the open leg fills.
    res_gap = completion_gap_model(tape, ws_list)
    print('\n  toxic frac & mean c/box vs assumed legging gap (minutes the completing leg fills later):')
    print('  gap=0 == the optimistic backtest (BOX_ADVERSE_OPEN); larger gap == realistic legging')
    for gmins, st in res_gap.items():
        print(f'    gap={gmins}min  N={st["n"]:4d}  toxic {st["tox"]*100:5.1f}%  mean {st["mean"]*100:+.3f}c  '
              f'strand {st["strand"]*100:4.1f}%')

    # ----------------------------------------------------- 3. LEVERS
    print('\n[3] COMPLETION LEVERS (offline tape; STRESSED -- model known optimistic)')
    print('\n  LEVER A: SIMULTANEOUS/PAIRED quoting (quote BOTH legs from t0; box completes at the')
    print('  same-minute touch -> gap~0). This is the gap=0 row above. Upper bound; live queue caps it.')
    print('  LEVER B: SMARTER CHASE -- complete toward the moved touch ONLY when the spot move during')
    print('  the gap is SMALL; HOLD/strand-and-dispose when the move is adverse & large.')
    chase_vs_hold(tape, ws_list)

    print('\nDONE. See BOX_COMPLETION_EXEC.md for the writeup.')


def completion_gap_model(tape, ws_list, gaps=(0, 1, 2, 3)):
    """For each pair-gated OPEN leg, model the completing leg paying the touch `g` minutes LATER.
    Box P&L = settle_open + settle_complete_at_moved_touch. If the touch moved so far the completing
    leg can't be afforded at a non-negative lock within the give budget (basis would exceed cap),
    the leg STRANDS and is disposed (settle_open + capcross). This injects the post-open price-path
    cost the q0=0 same-minute fill omits."""
    out = {}
    GIVE = 0.10  # close_max_give-ish disposal cap
    for g in gaps:
        rows = []
        for ws in ws_list:
            fills, h, _ = tape[ws]
            bid = col(h, 'bid_path'); ask = col(h, 'ask_path'); res = int(h['res_up'])
            net = 0; open_leg = None
            for f in fills:
                step = 1 if f['side'] == 'bid' else -1
                nn = net + step
                if abs(nn) > 1:
                    continue
                if net != 0 and abs(nn) < abs(net) and open_leg is not None:
                    k0 = int(open_leg['k'])
                    kc = min(k0 + g, 12)
                    if open_leg['side'] == 'bid':
                        # open YES@b0; complete NO = buy YES-ask at completion time -> settle = a' - res
                        a_now = ask[kc] if not np.isnan(ask[kc]) else ask[k0]
                        settle_open = open_leg['settle']                 # res - b0
                        settle_comp = a_now - res
                        basis = open_leg['p'] + a_now                    # cost_yes + cost_no
                    else:
                        b_now = bid[kc] if not np.isnan(bid[kc]) else bid[k0]
                        settle_open = open_leg['settle']                 # a0 - res
                        settle_comp = res - b_now
                        basis = (1.0 - open_leg['p']) + (1.0 - b_now)
                    # if completing would lock a loss worse than the give cap, STRAND+dispose instead
                    lock = 1.0 - basis
                    if lock < -GIVE:
                        hold = settle_open
                        early = open_leg.get('exit', hold)
                        fee = taker_fee(p_yeq(open_leg))
                        disp = hold if (early - fee) < -GIVE else (early - fee)
                        rows.append((disp, 'strand'))
                    else:
                        rows.append((settle_open + settle_comp, 'paired'))
                    open_leg = None
                else:
                    if not open_gate(f):
                        continue
                    open_leg = f
                net = nn
            if open_leg is not None:
                hold = open_leg['settle']; early = open_leg.get('exit', hold)
                fee = taker_fee(p_yeq(open_leg))
                disp = hold if (early - fee) < -GIVE else (early - fee)
                rows.append((disp, 'strand'))
        pnl = np.array([r[0] for r in rows])
        kind = np.array([r[1] for r in rows])
        out[g] = dict(n=len(pnl), tox=float((pnl < 0).mean()), mean=float(pnl.mean()),
                      strand=float((kind == 'strand').mean()))
    return out


def chase_vs_hold(tape, ws_list):
    """At a realistic legging gap (g=2 min), compare three completion policies on the SAME boxes:
      (1) ALWAYS CHASE: complete at the moved touch whenever lock>=-GIVE (the deployed dispose-cross).
      (2) HOLD-IF-ADVERSE: complete only if the spot move during the gap is SMALL (|move|<thr);
          otherwise STRAND+dispose (strands are ~100% toxic but bounded; a big-move completion is the
          balanced -10c box). Uses the trader's OWN observable: spot move over the gap.
      (3) NEVER CHASE (strand-and-dispose all unpaired): the floor.
    Reports net c/box for each at g=2, plus a sweep over the move threshold."""
    GIVE = 0.10
    g = 2
    def spot_move(h, k0, kc):
        sp = col(h, 'spot_path')
        a, b = sp[k0], sp[kc]
        if np.isnan(a) or np.isnan(b) or a <= 0:
            return 0.0
        return abs(b - a) / a * 1e4  # bps

    def run(thr):
        rows = []
        for ws in ws_list:
            fills, h, _ = tape[ws]
            bid = col(h, 'bid_path'); ask = col(h, 'ask_path'); res = int(h['res_up'])
            net = 0; open_leg = None
            for f in fills:
                step = 1 if f['side'] == 'bid' else -1
                nn = net + step
                if abs(nn) > 1:
                    continue
                if net != 0 and abs(nn) < abs(net) and open_leg is not None:
                    k0 = int(open_leg['k']); kc = min(k0 + g, 12)
                    mv = spot_move(h, k0, kc)
                    if open_leg['side'] == 'bid':
                        a_now = ask[kc] if not np.isnan(ask[kc]) else ask[k0]
                        settle_open = open_leg['settle']; settle_comp = a_now - res
                        basis = open_leg['p'] + a_now
                    else:
                        b_now = bid[kc] if not np.isnan(bid[kc]) else bid[k0]
                        settle_open = open_leg['settle']; settle_comp = res - b_now
                        basis = (1.0 - open_leg['p']) + (1.0 - b_now)
                    lock = 1.0 - basis
                    complete_ok = (lock >= -GIVE) and (thr is None or mv <= thr)
                    if complete_ok:
                        rows.append(settle_open + settle_comp)
                    else:
                        hold = settle_open; early = open_leg.get('exit', hold)
                        fee = taker_fee(p_yeq(open_leg))
                        rows.append(hold if (early - fee) < -GIVE else (early - fee))
                    open_leg = None
                else:
                    if not open_gate(f):
                        continue
                    open_leg = f
                net = nn
            if open_leg is not None:
                hold = open_leg['settle']; early = open_leg.get('exit', hold)
                fee = taker_fee(p_yeq(open_leg))
                rows.append(hold if (early - fee) < -GIVE else (early - fee))
        p = np.array(rows)
        return len(p), p.mean(), (p < 0).mean()

    print('  (g=2min legging gap assumed; thr = max spot move (bps) over the gap to still CHASE)')
    print('  policy                         N     mean c/box   toxic%   tot c')
    for name, thr in [('ALWAYS CHASE (deployed)', 1e9), ('chase if move<=30bps', 30),
                      ('chase if move<=20bps', 20), ('chase if move<=12bps', 12),
                      ('chase if move<=8bps', 8), ('NEVER chase (strand+dispose)', -1)]:
        n, m, t = run(thr)
        print(f'  {name:30s} {n:4d}   {m*100:+7.3f}    {t*100:5.1f}   {m*100*n:+8.0f}')


if __name__ == '__main__':
    main()
