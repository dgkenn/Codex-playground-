#!/usr/bin/env python3
"""
Negative-control OUTCOME panel from diagnoses_icd. Produces per-hadm indicators for ~15 diagnoses
that the studied drugs cannot plausibly cause (chronic/unrelated) -> used to fit the empirical null
(Schuemie) and calibrate every preference-IV / gate estimate. Writes nc_outcomes.csv (hadm_id + flags).
"""
import csv
SD = '/home/user/Codex-playground-/scratchpad/'
# ICD-10 prefixes for clearly-unrelated conditions (negative controls); ICD-9 rough equivalents added.
NC = {
    'cataract':   ('H25', 'H26', '366'),
    'glaucoma':   ('H40', '365'),
    'knee_oa':    ('M17', '71596'),
    'hip_oa':     ('M16', '71595'),
    'spondylosis':('M47', '721'),
    'dorsalgia':  ('M54', '724'),
    'sebkeratosis':('L82', '7021'),
    'benign_nevus':('D22', '2160'),
    'bph':        ('N40', '600'),
    'hearing_loss':('H90', 'H91', '389'),
    'refraction': ('H52', '367'),
    'deviated_septum':('J342', '4702'),
    'inguinal_hernia':('K40', '550'),
    'onychomycosis':('B351', '1101'),
    'hemorrhoids':('K64', 'I84', '455'),
}
keys = list(NC)
def match(code):
    c = code.replace('.', '').upper()
    for k, pref in NC.items():
        if any(c.startswith(p) for p in pref): return k
    return None

def main():
    per = {}
    try: f = open(SD+'diagnoses_icd.csv')
    except FileNotFoundError:
        print('diagnoses_icd.csv missing — SKIP'); return
    r = csv.reader(f); hdr = next(r); ix = {n:i for i,n in enumerate(hdr)}
    ih, icd = ix['hadm_id'], ix['icd_code']
    for row in r:
        k = match(row[icd])
        if k:
            per.setdefault(row[ih], set()).add(k)
    f.close()
    out = open(SD+'nc_outcomes.csv', 'w', newline='')
    w = csv.writer(out); w.writerow(['hadm_id'] + keys)
    for hadm, s in per.items():
        w.writerow([hadm] + [1 if k in s else 0 for k in keys])
    out.close()
    print(f'nc_outcomes.csv: {len(per)} hadm with >=1 NC dx, {len(keys)} controls')

if __name__ == '__main__':
    main()
