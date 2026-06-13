"""eth_revert_study.py -- Intra-window mean-reversion / overreaction test on ETH 15-min binary.

HYPOTHESIS: when the ETH 15-min binary YES mid makes a large move between minute k and k+1
(driven by a spot jump / taker flow burst), does the price OVERREACT and REVERT before settle?
If so, a MAKER resting a passive quote on the side the crowd is dumping earns reversion + spread.

DATA: hist parquet has per-minute mid/bid/ask/vol/spot path (15 min). trades has the tape.
      Settlement value of YES = res_up (mid -> 1 if up, 0 if down).

Tasks:
 1. Autocorrelation / reversion: after a +X move at minute k, expected change to settle.
 2. Overreaction vs information split: condition on spot follow-through / flow toxicity.
 3. Maker strategy: rest passive quote into the move; model taker-crosses-to-us fill.
 4. Exit: hold to settle vs flatten at touch.
 5. Verdict.

IS = first 60% of windows (by ws), OOS = last 40%.
"""
from __future__ import annotations
import sys
sys.path.insert(0, '/tmp/ev_revert')
import numpy as np
import pandas as pd

def parse_arr(v):
    if isinstance(v, np.ndarray): return v.astype(float)
    if isinstance(v, list): return np.array(v, float)
    import ast
    return np.array(ast.literal_eval(str(v)), float)

def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 2: return float('nan')
    s = x.std(ddof=1)
    return x.mean() / (s / np.sqrt(len(x))) if s > 1e-12 else float('nan')

def load():
    h = pd.read_parquet('/tmp/ev_revert/hist_kalshi_eth15m.parquet')
    t = pd.read_parquet('/tmp/ev_revert/trades_kalshi_eth15m.parquet')
    tidx = {r['ws']: r for _, r in t.iterrows()}
    rows = []
    for _, r in h.iterrows():
        ws = r['ws']
        mid = parse_arr(r['mid_path']); bid = parse_arr(r['bid_path']); ask = parse_arr(r['ask_path'])
        vol = parse_arr(r['vol_path']); spot = parse_arr(r['spot_path'])
        if len(mid) < 15: continue
        res = int(r['res_up'])
        tr = tidx.get(ws)
        if tr is not None:
            ta = parse_arr(tr['t']); tp = parse_arr(tr['p']); tsz = parse_arr(tr['sz']); tb = parse_arr(tr['buy']).astype(bool)
        else:
            ta = tp = tsz = np.array([]); tb = np.array([], bool)
        rows.append(dict(ws=ws, res=res, mid=mid, bid=bid, ask=ask, vol=vol, spot=spot,
                         t=ta, p=tp, sz=tsz, buy=tb))
    rows.sort(key=lambda d: d['ws'])
    return rows

def per_minute_flow(row):
    """Bucket trades into per-minute taker flow imbalance (signed notional) by minute index 0..14."""
    ws = row['ws']; ta = row['t']; tsz = row['sz']; tb = row['buy']
    flow = np.zeros(15); vol = np.zeros(15)
    if len(ta) == 0:
        return flow, vol
    for i in range(len(ta)):
        m = int((ta[i] - ws) // 60)
        if m < 0 or m > 14: continue
        s = tsz[i]
        flow[m] += s if tb[i] else -s
        vol[m] += s
    return flow, vol

# ============================================================
# TASK 1: REVERSION / AUTOCORRELATION
# ============================================================

def clean_mid(r):
    """Forward/back-fill NaNs in mid path so consecutive diffs are defined."""
    mid = r['mid'].copy()
    if np.isnan(mid).all():
        return mid
    # forward fill
    last = np.nan
    for i in range(len(mid)):
        if np.isnan(mid[i]): mid[i] = last
        else: last = mid[i]
    # back fill leading
    nxt = np.nan
    for i in range(len(mid) - 1, -1, -1):
        if np.isnan(mid[i]): mid[i] = nxt
        else: nxt = mid[i]
    return mid

def reversion_analysis(rows):
    print("=" * 72)
    print("TASK 1: INTRA-WINDOW REVERSION / AUTOCORRELATION (ETH 15-min)")
    print("=" * 72)
    for r in rows:
        r['midc'] = clean_mid(r)
    # Lag-1 autocorrelation of per-minute mid changes (pooled, minutes 2..12)
    dmid_all = []
    for r in rows:
        mid = r['midc']
        for k in range(1, 13):
            dmid_all.append((mid[k] - mid[k-1], mid[k+1] - mid[k]))
    dmid_all = np.array(dmid_all)
    d0 = dmid_all[:, 0]; d1 = dmid_all[:, 1]
    m = np.isfinite(d0) & np.isfinite(d1)
    ac1 = np.corrcoef(d0[m], d1[m])[0, 1]
    print(f"\nLag-1 autocorr of per-minute mid changes (k 1..12, n={m.sum()}): {ac1:+.4f}")
    print("  (negative => mean-reversion in the price PATH; positive => momentum)")

    # The trade-relevant question: after a move at minute k, what is the move TO SETTLE?
    # settle for YES = res. Define move dk = mid[k]-mid[k-1]. Post-move return to settle = res - mid[k].
    # If overreaction: large +dk -> mid[k] overshoots -> res-mid[k] negative (reverts down). And vice versa.
    print("\nMove-at-k vs realized return-to-settle (res - mid[k]), by move-size bucket:")
    print(f"{'move bucket (c)':<18} {'n':>6} {'mean dk':>8} {'mean ret2settle':>16} {'t':>7} {'corr(dk,ret)':>13}")
    recs = []
    for r in rows:
        mid = r['midc']; res = r['res']
        for k in range(2, 13):
            dk = mid[k] - mid[k-1]
            ret = res - mid[k]        # what a YES holder bought at mid[k] earns
            recs.append((dk, ret, mid[k]))
    recs = np.array(recs)
    dk = recs[:, 0]; ret = recs[:, 1]
    edges = [(-1.0, -0.10), (-0.10, -0.05), (-0.05, -0.02), (-0.02, 0.02),
             (0.02, 0.05), (0.05, 0.10), (0.10, 1.0)]
    for lo, hi in edges:
        sel = (dk >= lo) & (dk < hi) & np.isfinite(ret)
        if sel.sum() < 20: continue
        rr = ret[sel]
        print(f"[{lo:+.2f},{hi:+.2f})      {sel.sum():>6} {dk[sel].mean():>+8.3f} {rr.mean():>+16.4f} {tstat(rr):>+7.2f}")
    cc = np.corrcoef(dk[np.isfinite(ret)], ret[np.isfinite(ret)])[0, 1]
    print(f"\ncorr(move dk, return-to-settle) = {cc:+.4f}")
    print("  NOTE: ret-to-settle is dominated by drift toward 0/1 (binary pull). The OVERREACTION")
    print("  signal is whether a large +dk predicts NEGATIVE subsequent path move beyond that pull.")

    # Cleaner overreaction metric: subsequent PRICE-PATH move after k, NOT to settle.
    # post = mid[k+h] - mid[k]. If overreaction, sign(post) opposite to sign(dk).
    print("\nOverreaction: sign of subsequent path move vs the triggering move dk:")
    print(f"{'horizon h':<10} {'n(+dk)':>8} {'E[post|+dk]':>13} {'n(-dk)':>8} {'E[post|-dk]':>13}")
    for h in [1, 2, 3]:
        pos = []; neg = []
        for r in rows:
            mid = r['midc']
            for k in range(2, 13 - h):
                dk = mid[k] - mid[k-1]
                post = mid[k+h] - mid[k]
                if dk >= 0.05: pos.append(post)
                elif dk <= -0.05: neg.append(post)
        pos = np.array(pos); neg = np.array(neg)
        print(f"h={h:<8} {len(pos):>8} {pos.mean():>+13.4f} {len(neg):>8} {neg.mean():>+13.4f}")
    print("  (If reversion: E[post|+dk] < 0 and E[post|-dk] > 0. If momentum/info: same sign as dk.)")
    return ac1

# ============================================================
# TASK 2: OVERREACTION vs INFORMATION (condition on spot follow-through)
# ============================================================

def split_analysis(rows):
    print("\n" + "=" * 72)
    print("TASK 2: OVERREACTION vs INFORMATION (condition on spot follow-through & flow)")
    print("=" * 72)
    # For a binary move at k driven by spot, the move is INFORMED if spot keeps going
    # (follow-through) and NOISE if spot reverts. Measure subsequent path move conditioned on
    # whether the spot move that drove the binary move was sustained.
    # spot move bps at k: (spot[k]-spot[k-1])/spot[k-1]*1e4
    # follow-through: spot[k+2]-spot[k] same sign as spot[k]-spot[k-1]?
    print("\nSubsequent binary path move (mid[k+2]-mid[k]) after a LARGE binary move (|dk|>=0.05),")
    print("split by whether the SPOT continued (informed) or reverted (noise):")
    print(f"{'group':<28} {'n':>6} {'E[mid move k->k+2]':>18} {'t':>7}")
    groups = {'+dk & spot continues': [], '+dk & spot reverts': [],
              '-dk & spot continues': [], '-dk & spot reverts': []}
    for r in rows:
        mid = r['midc']; spot = r['spot']
        for k in range(2, 11):
            dk = mid[k] - mid[k-1]
            if abs(dk) < 0.05: continue
            dspot = spot[k] - spot[k-1]
            spot_fwd = spot[k+2] - spot[k]
            post = mid[k+2] - mid[k]
            cont = (np.sign(dspot) == np.sign(spot_fwd)) and dspot != 0
            if dk >= 0.05:
                groups['+dk & spot continues' if cont else '+dk & spot reverts'].append(post)
            else:
                groups['-dk & spot continues' if cont else '-dk & spot reverts'].append(post)
    for g, v in groups.items():
        v = np.array(v)
        if len(v) < 10:
            print(f"{g:<28} {len(v):>6}  (too few)"); continue
        print(f"{g:<28} {len(v):>6} {v.mean():>+18.4f} {tstat(v):>+7.2f}")
    print("  EXPECT if hypothesis holds: 'spot reverts' rows show binary move reversing (opposite sign to dk);")
    print("  'spot continues' rows show binary move sticking (same sign as dk = information).")

    # Condition on flow toxicity proxy: per-minute taker flow imbalance magnitude at k.
    print("\nSplit by FLOW: was the binary move accompanied by one-sided taker flow (toxic) or thin/balanced?")
    print(f"{'group':<34} {'n':>6} {'E[mid move k->k+2]':>18} {'t':>7}")
    fg = {'+dk high one-sided flow': [], '+dk low/balanced flow': [],
          '-dk high one-sided flow': [], '-dk low/balanced flow': []}
    flow_mags = []
    flows_cache = {}
    for r in rows:
        flow, vol = per_minute_flow(r)
        flows_cache[r['ws']] = (flow, vol)
        flow_mags.extend(np.abs(flow[2:13]))
    fthr = np.nanpercentile([x for x in flow_mags if x > 0], 70) if flow_mags else 0
    for r in rows:
        mid = r['midc']; flow, vol = flows_cache[r['ws']]
        for k in range(2, 11):
            dk = mid[k] - mid[k-1]
            if abs(dk) < 0.05: continue
            post = mid[k+2] - mid[k]
            toxic = abs(flow[k]) >= fthr
            if dk >= 0.05:
                fg['+dk high one-sided flow' if toxic else '+dk low/balanced flow'].append(post)
            else:
                fg['-dk high one-sided flow' if toxic else '-dk low/balanced flow'].append(post)
    for g, v in fg.items():
        v = np.array(v)
        if len(v) < 10:
            print(f"{g:<34} {len(v):>6}  (too few)"); continue
        print(f"{g:<34} {len(v):>6} {v.mean():>+18.4f} {tstat(v):>+7.2f}")
    print(f"  (flow toxicity threshold = 70th pct of |per-min taker imbalance| = {fthr:.1f})")
    return flows_cache

if __name__ == '__main__':
    rows = load()
    n = len(rows)
    cut = int(n * 0.6)
    print(f"Loaded {n} ETH windows. IS={cut}, OOS={n-cut}")
    reversion_analysis(rows)
    split_analysis(rows)
