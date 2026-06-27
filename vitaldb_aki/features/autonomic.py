"""autonomic.py -- Autonomic Nervous System Reserve biomarker family (UNMINED axis).

NORTH-STAR MECHANISM
--------------------
The autonomic nervous system continuously regulates organ perfusion: baroreflex
loops trim heart rate and vascular tone beat-to-beat to defend pressure AND flow.
When that reserve is exhausted or collapsing -- low heart-rate variability (HRV),
blunted baroreflex sensitivity (BRS) -- the patient loses the closed-loop control
that keeps kidneys (and every other organ) perfused through the insults of
surgery.  Autonomic failure therefore plausibly sits UPSTREAM of AKI and is, to
date, an UNMINED axis in the VitalDB-AKI feature set (the existing PFDS / hemo
families measure the pressure-flow *consequences*, not the *controller*).

This module operationalises that axis in TWO tiers:

  TIER A -- Numeric / coarse HRV surrogate  (DEFAULT, fast)
    Derived from the *numeric* HR track (Solar8000/HR), which updates only every
    ~1-2 s.  This is NOT true beat-to-beat R-R interval data: the monitor has
    already averaged/smoothed the cardiac rhythm into a once-per-second HR number.
    We convert each HR sample to an inter-beat-interval proxy (RR_ms = 60000/HR)
    and compute coarse SDNN / RMSSD / CV statistics over it.  Every feature name
    carries the suffix ``_coarse`` and every docstring states the limitation:
    these are *surrogates* that track gross autonomic variability, not validated
    HRV indices.  They are cheap, need no waveform download, and are computed on
    every case.

  TIER B -- Raw / beat-to-beat HRV + baroreflex  (DEFERRED, default OFF)
    True HRV (RMSSD/SDNN/LF-HF from R-peaks of the 500 Hz SNUADC/ECG_II waveform)
    and baroreflex sensitivity (sequence method on ART systolic pressure beats vs
    the following R-R interval).  These require the heavy 500 Hz streaming pass and
    are gated behind ``cfg["features"]["autonomic_raw_ecg"]`` (default False).  In
    the default build these features are ALWAYS None and NO ECG/ART track is
    downloaded -- the default path must stay fast.  The R-peak detector and the
    BRS sequence-method routine are present only as clearly-commented stubs.

LEAKAGE (Sec 11)
----------------
All features are timing="intraop".  The prediction cutoff is opend.  No sample at
t > opend is ever used: _intraop_window + _clip_to_window enforce the window
[t_start, opend].  audit_specs(SPECS) re-checks at import.

MISSINGNESS
-----------
If the HR track is absent or unusable (< 60 in-window physiologic samples),
auto_available = 0 and ALL other features are None (not 0).  HR is range-gated to
[20, 220] bpm before use.

Protocol reference: §7-novel (UNMINED autonomic axis), mirrors pfds.py structure.
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range constants (binding; HR artifact gate)
# ---------------------------------------------------------------------------
HR_MIN: float = 20.0     # bpm -- artifact gate (below = asystole/dropout)
HR_MAX: float = 220.0    # bpm -- artifact gate (above = noise/double-count)

# Minimum usable HR samples in window for the coarse tier to be defined.
MIN_HR_SAMPLES: int = 60

# Track priorities (binding)
HR_TRACK_CANDIDATES: list[str] = [
    "Solar8000/HR",
    "Solar8000/PLETH_HR",
]

# Tier-B (raw) tracks -- only ever touched when autonomic_raw_ecg is True.
ECG_TRACK: str = "SNUADC/ECG_II"   # 500 Hz waveform -- true R-peak HRV
ART_TRACK: str = "SNUADC/ART"      # 500 Hz arterial waveform -- BRS systolic beats

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11)
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability (FIRST spec, per contract) ---------------------------
    FeatureSpec(
        "auto_available", "comprehensive", "intraop",
        "1 if numeric HR track usable for coarse-HRV computation "
        "(>=60 in-window physiologic samples), else 0",
    ),
    # ---- TIER A: numeric / coarse HRV surrogates ---------------------------
    FeatureSpec(
        "auto_hr_sdnn_coarse", "comprehensive", "intraop",
        "COARSE SDNN surrogate: SD of the HR-derived inter-beat-interval proxy "
        "(RR_ms = 60000/HR per numeric HR sample) over the in-window samples. "
        "NOT true beat-to-beat SDNN -- the numeric HR track is monitor-averaged "
        "at ~1-2 s cadence; this tracks gross autonomic variability only",
    ),
    FeatureSpec(
        "auto_hr_rmssd_coarse", "comprehensive", "intraop",
        "COARSE RMSSD surrogate: root-mean-square of successive differences of "
        "the RR_ms proxy (RR_ms = 60000/HR). NOT true vagally-mediated RMSSD -- "
        "computed from monitor-averaged HR, so it reflects short-term HR "
        "fluctuation rather than respiratory sinus arrhythmia",
    ),
    FeatureSpec(
        "auto_hr_cv_coarse", "comprehensive", "intraop",
        "COARSE coefficient of variation of the numeric HR (SD/mean over in-window "
        "samples); a unit-free gross variability index. Surrogate, not a validated "
        "HRV measure",
    ),
    # ---- TIER B: raw / beat-to-beat HRV + baroreflex (DEFERRED, default None)
    FeatureSpec(
        "auto_hrv_rmssd", "pk", "intraop",
        "TRUE RMSSD (ms) from R-peaks of the 500 Hz SNUADC/ECG_II waveform. "
        "DEFERRED behind cfg.features.autonomic_raw_ecg (needs the streaming "
        "pass); None in the default build",
    ),
    FeatureSpec(
        "auto_hrv_sdnn", "pk", "intraop",
        "TRUE SDNN (ms) from R-peaks of the 500 Hz SNUADC/ECG_II waveform. "
        "DEFERRED behind cfg.features.autonomic_raw_ecg; None in the default build",
    ),
    FeatureSpec(
        "auto_hrv_lfhf", "pk", "intraop",
        "TRUE LF/HF ratio (sympatho-vagal balance) from the R-R tachogram of the "
        "500 Hz SNUADC/ECG_II waveform. DEFERRED behind cfg.features."
        "autonomic_raw_ecg; None in the default build",
    ),
    FeatureSpec(
        "auto_brs_seq", "pk", "intraop",
        "Baroreflex sensitivity (ms/mmHg) via the sequence method: spontaneous "
        "concordant ramps of ART systolic pressure (SNUADC/ART beats) and the "
        "following R-R interval; mean of valid-sequence slopes. DEFERRED behind "
        "cfg.features.autonomic_raw_ecg (needs ECG + ART 500 Hz); None by default",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Window / clipping helper (copied verbatim from pfds.py -- binding contract)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None."""
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


def _clip_to_window(
    samples: list[tuple[float, float]],
    t_start: float | None,
    t_end: float | None,
) -> list[tuple[float, float]]:
    """Return only samples in [t_start, t_end].  t_end is the leakage cutoff."""
    out = []
    for t, v in samples:
        if t_start is not None and t < t_start:
            continue
        if t_end is not None and t > t_end:
            continue
        out.append((t, v))
    return out


def _filter_physiologic(
    samples: list[tuple[float, float]],
    vmin: float,
    vmax: float,
) -> list[tuple[float, float]]:
    """Drop samples outside [vmin, vmax] (artifact rejection)."""
    return [(t, v) for t, v in samples if vmin <= v <= vmax]


# ===========================================================================
# TIER A pure helpers (no I/O; unit-tested in tests/test_autonomic.py)
# ===========================================================================

def _hr_to_rr_ms(series: list[float]) -> list[float]:
    """Convert a list of heart-rate values (bpm) to an inter-beat-interval proxy
    in milliseconds, RR_ms = 60000 / HR, one RR per HR sample.

    This is the COARSE surrogate at the heart of Tier A: the numeric HR track is
    already a monitor-averaged number (~1-2 s cadence), so each derived RR_ms is a
    *proxy* for the mean beat interval over that monitor epoch, not an actual
    measured R-R interval.

    HR values <= 0 are skipped (cannot invert).  Returns [] for empty input.
    """
    out: list[float] = []
    for hr in series:
        if hr is None:
            continue
        if hr <= 0:
            continue
        out.append(60000.0 / hr)
    return out


def _sdnn(rr: list[float]) -> float | None:
    """Standard deviation of the RR_ms proxy series (population SD, ddof=0).

    Coarse SDNN surrogate.  Returns None for < 2 values (SD undefined).
    """
    n = len(rr)
    if n < 2:
        return None
    mean = sum(rr) / n
    var = sum((x - mean) ** 2 for x in rr) / n
    return math.sqrt(var)


def _rmssd(rr: list[float]) -> float | None:
    """Root-mean-square of successive differences of the RR_ms proxy series.

    Coarse RMSSD surrogate: sqrt( mean( (rr[i+1] - rr[i])^2 ) ).
    Returns None for < 2 values (no successive difference exists).
    """
    n = len(rr)
    if n < 2:
        return None
    sq = 0.0
    for i in range(n - 1):
        d = rr[i + 1] - rr[i]
        sq += d * d
    return math.sqrt(sq / (n - 1))


def _cv(series: list[float]) -> float | None:
    """Coefficient of variation (population SD / mean) of a series.

    Used on the raw HR (bpm) series as a unit-free gross variability index.
    Returns None for < 2 values, or when the mean is <= 0 (CV undefined).
    """
    n = len(series)
    if n < 2:
        return None
    mean = sum(series) / n
    if mean <= 0:
        return None
    var = sum((x - mean) ** 2 for x in series) / n
    return math.sqrt(var) / mean


# ===========================================================================
# TIER B (raw / beat-to-beat) -- DEFERRED stubs.  These are NEVER executed in
# the default build: extract() only reaches them when cfg.features.
# autonomic_raw_ecg is True, and even then they return None / raise until the
# streaming pass implements them.  No 500 Hz track is downloaded by default.
# ===========================================================================

def _detect_r_peaks(
    ecg: list[tuple[float, float]],
    fs_hz: float = 500.0,
) -> list[float]:
    """[STUB -- DEFERRED] Detect R-peak times (seconds) in a 500 Hz ECG waveform.

    INTENDED ALGORITHM (Pan-Tompkins-style, to be implemented in the streaming
    pass, likely with numpy/scipy):
      1. Band-pass filter the raw ECG (~5-15 Hz) to isolate the QRS energy.
      2. Differentiate, square, then moving-window integrate to build a feature
         signal whose peaks coincide with QRS complexes.
      3. Adaptive dual-threshold peak picking with a refractory period (~200 ms)
         to reject T-waves and noise; search-back for missed beats.
      4. Return the ordered list of R-peak timestamps (s); successive differences
         are the R-R intervals (s) -> *1000 for ms used by HRV indices.

    Not implemented here: Tier B is gated off by default and computed only in the
    dedicated 500 Hz streaming pass.
    """
    raise NotImplementedError(
        "raw R-peak detection is deferred to the autonomic_raw_ecg streaming pass"
    )


def _hrv_from_rr_ms(rr_ms: list[float]) -> dict[str, float | None]:
    """[STUB -- DEFERRED] True HRV indices from a beat-to-beat R-R series (ms).

    INTENDED OUTPUT: {"rmssd": .., "sdnn": .., "lfhf": ..}
      * rmssd / sdnn: time-domain, as in Tier A but on REAL R-R intervals.
      * lfhf: frequency-domain -- resample the R-R tachogram to an even grid,
        estimate the power spectrum (Welch/Lomb-Scargle), integrate LF
        (0.04-0.15 Hz) and HF (0.15-0.4 Hz) bands, return LF/HF.

    Returns all-None until implemented (default build never calls this).
    """
    return {"rmssd": None, "sdnn": None, "lfhf": None}


def _brs_sequence_method(
    sbp_beats: list[tuple[float, float]],
    rr_beats: list[tuple[float, float]],
) -> float | None:
    """[STUB -- DEFERRED] Baroreflex sensitivity (ms/mmHg) via the sequence method.

    INTENDED ALGORITHM:
      Inputs are per-beat systolic blood pressure (from SNUADC/ART beat detection)
      and the *following* R-R interval (from ECG R-peaks), beat-aligned.
      1. Scan for SEQUENCES of >=3 consecutive beats where SBP and the following
         RR change in the SAME direction (concordant up-up-up or down-down-down),
         with minimum changes (e.g. >=1 mmHg SBP, >=4 ms RR).
      2. For each valid sequence, regress RR (ms) on SBP (mmHg); keep slopes with
         r >= ~0.85.
      3. Return the mean of valid-sequence slopes (ms/mmHg) -- the spontaneous BRS.

    Returns None until implemented (default build never calls this).
    """
    return None


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for the autonomic-reserve family.

    DEFAULT (fast) path -- Tier A only:
      * Download the numeric HR track (Solar8000/HR -> Solar8000/PLETH_HR).
      * Clip to [t_start, opend], range-gate to [20, 220] bpm.
      * If < 60 usable samples: auto_available = 0, all others None.
      * Else: auto_available = 1, compute coarse SDNN/RMSSD/CV.
      * Tier-B features (auto_hrv_*, auto_brs_seq) stay None and NO 500 Hz track
        is downloaded.

    Tier-B (raw) path is attempted ONLY when
      cfg["features"]["autonomic_raw_ecg"] is True.  Even then the stub helpers
      currently return None (deferred to the streaming pass), but this is where
      the ECG/ART downloads + R-peak/BRS computation will wire in.

    Missing HR track => auto_available = 0, every other feature None (not 0).
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float  # noqa: F401 (parity w/ pfds; future /cases use)

    raw_enabled = bool(cfg.get("features", {}).get("autonomic_raw_ecg", False))

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["auto_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        # ---- HR track (Tier A) ----------------------------------------------
        _hr_tname, raw_hr = first_available(cfg, cid_str, HR_TRACK_CANDIDATES)
        if not raw_hr:
            out[cid_str] = dict(none_row)   # missing => auto_available=0, rest None
            continue

        hr_samples = _clip_to_window(raw_hr, t_start, t_end)
        hr_samples = _filter_physiologic(hr_samples, HR_MIN, HR_MAX)
        if len(hr_samples) < MIN_HR_SAMPLES:
            out[cid_str] = dict(none_row)   # not enough usable HR => unavailable
            continue

        row: dict[str, Any] = dict(none_row)
        row["auto_available"] = 1

        hr_values = [v for _, v in hr_samples]
        rr_ms = _hr_to_rr_ms(hr_values)

        sdnn = _sdnn(rr_ms)
        rmssd = _rmssd(rr_ms)
        cv = _cv(hr_values)
        row["auto_hr_sdnn_coarse"] = round(sdnn, 6) if sdnn is not None else None
        row["auto_hr_rmssd_coarse"] = round(rmssd, 6) if rmssd is not None else None
        row["auto_hr_cv_coarse"] = round(cv, 6) if cv is not None else None

        # ---- TIER B: raw / beat-to-beat (DEFERRED, default OFF) --------------
        # The default build never enters this branch, so no 500 Hz ECG/ART track
        # is downloaded and the heavy path costs nothing.
        if raw_enabled:
            # Download the 500 Hz ECG + ART waveforms (heavy; opt-in only).
            raw_ecg = download_track(cfg, cid_str, ECG_TRACK)
            raw_art = download_track(cfg, cid_str, ART_TRACK)
            if raw_ecg:
                ecg = _clip_to_window(raw_ecg, t_start, t_end)
                # R-peaks -> R-R tachogram -> true HRV (stubs return None today).
                try:
                    r_peaks = _detect_r_peaks(ecg)
                    rr_true_ms = [
                        (r_peaks[i + 1] - r_peaks[i]) * 1000.0
                        for i in range(len(r_peaks) - 1)
                    ]
                    hrv = _hrv_from_rr_ms(rr_true_ms)
                    row["auto_hrv_rmssd"] = hrv.get("rmssd")
                    row["auto_hrv_sdnn"] = hrv.get("sdnn")
                    row["auto_hrv_lfhf"] = hrv.get("lfhf")
                except NotImplementedError:
                    pass  # deferred to the streaming pass; leave Tier-B None
                if raw_art:
                    art = _clip_to_window(raw_art, t_start, t_end)
                    # Beat detection for SBP + RR alignment would feed the sequence
                    # method; both stubs deferred, so this stays None for now.
                    sbp_beats: list[tuple[float, float]] = []  # from ART beats
                    rr_beats: list[tuple[float, float]] = []   # from ECG R-peaks
                    _ = art  # placeholder until beat detection lands
                    row["auto_brs_seq"] = _brs_sequence_method(sbp_beats, rr_beats)

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.autonomic
# ===========================================================================
if __name__ == "__main__":
    import csv
    import os
    import sys

    sys.path.insert(
        0,
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )
    from common.config import load_yaml
    from vitaldb_aki.data.client import fetch_cases

    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
    )
    cfg = load_yaml(cfg_path)

    cohort_path = os.path.join(cfg["data"]["cache_dir"], "cohort.csv")
    cohort_ids: list[str] = []
    with open(cohort_path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            cohort_ids.append(str(r["caseid"]))
            if len(cohort_ids) >= 12:
                break

    print(f"Autonomic validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [
        "auto_available",
        "auto_hr_sdnn_coarse",
        "auto_hr_rmssd_coarse",
        "auto_hr_cv_coarse",
        "auto_hrv_rmssd",
        "auto_hrv_sdnn",
        "auto_hrv_lfhf",
        "auto_brs_seq",
    ]
    print("\nPer-case autonomic summary (Tier B None unless autonomic_raw_ecg):")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
