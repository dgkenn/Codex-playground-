"""temporal.py -- Intraoperative TEMPORAL-STRUCTURE features (§7C/§7D, spirit of §9F).

The Stage-2a totals (tabular.py) and the Stage-2b summaries (hemodynamics.py)
collapse the intraoperative MAP/HR/drug time series to a single number per case
(mean MAP, total minutes < 65, total propofol mg). That throws away *when*
within the case an insult happened and *how* it co-occurred with drug exposure.
This module is the **temporal complement**: it preserves phase, timing,
dynamics, and cross-signal coupling that the time-collapsed summaries discard.

WHY TEMPORAL STRUCTURE MATTERS (rationale, binding for pre-registration)
  * Phase-resolved hypotension: late hypotension (close to surgery end) leaves
    less recovery time before the post-op creatinine that defines the KDIGO
    label, so it is temporally distinct from early hypotension even when the
    total minutes-below are identical.  We split [start, opend] into thirds.
  * Timing/dynamics: time-to-first-event, nadir position, longest continuous
    run, and the linear MAP trend distinguish a single deep dip from chronic
    smouldering hypotension that the cumulative summaries conflate.
  * Cross-signal coupling: hypotension *while propofol effect-site Ce is high* is
    a co-occurring pharmacologic + hemodynamic insult -- a temporal interaction
    that neither the MAP summary nor the drug total can express alone.

CONVENTIONS (shared with hemodynamics.py; do not diverge)
  ARTIFACT FILTERING -- physiologic range gates applied BEFORE any statistic:
    MAP in [MAP_MIN, MAP_MAX] = [20, 200] mmHg; HR in [20, 220] bpm.
  INTRAOPERATIVE WINDOW -- [anestart, opend] -> [opstart, opend] -> (None, opend].
    No sample at t > opend is ever used (prediction cutoff; §11 leakage).
  TIME-WEIGHTED INTEGRATION -- inter-sample dt = t[i+1]-t[i], each capped at
    MAX_INTER_SAMPLE_DT_S = 10 s so recording gaps cannot inflate durations/AUC.
  MISSINGNESS -- if no usable MAP track exists, EVERY feature is None (never 0).
    `temporal_available` (1/0) flags whether a MAP track was usable.

TRACK PRIORITY (verified cohort coverage)
  MAP: Solar8000/ART_MBP (invasive, ~72%) -> Solar8000/NIBP_MBP (~88%).
  HR:  Solar8000/HR (~100%)  [carried for completeness / future use].
  Propofol effect-site Ce: Orchestra/PPF20_CE (~56%).

SET MEMBERSHIP (§9 nested design)
  Hemodynamic-only temporal features -> "comprehensive".
  Anything that depends on propofol effect-site Ce -> "pk" (the drug layer).
All timings are "intraop"; audit_specs() enforces it at import (§11).

Protocol reference: §7C (intraoperative hemodynamic axis), §7D (temporal /
trajectory structure), §9F (incremental value beyond time-collapsed summaries).
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range constants (kept identical to hemodynamics.py; binding).
# ---------------------------------------------------------------------------
MAP_MIN: float = 20.0    # mmHg -- below this is artifact (flush / line disconnected)
MAP_MAX: float = 200.0   # mmHg -- above this is artifact (spike / calibration error)
HR_MIN: float = 20.0     # bpm
HR_MAX: float = 220.0    # bpm

# Primary hypotension threshold for phase / timing / coupling features (§7C).
MAP_HYPO_THRESHOLD: float = 65.0   # mmHg

# Integration gap cap: a single inter-sample dt above this is treated as a
# recording gap and capped, so gaps do not inflate durations/AUC (seconds).
MAX_INTER_SAMPLE_DT_S: float = 10.0

# Common resampling grid step for cross-signal coupling (seconds).
COUPLING_GRID_STEP_S: float = 30.0

# MAP track preference order (matches hemodynamics.py).
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]

# HR track preference order (carried for completeness).
HR_TRACK_CANDIDATES: list[str] = [
    "Solar8000/HR",
    "Solar8000/PLETH_HR",
]

# Propofol effect-site concentration track (pump-computed Ce).
PPFCE_TRACK_CANDIDATES: list[str] = [
    "Orchestra/PPF20_CE",
]

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11)
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- 1. Phase-resolved hypotension (early / mid / late thirds) ----------
    FeatureSpec("map_below65_min_early",  "comprehensive", "intraop",
                "minutes MAP<65 in the EARLY third of the intraop window (§7D)"),
    FeatureSpec("map_below65_min_mid",    "comprehensive", "intraop",
                "minutes MAP<65 in the MIDDLE third of the intraop window (§7D)"),
    FeatureSpec("map_below65_min_late",   "comprehensive", "intraop",
                "minutes MAP<65 in the LATE third (less recovery time before postop Cr) (§7D)"),
    FeatureSpec("map_auc65_early",        "comprehensive", "intraop",
                "area under MAP=65 (mmHg·min) in the EARLY third (§7D)"),
    FeatureSpec("map_auc65_mid",          "comprehensive", "intraop",
                "area under MAP=65 (mmHg·min) in the MIDDLE third (§7D)"),
    FeatureSpec("map_auc65_late",         "comprehensive", "intraop",
                "area under MAP=65 (mmHg·min) in the LATE third (§7D)"),
    # ---- 2. Timing / dynamics of hypotension --------------------------------
    FeatureSpec("map_time_to_first_below65_frac", "comprehensive", "intraop",
                "fraction of case elapsed before first MAP<65 (1.0 if never) (§7D)"),
    FeatureSpec("map_nadir_time_frac",    "comprehensive", "intraop",
                "relative position (0-1) of the global MAP minimum in the window (§7D)"),
    FeatureSpec("map_longest_hypotension_run_min", "comprehensive", "intraop",
                "longest continuous stretch (minutes) with MAP<65 (§7D)"),
    FeatureSpec("map_slope_per_hr",       "comprehensive", "intraop",
                "linear trend of MAP over the case (mmHg per hour) (§7D)"),
    FeatureSpec("map_early_vs_late_mean_delta", "comprehensive", "intraop",
                "mean MAP in last third minus first third (mmHg) (§7D)"),
    # ---- 3. Cross-signal coupling: hypotension during high drug exposure ----
    FeatureSpec("map_below65_during_high_ppfce_min", "pk", "intraop",
                "minutes MAP<65 AND propofol Ce above its own intraop median (§7D/§8)"),
    FeatureSpec("ppfce_map_temporal_corr", "pk", "intraop",
                "Pearson corr of MAP vs propofol Ce on a common 30 s grid (§7D/§8)"),
    # ---- 4. Availability flag ----------------------------------------------
    FeatureSpec("temporal_available",     "comprehensive", "intraop",
                "1 if a MAP track was usable, else 0"),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ---------------------------------------------------------------------------
# Window / filtering helpers (mirror hemodynamics.py so behaviour is identical)
# ---------------------------------------------------------------------------

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds for the intraoperative window.

    Priority: [anestart, opend] -> [opstart, opend] -> (None, opend).
    opend is mandatory (prediction cutoff); without it we return (None, None).
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
    """Return only samples within [t_start, t_end] (either bound may be None).

    The t_end bound is the leakage cutoff (opend); samples with t > t_end are
    NEVER returned (§11).
    """
    out = []
    for t, v in samples:
        if t_start is not None and t < t_start:
            continue
        if t_end is not None and t > t_end:
            continue
        out.append((t, v))
    return out


def _effective_window(
    samples: list[tuple[float, float]],
    t_start: float | None,
    t_end: float | None,
) -> tuple[float, float] | None:
    """Resolve the concrete [w0, w1] window used for phase / timing math.

    Uses explicit bounds when present; otherwise falls back to the span of the
    (already clipped + filtered) samples.  Returns None if it cannot form a
    positive-length window.
    """
    if not samples:
        return None
    w0 = t_start if t_start is not None else samples[0][0]
    w1 = t_end if t_end is not None else samples[-1][0]
    if w1 <= w0:
        return None
    return w0, w1


# ---------------------------------------------------------------------------
# Pure temporal-math helpers (no I/O; unit-testable on synthetic series)
# ---------------------------------------------------------------------------

def phase_thirds(
    samples: list[tuple[float, float]],
    window: tuple[float, float],
) -> tuple[list[tuple[float, float]], list[tuple[float, float]], list[tuple[float, float]]]:
    """Split `samples` into early / mid / late thirds of `window` by timestamp.

    `window` is (w0, w1); the thirds are [w0, b1), [b1, b2), [b2, w1] with
    b1 = w0 + (w1-w0)/3 and b2 = w0 + 2*(w1-w0)/3.  A sample exactly on a
    boundary goes to the earlier bucket; the final boundary (w1) goes to late.
    Samples outside the window are ignored.
    """
    w0, w1 = window
    span = w1 - w0
    if span <= 0:
        return [], [], []
    b1 = w0 + span / 3.0
    b2 = w0 + 2.0 * span / 3.0
    early: list[tuple[float, float]] = []
    mid: list[tuple[float, float]] = []
    late: list[tuple[float, float]] = []
    for t, v in samples:
        if t < w0 or t > w1:
            continue
        if t < b1:
            early.append((t, v))
        elif t < b2:
            mid.append((t, v))
        else:
            late.append((t, v))
    return early, mid, late


def hypotension_minutes_and_auc(
    samples: list[tuple[float, float]],
    threshold: float = MAP_HYPO_THRESHOLD,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> tuple[float, float]:
    """Return (minutes_below, auc_below_mmHg_min) for one threshold.

    Forward-dt weighting: interval i contributes if samples[i] value < threshold,
    with dt capped at max_dt_s.  Matches hemodynamics.hypotension_summaries math.
    """
    seconds_below = 0.0
    auc_below = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        v = samples[i][1]
        if v < threshold:
            seconds_below += dt
            auc_below += (threshold - v) * dt
    return round(seconds_below / 60.0, 4), round(auc_below / 60.0, 4)


def _phase_thirds_for_window(
    samples: list[tuple[float, float]],
    window: tuple[float, float],
) -> tuple[list[tuple[float, float]], list[tuple[float, float]], list[tuple[float, float]]]:
    """phase_thirds with an extra carry-forward sample appended to each bucket.

    For forward-dt integration each bucket needs a right endpoint so the LAST
    sample's interval is measured.  We append the next chronological in-window
    sample to early/mid as the bridge endpoint (so a hypotensive run straddling
    a boundary is attributed correctly to the third it starts in).
    """
    early, mid, late = phase_thirds(samples, window)
    in_win = [(t, v) for t, v in samples if window[0] <= t <= window[1]]
    # index map for fast "next sample" lookup
    by_t = {t: i for i, (t, _) in enumerate(in_win)}

    def _bridge(bucket: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if not bucket:
            return bucket
        last_t = bucket[-1][0]
        j = by_t.get(last_t)
        if j is not None and j + 1 < len(in_win):
            return bucket + [in_win[j + 1]]
        return bucket

    return _bridge(early), _bridge(mid), late


def time_to_first_below_frac(
    samples: list[tuple[float, float]],
    window: tuple[float, float],
    threshold: float = MAP_HYPO_THRESHOLD,
) -> float:
    """Fraction of the window elapsed before the first sample below `threshold`.

    Returns 1.0 if MAP never drops below the threshold (the event is censored at
    the case end).  Clamped to [0, 1].
    """
    w0, w1 = window
    span = w1 - w0
    if span <= 0:
        return 1.0
    for t, v in samples:
        if w0 <= t <= w1 and v < threshold:
            frac = (t - w0) / span
            return round(min(1.0, max(0.0, frac)), 6)
    return 1.0


def nadir_time_frac(
    samples: list[tuple[float, float]],
    window: tuple[float, float],
) -> float | None:
    """Relative position (0-1) of the global minimum value within the window.

    Ties resolve to the FIRST (earliest) occurrence of the minimum.  Returns
    None if no in-window samples.
    """
    w0, w1 = window
    span = w1 - w0
    in_win = [(t, v) for t, v in samples if w0 <= t <= w1]
    if not in_win or span <= 0:
        return None
    min_v = min(v for _, v in in_win)
    for t, v in in_win:          # earliest occurrence of the minimum
        if v == min_v:
            frac = (t - w0) / span
            return round(min(1.0, max(0.0, frac)), 6)
    return None


def longest_run_below(
    samples: list[tuple[float, float]],
    threshold: float = MAP_HYPO_THRESHOLD,
    cap_dt: float = MAX_INTER_SAMPLE_DT_S,
) -> float:
    """Longest CONTINUOUS stretch (minutes) with MAP below `threshold`.

    Walks consecutive intervals; an interval counts toward the current run when
    its left sample is below threshold.  dt is capped at cap_dt so a recording
    gap inside a low stretch does not over-credit a continuous run.  Returns the
    maximum run length in minutes (0.0 if never below threshold).
    """
    longest_s = 0.0
    current_s = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], cap_dt)
        if dt <= 0:
            continue
        if samples[i][1] < threshold:
            current_s += dt
            if current_s > longest_s:
                longest_s = current_s
        else:
            current_s = 0.0
    return round(longest_s / 60.0, 4)


def map_slope_per_hr(samples: list[tuple[float, float]]) -> float | None:
    """Ordinary-least-squares slope of value vs time, expressed in mmHg/hour.

    Returns None if fewer than 2 samples or the timestamps are degenerate
    (zero variance in t).
    """
    n = len(samples)
    if n < 2:
        return None
    sum_t = sum(t for t, _ in samples)
    sum_v = sum(v for _, v in samples)
    mean_t = sum_t / n
    mean_v = sum_v / n
    s_tt = 0.0
    s_tv = 0.0
    for t, v in samples:
        dt = t - mean_t
        s_tt += dt * dt
        s_tv += dt * (v - mean_v)
    if s_tt == 0:
        return None
    slope_per_s = s_tv / s_tt          # mmHg per second
    return round(slope_per_s * 3600.0, 6)


def mean_value(samples: list[tuple[float, float]]) -> float | None:
    """Plain arithmetic mean of the values (None if empty)."""
    if not samples:
        return None
    return sum(v for _, v in samples) / len(samples)


def resample_to_grid(
    samples: list[tuple[float, float]],
    window: tuple[float, float],
    step: float = COUPLING_GRID_STEP_S,
    max_gap_s: float = MAX_INTER_SAMPLE_DT_S,
) -> list[tuple[float, float | None]]:
    """Resample `samples` onto a uniform grid over `window` using last-value hold.

    Grid points are w0, w0+step, ... up to (and including) w1.  Each grid point
    takes the most recent sample value at-or-before it, but only if that sample
    is within `max_gap_s` of the grid point (otherwise the grid point is None,
    representing a recording gap -- not fabricated).  `samples` need not be
    sorted; they are sorted by time internally.
    """
    w0, w1 = window
    if w1 < w0:
        return []
    ordered = sorted(samples, key=lambda s: s[0])
    grid: list[tuple[float, float | None]] = []
    g = w0
    j = 0
    n = len(ordered)
    # last sample index with time <= current grid time
    last_idx = -1
    while g <= w1 + 1e-9:
        while j < n and ordered[j][0] <= g + 1e-9:
            last_idx = j
            j += 1
        if last_idx >= 0 and (g - ordered[last_idx][0]) <= max_gap_s + 1e-9:
            grid.append((g, ordered[last_idx][1]))
        else:
            grid.append((g, None))
        g = round(g + step, 6)
    return grid


def minutes_below_during_high_signal(
    map_samples: list[tuple[float, float]],
    other_samples: list[tuple[float, float]],
    window: tuple[float, float],
    threshold: float = MAP_HYPO_THRESHOLD,
    step: float = COUPLING_GRID_STEP_S,
    max_gap_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Minutes where MAP<threshold AND `other` is above its own in-window median.

    Both signals are resampled onto the SAME uniform grid; a grid cell counts
    (contributing `step` seconds) only when both signals have a value there and
    MAP<threshold and other>=median(other on the grid).  Returns None if the
    `other` series is empty after gridding (no co-occurrence can be measured).
    """
    map_grid = resample_to_grid(map_samples, window, step, max_gap_s)
    oth_grid = resample_to_grid(other_samples, window, step, max_gap_s)
    if not map_grid or not oth_grid:
        return None

    oth_vals = [v for _, v in oth_grid if v is not None]
    if not oth_vals:
        return None
    med = _median(oth_vals)

    oth_by_t = {t: v for t, v in oth_grid}
    seconds = 0.0
    for t, mv in map_grid:
        if mv is None or mv >= threshold:
            continue
        ov = oth_by_t.get(t)
        if ov is None:
            continue
        if ov >= med:
            seconds += step
    return round(seconds / 60.0, 4)


def temporal_pearson_corr(
    a_samples: list[tuple[float, float]],
    b_samples: list[tuple[float, float]],
    window: tuple[float, float],
    step: float = COUPLING_GRID_STEP_S,
    max_gap_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Pearson correlation of two signals resampled onto a common grid.

    Uses only grid cells where BOTH signals have a (non-gap) value.  Returns
    None if fewer than 3 paired points or either series has zero variance.
    """
    a_grid = resample_to_grid(a_samples, window, step, max_gap_s)
    b_grid = resample_to_grid(b_samples, window, step, max_gap_s)
    b_by_t = {t: v for t, v in b_grid}
    xs: list[float] = []
    ys: list[float] = []
    for t, av in a_grid:
        if av is None:
            continue
        bv = b_by_t.get(t)
        if bv is None:
            continue
        xs.append(av)
        ys.append(bv)
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    r = sxy / math.sqrt(sxx * syy)
    return round(max(-1.0, min(1.0, r)), 6)


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


# ---------------------------------------------------------------------------
# Public extract() -- matches the FeatureSpec contract
# ---------------------------------------------------------------------------

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for intraop temporal structure.

    Returns None for EVERY feature when no usable MAP track exists for a case
    (temporal_available=0).  The propofol-coupling features (fset="pk") are None
    when no propofol Ce track exists, even if MAP is present.
    """
    from vitaldb_aki.data.tracks import first_available

    none_row: dict[str, Any] = {s.name: None for s in SPECS}

    out: dict[str, dict[str, Any]] = {}
    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            row = dict(none_row)
            row["temporal_available"] = 0
            out[cid_str] = row
            continue

        t_start, t_end = _intraop_window(case)

        # ---- MAP track ------------------------------------------------------
        _map_tname, raw_map = first_available(cfg, cid_str, MAP_TRACK_CANDIDATES)
        if not raw_map:
            row = dict(none_row)
            row["temporal_available"] = 0
            out[cid_str] = row
            continue

        map_samples = _clip_to_window(raw_map, t_start, t_end)
        map_samples = _filter_physiologic(map_samples, MAP_MIN, MAP_MAX)

        win = _effective_window(map_samples, t_start, t_end)
        if not map_samples or win is None:
            row = dict(none_row)
            row["temporal_available"] = 0
            out[cid_str] = row
            continue

        row = _compute_row(map_samples, win)

        # ---- Cross-signal coupling (propofol Ce) ----------------------------
        _ppf_tname, raw_ppf = first_available(cfg, cid_str, PPFCE_TRACK_CANDIDATES)
        if raw_ppf:
            ppf_samples = _clip_to_window(raw_ppf, t_start, t_end)
            # Ce is a non-negative concentration; drop negatives as artefacts,
            # keep zeros (no drug yet is meaningful).
            ppf_samples = [(t, v) for t, v in ppf_samples if v >= 0.0]
            if ppf_samples:
                row["map_below65_during_high_ppfce_min"] = minutes_below_during_high_signal(
                    map_samples, ppf_samples, win)
                row["ppfce_map_temporal_corr"] = temporal_pearson_corr(
                    map_samples, ppf_samples, win)
        # else: leave the two pk features as None (no propofol Ce track)

        out[cid_str] = row

    return out


def _compute_row(
    map_samples: list[tuple[float, float]],
    win: tuple[float, float],
) -> dict[str, Any]:
    """Compute all hemodynamic-only temporal features for one case."""
    early, mid, late = _phase_thirds_for_window(map_samples, win)

    e_min, e_auc = hypotension_minutes_and_auc(early)
    m_min, m_auc = hypotension_minutes_and_auc(mid)
    l_min, l_auc = hypotension_minutes_and_auc(late)

    # early vs late mean delta uses the raw (un-bridged) thirds
    raw_early, _raw_mid, raw_late = phase_thirds(map_samples, win)
    mean_early = mean_value(raw_early)
    mean_late = mean_value(raw_late)
    if mean_early is not None and mean_late is not None:
        early_late_delta: float | None = round(mean_late - mean_early, 4)
    else:
        early_late_delta = None

    return {
        "map_below65_min_early": e_min,
        "map_below65_min_mid":   m_min,
        "map_below65_min_late":  l_min,
        "map_auc65_early":       e_auc,
        "map_auc65_mid":         m_auc,
        "map_auc65_late":        l_auc,
        "map_time_to_first_below65_frac": time_to_first_below_frac(map_samples, win),
        "map_nadir_time_frac":   nadir_time_frac(map_samples, win),
        "map_longest_hypotension_run_min": longest_run_below(map_samples),
        "map_slope_per_hr":      map_slope_per_hr(map_samples),
        "map_early_vs_late_mean_delta": early_late_delta,
        # pk features default to None; filled in by the caller if Ce present
        "map_below65_during_high_ppfce_min": None,
        "ppfce_map_temporal_corr": None,
        "temporal_available":    1,
    }


# ---------------------------------------------------------------------------
# Real-data validation (run once; NOT part of unit tests). Network lives here.
# Run: python -m vitaldb_aki.features.temporal
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import csv
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from common.config import load_yaml
    from vitaldb_aki.data.client import fetch_cases

    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    cfg = load_yaml(cfg_path)

    cohort_path = os.path.join(cfg["data"]["cache_dir"], "cohort.csv")
    cohort_ids: list[str] = []
    with open(cohort_path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            cohort_ids.append(str(r["caseid"]))
            if len(cohort_ids) >= 15:
                break

    print(f"Validating temporal features on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    n_map = sum(1 for r in result.values() if r.get("temporal_available") == 1)
    n_couple = sum(1 for r in result.values()
                   if r.get("ppfce_map_temporal_corr") is not None)
    print(f"\nMAP usable: {n_map}/{len(cohort_ids)} "
          f"({100.0 * n_map / len(cohort_ids):.0f}%)")
    print(f"Propofol-Ce coupling available: {n_couple}/{len(cohort_ids)} "
          f"({100.0 * n_couple / len(cohort_ids):.0f}%)")

    print("\nPer-case temporal sample:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        print(
            f"  case {cid:>5s}: avail={r.get('temporal_available')}  "
            f"below65(e/m/l)={r.get('map_below65_min_early')}/"
            f"{r.get('map_below65_min_mid')}/{r.get('map_below65_min_late')}  "
            f"nadir_frac={r.get('map_nadir_time_frac')}  "
            f"longest_run={r.get('map_longest_hypotension_run_min')}  "
            f"slope/hr={r.get('map_slope_per_hr')}  "
            f"ppfce_corr={r.get('ppfce_map_temporal_corr')}  "
            f"below65_hi_ppfce={r.get('map_below65_during_high_ppfce_min')}"
        )
