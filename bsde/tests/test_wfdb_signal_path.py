"""Regression test: a WFDB signal filename resolves relative to its HEADER's directory.

A .hea names its signal file bare -- `0284_010_012_EEG.mat` -- and WFDB semantics put that file beside the
header, not at the collection root. `read_wfdb_window_http` joined it to the base URL instead, which 404'd
on every one of I-CARE's 607 records because they live in per-patient subdirectories
(`training/0284/...`). A flat collection would have hidden this bug indefinitely.

This test pins the URL construction without touching the network.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

import bsde.ingestion.physionet_wfdb as W

HEA = """0284_010_012_EEG 19 500 1000
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 Fp1
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 Fp2
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 F3
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 F4
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 C3
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 C4
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 P3
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 P4
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 O1
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 O2
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 F7
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 F8
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 T3
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 T4
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 T5
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 T6
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 Fz
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 Cz
0284_010_012_EEG.mat 16 1000/uV 0 0 0 0 0 Pz
"""


def _capture_urls(monkeypatch):
    seen = []

    def fake_fetch(url, timeout=120.0):
        seen.append(url)
        if url.endswith(".hea"):
            return HEA.encode()
        raise AssertionError(f"unexpected non-header fetch: {url}")

    monkeypatch.setattr(W, "_fetch_whole", fake_fetch)
    return seen


def test_signal_url_is_resolved_beside_the_header_not_at_the_base(monkeypatch):
    seen = _capture_urls(monkeypatch)
    with pytest.raises(AssertionError):          # stops at the signal fetch, which is what we inspect
        W.read_wfdb_window_http("https://example.org/files/i-care/2.1/",
                                "training/0284/0284_010_012_EEG", window_s=1.0)
    assert seen[0] == "https://example.org/files/i-care/2.1/training/0284/0284_010_012_EEG.hea"


def test_the_signal_fetch_would_target_the_records_own_directory(monkeypatch):
    tried = []

    def fake_fetch(url, timeout=120.0):
        tried.append(url)
        if url.endswith(".hea"):
            return HEA.encode()
        raise RuntimeError("stop-here")

    monkeypatch.setattr(W, "_fetch_whole", fake_fetch)
    with pytest.raises(RuntimeError, match="stop-here"):
        W.read_wfdb_window_http("https://example.org/files/i-care/2.1/",
                                "training/0284/0284_010_012_EEG", window_s=1.0)
    sig = tried[-1]
    assert sig == ("https://example.org/files/i-care/2.1/training/0284/0284_010_012_EEG.mat"), sig
    assert "2.1/0284_010_012_EEG.mat" not in sig, "must not drop the per-patient directory"


def test_a_flat_record_name_still_resolves_against_the_base(monkeypatch):
    """The pre-existing flat layout must keep working -- the fix must not require a subdirectory."""
    tried = []

    def fake_fetch(url, timeout=120.0):
        tried.append(url)
        if url.endswith(".hea"):
            return HEA.encode()
        raise RuntimeError("stop-here")

    monkeypatch.setattr(W, "_fetch_whole", fake_fetch)
    with pytest.raises(RuntimeError, match="stop-here"):
        W.read_wfdb_window_http("https://example.org/db/", "0284_010_012_EEG", window_s=1.0)
    assert tried[-1] == "https://example.org/db/0284_010_012_EEG.mat", tried[-1]
    assert "//" not in tried[-1].split("://", 1)[1], "no doubled slash"
