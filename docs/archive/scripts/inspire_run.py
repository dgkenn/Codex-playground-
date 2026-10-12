#!/usr/bin/env python3
"""
INSPIRE v1.3 (Seoul National University, PhysioNet) SECOND EXTERNAL REPLICATION of the
assay-noise IV / flag-ITT engine (mirrors /home/user/Codex-playground-/docs/portfolio_run.py [MIMIC-IV] and
/home/user/Codex-playground-/docs/eicu_run.py [eICU-CRD]) for the lab-flag-triggered benchmark
de-implementation cases that INSPIRE's schema can support:

  RBC transfusion      @ Hgb < 7        (TRICC/TRISS validation)   -- runnable (vitals.csv 'rbc')
  Platelet transfusion @ platelets < 10                            -- runnable (vitals.csv 'pc')
  Bicarbonate          @ HCO3 < 15      (acidosis correction)      -- runnable (medications.csv
                                                                       'sodium bicarbonate')
  Insulin              @ glucose > 180  (NICE-SUGAR validation)    -- runnable (medications.csv
                                                                       'insulin'*)
  Potassium repletion  @ K < 3.5        (secondary/context, as in eICU/MIMIC engines)
                                                                    -- runnable (medications.csv
                                                                       'potassium chloride')
  Magnesium repletion  @ Mg < 2.0                                  -- NOT RUNNABLE: INSPIRE
                                                                       labs.csv has NO 'magnesium'
                                                                       item_name (confirmed absent
                                                                       from the fixed vocabulary in
                                                                       schema.csv/parameters.csv);
                                                                       loader below SKIPs it.

Design (identical to the MIMIC/eICU engines, restated for INSPIRE's second-resolution clock):
  - M1, M2 = first two pre-treatment lab draws (labs.csv chart_time, SECONDS from hospital
    admission per operations.csv admission_time==0 anchor; converted to hours by /3600 here)
  - instrument Z = 1(M2 crosses the flag in the de-implementation direction)
  - severity control = midpoint (M1+M2)/2, entered as a local-linear (2nd-order) control
    function of (mid - flag), i.e. RDD-style bandwidth regression
  - D = 1(treatment of the matching class occurs within 24h of M2)
  - primary outcome Y = in-hospital mortality (operations.csv inhosp_death_time non-empty;
    NOTE: NOT allcause_death_time, which also counts post-discharge deaths and would conflate a
    longer, less comparable window with the MIMIC/eICU hospital_expire_flag outcome)
  - reports: n, noise sigma, first-stage F, flag-ITT (headline), implied-LATE with
    Anderson-Rubin CI, covariate balance (age), M2 density/heaping (McCrary-style), and the
    NAIVE (confounded) D->mortality contrast (crude + severity-adjusted) for comparison.

Inputs (produced by inspire_stream_lab.py / inspire_stream_tx.py from the raw INSPIRE plain CSVs
-- NOTE: INSPIRE tables are NOT gzipped, unlike MIMIC/eICU):
  inspire_lab_hb.csv, inspire_lab_plt.csv, inspire_lab_hco3.csv, inspire_lab_glu.csv,
  inspire_lab_k.csv                                            (labs.csv streams)
  inspire_tx.csv                                               (vitals.csv 'rbc'/'pc' blood
                                                                 products + medications.csv
                                                                 insulin/KCl/NaHCO3 streams,
                                                                 unioned by inspire_stream_tx.py)
  operations.csv (raw INSPIRE operations.csv, NOT renamed: op_id, subject_id, ..., age,
                  inhosp_death_time)

Key schema differences from MIMIC/eICU handled here:
  - chart_time / *_time fields are RELATIVE TIME IN SECONDS from hospital admission (verified:
    admission_time==0 for ~96% of ops; interpreting other *_time fields as minutes gives
    multi-year "hospital stays", which is absurd -- seconds gives hours-to-days, which is sane).
  - Keyed by subject_id (labs.csv/medications.csv/vitals.csv have no hadm_id/op_id column for
    labs/medications) rather than hadm_id (MIMIC) or patientunitstayid (eICU). A small fraction
    of subjects (~4% in a 4k-row operations.csv sample) have >1 hospital admission; we take the
    FIRST operations.csv row per subject_id for age/mortality, which can blur admission windows
    for repeat patients -- a known limitation, documented rather than silently ignored.
  - Missing input files => SKIP, no crash (same contract as eicu_run.py).
"""
import csv, math
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'

# (name, lab_csv_key, tx_class, flag, direction '<'|'>', bandwidth)
# Units match INSPIRE labs.csv / parameters.csv conventions: Hgb g/dL, platelets /nL (==K/uL),
# HCO3 mmol/L, glucose mg/dL, potassium mmol/L -- SAME units/flags as portfolio_run.py/eicu_run.py.
CONFIG = [
    ('RBC transfusion (Hgb<7)',        'hb',   'rbc',     7.0,  '<', 0.60),
    ('Platelet transfusion (<10)',     'plt',  'plt',     10.0, '<', 5.0),
    ('Bicarbonate (acidosis, <15)',    'hco3', 'hco3',    15.0, '<', 3.0),
    ('Insulin (glucose>180)',          'glu',  'insulin', 180,  '>', 25),
    ('Potassium repletion (<3.5)',     'k',    'k',       3.5,  '<', 0.25),  # secondary/context
    # Magnesium repletion: NOT included -- no 'magnesium' item_name exists in INSPIRE labs.csv
    # (verified absent from schema.csv/parameters.csv fixed vocabulary); see module docstring.
]

def load_labseq(key):
    """chart_time in seconds -> convert to hours for readability/consistency with MIMIC/eICU engines."""
    d = {}
    try:
        f = open(SD + f'inspire_lab_{key}.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 4:
            continue
        sid, ct, _name, vn = row[0], row[1], row[2], row[3]
        if not sid or not ct or not vn:
            continue
        try:
            t = float(ct) / 3600.0  # seconds -> hours
            v = float(vn)
        except ValueError:
            continue
        d.setdefault(sid, []).append((t, v))
    f.close()
    for k in d:
        d[k].sort()
    return d

def load_tx(cls):
    d = {}
    try:
        f = open(SD + 'inspire_tx.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 3:
            continue
        sid, ct, c = row[0], row[1], row[2]
        if c != cls or not sid or not ct:
            continue
        try:
            t = float(ct) / 3600.0  # seconds -> hours
        except ValueError:
            continue
        d.setdefault(sid, []).append(t)
    f.close()
    for k in d:
        d[k].sort()
    return d

def load_operations():
    """raw INSPIRE operations.csv: subject_id, age, inhosp_death_time (non-empty => in-hospital
    death). Takes the FIRST row per subject_id (see module docstring re: repeat admissions).
    Returns dict keyed by subject_id: {'age':float, 'expire':0/1}.
    """
    d = {}
    try:
        f = open(SD + 'operations.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    hdr = next(r)
    # INSPIRE csv files are UTF-8-with-BOM (raw bytes start EF BB BF); text mode does not strip
    # it, so the first header cell would otherwise read as '﻿subject_id'.
    hdr = [h.lstrip('﻿') for h in hdr]
    idx = {n: i for i, n in enumerate(hdr)}
    i_sid = idx['subject_id']
    i_age = idx['age']
    i_death = idx['inhosp_death_time']
    for row in r:
        if len(row) < len(hdr):
            continue
        sid = row[i_sid]
        if sid in d:
            continue  # keep first occurrence only
        age_raw = row[i_age].strip() if i_age < len(row) else ''
        try:
            age = float(age_raw)
        except ValueError:
            age = float('nan')
        death_raw = row[i_death].strip() if i_death < len(row) else ''
        expire = 1 if death_raw != '' else 0
        d[sid] = {'age': age, 'expire': expire}
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

def run_trial(name, key, tx_class, flag, direction, hw, ops):
    seqs = load_labseq(key)
    if not seqs:
        print(f'  {name:28s}: inspire_lab_{key}.csv empty/missing — SKIP'); return
    tx = load_tx(tx_class)
    if not tx:
        print(f'  {name:28s}: inspire_tx.csv has no "{tx_class}" rows (or file missing) — SKIP'); return

    # noise sigma: adjacent pre-treatment draws within 12h, no intervening treatment
    diffs = []
    for sid, seq in seqs.items():
        rt = tx.get(sid, [])
        for i in range(len(seq) - 1):
            (t1, v1), (t2, v2) = seq[i], seq[i + 1]
            if 0 < t2 - t1 <= 12 and not any(t1 < r <= t2 for r in rt):
                diffs.append(v2 - v1)
    sig = np.std(diffs) / math.sqrt(2) if len(diffs) > 100 else float('nan')

    # single-decision cohort: M1, M2 = first two pre-treatment draws
    rows = []
    cross = (lambda v: v < flag) if direction == '<' else (lambda v: v > flag)
    for sid, seq in seqs.items():
        if sid not in ops:
            continue
        rt = tx.get(sid, []); first = rt[0] if rt else float('inf')
        pre = [(t, v) for (t, v) in seq if t < first]
        if len(pre) < 2:
            continue
        (t1, m1), (t2, m2) = pre[0], pre[1]
        rows.append({
            'mid': (m1 + m2) / 2, 'm2': m2,
            'z': 1.0 if cross(m2) else 0.0,
            'd': 1.0 if any(t2 <= r <= t2 + 24 for r in rt) else 0.0,
            'y': float(ops[sid]['expire']),
            'age': ops[sid]['age'],
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
    print('=== INSPIRE v1.3 EXTERNAL REPLICATION #2: assay-noise IV / flag-ITT (benchmark trials) ===')
    print('headline=flag-ITT(mortality); LATE=implied (ITT/FS) with Anderson-Rubin CI; balAge~0 => exogenous\n')
    ops = load_operations()
    if not ops:
        print('operations.csv missing/empty — SKIP all trials (need subject_id, age, inhosp_death_time)')
        return
    for (name, key, tx_class, flag, direction, hw) in CONFIG:
        run_trial(name, key, tx_class, flag, direction, hw, ops)
    print('\nDONE. Interpret: strong FS + balAge~0 + precise ITT => usable; weak FS or balAge!=0 => flag.')
    print('External-replication read: directional agreement with the MIMIC-IV portfolio_run.py and')
    print('eICU-CRD eicu_run.py results on flag-ITT sign/magnitude is the confirmatory signal;')
    print('NAIVE vs flag-ITT divergence should replicate too (same confounding-by-indication')
    print('mechanism is site-agnostic). Magnesium repletion is NOT tested here (no lab item in INSPIRE).')

if __name__ == '__main__':
    main()
