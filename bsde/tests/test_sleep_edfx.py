"""Sleep-EDF hypnogram parsing and the labelled-window adapter, pinned against synthetic EDF+ annotation
bytes -- no network. The one property that matters most is tested explicitly, per the module's own
docstring: two rows of one recording (wake, N3) must get DIFFERENT recording_ids but the SAME subject,
because that is what keeps the wake-vs-N3 contrast within-subject rather than silently between-subject.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from bsde.ingestion.sleep_edfx import (
    N3, WAKE, LabelledEDFWindowAdapter, find_hypnogram_filename, longest_block,
    parse_directory_listing, parse_hypnogram_edf, stage_blocks,
)


# --- synthetic EDF+ annotation file construction --------------------------------------------------------

def _ascii(v, n):
    b = str(v).encode()[:n]
    return b + b" " * (n - len(b))


def _make_annotation_edf(tal_text: str) -> bytes:
    """One EDF+ file with a single 'EDF Annotations' signal whose one data record holds `tal_text`
    (already using \\x14/\\x15/\\x00 separators), padded with \\x00 to fill the record.
    """
    ns = 1
    header_bytes = 256 * (ns + 1)
    raw = tal_text.encode("latin1")
    n_samples_per_record = -(-len(raw) // 2)  # ceil to whole 2-byte samples
    padded_len = n_samples_per_record * 2
    rec = raw + b"\x00" * (padded_len - len(raw))

    main = (_ascii(0, 8) + _ascii("X", 80) + _ascii("Y", 80)
            + _ascii("01.01.20", 8) + _ascii("00.00.00", 8)
            + _ascii(header_bytes, 8) + _ascii("", 44)
            + _ascii(1, 8) + _ascii(1, 8) + _ascii(ns, 4))
    assert len(main) == 256, len(main)

    def field(vals, w):
        return b"".join(_ascii(v, w) for v in vals)

    sh = (field(["EDF Annotations"], 16) + field([""], 80)
          + field([""], 8)                                   # phys_dim
          + field([0], 8) + field([1], 8)                    # phys_min, phys_max
          + field([-32768], 8) + field([32767], 8)           # dig_min, dig_max
          + field([""], 80) + field([n_samples_per_record], 8)
          + field([""], 32))
    assert len(sh) == ns * 256, (len(sh), ns * 256)
    return main + sh + rec


def _tal(onset, duration, label):
    dur_part = f"\x15{duration:g}" if duration else ""
    return f"+{onset:g}{dur_part}\x14{label}\x14\x00"


TIMEKEEPING = "+0\x14\x14\x00"  # the mandatory first TAL: onset, no duration, empty annotation text


# --- parse_hypnogram_edf -------------------------------------------------------------------------------

def test_parse_hypnogram_edf_recovers_known_triples():
    text = (TIMEKEEPING
            + _tal(0, 100, "Sleep stage W")
            + _tal(100, 200, "Sleep stage 2")
            + _tal(300, 50, "Sleep stage R"))
    blob = _make_annotation_edf(text)
    annots = parse_hypnogram_edf(blob)
    assert annots == [
        (0.0, 100.0, "Sleep stage W"),
        (100.0, 200.0, "Sleep stage 2"),
        (300.0, 50.0, "Sleep stage R"),
    ]


def test_multiple_annotations_in_one_tal_chunk_are_all_recovered():
    """A single TAL may carry several annotation texts sharing one onset/duration, each \\x14-terminated."""
    text = TIMEKEEPING + "+50\x1510\x14Sleep stage 1\x14Lights off\x14\x00"
    blob = _make_annotation_edf(text)
    annots = parse_hypnogram_edf(blob)
    assert (50.0, 10.0, "Sleep stage 1") in annots
    assert (50.0, 10.0, "Lights off") in annots


def test_timekeeping_annotation_yields_no_triple():
    blob = _make_annotation_edf(TIMEKEEPING + _tal(0, 30, "Sleep stage W"))
    annots = parse_hypnogram_edf(blob)
    assert annots == [(0.0, 30.0, "Sleep stage W")]


# --- stage_blocks / longest_block ------------------------------------------------------------------------

def test_stage_blocks_merges_contiguous_same_stage_annotations():
    annots = [(0.0, 30.0, "Sleep stage 3"), (30.0, 30.0, "Sleep stage 3"), (60.0, 30.0, "Sleep stage 3")]
    assert stage_blocks(annots, N3) == [(0.0, 90.0)]


def test_stage_blocks_does_not_merge_across_a_gap():
    annots = [(0.0, 30.0, "Sleep stage 3"), (100.0, 30.0, "Sleep stage 3")]
    assert stage_blocks(annots, N3) == [(0.0, 30.0), (100.0, 130.0)]


def test_stage_blocks_does_not_merge_across_a_different_stage():
    """3, 2, 3 back-to-back: the intervening N2 (not in the N3 stage set) must break the block, and does --
    the gap between the two N3 fragments equals the N2 annotation's own duration."""
    annots = [(0.0, 30.0, "Sleep stage 3"), (30.0, 30.0, "Sleep stage 2"), (60.0, 30.0, "Sleep stage 3")]
    assert stage_blocks(annots, N3) == [(0.0, 30.0), (60.0, 90.0)]


def test_longest_block_picks_the_longest():
    annots = [(0.0, 30.0, "Sleep stage W"), (30.0, 30.0, "Sleep stage 2"),
              (60.0, 300.0, "Sleep stage W"), (360.0, 10.0, "Sleep stage W")]
    # the 60-360 block (300s) and the trailing 360-370 fragment merge -> one 310s block
    assert longest_block(annots, WAKE) == (60.0, 370.0)


def test_longest_block_returns_none_when_stage_absent():
    annots = [(0.0, 30.0, "Sleep stage 2")]
    assert longest_block(annots, WAKE) is None
    assert stage_blocks(annots, WAKE) == []


def test_n3_mapping_includes_stage_3_and_4_and_excludes_stage_2():
    assert "Sleep stage 3" in N3
    assert "Sleep stage 4" in N3
    assert "Sleep stage 2" not in N3
    assert WAKE == {"Sleep stage W"}


# --- directory discovery ---------------------------------------------------------------------------------

def test_parse_directory_listing_extracts_edf_filenames():
    html = ('<a href="SC4001E0-PSG.edf">SC4001E0-PSG.edf</a>'
            '<a href="SC4001EC-Hypnogram.edf">SC4001EC-Hypnogram.edf</a>'
            '<a href="../">../</a>')
    assert parse_directory_listing(html) == ["SC4001E0-PSG.edf", "SC4001EC-Hypnogram.edf"]


def test_find_hypnogram_filename_matches_on_all_but_the_last_character():
    """The real pairing rule: SC4001E0-PSG.edf <-> SC4001EC-Hypnogram.edf. Substituting 'PSG' -> 'Hypnogram'
    in the string would look for 'SC4001E0-Hypnogram.edf', which does not exist."""
    filenames = ["SC4001E0-PSG.edf", "SC4001EC-Hypnogram.edf",
                 "SC4002E0-PSG.edf", "SC4002EC-Hypnogram.edf"]
    assert find_hypnogram_filename("SC4001E0-PSG.edf", filenames) == "SC4001EC-Hypnogram.edf"
    assert find_hypnogram_filename("SC4002E0-PSG.edf", filenames) == "SC4002EC-Hypnogram.edf"


def test_find_hypnogram_filename_raises_when_none_match():
    with pytest.raises(ValueError, match="no hypnogram"):
        find_hypnogram_filename("SC9999E0-PSG.edf", ["SC4001EC-Hypnogram.edf"])


def test_find_hypnogram_filename_raises_on_a_non_psg_name():
    with pytest.raises(ValueError, match="PSG"):
        find_hypnogram_filename("SC4001EC-Hypnogram.edf", ["SC4001EC-Hypnogram.edf"])


# --- LabelledEDFWindowAdapter -----------------------------------------------------------------------------

def _rows_for_one_recording():
    return [
        {"url": "https://example.org/SC4001E0-PSG.edf", "start_seconds": 100.0, "window_s": 120.0,
         "label": "W", "subject": "SC4001E0-PSG", "recording_id": "SC4001E0-PSG@W", "meta": {}},
        {"url": "https://example.org/SC4001E0-PSG.edf", "start_seconds": 33800.0, "window_s": 120.0,
         "label": "N3", "subject": "SC4001E0-PSG", "recording_id": "SC4001E0-PSG@N3", "meta": {}},
    ]


def test_two_stage_rows_of_one_recording_get_different_ids_but_the_same_subject():
    """THE PROPERTY THIS WHOLE DESIGN RESTS ON. If subject differed between the two rows, subject-level
    splitting would silently treat one person's wake and N3 windows as two independent subjects, and every
    resulting confidence interval would be too narrow."""
    adapter = LabelledEDFWindowAdapter(_rows_for_one_recording(), dataset="sleep_edfx_staged")
    refs = adapter.list_recordings()
    ids = {r.recording_id for r in refs}
    subjects = {r.subject for r in refs}
    assert ids == {"SC4001E0-PSG@W", "SC4001E0-PSG@N3"}, "recording_ids must differ"
    assert subjects == {"SC4001E0-PSG"}, "both rows must share exactly one subject"


def test_recording_id_encodes_the_stage():
    adapter = LabelledEDFWindowAdapter(_rows_for_one_recording(), dataset="sleep_edfx_staged")
    for ref in adapter.list_recordings():
        stage = ref.recording_id.rsplit("@", 1)[-1]
        assert stage in ("W", "N3")
        assert ref.meta["label"] == stage


def test_each_row_carries_its_own_start_seconds_into_the_loader():
    """The whole reason this adapter exists rather than reusing HttpEDFAdapter: two different offsets for
    the same URL. Confirm the loader closes over the RIGHT row, not a shared/last-seen one."""
    rows = _rows_for_one_recording()
    adapter = LabelledEDFWindowAdapter(rows, dataset="sleep_edfx_staged")
    by_id = {r.recording_id: r for r in adapter.list_recordings()}
    assert by_id["SC4001E0-PSG@W"].meta["start_seconds"] == 100.0
    assert by_id["SC4001E0-PSG@N3"].meta["start_seconds"] == 33800.0


def test_list_recordings_is_deterministically_ordered():
    rows = _rows_for_one_recording()
    a = [r.recording_id for r in LabelledEDFWindowAdapter(rows, dataset="d").list_recordings()]
    b = [r.recording_id for r in LabelledEDFWindowAdapter(list(reversed(rows)), dataset="d").list_recordings()]
    assert a == b == sorted(a)
