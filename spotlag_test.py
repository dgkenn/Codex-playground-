"""THE test: does Kalshi mid LAG spot? If spot moved but the Kalshi mid hasn't caught up, the mid
is stale -> (a) directional edge for unpaired legs, (b) legal stale-quote snipe. Test if spot-vs-mid
divergence at minute k predicts res_up BEYOND mid_k alone, OOS. Pool 4 assets."""
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
def arr(v): return np.asarray(v,float)
rows=[]
for a in ("btc","eth","sol","xrp"):
    try: h=pd.read_parquet(f"hist_kalshi_{a}15m.parquet")
    except: continue
    for _,r in h.iterrows():
        if r.res_up not in (0,1): continue
        mid=arr(r.mid_path); spot=arr(r.spot_path)
        for k in (5,7,9,11):
            if np.isnan(mid[k]) or np.isnan(spot[k]) or np.isnan(spot[max(k-3,0)]): continue
            s0=spot[max(k-3,0)]
            spot_ret = (spot[k]/s0 - 1)*1e4 if s0>0 else 0.0   # bps move over last 3 min
            # spot move NOT yet in the mid: implied move vs actual spot move
            rows.append((r.ws,k,mid[k],spot_ret,int(r.res_up)))
df=pd.DataFrame(rows,columns=["ws","k","mid","spotret","won"])
cut=df.ws.quantile(0.6)
tr=df[df.ws<cut]; te=df[df.ws>=cut]
import numpy as np
def logit(p): return np.log(np.clip(p,1e-4,1-1e-4)/(1-np.clip(p,1e-4,1-1e-4)))
# Model A: mid alone. Model B: mid + spot-lag. Compare OOS.
for k in (5,7,9,11):
    trk=tr[tr.k==k]; tek=te[te.k==k]
    if len(tek)<50: continue
    yA=roc_auc_score(tek.won, tek.mid)               # mid alone OOS AUC
    Xtr=np.c_[logit(trk.mid), trk.spotret]; Xte=np.c_[logit(tek.mid), tek.spotret]
    m=LogisticRegression(max_iter=2000).fit(Xtr, trk.won)
    pB=m.predict_proba(Xte)[:,1]
    yB=roc_auc_score(tek.won, pB)
    llA=log_loss(tek.won, tek.mid); llB=log_loss(tek.won, pB)
    coef=m.coef_[0][1]
    print(f"k={k:2d} n_oos={len(tek):4d} | mid-alone AUC {yA:.4f} | +spotlag AUC {yB:.4f} "
          f"(d={yB-yA:+.4f}) | logloss {llA:.4f}->{llB:.4f} | spot coef {coef:+.5f}")
# pooled
trk=tr; tek=te
Xtr=np.c_[logit(trk.mid),trk.spotret,trk.k]; Xte=np.c_[logit(tek.mid),tek.spotret,tek.k]
m=LogisticRegression(max_iter=2000).fit(Xtr,trk.won); pB=m.predict_proba(Xte)[:,1]
print(f"\nPOOLED: mid-alone AUC {roc_auc_score(tek.won,tek.mid):.4f} | +spotlag AUC {roc_auc_score(tek.won,pB):.4f}")
# economic: does spotret sign predict res beyond mid? bucket by spotret tercile, residual vs mid
te2=te.copy(); te2["resid"]=te2.won-te2.mid
print("\nResidual (won - mid) by spot-move sign, OOS (positive resid = mid UNDERpriced the move):")
print(f"  spot UP >+20bps:   mean resid {te2[te2.spotret>20].resid.mean()*100:+.2f}% (n={len(te2[te2.spotret>20])})")
print(f"  spot flat:         mean resid {te2[abs(te2.spotret)<=20].resid.mean()*100:+.2f}%")
print(f"  spot DOWN <-20bps: mean resid {te2[te2.spotret<-20].resid.mean()*100:+.2f}% (n={len(te2[te2.spotret<-20])})")
