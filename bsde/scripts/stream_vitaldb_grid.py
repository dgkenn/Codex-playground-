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

    python bsde/scripts/stream_vitaldb_grid.py --n-cases 250 --out bsde/results/vitaldb_grid.csv
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-cases", type=int, default=250, dest="n_cases")
    ap.add_argument("--grid-s", type=float, default=300.0, dest="grid_s")
    ap.add_argument("--window-s", type=float, default=30.0, dest="window_s")
    ap.add_argument("--max-windows", type=int, default=40, dest="max_windows")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results", "vitaldb_grid.csv"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--candidates", default="")
    a = ap.parse_args(argv)

    seed_registry()
    cands = (REGISTRY.all() if not a.candidates
             else [REGISTRY.get(n.strip()) for n in a.candidates.split(",") if n.strip()])

    adapter = VitalDBGridAdapter(n_cases=a.n_cases, grid_s=a.grid_s, window_s=a.window_s,
                                 max_windows=a.max_windows)
    print(f"streaming {adapter.name} -> {a.out}", flush=True)
    print(f"   candidates: {[c.name for c in cands]}", flush=True)
    stats = stream_features(adapter, cands, os.path.abspath(a.out), limit=a.limit,
                            meta_keys=META_KEYS)
    print(f"   {stats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
