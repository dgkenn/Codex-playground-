"""Our permutation entropy at THREE window lengths, plus a smoothing-matched version of the deposit's PE31.

WHY. E78 measured, on 62 held-out DOSE-I recordings, that our E76-corrected permutation entropy out-tracks
the deposit's own `PE31` column against MOAA/S by **+0.0500 [+0.0177, +0.0849]** -- an interval excluding
zero, and one this project has deliberately refused to claim. The reason is in QUEUE.md Q37:

    the deposit's `pEEG_parameter_description.txt` states an explicit window length for every spectral
    measure -- `T=8 s` for columns 26-29 and 36, `T=16 s` for 37-41 -- and states NONE for any of its
    three permutation-entropy columns. Ours is 30 s.

**A longer window is a smoother estimate, and a smoother estimate tracks a slowly-varying behavioural scale
better for reasons that have nothing to do with the measure.** Rule 50: before attributing a difference to
X, measure the difference when X is held constant, and match the baseline's statistical structure to the
effect's. This pass produces both halves of that control in one fetch.

WHAT IS COMPUTED, on the SAME 62 held-out recordings and the SAME causal alignment (window ENDING at each
pEEG timestamp, every 5th second, no lag search):

    pe_8, pe_16, pe_30    our PE with the declared recipe (0.5-45 Hz band, 0.5 uV tie) at three windows
    their_pe31            the deposit's column, unchanged
    their_pe31_smooth30   the SAME column, causally smoothed with a 30-sample trailing mean of its own
                          1 Hz series -- i.e. given the same ~30 s support ours has

The smoothed column is computed from the 1 Hz pEEG series in this pass rather than from any saved table,
because a trailing mean has to be taken in the series' own timebase and the saved table is sampled every
5 s. `peeg_idx` is emitted so the alignment is checkable afterwards instead of reconstructed.

THE TWO ARMS ANSWER DIFFERENT HALVES AND BOTH ARE NEEDED. Shortening OURS asks whether the advantage
survives at the deposit's own declared spectral window; smoothing THEIRS asks whether the advantage
survives at matched support. If either kills it, the +0.0500 is smoothing.

    python bsde/scripts/extract_dosei_window_control.py --n-recordings 128
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

from bsde.ingestion.remote_zip import RemoteZip                                      # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")
DATA_URL = "https://zenodo.org/records/18483292/files/data.zip?download=1"
PEEG_ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
OUT = os.path.join(RESULTS, "dosei_window_control.csv")
USED_TABLES = ("dosei_features.csv", "dosei_pe_check.csv", "dosei_pe_variants.csv")

SFREQ = 125.0
WINDOWS_S = (8.0, 16.0, 30.0)
SMOOTH_N = 30                     # trailing samples of the 1 Hz PE31 series
STRIDE_S = 5
TIE_UV = 0.5
BAND = (0.5, 45.0)
IQR_MIN, IQR_MAX = 0.5, 5000.0

FIELDS = ["recording", "t_s", "peeg_idx", "pe_8", "pe_16", "pe_30",
          "their_pe31", "their_pe31_smooth30", "soc", "moaas"]


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
    out = set()
    for name in USED_TABLES:
        p = os.path.join(RESULTS, name)
        if not os.path.exists(p):
            continue
        with open(p, newline="") as fh:
            rd = csv.DictReader(fh)
            key = "recording" if "recording" in (rd.fieldnames or []) else "recording_id"
            for r in rd:
                if r.get(key):
                    out.add(r[key].split("@")[0])
    return out


def peeg_series(z: zipfile.ZipFile, rec: str):
    """Sorted (timestamp, PE31, smoothed PE31, SOC, MOAAS) with the trailing mean taken at 1 Hz."""
    with z.open(f"pEEG/pEEG/{rec}_pEEG.csv") as fh:
        rows = list(csv.DictReader(io.TextIOWrapper(fh)))
    rows.sort(key=lambda r: _ts(r["Time"]))
    p31 = np.array([_f(r["PE31"]) for r in rows])
    sm = np.full(p31.size, np.nan)
    for i in range(p31.size):
        seg = p31[max(0, i - SMOOTH_N + 1): i + 1]
        seg = seg[np.isfinite(seg)]
        if seg.size >= SMOOTH_N // 2:                 # refuse a mean built from a handful of samples
            sm[i] = seg.mean()
    return [(_ts(r["Time"]), p31[i], sm[i], _f(r["SOC"]), _f(r["MOAAS"]))
            for i, r in enumerate(rows)]


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


def bandpass(x, lo, hi):
    from scipy.signal import butter, filtfilt
    nyq = SFREQ / 2.0
    b, a = butter(4, [lo / nyq, min(hi / nyq, 0.99)], btype="bandpass")
    return filtfilt(b, a, x)


def pe_fast(x, order=3, delay=1, tie=0.0) -> float:
    x = np.asarray(x, float)
    n = x.size - delay * (order - 1)
    if n < 1:
        return float("nan")
    E = np.stack([x[i * delay: i * delay + n] for i in range(order)], axis=1)
    if tie > 0:
        idx = np.argsort((E[:, None, :] < E[:, :, None] - tie).sum(axis=2), axis=1, kind="stable")
    else:
        idx = np.argsort(E, axis=1, kind="quicksort")
    cnt = np.bincount(idx @ (order ** np.arange(order)))
    cnt = cnt[cnt > 0].astype(float)
    p = cnt / cnt.sum()
    return float(-(p * np.log2(p)).sum() / math.log2(math.factorial(order)))


def main(argv=None) -> int:
    from bsde.features.complexity import permutation_entropy

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-recordings", type=int, default=128, dest="n_rec")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    pz = zipfile.ZipFile(os.path.abspath(PEEG_ZIP))
    have = {n.split("/")[-1].replace("_pEEG.csv", "") for n in pz.namelist() if n.endswith("_pEEG.csv")}
    used = used_recordings()
    rz = RemoteZip(DATA_URL)
    recs = [m["name"].split("/")[-1][:-4] for m in rz.index() if m["name"].endswith(".csv")]
    holdout = [r for r in recs if r in have and r not in used][:a.n_rec]
    print(f"{len(have)} pEEG tables, {len(used)} used, {len(holdout)} held out and selected", flush=True)

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["recording"] for r in csv.DictReader(fh)}
        print(f"   resuming: {len(done)} already present", flush=True)
    if done & used:
        print(f"   ABORT: output contains recordings that are not held out: {sorted(done & used)[:5]}")
        return 2

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n_win = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, rec in enumerate([r for r in holdout if r not in done], 1):
            try:
                series = peeg_series(pz, rec)
                x, t0 = raw_eeg(rz.read_member(f"data/{rec}.csv"))
            except Exception as e:                                            # noqa: BLE001
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

            wrote, checked = 0, False
            for k, (ts_abs, p31, p31s, soc, mo) in enumerate(series):
                t = (ts_abs - t0).total_seconds()
                if round(t) % STRIDE_S or t < max(WINDOWS_S):
                    continue
                i1 = int(round(t * SFREQ))
                if i1 > x.size:
                    continue
                segs = {}
                bad = False
                for ws in WINDOWS_S:
                    n = int(ws * SFREQ)
                    if i1 - n < 0:
                        bad = True
                        break
                    segs[ws] = xb[i1 - n:i1]
                if bad:
                    continue
                if not checked:
                    d = abs(permutation_entropy(segs[30.0], 3, 1, tie_threshold=TIE_UV)
                            - pe_fast(segs[30.0], tie=TIE_UV))
                    if d > 1e-9:
                        print(f"   [{i}] {rec}: REFUSED, fast PE differs by {d:.3g}", flush=True)
                        break
                    checked = True
                w.writerow({"recording": rec, "t_s": f"{t:.0f}", "peeg_idx": k,
                            "pe_8": f"{pe_fast(segs[8.0], tie=TIE_UV):.10g}",
                            "pe_16": f"{pe_fast(segs[16.0], tie=TIE_UV):.10g}",
                            "pe_30": f"{pe_fast(segs[30.0], tie=TIE_UV):.10g}",
                            "their_pe31": f"{p31:.10g}", "their_pe31_smooth30": f"{p31s:.10g}",
                            "soc": f"{soc:.10g}", "moaas": f"{mo:.10g}"})
                wrote += 1
            fh.flush()
            n_win += wrote
            print(f"   [{i}] {rec}: {wrote} windows, IQR {iqr:.3g} uV", flush=True)
    print(f"   wrote {n_win} windows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
