#!/usr/bin/env python3
"""
final_robust.py -- plateau & robustness checks for the PP-core + active-satellite blend.
Confirms the blend's OOS edge over pure static is a PLATEAU not a spike:
  - per-calendar-year returns (is it one lucky year?)
  - rolling 3y Sharpe: fraction of windows where blend >= pure PP
  - block-bootstrap haircut: P(blend Sharpe > pure-PP Sharpe)
  - RP base sanity (does the plateau hold with a different static core?)
Reuses locked engines. Net 3bps/side. Full 2007-06+, OOS 2016-01+.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from static_allocation import load_all, fixed_weight_port, inverse_vol_port, stats, RISKPARITY
from portfolio_combined import sleeve_A, sleeve_B, combine_n

TD = 252; FULL="2007-06-01"; OOS="2016-01-01"
PP_W = {"SPY":0.25,"TLT":0.25,"GLD":0.25,"BIL":0.25}

def sub(n,s): return n[n.index>=pd.Timestamp(s)].dropna()

def roll_sharpe(net, win=756):
    return net.rolling(win).mean()/net.rolling(win).std()*np.sqrt(TD)

px = load_all()
pp = fixed_weight_port(px, PP_W, start=FULL)
rp = inverse_vol_port(px, RISKPARITY, start=FULL)
a = sleeve_A(start=FULL); b = sleeve_B(start=FULL)
active = combine_n([a,b],[0.7,0.3])

blend70 = sub(combine_n([pp,active],[0.7,0.3]), FULL)
blend_rp70 = sub(combine_n([rp,active],[0.7,0.3]), FULL)

print("="*80)
print("PLATEAU & ROBUSTNESS: 70/30 PP-core + active satellite vs pure PP")
print("="*80)

# per-year
df = pd.concat({"PP":pp,"BLEND70":blend70,"ACTIVE":sub(active,FULL)},axis=1,join="inner").dropna()
yr = (1+df).groupby(df.index.year).prod()-1
print("\nPer-calendar-year returns (%):")
print((yr*100).round(1).to_string())
wins = (yr["BLEND70"]>yr["PP"]).sum(); tot=len(yr)
print(f"\nYears blend>PP: {wins}/{tot}  ({wins/tot*100:.0f}%)")
print(f"Worst year  PP={yr['PP'].min()*100:.1f}%  BLEND={yr['BLEND70'].min()*100:.1f}%")

# rolling 3y sharpe dominance
rs_pp = roll_sharpe(df["PP"]); rs_bl = roll_sharpe(df["BLEND70"])
both = pd.concat([rs_pp,rs_bl],axis=1).dropna()
frac = (both.iloc[:,1] >= both.iloc[:,0]).mean()
print(f"\nRolling 3y Sharpe: blend >= PP in {frac*100:.0f}% of windows "
      f"(median blend={both.iloc[:,1].median():.2f} vs PP={both.iloc[:,0].median():.2f})")
# OOS only
bo = both[both.index>=pd.Timestamp(OOS)]
print(f"   OOS-only: blend>=PP in {(bo.iloc[:,1]>=bo.iloc[:,0]).mean()*100:.0f}% of windows")

# block bootstrap on OOS daily returns, 30% drift haircut, compare Sharpe distributions
def boot_sharpe(net, n=3000, block=21, hc=0.30, seed=11):
    rng=np.random.default_rng(seed); r=net.dropna().values; mu=r.mean()
    r=r-hc*mu; N=len(r); H=TD*3; nb=int(np.ceil(H/block)); out=np.empty(n)
    for p in range(n):
        st=rng.integers(0,N-block,nb)
        path=np.concatenate([r[s:s+block] for s in st])[:H]
        out[p]=path.mean()/path.std()*np.sqrt(TD)
    return out
sp_pp=boot_sharpe(sub(pp,OOS)); sp_bl=boot_sharpe(sub(blend70,OOS))
print(f"\nBlock-bootstrap (3y horizon, 30% drift haircut, OOS returns):")
print(f"   median Sharpe  PP={np.median(sp_pp):.2f}  BLEND={np.median(sp_bl):.2f}")
print(f"   P(blend Sharpe > pure-PP Sharpe, paired)= {np.mean(sp_bl>sp_pp)*100:.0f}%")

# RP base sanity
print("\nRP-core sanity (does plateau hold with risk-parity core?):")
for nm,n in [("Pure RP", sub(rp,OOS)), ("70/30 RP/active", sub(blend_rp70,OOS))]:
    s=stats(n); print(f"   OOS {nm:18} Sharpe={s['Sharpe']:.3f} maxDD={s['maxDD']*100:.2f}% CAGR={s['CAGR']*100:.2f}%")
print("="*80)
