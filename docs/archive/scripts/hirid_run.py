#!/usr/bin/env python3
"""
HiRID (Bern, Switzerland; PhysioNet "hirid" v1.1.1) EXTERNAL REPLICATION of the assay-noise IV /
flag-ITT engine (mirrors /home/user/Codex-playground-/docs/portfolio_run.py, the MIMIC-IV engine, and
docs/eicu_run.py, the eICU-CRD replication) for the lab-flag-triggered benchmark cases available in HiRID:

  RBC transfusion      @ Hgb < 7        (TRICC/TRISS validation)
  Insulin              @ glucose > 180  (NICE-SUGAR validation)
  Bicarbonate          @ HCO3 < 15      (acidosis correction)
  Potassium chloride   @ K < 3.5        (repletion; context/secondary)
  Magnesium repletion  @ Mg < 2.0       (WEAK — lab id medium-confidence, no confirmed pharma id; see
                                          docs/MULTISITE_HARMONIZATION.md; kept here as a SKIP-by-default
                                          placeholder, do not trust until verified on access)

Design (identical to the MIMIC/eICU engines, restated for HiRID's ABSOLUTE-DATETIME clock — this is the
one replication dataset that needs real timestamp parsing, unlike eICU/SICdb/AmsterdamUMCdb's raw offsets):
  - M1, M2 = first two pre-treatment lab draws (observations.datetime, absolute, patient-timeshifted)
  - instrument Z = 1(M2 crosses the flag in the de-implementation direction)
  - severity control = midpoint (M1+M2)/2, local-linear (2nd-order) control function of (mid - flag)
  - D = 1(treatment of the matching class occurs within 24h of M2)
  - primary outcome Y = hospital mortality (general.discharge_status == 'dead')
  - reports: n, noise sigma, first-stage F, flag-ITT (headline), implied-LATE with Anderson-Rubin CI,
    covariate balance (age), M2 density/heaping (McCrary-style), and the NAIVE (confounded) D->mortality
    contrast (crude + severity-adjusted) for comparison.

=== ID MAPPINGS (see docs/MULTISITE_HARMONIZATION.md for full citations + confidence) ===
Labs (observations.variableid), from ricu concept-dict.json (github.com/eth-mds/ricu):
  hb    : 24000548, 24000836, 20000900     (raw units; ricu applies x0.1 -> g/dL)
  glu   : 20005110, 24000523, 24000585     (raw units; ricu applies x18.016 -> mg/dL)
  hco3  : 20004200                          (mEq/L)
  k     : 20000500, 24000520, 24000833, 24000867   (mEq/L)
  mg    : 20005200  (MEDIUM CONFIDENCE — ricu-only, not corroborated by HIRID-ICU-Benchmark varref.tsv;
                      x2.432 -> mg/dL; VERIFY against hirid_variable_reference.csv on access)
Treatments (pharma.pharmaid), from HIRID-ICU-Benchmark varref.tsv (github.com/ratschlab/HIRID-ICU-Benchmark)
cross-confirmed against ricu where noted:
  rbc     : 1000100 ("packed red blood cells"/"EK"), 1000743 ("EK Pflege")
  insulin : 15 ("Insulin Actrapid"), 1000724, 1000379   -- CROSS-SOURCE CONFIRMED (ricu + varref.tsv agree)
  nahco3  : 1000193 ("Na-Bicarbonat 8.4%"), 1000453 ("Na-Bicarbonat Inf Lsg 8.4%")
  kcl     : 1000080 ("K-Cl conc"), 1000568 ("K-Cl-Perfusor")
Patient (general table):
  age              : general.age               (years, capped at 90)
  sex              : general.sex                ('M'/'F')
  mortality        : general.discharge_status == 'dead'   (categorical: 'alive'/'dead'/'unknown')
Timestamps: observations.datetime, pharma.givenat, general.admissiontime are ABSOLUTE DATETIMES
(patient-timeshifted for de-identification) -- must be parsed and diffed against admissiontime, NOT
treated as raw offsets.

=== EXACT FETCH COMMANDS (fill in your PhysioNet credentials via ~/.netrc) ===
# Variable/pharma reference dictionaries (FETCH THESE FIRST -- day-one verification, see
# MULTISITE_HARMONIZATION.md checklist item 1):
wget -r -N -c -np --netrc -P ./hirid_raw \
  https://physionet.org/files/hirid/1.1.1/reference_data/hirid_variable_reference.csv
wget -r -N -c -np --netrc -P ./hirid_raw \
  https://physionet.org/files/hirid/1.1.1/reference_data/hirid_variable_reference_preprocessed.csv
wget -r -N -c -np --netrc -P ./hirid_raw \
  https://physionet.org/files/hirid/1.1.1/reference_data/ordinal_vars_ref.csv
# Schema PDF (table/column definitions):
wget -N -c --netrc -P ./hirid_raw https://physionet.org/files/hirid/1.1.1/doc/hirid_schema.pdf
# Raw tables (large; stream-filter, do not bulk-download uncompressed):
wget -r -N -c -np --netrc -P ./hirid_raw https://physionet.org/files/hirid/1.1.1/raw_stage/observation_tables/
wget -r -N -c -np --netrc -P ./hirid_raw https://physionet.org/files/hirid/1.1.1/raw_stage/pharma_records/
wget -r -N -c -np --netrc -P ./hirid_raw https://physionet.org/files/hirid/1.1.1/reference_data/general_table.csv

Inputs expected here (produced by a hirid_stream_lab.py / hirid_stream_tx.py stream-filter step,
mirroring eicu_stream_lab.py/eicu_stream_tx.py -- TODO: write those once table format is confirmed):
  hirid_lab_hb.csv, hirid_lab_glu.csv, hirid_lab_hco3.csv, hirid_lab_k.csv, hirid_lab_mg.csv
    columns: patientid, datetime_iso, variableid, value
  hirid_tx.csv
    columns: patientid, givenat_iso, tx_class   (tx_class in {rbc, insulin, nahco3, kcl})
  hirid_general.csv (renamed from the raw general_table.csv to a hirid_-prefixed name for consistency
  with the other adapters and to avoid any ambiguity with per-dataset scratchpad files; columns used:
  patientid, admissiontime, age, sex, discharge_status)

Missing input files => SKIP, no crash (same contract as eicu_run.py).
"""
import csv, math
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'

# (name, lab_csv_key, tx_class, flag, direction '<'|'>', bandwidth)
# TO-CONFIRM: units below assume ricu's converted units (g/dL, mg/dL, mEq/L) -- verify against
# hirid_variable_reference.csv on access; raw variableid values may need the ricu unit-conversion
# factors noted above applied during hirid_stream_lab.py before reaching these CSVs.
CONFIG = [
    ('RBC transfusion (Hgb<7)',        'hb',   'rbc',     7.0,  '<', 0.60),
    ('Insulin (glucose>180)',          'glu',  'insulin', 180,  '>', 25),
    ('Bicarbonate (acidosis, <15)',    'hco3', 'nahco3',  15.0, '<', 3.0),
    ('Potassium chloride (K<3.5)',     'k',    'kcl',     3.5,  '<', 0.25),
    # Magnesium: WEAK/SKIP-by-default -- lab variableid is medium-confidence (ricu only) and NO
    # treatment/pharma id was found in any public source for HiRID magnesium repletion. Left in CONFIG
    # as a documented placeholder; will legitimately SKIP (no mg tx_class rows) until verified on access.
    ('Magnesium repletion (Mg<2.0) -- UNVERIFIED, expect SKIP', 'mg', 'mg_TODO_UNMAPPED', 2.0, '<', 0.15),
]

def ep(s):
    """Parse HiRID's absolute (patient-timeshifted) ISO datetime -> epoch hours."""
    try:
        return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp() / 3600.0
    except Exception:
        return None

def load_labseq(key):
    d = {}
    try:
        f = open(SD + f'hirid_lab_{key}.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 4:
            continue
        pid, dt, _vid, vn = row[0], row[1], row[2], row[3]
        t = ep(dt)
        if t is None or not vn or not pid:
            continue
        try:
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
        f = open(SD + 'hirid_tx.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 3:
            continue
        pid, dt, c = row[0], row[1], row[2]
        if c != cls or not pid or not dt:
            continue
        t = ep(dt)
        if t is not None:
            d.setdefault(pid, []).append(t)
    f.close()
    for k in d:
        d[k].sort()
    return d

def load_patient():
    """hirid_general.csv (renamed from raw general_table.csv): patientid, admissiontime, age, sex, discharge_status.
    mortality = 1 if discharge_status == 'dead' else 0 (TO-CONFIRM exact string casing/values on access
    -- official docs give 'alive'/'dead'/'unknown', but verify against the real file header + a sample).
    """
    d = {}
    try:
        f = open(SD + 'hirid_general.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    hdr = next(r)
    idx = {n: i for i, n in enumerate(hdr)}
    if 'patientid' not in idx:
        print('  hirid_general.csv present but missing "patientid" column (wrong file/schema?) — SKIP all trials')
        f.close()
        return d
    i_pid = idx['patientid']
    i_age = idx.get('age')
    i_status = idx.get('discharge_status')
    i_sex = idx.get('sex')
    for row in r:
        pid = row[i_pid]
        try:
            age = float(row[i_age]) if i_age is not None else float('nan')
        except (ValueError, IndexError):
            age = float('nan')
        status = row[i_status].strip().lower() if (i_status is not None and i_status < len(row)) else ''
        expire = 1 if status == 'dead' else 0
        sex = row[i_sex] if (i_sex is not None and i_sex < len(row)) else ''
        d[pid] = {'age': age, 'expire': expire, 'sex': sex}
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
        print(f'  {name:40s}: hirid_lab_{key}.csv empty/missing — SKIP'); return
    tx = load_tx(tx_class)
    if not tx:
        print(f'  {name:40s}: hirid_tx.csv has no "{tx_class}" rows (or file missing) — SKIP'); return

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
        print(f'  {name:40s}: n={len(sub)} in-band (too small); cohort={len(rows)} sigma={sig:.3g}'); return

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

    # NAIVE association: crude + severity-adjusted D->mortality on full cohort (confounding-by-indication
    # check, same construction as portfolio_run.py/eicu_run.py).
    Dall = np.array([r['d'] for r in rows]); Yall = np.array([r['y'] for r in rows])
    Call = design_controls([r['mid'] for r in rows])
    naive_crude, _ = ols(Yall, np.column_stack([Dall, np.ones_like(Dall)]))
    naive_adj, _ = ols(Yall, np.column_stack([Dall, Call]))

    # McCrary-style density test: mass just-below vs just-above the flag on M2
    m2 = np.array([r['m2'] for r in sub])
    delta = max(hw / 3, sig if not math.isnan(sig) else hw / 3)
    below = np.sum((m2 >= flag - delta) & (m2 < flag)); above = np.sum((m2 >= flag) & (m2 < flag + delta))
    dens = below / above if above > 0 else float('nan')

    F_flag = '⚠' if F < 10 else ' '
    bal_flag = '⚠' if abs(ba[0]) > 3 else ' '
    print(f'  {name:40s} n={len(sub):6d} tx={d.mean():.3f} sig={sig:.3g}({100*sig/max(abs(flag),1e-9):.1f}%) | '
          f'NAIVE crude={naive_crude[0]:+.4f} adj={naive_adj[0]:+.4f} | '
          f'FS={fs:+.3f}(F{F:4.0f}){F_flag}| ITT={rf:+.5f}({srf[0]:.5f}) | LATE={late:+.3f} AR[{arlo:+.2f},{arhi:+.2f}] | '
          f'balAge={ba[0]:+.2f}{bal_flag}| densB/A={dens:.2f}')

def main():
    print('=== HiRID EXTERNAL REPLICATION: assay-noise IV / flag-ITT ===')
    print('headline=flag-ITT(mortality); LATE=implied (ITT/FS) with Anderson-Rubin CI; balAge~0 => exogenous\n')
    pat = load_patient()
    if not pat:
        print('hirid_general.csv missing/empty — SKIP all trials (need patientid, admissiontime, age, sex, discharge_status)')
        return
    for (name, key, tx_class, flag, direction, hw) in CONFIG:
        run_trial(name, key, tx_class, flag, direction, hw, pat)
    print('\nDONE. Interpret: strong FS + balAge~0 + precise ITT => usable; weak FS or balAge!=0 => flag.')
    print('External-replication read: directional agreement with the MIMIC-IV portfolio_run.py /')
    print('eICU eicu_run.py results on flag-ITT sign/magnitude is the confirmatory signal; NAIVE vs')
    print('flag-ITT divergence should replicate too (same confounding-by-indication mechanism, site-agnostic).')
    print('\nCAVEAT: lab/pharma ids above are compiled from PUBLIC sources (ricu + HIRID-ICU-Benchmark) with')
    print('no dataset access -- re-verify against hirid_variable_reference.csv before trusting results.')

if __name__ == '__main__':
    main()
