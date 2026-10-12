"""Re-stream the 81 suppression-onset cases at a 60 s grid, densely, around the onset only.

WHY, AND WHY THIS IS NOT MOVING A GOALPOST. E26 answered Challenge C in the negative and named the 300 s
grid as its binding limitation **in its scope note, written before the run**: a feature whose warning
arrives 60 s ahead of burst suppression is invisible at 300 s resolution. Re-testing a limitation declared
in advance is legitimate. Searching for a resolution at which the answer flips would not be, so the
follow-up (E27) re-registers with the **same statistic, same gates, same horizon rule and same primary**,
and varies only the sampling.

THE PLAN IS BUILT FROM THE CLINICAL RECORD, NOT FROM ANY CANDIDATE. `vitaldb_fine_plan.json` lists, per
case, windows every 60 s from 1,800 s before the first `BIS/SR > 0` window to 300 s after it. The onset
times come from the device's suppression score and the muscle filter; no candidate column is consulted, and
the 81 cases are exactly those E26 already found eligible.

COST. 81 cases at ~35 windows each — 2,796 windows against E26's 597 eligible ones, a five-fold density
increase for a third of the transfer of a full re-stream, because the expensive operation is fetching a
case's 9.4 MB waveform and that is per case.

    for k in 0 1 2 3; do
      python bsde/scripts/stream_vitaldb_fine.py --case-shard $k --of 4 \
             --out bsde/results/vitaldb_fine.s$k.csv &
    done; wait
    python bsde/scripts/stream_vitaldb_grid.py --merge bsde/results/vitaldb_fine.csv \
           bsde/results/vitaldb_fine.s?.csv
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.candidates.registry import REGISTRY                         # noqa: E402
from bsde.candidates.seed import seed_registry                        # noqa: E402
from bsde.ingestion.runner import stream_features                     # noqa: E402
from bsde.ingestion.vitaldb import VitalDBTargetedAdapter             # noqa: E402

from stream_vitaldb_grid import META_KEYS                             # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", default=os.path.join(HERE, "..", "results", "vitaldb_fine_plan.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results", "vitaldb_fine.csv"))
    ap.add_argument("--window-s", type=float, default=30.0, dest="window_s")
    ap.add_argument("--case-shard", type=int, default=0, dest="case_shard")
    ap.add_argument("--of", type=int, default=1, dest="n_case_shards")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)

    plan = json.load(open(os.path.abspath(a.plan)))
    seed_registry()
    cands = REGISTRY.all()
    adapter = VitalDBTargetedAdapter(plan, window_s=a.window_s, dataset="vitaldb_grid",
                                     case_shard=a.case_shard, n_case_shards=a.n_case_shards)
    print(f"streaming {adapter.name} over {len(plan)} planned cases -> {a.out}", flush=True)
    stats = stream_features(adapter, cands, os.path.abspath(a.out), limit=a.limit,
                            meta_keys=META_KEYS)
    print(f"   {stats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
