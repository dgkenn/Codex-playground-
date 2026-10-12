"""Configuration loading. Experiments are configuration-driven (brief §22); nothing is hard-coded in scripts.

A config is a plain dict loaded from YAML (or JSON if PyYAML is unavailable), with a recorded content hash so
that any result can be traced to the exact parameters that produced it.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "seed": 20260729,
    "preprocessing": {
        "sfreq": 250.0,
        "highpass_hz": 0.5,
        "lowpass_hz": 45.0,
        "notch_hz": None,
        "reference": "average",
    },
    # The aperiodic fit range is the single most influential analysis choice for UCE
    # (RESEARCH_STRATEGY.md §4). It is pinned here and swept in sensitivity analyses.
    "aperiodic": {
        "fit_lo_hz": 1.0,
        "fit_hi_hz": 40.0,
        "exclude_line_hz": None,
        "mode": "loglog_ols",
    },
    "psd": {"window_s": 4.0, "overlap": 0.5},
    "split": {"level": "subject", "n_folds": 5},
}


def _deep_update(base: Dict[str, Any], other: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (other or {}).items():
        out[k] = _deep_update(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def config_hash(cfg: Dict[str, Any]) -> str:
    """Content hash of a config. allow_nan=False so a NaN can never silently enter a manifest."""
    blob = json.dumps(cfg, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def load_config(path: str | None = None, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        text = open(path).read()
        try:
            import yaml
            loaded = yaml.safe_load(text) or {}
        except ImportError:
            loaded = json.loads(text)
        cfg = _deep_update(cfg, loaded)
    if overrides:
        cfg = _deep_update(cfg, overrides)
    cfg["_hash"] = config_hash({k: v for k, v in cfg.items() if not k.startswith("_")})
    return cfg
