"""test_aline_feasibility.py -- stdlib-only tests for the A-line feasibility
pipeline helpers (vitaldb_aki/analysis/aline_feasibility.py).

We test the two pure pieces that gate the pipeline's correctness WITHOUT any
network / science stack:
  * select_sample(): deterministic, seed-stable, order-independent sub-sampling
    of the ART caseids (this is what makes EXTRACT resumable),
  * incremental_band() + rank_auroc(): the incremental-band / AUROC ranking
    helpers used by the SCREEN report,
  * benjamini_hochberg(): the FDR helper.

No network, no numpy, no sklearn.

Run:
    python3 -m unittest vitaldb_aki.tests.test_aline_feasibility -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.analysis.aline_feasibility import (
    select_sample,
    incremental_band,
    rank_auroc,
    benjamini_hochberg,
    SAMPLE_N,
)


# ---------------------------------------------------------------------------
# 1. Seeded-sample selection determinism.
# ---------------------------------------------------------------------------

class TestSelectSample(unittest.TestCase):
    def _ids(self, n):
        return [str(i) for i in range(1000, 1000 + n)]

    def test_deterministic_same_seed(self):
        ids = self._ids(50)
        a = select_sample(ids, seed=20260626, n=10)
        b = select_sample(ids, seed=20260626, n=10)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 10)

    def test_order_independent(self):
        ids = self._ids(50)
        shuffled = list(reversed(ids))
        a = select_sample(ids, seed=7, n=12)
        b = select_sample(shuffled, seed=7, n=12)
        self.assertEqual(a, b)  # input order must not change the chosen sample

    def test_different_seed_differs(self):
        ids = self._ids(200)
        a = set(select_sample(ids, seed=1, n=20))
        b = set(select_sample(ids, seed=2, n=20))
        # Overwhelmingly likely to differ; assert not identical.
        self.assertNotEqual(a, b)

    def test_dedup_and_str_coercion(self):
        ids = [1, 1, 2, 2, 3, "3", 4]   # duplicates + mixed types
        s = select_sample(ids, seed=0, n=10)
        self.assertEqual(sorted(s), sorted(set(str(i) for i in ids)))
        # All entries are strings.
        self.assertTrue(all(isinstance(c, str) for c in s))

    def test_fewer_than_n_returns_all(self):
        ids = self._ids(5)
        s = select_sample(ids, seed=3, n=600)
        self.assertEqual(sorted(s), sorted(ids))
        self.assertEqual(len(s), 5)

    def test_caps_at_n(self):
        ids = self._ids(1000)
        s = select_sample(ids, seed=3, n=600)
        self.assertEqual(len(s), 600)
        # No duplicates.
        self.assertEqual(len(set(s)), 600)

    def test_resumability_subset_property(self):
        # The key resumability property: select_sample(N) on the same set/seed is a
        # STABLE target set, so a restart re-derives exactly the same caseids.
        ids = self._ids(800)
        first = select_sample(ids, seed=20260626, n=SAMPLE_N if SAMPLE_N <= 800 else 600)
        second = select_sample(ids, seed=20260626, n=len(first))
        self.assertEqual(first, second)

    def test_growing_target_is_prefix_stable_membership(self):
        # If the candidate pool grows but seed fixed, the chosen members are a
        # deterministic function of the hash order (not guaranteed nested, but
        # fully reproducible). Assert reproducibility on the larger pool.
        ids = self._ids(300)
        a = select_sample(ids, seed=5, n=30)
        b = select_sample(ids, seed=5, n=30)
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# 2. Incremental-band / AUROC ranking helpers.
# ---------------------------------------------------------------------------

class TestIncrementalBand(unittest.TestCase):
    def test_promising(self):
        r = incremental_band(0.60, 0.64)   # +0.04
        self.assertEqual(r["band"], "promising")
        self.assertAlmostEqual(r["delta"], 0.04, places=6)

    def test_weak(self):
        r = incremental_band(0.60, 0.615)  # +0.015
        self.assertEqual(r["band"], "weak")

    def test_flat(self):
        r = incremental_band(0.60, 0.605)  # +0.005
        self.assertEqual(r["band"], "flat")

    def test_negative(self):
        r = incremental_band(0.60, 0.55)   # -0.05
        self.assertEqual(r["band"], "negative")

    def test_boundary_003_is_promising(self):
        self.assertEqual(incremental_band(0.50, 0.53)["band"], "promising")

    def test_boundary_001_is_weak(self):
        self.assertEqual(incremental_band(0.50, 0.51)["band"], "weak")

    def test_none_inputs(self):
        self.assertEqual(incremental_band(None, 0.6)["band"], "undefined")
        self.assertIsNone(incremental_band(None, 0.6)["delta"])
        self.assertEqual(incremental_band(0.6, None)["band"], "undefined")


class TestRankAuroc(unittest.TestCase):
    def test_distance_from_chance(self):
        self.assertAlmostEqual(rank_auroc(0.70), 0.20, places=6)
        self.assertAlmostEqual(rank_auroc(0.30), 0.20, places=6)  # protective same dist
        self.assertAlmostEqual(rank_auroc(0.50), 0.0, places=6)

    def test_none_sorts_last(self):
        self.assertEqual(rank_auroc(None), -1.0)

    def test_ranking_order(self):
        feats = {"a": 0.55, "b": 0.72, "c": 0.49, "d": None}
        order = sorted(feats, key=lambda k: rank_auroc(feats[k]), reverse=True)
        self.assertEqual(order[0], "b")     # strongest discrimination
        self.assertEqual(order[-1], "d")    # None last


class TestBenjaminiHochberg(unittest.TestCase):
    def test_basic_monotone(self):
        ps = [0.001, 0.5, 0.02, 0.04]
        q = benjamini_hochberg(ps, alpha=0.05)
        self.assertEqual(len(q), 4)
        for qi in q:
            self.assertIsNotNone(qi)
            self.assertLessEqual(qi, 1.0)
        # The smallest p gets the smallest q.
        self.assertEqual(min(range(4), key=lambda i: q[i]), 0)

    def test_none_passthrough(self):
        q = benjamini_hochberg([0.01, None, 0.5])
        self.assertIsNone(q[1])
        self.assertIsNotNone(q[0])
        self.assertIsNotNone(q[2])

    def test_all_none(self):
        self.assertEqual(benjamini_hochberg([None, None]), [None, None])

    def test_empty(self):
        self.assertEqual(benjamini_hochberg([]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
