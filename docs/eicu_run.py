#!/usr/bin/env python3
"""
eICU-CRD v2.0 EXTERNAL REPLICATION of the assay-noise IV / flag-ITT engine
(mirrors /home/user/Codex-playground-/docs/portfolio_run.py, the MIMIC-IV engine) for the
4 benchmark de-implementation cases that are lab-flag-triggered and available in eICU-CRD:

  RBC transfusion      @ Hgb < 7        (TRICC/TRISS validation)
  Platelet transfusion @ platelets < 10
  Bicarbonate          @ HCO3 < 15      (acidosis correction)
  Insulin              @ glucose > 180  (NICE-SUGAR validation)

Design (identical to the MIMIC engine, restated for eICU's minute-offset clock):
  - M1, M2 = first two pre-treatment lab draws (labresultoffset, minutes from ICU admit)
  - instrument Z = 1(M2 crosses the flag in the de-implementation direction)
  - severity control = midpoint (M1+M2)/2, entered as a local-linear (2nd-order) control
    function of (mid - flag), i.e. RDD-style bandwidth regression
  - D = 1(treatment of the matching class occurs within 24h of M2)
  - primary outcome Y = hospital mortality (patient.hospitaldischargestatus == 'Expired')
  - reports: n, noise sigma, first-stage F, flag-ITT (headline), implied-LATE with
    Anderson-Rubin CI, covariate balance (age), M2 density/heaping (McCrary-style), and the
    NAIVE (confounded) D->mortality contrast (crude + severity-adjusted) for comparison.

Inputs (produced by eicu_stream_lab.py / eicu_stream_tx.py from the raw eICU-CRD CSV.gz):
  eicu_lab_hb.csv, eicu_lab_plt.csv, eicu_lab_hco3.csv, eicu_lab_glu.csv   (labresult streams)
  eicu_tx.csv                                                              (treatment stream)
  patient.csv (unzipped eICU-CRD patient.csv.gz: patientunitstayid, age, hospitaldischargestatus)

All offsets are minutes from ICU admission (eICU convention) — no timestamp parsing needed,
unlike the MIMIC engine which parses charttime strings. Missing input files => SKIP, no crash.
"""
import csv, math
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'

# (name, lab_csv_key, tx_class, flag, direction '<'|'>', bandwidth)
# Units match eICU labresult conventions: Hgb g/dL, platelets x1000/uL, HCO3 mEq/L, glucose mg/dL.
CONFIG = [
    ('RBC transfusion (Hgb<7)',        'hb',   'rbc',     7.0,  '<', 0.60),
    ('Platelet transfusion (<10)',     'plt',  'plt',     10.0, '<', 5.0),
    ('Bicarbonate (acidosis, <15)',    'hco3', 'hco3',    15.0, '<', 3.0),
    ('Insulin (glucose>180)',          'glu',  'insulin', 180,  '>', 25),
]

def load_labseq(key):
    """offset in minutes -> convert to hours for readability/consistency with MIMIC engine."""
    d = {}
    try:
        f = open(SD + f'eicu_lab_{key}.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 4:
            continue
        pid, off, _name, vn = row[0], row[1], row[2], row[3]
        if not pid or not off or not vn:
            continue
        try:
            t = float(off) / 60.0  # minutes -> hours
            v = float(vn)
        except ValueError:
            continue
        d.setdefault(pid, []).append((t, v))
    f.close()
    for k in d:
        d[k].sort()
    return d

def load_tx(cls):
    d = {}
    try:
        f = open(SD + 'eicu_tx.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 3:
            continue
        pid, off, c = row[0], row[1], row[2]
        if c != cls or not pid or not off:
            continue
        try:
            t = float(off) / 60.0  # minutes -> hours
        except ValueError:
            continue
        d.setdefault(pid, []).append(t)
    f.close()
    for k in d:
        d[k].sort()
    return d

def load_patient():
    """patient.csv (unzipped patient.csv.gz): patientunitstayid, age, hospitaldischargestatus.
    age is a string; '> 89' (deidentified top-code) -> 90. Returns dict keyed by patientunitstayid.
    """
    d = {}
    try:
        f = open(SD + 'patient.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    hdr = next(r)
    idx = {n: i for i, n in enumerate(hdr)}
    i_pid = idx['patientunitstayid']
    i_age = idx['age']
    i_status = idx['hospitaldischargestatus']
    for row in r:
        pid = row[i_pid]
        age_raw = row[i_age].strip() if i_age < len(row) else ''
        if age_raw == '> 89':
            age = 90.0
        else:
            try:
                age = float(age_raw)
            except ValueError:
                age = float('nan')
        status = row[i_status] if i_status < len(row) else ''
        expire = 1 if status.strip().lower() == 'expired' else 0
        d[pid] = {'age': age, 'expire': expire}
    f.close()
    return d

def ols(y, X):
    X = np.asarray(X, float); y = np.asarray(y, float)
    Bi = np.linalg.pinv(X.T @ X); b = Bi @ (X.T @ y); res = y - X @ b
    n, k = X.shape; S = X * res[:, None]; cov = Bi @ (S.T @ S) @ Bi * (n / (n - k))
    return b, np.sqrt(np.diag(cov))

def cb(t, flag):
    c = np.asarray(t, float) - flag
    return np.column_stack([np.ones_like(c), c, c * c])

def design_controls(mids):
    c = np.asarray(mids, float)
    return np.column_stack([np.ones_like(c), c])

def run_trial(name, key, tx_class, flag, direction, hw, pat):
    seqs = load_labseq(key)
    if not seqs:
        print(f'  {name:28s}: eicu_lab_{key}.csv empty/missing — SKIP'); return
    tx = load_tx(tx_class)
    if not tx:
        print(f'  {name:28s}: eicu_tx.csv has no "{tx_class}" rows (or file missing) — SKIP'); return

    # noise sigma: adjacent pre-treatment draws within 12h, no intervening treatment
    diffs = []
    for pid, seq in seqs.items():
        rt = tx.get(pid, [])
        for i in range(len(seq) - 1):
            (t1, v1), (t2, v2) = seq[i], seq[i + 1]
            if 0 < t2 - t1 <= 12 and not any(t1 < r <= t2 for r in rt):
                diffs.append(v2 - v1)
    sig = np.std(diffs) / math.sqrt(2) if len(diffs) > 100 else float('nan')

    # single-decision cohort: M1, M2 = first two pre-treatment draws
    rows = []
    cross = (lambda v: v < flag) if direction == '<' else (lambda v: v > flag)
    for pid, seq in seqs.items():
        if pid not in pat:
            continue
        rt = tx.get(pid, []); first = rt[0] if rt else float('inf')
        pre = [(t, v) for (t, v) in seq if t < first]
        if len(pre) < 2:
            continue
        (t1, m1), (t2, m2) = pre[0], pre[1]
        rows.append({
            'mid': (m1 + m2) / 2, 'm2': m2,
            'z': 1.0 if cross(m2) else 0.0,
            'd': 1.0 if any(t2 <= r <= t2 + 24 for r in rt) else 0.0,
            'y': float(pat[pid]['expire']),
            'age': pat[pid]['age'],
        })

    sub = [r for r in rows if abs(r['mid'] - flag) <= hw and not math.isnan(r['age'])]
    if len(sub) < 300:
        print(f'  {name:28s}: n={len(sub)} in-band (too small); cohort={len(rows)} sigma={sig:.3g}'); return

    z = np.array([r['z'] for r in sub]); d = np.array([r['d'] for r in sub])
    y = np.array([r['y'] for r in sub]); C = cb([r['mid'] for r in sub], flag)
    X = np.column_stack([z, C])
    bfs, sfs = ols(d, X); brf, srf = ols(y, X)
    fs, rf = bfs[0], brf[0]
    F = (fs / sfs[0]) ** 2 if sfs[0] > 0 else 0
    ba, sa = ols(np.array([r['age'] for r in sub]), X)
    ar = [b0 for b0 in np.arange(-1, 1.0001, 0.02)
          if abs((lambda bb, sb: bb[0] / sb[0] if sb[0] > 0 else 9)(*ols(y - b0 * d, X))) < 1.96]
    arlo, arhi = (min(ar), max(ar)) if ar else (float('nan'), float('nan'))
    late = rf / fs if abs(fs) > 1e-3 else float('nan')

    # NAIVE association ('if run simply from this data'): crude + severity-adjusted D->mortality
    # on the full cohort. Confounding-by-indication typically makes this show FALSE HARM;
    # contrast with the method's flag-ITT.
    Dall = np.array([r['d'] for r in rows]); Yall = np.array([r['y'] for r in rows])
    Call = design_controls([r['mid'] for r in rows])
    naive_crude, _ = ols(Yall, np.column_stack([Dall, np.ones_like(Dall)]))
    naive_adj, _ = ols(Yall, np.column_stack([Dall, Call]))

    # McCrary-style density test: mass just-below vs just-above the flag on M2 (manipulation/heaping)
    m2 = np.array([r['m2'] for r in sub])
    delta = max(hw / 3, sig if not math.isnan(sig) else hw / 3)
    below = np.sum((m2 >= flag - delta) & (m2 < flag)); above = np.sum((m2 >= flag) & (m2 < flag + delta))
    dens = below / above if above > 0 else float('nan')

    F_flag = '⚠' if F < 10 else ' '
    bal_flag = '⚠' if abs(ba[0]) > 3 else ' '
    print(f'  {name:28s} n={len(sub):6d} tx={d.mean():.3f} sig={sig:.3g}({100*sig/max(abs(flag),1e-9):.1f}%) | '
          f'NAIVE crude={naive_crude[0]:+.4f} adj={naive_adj[0]:+.4f} | '
          f'FS={fs:+.3f}(F{F:4.0f}){F_flag}| ITT={rf:+.5f}({srf[0]:.5f}) | LATE={late:+.3f} AR[{arlo:+.2f},{arhi:+.2f}] | '
          f'balAge={ba[0]:+.2f}{bal_flag}| densB/A={dens:.2f}')

def main():
    print('=== eICU-CRD v2.0 EXTERNAL REPLICATION: assay-noise IV / flag-ITT (4 benchmark trials) ===')
    print('headline=flag-ITT(mortality); LATE=implied (ITT/FS) with Anderson-Rubin CI; balAge~0 => exogenous\n')
    pat = load_patient()
    if not pat:
        print('patient.csv missing/empty — SKIP all trials (need patientunitstayid, age, hospitaldischargestatus)')
        return
    for (name, key, tx_class, flag, direction, hw) in CONFIG:
        run_trial(name, key, tx_class, flag, direction, hw, pat)
    print('\nDONE. Interpret: strong FS + balAge~0 + precise ITT => usable; weak FS or balAge!=0 => flag.')
    print('External-replication read: directional agreement with the MIMIC-IV portfolio_run.py results')
    print('on flag-ITT sign/magnitude is the confirmatory signal; NAIVE vs flag-ITT divergence should')
    print('replicate too (same confounding-by-indication mechanism is site-agnostic).')

if __name__ == '__main__':
    main()
