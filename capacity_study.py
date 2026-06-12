#!/usr/bin/env python3
"""
KXBTC15M Empirical Capacity Study - CORRECTED SCALE
Count units in API are in hundredths of contracts (cents).
Divide by 100 for actual contracts.
"""
import gzip, json, os, glob, datetime, subprocess
import numpy as np
import pandas as pd

SCALE = 100.0  # raw count -> actual contracts

# ─── 1. LOAD BOOK DATA ────────────────────────────────────────────────────────
book_files = (
    glob.glob('/home/user/Codex-playground-/overnight_data/book_kalshi_btc15m_*.jsonl.gz') +
    glob.glob('/home/user/Codex-playground-/gha_data/**/book_kalshi_btc15m_*.jsonl.gz', recursive=True)
)
print(f"Book files: {len(book_files)}")

def extract_touch_and_depth(levels, side='bid'):
    if not levels:
        return (None, 0, 0, 0, 0)
    arr = np.array(levels)
    prices = arr[:, 0]
    qtys   = arr[:, 1]
    if side == 'bid':
        touch_idx = np.argmax(prices)
        touch_price = prices[touch_idx]
        touch_qty   = qtys[touch_idx]
        m1 = prices >= touch_price - 0.01
        m2 = prices >= touch_price - 0.02
        m3 = prices >= touch_price - 0.03
    else:
        touch_idx = np.argmin(prices)
        touch_price = prices[touch_idx]
        touch_qty   = qtys[touch_idx]
        m1 = prices <= touch_price + 0.01
        m2 = prices <= touch_price + 0.02
        m3 = prices <= touch_price + 0.03
    return (touch_price, touch_qty, qtys[m1].sum(), qtys[m2].sum(), qtys[m3].sum())

def read_lines_safe(fpath):
    try:
        with gzip.open(fpath, 'rt') as f:
            return f.readlines()
    except EOFError:
        result = subprocess.run(['zcat', fpath], capture_output=True)
        return result.stdout.decode('utf-8', errors='replace').splitlines(keepends=True)

book_rows = []
for fpath in book_files:
    lines = read_lines_safe(fpath)
    n = 0
    for line in lines:
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get('type') != 'book':
            continue
        t = rec.get('t', 0)
        try:
            dt = datetime.datetime.utcfromtimestamp(t)
        except Exception:
            continue
        hour = dt.hour
        yes_levels = rec.get('yes', [])
        no_levels  = rec.get('no', [])
        yb_price, yb_t0, yb_d1, yb_d2, yb_d3 = extract_touch_and_depth(yes_levels, 'bid')
        nb_price, nb_t0, nb_d1, nb_d2, nb_d3 = extract_touch_and_depth(no_levels, 'bid')
        if yb_price is None or nb_price is None:
            continue
        if yb_price < 0.01 or nb_price < 0.01:
            continue
        # Book quantities are already in true contracts (not scaled)
        book_rows.append({
            'hour': hour,
            'yes_bid_price': yb_price,
            'yes_bid_t0': yb_t0,
            'yes_bid_d1': yb_d1,
            'yes_bid_d2': yb_d2,
            'yes_bid_d3': yb_d3,
            'no_bid_price': nb_price,
            'no_bid_t0': nb_t0,
            'no_bid_d1': nb_d1,
            'no_bid_d2': nb_d2,
            'no_bid_d3': nb_d3,
        })
        n += 1
    print(f"  {os.path.basename(fpath)}: {n} ticks")

bdf = pd.DataFrame(book_rows)
print(f"\nTotal book ticks: {len(bdf)}")
print(f"Hours covered: {sorted(bdf['hour'].unique())}")

# ─── 2. DEPTH DISTRIBUTIONS ───────────────────────────────────────────────────
percs = [10, 25, 50, 75, 90]
print("\n" + "="*72)
print("A. DEPTH DISTRIBUTIONS (book quantities ARE in true contracts)")
print("="*72)

for side, pfx in [('YES bid', 'yes_bid'), ('NO bid (=YES ask side)', 'no_bid')]:
    print(f"\n  --- {side} ---")
    mp = bdf[f'{pfx}_price'].median()
    print(f"  Median touch price: ${mp:.3f}")
    for label, col in [('Touch (0-tick)',  f'{pfx}_t0'),
                        ('Within 1 tick',  f'{pfx}_d1'),
                        ('Within 2 ticks', f'{pfx}_d2'),
                        ('Within 3 ticks', f'{pfx}_d3')]:
        vals = bdf[col]
        pct  = np.percentile(vals, percs)
        dol  = pct * mp
        ps   = '  '.join(f'{v:8.1f}' for v in pct)
        ds   = '  '.join(f'${v:8.2f}' for v in dol)
        print(f"  {label:20s} | ct  [ {ps} ]")
        print(f"  {' '*20} | $   [ {ds} ]")

# ─── 3. DEPTH BY HOUR ─────────────────────────────────────────────────────────
print("\n" + "="*72)
print("A2. TOUCH DEPTH BY HOUR (UTC) — median contracts, both sides")
print("="*72)
print(f"  {'Hr':>3}  {'YES_touch':>10}  {'NO_touch':>10}  {'MinSide':>8}  {'MinSide$':>10}  {'n_ticks':>7}")
for hour, grp in sorted(bdf.groupby('hour')):
    y  = grp['yes_bid_t0'].median()
    n  = grp['no_bid_t0'].median()
    mn = min(y, n)
    mp = min(grp['yes_bid_price'].median(), grp['no_bid_price'].median())
    print(f"  {hour:3d}  {y:10.1f}  {n:10.1f}  {mn:8.1f}  ${mn*mp:9.2f}  {len(grp):7d}")

# ─── 4. FLOW ANALYSIS ─────────────────────────────────────────────────────────
print("\n" + "="*72)
print("B. TAKER FLOW (tape_kalshi_btc15m.parquet — raw / 100 = true contracts)")
print("="*72)

trades = pd.read_parquet('/home/user/Codex-playground-/trades_kalshi_btc15m.parquet').set_index('ws')
ws_min, ws_max = trades.index.min(), trades.index.max()
print(f"  Windows: {len(trades)}")
print(f"  Date range: {datetime.datetime.utcfromtimestamp(ws_min)} to "
      f"{datetime.datetime.utcfromtimestamp(ws_max)} UTC")

flow_rows = []
for ws, row in trades.iterrows():
    sz  = np.array(row.sz,  dtype=float) / SCALE
    p   = np.array(row.p,   dtype=float)
    buy = np.array(row.buy, dtype=bool)
    t_arr = np.array(row.t, dtype=float)

    # Filter: maker-relevant price range & first 12 minutes of window
    ws_end = ws + 12 * 60
    mask = (p >= 0.35) & (p <= 0.65) & (t_arr <= ws_end)
    sz_m   = sz[mask];   p_m = p[mask];   buy_m = buy[mask]

    if len(sz_m) == 0:
        flow_rows.append({'buy_ct': 0, 'sell_ct': 0, 'total_ct': 0,
                          'buy_dol': 0, 'sell_dol': 0, 'total_dol': 0,
                          'min_side_ct': 0, 'min_side_dol': 0, 'n': 0})
        continue
    buy_ct  = sz_m[buy_m].sum()
    sell_ct = sz_m[~buy_m].sum()
    buy_dol = (sz_m[buy_m]  * p_m[buy_m]).sum()
    sell_dol= (sz_m[~buy_m] * p_m[~buy_m]).sum()
    flow_rows.append({
        'buy_ct': buy_ct, 'sell_ct': sell_ct, 'total_ct': buy_ct+sell_ct,
        'buy_dol': buy_dol, 'sell_dol': sell_dol, 'total_dol': buy_dol+sell_dol,
        'min_side_ct': min(buy_ct, sell_ct),
        'min_side_dol': min(buy_dol, sell_dol),
        'n': len(sz_m)
    })

flow = pd.DataFrame(flow_rows)

print(f"\n  Per-window flow distributions (p10/p25/med/p75/p90/p95):")
print(f"  {'Metric':28s} {'p10':>7} {'p25':>7} {'med':>7} {'p75':>7} {'p90':>7} {'p95':>7}")
for col, lbl in [('total_ct',    'Total volume (ct)'),
                  ('buy_ct',      'Buy taker (ct)'),
                  ('sell_ct',     'Sell taker (ct)'),
                  ('min_side_ct', 'Min-side (ct)'),
                  ('total_dol',   'Total volume ($)'),
                  ('min_side_dol','Min-side ($)')]:
    v = flow[col]
    ps = np.percentile(v, [10, 25, 50, 75, 90, 95])
    print(f"  {lbl:28s} {ps[0]:7.1f} {ps[1]:7.1f} {ps[2]:7.1f} {ps[3]:7.1f} {ps[4]:7.1f} {ps[5]:7.1f}")

# Per-minute flow (12 minute first portion)
pm_total = flow['total_ct'] / 12.0
pm_min   = flow['min_side_ct'] / 12.0
ps_pm = np.percentile(pm_total, [10, 25, 50, 75, 90])
print(f"\n  Per-minute total flow (ct/min): "
      f"p10={ps_pm[0]:.1f}  p25={ps_pm[1]:.1f}  med={ps_pm[2]:.1f}  p75={ps_pm[3]:.1f}  p90={ps_pm[4]:.1f}")
ps_pm_min = np.percentile(pm_min, [10, 25, 50, 75, 90])
print(f"  Per-minute min-side flow (ct/min): "
      f"p10={ps_pm_min[0]:.1f}  p25={ps_pm_min[1]:.1f}  med={ps_pm_min[2]:.1f}  p75={ps_pm_min[3]:.1f}  p90={ps_pm_min[4]:.1f}")

print(f"\n  Fraction of windows with >= X contracts of two-sided (min-side) flow:")
two_sided_any = (flow['buy_ct'] > 0) & (flow['sell_ct'] > 0)
print(f"  Any two-sided flow: {two_sided_any.mean()*100:.1f}%")
for X in [10, 50, 100, 500]:
    frac = (flow['min_side_ct'] >= X).mean()
    print(f"  min_side >= {X:4d} ct: {frac*100:.1f}% of windows")

# ─── 5. N-SWEEP ────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("C. FOOTPRINT AT SIZE N (N-SWEEP CAPACITY TABLE)")
print("="*72)

med_yes_touch   = bdf['yes_bid_t0'].median()
med_no_touch    = bdf['no_bid_t0'].median()
med_min_touch   = min(med_yes_touch, med_no_touch)
med_min_side_ct = flow['min_side_ct'].median()
med_total_ct    = flow['total_ct'].median()
med_pm_min      = pm_min.median()

print(f"\n  Reference medians:")
print(f"    yes-bid touch depth:   {med_yes_touch:.1f} ct")
print(f"    no-bid touch depth:    {med_no_touch:.1f} ct")
print(f"    min-side touch:        {med_min_touch:.1f} ct")
print(f"    min-side flow/window:  {med_min_side_ct:.1f} ct  (12-min, price 0.35-0.65)")
print(f"    per-minute min-side:   {med_pm_min:.1f} ct/min")

# Fill proxy: per-minute min-side >= N
# (q0=0 approximation: if that much trades THROUGH the touch, our quote gets filled)
ref_frac = (pm_min >= 1.0).mean() * 100  # 1-lot fill rate at q0=0

print(f"\n  {'N':>4}  {'%yes_touch':>11}  {'%no_touch':>10}  {'%flow_side':>11}  "
      f"{'fill_pm%':>9}  {'$col/win':>9}  {'$col/day':>10}")

Ns = [1, 2, 4, 8, 16, 32, 64]
cap_results = []
for N in Ns:
    pct_yes  = N / med_yes_touch   * 100
    pct_no   = N / med_no_touch    * 100
    pct_flow = N / med_min_side_ct * 100
    frac_fill = (pm_min >= N).mean() * 100
    dol_win   = N * 2 * 0.50  # N boxes x 2 legs x $0.50 avg
    dol_day   = dol_win * 38   # ~38 active windows/day per CLAUDE.md
    cap_results.append({
        'N': N, 'pct_yes': pct_yes, 'pct_no': pct_no,
        'pct_flow': pct_flow, 'frac_fill': frac_fill,
        'dol_win': dol_win, 'dol_day': dol_day
    })
    print(f"  {N:4d}  {pct_yes:11.2f}%  {pct_no:10.2f}%  {pct_flow:11.4f}%  "
          f"{frac_fill:9.1f}%  ${dol_win:7.2f}  ${dol_day:8.2f}")

# ─── 6. CONSTRAINT GATES ──────────────────────────────────────────────────────
print("\n" + "="*72)
print("D. CAPACITY CONSTRAINT GATES")
print("   (i)  N <= 10% median touch depth, both sides")
print("   (ii) N <= 5%  median per-window one-side flow")
print("   (iii)fill rate (per-min) at N >= 50% of 1-lot rate")
print("="*72)

print(f"\n  1-lot reference fill rate: {ref_frac:.1f}%  |  50% threshold: {ref_frac*0.50:.1f}%")

print(f"\n  {'N':>4}  {'(i)depth':>10}  {'(ii)flow':>10}  {'(iii)fill':>10}  {'ALL_PASS':>9}")
for r in cap_results:
    ok_i   = (r['pct_yes'] <= 10.0) and (r['pct_no'] <= 10.0)
    ok_ii  = r['pct_flow'] <= 5.0
    ok_iii = r['frac_fill'] >= ref_frac * 0.50
    ok_all = ok_i and ok_ii and ok_iii
    print(f"  {r['N']:4d}  {'PASS' if ok_i else 'FAIL':>10}  {'PASS' if ok_ii else 'FAIL':>10}  "
          f"{'PASS' if ok_iii else 'FAIL':>10}  {'YES' if ok_all else 'NO':>9}")

passing = [r for r in cap_results
           if (r['pct_yes'] <= 10.0) and (r['pct_no'] <= 10.0)
           and r['pct_flow'] <= 5.0
           and r['frac_fill'] >= ref_frac * 0.50]
if passing:
    best = passing[-1]
    print(f"\n  LARGEST N PASSING ALL GATES: N = {best['N']}")
    print(f"  $ per window at N={best['N']}: ${best['dol_win']:.2f}")
    print(f"  $ per day at N={best['N']} (x38 windows): ${best['dol_day']:.2f}")

# ─── 7. DOLLAR-TARGET REACHABILITY ────────────────────────────────────────────
print("\n" + "="*72)
print("D2. DOLLAR-TARGET REACHABILITY: $100 / $400 / $1000 working capital")
print("="*72)

med_yb_p = bdf['yes_bid_price'].median()
med_nb_p = bdf['no_bid_price'].median()
col_per_box = med_yb_p + med_nb_p
print(f"\n  Median yes_bid price: ${med_yb_p:.3f}")
print(f"  Median no_bid price:  ${med_nb_p:.3f}")
print(f"  Collateral per box:   ~${col_per_box:.3f}")

for target in [100, 400, 1000]:
    N_needed = target / col_per_box
    pct_yes  = N_needed / med_yes_touch   * 100
    pct_no   = N_needed / med_no_touch    * 100
    pct_flow = N_needed / med_min_side_ct * 100
    frac_n   = (pm_min >= N_needed).mean() * 100
    ok_i    = (pct_yes <= 10.0) and (pct_no <= 10.0)
    ok_ii   = pct_flow <= 5.0
    ok_iii  = frac_n >= ref_frac * 0.50
    binding = []
    if not ok_i:   binding.append('DEPTH')
    if not ok_ii:  binding.append('FLOW')
    if not ok_iii: binding.append('FILL_RATE')
    print(f"\n  Target ${target:5d}  (~{N_needed:.1f} contracts/window):")
    print(f"    (i)  N/touch yes/no: {pct_yes:.1f}% / {pct_no:.1f}%   limit=10%  -> {'PASS' if ok_i else 'FAIL'}")
    print(f"    (ii) N/1side_flow:   {pct_flow:.2f}%            limit= 5%  -> {'PASS' if ok_ii else 'FAIL'}")
    print(f"    (iii)fill rate/min:  {frac_n:.1f}%            need={ref_frac*0.50:.1f}%  -> {'PASS' if ok_iii else 'FAIL'}")
    print(f"    Binding:  {', '.join(binding) if binding else 'NONE — fits!'}")

# ─── 8. SANITY CHECK ─────────────────────────────────────────────────────────
print("\n" + "="*72)
print("E. SANITY CHECK vs $240k 24h STATED VOLUME")
print("="*72)

# Use hist vol_path for full-window volume (not filtered to 0.35-0.65 range)
hist = pd.read_parquet('/home/user/Codex-playground-/hist_kalshi_btc15m.parquet')
win_vols = []
for _, row in hist.iterrows():
    v = np.array(row.vol_path) / SCALE
    b = np.array(row.bid_path)
    a = np.array(row.ask_path)
    mids = (b + a) / 2.0
    valid = ~np.isnan(mids) & (mids > 0)
    if valid.any():
        avg_mid = mids[valid].mean()
    else:
        avg_mid = 0.50
    win_vols.append(v.sum() * avg_mid)

win_dol = np.array(win_vols)
med_win_dol = np.nanmedian(win_dol)
implied_24h = med_win_dol * 96
print(f"  Median per-window dollar volume (full): ${med_win_dol:,.0f}")
print(f"  Implied 24h dollar volume (x96 windows): ${implied_24h:,.0f}")
print(f"  Reported 24h volume: ~$240,000")
print()
for r in cap_results:
    pct = r['dol_day'] / 240000 * 100
    print(f"  N={r['N']:3d}: ${r['dol_day']:8.2f}/day  =  {pct:.4f}% of $240k")

print("\nDone.")
