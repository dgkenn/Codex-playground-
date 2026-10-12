"""Tests for `remote_zip.py` (generic remote-ZIP reader) and `chennu.py` (the EEGLAB adapter built on it).

Offline tests -- a real small ZIP built in-memory with Python's own `zipfile`, and hand-built `.fdt` bytes
-- are the ones that matter and must always run. `read_member`'s network layer is exercised by
monkeypatching `remote_zip._http_get_range` to slice a fully in-memory archive, so the ZIP-format logic
(central directory parsing, local-header offset correction, prefix-only deflate decoding) is tested end to
end with no network involved.

Network tests hit the real Chennu archive and are gated behind `BSDE_NETWORK_TESTS`, matching
`test_ingestion_adapters.py`.
"""
import io
import os
import struct
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.ingestion import remote_zip
from bsde.ingestion.chennu import (
    CHENNU_ARCHIVE_URL,
    ChennuRemoteZipAdapter,
    _is_matlab_v73,
    _load_labels,
    _subject_from_dataset_name,
    decode_fdt,
    parse_eeglab_set,
)
from bsde.ingestion.remote_zip import (
    RemoteZip,
    _ZIP64_EOCD_LOCATOR_SIG,
    parse_central_directory,
    parse_eocd,
)

NETWORK = pytest.mark.skipif(
    not os.environ.get("BSDE_NETWORK_TESTS"),
    reason="network tests disabled by default; set BSDE_NETWORK_TESTS=1 to enable",
)

REAL_LABELS_CSV = os.path.join(os.path.dirname(__file__), "..", "results", "chennu_labels.csv")


# --------------------------------------------------------------------------------------------------------
# A real, small, synthetic ZIP built with Python's own zipfile module
# --------------------------------------------------------------------------------------------------------

def _build_test_zip():
    """Returns (zip_bytes, contents) where `contents` maps member name -> the plaintext bytes written.

    Includes: a member with a SPACE in its name, a `__MACOSX/` member that must be skipped from `index()`,
    and one larger, highly compressible member to exercise prefix-window decoding meaningfully.
    """
    # Deterministic pseudo-random bytes (NOT a repeating pattern) for the .fdt stand-in, so its compressed
    # size stays close to its raw size -- a highly-repetitive body would compress this whole 5 KB member
    # down to a couple dozen bytes and make "fetched less than the full compressed size" untestable.
    rng = np.random.RandomState(0)
    fdt_stub = rng.bytes(5000)
    contents = {
        "Sedation-RestingState/02-2010-anest 20100210 135.003.set": b"fake set header bytes, whatever",
        "Sedation-RestingState/02-2010-anest 20100210 135.003.fdt": fdt_stub,
        "__MACOSX/Sedation-RestingState/._02-2010-anest 20100210 135.003.set": b"resource fork junk",
        "datainfo.mat": b"pretend mat bytes",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in contents.items():
            zf.writestr(name, data)
    return buf.getvalue(), contents


@pytest.fixture
def test_zip():
    return _build_test_zip()


# --------------------------------------------------------------------------------------------------------
# parse_eocd / parse_central_directory against the real synthetic ZIP
# --------------------------------------------------------------------------------------------------------

def test_parse_eocd_and_central_directory_recover_real_members(test_zip):
    zip_bytes, contents = test_zip
    tail = zip_bytes[-70000:] if len(zip_bytes) > 70000 else zip_bytes
    eocd = parse_eocd(tail)
    assert eocd["n_entries"] == len(contents)

    cd_bytes = zip_bytes[eocd["cd_offset"]: eocd["cd_offset"] + eocd["cd_size"]]
    entries = parse_central_directory(cd_bytes)
    assert len(entries) == len(contents)

    by_name = {e["name"]: e for e in entries}
    assert set(by_name) == set(contents)

    # the member with a space in its name round-trips exactly
    space_name = "Sedation-RestingState/02-2010-anest 20100210 135.003.set"
    assert space_name in by_name
    assert by_name[space_name]["uncompress_size"] == len(contents[space_name])

    # local_header_offset points at a real local file header (signature check)
    for e in entries:
        off = e["local_header_offset"]
        assert zip_bytes[off:off + 4] == remote_zip._LOCAL_HEADER_SIG


def test_index_skips_macosx_and_ds_store(test_zip, monkeypatch):
    zip_bytes, contents = test_zip
    monkeypatch.setattr(remote_zip, "_http_get_range",
                         lambda url, start, length, timeout=None: zip_bytes[start:start + length])
    rz = RemoteZip("fake://test.zip", total_size=len(zip_bytes))
    members = rz.index()
    names = [m["name"] for m in members]
    assert not any(n.startswith("__MACOSX/") for n in names)
    assert not any(n.endswith(".DS_Store") for n in names)
    assert names == sorted(names)  # sorted == deterministic listing
    assert "Sedation-RestingState/02-2010-anest 20100210 135.003.set" in names


def test_eocd_missing_signature_raises():
    with pytest.raises(ValueError, match="EOCD"):
        parse_eocd(b"not a zip file, no signature anywhere in here")


def test_zip64_eocd_locator_raises_not_implemented(test_zip):
    zip_bytes, _contents = test_zip
    tail = zip_bytes[-70000:] if len(zip_bytes) > 70000 else zip_bytes
    # Splice a fake Zip64 EOCD locator record in just before the real EOCD signature.
    idx = tail.rfind(remote_zip._EOCD_SIG)
    fake_locator = _ZIP64_EOCD_LOCATOR_SIG + b"\x00" * 16
    poisoned = tail[:idx] + fake_locator + tail[idx:]
    with pytest.raises(NotImplementedError, match="Zip64"):
        parse_eocd(poisoned)


# --------------------------------------------------------------------------------------------------------
# read_member: prefix-only decoding over a monkeypatched network layer
# --------------------------------------------------------------------------------------------------------

def test_read_member_full_content_matches_original(test_zip, monkeypatch):
    zip_bytes, contents = test_zip
    monkeypatch.setattr(remote_zip, "_http_get_range",
                         lambda url, start, length, timeout=None: zip_bytes[start:start + length])
    rz = RemoteZip("fake://test.zip", total_size=len(zip_bytes))
    name = "Sedation-RestingState/02-2010-anest 20100210 135.003.fdt"
    got = rz.read_member(name)
    assert got == contents[name]


def test_read_member_prefix_returns_exact_prefix_and_no_more(test_zip, monkeypatch):
    zip_bytes, contents = test_zip
    monkeypatch.setattr(remote_zip, "_http_get_range",
                         lambda url, start, length, timeout=None: zip_bytes[start:start + length])
    rz = RemoteZip("fake://test.zip", total_size=len(zip_bytes))
    name = "Sedation-RestingState/02-2010-anest 20100210 135.003.fdt"
    full = contents[name]
    prefix_len = 37
    got = rz.read_member(name, max_uncompressed_bytes=prefix_len)
    assert got == full[:prefix_len]
    assert len(got) == prefix_len


def test_read_member_prefix_fetches_less_than_full_compressed_size(test_zip, monkeypatch):
    """With a small chunk size, a small prefix of a larger member should stop fetching well before the
    whole compressed stream is transferred."""
    zip_bytes, contents = test_zip
    fetch_log = []

    def fake_get_range(url, start, length, timeout=None):
        fetch_log.append(length)
        return zip_bytes[start:start + length]

    monkeypatch.setattr(remote_zip, "_http_get_range", fake_get_range)
    monkeypatch.setattr(remote_zip, "_DEFAULT_CHUNK", 64)  # force many small chunks
    rz = RemoteZip("fake://test.zip", total_size=len(zip_bytes))
    name = "Sedation-RestingState/02-2010-anest 20100210 135.003.fdt"
    full_compress_size = rz._member_by_name(name)["compress_size"]

    got = rz.read_member(name, max_uncompressed_bytes=20)
    assert got == contents[name][:20]
    assert rz.last_bytes_fetched < full_compress_size


# --------------------------------------------------------------------------------------------------------
# decode_fdt
# --------------------------------------------------------------------------------------------------------

def test_decode_fdt_roundtrip_distinct_per_channel_values():
    nbchan, pnts, trials = 4, 6, 3
    arr = np.zeros((nbchan, pnts, trials), dtype="<f4")
    for c in range(nbchan):
        arr[c, :, :] = (c + 1) * 10.0  # a DIFFERENT constant per channel -- wrong axis order fails loudly
    raw = arr.tobytes(order="F")

    decoded = decode_fdt(raw, nbchan=nbchan, pnts=pnts)
    assert decoded.shape == (nbchan, pnts * trials)
    expected = arr.reshape(nbchan, pnts * trials, order="F").astype(np.float64)
    np.testing.assert_array_equal(decoded, expected)
    for c in range(nbchan):
        assert np.all(decoded[c, :] == (c + 1) * 10.0)


def test_decode_fdt_raises_on_partial_float32():
    with pytest.raises(ValueError, match="float32"):
        decode_fdt(b"\x00" * 15, nbchan=4, pnts=6)  # 15 is not a multiple of 4


def test_decode_fdt_raises_on_partial_timepoint():
    nbchan = 4
    # 5 whole float32 values -- not a multiple of nbchan=4, so not a whole number of timepoints
    raw = np.zeros(5, dtype="<f4").tobytes()
    with pytest.raises(ValueError, match="timepoint"):
        decode_fdt(raw, nbchan=nbchan, pnts=6)


def test_decode_fdt_raises_on_partial_epoch_when_pnts_given():
    nbchan, pnts = 4, 6
    # 7 timepoints -- a whole number of nbchan-wide rows, but not a whole number of 6-sample epochs
    raw = np.zeros(nbchan * 7, dtype="<f4").tobytes(order="F")
    with pytest.raises(ValueError, match="epoch"):
        decode_fdt(raw, nbchan=nbchan, pnts=pnts)


# --------------------------------------------------------------------------------------------------------
# Label loading and subject grouping
# --------------------------------------------------------------------------------------------------------

_FAKE_LABELS_CSV = """\
# Chennu propofol sedation labels, extracted from datainfo.mat inside the remote zip via HTTP
# range requests (no download of the 3.69 GB archive, no authentication required).
# Column semantics quoted from the deposit's own description page:
#   sedation_level: 1 = baseline, 2 = mild sedation, 3 = moderate sedation, 4 = recovery
#   plasma_propofol_ug_per_L: concentration of propofol MEASURED IN BLOOD PLASMA at that level
#   mean_reaction_time_ms: average reaction time in a speeded two-choice response task
#   n_correct_of_40: number of correct responses in that task, max 40
dataset_name,sedation_level,plasma_propofol_ug_per_L,mean_reaction_time_ms,n_correct_of_40
02-2010-anest 20100210 135.003,1.0,0.0,903.0,40.0
02-2010-anest 20100210 135.006,2.0,204.0,675.0,39.0
02-2010-anest 20100210 135.014,3.0,506.0,846.0,39.0
02-2010-anest- 20100210 16.003,4.0,299.0,739.0,38.0
03-2010-anest 20100211 142.003,1.0,0.0,630.0,37.0
03-2010-anest 20100211 142.008,2.0,246.0,637.0,37.0
03-2010-anest 20100211 142.021,3.0,689.0,945.0,3.0
03-2010-anest 20100211 142.026,4.0,224.0,669.0,38.0
"""


def test_load_labels_skips_comment_lines_and_parses_fields(tmp_path):
    p = tmp_path / "fake_labels.csv"
    p.write_text(_FAKE_LABELS_CSV)
    labels = _load_labels(str(p))
    assert len(labels) == 8
    row = labels["02-2010-anest 20100210 135.003"]
    assert row["sedation_level"] == 1.0
    assert row["plasma_propofol_ug_per_L"] == 0.0
    assert row["mean_reaction_time_ms"] == 903.0
    assert row["n_correct_of_40"] == 40.0


def test_subject_grouping_puts_four_conditions_under_one_subject(tmp_path):
    p = tmp_path / "fake_labels.csv"
    p.write_text(_FAKE_LABELS_CSV)
    labels = _load_labels(str(p))
    by_subject = {}
    for name in labels:
        by_subject.setdefault(_subject_from_dataset_name(name), []).append(name)
    assert len(by_subject) == 2
    assert all(len(v) == 4 for v in by_subject.values())


@pytest.mark.skipif(not os.path.exists(REAL_LABELS_CSV), reason="results/chennu_labels.csv not present")
def test_subject_grouping_is_20x4_on_real_labels():
    labels = _load_labels(REAL_LABELS_CSV)
    assert len(labels) == 80
    by_subject = {}
    for name in labels:
        by_subject.setdefault(_subject_from_dataset_name(name), []).append(name)
    assert len(by_subject) == 20, f"expected 20 subjects, got {len(by_subject)}: {sorted(by_subject)}"
    bad = {s: len(v) for s, v in by_subject.items() if len(v) != 4}
    assert not bad, f"subjects without exactly 4 rows: {bad}"


# --------------------------------------------------------------------------------------------------------
# ChennuRemoteZipAdapter, offline: real synthetic ZIP + real fake .set built with scipy.io.savemat
# --------------------------------------------------------------------------------------------------------

def _build_fake_set_bytes(nbchan, pnts, trials, srate, ch_names, fdt_name):
    """Build real MATLAB v5 bytes for an `EEG` struct via scipy.io.savemat, close enough to a real
    EEGLAB .set to exercise `parse_eeglab_set` -- a MATLAB struct ARRAY (chanlocs) needs a numpy
    structured (record) array of dtype=object fields, not a plain python list, for savemat to write it
    as one struct per element rather than one struct with array-valued fields."""
    import scipy.io

    chanlocs = np.zeros(len(ch_names), dtype=[("labels", "O")])
    for i, n in enumerate(ch_names):
        chanlocs[i]["labels"] = n

    eeg = dict(nbchan=nbchan, pnts=pnts, trials=trials, srate=srate, chanlocs=chanlocs, data=fdt_name)
    buf = io.BytesIO()
    scipy.io.savemat(buf, {"EEG": eeg})
    return buf.getvalue()


def test_parse_eeglab_set_recovers_metadata():
    ch_names = ["Fp1", "Fp2", "Cz"]
    blob = _build_fake_set_bytes(nbchan=3, pnts=100, trials=2, srate=250.0, ch_names=ch_names,
                                  fdt_name="rec.fdt")
    meta = parse_eeglab_set(blob)
    assert meta["nbchan"] == 3
    assert meta["pnts"] == 100
    assert meta["trials"] == 2
    assert meta["srate"] == 250.0
    assert meta["ch_names"] == ch_names
    assert meta["fdt_name"] == "rec.fdt"


def test_is_matlab_v73_detects_real_text_preamble():
    # Every real .set in the deposit starts with this exact text preamble, NOT an HDF5 magic at offset 0.
    real_preamble = (b"MATLAB 7.3 MAT-file, Platform: MACI64, Created on: Fri May 30 11:15:59 2014 "
                     b"HDF5 schema 1.00 .")
    assert _is_matlab_v73(real_preamble.ljust(512) + b"\x89HDF\r\n\x1a\n" + b"\x00" * 100) is True


def test_is_matlab_v73_detects_hdf5_signature_at_offset_512_without_text_preamble():
    blob = b"\x00" * 512 + b"\x89HDF\r\n\x1a\n" + b"\x00" * 40
    assert _is_matlab_v73(blob) is True


def test_is_matlab_v73_false_for_plain_v5_bytes():
    assert _is_matlab_v73(b"MATLAB 5.0 MAT-file" + b"\x00" * 500) is False


def _build_fake_set_bytes_v73(nbchan, pnts, trials, srate, ch_names, fdt_name):
    """A real, valid HDF5 file shaped like a MATLAB v7.3 EEGLAB .set -- built directly with h5py, since
    every real .set in the deposit turned out to be this format (see chennu.py's module docstring)."""
    import h5py

    buf = io.BytesIO()
    with h5py.File(buf, "w") as f:
        eeg = f.create_group("EEG")
        eeg.create_dataset("nbchan", data=np.array([[float(nbchan)]]))
        eeg.create_dataset("pnts", data=np.array([[float(pnts)]]))
        eeg.create_dataset("trials", data=np.array([[float(trials)]]))
        eeg.create_dataset("srate", data=np.array([[float(srate)]]))
        codes = np.array([[ord(c)] for c in fdt_name], dtype="uint16")
        eeg.create_dataset("data", data=codes)
        chanlocs = eeg.create_group("chanlocs")
        labels_ds = chanlocs.create_dataset(
            "labels", shape=(len(ch_names), 1), dtype=h5py.special_dtype(ref=h5py.Reference))
        for i, name in enumerate(ch_names):
            name_codes = np.array([[ord(c)] for c in name], dtype="uint16")
            ds = f.create_dataset(f"#refs#/lab{i}", data=name_codes)
            labels_ds[i, 0] = ds.ref
    return buf.getvalue()


def test_parse_eeglab_set_v73_recovers_metadata():
    ch_names = ["Fp1", "Fp2", "Cz"]
    blob = _build_fake_set_bytes_v73(nbchan=3, pnts=100, trials=2, srate=250.0, ch_names=ch_names,
                                      fdt_name="rec.fdt")
    assert _is_matlab_v73(blob) is True
    meta = parse_eeglab_set(blob)
    assert meta["nbchan"] == 3
    assert meta["pnts"] == 100
    assert meta["trials"] == 2
    assert meta["srate"] == 250.0
    assert meta["ch_names"] == ch_names
    assert meta["fdt_name"] == "rec.fdt"


def test_parse_eeglab_set_v73_dispatch_raises_cleanly_on_garbage_hdf5():
    # Real v7.3 preamble but not an actual valid HDF5 container after it -- must fail loudly, not silently
    # return wrong metadata.
    blob = b"MATLAB 7.3 MAT-file, Platform: fake".ljust(512) + b"\x89HDF\r\n\x1a\n" + b"\x00" * 100
    with pytest.raises(Exception):
        parse_eeglab_set(blob)


def test_chennu_adapter_end_to_end_offline(tmp_path, monkeypatch):
    """Build a real synthetic ZIP (with a real .set built via scipy.io.savemat, and a matching .fdt) and
    drive the full adapter -- list_recordings, then load() -- against a monkeypatched network layer."""
    rid = "02-2010-anest 20100210 135.003"
    nbchan, pnts, srate = 3, 20, 100.0
    ch_names = ["Fp1", "Fp2", "Cz"]
    n_epochs_available = 3
    arr = np.zeros((nbchan, pnts, n_epochs_available), dtype="<f4")
    for c in range(nbchan):
        arr[c, :, :] = (c + 1) * 5.0
    fdt_bytes = arr.tobytes(order="F")
    set_bytes = _build_fake_set_bytes(nbchan=nbchan, pnts=pnts, trials=n_epochs_available, srate=srate,
                                       ch_names=ch_names, fdt_name=f"{rid}.fdt")

    contents = {
        f"Sedation-RestingState/{rid}.set": set_bytes,
        f"Sedation-RestingState/{rid}.fdt": fdt_bytes,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in contents.items():
            zf.writestr(name, data)
    zip_bytes = buf.getvalue()

    monkeypatch.setattr(remote_zip, "_http_get_range",
                         lambda url, start, length, timeout=None: zip_bytes[start:start + length])

    labels_csv = tmp_path / "labels.csv"
    labels_csv.write_text(_FAKE_LABELS_CSV)

    adapter = ChennuRemoteZipAdapter(url="fake://test.zip", labels_csv=str(labels_csv), n_epochs=2)
    adapter._zip = RemoteZip("fake://test.zip", total_size=len(zip_bytes))

    refs = adapter.list_recordings()
    assert [r.recording_id for r in refs] == sorted(r.recording_id for r in refs)
    ref = next(r for r in refs if r.recording_id == rid)
    assert ref.subject == "02"
    assert ref.meta["sedation_level"] == 1.0

    data, out_ch_names, out_sfreq, meta = ref.load()
    assert out_ch_names == ch_names
    assert out_sfreq == srate
    assert data.shape == (nbchan, pnts * 2)  # n_epochs=2 requested, not all 3 available epochs
    for c in range(nbchan):
        assert np.all(data[c, :] == (c + 1) * 5.0)
    assert meta["n_epochs_used"] == 2
    assert meta["sedation_level"] == 1.0
    assert meta["plasma_propofol_ug_per_L"] == 0.0
    assert meta["mean_reaction_time_ms"] == 903.0
    assert meta["n_correct_of_40"] == 40.0


# --------------------------------------------------------------------------------------------------------
# Network tests: the real archive
# --------------------------------------------------------------------------------------------------------

@NETWORK
def test_network_remote_zip_index_finds_expected_member_counts():
    rz = RemoteZip(CHENNU_ARCHIVE_URL)
    assert rz.total_size == 3694326663
    members = rz.index()
    set_members = [m for m in members if m["name"].lower().endswith(".set")]
    fdt_members = [m for m in members if m["name"].lower().endswith(".fdt")]
    assert len(set_members) == 80
    assert len(fdt_members) == 80
    assert not any(m["name"].startswith("__MACOSX/") for m in members)
    assert not any(m["name"].endswith(".DS_Store") for m in members)


@NETWORK
def test_network_chennu_adapter_end_to_end_real():
    adapter = ChennuRemoteZipAdapter(n_epochs=4)
    refs = adapter.list_recordings()
    assert len(refs) == 80
    ref = refs[0]
    data, ch_names, sfreq, meta = ref.load()
    assert data.shape[0] == len(ch_names) > 0
    assert sfreq > 0
    std = float(np.std(data))
    assert 5.0 <= std <= 100.0, f"implausible scalp EEG microvolt std: {std}"
    assert meta["bytes_fetched_fdt"] > 0
    for f in ("sedation_level", "plasma_propofol_ug_per_L", "mean_reaction_time_ms", "n_correct_of_40"):
        assert f in meta
