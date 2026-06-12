"""
late_fav_test.py — Late-window favorite-bid maker strategy backtest
on Kalshi 15-min BTC binaries (KXBTC15M).
"""

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────

def load_parquet_robust(path):
    df = pd.read_parquet(path)
    if df.index.name == 'ws' or (df.index.name is not None and 'ws' not in df.columns):
        df = df.reset_index()
    return df

hist = load_parquet_robust('/home/user/Codex-playground-/hist_kalshi_btc15m.parquet')
trades = load_parquet_robust('/home/user/Codex-playground-/trades_kalshi_btc15m.parquet')

# Ensure ws is int64
hist['ws'] = hist['ws'].astype(np.int64)
trades['ws'] = trades['ws'].astype(np.int64)

# Build trades lookup: ws -> (t_arr, p_arr, sz_arr, buy_arr)
trades_dict = {}
for _, row in trades.iterrows():
    ws = int(row['ws'])
    t_arr  = np.asarray(row['t'],   dtype=np.float64)
    p_arr  = np.asarray(row['p'],   dtype=np.float64)
    sz_arr = np.asarray(row['sz'],  dtype=np.float64)
    buy_arr = np.asarray(row['buy'], dtype=bool)
    trades_dict[ws] = (t_arr, p_arr, sz_arr, buy_arr)

print(f"Hist: {hist.shape[0]} windows | Trades: {len(trades_dict)} windows with trade data")

# Diagnostics
sample_bid = np.asarray(hist['bid_path'].iloc[0])
sample_spot = np.asarray(hist['spot_path'].iloc[0])
print(f"bid_path sample len={len(sample_bid)}, spot_path sample len={len(sample_spot)}")
print(f"ws range: {hist['ws'].min()} – {hist['ws'].max()}")
n_days = hist['ws'].map(lambda x: pd.Timestamp(x, unit='s').date()).nunique()
print(f"Unique dates: {n_days}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# 2. CORE LOOP — build per-(ws, k, T) records
# ─────────────────────────────────────────────────────────────────────────────

K_VALUES = [12, 13, 14]
T_VALUES = [0.93, 0.95, 0.97]

records = []  # list of dicts

for _, row in hist.iterrows():
    ws = int(row['ws'])
    res_up = bool(row['res_up'])

    try:
        bid_path  = np.asarray(row['bid_path'],  dtype=np.float64)
        ask_path  = np.asarray(row['ask_path'],  dtype=np.float64)
        spot_path = np.asarray(row['spot_path'], dtype=np.float64)
    except Exception:
        continue

    if len(bid_path) < 15 or len(ask_path) < 15 or len(spot_path) < 15:
        continue
    if np.any(np.isnan(bid_path)) or np.any(np.isnan(ask_path)) or np.any(np.isnan(spot_path)):
        continue

    # sigma for z-score (use pct changes of all 15 spot points * mean spot)
    pct_ch = np.diff(spot_path) / spot_path[:-1]
    sigma_1min = np.std(pct_ch) * np.mean(spot_path) if len(pct_ch) > 1 else 1.0
    if sigma_1min <= 0 or np.isnan(sigma_1min):
        sigma_1min = 1.0

    strike = spot_path[0]

    # trades for this ws
    td = trades_dict.get(ws)

    for k in K_VALUES:
        try:
            mid_k  = (bid_path[k] + ask_path[k]) / 2.0
            bid_k  = bid_path[k]
            ask_k  = ask_path[k]
        except Exception:
            continue
        if np.isnan(mid_k) or np.isnan(bid_k) or np.isnan(ask_k):
            continue

        fav_yes = mid_k > 0.5
        fav_price = mid_k if fav_yes else (1.0 - mid_k)

        # z-score
        spot_k = spot_path[k]
        minutes_left = 14 - k
        z_abs = abs(spot_k - strike) / (sigma_1min * np.sqrt(max(minutes_left, 1)))

        for T in T_VALUES:
            if fav_price < T:
                continue  # not qualifying

            # Our bid price
            if fav_yes:
                our_bid = bid_k
            else:
                our_bid = 1.0 - ask_k  # NO bid price = 1 - ask (YES side)

            # Fill-through search
            contracts_filled = 0.0
            has_fill = False

            if td is not None:
                t_arr, p_arr, sz_arr, buy_arr = td
                # window for remaining time: ws + 60*k  through  ws + 900
                t_start = ws + 60 * k
                t_end   = ws + 900
                mask_time = (t_arr >= t_start) & (t_arr <= t_end)

                if fav_yes:
                    # taker sells YES (buy=False) at price <= our bid
                    mask_fill = mask_time & (~buy_arr) & (p_arr <= bid_k)
                else:
                    # taker buys YES (buy=True) at price >= ask_k
                    # (they lift the ask on YES side => hits our NO bid)
                    mask_fill = mask_time & (buy_arr) & (p_arr >= ask_k)

                if np.any(mask_fill):
                    contracts_filled = np.sum(sz_arr[mask_fill]) / 100.0
                    has_fill = True

            # PnL
            fav_wins = res_up if fav_yes else (not res_up)
            pnl_per_contract = (1.0 - our_bid) if fav_wins else (-our_bid)

            records.append({
                'ws': ws,
                'k': k,
                'T': T,
                'fav_yes': fav_yes,
                'fav_price': fav_price,
                'our_bid': our_bid,
                'has_fill': has_fill,
                'contracts': contracts_filled,
                'fav_wins': fav_wins,
                'pnl_per_contract': pnl_per_contract,
                'z_abs': z_abs,
                'date': pd.Timestamp(ws, unit='s').date(),
            })

df = pd.DataFrame(records)
print(f"Total qualifying (window, k, T) combos: {len(df)}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# 3. ANALYSIS 1 — FILL OPPORTUNITY
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("ANALYSIS 1 — FILL OPPORTUNITY")
print("=" * 70)
hdr = f"{'k':>3} {'T':>5} | {'qual/day':>9} {'fill%':>7} {'med_ctr':>8} {'mean_ctr':>9}"
print(hdr)
print("-" * 55)

for k in K_VALUES:
    for T in T_VALUES:
        sub = df[(df['k'] == k) & (df['T'] == T)]
        if len(sub) == 0:
            continue
        n_days_sub = sub['date'].nunique()
        qual_per_day = len(sub) / n_days_sub if n_days_sub > 0 else 0
        fill_pct = sub['has_fill'].mean() * 100
        filled = sub[sub['has_fill']]
        med_ctr  = filled['contracts'].median() if len(filled) > 0 else 0.0
        mean_ctr = filled['contracts'].mean()   if len(filled) > 0 else 0.0
        print(f"{k:>3} {T:>5.2f} | {qual_per_day:>9.2f} {fill_pct:>6.1f}% {med_ctr:>8.2f} {mean_ctr:>9.2f}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# 4. ANALYSIS 2 — REALIZED EV
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("ANALYSIS 2 — REALIZED EV  (fill-through windows, weighted by min(ctr,5))")
print("=" * 70)
hdr2 = (f"{'k':>3} {'T':>5} | {'EV/ctr':>8} {'win%':>7} "
        f"{'flip|fill%':>11} {'flip|qual%':>11} {'adv_sel':>8}")
print(hdr2)
print("-" * 65)

for k in K_VALUES:
    for T in T_VALUES:
        sub = df[(df['k'] == k) & (df['T'] == T)]
        if len(sub) == 0:
            continue

        filled = sub[sub['has_fill']].copy()
        uncond_flip = (1 - sub['fav_wins'].mean()) * 100  # P(fav loses | qualifying)

        if len(filled) == 0:
            print(f"{k:>3} {T:>5.2f} | {'n/a':>8} {'n/a':>7} {'n/a':>11} {uncond_flip:>10.1f}% {'n/a':>8}")
            continue

        weights = np.minimum(filled['contracts'].values, 5.0)
        w_sum = weights.sum()
        if w_sum == 0:
            weights = np.ones(len(filled))
            w_sum = len(filled)

        ev_wtd  = np.average(filled['pnl_per_contract'].values, weights=weights)
        win_pct = np.average(filled['fav_wins'].astype(float).values, weights=weights) * 100
        cond_flip = 100.0 - win_pct          # P(fav loses | fill-through)
        adv_sel   = cond_flip - uncond_flip

        print(f"{k:>3} {T:>5.2f} | {ev_wtd:>8.4f} {win_pct:>6.1f}% "
              f"{cond_flip:>10.1f}% {uncond_flip:>10.1f}% {adv_sel:>+8.2f}%")
print()

# ─────────────────────────────────────────────────────────────────────────────
# 5. ANALYSIS 3 — Z-CONDITIONING
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("ANALYSIS 3 — Z-CONDITIONING  (fill-through events by |z| bucket)")
print("=" * 70)

Z_BUCKETS = [('<1', lambda z: z < 1),
             ('1-2', lambda z: (z >= 1) & (z < 2)),
             ('>2', lambda z: z >= 2)]

hdr3 = f"{'k':>3} {'T':>5} {'|z|':>5} | {'EV/ctr':>8} {'fill%':>7} {'count':>7}"
print(hdr3)
print("-" * 50)

for k in K_VALUES:
    for T in T_VALUES:
        sub = df[(df['k'] == k) & (df['T'] == T)]
        if len(sub) == 0:
            continue
        for zlabel, zmask_fn in Z_BUCKETS:
            z_sub = sub[zmask_fn(sub['z_abs'])]
            if len(z_sub) == 0:
                continue
            fill_pct = z_sub['has_fill'].mean() * 100
            filled_z = z_sub[z_sub['has_fill']]
            if len(filled_z) > 0:
                weights = np.minimum(filled_z['contracts'].values, 5.0)
                w_sum = weights.sum()
                if w_sum == 0:
                    weights = np.ones(len(filled_z))
                ev_wtd = np.average(filled_z['pnl_per_contract'].values, weights=weights)
            else:
                ev_wtd = float('nan')
            print(f"{k:>3} {T:>5.2f} {zlabel:>5} | {ev_wtd:>8.4f} {fill_pct:>6.1f}% {len(z_sub):>7}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# 6. ANALYSIS 4 — IS vs OOS
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("ANALYSIS 4 — IS vs OOS  (60/40 chronological split)")
print("=" * 70)

# Chronological split by ws
all_ws_sorted = np.sort(hist['ws'].unique())
split_idx = int(len(all_ws_sorted) * 0.6)
is_ws  = set(all_ws_sorted[:split_idx].tolist())
oos_ws = set(all_ws_sorted[split_idx:].tolist())

df_is  = df[df['ws'].isin(is_ws)]
df_oos = df[df['ws'].isin(oos_ws)]

def compute_metrics(sub_df, n_days_total):
    """Returns (qual_per_day, fill_rate, mean_ev, ev_per_day) for a subset."""
    if len(sub_df) == 0:
        return (0, 0, float('nan'), 0)
    nd = sub_df['date'].nunique()
    if nd == 0:
        nd = 1
    qual_per_day = len(sub_df) / nd
    fill_rate = sub_df['has_fill'].mean()
    filled = sub_df[sub_df['has_fill']]
    if len(filled) == 0:
        return (qual_per_day, fill_rate, float('nan'), 0)
    weights = np.minimum(filled['contracts'].values, 5.0)
    w_sum = weights.sum()
    if w_sum == 0:
        weights = np.ones(len(filled))
    mean_ev = np.average(filled['pnl_per_contract'].values, weights=weights)
    ev_per_day = qual_per_day * fill_rate * mean_ev
    return (qual_per_day, fill_rate, mean_ev, ev_per_day)

Z_GATES = [
    ('all',  None),
    ('z>=1', 1.0),
    ('z>=2', 2.0),
]

# IS sweep to find best combo
best_ev_day = -np.inf
best_combo  = None
best_is_metrics  = None

is_results = []
for k in K_VALUES:
    for T in T_VALUES:
        for zname, zgate in Z_GATES:
            sub_is = df_is[(df_is['k'] == k) & (df_is['T'] == T)]
            if zgate is not None:
                sub_is = sub_is[sub_is['z_abs'] >= zgate]
            m = compute_metrics(sub_is, None)
            is_results.append((k, T, zname, m))
            if m[3] > best_ev_day:
                best_ev_day = m[3]
                best_combo  = (k, T, zname, zgate)
                best_is_metrics = m

bk, bT, bzname, bzgate = best_combo
sub_oos = df_oos[(df_oos['k'] == bk) & (df_oos['T'] == bT)]
if bzgate is not None:
    sub_oos = sub_oos[sub_oos['z_abs'] >= bzgate]
oos_m = compute_metrics(sub_oos, None)

print(f"Best IS combo: k={bk}, T={bT}, z_gate={bzname}")
print()
print(f"{'Metric':<28} {'IS':>10} {'OOS':>10}")
print("-" * 50)
print(f"{'qual windows/day':<28} {best_is_metrics[0]:>10.2f} {oos_m[0]:>10.2f}")
print(f"{'fill rate':<28} {best_is_metrics[1]*100:>9.1f}% {oos_m[1]*100:>9.1f}%")
print(f"{'mean EV/contract':<28} {best_is_metrics[2]:>10.4f} {oos_m[2]:>10.4f}")
print(f"{'expected EV/day ($)':<28} {best_is_metrics[3]:>10.4f} {oos_m[3]:>10.4f}")
print()

# Full IS sweep table
print("IS sweep — all combos (sorted by EV/day desc):")
hdr4 = f"{'k':>3} {'T':>5} {'z_gate':>6} | {'q/day':>7} {'fill%':>7} {'EV/ctr':>8} {'EV/day':>9}"
print(hdr4)
print("-" * 55)
is_results_sorted = sorted(is_results, key=lambda x: x[3][3], reverse=True)
for (k, T, zname, m) in is_results_sorted[:18]:  # top 18
    mark = " *" if (k == bk and T == bT and zname == bzname) else ""
    ev_str = f"{m[2]:.4f}" if not np.isnan(m[2]) else "  n/a"
    print(f"{k:>3} {T:>5.2f} {zname:>6} | {m[0]:>7.2f} {m[1]*100:>6.1f}% {ev_str:>8} {m[3]:>9.4f}{mark}")
print()
print("Done.")
