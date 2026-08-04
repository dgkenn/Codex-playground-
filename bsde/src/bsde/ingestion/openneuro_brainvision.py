"""BrainVision-over-HTTPS adapter for OpenNeuro's public S3 mirror.

WHY THIS EXISTS. `openneuro_s3.OpenNeuroS3Adapter` delegates loading to `read_edf_window_http`, which only
understands EDF's fixed-layout header. OpenNeuro dataset ds005620 is BrainVision (`.vhdr`/`.vmrk`/`.eeg`),
not EDF -- verified by enumerating its complete S3 key list: 21 subjects, 202 `.vhdr` recordings, tasks
`awake`/`sed`/`sed2`, acq `EC`/`EO`/`rest`/`tms`. Note the binary companion file's extension is `.eeg`, not
the `.dat` extension some other BrainVision exports use -- it is whatever `DataFile=` in the `.vhdr` says,
resolved relative to the `.vhdr`'s own URL, and this adapter never assumes a fixed extension for it.

REUSE, NOT REIMPLEMENTATION. S3 listing (`list_all_keys`, and via it `parse_list_objects_v2_xml`) and BIDS
subject extraction (`subject_from_bids_key`) are imported from `openneuro_s3.py` rather than duplicated here.
Byte-range fetching (`_http_get_range`, `_urlopen`) is imported from `http_edf.py` for the same reason --
one HTTPS-range implementation, with its CA-bundle / proxy handling, shared by every streaming adapter.

FORMAT. BrainVision splits a recording into three files: a small text header (`.vhdr`, INI-style, with
`[Common Infos]` / `[Binary Infos]` / `[Channel Infos]` sections), a marker file (`.vmrk`, unused here), and
the raw binary samples (commonly `.eeg`). Unlike EDF, the header does not encode its own binary layout in a
way that lets a byte-range GET be computed without first reading it -- but the header is tiny (a few KB),
so this adapter fetches it in full, then issues exactly ONE byte-range GET against the (potentially huge)
binary file for the requested window.

Two things this format does that EDF does not, and that a hasty implementation would get wrong:

  * `SamplingInterval` is in **microseconds**, not the sampling rate itself: `sfreq = 1e6 / SamplingInterval`.
  * A channel's resolution and unit fields (`Ch1=Fp1,,0.1,uV`) may be **empty**. BrainVision's own
    convention, applied here explicitly rather than left implicit, is: empty resolution -> 1.0 (no scaling
    beyond the raw digital value), empty unit -> microvolts (the format's overwhelmingly common case for
    scalp EEG). A recording that declares something else (mV, V, nV) is honoured via `to_microvolts`, never
    silently assumed to already be uV.

DATA ORIENTATION AND WHY VECTORIZED CANNOT BE STREAMED BY RANGE. `MULTIPLEXED` interleaves channels sample
by sample (`ch0@t0, ch1@t0, ..., chN@t0, ch0@t1, ...`), so any time window is one contiguous byte span --
exactly the shape a Range GET wants. `VECTORIZED` stores each channel's ENTIRE time series contiguously
(all of channel 0, then all of channel 1, ...); a time window then corresponds to N separate, far-apart byte
spans (one per channel), not one. This adapter refuses that case with `NotImplementedError` rather than
guessing or reading the whole file quietly, per this project's rule against silent fallback behaviour.

Only `INT_16` and `IEEE_FLOAT_32` binary formats are decoded, since those are what BrainVision EEG exports
in practice; anything else raises `NotImplementedError` naming the format rather than guessing a dtype.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from bsde.ingestion.base import Adapter, RecordingRef, to_microvolts
from bsde.ingestion.http_edf import _http_get_range, _urlopen
from bsde.ingestion.openneuro_s3 import list_all_keys, subject_from_bids_key

_S3_ENDPOINT = "https://s3.amazonaws.com"
_BUCKET = "openneuro.org"

_DTYPE_BY_FORMAT = {
    "INT_16": np.dtype("<i2"),
    "IEEE_FLOAT_32": np.dtype("<f4"),
}

_SECTION_RE = re.compile(r"^\[(.+)\]$")
_CHANNEL_KEY_RE = re.compile(r"^ch(\d+)$", re.IGNORECASE)
_BIDS_ENTITY_RE = re.compile(r"(?:^|[_/])(task|acq|run)-([A-Za-z0-9]+)")


# --------------------------------------------------------------------------------------------------------
# Pure parsing: .vhdr text -> dict. No network.
# --------------------------------------------------------------------------------------------------------

def parse_vhdr(text: str) -> Dict[str, Any]:
    """Parse a BrainVision `.vhdr` header. Pure function: no network, no filesystem.

    Handles a leading UTF-8 BOM and both LF and CRLF line endings identically. `.vhdr` is INI-style but not
    fed to `configparser`: its first line (`Brain Vision Data Exchange Header File Version 1.0`) sits above
    any `[Section]`, and channel lines pack four comma-separated sub-fields into one value
    (`Ch1=Fp1,,0.1,µV` -> name, reference channel, resolution, unit), which `configparser` does not
    unpack. A small hand-rolled line scanner is more direct than working around either of those.

    Returns a dict with (at least): `data_file`, `marker_file`, `n_channels`, `sfreq` (Hz, derived from
    `SamplingInterval`, which the format states in MICROSECONDS: `sfreq = 1e6 / SamplingInterval`),
    `binary_format` (e.g. `INT_16`, `IEEE_FLOAT_32`), `data_orientation` (`MULTIPLEXED`/`VECTORIZED`),
    `ch_names`, `resolutions` (per-channel float; an empty resolution field is BrainVision's convention for
    "no additional scaling", so it is treated as `1.0`), and `units` (per-channel string; an empty unit
    field is BrainVision's convention for microvolts, so it is treated as `µV` -- documented here rather
    than left as an implicit default, since it is silent in the file itself).
    """
    if text.startswith(chr(0xFEFF)):
        text = text[1:]
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    section: Optional[str] = None
    common: Dict[str, str] = {}
    binary: Dict[str, str] = {}
    channels: Dict[int, str] = {}

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        m = _SECTION_RE.match(line)
        if m:
            section = m.group(1).strip().lower()
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if section == "common infos":
            common[key.lower()] = value
        elif section == "binary infos":
            binary[key.lower()] = value
        elif section == "channel infos":
            ch_m = _CHANNEL_KEY_RE.match(key)
            if ch_m:
                channels[int(ch_m.group(1))] = value

    if not channels:
        raise ValueError("no [Channel Infos] entries found in .vhdr text")

    sampling_interval_raw = common.get("samplinginterval", "")
    try:
        sampling_interval_us = float(sampling_interval_raw)
    except ValueError:
        sampling_interval_us = 0.0
    if sampling_interval_us <= 0:
        raise ValueError(
            f"missing or invalid SamplingInterval in [Common Infos]: {sampling_interval_raw!r} "
            "(it must be a positive number of MICROSECONDS)")
    sfreq = 1e6 / sampling_interval_us

    n_channels_raw = common.get("numberofchannels", "")
    try:
        n_channels = int(n_channels_raw)
    except ValueError:
        n_channels = len(channels)

    ch_names: List[str] = []
    resolutions: List[float] = []
    units: List[str] = []
    for n in sorted(channels):
        parts = channels[n].split(",")
        name = parts[0].strip() if len(parts) > 0 else ""
        resolution_str = parts[2].strip() if len(parts) > 2 else ""
        unit = parts[3].strip() if len(parts) > 3 else ""
        resolution = float(resolution_str) if resolution_str else 1.0
        if not unit:
            unit = "µV"  # BrainVision convention: empty unit field means microvolts (documented above)
        ch_names.append(name)
        resolutions.append(resolution)
        units.append(unit)

    return dict(
        data_file=common.get("datafile", ""),
        marker_file=common.get("markerfile", ""),
        n_channels=n_channels,
        sfreq=sfreq,
        binary_format=binary.get("binaryformat", ""),
        data_orientation=common.get("dataorientation", "MULTIPLEXED"),
        ch_names=ch_names,
        resolutions=resolutions,
        units=units,
    )


def _check_format_and_orientation(binary_format: str, data_orientation: str) -> np.dtype:
    """Shared validation for `decode_brainvision_window` and `read_brainvision_window_http`, so an
    unsupported orientation is rejected BEFORE a network fetch, not only after."""
    fmt_key = str(binary_format).strip().upper()
    if fmt_key not in _DTYPE_BY_FORMAT:
        raise NotImplementedError(
            f"unsupported BrainVision binary format {binary_format!r}; only INT_16 and IEEE_FLOAT_32 are "
            "implemented here -- refusing to guess a decode for anything else.")

    orientation_key = str(data_orientation).strip().upper()
    if orientation_key != "MULTIPLEXED":
        raise NotImplementedError(
            f"BrainVision data orientation {data_orientation!r} is not supported for byte-range streaming. "
            "VECTORIZED stores each channel's ENTIRE time series contiguously (all of channel 0's samples, "
            "then all of channel 1's, ...), so a single contiguous byte range covering one time window "
            "covers a different sample index in every channel but the first -- there is no contiguous byte "
            "span that means 'this time window, every channel', unlike MULTIPLEXED. Reading it correctly "
            "would need one separate range GET per channel, which defeats the point of windowed streaming, "
            "so it is refused rather than silently done wrong."
        )
    return _DTYPE_BY_FORMAT[fmt_key]


def decode_brainvision_window(raw: bytes, n_channels: int, binary_format: str, data_orientation: str,
                               resolutions: Sequence[float], units: Sequence[str]) -> np.ndarray:
    """Decode a byte-range window of BrainVision binary samples into `(n_channels, n_samples)` MICROVOLTS.
    Pure function: no network, no filesystem.

    `raw` must start at a MULTIPLEXED frame boundary (`n_channels` samples per frame); the caller is
    responsible for having fetched an aligned span. Per-channel `resolution` is applied first (raw digital
    value * resolution == value in the channel's declared unit), then `to_microvolts` converts from that
    declared unit -- so channels with different units or different resolutions are each handled correctly,
    not scaled by one global factor.
    """
    dtype = _check_format_and_orientation(binary_format, data_orientation)

    if n_channels <= 0:
        raise ValueError("n_channels must be positive")
    if len(resolutions) != n_channels or len(units) != n_channels:
        raise ValueError(
            f"resolutions/units must each have exactly n_channels ({n_channels}) entries; "
            f"got {len(resolutions)}/{len(units)}")

    itemsize = dtype.itemsize
    frame_bytes = n_channels * itemsize
    n_frames = len(raw) // frame_bytes
    if n_frames == 0:
        raise ValueError(
            f"fetched window ({len(raw)} bytes) is shorter than one MULTIPLEXED frame ({frame_bytes} bytes "
            f"for {n_channels} channels of {binary_format})")

    usable = n_frames * frame_bytes
    arr = np.frombuffer(raw[:usable], dtype=dtype).reshape(n_frames, n_channels).T  # -> (n_channels, n_frames)

    out = np.empty((n_channels, n_frames), dtype=np.float64)
    for ch in range(n_channels):
        declared_unit_value = arr[ch].astype(np.float64) * float(resolutions[ch])
        out[ch] = to_microvolts(declared_unit_value, units[ch])
    return out


# --------------------------------------------------------------------------------------------------------
# Network: fetch the .vhdr in full, then ONE byte-range GET for the window of the binary file.
# --------------------------------------------------------------------------------------------------------

def read_brainvision_window_http(vhdr_url: str, window_s: float = 300.0, start_seconds: float = 0.0,
                                  timeout: float = 60.0) -> Tuple[np.ndarray, List[str], float, Dict[str, Any]]:
    """Fetch a `.vhdr` header in full (it is small), resolve its `DataFile` relative to the `.vhdr`'s own
    URL, then issue exactly ONE byte-range GET for the requested window of the binary file and decode it.

    Returns `(data_uV[n_channels, n_samples], ch_names, sfreq, meta)`. `meta` records `binary_format`,
    `data_orientation`, `source_units` (per-channel, as declared in the header), and `bytes_fetched` (the
    size of the ONE range GET against the binary file -- deliberately far smaller than the whole file for
    any window short relative to the recording).
    """
    req = urllib.request.Request(vhdr_url)
    with _urlopen(req, timeout=timeout) as resp:
        header_bytes = resp.read()
    text = header_bytes.decode("utf-8", errors="replace")
    header = parse_vhdr(text)

    if not header["data_file"]:
        raise ValueError(f"no DataFile= declared in .vhdr at {vhdr_url}")
    data_url = urllib.parse.urljoin(vhdr_url, header["data_file"])

    sfreq = header["sfreq"]
    n_channels = header["n_channels"]
    binary_format = header["binary_format"]
    data_orientation = header["data_orientation"]
    resolutions = header["resolutions"]
    units = header["units"]

    dtype = _check_format_and_orientation(binary_format, data_orientation)  # raises before any range GET
    frame_bytes = n_channels * dtype.itemsize

    start_frame = max(0, int(round(start_seconds * sfreq)))
    want_frames = max(1, int(round(window_s * sfreq)))
    start_byte = start_frame * frame_bytes
    length = want_frames * frame_bytes

    raw = _http_get_range(data_url, start_byte, length, timeout=timeout)
    data = decode_brainvision_window(
        raw, n_channels=n_channels, binary_format=binary_format, data_orientation=data_orientation,
        resolutions=resolutions, units=units)

    meta = dict(
        binary_format=binary_format,
        data_orientation=data_orientation,
        source_units=list(units),
        bytes_fetched=len(raw),
        data_file=header["data_file"],
        data_url=data_url,
        start_frame=start_frame,
    )
    return data, list(header["ch_names"]), float(sfreq), meta


def _bids_entities(key: str) -> Dict[str, str]:
    """Pull `task-`/`acq-`/`run-` BIDS entities out of an S3 key. These are the state labels this dataset
    exists to compare (awake/sed/sed2 x EC/EO/rest/tms), so they go straight into `RecordingRef.meta`."""
    return {name: value for name, value in _BIDS_ENTITY_RE.findall(key)}


class OpenNeuroBrainVisionAdapter(Adapter):
    """Stream BrainVision recordings from an OpenNeuro dataset's public S3 mirror, anonymously, over HTTPS.

    `recording_id` is the full S3 object key (e.g. `ds005620/sub-1010/eeg/sub-1010_task-awake_acq-EC_eeg.vhdr`),
    stable across runs and never an enumeration index over the (paginated) listing.

    `subject` is REQUIRED to come from `subject_from_bids_key`, never left to default to `recording_id`:
    ds005620 has up to 202 recordings across 21 subjects (multiple tasks/acq per subject), so defaulting
    would silently turn subject-level splitting into recording-level splitting and understate every
    confidence interval -- exactly the failure `RecordingRef.__post_init__` warns is unsafe here.
    """

    units = "microvolts"

    def __init__(self, accession: str, dataset: Optional[str] = None, window_s: float = 300.0,
                 start_seconds: float = 0.0, suffix: str = "_eeg.vhdr") -> None:
        self.accession = accession
        self.dataset = dataset or accession
        self.name = f"openneuro_brainvision:{self.accession}"
        self.window_s = window_s
        self.start_seconds = start_seconds
        self.suffix = suffix

    def list_recordings(self) -> List[RecordingRef]:
        prefix = f"{self.accession}/"
        keys = [k for k in list_all_keys(_BUCKET, prefix) if k.endswith(self.suffix)]
        out = []
        for key in sorted(keys):  # sorted == deterministic order, independent of S3 listing order/paging
            url = f"{_S3_ENDPOINT}/{_BUCKET}/{key}"
            meta: Dict[str, Any] = {"url": url, "key": key, "format": "brainvision"}
            meta.update(_bids_entities(key))
            out.append(RecordingRef(
                recording_id=key, dataset=self.dataset,
                subject=subject_from_bids_key(key),
                load=self._make_loader(url),
                meta=meta))
        return out

    def _make_loader(self, url: str):
        def load():
            return read_brainvision_window_http(url, window_s=self.window_s, start_seconds=self.start_seconds)
        return load
