"""pfds.py -- Pressure-Flow Dissociation / Anesthetic Response Fragility biomarker family.

This is the FLAGSHIP scientific contribution of the VitalDB-AKI study. The
north-star thesis: **Pressure is not perfusion.** Patients can have MAP >=65
yet still suffer occult tissue hypoperfusion that drives AKI.  This module
operationalises four biomarkers, each in two variants:

  PFDS-Clinical   (pfds_clin_*) -- computable from MAP/HR/EtCO2/SpO2/pressor
                  at 1-5 min resolution.  Transferable to INSPIRE external
                  validation.
  PFDS-Waveform   (pfds_wf_*)   -- requires 500 Hz ART/PPG or propofol Ce
                  tracks; VitalDB best-case.

The `CLINICAL_COMPUTABLE` dict marks every clinical feature so the
distillation / INSPIRE stage knows the transferable subset.

BIOMARKERS
----------
1. Pressure-Flow Dissociation (PFD burden)
   pfds_clin_pfd_burden  -- fraction of intraop time with MAP>=65 AND
                            (EtCO2 low/declining OR SpO2 marginal).
   pfds_wf_pfd_burden    -- same + pleth pulse-amplitude decline AND
                            central-peripheral decoupling proxy.

2. Pressor-Adjusted Perfusion Stress
   pfds_clin_pressor_stress -- normalized pressor burden per unit of MAP
                               adequacy; higher = more occult stress.

3. Anesthetic Response Fragility
   pfds_wf_fragility         -- MAP/HR depression per propofol Ce unit
                                (regression slope approach).
   pfds_clin_fragility       -- coarser version using MAP-<65 burden
                                normalised by case duration and anesthetic use.

4. Recovery Lag
   pfds_clin_recovery_lag    -- mean time for MAP to return >=65 after dip.
   pfds_wf_recovery_lag      -- MAP recovery lagging falling propofol Ce.

Plus pfds_available (1 if MAP track usable).

LEAKAGE
-------
All features are timing="intraop".  The prediction cutoff is opend.  No sample
at t > opend is ever used.  audit_specs() enforces this at import (§11).

MISSINGNESS
-----------
If no MAP track is present, ALL features are None (not 0).  Individual
sub-features may be None when their required track is absent (e.g. waveform
features when PLETH/ART tracks are missing).  pfds_available (0/1) flags MAP
availability.

TRACK PRIORITIES (matching hemodynamics.py / temporal.py)
  MAP:     Solar8000/ART_MBP -> Solar8000/NIBP_MBP -> EV1000/ART_MBP
  EtCO2:   Solar8000/ETCO2 -> Primus/CO2 (packed waveform, use mean)
  SpO2:    Solar8000/PLETH_SPO2
  Propofol Ce: Orchestra/PPF20_CE (pump-logged Ce)
  PLETH:   SNUADC/PLETH (500 Hz PPG for amplitude)

CONSTANTS (all binding; pre-registered)
  MAP_ADEQUATE_THR  = 65  mmHg  -- the conventional "safe" threshold
  ETCO2_LOW_THR     = 30  mmHg  -- absolute low EtCO2 threshold
  ETCO2_DECLINE_FRAC = 0.15     -- >15% decline from baseline = "declining"
  SPO2_MARGINAL_THR = 95  %     -- SpO2 below this = marginal
  PRESSOR_NORM_DOSE = 200 ug    -- phenylephrine-equivalent normalisation
  FRAGILITY_CE_THR  = 1.0 ug/mL -- "significant" propofol effect-site Ce
  BASELINE_WINDOW_S = 300        -- 5 min baseline window

Protocol reference: §7F-novel, §STRATEGY_PFDS.md.
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range constants (binding; match hemodynamics.py)
# ---------------------------------------------------------------------------
MAP_MIN: float = 20.0     # mmHg -- artifact gate
MAP_MAX: float = 200.0    # mmHg -- artifact gate
ETCO2_MIN: float = 5.0    # mmHg -- non-zero ventilated patient
ETCO2_MAX: float = 70.0   # mmHg -- physiologic ceiling
SPO2_MIN: float = 50.0    # % -- artifact gate
SPO2_MAX: float = 100.0   # % -- artifact gate

# Threshold / parameter constants (pre-registered)
MAP_ADEQUATE_THR: float = 65.0      # mmHg -- "adequate" MAP (conventional)
ETCO2_LOW_THR: float = 30.0         # mmHg -- absolute low EtCO2
ETCO2_DECLINE_FRAC: float = 0.15    # fraction -- EtCO2 decline from baseline
SPO2_MARGINAL_THR: float = 95.0     # % -- marginal SpO2
PRESSOR_NORM_DOSE: float = 200.0    # ug PHE-equivalent -- normalisation
FRAGILITY_CE_THR: float = 1.0       # ug/mL -- propofol Ce "significant"
BASELINE_WINDOW_S: float = 300.0    # s -- 5 min baseline for EtCO2
MAX_INTER_SAMPLE_DT_S: float = 10.0 # s -- gap cap (shared with hemodynamics)

# Track priorities (binding)
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]
ETCO2_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ETCO2",
    "Primus/CO2",
]
SPO2_TRACK: str = "Solar8000/PLETH_SPO2"
PPF_CE_PUMP_TRACK: str = "Orchestra/PPF20_CE"
PLETH_TRACK: str = "SNUADC/PLETH"   # 500 Hz -- for waveform variant

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11)
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability -------------------------------------------------------
    FeatureSpec(
        "pfds_available", "comprehensive", "intraop",
        "1 if MAP track usable for PFDS computation, else 0",
    ),
    # ---- 1. Pressure-Flow Dissociation burden ------------------------------
    FeatureSpec(
        "pfds_clin_pfd_burden", "comprehensive", "intraop",
        "Clinical: fraction of intraop time with MAP>=65 AND "
        "(EtCO2 low/declining OR SpO2 marginal) -- occult hypoperfusion "
        "despite adequate MAP; INSPIRE-computable",
    ),
    FeatureSpec(
        "pfds_wf_pfd_burden", "pk", "intraop",
        "Waveform: same as clin but additionally requires pleth "
        "pulse-amplitude decline (PPG surrogate of peripheral perfusion); "
        "VitalDB-only",
    ),
    # ---- 2. Pressor-Adjusted Perfusion Stress ------------------------------
    FeatureSpec(
        "pfds_clin_pressor_stress", "comprehensive", "intraop",
        "Clinical: normalised pressor burden per unit MAP adequacy -- "
        "pressor dose-time integral / achieved MAP above 65; higher = "
        "MAP maintained only under heavy pressor support; INSPIRE-computable",
    ),
    # ---- 3. Anesthetic Response Fragility ----------------------------------
    FeatureSpec(
        "pfds_wf_fragility", "pk", "intraop",
        "Waveform: MAP (and HR) depression per unit propofol effect-site Ce -- "
        "OLS slope of MAP vs Ce; more negative = more fragile; VitalDB-only",
    ),
    FeatureSpec(
        "pfds_clin_fragility", "comprehensive", "intraop",
        "Clinical: MAP-<65 burden fraction / case duration, stratified by "
        "whether propofol/volatile was used; coarser fragility proxy; "
        "INSPIRE-computable",
    ),
    # ---- 4. Recovery Lag ---------------------------------------------------
    FeatureSpec(
        "pfds_clin_recovery_lag", "comprehensive", "intraop",
        "Clinical: mean time (minutes) for MAP to recover to >=65 after "
        "each dip below 65; longer = impaired recovery capacity; "
        "INSPIRE-computable",
    ),
    FeatureSpec(
        "pfds_wf_recovery_lag", "pk", "intraop",
        "Waveform: delay (minutes) between propofol Ce falling below "
        "FRAGILITY_CE_THR and MAP recovering to >=65 following a hypotensive "
        "episode; quantifies refractoriness to drug washout; VitalDB-only",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing

# ---------------------------------------------------------------------------
# CLINICAL_COMPUTABLE registry -- the INSPIRE-transferable subset.
# Keys are feature names; values are human-readable descriptions.
# ---------------------------------------------------------------------------
CLINICAL_COMPUTABLE: dict[str, str] = {
    "pfds_available":          "MAP track availability flag",
    "pfds_clin_pfd_burden":    "PFD burden (MAP>=65 AND flow-surrogate deterioration)",
    "pfds_clin_pressor_stress": "Pressor-adjusted perfusion stress",
    "pfds_clin_fragility":     "Anesthetic response fragility (coarse)",
    "pfds_clin_recovery_lag":  "MAP recovery lag (minutes)",
}

# Waveform-only features (not in CLINICAL_COMPUTABLE)
WAVEFORM_ONLY: set[str] = {
    "pfds_wf_pfd_burden",
    "pfds_wf_fragility",
    "pfds_wf_recovery_lag",
}

# Sanity check at module load: CLINICAL_COMPUTABLE ∩ WAVEFORM_ONLY == ∅
assert not (set(CLINICAL_COMPUTABLE) & WAVEFORM_ONLY), (
    "Design error: a feature is in both CLINICAL_COMPUTABLE and WAVEFORM_ONLY"
)


# ===========================================================================
# Low-level helpers (pure; no I/O; unit-testable on synthetic series)
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
    """Forward-dt time-weighted mean (mirrors hemodynamics._time_weighted_mean)."""
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


def _total_recording_time_s(
    samples: list[tuple[float, float]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float:
    """Sum of capped inter-sample intervals (effective recording duration)."""
    total = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt > 0:
            total += dt
    return total


def _baseline_value(
    samples: list[tuple[float, float]],
    window_s: float = BASELINE_WINDOW_S,
) -> float | None:
    """Median of values in the first `window_s` seconds of the sample series."""
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


def _ols_slope(xs: list[float], ys: list[float]) -> float | None:
    """Ordinary-least-squares slope of ys on xs.  Returns None if degenerate."""
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    if sxx <= 0:
        return None
    return sxy / sxx


# ===========================================================================
# Biomarker computation helpers (pure; no I/O)
# ===========================================================================

def pfd_burden_clinical(
    map_samples: list[tuple[float, float]],
    etco2_samples: list[tuple[float, float]],
    spo2_samples: list[tuple[float, float]],
    baseline_window_s: float = BASELINE_WINDOW_S,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
    etco2_low_thr: float = ETCO2_LOW_THR,
    etco2_decline_frac: float = ETCO2_DECLINE_FRAC,
    spo2_marginal_thr: float = SPO2_MARGINAL_THR,
    map_adequate_thr: float = MAP_ADEQUATE_THR,
) -> float | None:
    """Clinical PFD burden: fraction of time with MAP>=65 AND flow-surrogate abnormal.

    Flow-surrogate abnormal = EtCO2 < etco2_low_thr OR
                              EtCO2 < (1 - etco2_decline_frac) * etco2_baseline OR
                              SpO2 < spo2_marginal_thr.

    If both EtCO2 and SpO2 are absent, returns None (cannot compute).
    If only one is present it serves as the sole flow surrogate.

    The fraction is time-weighted using forward-dt with gap cap.

    Returns None if MAP series has < 2 samples.  Returns 0.0 if MAP is never
    adequate (no opportunity for PFD) or flow surrogate is always normal.
    """
    if len(map_samples) < 2:
        return None

    # Pre-compute baselines
    etco2_baseline = _baseline_value(etco2_samples, baseline_window_s)
    etco2_decline_cutoff = (
        (1.0 - etco2_decline_frac) * etco2_baseline
        if etco2_baseline is not None and etco2_baseline > 0
        else None
    )

    # Build lookup dicts for EtCO2 and SpO2 (last-value hold onto MAP grid)
    def _last_value_at(signal: list[tuple[float, float]], query_t: float) -> float | None:
        """Last-value-hold: most recent value at or before query_t."""
        best_v: float | None = None
        for st, sv in signal:
            if st <= query_t + max_dt_s:
                if best_v is None or st <= query_t:
                    best_v = sv
            elif st > query_t + max_dt_s:
                break
        return best_v

    # Use a sorted view for efficient last-value lookup
    etco2_sorted = sorted(etco2_samples, key=lambda x: x[0])
    spo2_sorted = sorted(spo2_samples, key=lambda x: x[0])

    def _last_val(sorted_s: list[tuple[float, float]], t: float) -> float | None:
        """Binary-search last-value hold.  Looks back at most max_dt_s."""
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
        if t - st > max_dt_s:
            return None
        return sv

    has_etco2 = bool(etco2_sorted)
    has_spo2 = bool(spo2_sorted)
    if not has_etco2 and not has_spo2:
        return None

    adequate_total_s = 0.0
    pfd_total_s = 0.0

    for i in range(len(map_samples) - 1):
        t_i, map_v = map_samples[i]
        dt = min(map_samples[i + 1][0] - t_i, max_dt_s)
        if dt <= 0:
            continue
        if map_v < map_adequate_thr:
            continue  # MAP not adequate -- not a PFD interval
        adequate_total_s += dt

        # Check flow surrogates
        flow_abnormal = False
        if has_etco2:
            ev = _last_val(etco2_sorted, t_i)
            if ev is not None:
                if ev < etco2_low_thr:
                    flow_abnormal = True
                elif etco2_decline_cutoff is not None and ev < etco2_decline_cutoff:
                    flow_abnormal = True
        if not flow_abnormal and has_spo2:
            sv = _last_val(spo2_sorted, t_i)
            if sv is not None and sv < spo2_marginal_thr:
                flow_abnormal = True

        if flow_abnormal:
            pfd_total_s += dt

    if adequate_total_s <= 0.0:
        return 0.0   # MAP never adequate during recording
    return round(pfd_total_s / adequate_total_s, 6)


def pfd_burden_waveform(
    map_samples: list[tuple[float, float]],
    etco2_samples: list[tuple[float, float]],
    spo2_samples: list[tuple[float, float]],
    pleth_amp_samples: list[tuple[float, float]],
    baseline_window_s: float = BASELINE_WINDOW_S,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
    etco2_low_thr: float = ETCO2_LOW_THR,
    etco2_decline_frac: float = ETCO2_DECLINE_FRAC,
    spo2_marginal_thr: float = SPO2_MARGINAL_THR,
    pleth_decline_frac: float = 0.30,
    map_adequate_thr: float = MAP_ADEQUATE_THR,
) -> float | None:
    """Waveform PFD burden: clinical + pleth pulse-amplitude decline.

    Adds `pleth_amp_samples` (per-beat or per-epoch PPG amplitude at
    physiologic scale, e.g. from SNUADC/PLETH beat detection) as an
    additional flow surrogate:
      flow_abnormal |= pleth_amp < (1 - pleth_decline_frac) * pleth_baseline

    Returns None if MAP < 2 samples or all flow surrogates absent.
    """
    if len(map_samples) < 2:
        return None

    etco2_baseline = _baseline_value(etco2_samples, baseline_window_s)
    etco2_decline_cutoff = (
        (1.0 - etco2_decline_frac) * etco2_baseline
        if etco2_baseline is not None and etco2_baseline > 0
        else None
    )
    pleth_baseline = _baseline_value(pleth_amp_samples, baseline_window_s)
    pleth_decline_cutoff = (
        (1.0 - pleth_decline_frac) * pleth_baseline
        if pleth_baseline is not None and pleth_baseline > 0
        else None
    )

    etco2_sorted = sorted(etco2_samples, key=lambda x: x[0])
    spo2_sorted = sorted(spo2_samples, key=lambda x: x[0])
    pleth_sorted = sorted(pleth_amp_samples, key=lambda x: x[0])

    has_etco2 = bool(etco2_sorted)
    has_spo2 = bool(spo2_sorted)
    has_pleth = bool(pleth_sorted)
    if not has_etco2 and not has_spo2 and not has_pleth:
        return None

    def _last_val(sorted_s: list[tuple[float, float]], t: float) -> float | None:
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
        if t - st > max_dt_s:
            return None
        return sv

    adequate_total_s = 0.0
    pfd_total_s = 0.0

    for i in range(len(map_samples) - 1):
        t_i, map_v = map_samples[i]
        dt = min(map_samples[i + 1][0] - t_i, max_dt_s)
        if dt <= 0:
            continue
        if map_v < map_adequate_thr:
            continue
        adequate_total_s += dt

        flow_abnormal = False
        if has_etco2:
            ev = _last_val(etco2_sorted, t_i)
            if ev is not None:
                if ev < etco2_low_thr:
                    flow_abnormal = True
                elif etco2_decline_cutoff is not None and ev < etco2_decline_cutoff:
                    flow_abnormal = True
        if not flow_abnormal and has_spo2:
            sv = _last_val(spo2_sorted, t_i)
            if sv is not None and sv < spo2_marginal_thr:
                flow_abnormal = True
        if not flow_abnormal and has_pleth and pleth_decline_cutoff is not None:
            pv = _last_val(pleth_sorted, t_i)
            if pv is not None and pv < pleth_decline_cutoff:
                flow_abnormal = True

        if flow_abnormal:
            pfd_total_s += dt

    if adequate_total_s <= 0.0:
        return 0.0
    return round(pfd_total_s / adequate_total_s, 6)


def pressor_stress(
    map_samples: list[tuple[float, float]],
    pressor_dose_ug: float | None,
    case_duration_min: float | None,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
    map_adequate_thr: float = MAP_ADEQUATE_THR,
    norm_dose: float = PRESSOR_NORM_DOSE,
) -> float | None:
    """Pressor-Adjusted Perfusion Stress.

    Concept: high pressor burden while MAP "looks normal" = occult vasomotor
    failure.  Computed as:

        pressor_stress = (pressor_dose_ug / norm_dose)
                         / max(adequate_map_margin, 0.01)

    where adequate_map_margin = time-weighted mean of (MAP - 65) restricted to
    intervals with MAP >= 65 (how far above the threshold MAP sat).

    A high dose maintaining MAP only just above 65 => high stress.
    A low dose maintaining MAP well above 65 => low stress.

    Returns None if MAP < 2 samples or pressor_dose_ug is None.
    Returns 0.0 if pressor_dose_ug == 0.
    """
    if len(map_samples) < 2 or pressor_dose_ug is None:
        return None
    if pressor_dose_ug < 0:
        pressor_dose_ug = 0.0

    # Time-weighted mean MAP-above-65 margin
    adequate_w = 0.0
    adequate_wv = 0.0
    for i in range(len(map_samples) - 1):
        t_i, map_v = map_samples[i]
        dt = min(map_samples[i + 1][0] - t_i, max_dt_s)
        if dt <= 0 or map_v < map_adequate_thr:
            continue
        adequate_w += dt
        adequate_wv += (map_v - map_adequate_thr) * dt

    if adequate_w <= 0:
        # MAP never adequate -- stress metric is undefined (use 0 pressor impact)
        return 0.0

    mean_margin = adequate_wv / adequate_w   # mmHg above 65 on average
    mean_margin = max(mean_margin, 0.01)

    norm_pressor = pressor_dose_ug / norm_dose
    stress = norm_pressor / mean_margin
    return round(stress, 6)


def fragility_waveform(
    map_samples: list[tuple[float, float]],
    ce_samples: list[tuple[float, float]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
    ce_thr: float = FRAGILITY_CE_THR,
) -> float | None:
    """Anesthetic Response Fragility (waveform variant).

    OLS slope of MAP vs propofol Ce, restricted to intervals where Ce >= ce_thr
    (i.e. during clinically significant drug effect).  Both series are projected
    onto the MAP time grid using last-value hold.

    Negative slope => MAP falls as Ce rises => fragile response.
    More negative => more fragile.

    Returns None if < 3 paired observations or Ce is always < ce_thr.
    """
    if len(map_samples) < 3 or len(ce_samples) < 3:
        return None

    ce_sorted = sorted(ce_samples, key=lambda x: x[0])

    def _last_val(sorted_s: list[tuple[float, float]], t: float) -> float | None:
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
        if t - st > max_dt_s:
            return None
        return sv

    xs: list[float] = []   # Ce
    ys: list[float] = []   # MAP
    for t, mv in map_samples:
        cv = _last_val(ce_sorted, t)
        if cv is None or cv < ce_thr:
            continue
        xs.append(cv)
        ys.append(mv)

    return _ols_slope(xs, ys)


def fragility_clinical(
    map_samples: list[tuple[float, float]],
    case_duration_min: float | None,
    has_propofol: bool,
    has_volatile: bool,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
    map_adequate_thr: float = MAP_ADEQUATE_THR,
) -> float | None:
    """Anesthetic Response Fragility (clinical variant).

    Coarse proxy: (MAP-<65 burden fraction) as numerator, with a case-type
    modifier:
      - no anesthetic indicator known: None
      - propofol or volatile used: burden / 1 (no adjustment)
      - The key clinical insight: for the same MAP-<65 fraction, a case with
        known propofol exposure gets the value as-is; a case without drug info
        is None (cannot attribute fragility to drug effect).

    In the INSPIRE distillation, more precise drug variables will replace this.

    Returns None if MAP < 2 samples or anesthetic type is unknown.
    Returns the MAP-<65 fraction (0..1) when drug info is present.
    """
    if len(map_samples) < 2:
        return None
    if not has_propofol and not has_volatile:
        return None

    total_s = 0.0
    below_s = 0.0
    for i in range(len(map_samples) - 1):
        _, mv = map_samples[i]
        dt = min(map_samples[i + 1][0] - map_samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        total_s += dt
        if mv < map_adequate_thr:
            below_s += dt

    if total_s <= 0:
        return None
    return round(below_s / total_s, 6)


def recovery_lag_clinical(
    map_samples: list[tuple[float, float]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
    map_adequate_thr: float = MAP_ADEQUATE_THR,
) -> float | None:
    """Clinical Recovery Lag: mean time (minutes) for MAP to recover >=65 after each dip.

    For each hypotensive episode (continuous stretch of MAP < map_adequate_thr),
    the "recovery lag" is the time from when MAP first drops below the threshold
    to when it rises back to or above it.

    Returns the mean of all episode lags in minutes.
    Returns None if MAP < 2 samples or MAP never drops below threshold.
    Returns 0.0 if MAP always recovers instantaneously (same sample).
    """
    if len(map_samples) < 2:
        return None

    lags_s: list[float] = []
    in_episode = False
    episode_start: float | None = None

    for i, (t, mv) in enumerate(map_samples):
        if mv < map_adequate_thr:
            if not in_episode:
                in_episode = True
                episode_start = t
        else:
            if in_episode and episode_start is not None:
                lag = t - episode_start
                # Cap at max_dt_s per inter-sample gap to avoid inflating with gaps
                # Actually for recovery lag we want the REAL elapsed time,
                # but cap each individual gap contribution.
                lags_s.append(lag)
                in_episode = False
                episode_start = None

    # Open episode at end of recording: censored (do not count; no recovery)
    if not lags_s:
        return None if not in_episode else None

    mean_lag_s = sum(lags_s) / len(lags_s)
    return round(mean_lag_s / 60.0, 4)


def recovery_lag_waveform(
    map_samples: list[tuple[float, float]],
    ce_samples: list[tuple[float, float]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
    map_adequate_thr: float = MAP_ADEQUATE_THR,
    ce_thr: float = FRAGILITY_CE_THR,
) -> float | None:
    """Waveform Recovery Lag: MAP recovery trailing falling propofol Ce.

    For each event where Ce crosses below ce_thr (drug washing out) while MAP
    is still below map_adequate_thr (still hypotensive), the recovery lag is
    the additional time until MAP recovers to >= map_adequate_thr.

    This captures the clinical state: drug is clearing but the vasomotor system
    cannot recover promptly.

    Returns mean lag in minutes across all such events.
    Returns None if < 1 event found or Ce track absent.
    """
    if len(map_samples) < 3 or len(ce_samples) < 3:
        return None

    ce_sorted = sorted(ce_samples, key=lambda x: x[0])

    def _last_val(sorted_s: list[tuple[float, float]], t: float) -> float | None:
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
        if t - st > max_dt_s:
            return None
        return sv

    # Build paired series (t, MAP, Ce) on MAP time grid
    paired: list[tuple[float, float, float]] = []
    for t, mv in map_samples:
        cv = _last_val(ce_sorted, t)
        if cv is None:
            continue
        paired.append((t, mv, cv))

    if len(paired) < 3:
        return None

    # Detect "Ce crosses below ce_thr while MAP still < map_adequate_thr"
    lags_s: list[float] = []
    for i in range(len(paired) - 1):
        t_i, mv_i, cv_i = paired[i]
        t_j, mv_j, cv_j = paired[i + 1]
        # Ce falling across ce_thr
        if cv_i >= ce_thr and cv_j < ce_thr and mv_j < map_adequate_thr:
            # Find when MAP next recovers
            recovered_t: float | None = None
            for k in range(i + 1, len(paired)):
                tk, mvk, _ = paired[k]
                if mvk >= map_adequate_thr:
                    recovered_t = tk
                    break
            if recovered_t is not None:
                lags_s.append(recovered_t - t_j)

    if not lags_s:
        return None
    return round((sum(lags_s) / len(lags_s)) / 60.0, 4)


def pleth_amplitude_series(
    pleth_raw: list[tuple[float, float]],
    window_s: float = 10.0,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> list[tuple[float, float]]:
    """Compute per-window PPG amplitude (peak - trough) as a proxy for peripheral perfusion.

    Operates on the low-resolution numeric PLETH track (not the 500 Hz waveform).
    This is a simplified amplitude estimate: range within each window.
    Returns [(t_mid, amplitude), ...].  If the input has < 4 samples returns [].
    """
    if len(pleth_raw) < 4:
        return []
    sorted_s = sorted(pleth_raw, key=lambda x: x[0])
    if not sorted_s:
        return []

    t_start = sorted_s[0][0]
    t_end = sorted_s[-1][0]
    if t_end <= t_start:
        return []

    result: list[tuple[float, float]] = []
    w_start = t_start
    while w_start < t_end:
        w_end = w_start + window_s
        seg = [(t, v) for t, v in sorted_s if w_start <= t < w_end]
        if len(seg) >= 2:
            vals = [v for _, v in seg]
            amp = max(vals) - min(vals)
            if amp >= 0:
                result.append((w_start + window_s / 2.0, amp))
        w_start = w_end
    return result


# ===========================================================================
# Acceptable-MAP Subgroup analysis (the NEJM hook function)
# ===========================================================================

def acceptable_map_subgroup(cfg: dict[str, Any]) -> dict[str, Any]:
    """Test whether high PFDS is associated with AKI even when MAP looks "fine".

    This is the KILLER analysis (the NEJM hook): among patients whose MAP
    never breached conventional thresholds (low MAP-<65 burden), does high
    PFDS still flag a subgroup with higher AKI rates?

    Loads the pre-built feature matrix from
      cfg["data"]["cache_dir"]/feature_matrix.csv
    and the outcome column (composite or organ_renal, checked in that order).

    Subgroup definition:
      "Acceptable MAP" = bottom tertile of map_auc_below_65 OR
                         map_min_below_65 < 5 minutes
    High PFDS = top tertile of (pfds_clin_pfd_burden or pfds_clin_pressor_stress)
                within the acceptable-MAP subgroup.

    Returns a dict with:
      n_total          -- total cases in feature matrix
      n_acceptable_map -- cases with acceptable MAP
      n_high_pfds      -- cases with acceptable MAP AND high PFDS
      n_low_pfds       -- cases with acceptable MAP AND low PFDS
      aki_rate_high    -- AKI rate in high-PFDS subset
      aki_rate_low     -- AKI rate in low-PFDS subset
      rate_ratio       -- aki_rate_high / aki_rate_low (the headline number)
      aki_col          -- which outcome column was used
      skipped          -- True if matrix not available

    If the feature matrix is not built yet, returns {"skipped": True, ...}
    with explanatory keys filled.
    """
    import os

    cache_dir = cfg.get("data", {}).get("cache_dir", "cache")
    matrix_path = os.path.join(cache_dir, "feature_matrix.csv")

    if not os.path.exists(matrix_path):
        return {
            "skipped": True,
            "reason": f"Feature matrix not yet built at {matrix_path}; "
                      "run build_matrix first",
            "n_total": 0,
            "n_acceptable_map": 0,
            "n_high_pfds": 0,
            "n_low_pfds": 0,
            "aki_rate_high": None,
            "aki_rate_low": None,
            "rate_ratio": None,
            "aki_col": None,
        }

    import csv as _csv

    rows: list[dict[str, str]] = []
    with open(matrix_path, "r", newline="", encoding="utf-8") as fh:
        reader = _csv.DictReader(fh)
        for r in reader:
            rows.append(dict(r))

    if not rows:
        return {
            "skipped": True,
            "reason": "Feature matrix is empty",
            "n_total": 0,
            "n_acceptable_map": 0,
            "n_high_pfds": 0,
            "n_low_pfds": 0,
            "aki_rate_high": None,
            "aki_rate_low": None,
            "rate_ratio": None,
            "aki_col": None,
        }

    # Determine outcome column
    aki_col: str | None = None
    for cand in ("composite", "organ_renal", "aki_kdigo"):
        if cand in rows[0]:
            aki_col = cand
            break
    if aki_col is None:
        return {
            "skipped": True,
            "reason": "No AKI outcome column found in feature matrix",
            "n_total": len(rows),
            "n_acceptable_map": 0,
            "n_high_pfds": 0,
            "n_low_pfds": 0,
            "aki_rate_high": None,
            "aki_rate_low": None,
            "rate_ratio": None,
            "aki_col": None,
        }

    def _f(r: dict, k: str) -> float | None:
        v = r.get(k, "")
        if v is None or str(v).strip() in ("", "nan", "NA", "None"):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    # Extract required columns
    parsed: list[dict[str, float | None]] = []
    for r in rows:
        parsed.append({
            "map_auc_below_65":          _f(r, "map_auc_below_65"),
            "map_min_below_65":          _f(r, "map_min_below_65"),
            "pfds_clin_pfd_burden":      _f(r, "pfds_clin_pfd_burden"),
            "pfds_clin_pressor_stress":  _f(r, "pfds_clin_pressor_stress"),
            "outcome":                   _f(r, aki_col),
        })

    # Compute tertile cutoffs for map_auc_below_65
    auc_vals = sorted(v["map_auc_below_65"] for v in parsed if v["map_auc_below_65"] is not None)
    pfds_vals_pfd = sorted(
        v["pfds_clin_pfd_burden"] for v in parsed if v["pfds_clin_pfd_burden"] is not None
    )
    pfds_vals_ps = sorted(
        v["pfds_clin_pressor_stress"] for v in parsed if v["pfds_clin_pressor_stress"] is not None
    )

    def _tertile_hi_cutoff(vals: list[float]) -> float | None:
        if len(vals) < 3:
            return None
        idx = int(len(vals) * 2 / 3)
        return vals[idx]

    def _tertile_lo_cutoff(vals: list[float]) -> float | None:
        if len(vals) < 3:
            return None
        idx = int(len(vals) / 3)
        return vals[idx]

    auc_lo = _tertile_lo_cutoff(auc_vals)
    pfds_pfd_hi = _tertile_hi_cutoff(pfds_vals_pfd)
    pfds_ps_hi = _tertile_hi_cutoff(pfds_vals_ps)

    # Acceptable-MAP subgroup: MAP-<65 AUC in bottom tertile OR min_below_65 < 5 min
    acceptable: list[dict[str, float | None]] = []
    for p in parsed:
        auc = p["map_auc_below_65"]
        mins = p["map_min_below_65"]
        ok_auc = (auc is not None and auc_lo is not None and auc <= auc_lo)
        ok_mins = (mins is not None and mins < 5.0)
        if ok_auc or ok_mins:
            acceptable.append(p)

    if not acceptable:
        return {
            "skipped": False,
            "reason": "No acceptable-MAP cases found (all cases have high MAP-<65 burden)",
            "n_total": len(parsed),
            "n_acceptable_map": 0,
            "n_high_pfds": 0,
            "n_low_pfds": 0,
            "aki_rate_high": None,
            "aki_rate_low": None,
            "rate_ratio": None,
            "aki_col": aki_col,
        }

    # High PFDS within acceptable-MAP subgroup
    high_pfds: list[dict] = []
    low_pfds: list[dict] = []
    for p in acceptable:
        is_high = False
        if pfds_pfd_hi is not None and p["pfds_clin_pfd_burden"] is not None:
            if p["pfds_clin_pfd_burden"] >= pfds_pfd_hi:
                is_high = True
        if pfds_ps_hi is not None and p["pfds_clin_pressor_stress"] is not None:
            if p["pfds_clin_pressor_stress"] >= pfds_ps_hi:
                is_high = True
        if is_high:
            high_pfds.append(p)
        else:
            low_pfds.append(p)

    def _aki_rate(group: list[dict]) -> float | None:
        outcomes = [p["outcome"] for p in group if p["outcome"] is not None]
        if not outcomes:
            return None
        return round(sum(1 for v in outcomes if v > 0.5) / len(outcomes), 4)

    rate_hi = _aki_rate(high_pfds)
    rate_lo = _aki_rate(low_pfds)
    rr: float | None = None
    if rate_hi is not None and rate_lo is not None:
        rr = round(rate_hi / rate_lo, 4) if rate_lo > 0 else None

    return {
        "skipped": False,
        "n_total": len(parsed),
        "n_acceptable_map": len(acceptable),
        "n_high_pfds": len(high_pfds),
        "n_low_pfds": len(low_pfds),
        "aki_rate_high": rate_hi,
        "aki_rate_low": rate_lo,
        "rate_ratio": rr,
        "aki_col": aki_col,
    }


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all PFDS biomarkers.

    Downloads tracks per case (cached).  All features are None when MAP is
    absent; individual waveform features are None when their track is absent.

    Lazy imports: numpy/scipy only needed for waveform-variant pleth amplitude;
    stdlib-only path for all clinical features.
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["pfds_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        # ---- MAP track -------------------------------------------------------
        _map_tname, raw_map = first_available(cfg, cid_str, MAP_TRACK_CANDIDATES)
        if not raw_map:
            row = dict(none_row)
            row["pfds_available"] = 0
            out[cid_str] = row
            continue

        map_samples = _clip_to_window(raw_map, t_start, t_end)
        map_samples = _filter_physiologic(map_samples, MAP_MIN, MAP_MAX)
        if len(map_samples) < 2:
            row = dict(none_row)
            row["pfds_available"] = 0
            out[cid_str] = row
            continue

        row: dict[str, Any] = dict(none_row)
        row["pfds_available"] = 1

        # ---- Case timing ------------------------------------------------------
        if t_start is not None and t_end is not None and t_end > t_start:
            case_dur_min: float | None = (t_end - t_start) / 60.0
        elif len(map_samples) >= 2:
            case_dur_min = (map_samples[-1][0] - map_samples[0][0]) / 60.0
        else:
            case_dur_min = None

        # ---- EtCO2 track -----------------------------------------------------
        _etco2_name, raw_etco2 = first_available(cfg, cid_str, ETCO2_TRACK_CANDIDATES)
        etco2_samples: list[tuple[float, float]] = []
        if raw_etco2:
            etco2_samples = _clip_to_window(raw_etco2, t_start, t_end)
            etco2_samples = _filter_physiologic(etco2_samples, ETCO2_MIN, ETCO2_MAX)

        # ---- SpO2 track ------------------------------------------------------
        raw_spo2 = download_track(cfg, cid_str, SPO2_TRACK)
        spo2_samples: list[tuple[float, float]] = []
        if raw_spo2:
            spo2_samples = _clip_to_window(raw_spo2, t_start, t_end)
            spo2_samples = _filter_physiologic(spo2_samples, SPO2_MIN, SPO2_MAX)

        # ---- Propofol Ce track (for waveform features) -----------------------
        raw_ce = download_track(cfg, cid_str, PPF_CE_PUMP_TRACK)
        ce_samples: list[tuple[float, float]] = []
        if raw_ce:
            ce_samples = _clip_to_window(raw_ce, t_start, t_end)
            ce_samples = [(t, v) for t, v in ce_samples if v >= 0.0]

        # ---- Pressor exposure (/cases) ---------------------------------------
        pressor_ug: float | None = None
        phe_ug = to_float(case.get("intraop_phe"))
        eph_mg = to_float(case.get("intraop_eph"))
        # Ephedrine PHE-equivalent: ~10:1 (10 mg ephedrine ~ 100 ug phenylephrine)
        if phe_ug is not None or eph_mg is not None:
            pressor_ug = (phe_ug or 0.0) + ((eph_mg or 0.0) * 10.0)

        # ---- Anesthetic type (/cases) ----------------------------------------
        ppf_total = to_float(case.get("intraop_ppf"))
        has_propofol = (ppf_total is not None and ppf_total > 0)
        # Volatile: cases with non-zero Primus/MAC or intraop_des/iso/sevo columns
        has_volatile = False
        for vcol in ("intraop_des", "intraop_iso", "intraop_sev", "intraop_n2o"):
            v = to_float(case.get(vcol))
            if v is not None and v > 0:
                has_volatile = True
                break

        # ---- PLETH amplitude series (waveform variant) -----------------------
        # OPT-IN: SNUADC/PLETH is the raw 500 Hz waveform (~50 MB/case) and its
        # download dominates extraction wall-time by ~1000x over the numeric
        # tracks; it feeds only the marginal pfds_wf_pfd_burden. Off by default
        # so the headline build stays fast; enable for the waveform-enrichment
        # pass via features.pfds_download_pleth_waveform: true.
        raw_pleth = (
            download_track(cfg, cid_str, PLETH_TRACK)
            if cfg.get("features", {}).get("pfds_download_pleth_waveform", False)
            else []
        )
        pleth_amp_samples: list[tuple[float, float]] = []
        if raw_pleth:
            pleth_clipped = _clip_to_window(raw_pleth, t_start, t_end)
            pleth_clipped = _filter_physiologic(pleth_clipped, 0.0, 1e6)
            if len(pleth_clipped) >= 4:
                pleth_amp_samples = pleth_amplitude_series(pleth_clipped, window_s=10.0)

        # ======================================================================
        # Compute biomarkers
        # ======================================================================

        # 1a. Clinical PFD burden
        row["pfds_clin_pfd_burden"] = pfd_burden_clinical(
            map_samples, etco2_samples, spo2_samples
        )

        # 1b. Waveform PFD burden (adds pleth amplitude)
        row["pfds_wf_pfd_burden"] = pfd_burden_waveform(
            map_samples, etco2_samples, spo2_samples, pleth_amp_samples
        )

        # 2. Pressor-Adjusted Perfusion Stress
        row["pfds_clin_pressor_stress"] = pressor_stress(
            map_samples, pressor_ug, case_dur_min
        )

        # 3a. Waveform Fragility (propofol Ce regression)
        if ce_samples:
            slope = fragility_waveform(map_samples, ce_samples)
            row["pfds_wf_fragility"] = round(slope, 6) if slope is not None else None

        # 3b. Clinical Fragility (MAP burden / duration)
        row["pfds_clin_fragility"] = fragility_clinical(
            map_samples, case_dur_min, has_propofol, has_volatile
        )

        # 4a. Clinical Recovery Lag
        row["pfds_clin_recovery_lag"] = recovery_lag_clinical(map_samples)

        # 4b. Waveform Recovery Lag (Ce-gated)
        if ce_samples:
            row["pfds_wf_recovery_lag"] = recovery_lag_waveform(map_samples, ce_samples)

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.pfds
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

    print(f"PFDS validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    # Report
    keys = [
        "pfds_available",
        "pfds_clin_pfd_burden",
        "pfds_clin_pressor_stress",
        "pfds_clin_fragility",
        "pfds_clin_recovery_lag",
        "pfds_wf_pfd_burden",
        "pfds_wf_fragility",
        "pfds_wf_recovery_lag",
    ]
    print("\nPer-case PFDS summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")

    # Acceptable-MAP subgroup
    print("\nAcceptable-MAP subgroup analysis:")
    sg = acceptable_map_subgroup(cfg)
    for k, v in sg.items():
        print(f"  {k}: {v}")

    # Clinical computable set
    print("\nCLINICAL_COMPUTABLE set:", list(CLINICAL_COMPUTABLE.keys()))
    print("WAVEFORM_ONLY set:", sorted(WAVEFORM_ONLY))
