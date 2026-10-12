"""base.py -- the feature contract shared by every feature module (Sec 7-9, 11).

Each feature module declares a list of `FeatureSpec` and an `extract(cfg, cases,
caseids) -> {caseid: {feature_name: value|None}}`. A spec carries:

  * fset   -- which nested set it belongs to: "standard" | "comprehensive" | "pk"
              (Sec 9: Standard subset of +Comprehensive subset of +PK).
  * timing -- "preop" | "intraop". NEVER "postop": the prediction cutoff is end of
              surgery (Sec 11.1/11.2), so any feature timed after it is leakage and
              `audit_specs` raises. The KDIGO label may use postop creatinine by
              definition; features may not.

This is the single chokepoint the leakage battery (Sec 11) enforces, mirroring the
EEG study's loader firewall.
"""
from __future__ import annotations

from dataclasses import dataclass

ALLOWED_SETS = ("standard", "comprehensive", "pk")
ALLOWED_TIMING = ("preop", "intraop")


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    fset: str       # standard | comprehensive | pk
    timing: str     # preop | intraop  (postop == leakage, forbidden)
    desc: str = ""


class LeakageError(AssertionError):
    """Raised when a feature is timed after the prediction cutoff (Sec 11)."""


def audit_specs(specs: list[FeatureSpec]) -> None:
    """Enforce the Sec 11 leakage firewall + valid set membership. Hard error."""
    seen: set[str] = set()
    for s in specs:
        if s.timing not in ALLOWED_TIMING:
            raise LeakageError(
                f"feature {s.name!r} has timing {s.timing!r}; only {ALLOWED_TIMING} "
                "are admissible (prediction cutoff = end of surgery, Sec 11)."
            )
        if s.fset not in ALLOWED_SETS:
            raise ValueError(f"feature {s.name!r} has unknown set {s.fset!r}")
        if s.name in seen:
            raise ValueError(f"duplicate feature name {s.name!r}")
        seen.add(s.name)


def names_for_set(specs: list[FeatureSpec], fset: str) -> list[str]:
    """Names in a NESTED set (Sec 9): standard subset of comprehensive subset of +pk."""
    order = {"standard": 0, "comprehensive": 1, "pk": 2}
    if fset not in order:
        raise ValueError(fset)
    keep = {k for k, v in order.items() if v <= order[fset]}
    return [s.name for s in specs if s.fset in keep]
