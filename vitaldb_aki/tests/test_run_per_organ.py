"""test_run_per_organ.py -- tests for per-organ evaluation driver.

Tests that the module imports, has correct structure, and can be called
(even if the real evaluation may require the full matrix build).
"""
import json
import os
from unittest import mock

from vitaldb_aki.models import run_per_organ


def test_run_per_organ_imports():
    """Smoke test: module imports without error."""
    assert hasattr(run_per_organ, "run_all")
    assert callable(run_per_organ.run_all)


def test_safe_get():
    """_safe_get navigates nested dicts and returns None safely."""
    d = {"a": {"b": {"c": 42}}}
    assert run_per_organ._safe_get(d, "a", "b", "c") == 42
    assert run_per_organ._safe_get(d, "a", "x") is None
    assert run_per_organ._safe_get(d, "x", "y", "z") is None
    assert run_per_organ._safe_get(d, "a", "b", "c", "d", default="missing") == "missing"


def test_run_all_structure_mock():
    """run_all collects results into expected structure (mocked run)."""
    cfg = {
        "data": {"cache_dir": "/tmp/test_cache"},
        "evaluation": {"target": "composite"},
    }

    # Mock run.run to return a minimal valid result
    def mock_run(cfg, model_name, seed, target):
        return {
            "model": model_name,
            "target": target,
            "sets": {
                "standard": {"auroc": 0.71, "auprc": 0.25, "prevalence": 0.05},
                "comprehensive": {"auroc": 0.74, "auprc": 0.28, "prevalence": 0.05},
                "pk": {"auroc": 0.76, "auprc": 0.31, "prevalence": 0.05},
            },
            "n": 500,
            "n_events": 25,
            "incremental_value": [
                {
                    "contrast": "pk_vs_comprehensive",
                    "delta_auroc": 0.02,
                    "delong_p": 0.15,
                    "delta_auroc_ci95": [-0.01, 0.05],
                    "primary": True,
                }
            ],
            "negative_control": {"set": "pk", "auroc_shuffled": 0.51},
        }

    with mock.patch("vitaldb_aki.models.run.run", side_effect=mock_run):
        # Suppress I/O for test
        with mock.patch("builtins.open", mock.mock_open()):
            with mock.patch("os.makedirs"):
                with mock.patch("builtins.print"):
                    results = run_per_organ.run_all(cfg, model_name="logreg", seed=42)

    # Check structure
    assert results["model"] == "logreg"
    assert results["seed"] == 42
    assert "targets" in results
    assert "errors" in results

    # Each target should have been attempted
    assert len(results["targets"]) + len(results["errors"]) == 8


def test_run_all_error_handling():
    """run_all catches exceptions and records them gracefully."""
    cfg = {"data": {"cache_dir": "/tmp/test_cache"}}

    def mock_run_fail(cfg, model_name, seed, target):
        if target == "organ_renal":
            raise ValueError("Too few events in organ_renal")
        return {
            "model": model_name,
            "target": target,
            "sets": {"standard": {"auroc": 0.70, "auprc": 0.20, "prevalence": 0.02}},
            "n": 100,
            "n_events": 2,
            "incremental_value": [],
            "negative_control": {"set": "standard", "auroc_shuffled": 0.50},
        }

    with mock.patch("vitaldb_aki.models.run.run", side_effect=mock_run_fail):
        with mock.patch("builtins.open", mock.mock_open()):
            with mock.patch("os.makedirs"):
                with mock.patch("builtins.print"):
                    results = run_per_organ.run_all(cfg)

    # organ_renal should be in errors
    assert "organ_renal" in results["errors"]
    assert "Too few events" in results["errors"]["organ_renal"]

    # Others should be in targets
    assert "composite" in results["targets"]
