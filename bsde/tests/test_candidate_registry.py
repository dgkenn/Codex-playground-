"""The declaration format is only useful if it is impossible to skip. These tests are that guarantee.

The registry's job is not storage. It is to make a candidate state, before it is tested, what it claims to
be and what would refute it — and to make any later change to that claim visible. Every assertion below
corresponds to a way the format could be quietly bypassed.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.candidates.registry import (Candidate, CandidateRegistry, LAYERS, DIRECTIONS)


def _ok(**kw):
    base = dict(name="x", version="1.0", fn=lambda *a, **k: 0.0,
                interpretation="a test candidate",
                predictions={"unconscious_vs_awake": "higher"},
                failure_conditions=["it inverts across datasets"],
                requires=("computational", "statistical"), complexity=2)
    base.update(kw)
    return Candidate(**base)


# --- the declaration cannot be incomplete -----------------------------------------------------------

def test_a_candidate_without_an_interpretation_is_refused():
    """An uninterpreted measure cannot be refuted, only tuned."""
    with pytest.raises(ValueError, match="interpretation"):
        _ok(interpretation="   ")


def test_a_candidate_without_a_prediction_is_refused():
    with pytest.raises(ValueError, match="predicted direction"):
        _ok(predictions={})


def test_a_candidate_without_failure_conditions_is_refused():
    with pytest.raises(ValueError, match="refute"):
        _ok(failure_conditions=[])


def test_predictions_must_use_the_declared_vocabulary():
    with pytest.raises(ValueError, match="predictions must be one of"):
        _ok(predictions={"unconscious_vs_awake": "goes up a bit"})
    for d in DIRECTIONS:
        _ok(predictions={"unconscious_vs_awake": d})


def test_every_candidate_must_require_the_computational_layer():
    """A measure not shown to compute what it claims cannot be evaluated at all."""
    with pytest.raises(ValueError, match="computational"):
        _ok(requires=("statistical", "adversarial"))


def test_unknown_verifier_layers_are_refused():
    with pytest.raises(ValueError, match="unknown verifier layers"):
        _ok(requires=("computational", "vibes"))


def test_complexity_must_be_positive():
    with pytest.raises(ValueError, match="complexity"):
        _ok(complexity=0)


# --- the hash is the tripwire -----------------------------------------------------------------------

def test_the_declaration_hash_ignores_the_callable_but_not_the_claim():
    """Refactoring the implementation must not change the hash; changing the claim must."""
    a = _ok(fn=lambda *a, **k: 1.0)
    b = _ok(fn=lambda *a, **k: 2.0)
    assert a.declaration_hash() == b.declaration_hash()
    c = _ok(predictions={"unconscious_vs_awake": "lower"})
    assert c.declaration_hash() != a.declaration_hash()


def test_the_hash_is_insensitive_to_the_order_things_were_written_in():
    a = _ok(predictions={"mcs_vs_uws": "lower", "unconscious_vs_awake": "higher"},
            requires=("statistical", "computational"))
    b = _ok(predictions={"unconscious_vs_awake": "higher", "mcs_vs_uws": "lower"},
            requires=("computational", "statistical"))
    assert a.declaration_hash() == b.declaration_hash()


def test_redefining_a_registered_version_with_a_different_claim_is_refused():
    """This is the mechanism that stops a hypothesis being rewritten after its test is seen."""
    reg = CandidateRegistry()
    reg.register(_ok())
    reg.register(_ok())                       # identical declaration -> idempotent, no error
    with pytest.raises(ValueError, match="DIFFERENT declaration"):
        reg.register(_ok(predictions={"unconscious_vs_awake": "lower"}))


def test_a_new_version_is_a_new_candidate_not_a_revision():
    reg = CandidateRegistry()
    reg.register(_ok(version="1.0"))
    reg.register(_ok(version="2.0", predictions={"unconscious_vs_awake": "lower"}))
    assert len(reg) == 2
    with pytest.raises(KeyError, match="specify one"):
        reg.get("x")
    assert reg.get("x", "2.0").predictions["unconscious_vs_awake"] == "lower"


# --- undeclared contrasts earn nothing ---------------------------------------------------------------

def test_an_undeclared_contrast_returns_none_rather_than_a_default():
    c = _ok(predictions={"unconscious_vs_awake": "higher"})
    assert c.predicted("unconscious_vs_awake") == "higher"
    assert c.predicted("command_following") is None


def test_search_space_size_counts_registered_candidates():
    reg = CandidateRegistry()
    assert reg.search_space_size() == 0
    reg.register(_ok(name="a"))
    reg.register(_ok(name="b"))
    assert reg.search_space_size() == 2


# --- the seed set itself -----------------------------------------------------------------------------

def test_the_seed_set_registers_and_every_declaration_is_complete():
    from bsde.candidates.seed import seed_registry, CONTRASTS
    cands = seed_registry()
    assert len(cands) >= 8
    names = {c.name for c in cands}
    assert "whole_head_exponent" in names, "the trivial baseline must be registered like any other candidate"
    assert "uce_v1" in names, "UCE v1 is demoted to a candidate, not deleted"
    for c in cands:
        assert c.declaration_hash()
        assert all(k in CONTRASTS for k in c.predictions), f"{c.name} names an unknown contrast"
        assert all(ly in LAYERS for ly in c.requires)


def test_uce_v1_stays_frozen_and_declares_the_baseline_it_must_beat():
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.uce_v1 import W_FRONTAL, W_POSTERIOR
    seed_registry()
    from bsde.candidates.registry import REGISTRY
    u = REGISTRY.get("uce_v1")
    assert (W_FRONTAL, W_POSTERIOR) == (0.696, 0.718)
    assert u.version.endswith("frozen")
    assert any("whole_head_exponent" in f for f in u.failure_conditions), \
        "UCE v1 must declare, in advance, that failing to beat the one-feature baseline refutes it"
    assert tuple(u.required_regions) == ("frontal", "posterior")


def test_the_seed_set_declares_drug_invariance_where_it_matters():
    """Discovery Challenge A: a consciousness marker must not be a drug detector. Candidates claiming to
    index consciousness declare `unchanged`; the known pharmacological signature declares that it is not."""
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    seed_registry()
    assert REGISTRY.get("whole_head_exponent").predictions["anaesthetic_drug_identity"] == "unchanged"
    assert REGISTRY.get("lempel_ziv").predictions["anaesthetic_drug_identity"] == "unchanged"
    assert REGISTRY.get("relative_alpha_power").predictions["anaesthetic_drug_identity"] == "higher", \
        "frontal alpha IS a propofol signature; declaring otherwise would be dishonest"


def test_every_seeded_candidate_is_computable_on_synthetic_eeg():
    """The adapters must actually run end to end, on a montage that supports every one of them."""
    from bsde.candidates.seed import seed_registry
    from bsde.synth import simulate_recording
    chs = ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2"]
    data, chs, _ = simulate_recording(n_channels=len(chs), n_seconds=60.0, sfreq=250.0,
                                      exponent=1.5, seed=3, ch_names=chs)
    for c in seed_registry():
        v = c.fn(data, chs, 250.0, {})
        assert np.isfinite(v), f"{c.name} returned {v} on clean synthetic EEG"
