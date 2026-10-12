#!/usr/bin/env python3
"""MECHANICAL EXTRACTION -- not an experiment, no registration, no ledger row.

WHY. `bsde/docs/PROBE_2026_08_02_DOSEI_PEAK.md` establishes DOSE-I can replicate E242's propofol
peak-vs-dose null: 101 recordings (39 from `dosei_features.csv`, 62 from `dosei_holdout_features.csv`),
89-832 windows each, 2,095 bolus events, a validated exposure ladder. The one thing missing is
`alpha_peak_hz_wide` and `prominence`. This script computes exactly those two columns, on exactly the
windows the cached feature tables already describe, and nothing else -- no correlation with dose is
computed here (a registered experiment does that).

WINDOWS ARE NOT REDISCOVERED FROM SCRATCH, THE SELECTION LOGIC IS REUSED VERBATIM. `peeg_rows` and
`raw_two` are imported unchanged from `extract_dosei_features.py`; `WINDOW_S`, `STRIDE_S`, `SFREQ`,
`DATA_URL`, `PEEG_ZIP` are the same module-level constants. The per-recording loop below -- iterate
`peeg` timestamps, keep every `STRIDE_S`-th second at or past `WINDOW_S`, slice the trailing `WINDOW_S`
seconds of `x1`/`x2`, require >=90% finite samples, interpolate the rest -- is copied line for line from
`extract_dosei_features.py::main`. Only the per-window payload differs (two columns instead of
nineteen-plus-connectivity). Because the walk is independent (this script does not read the cached
`t_s` values and target them), the join against the cached tables in step 3 below is a genuine check that
the two walks agree, not a tautology.

SCOPE. Only the 101 recordings already covered by `dosei_features.csv` + `dosei_holdout_features.csv` are
processed -- the set this table needs to be comparable to, no more and no less. The recording order is
derived the same way `extract_dosei_features.py` derives it (RemoteZip member listing, intersected with
the local `dosei_pEEG.zip` table of contents), then filtered down to that target set, so a partial run
resumes in a stable order.

PROMINENCE, COPIED NOT REIMPLEMENTED (rule 20). `peak_and_prominence` below is copied verbatim from
`bsde/scripts/extract_vitaldb_prominence.py::peak_and_prominence`, which itself copied it from
`e239_prominence_gated_peak.py` (never imported here -- an experiments module, and this task is not
permitted to touch `bsde/src/bsde/experiments/`). It is the shipped `_iaf_peak`
(`bsde/src/bsde/candidates/seed.py`, PEAK_SEARCH_LO/HI = 5.0/15.0) line for line, plus one extra line:
the residual peak's height above the residual's own median, in robust standard deviations (MAD * 1.4826).
A diff against the shipped copy is a one-command check:

    diff <(sed -n '/^def peak_and_prominence/,/^$/p' bsde/scripts/extract_vitaldb_prominence.py) \\
         <(sed -n '/^def peak_and_prominence/,/^$/p' bsde/scripts/extract_dosei_prominence.py)

RESUMABLE, WITH RETRY. Recordings already present in the output (by `recording` column) are skipped
entirely at startup, matching `extract_dosei_features.py`'s own resume granularity. Rows are appended and
flushed+fsynced one at a time (never buffered across a whole recording), and existing rows are
de-duplicated on the (`recording`,`t_s`) key at load (rule 56 -- never trust this was the only writer).
The output file is always opened in APPEND mode once it exists, never "w" (rule 56's sibling bug, which
discarded 819 rows once already this project). Every network call funnels through
`bsde.ingestion.remote_zip._http_get_range` / `_urlopen` (the names `RemoteZip` binds at import time, so
those module attributes -- not `http_edf`'s -- are what must be patched); both are wrapped with retry and
exponential backoff (5 attempts, 2/4/8/16/32 s) on `RemoteDisconnected`, `URLError`, `socket.timeout`,
`ConnectionError`, generic `http.client.HTTPException` and `OSError`, matching
`extract_vitaldb_prominence.py`'s retry set exactly. This is a monkeypatch of the module attributes, not
an edit to `remote_zip.py` -- the S3/HTTP access logic itself stays verbatim.

Usage:
    scripts/heedb_run.sh python bsde/scripts/extract_dosei_prominence.py
    # smoke test:
    scripts/heedb_run.sh python bsde/scripts/extract_dosei_prominence.py --limit-recordings 2 \\
        --out /tmp/smoke.csv
"""
from __future__ import annotations

import argparse
import csv
import http.client
import os
import socket
import sys
import time
import urllib.error
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from bsde.ingestion.remote_zip import RemoteZip                                    # noqa: E402
import bsde.ingestion.remote_zip as remote_zip_mod                                 # noqa: E402
from extract_dosei_features import DATA_URL, PEEG_ZIP, SFREQ, peeg_rows, raw_two   # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")
OUT = os.path.join(RESULTS, "dosei_prominence.csv")
WINDOW_S = 30.0     # identical to extract_dosei_features.py
STRIDE_S = 5        # identical to extract_dosei_features.py

FIELDS = ["recording", "t_s", "alpha_peak_hz_wide", "prominence"]

RETRYABLE = (http.client.RemoteDisconnected, http.client.HTTPException, urllib.error.URLError,
             socket.timeout, ConnectionError, OSError)
MAX_ATTEMPTS = 5
BACKOFF_BASE_S = 2.0

PEAK_LO, PEAK_HI = 5.0, 15.0    # identical to seed.py's PEAK_SEARCH_LO/HI


def peak_and_prominence(data, sfreq):
    """Copied verbatim from extract_vitaldb_prominence.py::peak_and_prominence (rule 20).

    The shipped `_iaf_peak` line for line, plus the residual maximum's height above the residual median, in
    robust standard deviations of the residual. Nothing about the ANSWER (the frequency) changes.
    """
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


def _install_retrying_fetch(log=print):
    """Monkeypatch `remote_zip._http_get_range` / `_urlopen`. Does not edit remote_zip.py -- the HTTP
    range logic stays verbatim; only its resilience to a dropped connection changes. `RemoteZip` resolves
    both names from its own module's globals at call time (they were bound there by `from ... import`),
    so patching the module attributes here -- not `http_edf`'s -- covers every network call `index()` and
    `read_member()` make."""
    orig_get_range = remote_zip_mod._http_get_range
    orig_urlopen = remote_zip_mod._urlopen

    def _retry(fn, name):
        def wrapped(*args, **kwargs):
            last_exc = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    return fn(*args, **kwargs)
                except RETRYABLE as e:
                    last_exc = e
                    if attempt == MAX_ATTEMPTS:
                        raise
                    wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
                    log(f"      retry {attempt}/{MAX_ATTEMPTS} ({name}) after {type(e).__name__}: {e} "
                        f"-- sleeping {wait:.0f}s", flush=True)
                    time.sleep(wait)
            raise last_exc  # pragma: no cover -- unreachable
        return wrapped

    remote_zip_mod._http_get_range = _retry(orig_get_range, "_http_get_range")
    remote_zip_mod._urlopen = _retry(orig_urlopen, "_urlopen")


def _target_recordings():
    """Union of `recording` values in dosei_features.csv and dosei_holdout_features.csv -- the SAME
    windows this table must describe to be comparable to anything (rule 20)."""
    recs = set()
    for name in ("dosei_features.csv", "dosei_holdout_features.csv"):
        p = os.path.join(RESULTS, name)
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                recs.add(r["recording"])
    return recs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit-recordings", type=int, default=0,
                     help="process only the first N target recordings (smoke test)")
    a = ap.parse_args(argv)

    _install_retrying_fetch()

    target = _target_recordings()
    print(f"target: {len(target)} recordings (union of dosei_features.csv + "
          f"dosei_holdout_features.csv)", flush=True)
    assert len(target) > 0, "target recording set is empty -- cached tables did not load"

    pz = zipfile.ZipFile(os.path.abspath(PEEG_ZIP))
    have_peeg = {n.split("/")[-1].replace("_pEEG.csv", "")
                 for n in pz.namelist() if n.endswith("_pEEG.csv")}
    rz = RemoteZip(DATA_URL)
    all_recs = [m["name"].split("/")[-1][:-4] for m in rz.index() if m["name"].endswith(".csv")]
    all_recs = [r for r in all_recs if r in have_peeg]
    recs = [r for r in all_recs if r in target]
    missing = target - set(recs)
    if missing:
        print(f"WARNING: {len(missing)} target recordings not found in remote data.zip / "
              f"dosei_pEEG.zip intersection: {sorted(missing)[:10]}", flush=True)
    if a.limit_recordings:
        recs = recs[:a.limit_recordings]
    print(f"{len(recs)} recordings to process this run", flush=True)
    assert len(recs) > 0, "zero recordings resolved -- remote listing / local pEEG zip mismatch"

    out_path = os.path.abspath(a.out)
    done_recs = set()
    done_keys = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            rd = csv.DictReader(fh)
            existing = list(rd.fieldnames or [])
            if existing != FIELDS:
                raise ValueError(f"{out_path} exists with a different column set.\n  on disk: {existing}\n"
                                 f"  wanted : {FIELDS}\nDelete it deliberately or use a new path.")
            for r in rd:
                done_keys.add((r["recording"], r["t_s"]))
                done_recs.add(r["recording"])
    print(f"resuming: {len(done_keys)} rows / {len(done_recs)} recordings already present in "
          f"{out_path}", flush=True)

    todo = [r for r in recs if r not in done_recs]
    print(f"{len(todo)} of {len(recs)} recordings remain", flush=True)

    new_file = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n = int(WINDOW_S * SFREQ)
    n_written = 0
    n_skip_rec = 0
    first_bin_width = None
    with open(out_path, "a", newline="") as fh:      # APPEND, never "w" -- rule 56's sibling bug
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
            fh.flush()
            os.fsync(fh.fileno())
        for i, rec in enumerate(todo, 1):
            try:
                peeg = peeg_rows(pz, rec)
                x1, x2, t0 = raw_two(rz.read_member(f"data/{rec}.csv"))
            except Exception as e:                                        # noqa: BLE001
                print(f"   [{i}/{len(todo)}] {rec}: SKIP {type(e).__name__}: {e}", flush=True)
                n_skip_rec += 1
                continue
            if x1 is None:
                print(f"   [{i}/{len(todo)}] {rec}: SKIP non-uniform time axis", flush=True)
                n_skip_rec += 1
                continue
            wrote = 0
            for ts_abs in sorted(peeg):
                t = (ts_abs - t0).total_seconds()
                if round(t) % STRIDE_S or t < WINDOW_S:
                    continue
                key = (rec, f"{t:.0f}")
                if key in done_keys:
                    continue
                i1 = int(round(t * SFREQ))
                s1, s2 = x1[i1 - n:i1], x2[i1 - n:i1]
                if s1.size < n:
                    continue
                ok = np.isfinite(s1) & np.isfinite(s2)
                if ok.mean() < 0.9:
                    continue
                if not ok.all():
                    idx = np.flatnonzero(ok)
                    s1 = np.interp(np.arange(n), idx, s1[idx])
                data = s1[None, :]
                try:
                    pk, prom = peak_and_prominence(data, SFREQ)
                except Exception:                                         # noqa: BLE001
                    pk, prom = float("nan"), float("nan")
                if first_bin_width is None:
                    from bsde.candidates.seed import _mean_psd
                    f_arr, _ = _mean_psd(data, SFREQ)
                    first_bin_width = float(np.diff(f_arr)[0])
                    print(f"   PSD bin width measured on first window: {first_bin_width:.6g} Hz",
                          flush=True)
                row = {"recording": rec, "t_s": f"{t:.0f}",
                       "alpha_peak_hz_wide": "" if not np.isfinite(pk) else f"{pk:.10g}",
                       "prominence": "" if not np.isfinite(prom) else f"{prom:.10g}"}
                w.writerow(row)
                fh.flush()
                os.fsync(fh.fileno())          # a row on disk survives SIGKILL
                done_keys.add(key)
                wrote += 1
                n_written += 1
            print(f"   [{i}/{len(todo)}] {rec}: {wrote} windows written", flush=True)

    print(f"done: {n_written} rows written this run, {n_skip_rec} recordings skipped (fetch/axis "
          f"failure), {len(done_keys)} total rows now in {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
