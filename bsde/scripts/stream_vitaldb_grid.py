"""Stream VitalDB onto a whole-case grid, carrying the BIS monitor with every window.

WHY THIS IS A COMMITTED SCRIPT AND NOT A HEREDOC. The first VitalDB table
(`results/vitaldb_challenge_a.csv`) was produced by an inline shell heredoc, and when the diagnosis of E21's
gate failure needed to know exactly which offsets and filters had produced it, the command was gone. The
table was reproducible only by reading the adapter and guessing. Every extraction that takes hours gets a
committed driver from here on.

WHAT CHANGED FROM THE FIRST TABLE, in one line each -- the reasoning is in `ingestion/vitaldb.py`:
  * windows come from a fixed grid across the whole case, not from seven offsets around `aneend`;
  * `BIS/SQI` rides along, so the monitor's off-state is detectable instead of being read as BIS 0;
  * `BIS/SR` and `BIS/EMG` ride along, giving device-scored burst suppression and a REAL muscle channel.

Resumable: re-running appends only the rows that are not already in the output.

SHARDING IS BY CASE, NOT BY WINDOW. The runner's own `--shard` hashes the recording id, which would scatter
one case's forty windows across every shard and make each shard re-download that case's 9.4 MB waveform
track. `--case-shard` splits the CASE LIST instead, so four parallel shards cost four times one shard's
bandwidth rather than four times the whole job's. Measured single-stream rate: about 2.3 min per case, so
250 cases is ~9.5 h in one process and ~2.4 h in four.

    # four shards in parallel, each to its own file
    for k in 0 1 2 3; do
      python bsde/scripts/stream_vitaldb_grid.py --n-cases 250 --case-shard $k --of 4 \
             --out bsde/results/vitaldb_grid.s$k.csv &
    done; wait
    # then merge into the single table E22 reads
    python bsde/scripts/stream_vitaldb_grid.py --merge bsde/results/vitaldb_grid.csv \
             bsde/results/vitaldb_grid.s*.csv

`--n-cases` is applied BEFORE sharding, so the union of the shards is exactly the case set one unsharded run
would have produced.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.candidates.registry import REGISTRY                         # noqa: E402
from bsde.candidates.seed import seed_registry                        # noqa: E402
from bsde.ingestion.runner import stream_features                     # noqa: E402
from bsde.ingestion.vitaldb import VitalDBGridAdapter                 # noqa: E402

META_KEYS = (
    # from the ref, known before the window is decoded
    "caseid", "subjectid", "t_s", "rel_anestart_s", "rel_aneend_s", "anestart_s", "aneend_s",
    "opstart_s", "opend_s", "agents_present", "age", "sex", "asa", "bmi", "emop",
    "intraop_ppf", "intraop_mdz", "intraop_rocu", "intraop_vecu",
    # from the loader, known only after the window is read
    "bis", "sqi", "sr", "emg", "sensor_off", "nan_fraction",
)


def merge(out_path: str, parts) -> int:
    """Concatenate shard files into one table, de-duplicating on `recording_id`.

    Refuses to merge files with different column sets, for the same reason `stream_features` refuses to
    append to one: the result would parse cleanly and mean nothing. De-duplication is by recording id and
    keeps the FIRST occurrence, so a partial run that was later re-covered by a shard contributes its rows
    once. Every row is equally valid whichever process wrote it — the definition fingerprint is checked per
    file when that file is written.
    """
    import csv as _csv

    fields = None
    seen, n_in, n_dup = set(), 0, 0
    kept = []
    for p in parts:
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            print(f"   skip {p} (absent or empty)")
            continue
        with open(p, newline="") as fh:
            rd = _csv.DictReader(fh)
            if fields is None:
                fields = list(rd.fieldnames or [])
            elif list(rd.fieldnames or []) != fields:
                raise SystemExit(f"{p} has a different column set from the first part; refusing to merge.\n"
                                 f"  first: {fields}\n  this : {list(rd.fieldnames or [])}")
            n_here = 0
            for r in rd:
                n_in += 1
                n_here += 1
                rid = r.get("recording_id", "")
                if rid in seen:
                    n_dup += 1
                    continue
                seen.add(rid)
                kept.append(r)
        print(f"   {p}: {n_here} rows")
    if fields is None:
        raise SystemExit("nothing to merge")
    with open(out_path, "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(kept)
    print(f"   merged {n_in} rows from {len(parts)} parts -> {len(kept)} unique "
          f"({n_dup} duplicate recording ids dropped) -> {out_path}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--merge", default="", metavar="OUT",
                    help="merge mode: concatenate the files given as positional arguments into OUT, "
                         "de-duplicating on recording_id")
    ap.add_argument("parts", nargs="*", help="merge mode only: shard files to concatenate")
    ap.add_argument("--case-shard", type=int, default=0, dest="case_shard")
    ap.add_argument("--of", type=int, default=1, dest="n_case_shards")
    ap.add_argument("--n-cases", type=int, default=250, dest="n_cases")
    ap.add_argument("--grid-s", type=float, default=300.0, dest="grid_s")
    ap.add_argument("--window-s", type=float, default=30.0, dest="window_s")
    ap.add_argument("--max-windows", type=int, default=40, dest="max_windows")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results", "vitaldb_grid.csv"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--candidates", default="")
    a = ap.parse_args(argv)

    if a.merge:
        return merge(os.path.abspath(a.merge), [os.path.abspath(p) for p in a.parts])

    seed_registry()
    cands = (REGISTRY.all() if not a.candidates
             else [REGISTRY.get(n.strip()) for n in a.candidates.split(",") if n.strip()])

    adapter = VitalDBGridAdapter(n_cases=a.n_cases, grid_s=a.grid_s, window_s=a.window_s,
                                 max_windows=a.max_windows,
                                 case_shard=a.case_shard, n_case_shards=a.n_case_shards)
    print(f"streaming {adapter.name} -> {a.out}", flush=True)
    print(f"   candidates: {[c.name for c in cands]}", flush=True)
    stats = stream_features(adapter, cands, os.path.abspath(a.out), limit=a.limit,
                            meta_keys=META_KEYS)
    print(f"   {stats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
