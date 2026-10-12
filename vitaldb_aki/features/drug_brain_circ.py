"""drug_brain_circ.py -- the pharmacodynamic TRIAD biomarker family (§7F-novel).

Drug -> Brain -> Circulation response surface.  This module operationalises a
single mechanistic idea that is distinct from raw drug exposure (the `pk`
module) and from pressure-flow dissociation (`pfds`):

    For a given DEPTH of anesthesia (BIS suppression), some patients'
    circulation collapses far more than others.

We jointly observe three simultaneously-recorded effect signals:

  * propofol effect-site concentration  Ce   (Orchestra/PPF20_CE)  -- the DRUG
  * bispectral index                     BIS  (BIS/BIS)             -- the BRAIN
  * mean arterial pressure               MAP  (Solar8000/ART_MBP ...) -- the CIRCULATION

and fit the 3-way response surface:

  1. ce_bis_slope  -- OLS slope of BIS vs Ce: cerebral drug potency.  Expect
     NEGATIVE (BIS falls as Ce rises).
  2. ce_map_slope  -- OLS slope of MAP vs Ce: circulatory drug effect.  Expect
     NEGATIVE (MAP falls as Ce rises).
  3. map_per_bis_suppression = ce_map_slope / ce_bis_slope -- the HEADLINE
     fragility surface: ΔMAP per unit ΔBIS *attributable to drug*.  Large
     magnitude => circulation collapses a lot for little extra hypnotic depth =
     hemodynamically FRAGILE phenotype.
  4. resid_instability -- residual SD of the joint OLS fit  MAP ~ a + b·Ce + c·BIS.
     Circulatory lability NOT explained by the joint drug+depth state (excess
     instability).

This is a pk-tier family: it requires both a BIS monitor and a propofol Ce pump
log, i.e. the TIVA/BIS subset of cases.  When BIS and Ce are not jointly present
(>=30 aligned points) every feature is None and drugbrain_available=0.

LEAKAGE (§11)
-------------
All features are timing="intraop".  The prediction cutoff is opend.  No sample
at t > opend is ever used (window [t_start, opend]).  audit_specs() enforces the
firewall at import.

MISSINGNESS
-----------
If Ce or BIS (or MAP) is absent / not jointly usable => drugbrain_available=0 and
ALL other features are None (NOT 0).  Range gates reject artifact.

Tracks (NUMERIC only; first_available + range gate):
  Ce :  Orchestra/PPF20_CE                                 gate Ce  >= 0
  BIS:  BIS/BIS                                            gate 0   <= BIS <= 100
  MAP:  Solar8000/ART_MBP -> Solar8000/NIBP_MBP -> EV1000/ART_MBP   gate 20..200

Stdlib only (no numpy/scipy); all alignment/regression is pure python.

Protocol: §7F (drug->brain->circulation triad), §7C (hemodynamic axis), §pk.
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range gates (binding; artifact rejection).
# ---------------------------------------------------------------------------
CE_MIN: float = 0.0       # ug/mL -- pump-logged effect-site Ce is non-negative
CE_MAX: float = 30.0      # ug/mL -- generous ceiling (propofol Ce rarely > ~10)
BIS_MIN: float = 0.0      # BIS index lower bound (isoelectric)
BIS_MAX: float = 100.0    # BIS index upper bound (fully awake)
MAP_MIN: float = 20.0     # mmHg -- artifact gate (shared with pfds/hemodynamics)
MAP_MAX: float = 200.0    # mmHg -- artifact gate

# ---------------------------------------------------------------------------
# Alignment / fit parameters (binding; pre-registered).
# ---------------------------------------------------------------------------
ALIGN_DT_S: float = 10.0          # common resampling grid step (s)
MAX_STALE_S: float = 15.0         # last-value-hold staleness cap (s)
MIN_JOINT_POINTS: int = 30        # >=30 aligned (Ce,BIS,MAP) points to be "usable"
MIN_SLOPE_POINTS: int = 3         # OLS slope needs >=3 points
MIN_RESID_POINTS: int = 5         # joint 2-regressor OLS needs >=5 points
SLOPE_EPS: float = 1e-6           # |ce_bis_slope| below this => ratio undefined

# ---------------------------------------------------------------------------
# Track priorities (binding; NUMERIC tracks only).
# ---------------------------------------------------------------------------
CE_TRACK_CANDIDATES: list[str] = ["Orchestra/PPF20_CE"]
BIS_TRACK_CANDIDATES: list[str] = ["BIS/BIS"]
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11).
# First spec MUST be the availability flag.
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "drugbrain_available", "pk", "intraop",
        "1 if propofol Ce + BIS + MAP were jointly usable (>=30 aligned points) "
        "for the drug->brain->circulation triad, else 0; pk-tier (TIVA/BIS subset)",
    ),
    FeatureSpec(
        "drugbrain_ce_bis_slope", "pk", "intraop",
        "OLS slope of BIS vs propofol Ce on the aligned grid -- cerebral drug "
        "potency; expect NEGATIVE (BIS falls as Ce rises); None if <3 points",
    ),
    FeatureSpec(
        "drugbrain_ce_map_slope", "pk", "intraop",
        "OLS slope of MAP vs propofol Ce on the aligned grid -- circulatory drug "
        "effect; expect NEGATIVE (MAP falls as Ce rises); None if <3 points",
    ),
    FeatureSpec(
        "drugbrain_map_per_bis_suppression", "pk", "intraop",
        "HEADLINE fragility surface: ce_map_slope / ce_bis_slope = ΔMAP per unit "
        "ΔBIS attributable to drug; large magnitude = circulation collapses for "
        "little extra hypnotic depth = fragile; None if |ce_bis_slope| < eps",
    ),
    FeatureSpec(
        "drugbrain_resid_instability", "pk", "intraop",
        "Residual SD of the joint OLS fit MAP ~ a + b·Ce + c·BIS -- circulatory "
        "lability NOT explained by joint drug+depth state (excess instability); "
        "None if <5 points or singular",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Low-level window / gate helpers (pure; no I/O; copied to match pfds).
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds._intraop_window so the intraop leakage cutoff
    (t_end = opend) is identical across modules.
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


# ===========================================================================
# Pure computational helpers (unit-tested on synthetic series; stdlib only).
# ===========================================================================

def _align_grid(
    signals_dict: dict[str, list[tuple[float, float]]],
    t_start: float,
    t_end: float,
    dt: float = ALIGN_DT_S,
    max_stale: float = MAX_STALE_S,
) -> dict[str, list[float]]:
    """Align multiple irregular (t, v) series onto one common time grid.

    Builds a uniform grid t_start, t_start+dt, ..., up to t_end (inclusive of
    t_end if it lands on the grid).  For every grid time, each signal is sampled
    by LAST-VALUE-HOLD: the most recent sample at-or-before the grid time, but
    only if it is no more than `max_stale` seconds old (else the signal is
    missing at that grid point).

    A grid time is KEPT only if EVERY signal has a fresh value there; that grid
    point's value for each signal is appended to its output list.  Output lists
    are therefore equal length and index-aligned across signals.

    Returns {name: [values...]} (empty lists if nothing aligns).  Pure: no I/O.
    Never reads t > t_end (the leakage cutoff is the caller's responsibility via
    pre-clipping, but the grid also stops at t_end).
    """
    names = list(signals_dict.keys())
    out: dict[str, list[float]] = {name: [] for name in names}

    if t_end < t_start or dt <= 0:
        return out

    # Pre-sort each signal once for efficient last-value lookup.
    sorted_sigs: dict[str, list[tuple[float, float]]] = {
        name: sorted(samples, key=lambda x: x[0])
        for name, samples in signals_dict.items()
    }
    # Any signal that has no samples at all => nothing can align.
    for name in names:
        if not sorted_sigs[name]:
            return {name: [] for name in names}

    def _last_val(sorted_s: list[tuple[float, float]], t: float) -> float | None:
        """Binary-search last-value hold; None if stale (> max_stale old)."""
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
        if t - st > max_stale:
            return None
        return sv

    # Walk the uniform grid.  Use integer stepping to avoid float drift.
    n_steps = int(math.floor((t_end - t_start) / dt + 1e-9)) + 1
    for k in range(n_steps):
        gt = t_start + k * dt
        if gt > t_end + 1e-9:
            break
        vals: dict[str, float] = {}
        ok = True
        for name in names:
            v = _last_val(sorted_sigs[name], gt)
            if v is None:
                ok = False
                break
            vals[name] = v
        if ok:
            for name in names:
                out[name].append(vals[name])
    return out


def _ols_slope(xs: list[float], ys: list[float]) -> float | None:
    """Ordinary-least-squares slope of ys on xs.  None if degenerate.

    Mirrors pfds._ols_slope: needs >=MIN_SLOPE_POINTS paired points and non-zero
    variance in xs.
    """
    n = len(xs)
    if n < MIN_SLOPE_POINTS or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    if sxx <= 0:
        return None
    return sxy / sxx


def _ols2(
    y: list[float],
    x1: list[float],
    x2: list[float],
) -> tuple[float, float, float, float] | None:
    """Two-regressor OLS with intercept:  y = b0 + b1*x1 + b2*x2.

    Solves the 3x3 normal equations (X'X) b = X'y directly (pure python, no
    numpy) and returns (b0, b1, b2, resid_sd) where resid_sd is the (population)
    standard deviation of the residuals y - yhat.

    Returns None if:
      * fewer than MIN_RESID_POINTS observations, or lengths mismatch,
      * the normal-equations matrix is singular (collinear / no variance).
    """
    n = len(y)
    if n < MIN_RESID_POINTS or len(x1) != n or len(x2) != n:
        return None

    # Build the symmetric 3x3 X'X and the 3-vector X'y.
    s_1 = float(n)
    s_x1 = sum(x1)
    s_x2 = sum(x2)
    s_x1x1 = sum(a * a for a in x1)
    s_x2x2 = sum(b * b for b in x2)
    s_x1x2 = sum(x1[i] * x2[i] for i in range(n))
    s_y = sum(y)
    s_x1y = sum(x1[i] * y[i] for i in range(n))
    s_x2y = sum(x2[i] * y[i] for i in range(n))

    # Augmented matrix [A | b] for Gaussian elimination with partial pivoting.
    A = [
        [s_1,   s_x1,   s_x2,   s_y],
        [s_x1,  s_x1x1, s_x1x2, s_x1y],
        [s_x2,  s_x1x2, s_x2x2, s_x2y],
    ]

    nrows = 3
    for col in range(nrows):
        # Partial pivot: largest |value| in this column at/below the diagonal.
        pivot_row = max(range(col, nrows), key=lambda r: abs(A[r][col]))
        if abs(A[pivot_row][col]) < 1e-12:
            return None  # singular
        if pivot_row != col:
            A[col], A[pivot_row] = A[pivot_row], A[col]
        pivot = A[col][col]
        # Normalise pivot row.
        for c in range(col, nrows + 1):
            A[col][c] /= pivot
        # Eliminate this column from all other rows.
        for r in range(nrows):
            if r == col:
                continue
            factor = A[r][col]
            if factor == 0.0:
                continue
            for c in range(col, nrows + 1):
                A[r][c] -= factor * A[col][c]

    b0, b1, b2 = A[0][3], A[1][3], A[2][3]

    # Residual standard deviation (population SD of residuals).
    ss = 0.0
    for i in range(n):
        yhat = b0 + b1 * x1[i] + b2 * x2[i]
        e = y[i] - yhat
        ss += e * e
    resid_sd = math.sqrt(ss / n)
    return (b0, b1, b2, resid_sd)


# ===========================================================================
# Case-level triad computation (pure once signals are aligned).
# ===========================================================================

def compute_triad(
    ce_samples: list[tuple[float, float]],
    bis_samples: list[tuple[float, float]],
    map_samples: list[tuple[float, float]],
    t_start: float,
    t_end: float,
    dt: float = ALIGN_DT_S,
    max_stale: float = MAX_STALE_S,
) -> dict[str, Any]:
    """Compute the full drug->brain->circulation triad for one case.

    Aligns Ce/BIS/MAP onto a common dt-grid (last-value-hold, staleness-capped),
    requires >=MIN_JOINT_POINTS jointly-usable points, then derives the five
    SPEC features.  Returns a dict over all SPEC names; if not jointly usable,
    drugbrain_available=0 and every other feature is None.
    """
    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["drugbrain_available"] = 0

    aligned = _align_grid(
        {"ce": ce_samples, "bis": bis_samples, "map": map_samples},
        t_start, t_end, dt=dt, max_stale=max_stale,
    )
    ce = aligned["ce"]
    bis = aligned["bis"]
    mp = aligned["map"]

    if len(ce) < MIN_JOINT_POINTS:
        return dict(none_row)

    row: dict[str, Any] = dict(none_row)
    row["drugbrain_available"] = 1

    # Cerebral drug potency: BIS vs Ce.
    ce_bis_slope = _ols_slope(ce, bis)
    row["drugbrain_ce_bis_slope"] = (
        round(ce_bis_slope, 6) if ce_bis_slope is not None else None
    )

    # Circulatory drug effect: MAP vs Ce.
    ce_map_slope = _ols_slope(ce, mp)
    row["drugbrain_ce_map_slope"] = (
        round(ce_map_slope, 6) if ce_map_slope is not None else None
    )

    # Headline fragility surface: ΔMAP per unit ΔBIS attributable to drug.
    if (
        ce_bis_slope is not None
        and ce_map_slope is not None
        and abs(ce_bis_slope) >= SLOPE_EPS
    ):
        row["drugbrain_map_per_bis_suppression"] = round(
            ce_map_slope / ce_bis_slope, 6
        )
    else:
        row["drugbrain_map_per_bis_suppression"] = None

    # Excess circulatory lability: residual SD of MAP ~ a + b*Ce + c*BIS.
    fit = _ols2(mp, ce, bis)
    if fit is not None:
        row["drugbrain_resid_instability"] = round(fit[3], 6)
    else:
        row["drugbrain_resid_instability"] = None

    return row


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract).
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for the drug->brain->circ triad.

    Downloads the propofol Ce, BIS and MAP numeric tracks per case (cached),
    clips to the intraop window [t_start, opend] (no t > opend), range-gates,
    aligns onto a common dt-grid and computes the five SPEC features.

    Honest missingness: if Ce or BIS or MAP is absent / not jointly usable
    (>=30 aligned points), drugbrain_available=0 and every other feature is None.
    Stdlib-only path throughout.
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float  # noqa: F401  (contract import)

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["drugbrain_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)
        if t_end is None:
            out[cid_str] = dict(none_row)
            continue

        # ---- propofol effect-site Ce (the DRUG) -----------------------------
        _ce_name, raw_ce = first_available(cfg, cid_str, CE_TRACK_CANDIDATES)
        if not raw_ce:
            out[cid_str] = dict(none_row)
            continue
        ce_samples = _clip_to_window(raw_ce, t_start, t_end)
        ce_samples = _filter_physiologic(ce_samples, CE_MIN, CE_MAX)

        # ---- BIS (the BRAIN) ------------------------------------------------
        _bis_name, raw_bis = first_available(cfg, cid_str, BIS_TRACK_CANDIDATES)
        if not raw_bis:
            out[cid_str] = dict(none_row)
            continue
        bis_samples = _clip_to_window(raw_bis, t_start, t_end)
        bis_samples = _filter_physiologic(bis_samples, BIS_MIN, BIS_MAX)

        # ---- MAP (the CIRCULATION) ------------------------------------------
        _map_name, raw_map = first_available(cfg, cid_str, MAP_TRACK_CANDIDATES)
        if not raw_map:
            out[cid_str] = dict(none_row)
            continue
        map_samples = _clip_to_window(raw_map, t_start, t_end)
        map_samples = _filter_physiologic(map_samples, MAP_MIN, MAP_MAX)

        out[cid_str] = compute_triad(
            ce_samples, bis_samples, map_samples, t_start, t_end
        )

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.drug_brain_circ
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

    print(f"drug_brain_circ validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case drug->brain->circ triad summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")

    n_avail = sum(1 for cid in cohort_ids if result.get(cid, {}).get("drugbrain_available"))
    print(f"\ndrugbrain_available in {n_avail}/{len(cohort_ids)} cases "
          "(pk-tier: needs BIS + propofol Ce pump -> TIVA/BIS subset)")
