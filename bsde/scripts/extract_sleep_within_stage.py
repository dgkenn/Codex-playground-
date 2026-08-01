"""Multiple windows INSIDE one contiguous same-stage block, with the real submental EMG on each --
the muscle control E111 said its successor needs.

WHY THIS EXACT SHAPE. E107 found that time-irreversibility, a measure PROVABLY orthogonal to the power
spectrum, places REM at +0.9974 on the wake-to-N3 axis -- essentially at deep sleep, against the aperiodic
exponent's +0.4788. Its G5 then reported that 81 % of that effect disappears after residualising on
submental EMG, and since the permutation form cannot read muscle AMPLITUDE, the residue was interpreted as
muscle WAVEFORM SHAPE.

**E111 then showed that interpretation cannot be sustained, and named the fix.** Residualising on submental
EMG removed 121.3 % of the effect in the 0.5-12 Hz band -- more than all of it, the signature of
over-adjustment. Submental EMG amplitude is itself a state variable: it falls monotonically from wake to N3
and is at its floor in REM (E100 put REM's EMG position at +1.094). Regressing on it removes STATE variance
along with any artefact, which is rule 13's collider shape. E111's own verdict text says what a valid
successor needs, verbatim:

    "a muscle control that is not a within-subject regression on a state-tracking variable. Options are a
     deposit with pharmacological paralysis ... or a within-STAGE contrast where EMG varies but state does
     not."

This is the second option. Inside ONE contiguous block of ONE scored stage, the state label is constant by
construction, and submental tone still varies window to window. If irreversibility is reading muscle, it
must move with EMG there. If it does not, the muscle explanation for E107 fails on a test that no amount of
state variance can contaminate -- because there is no state variance to contaminate it.

WHY THE EXISTING TABLES CANNOT ANSWER IT. `sleep_edfx_irreversibility.csv` and `sleep_edfx_emg.csv` carry
EXACTLY ONE window per (subject, stage) -- 707 and 710 rows over 143 subjects and five stages. Within-stage
variance is not merely small in them, it is absent. `sleep_edfx_multiwindow.csv` has 12 windows per cell
but only 60 cells, no irreversibility column, and no submental channel: its `emg_index` is a SCALP-EEG
proxy that correlates with the real submental channel at rho = +0.20 pooled (E71), and rule 57 says a
positive control needs its own validation before it can be one.

N1 IS DROPPED AND THE REASON IS ARITHMETIC, NOT PREFERENCE. Contiguous same-stage blocks of at least
6 x 120 s exist for 128 subjects in W, 137 in N2, 94 in N3 and 133 in REM -- and **16** in N1, whose median
block is 360 s. N1 is a transition stage and does not hold a long block. Including it would contribute a
stratum with a tenth of the subjects and no ability to fail.

ONE READ PER BLOCK, NOT ONE PER WINDOW. The windows are contiguous inside a single block, so a single
`window_s = n_windows * 120` fetch covers all of them and they are sliced locally. That is 4 HTTP reads per
subject instead of 24, and it also guarantees the windows are exactly adjacent rather than re-derived.

THE WINDOWS ARE TILED FROM THE BLOCK CENTRE OUTWARD so that the set is symmetric about the same point the
one-window tables used, which keeps this table comparable to them rather than shifted toward a block edge.

    python bsde/scripts/extract_sleep_within_stage.py --n-windows 6 --limit 3    # smoke
    python bsde/scripts/extract_sleep_within_stage.py --n-windows 6
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

from bsde.ingestion.http_edf import read_edf_window_http                   # noqa: E402
from bsde.features.irreversibility import permutation_irreversibility, increment_asymmetry  # noqa: E402

WORKLIST = os.path.join(HERE, "..", "results", "sleep_edfx_five_stage_worklist.json")
OUT = os.path.join(HERE, "..", "results", "sleep_edfx_within_stage.csv")

WINDOW_S = 120.0
STAGES = ("W", "N2", "N3", "REM")          # N1 excluded: see docstring
EEG_RE = r"EEG"
EMG_RE = r"EMG"

FIELDS = ["recording_id", "subject", "label", "window_index", "start_seconds", "sfreq_eeg",
          "n_samples", "eeg_channel", "emg_channel",
          "irr3", "irr4", "incr_asym", "exponent_high", "emg_mean", "emg_median", "emg_p90", "emg_sd",
          "status", "error"]


def _aperiodic_slope(x: np.ndarray, sfreq: float, lo: float = 20.0, hi: float = 40.0) -> float:
    """The 20-40 Hz log-log slope. THIS IS THE POSITIVE CONTROL, not a candidate.

    E43 established that a broadband slope through this band is MORE muscle-associated than BIS, so it is
    the measure that MUST move with within-block EMG if the design has any power at all. Rule 66's lesson
    in one line: a design whose known effect is not tested cannot tell a null apart from a broken
    instrument."""
    from scipy.signal import welch
    f, p = welch(x, fs=sfreq, nperseg=int(min(len(x), 4 * sfreq)))
    m = (f >= lo) & (f <= hi) & (p > 0)
    if m.sum() < 5:
        return float("nan")
    b = np.polyfit(np.log10(f[m]), np.log10(p[m]), 1)
    return float(-b[0])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--n-windows", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    work = json.load(open(WORKLIST))
    span = a.n_windows * WINDOW_S

    jobs = []
    for r in work:
        if r["label"] not in STAGES:
            continue
        b0, b1 = r["meta"]["block_start_s"], r["meta"]["block_end_s"]
        if (b1 - b0) < span:
            continue
        start = max(b0, min((b0 + b1) / 2.0 - span / 2.0, b1 - span))
        jobs.append({"url": r["url"], "subject": r["subject"], "label": r["label"], "start": start})
    jobs.sort(key=lambda j: (j["subject"], j["label"]))
    if a.limit:
        jobs = jobs[:a.limit]

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        # Rule 56: de-duplicate on the key at load, rather than trusting this was the only writer.
        for r in csv.DictReader(open(out_path, newline="")):
            done.add((r["subject"], r["label"]))
    todo = [j for j in jobs if (j["subject"], j["label"]) not in done]
    print(f"{len(jobs)} (subject, stage) blocks with a contiguous {span:.0f}s span; "
          f"{len(done)} already done, {len(todo)} to fetch -> {out_path}", flush=True)
    if not todo:
        return 0

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, j in enumerate(todo, 1):
            base = {"subject": j["subject"], "label": j["label"], "status": "ok", "error": ""}
            try:
                xe, che, sfe, _ = read_edf_window_http(j["url"], window_s=span,
                                                       start_seconds=j["start"], channel_regex=EEG_RE)
                xm, chm, sfm, _ = read_edf_window_http(j["url"], window_s=span,
                                                       start_seconds=j["start"], channel_regex=EMG_RE)
            except Exception as e:                                          # noqa: BLE001
                w.writerow({**base, "recording_id": f"{j['subject']}@{j['label']}",
                            "status": "error", "error": f"{type(e).__name__}: {e}"})
                fh.flush()
                continue

            ne = int(round(WINDOW_S * sfe))
            nm = int(round(WINDOW_S * sfm))
            for k in range(a.n_windows):
                e_slice = xe[0, k * ne:(k + 1) * ne]
                m_slice = xm[0, k * nm:(k + 1) * nm]
                row = {**base,
                       "recording_id": f"{j['subject']}@{j['label']}#{k}",
                       "window_index": k, "start_seconds": f"{j['start'] + k * WINDOW_S:.1f}",
                       "sfreq_eeg": f"{sfe:g}", "n_samples": e_slice.size,
                       "eeg_channel": che[0] if che else "", "emg_channel": chm[0] if chm else ""}
                if e_slice.size < ne or m_slice.size < nm:
                    row.update({"status": "short", "error": f"eeg {e_slice.size}/{ne} emg "
                                                            f"{m_slice.size}/{nm}"})
                    w.writerow(row)
                    continue
                ok = np.isfinite(e_slice)
                if ok.mean() < 0.99:
                    row.update({"status": "gappy", "error": f"finite {ok.mean():.3f}"})
                    w.writerow(row)
                    continue
                row["irr3"] = f"{permutation_irreversibility(e_slice, order=3):.8g}"
                row["irr4"] = f"{permutation_irreversibility(e_slice, order=4):.8g}"
                row["incr_asym"] = f"{increment_asymmetry(e_slice):.8g}"
                row["exponent_high"] = f"{_aperiodic_slope(e_slice, sfe):.6g}"
                mm = m_slice[np.isfinite(m_slice)]
                if mm.size:
                    row["emg_mean"] = f"{float(np.mean(np.abs(mm))):.6g}"
                    row["emg_median"] = f"{float(np.median(np.abs(mm))):.6g}"
                    row["emg_p90"] = f"{float(np.percentile(np.abs(mm), 90)):.6g}"
                    row["emg_sd"] = f"{float(np.std(mm)):.6g}"
                w.writerow(row)
            fh.flush()
            if i % 10 == 0 or i == len(todo):
                print(f"   [{i}/{len(todo)}] {j['subject']} {j['label']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
