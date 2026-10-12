#!/usr/bin/env python3
"""
Stream INSPIRE treatment signals from stdin (PLAIN csv, NOT gzipped) and filter to the tx
classes needed for the assay-noise IV / flag-ITT replication, appending to one compact CSV
(inspire_tx.csv: subject_id, chart_time, tx_class).

UNLIKE MIMIC/eICU, INSPIRE splits treatment-of-interest across TWO different tables — there is
no single medications/treatment table with everything:
  - Blood products (RBC, platelet concentrate, FFP, cryoprecipitate) are recorded in
    vitals.csv as dense per-op_id numeric CHANNELS (item_name in {rbc, pc, ffp, cryo}, unit=
    "Unit" per parameters.csv), sampled roughly every few minutes with a nonzero value marking
    a transfusion event in that interval (confirmed by sampling: rows alternate 0.0 and nonzero,
    e.g. 'rbc,2.0' followed by 'rbc,0.0'). Column header: op_id,subject_id,chart_time,item_name,
    value. chart_time is in SECONDS from admission (same anchor as labs.csv / operations.csv).
  - Insulin and electrolyte-repletion drugs (potassium chloride, sodium bicarbonate; there is NO
    injectable magnesium/"repletion" product distinguishable from oral Mg products in this data)
    are recorded in medications.csv as one row per administration: subject_id,chart_time,
    drug_name,route,drug_name2,drug_name3,atc_code,atc_code2,atc_code3. Confirmed present (2026-07
    sampling of ~15MB, ~324k rows, 678 unique drug_name values): 'insulin' + 7 named insulin
    analogs (all route=iv in the sample), 'potassium chloride' (po/iv forms), 'sodium
    bicarbonate' (po/iv). No RBC/platelet/FFP/blood product drug_name found in medications.csv —
    those live only in vitals.csv (see above). No distinct "magnesium repletion" injectable
    found separate from oral magnesium oxide/citrate/lactate supplements (used for constipation
    per ATC A02AA02/A06 codes, not IV electrolyte repletion) -> Mg trial not supported.

Usage:
  wget -q -O - --netrc https://physionet.org/files/inspire/1.3/vitals.csv | \
      python3 inspire_stream_tx.py vitals
  wget -q -O - --netrc https://physionet.org/files/inspire/1.3/medications.csv | \
      python3 inspire_stream_tx.py medications
Run both (in either order); each call APPENDS its matches to the same output CSV so
inspire_run.py can load one unified tx stream, mirroring eicu_tx.csv / repletions.csv.
"""
import sys, csv

SD = '/home/user/Codex-playground-/scratchpad/'
OUT = SD + 'inspire_tx.csv'

# vitals.csv item_name -> tx_class (blood products; per-interval channel, value>0 == event)
VITALS_CLASSES = {
    'rbc':  'rbc',    # transfused red blood cell (Unit)
    'pc':   'plt',    # transfused platelet concentrate (Unit)
    'ffp':  'ffp',    # transfused fresh frozen plasma (Unit) -- not currently in CONFIG, kept for completeness
    'cryo': 'cryo',   # transfused cryoprecipitate (Unit) -- not currently in CONFIG, kept for completeness
}

# medications.csv drug_name (lowercased) substring -> tx_class
import re
MED_CLASSES = [
    ('insulin',            re.compile(r'^insulin')),          # insulin, insulin aspart/glargine/... (all IV in sample)
    ('k',                  re.compile(r'potassium chloride')),# IV/PO KCl repletion
    ('hco3',               re.compile(r'sodium bicarbonate')),# IV/PO NaHCO3 repletion
]


def _strip_bom(header):
    # INSPIRE csv files are UTF-8-with-BOM (raw bytes start EF BB BF); stdin text mode does not
    # strip it, so the first header cell would otherwise read as '﻿subject_id'.
    return [h.lstrip('﻿') for h in header]


def stream_vitals():
    r = csv.reader(sys.stdin)
    header = _strip_bom(next(r))
    idx = {name: i for i, name in enumerate(header)}
    i_sid = idx['subject_id']
    i_ct = idx['chart_time']
    i_name = idx['item_name']
    i_val = idx['value']
    n = kept = 0
    with open(OUT, 'a', newline='') as f:
        wr = csv.writer(f)
        for row in r:
            n += 1
            try:
                name = row[i_name]
            except IndexError:
                continue
            cls = VITALS_CLASSES.get(name)
            if cls is None:
                continue
            sid, ct, val = row[i_sid], row[i_ct], row[i_val]
            if not sid or not ct or not val:
                continue
            try:
                v = float(val)
            except ValueError:
                continue
            if v > 0:  # nonzero channel value in this interval == a transfusion event
                wr.writerow([sid, ct, cls])
                kept += 1
            if n % 5_000_000 == 0:
                sys.stderr.write(f'  [vitals] scanned {n:,} rows, kept {kept:,}\n')
                sys.stderr.flush()
    sys.stderr.write(f'DONE [vitals] scanned {n:,} rows, kept {kept:,}\n')


def stream_medications():
    r = csv.reader(sys.stdin)
    header = _strip_bom(next(r))
    idx = {name: i for i, name in enumerate(header)}
    i_sid = idx['subject_id']
    i_ct = idx['chart_time']
    i_drug = idx['drug_name']
    n = kept = 0
    with open(OUT, 'a', newline='') as f:
        wr = csv.writer(f)
        for row in r:
            n += 1
            try:
                drug = row[i_drug]
            except IndexError:
                continue
            dl = drug.lower().strip()
            sid, ct = row[i_sid], row[i_ct]
            if not sid or not ct:
                continue
            for cls, rx in MED_CLASSES:
                if rx.search(dl):
                    wr.writerow([sid, ct, cls])
                    kept += 1
                    break
            if n % 5_000_000 == 0:
                sys.stderr.write(f'  [medications] scanned {n:,} rows, kept {kept:,}\n')
                sys.stderr.flush()
    sys.stderr.write(f'DONE [medications] scanned {n:,} rows, kept {kept:,}\n')


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('vitals', 'medications'):
        sys.stderr.write('usage: inspire_stream_tx.py {vitals|medications}  (reads that INSPIRE '
                          'table, plain CSV, from stdin)\n')
        sys.exit(2)
    # write header once, only if output doesn't exist yet (each call APPENDS its own rows below)
    import os
    if not os.path.exists(OUT):
        with open(OUT, 'w', newline='') as f:
            csv.writer(f).writerow(['subject_id', 'chart_time', 'tx_class'])
    if sys.argv[1] == 'vitals':
        stream_vitals()
    else:
        stream_medications()


if __name__ == '__main__':
    main()
