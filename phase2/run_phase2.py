"""run_phase2.py -- the post-unlock confirmation flow (Sec 3, 6, 12, 13).

Composes the frozen pipeline against the held-out hospital, end to end:

  require phase==2
   -> verify the frozen-pipeline hash matches the Phase-1-close stamp
   -> verify the frozen OBJECTS (correction transform, assignment fn) by content
      hash against the manifest
   -> unlock the held-out hospital (logged, hash-stamped)
   -> acquire the single-use run-once lock
   -> apply the frozen site-correction + assignment to the held-out embeddings
   -> CROSS-SITE REPRODUCIBILITY (Sec 6/9): frozen assignments vs an
      independently re-derived held-out clustering must agree at the ARI
      threshold; this promotes the primary phenotype provisional -> confirmed.
      EEG only, no outcome -- so it is firewall-safe.
   -> only if the primary phenotype is confirmed, run the ONE pre-registered
      adjusted association test (Sec 12)
   -> leakage negative control: under shuffled outcome the association collapses
      to chance (Sec 13).

Everything is logged. The outcome is supplied by a Phase-2-only loader that must
guarantee temporal precedence (EEG before outcome) per patient.
"""
from __future__ import annotations

import json
import os
from typing import Any

from analysis.audits import negative_control_shuffled_outcome
from analysis.cluster import PhenotypeAssigner, cross_site_reproducibility
from common.hashing import hash_object
from common.logging_utils import audit_log
from guards.heldout_guard import FirewallBreach, HeldoutGuard
from phase2.unlock_and_test import (
    _acquire_run_once,
    _primary_phenotype_id,
    adjusted_association,
)


def _verify_frozen_objects(manifest: dict[str, Any], correction, assigner) -> None:
    """Confirm the live frozen objects match the hashes pinned at Phase-1 close.

    This is the load-bearing check that the SAME correction transform and
    assignment function used in discovery are the ones applied to the held-out
    hospital -- not a re-fit that could have peeked at confirmation data.
    """
    ch = correction.content_hash()
    ah = assigner.content_hash()
    if ch != manifest.get("correction_transform_hash"):
        raise FirewallBreach(
            f"correction-transform hash mismatch: live {ch} != manifest "
            f"{manifest.get('correction_transform_hash')}"
        )
    if ah != manifest.get("assignment_fn_hash"):
        raise FirewallBreach(
            f"assignment-fn hash mismatch: live {ah} != manifest "
            f"{manifest.get('assignment_fn_hash')}"
        )


def run_phase2(
    cfg: dict[str, Any],
    heldout_tables: dict[str, Any],
    *,
    correction,
    assigner,
    manifest: dict[str, Any],
    expected_pipeline_hash: str,
    outcome,
    covariates: dict[str, Any] | None = None,
    temporal_precedence_verified: bool = False,
) -> dict[str, Any]:
    """Execute the single confirmatory analysis on the held-out hospital.

    `heldout_tables` is the compact-table dict (from load_compact_tables) for the
    held-out site, produced by the frozen Pass-1 pipeline. `correction` and
    `assigner` are the frozen objects whose hashes are in `manifest`.
    """
    import numpy as np

    # 1) Phase + integrity gates ------------------------------------------------
    if cfg.get("phase") != 2:
        raise FirewallBreach("Phase-2 confirmation requires phase==2")
    if not temporal_precedence_verified:
        raise FirewallBreach(
            "temporal precedence (EEG before outcome) not verified by the loader"
        )
    actual_pipeline_hash = hash_object(manifest)
    if actual_pipeline_hash != expected_pipeline_hash:
        raise FirewallBreach(
            f"frozen-pipeline hash mismatch: manifest {actual_pipeline_hash} "
            f"!= expected {expected_pipeline_hash}; aborting unlock."
        )
    _verify_frozen_objects(manifest, correction, assigner)

    # 2) Unlock + single-use lock ----------------------------------------------
    guard = HeldoutGuard(cfg)
    unlock_record = guard.unlock_held_out(manifest)
    _acquire_run_once(cfg, expected_pipeline_hash)  # one unlocked analysis, ever
    log_path = os.path.join(cfg.get("log_dir", "artifacts/logs"), "phase2.log")

    # 3) Apply the frozen pipeline to held-out embeddings ----------------------
    qc = heldout_tables["qc"]
    sites = [r.get("hospital") for r in qc]
    held = cfg["sites"]["held_out"]
    if any(s != held for s in sites):
        raise FirewallBreach(
            "Phase-2 tables contain non-held-out sites; expected only "
            f"{held!r}"
        )
    # One recording per patient (Sec 5): duplicates would inflate the effective
    # n and pseudo-replicate the single test (audit MEDIUM #7).
    pids = [r.get("patient_id") for r in qc]
    if len(set(pids)) != len(pids):
        raise FirewallBreach(
            "Held-out tables contain multiple recordings per patient; the "
            "one-recording-per-patient rule must be applied before the test."
        )
    X = np.asarray(heldout_tables["embedding"], dtype="float64")
    Xc = correction.transform(X, sites)            # new-batch alignment (EEG only)
    frozen_labels = assigner.assign(Xc)

    # 4) Cross-site reproducibility (EEG only) -> provisional => confirmed ------
    k = assigner.k
    redrived = PhenotypeAssigner(cfg, k=k).fit(Xc).assign(Xc)
    repro = cross_site_reproducibility(assigner, Xc, redrived, cfg)

    primary_id = _primary_phenotype_id(cfg)
    membership = (frozen_labels == primary_id).astype(int)

    report: dict[str, Any] = {
        "held_out_site": held,
        "n_recordings": int(X.shape[0]),
        "frozen_pipeline_hash": expected_pipeline_hash,
        "cross_site_reproducibility": repro,
        "primary_phenotype": primary_id,
        "primary_confirmed": bool(repro["pass"]),
        "unlock": unlock_record,
    }

    # 5) The single outcome test -- only if the primary phenotype is confirmed --
    if not repro["pass"]:
        report["outcome_test"] = None
        report["status"] = "primary_phenotype_not_reproducible"  # negative result
        audit_log(log_path, "phase2_single_test", result=report)
        _write(cfg, report)
        return report

    result = adjusted_association(membership, outcome, covariates, cfg)

    # 6) Leakage negative control: shuffled outcome -> association collapses ----
    leak = negative_control_shuffled_outcome(membership, outcome, cfg)

    report["outcome_test"] = result
    report["leakage_negative_control"] = leak
    report["status"] = "supported" if result["supported"] else "not_supported"
    audit_log(log_path, "phase2_single_test",
              frozen_pipeline_hash=expected_pipeline_hash, result=result,
              cross_site=repro)
    _write(cfg, report)
    return report


def _write(cfg: dict[str, Any], report: dict[str, Any]) -> str:
    path = os.path.join(cfg.get("artifacts_dir", "artifacts"),
                        "phase2", "phase2_report.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True, default=str)
    return path
