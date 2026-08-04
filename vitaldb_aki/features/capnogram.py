"""capnogram.py -- End-tidal CO2 dynamics as a respiratory witness of perfusion.

THESIS (extends the PFDS "pressure is not perfusion" story).  At a fixed minute
ventilation, end-tidal CO2 (EtCO2) is governed by how much CO2 the lungs can
clear, which in turn is set by pulmonary blood flow.  A **falling EtCO2 at fixed
ventilation** therefore signals **falling pulmonary blood flow** -- low cardiac
output, rising alveolar dead space, or frank embolism -- i.e. systemic
hypoperfusion.  Where pfds.py uses EtCO2 only as one binary flow-surrogate inside
its PFD burden, this module characterises the **EtCO2 trajectory itself**: its
level, its depth, its decline, its variability, and its time below a
dead-space/hypoperfusion threshold.  This corner of the data is largely UNMINED.

The respiratory witness is mechanistically complementary to the arterial-pressure
witness: a patient whose MAP "looks fine" but whose EtCO2 is quietly declining is
exactly the occult-hypoperfusion phenotype the study hunts for.

BIOMARKERS (all fset="comprehensive"; None when EtCO2 absent)
-------------------------------------------------------------
  capno_available          1 if EtCO2 usable (>=10 gated samples) else 0
  capno_etco2_mean         time-weighted mean EtCO2 (mmHg)
  capno_etco2_min          minimum gated EtCO2 (deepest perfusion/dead-space hit)
  capno_etco2_decline      relative fall from first-300s baseline median to the
                           lowest sustained 300s level: (baseline-min_sustained)
                           /baseline, clamped 0..1; None if no baseline
  capno_etco2_variability  SD of gated EtCO2
  capno_etco2_low_frac     fraction of intraop time with EtCO2 < 30 mmHg

DEFERRED RAW TIER (fset="pk"; None/0 by default, behind a cfg flag)
-------------------------------------------------------------------
  capno_phase3_slope_available   placeholder availability flag (=0) for the raw
                           per-breath capnogram morphology metric.  The raw
                           waveform is "Primus/CO2"; it is NEVER downloaded on
                           the default path (heavy, ~per-breath samples).  When
                           features.capnogram_waveform is true AND the track is
                           present in the tid index (checked WITHOUT a heavy
                           fetch), the flag may be set; the actual phase-III
                           alveolar-plateau slope (a V/Q-mismatch marker) is a
                           documented NotImplemented stub -- see
                           _phase3_slope_stub().

LEAKAGE
-------
All features are timing="intraop".  Window is [t_start, opend]; no sample at
t > opend is ever used.  audit_specs() enforces no postop timing at import (§11).

MISSINGNESS
-----------
If no usable EtCO2 track is present, capno_available=0 and ALL other features
are None (NOT 0).

TRACK PRIORITIES (binding)
  EtCO2 (numeric): Solar8000/ETCO2 -> Primus/ETCO2   (mmHg)
  RR    (numeric): Solar8000/RR_CO2 -> Primus/RR_CO2  (optional; reserved)
  Raw   (waveform): Primus/CO2  (DEFERRED; never on default path)

Protocol reference: §7F-novel (PFDS respiratory witness extension).
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range constants (binding; artifact gate)
# ---------------------------------------------------------------------------
ETCO2_MIN: float = 5.0     # mmHg -- non-zero ventilated patient
ETCO2_MAX: float = 70.0    # mmHg -- physiologic ceiling

# Threshold / parameter constants (pre-registered)
ETCO2_LOW_THR: float = 30.0          # mmHg -- dead-space/hypoperfusion threshold
BASELINE_WINDOW_S: float = 300.0     # s -- first-5-min baseline window
SUSTAINED_WINDOW_S: float = 300.0    # s -- contiguous window for "sustained" min
MIN_USABLE_SAMPLES: int = 10         # gated samples required for usability
MAX_INTER_SAMPLE_DT_S: float = 10.0  # s -- gap cap (shared with hemodynamics/pfds)

# Track priorities (binding)
ETCO2_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ETCO2",
    "Primus/ETCO2",
]
RR_TRACK_CANDIDATES: list[str] = [
    "Solar8000/RR_CO2",
    "Primus/RR_CO2",
]
# Raw per-breath capnogram waveform -- DEFERRED; never fetched on default path.
CAPNO_WAVEFORM_TRACK: str = "Primus/CO2"

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11)
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability (FIRST spec, per contract) ---------------------------
    FeatureSpec(
        "capno_available", "comprehensive", "intraop",
        "1 if EtCO2 track usable (>=10 gated samples) for capnogram dynamics, else 0",
    ),
    # ---- EtCO2 trajectory characterisation ---------------------------------
    FeatureSpec(
        "capno_etco2_mean", "comprehensive", "intraop",
        "Time-weighted mean EtCO2 (mmHg) over the intraop window",
    ),
    FeatureSpec(
        "capno_etco2_min", "comprehensive", "intraop",
        "Minimum gated EtCO2 (mmHg) -- deepest pulmonary-perfusion / dead-space hit",
    ),
    FeatureSpec(
        "capno_etco2_decline", "comprehensive", "intraop",
        "Relative fall from first-300s baseline median to lowest sustained 300s "
        "level: (baseline - min_sustained)/baseline, clamped 0..1; respiratory "
        "witness of falling pulmonary blood flow; None if no baseline",
    ),
    FeatureSpec(
        "capno_etco2_variability", "comprehensive", "intraop",
        "Standard deviation of gated EtCO2 (mmHg) -- ventilation/perfusion lability",
    ),
    FeatureSpec(
        "capno_etco2_low_frac", "comprehensive", "intraop",
        "Fraction of intraop time with EtCO2 < 30 mmHg "
        "(dead-space/hypoperfusion threshold), time-weighted",
    ),
    # ---- DEFERRED raw morphology tier (pk; None/0 by default) ---------------
    FeatureSpec(
        "capno_phase3_slope_available", "pk", "intraop",
        "Availability flag (placeholder=0) for the raw per-breath capnogram "
        "phase-III (alveolar plateau) slope, a V/Q-mismatch marker derived from "
        "Primus/CO2; raw waveform NEVER downloaded on the default path; the slope "
        "itself is a documented NotImplemented stub (see _phase3_slope_stub)",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Low-level window helpers (copied from pfds.py -- binding identical behaviour)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds._intraop_window to keep the leakage cutoff
    (t_end == opend) identical across the PFDS feature family.
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
# Pure statistical helpers (no I/O; unit-tested on synthetic series)
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


def _sd(samples: list[tuple[float, float]]) -> float | None:
    """Sample standard deviation of the values (ddof=1).  None if < 2 samples."""
    vals = [v for _, v in samples]
    n = len(vals)
    if n < 2:
        return None
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    return math.sqrt(var)


def _frac_time_below(
    samples: list[tuple[float, float]],
    thr: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Time-weighted fraction of recording with value < thr.

    Forward-dt with gap cap (matches the burden style in pfds).  Returns None
    if < 2 samples or total weighted time is zero.  Returns a value in [0, 1].
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
    return below / total


def _baseline_median(
    samples: list[tuple[float, float]],
    window_s: float = BASELINE_WINDOW_S,
) -> float | None:
    """Median of values in the first `window_s` seconds of the series.

    Mirrors pfds._baseline_value: the baseline level the case starts from,
    against which any later decline is measured.  None if no samples.
    """
    if not samples:
        return None
    t0 = samples[0][0]
    vals = [v for t, v in samples if t <= t0 + window_s]
    if not vals:
        return None
    sv = sorted(vals)
    n = len(sv)
    mid = n // 2
    return sv[mid] if n % 2 == 1 else (sv[mid - 1] + sv[mid]) / 2.0


def _min_sustained(
    samples: list[tuple[float, float]],
    window_s: float = SUSTAINED_WINDOW_S,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Lowest time-weighted mean over any contiguous `window_s`-long window.

    Slides a left-anchored window of width `window_s` starting at each sample
    and takes the time-weighted mean of the samples it spans; returns the
    minimum such mean.  This avoids treating a single-sample artifact dip as
    the case low.  If no window spans >= 2 samples (e.g. the whole record is
    shorter than one sample-gap), falls back to the time-weighted mean of the
    full series.  Returns None if < 2 samples.
    """
    if len(samples) < 2:
        return None
    s = sorted(samples, key=lambda x: x[0])
    n = len(s)
    best: float | None = None
    for i in range(n):
        t0 = s[i][0]
        window = [pt for pt in s[i:] if pt[0] <= t0 + window_s]
        if len(window) < 2:
            continue
        m = _time_weighted_mean(window, max_dt_s=max_dt_s)
        if m is not None and (best is None or m < best):
            best = m
    if best is None:
        # No multi-sample window fit; fall back to the whole-series mean.
        best = _time_weighted_mean(s, max_dt_s=max_dt_s)
    return best


def _phase3_slope_stub(*_args: Any, **_kwargs: Any) -> None:
    """DEFERRED phase-III (alveolar plateau) capnogram slope -- NOT IMPLEMENTED.

    The raw per-breath capnogram (Primus/CO2) resolves a single breath into its
    phases; the slope of phase III (the alveolar plateau) rises with V/Q
    mismatch / alveolar dead space and is a candidate respiratory marker of
    pulmonary hypoperfusion.  Computing it requires per-breath segmentation of
    the raw waveform, which is intentionally out of scope for this tier and is
    NEVER downloaded on the default path (see extract()'s cfg gate).

    This stub documents the intended interface and always returns None.  When
    implemented, it would accept a per-breath capnogram segment and return the
    mmHg/s (or normalised) plateau slope.
    """
    raise NotImplementedError(
        "phase-III alveolar-plateau capnogram slope is deferred; enable the raw "
        "tier behind features.capnogram_waveform and implement per-breath "
        "segmentation of Primus/CO2 before use."
    )


# ===========================================================================
# Biomarker computation (pure orchestration over the helpers above)
# ===========================================================================

def _etco2_decline(
    samples: list[tuple[float, float]],
    baseline_window_s: float = BASELINE_WINDOW_S,
    sustained_window_s: float = SUSTAINED_WINDOW_S,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Relative EtCO2 decline: (baseline - min_sustained)/baseline, clamped 0..1.

    baseline = median EtCO2 in the first `baseline_window_s` seconds.
    min_sustained = lowest time-weighted mean over any contiguous
                    `sustained_window_s` window (artifact-robust low).
    Returns None if no baseline (no samples) or baseline <= 0.
    """
    baseline = _baseline_median(samples, baseline_window_s)
    if baseline is None or baseline <= 0:
        return None
    min_sustained = _min_sustained(samples, sustained_window_s, max_dt_s=max_dt_s)
    if min_sustained is None:
        return None
    decline = (baseline - min_sustained) / baseline
    if decline < 0.0:
        decline = 0.0
    elif decline > 1.0:
        decline = 1.0
    return decline


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all capnogram biomarkers.

    Downloads the NUMERIC EtCO2 track per case (cached).  If no usable EtCO2 is
    present, capno_available=0 and all other features are None.  The raw
    per-breath capnogram (Primus/CO2) is NEVER downloaded on the default path;
    it is gated behind features.capnogram_waveform and, when enabled, only its
    presence in the tid index is checked (no heavy fetch) to set the deferred
    availability placeholder.
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float  # noqa: F401  (contract import)

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["capno_available"] = 0
    # Deferred pk flag stays 0/None by default regardless of EtCO2 availability.
    none_row["capno_phase3_slope_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    waveform_enabled = bool(cfg.get("features", {}).get("capnogram_waveform", False))

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        # ---- EtCO2 track (NUMERIC; default path) -----------------------------
        _etco2_name, raw_etco2 = first_available(cfg, cid_str, ETCO2_TRACK_CANDIDATES)
        etco2_samples: list[tuple[float, float]] = []
        if raw_etco2:
            etco2_samples = _clip_to_window(raw_etco2, t_start, t_end)
            etco2_samples = _filter_physiologic(etco2_samples, ETCO2_MIN, ETCO2_MAX)

        if len(etco2_samples) < MIN_USABLE_SAMPLES:
            # Unusable EtCO2 -> available=0, everything else None.
            row = dict(none_row)
            row["capno_available"] = 0
            out[cid_str] = row
            continue

        row: dict[str, Any] = dict(none_row)
        row["capno_available"] = 1

        # ---- Trajectory biomarkers ------------------------------------------
        row["capno_etco2_mean"] = _time_weighted_mean(etco2_samples)
        row["capno_etco2_min"] = min(v for _, v in etco2_samples)
        row["capno_etco2_decline"] = _etco2_decline(etco2_samples)
        row["capno_etco2_variability"] = _sd(etco2_samples)
        row["capno_etco2_low_frac"] = _frac_time_below(etco2_samples, ETCO2_LOW_THR)

        # ---- DEFERRED raw morphology tier -----------------------------------
        # cfg-GATED, mirroring the pfds heavy-download gate, but here we do NOT
        # fetch the raw waveform at all: we only consult the tid index (cheap)
        # to learn whether Primus/CO2 exists for this case. The phase-III slope
        # itself remains a NotImplemented stub, so the flag stays a placeholder.
        if waveform_enabled:
            from vitaldb_aki.data.tracks import tid_for
            # Consult the tid index only (cheap); the raw Primus/CO2 waveform is
            # never fetched here. Even when present, the phase-III slope metric
            # is deferred (NotImplemented), so the availability flag stays at the
            # documented placeholder value of 0.
            _raw_tid = tid_for(cfg, cid_str, CAPNO_WAVEFORM_TRACK)  # presence probe
            row["capno_phase3_slope_available"] = 0
        else:
            row["capno_phase3_slope_available"] = 0

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.capnogram
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

    print(f"Capnogram validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case capnogram summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")

    print("\nNOTE: phase-III capnogram morphology (Primus/CO2) is DEFERRED "
          "behind features.capnogram_waveform; capno_phase3_slope_available is a "
          "placeholder (0) and _phase3_slope_stub raises NotImplementedError.")
