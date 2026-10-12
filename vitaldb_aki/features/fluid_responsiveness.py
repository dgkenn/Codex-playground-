"""fluid_responsiveness.py -- Advanced-hemodynamic-monitor fluid/vasoplegia biomarkers.

This module complements the PFDS thesis ("Pressure is not perfusion") with the
extra signal carried by cardiac-output monitors (EV1000 / Vigileo / Vigilance /
CardioQ).  Those devices report quantities a MAP trace alone cannot reveal:

  * SVV (stroke volume variation, %)  -- dynamic preload responsiveness.  A high
        SVV means the circulation is under-filled (occult hypovolemia): even with
        an "adequate" MAP, an under-filled heart under-perfuses organs and a fluid
        bolus would raise stroke volume.  SVV > 13 % is the classic
        fluid-responsive threshold.
  * SVR / SVRI (systemic vascular resistance) -- afterload / vasomotor tone.  A
        low SVR (< 800 dyn*s*cm^-5) is vasoplegia: the vasculature is pathologically
        dilated and pressure is maintained, if at all, only with pressors while
        tissue perfusion suffers.
  * CO / CI (cardiac output / cardiac index) -- the flow itself.  Low output means
        global hypoperfusion regardless of pressure.

MECHANISM (the AKI link): a fluid-responsive (under-filled) OR vasoplegic
circulation under-perfuses the kidney even when MAP looks fine -- exactly the
occult-hypoperfusion mechanism PFDS operationalises from pressure surrogates,
here measured directly off a cardiac-output monitor.

TIER -- WHY ALL "pk":
Only ~600-900 VitalDB cases carry an EV1000/Vigileo/Vigilance/CardioQ monitor, so
`fluid_available == 1` only on that advanced-hemodynamics subgroup.  Because the
whole family is confined to that subgroup, every spec is fset="pk" (the
PK / best-instrumented tier), parallel to the waveform-only PFDS variants.

LEAKAGE (Sec 11):
All features are timing="intraop".  The prediction cutoff is `opend`; no sample
at t > opend is ever used.  `_intraop_window` is copied verbatim from pfds.py and
`audit_specs(SPECS)` enforces the no-postop firewall at import.

MISSINGNESS:
If neither an SVV nor a CO track is usable, `fluid_available = 0` and ALL other
features are None (NOT 0).  Sub-features whose specific track is absent (e.g. no
SVR track) are individually None even when the monitor is otherwise present.

TRACK PRIORITIES (NUMERIC monitor channels; first_available across brands):
  SVV:  EV1000/SVV -> Vigileo/SVV
  SVR:  EV1000/SVR -> EV1000/SVRI
  CO:   EV1000/CO  -> Vigileo/CO  -> Vigilance/CO  -> CardioQ/CO
  CI:   EV1000/CI  -> Vigileo/CI  -> Vigilance/CI  -> CardioQ/CI

CONSTANTS (all binding; pre-registered):
  SVV_RESPONSIVE_THR = 13  %                     -- fluid-responsive / occult-hypovolemia
  SVR_VASOPLEGIA_THR = 800 dyn*s*cm^-5           -- vasoplegia threshold

Physiologic gates (artifact rejection):
  SVV 0-50 %, SVR 100-4000 dyn*s*cm^-5, CO 1-15 L/min, CI 0.5-8.
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range constants (binding; artifact gates)
# ---------------------------------------------------------------------------
SVV_MIN: float = 0.0       # % -- stroke volume variation
SVV_MAX: float = 50.0      # % -- ceiling above which it's artifact
SVR_MIN: float = 100.0     # dyn*s*cm^-5 -- below this is non-physiologic
SVR_MAX: float = 4000.0    # dyn*s*cm^-5 -- artifact ceiling
CO_MIN: float = 1.0        # L/min
CO_MAX: float = 15.0       # L/min
CI_MIN: float = 0.5        # L/min/m^2
CI_MAX: float = 8.0        # L/min/m^2

# Threshold / parameter constants (pre-registered)
SVV_RESPONSIVE_THR: float = 13.0    # % -- fluid-responsive / occult hypovolemia
SVR_VASOPLEGIA_THR: float = 800.0   # dyn*s*cm^-5 -- vasoplegia threshold
MAX_INTER_SAMPLE_DT_S: float = 10.0  # s -- gap cap (shared with hemodynamics/pfds)

# Track priorities (binding; NUMERIC monitor channels)
SVV_TRACK_CANDIDATES: list[str] = [
    "EV1000/SVV",
    "Vigileo/SVV",
]
SVR_TRACK_CANDIDATES: list[str] = [
    "EV1000/SVR",
    "EV1000/SVRI",
]
CO_TRACK_CANDIDATES: list[str] = [
    "EV1000/CO",
    "Vigileo/CO",
    "Vigilance/CO",
    "CardioQ/CO",
]
CI_TRACK_CANDIDATES: list[str] = [
    "EV1000/CI",
    "Vigileo/CI",
    "Vigilance/CI",
    "CardioQ/CI",
]

# ---------------------------------------------------------------------------
# Feature specs (Sec 9; all fset="pk" -- advanced-hemodynamics subgroup only;
# all timing="intraop" -- leakage firewall Sec 11)
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability (FIRST spec) -----------------------------------------
    FeatureSpec(
        "fluid_available", "pk", "intraop",
        "1 if an SVV or CO cardiac-output-monitor track is usable, else 0",
    ),
    # ---- occult hypovolemia (stroke volume variation) ----------------------
    FeatureSpec(
        "fluid_svv_mean", "pk", "intraop",
        "Time-weighted mean stroke volume variation (%); higher = under-filled "
        "fluid-responsive circulation (occult hypovolemia)",
    ),
    FeatureSpec(
        "fluid_svv_max", "pk", "intraop",
        "Maximum gated SVV (%) -- peak fluid responsiveness",
    ),
    FeatureSpec(
        "fluid_svv_high_frac", "pk", "intraop",
        "Fraction of intraop time with SVV > 13 % (occult-hypovolemia / "
        "fluid-responsive burden)",
    ),
    # ---- vasoplegia (systemic vascular resistance) -------------------------
    FeatureSpec(
        "fluid_svr_mean", "pk", "intraop",
        "Time-weighted mean systemic vascular resistance (dyn*s*cm^-5); "
        "None if no SVR/SVRI track",
    ),
    FeatureSpec(
        "fluid_svr_min", "pk", "intraop",
        "Minimum gated SVR -- depth of vasoplegia; None if no SVR/SVRI track",
    ),
    FeatureSpec(
        "fluid_svr_low_frac", "pk", "intraop",
        "Fraction of intraop time with SVR < 800 dyn*s*cm^-5 (vasoplegia "
        "burden); None if no SVR/SVRI track",
    ),
    # ---- low cardiac output ------------------------------------------------
    FeatureSpec(
        "fluid_co_mean", "pk", "intraop",
        "Time-weighted mean cardiac output (L/min); None if no CO track",
    ),
    FeatureSpec(
        "fluid_ci_min", "pk", "intraop",
        "Minimum gated cardiac index (L/min/m^2) -- low-output depth; "
        "None if no CI track",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Low-level helpers (pure; no I/O; unit-testable on synthetic series)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds.py so the leakage window is identical across
    modules; t_end (opend) is the hard prediction cutoff.
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
    """Forward-dt time-weighted mean (mirrors hemodynamics/pfds._time_weighted_mean)."""
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


def _frac_time_above(
    samples: list[tuple[float, float]],
    thr: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Forward-dt time-weighted fraction of recording with value > thr.

    Returns None if < 2 samples (no interval to weight).  Returns 0.0 if no
    sample exceeds thr.  The strict inequality matches the clinical threshold
    convention (SVV > 13 % = fluid-responsive).
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
        if samples[i][1] > thr:
            above += dt
    if total <= 0:
        return None
    return round(above / total, 6)


def _frac_time_below(
    samples: list[tuple[float, float]],
    thr: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Forward-dt time-weighted fraction of recording with value < thr.

    Returns None if < 2 samples.  Returns 0.0 if no sample is below thr.  The
    strict inequality matches the vasoplegia convention (SVR < 800).
    """
    if len(samples) < 2:
        return None
    total = 0.0
    below = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        total += dt
        if samples[i][1] < thr:
            below += dt
    if total <= 0:
        return None
    return round(below / total, 6)


def _min_gated(samples: list[tuple[float, float]]) -> float | None:
    """Minimum value over the (already range-gated) samples.

    Returns None when the series is empty.  Used for vasoplegia depth (min SVR)
    and low-output depth (min CI); a single sample is enough for a minimum.
    """
    if not samples:
        return None
    return min(v for _, v in samples)


def _max_gated(samples: list[tuple[float, float]]) -> float | None:
    """Maximum value over the (already range-gated) samples.

    Returns None when the series is empty.  Used for peak fluid responsiveness
    (max SVV).
    """
    if not samples:
        return None
    return max(v for _, v in samples)


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all fluid-responsiveness biomarkers.

    Downloads numeric monitor tracks per case (cached).  When neither an SVV nor
    a CO track is usable, `fluid_available = 0` and every other feature is None
    (NOT 0).  Sub-features whose specific track is absent are individually None.
    """
    from vitaldb_aki.data.tracks import download_track, first_available  # noqa: F401
    from vitaldb_aki.data.client import to_float  # noqa: F401

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["fluid_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        # ---- SVV track -------------------------------------------------------
        _svv_name, raw_svv = first_available(cfg, cid_str, SVV_TRACK_CANDIDATES)
        svv_samples: list[tuple[float, float]] = []
        if raw_svv:
            svv_samples = _clip_to_window(raw_svv, t_start, t_end)
            svv_samples = _filter_physiologic(svv_samples, SVV_MIN, SVV_MAX)

        # ---- CO track --------------------------------------------------------
        _co_name, raw_co = first_available(cfg, cid_str, CO_TRACK_CANDIDATES)
        co_samples: list[tuple[float, float]] = []
        if raw_co:
            co_samples = _clip_to_window(raw_co, t_start, t_end)
            co_samples = _filter_physiologic(co_samples, CO_MIN, CO_MAX)

        # ---- availability gate: need SVV or CO -------------------------------
        if not svv_samples and not co_samples:
            row = dict(none_row)
            row["fluid_available"] = 0
            out[cid_str] = row
            continue

        row: dict[str, Any] = dict(none_row)
        row["fluid_available"] = 1

        # ---- SVR / SVRI track ------------------------------------------------
        _svr_name, raw_svr = first_available(cfg, cid_str, SVR_TRACK_CANDIDATES)
        svr_samples: list[tuple[float, float]] = []
        if raw_svr:
            svr_samples = _clip_to_window(raw_svr, t_start, t_end)
            svr_samples = _filter_physiologic(svr_samples, SVR_MIN, SVR_MAX)

        # ---- CI track --------------------------------------------------------
        _ci_name, raw_ci = first_available(cfg, cid_str, CI_TRACK_CANDIDATES)
        ci_samples: list[tuple[float, float]] = []
        if raw_ci:
            ci_samples = _clip_to_window(raw_ci, t_start, t_end)
            ci_samples = _filter_physiologic(ci_samples, CI_MIN, CI_MAX)

        # ======================================================================
        # Compute biomarkers
        # ======================================================================

        # Occult hypovolemia (SVV)
        if svv_samples:
            row["fluid_svv_mean"] = _round(_time_weighted_mean(svv_samples))
            row["fluid_svv_max"] = _round(_max_gated(svv_samples))
            row["fluid_svv_high_frac"] = _frac_time_above(svv_samples, SVV_RESPONSIVE_THR)

        # Vasoplegia (SVR)
        if svr_samples:
            row["fluid_svr_mean"] = _round(_time_weighted_mean(svr_samples))
            row["fluid_svr_min"] = _round(_min_gated(svr_samples))
            row["fluid_svr_low_frac"] = _frac_time_below(svr_samples, SVR_VASOPLEGIA_THR)

        # Low cardiac output (CO / CI)
        if co_samples:
            row["fluid_co_mean"] = _round(_time_weighted_mean(co_samples))
        if ci_samples:
            row["fluid_ci_min"] = _round(_min_gated(ci_samples))

        out[cid_str] = row

    return out


def _round(v: float | None, ndigits: int = 6) -> float | None:
    """Round a value, passing None through unchanged."""
    return None if v is None else round(v, ndigits)


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.fluid_responsiveness
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
            if len(cohort_ids) >= 50:
                break

    print(f"fluid_responsiveness validation on {len(cohort_ids)} cases")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [
        "fluid_available",
        "fluid_svv_mean",
        "fluid_svv_max",
        "fluid_svv_high_frac",
        "fluid_svr_mean",
        "fluid_svr_min",
        "fluid_svr_low_frac",
        "fluid_co_mean",
        "fluid_ci_min",
    ]
    n_available = sum(1 for r in result.values() if r.get("fluid_available") == 1)
    print(f"\nfluid_available=1 on {n_available}/{len(cohort_ids)} cases "
          "(advanced-hemodynamics subgroup; ~600-900 cases cohort-wide)")
    print("\nPer-case fluid-responsiveness summary (monitored cases only):")
    for cid in cohort_ids:
        r = result.get(cid, {})
        if r.get("fluid_available") != 1:
            continue
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
