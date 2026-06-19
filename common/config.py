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


# Substrings whose presence in a field name would let an outcome (or an EHR
# proxy for one) leak into the Phase-1 workspace. Matched as case-insensitive
# SUBSTRINGS so variants like "seizure_label_v2", "primary_diagnosis",
# "icd9_code", "outcome_30d", "discharge_disposition" are all caught (Sec 0, 13).
_OUTCOME_SUBSTRINGS = (
    "outcome", "label", "target", "icd", "medication", "med_", "report_text",
    "mortality", "death", "deceased", "seizure", "status_epilepticus",
    "diagnos", "dx", "prognos", "recovery", "cpc", "discharge", "disposition",
    "event", "epilepsy", "rx", "drug",
)
# Bare field names that are outcomes/targets on their own.
_OUTCOME_EXACT = frozenset({"y", "outcome", "label", "target", "class"})


def _is_outcome_field(name: str) -> bool:
    n = name.lower()
    return n in _OUTCOME_EXACT or any(tok in n for tok in _OUTCOME_SUBSTRINGS)


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
    """Guard Phase-1 loaders: refuse any column that could carry an outcome
    (or an EHR proxy for one). Call this on the ACTUAL columns present in the
    loaded Phase-1 tables, not just at config time (Sec 0, 13)."""
    leaked = sorted({f for f in fields if _is_outcome_field(f)})
    if leaked:
        raise ConfigError(
            f"Phase-1 loader exposes outcome-bearing field(s) {leaked}; "
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
