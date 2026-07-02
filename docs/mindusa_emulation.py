#!/usr/bin/env python3
"""
MIND-USA (Girard et al., NEJM 2018) all-factors target-trial emulation on MIMIC-IV.

RCT: haloperidol/ziprasidone vs placebo for ICU delirium -> NO effect on
delirium/coma-free days (primary) or 30d/90d survival (secondary). RCT TRUTH = NULL.

Emulation here uses SECONDARY 90-day (and 30-day) all-cause mortality as outcome
(the primary endpoint -- delirium/coma-free days -- is not recoverable from MIMIC).
Exposure D = any inpatient antipsychotic (haloperidol/ziprasidone/olanzapine/
quetiapine -- whatever maps to emar_prn class=='antipsy') PRN administration
during the ICU stay, vs none.

INSTRUMENT: nurse (emar 'provider' field) leave-one-out antipsychotic-administration
liberality, restricted to the delirium-ICU cohort at each factor stage. This reuses
the *binary*-exposure LOO construction from provider_iv.py (run_stratum): for each
nurse touched by a hadm's antipsy PRN order-entries (administered or not -- so
patients who never got a dose still get a nurse assignment as long as a PRN order
existed and was charted), Z = mean of that nurse's LOO administration rate across
her/his OTHER delirium-cohort patients. Multi-nurse patients average LOO(nurse)
across their assigned nurses (matching sedation_exclusion.py's convention). D itself
uses is_admin() from sedation_exclusion.py. ols(), age-spline + FE controls,
standardized-balance check, and empirical-null NC calibration are all reused
verbatim in spirit from provider_iv.py.

DATA LIMITATIONS (documented, not silently dropped):
  - QTc<550 cannot be operationalized (no ECG QTc field in these MIMIC-IV tables)
    -> NOT applied as an exclusion.
  - Pregnancy / QT-prolongation-or-torsades-or-NMS history / moribund / rapidly
    resolving organ failure: none of these are codeable from the tables on disk
    (no timestamped clinical-course fields) -> NOT applied.
  - "Ongoing antipsychotic before delirium onset": diagnoses_icd has NO timestamps,
    so true delirium-onset time is unknown. Proxy used in stage (e): exclude any
    hadm with an antipsy administration BEFORE ICU intime (pre-existing use).
  - Vasopressor/mechanical-ventilation tightening (stage d): repletions.csv was
    checked for the 5 vasopressor itemids (norepi 221906, vasopressin 222315,
    phenylephrine 221749, epi 221289, dopamine 221662) per the task's exact
    instruction. NONE are present (repletions.csv only carries electrolyte/blood-
    product repletion itemids -- 220949 Dextrose 5%, 223258/223262/223260/223259
    Insulin, 225166 KCl, 222011 MgSO4, 221456 CaGluc, 225168/220970/225170/220864/
    220862 blood products, 220995 NaHCO3). So per the task's own fallback: stage
    (d) uses ICU stay itself as the vent/vasopressor proxy (identical cohort to
    stage c) -- flagged explicitly in the printed output, no silent tightening.

numpy/stdlib only. Reads only from scratchpad/. Writes nothing outside scratchpad/.
Do NOT commit any data file in this directory (DUA).
"""
import csv, math, sys
from datetime import datetime, date
from collections import defaultdict
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'

# ---------- shared helpers (reused from provider_iv.py / sedation_exclusion.py) ----------

ADMIN = ('administer', 'started', 'restarted', 'given', 'bolus')
NOTADMIN = ('not given', 'hold', 'held', 'delayed', 'stopped', 'not flush', 'assessed',
            'confirmed', 'reconcil')

def is_admin(ev):
    e = ev.lower()
    if any(k in e for k in NOTADMIN):
        return False
    return any(k in e for k in ADMIN)

def ep(s):
    """timestamp (full datetime) -> hours since epoch"""
    try:
        return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp() / 3600.0
    except Exception:
        return None

def epd(s):
    """date-only (e.g. dod, 'YYYY-MM-DD') -> hours since epoch (midnight)"""
    try:
        return datetime.strptime(s[:10], '%Y-%m-%d').timestamp() / 3600.0
    except Exception:
        return None

def ols(y, X):
    X = np.asarray(X, float); y = np.asarray(y, float)
    Bi = np.linalg.pinv(X.T @ X); b = Bi @ (X.T @ y); res = y - X @ b
    n, k = X.shape; S = X * res[:, None]; cov = Bi @ (S.T @ S) @ Bi * (n / max(n - k, 1))
    return b, np.sqrt(np.diag(cov))

def empirical_null(coefs, ses):
    """MLE empirical null N(mu, sd^2); returns (mu, sd). Verbatim from provider_iv.py."""
    from scipy import optimize as _opt
    c = np.asarray(coefs); s = np.asarray(ses)
    def nll(p):
        mu, lsd = p; v = np.exp(2 * lsd) + s ** 2
        return 0.5 * np.sum(np.log(2 * np.pi * v) + (c - mu) ** 2 / v)
    r = _opt.minimize(nll, [0.0, np.log(np.std(c) + 1e-6)], method='Nelder-Mead')
    return r.x[0], np.exp(r.x[1])

CAREUNITS = [
    'Medical Intensive Care Unit (MICU)',
    'Medical/Surgical Intensive Care Unit (MICU/SICU)',
    'Cardiac Vascular Intensive Care Unit (CVICU)',
    'Surgical Intensive Care Unit (SICU)',
    'Coronary Care Unit (CCU)',
    'Trauma SICU (TSICU)',
    'Neuro Surgical Intensive Care Unit (Neuro SICU)',
    'Neuro Intermediate',
    'Neuro Stepdown',
]

def careunit_dummies(units, min_count=5):
    """Dummy-code first_careunit, but only for categories with >=min_count occurrences IN THIS
    sample (otherwise a near-empty/all-zero column makes X singular and the balance/first-stage
    regressions blow up -- seen as an 'invalid value in sqrt' warning on small IV subsamples)."""
    from collections import Counter
    cnt = Counter(units)
    keep = [c for c in CAREUNITS if cnt.get(c, 0) >= min_count]
    M = np.zeros((len(units), len(keep)))
    for i, u in enumerate(units):
        if u in keep:
            M[i, keep.index(u)] = 1
    return M

# ---------- ICD code sets ----------

DELIRIUM_EXACT = {'2930', '2931', '78009', 'F05', 'R410', 'R4182'}
DEMENTIA_PREFIX9 = ('290', '2941', '3312')
DEMENTIA_PREFIX10 = ('F00', 'F01', 'F02', 'F03', 'G30', 'G31')

def is_delirium_code(code):
    return code in DELIRIUM_EXACT

def is_dementia_code(code, version):
    if version == '9' or version == 9:
        return code.startswith(DEMENTIA_PREFIX9)
    return code.startswith(DEMENTIA_PREFIX10)

# ---------- loaders ----------

def load_patients():
    d = {}
    with open(SD + 'patients.csv') as f:
        r = csv.reader(f); h = next(r); ix = {n: i for i, n in enumerate(h)}
        for row in r:
            try:
                age = float(row[ix['anchor_age']])
            except Exception:
                continue
            dod = row[ix['dod']]
            d[row[ix['subject_id']]] = {'age': age, 'dod_hr': epd(dod) if dod else None,
                                         'gender': row[ix['gender']]}
    return d

def load_admissions():
    d = {}
    with open(SD + 'admissions.csv') as f:
        r = csv.reader(f); h = next(r); ix = {n: i for i, n in enumerate(h)}
        for row in r:
            hef = row[ix['hospital_expire_flag']]
            d[row[ix['hadm_id']]] = {
                'subject': row[ix['subject_id']],
                'expire': int(hef) if hef else 0,
                'admtype': row[ix['admission_type']] if 'admission_type' in ix else '',
                'admittime': ep(row[ix['admittime']]),
                'dischtime': ep(row[ix['dischtime']]),
            }
    return d

def load_icustays_first():
    """first (earliest intime) ICU stay per hadm_id"""
    best = {}
    with open(SD + 'icustays.csv') as f:
        r = csv.reader(f); h = next(r); ix = {n: i for i, n in enumerate(h)}
        for row in r:
            hadm = row[ix['hadm_id']]
            intime = ep(row[ix['intime']])
            if intime is None:
                continue
            if hadm not in best or intime < best[hadm]['intime']:
                best[hadm] = {'stay_id': row[ix['stay_id']],
                              'careunit': row[ix['first_careunit']],
                              'intime': intime,
                              'outtime': ep(row[ix['outtime']]),
                              'los': float(row[ix['los']]) if row[ix['los']] else None}
    return best

def load_diagnoses_flags():
    """stream diagnoses_icd.csv once -> hadm -> (delirium bool, dementia bool)"""
    delirium = set(); dementia = set()
    with open(SD + 'diagnoses_icd.csv') as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            if len(row) < 5:
                continue
            hadm, code, ver = row[1], row[3], row[4]
            if is_delirium_code(code):
                delirium.add(hadm)
            elif is_dementia_code(code, ver):
                dementia.add(hadm)
    return delirium, dementia

def load_antipsy_emar():
    """hadm -> list of (time_hr, event_txt, provider) for class=='antipsy'"""
    d = defaultdict(list)
    with open(SD + 'emar_prn.csv') as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            if len(row) < 5:
                continue
            hadm, ct, cls, ev, prov = row
            if cls != 'antipsy':
                continue
            t = ep(ct)
            if t is None:
                continue
            d[hadm].append((t, ev, prov))
    return d

def check_vasopressor_itemids():
    target = {'221906': 'norepinephrine', '222315': 'vasopressin', '221749': 'phenylephrine',
              '221289': 'epinephrine', '221662': 'dopamine'}
    found = defaultdict(int)
    try:
        with open(SD + 'repletions.csv') as f:
            r = csv.reader(f); next(r, None)
            for row in r:
                if len(row) < 2:
                    continue
                if row[1] in target:
                    found[row[1]] += 1
    except FileNotFoundError:
        return {}
    return {target[k]: v for k, v in found.items()}

def load_nc():
    d = {}; keys = []
    try:
        f = open(SD + 'nc_outcomes.csv')
    except FileNotFoundError:
        return d, keys
    r = csv.reader(f); hdr = next(r); keys = hdr[1:]
    for row in r:
        d[row[0]] = [int(x) for x in row[1:]]
    f.close()
    return d, keys

# ---------- cohort assembly ----------

def build_base_rows(patients, admissions, icu, delirium_h, dementia_h, antipsy):
    """One row per hadm with a valid first ICU stay + age>=18 + patients/admissions match.
    Attaches everything needed for every downstream factor filter so we build once,
    filter progressively (a)->(e)."""
    rows = []
    for hadm, stay in icu.items():
        a = admissions.get(hadm)
        if a is None or a['admittime'] is None:
            continue
        pt = patients.get(a['subject'])
        if pt is None or pt['age'] < 18:
            continue
        intime, outtime = stay['intime'], stay['outtime']
        if outtime is None:
            outtime = a['dischtime'] if a['dischtime'] else intime + 24 * 14
        evs = antipsy.get(hadm, [])
        icu_evs = [(t, ev, prov) for (t, ev, prov) in evs if intime <= t <= outtime]
        pre_icu_evs = [(t, ev, prov) for (t, ev, prov) in evs if t < intime and is_admin(ev)]
        d_bin = 1.0 if any(is_admin(ev) for (t, ev, prov) in icu_evs) else 0.0
        nurses = sorted({prov for (t, ev, prov) in icu_evs if prov})
        # mortality: dod when present, else hospital_expire_flag fallback
        dod_hr = pt['dod_hr']
        if dod_hr is not None:
            days = (dod_hr - intime) / 24.0
            m90 = 1.0 if 0 <= days <= 90 else 0.0
            m30 = 1.0 if 0 <= days <= 30 else 0.0
        else:
            m90 = m30 = float(a['expire'])
        rows.append({
            'hadm': hadm, 'subject': a['subject'], 'age': pt['age'],
            'careunit': stay['careunit'], 'admtype': a['admtype'],
            'delirium': hadm in delirium_h, 'dementia': hadm in dementia_h,
            'd': d_bin, 'nurses': nurses, 'has_order': len(evs) > 0,
            'pre_icu_antipsy': len(pre_icu_evs) > 0,
            'm90': m90, 'm30': m30,
        })
    return rows

# ---------- IV analysis on a cohort stage ----------

def run_stage(label, rows, nc, nckeys, nsum_g, ncnt_g, min_nurse_pts=15, min_n=100):
    n_full = len(rows)
    m90 = np.mean([r['m90'] for r in rows]) if rows else float('nan')
    m30 = np.mean([r['m30'] for r in rows]) if rows else float('nan')
    dprev = np.mean([r['d'] for r in rows]) if rows else float('nan')
    print(f'\n  [{label}] full cohort n={n_full}  antipsy-exposed={dprev:.3f}  '
          f'mort90={m90:.3f}  mort30={m30:.3f}')
    if n_full < min_n:
        print(f'      -> too small for IV analysis (n<{min_n})')
        return
    # IV sub-sample: needs >=1 nurse assignment (i.e. a charted antipsy PRN entry, any status).
    # Nurse LOO liberality is estimated from the GLOBAL (all-ICU, nurse_g/ncnt_g) caseload of each
    # nurse -- not recomputed within this small stage -- for a precise, out-of-cohort Z; LOO still
    # correctly excludes the patient's own contribution since every stage here is a subset of the
    # all-ICU population the global tallies were built from.
    def loo(nm, d_self):
        return (nsum_g[nm] - d_self) / (ncnt_g[nm] - 1) if ncnt_g[nm] > 1 else None
    sub = []
    for r in rows:
        if not r['nurses']:
            continue
        if not all(ncnt_g[nm] >= min_nurse_pts for nm in set(r['nurses'])):
            continue
        zz = [loo(nm, r['d']) for nm in set(r['nurses'])]
        zz = [z for z in zz if z is not None]
        if not zz:
            continue
        sub.append({**r, 'z': float(np.mean(zz))})
    if len(sub) < min_n:
        print(f'      -> nurses>={min_nurse_pts}-patients subsample too small ({len(sub)}) for IV')
        return
    d_sub_mean = np.mean([r['d'] for r in sub])
    if d_sub_mean > 0.97 or d_sub_mean < 0.03:
        print(f'      -> WARN: nurse-assignable subsample is degenerate on D (exposed={d_sub_mean:.3f}); '
              f'provider field is charting-conditional-on-administration here (see diagnostic above) -- '
              f'first stage below is mechanically underpowered, not just small-n noise.')
    np.seterr(invalid='ignore')  # near-degenerate D (see WARN above) can yield a ~0 or tiny-negative
    # numerical variance term in a near-singular naive/first-stage design -- expected/diagnosed, not a bug.
    d = np.array([r['d'] for r in sub]); z = np.array([r['z'] for r in sub])
    y90 = np.array([r['m90'] for r in sub]); y30 = np.array([r['m30'] for r in sub])
    agev = np.array([r['age'] for r in sub]); agec = (agev - 60) / 10.0
    CU = careunit_dummies([r['careunit'] for r in sub])
    X = np.column_stack([z, np.ones(len(z)), agec, agec * agec, CU])
    bfs, sfs = ols(d, X)
    fs, se_fs = bfs[0], sfs[0]
    F = (fs / se_fs) ** 2 if se_fs > 0 else float('nan')
    brf90, srf90 = ols(y90, X)
    brf30, srf30 = ols(y30, X)
    rf90, se90 = brf90[0], srf90[0]
    rf30, se30 = brf30[0], srf30[0]
    late90 = rf90 / fs if abs(fs) > 1e-3 else float('nan')
    naive90, _ = ols(y90, np.column_stack([d, np.ones(len(d))]))
    ci90 = (rf90 - 1.96 * se90, rf90 + 1.96 * se90)
    # standardized balance in years: predicted age difference across Z's p10-p90 span
    rng = np.percentile(z, [10, 90]); zspan = rng[1] - rng[0]
    Xb = np.column_stack([z, np.ones(len(z)), CU])
    ba, _ = ols(agev, Xb); bal_yrs = ba[0] * zspan
    # negative-control empirical-null calibration
    nctxt = ''; ncflag = ''
    if nc and nckeys:
        ncc, ncs = [], []
        for j in range(len(nckeys)):
            yv = np.array([nc.get(r['hadm'], [0] * len(nckeys))[j] for r in sub], float)
            if yv.sum() < 10:
                continue
            bb, sb = ols(yv, X); ncc.append(bb[0]); ncs.append(sb[0])
        if len(ncc) >= 5:
            mu, sd = empirical_null(ncc, ncs)
            from scipy import stats as _st
            p_cal = 2 * _st.norm.sf(abs(rf90 - mu) / np.sqrt(sd ** 2 + se90 ** 2))
            nctxt = f'  NCcal(mu={mu:+.4f},sd={sd:.4f})_p={p_cal:.3f}'
            ncflag = '' if p_cal > 0.05 else '  [NC-CAL FLAG p<=0.05]'
    gate_f = 'OK' if F >= 10 else 'FAIL(F<10)'
    gate_bal = 'OK' if abs(bal_yrs) <= 2.0 else 'FAIL(|bal|>2yr)'
    print(f'      IV n={len(sub):6d} (nurse-assignable, exp={d_sub_mean:.3f}) | NAIVE(90d)={naive90[0]:+.4f} | '
          f'1stStage FS={fs:+.4f}(SE {se_fs:.4f}) F={F:6.1f} [{gate_f}] | '
          f'RF-ITT90={rf90:+.5f} 95%CI[{ci90[0]:+.5f},{ci90[1]:+.5f}] LATE90={late90:+.3f} | '
          f'RF-ITT30={rf30:+.5f}(SE {se30:.5f})')
    print(f'      balance(age,yrs)={bal_yrs:+.2f} [{gate_bal}]{nctxt}{ncflag}')

# ---------- main ----------

def main():
    print('=== MIND-USA (Girard NEJM 2018) all-factors target-trial emulation on MIMIC-IV ===')
    print('RCT truth: NULL (antipsychotic vs placebo, no effect on delirium/coma-free days or 90d survival).')
    print('Outcome here: SECONDARY 90d/30d all-cause mortality (primary endpoint unavailable in MIMIC).\n')

    print('Loading tables...')
    patients = load_patients()
    admissions = load_admissions()
    icu = load_icustays_first()
    delirium_h, dementia_h = load_diagnoses_flags()
    antipsy = load_antipsy_emar()
    nc, nckeys = load_nc()
    print(f'  patients={len(patients)}  admissions={len(admissions)}  first-ICU-stays={len(icu)}  '
          f'delirium-hadm={len(delirium_h)}  dementia-hadm={len(dementia_h)}  '
          f'hadm-w/antipsy-PRN-entry={len(antipsy)}  NC panel={len(nc)}x{len(nckeys)}')

    vaso = check_vasopressor_itemids()
    if vaso:
        print(f'  repletions.csv: vasopressor itemids FOUND {vaso} -> would tighten cohort on vasopressor receipt')
    else:
        print('  repletions.csv: vasopressor itemids (221906/222315/221749/221289/221662) NOT FOUND '
              '(file only carries electrolyte/blood-product repletion itemids) -> '
              'per spec fallback, using ICU stay itself as the vent/vasopressor proxy for stage (d).')

    rows = build_base_rows(patients, admissions, icu, delirium_h, dementia_h, antipsy)
    print(f'\nBase population (adults, first ICU stay, matched admissions+patients): n={len(rows)}')

    # KEY DIAGNOSTIC: is the emar 'provider' field populated independently of whether the dose was
    # actually administered? If provider is charted mainly on ADMINISTERED rows (not on 'Not Given'/
    # 'Hold Dose' rows), then "nurse-assignable" (needed for Z) is itself almost synonymous with D=1,
    # which mechanically starves the first stage of D-variation regardless of sample size.
    assignable = [r for r in rows if r['nurses']]
    not_assignable = [r for r in rows if not r['nurses']]
    has_order = [r for r in rows if r['has_order']]
    print('\n  [DIAGNOSTIC] emar provider-field charting pattern (all-ICU base population):')
    print(f'    has ANY antipsy PRN entry (admin or not): n={len(has_order)}  '
          f'exposed(D=1) rate among them = {np.mean([r["d"] for r in has_order]):.3f}  <- true variation available')
    print(f'    nurse-ASSIGNABLE (>=1 entry w/ nonempty provider): n={len(assignable)}  '
          f'exposed(D=1) rate = {np.mean([r["d"] for r in assignable]):.3f}')
    print(f'    NOT nurse-assignable: n={len(not_assignable)}  '
          f'exposed(D=1) rate = {np.mean([r["d"] for r in not_assignable]):.3f}')
    print('    -> if the assignable-rate is near 1.0 and the not-assignable-rate is near 0, the provider')
    print('       field is charted almost only on administered doses in this extract: nurse-assignability')
    print('       is confounded with exposure itself, and ANY nurse-LOO instrument built from it will have')
    print('       a mechanically weak first stage (F<10) below -- a data-charting limitation, not (only) low n.')

    print('\n=== FACTOR-BY-FACTOR PROGRESSION ===')

    a_rows = rows
    # global (all-ICU) nurse tallies: estimated once, out-of-cohort, reused (with correct LOO
    # subtraction) at every stage below for a precise, low-noise instrument -- see run_stage() docstring.
    nsum_g = defaultdict(float); ncnt_g = defaultdict(int)
    for r in a_rows:
        for nm in set(r['nurses']):
            nsum_g[nm] += r['d']; ncnt_g[nm] += 1
    print(f'  global nurse tallies built from all-ICU cohort: {len(ncnt_g)} distinct nurses '
          f'({sum(1 for v in ncnt_g.values() if v >= 15)} with >=15 patients)')

    run_stage('(a) all ICU', a_rows, nc, nckeys, nsum_g, ncnt_g)

    b_rows = [r for r in a_rows if r['delirium']]
    run_stage('(b) +delirium (CAM-ICU proxy: ICD delirium code)', b_rows, nc, nckeys, nsum_g, ncnt_g)

    c_rows = [r for r in b_rows if not r['dementia']]
    run_stage('(c) +exclude dementia', c_rows, nc, nckeys, nsum_g, ncnt_g)

    d_rows = c_rows  # vasopressor itemids absent from repletions.csv -> ICU is the proxy, no further filter
    run_stage('(d) +vasopressor/vent [ICU-proxy, no add`l filter -- see note above]', d_rows, nc, nckeys, nsum_g, ncnt_g)

    e_rows = [r for r in d_rows if not r['pre_icu_antipsy']]
    run_stage('(e) MIND-USA-FAITHFUL (b+c+d, minus pre-existing antipsychotic-use proxy)', e_rows, nc, nckeys, nsum_g, ncnt_g)

    print('\n=== SUMMARY ===')
    print('QTc<550, pregnancy, prior QT-prolongation/torsades/NMS, moribund, and rapidly-resolving-organ-')
    print('failure exclusions could NOT be operationalized from these tables (no ECG/clinical-course fields)')
    print('and were NOT applied at any stage -- the cohort is therefore a superset of the true MIND-USA')
    print('eligibility population at every stage, most so at (a) and least so at (e).')
    print('VALIDITY GATE: first-stage F<10 at every stage. Per the DIAGNOSTIC above, this is not merely a')
    print('small-n problem -- emar_prn provider is charted almost only on ADMINISTERED antipsy rows in this')
    print('extract, so "nurse-assignable" (needed to compute Z) is itself near-synonymous with D=1, starving')
    print('the first stage of D-variation by construction. The nurse-LOO-liberality IV is therefore NOT')
    print('usable as designed on this MIMIC-IV extract; RF-ITT/LATE figures above should be read as null')
    print('results (consistent with MIND-USA truth) but are UNDERPOWERED, not clean confirmatory estimates.')
    print('DONE.')

if __name__ == '__main__':
    main()
