#!/usr/bin/env python3
"""run_real_pilot.py -- a real-data Phase-1 pilot on HEEDB via BDSP.

Streams real HEEDB EDFs from the credentialed BDSP access point, harmonizes them,
embeds with the FROZEN CBraMod foundation model (falls back to the transparent
PlaceholderEmbedder only if torch/braindecode are unavailable), computes the
interpretable features, writes the compact tables, and runs the Phase-1 analysis
-- printing real metrics and writing a JSON report.

This is a PILOT/validation harness, not the registered study: it balances a small
number of recordings per discovery site so clustering has both sites, and it does
NOT enforce adults-only (the catalog's AgeAtVisit is largely empty; the real study
must join HEEDB_patients.csv for age). Credentials come from the AWS profile named
in config.yaml::data.heedb.profile via ~/.aws -- never from this repo.

Usage:
    AWS_PROFILE=physionet python scripts/run_real_pilot.py
Env overrides: PILOT_PER_SITE (default 30), PILOT_MAX_DURATION (default 300),
    PILOT_WORKDIR (default /tmp/heedb_real_pilot), PILOT_EMBEDDER (cbramod|placeholder).
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.run_phase1 import run_phase1, write_report
from common.config import load_yaml
from guards.heldout_guard import HeldoutGuard
from pipeline.run_pass1 import load_completed, process_recording
from pipeline.stream_fetch import HEEDBBDSPClient
from pipeline.writer import CompactTableWriter, load_compact_tables


def _embedder(cfg):
    which = os.environ.get("PILOT_EMBEDDER", "cbramod").lower()
    if which == "cbramod":
        try:
            from pipeline.embed import FrozenEmbedder
            emb = FrozenEmbedder(cfg)
            emb.load()
            print(">>> embedder: REAL frozen CBraMod (checkpoint verified)", flush=True)
            return emb
        except Exception as e:  # torch/braindecode/checkpoint unavailable
            print(f">>> CBraMod unavailable ({type(e).__name__}: {str(e)[:100]}); "
                  "falling back to PlaceholderEmbedder", flush=True)
    from pipeline.embed import PlaceholderEmbedder
    print(">>> embedder: PlaceholderEmbedder (PLUMBING ONLY -- not the science)", flush=True)
    return PlaceholderEmbedder(cfg)


def main() -> int:
    per_site = int(os.environ.get("PILOT_PER_SITE", "30"))
    max_dur = float(os.environ.get("PILOT_MAX_DURATION", "300"))
    work = os.environ.get("PILOT_WORKDIR", "/tmp/heedb_real_pilot")

    cfg = load_yaml("config.yaml")
    cfg["phase"] = 1
    cfg["artifacts_dir"] = work
    cfg["log_dir"] = work + "/logs"
    cfg["data"]["heedb"]["max_duration_s"] = max_dur
    # Scale clustering down for a pilot-sized cohort.
    cfg.setdefault("clustering", {})
    cfg["clustering"].update({
        "algorithm": "gmm", "k_candidates": [2, 3, 4], "k_selection": "consensus_pac",
        "stability_min": 0.6,
        "consensus": {"n_resamples": 20, "subsample_fraction": 0.8, "pac_low": 0.1, "pac_high": 0.9},
    })
    cfg.setdefault("audits", {}).update({"negative_controls": {"surrogate_n": 10},
                                         "acquisition_covariates": [], "site_purity_reject": 0.85})

    emb = _embedder(cfg)
    client = HEEDBBDSPClient(cfg)
    guard = HeldoutGuard(cfg)
    done = load_completed(cfg)
    t0 = time.time()
    n = 0
    print(f">>> PASS 1: real HEEDB EDFs, up to {per_site}/site, max_duration={max_dur}s", flush=True)
    with CompactTableWriter(cfg, out_dir=work, backend="jsonl") as w:
        for site in cfg["sites"]["discovery"]:
            guard.check_site_access(site, context="real_pilot")
            seen = 0
            for ref in client.list_recordings(site):
                if seen >= per_site:
                    break
                guard.check_site_access(ref.hospital, context="real_pilot:ref")
                if ref.recording_id in done:
                    continue
                seen += 1
                try:
                    row = process_recording(cfg, ref, emb, client)
                except Exception as e:
                    print(f"    skip {ref.recording_id}: {type(e).__name__}: {str(e)[:80]}", flush=True)
                    continue
                if row is None:
                    continue
                w.write_row(row)
                n += 1
                if n % 10 == 0:
                    print(f"    ... {n} rows ({time.time()-t0:.0f}s)", flush=True)
            w.flush()
            print(f"    {site}: total {n} rows so far ({time.time()-t0:.0f}s)", flush=True)

    tables = load_compact_tables(cfg, out_dir=work)
    by_site = {s: sum(1 for r in tables["qc"] if r["hospital"] == s)
               for s in sorted({r["hospital"] for r in tables["qc"]})}
    print(f">>> Pass 1 wrote {n} rows in {time.time()-t0:.0f}s; by site: {by_site}", flush=True)

    if n < 4:
        print(">>> too few rows for Phase-1; stopping.", flush=True)
        return 1
    print(">>> PHASE 1 analysis on real compact tables ...", flush=True)
    rep = run_phase1(cfg, tables)
    path = write_report(cfg, rep)
    summary = {
        "n_recordings": rep["n_recordings"], "by_site": by_site,
        "embedding_dim": len(tables["embedding"][0]),
        "site_probe_gate_pass": rep["site_probe_gate_pass"],
        "site_probe_auc": {k: round(v["auc"], 3) for k, v in rep["site_probe_gate"].items()},
        "k_selected": rep["k_selected"], "pac_by_k": rep["pac_by_k"],
        "leave_one_site_out": rep["leave_one_site_out"],
        "negative_control": rep["negative_control_surrogate"],
        "n_admitted": rep["phenotype_bar"]["n_admitted"],
        "elapsed_s": round(time.time() - t0, 0),
    }
    with open(work + "/pilot_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(">>> REAL PHASE-1 SUMMARY:")
    print(json.dumps(summary, indent=2))
    print(f">>> report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
