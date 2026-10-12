#!/usr/bin/env python3
"""Extract ds006695's sleep hypnograms by HTTP byte range, without downloading the deposit.

WHY THIS EXISTS. ds006695 is the only Challenge C cohort left whose columns have never been correlated with
its label — E217 and E219 have between them exposed the panels on every other deposit. It is 10.05 GB, and
the labels are NOT in any BIDS `events.tsv`: they live in a `VisualHypnogram` variable inside each
subject's 283-424 MB EEGLAB `.set` file.

**Any tool that loads the `.set` — `scipy.io.loadmat`, `mne.io.read_raw_eeglab` — needs the whole file, so
the naive path costs 6.5 GB to reach 19 small arrays.** The `.set` is large not because it holds the EEG
(that lives in the companion `.fdt`) but because it stores full-length accelerometer channels inline.

MAT5 is a flat sequence of tagged elements, each tag carrying its own byte length, so the file can be
WALKED by reading tags and skipping payloads. Measured on sub-122: **4,288 bytes** to locate and pull a
913-epoch hypnogram out of a 301,303,480-byte file.

Verified against `scipy.io.loadmat` on a reconstructed minimal `.mat` — the same loader the naive path
would use, given only the header plus the one element (rule 23: check against an independent implementation
rather than against expectations).

    python bsde/scripts/ds006695_labels.py --out bsde/results/ds006695_hypnograms.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import struct
import urllib.request

BASE = "https://s3.amazonaws.com/openneuro.org/ds006695"
SUBJECTS = ("101", "102", "104", "105", "106", "107", "109", "110", "111", "112",
            "114", "116", "117", "119", "122", "123", "124", "125", "126")
# README's coding. 0 is documented and was NOT in the first summary of this deposit -- it is a 6-level
# code, not 5, and the sixth level is 'unknown/movement' which must be dropped rather than ranked.
CODE = {1: "W", 2: "REM", 3: "N1", 4: "N2", 5: "N3", 0: "UNKNOWN"}
MI_MATRIX = 14


def _rng(url, a, b):
    r = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}"})
    return urllib.request.urlopen(r, timeout=180).read()


def hypnogram(sub, want="VisualHypnogram", max_vars=200):
    """Walk MAT5 tags, fetch only the named element, and decode it with the standard loader."""
    import numpy as np
    import scipy.io as sio
    url = f"{BASE}/sub-{sub}/eeg/sub-{sub}_task-sleep_eeg.set"
    head = _rng(url, 0, 127)
    fetched, pos, n = len(head), 128, 0
    while n < max_vars:
        t = _rng(url, pos, pos + 7)
        fetched += 8
        if len(t) < 8:
            break
        dt, nb = struct.unpack("<II", t)
        if dt != MI_MATRIX:
            break
        h = _rng(url, pos + 8, pos + 8 + 63)
        fetched += 64
        _adt, anb = struct.unpack("<II", h[16:24])
        off = 16 + 8 + ((anb + 7) // 8) * 8
        _ndt, nnb = struct.unpack("<II", h[off:off + 8])
        name = h[off + 8:off + 8 + nnb].decode("latin-1") if nnb <= 48 else ""
        if name == want:
            blob = _rng(url, pos, pos + nb + 7)
            fetched += nb + 8
            d = sio.loadmat(io.BytesIO(head + blob))
            return np.asarray(d[want]).ravel().astype(int), fetched
        pos += 8 + ((nb + 7) // 8) * 8
        n += 1
    return None, fetched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="bsde/results/ds006695_hypnograms.csv")
    a = ap.parse_args()
    import collections
    total = 0
    rows = []
    for s in SUBJECTS:
        try:
            h, got = hypnogram(s)
        except Exception as e:                                          # noqa: BLE001
            print(f"sub-{s}: FAILED {type(e).__name__}: {e}", flush=True)
            continue
        total += got
        if h is None:
            print(f"sub-{s}: VisualHypnogram not found ({got} bytes walked)", flush=True)
            continue
        c = collections.Counter(h.tolist())
        rows.append({"subject": f"sub-{s}", "n_epochs": int(h.size),
                     "hours": round(h.size * 30 / 3600.0, 2), "bytes_fetched": got,
                     **{f"n_{CODE.get(k, k)}": int(v) for k, v in sorted(c.items())}})
        print(f"sub-{s}: {h.size} epochs, {h.size*30/3600:.2f} h, {got} bytes, "
              f"{ {CODE.get(k,k): v for k,v in sorted(c.items())} }", flush=True)
    cols = ["subject", "n_epochs", "hours", "bytes_fetched"] + \
           [f"n_{v}" for v in ("W", "REM", "N1", "N2", "N3", "UNKNOWN")]
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, cols, restval=0)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, 0) for k in cols})
    print(f"\n{len(rows)} subjects, {total} bytes fetched in total "
          f"({total/1e6:.3f} MB against a 10.05 GB deposit)")
    print(f"wrote -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
