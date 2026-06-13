"""eth_leadlag_study.py -- BTC->ETH lead-lag directional strategy on Kalshi ETH 15-min binary.

GOAL: Does BTC's intra-window move (window open -> minute k) predict ETH's 15-min binary
settlement? If so, can we TAKE the ETH YES/NO with positive net EV after crossing the
(thin) ETH binary spread (Kalshi crypto15m FEE=0 -> taker pays only half-spread each side)?

Data: hist_kalshi_{btc,eth}15m.parquet -- per-window:
  ws (15-min boundary, shared grid), res_up (binary settle: 1=ETH up), spot_path[15] (spot/min),
  bid_path[15]/ask_path[15] (ETH binary YES quotes/min). BTC and ETH windows aligned by ws.

IS = first 60% of windows, OOS = last 40% (chronological).

Outputs metrics tables to stdout; ETH_LEADLAG.md is written from these numbers.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import rankdata


def load(asset):
    h = pd.read_parquet(f'/tmp/ev_leadlag/hist_kalshi_{asset}15m.parquet')
    return h


def arr(x):
    return np.array(x, float)


def auc(score, label):
    label = np.asarray(label, int)
    n1 = label.sum(); n0 = len(label) - n1
    if n1 == 0 or n0 == 0:
        return 0.5
    r = rankdata(score)
    return (r[label == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def ret_to_k(sp, k):
    """Spot return (bps) from window open (minute 0) to minute k, using last valid<=k."""
    s0 = sp[0]
    sk = sp[k]
    if np.isnan(s0) or np.isnan(sk) or s0 <= 0:
        return np.nan
    return (sk / s0 - 1.0) * 1e4


def build_aligned():
    """Return DataFrame of windows present in BOTH btc & eth, with aligned spot paths + ETH quotes."""
    hb = load('btc'); he = load('eth')
    bidx = {r['ws']: r for _, r in hb.iterrows()}
    eidx = {r['ws']: r for _, r in he.iterrows()}
    common = sorted(set(bidx) & set(eidx))
    rows = []
    for ws in common:
        b = bidx[ws]; e = eidx[ws]
        bsp = arr(b['spot_path']); esp = arr(e['spot_path'])
        if len(bsp) < 15 or len(esp) < 15:
            continue
        rows.append(dict(
            ws=ws,
            res_up=int(e['res_up']),
            btc_sp=bsp, eth_sp=esp,
            eth_bid=arr(e['bid_path']), eth_ask=arr(e['ask_path']),
        ))
    df = pd.DataFrame(rows).sort_values('ws').reset_index(drop=True)
    return df


def main():
    df = build_aligned()
    n = len(df)
    cut = int(n * 0.6)
    print("=" * 78)
    print("BTC->ETH LEAD-LAG :: ETH 15-min Kalshi binary")
    print("=" * 78)
    print(f"Aligned windows (BTC&ETH common): {n}  | IS={cut} OOS={n-cut}")
    print(f"Base rate ETH res_up: {df['res_up'].mean():.3f}")

    is_df = df.iloc[:cut].reset_index(drop=True)
    oos_df = df.iloc[cut:].reset_index(drop=True)

    # ---------- TASK 1: LEAD-LAG PREDICTIVE POWER ----------
    print("\n" + "=" * 78)
    print("TASK 1 :: LEAD-LAG PREDICTIVENESS (AUC of BTC move-to-k vs ETH settle)")
    print("=" * 78)
    print(f"{'k':>3} {'BTC->ETH AUC':>13} {'ETHself AUC':>12} {'BTC corr':>9} {'ETHself corr':>13} "
          f"{'BTC sign-hit':>13} {'n':>5}")
    print("-" * 78)
    leadlag = {}
    for k in range(1, 14):
        # OOS evaluation of raw signal (no fit needed -- raw sign / magnitude)
        sub = oos_df
        btc_r = np.array([ret_to_k(r, k) for r in sub['btc_sp']])
        eth_r = np.array([ret_to_k(r, k) for r in sub['eth_sp']])
        lab = sub['res_up'].values
        m = ~np.isnan(btc_r) & ~np.isnan(eth_r)
        btc_r, eth_r, lab2 = btc_r[m], eth_r[m], lab[m]
        a_btc = auc(btc_r, lab2)
        a_eth = auc(eth_r, lab2)
        c_btc = np.corrcoef(btc_r, lab2)[0, 1]
        c_eth = np.corrcoef(eth_r, lab2)[0, 1]
        # sign hit-rate: when btc_r != 0, does sign(btc_r) == direction?
        nz = np.abs(btc_r) > 1e-9
        hit = (np.sign(btc_r[nz]) == np.where(lab2[nz] == 1, 1, -1)).mean() if nz.sum() else np.nan
        leadlag[k] = dict(a_btc=a_btc, a_eth=a_eth, c_btc=c_btc, c_eth=c_eth, hit=hit, n=int(m.sum()))
        print(f"{k:>3} {a_btc:>13.3f} {a_eth:>12.3f} {c_btc:>+9.3f} {c_eth:>+13.3f} "
              f"{(hit*100 if not np.isnan(hit) else float('nan')):>12.1f}% {int(m.sum()):>5}")

    # Incremental BTC over ETH-self: does BTC add AUC beyond ETH's own move? Fit logit IS, eval OOS.
    print("\nIncremental value of BTC beyond ETH-self momentum (logistic, fit IS / eval OOS):")
    print(f"{'k':>3} {'ETHself OOS-AUC':>16} {'ETH+BTC OOS-AUC':>16} {'ΔAUC':>8} {'BTC beta t':>11}")
    print("-" * 70)
    from sklearn.linear_model import LogisticRegression
    incr = {}
    for k in range(1, 14):
        def feats(d):
            b = np.array([ret_to_k(r, k) for r in d['btc_sp']])
            e = np.array([ret_to_k(r, k) for r in d['eth_sp']])
            return b, e, d['res_up'].values
        bi, ei, yi = feats(is_df)
        bo, eo, yo = feats(oos_df)
        mi = ~np.isnan(bi) & ~np.isnan(ei)
        mo = ~np.isnan(bo) & ~np.isnan(eo)
        # standardize on IS
        emu, esd = np.nanmean(ei[mi]), np.nanstd(ei[mi]) + 1e-9
        bmu, bsd = np.nanmean(bi[mi]), np.nanstd(bi[mi]) + 1e-9
        Xi_e = ((ei[mi] - emu) / esd).reshape(-1, 1)
        Xo_e = ((eo[mo] - emu) / esd).reshape(-1, 1)
        Xi_be = np.column_stack([(ei[mi] - emu) / esd, (bi[mi] - bmu) / bsd])
        Xo_be = np.column_stack([(eo[mo] - emu) / esd, (bo[mo] - bmu) / bsd])
        try:
            m1 = LogisticRegression().fit(Xi_e, yi[mi])
            m2 = LogisticRegression().fit(Xi_be, yi[mi])
            a1 = auc(m1.predict_proba(Xo_e)[:, 1], yo[mo])
            a2 = auc(m2.predict_proba(Xo_be)[:, 1], yo[mo])
            btc_beta = m2.coef_[0, 1]
            # crude t via bootstrap of beta sign stability omitted; report beta
            incr[k] = dict(a1=a1, a2=a2, beta=btc_beta)
            print(f"{k:>3} {a1:>16.3f} {a2:>16.3f} {a2-a1:>+8.3f} {btc_beta:>+11.3f}")
        except Exception as ex:
            print(f"{k:>3} err {ex}")

    # ---------- TASK 2 + 3: DIRECTIONAL MODEL + TAKER STRATEGY ----------
    print("\n" + "=" * 78)
    print("TASK 2+3 :: DIRECTIONAL MODEL (ETH+BTC logit) + TAKER STRATEGY SWEEP")
    print("=" * 78)
    print("At minute k: model P(up). ETH binary YES mid=(bid+ask)/2 at k. half-spread cost.")
    print("TAKE YES if P(up)-yes_ask_price > thr ; TAKE NO if (1-P(up))-no_ask_price > thr.")
    print("Net PnL per trade ($/contract, stake=1): YES win=+(1-ask) loss=-ask ; settle by res_up.")
    print()

    def model_probs(k):
        """Fit ETH+BTC logit on IS, return (P_up_oos, oos_df_mask, fitted model info)."""
        def feats(d):
            b = np.array([ret_to_k(r, k) for r in d['btc_sp']])
            e = np.array([ret_to_k(r, k) for r in d['eth_sp']])
            return b, e, d['res_up'].values
        bi, ei, yi = feats(is_df); bo, eo, yo = feats(oos_df)
        mi = ~np.isnan(bi) & ~np.isnan(ei); mo = ~np.isnan(bo) & ~np.isnan(eo)
        emu, esd = np.nanmean(ei[mi]), np.nanstd(ei[mi]) + 1e-9
        bmu, bsd = np.nanmean(bi[mi]), np.nanstd(bi[mi]) + 1e-9
        Xi = np.column_stack([(ei[mi]-emu)/esd, (bi[mi]-bmu)/bsd])
        Xo = np.column_stack([(eo[mo]-emu)/esd, (bo[mo]-bmu)/bsd])
        m2 = LogisticRegression().fit(Xi, yi[mi])
        p_oos = m2.predict_proba(Xo)[:, 1]
        return p_oos, mo, m2, (emu, esd, bmu, bsd)

    def btc_only_probs(k):
        def feats(d):
            b = np.array([ret_to_k(r, k) for r in d['btc_sp']])
            e = np.array([ret_to_k(r, k) for r in d['eth_sp']])
            return b, e, d['res_up'].values
        bi, ei, yi = feats(is_df); bo, eo, yo = feats(oos_df)
        mi = ~np.isnan(bi) & ~np.isnan(ei); mo = ~np.isnan(bo) & ~np.isnan(eo)
        bmu, bsd = np.nanmean(bi[mi]), np.nanstd(bi[mi]) + 1e-9
        Xi = ((bi[mi]-bmu)/bsd).reshape(-1, 1); Xo = ((bo[mo]-bmu)/bsd).reshape(-1, 1)
        m2 = LogisticRegression().fit(Xi, yi[mi])
        return m2.predict_proba(Xo)[:, 1], mo

    def strat_metrics(pnl):
        pnl = np.asarray(pnl, float)
        if len(pnl) < 2:
            return None
        mu = pnl.mean(); sd = pnl.std(ddof=1)
        sh = mu / sd * np.sqrt(len(pnl)) if sd > 1e-12 else np.nan  # aggregate Sharpe over sample
        per = mu / sd if sd > 1e-12 else np.nan                     # per-trade Sharpe
        downs = pnl[pnl < 0]
        sor = mu / (downs.std(ddof=1)) if len(downs) > 1 and downs.std(ddof=1) > 1e-12 else np.nan
        tstat = mu / (sd / np.sqrt(len(pnl))) if sd > 1e-12 else np.nan
        wr = (pnl > 0).mean() * 100
        return dict(n=len(pnl), ev=mu, sh=per, sht=tstat, sor=sor, wr=wr, t=tstat)

    def run_taker(p_up, sub_df, mask, thr, half_cost_floor=0.0):
        """Apply taker rule. yes price = ask_path[k] (cross to buy YES), no price = 1-bid_path[k]
        (cross to buy NO = sell YES at bid). Returns pnl array."""
        return None  # replaced below per-k since prices depend on k

    # Sweep k and threshold. For each (k,thr): build trades on OOS, also IS for stability.
    print(f"{'k':>3} {'thr':>5} {'#tr':>5} {'tr/win%':>8} {'netEV(c)':>9} {'hit%':>6} "
          f"{'Sharpe':>7} {'t':>6} {'IS-EV(c)':>9} {'IS#tr':>6}")
    print("-" * 86)

    results = []
    ks = [3, 5, 7, 9, 11]
    thrs = [0.02, 0.04, 0.06, 0.08, 0.10]

    # Precompute IS model-applied-to-IS for stability (in-sample fit eval = optimistic, but for stability check we refit and eval on IS holdout? use simple: eval model on IS itself)
    for k in ks:
        p_oos, mo, m2, _ = model_probs(k)
        sub = oos_df[mo].reset_index(drop=True)
        yes_ask = np.array([r[k] for r in sub['eth_ask']])   # price to BUY YES
        yes_bid = np.array([r[k] for r in sub['eth_bid']])   # price to SELL YES (=1-price to buy NO)
        res = sub['res_up'].values
        # IS in-sample (apply m2 to IS features) for stability
        def is_apply(k, m2):
            bi = np.array([ret_to_k(r, k) for r in is_df['btc_sp']])
            ei = np.array([ret_to_k(r, k) for r in is_df['eth_sp']])
            yi = is_df['res_up'].values
            mi = ~np.isnan(bi) & ~np.isnan(ei)
            # standardize with IS stats (same as fit)
            emu, esd = np.nanmean(ei[mi]), np.nanstd(ei[mi]) + 1e-9
            bmu, bsd = np.nanmean(bi[mi]), np.nanstd(bi[mi]) + 1e-9
            Xi = np.column_stack([(ei[mi]-emu)/esd, (bi[mi]-bmu)/bsd])
            return m2.predict_proba(Xi)[:, 1], mi, yi
        p_is, mi_is, yi_is = is_apply(k, m2)
        is_sub = is_df[mi_is].reset_index(drop=True)
        is_yes_ask = np.array([r[k] for r in is_sub['eth_ask']])
        is_yes_bid = np.array([r[k] for r in is_sub['eth_bid']])
        is_res = is_sub['res_up'].values

        for thr in thrs:
            # OOS trades
            pnl = []
            for i in range(len(sub)):
                ya, yb = yes_ask[i], yes_bid[i]
                if np.isnan(ya) or np.isnan(yb):
                    continue
                pu = p_oos[i]
                # YES edge: model prob up - cost-to-buy-yes (ask)
                edge_yes = pu - ya
                # NO edge: model prob down - cost-to-buy-no (=1-bid)
                edge_no = (1 - pu) - (1 - yb)  # = yb - pu
                if edge_yes >= thr and edge_yes >= edge_no:
                    pnl.append((1 - ya) if res[i] == 1 else (-ya))
                elif edge_no >= thr:
                    pnl.append(((1 - (1 - yb)) if res[i] == 0 else (-(1 - yb))))
                    # buy NO at price (1-yb): win +(1-(1-yb))=yb if res==0 else -(1-yb)
                    pnl[-1] = (yb if res[i] == 0 else -(1 - yb))
            pnl = np.array(pnl, float)
            # IS trades (stability)
            ispnl = []
            for i in range(len(is_sub)):
                ya, yb = is_yes_ask[i], is_yes_bid[i]
                if np.isnan(ya) or np.isnan(yb):
                    continue
                pu = p_is[i]
                edge_yes = pu - ya; edge_no = yb - pu
                if edge_yes >= thr and edge_yes >= edge_no:
                    ispnl.append((1 - ya) if is_res[i] == 1 else (-ya))
                elif edge_no >= thr:
                    ispnl.append(yb if is_res[i] == 0 else -(1 - yb))
            ispnl = np.array(ispnl, float)
            if len(pnl) < 5:
                print(f"{k:>3} {thr:>5.2f} {len(pnl):>5} (too few)")
                continue
            mm = strat_metrics(pnl)
            trwin = len(pnl) / max(1, (n - cut)) * 100  # frac of OOS windows that trade
            is_ev = ispnl.mean()*100 if len(ispnl) else float('nan')
            print(f"{k:>3} {thr:>5.2f} {mm['n']:>5} {trwin:>7.1f}% {mm['ev']*100:>+8.2f}c "
                  f"{mm['wr']:>5.1f}% {mm['sh']:>+7.3f} {mm['t']:>+6.2f} {is_ev:>+8.2f}c {len(ispnl):>6}")
            results.append((k, thr, mm, is_ev, len(ispnl), trwin))

    # ---------- TASK 4: REALISM -- spread distribution + BTC-only replication ----------
    print("\n" + "=" * 78)
    print("TASK 4 :: REALISM -- ETH binary spread + BTC-only replication test")
    print("=" * 78)
    # ETH binary spread distribution by minute k
    print("ETH binary quoted spread (ask-bid, cents) by minute k (OOS):")
    print(f"{'k':>3} {'median':>7} {'mean':>7} {'p90':>6} {'half-sprd':>9}")
    for k in ks:
        spr = np.array([r[k] - b[k] for r, b in zip(oos_df['eth_ask'], oos_df['eth_bid'])])
        spr = spr[~np.isnan(spr)]
        print(f"{k:>3} {np.median(spr)*100:>6.2f}c {spr.mean()*100:>6.2f}c {np.percentile(spr,90)*100:>5.1f}c "
              f"{np.median(spr)/2*100:>8.2f}c")

    # BTC-only replication: same taker rule but trade the BTC binary instead.
    print("\nBTC binary replication: does the SAME signal trade better on BTC's own binary?")
    print("(Use BTC move-to-k -> predict BTC res_up, take BTC binary.) Best (k,thr) by net EV:")
    hb = load('btc')
    bidx = {r['ws']: r for _, r in hb.iterrows()}
    # build btc-only frame aligned to same windows
    brows = []
    for ws in df['ws']:
        b = bidx[ws]
        brows.append(dict(ws=ws, res_up=int(b['res_up']), btc_sp=arr(b['spot_path']),
                          bid=arr(b['bid_path']), ask=arr(b['ask_path'])))
    bdf = pd.DataFrame(brows)
    bis = bdf.iloc[:cut].reset_index(drop=True); boos = bdf.iloc[cut:].reset_index(drop=True)
    best = None
    for k in ks:
        # fit btc-move->btc res_up logit
        ri = np.array([ret_to_k(r, k) for r in bis['btc_sp']]); yi = bis['res_up'].values
        ro = np.array([ret_to_k(r, k) for r in boos['btc_sp']]); yo = boos['res_up'].values
        mi = ~np.isnan(ri); mo = ~np.isnan(ro)
        mu, sd = np.nanmean(ri[mi]), np.nanstd(ri[mi]) + 1e-9
        m2 = LogisticRegression().fit(((ri[mi]-mu)/sd).reshape(-1,1), yi[mi])
        po = m2.predict_proba(((ro[mo]-mu)/sd).reshape(-1,1))[:, 1]
        sub = boos[mo].reset_index(drop=True)
        ask = np.array([r[k] for r in sub['ask']]); bid = np.array([r[k] for r in sub['bid']])
        res = sub['res_up'].values
        for thr in thrs:
            pnl = []
            for i in range(len(sub)):
                ya, yb = ask[i], bid[i]
                if np.isnan(ya) or np.isnan(yb): continue
                pu = po[i]; ey = pu - ya; en = yb - pu
                if ey >= thr and ey >= en:
                    pnl.append((1-ya) if res[i]==1 else -ya)
                elif en >= thr:
                    pnl.append(yb if res[i]==0 else -(1-yb))
            pnl = np.array(pnl, float)
            if len(pnl) < 5: continue
            ev = pnl.mean(); t = ev/(pnl.std(ddof=1)/np.sqrt(len(pnl))) if pnl.std(ddof=1)>1e-12 else np.nan
            if best is None or ev > best[2]:
                best = (k, thr, ev, len(pnl), t, (pnl>0).mean()*100)
    if best:
        print(f"  BTC-only BEST: k={best[0]} thr={best[1]:.2f} netEV={best[2]*100:+.2f}c "
              f"#tr={best[3]} t={best[4]:+.2f} hit={best[5]:.1f}%")

    print("\nDone.")


if __name__ == '__main__':
    main()
