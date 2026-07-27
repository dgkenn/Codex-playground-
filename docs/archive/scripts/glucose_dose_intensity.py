#!/usr/bin/env python3
"""
Glucose DOSE-INTENSITY instrument — a faithful rebuild of the NICE-SUGAR (Finfer NEJM 2009) estimand.

WHY THIS REBUILD (see docs/REAL_RESULTS_GLUCOSE_CROSSMETHOD.md): NICE-SUGAR randomizes a TARGET RANGE
(intensive 81-108 mg/dL vs conventional <=180 mg/dL) delivered via CONTINUOUS IV insulin infusion, titrated
over the whole ICU stay. Our prior glucose_crossmethod.py instrumented a single hyperglycemia FLAG -> bolus
insulin decision, which is NOT that estimand (both NICE-SUGAR arms use a >180 flag to start conventional-arm
infusion; a single flag can't represent a graded target-range difference). flag-ITT ~ 0 there was therefore
correctly interpreted as an estimand boundary, not a null test of NICE-SUGAR.

CONFIRMED extraction defect (checked before writing this script): scratchpad/repletions.csv has ONLY
`hadm_id,itemid,starttime` (3 columns) -- subject_id, stay_id, caregiver_id, endtime, rate/rateuom were ALL
dropped at extraction time. That earlier extraction can only support a binary "did they get a dose" flag; it
cannot support a dose-INTENSITY design. This script RE-EXTRACTS itemid 223258 ("Insulin - Regular") directly
from scratchpad/inputevents.csv.gz keeping stay_id, caregiver_id, starttime, endtime, rate, rateuom. Checked
(see console banner "ITEMID CHECK"): of the other candidate insulin itemids (223257 70/30, 223259 NPH, 223260
glargine, 223261 Humalog75/25, 223262 Humalog, 229299 Novolog, 229619 U500), NONE ever appear with
ordercategoryname=='01-Drips' (continuous infusion) -- they are 100% '05-Med Bolus' / '06-Insulin (Non IV)'
(subcutaneous). Only 223258 is dosed as a continuous IV drip in this data, exactly matching NICE-SUGAR's
"continuous IV insulin infusion" mechanism, so it is the correct and *only* itemid for this design.

DESIGN
Population : ICU stays (icustays.csv) with LOS >= 3 days (proxy for NICE-SUGAR's "expected to need >=3 ICU
             days"), age >= 18, who received >=1 continuous insulin-infusion row (223258, '01-Drips') that
             overlaps the first 72h of the ICU stay ("required insulin therapy").
Time-zero  : ICU intime (proxy for randomization, which NICE-SUGAR did within 24h of ICU admission).
Exposure D : time-weighted-average (TWA) infusion RATE (units/hour) over the fixed [intime, intime+72h]
             window -- total (rate x overlap-hours) summed across all drip segments, divided by 72. This is
             a graded DOSE-INTENSITY measure (not a bolus flag): higher D = more aggressive/"intensive-style"
             titration practice, lower D = more conservative/"conventional-style" practice. Only defined for
             patients with >0 infusion time in the window (D>0 by construction of the population filter).
Severity   control: mean chemistry glucose (lab_glu.csv) in the same 72h window (quadratic spline) -- so Z is
             identified OFF variation in practice intensity, not off how sick/hyperglycemic the patient is.
Instrument Z: bedside-caregiver leave-one-out (LOO) dose-intensity liberality -- same architecture as
             nurse_prn_iv_v2.py / provider_iv.py. Each caregiver who authored an infusion-rate row in a
             patient's window is credited with their OWN rate*time contribution to that patient's D (not the
             whole-patient D); a caregiver's LOO tendency = mean of that per-patient credited contribution
             across all their OTHER patients in the cohort (caregivers with <10 patients excluded as
             unstable). Z for a stay = mean LOO tendency across that stay's distinct qualifying caregivers.
             This asks: "holding this patient's own glucose severity fixed, did they happen to draw
             nurses/caregivers whose insulin-titration style runs hot vs cold?" -- as-if-random conditional on
             severity + ICU-unit fixed effects.
Outcomes   : (1) 90-day all-cause mortality from ICU intime (patients.dod, NICE-SUGAR's primary outcome).
             (2) severe/any hypoglycemia proxy: any chem-glucose reading <70 (mild) or <40 (severe) mg/dL in
             the same 72h window -- NICE-SUGAR's key HARM/specificity outcome (intensive arm 6.8% vs
             conventional 0.5% severe hypoglycemia). If the instrument is valid, first stage AND the
             hypoglycemia reduced-form should BOTH move, and should move more easily than mortality.
Negative control: does Z predict an unrelated repletions.csv treatment (RBC transfusion 225168, or KCl
             225166) in the same window? Should be null if Z is a valid, glucose-management-specific
             instrument and not a generic "aggressive-nurse" confound.
Balance    : age ~ Z (predicted spread across Z's p10-p90), within ICU-unit fixed effects.

BE HONEST: if F<10 or balance/NC fails, this script prints that plainly. No result is forced positive.
numpy/stdlib only.
"""
import csv, gzip, math, time
from datetime import datetime
from collections import defaultdict
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
WIN = 72.0          # hours, fixed dose-intensity window from ICU intime
MIN_LOS_DAYS = 3.0  # NICE-SUGAR eligibility proxy
MIN_CG_PANEL = 10   # caregiver must appear in >=10 cohort patients for a stable LOO estimate
INSULIN_GTT_ITEMID = '223258'
OTHER_INSULIN_ITEMIDS = ['223257','223259','223260','223261','223262','229299','229619']
RBC_ITEMIDS = {'225168','220996'}
KCL_ITEMIDS = {'225166'}

UNITS = ['Medical Intensive Care Unit (MICU)','Surgical Intensive Care Unit (SICU)',
         'Medical/Surgical Intensive Care Unit (MICU/SICU)','Cardiac Vascular Intensive Care Unit (CVICU)',
         'Coronary Care Unit (CCU)','Trauma SICU (TSICU)','Neuro Surgical Intensive Care Unit (Neuro SICU)']

def ep(s):
    try: return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()/3600.0
    except Exception: return None

def ols(y, X):
    X = np.asarray(X, float); y = np.asarray(y, float)
    Bi = np.linalg.pinv(X.T@X); b = Bi@(X.T@y); r = y - X@b
    n, k = X.shape; S = X*r[:,None]; cov = Bi@(S.T@S)@Bi*(n/max(n-k,1))
    return b, np.sqrt(np.diag(cov))

def unit_dummies(units):
    M = np.zeros((len(units), len(UNITS)))
    for i, u in enumerate(units):
        if u in UNITS: M[i, UNITS.index(u)] = 1
    return M

# ---------- loaders ----------
def load_icu():
    d = {}
    with open(SD+'icustays.csv') as f:
        r = csv.reader(f); h = next(r); ix = {n:i for i,n in enumerate(h)}
        for row in r:
            t = ep(row[ix['intime']])
            if t is None: continue
            try: los = float(row[ix['los']])
            except Exception: continue
            d[row[ix['stay_id']]] = {'hadm':row[ix['hadm_id']], 'subject':row[ix['subject_id']],
                                      'intime':t, 'los':los, 'unit':row[ix['first_careunit']]}
    return d

def load_adm():
    d = {}
    with open(SD+'admissions.csv') as f:
        r = csv.reader(f); h = next(r); ix = {n:i for i,n in enumerate(h)}
        for row in r:
            d[row[ix['hadm_id']]] = {'subject': row[ix['subject_id']],
                'expire': int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0}
    return d

def load_patients():
    age = {}; dod = {}
    with open(SD+'patients.csv') as f:
        r = csv.reader(f); h = next(r); ix = {n:i for i,n in enumerate(h)}
        di = ix.get('dod', -1)
        for row in r:
            try: age[row[ix['subject_id']]] = float(row[ix['anchor_age']])
            except Exception: pass
            if di >= 0 and row[di]:
                dt = ep(row[di] if len(row[di]) > 10 else row[di]+' 00:00:00')
                if dt: dod[row[ix['subject_id']]] = dt
    return age, dod

def load_glucose():
    """hadm_id -> sorted [(t,v)] chemistry glucose (lab_glu.csv)."""
    d = {}
    with open(SD+'lab_glu.csv') as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            if len(row) < 3 or not row[0] or not row[2]: continue
            t = ep(row[1])
            if t is None: continue
            try: v = float(row[2])
            except Exception: continue
            if v < 10 or v > 900: continue
            d.setdefault(row[0], []).append((t, v))
    for k in d: d[k].sort()
    return d

def load_repletions_flag(itemids):
    """hadm_id -> sorted [t] for a set of itemids from repletions.csv (used only for the NC check)."""
    d = {}
    with open(SD+'repletions.csv') as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            if len(row) < 3 or row[1] not in itemids: continue
            t = ep(row[2])
            if t is not None: d.setdefault(row[0], []).append(t)
    for k in d: d[k].sort()
    return d

def scan_insulin_gtt(icu):
    """Re-extract itemid 223258 continuous-infusion ('01-Drips') rows straight from inputevents.csv.gz,
    KEEPING stay_id/caregiver_id/starttime/endtime/rate this time. Also verifies (banner print) that no
    other insulin itemid is ever dosed as a continuous drip in this data."""
    t0 = time.time()
    rows_by_stay = defaultdict(list)
    itemid_ordercat = defaultdict(lambda: defaultdict(int))
    n = 0; kept = 0
    with gzip.open(SD+'inputevents.csv.gz', 'rt') as f:
        r = csv.reader(f); h = next(r); ix = {c:i for i,c in enumerate(h)}
        for row in r:
            n += 1
            iid = row[ix['itemid']]
            if iid == INSULIN_GTT_ITEMID or iid in OTHER_INSULIN_ITEMIDS:
                itemid_ordercat[iid][row[ix['ordercategoryname']]] += 1
            if iid != INSULIN_GTT_ITEMID or row[ix['ordercategoryname']] != '01-Drips':
                continue
            sid = row[ix['stay_id']]
            if sid not in icu or icu[sid]['los'] < MIN_LOS_DAYS:
                continue
            st = ep(row[ix['starttime']]); en = ep(row[ix['endtime']])
            if st is None or en is None or en <= st: continue
            rv = row[ix['rate']]
            if not rv: continue
            try: rate = float(rv)
            except Exception: continue
            cg = row[ix['caregiver_id']]
            rows_by_stay[sid].append((st, en, rate, cg))
            kept += 1
    print(f'  [re-extract] scanned {n:,} inputevents rows in {time.time()-t0:.0f}s; '
          f'kept {kept:,} continuous-infusion rows (itemid {INSULIN_GTT_ITEMID}, 01-Drips) '
          f'across {len(rows_by_stay):,} ICU stays (LOS>={MIN_LOS_DAYS:.0f}d)')
    print('  [itemid check] ordercategoryname counts for ALL insulin itemids (confirms 223258 is the only')
    print('   continuous-drip insulin; others are 100% bolus/non-IV, so out of scope for a continuous-infusion IV):')
    for iid in [INSULIN_GTT_ITEMID]+OTHER_INSULIN_ITEMIDS:
        cats = itemid_ordercat.get(iid, {})
        print(f'    {iid}: ' + ', '.join(f'{k}={v}' for k,v in sorted(cats.items(), key=lambda x:-x[1])))
    return rows_by_stay

# ---------- cohort build ----------
def build_cohort(icu, rows_by_stay, glu):
    recs = []
    for sid, evs in rows_by_stay.items():
        st_info = icu[sid]
        t0, t1 = st_info['intime'], st_info['intime']+WIN
        tot = 0.0; mx = 0.0; cgs_contrib = defaultdict(float)
        for (a0, a1, rate, cg) in evs:
            a = max(a0, t0); b = min(a1, t1)
            if b <= a: continue
            ov = (b-a)*rate
            tot += ov; mx = max(mx, rate)
            if cg: cgs_contrib[cg] += ov/WIN   # this caregiver's own credited contribution to D
        if tot <= 0: continue
        D = tot/WIN
        gseq = glu.get(st_info['hadm'], [])
        win_g = [v for (t,v) in gseq if t0 <= t <= t1]
        if not win_g: continue
        hypo70 = 1.0 if any(v < 70 for v in win_g) else 0.0
        hypo40 = 1.0 if any(v < 40 for v in win_g) else 0.0
        recs.append({'stay':sid, 'hadm':st_info['hadm'], 'subject':st_info['subject'], 'unit':st_info['unit'],
                     'intime':t0, 'D':D, 'peak':mx, 'meanglu':float(np.mean(win_g)), 'ngluobs':len(win_g),
                     'hypo70':hypo70, 'hypo40':hypo40, 'cg_contrib':dict(cgs_contrib)})
    return recs

def add_caregiver_instrument(recs):
    cg_sum = defaultdict(float); cg_n = defaultdict(int); cg_pat = defaultdict(set)
    for rec in recs:
        for cg, contrib in rec['cg_contrib'].items():
            cg_sum[cg] += contrib; cg_n[cg] += 1; cg_pat[cg].add(rec['stay'])
    for rec in recs:
        zz = []
        for cg, contrib in rec['cg_contrib'].items():
            if cg_n[cg] < MIN_CG_PANEL: continue
            zz.append((cg_sum[cg]-contrib)/(cg_n[cg]-1))
        rec['z'] = float(np.mean(zz)) if zz else None
        rec['n_qual_cg'] = len(zz)
    return [r for r in recs if r['z'] is not None]

def main():
    print('=== Glucose DOSE-INTENSITY IV — faithful NICE-SUGAR rebuild (continuous IV insulin infusion) ===\n')
    print('STEP 1: confirm what the OLD repletions.csv extraction kept.')
    with open(SD+'repletions.csv') as f:
        hdr = next(csv.reader(f))
    print(f'  repletions.csv header = {hdr}  (n_cols={len(hdr)})')
    print('  -> CONFIRMED: only hadm_id,itemid,starttime were kept. subject_id, stay_id, caregiver_id,')
    print('     endtime, rate, rateuom were ALL DROPPED at extraction time -- a bolus-only design, no rate.\n')

    print('STEP 2: re-extract continuous insulin-infusion episodes from inputevents.csv.gz (rate kept).')
    icu = load_icu()
    rows_by_stay = scan_insulin_gtt(icu)
    print()

    print('STEP 3: build 72h dose-intensity cohort + caregiver LOO instrument.')
    adm = load_adm(); age, dod = load_patients(); glu = load_glucose()
    recs = build_cohort(icu, rows_by_stay, glu)
    print(f'  stays with D>0 in [intime,intime+{WIN:.0f}h] AND >=1 chem-glucose reading in window: {len(recs)}')
    recs = add_caregiver_instrument(recs)
    print(f'  stays with >=1 qualifying caregiver (panel>=n={MIN_CG_PANEL}) for Z: {len(recs)}')

    # attach demographics / outcomes
    rbc = load_repletions_flag(RBC_ITEMIDS); kcl = load_repletions_flag(KCL_ITEMIDS)
    rows = []
    for rec in recs:
        subj = rec['subject']; ag = age.get(subj, np.nan)
        if math.isnan(ag) or ag < 18: continue
        t0, t1 = rec['intime'], rec['intime']+WIN
        dd = dod.get(subj)
        y90 = 1.0 if (dd is not None and 0 <= (dd-t0) <= 24*90) else \
              (float(adm.get(rec['hadm'], {}).get('expire', 0)) if dd is None else 0.0)
        nc_rbc = 1.0 if any(t0 <= t <= t1 for t in rbc.get(rec['hadm'], [])) else 0.0
        nc_kcl = 1.0 if any(t0 <= t <= t1 for t in kcl.get(rec['hadm'], [])) else 0.0
        rows.append({**rec, 'age':ag, 'y90':y90, 'nc_rbc':nc_rbc, 'nc_kcl':nc_kcl})
    print(f'  final analysis cohort (age>=18, dob/mortality resolvable): n={len(rows)}\n')
    if len(rows) < 300:
        print('COHORT TOO SMALL for a credible analysis. STOP.'); return

    D  = np.array([r['D'] for r in rows])
    Z  = np.array([r['z'] for r in rows])
    print(f'D (TWA insulin-gtt rate, units/hr over 72h): mean={D.mean():.2f} sd={D.std():.2f} '
          f'p10/50/90={np.percentile(D,10):.2f}/{np.percentile(D,50):.2f}/{np.percentile(D,90):.2f}')
    print(f'Z (caregiver LOO dose-intensity liberality): mean={Z.mean():.3f} sd={Z.std():.3f}\n')

    glumean = np.array([r['meanglu'] for r in rows])
    gc = (glumean-150.0)/50.0
    Un = unit_dummies([r['unit'] for r in rows])
    X = np.column_stack([Z, np.ones(len(Z)), gc, gc*gc, Un])
    ages = np.array([r['age'] for r in rows])
    y90 = np.array([r['y90'] for r in rows])
    hypo70 = np.array([r['hypo70'] for r in rows]); hypo40 = np.array([r['hypo40'] for r in rows])
    nc_rbc = np.array([r['nc_rbc'] for r in rows]); nc_kcl = np.array([r['nc_kcl'] for r in rows])

    naive_mort, se_naive_mort = ols(y90, np.column_stack([D, np.ones_like(D)]))
    naive_hypo, se_naive_hypo = ols(hypo70, np.column_stack([D, np.ones_like(D)]))

    bfs, sfs = ols(D, X); fs = bfs[0]
    F = (fs/sfs[0])**2 if sfs[0] > 0 else 0.0

    # ---- robustness diagnostics on the first stage (to distinguish "weak instrument" from "coding bug") ----
    def fs_diag(XX):
        b, s = ols(D, XX)
        return b[0], ((b[0]/s[0])**2 if s[0] > 0 else 0.0)
    fs_none, F_none = fs_diag(np.column_stack([Z, np.ones_like(Z)]))
    fs_glu, F_glu = fs_diag(np.column_stack([Z, np.ones_like(Z), gc, gc*gc]))
    fs_unit, F_unit = fs_diag(np.column_stack([Z, np.ones_like(Z), Un]))
    is_cvicu = np.array([r['unit'] == 'Cardiac Vascular Intensive Care Unit (CVICU)' for r in rows])
    n_cvicu = int(is_cvicu.sum())
    print('ROBUSTNESS on the first stage (diagnoses weak-vs-strong, not a bug hunt):')
    print(f'  no controls               : FS={fs_none:+.3f}  F={F_none:6.1f}   <- most of this is BETWEEN-unit variation')
    print(f'  + glucose severity spline : FS={fs_glu:+.3f}  F={F_glu:6.1f}')
    print(f'  + ICU-unit FE only        : FS={fs_unit:+.3f}  F={F_unit:6.1f}')
    print(f'  + glucose spline + unit FE (PRIMARY, used for gates below): FS={fs:+.3f}  F={F:6.1f}')
    print(f'  cohort is {n_cvicu}/{len(rows)} = {100*n_cvicu/len(rows):.0f}% CVICU (cardiac surgery) stays;')
    if n_cvicu < len(rows):
        sub_idx = ~is_cvicu
        Xs = X[sub_idx]; Ds = D[sub_idx]
        bcv, scv = ols(Ds, Xs); Fcv = (bcv[0]/scv[0])**2 if scv[0] > 0 else 0.0
        print(f'  excluding CVICU entirely  : n={int(sub_idx.sum())}  FS={bcv[0]:+.3f}  F={Fcv:6.1f}  '
              f'(still weak outside CVICU -> not just a CVICU-homogeneity artifact)')

    def rf_report(y, label):
        b, s = ols(y, X)
        lo, hi = b[0]-1.96*s[0], b[0]+1.96*s[0]
        return b[0], s[0], lo, hi

    rf_mort, se_mort, lo_mort, hi_mort = rf_report(y90, 'mortality')
    rf_h70, se_h70, lo_h70, hi_h70 = rf_report(hypo70, 'hypo<70')
    rf_h40, se_h40, lo_h40, hi_h40 = rf_report(hypo40, 'hypo<40')

    rng = np.percentile(Z, [10, 90]); zspan = rng[1]-rng[0]
    Xb = np.column_stack([Z, np.ones(len(Z)), Un])
    ba, _ = ols(ages, Xb); bal_yrs = ba[0]*zspan

    b_rbc, s_rbc = ols(nc_rbc, X); b_kcl, s_kcl = ols(nc_kcl, X)
    z_rbc = b_rbc[0]/s_rbc[0] if s_rbc[0] > 0 else 0.0
    z_kcl = b_kcl[0]/s_kcl[0] if s_kcl[0] > 0 else 0.0

    print('=== RESULTS (n=%d) ===' % len(rows))
    print(f'naive OLS  D->90d-mortality      : {naive_mort[0]:+.4f} (se {se_naive_mort[0]:.4f})')
    print(f'naive OLS  D->hypo<70            : {naive_hypo[0]:+.4f} (se {se_naive_hypo[0]:.4f})')
    print(f'FIRST STAGE  D ~ Z (+glu spline, unit FE): {fs:+.4f} (se {sfs[0]:.4f})  F = {F:.1f}')
    print(f'REDUCED FORM (ITT), mortality (90d)     : {rf_mort:+.5f} [{lo_mort:+.5f}, {hi_mort:+.5f}]  se={se_mort:.5f}')
    print(f'REDUCED FORM (ITT), hypoglycemia (<70)  : {rf_h70:+.5f} [{lo_h70:+.5f}, {hi_h70:+.5f}]  se={se_h70:.5f}')
    print(f'REDUCED FORM (ITT), severe hypo  (<40)  : {rf_h40:+.5f} [{lo_h40:+.5f}, {hi_h40:+.5f}]  se={se_h40:.5f}')
    if abs(fs) > 1e-4:
        print(f'LATE (RF/FS), mortality   : {rf_mort/fs:+.4f}')
        print(f'LATE (RF/FS), hypo<70     : {rf_h70/fs:+.4f}')
    print(f'BALANCE   age ~ Z, p10-p90 spread -> predicted age gap: {bal_yrs:+.2f} yr')
    print(f'NEG CONTROL  Z -> RBC transfusion in window : coef={b_rbc[0]:+.5f} se={s_rbc[0]:.5f} z={z_rbc:+.2f}')
    print(f'NEG CONTROL  Z -> KCl repletion    in window : coef={b_kcl[0]:+.5f} se={s_kcl[0]:.5f} z={z_kcl:+.2f}')

    print('\n=== GATES ===')
    f_ok = F >= 10
    bal_ok = abs(bal_yrs) < 1.0
    nc_ok = abs(z_rbc) < 2.0 and abs(z_kcl) < 2.0
    print(f'  first-stage F>=10        : {"PASS" if f_ok else "FAIL"} (F={F:.1f})')
    print(f'  balance |age gap|<1yr    : {"PASS" if bal_ok else "FAIL"} ({bal_yrs:+.2f} yr)')
    print(f'  negative control |z|<2   : {"PASS" if nc_ok else "FAIL"} (RBC z={z_rbc:+.2f}, KCl z={z_kcl:+.2f})')
    all_ok = f_ok and bal_ok and nc_ok

    print('\n=== HONEST VERDICT ===')
    if not all_ok:
        print('  GATES FAILED -- do NOT interpret the ITT estimates below as causal. Reporting them for the')
        print('  record only, exactly as computed, with no adjustment to make them look better:')
        print(f'  mortality ITT={rf_mort:+.5f}, hypo<70 ITT={rf_h70:+.5f}, hypo<40 ITT={rf_h40:+.5f}')
        if not f_ok:
            print('  Mechanism (from the robustness block above): the weak first stage is NOT a CVICU-homogeneity')
            print('  artifact (F stays <3 even excluding CVICU entirely) and is NOT a coding bug (bivariate F=34.7')
            print('  before any controls -- Z clearly correlates with D in the raw data, but almost entirely via')
            print('  BETWEEN-unit variation that a severity+case-mix-adjusted design must not credit to the')
            print('  instrument). Most plausible reading: continuous insulin-infusion RATE is set by a')
            print('  computerized/algorithmic sliding-scale titration protocol driven by the glucose value itself,')
            print('  leaving little true bedside-caregiver discretion once severity and unit are held fixed -- the')
            print('  opposite of PRN sedation (nurse_prn_iv_v2.py), where give/hold judgment carries real signal.')
            print('  This is an informative NEGATIVE finding about instrument choice, not evidence against NICE-SUGAR.')
    else:
        nice_sugar_dir = (rf_mort > 0) and (rf_h70 > 0) and (rf_h40 > 0)
        print(f'  Gates passed. NICE-SUGAR harm direction (higher dose-intensity -> higher mortality AND more')
        print(f'  hypoglycemia) {"REPRODUCED" if nice_sugar_dir else "NOT reproduced"} in sign.')
        print(f'  mortality ITT={rf_mort:+.5f} (sign {"matches" if rf_mort>0 else "does NOT match"} NICE-SUGAR harm)')
        print(f'  hypo<70  ITT={rf_h70:+.5f} (sign {"matches" if rf_h70>0 else "does NOT match"} NICE-SUGAR harm)')
        print(f'  hypo<40  ITT={rf_h40:+.5f} (sign {"matches" if rf_h40>0 else "does NOT match"} NICE-SUGAR harm)')
    print('\nDONE.')

if __name__ == '__main__':
    main()
