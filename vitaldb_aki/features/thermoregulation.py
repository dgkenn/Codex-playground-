"""thermoregulation.py -- Intraoperative temperature dysregulation biomarker family.

UNMINED AXIS.  Most of the VitalDB-AKI feature modules attack hemodynamics,
perfusion, anesthetic PK/PD or ventilation; none characterise the patient's
**thermal trajectory**.  Yet intraoperative hypothermia is a well-established,
*independent* perioperative risk factor:

  * coagulopathy (platelet dysfunction + slowed enzyme kinetics) -> bleeding,
    transfusion, hypovolaemia;
  * impaired immunity and wound healing -> surgical-site infection;
  * peripheral vasoconstriction, "afterdrop" on rewarming, and shivering ->
    raised O2 demand and a redistribution insult.

Each of these stresses the kidney (and other organs) directly or via the
downstream volume / inflammatory cascade, so the depth, duration, and *recovery*
of an intraoperative cold dose is a plausible, currently-unmined contributor to
organ stress / AKI.

This module operationalises that axis from a single numeric body-temperature
track.  Everything is computed on the **intraoperative window** only.

BIOMARKERS (all fset="comprehensive"; None when temperature track is absent)
---------------------------------------------------------------------------
  thermo_available          -- 1 if a usable temperature series (>=10 gated
                               samples) exists, else 0.
  thermo_min_temp           -- minimum gated temperature (depth of hypothermia).
  thermo_mean_temp          -- time-weighted mean temperature.
  thermo_hypothermia_frac   -- fraction of intraop time with temp < 36.0 C.
  thermo_hypothermia_auc    -- time-integral (C*min) of (36.0 - temp) over
                               intervals where temp < 36.0 (cumulative cold dose).
  thermo_temp_variability   -- SD of gated temperature.
  thermo_rewarming_rate     -- warming slope (C/hour) from the temperature nadir
                               to the end of the window (recovery capacity).

LEAKAGE
-------
All features are timing="intraop".  The prediction cutoff is opend; no sample at
t > opend is ever used.  `_intraop_window` is copied verbatim from pfds.py and
audit_specs() enforces the firewall at import (Sec 11).

MISSINGNESS
-----------
If no temperature track is present (or fewer than MIN_USABLE_SAMPLES gated
samples remain), thermo_available = 0 and **every other feature is None** (not
0).  thermo_available is the first spec.

CONSTANTS (binding; pre-registered)
  NORMO_THR    = 36.0  C  -- hypothermia threshold (below this == hypothermic)
  TEMP_MIN     = 30.0  C  -- artifact gate (drop probe-disconnect lows)
  TEMP_MAX     = 42.0  C  -- artifact gate (drop probe-disconnect highs)
  MIN_USABLE_SAMPLES = 10 -- minimum gated samples to call the track "usable"
  MAX_INTER_SAMPLE_DT_S = 10.0 s -- gap cap (shared convention with pfds.py)

Protocol reference: Sec 7 (novel axes), Sec 9 (nested feature sets), Sec 11
(leakage firewall).
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range / parameter constants (binding; pre-registered)
# ---------------------------------------------------------------------------
NORMO_THR: float = 36.0            # C -- hypothermia threshold
TEMP_MIN: float = 30.0             # C -- artifact gate (probe disconnect)
TEMP_MAX: float = 42.0             # C -- artifact gate (probe disconnect)
MIN_USABLE_SAMPLES: int = 10       # gated samples required to call track usable
MAX_INTER_SAMPLE_DT_S: float = 10.0  # s -- gap cap (shared with pfds/hemodynamics)

# Track priority (binding).  Numeric body temperature only.
BT_TRACK_CANDIDATES: list[str] = [
    "Solar8000/BT",
]

# ---------------------------------------------------------------------------
# Feature specs (Sec 9 nested design; all "intraop" -- leakage firewall Sec 11)
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "thermo_available", "comprehensive", "intraop",
        "1 if a usable body-temperature series (>=10 gated samples) exists, else 0",
    ),
    FeatureSpec(
        "thermo_min_temp", "comprehensive", "intraop",
        "Minimum gated intraoperative temperature (C) -- depth of hypothermia",
    ),
    FeatureSpec(
        "thermo_mean_temp", "comprehensive", "intraop",
        "Time-weighted mean intraoperative temperature (C)",
    ),
    FeatureSpec(
        "thermo_hypothermia_frac", "comprehensive", "intraop",
        "Fraction of intraop time with temperature < 36.0 C",
    ),
    FeatureSpec(
        "thermo_hypothermia_auc", "comprehensive", "intraop",
        "Time-integral (C*min) of (36.0 - temp) over intervals where temp < 36.0 C "
        "-- cumulative cold dose",
    ),
    FeatureSpec(
        "thermo_temp_variability", "comprehensive", "intraop",
        "Standard deviation of gated intraoperative temperature (C)",
    ),
    FeatureSpec(
        "thermo_rewarming_rate", "comprehensive", "intraop",
        "Warming slope (C/hour) from the temperature nadir to end-of-window "
        "-- thermal recovery capacity",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Window / gating helpers (pure; no I/O)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds.py so the leakage cutoff (t_end == opend) is
    computed identically across modules.
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


# ===========================================================================
# Pure statistical helpers (unit-testable on synthetic series)
# ===========================================================================

def _time_weighted_mean(
    samples: list[tuple[float, float]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Forward-dt time-weighted mean (mirrors pfds._time_weighted_mean)."""
    if len(samples) < 2:
        return None
    tw = tw_v = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        tw += dt
        tw_v += samples[i][1] * dt
    return (tw_v / tw) if tw > 0 else None


def _min_gated(samples: list[tuple[float, float]]) -> float | None:
    """Minimum value over the (already gated) series.  None if empty."""
    if not samples:
        return None
    return min(v for _, v in samples)


def _frac_time_below(
    samples: list[tuple[float, float]],
    thr: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Time-weighted fraction of the series spent with value < thr.

    Forward-dt weighting with a per-gap cap so a long recording gap cannot
    inflate either numerator or denominator.  Returns None if < 2 samples or
    no positive recording time accrued; otherwise a fraction in [0, 1].
    """
    if len(samples) < 2:
        return None
    total = 0.0
    below = 0.0
    for i in range(len(samples) - 1):
        t_i, v_i = samples[i]
        dt = min(samples[i + 1][0] - t_i, max_dt_s)
        if dt <= 0:
            continue
        total += dt
        if v_i < thr:
            below += dt
    if total <= 0:
        return None
    return round(below / total, 6)


def _auc_below(
    samples: list[tuple[float, float]],
    thr: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Time-integral of (thr - value) over intervals where value < thr, in
    value-units * MINUTES (e.g. C*min for temperature).

    Forward-dt weighting with a per-gap cap (gaps capped at max_dt_s).  The
    deficit (thr - v_i) is summed only on intervals whose left endpoint is
    below the threshold (cumulative cold dose).  Returns None if < 2 samples;
    0.0 if the value is never below the threshold.
    """
    if len(samples) < 2:
        return None
    auc_s = 0.0  # accumulates in value-units * seconds
    for i in range(len(samples) - 1):
        t_i, v_i = samples[i]
        dt = min(samples[i + 1][0] - t_i, max_dt_s)
        if dt <= 0:
            continue
        if v_i < thr:
            auc_s += (thr - v_i) * dt
    return round(auc_s / 60.0, 6)  # -> value-units * minutes


def _sd(samples: list[tuple[float, float]]) -> float | None:
    """Sample standard deviation of the values (unweighted).

    Returns None if < 2 samples (variance undefined).  Uses the n-1 (sample)
    denominator.
    """
    vals = [v for _, v in samples]
    n = len(vals)
    if n < 2:
        return None
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    return round(var ** 0.5, 6)


def _rewarming_rate(samples: list[tuple[float, float]]) -> float | None:
    """Warming slope (C/hour) from the temperature nadir to end-of-window.

    Find the nadir (minimum value; first occurrence on ties).  Over the samples
    *strictly after* the nadir, fit a slope d(value)/d(time) and convert to
    per-hour units.  With >= 3 post-nadir points an OLS slope is used; with
    exactly 2 the two-point slope (last - nadir)/(t_last - t_nadir) is used.

    Returns None when:
      * fewer than 2 total samples;
      * the nadir is at or after the last sample (no post-nadir data); or
      * there are fewer than 3 post-nadir points AND the available points do not
        yield a defined slope (degenerate / zero time span).

    Captures recovery capacity: a positive rate == active rewarming.
    """
    if len(samples) < 2:
        return None

    # Locate the nadir (first occurrence of the minimum value).
    nadir_idx = 0
    nadir_v = samples[0][1]
    for i in range(1, len(samples)):
        if samples[i][1] < nadir_v:
            nadir_v = samples[i][1]
            nadir_idx = i

    # Nadir at/after the last sample => no recovery segment.
    if nadir_idx >= len(samples) - 1:
        return None

    nadir_t = samples[nadir_idx][0]
    post = samples[nadir_idx:]  # include the nadir as the segment origin
    n_post_points = len(post) - 1  # points strictly after the nadir

    if n_post_points < 3:
        # Two-point fallback: (last - nadir) / (t_last - t_nadir).
        t_last, v_last = post[-1]
        span_s = t_last - nadir_t
        if span_s <= 0:
            return None
        slope_per_s = (v_last - nadir_v) / span_s
        return round(slope_per_s * 3600.0, 6)

    # OLS slope over the recovery segment (nadir included as origin).
    xs = [t for t, _ in post]
    ys = [v for _, v in post]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    slope_per_s = sxy / sxx
    return round(slope_per_s * 3600.0, 6)


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all thermoregulation biomarkers.

    Downloads the body-temperature track per case (cached).  When the track is
    absent or has < MIN_USABLE_SAMPLES gated samples, thermo_available = 0 and
    every other feature is None.  stdlib only.
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float  # noqa: F401  (contract import)

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["thermo_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        # ---- Body-temperature track -----------------------------------------
        _bt_name, raw_bt = first_available(cfg, cid_str, BT_TRACK_CANDIDATES)
        if not raw_bt:
            out[cid_str] = dict(none_row)
            continue

        bt_samples = _clip_to_window(raw_bt, t_start, t_end)
        bt_samples = _filter_physiologic(bt_samples, TEMP_MIN, TEMP_MAX)
        if len(bt_samples) < MIN_USABLE_SAMPLES:
            out[cid_str] = dict(none_row)
            continue

        row: dict[str, Any] = dict(none_row)
        row["thermo_available"] = 1
        row["thermo_min_temp"] = _min_gated(bt_samples)
        row["thermo_mean_temp"] = _time_weighted_mean(bt_samples)
        row["thermo_hypothermia_frac"] = _frac_time_below(bt_samples, NORMO_THR)
        row["thermo_hypothermia_auc"] = _auc_below(bt_samples, NORMO_THR)
        row["thermo_temp_variability"] = _sd(bt_samples)
        row["thermo_rewarming_rate"] = _rewarming_rate(bt_samples)

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.thermoregulation
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

    print(f"Thermoregulation validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case thermoregulation summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
