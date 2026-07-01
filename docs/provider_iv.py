#!/usr/bin/env python3
"""
Provider-preference IV for the gestalt-triggered trials (PPI, benzo, opioid, antipsychotic,
steroid, anticoag-ppx). Instrument = admitting provider's LEAVE-ONE-OUT prescribing rate for the
drug class (as-if-random patient-provider assignment). First stage = exposure ~ provider tendency;
reduced form = outcome ~ provider tendency; LATE = RF/FS. Hardened: conditions WITHIN service
(service fixed effects) and reports balance (age ~ instrument) as the exclusion-restriction check.
Reads rx_class.csv + admissions + patients + services. No PHI printed.
"""
import csv, math
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
CLASSES = ['ppi', 'h2', 'benzo', 'opioid', 'antipsy', 'steroid', 'anticoag_ppx']

def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except Exception: return None

def load_rx():
    d = {}
    try: f = open(SD+'rx_class.csv')
    except FileNotFoundError: return d
    r = csv.reader(f); next(r, None)
    for row in r:
        if len(row) < 3: continue
        hadm, cls, st = row[0], row[1], row[2]
        t = ep(st)
        d.setdefault(hadm, {}).setdefault(cls, []).append(t if t else 1e18)
    f.close(); return d

def load_adm():
    d = {}
    with open(SD+'admissions.csv') as f:
        r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
        for row in r:
            prov = row[ix['admit_provider_id']] if 'admit_provider_id' in ix else ''
            adm = ep(row[ix['admittime']]); dis = ep(row[ix['dischtime']])
            d[row[ix['hadm_id']]] = {'prov': prov, 'admit': adm,
                'expire': int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0,
                'los': (dis-adm)/24.0 if (adm and dis) else None, 'subject': row[ix['subject_id']]}
    return d

def load_age():
    d = {}
    with open(SD+'patients.csv') as f:
        r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
        for row in r:
            try: d[row[ix['subject_id']]] = float(row[ix['anchor_age']])
            except Exception: pass
    return d

def load_service():
    d = {}
    try: f = open(SD+'services.csv')
    except FileNotFoundError: return d
    r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
    for row in r:
        h = row[ix['hadm_id']]
        if h not in d: d[h] = row[ix['curr_service']]  # first service
    f.close(); return d

def ols(y, X):
    X = np.asarray(X,float); y = np.asarray(y,float)
    Bi = np.linalg.pinv(X.T@X); b = Bi@(X.T@y); res = y - X@b
    n,k = X.shape; S = X*res[:,None]; cov = Bi@(S.T@S)@Bi*(n/max(n-k,1))
    return b, np.sqrt(np.diag(cov))

def service_dummies(svcs):
    top = ['MED','CMED','SURG','CSURG','NMED','NSURG','TRAUM','OMED','GU','VSURG','ORTHO','PSURG']
    M = np.zeros((len(svcs), len(top)))
    for i,s in enumerate(svcs):
        if s in top: M[i, top.index(s)] = 1
    return M

def main():
    print('=== Provider-preference IV (gestalt-triggered de-implementation trials) ===')
    print('instrument = admitting provider LOO prescribing rate; balAge~0 => as-if-random; within-service FE\n')
    rx = load_rx(); adm = load_adm(); age = load_age(); svc = load_service()
    print(f'hadm with any tracked rx: {len(rx)} | admissions: {len(adm)} | services: {len(svc)}')
    for cls in CLASSES:
        rows = []
        for hadm, a in adm.items():
            if not a['prov'] or a['admit'] is None: continue
            ag = age.get(a['subject'], np.nan)
            if math.isnan(ag): continue
            # exposure: drug class within 48h of admit
            times = rx.get(hadm, {}).get(cls, [])
            d = 1.0 if any(a['admit'] <= t <= a['admit']+48 for t in times) else 0.0
            rows.append({'hadm':hadm, 'prov':a['prov'], 'd':d, 'y':float(a['expire']),
                         'age':ag, 'svc':svc.get(hadm,'')})
        if len(rows) < 2000:
            print(f'  {cls:14s}: n={len(rows)} (too small)'); continue
        # provider LOO rate (>=20 admissions)
        from collections import defaultdict
        psum = defaultdict(float); pcnt = defaultdict(int)
        for r in rows:
            psum[r['prov']] += r['d']; pcnt[r['prov']] += 1
        sub = [r for r in rows if pcnt[r['prov']] >= 20]
        if len(sub) < 2000:
            print(f'  {cls:14s}: n_provider>=20 too few ({len(sub)})'); continue
        z = np.array([(psum[r['prov']]-r['d'])/(pcnt[r['prov']]-1) for r in sub])
        d = np.array([r['d'] for r in sub]); y = np.array([r['y'] for r in sub])
        agev = np.array([r['age'] for r in sub])
        D = service_dummies([r['svc'] for r in sub])
        X = np.column_stack([z, np.ones(len(z)), agev, D])   # controls: age + service FE
        bfs, sfs = ols(d, X); brf, srf = ols(y, X)
        fs, rf = bfs[0], brf[0]
        # balance: age ~ z | service (drop age from controls)
        Xb = np.column_stack([z, np.ones(len(z)), D])
        ba, sab = ols(agev, Xb)
        expo = d.mean(); rng = np.percentile(z, [10,90])
        late = rf/fs if abs(fs) > 1e-3 else float('nan')
        print(f'  {cls:14s} n={len(sub):6d} exp={expo:.3f} provSpread[p10-90]={rng[0]:.2f}-{rng[1]:.2f} | '
              f'FS={fs:+.3f}({sfs[0]:.3f}) | RF={rf:+.5f}({srf[0]:.5f}) | LATE={late:+.3f} | '
              f'balAge={ba[0]:+.2f}({sab[0]:.2f})')
    print('\nDONE. Strong FS + balAge~0 => valid provider IV. balAge!=0 => exclusion suspect (habit~case-mix).')

if __name__ == '__main__':
    main()
