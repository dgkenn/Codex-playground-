#!/usr/bin/env python3
"""
Nurse-PRN administration preference IV (instrument B) — NOW RUNNABLE from streamed emar.
For benzo/opioid/antipsychotic due-dose events (emar), the physician ORDER is confounded by
indication, but WHETHER the covering nurse ADMINISTERS a given due dose is driven by nurse practice
+ workload -> as-if-random conditional on the dose being due. One causal step closer to random.

  unit of analysis = emar due-dose event (Administered vs Not Given/Held)
  treatment D      = 1 if administered
  instrument Z     = administering nurse's (enter_provider_id) leave-one-out administration rate
  first stage D ~ Z ; outcome (hadm mortality) ~ Z ; balance (age ~ Z) as exclusion check
Reads emar_prn.csv + admissions + patients. Aggregates to patient exposure (mean administration
propensity of the nurses they drew) then IV on hadm-level outcome. No PHI printed.
"""
import csv, math
from collections import defaultdict
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
ADMIN = ('administered', 'started', 'restarted', 'applied', 'given', 'confirmed')
NOTGIVEN = ('not given', 'hold', 'held', 'delayed', 'stopped', 'not flush')

def is_admin(ev):
    e = ev.lower()
    if any(k in e for k in NOTGIVEN): return 0
    if any(k in e for k in ADMIN): return 1
    return None  # ambiguous -> skip

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

def main():
    import os
    if not os.path.exists(SD+'emar_prn.csv'):
        print('nurse_prn_iv: emar_prn.csv not present yet (emar still streaming) — SKIP'); return
    print('=== Nurse-PRN administration IV (instrument B) — from streamed emar ===\n')
    adm = load_adm(); age = load_age()
    # pass 1: nurse administration counts by class; per-(hadm,class) events
    events = defaultdict(list)  # (hadm,cls) -> list of (nurse, D)
    nsum = defaultdict(lambda: defaultdict(float)); ncnt = defaultdict(lambda: defaultdict(int))
    with open(SD+'emar_prn.csv') as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            if len(row) < 5: continue
            hadm, _, cls, ev, prov = row
            D = is_admin(ev)
            if D is None or not prov: continue
            events[(hadm, cls)].append((prov, D))
            nsum[cls][prov] += D; ncnt[cls][prov] += 1
    for cls in ['benzo', 'opioid', 'antipsy']:
        # patient-level instrument = mean LOO administration rate of the nurses that patient drew (nurses >=30 events)
        rows = []
        for (hadm, c), evs in events.items():
            if c != cls or hadm not in adm: continue
            ag = age.get(adm[hadm]['subject'], np.nan)
            if math.isnan(ag): continue
            zs = []; ds = []
            for (prov, D) in evs:
                if ncnt[cls][prov] < 30: continue
                loo = (nsum[cls][prov]-D)/(ncnt[cls][prov]-1)
                zs.append(loo); ds.append(D)
            if not zs: continue
            rows.append({'z':np.mean(zs), 'd':np.mean(ds), 'y':float(adm[hadm]['expire']), 'age':ag})
        if len(rows) < 500:
            print(f'  {cls:8s}: n={len(rows)} (too small)'); continue
        z = np.array([r['z'] for r in rows]); d = np.array([r['d'] for r in rows])
        y = np.array([r['y'] for r in rows]); agev = np.array([r['age'] for r in rows])
        X = np.column_stack([z, np.ones(len(z))])
        bfs, sfs = ols(d, X); brf, srf = ols(y, X); ba, sab = ols(agev, X)
        fs, rf = bfs[0], brf[0]
        late = rf/fs if abs(fs) > 1e-3 else float('nan')
        print(f'  {cls:8s} n={len(rows):6d} adminRate={d.mean():.3f} nurseSpread={z.std():.3f} | '
              f'FS={fs:+.3f}({sfs[0]:.3f}) | RF(mort)={rf:+.5f}({srf[0]:.5f}) | LATE={late:+.3f} | '
              f'balAge={ba[0]:+.2f}({sab[0]:.2f})')
    print('\nDONE. FS>0 = nurse habit drives administration; balAge~0 => nurse assignment as-if-random.')
    print('Refinement: restrict to PRN orders (join poe/prescriptions) + condition within unit x shift.')

if __name__ == '__main__':
    main()
