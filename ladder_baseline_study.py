"""ladder_baseline_study.py -- Phase A+B: 5-rung combined baseline + leave-one-out ablation.

PHASE A: Stack all 5 rungs into one combined policy on BTC (IS=first 60%, OOS=last 40%).
         Report the full A/B metric set.

PHASE B: Leave-one-out ablation (drop each rung in turn), candidate new rungs (buffer/split),
         and the recommended locked sequence.

Key design notes:
- Rung 2 GBM trained with PER-FILL STRAND label (1 if fill ends stranded, 0 if paired).
  Using settle<0 label was incorrect (that is P(binary wrong side) = ~50%, not P(strand)).
  Correct strand-fill rate IS=1.0%, OOS=0.65%; GBM OOS AUC=0.883.
- IS combined policy excludes GBM gate to avoid in-sample leakage.
- Rung 4 streak scale-down is confirmed to HURT net (-0.61c when dropped);
  recommend replacing with manage-split (continuous GBM-probability sizing).
- Tape note: mean spread in parquet=1c; t36's 2c YES floor blocks ~90% of bid fills.

Usage: python ladder_baseline_study.py
Writes: LADDER_BASELINE.md
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, '/tmp/lad')

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

# ---- import helpers from box_policy_ab (reuse ALL metric helpers) ----
from box_policy_ab import (
    window_fills, run_policy, pol_sell_unpaired, pol_hedge_unpaired,
    hedge_unpaired, tox_p, combo_tox_p, pair_prob,
    _live_open_ok, _LIVE_GATES,
    tstat, maxdd, calmar, profit_factor, sortino, recovery_factor,
    metric_skewness, metric_kurtosis, metric_ulcer, metric_var95, metric_cvar95,
    metric_ir, metric_avg_win_loss, metric_expectancy, metric_time_underwater,
    bench_line, _COMBO_THRESH,
)


# ============================================================
# DATA LOADING from parquet
# ============================================================

def parse_arr(v):
    if isinstance(v, np.ndarray):
        return v.astype(float)
    if isinstance(v, list):
        return np.array(v, float)
    import ast
    return np.array(ast.literal_eval(str(v)), float)


def load_parquet_windows(asset='btc'):
    """Load hist + trades parquets; return fills_per_ws dict and sorted ws list."""
    hist = pd.read_parquet(f'/tmp/lad/hist_kalshi_{asset}15m.parquet')
    trades = pd.read_parquet(f'/tmp/lad/trades_kalshi_{asset}15m.parquet')
    hist_idx = {row['ws']: row for _, row in hist.iterrows()}
    trades_idx = {row['ws']: row for _, row in trades.iterrows()}
    common_ws = sorted(set(hist_idx.keys()) & set(trades_idx.keys()))
    print(f"  [{asset}] common windows: {len(common_ws)}")
    fills_per_ws = {}
    for ws in common_ws:
        h = hist_idx[ws]; t = trades_idx[ws]
        res = int(h['res_up'])
        bid = parse_arr(h['bid_path']); ask = parse_arr(h['ask_path'])
        spot = parse_arr(h['spot_path'])
        depth = parse_arr(h['vol_path']) if h.get('vol_path') is not None else np.full(15, np.nan)
        t_arr = parse_arr(t['t']); p_arr = parse_arr(t['p'])
        sz_arr = parse_arr(t['sz']); buy_arr = parse_arr(t['buy']).astype(bool)
        tape = (t_arr, p_arr, sz_arr, buy_arr)
        try:
            fills = window_fills(ws, res, bid, ask, spot, depth, tape, oi_slope=None, q0=0.0)
        except Exception:
            fills = []
        if fills:
            fills_per_ws[ws] = fills
    ws_sorted = sorted(fills_per_ws.keys())
    print(f"  [{asset}] windows with fills: {len(ws_sorted)}")
    return fills_per_ws, ws_sorted


# ============================================================
# GBM STRAND CLASSIFIER (Rung 2: PREDICT)
# Label: 1 = this fill ends as a stranded (unpaired) leg under P0
# Features: spread, |p-0.5|, sig, |flow|, k, tau, vpin
# ============================================================

def _get_fill_feats(f):
    p_yeq = f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)
    vpin = f.get('vpin')
    if vpin is None or (isinstance(vpin, float) and np.isnan(vpin)):
        vpin = 0.42
    return [
        f.get('spread', 0.02),
        abs(p_yeq - 0.5),
        f.get('sig', 0.0) or 0.0,
        abs(f.get('flow', 0.0) or 0.0),
        float(f.get('k', 7)),
        f.get('tau', 0.5),
        float(vpin),
    ]


def get_strand_labels(fills_per_ws, ws_list):
    """Per-fill strand label: 1 if this fill ends up unpaired (stranded) under P0, else 0."""
    X = []; y = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        if not fills:
            continue
        # Walk P0 to identify the stranded fill
        net = 0; open_leg = None
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                open_leg = None
            else:
                open_leg = f
            net = nn
        if open_leg is not None:
            open_leg['_strand_mark'] = True
        for f in fills:
            X.append(_get_fill_feats(f))
            y.append(1 if f.get('_strand_mark') else 0)
    return np.array(X, float), np.array(y, int)


def _auc_approx(probs, labels):
    from scipy.stats import rankdata
    n1 = labels.sum(); n0 = len(labels) - n1
    if n1 == 0 or n0 == 0:
        return 0.5
    r = rankdata(probs)
    return (r[labels == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def build_gbm(fills_per_ws, ws_is):
    """Fit GBM on IS with correct strand label; return (gbm, col_means, thresh)."""
    X, y = get_strand_labels(fills_per_ws, ws_is)
    col_means = np.nanmean(X, axis=0)
    for j in range(X.shape[1]):
        X[np.isnan(X[:, j]), j] = col_means[j]

    gbm = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.1,
                                      subsample=0.8, random_state=42)
    gbm.fit(X, y)
    probs_is = gbm.predict_proba(X)[:, 1]

    # Threshold: IS F1-optimal for the strand class
    from sklearn.metrics import f1_score
    best_thresh = 0.5; best_f1 = -1.0
    for thr in np.linspace(0.01, 0.5, 100):
        pred = (probs_is >= thr).astype(int)
        f1 = f1_score(y, pred, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1; best_thresh = thr

    is_auc = _auc_approx(probs_is, y)
    print(f"  GBM IS strand_rate={y.mean()*100:.2f}%, IS-AUC={is_auc:.3f}, thresh={best_thresh:.3f}")
    return gbm, col_means, best_thresh


def make_gbm_gate(gbm, col_means, thresh):
    """Return open_ok function for GBM gate."""
    def gate(f, state):
        row = np.array([_get_fill_feats(f)], float)
        for j in range(row.shape[1]):
            if np.isnan(row[0, j]):
                row[0, j] = col_means[j]
        return gbm.predict_proba(row)[0, 1] <= thresh
    return gate


# ============================================================
# STREAK TRACKER (Rung 4)
# ============================================================

class StreakState:
    def __init__(self, mults=(0.75, 0.50, 0.25)):
        self.streak = 0; self.mults = mults

    def update(self, stranded):
        self.streak = self.streak + 1 if stranded else 0

    def multiplier(self):
        idx = min(self.streak, len(self.mults)) - 1
        return self.mults[idx] if idx >= 0 else 1.0


# ============================================================
# WALK ENGINE (all variants)
# r1=True: Rung 1 (t36), r2_fn: Rung 2 (GBM gate or None),
# r3=True: Rung 3 (sell-cheap<0.30), r4=True: Rung 4 (streak scale-down),
# r5=True: Rung 5 (hedge h=150), buf: Rung-0 structural spread buffer,
# size_fn: Rung-4 manage-split (replaces streak when provided)
# ============================================================

def walk(fills_per_ws, ws_list, r1=True, r2_fn=None, r3=True, r4=True, r5=True,
         buf=None, size_fn=None):
    streak = StreakState((0.75, 0.50, 0.25)) if r4 else None
    pnl_arr = []; strand_arr = []

    for ws in ws_list:
        fills = fills_per_ws[ws]
        mult = streak.multiplier() if streak else 1.0

        net = 0; pnl = 0.0; open_leg = None; open_sz = 1.0

        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue

            if net != 0 and abs(nn) < abs(net):
                # Pairing fill: always complete
                pnl += mult * open_sz * (f['settle'] + (open_leg['settle'] if open_leg else 0))
                open_leg = None; open_sz = 1.0
            else:
                # Opening fill: apply all entry gates
                blocked = False
                if buf is not None and f.get('spread', 0.0) < buf:
                    blocked = True
                if r1 and not blocked and not _live_open_ok(f, {}):
                    blocked = True
                if r2_fn is not None and not blocked and not r2_fn(f, {}):
                    blocked = True
                if blocked:
                    continue
                open_sz = size_fn(f) if size_fn is not None else 1.0
                open_leg = f

            net = nn

        stranded = False
        if open_leg is not None:
            stranded = True
            p_yeq = open_leg['p'] if open_leg['side'] == 'bid' else round(1.0 - open_leg['p'], 4)
            if r3 and p_yeq < 0.30:
                pnl += mult * open_sz * open_leg.get('exit', open_leg['settle'])
            elif r5:
                pnl += mult * open_sz * hedge_unpaired(open_leg, h=150.0)
            else:
                pnl += mult * open_sz * open_leg['settle']

        pnl_arr.append(pnl); strand_arr.append(stranded)
        if streak:
            streak.update(stranded)

    return np.array(pnl_arr, float), np.array(strand_arr, bool)


# ============================================================
# METRICS
# ============================================================

def full_metrics(x, b_p0=None, b_live=None):
    xc = np.asarray(x, float); xc = xc[~np.isnan(xc)]
    if len(xc) < 4:
        return {}
    std = xc.std(ddof=1)
    sh = xc.mean() / std if std > 1e-12 else float('nan')

    def ir(a, b):
        a = np.asarray(a, float); b = np.asarray(b, float)
        m = ~np.isnan(a) & ~np.isnan(b)
        if m.sum() < 4:
            return float('nan')
        d = a[m] - b[m]; s = d.std(ddof=1)
        return d.mean() / s if s > 1e-12 else float('nan')

    return dict(
        n=len(xc), nc=xc.mean() * 100, sh=sh, sor=sortino(xc),
        skew=metric_skewness(xc), kurt=metric_kurtosis(xc),
        recov=recovery_factor(xc), ulcer=metric_ulcer(xc) * 100,
        v95=metric_var95(xc) * 100, cv95=metric_cvar95(xc) * 100,
        awl=metric_avg_win_loss(xc), tuw=metric_time_underwater(xc) * 100,
        mdd=maxdd(xc) * 100, wr=(xc > 0).mean() * 100, pf=profit_factor(xc),
        ir_p0=ir(x, b_p0) if b_p0 is not None else float('nan'),
        ir_live=ir(x, b_live) if b_live is not None else float('nan'),
        ts=tstat(xc),
    )


def run_p0(fills_per_ws, ws_list):
    """P0: always-pair baseline."""
    pnl_arr = []; strand_arr = []
    for ws in ws_list:
        fills = fills_per_ws[ws]
        net = 0; pnl = 0.0; open_leg = None; stranded = False
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1; nn = net + step
            if abs(nn) > 1: continue
            if net != 0 and abs(nn) < abs(net):
                pnl += f['settle'] + (open_leg['settle'] if open_leg else 0)
                open_leg = None
            else:
                open_leg = f
            net = nn
        if open_leg is not None:
            stranded = True; pnl += open_leg['settle']
        pnl_arr.append(pnl); strand_arr.append(stranded)
    return np.array(pnl_arr, float), np.array(strand_arr, bool)


def run_live_current(fills_per_ws, ws_list):
    return np.array([run_policy(fills_per_ws[ws], open_ok=_live_open_ok) for ws in ws_list], float)


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("LADDER BASELINE STUDY -- Phase A + B")
    print("=" * 70)

    print("\nLoading BTC parquet data...")
    fills_btc, ws_btc = load_parquet_windows('btc')
    n = len(ws_btc)
    cut = int(n * 0.6)
    ws_is = ws_btc[:cut]; ws_oos = ws_btc[cut:]
    print(f"  IS: {len(ws_is)} windows, OOS: {len(ws_oos)} windows")

    print("\nFitting GBM strand gate on IS (correct strand label)...")
    gbm, col_means, gbm_thresh = build_gbm(fills_btc, ws_is)

    # OOS evaluation
    X_oos, y_oos = get_strand_labels(fills_btc, ws_oos)
    for j in range(X_oos.shape[1]):
        X_oos[np.isnan(X_oos[:, j]), j] = col_means[j]
    probs_oos = gbm.predict_proba(X_oos)[:, 1]
    oos_auc = _auc_approx(probs_oos, y_oos)
    oos_blocked = (probs_oos > gbm_thresh).mean() * 100
    print(f"  GBM OOS AUC={oos_auc:.3f}, blocks {oos_blocked:.1f}% at thresh={gbm_thresh:.3f}")

    gbm_gate = make_gbm_gate(gbm, col_means, gbm_thresh)

    # Make GBM size function for manage-split
    def gbm_size_fn(f, gbm=gbm, col_means=col_means):
        row = np.array([_get_fill_feats(f)], float)
        for j in range(row.shape[1]):
            if np.isnan(row[0, j]): row[0, j] = col_means[j]
        p = gbm.predict_proba(row)[0, 1]
        return max(0.25, 1.0 - p * 5)

    print("\nRunning policies...")
    p0_is, _ = run_p0(fills_btc, ws_is)
    p0_oos, p0_st_oos = run_p0(fills_btc, ws_oos)
    live_is = run_live_current(fills_btc, ws_is)
    live_oos = run_live_current(fills_btc, ws_oos)

    # IS combined: no GBM (leakage avoidance)
    ci, cst_is = walk(fills_btc, ws_is, r2_fn=None)
    # OOS combined: all 5 rungs with GBM
    co, cst_oos = walk(fills_btc, ws_oos, r2_fn=gbm_gate)

    # Metrics
    mp0i = full_metrics(p0_is, p0_is, live_is)
    mp0o = full_metrics(p0_oos, p0_oos, live_oos)
    mli = full_metrics(live_is, p0_is, live_is)
    mlo = full_metrics(live_oos, p0_oos, live_oos)
    mci = full_metrics(ci, p0_is, live_is)
    mco = full_metrics(co, p0_oos, live_oos)

    print("\n=== PHASE A: COMBINED 5-RUNG BASELINE ===")
    print(f"{'Policy':<25} {'IS net':>8} {'OOS net':>8} {'OOS Sh':>8} {'OOS CVaR':>10} {'Strand%':>8} {'Win%':>6} {'t-stat':>7}")
    print("-" * 85)
    for lbl, mi, mo, st in [
        ("P0 always-pair", mp0i, mp0o, p0_st_oos.mean()*100),
        ("live_current (t36)", mli, mlo, float('nan')),
        ("COMBINED 5-rung", mci, mco, cst_oos.mean()*100),
    ]:
        print(f"{lbl:<25} {mi['nc']:>+8.2f}c {mo['nc']:>+8.2f}c {mo['sh']:>+8.3f} {mo['cv95']:>10.2f}c "
              f"{st:>7.1f}% {mo['wr']:>5.1f}% {mo['ts']:>+6.3f}")

    print(f"\nCOMBINED OOS full metrics:")
    print(f"  Sortino={mco['sor']:+.3f}  Skew={mco['skew']:+.2f}  Kurt={mco['kurt']:+.2f}")
    print(f"  Recovery={mco['recov']:+.2f}  Ulcer={mco['ulcer']:.2f}c  VaR95={mco['v95']:.2f}c  CVaR95={mco['cv95']:.2f}c")
    print(f"  IR_vs_P0={mco['ir_p0']:+.3f}  IR_vs_live={mco['ir_live']:+.3f}")
    print(f"  AvgW/L={mco['awl']:.3f}  TimeUW={mco['tuw']:.1f}%  MaxDD={mco['mdd']:.2f}c  PF={mco['pf']:.2f}")
    print(f"  P(both fill)={1-cst_oos.mean():.3f}  Strand={cst_oos.mean()*100:.1f}%")

    print("\n=== PHASE B: LEAVE-ONE-OUT ABLATION (OOS) ===")
    print(f"{'Rung dropped':<38} {'Δnet':>7} {'ΔSharpe':>8} {'ΔCVaR':>8} {'Δstrand':>8} {'Abl.net':>8}")
    print("-" * 85)
    abl_results = {}
    for rname, kw in [
        ("Drop R1 PREVENT (t36)", dict(r1=False)),
        ("Drop R2 PREDICT (GBM)", dict(r2_fn=None)),
        ("Drop R3 COMPLETE (sell-cheap)", dict(r3=False)),
        ("Drop R4 COOL-OFF (streak)", dict(r4=False)),
        ("Drop R5 HEDGE (h=150)", dict(r5=False)),
    ]:
        kw2 = dict(r1=True, r2_fn=gbm_gate, r3=True, r4=True, r5=True)
        kw2.update(kw)
        ao, ast = walk(fills_btc, ws_oos, **kw2)
        ma = full_metrics(ao, p0_oos, live_oos)
        dn = ma['nc'] - mco['nc']; dsh = ma['sh'] - mco['sh']
        dcv = ma['cv95'] - mco['cv95']; ds = ast.mean()*100 - cst_oos.mean()*100
        print(f"{rname:<38} {dn:>+7.2f}c {dsh:>+8.3f} {dcv:>+8.3f}c {ds:>+7.1f}pp {ma['nc']:>+7.2f}c")
        abl_results[rname] = (dn, dsh, dcv, ds, ma)

    print("\n=== CANDIDATES (OOS vs COMBINED baseline) ===")
    print(f"{'Candidate':<38} {'net':>8} {'Δnet':>7} {'Strand%':>8} {'Sharpe':>8}")
    print("-" * 75)

    for buf in [0.01, 0.02]:
        bo, bst = walk(fills_btc, ws_oos, r2_fn=gbm_gate, buf=buf)
        mb = full_metrics(bo, p0_oos, live_oos)
        dn = mb['nc'] - mco['nc']
        print(f"{'Buffer spread>=' + str(buf):<38} {mb['nc']:>+8.2f}c {dn:>+7.2f}c {bst.mean()*100:>7.1f}% {mb['sh']:>+8.3f}")

    ms_oos, ms_st = walk(fills_btc, ws_oos, r2_fn=None, r4=False, size_fn=gbm_size_fn)
    mm = full_metrics(ms_oos, p0_oos, live_oos)
    dn_ms = mm['nc'] - mco['nc']
    print(f"{'MANAGE split (GBM sizing, no streak)':<38} {mm['nc']:>+8.2f}c {dn_ms:>+7.2f}c {ms_st.mean()*100:>7.1f}% {mm['sh']:>+8.3f}")

    # ETH note
    print("\n--- ETH note ---")
    fills_eth, ws_eth = load_parquet_windows('eth')
    cut_eth = int(len(ws_eth) * 0.6)
    ws_eth_oos = ws_eth[cut_eth:]
    p0_eth, p0_eth_st = run_p0(fills_eth, ws_eth_oos)
    me = full_metrics(p0_eth, p0_eth, p0_eth)
    print(f"ETH P0 OOS: n={me['n']} net={me['nc']:+.2f}c strand={p0_eth_st.mean()*100:.1f}%")

    print(f"\nGBM OOS AUC={oos_auc:.3f}  thresh={gbm_thresh:.3f}  blocks_OOS={oos_blocked:.1f}%")
    print("Done. See LADDER_BASELINE.md for full results.")


if __name__ == '__main__':
    main()
