"""waveforms.py -- per-case multimodal intraoperative waveform loader (§7F, §9F, §11).

The deep-learning arm (protocol §9, §9F) consumes the *raw* intraoperative signals
that the tabular summaries discard: arterial blood pressure, ECG, photoplethysmogram,
and capnography. This module turns one VitalDB case into a fixed-shape segment tensor

    (n_windows, n_channels, win_len)   float32

suitable for the 1D-CNN encoder in ``encoder.py``.

Design mirrors the EEG project's ``pipeline/`` conventions (this repo is the
architectural template):

  * **Disk-sparing / streaming.** One case is processed at a time and released; the
    whole cohort is never held in memory. Tracks are fetched through
    ``vitaldb_aki.data.tracks.download_track`` (which caches one CSV per track and is
    resumable), exactly as the EEG pipeline streams one recording at a time.
  * **Lazy heavy imports.** numpy/scipy import *inside* functions so the windowing
    contract can be reasoned about without the scientific stack at import time.
  * **Leakage firewall (§11).** Samples are clipped to the intraoperative window
    ``[anestart|opstart, opend]`` and **no sample with t > opend is ever emitted**.
    opend is the prediction cutoff; this is the same rule the hemodynamics feature
    module enforces (``_intraop_window``).

VitalDB PACKED-CSV format (load-bearing)
----------------------------------------
The high-frequency SNUADC tracks (``SNUADC/ART``, ``SNUADC/ECG_II``, ``SNUADC/PLETH``)
are served as a two-column CSV whose **Time column is sparse**: only a few anchor rows
carry a timestamp; every other row is ``,<value>`` on an implicit uniform ~500 Hz grid.
The shared ``data.tracks.download_track`` keeps only rows where *both* columns parse,
so it silently drops the entire waveform and returns ~0 samples. We therefore parse the
cached CSV ourselves and reconstruct the time grid by linearly interpolating the
row-index -> timestamp map across the anchors -- mirroring
``features.aline_morphology.load_art_waveform``. ``Primus/CO2`` is a normal slow
per-row numeric track, so ``download_track`` is used directly for it. We never edit the
shared ``tracks.py``; ``download_track`` is still used to fetch + cache the file, and we
re-read it for the packed channels.

CPU-feasibility note
--------------------
One ART case at 500 Hz is ~3.5M samples. For the CPU feasibility proof we downsample
aggressively to a common low rate (``COMMON_RATE_HZ``, default 25 Hz) and cut fixed
10 s windows. Full-scale pretraining (higher rate, longer context) is a GPU job; see
``README.md`` for the boundary.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Config-readable constants (the single source of truth for the deep arm's
# signal geometry; mirror these into config.yaml under a `deep:` block when the
# arm is promoted from feasibility to a real run).
# ---------------------------------------------------------------------------

# The four verified-coverage intraoperative waveforms (cohort coverage in
# parentheses). The order here defines the channel axis of every emitted tensor.
# Fields: (channel_name, [candidate_track_names], packed?). `packed=True` means the
# VitalDB sparse-timestamp ~500 Hz format that download_track silently drops -- we use
# the local `load_packed_waveform` reconstruction for those. A case missing the
# invasive ART line still yields a tensor (that channel is zero-filled).
CHANNELS: list[tuple[str, list[str], bool]] = [
    ("ART", ["SNUADC/ART"], True),        # arterial BP, ~500 Hz packed, ~71% of cases
    ("ECG_II", ["SNUADC/ECG_II"], True),  # ECG lead II, ~500 Hz packed, ~99%
    ("PLETH", ["SNUADC/PLETH"], True),    # plethysmogram, ~500 Hz packed, ~98%
    ("CO2", ["Primus/CO2"], False),       # capnography (slow per-row numeric), ~99.7%
]

N_CHANNELS: int = len(CHANNELS)

# Nominal raw rate of the packed SNUADC tracks; used only when a case carries a
# single time anchor (no end-anchor to interpolate against).
PACKED_FS_HZ_NOMINAL: float = 500.0

# Common low sampling rate every channel is resampled to (Hz). 25 Hz keeps the
# ART pulse + capno waveform shape while making a multi-hour case CPU-tractable.
COMMON_RATE_HZ: float = 25.0

# Fixed window length in seconds and the derived sample count.
WINDOW_SECONDS: float = 10.0
WINDOW_LEN: int = int(round(WINDOW_SECONDS * COMMON_RATE_HZ))   # 250 samples

# Physiologic clip ranges per channel (artifact rejection). Values outside the
# range become NaN before resampling; NaNs are then interpolated/zero-filled.
# Ranges are deliberately wide -- this is artifact rejection, not feature gating.
CLIP_RANGES: dict[str, tuple[float, float]] = {
    "ART": (0.0, 300.0),       # mmHg; arterial-line flush gives negatives/zeros
    "ECG_II": (-5.0, 5.0),     # mV
    "PLETH": (-10.0, 4096.0),  # arbitrary ADC units
    "CO2": (0.0, 100.0),       # mmHg
}

# A window is kept only if at least this fraction of its samples are finite in
# EVERY channel that is actually present (a present-but-flatlined channel still
# passes; an all-NaN window is dropped).
MIN_FINITE_FRACTION: float = 0.5


# ---------------------------------------------------------------------------
# Intraoperative window (§11 leakage firewall) -- mirrors hemodynamics._intraop_window.
# ---------------------------------------------------------------------------
def intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) seconds for the intraoperative window of `case`.

    Priority: [anestart, opend] -> [opstart, opend] -> (None, opend).
    ``opend`` is mandatory (the §11 prediction cutoff). With no opend we return
    (None, None) and the caller must skip the case -- we cannot guarantee no
    postoperative sample leaks in.
    """
    def _f(key: str) -> float | None:
        v = case.get(key)
        if v is None or str(v).strip() in ("", "nan", "NA", "None"):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    opend = _f("opend")
    if opend is None:
        return None, None
    anestart = _f("anestart")
    if anestart is not None:
        return anestart, opend
    opstart = _f("opstart")
    if opstart is not None:
        return opstart, opend
    return None, opend


# ---------------------------------------------------------------------------
# Pure-numpy signal ops (testable on synthetic arrays, no network).
# ---------------------------------------------------------------------------
def clip_and_window_series(
    times,
    values,
    t_start: float | None,
    t_end: float,
    vmin: float,
    vmax: float,
    common_rate_hz: float = COMMON_RATE_HZ,
):
    """Resample one irregular (t, v) track onto a uniform grid over the intraop window.

    Steps (all leakage-safe -- nothing past ``t_end`` survives):
      1. Drop samples with t < t_start or **t > t_end** (the opend cutoff, §11).
      2. Reject samples outside [vmin, vmax] (artifact) -> they become gaps.
      3. Build a uniform time grid at ``common_rate_hz`` spanning [t0, t_end].
      4. Linearly interpolate the surviving samples onto the grid; grid points
         outside the support of any surviving sample are left as NaN.

    Returns a 1-D float64 numpy array on the uniform grid (NaN where unknown).
    Returns an empty array if no in-window samples survive.
    """
    import numpy as np

    t = np.asarray(times, dtype="float64")
    v = np.asarray(values, dtype="float64")
    if t.size == 0:
        return np.empty(0, dtype="float64")

    t0 = t_start if t_start is not None else float(t.min())
    # Hard intraop clip -- the load-bearing §11 guarantee.
    in_win = (t >= t0) & (t <= t_end)
    t, v = t[in_win], v[in_win]
    if t.size == 0:
        return np.empty(0, dtype="float64")

    # Artifact rejection -> gaps (np.interp skips NaN by us masking them out).
    good = np.isfinite(v) & (v >= vmin) & (v <= vmax)

    # Uniform grid over the FULL intraop window so all channels share a clock.
    n_grid = int(np.floor((t_end - t0) * common_rate_hz)) + 1
    if n_grid <= 0:
        return np.empty(0, dtype="float64")
    grid = t0 + np.arange(n_grid, dtype="float64") / common_rate_hz

    if good.sum() == 0:
        return np.full(n_grid, np.nan, dtype="float64")

    tg, vg = t[good], v[good]
    # np.interp clamps outside [tg.min, tg.max] to the endpoints; mark those as NaN
    # so we never invent signal beyond where the channel actually reported.
    out = np.interp(grid, tg, vg)
    out[grid < tg.min()] = np.nan
    out[grid > tg.max()] = np.nan
    return out.astype("float64")


def segment_into_windows(grids, win_len: int = WINDOW_LEN):
    """Stack per-channel uniform grids into (n_windows, n_channels, win_len).

    `grids` is a list of 1-D arrays (one per channel, possibly different lengths;
    a fully-absent channel may be ``None`` or empty -> zero-filled). All present
    channels are truncated to the shortest common length, then cut into
    non-overlapping windows of ``win_len`` samples (trailing remainder dropped).

    Per-window NaN handling:
      * windows where any present channel has < ``MIN_FINITE_FRACTION`` finite
        samples are dropped (too sparse to be meaningful);
      * remaining NaNs are filled with the per-channel-per-window mean (or 0 if
        the whole channel/window is NaN), i.e. mean-imputation inside the window.

    Returns a float32 array of shape (n_windows, n_channels, win_len). When no
    window survives, returns shape (0, n_channels, win_len).
    """
    import numpy as np

    n_ch = len(grids)
    arrs = []
    lengths = []
    for g in grids:
        if g is None:
            arrs.append(None)
            continue
        a = np.asarray(g, dtype="float64")
        arrs.append(a)
        if a.size:
            lengths.append(a.size)

    if not lengths:
        return np.zeros((0, n_ch, win_len), dtype="float32")

    common_len = min(lengths)
    n_windows = common_len // win_len
    if n_windows == 0:
        return np.zeros((0, n_ch, win_len), dtype="float32")

    # Build (n_ch, n_windows*win_len) then reshape to (n_ch, n_windows, win_len).
    usable = n_windows * win_len
    stacked = np.zeros((n_ch, usable), dtype="float64")
    present = np.zeros(n_ch, dtype=bool)
    for ci, a in enumerate(arrs):
        if a is None or a.size == 0:
            continue          # absent channel -> stays zero-filled
        stacked[ci] = a[:usable]
        present[ci] = True

    cube = stacked.reshape(n_ch, n_windows, win_len)            # (C, W, L)
    cube = np.transpose(cube, (1, 0, 2))                        # (W, C, L)

    keep = np.ones(n_windows, dtype=bool)
    out = np.empty_like(cube)
    for wi in range(n_windows):
        win = cube[wi]                                          # (C, L)
        ok = True
        for ci in range(n_ch):
            if not present[ci]:
                out[wi, ci] = 0.0
                continue
            ch = win[ci]
            finite = np.isfinite(ch)
            frac = finite.mean() if ch.size else 0.0
            if frac < MIN_FINITE_FRACTION:
                ok = False
                break
            fill = ch[finite].mean() if finite.any() else 0.0
            ch = np.where(finite, ch, fill)
            out[wi, ci] = ch
        keep[wi] = ok

    out = out[keep]
    return out.astype("float32")


# ---------------------------------------------------------------------------
# VitalDB packed-CSV waveform reader (mirrors aline_morphology.load_art_waveform).
# ---------------------------------------------------------------------------
def load_packed_waveform(cfg: dict[str, Any], caseid: str, candidates: list[str]):
    """Return (times, values) numpy arrays for a packed ~500 Hz SNUADC track.

    Reconstructs the uniform time grid from VitalDB's sparse-timestamp CSV: only a
    few rows carry a Time anchor; sample i sits on the row-index->time line through
    those anchors (exact for the common 2-anchor [start, end] case). Uses
    ``download_track`` only to fetch + cache the file, then re-reads it directly
    because download_track's per-row parser drops the packed waveform.

    Returns (None, None) if no candidate track exists for the case or no numeric
    samples are present.
    """
    import csv as _csv
    import os as _os

    import numpy as np

    from vitaldb_aki.data import tracks as _T

    tid = None
    chosen = None
    for tn in candidates:
        tid = _T.tid_for(cfg, caseid, tn)
        if tid:
            chosen = tn
            break
    if not tid:
        return None, None

    # Fetch + cache the file (we ignore download_track's parsed return, which drops
    # the packed waveform), then parse the cached CSV ourselves.
    _T.download_track(cfg, caseid, chosen)
    path = _os.path.join(cfg["data"]["cache_dir"], "tracks", f"{tid}.csv")
    if not _os.path.exists(path):
        return None, None

    anchor_idx: list[int] = []
    anchor_t: list[float] = []
    vals: list[float] = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = _csv.reader(fh)
        next(reader, None)  # header
        i = 0
        for rowi in reader:
            if not rowi:
                continue
            tcell = rowi[0].strip() if len(rowi) >= 1 else ""
            vcell = rowi[1].strip() if len(rowi) >= 2 else ""
            if tcell != "":
                try:
                    anchor_idx.append(i)
                    anchor_t.append(float(tcell))
                except ValueError:
                    pass
            if vcell != "":
                try:
                    vals.append(float(vcell))
                except ValueError:
                    vals.append(float("nan"))
            else:
                vals.append(float("nan"))
            i += 1

    if not vals or len(anchor_t) < 1:
        return None, None

    v = np.asarray(vals, dtype="float64")
    n = v.size
    if len(anchor_t) >= 2:
        t = np.interp(np.arange(n, dtype="float64"),
                      np.asarray(anchor_idx, dtype="float64"),
                      np.asarray(anchor_t, dtype="float64"))
    else:
        t0 = anchor_t[0]
        t = t0 + np.arange(n, dtype="float64") / PACKED_FS_HZ_NOMINAL

    good = np.isfinite(v)
    if not good.any():
        return None, None
    return t[good], v[good]


def _load_channel_series(cfg: dict[str, Any], caseid: str,
                         candidates: list[str], packed: bool):
    """Return (times, values) for one channel, dispatching on the packed flag.

    Packed SNUADC tracks -> `load_packed_waveform` (sparse-timestamp reconstruction).
    Slow per-row numeric tracks (CO2) -> the shared `download_track`, which parses
    them correctly. Returns (None, None) when the channel is absent.
    """
    if packed:
        return load_packed_waveform(cfg, caseid, candidates)

    import numpy as np
    from vitaldb_aki.data.tracks import first_available

    _tn, series = first_available(cfg, caseid, candidates)
    if not series:
        return None, None
    times = np.asarray([t for (t, _v) in series], dtype="float64")
    values = np.asarray([v for (_t, v) in series], dtype="float64")
    return times, values


# ---------------------------------------------------------------------------
# Per-case loader (downloads the 4 channels; disk-sparing).
# ---------------------------------------------------------------------------
def load_case_windows(cfg: dict[str, Any], case: dict[str, Any],
                      common_rate_hz: float = COMMON_RATE_HZ,
                      win_len: int = WINDOW_LEN):
    """Download + window one case's multimodal waveforms.

    Parameters
    ----------
    cfg : loaded config dict (provides data.cache_dir, api_base for `download_track`).
    case : a /cases row dict -- must carry ``caseid`` and the timing fields
           (``opend`` mandatory, ``anestart``/``opstart`` preferred) for §11 clipping.

    Returns
    -------
    numpy.ndarray, shape (n_windows, N_CHANNELS, win_len), float32.
    Empty (0, N_CHANNELS, win_len) when the case has no opend (skipped for safety),
    no in-window signal, or no window passes the finite-fraction gate.

    Disk-sparing: each track CSV is fetched/cached individually by
    ``download_track`` and only the small uniform grids are held; the raw
    multi-million-sample series is released as soon as it is resampled.
    """
    import numpy as np

    caseid = str(case.get("caseid", "")).strip()
    t_start, t_end = intraop_window(case)
    if t_end is None:
        # No opend -> cannot guarantee the §11 cutoff; skip the case.
        return np.zeros((0, N_CHANNELS, win_len), dtype="float32")

    grids: list[Any] = []
    for ch_name, candidates, packed in CHANNELS:
        times, values = _load_channel_series(cfg, caseid, candidates, packed)
        if times is None or values is None or len(times) == 0:
            grids.append(None)                       # absent -> zero-filled later
            continue
        vmin, vmax = CLIP_RANGES.get(ch_name, (-np.inf, np.inf))
        grid = clip_and_window_series(
            times, values, t_start, t_end, vmin, vmax, common_rate_hz
        )
        grids.append(grid if grid.size else None)
        # `times`, `values` go out of scope each iteration: only the compact uniform
        # grid (one float per 1/rate s) survives -> disk/RAM sparing.

    return segment_into_windows(grids, win_len)


def iter_case_windows(cfg: dict[str, Any], cases, common_rate_hz: float = COMMON_RATE_HZ,
                      win_len: int = WINDOW_LEN):
    """Yield (caseid, windows) one case at a time (the streaming contract).

    Never materializes the whole cohort: each case is downloaded, windowed,
    yielded, and released before the next is touched -- the same batch-and-release
    pattern as the EEG ``run_pass1`` loop. Cases that yield zero windows are
    skipped (not yielded).
    """
    for case in cases:
        caseid = str(case.get("caseid", "")).strip()
        windows = load_case_windows(cfg, case, common_rate_hz, win_len)
        if windows.shape[0] == 0:
            continue
        yield caseid, windows
