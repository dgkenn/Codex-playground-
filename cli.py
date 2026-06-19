#!/usr/bin/env python3
"""cli.py -- one entry point that drives the whole study lifecycle.

Subcommands mirror the protocol stages:

  validate   check config.yaml against the binding invariants
  pass1      stream -> harmonize -> embed -> features (needs the BDSP + model
             adapters wired; see pipeline/stream_fetch.py, pipeline/embed.py)
  phase1     run the discovery analysis on the compact tables; persist the
             fitted correction + assigner for freezing
  freeze     hash the four objects into the frozen manifest (Phase-1 close)
  phase2     unlock the held-out hospital and run the single confirmation test
  demo       run the ENTIRE lifecycle end-to-end on synthetic data (no BDSP, no
             model) -- proof that the discovery->freeze->confirm wiring composes

`demo` is self-contained and runs here; the other commands operate on real
artifacts and the two un-wired adapter seams (BDSP transport, CBraMod forward).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import config_hash, load_yaml, validate


# --------------------------------------------------------------------------
def cmd_validate(args) -> int:
    cfg = validate(load_yaml(args.config))
    print(f"config OK  | phase={cfg['phase']}  hash={config_hash(cfg)[:12]}")
    print(f"discovery={cfg['sites']['discovery']}  held_out={cfg['sites']['held_out']}")
    return 0


def cmd_pass1(args) -> int:
    """Stream -> harmonize -> frozen-embed -> features -> compact tables.

    Loads + hash-verifies + freezes the CBraMod checkpoint, then runs Pass 1 with
    a pilot `--limit` (default from config.execution.max_recordings). Needs the
    data transport credentials + torch/braindecode installed (see docs/RUNBOOK).
    """
    from pipeline.embed import FrozenEmbedder
    from pipeline.run_pass1 import run
    from pipeline.stream_fetch import make_client
    from pipeline.writer import CompactTableWriter

    cfg = validate(load_yaml(args.config))
    if cfg.get("phase") != 1:
        print("refusing: cmd_pass1 is a Phase-1 op; set phase: 1 in config")
        return 1
    embedder = FrozenEmbedder(cfg)
    embedder.load()                      # download + sha256-verify + freeze
    client = make_client(cfg)
    out = args.tables or cfg["artifacts_dir"]
    limit = None if args.limit is not None and args.limit <= 0 else args.limit
    with CompactTableWriter(cfg, out_dir=out) as writer:
        summary = run(cfg, writer, embedder=embedder, client=client, limit=limit)
    print(f"pass1: wrote={summary['n_written']}  consumed={summary['n_consumed']}  "
          f"hit_limit={summary['hit_limit']}  -> {out}")
    return 0


def cmd_phase1(args) -> int:
    from analysis.run_phase1 import run_phase1, write_report
    from phase2.freeze import frozen_paths
    from pipeline.writer import load_compact_tables

    cfg = validate(load_yaml(args.config))
    tables = load_compact_tables(cfg, out_dir=args.tables or cfg["artifacts_dir"])
    report = run_phase1(cfg, tables)
    path = write_report(cfg, report)

    # Persist the fitted frozen objects so a later `freeze` can hash them.
    paths = frozen_paths(cfg)
    report["_objects"]["correction"].save(paths["correction"])
    report["_objects"]["assigner"].save(paths["assigner"])
    bar = report["phenotype_bar"]
    print(f"phase1 OK  | k={report['k_selected']}  stable={bar['stable']}  "
          f"admitted(provisional)={bar['admitted']}")
    print(f"  site-probe gate pass={report['site_probe_gate_pass']}  "
          f"structure_real={report['negative_control_surrogate']['structure_is_real']}")
    print(f"  report -> {path}")
    return 0


def cmd_freeze(args) -> int:
    from analysis.cluster import PhenotypeAssigner
    from analysis.correct_sites import SiteCorrection
    from phase2.freeze import build_manifest, frozen_paths, write_manifest

    cfg = validate(load_yaml(args.config))
    paths = frozen_paths(cfg)
    correction = SiteCorrection.load(paths["correction"], cfg)
    assigner = PhenotypeAssigner.load(paths["assigner"], cfg)
    manifest = build_manifest(
        cfg, checkpoint_sha256=cfg["model"]["checkpoint_sha256"],
        correction_transform_hash=correction.content_hash(),
        assignment_fn_hash=assigner.content_hash())
    pipeline_hash = write_manifest(cfg, manifest)
    print(f"frozen OK  | pipeline_hash={pipeline_hash[:12]}  "
          f"primary_phenotype={manifest['primary_phenotype']}")
    print(f"  manifest -> {cfg.get('frozen_manifest', 'artifacts/frozen/manifest.json')}")
    return 0


def cmd_phase2(args) -> int:
    from phase2.freeze import load_frozen_objects, load_manifest
    from phase2.run_phase2 import run_phase2
    from pipeline.writer import load_compact_tables

    cfg = validate(load_yaml(args.config))
    manifest, pipeline_hash = load_manifest(cfg)
    correction, assigner = load_frozen_objects(cfg, manifest)
    tables = load_compact_tables(cfg, out_dir=args.tables)
    with open(args.outcome, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    rep = run_phase2(cfg, tables, correction=correction, assigner=assigner,
                     manifest=manifest, expected_pipeline_hash=pipeline_hash,
                     outcome=payload["outcome"], covariates=payload.get("covariates"),
                     temporal_precedence_verified=payload.get("temporal_precedence_verified", False))
    print(f"phase2 status: {rep['status']}")
    if rep.get("outcome_test"):
        t = rep["outcome_test"]
        print(f"  OR={t['odds_ratio']:.2f}  CI95={t['ci95']}  supported={t['supported']}")
    return 0


def cmd_tuh_test(args) -> int:
    """Run the NEDC TEST-file rsync probe to verify TUH access (external
    replication, Sec 15). Requires the user's NEDC-registered ssh key + reach."""
    from pipeline.tuh_fetch import TUHRsyncClient
    cfg = validate(load_yaml(args.config))
    client = TUHRsyncClient(cfg)
    res = client.test_connection()
    print(f"cmd: {res['cmd']}")
    print(f"TUH connectivity: {'OK' if res['ok'] else 'FAILED'} (rc={res['returncode']})")
    if not res["ok"]:
        print((res["stderr"] or res["stdout"]).strip()[:500])
    return 0 if res["ok"] else 1


def cmd_demo(args) -> int:
    """Full synthetic lifecycle in a scratch dir -- the one-command proof."""
    from demo.synthetic import run_demo
    work = args.workdir or tempfile.mkdtemp(prefix="heedb_demo_")
    summary = run_demo(work, config_path=args.config)
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="heedb", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="config.yaml")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("validate").set_defaults(func=cmd_validate)

    sp = sub.add_parser("pass1")
    sp.add_argument("--tables", help="output dir for compact tables (default artifacts_dir)")
    sp.add_argument("--limit", type=int, default=500,
                    help="pilot cap: max NEW recordings this run (<=0 = no cap). Default 500.")
    sp.set_defaults(func=cmd_pass1)

    s1 = sub.add_parser("phase1")
    s1.add_argument("--tables", help="dir with compact tables (default artifacts_dir)")
    s1.set_defaults(func=cmd_phase1)

    sub.add_parser("freeze").set_defaults(func=cmd_freeze)

    s2 = sub.add_parser("phase2")
    s2.add_argument("--tables", required=True, help="held-out compact tables dir")
    s2.add_argument("--outcome", required=True, help="JSON: {outcome, covariates, temporal_precedence_verified}")
    s2.set_defaults(func=cmd_phase2)

    sub.add_parser("tuh-test").set_defaults(func=cmd_tuh_test)

    sd = sub.add_parser("demo")
    sd.add_argument("--workdir", help="scratch dir (default: temp)")
    sd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
