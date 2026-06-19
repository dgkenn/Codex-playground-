"""test_embed.py -- unit tests for pipeline.embed (no torch or model required).

These tests exercise:
  - importability of the module
  - pure-Python helpers (pool_embeddings, should_keep_epoch_subset)
  - FrozenEmbedder error paths that are reachable without torch/braindecode

Tests that genuinely need torch or numpy are guarded with skipUnless so the
suite stays green in minimal environments.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

# Mirror the sys.path convention used by test_integrity.py so the project root
# is always on the path regardless of how the test runner is invoked.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline.embed as embed_mod  # noqa: E402  (after sys.path fixup)
from pipeline.embed import (  # noqa: E402
    FrozenEmbedder,
    pool_embeddings,
    should_keep_epoch_subset,
)

# ---------------------------------------------------------------------------
# Availability flags
# ---------------------------------------------------------------------------
HAVE_NUMPY = importlib.util.find_spec("numpy") is not None
HAVE_TORCH = importlib.util.find_spec("torch") is not None


def _minimal_cfg():
    """Return the smallest config dict that FrozenEmbedder needs."""
    return {
        "model": {
            "name": "CBraMod",
            "repo_id": "weighting666/CBraMod",
            "checkpoint_file": "pretrained_weights.pth",
            "revision": "main",
            "checkpoint_sha256": "TO-CONFIRM",
            "expected_sfreq_hz": 200,
            "patch_seconds": 1.0,
            "channels_10_20": [
                "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
                "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
                "Fz", "Cz", "Pz",
            ],
            "window_seconds": 30,
        }
    }


# ---------------------------------------------------------------------------
# 1. Import-level smoke test
# ---------------------------------------------------------------------------
class TestModuleImport(unittest.TestCase):
    """The module must import cleanly with no heavy dependencies installed."""

    def test_module_imported(self):
        """pipeline.embed should be importable without torch/braindecode."""
        self.assertIsNotNone(embed_mod)

    def test_public_api_present(self):
        """Expected public names must exist on the module."""
        for name in ("FrozenEmbedder", "pool_embeddings", "should_keep_epoch_subset"):
            self.assertTrue(
                hasattr(embed_mod, name),
                f"pipeline.embed is missing expected name: {name!r}",
            )


# ---------------------------------------------------------------------------
# 2. pool_embeddings (pure NumPy -- guard with skipUnless)
# ---------------------------------------------------------------------------
class TestPoolEmbeddings(unittest.TestCase):

    @unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
    def test_mean_only(self):
        import numpy as np
        we = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = pool_embeddings(we, ["mean"])
        np.testing.assert_allclose(result, [2.0, 3.0])

    @unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
    def test_mean_std_concatenated(self):
        import numpy as np
        we = np.array([[0.0, 0.0], [2.0, 2.0]])
        result = pool_embeddings(we, ["mean", "std"])
        # mean = [1, 1], std = [1, 1] -> [1, 1, 1, 1]
        self.assertEqual(result.shape, (4,))
        np.testing.assert_allclose(result, [1.0, 1.0, 1.0, 1.0])

    @unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
    def test_empty_raises(self):
        import numpy as np
        with self.assertRaises(ValueError):
            pool_embeddings(np.zeros((0, 4)), ["mean"])

    @unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
    def test_1d_input_raises(self):
        import numpy as np
        with self.assertRaises(ValueError):
            pool_embeddings(np.array([1.0, 2.0, 3.0]), ["mean"])

    @unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
    def test_unknown_op_raises(self):
        import numpy as np
        with self.assertRaises(ValueError):
            pool_embeddings(np.ones((3, 4)), ["median"])

    @unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
    def test_output_dtype_float32(self):
        import numpy as np
        we = np.ones((2, 3), dtype="float64")
        result = pool_embeddings(we, ["mean"])
        self.assertEqual(result.dtype, np.float32)


# ---------------------------------------------------------------------------
# 3. should_keep_epoch_subset
# ---------------------------------------------------------------------------
class TestShouldKeepEpochSubset(unittest.TestCase):

    def test_fraction_zero_always_false(self):
        self.assertFalse(should_keep_epoch_subset("any_recording", 0.0))

    def test_fraction_one_always_true(self):
        self.assertTrue(should_keep_epoch_subset("any_recording", 1.0))

    def test_deterministic(self):
        """Same recording_id + fraction must always give the same answer."""
        result1 = should_keep_epoch_subset("rec_42", 0.5)
        result2 = should_keep_epoch_subset("rec_42", 0.5)
        self.assertEqual(result1, result2)

    def test_different_ids_differ(self):
        """Two recordings should not trivially both land on the same side."""
        results = {should_keep_epoch_subset(f"rec_{i}", 0.5) for i in range(20)}
        # With 20 samples at p=0.5 both True and False should appear.
        self.assertIn(True, results)
        self.assertIn(False, results)

    def test_approximate_rate(self):
        """Empirical keep-rate should be close to the requested fraction."""
        fraction = 0.2
        n = 2000
        kept = sum(should_keep_epoch_subset(f"rec_{i}", fraction) for i in range(n))
        # Allow generous +-50% relative tolerance on the empirical rate.
        self.assertTrue(
            0.1 <= kept / n <= 0.3,
            f"empirical rate {kept}/{n} is far from {fraction}",
        )


# ---------------------------------------------------------------------------
# 4. FrozenEmbedder.load() raises ImportError when torch is NOT installed
# ---------------------------------------------------------------------------
class TestLoadRaisesImportErrorWithoutTorch(unittest.TestCase):
    """This test is meaningful only when torch is absent; skip otherwise."""

    @unittest.skipIf(HAVE_TORCH, "torch IS installed -- skipping no-torch path")
    def test_load_raises_import_error_without_torch(self):
        """load() must raise ImportError with a pip-install hint when torch is missing."""
        embedder = FrozenEmbedder(_minimal_cfg())
        with self.assertRaises(ImportError) as ctx:
            embedder.load()
        msg = str(ctx.exception).lower()
        # The message should mention pip install so the user knows how to fix it.
        self.assertIn("pip install", msg, (
            "ImportError message should include a pip install hint. "
            f"Got: {ctx.exception}"
        ))

    @unittest.skipIf(HAVE_TORCH, "torch IS installed -- skipping no-torch path")
    def test_load_error_mentions_torch(self):
        """ImportError message should name 'torch' so users know what is missing."""
        embedder = FrozenEmbedder(_minimal_cfg())
        with self.assertRaises(ImportError) as ctx:
            embedder.load()
        self.assertIn("torch", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# 5. embed_windows() raises RuntimeError before load() -- testable without torch
# ---------------------------------------------------------------------------
class TestEmbedWindowsBeforeLoad(unittest.TestCase):
    """The self.model is None check must fire BEFORE any torch import."""

    def _make_windows(self):
        """Return a small windows array; use numpy if available, else a list."""
        if HAVE_NUMPY:
            import numpy as np
            return np.zeros((2, 19, 6000), dtype="float32")
        # Provide a nested list so we can still exercise the guard path even
        # without numpy (the RuntimeError should trigger before numpy is needed).
        return [[[0.0] * 6000] * 19] * 2

    def test_embed_windows_before_load_raises_runtime_error(self):
        """embed_windows() must raise RuntimeError when called before load()."""
        embedder = FrozenEmbedder(_minimal_cfg())
        # model is None -- the guard should fire regardless of torch presence.
        with self.assertRaises(RuntimeError) as ctx:
            embedder.embed_windows(self._make_windows())
        self.assertIn("load()", str(ctx.exception), (
            "RuntimeError message should mention load(). "
            f"Got: {ctx.exception}"
        ))

    def test_embed_windows_model_none_check_comes_first(self):
        """The model-is-None guard must precede any torch import in embed_windows.

        We verify this by confirming that the RuntimeError is raised even in
        environments where torch is not installed.  If the guard ran AFTER the
        torch import the test would raise ImportError instead.
        """
        embedder = FrozenEmbedder(_minimal_cfg())
        # Regardless of torch availability, RuntimeError (not ImportError) expected.
        try:
            embedder.embed_windows(self._make_windows())
            self.fail("Expected RuntimeError was not raised")
        except RuntimeError:
            pass  # correct -- guard fired before torch was touched
        except ImportError:
            self.fail(
                "ImportError raised instead of RuntimeError: "
                "the self.model is None guard must come BEFORE `import torch` "
                "in embed_windows()."
            )


# ---------------------------------------------------------------------------
# 6. FrozenEmbedder state after construction (no torch needed)
# ---------------------------------------------------------------------------
class TestFrozenEmbedderInit(unittest.TestCase):

    def test_model_is_none_initially(self):
        embedder = FrozenEmbedder(_minimal_cfg())
        self.assertIsNone(embedder.model)

    def test_verified_false_initially(self):
        embedder = FrozenEmbedder(_minimal_cfg())
        self.assertFalse(embedder._verified)

    def test_checkpoint_path_none_initially(self):
        embedder = FrozenEmbedder(_minimal_cfg())
        self.assertIsNone(embedder.checkpoint_path)

    def test_cfg_stored(self):
        cfg = _minimal_cfg()
        embedder = FrozenEmbedder(cfg)
        self.assertIs(embedder.cfg, cfg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
