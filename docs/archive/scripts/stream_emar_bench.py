#!/usr/bin/env python3
"""
Filter MIMIC-IV hosp/emar.csv.gz (stdin, gunzipped) to the RCT-BENCHMARK treatments, sourced
hospital-wide (ward+ICU) from administration records. Output: hadm_id,charttime,tx_class.
Only "Administered"-type events. tx_class in {rbc, platelet, insulin, bicarb}.
"""
import sys, csv, re
CLASSES = [
    ('rbc',      re.compile(r'red blood cell|packed red|prbc|leukoreduced|leukocyte reduced|rbc', re.I)),
    ('platelet', re.compile(r'platelet', re.I)),
    ('insulin',  re.compile(r'insulin', re.I)),
    ('bicarb',   re.compile(r'sodium bicarbonate|bicarbonate|nahco3', re.I)),
]
NOTADMIN = ('not given', 'hold', 'held', 'delayed', 'stopped', 'not flush', 'assessed', 'confirmed', 'reconcil')
def is_admin(ev):
    e = ev.lower()
    if any(k in e for k in NOTADMIN): return False
    return ('administer' in e or 'started' in e or 'given' in e or 'bolus' in e or 'infusion' in e)
out = open('/home/user/Codex-playground-/scratchpad/emar_bench.csv', 'w', newline='')
wr = csv.writer(out); wr.writerow(['hadm_id', 'charttime', 'tx_class'])
r = csv.reader(sys.stdin)
hdr = next(r); ix = {n: i for i, n in enumerate(hdr)}
ih, ic, imed, iev = ix['hadm_id'], ix['charttime'], ix['medication'], ix['event_txt']
n = kept = 0
for row in r:
    n += 1
    try:
        med = row[imed]; hadm = row[ih]
    except IndexError:
        continue
    if not hadm or not med or not is_admin(row[iev]):
        continue
    for cls, rx in CLASSES:
        if rx.search(med):
            wr.writerow([hadm, row[ic], cls]); kept += 1
            break
    if n % 5_000_000 == 0:
        sys.stderr.write(f'  scanned {n:,} kept {kept:,}\n'); sys.stderr.flush()
out.close()
sys.stderr.write(f'DONE scanned {n:,} kept {kept:,}\n')
