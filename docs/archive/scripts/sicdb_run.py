#!/usr/bin/env python3
"""
SICdb (Salzburg, Austria; PhysioNet "sicdb" v1.0.6) EXTERNAL REPLICATION of the assay-noise IV /
flag-ITT engine (mirrors /home/user/Codex-playground-/docs/portfolio_run.py and docs/eicu_run.py) for
the lab-flag-triggered benchmark cases.

*** MAPPING STATUS (see docs/MULTISITE_HARMONIZATION.md for full citations): ***
Labs are MEDIUM CONFIDENCE (ricu-only; no public source enumerates SICdb LaboratoryIDs directly — the
SICdb docs wiki explicitly declines to list them and instead shows the SQL join pattern against
d_references). ALL FOUR treatment/DrugIDs (RBC, insulin, NaHCO3, KCl) are TO-CONFIRM-ON-ACCESS: SICdb's
`medication` table is 100% reference-coded via d_references and no public source (docs wiki, paper, or
the ricu snippet reachable here) enumerates concrete DrugIDs. This is the WEAKEST-MAPPED of the three
external-replication datasets on the treatment side — budget real day-one time to resolve it (see the
fetch-and-grep recipe below).

  RBC transfusion      @ Hgb < 7        (TRICC/TRISS validation)     -- lab id medium-conf, tx id TODO
  Insulin              @ glucose > 180  (NICE-SUGAR validation)      -- lab id medium-conf, tx id TODO
  Bicarbonate          @ HCO3 < 15      (acidosis correction)        -- lab id medium-conf, tx id TODO
  Potassium chloride   @ K < 3.5        (repletion; context)         -- lab id medium-conf, tx id TODO
  Magnesium repletion  @ Mg < 2.0                                    -- lab id present in ricu (unlike
                                                                          HiRID's mg); tx id also TODO

Design (identical to the MIMIC/eICU/HiRID engines, restated for SICdb's SECONDS-FROM-ADMISSION clock —
like eICU's minutes and AmsterdamUMCdb's milliseconds, no datetime parsing needed, just an offset scale):
  - M1, M2 = first two pre-treatment lab draws (laboratory.Offset, seconds from ICU admission)
  - instrument Z = 1(M2 crosses the flag in the de-implementation direction)
  - severity control = midpoint (M1+M2)/2, local-linear (2nd-order) control function of (mid - flag)
  - D = 1(treatment of the matching class occurs within 24h of M2)
  - primary outcome Y = hospital mortality
  - reports: n, noise sigma, first-stage F, flag-ITT (headline), implied-LATE with Anderson-Rubin CI,
    covariate balance (age), M2 density/heaping (McCrary-style), and the NAIVE (confounded) D->mortality
    contrast (crude + severity-adjusted) for comparison.

=== ID MAPPINGS (see docs/MULTISITE_HARMONIZATION.md; ricu concept-dict.json, github.com/eth-mds/ricu) ===
Labs (laboratory.LaboratoryID -> d_references.ReferenceGlobalID), units TO-CONFIRM against d_references:
  hb    : 658, 289
  glu   : 348, 656
  hco3  : 451, 456, 666, 667
  k     : 463, 685
  mg    : 464, 688
Treatments (medication.DrugID): *** NONE CONFIRMED -- ALL TODO, see fetch-and-grep recipe below ***
  rbc     : TODO -- grep d_references.ReferenceValue for 'Erythrozyten'/'EK'/'Blutkonserve'
  insulin : TODO -- grep d_references.ReferenceValue for 'Insulin'
  nahco3  : TODO -- grep d_references.ReferenceValue for 'Bicarbonat'/'NaHCO3'
  kcl     : TODO -- grep d_references.ReferenceValue for 'Kalium'/'KCl'
Patient (cases table):
  age       : cases.AgeOnAdmission          (years, rounded +/-5, >90 capped at 90 -- COARSER than
                                              HiRID/MIMIC/eICU; expect noisier balAge by construction)
  sex       : cases.Sex OR cases.Gender (ricu's sic source config names the column "Gender" with
                                          callback M='m'/F='f'; SICdb docs wiki prose says "Sex" --
                                          RECONCILE the exact column name against the real header on
                                          access, both likely the same field)
  mortality : cases.HospitalDischargeType (reference-coded survival status; RECOMMENDED PRIMARY) or
              cases.OffsetOfDeath non-null (seconds from admission to death, but this is a *1-year*
              mortality field per docs, not strictly in-hospital -- needs a <= TimeOfStay-type bound;
              TO-CONFIRM exact thresholding on access, see MULTISITE_HARMONIZATION.md)
Timestamps: laboratory.Offset, medication.Offset/OffsetDrugEnd, cases.ICUOffset/TimeOfStay are all
INTEGER SECONDS from ICU admission (no datetime parsing needed, unlike HiRID).

=== EXACT FETCH COMMANDS (fill in your PhysioNet credentials via ~/.netrc) ===
# THE CRITICAL DAY-ONE FILE -- resolves all 4 TODO treatment ids and confirms lab units:
wget -N -c --netrc -P ./sicdb_raw https://physionet.org/files/sicdb/1.0.6/d_references.csv.gz
# Then: gunzip and grep/join against ReferenceValue for drug names (see recipe in module docstring
# above); this MUST be done before trusting any 'rbc'/'insulin'/'nahco3'/'kcl' tx_class row below.
wget -N -c --netrc -P ./sicdb_raw https://physionet.org/files/sicdb/1.0.6/laboratory.csv.gz
wget -N -c --netrc -P ./sicdb_raw https://physionet.org/files/sicdb/1.0.6/medication.csv.gz
wget -N -c --netrc -P ./sicdb_raw https://physionet.org/files/sicdb/1.0.6/cases.csv.gz
# Documentation (already used for the schema notes above, but re-check for updates):
wget -N -c --netrc -P ./sicdb_raw https://physionet.org/content/sicdb/1.0.6/

Inputs expected here (produced by a sicdb_stream_lab.py / sicdb_stream_tx.py stream-filter step,
mirroring eicu_stream_lab.py/eicu_stream_tx.py -- TODO: write those once d_references join is resolved):
  sicdb_lab_hb.csv, sicdb_lab_glu.csv, sicdb_lab_hco3.csv, sicdb_lab_k.csv, sicdb_lab_mg.csv
    columns: CaseID, Offset, LaboratoryID, LaboratoryValue
  sicdb_tx.csv
    columns: CaseID, Offset, tx_class   (tx_class in {rbc, insulin, nahco3, kcl} -- CANNOT BE
    POPULATED until the d_references grep above resolves concrete DrugIDs)
  sicdb_cases.csv (renamed from raw cases.csv.gz to a sicdb_-prefixed name for consistency with the
  other adapters and to avoid ambiguity with per-dataset scratchpad files)
    columns used: CaseID, AgeOnAdmission, Sex (or Gender), HospitalDischargeType (or OffsetOfDeath)

Missing input files => SKIP, no crash (same contract as eicu_run.py). Given the treatment-id gap, EXPECT
ALL TRIALS TO SKIP on first run until sicdb_tx.csv can be populated -- this is a known, documented
limitation of the public-source mapping, not a bug in this script.
"""
import csv, math
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'

# (name, lab_csv_key, tx_class, flag, direction '<'|'>', bandwidth)
# Units TO-CONFIRM against d_references.ReferenceUnit (assumed g/dL, mg/dL, mEq/L by analogy with the
# other sites pending verification).
CONFIG = [
    ('RBC transfusion (Hgb<7)',        'hb',   'rbc',     7.0,  '<', 0.60),
    ('Insulin (glucose>180)',          'glu',  'insulin', 180,  '>', 25),
    ('Bicarbonate (acidosis, <15)',    'hco3', 'nahco3',  15.0, '<', 3.0),
    ('Potassium chloride (K<3.5)',     'k',    'kcl',     3.5,  '<', 0.25),
    ('Magnesium repletion (Mg<2.0)',   'mg',   'mg',      2.0,  '<', 0.15),
]

def load_labseq(key):
    """Offset in seconds -> hours, mirroring eicu_run.py's minutes->hours conversion."""
    d = {}
    try:
        f = open(SD + f'sicdb_lab_{key}.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 4:
            continue
        cid, off, _labid, vn = row[0], row[1], row[2], row[3]
        if not cid or not off or not vn:
            continue
        try:
            t = float(off) / 3600.0  # seconds -> hours
            v = float(vn)
        except ValueError:
            continue
        d.setdefault(cid, []).append((t, v))
    f.close()
    for k in d:
        d[k].sort()
    return d

def load_tx(cls):
    d = {}
    try:
        f = open(SD + 'sicdb_tx.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 3:
            continue
        cid, off, c = row[0], row[1], row[2]
        if c != cls or not cid or not off:
            continue
        try:
            t = float(off) / 3600.0  # seconds -> hours
        except ValueError:
            continue
        d.setdefault(cid, []).append(t)
    f.close()
    for k in d:
        d[k].sort()
    return d

def load_cases():
    """sicdb_cases.csv (renamed from raw cases.csv.gz): CaseID, AgeOnAdmission, Sex/Gender, HospitalDischargeType (or OffsetOfDeath).
    mortality: prefer a reference-coded discharge-type match against a 'dead'/'deceased'-like value;
    TO-CONFIRM exact ReferenceValue string on access (join HospitalDischargeType -> d_references first).
    Falls back to OffsetOfDeath non-null if HospitalDischargeType column absent (TO-CONFIRM this proxy —
    OffsetOfDeath is documented as a 1-year mortality window, broader than in-hospital; using it as a
    stand-in will need a same-admission bound, e.g. OffsetOfDeath <= TimeOfStay, once TimeOfStay is
    available in this CSV).
    """
    d = {}
    try:
        f = open(SD + 'sicdb_cases.csv')
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    hdr = next(r)
    idx = {n: i for i, n in enumerate(hdr)}
    if 'CaseID' not in idx:
        print('  sicdb_cases.csv present but missing "CaseID" column (wrong file/schema?) — SKIP all trials')
        f.close()
        return d
    i_cid = idx['CaseID']
    i_age = idx.get('AgeOnAdmission')
    i_sex = idx.get('Sex', idx.get('Gender'))
    i_disch = idx.get('HospitalDischargeType')
    i_death_off = idx.get('OffsetOfDeath')
    for row in r:
        cid = row[i_cid]
        try:
            age = float(row[i_age]) if i_age is not None else float('nan')
        except (ValueError, IndexError):
            age = float('nan')
        sex = row[i_sex] if (i_sex is not None and i_sex < len(row)) else ''
        expire = 0
        if i_disch is not None and i_disch < len(row) and row[i_disch]:
            # TODO: this compares the RAW (still reference-coded) value; replace with the resolved
            # d_references.ReferenceValue string match for "deceased"/"dead" once the join is done.
            expire = 1 if row[i_disch].strip().lower() in ('dead', 'deceased', 'died') else 0
        elif i_death_off is not None and i_death_off < len(row) and row[i_death_off]:
            expire = 1
        d[cid] = {'age': age, 'expire': expire, 'sex': sex}
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

def run_trial(name, key, tx_class, flag, direction, hw, cases):
    seqs = load_labseq(key)
    if not seqs:
        print(f'  {name:28s}: sicdb_lab_{key}.csv empty/missing — SKIP'); return
    tx = load_tx(tx_class)
    if not tx:
        print(f'  {name:28s}: sicdb_tx.csv has no "{tx_class}" rows (or file missing) — SKIP '
              f'(EXPECTED until DrugID for {tx_class} is resolved via d_references, see module docstring)')
        return

    diffs = []
    for cid, seq in seqs.items():
        rt = tx.get(cid, [])
        for i in range(len(seq) - 1):
            (t1, v1), (t2, v2) = seq[i], seq[i + 1]
            if 0 < t2 - t1 <= 12 and not any(t1 < r <= t2 for r in rt):
                diffs.append(v2 - v1)
    sig = np.std(diffs) / math.sqrt(2) if len(diffs) > 100 else float('nan')

    rows = []
    cross = (lambda v: v < flag) if direction == '<' else (lambda v: v > flag)
    for cid, seq in seqs.items():
        if cid not in cases:
            continue
        rt = tx.get(cid, []); first = rt[0] if rt else float('inf')
        pre = [(t, v) for (t, v) in seq if t < first]
        if len(pre) < 2:
            continue
        (t1, m1), (t2, m2) = pre[0], pre[1]
        rows.append({
            'mid': (m1 + m2) / 2, 'm2': m2,
            'z': 1.0 if cross(m2) else 0.0,
            'd': 1.0 if any(t2 <= r <= t2 + 24 for r in rt) else 0.0,
            'y': float(cases[cid]['expire']),
            'age': cases[cid]['age'],
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
    print('=== SICdb EXTERNAL REPLICATION: assay-noise IV / flag-ITT ===')
    print('headline=flag-ITT(mortality); LATE=implied (ITT/FS) with Anderson-Rubin CI; balAge~0 => exogenous\n')
    print('NOTE: all 4 treatment DrugIDs are UNRESOLVED from public sources (see module docstring) --')
    print('every trial below will legitimately SKIP until sicdb_tx.csv is populated via the d_references')
    print('join. Age is +/-5y-binned (coarser than other sites) -- balAge will be noisier by construction.\n')
    cases = load_cases()
    if not cases:
        print('sicdb_cases.csv missing/empty — SKIP all trials (need CaseID, AgeOnAdmission, Sex/Gender, '
              'HospitalDischargeType/OffsetOfDeath)')
        return
    for (name, key, tx_class, flag, direction, hw) in CONFIG:
        run_trial(name, key, tx_class, flag, direction, hw, cases)
    print('\nDONE. Interpret: strong FS + balAge~0 + precise ITT => usable; weak FS or balAge!=0 => flag.')
    print('External-replication read: directional agreement with MIMIC-IV/eICU/HiRID results on')
    print('flag-ITT sign/magnitude is the confirmatory signal.')

if __name__ == '__main__':
    main()
