"""Robustness diagnostics: distinguish plateau from spike for top candidates.
- Fine lookback grid for raw vs riskadj.
- Turnover/break-even cost.
- Stability across two OOS split points (last 12mo AND prior 12mo, i.e. 24->12mo ago).
- Subperiod consistency (year-by-year REC).
"""
import numpy as np, pandas as pd
import mom_backtest as mb

px, vol = mb.load_panel()

def st(bt, start=None, end=None):
    r = bt["net"]
    if start is not None: r = r.loc[r.index >= start]
    if end is not None: r = r.loc[r.index < end]
    return mb.stats(r)

end = px.index.max()
rec12 = end - pd.DateOffset(months=12)
prev12 = end - pd.DateOffset(months=24)  # window [24mo,12mo) ago = independent OOS slice

print("FINE LOOKBACK GRID  (top-15, equal, 9bps) -- RECENT12 and PRIOR12 (24->12mo ago) Sharpe")
print(f"{'cfg':24s} {'FULL Sh':>9} {'REC12 Sh':>9} {'PREV12 Sh':>9} {'avg_turn':>9}")
for name, fn in [("raw", mb.sig_raw), ("riskadj", mb.sig_riskadj)]:
    for lb in (5,7,10,12,14,18,21,28):
        bt = mb.run_backtest(px,vol,fn,lb=lb,top_n=15,scheme="equal",cost_bps=9.0)
        if bt.empty: continue
        f = mb.stats(bt["net"])
        r = st(bt, start=rec12)
        p = st(bt, start=prev12, end=rec12)
        turn = bt["turnover"].mean()
        print(f"{name+'-'+str(lb)+'d':24s} {f['sharpe']:>9.2f} {r['sharpe']:>9.2f} {p['sharpe']:>9.2f} {turn:>9.2f}")

print("\nYEAR-BY-YEAR (net Sharpe) for key configs (top-15 equal 9bps):")
cfgs = [("raw-7d",mb.sig_raw,7),("raw-10d",mb.sig_raw,10),("raw-14d",mb.sig_raw,14),
        ("riskadj-14d",mb.sig_riskadj,14),("plain-14d-base",mb.sig_raw,14)]
years = [2021,2022,2023,2024,2025,2026]
hdr = f"{'cfg':16s}" + "".join(f"{y:>8}" for y in years)
print(hdr)
for name,fn,lb in cfgs:
    bt = mb.run_backtest(px,vol,fn,lb=lb,top_n=15,scheme="equal",cost_bps=9.0)
    row=f"{name:16s}"
    for y in years:
        r = bt["net"].loc[(bt.index>=f"{y}-01-01")&(bt.index<f"{y+1}-01-01")]
        s = mb.stats(r)["sharpe"]
        row += f"{s:>8.2f}" if not np.isnan(s) else f"{'--':>8}"
    print(row)

# break-even cost for raw-7d and riskadj-14d (REC12)
print("\nBREAK-EVEN cost (REC12 Sharpe->0), top-15 equal:")
for name,fn,lb in [("raw-7d",mb.sig_raw,7),("riskadj-14d",mb.sig_riskadj,14)]:
    for c in (9,18,30,50,80,120):
        bt=mb.run_backtest(px,vol,fn,lb=lb,top_n=15,scheme="equal",cost_bps=c)
        s=st(bt,start=rec12)["sharpe"]
        print(f"  {name:12s} cost={c:>3}bps  REC12 Sh={s:+.2f}")
