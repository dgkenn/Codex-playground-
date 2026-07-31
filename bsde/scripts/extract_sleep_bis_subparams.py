"""The four BIS subparameters on the five-stage sleep windows -- the muscle control Q35 owes for `bis_rbr`.

WHY. E69 found `exponent_high` places REM with sleep rather than wake, and reframed it: wake is the outlier
(W +0.070 against N1 +2.104, N2 +1.985, N3 +1.599, REM +2.089), so the feature separates AWAKE from ASLEEP
with REM counted as asleep despite its wake-like spectrum.

**The muscle explanation survives at group level and it is the one that matters.** `exponent_high` is fitted
over 20-40 Hz, where surface EMG lives -- E43 measured that a broadband slope through that band is MORE
muscle-associated than BIS. Wake carries more muscle tone than any sleep stage. So a flatter 20-40 Hz slope
at wake is exactly what muscle would produce, and E69's subject-level null against `emg_index` does not
settle it: `emg_index` is a SCALP-EEG proxy computed from Fpz-Cz and Pz-Oz, and those channels showed no
REM atonia at all (REM 0.312 against N3 0.127), so the proxy fails its own premise.

**Sleep-EDFx PSG ships a real submental EMG channel and our extraction kept only EEG.** This fetches it.

WHAT THE CHANNEL IS, stated because it changes what can be asked of it. In Sleep-EDF Expanded the submental
EMG is recorded at **1 Hz** -- an envelope, not a raw trace. That is useless for a spectrum and ideal here:
the question is only "how much muscle tone was there in this window", and a mean over the envelope answers
it directly. No filtering, no epoching, no assumptions.

THE WINDOWS ARE NOT RECOMPUTED. `sleep_edfx_five_stage_worklist.json` is the committed record of exactly
which (subject, stage, start_seconds, window_s) the EEG table came from, so this reads the same list and
joins on `recording_id`. Re-deriving the windows would risk a silent mismatch that a join could not detect.

    python bsde/scripts/extract_sleep_emg.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.features.bis_subparams import bis_subparams                     # noqa: E402
from bsde.ingestion.sleep_edfx import read_edf_window_http                 # noqa: E402

WORKLIST = os.path.join(HERE, "..", "results", "sleep_edfx_five_stage_worklist.json")
OUT = os.path.join(HERE, "..", "results", "sleep_edfx_bis_subparams.csv")
FIELDS = ["recording_id", "subject", "label", "bis_rbr", "bis_bsr", "bis_quazi", "bis_sfs",
          "n_channels", "n_samples", "sfreq", "channels"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    rows = json.load(open(os.path.abspath(WORKLIST)))
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["recording_id"] for r in csv.DictReader(fh)}
    todo = [r for r in rows if r["recording_id"] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(rows)} windows in the worklist, {len(done)} done, {len(todo)} to fetch", flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n_ok = n_err = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, r in enumerate(todo, 1):
            try:
                data, ch, sf, _ = read_edf_window_http(
                    r["url"], window_s=r["window_s"], start_seconds=r["start_seconds"],
                    channel_regex="^EEG ")
                d = np.asarray(data, float)
                if d.ndim == 1:
                    d = d[None, :]
                # Per channel, then median across channels -- the convention f_whole_head_exponent uses.
                per = [bis_subparams(d[c][np.isfinite(d[c])], float(sf)) for c in range(d.shape[0])]
                row = {"recording_id": r["recording_id"], "subject": r["subject"],
                       "label": r["label"], "n_channels": d.shape[0],
                       "n_samples": int(d.shape[1]), "sfreq": f"{float(sf):.4g}",
                       "channels": "|".join(ch)}
                for k in ("bis_rbr", "bis_bsr", "bis_quazi", "bis_sfs"):
                    v = np.nanmedian([p[k] for p in per])
                    row[k] = "" if not np.isfinite(v) else f"{float(v):.6g}"
                w.writerow(row)
                n_ok += 1
            except Exception as e:                                        # noqa: BLE001
                n_err += 1
                if n_err <= 5:
                    print(f"   FAIL {r['recording_id']}: {type(e).__name__}: {e}", flush=True)
            fh.flush()
            if i % 25 == 0 or i == len(todo):
                print(f"   [{i}/{len(todo)}] ok={n_ok} err={n_err}", flush=True)
    print(f"   wrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
