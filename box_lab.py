"""Box mechanism lab: evidence for detection/profit levers on the real tape."""
import sys
import numpy as np, pandas as pd

def tstat(x):
    x=np.asarray(x,float); x=x[~np.isnan(x)]
    return float(x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))) if len(x)>7 and x.std(ddof=1)>0 else float("nan")

def quotes(asset):
    """One row per (window, minute) BOTH-SIDES quote opportunity with completion outcome."""
    hist=pd.read_parquet(f"hist_kalshi_{asset}15m.parquet").set_index("ws")
    tap=pd.read_parquet(f"trades_kalshi_{asset}15m.parquet").set_index("ws")
    common=sorted(set(hist.index)&set(tap.index))
    rows=[]
    for w in common:
        h=hist.loc[w]; t=tap.loc[w]
        res=float(h.res_up)
        bid=np.asarray(h.bid_path,float); ask=np.asarray(h.ask_path,float)
        spot=np.asarray(h.spot_path,float); spot_l=np.concatenate([[np.nan],spot[:-1]])
        ta=np.asarray(t.t,float); pa=np.asarray(t.p,float); sa=np.asarray(t.sz,float); ba=np.asarray(t.buy,bool)
        for k in range(2,13):
            b0,a0=bid[k],ask[k]
            if np.isnan(b0) or np.isnan(a0) or not (0.03<=(b0+a0)/2<=0.97): continue
            sp=a0-b0
            s_now,s_then=spot_l[k],spot_l[max(k-3,0)]
            mv=(s_now/s_then-1)*1e4 if (s_now>0 and s_then>0) else np.nan
            pl,ph=w+60*(k-1),w+60*k
            j0,j1=np.searchsorted(ta,pl),np.searchsorted(ta,ph)
            fl=float(np.sum(np.where(ba[j0:j1],sa[j0:j1],-sa[j0:j1])))
            trd=float(np.sum(sa[j0:j1]))
            lo,hi=w+60*(k+1),w+60*(k+2)
            i0,i1=np.searchsorted(ta,lo),np.searchsorted(ta,hi)
            fb=fa=False; tb=tn=np.nan
            for i in range(i0,i1):
                p,sz,buy=pa[i],sa[i],ba[i]
                if not fb and not buy and p<=b0+1e-9: fb=True; tb=ta[i]
                if not fa and buy and p>=a0-1e-9: fa=True; tn=ta[i]
                if fb and fa: break
            rows.append((w,k,b0,a0,sp,mv,fl,trd,res,fb,fa))
    return pd.DataFrame(rows,columns=["ws","k","b","a","sp","mv","fl","trd","res","fb","fa"])

asset=sys.argv[1] if len(sys.argv)>1 else "btc"
q=quotes(asset)
q["both"]=q.fb&q.fa
q["pnl"]=np.where(q.both, q.a-q.b, np.where(q.fb, q.res-q.b, np.where(q.fa, q.a-q.res, 0.0)))
q["any"]=q.fb|q.fa
print(f"=== {asset}: {len(q)} quote-minutes, {q.ws.nunique()} windows ===")
print(f"P(any fill)={q['any'].mean():.3f}  P(both|any)={q.both.sum()/max(q['any'].sum(),1):.3f}  avg lock when both={q[q.both].sp.mean()*100:.2f}c")

print("\n[1] MIN-LOCK FLOOR (quote both only when spread>=floor):")
for f in (0.0,0.02,0.03,0.04,0.06):
    m=q.sp>=f-1e-9
    d=q[m]; by=d.groupby("ws").pnl.sum()
    print(f"  floor {f*100:>3.0f}c: opp={m.mean()*100:>3.0f}% P(both)={d.both.mean():.3f} net/win={by.mean()*100:>+6.2f}c t={tstat(by):>+5.1f}")

print("\n[2] MINUTE-OF-WINDOW (lock potential + completion by k):")
g=q.groupby("k").agg(sp=("sp","mean"),both=("both","mean"),pnl=("pnl","mean"))
for k,r in g.iterrows():
    print(f"  k={k:>2}: spread={r.sp*100:>5.2f}c P(both)={r.both:.3f} pnl/quote={r.pnl*100:+.3f}c")

print("\n[3] CHURN vs TREND regime (3-min |spot move| bps x trade rate):")
q["vol_b"]=pd.cut(q.mv.abs(),[0,2,5,10,1e9],labels=["<2","2-5","5-10",">10"])
g=q.groupby("vol_b",observed=True).agg(n=("both","size"),both=("both","mean"),pnl=("pnl","mean"))
print(g.assign(pnl=lambda d:(d.pnl*100).round(3)).to_string())

print("\n[4] FLOW BALANCE (prior-minute |imbalance|, contracts):")
q["fl_b"]=pd.cut(q.fl.abs(),[0,50,250,1000,1e12],labels=["<50","50-250","250-1k",">1k"])
g=q.groupby("fl_b",observed=True).agg(n=("both","size"),both=("both","mean"),pnl=("pnl","mean"))
print(g.assign(pnl=lambda d:(d.pnl*100).round(3)).to_string())

print("\n[5] PRICE LEVEL |p-0.5|:")
q["lv"]=pd.cut((q.b+q.a).div(2).sub(0.5).abs(),[0,0.1,0.25,0.4,0.5],labels=["mid","lean","tilt","tail"])
g=q.groupby("lv",observed=True).agg(n=("both","size"),sp=("sp","mean"),both=("both","mean"),pnl=("pnl","mean"))
print(g.assign(sp=lambda d:(d.sp*100).round(2),pnl=lambda d:(d.pnl*100).round(3)).to_string())

print("\n[6] SEQUENTIAL COMPLETION economics (leg1 fills, leg2 at later minute touch):")
# for each window: first bid fill at minute k -> complete with ask quote at k+1.. (price a[k'])
hist=pd.read_parquet(f"hist_kalshi_{asset}15m.parquet").set_index("ws")
neg=pos=0; locked=[]
for w,d in q.groupby("ws"):
    d=d.sort_values("k")
    f=d[d.fb]
    if not len(f): continue
    k1=int(f.k.iloc[0]); b1=float(f.b.iloc[0])
    later=d[(d.k>k1)&d.fa]
    if not len(later): continue
    a2=float(later.a.iloc[0])
    lk=a2-b1
    locked.append(lk); neg+= lk<0; pos+= lk>=0
print(f"  sequential pairs: {len(locked)}; negative-lock completions: {neg} ({neg/max(len(locked),1)*100:.0f}%)")
locked=np.array(locked)
if len(locked):
    print(f"  avg lock all={locked.mean()*100:+.2f}c | if SKIP negatives: {locked[locked>=0].mean()*100:+.2f}c on {pos} pairs")
    print(f"  value of completion floor: skip-neg total {locked[locked>=0].sum()*100:+.0f}c vs take-all {locked.sum()*100:+.0f}c")
