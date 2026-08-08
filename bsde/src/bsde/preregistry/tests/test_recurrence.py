#!/usr/bin/env python3
"""Tests for the v1.1 recurrence record. Stdlib only.

Written to the rule-40 shape: for every guard, construct the input that SHOULD fail it and check that it
does, and the input that SHOULD pass and check that it does. A guard tested only in the passing direction
is not a guard.

    python -m bsde.preregistry.tests.test_recurrence
"""
from __future__ import annotations

import os
import tempfile
import unittest

from bsde.preregistry.recurrence import (
    RecurrenceError, append, load, summarise, validate)


def row(**kw):
    base = dict(rule_id="R37", occurred_on="2026-07-31", first_stated_on="2026-07-29",
                noticed_by="self", was_cited=False, detail="")
    base.update(kw)
    return base


class TestValidate(unittest.TestCase):
    def test_minimal_row_validates(self):
        r = validate(row())
        self.assertTrue(r["_post_statement"])
        self.assertEqual(r["_days_after"], 2)

    def test_every_required_field_is_actually_required(self):
        for f in ("rule_id", "occurred_on", "first_stated_on", "noticed_by", "was_cited"):
            bad = row()
            del bad[f]
            with self.assertRaises(RecurrenceError, msg=f"{f} was not enforced"):
                validate(bad)

    def test_blank_rule_id_refused(self):
        # the defect the whole record exists to prevent: a recurrence with no attributable rule
        with self.assertRaises(RecurrenceError):
            validate(row(rule_id="  "))

    def test_bad_enum_and_bad_date_refused(self):
        with self.assertRaises(RecurrenceError):
            validate(row(noticed_by="probably"))
        with self.assertRaises(RecurrenceError):
            validate(row(occurred_on="31/07/2026"))

    def test_was_cited_must_be_boolean(self):
        # a cited-then-violated rate computed over "unknown" is not a rate
        with self.assertRaises(RecurrenceError):
            validate(row(was_cited="unknown"))

    def test_pre_statement_event_is_legal_and_flagged(self):
        # rule 36's case: written AT its third occurrence, so occurrences 1-2 predate the rule
        r = validate(row(occurred_on="2026-07-20", first_stated_on="2026-07-29"))
        self.assertFalse(r["_post_statement"])
        self.assertEqual(r["_days_after"], -9)

    def test_same_day_is_not_post_statement(self):
        r = validate(row(occurred_on="2026-07-29", first_stated_on="2026-07-29"))
        self.assertFalse(r["_post_statement"])


class TestSummarise(unittest.TestCase):
    def test_pre_statement_events_do_not_count_as_failures(self):
        """The false positive a prose scan produces, and the reason the field exists.

        A rule written at its own third occurrence emits two pre-statement rows. It has failed ZERO
        times, and the summary must say so.
        """
        rows = [validate(row(rule_id="R36", occurred_on=d, first_stated_on="2026-07-29"))
                for d in ("2026-07-10", "2026-07-20")]
        s = summarise(rows)
        self.assertEqual(s["n_events"], 2)
        self.assertEqual(s["n_post_statement"], 0)
        self.assertEqual(s["rules_with_post_statement_recurrence"], [])

    def test_recurrence_filed_under_another_id_is_still_attributed_correctly(self):
        """The false negative, and the structural one (E343 defect 3).

        Rule 84 IS a second occurrence of rule 77, written up as a new rule. `rule_id` must carry 77
        while `filed_as` carries 84, so a scan of rule 77 finds it.
        """
        rows = [validate(row(rule_id="R77", filed_as="R84", occurred_on="2026-08-01",
                             first_stated_on="2026-08-01"))]
        rows[0] = validate(row(rule_id="R77", filed_as="R84", occurred_on="2026-08-02",
                               first_stated_on="2026-08-01"))
        s = summarise(rows)
        self.assertEqual(s["rules_with_post_statement_recurrence"], ["R77"])
        self.assertEqual(s["filed_under_another_id"], 1)

    def test_counts_days_and_mix(self):
        rows = [
            validate(row(rule_id="R37", occurred_on="2026-07-31", noticed_by="gate",
                         was_cited=True)),
            validate(row(rule_id="R37", occurred_on="2026-08-02", noticed_by="self")),
            validate(row(rule_id="R38", occurred_on="2026-08-05", first_stated_on="2026-07-29",
                         noticed_by="downstream")),
        ]
        s = summarise(rows)
        self.assertEqual(s["recurrences_per_rule"], {"R37": 2, "R38": 1})
        self.assertEqual(s["days_to_first_recurrence"], {"R37": 2, "R38": 7})
        self.assertEqual(s["cited_then_violated"], 1)
        self.assertEqual(s["cited_then_violated_of_post"], "1/3")
        self.assertEqual(s["noticed_by_mix"],
                         {"self": 1, "gate": 1, "reviewer": 0, "downstream": 1})

    def test_no_rate_is_reported(self):
        """Deliberate absence: the numerator is a lower bound, so a quotient would be false precision."""
        s = summarise([validate(row())])
        self.assertNotIn("recurrence_rate", s)
        self.assertIn("IS_A_LOWER_BOUND", s)

    def test_empty_register_does_not_divide_by_zero(self):
        s = summarise([])
        self.assertEqual(s["n_events"], 0)
        self.assertEqual(s["cited_then_violated_of_post"], "0/0")


class TestRoundTrip(unittest.TestCase):
    def test_append_then_load(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "recurrences.jsonl")
        append(p, **row(rule_id="R37", noticed_by="gate", was_cited=True, detail="x"))
        append(p, **row(rule_id="R38", occurred_on="2026-08-02"))
        rows = load(p)
        self.assertEqual([r["rule_id"] for r in rows], ["R37", "R38"])
        self.assertTrue(all(r["_post_statement"] for r in rows))

    def test_append_refuses_an_invalid_row_and_writes_nothing(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "recurrences.jsonl")
        with self.assertRaises(RecurrenceError):
            append(p, **row(noticed_by="maybe"))
        self.assertFalse(os.path.exists(p), "a refused row must not be partially written")

    def test_load_reports_the_offending_line(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "recurrences.jsonl")
        append(p, **row())
        with open(p, "a") as fh:
            fh.write('{"rule_id": "R1"}\n')
        with self.assertRaises(RecurrenceError) as cm:
            load(p)
        self.assertIn(":2:", str(cm.exception))

    def test_missing_file_is_empty_not_an_error(self):
        self.assertEqual(load("/nonexistent/recurrences.jsonl"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
