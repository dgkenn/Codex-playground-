"""End-to-end Phase-2 confirmation test.

Runs a small Phase-1 discovery to obtain the REAL frozen objects (site
correction + phenotype assigner), freezes them into a manifest, then drives the
held-out confirmation flow and asserts:

  * the happy path: held-out cross-site reproducibility passes, the primary
    phenotype is promoted to confirmed, and the single adjusted-OR test recovers
    the planted phenotype<->outcome association (OR>1, CI excludes 1);
  * the leakage negative control collapses under shuffled outcome;
  * the run-once lock makes a second test abort;
  * every firewall gate trips: wrong phase, wrong pipeline hash, and a
    tampered (re-fit) frozen object are all refused BEFORE any unlock.

Skipped without numpy/scikit-learn/statsmodels.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np  # noqa: F401
    import sklearn  # noqa: F401
    import statsmodels.api  # noqa: F401
    HAVE_STACK = True
except ImportError:
    HAVE_STACK = False

from tests.test_integrity import base_cfg

CENTERS = None


def _cfg():
    cfg = base_cfg()
    cfg["artifacts_dir"] = tempfile.mkdtemp()
    cfg["log_dir"] = tempfile.mkdtemp()
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
    return cfg


def _centers(d=16):
    return np.array([[0.0] * d,
                     [9.0] * d,
                     [0.0] * (d // 2) + [9.0] * (d - d // 2)])


def _rows(sites, offsets, n_per_cluster, d=16, seed=0, outcome_cluster=None):
    """Synthetic compact rows with a planted 3-cluster structure. If
    outcome_cluster is given, also return a binary outcome correlated with it."""
    rng = np.random.default_rng(seed)
    centers = _centers(d)
    rows, truth, outcome = [], [], []
    rid = 0
    for c, ctr in enumerate(centers):
        for k in range(n_per_cluster):
            site = sites[k % len(sites)]
            emb = ctr + rng.normal(scale=0.4, size=d) + offsets[site]
            rows.append({
                "recording_id": f"{site}_{rid}", "patient_id": f"p{rid}",
                "hospital": site, "device": f"dev_{site}", "sampling_rate": 200.0,
                "embedding": emb.tolist(),
                "features": {"bp_alpha_C3": float(emb[0])},
                "n_windows": 20, "harmonization_hash": "h",
                "keep_epoch_subset": False,
            })
            truth.append(c)
            if outcome_cluster is not None:
                p = 0.85 if c == outcome_cluster else 0.12
                outcome.append(int(rng.random() < p))
            rid += 1
    return rows, np.array(truth), np.array(outcome)


def _tables_from_rows(rows):
    return {
        "recording_id": [r["recording_id"] for r in rows],
        "embedding": [r["embedding"] for r in rows],
        "features": [{"recording_id": r["recording_id"], **r["features"]} for r in rows],
        "qc": [{k: v for k, v in r.items() if k not in ("embedding", "features")} for r in rows],
    }


@unittest.skipUnless(HAVE_STACK, "scientific stack not installed")
class TestPhase2EndToEnd(unittest.TestCase):
    def _discover_and_freeze(self, cfg):
        """Run Phase-1, return (correction, assigner, manifest, pipeline_hash,
        primary_id) where primary_id is the assigner label of true cluster 1."""
        from analysis.run_phase1 import run_phase1
        from phase2.freeze import build_manifest

        offs = {"MGH": np.full(16, 5.0), "BWH": np.full(16, -5.0)}
        rows, truth, _ = _rows(["MGH", "BWH"], offs, n_per_cluster=70, seed=1)
        cfg["phase"] = 1
        report = run_phase1(cfg, _tables_from_rows(rows))
        correction = report["_objects"]["correction"]
        assigner = report["_objects"]["assigner"]
        labels = report["_objects"]["labels"]

        # Map true cluster 1 -> assigner label by majority vote.
        target_true = 1
        votes = labels[truth == target_true]
        primary_id = int(np.bincount(votes).argmax())

        cfg["phase2"]["primary_phenotype"] = primary_id
        manifest = build_manifest(
            cfg, checkpoint_sha256="a" * 64,
            correction_transform_hash=correction.content_hash(),
            assignment_fn_hash=assigner.content_hash())
        from common.hashing import hash_object
        return correction, assigner, manifest, hash_object(manifest), primary_id

    def test_happy_path_then_run_once(self):
        from phase2.run_phase2 import run_phase2
        from phase2.unlock_and_test import RunOnceViolation

        cfg = _cfg()
        corr, asg, manifest, phash, primary_id = self._discover_and_freeze(cfg)

        # Held-out site with its OWN offset (tests new-batch alignment), outcome
        # correlated with true cluster 1 (= primary_id after assignment).
        offs = {"BIDMC": np.full(16, 2.5)}
        rows, _, outcome = _rows(["BIDMC"], offs, n_per_cluster=90, seed=7,
                                 outcome_cluster=1)
        tables = _tables_from_rows(rows)

        cfg["phase"] = 2
        rep = run_phase2(cfg, tables, correction=corr, assigner=asg,
                         manifest=manifest, expected_pipeline_hash=phash,
                         outcome=outcome.tolist(), covariates=None,
                         temporal_precedence_verified=True)

        self.assertTrue(rep["cross_site_reproducibility"]["pass"])
        self.assertTrue(rep["primary_confirmed"])
        self.assertEqual(rep["status"], "supported")
        self.assertGreater(rep["outcome_test"]["odds_ratio"], 1.0)
        self.assertTrue(rep["outcome_test"]["ci_excludes_1"])
        # Leakage control: shuffled-outcome MI null is small.
        self.assertLess(rep["leakage_negative_control"]["p95_mi_under_null"], 0.2)

        # Run-once: a second test on the same artifacts dir aborts.
        with self.assertRaises(RunOnceViolation):
            run_phase2(cfg, tables, correction=corr, assigner=asg,
                       manifest=manifest, expected_pipeline_hash=phash,
                       outcome=outcome.tolist(), covariates=None,
                       temporal_precedence_verified=True)

    def test_firewall_gates_trip_before_unlock(self):
        from guards.heldout_guard import FirewallBreach
        from phase2.run_phase2 import run_phase2

        cfg = _cfg()
        corr, asg, manifest, phash, _ = self._discover_and_freeze(cfg)
        offs = {"BIDMC": np.full(16, 2.5)}
        rows, _, outcome = _rows(["BIDMC"], offs, n_per_cluster=30, seed=3,
                                 outcome_cluster=1)
        tables = _tables_from_rows(rows)

        # (a) wrong phase
        cfg["phase"] = 1
        with self.assertRaises(FirewallBreach):
            run_phase2(cfg, tables, correction=corr, assigner=asg,
                       manifest=manifest, expected_pipeline_hash=phash,
                       outcome=outcome.tolist(), temporal_precedence_verified=True)

        # (b) wrong pipeline hash
        cfg["phase"] = 2
        with self.assertRaises(FirewallBreach):
            run_phase2(cfg, tables, correction=corr, assigner=asg,
                       manifest=manifest, expected_pipeline_hash="b" * 64,
                       outcome=outcome.tolist(), temporal_precedence_verified=True)

        # (c) tampered frozen object: a re-fit assigner has a different hash
        from analysis.cluster import PhenotypeAssigner
        Xc = corr.transform(np.asarray(tables["embedding"]),
                            [r["hospital"] for r in rows])
        tampered = PhenotypeAssigner(cfg, k=asg.k).fit(Xc)
        with self.assertRaises(FirewallBreach):
            run_phase2(cfg, tables, correction=corr, assigner=tampered,
                       manifest=manifest, expected_pipeline_hash=phash,
                       outcome=outcome.tolist(), temporal_precedence_verified=True)

        # (d) temporal precedence not verified
        with self.assertRaises(FirewallBreach):
            run_phase2(cfg, tables, correction=corr, assigner=asg,
                       manifest=manifest, expected_pipeline_hash=phash,
                       outcome=outcome.tolist(), temporal_precedence_verified=False)

        # No run-once lock should have been created by any refused attempt.
        lock = os.path.join(cfg["artifacts_dir"], "phase2", "RUN_ONCE.lock")
        self.assertFalse(os.path.exists(lock))


if __name__ == "__main__":
    unittest.main(verbosity=2)
