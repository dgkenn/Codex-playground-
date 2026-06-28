"""bp_variability.py -- Blood-pressure VARIABILITY and physiologic COMPLEXITY.

This module is deliberately ORTHOGONAL to the hemodynamics module. The
hemodynamics family already captures the *level* of pressure (mean MAP, time/
area below 65, minima). The thesis here is different and well-supported in the
perioperative/critical-care literature:

  **It is not only how LOW the pressure goes, but how it MOVES.**

Two patients can share an identical mean MAP yet differ wildly in beat-to-beat
behaviour: one tracks a smooth, gently-regulated curve; the other oscillates
erratically (loss of autonomic buffering) or, conversely, becomes pathologically
*rigid/monotonous* (loss of physiologic complexity -- a hallmark of failing
homeostatic control). Both extremes carry end-organ risk that a mean cannot see.

This module operationalises two complementary axes, computed independently of
mean pressure:

  1. VARIABILITY -- dispersion and successive-difference metrics of the MAP/HR
     time-series (SD, CV, ARV, RMSSD). ARV (Average Real Variability) is the
     headline metric: the mean absolute successive difference, which is robust
     to outliers and is the standard BP-variability index in the hypertension /
     perioperative literature.

  2. COMPLEXITY-LOSS -- Sample Entropy (SampEn). LOWER SampEn == more regular /
     less complex / more predictable signal, which paradoxically flags a SICKER
     physiology (reduced regulatory richness). Higher SampEn == more irregular.

CV (SD/mean) carries a whiff of the mean, but it is the SHAPE-normalised
dispersion -- it is included precisely because it removes mean scaling, making it
a variability ratio rather than a level. The mean itself is never returned.

LEAKAGE (Sec 11)
----------------
All features are timing="intraop". The prediction cutoff is opend. No sample at
t > opend is ever used (the window is [t_start, opend], copied verbatim from
pfds._intraop_window + _clip_to_window). audit_specs() enforces no-postop at
import.

MISSINGNESS
-----------
If no usable MAP track is present (or < MIN_SAMPLES in-window samples), ALL
features are None and bpv_available == 0 (an int flag, NOT None). HR features
are computed only when the HR track is present and has >= MIN_SAMPLES samples;
when HR is absent the HR features are None even if MAP is fine. This mirrors the
pfds missing-track convention exactly.

NUMERICS
--------
Sample Entropy is the classic Richman-Moorman template-matching estimator. The
O(n^2) template match is NUMPY-vectorized (lazily imported inside the function so
the stdlib-only integrity core is unaffected); the result is bit-equivalent to
the prior pure-Python pair counting. For tractability the input series is first
capped to MAX_SAMPEN_LEN points by a uniform stride (decimation) -- documented at
_uniform_cap -- which bounds both the time and the O(n^2) memory of the match
matrix. Degenerate (constant / SD ~ 0) and too-short series are guarded BEFORE
the match so a flat MAP/HR record can never hang the extraction (see
_sample_entropy guards).

TRACK PRIORITIES (binding)
  MAP: Solar8000/ART_MBP -> Solar8000/NIBP_MBP -> EV1000/ART_MBP
  HR:  Solar8000/HR -> Solar8000/PLETH_HR

Protocol reference: §7C (variability companion to hemodynamics level metrics).
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range constants (binding; artifact gates)
# ---------------------------------------------------------------------------
MAP_MIN: float = 20.0     # mmHg -- artifact gate
MAP_MAX: float = 200.0    # mmHg -- artifact gate
HR_MIN: float = 20.0      # bpm -- artifact gate
HR_MAX: float = 220.0     # bpm -- artifact gate

# Minimum in-window samples required to compute any variability metric.
MIN_SAMPLES: int = 30

# Sample Entropy parameters (pre-registered; classic Richman & Moorman 2000).
SAMPEN_M: int = 2          # embedding dimension
SAMPEN_R_FRAC: float = 0.2  # tolerance r = SAMPEN_R_FRAC * SD(series)

# Cap on series length before the SampEn template match (uniform stride).
# Lowered from 3000 -> 2000: the template match is now numpy-vectorized but is
# still O(n^2) in MEMORY (it materialises an n x n match matrix), so the cap
# bounds peak memory as well as time. 2000 points still capture the full
# temporal shape of an intraop record after uniform decimation.
MAX_SAMPEN_LEN: int = 2000

MAX_INTER_SAMPLE_DT_S: float = 10.0  # s -- (unused by stats but kept for parity)

# Track priorities (binding)
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]
HR_TRACK_CANDIDATES: list[str] = [
    "Solar8000/HR",
    "Solar8000/PLETH_HR",
]

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11)
# First spec MUST be bpv_available.
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "bpv_available", "comprehensive", "intraop",
        "1 if MAP track usable for BP-variability computation "
        f"(>= {MIN_SAMPLES} in-window physiologic samples), else 0",
    ),
    # ---- MAP variability ---------------------------------------------------
    FeatureSpec(
        "bpv_map_sd", "comprehensive", "intraop",
        "Standard deviation of intraop MAP (mmHg); raw dispersion of pressure "
        "about its own mean",
    ),
    FeatureSpec(
        "bpv_map_cv", "comprehensive", "intraop",
        "Coefficient of variation of MAP (SD/mean); mean-normalised dispersion "
        "-- a variability ratio that removes pressure-level scaling",
    ),
    FeatureSpec(
        "bpv_map_arv", "comprehensive", "intraop",
        "Average Real Variability of MAP: mean of |MAP[i+1]-MAP[i]| over "
        "successive in-window samples (time-ordered). Headline BP-variability "
        "metric; robust to outliers vs SD",
    ),
    FeatureSpec(
        "bpv_map_succ_var", "comprehensive", "intraop",
        "Root-mean-square of successive MAP differences (RMSSD); emphasises "
        "beat-to-beat jumps more than ARV",
    ),
    FeatureSpec(
        "bpv_map_sampen", "comprehensive", "intraop",
        "Sample Entropy of MAP (m=2, r=0.2*SD; uniform-decimated to <=2000 pts). "
        "LOWER = more regular / less complex (loss of physiologic complexity)",
    ),
    # ---- HR variability ----------------------------------------------------
    FeatureSpec(
        "bpv_hr_sd", "comprehensive", "intraop",
        "Standard deviation of intraop HR (bpm); None if HR track absent",
    ),
    FeatureSpec(
        "bpv_hr_arv", "comprehensive", "intraop",
        "Average Real Variability of HR: mean of |HR[i+1]-HR[i]| over "
        "successive in-window samples; None if HR track absent",
    ),
    FeatureSpec(
        "bpv_hr_sampen", "comprehensive", "intraop",
        "Sample Entropy of HR (m=2, r=0.2*SD; uniform-decimated to <=2000 pts). "
        "LOWER = more regular. None if HR track absent",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Window helper (copied verbatim from pfds._intraop_window -- binding contract)
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
# Pure variability / complexity helpers (no I/O; unit-testable on synthetic
# series).  These take a plain list[float] of VALUES already in time order.
# ===========================================================================

def _mean(series: list[float]) -> float | None:
    """Arithmetic mean; None if empty."""
    if not series:
        return None
    return sum(series) / len(series)


def _sd(series: list[float]) -> float | None:
    """Population standard deviation.  None if < 2 samples."""
    n = len(series)
    if n < 2:
        return None
    m = sum(series) / n
    var = sum((x - m) ** 2 for x in series) / n
    return math.sqrt(var)


def _cv(series: list[float]) -> float | None:
    """Coefficient of variation = SD / |mean|.  None if < 2 samples or mean ~= 0."""
    sd = _sd(series)
    if sd is None:
        return None
    m = _mean(series)
    if m is None or abs(m) < 1e-9:
        return None
    return sd / abs(m)


def _arv(series: list[float]) -> float | None:
    """Average Real Variability = mean of |x[i+1]-x[i]| over successive samples.

    Requires the series to be in time order (the caller guarantees this by
    sorting the in-window samples by timestamp before extracting values).
    None if < 2 samples.
    """
    n = len(series)
    if n < 2:
        return None
    total = 0.0
    for i in range(n - 1):
        total += abs(series[i + 1] - series[i])
    return total / (n - 1)


def _rmssd(series: list[float]) -> float | None:
    """Root-mean-square of successive differences.  None if < 2 samples."""
    n = len(series)
    if n < 2:
        return None
    ss = 0.0
    for i in range(n - 1):
        d = series[i + 1] - series[i]
        ss += d * d
    return math.sqrt(ss / (n - 1))


def _uniform_cap(series: list[float], maxlen: int = MAX_SAMPEN_LEN) -> list[float]:
    """Uniformly decimate `series` to at most `maxlen` points by integer stride.

    Sample Entropy is O(n^2) in pure Python; for long intraop records (tens of
    thousands of samples) that is intractable. We therefore cap the series to
    `maxlen` points BEFORE the template match using a uniform stride (every
    k-th sample, k = ceil(n / maxlen)). Uniform striding preserves the overall
    temporal structure / shape far better than truncation and keeps the cap
    deterministic. If len(series) <= maxlen the series is returned unchanged.
    """
    n = len(series)
    if maxlen <= 0 or n <= maxlen:
        return list(series)
    stride = (n + maxlen - 1) // maxlen   # ceil(n / maxlen)
    return series[::stride]


def _sample_entropy(
    series: list[float],
    m: int = SAMPEN_M,
    r: float | None = None,
) -> float | None:
    """Sample Entropy (Richman & Moorman 2000), NUMPY-vectorized.

    SampEn = -ln( A / B ) where
      B = average fraction of length-m template pairs within Chebyshev distance r
      A = average fraction of length-(m+1) template pairs within distance r
    (self-matches excluded).  A and B are normalised by the number of available
    templates at each length so that a perfectly constant series gives A/B == 1
    exactly (SampEn == 0); the raw pair COUNTS differ between lengths m and m+1
    purely because there is one fewer template at the longer length, which would
    leave a constant series at a small non-zero value -- the normalisation is the
    standard Richman & Moorman correction.

    Implementation
    --------------
    The double Python loop over template pairs is replaced by numpy. For each
    embedding length mm we build the (last x mm) matrix of templates and form the
    per-pair Chebyshev distance via broadcasting; pairs (i<j) within r are counted
    with a boolean upper-triangular mask. The result is bit-equivalent to the old
    pure-Python counting (integer pair counts; same normalisation), so SampEn
    matches to floating-point round-off (~1e-12). numpy is lazily imported here so
    the stdlib-only integrity core is unaffected.

    Parameters
    ----------
    series : list[float]
        Values in time order. Capped to MAX_SAMPEN_LEN by uniform stride first.
    m : int
        Embedding dimension (default 2).
    r : float | None
        Tolerance. If None, r is set to SAMPEN_R_FRAC * SD(series) (the standard
        choice). If SD is 0 (constant series) the tolerance is 0.

    Returns
    -------
    float | None
        SampEn value. LOWER == more regular / less complex.
        Returns None when the series is too short (< m + 2 after capping) or
        when the statistic is undefined (no matched templates).

    Guards (poison-pill protection; evaluated BEFORE the O(n^2) match)
    -----------------------------------------------------------------
      * SHORT: if the capped series has < m + 2 valid finite points the
        statistic is undefined -> return None. (m + 2 is the Richman-Moorman
        minimum: at least 2 templates at length m+1.)
      * NON-FINITE: NaN / inf samples are dropped before the cap; if too few
        finite points remain -> None.
      * DEGENERATE / (near-)CONSTANT: a flat MAP/HR series (SD ~ 0, or every
        pair within r) is the pathological case that made the old naive counter
        pathological (every one of the ~n^2/2 pairs matches). When SD <= 0 the
        series is perfectly constant: every length-(m) and length-(m+1) pair
        matches, so A == B and SampEn == 0.0 -- we return 0.0 immediately
        WITHOUT building any match matrix. This is the poison-pill fix.

    Other edge cases:
      * A highly irregular / noisy series produces few length-(m+1) matches, so
        A << B and SampEn is large.
    """
    import numpy as np

    # ---- finite filter + cap (guards run before any O(n^2) work) ------------
    arr = np.asarray(series, dtype=float)
    if arr.ndim != 1:
        arr = arr.ravel()
    arr = arr[np.isfinite(arr)]
    capped = _uniform_cap(arr.tolist(), MAX_SAMPEN_LEN)
    n = len(capped)
    if n < m + 2:
        # SHORT guard: too few valid points for a defined statistic.
        return None

    x = np.asarray(capped, dtype=float)

    if r is None:
        sd = _sd(capped)
        r = (SAMPEN_R_FRAC * sd) if sd is not None else 0.0
    else:
        sd = _sd(capped)

    # ---- DEGENERATE / (near-)constant fast path -----------------------------
    # A perfectly constant series (SD == 0) has every template pair matching at
    # any r >= 0, so A == B and SampEn == 0 exactly. The old pure-Python counter
    # would still walk all ~n^2/2 pairs here (the poison case on a flat MAP/HR
    # series); we short-circuit to 0.0 without touching the match matrix.
    if sd is not None and sd <= 0.0:
        return 0.0

    def _matched_pairs(mm: int) -> tuple[int, int]:
        """(matched_pairs, total_pairs) for length-mm templates (i<j), vectorized.

        Counted ROW BY ROW to keep memory O(last) rather than O(last^2 * mm):
        for template i we compare it against all templates j > i at once
        (broadcast over the mm lags) and add the within-r count. This avoids
        materialising the full last x last x mm distance cube (which is both
        memory-heavy and, at n~2000, slower than the loop).
        """
        last = n - mm + 1   # number of length-mm templates
        if last < 2:
            return 0, 0
        # templates[i] = x[i:i+mm]; shape (last, mm) via a sliding window.
        templates = np.lib.stride_tricks.sliding_window_view(x, mm)[:last]
        matched = 0
        for i in range(last - 1):
            rest = templates[i + 1:]                       # (last-1-i, mm)
            # Chebyshev distance of template i to every later template.
            dist = np.abs(rest - templates[i]).max(axis=1)  # (last-1-i,)
            matched += int(np.count_nonzero(dist <= r))
        total = last * (last - 1) // 2
        return matched, total

    b_cnt, b_tot = _matched_pairs(m)
    if b_tot == 0 or b_cnt == 0:
        # No length-m template matches (or no templates) -> statistic undefined.
        return None
    # DEGENERATE all-match fast path: when EVERY length-m pair already matches
    # (a flat/near-flat series whose spread fits inside r = 0.2*SD), every
    # length-(m+1) pair matches too, so A == B and SampEn == 0 exactly. Skip the
    # second (a) match matrix. This is the other face of the poison case: the old
    # naive counter walked all ~n^2/2 pairs with the inner loop never breaking.
    if b_cnt == b_tot:
        return 0.0

    a_cnt, a_tot = _matched_pairs(m + 1)

    if a_tot == 0:
        return None
    if a_cnt == 0:
        # Matches at length m but none extend to m+1: maximal irregularity.
        # SampEn -> +inf in the limit; report None (undefined / unbounded).
        return None
    # Normalised average match fractions (Richman & Moorman).
    b = b_cnt / b_tot
    a = a_cnt / a_tot
    return -math.log(a / b)


def _ordered_values(samples: list[tuple[float, float]]) -> list[float]:
    """Sort (t, v) samples by time and return the value sequence in time order."""
    return [v for _, v in sorted(samples, key=lambda x: x[0])]


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all BP-variability biomarkers.

    Downloads MAP/HR tracks per case (cached). When MAP is absent or has
    < MIN_SAMPLES in-window physiologic samples, bpv_available == 0 and every
    other feature is None. HR features are None when the HR track is absent or
    too short, independent of MAP.
    """
    from vitaldb_aki.data.tracks import download_track, first_available  # noqa: F401
    from vitaldb_aki.data.client import to_float  # noqa: F401

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["bpv_available"] = 0

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
        map_samples = _filter_physiologic(map_samples, MAP_MIN, MAP_MAX)
        if len(map_samples) < MIN_SAMPLES:
            out[cid_str] = dict(none_row)
            continue

        row: dict[str, Any] = dict(none_row)
        row["bpv_available"] = 1

        map_vals = _ordered_values(map_samples)
        row["bpv_map_sd"] = _round(_sd(map_vals))
        row["bpv_map_cv"] = _round(_cv(map_vals))
        row["bpv_map_arv"] = _round(_arv(map_vals))
        row["bpv_map_succ_var"] = _round(_rmssd(map_vals))
        row["bpv_map_sampen"] = _round(_sample_entropy(map_vals))

        # ---- HR track (independent of MAP) ----------------------------------
        _hr_tname, raw_hr = first_available(cfg, cid_str, HR_TRACK_CANDIDATES)
        if raw_hr:
            hr_samples = _clip_to_window(raw_hr, t_start, t_end)
            hr_samples = _filter_physiologic(hr_samples, HR_MIN, HR_MAX)
            if len(hr_samples) >= MIN_SAMPLES:
                hr_vals = _ordered_values(hr_samples)
                row["bpv_hr_sd"] = _round(_sd(hr_vals))
                row["bpv_hr_arv"] = _round(_arv(hr_vals))
                row["bpv_hr_sampen"] = _round(_sample_entropy(hr_vals))

        out[cid_str] = row

    return out


def _round(v: float | None, ndigits: int = 6) -> float | None:
    """Round a value, passing None through unchanged."""
    return None if v is None else round(v, ndigits)


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.bp_variability
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

    print(f"BP-variability validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case BP-variability summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
