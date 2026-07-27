#!/usr/bin/env python3
"""
Filter MIMIC-IV hosp/prescriptions.csv.gz (stdin, gunzipped) to electrolyte-REPLETION drug
orders for the WARD-INCLUSIVE assay-noise IV. prescriptions is HOSPITAL-WIDE (ward+ICU),
unlike inputevents (ICU-only) — this is what makes floor-level de-implementation testable.
Output: hadm_id,class,starttime. Disk-sparing. Drug matched by lowercased 'drug' free-text regex,
with explicit excludes for non-repletion formulations (laxative/antacid Mg, penicillin-K salts,
and — validated against a real prescriptions.csv.gz sample — unrelated actives that merely use a
phosphate/magnesium SALT form, e.g. codeine phosphate, esomeprazole magnesium; 'phosphate' and
'magnesium' alone are dangerously broad bare-substring matches without these excludes).
"""
import sys, csv, re

# order matters: exclude-check happens before/alongside the class regex per class below.
CLASSES = [
    ('mg_repl', re.compile(r'magnesium'),
        re.compile(r'hydroxide|milk of magnesia|citrate|citracal|aluminum|esomeprazole|omeprazole|'
                   r'carbonate|trisalicylate|calcium magnesium')),
    ('k_repl', re.compile(r'potassium chlor|potassium bicarb|klor-con|k-dur|kcl|potassium citrate'),
        re.compile(r'penicillin')),
    ('phos_repl', re.compile(r'phosphate|neutra-phos|phosphorus'),
        re.compile(r'clindamycin|codeine|dexamethasone|disopyramide|fludarabine|oseltamivir|'
                   r'prednisolone|glycerophosphate|guaifenesin|betamethasone|dexbrompheniramine|'
                   r'polyethylene glycol|carvedilol|etoposide|primaquine|triphosphate')),
]

out = open('/home/user/Codex-playground-/scratchpad/rx_elyte.csv', 'w', newline='')
wr = csv.writer(out); wr.writerow(['hadm_id', 'class', 'starttime'])
r = csv.reader(sys.stdin)
hdr = next(r)
idx = {n: i for i, n in enumerate(hdr)}
ih, idr, ist = idx['hadm_id'], idx['drug'], idx['starttime']
n = kept = 0
for row in r:
    n += 1
    try:
        drug = row[idr].lower(); hadm = row[ih]
    except IndexError:
        continue
    if not hadm or not drug:
        continue
    for cls, rx, exc in CLASSES:
        if rx.search(drug) and not (exc and exc.search(drug)):
            wr.writerow([hadm, cls, row[ist]])
            kept += 1
            break
    if n % 2_000_000 == 0:
        sys.stderr.write(f'  scanned {n:,} kept {kept:,}\n'); sys.stderr.flush()
out.close()
sys.stderr.write(f'DONE scanned {n:,} kept {kept:,}\n')
