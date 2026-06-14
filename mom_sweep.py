"""Run all signal/universe/weighting sweeps and print OOS tables (recent-regime focus)."""
import numpy as np
import pandas as pd
from functools import partial
import mom_backtest as mb

px, vol = mb.load_panel()
print(f"Panel: {px.shape[1]} syms, {px.index.min().date()} -> {px.index.max().date()}, {px.shape[0]} days")
print(f"OOS holdout = last 18mo; recent-regime = last 12mo. Costs default 9bps/side.\n")

def fmt(s):
    return f"Sh={s['sharpe']:+.2f} ann={s['ann_ret']*100:+.0f}% vol={s['ann_vol']*100:.0f}% n={s['n']}"

def line(label, bt):
    ws = mb.window_stats(bt)
    if ws is None:
        print(f"{label:42s} EMPTY"); return None
    full, oos, rec = ws
    print(f"{label:42s} | FULL {fmt(full)} | OOS18 {fmt(oos)} | REC12 {fmt(rec)}")
    return rec

# ============ 1. SIGNAL VARIANTS (top_n=15, equal weight, dollar-neutral baseline frame) ============
print("="*150)
print("SIGNAL VARIANTS  (universe top-15 by liquidity, equal-weight, 30% tails, 9bps/side)")
print("="*150)
TN=15; SCH="equal"; COST=9.0

# baseline plain-14d raw return rank
sig_results = {}
sig_results['plain-14d (BASELINE)'] = line("plain-14d raw return", mb.run_backtest(px,vol,mb.sig_raw,lb=14,top_n=TN,scheme=SCH,cost_bps=COST))
sig_results['raw-7d']   = line("raw-7d", mb.run_backtest(px,vol,mb.sig_raw,lb=7,top_n=TN,scheme=SCH,cost_bps=COST))
sig_results['raw-30d']  = line("raw-30d", mb.run_backtest(px,vol,mb.sig_raw,lb=30,top_n=TN,scheme=SCH,cost_bps=COST))
sig_results['raw-60d']  = line("raw-60d", mb.run_backtest(px,vol,mb.sig_raw,lb=60,top_n=TN,scheme=SCH,cost_bps=COST))
print("-"*150)
# (a) risk-adjusted
for lb in (14,30,60):
    sig_results[f'riskadj-{lb}d'] = line(f"riskadj (ret/vol) {lb}d", mb.run_backtest(px,vol,mb.sig_riskadj,lb=lb,top_n=TN,scheme=SCH,cost_bps=COST))
print("-"*150)
# (b) skip-recent (12-1 style)
for lb in (14,21,30):
    sig_results[f'skip3-{lb}d'] = line(f"skip-recent3 {lb}d->t-3", mb.run_backtest(px,vol,mb.sig_skip,lb=lb,top_n=TN,scheme=SCH,cost_bps=COST))
print("-"*150)
# (c) multi-lookback ensemble
sig_results['ensemble-7/14/30/60'] = line("ensemble rank 7/14/30/60", mb.run_backtest(px,vol,mb.sig_ensemble,top_n=TN,scheme=SCH,cost_bps=COST))
print("-"*150)
# (d) residual momentum vs BTC
for lb in (14,30,60):
    sig_results[f'residual-{lb}d'] = line(f"residual-vs-BTC {lb}d", mb.run_backtest(px,vol,mb.sig_residual,lb=lb,top_n=TN,scheme=SCH,cost_bps=COST))

# pick best signal by REC12 sharpe (among non-nan)
def rec_sh(d): return d['sharpe'] if d is not None and not np.isnan(d['sharpe']) else -9
best_sig = max(sig_results, key=lambda k: rec_sh(sig_results[k]))
print(f"\n>> BEST SIGNAL by REC12 Sharpe: {best_sig}  ({rec_sh(sig_results[best_sig]):+.2f})")

# map best signal label -> (fn, lb)
SIGMAP = {
    'plain-14d (BASELINE)': (mb.sig_raw,14), 'raw-7d':(mb.sig_raw,7),'raw-30d':(mb.sig_raw,30),'raw-60d':(mb.sig_raw,60),
    'riskadj-14d':(mb.sig_riskadj,14),'riskadj-30d':(mb.sig_riskadj,30),'riskadj-60d':(mb.sig_riskadj,60),
    'skip3-14d':(mb.sig_skip,14),'skip3-21d':(mb.sig_skip,21),'skip3-30d':(mb.sig_skip,30),
    'ensemble-7/14/30/60':(mb.sig_ensemble,14),
    'residual-14d':(mb.sig_residual,14),'residual-30d':(mb.sig_residual,30),'residual-60d':(mb.sig_residual,60),
}
bfn, blb = SIGMAP[best_sig]

# ============ 2. UNIVERSE SWEEP (best signal, equal weight) ============
print("\n"+"="*150)
print(f"UNIVERSE SWEEP  (signal={best_sig}, equal-weight, 9bps/side)")
print("="*150)
for tn in (8,15,25,40):
    line(f"top-{tn} (incl BTC/ETH)", mb.run_backtest(px,vol,bfn,lb=blb,top_n=tn,scheme=SCH,cost_bps=COST))
print("-"*150)
for tn in (15,25,40):
    line(f"top-{tn} (EXCL BTC/ETH)", mb.run_backtest(px,vol,bfn,lb=blb,top_n=tn,scheme=SCH,cost_bps=COST,exclude_mega=True))

# ============ 3. WEIGHTING SWEEP (best signal, top-15) ============
print("\n"+"="*150)
print(f"WEIGHTING SWEEP  (signal={best_sig}, top-15, 9bps/side)")
print("="*150)
for sch in ('equal','rank','signal','volinv'):
    line(f"weight={sch}", mb.run_backtest(px,vol,bfn,lb=blb,top_n=15,scheme=sch,cost_bps=COST))

# ============ 4. COST SENSITIVITY on best ============
print("\n"+"="*150)
print(f"COST SENSITIVITY  (signal={best_sig}, top-15, equal)")
print("="*150)
for c in (5,9,12,18):
    line(f"cost={c}bps/side", mb.run_backtest(px,vol,bfn,lb=blb,top_n=15,scheme=SCH,cost_bps=c))

# ============ 5. ROBUSTNESS: lookback plateau for best signal family ============
print("\n"+"="*150)
print(f"LOOKBACK PLATEAU  (best signal family, top-15, equal, 9bps) -- want plateau not spike")
print("="*150)
for lb in (7,10,14,21,30,45,60):
    line(f"lb={lb}d", mb.run_backtest(px,vol,bfn,lb=lb,top_n=15,scheme=SCH,cost_bps=COST))
