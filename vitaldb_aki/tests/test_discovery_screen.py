"""test_discovery_screen.py -- stdlib-only unit tests for the PURE helpers in
vitaldb_aki/analysis/discovery_screen.py.

These exercise the multiple-testing correction and the availability/coverage
logic WITHOUT numpy/pandas/sklearn and WITHOUT the real enriched matrix, so they
run fast and green in any environment (matching the repo's "heavy deps are lazy"
convention). The module must import with the stdlib only.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_discovery_screen -v
"""
from __future__ import annotations

import unittest

from vitaldb_aki.analysis import discovery_screen as ds


class TestBenjaminiHochberg(unittest.TestCase):
    """BH-FDR monotonicity + correctness on known p-values."""

    def test_known_values(self):
        # Classic worked example. p sorted: 0.01,0.02,0.03,0.04,0.05 (m=5).
        # raw q_i = p_i * m / i; then enforce monotone non-decreasing.
        p = [0.01, 0.02, 0.03, 0.04, 0.05]
        q = ds.benjamini_hochberg(p)
        # raw: 0.05, 0.05, 0.05, 0.05, 0.05 -> all 0.05 after monotone min.
        for qi in q:
            self.assertAlmostEqual(qi, 0.05, places=6)

    def test_monotonicity_in_p_rank_order(self):
        # q-values, when ordered by their p-value rank, must be non-decreasing.
        p = [0.001, 0.008, 0.039, 0.041, 0.9, 0.2, 0.5]
        q = ds.benjamini_hochberg(p)
        paired = sorted(zip(p, q), key=lambda t: t[0])
        qs = [t[1] for t in paired]
        for a, b in zip(qs, qs[1:]):
            self.assertLessEqual(a - 1e-12, b, f"q not monotone: {qs}")

    def test_q_never_exceeds_one(self):
        p = [0.6, 0.7, 0.8, 0.95]
        q = ds.benjamini_hochberg(p)
        for qi in q:
            self.assertLessEqual(qi, 1.0)
            self.assertGreaterEqual(qi, 0.0)

    def test_q_at_least_p(self):
        # BH q-value is always >= the raw p-value.
        p = [0.001, 0.01, 0.02, 0.03, 0.2]
        q = ds.benjamini_hochberg(p)
        for pi, qi in zip(p, q):
            self.assertGreaterEqual(qi + 1e-12, pi)

    def test_order_is_preserved(self):
        # Output q-values must align positionally with the input list.
        p = [0.5, 0.01, 0.2]
        q = ds.benjamini_hochberg(p)
        self.assertEqual(len(q), 3)
        # The smallest p (index 1) should get the smallest q.
        self.assertEqual(min(range(3), key=lambda i: q[i]), 1)

    def test_none_and_nan_pass_through(self):
        nan = float("nan")
        p = [0.01, None, 0.02, nan, 0.03]
        q = ds.benjamini_hochberg(p)
        self.assertIsNone(q[1])
        self.assertIsNone(q[3])
        # m = 3 tested values; raw 0.01*3/1, 0.02*3/2, 0.03*3/3 = 0.03,0.03,0.03.
        for idx in (0, 2, 4):
            self.assertAlmostEqual(q[idx], 0.03, places=6)

    def test_empty(self):
        self.assertEqual(ds.benjamini_hochberg([]), [])

    def test_single_pvalue(self):
        q = ds.benjamini_hochberg([0.04])
        self.assertAlmostEqual(q[0], 0.04, places=6)


class TestAvailabilityHelpers(unittest.TestCase):
    """availability_subset_mask + coverage on a tiny synthetic list-of-dicts."""

    def setUp(self):
        # 5 rows; flag `vent_available`, outcome `composite`.
        # row0: avail, outcome present(1)      -> keep
        # row1: avail, outcome present(0)      -> keep (0 is a labelable event-free)
        # row2: avail, outcome missing ("")    -> drop (unlabelable)
        # row3: NOT avail, outcome present     -> drop (family unavailable)
        # row4: avail(1.0 float-string), present -> keep
        self.rows = [
            {"vent_available": 1, "composite": 1},
            {"vent_available": "1", "composite": "0"},
            {"vent_available": 1, "composite": ""},
            {"vent_available": 0, "composite": 1},
            {"vent_available": "1.0", "composite": "1"},
        ]

    def test_subset_mask(self):
        mask = ds.availability_subset_mask(self.rows, "vent_available", "composite")
        self.assertEqual(mask, [True, True, False, False, True])

    def test_subset_mask_drops_nan_outcome(self):
        rows = [{"f_available": 1, "y": "nan"}, {"f_available": 1, "y": "None"},
                {"f_available": 1, "y": 0}]
        mask = ds.availability_subset_mask(rows, "f_available", "y")
        self.assertEqual(mask, [False, False, True])

    def test_coverage(self):
        # 4 of 5 rows have flag == 1.
        cov = ds.coverage(self.rows, "vent_available")
        self.assertAlmostEqual(cov, 4 / 5)

    def test_coverage_empty_cohort(self):
        self.assertEqual(ds.coverage([], "vent_available"), 0.0)

    def test_coverage_cutoff_behavior(self):
        # Build a frame where one family is widely available (>=80%) and one is not.
        rows = [{"wide_available": 1, "sparse_available": 0} for _ in range(9)]
        rows.append({"wide_available": 0, "sparse_available": 1})  # 10 rows total
        wide = ds.coverage(rows, "wide_available")    # 9/10 = 0.9
        sparse = ds.coverage(rows, "sparse_available")  # 1/10 = 0.1
        self.assertGreaterEqual(wide, ds.COVERAGE_CUTOFF)
        self.assertLess(sparse, ds.COVERAGE_CUTOFF)

    def test_is_one_leniency(self):
        self.assertTrue(ds._is_one(1))
        self.assertTrue(ds._is_one("1"))
        self.assertTrue(ds._is_one("1.0"))
        self.assertTrue(ds._is_one(True))
        self.assertFalse(ds._is_one(0))
        self.assertFalse(ds._is_one(""))
        self.assertFalse(ds._is_one("nan"))
        self.assertFalse(ds._is_one(None))
        self.assertFalse(ds._is_one("false"))


class TestCfgResolution(unittest.TestCase):
    """cache_dir resolution handles both nested and flat cfg shapes."""

    def test_nested_cfg(self):
        self.assertEqual(ds._cache_dir({"data": {"cache_dir": "/x"}}), "/x")

    def test_flat_cfg(self):
        self.assertEqual(ds._cache_dir({"cache_dir": "/y"}), "/y")

    def test_missing_cfg_raises(self):
        with self.assertRaises(KeyError):
            ds._cache_dir({"foo": "bar"})

    def test_seed_default(self):
        self.assertEqual(ds._seed({"seed": 7}), 7)
        self.assertEqual(ds._seed({}), 42)


if __name__ == "__main__":
    unittest.main(verbosity=2)
