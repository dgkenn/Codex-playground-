#!/usr/bin/env python3
"""I-CARE Stage 2 — measure burst-suppression burden in post-cardiac-arrest coma, at a standard
neuroprognostic timepoint, with the SAME detector validated at ~90% vs sample-level expert labels.

Key correctness points:
  * WFDB gains differ per channel (17.98 .. 698.3) -> physical uV = (raw - baseline)/gain. Skipping this
    makes any amplitude threshold meaningless.
  * Same preprocessing as the validated detector: 0.5-40 Hz bandpass + bipolar longitudinal montage.
  * Segment chosen nearest a target hour post-arrest so every patient is compared at a like timepoint.
Streams each ~57 MB file and discards it (no disk accumulation).
"""
import boto3, io, re, sys, csv, os
from concurrent.futures import ThreadPoolExecutor
from botocore.config import Config
import numpy as np, scipy.io as sio
from scipy.signal import butter, filtfilt
AP="arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-restricted-access-point"
ROOT="ICARE_train/training/"
def s3c():
    return boto3.Session(profile_name="physionet").client("s3",region_name="us-east-1",
        config=Config(s3={'payload_signing_enabled':False},max_pool_connections=32,retries={'max_attempts':3}))
_BP={}
def bp(fs):
    if fs not in _BP: _BP[fs]=butter(4,[0.5/(fs/2),40.0/(fs/2)],btype="band")
    return _BP[fs]
PAIRS=[("FP1","F3"),("F3","C3"),("C3","P3"),("P3","O1"),("FP2","F4"),("F4","C4"),("C4","P4"),("P4","O2")]
def burden(x, fs, thresh=8.0, frame_s=0.1, min_run_s=0.5):
    x=x[np.isfinite(x)]
    if len(x)<fs*20: return np.nan
    fr=max(1,int(frame_s*fs)); n=len(x)//fr
    seg=x[:n*fr].reshape(n,fr); ptp=seg.max(1)-seg.min(1)
    dead=ptp<1e-9
    supp=(ptp<thresh)&(~dead)
    need=max(1,int(min_run_s/frame_s)); run=0; out=supp.copy()
    for i in range(n):
        if supp[i]: run+=1
        else:
            if run<need: out[max(0,i-run):i]=False
            run=0
    valid=(~dead).sum()
    if valid < 0.5*n: return np.nan
    return float(out.sum()/max(1,valid))
def parse_hea(txt):
    lines=[l for l in txt.splitlines() if l.strip()]
    first=lines[0].split()
    nsig=int(first[1]); fs=float(first[2])
    gains=[];bases=[];names=[]
    for l in lines[1:1+nsig]:
        p=l.split()
        m=re.match(r"([-\d.eE+]+)\(?(-?\d+)?\)?", p[2])
        g=float(m.group(1)); b=float(m.group(2) or 0)
        gains.append(g if g!=0 else 1.0); bases.append(b); names.append(p[-1])
    return fs,gains,bases,names
def one_patient(pid, target_hour=24, thresh=8.0, s3=None):
    s3=s3 or s3c()
    try:
        r=s3.list_objects_v2(Bucket=AP,Prefix=f"{ROOT}{pid}/",MaxKeys=1000)
        eeg=[o["Key"] for o in r.get("Contents",[]) if o["Key"].endswith("_EEG.mat")]
        if not eeg: return None
        def hr(k):
            m=re.match(r"^\d+_\d+_(\d+)_EEG\.mat$",k.split('/')[-1])
            return int(m.group(1)) if m else 10**6
        eeg.sort(key=lambda k: abs(hr(k)-target_hour))
        key=eeg[0]; hour=hr(key)
        hea=s3.get_object(Bucket=AP,Key=key[:-4]+".hea")["Body"].read().decode("utf-8","replace")
        fs,gains,bases,names=parse_hea(hea)
        val=sio.loadmat(io.BytesIO(s3.get_object(Bucket=AP,Key=key)["Body"].read()))["val"]
        idx={n.upper():i for i,n in enumerate(names)}
        b,a=bp(fs); vals=[]
        for u,v in PAIRS:
            if u in idx and v in idx:
                iu,iv=idx[u],idx[v]
                su=(val[iu].astype(np.float64)-bases[iu])/gains[iu]
                sv=(val[iv].astype(np.float64)-bases[iv])/gains[iv]
                d=su-sv
                if len(d)>100:
                    try: vals.append(burden(filtfilt(b,a,d),fs,thresh))
                    except Exception: pass
        vals=[v for v in vals if v==v]
        if not vals: return None
        return dict(pid=pid, hour=hour, n_seg=len(eeg), bs=float(np.median(vals)),
                    bs_max=float(np.max(vals)), fs=fs)
    except Exception as e:
        return dict(pid=pid, hour=np.nan, n_seg=0, bs=np.nan, bs_max=np.nan, fs=np.nan, err=type(e).__name__)
def main(limit=None, target_hour=24, workers=8):
    coh=list(csv.DictReader(open("/tmp/eeg_probe/icare_cohort.csv")))
    # Per-hour output, so serial measurements can be built for the same patients. The original run
    # hardcoded a single file at hour 24; measuring the SAME cohort at several hours is what turns this
    # into an external test of whether burden behaves as a fixed quantity (the Q2 claim) rather than only
    # of the outcome association.
    out_path=os.environ.get("ICARE_OUT", "/tmp/eeg_probe/icare_bs.csv")
    done=set()
    if os.path.exists(out_path):
        done={r["pid"] for r in csv.DictReader(open(out_path))}
    todo=[c["pid"] for c in coh if c["pid"] not in done]
    if limit: todo=todo[:limit]
    print(f"measuring {len(todo)} patients at ~hour {target_hour} ({len(done)} already done)")
    nf=not os.path.exists(out_path)
    f=open(out_path,"a",newline="")
    w=csv.writer(f)
    if nf: w.writerow(["pid","hour","n_seg","bs","bs_max","fs"]); f.flush()
    s3=s3c(); n=0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(lambda p: one_patient(p,target_hour,8.0,s3), todo):
            if not res: continue
            w.writerow([res["pid"],res["hour"],res["n_seg"],
                        f"{res['bs']:.4f}" if res["bs"]==res["bs"] else "",
                        f"{res['bs_max']:.4f}" if res["bs_max"]==res["bs_max"] else "", res["fs"]])
            n+=1
            if n%25==0: f.flush(); print(f"  {n}/{len(todo)}",flush=True)
    f.close(); print(f"DONE {n} -> {out_path}")
if __name__=="__main__":
    main(limit=int(sys.argv[1]) if len(sys.argv) > 1 else None,
         target_hour=float(os.environ.get("ICARE_HOUR", "24")))
