import pandas as pd
import numpy as np
import ast
import warnings
warnings.filterwarnings('ignore')

# ── Load data ──────────────────────────────────────────────────────────────────
hist = pd.read_parquet('/home/user/Codex-playground-/hist_kalshi_btc15m.parquet')
trades = pd.read_parquet('/home/user/Codex-playground-/trades_kalshi_btc15m.parquet')

# Convert array columns
def parse_arr(x):
    if isinstance(x, str):
        return ast.literal_eval(x)
    if isinstance(x, (list, np.ndarray)):
        return list(x)
    return x

for col in ['bid_path', 'ask_path', 'spot_path']:
    if col in hist.columns:
        hist[col] = hist[col].apply(parse_arr)

for col in ['t', 'p', 'sz', 'buy']:
    if col in trades.columns:
        trades[col] = trades[col].apply(parse_arr)

# Build trades lookup by ws
trades_by_ws = {}
for ws, row in trades.iterrows():
    trades_by_ws[ws] = row

Ks = [12, 13, 14]
Ts = [0.93, 0.95, 0.97]

# ── ANALYSIS 1 & 2 ────────────────────────────────────────────────────────────
results = {}  # key=(k,T) -> list of dicts

for ws, row in hist.iterrows():
    try:
        bid_path = row['bid_path']
        ask_path = row['ask_path']
        spot_path = row['spot_path']
        res_up = row['res_up']
    except Exception:
        continue
    if bid_path is None or ask_path is None:
        continue
    
    tr = trades_by_ws.get(ws, None)
    
    for k in Ks:
        try:
            bid_k = bid_path[k]
            ask_k = ask_path[k]
        except (IndexError, TypeError):
            continue
        if bid_k is None or ask_k is None or np.isnan(bid_k) or np.isnan(ask_k):
            continue
        
        mid_k = (bid_k + ask_k) / 2.0
        fav_yes = mid_k > 0.5
        fav_p = mid_k if fav_yes else (1.0 - mid_k)
        
        for T in Ts:
            if fav_p < T:
                continue
            
            key = (k, T)
            if key not in results:
                results[key] = []
            
            # Fill opportunity
            contracts_available = 0.0
            fill_occurred = False
            
            if tr is not None:
                t_arr = tr['t']
                p_arr = tr['p']
                sz_arr = tr['sz']
                buy_arr = tr['buy']
                
                cutoff_lo = ws + 60 * (k + 1)
                cutoff_hi = ws + 900
                
                for i in range(len(t_arr)):
                    ti = t_arr[i]
                    if ti <= cutoff_lo or ti > cutoff_hi:
                        continue
                    pi = p_arr[i]
                    szi = sz_arr[i] / 100.0  # convert to contracts
                    bi = buy_arr[i]
                    
                    if fav_yes:
                        # fill if taker sells YES (buy=False) at p <= bid_k
                        if not bi and pi <= bid_k:
                            contracts_available += szi
                            fill_occurred = True
                    else:
                        # fill if taker buys YES (buy=True) at p >= ask_k
                        if bi and pi >= ask_k:
                            contracts_available += szi
                            fill_occurred = True
            
            # res_favorable
            if fav_yes:
                res_fav = bool(res_up)
            else:
                res_fav = not bool(res_up)
            
            results[key].append({
                'ws': ws,
                'fav_yes': fav_yes,
                'fav_p': fav_p,
                'bid_k': bid_k,
                'ask_k': ask_k,
                'fill_occurred': fill_occurred,
                'contracts': contracts_available,
                'res_fav': res_fav,
                'spot_path': spot_path,
                'k': k,
            })

# ── Print Analysis 1 & 2 ──────────────────────────────────────────────────────
print("=" * 70)
print("ANALYSIS 1 - FILL OPPORTUNITY")
print(f"{'k':>3} {'T':>5} {'N_qual':>7} {'per_day':>8} {'fill%':>7} {'med_c':>7} {'mean_c':>7}")
print("-" * 70)

for k in Ks:
    for T in Ts:
        key = (k, T)
        if key not in results:
            print(f"{k:>3} {T:>5.2f}  NO DATA")
            continue
        recs = results[key]
        n_qual = len(recs)
        per_day = n_qual / (n_qual / 96) if n_qual > 0 else 0  # placeholder
        # compute total windows from hist
        n_days = len(hist) / 96.0
        per_day_rate = n_qual / n_days if n_days > 0 else 0
        
        fill_recs = [r for r in recs if r['fill_occurred']]
        fill_pct = 100.0 * len(fill_recs) / n_qual if n_qual > 0 else 0
        
        if fill_recs:
            contracts_list = [r['contracts'] for r in fill_recs]
            med_c = np.median(contracts_list)
            mean_c = np.mean(contracts_list)
        else:
            med_c = 0.0
            mean_c = 0.0
        
        print(f"{k:>3} {T:>5.2f} {n_qual:>7} {per_day_rate:>8.2f} {fill_pct:>7.1f} {med_c:>7.2f} {mean_c:>7.2f}")

print()
print("=" * 70)
print("ANALYSIS 2 - REALIZED EV (fill-through events only)")
print(f"{'k':>3} {'T':>5} {'N_fill':>7} {'wt_EV/c':>9} {'win%_f':>8} {'win%_u':>8} {'adv_sel':>9}")
print("-" * 70)

for k in Ks:
    for T in Ts:
        key = (k, T)
        if key not in results:
            continue
        recs = results[key]
        fill_recs = [r for r in recs if r['fill_occurred']]
        
        if not fill_recs:
            n_qual = len(recs)
            unc_win = np.mean([r['res_fav'] for r in recs]) if recs else float('nan')
            print(f"{k:>3} {T:>5.2f} {0:>7}  NO FILLS  unc_win%={100*unc_win:.1f}")
            continue
        
        # weighted EV
        wt_evs = []
        for r in fill_recs:
            fp = r['fav_p']
            ev = (1.0 - fp) if r['res_fav'] else (-fp)
            w = min(r['contracts'], 5.0)
            wt_evs.append((ev, w))
        
        total_w = sum(w for _, w in wt_evs)
        wt_ev = sum(ev * w for ev, w in wt_evs) / total_w if total_w > 0 else float('nan')
        
        win_filled = np.mean([r['res_fav'] for r in fill_recs])
        win_uncond = np.mean([r['res_fav'] for r in recs])
        
        cond_flip = 1.0 - win_filled
        uncond_flip = 1.0 - win_uncond
        adv_sel = cond_flip - uncond_flip
        
        print(f"{k:>3} {T:>5.2f} {len(fill_recs):>7} {wt_ev:>9.4f} {100*win_filled:>8.1f} {100*win_uncond:>8.1f} {adv_sel:>9.4f}")

# ── ANALYSIS 3 - Z-CONDITIONING ──────────────────────────────────────────────
# Find best (k,T) on IS (first 60%)
ws_sorted = sorted(hist.index)
cutoff_idx = int(0.6 * len(ws_sorted))
is_ws = set(ws_sorted[:cutoff_idx])

def compute_z(r):
    sp = r['spot_path']
    k = r['k']
    if sp is None or len(sp) < k + 1:
        return None
    try:
        sp = [float(x) for x in sp]
        strike = sp[0]
        spot_k = sp[k]
        log_returns = np.diff(np.log(sp[:k+1]))
        sigma = np.std(log_returns) * sp[k] if len(log_returns) > 0 else 0.0
        if sigma == 0:
            return None
        minutes_left = 15 - k - 1
        if minutes_left <= 0:
            return None
        z = abs(spot_k - strike) / (sigma * np.sqrt(minutes_left))
        return z
    except Exception:
        return None

# Find best IS combo
best_combo = None
best_is_score = -np.inf

print()
print("=" * 70)
print("ANALYSIS 4 - IS vs OOS ECONOMICS")
print(f"{'k':>3} {'T':>5} {'IS_qual/d':>10} {'IS_fill%':>9} {'IS_EV/c':>9} {'IS_c/d':>8}")
print("-" * 70)

is_scores = {}
for k in Ks:
    for T in Ts:
        key = (k, T)
        if key not in results:
            continue
        recs = results[key]
        is_recs = [r for r in recs if r['ws'] in is_ws]
        fill_recs = [r for r in is_recs if r['fill_occurred']]
        
        if not is_recs or not fill_recs:
            continue
        
        n_is_days = len(is_ws) / 96.0
        qual_per_day = len(is_recs) / n_is_days
        fill_rate = len(fill_recs) / len(is_recs)
        
        wt_evs = []
        for r in fill_recs:
            fp = r['fav_p']
            ev = (1.0 - fp) if r['res_fav'] else (-fp)
            w = min(r['contracts'], 5.0)
            wt_evs.append((ev, w))
        
        total_w = sum(w for _, w in wt_evs)
        mean_ev = sum(ev * w for ev, w in wt_evs) / total_w if total_w > 0 else float('nan')
        
        # c/day = qual/day * fill_rate * mean_contracts_filled * mean_ev
        mean_c_filled = np.mean([r['contracts'] for r in fill_recs])
        score = qual_per_day * fill_rate * mean_c_filled * mean_ev
        is_scores[key] = score
        
        print(f"{k:>3} {T:>5.2f} {qual_per_day:>10.2f} {100*fill_rate:>9.1f} {mean_ev:>9.4f} {score:>8.4f}")
        
        if score > best_is_score:
            best_is_score = score
            best_combo = key

print()
if best_combo:
    print(f"Best IS combo: k={best_combo[0]}, T={best_combo[1]:.2f}, IS_score={best_is_score:.4f}")
    
    # OOS evaluation
    oos_ws = set(ws_sorted[cutoff_idx:])
    recs = results[best_combo]
    oos_recs = [r for r in recs if r['ws'] in oos_ws]
    oos_fill = [r for r in oos_recs if r['fill_occurred']]
    
    n_oos_days = len(oos_ws) / 96.0
    
    if oos_recs and oos_fill:
        qual_per_day_oos = len(oos_recs) / n_oos_days
        fill_rate_oos = len(oos_fill) / len(oos_recs)
        
        wt_evs = []
        for r in oos_fill:
            fp = r['fav_p']
            ev = (1.0 - fp) if r['res_fav'] else (-fp)
            w = min(r['contracts'], 5.0)
            wt_evs.append((ev, w))
        total_w = sum(w for _, w in wt_evs)
        mean_ev_oos = sum(ev * w for ev, w in wt_evs) / total_w if total_w > 0 else float('nan')
        mean_c_oos = np.mean([r['contracts'] for r in oos_fill])
        oos_score = qual_per_day_oos * fill_rate_oos * mean_c_oos * mean_ev_oos
        
        print(f"OOS (no z-gate):  qual/d={qual_per_day_oos:.2f} fill%={100*fill_rate_oos:.1f} EV/c={mean_ev_oos:.4f} c/d={oos_score:.4f}")
    else:
        print(f"OOS: no qualifying data")
    
    # Z-gate analysis
    print()
    print("=" * 70)
    print("ANALYSIS 3 - Z-CONDITIONING (best IS combo)")
    print(f"{'z_bucket':>12} {'N':>7} {'EV/c':>9} {'flip%':>8}")
    print("-" * 70)
    
    all_fill_recs = [r for r in results[best_combo] if r['fill_occurred']]
    
    z_buckets = {'<1': [], '1-2': [], '>=2': []}
    for r in all_fill_recs:
        z = compute_z(r)
        if z is None:
            continue
        fp = r['fav_p']
        ev = (1.0 - fp) if r['res_fav'] else (-fp)
        flip = 0 if r['res_fav'] else 1
        rec = {'ev': ev, 'flip': flip}
        if z < 1:
            z_buckets['<1'].append(rec)
        elif z < 2:
            z_buckets['1-2'].append(rec)
        else:
            z_buckets['>=2'].append(rec)
    
    for bname, brecs in z_buckets.items():
        if not brecs:
            print(f"{bname:>12} {0:>7}  NO DATA")
            continue
        mean_ev = np.mean([r['ev'] for r in brecs])
        flip_rate = np.mean([r['flip'] for r in brecs])
        print(f"{bname:>12} {len(brecs):>7} {mean_ev:>9.4f} {100*flip_rate:>8.1f}")
    
    # Z-gate OOS
    print()
    print("OOS with z-gate (best combo)")
    print(f"{'z_gate':>8} {'qual/d':>8} {'fill%':>7} {'EV/c':>9} {'c/d':>8}")
    print("-" * 50)
    
    for z_thresh in [1.0, 2.0]:
        oos_fill_z = []
        oos_qual_z = 0
        for r in oos_recs:
            if r['fill_occurred']:
                z = compute_z(r)
                if z is not None and z >= z_thresh:
                    oos_fill_z.append(r)
            # count qualifying: those with fill_occurred=True or not, but z >= thresh
            z = compute_z(r)
            if z is not None and z >= z_thresh:
                oos_qual_z += 1
        
        if oos_qual_z == 0 or not oos_fill_z:
            print(f"{'>='+str(z_thresh):>8}  NO DATA")
            continue
        
        qpd = oos_qual_z / n_oos_days
        fr = len(oos_fill_z) / oos_qual_z
        
        wt_evs = []
        for r in oos_fill_z:
            fp = r['fav_p']
            ev = (1.0 - fp) if r['res_fav'] else (-fp)
            w = min(r['contracts'], 5.0)
            wt_evs.append((ev, w))
        total_w = sum(w for _, w in wt_evs)
        mean_ev_z = sum(ev * w for ev, w in wt_evs) / total_w if total_w > 0 else float('nan')
        mean_c_z = np.mean([r['contracts'] for r in oos_fill_z])
        score_z = qpd * fr * mean_c_z * mean_ev_z
        
        print(f"{'>='+str(z_thresh):>8} {qpd:>8.2f} {100*fr:>7.1f} {mean_ev_z:>9.4f} {score_z:>8.4f}")

print()
print("=" * 70)
print("DONE")
