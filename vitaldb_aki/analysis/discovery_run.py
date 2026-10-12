"""discovery_run.py -- EXPLORATORY discovery track (separate from the frozen
confirmatory pipeline, to preserve confirmatory integrity).

Stages (resumable; a container kill just resumes from the per-module _featcache):
  1. Build the ENRICHED feature matrix = confirmatory MODULES + 16 DISCOVERY
     modules -> cache/feature_matrix_enriched.csv  (this stage is the long pole:
     it extracts the new discovery families' numeric tracks per case).
  2. (discovery_screen.py) per-family x per-outcome incremental-value screen.
  3. (discovery_screen.py) enriched phenotype discovery on widely-available
     features (availability-aware, to avoid has-monitor artifact clusters).

Writes a stage-1 done marker so the watchdog knows extraction finished.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.config import load_yaml
from vitaldb_aki.features.build_matrix import build_matrix, MODULES, DISCOVERY_MODULES

_CFG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")


def build_enriched_matrix(cfg) -> dict:
    cdir = cfg["data"]["cache_dir"]
    print("[discovery] Stage 1: building ENRICHED matrix "
          f"({len(MODULES)} confirmatory + {len(DISCOVERY_MODULES)} discovery modules)...",
          flush=True)
    summary = build_matrix(
        cfg,
        modules=MODULES + DISCOVERY_MODULES,
        workers=12,
        out_name="feature_matrix_enriched.csv",
    )
    print(f"[discovery] Stage 1 DONE: n_rows={summary['n_rows']} "
          f"n_features={summary['n_features']} "
          f"tiers={summary.get('feature_sets')}", flush=True)
    with open(os.path.join(cdir, "_discovery_matrix_done.json"), "w", encoding="utf-8") as fh:
        import json
        json.dump({"n_rows": summary["n_rows"], "n_features": summary["n_features"]}, fh)
    return summary


def main():
    cfg = load_yaml(_CFG_PATH)
    build_enriched_matrix(cfg)
    # Stages 2-3 (per-family screen + enriched clustering) run from discovery_screen.py
    # once it lands; kept separate so the long extraction can start immediately.
    try:
        from vitaldb_aki.analysis.discovery_screen import run_discovery_screen
        print("[discovery] Stage 2-3: running per-family screen + enriched clustering...",
              flush=True)
        run_discovery_screen(cfg)
        print("[discovery] DISCOVERY RUN COMPLETE", flush=True)
    except ImportError:
        print("[discovery] discovery_screen not present yet; enriched matrix is ready "
              "for the screen stage.", flush=True)


if __name__ == "__main__":
    main()
