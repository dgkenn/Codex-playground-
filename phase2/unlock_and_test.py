"""unlock_and_test.py -- apply the frozen pipeline to the held-out hospital and
run the single pre-registered outcome test ONCE (Sec 3, 12, 14).

Sequence (all logged, hash-stamped):
  1. require phase == 2;
  2. load + verify the frozen manifest (hash matches the Phase-1-close stamp);
  3. unlock the held-out hospital via the guard;
  4. apply the frozen harmonization, correction, and assignment functions;
  5. run the ONE primary phenotype<->outcome contrast, adjusted for the
     pre-specified covariates;
  6. write a run-once lock so the test can never be repeated.

A persistent lock file makes "run once" enforceable across processes: any second
attempt aborts.
"""
from __future__ import annotations

import json
import os
from typing import Any

from common.logging_utils import audit_log
from guards.heldout_guard import FirewallBreach, HeldoutGuard
from phase2.freeze import load_manifest


def _lock_path(cfg: dict[str, Any]) -> str:
    return os.path.join(cfg.get("artifacts_dir", "artifacts"),
                        "phase2", "RUN_ONCE.lock")


class RunOnceViolation(RuntimeError):
    """Raised if the single confirmatory test is attempted more than once."""


def _acquire_run_once(cfg: dict[str, Any], frozen_pipeline_hash: str) -> None:
    path = _lock_path(cfg)
    if os.path.exists(path):
        with open(path) as fh:
            prior = fh.read()
        raise RunOnceViolation(
            f"Phase-2 test already executed (lock at {path}): {prior!r}. "
            "The confirmatory contrast is single-use; voiding it requires a "
            "logged protocol deviation, not a re-run."
        )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Exclusive create: fails if another process raced us to the lock.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps({"frozen_pipeline_hash": frozen_pipeline_hash}))


def adjusted_association(phenotype_membership, outcome, covariates, cfg: dict[str, Any]) -> dict[str, Any]:
    """The single test: covariate-adjusted association of the primary phenotype
    with the outcome (effect size + 95% CI). Logistic regression by default."""
    import numpy as np
    import statsmodels.api as sm

    y = np.asarray(outcome, dtype="float64")
    design = [np.asarray(phenotype_membership, dtype="float64")]
    names = ["phenotype"]
    for name, vals in (covariates or {}).items():
        v = np.asarray(vals, dtype="float64")
        design.append(v)
        names.append(name)
    X = np.column_stack(design)
    X = sm.add_constant(X)
    model = sm.Logit(y, X).fit(disp=0)
    coef = model.params[1]            # phenotype coefficient (index 0 is const)
    ci = model.conf_int()[1]
    crit = cfg["phase2"]["association_criterion"]
    or_point = float(np.exp(coef))
    or_ci = (float(np.exp(ci[0])), float(np.exp(ci[1])))
    excludes_1 = or_ci[0] > 1.0 or or_ci[1] < 1.0
    meets_min = or_point >= crit.get("min_effect_size_or", 1.0)
    return {
        "effect_measure": "adjusted_odds_ratio",
        "odds_ratio": or_point,
        "ci95": or_ci,
        "p_value": float(model.pvalues[1]),
        "ci_excludes_1": bool(excludes_1),
        "meets_min_effect": bool(meets_min),
        "supported": bool(excludes_1 and meets_min),
        "covariates": names[1:],
    }


def run(cfg: dict[str, Any], heldout_data_loader, *,
        expected_pipeline_hash: str) -> dict[str, Any]:  # pragma: no cover - needs full stack + held-out
    """Execute the single confirmatory test. `heldout_data_loader` returns
    (corrected_embeddings, outcome, covariates) for the held-out hospital after
    applying the frozen harmonization+correction; it must itself route the site
    through the guard's unlock."""
    if cfg.get("phase") != 2:
        raise FirewallBreach("Phase-2 test requires phase==2")

    manifest, frozen_pipeline_hash = load_manifest(cfg)
    if frozen_pipeline_hash != expected_pipeline_hash:
        raise FirewallBreach(
            f"frozen-pipeline hash mismatch: manifest {frozen_pipeline_hash} "
            f"!= expected {expected_pipeline_hash}. Aborting unlock."
        )

    guard = HeldoutGuard(cfg)
    unlock_record = guard.unlock_held_out(manifest)

    _acquire_run_once(cfg, frozen_pipeline_hash)  # single-use enforcement

    X, outcome, covariates = heldout_data_loader(manifest)
    assigner = _load_frozen_assigner(cfg, manifest)
    membership = (assigner.assign(X) == _primary_phenotype_id(cfg)).astype(int)
    result = adjusted_association(membership, outcome, covariates, cfg)

    log_path = os.path.join(cfg.get("log_dir", "artifacts/logs"), "phase2.log")
    audit_log(log_path, "phase2_single_test",
              frozen_pipeline_hash=frozen_pipeline_hash,
              unlock=unlock_record, result=result)
    return result


def _load_frozen_assigner(cfg, manifest):
    """Load the frozen PhenotypeAssigner and verify its content hash against the
    manifest before it is used (Sec 3)."""
    from phase2.freeze import load_frozen_objects
    _correction, assigner = load_frozen_objects(cfg, manifest)
    return assigner


def _primary_phenotype_id(cfg) -> int:  # pragma: no cover - config dependent
    pid = cfg.get("phase2", {}).get("primary_phenotype")
    if pid is None or str(pid).upper().startswith("TO-CONFIRM"):
        raise FirewallBreach("phase2.primary_phenotype must be pinned before unlock")
    return int(pid)
