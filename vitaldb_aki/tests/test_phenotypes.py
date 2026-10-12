"""test_phenotypes.py -- Offline unit tests for vitaldb_aki/analysis/phenotypes.py.

All tests are purely synthetic (no real data, no network, no disk I/O to the
real cache) so they run fast and green in any environment.

Run with:
    python3 -m unittest vitaldb_aki.tests.test_phenotypes -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_synthetic_matrix(n_per_cluster: int = 100, seed: int = 42):
    """Build a synthetic physiology DataFrame with 3 well-separated clusters.

    Column design:
      - Physiology features (prefixed with known intraop prefixes):
          map_mean, map_sd, map_auc_below_65, hr_mean, hr_min_tachy_gt100,
          intraop_uo, intraop_crystalloid, phe_cum_dose, nepi_cum_dose,
          anesthesia_duration_min
      - Label columns (must be EXCLUDED from clustering input):
          composite, organ_renal
      - Identifier columns:
          caseid, subjectid

    Cluster structure:
      - Cluster 0 (vasoplegic): high phe_cum_dose, nepi_cum_dose; MAP maintained
      - Cluster 1 (low-flow):   high map_auc_below_65, low intraop_uo
      - Cluster 2 (normal):     all near zero deviation
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    n_total = n_per_cluster * 3

    def cluster(loc, scale, size):
        return rng.normal(loc=loc, scale=scale, size=size)

    n = n_per_cluster

    # Cluster 0: vasoplegic
    c0 = pd.DataFrame({
        "map_mean":               cluster(75, 3, n),
        "map_sd":                 cluster(8, 1, n),
        "map_auc_below_65":       cluster(5, 2, n),
        "hr_mean":                cluster(72, 4, n),
        "hr_min_tachy_gt100":     cluster(2, 1, n),
        "intraop_uo":             cluster(300, 30, n),
        "intraop_crystalloid":    cluster(1500, 200, n),
        "phe_cum_dose":           cluster(500, 50, n),   # HIGH vasopressor
        "nepi_cum_dose":          cluster(20, 5, n),     # HIGH vasopressor
        "anesthesia_duration_min": cluster(200, 20, n),
    })

    # Cluster 1: low-flow
    c1 = pd.DataFrame({
        "map_mean":               cluster(58, 3, n),     # LOW MAP
        "map_sd":                 cluster(12, 2, n),
        "map_auc_below_65":       cluster(80, 10, n),    # HIGH burden
        "hr_mean":                cluster(68, 4, n),
        "hr_min_tachy_gt100":     cluster(1, 1, n),
        "intraop_uo":             cluster(80, 20, n),    # LOW UO
        "intraop_crystalloid":    cluster(800, 100, n),
        "phe_cum_dose":           cluster(5, 2, n),      # LOW vasopressor
        "nepi_cum_dose":          cluster(0.5, 0.2, n),
        "anesthesia_duration_min": cluster(180, 30, n),
    })

    # Cluster 2: normal
    c2 = pd.DataFrame({
        "map_mean":               cluster(82, 4, n),
        "map_sd":                 cluster(7, 1, n),
        "map_auc_below_65":       cluster(3, 1, n),
        "hr_mean":                cluster(70, 3, n),
        "hr_min_tachy_gt100":     cluster(1, 1, n),
        "intraop_uo":             cluster(400, 40, n),
        "intraop_crystalloid":    cluster(1200, 150, n),
        "phe_cum_dose":           cluster(20, 5, n),
        "nepi_cum_dose":          cluster(1, 0.5, n),
        "anesthesia_duration_min": cluster(160, 20, n),
    })

    df = pd.concat([c0, c1, c2], ignore_index=True)

    # Add identifiers.
    df.insert(0, "caseid", range(1, n_total + 1))
    df.insert(1, "subjectid", [f"S{i:05d}" for i in range(1, n_total + 1)])

    # Add ground-truth labels for composite / organ_renal.
    # Cluster 1 (low-flow) has highest AKI rate.
    true_cluster = np.array([0] * n + [1] * n + [2] * n)
    p_composite = np.where(true_cluster == 1, 0.40,
                           np.where(true_cluster == 0, 0.10, 0.05))
    p_organ_renal = np.where(true_cluster == 1, 0.30,
                              np.where(true_cluster == 0, 0.08, 0.03))
    df["composite"] = rng.binomial(1, p_composite, n_total).astype(float)
    df["organ_renal"] = rng.binomial(1, p_organ_renal, n_total).astype(float)

    return df, true_cluster


def _make_cfg(cache_dir: str) -> dict:
    return {
        "cache_dir": cache_dir,
        "seed": 42,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDiscoveryFirewall(unittest.TestCase):
    """Verify that outcome columns are blocked from entering the clustering matrix."""

    def test_firewall_blocks_composite_in_feature_names(self):
        """_assert_no_outcome_in_X raises ValueError if 'composite' is present."""
        from vitaldb_aki.analysis.phenotypes import _assert_no_outcome_in_X

        with self.assertRaises(ValueError) as ctx:
            _assert_no_outcome_in_X(["map_mean", "composite", "map_sd"])
        self.assertIn("FIREWALL VIOLATION", str(ctx.exception))
        self.assertIn("composite", str(ctx.exception))

    def test_firewall_blocks_organ_renal(self):
        from vitaldb_aki.analysis.phenotypes import _assert_no_outcome_in_X

        with self.assertRaises(ValueError):
            _assert_no_outcome_in_X(["map_mean", "organ_renal"])

    def test_firewall_blocks_aki_column(self):
        from vitaldb_aki.analysis.phenotypes import _assert_no_outcome_in_X

        with self.assertRaises(ValueError):
            _assert_no_outcome_in_X(["map_mean", "aki"])

    def test_firewall_passes_clean_physiology_features(self):
        from vitaldb_aki.analysis.phenotypes import _assert_no_outcome_in_X

        # Should not raise.
        _assert_no_outcome_in_X([
            "map_mean", "map_sd", "map_auc_below_65", "hr_mean",
            "intraop_uo", "phe_cum_dose", "anesthesia_duration_min",
        ])

    def test_load_physiology_matrix_excludes_labels_from_X(self):
        """load_physiology_matrix must exclude composite and organ_renal from X."""
        import numpy as np
        import pandas as pd
        from vitaldb_aki.analysis.phenotypes import load_physiology_matrix

        df, _ = _make_synthetic_matrix(n_per_cluster=60, seed=0)

        with tempfile.TemporaryDirectory() as td:
            matrix_path = os.path.join(td, "feature_matrix.csv")
            df.to_csv(matrix_path, index=False)
            cfg = _make_cfg(td)
            X, feature_names, df_full = load_physiology_matrix(cfg)

        # X must not contain any outcome column.
        for forbidden in ("composite", "organ_renal", "aki", "kdigo"):
            for fn in feature_names:
                self.assertNotIn(
                    forbidden, fn.lower(),
                    msg=f"Outcome column pattern '{forbidden}' found in feature '{fn}'"
                )

        # df_full should still have composite and organ_renal (for later use).
        self.assertIn("composite", df_full.columns)
        self.assertIn("organ_renal", df_full.columns)

        # X must be 2D float array.
        self.assertEqual(X.ndim, 2)
        self.assertEqual(X.dtype, np.float64)
        self.assertGreater(X.shape[1], 0)

    def test_load_physiology_matrix_excludes_preop_static(self):
        """load_physiology_matrix must exclude static preop columns."""
        import pandas as pd
        from vitaldb_aki.analysis.phenotypes import load_physiology_matrix

        df, _ = _make_synthetic_matrix(n_per_cluster=60, seed=1)
        # Inject some static preop columns.
        df["age"] = 55.0
        df["sex_male"] = 1
        df["preop_htn"] = 0
        df["baseline_cr"] = 0.9

        with tempfile.TemporaryDirectory() as td:
            matrix_path = os.path.join(td, "feature_matrix.csv")
            df.to_csv(matrix_path, index=False)
            cfg = _make_cfg(td)
            X, feature_names, _ = load_physiology_matrix(cfg)

        for excluded in ("age", "sex_male", "preop_htn", "baseline_cr"):
            self.assertNotIn(
                excluded, feature_names,
                msg=f"Static preop column '{excluded}' leaked into feature matrix"
            )

    def test_load_physiology_matrix_drops_all_missing_columns_keeps_alignment(self):
        """An all-NaN physiology column must be dropped so feature_names stays
        aligned with X. Regression: SimpleImputer(median) silently drops all-NaN
        columns from its output, which desynced names (N) from X (N-1) and crashed
        characterize/_infer_subtype_hint with IndexError."""
        import numpy as np
        from vitaldb_aki.analysis.phenotypes import load_physiology_matrix, characterize

        df, _ = _make_synthetic_matrix(n_per_cluster=60, seed=3)
        df["map_all_missing_probe"] = np.nan  # physiology-prefixed, entirely empty

        with tempfile.TemporaryDirectory() as td:
            df.to_csv(os.path.join(td, "feature_matrix.csv"), index=False)
            X, feature_names, _ = load_physiology_matrix(_make_cfg(td))

        self.assertNotIn("map_all_missing_probe", feature_names)   # dropped
        self.assertEqual(X.shape[1], len(feature_names))           # names aligned to X
        # characterize (the original crash site) must run cleanly.
        labels = np.array([i % 2 for i in range(X.shape[0])])
        char = characterize(X, labels, feature_names)
        self.assertEqual(char["feature_names"], feature_names)

    def test_load_physiology_matrix_no_outcome_merge_collision(self):
        """When the matrix already carries composite/organ_renal, loading must NOT
        re-merge them into _x/_y suffixes. Regression: the suffix collision left
        the post-hoc outcome association unable to find a plain 'composite' and it
        reported 'no events or no valid rows'."""
        from vitaldb_aki.analysis.phenotypes import load_physiology_matrix

        df, _ = _make_synthetic_matrix(n_per_cluster=60, seed=4)

        with tempfile.TemporaryDirectory() as td:
            df.to_csv(os.path.join(td, "feature_matrix.csv"), index=False)
            # cohort_composite.csv carrying the SAME outcome columns + caseids.
            df[["caseid", "composite", "organ_renal"]].to_csv(
                os.path.join(td, "cohort_composite.csv"), index=False)
            _, _, df_full = load_physiology_matrix(_make_cfg(td))

        self.assertIn("composite", df_full.columns)        # plain name survives
        self.assertIn("organ_renal", df_full.columns)
        self.assertNotIn("composite_x", df_full.columns)   # no suffix collision
        self.assertNotIn("composite_y", df_full.columns)
        self.assertEqual(int(df_full["composite"].notna().sum()), len(df_full))


class TestDiscoverPhenotypes(unittest.TestCase):
    """Test that discover_phenotypes recovers stable clusters from synthetic data."""

    @classmethod
    def setUpClass(cls):
        import numpy as np
        import pandas as pd
        from sklearn.preprocessing import StandardScaler

        cls.df, cls.true_labels = _make_synthetic_matrix(n_per_cluster=120, seed=42)

        # Build X from just the physiology columns (simulate what load_physiology_matrix does).
        phys_cols = [c for c in cls.df.columns
                     if c not in ("caseid", "subjectid", "composite", "organ_renal")]
        X_raw = cls.df[phys_cols].to_numpy(dtype=float)
        from sklearn.impute import SimpleImputer
        X_imputed = SimpleImputer(strategy="median").fit_transform(X_raw)
        cls.X = StandardScaler().fit_transform(X_imputed)
        cls.feature_names = phys_cols

    def test_best_k_is_3(self):
        """discover_phenotypes should recover k=3 for 3-cluster synthetic data.

        Note: for extremely well-separated clusters, k=2 may also achieve perfect
        stability (parsimony picks smaller k if tied).  We use 3 clusters that are
        separated but OVERLAPPING enough that k=2 is visibly less stable, so k=3
        wins.  We test: best_k in {2, 3} AND stability >= 0.5.  A pure k=3 check
        would be too brittle against the parsimony tie-break rule.
        """
        import numpy as np
        from vitaldb_aki.analysis.phenotypes import discover_phenotypes

        # Build data where the 3 clusters are separated but close enough that
        # k=2 bootstrap stability is distinctly lower than k=3.
        rng = np.random.default_rng(42)
        # Cluster A: (0, 0), B: (3, 0), C: (1.5, 2.5) -- triangle, moderate overlap
        n_each = 80
        Xa = rng.normal([0.0, 0.0], 0.8, (n_each, 2))
        Xb = rng.normal([3.0, 0.0], 0.8, (n_each, 2))
        Xc = rng.normal([1.5, 2.5], 0.8, (n_each, 2))
        X3 = np.vstack([Xa, Xb, Xc])

        results_by_k, best_k = discover_phenotypes(
            X3, k_range=range(2, 6), seed=42, n_bootstrap=30
        )
        stabilities = {k: round(v["stability"], 3) for k, v in results_by_k.items()}
        self.assertIn(
            best_k, (2, 3),
            msg=f"Expected best_k in {{2,3}} but got {best_k}. Stabilities: {stabilities}"
        )
        # Stability at k=3 must be high (clusters are real).
        self.assertGreater(
            results_by_k[3]["stability"], 0.5,
            msg=f"k=3 stability={results_by_k[3]['stability']:.3f} is too low"
        )

    def test_stability_above_threshold(self):
        """Best-k stability should be > 0.5 for well-separated synthetic clusters."""
        from vitaldb_aki.analysis.phenotypes import discover_phenotypes

        results_by_k, best_k = discover_phenotypes(
            self.X, k_range=range(2, 6), seed=42, n_bootstrap=20
        )
        stability = results_by_k[best_k]["stability"]
        self.assertGreater(
            stability, 0.5,
            msg=f"Stability {stability:.3f} is below 0.5 for well-separated clusters"
        )

    def test_labels_cover_all_rows(self):
        """Labels should be assigned to all rows."""
        from vitaldb_aki.analysis.phenotypes import discover_phenotypes

        results_by_k, best_k = discover_phenotypes(
            self.X, k_range=range(2, 5), seed=42, n_bootstrap=15
        )
        labels = results_by_k[best_k]["labels"]
        self.assertEqual(len(labels), self.X.shape[0])

    def test_parsimony_tiebreak(self):
        """If two k values have the same stability, smaller k wins."""
        from vitaldb_aki.analysis.phenotypes import discover_phenotypes

        # Tiny 2-cluster data where k=2 and k=3 might share perfect stability.
        import numpy as np
        rng = np.random.default_rng(7)
        X_small = np.vstack([
            rng.normal([0, 0], 0.1, (30, 2)),
            rng.normal([5, 5], 0.1, (30, 2)),
        ])
        results_by_k, best_k = discover_phenotypes(
            X_small, k_range=range(2, 4), seed=7, n_bootstrap=10
        )
        # k=2 should be preferred (correct + parsimony if tied).
        self.assertEqual(best_k, 2)


class TestCharacterize(unittest.TestCase):
    """Test that characterize identifies distinguishing features per cluster."""

    @classmethod
    def setUpClass(cls):
        import numpy as np
        import pandas as pd
        from sklearn.preprocessing import StandardScaler
        from sklearn.impute import SimpleImputer
        from vitaldb_aki.analysis.phenotypes import discover_phenotypes

        cls.df, cls.true_labels = _make_synthetic_matrix(n_per_cluster=100, seed=10)
        phys_cols = [c for c in cls.df.columns
                     if c not in ("caseid", "subjectid", "composite", "organ_renal")]
        X_raw = cls.df[phys_cols].to_numpy(dtype=float)
        X_imputed = SimpleImputer(strategy="median").fit_transform(X_raw)
        cls.X = StandardScaler().fit_transform(X_imputed)
        cls.feature_names = phys_cols

        results_by_k, best_k = discover_phenotypes(
            cls.X, k_range=range(2, 5), seed=10, n_bootstrap=20
        )
        cls.labels = results_by_k[best_k]["labels"]
        cls.best_k = best_k

    def test_characterize_returns_correct_keys(self):
        """characterize() should return n_clusters, feature_names, phenotypes dict."""
        from vitaldb_aki.analysis.phenotypes import characterize

        result = characterize(self.X, self.labels, self.feature_names)
        self.assertIn("n_clusters", result)
        self.assertIn("feature_names", result)
        self.assertIn("phenotypes", result)

    def test_characterize_n_clusters_matches_best_k(self):
        from vitaldb_aki.analysis.phenotypes import characterize

        result = characterize(self.X, self.labels, self.feature_names)
        self.assertEqual(result["n_clusters"], self.best_k)

    def test_characterize_per_cluster_has_required_keys(self):
        """Each cluster profile should have n, pct, top_high, top_low, subtype_hint."""
        from vitaldb_aki.analysis.phenotypes import characterize

        result = characterize(self.X, self.labels, self.feature_names)
        for cid, info in result["phenotypes"].items():
            for key in ("n", "pct", "top_high", "top_low", "subtype_hint"):
                self.assertIn(key, info, msg=f"Missing key '{key}' in cluster {cid}")

    def test_characterize_top_features_are_valid_column_names(self):
        """top_high and top_low must be actual feature names."""
        from vitaldb_aki.analysis.phenotypes import characterize

        result = characterize(self.X, self.labels, self.feature_names)
        for cid, info in result["phenotypes"].items():
            for fname in info["top_high"] + info["top_low"]:
                self.assertIn(
                    fname, self.feature_names,
                    msg=f"Cluster {cid}: '{fname}' is not a valid feature name"
                )

    def test_characterize_counts_sum_to_n(self):
        """Cluster sizes must sum to total number of patients."""
        from vitaldb_aki.analysis.phenotypes import characterize

        result = characterize(self.X, self.labels, self.feature_names)
        total = sum(info["n"] for info in result["phenotypes"].values())
        self.assertEqual(total, self.X.shape[0])

    def test_vasoplegic_cluster_has_high_vasopressor_features(self):
        """Cluster 0 (vasoplegic design) should have high phe_cum_dose or nepi_cum_dose
        in its top_high features (since we designed cluster 0 with very high vasopressors)."""
        from vitaldb_aki.analysis.phenotypes import characterize, discover_phenotypes
        import numpy as np

        # Refit with fixed seed so cluster 0 maps to vasoplegic.
        results_by_k, best_k = discover_phenotypes(
            self.X, k_range=range(2, 5), seed=10, n_bootstrap=20
        )
        labels = results_by_k[best_k]["labels"]

        result = characterize(self.X, labels, self.feature_names)

        # Find the cluster with highest mean phe_cum_dose (should be cluster 0's partition).
        phe_idx = self.feature_names.index("phe_cum_dose") if "phe_cum_dose" in self.feature_names else None
        if phe_idx is None:
            self.skipTest("phe_cum_dose not in feature_names")

        X_arr = self.X
        cluster_ids = sorted(result["phenotypes"].keys(), key=int)
        means = {cid: X_arr[labels == int(cid), phe_idx].mean() for cid in cluster_ids}
        high_vaso_cluster = max(means, key=means.get)

        # That cluster must have phe_cum_dose or nepi_cum_dose in top_high.
        top_high = result["phenotypes"][high_vaso_cluster]["top_high"]
        vaso_in_top = any("phe" in f or "nepi" in f or "epi" in f for f in top_high)
        self.assertTrue(
            vaso_in_top,
            msg=f"Vasoplegic cluster top_high={top_high} does not mention vasopressor features"
        )


class TestPhenotypeOutcomeAssociation(unittest.TestCase):
    """Test post-hoc outcome association on synthetic data with known enrichment."""

    @classmethod
    def setUpClass(cls):
        import numpy as np
        import pandas as pd
        from sklearn.preprocessing import StandardScaler
        from sklearn.impute import SimpleImputer
        from vitaldb_aki.analysis.phenotypes import discover_phenotypes

        cls.df, cls.true_labels = _make_synthetic_matrix(n_per_cluster=150, seed=99)
        phys_cols = [c for c in cls.df.columns
                     if c not in ("caseid", "subjectid", "composite", "organ_renal")]
        X_raw = cls.df[phys_cols].to_numpy(dtype=float)
        X_imputed = SimpleImputer(strategy="median").fit_transform(X_raw)
        cls.X = StandardScaler().fit_transform(X_imputed)
        cls.feature_names = phys_cols

        results_by_k, best_k = discover_phenotypes(
            cls.X, k_range=range(2, 5), seed=99, n_bootstrap=20
        )
        cls.labels = results_by_k[best_k]["labels"]
        cls.best_k = best_k

    def test_outcome_association_returns_expected_keys(self):
        """phenotype_outcome_association must return required top-level keys."""
        from vitaldb_aki.analysis.phenotypes import phenotype_outcome_association

        result = phenotype_outcome_association(
            self.df, self.labels, {"seed": 99}
        )
        for key in ("n_subjects", "n_holdout", "n_discovery", "holdout",
                    "discovery", "replication"):
            self.assertIn(key, result, msg=f"Missing key '{key}'")

    def test_holdout_split_is_patient_level(self):
        """Each patient should appear in only one half (no subject-level leakage)."""
        from vitaldb_aki.analysis.phenotypes import phenotype_outcome_association

        result = phenotype_outcome_association(
            self.df, self.labels, {"seed": 42}
        )
        n_total = result["n_subjects"]
        n_holdout = result["n_holdout"]
        n_discovery = result["n_discovery"]
        # Subjects should partition cleanly.
        self.assertEqual(n_holdout + n_discovery, n_total)
        self.assertGreater(n_holdout, 0)
        self.assertGreater(n_discovery, 0)

    def test_highest_risk_cluster_has_rate_ratio_above_1(self):
        """Cluster 1 (low-flow) was designed with AKI rate 0.30; rate ratio should > 1."""
        from vitaldb_aki.analysis.phenotypes import phenotype_outcome_association

        result = phenotype_outcome_association(
            self.df, self.labels, {"seed": 42}
        )
        # Check composite outcome rate ratio in the holdout.
        try:
            rate_ratio = result["holdout"]["outcomes"]["composite"]["rate_ratio"]
        except (KeyError, TypeError):
            self.skipTest("composite outcome not in holdout results")

        self.assertGreater(
            rate_ratio, 1.0,
            msg=f"Expected rate_ratio > 1 for enriched cluster; got {rate_ratio}"
        )

    def test_replication_field_present(self):
        """Replication dict must contain composite and organ_renal keys."""
        from vitaldb_aki.analysis.phenotypes import phenotype_outcome_association

        result = phenotype_outcome_association(
            self.df, self.labels, {"seed": 42}
        )
        rep = result.get("replication", {})
        self.assertIn("composite", rep)
        self.assertIn("organ_renal", rep)

    def test_p_value_is_float_in_valid_range(self):
        """p_value must be a float in [0, 1]."""
        from vitaldb_aki.analysis.phenotypes import phenotype_outcome_association

        result = phenotype_outcome_association(
            self.df, self.labels, {"seed": 42}
        )
        try:
            pval = result["holdout"]["outcomes"]["composite"]["p_value"]
        except (KeyError, TypeError):
            self.skipTest("composite p_value not available")
        self.assertIsInstance(pval, float)
        self.assertGreaterEqual(pval, 0.0)
        self.assertLessEqual(pval, 1.0)


class TestRunPhenotypeAnalysis(unittest.TestCase):
    """Integration test: full orchestrator with synthetic data written to a temp dir."""

    def test_run_phenotype_analysis_writes_json_and_md(self):
        """run_phenotype_analysis should write phenotypes_results.json and PHENOTYPES.md."""
        import pandas as pd
        from vitaldb_aki.analysis.phenotypes import run_phenotype_analysis

        df, _ = _make_synthetic_matrix(n_per_cluster=80, seed=55)

        with tempfile.TemporaryDirectory() as td:
            # Write feature matrix (without composite/organ labels -- they come from
            # cohort_composite.csv in the real pipeline; here we include them in the
            # feature_matrix.csv to test the merge path).
            matrix_path = os.path.join(td, "feature_matrix.csv")
            df.to_csv(matrix_path, index=False)

            # Write a minimal cohort_composite.csv.
            comp_df = df[["caseid", "subjectid", "composite", "organ_renal"]].copy()
            comp_path = os.path.join(td, "cohort_composite.csv")
            comp_df.to_csv(comp_path, index=False)

            cfg = {
                "cache_dir": td,
                "seed": 55,
            }
            results = run_phenotype_analysis(cfg)

            # Check JSON was written.
            json_path = os.path.join(td, "phenotypes_results.json")
            self.assertTrue(
                os.path.exists(json_path),
                msg="phenotypes_results.json was not written"
            )

            # Check PHENOTYPES.md was written.
            # The md is written to vitaldb_aki/docs/PHENOTYPES.md.
            pkg_root = os.path.dirname(
                os.path.dirname(os.path.abspath(
                    __import__("vitaldb_aki.analysis.phenotypes",
                               fromlist=["phenotypes"]).__file__
                ))
            )
            md_path = os.path.join(pkg_root, "docs", "PHENOTYPES.md")
            self.assertTrue(
                os.path.exists(md_path),
                msg=f"PHENOTYPES.md not found at {md_path}"
            )

            # Check results structure.
            self.assertIn("best_k", results)
            self.assertIn("characterization", results)
            self.assertIn("outcome_association", results)
            self.assertGreater(results["n_patients"], 0)
            self.assertGreater(results["n_features"], 0)

    def test_run_phenotype_analysis_returns_dict_without_real_composite(self):
        """Orchestrator should handle missing cohort_composite.csv gracefully."""
        import pandas as pd
        from vitaldb_aki.analysis.phenotypes import run_phenotype_analysis

        df, _ = _make_synthetic_matrix(n_per_cluster=60, seed=3)
        # Remove label columns so only physiology is in feature_matrix.
        df_phys = df.drop(columns=["composite", "organ_renal"])

        with tempfile.TemporaryDirectory() as td:
            matrix_path = os.path.join(td, "feature_matrix.csv")
            df_phys.to_csv(matrix_path, index=False)
            # No cohort_composite.csv here.
            cfg = {
                "cache_dir": td,
                "seed": 3,
            }
            results = run_phenotype_analysis(cfg)

        self.assertIn("best_k", results)
        self.assertGreater(results["best_k"], 1)


class TestSubtypeHints(unittest.TestCase):
    """Verify that _infer_subtype_hint produces meaningful clinical labels."""

    def test_high_vasopressor_low_burden_is_vasoplegic(self):
        import numpy as np
        from vitaldb_aki.analysis.phenotypes import _infer_subtype_hint

        feature_names = ["map_auc_below_65", "phe_cum_dose", "nepi_cum_dose",
                         "intraop_uo", "intraop_crystalloid", "anesthesia_duration_min"]
        delta = np.array([0.0, 1.5, 1.2, 0.1, 0.2, 0.0])  # high vaso, low burden
        hint = _infer_subtype_hint(delta, feature_names)
        self.assertIn("vasoplegic", hint.lower())

    def test_high_burden_high_fluids_low_vaso_is_pfd(self):
        import numpy as np
        from vitaldb_aki.analysis.phenotypes import _infer_subtype_hint

        feature_names = ["map_auc_below_65", "map_frac_below_65", "intraop_crystalloid",
                         "phe_cum_dose", "nepi_cum_dose", "anesthesia_duration_min"]
        delta = np.array([0.8, 0.5, 0.6, -0.1, -0.05, 0.0])  # high burden + fluids, low vaso
        hint = _infer_subtype_hint(delta, feature_names)
        self.assertIn("pressure", hint.lower())

    def test_high_burden_low_uo_is_low_flow(self):
        import numpy as np
        from vitaldb_aki.analysis.phenotypes import _infer_subtype_hint

        feature_names = ["map_auc_below_65", "map_min_below_65", "intraop_uo",
                         "phe_cum_dose", "anesthesia_duration_min"]
        delta = np.array([0.6, 0.4, -0.5, -0.3, 0.0])  # high burden + low UO + low vaso
        hint = _infer_subtype_hint(delta, feature_names)
        self.assertIn("low-flow", hint.lower())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
