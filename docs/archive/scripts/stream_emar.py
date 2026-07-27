#!/usr/bin/env python3
"""
Stream MIMIC-IV hosp/emar.csv.gz (stdin, gunzipped), filter to PRN-relevant drug classes
(benzo/opioid/antipsychotic), output the administration DECISION per due dose for the nurse-PRN IV.
Columns kept: hadm_id, charttime, class, event_txt, provider (enter_provider_id = administering nurse proxy).
Disk-sparing.
"""
import sys, csv, re
CLASSES = [
    ('benzo',  re.compile(r'lorazepam|midazolam|diazepam|alprazolam|clonazepam|temazepam|oxazepam|chlordiazepoxide', re.I)),
    ('opioid', re.compile(r'morphine|hydromorphone|fentanyl|oxycodone|hydrocodone|methadone|tramadol|oxymorphone', re.I)),
    ('antipsy',re.compile(r'haloperidol|quetiapine|olanzapine|risperidone|ziprasidone|aripiprazole|chlorpromazine', re.I)),
]
EXCLUDE = re.compile(r'naloxone|topical|patch|cream|ointment', re.I)
out = open('/home/user/Codex-playground-/scratchpad/emar_prn.csv', 'w', newline='')
wr = csv.writer(out); wr.writerow(['hadm_id', 'charttime', 'class', 'event_txt', 'provider'])
r = csv.reader(sys.stdin)
hdr = next(r); ix = {n: i for i, n in enumerate(hdr)}
ih, ic, imed, iev = ix['hadm_id'], ix['charttime'], ix['medication'], ix['event_txt']
ipr = ix.get('enter_provider_id', -1)
n = kept = 0
for row in r:
    n += 1
    try:
        med = row[imed]; hadm = row[ih]
    except IndexError:
        continue
    if not hadm or not med or EXCLUDE.search(med):
        continue
    for cls, rx in CLASSES:
        if rx.search(med):
            wr.writerow([hadm, row[ic], cls, row[iev], row[ipr] if ipr >= 0 else ''])
            kept += 1
            break
    if n % 5_000_000 == 0:
        sys.stderr.write(f'  scanned {n:,} kept {kept:,}\n'); sys.stderr.flush()
out.close()
sys.stderr.write(f'DONE scanned {n:,} kept {kept:,}\n')
