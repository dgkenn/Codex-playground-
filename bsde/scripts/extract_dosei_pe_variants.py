"""Recompute this repo's permutation entropy on DOSE-I under FIVE preprocessing variants, in one pass.

WHY. `extract_dosei_pe.py` established (rule 23, independent implementation) that our
`permutation_entropy(order=3, delay=1)` agrees with DOSE-I's shipped `PE31` at median within-recording
rho **+0.7239** over 39 recordings, against a circular-shift placebo of **-0.1238**. Strong agreement --
and yet against the deposit's own clinician-rated MOAA/S ours reaches **+0.3545** where theirs reaches
**+0.4944**, on the same 39 recordings and at nominally identical n=3, tau=1.

The deposit says what else it does. `pEEG_parameter_description.txt`, verbatim:

    Column 30: Permutation Entropy (PE) according to Olofsen et al. (2008), band: 0.5-45 Hz, n=3, tau=1,
               tie=0.5 uV

**Two declared steps our implementation does not perform: a 0.5-45 Hz band limit, and a 0.5 uV tie
threshold.** This script computes the variants that isolate each, so E76 can ask whether the declared
preprocessing accounts for the gap -- and, if it does not, say so rather than leave the gap unexplained.

WHAT IS COMPUTED, PER WINDOW (the alignment is byte-identical to `extract_dosei_pe.py`: a 30 s window
ENDING at each pEEG timestamp, every 5th second, causal, no lag search anywhere):

    pe_raw          no band, no tie          -- must reproduce `extract_dosei_pe.py`; a self-check
    pe_band         0.5-45 Hz, no tie        -- the band step alone
    pe_tie          no band, tie 0.5 uV      -- the tie step alone
    pe_declared     0.5-45 Hz + tie 0.5 uV   -- both, i.e. what the deposit declares
    pe_placebo20    0.5-20 Hz + tie 0.5 uV   -- an ARBITRARY WRONG BAND, the placebo

The placebo is the point of the design. If a 0.5-20 Hz band improves agreement as much as the declared
0.5-45 Hz one, then nothing has been shown about fidelity to a specification -- only that permutation
entropy is band-sensitive and that any low-pass helps. Rule 34: a placebo is a comparison against the real
effect, never an absolute threshold.

TWO GATES THAT CAN FAIL, both recorded per window rather than asserted (rule 40):

    tie_frac        fraction of embedded windows containing a within-0.5 uV pair, on the declared arm.
                    If this is ~0 the tie threshold is a no-op and `pe_tie` == `pe_raw` by construction;
                    the arm must then be reported as inapplicable, not as "no effect".
    band_rel_delta  median |x_band - x_raw| divided by the IQR of x_raw. If ~0 the filter did nothing --
                    which is the failure mode if the signal is already band-limited, or if the units are
                    wrong and the filter coefficients are degenerate.

UNITS ARE A GATE, NOT AN ASSUMPTION. A 0.5 uV threshold is meaningless unless the raw column is in
microvolts. Per recording the interquartile range of `Intellivue/EEG_1` is written to the log, and a
recording whose IQR is outside [0.5, 5000] is REFUSED rather than silently processed -- volts would give
~1e-5 and millivolts ~1e-2, both of which fail, and both of which would otherwise produce a tie arm that
is either a no-op or total collapse while looking like a result.

    python bsde/scripts/extract_dosei_pe_variants.py --n-recordings 40
"""
from __future__ import annotations

import argparse
import csv
import io
import math
import os
import sys
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.features.complexity import permutation_entropy, permutation_tie_fraction   # noqa: E402
from bsde.ingestion.remote_zip import RemoteZip                                       # noqa: E402

DATA_URL = "https://zenodo.org/records/18483292/files/data.zip?download=1"
PEEG_ZIP = os.path.join(HERE, "..", "results", "dosei_pEEG.zip")
OUT = os.path.join(HERE, "..", "results", "dosei_pe_variants.csv")

SFREQ = 125.0
WINDOW_S = 30.0
STRIDE_S = 5
TIE_UV = 0.5                      # the deposit's declared tie threshold, in microvolts
BAND_DECLARED = (0.5, 45.0)       # the deposit's declared band
BAND_PLACEBO = (0.5, 20.0)        # an arbitrary wrong band, fixed here before any result exists
IQR_MIN, IQR_MAX = 0.5, 5000.0    # the microvolt gate

FIELDS = ["recording", "t_s", "pe_raw", "pe_band", "pe_tie", "pe_declared", "pe_placebo20",
          "tie_frac", "band_rel_delta", "their_pe31", "their_pe32", "soc", "moaas"]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


TFMT = "%Y-%m-%d %H:%M:%S.%f"
TFMT_S = "%Y-%m-%d %H:%M:%S"


def _ts(s: str):
    from datetime import datetime
    return datetime.strptime(s, TFMT if "." in s else TFMT_S)


def peeg_series(z: zipfile.ZipFile, rec: str):
    with z.open(f"pEEG/pEEG/{rec}_pEEG.csv") as fh:
        rows = list(csv.DictReader(io.TextIOWrapper(fh)))
    return {_ts(r["Time"]): (_f(r["PE31"]), _f(r["PE32"]), _f(r["SOC"]), _f(r["MOAAS"]))
            for r in rows}


def raw_eeg(blob: bytes):
    """EEG_1 as a uniform 125 Hz array plus its first timestamp; None if the time axis is not uniform."""
    rd = csv.DictReader(io.TextIOWrapper(io.BytesIO(blob)))
    ts, xs = [], []
    for r in rd:
        v = r.get("Intellivue/EEG_1", "")
        if v == "":
            continue
        ts.append(r["Time"])
        xs.append(_f(v))
    if len(xs) < int(60 * SFREQ):
        return None, None
    t0, t1 = _ts(ts[0]), _ts(ts[-1])
    elapsed = (t1 - t0).total_seconds()
    expected = (len(xs) - 1) / SFREQ
    if elapsed <= 0 or abs(expected - elapsed) / elapsed > 0.01:
        return None, None
    return np.asarray(xs, float), t0


def bandpass(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Zero-phase Butterworth bandpass applied to the WHOLE recording once, then sliced.

    Filtering per 30 s window instead would put filtfilt's edge transient inside every window, and the
    transient is exactly where a burst-suppression signal's structure lives.
    """
    from scipy.signal import butter, filtfilt
    nyq = SFREQ / 2.0
    b, a = butter(4, [lo / nyq, min(hi / nyq, 0.99)], btype="bandpass")
    return filtfilt(b, a, x)


# --- fast permutation entropy -----------------------------------------------------------------------
# Vectorised over embedded windows.  Checked against `bsde.features.complexity.permutation_entropy` at
# runtime on the first window of every recording (see `main`), because a fast reimplementation that
# silently disagrees with the tested one is the failure mode this project has already paid for once.

def _embed(x: np.ndarray, order: int, delay: int) -> np.ndarray:
    n = x.size - delay * (order - 1)
    if n < 1:
        return np.empty((0, order))
    return np.stack([x[i * delay: i * delay + n] for i in range(order)], axis=1)


def pe_fast(x: np.ndarray, order: int = 3, delay: int = 1, tie: float = 0.0) -> float:
    E = _embed(np.asarray(x, float), order, delay)
    if E.shape[0] < 1:
        return float("nan")
    if tie > 0:
        lower = (E[:, None, :] < E[:, :, None] - tie).sum(axis=2)
        idx = np.argsort(lower, axis=1, kind="stable")
    else:
        idx = np.argsort(E, axis=1, kind="quicksort")
    code = idx @ (order ** np.arange(order))
    cnt = np.bincount(code)
    cnt = cnt[cnt > 0].astype(float)
    p = cnt / cnt.sum()
    return float(-(p * np.log2(p)).sum() / math.log2(math.factorial(order)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-recordings", type=int, default=40, dest="n_rec")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    pz = zipfile.ZipFile(os.path.abspath(PEEG_ZIP))
    have_peeg = {n.split("/")[-1].replace("_pEEG.csv", "")
                 for n in pz.namelist() if n.endswith("_pEEG.csv")}
    rz = RemoteZip(DATA_URL)
    members = [m for m in rz.index() if m["name"].endswith(".csv")]
    recs = [m["name"].split("/")[-1][:-4] for m in members]
    recs = [r for r in recs if r in have_peeg][:a.n_rec]
    print(f"{len(recs)} recordings selected", flush=True)

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["recording"] for r in csv.DictReader(fh)}
        print(f"   resuming: {len(done)} recordings already present", flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n_win = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, rec in enumerate([r for r in recs if r not in done], 1):
            try:
                peeg = peeg_series(pz, rec)
                x, t0 = raw_eeg(rz.read_member(f"data/{rec}.csv"))
            except Exception as e:                                        # noqa: BLE001
                print(f"   [{i}] {rec}: SKIP {type(e).__name__}: {e}", flush=True)
                continue
            if x is None:
                print(f"   [{i}] {rec}: SKIP non-uniform time axis or too short", flush=True)
                continue

            iqr = float(np.subtract(*np.percentile(x, [75, 25])))
            if not (IQR_MIN <= iqr <= IQR_MAX):
                print(f"   [{i}] {rec}: REFUSED, IQR {iqr:.4g} outside the microvolt gate "
                      f"[{IQR_MIN}, {IQR_MAX}]", flush=True)
                continue

            xb = bandpass(x, *BAND_DECLARED)
            xp = bandpass(x, *BAND_PLACEBO)
            band_rel = float(np.median(np.abs(xb - x)) / iqr) if iqr > 0 else float("nan")

            n = int(WINDOW_S * SFREQ)
            wrote = 0
            checked = False
            for ts_abs in sorted(peeg):
                t = (ts_abs - t0).total_seconds()
                if round(t) % STRIDE_S or t < WINDOW_S:
                    continue
                i1 = int(round(t * SFREQ))
                if i1 - n < 0 or i1 > x.size:
                    continue
                seg, segb, segp = x[i1 - n:i1], xb[i1 - n:i1], xp[i1 - n:i1]
                if seg.size < n:
                    continue
                if not checked:
                    ref0 = permutation_entropy(seg, 3, 1)
                    ref1 = permutation_entropy(segb, 3, 1, tie_threshold=TIE_UV)
                    d0 = abs(ref0 - pe_fast(seg))
                    d1 = abs(ref1 - pe_fast(segb, tie=TIE_UV))
                    if max(d0, d1) > 1e-9:
                        print(f"   [{i}] {rec}: REFUSED, fast PE disagrees with the tested "
                              f"implementation by {max(d0, d1):.3g}", flush=True)
                        break
                    checked = True
                s, p, soc, mo = peeg[ts_abs]
                w.writerow({
                    "recording": rec, "t_s": f"{t:.0f}",
                    "pe_raw": f"{pe_fast(seg):.10g}",
                    "pe_band": f"{pe_fast(segb):.10g}",
                    "pe_tie": f"{pe_fast(seg, tie=TIE_UV):.10g}",
                    "pe_declared": f"{pe_fast(segb, tie=TIE_UV):.10g}",
                    "pe_placebo20": f"{pe_fast(segp, tie=TIE_UV):.10g}",
                    "tie_frac": f"{permutation_tie_fraction(segb[:400], 3, 1, TIE_UV):.6g}",
                    "band_rel_delta": f"{band_rel:.6g}",
                    "their_pe31": f"{s:.10g}", "their_pe32": f"{p:.10g}",
                    "soc": f"{soc:.10g}", "moaas": f"{mo:.10g}"})
                wrote += 1
            fh.flush()
            n_win += wrote
            print(f"   [{i}] {rec}: {wrote} windows, IQR {iqr:.3g} uV, band_rel_delta {band_rel:.4f}",
                  flush=True)
    print(f"   wrote {n_win} windows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
