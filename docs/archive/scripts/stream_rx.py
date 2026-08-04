#!/usr/bin/env python3
"""
Filter MIMIC-IV hosp/prescriptions.csv.gz (stdin, gunzipped) to the 7 drug classes needed for
the provider-preference IV + contraindication-gate trials. Output: hadm_id,class,starttime,provider.
Disk-sparing. Drug matched by lowercased 'drug' free-text regex.
"""
import sys, csv, re

CLASSES = [
    ('ppi',    re.compile(r'pantoprazole|omeprazole|esomeprazole|lansoprazole|rabeprazole|dexlansoprazole')),
    ('h2',     re.compile(r'famotidine|ranitidine|cimetidine|nizatidine')),
    ('benzo',  re.compile(r'lorazepam|midazolam|diazepam|alprazolam|clonazepam|temazepam|oxazepam|chlordiazepoxide')),
    ('opioid', re.compile(r'morphine|hydromorphone|fentanyl|oxycodone|hydrocodone|methadone|tramadol|oxymorphone')),
    ('antipsy',re.compile(r'haloperidol|quetiapine|olanzapine|risperidone|ziprasidone|aripiprazole|chlorpromazine')),
    ('steroid',re.compile(r'prednisone|prednisolone|methylprednisolone|hydrocortisone|dexamethasone')),
    ('anticoag_ppx', re.compile(r'heparin|enoxaparin|fondaparinux|dalteparin')),
]
EXCLUDE = re.compile(r'naloxone|topical|ophthalmic|otic|cream|ointment|inhal|nebul|eye|ear|nasal|rectal|patch')

out = open('/home/user/Codex-playground-/scratchpad/rx_class.csv', 'w', newline='')
wr = csv.writer(out); wr.writerow(['hadm_id', 'class', 'starttime', 'provider', 'stoptime'])
r = csv.reader(sys.stdin)
hdr = next(r)
idx = {n: i for i, n in enumerate(hdr)}
ih, idr, ist = idx['hadm_id'], idx['drug'], idx['starttime']
ipr = idx.get('order_provider_id', -1)
isp = idx.get('stoptime', -1)
n = kept = 0
for row in r:
    n += 1
    try:
        drug = row[idr].lower(); hadm = row[ih]
    except IndexError:
        continue
    if not hadm or EXCLUDE.search(drug):
        continue
    for cls, rx in CLASSES:
        if rx.search(drug):
            wr.writerow([hadm, cls, row[ist], row[ipr] if ipr >= 0 else '',
                         row[isp] if isp >= 0 else ''])
            kept += 1
            break
    if n % 2_000_000 == 0:
        sys.stderr.write(f'  scanned {n:,} kept {kept:,}\n'); sys.stderr.flush()
out.close()
sys.stderr.write(f'DONE scanned {n:,} kept {kept:,}\n')
