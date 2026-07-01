#!/usr/bin/env python3
"""
Stream INSPIRE labs.csv from stdin (PLAIN csv — NOT gzipped, unlike MIMIC/eICU), filter to the
analytes needed for the assay-noise IV / flag-ITT replication, write compact per-analyte CSVs.
Disk-sparing: only subject_id,chart_time,item_name,value are retained (already the full row —
labs.csv has no extra columns to drop).

INSPIRE v1.3 labs.csv columns (confirmed via header stream + schema.csv, 2026-07):
  subject_id, chart_time, item_name, value
  - subject_id: patient identifier (joins to operations.csv subject_id)
  - chart_time: Relative Time in SECONDS from hospital admission (admission_time==0 anchor in
    operations.csv; verified: raw offsets are absurd as minutes [years-long "stays"] but sane as
    seconds [hours-to-days]) — NOTE this differs from MIMIC (charttime timestamp string) and
    eICU (offset in MINUTES); inspire_run.py converts seconds -> hours by /3600.
  - item_name: analyte label, confirmed present in labs.csv: hb, glucose, platelet, hco3,
    potassium, calcium, phosphorus, ica (ionized calcium), ptinr, and others (see schema.csv).
    NOTE: there is NO 'magnesium' item in labs.csv — INSPIRE does not report serum magnesium as a
    lab analyte (confirmed by sampling ~500k+ rows; parameters.csv/schema.csv enumerate the full
    fixed vocabulary and magnesium is absent). Mg repletion trial is therefore NOT RUNNABLE here.
  - value: numeric result, units per parameters.csv (hb g/dL, glucose mg/dL, platelet /nL i.e.
    equivalent to K/uL used by MIMIC/eICU, hco3 mmol/L, potassium mmol/L) — SAME units/flags as
    the MIMIC (portfolio_run.py) and eICU (eicu_run.py) engines, no unit conversion needed.
"""
import sys, csv

# item_name (as it appears in INSPIRE labs.csv) -> short key used by inspire_run.py / filenames
WANT = {
    'hb':         'hb',    # hemoglobin -> RBC transfusion trial
    'glucose':    'glu',   # glucose -> insulin trial
    'platelet':   'plt',   # platelet count -> platelet transfusion trial
    'hco3':       'hco3',  # HCO3 (ABG) -> bicarbonate/acidosis trial
    'potassium':  'k',     # potassium -> potassium repletion (secondary/context)
    # NOTE: no 'magnesium' item_name exists in INSPIRE labs.csv (verified absent from the fixed
    # vocabulary in schema.csv/parameters.csv) -> Mg repletion trial cannot be built from labs.
}

SD = '/home/user/Codex-playground-/scratchpad/'
KEYS = sorted(set(WANT.values()))
out = {k: open(SD + f'inspire_lab_{k}.csv', 'w', newline='') for k in KEYS}
wr = {k: csv.writer(out[k]) for k in KEYS}
for k in KEYS:
    wr[k].writerow(['subject_id', 'chart_time', 'item_name', 'value'])

r = csv.reader(sys.stdin)
header = next(r)
# INSPIRE csv files are UTF-8-with-BOM (confirmed: raw bytes start EF BB BF); stdin text mode
# does not strip it, so the first header cell would otherwise read as '﻿subject_id'.
header = [h.lstrip('﻿') for h in header]
# INSPIRE labs.csv header: subject_id,chart_time,item_name,value
idx = {name: i for i, name in enumerate(header)}
i_sid = idx['subject_id']
i_ct = idx['chart_time']
i_name = idx['item_name']
i_val = idx['value']

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
    sid = row[i_sid]
    ct = row[i_ct]
    val = row[i_val]
    if sid and ct and val:
        wr[key].writerow([sid, ct, name, val])
        kept += 1
    if n % 5_000_000 == 0:
        sys.stderr.write(f'  scanned {n:,} rows, kept {kept:,}\n')
        sys.stderr.flush()

for f in out.values():
    f.close()
sys.stderr.write(f'DONE scanned {n:,} rows, kept {kept:,}\n')
