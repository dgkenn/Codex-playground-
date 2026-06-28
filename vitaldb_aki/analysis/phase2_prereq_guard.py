"""phase2_prereq_guard.py -- BINDING gate for Phase 2 generative-counterfactual
interpretability of the arterial-waveform arm.

Generative-counterfactual interpretability reveals WHAT THE PREDICTIVE MODEL RELIES
ON. Applied to a model that leaks (re-reads MAP / a hypotension scalar), it will
synthesize a plausible waveform encoding the confound and launder it into a false
"morphological discovery." Therefore Phase 2 may ONLY interpret a model already
shown to be leakage-clean AND incremental over the hypotension scalars (the HPI
guard) on the LOCKED test partition.

This guard is load-bearing: call `assert_phase2_prerequisite(cfg)` at the top of any
Phase-2 entry point. It refuses to proceed unless Paper-1 validation has written the
gate marker. stdlib only (imports + runs without numpy/torch).

See docs/PHASE2_GENERATIVE_COUNTERFACTUAL.md.
"""
from __future__ import annotations

import json
import os
from typing import Any

GATE_MARKER = "aline_hpi_guard_passed.json"

# The marker, written by Paper-1 validation, must assert ALL of these.
REQUIRED = {
    "hpi_incremental": True,   # a-line increment beats hypotension scalars (HPI guard)
    "leakage_battery": "pass", # §12 leakage/confound battery passed
    "locked_test": True,       # evaluated on the locked test partition, not in-sample
}


class Phase2PrerequisiteError(RuntimeError):
    """Raised when Phase 2 is attempted before the a-line increment is validated."""


def phase2_prereq_status(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return {satisfied: bool, reasons: [...], marker: <contents or None>}."""
    cache_dir = (cfg.get("data", {}) or {}).get("cache_dir") or cfg.get("cache_dir", "vitaldb_aki/cache")
    path = os.path.join(cache_dir, GATE_MARKER)
    if not os.path.exists(path):
        return {
            "satisfied": False,
            "reasons": [
                f"gate marker {path!r} does not exist -- the Paper-1 a-line increment "
                "has not been validated leakage-clean + HPI-incremental on the locked "
                "test partition. Phase 2 is correctly blocked."
            ],
            "marker": None,
        }
    try:
        with open(path, encoding="utf-8") as fh:
            marker = json.load(fh)
    except Exception as exc:
        return {"satisfied": False, "reasons": [f"gate marker unreadable: {exc}"], "marker": None}

    reasons = []
    for k, want in REQUIRED.items():
        got = marker.get(k)
        if got != want:
            reasons.append(f"requirement {k!r}: need {want!r}, marker has {got!r}")
    return {"satisfied": not reasons, "reasons": reasons, "marker": marker}


def assert_phase2_prerequisite(cfg: dict[str, Any]) -> None:
    """Hard gate: raise Phase2PrerequisiteError unless the a-line increment is
    validated. Call this FIRST in every Phase-2 entry point."""
    status = phase2_prereq_status(cfg)
    if not status["satisfied"]:
        raise Phase2PrerequisiteError(
            "Phase 2 generative-counterfactual interpretability is BLOCKED.\n"
            "  You may only interpret a model proven leakage-clean + HPI-incremental.\n"
            + "\n".join(f"  - {r}" for r in status["reasons"])
            + "\n  See docs/PHASE2_GENERATIVE_COUNTERFACTUAL.md."
        )


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    cfg = {"cache_dir": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")}
    st = phase2_prereq_status(cfg)
    print(f"Phase 2 prerequisite satisfied: {st['satisfied']}")
    for r in st["reasons"]:
        print(f"  - {r}")
