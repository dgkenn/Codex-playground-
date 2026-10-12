"""Resting-state graph measures on the Dreyer BCI database -- the cohort that can test WHY E124 failed.

WHY THIS DEPOSIT AND WHY NOW. E86 found `ge_norm` predicts BCI accuracy in Stieger's 62 subjects at
+0.3069 [+0.0495, +0.5343]. E124 tried to replicate that in eegmmidb and returned NOT REPLICATED with an
interval, -0.1298 [-0.3225, +0.0735], that EXCLUDES an effect of E86's size. E108 had fixed four
explanations in advance, and **the first on that list was that the outcomes are different constructs**:

    "Stieger's accuracy is ONLINE BCI CONTROL over real sessions. `imagery_auc` is CROSS-VALIDATED
     DECODABILITY ... Decodability is an upper bound on control; a subject can be decodable and still
     control badly."

That explanation is currently unfalsifiable, because no cohort in this project has online control besides
Stieger's. **Dreyer et al. 2023 (Sci Data, PMID 37670009; data at Zenodo 10.5281/zenodo.8089820) has it**:
87 participants, and `Perfomances.csv` ships `Perf_RUN_3` .. `Perf_RUN_6`, the OpenViBE ONLINE
classification accuracy per run. That is Stieger's construct, not eegmmidb's.

THE PREDICTOR TRANSFERS VERBATIM, WHICH IS THE PART THAT MAKES THIS A CLEAN TEST. E86 and E108 both define
`ge_norm` per subject as the MEAN of an eyes-open and an eyes-closed resting run -- a definition fixed
before either cohort's data was read, precisely so the better run could not be chosen afterwards. Dreyer
ships exactly that pair for every subject: `<S>_OE_baseline.gdf` and `<S>_CE_baseline.gdf`, 87 of each.
Nothing about the predictor has to be adapted, reinterpreted or chosen here.

HOW 27.5 GB IS READ WITHOUT DOWNLOADING 27.5 GB. The archive is a single Zip64 file. `RemoteZip` reads the
central directory over HTTP Range requests and then only the members asked for; Zip64 support was added
for this archive (it previously refused rather than misread, which was correct). Each baseline member is
24.5 MB, and only a PREFIX of each is inflated -- `WINDOW_S` seconds is all a resting-state graph measure
needs, and a prefix keeps the whole thing in memory with nothing written to disk.

GRAPH CODE IS IMPORTED, NOT REIMPLEMENTED (rule 20). `graph_features` comes from
`extract_stieger_graph62.py`, the same function that produced E86's numbers and E124's, so a difference
between cohorts cannot be a difference between implementations.

SCOPE. This script extracts. It fits nothing, correlates nothing with performance, and makes no claim; the
registration that uses it is separate and is written before this runs to completion.

    python bsde/scripts/extract_dreyer_graph.py --limit 3        # smoke
    python bsde/scripts/extract_dreyer_graph.py --shard k --of 6
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from bsde.features.connectivity import wpli_matrix                          # noqa: E402
from bsde.ingestion.remote_zip import RemoteZip                            # noqa: E402
# BOTH imported, and from the eegmmidb extractor rather than from Stieger's (rule 20). `graph_features`
# is Stieger's own, re-exported; `periodic_features_at` is the sfreq-PARAMETERISED transcription that
# E124's numbers came from -- Stieger's `periodic_features` hardcodes 1000 Hz through a module constant
# and would silently mis-fit a 512 Hz deposit. Using E124's exact path is what makes a Dreyer-vs-eegmmidb
# difference a difference between cohorts rather than between implementations.
from extract_eegmmidb_graph import (ALPHA_HI, ALPHA_LO, WPLI_OVERLAP,       # noqa: E402
                                    WPLI_WINDOW_S, graph_features, periodic_features_at)

ZIP_URL = "https://zenodo.org/records/8089820/files/BCI%20Database.zip?download=1"
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
OUT = os.path.join(RESULTS, "dreyer_graph.csv")

WINDOW_S = 120.0            # resting segment per run; E86 used 2 min of rest per run
# A PREFIX WOULD BE CHEAPER AND DOES NOT WORK, which is worth recording so it is not retried. GDF stores
# its event table AFTER the data, and mne's reader seeks there during header parsing -- so an inflated
# prefix raises `IndexError` in `_read_gdf_header` before a single sample is decoded. Truncating a GDF is
# not like truncating an EDF. Members are therefore read whole (24.5 MB each, held in memory one at a
# time and never written to disk); only WINDOW_S seconds of the decoded signal is analysed.
FIELDS = ["subject", "dataset", "run", "status", "error", "n_channels", "sfreq", "n_samples",
          "ge", "cl", "deg", "ge_norm", "cl_norm", "smallworld", "modularity", "strength_cv",
          "iaf", "alpha_prom"]


def _read_gdf_prefix(blob: bytes):
    """Decode a GDF prefix with mne. Returns (data uV, channel names, sfreq) or raises.

    The blob is a PREFIX of the file, so the header's declared record count overruns what is present.
    mne reads what is there; the guard below is that we require at least WINDOW_S seconds of samples and
    refuse the member otherwise, rather than silently analysing a shorter segment (rule 5)."""
    import tempfile
    import mne
    with tempfile.NamedTemporaryFile(suffix=".gdf", delete=False) as fh:
        fh.write(blob)
        path = fh.name
    try:
        raw = mne.io.read_raw_gdf(path, preload=True, verbose="ERROR")
        sf = float(raw.info["sfreq"])
        picks = [i for i, n in enumerate(raw.ch_names)
                 if not re.search(r"(EOG|EMG|ECG|status|ref)", n, re.I)]
        if not picks:
            picks = list(range(len(raw.ch_names)))
        x = raw.get_data(picks=picks) * 1e6            # mne returns volts; this project works in uV
        names = [raw.ch_names[i] for i in picks]
        return x, names, sf
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=-1)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args(argv)
    if a.shard >= 0:
        root, ext = os.path.splitext(a.out)
        a.out = f"{root}.s{a.shard}{ext}"

    rng = np.random.default_rng(20260801)
    rz = RemoteZip(ZIP_URL)
    members = [m for m in rz.index()
               if re.search(r"_(OE|CE)_baseline\.gdf$", m["name"])]
    jobs = []
    for m in members:
        base = m["name"].split("/")[-1]
        mm = re.match(r"([A-C]\d+)_(OE|CE)_baseline\.gdf$", base)
        if not mm:
            continue
        jobs.append({"member": m["name"], "subject": mm.group(1), "run": mm.group(2),
                     "dataset": mm.group(1)[0]})
    jobs.sort(key=lambda j: (j["subject"], j["run"]))
    if a.shard >= 0:
        jobs = [j for i, j in enumerate(jobs) if i % a.of == a.shard]
    if a.limit:
        jobs = jobs[:a.limit]

    out_path = os.path.abspath(a.out)
    done = set()
    import glob as _glob
    root, ext = os.path.splitext(os.path.abspath(a.out).replace(f".s{a.shard}", "")
                                 if a.shard >= 0 else os.path.abspath(a.out))
    for p in {out_path, *_glob.glob(f"{root}.s*{ext}"), f"{root}{ext}"}:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            for r in csv.DictReader(open(p, newline="")):
                done.add((r["subject"], r["run"]))
    todo = [j for j in jobs if (j["subject"], j["run"]) not in done]
    print(f"{len(members)} baseline members; {len(jobs)} in this shard, {len(done)} done, "
          f"{len(todo)} to fetch -> {out_path}", flush=True)
    if not todo:
        return 0

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for i, j in enumerate(todo, 1):
            row = {"subject": j["subject"], "dataset": j["dataset"], "run": j["run"],
                   "status": "ok", "error": ""}
            try:
                blob = rz.read_member(j["member"])
                x, names, sf = _read_gdf_prefix(blob)
                need = int(WINDOW_S * sf)
                if x.shape[1] < need:
                    raise ValueError(f"recording has {x.shape[1]} samples, need {need} "
                                     f"({WINDOW_S:.0f}s at {sf:g} Hz)")
                seg = x[:, :need]
                ok = np.isfinite(seg)
                if ok.mean() < 0.99:
                    raise ValueError(f"only {ok.mean():.3f} finite")
                row.update({"n_channels": seg.shape[0], "sfreq": f"{sf:g}",
                            "n_samples": seg.shape[1]})
                W = wpli_matrix(seg, float(sf), ALPHA_LO, ALPHA_HI,
                                window_s=WPLI_WINDOW_S, overlap=WPLI_OVERLAP, debias=True)
                feats = dict(graph_features(W, rng))
                feats.update(periodic_features_at(seg, float(sf)))
                for k in ("ge", "cl", "deg", "ge_norm", "cl_norm", "smallworld", "modularity",
                          "strength_cv", "iaf", "alpha_prom"):
                    v = feats.get(k)
                    row[k] = "" if v is None or not np.isfinite(v) else f"{float(v):.6g}"
            except Exception as e:                                          # noqa: BLE001
                row.update({"status": "error", "error": f"{type(e).__name__}: {e}"[:200]})
            w.writerow(row)
            fh.flush()
            print(f"   [{i}/{len(todo)}] {j['subject']} {j['run']} {row['status']} "
                  f"ge_norm={row.get('ge_norm', '')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
