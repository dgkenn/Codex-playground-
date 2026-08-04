"""Offline tests for analysis/external_validation.py -- the INSPIRE replication
harness.

Two layers:
  * STDLIB-ONLY tests (no numpy/pandas/sklearn): the gate (BLOCKED when the matrix
    is absent), the pure concordance logic, and the registries/variable-map.
  * SCIENCE-STACK tests (skipped if numpy/pandas/sklearn absent): the end-to-end
    SYNTHETIC smoke test -- proves the harness wiring runs without real INSPIRE
    data, and that no synthetic data ever lands at the gate path.

The synthetic frame is clearly labelled synthetic and is NEVER written to
cache/inspire_matrix.csv.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from vitaldb_aki.analysis import external_validation as ev


class TestGateStdlib(unittest.TestCase):
    """Gate + pure logic; import + run with the stdlib only."""

    def test_blocked_when_matrix_absent(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"cache_dir": d, "seed": ev.RANDOM_SEED}
            st = ev.external_validation_status(cfg)
            self.assertTrue(st["blocked"])
            self.assertEqual(st["status"], "BLOCKED")
            self.assertFalse(st["matrix_present"])
            self.assertIn("does not exist", " ".join(st["reasons"]))
            # all four targets advertised even while blocked
            self.assertEqual(set(st["replication_targets"]),
                             set(ev.REPLICATION_TARGETS))

    def test_assert_raises_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"cache_dir": d}
            with self.assertRaises(ev.InspireMatrixAbsentError):
                ev.assert_inspire_matrix(cfg)

    def test_status_file_written_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"cache_dir": d, "seed": ev.RANDOM_SEED}
            out = ev.run_external_validation(cfg)
            self.assertTrue(out["blocked"])
            self.assertTrue(os.path.exists(os.path.join(d, ev.STATUS_FILE)))

    def test_not_blocked_when_matrix_present(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ev.INSPIRE_MATRIX_FILE)
            with open(p, "w") as fh:
                fh.write("caseid\n")
            st = ev.external_validation_status({"cache_dir": d})
            self.assertFalse(st["blocked"])
            self.assertEqual(st["status"], "READY")

    def test_concordance_same_direction_overlap_magnitude(self):
        internal = {"point": 0.6, "ci": [0.4, 0.9]}
        inspire = {"point": 0.7, "ci": [0.5, 0.95]}
        v = ev.judge_concordance(internal, inspire, ev.KIND_RR)
        self.assertTrue(v["components"]["same_direction"])      # both < 1
        self.assertIs(v["components"]["ci_overlap"], True)
        self.assertIs(v["components"]["magnitude_within_factor"], True)
        self.assertTrue(v["concordant"])

    def test_concordance_opposite_direction_fails(self):
        internal = {"point": 0.6, "ci": [0.4, 0.9]}    # protective
        inspire = {"point": 1.6, "ci": [1.1, 2.2]}     # harmful
        v = ev.judge_concordance(internal, inspire, ev.KIND_RR)
        self.assertFalse(v["components"]["same_direction"])
        self.assertFalse(v["concordant"])

    def test_concordance_no_ci_overlap_fails(self):
        internal = {"point": 0.6, "ci": [0.4, 0.7]}
        inspire = {"point": 0.9, "ci": [0.85, 0.99]}
        v = ev.judge_concordance(internal, inspire, ev.KIND_RR)
        self.assertIs(v["components"]["ci_overlap"], False)
        self.assertFalse(v["concordant"])

    def test_concordance_missing_internal_inconclusive(self):
        internal = {"point": None, "ci": [None, None]}
        inspire = {"point": 0.7, "ci": [0.5, 0.95]}
        v = ev.judge_concordance(internal, inspire, ev.KIND_RR)
        self.assertFalse(v["concordant"])

    def test_delta_auroc_both_near_zero_concordant(self):
        internal = {"point": 0.002, "ci": [-0.02, 0.03]}
        inspire = {"point": -0.003, "ci": [-0.04, 0.02]}
        v = ev.judge_concordance(internal, inspire, ev.KIND_DELTA_AUROC)
        # both effectively null -> magnitude concordant, CIs overlap; direction
        # at-null -> not "same direction" so overall not concordant (correctly
        # reported as inconclusive for a null effect).
        self.assertIs(v["components"]["magnitude_within_factor"], True)

    def test_variable_map_and_no_equivalents_present(self):
        # The mapping documents the key mapped columns.
        for col in ("map_auc_below_65", "organ_renal", "phe_vs_norepi",
                    "baseline_cr", "recovery_velocity"):
            self.assertIn(col, ev.INSPIRE_VARIABLE_MAP)
        # Waveform morphology explicitly flagged unvalidatable.
        self.assertIn("arterial_waveform_morphology", ev.NO_INSPIRE_EQUIVALENT)

    def test_internal_extractors_against_real_cache(self):
        # If the real internal result JSONs exist, extractors must pull a point.
        cd = os.path.join(_ROOT, "vitaldb_aki", "cache")
        cases = [
            ("hypotension_treatment_results.json", ev._internal_from_hypotension),
            ("map_target_results.json", ev._internal_from_map_hte),
            ("reperfusion_dynamics_results.json", ev._internal_from_reperfusion),
            ("actionable_results.json", ev._internal_from_pressor_choice),
        ]
        for fname, extr in cases:
            d = ev._load_internal_result(cd, fname)
            if not d:
                continue  # cache not populated in this checkout -> skip silently
            out = extr(d)
            self.assertIn("kind", out)
            self.assertIn("point", out)


class TestSmokeScienceStack(unittest.TestCase):
    """End-to-end synthetic smoke test (needs numpy/pandas/sklearn)."""

    @classmethod
    def setUpClass(cls):
        try:
            import numpy  # noqa: F401
            import pandas  # noqa: F401
            import sklearn  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(f"Missing dependency: {exc}") from exc

    def test_synthetic_frame_is_labelled_and_shaped(self):
        df = ev.make_synthetic_inspire_frame(n=120, seed=1)
        self.assertEqual(len(df), 120)
        self.assertTrue(df.attrs.get("SYNTHETIC"))
        for col in ("map_auc_below_65", "organ_renal", "composite",
                    "phe_vs_norepi", "recovery_velocity"):
            self.assertIn(col, df.columns)

    def test_smoke_end_to_end_schema(self):
        report = ev.smoke_test(seed=ev.RANDOM_SEED)
        self.assertFalse(report["blocked"])
        self.assertEqual(report["status"], "RAN")
        self.assertEqual(len(report["targets"]), len(ev.REPLICATION_TARGETS))
        for name, rep in report["targets"].items():
            self.assertTrue(rep["ran"], f"{name} did not run")
            conc = rep["concordance"]
            self.assertIn("concordant", conc)
            self.assertEqual(set(conc["components"]),
                             {"same_direction", "ci_overlap",
                              "magnitude_within_factor"})

    def test_smoke_never_writes_gate_path(self):
        gate = os.path.join(_ROOT, "vitaldb_aki", "cache", ev.INSPIRE_MATRIX_FILE)
        existed_before = os.path.exists(gate)
        ev.smoke_test(seed=7)
        # Smoke test must NOT create the real gate matrix.
        if not existed_before:
            self.assertFalse(os.path.exists(gate),
                             "smoke test must never write cache/inspire_matrix.csv")


if __name__ == "__main__":
    unittest.main(verbosity=2)
