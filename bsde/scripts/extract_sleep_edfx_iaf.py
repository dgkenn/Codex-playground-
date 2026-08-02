#!/usr/bin/env python3
"""MECHANICAL COMPUTATION -- not an experiment. Compute the four IAF-anchored candidates
(`alpha_peak_hz_wide`, `relative_alpha_power_iaf`, `alpha_peak_hz`, `relative_alpha_power`) on the
SAME 710 (recording, stage) windows as `sleep_edfx_five_stage.csv`, so a second deposit carries them
and Challenge D's band-anchoring hypothesis becomes testable across two deposits.

WINDOWS ARE NOT RECOMPUTED. `sleep_edfx_five_stage_worklist.json` is the committed record of exactly
which (url, start_seconds, window_s) triple produced every row of `sleep_edfx_five_stage.csv` -- this
script reads it verbatim and changes nothing about window selection. The only thing that differs from
that table is which candidates are evaluated (four, all from the registry) rather than seventeen.

CHANNEL SELECTION mirrors `build_sleep_edfx_labels.py` and `build_sleep_edfx_five_stage.py`'s sibling
extractors: '^EEG ' selects the two same-rate EEG derivations (Fpz-Cz, Pz-Oz) and excludes EOG/EMG/
thermistor/event channels at other sampling rates. Verified against `sleep_edfx_five_stage.csv` itself
(n_channels=2, sfreq=100) before this script was written -- see the join/reproduction check this
script prints at the end.

RESUMABLE. Rows are appended and fsynced one at a time; a run killed mid-stream picks up where it left
off. On load, existing rows are de-duplicated on `recording_id` (rule 56) rather than trusting this was
the only writer. Network calls retry with exponential backoff (5 attempts, 2/4/8/16/32 s) on
`RemoteDisconnected`, `URLError`, `socket.timeout`, `ConnectionError` and `http.client.HTTPException` --
today's run of a sibling extractor died on exactly the first of those after 13 subjects.

Usage:
    python bsde/scripts/extract_sleep_edfx_iaf.py            # full run, resumable
    python bsde/scripts/extract_sleep_edfx_iaf.py --limit 3   # smoke test
"""
from __future__ import annotations

import argparse
import csv
import http.client
import json
import os
import socket
import sys
import time
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.ingestion.http_edf import read_edf_window_http          # noqa: E402
from bsde.candidates.seed import seed_registry                     # noqa: E402
from bsde.candidates.registry import REGISTRY                      # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")
WORKLIST = os.path.join(RESULTS, "sleep_edfx_five_stage_worklist.json")
OUT = os.path.join(RESULTS, "sleep_edfx_iaf.csv")

CHANNEL_REGEX = "^EEG "
CANDIDATE_NAMES = ["alpha_peak_hz_wide", "relative_alpha_power_iaf", "alpha_peak_hz", "relative_alpha_power"]

FIELDS = (["recording_id", "subject", "label", "url", "start_seconds", "window_s",
           "status", "error", "n_channels", "sfreq", "n_samples"] + CANDIDATE_NAMES)

RETRYABLE = (http.client.RemoteDisconnected, http.client.HTTPException, urllib.error.URLError,
             socket.timeout, ConnectionError, OSError)
MAX_ATTEMPTS = 5
BACKOFF_BASE_S = 2.0


def _fetch_with_retry(url: str, window_s: float, start_seconds: float, log=print):
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return read_edf_window_http(url, window_s=window_s, start_seconds=start_seconds,
                                        channel_regex=CHANNEL_REGEX)
        except RETRYABLE as e:
            last_exc = e
            if attempt == MAX_ATTEMPTS:
                raise
            wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
            log(f"      retry {attempt}/{MAX_ATTEMPTS} after {type(e).__name__}: {e} -- sleeping {wait:.0f}s")
            time.sleep(wait)
    raise last_exc  # pragma: no cover -- unreachable, MAX_ATTEMPTS>=1 always either returns or raises above


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    work = json.load(open(WORKLIST))
    assert len(work) > 0, f"worklist {WORKLIST} is empty -- nothing to compute"
    print(f"worklist: {len(work)} (recording, stage) rows from {WORKLIST}")

    seed_registry()
    cands = [REGISTRY.get(n) for n in CANDIDATE_NAMES]
    assert len(cands) == 4, f"expected 4 candidates, got {len(cands)}"
    print(f"candidates: {[c.name for c in cands]}")

    jobs = sorted(work, key=lambda r: r["recording_id"])
    if a.limit:
        jobs = jobs[:a.limit]

    out_path = os.path.abspath(a.out)
    done: set = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            rd = csv.DictReader(fh)
            existing = list(rd.fieldnames or [])
            if existing != FIELDS:
                raise ValueError(f"{out_path} exists with a different column set.\n  on disk: {existing}\n"
                                 f"  wanted : {FIELDS}\nDelete it deliberately or use a new path.")
            # de-duplicate on the key at load (rule 56) -- never trust this was the only writer
            for r in rd:
                done.add(r["recording_id"])
    print(f"resuming: {len(done)} rows already present in {out_path}")

    todo = [j for j in jobs if j["recording_id"] not in done]
    print(f"{len(todo)} of {len(jobs)} rows remain to fetch -> {out_path}")
    if not todo:
        print("nothing to do")
        return 0

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    new_file = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n_ok = n_err = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
            fh.flush()
            os.fsync(fh.fileno())
        for i, j in enumerate(todo, 1):
            row = {"recording_id": j["recording_id"], "subject": j["subject"], "label": j["label"],
                   "url": j["url"], "start_seconds": f"{j['start_seconds']:.3f}",
                   "window_s": f"{j['window_s']:.1f}", "status": "ok", "error": "",
                   "n_channels": "", "sfreq": "", "n_samples": ""}
            for c in cands:
                row[c.name] = ""
            try:
                data, ch_names, sfreq, meta = _fetch_with_retry(j["url"], j["window_s"], j["start_seconds"])
                import numpy as np
                data = np.asarray(data, float)
                row["n_channels"] = data.shape[0]
                row["n_samples"] = data.shape[1]
                row["sfreq"] = f"{float(sfreq):.6g}"
                merged = dict(j.get("meta") or {})
                merged.update(meta or {})
                for c in cands:
                    try:
                        v = c.fn(data, ch_names, sfreq, merged)
                        row[c.name] = "" if v is None or not np.isfinite(v) else f"{float(v):.10g}"
                    except Exception as e:                        # one bad candidate must not lose the row
                        row[c.name] = ""
                        row["error"] = (row["error"] + f"|{c.name}:{type(e).__name__}").lstrip("|")
            except Exception as e:
                row["status"] = "error"
                row["error"] = f"{type(e).__name__}: {e}"[:300]
            w.writerow(row)
            fh.flush()
            os.fsync(fh.fileno())          # a row on disk survives SIGKILL
            n_ok += row["status"] == "ok"
            n_err += row["status"] == "error"
            if i % 10 == 0 or i == len(todo):
                print(f"   [{i}/{len(todo)}] ok={n_ok} err={n_err} -- {j['recording_id']}", flush=True)

    print(f"done: {n_ok} ok, {n_err} error, {len(done) + len(todo)} total rows in {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
