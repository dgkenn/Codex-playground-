"""run_phase1.py -- Phase-1 discovery orchestrator (Sec 8-11).

Composes the disk-light analysis chain on the compact tables, in order:

  load compacts -> guard sites -> Route-A site correction -> site-probe GATE
  -> consensus-PAC k selection -> resampling stability -> fit assigner
  -> per-cluster site-alignment + leave-one-site-out -> phenotype bar
  -> interpretable characterization -> acquisition-covariate audit
  -> phenotype report.

It touches NO outcome and NO held-out site (every site is run through the
firewall guard). Its by-products -- the fitted `SiteCorrection` and
`PhenotypeAssigner` -- are returned so `phase2/freeze.py` can hash them into the
frozen manifest. Cross-site reproducibility is intentionally left `None` here
(the held-out hospital is locked in Phase 1); the bar therefore tops out at
"provisional".
"""
from __future__ import annotations

import json
import os
from typing import Any

from analysis.audits import acquisition_covariate_association, leave_one_site_out
from analysis.characterize import phenotype_feature_profile
from analysis.cluster import PhenotypeAssigner, consensus_pac, select_k, stability_score
from analysis.correct_sites import SiteCorrection
from analysis.phenotype_bar import apply_phenotype_bar, per_cluster_site_alignment
from analysis.site_probe import probe_site
from common.config import config_hash
from common.logging_utils import audit_log
from guards.heldout_guard import HeldoutGuard
from pipeline.features import feature_schema


def _feature_matrix(features: list[dict], names: list[str]):
    import numpy as np
    return np.array([[row.get(n, float("nan")) for n in names]
                     for row in features], dtype="float64")


def run_phase1(cfg: dict[str, Any], tables: dict[str, Any]) -> dict[str, Any]:
    """Run the Phase-1 chain on pre-loaded compact `tables`.

    `tables` is the dict returned by `pipeline.writer.load_compact_tables`.
    Returns a report dict and attaches the fitted transforms under
    `_objects` (not JSON-serialised) for the freeze step.
    """
    import numpy as np

    if cfg.get("phase") != 1:
        raise RuntimeError("run_phase1 is a Phase-1 operation; set phase: 1")

    guard = HeldoutGuard(cfg)
    qc = tables["qc"]
    sites = [r.get("hospital") for r in qc]
    for s in set(sites):                       # firewall: refuse held-out rows
        guard.check_site_access(s, context="run_phase1")

    X = np.asarray(tables["embedding"], dtype="float64")
    feature_names = feature_schema(cfg)
    F = _feature_matrix(tables["features"], feature_names)
    log_path = os.path.join(cfg.get("log_dir", "artifacts/logs"), "phase1.log")
    audit_log(log_path, "phase1_analysis_start",
              n=len(sites), config_hash=config_hash(cfg))

    # 1) Route-A site correction (fit on discovery embeddings).
    correction = SiteCorrection(cfg).fit(X, sites)
    Xc = correction.transform(X, sites)

    # 2) The GATE: site identity must be unrecoverable after correction.
    gate = {t: probe_site(Xc, [r.get(_qc_key(t)) for r in qc], cfg)
            for t in cfg["site_invariance"]["site_probe"]["targets"]
            if any(r.get(_qc_key(t)) is not None for r in qc)}
    gate_pass = all(g["pass"] for g in gate.values()) if gate else False

    # 3) Stability-based k selection (never interpretability).
    pac = consensus_pac(Xc, cfg)
    k = select_k(pac)
    stability = stability_score(Xc, k, cfg)

    # 4) Fit the (freezable) assignment function.
    assigner = PhenotypeAssigner(cfg, k=k).fit(Xc)
    labels = assigner.assign(Xc)

    # 5) Site-audit signals: per-cluster purity + leave-one-site-out.
    alignment = per_cluster_site_alignment(labels, sites)
    loso = leave_one_site_out(Xc, sites, lambda: PhenotypeAssigner(cfg, k=k), cfg)

    # 6) The phenotype bar (cross_site=None -> provisional ceiling in Phase 1).
    bar = apply_phenotype_bar(
        stability=stability, site_alignment=alignment, cfg=cfg,
        cross_site=None, loso_min_ari=loso.get("min_ari"),
    )

    # 7) Interpretable characterization (descriptive only).
    profile = phenotype_feature_profile(F, labels, feature_names)

    # 8) Acquisition-covariate audit (batch red-flag).
    covs = {c: [r.get(c) for r in qc]
            for c in cfg.get("audits", {}).get("acquisition_covariates", [])
            if any(r.get(c) is not None for r in qc)}
    acq = acquisition_covariate_association(labels, covs, cfg) if covs else {}

    report = {
        "n_recordings": int(X.shape[0]),
        "site_probe_gate": gate,
        "site_probe_gate_pass": gate_pass,
        "k_selected": int(k),
        "pac_by_k": pac,
        "stability": stability,
        "leave_one_site_out": loso,
        "phenotype_bar": bar,
        "characterization": {str(c): v["top_distinguishing_features"]
                             for c, v in profile["phenotypes"].items()},
        "acquisition_covariate_association": acq,
        "frozen_object_hashes": {
            "correction_transform_hash": correction.content_hash(),
            "assignment_fn_hash": assigner.content_hash(),
        },
        "config_hash": config_hash(cfg),
    }
    audit_log(log_path, "phase1_analysis_done",
              k=int(k), n_admitted=bar["n_admitted"], gate_pass=gate_pass)
    report["_objects"] = {"correction": correction, "assigner": assigner,
                          "labels": labels}
    return report


def _qc_key(target: str) -> str:
    """Map a site-probe target name to its qc column."""
    return {"hospital": "hospital", "device": "device",
            "sampling_rate": "sampling_rate"}.get(target, target)


def write_report(cfg: dict[str, Any], report: dict[str, Any]) -> str:
    """Persist the JSON-serialisable part of the report."""
    path = os.path.join(cfg.get("artifacts_dir", "artifacts"), "phase1_report.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    serialisable = {k: v for k, v in report.items() if k != "_objects"}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(serialisable, fh, indent=2, sort_keys=True, default=str)
    return path
