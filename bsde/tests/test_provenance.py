"""Tests for the licence-provenance join.

The failure mode this guards against is a permissive DEFAULT. A new deposit that nobody added to the
registry, or a `dataset` value that does not match its registry key, must report as UNVERIFIED and count
against commercial cleanliness -- never as clean. "The bucket was public" is not a licence.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bsde.provenance import DATASET_TO_REGISTRY, audit, licence_for, load_registry


def test_an_unmapped_dataset_is_unverified_not_clean():
    lic = licence_for("some_deposit_nobody_registered")
    assert lic["commercial_use"] == "UNVERIFIED"
    assert lic["dataset_id"].startswith("UNMAPPED:")


def test_every_mapped_key_exists_in_the_registry():
    """A mapping pointing at a missing registry row would silently report UNVERIFIED for a deposit whose
    terms HAVE been read -- the opposite error, and just as bad."""
    reg = load_registry()
    if not reg:
        return
    missing = sorted({v for v in DATASET_TO_REGISTRY.values() if v not in reg})
    assert not missing, f"mapped to registry ids that do not exist: {missing}"


def test_unverified_counts_against_commercial_cleanliness(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("recording_id,dataset,status\nr1,some_unregistered_thing,ok\n")
    rep = audit([str(p)])
    assert rep["commercially_clean"] is False
    assert rep["unverified"], "an unread licence must show up as unverified, not be silently ignored"


def test_a_clean_deposit_reports_clean(tmp_path):
    reg = load_registry()
    if reg.get("openneuro_ds004541", {}).get("commercial_use") != "YES":
        return
    p = tmp_path / "t.csv"
    p.write_text("recording_id,dataset,status\nr1,ds004541,ok\n")
    rep = audit([str(p)])
    assert rep["commercially_clean"] is True
    assert not rep["commercial_blockers"]


def test_the_registry_records_the_vitaldb_licence_conflict():
    """Two sources give VitalDB two different licences. The registry must record the CONFLICT rather than
    resolving it silently in either direction -- resolving it is a lawyer's job, not this file's."""
    reg = load_registry()
    if "vitaldb" not in reg:
        return
    text = (reg["vitaldb"]["license_name"] + " " + reg["vitaldb"]["notes"]).lower()
    assert "conflict" in text
    assert "cc by 4.0" in text and "nc-sa" in text
    assert "api.vitaldb.net" in reg["vitaldb"]["notes"], (
        "the notes must say WHICH grant applies to the bytes on disk, or the conflict is undecidable later")
