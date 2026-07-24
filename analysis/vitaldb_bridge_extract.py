#!/usr/bin/env python3
"""Time-resolved extraction for Aim-2 (BS susceptibility) + Aim-3 (EEG over-sedation -> hypotension bridge).
Per case, in 30s bins over the whole case: burst-suppression burden, multitaper alpha/slow power, mean arterial
MBP, mean propofol Ce. Writes one row per (case,bin). Resumable (skips cases already present)."""
import csv, urllib.request, gzip, os, numpy as np
from scipy.signal import windows
BASE="https://api.vitaldb.net/"; fs=128.0; BIN=30.0
N=512; NW=3; K=5; THRESH=8.0
tapers=windows.dpss(N,NW,K); freqs=np.fft.rfftfreq(N,1/fs)
MA=(freqs>=8)&(freqs<12); MD=(freqs>=0.5)&(freqs<4)
def fetch(tid):
    for _ in range(2):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(BASE+tid,headers={'Accept-Encoding':'gzip'}),timeout=30).read()
            try: return gzip.decompress(raw).decode()
            except: return raw.decode()
        except Exception: pass
    return None
def eeg_arr(txt):
    v=np.empty(txt.count('\n'),dtype=np.float32); i=0
    for ln in txt.split('\n')[1:]:
        c=ln.find(',')
        if c<0: continue
        try: v[i]=float(ln[c+1:])
        except: v[i]=np.nan
        i+=1
    return v[:i]
def tv(txt):
    t=[];v=[]
    for ln in txt.split('\n')[1:]:
        if not ln: continue
        p=ln.split(',')
        try: t.append(float(p[0])); v.append(float(p[1]))
        except: pass
    return (np.array(t),np.array(v)) if t else (None,None)
def bin_mean(ts,vs,t0,t1):
    if ts is None: return np.nan
    m=(ts>=t0)&(ts<t1);
    return float(np.nanmean(vs[m])) if m.sum()>0 else np.nan
def eeg_bin(seg):
    """BS burden + alpha_db + slow_db for a 30s EEG segment."""
    seg=seg[~np.isnan(seg)]
    if len(seg)<fs*10: return np.nan,np.nan,np.nan
    # BS
    fr=int(0.1*fs); n=len(seg)//fr; sup=np.zeros(n,bool)
    for i in range(n):
        w=seg[i*fr:(i+1)*fr]
        if w.max()-w.min()<THRESH: sup[i]=True
    run=0
    for i in range(n):
        if sup[i]: run+=1
        else:
            if run<5: sup[max(0,i-run):i]=False
            run=0
    bs=float(sup.mean())
    # multitaper alpha/slow over 4s windows
    A=D=0.0; c=0
    for s in range(0,len(seg)-N,N):
        w=seg[s:s+N]
        if np.isnan(w).any(): continue
        w=w-w.mean(); S=np.zeros(len(freqs))
        for tp in tapers: S+=np.abs(np.fft.rfft(w*tp))**2
        S/=K; A+=np.trapezoid(S[MA],freqs[MA]); D+=np.trapezoid(S[MD],freqs[MD]); c+=1
    if c==0: return bs,np.nan,np.nan
    db=lambda x:10*np.log10(x/c+1e-9)
    return bs, db(A), db(D)
def run(manifest,out,limit=None):
    done=set()
    if os.path.exists(out):
        for r in csv.DictReader(open(out)): done.add(r['caseid'])
    rows=list(csv.DictReader(open(manifest)))
    nf=not os.path.exists(out); f=open(out,'a',newline=''); w=csv.writer(f)
    if nf: w.writerow(['caseid','age','sex','bmi','death','bin_t','bs','alpha_db','slow_db','mbp','ce']); f.flush()
    nc=0
    for r in rows:
        if r['caseid'] in done: continue
        if limit and nc>=limit: break
        try:
            et=fetch(r['eeg_tid'])
            if not et: continue
            v=eeg_arr(et)
            if len(v)<fs*300: continue
            dur=len(v)/fs
            at,av=tv(fetch(r['art_tid']) or ""); ct,cv=tv(fetch(r['ce_tid']) or "")
            nb=int(dur//BIN); wrote=0
            for b in range(nb):
                t0=b*BIN; t1=t0+BIN
                s0=int(t0*fs); s1=int(t1*fs)
                bs,adb,sdb=eeg_bin(v[s0:s1])
                if bs!=bs: continue
                mbp=bin_mean(at,av,t0,t1); ce=bin_mean(ct,cv,t0,t1)
                w.writerow([r['caseid'],r['age'],r['sex'],r['bmi'],r['death'],round(t0,0),
                            round(bs,4),round(adb,2) if adb==adb else '',round(sdb,2) if sdb==sdb else '',
                            round(mbp,1) if mbp==mbp else '',round(ce,3) if ce==ce else '']); wrote+=1
            f.flush(); nc+=1
            if nc%20==0: print(f"  {nc} cases ({r['caseid']}, {wrote} bins)",flush=True)
        except Exception as e:
            print("  ERR",r['caseid'],type(e).__name__,str(e)[:80],flush=True)
    f.close(); print(f"DONE {nc} cases -> {out}")
if __name__=='__main__':
    import sys
    run('manifest_bridge.csv','/tmp/eeg_probe/bridge_bins.csv',limit=int(sys.argv[1]) if len(sys.argv)>1 else None)
