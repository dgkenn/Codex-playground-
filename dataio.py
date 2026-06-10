"""dataio.py -- one loader for the gha_data tapes, plain or gzipped.

The collector gzips its bulk streams (fills/ticks/trades ~10.5x smaller -- the difference between
weeks and months of viable unattended collection), while historical files are plain .jsonl. Every
analysis tool reads through these helpers so both eras of data load identically.

    from dataio import jl_glob, jl_lines
    for fp in jl_glob("gha_data/fills_*.jsonl"):       # matches .jsonl AND .jsonl.gz
        for rec in jl_lines(fp):                       # dict per line; tolerant of a truncated
            ...                                        # final gz block (collector killed mid-write)
"""
from __future__ import annotations

import glob
import gzip
import json


def jl_glob(pattern):
    """Glob the plain pattern, its .gz sibling, AND date-partitioned subdirs (the collector commits
    into gha_data/YYYY-MM-DD/ so no directory ever holds months of files). De-duplicated, sorted."""
    pats = [pattern]
    if pattern.endswith(".jsonl"):
        pats.append(pattern + ".gz")
    if "/" in pattern:
        d, base = pattern.rsplit("/", 1)
        pats.append(f"{d}/*/{base}")
        if base.endswith(".jsonl"):
            pats.append(f"{d}/*/{base}.gz")
    out = set()
    for p in pats:
        out |= set(glob.glob(p))
    return sorted(out)


def jl_open(path):
    """Text-line generator, gz-or-plain, EOF-tolerant -- a drop-in for `open(path)` in line loops
    (callers keep their own json.loads/strip logic)."""
    op = gzip.open if path.endswith(".gz") else open
    try:
        with op(path, "rt") as fh:
            for ln in fh:
                yield ln
    except EOFError:
        return


def jl_lines(path):
    """Yield parsed JSON records; skips blank/corrupt lines; tolerates a truncated final gzip
    member (a SIGKILLed writer leaves one -- the data before it is fine)."""
    op = gzip.open if path.endswith(".gz") else open
    try:
        with op(path, "rt") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    yield json.loads(ln)
                except Exception:
                    continue
    except EOFError:
        return
