"""When informed flow is directional, does LEANING WITH it (only complete/keep the leg the flow
agrees with; refuse the lagging side that gets adversely filled & stranded) beat always-pair?
This is the profitable version of 'informed flow fills us': position so the move COMPLETES the box
on the favorable side instead of stranding the wrong side. Pool 4 assets, IS/OOS."""
import sys; sys.path.insert(0,"/home/user/Codex-playground-")
import numpy as np, pandas as pd
recs=[]
for a in ("btc","eth","sol","xrp"):
    try:
        hist=pd.read_parquet(f"hist_kalshi_{a}15m.parquet").set_index("ws")
        tap=pd.read_parquet(f"trades_kalshi_{a}15m.parquet").set_index("ws")
    except: continue
    for ws in sorted(set(hist.index)&set(tap.index)):
        h=hist.loc[ws]; t=tap.loc[ws]; res=h.res_up
        if res not in (0,1): continue
        bid=np.asarray(h.bid_path,float); ask=np.asarray(h.ask_path,float)
        tt=np.asarray(t.t,float); p=np.asarray(t.p,float); sz=np.asarray(t.sz,float)/100.0; buy=np.asarray(t.buy,bool)
        for k in range(2,13):
            b0,a0=bid[k],ask[k]
            if np.isnan(b0) or np.isnan(a0) or not(0.03<=(b0+a0)/2<=0.97): continue
            # informed flow direction up to k: net signed take, weighted by size (large=informed)
            m=tt<=ws+60*k
            netflow=float(np.sum(np.where(buy[m],sz[m],-sz[m]))) if m.any() else 0.0
            lo,hi=ws+60*(k+1),ws+60*(k+2); i0,i1=np.searchsorted(tt,lo),np.searchsorted(tt,hi)
            db=da=False
            for i in range(i0,i1):
                if db and da: break
                if not db and not buy[i] and p[i]<=b0+1e-9:
                    recs.append((ws,k,"bid",b0,res-b0,netflow)); db=True
                if not da and buy[i] and p[i]>=a0-1e-9:
                    recs.append((ws,k,"ask",1-a0,a0-res,netflow)); da=True
df=pd.DataFrame(recs,columns=["ws","k","side","cost","settle","netflow"])
cut=df.ws.quantile(0.6)
# per-window box pairing P&L under policies
def policy_pnl(sub, lean=False, thr=200):
    net=0; pnl=0.0; held=None
    for _,f in sub.sort_values("k").iterrows():
        step=1 if f.side=="bid" else -1; nn=net+step
        if abs(nn)>1: continue
        if lean and held is None:
            # informed-lean: refuse to OPEN a leg the strong flow is AGAINST
            # bid(YES) leg favorable if netflow>0 (buyers); ask(NO) favorable if netflow<0
            fav = (f.side=="bid" and f.netflow>-thr) or (f.side=="ask" and f.netflow<thr)
            if abs(f.netflow)>thr and not fav: continue
        if held is not None and abs(nn)<abs(net): pnl+=f.settle+held; held=None
        else: held=f.settle
        net=nn
    if held is not None: pnl+=held
    return pnl
for tag,d in [("IS",df[df.ws<cut]),("OOS",df[df.ws>=cut])]:
    base=d.groupby("ws").apply(lambda s: policy_pnl(s,False),include_groups=False)
    for thr in (100,200,400):
        lean=d.groupby("ws").apply(lambda s: policy_pnl(s,True,thr),include_groups=False)
        diff=(lean-base)
        print(f"  {tag} thr={thr}: base {base.mean()*100:+.2f}c lean {lean.mean()*100:+.2f}c diff {diff.mean()*100:+.3f}c (t={diff.mean()/(diff.std()/np.sqrt(len(diff))):+.1f}, n={len(diff)})")
