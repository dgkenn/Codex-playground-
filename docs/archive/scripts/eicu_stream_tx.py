#!/usr/bin/env python3
"""
Stream eICU-CRD treatment.csv.gz from stdin (gunzipped), filter treatmentstring to the
tx classes needed for the assay-noise IV / flag-ITT replication, write one compact CSV.
Disk-sparing: only patientunitstayid,treatmentoffset,tx_class are retained.

eICU-CRD v2.0 treatment.csv.gz columns (subset used):
  patientunitstayid, treatmentoffset (minutes from ICU admit), treatmentstring (hierarchical,
  pipe-delimited, e.g. '...|transfusion of packed red blood cells',
  '...|electrolyte correction|...magnesium')

Mirrors scratchpad/stream_rx.py (MIMIC prescriptions) but matches on treatmentstring
substrings instead of drug names, and offset is already minutes-from-admit.
insulin is NOT typically in treatment.csv.gz treatmentstring in eICU-CRD (it's under
infusionDrug/medication) — matched here too in case it appears under an
'endocrine|...insulin' treatmentstring branch; eicu_run.py falls back to
infusionDrug/medication if this file has no insulin rows (see SKIP-guard there).
"""
import sys, csv, re

# tx_class -> regex over lowercased treatmentstring
CLASSES = [
    ('rbc',   re.compile(r'transfusion of packed red blood cells|packed red blood cells')),
    ('plt',   re.compile(r'platelet')),
    ('hco3',  re.compile(r'bicarbonate')),
    ('mg',    re.compile(r'magnesium')),
    ('k',     re.compile(r'potassium')),
    ('insulin', re.compile(r'insulin')),
]

SD = '/home/user/Codex-playground-/scratchpad/'
out = open(SD + 'eicu_tx.csv', 'w', newline='')
wr = csv.writer(out)
wr.writerow(['patientunitstayid', 'treatmentoffset', 'tx_class'])

r = csv.reader(sys.stdin)
header = next(r)
# eICU-CRD treatment.csv.gz header (2.0):
# treatmentid,patientunitstayid,treatmentoffset,treatmentstring,activeupondischarge
idx = {name: i for i, name in enumerate(header)}
i_pid = idx['patientunitstayid']
i_off = idx['treatmentoffset']
i_str = idx['treatmentstring']

n = 0
kept = 0
for row in r:
    n += 1
    try:
        ts = row[i_str]
    except IndexError:
        continue
    tsl = ts.lower()
    pid = row[i_pid]
    off = row[i_off]
    if not pid or not off:
        continue
    for cls, rx in CLASSES:
        if rx.search(tsl):
            wr.writerow([pid, off, cls])
            kept += 1
            break
    if n % 2_000_000 == 0:
        sys.stderr.write(f'  scanned {n:,} rows, kept {kept:,}\n')
        sys.stderr.flush()

out.close()
sys.stderr.write(f'DONE scanned {n:,} rows, kept {kept:,}\n')
