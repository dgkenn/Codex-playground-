#!/usr/bin/env python3
"""
Build a SYNTHETIC HiRID in the documented schema and run the whole adapter chain over it.

WHY THIS EXISTS. HiRID is DUA-gated, so the adapters (hirid_stream_lab / _tx / _general -> hirid_run) could
not be executed before writing them. This generates fake tables matching
docs/archive/MULTISITE_HARMONIZATION.md §1 exactly — RAW instrument units, absolute patient-timeshifted
datetimes, the real variableids and pharmaids — and pushes them through the chain. It proves the plumbing,
the unit conversions, the datetime parsing and the mapping/units/outcome gates all work, so that on the day
credentials arrive the only open question is whether the SHIPPED files match the documented schema (which
the adapters assert loudly).

**NOTHING HERE IS A RESULT.** The associations are random by construction — treatment assignment is
independent of the lab value and mortality is independent of everything. Any number this produces is noise,
and that is the point: it exercises every code path while revealing nothing (error-catalogue rule 26).

USAGE
    python hirid_smoke_synth.py            # writes to a temp dir, runs the chain, reports pass/fail
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SD = '/home/user/Codex-playground-/scratchpad/'

# RAW units, chosen so the documented multipliers land in the physiological window the gates check.
#   hb  x0.1    -> raw ~100  = 10.0 g/dL
#   glu x18.016 -> raw ~7.0  = 126 mg/dL
#   mg  x2.432  -> raw ~0.85 = 2.07 mg/dL
RAW = {
    24000548: ('hb',   lambda r: r.gauss(100, 18)),
    20005110: ('glu',  lambda r: max(1.0, r.gauss(7.0, 2.2))),
    20004200: ('hco3', lambda r: r.gauss(24, 4)),
    20000500: ('k',    lambda r: r.gauss(4.0, 0.6)),
    20005200: ('mg',   lambda r: max(0.1, r.gauss(0.85, 0.15))),
}
PHARMA = [1000100, 15, 1000193, 1000080]     # rbc, insulin, nahco3, kcl


def build(root, n_pat=400, seed=7):
    r = random.Random(seed)
    os.makedirs(f'{root}/observation_tables', exist_ok=True)
    os.makedirs(f'{root}/pharma_records', exist_ok=True)
    base = datetime(2100, 1, 1)          # HiRID timeshifts into the future; mimic that
    gen = [('patientid', 'admissiontime', 'sex', 'age', 'discharge_status')]
    obs = [('patientid', 'datetime', 'variableid', 'value', 'stringvalue', 'type', 'status')]
    pha = [('patientid', 'givenat', 'pharmaid', 'givendose', 'doseunit', 'infusionid')]
    for p in range(1, n_pat + 1):
        adm = base + timedelta(days=r.randint(0, 900), hours=r.randint(0, 23))
        gen.append((p, adm.strftime('%Y-%m-%d %H:%M:%S'), r.choice('MF'),
                    r.randint(18, 90), 'dead' if r.random() < 0.12 else 'alive'))
        for vid, (_key, draw) in RAW.items():
            for j in range(r.randint(2, 4)):          # >=2 pre-treatment draws, as the engine needs
                t = adm + timedelta(hours=r.uniform(1, 40) + 6 * j)
                obs.append((p, t.strftime('%Y-%m-%d %H:%M:%S'), vid, f'{draw(r):.4f}', '', 4, 8))
        for pid_drug in PHARMA:
            if r.random() < 0.35:
                t = adm + timedelta(hours=r.uniform(2, 70))
                pha.append((p, t.strftime('%Y-%m-%d %H:%M:%S'), pid_drug, 1.0, 'U', 0))

    def dump(path, rows):
        import csv
        with open(path, 'w', newline='') as fh:
            csv.writer(fh).writerows(rows)
    dump(f'{root}/general_table.csv', gen)
    dump(f'{root}/observation_tables/part-0.csv', obs)
    dump(f'{root}/pharma_records/part-0.csv', pha)
    return len(obs) - 1, len(pha) - 1


def run(label, args):
    print(f'\n{"="*88}\n$ {" ".join(os.path.basename(a) for a in args)}\n{"="*88}')
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    sys.stdout.write(p.stdout[-3000:])
    if p.returncode != 0:
        sys.stdout.write(p.stderr[-2000:])
    print(f'-- {label}: exit {p.returncode}')
    return p.returncode


def main():
    root = tempfile.mkdtemp(prefix='hirid_synth_')
    saved = {}
    try:
        n_obs, n_pha = build(root)
        print(f'synthetic HiRID at {root}: {n_obs:,} observations, {n_pha:,} pharma rows')
        # protect any real scratchpad inputs from being clobbered by the smoke test
        for f in os.listdir(SD) if os.path.isdir(SD) else []:
            if f.startswith('hirid_'):
                saved[f] = open(SD + f, 'rb').read()
        rc = 0
        rc |= run('general', [f'{HERE}/hirid_stream_general.py', f'{root}/general_table.csv'])
        rc |= run('labs', [f'{HERE}/hirid_stream_lab.py', f'{root}/observation_tables'])
        rc |= run('treatments', [f'{HERE}/hirid_stream_tx.py', f'{root}/pharma_records'])
        rc |= run('engine', [f'{HERE}/hirid_run.py'])
        print(f'\n{"="*88}')
        print('SMOKE TEST ' + ('PASSED — the chain runs end to end on the documented schema.'
                               if rc == 0 else 'FAILED — see the non-zero step above.'))
        print('The numbers above are NOISE by construction and must never be quoted.')
        print('=' * 88)
        return rc
    finally:
        shutil.rmtree(root, ignore_errors=True)
        for f in os.listdir(SD) if os.path.isdir(SD) else []:
            if f.startswith('hirid_') and f not in saved:
                os.remove(SD + f)
        for f, blob in saved.items():
            open(SD + f, 'wb').write(blob)


if __name__ == '__main__':
    sys.exit(main())
