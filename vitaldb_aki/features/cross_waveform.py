"""cross_waveform.py -- Cross-channel coupling features (§7F novel biomarkers).

Individual signals (MAP, HR, SpO2) are well-mined in the tabular and
hemodynamics modules. The novelty here is COUPLING BETWEEN simultaneously
recorded waveforms: features that only exist when two channels are present and
synchronized. These are candidate novel biomarkers for postoperative organ
damage (AKI, hemodynamic failure) that could add incremental discrimination
beyond single-channel summaries.

Mechanistic grounding
---------------------
1. **Pulse Arrival Time (PAT)**: ECG R-peak to PPG foot delay. Encodes
   vascular transit time = arterial stiffness + pre-ejection period. Prolonged
   or variable PAT signals increased stiffness (endothelial / vascular
   dysfunction) or poor cardiac output — both AKI risk factors.

2. **Central-peripheral perfusion decoupling**: ART pulse amplitude (SBP-DBP)
   vs. PPG pulse amplitude (and PPG perfusion index AC/DC). When the two
   decouple (central BP maintained but peripheral PPG drops), microcirculatory
   failure is indicated — a sensitive early marker of tissue hypoperfusion
   before global MAP falls.

3. **Baroreflex sensitivity (BRS)**: spontaneous coupling of beat-to-beat SBP
   changes with the next RR interval (ECG). High BRS = intact autonomic
   cardiovascular regulation; low BRS predicts postoperative complications.
   Sequence method (≥3 consecutive SBP-RR pairs with same-sign slope).

4. **Cardiopulmonary coupling**: spectral coherence between beat-to-beat SBP
   (or PPG amplitude) and the capnography envelope (Primus/CO2 respiratory
   signal) in the respiratory band (0.05-0.4 Hz). High coherence = tight
   respiratory-cardiovascular coupling; loss of coupling = autonomic
   impairment.

-----------------------------------------------------------------------
WINDOWING AND MEMORY DISCIPLINE (mirrors aline_morphology.py)
-----------------------------------------------------------------------
We never hold the full 500 Hz traces in memory. We carve the intraop window
into ANALYSIS_WINDOW_S (30 s) segments sampled every WINDOW_PERIOD_S (5 min),
capped at MAX_ANALYSIS_WINDOWS (60). Only per-beat scalars and per-window
aggregates are retained.

The Primus/CO2 track is ~62.5 Hz (slow enough to hold in a window buffer).

-----------------------------------------------------------------------
CHANNELS (verified coverage in cohort)
-----------------------------------------------------------------------
  SNUADC/ECG_II   500 Hz  99 % coverage
  SNUADC/PLETH    500 Hz  98 % coverage (PPG / photoplethysmography)
  SNUADC/ART      500 Hz  71 % coverage (arterial pressure)
  Primus/CO2      ~62.5 Hz  99.7 % coverage (capnography)

All SNUADC/* tracks are in VitalDB's PACKED sparse-timestamp format, so we
use the same reconstruction approach as load_art_waveform() in
aline_morphology.py (generalized to any SNUADC channel).

-----------------------------------------------------------------------
LEAKAGE (§11)
-----------------------------------------------------------------------
All features are "intraop"; never t > opend. audit_specs() enforces this
at import.

Protocol: §7C (hemodynamic axis), §7F (raw waveform coupling).
"""
from __future__ import annotations

import csv as _csv
import os as _os
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Track names (all SNUADC/* are packed; Primus/CO2 is a normal slow track).
# ---------------------------------------------------------------------------
ECG_TRACK: str = "SNUADC/ECG_II"
PPG_TRACK: str = "SNUADC/PLETH"
ART_TRACK: str = "SNUADC/ART"
CO2_TRACK: str = "Primus/CO2"

# Nominal sampling rates.
FS_HZ_SNUADC: float = 500.0
FS_HZ_CO2: float = 62.5

# ---------------------------------------------------------------------------
# Windowing constants (mirrors aline_morphology.py approach).
# ---------------------------------------------------------------------------
ANALYSIS_WINDOW_S: float = 30.0      # slightly longer window for spectral features
WINDOW_PERIOD_S: float = 300.0       # one window every 5 min
MAX_ANALYSIS_WINDOWS: int = 60

# ---------------------------------------------------------------------------
# Physiologic gates (binding; documented in pre-registration).
# ---------------------------------------------------------------------------
HR_MIN_BPM: float = 40.0
HR_MAX_BPM: float = 200.0
SBP_MIN: float = 40.0
SBP_MAX: float = 250.0
DBP_MIN: float = 10.0
DBP_MAX: float = 150.0
PP_MIN: float = 5.0
# PAT physiologic range (ms): cardiac cycle traversal
PAT_MIN_MS: float = 80.0    # very fast transit (stiff vessel / high CO)
PAT_MAX_MS: float = 600.0   # very slow transit

# BRS sequence method thresholds
BRS_MIN_SLOPE_MS_MMHG: float = 0.5   # ~0.5 ms/mmHg (very blunted)
BRS_MAX_SLOPE_MS_MMHG: float = 40.0  # physiologic ceiling
BRS_MIN_SEQ_LEN: int = 3              # minimum consecutive SBP-RR pairs

# Spectral bands (Hz)
RESP_BAND_LO: float = 0.05
RESP_BAND_HI: float = 0.40

# ---------------------------------------------------------------------------
# Feature specs (all "comprehensive", all "intraop").
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # -- Availability --
    FeatureSpec("cross_waveform_available", "comprehensive", "intraop",
                "1 if >=2 simultaneous waveform channels were usable for cross-channel "
                "features, else 0"),

    # -- Pulse Arrival Time (PAT): ECG R-peak -> PPG foot --
    FeatureSpec("pat_mean_ms", "comprehensive", "intraop",
                "mean pulse arrival time (ms) = ECG R-peak to PPG foot; "
                "inverse-BP / arterial-stiffness surrogate (§7F)"),
    FeatureSpec("pat_sd_ms", "comprehensive", "intraop",
                "SD of beat-to-beat PAT (ms); PAT variability as autonomic / "
                "vascular-tone marker (§7F)"),
    FeatureSpec("pat_slope", "comprehensive", "intraop",
                "linear slope of PAT (ms/min) over the case; rising = stiffening "
                "/ declining perfusion; falling = vasodilation (§7F)"),

    # -- Central-peripheral perfusion decoupling (ART + PPG) --
    FeatureSpec("art_ppg_amp_corr", "comprehensive", "intraop",
                "Pearson r between per-beat ART pulse amplitude (SBP-DBP) and PPG "
                "pulse amplitude across the case; near 1 = coupled; near 0 or "
                "negative = decoupled (microvascular failure) (§7F)"),
    FeatureSpec("central_peripheral_decoupling", "comprehensive", "intraop",
                "1 - |art_ppg_amp_corr|; 0 = perfectly coupled, 1 = fully "
                "decoupled; primary novelty biomarker (§7F)"),

    # -- Baroreflex sensitivity (BRS): ART SBP + ECG RR --
    FeatureSpec("brs_mean", "comprehensive", "intraop",
                "mean baroreflex sensitivity (ms/mmHg) from spontaneous SBP-RR "
                "sequences (sequence method); low = impaired autonomic control (§7F)"),
    FeatureSpec("brs_n_sequences", "comprehensive", "intraop",
                "number of valid SBP-RR sequences used for BRS estimate; "
                "higher = more reliable estimate (§7F)"),

    # -- Cardiopulmonary coupling (ART/PPG + Primus/CO2) --
    FeatureSpec("cardiopulm_coherence", "comprehensive", "intraop",
                "mean spectral coherence (0-1) between beat-to-beat RR / SBP and "
                "capnography envelope in the respiratory band (0.05-0.40 Hz); "
                "1 = tight respiratory-cardiovascular coupling (§7F)"),
    FeatureSpec("resp_sbp_coupling", "comprehensive", "intraop",
                "mean squared coherence between CO2 respiratory envelope and "
                "beat-to-beat SBP in the respiratory band (§7F)"),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Pure computational helpers (lazy numpy/scipy imports inside functions).
# ===========================================================================

def pulse_arrival_times(ecg: "Any", ppg: "Any", fs: float) -> "Any":
    """Compute per-beat pulse arrival times (ms) from ECG and PPG.

    Parameters
    ----------
    ecg : array-like
        ECG_II samples at `fs` Hz. R-peaks are tall positive deflections.
    ppg : array-like
        PLETH (PPG) samples at `fs` Hz, synchronised with `ecg`.
    fs  : float
        Sampling rate (Hz) of both signals.

    Returns
    -------
    pat_ms : np.ndarray
        1-D array of PAT values (ms), one per beat where a valid PPG foot was
        found in the 80-400 ms search window after the R-peak. Empty if no
        valid beats.

    Algorithm
    ---------
    1. Detect ECG R-peaks (tall positive peaks with refractory distance from
       HR_MAX_BPM and prominence based on robust signal range).
    2. For each R-peak, search for the PPG foot (minimum of PPG) in the
       window [0.08 s, 0.40 s] after the peak (physiologic PAT range).
    3. Gate: PAT_MIN_MS <= PAT <= PAT_MAX_MS; drop outliers.
    """
    import numpy as np
    from scipy.signal import find_peaks

    ecg_arr = np.asarray(ecg, dtype=float)
    ppg_arr = np.asarray(ppg, dtype=float)
    n = min(ecg_arr.size, ppg_arr.size)
    if n < int(fs) or fs <= 0:
        return np.empty(0, dtype=float)
    ecg_arr = ecg_arr[:n]
    ppg_arr = ppg_arr[:n]

    # R-peak detection: refractory from max HR
    min_dist = max(1, int(fs * 60.0 / HR_MAX_BPM))
    # Prominence: 20% of robust ECG range
    rng = float(np.nanpercentile(ecg_arr, 95) - np.nanpercentile(ecg_arr, 5))
    prominence = max(0.05, 0.2 * rng)  # ECG is in mV-scale (dimensionless here)

    r_peaks, _ = find_peaks(ecg_arr, distance=min_dist, prominence=prominence)
    if r_peaks.size < 2:
        return np.empty(0, dtype=float)

    # PAT search window bounds (samples)
    lo_samp = max(1, int(PAT_MIN_MS * fs / 1000.0))   # 80 ms
    hi_samp = min(n, int(PAT_MAX_MS * fs / 1000.0))   # 400 ms (search window)

    pats: list[float] = []
    for rp in r_peaks:
        lo = int(rp) + lo_samp
        hi = int(rp) + hi_samp
        if hi > n:
            continue
        seg = ppg_arr[lo:hi]
        if seg.size == 0:
            continue
        foot_rel = int(np.argmin(seg))
        pat_samp = lo_samp + foot_rel
        pat_ms = pat_samp * 1000.0 / fs
        if PAT_MIN_MS <= pat_ms <= PAT_MAX_MS:
            pats.append(pat_ms)

    return np.asarray(pats, dtype=float)


def beat_amplitudes(sig: "Any", fs: float,
                    ppg: bool = True) -> "Any":
    """Per-beat amplitude series from a PPG (or ART) signal.

    For PPG (photoplethysmography): amplitude = peak - trough (systolic
    excursion, proportional to stroke volume at the periphery).
    For ART: amplitude = SBP - DBP = pulse pressure.

    Parameters
    ----------
    sig : array-like
        1-D signal at `fs` Hz.
    fs  : float
        Sampling rate (Hz).
    ppg : bool
        If True, treat `sig` as PPG (invert for trough detection).
        If False, treat as ART pressure (peak = systolic, trough = diastolic).

    Returns
    -------
    amplitudes : np.ndarray
        1-D array of per-beat amplitudes, one per detected pulse.
    """
    import numpy as np
    from scipy.signal import find_peaks

    arr = np.asarray(sig, dtype=float)
    n = arr.size
    if n < int(fs) or fs <= 0:
        return np.empty(0, dtype=float)

    min_dist = max(1, int(fs * 60.0 / HR_MAX_BPM))
    rng = float(np.nanpercentile(arr, 95) - np.nanpercentile(arr, 5))

    if ppg:
        # PPG peaks (positive deflections)
        prominence = max(0.01, 0.15 * rng)
        peaks, _ = find_peaks(arr, distance=min_dist, prominence=prominence)
        # Trough = minimum between consecutive peaks
        amps: list[float] = []
        for i in range(len(peaks) - 1):
            p1, p2 = int(peaks[i]), int(peaks[i + 1])
            trough = float(np.min(arr[p1:p2 + 1]))
            amp = float(arr[p1]) - trough
            if amp > 0:
                amps.append(amp)
    else:
        # ART: systolic peaks
        prominence = max(PP_MIN, 0.2 * rng)
        peaks, _ = find_peaks(arr, distance=min_dist, prominence=prominence)
        max_cycle = max(min_dist + 1, int(fs * 60.0 / HR_MIN_BPM))
        amps = []
        for pk in peaks:
            lo = max(0, int(pk) - max_cycle)
            seg = arr[lo:int(pk) + 1]
            if seg.size < 2:
                continue
            sbp = float(arr[int(pk)])
            dbp = float(np.min(seg))
            pp = sbp - dbp
            if PP_MIN <= pp <= 200.0 and SBP_MIN <= sbp <= SBP_MAX:
                amps.append(pp)

    return np.asarray(amps, dtype=float)


def brs_sequence(sbp: "Any", rr: "Any",
                 min_len: int = BRS_MIN_SEQ_LEN) -> tuple["Any", int]:
    """Baroreflex sensitivity via the sequence method.

    Finds spontaneous sequences of >=`min_len` consecutive beats where SBP
    and RR change in the same direction (both up or both down), computes the
    linear slope SBP->RR for each sequence, and returns all slopes plus the
    total sequence count.

    Parameters
    ----------
    sbp : array-like
        Beat-to-beat systolic blood pressure (mmHg), one value per beat.
    rr  : array-like
        Beat-to-beat RR interval (ms), one value per beat (same length as sbp).
    min_len : int
        Minimum run length to count as a sequence (default 3).

    Returns
    -------
    slopes : np.ndarray
        BRS slopes (ms/mmHg) for each qualifying sequence. Empty if none.
    n_sequences : int
        Total number of qualifying sequences found.

    Notes
    -----
    Physiologic gate: BRS_MIN_SLOPE <= slope <= BRS_MAX_SLOPE to exclude
    spurious sequences (ectopy, noise).
    """
    import numpy as np

    s = np.asarray(sbp, dtype=float)
    r = np.asarray(rr, dtype=float)
    n = min(s.size, r.size)
    if n < min_len + 1:
        return np.empty(0, dtype=float), 0

    s = s[:n]
    r = r[:n]

    # Direction of change at each beat transition.
    ds = np.sign(np.diff(s))   # +1 rise, -1 fall, 0 flat
    dr = np.sign(np.diff(r))

    # Concordant = same non-zero sign.
    concordant = (ds == dr) & (ds != 0)

    slopes: list[float] = []
    n_seqs = 0
    i = 0
    while i < concordant.size:
        if concordant[i]:
            j = i
            while j < concordant.size and concordant[j]:
                j += 1
            run_len = j - i + 1  # +1 because a run of k concordant diffs spans k+1 beats
            if run_len >= min_len:
                # Fit slope over the run (indices i..j in the original arrays)
                seg_s = s[i: j + 1]
                seg_r = r[i: j + 1]
                if np.std(seg_s) > 0:
                    slope = float(np.polyfit(seg_s, seg_r, 1)[0])
                    if BRS_MIN_SLOPE_MS_MMHG <= slope <= BRS_MAX_SLOPE_MS_MMHG:
                        slopes.append(slope)
                        n_seqs += 1
            i = j
        else:
            i += 1

    return np.asarray(slopes, dtype=float), n_seqs


def spectral_coherence(x: "Any", y: "Any", fs: float,
                       band: tuple[float, float] = (RESP_BAND_LO, RESP_BAND_HI)
                       ) -> float | None:
    """Mean squared coherence between two signals in a frequency band.

    Parameters
    ----------
    x, y : array-like
        Same-length 1-D time series at `fs` Hz.
    fs   : float
        Sampling rate (Hz).
    band : (lo, hi) tuple
        Frequency band (Hz) to average coherence over.

    Returns
    -------
    msc : float or None
        Mean squared coherence in [0, 1] for the band. None if insufficient
        data or numerical failure.

    Notes
    -----
    Uses scipy.signal.coherence (Welch cross-spectral density method). A
    minimum of 4 non-overlapping Welch segments is required; if the signal is
    too short, returns None.
    """
    import numpy as np
    from scipy.signal import coherence as _coherence

    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    n = min(xa.size, ya.size)
    if n < 2 or fs <= 0:
        return None
    xa, ya = xa[:n], ya[:n]

    # Welch segment length: nperseg = 4 * fs / band_lo (enough cycles for the
    # lowest frequency of interest), but no longer than n // 4.
    nperseg = min(n // 4, max(16, int(4.0 * fs / band[0])))
    if nperseg < 8 or n < nperseg:
        return None

    try:
        freqs, coh = _coherence(xa, ya, fs=fs, nperseg=nperseg)
    except Exception:
        return None

    in_band = (freqs >= band[0]) & (freqs <= band[1])
    if not in_band.any():
        return None
    return float(np.mean(coh[in_band]))


# ===========================================================================
# Packed-waveform loader (generalises load_art_waveform from aline_morphology)
# ===========================================================================

def load_snuadc_waveform(cfg: dict[str, Any], caseid: str,
                         tname: str) -> tuple["Any | None", "Any | None"]:
    """Return (times, values) numpy arrays for any SNUADC/* packed track.

    VitalDB's SNUADC waveforms (ART, ECG_II, PLETH) use a sparse-timestamp
    "packed" CSV format where only the first/last rows carry a timestamp; all
    intermediate rows are ',<value>'. The shared download_track() drops these
    because it requires both columns to be numeric. This function re-reads the
    cached file and reconstructs the uniform time grid via anchor interpolation.

    Time-anchor validation: we skip any cell that does not parse as float
    *before* appending to anchor_idx / anchor_t so the two lists always stay
    the same length and np.interp never sees mismatched arrays.

    Falls back to (None, None) if the track is absent or has no numeric samples.
    """
    import numpy as np
    from vitaldb_aki.data import tracks as _T

    tid = _T.tid_for(cfg, caseid, tname)
    if not tid:
        return None, None

    # Ensure the file is fetched and cached (download_track writes it).
    _T.download_track(cfg, caseid, tname)
    path = _os.path.join(cfg["data"]["cache_dir"], "tracks", f"{tid}.csv")
    if not _os.path.exists(path):
        return None, None

    anchor_idx: list[int] = []
    anchor_t: list[float] = []
    vals: list[float] = []

    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = _csv.reader(fh)
        next(reader, None)  # skip header
        i = 0
        for row in reader:
            if not row:
                continue
            tcell = row[0].strip() if len(row) >= 1 else ""
            vcell = row[1].strip() if len(row) >= 2 else ""

            # Validate timestamp as float BEFORE appending to both lists
            # (keeps anchor_idx and anchor_t in lockstep -- prevents index/value
            # divergence that caused crashes in the prior implementation).
            if tcell != "":
                try:
                    t_val = float(tcell)
                    anchor_idx.append(i)
                    anchor_t.append(t_val)
                except ValueError:
                    pass  # non-numeric time cell: skip (do NOT append index)

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

    v = np.asarray(vals, dtype=float)
    n = v.size

    if len(anchor_t) >= 2:
        t = np.interp(np.arange(n, dtype=float),
                      np.asarray(anchor_idx, dtype=float),
                      np.asarray(anchor_t, dtype=float))
    else:
        # Single anchor: assume nominal fs
        t0 = anchor_t[0]
        t = t0 + np.arange(n, dtype=float) / FS_HZ_SNUADC

    good = np.isfinite(v)
    if not good.any():
        return None, None
    return t[good], v[good]


def _intraop_clip(t: "Any", v: "Any",
                  t_start: float | None, t_end: float | None) -> tuple["Any", "Any"]:
    """Apply intraop window clip [t_start, t_end] to (t, v) arrays. Pure."""
    import numpy as np
    mask = np.ones(t.shape, dtype=bool)
    if t_start is not None:
        mask &= t >= t_start
    if t_end is not None:
        mask &= t <= t_end
    return t[mask], v[mask]


def _window_starts(t0: float, t_end: float) -> list[float]:
    """Analysis-window start times (one per WINDOW_PERIOD_S, capped)."""
    if t_end <= t0:
        return []
    starts: list[float] = []
    s = t0
    while s + ANALYSIS_WINDOW_S <= t_end and len(starts) < MAX_ANALYSIS_WINDOWS:
        starts.append(s)
        s += WINDOW_PERIOD_S
    if not starts and (t_end - t0) >= 1.0:
        starts.append(t0)
    return starts


def _slice_window(t: "Any", v: "Any",
                  ws: float, we: float) -> tuple["Any", "Any"]:
    """Return samples in [ws, we)."""
    import numpy as np
    sel = (t >= ws) & (t < we)
    return t[sel], v[sel]


def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) for the intraop window (mirrors aline_morphology)."""
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


# ===========================================================================
# Per-window computation (returns dict of per-window scalars).
# ===========================================================================

def _process_window_ecg_ppg(ecg_t: "Any", ecg_v: "Any",
                             ppg_t: "Any", ppg_v: "Any",
                             fs: float) -> dict[str, Any]:
    """PAT and PPG beat-amplitude features for one analysis window.

    Interpolates PPG onto the ECG time grid so both are synchronised at the
    same sample rate `fs`. Returns dict with keys:
      pat_ms_arr, ppg_amp_arr
    (both numpy arrays, possibly empty).
    """
    import numpy as np

    # Both must span roughly the same window; interpolate PPG onto ECG times.
    if ecg_t.size < int(fs) or ppg_t.size < int(fs):
        return {"pat_ms_arr": np.empty(0), "ppg_amp_arr": np.empty(0)}

    # Resample PPG to ECG time grid if necessary (they may have slightly different
    # numbers of samples due to packet loss).
    ppg_resampled = np.interp(ecg_t, ppg_t, ppg_v,
                              left=float("nan"), right=float("nan"))
    good = np.isfinite(ppg_resampled)
    if not good.any():
        return {"pat_ms_arr": np.empty(0), "ppg_amp_arr": np.empty(0)}

    pat_arr = pulse_arrival_times(ecg_v, ppg_resampled, fs)
    ppg_amp_arr = beat_amplitudes(ppg_resampled, fs, ppg=True)
    return {"pat_ms_arr": pat_arr, "ppg_amp_arr": ppg_amp_arr}


def _process_window_art_ppg(art_t: "Any", art_v: "Any",
                             ppg_t: "Any", ppg_v: "Any",
                             fs: float) -> dict[str, Any]:
    """ART and PPG amplitude coupling for one analysis window.

    Returns dict with keys:
      art_pp_arr, ppg_amp_arr
    """
    import numpy as np

    if art_t.size < int(fs) or ppg_t.size < int(fs):
        return {"art_pp_arr": np.empty(0), "ppg_amp_arr": np.empty(0)}

    art_pp = beat_amplitudes(art_v, fs, ppg=False)
    ppg_amp = beat_amplitudes(ppg_v, fs, ppg=True)
    return {"art_pp_arr": art_pp, "ppg_amp_arr": ppg_amp}


def _process_window_brs(art_t: "Any", art_v: "Any",
                        ecg_t: "Any", ecg_v: "Any",
                        fs: float) -> dict[str, Any]:
    """BRS (baroreflex sensitivity) for one analysis window.

    Extracts per-beat SBP from ART and RR intervals from ECG, then applies
    the sequence method. Returns dict with keys:
      brs_slopes, n_sequences
    """
    import numpy as np
    from scipy.signal import find_peaks

    if art_t.size < int(fs) or ecg_t.size < int(fs):
        return {"brs_slopes": np.empty(0), "n_sequences": 0}

    # --- SBP series from ART ---
    min_dist = max(1, int(fs * 60.0 / HR_MAX_BPM))
    max_cycle = max(min_dist + 1, int(fs * 60.0 / HR_MIN_BPM))
    rng_art = float(np.nanpercentile(art_v, 95) - np.nanpercentile(art_v, 5))
    prominence_art = max(PP_MIN, 0.2 * rng_art)
    art_peaks, _ = find_peaks(art_v, distance=min_dist, prominence=prominence_art)

    sbp_list: list[float] = []
    for pk in art_peaks:
        lo = max(0, int(pk) - max_cycle)
        seg = art_v[lo:int(pk) + 1]
        sbp = float(art_v[int(pk)])
        dbp = float(np.min(seg))
        if SBP_MIN <= sbp <= SBP_MAX and DBP_MIN <= dbp <= DBP_MAX and (sbp - dbp) >= PP_MIN:
            sbp_list.append(sbp)

    if len(sbp_list) < BRS_MIN_SEQ_LEN + 1:
        return {"brs_slopes": np.empty(0), "n_sequences": 0}

    # --- RR intervals from ECG ---
    rng_ecg = float(np.nanpercentile(ecg_v, 95) - np.nanpercentile(ecg_v, 5))
    prominence_ecg = max(0.05, 0.2 * rng_ecg)
    r_peaks, _ = find_peaks(ecg_v, distance=min_dist, prominence=prominence_ecg)
    if r_peaks.size < 2:
        return {"brs_slopes": np.empty(0), "n_sequences": 0}
    rr_ms_arr = np.diff(r_peaks.astype(float)) * 1000.0 / fs  # ms

    # Match lengths (take min available beats)
    n_beats = min(len(sbp_list), len(rr_ms_arr))
    if n_beats < BRS_MIN_SEQ_LEN + 1:
        return {"brs_slopes": np.empty(0), "n_sequences": 0}

    sbp_arr = np.asarray(sbp_list[:n_beats], dtype=float)
    rr_arr = rr_ms_arr[:n_beats]

    slopes, n_seqs = brs_sequence(sbp_arr, rr_arr)
    return {"brs_slopes": slopes, "n_sequences": n_seqs}


def _process_window_cardiopulm(rr_or_sbp_series: "Any",
                                co2_t: "Any", co2_v: "Any",
                                fs_beats: float,
                                fs_co2: float) -> float | None:
    """Squared coherence between a beat-to-beat series and the CO2 signal.

    Both series are resampled to a common low-rate grid (fs_beats or fs_co2,
    whichever is smaller and >= 2 * RESP_BAND_HI = 0.8 Hz).

    Returns mean squared coherence in the respiratory band, or None.
    """
    import numpy as np

    if rr_or_sbp_series.size < 4 or co2_v.size < 4:
        return None

    # Interpolate CO2 to beat-index time. Build beat times (cumulative beat
    # intervals assume fs_beats is the rate of the series -- it's already a
    # beat-to-beat series so treat each sample as equally spaced in time).
    # Use 1/mean_fs as the inter-beat time.
    n_beats = rr_or_sbp_series.size
    # Build a uniform-time version of both series for coherence.
    # Target grid: 2 Hz (>2*0.4 Hz, enough for respiratory band).
    fs_common = max(2.0, min(fs_beats, fs_co2))
    # Duration of the window
    if co2_t.size < 2:
        return None
    dur = float(co2_t[-1] - co2_t[0])
    if dur < 5.0:
        return None

    # Build a uniform time axis
    t_common = np.arange(0, dur, 1.0 / fs_common)
    # Beat-series: distribute beats uniformly over the window
    beat_times = np.linspace(0, dur, n_beats)
    beat_interp = np.interp(t_common, beat_times, rr_or_sbp_series)

    # CO2: interpolate to common grid
    co2_t_rel = co2_t - float(co2_t[0])
    co2_interp = np.interp(t_common, co2_t_rel, co2_v)

    if np.all(beat_interp == beat_interp[0]) or np.all(co2_interp == co2_interp[0]):
        return None

    return spectral_coherence(beat_interp, co2_interp, fs_common,
                              band=(RESP_BAND_LO, RESP_BAND_HI))


# ===========================================================================
# Case-level aggregation
# ===========================================================================

def compute_cross_features(
    ecg_data: "tuple[Any,Any] | None",
    ppg_data: "tuple[Any,Any] | None",
    art_data: "tuple[Any,Any] | None",
    co2_data: "tuple[Any,Any] | None",
    t_start: float | None,
    t_end: float | None,
) -> dict[str, Any]:
    """Compute all cross-waveform features for one case.

    Parameters
    ----------
    ecg_data : (times, values) or None -- SNUADC/ECG_II at ~500 Hz
    ppg_data : (times, values) or None -- SNUADC/PLETH at ~500 Hz
    art_data : (times, values) or None -- SNUADC/ART at ~500 Hz
    co2_data : (times, values) or None -- Primus/CO2 at ~62.5 Hz
    t_start, t_end : intraop window bounds (seconds)

    Returns
    -------
    dict with all SPECS keys.
    """
    import numpy as np

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["cross_waveform_available"] = 0

    # Count available channels
    n_channels = sum(d is not None for d in [ecg_data, ppg_data, art_data])
    if n_channels < 2:
        return dict(none_row)

    # -- Clip to intraop window and estimate fs --
    def _clip_and_check(data: "tuple | None"):
        if data is None:
            return None, None
        t, v = data
        if t is None or v is None or len(t) < 2:
            return None, None
        t2, v2 = _intraop_clip(t, v, t_start, t_end)
        if t2.size < 2:
            return None, None
        return t2, v2

    ecg_t, ecg_v = _clip_and_check(ecg_data)
    ppg_t, ppg_v = _clip_and_check(ppg_data)
    art_t, art_v = _clip_and_check(art_data)
    co2_t, co2_v = _clip_and_check(co2_data)

    # Re-count usable channels
    usable = sum(x is not None for x in [ecg_t, ppg_t, art_t])
    if usable < 2:
        return dict(none_row)

    # Determine window anchor from first available high-rate channel
    anchor_t = ecg_t if ecg_t is not None else (ppg_t if ppg_t is not None else art_t)
    t0 = float(anchor_t[0])
    t_fin = float(anchor_t[-1])
    window_starts = _window_starts(t0, t_fin)
    if not window_starts:
        return dict(none_row)

    # Estimate fs (from ECG or PPG or ART)
    from vitaldb_aki.features.aline_morphology import estimate_fs as _est_fs
    fs = _est_fs(ecg_t) if ecg_t is not None else (
        _est_fs(ppg_t) if ppg_t is not None else _est_fs(art_t))
    if fs < 50:
        fs = FS_HZ_SNUADC

    # Accumulators
    all_pat_ms: list[float] = []
    all_ppg_amps: list[float] = []
    all_art_pps: list[float] = []
    all_brs_slopes: list[float] = []
    total_brs_seqs: int = 0
    all_cardiopulm: list[float] = []
    all_resp_sbp: list[float] = []
    # For PAT slope: (window_midpoint_min, mean_pat_ms) pairs
    pat_trend_pts: list[tuple[float, float]] = []

    for ws in window_starts:
        we = ws + ANALYSIS_WINDOW_S

        # Slice each channel for this window
        def _wslice(t, v):
            if t is None:
                return None, None
            wt, wv = _slice_window(t, v, ws, we)
            return (wt, wv) if wt.size >= int(fs * 0.5) else (None, None)

        w_ecg_t, w_ecg_v = _wslice(ecg_t, ecg_v)
        w_ppg_t, w_ppg_v = _wslice(ppg_t, ppg_v)
        w_art_t, w_art_v = _wslice(art_t, art_v)
        w_co2_t, w_co2_v = _wslice(co2_t, co2_v)

        # --- PAT: ECG + PPG ---
        if w_ecg_t is not None and w_ppg_t is not None:
            r = _process_window_ecg_ppg(w_ecg_t, w_ecg_v, w_ppg_t, w_ppg_v, fs)
            if r["pat_ms_arr"].size > 0:
                pats = r["pat_ms_arr"].tolist()
                all_pat_ms.extend(pats)
                pat_trend_pts.append((ws / 60.0, float(np.mean(r["pat_ms_arr"]))))
            if r["ppg_amp_arr"].size > 0:
                all_ppg_amps.extend(r["ppg_amp_arr"].tolist())

        # --- Central-peripheral coupling: ART + PPG ---
        if w_art_t is not None and w_ppg_t is not None:
            r2 = _process_window_art_ppg(w_art_t, w_art_v, w_ppg_t, w_ppg_v, fs)
            if r2["art_pp_arr"].size > 0:
                all_art_pps.extend(r2["art_pp_arr"].tolist())
            if r2["ppg_amp_arr"].size > 0 and len(all_ppg_amps) == 0:
                # fallback if ECG was not available
                all_ppg_amps.extend(r2["ppg_amp_arr"].tolist())

        # --- BRS: ART + ECG ---
        if w_art_t is not None and w_ecg_t is not None:
            r3 = _process_window_brs(w_art_t, w_art_v, w_ecg_t, w_ecg_v, fs)
            if r3["brs_slopes"].size > 0:
                all_brs_slopes.extend(r3["brs_slopes"].tolist())
            total_brs_seqs += r3["n_sequences"]

        # --- Cardiopulmonary coupling: (ECG or ART) + CO2 ---
        if w_co2_t is not None:
            # Build a beat-to-beat series (RR from ECG or SBP from ART)
            beat_series: "Any | None" = None
            from scipy.signal import find_peaks as _find_peaks
            if w_ecg_t is not None and w_ecg_v is not None:
                min_d = max(1, int(fs * 60.0 / HR_MAX_BPM))
                rng_e = float(np.nanpercentile(w_ecg_v, 95) - np.nanpercentile(w_ecg_v, 5))
                prom_e = max(0.05, 0.2 * rng_e)
                rpeaks, _ = _find_peaks(w_ecg_v, distance=min_d, prominence=prom_e)
                if rpeaks.size >= 4:
                    rr = np.diff(rpeaks.astype(float)) * 1000.0 / fs
                    beat_series = rr
            elif w_art_t is not None and w_art_v is not None:
                beat_series = beat_amplitudes(w_art_v, fs, ppg=False)

            if beat_series is not None and beat_series.size >= 4:
                coh = _process_window_cardiopulm(
                    beat_series, w_co2_t, w_co2_v,
                    fs_beats=1.0,   # beat series is already 1 value per beat
                    fs_co2=FS_HZ_CO2,
                )
                if coh is not None:
                    all_cardiopulm.append(coh)

                # Also SBP vs CO2 when ART available
                if w_art_t is not None and w_art_v is not None:
                    sbp_series = beat_amplitudes(w_art_v, fs, ppg=False)
                    if sbp_series.size >= 4:
                        coh2 = _process_window_cardiopulm(
                            sbp_series, w_co2_t, w_co2_v,
                            fs_beats=1.0, fs_co2=FS_HZ_CO2,
                        )
                        if coh2 is not None:
                            all_resp_sbp.append(coh2)

    # ---- Aggregate ----
    row: dict[str, Any] = dict(none_row)

    any_feature = False

    # PAT
    if all_pat_ms:
        any_feature = True
        pat_arr = np.asarray(all_pat_ms)
        row["pat_mean_ms"] = round(float(np.mean(pat_arr)), 3)
        row["pat_sd_ms"] = round(float(np.std(pat_arr)), 3) if len(all_pat_ms) >= 2 else None
        # Slope (ms/min) via linear regression on window midpoints
        if len(pat_trend_pts) >= 2:
            xs = np.asarray([p[0] for p in pat_trend_pts])
            ys = np.asarray([p[1] for p in pat_trend_pts])
            if np.std(xs) > 0:
                row["pat_slope"] = round(float(np.polyfit(xs, ys, 1)[0]), 4)

    # Central-peripheral coupling
    if all_art_pps and all_ppg_amps:
        any_feature = True
        n_match = min(len(all_art_pps), len(all_ppg_amps))
        art_pp_arr = np.asarray(all_art_pps[:n_match])
        ppg_amp_arr = np.asarray(all_ppg_amps[:n_match])
        if n_match >= 3 and np.std(art_pp_arr) > 0 and np.std(ppg_amp_arr) > 0:
            corr = float(np.corrcoef(art_pp_arr, ppg_amp_arr)[0, 1])
            row["art_ppg_amp_corr"] = round(corr, 4)
            row["central_peripheral_decoupling"] = round(1.0 - abs(corr), 4)

    # BRS
    if all_brs_slopes:
        any_feature = True
        row["brs_mean"] = round(float(np.mean(all_brs_slopes)), 4)
        row["brs_n_sequences"] = total_brs_seqs

    # Cardiopulmonary coherence
    if all_cardiopulm:
        any_feature = True
        row["cardiopulm_coherence"] = round(float(np.mean(all_cardiopulm)), 4)
    if all_resp_sbp:
        any_feature = True
        row["resp_sbp_coupling"] = round(float(np.mean(all_resp_sbp)), 4)

    row["cross_waveform_available"] = 1 if any_feature else 0
    return row


# ===========================================================================
# Public extract() -- matches the FeatureSpec contract.
# ===========================================================================

def extract(cfg: dict[str, Any], cases_by_id: dict[str, dict],
            caseids: list[str]) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for cross-waveform features.

    Downloads SNUADC/ECG_II, SNUADC/PLETH, SNUADC/ART, Primus/CO2 per case
    (each cached under cache/tracks/). At least 2 channels must be present for
    any feature to be non-None. Honest missingness: when channels are absent
    all features are None and cross_waveform_available=0.
    """
    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["cross_waveform_available"] = 0

    out: dict[str, dict[str, Any]] = {}
    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        # Load each channel (returns (None,None) if absent).
        ecg_data = load_snuadc_waveform(cfg, cid_str, ECG_TRACK)
        ppg_data = load_snuadc_waveform(cfg, cid_str, PPG_TRACK)
        art_data = load_snuadc_waveform(cfg, cid_str, ART_TRACK)

        # CO2 (Primus/CO2) is ALSO a packed waveform (sparse timestamp format)
        # so we use load_snuadc_waveform rather than download_track.
        # Filter out zero-valued samples (sensor warm-up / off-patient artefact).
        import numpy as np
        co2_t_raw, co2_v_raw = load_snuadc_waveform(cfg, cid_str, CO2_TRACK)
        if co2_t_raw is not None and co2_t_raw.size >= 4:
            # Keep only physiologic non-zero CO2 (etCO2 > 0.5 % or > 5 mmHg fraction)
            co2_good = co2_v_raw > 0.5
            if co2_good.sum() >= 4:
                co2_data: "tuple | None" = (co2_t_raw[co2_good], co2_v_raw[co2_good])
            else:
                co2_data = None
        else:
            co2_data = None

        out[cid_str] = compute_cross_features(
            ecg_data, ppg_data, art_data, co2_data, t_start, t_end
        )

    return out
