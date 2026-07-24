#!/usr/bin/env python3
"""Calibrate the raw-signal burst-suppression detector against HEEDB's OWN clinician labels.

Why this and not MORGOTH: HEEDB already contains 2,813 (S0001) + 1,828 (S0002) expert-read recordings labelled
`bs`, plus tens of thousands labelled not-bs. That is a larger, in-distribution, same-montage ground truth than
any external set — and it needs no extra DUA. (MORGOTH's BS/ set remains a nice external check later.)

Procedure:
  1. sample recordings labelled bs=1 and bs=0, MATCHED on recording service (LTM/Routine) so montage/context match
  2. byte-range read a fixed mid-recording window from each BIDS EDF (never downloads the ~1 GB file)
  3. compute suppression burden over a grid of amplitude thresholds, with flat/disconnected-segment rejection
  4. pick the threshold maximizing separation (AUC) between expert bs=1 and bs=0
Outputs a small CSV of per-recording burdens + the chosen operating point. De-identified aggregates only.
"""
import boto3, io, csv, sys, random
from botocore.config import Config
import numpy as np
from scipy.signal import butter, filtfilt
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from heedb_edf_range import read_edf_window, AP
S3 = boto3.client("s3", region_name="us-east-1", config=Config(s3={'payload_signing_enabled': False}))
FIND = {"S0001": "EEG/HEEDB_Metadata/S0001_EEG__reports_findings.csv"}
META = {"S0001": "EEG/eeg-metadata/S0001_eeg_metadata_2026_04_30.csv"}
TEN20 = ("FP1","FP2","F3","F4","C3","C4","P3","P4","O1","O2","F7","F8","T3","T4","T5","T6","FZ","CZ","PZ")
def get(key):
    return list(csv.DictReader(io.StringIO(S3.get_object(Bucket=AP, Key=key)["Body"].read().decode("utf-8","replace"))))
def hasv(v): return (v or "").strip() not in ("", "None", "nan")
_BP={}
def _bp(fs):
    if fs not in _BP: _BP[fs]=butter(4,[0.5/(fs/2), 40.0/(fs/2)],btype="band")
    return _BP[fs]
def prep(X, names, fs):
    """Bandpass 0.5-40 Hz and build a BIPOLAR longitudinal montage.
    Referential channels carry large DC/common-mode drift that swamps an amplitude criterion;
    clinical burst-suppression is read on bipolar chains."""
    idx={n.upper():i for i,n in enumerate(names)}
    pairs=[("FP1","F3"),("F3","C3"),("C3","P3"),("P3","O1"),
           ("FP2","F4"),("F4","C4"),("C4","P4"),("P4","O2")]
    b,a=_bp(fs); out=[]
    for u,v in pairs:
        if u in idx and v in idx:
            d=X[idx[u]]-X[idx[v]]
            if len(d)>30:
                try: out.append(filtfilt(b,a,d))
                except Exception: pass
    return out
def burden(x, fs, thresh, frame_s=0.1, min_run_s=0.5, flat_reject=True):
    """Suppression burden with flat-segment rejection.
    A frame is SUPPRESSED if low-amplitude but not identically constant (true amplifier-off / zero padding)."""
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < fs*20: return np.nan, np.nan
    fr = max(1, int(frame_s*fs)); n = len(x)//fr
    if n < 20: return np.nan, np.nan
    seg = x[:n*fr].reshape(n, fr)
    ptp = seg.max(axis=1) - seg.min(axis=1)
    dead = ptp < 1e-6                      # exactly flat -> amplifier off / padding, NOT physiology
    supp = (ptp < thresh) & (~dead)
    need = max(1, int(min_run_s/frame_s)); run = 0; out = supp.copy()
    for i in range(n):
        if supp[i]: run += 1
        else:
            if run < need: out[max(0,i-run):i] = False
            run = 0
    valid = ~dead
    if flat_reject and valid.sum() < 0.5*n: return np.nan, float(dead.mean())
    denom = valid.sum() if flat_reject else n
    return float(out.sum()/max(1, denom)), float(dead.mean())
def bids_key(site, bidsfolder, session, eegfolder):
    task = "cEEG" if (eegfolder or "").lower().startswith("ceeg") else "EEG"
    return f"EEG/bids/{site}/{bidsfolder}/ses-{session}/eeg/{bidsfolder}_ses-{session}_task-{task}_eeg.edf"
def main(site="S0001", n_per=40, window_s=120, seed=0):
    random.seed(seed)
    f = get(FIND[site]); m = get(META[site])
    # metadata index: (BidsFolder, SessionID) -> row  (BDSPPatientID is blank in metadata; folder carries it)
    meta_by = {}
    for r in m:
        bf = (r.get("BidsFolder") or "").strip()
        if not bf: continue
        meta_by[(bf, (r.get("SessionID") or "").strip())] = r
    # findings give the expert label; patient id -> bids folder is sub-<SITE><PID>
    pool = {1: [], 0: []}
    for r in f:
        pid = (r.get("BDSPPatientID") or "").strip()
        sess = (r.get("SessionID") or "").strip()
        if not pid or not sess: continue
        bf = f"sub-{site}{pid}"
        mr = meta_by.get((bf, sess))
        if not mr: continue
        svc = (r.get("ServiceName(EEG)") or "").strip()
        if svc not in ("LTM", "Routine"): continue
        lab = 1 if hasv(r.get("bs")) else 0
        pool[lab].append((bf, sess, svc, mr.get("EEGFolder",""), mr.get("DurationInSeconds","")))
    print(f"[{site}] matched findings<->metadata: bs=1 {len(pool[1])}, bs=0 {len(pool[0])}")
    if min(len(pool[1]), len(pool[0])) == 0:
        print("  join failed — check BidsFolder/SessionID construction"); return
    # match on service composition of the bs=1 sample
    random.shuffle(pool[1]); random.shuffle(pool[0])
    sel1 = pool[1][:n_per]
    want_svc = {}
    for _,_,svc,_,_ in sel1: want_svc[svc] = want_svc.get(svc,0)+1
    sel0 = []
    for svc, k in want_svc.items():
        sel0 += [x for x in pool[0] if x[2]==svc][:k]
    print(f"  sampling {len(sel1)} bs=1 and {len(sel0)} bs=0 (service-matched: {want_svc})")
    THRESH = [3,5,8,12,18,25,35]
    rows=[]
    for lab, sel in ((1, sel1), (0, sel0)):
        for bf, sess, svc, eegf, dur in sel:
            key = bids_key(site, bf, sess, eegf)
            try:
                # expert label applies to the WHOLE recording; BS is often intermittent ->
                # scan several windows and take the MAX burden (presence, not average)
                vals={t: [] for t in THRESH}; deads=[]
                for frac in (0.15, 0.35, 0.55, 0.75):
                    try:
                        X, fs, names, meta = read_edf_window(key, max_seconds=window_s, s3=S3, start_frac=frac)
                    except Exception:
                        continue
                    chans=prep(X, names, fs)
                    if not chans: continue
                    for t in THRESH:
                        b=[burden(c, fs, t)[0] for c in chans]
                        b=[v for v in b if v==v]
                        if b: vals[t].append(float(np.median(b)))
                    deads.append(float(np.median([burden(c,fs,20)[1] for c in chans])))
                if not any(vals[t] for t in THRESH): continue
                vals={t: (max(v) if v else np.nan) for t,v in vals.items()}
                dead=float(np.median(deads)) if deads else np.nan
                rows.append(dict(label=lab, svc=svc, dead=dead, **{f"t{t}":vals[t] for t in THRESH}))
            except Exception as e:
                rows.append(dict(label=lab, svc=svc, dead=np.nan, **{f"t{t}":np.nan for t in THRESH}))
        print(f"  ...label={lab} done ({len([r for r in rows if r['label']==lab])})")
    out="/tmp/eeg_probe/heedb_bs_calib.csv"
    with open(out,"w",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"\nwrote {out} ({len(rows)} recordings)")
    print("\n=== threshold calibration (median burden by expert label; AUC) ===")
    def auc(pos,neg):
        pos=[p for p in pos if p==p]; neg=[n for n in neg if n==n]
        if not pos or not neg: return float("nan")
        c=sum((1 if p>n else 0.5 if p==n else 0) for p in pos for n in neg)
        return c/(len(pos)*len(neg))
    best=(None,-1)
    for t in THRESH:
        p=[r[f"t{t}"] for r in rows if r["label"]==1]; n=[r[f"t{t}"] for r in rows if r["label"]==0]
        a=auc(p,n)
        pm=np.nanmedian(p) if any(x==x for x in p) else float("nan")
        nm=np.nanmedian(n) if any(x==x for x in n) else float("nan")
        print(f"  thresh {t:3d} uV: bs=1 median={pm:.3f}  bs=0 median={nm:.3f}   AUC={a:.3f}")
        if a==a and a>best[1]: best=(t,a)
    print(f"\n  --> best operating threshold: {best[0]} uV (AUC {best[1]:.3f})")
    print(f"  flat/dead-segment fraction: median {np.nanmedian([r['dead'] for r in rows]):.3f}")
if __name__=="__main__":
    main(n_per=int(sys.argv[1]) if len(sys.argv)>1 else 40)
