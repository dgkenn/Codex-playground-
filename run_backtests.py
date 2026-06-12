import numpy as np
import pandas as pd
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

hist = pd.read_parquet('/home/user/Codex-playground-/hist_kalshi_btc15m.parquet')
tap = pd.read_parquet('/home/user/Codex-playground-/trades_kalshi_btc15m.parquet')

# Explode arrays into per-second rows for hist
# Each window has arrays of length 15 (one per minute in the 15-min window)
# spot_path, mid_path, bid_path, ask_path are arrays

# ---- HELPER: flatten hist to per-tick rows ----
rows = []
for _, r in hist.iterrows():
    sp = np.array(r['spot_path'])
    mid = np.array(r['mid_path'])
    bid = np.array(r['bid_path'])
    ask = np.array(r['ask_path'])
    for i in range(len(sp)):
        rows.append({
            'ws': r['ws'],
            'res_up': r['res_up'],
            'tick': i,
            'spot': sp[i],
            'mid': mid[i],
            'bid': bid[i],
            'ask': ask[i],
        })
hist_flat = pd.DataFrame(rows)

# IS/OOS split by ws (60/40)
all_ws = sorted(hist['ws'].unique())
n_is = int(len(all_ws) * 0.6)
is_ws = set(all_ws[:n_is])
oos_ws = set(all_ws[n_is:])

print(f"IS windows: {len(is_ws)}, OOS windows: {len(oos_ws)}")

# ============================================================
# TEST 1: STALE-MAKER SNIPE
# When spot moves by >X ticks but Kalshi mid hasn't moved yet,
# take the lagging side. Measure PnL = (resolution - taker_price).
# "Snipe" = if spot_delta > threshold AND mid hasn't moved proportionally,
# we TAKE ask (if spot up) or BID (if spot down), then hold to resolution.
# PnL = res_up - ask_price (for YES buy), or bid_price - res_up (for NO buy = buy at bid for NO)
# Actually for Kalshi binary: YES costs ask, pays 1 if res_up=1. NO costs (1-bid), pays 1 if res_up=0
# Simplify: take YES at ask if spot_lead bullish, PnL = res_up - ask
#           take NO at (1-bid) if spot_lead bearish, PnL = (1-res_up) - (1-bid) = bid - res_up
# Fee = 0 (maker), taker fee also ~0 for CRYPTO15M per CLAUDE.md
# ============================================================
print("\n=== TEST 1: STALE-MAKER SNIPE ===")
thresholds = [0.002, 0.005, 0.010]  # spot move thresholds

for split_name, ws_set in [('IS', is_ws), ('OOS', oos_ws)]:
    df = hist_flat[hist_flat['ws'].isin(ws_set)].copy()
    # spot_delta = (spot[t] - spot[t-1]) / spot[t-1]
    df = df.sort_values(['ws', 'tick'])
    df['spot_prev_tick'] = df.groupby('ws')['spot'].shift(1)
    df['spot_delta'] = (df['spot'] - df['spot_prev_tick']) / df['spot_prev_tick']
    df['mid_prev_tick'] = df.groupby('ws')['mid'].shift(1)
    df['mid_delta'] = df['mid'] - df['mid_prev_tick']

    # Only look at ticks 1+ (need prev)
    df = df.dropna(subset=['spot_prev_tick', 'mid_prev_tick'])

    # Stale condition: spot moved significantly but mid moved less than half as much
    # Bullish spot move but mid hasn't moved up proportionally -> buy YES at ask
    # Bearish spot move but mid hasn't moved down proportionally -> buy NO (at 1-bid)

    results = []
    for thresh in thresholds:
        # Bullish stale: spot up > thresh, mid up < spot_delta * 0.5 * current_mid
        bull_mask = (df['spot_delta'] > thresh) & (df['mid_delta'] < df['spot_delta'] * df['mid_prev_tick'] * 0.5)
        bear_mask = (df['spot_delta'] < -thresh) & (df['mid_delta'] > df['spot_delta'] * df['mid_prev_tick'] * 0.5)

        bull_pnl = df[bull_mask]['res_up'] - df[bull_mask]['ask']
        bear_pnl = df[bear_mask]['bid'] - df[bear_mask]['res_up']  # buy NO

        all_pnl = pd.concat([bull_pnl, bear_pnl])
        n = len(all_pnl)
        if n > 5:
            mean_pnl = all_pnl.mean()
            t_stat = stats.ttest_1samp(all_pnl, 0).statistic
            results.append(f"  thresh={thresh:.3f}: n={n:4d}, edge={mean_pnl*100:+.3f}c/ct, t={t_stat:.2f}")
        else:
            results.append(f"  thresh={thresh:.3f}: n={n:4d}, INSUFFICIENT DATA")

    print(f"  {split_name}:")
    for r in results:
        print(r)

# ============================================================
# TEST 2: NAIVE FLOW FADE vs FOLLOW
# From the trade tape: for each fill, compute markout to resolution.
# buy=True fills (takers buying YES): if they're naive, they'll push price up
# but if wrong, maker who sold YES earns.
# Classify flow as: aggressive taker buys vs sells.
# Fade = take opposite side of taker flow (be the maker they're hitting)
# Follow = take same side as taker flow
# Measure: for windows with net buy imbalance, does res_up=1 more often?
# ============================================================
print("\n=== TEST 2: NAIVE FLOW FADE vs FOLLOW ===")

# Merge tap with hist to get resolution
tap_merged = tap.merge(hist[['ws', 'res_up']], on='ws', how='left')

for split_name, ws_set in [('IS', is_ws), ('OOS', oos_ws)]:
    df_tap = tap_merged[tap_merged['ws'].isin(ws_set)].copy()

    # Per window: compute flow imbalance
    window_stats = []
    for _, row in df_tap.iterrows():
        buys = np.array(row['buy'])
        prices = np.array(row['p'])
        sizes = np.array(row['sz'])

        if len(buys) == 0:
            continue

        buy_vol = np.sum(sizes[buys == True]) if np.any(buys) else 0
        sell_vol = np.sum(sizes[buys == False]) if np.any(buys == False) else 0
        total_vol = buy_vol + sell_vol

        if total_vol == 0:
            continue

        imbalance = (buy_vol - sell_vol) / total_vol  # -1 to +1
        avg_price = np.mean(prices)

        window_stats.append({
            'ws': row['ws'],
            'res_up': row['res_up'],
            'imbalance': imbalance,
            'avg_price': avg_price,
            'total_vol': total_vol
        })

    ws_df = pd.DataFrame(window_stats)

    if len(ws_df) < 10:
        print(f"  {split_name}: INSUFFICIENT DATA")
        continue

    # FOLLOW: bet YES when buy-imbalanced, NO when sell-imbalanced
    ws_df['follow_correct'] = ((ws_df['imbalance'] > 0) & (ws_df['res_up'] == 1)) | \
                               ((ws_df['imbalance'] < 0) & (ws_df['res_up'] == 0))
    # FADE: opposite
    ws_df['fade_correct'] = ~ws_df['follow_correct']

    # PnL for follow: buy YES at mid+0.5 spread (taker cost ~mid), get res_up
    # Actually compute edge as E[res_up | imbalance > 0] vs baseline
    baseline = ws_df['res_up'].mean()

    bull_wins = ws_df[ws_df['imbalance'] > 0.2]['res_up'].mean()  # strongly buy-imbalanced
    bear_wins = 1 - ws_df[ws_df['imbalance'] < -0.2]['res_up'].mean()  # strongly sell-imbalanced

    # Edge = predictive accuracy above 50%
    all_imb = ws_df[np.abs(ws_df['imbalance']) > 0.2]
    if len(all_imb) > 5:
        follow_pnl = np.where(all_imb['imbalance'] > 0,
                               all_imb['res_up'] - all_imb['avg_price'],
                               (1-all_imb['res_up']) - (1-all_imb['avg_price']))
        t_follow = stats.ttest_1samp(follow_pnl, 0).statistic
        fade_pnl = -follow_pnl
        t_fade = stats.ttest_1samp(fade_pnl, 0).statistic
        print(f"  {split_name}: n_windows={len(ws_df)}, baseline_res_up={baseline:.3f}")
        print(f"    FOLLOW edge={np.mean(follow_pnl)*100:+.3f}c/ct, t={t_follow:.2f} | n_strong={len(all_imb)}")
        print(f"    FADE  edge={np.mean(fade_pnl)*100:+.3f}c/ct, t={t_fade:.2f}")
    else:
        print(f"  {split_name}: n={len(ws_df)}, strong_imb={len(all_imb)} - LOW N")

# ============================================================
# TEST 3: NEW-WINDOW FIRST N SECONDS MISPRICING
# The first ticks of each window: is the opening spread wider?
# Is the opening mid a worse predictor of res_up (more noise)?
# Edge: quotes are stale/wide early -> snipe mispriced opening quotes
# ============================================================
print("\n=== TEST 3: NEW-WINDOW FIRST-N-TICKS MISPRICING ===")

for split_name, ws_set in [('IS', is_ws), ('OOS', oos_ws)]:
    df = hist_flat[hist_flat['ws'].isin(ws_set)].copy()

    # Merge resolution
    df = df.merge(hist[['ws', 'res_up']], on='ws', how='left')

    # Early ticks (0-2) vs late ticks (10-14)
    early = df[df['tick'] <= 2].copy()
    late = df[df['tick'] >= 10].copy()

    def spread_and_accuracy(subset):
        spread = (subset['ask'] - subset['bid']).mean()
        # Calibration: does mid predict res_up?
        # res_up=1 means YES resolved, mid should ≈ P(YES)
        mid_err = (subset['mid'] - subset['res_up']).abs().mean()
        # Taker edge: if you buy YES at ask in early ticks
        pnl_buy_yes = subset['res_up'] - subset['ask']
        pnl_buy_no = (1 - subset['res_up']) - (1 - subset['bid'])
        # Best direction based on mid > 0.5 or < 0.5
        directional_pnl = np.where(subset['mid'] > 0.5,
                                    subset['res_up'] - subset['ask'],
                                    (1-subset['res_up']) - (1-subset['bid']))
        return {
            'n': len(subset),
            'spread': spread,
            'mid_mae': mid_err,
            'dir_edge': directional_pnl.mean(),
            't': stats.ttest_1samp(directional_pnl, 0).statistic if len(directional_pnl) > 5 else np.nan
        }

    e = spread_and_accuracy(early)
    l = spread_and_accuracy(late)

    print(f"  {split_name}: Early(tick 0-2): spread={e['spread']:.4f}, MAE={e['mid_mae']:.4f}, dir_edge={e['dir_edge']*100:+.3f}c, t={e['t']:.2f}")
    print(f"  {split_name}: Late (tick10-14): spread={l['spread']:.4f}, MAE={l['mid_mae']:.4f}, dir_edge={l['dir_edge']*100:+.3f}c, t={l['t']:.2f}")

# ============================================================
# TEST 4: FLOW TOXICITY CONDITIONED QUOTING
# Simplified VPIN: rolling order flow imbalance as adverse selection proxy.
# When OFI is extreme (>70th percentile), the NEXT fill is more likely to
# be adverse for makers. Measure: maker PnL conditioned on prior OFI.
# ============================================================
print("\n=== TEST 4: FLOW-TOXICITY CONDITIONED QUOTING ===")

# Use trade tape: for each window, compute OFI in first half,
# predict maker PnL in second half
tap_merged2 = tap.merge(hist[['ws', 'res_up']], on='ws', how='left')

for split_name, ws_set in [('IS', is_ws), ('OOS', oos_ws)]:
    df_tap = tap_merged2[tap_merged2['ws'].isin(ws_set)].copy()

    high_toxic_maker_pnl = []
    low_toxic_maker_pnl = []

    for _, row in df_tap.iterrows():
        buys = np.array(row['buy'])
        prices = np.array(row['p'])
        sizes = np.array(row['sz'])
        res = row['res_up']

        if len(buys) < 4:
            continue

        n = len(buys)
        half = n // 2

        # First half OFI
        b1 = buys[:half]
        s1 = sizes[:half]
        buy_vol_1 = np.sum(s1[b1]) if np.any(b1) else 0
        sell_vol_1 = np.sum(s1[~b1]) if np.any(~b1) else 0
        ofi = (buy_vol_1 - sell_vol_1) / max(buy_vol_1 + sell_vol_1, 1)

        # Second half: maker PnL (maker earns spread if prices don't move adversely)
        # Maker mid-price PnL: if maker quotes at mid, earns half-spread per fill
        # But adverse selection: if res_up and most buys -> maker sold YES -> lost
        p2 = prices[half:]
        b2 = buys[half:]
        s2 = sizes[half:]

        if len(p2) == 0:
            continue

        # Maker PnL: for each taker buy (maker sells YES at ask), maker PnL = ask - res_up
        # For each taker sell (maker buys YES at bid), maker PnL = res_up - bid
        maker_pnl = []
        for pi, bi, si in zip(p2, b2, s2):
            # pi is the trade price; assume bid=pi-0.01, ask=pi+0.01 (approximation)
            # Actually use hist_flat bid/ask -- but that's complex. Use: maker earns half-spread per fill
            # Conservative: maker pnl = 0.01 - |res_up - (1 if bi else 0)| * 0  (simplified)
            # Better: if taker buys at price p, maker sold YES at p, earns p - res_up
            if bi:  # taker buy -> maker sold YES at p
                maker_pnl.append(pi - res)
            else:   # taker sell -> maker bought YES at p
                maker_pnl.append(res - pi)

        if maker_pnl:
            avg_maker = np.mean(maker_pnl)
            if abs(ofi) > 0.5:  # high toxicity
                high_toxic_maker_pnl.append(avg_maker)
            else:
                low_toxic_maker_pnl.append(avg_maker)

    if len(high_toxic_maker_pnl) > 5 and len(low_toxic_maker_pnl) > 5:
        ht = np.array(high_toxic_maker_pnl)
        lt = np.array(low_toxic_maker_pnl)
        t_ht = stats.ttest_1samp(ht, 0).statistic
        t_lt = stats.ttest_1samp(lt, 0).statistic
        print(f"  {split_name}: HIGH-toxic maker edge={ht.mean()*100:+.3f}c/ct, t={t_ht:.2f}, n={len(ht)}")
        print(f"  {split_name}: LOW-toxic  maker edge={lt.mean()*100:+.3f}c/ct, t={t_lt:.2f}, n={len(lt)}")
        diff_t = stats.ttest_ind(lt, ht).statistic
        print(f"  {split_name}: LOW vs HIGH diff t={diff_t:.2f}")
    else:
        print(f"  {split_name}: INSUFFICIENT DATA (ht={len(high_toxic_maker_pnl)}, lt={len(low_toxic_maker_pnl)})")

# ============================================================
# TEST 5: SPOT-LAG ALPHA — More refined stale snipe
# For each tick in hist_flat, compute:
# - spot_move_5tick: cumulative spot return over last 5 ticks
# - mid_move_5tick: cumulative mid move
# - lag = spot_move_5tick - mid_move_5tick (in probability space)
# When lag > threshold, take the lagging side. Outcome = resolution.
# ============================================================
print("\n=== TEST 5: SPOT-LAG ALPHA (REFINED) ===")

hist_flat2 = hist_flat.sort_values(['ws', 'tick']).copy()
hist_flat2 = hist_flat2.merge(hist[['ws', 'res_up']], on='ws', how='left')

# Normalize spot to [0,1] scale using logistic approximation:
# spot_signal = how far spot has moved vs typical range
# proxy: use rank within window

for split_name, ws_set in [('IS', is_ws), ('OOS', oos_ws)]:
    df = hist_flat2[hist_flat2['ws'].isin(ws_set)].copy()

    # For each tick t>=5:
    # spot_lag_5 = spot[t] / spot[t-5] - 1  (return)
    # mid_lag_5 = mid[t] - mid[t-5]
    df = df.sort_values(['ws', 'tick'])
    df['spot_ret5'] = df.groupby('ws')['spot'].transform(lambda x: x / x.shift(5) - 1)
    df['mid_move5'] = df.groupby('ws')['mid'].transform(lambda x: x - x.shift(5))
    df = df.dropna(subset=['spot_ret5', 'mid_move5'])

    # Convert spot ret to "expected mid move" in probability space
    # If BTC moves +1%, roughly mid should move by sensitivity (empirically ~0.5% per 1% spot)
    # We'll calibrate from data: regress mid_move5 on spot_ret5
    from numpy.polynomial import polynomial as P
    if len(df) > 20:
        coef = np.polyfit(df['spot_ret5'], df['mid_move5'], 1)
        # lag = actual_mid_move - predicted_mid_move from spot
        df['predicted_mid'] = coef[0] * df['spot_ret5'] + coef[1]
        df['mid_lag'] = df['mid_move5'] - df['predicted_mid']  # negative = mid lagging spot

        thresholds_lag = [0.01, 0.02, 0.03]
        print(f"  {split_name}: spot->mid sensitivity = {coef[0]:.4f}")
        for thr in thresholds_lag:
            # Spot moved up but mid lagged behind -> buy YES (mid will catch up)
            spot_up_mid_lag = df[(df['spot_ret5'] > 0) & (df['mid_lag'] < -thr)]
            spot_dn_mid_lag = df[(df['spot_ret5'] < 0) & (df['mid_lag'] > thr)]

            pnl_up = spot_up_mid_lag['res_up'] - spot_up_mid_lag['ask']
            pnl_dn = spot_dn_mid_lag['bid'] - spot_dn_mid_lag['res_up']
            all_pnl = pd.concat([pnl_up, pnl_dn])

            n = len(all_pnl)
            if n > 5:
                t_s = stats.ttest_1samp(all_pnl, 0).statistic
                print(f"  {split_name} lag_thr={thr:.2f}: n={n:4d}, edge={all_pnl.mean()*100:+.4f}c/ct, t={t_s:.2f}")
            else:
                print(f"  {split_name} lag_thr={thr:.2f}: n={n} INSUFFICIENT")

print("\n=== SUMMARY TABLE ===")
print("Test | IS edge | IS t | OOS edge | OOS t | Survivor")
print("(see individual results above for exact numbers)")
