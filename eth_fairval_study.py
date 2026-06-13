"""eth_fairval_study.py -- Spot-GBM fair-value stat-arb on the Kalshi ETH 15-min binary.

THESIS: the two-sided ETH maker box is dead. But if a GBM fair probability for the up/down
binary (ETH spot vs window strike, time-to-expiry, realized vol) systematically deviates from
the Kalshi price, we can TAKE the underpriced side (crypto15m FEE=0 -> cost is the crossed spread).

CRITICAL REALISM FIX (vs a naive first pass):
  A TAKER must CROSS the spread. Buying YES costs the YES ASK; buying NO costs the YES BID
  (= 1 - ask_no... here NO ask = 1 - YES bid). We reconstruct bid_path/ask_path per minute and
  charge the taker the true crossed price -- NOT the resting maker fill price 'p' (which is the
  favorable side a passive maker got and would massively overstate edge).

  Fair value is benchmarked against the Kalshi MID (the unbiased market estimate), and a trade
  only fires when fair beats the price the taker would actually PAY (ask for YES, 1-bid for NO).

PIPELINE
  1. FAIR MODEL: fair_yes = N(d2), d2=(ln(S/K) - 0.5 sig^2 tau)/(sig sqrt(tau)), mu=0.
     S=ETH spot at minute k, K=strike=spot_prev[-1] (spot at window open), tau=(15-k) min,
     sig=per-minute realized vol (calibrated on IS, swept for robustness).
  2. CALIBRATION: fair_yes & kalshi-mid reliability vs realized res_up; Brier; pick vol.
  3. GAP vs MID and vs the PRICE-PAID (crossed). Favorite-longshot check on the mid.
  4. TAKER STAT-ARB: fire when fair_edge_after_cross > thr. Sweep. OOS metrics, t.
  5. ROBUSTNESS: vol mis-spec; raw favorite-longshot benchmark; surviving #trades.

Usage: python eth_fairval_study.py
"""
from __future__ import annotations
import sys, ast
sys.path.insert(0, '/tmp/ev_fairval')
import numpy as np
import pandas as pd
from math import erf, sqrt, log


def pa(v):
    if isinstance(v, (np.ndarray, list)):
        return np.asarray(v, float)
    return np.array(ast.literal_eval(str(v)), float)


def Ncdf(x):
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


# ---------------------------------------------------------------
# Build a per-(window,minute) table directly from the hist parquet:
# bid/ask/mid (YES), spot at minute k, strike, res_up, tau.
# This is the REAL tradeable surface; we do not use the maker fill price.
# ---------------------------------------------------------------
def build_table(asset='eth'):
    hist = pd.read_parquet(f'/tmp/ev_fairval/hist_kalshi_{asset}15m.parquet')
    rows = []
    for _, r in hist.iterrows():
        ru = int(r['res_up'])
        bid = pa(r['bid_path']); ask = pa(r['ask_path'])
        sp = pa(r['spot_path']); spv = pa(r['spot_prev'])
        if len(spv) < 1 or np.isnan(spv[-1]):
            continue
        K = float(spv[-1])
        for k in range(2, 13):
            if k >= len(bid) or k >= len(ask) or np.isnan(bid[k]) or np.isnan(ask[k]):
                continue
            b, a = float(bid[k]), float(ask[k])
            mid = (b + a) / 2.0; spread = a - b
            if not (0.0 < b < a < 1.0) or spread <= 0:
                continue
            # spot at decision time: spot path is sampled at minute boundaries; use spot[k-1]
            si = k - 1
            if si >= len(sp) or np.isnan(sp[si]) or sp[si] <= 0 or K <= 0:
                continue
            S = float(sp[si])
            rows.append(dict(ws=r['ws'], k=k, tau_min=max(15 - k, 0.5),
                             S=S, K=K, res_up=ru, yes_bid=b, yes_ask=a,
                             mid=mid, spread=spread))
    return pd.DataFrame(rows)


def fair_yes(S, K, tau_min, sig_per_min):
    vol = sig_per_min * sqrt(tau_min)
    if vol < 1e-9:
        return 1.0 if S > K else 0.0
    d2 = (log(S / K) - 0.5 * sig_per_min * sig_per_min * tau_min) / vol
    return Ncdf(d2)


def add_fair(df, sig):
    fp = np.array([fair_yes(S, K, t, sig) for S, K, t in zip(df['S'], df['K'], df['tau_min'])])
    df = df.copy(); df['fair_yes'] = fp
    df['gap_mid'] = df['mid'] - df['fair_yes']
    return df


def sharpe(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 4: return float('nan')
    s = x.std(ddof=1); return x.mean() / s if s > 1e-12 else float('nan')

def sortino(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 4: return float('nan')
    dn = x[x < 0]; d = dn.std(ddof=1) if len(dn) > 1 else float('nan')
    return x.mean() / d if d and d > 1e-12 else float('nan')

def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 4: return float('nan')
    s = x.std(ddof=1); return x.mean() / (s / sqrt(len(x))) if s > 1e-12 else float('nan')

def brier(p, y):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def calib_table(df, col, nbins=10):
    out = []; edges = np.linspace(0, 1, nbins + 1)
    for i in range(nbins):
        lo, hi = edges[i], edges[i + 1]
        m = (df[col] >= lo) & ((df[col] < hi) if i < nbins - 1 else (df[col] <= hi))
        if m.sum() == 0: continue
        out.append((f"{lo:.1f}-{hi:.1f}", int(m.sum()), df.loc[m, col].mean(),
                    df.loc[m, 'res_up'].mean(), df.loc[m, 'mid'].mean()))
    return out


# ---------------------------------------------------------------
# TAKER stat-arb with TRUE crossed prices.
#   fair_yes high vs price -> buy YES at yes_ask: edge = fair_yes - yes_ask
#   fair_yes low  vs price -> buy NO  at (1-yes_bid): edge = (1-fair_yes) - (1-yes_bid)
#                                                            = yes_bid - fair_yes
#   Fire the side whose post-cross edge > thr. Realized P&L from res_up.
# ---------------------------------------------------------------
def taker_pnl(df, thr):
    fy = df['fair_yes'].values; ba = df['yes_ask'].values; bb = df['yes_bid'].values
    ru = df['res_up'].values
    pnl = []; idx = []; sides = []
    for i in range(len(df)):
        edge_yes = fy[i] - ba[i]        # buy YES at ask
        edge_no = bb[i] - fy[i]         # buy NO  at (1 - bid)
        if edge_yes >= edge_no and edge_yes > thr:
            pnl.append(ru[i] - ba[i]); sides.append('YES'); idx.append(i)
        elif edge_no > edge_yes and edge_no > thr:
            pnl.append((1 - ru[i]) - (1 - bb[i])); sides.append('NO'); idx.append(i)
    return np.array(pnl, float), sides, idx


def summarize(pnl):
    if len(pnl) == 0: return dict(n=0)
    return dict(n=len(pnl), evc=pnl.mean() * 100, wr=(pnl > 0).mean() * 100,
                sh=sharpe(pnl), sor=sortino(pnl), t=tstat(pnl), tot=pnl.sum())


def fmt(d, *keys):
    return [d.get(k, float('nan')) for k in keys]


def main():
    print("=" * 80)
    print("ETH 15-min binary -- spot-GBM fair-value stat-arb (TRUE crossed-price taker)")
    print("=" * 80)

    df_all = build_table('eth')
    print(f"\n(window,minute) rows: {len(df_all)}  windows: {df_all['ws'].nunique()}")
    print(f"res_up rate: {df_all['res_up'].mean():.4f}")
    print(f"YES spread: mean={df_all['spread'].mean()*100:.2f}c median={df_all['spread'].median()*100:.2f}c "
          f"(half-spread = crossing cost the gap must beat)")

    ws_sorted = sorted(df_all['ws'].unique())
    cut = ws_sorted[int(len(ws_sorted) * 0.6)]
    is_m = df_all['ws'] < cut
    print(f"IS rows {is_m.sum()}  OOS rows {(~is_m).sum()}")

    # 1+2 VOL CALIBRATION (IS Brier)
    print("\n=== VOL CALIBRATION (IS Brier of fair_yes vs res_up) ===")
    best_sig, best_br = None, 1e9
    for sg in [0.0004, 0.0005, 0.0006, 0.0007, 0.00078, 0.0008, 0.0009, 0.0010, 0.0012, 0.0015]:
        d = add_fair(df_all[is_m], sg); br = brier(d['fair_yes'], d['res_up'])
        flag = ""
        if br < best_br: best_br, best_sig = br, sg; flag = " <-- best"
        print(f"  sigma/min={sg:.5f}  IS Brier={br:.4f}{flag}")
    d_is_b = add_fair(df_all[is_m], best_sig)
    print(f"  [ref] Brier(p=0.5)      = {brier(np.full(len(d_is_b),0.5), d_is_b['res_up']):.4f}")
    print(f"  [ref] Brier(KALSHI mid) = {brier(d_is_b['mid'], d_is_b['res_up']):.4f}  <-- market benchmark")
    print(f"  [ref] Brier(fair @best) = {best_br:.4f}")
    print(f"  chosen sigma/min = {best_sig:.5f}  (empirical realized ~0.00078)")

    df = add_fair(df_all, best_sig); d_oos = df[~is_m]

    print("\n=== RELIABILITY (OOS) ===")
    print(f"{'bin':<10}{'n':>7}{'mean_fair':>11}{'realized':>10}{'mean_mid':>10}")
    for b, c, mf, rz, mk in calib_table(d_oos, 'fair_yes'):
        print(f"{b:<10}{c:>7}{mf:>11.3f}{rz:>10.3f}{mk:>10.3f}")
    print(f"OOS Brier: fair={brier(d_oos['fair_yes'],d_oos['res_up']):.4f}  "
          f"mid={brier(d_oos['mid'],d_oos['res_up']):.4f}")

    print("\n=== KALSHI MID CALIBRATION (OOS) -- favorite-longshot? ===")
    print(f"{'bin':<10}{'n':>7}{'mean_mid':>10}{'realized':>10}")
    for b, c, mm, rz, _ in calib_table(d_oos, 'mid'):
        print(f"{b:<10}{c:>7}{mm:>10.3f}{rz:>10.3f}")

    print("\n=== GAP = mid - fair (OOS) ===")
    g = d_oos['gap_mid']
    print(f"  mean={g.mean():+.4f} std={g.std():.4f} "
          f"q[10,25,50,75,90]={np.round(np.quantile(g,[.1,.25,.5,.75,.9]),4)}")
    print(f"  half-spread mean={d_oos['spread'].mean()/2*100:.2f}c -> a gap must exceed this to be tradeable")
    print(f"  |gap_mid|>half_spread: {(g.abs() > d_oos['spread']/2).mean()*100:.1f}% of rows")

    # 4 TAKER SWEEP (true crossed price; thr is post-cross edge in $)
    print("\n=== STAT-ARB TAKER: post-cross edge threshold sweep (true ask/bid) ===")
    print(f"{'thr':>6}  {'IS_n':>6}{'IS_EVc':>8}{'IS_t':>7}  "
          f"{'OOS_n':>6}{'OOS_EVc':>9}{'OOS_wr':>8}{'OOS_Sh':>8}{'OOS_Sor':>8}{'OOS_t':>7}")
    df_is = df[is_m]
    for thr in [0.00, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12]:
        si = summarize(taker_pnl(df_is, thr)[0]); so = summarize(taker_pnl(d_oos, thr)[0])
        print(f"{thr:>6.2f}  {si.get('n',0):>6}{si.get('evc',float('nan')):>8.2f}{si.get('t',float('nan')):>7.2f}  "
              f"{so.get('n',0):>6}{so.get('evc',float('nan')):>9.2f}{so.get('wr',float('nan')):>8.1f}"
              f"{so.get('sh',float('nan')):>8.3f}{so.get('sor',float('nan')):>8.3f}{so.get('t',float('nan')):>7.2f}")

    # by k at thr=0.02
    print("\n=== OOS EV by minute k (thr=0.02, true crossed) ===")
    po, sides, idx = taker_pnl(d_oos, 0.02)
    if len(idx):
        sub = d_oos.iloc[idx].copy(); sub['pnl'] = po
        for k in sorted(sub['k'].unique()):
            s = sub[sub['k'] == k]
            if len(s) >= 10:
                print(f"  k={k:>2} n={len(s):>4} EV={s['pnl'].mean()*100:+.2f}c wr={(s['pnl']>0).mean()*100:.1f}%")
        print(f"  side mix: YES={sides.count('YES')} NO={sides.count('NO')}")

    # 5a VOL MIS-SPEC
    print("\n=== VOL MIS-SPEC robustness (OOS, thr=0.02, true crossed) ===")
    print(f"{'sigma/min':>10}{'OOS_n':>7}{'OOS_EVc':>9}{'OOS_t':>7}")
    for sg in [0.0005, 0.0006, 0.00078, 0.0009, 0.0011, 0.0014]:
        dd = add_fair(df_all[~is_m], sg); so = summarize(taker_pnl(dd, 0.02)[0])
        print(f"{sg:>10.5f}{so.get('n',0):>7}{so.get('evc',float('nan')):>9.2f}{so.get('t',float('nan')):>7.2f}")

    # 5b RAW FAVORITE-LONGSHOT benchmark (no GBM): fade favorites / back longshots at the crossed price.
    print("\n=== BENCHMARK: raw favorite-longshot (no GBM), true crossed price, OOS ===")
    def fl(d, m):
        ba=d['yes_ask'].values; bb=d['yes_bid'].values; ru=d['res_up'].values; md=d['mid'].values
        out=[]
        for i in range(len(d)):
            if md[i] < 0.5 - m:   out.append(ru[i] - ba[i])           # back longshot YES (buy YES at ask)
            elif md[i] > 0.5 + m: out.append((1-ru[i]) - (1-bb[i]))    # fade favorite (buy NO at 1-bid)
        return np.array(out, float)
    print(f"{'margin':>7}{'OOS_n':>7}{'OOS_EVc':>9}{'OOS_t':>7}")
    for m in [0.0, 0.05, 0.10, 0.15, 0.20]:
        s = summarize(fl(d_oos, m))
        print(f"{m:>7.2f}{s.get('n',0):>7}{s.get('evc',float('nan')):>9.2f}{s.get('t',float('nan')):>7.2f}")

    # Direct check: how much of fair vs mid gap is REAL (does fair beat mid out of sample)?
    print("\n=== Does fair beat the MID at predicting res_up, OOS? (the only source of true edge) ===")
    print(f"  OOS Brier fair={brier(d_oos['fair_yes'],d_oos['res_up']):.5f}  "
          f"mid={brier(d_oos['mid'],d_oos['res_up']):.5f}  "
          f"diff(mid-fair)={brier(d_oos['mid'],d_oos['res_up'])-brier(d_oos['fair_yes'],d_oos['res_up']):+.5f}")
    # log-loss too
    def ll(p,y):
        p=np.clip(np.asarray(p,float),1e-6,1-1e-6); y=np.asarray(y,float)
        return float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p)))
    print(f"  OOS LogLoss fair={ll(d_oos['fair_yes'],d_oos['res_up']):.5f}  "
          f"mid={ll(d_oos['mid'],d_oos['res_up']):.5f}")
    print("\nDone.")


if __name__ == '__main__':
    main()
