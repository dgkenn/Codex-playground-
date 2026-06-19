"""Analysis-layer tests -- skipped automatically when numpy/sklearn are absent.

These check the *behaviour* of the disk-light analysis stages on synthetic data:
that site correction reduces site predictability (the gate), that consensus PAC
recovers a planted k, that the negative-control battery flags real-vs-null, and
that the frozen assigner produces a stable content hash. They run in CI only
when the scientific stack is installed.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np  # noqa: F401
    import sklearn  # noqa: F401
    HAVE_STACK = True
except ImportError:
    HAVE_STACK = False

from tests.test_integrity import base_cfg


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestSiteCorrectionGate(unittest.TestCase):
    def test_correction_reduces_site_predictability(self):
        import numpy as np
        from analysis.correct_sites import SiteCorrection
        from analysis.site_probe import probe_site

        rng = np.random.default_rng(0)
        n, d = 600, 8
        # Two sites with a strong additive offset = recoverable site identity.
        site = np.array(["MGH"] * (n // 2) + ["BWH"] * (n // 2))
        signal = rng.normal(size=(n, d))
        offset = np.where(site[:, None] == "MGH", 5.0, -5.0)
        X = signal + offset

        cfg = base_cfg()
        before = probe_site(X, site, cfg)["auc"]
        corr = SiteCorrection(cfg).fit(X, site)
        Xc = corr.transform(X, site)
        after = probe_site(Xc, site, cfg)["auc"]
        self.assertGreater(before, 0.9)        # site was recoverable
        self.assertLess(after, before)         # correction reduced it
        self.assertLess(after, 0.7)            # near chance after correction

    def test_correction_hash_is_stable(self):
        import numpy as np
        from analysis.correct_sites import SiteCorrection
        rng = np.random.default_rng(1)
        X = rng.normal(size=(100, 4))
        site = np.array(["A", "B"] * 50)
        h1 = SiteCorrection(base_cfg()).fit(X, site).content_hash()
        h2 = SiteCorrection(base_cfg()).fit(X, site).content_hash()
        self.assertEqual(h1, h2)


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestConsensusClustering(unittest.TestCase):
    def test_pac_recovers_planted_k(self):
        import numpy as np
        from analysis.cluster import consensus_pac, select_k

        rng = np.random.default_rng(2)
        # Three well-separated blobs.
        centers = np.array([[0, 0], [10, 10], [0, 10]])
        X = np.vstack([c + rng.normal(scale=0.5, size=(80, 2)) for c in centers])
        cfg = base_cfg()
        cfg["clustering"] = {
            "algorithm": "gmm", "k_candidates": [2, 3, 4, 5],
            "consensus": {"n_resamples": 25, "subsample_fraction": 0.8,
                          "pac_low": 0.1, "pac_high": 0.9},
        }
        pac = consensus_pac(X, cfg)
        self.assertEqual(select_k(pac), 3)


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestAssignerFreeze(unittest.TestCase):
    def test_assigner_hash_and_assign(self):
        import numpy as np
        from analysis.cluster import PhenotypeAssigner

        rng = np.random.default_rng(3)
        X = np.vstack([rng.normal(loc, scale=0.3, size=(50, 3))
                       for loc in (0, 8)])
        a = PhenotypeAssigner(base_cfg(), k=2).fit(X)
        self.assertEqual(len(a.content_hash()), 64)
        self.assertEqual(len(set(a.assign(X).tolist())), 2)


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestNegativeControls(unittest.TestCase):
    def test_surrogate_structure_collapse(self):
        from analysis.audits import surrogate_structure_collapse
        # Real structure clearly beats surrogate null -> real.
        res = surrogate_structure_collapse(0.9, [0.1, 0.2, 0.15, 0.18])
        self.assertTrue(res["structure_is_real"])
        # Real no better than null -> artifact.
        res2 = surrogate_structure_collapse(0.15, [0.1, 0.2, 0.15, 0.18, 0.3])
        self.assertFalse(res2["structure_is_real"])


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestPooling(unittest.TestCase):
    def test_pool_mean_std(self):
        import numpy as np
        from pipeline.embed import pool_embeddings
        we = np.arange(12, dtype="float64").reshape(3, 4)
        pooled = pool_embeddings(we, ["mean", "std"])
        self.assertEqual(pooled.shape[0], 8)  # mean(4) + std(4)
        np.testing.assert_allclose(pooled[:4], we.mean(axis=0), rtol=1e-5)


if __name__ == "__main__":
    unittest.main(verbosity=2)


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestLeaveOneSiteOutDegenerate(unittest.TestCase):
    def test_single_site_does_not_crash(self):
        import numpy as np
        from analysis.audits import leave_one_site_out
        from analysis.cluster import PhenotypeAssigner
        rng = np.random.default_rng(0)
        X = rng.normal(size=(20, 6))
        sites = np.array(["S0001"] * 20)            # only one site
        cfg = base_cfg()
        r = leave_one_site_out(X, sites, lambda: PhenotypeAssigner(cfg, k=2), cfg)
        self.assertEqual(r["per_site_ari"], {})
        self.assertNotEqual(r["min_ari"], r["min_ari"])  # NaN, not a crash
