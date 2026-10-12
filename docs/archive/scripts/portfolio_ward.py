#!/usr/bin/env python3
"""
WARD-INCLUSIVE assay-noise IV / flag-ITT engine for electrolyte repletion, stratified WARD vs ICU.

Mirrors docs/portfolio_run.py's design (first two pre-treatment draws M1,M2; instrument
Z=1(M2 crosses flag); control=midpoint; D=treatment within 24h of M2; headline=flag-ITT with
Anderson-Rubin CI; naive crude+adjusted D->mortality contrast) but sources TREATMENT from
PRESCRIPTIONS (rx_elyte.csv, built by stream_rx_elyte.py) instead of inputevents/repletions.csv.
inputevents/chartevents are ICU-only; prescriptions/labevents/admissions are HOSPITAL-WIDE
(ward+ICU) — so this is the first version of the design that can see floor-level repletion,
which is the highest-scale reflexive-treatment-of-mild-derangement target (most patient-time in
a hospital is ward, not ICU).

Each single-decision (M1,M2)->treat-or-not observation is classified WARD or ICU using
ward_classify.is_icu(hadm, epoch_hours_of_M2) — i.e. the careunit the patient was physically in
at the moment the triggering lab (M2) resulted, which is the right timepoint for "was this a
floor-nurse/floor-provider decision or an ICU one." Results are reported separately for WARD,
ICU, and OVERALL (pooled) strata; WARD is the headline because that's the de-implementation
target with the larger population and, per the design brief, the case unaddressed by the
ICU-only inputevents-sourced engine.

Guards: any missing input file (rx_elyte.csv, lab_mg.csv/lab_k.csv, admissions.csv,
transfers.csv) causes that trial (or the whole run) to SKIP with a message, not a crash.
"""
import csv, math
from datetime import datetime
import numpy as np

from ward_classify import load_transfers, is_icu

SD = '/home/user/Codex-playground-/scratchpad/'

# (name, lab_csv_key, rx classes, flag, direction '<'|'>', bandwidth)
CONFIG = [
    ('Mg repletion (ward-incl)', 'mg', {'mg_repl'}, 2.0, '<', 0.15),
    ('K repletion (ward-incl)',  'k',  {'k_repl'},  3.5, '<', 0.25),
]


def ep(s):
    try:
        return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp() / 3600.0
    except Exception:
        return None


def load_labseq(key):
    d = {}
    try:
        f = open(SD + f'lab_{key}.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f); next(r, None)
    for row in r:
        if len(row) < 3:
            continue
        hadm, ct, vn = row[0], row[1], row[2]
        t = ep(ct)
        if t is None or not vn or not hadm:
            continue
        try:
            v = float(vn)
        except ValueError:
            continue
        d.setdefault(hadm, []).append((t, v))
    f.close()
    for k in d:
        d[k].sort()
    return d


def load_rx(classes):
    """Load rx_elyte.csv (built by stream_rx_elyte.py from prescriptions.csv.gz)."""
    d = {}
    try:
        f = open(SD + 'rx_elyte.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f); next(r, None)
    for row in r:
        if len(row) < 3:
            continue
        hadm, cls, st = row[0], row[1], row[2]
        if cls not in classes:
            continue
        t = ep(st)
        if t is not None:
            d.setdefault(hadm, []).append(t)
    f.close()
    for k in d:
        d[k].sort()
    return d


def load_adm():
    d = {}
    try:
        f = open(SD + 'admissions.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f); hdr = next(r); idx = {n: i for i, n in enumerate(hdr)}
    for row in r:
        adm = ep(row[idx['admittime']]); dis = ep(row[idx['dischtime']])
        d[row[idx['hadm_id']]] = {
            'subject': row[idx['subject_id']],
            'expire': int(row[idx['hospital_expire_flag']]) if row[idx['hospital_expire_flag']] else 0,
            'los': (dis - adm) / 24.0 if (adm and dis) else None,
        }
    f.close()
    return d


def load_age():
    d = {}
    try:
        f = open(SD + 'patients.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f); hdr = next(r); idx = {n: i for i, n in enumerate(hdr)}
    for row in r:
        try:
            d[row[idx['subject_id']]] = float(row[idx['anchor_age']])
        except Exception:
            pass
    f.close()
    return d


def load_gender():
    d = {}
    try:
        f = open(SD + 'patients.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f); hdr = next(r); idx = {n: i for i, n in enumerate(hdr)}
    gi = idx.get('gender', -1)
    for row in r:
        if gi >= 0:
            d[row[idx['subject_id']]] = row[gi]
    f.close()
    return d

def recent_before(series, t, maxage=168.0):
    """most recent (t_i, v_i) with t_i <= t within maxage hours; series sorted by time."""
    best = None
    for (ti, vi) in series:
        if ti <= t and (t - ti) <= maxage:
            best = vi
        elif ti > t:
            break
    return best

def egfr_ckdepi(scr, age, female):
    """CKD-EPI 2021 race-free eGFR from serum creatinine (mg/dL), age, sex."""
    if scr is None or scr <= 0 or age is None:
        return None
    k = 0.7 if female else 0.9
    a = -0.241 if female else -0.302
    e = 142 * (min(scr / k, 1) ** a) * (max(scr / k, 1) ** -1.200) * (0.9938 ** age)
    if female:
        e *= 1.012
    return e


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


def build_cohort(seqs, tx, adm, age, transfers, flag, direction, creat=None, bun=None, gender=None):
    """One row per hadm with >=2 pre-treatment draws; annotate stratum + pre-decision RENAL function."""
    creat = creat or {}; bun = bun or {}; gender = gender or {}
    cross = (lambda v: v < flag) if direction == '<' else (lambda v: v > flag)
    rows = []
    for hadm, seq in seqs.items():
        if hadm not in adm:
            continue
        rt = tx.get(hadm, []); first = rt[0] if rt else float('inf')
        pre = [(t, v) for (t, v) in seq if t < first]
        if len(pre) < 2:
            continue
        (t1, m1), (t2, m2) = pre[0], pre[1]
        if (t2 - t1) > 24.0:   # tight inter-draw window (contemporaneous severity)
            continue
        icu_flag = is_icu(transfers, hadm, t2)
        stratum = 'ICU' if icu_flag is True else ('WARD' if icu_flag is False else 'UNKNOWN')
        subj = adm[hadm]['subject']; ag = age.get(subj, np.nan)
        cr = recent_before(creat.get(hadm, []), t2) if creat else None      # renal fn at decision time
        bn = recent_before(bun.get(hadm, []), t2) if bun else None
        female = (gender.get(subj, '') == 'F')
        egfr = egfr_ckdepi(cr, ag if not math.isnan(ag) else None, female)
        rows.append({
            'hadm': hadm, 'mid': (m1 + m2) / 2, 'm2': m2,
            'z': 1.0 if cross(m2) else 0.0,
            'd': 1.0 if any(t2 <= r <= t2 + 24 for r in rt) else 0.0,
            'y': float(adm[hadm]['expire']),
            'los': adm[hadm]['los'], 'age': ag, 'stratum': stratum,
            'cr': cr, 'bun': bn, 'egfr': egfr,
        })
    return rows


def noise_sigma(seqs, tx):
    diffs = []
    for hadm, seq in seqs.items():
        rt = tx.get(hadm, [])
        for i in range(len(seq) - 1):
            (t1, v1), (t2, v2) = seq[i], seq[i + 1]
            if 0 < t2 - t1 <= 12 and not any(t1 < r <= t2 for r in rt):
                diffs.append(v2 - v1)
    return np.std(diffs) / math.sqrt(2) if len(diffs) > 100 else float('nan')


def analyze_stratum(label, rows, flag, hw):
    """rows already restricted to a stratum (or 'overall'); runs the full battery, prints one line."""
    sub = [r for r in rows if abs(r['mid'] - flag) <= hw and not math.isnan(r['age'])]
    if len(sub) < 300:
        print(f'    [{label:7s}] n={len(sub)} in-band (too small; need >=300) — SKIP')
        return
    z = np.array([r['z'] for r in sub]); d = np.array([r['d'] for r in sub])
    y = np.array([r['y'] for r in sub]); C = cb([r['mid'] for r in sub], flag)
    agec = (np.array([r['age'] for r in sub]) - 60) / 10.0
    Xbase = np.column_stack([z, C])                       # midpoint-only: for the honest balance diagnostic
    Xadj = np.column_stack([z, C, agec, agec * agec])     # + age spline: age-adjusted robustness estimate
    # PRIMARY (pure noise-IV, unadjusted) first stage + reduced form
    bfs, sfs = ols(d, Xbase); brf, srf = ols(y, Xbase)
    fs, rf = bfs[0], brf[0]
    F = (fs / sfs[0]) ** 2 if sfs[0] > 0 else 0
    # balance diagnostic: age ~ z | midpoint (NOT controlling for age) — the real exogeneity test
    ba, sa = ols(np.array([r['age'] for r in sub]), Xbase)
    # age-ADJUSTED reduced form (robustness: does the near-null survive purging the age channel?)
    brf_adj, _ = ols(y, Xadj); rf_adj = brf_adj[0]
    # RENAL-ADJUSTED: add pre-decision eGFR + creatinine + BUN (renal fn drives Mg/K variability AND mortality)
    def col(keyname):
        v = np.array([r[keyname] if r[keyname] is not None else np.nan for r in sub], float)
        cov = float(np.mean([r[keyname] is not None for r in sub]))
        m = np.nanmedian(v) if np.any(~np.isnan(v)) else 0.0
        v[np.isnan(v)] = m
        return v, cov
    egfr_v, cov_egfr = col('egfr'); cr_v, _ = col('cr'); bun_v, cov_bun = col('bun')
    egfr_c = (egfr_v - 60) / 30.0; cr_c = (cr_v - 1.0); bun_c = (bun_v - 20) / 20.0
    Xren = np.column_stack([z, C, agec, agec * agec, egfr_c, cr_c, bun_c])
    brf_ren, _ = ols(y, Xren); rf_ren = brf_ren[0]
    # balance on RENAL function: creatinine ~ z | midpoint (does the noise-flag track renal severity?)
    bcr, _ = ols(cr_v, Xbase)
    ar = [b0 for b0 in np.arange(-1, 1.0001, 0.02)
          if abs((lambda bb, sb: bb[0] / sb[0] if sb[0] > 0 else 9)(*ols(y - b0 * d, Xbase))) < 1.96]
    arlo, arhi = (min(ar), max(ar)) if ar else (float('nan'), float('nan'))
    late = rf / fs if abs(fs) > 1e-3 else float('nan')

    # NAIVE association ('if run simply from this data'): crude + adjusted D->mortality, full (non-in-band) rows
    Dall = np.array([r['d'] for r in rows]); Yall = np.array([r['y'] for r in rows])
    Call = design_controls([r['mid'] for r in rows])
    naive_crude, _ = ols(Yall, np.column_stack([Dall, np.ones_like(Dall)]))
    naive_adj, _ = ols(Yall, np.column_stack([Dall, Call]))

    # LOS on the in-band cohort (secondary outcome)
    los_vals = [r['los'] for r in sub if r['los'] is not None]
    los_med = np.median(los_vals) if los_vals else float('nan')

    # McCrary-style density test at the flag
    m2 = np.array([r['m2'] for r in sub])
    sig = noise_sigma_cache.get('sig', float('nan'))
    delta = max(hw / 3, sig if not math.isnan(sig) else hw / 3)
    below = np.sum((m2 >= flag - delta) & (m2 < flag)); above = np.sum((m2 >= flag) & (m2 < flag + delta))
    dens = below / above if above > 0 else float('nan')

    F_flag = '⚠' if F < 10 else ' '
    bal_flag = '⚠' if abs(ba[0]) > 3 else ' '
    print(f'    [{label:7s}] n={len(sub):6d} tx={d.mean():.3f} | '
          f'NAIVE crude={naive_crude[0]:+.4f} adj={naive_adj[0]:+.4f} | '
          f'FS={fs:+.3f}(F{F:4.0f}){F_flag}| ITT={rf:+.5f}({srf[0]:.5f}) ITTadj={rf_adj:+.5f} ITTrenal={rf_ren:+.5f} | LATE={late:+.3f} | '
          f'balAge={ba[0]:+.2f}{bal_flag}balCr={bcr[0]:+.3f}(egfr_cov={cov_egfr:.2f}) | densB/A={dens:.2f} | LOSmed={los_med:.1f}d')


noise_sigma_cache = {}


def run_trial(name, key, classes, flag, direction, hw, adm, age, transfers, creat=None, bun=None, gender=None):
    seqs = load_labseq(key)
    if not seqs:
        print(f'  {name:28s}: lab_{key}.csv empty/missing — SKIP'); return
    tx = load_rx(classes)
    if not tx:
        print(f'  {name:28s}: rx_elyte.csv empty/missing (run stream_rx_elyte.py on prescriptions.csv.gz first) — SKIP')
        return
    if not transfers:
        print(f'  {name:28s}: transfers.csv empty/missing — cannot classify WARD/ICU — SKIP')
        return

    sig = noise_sigma(seqs, tx)
    noise_sigma_cache['sig'] = sig
    print(f'  {name}  (noise sigma={sig:.3g})')

    rows = build_cohort(seqs, tx, adm, age, transfers, flag, direction, creat, bun, gender)
    n_unk = sum(1 for r in rows if r['stratum'] == 'UNKNOWN')
    if n_unk:
        print(f'    note: {n_unk}/{len(rows)} decisions have no transfers coverage at M2 time (UNKNOWN, excluded from strata)')

    ward_rows = [r for r in rows if r['stratum'] == 'WARD']
    icu_rows = [r for r in rows if r['stratum'] == 'ICU']

    print('    --- WARD (headline: floor de-implementation target) ---')
    analyze_stratum('WARD', ward_rows, flag, hw)
    print('    --- ICU ---')
    analyze_stratum('ICU', icu_rows, flag, hw)
    print('    --- OVERALL (pooled ward+ICU+unknown) ---')
    analyze_stratum('OVERALL', rows, flag, hw)
    print()


def main():
    print('=== WARD-INCLUSIVE PORTFOLIO: assay-noise IV / flag-ITT, electrolyte repletion ===')
    print('Treatment sourced from PRESCRIPTIONS (hospital-wide) not inputevents (ICU-only) -> floor-visible.')
    print('Stratified WARD vs ICU via transfers.csv careunit at the time of the triggering lab (M2).')
    print('headline = WARD flag-ITT(mortality); LATE=implied (ITT/FS) with Anderson-Rubin CI; balAge~0 => exogenous\n')
    adm = load_adm(); age = load_age(); transfers = load_transfers()
    if not adm:
        print('admissions.csv missing — ABORT (need admissions for mortality/LOS/subject linkage)'); return
    if not transfers:
        print('transfers.csv missing — ABORT (need transfers for ward/ICU classification)'); return
    creat = load_labseq('creat'); bun = load_labseq('bun'); gender = load_gender()
    print(f'renal controls: creatinine {len(creat)} hadm, BUN {len(bun)} hadm, gender {len(gender)} subj '
          f'(ITTrenal adjusts for eGFR[CKD-EPI]+Cr+BUN; balCr = creatinine~Z exogeneity check)\n')
    for (name, key, classes, flag, direction, hw) in CONFIG:
        run_trial(name, key, classes, flag, direction, hw, adm, age, transfers, creat, bun, gender)
    print('DONE. Interpret per stratum: strong FS + balAge~0 + precise ITT => usable; WARD stratum is the')
    print('headline de-implementation estimate (highest-scale floor reflexive-repletion target); ICU stratum')
    print('replicates the original inputevents-sourced design as a cross-check on the same rx-sourced treatment.')


if __name__ == '__main__':
    main()
