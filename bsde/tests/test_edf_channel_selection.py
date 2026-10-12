"""Regression tests for two EDF decoding bugs found on real polysomnography (Sleep-EDF SC4001E0-PSG.edf).

That file declares seven signals with THREE different physical dimensions and TWO different sampling rates:

    0 'EEG Fpz-Cz'      uV     3000 samples/record  ->  100 Hz
    1 'EEG Pz-Oz'       uV     3000                 ->  100 Hz
    2 'EOG horizontal'  uV     3000                 ->  100 Hz
    3 'Resp oro-nasal'  ''       30                 ->    1 Hz
    4 'EMG submental'   uV       30                 ->    1 Hz
    5 'Temp rectal'     DegC     30                 ->    1 Hz
    6 'Event marker'    ''       30                 ->    1 Hz

Bug 1 (loud): the units guard rejected the whole recording because of the blank/DegC channels, so no
polysomnography could be read at all.

Bug 2 (silent, and the dangerous one): `decode_edf_window` took `min(len(v))` across channels and
`vstack`ed. With 3000-sample EEG beside 30-sample slow channels that truncated the EEG to one hundredth of
its samples, while still returning `sfreq = 100`. A wrong array at a wrongly-reported rate, with no error
raised — a 30-minute window silently becoming 18 seconds of data labelled as 30 minutes.

The fix is channel selection plus a hard refusal to mix rates. These tests pin both.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.ingestion.http_edf import decode_edf_window, select_channels


# --- synthetic EDF construction ---------------------------------------------------------------------

def _ascii(v, n):
    b = str(v).encode()[:n]
    return b + b" " * (n - len(b))


def _make_edf(specs, n_records=4, rec_dur=1.0):
    """Build EDF bytes. `specs` = [(label, dim, samples_per_record, phys_min, phys_max, const_digital)].

    Digital range is fixed at [-2048, 2047] and each channel is filled with one constant digital value, so
    the expected physical value is analytic.
    """
    ns = len(specs)
    header_bytes = 256 * (ns + 1)
    # EDF main header, field widths per the spec: 8 version | 80 patient | 80 recording | 8 startdate
    # | 8 starttime | 8 header_bytes | 44 reserved | 8 n_records | 8 record_duration | 4 n_signals = 256.
    main = (_ascii(0, 8) + _ascii("X", 80) + _ascii("Y", 80)
            + _ascii("01.01.20", 8) + _ascii("00.00.00", 8)
            + _ascii(header_bytes, 8) + _ascii("", 44)
            + _ascii(n_records, 8) + _ascii(rec_dur, 8) + _ascii(ns, 4))
    assert len(main) == 256, len(main)

    def field(vals, w):
        return b"".join(_ascii(v, w) for v in vals)

    sh = (field([s[0] for s in specs], 16) + field(["" for _ in specs], 80)
          + field([s[1] for s in specs], 8)
          + field([s[3] for s in specs], 8) + field([s[4] for s in specs], 8)
          + field([-2048 for _ in specs], 8) + field([2047 for _ in specs], 8)
          + field(["" for _ in specs], 80) + field([s[2] for s in specs], 8)
          + field(["" for _ in specs], 32))
    assert len(sh) == ns * 256, (len(sh), ns * 256)

    rec = b""
    for _ in range(n_records):
        for lab, dim, spr, pmin, pmax, dig in specs:
            rec += struct.pack("<" + "h" * spr, *([dig] * spr))
    return main, sh, rec


def _expected_uv(dig, pmin, pmax, dim):
    gain = (pmax - pmin) / (2047 - (-2048))
    phys = (dig - (-2048)) * gain + pmin
    return phys * {"uV": 1.0, "mV": 1e3, "V": 1e6}[dim]


# --- bug 1: units ------------------------------------------------------------------------------------

def test_a_blank_physical_dimension_still_raises_when_that_channel_is_selected():
    """The guard must stay strict. Assuming microvolts for a respiration trace would feed a non-voltage
    into a voltage feature."""
    main, sh, rec = _make_edf([("EEG Fpz-Cz", "uV", 4, -100, 100, 500),
                               ("Resp oro-nasal", "", 4, -2048, 2047, 100)])
    with pytest.raises(ValueError, match="dimension"):
        decode_edf_window(main, sh, rec, skip_records=0)


def test_selecting_only_the_eeg_channels_makes_a_mixed_unit_file_readable():
    """This is the whole point: Sleep-EDF is readable, without relaxing the guard."""
    main, sh, rec = _make_edf([("EEG Fpz-Cz", "uV", 4, -100, 100, 500),
                               ("Temp rectal", "DegC", 4, 34, 40, 0),
                               ("Event marker", "", 4, -2048, 2047, 0)])
    data, labels, sfreq, meta = decode_edf_window(main, sh, rec, skip_records=0, select=[0])
    assert labels == ["EEG Fpz-Cz"]
    assert data.shape == (1, 16)
    assert data[0, 0] == pytest.approx(_expected_uv(500, -100, 100, "uV"), rel=1e-9)
    assert meta["selected_labels"] == ["EEG Fpz-Cz"]


def test_per_channel_units_are_converted_independently():
    """A mV channel must come out 1000x a µV channel carrying the same digital code and physical range."""
    main, sh, rec = _make_edf([("A", "uV", 4, -100, 100, 700), ("B", "mV", 4, -100, 100, 700)])
    data, _, _, _ = decode_edf_window(main, sh, rec, skip_records=0)
    assert data[1, 0] / data[0, 0] == pytest.approx(1000.0, rel=1e-9)


# --- bug 2: the silent truncation --------------------------------------------------------------------

def test_mixed_sampling_rates_raise_instead_of_truncating_to_the_shortest():
    """THE REGRESSION THAT MATTERS. Before the fix this returned a (2, 4) array with sfreq=100 -- the
    100 Hz channel silently cut to the 1 Hz channel's length, mislabelled as 100 Hz."""
    main, sh, rec = _make_edf([("EEG Fpz-Cz", "uV", 400, -100, 100, 500),
                               ("EMG submental", "uV", 4, -5, 5, 100)], n_records=2)
    with pytest.raises(ValueError, match="different sampling rates"):
        decode_edf_window(main, sh, rec, skip_records=0)


def test_the_error_names_the_offending_channels_and_their_rates():
    main, sh, rec = _make_edf([("EEG Fpz-Cz", "uV", 400, -100, 100, 500),
                               ("EMG submental", "uV", 4, -5, 5, 100)], n_records=2)
    with pytest.raises(ValueError) as e:
        decode_edf_window(main, sh, rec, skip_records=0)
    msg = str(e.value)
    assert "EEG Fpz-Cz" in msg and "EMG submental" in msg
    assert "400" in msg and "4 Hz" in msg, msg


def test_selecting_one_rate_recovers_the_full_sample_count():
    """With the slow channel excluded, the EEG keeps every sample and sfreq is right."""
    main, sh, rec = _make_edf([("EEG Fpz-Cz", "uV", 400, -100, 100, 500),
                               ("EMG submental", "uV", 4, -5, 5, 100)], n_records=2)
    data, labels, sfreq, _ = decode_edf_window(main, sh, rec, skip_records=0, select=[0])
    assert data.shape == (1, 800), "2 records x 400 samples must all survive"
    assert sfreq == pytest.approx(400.0)


def test_channel_offsets_are_correct_when_earlier_channels_have_different_widths():
    """Selecting a later channel must not read another channel's bytes. Channel 2 sits behind a wide
    channel 0 and a narrow channel 1, so a naive fixed-stride offset would misread it."""
    main, sh, rec = _make_edf([("wide", "uV", 40, -100, 100, 111),
                               ("narrow", "uV", 4, -100, 100, 222),
                               ("target", "uV", 4, -100, 100, 333)], n_records=2)
    data, labels, _, _ = decode_edf_window(main, sh, rec, skip_records=0, select=[2])
    assert labels == ["target"]
    assert data[0, 0] == pytest.approx(_expected_uv(333, -100, 100, "uV"), rel=1e-9)
    assert np.allclose(data[0], data[0, 0]), "constant channel must decode as constant"


# --- select_channels ---------------------------------------------------------------------------------

def test_select_channels_matches_case_insensitively():
    labels = ["EEG Fpz-Cz", "EEG Pz-Oz", "EOG horizontal", "Temp rectal"]
    assert select_channels(labels, "^EEG ") == [0, 1]
    assert select_channels(labels, "^eeg ") == [0, 1]
    assert select_channels(labels, None) is None


def test_a_regex_matching_nothing_raises_rather_than_falling_back_to_all():
    """A typo must not silently reintroduce the thermistor."""
    with pytest.raises(ValueError, match="matched none"):
        select_channels(["EEG Fpz-Cz", "Temp rectal"], "^MEG ")


def test_out_of_range_selection_raises():
    main, sh, rec = _make_edf([("A", "uV", 4, -100, 100, 1)])
    with pytest.raises(ValueError, match="out of range"):
        decode_edf_window(main, sh, rec, skip_records=0, select=[0, 5])
