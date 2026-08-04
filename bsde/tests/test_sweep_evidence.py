"""Tests for the sweep-to-Evidence bridge, and for the report rows it stops from lying.

THE TEST THAT MATTERS is `test_a_candidate_the_sweep_never_touched_gets_NOT_RUN_naming_itself`. The failure
this module exists to prevent is subtle: a sweep runs, a report row goes green, and nobody notices the sweep
covered a DIFFERENT candidate. "The sweep ran" and "the sweep ran on this candidate" must never be
confusable, so the refusal names the candidate.

`test_report_items_that_nothing_populates_are_enumerated` is the standing guard on the wider problem: a
mandatory report row that no code can satisfy is a promise the format makes and the code cannot keep. It
lists the rows still in that state so the number is visible rather than discovered later.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from bsde.verifier.report import FAIL, NOT_APPLICABLE, NOT_RUN, REPORT_ITEMS
from bsde.verifier.sweeps import (preprocessing_evidence, reduced_channel_evidence, sweep_evidence,
                                  SIGN_FLIP_FRACTION)

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")


def _write(tmp, name, obj):
    with open(os.path.join(tmp, name), "w") as fh:
        json.dump(obj, fh)


# --- the refusals ---------------------------------------------------------------------------------

def test_a_candidate_the_sweep_never_touched_gets_NOT_RUN_naming_itself(tmp_path):
    _write(tmp_path, "e09_preprocessing_sensitivity.json",
           {"n_variants": 72, "exponent": {"frac_above_half": 0.0, "frac_below_half": 1.0}})
    e = preprocessing_evidence("lempel_ziv", str(tmp_path))
    assert e.status == NOT_RUN
    assert "lempel_ziv" in e.reason, (
        "the refusal must name the candidate, or 'the sweep ran' becomes confusable with 'the sweep ran on "
        "this candidate' — which is the whole failure mode")


def test_a_missing_sweep_gives_NOT_RUN_and_says_the_format_promises_it(tmp_path):
    e = preprocessing_evidence("exponent_high", str(tmp_path))
    assert e.status == NOT_RUN
    assert "required report items" in e.reason


def test_a_corrupt_sweep_file_is_treated_as_absent_not_as_zero(tmp_path):
    with open(os.path.join(tmp_path, "e09_preprocessing_sensitivity.json"), "w") as fh:
        fh.write("{not json")
    assert preprocessing_evidence("exponent_high", str(tmp_path)).status == NOT_RUN


# --- what a sweep can and cannot establish ----------------------------------------------------------

def test_a_sign_flipping_sweep_is_a_REFUTATION(tmp_path):
    """The one thing a sensitivity sweep CAN establish: if the direction depends on defensible analysis
    choices, the analyst's degrees of freedom refuted the candidate."""
    _write(tmp_path, "e09_preprocessing_sensitivity.json",
           {"n_variants": 72, "exponent": {"frac_above_half": 0.45, "frac_below_half": 0.55,
                                           "median_auc": 0.49, "iqr": [0.3, 0.7], "min": 0.1, "max": 0.9}})
    e = preprocessing_evidence("exponent_high", str(tmp_path))
    assert e.status == FAIL and e.fatal
    assert "analysis choice" in e.reason


def test_a_stable_sweep_is_NOT_a_pass(tmp_path):
    """Deliberate: there is no defensible threshold at which a sensitivity sweep 'passes', and inventing one
    would turn a descriptive number into a green light."""
    _write(tmp_path, "e09_preprocessing_sensitivity.json",
           {"n_variants": 72, "exponent": {"frac_above_half": 0.0, "frac_below_half": 1.0,
                                           "median_auc": 0.18, "iqr": [0.09, 0.29], "min": 0.06,
                                           "max": 0.43}})
    e = preprocessing_evidence("exponent_high", str(tmp_path))
    assert e.status == NOT_APPLICABLE, "a stable sweep must not be reported as PASS"
    assert not e.fatal
    assert "no defensible threshold" in e.reason


def test_the_flip_threshold_is_the_one_e09_registered():
    assert SIGN_FLIP_FRACTION == 0.10, (
        "E09 registered 10% before running; changing it here would be re-registering after the fact")


# --- the real committed sweeps ------------------------------------------------------------------------

def test_the_real_e09_sweep_populates_the_row_for_the_exponent_family():
    e = preprocessing_evidence("exponent_high", os.path.abspath(RESULTS))
    assert e.item == "preprocessing_sensitivity"
    assert e.status in (NOT_APPLICABLE, FAIL, NOT_RUN)
    if e.status != NOT_RUN:
        assert e.values.get("n_variants") == 72


def test_the_real_e06_sweep_populates_the_reduced_channel_row():
    e = reduced_channel_evidence("lempel_ziv", os.path.abspath(RESULTS))
    assert e.item == "reduced_channel"
    if e.status != NOT_RUN:
        assert "single channel" in e.reason


def test_sweep_evidence_returns_both_items():
    items = {e.item for e in sweep_evidence("exponent_high", os.path.abspath(RESULTS))}
    assert items == {"preprocessing_sensitivity", "reduced_channel"}


# --- the standing guard -------------------------------------------------------------------------------

def test_report_items_that_nothing_populates_are_enumerated():
    """A mandatory report row that no code can satisfy is a promise the format makes and the code cannot
    keep. This lists the rows still in that state, so the number is visible rather than discovered later.

    Update the expected set deliberately when a row gains a producer — never by deleting the assertion.
    """
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "src" / "bsde"
    populated = set()
    for path in src.rglob("*.py"):
        text = path.read_text()
        for item in REPORT_ITEMS:
            if f'item="{item}"' in text:
                populated.add(item)
    unpopulated = sorted(set(REPORT_ITEMS) - populated - {"verdict"})
    assert unpopulated == [], (
        f"report items with no producer: {unpopulated}. Either wire them up or record here, in this "
        "assertion, why the format asks for something the code cannot supply.")
