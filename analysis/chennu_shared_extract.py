#!/usr/bin/env python3
"""Re-extract chennu through the SHARED feature path, to remove E52's last pipeline asymmetry.

WHY. E52 confirmed E50's prediction -- `exponent_low` and `exponent_high` agree in sign across chennu and
ds005620 (P(sign disagreement) = 0.0000 for both) where `whole_head_exponent` flips (P = 0.7071). But
chennu's sub-bands came from the older per-deposit extraction and ds005620's from
`analysis/eeg_features_common.py`. The ESTIMATOR was identical in both -- `subband_exponents` from
`bsde.features.exotic` -- yet the montage, the 180 s analysis window and the 250 Hz resample were not.

`exponent_high` agreed to **0.006** across that difference, which is either strong evidence the difference
is immaterial or luck at n = 20. This script removes the ambiguity instead of arguing about it: same code,
same window, same montage, same rate, both deposits.

WHAT IT DOES NOT CHANGE. chennu is still a SEDATION study -- subjects score 26.9/40 at the deepest level --
and level 4 is RECOVERY (plasma 0 / 447 / 900 / 290 ug/L), not a deeper level. Both facts are properties of
the deposit and survive any re-extraction.

    scripts/heedb_run.sh python analysis/chennu_shared_extract.py --out /tmp/eeg_probe/chennu_shared.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "bsde", "src")))
from eeg_features_common import features_from_array                          # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="/tmp/eeg_probe/chennu_shared.csv")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    from bsde.ingestion.chennu import ChennuRemoteZipAdapter
    # The adapter's default labels path is relative ("results/chennu_labels.csv") and only resolves when
    # run from bsde/. Pass it absolutely so the script works from the repo root like every other extractor.
    labels = os.path.abspath(os.path.join(HERE, "..", "bsde", "results", "chennu_labels.csv"))
    ad = ChennuRemoteZipAdapter(labels_csv=labels)
    refs = ad.list_recordings()
    print(f"{len(refs)} chennu recordings", flush=True)

    done = set()
    if os.path.exists(a.out):
        with open(a.out) as fh:
            done = {r["recording_id"] for r in csv.DictReader(fh)}
        print(f"resuming: {len(done)} present", flush=True)

    fh = w = None
    n_ok = n_fail = 0
    t0 = time.time()
    for ref in refs:
        rid = getattr(ref, "recording_id", None) or getattr(ref, "id", str(ref))
        if rid in done:
            continue
        try:
            data_uv, ch_names, sfreq, meta = ref.load()
            feats = features_from_array(data_uv, sfreq, ch_names)
        except Exception as exc:                                             # noqa: BLE001
            n_fail += 1
            print(f"   FAIL {rid}: {type(exc).__name__}: {exc}", flush=True)
            continue
        row = {"recording_id": rid,
               "subject": getattr(ref, "subject", "") or meta.get("subject", ""),
               "sedation_level": meta.get("sedation_level", ""),
               "plasma_propofol_ug_per_L": meta.get("plasma_propofol_ug_per_L", ""),
               "mean_reaction_time_ms": meta.get("mean_reaction_time_ms", ""),
               "n_correct_of_40": meta.get("n_correct_of_40", "")}
        row.update(feats)
        if w is None:
            fh = open(a.out, "a", newline="")
            w = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if os.path.getsize(a.out) == 0:
                w.writeheader()
        w.writerow(row)
        fh.flush()
        n_ok += 1
        if n_ok % 10 == 0:
            print(f"   {n_ok} ok / {n_fail} fail   {(time.time() - t0) / n_ok:.1f}s each", flush=True)
        if a.limit and n_ok >= a.limit:
            break
    print(f"\n{n_ok} written, {n_fail} failed -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
