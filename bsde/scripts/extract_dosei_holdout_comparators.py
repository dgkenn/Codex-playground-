"""`bis_rbr` and the E76-corrected permutation entropy on IDENTICAL windows, on DOSE-I recordings never used.

WHY THIS PASS EXISTS. Two results collide and neither can settle the collision on its own data.

  * QUEUE.md **Q35** (exploratory, post-hoc over 29 features) found `bis_rbr` at median within-recording
    rho **+0.5258** against MOAA/S, against the deposit's shipped `PE31` at **+0.4813**, and amended Q34's
    "PE31 is the comparator to use" to "`bis_rbr` matches or beats it under every adjustment tried".
  * **E76** then showed our permutation entropy had been mis-specified: applying the deposit's declared
    0.5-45 Hz band and 0.5 uV tie threshold raises clinician tracking by **+0.1609 [+0.0764, +0.2613]**,
    to a median of **+0.5304**.

**+0.5304 against +0.5258 is a tie, not a win for either** -- and the two numbers come from different
window definitions in different passes, so even that comparison is not one a reader should accept. Q35 owed
"a registered test on a deposit or a partition not used here, with `bis_rbr` and PE31 pre-declared, and the
29-feature multiplicity handled rather than noted". This pass supplies the data for it.

WHAT IS HELD OUT, AND IT IS NOT A GESTURE. The deposit ships 171 pEEG tables. Every DOSE-I result this
project has -- E33, E34, E59, E65, Q35, Q36, E76 -- was computed on the SAME 43 recordings (the union of
`dosei_features.csv`, `dosei_pe_check.csv` and `dosei_pe_variants.csv`; verified, the union is 43 and not
merely each of them). **This script refuses any recording in that union**, so the 128 remaining are a
genuine held-out partition rather than a re-slice.

IDENTICAL WINDOWS IS THE POINT. Both measures are computed on the same 30 s window ENDING at each pEEG
timestamp, every 5th second, causal, no lag search -- the alignment E76 and `extract_dosei_pe.py` already
use. `bis_rbr` is computed on the RAW window because the relative beta ratio is band-limited by its own
definition (log P[30-47] / P[11-20]); `pe_declared` is computed on the 0.5-45 Hz filtered window with the
0.5 uV tie threshold, because that is the specification E76 validated. Filtering the whole recording once
and slicing keeps filtfilt's edge transient out of every window.

CARRIED FOR THE INCUMBENTS (rule 45): the deposit's own `PE31` and `SEF95`, so the held-out comparison has
two published bars beside it and not just each candidate against the other.

GATES RECORDED PER WINDOW, not asserted: `tie_frac` and `band_rel_delta` as in E76, and the per-recording
EEG interquartile range, since a 0.5 uV threshold is meaningless unless the column is in microvolts.

    python bsde/scripts/extract_dosei_holdout_comparators.py --n-recordings 60
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.features.bis_subparams import relative_beta_ratio                          # noqa: E402
from bsde.features.complexity import permutation_tie_fraction                        # noqa: E402
from bsde.ingestion.remote_zip import RemoteZip                                      # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")
DATA_URL = "https://zenodo.org/records/18483292/files/data.zip?download=1"
PEEG_ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
OUT = os.path.join(RESULTS, "dosei_holdout_comparators.csv")
USED_TABLES = ("dosei_features.csv", "dosei_pe_check.csv", "dosei_pe_variants.csv")

SFREQ = 125.0
WINDOW_S = 30.0
STRIDE_S = 5
TIE_UV = 0.5
BAND = (0.5, 45.0)
IQR_MIN, IQR_MAX = 0.5, 5000.0

FIELDS = ["recording", "t_s", "bis_rbr", "pe_declared", "their_pe31", "their_sef95",
          "tie_frac", "band_rel_delta", "iqr_uv", "soc", "moaas"]


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


def used_recordings() -> set:
    """Every recording this project has already computed a DOSE-I number on."""
    out = set()
    for name in USED_TABLES:
        p = os.path.join(RESULTS, name)
        if not os.path.exists(p):
            continue
        with open(p, newline="") as fh:
            rd = csv.DictReader(fh)
            key = "recording" if "recording" in (rd.fieldnames or []) else "recording_id"
            for r in rd:
                v = r.get(key, "")
                out.add(v.split("@")[0] if v else v)
    out.discard("")
    return out


def peeg_series(z: zipfile.ZipFile, rec: str):
    with z.open(f"pEEG/pEEG/{rec}_pEEG.csv") as fh:
        rows = list(csv.DictReader(io.TextIOWrapper(fh)))
    return {_ts(r["Time"]): (_f(r["PE31"]), _f(r["SEF95"]), _f(r["SOC"]), _f(r["MOAAS"]))
            for r in rows}


def raw_eeg(blob: bytes):
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
    from scipy.signal import butter, filtfilt
    nyq = SFREQ / 2.0
    b, a = butter(4, [lo / nyq, min(hi / nyq, 0.99)], btype="bandpass")
    return filtfilt(b, a, x)


def _embed(x, order, delay):
    n = x.size - delay * (order - 1)
    return np.empty((0, order)) if n < 1 else np.stack(
        [x[i * delay: i * delay + n] for i in range(order)], axis=1)


def pe_fast(x, order=3, delay=1, tie=0.0) -> float:
    import math
    E = _embed(np.asarray(x, float), order, delay)
    if E.shape[0] < 1:
        return float("nan")
    if tie > 0:
        idx = np.argsort((E[:, None, :] < E[:, :, None] - tie).sum(axis=2), axis=1, kind="stable")
    else:
        idx = np.argsort(E, axis=1, kind="quicksort")
    cnt = np.bincount(idx @ (order ** np.arange(order)))
    cnt = cnt[cnt > 0].astype(float)
    p = cnt / cnt.sum()
    return float(-(p * np.log2(p)).sum() / math.log2(math.factorial(order)))


def main(argv=None) -> int:
    from bsde.features.aperiodic import welch_psd
    from bsde.features.complexity import permutation_entropy

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-recordings", type=int, default=60, dest="n_rec")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    pz = zipfile.ZipFile(os.path.abspath(PEEG_ZIP))
    have = {n.split("/")[-1].replace("_pEEG.csv", "")
            for n in pz.namelist() if n.endswith("_pEEG.csv")}
    used = used_recordings()
    rz = RemoteZip(DATA_URL)
    recs = [m["name"].split("/")[-1][:-4] for m in rz.index() if m["name"].endswith(".csv")]
    holdout = [r for r in recs if r in have and r not in used]
    print(f"{len(have)} pEEG tables, {len(used)} already used, {len(holdout)} held out; "
          f"taking {min(a.n_rec, len(holdout))}", flush=True)
    recs = holdout[:a.n_rec]

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["recording"] for r in csv.DictReader(fh)}
        print(f"   resuming: {len(done)} already present", flush=True)
    overlap = done & used
    if overlap:
        print(f"   ABORT: {len(overlap)} rows already in the output are NOT held out: {sorted(overlap)[:5]}")
        return 2

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
            except Exception as e:                                              # noqa: BLE001
                print(f"   [{i}] {rec}: SKIP {type(e).__name__}: {e}", flush=True)
                continue
            if x is None:
                print(f"   [{i}] {rec}: SKIP non-uniform time axis or too short", flush=True)
                continue
            iqr = float(np.subtract(*np.percentile(x, [75, 25])))
            if not (IQR_MIN <= iqr <= IQR_MAX):
                print(f"   [{i}] {rec}: REFUSED, IQR {iqr:.4g} uV outside the gate", flush=True)
                continue
            xb = bandpass(x, *BAND)
            band_rel = float(np.median(np.abs(xb - x)) / iqr) if iqr > 0 else float("nan")

            n = int(WINDOW_S * SFREQ)
            wrote, checked = 0, False
            for ts_abs in sorted(peeg):
                t = (ts_abs - t0).total_seconds()
                if round(t) % STRIDE_S or t < WINDOW_S:
                    continue
                i1 = int(round(t * SFREQ))
                if i1 - n < 0 or i1 > x.size:
                    continue
                seg, segb = x[i1 - n:i1], xb[i1 - n:i1]
                if seg.size < n:
                    continue
                if not checked:
                    d = abs(permutation_entropy(segb, 3, 1, tie_threshold=TIE_UV)
                            - pe_fast(segb, tie=TIE_UV))
                    if d > 1e-9:
                        print(f"   [{i}] {rec}: REFUSED, fast PE differs from the tested one by {d:.3g}",
                              flush=True)
                        break
                    checked = True
                try:
                    freqs, psd = welch_psd(seg, SFREQ)
                    rbr = relative_beta_ratio(freqs, psd)
                except Exception:                                               # noqa: BLE001
                    rbr = float("nan")
                p31, sef, soc, mo = peeg[ts_abs]
                w.writerow({"recording": rec, "t_s": f"{t:.0f}",
                            "bis_rbr": f"{rbr:.10g}",
                            "pe_declared": f"{pe_fast(segb, tie=TIE_UV):.10g}",
                            "their_pe31": f"{p31:.10g}", "their_sef95": f"{sef:.10g}",
                            "tie_frac": f"{permutation_tie_fraction(segb[:400], 3, 1, TIE_UV):.6g}",
                            "band_rel_delta": f"{band_rel:.6g}", "iqr_uv": f"{iqr:.6g}",
                            "soc": f"{soc:.10g}", "moaas": f"{mo:.10g}"})
                wrote += 1
            fh.flush()
            n_win += wrote
            print(f"   [{i}] {rec}: {wrote} windows, IQR {iqr:.3g} uV", flush=True)
    print(f"   wrote {n_win} windows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
