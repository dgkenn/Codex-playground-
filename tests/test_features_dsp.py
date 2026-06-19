"""DSP feature tests -- require numpy and scipy.

Exercises compute_features() for the three families that were previously
NaN placeholders: wPLI, entropy, and microstates.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np
    import scipy  # noqa: F401
    HAVE_STACK = True
except ImportError:
    HAVE_STACK = False

from tests.test_integrity import base_cfg
from pipeline.features import compute_features, feature_schema


def _make_windows(cfg, sfreq=200, n_windows=4, n_samples=400, seed=42):
    """Synthetic EEG windows with a known 10 Hz alpha oscillation plus white noise."""
    rng = np.random.default_rng(seed)
    chans = cfg["model"]["channels_10_20"]
    nch = len(chans)
    t = np.arange(n_samples) / sfreq
    # Alpha oscillation (10 Hz) + broadband noise
    osc = np.sin(2 * np.pi * 10 * t)  # (n_samples,)
    windows = np.zeros((n_windows, nch, n_samples))
    for w in range(n_windows):
        for c in range(nch):
            noise = rng.standard_normal(n_samples) * 0.5
            windows[w, c] = osc + noise
    return windows


@unittest.skipUnless(HAVE_STACK, "numpy/scipy not available")
class TestComputeFeaturesWPLI(unittest.TestCase):
    def setUp(self):
        self.cfg = base_cfg()
        self.sfreq = 200.0
        self.windows = _make_windows(self.cfg, sfreq=self.sfreq)

    def test_returns_exact_schema_keys(self):
        result = compute_features(self.windows, self.sfreq, self.cfg)
        expected = set(feature_schema(self.cfg))
        self.assertEqual(set(result.keys()), expected,
                         msg=f"Extra: {set(result)-expected}; Missing: {expected-set(result)}")

    def test_wpli_not_nan(self):
        result = compute_features(self.windows, self.sfreq, self.cfg)
        bands = self.cfg["features"]["bands"]
        for band in bands:
            key = f"wpli_{band}_globalmean"
            self.assertFalse(
                result[key] != result[key],  # NaN check: NaN != NaN
                msg=f"{key} is NaN"
            )

    def test_wpli_in_range(self):
        result = compute_features(self.windows, self.sfreq, self.cfg)
        bands = self.cfg["features"]["bands"]
        for band in bands:
            key = f"wpli_{band}_globalmean"
            val = result[key]
            self.assertGreaterEqual(val, 0.0, msg=f"{key}={val} < 0")
            self.assertLessEqual(val, 1.0, msg=f"{key}={val} > 1")


@unittest.skipUnless(HAVE_STACK, "numpy/scipy not available")
class TestComputeFeaturesEntropy(unittest.TestCase):
    def setUp(self):
        self.cfg = base_cfg()  # has entropy: ["sample_entropy"]
        self.sfreq = 200.0
        self.windows = _make_windows(self.cfg, sfreq=self.sfreq)

    def test_sample_entropy_not_nan(self):
        result = compute_features(self.windows, self.sfreq, self.cfg)
        chans = self.cfg["model"]["channels_10_20"]
        for ch in chans:
            key = f"sample_entropy_{ch}"
            self.assertIn(key, result)
            self.assertFalse(result[key] != result[key], msg=f"{key} is NaN")

    def test_permutation_entropy_in_range(self):
        """Test permutation entropy using a config variant that adds it."""
        import copy
        cfg2 = copy.deepcopy(self.cfg)
        cfg2["features"]["entropy"] = ["sample_entropy", "permutation_entropy"]
        result = compute_features(self.windows, self.sfreq, cfg2)
        chans = cfg2["model"]["channels_10_20"]
        for ch in chans:
            key = f"permutation_entropy_{ch}"
            self.assertIn(key, result)
            val = result[key]
            self.assertFalse(val != val, msg=f"{key} is NaN")
            self.assertGreaterEqual(val, 0.0, msg=f"{key}={val} < 0")
            self.assertLessEqual(val, 1.0, msg=f"{key}={val} > 1")

    def test_permutation_entropy_keys_in_schema(self):
        """Keys for permutation_entropy must exactly match feature_schema."""
        import copy
        cfg2 = copy.deepcopy(self.cfg)
        cfg2["features"]["entropy"] = ["sample_entropy", "permutation_entropy"]
        result = compute_features(self.windows, self.sfreq, cfg2)
        expected = set(feature_schema(cfg2))
        self.assertEqual(set(result.keys()), expected)


@unittest.skipUnless(HAVE_STACK, "numpy/scipy not available")
class TestComputeFeaturesMicrostates(unittest.TestCase):
    def setUp(self):
        self.cfg = base_cfg()  # microstates.n_states = 4
        self.sfreq = 200.0
        self.windows = _make_windows(self.cfg, sfreq=self.sfreq)

    def test_microstate_coverage_not_nan(self):
        result = compute_features(self.windows, self.sfreq, self.cfg)
        n_states = self.cfg["features"]["microstates"]["n_states"]
        for s in range(n_states):
            key = f"microstate{s}_coverage"
            self.assertIn(key, result)
            self.assertFalse(result[key] != result[key], msg=f"{key} is NaN")

    def test_microstate_meandur_not_nan(self):
        result = compute_features(self.windows, self.sfreq, self.cfg)
        n_states = self.cfg["features"]["microstates"]["n_states"]
        for s in range(n_states):
            key = f"microstate{s}_meandur"
            self.assertIn(key, result)
            self.assertFalse(result[key] != result[key], msg=f"{key} is NaN")

    def test_coverages_in_range(self):
        result = compute_features(self.windows, self.sfreq, self.cfg)
        n_states = self.cfg["features"]["microstates"]["n_states"]
        for s in range(n_states):
            val = result[f"microstate{s}_coverage"]
            self.assertGreaterEqual(val, 0.0, msg=f"microstate{s}_coverage={val} < 0")
            self.assertLessEqual(val, 1.0, msg=f"microstate{s}_coverage={val} > 1")

    def test_coverages_sum_leq_one(self):
        result = compute_features(self.windows, self.sfreq, self.cfg)
        n_states = self.cfg["features"]["microstates"]["n_states"]
        total = sum(result[f"microstate{s}_coverage"] for s in range(n_states))
        self.assertLessEqual(total, 1.0 + 1e-9,
                             msg=f"Coverage sum {total} > 1")

    def test_meandur_nonnegative(self):
        result = compute_features(self.windows, self.sfreq, self.cfg)
        n_states = self.cfg["features"]["microstates"]["n_states"]
        for s in range(n_states):
            val = result[f"microstate{s}_meandur"]
            self.assertGreaterEqual(val, 0.0, msg=f"microstate{s}_meandur={val} < 0")


@unittest.skipUnless(HAVE_STACK, "numpy/scipy not available")
class TestSchemaAlignmentEnd2End(unittest.TestCase):
    """Cross-cutting: the returned dict keys must EXACTLY match feature_schema."""

    def test_exact_key_match_base_cfg(self):
        cfg = base_cfg()
        windows = _make_windows(cfg, sfreq=200.0)
        result = compute_features(windows, 200.0, cfg)
        expected = set(feature_schema(cfg))
        self.assertEqual(set(result.keys()), expected)

    def test_no_nan_in_wpli_entropy_microstates(self):
        cfg = base_cfg()
        windows = _make_windows(cfg, sfreq=200.0)
        result = compute_features(windows, 200.0, cfg)
        chans = cfg["model"]["channels_10_20"]
        bands = cfg["features"]["bands"]
        # wPLI
        for band in bands:
            key = f"wpli_{band}_globalmean"
            self.assertFalse(result[key] != result[key], msg=f"{key} is NaN")
        # entropy
        for ent in cfg["features"].get("entropy", []):
            for ch in chans:
                key = f"{ent}_{ch}"
                self.assertFalse(result[key] != result[key], msg=f"{key} is NaN")
        # microstates
        n_states = cfg["features"]["microstates"]["n_states"]
        for s in range(n_states):
            for suffix in ("coverage", "meandur"):
                key = f"microstate{s}_{suffix}"
                self.assertFalse(result[key] != result[key], msg=f"{key} is NaN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
