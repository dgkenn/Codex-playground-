"""Re-extract ds005620 with the FULL candidate registry, to widen Challenge A's drug arm.

WHY. Challenge A's current evidence rests on a four-arm sign comparison, and Q33 established that
**name-mapping features across this project's two extraction pipelines is invalid** -- on identical
recordings `lempel_ziv` differs by 83.8 % between them and `relative_alpha_power` by 53.2 %. So the arms
must be within-pipeline, and the bsde-path tables are:

    sleep_edfx_five_stage   142 subjects, W/N1/N2/N3/REM   **17 features**   (the no-drug arm)
    ds004541                  7 usable subjects, GA        **18 features**
    ds005620                 21 subjects, propofol          **8 features**   <- the binding constraint

**ds005620 is the well-powered drug arm and it was extracted with only eight candidates.** Its manifest
records exactly which: `lempel_ziv`, `relative_alpha_power`, `relative_delta_power`, `spectral_edge_95`,
`spectral_entropy`, `uce_v1`, `whole_head_exponent`, `wpli_alpha`. **That was a candidate-list choice, not a
montage limit** -- the deposit has 65 channels, more than ds004541's 62, and ds004541 got all 18.

Re-running with `REGISTRY.all()` lifts the sleep-versus-propofol comparison from a six-feature intersection
to roughly seventeen, at 21 subjects rather than 7, entirely within one pipeline.

A NEW TABLE, NOT AN APPEND. `stream_features` refuses to append to a file whose column set changed, and it
is right to: the existing rows would be blank in the new columns and the table would parse cleanly and mean
nothing. This writes `ds005620_full.csv` and the old table stays exactly as it is, so every result already
built on it (E67, E30, E50, E52) remains reproducible against the file it actually used.

    python bsde/scripts/stream_ds005620_full.py
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.candidates.registry import REGISTRY                             # noqa: E402
from bsde.candidates.seed import seed_registry                            # noqa: E402
from bsde.ingestion.openneuro_brainvision import OpenNeuroBrainVisionAdapter   # noqa: E402
from bsde.ingestion.runner import stream_features                         # noqa: E402

OUT = os.path.join(HERE, "..", "results", "ds005620_full.csv")
META_KEYS = ("task", "acq", "run")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--window-s", type=float, default=30.0, dest="window_s")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)

    seed_registry()
    cands = REGISTRY.all()
    adapter = OpenNeuroBrainVisionAdapter("ds005620", dataset="ds005620", window_s=a.window_s)
    print(f"streaming {adapter.name} -> {a.out}", flush=True)
    print(f"   {len(cands)} candidates: {[c.name for c in cands]}", flush=True)
    stats = stream_features(adapter, cands, os.path.abspath(a.out), limit=a.limit, meta_keys=META_KEYS)
    print(f"   {stats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
