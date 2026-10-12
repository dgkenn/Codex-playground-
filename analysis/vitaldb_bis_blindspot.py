#!/usr/bin/env python3
"""IDEA #1 — THE BIS BLIND SPOT (decisive-first test).
Claim under test: the displayed BIS index reads misleadingly HIGH (i.e. "adequate/light") during EEG-confirmed
burst suppression when frontalis EMG power is present, because EMG is folded into BIS's proprietary composite.
Reference is NON-CIRCULAR: suppression is measured from the RAW EEG waveform (our detector, validated r=0.68/0.78
vs device SR), and compared against the DISPLAYED BIS INDEX (a different, proprietary output).
DECISIVE TEST: among deeply-suppressed bins, what fraction display BIS in the clinician's 'acceptable' range,
and does that fraction rise with EMG?  If BIS is uniformly low whenever raw suppression is high, the idea dies."""
import csv, numpy as np, math, statistics as st
# join raw-EEG BS (bridge_bins) with displayed BIS/EMG/device-SR (bis_bins) on (caseid,bin_t)
raw={}
for d in csv.DictReader(open('/tmp/eeg_probe/bridge_bins.csv')):
    try: raw[(d['caseid'],d['bin_t'])]=(float(d['bs']), float(d['ce']) if d['ce'] else np.nan,
                                        float(d['mbp']) if d['mbp'] else np.nan, float(d['age']) if d['age'] else np.nan)
    except: pass
R=[]
for d in csv.DictReader(open('/tmp/eeg_probe/bis_bins.csv')):
    k=(d['caseid'],d['bin_t'])
    if k not in raw: continue
    try: bis=float(d['bis'])
    except: continue
    emg=float(d['emg']) if d['emg'] else np.nan
    dsr=float(d['devsr']) if d['devsr'] else np.nan
    bs,ce,mbp,age=raw[k]
    R.append(dict(cid=d['caseid'],bs=bs,bis=bis,emg=emg,dsr=dsr,ce=ce,mbp=mbp,age=age))
print(f"joined bins: {len(R)} across {len(set(r['cid'] for r in R))} cases")
mt=[r for r in R if r['ce']==r['ce'] and r['ce']>=1.0]          # maintenance
print(f"maintenance bins (Ce>=1): {len(mt)}")
supp=[r for r in mt if r['bs']>=0.5]                             # EEG-confirmed DEEP suppression
print(f"EEG-confirmed deep suppression (raw BS>=50% of bin): {len(supp)} bins "
      f"({100*len(supp)/max(1,len(mt)):.1f}% of maintenance) in {len(set(r['cid'] for r in supp))} cases")
if not supp: raise SystemExit("no suppressed bins")
b=np.array([r['bis'] for r in supp])
print("\n== DECISIVE TABLE: displayed BIS during EEG-confirmed deep suppression ==")
print(f"   BIS median={np.median(b):.1f}  IQR=[{np.percentile(b,25):.1f},{np.percentile(b,75):.1f}]  max={b.max():.0f}")
for lo,hi,lab in [(0,20,'deep (correct alarm)'),(20,40,'low-ish'),(40,60,'*** clinician TARGET range ***'),(60,101,'*** reads LIGHT ***')]:
    n=int(((b>=lo)&(b<hi)).sum()); print(f"   BIS {lo:3d}-{hi:3d}: {n:6d} bins ({100*n/len(b):5.1f}%)   {lab}")
blind=int((b>=40).sum()); print(f"   >>> BLIND-SPOT RATE: {100*blind/len(b):.1f}% of truly-suppressed bins display BIS>=40 (looks acceptable/light)")
# EMG stratification — the mechanism
print("\n== MECHANISM: does EMG drive the blind spot? (suppressed bins only) ==")
se=[r for r in supp if r['emg']==r['emg']]
if se:
    e=np.array([r['emg'] for r in se]); t1,t2=np.percentile(e,[33,67])
    for lab,sel in [(f'EMG low  (<{t1:.0f})',lambda r:r['emg']<t1),
                    (f'EMG mid  ({t1:.0f}-{t2:.0f})',lambda r:t1<=r['emg']<t2),
                    (f'EMG high (>={t2:.0f})',lambda r:r['emg']>=t2)]:
        s=[r['bis'] for r in se if sel(r)]
        if s: print(f"   {lab:22s}: n={len(s):5d}  median BIS={np.median(s):5.1f}   BIS>=40 in {100*np.mean([x>=40 for x in s]):5.1f}%")
    # regression: BIS ~ BS + EMG (+interaction) among ALL maintenance bins
    M=[r for r in mt if r['emg']==r['emg']]
    X=np.array([[1,r['bs'],r['emg']] for r in M],float); y=np.array([r['bis'] for r in M],float)
    bb,_,_,_=np.linalg.lstsq(X,y,rcond=None)
    res=y-X@bb; se_=np.sqrt(np.diag((res@res/(len(y)-3))*np.linalg.inv(X.T@X)))
    print(f"\n   BIS ~ rawBS + EMG   (n={len(M)}):  rawBS {bb[1]:+.2f} [{bb[1]-1.96*se_[1]:+.2f},{bb[1]+1.96*se_[1]:+.2f}]   "
          f"EMG {bb[2]:+.3f} [{bb[2]-1.96*se_[2]:+.3f},{bb[2]+1.96*se_[2]:+.3f}] BIS-units per EMG-unit")
    print("   [mechanism supported if EMG coef POSITIVE: EMG pushes the displayed index UP at matched true suppression]")
# device SR comparison — is the device's OWN SR also blind? (does BIS ignore its own SR when EMG high?)
sd=[r for r in supp if r['dsr']==r['dsr']]
if sd:
    print(f"\n== device's own SR during these bins: median={np.median([r['dsr'] for r in sd]):.1f}%  "
          f"(fraction with devSR==0 despite raw suppression: {100*np.mean([r['dsr']==0 for r in sd]):.1f}%)")
print("DONE")
