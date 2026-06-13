"""box_fill_yield.py -- Box-yield Phase 1 FILL CONVERSION study.

FOCUS: the FIRST term of TOTAL PnL = (#boxes filled) x (avg locked edge/box) - strand losses.
       Raise #boxes filled and P(both fill) using MAKER fills only (no spread paid).

We re-replay the raw Kalshi 15m tape (hist + trades parquets) under ALTERNATE posting
policies so we can measure FILL CONVERSION, not just PnL:
  - at-touch (live): rest YES bid at b0, NO at a0 (== window_fills with q0).
  - improve-tick: rest 1c inside the touch on one/both sides (jump queue, wider trigger,
    give up 1c of locked edge on the improved leg).
  - queue-ahead sensitivity: q0 sweep (true queue position is NOT observable on the tape;
    we bracket it with q0 in {0, depth-fraction} as a sensitivity, not a point estimate).
  - k-slot timing: boxes-per-window conversion by minute k=2..12.
  - completion-regime open bar: open MORE when completion_score is favorable.
  - multi-slot / size skew toward the slower-filling side.

A "box" = one YES leg AND one NO leg both filled in the SAME window (net returns to 0
after going to +-1). #boxes/window and P(both fill) are the conversion metrics.

TAPE CAVEATS (explicit):
  * The parquet is a REPLAY: a maker fill is inferred when a taker trade crosses our
    resting price. We do NOT observe our true queue position, so "front of queue" (q0=0)
    is an OPTIMISTIC bound and a positive q0 is PESSIMISTIC; the truth is bracketed.
  * Improve-tick assumes posting 1c inside makes us alone at a new price (queue-ahead~0)
    and that the SAME taker flow that crossed the old touch still crosses the improved
    price. Both are book-mechanics assumptions the tape cannot fully prove; sweeps below
    are SCREENS for forward validation, not live-validated edges.
  * Adding our own size to the book would change other agents' behavior (reflexivity);
    a replay cannot capture that.
"""
from __future__ import annotations
import sys, ast
sys.path.insert(0, '/tmp/by_fill')
import numpy as np
import pandas as pd

from box_policy_ab import completion_score, tstat, _vpin_buckets, _vpin_at

# ---------------------------------------------------------------------------
# RAW TAPE LOADER (so we control posting price + queue assumption)
# ---------------------------------------------------------------------------

def _pa(v):
    if isinstance(v, np.ndarray):
        return v.astype(float)
    if isinstance(v, list):
        return np.array(v, float)
    return np.array(ast.literal_eval(str(v)), float)


def load_raw(asset='btc'):
    hist = pd.read_parquet(f'/tmp/by_fill/hist_kalshi_{asset}15m.parquet')
    trades = pd.read_parquet(f'/tmp/by_fill/trades_kalshi_{asset}15m.parquet')
    hidx = {r['ws']: r for _, r in hist.iterrows()}
    tidx = {r['ws']: r for _, r in trades.iterrows()}
    common = sorted(set(hidx) & set(tidx))
    out = {}
    for ws in common:
        h, t = hidx[ws], tidx[ws]
        out[ws] = dict(
            ws=ws, res=int(h['res_up']),
            bid=_pa(h['bid_path']), ask=_pa(h['ask_path']),
            spot=_pa(h['spot_path']),
            depth=(_pa(h['vol_path']) if h.get('vol_path') is not None else np.full(15, np.nan)),
            t=_pa(t['t']), p=_pa(t['p']), sz=_pa(t['sz']),
            buy=_pa(t['buy']).astype(bool),
        )
    return out, common


# ---------------------------------------------------------------------------
# FILL RECONSTRUCTION under an arbitrary posting policy.
#   improve_bid / improve_ask: cents to post INSIDE the touch (0 = at touch).
#   q0: queue-ahead size to consume before our resting size fills (contracts).
#       For improved quotes we are alone at a new price -> q0_eff = 0.
# Returns time-ordered fill list (same schema window_fills uses) plus per-leg
# 'improved' flag and the locked-edge accounting price.
# ---------------------------------------------------------------------------

def reconstruct(win, improve_bid=0.0, improve_ask=0.0, q0=0.0, q0_improved=0.0,
                kmin=2, kmax=12):
    ws, res = win['ws'], win['res']
    bid, ask, spot, depth = win['bid'], win['ask'], win['spot'], win['depth']
    t_arr, p_arr, sz_arr, buy_arr = win['t'], win['p'], win['sz'], win['buy']
    spot_l = np.concatenate([[np.nan], spot[:-1]])
    bt, bi = _vpin_buckets(t_arr, sz_arr, buy_arr)
    recs = []
    for k in range(kmin, kmax + 1):
        b0, a0 = bid[k], ask[k]
        if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
            continue
        # Our posting prices (improve = move inside the touch)
        my_bid = round(b0 + improve_bid, 4)
        my_ask = round(a0 - improve_ask, 4)
        if my_bid >= my_ask:   # crossed / locked -> skip (can't post inside a 1c book on both)
            my_bid = b0; my_ask = a0
            ib = ia = False
        else:
            ib = improve_bid > 0
            ia = improve_ask > 0
        s_now, s_then = spot_l[k], spot_l[max(k - 3, 0)]
        mv = (s_now / s_then - 1) * 1e4 if (s_now and s_then and s_now > 0 and s_then > 0) else 0.0
        spread = round(a0 - b0, 4); tau = (15 - k) / 15.0
        dk = float(depth[k]) if not np.isnan(depth[k]) else None
        pl, ph = ws + 60 * (k - 1), ws + 60 * k
        j0, j1 = np.searchsorted(t_arr, pl), np.searchsorted(t_arr, ph)
        flow = float(np.sum(np.where(buy_arr[j0:j1], sz_arr[j0:j1], -sz_arr[j0:j1])))
        lo, hi = ws + 60 * (k + 1), ws + 60 * (k + 2)
        i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
        qb = (q0_improved if ib else q0)
        qa = (q0_improved if ia else q0)
        done_b = done_a = False
        for i in range(i0, i1):
            if done_b and done_a:
                break
            p, sz, buy = p_arr[i], sz_arr[i], buy_arr[i]
            # resting bid fills on a sell taker crossing our (possibly improved) bid
            if not done_b and not buy and p <= my_bid + 1e-9:
                if qb >= sz:
                    qb -= sz
                else:
                    recs.append(dict(ws=ws, side='bid', settle=res - my_bid,
                                     p=my_bid, spread=spread, k=k, tau=tau, flow=flow,
                                     depth=dk, oi=None, vpin=_vpin_at(bt, bi, t_arr[i]),
                                     tksize=float(sz), improved=ib,
                                     spot=(float(spot[k]) if not np.isnan(spot[k]) else None)))
                    done_b = True
            if not done_a and buy and p >= my_ask - 1e-9:
                if qa >= sz:
                    qa -= sz
                else:
                    recs.append(dict(ws=ws, side='ask', settle=my_ask - res,
                                     p=round(1.0 - my_ask, 4), spread=spread, k=k, tau=tau,
                                     flow=-flow, depth=dk, oi=None,
                                     vpin=_vpin_at(bt, bi, t_arr[i]), tksize=float(sz),
                                     improved=ia,
                                     spot=(float(spot[k]) if not np.isnan(spot[k]) else None)))
                    done_a = True
    return recs


# ---------------------------------------------------------------------------
# BOX WALK: cap |net|<=1, pair when possible. Returns per-window:
#   pnl (locked edge summed), n_boxes (completed pairs), both_fill (>=1 box),
#   stranded (leftover open leg), and the strand leg for accounting.
# open_ok(f)->bool gates OPENING. size_of(f)->float sizes the open leg
# (completing leg matches). strand_value(leg)-> $ for a leftover leg.
# ---------------------------------------------------------------------------

def box_walk(fills, open_ok=None, size_of=None, strand_value=None):
    net = 0; pnl = 0.0; open_leg = None; open_sz = 1.0; n_boxes = 0
    for f in fills:
        step = 1 if f['side'] == 'bid' else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        if net != 0 and abs(nn) < abs(net):    # completing fill
            pnl += open_sz * (f['settle'] + (open_leg['settle'] if open_leg else 0.0))
            n_boxes += 1
            open_leg = None; open_sz = 1.0
            net = nn
        else:                                   # opening fill
            if open_ok is not None and not open_ok(f):
                continue
            open_leg = f
            open_sz = float(size_of(f)) if size_of else 1.0
            net = nn
    stranded = open_leg is not None
    if stranded:
        if strand_value is not None:
            pnl += open_sz * strand_value(open_leg)
        else:
            pnl += open_sz * open_leg['settle']
    return dict(pnl=pnl, n_boxes=n_boxes, both=int(n_boxes >= 1),
                stranded=int(stranded), strand_leg=open_leg)


def run_set(raw, ws_list, recon_kw=None, walk_kw=None):
    recon_kw = recon_kw or {}; walk_kw = walk_kw or {}
    pnl = []; nb = []; both = []; strand = []
    for ws in ws_list:
        fills = reconstruct(raw[ws], **recon_kw)
        r = box_walk(fills, **walk_kw)
        pnl.append(r['pnl']); nb.append(r['n_boxes'])
        both.append(r['both']); strand.append(r['stranded'])
    return (np.array(pnl, float), np.array(nb, float),
            np.array(both, float), np.array(strand, float))


def summ(pnl, nb, both, strand):
    return dict(
        n=len(pnl), net=pnl.mean() * 100, ts=tstat(pnl),
        boxes=nb.mean(), pboth=both.mean(), strand=strand.mean() * 100,
        total=pnl.sum() * 100,
    )


def paired_ts(a, b):
    """t-stat of paired per-window difference a-b."""
    d = np.asarray(a, float) - np.asarray(b, float)
    d = d[~np.isnan(d)]
    if len(d) < 8 or d.std(ddof=1) == 0:
        return float('nan')
    return float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))))


# ---------------------------------------------------------------------------
# K-SLOT conversion: for each minute k, what fraction of windows get a fill on
# that slot, and what is the per-slot pair rate (a fill that later pairs)?
# ---------------------------------------------------------------------------

def kslot_table(raw, ws_list):
    # counts[k] = #fills opened, paired[k] = #of those that paired (completed a box)
    open_ct = {k: 0 for k in range(2, 13)}
    pair_ct = {k: 0 for k in range(2, 13)}
    fill_ct = {k: 0 for k in range(2, 13)}  # any fill (either side) at slot k
    for ws in ws_list:
        fills = reconstruct(raw[ws])
        for f in fills:
            fill_ct[f['k']] += 1
        # walk to attribute pair credit to the OPENING leg's k
        net = 0; open_leg = None
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                if open_leg is not None:
                    pair_ct[open_leg['k']] += 1
                open_leg = None
            else:
                open_ct[f['k']] += 1
                open_leg = f
            net = nn
    rows = []
    for k in range(2, 13):
        oc = open_ct[k]; pc = pair_ct[k]
        rows.append(dict(k=k, opens=oc, paired=pc,
                         pair_rate=(pc / oc if oc else float('nan')),
                         fills=fill_ct[k]))
    return rows
