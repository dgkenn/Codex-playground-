"""k_window_study.py -- K-Window Entry Alternatives Study for Kalshi Maker-Box Bot.

Full metric sweep:
  1. Every single k=0..14 (individual slots)
  2. Every contiguous k-window {a..b} (all pairs)
  3. A few non-contiguous sets
  4. Cross k4,5 with price-bands and unpaired-handlers
  5. Sleeve analysis: risk-adjusted comparison, drawdown control value

IS=first 60%, OOS=last 40%, per-window PnL for Sharpe/Sortino/maxDD/Calmar/recovery.
"""
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")
from itertools import combinations

# ─── Load data ──────────────────────────────────────────────────────────────
print("Loading data...")
h = pd.read_parquet("/tmp/kw/hist_kalshi_btc15m.parquet").set_index("ws")
t = pd.read_parquet("/tmp/kw/trades_kalshi_btc15m.parquet").set_index("ws")

common = sorted(set(h.index) & set(t.index))
n = len(common)
cut = int(n * 0.6)
is_ws = set(common[:cut])
oos_ws = set(common[cut:])
print(f"Common windows: {n}  IS={cut}  OOS={n-cut}")
print(f"IS range: {pd.to_datetime(common[0], unit='s')} -> {pd.to_datetime(common[cut-1], unit='s')}")
print(f"OOS range: {pd.to_datetime(common[cut], unit='s')} -> {pd.to_datetime(common[-1], unit='s')}")


def arr(x):
    return np.asarray(x, float)


# ─── Main replay loop ────────────────────────────────────────────────────────
print("\nRunning clean-box replay (k=0..14, all windows)...")
records = []  # per-event records

for ws in common:
    h_row = h.loc[ws]
    t_row = t.loc[ws]
    bid_path = arr(h_row["bid_path"])
    ask_path = arr(h_row["ask_path"])
    res = int(h_row["res_up"])

    t_arr = arr(t_row["t"])
    p_arr = arr(t_row["p"])
    sz_arr = arr(t_row["sz"])
    buy_arr = arr(t_row["buy"]).astype(bool)

    split = "IS" if ws in is_ws else "OOS"

    for k in range(15):
        b0 = bid_path[k]
        a0 = ask_path[k]
        if np.isnan(b0) or np.isnan(a0):
            continue
        mid = (b0 + a0) / 2.0
        if not (0.02 <= mid <= 0.98):
            continue
        spread = a0 - b0
        if spread < 0 or spread > 0.20:
            continue

        lo = ws + 60 * (k + 1)
        hi = ws + 60 * (k + 2)
        i0 = int(np.searchsorted(t_arr, lo))
        i1 = int(np.searchsorted(t_arr, hi))

        got_b = got_a = False
        for i in range(i0, i1):
            p = float(p_arr[i])
            buy = bool(buy_arr[i])
            if not got_b and not buy and p <= b0 + 1e-9:
                got_b = True
            if not got_a and buy and p >= a0 - 1e-9:
                got_a = True
            if got_b and got_a:
                break

        abs_tilt = abs(mid - 0.5)
        lock = a0 - b0

        if got_b and got_a:
            outcome = "box"
            realized_c = lock * 100
        elif got_b:
            outcome = "strand_yes"
            realized_c = (res - b0) * 100
        elif got_a:
            outcome = "strand_no"
            realized_c = (a0 - res) * 100
        else:
            continue  # no fill at all

        records.append({
            "ws": ws, "split": split, "k": k,
            "mid": mid, "abs_tilt": abs_tilt, "lock": lock,
            "outcome": outcome, "realized_c": realized_c,
            "b0": b0, "a0": a0, "res": res,
        })

df = pd.DataFrame(records)
print(f"Total events: {len(df)}  boxes={len(df[df.outcome=='box'])}  "
      f"strands={len(df[df.outcome!='box'])}")


# ─── Core metrics helpers ─────────────────────────────────────────────────────
def sharpe(x):
    x = np.asarray(x, float)
    if len(x) < 3:
        return float("nan")
    m = np.mean(x); s = np.std(x, ddof=1)
    return m / s if s > 1e-9 else float("nan")


def sortino_r(x):
    x = np.asarray(x, float)
    if len(x) < 3:
        return float("nan")
    dn = x[x < 0]
    if len(dn) == 0:
        return float("inf") if np.mean(x) > 0 else float("nan")
    dd = np.sqrt(np.mean(dn ** 2))
    return float(np.mean(x)) / dd if dd > 1e-9 else float("nan")


def maxdd(x):
    x = np.asarray(x, float)
    if len(x) == 0:
        return 0.0
    cum = np.cumsum(x)
    return float(np.max(np.maximum.accumulate(cum) - cum))


def recovery_factor(x):
    x = np.asarray(x, float)
    dd = maxdd(x); tot = float(np.sum(x))
    return tot / dd if dd > 1e-9 else (float("inf") if tot > 0 else float("nan"))


def skew_r(x):
    x = np.asarray(x, float)
    if len(x) < 3:
        return float("nan")
    m = np.mean(x); s = np.std(x, ddof=1)
    if s < 1e-9:
        return float("nan")
    return float(np.mean(((x - m) / s) ** 3))


def stats_full(sub_df, label=""):
    """Full metric set for a filtered subset of events."""
    if len(sub_df) == 0:
        return {"label": label, "n_events": 0, "n_windows": 0,
                "p_both": float("nan"), "strand_pct": float("nan"),
                "mean_lock_c": float("nan"), "mean_net_c": float("nan"),
                "sharpe": float("nan"), "sortino": float("nan"),
                "skew": float("nan"), "maxDD_c": float("nan"),
                "recovery": float("nan"), "n_w": 0}
    is_box = sub_df["outcome"] == "box"
    n_ev = len(sub_df)
    n_box = is_box.sum()
    n_w = sub_df["ws"].nunique()
    p_both = n_box / n_ev
    strand_pct = 1.0 - p_both
    mean_lock_c = sub_df.loc[is_box, "lock"].mean() * 100 if n_box > 0 else float("nan")
    mean_net_c = sub_df["realized_c"].mean()

    # Per-window PnL for risk metrics
    wp = sub_df.groupby("ws")["realized_c"].sum().values
    sh = sharpe(wp)
    so = sortino_r(wp)
    sk = skew_r(wp)
    md = maxdd(wp) * 1  # already in cents
    rf = recovery_factor(wp)

    return {
        "label": label, "n_events": n_ev, "n_windows": n_w,
        "p_both": p_both, "strand_pct": strand_pct,
        "mean_lock_c": mean_lock_c, "mean_net_c": mean_net_c,
        "sharpe": sh, "sortino": so, "skew": sk,
        "maxDD_c": md, "recovery": rf, "n_w": len(wp),
    }


def fmt_full(s):
    def f(v, fmt=".3f"):
        return f"{v:{fmt}}" if not (v is None or (isinstance(v, float) and np.isnan(v))) else "  nan"
    return (f"P(both)={f(s['p_both'])}  strand%={f(s['strand_pct'])}  "
            f"lock={f(s['mean_lock_c'],'.2f')}c  net={f(s['mean_net_c'],'.2f')}c  "
            f"Sh={f(s['sharpe'])}  Sor={f(s['sortino'],'.2f')}  skew={f(s['skew'],'.2f')}  "
            f"maxDD={f(s['maxDD_c'],'.1f')}c  recov={f(s['recovery'],'.2f')}  "
            f"n={s['n_events']}  nw={s['n_w']}")


# ─── BASELINE ────────────────────────────────────────────────────────────────
print("\n" + "="*90)
print("BASELINE (always-on, k=0..14, all prices)")
print("="*90)
for sp in ["IS", "OOS"]:
    sub = df[df["split"] == sp]
    s = stats_full(sub, f"always-on {sp}")
    print(f"  {sp}: {fmt_full(s)}")


# ─── SWEEP 1: Every single k ─────────────────────────────────────────────────
print("\n" + "="*90)
print("SWEEP 1: Every single k=0..14 (IS and OOS)")
print("="*90)
k_stats = {}
for k in range(15):
    row = {"k": k}
    for sp in ["IS", "OOS"]:
        sub = df[(df["k"] == k) & (df["split"] == sp)]
        s = stats_full(sub)
        row[f"{sp}_sharpe"] = s["sharpe"]
        row[f"{sp}_net_c"] = s["mean_net_c"]
        row[f"{sp}_p_both"] = s["p_both"]
        row[f"{sp}_sortino"] = s["sortino"]
        row[f"{sp}_maxDD_c"] = s["maxDD_c"]
        row[f"{sp}_recovery"] = s["recovery"]
        row[f"{sp}_skew"] = s["skew"]
        row[f"{sp}_strand_pct"] = s["strand_pct"]
        row[f"{sp}_nw"] = s["n_w"]
        row[f"{sp}_n"] = s["n_events"]
    k_stats[k] = row

print(f"\n{'k':>3} | {'IS_Sh':>6} {'IS_net':>7} {'IS_P(both)':>10} {'IS_Sort':>7} "
      f"| {'OOS_Sh':>6} {'OOS_net':>7} {'OOS_P(b)':>8} {'OOS_Sort':>8} {'OOS_maxDD':>9} {'OOS_recov':>9}")
print("-"*100)
for k, row in k_stats.items():
    def fv(v, fmt=".3f"):
        return f"{v:{fmt}}" if not np.isnan(v) else "   nan"
    print(f"  {k:2d} | {fv(row['IS_sharpe']):>6} {fv(row['IS_net_c'],'.2f'):>7}c "
          f"{fv(row['IS_p_both'],'.3f'):>10} {fv(row['IS_sortino'],'.2f'):>7} "
          f"| {fv(row['OOS_sharpe']):>6} {fv(row['OOS_net_c'],'.2f'):>7}c "
          f"{fv(row['OOS_p_both'],'.3f'):>8} {fv(row['OOS_sortino'],'.2f'):>8} "
          f"{fv(row['OOS_maxDD_c'],'.1f'):>9}c {fv(row['OOS_recovery'],'.2f'):>9}")

# Find best individual k by OOS metrics
oos_sh = [(k, row["OOS_sharpe"]) for k, row in k_stats.items() if not np.isnan(row["OOS_sharpe"])]
oos_net = [(k, row["OOS_net_c"]) for k, row in k_stats.items() if not np.isnan(row["OOS_net_c"])]
oos_pb = [(k, row["OOS_p_both"]) for k, row in k_stats.items() if not np.isnan(row["OOS_p_both"])]
best_k_sh = max(oos_sh, key=lambda x: x[1])
best_k_net = max(oos_net, key=lambda x: x[1])
best_k_pb = max(oos_pb, key=lambda x: x[1])
print(f"\nBest single k by OOS Sharpe:   k={best_k_sh[0]} ({best_k_sh[1]:+.3f})")
print(f"Best single k by OOS net c/ev: k={best_k_net[0]} ({best_k_net[1]:+.2f}c)")
print(f"Best single k by OOS P(both):  k={best_k_pb[0]} ({best_k_pb[1]:.3f})")


# ─── SWEEP 2: Every contiguous k-window {a..b} ───────────────────────────────
print("\n" + "="*90)
print("SWEEP 2: Every contiguous k-window {a..b} (all IS n_w>=5)")
print("="*90)
window_results = []
for a_k in range(15):
    for b_k in range(a_k, 15):
        ks = set(range(a_k, b_k + 1))
        mask = df["k"].isin(ks)
        s_is = stats_full(df[mask & (df["split"] == "IS")])
        s_oos = stats_full(df[mask & (df["split"] == "OOS")])
        if s_is["n_w"] < 5:
            continue
        window_results.append({
            "k_set": f"k={a_k}..{b_k}", "a": a_k, "b": b_k, "width": b_k - a_k + 1,
            "IS_sharpe": s_is["sharpe"], "IS_net": s_is["mean_net_c"],
            "IS_p_both": s_is["p_both"], "IS_nw": s_is["n_w"],
            "OOS_sharpe": s_oos["sharpe"], "OOS_net": s_oos["mean_net_c"],
            "OOS_p_both": s_oos["p_both"], "OOS_sortino": s_oos["sortino"],
            "OOS_maxDD": s_oos["maxDD_c"], "OOS_recovery": s_oos["recovery"],
            "OOS_skew": s_oos["skew"], "OOS_nw": s_oos["n_w"],
        })

wr = pd.DataFrame(window_results)

# Top by OOS Sharpe
print("\nTop 15 contiguous windows by OOS Sharpe (min IS nw>=5):")
top_sh = wr.sort_values("OOS_sharpe", ascending=False).head(15)
for _, row in top_sh.iterrows():
    def fv(v, fmt=".3f"):
        return f"{v:{fmt}}" if not np.isnan(v) else "  nan"
    print(f"  {row['k_set']:>10}: IS_Sh={fv(row['IS_sharpe'])}  IS_net={fv(row['IS_net'],'.2f')}c  "
          f"IS_nw={int(row['IS_nw'])}  OOS_Sh={fv(row['OOS_sharpe'])}  "
          f"OOS_net={fv(row['OOS_net'],'.2f')}c  OOS_P(b)={fv(row['OOS_p_both'])}  "
          f"OOS_Sort={fv(row['OOS_sortino'],'.2f')}  OOS_maxDD={fv(row['OOS_maxDD'],'.1f')}c  "
          f"OOS_recov={fv(row['OOS_recovery'],'.2f')}  OOS_nw={int(row['OOS_nw'])}")

# Top by OOS net
print("\nTop 15 contiguous windows by OOS net c/event:")
top_net = wr.sort_values("OOS_net", ascending=False).head(15)
for _, row in top_net.iterrows():
    print(f"  {row['k_set']:>10}: IS_Sh={fv(row['IS_sharpe'])}  IS_net={fv(row['IS_net'],'.2f')}c  "
          f"OOS_Sh={fv(row['OOS_sharpe'])}  OOS_net={fv(row['OOS_net'],'.2f')}c  "
          f"OOS_P(b)={fv(row['OOS_p_both'])}  OOS_nw={int(row['OOS_nw'])}")

# Top by OOS P(both)
print("\nTop 10 contiguous windows by OOS P(both fill):")
top_pb = wr.sort_values("OOS_p_both", ascending=False).head(10)
for _, row in top_pb.iterrows():
    print(f"  {row['k_set']:>10}: OOS_P(b)={fv(row['OOS_p_both'])}  "
          f"OOS_Sh={fv(row['OOS_sharpe'])}  OOS_net={fv(row['OOS_net'],'.2f')}c")

# Where do they differ? Find the best by each metric
best_wr_sh = wr.loc[wr["OOS_sharpe"].idxmax()]
best_wr_net = wr.loc[wr["OOS_net"].idxmax()]
best_wr_pb = wr.loc[wr["OOS_p_both"].idxmax()]
print(f"\nBest contiguous window by OOS Sharpe:   {best_wr_sh['k_set']} "
      f"OOS_Sh={best_wr_sh['OOS_sharpe']:+.3f}  OOS_net={best_wr_sh['OOS_net']:+.2f}c")
print(f"Best contiguous window by OOS net c/ev: {best_wr_net['k_set']} "
      f"OOS_Sh={best_wr_net['OOS_sharpe']:+.3f}  OOS_net={best_wr_net['OOS_net']:+.2f}c")
print(f"Best contiguous window by OOS P(both):  {best_wr_pb['k_set']} "
      f"OOS_Sh={best_wr_pb['OOS_sharpe']:+.3f}  OOS_P(b)={best_wr_pb['OOS_p_both']:.3f}")


# ─── SWEEP 3: Non-contiguous sets ────────────────────────────────────────────
print("\n" + "="*90)
print("SWEEP 3: Non-contiguous k-sets (curated)")
print("="*90)
nc_sets = [
    ("k={4,5}", {4, 5}),
    ("k={3,4,5}", {3, 4, 5}),
    ("k={4,5,6}", {4, 5, 6}),
    ("k={3,4,5,6}", {3, 4, 5, 6}),
    ("k={0,4,5}", {0, 4, 5}),
    ("k={4,5,7}", {4, 5, 7}),
    ("k={2,4,5}", {2, 4, 5}),
    ("k={4,5,8}", {4, 5, 8}),
    ("k={1,2,4,5}", {1, 2, 4, 5}),
    ("k={0,1,2}", {0, 1, 2}),
    ("k={4,5,9}", {4, 5, 9}),
    ("k={3,4}", {3, 4}),
    ("k={5,6}", {5, 6}),
    ("k={2,3,4,5}", {2, 3, 4, 5}),
    ("k={4,5,6,7}", {4, 5, 6, 7}),
    ("k={0,1}", {0, 1}),
    ("k={6,7}", {6, 7}),
    ("k={4}", {4}),
    ("k={5}", {5}),
    ("k={3}", {3}),
    ("k={6}", {6}),
]

nc_results = []
for label, ks in nc_sets:
    mask = df["k"].isin(ks)
    s_is = stats_full(df[mask & (df["split"] == "IS")])
    s_oos = stats_full(df[mask & (df["split"] == "OOS")])
    nc_results.append({
        "label": label, "ks": ks,
        "IS_sharpe": s_is["sharpe"], "IS_net": s_is["mean_net_c"],
        "IS_p_both": s_is["p_both"], "IS_nw": s_is["n_w"],
        "OOS_sharpe": s_oos["sharpe"], "OOS_net": s_oos["mean_net_c"],
        "OOS_p_both": s_oos["p_both"], "OOS_sortino": s_oos["sortino"],
        "OOS_maxDD": s_oos["maxDD_c"], "OOS_recovery": s_oos["recovery"],
        "OOS_skew": s_oos["skew"], "OOS_strand_pct": s_oos["strand_pct"],
        "OOS_nw": s_oos["n_w"],
    })

nc_df = pd.DataFrame(nc_results).sort_values("OOS_sharpe", ascending=False)
print(f"\n{'k_set':>20} | {'IS_Sh':>6} {'IS_net':>7} | {'OOS_Sh':>6} {'OOS_net':>7} "
      f"{'OOS_P(b)':>8} {'OOS_Sor':>7} {'OOS_mDD':>7} {'OOS_rec':>7} {'OOS_nw':>6}")
print("-"*100)
for _, row in nc_df.iterrows():
    def fv(v, fmt=".3f"):
        return f"{v:{fmt}}" if not np.isnan(v) else "   nan"
    print(f"  {row['label']:>18} | {fv(row['IS_sharpe']):>6} {fv(row['IS_net'],'.2f'):>6}c "
          f"| {fv(row['OOS_sharpe']):>6} {fv(row['OOS_net'],'.2f'):>6}c "
          f"{fv(row['OOS_p_both']):>8} {fv(row['OOS_sortino'],'.2f'):>7} "
          f"{fv(row['OOS_maxDD'],'.1f'):>6}c {fv(row['OOS_recovery'],'.2f'):>7} "
          f"{int(row['OOS_nw']):>6}")


# ─── SWEEP 4: k4,5 x Price Bands ─────────────────────────────────────────────
print("\n" + "="*90)
print("SWEEP 4: k={4,5} crossed with price bands (|p-0.5| bins)")
print("="*90)
base_mask = df["k"].isin({4, 5})
price_bins = [
    ("all_prices", 0.00, 0.50),
    ("near-ATM [0,0.1)", 0.00, 0.10),
    ("ATM [0.1,0.2)", 0.10, 0.20),
    ("mid [0.2,0.3)", 0.20, 0.30),
    ("tilt [0.3,0.4)", 0.30, 0.40),
    ("tail [0.4,0.5)", 0.40, 0.50),
    ("not-tail [0,0.3)", 0.00, 0.30),
    ("mid-out [0.1,0.4)", 0.10, 0.40),
    ("tight ATM [0,0.15)", 0.00, 0.15),
    ("tilt+ [0.35,0.5)", 0.35, 0.50),
]
pb_results = []
for p_label, p_lo, p_hi in price_bins:
    pmask = (df["abs_tilt"] >= p_lo) & (df["abs_tilt"] < p_hi)
    mask = base_mask & pmask
    for sp in ["IS", "OOS"]:
        sub = df[mask & (df["split"] == sp)]
        s = stats_full(sub)
        pb_results.append({
            "price_band": p_label, "split": sp,
            "sharpe": s["sharpe"], "net_c": s["mean_net_c"],
            "p_both": s["p_both"], "sortino": s["sortino"],
            "maxDD": s["maxDD_c"], "recovery": s["recovery"], "nw": s["n_w"],
        })

pb_df = pd.DataFrame(pb_results)
print(f"\nk={{4,5}} x price bands:")
print(f"{'price_band':>20} | {'IS_Sh':>6} {'IS_net':>7} {'IS_nw':>5} "
      f"| {'OOS_Sh':>6} {'OOS_net':>7} {'OOS_P(b)':>8} {'OOS_Sor':>7} {'OOS_mDD':>7} {'OOS_nw':>6}")
for p_label, _, _ in price_bins:
    r_is = pb_df[(pb_df["price_band"] == p_label) & (pb_df["split"] == "IS")].iloc[0]
    r_oos = pb_df[(pb_df["price_band"] == p_label) & (pb_df["split"] == "OOS")].iloc[0]
    def fv(v, fmt=".3f"):
        return f"{v:{fmt}}" if not np.isnan(v) else "   nan"
    print(f"  {p_label:>18} | {fv(r_is['sharpe']):>6} {fv(r_is['net_c'],'.2f'):>6}c {int(r_is['nw']):>5} "
          f"| {fv(r_oos['sharpe']):>6} {fv(r_oos['net_c'],'.2f'):>6}c "
          f"{fv(r_oos['p_both']):>8} {fv(r_oos['sortino'],'.2f'):>7} "
          f"{fv(r_oos['maxDD'],'.1f'):>6}c {int(r_oos['nw']):>6}")


# ─── SWEEP 5: k4,5 x Unpaired Handlers (HOLD vs SELL-CHEAP vs PERP-HEDGE simulation) ─
print("\n" + "="*90)
print("SWEEP 5: k={4,5} with unpaired handlers (HOLD vs sell-cheap<0.30 vs perp-approx)")
print("  (clean-box replay: no fill = no event. Sell-cheap approximated as: stranded YES")
print("   at low price exits at mid - 0.5*spread; stranded NO at high price exits same.)")
print("  Perp-hedge: assume ~0 residual from hedge (conservative: hedge eliminates ~avg. loss)")
print("="*90)

def handler_stats(sub_df, handler="hold"):
    """Compute modified realized_c for different strand handlers."""
    if len(sub_df) == 0:
        return {"handler": handler, "n_events": 0, "n_w": 0,
                "p_both": float("nan"), "mean_net_c": float("nan"),
                "sharpe": float("nan"), "sortino": float("nan"),
                "maxDD_c": float("nan"), "recovery": float("nan")}
    is_box = sub_df["outcome"] == "box"
    n_ev = len(sub_df)
    n_box = is_box.sum()
    p_both = n_box / n_ev

    pnl = np.array(sub_df["realized_c"].values, dtype=float)
    if handler == "sell_cheap":
        # sell strand only if leg price < 0.30 (cheap long-shot)
        strand_mask = ~is_box.values
        cheap_mask_yes = ((sub_df["outcome"] == "strand_yes") & (sub_df["b0"] < 0.30)).values
        cheap_mask_no = ((sub_df["outcome"] == "strand_no") & ((1 - sub_df["a0"]) < 0.30)).values
        cheap_mask = cheap_mask_yes | cheap_mask_no
        # exit at mid (estimated) instead of settle
        for i in range(len(pnl)):
            if strand_mask[i] and cheap_mask[i]:
                row = sub_df.iloc[i]
                mid = (row["b0"] + row["a0"]) / 2.0
                # sell at mid (no cost model, conservative)
                if row["outcome"] == "strand_yes":
                    pnl[i] = (mid - row["b0"]) * 100
                else:
                    pnl[i] = (row["a0"] - mid) * 100
    elif handler == "perp_hedge":
        # Conservative: strand pnl -> 0 (hedge eliminates directional loss)
        strand_mask = ~is_box.values
        pnl = np.where(strand_mask, 0.0, pnl)

    mean_net = float(np.mean(pnl))
    ws_groups = {}
    for i, ws_val in enumerate(sub_df["ws"].values):
        ws_groups.setdefault(ws_val, []).append(pnl[i])
    wp = np.array([sum(v) for v in ws_groups.values()])
    sh = sharpe(wp); so = sortino_r(wp)
    md = maxdd(wp); rf = recovery_factor(wp)

    return {"handler": handler, "n_events": n_ev, "n_w": len(wp),
            "p_both": p_both, "mean_net_c": mean_net,
            "sharpe": sh, "sortino": so, "maxDD_c": md, "recovery": rf}


base_mask45 = df["k"].isin({4, 5})
for sp in ["IS", "OOS"]:
    print(f"\n  k={{4,5}} {sp}:")
    sub = df[base_mask45 & (df["split"] == sp)]
    for handler in ["hold", "sell_cheap", "perp_hedge"]:
        s = handler_stats(sub, handler)
        def fv(v, fmt=".3f"):
            return f"{v:{fmt}}" if not np.isnan(v) else "  nan"
        print(f"    {handler:>15}: net={fv(s['mean_net_c'],'.2f')}c  "
              f"Sh={fv(s['sharpe'])}  Sort={fv(s['sortino'],'.2f')}  "
              f"maxDD={fv(s['maxDD_c'],'.1f')}c  recov={fv(s['recovery'],'.2f')}  nw={s['n_w']}")


# ─── SLEEVE ANALYSIS: k4,5 vs always-on vs best-mean rule ────────────────────
print("\n" + "="*90)
print("SLEEVE ANALYSIS: Sharpe/Calmar/Recovery comparison (k4,5 vs always-on vs best-mean)")
print("="*90)

def full_sleeve_stats(mask, label, split):
    sub = df[mask & (df["split"] == split)]
    if len(sub) == 0:
        return None
    wp = sub.groupby("ws")["realized_c"].sum().values
    sh = sharpe(wp); so = sortino_r(wp); sk = skew_r(wp)
    md = maxdd(wp); rf = recovery_factor(wp)
    mn = float(np.mean(wp)); tot = float(np.sum(wp))

    # Calmar (total return / maxDD)
    calmar = tot / md if md > 1e-9 else (float("inf") if tot > 0 else float("nan"))

    # Time underwater (fraction of windows where cumPnL < running max)
    cum = np.cumsum(wp); runn_max = np.maximum.accumulate(cum)
    time_uw = float(np.mean(cum < runn_max))

    return {"label": label, "split": split,
            "mean_c_per_win": mn, "total_c": tot,
            "sharpe": sh, "sortino": so, "skew": sk,
            "maxDD_c": md, "calmar": calmar, "recovery": rf,
            "time_underwater": time_uw, "n_w": len(wp)}

# Identify best-mean rule from sweep 2 (OOS net)
best_mean_k_set = best_wr_net["k_set"]
best_mean_a = int(best_wr_net["a"]); best_mean_b = int(best_wr_net["b"])
best_mean_mask = df["k"].between(best_mean_a, best_mean_b)

# Best OOS Sharpe contiguous window
best_sh_k_set = best_wr_sh["k_set"]
best_sh_a = int(best_wr_sh["a"]); best_sh_b = int(best_wr_sh["b"])
best_sh_mask = df["k"].between(best_sh_a, best_sh_b)

sleeve_comparisons = [
    ("always-on", df["k"].between(0, 14)),
    ("k={4,5}", df["k"].isin({4, 5})),
    ("k={4}", df["k"] == 4),
    ("k={5}", df["k"] == 5),
    (f"best-mean: {best_mean_k_set}", best_mean_mask),
    (f"best-Sh: {best_sh_k_set}", best_sh_mask),
]

# Also add best window from single k
best_k_single = best_k_sh[0]
sleeve_comparisons.append((f"best-single-k: k={best_k_single}", df["k"] == best_k_single))

print(f"\n{'Rule':>30} | {'split':>4} | {'mean_c/w':>8} {'Sharpe':>7} {'Sortino':>8} "
      f"{'Calmar':>7} {'maxDD_c':>8} {'recovery':>9} {'time_uw%':>9} {'skew':>6} {'nw':>5}")
print("-"*120)

sleeve_data = {}
for label, mask in sleeve_comparisons:
    for sp in ["OOS"]:
        s = full_sleeve_stats(mask, label, sp)
        if s is None:
            continue
        sleeve_data[(label, sp)] = s
        def fv(v, fmt=".3f"):
            return f"{v:{fmt}}" if not (v is None or np.isnan(v)) else "    nan"
        print(f"  {label:>28} | {sp:>4} | {fv(s['mean_c_per_win'],'.2f'):>8} "
              f"{fv(s['sharpe']):>7} {fv(s['sortino'],'.2f'):>8} "
              f"{fv(s['calmar'],'.2f'):>7} {fv(s['maxDD_c'],'.1f'):>7}c "
              f"{fv(s['recovery'],'.2f'):>9} {fv(s['time_underwater']*100,'.1f'):>8}% "
              f"{fv(s['skew'],'.2f'):>6} {s['n_w']:>5}")

# IS results too
print()
for label, mask in sleeve_comparisons:
    for sp in ["IS"]:
        s = full_sleeve_stats(mask, label, sp)
        if s is None:
            continue
        def fv(v, fmt=".3f"):
            return f"{v:{fmt}}" if not (v is None or np.isnan(v)) else "    nan"
        print(f"  {label:>28} | {sp:>4} | {fv(s['mean_c_per_win'],'.2f'):>8} "
              f"{fv(s['sharpe']):>7} {fv(s['sortino'],'.2f'):>8} "
              f"{fv(s['calmar'],'.2f'):>7} {fv(s['maxDD_c'],'.1f'):>7}c "
              f"{fv(s['recovery'],'.2f'):>9} {fv(s['time_underwater']*100,'.1f'):>8}% "
              f"{fv(s['skew'],'.2f'):>6} {s['n_w']:>5}")


# ─── Explicit sleeve verdict ─────────────────────────────────────────────────
print("\n" + "="*90)
print("SLEEVE VERDICT: explicit DD-control quantification")
print("="*90)
ao_oos = sleeve_data.get(("always-on", "OOS"))
k45_oos = sleeve_data.get(("k={4,5}", "OOS"))
bm_oos = sleeve_data.get((f"best-mean: {best_mean_k_set}", "OOS"))
bsh_oos = sleeve_data.get((f"best-Sh: {best_sh_k_set}", "OOS"))
bk_oos = sleeve_data.get((f"best-single-k: k={best_k_single}", "OOS"))

def ratio_str(num, den):
    if num is None or den is None or np.isnan(num) or np.isnan(den) or den == 0:
        return "n/a"
    return f"{num/den:.2f}x"

if ao_oos and k45_oos:
    print(f"\n  k={{4,5}} vs always-on (OOS):")
    print(f"    Sharpe:     {k45_oos['sharpe']:+.3f} vs {ao_oos['sharpe']:+.3f}  "
          f"(delta={k45_oos['sharpe']-ao_oos['sharpe']:+.3f})")
    print(f"    Sortino:    {k45_oos['sortino']:+.3f} vs {ao_oos['sortino']:+.3f}")
    print(f"    Calmar:     {k45_oos['calmar']:+.3f} vs {ao_oos['calmar']:+.3f}")
    print(f"    maxDD_c:    {k45_oos['maxDD_c']:.1f}c vs {ao_oos['maxDD_c']:.1f}c  "
          f"({ratio_str(k45_oos['maxDD_c'], ao_oos['maxDD_c'])} of always-on)")
    print(f"    recovery:   {k45_oos['recovery']:+.3f} vs {ao_oos['recovery']:+.3f}")
    print(f"    time_uw%:   {k45_oos['time_underwater']*100:.1f}% vs {ao_oos['time_underwater']*100:.1f}%")
    print(f"    mean_c/win: {k45_oos['mean_c_per_win']:+.2f}c vs {ao_oos['mean_c_per_win']:+.2f}c")

if bm_oos and k45_oos:
    print(f"\n  k={{4,5}} vs best-mean rule ({best_mean_k_set}) (OOS):")
    print(f"    Sharpe:     {k45_oos['sharpe']:+.3f} vs {bm_oos['sharpe']:+.3f}")
    print(f"    Calmar:     {k45_oos['calmar']:+.3f} vs {bm_oos['calmar']:+.3f}")
    print(f"    maxDD_c:    {k45_oos['maxDD_c']:.1f}c vs {bm_oos['maxDD_c']:.1f}c")
    print(f"    mean_c/win: {k45_oos['mean_c_per_win']:+.2f}c vs {bm_oos['mean_c_per_win']:+.2f}c")


# ─── COMBINATION: k4,5 SLEEVE + BEST-MEAN SLEEVE ────────────────────────────
print("\n" + "="*90)
print("PORTFOLIO COMBINATION: k4,5 (low-variance) + best-mean rule (50/50 blend)")
print("  (Concept: allocate 50% to k4,5 and 50% to best-mean; each takes half the position)")
print("="*90)

# For the blend: sum (0.5 * k45) + (0.5 * best_mean) per window
for sp in ["IS", "OOS"]:
    sub45 = df[df["k"].isin({4, 5}) & (df["split"] == sp)]
    sub_bm = df[best_mean_mask & (df["split"] == sp)]

    wp45 = sub45.groupby("ws")["realized_c"].sum()
    wp_bm = sub_bm.groupby("ws")["realized_c"].sum()

    all_ws = sorted(set(wp45.index) | set(wp_bm.index))
    blend = np.array([0.5 * wp45.get(w, 0.0) + 0.5 * wp_bm.get(w, 0.0) for w in all_ws])

    sh = sharpe(blend); so = sortino_r(blend); md = maxdd(blend); rf = recovery_factor(blend)
    cal = sum(blend) / md if md > 1e-9 else float("inf")
    print(f"  50/50 blend k4,5 + {best_mean_k_set} ({sp}): "
          f"mean={np.mean(blend):+.2f}c/w  Sh={sh:+.3f}  Sort={so:+.2f}  "
          f"Calmar={cal:+.2f}  maxDD={md:.1f}c  recov={rf:+.2f}  nw={len(blend)}")


# ─── FINAL RECOMMENDATIONS ───────────────────────────────────────────────────
print("\n" + "="*90)
print("TRIAL RECOMMENDATIONS: Top 4 to register as A/B trials (by OOS Sharpe and OOS net)")
print("="*90)

# Collect all candidate results for final ranking
all_candidates = []

# From single k slots
for k_val in range(15):
    sub_oos = df[(df["k"] == k_val) & (df["split"] == "OOS")]
    s = stats_full(sub_oos)
    if not np.isnan(s["sharpe"]) and s["n_w"] >= 5:
        all_candidates.append({
            "label": f"k={{{k_val}}}",
            "k_set": {k_val},
            "open_ok_lambda": f"lambda f, s: f['k'] == {k_val}",
            "OOS_sharpe": s["sharpe"], "OOS_net_c": s["mean_net_c"],
            "OOS_p_both": s["p_both"], "OOS_sortino": s["sortino"],
            "OOS_maxDD_c": s["maxDD_c"], "OOS_recovery": s["recovery"],
            "OOS_nw": s["n_w"],
        })

# From contiguous windows
for _, row in wr.iterrows():
    all_candidates.append({
        "label": row["k_set"],
        "k_set": set(range(int(row["a"]), int(row["b"]) + 1)),
        "open_ok_lambda": (f"lambda f, s: {int(row['a'])} <= f['k'] <= {int(row['b'])}"
                           if row["a"] != row["b"] else f"lambda f, s: f['k'] == {int(row['a'])}"),
        "OOS_sharpe": row["OOS_sharpe"], "OOS_net_c": row["OOS_net"],
        "OOS_p_both": row["OOS_p_both"], "OOS_sortino": row["OOS_sortino"],
        "OOS_maxDD_c": row["OOS_maxDD"], "OOS_recovery": row["OOS_recovery"],
        "OOS_nw": int(row["OOS_nw"]),
    })

# From non-contiguous
for row in nc_results:
    ks = row["ks"]
    k_list = sorted(ks)
    all_candidates.append({
        "label": row["label"],
        "k_set": ks,
        "open_ok_lambda": f"lambda f, s: f['k'] in {tuple(sorted(ks))}",
        "OOS_sharpe": row["OOS_sharpe"], "OOS_net_c": row["OOS_net"],
        "OOS_p_both": row["OOS_p_both"], "OOS_sortino": row["OOS_sortino"],
        "OOS_maxDD_c": row["OOS_maxDD"], "OOS_recovery": row["OOS_recovery"],
        "OOS_nw": int(row["OOS_nw"]),
    })

cand_df = pd.DataFrame(all_candidates)
cand_df = cand_df[cand_df["OOS_nw"] >= 5].drop_duplicates(subset=["label"])

top_by_sharpe = cand_df.sort_values("OOS_sharpe", ascending=False).head(10)
top_by_net = cand_df.sort_values("OOS_net_c", ascending=False).head(10)

print("\nTop 10 by OOS Sharpe:")
for _, row in top_by_sharpe.iterrows():
    def fv(v, fmt=".3f"):
        return f"{v:{fmt}}" if not np.isnan(v) else "  nan"
    print(f"  {row['label']:>20}: OOS_Sh={fv(row['OOS_sharpe'])}  OOS_net={fv(row['OOS_net_c'],'.2f')}c  "
          f"OOS_P(b)={fv(row['OOS_p_both'])}  OOS_Sort={fv(row['OOS_sortino'],'.2f')}  "
          f"OOS_mDD={fv(row['OOS_maxDD_c'],'.1f')}c  OOS_rec={fv(row['OOS_recovery'],'.2f')}  nw={int(row['OOS_nw'])}")
    print(f"  {'':>20}  open_ok: {row['open_ok_lambda']}")

print("\nTop 10 by OOS net c/event:")
for _, row in top_by_net.iterrows():
    def fv(v, fmt=".3f"):
        return f"{v:{fmt}}" if not np.isnan(v) else "  nan"
    print(f"  {row['label']:>20}: OOS_Sh={fv(row['OOS_sharpe'])}  OOS_net={fv(row['OOS_net_c'],'.2f')}c  "
          f"OOS_P(b)={fv(row['OOS_p_both'])}  OOS_Sort={fv(row['OOS_sortino'],'.2f')}  "
          f"OOS_mDD={fv(row['OOS_maxDD_c'],'.1f')}c  OOS_rec={fv(row['OOS_recovery'],'.2f')}  nw={int(row['OOS_nw'])}")


print("\n" + "="*90)
print("SUMMARY: Key numbers for K_WINDOW_ALTERNATIVES.md")
print("="*90)

# Print the exact numbers we need for the report
ao_is = full_sleeve_stats(df["k"].between(0, 14), "always-on", "IS")
ao_oos = full_sleeve_stats(df["k"].between(0, 14), "always-on", "OOS")
k45_is = full_sleeve_stats(df["k"].isin({4, 5}), "k={4,5}", "IS")
k45_oos = full_sleeve_stats(df["k"].isin({4, 5}), "k={4,5}", "OOS")

print(f"\nAlways-on IS:  Sh={ao_is['sharpe']:+.3f}  Sort={ao_is['sortino']:+.3f}  "
      f"maxDD={ao_is['maxDD_c']:.1f}c  calmar={ao_is['calmar']:+.3f}  "
      f"recov={ao_is['recovery']:+.3f}  time_uw={ao_is['time_underwater']*100:.1f}%  nw={ao_is['n_w']}")
print(f"Always-on OOS: Sh={ao_oos['sharpe']:+.3f}  Sort={ao_oos['sortino']:+.3f}  "
      f"maxDD={ao_oos['maxDD_c']:.1f}c  calmar={ao_oos['calmar']:+.3f}  "
      f"recov={ao_oos['recovery']:+.3f}  time_uw={ao_oos['time_underwater']*100:.1f}%  nw={ao_oos['n_w']}")

print(f"\nk={{4,5}} IS:  Sh={k45_is['sharpe']:+.3f}  Sort={k45_is['sortino']:+.3f}  "
      f"maxDD={k45_is['maxDD_c']:.1f}c  calmar={k45_is['calmar']:+.3f}  "
      f"recov={k45_is['recovery']:+.3f}  time_uw={k45_is['time_underwater']*100:.1f}%  nw={k45_is['n_w']}")
print(f"k={{4,5}} OOS: Sh={k45_oos['sharpe']:+.3f}  Sort={k45_oos['sortino']:+.3f}  "
      f"maxDD={k45_oos['maxDD_c']:.1f}c  calmar={k45_oos['calmar']:+.3f}  "
      f"recov={k45_oos['recovery']:+.3f}  time_uw={k45_oos['time_underwater']*100:.1f}%  nw={k45_oos['n_w']}")

# For best windows, print exact numbers
print(f"\nBest contiguous by OOS Sharpe: {best_wr_sh['k_set']}")
s_bsh_is = full_sleeve_stats(df["k"].between(best_sh_a, best_sh_b), f"best-Sh:{best_sh_k_set}", "IS")
s_bsh_oos = full_sleeve_stats(df["k"].between(best_sh_a, best_sh_b), f"best-Sh:{best_sh_k_set}", "OOS")
print(f"  IS:  Sh={s_bsh_is['sharpe']:+.3f}  net={s_bsh_is['mean_c_per_win']:+.2f}c/w  "
      f"maxDD={s_bsh_is['maxDD_c']:.1f}c  nw={s_bsh_is['n_w']}")
print(f"  OOS: Sh={s_bsh_oos['sharpe']:+.3f}  net={s_bsh_oos['mean_c_per_win']:+.2f}c/w  "
      f"maxDD={s_bsh_oos['maxDD_c']:.1f}c  Sort={s_bsh_oos['sortino']:+.3f}  "
      f"calmar={s_bsh_oos['calmar']:+.3f}  recov={s_bsh_oos['recovery']:+.3f}  nw={s_bsh_oos['n_w']}")

print(f"\nBest contiguous by OOS net: {best_wr_net['k_set']}")
s_bm_is = full_sleeve_stats(best_mean_mask, f"best-mean:{best_mean_k_set}", "IS")
s_bm_oos = full_sleeve_stats(best_mean_mask, f"best-mean:{best_mean_k_set}", "OOS")
print(f"  IS:  Sh={s_bm_is['sharpe']:+.3f}  net={s_bm_is['mean_c_per_win']:+.2f}c/w  "
      f"maxDD={s_bm_is['maxDD_c']:.1f}c  nw={s_bm_is['n_w']}")
print(f"  OOS: Sh={s_bm_oos['sharpe']:+.3f}  net={s_bm_oos['mean_c_per_win']:+.2f}c/w  "
      f"maxDD={s_bm_oos['maxDD_c']:.1f}c  Sort={s_bm_oos['sortino']:+.3f}  "
      f"calmar={s_bm_oos['calmar']:+.3f}  recov={s_bm_oos['recovery']:+.3f}  nw={s_bm_oos['n_w']}")

print("\n[Done]")
