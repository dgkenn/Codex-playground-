"""Final confirmation of best config: 10d signal x weighting x universe, with plateau check.
Reports FULL / OOS18 / REC12 / PREV12 net Sharpe."""
import numpy as np, pandas as pd
import mom_backtest as mb

px, vol = mb.load_panel()
end = px.index.max()
rec12 = end - pd.DateOffset(months=12)
prev12 = end - pd.DateOffset(months=24)
oos18 = end - pd.DateOffset(months=18)

def slc(bt,s=None,e=None):
    r=bt["net"]
    if s is not None: r=r.loc[r.index>=s]
    if e is not None: r=r.loc[r.index<e]
    return mb.stats(r)

def row(label, bt):
    f=mb.stats(bt["net"]); o=slc(bt,oos18); r=slc(bt,rec12); p=slc(bt,prev12,rec12)
    print(f"{label:34s} FULL {f['sharpe']:+.2f}/{f['ann_ret']*100:+.0f}% | OOS18 {o['sharpe']:+.2f} | REC12 {r['sharpe']:+.2f}/{r['ann_ret']*100:+.0f}% | PREV12 {p['sharpe']:+.2f} | turn {bt['turnover'].mean():.2f}")

print("=== 10d SIGNAL x WEIGHTING (top-15, 9bps) ===")
for sig,fn in [("raw",mb.sig_raw),("riskadj",mb.sig_riskadj)]:
    for sch in ("equal","rank","signal","volinv"):
        row(f"{sig}-10d {sch}", mb.run_backtest(px,vol,fn,lb=10,top_n=15,scheme=sch,cost_bps=9.0))

print("\n=== riskadj-10d rank-weight x UNIVERSE (9bps) ===")
for tn in (8,15,25,40):
    row(f"top-{tn}", mb.run_backtest(px,vol,mb.sig_riskadj,lb=10,top_n=tn,scheme="rank",cost_bps=9.0))
for tn in (15,25):
    row(f"top-{tn} EXCL mega", mb.run_backtest(px,vol,mb.sig_riskadj,lb=10,top_n=tn,scheme="rank",cost_bps=9.0,exclude_mega=True))

print("\n=== PLATEAU around lb=10 (riskadj, top-15, rank, 9bps) ===")
for lb in (7,8,9,10,11,12,13,14):
    row(f"riskadj-{lb}d rank", mb.run_backtest(px,vol,mb.sig_riskadj,lb=lb,top_n=15,scheme="rank",cost_bps=9.0))

print("\n=== BASELINE for comparison (plain-14d raw, top-15, equal, 9bps) ===")
row("plain-14d BASELINE", mb.run_backtest(px,vol,mb.sig_raw,lb=14,top_n=15,scheme="equal",cost_bps=9.0))
