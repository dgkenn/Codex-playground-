#!/usr/bin/env python3
"""
AmsterdamUMCdb (Amsterdam, Netherlands; PhysioNet "amsterdamumcdb" v1.0.2) EXTERNAL REPLICATION of the
assay-noise IV / flag-ITT engine (mirrors /home/user/Codex-playground-/docs/portfolio_run.py and
docs/eicu_run.py) for the lab-flag-triggered benchmark cases.

*** MAPPING STATUS (see docs/MULTISITE_HARMONIZATION.md for full citations): ***
Labs (numericitems.itemid) are CONFIRMED from ricu's concept-dict.json (single source; units NOT
confirmed -- Dutch labs commonly report Hb/glucose in mmol/L, NOT the US mg/dL or g/dL convention, so a
unit-conversion bug here is the top day-one risk). Insulin (drugitems.itemid) is CONFIRMED (ricu). RBC
transfusion, sodium bicarbonate, and potassium chloride (drugitems.itemid) are ALL TO-CONFIRM-ON-ACCESS
-- a verification pass explicitly caught and discarded a fabricated-looking itemid set for these three
(a WebFetch summarizer produced numbers after admitting it never actually saw that part of the source
file); do not trust any RBC/NaHCO3/KCl itemid that isn't re-derived directly from dictionary.csv or the
concepts/ folder on access.

  RBC transfusion      @ Hgb < 7        (TRICC/TRISS validation)     -- lab id confirmed, tx id TODO
  Insulin              @ glucose > 180  (NICE-SUGAR validation)      -- lab id confirmed, tx id CONFIRMED
  Bicarbonate          @ HCO3 < 15      (acidosis correction)        -- lab id confirmed, tx id TODO
  Potassium chloride   @ K < 3.5        (repletion; context)         -- lab id confirmed, tx id TODO
  Magnesium repletion  @ Mg < 2.0                                    -- lab id confirmed, tx id TODO

Design (identical to the MIMIC/eICU/HiRID/SICdb engines, restated for AmsterdamUMCdb's
MILLISECONDS-FROM-FIRST-ADMISSION clock -- like eICU's minutes and SICdb's seconds, just finer-grained,
no datetime parsing needed):
  - M1, M2 = first two pre-treatment lab draws (numericitems.measuredat, ms since first admission)
  - instrument Z = 1(M2 crosses the flag in the de-implementation direction)
  - severity control = midpoint (M1+M2)/2, local-linear (2nd-order) control function of (mid - flag)
  - D = 1(treatment of the matching class occurs within 24h of M2)
  - primary outcome Y = hospital mortality (admissions.destination == 'Overleden' -- died during THIS
    ICU/MCU admission; deliberately narrower than bare `dateofdeath` non-null, which counts ANY death at
    ANY time and would overcount post-discharge deaths as in-hospital)
  - reports: n, noise sigma, first-stage F, flag-ITT (headline), implied-LATE with Anderson-Rubin CI,
    covariate balance (age), M2 density/heaping (McCrary-style), and the NAIVE (confounded) D->mortality
    contrast (crude + severity-adjusted) for comparison.

=== ID MAPPINGS (see docs/MULTISITE_HARMONIZATION.md; ricu concept-dict.json, github.com/eth-mds/ricu) ===
Labs (numericitems.itemid), units TO-CONFIRM (mmol/L vs g/dL/mg/dL -- Dutch convention risk):
  hb    : 6778, 9553, 9960, 10286, 19703
  glu   : 6833, 9557, 9947
  hco3  : 6810, 9992
  k     : 6835, 9556, 9927, 10285
  mg    : 6849, 9931
Treatments (drugitems.itemid):
  insulin : 7624, 9014, 19129     -- CONFIRMED (ricu; reached before the file-truncation point)
  rbc     : TODO -- grep dictionary.csv / concepts/ for 'erytrocytenconcentraat' / 'packed cells' / 'EC'
  nahco3  : TODO -- grep dictionary.csv / concepts/ for 'natriumbicarbonaat' / 'bicarbonaat'
  kcl     : TODO -- grep dictionary.csv / concepts/ for 'kaliumchloride' / 'kalium'
Patient (admissions table):
  age       : admissions.agegroup   (CATEGORICAL banded age, NOT continuous -- exact band strings e.g.
                                      "18-39" TO-CONFIRM-ON-ACCESS; this changes the balance-check design,
                                      see note in run_trial below)
  sex       : admissions.gender     ('Man' / 'Vrouw')
  mortality : admissions.destination == 'Overleden'   (RECOMMENDED -- died during this admission)
Timestamps: numericitems.measuredat, drugitems.start/stop are INTEGER MILLISECONDS since the patient's
FIRST ICU admission (drugitems.duration is in MINUTES, not ms -- watch this field specifically).

=== EXACT FETCH COMMANDS (fill in your PhysioNet credentials via ~/.netrc) ===
# THE CRITICAL DAY-ONE FILE -- resolves the 3 TODO treatment itemids and confirms lab units:
wget -N -c --netrc -P ./amsterdam_raw \
  https://raw.githubusercontent.com/AmsterdamUMC/AmsterdamUMCdb/master/amsterdamumcdb/dictionary.csv
# (Alternative: `pip install amsterdamumcdb` then `amsterdamumcdb.get_dictionary()` in Python.)
wget -N -c --netrc -P ./amsterdam_raw https://physionet.org/files/amsterdamumcdb/1.0.2/numericitems.csv.gz
wget -N -c --netrc -P ./amsterdam_raw https://physionet.org/files/amsterdamumcdb/1.0.2/drugitems.csv.gz
wget -N -c --netrc -P ./amsterdam_raw https://physionet.org/files/amsterdamumcdb/1.0.2/admissions.csv.gz
# Concept notebooks (may already contain a working blood-transfusion/medication query to crib from):
git clone https://github.com/AmsterdamUMC/AmsterdamUMCdb.git ./amsterdam_raw/AmsterdamUMCdb_repo

Inputs expected here (produced by an amsterdam_stream_lab.py / amsterdam_stream_tx.py stream-filter
step, mirroring eicu_stream_lab.py/eicu_stream_tx.py -- TODO: write those once dictionary.csv resolves
the 3 missing treatment itemids):
  amsterdam_lab_hb.csv, amsterdam_lab_glu.csv, amsterdam_lab_hco3.csv, amsterdam_lab_k.csv,
  amsterdam_lab_mg.csv
    columns: admissionid, measuredat, itemid, value
  amsterdam_tx.csv
    columns: admissionid, start, tx_class   (tx_class in {rbc, insulin, nahco3, kcl} -- rbc/nahco3/kcl
    CANNOT BE POPULATED until the dictionary.csv grep above resolves concrete itemids; insulin can be
    populated now with itemid in {7624, 9014, 19129})
  amsterdam_admissions.csv (renamed from the raw admissions.csv.gz to avoid colliding with the MIMIC
  engine's own scratchpad/admissions.csv, which uses a completely different hadm_id-based schema)
    columns used: admissionid, agegroup, gender, destination

Missing input files => SKIP, no crash (same contract as eicu_run.py). Given the treatment-id gap, EXPECT
RBC/BICARBONATE/KCL TRIALS TO SKIP on first run (insulin should run once labs are populated) -- this is a
known, documented limitation of the public-source mapping, not a bug in this script.
"""
import csv, math
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'

# (name, lab_csv_key, tx_class, flag, direction '<'|'>', bandwidth)
# Units TO-CONFIRM: if numericitems reports Hb/glucose in mmol/L (common Dutch lab convention), these
# flags (g/dL, mg/dL) must be converted BEFORE reaching these CSVs (in amsterdam_stream_lab.py), or the
# flag thresholds silently apply to the wrong scale. Verify via dictionary.csv's unit column on access.
CONFIG = [
    ('RBC transfusion (Hgb<7)',        'hb',   'rbc',     7.0,  '<', 0.60),
    ('Insulin (glucose>180)',          'glu',  'insulin', 180,  '>', 25),
    ('Bicarbonate (acidosis, <15)',    'hco3', 'nahco3',  15.0, '<', 3.0),
    ('Potassium chloride (K<3.5)',     'k',    'kcl',     3.5,  '<', 0.25),
    ('Magnesium repletion (Mg<2.0)',   'mg',   'mg',      2.0,  '<', 0.15),
]

# admissions.agegroup band midpoints, for use as a continuous-ish covariate in the balance check.
# TO-CONFIRM-ON-ACCESS: exact band strings were NOT verifiable from public sources -- this map is a
# best-effort placeholder using the commonly-cited AmsterdamUMCdb bands and MUST be corrected against
# the real column values before trusting balAge in the output.
AGEGROUP_MIDPOINT = {
    '18-39': 28.5, '40-49': 44.5, '50-59': 54.5, '60-69': 64.5,
    '70-79': 74.5, '80+': 85.0,
}

def load_labseq(key):
    """measuredat in ms -> hours, mirroring eicu_run.py's minutes->hours conversion."""
    d = {}
    try:
        f = open(SD + f'amsterdam_lab_{key}.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 4:
            continue
        aid, ts, _itemid, vn = row[0], row[1], row[2], row[3]
        if not aid or not ts or not vn:
            continue
        try:
            t = float(ts) / 3_600_000.0  # ms -> hours
            v = float(vn)
        except ValueError:
            continue
        d.setdefault(aid, []).append((t, v))
    f.close()
    for k in d:
        d[k].sort()
    return d

def load_tx(cls):
    d = {}
    try:
        f = open(SD + 'amsterdam_tx.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 3:
            continue
        aid, ts, c = row[0], row[1], row[2]
        if c != cls or not aid or not ts:
            continue
        try:
            t = float(ts) / 3_600_000.0  # ms -> hours
        except ValueError:
            continue
        d.setdefault(aid, []).append(t)
    f.close()
    for k in d:
        d[k].sort()
    return d

def load_admissions():
    """amsterdam_admissions.csv (renamed from raw admissions.csv.gz): admissionid, agegroup, gender, destination.
    mortality = 1 if destination == 'Overleden' else 0 (died during THIS admission -- narrower and more
    correct than bare dateofdeath non-null, see module docstring).
    age = AGEGROUP_MIDPOINT.get(agegroup, nan) -- TO-CONFIRM band strings on access; a mismatch here
    silently drops patients from the balance-check n (nan age), not from the main trial (age is only
    used for the balAge diagnostic, not the core Z/D/Y identification).
    """
    d = {}
    try:
        f = open(SD + 'amsterdam_admissions.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    hdr = next(r)
    idx = {n: i for i, n in enumerate(hdr)}
    if 'admissionid' not in idx:
        print('  amsterdam_admissions.csv present but missing "admissionid" column '
              '(wrong file/schema?) — SKIP all trials')
        f.close()
        return d
    i_aid = idx['admissionid']
    i_age = idx.get('agegroup')
    i_dest = idx.get('destination')
    i_gender = idx.get('gender')
    for row in r:
        aid = row[i_aid]
        agegroup = row[i_age].strip() if (i_age is not None and i_age < len(row)) else ''
        age = AGEGROUP_MIDPOINT.get(agegroup, float('nan'))
        dest = row[i_dest] if (i_dest is not None and i_dest < len(row)) else ''
        expire = 1 if dest.strip() == 'Overleden' else 0
        gender = row[i_gender] if (i_gender is not None and i_gender < len(row)) else ''
        d[aid] = {'age': age, 'expire': expire, 'sex': gender}
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

def run_trial(name, key, tx_class, flag, direction, hw, adm):
    seqs = load_labseq(key)
    if not seqs:
        print(f'  {name:28s}: amsterdam_lab_{key}.csv empty/missing — SKIP'); return
    tx = load_tx(tx_class)
    if not tx:
        print(f'  {name:28s}: amsterdam_tx.csv has no "{tx_class}" rows (or file missing) — SKIP '
              f'(EXPECTED for rbc/nahco3/kcl until itemid resolved via dictionary.csv, see module docstring)')
        return

    diffs = []
    for aid, seq in seqs.items():
        rt = tx.get(aid, [])
        for i in range(len(seq) - 1):
            (t1, v1), (t2, v2) = seq[i], seq[i + 1]
            if 0 < t2 - t1 <= 12 and not any(t1 < r <= t2 for r in rt):
                diffs.append(v2 - v1)
    sig = np.std(diffs) / math.sqrt(2) if len(diffs) > 100 else float('nan')

    rows = []
    cross = (lambda v: v < flag) if direction == '<' else (lambda v: v > flag)
    for aid, seq in seqs.items():
        if aid not in adm:
            continue
        rt = tx.get(aid, []); first = rt[0] if rt else float('inf')
        pre = [(t, v) for (t, v) in seq if t < first]
        if len(pre) < 2:
            continue
        (t1, m1), (t2, m2) = pre[0], pre[1]
        rows.append({
            'mid': (m1 + m2) / 2, 'm2': m2,
            'z': 1.0 if cross(m2) else 0.0,
            'd': 1.0 if any(t2 <= r <= t2 + 24 for r in rt) else 0.0,
            'y': float(adm[aid]['expire']),
            'age': adm[aid]['age'],
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

    Dall = np.array([r['d'] for r in rows]); Yall = np.array([r['y'] for r in rows])
    Call = design_controls([r['mid'] for r in rows])
    naive_crude, _ = ols(Yall, np.column_stack([Dall, np.ones_like(Dall)]))
    naive_adj, _ = ols(Yall, np.column_stack([Dall, Call]))

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
    print('=== AmsterdamUMCdb EXTERNAL REPLICATION: assay-noise IV / flag-ITT ===')
    print('headline=flag-ITT(mortality); LATE=implied (ITT/FS) with Anderson-Rubin CI; balAge~0 => exogenous\n')
    print('NOTE: rbc/nahco3/kcl treatment itemids are UNRESOLVED from public sources (insulin IS resolved)')
    print('-- those 3 trials will legitimately SKIP until amsterdam_tx.csv is populated via dictionary.csv.')
    print('Age uses a PLACEHOLDER agegroup->midpoint map -- verify AGEGROUP_MIDPOINT band strings on access.\n')
    adm = load_admissions()
    if not adm:
        print('amsterdam_admissions.csv missing/empty — SKIP all trials (need admissionid, agegroup, gender, destination)')
        return
    for (name, key, tx_class, flag, direction, hw) in CONFIG:
        run_trial(name, key, tx_class, flag, direction, hw, adm)
    print('\nDONE. Interpret: strong FS + balAge~0 + precise ITT => usable; weak FS or balAge!=0 => flag.')
    print('External-replication read: directional agreement with MIMIC-IV/eICU/HiRID/SICdb results on')
    print('flag-ITT sign/magnitude is the confirmatory signal.')

if __name__ == '__main__':
    main()
