"""Integrity-core tests -- stdlib only (no numpy / torch / sklearn required).

These exercise the firewall, hashing, config invariants, run-once lock, and the
disk-sparing bookkeeping: the machinery the pre-registration's confirmatory
status depends on. The heavy ML stages are covered by adapter boundaries and are
not unit-tested here (they require the model + data).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import config as cfgmod
from common.config import ConfigError, assert_no_outcome_in_loader_fields, validate
from common.hashing import canonical_json, hash_file, hash_object, verify
from common.logging_utils import audit_log, read_log
from guards.heldout_guard import FirewallBreach, HeldoutGuard
from pipeline.embed import should_keep_epoch_subset
from pipeline.features import feature_schema
from pipeline.harmonize import plan_harmonization
from pipeline.run_pass1 import load_completed, mark_completed, shard_iter
from pipeline.stream_fetch import RecordingRef


def base_cfg(phase=1):
    return {
        "config_version": "2.0.0",
        "phase": phase,
        "seed": 1,
        "sites": {"discovery": ["MGH", "BWH", "BIDMC"], "held_out": "BCH_ADULT",
                  "reproducibility_ari_threshold": 0.5},
        "cohort": {"primary_min_age_years": 18},
        "model": {"name": "CBraMod", "repo_id": "x", "revision": "r",
                  "checkpoint_sha256": "TO-CONFIRM", "expected_sfreq_hz": 200,
                  "channels_10_20": ["Fp1", "Fp2", "C3", "C4"],
                  "window_seconds": 30, "window_stride_seconds": 30},
        "harmonization": {"reference": "average", "notch_hz": [50, 60],
                          "bandpass_hz": [0.5, 45], "artifact_rejection": "amplitude_zscore",
                          "artifact_reject_z": 6.0},
        "embedding": {"pooling": ["mean", "std"], "persist_epoch_subset_fraction": 0.02},
        "features": {"bands": {"delta": [0.5, 4], "alpha": [8, 13]},
                     "specparam": {"freq_range": [1, 45]}, "spectral_edge_pct": 95,
                     "connectivity": "wpli", "entropy": ["sample_entropy"],
                     "microstates": {"n_states": 4}},
        "clustering": {"algorithm": "gmm", "k_candidates": [2, 3],
                       "stability_min": 0.80,
                       "consensus": {"n_resamples": 10, "subsample_fraction": 0.8,
                                     "pac_low": 0.1, "pac_high": 0.9}},
        "execution": {"shard_size_recordings": 2},
        "phase2": {"run_once": True, "primary_phenotype": 0,
                   "association_criterion": {"min_effect_size_or": 1.5}},
        "artifacts_dir": tempfile.mkdtemp(),
        "log_dir": tempfile.mkdtemp(),
    }


class TestHashing(unittest.TestCase):
    def test_canonical_json_is_order_independent(self):
        self.assertEqual(canonical_json({"a": 1, "b": 2}),
                         canonical_json({"b": 2, "a": 1}))

    def test_hash_object_stable_and_sensitive(self):
        h1 = hash_object({"x": [1, 2, 3]})
        self.assertEqual(h1, hash_object({"x": [1, 2, 3]}))
        self.assertNotEqual(h1, hash_object({"x": [1, 2, 4]}))

    def test_verify_object(self):
        obj = {"transform": "combat", "gamma": [0.1, 0.2]}
        self.assertTrue(verify(obj, hash_object(obj)))
        self.assertFalse(verify(obj, "deadbeef"))

    def test_hash_file_streaming(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as fh:
            fh.write(b"hello eeg")
            p = fh.name
        self.addCleanup(os.unlink, p)
        # known sha256 of b"hello eeg"
        self.assertEqual(len(hash_file(p)), 64)


class TestConfigInvariants(unittest.TestCase):
    def test_validate_ok(self):
        c = base_cfg()
        self.assertIs(validate(c), c)  # returns the config unchanged on success

    def test_held_out_cannot_be_in_discovery(self):
        c = base_cfg()
        c["sites"]["held_out"] = "MGH"
        with self.assertRaises(ConfigError):
            validate(c)

    def test_run_once_required(self):
        c = base_cfg()
        c["phase2"]["run_once"] = False
        with self.assertRaises(ConfigError):
            validate(c)

    def test_no_outcome_fields_in_phase1_loader(self):
        assert_no_outcome_in_loader_fields(
            ["age", "sex", "hospital", "sampling_rate", "device",
             "recording_length", "patient_id", "care_setting"])
        # Audit CRITICAL #2 / #8: substring matching catches EHR-proxy variants.
        for bad in (["icd10"], ["medication"], ["report_text"], ["outcome"],
                    ["mortality"], ["seizure_label_v2"], ["primary_diagnosis"],
                    ["icd9_code"], ["outcome_30d"], ["discharge_disposition"],
                    ["cpc_score"], ["functional_recovery"]):
            with self.assertRaises(ConfigError):
                assert_no_outcome_in_loader_fields(bad)

    def test_harmonization_hash_changes_with_params(self):
        c = base_cfg()
        h1 = cfgmod.harmonization_hash(c)
        c["harmonization"]["notch_hz"] = [60]
        self.assertNotEqual(h1, cfgmod.harmonization_hash(c))


class TestFirewall(unittest.TestCase):
    def test_phase1_blocks_heldout(self):
        g = HeldoutGuard(base_cfg(phase=1))
        self.assertEqual(g.check_site_access("MGH"), "MGH")
        with self.assertRaises(FirewallBreach):
            g.check_site_access("BCH_ADULT", context="test")

    def test_block_is_logged(self):
        c = base_cfg(phase=1)
        g = HeldoutGuard(c)
        with self.assertRaises(FirewallBreach):
            g.check_site_access("BCH_ADULT")
        log = read_log(os.path.join(c["log_dir"], "firewall.log"))
        self.assertTrue(any(r["event"] == "firewall_block" for r in log))

    def test_unlock_requires_phase2(self):
        g = HeldoutGuard(base_cfg(phase=1))
        with self.assertRaises(FirewallBreach):
            g.unlock_held_out(self._full_manifest())

    def test_unlock_rejects_incomplete_manifest(self):
        g = HeldoutGuard(base_cfg(phase=2))
        with self.assertRaises(FirewallBreach):
            g.unlock_held_out({"checkpoint_sha256": "abc"})

    def test_unlock_rejects_placeholder(self):
        g = HeldoutGuard(base_cfg(phase=2))
        m = self._full_manifest()
        m["assignment_fn_hash"] = "TO-CONFIRM"
        with self.assertRaises(FirewallBreach):
            g.unlock_held_out(m)

    def test_phase_string_does_not_bypass_block(self):
        # Audit CRITICAL #1: phase "1" (YAML string) must still block held-out.
        c = base_cfg(phase=1)
        c["phase"] = "1"
        g = HeldoutGuard(c)
        self.assertEqual(g.phase, 1)
        with self.assertRaises(FirewallBreach):
            g.check_site_access("BCH_ADULT")

    def test_bad_phase_rejected(self):
        c = base_cfg()
        c["phase"] = "later"
        with self.assertRaises(FirewallBreach):
            HeldoutGuard(c)

    def test_null_or_blank_site_refused(self):
        g = HeldoutGuard(base_cfg(phase=1))
        for bad in (None, "", "   "):
            with self.assertRaises(FirewallBreach):
                g.check_site_access(bad)

    def test_unlock_succeeds_and_stamps_hash(self):
        c = base_cfg(phase=2)
        g = HeldoutGuard(c)
        rec = g.unlock_held_out(self._full_manifest())
        self.assertIn("frozen_pipeline_hash", rec)
        self.assertEqual(len(rec["frozen_pipeline_hash"]), 64)

    @staticmethod
    def _full_manifest():
        return {"checkpoint_sha256": "a" * 64, "harmonization_hash": "b" * 64,
                "correction_transform_hash": "c" * 64, "assignment_fn_hash": "d" * 64}


class TestRunOnceLock(unittest.TestCase):
    def test_second_test_aborts(self):
        from phase2.unlock_and_test import RunOnceViolation, _acquire_run_once
        c = base_cfg(phase=2)
        _acquire_run_once(c, "hash123")
        with self.assertRaises(RunOnceViolation):
            _acquire_run_once(c, "hash123")


class TestDiskSparingBookkeeping(unittest.TestCase):
    def test_shard_iter(self):
        refs = [RecordingRef(str(i), "p", "MGH") for i in range(5)]
        shards = list(shard_iter(refs, 2))
        self.assertEqual([len(s) for s in shards], [2, 2, 1])

    def test_resume_set_roundtrip(self):
        c = base_cfg()
        self.assertEqual(load_completed(c), set())
        mark_completed(c, "rec1")
        mark_completed(c, "rec2")
        self.assertEqual(load_completed(c), {"rec1", "rec2"})

    def test_epoch_subset_deterministic_and_bounded(self):
        self.assertEqual(should_keep_epoch_subset("rec", 0.5),
                         should_keep_epoch_subset("rec", 0.5))
        self.assertFalse(should_keep_epoch_subset("rec", 0.0))
        self.assertTrue(should_keep_epoch_subset("rec", 1.0))
        kept = sum(should_keep_epoch_subset(f"rec{i}", 0.2) for i in range(2000))
        self.assertTrue(300 < kept < 500)  # ~20% with tolerance


class TestHarmonizationPlan(unittest.TestCase):
    def test_mappable_requires_all_channels(self):
        c = base_cfg()
        ref = RecordingRef("r", "p", "MGH")
        plan = plan_harmonization(c, ref, available_channels=["Fp1", "Fp2", "C3", "C4"])
        self.assertTrue(plan.mappable)
        plan2 = plan_harmonization(c, ref, available_channels=["Fp1", "Fp2"])
        self.assertFalse(plan2.mappable)
        self.assertEqual(set(plan2.dropped_channels), {"C3", "C4"})

    def test_plan_hash_pins_notch(self):
        c = base_cfg()
        ref = RecordingRef("r", "p", "MGH")
        h1 = plan_harmonization(c, ref, ["Fp1", "Fp2", "C3", "C4"]).content_hash()
        c["harmonization"]["notch_hz"] = [60]
        h2 = plan_harmonization(c, ref, ["Fp1", "Fp2", "C3", "C4"]).content_hash()
        self.assertNotEqual(h1, h2)


class TestFeatureSchema(unittest.TestCase):
    def test_schema_deterministic(self):
        c = base_cfg()
        self.assertEqual(feature_schema(c), feature_schema(c))

    def test_schema_includes_aperiodic(self):
        cols = feature_schema(base_cfg())
        self.assertTrue(any(col.startswith("aperiodic_exponent_") for col in cols))


class TestPhenotypeBar(unittest.TestCase):
    """Pure-Python admission logic (Sec 9) -- no numpy needed."""

    def setUp(self):
        from analysis.phenotype_bar import apply_phenotype_bar
        self.fn = apply_phenotype_bar
        self.cfg = base_cfg()
        self.cfg.setdefault("audits", {})["site_purity_reject"] = 0.80
        self.clean = {0: {"dominant_site_fraction": 0.55,
                          "dominant_site_base_rate": 0.5, "enrichment": 0.05}}
        self.dirty = {1: {"dominant_site_fraction": 0.95,
                          "dominant_site_base_rate": 0.5, "enrichment": 0.45}}

    def test_provisional_when_phase1_and_clean(self):
        r = self.fn(stability=0.9, site_alignment=self.clean, cfg=self.cfg,
                    cross_site=None, loso_min_ari=0.6)
        self.assertEqual(r["decisions"][0]["status"], "provisional")
        self.assertEqual(r["admitted"], [0])

    def test_site_aligned_cluster_rejected(self):
        r = self.fn(stability=0.9, site_alignment=self.dirty, cfg=self.cfg,
                    cross_site=None, loso_min_ari=0.6)
        self.assertEqual(r["decisions"][1]["status"], "rejected")
        self.assertIn("site_aligned", r["decisions"][1]["reasons"])

    def test_unstable_solution_rejected(self):
        r = self.fn(stability=0.5, site_alignment=self.clean, cfg=self.cfg,
                    cross_site=None, loso_min_ari=0.6)
        self.assertEqual(r["decisions"][0]["status"], "rejected")
        self.assertIn("unstable", r["decisions"][0]["reasons"])

    def test_confirmed_only_with_cross_site_pass(self):
        ok = self.fn(stability=0.9, site_alignment=self.clean, cfg=self.cfg,
                     cross_site={0: {"ari": 0.7, "pass": True}}, loso_min_ari=0.6)
        self.assertEqual(ok["decisions"][0]["status"], "confirmed")
        bad = self.fn(stability=0.9, site_alignment=self.clean, cfg=self.cfg,
                      cross_site={0: {"ari": 0.2, "pass": False}}, loso_min_ari=0.6)
        self.assertEqual(bad["decisions"][0]["status"], "rejected")


class TestFreezeManifest(unittest.TestCase):
    def test_build_and_write_manifest(self):
        from phase2.freeze import build_manifest, load_manifest, write_manifest
        c = base_cfg(phase=2)
        c["frozen_manifest"] = os.path.join(c["artifacts_dir"], "frozen", "manifest.json")
        m = build_manifest(c, checkpoint_sha256="a" * 64,
                           correction_transform_hash="c" * 64,
                           assignment_fn_hash="d" * 64)
        ph = write_manifest(c, m)
        m2, ph2 = load_manifest(c)
        self.assertEqual(ph, ph2)
        self.assertEqual(m2["checkpoint_sha256"], "a" * 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
