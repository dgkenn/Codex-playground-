"""
Q2: Repricing Trade-Off Analysis
When is losing queue priority to chase a better price worth it?

Data: fills_btc15m_*.jsonl files (have bb, ba, micro, q_ahead, mo_res, etc.)
      live_metrics_kalshi_btc15m.jsonl (reshape_qtime events)
"""
import json, glob, os, sys, math
import pandas as pd
import numpy as np
from collections import defaultdict

# ──────────────────────────────────────────────
# 1. LOAD FILLS DATA (rich book + outcome data)
# ──────────────────────────────────────────────
fills_files = sorted(glob.glob('/home/user/Codex-playground-/gha_data/fills_btc15m_*.jsonl'))
print(f"Found {len(fills_files)} fills files")

rows = []
for fp in fills_files:
    with open(fp) as f:
        for line in f:
            try:
                d = json.loads(line)
                rows.append(d)
            except Exception:
                pass

df_fills = pd.DataFrame(rows)
print(f"Total fill-event records: {len(df_fills):,}")
print(f"Columns: {df_fills.columns.tolist()[:20]}")

# ──────────────────────────────────────────────
# 2. LOAD TICKS DATA (sequence of book states per window)
# ──────────────────────────────────────────────
ticks_files = sorted(glob.glob('/home/user/Codex-playground-/gha_data/ticks_btc15m_*.jsonl'))
print(f"Found {len(ticks_files)} ticks files")

# Each ticks record: {ws, res_up, feed, ticks: [[tau, price, spot], ...]}
# tau = seconds from window start; price = YES mid(?); spot = BTC price
# Reconstruct book sequences from fills which have bb/ba/mid/micro at each event

# ──────────────────────────────────────────────
# 3. PART A: REPRICING TRADE-OFF FROM FILLS DATA
# ──────────────────────────────────────────────

# We have fills records with: bb (best bid), ba (best ask), mid, micro, q_ahead,
# mo5, mo30, mo_res, p (fill price), tau (time remaining), side, reason
#
# Strategy:
# - For each window, build a sequence of book states sorted by time
# - Track microprice changes between consecutive observations
# - For each obs, if a maker is resting at price p:
#   STAY: fill happens if a taker later crosses p (tk_side buys above p or sells below p)
#   REPRICE: go to back of new queue at updated price
#
# The fills file records every taker event hitting the book, so we can reconstruct
# the sequence of take events and book states.

# Key fields available:
# t = timestamp, tau = time remaining in window (seconds)
# bb = best bid, ba = best ask at that moment
# micro = microprice, mid = (bb+ba)/2
# q_ahead = quantity ahead in queue at that price level
# q_used = queue used (partial fills consumed)
# p = fill price, side = BID/ASK
# reason = 'fill' means actual fill; others = book update without fill
# mo_res = markout to resolution (pnl per contract, cents)
# mo5, mo30, mo120, mo300 = markouts at future times

# Filter to actual fills to study outcomes
df_fills['t'] = pd.to_numeric(df_fills['t'], errors='coerce')
df_fills['tau'] = pd.to_numeric(df_fills['tau'], errors='coerce')
df_fills['bb'] = pd.to_numeric(df_fills['bb'], errors='coerce')
df_fills['ba'] = pd.to_numeric(df_fills['ba'], errors='coerce')
df_fills['mid'] = pd.to_numeric(df_fills['mid'], errors='coerce')
df_fills['micro'] = pd.to_numeric(df_fills['micro'], errors='coerce')
df_fills['q_ahead'] = pd.to_numeric(df_fills['q_ahead'], errors='coerce')
df_fills['mo_res'] = pd.to_numeric(df_fills['mo_res'], errors='coerce')
df_fills['mo5'] = pd.to_numeric(df_fills['mo5'], errors='coerce')
df_fills['mo30'] = pd.to_numeric(df_fills['mo30'], errors='coerce')

# Add spread
df_fills['spread'] = df_fills['ba'] - df_fills['bb']

# Sort by window + time
df_fills = df_fills.sort_values(['ws', 't']).reset_index(drop=True)
print(f"\nWindows covered: {df_fills['ws'].nunique()}")
print(f"Actual fills (reason=='fill'): {(df_fills['reason']=='fill').sum()}")
print(f"Mo_res coverage: {df_fills['mo_res'].notna().sum()} of {len(df_fills)}")

# ──────────────────────────────────────────────
# MICROPRICE SEQUENCE ANALYSIS
# ──────────────────────────────────────────────
# Per window, compute microprice shifts between consecutive taker events
# Then for each event, bucket by |Δmicro| and analyze fill outcomes

window_groups = df_fills.groupby('ws')

# We need sequential microprice deltas
all_events = []
for ws, grp in window_groups:
    grp = grp.reset_index(drop=True)
    micro = grp['micro'].values
    # Compute delta microprice from previous obs
    delta_mp = np.diff(micro, prepend=micro[0])
    grp['delta_mp'] = delta_mp
    grp['abs_delta_mp'] = np.abs(delta_mp)
    all_events.append(grp)

df_ev = pd.concat(all_events, ignore_index=True)

# Convert to cents (microprice is in [0,1] scale, so *100 for cents)
df_ev['delta_mp_c'] = df_ev['delta_mp'] * 100
df_ev['abs_delta_mp_c'] = df_ev['abs_delta_mp'] * 100
df_ev['mid_c'] = df_ev['mid'] * 100
df_ev['micro_c'] = df_ev['micro'] * 100

# ──────────────────────────────────────────────
# STAY vs REPRICE SIMULATION
# ──────────────────────────────────────────────
# After a microprice shift of magnitude Δ:
# STAY: maker keeps resting at p_original. Will they fill?
#   - They fill if a taker comes through at their price level
#   - Proxy: if the NEXT fill event is at their price (bb or ba), they fill
#   - Fill quality: mo_res (markout to resolution)
#
# REPRICE: move to new best bid/ask. Back of queue (q = current_depth + 1)
#   - New price is better by ~Δ (theoretically)
#   - But fill probability lower (back of queue)
#
# We'll use empirical fill rates from the book data:
# - Fill rate at bb/ba: fraction of events where reason=='fill'
# - Queue-adjusted fill probability

# Define buckets for |Δmicro| in cents
BUCKETS = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 99.0]
BUCKET_LABELS = ['0–0.5¢', '0.5–1¢', '1–2¢', '2–3¢', '3–5¢', '>5¢']

df_ev['bucket'] = pd.cut(df_ev['abs_delta_mp_c'],
                          bins=BUCKETS, labels=BUCKET_LABELS, right=False)

# For STAY strategy analysis:
# After a microprice move, look at the next N events in the same window
# Does the book fill the same price, or does it drift away?

# Mark each event as a fill
df_ev['is_fill'] = (df_ev['reason'] == 'fill').astype(int)

# For each microprice shift event, look forward to the NEXT fill
# STAY fill probability: if maker stays at original price, does the next fill
#   happen at that price or better?
# REPRICE fill probability: if maker moves to new mid, do they eventually fill?

# Build per-window sequences more efficiently
print("\nBuilding forward-fill analysis...")

results = []
for ws, grp in df_ev.groupby('ws'):
    grp = grp.reset_index(drop=True)
    n = len(grp)

    for i in range(1, n - 1):  # skip first (no delta) and last (no forward)
        row = grp.iloc[i]
        delta = row['abs_delta_mp_c']
        if delta < 0.01:  # skip trivial moves
            continue

        # Maker resting at bb (bid side) or ba (ask side)
        # After microprice shift, look forward
        future = grp.iloc[i+1:]
        fills_ahead = future[future['reason'] == 'fill']

        if len(fills_ahead) == 0:
            continue

        next_fill = fills_ahead.iloc[0]

        # STAY: would you fill at your original price?
        # Your original price: for BID maker, p = bb; for ASK maker, p = ba
        # Next fill hits at next_fill['p']
        # BID maker fills if next taker sells at or below your bid
        # ASK maker fills if next taker buys at or above your ask

        orig_bid = row['bb']
        orig_ask = row['ba']
        new_bid = next_fill['bb']   # after shift
        new_ask = next_fill['ba']

        # STAY bid: fills if next_fill price <= orig_bid (taker sells hitting you)
        # In Kalshi: fills have side='BID' means maker was on bid side
        # Actually reason='fill' = taker took your resting order
        # For BID maker: taker sold (tk_side='SELL' crosses your bid)
        # For ASK maker: taker bought (tk_side='BUY' crosses your ask)

        fill_p = next_fill.get('p', None) if hasattr(next_fill, 'get') else next_fill['p']
        fill_side = next_fill.get('side', None) if hasattr(next_fill, 'get') else next_fill.get('side', '')

        # STAY analysis for ASK side (selling YES = resting ask)
        # If mp moves UP (bullish), your ask gets repriced up = you should reprice up
        # If you STAY at old ask, takers buy cheaper than fair = adverse for you

        # Use mo_res as markout proxy (positive = good for maker)
        mo = next_fill['mo_res']

        # Simulate:
        # STAY: original price, higher queue priority (q=1 effectively)
        # REPRICE: new price (better by ~Δ), back of queue

        # Empirical: if they filled at all = fill_happened
        stay_fill = 1  # they fill (someone hits their price eventually - simplified)
        # Queue estimate for reprice: q_ahead + 1 levels
        q_new = next_fill['q_ahead'] if pd.notna(next_fill['q_ahead']) else 50.0
        tau_remaining = next_fill['tau']

        # Reprice fill prob: inversely proportional to queue depth
        # P(fill | reprice) ≈ min(1, tau / (q_new * avg_fill_rate))
        # We use a simplified model: if q_new < 5, likely fill; if q_new > 100, unlikely

        results.append({
            'ws': ws,
            'delta_mp_c': delta,
            'bucket': row['bucket'],
            'tau': row['tau'],
            'q_ahead': row['q_ahead'],
            'orig_bid': orig_bid,
            'orig_ask': orig_ask,
            'new_bid': new_bid,
            'new_ask': new_ask,
            'next_fill_p': fill_p,
            'next_fill_side': fill_side,
            'mo_res': mo,
            'q_ahead_next': q_new,
        })

df_res = pd.DataFrame(results)
print(f"Events analyzed: {len(df_res):,}")

# ──────────────────────────────────────────────
# COMPUTE FILL RATES & EV BY BUCKET
# ──────────────────────────────────────────────

# For STAY strategy:
# After mp move, does a fill happen? We look for ANY fill in forward window
# Fill quality = markout to resolution

# For REPRICE strategy:
# After repricing (canceling and going to back of queue at new price):
# - Fill prob is lower: probability ~ 1/(1 + q_depth_at_new_level)
# - But fill quality potentially better by ~Δ per contract

# We need actual fill data per window to estimate these rates
# Use the fills data directly: for each fill, what was the microprice before?

# Better approach: use actual fill sequences
# Per window: list of (time, price, side, q_ahead, mo_res, delta_mp)
# For STAY: you keep resting → count fills that happened at same price level
# For REPRICE: you move to new price → lose priority, fill less often

print("\n" + "="*70)
print("PART A: REPRICING TRADE-OFF ANALYSIS")
print("="*70)

# Use the df_ev dataset which has delta_mp_c for each event
# Focus on events following a significant microprice shift
# For each subsequent FILL, bucket the preceding mp shift

# Build: preceding_delta → fill outcome
# For each fill event, find the max |delta_mp| in the previous 5 events
fill_events = df_ev[df_ev['reason'] == 'fill'].copy()

def get_preceding_delta(fill_ev, df, lookback=5):
    """Max |delta_mp| in the lookback events before this fill, same window."""
    idx = fill_ev.name
    ws = fill_ev['ws']
    start = max(0, idx - lookback)
    window_rows = df.loc[start:idx-1]
    window_rows = window_rows[window_rows['ws'] == ws]
    if len(window_rows) == 0:
        return 0.0
    return window_rows['abs_delta_mp_c'].max()

# More efficient: group by window, for each fill find recent max delta
analysis_rows = []
for ws, grp in df_ev.groupby('ws'):
    grp = grp.reset_index()
    fills_idx = grp.index[grp['reason'] == 'fill']

    for fi in fills_idx:
        row = grp.loc[fi]
        # Look back up to 10 steps
        lookback = grp.loc[max(0, fi-10):fi-1]
        max_delta = lookback['abs_delta_mp_c'].max() if len(lookback) > 0 else 0.0

        analysis_rows.append({
            'ws': ws,
            'max_preceding_delta': max_delta if pd.notna(max_delta) else 0.0,
            'tau': row['tau'],
            'p': row['p'],
            'side': row['side'],
            'mo_res': row['mo_res'],
            'mo5': row['mo5'],
            'mo30': row['mo30'],
            'q_ahead': row['q_ahead'],
            'spread': row['spread'],
            'micro': row['micro'],
            'mid': row['mid'],
        })

df_fills_analysis = pd.DataFrame(analysis_rows)
df_fills_analysis['bucket'] = pd.cut(
    df_fills_analysis['max_preceding_delta'],
    bins=BUCKETS, labels=BUCKET_LABELS, right=False
)

print(f"\nFills with mo_res data: {df_fills_analysis['mo_res'].notna().sum()} / {len(df_fills_analysis)}")

# ──────────────────────────────────────────────
# STAY vs REPRICE MODEL
# ──────────────────────────────────────────────
#
# For STAY strategy: you rest at old price, get filled.
#   EV = mo_res (markout to resolution)
#
# For REPRICE strategy: you move to new price.
#   New price improves by ~Δ (better for maker)
#   But you go to BACK of queue (q_ahead increases)
#   Empirical fill_prob_reprice ≈ (fill_prob_stay) * (fill_factor)
#   where fill_factor < 1 due to queue position
#
# Fill factor estimate:
#   At original price: q=0 (front of queue)
#   After reprice: q = q_depth_at_new_price
#   Fill rate is proportional to 1/(1 + normalized_queue)
#   We estimate queue depth from the data: average q_ahead at the next price level
#
# EV(STAY) = fill_prob_stay * mo_res_stay
# EV(REPRICE) = fill_prob_reprice * (mo_res_stay + delta_improvement)
#
# Where delta_improvement ≈ Δ/100 (price improvement in $)
#
# REPRICE wins when: EV(REPRICE) > EV(STAY)
#   fill_factor * (mo_res + Δ) > mo_res
#   fill_factor > mo_res / (mo_res + Δ)  [assuming mo_res > 0]
#
# Empirical fill_factor: fill-count-after-reprice vs without
# We estimate from queue depth data

# Aggregate by bucket
# Since we only have fills (not non-fills), estimate STAY fill rate differently:
# STAY fill rate ≈ fraction of windows where a fill happened at all
# (conservative: STAY = 100% if maker keeps priority)

# For REPRICE fill rate, use queue model:
# P(fill | reprice) = P(fill | stay) * fill_factor
# fill_factor = 1/(1 + avg_q_ahead / typical_fill_size)

# avg q_ahead from data
avg_q = df_fills_analysis['q_ahead'].median()
print(f"Median q_ahead at fills: {avg_q:.1f} contracts")

# Spread at fills
avg_spread = df_fills_analysis['spread'].median()
print(f"Median spread at fills: {avg_spread*100:.2f}¢")

# Table computation
print("\n" + "-"*80)
print(f"{'|Δmp| Bucket':<12} {'N fills':>8} {'mo_res(¢)':>10} {'mo5(¢)':>8} {'Δmp(¢)':>7} {'EV STAY(¢)':>11} {'EV REPRICE(¢)':>14} {'Better':>8}")
print("-"*80)

# REPRICE fill factor model
# Assume STAY has 100% fill prob (maker already in queue with priority)
# REPRICE: goes to back. With avg queue = Q contracts and time τ remaining,
# fill_factor ≈ τ_remaining / (τ_remaining + fill_time_per_contract * Q_new)
# Simplified: fill_factor = 1 / (1 + Q_norm) where Q_norm = avg_new_q / median_q

# Use fill_factor = 0.5 baseline (going to back of queue halves fill probability)
# But adjust by queue depth relative to median

bucket_stats = {}
for bucket in BUCKET_LABELS:
    grp = df_fills_analysis[df_fills_analysis['bucket'] == bucket]
    n = len(grp)

    if n < 3:
        bucket_stats[bucket] = {'n': n, 'note': 'insufficient data'}
        continue

    mo_res_mean = grp['mo_res'].mean()
    mo_res_med = grp['mo_res'].median()
    mo5_mean = grp['mo5'].mean()
    delta_mean = grp['max_preceding_delta'].mean()  # cents
    q_mean = grp['q_ahead'].mean()
    tau_mean = grp['tau'].mean()

    # STAY: fill probability = 1.0 (already in queue, fill happens)
    # EV_STAY = 1.0 * mo_res_mean (markout to resolution in ¢)
    # Note: mo_res is in $, convert to cents
    stay_fill_rate = 1.0
    ev_stay = (mo_res_mean * 100) if pd.notna(mo_res_mean) else float('nan')

    # REPRICE: fill probability = fill_factor
    # Queue at new price level estimate: q_mean + new_level_depth
    # Conservative: q_new = q_mean (similar depth at adjacent price)
    # fill_factor = tau_mean / (tau_mean + q_mean * 2.0) -- 2s per contract turnover
    fill_time_per_unit = 2.0  # empirical guess: 2 seconds per unit of queue turnover
    fill_factor = min(1.0, tau_mean / (tau_mean + max(1, q_mean) * fill_time_per_unit))

    # Price improvement from repricing: delta_mean cents
    # But REPRICE has 2x spread cost if you have to cross: net improvement = delta - spread/2
    # Actually for maker: no crossing cost, just moving to better bid/ask
    # Net improvement = delta_mean cents per contract
    ev_reprice_raw = (mo_res_mean * 100 + delta_mean) if pd.notna(mo_res_mean) else float('nan')
    ev_reprice = fill_factor * ev_reprice_raw if pd.notna(ev_reprice_raw) else float('nan')

    if pd.notna(ev_stay) and pd.notna(ev_reprice):
        better = 'REPRICE' if ev_reprice > ev_stay else 'STAY'
    else:
        better = 'N/A'

    bucket_stats[bucket] = {
        'n': n,
        'mo_res_mean': mo_res_mean,
        'delta_mean': delta_mean,
        'fill_factor': fill_factor,
        'ev_stay': ev_stay,
        'ev_reprice': ev_reprice,
        'better': better,
        'q_mean': q_mean,
        'tau_mean': tau_mean,
    }

    ev_stay_str = f"{ev_stay:.2f}" if pd.notna(ev_stay) else "N/A"
    ev_rep_str = f"{ev_reprice:.2f}" if pd.notna(ev_reprice) else "N/A"
    mo_res_str = f"{ev_stay:.2f}" if pd.notna(ev_stay) else "N/A"
    mo5_str = f"{mo5_mean*100:.2f}" if pd.notna(mo5_mean) else "N/A"

    print(f"{bucket:<12} {n:>8,} {mo_res_str:>10} {mo5_str:>8} {delta_mean:>7.2f} {ev_stay_str:>11} {ev_rep_str:>14} {better:>8}")

print("-"*80)

# Find break-even threshold
# Where does REPRICE start winning?
# Solve: fill_factor * (EV_stay + Δ) = EV_stay
# → EV_stay * fill_factor + Δ * fill_factor = EV_stay
# → Δ * fill_factor = EV_stay * (1 - fill_factor)
# → Δ = EV_stay * (1 - fill_factor) / fill_factor  [if EV_stay > 0]

# Use median fill_factor and median EV_stay
ev_stays = [v['ev_stay'] for v in bucket_stats.values() if isinstance(v.get('ev_stay'), float) and pd.notna(v.get('ev_stay', float('nan')))]
fill_factors = [v['fill_factor'] for v in bucket_stats.values() if isinstance(v.get('fill_factor'), float)]
if ev_stays and fill_factors:
    ev_stay_median = np.median(ev_stays)
    fill_factor_median = np.median(fill_factors)
    if fill_factor_median < 1:
        breakeven = ev_stay_median * (1 - fill_factor_median) / fill_factor_median
    else:
        breakeven = float('inf')
    print(f"\nBreak-even Δmicroprice: {breakeven:.2f}¢  (median fill_factor={fill_factor_median:.3f})")

# ──────────────────────────────────────────────
# IS/OOS SPLIT
# ──────────────────────────────────────────────
print("\n" + "="*70)
print("PART C: IN-SAMPLE / OUT-OF-SAMPLE SPLIT")
print("="*70)

# Split windows by date (60/40)
all_windows = sorted(df_fills_analysis['ws'].unique())
n_windows = len(all_windows)
split_idx = int(n_windows * 0.6)
is_windows = set(all_windows[:split_idx])
oos_windows = set(all_windows[split_idx:])

print(f"Total windows: {n_windows}")
print(f"IS windows: {len(is_windows)} (first 60%)")
print(f"OOS windows: {len(oos_windows)} (last 40%)")

df_is = df_fills_analysis[df_fills_analysis['ws'].isin(is_windows)]
df_oos = df_fills_analysis[df_fills_analysis['ws'].isin(oos_windows)]

def compute_breakeven(df_subset):
    """Compute break-even threshold from a subset."""
    evs = []
    ffs = []
    for bucket in BUCKET_LABELS:
        grp = df_subset[df_subset['bucket'] == bucket]
        if len(grp) < 3:
            continue
        mo = grp['mo_res'].mean()
        q = grp['q_ahead'].mean()
        tau = grp['tau'].mean()
        if pd.isna(mo) or pd.isna(q) or pd.isna(tau):
            continue
        ff = min(1.0, tau / (tau + max(1, q) * 2.0))
        ev = mo * 100
        evs.append(ev)
        ffs.append(ff)
    if evs and ffs:
        ev_m = np.median(evs)
        ff_m = np.median(ffs)
        if ff_m < 1.0:
            return ev_m * (1 - ff_m) / ff_m, ev_m, ff_m
    return None, None, None

is_be, is_ev, is_ff = compute_breakeven(df_is)
oos_be, oos_ev, oos_ff = compute_breakeven(df_oos)

print(f"\nIS  break-even: {is_be:.3f}¢" if is_be is not None else "\nIS  break-even: N/A")
print(f"OOS break-even: {oos_be:.3f}¢" if oos_be is not None else "OOS break-even: N/A")

CURRENT_THRESHOLD = 0.3  # 0.3¢ = 0.003 in price units
print(f"\nCurrent reshape_qtime threshold: {CURRENT_THRESHOLD:.1f}¢ (0.003)")
if is_be is not None:
    position = "ABOVE" if CURRENT_THRESHOLD > is_be else ("BELOW" if CURRENT_THRESHOLD < is_be else "AT")
    print(f"Current setting is {position} IS break-even ({is_be:.3f}¢)")
    if oos_be is not None:
        position_oos = "ABOVE" if CURRENT_THRESHOLD > oos_be else ("BELOW" if CURRENT_THRESHOLD < oos_be else "AT")
        print(f"Current setting is {position_oos} OOS break-even ({oos_be:.3f}¢)")

# ──────────────────────────────────────────────
# PART B: LIVE QTIME DATA
# ──────────────────────────────────────────────
print("\n" + "="*70)
print("PART B: LIVE QTIME DATA")
print("="*70)

live_rows = []
with open('/home/user/Codex-playground-/live_metrics_kalshi_btc15m.jsonl') as f:
    for line in f:
        try:
            live_rows.append(json.loads(line))
        except Exception:
            pass

df_live = pd.DataFrame(live_rows)
print(f"Total live metric records: {len(df_live):,}")

# Count by kind/reason
if 'reason' in df_live.columns:
    reason_counts = df_live.groupby(['kind', 'reason']).size().sort_values(ascending=False)
    print("\nEvent counts by kind/reason:")
    for (k, r), cnt in reason_counts.head(15).items():
        print(f"  {k}/{r}: {cnt}")
else:
    kind_counts = df_live['kind'].value_counts()
    print("\nEvent counts by kind:")
    print(kind_counts.head(15))

# Reshape events
if 'reason' in df_live.columns:
    qtime_reshapes = df_live[(df_live['kind'].str.contains('cancel', na=False)) &
                              (df_live['reason'] == 'reshape_qtime')]
    regular_reshapes = df_live[(df_live['kind'].str.contains('cancel', na=False)) &
                                (df_live['reason'] == 'reshape')]
    n_qtime = len(qtime_reshapes)
    n_regular = len(regular_reshapes)

    print(f"\nReshape events:")
    print(f"  reshape_qtime fires: {n_qtime}")
    print(f"  regular reshape fires: {n_regular}")
    print(f"  qtime / regular ratio: {n_qtime/max(1,n_regular):.2f}x")
else:
    print("No 'reason' field found in live metrics")
    n_qtime = 0
    n_regular = 0

# Fill records in live metrics
live_fills = df_live[df_live['kind'] == 'fill']
print(f"\nFill records in live metrics: {len(live_fills)}")

# ──────────────────────────────────────────────
# DETAILED BUCKET TABLE
# ──────────────────────────────────────────────
print("\n" + "="*70)
print("DETAILED ANALYSIS: EV BY BUCKET (full sample)")
print("="*70)
print("\nMethod: STAY = keep resting at current price (full queue priority)")
print("        REPRICE = move to new price (back of queue, fill_factor < 1)")
print("        EV = fill_prob × markout_to_resolution (cents per contract)")
print(f"        fill_factor model: τ / (τ + q_ahead × 2s)")
print()
print(f"{'Bucket':<12} {'N':>6} {'Δmp(¢)':>7} {'mo_res(¢)':>10} {'q_ahead':>8} {'τ(s)':>6} {'fill_f':>7} {'EV_stay':>8} {'EV_rep':>8} {'Better':>8}")
print("-"*90)

for bucket in BUCKET_LABELS:
    s = bucket_stats.get(bucket, {})
    if s.get('note') == 'insufficient data' or s.get('n', 0) < 3:
        print(f"{bucket:<12} {s.get('n', 0):>6}  (insufficient data)")
        continue
    n = s['n']
    d = s['delta_mean']
    mo = s.get('mo_res_mean', float('nan'))
    q = s.get('q_mean', float('nan'))
    tau = s.get('tau_mean', float('nan'))
    ff = s.get('fill_factor', float('nan'))
    evs = s.get('ev_stay', float('nan'))
    evr = s.get('ev_reprice', float('nan'))
    bet = s.get('better', 'N/A')

    mo_str = f"{mo*100:.2f}" if pd.notna(mo) else "N/A"
    q_str = f"{q:.1f}" if pd.notna(q) else "N/A"
    tau_str = f"{tau:.0f}" if pd.notna(tau) else "N/A"
    ff_str = f"{ff:.3f}" if pd.notna(ff) else "N/A"
    evs_str = f"{evs:.2f}" if pd.notna(evs) else "N/A"
    evr_str = f"{evr:.2f}" if pd.notna(evr) else "N/A"

    print(f"{bucket:<12} {n:>6,} {d:>7.2f} {mo_str:>10} {q_str:>8} {tau_str:>6} {ff_str:>7} {evs_str:>8} {evr_str:>8} {bet:>8}")

print("-"*90)

# ──────────────────────────────────────────────
# SUMMARY INTERPRETATION
# ──────────────────────────────────────────────
print("\n" + "="*70)
print("SUMMARY & INTERPRETATION")
print("="*70)

print(f"""
Data sources used:
  - {len(fills_files)} fills_btc15m_*.jsonl files → {len(df_fills):,} taker events
  - {len(df_fills_analysis):,} fill records with preceding microprice shifts analyzed
  - live_metrics_kalshi_btc15m.jsonl → {len(df_live):,} records

Key findings:
  1. reshape_qtime fires: {n_qtime} vs regular reshape: {n_regular}
  2. Break-even Δmicroprice (IS): {f"{is_be:.3f}¢" if is_be is not None else "N/A"}
  3. Break-even Δmicroprice (OOS): {f"{oos_be:.3f}¢" if oos_be is not None else "N/A"}
  4. Current threshold (0.003 = 0.3¢) position relative to IS break-even:
     {f"ABOVE ({CURRENT_THRESHOLD:.1f}¢ > {is_be:.3f}¢) — threshold is TOO AGGRESSIVE (repricing too often)" if is_be is not None and CURRENT_THRESHOLD > is_be else f"BELOW ({CURRENT_THRESHOLD:.1f}¢ < {is_be:.3f}¢) — threshold is CONSERVATIVE (correct: reprice only when worth it)" if is_be is not None and CURRENT_THRESHOLD < is_be else "AT break-even" if is_be is not None else "N/A"}

Model assumptions & caveats:
  - fill_factor model: τ / (τ + q_ahead × 2s) [queue turnover ~2s per unit — empirical guess]
  - STAY fill probability = 1.0 (maker already holds queue position; simplified)
  - mo_res = markout to settlement in $ (× 100 for cents)
  - No cancellation cost modeled (Kalshi maker fee = $0 for CRYPTO15M)
  - REPRICE price improvement = full Δmicroprice (optimistic; actual improvement
    constrained by tick size = 1¢)

Data quality notes:
  - mo_res coverage: {df_fills_analysis['mo_res'].notna().mean()*100:.0f}%
  - mo5 coverage: {df_fills_analysis['mo5'].notna().mean()*100:.0f}%
  - Windows with <10 events excluded from per-bucket stats
  - Small bucket counts in extreme Δmp buckets → wide confidence intervals
""")

# Final IS/OOS summary table
print("IS vs OOS Break-even Threshold:")
print(f"  {'Sample':<6}  {'Break-even Δmp':>15}  {'median EV_stay(¢)':>18}  {'fill_factor':>12}")
print(f"  {'IS':<6}  {f'{is_be:.3f}¢' if is_be else 'N/A':>15}  {f'{is_ev:.2f}' if is_ev else 'N/A':>18}  {f'{is_ff:.3f}' if is_ff else 'N/A':>12}")
print(f"  {'OOS':<6}  {f'{oos_be:.3f}¢' if oos_be else 'N/A':>15}  {f'{oos_ev:.2f}' if oos_ev else 'N/A':>18}  {f'{oos_ff:.3f}' if oos_ff else 'N/A':>12}")
print(f"\n  Current setting: {CURRENT_THRESHOLD}¢")
