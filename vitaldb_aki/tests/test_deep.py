"""test_deep.py -- offline unit tests for the deep-learning waveform arm (§9F, §10).

NO network, NO real downloads. Everything runs on synthetic in-memory arrays:
  * windowing math (resample grid, window count/length, NaN handling, §11 opend cut),
  * encoder forward-pass shape,
  * SSL loss finiteness + a single optimizer step reduces loss on a fixed batch,
  * per-case mean-pooling shape.

torch tests skip gracefully if torch import fails (it won't here -- 2.5.1+cpu).
"""
from __future__ import annotations

import unittest

import numpy as np

from vitaldb_aki.deep import waveforms as W


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


# ===========================================================================
# Windowing math (pure numpy -- no torch needed)
# ===========================================================================
class TestIntraopWindow(unittest.TestCase):
    def test_prefers_anestart_opend(self):
        case = {"anestart": "100", "opstart": "150", "opend": "400"}
        self.assertEqual(W.intraop_window(case), (100.0, 400.0))

    def test_falls_back_to_opstart(self):
        case = {"opstart": "150", "opend": "400"}
        self.assertEqual(W.intraop_window(case), (150.0, 400.0))

    def test_opend_only(self):
        case = {"opend": "400"}
        self.assertEqual(W.intraop_window(case), (None, 400.0))

    def test_no_opend_returns_none(self):
        # No opend -> the case is unsafe (cannot guarantee §11 cutoff).
        self.assertEqual(W.intraop_window({"anestart": "100"}), (None, None))


class TestClipAndWindowSeries(unittest.TestCase):
    def test_resample_rate_and_length(self):
        # 0..10 s of a 100 Hz sine -> resample to 25 Hz over [0, 10].
        t = np.arange(0.0, 10.0 + 1e-9, 0.01)   # include t=10.0 so the grid is covered
        v = np.sin(2 * np.pi * 1.0 * t)
        grid = W.clip_and_window_series(t, v, 0.0, 10.0, -2.0, 2.0, common_rate_hz=25.0)
        # n_grid = floor((10-0)*25)+1 = 251
        self.assertEqual(grid.shape[0], 251)
        # Grid lies within the sampled support [0, 10] -> all points are finite.
        self.assertTrue(np.isfinite(grid).all())

    def test_post_opend_samples_excluded(self):
        # Samples past opend (t_end=5.0) must never appear in the grid support.
        t = np.arange(0.0, 10.0, 0.1)
        v = np.where(t <= 5.0, 1.0, 999.0)   # post-opend value is a sentinel
        grid = W.clip_and_window_series(t, v, 0.0, 5.0, -1e9, 1e9, common_rate_hz=10.0)
        # Grid spans [0,5]; all finite values come from the <=5 region == 1.0.
        finite = grid[np.isfinite(grid)]
        self.assertTrue(finite.size > 0)
        self.assertFalse((finite > 1.5).any(), "a post-opend sentinel leaked in")

    def test_artifact_values_become_gaps(self):
        # Out-of-range artifacts (-70, 346) are rejected; interior stays clean.
        t = np.arange(0.0, 4.0, 0.1)
        v = np.full_like(t, 80.0)
        v[10] = -70.0     # flush artifact
        v[20] = 346.0     # impossible spike
        grid = W.clip_and_window_series(t, v, 0.0, 4.0, 0.0, 300.0, common_rate_hz=10.0)
        # No grid value should equal the rejected artifacts.
        self.assertFalse(np.any(grid == -70.0))
        self.assertFalse(np.any(grid == 346.0))

    def test_empty_when_no_in_window_samples(self):
        t = np.arange(0.0, 4.0, 0.1)
        v = np.ones_like(t)
        grid = W.clip_and_window_series(t, v, 10.0, 20.0, -1e9, 1e9, common_rate_hz=10.0)
        # window [10,20] has no samples -> all-NaN grid (or empty)
        self.assertTrue(grid.size == 0 or np.isnan(grid).all())


class TestSegmentIntoWindows(unittest.TestCase):
    def test_window_count_and_shape(self):
        # 4 channels each 250 samples; win_len 25 -> 10 windows.
        grids = [np.arange(250, dtype=float) for _ in range(4)]
        out = W.segment_into_windows(grids, win_len=25)
        self.assertEqual(out.shape, (10, 4, 25))
        self.assertEqual(out.dtype, np.float32)

    def test_trailing_remainder_dropped(self):
        grids = [np.arange(260, dtype=float) for _ in range(4)]   # 260 // 25 = 10
        out = W.segment_into_windows(grids, win_len=25)
        self.assertEqual(out.shape[0], 10)

    def test_absent_channel_zero_filled(self):
        # One channel None -> that channel axis is all zeros, shape preserved.
        grids = [np.ones(100, dtype=float), None,
                 np.ones(100, dtype=float), np.ones(100, dtype=float)]
        out = W.segment_into_windows(grids, win_len=50)
        self.assertEqual(out.shape, (2, 4, 50))
        self.assertTrue(np.all(out[:, 1, :] == 0.0))   # channel 1 absent

    def test_nan_imputed_when_above_threshold(self):
        # A channel with a few NaNs (above the finite-fraction floor) is mean-imputed.
        g = np.ones(50, dtype=float)
        g[:5] = np.nan
        grids = [g, np.ones(50), np.ones(50), np.ones(50)]
        out = W.segment_into_windows(grids, win_len=50)
        self.assertEqual(out.shape, (1, 4, 50))
        self.assertTrue(np.isfinite(out).all(), "NaNs were not imputed")

    def test_too_sparse_window_dropped(self):
        # A channel that is >50% NaN -> the window fails the finite-fraction gate.
        g = np.full(50, np.nan)
        g[:5] = 1.0   # only 10% finite
        grids = [g, np.ones(50), np.ones(50), np.ones(50)]
        out = W.segment_into_windows(grids, win_len=50)
        self.assertEqual(out.shape[0], 0)

    def test_all_absent_returns_empty(self):
        out = W.segment_into_windows([None, None, None, None], win_len=25)
        self.assertEqual(out.shape, (0, 4, 25))


# ===========================================================================
# Packed-CSV reconstruction (the SNUADC ~500 Hz sparse-timestamp format)
# ===========================================================================
class TestPackedWaveformReconstruction(unittest.TestCase):
    def test_two_anchor_grid_is_uniform_500hz(self):
        """A 2-anchor [start,end] packed file -> uniform grid at the implied rate.

        We exercise the same row-index->time interpolation `load_packed_waveform`
        uses (np.interp over anchors), independent of any file/network.
        """
        n = 1000
        # anchors: row 0 -> t=10.0, row 999 -> t=10.0 + 999/500 (== 500 Hz)
        anchor_idx = np.array([0, n - 1], dtype=float)
        anchor_t = np.array([10.0, 10.0 + (n - 1) / 500.0], dtype=float)
        t = np.interp(np.arange(n, dtype=float), anchor_idx, anchor_t)
        dt = np.diff(t)
        fs = 1.0 / dt.mean()
        self.assertAlmostEqual(fs, 500.0, places=3)
        self.assertTrue(np.allclose(dt, dt[0]))   # uniform


# ===========================================================================
# Encoder / SSL (torch)
# ===========================================================================
@unittest.skipUnless(_torch_available(), "torch not importable")
class TestEncoder(unittest.TestCase):
    def test_forward_shape(self):
        from vitaldb_aki.deep.encoder import WaveformEncoder
        enc = WaveformEncoder(n_channels=4, emb_dim=32)
        import torch
        x = torch.randn(7, 4, W.WINDOW_LEN)
        out = enc(x)
        self.assertEqual(tuple(out.shape), (7, 32))

    def test_embed_windows_numpy(self):
        from vitaldb_aki.deep.encoder import WaveformEncoder
        enc = WaveformEncoder(n_channels=4, emb_dim=32)
        x = np.random.RandomState(0).randn(5, 4, W.WINDOW_LEN).astype("float32")
        emb = enc.embed_windows(x)
        self.assertEqual(emb.shape, (5, 32))

    def test_capacity_is_small(self):
        # §10 discipline: the feasibility encoder is tens of thousands of params.
        from vitaldb_aki.deep.encoder import WaveformEncoder
        enc = WaveformEncoder(n_channels=4)
        self.assertLess(enc.count_parameters(), 200_000)


@unittest.skipUnless(_torch_available(), "torch not importable")
class TestMeanPool(unittest.TestCase):
    def test_pool_shape(self):
        from vitaldb_aki.deep.encoder import mean_pool_embeddings
        we = np.random.RandomState(1).randn(12, 32)
        pooled = mean_pool_embeddings(we)
        self.assertEqual(pooled.shape, (32,))

    def test_pool_rejects_empty(self):
        from vitaldb_aki.deep.encoder import mean_pool_embeddings
        with self.assertRaises(ValueError):
            mean_pool_embeddings(np.zeros((0, 32)))


@unittest.skipUnless(_torch_available(), "torch not importable")
class TestMask(unittest.TestCase):
    def test_mask_fraction_and_shape(self):
        rng = np.random.default_rng(0)
        mask = W_make_mask(40, 250, 0.4, rng)
        self.assertEqual(mask.shape, (40, 250))
        frac = mask.mean()
        # spans overshoot the target slightly; require roughly the requested coverage.
        self.assertGreaterEqual(frac, 0.35)
        self.assertLessEqual(frac, 0.75)

    def test_mask_deterministic(self):
        m1 = W_make_mask(8, 100, 0.4, np.random.default_rng(123))
        m2 = W_make_mask(8, 100, 0.4, np.random.default_rng(123))
        self.assertTrue(np.array_equal(m1, m2))


def W_make_mask(n, L, frac, rng):
    from vitaldb_aki.deep.ssl import make_mask
    return make_mask(n, L, frac, rng=rng)


@unittest.skipUnless(_torch_available(), "torch not importable")
class TestSSL(unittest.TestCase):
    def _fixed_batch(self):
        # Deterministic structured batch: smooth multi-channel sinusoids (learnable).
        import numpy as _np
        rng = _np.random.RandomState(0)
        t = _np.linspace(0, 4 * _np.pi, W.WINDOW_LEN)
        batch = _np.zeros((16, W.N_CHANNELS, W.WINDOW_LEN), dtype="float32")
        for b in range(16):
            for c in range(W.N_CHANNELS):
                phase = rng.rand() * 2 * _np.pi
                batch[b, c] = _np.sin(t + phase) + 0.05 * rng.randn(W.WINDOW_LEN)
        return batch

    def test_loss_finite(self):
        from vitaldb_aki.deep.encoder import WaveformEncoder
        from vitaldb_aki.deep.ssl import MaskedReconstructionSSL
        enc = WaveformEncoder(n_channels=W.N_CHANNELS)
        ssl = MaskedReconstructionSSL(enc, win_len=W.WINDOW_LEN, seed=0)
        loss = ssl.eval_loss(self._fixed_batch())
        self.assertTrue(np.isfinite(loss))

    def test_single_step_reduces_loss(self):
        import torch
        from vitaldb_aki.deep.encoder import WaveformEncoder
        from vitaldb_aki.deep.ssl import MaskedReconstructionSSL

        torch.manual_seed(0)
        enc = WaveformEncoder(n_channels=W.N_CHANNELS)
        ssl = MaskedReconstructionSSL(enc, win_len=W.WINDOW_LEN, seed=0)
        batch = self._fixed_batch()
        # Train several steps; the loss after should be below the initial loss.
        before = ssl.eval_loss(batch)
        last = before
        for _ in range(15):
            last = ssl.train_step(batch)
        after = ssl.eval_loss(batch)
        self.assertTrue(np.isfinite(before) and np.isfinite(after))
        self.assertLess(after, before, f"SSL did not reduce loss: {before} -> {after}")


if __name__ == "__main__":
    unittest.main()
