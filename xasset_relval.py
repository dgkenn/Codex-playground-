"""xasset_relval.py -- Cross-asset relative-value study on Kalshi 15-min crypto binaries.

Tasks:
 1. Co-movement / basket: correlation of up/down settlement across BTC/ETH/SOL/XRP; all-up/all-down vs split; common factor.
 2. Lead-lag across alts: does BTC / basket intra-window move to minute k predict a target alt's settlement
    INCREMENTALLY over the target's own binary mid? (delta-AUC)
 3. Relative mispricing: at minute k compute each alt's binary mid vs basket-implied fair P(up);
    when the alt diverges by > multi-leg cost, take the cheap side. Backtest net of fee x legs + spread x legs.
 4. Pairs: BTC->alt lead-lag at minute k where follower binary hasn't repriced; net of costs.
 5. Verdict.

Data per window (hist parquet): ws, res_up (settle dir), mid_path[15], bid/ask_path[15], spot_path[15], spot_prev[60].
All four assets share 15-min ws boundaries -> align concurrent windows by ws.

IS = first 60% of common windows (chronological), OOS = last 40%.
Fees: Kalshi taker = ceil(M*P*(1-P)*100)/100 per contract, M=0.07 std, 0.14 crypto premium (model both).
A relative-value taker trade legs into L binaries -> cost = sum_legs(fee(P_leg) + spread_leg).
"""
from __future__ import annotations
import ast, math, sys
import numpy as np
import pandas as pd
from scipy import stats

ASSETS = ['btc', 'eth', 'sol', 'xrp']
KMIN, KMAX = 2, 12  # tradeable minutes (matches window_fills)


def parse_arr(v):
    if isinstance(v, np.ndarray):
        return v.astype(float)
    if isinstance(v, list):
        return np.array(v, float)
    return np.array(ast.literal_eval(str(v)), float)


def load(asset):
    h = pd.read_parquet(f'/tmp/ev_xasset/hist_kalshi_{asset}15m.parquet')
    d = {}
    for _, r in h.iterrows():
        ws = int(r['ws'])
        mid = parse_arr(r['mid_path'])
        bid = parse_arr(r['bid_path']); ask = parse_arr(r['ask_path'])
        spot = parse_arr(r['spot_path'])
        sprev = parse_arr(r['spot_prev'])
        # strike = window open = last value of spot_prev (continues into spot_path[0])
        open_px = sprev[-1] if len(sprev) and not np.isnan(sprev[-1]) else (spot[0] if not np.isnan(spot[0]) else np.nan)
        d[ws] = dict(res=int(r['res_up']), mid=mid, bid=bid, ask=ask, spot=spot, open=open_px)
    return d


def intrawin_ret_bps(rec, k):
    """Spot return from window open to minute k, in bps (signed). +ve = up."""
    o = rec['open']; sk = rec['spot'][k]
    if not o or np.isnan(o) or np.isnan(sk) or o <= 0:
        return np.nan
    return (sk / o - 1.0) * 1e4


def taker_fee(p, M):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.ceil(M * p * (1 - p) * 100) / 100.0


def auc(score, label):
    label = np.asarray(label).astype(int)
    score = np.asarray(score, float)
    m = ~np.isnan(score)
    score, label = score[m], label[m]
    n1 = label.sum(); n0 = len(label) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    r = stats.rankdata(score)
    return (r[label == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def main():
    out = []
    def pr(*a):
        s = ' '.join(str(x) for x in a); print(s); out.append(s)

    data = {a: load(a) for a in ASSETS}
    for a in ASSETS:
        pr(f"[{a}] windows={len(data[a])}")

    # ---- common-window sets ----
    sets = {a: set(data[a].keys()) for a in ASSETS}
    all4 = sorted(set.intersection(*sets.values()))
    pr(f"\n4-way common windows: {len(all4)}")

    # ============================================================
    # TASK 1: CO-MOVEMENT / BASKET
    # ============================================================
    pr("\n" + "=" * 60)
    pr("TASK 1: CO-MOVEMENT of 15-min settlement directions")
    pr("=" * 60)
    R = {a: np.array([data[a][ws]['res'] for ws in all4]) for a in ASSETS}
    pr(f"n windows (4-way) = {len(all4)}")
    pr("Marginal P(up): " + ", ".join(f"{a}={R[a].mean():.3f}" for a in ASSETS))
    # pairwise phi (Pearson on 0/1)
    pr("\nPairwise settlement correlation (phi):")
    pr("       " + "  ".join(f"{a:>5}" for a in ASSETS))
    for a in ASSETS:
        row = []
        for b in ASSETS:
            c = np.corrcoef(R[a], R[b])[0, 1]
            row.append(f"{c:5.2f}")
        pr(f"{a:>5}  " + "  ".join(row))
    # all-up / all-down / split
    stack = np.vstack([R[a] for a in ASSETS]).T  # n x 4
    nup = stack.sum(axis=1)
    pr(f"\nBreadth (#assets up out of 4), distribution:")
    for k in range(5):
        c = (nup == k).sum()
        pr(f"  {k} up: {c:4d} ({c/len(all4)*100:5.1f}%)")
    allsame = ((nup == 0) | (nup == 4)).mean()
    pr(f"All-same-direction (0 or 4 up): {allsame*100:.1f}%  (independent baseline ~12.5%)")
    # common factor: BTC as lead. P(alt up | btc up) vs base rate
    pr("\nP(alt up | BTC up) vs P(alt up | BTC down):")
    bup = R['btc'] == 1
    for a in ['eth', 'sol', 'xrp']:
        p_g_up = R[a][bup].mean(); p_g_dn = R[a][~bup].mean()
        pr(f"  {a}: P(up|BTC up)={p_g_up:.3f}  P(up|BTC dn)={p_g_dn:.3f}  lift={p_g_up-p_g_dn:+.3f}")
    # first PC of settlement matrix (common factor strength)
    Z = stack - stack.mean(axis=0)
    cov = np.cov(Z.T)
    ev = np.linalg.eigvalsh(cov)[::-1]
    pr(f"\nEigenvalues of settlement cov: {np.round(ev,3)}; PC1 explains {ev[0]/ev.sum()*100:.0f}% of variance")

    # ============================================================
    # TASK 2: LEAD-LAG -- incremental AUC of basket/BTC move over target's own mid
    # ============================================================
    pr("\n" + "=" * 60)
    pr("TASK 2: INCREMENTAL AUC of cross-asset signal over target's own mid")
    pr("=" * 60)
    pr("For each target alt, at minute k: does (a) BTC intra-window move to k, or")
    pr("(b) basket avg alt move to k, predict target settlement BEYOND target's own binary mid?")
    pr("delta-AUC = AUC(own_mid + cross) - AUC(own_mid). Logistic combine, in-sample fit shown then OOS.")

    from sklearn.linear_model import LogisticRegression

    def build_xy(target, ws_list, k):
        """Features at minute k: target own mid, target own spot move, BTC move, basket(other alts) move."""
        rows = []; lab = []
        others = [a for a in ['eth', 'sol', 'xrp'] if a != target]
        for ws in ws_list:
            rt = data[target][ws]
            mid = rt['mid'][k]
            if np.isnan(mid):
                continue
            own_mv = intrawin_ret_bps(rt, k)
            btc_mv = intrawin_ret_bps(data['btc'][ws], k) if ws in data['btc'] else np.nan
            # basket = mean move of the other alts present
            bm = [intrawin_ret_bps(data[o][ws], k) for o in others if ws in data[o]]
            bm = [x for x in bm if not np.isnan(x)]
            basket_mv = np.mean(bm) if bm else np.nan
            if np.isnan(own_mv) or np.isnan(btc_mv) or np.isnan(basket_mv):
                continue
            rows.append([mid, own_mv, btc_mv, basket_mv])
            lab.append(rt['res'])
        return np.array(rows, float), np.array(lab, int)

    pr(f"\n{'target':<6} {'k':>3} {'n':>5} {'AUC_mid':>8} {'+own_mv':>8} {'+BTC':>8} {'+basket':>8} {'+all':>8}")
    for target in ['eth', 'sol', 'xrp']:
        # use windows where target + btc present (pairwise, larger than 4-way for sol/xrp)
        cw = sorted(sets[target] & sets['btc'])
        cut = int(len(cw) * 0.6)
        ws_oos = cw[cut:]
        for k in [5, 8, 10]:
            X, y = build_xy(target, ws_oos, k)
            if len(y) < 40 or y.mean() in (0, 1):
                pr(f"{target:<6} {k:>3} {len(y):>5}  (insufficient)")
                continue
            # AUC of raw mid
            a_mid = auc(X[:, 0], y)
            def fit_auc(cols):
                Xs = X[:, cols]
                lr = LogisticRegression(max_iter=500)
                lr.fit(Xs, y)
                return auc(lr.predict_proba(Xs)[:, 1], y)
            a_own = fit_auc([0, 1])
            a_btc = fit_auc([0, 2])
            a_bsk = fit_auc([0, 3])
            a_all = fit_auc([0, 1, 2, 3])
            pr(f"{target:<6} {k:>3} {len(y):>5} {a_mid:8.3f} {a_own:8.3f} {a_btc:8.3f} {a_bsk:8.3f} {a_all:8.3f}")

    # ============================================================
    # TASK 3: RELATIVE MISPRICING strategy
    # ============================================================
    pr("\n" + "=" * 60)
    pr("TASK 3: RELATIVE MISPRICING backtest (basket-implied fair vs alt binary mid)")
    pr("=" * 60)
    pr("At minute k, basket-implied direction prob for an alt is estimated from concurrent")
    pr("co-movement: fair_up = logistic of (own spot move, BTC move, basket move) fit on IS.")
    pr("If alt binary mid diverges from fair by > threshold (and > est. round-trip cost), TAKE cheap side.")
    pr("Settle to res_up. Cost = taker_fee(entry_price) + spread (cross to take). Single-leg directional take.")

    def run_relval(target, M, thr, k_set=(4, 6, 8, 10), neutral=False):
        others = [a for a in ['eth', 'sol', 'xrp'] if a != target]
        cw = sorted(sets[target] & sets['btc'])
        cut = int(len(cw) * 0.6)
        ws_is, ws_oos = cw[:cut], cw[cut:]
        # fit fair model on IS pooled over k
        def collect(ws_list, fit=False):
            feats = []; labs = []; meta = []
            for ws in ws_list:
                rt = data[target][ws]
                for k in k_set:
                    mid = rt['mid'][k]; bid = rt['bid'][k]; ask = rt['ask'][k]
                    if np.isnan(mid) or np.isnan(bid) or np.isnan(ask):
                        continue
                    own_mv = intrawin_ret_bps(rt, k)
                    btc_mv = intrawin_ret_bps(data['btc'][ws], k) if ws in data['btc'] else np.nan
                    bm = [intrawin_ret_bps(data[o][ws], k) for o in others if ws in data[o]]
                    bm = [x for x in bm if not np.isnan(x)]
                    basket_mv = np.mean(bm) if bm else np.nan
                    if np.isnan(own_mv) or np.isnan(btc_mv) or np.isnan(basket_mv):
                        continue
                    feats.append([own_mv, btc_mv, basket_mv])
                    labs.append(rt['res'])
                    meta.append((ws, k, mid, bid, ask, rt['res']))
            return np.array(feats, float), np.array(labs, int), meta
        Xi, yi, _ = collect(ws_is)
        if len(yi) < 50 or yi.mean() in (0, 1):
            return None
        lr = LogisticRegression(max_iter=500)
        lr.fit(Xi, yi)

        def backtest(ws_list):
            X, y, meta = collect(ws_list)
            if len(y) == 0:
                return np.array([]), 0
            fair = lr.predict_proba(X)[:, 1]
            pnls = []
            for i, (ws, k, mid, bid, ask, res) in enumerate(meta):
                f = fair[i]
                edge = f - mid  # >0 => fair says up more than priced => buy YES
                if abs(edge) < thr:
                    continue
                if edge > 0:
                    # buy YES at ask
                    entry = ask
                    fee = taker_fee(entry, M)
                    pnl = (res - entry) - fee
                else:
                    # buy NO at (1-bid)  => sell YES at bid
                    entry = 1 - bid
                    fee = taker_fee(entry, M)
                    pnl = ((1 - res) - entry) - fee
                pnls.append(pnl)
            return np.array(pnls, float), len(meta)
        p_is, n_is = backtest(ws_is)
        p_oos, n_oos = backtest(ws_oos)
        return dict(p_is=p_is, p_oos=p_oos, n_is=n_is, n_oos=n_oos)

    for M, mlbl in [(0.07, 'std'), (0.14, 'crypto')]:
        pr(f"\n--- Fee M={M} ({mlbl}) ---")
        pr(f"{'target':<6} {'thr':>5} {'IS n':>6} {'IS EV/c':>8} {'OOS n':>6} {'OOS EV/c':>9} {'OOS Sh':>7} {'win%':>6} {'t':>6}")
        for target in ['eth', 'sol', 'xrp']:
            for thr in [0.05, 0.10, 0.15]:
                r = run_relval(target, M, thr)
                if r is None:
                    continue
                pi, po = r['p_is'], r['p_oos']
                if len(po) < 5:
                    pr(f"{target:<6} {thr:>5.2f} {len(pi):>6} {'-':>8} {len(po):>6}  (few OOS trades)")
                    continue
                ev_is = pi.mean() * 100 if len(pi) else float('nan')
                ev = po.mean() * 100
                sh = po.mean() / po.std(ddof=1) if po.std(ddof=1) > 1e-9 else float('nan')
                t = stats.ttest_1samp(po, 0).statistic if len(po) > 2 else float('nan')
                wr = (po > 0).mean() * 100
                pr(f"{target:<6} {thr:>5.2f} {len(pi):>6} {ev_is:>+7.2f}c {len(po):>6} {ev:>+8.2f}c {sh:>+7.3f} {wr:>5.1f}% {t:>+6.2f}")

    # ============================================================
    # TASK 4: PAIRS lead-lag (BTC move -> alt binary not yet repriced)
    # ============================================================
    pr("\n" + "=" * 60)
    pr("TASK 4: PAIRS -- BTC intra-window move at k predicts alt settlement; is alt binary repriced?")
    pr("=" * 60)
    pr("Signal: at minute k BTC moved up (>thr bps) since open. If alt binary mid still < 0.5+margin,")
    pr("the follower hasn't repriced -> buy alt YES (taker). Symmetric for down. Net of fee+spread.")

    def run_pair(target, M, btc_thr_bps, k_set=(4, 6, 8, 10)):
        cw = sorted(sets[target] & sets['btc'])
        cut = int(len(cw) * 0.6)
        ws_is, ws_oos = cw[:cut], cw[cut:]
        def bt(ws_list):
            pnls = []; n_eval = 0
            for ws in ws_list:
                rt = data[target][ws]; rb = data['btc'][ws]
                for k in k_set:
                    mid = rt['mid'][k]; bid = rt['bid'][k]; ask = rt['ask'][k]
                    if np.isnan(mid) or np.isnan(bid) or np.isnan(ask):
                        continue
                    btc_mv = intrawin_ret_bps(rb, k)
                    own_mv = intrawin_ret_bps(rt, k)
                    if np.isnan(btc_mv) or np.isnan(own_mv):
                        continue
                    n_eval += 1
                    res = rt['res']
                    # BTC up strongly but alt own move lagging (alt moved less) and binary still cheap
                    if btc_mv > btc_thr_bps and own_mv < btc_mv * 0.5 and mid < 0.55:
                        entry = ask; fee = taker_fee(entry, M)
                        pnls.append((res - entry) - fee)
                    elif btc_mv < -btc_thr_bps and own_mv > btc_mv * 0.5 and mid > 0.45:
                        entry = 1 - bid; fee = taker_fee(entry, M)
                        pnls.append(((1 - res) - entry) - fee)
            return np.array(pnls, float), n_eval
        return bt(ws_is), bt(ws_oos)

    M = 0.14
    pr(f"\n--- Fee M={M} (crypto) ---")
    pr(f"{'pair':<10} {'btc_thr':>8} {'IS n':>6} {'IS EV':>7} {'OOS n':>6} {'OOS EV':>8} {'OOS Sh':>7} {'win%':>6} {'t':>6}")
    for target in ['eth', 'sol', 'xrp']:
        for thr in [10, 20, 40]:
            (pi, _), (po, _) = run_pair(target, M, thr)
            if len(po) < 5:
                pr(f"{'BTC->'+target:<10} {thr:>8} {len(pi):>6} {'-':>7} {len(po):>6}  (few)")
                continue
            ev_is = pi.mean() * 100 if len(pi) else float('nan')
            ev = po.mean() * 100
            sh = po.mean() / po.std(ddof=1) if po.std(ddof=1) > 1e-9 else float('nan')
            t = stats.ttest_1samp(po, 0).statistic if len(po) > 2 else float('nan')
            wr = (po > 0).mean() * 100
            pr(f"{'BTC->'+target:<10} {thr:>8} {len(pi):>6} {ev_is:>+6.2f}c {len(po):>6} {ev:>+7.2f}c {sh:>+7.3f} {wr:>5.1f}% {t:>+6.2f}")

    with open('/tmp/ev_xasset/_xasset_out.txt', 'w') as fh:
        fh.write('\n'.join(out))
    pr("\n[done] raw output saved to _xasset_out.txt")


if __name__ == '__main__':
    main()
