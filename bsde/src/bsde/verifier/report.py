"""The verdict: SURVIVE / REVISE / REJECT — and the rules that stop it from being generous.

Every check returns an `Evidence` record, never a bare p-value. The verdict is a deterministic function of
the evidence, computed by `decide()`, and the ORDER of that function is the part that took the longest to get
right. Three failure modes from the sibling project's error catalogue are encoded here directly:

    rule 31  When a replication fails its own gate, the downstream verdict is ABSENT, not negative. A broken
             harness must not be allowed to print a clean-looking negative result.
    rule 34  A placebo/negative control must GATE the verdict, not sit beside it. A test with no placebo is a
             test with no denominator.
    rule 37  Verdict logic that evaluates checks in the wrong order makes failing tests print as passing. In
             particular: a directional claim is NOT satisfied by an interval spanning the null.

`decide()` therefore resolves in this order, and the order is load-bearing:

    1. MACHINERY gates. If the permutation null is not centred at chance, or a positive control the pipeline
       is known to be able to detect was missed, then nothing downstream means anything -- including an
       apparent refutation, which could equally be the broken harness. -> INDETERMINATE.
    2. FATAL failures. A confound probe that fires is a refutation, and a refutation is not softened by an
       incomplete verifier run. -> REJECT.
    3. COMPLETENESS. A candidate cannot SURVIVE on checks that never ran. Silence is not evidence.
       -> INCOMPLETE.
    4. Non-fatal failures. -> REVISE.
    5. Everything the candidate's own declaration required has passed. -> SURVIVE.

Note what step 5 says: *the candidate's own declaration*. A candidate that declares it only needs the
computational layer can "survive" trivially, and that is intentional — the survival is then reported together
with the short list of layers it asked to be judged on, which is far more revealing than a blanket pass.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Sequence

# The ten items the brief requires every report to contain. A report that cannot fill one prints NOT RUN
# against it rather than omitting the row, so a gap in coverage is visible instead of invisible.
REPORT_ITEMS: Sequence[str] = (
    "cross_dataset_performance",
    "within_subject_state_response",
    "leave_one_dataset_out",
    "confound_probes",
    "preprocessing_sensitivity",
    "baseline_comparison",
    "temporal_transition",
    "complexity_interpretability",
    "reduced_channel",
    "verdict",
)

PASS, FAIL, NOT_RUN, NOT_APPLICABLE = "pass", "fail", "not_run", "not_applicable"

SURVIVE, REVISE, REJECT = "SURVIVE", "REVISE", "REJECT"
INDETERMINATE, INCOMPLETE = "INDETERMINATE", "INCOMPLETE"


@dataclass
class Evidence:
    """One check. `values` carries the numbers so a reader can disagree with the interpretation."""

    check: str
    layer: str
    status: str
    reason: str
    values: Dict[str, object] = field(default_factory=dict)
    item: str = ""            # which of REPORT_ITEMS this populates
    fatal: bool = False       # a FAIL here is a refutation
    machinery_gate: bool = False  # a FAIL here means nothing downstream is interpretable

    def __post_init__(self) -> None:
        if self.status not in (PASS, FAIL, NOT_RUN, NOT_APPLICABLE):
            raise ValueError(f"{self.check}: bad status {self.status!r}")
        if self.item and self.item not in REPORT_ITEMS:
            raise ValueError(f"{self.check}: unknown report item {self.item!r}")
        if self.fatal and self.machinery_gate:
            raise ValueError(f"{self.check}: a check cannot be both a refutation and a machinery gate — "
                             "decide which failure it represents")


@dataclass
class VerifierReport:
    candidate: str
    candidate_version: str
    declaration_hash: str
    search_space_size: int
    evidence: List[Evidence] = field(default_factory=list)
    verdict: str = NOT_RUN
    verdict_reasons: List[str] = field(default_factory=list)
    required_layers: List[str] = field(default_factory=list)
    datasets: List[str] = field(default_factory=list)

    # -- composition ----------------------------------------------------------------------------------

    def add(self, ev: Evidence) -> "VerifierReport":
        self.evidence.append(ev)
        return self

    def by_layer(self, layer: str) -> List[Evidence]:
        return [e for e in self.evidence if e.layer == layer]

    def failures(self) -> List[Evidence]:
        return [e for e in self.evidence if e.status == FAIL]

    def items_covered(self) -> Dict[str, str]:
        """Which of the ten required report items have at least one non-NOT_RUN piece of evidence."""
        out = {}
        for item in REPORT_ITEMS:
            evs = [e for e in self.evidence if e.item == item]
            if not evs:
                out[item] = NOT_RUN
            elif all(e.status == NOT_RUN for e in evs):
                out[item] = NOT_RUN
            elif any(e.status == FAIL for e in evs):
                out[item] = FAIL
            elif all(e.status == NOT_APPLICABLE for e in evs):
                out[item] = NOT_APPLICABLE
            else:
                out[item] = PASS
        out["verdict"] = self.verdict
        return out

    def to_json(self) -> str:
        d = asdict(self)
        d["items_covered"] = self.items_covered()
        return json.dumps(d, indent=2, sort_keys=True, default=str)


def decide(report: VerifierReport) -> VerifierReport:
    """Resolve the verdict. See the module docstring for why the order is what it is."""
    reasons: List[str] = []

    # --- 1. machinery gates ------------------------------------------------------------------------
    broken = [e for e in report.evidence if e.machinery_gate and e.status == FAIL]
    if broken:
        report.verdict = INDETERMINATE
        report.verdict_reasons = [f"machinery gate failed ({e.check}): {e.reason}" for e in broken] + [
            "No verdict is issued. A broken harness can manufacture a negative result as easily as a "
            "positive one, so this run says nothing about the candidate either way."]
        return report

    # --- 2. refutations ----------------------------------------------------------------------------
    refuted = [e for e in report.evidence if e.fatal and e.status == FAIL]
    if refuted:
        report.verdict = REJECT
        report.verdict_reasons = [f"{e.check}: {e.reason}" for e in refuted]
        return report

    # --- 3. completeness ---------------------------------------------------------------------------
    required = set(report.required_layers)
    covered = {e.layer for e in report.evidence if e.status in (PASS, FAIL)}
    missing = sorted(required - covered)
    not_run_in_required = sorted({e.check for e in report.evidence
                                  if e.layer in required and e.status == NOT_RUN})
    if missing or not_run_in_required:
        report.verdict = INCOMPLETE
        if missing:
            reasons.append(f"required layers with no evidence at all: {missing}")
        if not_run_in_required:
            reasons.append(f"checks in required layers that did not run: {not_run_in_required}")
        reasons.append("A candidate cannot survive on checks that were never executed.")
        report.verdict_reasons = reasons
        return report

    # --- 4/5. pass or revise -----------------------------------------------------------------------
    failed_required = [e for e in report.evidence if e.layer in required and e.status == FAIL]
    if failed_required:
        report.verdict = REVISE
        report.verdict_reasons = [f"{e.check} ({e.layer}): {e.reason}" for e in failed_required]
        return report

    report.verdict = SURVIVE
    other_failures = [e for e in report.failures() if e.layer not in required]
    report.verdict_reasons = [
        f"cleared every layer this candidate's declaration requires: {sorted(required)}"]
    if other_failures:
        report.verdict_reasons.append(
            "NOTE — failures outside the required set, which the declaration did not ask to be judged on: "
            + "; ".join(f"{e.check} ({e.layer})" for e in other_failures))
    return report


def render(report: VerifierReport) -> str:
    """Human-readable report. The ten required items are printed whether or not they were populated."""
    w = 100
    L = ["=" * w,
         f"VERIFIER REPORT — {report.candidate} v{report.candidate_version}",
         f"declaration {report.declaration_hash}   search space {report.search_space_size} registered "
         f"candidates   datasets {report.datasets or ['none']}",
         "=" * w, ""]
    order = ["computational", "statistical", "adversarial", "cross_domain",
             "temporal", "mechanistic", "clinical"]
    seen = [ly for ly in order if report.by_layer(ly)] + \
           [ly for ly in {e.layer for e in report.evidence} if ly not in order]
    for layer in seen:
        req = " (REQUIRED)" if layer in report.required_layers else ""
        L.append(f"-- layer: {layer}{req} " + "-" * max(0, w - 12 - len(layer) - len(req)))
        for e in report.by_layer(layer):
            mark = {PASS: "PASS", FAIL: "FAIL", NOT_RUN: "....", NOT_APPLICABLE: "n/a "}[e.status]
            tag = "  [REFUTES]" if e.fatal else ("  [GATE]" if e.machinery_gate else "")
            L.append(f"   {mark}  {e.check}{tag}")
            L.append(f"         {e.reason}")
            if e.values:
                L.append("         " + "  ".join(
                    f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}" for k, v in e.values.items()))
        L.append("")
    L.append("-- required report items " + "-" * (w - 25))
    cov = report.items_covered()
    for item in REPORT_ITEMS:
        if item == "verdict":
            continue
        L.append(f"   {cov[item]:<16} {item}")
    L += ["", "=" * w, f"VERDICT: {report.verdict}", "=" * w]
    for r in report.verdict_reasons:
        L.append(f"   - {r}")
    return "\n".join(L)
