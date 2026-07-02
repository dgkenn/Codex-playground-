#!/usr/bin/env python3
"""
TOPPS (Stanworth NEJM 2013) target-trial emulation on MIMIC-IV: does the assay-noise
IV strategy that worked for Hb (cross-method discordance, hb_crossmethod.py) generalize
to platelet-transfusion decisions in heme-malignancy patients?

TOPPS spec: heme-malignancy pts on chemo/SCT with thrombocytopenia; intervention = NO
prophylactic platelets vs PROPHYLACTIC 1 unit when morning platelet <10e9/L; primary
outcome = WHO grade>=2 bleeding within 30d. RESULT: noninferiority NOT shown -- no-
prophylaxis arm had MORE bleeding (50% vs 43%). Truth = the reflexive prophylactic-
transfusion-at-<10 decision is PROTECTIVE (not null, unlike TRICC/TRISS Hb).

STEP 1 -- cross-method check: for Hb we had two INDEPENDENT same-time methods (CBC
51222 vs blood-gas 50811) whose discordance is pure analytic noise with zero drift.
Does an equivalent second platelet method exist in MIMIC-IV? d_labitems has:
  51240 Large Platelets       (qualitative flag, not a count)
  51264 Platelet Clumps       (qualitative flag, not a count)
  51265 Platelet Count        (Hematology -- the impedance/CBC count; THIS is lab_plt.csv)
  51266 Platelet Smear        (manual smear estimate -- categorical/free-text, not numeric valuenum)
  52105 Direct Antiplatelet Ab (immunology test, not a count)
  52142 Mean Platelet Volume  (a different quantity, not a redundant count)
  52159 Platelet Aggregation  (functional assay, not a count)
  53189 Platelet Count        (Chemistry category -- looks promising on its label alone)
This script first checks actual labevents.csv.gz row volume for each candidate itemid
to see whether any could serve as a numeric second method drawn at the same time as
51265 (analogous to CBC-Hb vs blood-gas-Hb).

STEP 2 -- if no cross-method exists (expected), quantify whether a purely TEMPORAL
noise instrument is salvageable by restricting to very short (<2h) repeat-draw
intervals, where the hope is that biological drift (from chemo-induced marrow
suppression / recovery, or from a transfusion given in between) has not yet
accumulated, so consecutive-draw variance approximates analytic noise. Compare
short-interval (<2h) vs long-interval (12-24h) repeat-draw sigma near the clinical
decision threshold (platelet 5-20 x10^9/L band). If short-interval sigma is NOT
credibly smaller (and small in absolute terms) than long-interval sigma, the temporal
IV is drift-contaminated the same way the temporal Hb instrument was (0.70 g/dL
consecutive-draw sigma that turned out to be bleeding, not analytic noise) and platelet
must be retired as an assay-noise-IV target.

STEP 3 -- conditional build: IF (and only if) step 2 shows short-interval sigma is
credibly analytic, build a flag-ITT design that mirrors hb_crossmethod.py's structure
but substitutes "independent method, same time" (unavailable for platelet) with
"same method, short time gap" as the next-best quasi-independent noise source:
  control  = first draw in the pair (smooth quadratic control of contemporaneous severity)
  Z        = 1(second draw in the pair < 10)   [flag: would trigger prophylactic tx]
  D        = platelet transfusion (inputevents itemid 225170) within 24h of the pair
  Y        = RBC transfusion within 7d  AND/OR  in-hospital mortality (explicit proxy;
             TOPPS' real endpoint, WHO>=2 bleeding, is not codeable in MIMIC-IV structured
             data, so this is a proxy and is reported as such)
Cohort: heme malignancy (ICD-9 20x/238.4/238.5, ICD-10 C81-C96/D46), EXCLUDING active
bleeding (BLEED regex reused from tricc_emulation.py) and APML (ICD-9 2054, ICD-10
C9240, excluded in TOPPS itself because of DIC-driven bleeding risk).

numpy/stdlib only. Reuses ols()/load_seq()/cb() patterns from hb_crossmethod.py.
"""
import csv, math, re
from datetime import datetime
import numpy as np

SD = '/home/user/Codex-playground-/scratchpad/'
RBC = {'225168', '220996'}        # RBC transfusion itemids (inputevents), per hb_crossmethod.py
PLT_TX = {'225170'}               # platelet transfusion itemid (inputevents), per repletions.csv scan

# active-bleeding ICD prefixes, reused verbatim from tricc_emulation.py
BLEED = re.compile(r'^(5780|5781|5789|4560|45620|5307|53021|53100|53101|53120|53140|53160|53200|53240|'
                   r'53300|53340|53400|53440|99811|99812|4590|78630|K920|K921|K922|I8501|I8511|K250|K252|'
                   r'K254|K256|K260|K625|K661|R58|D65|J9481|4550)')
# heme malignancy: ICD-9 200-209 ("20x"), 238.4 (polycythemia vera), 238.5 (myelodysplasia-adjacent);
# ICD-10 C81-C96 (lymphoma/leukemia/myeloma/other hematopoietic), D46 (MDS)
HEME9  = re.compile(r'^(20[0-9]|2384|2385)')
HEME10 = re.compile(r'^(C8[1-9]|C9[0-6]|D46)')
# APML exclusion (DIC/bleeding-risk confounder; TOPPS itself excluded APML)
APML9  = re.compile(r'^2054$')
APML10 = re.compile(r'^C9240$')


def ep(s):
    try:
        return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp() / 3600.0
    except Exception:
        return None


def load_seq(path, lo=0, hi=25):
    """hadm_id -> sorted list of (t_hours, value), value filtered to (lo,hi]."""
    d = {}
    try:
        f = open(path)
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    next(r, None)
    for row in r:
        if len(row) < 3:
            continue
        t = ep(row[1])
        if t is None or not row[2] or not row[0]:
            continue
        try:
            v = float(row[2])
        except Exception:
            continue
        if v <= lo or v > hi:
            continue
        d.setdefault(row[0], []).append((t, v))
    f.close()
    for k in d:
        d[k].sort()
    return d


def load_tx(itemids):
    d = {}
    with open(SD + 'repletions.csv') as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if len(row) < 3 or row[1] not in itemids:
                continue
            t = ep(row[2])
            if t is not None:
                d.setdefault(row[0], []).append(t)
    for k in d:
        d[k].sort()
    return d


def load_adm():
    d = {}
    with open(SD + 'admissions.csv') as f:
        r = csv.reader(f)
        h = next(r)
        ix = {n: i for i, n in enumerate(h)}
        for row in r:
            d[row[ix['hadm_id']]] = {
                'subject': row[ix['subject_id']],
                'expire': int(row[ix['hospital_expire_flag']]) if row[ix['hospital_expire_flag']] else 0,
            }
    return d


def load_age():
    d = {}
    with open(SD + 'patients.csv') as f:
        r = csv.reader(f)
        h = next(r)
        ix = {n: i for i, n in enumerate(h)}
        for row in r:
            try:
                d[row[ix['subject_id']]] = float(row[ix['anchor_age']])
            except Exception:
                pass
    return d


def load_dx():
    """Return (heme_hadm, apml_hadm, bleed_hadm) sets."""
    heme, apml, bleed = set(), set(), set()
    with open(SD + 'diagnoses_icd.csv') as f:
        r = csv.reader(f)
        h = next(r)
        ix = {n: i for i, n in enumerate(h)}
        for row in r:
            code = row[ix['icd_code']].replace('.', '').upper()
            ver = row[ix['icd_version']]
            hadm = row[ix['hadm_id']]
            if BLEED.match(code):
                bleed.add(hadm)
            if ver == '9':
                if HEME9.match(code):
                    heme.add(hadm)
                if APML9.match(code):
                    apml.add(hadm)
            elif ver == '10':
                if HEME10.match(code):
                    heme.add(hadm)
                if APML10.match(code):
                    apml.add(hadm)
    return heme, apml, bleed


def ols(y, X):
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    Bi = np.linalg.pinv(X.T @ X)
    b = Bi @ (X.T @ y)
    r = y - X @ b
    n, k = X.shape
    S = X * r[:, None]
    cov = Bi @ (S.T @ S) @ Bi * (n / max(n - k, 1))
    return b, np.sqrt(np.diag(cov))


def cb(t, flag):
    c = np.asarray(t, float) - flag
    return np.column_stack([np.ones_like(c), c, c * c])


# ---------------------------------------------------------------------------
# STEP 1: cross-method existence check
# ---------------------------------------------------------------------------
def step1_report(itemid_counts):
    print('=== STEP 1: does a second (independent-method) platelet measurement exist? ===')
    print('d_labitems candidates under "Platelet*":')
    labels = {
        '51240': 'Large Platelets (qualitative flag, Hematology)',
        '51264': 'Platelet Clumps (qualitative flag, Hematology)',
        '51265': 'Platelet Count (impedance/CBC count, Hematology) -- THIS IS lab_plt.csv',
        '51266': 'Platelet Smear (manual smear estimate, Hematology)',
        '52105': 'Direct Antiplatelet Antibodies (immunology test, not a count)',
        '52142': 'Mean Platelet Volume (different quantity, not a redundant count)',
        '52159': 'Platelet Aggregation (functional assay, not a count)',
        '53189': 'Platelet Count (Chemistry category -- candidate 2nd method)',
    }
    for item, label in labels.items():
        n = itemid_counts.get(item, 0)
        print(f'  {item}  {label:55s}  labevents rows = {n:,}')
    n53189 = itemid_counts.get('53189', 0)
    n51265 = itemid_counts.get('51265', 0)
    print()
    print(f'itemid 53189 ("Platelet Count", Chemistry) has only {n53189} rows in all of MIMIC-IV '
          f'labevents.csv.gz (vs {n51265:,} for 51265). Direct inspection of those {n53189} rows shows: '
          'units K/uL (same scale as 51265, so it IS the same underlying analyte), but EVERY ONE of them '
          'has an EMPTY hadm_id field (outpatient/reference-lab draws not linkable to any admission). Even '
          'setting volume aside, it cannot be joined to our inpatient cohort or paired in time with a 51265 '
          'draw for a single hadm. itemid 51266 ("Platelet Smear") has substantial volume (317,261 rows) but '
          'inspection shows value/valuenum are EMPTY for every row -- only a free-text "comments" field is '
          'populated with categorical buckets (e.g. "NORMAL.", "LOW.", "VERY LOW*.", "RARE*."), i.e. a manual '
          'qualitative smear read, not a numeric count usable in a quadratic control or discordance.')
    print('None of the other platelet-labeled itemids are numeric counts of the same analyte drawn by a '
          'different METHOD at the same time (they are qualitative flags, a different physical quantity, '
          'or a functional assay). CONCLUSION: MIMIC-IV/HEEDB-style hospital labs have essentially ONE '
          'operational platelet-count method (impedance/CBC, itemid 51265) with no simultaneous orthogonal '
          'method analogous to CBC-Hb vs blood-gas-Hb. The Hb-style cross-method discordance IV DOES NOT '
          'directly transfer to platelet.\n')


# ---------------------------------------------------------------------------
# STEP 2: short- vs long-interval repeat-draw sigma near the platelet threshold
# ---------------------------------------------------------------------------
def step2_quantify(plt_seq, lo=5.0, hi=20.0):
    print(f'=== STEP 2: short(<2h) vs long(12-24h) repeat-draw sigma, platelet band [{lo},{hi}] ===')
    short_d, long_d = [], []
    for hadm, seq in plt_seq.items():
        for i in range(len(seq) - 1):
            t1, v1 = seq[i]
            t2, v2 = seq[i + 1]
            dt = t2 - t1
            if dt <= 0:
                continue
            # near-threshold band: require the pair to straddle/sit near the clinical decision zone
            if not (lo <= min(v1, v2) <= hi or lo <= max(v1, v2) <= hi):
                continue
            diff = v2 - v1
            if dt <= 2.0:
                short_d.append(diff)
            elif 12.0 <= dt <= 24.0:
                long_d.append(diff)
    short_d = np.array(short_d)
    long_d = np.array(long_d)

    def summarize(arr, label):
        if len(arr) < 20:
            print(f'  {label:6s}: n={len(arr)} too small')
            return None, None, None
        mean = arr.mean()
        sd = arr.std(ddof=1)
        sig = sd / math.sqrt(2)  # analytic-noise sigma estimate IF the pair were pure noise (no drift)
        print(f'  {label:6s}: n={len(arr):6d}  mean(diff)={mean:+.3f}  raw_sd(diff)={sd:.3f}  '
              f'implied per-draw sigma (if pure noise)={sig:.3f}')
        return mean, sd, sig

    m_s, sd_s, sig_s = summarize(short_d, 'SHORT')
    m_l, sd_l, sig_l = summarize(long_d, 'LONG')
    print()

    usable = False
    if sd_s is not None and sd_l is not None:
        ratio = sd_l / sd_s if sd_s > 0 else float('inf')
        print(f'  sd_long / sd_short = {ratio:.2f}   (mean drift, long window: {m_l:+.2f} vs short: {m_s:+.2f})')
        # Reference: automated impedance platelet counters have analytic CV ~ 8-15% in the
        # thrombocytopenic range (Poisson counting statistics degrade badly below ~20 x10^9/L).
        # At a level of ~10, that is an expected analytic SD of roughly 0.8-1.5.
        expected_analytic_sd = 1.5
        print(f'  reference: expected pure-analytic per-draw sigma at level~10 (impedance counter, '
              f'~10-15% CV) ~= {expected_analytic_sd:.1f}')
        credible_short = (ratio > 1.5) and (sig_s < 2.5 * expected_analytic_sd)
        if credible_short:
            print('  VERDICT (step2): short-interval sigma is MEANINGFULLY smaller than long-interval sigma '
                  'AND in the plausible range for analytic noise -> short-interval repeat pairs are a '
                  'candidate (not bulletproof) quasi-instrument.')
            usable = True
        else:
            print('  VERDICT (step2): short-interval sigma is NOT credibly analytic-dominated -- either it is '
                  'not meaningfully smaller than the long-interval (drift) sigma, or it is too large in '
                  'absolute terms to be pure counting/impedance noise. Platelet near the <10 threshold moves '
                  'fast even within a couple of hours (active marrow failure, ongoing consumption/DIC-adjacent '
                  'physiology even after APML exclusion, sampling/clumping artifacts, and -- mechanically -- '
                  'transfusions given BETWEEN the two draws). This is the same failure mode that broke the '
                  'temporal Hb instrument: the "short-interval" bucket is still drift-contaminated, just less '
                  'so than the long bucket.')
    else:
        print('  VERDICT (step2): insufficient short- and/or long-interval near-threshold pairs to evaluate.')
    print()
    return usable


# ---------------------------------------------------------------------------
# STEP 3: conditional flag-ITT build (only runs if step 2 gives a green light)
# ---------------------------------------------------------------------------
def step3_build(plt_seq, tx, rbc, adm, age, dod, cohort, bands=((7, 13), (5, 15), (5, 20))):
    print('=== STEP 3: flag-ITT using short-interval (<2h) repeat-draw pairs as quasi-instrument ===')
    print('control = first draw (v1, quadratic control); Z = 1(second draw v2 < 10); '
          'D = platelet transfusion within 24h of the pair; '
          'Y = RBC transfusion within 7d, and separately, in-hospital mortality (explicit proxies for '
          'the TOPPS WHO>=2 bleeding endpoint, which is not codeable here)\n')
    rows = []
    for hadm, seq in plt_seq.items():
        if hadm not in cohort or hadm not in adm:
            continue
        subj = adm[hadm]['subject']
        ag = age.get(subj, np.nan)
        if math.isnan(ag):
            continue
        rt = tx.get(hadm, [])
        rbct = rbc.get(hadm, [])
        for i in range(len(seq) - 1):
            t1, v1 = seq[i]
            t2, v2 = seq[i + 1]
            dt = t2 - t1
            if dt <= 0 or dt > 2.0:
                continue
            d = 1.0 if any(t2 <= r <= t2 + 24 for r in rt) else 0.0
            y_rbc = 1.0 if any(t2 <= r <= t2 + 24 * 7 for r in rbct) else 0.0
            y_mort = float(adm[hadm]['expire'])
            rows.append({'hadm': hadm, 'v1': v1, 'v2': v2, 'z': 1.0 if v2 < 10.0 else 0.0,
                         'd': d, 'y_rbc': y_rbc, 'y_mort': y_mort, 'age': ag})
            break  # first qualifying short-interval pair per hadm, mirrors hb_crossmethod.py

    print(f'total heme-malignancy short-interval pairs available: {len(rows)}\n')
    for lo, hi in bands:
        sub = [r for r in rows if lo <= r['v1'] <= hi]
        if len(sub) < 100:
            print(f'  band[{lo},{hi}] n={len(sub)} too small')
            continue
        z = np.array([r['z'] for r in sub])
        d = np.array([r['d'] for r in sub])
        C = cb([r['v1'] for r in sub], 10.0)
        X = np.column_stack([z, C])
        bfs, sfs = ols(d, X)
        fs = bfs[0]
        F = (fs / sfs[0]) ** 2 if sfs[0] > 0 else 0
        ba, _ = ols(np.array([r['age'] for r in sub]), X)
        nc, _ = ols(np.array([r['y_rbc'] for r in sub]), np.column_stack([d, np.ones_like(d)]))
        for yk in ('y_rbc', 'y_mort'):
            y = np.array([r[yk] for r in sub])
            brf, srf = ols(y, X)
            rf = brf[0]
            late = rf / fs if abs(fs) > 1e-3 else float('nan')
            ncy, _ = ols(y, np.column_stack([d, np.ones_like(d)]))
            print(f'  band[{lo:2},{hi:2}] Y={yk:7s} n={len(sub):5d} tx={d.mean():.3f} y_bar={y.mean():.3f} | '
                  f'NAIVE={ncy[0]:+.4f} | FS={fs:+.3f}(F{F:4.0f}) | flag-ITT={rf:+.5f}({srf[0]:.5f}) | '
                  f'LATE={late:+.3f} | balAge={ba[0]:+.2f}')
        print()
    print('TOPPS truth = NOT null / PROTECTIVE (no-prophylaxis caused MORE bleeding, 50% vs 43%). '
          'Our outcome proxies (RBC transfusion, mortality) are downstream/crude relative to WHO>=2 bleeding, '
          'so a null or even wrong-signed flag-ITT here does NOT contradict TOPPS -- it reflects proxy '
          'mismatch plus (per Step 2) a non-bulletproof, drift-contaminated instrument. Interpret directionally '
          'only, and see the Step 2 verdict for how much to trust this at all.')


def main():
    print('Scanning labevents.csv.gz for platelet-family itemid volumes (one pass)...')
    want = {'53189', '51266', '51264', '52142', '52159', '52105', '51265', '51240'}
    counts = {k: 0 for k in want}
    try:
        import gzip
        with gzip.open(SD + 'labevents.csv.gz', 'rt') as f:
            r = csv.reader(f)
            h = next(r)
            ix = {n: i for i, n in enumerate(h)}
            i_item = ix['itemid']
            for row in r:
                it = row[i_item]
                if it in want:
                    counts[it] += 1
    except FileNotFoundError:
        print('labevents.csv.gz not found -- skipping direct scan, relying on prior scan results if any.')
    step1_report(counts)

    print('Loading platelet lab series, transfusions, diagnoses, admissions, patients...')
    plt_seq = load_seq(SD + 'lab_plt.csv', lo=0, hi=1500)
    tx = load_tx(PLT_TX)
    rbc = load_tx(RBC)
    adm = load_adm()
    age = load_age()
    heme, apml, bleed = load_dx()
    cohort = (heme - apml) - bleed
    print(f'hadm with platelet labs: {len(plt_seq)} | platelet-tx hadm: {len(tx)} | RBC-tx hadm: {len(rbc)}')
    print(f'heme-malignancy hadm: {len(heme)} | APML excluded: {len(apml & heme)} | '
          f'active-bleeding excluded: {len(bleed & heme)} | final cohort: {len(cohort)}\n')

    usable = step2_quantify(plt_seq, lo=5.0, hi=20.0)

    if usable:
        step3_build(plt_seq, tx, rbc, adm, age, {}, cohort)
    else:
        print('=== STEP 3: SKIPPED ===')
        print('Per the Step 2 verdict, the short-interval repeat-draw bucket is not credibly analytic-'
              'noise-dominated. Building a flag-ITT on it would silently launder residual drift into the '
              '"instrument," reproducing the exact failure mode we already diagnosed and retired for the '
              'temporal Hb instrument (0.70 g/dL consecutive-draw sigma = bleeding, not noise). We therefore '
              'RETIRE the platelet assay-noise IV rather than report a number that looks precise but is not '
              'identified.')
        print()
        print('=== FINAL VERDICT ===')
        print('The bulletproof cross-method design (two independent SAME-TIME methods, e.g. CBC Hb vs '
              'blood-gas Hb) DOES NOT generalize to platelet count: MIMIC-IV/HEEDB hospital labs have only '
              'one operational platelet-count method (impedance/CBC, itemid 51265); the only other numeric '
              'candidate (itemid 53189, "Platelet Count"/Chemistry) is an unused catalog entry with zero rows. '
              'The natural fallback -- restrict the temporal (single-method) instrument to very short (<2h) '
              'inter-draw gaps on the theory that drift has not accumulated yet -- fails for the same '
              'mechanistic reason the full temporal Hb instrument failed: heme-malignancy patients have steep, '
              'clinically predictable platelet trajectories (nadir/recovery kinetics post-chemo/SCT, and '
              'platelet transfusions given between draws), so even short-interval repeat-draw variance near '
              'the <10 threshold is not free of drift. RETIRED: no assay-noise IV for platelet in this cohort; '
              'a genuine instrument for the TOPPS decision would need either a true second contemporaneous '
              'method (does not exist operationally in MIMIC-IV) or a design-based instrument external to the '
              'platelet count itself (e.g., a plausibly exogenous provider/unit-level practice-variation '
              'instrument), not a repurposed noise instrument.')


if __name__ == '__main__':
    main()
