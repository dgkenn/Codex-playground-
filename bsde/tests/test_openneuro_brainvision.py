"""Tests for the OpenNeuro BrainVision streaming adapter (`.vhdr`/`.eeg` over public S3 HTTPS).

Offline tests -- built from a hand-written `.vhdr` string and synthetic binary bytes -- are the ones that
matter and must always run. They pin the header parse against known ground truth (including the
microsecond-to-Hz conversion, empty resolution/unit defaults, and BOM/CRLF handling) and the sample decode
against a KNOWN round-trip with deliberately DIFFERENT per-channel resolutions and units, so an
implementation that applies one global scale factor is caught.

Network tests hit the real OpenNeuro S3 mirror and are gated behind `BSDE_NETWORK_TESTS` so a slow or
unavailable network never breaks the default suite.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.ingestion.openneuro_brainvision import (
    OpenNeuroBrainVisionAdapter,
    _bids_entities,
    decode_brainvision_window,
    parse_vhdr,
    read_brainvision_window_http,
)

NETWORK = pytest.mark.skipif(
    not os.environ.get("BSDE_NETWORK_TESTS"),
    reason="network tests disabled by default; set BSDE_NETWORK_TESTS=1 to enable",
)


# --------------------------------------------------------------------------------------------------------
# Hand-written .vhdr fixtures
# --------------------------------------------------------------------------------------------------------

_BASE_VHDR = """Brain Vision Data Exchange Header File Version 1.0
; Data created by some exporter

[Common Infos]
Codepage=UTF-8
DataFile=sub-1010_task-awake_acq-EC_eeg.eeg
MarkerFile=sub-1010_task-awake_acq-EC_eeg.vmrk
DataFormat=BINARY
DataOrientation=MULTIPLEXED
NumberOfChannels=3
SamplingInterval=4000

[Binary Infos]
BinaryFormat=INT_16

[Channel Infos]
; Ch<N>=<Name>,<Reference channel name>,<Resolution in "Unit">,<Unit>
Ch1=Fp1,,0.1,µV
Ch2=Fp2,,0.5,mV
Ch3=Cz,,,
"""


def test_parse_vhdr_derives_sfreq_from_sampling_interval_microseconds():
    header = parse_vhdr(_BASE_VHDR)
    assert header["sfreq"] == pytest.approx(250.0)  # 1e6 / 4000
    assert header["n_channels"] == 3
    assert header["data_file"] == "sub-1010_task-awake_acq-EC_eeg.eeg"
    assert header["marker_file"] == "sub-1010_task-awake_acq-EC_eeg.vmrk"
    assert header["binary_format"] == "INT_16"
    assert header["data_orientation"] == "MULTIPLEXED"
    assert header["ch_names"] == ["Fp1", "Fp2", "Cz"]


def test_parse_vhdr_reads_per_channel_resolutions_and_units():
    header = parse_vhdr(_BASE_VHDR)
    assert header["resolutions"] == [pytest.approx(0.1), pytest.approx(0.5), pytest.approx(1.0)]
    assert header["units"][0] == "µV"
    assert header["units"][1] == "mV"


def test_parse_vhdr_empty_resolution_defaults_to_one():
    header = parse_vhdr(_BASE_VHDR)
    assert header["resolutions"][2] == pytest.approx(1.0)  # Ch3's resolution field is empty


def test_parse_vhdr_empty_unit_defaults_to_microvolts():
    header = parse_vhdr(_BASE_VHDR)
    assert header["units"][2] == "µV"  # Ch3's unit field is empty


def test_parse_vhdr_with_bom_matches_plain_version():
    with_bom = "﻿" + _BASE_VHDR
    header_bom = parse_vhdr(with_bom)
    header_plain = parse_vhdr(_BASE_VHDR)
    assert header_bom == header_plain


def test_parse_vhdr_with_crlf_matches_plain_version():
    with_crlf = _BASE_VHDR.replace("\n", "\r\n")
    header_crlf = parse_vhdr(with_crlf)
    header_plain = parse_vhdr(_BASE_VHDR)
    assert header_crlf == header_plain


# --------------------------------------------------------------------------------------------------------
# decode_brainvision_window: known round-trip, DIFFERENT resolutions/units per channel
# --------------------------------------------------------------------------------------------------------

def _build_multiplexed_int16(per_channel_values, n_frames):
    """Interleave `n_frames` identical frames of `per_channel_values` (one int16 per channel) MULTIPLEXED."""
    n_channels = len(per_channel_values)
    frame = struct.pack(f"<{n_channels}h", *per_channel_values)
    return frame * n_frames


def test_decode_brainvision_window_applies_per_channel_resolution_and_unit():
    # 3 channels, DIFFERENT resolutions (0.1, 0.5, 1.0) and DIFFERENT units (uV, mV, uV) -- an
    # implementation that applies one global scale factor fails this.
    raw_digital = [100, 20, -50]  # int16 raw values
    raw = _build_multiplexed_int16(raw_digital, n_frames=4)
    resolutions = [0.1, 0.5, 1.0]
    units = ["uV", "mV", "uV"]

    data = decode_brainvision_window(
        raw, n_channels=3, binary_format="INT_16", data_orientation="MULTIPLEXED",
        resolutions=resolutions, units=units)

    assert data.shape == (3, 4)
    # ch0: 100 * 0.1 uV = 10.0 uV
    assert np.allclose(data[0], 10.0, atol=1e-9)
    # ch1: 20 * 0.5 = 10.0 mV = 10000.0 uV  (mV -> uV factor 1000)
    assert np.allclose(data[1], 10000.0, atol=1e-9)
    # ch2: -50 * 1.0 = -50.0 uV
    assert np.allclose(data[2], -50.0, atol=1e-9)


def test_decode_brainvision_window_mv_channel_is_1000x_identical_uv_channel():
    # Same raw digital value and same resolution, differing only in declared unit.
    raw_digital = [42, 42]
    raw = _build_multiplexed_int16(raw_digital, n_frames=1)
    data = decode_brainvision_window(
        raw, n_channels=2, binary_format="INT_16", data_orientation="MULTIPLEXED",
        resolutions=[1.0, 1.0], units=["uV", "mV"])
    assert data[1, 0] == pytest.approx(1000.0 * data[0, 0])


def test_decode_brainvision_window_ieee_float32():
    values = [1.5, -2.25]
    raw = struct.pack("<2f", *values)
    data = decode_brainvision_window(
        raw, n_channels=2, binary_format="IEEE_FLOAT_32", data_orientation="MULTIPLEXED",
        resolutions=[1.0, 1.0], units=["uV", "uV"])
    assert data.shape == (2, 1)
    assert data[0, 0] == pytest.approx(1.5)
    assert data[1, 0] == pytest.approx(-2.25)


def test_decode_brainvision_window_unsupported_format_raises():
    raw = b"\x00" * 16
    with pytest.raises(NotImplementedError):
        decode_brainvision_window(
            raw, n_channels=2, binary_format="UINT_32", data_orientation="MULTIPLEXED",
            resolutions=[1.0, 1.0], units=["uV", "uV"])


def test_decode_brainvision_window_vectorized_raises_with_explanation():
    raw = b"\x00" * 16
    with pytest.raises(NotImplementedError) as excinfo:
        decode_brainvision_window(
            raw, n_channels=2, binary_format="INT_16", data_orientation="VECTORIZED",
            resolutions=[1.0, 1.0], units=["uV", "uV"])
    msg = str(excinfo.value).lower()
    assert "vectorized" in msg
    assert "contiguous" in msg or "byte range" in msg or "byte-range" in msg


# --------------------------------------------------------------------------------------------------------
# BIDS entity extraction
# --------------------------------------------------------------------------------------------------------

def test_bids_entities_extracts_task_acq_run():
    key = "ds005620/sub-1010/eeg/sub-1010_task-sed2_acq-rest_run-1_eeg.vhdr"
    entities = _bids_entities(key)
    assert entities == {"task": "sed2", "acq": "rest", "run": "1"}


def test_bids_entities_missing_run_is_absent_not_defaulted():
    key = "ds005620/sub-02/eeg/sub-02_task-awake_acq-EO_eeg.vhdr"
    entities = _bids_entities(key)
    assert entities == {"task": "awake", "acq": "EO"}
    assert "run" not in entities


# --------------------------------------------------------------------------------------------------------
# OpenNeuroBrainVisionAdapter: listing / recording_id / subject (no network)
# --------------------------------------------------------------------------------------------------------

def test_adapter_lists_vhdr_keys_in_sorted_order_with_subject_and_meta(monkeypatch):
    keys = [
        "ds005620/sub-1010/eeg/sub-1010_task-sed2_acq-rest_run-1_eeg.vhdr",
        "ds005620/sub-1010/eeg/sub-1010_task-awake_acq-EC_eeg.vhdr",
        "ds005620/sub-1010/eeg/sub-1010_task-awake_acq-EC_eeg.vmrk",  # not a .vhdr -- must be filtered out
        "ds005620/sub-1005/eeg/sub-1005_task-awake_acq-EC_eeg.vhdr",
    ]
    import bsde.ingestion.openneuro_brainvision as mod
    monkeypatch.setattr(mod, "list_all_keys", lambda bucket, prefix: keys)

    adapter = OpenNeuroBrainVisionAdapter(accession="ds005620")
    refs = adapter.list_recordings()

    vhdr_keys = [k for k in keys if k.endswith(".vhdr")]
    assert [r.recording_id for r in refs] == sorted(vhdr_keys)  # deterministic, not listing order

    by_id = {r.recording_id: r for r in refs}
    awake = by_id["ds005620/sub-1010/eeg/sub-1010_task-awake_acq-EC_eeg.vhdr"]
    sed2 = by_id["ds005620/sub-1010/eeg/sub-1010_task-sed2_acq-rest_run-1_eeg.vhdr"]

    assert awake.subject == "sub-1010"
    assert sed2.subject == "sub-1010"
    assert by_id["ds005620/sub-1005/eeg/sub-1005_task-awake_acq-EC_eeg.vhdr"].subject == "sub-1005"

    assert awake.meta["task"] == "awake"
    assert awake.meta["acq"] == "EC"
    assert sed2.meta["task"] == "sed2"
    assert sed2.meta["acq"] == "rest"
    assert sed2.meta["run"] == "1"


def test_adapter_recording_id_is_full_key_never_an_enumeration_index(monkeypatch):
    keys = [
        "ds005620/sub-02/eeg/sub-02_task-awake_acq-EC_eeg.vhdr",
        "ds005620/sub-01/eeg/sub-01_task-awake_acq-EC_eeg.vhdr",
    ]
    import bsde.ingestion.openneuro_brainvision as mod
    monkeypatch.setattr(mod, "list_all_keys", lambda bucket, prefix: keys)

    adapter = OpenNeuroBrainVisionAdapter(accession="ds005620")
    refs = adapter.list_recordings()
    assert refs[0].recording_id == "ds005620/sub-01/eeg/sub-01_task-awake_acq-EC_eeg.vhdr"
    assert refs[1].recording_id == "ds005620/sub-02/eeg/sub-02_task-awake_acq-EC_eeg.vhdr"


# --------------------------------------------------------------------------------------------------------
# read_brainvision_window_http: network mocked out at the byte-range/urlopen layer
# --------------------------------------------------------------------------------------------------------

class _FakeVhdrResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_read_brainvision_window_http_issues_one_range_get_and_decodes(monkeypatch):
    import bsde.ingestion.openneuro_brainvision as mod

    vhdr_url = "https://s3.amazonaws.com/openneuro.org/ds005620/sub-1010/eeg/sub-1010_task-awake_acq-EC_eeg.vhdr"

    monkeypatch.setattr(mod, "_urlopen", lambda req, timeout=60.0: _FakeVhdrResponse(_BASE_VHDR.encode("utf-8")))

    calls = []

    def fake_range(url, start, length, timeout=60.0):
        calls.append((url, start, length))
        n_frames = 5
        # 3 channels' worth of a constant frame, repeated n_frames times
        return _build_multiplexed_int16([10, 20, 30], n_frames=n_frames)

    monkeypatch.setattr(mod, "_http_get_range", fake_range)

    data, ch_names, sfreq, meta = read_brainvision_window_http(vhdr_url, window_s=0.02, start_seconds=0.0)

    assert len(calls) == 1, "must issue exactly ONE range GET against the binary file"
    called_url, start, length = calls[0]
    assert called_url == "https://s3.amazonaws.com/openneuro.org/ds005620/sub-1010/eeg/sub-1010_task-awake_acq-EC_eeg.eeg"
    assert ch_names == ["Fp1", "Fp2", "Cz"]
    assert sfreq == pytest.approx(250.0)
    assert data.shape[0] == 3
    assert meta["binary_format"] == "INT_16"
    assert meta["data_orientation"] == "MULTIPLEXED"
    assert meta["bytes_fetched"] == len(_build_multiplexed_int16([10, 20, 30], n_frames=5))
    # ch0 resolution 0.1 uV -> 10 * 0.1 = 1.0 uV
    assert np.allclose(data[0], 1.0, atol=1e-9)


# --------------------------------------------------------------------------------------------------------
# Network tests -- real remote host, opt-in only
# --------------------------------------------------------------------------------------------------------

@NETWORK
def test_network_real_brainvision_window_from_openneuro_ds005620():
    url = "https://s3.amazonaws.com/openneuro.org/ds005620/sub-1010/eeg/sub-1010_task-awake_acq-EC_eeg.vhdr"
    data, ch_names, sfreq, meta = read_brainvision_window_http(url, window_s=60.0)
    assert data.shape[0] == len(ch_names) > 0
    assert sfreq > 0
    assert meta["bytes_fetched"] > 0
    # Physiologically plausible scalp EEG amplitude in microvolts. Raw per-channel DC offsets differ (this
    # is an unfiltered stream, not baseline-corrected), which inflates the POOLED std across channels well
    # past any single channel's physiological range -- so amplitude is judged per channel, after removing
    # each channel's own mean, which is the quantity that actually reflects EEG activity.
    demeaned = data - data.mean(axis=1, keepdims=True)
    assert 5.0 < float(demeaned.std()) < 300.0
    assert 5.0 < float(np.median(demeaned.std(axis=1))) < 300.0


@NETWORK
def test_network_openneuro_brainvision_adapter_lists_real_ds005620_recordings():
    adapter = OpenNeuroBrainVisionAdapter(accession="ds005620")
    refs = adapter.list_recordings()
    assert len(refs) > 0
    assert all(r.recording_id.endswith("_eeg.vhdr") for r in refs)
    assert all(r.subject.startswith("sub-") for r in refs)
