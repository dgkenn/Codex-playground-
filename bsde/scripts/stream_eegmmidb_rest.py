"""Stream the eegmmidb BASELINE runs into a feature table. Task runs are never touched here.

The separation is the point: the label for Challenge B's alternative (E28) is built from the imagery runs by
`build_eegmmidb_bci_label.py`, and this table must contain nothing from them, or the association is circular.

    python bsde/scripts/stream_eegmmidb_rest.py --out bsde/results/eegmmidb_rest.csv
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.candidates.registry import REGISTRY                     # noqa: E402
from bsde.candidates.seed import seed_registry                    # noqa: E402
from bsde.ingestion.eegmmidb import EEGMMIDBRestAdapter           # noqa: E402
from bsde.ingestion.runner import stream_features                 # noqa: E402

META_KEYS = ("run", "condition", "sfreq")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results", "eegmmidb_rest.csv"))
    ap.add_argument("--window-s", type=float, default=55.0, dest="window_s")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    seed_registry()
    adapter = EEGMMIDBRestAdapter(window_s=a.window_s)
    print(f"streaming {adapter.name} -> {a.out}", flush=True)
    print(f"   {stream_features(adapter, REGISTRY.all(), os.path.abspath(a.out), limit=a.limit, meta_keys=META_KEYS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
