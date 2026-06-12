"""
OOS test: do microstructure signals predict settlement better than mid price alone?
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
import os

# ── helpers ──────────────────────────────────────────────────────────────────

def safe_arr(x):
    """Convert stored object (list/ndarray/etc) to numpy float array."""
    if x is None:
        return None
    if isinstance(x, np.ndarray):
        return x.astype(float)
    try:
        return np.array(x, dtype=float)
    except Exception:
        return None

def load_hist(path):
    if not os.path.exists(path):
        return None
    df = pd.read_parquet(path)
    for col in ["mid_path","bid_path","ask_path","spot_path","vol_path"]:
        if col in df.columns:
            df[col] = df[col].apply(safe_arr)
    return df

def load_trades(path):
    """
    Trades parquet: each row = one window, with columns t/p/sz/buy as arrays.
    Returns a compact dict: ws -> per-minute signed-dollar-flow array (len 15).
    This avoids exploding 18M+ rows into a DataFrame.
    """
    if not os.path.exists(path):
        return None
    raw = pd.read_parquet(path)
    flows = {}
    for _, row in raw.iterrows():
        ws_val = float(row["ws"])
        t_arr  = safe_arr(row["t"])
        p_arr  = safe_arr(row["p"])
        sz_arr = safe_arr(row["sz"])
        buy_raw= row["buy"]
        if p_arr is None or t_arr is None:
            flows[ws_val] = np.zeros(15)
            continue
        if isinstance(buy_raw, np.ndarray):
            buy_arr = buy_raw.astype(float)
        else:
            try:
                buy_arr = np.array(buy_raw, dtype=float)
            except Exception:
                flows[ws_val] = np.zeros(15)
                continue
        n = min(len(t_arr), len(p_arr), len(sz_arr), len(buy_arr))
        if n == 0:
            flows[ws_val] = np.zeros(15)
            continue
        t_  = t_arr[:n]
        p_  = p_arr[:n]
        sz_ = sz_arr[:n]
        b_  = buy_arr[:n]
        # minute offset within window
        moff = ((t_ - ws_val) / 60).astype(int)
        moff = np.clip(moff, 0, 14)
        dollar_signed = np.where(b_ == 1, p_ * sz_, -p_ * sz_)
        f = np.zeros(15)
        for m in range(15):
            mask = moff == m
            if mask.any():
                f[m] = dollar_signed[mask].sum()
        flows[ws_val] = f
    return flows  # dict ws -> array[15]

# (build_minute_flows replaced — flows now built inside load_trades)

# ── feature extraction at decision point k ───────────────────────────────────

def extract_features(hist_df, flows, k):
    """Return X (features) and y (target) arrays aligned row-by-row."""
    rows = []
    ys   = []
    ws_vals = []

    for _, row in hist_df.iterrows():
        ws_val  = float(row["ws"])
        mid     = safe_arr(row["mid_path"])
        spot    = safe_arr(row["spot_path"])
        y       = int(row["res_up"])

        if mid is None or len(mid) < k+1:
            continue
        if spot is None or len(spot) < k+1:
            spot = None

        mid_k   = mid[k]
        mid_km1 = mid[k-1] if k > 0 else mid[k]

        # ── flow features ──
        f = flows.get(ws_val, np.zeros(15))
        flow_prev = f[k-1] if k > 0 else 0.0
        flow_cum  = f[:k+1].sum()
        flow_accel= (f[k] - f[k-1]) if k > 0 else 0.0

        # ── spot vs mid divergence ──
        if spot is not None and spot[k-1] != 0 and k > 0:
            spot_ret = (spot[k] - spot[k-1]) / spot[k-1]
            mid_ret  = (mid_k - mid_km1) / (mid_km1 if mid_km1 != 0 else 1e-9)
            spot_lag = spot_ret - mid_ret
        else:
            spot_lag = 0.0

        # ── vol regime ──
        if spot is not None and k > 1:
            spot_rets = np.diff(spot[:k+1]) / (spot[:k] + 1e-12)
            vol_regime = np.std(spot_rets) if len(spot_rets) > 1 else 0.0
        else:
            vol_regime = 0.0

        rows.append({
            "ws": ws_val,
            "mid_k": mid_k,
            "flow_prev": flow_prev,
            "flow_cum":  flow_cum,
            "flow_accel": flow_accel,
            "spot_lag":  spot_lag,
            "vol_regime": vol_regime,
        })
        ys.append(y)
        ws_vals.append(ws_val)

    df_feat = pd.DataFrame(rows)
    df_feat["y"] = ys
    return df_feat

# ── modelling helpers ─────────────────────────────────────────────────────────

LR_KWARGS = dict(solver="lbfgs", max_iter=500, C=0.1, random_state=42)

def fit_predict(X_tr, y_tr, X_te):
    # impute NaN with column means computed on training set
    col_means = np.nanmean(X_tr, axis=0)
    col_means = np.where(np.isnan(col_means), 0.0, col_means)
    nan_mask_tr = np.isnan(X_tr)
    nan_mask_te = np.isnan(X_te)
    X_tr = X_tr.copy(); X_tr[nan_mask_tr] = np.take(col_means, np.where(nan_mask_tr)[1])
    X_te = X_te.copy(); X_te[nan_mask_te] = np.take(col_means, np.where(nan_mask_te)[1])
    # also drop rows in training with all-NaN features (shouldn't occur after impute)
    clf = LogisticRegression(**LR_KWARGS)
    clf.fit(X_tr, y_tr)
    return clf.predict_proba(X_te)[:, 1]

def bootstrap_dauc(y_true, p_base, p_sig, n=500, seed=0):
    rng = np.random.default_rng(seed)
    n_s = len(y_true)
    deltas = []
    for _ in range(n):
        idx = rng.integers(0, n_s, n_s)
        yt  = y_true[idx]
        if len(np.unique(yt)) < 2:
            continue
        a_sig  = roc_auc_score(yt, p_sig[idx])
        a_base = roc_auc_score(yt, p_base[idx])
        deltas.append(a_sig - a_base)
    deltas = np.array(deltas)
    p_val = (deltas <= 0).mean()
    return np.mean(deltas), p_val

SIGNAL_COLS = {
    "flow_imb_prev":       ["mid_k","flow_prev"],
    "flow_imb_cum":        ["mid_k","flow_cum"],
    "flow_accel":          ["mid_k","flow_accel"],
    "spot_lag":            ["mid_k","spot_lag"],
    "vol_regime_interact": ["mid_k","flow_prev","flow_cum","vol_regime"],
    "combined":            ["mid_k","flow_prev","flow_cum","flow_accel","spot_lag","vol_regime"],
}

# ── main ──────────────────────────────────────────────────────────────────────

BASE_DIR = "/home/user/Codex-playground-"
ASSETS   = ["btc","eth","sol","xrp"]

# load data
hist_all   = {}
trades_all = {}
for asset in ASSETS:
    hp = f"{BASE_DIR}/hist_kalshi_{asset}15m.parquet"
    tp = f"{BASE_DIR}/trades_kalshi_{asset}15m.parquet"
    h = load_hist(hp)
    if h is not None:
        print(f"  loading {asset} trades ...", end=" ", flush=True)
        flows = load_trades(tp)  # returns dict ws->array[15] or None
        hist_all[asset]   = h
        trades_all[asset] = flows if flows is not None else {}
        n_flows = len(flows) if flows is not None else 0
        print(f"{len(h)} hist rows, {n_flows} flow windows")
    else:
        print(f"  {asset}: hist not found, skipping")

# pool all assets into one frame after building flows per asset
all_feat_by_k = {k_: [] for k_ in [5,7,9,11]}

for asset, hist_df in hist_all.items():
    hist_df = hist_df.sort_values("ws").reset_index(drop=True)
    flows = trades_all.get(asset, {})  # already a dict ws->array[15]
    if flows is None:
        flows = {}
    for k_ in [5,7,9,11]:
        df_feat = extract_features(hist_df, flows, k_)
        df_feat["asset"] = asset
        all_feat_by_k[k_].append(df_feat)

# concatenate across assets
feat_by_k = {}
for k_, frames in all_feat_by_k.items():
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values("ws").reset_index(drop=True)
        feat_by_k[k_] = combined
        print(f"  k={k_}: {len(combined)} total rows")

# ── IS/OOS split (60/40 by sorted ws) ────────────────────────────────────────

results_auc  = {}   # signal -> list of (dauc, pval) per k
results_loss = {}   # signal -> list of dloss per k

for sig_name, cols in SIGNAL_COLS.items():
    results_auc[sig_name]  = {}
    results_loss[sig_name] = {}

    for k_ in [5,7,9,11]:
        df = feat_by_k.get(k_)
        if df is None or len(df) < 20:
            results_auc[sig_name][k_]  = (np.nan, np.nan)
            results_loss[sig_name][k_] = np.nan
            continue

        n     = len(df)
        split = int(n * 0.6)
        df_is = df.iloc[:split]
        df_os = df.iloc[split:]

        y_is = df_is["y"].values
        y_os = df_os["y"].values

        if len(np.unique(y_os)) < 2:
            results_auc[sig_name][k_]  = (np.nan, np.nan)
            results_loss[sig_name][k_] = np.nan
            continue

        # scale features (crude standardise on IS)
        def scale(df_s, mu, sd):
            return (df_s - mu) / (sd + 1e-12)

        # baseline model: mid_k only
        X_base_is = df_is[["mid_k"]].values
        X_base_os = df_os[["mid_k"]].values
        mu_b = X_base_is.mean(0); sd_b = X_base_is.std(0)
        p_base = fit_predict(scale(X_base_is, mu_b, sd_b), y_is,
                             scale(X_base_os, mu_b, sd_b))

        # signal model
        avail = [c for c in cols if c in df.columns]
        X_sig_is = df_is[avail].values
        X_sig_os = df_os[avail].values
        mu_s = X_sig_is.mean(0); sd_s = X_sig_is.std(0)
        p_sig = fit_predict(scale(X_sig_is, mu_s, sd_s), y_is,
                            scale(X_sig_os, mu_s, sd_s))

        auc_base = roc_auc_score(y_os, p_base)
        auc_sig  = roc_auc_score(y_os, p_sig)
        dauc     = auc_sig - auc_base

        ll_base = log_loss(y_os, p_base)
        ll_sig  = log_loss(y_os, p_sig)
        dloss   = ll_sig - ll_base

        _, pval = bootstrap_dauc(y_os, p_base, p_sig, n=500)

        results_auc[sig_name][k_]  = (dauc, pval)
        results_loss[sig_name][k_] = dloss

# ── economic test ─────────────────────────────────────────────────────────────

def economic_test(feat_by_k, signal_name, sig_cols):
    """Simulate hold/cut for all ks, pool results."""
    pnl_hold_all = []
    pnl_cut_all  = []
    pnl_sig_all  = []
    pnl_comb_all = []

    for k_ in [5,7,9,11]:
        df = feat_by_k.get(k_)
        if df is None or len(df) < 20:
            continue
        n     = len(df)
        split = int(n * 0.6)
        df_is = df.iloc[:split]
        df_os = df.iloc[split:]

        y_is = df_is["y"].values
        y_os = df_os["y"].values

        if len(np.unique(y_os)) < 2:
            continue

        def scale(x, mu, sd):
            return (x - mu) / (sd + 1e-12)

        # baseline
        X_b_is = df_is[["mid_k"]].values
        X_b_os = df_os[["mid_k"]].values
        mu_b = X_b_is.mean(0); sd_b = X_b_is.std(0)

        # best signal
        avail_s = [c for c in sig_cols if c in df.columns]
        X_s_is  = df_is[avail_s].values
        X_s_os  = df_os[avail_s].values
        mu_s = X_s_is.mean(0); sd_s = X_s_is.std(0)
        p_sig = fit_predict(scale(X_s_is, mu_s, sd_s), y_is,
                            scale(X_s_os, mu_s, sd_s))

        # combined
        comb_cols = ["mid_k","flow_prev","flow_cum","flow_accel","spot_lag","vol_regime"]
        avail_c   = [c for c in comb_cols if c in df.columns]
        X_c_is = df_is[avail_c].values
        X_c_os = df_os[avail_c].values
        mu_c = X_c_is.mean(0); sd_c = X_c_is.std(0)
        p_comb = fit_predict(scale(X_c_is, mu_c, sd_c), y_is,
                             scale(X_c_os, mu_c, sd_c))

        mid_os = df_os["mid_k"].values

        # YES leg P&L: res_up*1 - (1 - mid_k) if hold, else 0
        def yes_pnl(y, mid, prob, hi=0.55, lo=0.45):
            """hold if prob>hi or in grey zone, cut (pnl=0) if prob<lo"""
            y    = np.asarray(y,    dtype=float)
            mid  = np.asarray(mid,  dtype=float)
            prob = np.asarray(prob, dtype=float)
            raw  = y - (1.0 - mid)        # hold payoff for YES leg
            cut  = prob < lo              # cut → pnl = 0
            return np.where(cut, 0.0, raw)

        mid_os   = np.array(mid_os,  dtype=float)
        y_os_arr = np.array(y_os,    dtype=float)
        p_sig    = np.array(p_sig,   dtype=float)
        p_comb   = np.array(p_comb,  dtype=float)

        hold_pnl = y_os_arr - (1.0 - mid_os)
        cut_pnl  = np.zeros(len(y_os_arr))
        sig_pnl  = yes_pnl(y_os_arr, mid_os, p_sig)
        comb_pnl = yes_pnl(y_os_arr, mid_os, p_comb)

        # keep only rows with finite values
        valid = (np.isfinite(hold_pnl) & np.isfinite(sig_pnl) &
                 np.isfinite(comb_pnl))
        hold_pnl = hold_pnl[valid]
        cut_pnl  = cut_pnl[valid]
        sig_pnl  = sig_pnl[valid]
        comb_pnl = comb_pnl[valid]

        pnl_hold_all.extend(hold_pnl)
        pnl_cut_all.extend(cut_pnl)
        pnl_sig_all.extend(sig_pnl)
        pnl_comb_all.extend(comb_pnl)

    def summarise(arr):
        arr = np.array(arr, dtype=float)
        arr = arr[np.isfinite(arr)]
        return np.mean(arr) if len(arr) > 0 else 0.0, len(arr)

    h_m, h_n   = summarise(pnl_hold_all)
    c_m, c_n   = summarise(pnl_cut_all)
    s_m, s_n   = summarise(pnl_sig_all)
    cb_m, cb_n = summarise(pnl_comb_all)

    return {
        "always-hold":    (h_m,  h_n),
        "always-cut":     (c_m,  c_n),
        "signal-hold/cut":(s_m,  s_n),
        "combined":       (cb_m, cb_n),
    }

# find best single signal by avg dauc
avg_daucs = {}
for sig in SIGNAL_COLS:
    if sig == "combined":
        continue
    vals = [results_auc[sig][k_][0] for k_ in [5,7,9,11]
            if not np.isnan(results_auc[sig][k_][0])]
    avg_daucs[sig] = np.mean(vals) if vals else np.nan

best_sig  = max(avg_daucs, key=lambda s: avg_daucs[s] if not np.isnan(avg_daucs[s]) else -999)
best_cols = SIGNAL_COLS[best_sig]
econ      = economic_test(feat_by_k, best_sig, best_cols)

# ── print results ─────────────────────────────────────────────────────────────

print()
print("=" * 80)
print("=== SIGNAL vs MID-ALONE, OOS ===")
print("=" * 80)
hdr = f"{'Signal':<22}| {'k=5 dAUC':>9} | {'k=7 dAUC':>9} | {'k=9 dAUC':>9} | {'k=11 dAUC':>10} | {'avg dAUC':>9} | {'p-val':>6}"
print(hdr)
print("-"*88)
for sig in SIGNAL_COLS:
    vals  = [results_auc[sig][k_][0] for k_ in [5,7,9,11]]
    pvals = [results_auc[sig][k_][1] for k_ in [5,7,9,11]]
    avg_v = np.nanmean(vals)
    # use average p-val across k values (more conservative than min)
    pv    = np.nanmean([p for p in pvals if not np.isnan(p)] or [np.nan])
    def fmt(v):
        return f"{v:+.4f}" if not np.isnan(v) else "  nan  "
    print(f"{sig:<22}| {fmt(vals[0]):>9} | {fmt(vals[1]):>9} | {fmt(vals[2]):>9} | {fmt(vals[3]):>10} | {fmt(avg_v):>9} | {pv:>6.3f}")

print()
print("=== LOG-LOSS DELTA (negative = better than mid-alone) ===")
print("-"*88)
hdr2 = f"{'Signal':<22}| {'k=5 dLL':>9} | {'k=7 dLL':>9} | {'k=9 dLL':>9} | {'k=11 dLL':>10} | {'avg dLL':>9}"
print(hdr2)
print("-"*88)
for sig in SIGNAL_COLS:
    vals = [results_loss[sig][k_] for k_ in [5,7,9,11]]
    avg_v= np.nanmean(vals)
    def fmt(v):
        return f"{v:+.5f}" if not np.isnan(v) else "  nan  "
    print(f"{sig:<22}| {fmt(vals[0]):>9} | {fmt(vals[1]):>9} | {fmt(vals[2]):>9} | {fmt(vals[3]):>10} | {fmt(avg_v):>9}")

print()
print(f"=== ECONOMIC TEST (OOS, best signal = {best_sig}) ===")
hdr3 = f"{'Strategy':<18}| {'P&L/trade':>10} | {'vs always-hold':>15} | {'vs always-cut':>14} | {'N_trades':>9}"
print(hdr3)
print("-"*70)
hold_m = econ["always-hold"][0]
cut_m  = econ["always-cut"][0]
for strat, (m, n) in econ.items():
    vs_hold = m - hold_m
    vs_cut  = m - cut_m
    print(f"{strat:<18}| {m:>+10.5f} | {vs_hold:>+15.5f} | {vs_cut:>+14.5f} | {n:>9}")

print()
print("=== VERDICT ===")

# gather summary stats for verdict
avg_dauc_vals = {s: np.nanmean([results_auc[s][k_][0] for k_ in [5,7,9,11]])
                 for s in SIGNAL_COLS}
best_combined = avg_dauc_vals["combined"]
best_single   = avg_dauc_vals[best_sig]

hold_m_v = econ["always-hold"][0]
sig_m_v  = econ["signal-hold/cut"][0]
comb_m_v = econ["combined"][0]

best_k_dauc = {}
for sig in SIGNAL_COLS:
    best_k_dauc[sig] = max([results_auc[sig][k_][0] for k_ in [5,7,9,11]
                            if not np.isnan(results_auc[sig][k_][0])],
                           default=np.nan)

any_sig_edge = any(avg_dauc_vals[s] > 0.005 for s in SIGNAL_COLS if s != "combined")
comb_edge    = best_combined > 0.005

print(f"""
OOS microstructure signals show {'SOME measurable' if any_sig_edge else 'NO consistent'} lift over the
mid-price-alone benchmark across k=5,7,9,11. The best single signal is
'{best_sig}' (avg dAUC={best_single:+.4f}); the combined model gives avg dAUC={best_combined:+.4f}.

Spot-lag divergence tests whether BTC spot moves are yet to be reflected in Kalshi
mid; flow imbalance tests whether taker aggression predicts settlement. If dAUCs are
near zero, this confirms the Kalshi mid is a highly efficient prior for these short
windows, consistent with liquid arbitrage between spot and binary prices.

In the economic simulation (YES legs, hold/cut at 55/45% thresholds), the signal
strategy yields {sig_m_v:+.5f} $/trade vs always-hold at {hold_m_v:+.5f} $/trade. Any
lift from holding fewer losing legs must be weighed against the opportunity cost of
cutting legs that would have paid out.

Bootstrap p-values for incremental AUC near 0.05 or below indicate statistically
significant OOS signal; values near 0.50 are noise. Given the small sample (pooled
across assets), treat any dAUC < 0.005 as economically meaningless even if formally
significant.

Practical verdict: the Kalshi mid encodes most of the available information within
the first 5-11 minutes of a window. Microstructure flow signals add {'modest but real' if any_sig_edge else 'negligible'}
incremental value — {'consistent with a weakly efficient limit-order book' if not any_sig_edge else 'suggesting a small hold/cut filter could modestly reduce inventory cost on unpaired legs, but sizing would need to be tight to overcome transaction risk'}.
""")
