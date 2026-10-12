"""SEARCH_LOG.jsonl — every candidate evaluated, including (especially) the rejected ones.

WHY REJECTED CANDIDATES ARE THE POINT. A result reported at a given significance level means something
different when three candidates were tried than when three thousand were. The literature's file-drawer
problem exists because rejected attempts leave no trace, so the denominator of any discovery claim is
unknowable. This log is the denominator. It is append-only, one JSON object per line, and it records the
verdict whatever the verdict was.

WHAT IT DELIBERATELY DOES NOT DO. It does not stop anyone from running an analysis without logging it. No
mechanism in a single repository can. What it does is make the logged search space a number that can be
published and audited, so that an unlogged search becomes a discrepancy rather than an absence.

DETERMINISM. `now` is a required argument, never read from the clock inside this module. Timestamps read
from the environment make a run irreproducible and make the log impossible to regenerate for verification;
the caller supplies one explicitly.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Iterable, Mapping

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "..", "governance", "SEARCH_LOG.jsonl")


def entry_from_report(report, now: str, *, config_hash: str = "",
                      analytic_dof: int = 1, extra: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """One log line from a VerifierReport.

    `analytic_dof` is the number of distinct analytic choices explored INSIDE this candidate — fit ranges,
    references, window lengths, preprocessing variants. It defaults to 1 and is the caller's honest
    declaration. `search_space_size` counts registered candidates, which is a floor; the product of the two
    is the figure that should be quoted when describing how wide the search actually was.
    """
    checks = {e.check: e.status for e in report.evidence}
    failed = [e.check for e in report.evidence if e.status == "fail"]
    rec = {
        "logged_at": now,
        "candidate": report.candidate,
        "version": report.candidate_version,
        "declaration_hash": report.declaration_hash,
        "verdict": report.verdict,
        "verdict_reasons": list(report.verdict_reasons),
        "datasets": list(report.datasets),
        "required_layers": list(report.required_layers),
        "search_space_size": report.search_space_size,
        "analytic_dof": int(analytic_dof),
        "effective_search_space": int(report.search_space_size) * int(analytic_dof),
        "checks": checks,
        "failed_checks": failed,
        "items_covered": report.items_covered(),
        "config_hash": config_hash,
    }
    if extra:
        rec["extra"] = dict(extra)
    rec["entry_hash"] = hashlib.sha256(
        json.dumps(rec, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()[:16]
    return rec


def append(record: Mapping[str, Any], path: str | None = None) -> str:
    """Append one record. Creates the file and its directory if absent. Returns the path written."""
    p = os.path.abspath(path or DEFAULT_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a") as fh:
        fh.write(json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    return p


def read_all(path: str | None = None) -> list:
    p = os.path.abspath(path or DEFAULT_PATH)
    if not os.path.exists(p):
        return []
    return [json.loads(line) for line in open(p) if line.strip()]


def summarise(records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """The numbers that belong in a manuscript's methods section.

    `n_survived` over `n_evaluations` is the figure a reader needs in order to interpret any single surviving
    candidate, and it is the figure papers almost never report.
    """
    recs = list(records)
    verdicts: Dict[str, int] = {}
    for r in recs:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    return {
        "n_evaluations": len(recs),
        "n_distinct_candidates": len({(r["candidate"], r["version"]) for r in recs}),
        "n_distinct_declarations": len({r["declaration_hash"] for r in recs}),
        "verdicts": dict(sorted(verdicts.items())),
        "n_survived": verdicts.get("SURVIVE", 0),
        "max_effective_search_space": max((r.get("effective_search_space", 0) for r in recs), default=0),
        "datasets_touched": sorted({d for r in recs for d in r.get("datasets", [])}),
    }
