#!/usr/bin/env python3
"""Reduce the 3.3 GB quant condition_occurrence table to the ~1 MB file the analyses actually need.

WHY THIS EXISTS. Every aetiology analysis from R398 onward opens
`/tmp/eeg_probe/heedb_omop_quant/condition_occurrence.csv` — 74 million rows, 3.3 GB — and reduces it to one
boolean per patient. That is minutes of CSV parsing per run, and worse, the big file has now been **reaped by
the container twice in a single session** (2026-07-29), each time costing a 22-minute rebuild. A one-megabyte
derived table is faster to load and small enough that losing it is trivial.

WHAT IT PRESERVES. Exactly the reduction the analyses perform: a patient is anoxic if any
`condition_source_value`, normalized, starts with one of `AETIOLOGY["anoxic"]`. The same `norm` and the same
prefix list are imported from `heedb_bs_ascertainment`, not re-implemented, so the two cannot drift
(catalogue rule 20: when two scripts compute the same quantity, they must not be separate implementations).

It also records EVERY aetiology group in `AETIOLOGY`, not just anoxic, so a future decomposition does not
need the big table back.

OUTPUT `/tmp/eeg_probe/heedb_aetiology_compact.csv`:
    patient,anoxic,<one column per other AETIOLOGY group>,n_conditions

USAGE
    python analysis/heedb_aetiology_compact.py
    # then in an analysis, prefer the compact file and fall back to the big one:
    #     from heedb_aetiology_compact import load_anoxic
    #     anox = load_anoxic()
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heedb_bs_ascertainment import AETIOLOGY, norm

OMOP_Q = os.environ.get("OMOP_QUANT", "/tmp/eeg_probe/heedb_omop_quant")
COMPACT = os.environ.get("HEEDB_AET_COMPACT", "/tmp/eeg_probe/heedb_aetiology_compact.csv")
GROUPS = sorted(AETIOLOGY)


def build(src=None, dest=COMPACT):
    src = src or f"{OMOP_Q}/condition_occurrence.csv"
    if not os.path.exists(src):
        raise SystemExit(f"FATAL: {src} missing — see CLAUDE.md for the rebuild command.")
    hit = {}
    n_cond = {}
    n = 0
    with open(src) as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            n += 1
            if p not in hit:
                hit[p] = {g: False for g in GROUPS}
                n_cond[p] = 0
            n_cond[p] += 1
            c = norm(r.get("condition_source_value"))
            if not c:
                continue
            for g in GROUPS:
                if not hit[p][g] and any(c.startswith(x) for x in AETIOLOGY[g]):
                    hit[p][g] = True
            if n % 10_000_000 == 0:
                print(f"  {n:,} rows, {len(hit):,} patients", flush=True)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["patient"] + GROUPS + ["n_conditions"])
        for p in sorted(hit):
            w.writerow([p] + [int(hit[p][g]) for g in GROUPS] + [n_cond[p]])
    os.replace(tmp, dest)          # atomic, so a reaped/interrupted run never leaves a half file
    print(f"read {n:,} condition rows for {len(hit):,} patients -> {dest}")
    for g in GROUPS:
        k = sum(1 for p in hit if hit[p][g])
        print(f"   {g:>22}: {k:,} patients ({100*k/max(len(hit),1):.1f}%)")
    # rule 5: a filter that matches nothing is a broken filter, not an absent disease
    assert any(hit[p]["anoxic"] for p in hit), "no anoxic patients matched — the prefix list is broken"
    return dest


def load_anoxic(compact=COMPACT, src=None):
    """{patient_id: bool}. Prefers the compact table; builds it from the big one if absent."""
    if not os.path.exists(compact):
        build(src=src, dest=compact)
    out = {}
    with open(compact) as fh:
        for r in csv.DictReader(fh):
            try:
                out[int(r["patient"])] = bool(int(r["anoxic"]))
            except (KeyError, TypeError, ValueError):
                continue
    assert out, f"{compact} parsed to nothing"
    return out


if __name__ == "__main__":
    build()
