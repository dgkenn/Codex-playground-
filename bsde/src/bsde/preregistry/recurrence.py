#!/usr/bin/env python3
"""Reference implementation of the v1.1 recurrence record (see SPEC.md). Stdlib only.

A recurrence is an EVENT -- "failure mode X happened again on date D" -- not a property of a rule, so
several rows may share a `rule_id`. The three fields that carry the whole design are:

  `rule_id`          which rule FAILED, never where the write-up was filed. Without this, a recurrence
                     written up as a NEW rule is invisible to any scan of the old one, which E343
                     verified is the normal case rather than the exception and biases counts DOWNWARD.
  `first_stated_on`  carried on the event row rather than looked up, so before/after stays decidable
                     offline and survives the rule being renumbered or the catalogue being reformatted.
  `noticed_by`       the only handle on the lower-bound problem. A count of recurrences is always a
                     lower bound; a register whose events are all `self` has no evidence at all about
                     its own sensitivity.

`occurred_on < first_stated_on` is LEGAL and load-bearing: it encodes an instance that predates the rule.
A rule written at its own third occurrence emits two such rows and correctly yields ZERO post-statement
failures, where a prose scan of "third occurrence" produces a false positive.

    python -m bsde.preregistry.recurrence <recurrences.jsonl>     # print the summary
"""
from __future__ import annotations

import datetime
import json
import os

NOTICED_BY = ("self", "gate", "reviewer", "downstream")
REQUIRED = ("rule_id", "occurred_on", "first_stated_on", "noticed_by", "was_cited")


class RecurrenceError(ValueError):
    pass


def _date(v, field):
    if not isinstance(v, str):
        raise RecurrenceError(f"{field} must be an ISO date string, got {type(v).__name__}")
    try:
        return datetime.date.fromisoformat(v)
    except ValueError as e:
        raise RecurrenceError(f"{field}: {e}") from e


def validate(row):
    """Return the row, normalised, or raise RecurrenceError. Never silently repairs a row."""
    if not isinstance(row, dict):
        raise RecurrenceError("a recurrence row must be an object")
    missing = [f for f in REQUIRED if f not in row]
    if missing:
        raise RecurrenceError(f"missing required field(s): {', '.join(missing)}")
    if not str(row["rule_id"]).strip():
        raise RecurrenceError("rule_id must be non-empty -- it names which rule FAILED, and a blank "
                              "one is exactly the defect this record exists to prevent")
    occurred = _date(row["occurred_on"], "occurred_on")
    stated = _date(row["first_stated_on"], "first_stated_on")
    if row["noticed_by"] not in NOTICED_BY:
        raise RecurrenceError(f"noticed_by must be one of {NOTICED_BY}, got {row['noticed_by']!r}")
    if not isinstance(row["was_cited"], bool):
        raise RecurrenceError("was_cited must be a bool; 'unknown' is not a value, because a "
                              "cited-then-violated rate computed over unknowns is not a rate")
    out = dict(row)
    out["filed_as"] = row.get("filed_as") or None
    out["detail"] = str(row.get("detail", ""))
    out["_post_statement"] = occurred > stated
    out["_days_after"] = (occurred - stated).days
    return out


def append(path, **row):
    """Append one validated recurrence event. Append-only: rows are never edited."""
    rec = validate(row)
    rec.pop("_post_statement"), rec.pop("_days_after")
    with open(path, "a") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def load(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(validate(json.loads(line)))
            except (ValueError, RecurrenceError) as e:
                raise RecurrenceError(f"{path}:{i}: {e}") from e
    return rows


def summarise(rows, as_of=None):
    """Everything SPEC.md v1.1 says is measurable, and nothing it says is not.

    Note what is deliberately absent: a recurrence RATE. The denominator would be the set of rules that
    could have recurred, which is knowable, but the numerator is a lower bound of unknown tightness, so
    the quotient would be false precision (E343's LIMITATION 1). Counts and the detection mix are
    reported instead, and a caller that wants a rate must construct it and own the caveat.
    """
    as_of = as_of or datetime.date.today()
    post = [r for r in rows if r["_post_statement"]]
    pre = [r for r in rows if not r["_post_statement"]]
    by_rule = {}
    for r in post:
        by_rule.setdefault(r["rule_id"], []).append(r)
    stated = {}
    for r in rows:
        d = _date(r["first_stated_on"], "first_stated_on")
        stated[r["rule_id"]] = min(stated.get(r["rule_id"], d), d)
    mix = {k: sum(1 for r in post if r["noticed_by"] == k) for k in NOTICED_BY}
    filed_elsewhere = sum(1 for r in post if r["filed_as"] and r["filed_as"] != r["rule_id"])
    return {
        "n_events": len(rows),
        "n_post_statement": len(post),
        "n_pre_statement": len(pre),
        "rules_with_post_statement_recurrence": sorted(by_rule),
        "recurrences_per_rule": {k: len(v) for k, v in sorted(by_rule.items())},
        "days_to_first_recurrence": {
            k: min(r["_days_after"] for r in v) for k, v in sorted(by_rule.items())},
        "exposure_days": {k: (as_of - d).days for k, d in sorted(stated.items())},
        "cited_then_violated": sum(1 for r in post if r["was_cited"]),
        "cited_then_violated_of_post": (
            f"{sum(1 for r in post if r['was_cited'])}/{len(post)}" if post else "0/0"),
        "noticed_by_mix": mix,
        "filed_under_another_id": filed_elsewhere,
        "IS_A_LOWER_BOUND": ("a recurrence nobody noticed is invisible to any schema; report these "
                             "counts with the noticed_by mix beside them"),
    }


def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    print(json.dumps(summarise(load(argv[0])), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
