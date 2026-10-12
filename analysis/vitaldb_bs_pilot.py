#!/usr/bin/env python3
"""VitalDB validation-arm pilot: detect burst suppression from RAW EEG (not BIS/SR), relate to propofol effect-site
conc (Ce) and in-hospital mortality. Establishes the 'drug-induced BS' reference for the HEEDB discovery study.
BS detection: 0.1s frames suppressed if peak-to-peak < THRESH uV; runs >=0.5s = suppression; BS_burden = fraction."""
import csv, urllib.request, numpy as np, io, time
BASE="https://api.vitaldb.net/"
THRESH=8.0; fs=128.0
def fetch(tid):
    for _ in range(3):
        try:
            req=urllib.request.Request(BASE+tid,headers={'Accept-Encoding':'gzip'})
            raw=urllib.request.urlopen(req,timeout=60).read()
            import gzip
            try: txt=gzip.decompress(raw).decode()
            except: txt=raw.decode()
            return txt
        except Exception as e:
            time.sleep(2)
    return None
def parse_eeg(txt):
    v=[]
    for line in txt.split('\n')[1:]:
        if not line: continue
        p=line.split(',')
        try: v.append(float(p[1]))
        except: v.append(np.nan)
    return np.array(v)
def parse_ce(txt):
    vals=[]
    for line in txt.split('\n')[1:]:
        if not line: continue
        p=line.split(',')
        try: vals.append(float(p[1]))
        except: pass
    return np.array(vals) if vals else None
def bs_burden(v):
    v=v[~np.isnan(v)]
    if len(v)<fs*60: return None,None
    fr=int(0.1*fs); n=len(v)//fr
    supp=np.zeros(n,bool)
    for i in range(n):
        seg=v[i*fr:(i+1)*fr]
        if seg.max()-seg.min()<THRESH: supp[i]=True
    # require runs >=0.5s (5 frames)
    out=supp.copy(); run=0
    for i in range(n):
        if supp[i]: run+=1
        else:
            if run<5:
                out[max(0,i-run):i]=False
            run=0
    burden=out.mean()
    # BSP proxy: also suppression in the middle 60% (maintenance)
    lo,hi=int(0.2*n),int(0.8*n)
    return burden, out[lo:hi].mean() if hi>lo else burden
rows=list(csv.DictReader(open('pilot_manifest.csv')))
out=open('pilot_bs.csv','w',newline=''); w=csv.writer(out)
w.writerow(['caseid','age','sex','death','peak_ce','bs_burden','bs_maint']); out.flush()
done=0
for r in rows:
    eeg=fetch(r['eeg_tid']);
    if not eeg: continue
    v=parse_eeg(eeg)
    burden,maint=bs_burden(v)
    if burden is None: continue
    cetxt=fetch(r['ce_tid']); ce=parse_ce(cetxt) if cetxt else None
    peak_ce=float(np.nanmax(ce)) if ce is not None and len(ce) else ''
    w.writerow([r['caseid'],r['age'],r['sex'],r['death'],peak_ce,round(burden,4),round(maint,4)]); out.flush()
    done+=1
    if done%5==0: print(f"  {done} cases done",flush=True)
out.close()
print(f"DONE pilot: {done} cases -> pilot_bs.csv")
# quick summary
import statistics as st
R=[r for r in csv.DictReader(open('pilot_bs.csv'))]
bs=[float(r['bs_maint']) for r in R if r['bs_maint']]
print(f"BS maintenance burden: median={st.median(bs):.3f} p90={sorted(bs)[int(.9*len(bs))]:.3f} ; %cases with >1% BS: {100*np.mean([b>0.01 for b in bs]):.0f}%")
ce=[(float(r['peak_ce']),float(r['bs_maint'])) for r in R if r['peak_ce'] and r['bs_maint']]
if len(ce)>5:
    import numpy as np
    x=np.array([a for a,_ in ce]); y=np.array([b for _,b in ce])
    print(f"corr(peak_Ce, BS_burden) = {np.corrcoef(x,y)[0,1]:.2f} (dose->suppression, n={len(ce)})")
