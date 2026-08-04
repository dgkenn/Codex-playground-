#!/usr/bin/env python3
"""Stream MIMIC-IV icu/chartevents.csv.gz from stdin (gunzipped), filter to the
vitals itemids needed for MAP-target / vasopressor-eligibility instruments
(ADRENAL BP-target gate; a MIMIC-native SEPSISPAM-style MAP design; PREVENT/vent
support). Disk-sparing: only stay_id,hadm_id,charttime,valuenum retained.
"""
import sys, csv

WANT = {
    '220052': 'abpm',    # Arterial BP mean (invasive, gold-standard MAP)
    '220050': 'abps',    # Arterial BP systolic
    '220051': 'abpd',    # Arterial BP diastolic
    '220181': 'nbpm',    # Non-invasive BP mean
    '220179': 'nbps',    # Non-invasive BP systolic
    '220180': 'nbpd',    # Non-invasive BP diastolic
    '220045': 'hr',      # Heart rate
    '220277': 'spo2',    # SpO2
    '220210': 'rr',      # Respiratory rate
}
out = {k: open(f'/home/user/Codex-playground-/scratchpad/chart_{v}.csv', 'w', newline='')
       for k, v in WANT.items()}
wr = {k: csv.writer(out[k]) for k in WANT}
for k in WANT:
    wr[k].writerow(['hadm_id', 'stay_id', 'charttime', 'valuenum'])

r = csv.reader(sys.stdin)
header = next(r)
# icu/chartevents columns: subject_id,hadm_id,stay_id,caregiver_id,charttime,
#                          storetime,itemid,value,valuenum,valueuom,warning
idx = {name: i for i, name in enumerate(header)}
i_item = idx['itemid']; i_hadm = idx['hadm_id']; i_stay = idx['stay_id']
i_ct = idx['charttime']; i_vn = idx['valuenum']
n = 0; kept = 0
for row in r:
    n += 1
    it = row[i_item]
    if it in WANT:
        vn = row[i_vn]
        hadm = row[i_hadm]
        if vn and hadm:
            wr[it].writerow([hadm, row[i_stay], row[i_ct], vn])
            kept += 1
    if n % 20_000_000 == 0:
        sys.stderr.write(f'  scanned {n:,} rows, kept {kept:,}\n'); sys.stderr.flush()
for f in out.values():
    f.close()
sys.stderr.write(f'DONE scanned {n:,} rows, kept {kept:,}\n')
