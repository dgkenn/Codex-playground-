"""EDF-over-HTTPS adapter: stream only the requested window via HTTP Range requests.

WHY THIS EXISTS. EDF has a fixed, simple layout (256-byte main header, then `ns * 256` bytes of
per-signal headers, then fixed-size data records). That means the byte offset of any window is
computable from the header alone, so a remote EDF file can be read with two small HTTP requests — one
for the headers, one Range request for the samples wanted — instead of downloading the whole file. The
core trick is lifted from `analysis/heedb_edf_range.py` in the sibling project (function
`read_edf_window`), adapted here to use `urllib.request` against a URL instead of an S3 byte-range GET.

Header parsing and sample decoding are split into pure functions (`parse_edf_header`, `decode_edf_window`)
that take plain bytes and return plain data — no network, no adapter state. That is what lets the offline
tests exercise the format logic against a synthetic in-memory EDF without ever touching the network.

UNITS. EDF's physical dimension field (8 bytes per signal, e.g. "uV", "mV", "V") declares what the
physical min/max are measured in. We READ it and convert with `to_microvolts` rather than assuming — the
base module's rule that guessing from magnitude is unacceptable applies here as much as anywhere. A blank
or unrecognised dimension field raises, per that same rule; a plausible-looking silent guess would be the
kind of bug that only shows up as a subtly wrong band-power number months later.

RANGE REQUESTS. `urllib.request` honours the standard `http_proxy`/`https_proxy`/`HTTPS_PROXY` environment
variables and the system CA trust store via `ssl` (extended with `AWS_CA_BUNDLE`/`REQUESTS_CA_BUNDLE` if
set) automatically through its default handlers — no custom opener is needed, and TLS verification is never
disabled here under any circumstances.
"""
from __future__ import annotations

import os
import ssl
import struct
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

import numpy as np

from bsde.ingestion.base import Adapter, RecordingRef, to_microvolts

_HEADER_BYTES = 256
_SIGNAL_HEADER_BYTES = 256  # per signal


def _ssl_context() -> ssl.SSLContext:
    """Build a verifying SSL context, honouring a CA bundle if the environment declares one.

    Never returns an unverified context -- raw EEG travels over HTTPS precisely so it is never staged to
    disk in the clear, and disabling verification would defeat that for a MITM-shaped reason.
    """
    bundle = os.environ.get("AWS_CA_BUNDLE") or os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if bundle and os.path.exists(bundle):
        return ssl.create_default_context(cafile=bundle)
    return ssl.create_default_context()


def _urlopen(req: urllib.request.Request, timeout: float = 60.0):
    ctx = _ssl_context() if urlsplit(req.full_url).scheme == "https" else None
    if ctx is not None:
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return urllib.request.urlopen(req, timeout=timeout)


def _http_get_range(url: str, start: int, length: int, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{start + length - 1}"})
    with _urlopen(req, timeout=timeout) as resp:
        return resp.read()


def supports_range(url: str, timeout: float = 20.0) -> bool:
    """HEAD the URL and check for `Accept-Ranges: bytes`. Best-effort: some servers omit the header
    even when Range works, so a False here means "unconfirmed", not "definitely unsupported"."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with _urlopen(req, timeout=timeout) as resp:
            return resp.headers.get("Accept-Ranges", "").strip().lower() == "bytes"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


def parse_edf_header(main_header: bytes, signal_headers: bytes) -> Dict[str, Any]:
    """Parse EDF's fixed-layout header fields from raw bytes. Pure function: no I/O.

    `main_header` must be the first 256 bytes of the file. `signal_headers` must be the following
    `ns * 256` bytes, where `ns` is read out of `main_header` itself.

    Field offsets (all `ns`-wide blocks are contiguous, one entry per signal, per the EDF spec):
        0*ns : label (16)          96*ns : phys_dim (8)       128*ns : dig_max (8)
        16*ns: transducer (80)     104*ns: phys_min (8)       136*ns: prefilter (80)
        (unused)                   112*ns: phys_max (8)       216*ns: n_samples_per_record (8)
                                    120*ns: dig_min (8)        224*ns: reserved (32)
    """
    if len(main_header) < _HEADER_BYTES:
        raise ValueError(f"EDF main header truncated: got {len(main_header)} bytes, need {_HEADER_BYTES}")
    h = main_header
    n_hdr = int(h[184:192].decode(errors="replace").strip() or 0)
    n_rec = int(h[236:244].decode(errors="replace").strip() or 0)
    rec_dur = float(h[244:252].decode(errors="replace").strip() or 1)
    ns = int(h[252:256].decode(errors="replace").strip() or 0)
    if ns <= 0:
        raise ValueError("bad EDF: number of signals (ns) is 0")
    if len(signal_headers) < ns * _SIGNAL_HEADER_BYTES:
        raise ValueError(
            f"EDF signal headers truncated: got {len(signal_headers)} bytes, need {ns * _SIGNAL_HEADER_BYTES}")
    sh = signal_headers

    def blk(off_mult: int, width: int) -> List[str]:
        base = off_mult * ns
        return [sh[base + i * width: base + (i + 1) * width].decode(errors="replace").strip() for i in range(ns)]

    def fnum(vals: List[str], default: float) -> List[float]:
        out = []
        for v in vals:
            try:
                out.append(float(v))
            except ValueError:
                out.append(default)
        return out

    labels = blk(0, 16)
    phys_dim = blk(96, 8)
    pmin = fnum(blk(104, 8), -32768.0)
    pmax = fnum(blk(112, 8), 32767.0)
    dmin = fnum(blk(120, 8), -32768.0)
    dmax = fnum(blk(128, 8), 32767.0)
    nsamp_raw = blk(216, 8)
    nsamp = [int(float(x)) if x else 0 for x in nsamp_raw]
    nsamp = [n if n > 0 else 1 for n in nsamp]
    data_offset = _HEADER_BYTES + ns * _SIGNAL_HEADER_BYTES
    record_bytes = 2 * sum(nsamp)  # int16 LE per sample
    return dict(
        header_bytes=n_hdr, n_records=n_rec, record_duration=rec_dur, n_signals=ns,
        labels=labels, phys_dim=phys_dim, phys_min=pmin, phys_max=pmax,
        dig_min=dmin, dig_max=dmax, n_samples_per_record=nsamp,
        data_offset=data_offset, record_bytes=record_bytes,
    )


def _dimension_to_source_units(dim: str) -> str:
    """Map an EDF physical-dimension field to a `to_microvolts` source-unit key. Raises on blank/unknown
    fields rather than guessing (base.py's rule, applied to the one place EDF states its own units)."""
    key = dim.strip().lower()
    aliases = {"uv": "microvolts", "µv": "microvolts", "microv": "microvolts",
               "mv": "millivolts", "v": "volts", "volt": "volts", "volts": "volts", "nv": "nanovolts"}
    if key in aliases:
        return aliases[key]
    if key in ("microvolts", "millivolts", "volts", "nanovolts"):
        return key
    raise ValueError(
        f"unrecognised or blank EDF physical dimension {dim!r}; refusing to guess units. "
        "Declare/verify the signal header's physical-dimension field.")


def decode_edf_window(main_header: bytes, signal_headers: bytes, data_bytes: bytes,
                       skip_records: int) -> Tuple[np.ndarray, List[str], float, Dict[str, Any]]:
    """Decode a byte-range window of EDF data records into (data[n_ch, n_samp] in microvolts, ch_names,
    sfreq, meta). `data_bytes` must start at a record boundary `skip_records` records into the file --
    the caller is responsible for having fetched the right span; this function only decodes it.

    All channels are required to declare the SAME recognised physical dimension (EDF allows differing
    units per channel; mixed-unit files are rejected rather than silently converted per-channel-wrong, but
    per-channel conversion IS applied correctly when dimensions differ, since `to_microvolts` is invoked
    per channel below).
    """
    meta = parse_edf_header(main_header, signal_headers)
    ns = meta["n_signals"]
    nsamp = meta["n_samples_per_record"]
    record_bytes = meta["record_bytes"]
    if record_bytes <= 0:
        raise ValueError("bad EDF: zero-length data record")
    got_records = len(data_bytes) // record_bytes
    if got_records == 0:
        raise ValueError("no complete EDF data record in the fetched window")
    arr = np.frombuffer(data_bytes[: got_records * record_bytes], dtype="<i2").reshape(got_records, -1)

    labels = meta["labels"]
    phys_dim = meta["phys_dim"]
    pmin, pmax = meta["phys_min"], meta["phys_max"]
    dmin, dmax = meta["dig_min"], meta["dig_max"]
    rec_dur = meta["record_duration"] or 1.0

    out = []
    fs_per_ch = []
    idx = 0
    for i in range(ns):
        n = nsamp[i]
        block = arr[:, idx: idx + n].astype(np.float64).ravel()
        idx += n
        span_d = (dmax[i] - dmin[i]) or 1.0
        gain = (pmax[i] - pmin[i]) / span_d
        physical = (block - dmin[i]) * gain + pmin[i]
        source_units = _dimension_to_source_units(phys_dim[i])
        out.append(to_microvolts(physical, source_units))
        fs_per_ch.append(n / rec_dur)

    n_min = min(len(v) for v in out)
    data = np.vstack([v[:n_min] for v in out])
    sfreq = fs_per_ch[0] if fs_per_ch else 0.0
    meta_out = dict(meta)
    meta_out.update(source_units="microvolts", skip_records=skip_records, got_records=got_records)
    return data, list(labels), float(sfreq), meta_out


def read_edf_window_http(url: str, window_s: float = 300.0, start_seconds: float = 0.0,
                          timeout: float = 60.0) -> Tuple[np.ndarray, List[str], float, Dict[str, Any]]:
    """Fetch just the header plus the requested window of an EDF file served over HTTPS, and decode it.

    Two requests total: one Range GET for the fixed-size headers (whose combined length is not known
    until the main header's `ns` field is read, hence two small reads), one Range GET for the data
    records that cover `[start_seconds, start_seconds + window_s)`. Shared by `HttpEDFAdapter` and
    `OpenNeuroS3Adapter` so the EDF-over-HTTP logic exists in exactly one place.
    """
    main_header = _http_get_range(url, 0, _HEADER_BYTES, timeout=timeout)
    ns = int(main_header[252:256].decode(errors="replace").strip() or 0)
    if ns <= 0:
        raise ValueError(f"bad EDF at {url}: ns=0")
    signal_headers = _http_get_range(url, _HEADER_BYTES, ns * _SIGNAL_HEADER_BYTES, timeout=timeout)
    meta = parse_edf_header(main_header, signal_headers)

    rec_dur = meta["record_duration"] or 1.0
    n_rec = meta["n_records"]
    total = n_rec if n_rec > 0 else 10 ** 9
    want_records = min(total, max(1, int(round(window_s / rec_dur))))
    skip = int(start_seconds / rec_dur)
    skip = max(0, min(skip, max(0, total - want_records)))

    data_off = meta["data_offset"] + skip * meta["record_bytes"]
    data_bytes = _http_get_range(url, data_off, want_records * meta["record_bytes"], timeout=timeout)
    return decode_edf_window(main_header, signal_headers, data_bytes, skip_records=skip)


class HttpEDFAdapter(Adapter):
    """Stream EDF files over HTTPS via Range requests -- only the requested window is transferred.

    `recording_id` is the URL's basename without extension, which is stable across runs regardless of the
    order `urls` happens to be given in (we `sorted()` them for listing anyway, per the reference adapter's
    convention).
    """

    units = "microvolts"

    def __init__(self, urls: Sequence[str], dataset: str, window_s: float = 300.0,
                 start_seconds: float = 0.0, subject_from_url=None) -> None:
        self.urls = list(urls)
        self.dataset = dataset
        self.name = f"http_edf:{dataset}"
        self.window_s = window_s
        self.start_seconds = start_seconds
        # A dataset with several recordings per subject MUST pass this, or subject-level splitting
        # silently degrades to recording-level splitting (see base.py's RecordingRef.__post_init__).
        self._subject_from_url = subject_from_url

    def list_recordings(self) -> List[RecordingRef]:
        out = []
        for url in sorted(self.urls):  # sorted == deterministic order, independent of input ordering
            base = url.rsplit("/", 1)[-1]
            rid = base.rsplit(".", 1)[0] if "." in base else base
            out.append(RecordingRef(
                recording_id=rid, dataset=self.dataset,
                subject=(self._subject_from_url(url) if self._subject_from_url else rid),
                load=self._make_loader(url),
                meta={"url": url, "format": "edf"}))
        return out

    def _make_loader(self, url: str):
        def load():
            data, ch_names, sfreq, meta = read_edf_window_http(
                url, window_s=self.window_s, start_seconds=self.start_seconds)
            return data, ch_names, sfreq, meta
        return load
