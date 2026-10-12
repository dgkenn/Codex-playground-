"""Tests for incremental-value statistics (Sec 12) -- needs numpy/scipy/sklearn."""
from __future__ import annotations
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import numpy as np
    from sklearn.metrics import roc_auc_score
    from vitaldb_aki.models.metrics import delong_roc_test, idi_nri, bootstrap_ci
    HAVE = True
except Exception:
    HAVE = False


@unittest.skipUnless(HAVE, "needs scientific stack")
class TestDeLong(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.n = 800
        self.y = rng.integers(0, 2, self.n)
        # a is informative, b is a bit better
        self.a = np.clip(self.y * 0.4 + rng.normal(0, 1, self.n), -3, 3)
        self.b = np.clip(self.y * 0.8 + rng.normal(0, 1, self.n), -3, 3)

    def test_auc_matches_sklearn(self):
        d = delong_roc_test(self.y, self.a, self.b)
        self.assertAlmostEqual(d["auc_a"], roc_auc_score(self.y, self.a), places=6)
        self.assertAlmostEqual(d["auc_b"], roc_auc_score(self.y, self.b), places=6)

    def test_better_model_positive_delta_significant(self):
        d = delong_roc_test(self.y, self.a, self.b)
        self.assertGreater(d["delta"], 0)
        self.assertLess(d["p_value"], 0.05)

    def test_identical_models_zero_delta(self):
        d = delong_roc_test(self.y, self.a, self.a)
        self.assertAlmostEqual(d["delta"], 0.0, places=10)

    def test_idi_nri_positive_for_better(self):
        # convert to probabilities via logistic
        pa = 1 / (1 + np.exp(-self.a)); pb = 1 / (1 + np.exp(-self.b))
        r = idi_nri(self.y, pa, pb)
        self.assertGreater(r["idi"], 0)

    def test_bootstrap_ci_brackets_delta(self):
        g = np.arange(self.n)  # each sample its own patient
        lo, hi = bootstrap_ci(lambda yy, a, b: delong_roc_test(yy, a, b)["delta"],
                              self.y, self.a, self.b, g, n_iter=200, seed=0)
        d = delong_roc_test(self.y, self.a, self.b)["delta"]
        self.assertLessEqual(lo, d)
        self.assertGreaterEqual(hi, d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
