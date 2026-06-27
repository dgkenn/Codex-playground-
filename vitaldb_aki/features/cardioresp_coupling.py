"""cardioresp_coupling.py -- the cardio-respiratory-autonomic triad (§7F-novel).

THESIS: healthy autonomic control jointly couples three signals --
**heart rate (HR)**, **respiration (RR)** and **mean arterial pressure (MAP)**.
Two physiologic loops drive that coupling:

  * Respiratory Sinus Arrhythmia (RSA)  -- HR speeds up on inspiration and
    slows on expiration, i.e. HR co-oscillates with RR.  Vagal (parasympathetic)
    tone sets its amplitude.
  * Baroreflex                          -- a fall in MAP reflexively raises HR
    (and vice versa), so over short windows HR moves *opposite* to MAP under an
    intact baroreflex.

When these loops are intact the three signals move in a coordinated, mutually
constrained way.  Their **de-synchronization** -- HR no longer tracking RR, HR no
longer counter-regulating MAP -- is a fingerprint of **autonomic decompensation**
and predicts poor perioperative outcome (including AKI).

This is a **3-way coupling** module.  It is deliberately distinct from any
single-signal autonomic module (HRV, MAP variability, etc.): every feature here
requires at least two of the three signals *simultaneously* and the headline
feature requires all three.  The novelty is the joint structure, not the marginals.

WHY NUMERIC TRACKS (and the RSA caveat)
---------------------------------------
On the default path this module reads only the slow NUMERIC monitor tracks
(Solar8000/VENT_RR, Solar8000/ART_MBP, Solar8000/HR, ...) at ~0.5 Hz.  That is
plenty for baroreflex-band and respiratory-band trend coupling, but it is far
below beat-to-beat resolution.  Consequently `cardioresp_rsa_coarse` is an
explicit COARSE numeric SURROGATE of RSA (variance of HR that co-oscillates with
RR on the numeric grid), NOT true beat-to-beat RSA.  The genuine beat-to-beat
RSA (`cardioresp_rsa_beat`) is DEFERRED behind a config flag because it would
require downloading the 500 Hz ECG (~57 MB/case); it is a documented stub on the
default path and never downloads the waveform unless explicitly enabled.

JOINT-AVAILABILITY CAVEAT
-------------------------
HR and MAP are near-universal in the cohort.  RR comes from the ventilator
(Solar8000/VENT_RR) or capnometer (RR_CO2); MOST ventilated cases have it, but
spontaneously-breathing / MAC cases may lack a numeric RR.  Features that need RR
(`cardioresp_hr_rr_corr`, `cardioresp_triple_concordance`, `cardioresp_rsa_coarse`)
are therefore None whenever RR is absent -- honest missingness, never imputed 0.

LEAKAGE (§11)
-------------
All features are timing="intraop"; the window is [t_start, opend] and no sample
at t > opend is ever used.  audit_specs() enforces this at import.

MISSINGNESS
-----------
If the required signals (HR & MAP) are not jointly usable, cardioresp_available=0
and every other feature is None (NOT 0).  Individual features are None when their
specific signal (e.g. RR) is absent or there are < MIN_JOINT_POINTS jointly-valid
samples.

TRACK PRIORITIES (binding; first_available)
  HR :  Solar8000/HR            -> Solar8000/PLETH_HR             gate 20-220 bpm
  RR :  Solar8000/VENT_RR       -> Solar8000/RR_CO2 -> Primus/RR_CO2  gate 4-60 /min
  MAP:  Solar8000/ART_MBP       -> Solar8000/NIBP_MBP -> EV1000/ART_MBP gate 20-200 mmHg

CONSTANTS (all binding; pre-registered)
  ALIGN_DT_S         = 5.0   s   -- common resampling grid
  MAX_STALE_S        = 10.0  s   -- last-value-hold staleness cap (jointly-valid = all fresh)
  MIN_JOINT_POINTS   = 30        -- minimum jointly-valid points for any correlation
  CONCORDANCE_WIN_S  = 60.0  s   -- sliding window for triple-concordance / RSA-coarse
  CONCORDANCE_STEP_S = 30.0  s   -- step between sliding windows
  MIN_WIN_POINTS     = 4         -- minimum aligned points inside a window to score it

Protocol reference: §7F-novel (raw-signal coupling), §7C (hemodynamic axis).
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range gates (binding; artifact rejection).
# ---------------------------------------------------------------------------
HR_MIN: float = 20.0      # bpm
HR_MAX: float = 220.0     # bpm
RR_MIN: float = 4.0       # breaths/min
RR_MAX: float = 60.0      # breaths/min
MAP_MIN: float = 20.0     # mmHg
MAP_MAX: float = 200.0    # mmHg

# ---------------------------------------------------------------------------
# Alignment / windowing constants (binding; pre-registered).
# ---------------------------------------------------------------------------
ALIGN_DT_S: float = 5.0          # common resampling grid step (s)
MAX_STALE_S: float = 10.0        # last-value-hold staleness cap (s)
MIN_JOINT_POINTS: int = 30       # min jointly-valid points for a correlation
CONCORDANCE_WIN_S: float = 60.0  # sliding window length (s)
CONCORDANCE_STEP_S: float = 30.0 # sliding window step (s)
MIN_WIN_POINTS: int = 4          # min aligned points to score a window

# ---------------------------------------------------------------------------
# Track priorities (binding; first_available -- prefer leftmost).
# ---------------------------------------------------------------------------
HR_TRACK_CANDIDATES: list[str] = [
    "Solar8000/HR",
    "Solar8000/PLETH_HR",
]
RR_TRACK_CANDIDATES: list[str] = [
    "Solar8000/VENT_RR",
    "Solar8000/RR_CO2",
    "Primus/RR_CO2",
]
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]

# Config flag gating the deferred beat-to-beat RSA (500 Hz ECG download).
RAW_ECG_FLAG: str = "cardioresp_raw_ecg"

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11).
# First spec is the availability flag (cardioresp_available).
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability -------------------------------------------------------
    FeatureSpec(
        "cardioresp_available", "comprehensive", "intraop",
        "1 if HR and MAP are jointly usable (>=MIN_JOINT_POINTS aligned points) "
        "for cardio-respiratory coupling, else 0",
    ),
    # ---- cardiovascular / baroreflex coupling (HR x MAP) -------------------
    FeatureSpec(
        "cardioresp_hr_map_corr", "comprehensive", "intraop",
        "Pearson corr(HR, MAP) over jointly-valid aligned points -- baroreflex "
        "coupling proxy; expect NEGATIVE under an intact baroreflex (HR rises as "
        "BP falls); near 0 = blunted regulation (§7F)",
    ),
    # ---- cardio-respiratory coupling (HR x RR) -----------------------------
    FeatureSpec(
        "cardioresp_hr_rr_corr", "comprehensive", "intraop",
        "Pearson corr(HR, RR) over jointly-valid aligned points -- coarse "
        "cardio-respiratory coupling; None if RR (ventilator/capnometer) absent (§7F)",
    ),
    # ---- 3-way coordinated control (HR x RR x MAP) -------------------------
    FeatureSpec(
        "cardioresp_triple_concordance", "comprehensive", "intraop",
        "Fraction of sliding 60 s windows whose HR/RR/MAP slope SIGNS are "
        "mutually consistent with coordinated autonomic control (see "
        "_concordant_signs rule); 1 = always coordinated, 0 = always "
        "de-synchronized; None if any of the 3 signals absent (§7F)",
    ),
    # ---- coarse RSA surrogate (HR variance co-oscillating with RR) ---------
    FeatureSpec(
        "cardioresp_rsa_coarse", "comprehensive", "intraop",
        "COARSE numeric RSA surrogate: mean over short windows of "
        "|corr(detrended HR, detrended RR)| -- fraction of HR variability that "
        "co-oscillates with respiration on the numeric grid; NOT beat-to-beat "
        "RSA; None if RR absent (§7F)",
    ),
    # ---- TRUE beat-to-beat RSA (DEFERRED behind cfg flag; 500 Hz ECG) ------
    FeatureSpec(
        "cardioresp_rsa_beat", "pk", "intraop",
        "TRUE beat-to-beat RSA (HF-band RR-interval power / peak-valley) from "
        "500 Hz ECG; DEFERRED behind cfg.features.cardioresp_raw_ecg (default "
        "off); never downloads the raw ECG on the default path; stub returns "
        "None unless enabled (§7F)",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing

# Which features become None when RR is absent (HR & MAP alone cannot compute
# them).  Documented here so the missingness contract is auditable.
REQUIRES_RR: set[str] = {
    "cardioresp_hr_rr_corr",
    "cardioresp_triple_concordance",
    "cardioresp_rsa_coarse",
}


# ===========================================================================
# Low-level helpers (pure; no I/O; unit-testable on synthetic series)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds._intraop_window (binding contract).  t_end is the
    leakage cutoff (== opend); no sample at t > t_end may ever be used.
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


def _filter_physiologic(
    samples: list[tuple[float, float]],
    vmin: float,
    vmax: float,
) -> list[tuple[float, float]]:
    """Drop samples outside [vmin, vmax] (artifact rejection)."""
    return [(t, v) for t, v in samples if vmin <= v <= vmax]


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


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation of two equal-length lists.  None if degenerate.

    Returns None when fewer than 3 paired points or either series has zero
    variance (correlation undefined).  Result is clamped to [-1, 1] to absorb
    floating-point overshoot.
    """
    n = min(len(xs), len(ys))
    if n < 3:
        return None
    xs = xs[:n]
    ys = ys[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    r = sxy / math.sqrt(sxx * syy)
    if r > 1.0:
        r = 1.0
    elif r < -1.0:
        r = -1.0
    return r


def _detrend(series: list[float]) -> list[float]:
    """Remove the least-squares linear trend from a series (index as x).

    Returns the residuals (series minus best-fit line over equally-spaced
    indices).  For series of length < 2 returns a copy (nothing to detrend).
    If the indices have zero variance (length 1) the mean is removed.  Detrending
    isolates the oscillatory (respiratory-band) component from the slow drift,
    so that |corr(detrended HR, detrended RR)| measures co-oscillation rather
    than shared slow trend.
    """
    n = len(series)
    if n < 2:
        return list(series)
    xs = list(range(n))
    mx = (n - 1) / 2.0
    my = sum(series) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0.0:
        return [v - my for v in series]
    sxy = sum((xs[i] - mx) * (series[i] - my) for i in range(n))
    slope = sxy / sxx
    intercept = my - slope * mx
    return [series[i] - (slope * xs[i] + intercept) for i in range(n)]


def _slope_sign(series: list[float]) -> int:
    """Sign (+1/-1/0) of the least-squares slope of a series over its indices.

    0 is returned for a flat / too-short series or an exactly-zero slope.
    """
    n = len(series)
    if n < 2:
        return 0
    xs = list(range(n))
    mx = (n - 1) / 2.0
    my = sum(series) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0.0:
        return 0
    sxy = sum((xs[i] - mx) * (series[i] - my) for i in range(n))
    slope = sxy / sxx
    if slope > 0:
        return 1
    if slope < 0:
        return -1
    return 0


def _concordant_signs(hr_sign: int, rr_sign: int, map_sign: int) -> bool:
    """Are the three slope signs consistent with coordinated autonomic control?

    RULE (documented + binding).  A window is "concordant" when ALL THREE signs
    are non-zero AND the pattern matches one of the two physiologically coherent
    co-ordination modes:

      (A) Respiratory-drive mode  -- HR and RR move together (same sign): RSA /
          shared respiratory drive is intact, so HR tracks RR.  MAP may move
          either way (ventilation / surgical stimulus drives all three), so MAP
          sign is unconstrained in this mode.  Condition: hr_sign == rr_sign.

      (B) Baroreflex mode         -- HR and MAP move OPPOSITELY (intact
          baroreflex counter-regulation: HR up as BP down).  Condition:
          hr_sign == -map_sign.

    A window is concordant if (A) OR (B) holds.  This deliberately rewards EITHER
    coupling loop being intact; only when HR tracks neither RR nor (inversely)
    MAP is the window scored discordant -- the de-synchronization signature.

    Any zero (flat) sign makes the window non-scorable -> returns False
    (callers exclude flat windows from the denominator separately if desired;
    here we treat flat as not-concordant, see _trend_concordance).
    """
    if hr_sign == 0 or rr_sign == 0 or map_sign == 0:
        return False
    mode_a = (hr_sign == rr_sign)            # HR tracks RR (respiratory drive)
    mode_b = (hr_sign == -map_sign)          # HR counter-regulates MAP (baroreflex)
    return mode_a or mode_b


def _align_grid(
    signals_dict: dict[str, list[tuple[float, float]]],
    t_start: float,
    t_end: float,
    dt: float = ALIGN_DT_S,
    max_stale: float = MAX_STALE_S,
) -> tuple[list[float], dict[str, list[float | None]]]:
    """Resample multiple (t, v) signals onto a common uniform grid (PURE).

    Walks a grid t_start, t_start+dt, ... <= t_end and, for each signal, holds
    the LAST observed value forward.  A grid cell is "fresh" for a signal if the
    most recent sample at or before the grid time is within `max_stale` seconds;
    otherwise that cell's value is None (the signal has gone stale -- we do not
    hold an arbitrarily old value across a long gap).

    A grid time is JOINTLY-VALID for a set of signals when ALL of them are fresh
    there.  This function returns per-signal grids (with None for stale cells);
    callers extract the jointly-valid subset via _joint_valid().

    Parameters
    ----------
    signals_dict : {name: [(t, v), ...]}  -- each list may be unsorted; sorted here.
    t_start, t_end : grid bounds (s).  t_end is the leakage cutoff (no grid time
                     exceeds t_end).
    dt        : grid step (s).
    max_stale : last-value-hold staleness cap (s).

    Returns
    -------
    (grid_times, aligned) where
        grid_times : list[float]                 -- the uniform grid (<= t_end)
        aligned    : {name: list[float|None]}    -- same length as grid_times
    """
    # Degenerate window -> empty grid.
    if t_end < t_start or dt <= 0.0:
        return [], {name: [] for name in signals_dict}

    # Build the uniform grid (inclusive of t_end up to floating tolerance).
    grid_times: list[float] = []
    n_steps = int((t_end - t_start) / dt)
    for k in range(n_steps + 1):
        gt = t_start + k * dt
        if gt > t_end + 1e-9:
            break
        grid_times.append(gt)

    # Pre-sort each signal once.
    sorted_signals: dict[str, list[tuple[float, float]]] = {
        name: sorted(s, key=lambda x: x[0]) for name, s in signals_dict.items()
    }

    def _last_fresh(sorted_s: list[tuple[float, float]], t: float) -> float | None:
        """Last value at or before t, only if within max_stale; else None."""
        lo, hi = 0, len(sorted_s)
        while lo < hi:
            mid = (lo + hi) // 2
            if sorted_s[mid][0] <= t:
                lo = mid + 1
            else:
                hi = mid
        idx = lo - 1
        if idx < 0:
            return None
        st, sv = sorted_s[idx]
        if t - st > max_stale:
            return None
        return sv

    aligned: dict[str, list[float | None]] = {}
    for name, sorted_s in sorted_signals.items():
        col: list[float | None] = []
        for gt in grid_times:
            col.append(_last_fresh(sorted_s, gt))
        aligned[name] = col

    return grid_times, aligned


def _joint_valid(
    aligned: dict[str, list[float | None]],
    names: list[str],
) -> tuple[list[int], dict[str, list[float]]]:
    """Indices where ALL of `names` are non-None, plus the per-name value lists.

    Returns (idxs, {name: [values at those idxs]}).  Pure helper over the output
    of _align_grid.
    """
    if not names:
        return [], {}
    cols = [aligned.get(n, []) for n in names]
    length = min((len(c) for c in cols), default=0)
    idxs: list[int] = []
    for i in range(length):
        if all(aligned[n][i] is not None for n in names):
            idxs.append(i)
    out: dict[str, list[float]] = {}
    for n in names:
        out[n] = [aligned[n][i] for i in idxs]  # type: ignore[misc]
    return idxs, out


def _window_index_bounds(
    grid_times: list[float],
    win_s: float = CONCORDANCE_WIN_S,
    step_s: float = CONCORDANCE_STEP_S,
) -> list[tuple[int, int]]:
    """Sliding-window (start_idx, end_idx_exclusive) pairs over a uniform grid.

    Windows of `win_s` seconds, advanced by `step_s` seconds, expressed as index
    ranges into grid_times.  Pure (operates on times only).
    """
    if not grid_times:
        return []
    dt = ALIGN_DT_S
    if len(grid_times) >= 2:
        dt = grid_times[1] - grid_times[0]
    if dt <= 0:
        dt = ALIGN_DT_S
    win_n = max(1, int(round(win_s / dt)))
    step_n = max(1, int(round(step_s / dt)))
    n = len(grid_times)
    bounds: list[tuple[int, int]] = []
    start = 0
    while start < n:
        end = min(start + win_n, n)
        bounds.append((start, end))
        if end >= n:
            break
        start += step_n
    return bounds


def _windowed_metric(
    aligned: dict[str, list[float | None]],
    grid_times: list[float],
    names: list[str],
    metric,
    win_s: float = CONCORDANCE_WIN_S,
    step_s: float = CONCORDANCE_STEP_S,
    min_points: int = MIN_WIN_POINTS,
) -> list[Any]:
    """Apply `metric` to each sliding window's jointly-valid sub-series (PURE).

    For each sliding window, gather the indices in that window where ALL `names`
    are non-None; if there are >= `min_points`, call
    metric({name: [values], ...}) and collect its result (skipping None results).

    Returns the list of per-window metric results (only those that were scorable).
    """
    bounds = _window_index_bounds(grid_times, win_s, step_s)
    results: list[Any] = []
    for (s, e) in bounds:
        # jointly-valid indices within [s, e)
        idxs = [
            i for i in range(s, e)
            if all(aligned[n][i] is not None for n in names)
        ]
        if len(idxs) < min_points:
            continue
        sub = {n: [aligned[n][i] for i in idxs] for n in names}  # type: ignore[misc]
        res = metric(sub)
        if res is not None:
            results.append(res)
    return results


def _trend_concordance(windows: list[tuple[int, int, int]]) -> float | None:
    """Fraction of windows whose (hr_sign, rr_sign, map_sign) triple is concordant.

    Parameters
    ----------
    windows : list of (hr_sign, rr_sign, map_sign) integer-sign triples, one per
              scorable sliding window.

    Returns the fraction concordant (per _concordant_signs) over the windows that
    are SCORABLE (all three signs non-zero).  Windows where any signal is flat
    are excluded from BOTH numerator and denominator (they carry no directional
    information).  Returns None if no window is scorable.
    """
    scorable = [w for w in windows if w[0] != 0 and w[1] != 0 and w[2] != 0]
    if not scorable:
        return None
    n_conc = sum(1 for (h, r, m) in scorable if _concordant_signs(h, r, m))
    return round(n_conc / len(scorable), 6)


# ===========================================================================
# Case-level metric helpers (pure; build on the primitives above)
# ===========================================================================

def hr_map_corr(
    aligned: dict[str, list[float | None]],
    min_points: int = MIN_JOINT_POINTS,
) -> float | None:
    """Pearson corr(HR, MAP) over jointly-valid aligned points.  None if < min."""
    _idxs, vals = _joint_valid(aligned, ["HR", "MAP"])
    if len(_idxs) < min_points:
        return None
    r = _pearson(vals["HR"], vals["MAP"])
    return round(r, 6) if r is not None else None


def hr_rr_corr(
    aligned: dict[str, list[float | None]],
    min_points: int = MIN_JOINT_POINTS,
) -> float | None:
    """Pearson corr(HR, RR) over jointly-valid aligned points.  None if < min."""
    _idxs, vals = _joint_valid(aligned, ["HR", "RR"])
    if len(_idxs) < min_points:
        return None
    r = _pearson(vals["HR"], vals["RR"])
    return round(r, 6) if r is not None else None


def triple_concordance(
    aligned: dict[str, list[float | None]],
    grid_times: list[float],
    win_s: float = CONCORDANCE_WIN_S,
    step_s: float = CONCORDANCE_STEP_S,
    min_points: int = MIN_WIN_POINTS,
) -> float | None:
    """3-way slope-sign concordance over sliding windows (needs HR, RR, MAP)."""
    names = ["HR", "RR", "MAP"]
    bounds = _window_index_bounds(grid_times, win_s, step_s)
    triples: list[tuple[int, int, int]] = []
    for (s, e) in bounds:
        idxs = [
            i for i in range(s, e)
            if all(aligned[n][i] is not None for n in names)
        ]
        if len(idxs) < min_points:
            continue
        hr = [aligned["HR"][i] for i in idxs]   # type: ignore[misc]
        rr = [aligned["RR"][i] for i in idxs]   # type: ignore[misc]
        mp = [aligned["MAP"][i] for i in idxs]  # type: ignore[misc]
        triples.append((_slope_sign(hr), _slope_sign(rr), _slope_sign(mp)))
    return _trend_concordance(triples)


def rsa_coarse(
    aligned: dict[str, list[float | None]],
    grid_times: list[float],
    win_s: float = CONCORDANCE_WIN_S,
    step_s: float = CONCORDANCE_STEP_S,
    min_points: int = MIN_WIN_POINTS,
) -> float | None:
    """COARSE RSA surrogate: mean over windows of |corr(detrended HR, detrended RR)|.

    This is a numeric-grid surrogate of respiratory sinus arrhythmia: within each
    short window we detrend HR and RR (removing slow drift), correlate them, and
    take the absolute value (co-oscillation strength irrespective of phase sign).
    The case-level value is the mean over scorable windows.  NOT beat-to-beat RSA.

    Returns None if RR is jointly absent or no window is scorable.
    """
    def _metric(sub: dict[str, list[float]]) -> float | None:
        hr_d = _detrend(sub["HR"])
        rr_d = _detrend(sub["RR"])
        r = _pearson(hr_d, rr_d)
        return abs(r) if r is not None else None

    vals = _windowed_metric(
        aligned, grid_times, ["HR", "RR"], _metric,
        win_s=win_s, step_s=step_s, min_points=min_points,
    )
    if not vals:
        return None
    return round(sum(vals) / len(vals), 6)


def rsa_beat_stub(
    cfg: dict[str, Any],
    caseid: str,
    t_start: float | None,
    t_end: float | None,
) -> float | None:
    """TRUE beat-to-beat RSA -- DEFERRED stub.

    On the DEFAULT path this returns None and NEVER downloads the 500 Hz ECG.
    It is gated behind cfg["features"]["cardioresp_raw_ecg"] (default False).
    When that flag is enabled a future implementation would load SNUADC/ECG_II,
    detect R-peaks, build the RR-interval tachogram, and compute HF-band power /
    peak-valley RSA over the intraop window [t_start, t_end].  Until then, even
    when enabled, this stub returns None (documented placeholder) so that turning
    the flag on never silently fabricates a value -- and, crucially, the default
    path performs no waveform I/O whatsoever.
    """
    if not cfg.get("features", {}).get(RAW_ECG_FLAG, False):
        return None
    # Flag enabled but implementation deferred: documented no-op placeholder.
    # (Intentionally does NOT download the raw ECG -- real impl is future work.)
    return None


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for the cardio-respiratory triad.

    Downloads NUMERIC tracks per case (HR, RR, MAP; cached).  When HR & MAP are
    not jointly usable, cardioresp_available=0 and all other features are None.
    Features that require RR are None whenever RR is absent.  The beat-to-beat
    RSA is None on the default path (no 500 Hz ECG download).
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float  # noqa: F401  (contract import)

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["cardioresp_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)
        if t_end is None:
            # No leakage cutoff -> cannot define an intraop window safely.
            out[cid_str] = dict(none_row)
            continue

        # ---- HR track (required) --------------------------------------------
        _hr_name, raw_hr = first_available(cfg, cid_str, HR_TRACK_CANDIDATES)
        hr_samples: list[tuple[float, float]] = []
        if raw_hr:
            hr_samples = _clip_to_window(raw_hr, t_start, t_end)
            hr_samples = _filter_physiologic(hr_samples, HR_MIN, HR_MAX)

        # ---- MAP track (required) -------------------------------------------
        _map_name, raw_map = first_available(cfg, cid_str, MAP_TRACK_CANDIDATES)
        map_samples: list[tuple[float, float]] = []
        if raw_map:
            map_samples = _clip_to_window(raw_map, t_start, t_end)
            map_samples = _filter_physiologic(map_samples, MAP_MIN, MAP_MAX)

        # ---- RR track (optional; ventilator / capnometer) -------------------
        _rr_name, raw_rr = first_available(cfg, cid_str, RR_TRACK_CANDIDATES)
        rr_samples: list[tuple[float, float]] = []
        if raw_rr:
            rr_samples = _clip_to_window(raw_rr, t_start, t_end)
            rr_samples = _filter_physiologic(rr_samples, RR_MIN, RR_MAX)

        # Need both HR and MAP present to attempt alignment at all.
        if len(hr_samples) < 2 or len(map_samples) < 2:
            row = dict(none_row)
            row["cardioresp_available"] = 0
            out[cid_str] = row
            continue

        # Grid bounds: union span of the available required signals, clamped to
        # the intraop window (t_start may be None -> use earliest sample time).
        sample_starts = [hr_samples[0][0], map_samples[0][0]]
        sample_ends = [hr_samples[-1][0], map_samples[-1][0]]
        if rr_samples:
            sample_starts.append(rr_samples[0][0])
            sample_ends.append(rr_samples[-1][0])
        grid_start = min(sample_starts)
        if t_start is not None:
            grid_start = max(grid_start, t_start)
        grid_end = max(sample_ends)
        grid_end = min(grid_end, t_end)   # never past the leakage cutoff

        signals: dict[str, list[tuple[float, float]]] = {
            "HR": hr_samples,
            "MAP": map_samples,
        }
        if rr_samples:
            signals["RR"] = rr_samples

        grid_times, aligned = _align_grid(
            signals, grid_start, grid_end, dt=ALIGN_DT_S, max_stale=MAX_STALE_S
        )
        # Ensure RR column exists (all-None) when RR absent, so helpers can index.
        if "RR" not in aligned:
            aligned["RR"] = [None] * len(grid_times)

        # Require >= MIN_JOINT_POINTS HR&MAP jointly-valid points to be "available".
        hr_map_idxs, _ = _joint_valid(aligned, ["HR", "MAP"])
        if len(hr_map_idxs) < MIN_JOINT_POINTS:
            row = dict(none_row)
            row["cardioresp_available"] = 0
            out[cid_str] = row
            continue

        row: dict[str, Any] = dict(none_row)
        row["cardioresp_available"] = 1

        # ---- HR x MAP (baroreflex proxy) ------------------------------------
        row["cardioresp_hr_map_corr"] = hr_map_corr(aligned)

        has_rr = bool(rr_samples)
        if has_rr:
            # ---- HR x RR (cardio-respiratory coupling) ----------------------
            row["cardioresp_hr_rr_corr"] = hr_rr_corr(aligned)
            # ---- 3-way triple concordance -----------------------------------
            row["cardioresp_triple_concordance"] = triple_concordance(
                aligned, grid_times
            )
            # ---- coarse RSA surrogate ---------------------------------------
            row["cardioresp_rsa_coarse"] = rsa_coarse(aligned, grid_times)
        # else: all REQUIRES_RR features remain None (honest missingness).

        # ---- beat-to-beat RSA (deferred; no waveform I/O on default path) ---
        row["cardioresp_rsa_beat"] = rsa_beat_stub(cfg, cid_str, t_start, t_end)

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.cardioresp_coupling
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

    print(f"cardioresp_coupling validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case cardioresp summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
