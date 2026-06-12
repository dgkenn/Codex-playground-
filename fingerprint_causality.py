"""THE make-or-break test for the 'one-sided pull predicts direction' signal:
is it LEADING (early-window pull predicts LATER move = tradeable) or COINCIDENT (pull and move happen
together over the window = NOT tradeable, MM just reacting to a move already underway)?
Strict temporal separation: pull measured in minutes 0-7, spot move measured in minutes 8-15."""
import gzip,json,glob,numpy as np,pandas as pd
from collections import Counter
def iter_gz(fp):
    try:
        with gzip.open(fp,"rt") as fh:
            for ln in fh:
                try: yield json.loads(ln)
                except: continue
    except (EOFError,OSError): return
def modal_size(levels):
    s=[round(x) for _,x in levels if x>50]
    return Counter(s).most_common(1)[0][0] if s else 0
def mdepth(levels,m):
    return sum(x for _,x in levels if abs(round(x)-m)<=1)
books={}
for fp in glob.glob("/tmp/bk/gha_data/**/book_kalshi_btc15m_*.jsonl.gz",recursive=True)+glob.glob("overnight_data/book_kalshi_btc15m_*.jsonl.gz"):
    for r in iter_gz(fp):
        if r.get("type")!="book" or not r.get("yes"): continue
        books.setdefault(r["ws"],[]).append((r["t"],r["yes"],r.get("no") or [],r.get("spot")))
rows=[]
for ws,sn in books.items():
    if len(sn)<25: continue
    sn.sort(); t0=sn[0][0]
    m_y=modal_size(sn[0][1]); m_n=modal_size(sn[0][2])
    # EARLY (0-420s = min 0-7): net one-sided pull = (YES modal depth drop) - (NO modal depth drop)
    early=[(t-t0,mdepth(yb,m_y),mdepth(nb,m_n),sp) for t,yb,nb,sp in sn if t-t0<=420 and sp]
    late =[(t-t0,sp) for t,yb,nb,sp in sn if t-t0>420 and sp]
    if len(early)<5 or len(late)<5: continue
    ey=np.array([e[1] for e in early]); en=np.array([e[2] for e in early])
    yes_pull=(ey.max()-ey[-1])/max(ey.max(),1); no_pull=(en.max()-en[-1])/max(en.max(),1)
    net_pull=yes_pull-no_pull                       # >0 = YES pulled more (EARLY)
    s_early_end=early[-1][3]; s_late_end=late[-1][1]
    late_move=(s_late_end/s_early_end-1)*1e4 if s_early_end else 0   # LATER move only
    # coincident comparison: pull over whole window vs whole-window move
    rows.append((ws,net_pull,late_move,(sn[-1][3]/sn[0][3]-1)*1e4 if sn[0][3] else 0))
df=pd.DataFrame(rows,columns=["ws","net_pull","late_move","full_move"])
print(f"windows: {len(df)}")
from scipy import stats
cut=df.ws.quantile(0.6)
print("\nCOINCIDENT (whole-window pull vs whole-window move) -- the agent's test:")
r=stats.pearsonr(df.net_pull,df.full_move); print(f"  corr={r[0]:+.3f} t={r[0]*np.sqrt(len(df)-2)/np.sqrt(1-r[0]**2):+.1f} (n={len(df)})")
print("\nLEADING (EARLY pull min0-7 -> LATE move min8-15) -- the tradeable test:")
for tag,sub in [("IS",df[df.ws<cut]),("OOS",df[df.ws>=cut])]:
    if len(sub)<15: print(f"  {tag}: n={len(sub)} too small"); continue
    r=stats.pearsonr(sub.net_pull,sub.late_move); t=r[0]*np.sqrt(len(sub)-2)/np.sqrt(1-r[0]**2)
    print(f"  {tag}: corr(early_pull, LATE move)={r[0]:+.3f} t={t:+.1f} p={r[1]:.3f} (n={len(sub)})")
