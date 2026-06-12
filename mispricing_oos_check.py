import numpy as np, pandas as pd
def arr(v): return np.asarray(v,float)
def wilson(k,n,z=1.96):
    if n==0: return (0,0,1)
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; hw=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return p,c-hw,c+hw
rows=[]
for a in ("btc","eth","sol","xrp"):
    try: h=pd.read_parquet(f"hist_kalshi_{a}15m.parquet")
    except: continue
    for _,r in h.iterrows():
        if r.res_up not in (0,1): continue
        bid=arr(r.bid_path); ask=arr(r.ask_path)
        for k in range(2,15):
            if k>=15 or np.isnan(bid[k]) or np.isnan(ask[k]): continue
            mid=(bid[k]+ask[k])/2
            rows.append((r.ws,k,mid,int(r.res_up)))
df=pd.DataFrame(rows,columns=["ws","k","mid","won"])
cut=df.ws.quantile(0.6)
def check(name,k,lo,hi):
    print(f"\n=== {name}: minute {k}, YES mid in [{lo},{hi}) ===")
    for tag,sub in [("IS",df[(df.ws<cut)]),("OOS",df[(df.ws>=cut)])]:
        q=sub[(sub.k==k)&(sub.mid>=lo)&(sub.mid<hi)]
        n=len(q); w=q.won.sum()
        if n<15: print(f"  {tag}: n={n} too small"); continue
        impl=q.mid.mean(); p,clo,chi=wilson(w,n)
        sig = "SIG" if (chi<impl or clo>impl) else "ns"
        print(f"  {tag}: n={n:4d} realized={p*100:5.1f}% implied={impl*100:5.1f}% "
              f"misprice={(p-impl)*100:+6.1f}% CI=[{clo*100:.1f},{chi*100:.1f}] {sig}")
check("Mid-range early (the -12.8c flag)",3,0.60,0.65)
check("Early favorite broad",3,0.58,0.70)
check("Longshot tail",9,0.06,0.08)
check("Longshot tail",11,0.06,0.08)
check("Longshot tail pooled k9-12",10,0.05,0.10)  # approx
# generalized early-extreme test: minute<=4, |mid-0.5|>0.10, does it revert?
print("\n=== GENERALIZED: early (k<=4) extreme prices -- do they revert toward 50%? ===")
for tag,sub in [("IS",df[df.ws<cut]),("OOS",df[df.ws>=cut])]:
    q=sub[(sub.k<=4)&(sub.mid>0.60)]   # YES priced as favorite early
    n=len(q); 
    if n<30: continue
    print(f"  {tag} (YES mid>0.60, k<=4): n={n} realized={q.won.mean()*100:.1f}% implied={q.mid.mean()*100:.1f}% misprice={(q.won.mean()-q.mid.mean())*100:+.1f}%")
    q2=sub[(sub.k<=4)&(sub.mid<0.40)]
    print(f"  {tag} (YES mid<0.40, k<=4): n={len(q2)} realized={q2.won.mean()*100:.1f}% implied={q2.mid.mean()*100:.1f}% misprice={(q2.won.mean()-q2.mid.mean())*100:+.1f}%")
