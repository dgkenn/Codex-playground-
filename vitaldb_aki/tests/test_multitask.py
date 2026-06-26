"""test_multitask.py -- offline unit tests for the multi-task organ-injury model.

Tests run entirely on synthetic data (no VitalDB credentials, no real matrix)
and require numpy + sklearn + torch.  Skip gracefully when the stack is absent.

§9 multi-task model guarantees verified here:
  1. masked_bce_loss ignores NaN labels (gradient is zero for missing rows).
  2. SharedTrunkMLP forward pass produces shape (batch, n_tasks).
  3. One SGD update reduces the masked BCE on a seeded synthetic batch.
  4. Per-organ AUROC is computed only on labelable (non-NaN) rows.
  5. run_multitask completes on a synthetic DataFrame and writes results JSON.

Run:
    python3 -m unittest vitaldb_aki.tests.test_multitask -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    import numpy as np
    import pandas as pd
    import torch
    from sklearn.metrics import roc_auc_score
    from vitaldb_aki.models.multitask import (
        ORGAN_TARGETS,
        _build_model,
        _organ_aurocs,
        masked_bce_loss,
        run_multitask,
    )
    HAVE = True
except Exception as _exc:
    HAVE = False
    _SKIP_MSG = str(_exc)


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_synthetic_df(n: int = 200, n_features: int = 8,
                       seed: int = 0) -> pd.DataFrame:
    """Small DataFrame with subjectid, 7 organ_* columns (partial NaN) and
    numeric features -- mimics the full organ-injury feature matrix."""
    rng = np.random.default_rng(seed)

    df = pd.DataFrame()
    df["subjectid"] = [f"subj_{i:04d}" for i in range(n)]

    organs = [
        "organ_renal",
        "organ_hepatocellular",
        "organ_cholestatic",
        "organ_coagulation_plt",
        "organ_coagulation_inr",
        "organ_hypoperfusion",
        "organ_mortality",
    ]
    for i, col in enumerate(organs):
        # ~15 % positive rate; ~20 % rows unlabelled (NaN)
        raw = (rng.random(n) < 0.15).astype(float)
        missing = rng.random(n) < 0.20
        raw[missing] = np.nan
        df[col] = raw

    for j in range(n_features):
        df[f"feat_{j}"] = rng.standard_normal(n).astype(np.float32)

    return df


def _synthetic_cfg(cache_dir: str) -> dict:
    """Minimal config dict pointing to a temp cache dir."""
    return {
        "data": {"cache_dir": cache_dir},
        "evaluation": {
            "outer_folds": 3,
            "inner_folds": 2,
            "bootstrap_iters": 50,
            "target": "organ_renal",
        },
    }


def _write_synthetic_matrix(df: pd.DataFrame, cache_dir: str) -> None:
    """Save the synthetic DataFrame as feature_matrix.csv."""
    os.makedirs(cache_dir, exist_ok=True)
    df.to_csv(os.path.join(cache_dir, "feature_matrix.csv"), index=False)


# ── mock modules that expose only the synthetic feat_* columns ─────────────────

class _FakeSpec:
    """Minimal stand-in for FeatureSpec used by feature_columns."""
    def __init__(self, name: str, fset: str):
        self.name = name
        self.fset = fset
        self.timing = "preop"
        self.leaks = []


class _FakeModule:
    """A fake feature module whose SPECS cover the synthetic feature columns."""
    SPECS: list

    def __init__(self, n_features: int = 8):
        self.SPECS = [_FakeSpec(f"feat_{j}", "comprehensive") for j in range(n_features)]


# ── patch dataset helpers for the synthetic world ─────────────────────────────

def _patched_feature_cols(df: pd.DataFrame, modules):
    """Return (num_cols, cat_cols) for the synthetic DataFrame."""
    num_cols = [c for c in df.columns if c.startswith("feat_")]
    return num_cols, []


# ── test cases ─────────────────────────────────────────────────────────────────

@unittest.skipUnless(HAVE, f"needs torch+sklearn+numpy: {'' if HAVE else _SKIP_MSG!r}")
class TestMaskedBCELoss(unittest.TestCase):
    """Masked BCE correctly ignores NaN labels."""

    def setUp(self):
        torch.manual_seed(0)
        self.batch = 32
        self.n_tasks = 7
        self.preds = torch.rand(self.batch, self.n_tasks)

    def test_all_present_equals_plain_bce(self):
        """When no NaNs, masked_bce == average plain BCE across tasks."""
        import torch.nn.functional as F  # noqa: N812

        targets = torch.randint(0, 2, (self.batch, self.n_tasks)).float()
        got = masked_bce_loss(self.preds, targets)
        expected = torch.mean(
            torch.stack([F.binary_cross_entropy(self.preds[:, k], targets[:, k])
                         for k in range(self.n_tasks)])
        )
        self.assertAlmostEqual(got.item(), expected.item(), places=5)

    def test_nan_column_excluded(self):
        """A fully-NaN organ column does not affect loss."""
        targets_full = torch.randint(0, 2, (self.batch, self.n_tasks)).float()
        targets_nan  = targets_full.clone()
        targets_nan[:, 3] = float("nan")  # wipe out organ index 3

        loss_full = masked_bce_loss(self.preds, targets_full)
        loss_nan  = masked_bce_loss(self.preds, targets_nan)

        # With one fewer organ the two losses are generally different; but
        # removing an organ column must NOT raise and must be a finite float.
        self.assertTrue(torch.isfinite(loss_nan))
        # Verify it is NOT using the same average (6 tasks, not 7)
        self.assertNotAlmostEqual(loss_full.item(), loss_nan.item(), places=5)

    def test_partial_nan_rows_ignored(self):
        """Rows that are NaN for ONE organ do not contribute to that organ's loss."""
        torch.manual_seed(7)
        targets = torch.randint(0, 2, (self.batch, self.n_tasks)).float()
        # Mark first 10 rows as NaN for organ 0 only
        targets_partial = targets.clone()
        targets_partial[:10, 0] = float("nan")

        # Manually compute expected: organ 0 uses rows 10..end; others use all rows
        import torch.nn.functional as F  # noqa: N812

        expected_losses = []
        for k in range(self.n_tasks):
            t_k = targets_partial[:, k]
            mask = ~torch.isnan(t_k)
            expected_losses.append(
                F.binary_cross_entropy(self.preds[mask, k], t_k[mask])
            )
        expected = torch.mean(torch.stack(expected_losses))
        got = masked_bce_loss(self.preds, targets_partial)
        self.assertAlmostEqual(got.item(), expected.item(), places=5)

    def test_all_nan_returns_zero(self):
        """All-NaN target gives 0.0 loss (no active organ)."""
        targets = torch.full((self.batch, self.n_tasks), float("nan"))
        loss = masked_bce_loss(self.preds, targets)
        self.assertEqual(loss.item(), 0.0)


@unittest.skipUnless(HAVE, "needs torch+sklearn+numpy")
class TestSharedTrunkForward(unittest.TestCase):
    """SharedTrunkMLP produces the correct output shape."""

    def test_output_shape(self):
        batch, n_in, n_tasks = 16, 40, 7
        model = _build_model(n_in, n_tasks)
        model.eval()
        x = torch.randn(batch, n_in)
        out = model(x)
        self.assertEqual(out.shape, (batch, n_tasks))

    def test_output_in_zero_one(self):
        """Sigmoid heads keep outputs in (0, 1)."""
        model = _build_model(20, 7)
        model.eval()
        x = torch.randn(50, 20)
        out = model(x)
        self.assertTrue((out >= 0.0).all() and (out <= 1.0).all())

    def test_different_n_tasks(self):
        """Architecture scales to arbitrary task counts."""
        for n_tasks in (1, 3, 7, 10):
            model = _build_model(32, n_tasks)
            model.eval()
            out = model(torch.randn(8, 32))
            self.assertEqual(out.shape[1], n_tasks)


@unittest.skipUnless(HAVE, "needs torch+sklearn+numpy")
class TestTrainingReducesLoss(unittest.TestCase):
    """A few SGD steps on a seeded batch reduce the masked BCE (sanity check)."""

    def test_loss_decreases(self):
        torch.manual_seed(42)
        np.random.seed(42)

        batch, n_in, n_tasks = 64, 20, 7
        X = torch.randn(batch, n_in)
        # Binary targets with ~20 % NaN per organ
        rng = np.random.default_rng(42)
        Y = rng.integers(0, 2, (batch, n_tasks)).astype(float)
        Y[rng.random((batch, n_tasks)) < 0.2] = np.nan
        Yt = torch.tensor(Y, dtype=torch.float32)

        model = _build_model(n_in, n_tasks)
        opt   = torch.optim.Adam(model.parameters(), lr=1e-2)

        # record loss before any training
        model.eval()
        with torch.no_grad():
            loss_before = masked_bce_loss(model(X), Yt).item()

        # 20 steps of gradient descent
        model.train()
        for _ in range(20):
            opt.zero_grad()
            loss = masked_bce_loss(model(X), Yt)
            loss.backward()
            opt.step()

        model.eval()
        with torch.no_grad():
            loss_after = masked_bce_loss(model(X), Yt).item()

        self.assertLess(loss_after, loss_before,
                        f"loss did not decrease: {loss_before:.4f} -> {loss_after:.4f}")


@unittest.skipUnless(HAVE, "needs torch+sklearn+numpy")
class TestOrganAUROC(unittest.TestCase):
    """Per-organ AUROC is computed only on labelable (non-NaN) rows."""

    def setUp(self):
        rng = np.random.default_rng(3)
        n = 300
        self.Y = rng.integers(0, 2, (n, 7)).astype(float)
        # Organ 2: all NaN → AUROC should be NaN/None
        self.Y[:, 2] = np.nan
        # Organ 5: half NaN
        self.Y[:int(n / 2), 5] = np.nan

        # Simulate better-than-random predictions (correlated with truth)
        noise = rng.standard_normal((n, 7)) * 0.5
        self.oof_single = np.clip(self.Y + noise, 0, 1)
        self.oof_single[np.isnan(self.Y)] = np.nan

        self.oof_multi = np.clip(self.Y + rng.standard_normal((n, 7)) * 0.3, 0, 1)
        self.oof_multi[np.isnan(self.Y)] = np.nan

        self.organs = [f"organ_{i}" for i in range(7)]

    def test_all_nan_organ_returns_none(self):
        """Organ with all-NaN labels yields None AUROC."""
        table = _organ_aurocs(self.Y, self.oof_single, self.oof_multi, self.organs)
        row = table[2]   # index 2 is all-NaN
        self.assertIsNone(row["auroc_single"])
        self.assertIsNone(row["auroc_multi"])
        self.assertIsNone(row["delta"])

    def test_partial_nan_organ_uses_labelable_rows_only(self):
        """AUROC for organ 5 (half NaN) is computed only on non-NaN rows."""
        table = _organ_aurocs(self.Y, self.oof_single, self.oof_multi, self.organs)
        row5 = table[5]
        self.assertIsNotNone(row5["auroc_single"])
        # Manually verify: only rows 150..299 for organ 5
        n = self.Y.shape[0]
        y5 = self.Y[int(n / 2):, 5].astype(int)
        p5 = self.oof_single[int(n / 2):, 5]
        expected = float(roc_auc_score(y5, p5))
        self.assertAlmostEqual(row5["auroc_single"], round(expected, 4), places=4)

    def test_delta_equals_multi_minus_single(self):
        """delta = auroc_multi - auroc_single for each organ."""
        table = _organ_aurocs(self.Y, self.oof_single, self.oof_multi, self.organs)
        for row in table:
            if row["auroc_single"] is not None and row["auroc_multi"] is not None:
                expected_delta = row["auroc_multi"] - row["auroc_single"]
                self.assertAlmostEqual(row["delta"], expected_delta, places=3)

    def test_n_events_counted_correctly(self):
        """n_events counts positive labels, ignoring NaN."""
        table = _organ_aurocs(self.Y, self.oof_single, self.oof_multi, self.organs)
        for k, row in enumerate(table):
            expected = int(np.nansum(self.Y[:, k]))
            self.assertEqual(row["n_events"], expected)


@unittest.skipUnless(HAVE, "needs torch+sklearn+numpy")
class TestRunMultitaskSynthetic(unittest.TestCase):
    """run_multitask completes on a synthetic matrix and writes valid JSON."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="vdb_mt_test_")
        self.df = _make_synthetic_df(n=150, n_features=6, seed=7)
        _write_synthetic_matrix(self.df, self.tmpdir)
        self.cfg = _synthetic_cfg(self.tmpdir)
        self.fake_modules = [_FakeModule(n_features=6)]

    def _patched_run(self):
        """Run multitask but with patched _feature_cols to use the fake module."""
        import vitaldb_aki.models.multitask as mt

        # Monkey-patch _feature_cols to work with synthetic data
        _orig = mt._feature_cols

        def _fake_feature_cols(df, modules):
            return _patched_feature_cols(df, modules)

        mt._feature_cols = _fake_feature_cols
        try:
            results = run_multitask(
                self.cfg,
                organ_targets=ORGAN_TARGETS,
                modules=self.fake_modules,
                n_splits=3,
                seed=42,
            )
        finally:
            mt._feature_cols = _orig
        return results

    def test_results_json_written(self):
        """results JSON is created with expected keys."""
        results = self._patched_run()
        json_path = os.path.join(self.tmpdir, "multitask_results.json")
        self.assertTrue(os.path.exists(json_path))
        with open(json_path) as fh:
            data = json.load(fh)
        self.assertIn("table", data)
        self.assertIn("organ_targets", data)

    def test_table_has_all_organs(self):
        """Table has one row per organ target."""
        results = self._patched_run()
        self.assertEqual(len(results["table"]), len(ORGAN_TARGETS))

    def test_table_row_keys(self):
        """Each table row has the required keys."""
        results = self._patched_run()
        required = {"organ", "n_events", "auroc_single", "auroc_multi", "delta"}
        for row in results["table"]:
            self.assertTrue(required.issubset(row.keys()),
                            f"missing keys in {row}")

    def test_auroc_values_in_range(self):
        """Non-None AUROCs must be in [0, 1]."""
        results = self._patched_run()
        for row in results["table"]:
            for key in ("auroc_single", "auroc_multi"):
                val = row[key]
                if val is not None:
                    self.assertGreaterEqual(val, 0.0,
                                            f"{row['organ']} {key}={val}")
                    self.assertLessEqual(val, 1.0,
                                         f"{row['organ']} {key}={val}")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
