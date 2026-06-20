"""MORGOTH-finding redundancy / novelty control (v3 Sec 9(4), 13.3).

Skipped without numpy/scikit-learn.
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


def _cfg(thr=0.80):
    c = base_cfg()
    c.setdefault("audits", {})["morgoth_redundancy"] = {"max_predictable_auc": thr}
    return c


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestRedundancyCheck(unittest.TestCase):
    def test_skipped_when_no_model_outputs(self):
        from analysis.morgoth_redundancy import redundancy_check
        r = redundancy_check([0, 1, 0, 1], None, _cfg())
        self.assertFalse(r["applicable"])
        self.assertEqual(r["novel_phenotypes"], [])

    def test_phenotype_that_is_a_model_finding_is_reducible(self):
        import numpy as np
        from analysis.morgoth_redundancy import redundancy_check
        rng = np.random.default_rng(0)
        # model_outputs has a column that (nearly) IS the phenotype label.
        n = 200
        labels = rng.integers(0, 2, size=n)
        finding = labels + rng.normal(0, 0.05, size=n)          # leaks the label
        noise = rng.normal(size=(n, 4))
        M = np.column_stack([finding, noise])
        r = redundancy_check(labels, M, _cfg())
        self.assertTrue(r["applicable"])
        # Both phenotypes should be predictable from the finding -> reducible.
        self.assertTrue(any(d["reducible"] for d in r["per_phenotype"].values()))
        self.assertGreater(max(d["predictable_auc"] for d in r["per_phenotype"].values()), 0.9)

    def test_phenotype_independent_of_outputs_is_novel(self):
        import numpy as np
        from analysis.morgoth_redundancy import redundancy_check
        rng = np.random.default_rng(1)
        n = 200
        labels = rng.integers(0, 2, size=n)
        M = rng.normal(size=(n, 5))                              # unrelated outputs
        r = redundancy_check(labels, M, _cfg())
        self.assertTrue(r["applicable"])
        # Not predictable -> not reducible -> all phenotypes novel.
        self.assertEqual(sorted(r["novel_phenotypes"]), [0, 1])
        self.assertEqual(r["n_reducible"], 0)


@unittest.skipUnless(HAVE_STACK, "numpy/sklearn not installed")
class TestAnnotateBar(unittest.TestCase):
    def test_reducible_phenotype_demoted(self):
        from analysis.morgoth_redundancy import annotate_phenotype_bar
        bar = {"decisions": {0: {"status": "provisional", "reasons": []},
                             1: {"status": "provisional", "reasons": []}},
               "admitted": [0, 1], "n_admitted": 2}
        redundancy = {"applicable": True, "threshold": 0.8,
                      "per_phenotype": {0: {"reducible": True}, 1: {"reducible": False}},
                      "novel_phenotypes": [1]}
        out = annotate_phenotype_bar(bar, redundancy)
        self.assertEqual(out["decisions"][0]["status"], "rejected")
        self.assertIn("morgoth_redundant", out["decisions"][0]["reasons"])
        self.assertEqual(out["decisions"][1]["status"], "provisional")
        self.assertEqual(out["admitted"], [1])

    def test_noop_when_not_applicable(self):
        from analysis.morgoth_redundancy import annotate_phenotype_bar
        bar = {"decisions": {0: {"status": "provisional", "reasons": []}},
               "admitted": [0], "n_admitted": 1}
        out = annotate_phenotype_bar(bar, {"applicable": False})
        self.assertEqual(out["n_admitted"], 1)
        self.assertIn("not applied", out["morgoth_redundancy"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
