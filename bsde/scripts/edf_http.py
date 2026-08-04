#!/usr/bin/env python3
"""Byte-range EDF reader over plain HTTP, for deposits too large to download whole.

WHY THIS EXISTS. The CAP Sleep Database is 40 GB and this sandbox pulls about 17 MB/min through its proxy —
about 39 hours for the whole deposit, and sharding does not help because the cap is on aggregate bandwidth,
not per connection. But the analysis needs twelve 30-second epochs per sleep stage, which is roughly **7 %**
of each recording. EDF is a flat, fixed-layout binary, so the other 93 % never has to cross the wire.

    256-byte main header | ns * 256 bytes of signal headers | fixed-size data records

`analysis/heedb_edf_range.py` does the same thing against S3 for the HEEDB cohort. This is deliberately a
SEPARATE implementation rather than a refactor of that one: the HEEDB reader is load-bearing for a
different active programme, and changing its fetch path to accommodate a new deposit would put that
programme's data at risk for no benefit to it.

**VALIDATION.** `verify_against_mne()` reads the same window twice — once through this reader and once
through MNE on a fully downloaded copy — and reports the maximum absolute difference in microvolts. Rule
23: self-written code plus self-written tests share blind spots, so the check is against an independent
implementation, not against my own expectations.
"""

from __future__ import annotations

import math
import urllib.request

import numpy as np


def _get(url, start, length):
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{start + length - 1}",
                                               "User-Agent": "bsde-edf-range"})
    with urllib.request.urlopen(req, timeout=300) as r:
        if r.status not in (206, 200):
            raise OSError(f"range request returned {r.status}")
        return r.read()


class EdfHttp:
    """Header-only open; data records are fetched on demand."""

    def __init__(self, url):
        self.url = url
        h = _get(url, 0, 256)
        self.n_hdr = int(h[184:192].decode(errors="replace").strip() or 0)
        self.n_rec = int(h[236:244].decode(errors="replace").strip() or 0)
        self.rec_dur = float(h[244:252].decode(errors="replace").strip() or 1)
        self.ns = int(h[252:256].decode(errors="replace").strip() or 0)
        if self.ns <= 0 or self.n_rec <= 0:
            raise ValueError(f"bad EDF header: ns={self.ns} n_rec={self.n_rec}")
        sh = _get(url, 256, self.ns * 256)

        def blk(mult, width):
            base = mult * self.ns
            return [sh[base + i * width: base + (i + 1) * width].decode(errors="replace").strip()
                    for i in range(self.ns)]

        self.labels = blk(0, 16)
        self.phys_min = np.array([float(x or 0) for x in blk(104, 8)])
        self.phys_max = np.array([float(x or 0) for x in blk(112, 8)])
        self.dig_min = np.array([float(x or 0) for x in blk(120, 8)])
        self.dig_max = np.array([float(x or 0) for x in blk(128, 8)])
        self.n_samp = np.array([int(float(x or 0)) for x in blk(216, 8)])
        self.rec_bytes = int(2 * self.n_samp.sum())
        span = np.where((self.dig_max - self.dig_min) != 0, self.dig_max - self.dig_min, 1.0)
        self.gain = (self.phys_max - self.phys_min) / span
        self.duration_s = self.n_rec * self.rec_dur

    def sfreq(self, i):
        return self.n_samp[i] / self.rec_dur

    def read(self, t0, dur, picks):
        """Physical units for `picks` over [t0, t0+dur). Every pick must share one sampling rate."""
        r0 = int(math.floor(t0 / self.rec_dur))
        nrec = int(math.ceil((t0 + dur) / self.rec_dur)) - r0
        if r0 < 0 or r0 + nrec > self.n_rec:
            raise ValueError("window outside the recording")
        raw = _get(self.url, self.n_hdr + r0 * self.rec_bytes, nrec * self.rec_bytes)
        if len(raw) < nrec * self.rec_bytes:
            raise OSError(f"short range read: {len(raw)} of {nrec * self.rec_bytes}")
        a = np.frombuffer(raw, dtype="<i2").reshape(nrec, -1)
        off = np.concatenate([[0], np.cumsum(self.n_samp)])
        rates = {int(self.n_samp[i]) for i in picks}
        if len(rates) != 1:
            raise ValueError(f"picks have differing samples-per-record: {rates}")
        out = []
        for i in picks:
            d = a[:, off[i]:off[i + 1]].astype(np.float64).ravel()
            out.append((d - self.dig_min[i]) * self.gain[i] + self.phys_min[i])
        X = np.vstack(out)
        fs = self.sfreq(picks[0])
        s0 = int(round((t0 - r0 * self.rec_dur) * fs))
        return X[:, s0:s0 + int(round(dur * fs))], fs


def verify_against_mne(url, local_path, t0=600.0, dur=30.0, max_picks=4):
    """Read one window both ways and report the largest absolute disagreement, in microvolts."""
    import mne
    mne.set_log_level("ERROR")
    e = EdfHttp(url)
    raw = mne.io.read_raw_edf(local_path, preload=False, verbose=False)
    common = [i for i, l in enumerate(e.labels) if l in raw.ch_names][:max_picks]
    common = [i for i in common if e.n_samp[i] == e.n_samp[common[0]]]
    X, fs = e.read(t0, dur, common)
    idx = [raw.ch_names.index(e.labels[i]) for i in common]
    s0 = int(round(t0 * raw.info["sfreq"]))
    Y = raw.get_data(picks=idx, start=s0, stop=s0 + int(round(dur * raw.info["sfreq"]))) * 1e6
    n = min(X.shape[1], Y.shape[1])
    return {"channels": [e.labels[i] for i in common], "sfreq_range": fs,
            "sfreq_mne": float(raw.info["sfreq"]), "n_compared": int(n),
            "max_abs_diff_uv": float(np.max(np.abs(X[:, :n] - Y[:, :n]))),
            "rms_uv": float(np.sqrt(np.mean(Y[:, :n] ** 2)))}
