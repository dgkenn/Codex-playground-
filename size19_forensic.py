"""Deep forensic on the size-19 taker: is it ONE coherent informed algo, what's its strategy
signature, and is the edge COPYABLE (a visible rule) or informational (can't replicate)?"""
import pandas as pd, numpy as np
from collections import Counter
recs=[]
for a in ("btc","eth","sol","xrp"):
    try: tr=pd.read_parquet(f"trades_kalshi_{a}15m.parquet").set_index("ws")
    except: continue
    h=pd.read_parquet(f"hist_kalshi_{a}15m.parquet").set_index("ws")
    for ws in tr.index.unique():
        if ws not in h.index: continue
        hr=h.loc[ws]; res=hr.res_up
        if res not in (0,1): continue
        spot=np.asarray(hr.spot_path,float)
        t=tr.loc[ws]; tt=np.asarray(t.t,float); p=np.asarray(t.p,float)
        sz=np.round(np.asarray(t.sz,float)/100.0).astype(int); buy=np.asarray(t.buy,bool)
        for i in range(len(p)):
            if sz[i] not in (18,19,20): continue
            k=int((tt[i]-ws)//60)
            sm = (spot[min(k,14)]/spot[max(k-2,0)]-1)*1e4 if (k<15 and spot[max(k-2,0)]>0) else 0.0
            tk_edge = (res-p[i]) if buy[i] else (p[i]-res)
            recs.append((a,ws,sz[i],k,p[i],bool(buy[i]),res,sm,tk_edge))
df=pd.DataFrame(recs,columns=["asset","ws","sz","k","p","buy","res","spotmv","edge"])
for S in (19,18,20):
    d=df[df.sz==S]
    if len(d)<50: continue
    print(f"\n===== SIZE {S}: n={len(d)} | windows={d.ws.nunique()} | assets={dict(d.asset.value_counts())}")
    print(f"  taker EDGE: {d.edge.mean()*100:+.2f}c/ct (t={d.edge.mean()/(d.edge.std()/np.sqrt(len(d))):+.1f}) | win {(d.edge>0).mean()*100:.0f}%")
    print(f"  direction: {d.buy.mean()*100:.0f}% buy-YES | price mean {d.p.mean():.2f} | minute mean {d.k.mean():.1f}")
    # strategy signature: takes WITH spot momentum? at favorites? early/late?
    print(f"  buys when spot UP: buy-rate|spotmv>5bp = {d[d.spotmv>5].buy.mean()*100:.0f}% vs |spotmv<-5bp = {d[d.spotmv<-5].buy.mean()*100:.0f}%")
    print(f"  price buckets: <0.3 {len(d[d.p<0.3])} | 0.3-0.7 {len(d[(d.p>=0.3)&(d.p<0.7)])} | >0.7 {len(d[d.p>=0.7])}")
    print(f"  minute split: early(k<=5) {len(d[d.k<=5])} edge {d[d.k<=5].edge.mean()*100:+.1f}c | late(k>=10) {len(d[d.k>=10])} edge {d[d.k>=10].edge.mean()*100:+.1f}c")
    # coherence: bursty (clustered in windows) or uniform?
    perwin=d.ws.value_counts()
    print(f"  clustering: {(perwin>=3).sum()} windows with >=3 size-{S} takes (bursty) of {len(perwin)} windows")

print("\n\n===== DECISIVE: is size-19's edge SKILL or longshot fat-tail variance? =====")
d=df[df.sz==19]
for lab,sub in [("longshot p<0.3",d[d.p<0.3]),("mid 0.3-0.7",d[(d.p>=0.3)&(d.p<0.7)]),("favorite p>0.7",d[d.p>=0.7])]:
    if len(sub)<20: continue
    # does taker beat the PRICE (informed) -> realized win rate vs implied price
    impl = sub.apply(lambda r: r.p if r.buy else 1-r.p, axis=1).mean()  # taker's implied win prob
    realw = (sub.edge>0).mean()
    print(f"  {lab:>16}: n={len(sub)} edge {sub.edge.mean()*100:+.1f}c | taker realized-win {realw*100:.0f}% vs implied {impl*100:.0f}% (>0 gap=informed)")
# the killer: remove the longshot tail -- does any edge remain on the calibrated mid?
mid=d[(d.p>=0.3)&(d.p<0.7)]
print(f"\n  EDGE WITH LONGSHOTS REMOVED (only mid 0.3-0.7, where market is calibrated): "
      f"{mid.edge.mean()*100:+.2f}c (t={mid.edge.mean()/(mid.edge.std()/np.sqrt(len(mid))):+.1f}, n={len(mid)})")
# bootstrap the skew: how much of total edge is the top-5 single trades?
e=np.sort(d.edge.values)[::-1]
print(f"  fat-tail check: top-5 trades contribute {e[:5].sum()/d.edge.sum()*100:.0f}% of total edge; "
      f"median trade edge {np.median(d.edge)*100:+.2f}c")
