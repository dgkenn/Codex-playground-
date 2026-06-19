"""freeze.py -- freeze the four objects at Phase-1 close (Sec 3).

At Phase-1 close, four objects are frozen and hashed before the held-out
hospital is unlocked:
  (a) the model checkpoint,
  (b) the on-the-fly harmonization config,
  (c) the embedding-correction transform,
  (d) the phenotype-assignment function.

This module assembles those hashes into a manifest, writes it, and stamps the
combined frozen-pipeline hash. The held-out guard refuses to unlock unless this
manifest is complete and placeholder-free.
"""
from __future__ import annotations

import json
import os
from typing import Any

from common.config import harmonization_hash
from common.hashing import hash_object
from common.logging_utils import audit_log


def build_manifest(cfg: dict[str, Any], *, checkpoint_sha256: str,
                   correction_transform_hash: str,
                   assignment_fn_hash: str) -> dict[str, Any]:
    """Assemble the frozen manifest (the four objects + provenance)."""
    manifest = {
        "config_version": cfg.get("config_version"),
        "checkpoint_sha256": checkpoint_sha256,
        "harmonization_hash": harmonization_hash(cfg),
        "correction_transform_hash": correction_transform_hash,
        "assignment_fn_hash": assignment_fn_hash,
        "primary_phenotype": cfg.get("phase2", {}).get("primary_phenotype"),
        "outcome": cfg.get("phase2", {}).get("outcome"),
        "association_criterion": cfg.get("phase2", {}).get("association_criterion"),
    }
    return manifest


def write_manifest(cfg: dict[str, Any], manifest: dict[str, Any]) -> str:
    """Persist the manifest and append the frozen-pipeline hash to the log."""
    path = cfg.get("frozen_manifest", "artifacts/frozen/manifest.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    pipeline_hash = hash_object(manifest)
    payload = {"manifest": manifest, "frozen_pipeline_hash": pipeline_hash}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    audit_log(os.path.join(cfg.get("log_dir", "artifacts/logs"), "freeze.log"),
              "freeze", frozen_pipeline_hash=pipeline_hash, path=path)
    return pipeline_hash


def load_manifest(cfg: dict[str, Any]) -> tuple[dict[str, Any], str]:
    path = cfg.get("frozen_manifest", "artifacts/frozen/manifest.json")
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload["manifest"], payload["frozen_pipeline_hash"]


# ---- frozen-object persistence (cross-process freeze -> unlock) ------------
def frozen_paths(cfg: dict[str, Any]) -> dict[str, str]:
    """Canonical on-disk locations for the serialised frozen objects."""
    base = os.path.join(cfg.get("artifacts_dir", "artifacts"), "frozen")
    return {"correction": os.path.join(base, "correction.json"),
            "assigner": os.path.join(base, "assigner.pkl")}


def freeze_pipeline(cfg: dict[str, Any], *, correction, assigner,
                    checkpoint_sha256: str) -> tuple[dict[str, Any], str]:
    """Persist the correction + assigner, build & write the manifest, and stamp
    the combined frozen-pipeline hash. The one call that closes Phase 1 (Sec 3).
    """
    paths = frozen_paths(cfg)
    corr_hash = correction.save(paths["correction"])
    asg_hash = assigner.save(paths["assigner"])
    manifest = build_manifest(
        cfg, checkpoint_sha256=checkpoint_sha256,
        correction_transform_hash=corr_hash, assignment_fn_hash=asg_hash)
    pipeline_hash = write_manifest(cfg, manifest)
    return manifest, pipeline_hash


def load_frozen_objects(cfg: dict[str, Any], manifest: dict[str, Any]):
    """Reload the frozen correction + assigner and RE-VERIFY each by content
    hash against the manifest before returning. Raises FirewallBreach on any
    mismatch -- the guarantee that the held-out site sees the exact discovery
    objects, not a re-fit (Sec 3)."""
    from analysis.cluster import PhenotypeAssigner
    from analysis.correct_sites import SiteCorrection
    from guards.heldout_guard import FirewallBreach

    paths = frozen_paths(cfg)
    correction = SiteCorrection.load(paths["correction"], cfg)
    assigner = PhenotypeAssigner.load(paths["assigner"], cfg)
    if correction.content_hash() != manifest.get("correction_transform_hash"):
        raise FirewallBreach("loaded correction transform fails manifest hash")
    if assigner.content_hash() != manifest.get("assignment_fn_hash"):
        raise FirewallBreach("loaded assignment fn fails manifest hash")
    return correction, assigner
