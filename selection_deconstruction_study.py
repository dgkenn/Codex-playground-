"""selection_deconstruction_study.py -- Kalshi maker-box selection deconstruction.

Challenges two prior hypotheses:
  P1: tilt zone (|p-0.5| ~ 0.25-0.40) wins on Sharpe + PnL
  P2: early k=0..2 wins on Sharpe + PnL

Approach:
  - Clean-box replay on hist_kalshi_btc15m.parquet + trades_kalshi_btc15m.parquet
  - Per opened box: record k, mid p, abs_tilt=|p-0.5|, lock, fill outcome
  - Aggregate by: |p-0.5| bins 0.05-wide, k 0..14, 2D k x price grid
  - IS=first 60%, OOS=last 40%
  - Per bucket: #boxes, P(both), strand%, mean lock, mean net c/win, std, Sharpe, win-rate
  - Deconstruct P1 and P2 vs baseline
  - Find granular k x price rule maximizing Sharpe + PnL
"""
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# ─── Load data ──────────────────────────────────────────────────────────────
print("Loading data...")
h = pd.read_parquet("/tmp/sel/hist_kalshi_btc15m.parquet").set_index("ws")
t = pd.read_parquet("/tmp/sel/trades_kalshi_btc15m.parquet").set_index("ws")

common = sorted(set(h.index) & set(t.index))
n = len(common)
cut = int(n * 0.6)
is_ws = set(common[:cut])
oos_ws = set(common[cut:])
print(f"Common windows: {n}  IS={cut}  OOS={n-cut}")
print(f"IS date range: {pd.to_datetime(common[0], unit='s')} - {pd.to_datetime(common[cut-1], unit='s')}")
print(f"OOS date range: {pd.to_datetime(common[cut], unit='s')} - {pd.to_datetime(common[-1], unit='s')}")


def arr(x):
    return np.asarray(x, float)


# ─── Main replay loop ────────────────────────────────────────────────────────
print("\nRunning clean-box replay (k=0..14)...")
records = []      # per box event
per_window = {}   # ws -> list of box/strand pnls

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
    window_pnl_list = []

    for k in range(15):
        b0 = bid_path[k]
        a0 = ask_path[k]
        if np.isnan(b0) or np.isnan(a0):
            continue
        mid = (b0 + a0) / 2.0
        if not (0.02 <= mid <= 0.98):
            continue
        spread = a0 - b0
        if spread < 0 or spread > 0.20:   # sanity check
            continue

        lo = ws + 60 * (k + 1)
        hi = ws + 60 * (k + 2)
        i0 = int(np.searchsorted(t_arr, lo))
        i1 = int(np.searchsorted(t_arr, hi))

        got_b = got_a = False
        b_time = a_time = None
        b_sz = a_sz = 0.0

        for i in range(i0, i1):
            p = float(p_arr[i])
            buy = bool(buy_arr[i])
            sz = float(sz_arr[i])
            tf = float(t_arr[i])
            if not got_b and not buy and p <= b0 + 1e-9:
                got_b = True; b_time = tf; b_sz = sz
            if not got_a and buy and p >= a0 - 1e-9:
                got_a = True; a_time = tf; a_sz = sz
            if got_b and got_a:
                break

        abs_tilt = abs(mid - 0.5)
        lock = a0 - b0  # spread = box lock = max profit per unit

        if got_b and got_a:
            # Full box
            box_pnl = (res - b0) + (a0 - res)  # = a0 - b0 = lock (no directional risk)
            realized_c = box_pnl * 100
            rec = {
                "ws": ws, "split": split, "k": k,
                "mid": mid, "abs_tilt": abs_tilt, "lock": lock,
                "outcome": "box",
                "realized_c": realized_c,
                "b0": b0, "a0": a0, "res": res,
            }
            records.append(rec)
            window_pnl_list.append(realized_c)

        elif got_b and not got_a:
            # YES strand: bought YES at b0, settled to res
            strand_pnl = res - b0
            realized_c = strand_pnl * 100
            rec = {
                "ws": ws, "split": split, "k": k,
                "mid": mid, "abs_tilt": abs_tilt, "lock": lock,
                "outcome": "strand_yes",
                "realized_c": realized_c,
                "b0": b0, "a0": a0, "res": res,
            }
            records.append(rec)
            window_pnl_list.append(realized_c)

        elif got_a and not got_b:
            # NO strand: sold YES at a0, settled to res
            strand_pnl = a0 - res
            realized_c = strand_pnl * 100
            rec = {
                "ws": ws, "split": split, "k": k,
                "mid": mid, "abs_tilt": abs_tilt, "lock": lock,
                "outcome": "strand_no",
                "realized_c": realized_c,
                "b0": b0, "a0": a0, "res": res,
            }
            records.append(rec)
            window_pnl_list.append(realized_c)

    if window_pnl_list:
        per_window[ws] = window_pnl_list

df = pd.DataFrame(records)
print(f"Total events: {len(df)}  boxes={len(df[df['outcome']=='box'])}  "
      f"strand_yes={len(df[df['outcome']=='strand_yes'])}  "
      f"strand_no={len(df[df['outcome']=='strand_no'])}")


# ─── Per-window PnL aggregation (for Sharpe calc) ───────────────────────────
def window_pnls_for(subset_df):
    """Sum realized_c per window for a given sub-dataframe of events."""
    if len(subset_df) == 0:
        return np.array([])
    gp = subset_df.groupby("ws")["realized_c"].sum()
    return gp.values


def sharpe(arr_vals):
    if len(arr_vals) < 3:
        return float("nan")
    m = np.mean(arr_vals)
    s = np.std(arr_vals, ddof=1)
    if s < 1e-9:
        return float("nan")
    return m / s


def stats(subset_df, label=""):
    """Compute stats for a subset of events."""
    if len(subset_df) == 0:
        return {
            "label": label, "n_events": 0, "n_boxes": 0, "n_windows": 0,
            "p_both": float("nan"), "strand_pct": float("nan"),
            "mean_lock_c": float("nan"), "mean_net_c": float("nan"),
            "std_c": float("nan"), "win_rate": float("nan"),
            "sharpe": float("nan"), "n_for_sharpe": 0,
        }
    is_box = subset_df["outcome"] == "box"
    is_strand = ~is_box
    n_events = len(subset_df)
    n_boxes = is_box.sum()
    n_strands = is_strand.sum()
    n_windows = subset_df["ws"].nunique()

    p_both = n_boxes / n_events if n_events > 0 else float("nan")
    strand_pct = n_strands / n_events if n_events > 0 else float("nan")
    mean_lock_c = subset_df.loc[is_box, "lock"].mean() * 100 if n_boxes > 0 else float("nan")
    mean_net_c = subset_df["realized_c"].mean()
    std_c = subset_df["realized_c"].std(ddof=1)
    win_rate = (subset_df["realized_c"] > 0).mean()

    # Per-window Sharpe
    wp = window_pnls_for(subset_df)
    sh = sharpe(wp)

    return {
        "label": label, "n_events": n_events, "n_boxes": n_boxes,
        "n_windows": n_windows,
        "p_both": p_both, "strand_pct": strand_pct,
        "mean_lock_c": mean_lock_c, "mean_net_c": mean_net_c,
        "std_c": std_c, "win_rate": win_rate,
        "sharpe": sh, "n_for_sharpe": len(wp),
    }


def fmt_stats(s):
    return (
        f"  n_events={s['n_events']:4d}  n_boxes={s['n_boxes']:4d}  n_windows={s['n_windows']:3d}  "
        f"P(both)={s['p_both']:.3f}  strand%={s['strand_pct']:.3f}  "
        f"lock={s['mean_lock_c']:.2f}c  net={s['mean_net_c']:.2f}c  "
        f"win%={s['win_rate']:.3f}  Sharpe={s['sharpe']:.3f}  (n_w={s['n_for_sharpe']})"
    )


# ─── BASELINE (always-on, all k, all prices) ────────────────────────────────
print("\n" + "="*80)
print("ALWAYS-ON BASELINE (k=0..14, all prices)")
print("="*80)
for split in ["IS", "OOS", "ALL"]:
    sub = df if split == "ALL" else df[df["split"] == split]
    s = stats(sub, f"always-on {split}")
    print(f"  {split:3s}: {fmt_stats(s)}")


# ─── PRICE TILT BINS ─────────────────────────────────────────────────────────
print("\n" + "="*80)
print("BY |p-0.5| TILT BINS (0.05-wide, symmetric around 0.5)")
print("="*80)
tilt_bins = [(0.00, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 0.20),
             (0.20, 0.25), (0.25, 0.30), (0.30, 0.35), (0.35, 0.40),
             (0.40, 0.45), (0.45, 0.50)]

tilt_results = {}
for lo_t, hi_t in tilt_bins:
    mask = (df["abs_tilt"] >= lo_t) & (df["abs_tilt"] < hi_t)
    bin_label = f"{lo_t:.2f}-{hi_t:.2f}"
    row = {"bin": bin_label}
    for split in ["IS", "OOS"]:
        sub = df[mask & (df["split"] == split)]
        s = stats(sub)
        row[f"n_{split}"] = s["n_events"]
        row[f"p_both_{split}"] = s["p_both"]
        row[f"net_c_{split}"] = s["mean_net_c"]
        row[f"sharpe_{split}"] = s["sharpe"]
        row[f"n_w_{split}"] = s["n_for_sharpe"]
    tilt_results[bin_label] = row
    print(f"  tilt={bin_label}:")
    for split in ["IS", "OOS"]:
        sub = df[mask & (df["split"] == split)]
        s = stats(sub, f"tilt={bin_label} {split}")
        print(f"    {split}: {fmt_stats(s)}")

# ─── P1 VERDICT: TILT ZONE 0.25-0.40 ─────────────────────────────────────────
print("\n" + "="*80)
print("P1 VERDICT: Tilt zone |p-0.5| in [0.25, 0.40]")
print("="*80)
p1_mask = (df["abs_tilt"] >= 0.25) & (df["abs_tilt"] < 0.40)
anti_p1_mask = ~p1_mask & (df["abs_tilt"] < 0.50)
for split in ["IS", "OOS"]:
    sub_p1 = df[p1_mask & (df["split"] == split)]
    sub_anti = df[anti_p1_mask & (df["split"] == split)]
    s_p1 = stats(sub_p1, f"P1 tilt zone {split}")
    s_anti = stats(sub_anti, f"non-P1 tilt {split}")
    print(f"\n  Tilt zone [0.25,0.40) {split}: {fmt_stats(s_p1)}")
    print(f"  Non-tilt zone {split}:          {fmt_stats(s_anti)}")


# ─── BY K-SLOT ───────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("BY K-SLOT (0..14)")
print("="*80)
k_results = {}
for k in range(15):
    kmask = df["k"] == k
    row = {"k": k}
    for split in ["IS", "OOS"]:
        sub = df[kmask & (df["split"] == split)]
        s = stats(sub)
        row[f"n_{split}"] = s["n_events"]
        row[f"net_c_{split}"] = s["mean_net_c"]
        row[f"sharpe_{split}"] = s["sharpe"]
    k_results[k] = row
    sub_is = df[kmask & (df["split"] == "IS")]
    sub_oos = df[kmask & (df["split"] == "OOS")]
    s_is = stats(sub_is)
    s_oos = stats(sub_oos)
    print(f"  k={k:2d}: IS: {fmt_stats(s_is)}")
    print(f"        OOS:{fmt_stats(s_oos)}")

# ─── P2 VERDICT: EARLY k=0..2 ─────────────────────────────────────────────────
print("\n" + "="*80)
print("P2 VERDICT: Early k=0..2 vs later k=3..14")
print("="*80)
p2_mask = df["k"] <= 2
anti_p2_mask = df["k"] > 2
for split in ["IS", "OOS"]:
    sub_p2 = df[p2_mask & (df["split"] == split)]
    sub_late = df[anti_p2_mask & (df["split"] == split)]
    s_p2 = stats(sub_p2, f"P2 k=0..2 {split}")
    s_late = stats(sub_late, f"k=3..14 {split}")
    print(f"\n  Early k=0..2 {split}: {fmt_stats(s_p2)}")
    print(f"  Later k=3..14 {split}: {fmt_stats(s_late)}")


# ─── 2D k x TILT GRID ────────────────────────────────────────────────────────
print("\n" + "="*80)
print("2D k x TILT GRID (IS Sharpe + net c/win)")
print("="*80)
grid_is = {}
grid_oos = {}
for k in range(15):
    for lo_t, hi_t in tilt_bins:
        mask = (df["k"] == k) & (df["abs_tilt"] >= lo_t) & (df["abs_tilt"] < hi_t)
        bin_label = f"{lo_t:.2f}-{hi_t:.2f}"
        for split, gd in [("IS", grid_is), ("OOS", grid_oos)]:
            sub = df[mask & (df["split"] == split)]
            s = stats(sub)
            gd[(k, bin_label)] = s

# Print grid (IS Sharpe)
print("\nIS Sharpe by k x tilt (requires >=5 windows):")
header = "k\\tilt  " + "  ".join(f"{lo:.2f}-{hi:.2f}" for lo, hi in tilt_bins)
print(header)
for k in range(15):
    row_vals = []
    for lo_t, hi_t in tilt_bins:
        bin_label = f"{lo_t:.2f}-{hi_t:.2f}"
        s = grid_is[(k, bin_label)]
        if s["n_for_sharpe"] >= 5:
            row_vals.append(f"{s['sharpe']:+.2f}")
        else:
            row_vals.append("  nan")
    print(f"  k={k:2d}:  " + "  ".join(row_vals))

print("\nIS net c/event by k x tilt (requires >=5 windows):")
print(header)
for k in range(15):
    row_vals = []
    for lo_t, hi_t in tilt_bins:
        bin_label = f"{lo_t:.2f}-{hi_t:.2f}"
        s = grid_is[(k, bin_label)]
        if s["n_events"] >= 5:
            row_vals.append(f"{s['mean_net_c']:+.1f}")
        else:
            row_vals.append("  nan")
    print(f"  k={k:2d}:  " + "  ".join(row_vals))


# ─── FIND BEST k x TILT RULE ─────────────────────────────────────────────────
print("\n" + "="*80)
print("FINDING BEST k x PRICE RULE (maximize IS Sharpe, min 5 IS windows)")
print("="*80)

# Single k + single tilt bin
best_is_sharpe = -999
best_rule = None
candidate_rules = []

for k in range(15):
    for lo_t, hi_t in tilt_bins:
        bin_label = f"{lo_t:.2f}-{hi_t:.2f}"
        s_is = grid_is[(k, bin_label)]
        s_oos = grid_oos[(k, bin_label)]
        if s_is["n_for_sharpe"] < 5:
            continue
        candidate_rules.append({
            "k": k, "tilt_bin": bin_label, "lo_t": lo_t, "hi_t": hi_t,
            "is_sharpe": s_is["sharpe"], "is_net_c": s_is["mean_net_c"],
            "is_n": s_is["n_events"], "is_n_w": s_is["n_for_sharpe"],
            "oos_sharpe": s_oos["sharpe"], "oos_net_c": s_oos["mean_net_c"],
            "oos_n": s_oos["n_events"], "oos_n_w": s_oos["n_for_sharpe"],
        })

cdf = pd.DataFrame(candidate_rules).sort_values("is_sharpe", ascending=False)
print("\nTop 10 single-k x single-bin rules by IS Sharpe:")
print(f"{'k':>4} {'tilt_bin':>12} {'IS_Sh':>7} {'IS_net':>7} {'IS_n':>5} {'IS_nw':>5} "
      f"{'OOS_Sh':>7} {'OOS_net':>8} {'OOS_n':>5} {'OOS_nw':>6}")
for _, row in cdf.head(10).iterrows():
    oos_sh_str = f"{row['oos_sharpe']:+.3f}" if not np.isnan(row['oos_sharpe']) else "   nan"
    oos_net_str = f"{row['oos_net_c']:+.2f}" if not np.isnan(row['oos_net_c']) else "   nan"
    print(f"  k={int(row['k']):2d}  tilt={row['tilt_bin']}  IS_Sh={row['is_sharpe']:+.3f}  "
          f"IS_net={row['is_net_c']:+.2f}c  IS_n={int(row['is_n'])}  IS_nw={int(row['is_n_w'])}  "
          f"OOS_Sh={oos_sh_str}  OOS_net={oos_net_str}c  OOS_n={int(row['oos_n'])}  OOS_nw={int(row['oos_n_w'])}")

# Also: multi-k range with tilt filter
print("\n--- Multi-k range x tilt combinations ---")
multi_rules = []
tilt_ranges = [
    ("P1_tilt_0.25-0.40", 0.25, 0.40),
    ("near_0.30-0.45", 0.30, 0.45),
    ("mid_0.15-0.35", 0.15, 0.35),
    ("near-atm_0.00-0.15", 0.00, 0.15),
    ("all_prices", 0.00, 0.50),
    ("outer_0.35-0.50", 0.35, 0.50),
]
k_ranges = [
    ("early_k0-2", 0, 2),
    ("mid_k3-7", 3, 7),
    ("late_k8-14", 8, 14),
    ("all_k", 0, 14),
    ("k0-5", 0, 5),
    ("k6-14", 6, 14),
    ("k3-10", 3, 10),
]

for tilt_label, tlo, thi in tilt_ranges:
    for k_label, klo, khi in k_ranges:
        tmask = (df["abs_tilt"] >= tlo) & (df["abs_tilt"] < thi)
        kmask = (df["k"] >= klo) & (df["k"] <= khi)
        combo_mask = tmask & kmask
        for split, gd in [("IS", {}), ("OOS", {})]:
            pass  # will do inline

        is_sub = df[combo_mask & (df["split"] == "IS")]
        oos_sub = df[combo_mask & (df["split"] == "OOS")]
        s_is = stats(is_sub)
        s_oos = stats(oos_sub)
        if s_is["n_for_sharpe"] < 5:
            continue
        multi_rules.append({
            "tilt": tilt_label, "k_range": k_label,
            "is_sharpe": s_is["sharpe"], "is_net_c": s_is["mean_net_c"],
            "is_n": s_is["n_events"], "is_n_w": s_is["n_for_sharpe"],
            "oos_sharpe": s_oos["sharpe"], "oos_net_c": s_oos["mean_net_c"],
            "oos_n": s_oos["n_events"], "oos_n_w": s_oos["n_for_sharpe"],
        })

mdf = pd.DataFrame(multi_rules).sort_values("is_sharpe", ascending=False)
print(f"\n{'tilt_range':>25} {'k_range':>12} {'IS_Sh':>7} {'IS_net':>7} {'IS_nw':>6} "
      f"{'OOS_Sh':>7} {'OOS_net':>8} {'OOS_nw':>7}")
for _, row in mdf.head(15).iterrows():
    oos_sh_str = f"{row['oos_sharpe']:+.3f}" if not np.isnan(row['oos_sharpe']) else "    nan"
    oos_net_str = f"{row['oos_net_c']:+.2f}" if not np.isnan(row['oos_net_c']) else "    nan"
    print(f"  {row['tilt']:>23}  {row['k_range']:>12}  IS={row['is_sharpe']:+.3f}  "
          f"IS_net={row['is_net_c']:+.2f}c  IS_nw={int(row['is_n_w'])}  "
          f"OOS={oos_sh_str}  OOS_net={oos_net_str}c  OOS_nw={int(row['oos_n_w'])}")


# ─── RECOMMENDED RULE vs PRIORS ────────────────────────────────────────────
print("\n" + "="*80)
print("RECOMMENDED RULE vs PRIORS COMPARISON")
print("="*80)

# Find best combined multi rule with IS Sharpe AND positive OOS
valid_oos = mdf[(mdf["oos_n_w"] >= 3) & (~mdf["oos_sharpe"].isna())]
valid_oos_pos = valid_oos[valid_oos["oos_sharpe"] > 0].sort_values("is_sharpe", ascending=False)

print("\nBest rules with positive OOS Sharpe (sorted by IS Sharpe):")
for _, row in valid_oos_pos.head(5).iterrows():
    oos_sh_str = f"{row['oos_sharpe']:+.3f}" if not np.isnan(row['oos_sharpe']) else "    nan"
    oos_net_str = f"{row['oos_net_c']:+.2f}" if not np.isnan(row['oos_net_c']) else "    nan"
    print(f"  tilt={row['tilt']:>25}  k={row['k_range']:>12}  IS_Sh={row['is_sharpe']:+.3f}  "
          f"IS_net={row['is_net_c']:+.2f}c  OOS_Sh={oos_sh_str}  OOS_net={oos_net_str}c")

# Specific comparisons to priors
print("\n--- SPECIFIC PRIOR COMPARISONS ---")
comparison_labels = {
    "always-on": (0.0, 0.5, 0, 14),
    "P1 tilt [0.25,0.40)": (0.25, 0.40, 0, 14),
    "P2 early k=0..2": (0.0, 0.5, 0, 2),
    "P1+P2 combo": (0.25, 0.40, 0, 2),
}
print(f"\n{'rule':>30} {'IS_Sh':>7} {'IS_net':>7} {'IS_nw':>6} {'OOS_Sh':>7} {'OOS_net':>8} {'OOS_nw':>7}")
for label, (tlo, thi, klo, khi) in comparison_labels.items():
    tmask = (df["abs_tilt"] >= tlo) & (df["abs_tilt"] < thi)
    kmask = (df["k"] >= klo) & (df["k"] <= khi)
    combo = tmask & kmask
    s_is = stats(df[combo & (df["split"] == "IS")])
    s_oos = stats(df[combo & (df["split"] == "OOS")])
    oos_sh_str = f"{s_oos['sharpe']:+.3f}" if not np.isnan(s_oos["sharpe"]) else "    nan"
    oos_net_str = f"{s_oos['mean_net_c']:+.2f}" if not np.isnan(s_oos["mean_net_c"]) else "    nan"
    print(f"  {label:>28}: IS_Sh={s_is['sharpe']:+.3f}  IS_net={s_is['mean_net_c']:+.2f}c  "
          f"IS_nw={s_is['n_for_sharpe']}  OOS_Sh={oos_sh_str}  OOS_net={oos_net_str}c  "
          f"OOS_nw={s_oos['n_for_sharpe']}")


# ─── MECHANISM INSIGHT: Lock vs Tilt Correlation ──────────────────────────────
print("\n" + "="*80)
print("MECHANISM INSIGHT: Lock/spread analysis")
print("="*80)
boxes_only = df[df["outcome"] == "box"]
if len(boxes_only) > 0:
    print(f"\nBox-only events: {len(boxes_only)}")
    print(f"Lock (spread) statistics:")
    print(f"  mean lock: {boxes_only['lock'].mean()*100:.2f}c")
    print(f"  median lock: {boxes_only['lock'].median()*100:.2f}c")
    print(f"  lock vs abs_tilt correlation: {boxes_only['lock'].corr(boxes_only['abs_tilt']):.3f}")
    print(f"  lock vs k correlation: {boxes_only['lock'].corr(boxes_only['k'].astype(float)):.3f}")

    # By tilt quartiles
    print("\nLock by tilt band (boxes only):")
    for lo_t, hi_t in tilt_bins:
        sub = boxes_only[(boxes_only["abs_tilt"] >= lo_t) & (boxes_only["abs_tilt"] < hi_t)]
        if len(sub) > 0:
            print(f"  tilt={lo_t:.2f}-{hi_t:.2f}: n={len(sub):3d}  "
                  f"mean_lock={sub['lock'].mean()*100:.2f}c  "
                  f"mean_realized={sub['realized_c'].mean():.2f}c")

# ─── STRAND ANALYSIS ─────────────────────────────────────────────────────────
print("\n" + "="*80)
print("STRAND ANALYSIS by tilt and k")
print("="*80)
print("\nStrand YES vs NO by tilt bin (IS+OOS):")
for lo_t, hi_t in tilt_bins:
    mask = (df["abs_tilt"] >= lo_t) & (df["abs_tilt"] < hi_t)
    sy = df[mask & (df["outcome"] == "strand_yes")]
    sn = df[mask & (df["outcome"] == "strand_no")]
    bx = df[mask & (df["outcome"] == "box")]
    total = len(df[mask])
    if total == 0:
        continue
    print(f"  tilt={lo_t:.2f}-{hi_t:.2f}: boxes={len(bx):3d} ({len(bx)/total:.2f})  "
          f"strand_yes={len(sy):3d} ({sy['realized_c'].mean():+.2f}c mean)  "
          f"strand_no={len(sn):3d} ({sn['realized_c'].mean():+.2f}c mean)")

# ─── FINAL SUMMARY TABLE ─────────────────────────────────────────────────────
print("\n" + "="*80)
print("FINAL SUMMARY TABLE")
print("="*80)

# Collect key rules
summary_rules = {
    "always-on (baseline)": (0.0, 0.5, 0, 14),
    "P1: tilt [0.25,0.40)": (0.25, 0.40, 0, 14),
    "P2: k=0..2": (0.0, 0.5, 0, 2),
    "P1+P2: tilt+early": (0.25, 0.40, 0, 2),
    "near-ATM [0.00,0.15)": (0.0, 0.15, 0, 14),
    "tilt [0.30,0.45)": (0.30, 0.45, 0, 14),
    "tilt [0.35,0.50) all-k": (0.35, 0.50, 0, 14),
    "tilt [0.25,0.40) k=3-10": (0.25, 0.40, 3, 10),
}

print(f"\n{'rule':>35} | {'IS_Sh':>7} {'IS_net':>7} {'IS_nw':>6} | {'OOS_Sh':>7} {'OOS_net':>8} {'OOS_nw':>7}")
print("-" * 90)
for label, (tlo, thi, klo, khi) in summary_rules.items():
    tmask = (df["abs_tilt"] >= tlo) & (df["abs_tilt"] < thi)
    kmask = (df["k"] >= klo) & (df["k"] <= khi)
    combo = tmask & kmask
    s_is = stats(df[combo & (df["split"] == "IS")])
    s_oos = stats(df[combo & (df["split"] == "OOS")])
    oos_sh_str = f"{s_oos['sharpe']:+.3f}" if not np.isnan(s_oos["sharpe"]) else "    nan"
    oos_net_str = f"{s_oos['mean_net_c']:+.2f}" if not np.isnan(s_oos["mean_net_c"]) else "    nan"
    print(f"  {label:>33} | IS={s_is['sharpe']:+.3f}  {s_is['mean_net_c']:+.2f}c  {s_is['n_for_sharpe']:>5} | "
          f"OOS={oos_sh_str}  {oos_net_str}c  {s_oos['n_for_sharpe']:>6}")

print("\n[Done]")
