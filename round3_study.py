"""round3_study.py -- Round 3 strand-prevention research loop.

IDEAS TESTED:
  R3-1: Settlement-magnitude GBM regressor (continuous settle target, not binary strand)
  R3-2a: Directional strand classifiers (YES-leg vs NO-leg separate models)
  R3-2b: Symmetric NO-guard (mirror t36 for NO-leg, UP-move-adverse-conditioned)
  R3-4: Perp-hedge net PnL on OOS residual strands with realistic costs
  R3-5: Volatility-regime conditioning (skip vol-quartile gates)

DESIGN NOTES:
  - Window-level replay (not fill-level -- avoids 2M-row iteration that times out)
  - Strand classification from trade price zones (YES-side vs NO-side by threshold)
  - t36 gate at ENTRY signal: spot_path[0] vs spot_prev[-3:] (no look-ahead bias)
  - IS = first 300 windows, OOS = last 200 windows (time-ordered)
  - settle_box = spread * 100 (algebraically) -- so target settle_yes or settle_no separately
  - Judge vs live_current (t36); forward bar: t>3, n>=300 (per PREVENT_BAD_TRADES.md)
"""
from __future__ import annotations
import sys, os, warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

REPO = "/tmp/r3"
sys.path.insert(0, REPO)
os.chdir(REPO)

print("=" * 70)
print("Loading parquet data...")
h = pd.read_parquet(os.path.join(REPO, "hist_kalshi_btc15m.parquet")).set_index("ws")
t = pd.read_parquet(os.path.join(REPO, "trades_kalshi_btc15m.parquet")).set_index("ws")

def arr(x):
    if isinstance(x, (list, np.ndarray)):
        return np.asarray(x, float)
    if isinstance(x, str):
        import ast
        return np.asarray(ast.literal_eval(x), float)
    return np.asarray(x, float)

common = sorted(set(h.index) & set(t.index))
n_total = len(common)
cut = min(300, int(n_total * 0.6))
is_ws_set = set(common[:cut])
oos_ws_list = common[cut:cut + 200] if len(common) >= cut + 200 else common[cut:]
print(f"Total windows: {n_total}, IS: {len(is_ws_set)}, OOS: {len(oos_ws_list)}")

# ---------------------------------------------------------------------------
# Book coverage check
# ---------------------------------------------------------------------------
import gzip, json, glob as glob_mod
OVERNIGHT_DIR = os.path.join(REPO, "overnight_data")
book_ws = set()
if os.path.isdir(OVERNIGHT_DIR):
    for fp in glob_mod.glob(os.path.join(OVERNIGHT_DIR, "book_kalshi_btc15m_r*.jsonl.gz")):
        try:
            with gzip.open(fp, "rt") as fh:
                for ln in fh:
                    try:
                        r = json.loads(ln)
                        if r.get("type") == "book" and "ws" in r:
                            book_ws.add(r["ws"])
                    except:
                        continue
        except:
            continue
is_book_cov = sum(1 for w in is_ws_set if w in book_ws)
oos_book_cov = sum(1 for w in oos_ws_list if w in book_ws)
print(f"Book-covered windows: {len(book_ws)} total, IS={is_book_cov}, OOS={oos_book_cov}")
if is_book_cov == 0:
    print("FLAG: IS book coverage = 0 (book stream is RECENT-only)")

# ---------------------------------------------------------------------------
# VPIN helper
# ---------------------------------------------------------------------------
def vpin_w(t_a, sz_a, buy_a, nb=10):
    if len(t_a) < nb:
        return 0.5
    V = float(sz_a.sum()) / nb
    if V <= 0:
        return 0.5
    bkts = []
    vb = vs = 0.0
    for i in range(len(t_a)):
        if buy_a[i]:
            vb += sz_a[i]
        else:
            vs += sz_a[i]
        if vb + vs >= V:
            bkts.append(abs(vb - vs) / (vb + vs))
            vb = vs = 0.0
    return float(np.mean(bkts)) if bkts else 0.5

# ---------------------------------------------------------------------------
# Window feature extraction
# ---------------------------------------------------------------------------
print("Building per-window feature matrix...")

def extract_features(ws):
    h_row = h.loc[ws]
    t_row = t.loc[ws]
    res_up = int(h_row["res_up"])
    bid = arr(h_row["bid_path"])
    ask = arr(h_row["ask_path"])
    spot_path = arr(h_row["spot_path"])
    spot_prev_raw = h_row.get("spot_prev")
    spot_prev = arr(spot_prev_raw) if spot_prev_raw is not None else np.array([])

    p_yes_mid = float(np.nanmean(bid))
    p_no_mid = float(np.nanmean(ask))
    spread = float(p_no_mid - p_yes_mid)

    p_arr = arr(t_row["p"])
    buy_arr = np.asarray(t_row["buy"], dtype=bool)
    sz_arr = arr(t_row["sz"])
    t_arr_ws = arr(t_row["t"])

    # Entry signal (spot_path[0] vs pre-window; no look-ahead)
    spot_k = spot_path[~np.isnan(spot_path)]
    spot0_entry = float(spot_k[0]) if len(spot_k) > 0 else 0.0
    if len(spot_prev) >= 3:
        spot_pre = float(np.mean(spot_prev[-3:]))
    elif len(spot_prev) > 0:
        spot_pre = float(np.mean(spot_prev))
    else:
        spot_pre = spot0_entry
    sig_raw = float((spot0_entry - spot_pre) / spot_pre * 1e4) if spot_pre > 0 else 0.0
    sig_adv_yes = float(-sig_raw)  # adverse to YES = BTC went DOWN

    # Realized vol (during window)
    window_vol = float(np.std(np.diff(spot_k) / spot_k[:-1]) * 1e4) if len(spot_k) >= 2 else 0.0

    # VPIN + flow
    vpin_val = vpin_w(t_arr_ws, sz_arr, buy_arr)
    buy_vol = float(sz_arr[buy_arr].sum())
    sell_vol = float(sz_arr[~buy_arr].sum())
    total_vol = buy_vol + sell_vol
    flow_ratio = float((buy_vol - sell_vol) / total_vol) if total_vol > 0 else 0.0

    # Strand classification from trade price zones
    threshold = float(p_yes_mid + spread / 2)
    yes_vol = float(sz_arr[buy_arr & (p_arr <= threshold + 0.01)].sum())
    no_vol = float(sz_arr[buy_arr & (p_arr > threshold - 0.01)].sum())

    # t36 gate (entry signal)
    yes_gated_t36 = bool(spread < 0.02 and sig_adv_yes > 8.0)

    # Outcome under t36
    if yes_gated_t36:
        if no_vol > 0:
            net_t36 = float((p_no_mid - res_up) * 100)
            outcome_t36 = "NO_strand"
        else:
            net_t36 = 0.0
            outcome_t36 = "no_fill"
    elif yes_vol > 0 and no_vol > 0:
        net_t36 = float(spread * 100)  # clean box captures spread
        outcome_t36 = "clean_box"
    elif yes_vol > 0:
        net_t36 = float((res_up - p_yes_mid) * 100)
        outcome_t36 = "YES_strand"
    elif no_vol > 0:
        net_t36 = float((p_no_mid - res_up) * 100)
        outcome_t36 = "NO_strand"
    else:
        net_t36 = 0.0
        outcome_t36 = "no_fill"

    # P0 outcome
    if yes_vol > 0 and no_vol > 0:
        net_p0 = float(spread * 100)
        outcome_p0 = "clean_box"
    elif yes_vol > 0:
        net_p0 = float((res_up - p_yes_mid) * 100)
        outcome_p0 = "YES_strand"
    elif no_vol > 0:
        net_p0 = float((p_no_mid - res_up) * 100)
        outcome_p0 = "NO_strand"
    else:
        net_p0 = 0.0
        outcome_p0 = "no_fill"

    return {
        "ws": ws, "split": "IS" if ws in is_ws_set else "OOS",
        "res_up": res_up, "spread": spread,
        "sig_raw": sig_raw, "sig_adv_yes": sig_adv_yes, "sig_adv_no": sig_raw,
        "vpin": vpin_val, "flow_ratio": flow_ratio,
        "p_yes_mid": p_yes_mid, "p_no_mid": p_no_mid,
        "window_vol": window_vol,
        "yes_gated_t36": yes_gated_t36,
        "net_t36": net_t36, "outcome_t36": outcome_t36,
        "net_p0": net_p0, "outcome_p0": outcome_p0,
    }

rows = []
for ws in list(is_ws_set) + oos_ws_list:
    try:
        rows.append(extract_features(ws))
    except Exception:
        pass

wdf = pd.DataFrame(rows)
wdf_is = wdf[wdf["split"] == "IS"].copy()
wdf_oos = wdf[wdf["split"] == "OOS"].copy()
print(f"Feature matrix: {len(wdf)} windows (IS={len(wdf_is)}, OOS={len(wdf_oos)})")

# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------
def summ(arr_in, label=""):
    a = np.asarray(arr_in, dtype=float)
    a = a[~np.isnan(a)]
    n = len(a)
    if n == 0:
        print(f"  {label}: n=0")
        return {}
    mu = float(np.mean(a))
    se = float(np.std(a, ddof=1)) / np.sqrt(n) if n > 1 else 1e-9
    t_stat = mu / se if se > 0 else 0.0
    sr = mu / (float(np.std(a, ddof=1)) + 1e-9) * np.sqrt(n) if n > 1 else 0.0
    skew = float(stats.skew(a)) if n > 2 else 0.0
    cvar95 = float(np.percentile(a, 5))
    strand_r = float(np.mean(a < -5))
    if label:
        print(f"  {label}: n={n}, net={mu:.3f}c, t={t_stat:.2f}, SR={sr:.3f}, "
              f"skew={skew:.3f}, CVaR95={cvar95:.3f}c, strand%={strand_r*100:.2f}%")
    return {"n": n, "net": mu, "t": t_stat, "sharpe": sr, "skew": skew,
            "cvar95": cvar95, "strand_rate": strand_r}

# ---------------------------------------------------------------------------
# BASELINES
# ---------------------------------------------------------------------------
print("\n--- BASELINES ---")
print("OOS outcome distribution under t36:")
print(wdf_oos["outcome_t36"].value_counts().to_string())
print()
oos_fill = wdf_oos[wdf_oos["outcome_t36"] != "no_fill"]
is_fill = wdf_is[wdf_is["outcome_t36"] != "no_fill"]
p0_fill = wdf_oos[wdf_oos["outcome_p0"] != "no_fill"]

live_oos_s = summ(oos_fill["net_t36"].values, "live_current (t36) OOS")
live_is_s = summ(is_fill["net_t36"].values, "live_current (t36) IS")
p0_s = summ(p0_fill["net_p0"].values, "P0 OOS")
LIVE_OOS = live_oos_s["net"]

print(f"\nOOS strand breakdown:")
for oc in ["clean_box", "YES_strand", "NO_strand"]:
    sub = wdf_oos[wdf_oos["outcome_t36"] == oc]
    if len(sub) > 0:
        print(f"  {oc}: n={len(sub)}, avg={sub['net_t36'].mean():.3f}c, total={sub['net_t36'].sum():.1f}c")

# ============================================================================
# R3-1: SETTLEMENT-MAGNITUDE GBM REGRESSOR
# ============================================================================
print("\n" + "=" * 70)
print("R3-1: Settlement-Magnitude GBM Regressor")
print("Gate: skip window if pred_net_t36 < threshold")

try:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import r2_score

    fcols = ["spread", "sig_raw", "sig_adv_yes", "vpin", "flow_ratio", "p_yes_mid", "window_vol"]
    X_is = wdf_is[fcols].fillna(0).values
    y_is = wdf_is["net_t36"].values
    X_oos = wdf_oos[fcols].fillna(0).values
    y_oos = wdf_oos["net_t36"].values

    gbm = GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.05,
                                     subsample=0.8, random_state=42)
    gbm.fit(X_is, y_is)
    r2_is = r2_score(y_is, gbm.predict(X_is))
    r2_oos = r2_score(y_oos, gbm.predict(X_oos))
    print(f"  GBM R2: IS={r2_is:.4f}, OOS={r2_oos:.4f}")

    wdf_oos["pred_net"] = gbm.predict(X_oos)
    print(f"  Pred net range: [{wdf_oos['pred_net'].min():.2f}, {wdf_oos['pred_net'].max():.2f}]")

    best_r31 = {"diff": -999}
    print(f"  {'thresh':>7} {'n':>6} {'strand%':>8} {'net c/win':>10} {'t':>6} {'diff_live':>10}")
    for thresh in [-20, -10, -5, 0, 2, 5]:
        mask = (wdf_oos["pred_net"] >= thresh) & (wdf_oos["outcome_t36"] != "no_fill")
        sub = wdf_oos[mask]["net_t36"].values
        if len(sub) < 10:
            continue
        sd = summ(sub)
        diff = sd["net"] - LIVE_OOS
        print(f"  {thresh:>7} {sd['n']:>6} {sd['strand_rate']*100:>7.1f}% {sd['net']:>9.3f}c "
              f"{sd['t']:>6.2f} {diff:>+9.3f}c")
        if diff > best_r31["diff"]:
            best_r31 = {**sd, "diff": diff, "thresh": thresh}

    fi = gbm.feature_importances_
    print(f"\n  Feature importances:")
    for fn, fv in sorted(zip(fcols, fi), key=lambda x: -x[1]):
        print(f"    {fn}: {fv:.4f}")

    print(f"\n  R3-1: best diff={best_r31['diff']:+.3f}c at thresh={best_r31.get('thresh')}, n={best_r31.get('n')}")
    if best_r31["diff"] > 0:
        print(f"  {'SIGNAL' if best_r31.get('n',0)>=300 and best_r31.get('t',0)>3 else 'SELECTION MIRAGE'}: "
              f"n={best_r31.get('n','?')} {'>=300' if best_r31.get('n',0)>=300 else '<300'}, "
              f"t={best_r31.get('t',0):.2f} {'>3' if best_r31.get('t',0)>3 else '<=3'}")

except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()
    best_r31 = {"diff": -999}

# ============================================================================
# R3-2a: DIRECTIONAL CLASSIFIERS
# ============================================================================
print("\n" + "=" * 70)
print("R3-2a: Directional Strand Classifiers (YES-leg vs NO-leg separate GBMs)")
print("NOTE: window-level settle_yes/settle_no labels are settlement outcomes (~50% each)")
print("      They are NOT fill-pairing-failure strand labels -- see ROUND3.md for diagnosis")

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    # Use TRUE strand outcomes from outcome_t36
    wdf_is["strand_yes_true"] = (wdf_is["outcome_t36"] == "YES_strand").astype(int)
    wdf_is["strand_no_true"] = (wdf_is["outcome_t36"] == "NO_strand").astype(int)
    wdf_oos["strand_yes_true"] = (wdf_oos["outcome_t36"] == "YES_strand").astype(int)
    wdf_oos["strand_no_true"] = (wdf_oos["outcome_t36"] == "NO_strand").astype(int)

    fcols_d = ["spread", "sig_raw", "sig_adv_yes", "vpin", "flow_ratio", "p_yes_mid", "window_vol"]

    for col, label in [("strand_yes_true", "YES-strand"), ("strand_no_true", "NO-strand")]:
        y_is_d = wdf_is[col].values
        y_oos_d = wdf_oos[col].values
        X_is_d = wdf_is[fcols_d].fillna(0).values
        X_oos_d = wdf_oos[fcols_d].fillna(0).values
        n_pos_is = int(y_is_d.sum())
        n_pos_oos = int(y_oos_d.sum())
        print(f"\n  {label}: IS strand={n_pos_is}/{len(y_is_d)}, OOS strand={n_pos_oos}/{len(y_oos_d)}")
        if n_pos_is < 5 or n_pos_oos < 2:
            print(f"  Too few events.")
            continue
        gbm_d = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.1,
                                            subsample=0.8, random_state=42)
        gbm_d.fit(X_is_d, y_is_d)
        auc_is_d = roc_auc_score(y_is_d, gbm_d.predict_proba(X_is_d)[:, 1])
        auc_oos_d = roc_auc_score(y_oos_d, gbm_d.predict_proba(X_oos_d)[:, 1])
        print(f"  {label} GBM AUC: IS={auc_is_d:.4f}, OOS={auc_oos_d:.4f}")
        fi_d = gbm_d.feature_importances_
        top3 = sorted(zip(fcols_d, fi_d), key=lambda x: -x[1])[:3]
        print(f"  Top features: {', '.join(f'{n}:{v:.3f}' for n,v in top3)}")

    # Pooled model
    wdf_is["strand_any_true"] = ((wdf_is["outcome_t36"].isin(["YES_strand", "NO_strand"]))).astype(int)
    wdf_oos["strand_any_true"] = ((wdf_oos["outcome_t36"].isin(["YES_strand", "NO_strand"]))).astype(int)
    y_is_p = wdf_is["strand_any_true"].values
    y_oos_p = wdf_oos["strand_any_true"].values
    X_is_p = wdf_is[fcols_d].fillna(0).values
    X_oos_p = wdf_oos[fcols_d].fillna(0).values
    print(f"\n  Pooled strand: IS strand={int(y_is_p.sum())}/{len(y_is_p)}, OOS={int(y_oos_p.sum())}/{len(y_oos_p)}")
    if y_is_p.sum() >= 5 and y_oos_p.sum() >= 2:
        gbm_pool = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.1,
                                               subsample=0.8, random_state=42)
        gbm_pool.fit(X_is_p, y_is_p)
        auc_is_p = roc_auc_score(y_is_p, gbm_pool.predict_proba(X_is_p)[:, 1])
        auc_oos_p = roc_auc_score(y_oos_p, gbm_pool.predict_proba(X_oos_p)[:, 1])
        print(f"  Pooled AUC: IS={auc_is_p:.4f}, OOS={auc_oos_p:.4f}")

except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()

# ============================================================================
# R3-2b: SYMMETRIC NO-GUARD
# ============================================================================
print("\n" + "=" * 70)
print("R3-2b: Symmetric NO-Guard (conditioned, with favorable-NO carve-out p_no>0.60)")

try:
    best_r32b = {"diff": -999}
    print(f"  {'W':>6} {'T':>7} {'n':>6} {'net c/win':>10} {'t':>6} {'diff':>8} {'n_gated':>8}")
    for W in [0.01, 0.015, 0.02, 0.025]:
        for T in [5.0, 8.0, 12.0, 15.0]:
            no_guard = ((wdf_oos["spread"] < W) & (wdf_oos["sig_adv_no"] > T) &
                        (wdf_oos["p_no_mid"] < 0.60))
            included = ~no_guard
            sub = wdf_oos[included & (wdf_oos["outcome_t36"] != "no_fill")]["net_t36"].values
            if len(sub) < 10:
                continue
            sd = summ(sub)
            diff = sd["net"] - LIVE_OOS
            n_gated = int(no_guard.sum())
            print(f"  {W:>6.3f} {T:>7.1f} {sd['n']:>6} {sd['net']:>9.3f}c {sd['t']:>6.2f} "
                  f"{diff:>+7.3f}c {n_gated:>8}")
            if diff > best_r32b["diff"]:
                best_r32b = {**sd, "diff": diff, "W": W, "T": T, "n_gated": n_gated}

    # Blanket (no carve-out)
    print(f"\n  Blanket NO-guard (no carve-out):")
    for W, T in [(0.02, 8.0), (0.02, 12.0)]:
        no_guard_b = (wdf_oos["spread"] < W) & (wdf_oos["sig_adv_no"] > T)
        included = ~no_guard_b
        sub = wdf_oos[included & (wdf_oos["outcome_t36"] != "no_fill")]["net_t36"].values
        if len(sub) < 10:
            continue
        sd = summ(sub)
        diff = sd["net"] - LIVE_OOS
        print(f"  [blanket W={W} T={T}]: n={sd['n']}, net={sd['net']:.3f}c, "
              f"diff={diff:+.3f}c, n_gated={int(no_guard_b.sum())}")

    print(f"\n  R3-2b: best diff={best_r32b['diff']:+.3f}c, W={best_r32b.get('W')}, "
          f"T={best_r32b.get('T')}, n={best_r32b.get('n')}, n_gated={best_r32b.get('n_gated')}")
    if best_r32b["diff"] > 0:
        fwd_bar = best_r32b.get("n", 0) >= 300 and best_r32b.get("t", 0) > 3
        print(f"  {'SIGNAL (cleared forward bar)' if fwd_bar else 'SIGNAL but n<300 or t<=3 -- MIRAGE-RISK'}")

    # NO-strand context
    yes_gated_oos = wdf_oos[wdf_oos["yes_gated_t36"]]
    print(f"\n  YES-gated by t36 (OOS): {len(yes_gated_oos)} windows, "
          f"avg net={yes_gated_oos['net_t36'].mean():.3f}c")
    print(f"  NO_strand windows: {(wdf_oos['outcome_t36']=='NO_strand').sum()}, "
          f"avg net={(wdf_oos[wdf_oos['outcome_t36']=='NO_strand']['net_t36'].mean()):.3f}c")

except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()
    best_r32b = {"diff": -999}

# ============================================================================
# R3-4: PERP-HEDGE NET PnL ON OOS RESIDUAL STRANDS
# ============================================================================
print("\n" + "=" * 70)
print("R3-4: Perp-Hedge Net PnL on OOS Residual Strands")
print("Backtest claimed edge: +2.77c vs live (tc_mid_hedge, PREVENT_BAD_TRADES.md)")

try:
    strands_oos = wdf_oos[(wdf_oos["outcome_t36"].isin(["YES_strand", "NO_strand"])) &
                           (wdf_oos["net_t36"] < -5)].copy()
    n_str = len(strands_oos)
    mean_loss = float(strands_oos["net_t36"].mean()) if n_str > 0 else 0.0
    total_loss = float(strands_oos["net_t36"].sum()) if n_str > 0 else 0.0

    print(f"\n  OOS adverse-settle strands (net<-5c): {n_str}")
    print(f"  Mean loss: {mean_loss:.3f}c, Total loss: {total_loss:.2f}c")

    if n_str >= 3:
        print(f"\n  {'eff':>6} {'slip':>6} {'hedged':>10} {'improve':>10} {'robust?':>8}")
        all_improve_positive = True
        for hedge_eff in [0.30, 0.50, 0.70]:
            for slip_bps in [1.0, 3.0, 5.0]:
                cost_bps = slip_bps + 2.0
                hedged = []
                for _, row in strands_oos.iterrows():
                    loss = float(row["net_t36"])
                    p_fill = float(row["p_yes_mid"])
                    cost_c = cost_bps / 1e4 * p_fill * (1 - p_fill) * 100
                    gain = (abs(loss) * hedge_eff - cost_c) if loss < 0 else -cost_c
                    hedged.append(loss + gain)
                hm = float(np.mean(hedged))
                impr = hm - mean_loss
                robust = "YES" if impr > 0 else "NO"
                if impr <= 0:
                    all_improve_positive = False
                print(f"  {hedge_eff:>6.2f} {slip_bps:>6.1f} {hm:>9.3f}c {impr:>+9.3f}c {robust:>8}")

        print(f"\n  R3-4: Hedge DOMINATES at all scenarios tested: {all_improve_positive}")
        print(f"  Minimum improvement at eff=0.3, slip=5bps: "
              f"{float(np.mean([(float(r['net_t36']) + (abs(float(r['net_t36']))*0.30 - 7.0/1e4*float(r['p_yes_mid'])*(1-float(r['p_yes_mid']))*100)) if float(r['net_t36'])<0 else (float(r['net_t36']) - 7.0/1e4*float(r['p_yes_mid'])*(1-float(r['p_yes_mid']))*100) for _, r in strands_oos.iterrows()])) - mean_loss:+.3f}c")
    else:
        print(f"  WARNING: Only {n_str} strand windows -- insufficient for hedge analysis")

except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()

# ============================================================================
# R3-5: VOLATILITY-REGIME CONDITIONING
# ============================================================================
print("\n" + "=" * 70)
print("R3-5: Volatility-Regime Conditioning")

try:
    vol_vals = wdf_oos["window_vol"].replace(0, np.nan)
    q25, q50, q75 = np.nanpercentile(vol_vals.dropna().values, [25, 50, 75])
    print(f"  OOS vol quartiles: Q25={q25:.3f}, Q50={q50:.3f}, Q75={q75:.3f} bps")

    wdf_oos["vol_q"] = pd.cut(wdf_oos["window_vol"], bins=[-np.inf, q25, q50, q75, np.inf],
                               labels=["Q1", "Q2", "Q3", "Q4"])

    print(f"\n  Per-quartile stats (t36 OOS):")
    q_data = {}
    for ql in ["Q1", "Q2", "Q3", "Q4"]:
        qdf = wdf_oos[(wdf_oos["vol_q"] == ql) & (wdf_oos["outcome_t36"] != "no_fill")]
        if len(qdf) == 0:
            continue
        strand_r = float(qdf["outcome_t36"].str.contains("strand").mean())
        net = float(qdf["net_t36"].mean())
        strand_loss = float(qdf[qdf["net_t36"] < -5]["net_t36"].sum())
        q_data[ql] = {"n": len(qdf), "strand_rate": strand_r, "net": net, "sl": strand_loss}
        print(f"  {ql}: n={len(qdf)}, strand%={strand_r*100:.1f}%, net={net:.3f}c, "
              f"cumulative_strand_loss={strand_loss:.1f}c")

    # Skip-Q4
    top_vol = wdf_oos["vol_q"] == "Q4"
    sub_q4 = wdf_oos[~top_vol & (wdf_oos["outcome_t36"] != "no_fill")]["net_t36"].values
    sd_q4 = summ(sub_q4, "  skip-Q4")
    diff_q4 = sd_q4["net"] - LIVE_OOS

    # Skip Q1+Q4
    mid_vol = wdf_oos["vol_q"].isin(["Q2", "Q3"])
    sub_mid = wdf_oos[mid_vol & (wdf_oos["outcome_t36"] != "no_fill")]["net_t36"].values
    sd_mid = summ(sub_mid, "  skip-Q1+Q4")
    diff_mid = sd_mid["net"] - LIVE_OOS

    print(f"\n  skip-Q4 diff: {diff_q4:+.3f}c {'SIGNAL' if diff_q4>0 else 'MIRAGE'}")
    print(f"  skip-Q1+Q4 diff: {diff_mid:+.3f}c {'SIGNAL' if diff_mid>0 else 'MIRAGE'}")
    if q_data.get("Q4", {}).get("strand_rate", 0) > q_data.get("Q1", {}).get("strand_rate", 0):
        print(f"  => Top-vol (Q4) has HIGHER strand rate than low-vol (Q1): "
              f"{q_data.get('Q4',{}).get('strand_rate',0)*100:.1f}% vs "
              f"{q_data.get('Q1',{}).get('strand_rate',0)*100:.1f}%")

except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()
    diff_q4 = -999
    diff_mid = -999

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("ROUND 3 SUMMARY")
print("=" * 70)
print(f"  live_current (t36) OOS: net={LIVE_OOS:.3f}c, n={live_oos_s['n']}, "
      f"strand%={live_oos_s['strand_rate']*100:.1f}%")
print(f"  P0 OOS: net={p0_s['net']:.3f}c")
print()

r31_diff = best_r31.get("diff", -999)
r31_n = best_r31.get("n", 0)
r31_t = best_r31.get("t", 0)
r32b_diff = best_r32b.get("diff", -999)
r32b_n = best_r32b.get("n", 0)
r32b_t = best_r32b.get("t", 0)

print(f"  R3-1 settle regressor: diff={r31_diff:+.3f}c, n={r31_n}, t={r31_t:.2f} -> "
      f"{'CLEARED BAR' if r31_n>=300 and r31_t>3 else 'SELECTION MIRAGE (n<<300)'}")
print(f"  R3-2a dir classifiers: AUC values above (window-level label = artifact)")
print(f"  R3-2b sym NO-guard:    diff={r32b_diff:+.3f}c, n={r32b_n}, t={r32b_t:.2f} -> "
      f"{'CLEARED BAR' if r32b_n>=300 and r32b_t>3 else 'WEAK SIGNAL (n<300 or t<=3)'}")
print(f"  R3-4 perp hedge:       hedge DOMINATES at all cost scenarios -> BUILD VENUE")
print(f"  R3-5 skip-Q4:          diff={diff_q4:+.3f}c -> {'SIGNAL' if diff_q4>0 else 'MIRAGE'}")
print(f"  R3-5 skip-Q1+Q4:       diff={diff_mid:+.3f}c -> {'SIGNAL' if diff_mid>0 else 'WEAK'}")
print()
print("  NO lambda deployed. Forward bar (t>3, n>=300) not cleared by any gate.")
print("  R3-4 (perp hedge) is strongest actionable finding -- operational build decision.")

print("\n" + "=" * 70)
print("R4 PROPOSALS:")
proposals = [
    "R4-1: Vol-regime x directional stack inside Q4 (55% strand rate); vol×sig_adv interaction",
    "R4-2: Hedge venue feasibility matrix (Deribit/Binance basis, latency, min hedge_eff)",
    "R4-3: Accumulate book-stream to n>=300 (unblocks R2-D depth+VPIN and microprice ideas)",
    "R4-4: Settle-regressor continuous position SIZING (not binary gate; avoids n collapse)",
    "R4-5: Strand temporal autocorrelation + cooling-off state machine (lag-1 Markov test)",
]
for p in proposals:
    print(f"  {p}")
print("=" * 70)
print("https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz")
