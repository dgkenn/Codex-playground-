"""ischemia.py -- Intraoperative myocardial ischemia (ST-segment) as a FEATURE.

This module operationalises the monitor-computed ST-segment level (per lead, in
mV; 0.1 mV == 1 mm) as an INTRAOP PREDICTOR FEATURE for the study's organ
outcomes -- NOT as an outcome itself.

WHY A FEATURE, NOT A LABEL
--------------------------
The VitalDB open-lab panel carries no troponin / CK / CK-MB; the study therefore
*cannot* label myocardial injury.  But ST-segment ischemia is valuable precisely
*as a predictor*: intraoperative demand ischemia is the cardiac fingerprint of
systemic hypoperfusion, and systemic hypoperfusion is the mechanistic driver of
the renal / hepatic / other organ outcomes the study DOES label.  In other words,
"the heart's ST deviation is a witness to the same oxygen-supply/demand mismatch
that injures the kidney."  So `isch_*` features feed the organ-outcome models the
way PFDS (pressure-flow dissociation) does -- a second, independent perfusion
witness -- and are entirely UNMINED in this cohort to date.

UNITS
-----
Tracks are the Solar8000 monitor-computed ST level per lead, NUMERIC, in mV.
Clinically, 0.1 mV == 1 mm of ST shift.  ABN = 0.1 mV (1 mm) is the conventional
abnormal threshold.  Depression = ST <= -ABN; elevation = ST >= +ABN.

LEAKAGE
-------
All features are timing="intraop".  The prediction cutoff is opend.  No sample at
t > opend is ever used (window [t_start, opend]).  audit_specs() enforces the
no-postop firewall at import (Sec 11).

MISSINGNESS
-----------
If NO ST lead has usable data, `isch_available` = 0 and ALL other features are
None (not 0).  `isch_available` is the FIRST spec.

Protocol reference: Sec 7 (intraop perfusion-witness features).
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Constants (binding; pre-registered)
# ---------------------------------------------------------------------------
ST_PHYS_MIN: float = -2.0      # mV -- artifact gate (drop |ST| > 2 mV as noise)
ST_PHYS_MAX: float = 2.0       # mV -- artifact gate
ABN: float = 0.1               # mV -- abnormal ST threshold (== 1 mm)
MAX_INTER_SAMPLE_DT_S: float = 10.0   # s -- gap cap (shared convention)

# Monitor-computed ST level per lead (NUMERIC, mV).  Download each available
# lead; treat an absent track as [].  (Solar8000/ST_V5 appears twice in the
# pre-registered list; the duplicate is harmless -- de-duplicated at use.)
ST_LEADS: list[str] = [
    "Solar8000/ST_II",
    "Solar8000/ST_V5",
    "Solar8000/ST_I",
    "Solar8000/ST_III",
    "Solar8000/ST_AVF",
    "Solar8000/ST_AVL",
    "Solar8000/ST_AVR",
    "Solar8000/ST_V5",
]

# ---------------------------------------------------------------------------
# Feature specs (Sec 9 nested design; all "intraop" -- leakage firewall Sec 11)
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability (FIRST spec) -----------------------------------------
    FeatureSpec(
        "isch_available", "comprehensive", "intraop",
        "1 if >=1 ST lead has usable (range-gated, in-window) data, else 0",
    ),
    # ---- max deviation -----------------------------------------------------
    FeatureSpec(
        "isch_st_max_dev", "comprehensive", "intraop",
        "Maximum |ST| deviation (mV) observed across all leads and all "
        "intraop time; peak magnitude of ST shift",
    ),
    # ---- depression burden -------------------------------------------------
    FeatureSpec(
        "isch_st_depression_burden", "comprehensive", "intraop",
        "Time-integral (mV.min) of (-ST - ABN) over intervals where "
        "ST <= -ABN, summed across leads (inter-sample gaps capped at 10 s); "
        "cumulative depression magnitude",
    ),
    # ---- elevation burden --------------------------------------------------
    FeatureSpec(
        "isch_st_elevation_burden", "comprehensive", "intraop",
        "Time-integral (mV.min) of (ST - ABN) over intervals where "
        "ST >= +ABN, summed across leads (gaps capped 10 s); cumulative "
        "elevation magnitude (symmetric to depression burden)",
    ),
    # ---- time abnormal fraction --------------------------------------------
    FeatureSpec(
        "isch_st_time_abnormal_frac", "comprehensive", "intraop",
        "Fraction of intraop time during which ANY lead has |ST| > ABN "
        "(union across leads via last-value-hold on a merged time grid)",
    ),
    # ---- n leads (context) -------------------------------------------------
    FeatureSpec(
        "isch_n_leads", "comprehensive", "intraop",
        "Number of distinct ST leads with usable data (context for the "
        "burden / max-dev features)",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Low-level window / range helpers (pure; copied from pfds.py per contract)
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


def _filter_physiologic(
    samples: list[tuple[float, float]],
    vmin: float,
    vmax: float,
) -> list[tuple[float, float]]:
    """Drop samples outside [vmin, vmax] (artifact rejection)."""
    return [(t, v) for t, v in samples if vmin <= v <= vmax]


# ===========================================================================
# Pure ST-ischemia helpers (no I/O; unit-testable on synthetic series)
# ===========================================================================

def _max_abs_dev(samples: list[tuple[float, float]]) -> float | None:
    """Maximum |value| over a single lead's (t, ST) samples.

    Returns None for an empty series.  This is the per-lead peak magnitude of
    ST deviation in mV; the module aggregates across leads with max().
    """
    if not samples:
        return None
    return max(abs(v) for _, v in samples)


def _burden_beyond(
    samples: list[tuple[float, float]],
    thr: float,
    sign: int,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float:
    """Time-integral (mV.min) of the excursion of ST beyond a one-sided threshold.

    For a single lead's (t, ST) samples:
      * sign = -1 (depression): contribution at sample i is (-ST_i - thr) when
        ST_i <= -thr, i.e. how far below -thr the ST level sat.
      * sign = +1 (elevation): contribution is (ST_i - thr) when ST_i >= +thr.

    Each contribution is weighted by the forward inter-sample interval dt
    (capped at max_dt_s so a recording gap cannot inflate the integral), and the
    running sum is converted from mV.seconds to mV.min by /60.

    Returns 0.0 when the lead never breaches the threshold (or has < 2 samples).
    Only NON-NEGATIVE excursions contribute (a sample exactly at the threshold
    contributes 0).
    """
    if len(samples) < 2 or thr < 0:
        return 0.0
    total_mv_s = 0.0
    for i in range(len(samples) - 1):
        t_i, v_i = samples[i]
        dt = min(samples[i + 1][0] - t_i, max_dt_s)
        if dt <= 0:
            continue
        if sign < 0:
            excursion = (-v_i) - thr      # ST <= -thr  =>  -v_i >= thr
        else:
            excursion = v_i - thr         # ST >= +thr
        if excursion > 0:
            total_mv_s += excursion * dt
    return total_mv_s / 60.0


def _frac_time_abnormal(
    list_of_lead_sample_lists: list[list[tuple[float, float]]],
    abn: float = ABN,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Fraction of intraop time during which ANY lead has |ST| > abn (true union).

    Builds the union of all leads' sample timestamps into a single merged time
    grid.  At each grid point t_i we ask, for every lead, "is the lead's
    last-value-hold sample (most recent sample at or before t_i, within
    max_dt_s) abnormal (|ST| > abn)?"  The interval [t_i, t_{i+1}) (dt capped at
    max_dt_s) counts as abnormal if ANY lead is abnormal there.

    Returns abnormal_time / total_time.  Returns None when no lead has >= 2
    samples (no time span to integrate over).  Returns 0.0 when there is a valid
    time span but no lead is ever abnormal.

    This is a real per-sample union across leads (not a per-lead-then-max
    approximation).
    """
    leads = [sorted(s, key=lambda x: x[0]) for s in list_of_lead_sample_lists if s]
    if not leads:
        return None

    # Merged, de-duplicated, sorted time grid across all leads.
    grid = sorted({t for lead in leads for t, _ in lead})
    if len(grid) < 2:
        return None

    def _last_val(sorted_s: list[tuple[float, float]], t: float) -> float | None:
        """Binary-search last-value hold; looks back at most max_dt_s."""
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

    total_s = 0.0
    abnormal_s = 0.0
    for i in range(len(grid) - 1):
        t_i = grid[i]
        dt = min(grid[i + 1] - t_i, max_dt_s)
        if dt <= 0:
            continue
        total_s += dt
        any_abnormal = False
        for lead in leads:
            v = _last_val(lead, t_i)
            if v is not None and abs(v) > abn:
                any_abnormal = True
                break
        if any_abnormal:
            abnormal_s += dt

    if total_s <= 0.0:
        return None
    return round(abnormal_s / total_s, 6)


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all ST-ischemia features.

    Downloads each available ST lead per case (cached).  Samples are clipped to
    the intraop window [t_start, opend] and range-gated to [ST_PHYS_MIN,
    ST_PHYS_MAX].  When NO lead has usable data, isch_available=0 and all other
    features are None (not 0).  stdlib only.
    """
    from vitaldb_aki.data.tracks import download_track

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["isch_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    # De-duplicate leads (ST_V5 listed twice in the pre-registered list).
    lead_names: list[str] = list(dict.fromkeys(ST_LEADS))

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        # ---- Gather usable per-lead series -----------------------------------
        usable_leads: list[list[tuple[float, float]]] = []
        for tname in lead_names:
            raw = download_track(cfg, cid_str, tname)
            if not raw:
                continue
            samples = _clip_to_window(raw, t_start, t_end)
            samples = _filter_physiologic(samples, ST_PHYS_MIN, ST_PHYS_MAX)
            if samples:
                usable_leads.append(samples)

        if not usable_leads:
            out[cid_str] = dict(none_row)
            continue

        # ---- Compute features ------------------------------------------------
        row: dict[str, Any] = dict(none_row)
        row["isch_available"] = 1
        row["isch_n_leads"] = len(usable_leads)

        # Max |ST| deviation across all leads/time.
        per_lead_max = [m for m in (_max_abs_dev(s) for s in usable_leads) if m is not None]
        row["isch_st_max_dev"] = round(max(per_lead_max), 6) if per_lead_max else None

        # Depression / elevation burden, summed across leads (mV.min).
        depr = sum(_burden_beyond(s, ABN, sign=-1) for s in usable_leads)
        elev = sum(_burden_beyond(s, ABN, sign=+1) for s in usable_leads)
        row["isch_st_depression_burden"] = round(depr, 6)
        row["isch_st_elevation_burden"] = round(elev, 6)

        # Fraction of time with ANY lead abnormal (true union).
        row["isch_st_time_abnormal_frac"] = _frac_time_abnormal(usable_leads, ABN)

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.ischemia
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

    print(f"Ischemia validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case ST-ischemia summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")

    print(
        "\nNOTE: these isch_* values are a FEATURE for the organ outcomes "
        "(no troponin/CK label exists in VitalDB open labs)."
    )
