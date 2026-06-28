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

# Each Phase-2 variant gates on its own validation marker, written only after the
# relevant predictor is shown leakage-clean on the locked test partition. A
# generative-counterfactual engine AMPLIFIES the predictor's confounds, so it may
# only ever interpret a validated, confound-free predictor.
GATES = {
    # Phase 2 (a-line outcome axis): the a-line organ-injury increment must beat the
    # hypotension scalars (HPI guard) + pass the leakage battery, on locked test.
    "aline_outcome": ("aline_hpi_guard_passed.json", {
        "hpi_incremental": True,
        "leakage_battery": "pass",
        "locked_test": True,
    }),
    # Phase 2b (Ce drug-exposure axis): the Ce predictor must read the EEG ONLY (not
    # the infusion pump / drug totals -- "reading the syringe"), pass leakage, locked.
    "ce_axis": ("ce_predictor_validated.json", {
        "ce_from_eeg_only": True,
        "leakage_battery": "pass",
        "locked_test": True,
    }),
}

# Back-compat default (the original a-line gate).
GATE_MARKER, REQUIRED = GATES["aline_outcome"]


class Phase2PrerequisiteError(RuntimeError):
    """Raised when Phase 2 is attempted before the a-line increment is validated."""


def phase2_prereq_status(cfg: dict[str, Any], gate: str = "aline_outcome") -> dict[str, Any]:
    """Return {satisfied, reasons, marker} for the named Phase-2 gate
    (``aline_outcome`` or ``ce_axis``)."""
    if gate not in GATES:
        raise ValueError(f"unknown Phase-2 gate {gate!r}; choose from {list(GATES)}")
    marker_name, required = GATES[gate]
    cache_dir = (cfg.get("data", {}) or {}).get("cache_dir") or cfg.get("cache_dir", "vitaldb_aki/cache")
    path = os.path.join(cache_dir, marker_name)
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
    for k, want in required.items():
        got = marker.get(k)
        if got != want:
            reasons.append(f"requirement {k!r}: need {want!r}, marker has {got!r}")
    return {"satisfied": not reasons, "reasons": reasons, "marker": marker}


def assert_phase2_prerequisite(cfg: dict[str, Any], gate: str = "aline_outcome") -> None:
    """Hard gate: raise Phase2PrerequisiteError unless the named predictor is
    validated leakage-clean. Call this FIRST in every Phase-2 entry point."""
    status = phase2_prereq_status(cfg, gate=gate)
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
    for gate in GATES:
        st = phase2_prereq_status(cfg, gate=gate)
        print(f"[{gate}] Phase-2 prerequisite satisfied: {st['satisfied']}")
        for r in st["reasons"]:
            print(f"    - {r}")
