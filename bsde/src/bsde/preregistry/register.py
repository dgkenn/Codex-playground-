#!/usr/bin/env python3
"""Minimal Pre-Registration Register, reference implementation. Stdlib only, no project dependencies.

    python -m bsde.preregistry.register new     --file reg.jsonl --id E01 --question "..." \
                                               --primary "..." --gate "..." --gate "..." \
                                               --incumbent "..." --placebo "..."
    python -m bsde.preregistry.register outcome --file reg.jsonl --id E01 --outcome gate_failed \
                                               --detail "G2 refused: incumbent not alive"
    python -m bsde.preregistry.register verify  --file reg.jsonl

The two invariants the format depends on, enforced here rather than documented:
  * a NEW row is always `outcome = registered` -- a register whose rows can be born with a verdict
    measures nothing;
  * `outcome` and `outcome_detail` are the ONLY fields an existing row may ever change.
"""
from __future__ import annotations

import argparse, datetime, json, os, sys

OUTCOMES = ("registered", "gate_failed", "positive", "negative", "absent",
            "blocked", "withdrawn", "closed")
REQUIRED = ("id", "registered_utc", "question", "primary", "gates", "incumbent",
            "placebo", "outcome", "outcome_detail")
MUTABLE = ("outcome", "outcome_detail")


def load(path):
    if not os.path.exists(path):
        return []
    out = []
    for n, line in enumerate(open(path), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path}:{n}: not valid JSON ({e})")
    return out


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def cmd_new(a):
    rows = load(a.file)
    if any(r.get("id") == a.id for r in rows):
        raise SystemExit(f"id {a.id!r} already registered; the register is append-only")
    if not a.gate:
        print("WARNING: no gates declared. A design with no gate cannot be refused -- it can only "
              "produce a number. This is recorded as-is.", file=sys.stderr)
    if not (a.incumbent or "").strip():
        print("WARNING: no incumbent named. A marker reported without the thing it must beat is not "
              "a result. Recorded as a defect.", file=sys.stderr)
    row = {"id": a.id, "registered_utc": _now(), "question": a.question, "primary": a.primary,
           "gates": list(a.gate or []), "incumbent": a.incumbent or "",
           "placebo": a.placebo, "outcome": "registered", "outcome_detail": ""}
    for k in ("successor_of", "instrument_changed", "dataset", "code_ref"):
        v = getattr(a, k, None)
        if v:
            row[k] = v
    with open(a.file, "a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"registered {a.id} with {len(row['gates'])} gate(s)")
    return 0


def cmd_outcome(a):
    rows = load(a.file)
    hit = [r for r in rows if r.get("id") == a.id]
    if not hit:
        raise SystemExit(f"{a.id!r} is not in the register; register it before recording an outcome")
    if a.outcome not in OUTCOMES:
        raise SystemExit(f"unknown outcome {a.outcome!r}; known: {OUTCOMES}")
    before = {k: v for k, v in hit[0].items() if k not in MUTABLE}
    for r in rows:
        if r.get("id") == a.id:
            r["outcome"], r["outcome_detail"] = a.outcome, a.detail or ""
            after = {k: v for k, v in r.items() if k not in MUTABLE}
            if after != before:
                raise SystemExit("refusing to write: a field other than outcome/outcome_detail changed")
    with open(a.file, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"{a.id} -> {a.outcome}")
    return 0


def cmd_verify(a):
    rows = load(a.file)
    bad = 0
    seen = set()
    for r in rows:
        for k in REQUIRED:
            if k not in r:
                print(f"  {r.get('id', '?')}: missing required field {k!r}"); bad += 1
        if r.get("outcome") not in OUTCOMES:
            print(f"  {r.get('id', '?')}: unknown outcome {r.get('outcome')!r}"); bad += 1
        if r.get("id") in seen:
            print(f"  {r.get('id')}: duplicate id"); bad += 1
        seen.add(r.get("id"))
        if not (r.get("incumbent") or "").strip():
            print(f"  {r.get('id')}: no incumbent named (defect, not an error)")
        if not (r.get("gates") or []):
            print(f"  {r.get('id')}: no gates (cannot be refused)")
    print(f"{len(rows)} rows checked, {bad} structural problem(s)")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.set_defaults(fn=cmd_new)
    n.add_argument("--file", required=True); n.add_argument("--id", required=True)
    n.add_argument("--question", required=True); n.add_argument("--primary", required=True)
    n.add_argument("--gate", action="append", default=[])
    n.add_argument("--incumbent", default=""); n.add_argument("--placebo", default=None)
    n.add_argument("--successor-of", dest="successor_of", default=None)
    n.add_argument("--instrument-changed", dest="instrument_changed", default=None)
    n.add_argument("--dataset", default=None); n.add_argument("--code-ref", dest="code_ref", default=None)
    o = sub.add_parser("outcome"); o.set_defaults(fn=cmd_outcome)
    o.add_argument("--file", required=True); o.add_argument("--id", required=True)
    o.add_argument("--outcome", required=True); o.add_argument("--detail", default="")
    v = sub.add_parser("verify"); v.set_defaults(fn=cmd_verify)
    v.add_argument("--file", required=True)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
