#!/usr/bin/env python3
"""
Attending-rotation time-RDD (instrument C): exogenous within-patient shock. At a service handoff
the receiving team's habit changes prescribing for the SAME patient at an as-if-random time,
unrelated to the patient's trajectory -> fixes within-patient FE's sicker-episode flaw.
Design (per drug class active at a handoff):
  continuation D = drug still active >12h after the first service transfer | active before it.
  instrument Z  = receiving service's leave-one-out class-continuation propensity.
  first stage D ~ Z | sending service; outcome mortality ~ Z.
Uses services.csv (transfers) + rx_class.csv (start/stop). Exploratory (needs stoptime present).
"""
import csv, math
from datetime import datetime
from collections import defaultdict
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
CLASSES = ['ppi', 'benzo', 'steroid', 'opioid', 'antipsy']

def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except Exception: return None

def load_rx_intervals(cls):
    d = {}
    try: f = open(SD+'rx_class.csv')
    except FileNotFoundError: return d
    r = csv.reader(f); hdr = next(r, None)
    for row in r:
        if len(row) < 5 or row[1] != cls: continue
        s = ep(row[2]); e = ep(row[4])
        if s is None: continue
        if e is None: e = s + 24
        d.setdefault(row[0], []).append((s, e))
    f.close(); return d

def load_transfers():
    """hadm -> list of (transfertime, prev_service, curr_service), sorted."""
    d = {}
    try: f = open(SD+'services.csv')
    except FileNotFoundError: return d
    r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
    for row in r:
        t = ep(row[ix['transfertime']])
        d.setdefault(row[ix['hadm_id']], []).append((t if t else 0, row[ix['prev_service']], row[ix['curr_service']]))
    for k in d: d[k].sort()
    f.close(); return d

def load_adm():
    d = {}
    with open(SD+'admissions.csv') as f:
        r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
        for row in r:
            d[row[ix['hadm_id']]] = int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0
    return d

def ols(y, X):
    X = np.asarray(X,float); y = np.asarray(y,float)
    Bi = np.linalg.pinv(X.T@X); b = Bi@(X.T@y); res = y - X@b
    n,k = X.shape; S = X*res[:,None]; cov = Bi@(S.T@S)@Bi*(n/max(n-k,1))
    return b, np.sqrt(np.diag(cov))

def active(intervals, t):
    return any(s <= t <= e for (s, e) in intervals)

def main():
    print('=== Attending-rotation time-RDD (instrument C): within-patient exogenous handoff shock ===\n')
    trans = load_transfers(); adm = load_adm()
    if not trans:
        print('services.csv missing -> SKIP'); return
    for cls in CLASSES:
        rx = load_rx_intervals(cls)
        recs = []  # (hadm, recv_service, send_service, D_continue, Y)
        for hadm, tlist in trans.items():
            if hadm not in adm or hadm not in rx: continue
            iv = rx[hadm]
            for (tt, prev, curr) in tlist:
                if tt <= 0 or prev == curr or not prev or not curr: continue
                if active(iv, tt - 1):  # drug active just before handoff
                    D = 1.0 if active(iv, tt + 12) else 0.0
                    recs.append((hadm, curr, prev, D, float(adm[hadm])))
                    break  # first qualifying handoff only
        if len(recs) < 500:
            print(f'  {cls:10s}: n={len(recs)} qualifying handoffs (too small)'); continue
        # receiving-service LOO continuation propensity
        ssum = defaultdict(float); scnt = defaultdict(int)
        for (_, recv, _, D, _) in recs:
            ssum[recv] += D; scnt[recv] += 1
        sub = [r for r in recs if scnt[r[1]] >= 20]
        if len(sub) < 500:
            print(f'  {cls:10s}: n_recv>=20 too few ({len(sub)})'); continue
        z = np.array([(ssum[r[1]]-r[3])/(scnt[r[1]]-1) for r in sub])
        D = np.array([r[3] for r in sub]); Y = np.array([r[4] for r in sub])
        # sending-service fixed effects
        sends = sorted(set(r[2] for r in sub))
        SF = np.array([[1.0 if r[2]==s else 0.0 for s in sends[:10]] for r in sub])
        X = np.column_stack([z, np.ones(len(z)), SF])
        bfs, sfs = ols(D, X); brf, srf = ols(Y, X)
        fs, rf = bfs[0], brf[0]
        late = rf/fs if abs(fs) > 1e-3 else float('nan')
        print(f'  {cls:10s} n={len(sub):6d} cont={D.mean():.3f} | FS={fs:+.3f}({sfs[0]:.3f}) | '
              f'RF(mort)={rf:+.5f}({srf[0]:.5f}) | LATE={late:+.3f}')
    print('\nDONE. FS>0 = receiving team habit drives continuation; RF = its effect on mortality (within-patient, exogenous handoff).')

if __name__ == '__main__':
    main()
