"""perfusion_cascade.py -- the THREE-WITNESS occult-hypoperfusion signature (§7F-novel).

This module extends the PFDS "**pressure is not perfusion**" thesis (see
pfds.py) from a SINGLE downstream witness to a TRIANGULATED cascade.  The
physiologic chain is:

    arterial pressure (MAP)  ->  pulmonary blood flow (EtCO2)  ->  peripheral
    perfusion (SpO2 / PPG)

EtCO2 is governed by pulmonary blood flow: at fixed ventilation, end-tidal CO2
tracks cardiac output delivered to the lungs.  SpO2 (the pulse-oximeter pleth)
reflects peripheral perfusion.  The dangerous, OCCULT pattern this module
operationalises is: **MAP looks ADEQUATE (>=65) while BOTH downstream witnesses
deteriorate together** -- a confirmed dissociation where pressure is maintained
but flow and peripheral delivery are failing.  One witness can mislead (a low
EtCO2 may be hyperventilation; a low SpO2 may be a cold finger); two witnesses
moving DOWN TOGETHER under adequate pressure is the triangulated signal.

CASCADE LOGIC
-------------
  * pcasc_map_etco2_corr        -- do MAP and EtCO2 co-move? (flow-limited coupling)
  * pcasc_map_etco2_lagcorr     -- does EtCO2 FOLLOW MAP with a lag? (propagation)
  * pcasc_downstream_decouple_frac -- pressure fine but >=1 downstream witness bad
  * pcasc_tri_codrop_frac       -- ALL THREE concordantly bad (the tri-witness)
  * pcasc_perfusion_coherence   -- 3-way trend concordance over sliding windows

SIGNALS / GATES (binding; pre-registered)
  MAP   : Solar8000/ART_MBP -> Solar8000/NIBP_MBP -> EV1000/ART_MBP   gate 20-200
  EtCO2 : Solar8000/ETCO2  -> Primus/ETCO2                            gate 5-70
  SpO2  : Solar8000/PLETH_SPO2                                        gate 50-100

THRESHOLDS (binding)
  MAP_ADEQUATE  = 65 mmHg   -- conventional "safe" MAP
  SPO2_MARGINAL = 95 %      -- SpO2 below this = marginal peripheral delivery
  ETCO2_LOW     = 30 mmHg   -- EtCO2 below this = low pulmonary flow

ALIGNMENT
---------
All signals are projected onto a common dt=5 s grid via last-value-hold with a
max_stale cap (a sample older than max_stale seconds does not count).  A grid
point is "jointly valid" only when ALL required signals are non-None there.

AVAILABILITY / MISSINGNESS (honest)
  * MAP & EtCO2 must be JOINTLY usable for >= MIN_JOINT_POINTS grid points,
    else pcasc_available=0 and ALL other features are None (NOT 0).
  * SpO2 is OPTIONAL for the decouple fraction (falls back to EtCO2 alone) but
    REQUIRED for the tri-witness co-drop fraction and the 3-way coherence; those
    are None when SpO2 is absent.

LEAKAGE (§11)
-------------
All features are timing="intraop".  The window is [t_start, opend]; no sample
at t > opend is ever used.  audit_specs() enforces this at import.

stdlib only (no numpy on the default path); mirrors pfds.py conventions.

Protocol: §7C (hemodynamic axis), §7F (occult perfusion biomarkers).
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range gates (binding; match pfds.py / hemodynamics.py)
# ---------------------------------------------------------------------------
MAP_MIN: float = 20.0     # mmHg -- artifact gate
MAP_MAX: float = 200.0    # mmHg -- artifact gate
ETCO2_MIN: float = 5.0    # mmHg -- non-zero ventilated patient
ETCO2_MAX: float = 70.0   # mmHg -- physiologic ceiling
SPO2_MIN: float = 50.0    # % -- artifact gate
SPO2_MAX: float = 100.0   # % -- artifact gate

# ---------------------------------------------------------------------------
# Threshold / parameter constants (pre-registered; binding)
# ---------------------------------------------------------------------------
MAP_ADEQUATE: float = 65.0     # mmHg -- "adequate" MAP (conventional)
SPO2_MARGINAL: float = 95.0    # % -- marginal peripheral SpO2
ETCO2_LOW: float = 30.0        # mmHg -- low pulmonary flow EtCO2

GRID_DT_S: float = 5.0          # s -- common alignment grid step
MAX_STALE_S: float = 10.0       # s -- last-value-hold staleness cap
MIN_JOINT_POINTS: int = 30      # min jointly-valid grid points to compute
LAGS_S: tuple[float, ...] = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0,
                             35.0, 40.0, 45.0, 50.0, 55.0, 60.0)  # lag sweep
TREND_WINDOW_S: float = 60.0    # s -- sliding window for 3-way trend concordance

# ---------------------------------------------------------------------------
# Track priorities (binding)
# ---------------------------------------------------------------------------
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]
ETCO2_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ETCO2",
    "Primus/ETCO2",
]
SPO2_TRACK: str = "Solar8000/PLETH_SPO2"

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11)
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability (FIRST spec) -----------------------------------------
    FeatureSpec(
        "pcasc_available", "comprehensive", "intraop",
        "1 if MAP & EtCO2 are jointly usable for >=30 aligned grid points "
        "(the minimum for the perfusion-cascade biomarkers), else 0",
    ),
    # ---- 1. MAP <-> EtCO2 instantaneous coupling ---------------------------
    FeatureSpec(
        "pcasc_map_etco2_corr", "comprehensive", "intraop",
        "Pearson correlation of MAP vs EtCO2 over jointly-valid aligned points; "
        "positive co-movement suggests flow-limited coupling (EtCO2 tracks "
        "pulmonary blood flow driven by pressure) (§7F)",
    ),
    # ---- 2. MAP -> EtCO2 lagged propagation --------------------------------
    FeatureSpec(
        "pcasc_map_etco2_lagcorr", "comprehensive", "intraop",
        "max Pearson corr of MAP(t) vs EtCO2(t+lag) over lag in {0,5,...,60}s; "
        "tests whether EtCO2 FOLLOWS MAP (perfusion propagation downstream); "
        "reports the peak correlation value (§7F)",
    ),
    # ---- 3. Downstream decoupling (pressure fine, flow not) ----------------
    FeatureSpec(
        "pcasc_downstream_decouple_frac", "comprehensive", "intraop",
        "fraction of jointly-valid time with MAP>=65 (adequate) AND "
        "(EtCO2<30 OR SpO2<95) -- 'pressure fine, flow not'; SpO2 optional "
        "(EtCO2 alone if SpO2 absent) (§7F)",
    ),
    # ---- 4. Tri-witness concordant co-drop ---------------------------------
    FeatureSpec(
        "pcasc_tri_codrop_frac", "comprehensive", "intraop",
        "fraction of time with MAP>=65 AND EtCO2<30 AND SpO2<95 simultaneously "
        "-- all three witnesses concordantly bad despite adequate pressure "
        "(the occult tri-witness signature); None if SpO2 absent (§7F)",
    ),
    # ---- 5. 3-way trend concordance (PK tier) ------------------------------
    FeatureSpec(
        "pcasc_perfusion_coherence", "pk", "intraop",
        "3-way trend concordance: over sliding 60s windows, fraction of windows "
        "where the SIGNS of the MAP, EtCO2, SpO2 slopes all agree "
        "(co-deterioration / co-recovery); None if any of the 3 absent (§7F)",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Low-level window/clip helpers (pure; copied from pfds.py per contract)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds._intraop_window so the leakage cutoff (opend) is
    identical across the PFDS / perfusion-cascade family.
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
# Pure multi-signal alignment + statistics helpers (unit-tested; stdlib only)
# ===========================================================================

def _align_grid(
    signals_dict: dict[str, list[tuple[float, float]]],
    t_start: float,
    t_end: float,
    dt: float = GRID_DT_S,
    max_stale: float = MAX_STALE_S,
) -> tuple[list[float], dict[str, list[float | None]]]:
    """Project multiple irregular signals onto a common uniform grid.

    For each grid time t in [t_start, t_end] stepping by `dt`, each signal's
    aligned value is the most-recent sample at-or-before t within `max_stale`
    seconds (last-value-hold); if the most-recent at-or-before sample is older
    than max_stale (or none exists) the aligned value at that point is None.

    Parameters
    ----------
    signals_dict : {name: [(t, v), ...]}
        Each signal's samples (any order; clipped/gated by the caller).
    t_start, t_end : float
        Inclusive grid bounds (seconds).  t_end is the leakage cutoff; no grid
        time exceeds it.
    dt : float
        Grid step (seconds).
    max_stale : float
        Maximum age (seconds) of the held sample relative to the grid time.

    Returns
    -------
    (grid_times, aligned)
        grid_times : list[float]  -- the grid time points.
        aligned    : {name: [value|None per grid point]} aligned to grid_times.

    A signal's points are jointly valid where ALL required signals are non-None;
    the caller decides which signals are "required" (see helpers below).
    """
    grid_times: list[float] = []
    if dt <= 0 or t_end < t_start:
        return grid_times, {name: [] for name in signals_dict}

    # Build the uniform grid (inclusive of t_end up to floating tolerance).
    t = t_start
    eps = dt * 1e-9
    while t <= t_end + eps:
        grid_times.append(t)
        t += dt

    # Pre-sort each signal by time for the last-value-hold scan.
    sorted_signals = {
        name: sorted(samples, key=lambda x: x[0])
        for name, samples in signals_dict.items()
    }

    aligned: dict[str, list[float | None]] = {name: [] for name in signals_dict}
    for name, sorted_s in sorted_signals.items():
        col = aligned[name]
        n = len(sorted_s)
        idx = 0  # advancing pointer: last sample with time <= current grid time
        for gt in grid_times:
            # Advance idx to the last sample with time <= gt.
            while idx < n and sorted_s[idx][0] <= gt:
                idx += 1
            j = idx - 1
            if j < 0:
                col.append(None)
                continue
            st, sv = sorted_s[j]
            if gt - st > max_stale:
                col.append(None)
            else:
                col.append(sv)
    return grid_times, aligned


def _jointly_valid_indices(
    aligned: dict[str, list[float | None]],
    required: list[str],
) -> list[int]:
    """Indices where ALL `required` signals are non-None (jointly valid)."""
    if not required:
        return []
    n = min(len(aligned.get(name, [])) for name in required)
    out: list[int] = []
    for i in range(n):
        if all(aligned[name][i] is not None for name in required):
            out.append(i)
    return out


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation of two equal-length numeric lists.

    Returns None if fewer than 2 paired points or either series has zero
    variance (correlation undefined).  Result is clamped to [-1, 1].
    """
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    xs = xs[:n]
    ys = ys[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    r = sxy / math.sqrt(sxx * syy)
    if r > 1.0:
        r = 1.0
    elif r < -1.0:
        r = -1.0
    return r


def _lagged_max_corr(
    x_aligned: list[float | None],
    y_aligned: list[float | None],
    dt: float = GRID_DT_S,
    lags_s: tuple[float, ...] = LAGS_S,
) -> float | None:
    """Peak Pearson corr of x(t) vs y(t+lag) over a grid of lags (seconds).

    Both inputs are aligned onto the SAME uniform grid with step `dt`; each
    lag in seconds is converted to an integer grid-point shift (round(lag/dt)).
    For each lag, pairs are (x[i], y[i+shift]) over indices where BOTH are
    non-None.  Returns the maximum correlation across lags, or None if no lag
    yields a computable correlation.

    Tests whether y FOLLOWS x (downstream propagation): a positive peak at a
    non-zero lag means y trails x.
    """
    if dt <= 0:
        return None
    n = min(len(x_aligned), len(y_aligned))
    best: float | None = None
    for lag in lags_s:
        shift = int(round(lag / dt))
        if shift < 0 or shift >= n:
            continue
        xs: list[float] = []
        ys: list[float] = []
        for i in range(n - shift):
            xv = x_aligned[i]
            yv = y_aligned[i + shift]
            if xv is None or yv is None:
                continue
            xs.append(xv)
            ys.append(yv)
        r = _pearson(xs, ys)
        if r is None:
            continue
        if best is None or r > best:
            best = r
    return best


def _frac_joint_condition(
    aligned: dict[str, list[float | None]],
    required: list[str],
    predicate,
) -> float | None:
    """Fraction of jointly-valid grid points where `predicate(values)` is True.

    Parameters
    ----------
    aligned : {name: [value|None, ...]}
    required : signals that must ALL be non-None for a point to count.
    predicate : callable(dict[name -> float]) -> bool
        Evaluated only at jointly-valid points; receives the non-None values
        for that grid point keyed by signal name (only `required` names are
        guaranteed present, but all currently-non-None names are passed).

    Returns the fraction in [0, 1], or None if there are no jointly-valid
    points (cannot compute).
    """
    idxs = _jointly_valid_indices(aligned, required)
    if not idxs:
        return None
    hits = 0
    for i in idxs:
        vals = {
            name: col[i]
            for name, col in aligned.items()
            if i < len(col) and col[i] is not None
        }
        if predicate(vals):
            hits += 1
    return hits / len(idxs)


def _slope_sign(ys: list[float], dt: float = GRID_DT_S) -> int | None:
    """Sign (+1/-1/0) of the OLS slope of `ys` against uniform time (step dt).

    Returns None if fewer than 2 points.  A flat / degenerate window yields 0.
    """
    n = len(ys)
    if n < 2 or dt <= 0:
        return None
    xs = [i * dt for i in range(n)]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return 0
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    slope = sxy / sxx
    if slope > 0:
        return 1
    if slope < 0:
        return -1
    return 0


def _trend_sign_concordance(
    aligned: dict[str, list[float | None]],
    required: list[str],
    dt: float = GRID_DT_S,
    window_s: float = TREND_WINDOW_S,
) -> float | None:
    """Fraction of sliding windows where all required signals' slope SIGNS agree.

    The grid is carved into NON-OVERLAPPING windows of `window_s` seconds
    (window length = max(2, round(window_s/dt)) grid points).  A window counts
    only if EVERY required signal has all-non-None values across that window
    (so every signal yields a defined slope).  The window is "concordant" if
    the non-zero slope signs of all required signals are equal (a flat slope,
    sign 0, breaks concordance -- there is no co-trend to agree on).

    Returns the fraction of usable windows that are concordant, in [0, 1], or
    None if there are no usable windows.
    """
    if dt <= 0:
        return None
    win_pts = max(2, int(round(window_s / dt)))
    n = min((len(aligned.get(name, [])) for name in required), default=0)
    if n < win_pts:
        return None

    usable = 0
    concordant = 0
    start = 0
    while start + win_pts <= n:
        signs: list[int] = []
        ok = True
        for name in required:
            col = aligned[name]
            seg = col[start:start + win_pts]
            if any(v is None for v in seg):
                ok = False
                break
            s = _slope_sign([v for v in seg], dt)  # type: ignore[misc]
            if s is None:
                ok = False
                break
            signs.append(s)
        if ok:
            usable += 1
            # Concordant iff all signs equal AND non-zero (a real co-trend).
            first = signs[0]
            if first != 0 and all(s == first for s in signs):
                concordant += 1
        start += win_pts

    if usable == 0:
        return None
    return concordant / usable


# ===========================================================================
# Case-level computation (pure given aligned signals)
# ===========================================================================

def compute_cascade_features(
    map_samples: list[tuple[float, float]],
    etco2_samples: list[tuple[float, float]],
    spo2_samples: list[tuple[float, float]],
    t_start: float,
    t_end: float,
) -> dict[str, Any]:
    """Compute all perfusion-cascade features from gated, clipped samples.

    Requires MAP & EtCO2 jointly usable for >= MIN_JOINT_POINTS aligned points,
    else returns the all-None row with pcasc_available=0.  SpO2 is optional;
    the tri-witness co-drop and 3-way coherence features are None without it.
    """
    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["pcasc_available"] = 0

    if not map_samples or not etco2_samples:
        return dict(none_row)

    signals: dict[str, list[tuple[float, float]]] = {
        "map": map_samples,
        "etco2": etco2_samples,
    }
    has_spo2 = bool(spo2_samples)
    if has_spo2:
        signals["spo2"] = spo2_samples

    grid_times, aligned = _align_grid(signals, t_start, t_end)

    # Joint MAP & EtCO2 validity gate.
    joint_me = _jointly_valid_indices(aligned, ["map", "etco2"])
    if len(joint_me) < MIN_JOINT_POINTS:
        return dict(none_row)

    row: dict[str, Any] = dict(none_row)
    row["pcasc_available"] = 1

    # ---- 1. MAP <-> EtCO2 instantaneous Pearson corr -----------------------
    map_j = [aligned["map"][i] for i in joint_me]
    etco2_j = [aligned["etco2"][i] for i in joint_me]
    corr = _pearson(map_j, etco2_j)  # type: ignore[arg-type]
    row["pcasc_map_etco2_corr"] = round(corr, 6) if corr is not None else None

    # ---- 2. MAP -> EtCO2 lagged peak corr ----------------------------------
    lagcorr = _lagged_max_corr(aligned["map"], aligned["etco2"])
    row["pcasc_map_etco2_lagcorr"] = (
        round(lagcorr, 6) if lagcorr is not None else None
    )

    # ---- 3. Downstream decoupling fraction (SpO2 optional) -----------------
    def _decouple(vals: dict[str, float]) -> bool:
        if vals.get("map", -1.0) < MAP_ADEQUATE:
            return False
        etco2_bad = vals.get("etco2") is not None and vals["etco2"] < ETCO2_LOW
        spo2_bad = "spo2" in vals and vals["spo2"] < SPO2_MARGINAL
        return etco2_bad or spo2_bad

    decouple = _frac_joint_condition(aligned, ["map", "etco2"], _decouple)
    row["pcasc_downstream_decouple_frac"] = (
        round(decouple, 6) if decouple is not None else None
    )

    # ---- 4. Tri-witness co-drop fraction (needs SpO2) ----------------------
    if has_spo2:
        def _tri(vals: dict[str, float]) -> bool:
            return (
                vals.get("map", -1.0) >= MAP_ADEQUATE
                and vals.get("etco2", 1e9) < ETCO2_LOW
                and vals.get("spo2", 1e9) < SPO2_MARGINAL
            )

        tri = _frac_joint_condition(aligned, ["map", "etco2", "spo2"], _tri)
        row["pcasc_tri_codrop_frac"] = round(tri, 6) if tri is not None else None

        # ---- 5. 3-way trend-sign concordance (needs all 3) -----------------
        coh = _trend_sign_concordance(aligned, ["map", "etco2", "spo2"])
        row["pcasc_perfusion_coherence"] = (
            round(coh, 6) if coh is not None else None
        )

    return row


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all perfusion-cascade features.

    Downloads MAP / EtCO2 / SpO2 numeric tracks per case (cached).  When MAP &
    EtCO2 are not jointly usable for >=30 aligned grid points, ALL features are
    None and pcasc_available=0.  SpO2 is optional (tri-witness / coherence are
    None without it).  stdlib-only path (no numpy).
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float  # noqa: F401  (contract import)

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["pcasc_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)
        if t_end is None:
            # No leakage cutoff -> cannot bound the window safely.
            out[cid_str] = dict(none_row)
            continue
        grid_start = t_start if t_start is not None else 0.0

        # ---- MAP track -------------------------------------------------------
        _map_tname, raw_map = first_available(cfg, cid_str, MAP_TRACK_CANDIDATES)
        map_samples: list[tuple[float, float]] = []
        if raw_map:
            map_samples = _clip_to_window(raw_map, t_start, t_end)
            map_samples = _filter_physiologic(map_samples, MAP_MIN, MAP_MAX)

        # ---- EtCO2 track -----------------------------------------------------
        _etco2_name, raw_etco2 = first_available(cfg, cid_str, ETCO2_TRACK_CANDIDATES)
        etco2_samples: list[tuple[float, float]] = []
        if raw_etco2:
            etco2_samples = _clip_to_window(raw_etco2, t_start, t_end)
            etco2_samples = _filter_physiologic(etco2_samples, ETCO2_MIN, ETCO2_MAX)

        # Missing either REQUIRED signal => pcasc_available=0, all others None.
        if not map_samples or not etco2_samples:
            out[cid_str] = dict(none_row)
            continue

        # ---- SpO2 track (optional) -------------------------------------------
        raw_spo2 = download_track(cfg, cid_str, SPO2_TRACK)
        spo2_samples: list[tuple[float, float]] = []
        if raw_spo2:
            spo2_samples = _clip_to_window(raw_spo2, t_start, t_end)
            spo2_samples = _filter_physiologic(spo2_samples, SPO2_MIN, SPO2_MAX)

        out[cid_str] = compute_cascade_features(
            map_samples, etco2_samples, spo2_samples, grid_start, t_end
        )

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.perfusion_cascade
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

    print(f"perfusion_cascade validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case perfusion-cascade summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
