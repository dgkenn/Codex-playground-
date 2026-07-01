#!/usr/bin/env python3
"""
Stream eICU-CRD lab.csv.gz from stdin (gunzipped), filter to the labnames needed for the
assay-noise IV / flag-ITT replication, write compact per-analyte CSVs.
Disk-sparing: only patientunitstayid,labresultoffset,labname,labresult are retained.

eICU-CRD v2.0 lab.csv.gz columns (subset used):
  patientunitstayid, labresultoffset (minutes from ICU admit), labname, labresult

Mirrors scratchpad/stream_labs.py (MIMIC) but keyed by labname string instead of itemid,
and offset is already minutes-from-admit (no timestamp parsing needed).
"""
import sys, csv

# labname (as it appears in eICU-CRD) -> short key used by eicu_run.py / output filenames
WANT = {
    'Hgb':                'hb',    # hemoglobin -> RBC transfusion trial
    'glucose':             'glu',  # chemistry glucose -> insulin trial
    'bedside glucose':     'glu',  # point-of-care glucose -> same trial/key (merged)
    'platelets x 1000':    'plt',  # platelet transfusion trial
    'HCO3':                'hco3', # bicarbonate -> acidosis-correction trial
    'potassium':           'k',    # potassium repletion (secondary/context)
    'magnesium':           'mg',   # magnesium repletion (secondary/context)
}

SD = '/home/user/Codex-playground-/scratchpad/'
KEYS = sorted(set(WANT.values()))
out = {k: open(SD + f'eicu_lab_{k}.csv', 'w', newline='') for k in KEYS}
wr = {k: csv.writer(out[k]) for k in KEYS}
for k in KEYS:
    wr[k].writerow(['patientunitstayid', 'labresultoffset', 'labname', 'labresult'])

r = csv.reader(sys.stdin)
header = next(r)
# eICU-CRD lab.csv.gz header (2.0):
# labid,patientunitstayid,labresultoffset,labtypeid,labname,labresult,labresulttext,
# labmeasurenamesystem,labmeasurenameinterface,labresultrevisedoffset,labotherresult,labotheruom
idx = {name: i for i, name in enumerate(header)}
i_pid = idx['patientunitstayid']
i_off = idx['labresultoffset']
i_name = idx['labname']
i_val = idx['labresult']

n = 0
kept = 0
for row in r:
    n += 1
    try:
        name = row[i_name]
    except IndexError:
        continue
    key = WANT.get(name)
    if key is None:
        continue
    pid = row[i_pid]
    off = row[i_off]
    val = row[i_val]
    if pid and off and val:
        wr[key].writerow([pid, off, name, val])
        kept += 1
    if n % 5_000_000 == 0:
        sys.stderr.write(f'  scanned {n:,} rows, kept {kept:,}\n')
        sys.stderr.flush()

for f in out.values():
    f.close()
sys.stderr.write(f'DONE scanned {n:,} rows, kept {kept:,}\n')
