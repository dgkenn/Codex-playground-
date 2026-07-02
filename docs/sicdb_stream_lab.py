#!/usr/bin/env python3
"""Stream-filter SICdb laboratory.csv.gz from stdin (gunzipped) to just the Hb rows we need, avoiding the
file-integrity problem (the agent proxy won't serve mid-file byte ranges, but a single stream from offset 0
works — same pattern as the 2.6GB MIMIC chartevents stream). Keeps LaboratoryID in {289 CBC-Hb, 658 BGA-Hb,
288 arterial-lab-Hb}."""
import sys, csv
WANT = {'289', '658', '288'}
out = open('/home/user/Codex-playground-/scratchpad/sicdb_raw/sicdb_lab_hb.csv', 'w', newline='')
w = csv.writer(out); w.writerow(['CaseID', 'LaboratoryID', 'Offset', 'LaboratoryValue'])
r = csv.reader(sys.stdin)
h = [c.strip('"') for c in next(r)]
ix = {n: i for i, n in enumerate(h)}
ci, li, oi, vi = ix['CaseID'], ix['LaboratoryID'], ix['Offset'], ix['LaboratoryValue']
n = k = 0
for row in r:
    n += 1
    if len(row) > max(ci, li, oi, vi) and row[li] in WANT:
        w.writerow([row[ci], row[li], row[oi], row[vi]]); k += 1
    if n % 2000000 == 0:
        sys.stderr.write(f'{n} rows, kept {k}\n'); sys.stderr.flush()
out.close()
sys.stderr.write(f'DONE {n} rows, kept {k} Hb rows\n')
