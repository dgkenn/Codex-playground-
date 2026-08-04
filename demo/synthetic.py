"""synthetic.py -- run the whole discovery->freeze->confirm lifecycle on
synthetic compact tables, exercising every real stage and the cross-process
freeze/unlock persistence. Used by `cli.py demo` and by tests.

The synthetic embeddings carry (a) a planted 3-cluster phenotype structure and
(b) a strong per-site additive offset (the confound the pipeline must remove).
One phenotype is made to precede a synthetic binary outcome; the held-out site
gets its own offset, so new-batch alignment is exercised too. No outcome ever
touches Phase 1.
"""
from __future__ import annotations

import os
from typing import Any

from common.config import load_yaml, validate
from common.hashing import hash_object


def _demo_cfg(work: str, config_path: str) -> dict[str, Any]:
    """Load the real config, then shrink the search for a fast, deterministic
    demo and point all artifacts at the scratch dir."""
    cfg = validate(load_yaml(config_path))
    cfg["artifacts_dir"] = work
    cfg["log_dir"] = os.path.join(work, "logs")
    cfg["frozen_manifest"] = os.path.join(work, "frozen", "manifest.json")
    cfg["sites"] = {"discovery": ["MGH", "BWH"], "held_out": "BIDMC",
                    "reproducibility_ari_threshold": 0.5}
    cfg["site_invariance"] = {
        "route_a_method": "combat",
        "site_probe": {"targets": ["hospital"], "chance_tolerance_auc": 0.65,
                       "cv_folds": 4},
    }
    cfg["clustering"] = {
        "algorithm": "gmm", "k_candidates": [2, 3, 4], "k_selection": "consensus_pac",
        "stability_min": 0.6,
        "consensus": {"n_resamples": 12, "subsample_fraction": 0.8,
                      "pac_low": 0.1, "pac_high": 0.9},
    }
    cfg["audits"] = {"acquisition_covariates": [], "site_purity_reject": 0.9,
                     "negative_controls": {"surrogate_n": 8}}
    cfg["model"]["checkpoint_sha256"] = "d" * 64  # demo: a real (non-placeholder) hash
    return cfg


def _gen(sites, offsets, n_per_cluster, d=16, seed=0, outcome_cluster=None):
    import numpy as np
    rng = np.random.default_rng(seed)
    centers = np.array([[0.0] * d, [9.0] * d,
                        [0.0] * (d // 2) + [9.0] * (d - d // 2)])
    rows, truth_by_rid, outcome_by_rid = [], {}, {}
    rid = 0
    for c, ctr in enumerate(centers):
        for k in range(n_per_cluster):
            site = sites[k % len(sites)]
            emb = ctr + rng.normal(scale=0.4, size=d) + offsets[site]
            r = f"{site}_{rid}"
            rows.append({
                "recording_id": r, "patient_id": f"p{rid}", "hospital": site,
                "device": f"dev_{site}", "sampling_rate": 200.0,
                "embedding": emb.tolist(),
                "features": {"bp_alpha_C3": float(emb[0])},
                "n_windows": 20, "harmonization_hash": "h",
                "keep_epoch_subset": False,
            })
            truth_by_rid[r] = c
            if outcome_cluster is not None:
                outcome_by_rid[r] = int(rng.random() < (0.85 if c == outcome_cluster else 0.12))
            rid += 1
    return rows, truth_by_rid, outcome_by_rid


def _write_tables(cfg, rows, subdir):
    from pipeline.writer import CompactTableWriter
    out = os.path.join(cfg["artifacts_dir"], subdir)
    with CompactTableWriter(cfg, out_dir=out, backend="jsonl") as w:
        for r in rows:
            w.write_row(r)
        w.flush()
    return out


def run_demo(work: str, config_path: str = "config.yaml") -> dict[str, Any]:
    """Execute the full lifecycle; return a JSON-able summary."""
    import numpy as np

    os.makedirs(work, exist_ok=True)
    cfg = _demo_cfg(work, config_path)
    target_true = 1

    # 1) Pass-1 stand-in: synthesize + persist compact tables (no raw, no model).
    disc_offsets = {"MGH": np.full(16, 5.0), "BWH": np.full(16, -5.0)}
    disc_rows, disc_truth, _ = _gen(["MGH", "BWH"], disc_offsets,
                                    n_per_cluster=70, seed=1)
    disc_dir = _write_tables(cfg, disc_rows, "discovery")

    held_offsets = {"BIDMC": np.full(16, 2.5)}
    held_rows, held_truth, held_outcome = _gen(["BIDMC"], held_offsets,
                                               n_per_cluster=90, seed=7,
                                               outcome_cluster=target_true)
    held_dir = _write_tables(cfg, held_rows, "heldout")

    # 2) Phase 1 -- discovery on the compact tables (no outcome, no held-out).
    from analysis.run_phase1 import run_phase1, write_report
    from pipeline.writer import load_compact_tables

    cfg["phase"] = 1
    disc_tables = load_compact_tables(cfg, out_dir=disc_dir)
    report = run_phase1(cfg, disc_tables)
    write_report(cfg, report)
    correction = report["_objects"]["correction"]
    assigner = report["_objects"]["assigner"]
    labels = report["_objects"]["labels"]

    # Name the primary phenotype = assigner label of the planted target cluster.
    truth_arr = np.array([disc_truth[r] for r in disc_tables["recording_id"]])
    primary_id = int(np.bincount(labels[truth_arr == target_true]).argmax())
    cfg["phase2"]["primary_phenotype"] = primary_id

    # 3) Freeze the four objects (Phase-1 close).
    from phase2.freeze import freeze_pipeline
    manifest, pipeline_hash = freeze_pipeline(
        cfg, correction=correction, assigner=assigner,
        checkpoint_sha256=cfg["model"]["checkpoint_sha256"])

    # 4) Phase 2 -- unlock held-out + single test, reloading frozen objects from
    #    disk (cross-process path) and re-verifying their hashes.
    from phase2.freeze import load_frozen_objects
    from phase2.run_phase2 import run_phase2

    cfg["phase"] = 2
    fc, fa = load_frozen_objects(cfg, manifest)
    held_tables = load_compact_tables(cfg, out_dir=held_dir)
    outcome = [held_outcome[r] for r in held_tables["recording_id"]]
    rep = run_phase2(cfg, held_tables, correction=fc, assigner=fa,
                     manifest=manifest, expected_pipeline_hash=pipeline_hash,
                     outcome=outcome, covariates=None,
                     temporal_precedence_verified=True)

    ot = rep.get("outcome_test") or {}
    return {
        "ok": rep["status"] == "supported",
        "workdir": work,
        "k_selected": report["k_selected"],
        "site_probe_gate_pass": report["site_probe_gate_pass"],
        "structure_is_real": report["negative_control_surrogate"]["structure_is_real"],
        "primary_phenotype": primary_id,
        "frozen_pipeline_hash": pipeline_hash[:12],
        "cross_site_ari": rep["cross_site_reproducibility"]["ari"],
        "primary_confirmed": rep["primary_confirmed"],
        "status": rep["status"],
        "odds_ratio": ot.get("odds_ratio"),
        "ci95": ot.get("ci95"),
        "leakage_null_p95_mi": rep.get("leakage_negative_control", {}).get("p95_mi_under_null"),
    }
