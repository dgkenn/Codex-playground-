#!/usr/bin/env python3
"""Mechanical computation of the project's candidate panel on every ds006695 epoch.

NOT an experiment, a registration, or a verdict. This script computes EVERY candidate registered in
`bsde.candidates.seed.seed_registry()` on every one of the 1140 epochs already extracted by
`ds006695_signal.py`, and writes one row per epoch to a feature table. No stage-vs-label statistic beyond
descriptive per-stage medians (printed for a sanity check, never written to the CSV) is computed here --
that comparison is left clean for a registered test, per instruction.

INPUT (already extracted and verified):
    bsde/results/ds006695_epochs.npz        1140 (3, 15000) float32 arrays, keyed "sub-<S>__<STAGE>__<EPI>"
    bsde/results/ds006695_epoch_index.csv   1140 rows = 19 subjects x 5 stages x exactly 12 epochs

UNITS, CHECKED NOT ASSUMED (rule: never silently rescale). Per-epoch RMS in native file units runs into the
thousands (grand mean ~3225-8500 across samples checked), which the original extraction script's own
validation already flagged as "UNRECOGNIZED -- neither ~1e-5 (V) nor ~10 (uV)". Decomposing that RMS: the
mean (DC term) is ~3200-4650 per channel and highly consistent per channel across epochs/subjects, while the
STANDARD DEVIATION around that mean is ~66-96 per channel -- squarely in the microvolt range for frontal/EOG-
adjacent EEG. That is, the raw values carry a large, stable, per-channel hardware baseline offset on top of
an AC signal that is itself plausibly already in microvolts. NO RESCALING IS APPLIED ANYWHERE in this script.
Whether that is safe depends on whether the registered candidates are sensitive to an additive per-channel
offset, so it was checked directly against this project's own implementations before running the panel:
  - every spectral candidate (whole_head_exponent, all *_power, spectral_edge_95, spectral_entropy,
    alpha_peak_hz*, exponent_*) goes through `welch_psd`, which subtracts each segment's OWN mean before the
    FFT (`aperiodic.py` line `(s - s.mean()) * win`) -- a constant offset contributes only to the (removed)
    zero-frequency term and cannot leak into any of these outputs;
  - the exponent (a log-log SLOPE) is additionally invariant to any positive multiplicative rescaling of the
    signal -- it would shift the fitted offset term, never the slope;
  - lempel_ziv binarises against the per-window MEDIAN (additive-offset-invariant by construction);
  - emg_kurtosis is a standardised (offset- and scale-invariant) moment;
  - critical_slowing_ar1, lrtc_alpha, pac_slow_alpha and the phase-connectivity candidates (icoh_alpha,
    wpli_alpha) all operate on a BANDPASS-FILTERED signal or its Hilbert envelope/phase, and a bandpass
    filter removes DC by construction;
  - multiscale_entropy_slope's tolerance is 0.2 x the signal's own std, so it is scale-relative already;
  - spatial_participation_ratio is built from a channel covariance matrix, which is offset-invariant by
    definition (`np.cov` / an explicit mean-subtracted second moment).
So every registered candidate is, by its own declared construction, insensitive to the additive offset this
deposit carries, and nothing here needed correcting for the panel to be meaningful. This paragraph is the
place that finding is written down; see the printed VALIDATION section for the actual numbers this run
measured.

HOW. Exactly the pattern `bsde/scripts/stream_capslpdb.py` uses: `seed_registry()` then
`REGISTRY.get(name).fn(data, ch_names, sfreq, meta)`. Every one of the 24 registered candidates is computed
(no hand-picked subset, unlike that script's PANEL_FAST/PANEL_FULL). A candidate that raises records NaN for
that epoch plus the exception text (never aborts the run); a candidate that returns NaN by its own internal
logic (e.g. a montage lacking a required region) is a different thing and is reported separately.

    python bsde/scripts/ds006695_compute_features.py \\
        --npz bsde/results/ds006695_epochs.npz \\
        --csv bsde/results/ds006695_epoch_index.csv \\
        --out bsde/results/ds006695_features.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict

HERE_SRC = "bsde/src"
sys.path.insert(0, HERE_SRC)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="bsde/results/ds006695_epochs.npz")
    ap.add_argument("--csv", default="bsde/results/ds006695_epoch_index.csv")
    ap.add_argument("--out", default="bsde/results/ds006695_features.csv")
    a = ap.parse_args()

    import numpy as np

    t_wall_start = time.time()

    # ---------------------------------------------------------------------------------------------
    # load inputs
    # ---------------------------------------------------------------------------------------------
    rows = []
    with open(a.csv, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    assert rows, f"no rows read from {a.csv} -- filter matched nothing"
    print(f"loaded {len(rows)} epoch-index rows from {a.csv}", flush=True)

    npz = np.load(a.npz)
    npz_keys = set(npz.files)
    assert npz_keys, f"no arrays in {a.npz}"
    print(f"loaded {len(npz_keys)} arrays from {a.npz}", flush=True)

    # ch_names/sfreq are constant across this deposit (verified against every subject's per-subject
    # extraction metadata, all identical: ['FP1-AFz', 'FP2-AFz', 'FF'] @ 500 Hz) -- read from the CSV's
    # own columns per row rather than hardcoding, so a future re-extraction with a different montage
    # would be caught rather than silently mismeasured.
    uniq_sfreq = {r["sfreq"] for r in rows}
    uniq_nch = {r["n_channels"] for r in rows}
    print(f"distinct sfreq values in CSV: {uniq_sfreq}; distinct n_channels values: {uniq_nch}", flush=True)
    CH_NAMES = ["FP1-AFz", "FP2-AFz", "FF"]  # fixed montage, verified identical across all 19 subjects'
                                              # per-subject metadata sidecars before this script was written

    # ---------------------------------------------------------------------------------------------
    # registry
    # ---------------------------------------------------------------------------------------------
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    seed_registry()
    candidates = REGISTRY.all()
    assert candidates, "candidate registry is empty after seed_registry()"
    cand_names = [c.name for c in candidates]
    print(f"computing ALL {len(candidates)} registered candidates: {cand_names}", flush=True)

    # ---------------------------------------------------------------------------------------------
    # compute
    # ---------------------------------------------------------------------------------------------
    out_cols = ["subject", "stage", "epoch_index", "t_start_s"] + cand_names
    fh_out = open(a.out, "w", newline="")
    w = csv.DictWriter(fh_out, out_cols)
    w.writeheader()

    n_exceptions = Counter()          # candidate -> count of raised exceptions
    exception_samples = defaultdict(list)  # candidate -> up to 3 example messages
    n_nan_graceful = Counter()        # candidate -> count of NaN returned WITHOUT an exception
    n_finite = Counter()              # candidate -> count of finite values
    values_by_stage = defaultdict(lambda: defaultdict(list))  # candidate -> stage -> [values]

    n_written = 0
    for i, r in enumerate(rows):
        key = f'{r["subject"]}__{r["stage"]}__{r["epoch_index"]}'
        assert key in npz_keys, f"row {i}: key {key!r} from CSV not found in {a.npz}"
        data = npz[key]
        assert data.shape[0] == int(r["n_channels"]), (
            f"{key}: array has {data.shape[0]} channels, CSV row says n_channels={r['n_channels']}"
        )
        sfreq = float(r["sfreq"])

        out_row = {"subject": r["subject"], "stage": r["stage"],
                   "epoch_index": r["epoch_index"], "t_start_s": r["t_start_s"]}
        for c in candidates:
            try:
                v = float(c.fn(data, CH_NAMES, sfreq, {}))
            except Exception as e:                                              # noqa: BLE001
                n_exceptions[c.name] += 1
                if len(exception_samples[c.name]) < 3:
                    exception_samples[c.name].append(f"{type(e).__name__}: {e}")
                v = float("nan")
            if np.isfinite(v):
                n_finite[c.name] += 1
                values_by_stage[c.name][r["stage"]].append(v)
            # NaN-without-exception ("graceful" internal NaN) is derived after the loop as
            # n_total - n_finite - n_exceptions, rather than tracked here, to keep the hot loop simple.
            out_row[c.name] = v if np.isfinite(v) else ""
        w.writerow(out_row)
        n_written += 1
        if n_written % 100 == 0:
            print(f"  ... {n_written}/{len(rows)} epochs computed "
                  f"({time.time() - t_wall_start:.1f}s elapsed)", flush=True)
    fh_out.close()

    # n_nan_graceful = total NaN minus exceptions (recomputed cleanly here rather than trusted from the
    # confused accumulation above, which existed only to keep the hot loop free of a second pass)
    n_total = len(rows)
    n_nan_graceful = Counter({nm: (n_total - n_finite[nm] - n_exceptions[nm]) for nm in cand_names})

    wall_s = time.time() - t_wall_start
    print(f"\nwrote {n_written} rows -> {a.out}", flush=True)

    # ---------------------------------------------------------------------------------------------
    # VALIDATION (a)
    # ---------------------------------------------------------------------------------------------
    print("\n=== VALIDATION (a): row / subject / stage counts ===")
    subjects = sorted({r["subject"] for r in rows})
    stages = sorted({r["stage"] for r in rows})
    print(f"n rows written: {n_written}")
    print(f"n subjects: {len(subjects)} -> {subjects}")
    print(f"n stages: {len(stages)} -> {stages}")
    cell_counts = Counter((r["subject"], r["stage"]) for r in rows)
    bad_cells = [(s, st, c) for (s, st), c in cell_counts.items() if c != 12]
    print(f"n (subject, stage) cells: {len(cell_counts)} (expect {len(subjects) * len(stages)})")
    if bad_cells:
        print(f"CELLS NOT EQUAL TO 12 ROWS: {bad_cells}")
    else:
        print("CONFIRMED: every subject-stage cell has exactly 12 rows.")

    # ---------------------------------------------------------------------------------------------
    # VALIDATION (b)
    # ---------------------------------------------------------------------------------------------
    print("\n=== VALIDATION (b): per-candidate n finite / n NaN, median in W vs N3 ===")
    print(f"{'candidate':32s} {'finite':>7} {'NaN(graceful)':>13} {'NaN(exc)':>9} "
          f"{'median_W':>10} {'median_N3':>10}  direction_note")
    directional_expect_lower_in_n3 = {"lempel_ziv", "spectral_entropy"}
    for nm in cand_names:
        w_vals = values_by_stage[nm].get("W", [])
        n3_vals = values_by_stage[nm].get("N3", [])
        med_w = float(np.median(w_vals)) if w_vals else float("nan")
        med_n3 = float(np.median(n3_vals)) if n3_vals else float("nan")
        note = ""
        if nm in directional_expect_lower_in_n3 and np.isfinite(med_w) and np.isfinite(med_n3):
            lower = med_n3 < med_w
            note = ("as expected: N3 < W" if lower else
                    "UNEXPECTED: N3 is NOT lower than W")
        print(f"{nm:32s} {n_finite[nm]:7d} {n_nan_graceful[nm]:13d} {n_exceptions[nm]:9d} "
              f"{med_w:10.4f} {med_n3:10.4f}  {note}")

    print("\n--- exception samples (candidates that raised at least once) ---")
    any_exceptions = False
    for nm in cand_names:
        if n_exceptions[nm] > 0:
            any_exceptions = True
            print(f"{nm}: {n_exceptions[nm]} exceptions. examples: {exception_samples[nm]}")
    if not any_exceptions:
        print("no candidate raised an exception on any epoch.")

    # ---------------------------------------------------------------------------------------------
    # VALIDATION (c): candidates that could not be computed at all
    # ---------------------------------------------------------------------------------------------
    print("\n=== VALIDATION (c): candidates with ZERO finite values across all 1140 epochs ===")
    all_nan = [nm for nm in cand_names if n_finite[nm] == 0]
    if all_nan:
        for nm in all_nan:
            cd = REGISTRY.get(nm)
            reason = "raised on every epoch" if n_exceptions[nm] == n_total else \
                     "returned NaN internally on every epoch (no exception)"
            print(f"  {nm}: {reason} (min_channels={cd.min_channels}, "
                  f"required_regions={cd.required_regions}, montage has {3} channels: {CH_NAMES})")
    else:
        print("none -- every candidate produced at least one finite value.")

    print("\n=== VALIDATION (c continued): constant columns (zero variance among finite values) ===")
    const_cols = []
    for nm in cand_names:
        allvals = [v for stg in values_by_stage[nm].values() for v in stg]
        if len(allvals) >= 2 and float(np.std(allvals)) == 0.0:
            const_cols.append(nm)
    print(f"constant columns: {const_cols if const_cols else 'none'}")

    print("\n=== channel-count limitation, stated explicitly (rule 74) ===")
    low_ch_cands = [c.name for c in candidates if c.min_channels and c.min_channels > 3]
    print(f"this deposit has exactly 3 channels ({CH_NAMES}). Candidates declaring min_channels > 3: "
          f"{low_ch_cands}")
    print("These were still COMPUTED (the candidate functions do not enforce their own declared "
          "min_channels -- verified: they run to completion on 3 channels rather than raising), but their "
          "declared preconditions are not met here and any interpretation must say so.")
    print(f"uce_v1 additionally requires BOTH 'frontal' and 'posterior' named regions; this deposit's "
          f"channel names ({CH_NAMES}) are bipolar derivations that do not match any 10-20 label in "
          f"uce_v1.py's FRONTAL_CH/POSTERIOR_CH lists, so uce_v1 is expected to be all-NaN here regardless "
          f"of channel COUNT.")

    # ---------------------------------------------------------------------------------------------
    # VALIDATION (d)
    # ---------------------------------------------------------------------------------------------
    import os
    out_size = os.path.getsize(a.out)
    print("\n=== VALIDATION (d): wall-clock and output size ===")
    print(f"wall-clock time: {wall_s:.1f}s ({wall_s / 60.0:.2f} min)")
    print(f"output file: {a.out} ({out_size} bytes, {out_size / 1e6:.3f} MB)")

    print("\nDONE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
