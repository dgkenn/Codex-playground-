"""
btc_deep_model.py -- Build short-horizon BTC direction signal and run THE DECISIVE
incremental-AUC-over-mid test for Kalshi BTC 15-min transfer.

Decision minutes k = 2..12. Label = res_up (settlement).

Features at minute k (only info available by minute k):
  A. Spot-path features from Kalshi settle-index spot_path[0..k] + spot_prev (60m prior):
     multi-horizon momentum, acceleration, realized vol, distance-to-strike, microstructure.
  B. CEX (Coinbase/OKX 1m candles) returns/volume aligned to window minutes + lead-lag
     vs the Kalshi index (does CEX lead the settle index within the window?).
  C. Derivatives: OKX funding rate (slow, daily-ish; included as level/sign).

Models: logistic (L2) and GBM (HistGradientBoosting). Time-ordered OOS split (no leak).

THE KEY TEST: AUC of [signal + mid@k] minus AUC of [mid@k alone], OOS.
Then EV/trade when |model_p - mid| > thresh, taking the binary side, net of ~2-4c cost.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
import warnings, os
warnings.filterwarnings("ignore")

HIST = "/tmp/cx_btcdeep/hist_kalshi_btc15m.parquet"
CACHE = "/tmp/cx_btcdeep/cex_cache"
DECISION_MINS = list(range(2, 13))
COST = 0.03  # ~3c round-ish taker cost (crossed spread + fee), mid of the 2-4c band


def load():
    h = pd.read_parquet(HIST).reset_index(drop=True)
    h = h.sort_values("ws").reset_index(drop=True)
    def A(c):
        return np.stack(h[c].apply(lambda x: np.array(x, dtype=float)).values)
    d = dict(
        ws=h.ws.values.astype(np.int64),
        res=h.res_up.values.astype(int),
        MID=A("mid_path"), BID=A("bid_path"), ASK=A("ask_path"),
        VOL=A("vol_path"), SP=A("spot_path"), SPP=A("spot_prev"),
    )
    return d


def load_cex():
    out = {}
    for name in ["coinbase_1m", "okx_1m"]:
        fp = f"{CACHE}/{name}.parquet"
        if os.path.exists(fp):
            df = pd.read_parquet(fp).set_index("ts")
            out[name] = df
    fp = f"{CACHE}/okx_funding.parquet"
    if os.path.exists(fp):
        out["funding"] = pd.read_parquet(fp)
    return out


def clean(SP):
    """Forward/back fill NaNs in a path matrix row-wise so features are computable."""
    SP = SP.copy()
    for i in range(SP.shape[0]):
        row = SP[i]
        if np.any(np.isnan(row)):
            idx = np.arange(len(row))
            good = ~np.isnan(row)
            if good.sum() == 0:
                row[:] = 0.0
            else:
                row[:] = np.interp(idx, idx[good], row[good])
            SP[i] = row
    return SP


def cex_window_close(cexdf, ws, n=15, pre=15):
    """Return (close[n], vol[n], pre_close[pre]) arrays for each window from a CEX 1m df.
    Aligned so col j is the candle at ws+j*60. NaN where missing."""
    if cexdf is None:
        return None
    ts2c = cexdf["close"].to_dict()
    ts2v = cexdf["vol"].to_dict()
    N = len(ws)
    C = np.full((N, n), np.nan)
    V = np.full((N, n), np.nan)
    PC = np.full((N, pre), np.nan)
    for i, w in enumerate(ws):
        for j in range(n):
            C[i, j] = ts2c.get(int(w) + j * 60, np.nan)
            V[i, j] = ts2v.get(int(w) + j * 60, np.nan)
        for j in range(pre):
            PC[i, j] = ts2c.get(int(w) - (pre - j) * 60, np.nan)
    return C, V, PC


def build_features(d, cex, k):
    """Features known by decision minute k (use spot_path[0..k] inclusive)."""
    SP = clean(d["SP"]); SPP = clean(d["SPP"]); VOL = d["VOL"]
    BID = d["BID"]; ASK = d["ASK"]
    N = SP.shape[0]
    feats = {}
    s = SP[:, : k + 1]  # window spot up to k
    strike = SPP[:, -1]  # best proxy for settle strike (prev_last gave 92% match)
    p0 = SP[:, 0]
    pk = SP[:, k]
    # --- A: spot-path momentum / accel / vol ---
    feats["ret_0_k"] = np.log(pk / p0)
    feats["dist_strike"] = (pk - strike) / strike
    for h in [1, 2, 3, 5]:
        if k - h >= 0:
            feats[f"mom_{h}"] = np.log(pk / SP[:, k - h])
        else:
            feats[f"mom_{h}"] = np.log(pk / p0)
    # acceleration: recent mom vs earlier mom
    if k >= 4:
        feats["accel"] = (np.log(pk / SP[:, k - 2])) - (np.log(SP[:, k - 2] / SP[:, k - 4]))
    else:
        feats["accel"] = np.log(pk / p0)
    # realized vol within window so far
    rets = np.diff(np.log(s), axis=1) if k >= 1 else np.zeros((N, 1))
    feats["rv_win"] = np.sqrt(np.nansum(rets ** 2, axis=1))
    feats["last_ret"] = rets[:, -1] if rets.shape[1] else np.zeros(N)
    # prior 60m context (all available pre-window)
    pr = np.diff(np.log(SPP), axis=1)
    feats["rv_prev60"] = np.sqrt(np.nansum(pr ** 2, axis=1))
    feats["mom_prev60"] = np.log(SPP[:, -1] / SPP[:, 0])
    feats["mom_prev15"] = np.log(SPP[:, -1] / SPP[:, -16]) if SPP.shape[1] > 16 else np.zeros(N)
    # microstructure: position of pk within window range so far
    rng = (np.nanmax(s, axis=1) - np.nanmin(s, axis=1))
    feats["range_pos"] = np.where(rng > 0, (pk - np.nanmin(s, axis=1)) / rng, 0.5)
    feats["minutes_left"] = np.full(N, 14 - k, dtype=float)
    # Kalshi book features (legit info, but NOT the mid itself for the standalone signal)
    feats["spread_k"] = (ASK[:, k] - BID[:, k])
    feats["vol_k"] = np.log1p(np.nan_to_num(VOL[:, k]))
    feats["vol_cum"] = np.log1p(np.nansum(VOL[:, : k + 1], axis=1))
    # --- B: CEX lead-lag / flow ---
    for name in ["coinbase_1m", "okx_1m"]:
        cc = cex.get(f"_{name}")
        if cc is None:
            continue
        C, V, PC = cc
        ck = C[:, k]; c0 = C[:, 0]
        feats[f"{name}_ret_0_k"] = np.log(ck / c0)
        # lead-lag: CEX recent return MINUS index recent return (does CEX move first?)
        if k >= 1:
            cex_lastret = np.log(C[:, k] / C[:, k - 1])
            idx_lastret = np.log(pk / SP[:, k - 1])
            feats[f"{name}_lead"] = cex_lastret - idx_lastret
            # CEX-index basis (level dislocation)
            feats[f"{name}_basis"] = np.log(ck / pk)
        feats[f"{name}_vol_cum"] = np.log1p(np.nansum(V[:, : k + 1], axis=1))
        # signed-volume proxy: sum(sign(ret)*vol) within window = crude CVD
        cret = np.diff(np.log(np.nan_to_num(C[:, : k + 1], nan=np.nan)), axis=1)
        cvd = np.nansum(np.sign(cret) * np.nan_to_num(V[:, 1 : k + 1]), axis=1)
        feats[f"{name}_cvd"] = np.sign(cvd) * np.log1p(np.abs(cvd))
    # --- C: funding ---
    fund = cex.get("funding")
    if fund is not None and len(fund):
        fr = fund.sort_values("ts")
        # most recent funding before window start
        vals = np.full(N, 0.0)
        ft = fr.ts.values; fv = fr.fundingRate.values
        for i, w in enumerate(d["ws"]):
            j = np.searchsorted(ft, w) - 1
            vals[i] = fv[j] if j >= 0 else 0.0
        feats["funding"] = vals
    X = pd.DataFrame(feats)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return X


def ev_test(p_model, mid, res, cost):
    """When model disagrees with mid by > thresh, take the binary side model favors.
    EV/trade = realized payoff (1 if right side) - entry price - cost.
    For a YES taker at price=ask~mid: pay mid, get 1 if res_up else 0.
    Net EV = (res_up - mid) - cost for YES; (mid - res_up) - cost for NO. We take side model says."""
    rows = []
    for thr in [0.03, 0.05, 0.08, 0.10, 0.15]:
        take_yes = (p_model - mid) > thr
        take_no = (mid - p_model) > thr
        evs = []
        for mask, side in [(take_yes, 1), (take_no, 0)]:
            if mask.sum() == 0:
                continue
            m = mid[mask]; r = res[mask]
            if side == 1:
                ev = (r - m) - cost  # buy YES at ~mid
            else:
                ev = ((1 - r) - (1 - m)) - cost  # buy NO at ~(1-mid)
            evs.append(ev)
        if not evs:
            rows.append((thr, 0, np.nan, np.nan))
            continue
        allev = np.concatenate(evs)
        rows.append((thr, len(allev), allev.mean(), allev.mean() / (allev.std() / np.sqrt(len(allev)) + 1e-9)))
    return rows


def main():
    d = load()
    cexraw = load_cex()
    cex = dict(cexraw)
    for name in ["coinbase_1m", "okx_1m"]:
        cex[f"_{name}"] = cex_window_close(cexraw.get(name), d["ws"])
    res = d["res"]
    MID = clean(d["MID"])
    N = len(res)
    # time-ordered split: first 65% train, last 35% OOS
    order = np.argsort(d["ws"])
    cut = int(N * 0.65)
    tr_idx = order[:cut]; te_idx = order[cut:]
    print(f"N={N} train={len(tr_idx)} oos={len(te_idx)}")
    print(f"OOS date range: {pd.to_datetime(d['ws'][te_idx].min(),unit='s')} .. {pd.to_datetime(d['ws'][te_idx].max(),unit='s')}")
    print(f"CEX loaded: coinbase={cex.get('_coinbase_1m') is not None} okx={cex.get('_okx_1m') is not None} funding={len(cexraw.get('funding',[]))>0}")
    print()
    results = []
    for k in DECISION_MINS:
        X = build_features(d, cex, k)
        Xtr, Xte = X.iloc[tr_idx], X.iloc[te_idx]
        ytr, yte = res[tr_idx], res[te_idx]
        midk = MID[:, k]
        midk_tr, midk_te = midk[tr_idx], midk[te_idx]
        # mid baseline OOS AUC
        auc_mid = roc_auc_score(yte, midk_te)
        # --- signal alone (GBM) ---
        gbm = HistGradientBoostingClassifier(max_iter=200, max_depth=3, learning_rate=0.05,
                                             l2_regularization=1.0, min_samples_leaf=40,
                                             random_state=0)
        gbm.fit(Xtr, ytr)
        p_sig = gbm.predict_proba(Xte)[:, 1]
        auc_sig = roc_auc_score(yte, p_sig)
        # logistic alt
        sc = StandardScaler().fit(Xtr)
        lr = LogisticRegression(C=0.5, max_iter=2000).fit(sc.transform(Xtr), ytr)
        p_lr = lr.predict_proba(sc.transform(Xte))[:, 1]
        auc_lr = roc_auc_score(yte, p_lr)
        # --- DECISIVE incremental test (two framings) ---
        # (1) GBM on [features + mid] vs mid alone
        Xtr2 = Xtr.copy(); Xte2 = Xte.copy()
        Xtr2["__mid"] = midk_tr; Xte2["__mid"] = midk_te
        gbm2 = HistGradientBoostingClassifier(max_iter=200, max_depth=3, learning_rate=0.05,
                                              l2_regularization=1.0, min_samples_leaf=40,
                                              random_state=0)
        gbm2.fit(Xtr2, ytr)
        p_both = gbm2.predict_proba(Xte2)[:, 1]
        auc_both = roc_auc_score(yte, p_both)
        dauc = auc_both - auc_mid
        # (2) Cleanest incremental: logistic of res ~ [logit(mid), signal_score].
        #     signal_score = GBM-on-features prob (p_sig). Compare OOS AUC of
        #     [logit_mid + sig] vs [logit_mid] alone. This isolates residual lift.
        def logit(p):
            p = np.clip(p, 1e-4, 1 - 1e-4); return np.log(p / (1 - p))
        p_sig_tr = gbm.predict_proba(Xtr)[:, 1]
        lm_tr = logit(midk_tr).reshape(-1, 1); lm_te = logit(midk_te).reshape(-1, 1)
        sg_tr = logit(p_sig_tr).reshape(-1, 1); sg_te = logit(p_sig).reshape(-1, 1)
        lr_m = LogisticRegression(C=1e6, max_iter=2000).fit(lm_tr, ytr)
        auc_lm = roc_auc_score(yte, lr_m.predict_proba(lm_te)[:, 1])
        Z_tr = np.hstack([lm_tr, sg_tr]); Z_te = np.hstack([lm_te, sg_te])
        lr_ms = LogisticRegression(C=1.0, max_iter=2000).fit(Z_tr, ytr)
        p_ms = lr_ms.predict_proba(Z_te)[:, 1]
        auc_ms = roc_auc_score(yte, p_ms)
        dauc_clean = auc_ms - auc_lm
        # EV test using the clean blended prob vs mid (the disagreement trades)
        evrows = ev_test(p_ms, midk_te, yte, COST)
        best_ev = max(evrows, key=lambda r: (r[2] if not np.isnan(r[2]) else -9))
        results.append(dict(k=k, auc_mid=auc_mid, auc_sig=auc_sig, auc_lr=auc_lr,
                            auc_both=auc_both, dauc=dauc,
                            auc_lm=auc_lm, auc_ms=auc_ms, dauc_clean=dauc_clean,
                            ev_thr=best_ev[0], ev_n=best_ev[1], ev_mean=best_ev[2], ev_t=best_ev[3],
                            evrows=evrows))
    # report
    print("=" * 96)
    print(f"{'k':>2} {'mid_AUC':>8} {'sig_AUC':>8} {'both_AUC':>9} {'dAUC_gbm':>8} "
          f"{'dAUC_clean':>10} | best-EV(thr,n,mean,t)")
    print("-" * 96)
    for r in results:
        print(f"{r['k']:>2} {r['auc_mid']:>8.4f} {r['auc_sig']:>8.4f} "
              f"{r['auc_both']:>9.4f} {r['dauc']:>+8.4f} {r['dauc_clean']:>+10.4f} | "
              f"thr={r['ev_thr']:.2f} n={r['ev_n']:>4} ev={r['ev_mean']:+.4f} t={r['ev_t']:.2f}")
    print("=" * 96)
    print("dAUC_clean = OOS AUC[logit(mid)+signal] - OOS AUC[logit(mid)]  <-- THE KEY NUMBER")
    df = pd.DataFrame([{kk: vv for kk, vv in r.items() if kk != 'evrows'} for r in results])
    df.to_csv("/tmp/cx_btcdeep/btc_deep_results.csv", index=False)
    # full EV grid for a representative mid-window k
    print("\nFull EV grid (k=6, k=9):")
    for r in results:
        if r['k'] in (6, 9):
            print(f" k={r['k']}: " + " | ".join(f"thr{t:.2f}:n{n},ev{e:+.4f},t{tt:.2f}" for (t,n,e,tt) in r['evrows']))
    return results, df


if __name__ == "__main__":
    main()
