"""ventilation.py -- Ventilator-Induced Lung Injury (VILI) biomarker family.

The mining thesis: **The ventilator is an organ-injury vector.** Mechanical
ventilation that is locally injurious to the lung (high driving pressure, high
mechanical power, progressive derecruitment) drives a systemic inflammatory
response (biotrauma) that propagates to distal organs -- including the kidney.
The intraoperative-ventilation -> systemic-inflammation -> end-organ-injury
axis is currently UNMINED in the VitalDB-AKI study; this module operationalises
it from the routinely-logged ventilator numeric tracks.

BIOMARKERS (all fset="comprehensive")
-------------------------------------
1. ventilation_available -- 1 if PPLAT and PEEP are both usable, else 0.

2. Driving pressure (dP = PPLAT - PEEP); the single best-validated VILI metric.
   vent_driving_pressure_mean       -- time-weighted mean dP
   vent_driving_pressure_max        -- max dP over the case
   vent_driving_pressure_high_frac  -- fraction of intraop time with dP >= 15
                                       cmH2O (the injurious threshold)

3. Mechanical power (Gattinoni simplified, J/min):
   vent_mech_power  -- time-weighted mean of
                       0.098 * RR * TV_L * (PIP - 0.5*(PPLAT - PEEP)),
                       TV_L = TV/1000. None if any of RR/TV/PIP/PPLAT/PEEP absent.

4. Dynamic compliance:
   vent_compliance_mean    -- time-weighted mean dynamic compliance
   vent_compliance_decline -- relative fall from the first-300s baseline median
                              to the last-300s median ((baseline - late)/baseline,
                              clamped to 0..1); captures progressive derecruitment.
                              None if no baseline or < 2 epochs.

5. PEEP:
   vent_peep_mean -- time-weighted mean PEEP.

UNITS
-----
Airway-pressure tracks differ by device: the Primus tracks are in mbar, the
Solar8000 tracks in cmH2O.  1 mbar = 1.0197 cmH2O, i.e. ~1.02% apart -- well
within ventilator measurement noise -- so we treat mbar and cmH2O as
INTERCHANGEABLE and do not convert.  All pressure thresholds below are stated in
cmH2O and applied directly to whichever unit the device reports.

LEAKAGE
-------
All features are timing="intraop".  The prediction cutoff is opend.  No sample
at t > opend is ever used.  audit_specs() enforces this at import (Sec 11).

MISSINGNESS
-----------
If PPLAT or PEEP is absent (no usable driving-pressure inputs), ALL features are
None except ventilation_available, which is 0.  Individual derived features are
None when THEIR specific inputs are absent (e.g. vent_mech_power is None unless
RR, TV and PIP are all present in addition to PPLAT/PEEP).

TRACK PRIORITIES (first_available across device variants; all NUMERIC)
  PPLAT:      Primus/PPLAT_MBAR -> Solar8000/VENT_PPLAT
  PEEP:       Primus/PEEP_MBAR  -> Solar8000/VENT_MEAS_PEEP
  PIP:        Primus/PIP_MBAR   -> Solar8000/VENT_PIP
  COMPLIANCE: Primus/COMPLIANCE -> Solar8000/VENT_COMPL
  TV:         Primus/TV         -> Solar8000/VENT_TV
  RR:         Solar8000/VENT_RR -> Primus/RR_CO2 -> Solar8000/RR_CO2

Protocol reference: Sec 7F-novel (unmined VILI axis).
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range constants (binding; pre-registered artifact gates).
# Pressures are in cmH2O (== mbar, treated interchangeably; see module docstring).
# Samples outside [min, max] are dropped before any statistic is computed.
# ---------------------------------------------------------------------------
PEEP_MIN: float = 0.0       # cmH2O
PEEP_MAX: float = 25.0      # cmH2O
PPLAT_MIN: float = 5.0      # cmH2O
PPLAT_MAX: float = 60.0     # cmH2O
PIP_MIN: float = 5.0        # cmH2O
PIP_MAX: float = 80.0       # cmH2O
TV_MIN: float = 50.0        # mL
TV_MAX: float = 2000.0      # mL
RR_MIN: float = 4.0         # breaths/min
RR_MAX: float = 60.0        # breaths/min
COMPLIANCE_MIN: float = 5.0     # mL/cmH2O
COMPLIANCE_MAX: float = 200.0   # mL/cmH2O

# ---------------------------------------------------------------------------
# Threshold / parameter constants (pre-registered).
# ---------------------------------------------------------------------------
DRIVING_PRESSURE_HIGH_THR: float = 15.0  # cmH2O -- "injurious" driving pressure
MECH_POWER_COEF: float = 0.098           # Gattinoni simplified MP coefficient
BASELINE_WINDOW_S: float = 300.0         # s -- first-/last-300s epochs for decline
MAX_INTER_SAMPLE_DT_S: float = 10.0      # s -- gap cap (shared convention)
LAST_VAL_LOOKBACK_S: float = 10.0        # s -- last-value-hold lookback for alignment

# ---------------------------------------------------------------------------
# Track priorities (binding; all NUMERIC, small/fast).
# ---------------------------------------------------------------------------
PPLAT_TRACK_CANDIDATES: list[str] = ["Primus/PPLAT_MBAR", "Solar8000/VENT_PPLAT"]
PEEP_TRACK_CANDIDATES: list[str] = ["Primus/PEEP_MBAR", "Solar8000/VENT_MEAS_PEEP"]
PIP_TRACK_CANDIDATES: list[str] = ["Primus/PIP_MBAR", "Solar8000/VENT_PIP"]
COMPLIANCE_TRACK_CANDIDATES: list[str] = ["Primus/COMPLIANCE", "Solar8000/VENT_COMPL"]
TV_TRACK_CANDIDATES: list[str] = ["Primus/TV", "Solar8000/VENT_TV"]
RR_TRACK_CANDIDATES: list[str] = ["Solar8000/VENT_RR", "Primus/RR_CO2", "Solar8000/RR_CO2"]

# ---------------------------------------------------------------------------
# Feature specs (Sec 9 nested design; all "intraop" -- leakage firewall Sec 11).
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability -------------------------------------------------------
    FeatureSpec(
        "ventilation_available", "comprehensive", "intraop",
        "1 if PPLAT and PEEP tracks are both usable for VILI computation, else 0",
    ),
    # ---- driving pressure ---------------------------------------------------
    FeatureSpec(
        "vent_driving_pressure_mean", "comprehensive", "intraop",
        "Time-weighted mean driving pressure (PPLAT - PEEP, cmH2O); the core "
        "VILI metric. PEEP aligned to the PPLAT time grid by last-value-hold",
    ),
    FeatureSpec(
        "vent_driving_pressure_max", "comprehensive", "intraop",
        "Maximum driving pressure (PPLAT - PEEP, cmH2O) over the intraop window",
    ),
    FeatureSpec(
        "vent_driving_pressure_high_frac", "comprehensive", "intraop",
        "Fraction of intraop time with driving pressure >= 15 cmH2O "
        "(injurious-dP threshold)",
    ),
    # ---- mechanical power ---------------------------------------------------
    FeatureSpec(
        "vent_mech_power", "comprehensive", "intraop",
        "Time-weighted mean mechanical power (Gattinoni simplified, J/min): "
        "0.098 * RR * TV_L * (PIP - 0.5*(PPLAT - PEEP)), TV_L=TV/1000. "
        "None unless RR, TV, PIP, PPLAT and PEEP are all present",
    ),
    # ---- compliance ---------------------------------------------------------
    FeatureSpec(
        "vent_compliance_mean", "comprehensive", "intraop",
        "Time-weighted mean dynamic compliance (mL/cmH2O)",
    ),
    FeatureSpec(
        "vent_compliance_decline", "comprehensive", "intraop",
        "Relative fall in dynamic compliance from the first-300s baseline median "
        "to the last-300s median ((baseline - late)/baseline, clamped 0..1); "
        "captures progressive derecruitment. None if no baseline or < 2 epochs",
    ),
    # ---- PEEP ---------------------------------------------------------------
    FeatureSpec(
        "vent_peep_mean", "comprehensive", "intraop",
        "Time-weighted mean PEEP (cmH2O)",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Low-level helpers (pure; no I/O; unit-testable on synthetic series)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    t_end == opend is the leakage cutoff: no sample at t > opend may be used.
    (Copied verbatim from pfds._intraop_window to keep the cutoff identical.)
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


def _last_val(
    sorted_s: list[tuple[float, float]],
    t: float,
    lookback_s: float = LAST_VAL_LOOKBACK_S,
) -> float | None:
    """Binary-search last-value hold: most recent value at or before t.

    Returns None if there is no sample at or before t, or the nearest preceding
    sample is more than `lookback_s` old (stale -> treated as missing).
    `sorted_s` MUST be sorted ascending by time.
    """
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
    if t - st > lookback_s:
        return None
    return sv


def driving_pressure_series(
    pplat_samples: list[tuple[float, float]],
    peep_samples: list[tuple[float, float]],
    lookback_s: float = LAST_VAL_LOOKBACK_S,
) -> list[tuple[float, float]]:
    """Build the driving-pressure series (PPLAT - PEEP) on the PPLAT time grid.

    PEEP is aligned to each PPLAT timestamp by last-value-hold (most recent PEEP
    at or before the PPLAT time, within `lookback_s`).  A PPLAT sample with no
    aligned PEEP (none within lookback) is skipped.

    Returns [(t, dP), ...].  Empty if PPLAT is empty or no sample aligns.
    """
    if not pplat_samples:
        return []
    peep_sorted = sorted(peep_samples, key=lambda x: x[0])
    if not peep_sorted:
        return []
    out: list[tuple[float, float]] = []
    for t, pplat_v in pplat_samples:
        peep_v = _last_val(peep_sorted, t, lookback_s)
        if peep_v is None:
            continue
        out.append((t, pplat_v - peep_v))
    return out


def series_max(samples: list[tuple[float, float]]) -> float | None:
    """Maximum value of a (t, v) series, or None if empty."""
    if not samples:
        return None
    return max(v for _, v in samples)


def fraction_above(
    samples: list[tuple[float, float]],
    threshold: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Time-weighted fraction of the series with value >= threshold (forward-dt).

    Returns None if < 2 samples (no interval to weight).  Returns 0.0 if no
    sample is at/above the threshold but intervals exist.
    """
    if len(samples) < 2:
        return None
    total = 0.0
    above = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        total += dt
        if samples[i][1] >= threshold:
            above += dt
    if total <= 0:
        return None
    return round(above / total, 6)


def mech_power_series(
    pplat_samples: list[tuple[float, float]],
    peep_samples: list[tuple[float, float]],
    pip_samples: list[tuple[float, float]],
    tv_samples: list[tuple[float, float]],
    rr_samples: list[tuple[float, float]],
    coef: float = MECH_POWER_COEF,
    lookback_s: float = LAST_VAL_LOOKBACK_S,
) -> list[tuple[float, float]]:
    """Build the mechanical-power series (J/min) on the PPLAT time grid.

    Gattinoni simplified per-breath power integrated to a rate:

        MP = coef * RR * TV_L * (PIP - 0.5*(PPLAT - PEEP)),  TV_L = TV/1000

    PEEP, PIP, TV and RR are each aligned to the PPLAT timestamp by
    last-value-hold (within `lookback_s`).  A PPLAT sample is skipped unless ALL
    four co-inputs align.  Returns [(t, MP), ...]; empty if any track is empty or
    nothing aligns.
    """
    if not pplat_samples:
        return []
    peep_sorted = sorted(peep_samples, key=lambda x: x[0])
    pip_sorted = sorted(pip_samples, key=lambda x: x[0])
    tv_sorted = sorted(tv_samples, key=lambda x: x[0])
    rr_sorted = sorted(rr_samples, key=lambda x: x[0])
    if not (peep_sorted and pip_sorted and tv_sorted and rr_sorted):
        return []
    out: list[tuple[float, float]] = []
    for t, pplat_v in pplat_samples:
        peep_v = _last_val(peep_sorted, t, lookback_s)
        pip_v = _last_val(pip_sorted, t, lookback_s)
        tv_v = _last_val(tv_sorted, t, lookback_s)
        rr_v = _last_val(rr_sorted, t, lookback_s)
        if peep_v is None or pip_v is None or tv_v is None or rr_v is None:
            continue
        tv_l = tv_v / 1000.0
        driving = pplat_v - peep_v
        mp = coef * rr_v * tv_l * (pip_v - 0.5 * driving)
        out.append((t, mp))
    return out


def _epoch_median(
    samples: list[tuple[float, float]],
    t_lo: float,
    t_hi: float,
) -> float | None:
    """Median of values with t in [t_lo, t_hi].  None if no sample in window."""
    vals = [v for t, v in samples if t_lo <= t <= t_hi]
    if not vals:
        return None
    sv = sorted(vals)
    n = len(sv)
    mid = n // 2
    return sv[mid] if n % 2 == 1 else (sv[mid - 1] + sv[mid]) / 2.0


def compliance_decline(
    compliance_samples: list[tuple[float, float]],
    window_s: float = BASELINE_WINDOW_S,
) -> float | None:
    """Relative compliance fall from a first-window baseline to a last-window late.

    baseline = median of compliance in the first `window_s` of the series.
    late     = median of compliance in the last  `window_s` of the series.
    decline  = (baseline - late) / baseline, clamped to [0, 1].

    A positive value means compliance fell (progressive derecruitment).  The
    clamp drops negative values (compliance improved) to 0.0.

    Returns None if:
      * fewer than 2 samples (no two epochs to compare), or
      * the series spans less than `window_s` total (baseline and late windows
        would overlap -- not two distinct epochs), or
      * no baseline value, or baseline <= 0.
    """
    if len(compliance_samples) < 2:
        return None
    sorted_s = sorted(compliance_samples, key=lambda x: x[0])
    t0 = sorted_s[0][0]
    t_end = sorted_s[-1][0]
    if t_end - t0 < window_s:
        return None  # only one epoch's worth of data -- decline undefined
    baseline = _epoch_median(sorted_s, t0, t0 + window_s)
    late = _epoch_median(sorted_s, t_end - window_s, t_end)
    if baseline is None or baseline <= 0 or late is None:
        return None
    decline = (baseline - late) / baseline
    if decline < 0.0:
        decline = 0.0
    elif decline > 1.0:
        decline = 1.0
    return round(decline, 6)


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all ventilation biomarkers.

    Downloads the numeric ventilator tracks per case (cached).  If PPLAT or PEEP
    is absent, ventilation_available=0 and every other feature is None.  Derived
    features that need extra tracks (mech power needs PIP/TV/RR; compliance needs
    its own track) are None when those tracks are absent.

    stdlib only; no heavy deps.
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float  # noqa: F401 (kept for parity/parsing)

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["ventilation_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        def _load(candidates: list[str], vmin: float, vmax: float) -> list[tuple[float, float]]:
            _name, raw = first_available(cfg, cid_str, candidates)
            if not raw:
                return []
            samples = _clip_to_window(raw, t_start, t_end)
            return _filter_physiologic(samples, vmin, vmax)

        # ---- required tracks: PPLAT + PEEP ----------------------------------
        pplat_samples = _load(PPLAT_TRACK_CANDIDATES, PPLAT_MIN, PPLAT_MAX)
        peep_samples = _load(PEEP_TRACK_CANDIDATES, PEEP_MIN, PEEP_MAX)

        if len(pplat_samples) < 2 or len(peep_samples) < 1:
            # No usable driving-pressure inputs -> unavailable, all-None.
            row = dict(none_row)
            row["ventilation_available"] = 0
            out[cid_str] = row
            continue

        row: dict[str, Any] = dict(none_row)
        row["ventilation_available"] = 1

        # ---- driving pressure -----------------------------------------------
        dp_series = driving_pressure_series(pplat_samples, peep_samples)
        row["vent_driving_pressure_mean"] = _time_weighted_mean(dp_series)
        row["vent_driving_pressure_max"] = series_max(dp_series)
        row["vent_driving_pressure_high_frac"] = fraction_above(
            dp_series, DRIVING_PRESSURE_HIGH_THR
        )

        # ---- PEEP -----------------------------------------------------------
        row["vent_peep_mean"] = _time_weighted_mean(peep_samples)

        # ---- compliance -----------------------------------------------------
        comp_samples = _load(COMPLIANCE_TRACK_CANDIDATES, COMPLIANCE_MIN, COMPLIANCE_MAX)
        if comp_samples:
            row["vent_compliance_mean"] = _time_weighted_mean(comp_samples)
            row["vent_compliance_decline"] = compliance_decline(comp_samples)

        # ---- mechanical power (needs PIP + TV + RR in addition) -------------
        pip_samples = _load(PIP_TRACK_CANDIDATES, PIP_MIN, PIP_MAX)
        tv_samples = _load(TV_TRACK_CANDIDATES, TV_MIN, TV_MAX)
        rr_samples = _load(RR_TRACK_CANDIDATES, RR_MIN, RR_MAX)
        if pip_samples and tv_samples and rr_samples:
            mp_series = mech_power_series(
                pplat_samples, peep_samples, pip_samples, tv_samples, rr_samples
            )
            row["vent_mech_power"] = _time_weighted_mean(mp_series)

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.ventilation
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

    print(f"Ventilation validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case ventilation summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
