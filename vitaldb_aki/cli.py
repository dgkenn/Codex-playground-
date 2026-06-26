#!/usr/bin/env python3
"""cli.py -- entry point for the VitalDB postoperative-AKI study.

Stage 1 (built): cohort construction + KDIGO labeling.

    python vitaldb_aki/cli.py cohort            # build/refresh the labelable cohort
    python vitaldb_aki/cli.py cohort --refresh  # re-pull /cases + /labs from the API

Later stages (features, PK, models, leakage battery, external validation) attach
here as additional subcommands.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.config import load_yaml
from vitaldb_aki.cohort.build import build_cohort


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cohort", help="build the labelable KDIGO cohort")
    c.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "config.yaml"))
    c.add_argument("--refresh", action="store_true", help="re-pull tables from the API")
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    if args.cmd == "cohort":
        summary = build_cohort(cfg, refresh=args.refresh)
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
