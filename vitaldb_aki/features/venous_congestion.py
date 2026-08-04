"""venous_congestion.py -- Central Venous Pressure / venous congestion biomarker family.

UNMINED AXIS. The PFDS flagship operationalises the *arterial / low-flow* side of
intraop hypoperfusion ("pressure is not perfusion"). This module operationalises a
mechanistically DISTINCT axis: **renal VENOUS congestion**.

Mechanism
---------
Elevated central venous pressure (CVP) is transmitted backward into the renal vein
and raises renal interstitial / tubular pressure. Because the kidney is encapsulated,
a rise in venous (back) pressure compresses the tubules and lowers the *net*
trans-renal perfusion gradient (MAP - CVP), reducing glomerular filtration **even
when arterial pressure looks adequate**. This is the cardiorenal / "congestive AKI"
pathway -- a major, under-recognised driver of perioperative AKI that is
mechanistically orthogonal to the low-flow hypotension axis PFDS already mines.

A patient can have MAP >=65 the entire case (low PFDS burden) yet sit at CVP 16 mmHg
from right-heart failure / volume overload -- and still injure the kidney. CVP is the
direct, invasively-monitored readout of that congestion.

BIOMARKERS (all fset="comprehensive"; None if CVP track absent)
---------------------------------------------------------------
  vcong_available            -- 1 if CVP track usable (>=10 physiologic samples) else 0
  vcong_cvp_mean             -- time-weighted mean CVP (mmHg)
  vcong_cvp_max              -- peak CVP among physiologic-gated samples (mmHg)
  vcong_cvp_above12_frac     -- fraction of intraop time with CVP > 12 mmHg (congestion)
  vcong_cvp_above8_frac      -- fraction of intraop time with CVP > 8 mmHg (mild)
  vcong_cvp_auc_above12      -- time-integral of (CVP - 12) over CVP>12 intervals,
                                gaps capped at 10 s, in mmHg*minutes

LEAKAGE
-------
All features are timing="intraop". The prediction cutoff is opend. No sample at
t > opend is ever used (_clip_to_window). audit_specs() enforces this at import (§11).

MISSINGNESS
-----------
Only ~1600 of the ~4337 cohort cases carry ANY CVP track (CVP requires a central
line, an invasive-monitoring decision driven by case acuity). When CVP is absent --
or has < 10 usable physiologic samples -- vcong_available = 0 and EVERY other feature
is None (NOT 0). So MOST cases will be vcong_available=0 / None. This is EXPECTED and
CORRECT: the module characterises an invasive-monitoring subgroup, and that
selectivity must be modelled downstream (do not impute 0 for missing CVP).

Track priority (binding)
  CVP: Solar8000/CVP -> SNUADC/CVP   (both numeric, mmHg)

CONSTANTS (all binding; pre-registered)
  CVP_MIN              = -5.0  mmHg  -- artifact gate (drop below)
  CVP_MAX              = 40.0  mmHg  -- artifact gate (drop above)
  CVP_CONGESTION_THR   = 12.0  mmHg  -- frank venous congestion threshold
  CVP_MILD_THR         =  8.0  mmHg  -- mild elevation threshold
  MIN_USABLE_SAMPLES   = 10          -- minimum physiologic samples to be "usable"
  MAX_INTER_SAMPLE_DT_S = 10.0 s     -- gap cap (shared convention with pfds)

Protocol reference: §7F-novel (venous congestion axis), §STRATEGY_PFDS.md.
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range / threshold constants (binding; pre-registered)
# ---------------------------------------------------------------------------
CVP_MIN: float = -5.0       # mmHg -- artifact gate (drop below)
CVP_MAX: float = 40.0       # mmHg -- artifact gate (drop above)
CVP_CONGESTION_THR: float = 12.0   # mmHg -- frank venous congestion
CVP_MILD_THR: float = 8.0          # mmHg -- mild elevation
MIN_USABLE_SAMPLES: int = 10       # minimum physiologic samples to be "usable"
MAX_INTER_SAMPLE_DT_S: float = 10.0  # s -- gap cap (shared with pfds/hemodynamics)

# Track priority (binding); both numeric tracks in mmHg.
CVP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/CVP",
    "SNUADC/CVP",
]

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11)
# vcong_available MUST be first (availability flag).
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "vcong_available", "comprehensive", "intraop",
        "1 if CVP track usable (>=10 physiologic samples) for venous-congestion "
        "computation, else 0; flags the invasive-monitoring subgroup",
    ),
    FeatureSpec(
        "vcong_cvp_mean", "comprehensive", "intraop",
        "Time-weighted mean central venous pressure (mmHg) over the intraop "
        "window; higher = sustained venous congestion / renal back-pressure",
    ),
    FeatureSpec(
        "vcong_cvp_max", "comprehensive", "intraop",
        "Peak CVP (mmHg) among physiologic-gated samples; captures transient "
        "congestion spikes (e.g. clamp/positioning/volume bolus)",
    ),
    FeatureSpec(
        "vcong_cvp_above12_frac", "comprehensive", "intraop",
        "Fraction of intraop time with CVP > 12 mmHg -- frank venous-congestion "
        "burden (renal interstitial/tubular pressure likely elevated)",
    ),
    FeatureSpec(
        "vcong_cvp_above8_frac", "comprehensive", "intraop",
        "Fraction of intraop time with CVP > 8 mmHg -- mild venous-congestion "
        "burden (early back-pressure)",
    ),
    FeatureSpec(
        "vcong_cvp_auc_above12", "comprehensive", "intraop",
        "Time-integral (mmHg*minutes) of (CVP - 12) over intervals where "
        "CVP > 12 mmHg, inter-sample gaps capped at 10 s; dose-time burden of "
        "frank congestion",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Low-level helpers (pure; no I/O; copied/aligned with pfds for consistency)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds._intraop_window to keep the windowing identical
    across feature modules. t_end (opend) is the leakage cutoff.
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


def _frac_time_above(
    samples: list[tuple[float, float]],
    thr: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Fraction of (gap-capped) recording time with value > thr.

    Forward-dt weighting: each interval [t_i, t_{i+1}) is attributed the value at
    t_i, with the interval length capped at max_dt_s. Returns time-above-thr /
    total-time. Returns None if < 2 samples or total recording time is 0.
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


def _auc_above(
    samples: list[tuple[float, float]],
    thr: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Time-integral of (value - thr) over intervals where value > thr.

    Forward-dt weighting: each interval [t_i, t_{i+1}) contributes
    (value_i - thr) * dt when value_i > thr, with dt capped at max_dt_s. The raw
    integral is in mmHg*seconds; this returns mmHg*MINUTES (divide by 60).

    Returns None if < 2 samples. Returns 0.0 if value is never above thr (no
    congestion burden) -- distinct from None (no/insufficient data).
    """
    if len(samples) < 2:
        return None
    acc_s = 0.0  # mmHg*seconds
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        v = samples[i][1]
        if v > thr:
            acc_s += (v - thr) * dt
    return round(acc_s / 60.0, 6)


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all venous-congestion biomarkers.

    Downloads the CVP track per case (cached, first_available over the priority
    list). When CVP is absent OR has < MIN_USABLE_SAMPLES physiologic samples in
    the intraop window, vcong_available=0 and every other feature is None (NOT 0):
    the invasive-monitoring subgroup must be modelled, not imputed.

    stdlib only.
    """
    from vitaldb_aki.data.tracks import download_track, first_available  # noqa: F401
    from vitaldb_aki.data.client import to_float  # noqa: F401  (contract import)

    # Default row: availability flag 0, all biomarkers None.
    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["vcong_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        # ---- CVP track -------------------------------------------------------
        _cvp_tname, raw_cvp = first_available(cfg, cid_str, CVP_TRACK_CANDIDATES)
        if not raw_cvp:
            out[cid_str] = dict(none_row)
            continue

        cvp_samples = _clip_to_window(raw_cvp, t_start, t_end)
        cvp_samples = _filter_physiologic(cvp_samples, CVP_MIN, CVP_MAX)
        if len(cvp_samples) < MIN_USABLE_SAMPLES:
            # CVP present but not usable -> still the missing-data case.
            out[cid_str] = dict(none_row)
            continue

        row: dict[str, Any] = dict(none_row)
        row["vcong_available"] = 1
        row["vcong_cvp_mean"] = _time_weighted_mean(cvp_samples)
        row["vcong_cvp_max"] = round(max(v for _, v in cvp_samples), 6)
        row["vcong_cvp_above12_frac"] = _frac_time_above(cvp_samples, CVP_CONGESTION_THR)
        row["vcong_cvp_above8_frac"] = _frac_time_above(cvp_samples, CVP_MILD_THR)
        row["vcong_cvp_auc_above12"] = _auc_above(cvp_samples, CVP_CONGESTION_THR)

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.venous_congestion
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
            if len(cohort_ids) >= 24:
                break

    print(f"Venous-congestion validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case venous-congestion summary:")
    n_avail = 0
    for cid in cohort_ids:
        r = result.get(cid, {})
        if r.get("vcong_available") == 1:
            n_avail += 1
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")

    print(
        f"\nCVP available in {n_avail}/{len(cohort_ids)} sampled cases "
        f"(expected ~1600/4337 cohort-wide; CVP requires a central line -- "
        f"vcong_available=0 / None for the rest is correct, NOT imputed 0)."
    )
