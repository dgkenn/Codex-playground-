"""Book-diff fingerprint proxies + the decisive test: does early-window ladder-MM PULL / quote churn
predict the HARD (big-move, leg-stranding) windows? If yes => a LEADING prevention signal."""
import gzip, json, glob, os
import numpy as np, pandas as pd
from collections import Counter

def iter_gz(fp):
    try:
        with gzip.open(fp,"rt") as fh:
            for ln in fh:
                try: yield json.loads(ln)
                except: continue
    except (EOFError,OSError): return

# gather book snapshots per window
books={}
files=glob.glob("overnight_data/book_kalshi_btc15m_*.jsonl.gz")+glob.glob("gha_data/**/book_kalshi_btc15m_*.jsonl.gz",recursive=True)
for fp in files[:60]:
    for r in iter_gz(fp):
        if r.get("type")!="book": continue
        yb=r.get("yes") or []
        if not yb: continue
        books.setdefault(r["ws"],[]).append((r["t"], yb, r.get("no") or [], r.get("spot")))
print(f"windows with book data: {len(books)}")

rows=[]
for ws,snaps in books.items():
    if len(snaps)<20: continue
    snaps.sort()
    t0=snaps[0][0]
    # modal ladder size per snapshot (the single-MM fingerprint), and laddered depth
    def modal_depth(levels):
        sizes=[round(s) for _,s in levels if s>50]
        if not sizes: return 0,0
        c=Counter(sizes); modal,cnt=c.most_common(1)[0]
        return modal, modal*cnt   # modal size, total depth at that modal size
    ladder_dep=[]; churn=[]; prev=None
    for (t,yb,nb,spot) in snaps:
        _,dep=modal_depth(yb); ladder_dep.append((t-t0,dep))
        d=dict((round(p,4),s) for p,s in yb)
        if prev is not None:
            ch=sum(abs(d.get(k,0)-prev.get(k,0)) for k in set(d)|set(prev))
            churn.append((t-t0, ch))
        prev=d
    ld=np.array(ladder_dep); ch=np.array(churn) if churn else np.zeros((1,2))
    # EARLY window (first 5 min = 300s): ladder pull = max drop in modal depth; mean churn
    early=ld[ld[:,0]<=300]
    if len(early)<5: continue
    pull = (early[:,1].max()-early[:,1].min())/max(early[:,1].max(),1)   # frac drop in ladder depth
    early_churn = ch[ch[:,0]<=300][:,1].mean() if (ch[:,0]<=300).any() else 0
    # outcome: window hardness = |spot move open->close| (big move strands a leg)
    spots=[s for _,_,_,s in snaps if s]
    if len(spots)<5: continue
    move=abs(spots[-1]/spots[0]-1)*1e4   # bps
    rows.append((ws,pull,early_churn,move))

df=pd.DataFrame(rows,columns=["ws","pull","churn","move_bps"])
print(f"usable windows: {len(df)}")
print(f"\nLadder-pull proxy: median {df.pull.median():.2f}, p90 {df.pull.quantile(.9):.2f}")
print(f"Quote-churn proxy: median {df.churn.median():.0f}")
# DECISIVE: does early pull/churn predict a HARD window (big move)?
cut=df.ws.quantile(0.6)
for tag,sub in [("IS",df[df.ws<cut]),("OOS",df[df.ws>=cut])]:
    if len(sub)<20: continue
    hard=sub.move_bps>sub.move_bps.median()
    from scipy import stats
    # correlation pull vs move
    rp=stats.pearsonr(sub.pull,sub.move_bps); rc=stats.pearsonr(sub.churn,sub.move_bps)
    # high-pull windows: are they harder?
    hi=sub[sub.pull>sub.pull.quantile(.75)]; lo=sub[sub.pull<=sub.pull.quantile(.75)]
    print(f"\n{tag} (n={len(sub)}): corr(early_pull, move)={rp[0]:+.3f} p={rp[1]:.3f} | "
          f"corr(churn,move)={rc[0]:+.3f} p={rc[1]:.3f}")
    print(f"  high-pull windows move {hi.move_bps.mean():.0f}bps vs low-pull {lo.move_bps.mean():.0f}bps "
          f"(t={(hi.move_bps.mean()-lo.move_bps.mean())/np.sqrt(hi.move_bps.var()/len(hi)+lo.move_bps.var()/len(lo)):+.1f})")
