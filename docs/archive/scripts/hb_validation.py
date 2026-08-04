#!/usr/bin/env python3
"""
RCT-ANCHORED VALIDATION: assay-noise IV / flag-ITT for RBC transfusion at the Hb threshold.
Ground truth (RCTs): restrictive (Hb<7) non-inferior/superior in GENERAL ICU (TRICC/TRISS/FOCUS),
CONTESTED in CARDIAC SURGERY (TITRe2 mortality HR 1.64) / acute MI (MINT). Dual-stratum recovery
= a graded test. Benchmarks Bosch et al. Ann ATS 2022 (fuzzy RDD at Hb 7 in MIMIC-IV; first stage >20pp).
Reports: Hb noise sigma; first stage (transfusion ~ flag); flag-ITT (mortality) + implied-LATE (ITT/FS)
with Anderson-Rubin CI; balance; by stratum and threshold. Leads with the ITT, reports implied-LATE
so a null is legible as 'no effect OR underpowered', not silently 'no effect'.
"""
import csv, math
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
RBC = {'225168'}  # packed red blood cells

def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp() / 3600.0
    except Exception: return None

def load_labseq(path):
    d = {}
    try: f = open(path)
    except FileNotFoundError: return d
    r = csv.reader(f); next(r, None)
    for row in r:
        if len(row) < 3: continue
        hadm, ct, vn = row[0], row[1], row[2]
        t = ep(ct)
        if t is None or not vn or not hadm: continue
        try: v = float(vn)
        except ValueError: continue
        if v <= 0 or v > 25: continue
        d.setdefault(hadm, []).append((t, v))
    f.close()
    for k in d: d[k].sort()
    return d

def load_repl(path, items):
    d = {}
    with open(path) as f:
        r = csv.reader(f); next(r)
        for hadm, itemid, st in r:
            if itemid not in items: continue
            t = ep(st)
            if t is not None: d.setdefault(hadm, []).append(t)
    for k in d: d[k].sort()
    return d

def load_adm(path):
    d = {}
    with open(path) as f:
        r = csv.reader(f); hdr = next(r); idx = {n: i for i, n in enumerate(hdr)}
        for row in r:
            d[row[idx['hadm_id']]] = {
                'subject': row[idx['subject_id']],
                'expire': int(row[idx['hospital_expire_flag']]) if row[idx['hospital_expire_flag']] else 0,
            }
    return d

def load_age(path):
    d = {}
    with open(path) as f:
        r = csv.reader(f); hdr = next(r); idx = {n: i for i, n in enumerate(hdr)}
        for row in r:
            try: d[row[idx['subject_id']]] = float(row[idx['anchor_age']])
            except Exception: pass
    return d

def load_cardiac(path):
    """hadm -> True if ever on a cardiac-surgery service."""
    s = set()
    try: f = open(path)
    except FileNotFoundError: return s
    r = csv.reader(f); hdr = next(r); idx = {n: i for i, n in enumerate(hdr)}
    for row in r:
        if row[idx['curr_service']] in ('CSURG', 'CMED', 'VSURG'):
            s.add(row[idx['hadm_id']])
    f.close(); return s

def ols(y, X):
    X = np.asarray(X, float); y = np.asarray(y, float)
    Bi = np.linalg.pinv(X.T @ X); b = Bi @ (X.T @ y); res = y - X @ b
    n, k = X.shape
    S = X * res[:, None]; cov = Bi @ (S.T @ S) @ Bi * (n / (n - k))
    return b, np.sqrt(np.diag(cov))

def cb(t, flag):
    c = np.asarray(t, float) - flag
    return np.column_stack([np.ones_like(c), c, c * c])

def main():
    print('=== Hb-transfusion RCT-anchored validation (assay-noise IV / flag-ITT) ===')
    hb = load_labseq(SD + 'lab_hb.csv')
    if not hb:
        print('lab_hb.csv missing/empty — did the filter capture itemid 51222?'); return
    tx = load_repl(SD + 'repletions.csv', RBC)
    adm = load_adm(SD + 'admissions.csv'); age = load_age(SD + 'patients.csv')
    cardiac = load_cardiac(SD + 'services.csv')
    print(f'hadm with Hb: {len(hb)} | with RBC tx: {len(tx)} | cardiac-service hadm: {len(cardiac)}')

    # Hb noise sigma from consecutive pairs 1-12h apart, no intervening transfusion
    diffs = []
    for hadm, seq in hb.items():
        rt = tx.get(hadm, [])
        for i in range(len(seq) - 1):
            (t1, v1), (t2, v2) = seq[i], seq[i + 1]
            dt = t2 - t1
            if 0 < dt <= 12 and not any(t1 < r <= t2 for r in rt):
                diffs.append(v2 - v1)
    if len(diffs) > 100:
        sig = np.std(diffs) / math.sqrt(2)
        print(f'Hb noise sigma ~= {sig:.4f} g/dL (n_pairs={len(diffs)})  '
              f'[CV ~{100*sig/8:.1f}% at Hb 8; flag gap ~1.0 g/dL]')

    # build single-decision cohort: first two pre-transfusion Hb draws
    rows = []
    for hadm, seq in hb.items():
        if hadm not in adm: continue
        rt = tx.get(hadm, []); first = rt[0] if rt else float('inf')
        pre = [(t, v) for (t, v) in seq if t < first]
        if len(pre) < 2: continue
        (t1, h1), (t2, h2) = pre[0], pre[1]
        rows.append({'h1': h1, 'h2': h2, 'mid': (h1 + h2) / 2,
                     'd': 1 if any(t2 <= r <= t2 + 24 for r in rt) else 0,
                     'y': adm[hadm]['expire'], 'age': age.get(adm[hadm]['subject'], np.nan),
                     'cardiac': hadm in cardiac})
    print(f'single-decision cohort n={len(rows)}')

    def run(sub, flag, hw, label):
        sub = [r for r in sub if abs(r['mid'] - flag) <= hw]
        if len(sub) < 300:
            print(f'  {label} flag={flag}: n={len(sub)} (too small)'); return
        z = np.array([1.0 if r['h2'] < flag else 0.0 for r in sub])
        d = np.array([r['d'] for r in sub], float)
        y = np.array([r['y'] for r in sub], float)
        C = cb([r['mid'] for r in sub], flag); X = np.column_stack([z, C])
        bfs, sfs = ols(d, X); brf, srf = ols(y, X)
        fs, rf = bfs[0], brf[0]
        F = (fs / sfs[0]) ** 2 if sfs[0] > 0 else 0
        # implied-LATE + Anderson-Rubin CI
        ar = [b0 for b0 in np.arange(-1, 1.0001, 0.01)
              if abs((lambda bb, sb: bb[0] / sb[0] if sb[0] > 0 else 9)(*ols(y - b0 * d, X))) < 1.96]
        arlo, arhi = (min(ar), max(ar)) if ar else (float('nan'), float('nan'))
        ba, sa = ols(np.array([r['age'] for r in sub]), X)
        print(f'  {label} flag={flag} n={len(sub):6d} tx={d.mean():.3f} | '
              f'FS={fs:+.3f}(F={F:4.0f}) | flag-ITT(mort)={rf:+.5f}({srf[0]:.5f}) | '
              f'impliedLATE={rf/fs if abs(fs)>1e-3 else float("nan"):+.3f} AR[{arlo:+.2f},{arhi:+.2f}] | '
              f'balAge={ba[0]:+.2f}')

    print('\n-- ALL patients (Bosch-style first stage + flag-ITT) --')
    for flag, hw in [(7.0, 0.6), (8.0, 0.6)]:
        run(rows, flag, hw, 'ALL   ')
    print('\n-- GENERAL (non-cardiac): RCT truth = restrictive non-inferior (expect ITT ~ 0) --')
    gen = [r for r in rows if not r['cardiac']]
    for flag, hw in [(7.0, 0.6), (8.0, 0.6)]:
        run(gen, flag, hw, 'GENERL')
    print('\n-- CARDIAC surgery: RCT truth CONTESTED (TITRe2 liberal-favoring; expect signal) --')
    car = [r for r in rows if r['cardiac']]
    for flag, hw in [(7.0, 0.6), (8.0, 0.6)]:
        run(car, flag, hw, 'CARDIAC')
    print('\nDONE — interpretation: recovering ~0 in GENERAL and a liberal-favoring signal in CARDIAC')
    print('would validate the method against the graded RCT truth (extends Bosch 2022 with a formal noise model).')

if __name__ == '__main__':
    main()
