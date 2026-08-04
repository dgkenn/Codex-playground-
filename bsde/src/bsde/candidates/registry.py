"""The candidate declaration format — what a brain-state measure must say about itself before it is tested.

A *candidate* is any function `(data, ch_names, sfreq, meta) -> float | np.ndarray`. Registering one is not
bookkeeping; it is the act that makes the candidate falsifiable. The declaration fixes, IN ADVANCE:

    interpretation          what the measure is claimed to be, physiologically
    predictions             the direction the measure must move, per named contrast
    failure_conditions      what would count as a refutation, in the author's own words
    requires                the verifier layers this candidate's claim must clear to be reported as surviving
    complexity              the cost side of the complexity/performance trade-off
    prior_art               who published this already, if anyone

`declaration_hash()` hashes all of it. The verifier records that hash next to every result. **If the
declaration changes, the hash changes, and the old results no longer apply to the new declaration** — which
is the mechanism that stops a hypothesis from being rewritten after its test is seen. It is a tripwire, not a
lock; the point is that silently moving the goalposts becomes visible in the record.

WHY `predictions` IS A DICT AND NOT A SIGN. A candidate that predicts "higher under unconsciousness" has made
a much weaker claim than one that also predicts "unchanged across anaesthetic drug identity" and "higher in
UWS than in MCS". Every entry is a separate opportunity to be wrong, and a candidate that declares only one
is not thereby safer — it is less informative, and `n_predictions` is reported so that shows.

WHY COMPLEXITY IS DECLARED BY HAND. It is the number of free parameters plus the number of distinct
transformations the measure applies — not lines of code. `z(mean exponent)` costs 2; a fitted 30-feature
gradient boosting model costs far more. A gain that does not exceed the complexity penalty is not a
discovery. Declaring it by hand and having a human check it beats an automatic proxy that is easy to game.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, Mapping, Sequence, Tuple

# The verifier layers a candidate can be required to clear. A candidate is reported as SURVIVING only if it
# clears every layer its own declaration says its claim requires (see verifier/report.py).
LAYERS: Tuple[str, ...] = (
    "computational",   # 1: correct implementation; recovers known synthetic ground truth
    "statistical",     # 2: nested validation, subject-level independence, calibration, multiplicity
    "adversarial",     # 3: EMG / site / drug / age / leakage / trivial-baseline probes
    "cross_domain",    # 4: held-out datasets, devices, drugs, etiologies
    "temporal",        # 5: predicts transitions; direction preserved within subject
    "mechanistic",     # 6: ketamine, REM dreaming, locked-in, neuromuscular blockade
    "clinical",        # 7: adds value over clinician judgement + the existing monitor
)

DIRECTIONS: Tuple[str, ...] = ("higher", "lower", "unchanged")


@dataclass(frozen=True)
class Candidate:
    """A registered candidate measure and the claim it is committed to."""

    name: str
    version: str
    fn: Callable
    interpretation: str
    predictions: Mapping[str, str]          # contrast name -> one of DIRECTIONS
    failure_conditions: Sequence[str]
    requires: Sequence[str]                 # subset of LAYERS
    complexity: int
    min_channels: int = 1
    min_duration_s: float = 30.0
    required_regions: Sequence[str] = field(default_factory=tuple)
    prior_art: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("a candidate needs a name and a version")
        if not self.interpretation.strip():
            raise ValueError(f"{self.name}: interpretation may not be blank — an uninterpreted measure "
                             "cannot be refuted, only tuned")
        if not self.predictions:
            raise ValueError(f"{self.name}: at least one predicted direction must be declared before testing")
        bad = {k: v for k, v in self.predictions.items() if v not in DIRECTIONS}
        if bad:
            raise ValueError(f"{self.name}: predictions must be one of {DIRECTIONS}, got {bad}")
        if not self.failure_conditions:
            raise ValueError(f"{self.name}: state at least one condition that would refute this candidate")
        unknown = [layer for layer in self.requires if layer not in LAYERS]
        if unknown:
            raise ValueError(f"{self.name}: unknown verifier layers {unknown}; known layers are {LAYERS}")
        if "computational" not in self.requires:
            raise ValueError(f"{self.name}: every candidate requires the computational layer — a measure "
                             "that has not been shown to compute what it claims cannot be evaluated")
        if self.complexity < 1:
            raise ValueError(f"{self.name}: complexity must be a positive integer")

    # -- the record -----------------------------------------------------------------------------------

    def declaration(self) -> Dict[str, object]:
        """Everything that was claimed, minus the callable. This is what gets hashed and logged."""
        d = {k: v for k, v in asdict(self).items() if k != "fn"}
        d["predictions"] = dict(sorted(self.predictions.items()))
        d["failure_conditions"] = list(self.failure_conditions)
        d["requires"] = sorted(self.requires)
        d["required_regions"] = list(self.required_regions)
        return d

    def declaration_hash(self) -> str:
        blob = json.dumps(self.declaration(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    @property
    def n_predictions(self) -> int:
        """How many separate ways this candidate has offered to be wrong."""
        return len(self.predictions)

    def predicted(self, contrast: str) -> str | None:
        """The declared direction for a contrast, or None if the candidate never claimed anything about it.

        None is not a pass. The verifier reports an undeclared contrast as `undeclared`, never as satisfied —
        a candidate cannot earn credit for a prediction it did not make.
        """
        return self.predictions.get(contrast)


class CandidateRegistry:
    """Names are unique across versions: `uce_v1` and `uce_v2` are different candidates, not one revised."""

    def __init__(self) -> None:
        self._by_key: Dict[str, Candidate] = {}

    @staticmethod
    def key(name: str, version: str) -> str:
        return f"{name}@{version}"

    def register(self, c: Candidate) -> Candidate:
        k = self.key(c.name, c.version)
        if k in self._by_key:
            existing = self._by_key[k]
            if existing.declaration_hash() != c.declaration_hash():
                raise ValueError(
                    f"{k} is already registered with a DIFFERENT declaration "
                    f"({existing.declaration_hash()} vs {c.declaration_hash()}). Register a new version; "
                    "do not redefine an existing one.")
            return existing
        self._by_key[k] = c
        return c

    def get(self, name: str, version: str | None = None) -> Candidate:
        if version is not None:
            return self._by_key[self.key(name, version)]
        hits = [c for c in self._by_key.values() if c.name == name]
        if not hits:
            raise KeyError(f"no candidate named {name!r}; registered: {sorted(self.names())}")
        if len(hits) > 1:
            raise KeyError(f"{name!r} has versions {[c.version for c in hits]}; specify one")
        return hits[0]

    def names(self) -> list[str]:
        return sorted({c.name for c in self._by_key.values()})

    def all(self) -> list[Candidate]:
        return [self._by_key[k] for k in sorted(self._by_key)]

    def __len__(self) -> int:
        return len(self._by_key)

    def __contains__(self, key: object) -> bool:
        return key in self._by_key

    # -- search-space accounting ---------------------------------------------------------------------

    def search_space_size(self) -> int:
        """How many candidates exist to be tested.

        Reported alongside every result. A finding at p < 0.05 means something different when 3 candidates
        were tried than when 3,000 were — and the only defence against industrialised p-hacking is that this
        number is published rather than inferred. It counts REGISTERED candidates, which is a floor, not a
        ceiling: analytic degrees of freedom inside each candidate are counted separately in SEARCH_LOG.jsonl.
        """
        return len(self._by_key)


REGISTRY = CandidateRegistry()


def register(**kw) -> Candidate:
    """Construct and register in one step. Raises if the declaration is incomplete."""
    return REGISTRY.register(Candidate(**kw))
