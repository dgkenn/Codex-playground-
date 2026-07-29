"""PhysioNet WFDB adapter: stream `.hea` + signal-file pairs over HTTPS, never to disk.

The `.hea` file is a small text header (record name, signal count, sampling frequency, then one line per
channel giving the signal filename, storage format, gain/baseline/units, and channel name). It is fetched
whole -- it is a few hundred bytes -- and parsed with `parse_hea`, lifted from
`analysis/icare_bs_burden.py` in the sibling project (same function name, same field layout) and extended
to also capture the signal filename and storage format per channel, which that version did not need because
it always loaded a whole `.mat` file.

PHYSICAL UNITS. WFDB encodes gain, baseline and units together in one field, e.g. `200(0)/uV` means
`physical = (raw - baseline) / gain`, and the row is measured in the units named after the `/`. That unit
string is converted to microvolts via `to_microvolts` per channel -- WFDB permits different gains AND
different units per channel in principle, so the conversion is applied per channel rather than once for the
whole record.

LIMITATION, stated plainly because it would otherwise look like an oversight, not a design choice.
PhysioNet critical-care databases -- I-CARE among them -- store signals as MATLAB `.mat` files rather than
raw WFDB `.dat`. A `.mat` file is a self-describing container: the array shape, dtype, and byte layout all
live inside a header that `scipy.io.loadmat` has to parse, so there is no fixed byte offset for "sample N"
the way there is for a `.dat` file. Byte-range slicing a `.mat` file is not straightforward, and this
adapter does not attempt it. **When the header names a `.mat` file, the whole signal file is fetched into
MEMORY (never to local disk) and the requested window is sliced out of the decoded array afterwards.**
That satisfies the "raw EEG never lands on disk" invariant but it is NOT byte-range streaming in the sense
`HttpEDFAdapter` achieves for `.edf` -- a 57 MB I-CARE hour file is 57 MB transferred, every time. Only the
`.dat` path below is genuine byte-range streaming, and only for WFDB storage format 16 (16-bit signed
integers, the common case for clinical EEG); any other format raises rather than silently mis-decoding,
per this project's rule against guessing at binary layout.
"""
from __future__ import annotations

import io
import re
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from bsde.ingestion.base import Adapter, RecordingRef, to_microvolts
from bsde.ingestion.http_edf import _http_get_range, _urlopen  # shared range/SSL plumbing, not duplicated

_SIGNAL_LINE_RE = re.compile(r"^(\d+)")
_GAIN_RE = re.compile(r"^([-\d.eE+]+)(?:\((-?[\d.eE+]+)\))?(?:/(\S+))?$")


def parse_hea(text: str) -> Dict[str, Any]:
    """Parse a WFDB `.hea` header from its text content. Pure function: no I/O.

    Returns fs, per-channel gains/baselines/units/names, the signal filename(s) and storage format(s), and
    the declared sample count if the header states one (the "record line" `nsamples` field is optional in
    the WFDB spec; absent, `n_samples` is None and the caller must bound the window some other way).
    """
    lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        raise ValueError("empty WFDB header")
    first = lines[0].split()
    if len(first) < 3:
        raise ValueError(f"malformed WFDB record line: {lines[0]!r}")
    nsig = int(first[1])
    fs = float(first[2].split("/")[0])  # fs may carry "/counterfreq"; only the base rate matters here
    n_samples: Optional[int] = None
    if len(first) > 3:
        try:
            n_samples = int(first[3])
        except ValueError:
            n_samples = None
    if len(lines) < 1 + nsig:
        raise ValueError(f"WFDB header declares {nsig} signals but only {len(lines) - 1} signal lines present")

    files: List[str] = []
    fmts: List[str] = []
    gains: List[float] = []
    bases: List[float] = []
    units: List[str] = []
    names: List[str] = []
    for l in lines[1: 1 + nsig]:
        p = l.split()
        if len(p) < 3:
            raise ValueError(f"malformed WFDB signal line: {l!r}")
        files.append(p[0])
        fmt_m = _SIGNAL_LINE_RE.match(p[1])
        fmts.append(fmt_m.group(1) if fmt_m else p[1])
        m = _GAIN_RE.match(p[2])
        if m:
            gains.append(float(m.group(1)) if m.group(1) and float(m.group(1)) != 0 else 1.0)
            bases.append(float(m.group(2)) if m.group(2) else 0.0)
            units.append(m.group(3) or "")
        else:
            gains.append(1.0)
            bases.append(0.0)
            units.append("")
        names.append(p[-1])
    return dict(nsig=nsig, fs=fs, n_samples=n_samples, files=files, fmts=fmts,
                gains=gains, bases=bases, units=units, names=names)


def _fetch_whole(url: str, timeout: float = 120.0) -> bytes:
    req = urllib.request.Request(url)
    with _urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _wfdb_unit_to_source(u: str) -> str:
    key = u.strip().lower()
    aliases = {"uv": "microvolts", "µv": "microvolts", "mv": "millivolts", "v": "volts", "nv": "nanovolts"}
    if key in aliases:
        return aliases[key]
    if key in ("microvolts", "millivolts", "volts", "nanovolts"):
        return key
    raise ValueError(f"unrecognised or blank WFDB unit {u!r}; refusing to guess. "
                      "Declare the unit in the header's gain field (e.g. '200(0)/uV').")


def _decode_dat_window(raw: bytes, nsig: int, gains: Sequence[float], bases: Sequence[float],
                        fmt: str) -> np.ndarray:
    if fmt != "16":
        raise NotImplementedError(
            f"WFDB storage format {fmt!r} is not supported for byte-range .dat reads (only format 16, "
            "16-bit signed interleaved, is implemented). Decoding any other format here would require "
            "guessing at a bit-packed layout this adapter does not implement.")
    frame_bytes = 2 * nsig
    n_frames = len(raw) // frame_bytes
    if n_frames == 0:
        raise ValueError("no complete WFDB frame in the fetched byte range")
    arr = np.frombuffer(raw[: n_frames * frame_bytes], dtype="<i2").reshape(n_frames, nsig)
    out = np.empty((nsig, n_frames), dtype=np.float64)
    for i in range(nsig):
        out[i] = (arr[:, i].astype(np.float64) - bases[i]) / gains[i]
    return out


def read_wfdb_window_http(base_url: str, record_name: str, window_s: float = 300.0,
                           start_seconds: float = 0.0, timeout: float = 120.0
                           ) -> Tuple[np.ndarray, List[str], float, Dict[str, Any]]:
    """Fetch and decode one WFDB record's window over HTTPS. See module docstring for the `.mat`
    whole-file-in-memory limitation -- only the `.dat` branch is genuine byte-range streaming."""
    base = base_url.rstrip("/")
    hea_url = f"{base}/{record_name}.hea"
    hea_text = _fetch_whole(hea_url, timeout=timeout).decode("utf-8", errors="replace")
    hdr = parse_hea(hea_text)

    sig_files = set(hdr["files"])
    if len(sig_files) != 1:
        raise NotImplementedError(
            f"record {record_name!r} spreads signals across {len(sig_files)} files "
            f"({sorted(sig_files)}); only the single-signal-file layout is implemented.")
    sig_file = hdr["files"][0]
    fs = hdr["fs"]
    nsig = hdr["nsig"]
    gains, bases, units, names = hdr["gains"], hdr["bases"], hdr["units"], hdr["names"]
    sig_url = f"{base}/{sig_file}"

    if sig_file.lower().endswith(".mat"):
        import scipy.io as sio  # heavy dep: imported lazily, per project convention

        blob = _fetch_whole(sig_url, timeout=timeout)  # WHOLE FILE IN MEMORY -- see module docstring
        mat = sio.loadmat(io.BytesIO(blob))
        if "val" in mat:
            val = mat["val"]
        else:
            candidates = [v for k, v in mat.items() if not k.startswith("__") and hasattr(v, "shape")]
            if not candidates:
                raise ValueError(f"{sig_url}: no array variable found in .mat file (expected 'val')")
            val = candidates[0]
        val = np.asarray(val)
        if val.shape[0] != nsig and val.shape[1] == nsig:
            val = val.T
        total_samples = val.shape[1]
        want = max(1, int(round(window_s * fs)))
        skip = int(round(start_seconds * fs))
        skip = max(0, min(skip, max(0, total_samples - want)))
        window = val[:, skip: skip + want].astype(np.float64)
        physical = np.empty_like(window)
        for i in range(nsig):
            physical[i] = (window[i] - bases[i]) / gains[i]
        got_samples = window.shape[1]
        meta = dict(hdr, source_file=sig_file, storage="mat", skip=skip, got_samples=got_samples,
                    whole_file_bytes=len(blob))
    else:
        fmt = hdr["fmts"][0]
        if len(set(hdr["fmts"])) != 1:
            raise NotImplementedError("mixed storage formats across channels are not supported")
        frame_bytes = 2 * nsig  # format 16 only, enforced in _decode_dat_window
        total_frames = hdr["n_samples"] if hdr["n_samples"] else None
        want_frames = max(1, int(round(window_s * fs)))
        skip_frames = int(round(start_seconds * fs))
        if total_frames is not None:
            want_frames = min(want_frames, total_frames)
            skip_frames = max(0, min(skip_frames, max(0, total_frames - want_frames)))
        raw = _http_get_range(sig_url, skip_frames * frame_bytes, want_frames * frame_bytes, timeout=timeout)
        physical = _decode_dat_window(raw, nsig, gains, bases, fmt)
        meta = dict(hdr, source_file=sig_file, storage="dat", skip=skip_frames,
                    got_samples=physical.shape[1])

    out = np.empty_like(physical)
    for i in range(nsig):
        out[i] = to_microvolts(physical[i], _wfdb_unit_to_source(units[i]))
    meta["source_units"] = "microvolts"
    return out, list(names), float(fs), meta


class PhysioNetWFDBAdapter(Adapter):
    """Stream PhysioNet WFDB records (`.hea` + `.mat`/`.dat`) over HTTPS.

    `recording_id` is the WFDB record name/path exactly as given in `record_names` -- it already comes
    from the dataset's own record list rather than an enumeration index, so it is stable as long as that
    list is (the same guarantee `HttpEDFAdapter` gets from a URL basename).
    """

    units = "microvolts"

    def __init__(self, base_url: str, record_names: Sequence[str], dataset: str,
                 window_s: float = 300.0, subject_from_record=None) -> None:
        self.base_url = base_url.rstrip("/")
        self.record_names = list(record_names)
        self.dataset = dataset
        self.name = f"physionet_wfdb:{dataset}"
        self.window_s = window_s
        # A dataset with several recordings per subject MUST pass this, or subject-level splitting
        # silently degrades to recording-level splitting (see base.py's RecordingRef.__post_init__).
        self._subject_from_record = subject_from_record

    def list_recordings(self) -> List[RecordingRef]:
        out = []
        for rec in sorted(self.record_names):  # sorted == deterministic order
            out.append(RecordingRef(
                recording_id=rec, dataset=self.dataset,
                subject=(self._subject_from_record(rec) if self._subject_from_record else rec),
                load=self._make_loader(rec),
                meta={"base_url": self.base_url, "record": rec, "format": "wfdb"}))
        return out

    def _make_loader(self, rec: str):
        def load():
            return read_wfdb_window_http(self.base_url, rec, window_s=self.window_s)
        return load
