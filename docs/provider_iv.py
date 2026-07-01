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
            at = row[ix['admission_type']] if 'admission_type' in ix else ''
            d[row[ix['hadm_id']]] = {'prov': prov, 'admit': adm,
                'expire': int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0,
                'los': (dis-adm)/24.0 if (adm and dis) else None, 'subject': row[ix['subject_id']],
                'admtype': at}
    return d

# low-acuity strata where patient<->provider assignment is most plausibly as-if-random (our prior finding:
# provider-IV is clean only here; confounded in emergent admissions where acuity triages patients to teams)
LOW_ACUITY = {'ELECTIVE', 'SURGICAL SAME DAY ADMISSION', 'OBSERVATION ADMIT',
              'DIRECT OBSERVATION', 'AMBULATORY OBSERVATION'}

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

def load_nc():
    d = {}; keys = []
    try: f = open(SD+'nc_outcomes.csv')
    except FileNotFoundError: return d, keys
    r = csv.reader(f); hdr = next(r); keys = hdr[1:]
    for row in r:
        d[row[0]] = [int(x) for x in row[1:]]
    f.close(); return d, keys

def empirical_null(coefs, ses):
    """MLE empirical null N(mu, sd^2); returns (mu, sd)."""
    import numpy as _np
    from scipy import optimize as _opt
    c = _np.asarray(coefs); s = _np.asarray(ses)
    def nll(p):
        mu, lsd = p; v = _np.exp(2*lsd)+s**2
        return 0.5*_np.sum(_np.log(2*_np.pi*v)+(c-mu)**2/v)
    r = _opt.minimize(nll, [0.0, _np.log(_np.std(c)+1e-6)], method='Nelder-Mead')
    return r.x[0], _np.exp(r.x[1])

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
    nc, nckeys = load_nc()
    print(f'hadm with any tracked rx: {len(rx)} | admissions: {len(adm)} | services: {len(svc)} | '
          f'NC panel: {len(nc)} hadm x {len(nckeys)} controls')
    from collections import defaultdict
    def run_stratum(cls, rows, label):
        if len(rows) < 1500:
            print(f'    {label:8s}: n={len(rows)} (too small)'); return
        # provider LOO rate computed WITHIN this stratum (comparable case-mix)
        psum = defaultdict(float); pcnt = defaultdict(int)
        for r in rows:
            psum[r['prov']] += r['d']; pcnt[r['prov']] += 1
        sub = [r for r in rows if pcnt[r['prov']] >= 20]
        if len(sub) < 1500:
            print(f'    {label:8s}: providers>=20 too few ({len(sub)})'); return
        z = np.array([(psum[r['prov']]-r['d'])/(pcnt[r['prov']]-1) for r in sub])
        d = np.array([r['d'] for r in sub]); y = np.array([r['y'] for r in sub])
        agev = np.array([r['age'] for r in sub]); agec = (agev-60)/10.0
        D = service_dummies([r['svc'] for r in sub])
        # controls: age spline (age, age^2) + service FE
        X = np.column_stack([z, np.ones(len(z)), agec, agec*agec, D])
        bfs, sfs = ols(d, X); brf, srf = ols(y, X)
        fs, rf = bfs[0], brf[0]
        rng = np.percentile(z, [10,90]); zspan = rng[1]-rng[0]
        # STANDARDIZED balance: predicted age difference across the instrument's p10-p90 range (years)
        Xb = np.column_stack([z, np.ones(len(z)), D])
        ba, _ = ols(agev, Xb); bal_yrs = ba[0]*zspan
        late = rf/fs if abs(fs) > 1e-3 else float('nan')
        naive, _ = ols(y, np.column_stack([d, np.ones_like(d)]))
        # negative-control empirical-null calibration
        nctxt = ''
        if nc and nckeys:
            ncc, ncs = [], []
            for j in range(len(nckeys)):
                yv = np.array([nc.get(r['hadm'], [0]*len(nckeys))[j] for r in sub], float)
                if yv.sum() < 20: continue
                bb, sb = ols(yv, X); ncc.append(bb[0]); ncs.append(sb[0])
            if len(ncc) >= 5:
                mu, sd = empirical_null(ncc, ncs)
                from scipy import stats as _st
                p_cal = 2*_st.norm.sf(abs(rf-mu)/np.sqrt(sd**2+srf[0]**2))
                nctxt = f' NCcal_p={p_cal:.3f}'
        valid = '✓VALID' if abs(bal_yrs) < 1.0 and 5 < (fs/sfs[0])**2 else '✗INVALID(balance)'
        print(f'    {label:8s} n={len(sub):6d} exp={d.mean():.3f} | NAIVE={naive[0]:+.4f} | '
              f'FS={fs:+.3f} | RF(ITT)={rf:+.5f}({srf[0]:.5f}) LATE={late:+.3f} | '
              f'bal={bal_yrs:+.1f}yr {valid}{nctxt}')

    for cls in CLASSES:
        rows_low, rows_high = [], []
        for hadm, a in adm.items():
            if not a['prov'] or a['admit'] is None: continue
            ag = age.get(a['subject'], np.nan)
            if math.isnan(ag): continue
            times = rx.get(hadm, {}).get(cls, [])
            d = 1.0 if any(a['admit'] <= t <= a['admit']+48 for t in times) else 0.0
            row = {'hadm':hadm, 'prov':a['prov'], 'd':d, 'y':float(a['expire']),
                   'age':ag, 'svc':svc.get(hadm,'')}
            (rows_low if a['admtype'] in LOW_ACUITY else rows_high).append(row)
        print(f'  {cls}:')
        run_stratum(cls, rows_low, 'ELECTIVE')   # headline: as-if-random assignment most plausible
        run_stratum(cls, rows_high, 'EMERGENT')   # contrast: expect confounded (acuity triage)
    print('\nDONE. ELECTIVE stratum with bal<1yr + F>5 = valid provider IV; EMERGENT balance failure = the')
    print('confounding-by-indication the balance gate is designed to catch. RF(ITT) is the headline; LATE fragile.')

if __name__ == '__main__':
    main()
