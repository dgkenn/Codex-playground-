"""hemodynamics.py -- Intraoperative hemodynamic features (§7C).

Computes time-weighted hypotension burden, MAP variability, heart-rate burden, and
hypertensive exposure from continuous per-case VitalDB tracks (Solar8000/EV1000).

Key design decisions (all binding, documented here for pre-registration):

ARTIFACT FILTERING
  Physiologic range gates are applied BEFORE any summary statistic:
    MAP: keep samples in [MAP_MIN, MAP_MAX]  = [20, 200] mmHg
    HR:  keep samples in [HR_MIN,  HR_MAX]   = [20, 220] bpm
  Values outside these bounds are treated as sensor artifacts (flush events,
  clamp artefacts, cable disconnects) and excluded.  Constants are defined at
  module top so config-readable audits can reference them.

INTRAOPERATIVE WINDOW
  Samples are restricted to [anestart, opend] (anesthesia start to end of surgery).
  Fallback order: [anestart, opend] -> [opstart, opend] -> full track.
  No samples after opend are used; opend is the prediction cutoff (§11).
  Case time fields (anestart, opstart, opend) are seconds from casestart == 0.

TIME-WEIGHTED INTEGRATION
  All duration and area integrals use actual inter-sample dt (dt = t_i+1 - t_i),
  NOT sample counts, to handle Solar8000 irregular spacing (~2 s typical) and
  recording gaps.  A single inter-sample gap is capped at MAX_INTER_SAMPLE_DT_S
  = 10 s so that a long recording gap does not falsely inflate hypotension area.
  Results are expressed in minutes (divide seconds by 60).

TRACK PRIORITY
  MAP: Solar8000/ART_MBP (invasive) -> Solar8000/NIBP_MBP (non-invasive) ->
       EV1000/ART_MBP.  `map_invasive` flag records which was used.
  SBP (hypertensive exposure): Solar8000/ART_SBP -> Solar8000/NIBP_SBP.
  HR:  Solar8000/HR -> Solar8000/PLETH_HR.

MISSINGNESS
  If no usable MAP track exists for a case, ALL features are None (not 0).
  `map_available` (1/0) signals downstream whether MAP was present.
  HR features are None when no HR track exists for a case.

Protocol reference: §7C (intraoperative hemodynamic feature axis).
Leakage compliance: all features are "intraop"; prediction cutoff is opend (§11).
"""
from __future__ import annotations

import math
import statistics
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# ---------------------------------------------------------------------------
# Physiologic range constants (binding; documented in pre-registration).
# ---------------------------------------------------------------------------
MAP_MIN: float = 20.0    # mmHg -- below this is artifact (flush / line disconnected)
MAP_MAX: float = 200.0   # mmHg -- above this is artifact (spike / calibration error)
HR_MIN: float = 20.0     # bpm  -- below this is artifact or asystole artefact
HR_MAX: float = 220.0    # bpm  -- above this is artifact

# Hypotension thresholds (§7C)
MAP_HYPO_THRESHOLDS: tuple[int, ...] = (65, 60, 55, 50)   # mmHg

# Hypertensive exposure threshold -- MAP > 120 mmHg (§7C "hypertensive exposure")
MAP_HYPER_THRESHOLD: float = 120.0   # mmHg

# HR burden thresholds
HR_TACHY_THRESHOLD: float = 100.0    # bpm
HR_BRADY_THRESHOLD: float = 50.0     # bpm

# Integration gap cap: inter-sample dt > this is treated as a recording gap and
# capped at this value so gaps do not inflate AUC/duration (seconds).
MAX_INTER_SAMPLE_DT_S: float = 10.0

# Baseline MAP window for relative-drop computation (seconds)
BASELINE_WINDOW_S: float = 5.0 * 60.0   # first 5 minutes of intraop window

# MAP track preference order
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]
MAP_INVASIVE_TRACK: str = "Solar8000/ART_MBP"

# SBP track preference order (for hypertensive exposure fallback; not used here;
# we use MAP > 120 as the primary hypertensive-exposure feature -- documented)
SBP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_SBP",
    "Solar8000/NIBP_SBP",
]

# HR track preference order
HR_TRACK_CANDIDATES: list[str] = [
    "Solar8000/HR",
    "Solar8000/PLETH_HR",
]

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11)
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability flags ------------------------------------------------
    FeatureSpec("map_available",      "standard",       "intraop",
                "1 if any MAP track present else 0"),
    FeatureSpec("map_invasive",       "standard",       "intraop",
                "1 if invasive ART_MBP used, 0 if non-invasive NIBP fallback"),
    # ---- basic MAP summaries -----------------------------------------------
    FeatureSpec("map_mean",           "standard",       "intraop",
                "time-weighted mean MAP (mmHg) in intraop window"),
    FeatureSpec("map_lowest",         "standard",       "intraop",
                "minimum MAP (mmHg) in intraop window after artifact filter"),
    FeatureSpec("map_sd",             "comprehensive",  "intraop",
                "SD of MAP (mmHg) -- variability (§7C)"),
    # ---- hypotension: cumulative MINUTES below thresholds ------------------
    FeatureSpec("map_min_below_65",   "standard",       "intraop",
                "cumulative minutes with MAP < 65 mmHg (§7C)"),
    FeatureSpec("map_min_below_60",   "comprehensive",  "intraop",
                "cumulative minutes with MAP < 60 mmHg"),
    FeatureSpec("map_min_below_55",   "comprehensive",  "intraop",
                "cumulative minutes with MAP < 55 mmHg"),
    FeatureSpec("map_min_below_50",   "comprehensive",  "intraop",
                "cumulative minutes with MAP < 50 mmHg"),
    # ---- hypotension: area under threshold (mmHg·min) ----------------------
    FeatureSpec("map_auc_below_65",   "standard",       "intraop",
                "area under MAP=65 threshold (mmHg·min) (§7C)"),
    FeatureSpec("map_auc_below_60",   "comprehensive",  "intraop",
                "area under MAP=60 threshold (mmHg·min)"),
    FeatureSpec("map_auc_below_55",   "comprehensive",  "intraop",
                "area under MAP=55 threshold (mmHg·min)"),
    FeatureSpec("map_auc_below_50",   "comprehensive",  "intraop",
                "area under MAP=50 threshold (mmHg·min)"),
    # ---- hypotension: fraction of intraop time -----------------------------
    FeatureSpec("map_frac_below_65",  "standard",       "intraop",
                "fraction of intraop recording time with MAP < 65 (§7C)"),
    # ---- relative hypotension ----------------------------------------------
    FeatureSpec("map_rel_drop_pct",   "standard",       "intraop",
                "% decrease of lowest MAP from first-5-min baseline (§7C)"),
    # ---- hypertensive exposure (MAP > 120) ---------------------------------
    FeatureSpec("map_min_above_120",  "comprehensive",  "intraop",
                "cumulative minutes with MAP > 120 mmHg (hypertensive exposure §7C)"),
    # ---- heart rate burden -------------------------------------------------
    FeatureSpec("hr_mean",            "comprehensive",  "intraop",
                "time-weighted mean HR (bpm) in intraop window"),
    FeatureSpec("hr_min_tachy_gt100", "comprehensive",  "intraop",
                "cumulative minutes with HR > 100 bpm (tachycardia burden §7C)"),
    FeatureSpec("hr_min_brady_lt50",  "comprehensive",  "intraop",
                "cumulative minutes with HR < 50 bpm (bradycardia burden §7C)"),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ---------------------------------------------------------------------------
# Pure computation helpers (no I/O; unit-testable without network)
# ---------------------------------------------------------------------------

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds for the intraoperative window.

    Priority: [anestart, opend] -> [opstart, opend] -> (None, None).
    opend is mandatory (prediction cutoff); without it we cannot safely
    constrain the window.
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
    return None, opend   # use whole track up to opend


def _filter_physiologic(
    samples: list[tuple[float, float]],
    vmin: float,
    vmax: float,
) -> list[tuple[float, float]]:
    """Drop samples outside [vmin, vmax] (artifact rejection).

    Handles negative values (arterial-line flush artefacts such as MAP = -70)
    and physiologically impossible spikes (MAP = 346).
    """
    return [(t, v) for t, v in samples if vmin <= v <= vmax]


def _clip_to_window(
    samples: list[tuple[float, float]],
    t_start: float | None,
    t_end: float | None,
) -> list[tuple[float, float]]:
    """Return only samples within [t_start, t_end].

    Either bound may be None, meaning unbounded on that side.
    """
    out = []
    for t, v in samples:
        if t_start is not None and t < t_start:
            continue
        if t_end is not None and t > t_end:
            continue
        out.append((t, v))
    return out


def _time_weighted_mean(
    samples: list[tuple[float, float]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Time-weighted mean value using trapezoid-like forward-dt weighting.

    Each sample i contributes value[i] * min(dt[i], max_dt_s) where
    dt[i] = t[i+1] - t[i] (last sample gets dt = 0; it is a point).
    Returns None if fewer than 2 samples.
    """
    if len(samples) < 2:
        return None
    total_w = 0.0
    total_wv = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        total_w += dt
        total_wv += samples[i][1] * dt
    if total_w == 0:
        return None
    return total_wv / total_w


def _total_recording_time_s(
    samples: list[tuple[float, float]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float:
    """Sum of capped inter-sample intervals -- the effective recording duration."""
    total = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt > 0:
            total += dt
    return total


def hypotension_summaries(
    samples: list[tuple[float, float]],
    thresholds: tuple[int, ...] = MAP_HYPO_THRESHOLDS,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> dict[str, float]:
    """Compute time-below and AUC-below for each MAP threshold (§7C).

    Args:
        samples: [(t_seconds, map_mmhg), ...] already filtered and window-clipped.
        thresholds: MAP thresholds in mmHg (e.g. (65, 60, 55, 50)).
        max_dt_s: cap on a single inter-sample gap (seconds).

    Returns:
        Dict with keys 'min_below_{thr}' (minutes) and 'auc_below_{thr}'
        (mmHg·min) for each threshold.  Also 'total_recording_min' and
        'frac_below_65'.
    """
    # Initialize accumulators
    seconds_below: dict[int, float] = {t: 0.0 for t in thresholds}
    auc_below: dict[int, float] = {t: 0.0 for t in thresholds}

    total_s = 0.0

    for i in range(len(samples) - 1):
        t_i, v_i = samples[i]
        dt = min(samples[i + 1][0] - t_i, max_dt_s)
        if dt <= 0:
            continue
        total_s += dt
        for thr in thresholds:
            if v_i < thr:
                seconds_below[thr] += dt
                auc_below[thr] += (thr - v_i) * dt  # mmHg·seconds

    result: dict[str, float] = {}
    for thr in thresholds:
        result[f"min_below_{thr}"] = round(seconds_below[thr] / 60.0, 4)
        result[f"auc_below_{thr}"] = round(auc_below[thr] / 60.0, 4)   # mmHg·min

    result["total_recording_min"] = round(total_s / 60.0, 4)
    frac = (seconds_below[65] / total_s) if total_s > 0 and 65 in thresholds else 0.0
    result["frac_below_65"] = round(frac, 6)
    return result


def hypertensive_burden_min(
    samples: list[tuple[float, float]],
    threshold: float = MAP_HYPER_THRESHOLD,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float:
    """Cumulative minutes with MAP above `threshold` (hypertensive exposure §7C)."""
    seconds_above = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt > 0 and samples[i][1] > threshold:
            seconds_above += dt
    return round(seconds_above / 60.0, 4)


def baseline_map(
    samples: list[tuple[float, float]],
    window_s: float = BASELINE_WINDOW_S,
) -> float | None:
    """Median MAP in the first `window_s` seconds of intraop window (§7C).

    Used as the denominator for relative MAP drop.  Returns None if no samples
    in the window.
    """
    if not samples:
        return None
    t0 = samples[0][0]
    t_cutoff = t0 + window_s
    baseline_vals = [v for t, v in samples if t <= t_cutoff]
    if not baseline_vals:
        return None
    # sort and take median
    baseline_vals_sorted = sorted(baseline_vals)
    n = len(baseline_vals_sorted)
    mid = n // 2
    if n % 2 == 1:
        return baseline_vals_sorted[mid]
    return (baseline_vals_sorted[mid - 1] + baseline_vals_sorted[mid]) / 2.0


def relative_drop_pct(
    samples: list[tuple[float, float]],
    baseline_window_s: float = BASELINE_WINDOW_S,
) -> float | None:
    """Percent decrease of lowest MAP from baseline MAP (§7C).

    Formula: 100 * (baseline - lowest) / baseline.
    Returns None if baseline could not be computed or baseline <= 0.
    """
    base = baseline_map(samples, baseline_window_s)
    if base is None or base <= 0:
        return None
    lowest = min(v for _, v in samples)
    drop = 100.0 * (base - lowest) / base
    return round(drop, 4)


def hr_summaries(
    samples: list[tuple[float, float]],
    tachy_thr: float = HR_TACHY_THRESHOLD,
    brady_thr: float = HR_BRADY_THRESHOLD,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> dict[str, float | None]:
    """Time-weighted HR mean and tachy/brady burden in minutes (§7C).

    Args:
        samples: [(t_seconds, hr_bpm), ...] already filtered and window-clipped.

    Returns:
        Dict with keys 'hr_mean', 'hr_min_tachy_gt100', 'hr_min_brady_lt50'.
        All None if fewer than 2 samples.
    """
    if len(samples) < 2:
        return {"hr_mean": None, "hr_min_tachy_gt100": None, "hr_min_brady_lt50": None}

    total_w = 0.0
    total_wv = 0.0
    tachy_s = 0.0
    brady_s = 0.0

    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        v = samples[i][1]
        total_w += dt
        total_wv += v * dt
        if v > tachy_thr:
            tachy_s += dt
        if v < brady_thr:
            brady_s += dt

    hr_mean = (total_wv / total_w) if total_w > 0 else None
    return {
        "hr_mean": round(hr_mean, 4) if hr_mean is not None else None,
        "hr_min_tachy_gt100": round(tachy_s / 60.0, 4),
        "hr_min_brady_lt50": round(brady_s / 60.0, 4),
    }


# ---------------------------------------------------------------------------
# Public extract() -- matches the FeatureSpec contract
# ---------------------------------------------------------------------------

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for intraoperative hemodynamics (§7C).

    Downloads tracks for each case (cached under cfg['data']['cache_dir']/tracks/).
    Returns None for every feature when no usable MAP track is found for a case,
    so downstream imputation/missingness handling is honest.

    Args:
        cfg: loaded config dict (from common.config.load_yaml).
        cases_by_id: {caseid_str: case_dict} from the /cases table.
        caseids: list of case IDs to process.

    Returns:
        {caseid_str: {feature_name: value|None}}.
    """
    from vitaldb_aki.data.tracks import download_track, first_available

    none_row: dict[str, Any] = {s.name: None for s in SPECS}

    out: dict[str, dict[str, Any]] = {}
    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        # ---- Intraoperative window -----------------------------------------
        t_start, t_end = _intraop_window(case)

        # ---- MAP track -------------------------------------------------------
        map_tname, raw_map = first_available(cfg, cid_str, MAP_TRACK_CANDIDATES)

        if not raw_map:
            # No MAP track at all
            row: dict[str, Any] = dict(none_row)
            row["map_available"] = 0
            row["map_invasive"] = None
            out[cid_str] = row
            continue

        # Clip to intraop window then filter artifacts
        map_samples = _clip_to_window(raw_map, t_start, t_end)
        map_samples = _filter_physiologic(map_samples, MAP_MIN, MAP_MAX)

        if not map_samples:
            # Track present but all samples either outside window or artifact
            row = dict(none_row)
            row["map_available"] = 0
            row["map_invasive"] = None
            out[cid_str] = row
            continue

        map_available = 1
        map_invasive = 1 if map_tname == MAP_INVASIVE_TRACK else 0

        # ---- MAP basic summaries -------------------------------------------
        map_mean = _time_weighted_mean(map_samples)
        map_lowest = min(v for _, v in map_samples)

        # SD (population sd; requires >= 2 values)
        vals = [v for _, v in map_samples]
        if len(vals) >= 2:
            mean_v = sum(vals) / len(vals)
            variance = sum((v - mean_v) ** 2 for v in vals) / len(vals)
            map_sd: float | None = round(math.sqrt(variance), 4)
        else:
            map_sd = None

        # ---- Hypotension summaries -----------------------------------------
        hypo = hypotension_summaries(map_samples)

        # ---- Hypertensive exposure -----------------------------------------
        map_min_above_120 = hypertensive_burden_min(map_samples)

        # ---- Relative drop -------------------------------------------------
        map_rel_drop = relative_drop_pct(map_samples)

        # ---- HR track -------------------------------------------------------
        hr_tname, raw_hr = first_available(cfg, cid_str, HR_TRACK_CANDIDATES)
        if raw_hr:
            hr_samples = _clip_to_window(raw_hr, t_start, t_end)
            hr_samples = _filter_physiologic(hr_samples, HR_MIN, HR_MAX)
            hr_s = hr_summaries(hr_samples)
        else:
            hr_s = {"hr_mean": None, "hr_min_tachy_gt100": None, "hr_min_brady_lt50": None}

        # ---- Assemble output row -------------------------------------------
        row = {
            "map_available":      map_available,
            "map_invasive":       map_invasive,
            "map_mean":           round(map_mean, 4) if map_mean is not None else None,
            "map_lowest":         round(map_lowest, 4),
            "map_sd":             map_sd,
            "map_min_below_65":   hypo["min_below_65"],
            "map_min_below_60":   hypo["min_below_60"],
            "map_min_below_55":   hypo["min_below_55"],
            "map_min_below_50":   hypo["min_below_50"],
            "map_auc_below_65":   hypo["auc_below_65"],
            "map_auc_below_60":   hypo["auc_below_60"],
            "map_auc_below_55":   hypo["auc_below_55"],
            "map_auc_below_50":   hypo["auc_below_50"],
            "map_frac_below_65":  hypo["frac_below_65"],
            "map_rel_drop_pct":   map_rel_drop,
            "map_min_above_120":  map_min_above_120,
            "hr_mean":            hr_s["hr_mean"],
            "hr_min_tachy_gt100": hr_s["hr_min_tachy_gt100"],
            "hr_min_brady_lt50":  hr_s["hr_min_brady_lt50"],
        }
        out[cid_str] = row

    return out


# ---------------------------------------------------------------------------
# Real-data validation (run once; not part of unit tests)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    """Validate on first 15 cohort cases. Run: python -m vitaldb_aki.features.hemodynamics"""
    import csv
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from common.config import load_yaml
    from vitaldb_aki.data.client import fetch_cases

    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    cfg = load_yaml(cfg_path)

    # Load cohort caseids
    cohort_path = os.path.join(cfg["data"]["cache_dir"], "cohort.csv")
    cohort_ids: list[str] = []
    with open(cohort_path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cohort_ids.append(str(row["caseid"]))
            if len(cohort_ids) >= 15:
                break

    print(f"Validating on {len(cohort_ids)} cases: {cohort_ids}")

    # Build cases_by_id
    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    # Summarise
    n_art = sum(1 for r in result.values() if r.get("map_invasive") == 1)
    n_nibp = sum(1 for r in result.values() if r.get("map_invasive") == 0 and r.get("map_available") == 1)
    n_none = sum(1 for r in result.values() if not r.get("map_available"))
    print(f"\nMAP source: ART invasive={n_art}, NIBP={n_nibp}, none={n_none}")

    map_lows = [r["map_lowest"] for r in result.values() if r.get("map_lowest") is not None]
    map_hypo = [r["map_min_below_65"] for r in result.values() if r.get("map_min_below_65") is not None]
    hr_means = [r["hr_mean"] for r in result.values() if r.get("hr_mean") is not None]

    if map_lows:
        print(f"map_lowest: min={min(map_lows):.1f} mean={sum(map_lows)/len(map_lows):.1f} max={max(map_lows):.1f}")
    if map_hypo:
        print(f"map_min_below_65: min={min(map_hypo):.2f} mean={sum(map_hypo)/len(map_hypo):.2f} max={max(map_hypo):.2f} min")
    if hr_means:
        print(f"hr_mean: min={min(hr_means):.1f} mean={sum(hr_means)/len(hr_means):.1f} max={max(hr_means):.1f}")

    print("\nPer-case summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        src = "ART" if r.get("map_invasive") == 1 else ("NIBP" if r.get("map_available") else "none")
        print(
            f"  case {cid:>5s}: src={src:4s}  "
            f"map_lowest={r.get('map_lowest')!r:>7}  "
            f"map_min_below_65={r.get('map_min_below_65')!r:>7}  "
            f"hr_mean={r.get('hr_mean')!r}"
        )
