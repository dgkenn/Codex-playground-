"""Drives the full synthetic lifecycle (cli demo) + frozen-object persistence.

Confirms the discovery -> freeze -> confirm wiring composes across a real
on-disk freeze/unlock boundary, and that the frozen objects survive a save/load
round-trip with a stable content hash (the basis of the Sec-3 re-verification).
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


@unittest.skipUnless(HAVE_STACK, "scientific stack not installed")
class TestFrozenObjectPersistence(unittest.TestCase):
    def test_correction_roundtrip_hash_stable(self):
        from analysis.correct_sites import SiteCorrection
        rng = np.random.default_rng(0)
        X = rng.normal(size=(120, 6))
        site = np.array(["MGH", "BWH"] * 60)
        corr = SiteCorrection(base_cfg()).fit(X, site)
        p = os.path.join(tempfile.mkdtemp(), "correction.json")
        h = corr.save(p)
        back = SiteCorrection.load(p, base_cfg())
        self.assertEqual(h, back.content_hash())
        np.testing.assert_allclose(corr.transform(X, site),
                                   back.transform(X, site))

    def test_assigner_roundtrip_hash_stable(self):
        from analysis.cluster import PhenotypeAssigner
        rng = np.random.default_rng(1)
        X = np.vstack([rng.normal(loc, 0.3, size=(40, 4)) for loc in (0, 8, 16)])
        asg = PhenotypeAssigner(base_cfg(), k=3).fit(X)
        p = os.path.join(tempfile.mkdtemp(), "assigner.pkl")
        h = asg.save(p)
        back = PhenotypeAssigner.load(p, base_cfg())
        self.assertEqual(h, back.content_hash())
        np.testing.assert_array_equal(asg.assign(X), back.assign(X))


@unittest.skipUnless(HAVE_STACK, "scientific stack not installed")
class TestDemoLifecycle(unittest.TestCase):
    def test_demo_runs_and_confirms(self):
        from demo.synthetic import run_demo
        work = tempfile.mkdtemp(prefix="heedb_demo_test_")
        s = run_demo(work, config_path=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"))
        self.assertTrue(s["ok"])
        self.assertEqual(s["k_selected"], 3)
        self.assertTrue(s["site_probe_gate_pass"])
        self.assertTrue(s["structure_is_real"])
        self.assertTrue(s["primary_confirmed"])
        self.assertEqual(s["status"], "supported")
        self.assertGreater(s["odds_ratio"], 1.0)
        # The freeze/unlock boundary produced a real manifest on disk.
        self.assertTrue(os.path.exists(os.path.join(work, "frozen", "manifest.json")))
        # Run-once lock now lives next to the frozen manifest (audit fix #4).
        self.assertTrue(os.path.exists(os.path.join(work, "frozen", "RUN_ONCE.lock")))


@unittest.skipUnless(HAVE_STACK, "scientific stack not installed")
class TestCliValidate(unittest.TestCase):
    def test_validate_command(self):
        import cli
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rc = cli.main(["--config", os.path.join(root, "config.yaml"), "validate"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
