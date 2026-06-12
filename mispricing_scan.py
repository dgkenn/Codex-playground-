import numpy as np
import pandas as pd
from scipy.stats import norm, linregress
from statsmodels.stats.proportion import proportion_confint
from statsmodels.stats.multitest import multipletests
import math
import warnings
warnings.filterwarnings('ignore')

# ── 1. Load & pool ────────────────────────────────────────────────────────────
assets = ['btc', 'eth', 'sol', 'xrp']
frames = []
for a in assets:
    path = f'/home/user/Codex-playground-/hist_kalshi_{a}15m.parquet'
    df = pd.read_parquet(path)
    if 'ws' in df.columns:
        df = df.set_index('ws')
    df['asset'] = a
    frames.append(df)
raw = pd.concat(frames)

# ── 2. Expand array columns into long form ────────────────────────────────────
for col in ['mid_path', 'bid_path', 'ask_path']:
    raw[col] = raw[col].apply(lambda x: np.array(x))

# Sort by index to ensure time ordering for IS/OOS split
raw = raw.sort_index()

n_windows = len(raw)
split_idx = int(0.60 * n_windows)
is_set = set(raw.index[:split_idx])

rows = []
for minute in range(2, 15):
    mid_arr = np.stack(raw['mid_path'].values)[:, minute]
    bid_arr = np.stack(raw['bid_path'].values)[:, minute]
    ask_arr = np.stack(raw['ask_path'].values)[:, minute]
    tmp = pd.DataFrame({
        'win_idx': raw.index,
        'res_up': raw['res_up'].values,
        'minute': minute,
        'mid': mid_arr,
        'bid': bid_arr,
        'ask': ask_arr,
    })
    rows.append(tmp)

long = pd.concat(rows, ignore_index=True)
long = long.dropna(subset=['mid', 'res_up'])
long['res_up'] = long['res_up'].astype(float)
long['is_sample'] = long['win_idx'].isin(is_set)

# ── 3. Bucket assignment ──────────────────────────────────────────────────────
def assign_bucket(mid_val):
    if mid_val < 0.10 or mid_val > 0.90:
        # fine 0.01-wide buckets
        c = math.floor(mid_val / 0.01) * 0.01 + 0.005
        return round(c, 4)
    else:
        # coarse 0.05-wide buckets
        c = math.floor(mid_val / 0.05) * 0.05 + 0.025
        return round(c, 4)

long['bucket'] = long['mid'].apply(assign_bucket)

# ── 4. Per-(minute, bucket) stats ─────────────────────────────────────────────
records = []
grouped = long.groupby(['minute', 'bucket'])

for (minute, bucket), grp in grouped:
    n = len(grp)
    if n < 30:
        continue
    implied = grp['mid'].mean()
    if implied <= 0 or implied >= 1:
        continue
    realized = grp['res_up'].mean()
    n_yes = int(round(realized * n))

    ci_lo, ci_hi = proportion_confint(count=n_yes, nobs=n, alpha=0.05, method='wilson')
    misprice = realized - implied

    # raw_sig: Wilson CI excludes implied
    raw_sig = (ci_lo > implied) or (ci_hi < implied)

    # p-value from normal approximation
    denom = math.sqrt(implied * (1 - implied) / n)
    z = misprice / denom if denom > 0 else 0.0
    pval = 2 * (1 - norm.cdf(abs(z)))

    # IS / OOS split
    grp_oos = grp[~grp['is_sample']]
    oos_realized = grp_oos['res_up'].mean() if len(grp_oos) > 0 else np.nan
    oos_misprice = oos_realized - implied if not np.isnan(oos_realized) else np.nan
    oos_stable_raw = (
        (not np.isnan(oos_misprice)) and
        (np.sign(oos_misprice) == np.sign(misprice)) and
        (abs(oos_misprice) > 0)
    )

    # Economic translation
    edge = abs(misprice)
    # Taker fee = ceil(0.07 * p * (1-p)) in cents → convert to dollars
    taker_fee_raw = 0.07 * implied * (1 - implied)
    taker_fee_d = math.ceil(taker_fee_raw * 100) / 100
    net_edge_taker = edge - taker_fee_d
    taker_only = net_edge_taker <= 0
    maker_capturable = edge > 0

    side = 'BUY YES' if misprice > 0 else 'SELL YES / BUY NO'

    records.append({
        'minute': minute,
        'bucket': bucket,
        'n': n,
        'realized': round(realized, 4),
        'implied': round(implied, 4),
        'misprice': round(misprice, 4),
        'CI_lo': round(ci_lo, 4),
        'CI_hi': round(ci_hi, 4),
        'raw_sig': raw_sig,
        'pval': pval,
        'oos_stable_raw': oos_stable_raw,
        'edge': edge,
        'taker_fee': taker_fee_d,
        'net_edge_taker': net_edge_taker,
        'net_maker_edge': edge,
        'maker_capturable': maker_capturable,
        'taker_only': taker_only,
        'side': side,
    })

res = pd.DataFrame(records)

# ── 5. Multiple testing (BH FDR at q=0.05) ───────────────────────────────────
if len(res) > 0:
    pvals = res['pval'].values
    reject, pvals_corrected, _, _ = multipletests(pvals, alpha=0.05, method='fdr_bh')
    res['FDR_sig'] = reject
    res['pval_corrected'] = pvals_corrected
else:
    res['FDR_sig'] = False
    res['pval_corrected'] = np.nan

res['OOS_stable'] = res['FDR_sig'] & res['oos_stable_raw']

# ── 6. Favorite-Longshot regression ──────────────────────────────────────────
tail_mask = (long['mid'] < 0.10) | (long['mid'] > 0.90)
tail_data = long[tail_mask]
fl_slope, fl_intercept, fl_r, fl_pval, fl_se = linregress(
    tail_data['mid'].values, tail_data['res_up'].values
)
fl_n = len(tail_data)

# ── PRINT SECTION ─────────────────────────────────────────────────────────────

# A) Calibration summary for tail buckets (bucket < 0.15 or bucket > 0.85)
tail_res = res[(res['bucket'] < 0.15) | (res['bucket'] > 0.85)].copy()
tail_res = tail_res.sort_values('misprice', key=abs, ascending=False).head(20)
display_cols = ['minute', 'bucket', 'n', 'realized', 'implied', 'misprice',
                'CI_lo', 'CI_hi', 'raw_sig', 'FDR_sig']
print("=== A) Tail Calibration Summary (top 20 by |misprice|) ===")
print(tail_res[display_cols].to_string(index=False))
print()

# B) Favorite-longshot regression
print("=== B) Favorite-Longshot Regression ===")
print(f"Fav-longshot slope: {fl_slope:.4f}, p={fl_pval:.4e}, n={fl_n}")
print()

# C) Counts
raw_sig_count = int(res['raw_sig'].sum())
fdr_sig_count = int(res['FDR_sig'].sum())
oos_stable_count = int(res['OOS_stable'].sum())
print("=== C) Counts ===")
print(f"raw_sig={raw_sig_count}, FDR_sig={fdr_sig_count}, OOS_stable={oos_stable_count}")
print()

# D) Best single FDR-surviving bucket (by net maker edge)
fdr_survivors = res[res['FDR_sig']].copy()
print("=== D) Best FDR-Surviving Bucket ===")
if len(fdr_survivors) > 0:
    best = fdr_survivors.sort_values('net_maker_edge', ascending=False).iloc[0]
    maker_or_taker = 'taker_only' if best['taker_only'] else 'maker_capturable'
    print(f"Best bucket: minute={int(best['minute'])}, price={best['implied']:.2f}, "
          f"side={best['side']}, edge={best['edge']:.4f} ({maker_or_taker})")
else:
    print("None")
print()

# E) All FDR-surviving OOS-stable buckets
oos_stable_rows = res[res['OOS_stable']].copy()
print("=== E) FDR-Surviving OOS-Stable Buckets ===")
if len(oos_stable_rows) == 0:
    print("None")
else:
    ecols = ['minute', 'bucket', 'n', 'realized', 'implied', 'misprice',
             'CI_lo', 'CI_hi', 'raw_sig', 'FDR_sig', 'side', 'net_maker_edge']
    oos_stable_rows = oos_stable_rows.sort_values('net_maker_edge', ascending=False)
    print(oos_stable_rows[ecols].to_string(index=False))
