"""Tests for the HBN adapter, and specifically for the window-selection bug that two gates caught.

THE TEST THAT MATTERS is `test_the_trailing_unbounded_block_is_dropped`. HBN's resting run alternates 20 s
eyes-open with 40 s eyes-closed and ENDS on an eyes-open instruction. The first version of
`blocks_from_events` returned that final block open-ended, the loader closed it at the recording end, and it
was therefore the LONGEST block of its condition in every single recording — so every subject's "eyes open"
window came from ~35 s of post-protocol recording where the run is over, the participant moves and the
experimenter talks.

It was found because two independent gates sat near chance (band-dependent 63.0 %, band-free 46.3 %) on a
contrast — alpha blocking — that is the most robust phenomenon in EEG. Neither gate was weakened; the
adapter was wrong.

The lesson generalises beyond this deposit and is the reason the test is written as strictly as it is:
**"the longest block" is a rule that silently prefers whichever block is least well defined**, because an
unbounded interval is always longer than a bounded one.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.ingestion.hbn import CLOSE_EVENT, OPEN_EVENT, blocks_from_events


class _Ev:
    """Minimal stand-in for an EEGLAB event struct entry."""

    def __init__(self, type_, latency):
        self.type = type_
        self.latency = latency


def _hbn_like(sfreq=500.0):
    """The real HBN pattern: 20 s open / 40 s closed, ENDING on an open instruction."""
    marks, t = [], 47.84
    for i in range(6):
        marks.append(_Ev(OPEN_EVENT, t * sfreq))
        t += 20.0
        if i < 5:
            marks.append(_Ev(CLOSE_EVENT, t * sfreq))
            t += 40.0
    return np.array(marks, dtype=object)


def test_the_trailing_unbounded_block_is_dropped():
    b = blocks_from_events(_hbn_like(), 500.0)
    for cond, blocks in b.items():
        for t0, t1 in blocks:
            assert t1 is not None, f"{cond} block at {t0} is unbounded; the loader would close it at the "
            assert t1 > t0


def test_every_open_block_is_the_instructed_twenty_seconds():
    b = blocks_from_events(_hbn_like(), 500.0)
    durs = [round(t1 - t0, 3) for t0, t1 in b["open"]]
    assert durs and all(d == pytest.approx(20.0) for d in durs), durs
    assert len(durs) == 5, "the sixth open instruction opens the trailing block and must be dropped"


def test_every_closed_block_is_the_instructed_forty_seconds():
    b = blocks_from_events(_hbn_like(), 500.0)
    durs = [round(t1 - t0, 3) for t0, t1 in b["closed"]]
    assert durs and all(d == pytest.approx(40.0) for d in durs), durs


def test_the_longest_open_block_is_not_the_end_of_the_recording():
    """The failure restated as the thing that actually went wrong: the selection rule preferred the block
    that was least well defined, because an unbounded interval is always the longest one."""
    b = blocks_from_events(_hbn_like(), 500.0)
    longest_open = max(b["open"], key=lambda ab: ab[1] - ab[0])
    last_instruction = max(t0 for t0, _ in b["open"] + b["closed"])
    assert longest_open[0] < last_instruction, (
        "the longest open block starts at the final instruction — the trailing unbounded segment is being "
        "selected again")


def test_events_of_other_types_are_ignored():
    ev = np.array([_Ev("break cnt", 0.0), _Ev("resting_start", 645.0),
                   _Ev(OPEN_EVENT, 23921.0), _Ev("dot_no2_ON", 30000.0),
                   _Ev(CLOSE_EVENT, 33921.0), _Ev(OPEN_EVENT, 53921.0)], dtype=object)
    b = blocks_from_events(ev, 500.0)
    assert len(b["open"]) == 1 and len(b["closed"]) == 1
    assert b["open"][0][1] == pytest.approx(33921.0 / 500.0), \
        "an unrelated event between instructions must not truncate a block"


def test_no_events_yields_no_blocks_rather_than_the_whole_recording():
    b = blocks_from_events(np.array([_Ev("break cnt", 0.0)], dtype=object), 500.0)
    assert b == {"open": [], "closed": []}


def test_the_window_leaves_out_the_instruction_transient():
    """A participant does not open their eyes instantaneously, and the lead-in must apply to BOTH
    conditions so the closed window is not quietly given cleaner data than the open one."""
    from bsde.ingestion.hbn import HBNRestingAdapter
    ad = HBNRestingAdapter(release="R1", window_s=16.0, lead_in_s=2.0)
    assert ad.lead_in_s > 0
    assert ad.window_s + ad.lead_in_s <= 20.0, (
        "window plus lead-in must fit inside HBN's 20 s eyes-open block, or the open condition silently "
        "loses subjects that the closed condition keeps")
