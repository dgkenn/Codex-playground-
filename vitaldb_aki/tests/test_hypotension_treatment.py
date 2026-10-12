"""Offline tests for hypotension_treatment.py -- stdlib + numpy/pandas/sklearn.

Uses the built-in synthetic dataset generator (_make_synthetic_df) so no real
data or network access is needed.  Tests cover:
  - define_treatment:      binary vasopressor column created correctly
  - assign_burden_tertiles: three tertile labels, no NaN on non-degenerate data
  - crude_rate_table:      shape and non-negative counts
  - fit_propensity_model:  produces a propensity_score column in [0, 1]
  - compute_iptw_weights:  positive weights for all rows
  - check_balance:         returns SMD DataFrame with expected columns
  - iptw_outcome_model:    returns OR dict with required keys
  - run_analysis (end-to-end): runs without error, writes output, OR is finite
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

# Ensure package root is on the path so we can import vitaldb_aki.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class TestHypotensionTreatment(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            import numpy  # noqa: F401
            import pandas  # noqa: F401
            import sklearn  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(f"Missing dependency: {exc}") from exc

        from vitaldb_aki.analysis.hypotension_treatment import _make_synthetic_df
        cls.df = _make_synthetic_df(n=300, seed=7)

    def test_define_treatment(self):
        from vitaldb_aki.analysis.hypotension_treatment import define_treatment
        df2 = define_treatment(self.df)
        self.assertIn("vasopressor_treated", df2.columns)
        self.assertTrue(set(df2["vasopressor_treated"].unique()).issubset({0, 1}))
        # At least some treated and untreated
        self.assertGreater(df2["vasopressor_treated"].sum(), 0)
        self.assertGreater((df2["vasopressor_treated"] == 0).sum(), 0)

    def test_assign_burden_tertiles(self):
        import pandas as pd
        from vitaldb_aki.analysis.hypotension_treatment import (
            define_treatment, assign_burden_tertiles
        )
        df2 = assign_burden_tertiles(define_treatment(self.df))
        self.assertIn("burden_tertile", df2.columns)
        self.assertIn("burden_label", df2.columns)
        non_null = df2["burden_label"].dropna()
        self.assertTrue(set(non_null).issubset({"low", "med", "high"}))

    def test_crude_rate_table(self):
        import pandas as pd
        from vitaldb_aki.analysis.hypotension_treatment import (
            define_treatment, assign_burden_tertiles, crude_rate_table
        )
        df2 = assign_burden_tertiles(define_treatment(self.df))
        table = crude_rate_table(df2)
        self.assertIsInstance(table, pd.DataFrame)
        self.assertIn("n", table.columns)
        self.assertIn("events", table.columns)
        self.assertTrue((table["n"] >= 0).all())

    def test_fit_propensity_model(self):
        from vitaldb_aki.analysis.hypotension_treatment import (
            define_treatment, fit_propensity_model
        )
        df2 = define_treatment(self.df)
        df3, _, used = fit_propensity_model(df2)
        self.assertIn("propensity_score", df3.columns)
        ps = df3["propensity_score"]
        self.assertTrue((ps >= 0).all() and (ps <= 1).all())
        self.assertGreater(len(used), 0)

    def test_compute_iptw_weights(self):
        from vitaldb_aki.analysis.hypotension_treatment import (
            define_treatment, fit_propensity_model, compute_iptw_weights
        )
        df2 = define_treatment(self.df)
        df3, _, _ = fit_propensity_model(df2)
        df4 = compute_iptw_weights(df3)
        self.assertIn("iptw_weight", df4.columns)
        self.assertTrue((df4["iptw_weight"] > 0).all())

    def test_check_balance(self):
        import pandas as pd
        from vitaldb_aki.analysis.hypotension_treatment import (
            define_treatment, fit_propensity_model, compute_iptw_weights, check_balance
        )
        df2 = define_treatment(self.df)
        df3, _, used = fit_propensity_model(df2)
        df4 = compute_iptw_weights(df3)
        bal = check_balance(df4, covariates=used, weight_col="iptw_weight")
        self.assertIsInstance(bal, pd.DataFrame)
        self.assertIn("smd", bal.columns)

    def test_iptw_outcome_model(self):
        from vitaldb_aki.analysis.hypotension_treatment import (
            define_treatment, assign_burden_tertiles,
            fit_propensity_model, compute_iptw_weights, iptw_outcome_model
        )
        import math
        df2 = assign_burden_tertiles(define_treatment(self.df))
        df3, _, _ = fit_propensity_model(df2)
        df4 = compute_iptw_weights(df3)
        result = iptw_outcome_model(df4, n_bootstrap=20, seed=1)
        for key in ("OR", "CI_lower", "CI_upper", "log_OR", "n", "n_events"):
            self.assertIn(key, result)
        self.assertTrue(math.isfinite(result["OR"]))

    def test_run_analysis_end_to_end(self):
        """Full pipeline runs and writes JSON output."""
        import math
        from vitaldb_aki.analysis.hypotension_treatment import run_analysis

        with tempfile.TemporaryDirectory() as tmp:
            results = run_analysis(self.df.copy(), cache_dir=tmp)
            # Check output JSON was written
            out_path = os.path.join(tmp, "hypotension_treatment_results.json")
            self.assertTrue(os.path.exists(out_path), "results JSON not written")
            with open(out_path) as fh:
                loaded = json.load(fh)
            self.assertIn("iptw_or", loaded)
            or_val = loaded["iptw_or"].get("OR")
            self.assertIsNotNone(or_val)
            self.assertTrue(math.isfinite(float(or_val)))
            self.assertIn("n_total", loaded)
            self.assertGreater(loaded["n_total"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
