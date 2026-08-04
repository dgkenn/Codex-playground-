"""pfds_clinical.py -- PFDS-Clinical biomarker from INSPIRE 5-min OR vitals + meds.

This is the DISTILLED, EHR-computable version of the PFDS biomarker family
(STRATEGY_PFDS.md).  It operates on 5-minute-interval INSPIRE data and is the
target for external validation.  The waveform version (PFDS-Waveform, VitalDB
only) lives in vitaldb_aki/features/pfds.py.

Four biomarkers (two versions each -- waveform / clinical; this file is clinical):
-----------------------------------------------------------------------
1. pressure_flow_dissociation  (PFDS-PFD)
   MAP preserved while perfusion surrogates deteriorate.
   Clinical: MAP + EtCO2 + SpO2 + HR -- dissociation = MAP OK but EtCO2/SpO2 low.

2. pressor_adjusted_stress     (PFDS-PAS)
   Normal MAP on heavy pressor ≠ true normovolaemia.
   Clinical: pressor dose-weighting of MAP trajectory.

3. anesthetic_fragility        (PFDS-ARF)
   Physiology deteriorates more than expected for the anesthetic depth/type.
   Clinical: anesthesia type + gas vitals (EtCO2 / FiO2 / MAC-equivalent from
   vent settings) + MAP/HR response trajectory.

4. recovery_lag                (PFDS-RLG)
   Risk encoded in failure to RECOVER, not just depth of insult.
   Clinical: recovery of MAP/HR/EtCO2 in final 30 min of surgery + early
   post-op ward/ICU trajectory (if available in INSPIRE discharge vitals).

INSPIRE → PFDS-Clinical column mapping
---------------------------------------
The dict ``COLUMN_MAP`` below is the SINGLE POINT TO EDIT when the real INSPIRE
schema deviates from the PhysioNet documentation.  Confirm every key against the
actual header row on first real-data access.

INSPIRE vitals.csv columns (best-effort from PhysioNet v1.4.2 docs):
  mbp, sbp, dbp       MAP/SBP/DBP (mmHg)
  hr                  heart rate (bpm)
  spo2                SpO2 (%)
  etco2               end-tidal CO2 (mmHg)
  rr                  respiratory rate
  temp                temperature (°C)
  fio2                inspired O2 fraction (fraction, 0-1 OR %, confirm)
  peep, tv, pip, compliance, minvol  -- ventilator settings
  time                seconds from opstart

INSPIRE medications.csv columns:
  name                drug name (lower-case; see PRESSOR_DRUGS below)
  amount              dose
  unit                dose unit (mcg/kg/min etc.)
  time                seconds from opstart
  caseid

INSPIRE operations.csv (used for surgery type / anesthesia type):
  optype / department for surgery-type subgroup
  (anesthesia type field -- confirm column name; may be 'antype' or 'ane_type')
"""
from __future__ import annotations

import math
from typing import Any

# --------------------------------------------------------------------------
# Column map: INSPIRE column name -> internal name.
# Edit THIS dict, not the feature code, when the real schema differs.
# --------------------------------------------------------------------------
COLUMN_MAP: dict[str, str] = {
    # vitals.csv
    "mbp":          "map",       # mean arterial pressure (mmHg)
    "hr":           "hr",        # heart rate (bpm)
    "spo2":         "spo2",      # SpO2 (%)
    "etco2":        "etco2",     # end-tidal CO2 (mmHg)
    "fio2":         "fio2",      # FiO2 (fraction or %; see NOTE below)
    "rr":           "rr",        # respiratory rate (/min)
    "tv":           "tv",        # tidal volume (mL)
    "peep":         "peep",      # PEEP (cmH2O)
    "temp":         "temp",      # temperature (°C)
    "time":         "time",      # seconds from opstart
    # medications.csv
    "name":         "drug",
    "amount":       "dose",
    "unit":         "dose_unit",
    # operations.csv
    "optype":       "optype",
    "department":   "department",
}

# NOTE: FiO2 units -- PhysioNet docs are ambiguous.  Treat values > 1.5 as
# percentage and divide by 100; otherwise treat as fraction.  Flag with
# fio2_unit_assumed = True in the output dict.

# --------------------------------------------------------------------------
# Physiologic range gates (artifact rejection at 5-min resolution)
# --------------------------------------------------------------------------
MAP_MIN, MAP_MAX   = 20.0, 200.0   # mmHg
HR_MIN, HR_MAX     = 20.0, 220.0   # bpm
SPO2_MIN, SPO2_MAX = 50.0, 100.0   # %
ETCO2_MIN, ETCO2_MAX = 5.0, 70.0  # mmHg
FIO2_MIN, FIO2_MAX   = 0.1, 1.0   # fraction after normalisation

# --------------------------------------------------------------------------
# Pressor classification (vasopressors that confound MAP interpretation)
# --------------------------------------------------------------------------
PRESSOR_DRUGS: frozenset[str] = frozenset({
    "phenylephrine", "norepinephrine", "epinephrine",
    "vasopressin", "dopamine", "dobutamine",
    "noradrenaline", "adrenaline", "neosynephrine",
    "levophed",                                   # brand name norepinephrine
})

# Inotrope subset (myocardial support, distinguished from pure vasopressors)
INOTROPE_DRUGS: frozenset[str] = frozenset({
    "dobutamine", "epinephrine", "adrenaline", "milrinone",
})

# --------------------------------------------------------------------------
# Clinical feature definitions (PFDS-Clinical; INSPIRE resolution = 5 min)
# --------------------------------------------------------------------------
CLINICAL_COMPUTABLE: dict[str, str] = {
    # biomarker 1 -- Pressure-Flow Dissociation
    "pfd_map_mean":        "time-weighted mean MAP (mmHg) over intraop window",
    "pfd_etco2_mean":      "time-weighted mean EtCO2 (mmHg) over intraop window",
    "pfd_spo2_nadir":      "minimum SpO2 (%) in intraop window",
    "pfd_dissociation":    "fraction of 5-min epochs with MAP>=65 but (EtCO2<30 or SpO2<95)",
    # biomarker 2 -- Pressor-Adjusted Perfusion Stress
    "pas_pressor_min":     "total minutes with any pressor infusing (intraop)",
    "pas_pressor_frac":    "fraction of intraop time on pressor",
    "pas_map_on_pressor":  "mean MAP during epochs with pressor active (mmHg)",
    "pas_pressor_stress":  "pressor_frac * (1 - map_mean/100); proxy for stress",
    # biomarker 3 -- Anesthetic Response Fragility (low-res)
    "arf_fio2_mean":       "mean FiO2 (fraction) -- proxy for ventilatory demand",
    "arf_etco2_sd":        "SD of EtCO2 (mmHg) -- fragility proxy",
    "arf_hr_sd":           "SD of HR (bpm) -- autonomic fragility",
    "arf_map_sd":          "SD of MAP (mmHg) -- hemodynamic fragility",
    # biomarker 4 -- Recovery Lag
    "rlg_map_recovery":    "mean MAP in final 30 min - mean MAP in first 30 min (delta; higher=better recovery)",
    "rlg_etco2_recovery":  "mean EtCO2 in final 30 min - mean EtCO2 in first 30 min (delta)",
    "rlg_hr_recovery":     "mean HR in final 30 min - mean HR in first 30 min (delta; neg=recovery)",
    "rlg_spo2_recovery":   "mean SpO2 in final 30 min - mean SpO2 in first 30 min",
}

RECOVERY_WINDOW_S: float = 30 * 60.0   # 30 minutes


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------

def _parse_vitals(
    rows: list[dict[str, str]],
    caseid: str,
    op_duration_s: float,
) -> list[dict[str, float | None]]:
    """Return a list of per-epoch dicts for one case, filtered to intraop window.

    Applies physiologic range gates and FiO2 unit normalisation.
    Only epochs with time in [0, op_duration_s] are included.
    """
    from vitaldb_aki.inspire.client import to_float

    epochs = []
    for row in rows:
        if row.get("caseid", "").strip() != caseid:
            continue
        t = to_float(row.get("time"))
        if t is None or t < 0 or t > op_duration_s:
            continue

        def g(col: str) -> float | None:
            return to_float(row.get(col))

        map_v   = g("mbp")
        hr_v    = g("hr")
        spo2_v  = g("spo2")
        etco2_v = g("etco2")
        fio2_v  = g("fio2")
        rr_v    = g("rr")

        # Range gates
        if map_v is not None and not (MAP_MIN <= map_v <= MAP_MAX):
            map_v = None
        if hr_v is not None and not (HR_MIN <= hr_v <= HR_MAX):
            hr_v = None
        if spo2_v is not None and not (SPO2_MIN <= spo2_v <= SPO2_MAX):
            spo2_v = None
        if etco2_v is not None and not (ETCO2_MIN <= etco2_v <= ETCO2_MAX):
            etco2_v = None
        # FiO2 unit normalisation
        if fio2_v is not None:
            if fio2_v > 1.5:
                fio2_v = fio2_v / 100.0
            if not (FIO2_MIN <= fio2_v <= FIO2_MAX):
                fio2_v = None

        epochs.append({
            "time": t,
            "map": map_v,
            "hr": hr_v,
            "spo2": spo2_v,
            "etco2": etco2_v,
            "fio2": fio2_v,
            "rr": rr_v,
        })

    epochs.sort(key=lambda e: e["time"])  # type: ignore[arg-type]
    return epochs


def _parse_meds(
    rows: list[dict[str, str]],
    caseid: str,
    op_duration_s: float,
) -> list[dict[str, Any]]:
    """Return pressor events for one case within the intraop window."""
    from vitaldb_aki.inspire.client import to_float

    events = []
    for row in rows:
        if row.get("caseid", "").strip() != caseid:
            continue
        drug = row.get("name", "").strip().lower()
        if drug not in PRESSOR_DRUGS:
            continue
        t = to_float(row.get("time"))
        if t is None or t < 0 or t > op_duration_s:
            continue
        events.append({"time": t, "drug": drug,
                        "dose": to_float(row.get("amount"))})
    return events


def _pressor_active_epochs(
    epochs: list[dict[str, float | None]],
    pressor_events: list[dict[str, Any]],
    interval_s: float = 300.0,   # 5-min default
) -> list[bool]:
    """Tag each epoch as pressor-active (True) or not.

    Heuristic: epoch at time t is pressor-active if any pressor event falls
    within [t - interval_s, t + interval_s] (a two-epoch window to account for
    sparse medication records).
    """
    event_times = {e["time"] for e in pressor_events}
    active = []
    for ep in epochs:
        t = ep["time"]
        on = any(abs(t - et) <= interval_s for et in event_times)
        active.append(on)
    return active


def _safe_mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def _safe_sd(vals: list[float]) -> float | None:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


# --------------------------------------------------------------------------
# Public compute function
# --------------------------------------------------------------------------

def compute_pfds_clinical(
    caseid: str,
    vital_rows: list[dict[str, str]],
    med_rows: list[dict[str, str]],
    op_duration_s: float,
) -> dict[str, float | None]:
    """Compute all PFDS-Clinical features for one case.

    Parameters
    ----------
    caseid        : case identifier
    vital_rows    : rows from INSPIRE vitals.csv (all cases; filtered internally)
    med_rows      : rows from INSPIRE medications.csv (all cases; filtered internally)
    op_duration_s : surgery duration in seconds (opend - opstart)

    Returns
    -------
    Dict matching the CLINICAL_COMPUTABLE keys, with float values or None for
    missing data.  All values are finite or None (never NaN).
    """
    epochs = _parse_vitals(vital_rows, caseid, op_duration_s)
    pressor_events = _parse_meds(med_rows, caseid, op_duration_s)

    if not epochs:
        return {k: None for k in CLINICAL_COMPUTABLE}

    pressor_active = _pressor_active_epochs(epochs, pressor_events)
    total_n = len(epochs)

    # ---- Collect valid values per signal ----
    maps    = [e["map"]   for e in epochs if e["map"]   is not None]
    hrs     = [e["hr"]    for e in epochs if e["hr"]    is not None]
    spo2s   = [e["spo2"]  for e in epochs if e["spo2"]  is not None]
    etco2s  = [e["etco2"] for e in epochs if e["etco2"] is not None]
    fio2s   = [e["fio2"]  for e in epochs if e["fio2"]  is not None]

    # ---- Biomarker 1: Pressure-Flow Dissociation ----
    pfd_map_mean   = _safe_mean(maps)
    pfd_etco2_mean = _safe_mean(etco2s)
    pfd_spo2_nadir = min(spo2s) if spo2s else None

    # Dissociation = fraction of epochs where MAP>=65 but EtCO2<30 or SpO2<95
    diss_count = 0
    diss_denom = 0
    for e in epochs:
        m = e["map"]; c = e["etco2"]; s = e["spo2"]
        if m is not None and (c is not None or s is not None):
            diss_denom += 1
            flow_low = (c is not None and c < 30.0) or (s is not None and s < 95.0)
            if m >= 65.0 and flow_low:
                diss_count += 1
    pfd_dissociation = (diss_count / diss_denom) if diss_denom > 0 else None

    # ---- Biomarker 2: Pressor-Adjusted Perfusion Stress ----
    pressor_on_n = sum(pressor_active)
    pas_pressor_min  = pressor_on_n * 5.0   # each epoch ~5 min
    pas_pressor_frac = pressor_on_n / total_n if total_n > 0 else None

    map_on_pressor = [
        e["map"] for e, on in zip(epochs, pressor_active)
        if on and e["map"] is not None
    ]
    pas_map_on_pressor = _safe_mean(map_on_pressor)

    if pfd_map_mean is not None and pas_pressor_frac is not None:
        pas_pressor_stress = float(pas_pressor_frac) * (1.0 - pfd_map_mean / 100.0)
    else:
        pas_pressor_stress = None

    # ---- Biomarker 3: Anesthetic Response Fragility ----
    arf_fio2_mean = _safe_mean(fio2s)
    arf_etco2_sd  = _safe_sd(etco2s)
    arf_hr_sd     = _safe_sd(hrs)
    arf_map_sd    = _safe_sd(maps)

    # ---- Biomarker 4: Recovery Lag ----
    # First-30-min vs last-30-min epoch windows
    if op_duration_s > 0:
        cutoff_early = RECOVERY_WINDOW_S
        cutoff_late  = op_duration_s - RECOVERY_WINDOW_S

        def _window_mean(signal_key: str, tmin: float, tmax: float) -> float | None:
            vals = [
                e[signal_key] for e in epochs  # type: ignore[literal-required]
                if tmin <= e["time"] <= tmax and e[signal_key] is not None  # type: ignore[literal-required]
            ]
            return _safe_mean(vals)  # type: ignore[arg-type]

        early_map   = _window_mean("map",   0.0,         cutoff_early)
        late_map    = _window_mean("map",   cutoff_late, op_duration_s)
        early_etco2 = _window_mean("etco2", 0.0,         cutoff_early)
        late_etco2  = _window_mean("etco2", cutoff_late, op_duration_s)
        early_hr    = _window_mean("hr",    0.0,         cutoff_early)
        late_hr     = _window_mean("hr",    cutoff_late, op_duration_s)
        early_spo2  = _window_mean("spo2",  0.0,         cutoff_early)
        late_spo2   = _window_mean("spo2",  cutoff_late, op_duration_s)

        def _delta(a: float | None, b: float | None) -> float | None:
            return (b - a) if (a is not None and b is not None) else None

        rlg_map_recovery   = _delta(early_map,   late_map)
        rlg_etco2_recovery = _delta(early_etco2, late_etco2)
        rlg_hr_recovery    = _delta(early_hr,    late_hr)
        rlg_spo2_recovery  = _delta(early_spo2,  late_spo2)
    else:
        rlg_map_recovery = rlg_etco2_recovery = rlg_hr_recovery = rlg_spo2_recovery = None

    result = {
        # Biomarker 1
        "pfd_map_mean":        pfd_map_mean,
        "pfd_etco2_mean":      pfd_etco2_mean,
        "pfd_spo2_nadir":      pfd_spo2_nadir,
        "pfd_dissociation":    pfd_dissociation,
        # Biomarker 2
        "pas_pressor_min":     pas_pressor_min,
        "pas_pressor_frac":    pas_pressor_frac,
        "pas_map_on_pressor":  pas_map_on_pressor,
        "pas_pressor_stress":  pas_pressor_stress,
        # Biomarker 3
        "arf_fio2_mean":       arf_fio2_mean,
        "arf_etco2_sd":        arf_etco2_sd,
        "arf_hr_sd":           arf_hr_sd,
        "arf_map_sd":          arf_map_sd,
        # Biomarker 4
        "rlg_map_recovery":    rlg_map_recovery,
        "rlg_etco2_recovery":  rlg_etco2_recovery,
        "rlg_hr_recovery":     rlg_hr_recovery,
        "rlg_spo2_recovery":   rlg_spo2_recovery,
    }

    # Guarantee no raw NaN leaks out (replace with None)
    return {
        k: (None if (v is not None and math.isnan(v)) else v)
        for k, v in result.items()
    }


def compute_pfds_clinical_all(
    operations: list[dict[str, str]],
    vital_rows: list[dict[str, str]],
    med_rows: list[dict[str, str]],
) -> dict[str, dict[str, float | None]]:
    """Compute PFDS-Clinical for all cases in the operations table.

    Returns {caseid: {feature: value|None}}.
    """
    from vitaldb_aki.inspire.client import to_float

    out: dict[str, dict[str, float | None]] = {}
    for row in operations:
        cid = row.get("caseid", "").strip()
        if not cid:
            continue
        opstart = to_float(row.get("opstart")) or 0.0
        opend   = to_float(row.get("opend"))
        op_duration_s = (opend - opstart) if opend is not None else 0.0
        out[cid] = compute_pfds_clinical(cid, vital_rows, med_rows, op_duration_s)
    return out
