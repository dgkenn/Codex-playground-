"""vasoactive_pd.py -- Vasoactive pharmacodynamics & VASOPLEGIA signature.

Scientific thesis (distinct from pfds.py).  pfds.py asks whether *pressure*
(MAP) tracks *perfusion* (flow surrogates) and builds a fragility metric against
the anaesthetic.  THIS module asks a different circulatory question entirely:
**how hard, and with how many drugs, did the circulation have to be propped up
to hold a MAP at all, and did MAP actually respond to the pressor?**

Needing escalating and/or multiple vasoactive agents to maintain MAP -- or a
blunted MAP response to a rising pressor infusion (vasoplegia) -- marks
circulatory failure, the kind that drives renal and other organ injury.  We
operationalise that as a small family of vasoactive-drug-response biomarkers
computed from the Orchestra infusion-pump RATE tracks (presence of a numeric
rate ==> that drug is running) and the MAP track.

BIOMARKERS (all fset="comprehensive"; all timing="intraop")
-----------------------------------------------------------
  vaso_available                 1 if MAP usable OR any pressor evidence, else 0.
  vaso_n_agents                  count of DISTINCT pressor agents that ran
                                 (rate>0 at some in-window sample), augmented by
                                 /cases bolus/total evidence (intraop_phe/epi/eph).
                                 Breadth of circulatory support.
  vaso_pressor_duration_frac     fraction of intraop time with ANY pressor
                                 infusion running (union of pump rates>0 over a
                                 merged time grid, last-value-hold).
  vaso_max_infusion_norm         peak total pressor infusion intensity: at the
                                 busiest instant, sum across pumps of each pump's
                                 rate normalised within-drug to its own in-case
                                 max (0..1).  A documented escalation-height proxy.
  vaso_responsiveness            OLS slope of MAP vs total-pressor-infusion-rate
                                 (pump total projected onto the MAP grid by
                                 last-value-hold).  Health: MAP rises with pressor
                                 (positive); flat/negative under rising pressor =
                                 vasoplegia.
  vaso_time_to_first_pressor_min minutes from t_start to first pressor infusion
                                 onset; None if pressor never ran.

MISSINGNESS
-----------
If there is NO MAP track AND no pump/case pressor evidence at all, every feature
is None except vaso_available, which is 0.  Individual features are None when
their specific inputs are absent (e.g. vaso_max_infusion_norm / vaso_responsiveness
need pump tracks; vaso_time_to_first_pressor_min needs an actual onset).

LEAKAGE
-------
All features are timing="intraop"; the prediction cutoff is opend.  No sample at
t > opend is ever used.  `_intraop_window` is copied verbatim from pfds.py and
`audit_specs(SPECS)` enforces the no-postop firewall at import (§11).

NUMERIC tracks only.  stdlib only (heavy deps lazy / unused).
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range constants (binding; match hemodynamics.py / pfds.py)
# ---------------------------------------------------------------------------
MAP_MIN: float = 20.0     # mmHg -- artifact gate
MAP_MAX: float = 200.0    # mmHg -- artifact gate
MAX_INTER_SAMPLE_DT_S: float = 10.0  # s -- gap cap (shared with hemodynamics)

# ---------------------------------------------------------------------------
# Vasoactive infusion RATE tracks (Orchestra pumps; NUMERIC rate; a present
# rate>0 sample ==> that drug is running).  All binding / pre-registered.
# ---------------------------------------------------------------------------
PRESSORS: list[str] = [
    "Orchestra/PHEN_RATE",   # phenylephrine
    "Orchestra/NEPI_RATE",   # norepinephrine
    "Orchestra/DOPA_RATE",   # dopamine
    "Orchestra/EPI_RATE",    # epinephrine
    "Orchestra/VASO_RATE",   # vasopressin
    "Orchestra/DOBU_RATE",   # dobutamine (inotrope; counts as vasoactive support)
]
VASODILATORS: list[str] = [
    "Orchestra/NTG_RATE",    # nitroglycerin
    "Orchestra/NPS_RATE",    # nitroprusside
]

MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11).
# First spec MUST be vaso_available (the availability flag).
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "vaso_available", "comprehensive", "intraop",
        "1 if MAP track usable OR any pressor evidence (pump rate / /cases "
        "total) present, else 0",
    ),
    FeatureSpec(
        "vaso_n_agents", "comprehensive", "intraop",
        "Count of DISTINCT pressor agents with any in-window infusion (rate>0), "
        "augmented by /cases bolus/total evidence (intraop_phe -> phenylephrine, "
        "intraop_epi -> epinephrine, intraop_eph -> ephedrine bolus). Breadth of "
        "circulatory support.",
    ),
    FeatureSpec(
        "vaso_pressor_duration_frac", "comprehensive", "intraop",
        "Fraction of intraop time with ANY pressor infusion running (union of "
        "pump rates>0 on a merged grid, last-value-hold). 0..1.",
    ),
    FeatureSpec(
        "vaso_max_infusion_norm", "comprehensive", "intraop",
        "Peak total pressor infusion intensity: at the busiest instant, sum "
        "across pumps of each pump's rate normalised within-drug to its own "
        "in-case max (0..1 per pump). Documented escalation-height proxy. None "
        "if no pump tracks.",
    ),
    FeatureSpec(
        "vaso_responsiveness", "comprehensive", "intraop",
        "OLS slope of MAP vs total-pressor-infusion-rate (pump total projected "
        "onto the MAP grid by last-value-hold). Positive = MAP rises with "
        "pressor (healthy); flat/negative under rising pressor = vasoplegia. "
        "None if <3 paired points or no pump track.",
    ),
    FeatureSpec(
        "vaso_time_to_first_pressor_min", "comprehensive", "intraop",
        "Minutes from t_start to the first pressor infusion onset (rate>0). "
        "None if pressor never ran.",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Low-level window/clip helpers (copied from pfds.py; pure; no I/O)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds._intraop_window so the leakage cutoff (t_end ==
    opend) is identical across feature modules.
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


def _last_val(sorted_s: list[tuple[float, float]], t: float,
              max_dt_s: float = MAX_INTER_SAMPLE_DT_S) -> float | None:
    """Binary-search last-value hold.  Looks back at most max_dt_s.

    Mirrors the inner _last_val used throughout pfds.py.  `sorted_s` must be
    sorted ascending by time.
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
    if t - st > max_dt_s:
        return None
    return sv


def _ols_slope(xs: list[float], ys: list[float]) -> float | None:
    """Ordinary-least-squares slope of ys on xs.  Returns None if degenerate.

    Copied from pfds._ols_slope (needs >=3 points and non-zero x-variance).
    """
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
# Pure vasoactive-PD helpers (unit-testable on synthetic series)
#
# pump_series_dict maps drug-track-name -> [(t, rate), ...] already clipped to
# the intraop window.  A sample with rate>0 means that drug is infusing.
# ===========================================================================

def _agents_used(
    pump_series_dict: dict[str, list[tuple[float, float]]],
    case_flags: dict[str, bool] | None = None,
) -> int:
    """Count DISTINCT pressor agents with evidence of having run.

    A pump counts if it has at least one in-window sample with rate > 0.
    `case_flags` adds /cases-derived bolus/total evidence so agents that were
    given by bolus (and thus never appear on an infusion pump) are still
    counted.  Recognised flag keys:

        "phe" -> phenylephrine   (intraop_phe>0)   -- ensures PHEN counted
        "epi" -> epinephrine     (intraop_epi>0)   -- ensures EPI counted
        "eph" -> ephedrine bolus (intraop_eph>0)   -- a distinct agent

    phe/epi map onto the corresponding Orchestra pump identity (so a drug given
    both by pump and bolus is counted ONCE); ephedrine has no pump track here,
    so its flag always adds a distinct agent.
    """
    agents: set[str] = set()
    for tname, series in pump_series_dict.items():
        if tname not in PRESSORS:
            continue
        if any(v > 0.0 for _, v in series):
            agents.add(tname)

    if case_flags:
        if case_flags.get("phe"):
            agents.add("Orchestra/PHEN_RATE")
        if case_flags.get("epi"):
            agents.add("Orchestra/EPI_RATE")
        if case_flags.get("eph"):
            # Ephedrine is a bolus drug with no Orchestra rate track here;
            # use a sentinel so it counts as its own distinct agent.
            agents.add("__ephedrine_bolus__")

    return len(agents)


def _merged_grid(
    pump_series_dict: dict[str, list[tuple[float, float]]],
) -> list[float]:
    """Sorted, de-duplicated union of all sample timestamps across pumps."""
    ts: set[float] = set()
    for series in pump_series_dict.values():
        for t, _ in series:
            ts.add(t)
    return sorted(ts)


def _any_running_at(
    sorted_pumps: dict[str, list[tuple[float, float]]],
    t: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> bool:
    """True if any PRESSOR pump's last-value-hold rate at time t is > 0."""
    for tname, series in sorted_pumps.items():
        if tname not in PRESSORS:
            continue
        v = _last_val(series, t, max_dt_s)
        if v is not None and v > 0.0:
            return True
    return False


def _frac_time_any_running(
    pump_series_dict: dict[str, list[tuple[float, float]]],
    window: tuple[float | None, float | None],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Fraction of intraop time with ANY pressor infusion running.

    Builds the union of all pump sample times (the merged grid), and for each
    forward interval [t_i, t_{i+1}) charges its (gap-capped) duration to the
    "running" bucket iff any pressor pump is holding a rate>0 at t_i.  The
    denominator is the total gap-capped duration spanned by the grid.

    `window` is accepted for symmetry / documentation; the series are assumed
    already clipped to it (extract() clips before calling).  Returns None if
    there is no pump data at all (fewer than 2 grid points).
    """
    # Only pressor pumps participate.
    pressor_pumps = {
        tn: sorted(s, key=lambda x: x[0])
        for tn, s in pump_series_dict.items()
        if tn in PRESSORS and s
    }
    if not pressor_pumps:
        return None

    grid = _merged_grid(pressor_pumps)
    if len(grid) < 2:
        return None

    total_s = 0.0
    running_s = 0.0
    for i in range(len(grid) - 1):
        t_i = grid[i]
        dt = min(grid[i + 1] - t_i, max_dt_s)
        if dt <= 0:
            continue
        total_s += dt
        if _any_running_at(pressor_pumps, t_i, max_dt_s):
            running_s += dt

    if total_s <= 0:
        return None
    return round(running_s / total_s, 6)


def _max_infusion_norm(
    pump_series_dict: dict[str, list[tuple[float, float]]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Peak total normalised pressor infusion intensity.

    Each pump's rate is normalised within-drug to its own in-case max (so it
    sits in 0..1, robust to wildly different dosing units across drugs).  At
    each merged-grid instant we sum the per-pump normalised last-value-hold
    rates; the returned value is the maximum of that sum over the case -- a
    simple, documented proxy for escalation HEIGHT (how many drugs near their
    own peak simultaneously).

    Returns None if there are no pressor pump tracks at all.  Returns 0.0 if
    pumps are present but never ran (all rates <= 0).
    """
    pressor_pumps = {
        tn: sorted(s, key=lambda x: x[0])
        for tn, s in pump_series_dict.items()
        if tn in PRESSORS and s
    }
    if not pressor_pumps:
        return None

    # Per-pump in-case max (positive only); a pump with no positive rate
    # contributes 0 and is skipped in the normalisation denominator.
    pump_max: dict[str, float] = {}
    for tn, series in pressor_pumps.items():
        mx = max((v for _, v in series if v > 0.0), default=0.0)
        pump_max[tn] = mx

    grid = _merged_grid(pressor_pumps)
    if not grid:
        return None

    best = 0.0
    for t in grid:
        total = 0.0
        for tn, series in pressor_pumps.items():
            mx = pump_max[tn]
            if mx <= 0.0:
                continue
            v = _last_val(series, t, max_dt_s)
            if v is not None and v > 0.0:
                total += v / mx
        if total > best:
            best = total
    return round(best, 6)


def _responsiveness(
    pump_series_dict: dict[str, list[tuple[float, float]]],
    map_samples: list[tuple[float, float]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """OLS slope of MAP vs total normalised pressor rate over the case.

    For each MAP sample we project the (within-drug-normalised) total pressor
    infusion rate onto the MAP time grid by last-value-hold, then regress MAP on
    that total.  Positive slope = MAP rises with pressor (healthy response);
    flat/negative under rising pressor = vasoplegia.

    Returns None if there is no pressor pump track, or fewer than 3 paired
    points after projection.
    """
    pressor_pumps = {
        tn: sorted(s, key=lambda x: x[0])
        for tn, s in pump_series_dict.items()
        if tn in PRESSORS and s
    }
    if not pressor_pumps or len(map_samples) < 3:
        return None

    pump_max: dict[str, float] = {}
    for tn, series in pressor_pumps.items():
        pump_max[tn] = max((v for _, v in series if v > 0.0), default=0.0)

    def _total_at(t: float) -> float:
        total = 0.0
        for tn, series in pressor_pumps.items():
            mx = pump_max[tn]
            if mx <= 0.0:
                continue
            v = _last_val(series, t, max_dt_s)
            if v is not None and v > 0.0:
                total += v / mx
        return total

    xs: list[float] = []   # total normalised pressor rate
    ys: list[float] = []   # MAP
    for t, mv in map_samples:
        xs.append(_total_at(t))
        ys.append(mv)

    slope = _ols_slope(xs, ys)
    return round(slope, 6) if slope is not None else None


def _time_to_first(
    pump_series_dict: dict[str, list[tuple[float, float]]],
    t_start: float | None,
) -> float | None:
    """Minutes from t_start to the first pressor infusion onset (rate>0).

    Scans every PRESSOR pump for the earliest timestamp with rate>0 and returns
    (that_time - t_start)/60.  Returns None if no pressor ever ran.  If t_start
    is None, the first MAP/grid-relative onset cannot be referenced, so the
    onset time itself (in minutes) is returned relative to 0.  A negative result
    is clamped to 0.0 (onset recorded just before the nominal window start).
    """
    first_t: float | None = None
    for tname, series in pump_series_dict.items():
        if tname not in PRESSORS:
            continue
        for t, v in series:
            if v > 0.0:
                if first_t is None or t < first_t:
                    first_t = t
                break
    if first_t is None:
        return None
    ref = t_start if t_start is not None else 0.0
    val = (first_t - ref) / 60.0
    return round(max(val, 0.0), 4)


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all vasoactive-PD biomarkers.

    Downloads the Orchestra pressor RATE pump tracks and a MAP track per case
    (cached).  If there is NO MAP AND no pressor evidence at all, the whole row
    is None except vaso_available=0.  Individual features are None when their
    specific inputs are absent.
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["vaso_available"] = 0

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
        map_samples: list[tuple[float, float]] = []
        if raw_map:
            map_samples = _clip_to_window(raw_map, t_start, t_end)
            map_samples = _filter_physiologic(map_samples, MAP_MIN, MAP_MAX)

        # ---- Pressor RATE pump tracks ---------------------------------------
        pump_series_dict: dict[str, list[tuple[float, float]]] = {}
        for tname in PRESSORS:
            raw = download_track(cfg, cid_str, tname)
            if not raw:
                continue
            clipped = _clip_to_window(raw, t_start, t_end)
            # NUMERIC rate; drop negative (artifact) but keep zeros (pump idle).
            clipped = [(t, v) for t, v in clipped if v >= 0.0]
            if clipped:
                pump_series_dict[tname] = clipped

        # ---- /cases bolus/total pressor evidence -----------------------------
        phe_total = to_float(case.get("intraop_phe"))
        epi_total = to_float(case.get("intraop_epi"))
        eph_total = to_float(case.get("intraop_eph"))
        case_flags: dict[str, bool] = {
            "phe": phe_total is not None and phe_total > 0,
            "epi": epi_total is not None and epi_total > 0,
            "eph": eph_total is not None and eph_total > 0,
        }
        any_case_evidence = any(case_flags.values())
        any_pump_evidence = any(
            any(v > 0.0 for _, v in s) for s in pump_series_dict.values()
        )

        # ---- Availability ----------------------------------------------------
        map_usable = len(map_samples) >= 2
        if not map_usable and not any_pump_evidence and not any_case_evidence:
            # Nothing to compute on.
            row = dict(none_row)
            row["vaso_available"] = 0
            out[cid_str] = row
            continue

        row: dict[str, Any] = dict(none_row)
        row["vaso_available"] = 1

        # ---- vaso_n_agents (pumps + /cases evidence) -------------------------
        n_agents = _agents_used(pump_series_dict, case_flags)
        row["vaso_n_agents"] = n_agents if n_agents > 0 else None

        # ---- vaso_pressor_duration_frac (union of pump rates>0) --------------
        row["vaso_pressor_duration_frac"] = _frac_time_any_running(
            pump_series_dict, (t_start, t_end)
        )

        # ---- vaso_max_infusion_norm (escalation height; needs pumps) ---------
        row["vaso_max_infusion_norm"] = _max_infusion_norm(pump_series_dict)

        # ---- vaso_responsiveness (MAP vs pressor; needs MAP + pumps) ---------
        if map_usable:
            row["vaso_responsiveness"] = _responsiveness(
                pump_series_dict, map_samples
            )

        # ---- vaso_time_to_first_pressor_min ----------------------------------
        row["vaso_time_to_first_pressor_min"] = _time_to_first(
            pump_series_dict, t_start
        )

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.vasoactive_pd
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

    print(f"vasoactive_pd validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case vasoactive-PD summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
