"""
BTC 15-min binary fair-value mispricing study.

Question: is the Kalshi BTC binary PRICE systematically mispriced vs a spot-implied
fair probability, and is a TAKER strategy (cross the spread, hold to settle) +EV net
of taker fee + crossed half-spread?

Settle mechanic: Kalshi BTC15m settles on Coinbase BTC-USD 1-min close vs strike.
Prior work (BTC_DEEP.md) proved spot_path == Coinbase 1-min close EXACTLY. So spot_path
is the settlement reference and the fair-value computation has no feed mismatch in S.

Strike = spot at window open = spot_prev[-1] (mid[k0] mean = 0.504 confirms ATM-at-open;
reproduces res_up for 92.3% of windows, residual = boundary near-ties / settle-minute feed
noise, same structure as the ETH study which got 93.6%).

NO LOOKAHEAD: vol estimated from prior-60-min spot (known at window open) and from the
in-window path up to (and excluding) the decision minute. Strike known at open. Decision at
minute k uses spot_path[k] (price observed at minute k) only.

Costs (taker): crossed half-spread (buy YES at ask, buy NO at 1-bid) PLUS Kalshi crypto
taker fee = ceil(M*P*(1-P)*100)/100 cents, modeled at M=0.07 (std) and M=0.14 (crypto premium).
"""
import pandas as pd, numpy as np
from scipy.stats import norm

HIST = '/tmp/ev_leadlag/hist_kalshi_btc15m.parquet'


def load():
    df = pd.read_parquet(HIST).sort_values('ws').reset_index(drop=True)
    sp = np.vstack(df.spot_path.values).astype(float)      # (N,15) in-window 1-min spot
    spv = np.vstack(df.spot_prev.values).astype(float)     # (N,60) prior 60-min spot
    mid = np.vstack(df.mid_path.values).astype(float)
    bid = np.vstack(df.bid_path.values).astype(float)
    ask = np.vstack(df.ask_path.values).astype(float)
    res = df.res_up.values.astype(int)
    ws = df.ws.values
    return df, sp, spv, mid, bid, ask, res, ws


def realized_settle_minute_check(sp, spv, res):
    """Confirm strike+settle reproduce res_up."""
    K = spv[:, -1]
    sset = sp[:, -1]
    ok = ~np.isnan(sset) & ~np.isnan(K)
    pred = (sset >= K).astype(int)
    return (pred[ok] == res[ok]).mean(), ok.sum()


def fair_prob(S, K, tau_min, sigma_min):
    """Digital P(settle >= K) under driftless GBM. tau in minutes, sigma per-minute.
    d2 = (ln(S/K) - 0.5 sigma^2 tau) / (sigma sqrt(tau)); P = N(d2)."""
    tau_min = np.asarray(tau_min, dtype=float)
    vol = sigma_min * np.sqrt(np.maximum(tau_min, 1e-9))
    d2 = (np.log(S / K) - 0.5 * sigma_min**2 * tau_min) / vol
    p = norm.cdf(d2)
    return np.where(tau_min <= 0, (np.asarray(S) >= np.asarray(K)).astype(float), p)


def taker_fee(P, M):
    """Kalshi taker fee in cents (dollars): ceil(M*P*(1-P)*100)/100."""
    return np.ceil(M * P * (1.0 - P) * 100.0) / 100.0


def build_table(sp, spv, mid, bid, ask, res, ws, sigma_mode='prior60'):
    """One row per (window, decision-minute k) for k=1..13 (tau=14..2).
    sigma known at decision time only."""
    N = sp.shape[0]
    K = spv[:, -1]
    rows = []
    # prior-60 per-min realized vol per window (known at open)
    lrp = np.diff(np.log(spv), axis=1)
    sig_prior = np.nanstd(lrp, axis=1)  # (N,)
    for i in range(N):
        if np.isnan(K[i]) or sig_prior[i] <= 0 or np.isnan(sig_prior[i]):
            continue
        for k in range(1, 14):
            S = sp[i, k]
            if np.isnan(S) or S <= 0:
                continue
            tau = 15 - k  # minutes to expiry (settle at min 15 ~ last close)
            if sigma_mode == 'prior60':
                sig = sig_prior[i]
            elif sigma_mode == 'inwindow':
                # vol from in-window path up to k (exclude future) blended w/ prior
                seg = sp[i, :k+1]
                seg = seg[~np.isnan(seg)]
                if len(seg) >= 3:
                    sw = np.nanstd(np.diff(np.log(seg)))
                    sig = 0.5*sw + 0.5*sig_prior[i] if sw > 0 else sig_prior[i]
                else:
                    sig = sig_prior[i]
            a = ask[i, k]; b = bid[i, k]; m = mid[i, k]
            if np.isnan(a) or np.isnan(b) or np.isnan(m):
                continue
            fp = float(fair_prob(S, K[i], tau, sig))
            rows.append((ws[i], k, tau, S, K[i], sig, fp, m, b, a, res[i]))
    cols = ['ws', 'k', 'tau', 'S', 'K', 'sigma', 'fair', 'mid', 'bid', 'ask', 'res']
    return pd.DataFrame(rows, columns=cols)


def calibration(tab, pcol, nbins=10):
    """Reliability + Brier + LogLoss for a probability column vs realized res."""
    p = tab[pcol].clip(1e-6, 1-1e-6).values
    y = tab['res'].values
    brier = np.mean((p - y)**2)
    ll = -np.mean(y*np.log(p) + (1-y)*np.log(1-p))
    edges = np.quantile(p, np.linspace(0, 1, nbins+1))
    edges[0] = -1; edges[-1] = 2
    binned = []
    for j in range(nbins):
        m = (p >= edges[j]) & (p < edges[j+1])
        if m.sum() > 0:
            binned.append((p[m].mean(), y[m].mean(), m.sum()))
    return brier, ll, binned


def deviation_analysis(tab):
    """gap = mid - fair, signed, by tau band and price band."""
    tab = tab.copy()
    tab['gap'] = tab['mid'] - tab['fair']
    out = {}
    out['overall'] = (tab.gap.mean(), tab.gap.std(), len(tab))
    # by tau band
    tab['taub'] = pd.cut(tab['tau'], [0, 3, 7, 11, 15], labels=['tau1-3', 'tau4-7', 'tau8-11', 'tau12-14'])
    out['by_tau'] = tab.groupby('taub', observed=True)['gap'].agg(['mean', 'std', 'count'])
    # by price band (mid)
    tab['pb'] = pd.cut(tab['mid'], [0, .15, .35, .65, .85, 1.0],
                       labels=['longshot<15', 'low15-35', 'ATM35-65', 'high65-85', 'fav>85'])
    out['by_price'] = tab.groupby('pb', observed=True)['gap'].agg(['mean', 'std', 'count'])
    # favorite-longshot: bin by mid, realized vs mid
    tab['mb'] = pd.cut(tab['mid'], np.linspace(0, 1, 11))
    flb = tab.groupby('mb', observed=True).agg(mid=('mid', 'mean'), real=('res', 'mean'),
                                               fair=('fair', 'mean'), n=('res', 'size'))
    out['favlong'] = flb
    return out


def taker_backtest(tab, M, thr, half_spread_floor=0.0):
    """Taker: cross to whichever side fair says is cheap, hold to settle.
    Buy YES at ask: edge = fair - ask, cost paid = ask, payoff = res. PnL = res - ask - fee.
    Buy NO at (1-bid): edge = (1-fair) - (1-bid) = bid - fair. PnL = (1-res) - (1-bid) - fee.
    Fire side whose post-cross edge > thr. fee at price actually paid."""
    fair = tab['fair'].values
    ask = tab['ask'].values; bid = tab['bid'].values; res = tab['res'].values
    edge_yes = fair - ask
    edge_no = bid - fair
    take_yes = (edge_yes > thr) & (edge_yes >= edge_no)
    take_no = (edge_no > thr) & (edge_no > edge_yes)
    pnl = np.full(len(fair), np.nan)
    # YES
    py = ask[take_yes]
    fee_y = taker_fee(py, M)
    pnl[take_yes] = (res[take_yes] - py - fee_y)
    # NO
    pn = 1 - bid[take_no]
    fee_n = taker_fee(pn, M)
    pnl[take_no] = ((1 - res[take_no]) - pn - fee_n)
    sel = take_yes | take_no
    return pnl[sel], sel, take_yes, take_no


def summ(pnl):
    if len(pnl) == 0:
        return dict(n=0, ev=np.nan, t=np.nan, wr=np.nan, sharpe=np.nan)
    ev = pnl.mean()
    sd = pnl.std(ddof=1) if len(pnl) > 1 else np.nan
    t = ev / (sd / np.sqrt(len(pnl))) if sd > 0 else np.nan
    return dict(n=len(pnl), ev=ev*100, t=t, wr=(pnl > 0).mean(), sharpe=ev/sd if sd>0 else np.nan)


def calibrate_vol(tab):
    """Find per-min sigma (single scalar) minimizing IS Brier of the GBM fair prob.
    Uses the ACTUAL S,K,tau in the table. This is the vol that makes the model calibrated
    -- if the 'mispricing' is real it should survive at this vol; if it's a vol artifact it dies."""
    S = tab['S'].values; K = tab['K'].values; tau = tab['tau'].values; y = tab['res'].values
    best = (None, 1e9)
    for sig in np.linspace(0.0003, 0.0012, 40):
        p = fair_prob(S, K, tau, sig).clip(1e-6, 1-1e-6)
        br = np.mean((p - y)**2)
        if br < best[1]:
            best = (sig, br)
    return best


def main():
    df, sp, spv, mid, bid, ask, res, ws = load()
    print('=== DATA ===')
    print('windows', len(df), 'res_up', res.mean().round(4))
    import datetime as dt
    print('range', dt.datetime.utcfromtimestamp(ws.min()), '->', dt.datetime.utcfromtimestamp(ws.max()))
    match, n = realized_settle_minute_check(sp, spv, res)
    print(f'strike=spot_prev[-1], settle=last close -> reproduces res_up {match:.3f} (n={n})')

    lrp = np.diff(np.log(spv), axis=1)
    print('per-min sigma (prior60) median', np.round(np.nanmedian(np.nanstd(lrp,axis=1)),6))

    tab = build_table(sp, spv, mid, bid, ask, res, ws, sigma_mode='prior60')
    print('table rows', len(tab))

    # time-ordered split 60/40 by ws
    cut = np.quantile(tab['ws'].values, 0.60)
    IS = tab[tab.ws <= cut]; OOS = tab[tab.ws > cut]
    print(f'IS {len(IS)}  OOS {len(OOS)}  (cut {dt.datetime.utcfromtimestamp(cut)})')

    print('=== CALIBRATION (OOS) ===')
    for pcol in ['fair', 'mid']:
        br, ll, binned = calibration(OOS, pcol)
        print(f'{pcol:5s}  Brier {br:.4f}  LogLoss {ll:.4f}')
    print('  fair reliability (pred->real):')
    _, _, fb = calibration(OOS, 'fair')
    print('   ', ' '.join(f'{a:.2f}->{r:.2f}' for a, r, _ in fb))
    print('  mid reliability (pred->real):')
    _, _, mb = calibration(OOS, 'mid')
    print('   ', ' '.join(f'{a:.2f}->{r:.2f}' for a, r, _ in mb))

    print('=== DEVIATION gap=mid-fair (full) ===')
    dev = deviation_analysis(tab)
    print('overall mean/std/n', tuple(round(x,4) if isinstance(x,float) else x for x in dev['overall']))
    print('by tau:', dev['by_tau'].round(4))
    print('by price band:', dev['by_price'].round(4))
    print('favorite-longshot (mid bin -> real vs fair):', dev['favlong'].round(4))

    print('=== TAKER BACKTEST (cross spread, hold to settle) ===')
    for M in [0.07, 0.14]:
        print(f'-- crypto taker fee M={M} --')
        print(f'{"thr":>5} | {"IS n":>6} {"IS ev":>7} {"IS t":>6} | {"OOS n":>6} {"OOS ev":>7} {"OOS t":>6} {"OOS wr":>6} {"Shrp":>6}')
        for thr in [0.00, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12]:
            pis, *_ = taker_backtest(IS, M, thr)
            pos, *_ = taker_backtest(OOS, M, thr)
            si = summ(pis); so = summ(pos)
            print(f'{thr:5.2f} | {si["n"]:6d} {si["ev"]:7.3f} {si["t"]:6.2f} | '
                  f'{so["n"]:6d} {so["ev"]:7.3f} {so["t"]:6.2f} {so["wr"]:6.3f} {so["sharpe"]:6.3f}')

    # where is edge concentrated? OOS at thr=0.03 M=0.14, by tau & price band
    print('=== OOS EDGE LOCATION (thr=0.03, M=0.14) ===')
    pnl, sel, ty, tn = taker_backtest(OOS, 0.14, 0.03)
    osel = OOS[sel].copy(); osel['pnl'] = pnl
    osel['taub'] = pd.cut(osel['tau'], [0,3,7,11,15], labels=['t1-3','t4-7','t8-11','t12-14'])
    g = osel.groupby('taub', observed=True)['pnl'].agg(['mean','count'])
    g['mean']*=100; print('by tau:', g.round(3))
    osel['pb'] = pd.cut((osel['ask']*ty.sum()/ty.sum() if False else osel['mid']), [0,.15,.35,.65,.85,1.0],
                        labels=['ls<15','lo','ATM','hi','fav>85'])
    g2 = osel.groupby('pb', observed=True)['pnl'].agg(['mean','count']); g2['mean']*=100
    print('by price band:', g2.round(3))

    # CALIBRATED-VOL RE-RUN: the prior-60 vol is biased low -> over-confident tails -> fake gap.
    # Find the IS-Brier-minimizing single sigma, rebuild fair, re-run taker. If 'edge' is a vol
    # artifact, it collapses here.
    print('=== VOL CALIBRATION (fix the fake-gap source) ===')
    sig_star, br_star = calibrate_vol(IS)
    print(f'IS-Brier-min sigma = {sig_star:.6f}  (prior60 median {np.nanmedian(np.nanstd(lrp,axis=1)):.6f})')
    ISc = IS.copy(); OOSc = OOS.copy()
    ISc['fair'] = fair_prob(ISc.S.values, ISc.K.values, ISc.tau.values, sig_star)
    OOSc['fair'] = fair_prob(OOSc.S.values, OOSc.K.values, OOSc.tau.values, sig_star)
    brc, llc, fbc = calibration(OOSc, 'fair')
    print(f'calibrated fair OOS Brier {brc:.4f} LogLoss {llc:.4f}  (mid Brier {calibration(OOS,"mid")[0]:.4f})')
    print('calibrated fair reliability:', ' '.join(f'{a:.2f}->{r:.2f}' for a,r,_ in fbc))
    devc = deviation_analysis(ISc.assign(fair=ISc.fair))
    print('calibrated favorite-longshot (mid->real vs fair):', devc['favlong'][['mid','real','fair','n']].round(4))
    print('calibrated taker (M=0.14):')
    print(f'{"thr":>5} | {"OOS n":>6} {"OOS ev":>7} {"OOS t":>6} {"wr":>6}')
    for thr in [0.00, 0.02, 0.03, 0.05]:
        p, *_ = taker_backtest(OOSc, 0.14, thr); s = summ(p)
        print(f'{thr:5.2f} | {s["n"]:6d} {s["ev"]:7.3f} {s["t"]:6.2f} {s["wr"]:6.3f}')

    # VOL SENSITIVITY: scale sigma, see if 'edge' is a vol artifact (OOS thr=0.02 M=0.14)
    print('=== VOL SENSITIVITY (OOS thr=0.02 M=0.14) — is edge a vol artifact? ===')
    base_sig_med = np.nanmedian(np.nanstd(lrp, axis=1))
    for scale in [0.6, 0.8, 1.0, 1.2, 1.5]:
        tt = OOS.copy()
        # recompute fair with scaled sigma
        tt['fair'] = fair_prob(tt['S'].values, tt['K'].values, tt['tau'].values, tt['sigma'].values*scale)
        p, *_ = taker_backtest(tt, 0.14, 0.02)
        s = summ(p)
        print(f'sigma x{scale:.1f}: OOS ev {s["ev"]:7.3f}c  t {s["t"]:6.2f}  n {s["n"]}')


if __name__ == '__main__':
    main()
