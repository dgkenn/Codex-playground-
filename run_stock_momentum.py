#!/usr/bin/env python3
"""Run the individual-stock momentum study and print all tables for STOCK_MOMENTUM.md."""
import numpy as np, pandas as pd, sys
sys.path.insert(0,"/tmp/stockmom")
from stock_momentum import (load_prices, load_etf, backtest, stats, worst_months,
                            cash_series, spy_series, UNIVERSE)

px = load_prices()
e = load_etf()
print("="*78)
print("DATA: stocks %s -> %s, %d names; eligible-name count grows over time" %
      (px.index.min().date(), px.index.max().date(), px.shape[1]))
# how many names have >=126d history at various points
for yr in [2002,2008,2016,2024]:
    asof = pd.Timestamp(f"{yr}-06-30")
    n = (px.loc[:asof].notna().sum() >= 126).sum()
    print(f"  names with >=6m history by {yr}-06: {n}")

FULL_START="2002-06-01"   # enough names + 12m lookback room
HOLDOUT="2016-01-01"
END="2026-06-12"

def row(label, net, to):
    s=stats(net)
    return f"{label:30s} CAGR {s['CAGR']*100:5.1f}%  Sharpe {s['Sharpe']:5.2f}  maxDD {s['maxDD']*100:6.1f}%  vol {s['vol']*100:4.1f}%  to/mo {to:.2f}"

print("\n"+"="*78)
print("1. LOOKBACK / K SWEEP  (risk-adj XS, no gate, full sample, skip-last-month)")
print("="*78)
for lb,lbl in [(126,"6m"),(189,"9m"),(252,"12m")]:
    for K in [10,15,20]:
        net,to=backtest(px,UNIVERSE,lookback_days=lb,K=K,skip_days=21,
                        risk_adj=True,dual=False,regime=False,partial=1.0,
                        start=FULL_START,end=END)
        print(row(f"{lbl} K={K}",net,to))

print("\n"+"="*78)
print("2. SKIP-LAST-MONTH effect (6m K=15, full)")
print("="*78)
for sk,lbl in [(0,"no skip"),(21,"skip 1m")]:
    net,to=backtest(px,UNIVERSE,lookback_days=126,K=15,skip_days=sk,
                    risk_adj=True,dual=False,regime=False,start=FULL_START,end=END)
    print(row(lbl,net,to))

print("\n"+"="*78)
print("3. GATES on best base (6m K=15 skip1m). XS only / +dual / +regime / +both / +partial")
print("="*78)
cfgs=[
 ("XS only",        dict(dual=False,regime=False,partial=1.0)),
 ("+dual",          dict(dual=True, regime=False,partial=1.0)),
 ("+regime(SPY200)",dict(dual=False,regime=True, partial=1.0)),
 ("+dual+regime",   dict(dual=True, regime=True, partial=1.0)),
 ("+both+partial.5",dict(dual=True, regime=True, partial=0.5)),
 ("+both+partial.34",dict(dual=True,regime=True, partial=0.34)),
]
best=None
for lbl,kw in cfgs:
    net,to=backtest(px,UNIVERSE,lookback_days=126,K=15,skip_days=21,risk_adj=True,
                    start=FULL_START,end=END,**kw)
    print(row(lbl,net,to))

print("\n"+"="*78)
print("4. BEST CONFIG (dual+regime+partial.34, 6m, skip1m) across K and windows")
print("="*78)
BEST=dict(lookback_days=126,skip_days=21,risk_adj=True,dual=True,regime=True,partial=0.34)
for K in [10,15,20]:
    net,to=backtest(px,UNIVERSE,K=K,start=FULL_START,end=END,**BEST)
    print(row(f"K={K} full 2002-26",net,to))
print("  -- windows at K=15 --")
for st,en,lbl in [(FULL_START,END,"full 2002-2026"),(HOLDOUT,END,"HOLDOUT 2016-2026"),
                  ("2010-01-01",END,"2010-2026"),("2020-01-01",END,"2020-2026")]:
    net,to=backtest(px,UNIVERSE,K=15,start=st,end=en,**BEST)
    print(row(lbl,net,to))

print("\n"+"="*78)
print("5. MOMENTUM CRASH behavior. Worst monthly returns, ungated vs gated (K=15,6m)")
print("="*78)
net_u,_=backtest(px,UNIVERSE,lookback_days=126,K=15,skip_days=21,risk_adj=True,
                 dual=False,regime=False,partial=1.0,start=FULL_START,end=END)
net_g,_=backtest(px,UNIVERSE,K=15,start=FULL_START,end=END,**BEST)
print("UNGATED worst months:")
print(worst_months(net_u,8).apply(lambda x:f"{x*100:.1f}%").to_string())
print("GATED(best) worst months:")
print(worst_months(net_g,8).apply(lambda x:f"{x*100:.1f}%").to_string())
# crash-window CAGR/DD: 2008-09, 2009 rebound, 2020
for st,en,lbl in [("2008-06-01","2009-12-31","GFC+2009-rebound"),
                  ("2020-01-01","2020-12-31","2020 COVID+recovery"),
                  ("2022-01-01","2022-12-31","2022 stock+bond")]:
    nu,_=backtest(px,UNIVERSE,lookback_days=126,K=15,skip_days=21,risk_adj=True,
                  dual=False,regime=False,partial=1.0,start=st,end=en)
    ng,_=backtest(px,UNIVERSE,K=15,start=st,end=en,**BEST)
    su,sg=stats(nu),stats(ng)
    print(f"  {lbl:22s} ungated maxDD {su['maxDD']*100:6.1f}% ret {((1+nu).prod()-1)*100:6.1f}% | "
          f"gated maxDD {sg['maxDD']*100:6.1f}% ret {((1+ng).prod()-1)*100:6.1f}%")

print("\n"+"="*78)
print("6. COST SENSITIVITY (best config, K=15, full)")
print("="*78)
for cb in [0,2,4,10,25]:
    net,to=backtest(px,UNIVERSE,K=15,start=FULL_START,end=END,cost_bps=cb,**BEST)
    s=stats(net)
    print(f"  {cb:2d} bps/side: CAGR {s['CAGR']*100:5.1f}%  Sharpe {s['Sharpe']:.2f}  to/mo {to:.2f}")

print("\n"+"="*78)
print("7. BENCHMARKS over matched windows")
print("="*78)
def bh(tkr,st,en):
    r=e[tkr].pct_change(); r=r[(r.index>=pd.Timestamp(st))&(r.index<=pd.Timestamp(en))]
    return r.dropna()
for st,lbl in [(FULL_START,"2002-2026"),(HOLDOUT,"2016-2026")]:
    spy=stats(bh("SPY",st,END))
    print(f"  SPY buy&hold {lbl}: CAGR {spy['CAGR']*100:.1f}%  Sharpe {spy['Sharpe']:.2f}  maxDD {spy['maxDD']*100:.1f}%")

print("\ndone.")
