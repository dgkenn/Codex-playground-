#!/usr/bin/env python3
"""Cache the per-TRIAL features behind E28's label, so label-validity questions stop costing an S3 pass.

`build_eegmmidb_bci_label.py` computes one band-power vector per trial and then throws every one of them
away, keeping only the subject-level AUC. That was fine while the AUC was the deliverable. It is not fine
now: E28's gate failed on a property of the LABEL, and every question about a label — its reliability, its
ceiling, how it behaves under resampling — needs the trials, not the summary.

WHAT THIS DOES NOT DO. It does not recompute anything. `_band_power`, `CHANNELS`, `BANDS`, `EPOCH` and the
event handling are **imported from the builder**, not reimplemented, so the cached features are the same
numbers the label was built from by construction rather than by agreement. Error-catalogue rule 20 says to
diff two computations of the same quantity; the cheaper move, where it is available, is to have only one.

Output: `bsde/results/eegmmidb_trials.csv`, one row per trial —

    subject, task, run, trial, y, f0..f5      y = 1 for right fist (T2), 0 for left (T1)

Roughly 104 subjects x 2 tasks x 45 trials x 6 features. Small enough to commit, which matters because this
container's disk does not survive reclamation.

Resumable: reads the subjects already present per task and fetches only the remainder. Shardable by subject
(`--shard k --of n`), because the cost is the per-run HTTPS fetch and nothing else.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "src")))
sys.path.insert(0, HERE)

from bsde.ingestion.eegmmidb import (EXECUTED_LR_RUNS, IMAGERY_LR_RUNS,      # noqa: E402
                                     events, read_window, record_duration_s, subjects)
from build_eegmmidb_bci_label import CHANNELS, EPOCH, _band_power            # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
OUT = os.path.join(RESULTS, "eegmmidb_trials.csv")
N_FEATURES = 6
FIELDS = ["subject", "task", "run", "trial", "y"] + [f"f{i}" for i in range(N_FEATURES)]


def _trials(sub: str, runs):
    """Per-trial band powers for one subject, using the builder's own epoching."""
    ch_idx, out = None, []
    for run in runs:
        ev = events(sub, run)
        full, names, sf, _ = read_window(sub, run, 0.0, record_duration_s(sub, run))
        full = np.asarray(full, float)
        if ch_idx is None:
            ch_idx = [names.index(c) for c in CHANNELS if c in names]
            if len(ch_idx) < len(CHANNELS):
                raise ValueError(f"montage lacks {set(CHANNELS) - set(names)}")
        n_ep = int(round((EPOCH[1] - EPOCH[0]) * sf))
        for k, (onset, label, _dur) in enumerate(ev):
            if label == "T0":
                continue
            i0 = int(round((onset + EPOCH[0]) * sf))
            seg = full[ch_idx, i0:i0 + n_ep]
            if seg.shape[1] < n_ep or not np.isfinite(seg).all():
                continue
            out.append((run, k, 1.0 if label == "T2" else 0.0, _band_power(seg, sf)))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", choices=("imagery", "executed"), default="imagery")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    runs = IMAGERY_LR_RUNS if a.task == "imagery" else EXECUTED_LR_RUNS
    done = set()
    if os.path.exists(a.out):
        for r in csv.DictReader(open(a.out, newline="")):
            done.add((r["subject"], r["task"]))
    subs = [s for i, s in enumerate(subjects()) if i % a.of == a.shard]
    todo = [s for s in subs if (s, a.task) not in done]
    print(f"{a.task}: {len(todo)} of {len(subs)} subjects to fetch (shard {a.shard}/{a.of})")

    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for s in todo:
            try:
                rows = _trials(s, runs)
            except Exception as e:                                          # noqa: BLE001
                print(f"   {s} {a.task}: {type(e).__name__}: {e}", flush=True)
                continue
            for run, k, y, f in rows:
                rec = {"subject": s, "task": a.task, "run": run, "trial": k, "y": y}
                rec.update({f"f{i}": float(v) for i, v in enumerate(f)})
                w.writerow(rec)
            fh.flush()
            print(f"   {s} {a.task}: {len(rows)} trials", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
