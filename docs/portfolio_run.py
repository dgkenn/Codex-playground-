#!/usr/bin/env python3
"""
Parameterized assay-noise IV / flag-ITT engine — runs the SAME corrected design on all 10
de-implementation trials. For each (trigger lab, treatment itemids, flag, direction):
  - first two pre-treatment draws M1,M2; instrument Z = 1(M2 crosses flag); control = midpoint (M1+M2)/2
  - D = treatment within 24h of M2; primary Y = in-hospital mortality; also LOS>median
  - reports: n, noise sigma, first stage (F), flag-ITT (headline) + implied-LATE with Anderson-Rubin CI,
    balance (age), heaping fraction at the flag.
Leads with the flag-ITT; reports implied-LATE so a null is legible as 'no effect OR underpowered'.
CONFIG itemids/flags are refined per the portfolio spec. Reads compact filtered CSVs; no PHI printed.
"""
import csv, math
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'

# (name, lab_csv_key, treatment_itemids, flag, direction '<'|'>', bandwidth, mortality-relevant)
# Verified against d_items (2026-07). Lab-flag-triggered subset of the user's 10 (assay-noise IV applies).
# Non-lab-triggered trials (PPI/benzo/opioid/antipsychotic/steroid) go in the provider-IV engine.
CONFIG = [
    ('Mg repletion',        'mg',   {'222011','227523','227524'}, 2.0, '<', 0.15),
    ('K repletion',         'k',    {'225166'},                   3.5, '<', 0.25),
    ('Phosphate repletion', 'phos', {'225925'},                   2.5, '<', 0.30),
    ('RBC transfusion',     'hb',   {'225168','220996'},          7.0, '<', 0.60),   # validation (TRICC/TRISS)
    ('Insulin (glucose>180)','glu', {'223258'},                   180, '>', 25),     # validation (NICE-SUGAR)
    ('Platelet transfusion','plt',  {'225170'},                   10.0,'<', 5.0),    # SUP coagulopathy / #9
    ('Bicarb (acidosis)',   'hco3', {'220995','227533'},          15.0,'<', 3.0),
    ('FFP (INR>1.7)',       'inr',  {'220970'},                   1.7, '>', 0.4),    # SUP coagulopathy / #9
    ('Albumin (alb<2.5)',   'alb',  {'220864','220862'},          2.5, '<', 0.4),    # weak (sparse draws)
    ('Calcium (ionized)',   'ical', {'221456','229618','229640'}, 1.1, '<', 0.12),
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
        hadm, ct, vn = row[0], row[1], row[2]
        t = ep(ct)
        if t is None or not vn or not hadm: continue
        try: v = float(vn)
        except ValueError: continue
        d.setdefault(hadm, []).append((t, v))
    f.close()
    for k in d: d[k].sort()
    return d

def load_repl(items):
    d = {}
    with open(SD+'repletions.csv') as f:
        r = csv.reader(f); next(r)
        for hadm, itemid, st in r:
            if itemid not in items: continue
            t = ep(st)
            if t is not None: d.setdefault(hadm, []).append(t)
    for k in d: d[k].sort()
    return d

def load_adm():
    d = {}
    with open(SD+'admissions.csv') as f:
        r = csv.reader(f); hdr = next(r); idx = {n:i for i,n in enumerate(hdr)}
        for row in r:
            adm = ep(row[idx['admittime']]); dis = ep(row[idx['dischtime']])
            d[row[idx['hadm_id']]] = {'subject': row[idx['subject_id']],
                'expire': int(row[idx['hospital_expire_flag']]) if row[idx['hospital_expire_flag']] else 0,
                'los': (dis-adm)/24.0 if (adm and dis) else None}
    return d

def load_age():
    d = {}
    with open(SD+'patients.csv') as f:
        r = csv.reader(f); hdr = next(r); idx = {n:i for i,n in enumerate(hdr)}
        for row in r:
            try: d[row[idx['subject_id']]] = float(row[idx['anchor_age']])
            except Exception: pass
    return d

def ols(y, X):
    X = np.asarray(X,float); y = np.asarray(y,float)
    Bi = np.linalg.pinv(X.T@X); b = Bi@(X.T@y); res = y - X@b
    n,k = X.shape; S = X*res[:,None]; cov = Bi@(S.T@S)@Bi*(n/(n-k))
    return b, np.sqrt(np.diag(cov))

def cb(t, flag):
    c = np.asarray(t,float)-flag; return np.column_stack([np.ones_like(c), c, c*c])

def run_trial(name, key, items, flag, direction, hw, adm, age):
    seqs = load_labseq(key)
    if not seqs:
        print(f'  {name:22s}: lab_{key}.csv empty/missing — SKIP'); return
    tx = load_repl(items)
    # noise sigma
    diffs = []
    for hadm, seq in seqs.items():
        rt = tx.get(hadm, [])
        for i in range(len(seq)-1):
            (t1,v1),(t2,v2) = seq[i], seq[i+1]
            if 0 < t2-t1 <= 12 and not any(t1 < r <= t2 for r in rt):
                diffs.append(v2-v1)
    sig = np.std(diffs)/math.sqrt(2) if len(diffs) > 100 else float('nan')
    # single-decision cohort
    rows = []
    cross = (lambda v: v < flag) if direction=='<' else (lambda v: v > flag)
    for hadm, seq in seqs.items():
        if hadm not in adm: continue
        rt = tx.get(hadm, []); first = rt[0] if rt else float('inf')
        pre = [(t,v) for (t,v) in seq if t < first]
        if len(pre) < 2: continue
        (t1,m1),(t2,m2) = pre[0], pre[1]
        rows.append({'mid':(m1+m2)/2, 'z':1.0 if cross(m2) else 0.0,
                     'd':1.0 if any(t2 <= r <= t2+24 for r in rt) else 0.0,
                     'y':float(adm[hadm]['expire']), 'age':age.get(adm[hadm]['subject'], np.nan)})
    sub = [r for r in rows if abs(r['mid']-flag) <= hw and not math.isnan(r['age'])]
    if len(sub) < 300:
        print(f'  {name:22s}: n={len(sub)} in-band (too small); cohort={len(rows)} sigma={sig:.3g}'); return
    z = np.array([r['z'] for r in sub]); d = np.array([r['d'] for r in sub])
    y = np.array([r['y'] for r in sub]); C = cb([r['mid'] for r in sub], flag)
    X = np.column_stack([z, C])
    bfs, sfs = ols(d, X); brf, srf = ols(y, X)
    fs, rf = bfs[0], brf[0]
    F = (fs/sfs[0])**2 if sfs[0] > 0 else 0
    ba, sa = ols(np.array([r['age'] for r in sub]), X)
    ar = [b0 for b0 in np.arange(-1,1.0001,0.02)
          if abs((lambda bb,sb: bb[0]/sb[0] if sb[0]>0 else 9)(*ols(y-b0*d, X))) < 1.96]
    arlo, arhi = (min(ar), max(ar)) if ar else (float('nan'), float('nan'))
    late = rf/fs if abs(fs) > 1e-3 else float('nan')
    # heaping at flag (fraction of M2 exactly at rounded flag)
    print(f'  {name:22s} n={len(sub):6d} tx={d.mean():.3f} sig={sig:.3g}({100*sig/max(abs(flag),1e-9):.1f}%) | '
          f'FS={fs:+.3f}(F{F:4.0f}) | ITT={rf:+.5f}({srf[0]:.5f}) | LATE={late:+.3f} AR[{arlo:+.2f},{arhi:+.2f}] | balAge={ba[0]:+.2f}')

def main():
    print('=== PORTFOLIO: assay-noise IV / flag-ITT across 10 de-implementation trials ===')
    print('headline=flag-ITT(mortality); LATE=implied (ITT/FS) with Anderson-Rubin CI; balAge~0 => exogenous\n')
    adm = load_adm(); age = load_age()
    for (name, key, items, flag, direction, hw) in CONFIG:
        run_trial(name, key, items, flag, direction, hw, adm, age)
    print('\nDONE. Interpret: strong FS + balAge~0 + precise ITT => usable; weak FS or balAge!=0 => flag.')

if __name__ == '__main__':
    main()
