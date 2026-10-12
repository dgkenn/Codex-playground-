import csv, urllib.request, gzip, numpy as np
from collections import defaultdict
sr_tid={}
with open('trks.csv') as f:
    r=csv.reader(f); next(r)
    for cid,tn,tid in r:
        if tn=='BIS/SR': sr_tid[cid]=tid
bs=defaultdict(list)
for d in csv.DictReader(open('/tmp/eeg_probe/bridge_bins.csv')):
    try:
        if float(d['ce'])>=1.0: bs[d['caseid']].append(float(d['bs']))
    except: pass
cases=[c for c in bs if c in sr_tid][:200]
def fetch(tid):
    try:
        raw=urllib.request.urlopen(urllib.request.Request("https://api.vitaldb.net/"+tid,headers={'Accept-Encoding':'gzip'}),timeout=25).read()
        try: return gzip.decompress(raw).decode()
        except: return raw.decode()
    except: return None
pairs=[]
for c in cases:
    t=fetch(sr_tid[c])
    if not t: continue
    srv=[]
    for ln in t.split('\n')[1:]:
        p=ln.split(',')
        try: srv.append(float(p[1]))
        except: pass
    if not srv: continue
    pairs.append((np.mean(bs[c])*100, np.nanmean(srv)))
x=np.array([a for a,_ in pairs]); y=np.array([b for _,b in pairs])
print(f"CONCURRENT VALIDITY (n={len(pairs)}): corr(raw-EEG BS%, device SR%) = {np.corrcoef(x,y)[0,1]:.3f}")
print(f"  spearman-ish rank corr = {np.corrcoef(np.argsort(np.argsort(x)),np.argsort(np.argsort(y)))[0,1]:.3f}")
open('/tmp/eeg_probe/sr_validity.txt','w').write(f"n={len(pairs)} pearson={np.corrcoef(x,y)[0,1]:.3f}\n")
