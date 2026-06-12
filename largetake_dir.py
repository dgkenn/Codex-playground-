"""Can LARGE-taker direction give a directional signal? Large takes (>=50 ct) are informed (win at
settlement). Test: does net large-take direction predict res_up BEYOND the Kalshi mid, OOS? And does
it help the UNPAIRED-LEG hold/cut decision (no fee needed -- a position we already hold)?"""
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
def lg(p): return np.log(np.clip(p,1e-4,1-1e-4)/(1-np.clip(p,1e-4,1-1e-4)))
rows=[]
for a in ("btc","eth","sol","xrp"):
    try: tr=pd.read_parquet(f"trades_kalshi_{a}15m.parquet").set_index("ws")
    except: continue
    h=pd.read_parquet(f"hist_kalshi_{a}15m.parquet").set_index("ws")
    for ws in tr.index.unique():
        if ws not in h.index: continue
        hr=h.loc[ws]; res=hr.res_up
        if res not in (0,1): continue
        mid=np.asarray(hr.mid_path,float)
        t=tr.loc[ws]; tt=np.asarray(t.t,float); p=np.asarray(t.p,float)
        sz=np.asarray(t.sz,float)/100.0; buy=np.asarray(t.buy,bool)
        for k in (5,7,9,11):
            if np.isnan(mid[k]): continue
            # net LARGE-take direction up to minute k (signed contracts, takes >=50)
            m=(tt<=ws+60*k)&(sz>=50)
            lt=float(np.sum(np.where(buy[m],sz[m],-sz[m]))) if m.any() else 0.0
            # also net SMALL-take for contrast
            ms=(tt<=ws+60*k)&(sz<50)
            st=float(np.sum(np.where(buy[ms],sz[ms],-sz[ms]))) if ms.any() else 0.0
            rows.append((ws,k,mid[k],lt,st,int(res)))
df=pd.DataFrame(rows,columns=["ws","k","mid","ltdir","stdir","won"])
cut=df.ws.quantile(0.6)
tr_,te=df[df.ws<cut],df[df.ws>=cut]
print("Does LARGE-take direction beat the mid for predicting settlement, OOS?")
for k in (5,7,9,11):
    a_=tr_[tr_.k==k]; b=te[te.k==k]
    if len(b)<50: continue
    aucM=roc_auc_score(b.won,b.mid)
    mL=LogisticRegression(max_iter=2000).fit(np.c_[lg(a_.mid),a_.ltdir],a_.won)
    aucL=roc_auc_score(b.won,mL.predict_proba(np.c_[lg(b.mid),b.ltdir])[:,1])
    print(f"  k={k:2d} n={len(b):4d} | mid AUC {aucM:.4f} | +large-take-dir {aucL:.4f} (d={aucL-aucM:+.4f}) | coef {mL.coef_[0][1]:+.5f}")
# residual: does large-take direction predict the OUTCOME beyond the mid? (sign test)
te2=te.copy(); te2["resid"]=te2.won-te2.mid
print("\nResidual (won-mid) by large-take net direction sign, OOS:")
print(f"  large takes net BUY-YES (>+50ct): resid {te2[te2.ltdir>50].resid.mean()*100:+.2f}% (n={len(te2[te2.ltdir>50])})")
print(f"  large takes net SELL-YES (<-50ct): resid {te2[te2.ltdir<-50].resid.mean()*100:+.2f}% (n={len(te2[te2.ltdir<-50])})")
print(f"  (positive resid when net-buy = large takers right BEYOND the mid = a usable signal)")

print("\n\n===== DECISIVE: is the large-net-buy residual STABLE IS vs OOS? (stronger threshold, pool k) =====")
for thr in (50,100,200):
    print(f"\n  large-take net |dir| > {thr} ct:")
    for tag,sub in [("IS",df[df.ws<cut]),("OOS",df[df.ws>=cut])]:
        sub=sub.copy(); sub["resid"]=sub.won-sub.mid
        nb=sub[sub.ltdir>thr]; ns=sub[sub.ltdir<-thr]
        nbm=f"{nb.resid.mean()*100:+.1f}% (n={len(nb)})" if len(nb)>=10 else f"n={len(nb)} too small"
        nsm=f"{ns.resid.mean()*100:+.1f}% (n={len(ns)})" if len(ns)>=10 else f"n={len(ns)} too small"
        print(f"    {tag}: net-BUY resid {nbm} | net-SELL resid {nsm}")
# the economic version: a 'follow large takers' directional bet -- buy YES when large net-buy, OOS edge
sub=df[df.ws>=cut].copy()
strong=sub[sub.ltdir.abs()>100]
if len(strong)>20:
    # bet the large-taker direction: edge = (won-mid) in their direction
    edge=np.where(strong.ltdir>0, strong.won-strong.mid, strong.mid-strong.won)
    print(f"\n  'FOLLOW large takers' OOS: bet their direction when |net|>100 -> edge {edge.mean()*100:+.2f}% "
          f"(t={edge.mean()/(edge.std()/np.sqrt(len(edge))):+.1f}, n={len(strong)})")
