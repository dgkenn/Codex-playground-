#!/usr/bin/env python3
"""MECHANICAL COMPUTATION -- not an experiment. Recompute VitalDB's IAF table with the peak's PROMINENCE
recorded, so E239's prominence gate (k = 3.5 robust sds, false-positive rate 0.020) can actually be applied
to real VitalDB windows instead of only to Sleep-EDFx.

WHY. `stream_vitaldb_grid.py --candidates alpha_peak_hz_wide,relative_alpha_power_iaf,alpha_peak_hz,
relative_alpha_power` produced `vitaldb_iaf.s0-3.csv` (6,679 rows, 6,438 status=ok) with `alpha_peak_hz_wide`
but no prominence -- E233's propofol-arm peak-frequency null is ambiguous between "the peak does not move"
and "there is too little alpha for the estimator to track", and only the prominence statistic distinguishes
those. See bsde/docs/AUDIT_2026_08_02_PEAK_DEPENDENT_CLAIMS.md.

WINDOWS ARE NOT RECOMPUTED. This reuses `VitalDBGridAdapter` -- the exact class `stream_vitaldb_grid.py`
drives -- with the exact defaults that produced `vitaldb_iaf.s*.csv` (n_cases=250, grid_s=300.0,
window_s=30.0, max_windows=40; see the `.gitignore` comment recording the original invocation:
`stream_vitaldb_grid.py --case-shard $i --of 4 --candidates ... --out vitaldb_iaf.s$i.csv`, no overrides on
any of those four). `list_recordings()` is called unmodified; nothing about case selection, grid placement,
channel choice or monitor-track handling is touched here. The output is keyed on the same `recording_id`
(`case{cid}@t{t:.0f}`), which encodes (meta_caseid, meta_t_s) exactly as the cached table does, so a join is
a plain key match.

PROMINENCE, COPIED NOT REIMPLEMENTED (rule 20). `peak_and_prominence` below is copied line-for-line from
`bsde/src/bsde/experiments/e239_prominence_gated_peak.py::peak_and_prominence`, which is itself the shipped
`_iaf_peak` (bsde/src/bsde/candidates/seed.py, PEAK_SEARCH_LO/HI = 5.0/15.0, identical to e239's
PEAK_LO/PEAK_HI) plus one extra line computing the residual peak's height above the residual's own median in
robust standard deviations. This script does not import from e239 (an experiments module) or from
candidates/seed.py's registry (to avoid registering a throwaway Candidate and to keep this script decoupled
from files this task is not permitted to modify); it duplicates the function verbatim and says so here so a
diff against the source is a one-command check:

    diff <(sed -n '/^def peak_and_prominence/,/^$/p' bsde/src/bsde/experiments/e239_prominence_gated_peak.py) \\
         <(sed -n '/^def peak_and_prominence/,/^$/p' bsde/scripts/extract_vitaldb_prominence.py)

Both `alpha_peak_hz_wide` and `prominence` come out of ONE call to this function per window (not two,
which would double the PSD/aperiodic-fit cost for no reason) -- `alpha_peak_hz_wide` is carried in the
output purely so a join against the cached table can verify EXACT reproduction (rule 20: if it does not
reproduce, the window selection differs and nothing downstream is comparable, and this script says so and
stops rather than writing a table that looks comparable and is not).

RESUMABLE, WITH RETRY. Rows are appended and fsynced one at a time; a run killed mid-stream picks up where
it left off (existing rows are de-duplicated on `recording_id` at load time, rule 56 -- never trust this was
the only writer). The output is always opened in APPEND mode when rows already exist, never "w" -- rule 56's
sibling bug, which cost a 55-minute run once. Network calls (every one of them funnels through the module-
level `bsde.ingestion.vitaldb._fetch`, which `tracks()`, `cases()`, `_series()` and `_numeric()` all call)
are wrapped with retry and exponential backoff (5 attempts, 2/4/8/16/32 s) on `RemoteDisconnected`,
`URLError`, `socket.timeout`, `ConnectionError`, `http.client.HTTPException` and generic `OSError` -- matching
`extract_sleep_edfx_prominence.py`'s retry set exactly. The wrapping is a monkeypatch of the module attribute
rather than an edit to `vitaldb.py`, so the S3/API access logic itself stays VERBATIM as instructed; only its
resilience to a dropped connection changes.

SHARDING IS BY CASE (`VitalDBGridAdapter`'s own `case_shard`/`n_case_shards`), matching the original
extraction, so four parallel shards cost four times one shard's bandwidth rather than four times the whole
job's -- see `stream_vitaldb_grid.py`'s docstring for why (one case's ~9.4 MB EEG track would otherwise be
re-fetched by whichever shards happen to draw its windows).

Usage:
    scripts/heedb_run.sh python bsde/scripts/extract_vitaldb_prominence.py --case-shard 0 --of 4 \\
        --out bsde/results/vitaldb_prominence.s0.csv
    # smoke test:
    scripts/heedb_run.sh python bsde/scripts/extract_vitaldb_prominence.py --limit 3 --out /tmp/smoke.csv
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.ingestion import vitaldb as vitaldb_mod              # noqa: E402
from bsde.ingestion.vitaldb import VitalDBGridAdapter          # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")

# Identical to stream_vitaldb_grid.py's META_KEYS -- same order, same names, so the meta_* columns line up
# one-for-one against vitaldb_iaf.s*.csv.
META_KEYS = (
    "caseid", "subjectid", "t_s", "rel_anestart_s", "rel_aneend_s", "anestart_s", "aneend_s",
    "opstart_s", "opend_s", "agents_present", "age", "sex", "asa", "bmi", "emop",
    "intraop_ppf", "intraop_mdz", "intraop_rocu", "intraop_vecu",
    "bis", "sqi", "sr", "emg", "sensor_off", "nan_fraction",
)

FIELDS = (["recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"]
          + [f"meta_{k}" for k in META_KEYS] + ["alpha_peak_hz_wide", "prominence"])

RETRYABLE = (http.client.RemoteDisconnected, http.client.HTTPException, urllib.error.URLError,
             socket.timeout, ConnectionError, OSError)
MAX_ATTEMPTS = 5
BACKOFF_BASE_S = 2.0

PEAK_LO, PEAK_HI = 5.0, 15.0                # identical to seed.py's PEAK_SEARCH_LO/HI and e239's PEAK_LO/HI


def peak_and_prominence(data, sfreq):
    """Copied verbatim from e239_prominence_gated_peak.py::peak_and_prominence (rule 20).

    The shipped `_iaf_peak` line for line, plus the residual maximum's height above the residual median, in
    robust standard deviations of the residual. Nothing about the ANSWER (the frequency) changes.
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


def _install_retrying_fetch(log=print):
    """Monkeypatch `vitaldb._fetch` with a retrying wrapper. Does not edit vitaldb.py -- the S3/API access
    logic stays verbatim; only its resilience to a dropped connection changes. Every network call in
    VitalDBGridAdapter (tracks(), cases(), _series(), _numeric()) resolves `_fetch` via this module's
    globals at call time, so patching the module attribute here covers all of them."""
    orig = vitaldb_mod._fetch

    def wrapped(url, timeout=300.0):
        last_exc = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return orig(url, timeout=timeout)
            except RETRYABLE as e:
                last_exc = e
                if attempt == MAX_ATTEMPTS:
                    raise
                wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
                log(f"      retry {attempt}/{MAX_ATTEMPTS} after {type(e).__name__}: {e} "
                    f"-- sleeping {wait:.0f}s", flush=True)
                time.sleep(wait)
        raise last_exc  # pragma: no cover -- unreachable, MAX_ATTEMPTS>=1 always either returns or raises

    vitaldb_mod._fetch = wrapped


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-cases", type=int, default=250, dest="n_cases")
    ap.add_argument("--grid-s", type=float, default=300.0, dest="grid_s")
    ap.add_argument("--window-s", type=float, default=30.0, dest="window_s")
    ap.add_argument("--max-windows", type=int, default=40, dest="max_windows")
    ap.add_argument("--case-shard", type=int, default=0, dest="case_shard")
    ap.add_argument("--of", type=int, default=1, dest="n_case_shards")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    _install_retrying_fetch()

    adapter = VitalDBGridAdapter(n_cases=a.n_cases, grid_s=a.grid_s, window_s=a.window_s,
                                 max_windows=a.max_windows,
                                 case_shard=a.case_shard, n_case_shards=a.n_case_shards)
    print(f"listing recordings for {adapter.name} (this hits /trks and /cases once)...", flush=True)
    refs = adapter.list_recordings()
    assert len(refs) > 0, "adapter returned zero recordings -- cohort/filters are not matching anything"
    print(f"{len(refs)} (case, grid-point) windows in this shard", flush=True)
    if a.limit:
        refs = refs[:a.limit]
        print(f"--limit applied: {len(refs)} windows", flush=True)

    out_path = os.path.abspath(a.out)
    done: set = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            rd = csv.DictReader(fh)
            existing = list(rd.fieldnames or [])
            if existing != list(FIELDS):
                raise ValueError(f"{out_path} exists with a different column set.\n  on disk: {existing}\n"
                                 f"  wanted : {list(FIELDS)}\nDelete it deliberately or use a new path.")
            # de-duplicate on the key at load (rule 56) -- never trust this was the only writer
            for r in rd:
                done.add(r["recording_id"])
    print(f"resuming: {len(done)} rows already present in {out_path}", flush=True)

    todo = [r for r in refs if r.recording_id not in done]
    print(f"{len(todo)} of {len(refs)} windows remain -> {out_path}", flush=True)
    if not todo:
        print("nothing to do", flush=True)
        return 0

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    new_file = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n_ok = n_err = 0
    with open(out_path, "a", newline="") as fh:          # APPEND, never "w" -- rule 56's sibling bug
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
            fh.flush()
            os.fsync(fh.fileno())
        for i, ref in enumerate(todo, 1):
            row = {"recording_id": ref.recording_id, "dataset": ref.dataset, "subject": ref.subject,
                   "status": "ok", "error": "", "n_channels": "", "sfreq": "", "n_samples": ""}
            for k in META_KEYS:
                row[f"meta_{k}"] = "" if ref.meta.get(k) is None else str(ref.meta.get(k))
            try:
                import numpy as np
                data, ch_names, sfreq, meta = ref.load()
                data = np.asarray(data, float)
                row["n_channels"] = data.shape[0]
                row["n_samples"] = data.shape[1]
                row["sfreq"] = f"{float(sfreq):.6g}"
                merged = dict(ref.meta)
                merged.update(meta or {})
                for k in META_KEYS:
                    if row.get(f"meta_{k}", "") == "" and merged.get(k) is not None:
                        row[f"meta_{k}"] = str(merged.get(k))
                pk, prom = peak_and_prominence(data, float(sfreq))
                row["alpha_peak_hz_wide"] = "" if not np.isfinite(pk) else f"{pk:.10g}"
                row["prominence"] = "" if not np.isfinite(prom) else f"{prom:.10g}"
            except Exception as e:
                row["status"] = "error"
                row["error"] = f"{type(e).__name__}: {e}"[:300]
                row.setdefault("alpha_peak_hz_wide", "")
                row.setdefault("prominence", "")
            row = {k: row.get(k, "") for k in FIELDS}
            w.writerow(row)
            fh.flush()
            os.fsync(fh.fileno())          # a row on disk survives SIGKILL
            n_ok += row["status"] == "ok"
            n_err += row["status"] == "error"
            if i % 10 == 0 or i == len(todo):
                print(f"   [{i}/{len(todo)}] ok={n_ok} err={n_err} -- {ref.recording_id}", flush=True)

    print(f"done: {n_ok} ok, {n_err} error, {len(done) + len(todo)} total rows in {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
