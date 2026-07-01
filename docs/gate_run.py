#!/usr/bin/env python3
"""
Contraindication/indication-GATE assay-noise IV (instrument A): apply the noise-IV to a measured
GATE that drives a gestalt drug from prescriptions. Same design as portfolio_run.py but the
treatment comes from rx_class.csv (drug class) instead of inputevents repletions.
Runnable gates with labs+rx in hand (QTc gate needs chartevents -> deferred):
  - SUP/PPI indicated at coagulopathy: platelet<50k, INR>1.7
  - Steroid (COPD) eosinophil-guided: eos above threshold
Reports first stage, flag-ITT (mortality), implied-LATE (AR), balance, noise sigma.
"""
import csv, math
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
# (name, lab_key, drug_class, flag, direction, bandwidth)
CONFIG = [
    ('PPI @ platelet<50k', 'plt', 'ppi',     50.0, '<', 20.0),
    ('PPI @ INR>1.7',      'inr', 'ppi',     1.7,  '>', 0.4),
    ('Steroid @ eos gate', 'eos', 'steroid', 0.5,  '>', 0.4),
]

def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except Exception: return None

def load_labseq(key):
    d = {}
    try: f = open(SD+f'lab_{key}.csv')
    except FileNotFoundError: return d
    r = csv.reader(f); next(r, None)
    for row in r:
        if len(row) < 3: continue
        t = ep(row[1])
        if t is None or not row[2] or not row[0]: continue
        try: v = float(row[2])
        except ValueError: continue
        d.setdefault(row[0], []).append((t, v))
    f.close()
    for k in d: d[k].sort()
    return d

def load_rx_class(cls):
    d = {}
    try: f = open(SD+'rx_class.csv')
    except FileNotFoundError: return d
    r = csv.reader(f); next(r, None)
    for row in r:
        if len(row) < 3 or row[1] != cls: continue
        t = ep(row[2])
        if t is not None: d.setdefault(row[0], []).append(t)
    f.close()
    for k in d: d[k].sort()
    return d

def load_adm():
    d = {}
    with open(SD+'admissions.csv') as f:
        r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
        for row in r:
            d[row[ix['hadm_id']]] = {'subject': row[ix['subject_id']],
                'expire': int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0}
    return d

def load_age():
    d = {}
    with open(SD+'patients.csv') as f:
        r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
        for row in r:
            try: d[row[ix['subject_id']]] = float(row[ix['anchor_age']])
            except Exception: pass
    return d

def ols(y, X):
    X = np.asarray(X,float); y = np.asarray(y,float)
    Bi = np.linalg.pinv(X.T@X); b = Bi@(X.T@y); res = y - X@b
    n,k = X.shape; S = X*res[:,None]; cov = Bi@(S.T@S)@Bi*(n/max(n-k,1))
    return b, np.sqrt(np.diag(cov))

def cb(t, flag):
    c = np.asarray(t,float)-flag; return np.column_stack([np.ones_like(c), c, c*c])

def run(name, key, cls, flag, direction, hw, adm, age):
    seqs = load_labseq(key)
    if not seqs:
        print(f'  {name:22s}: lab_{key}.csv missing -> SKIP'); return
    tx = load_rx_class(cls)
    diffs = []
    for hadm, seq in seqs.items():
        for i in range(len(seq)-1):
            (t1,v1),(t2,v2) = seq[i], seq[i+1]
            if 0 < t2-t1 <= 12: diffs.append(v2-v1)
    sig = np.std(diffs)/math.sqrt(2) if len(diffs) > 100 else float('nan')
    cross = (lambda v: v < flag) if direction=='<' else (lambda v: v > flag)
    rows = []
    for hadm, seq in seqs.items():
        if hadm not in adm: continue
        rt = tx.get(hadm, []); first = rt[0] if rt else float('inf')
        pre = [(t,v) for (t,v) in seq if t < first]
        if len(pre) < 2: continue
        (t1,m1),(t2,m2) = pre[0], pre[1]
        ag = age.get(adm[hadm]['subject'], np.nan)
        if math.isnan(ag): continue
        rows.append({'mid':(m1+m2)/2, 'z':1.0 if cross(m2) else 0.0,
                     'd':1.0 if any(t2 <= r <= t2+48 for r in rt) else 0.0,
                     'y':float(adm[hadm]['expire']), 'age':ag})
    sub = [r for r in rows if abs(r['mid']-flag) <= hw]
    if len(sub) < 300:
        print(f'  {name:22s}: n={len(sub)} in-band (cohort {len(rows)}, too small)'); return
    z = np.array([r['z'] for r in sub]); d = np.array([r['d'] for r in sub])
    y = np.array([r['y'] for r in sub]); C = cb([r['mid'] for r in sub], flag)
    X = np.column_stack([z, C])
    bfs, sfs = ols(d, X); brf, srf = ols(y, X)
    fs, rf = bfs[0], brf[0]; F = (fs/sfs[0])**2 if sfs[0] > 0 else 0
    ba, _ = ols(np.array([r['age'] for r in sub]), X)
    late = rf/fs if abs(fs) > 1e-3 else float('nan')
    print(f'  {name:22s} n={len(sub):6d} rx={d.mean():.3f} sig={sig:.3g} | FS={fs:+.3f}(F{F:4.0f}) | '
          f'ITT={rf:+.5f}({srf[0]:.5f}) | LATE={late:+.3f} | balAge={ba[0]:+.2f}')

def main():
    print('=== Contraindication/indication-GATE assay-noise IV (instrument A) ===\n')
    adm = load_adm(); age = load_age()
    for c in CONFIG:
        run(c[0], c[1], c[2], c[3], c[4], c[5], adm, age)
    print('\nDONE (QTc-gate for antipsychotics deferred: QTc is in chartevents, not downloaded).')

if __name__ == '__main__':
    main()
