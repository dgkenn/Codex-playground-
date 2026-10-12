#!/usr/bin/env python3
"""run_shard.py -- one parallel Pass-1 worker (shard k of N).

Processes only the recordings whose stable hash selects shard k, streaming them
from BDSP, embedding with the frozen CBraMod backbone (uses a GPU automatically
when torch sees one), and writing compact tables into a SHARED output dir with a
per-worker fragment prefix (`wKK-`) so N workers never collide. Each worker keeps
its own resume file `OUT/pass1_done_wKK.txt`, so the run is fully resumable and
re-running picks up where it left off.

Launch 16 workers on one box with scripts/run_parallel.sh; watch resource usage
with scripts/monitor_usage.py (see docs/RUN_OVERNIGHT.md).

Usage:
    AWS_PROFILE=physionet python3 scripts/run_shard.py \
        --shard 0 --num-shards 16 --out artifacts --limit 0
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import load_yaml, validate
from pipeline.run_pass1 import run
from pipeline.stream_fetch import make_client
from pipeline.writer import CompactTableWriter


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shard", type=int, required=True, help="worker index, 0..N-1")
    ap.add_argument("--num-shards", type=int, required=True, help="total workers N")
    ap.add_argument("--out", default="artifacts", help="shared output dir")
    ap.add_argument("--limit", type=int, default=0, help="cap NEW recordings (0 = no cap)")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    if not (0 <= args.shard < args.num_shards):
        ap.error("--shard must be in [0, --num-shards)")

    cfg = validate(load_yaml(args.config))
    if cfg.get("phase") != 1:
        print("refusing: run_shard is a Phase-1 op; set phase: 1 in config")
        return 1
    cfg["artifacts_dir"] = args.out
    cfg["log_dir"] = os.path.join(args.out, "logs")

    tag = f"w{args.shard:02d}-"
    done_path = os.path.join(args.out, f"pass1_done_w{args.shard:02d}.txt")
    limit = None if args.limit <= 0 else args.limit

    # Real frozen backbone (CBraMod). GPU is used automatically if torch sees one.
    from pipeline.embed import FrozenEmbedder
    embedder = FrozenEmbedder(cfg)
    embedder.load()                       # download + sha256-verify + freeze
    client = make_client(cfg)

    t0 = time.time()
    print(f"[shard {args.shard}/{args.num_shards}] start -> {args.out}", flush=True)
    with CompactTableWriter(cfg, out_dir=args.out, fragment_prefix=tag) as writer:
        summary = run(cfg, writer, embedder=embedder, client=client,
                      limit=limit, shard=(args.shard, args.num_shards),
                      done_path=done_path)
    print(f"[shard {args.shard}/{args.num_shards}] done: wrote={summary['n_written']} "
          f"consumed={summary['n_consumed']} hit_limit={summary['hit_limit']} "
          f"({time.time()-t0:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
