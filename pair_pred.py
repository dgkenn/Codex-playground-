"""Do COUNTERPARTY features predict whether a leg PAIRS? Label: a fill at minute k pairs if an
OPPOSITE-side fill occurs later in the window. Features = WHO crossed us: take size, flow sign
(momentum vs contrarian), spot move. Pool 4 assets. IS/OOS 60/40."""
import sys; sys.path.insert(0,"/home/user/Codex-playground-")
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
recs=[]
for a in ("btc","eth","sol","xrp"):
    try:
        hist=pd.read_parquet(f"hist_kalshi_{a}15m.parquet").set_index("ws")
        tap=pd.read_parquet(f"trades_kalshi_{a}15m.parquet").set_index("ws")
    except: continue
    common=sorted(set(hist.index)&set(tap.index))
    for ws in common:
        h=hist.loc[ws]; t=tap.loc[ws]
        bid=np.asarray(h.bid_path,float); ask=np.asarray(h.ask_path,float); spot=np.asarray(h.spot_path,float)
        spot_l=np.concatenate([[np.nan],spot[:-1]])
        tt=np.asarray(t.t,float); p=np.asarray(t.p,float); sz=np.asarray(t.sz,float)/100.0; buy=np.asarray(t.buy,bool)
        # reconstruct front-of-queue fills per minute + WHO crossed
        fills=[]  # (k, side 'bid'/'ask', take_size, flow_sign_vs_leg)
        for k in range(2,13):
            b0,a0=bid[k],ask[k]
            if np.isnan(b0) or np.isnan(a0) or not(0.03<=(b0+a0)/2<=0.97): continue
            s_now,s_then=spot_l[k],spot_l[max(k-3,0)]
            mv=(s_now/s_then-1)*1e4 if (s_now>0 and s_then>0) else 0.0
            lo,hi=ws+60*(k+1),ws+60*(k+2)
            i0,i1=np.searchsorted(tt,lo),np.searchsorted(tt,hi)
            db=da=False
            for i in range(i0,i1):
                if db and da: break
                if not db and not buy[i] and p[i]<=b0+1e-9:
                    fills.append((k,"bid",sz[i],mv)); db=True   # our YES bid hit by a seller
                if not da and buy[i] and p[i]>=a0-1e-9:
                    fills.append((k,"ask",sz[i],-mv)); da=True  # our NO bid hit by a buyer
        # pairing label: a leg pairs if an OPPOSITE side fill exists later
        bid_ks=[f[0] for f in fills if f[1]=="bid"]; ask_ks=[f[0] for f in fills if f[1]=="ask"]
        for (k,side,tks,flowvs) in fills:
            opp = ask_ks if side=="bid" else bid_ks
            paired=int(any(ok>k for ok in opp))
            recs.append((ws,k,side,tks,flowvs,mv if side=="bid" else -mv,paired))
df=pd.DataFrame(recs,columns=["ws","k","side","tksize","flowvs","spotvs","paired"])
print(f"fills={len(df)} | overall pair rate {df.paired.mean()*100:.1f}%")
cut=df.ws.quantile(0.6); tr_,te=df[df.ws<cut],df[df.ws>=cut]
# does a BIG take predict NO pair? does adverse spot predict no pair?
print("\nPair rate by counterparty feature (OOS):")
print(f"  small take (<50): {te[te.tksize<50].paired.mean()*100:.1f}% (n={len(te[te.tksize<50])}) | large take (>=50): {te[te.tksize>=50].paired.mean()*100:.1f}% (n={len(te[te.tksize>=50])})")
print(f"  spot move favorable to leg (<=0): {te[te.spotvs<=0].paired.mean()*100:.1f}% | adverse (>5bp): {te[te.spotvs>5].paired.mean()*100:.1f}%")
# AUC: do counterparty features predict pairing OOS, beyond minute-k (the known dominant predictor)?
for label,cols in [("k only",["k"]),("k+counterparty",["k","tksize","flowvs","spotvs"])]:
    X=tr_[cols].fillna(0); m=LogisticRegression(max_iter=2000).fit(X,tr_.paired)
    auc=roc_auc_score(te.paired, m.predict_proba(te[cols].fillna(0))[:,1])
    print(f"  AUC {label}: {auc:.4f}")
