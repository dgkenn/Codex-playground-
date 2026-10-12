#!/usr/bin/env python3
"""
Normalize HiRID's `general_table.csv` -> SD/hirid_general.csv for hirid_run.py.

`hirid_run.py`'s docstring names two TODO adapters (lab, tx) but needs THREE inputs — it also reads
`hirid_general.csv`, "renamed from the raw general_table.csv". That rename is not a pure `cp`: the engine
reads `discharge_status` and compares it to the literal string 'dead', and its own comment flags this as
TO-CONFIRM ("official docs give 'alive'/'dead'/'unknown', but verify against the real file header + a
sample"). Doing it here means the check happens once, loudly, instead of silently defining the outcome.

HiRID `general` columns (confirmed, MULTISITE_HARMONIZATION.md §1):
    patientid, admissiontime (absolute timeshifted datetime), sex ('M'/'F'), age (int, capped at 90),
    discharge_status ('alive'/'dead'/'unknown')

WHAT THIS GUARDS. `discharge_status` IS the outcome for every trial in the replication. If its values are
cased differently, spelled differently, or mostly empty, `== 'dead'` silently yields a near-zero event rate
and every flag-ITT estimate collapses toward zero — a null that looks like a finding. So the observed value
distribution is printed and the run fails unless a plausible mortality rate is present.

USAGE
    python hirid_stream_general.py <path-to-general_table.csv>
"""
import csv
import glob
import gzip
import os
import sys
from collections import Counter
from datetime import datetime

SD = '/home/user/Codex-playground-/scratchpad/'
REQUIRED = ('patientid', 'admissiontime', 'age', 'sex', 'discharge_status')

# HiRID is a general adult ICU; in-hospital mortality should land in this band. Wide on purpose --
# this is a "did the outcome field parse at all" check, not a clinical claim.
PLAUSIBLE_MORTALITY = (0.02, 0.30)


def rows_from(path):
    if path.endswith('.parquet'):
        try:
            import pyarrow.parquet as pq
        except ImportError:
            sys.exit('FATAL: parquet input needs pyarrow (pip install pyarrow).')
        t = pq.read_table(path)
        cols = set(t.column_names)
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            sys.exit(f'FATAL: {path} lacks {missing}. Actual columns: {sorted(cols)}')
        d = t.to_pydict()
        for i in range(t.num_rows):
            yield {c: d[c][i] for c in REQUIRED}
    else:
        op = gzip.open if path.endswith('.gz') else open
        with op(path, 'rt', newline='') as fh:
            r = csv.reader(fh)
            hdr = next(r, None)
            if hdr is None:
                sys.exit(f'FATAL: {path} is empty')
            idx = {n.strip(): i for i, n in enumerate(hdr)}
            missing = [c for c in REQUIRED if c not in idx]
            if missing:
                sys.exit(f'FATAL: {path} lacks {missing}. Actual header: {hdr}\n'
                         f'MULTISITE_HARMONIZATION.md §1 does not match the shipped file — re-verify '
                         f'against hirid_schema.pdf before trusting the outcome definition.')
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
    if len(argv) < 2:
        sys.exit('usage: hirid_stream_general.py <general_table.csv>')
    matches = [p for a in argv[1:] for p in sorted(glob.glob(a))]
    if not matches:
        sys.exit(f'FATAL: no file matched {argv[1:]!r}')
    os.makedirs(SD, exist_ok=True)
    dest = SD + 'hirid_general.csv'
    status = Counter()
    n = written = 0
    bad_dt = 0
    with open(dest, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['patientid', 'admissiontime', 'age', 'sex', 'discharge_status'])
        for path in matches:
            for row in rows_from(path):
                n += 1
                pid = str(row['patientid']).strip()
                ts = norm_dt(row['admissiontime'])
                st = str(row['discharge_status']).strip()
                status[st.lower() or '<empty>'] += 1
                if not pid:
                    continue
                if ts is None:
                    bad_dt += 1
                    continue
                w.writerow([pid, ts, str(row['age']).strip(), str(row['sex']).strip(), st])
                written += 1

    print('=' * 88)
    print('GENERAL TABLE — the outcome field, checked before it silently defines every result')
    print('=' * 88)
    print(f'  rows read {n:,}   written {written:,}   unparseable admissiontime {bad_dt:,}')
    print(f'  -> {dest}')
    print('\n  discharge_status value distribution (lowercased):')
    for k, v in status.most_common(10):
        print(f'     {k:>12}  {v:>8,}  ({100*v/max(n,1):.1f}%)')

    dead = status.get('dead', 0)
    rate = dead / written if written else 0.0
    lo, hi = PLAUSIBLE_MORTALITY
    print(f"\n  hirid_run.py scores mortality as discharge_status == 'dead' (exact, lowercase).")
    print(f"  matching that literal: {dead:,} of {written:,} = {100*rate:.1f}%   expected "
          f"{100*lo:.0f}-{100*hi:.0f}%")
    problems = []
    if written == 0:
        problems.append('no rows written at all')
    elif not (lo <= rate <= hi):
        alt = [k for k in status if k not in ('alive', 'dead', 'unknown', '<empty>')]
        problems.append(
            f"mortality rate {100*rate:.1f}% is outside [{100*lo:.0f}%, {100*hi:.0f}%] — the literal "
            f"'dead' probably does not match this file's encoding"
            + (f' (unexpected values present: {alt[:5]})' if alt else ''))
    if bad_dt > 0.01 * max(n, 1):
        problems.append(f'{100*bad_dt/n:.1f}% of admissiontime values did not parse as '
                        f"'%Y-%m-%d %H:%M:%S' — hirid_run.py will drop those patients")
    if problems:
        print('\nFATAL — refusing to hand this file to hirid_run.py:')
        for p in problems:
            print(f'   - {p}')
        print('\nFix the outcome mapping before running. An outcome that fails to match is not a null '
              'result; it is a broken join, and it will look like a confident null.')
        return 1
    print('\n  Outcome field parses and the mortality rate is plausible.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
