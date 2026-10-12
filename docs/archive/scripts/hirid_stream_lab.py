#!/usr/bin/env python3
"""
Stream HiRID `observations` tables -> compact per-analyte CSVs for hirid_run.py.

This is one of the two files `hirid_run.py`'s docstring marks TODO ("write those once table format is
confirmed"). The table format IS confirmed from public sources — see docs/archive/MULTISITE_HARMONIZATION.md
§1, which cites `hirid.intensivecare.ai/structure-of-the-published-data`, the HIRID-ICU-Benchmark repo's
`varref.tsv`, and ricu's concept-dict.json. What is NOT confirmed is that the shipped files match those
docs, so **every assumption below is asserted at runtime and fails loudly with the actual header** rather
than silently producing an empty or wrong file (error-catalogue rules 5 and 6).

HiRID `observations` columns (confirmed): patientid, datetime, variableid, value, stringvalue, type, status
  - `datetime` is an ABSOLUTE datetime, patient-timeshifted for de-identification. It is NOT a relative
    offset. hirid_run.py parses it with '%Y-%m-%d %H:%M:%S', so that is the format written here.

THE UNIT CONVERSIONS ARE THE DANGEROUS PART. hirid_run.py's CONFIG thresholds are in clinical units
(Hgb < 7 g/dL, glucose > 180 mg/dL, HCO3 < 15 mEq/L, K < 3.5 mEq/L), and HiRID stores several analytes in
raw instrument units. ricu applies the factors below. **A wrong factor would not crash — it would silently
move every patient to one side of the flag and produce a confident, meaningless result.** So after writing,
each analyte's median is checked against a physiological range stated here in advance, and a failure is
fatal. This is cheap insurance against exactly the failure mode this project has been bitten by before.

USAGE
    python hirid_stream_lab.py <path> [<path> ...]
    # paths may be .csv, .csv.gz, or .parquet, and directories are searched recursively.
    # e.g. python hirid_stream_lab.py hirid_raw/physionet.org/files/hirid/1.1.1/raw_stage/observation_tables/

Writes to SD: hirid_lab_hb.csv, hirid_lab_glu.csv, hirid_lab_hco3.csv, hirid_lab_k.csv, hirid_lab_mg.csv
with columns: patientid, datetime_iso, variableid, value   (value already unit-converted)
"""
import csv
import glob
import gzip
import os
import sys
from datetime import datetime

SD = '/home/user/Codex-playground-/scratchpad/'

# key -> (set of observations.variableid, multiplier to clinical units, unit label)
# Sources and confidence per mapping: docs/archive/MULTISITE_HARMONIZATION.md §1 table.
WANT = {
    'hb':   ({24000548, 24000836, 20000900}, 0.1,    'g/dL'),
    'glu':  ({20005110, 24000523, 24000585}, 18.016, 'mg/dL'),
    'hco3': ({20004200},                     1.0,    'mEq/L'),
    'k':    ({20000500, 24000520, 24000833, 24000867}, 1.0, 'mEq/L'),
    # MEDIUM CONFIDENCE: ricu-only, absent from HIRID-ICU-Benchmark varref.tsv. hirid_run.py already
    # expects the magnesium trial to SKIP (no mapped treatment id). Kept so the lab side is ready.
    'mg':   ({20005200},                     2.432,  'mg/dL'),
}
VID2KEY = {vid: k for k, (vids, _, _) in WANT.items() for vid in vids}

# Median of the CONVERTED values must land in here, or the conversion factor is wrong. Ranges are
# deliberately wide -- they are a units check (is this g/dL or g/L?), not a clinical claim.
PLAUSIBLE = {
    'hb':   (6.0, 15.0),
    'glu':  (70.0, 250.0),
    'hco3': (15.0, 32.0),
    'k':    (2.8, 5.5),
    'mg':   (1.2, 3.2),
}

REQUIRED = ('patientid', 'datetime', 'variableid', 'value')


def iter_files(paths):
    seen = []
    for p in paths:
        if os.path.isdir(p):
            for ext in ('*.csv', '*.csv.gz', '*.parquet'):
                seen.extend(sorted(glob.glob(os.path.join(p, '**', ext), recursive=True)))
        else:
            seen.extend(sorted(glob.glob(p)))
    out = [f for f in dict.fromkeys(seen)]
    if not out:
        sys.exit(f'FATAL: no .csv/.csv.gz/.parquet files found under {paths!r}')
    return out


def rows_from(path):
    """Yield dict-like rows. Fails loudly if the confirmed columns are absent."""
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
                     f'The schema in MULTISITE_HARMONIZATION.md §1 does not match the shipped file — '
                     f're-verify against hirid_schema.pdf before trusting any mapping.')
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
                         f'The schema in MULTISITE_HARMONIZATION.md §1 does not match the shipped file — '
                         f're-verify against hirid_schema.pdf before trusting any mapping.')
            take = {c: idx[c] for c in REQUIRED}
            for row in r:
                if len(row) <= max(take.values()):
                    continue
                yield {c: row[i] for c, i in take.items()}


def norm_dt(v):
    """HiRID datetimes are absolute and patient-timeshifted. Emit exactly what hirid_run.py parses."""
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
    handles = {k: open(SD + f'hirid_lab_{k}.csv', 'w', newline='') for k in WANT}
    writers = {}
    for k, fh in handles.items():
        w = csv.writer(fh)
        w.writerow(['patientid', 'datetime_iso', 'variableid', 'value'])
        writers[k] = w
    vals = {k: [] for k in WANT}
    seen_vids = set()
    n = kept = 0
    sys.stderr.write(f'scanning {len(files)} file(s)\n')
    for path in files:
        for row in rows_from(path):
            n += 1
            try:
                vid = int(str(row['variableid']).strip())
            except (TypeError, ValueError):
                continue
            seen_vids.add(vid)
            key = VID2KEY.get(vid)
            if key is None:
                continue
            pid = str(row['patientid']).strip()
            ts = norm_dt(row['datetime'])
            if not pid or ts is None:
                continue
            try:
                v = float(row['value']) * WANT[key][1]
            except (TypeError, ValueError):
                continue
            if v != v:
                continue
            writers[key].writerow([pid, ts, vid, f'{v:.6g}'])
            vals[key].append(v)
            kept += 1
            if n % 5_000_000 == 0:
                sys.stderr.write(f'  scanned {n:,} rows, kept {kept:,}\n'); sys.stderr.flush()
    for fh in handles.values():
        fh.close()
    sys.stderr.write(f'DONE scanned {n:,} rows, kept {kept:,}\n\n')

    # --- rule 5: empty is not evidence of absence until the filter is shown able to match ----------
    print('=' * 88)
    print('MAPPING CHECK — did each variableid actually appear in the data?')
    print('=' * 88)
    bad = []
    for k, (vids, mult, unit) in sorted(WANT.items()):
        hit = sorted(v for v in vids if v in seen_vids)
        miss = sorted(v for v in vids if v not in seen_vids)
        print(f'  {k:>5}  matched ids {hit or "NONE"}   unmatched {miss or "-"}   rows {len(vals[k]):,}')
        if not hit:
            bad.append(f'{k}: none of its variableids {sorted(vids)} appear anywhere in the scanned data')
    print(f'\n  distinct variableids seen in the source: {len(seen_vids):,}')

    # --- the units gate ---------------------------------------------------------------------------
    print('\n' + '=' * 88)
    print('UNITS GATE — median of CONVERTED values against a range stated before the run')
    print('=' * 88)
    import statistics
    for k in sorted(WANT):
        lo, hi = PLAUSIBLE[k]
        unit = WANT[k][2]
        if not vals[k]:
            print(f'  {k:>5}  no rows — cannot check (see mapping check above)')
            continue
        med = statistics.median(vals[k])
        ok = lo <= med <= hi
        print(f'  {k:>5}  median {med:>8.2f} {unit:<6} expected [{lo}, {hi}]  '
              f'x{WANT[k][1]}  {"OK" if ok else "*** OUT OF RANGE ***"}')
        if not ok:
            bad.append(f'{k}: converted median {med:.2f} {unit} outside [{lo}, {hi}] — '
                       f'the x{WANT[k][1]} factor is probably wrong for this variableid')
    if bad:
        print('\nFATAL — refusing to hand these files to hirid_run.py:')
        for b in bad:
            print(f'   - {b}')
        print('\nFix the mapping in MULTISITE_HARMONIZATION.md §1 against hirid_variable_reference.csv '
              'before re-running. A wrong factor does not crash the engine; it produces a confident '
              'and meaningless result.')
        return 1
    print('\nAll mappings matched and all converted medians are physiologically plausible.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
