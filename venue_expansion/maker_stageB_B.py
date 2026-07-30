"""maker_stageB_B.py -- Build B (independent replication) driver for Stage B of the frozen
MM1 spec (venue_expansion/out/spec_MM1_frozen.json).

This is the canonical entry point named by the task's deliverable list. The actual pipeline
stages live under cache/mm1B/ (each stage is independently resumable and was run/cached
incrementally during development -- see maker_stageB_B.md for the full narrative, including two
divergences found and resolved/fixed along the way). Running this script end-to-end from a clean
cache reproduces venue_expansion/out/maker_stageB_B.json and is safe to re-run (every stage is
idempotent: it skips already-cached shards/days/files).

Pipeline (see maker_stageB_B.md section 0 for a description of each stage):
  1. extract_shard_B.py   -- 16 HF trade shards -> per-shard admitted-fill parquet
  2. merge_to_days_B.py   -- combine shards -> per-UTC-day fill partitions
  3. fetch_binance_B.py   -- Binance 1s klines, BTCUSDT/ETHUSDT, 2024-10-24..2026-01-28
  4. classify_days_B.py   -- per-fill (R,theta) classification vs the pre-fill spot clock
  5. reconcile_anchor_a_B.py -- sanity anchor (a): U1 cross-reconciliation
  6. aggregate_stats_B.py -- 20-cell grid, sanity anchors, verdict -> out/maker_stageB_B.json

Do NOT read any maker_stageB_A.* file -- this build's extraction, spot-clock join,
classification and statistics were written independently from the frozen spec text alone.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MM1B = os.path.join(HERE, "cache", "mm1B")

STAGES = [
    ("extract_shard_B.py", list(str(i) for i in range(16))),
    ("merge_to_days_B.py", []),
    ("fetch_binance_B.py", ["BTC", "ETH"]),
    ("classify_days_B.py", ["BTC", "ETH"]),
    ("reconcile_anchor_a_B.py", []),
    ("aggregate_stats_B.py", []),
]


def main():
    for script, args in STAGES:
        path = os.path.join(MM1B, script)
        cmd = [sys.executable, path] + args
        print(f"=== running {script} {' '.join(args)} ===", flush=True)
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"STAGE FAILED: {script} (exit {r.returncode}) -- stopping. "
                  f"Re-run this driver to resume; every stage is idempotent.", file=sys.stderr)
            sys.exit(r.returncode)
    print("Pipeline complete. See venue_expansion/out/maker_stageB_B.json and .md.")


if __name__ == "__main__":
    main()
