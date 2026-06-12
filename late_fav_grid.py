"""Complete late-favorite-bid maker grid: T in 0.90..0.99, k in {12,13,14}, z in {all,>=1,>=2}.
Strict IS/OOS + Bonferroni. Reuses the validated mechanics."""
import numpy as np, pandas as pd
from scipy import stats

h = pd.read_parquet("hist_kalshi_btc15m.parquet")
tr = pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")

def arr(v): return np.asarray(v, float)
days = (h.ws.max()-h.ws.min())/86400.0

rows_all = []   # (ws, k, T, fav_price, won, fill_ctr, z)
trd = {ws: (arr(r.t), arr(r.p), arr(r.sz)/100.0, np.asarray(r.buy, bool)) for ws,r in tr.iterrows()}

for _,r in h.iterrows():
    ws=int(r.ws); res=r.res_up
    if res not in (0,1): continue
    bid=arr(r.bid_path); ask=arr(r.ask_path); spot=arr(r.spot_path)
    if ws not in trd: continue
    t,p,sz,buy = trd[ws]
    strike = spot[0] if not np.isnan(spot[0]) else np.nan
    # 1-min spot returns for sigma
    sret = np.diff(spot)/spot[:-1]
    sig1 = np.nanstd(sret)*np.nanmean(spot) if np.sum(~np.isnan(sret))>2 else np.nan
    for k in (12,13,14):
        if k>=15 or np.isnan(bid[k]) or np.isnan(ask[k]): continue
        mid=(bid[k]+ask[k])/2
        favy = mid>0.5
        favp = mid if favy else 1-mid
        # our bid touch & the taker flow that hits it, in remaining window
        lo=ws+60*(k+1); 
        m=(t>=lo)
        if favy:
            hit = m & (~buy) & (p<=bid[k]+1e-9)   # taker sells YES into our YES bid
            entry=bid[k]
        else:
            hit = m & (buy) & (p>=ask[k]-1e-9)     # taker buys YES (sells NO) into our NO bid
            entry=1-ask[k]
        ctr = sz[hit].sum()
        won = (res==1) if favy else (res==0)
        ev = (1-entry) if won else (-entry)
        minleft=15-k
        z = abs(spot[k]-strike)/(sig1*np.sqrt(minleft)) if (sig1 and sig1>0 and not np.isnan(spot[k])) else np.nan
        rows_all.append((ws,k,favp,entry,won,ctr,ev,z))

df=pd.DataFrame(rows_all, columns=["ws","k","favp","entry","won","ctr","ev","z"])
cut=df.ws.quantile(0.6)
res=[]
for T in [round(x,2) for x in np.arange(0.90,0.991,0.01)]:
    for k in (12,13,14):
        for zg,zname in [(0,"all"),(1,"z>=1"),(2,"z>=2")]:
            q = df[(df.k==k)&(df.favp>=T)&(df.ctr>0)]
            if zg>0: q=q[q.z>=zg]
            if len(q)<10: continue
            for tag,sub in [("IS",q[q.ws<cut]),("OOS",q[q.ws>=cut])]:
                if len(sub)<8: 
                    res.append((T,k,zname,tag,len(sub),np.nan,np.nan,np.nan)); continue
                w=np.minimum(sub.ctr,5)
                evc=np.average(sub.ev, weights=w)
                # per-window EV t-stat (unweighted, conservative)
                tstat = sub.ev.mean()/(sub.ev.std(ddof=1)/np.sqrt(len(sub))) if sub.ev.std()>0 else np.nan
                qpd=len(sub)/(days*0.6 if tag=="IS" else days*0.4)
                res.append((T,k,zname,tag,len(sub),evc,evc*qpd*100,tstat))
R=pd.DataFrame(res, columns=["T","k","z","split","n","evc","cday","t"])
isp=R[R.split=="IS"]; oosp=R[R.split=="OOS"]
m=isp.merge(oosp,on=["T","k","z"],suffixes=("_is","_oos"))
print(f"combos tested: {len(m)} | days={days:.0f}")
print(f"IS EV/ctr > 0: {(m.evc_is>0).sum()}/{len(m)}")
print(f"OOS EV/ctr > 0: {(m.evc_oos>0).sum()}/{len(m)}")
print(f"positive in BOTH IS and OOS: {((m.evc_is>0)&(m.evc_oos>0)).sum()}/{len(m)}")
print(f"\nBonferroni bar for 60+ combos, FWER 0.05: |t|>=3.35")
surv=m[(m.evc_is>0)&(m.evc_oos>0)&(m.t_oos>=2.0)].sort_values("cday_oos",ascending=False)
print(f"\nSurvivors (both>0, OOS t>=2.0): {len(surv)}")
print(surv[["T","k","z","evc_oos","cday_oos","t_oos"]].head(8).to_string(index=False))
bonf=m[(m.evc_is>0)&(m.evc_oos>0)&(m.t_oos>=3.35)]
print(f"\nSurvivors past BONFERRONI (OOS t>=3.35): {len(bonf)}")
if len(bonf): print(bonf[["T","k","z","evc_oos","cday_oos","t_oos"]].to_string(index=False))
print("\nTop-5 by IS c/day, with their OOS:")
top=m.sort_values("cday_is",ascending=False).head(5)
print(top[["T","k","z","cday_is","cday_oos","t_oos"]].to_string(index=False))

print("\n=== CAPACITY/REALISM for the 4 Bonferroni survivors ===")
for T,k,zg in [(0.99,12,2),(0.97,13,2),(0.98,13,2),(0.99,13,2)]:
    q=df[(df.k==k)&(df.favp>=T)&(df.ctr>0)&(df.z>=zg)]
    oos=q[q.ws>=cut]
    print(f"T={T} k={k} z>=2: OOS n={len(oos)} | {len(oos)/(days*0.4):.1f} windows/day | "
          f"med fill {oos.ctr.median():.0f} ctr | entry price {oos.entry.mean():.3f} | win {oos.won.mean()*100:.1f}%")
