#!/usr/bin/env python3
"""Convert this project's own REGISTRATION_LEDGER.jsonl to the portable SPEC.md format.

Exists for two reasons. It shows the format is adoptable from an existing register rather than only
from scratch, and it lets `metrics.py` be validated against E330's independently-written numbers on the
same data -- catalogue rule 23, which says self-written code plus self-written tests share blind spots
and a second implementation is what catches them.
"""
from __future__ import annotations
import argparse, json


def canon(o):
    o = (o or "").strip().lower()
    for k in ("gate_failed", "withdrawn", "blocked", "closed", "absent",
              "positive", "negative", "registered"):
        if o.startswith(k):
            return k
    if "not confirmed" in o or "refuted" in o:
        return "negative"
    if "confirmed" in o:
        return "positive"
    return "closed"          # 'mixed' and other free text map to a non-conclusive class


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    n = 0
    with open(a.out, "w") as fh:
        for line in open(a.src):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            row = {"id": r.get("id", ""),
                   "registered_utc": (r.get("registered_date") or "") + "T00:00:00+00:00",
                   "question": r.get("question", ""), "primary": r.get("primary", ""),
                   "gates": r.get("gates") or [], "incumbent": r.get("incumbent") or "",
                   "placebo": r.get("placebo"), "outcome": canon(r.get("outcome")),
                   "outcome_detail": r.get("outcome_detail") or ""}
            for k_src, k_dst in (("successor_of", "successor_of"),
                                 ("instrument_changed", "instrument_changed"),
                                 ("deposit", "dataset"), ("file", "code_ref")):
                if r.get(k_src):
                    row[k_dst] = r[k_src]
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            n += 1
    print(f"converted {n} rows -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
