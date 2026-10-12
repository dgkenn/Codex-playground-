#!/usr/bin/env python3
"""
Stream HiRID `pharma` tables -> one compact hirid_tx.csv for hirid_run.py.

The second of the two files `hirid_run.py`'s docstring marks TODO. Same contract and same defensive
posture as hirid_stream_lab.py: the schema is confirmed from public sources
(docs/archive/MULTISITE_HARMONIZATION.md §1) but the shipped files are not, so every assumption is
asserted at runtime and fails loudly with the actual header.

HiRID `pharma` columns (confirmed): patientid, givenat, pharmaid, givendose, doseunit, infusionid
  - `givenat` is an ABSOLUTE datetime, patient-timeshifted. hirid_run.py parses '%Y-%m-%d %H:%M:%S'.

ONE DESIGN NOTE THAT MATTERS. Unlike the eICU adapter, which regex-matches a free-text `treatmentstring`,
HiRID gives numeric `pharmaid`s. That is safer — no substring can accidentally match — but it fails
DIFFERENTLY: a wrong id yields **zero rows**, and zero rows look exactly like "this hospital does not do
that". Error-catalogue rule 5 says empty is not evidence of absence until the filter is shown able to match
something, so this script reports, per class, whether each mapped pharmaid was seen ANYWHERE in the data
and treats an all-miss class as a mapping failure rather than a finding.

Magnesium is deliberately absent: no public source gives a HiRID pharmaid for magnesium repletion, so
hirid_run.py's magnesium trial is expected to SKIP. That is a documented gap, not an oversight.

USAGE
    python hirid_stream_tx.py <path> [<path> ...]
    # paths may be .csv, .csv.gz, or .parquet; directories are searched recursively.
    # e.g. python hirid_stream_tx.py hirid_raw/physionet.org/files/hirid/1.1.1/raw_stage/pharma_records/

Writes SD/hirid_tx.csv with columns: patientid, givenat_iso, tx_class
where tx_class is one of {rbc, insulin, nahco3, kcl} -- the exact strings hirid_run.py's CONFIG asks for.
"""
import csv
import glob
import gzip
import os
import sys
from collections import Counter
from datetime import datetime

SD = '/home/user/Codex-playground-/scratchpad/'

# tx_class -> set of pharma.pharmaid. Sources/confidence: MULTISITE_HARMONIZATION.md §1 table.
#   insulin is the only CROSS-SOURCE CONFIRMED mapping (ricu + HIRID-ICU-Benchmark varref.tsv agree).
#   rbc / nahco3 / kcl are single-source (varref.tsv, dataset-native) = medium-high confidence.
CLASSES = {
    'rbc':     {1000100, 1000743},          # "packed red blood cells"/"EK", "EK Pflege"
    'insulin': {15, 1000724, 1000379},      # "Insulin Actrapid" (short), longer-acting
    'nahco3':  {1000193, 1000453},          # "Na-Bicarbonat 8.4%", "Na-Bicarbonat Inf Lsg 8.4%"
    'kcl':     {1000080, 1000568},          # "K-Cl conc", "K-Cl-Perfusor"
}
PID2CLASS = {pid: c for c, pids in CLASSES.items() for pid in pids}

REQUIRED = ('patientid', 'givenat', 'pharmaid')


def iter_files(paths):
    seen = []
    for p in paths:
        if os.path.isdir(p):
            for ext in ('*.csv', '*.csv.gz', '*.parquet'):
                seen.extend(sorted(glob.glob(os.path.join(p, '**', ext), recursive=True)))
        else:
            seen.extend(sorted(glob.glob(p)))
    out = list(dict.fromkeys(seen))
    if not out:
        sys.exit(f'FATAL: no .csv/.csv.gz/.parquet files found under {paths!r}')
    return out


def rows_from(path):
    if path.endswith('.parquet'):
        try:
            import pyarrow.parquet as pq
        except ImportError:
            sys.exit('FATAL: parquet input needs pyarrow (pip install pyarrow), or use the csv/ variant.')
        t = pq.read_table(path)
        cols = set(t.column_names)
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            sys.exit(f'FATAL: {path} lacks {missing}. Actual columns: {sorted(cols)}\n'
                     f'The schema in MULTISITE_HARMONIZATION.md §1 does not match the shipped file.')
        d = t.to_pydict()
        for i in range(t.num_rows):
            yield {c: d[c][i] for c in REQUIRED}
    else:
        op = gzip.open if path.endswith('.gz') else open
        with op(path, 'rt', newline='') as fh:
            r = csv.reader(fh)
            hdr = next(r, None)
            if hdr is None:
                return
            idx = {n.strip(): i for i, n in enumerate(hdr)}
            missing = [c for c in REQUIRED if c not in idx]
            if missing:
                sys.exit(f'FATAL: {path} lacks {missing}. Actual header: {hdr}\n'
                         f'The schema in MULTISITE_HARMONIZATION.md §1 does not match the shipped file.')
            take = {c: idx[c] for c in REQUIRED}
            for row in r:
                if len(row) <= max(take.values()):
                    continue
                yield {c: row[i] for c, i in take.items()}


def norm_dt(v):
    if isinstance(v, datetime):
        return v.strftime('%Y-%m-%d %H:%M:%S')
    s = str(v).strip().replace('T', ' ')
    if len(s) >= 19:
        s = s[:19]
        try:
            datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
            return s
        except ValueError:
            return None
    return None


def main(argv):
    files = iter_files(argv[1:])
    os.makedirs(SD, exist_ok=True)
    out = open(SD + 'hirid_tx.csv', 'w', newline='')
    w = csv.writer(out)
    w.writerow(['patientid', 'givenat_iso', 'tx_class'])
    per_class = Counter()
    per_id = Counter()
    seen_ids = set()
    n = kept = 0
    sys.stderr.write(f'scanning {len(files)} file(s)\n')
    for path in files:
        for row in rows_from(path):
            n += 1
            try:
                pid_drug = int(str(row['pharmaid']).strip())
            except (TypeError, ValueError):
                continue
            seen_ids.add(pid_drug)
            cls = PID2CLASS.get(pid_drug)
            if cls is None:
                continue
            pid = str(row['patientid']).strip()
            ts = norm_dt(row['givenat'])
            if not pid or ts is None:
                continue
            w.writerow([pid, ts, cls])
            per_class[cls] += 1
            per_id[pid_drug] += 1
            kept += 1
            if n % 5_000_000 == 0:
                sys.stderr.write(f'  scanned {n:,} rows, kept {kept:,}\n'); sys.stderr.flush()
    out.close()
    sys.stderr.write(f'DONE scanned {n:,} rows, kept {kept:,}\n\n')

    print('=' * 88)
    print('MAPPING CHECK — a wrong pharmaid yields ZERO rows, which reads as "they do not do that"')
    print('=' * 88)
    bad = []
    for cls in sorted(CLASSES):
        hits = sorted(i for i in CLASSES[cls] if i in seen_ids)
        miss = sorted(i for i in CLASSES[cls] if i not in seen_ids)
        detail = ', '.join(f'{i}:{per_id[i]:,}' for i in hits) or 'NONE'
        print(f'  {cls:>8}  rows {per_class[cls]:>9,}   ids present [{detail}]   absent {miss or "-"}')
        if not hits:
            bad.append(f'{cls}: none of its pharmaids {sorted(CLASSES[cls])} appear anywhere in the data')
    print(f'\n  distinct pharmaids seen in the source: {len(seen_ids):,}')
    print('  magnesium: intentionally unmapped (no public source gives a HiRID pharmaid) — '
          'hirid_run.py will SKIP that trial.')
    if bad:
        print('\nFATAL — refusing to hand this file to hirid_run.py:')
        for b in bad:
            print(f'   - {b}')
        print('\nRe-verify against the pharma reference on access. Zero rows for a class is a mapping '
              'failure until proven otherwise, not evidence the hospital never gives that drug.')
        return 1
    print('\nEvery treatment class matched at least one pharmaid present in the data.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
