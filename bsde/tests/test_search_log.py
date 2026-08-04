"""The search log is the denominator of every discovery claim this project makes. These tests pin the
properties that make it usable as one: rejected candidates are recorded, the log is append-only, and the
same run produces the same bytes."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.governance.search_log import append, entry_from_report, read_all, summarise
from bsde.candidates.registry import Candidate
from bsde.verifier.engine import Cohort, verify
from bsde.verifier.report import Evidence

NOW = "2026-07-29T00:00:00Z"


def _cand(name="c"):
    return Candidate(name=name, version="1.0", fn=lambda *a, **k: 0.0,
                     interpretation="test", predictions={"outcome": "higher"},
                     failure_conditions=["x"],
                     requires=("computational", "statistical", "adversarial"), complexity=2)


def _run(seed, planted_site):
    rng = np.random.default_rng(seed)
    n = 270
    if planted_site:
        sites, vals, ys = [], [], []
        for s, off, pr in [("A", 0., .2), ("B", 2., .55), ("C", 4., .85)]:
            sites += [s] * 90
            vals.append(off + rng.normal(0, .5, 90))
            ys.append(rng.binomial(1, pr, 90).astype(float))
        coh = Cohort(values=np.concatenate(vals), y=np.concatenate(ys), subject=np.arange(n),
                     contrast="outcome", nuisance={"site": np.array(sites)},
                     baseline=rng.normal(size=n), dataset="planted")
    else:
        y = rng.binomial(1, .5, n).astype(float)
        # a nuisance MUST be supplied: with none, the adversarial layer has nothing to probe and the
        # engine returns INCOMPLETE rather than SURVIVE. That is the intended behaviour -- silence is not
        # evidence -- so the "clean" fixture has to give the probes something real to chew on.
        coh = Cohort(values=y * 1.3 + rng.normal(0, 1., n), y=y, subject=np.arange(n),
                     contrast="outcome", nuisance={"age": rng.normal(size=n)},
                     baseline=rng.normal(size=n), dataset="planted")
    return verify(_cand(), [coh], np.random.default_rng(0), search_space_size=8,
                  extra_evidence=[Evidence("synthetic_ground_truth", "computational", "pass", "ok")])


def test_a_rejected_candidate_is_recorded_not_discarded(tmp_path):
    """The file-drawer problem in one assertion."""
    rep = _run(11, planted_site=True)
    assert rep.verdict == "REJECT"
    p = str(tmp_path / "SEARCH_LOG.jsonl")
    append(entry_from_report(rep, NOW), p)
    (rec,) = read_all(p)
    assert rec["verdict"] == "REJECT"
    assert "probe:site" in rec["failed_checks"]
    assert rec["declaration_hash"] == rep.declaration_hash


def test_the_log_is_append_only_and_summarises_the_denominator(tmp_path):
    p = str(tmp_path / "SEARCH_LOG.jsonl")
    append(entry_from_report(_run(11, True), NOW), p)
    append(entry_from_report(_run(17, False), NOW), p)
    recs = read_all(p)
    assert len(recs) == 2, "appending must not overwrite"
    s = summarise(recs)
    assert s["n_evaluations"] == 2
    assert s["n_survived"] == 1
    assert s["verdicts"]["REJECT"] == 1
    # the figure that makes a single surviving candidate interpretable
    assert s["n_survived"] < s["n_evaluations"]


def test_effective_search_space_multiplies_candidates_by_analytic_choices(tmp_path):
    rep = _run(17, False)
    e = entry_from_report(rep, NOW, analytic_dof=6)
    assert e["search_space_size"] == 8
    assert e["effective_search_space"] == 48, \
        "eight candidates each explored under six analytic variants is a search of 48, not 8"


def test_the_entry_is_deterministic_and_hashed(tmp_path):
    """Same report, same timestamp, same bytes -- so the log can be regenerated and compared."""
    rep = _run(17, False)
    a = entry_from_report(rep, NOW)
    b = entry_from_report(rep, NOW)
    assert a == b
    assert a["entry_hash"] == b["entry_hash"]
    c = entry_from_report(rep, NOW, analytic_dof=3)
    assert c["entry_hash"] != a["entry_hash"], "a different declared search width is a different record"


def test_no_nan_can_enter_the_log(tmp_path):
    """allow_nan=False: a NaN silently serialised as `NaN` is invalid JSON and breaks every downstream
    reader, which is how a corrupt audit record survives unnoticed."""
    p = str(tmp_path / "SEARCH_LOG.jsonl")
    with pytest.raises(ValueError):
        append({"bad": float("nan")}, p)
