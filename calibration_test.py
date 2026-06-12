"""The RIGHT test: don't chase realized EV (hostage to the unobserved tail). Measure CALIBRATION
-- does the favorite settle MORE often than its price implies? -- with Wilson CIs. This uses EVERY
observation (not just the rare losses), so it's the data-efficient, generalizable answer."""
import numpy as np, pandas as pd
from scipy import stats
h = pd.read_parquet("hist_kalshi_btc15m.parquet")
def arr(v): return np.asarray(v, float)

def wilson(k, n, z=1.96):
    if n==0: return (0,0,1)
    p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d; hw=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return p, c-hw, c+hw

rows=[]
for _,r in h.iterrows():
    res=r.res_up
    if res not in (0,1): continue
    bid=arr(r.bid_path); ask=arr(r.ask_path)
    for k in (12,13,14):
        if k>=15 or np.isnan(bid[k]) or np.isnan(ask[k]): continue
        mid=(bid[k]+ask[k])/2; favy=mid>0.5; favp=mid if favy else 1-mid
        won = (res==1) if favy else (res==0)
        rows.append((k,favp,int(won)))
df=pd.DataFrame(rows,columns=["k","favp","won"])

print("CALIBRATION: realized favorite win-rate vs implied price (the break-even bar).")
print("If realized_LO (95% Wilson lower bound) > price, the threshold has a DEFENSIBLE positive edge.\n")
print(f"{'k':>2} {'price band':>12} {'n':>5} {'wins':>5} {'realized':>9} {'95% CI':>16} {'implied':>8} {'gap_LO':>8}")
for k in (12,13,14):
    for lo,hi in [(0.90,0.93),(0.93,0.95),(0.95,0.97),(0.97,0.99),(0.99,1.01)]:
        sub=df[(df.k==k)&(df.favp>=lo)&(df.favp<hi)]
        n=len(sub); w=sub.won.sum()
        if n<20: continue
        implied=sub.favp.mean()
        p,clo,chi=wilson(w,n)
        gap_lo = clo - implied   # >0 means even the pessimistic bound beats the price
        flag = " <-- EDGE" if gap_lo>0 else ""
        print(f"{k:>2} {f'[{lo:.2f},{hi:.2f})':>12} {n:>5} {w:>5} {p*100:>8.2f}% "
              f"[{clo*100:>5.1f},{chi*100:>5.1f}] {implied*100:>7.2f}% {gap_lo*100:>+7.2f}%{flag}")
