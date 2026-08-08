#!/usr/bin/env python3
"""Metrics over any register conforming to preregistry/SPEC.md. Stdlib only.

    python -m bsde.preregistry.metrics --file reg.jsonl [--file other.jsonl ...] [--by-site]

Reports the quantities a published literature cannot supply, because a literature contains only the
experiments that produced a reportable result:

    machinery-failure rate   gate_failed / all
    overstatement factor     1 / (positive / all)
    qualification rate       positives whose own detail text hedges
    failures per gate         gate_failed / total gates carried -- controls for gating intensity
    no-incumbent rate        rows that named nothing to beat
    ungated rate             rows that could not have been refused

`--by-site` treats each --file as one site and reports between-site spread, which is the whole point of
running this across labs rather than within one.
"""
from __future__ import annotations

import argparse, collections, json, math, os

HEDGES = ("but ", "however", "qualif", "caveat", "not licensed", "underpowered",
          "not decisive", "suggestive", "limitation")


def canon(o):
    o = (o or "").strip().lower()
    for k in ("gate_failed", "withdrawn", "blocked", "closed", "absent", "positive",
              "negative", "registered", "mixed"):
        if o.startswith(k):
            return k
    return "other"


def load(paths):
    out = []
    for p in paths:
        rows = []
        for line in open(p):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        out.append((os.path.basename(p), rows))
    return out


def summarise(rows):
    n = len(rows)
    if not n:
        return None
    cls = [canon(r.get("outcome")) for r in rows]
    c = collections.Counter(cls)
    run = [r for r, k in zip(rows, cls) if k != "registered"]
    nrun = len(run) or 1
    pos = c["positive"]
    concl = c["positive"] + c["negative"] + c["absent"]
    gates = sum(len(r.get("gates") or []) for r in rows)
    posrows = [r for r, k in zip(rows, cls) if k == "positive"]
    hedged = sum(1 for r in posrows
                 if any(h in (r.get("outcome_detail") or "").lower() for h in HEDGES))
    return {
        "n": n, "n_run": len(run), "counts": dict(c),
        "machinery_rate": c["gate_failed"] / nrun,
        "positive_rate_all": pos / nrun,
        "positive_rate_concluded": (pos / concl) if concl else float("nan"),
        "overstatement_factor": (nrun / pos) if pos else float("inf"),
        "qualification_rate": (hedged / pos) if pos else float("nan"),
        "gates_total": gates,
        "failures_per_gate": (c["gate_failed"] / gates) if gates else float("nan"),
        "mean_gates": gates / n,
        "no_incumbent_rate": sum(1 for r in rows if not (r.get("incumbent") or "").strip()) / n,
        "ungated_rate": sum(1 for r in rows if not (r.get("gates") or [])) / n,
    }


def show(name, s):
    print(f"\n--- {name} ---")
    print(f"  registrations {s['n']}  (run: {s['n_run']})")
    for k, v in sorted(s["counts"].items(), key=lambda t: -t[1]):
        print(f"     {k:12s} {v:4d}")
    print(f"  machinery-failure rate    {s['machinery_rate']:7.1%}")
    print(f"  positive rate (of run)    {s['positive_rate_all']:7.1%}")
    print(f"  positive rate (concluded) {s['positive_rate_concluded']:7.1%}")
    print(f"  OVERSTATEMENT FACTOR      {s['overstatement_factor']:7.2f}x")
    print(f"  qualification rate        {s['qualification_rate']:7.1%}  (positives that hedge)")
    print(f"  mean gates per design     {s['mean_gates']:7.2f}")
    print(f"  failures per gate carried {s['failures_per_gate']:7.4f}")
    print(f"  named no incumbent        {s['no_incumbent_rate']:7.1%}")
    print(f"  carried no gate           {s['ungated_rate']:7.1%}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", action="append", required=True)
    ap.add_argument("--by-site", action="store_true")
    a = ap.parse_args(argv)
    sites = load(a.file)
    allrows = [r for _, rows in sites for r in rows]
    s = summarise(allrows)
    if s is None:
        raise SystemExit("no rows")
    show("POOLED", s)
    if a.by_site and len(sites) > 1:
        per = []
        for nm, rows in sites:
            si = summarise(rows)
            if si:
                show(nm, si); per.append(si)
        print("\n--- BETWEEN-SITE SPREAD (the reason to run this across labs) ---")
        for k in ("machinery_rate", "positive_rate_all", "overstatement_factor",
                  "failures_per_gate", "mean_gates"):
            v = [p[k] for p in per if math.isfinite(p[k])]
            if len(v) > 1:
                print(f"  {k:24s} min {min(v):.4f}  max {max(v):.4f}  "
                      f"range {max(v)-min(v):.4f}")
    elif a.by_site:
        print("\n  --by-site given but only one register supplied; between-site spread needs >= 2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
