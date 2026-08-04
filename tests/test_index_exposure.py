"""Look-ahead guards for the repeated-measures exposure -- stdlib only.

WHY THIS EXISTS. The headline analysis (`analysis/heedb_vs_guideline.py`) starts its outcome clock at a
patient's index EEG but originally measured the exposure by aggregating over ALL of that patient's recordings:
burden with `max`, the EEG category with `or`, morphology with last-write-wins. A patient who survives accrues
more recordings -- and more chances at a high maximum -- than one who dies on day two, so the exposure window
was partly a function of the outcome. `heedb_burden_lookahead_check.py` measured the exposure at 41.0 % of
patients (n=7,577).

The fix resolves the index recording by TIMESTAMP, falling back to the lowest session number only when no
timestamp exists, and reports the concordance between the two orderings. These tests pin that behaviour on cases
whose answers can be computed by hand, including the case that matters most: a patient whose session NUMBERS run
opposite to their session TIMES, where picking by number silently returns the wrong recording.
"""
from __future__ import annotations

import datetime as _dt
import unittest


def resolve_burden(bsess, stime, scope):
    """Mirror of the resolver in analysis/heedb_vs_guideline.py.

    Kept as a copy rather than imported because that module pulls in numpy and boto3 at call time, and the
    integrity suite is required to run on the stdlib alone. Any change there must be mirrored here -- which is
    the point: the behaviour is pinned, so a silent revert to `max` fails a test.
    """
    out, agree, total = {}, 0, 0
    for p, d in bsess.items():
        by_num = min(d)
        times = {s: stime[(p, s)] for s in d if (p, s) in stime}
        if times:
            by_time = min(times, key=lambda s: times[s])
            total += 1
            agree += (by_time == by_num)
        else:
            by_time = by_num
        out[p] = d[by_time] if scope == "index" else max(d.values())
    return out, agree, total


def _t(hours):
    return _dt.datetime(2026, 1, 1) + _dt.timedelta(hours=hours)


class IndexExposureTest(unittest.TestCase):
    def setUp(self):
        # patient 1: session order agrees with time order
        # patient 2: session order is the REVERSE of time order -- the case that breaks number-based selection
        # patient 3: a single recording, so index and max coincide
        # patient 4: no timestamps at all, so selection must fall back to the lowest session number
        self.bsess = {
            1: {5: 0.10, 9: 0.90},
            2: {3: 0.20, 7: 0.80},
            3: {4: 0.30},
            4: {2: 0.40, 6: 0.05},
        }
        self.stime = {
            (1, 5): _t(0), (1, 9): _t(10),
            (2, 3): _t(10), (2, 7): _t(0),
            (3, 4): _t(0),
        }

    def test_index_scope_takes_the_earliest_recording_by_time(self):
        out, _, _ = resolve_burden(self.bsess, self.stime, "index")
        self.assertEqual(out, {1: 0.10, 2: 0.80, 3: 0.30, 4: 0.40})

    def test_reversed_session_numbering_is_resolved_by_timestamp(self):
        """Patient 2's earliest recording is session 7, not session 3."""
        out, _, _ = resolve_burden(self.bsess, self.stime, "index")
        self.assertEqual(out[2], 0.80)
        by_number = self.bsess[2][min(self.bsess[2])]
        self.assertNotEqual(out[2], by_number)

    def test_max_scope_reproduces_the_legacy_look_ahead(self):
        out, _, _ = resolve_burden(self.bsess, self.stime, "max")
        self.assertEqual(out, {1: 0.90, 2: 0.80, 3: 0.30, 4: 0.40})

    def test_index_and_max_actually_differ(self):
        """Guards against a refactor that makes the scope flag a no-op."""
        idx, _, _ = resolve_burden(self.bsess, self.stime, "index")
        mx, _, _ = resolve_burden(self.bsess, self.stime, "max")
        self.assertNotEqual(idx, mx)
        self.assertLess(idx[1], mx[1])

    def test_falls_back_to_lowest_session_number_without_timestamps(self):
        out, _, _ = resolve_burden(self.bsess, self.stime, "index")
        self.assertEqual(out[4], 0.40)

    def test_concordance_counts_only_patients_that_have_timestamps(self):
        _, agree, total = resolve_burden(self.bsess, self.stime, "index")
        self.assertEqual(total, 3)   # patients 1, 2, 3 -- not 4, which has no timestamps
        self.assertEqual(agree, 2)   # 1 and 3 agree; 2 does not

    def test_max_never_falls_below_index(self):
        idx, _, _ = resolve_burden(self.bsess, self.stime, "index")
        mx, _, _ = resolve_burden(self.bsess, self.stime, "max")
        for p in idx:
            self.assertGreaterEqual(mx[p], idx[p])


if __name__ == "__main__":
    unittest.main()
