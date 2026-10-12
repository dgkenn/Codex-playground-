"""Tests for the three network-streaming adapters (http_edf, physionet_wfdb, openneuro_s3).

Offline tests -- built from synthetic bytes / hand-written XML -- are the ones that matter and must always
run. They exercise the EDF header/sample decoding and the S3 XML listing against KNOWN ground truth, with a
deliberately asymmetric physical/digital range so an implementation that ignores the digital offset (only
applies a scale factor) is caught.

Network tests hit real remote hosts and are gated behind `BSDE_NETWORK_TESTS` so a slow or unavailable
network never breaks the default suite."""
import io
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.ingestion.base import to_microvolts
from bsde.ingestion.http_edf import (
    HttpEDFAdapter,
    decode_edf_window,
    parse_edf_header,
    read_edf_window_http,
    supports_range,
)
from bsde.ingestion.physionet_wfdb import (
    PhysioNetWFDBAdapter,
    _decode_dat_window,
    parse_hea,
)
from bsde.ingestion import openneuro_s3
from bsde.ingestion.openneuro_s3 import (
    OpenNeuroS3Adapter,
    list_all_keys,
    parse_list_objects_v2_xml,
    subject_from_bids_key,
)

NETWORK = pytest.mark.skipif(
    not os.environ.get("BSDE_NETWORK_TESTS"),
    reason="network tests disabled by default; set BSDE_NETWORK_TESTS=1 to enable",
)


# --------------------------------------------------------------------------------------------------------
# Synthetic EDF byte builder
# --------------------------------------------------------------------------------------------------------

def _field(value, width: int) -> bytes:
    s = str(value)
    if len(s) > width:
        raise ValueError(f"{value!r} does not fit in a {width}-byte EDF field")
    return s.ljust(width).encode("ascii")


def _blockify(values, width: int) -> bytes:
    return b"".join(_field(v, width) for v in values)


def build_edf_bytes(channels, n_records: int = 1, rec_dur: float = 1.0):
    """Build a synthetic, spec-layout EDF header + data section from a list of channel dicts, each with
    label/phys_dim/phys_min/phys_max/dig_min/dig_max/nsamp/digital_value. All samples of a channel across
    every record carry the same `digital_value`, i.e. a known constant signal.

    Returns (main_header: bytes, signal_headers: bytes, data_bytes: bytes).
    """
    ns = len(channels)
    main_header = (
        _field("0", 8)
        + _field("test_patient", 80)
        + _field("test_recording", 80)
        + _field("01.01.01", 8)
        + _field("00.00.00", 8)
        + _field(256 + ns * 256, 8)
        + _field("", 44)
        + _field(n_records, 8)
        + _field(rec_dur, 8)
        + _field(ns, 4)
    )
    assert len(main_header) == 256

    signal_headers = (
        _blockify([c["label"] for c in channels], 16)
        + _blockify(["transducer"] * ns, 80)
        + _blockify([c["phys_dim"] for c in channels], 8)
        + _blockify([c["phys_min"] for c in channels], 8)
        + _blockify([c["phys_max"] for c in channels], 8)
        + _blockify([c["dig_min"] for c in channels], 8)
        + _blockify([c["dig_max"] for c in channels], 8)
        + _blockify([""] * ns, 80)
        + _blockify([c["nsamp"] for c in channels], 8)
        + _blockify([""] * ns, 32)
    )
    assert len(signal_headers) == ns * 256

    data = bytearray()
    for _ in range(n_records):
        for c in channels:
            vals = np.full(c["nsamp"], c["digital_value"], dtype="<i2")
            data += vals.tobytes()
    return main_header, signal_headers, bytes(data)


# --------------------------------------------------------------------------------------------------------
# EDF header + sample decoding, against known ground truth (asymmetric physical vs digital range)
# --------------------------------------------------------------------------------------------------------

def test_edf_decode_applies_asymmetric_scale_and_offset_correctly():
    # phys range [-100, 300], digital range [-2048, 2047]: NOT symmetric with each other, so an
    # implementation that applies only a scale factor (ignoring phys_min / dig_min offsets) fails this.
    channels = [
        {"label": "C3", "phys_dim": "uV", "phys_min": -100.0, "phys_max": 300.0,
         "dig_min": -2048, "dig_max": 2047, "nsamp": 4, "digital_value": -2048},  # == dig_min -> phys_min
        {"label": "C4", "phys_dim": "uV", "phys_min": -100.0, "phys_max": 300.0,
         "dig_min": -2048, "dig_max": 2047, "nsamp": 4, "digital_value": 2047},   # == dig_max -> phys_max
    ]
    main_header, signal_headers, data_bytes = build_edf_bytes(channels, n_records=2, rec_dur=1.0)

    data, ch_names, sfreq, meta = decode_edf_window(main_header, signal_headers, data_bytes, skip_records=0)

    assert ch_names == ["C3", "C4"]
    assert sfreq == pytest.approx(4.0)  # nsamp(4) / rec_dur(1.0)
    assert data.shape == (2, 8)  # 2 records * 4 samples
    # ground truth: digital_value == dig_min maps to EXACTLY phys_min, dig_max maps to EXACTLY phys_max --
    # true regardless of gain, since it is the definition of the two range endpoints.
    assert np.allclose(data[0], -100.0, atol=1e-6)
    assert np.allclose(data[1], 300.0, atol=1e-6)


def test_edf_decode_reads_the_correct_number_of_signals_and_records():
    channels = [
        {"label": f"CH{i}", "phys_dim": "uV", "phys_min": -50.0, "phys_max": 50.0,
         "dig_min": -100, "dig_max": 100, "nsamp": 2, "digital_value": 0}
        for i in range(3)
    ]
    main_header, signal_headers, data_bytes = build_edf_bytes(channels, n_records=5, rec_dur=0.5)
    meta = parse_edf_header(main_header, signal_headers)
    assert meta["n_signals"] == 3
    assert meta["n_records"] == 5
    assert meta["record_duration"] == pytest.approx(0.5)
    assert meta["data_offset"] == 256 + 3 * 256

    data, ch_names, sfreq, _ = decode_edf_window(main_header, signal_headers, data_bytes, skip_records=0)
    assert len(ch_names) == 3
    assert sfreq == pytest.approx(2 / 0.5)  # nsamp / rec_dur
    assert data.shape == (3, 10)  # 5 records * 2 samples


def test_edf_decode_converts_millivolts_to_microvolts():
    # digital_value == dig_min -> physical == phys_min == -1.0 mV == -1000 uV exactly.
    channels = [{"label": "Fp1", "phys_dim": "mV", "phys_min": -1.0, "phys_max": 1.0,
                 "dig_min": -2048, "dig_max": 2047, "nsamp": 4, "digital_value": -2048}]
    main_header, signal_headers, data_bytes = build_edf_bytes(channels, n_records=1, rec_dur=1.0)

    data, ch_names, sfreq, meta = decode_edf_window(main_header, signal_headers, data_bytes, skip_records=0)

    assert np.allclose(data[0], -1000.0, atol=1e-6)
    assert meta["source_units"] == "microvolts"


@pytest.mark.parametrize("bad_dim", ["", "???", "furlongs"])
def test_edf_decode_raises_on_blank_or_unrecognised_physical_dimension(bad_dim):
    channels = [{"label": "Fp1", "phys_dim": bad_dim, "phys_min": -1.0, "phys_max": 1.0,
                 "dig_min": -10, "dig_max": 10, "nsamp": 2, "digital_value": 0}]
    main_header, signal_headers, data_bytes = build_edf_bytes(channels, n_records=1, rec_dur=1.0)
    with pytest.raises(ValueError):
        decode_edf_window(main_header, signal_headers, data_bytes, skip_records=0)


def test_edf_header_parse_rejects_truncated_bytes():
    with pytest.raises(ValueError):
        parse_edf_header(b"short", b"")


# --------------------------------------------------------------------------------------------------------
# HttpEDFAdapter: recording_id / listing behaviour (no network)
# --------------------------------------------------------------------------------------------------------

def test_http_edf_adapter_recording_id_is_basename_without_extension_and_stable_order():
    urls = [
        "https://example.org/data/b_recording.edf",
        "https://example.org/data/a_recording.edf",
    ]
    adapter = HttpEDFAdapter(urls, dataset="demo")
    refs = adapter.list_recordings()
    assert [r.recording_id for r in refs] == ["a_recording", "b_recording"]  # sorted, not input order
    assert [r.dataset for r in refs] == ["demo", "demo"]
    # default subject == recording_id (no subject_from_url given)
    assert refs[0].subject == "a_recording"


def test_http_edf_adapter_uses_subject_from_url_when_given():
    urls = ["https://example.org/sub-01/run-1_eeg.edf", "https://example.org/sub-01/run-2_eeg.edf"]
    adapter = HttpEDFAdapter(urls, dataset="demo", subject_from_url=lambda u: u.split("/")[-2])
    refs = adapter.list_recordings()
    assert all(r.subject == "sub-01" for r in refs)
    assert refs[0].recording_id != refs[1].recording_id  # still distinct per-recording


# --------------------------------------------------------------------------------------------------------
# supports_range: HEAD-based check, network mocked out
# --------------------------------------------------------------------------------------------------------

class _FakeHeadResponse:
    def __init__(self, headers):
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_supports_range_true_when_header_present(monkeypatch):
    import bsde.ingestion.http_edf as http_edf_mod

    monkeypatch.setattr(http_edf_mod, "_urlopen",
                         lambda req, timeout=20.0: _FakeHeadResponse({"Accept-Ranges": "bytes"}))
    assert supports_range("https://example.org/x.edf") is True


def test_supports_range_false_when_header_absent(monkeypatch):
    import bsde.ingestion.http_edf as http_edf_mod

    monkeypatch.setattr(http_edf_mod, "_urlopen", lambda req, timeout=20.0: _FakeHeadResponse({}))
    assert supports_range("https://example.org/x.edf") is False


def test_supports_range_false_on_request_failure(monkeypatch):
    import urllib.error

    import bsde.ingestion.http_edf as http_edf_mod

    def _boom(req, timeout=20.0):
        raise urllib.error.URLError("nope")

    monkeypatch.setattr(http_edf_mod, "_urlopen", _boom)
    assert supports_range("https://example.org/x.edf") is False


# --------------------------------------------------------------------------------------------------------
# WFDB header parsing (parse_hea), lifted from analysis/icare_bs_burden.py
# --------------------------------------------------------------------------------------------------------

def test_parse_hea_reads_fs_gains_baselines_units_and_files():
    text = (
        "record_x 2 250 25000\n"
        "record_x.dat 16 200(0)/uV 12 0 0 0 0 Fp1\n"
        "record_x.dat 16 200(0)/uV 12 0 0 0 0 Fp2\n"
    )
    hdr = parse_hea(text)
    assert hdr["nsig"] == 2
    assert hdr["fs"] == pytest.approx(250.0)
    assert hdr["n_samples"] == 25000
    assert hdr["gains"] == [pytest.approx(200.0), pytest.approx(200.0)]
    assert hdr["bases"] == [pytest.approx(0.0), pytest.approx(0.0)]
    assert hdr["units"] == ["uV", "uV"]
    assert hdr["names"] == ["Fp1", "Fp2"]
    assert hdr["files"] == ["record_x.dat", "record_x.dat"]
    assert hdr["fmts"] == ["16", "16"]


def test_parse_hea_handles_nonzero_baseline_and_missing_nsamples():
    text = (
        "rec 1 500\n"
        "rec.dat 16 100(50)/mV 12 50 0 0 0 EEG1\n"
    )
    hdr = parse_hea(text)
    assert hdr["n_samples"] is None
    assert hdr["gains"] == [pytest.approx(100.0)]
    assert hdr["bases"] == [pytest.approx(50.0)]
    assert hdr["units"] == ["mV"]


def test_decode_dat_window_applies_gain_and_baseline():
    # frame layout: 2 channels, format 16, gain=10 baseline=100 for channel 0, gain=1 baseline=0 for ch1.
    frames = [(100, 0), (200, 5), (300, -5)]  # (ch0 raw, ch1 raw) per frame
    raw = b"".join(struct.pack("<2h", a, b) for a, b in frames)
    out = _decode_dat_window(raw, nsig=2, gains=[10.0, 1.0], bases=[100.0, 0.0], fmt="16")
    assert out.shape == (2, 3)
    assert np.allclose(out[0], [(100 - 100) / 10.0, (200 - 100) / 10.0, (300 - 100) / 10.0])
    assert np.allclose(out[1], [0.0, 5.0, -5.0])


def test_decode_dat_window_raises_on_unsupported_format():
    with pytest.raises(NotImplementedError):
        _decode_dat_window(b"\x00" * 8, nsig=1, gains=[1.0], bases=[0.0], fmt="212")


def test_physionet_wfdb_adapter_recording_id_is_the_record_name_itself():
    adapter = PhysioNetWFDBAdapter(
        base_url="https://physionet.org/files/demo/1.0.0",
        record_names=["p02/rec2", "p01/rec1"],
        dataset="demo",
    )
    refs = adapter.list_recordings()
    assert [r.recording_id for r in refs] == ["p01/rec1", "p02/rec2"]  # sorted, deterministic
    assert refs[0].subject == "p01/rec1"  # default subject == recording_id


def test_physionet_wfdb_adapter_uses_subject_from_record_when_given():
    adapter = PhysioNetWFDBAdapter(
        base_url="https://physionet.org/files/demo/1.0.0",
        record_names=["p01/rec1", "p01/rec2"],
        dataset="demo",
        subject_from_record=lambda r: r.split("/")[0],
    )
    refs = adapter.list_recordings()
    assert all(r.subject == "p01" for r in refs)


# --------------------------------------------------------------------------------------------------------
# OpenNeuro S3 ListObjectsV2 XML parsing (hand-written fixtures, no network)
# --------------------------------------------------------------------------------------------------------

_PAGE_1 = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>openneuro.org</Name>
  <Prefix>ds005620/</Prefix>
  <IsTruncated>true</IsTruncated>
  <NextContinuationToken>TOKEN123</NextContinuationToken>
  <Contents><Key>ds005620/sub-01/ses-01/eeg/sub-01_ses-01_task-rest_eeg.edf</Key></Contents>
  <Contents><Key>ds005620/sub-01/ses-01/eeg/sub-01_ses-01_task-rest_channels.tsv</Key></Contents>
</ListBucketResult>
"""

_PAGE_2 = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>openneuro.org</Name>
  <IsTruncated>false</IsTruncated>
  <Contents><Key>ds005620/sub-02/ses-01/eeg/sub-02_ses-01_task-rest_eeg.edf</Key></Contents>
</ListBucketResult>
"""


def test_parse_list_objects_v2_xml_single_page():
    keys, token, truncated = parse_list_objects_v2_xml(_PAGE_1)
    assert keys == [
        "ds005620/sub-01/ses-01/eeg/sub-01_ses-01_task-rest_eeg.edf",
        "ds005620/sub-01/ses-01/eeg/sub-01_ses-01_task-rest_channels.tsv",
    ]
    assert token == "TOKEN123"
    assert truncated is True


def test_parse_list_objects_v2_xml_last_page_has_no_token():
    keys, token, truncated = parse_list_objects_v2_xml(_PAGE_2)
    assert keys == ["ds005620/sub-02/ses-01/eeg/sub-02_ses-01_task-rest_eeg.edf"]
    assert token is None
    assert truncated is False


def test_list_all_keys_follows_continuation_token_across_two_pages(monkeypatch):
    calls = []

    def fake_fetch(bucket, prefix, continuation_token=None, endpoint=None, timeout=30.0):
        calls.append(continuation_token)
        if continuation_token is None:
            return _PAGE_1
        assert continuation_token == "TOKEN123"
        return _PAGE_2

    monkeypatch.setattr(openneuro_s3, "_fetch_listing_page", fake_fetch)
    keys = list_all_keys("openneuro.org", "ds005620/")

    assert len(keys) == 3, "both pages' keys must be returned"
    assert calls == [None, "TOKEN123"], "must follow the continuation token, not just call once"
    edf_keys = [k for k in keys if k.endswith("_eeg.edf")]
    assert len(edf_keys) == 2, "suffix filtering must not drop either page's .edf key"


def test_subject_from_bids_key_extracts_sub_entity():
    key = "ds005620/sub-03/ses-01/eeg/sub-03_ses-01_task-rest_eeg.edf"
    assert subject_from_bids_key(key) == "sub-03"


def test_subject_from_bids_key_raises_when_absent():
    with pytest.raises(ValueError):
        subject_from_bids_key("ds005620/dataset_description.json")


def test_openneuro_adapter_derives_subject_from_bids_path_never_recording_id(monkeypatch):
    keys = [
        "ds005620/sub-02/ses-01/eeg/sub-02_ses-01_task-rest_eeg.edf",
        "ds005620/sub-01/ses-02/eeg/sub-01_ses-02_task-rest_eeg.edf",
        "ds005620/sub-01/ses-01/eeg/sub-01_ses-01_task-rest_eeg.edf",
    ]
    monkeypatch.setattr(openneuro_s3, "list_all_keys", lambda bucket, prefix: keys)

    adapter = OpenNeuroS3Adapter(accession="ds005620")
    refs = adapter.list_recordings()

    assert [r.recording_id for r in refs] == sorted(keys)  # deterministic, not S3 listing order
    by_id = {r.recording_id: r for r in refs}
    # two DIFFERENT recordings (different sessions) for the SAME subject must share `subject`
    r1 = by_id["ds005620/sub-01/ses-01/eeg/sub-01_ses-01_task-rest_eeg.edf"]
    r2 = by_id["ds005620/sub-01/ses-02/eeg/sub-01_ses-02_task-rest_eeg.edf"]
    assert r1.subject == r2.subject == "sub-01"
    assert r1.recording_id != r2.recording_id, "recording_id must still distinguish the two sessions"


# --------------------------------------------------------------------------------------------------------
# Network tests -- real remote hosts, opt-in only
# --------------------------------------------------------------------------------------------------------

@NETWORK
def test_network_real_range_request_against_physionet_chbmit():
    """CHB-MIT scalp EEG on PhysioNet is public and served with Accept-Ranges: bytes; fetch a small window
    of a ~42 MB file and check only a small byte span was actually transferred worth of samples decoded."""
    url = "https://physionet.org/files/chbmit/1.0.0/chb01/chb01_01.edf"
    assert supports_range(url) is True
    data, ch_names, sfreq, meta = read_edf_window_http(url, window_s=5.0, start_seconds=10.0)
    assert data.shape[0] == len(ch_names) > 0
    assert sfreq > 0
    assert meta["got_records"] * meta["record_duration"] <= 6.0  # only ~5s worth of records fetched


@NETWORK
def test_network_openneuro_listing_returns_real_keys():
    keys = list_all_keys("openneuro.org", "ds002718/sub-002/")
    assert any(k.endswith(".json") or k.endswith(".tsv") or k.endswith(".edf") for k in keys)
