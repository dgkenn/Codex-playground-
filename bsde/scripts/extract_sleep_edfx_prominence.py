#!/usr/bin/env python3
"""MECHANICAL COMPUTATION -- not an experiment. Recompute Sleep-EDFx with the peak's PROMINENCE recorded,
so E239's registered P3 (the real-data control) can actually run.

WHY. `extract_sleep_edfx_iaf.py` produced `sleep_edfx_iaf.csv` with `alpha_peak_hz_wide` but not the
prominence statistic E239 gates on -- P3 could only report the ungated picture. This script is that same
extraction, unchanged in every respect that affects window selection, with one extra column.

WINDOWS ARE NOT RECOMPUTED. Reads `sleep_edfx_five_stage_worklist.json` verbatim -- the same 710
(recording, stage) rows, same URLs, same start_seconds/window_s -- exactly as `extract_sleep_edfx_iaf.py`
does. Nothing about window selection or channel selection differs; see that script's docstring for why
`^EEG ` is the right channel regex here.

PROMINENCE, COPIED NOT REIMPLEMENTED (rule 20). `peak_and_prominence` below is copied line-for-line from
`bsde/src/bsde/experiments/e239_prominence_gated_peak.py::peak_and_prominence`, which is itself the
shipped `_iaf_peak` (bsde/src/bsde/candidates/seed.py) plus one extra line computing the residual peak's
height above the residual's own median in robust standard deviations. This script does not import from
e239 (an experiments module) to avoid coupling a mechanical script to an experiment file; it duplicates
the function verbatim and says so here so a diff against the source is a one-command check:

    diff <(sed -n '140,163p' bsde/src/bsde/experiments/e239_prominence_gated_peak.py) \\
         <(sed -n '/^def peak_and_prominence/,/^$/p' bsde/scripts/extract_sleep_edfx_prominence.py)

RESUMABLE. Rows are appended and fsynced one at a time; a run killed mid-stream picks up where it left
off. On load, existing rows are de-duplicated on `recording_id` (rule 56) rather than trusting this was
the only writer. Network calls retry with exponential backoff (5 attempts, 2/4/8/16/32 s) on
`RemoteDisconnected`, `URLError`, `socket.timeout`, `ConnectionError` and `http.client.HTTPException`,
matching `extract_sleep_edfx_iaf.py` exactly -- an earlier extraction died on the first of those.

Usage:
    python bsde/scripts/extract_sleep_edfx_prominence.py            # full run, resumable
    python bsde/scripts/extract_sleep_edfx_prominence.py --limit 3   # smoke test
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

RESULTS = os.path.join(HERE, "..", "results")
WORKLIST = os.path.join(RESULTS, "sleep_edfx_five_stage_worklist.json")
OUT = os.path.join(RESULTS, "sleep_edfx_prominence.csv")

CHANNEL_REGEX = "^EEG "                     # identical to extract_sleep_edfx_iaf.py

FIELDS = ["recording_id", "subject", "label", "url", "start_seconds", "window_s",
          "status", "error", "n_channels", "sfreq", "n_samples",
          "alpha_peak_hz_wide", "prominence"]

RETRYABLE = (http.client.RemoteDisconnected, http.client.HTTPException, urllib.error.URLError,
             socket.timeout, ConnectionError, OSError)
MAX_ATTEMPTS = 5
BACKOFF_BASE_S = 2.0

PEAK_LO, PEAK_HI = 5.0, 15.0                # identical to e239.PEAK_LO, PEAK_HI


def peak_and_prominence(data, sfreq):
    """Copied verbatim from e239_prominence_gated_peak.py::peak_and_prominence (rule 20).

    The shipped `_iaf_peak` line for line, plus the residual maximum's height above the residual median,
    in robust standard deviations of the residual. Nothing about the ANSWER (the frequency) changes.
    """
    import numpy as np
    from bsde.candidates.seed import _mean_psd
    from bsde.features.aperiodic import fit_aperiodic
    f, p = _mean_psd(data, sfreq)
    ap = fit_aperiodic(f, p, fit_lo_hz=1.0, fit_hi_hz=45.0)
    m = (f >= PEAK_LO) & (f <= PEAK_HI) & (p > 0)
    if m.sum() < 5:
        return float("nan"), float("nan")
    resid = np.log10(p[m]) - (ap["offset"] - ap["exponent"] * np.log10(f[m]))
    i = int(np.nanargmax(resid))
    if i == 0 or i == resid.size - 1:
        return float("nan"), float("nan")
    med = float(np.median(resid))
    mad = float(np.median(np.abs(resid - med)))
    scale = 1.4826 * mad
    prom = float((resid[i] - med) / scale) if scale > 0 else float("inf")
    return float(f[m][i]), prom


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
                   "n_channels": "", "sfreq": "", "n_samples": "",
                   "alpha_peak_hz_wide": "", "prominence": ""}
            try:
                data, ch_names, sfreq, meta = _fetch_with_retry(j["url"], j["window_s"], j["start_seconds"])
                import numpy as np
                data = np.asarray(data, float)
                row["n_channels"] = data.shape[0]
                row["n_samples"] = data.shape[1]
                row["sfreq"] = f"{float(sfreq):.6g}"
                pk, prom = peak_and_prominence(data, float(sfreq))
                row["alpha_peak_hz_wide"] = "" if not np.isfinite(pk) else f"{pk:.10g}"
                row["prominence"] = "" if not np.isfinite(prom) else f"{prom:.10g}"
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
