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

_DEFAULT_CFG = os.path.join(os.path.dirname(__file__), "config.yaml")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cohort", help="build the renal-only KDIGO cohort (§5/§6)")
    c.add_argument("--config", default=_DEFAULT_CFG)
    c.add_argument("--refresh", action="store_true", help="re-pull tables from the API")

    cc = sub.add_parser("cohort-composite", help="build the composite end-organ cohort (primary)")
    cc.add_argument("--config", default=_DEFAULT_CFG)
    cc.add_argument("--refresh", action="store_true")

    m = sub.add_parser("matrix", help="build the modeling feature matrix (§7-9)")
    m.add_argument("--config", default=_DEFAULT_CFG)
    m.add_argument("--workers", type=int, default=12)

    mo = sub.add_parser("model", help="run the incremental-value harness (§9-12)")
    mo.add_argument("--config", default=_DEFAULT_CFG)
    mo.add_argument("--clf", default="logreg", choices=["logreg", "gbm"])
    mo.add_argument("--seed", type=int, default=0)
    mo.add_argument("--target", default=None, help="outcome col (default: config evaluation.target)")

    args = ap.parse_args()
    cfg = load_yaml(args.config)

    if args.cmd == "cohort":
        print(json.dumps(build_cohort(cfg, refresh=args.refresh), indent=2))
    elif args.cmd == "cohort-composite":
        from vitaldb_aki.cohort.build_composite import build_composite_cohort
        print(json.dumps(build_composite_cohort(cfg, refresh=args.refresh), indent=2))
    elif args.cmd == "matrix":
        from vitaldb_aki.features.build_matrix import build_matrix
        print(json.dumps(build_matrix(cfg, workers=args.workers), indent=2))
    elif args.cmd == "model":
        from vitaldb_aki.models.run import run
        print(json.dumps(run(cfg, model_name=args.clf, seed=args.seed, target=args.target), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
