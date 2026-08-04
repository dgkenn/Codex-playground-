#!/usr/bin/env python3
"""Second targeted chartevents pass: compression-device (IPC/SCD) flags for PREVENT.
Chained to run after the first vitals pass finishes (see run_chart2.sh)."""
import sys, csv

WANT = {'228419':'comp1','228420':'comp2','228451':'comp3','228452':'comp4'}
out = {k: open(f'/home/user/Codex-playground-/scratchpad/chart_{v}.csv', 'w', newline='')
       for k, v in WANT.items()}
wr = {k: csv.writer(out[k]) for k in WANT}
for k in WANT:
    wr[k].writerow(['hadm_id', 'stay_id', 'charttime', 'value'])

r = csv.reader(sys.stdin)
# NOTE: input is grep-prefiltered (header stripped), so use the known MIMIC-IV icu/chartevents column order:
# subject_id,hadm_id,stay_id,caregiver_id,charttime,storetime,itemid,value,valuenum,valueuom,warning
i_hadm = 1; i_stay = 2; i_ct = 4; i_item = 6; i_val = 7
n = 0; kept = 0
for row in r:
    if len(row) < 8: continue
    n += 1
    it = row[i_item]
    if it in WANT:
        val = row[i_val]
        hadm = row[i_hadm]
        if val and hadm:
            wr[it].writerow([hadm, row[i_stay], row[i_ct], val])
            kept += 1
    if n % 20_000_000 == 0:
        sys.stderr.write(f'  scanned {n:,} rows, kept {kept:,}\n'); sys.stderr.flush()
for f in out.values():
    f.close()
sys.stderr.write(f'DONE scanned {n:,} rows, kept {kept:,}\n')
