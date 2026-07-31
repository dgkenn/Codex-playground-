"""Time-irreversibility on the Sleep-EDFx five-stage windows -- WITH A PHASE-RANDOMISED NULL PER WINDOW.

WHY THIS DEPOSIT AND WHY THIS MEASURE. Three independent routes have now placed REM with SLEEP rather than
with wake on this project's measures (E69's fraction-nearer-wake, E93/E95's axis position at 0.629 of the
way from wake to N3, E100's per-channel low-frequency version), **and in two of the three the placement was
measured to be substantially muscle.** REM is the one stage where arousal and experience come apart, so a
coordinate that puts REM with N2 is an arousal coordinate. E100 tested whether a better SPATIAL reduction
rescues it; it does not, and the nudge it gives vanishes after residualising on submental EMG.

`bsde/src/bsde/features/irreversibility.py` attacks it from the other side. Time-irreversibility is
**provably orthogonal to the whole spectral family** -- the autocovariance is symmetric in lag, so the PSD
and every summary of it is invariant under time reversal -- and the permutation form is **invariant to any
monotone amplitude transform**, so it cannot be muscle amplitude in the way E70/E100's results were. Those
two properties are exactly what rule 60 demands and no measure this project has run has either.

THE NULL IS CUT FROM THE SAME WINDOW, the way E104's sham was. `phase_randomise` produces a surrogate with
the IDENTICAL power spectrum and randomised phases; a stationary Gaussian process is time-reversible
whatever its spectrum, so the surrogate's irreversibility is zero up to sampling noise. **Every measure is
therefore emitted twice, real and surrogate, and any experiment consuming this table must use the
difference.** Validated before extraction against analytic ground truths: reversible processes returned
~0.0001, a sawtooth 0.116, skewed-innovation AR(1) 0.085, and surrogates of the irreversible cases
collapsed to ~0.0006 while preserving the aperiodic exponent to 0.5 % (+2.013 vs +2.023).

TWO SURROGATE DRAWS PER WINDOW, averaged. One draw is a sample from the null, not the null; with a single
draw the real-minus-surrogate difference carries the surrogate's own sampling noise at full weight, and
that noise is the same size as the effect in the reversible cases.

CHANNELS ARE MATCHED ON THEIR FULL LABEL, not a substring (rule 61), and kept separate -- frontal and
posterior -- because E100 established the whole-head reduction cannot express a local effect and there is
no reason to repeat that.

SCOPE. This script extracts. It computes no contrast, reads no stage label except to copy the worklist's
own `label` field through, and makes no claim.

    python bsde/scripts/extract_sleep_irreversibility.py --limit 40      # smoke
    python bsde/scripts/extract_sleep_irreversibility.py                 # full, resumable
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

from bsde.features.irreversibility import (increment_asymmetry,             # noqa: E402
                                           permutation_irreversibility,
                                           phase_randomise)
from bsde.ingestion.sleep_edfx import read_edf_window_http                  # noqa: E402

WORKLIST = os.path.join(HERE, "..", "results", "sleep_edfx_five_stage_worklist.json")
OUT = os.path.join(HERE, "..", "results", "sleep_edfx_irreversibility.csv")
FRONTAL_LABEL, POSTERIOR_LABEL = "EEG Fpz-Cz", "EEG Pz-Oz"
N_SURROGATE = 2
SEED = 20260731

MEASURES = ["irr3", "irr4", "incr"]
FIELDS = (["recording_id", "subject", "label", "sfreq", "n_samples"]
          + [f"{site}_{m}{suffix}"
             for site in ("frontal", "posterior")
             for m in MEASURES
             for suffix in ("", "_surr")])


def measures(x, rng):
    """Real and surrogate values for one channel. Same code path for both (rule 20)."""
    x = np.asarray(x, float)
    real = {"irr3": permutation_irreversibility(x, order=3),
            "irr4": permutation_irreversibility(x, order=4),
            "incr": increment_asymmetry(x)}
    acc = {k: [] for k in MEASURES}
    for _ in range(N_SURROGATE):
        s = phase_randomise(x, rng)
        acc["irr3"].append(permutation_irreversibility(s, order=3))
        acc["irr4"].append(permutation_irreversibility(s, order=4))
        acc["incr"].append(increment_asymmetry(s))
    surr = {k: float(np.nanmean(v)) if np.any(np.isfinite(v)) else float("nan")
            for k, v in acc.items()}
    return real, surr


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args(argv)

    rows = json.load(open(os.path.abspath(WORKLIST)))
    rows = [r for i, r in enumerate(rows) if i % a.of == a.shard]
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["recording_id"] for r in csv.DictReader(fh)}
    todo = [r for r in rows if r["recording_id"] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"shard {a.shard}/{a.of}: {len(rows)} windows, {len(done)} done, {len(todo)} to fetch",
          flush=True)

    rng = np.random.default_rng(SEED + a.shard)
    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n_ok = n_err = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for i, r in enumerate(todo, 1):
            try:
                data, ch, sf, _ = read_edf_window_http(
                    r["url"], window_s=r["window_s"], start_seconds=r["start_seconds"],
                    channel_regex="^EEG")
                names = [c.strip() for c in ch]
                if FRONTAL_LABEL not in names or POSTERIOR_LABEL not in names:
                    raise ValueError(f"expected both derivations, got {names}")
                d = np.asarray(data, float)
                row = {"recording_id": r["recording_id"], "subject": r["subject"],
                       "label": r["label"], "sfreq": f"{float(sf):.4g}",
                       "n_samples": int(d.shape[1])}
                for site, lab in (("frontal", FRONTAL_LABEL), ("posterior", POSTERIOR_LABEL)):
                    real, surr = measures(d[names.index(lab)], rng)
                    for m in MEASURES:
                        row[f"{site}_{m}"] = f"{real[m]:.8g}"
                        row[f"{site}_{m}_surr"] = f"{surr[m]:.8g}"
                w.writerow(row)
                fh.flush()
                n_ok += 1
            except Exception as e:                                          # noqa: BLE001
                n_err += 1
                if n_err <= 5:
                    print(f"   FAIL {r['recording_id']}: {type(e).__name__}: {e}", flush=True)
            if i % 100 == 0:
                print(f"   [{i}/{len(todo)}] ok={n_ok} err={n_err}", flush=True)
    print(f"done: {n_ok} ok, {n_err} failed -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
