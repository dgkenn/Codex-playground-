#!/usr/bin/env python3
"""MECHANISM from the RAW 500 Hz ARTERIAL WAVEFORM — vasodilation vs reduced stroke volume.

Why this supersedes the earlier attempt: the EV1000/Vigileo SVR used before is a derived, noisy quantity
available in only ~215 cases. The raw arterial waveform (SNUADC/ART, 500 Hz) exists in 1,831 propofol and
2,106 sevoflurane cases and permits a first-principles decomposition.

Physiology:  MAP = CO x SVR,  CO = SV x HR.  Pulse pressure (PP) tracks stroke volume.
  * MAP falls with PP PRESERVED/RISING and HR steady  -> SVR fell        => VASODILATION
  * MAP falls with PP FALLING                          -> SV fell        => cardiac / preload
Per 30 s bin we derive beat-wise: MAP, systolic, diastolic, PP, HR, and dP/dt_max (contractility proxy).
Then we ask what happens to each at +30..+120 s AFTER burst suppression, adjusting for the current value.
Streams each waveform and discards it (never stored).
"""
import csv, urllib.request, gzip, os, sys, numpy as np
from concurrent.futures import ThreadPoolExecutor
BASE="https://api.vitaldb.net/"; BIN=30.0; FS=500.0
def fetch(tid):
    if not tid: return None
    for _ in range(2):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(BASE+tid,headers={'Accept-Encoding':'gzip'}),timeout=90).read()
            try: return gzip.decompress(raw).decode()
            except Exception: return raw.decode()
        except Exception: pass
    return None
def wave(txt):
    """parse a uniformly sampled waveform track -> (t0, values)"""
    if not txt: return None,None
    v=np.empty(txt.count('\n'),dtype=np.float32); i=0; t0=None
    for ln in txt.split('\n')[1:]:
        c=ln.find(',')
        if c<0: continue
        if t0 is None:
            try: t0=float(ln[:c])
            except Exception: t0=0.0
        try: v[i]=float(ln[c+1:])
        except Exception: v[i]=np.nan
        i+=1
    return (t0 or 0.0), v[:i]
def tv(txt):
    t=[];v=[]
    if not txt: return None,None
    for ln in txt.split('\n')[1:]:
        if not ln: continue
        p=ln.split(',')
        try: t.append(float(p[0])); v.append(float(p[1]))
        except Exception: pass
    return (np.array(t),np.array(v)) if t else (None,None)
def beats(seg, fs=FS):
    """beat-wise features from an arterial pressure segment."""
    s=seg[np.isfinite(seg)]
    if len(s)<fs*5: return None
    if np.nanmedian(s)<20 or np.nanmedian(s)>200: return None      # not a plausible arterial line
    d=np.diff(s)
    # systolic upstrokes: large positive derivative, refractory 0.25 s
    thr=np.percentile(d,99)*0.4
    idx=np.where(d>thr)[0]
    if len(idx)<3: return None
    peaks=[]; last=-10**9
    for i in idx:
        if i-last > int(0.25*fs):
            j=min(len(s)-1, i+int(0.15*fs))
            peaks.append((i, int(np.argmax(s[i:j+1]))+i)); last=i
    if len(peaks)<3: return None
    sys_=[]; dia=[]; dpdt=[]
    for k in range(len(peaks)-1):
        a=peaks[k][1]; b=peaks[k+1][0]
        if b<=a: continue
        sys_.append(float(s[a])); dia.append(float(np.min(s[a:b+1])))
        w=d[peaks[k][0]:a+1]
        if len(w): dpdt.append(float(np.max(w))*fs)
    if len(sys_)<2: return None
    sys_=np.array(sys_); dia=np.array(dia)
    hr=60.0*len(sys_)/(len(s)/fs)
    return dict(sbp=float(np.median(sys_)), dbp=float(np.median(dia)),
                pp=float(np.median(sys_-dia)), map=float(np.median(dia+(sys_-dia)/3.0)),
                hr=hr, dpdt=float(np.median(dpdt)) if dpdt else np.nan)
def run(manifest, out, limit, drug_is_ce=True):
    rows=list(csv.DictReader(open(manifest)))[:limit]
    done=set()
    if os.path.exists(out):
        for r in csv.DictReader(open(out)): done.add(r['caseid'])
    nf=not os.path.exists(out); f=open(out,'a',newline=''); w=csv.writer(f)
    if nf: w.writerow(['caseid','bin_t','map','sbp','dbp','pp','hr','dpdt','drug','age']); f.flush()
    def work(r):
        if r['caseid'] in done: return None
        aw=fetch(r['artwav'])
        if not aw: return None
        t0,av=wave(aw)
        if av is None or len(av)<FS*300: return None
        dt_,dv=tv(fetch(r['drug']))
        out_rows=[]
        nb=int((len(av)/FS)//BIN)
        for b in range(nb):
            s0=int(b*BIN*FS); s1=int((b+1)*BIN*FS)
            bt=t0+b*BIN
            ft=beats(av[s0:s1])
            if not ft: continue
            dg=np.nan
            if dt_ is not None:
                m=(dt_>=bt)&(dt_<bt+BIN)
                if m.sum()>0: dg=float(np.nanmean(dv[m]))
            out_rows.append([r['caseid'],round(bt),round(ft['map'],1),round(ft['sbp'],1),round(ft['dbp'],1),
                             round(ft['pp'],1),round(ft['hr'],1),
                             round(ft['dpdt'],1) if ft['dpdt']==ft['dpdt'] else '',
                             round(dg,3) if dg==dg else '', r['age']])
        return out_rows
    n=0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for res in ex.map(work, rows):
            if not res: continue
            for line in res: w.writerow(line)
            f.flush(); n+=1
            if n%25==0: print(f"  {n}",flush=True)
    f.close(); print(f"DONE {n} cases -> {out}")
if __name__=="__main__":
    which=sys.argv[1] if len(sys.argv)>1 else "prop"
    lim=int(sys.argv[2]) if len(sys.argv)>2 else 250
    if which=="prop": run("manifest_wav_prop.csv","/tmp/eeg_probe/wav_prop.csv",lim,True)
    else: run("manifest_wav_sevo.csv","/tmp/eeg_probe/wav_sevo.csv",lim,False)
