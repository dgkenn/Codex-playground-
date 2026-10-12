"""Stream the four BIS subparameters onto the SAME VitalDB grid `vitaldb_grid.csv` already covers.

WHY A SECOND TABLE RATHER THAN MORE COLUMNS ON THE FIRST. `stream_features` refuses to append to a table
whose column set has changed, and it is right to: a resumed run would leave the old rows blank in the new
columns and the table would parse cleanly and mean nothing. So this writes `vitaldb_bis.csv` with the same
`recording_id` key, and analysis joins the two. The join is exact, not approximate — the recording id is
built from caseid and window start time, and this script constructs the adapter with the SAME parameters the
grid was built with (250 cases, 300 s grid, 30 s windows, 40 windows max). Those defaults are duplicated
here deliberately: if they drift, the join silently produces fewer matched rows, so `--verify-join` checks
the overlap against the existing grid BEFORE any download starts.

WHAT THIS COSTS. VitalDB serves whole waveform tracks with no range requests: about 9.4 MB per case, ~2.3
min per case single-stream, so 250 cases is ~9.5 h in one process. Sharding is by CASE (see
`stream_vitaldb_grid.py` for why) so four parallel shards cost four times one shard's bandwidth rather than
four times the whole job's.

    for k in 0 1 2 3; do
      python bsde/scripts/stream_vitaldb_bis.py --case-shard $k --of 4 \
             --out bsde/results/vitaldb_bis.s$k.csv &
    done; wait
    python bsde/scripts/stream_vitaldb_grid.py --merge bsde/results/vitaldb_bis.csv \
             bsde/results/vitaldb_bis.s*.csv

WHAT IT IS FOR. QUEUE.md Q22: BIS is the incumbent Challenge C needs and it exists only where a monitor
recorded it. The feasibility probe reached a case-grouped median absolute error of 5.01 BIS units using
features that were missing three of BIS's four actual ingredients; this adds them so the comparison can be
made properly, and PER BIS RANGE. Whatever comes out is a BIS-LIKE INDEX and never BIS.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.candidates.bis_comparator import bis_candidates                 # noqa: E402
from bsde.ingestion.runner import stream_features                         # noqa: E402
from bsde.ingestion.vitaldb import VitalDBGridAdapter                     # noqa: E402

# Duplicated from the grid run so the recording ids line up. Changing one without the other breaks the join,
# which is why --verify-join exists.
GRID_DEFAULTS = dict(n_cases=250, grid_s=300.0, window_s=30.0, max_windows=40)

META_KEYS = ("caseid", "t_s", "bis", "sqi", "sr", "emg", "sensor_off", "nan_fraction")


def verify_join(refs, grid_path: str) -> int:
    """Report how many of this run's recording ids already exist in the grid, before spending any bandwidth.

    A LOW OVERLAP IS A CONFIGURATION ERROR, NOT A FINDING. It means the adapter parameters here have drifted
    from the ones that built the grid, and the resulting table would join to a biased subset of windows.
    """
    if not os.path.exists(grid_path):
        print(f"   grid {grid_path} absent — cannot verify the join")
        return 1
    with open(grid_path, newline="") as fh:
        grid_ids = {r["recording_id"] for r in csv.DictReader(fh)}
    mine = {r.recording_id for r in refs}
    both = mine & grid_ids
    print(f"   join check: {len(mine)} windows here, {len(grid_ids)} in the grid, {len(both)} shared "
          f"({100.0 * len(both) / max(1, len(mine)):.1f}% of this run)")
    if len(both) < 0.9 * len(mine):
        print("   REFUSING: under 90% of this run's windows exist in the grid. The adapter parameters have "
              "drifted from the ones that built it; fix them rather than joining a biased subset.")
        return 2
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--case-shard", type=int, default=0, dest="case_shard")
    ap.add_argument("--of", type=int, default=1, dest="n_case_shards")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results", "vitaldb_bis.csv"))
    ap.add_argument("--grid", default=os.path.join(HERE, "..", "results", "vitaldb_grid.csv"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--verify-join", action="store_true", dest="verify_join",
                    help="check the recording-id overlap with the grid and exit without downloading")
    a = ap.parse_args(argv)

    cands = bis_candidates()
    adapter = VitalDBGridAdapter(case_shard=a.case_shard, n_case_shards=a.n_case_shards, **GRID_DEFAULTS)

    if a.verify_join:
        return verify_join(adapter.list_recordings(), os.path.abspath(a.grid))

    print(f"streaming {adapter.name} -> {a.out}", flush=True)
    print(f"   candidates: {[c.name for c in cands]}", flush=True)
    stats = stream_features(adapter, cands, os.path.abspath(a.out), limit=a.limit, meta_keys=META_KEYS)
    print(f"   {stats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
