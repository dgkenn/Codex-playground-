"""low_risk_sleeves_study.py -- Low-risk sleeve identification backtest (final version).

Objective: find policies with HIGH Sharpe/Sortino, POSITIVE skew, LOW CVaR95/Ulcer/maxDD
even if absolute mean is modest. Five sleeve families:
  1. ULTRA-SELECTIVE ENTRY (balanced flow + tight spread + tilt-zone + k-timing)
  2. FAVORITE-ONLY high-prob boxes (t29 family, various thresholds)
  3. SETTLEMENT-SAFE (early-k + near-settled price = low remaining variance)
  4. COMPLETE-ALL + selective entry combos (tc_pairmax family variants)
  5. POSITIVE-SKEW CONSTRUCTIONS (cap losses via complete-all + selective entry)

IS = first 60%, OOS = last 40% (time-ordered).
Metrics: Sharpe, Sortino, skew, CVaR95, Ulcer, maxDD, mean c/win, #windows.
Baselines: P0 (always-pair), live_current (t36 guarded-opener = deployed strategy).
"""
from __future__ import annotations
import os, sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

os.chdir("/tmp/ls2")
sys.path.insert(0, "/tmp/ls2")

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------
def arr(x): return np.asarray(x, float)

def _clean(x):
    x = np.asarray(x, float)
    return x[~np.isnan(x)]

def sharpe(x):
    x = _clean(x)
    if len(x) < 8 or x.std(ddof=1) == 0: return float("nan")
    return float(x.mean() / x.std(ddof=1))

def sortino(x):
    x = _clean(x)
    if len(x) < 8: return float("nan")
    dn = x[x < 0]
    dd = float(np.sqrt(np.mean(dn**2))) if len(dn) else 0.0
    return (float(x.mean()) / dd) if dd > 1e-12 else (float("inf") if x.mean() > 0 else 0.0)

def skewness(x):
    x = _clean(x)
    if len(x) < 8: return float("nan")
    n = len(x); mu = x.mean(); sig = x.std(ddof=1)
    if sig < 1e-12: return 0.0
    return float(n / ((n-1)*(n-2)) * np.sum(((x-mu)/sig)**3))

def cvar95(x):
    x = _clean(x)
    if len(x) < 8: return float("nan")
    cut = np.percentile(x, 5)
    tail = x[x <= cut]
    return float(-np.mean(tail)) if len(tail) else float(-cut)

def ulcer(x):
    x = _clean(x)
    if len(x) < 2: return float("nan")
    cum = np.cumsum(x)
    peak = np.maximum.accumulate(cum)
    return float(np.sqrt(np.mean((peak - cum)**2)))

def maxdd(x):
    x = _clean(x)
    cum = np.cumsum(x)
    return float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0

def tstat_fn(x):
    x = _clean(x)
    if len(x) < 8 or x.std(ddof=1) == 0: return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))

def profile(pnl_all, name, n_traded, n_total, live_pnl=None):
    """pnl_all: per-window PnL (zeros for untraded windows)."""
    # Only scored windows (non-zero) for metric computation
    x = np.array(pnl_all, dtype=float)
    x_traded = x[x != 0.0]
    return {
        "name": name,
        "n_total": n_total,
        "n_traded": n_traded,
        "pct": 100.0 * n_traded / n_total if n_total else 0.0,
        "mean_c": float(np.mean(x_traded)) * 100 if len(x_traded) else 0.0,
        "sharpe": sharpe(x_traded),
        "sortino": sortino(x_traded),
        "skew": skewness(x_traded),
        "cvar95_c": cvar95(x_traded) * 100,
        "ulcer_c": ulcer(x_traded) * 100,
        "maxdd_c": maxdd(x_traded) * 100,
        "tstat": tstat_fn(x_traded),
        "diff_live_c": float(np.mean(x - (live_pnl if live_pnl is not None else x))) * 100 if live_pnl is not None else float("nan"),
        "diff_t": tstat_fn(x - live_pnl) if live_pnl is not None else float("nan"),
    }

def pp(d):
    print(f"  n={d['n_traded']}/{d['n_total']} ({d['pct']:.0f}%)  "
          f"mean={d['mean_c']:+.3f}c  Sh={d['sharpe']:+.3f}  So={d['sortino']:+.3f}  "
          f"skew={d['skew']:+.3f}  CVaR95={d['cvar95_c']:.3f}c  "
          f"Ulcer={d['ulcer_c']:.3f}c  maxDD={d['maxdd_c']:.3f}c  t={d['tstat']:+.3f}")
    if not np.isnan(d["diff_live_c"]):
        print(f"  diff_vs_live={d['diff_live_c']:+.3f}c  diff_t={d['diff_t']:+.3f}")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
print("Loading parquet data...", flush=True)
h = pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
t = pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")
common = sorted(set(h.index) & set(t.index))
n = len(common)
cut = int(n * 0.6)
is_ws_set = set(common[:cut])
oos_ws_set = set(common[cut:])
is_list = [ws for ws in common if ws in is_ws_set]
oos_list = [ws for ws in common if ws in oos_ws_set]
print(f"Windows: {n}  IS={cut}  OOS={n-cut}", flush=True)

# ---------------------------------------------------------------------------
# Per-window fill reconstruction (same-minute clean-box logic with full features)
# Produces a list of fill dicts per window.
# Fields: side, settle, exit, p, spread, k, tau, flow, sig, spot, p_yeq
# ---------------------------------------------------------------------------
print("Reconstructing fills...", flush=True)

def reconstruct_fills(ws, h_row, t_row):
    """Reconstruct fill dicts from parquet data.
    Returns list of fills, each with all fields needed by sleeve gate functions.
    Computed on the same same-minute clean-box pairing logic as multi_asset_study."""
    bid = arr(h_row["bid_path"])
    ask = arr(h_row["ask_path"])
    res = int(h_row["res_up"])
    spot_path = arr(h_row["spot_path"]) if "spot_path" in h_row.index else np.full(15, np.nan)
    t_arr = arr(t_row["t"])
    p_arr = arr(t_row["p"])
    sz_arr = arr(t_row["sz"])
    buy_arr = arr(t_row["buy"]).astype(bool)

    fills = []
    for k in range(2, 13):
        b0, a0 = bid[k], ask[k]
        if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
            continue
        spread = round(a0 - b0, 4)
        tau = (15 - k) / 15.0
        # Spot signal: 3-min price move (bps) prior to this minute
        s_now = spot_path[k] if k < len(spot_path) else np.nan
        s_then = spot_path[max(k-3, 0)] if max(k-3, 0) < len(spot_path) else np.nan
        if s_now > 0 and s_then > 0 and not (np.isnan(s_now) or np.isnan(s_then)):
            sig_bps = (s_now / s_then - 1.0) * 1e4
        else:
            sig_bps = 0.0
        # Prior-minute taker flow imbalance
        pl, ph = ws + 60 * (k - 1), ws + 60 * k
        j0, j1 = np.searchsorted(t_arr, pl), np.searchsorted(t_arr, ph)
        flow = float(np.sum(np.where(buy_arr[j0:j1], sz_arr[j0:j1], -sz_arr[j0:j1])))
        # Exit value at k+1 (sell/complete at next minute's touch)
        b1 = bid[k+1] if k+1 < 15 and not np.isnan(bid[k+1]) else b0
        a1 = ask[k+1] if k+1 < 15 and not np.isnan(ask[k+1]) else a0
        mid1 = (b1 + a1) / 2.0; sp1 = a1 - b1
        exit_bid = (mid1 - sp1 / 2.0) - b0    # sell YES at next bid
        exit_ask = a0 - (mid1 + sp1 / 2.0)    # buy YES back at next ask (flatten NO)
        # Spot at settlement (last valid spot)
        valid_spots = spot_path[~np.isnan(spot_path)]
        sset = float(valid_spots[-1]) if len(valid_spots) else np.nan
        # Fill window: next minute trades
        lo = ws + 60 * (k + 1); hi = ws + 60 * (k + 2)
        i0, i1 = int(np.searchsorted(t_arr, lo)), int(np.searchsorted(t_arr, hi))
        got_b = got_a = False
        b_sz = a_sz = 1.0
        for i in range(i0, i1):
            p = float(p_arr[i]); buy = bool(buy_arr[i]); sz = float(sz_arr[i])
            if not got_b and not buy and p <= b0 + 1e-9:
                b_sz = sz; got_b = True
            if not got_a and buy and p >= a0 - 1e-9:
                a_sz = sz; got_a = True
            if got_b and got_a:
                break
        p_yeq_bid = b0  # YES-equiv price for bid fill
        p_yeq_ask = round(1.0 - a0, 4)  # YES-equiv price for ask fill
        if got_b:
            fills.append({
                "ws": ws, "side": "bid", "settle": res - b0, "exit": exit_bid,
                "sig": sig_bps, "p": b0, "p_yeq": b0, "spread": spread,
                "k": k, "tau": tau, "flow": flow, "tksize": b_sz,
                "depth": None, "oi": None, "vpin": None,
                "spot": float(s_now) if not np.isnan(s_now) else None,
                "sset": sset, "paired": got_a,  # whether the other leg also filled
            })
        if got_a:
            fills.append({
                "ws": ws, "side": "ask", "settle": a0 - res, "exit": exit_ask,
                "sig": -sig_bps, "p": p_yeq_ask, "p_yeq": p_yeq_ask, "spread": spread,
                "k": k, "tau": tau, "flow": -flow, "tksize": a_sz,
                "depth": None, "oi": None, "vpin": None,
                "spot": float(s_now) if not np.isnan(s_now) else None,
                "sset": sset, "paired": got_b,
            })
    return fills

all_fills = {}
for ws in common:
    all_fills[ws] = reconstruct_fills(ws, h.loc[ws], t.loc[ws])

filled_windows = sum(1 for f in all_fills.values() if len(f) > 0)
print(f"Fills reconstructed: {filled_windows} windows with fills", flush=True)

# ---------------------------------------------------------------------------
# Gate helpers
# ---------------------------------------------------------------------------
def fav_cost(f):
    """Leg's own cost (p_yeq for both sides)."""
    return f.get("p_yeq", f["p"]) if f["side"] == "bid" else (1.0 - f["p"])


# Tox proxy: high-flow + high-spread = adverse fill (simplified without VPIN)
def tox_simple(f):
    """Simple toxicity proxy: flow adverse and spread wide."""
    flow_adv = abs(f.get("flow") or 0.0) / 1000.0
    spread = f.get("spread", 0.03)
    sig = abs(f.get("sig") or 0.0) / 100.0
    return 0.2 + 0.3 * flow_adv + 2.0 * spread + 0.1 * sig

# ---------------------------------------------------------------------------
# Policy walkers
# ---------------------------------------------------------------------------
def walk_always_pair(fills):
    """P0: always pair. Per-window PnL."""
    net = 0; pnl = 0.0; held = None
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1: continue
        net = nn; pnl += f["settle"]
        if net == 0: held = None
        elif held is None: held = f
    return pnl

def walk_gate(fills, open_ok):
    """Always-pair with entry gate."""
    net = 0; pnl = 0.0; held = None
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1: continue
        pairing = (net != 0 and abs(nn) < abs(net))
        if not pairing and not open_ok(f):
            continue
        net = nn; pnl += f["settle"]
        if net == 0: held = None
        elif held is None: held = f
    return pnl

def walk_complete_all(fills, open_ok=None):
    """Gate + complete-all: orphaned leg is sold at exit value instead of held to settlement."""
    net = 0; pnl = 0.0; held = None
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1: continue
        pairing = (net != 0 and abs(nn) < abs(net))
        if not pairing and open_ok is not None and not open_ok(f):
            continue
        net = nn; pnl += f["settle"]
        if net == 0: held = None
        elif held is None: held = f
    # Orphaned leg: sell at exit value
    if held is not None:
        pnl -= held["settle"]   # undo settlement value
        pnl += held["exit"]     # use exit (sell-back) value instead
    return pnl

def walk_sell_cheap_orphan(fills, cheap_below=0.30, open_ok=None):
    """Sell orphaned leg only if price < cheap_below."""
    net = 0; pnl = 0.0; held = None
    for f in fills:
        step = 1 if f["side"] == "bid" else -1
        nn = net + step
        if abs(nn) > 1: continue
        pairing = (net != 0 and abs(nn) < abs(net))
        if not pairing and open_ok is not None and not open_ok(f):
            continue
        net = nn; pnl += f["settle"]
        if net == 0: held = None
        elif held is None: held = f
    if held is not None:
        if held.get("p", 1.0) < cheap_below:
            pnl -= held["settle"]
            pnl += held["exit"]
    return pnl

# ---------------------------------------------------------------------------
# Evaluation engine
# ---------------------------------------------------------------------------
def eval_sleeve(name, policy_fn, is_list, oos_list, live_is_pnl, live_oos_pnl):
    pnl_is = np.array([policy_fn(all_fills.get(ws, [])) for ws in is_list])
    pnl_oos = np.array([policy_fn(all_fills.get(ws, [])) for ws in oos_list])
    trd_is = int(np.sum(pnl_is != 0))
    trd_oos = int(np.sum(pnl_oos != 0))
    pi = profile(pnl_is, f"{name}_IS", trd_is, len(is_list), live_is_pnl)
    po = profile(pnl_oos, f"{name}_OOS", trd_oos, len(oos_list), live_oos_pnl)
    return pi, po, pnl_is, pnl_oos

# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------
print("\nComputing baselines...", flush=True)

p0_pnl_is = np.array([walk_always_pair(all_fills.get(ws, [])) for ws in is_list])
p0_pnl_oos = np.array([walk_always_pair(all_fills.get(ws, [])) for ws in oos_list])

live_fn = lambda F: walk_gate(F, open_ok=lambda f:
    not (f["side"] == "bid" and f["spread"] < 0.02)
    and not ((f.get("sig") or 0.0) > 8.0 and f["spread"] < 0.02))
live_pnl_is = np.array([live_fn(all_fills.get(ws, [])) for ws in is_list])
live_pnl_oos = np.array([live_fn(all_fills.get(ws, [])) for ws in oos_list])

p0_is = profile(p0_pnl_is, "P0_IS", int(np.sum(p0_pnl_is != 0)), len(is_list))
p0_oos = profile(p0_pnl_oos, "P0_OOS", int(np.sum(p0_pnl_oos != 0)), len(oos_list))
lc_is = profile(live_pnl_is, "live_IS", int(np.sum(live_pnl_is != 0)), len(is_list))
lc_oos = profile(live_pnl_oos, "live_OOS", int(np.sum(live_pnl_oos != 0)), len(oos_list))

# tc_pairmax reference
tc_fn = lambda F: walk_complete_all(F, open_ok=lambda f:
    f["k"] <= 9 and f["spread"] <= 0.03
    and (f["flow"] is None or abs(f["flow"]) < 250))
tc_pnl_is = np.array([tc_fn(all_fills.get(ws, [])) for ws in is_list])
tc_pnl_oos = np.array([tc_fn(all_fills.get(ws, [])) for ws in oos_list])
tc_is = profile(tc_pnl_is, "tc_pairmax_IS", int(np.sum(tc_pnl_is != 0)), len(is_list), live_pnl_is)
tc_oos = profile(tc_pnl_oos, "tc_pairmax_OOS", int(np.sum(tc_pnl_oos != 0)), len(oos_list), live_pnl_oos)

print("\n=== BASELINES ===")
print("P0 IS:"); pp(p0_is)
print("P0 OOS:"); pp(p0_oos)
print("live_current IS:"); pp(lc_is)
print("live_current OOS:"); pp(lc_oos)
print("tc_pairmax IS:"); pp(tc_is)
print("tc_pairmax OOS:"); pp(tc_oos)

# ---------------------------------------------------------------------------
# Master policy sweep
# ---------------------------------------------------------------------------
policies = {}

# --- FAMILY 1: ULTRA-SELECTIVE ENTRY ---
policies["f1_flow250"] = lambda F: walk_gate(F,
    lambda f: (f["flow"] is None or abs(f["flow"]) < 250))
policies["f1_flow100"] = lambda F: walk_gate(F,
    lambda f: (f["flow"] is None or abs(f["flow"]) < 100))
policies["f1_spread2c"] = lambda F: walk_gate(F,
    lambda f: f["spread"] <= 0.02)
policies["f1_spread1c"] = lambda F: walk_gate(F,
    lambda f: f["spread"] <= 0.01)
policies["f1_flow_spread"] = lambda F: walk_gate(F,
    lambda f: (f["flow"] is None or abs(f["flow"]) < 250) and f["spread"] <= 0.02)
policies["f1_flow_spread_k9"] = lambda F: walk_gate(F,
    lambda f: (f["flow"] is None or abs(f["flow"]) < 250) and f["spread"] <= 0.02 and f["k"] <= 9)
policies["f1_full_ultra"] = lambda F: walk_gate(F,
    lambda f: (f["flow"] is None or abs(f["flow"]) < 250) and f["spread"] <= 0.02
    and f["k"] <= 9 and abs(f["p"] - 0.5) > 0.10)
policies["f1_ultra_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: (f["flow"] is None or abs(f["flow"]) < 250) and f["spread"] <= 0.02
    and f["k"] <= 9)
policies["f1_strictest"] = lambda F: walk_gate(F,
    lambda f: (f["flow"] is None or abs(f["flow"]) < 150) and f["spread"] <= 0.01
    and f["k"] <= 8 and abs(f["p"] - 0.5) > 0.15)

# --- FAMILY 2: FAVORITE-ONLY HIGH-PROB BOXES ---
for thr in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]:
    policies[f"f2_fav{int(thr*100)}"] = (lambda t: lambda F: walk_gate(F,
        lambda f: fav_cost(f) >= t))(thr)
    policies[f"f2_fav{int(thr*100)}_complete"] = (lambda t: lambda F: walk_complete_all(F,
        open_ok=lambda f: fav_cost(f) >= t))(thr)
# Fav + tight spread
policies["f2_fav45_sp2"] = lambda F: walk_gate(F,
    lambda f: fav_cost(f) >= 0.45 and f["spread"] <= 0.02)
policies["f2_fav50_sp2"] = lambda F: walk_gate(F,
    lambda f: fav_cost(f) >= 0.50 and f["spread"] <= 0.02)
policies["f2_fav45_sp2_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: fav_cost(f) >= 0.45 and f["spread"] <= 0.02)
# Fav + balanced flow
policies["f2_fav45_flow"] = lambda F: walk_gate(F,
    lambda f: fav_cost(f) >= 0.45 and (f["flow"] is None or abs(f["flow"]) < 250))
# Fav + k timing
policies["f2_fav45_k9"] = lambda F: walk_gate(F,
    lambda f: fav_cost(f) >= 0.45 and f["k"] <= 9)
policies["f2_fav45_k9_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: fav_cost(f) >= 0.45 and f["k"] <= 9)

# --- FAMILY 3: SETTLEMENT-SAFE / LOW-VARIANCE ---
policies["f3_k4"] = lambda F: walk_gate(F, lambda f: f["k"] <= 4)
policies["f3_k5"] = lambda F: walk_gate(F, lambda f: f["k"] <= 5)
policies["f3_k6"] = lambda F: walk_gate(F, lambda f: f["k"] <= 6)
policies["f3_k4_complete"] = lambda F: walk_complete_all(F, open_ok=lambda f: f["k"] <= 4)
policies["f3_k5_complete"] = lambda F: walk_complete_all(F, open_ok=lambda f: f["k"] <= 5)
# Near-settled price = binary resolved early
policies["f3_near70"] = lambda F: walk_gate(F, lambda f: abs(f["p"] - 0.5) >= 0.20)
policies["f3_near80"] = lambda F: walk_gate(F, lambda f: abs(f["p"] - 0.5) >= 0.30)
policies["f3_near70_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: abs(f["p"] - 0.5) >= 0.20)
# Near-settled + early k
policies["f3_near70_k6"] = lambda F: walk_gate(F,
    lambda f: abs(f["p"] - 0.5) >= 0.20 and f["k"] <= 6)
policies["f3_near70_k6_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: abs(f["p"] - 0.5) >= 0.20 and f["k"] <= 6)
# Early k + tight spread (low-vol windows)
policies["f3_k4_sp2"] = lambda F: walk_gate(F,
    lambda f: f["k"] <= 4 and f["spread"] <= 0.02)
policies["f3_k6_sp2"] = lambda F: walk_gate(F,
    lambda f: f["k"] <= 6 and f["spread"] <= 0.02)
policies["f3_k6_sp2_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["k"] <= 6 and f["spread"] <= 0.02)

# --- FAMILY 4: COMPLETE-ALL + tc_pairmax VARIANTS ---
policies["f4_tc_orig"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["k"] <= 9 and f["spread"] <= 0.03
    and (f["flow"] is None or abs(f["flow"]) < 250))
policies["f4_tc_k7"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["k"] <= 7 and f["spread"] <= 0.03
    and (f["flow"] is None or abs(f["flow"]) < 250))
policies["f4_tc_sp2"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["k"] <= 9 and f["spread"] <= 0.02
    and (f["flow"] is None or abs(f["flow"]) < 250))
policies["f4_tc_sp2_k7"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["k"] <= 7 and f["spread"] <= 0.02
    and (f["flow"] is None or abs(f["flow"]) < 250))
policies["f4_tc_flow150"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["k"] <= 9 and f["spread"] <= 0.03
    and (f["flow"] is None or abs(f["flow"]) < 150))
policies["f4_tc_tilt"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["k"] <= 9 and f["spread"] <= 0.03
    and (f["flow"] is None or abs(f["flow"]) < 250) and abs(f["p"] - 0.5) > 0.10)
policies["f4_tc_fav45"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: fav_cost(f) >= 0.45 and f["spread"] <= 0.03
    and (f["flow"] is None or abs(f["flow"]) < 250))
policies["f4_tc_fav45_k9"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: fav_cost(f) >= 0.45 and f["k"] <= 9 and f["spread"] <= 0.03)
# Complete-all + guarded-opener
policies["f4_guarded_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f:
    not (f["side"] == "bid" and f["spread"] < 0.02)
    and not ((f.get("sig") or 0.0) > 8.0 and f["spread"] < 0.02))
# Complete-all + NO-only (asymmetry)
policies["f4_no_only_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["side"] == "ask")
# Complete-all, all windows (no gate)
policies["f4_complete_all_nogate"] = lambda F: walk_complete_all(F)

# --- FAMILY 5: POSITIVE-SKEW / LOSS-CAPPING ---
# Sell cheap orphans (reduce left tail on longshot strands)
policies["f5_sell_cheap30"] = lambda F: walk_sell_cheap_orphan(F, cheap_below=0.30)
policies["f5_sell_cheap40"] = lambda F: walk_sell_cheap_orphan(F, cheap_below=0.40)
# Low-signal (spot quiet = low adverse selection)
policies["f5_lowsig5"] = lambda F: walk_gate(F,
    lambda f: abs(f.get("sig") or 0.0) <= 5.0)
policies["f5_lowsig3"] = lambda F: walk_gate(F,
    lambda f: abs(f.get("sig") or 0.0) <= 3.0)
# Low-signal + complete
policies["f5_lowsig5_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: abs(f.get("sig") or 0.0) <= 5.0)
# Fav + low-sig + complete (the "barbell" construction)
policies["f5_fav_lowsig_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: fav_cost(f) >= 0.50 and abs(f.get("sig") or 0.0) <= 5.0)
# Tight spread + low-sig + complete
policies["f5_sp2_lowsig_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["spread"] <= 0.02 and abs(f.get("sig") or 0.0) <= 5.0)
# Near-settled + fav + complete
policies["f5_near70_fav_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: abs(f["p"] - 0.5) >= 0.20 and fav_cost(f) >= 0.50)
# Ultra-low flow (near-zero imbalance = most balanced market)
policies["f5_flow50_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["flow"] is None or abs(f["flow"]) < 50)
# k4-5 mid-window (from SELECTION_DECONSTRUCTION.md)
policies["f5_k45"] = lambda F: walk_gate(F,
    lambda f: f["k"] in (4, 5))
policies["f5_k45_complete"] = lambda F: walk_complete_all(F,
    open_ok=lambda f: f["k"] in (4, 5))
# k8 (K_WINDOW_ALTERNATIVES.md best slot)
policies["f5_k8"] = lambda F: walk_gate(F, lambda f: f["k"] == 8)
policies["f5_k8_complete"] = lambda F: walk_complete_all(F, open_ok=lambda f: f["k"] == 8)

# ---------------------------------------------------------------------------
# Run all policies
# ---------------------------------------------------------------------------
print("\nRunning all sleeve families...", flush=True)
all_results = {}

# Add baselines
all_results["P0"] = (p0_is, p0_oos, p0_pnl_is, p0_pnl_oos)
all_results["live_current"] = (lc_is, lc_oos, live_pnl_is, live_pnl_oos)
all_results["tc_pairmax_ref"] = (tc_is, tc_oos, tc_pnl_is, tc_pnl_oos)

for name, fn in policies.items():
    pi, po, pis, pos = eval_sleeve(name, fn, is_list, oos_list, live_pnl_is, live_pnl_oos)
    all_results[name] = (pi, po, pis, pos)
    print(f"\n{name}:")
    print("  IS:"); pp(pi)
    print("  OOS:"); pp(po)

# ---------------------------------------------------------------------------
# RANKING TABLE
# ---------------------------------------------------------------------------
print("\n\n" + "="*80)
print("RANKING: OOS positive-skew composite score  (Sharpe + 0.5*max(skew,0) - 0.03*CVaR95)")
print("="*80)
print(f"{'Name':<30} {'IS_Sh':>6} {'OOS_Sh':>7} {'OOS_So':>7} {'OOS_sk':>8} "
      f"{'CVaR':>7} {'Ulcer':>7} {'maxDD':>8} {'n_oos':>6} {'%trd':>5} {'diff_t':>7}")
print("-"*100)

scored = []
for name, (pi, po, pis, pos) in all_results.items():
    oos_sh = po["sharpe"]; oos_sk = po["skew"]
    if np.isnan(oos_sh) or np.isnan(oos_sk): continue
    if po["n_traded"] < 5: continue
    score = oos_sh + 0.5 * max(oos_sk, 0) - 0.03 * po["cvar95_c"]
    scored.append((score, name, pi, po))
scored.sort(reverse=True)

for score, name, pi, po in scored[:30]:
    dt = po.get("diff_t", float("nan"))
    print(f"{name:<30} {pi['sharpe']:>+6.3f} {po['sharpe']:>+7.3f} {po['sortino']:>+7.3f} "
          f"{po['skew']:>+8.3f} {po['cvar95_c']:>7.3f} {po['ulcer_c']:>7.3f} "
          f"{po['maxdd_c']:>8.3f} {po['n_traded']:>6} {po['pct']:>4.0f}% "
          f"{dt:>+7.3f}")

# ---------------------------------------------------------------------------
# ROBUSTNESS CHECK
# ---------------------------------------------------------------------------
print("\n\nROBUSTNESS (IS-only mirages: big IS->OOS Sharpe drop, skew flips negative OOS)")
print(f"{'Name':<30} {'IS_Sh':>7} {'OOS_Sh':>8} {'drop':>6} {'IS_sk':>7} {'OOS_sk':>8} "
      f"{'VERDICT':>10}")
print("-"*82)
for score, name, pi, po in scored[:30]:
    drop = po["sharpe"] - pi["sharpe"]
    if po["sharpe"] > 0 and po["skew"] > 0 and pi["sharpe"] > 0:
        verdict = "ROBUST+"
    elif po["sharpe"] > 0 and pi["sharpe"] > 0:
        verdict = "ROBUST"
    elif po["sharpe"] > 0:
        verdict = "OOS_only?"
    else:
        verdict = "mirage"
    print(f"{name:<30} {pi['sharpe']:>+7.3f} {po['sharpe']:>+8.3f} {drop:>+6.3f} "
          f"{pi['skew']:>+7.3f} {po['skew']:>+8.3f} {verdict:>10}")

# ---------------------------------------------------------------------------
# TOP 3 LOW-RISK SLEEVES
# ---------------------------------------------------------------------------
print("\n\n" + "="*80)
print("TOP LOW-RISK SLEEVES (positive OOS Sharpe + lowest CVaR95 + best skew)")
print("="*80)

# Best robust: OOS Sharpe > 0, CVaR95 minimal, skew as positive as possible
candidates = [(score, name, pi, po) for score, name, pi, po in scored
              if po["sharpe"] > 0 and po["n_traded"] >= 8]
candidates.sort(key=lambda x: (-x[3]["sharpe"], x[3]["cvar95_c"]))

print("\nTop low-risk candidates (OOS Sharpe > 0, n>=8):")
for score, name, pi, po in candidates[:10]:
    print(f"\n  [{name}]")
    print(f"    IS:  Sh={pi['sharpe']:+.3f}  So={pi['sortino']:+.3f}  sk={pi['skew']:+.3f}  "
          f"CVaR={pi['cvar95_c']:.3f}c  Ulcer={pi['ulcer_c']:.3f}c  "
          f"maxDD={pi['maxdd_c']:.3f}c  n={pi['n_traded']} ({pi['pct']:.0f}%)  t={pi['tstat']:+.3f}")
    print(f"    OOS: Sh={po['sharpe']:+.3f}  So={po['sortino']:+.3f}  sk={po['skew']:+.3f}  "
          f"CVaR={po['cvar95_c']:.3f}c  Ulcer={po['ulcer_c']:.3f}c  "
          f"maxDD={po['maxdd_c']:.3f}c  n={po['n_traded']} ({po['pct']:.0f}%)  t={po['tstat']:+.3f}")
    print(f"    diff_vs_live: {po['diff_live_c']:+.3f}c  t={po['diff_t']:+.3f}")

# Absolute best by skew (for positive-skew criteria)
pos_skew = [(score, name, pi, po) for score, name, pi, po in scored
            if po["sharpe"] > 0 and po["skew"] > 0 and po["n_traded"] >= 8]
if pos_skew:
    print("\n\nPOSITIVE-SKEW OOS subset (Sharpe>0 + skew>0 + n>=8):")
    for score, name, pi, po in sorted(pos_skew, key=lambda x: (-x[3]["skew"], -x[3]["sharpe"]))[:10]:
        print(f"\n  [{name}]  IS_Sh={pi['sharpe']:+.3f}  OOS_Sh={po['sharpe']:+.3f}  "
              f"OOS_skew={po['skew']:+.3f}  OOS_CVaR={po['cvar95_c']:.3f}c  "
              f"OOS_maxDD={po['maxdd_c']:.3f}c  n={po['n_traded']}")
else:
    print("\nNo strict positive-skew+OOS-Sharpe candidates found at n>=8.")
    print("Closest (sorted by skew descending among OOS-positive-Sharpe):")
    for score, name, pi, po in sorted(candidates[:10],
                                       key=lambda x: -x[3]["skew"])[:5]:
        print(f"  [{name}] OOS_skew={po['skew']:+.3f}  OOS_Sh={po['sharpe']:+.3f}  "
              f"CVaR={po['cvar95_c']:.3f}c  n={po['n_traded']}")

print("\nDone.", flush=True)
