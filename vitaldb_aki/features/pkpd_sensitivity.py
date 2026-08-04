"""pkpd_sensitivity.py -- Parametric PK-PD Sensitivity / Anesthetic Response Fragility.

This module quantifies each patient's individual drug->hemodynamic sensitivity as
a fragility biomarker: **how much does MAP fall per unit propofol effect-site
concentration?**  A patient whose MAP collapses for modest drug exposure is
"fragile."  This is the parametric upgrade of the crude OLS slope in
pfds.py::fragility_waveform().

SCIENTIFIC RATIONALE
--------------------
pfds.py computes pfds_wf_fragility as a simple OLS slope of MAP vs Ce restricted
to Ce >= 1 ug/mL.  That slope conflates baseline MAP, maximum drug effect, and the
sensitivity of the transition.  The full sigmoid Emax model disentangles these:

    MAP(Ce) = MAP0 - Emax * Ce^h / (EC50^h + Ce^h)

where:
  MAP0  = baseline MAP when Ce -> 0  (intercept; mmHg)
  Emax  = maximum attributable MAP drop (mmHg; positive = more drug effect)
  EC50  = Ce at half-maximal effect (ug/mL; lower EC50 = more sensitive)
  h     = Hill steepness coefficient (dimensionless)

The headline fragility scalar is:
  pkpd_sensitivity = Emax / EC50   (mmHg per ug/mL relative to the half-effect point)

Higher pkpd_sensitivity = more fragile patient.

CONFOUND NOTE: PRESSORS
-----------------------
Concurrent pressor (phenylephrine, norepinephrine, ephedrine) administration raises
MAP independent of propofol.  When a pressor bolus is given during the measurement
window, the MAP-Ce relationship will appear *less* sensitive than reality — the
pressor partially masks the drug effect.  The sigmoid fit will then underestimate
Emax and overestimate EC50, biasing pkpd_sensitivity toward zero (conservative /
attenuated).  This is a LIMITATION of the approach.  Methodological options:

  1. Exclude windows with known pressor boluses — infeasible without high-resolution
     pressor timestamps.
  2. Down-weight pressor-concurrent MAP samples — implemented here as an optional
     residual-based outlier downweight (robust_loss flag for curve_fit).
  3. Statistical sensitivity analysis conditioning on pressor dose — recommended
     in protocol notes as a secondary analysis.

The current implementation uses the 'soft_l1' robust loss in curve_fit, which
down-weights outliers (large positive MAP excursions caused by pressor boluses).
This attenuates but does not eliminate the confound.

MODEL IDENTIFICATION CRITERION
-------------------------------
The sigmoid Emax model requires:
  - >= MIN_SIGMOID_POINTS paired (Ce, MAP) samples
  - Ce range >= MIN_CE_RANGE_UG_ML (needs variation in drug exposure)
If either criterion fails, we fall back to robust linear slope (MAP~Ce).

TRACK WIRING
------------
  propofol effect-site Ce : Orchestra/PPF20_CE  (~56 % cohort; pump-logged)
  MAP primary             : Solar8000/ART_MBP
  MAP fallback            : Solar8000/NIBP_MBP

Intraop window: [anestart|opstart, opend]; NEVER t > opend (§11 leakage gate).
MAP filtered to [20, 200] mmHg (artifact rejection, matching pfds.py).
Ce filtered to >= 0 (no negative concentrations).

RESAMPLING
----------
Both Ce and MAP are resampled to a 30-second grid via last-value hold.  Pairs are
dropped where either track has no sample within RESAMPLE_LOOKBACK_S seconds
(avoids crossing large gaps with stale values).

Protocol reference: §7F-novel, §8, §STRATEGY_PFDS.md.
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic constants (matching pfds.py artifact gates)
# ---------------------------------------------------------------------------
MAP_MIN: float = 20.0    # mmHg  -- artifact floor
MAP_MAX: float = 200.0   # mmHg  -- artifact ceiling
CE_MIN: float = 0.0      # ug/mL -- non-negative concentrations only

# ---------------------------------------------------------------------------
# Resampling / identification parameters (pre-registered)
# ---------------------------------------------------------------------------
RESAMPLE_GRID_S: float = 30.0         # 30 s common grid
RESAMPLE_LOOKBACK_S: float = 120.0    # max stale-value age for last-value hold
MIN_SIGMOID_POINTS: int = 8           # minimum paired points for sigmoid fit
MIN_CE_RANGE_UG_ML: float = 1.0       # minimum Ce range to attempt sigmoid
MIN_LINEAR_POINTS: int = 4            # minimum points for linear fallback
# Sigmoid parameter bounds (physiologically informed)
MAP0_LO: float = 30.0    # mmHg
MAP0_HI: float = 200.0   # mmHg
EMAX_LO: float = 0.0     # mmHg -- non-negative (drug lowers MAP)
EMAX_HI: float = 150.0   # mmHg
EC50_LO: float = 0.05    # ug/mL -- published propofol EC50 MAP range ~1-4 ug/mL
EC50_HI: float = 20.0    # ug/mL
HILL_LO: float = 0.3     # dimensionless
HILL_HI: float = 10.0    # dimensionless

# ---------------------------------------------------------------------------
# Track priorities (matching pfds.py)
# ---------------------------------------------------------------------------
PPF_CE_TRACK: str = "Orchestra/PPF20_CE"
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]

# ---------------------------------------------------------------------------
# Feature specs (fset="pk", timing="intraop")
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "pkpd_available", "pk", "intraop",
        "1 if propofol Ce (Orchestra/PPF20_CE) AND MAP both present; 0 otherwise. "
        "All other pkpd features are None when 0.",
    ),
    FeatureSpec(
        "pkpd_map0", "pk", "intraop",
        "Emax sigmoid: estimated baseline MAP (Ce→0) in mmHg. "
        "None if sigmoid did not identify.",
    ),
    FeatureSpec(
        "pkpd_emax", "pk", "intraop",
        "Emax sigmoid: maximum attributable MAP drop (mmHg; positive = larger drop). "
        "Higher = patient's MAP can drop further under propofol. None if sigmoid "
        "did not identify.",
    ),
    FeatureSpec(
        "pkpd_ec50", "pk", "intraop",
        "Emax sigmoid: propofol Ce at half-maximal MAP effect (ug/mL). Lower = more "
        "sensitive (MAP drops at lower drug concentration). None if sigmoid did not "
        "identify. Published propofol EC50 for MAP is ~1-4 ug/mL.",
    ),
    FeatureSpec(
        "pkpd_hill", "pk", "intraop",
        "Emax sigmoid: Hill steepness coefficient (dimensionless). None if sigmoid "
        "did not identify.",
    ),
    FeatureSpec(
        "pkpd_slope", "pk", "intraop",
        "Robust linear MAP~Ce slope (mmHg per ug/mL). Negative = MAP falls with "
        "higher Ce. Used as fallback when sigmoid does not identify (narrow Ce "
        "range / few points). Also computed when sigmoid fits, for comparison.",
    ),
    FeatureSpec(
        "pkpd_sensitivity", "pk", "intraop",
        "Headline fragility scalar: Emax/EC50 when sigmoid identifies, else "
        "|slope| (linear fallback). Higher = more fragile. Units: mmHg/(ug/mL). "
        "Confound: concurrent pressors attenuate apparent sensitivity (see module "
        "docstring).",
    ),
    FeatureSpec(
        "pkpd_fit_quality", "pk", "intraop",
        "R^2 of the best fitting model (sigmoid if identified, else linear) "
        "against the (Ce, MAP) sample pairs. Range [0, 1]; higher = better fit.",
    ),
    FeatureSpec(
        "pkpd_n_pairs", "pk", "intraop",
        "Number of valid paired (Ce, MAP) samples used for fitting (after 30 s "
        "resampling, last-value hold, artifact rejection).",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Pure helpers (no I/O; unit-testable)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) seconds.  Priority: anestart > opstart > None."""
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


def _filter_range(
    samples: list[tuple[float, float]],
    vmin: float,
    vmax: float,
) -> list[tuple[float, float]]:
    """Drop samples outside [vmin, vmax]."""
    return [(t, v) for t, v in samples if vmin <= v <= vmax]


def _last_value_hold(
    samples: list[tuple[float, float]],
    query_t: float,
    lookback_s: float = RESAMPLE_LOOKBACK_S,
) -> float | None:
    """Return the most recent value at or before query_t, within lookback_s.

    Assumes samples is sorted by time.  Uses binary search.
    """
    lo, hi = 0, len(samples)
    while lo < hi:
        mid = (lo + hi) // 2
        if samples[mid][0] <= query_t:
            lo = mid + 1
        else:
            hi = mid
    idx = lo - 1
    if idx < 0:
        return None
    t_s, v_s = samples[idx]
    if query_t - t_s > lookback_s:
        return None
    return v_s


def resample_to_grid(
    ce_samples: list[tuple[float, float]],
    map_samples: list[tuple[float, float]],
    grid_s: float = RESAMPLE_GRID_S,
    lookback_s: float = RESAMPLE_LOOKBACK_S,
) -> tuple[list[float], list[float]]:
    """Resample Ce and MAP onto a common grid using last-value hold.

    Returns (ce_vals, map_vals) paired lists.  Points where either track
    has no sample within lookback_s are dropped.  Requires the intraop window
    to be pre-applied on both series.

    Parameters
    ----------
    ce_samples : sorted (t, Ce) in ug/mL
    map_samples : sorted (t, MAP) in mmHg
    grid_s : grid spacing in seconds (default 30)
    lookback_s : maximum age of a stale sample to be used (default 120 s)

    Returns
    -------
    (ce_vals, map_vals) : parallel float lists, len >= 0
    """
    if not ce_samples or not map_samples:
        return [], []

    ce_sorted = sorted(ce_samples, key=lambda x: x[0])
    map_sorted = sorted(map_samples, key=lambda x: x[0])

    t_first = max(ce_sorted[0][0], map_sorted[0][0])
    t_last = min(ce_sorted[-1][0], map_sorted[-1][0])
    if t_last <= t_first:
        return [], []

    ce_out: list[float] = []
    map_out: list[float] = []

    t = t_first
    while t <= t_last + 1e-6:
        ce_v = _last_value_hold(ce_sorted, t, lookback_s)
        map_v = _last_value_hold(map_sorted, t, lookback_s)
        if ce_v is not None and map_v is not None:
            ce_out.append(ce_v)
            map_out.append(map_v)
        t += grid_s

    return ce_out, map_out


def _emax_model(ce: float, map0: float, emax: float, ec50: float, h: float) -> float:
    """Sigmoid Emax dose-response: MAP(Ce) = MAP0 - Emax * Ce^h / (EC50^h + Ce^h).

    Returns MAP0 when Ce == 0 (limit).
    """
    if ce <= 0.0:
        return map0
    ceh = ce ** h
    ec50h = ec50 ** h
    return map0 - emax * ceh / (ec50h + ceh)


def _r_squared(
    ce_vals: list[float],
    map_vals: list[float],
    pred_fn,  # callable(ce: float) -> float
) -> float:
    """Coefficient of determination R^2 = 1 - SS_res / SS_tot."""
    n = len(map_vals)
    if n < 2:
        return 0.0
    mean_y = sum(map_vals) / n
    ss_tot = sum((y - mean_y) ** 2 for y in map_vals)
    if ss_tot <= 0.0:
        return 1.0  # constant signal -- perfect fit by convention
    ss_res = sum((y - pred_fn(x)) ** 2 for x, y in zip(ce_vals, map_vals))
    r2 = 1.0 - ss_res / ss_tot
    return float(r2)


def _ols_slope_intercept(
    xs: list[float], ys: list[float]
) -> tuple[float | None, float | None]:
    """OLS slope and intercept of ys ~ xs.  Returns (None, None) if degenerate."""
    n = len(xs)
    if n < 2:
        return None, None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    if sxx <= 0.0:
        return None, None
    slope = sxy / sxx
    intercept = my - slope * mx
    return slope, intercept


def fit_sigmoid_emax(
    ce_vals: list[float],
    map_vals: list[float],
) -> dict[str, float | None]:
    """Fit sigmoid Emax model to (Ce, MAP) pairs.

    Uses scipy.optimize.curve_fit with 'soft_l1' loss (robust to outliers caused
    by pressor boluses) and physiologically bounded parameters.  Returns a dict
    with keys: map0, emax, ec50, hill, r2, success (bool as float 1/0).

    All returned values are None on failure.

    Identification guard:
      - Need >= MIN_SIGMOID_POINTS points
      - Ce range (max - min) >= MIN_CE_RANGE_UG_ML
    """
    result: dict[str, float | None] = {
        "map0": None, "emax": None, "ec50": None, "hill": None,
        "r2": None, "success": 0.0,
    }

    n = len(ce_vals)
    if n < MIN_SIGMOID_POINTS:
        return result

    ce_range = max(ce_vals) - min(ce_vals)
    if ce_range < MIN_CE_RANGE_UG_ML:
        return result

    # Lazy import
    try:
        from scipy.optimize import curve_fit
        import numpy as np
    except ImportError:
        return result

    ce_arr = np.array(ce_vals, dtype=np.float64)
    map_arr = np.array(map_vals, dtype=np.float64)

    # Initial parameter guess
    map0_guess = float(np.percentile(map_arr[ce_arr < (ce_arr.min() + ce_range * 0.25)
                                              if np.any(ce_arr < ce_arr.min() + ce_range * 0.25)
                                              else [True] * len(map_arr)], 75))
    map0_guess = max(MAP0_LO, min(MAP0_HI, map0_guess))
    emax_guess = min(EMAX_HI, max(0.0, map0_guess - float(np.min(map_arr))))
    ec50_guess = max(EC50_LO, min(EC50_HI, float(np.median(ce_arr))))
    hill_guess = 1.0

    p0 = [map0_guess, emax_guess, ec50_guess, hill_guess]
    bounds = ([MAP0_LO, EMAX_LO, EC50_LO, HILL_LO],
              [MAP0_HI, EMAX_HI, EC50_HI, HILL_HI])

    def _model_np(ce, map0, emax, ec50, h):
        ceh = np.power(np.maximum(ce, 0.0), h)
        ec50h = ec50 ** h
        return map0 - emax * ceh / (ec50h + ceh)

    try:
        popt, _ = curve_fit(
            _model_np, ce_arr, map_arr,
            p0=p0, bounds=bounds,
            method="trf", loss="soft_l1",
            max_nfev=5000,
        )
        map0_f, emax_f, ec50_f, hill_f = float(popt[0]), float(popt[1]), float(popt[2]), float(popt[3])

        def pred_fn(x: float) -> float:
            return _emax_model(x, map0_f, emax_f, ec50_f, hill_f)

        r2 = _r_squared(ce_vals, map_vals, pred_fn)

        result["map0"] = round(map0_f, 4)
        result["emax"] = round(emax_f, 4)
        result["ec50"] = round(ec50_f, 4)
        result["hill"] = round(hill_f, 4)
        result["r2"] = round(r2, 6)
        result["success"] = 1.0
    except Exception:
        pass  # curve_fit diverged or hit max_nfev -- fallback to linear

    return result


def fit_linear_robust(
    ce_vals: list[float],
    map_vals: list[float],
) -> dict[str, float | None]:
    """Robust linear MAP~Ce regression.

    Uses scipy's HuberRegressor when available (robust to pressor outliers),
    falling back to plain OLS.  Returns dict with: slope, intercept, r2.

    Returns all None if < MIN_LINEAR_POINTS points.
    """
    result: dict[str, float | None] = {"slope": None, "intercept": None, "r2": None}
    n = len(ce_vals)
    if n < MIN_LINEAR_POINTS:
        return result

    # Try scipy HuberRegressor first (robust)
    try:
        from sklearn.linear_model import HuberRegressor
        import numpy as np
        ce_arr = np.array(ce_vals).reshape(-1, 1)
        map_arr = np.array(map_vals)
        hr = HuberRegressor(epsilon=1.35, max_iter=300)
        hr.fit(ce_arr, map_arr)
        slope_f = float(hr.coef_[0])
        intercept_f = float(hr.intercept_)
        pred_fn = lambda x: slope_f * x + intercept_f  # noqa: E731
        r2 = _r_squared(ce_vals, map_vals, pred_fn)
        result["slope"] = round(slope_f, 4)
        result["intercept"] = round(intercept_f, 4)
        result["r2"] = round(r2, 6)
        return result
    except (ImportError, Exception):
        pass

    # OLS fallback (stdlib only)
    slope, intercept = _ols_slope_intercept(ce_vals, map_vals)
    if slope is None or intercept is None:
        return result
    pred_fn_ols = lambda x: slope * x + intercept  # noqa: E731
    r2 = _r_squared(ce_vals, map_vals, pred_fn_ols)
    result["slope"] = round(slope, 4)
    result["intercept"] = round(intercept, 4)
    result["r2"] = round(r2, 6)
    return result


def compute_pkpd_features(
    ce_vals: list[float],
    map_vals: list[float],
) -> dict[str, float | None]:
    """Compute all PK-PD sensitivity features from paired (Ce, MAP) samples.

    This is the pure computational core (no I/O; unit-testable).

    Algorithm
    ---------
    1. Gate on minimum data requirements.
    2. Attempt sigmoid Emax fit; if it identifies, use Emax/EC50 as sensitivity.
    3. Regardless, compute robust linear slope for comparison / fallback.
    4. pkpd_sensitivity = Emax/EC50 (sigmoid) OR |slope| (linear fallback).
    5. pkpd_fit_quality = R^2 of the chosen model.

    Returns
    -------
    dict with keys matching SPECS (minus pkpd_available and pkpd_n_pairs which
    are filled by the caller).
    """
    out: dict[str, float | None] = {
        "pkpd_map0": None,
        "pkpd_emax": None,
        "pkpd_ec50": None,
        "pkpd_hill": None,
        "pkpd_slope": None,
        "pkpd_sensitivity": None,
        "pkpd_fit_quality": None,
    }

    n = len(ce_vals)
    if n < MIN_LINEAR_POINTS or not map_vals:
        return out

    # Always compute linear (for pkpd_slope and as fallback sensitivity)
    lin = fit_linear_robust(ce_vals, map_vals)
    out["pkpd_slope"] = lin["slope"]

    # Attempt sigmoid Emax
    sig = fit_sigmoid_emax(ce_vals, map_vals)

    if sig["success"]:
        out["pkpd_map0"] = sig["map0"]
        out["pkpd_emax"] = sig["emax"]
        out["pkpd_ec50"] = sig["ec50"]
        out["pkpd_hill"] = sig["hill"]
        out["pkpd_fit_quality"] = sig["r2"]
        # Sensitivity = Emax / EC50 (mmHg per ug/mL)
        emax = sig["emax"]
        ec50 = sig["ec50"]
        if emax is not None and ec50 is not None and ec50 > 0:
            out["pkpd_sensitivity"] = round(emax / ec50, 4)
    else:
        # Sigmoid didn't identify -- use linear fallback
        out["pkpd_fit_quality"] = lin["r2"]
        slope = lin["slope"]
        if slope is not None:
            out["pkpd_sensitivity"] = round(abs(slope), 4)

    return out


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all PK-PD sensitivity features.

    Downloads tracks per case (cached).  All features are None when propofol Ce
    or MAP tracks are absent (pkpd_available = 0).

    Lazy imports: scipy/numpy/sklearn imported inside compute functions.
    """
    from vitaldb_aki.data.tracks import download_track, first_available

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["pkpd_available"] = 0

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
            out[cid_str] = dict(none_row)
            continue

        map_samples = _clip_to_window(raw_map, t_start, t_end)
        map_samples = _filter_range(map_samples, MAP_MIN, MAP_MAX)
        map_samples = sorted(map_samples, key=lambda x: x[0])
        if len(map_samples) < 2:
            out[cid_str] = dict(none_row)
            continue

        # ---- Propofol Ce track -----------------------------------------------
        raw_ce = download_track(cfg, cid_str, PPF_CE_TRACK)
        if not raw_ce:
            # No Ce track -> pkpd_available=0, all None
            out[cid_str] = dict(none_row)
            continue

        ce_samples = _clip_to_window(raw_ce, t_start, t_end)
        ce_samples = _filter_range(ce_samples, CE_MIN, 1e6)
        ce_samples = sorted(ce_samples, key=lambda x: x[0])
        if not ce_samples:
            out[cid_str] = dict(none_row)
            continue

        # ---- Resample to common 30 s grid ------------------------------------
        ce_vals, map_vals = resample_to_grid(ce_samples, map_samples)

        row: dict[str, Any] = dict(none_row)
        row["pkpd_available"] = 1
        row["pkpd_n_pairs"] = len(ce_vals)

        if len(ce_vals) >= MIN_LINEAR_POINTS:
            features = compute_pkpd_features(ce_vals, map_vals)
            row.update(features)

        out[cid_str] = row

    return out


# ===========================================================================
# Real-data validation (network code; run offline under __main__).
# Usage: python -m vitaldb_aki.features.pkpd_sensitivity
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
            if len(cohort_ids) >= 15:
                break

    print(f"PK-PD sensitivity validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    # Report
    keys = [
        "pkpd_available",
        "pkpd_n_pairs",
        "pkpd_map0",
        "pkpd_emax",
        "pkpd_ec50",
        "pkpd_hill",
        "pkpd_slope",
        "pkpd_sensitivity",
        "pkpd_fit_quality",
    ]
    print("\nPer-case PK-PD sensitivity summary:")
    n_avail = 0
    sensitivities = []
    emax_list = []
    ec50_list = []
    for cid in cohort_ids:
        r = result.get(cid, {})
        if r.get("pkpd_available"):
            n_avail += 1
            s = r.get("pkpd_sensitivity")
            if s is not None:
                sensitivities.append(s)
            e = r.get("pkpd_emax")
            if e is not None:
                emax_list.append(e)
            ec = r.get("pkpd_ec50")
            if ec is not None:
                ec50_list.append(ec)
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")

    print(f"\nCoverage: {n_avail}/{len(cohort_ids)} cases have pkpd_available=1")
    if sensitivities:
        sensitivities.sort()
        print(f"pkpd_sensitivity range: [{min(sensitivities):.3f}, {max(sensitivities):.3f}]  "
              f"median={sensitivities[len(sensitivities)//2]:.3f}")
    if emax_list:
        emax_list.sort()
        print(f"pkpd_emax range: [{min(emax_list):.1f}, {max(emax_list):.1f}] mmHg  "
              f"median={emax_list[len(emax_list)//2]:.1f}")
    if ec50_list:
        ec50_list.sort()
        print(f"pkpd_ec50 range: [{min(ec50_list):.2f}, {max(ec50_list):.2f}] ug/mL  "
              f"(physiologic: ~1-4 ug/mL)  median={ec50_list[len(ec50_list)//2]:.2f}")
