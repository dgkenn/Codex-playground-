"""Config loading + validation.

The config (config.yaml) is the single versioned source of truth (Sec 0). This
module loads it, validates the firewall-critical invariants, and exposes its
content hash so that "the harmonization parameters were frozen" is a checkable
claim and not a promise.

PyYAML is imported lazily so that the stdlib-only integrity tests (which build
config dicts directly) do not depend on it.
"""
from __future__ import annotations

import os
from typing import Any

from .hashing import hash_object


class ConfigError(ValueError):
    """Raised when the config violates a binding invariant."""


def load_yaml(path: str | os.PathLike) -> dict[str, Any]:
    try:
        import yaml  # lazy: only needed for the real file-backed config
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ConfigError(
            "PyYAML is required to load the YAML config "
            "(`pip install pyyaml`); pass a dict directly in tests."
        ) from exc
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigError(f"config root must be a mapping, got {type(data)!r}")
    return data


# Keys whose presence would let an outcome leak into the Phase-1 workspace.
# Phase-1 data loaders must never expose these (Sec 0, 13).
_OUTCOME_KEYS = frozenset(
    {"outcome", "label", "y", "target", "icd", "icd10", "medication",
     "medications", "report_text", "mortality", "seizure_label"}
)


def validate(cfg: dict[str, Any]) -> dict[str, Any]:
    """Validate binding invariants. Returns the config unchanged on success."""
    phase = cfg.get("phase")
    if phase not in (1, 2):
        raise ConfigError(f"phase must be 1 or 2, got {phase!r}")

    sites = cfg.get("sites", {})
    discovery = sites.get("discovery") or []
    held_out = sites.get("held_out")
    if not discovery:
        raise ConfigError("sites.discovery must list at least one hospital")
    if not held_out:
        raise ConfigError("sites.held_out must name the held-out hospital")
    if held_out in discovery:
        raise ConfigError(
            f"held_out hospital {held_out!r} must NOT be in discovery set "
            "(firewall breach)"
        )

    if cfg.get("phase2", {}).get("run_once") is not True:
        raise ConfigError("phase2.run_once must be true (single-test design)")

    return cfg


def assert_no_outcome_in_loader_fields(fields: list[str]) -> None:
    """Guard Phase-1 loaders: refuse any column that could carry an outcome."""
    lowered = {f.lower() for f in fields}
    leaked = sorted(lowered & _OUTCOME_KEYS)
    if leaked:
        raise ConfigError(
            f"Phase-1 loader exposes outcome-bearing fields {leaked}; "
            "only EEG + acquisition metadata are permitted (Sec 0)."
        )


def config_hash(cfg: dict[str, Any]) -> str:
    """Content hash of the full config (pins all parameters at once)."""
    return hash_object(cfg)


def harmonization_hash(cfg: dict[str, Any]) -> str:
    """Hash of just the harmonization + model-IO params -- one of the four
    objects frozen before unlock (Sec 3)."""
    relevant = {
        "model": {
            k: cfg.get("model", {}).get(k)
            for k in ("name", "repo_id", "revision", "checkpoint_sha256",
                      "expected_sfreq_hz", "channels_10_20",
                      "window_seconds", "window_stride_seconds")
        },
        "harmonization": cfg.get("harmonization", {}),
        "embedding": cfg.get("embedding", {}),
    }
    return hash_object(relevant)
