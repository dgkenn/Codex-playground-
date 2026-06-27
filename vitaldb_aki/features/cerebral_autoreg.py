"""cerebral_autoreg.py -- Intraoperative cerebral autoregulation failure (§7F-novel).

UNMINED biomarker family that leverages the VitalDB BIS (processed-EEG) data to
operationalise **cerebral autoregulation failure as a 3-way CONDITIONAL coupling**
between cerebral electrical activity (EEG), arterial pressure (MAP), and
anesthetic effect-site concentration (propofol Ce).

Mechanism
---------
Under INTACT cerebral autoregulation, cerebral blood flow -- and therefore
cerebral electrical activity -- is held roughly constant across a wide MAP band,
so EEG is statistically INDEPENDENT of arterial pressure. When autoregulation
FAILS, perfusion becomes pressure-passive and EEG begins to TRACK MAP (the
classic Mx / COx "moving-correlation" picture: a sustained positive
MAP-cerebral-signal correlation is the hallmark of impaired autoregulation).

The honest catch: anesthetic depth (propofol Ce) ALSO drives EEG directly --
deeper anesthesia suppresses cortical activity (lowers SEF / BIS) independently
of perfusion. A naive MAP-EEG correlation is therefore confounded by the drug,
because Ce co-varies with both the pressure (vasodilation / myocardial
depression lower MAP) and the EEG (cortical suppression). The mechanistically
honest autoregulation-failure signal is the MAP-EEG association AFTER removing
the drug effect: the **partial correlation r(EEG, MAP | Ce)**.

EEG signal choice
-----------------
We prefer the **spectral edge frequency (BIS/SEF)** as the cerebral-activity
proxy -- it is a continuous EEG-derived quantity that falls with cortical
suppression and is less algorithmically smoothed than the BIS index. If SEF is
absent we fall back to the **BIS index (BIS/BIS)**. Either way the coupling is
computed identically; only the gate range differs.

Features (fset="pk" -- requires the BIS monitor, a VitalDB subset of ~5871 cases)
  cautoreg_available           1 if MAP & EEG(SEF or BIS) jointly usable, else 0
  cautoreg_eeg_map_corr        raw Pearson corr(EEG, MAP)  [confounded by drug]
  cautoreg_eeg_map_partial_ce  PARTIAL corr r(EEG,MAP|Ce)  [HEADLINE index];
                               None if propofol Ce track absent (cannot deconfound)
  cautoreg_cox_index           Mx/COx-style: mean of per-5-min-window corr(MAP,EEG)
  cautoreg_impaired_frac       fraction of 5-min windows with corr(MAP,EEG) > +0.3

LEAKAGE (§11)
-------------
All features are timing="intraop". The prediction cutoff is opend. No sample at
t > opend is ever used (window is [t_start, opend]). audit_specs() enforces the
no-postop firewall at import.

MISSINGNESS
-----------
If MAP OR EEG (SEF or BIS) is absent / not jointly usable for >=30 grid points,
cautoreg_available=0 and ALL other features are None (NOT 0). The partial-Ce
feature is additionally None whenever the propofol Ce pump track is absent, even
when MAP+EEG are present (you cannot control for a drug you did not measure).

Tracks (all NUMERIC, low-rate)
  MAP: Solar8000/ART_MBP -> Solar8000/NIBP_MBP -> EV1000/ART_MBP   gate 20-200
  EEG: BIS/SEF (preferred, gate 0-30)  ->  BIS/BIS (gate 0-100)
  Ce : Orchestra/PPF20_CE  gate >= 0

Protocol reference: §7F (raw / processed-EEG coupling), §7C (hemodynamic axis).
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
MAP_MIN: float = 20.0      # mmHg
MAP_MAX: float = 200.0     # mmHg
SEF_MIN: float = 0.0       # Hz -- spectral edge frequency floor
SEF_MAX: float = 30.0      # Hz -- spectral edge frequency ceiling
BIS_MIN: float = 0.0       # BIS index floor
BIS_MAX: float = 100.0     # BIS index ceiling
CE_MIN: float = 0.0        # ug/mL -- propofol effect-site concentration >= 0

# ---------------------------------------------------------------------------
# Alignment / analysis parameters (pre-registered).
# ---------------------------------------------------------------------------
ALIGN_DT_S: float = 10.0        # s -- common resampling grid step
MAX_STALE_S: float = 15.0       # s -- last-value-hold staleness cap (1.5 * dt)
MIN_JOINT_POINTS: int = 30      # minimum jointly-valid MAP+EEG points to compute
COX_WINDOW_S: float = 300.0     # s -- 5 min Mx/COx window
COX_MIN_WINDOWS: int = 2        # need >=2 windows for cox_index / impaired_frac
COX_MIN_POINTS_PER_WIN: int = 3 # min points to correlate within a window
IMPAIRED_CORR_THR: float = 0.3  # corr(MAP,EEG) > this = "actively impaired" window

# ---------------------------------------------------------------------------
# Track priorities (binding; NUMERIC tracks only).
# ---------------------------------------------------------------------------
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]
SEF_TRACK: str = "BIS/SEF"          # preferred EEG proxy (spectral edge freq)
BIS_TRACK: str = "BIS/BIS"          # fallback EEG proxy (BIS index)
PPF_CE_PUMP_TRACK: str = "Orchestra/PPF20_CE"

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11).
# All are "pk": they require the BIS processed-EEG monitor (a VitalDB subset).
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "cautoreg_available", "pk", "intraop",
        "1 if MAP and EEG (BIS/SEF preferred, else BIS/BIS) are jointly usable "
        "for cerebral-autoregulation coupling (>=30 aligned points), else 0",
    ),
    FeatureSpec(
        "cautoreg_eeg_map_corr", "pk", "intraop",
        "Raw Pearson correlation between EEG activity (SEF or BIS) and MAP over "
        "the aligned intraop grid; confounded by anesthetic depth (drug drives "
        "EEG), so interpret with the partial-Ce variant (§7F)",
    ),
    FeatureSpec(
        "cautoreg_eeg_map_partial_ce", "pk", "intraop",
        "HEADLINE autoregulation-failure index: PARTIAL correlation "
        "r(EEG,MAP|Ce) controlling for propofol effect-site Ce -- the MAP-EEG "
        "coupling AFTER removing the drug effect; |value| high = EEG tracks MAP "
        "independent of anesthetic depth = pressure-passive cerebral perfusion. "
        "None when the propofol Ce track is absent (cannot deconfound) (§7F)",
    ),
    FeatureSpec(
        "cautoreg_cox_index", "pk", "intraop",
        "Mx/COx-style autoregulation index: split intraop into consecutive 5-min "
        "windows, compute Pearson corr(MAP,EEG) per window, return the MEAN of "
        "those window correlations; sustained positive = impaired autoregulation. "
        "None if <2 valid windows (§7F)",
    ),
    FeatureSpec(
        "cautoreg_impaired_frac", "pk", "intraop",
        "Fraction of 5-min windows whose corr(MAP,EEG) > +0.3 (actively "
        "pressure-passive); high = autoregulation impaired for much of the case. "
        "None if <2 valid windows (§7F)",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Pure computational helpers (no I/O; stdlib only; unit-testable on synthetic
# series). NO numpy -- correlations / alignment are implemented from scratch.
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds._intraop_window so the leakage cutoff (t_end ==
    opend) is identical across modules. t_end is the prediction cutoff (§11);
    no sample at t > t_end is ever used.
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


def _align_grid(
    signals_dict: dict[str, list[tuple[float, float]]],
    t_start: float,
    t_end: float,
    dt: float = ALIGN_DT_S,
    max_stale: float = MAX_STALE_S,
) -> tuple[list[float], dict[str, list[float | None]]]:
    """Resample several irregular signals onto a common uniform time grid.

    Builds the grid t_start, t_start+dt, ... up to (and including, when it lands
    exactly on) t_end. Each signal is projected onto the grid by LAST-VALUE-HOLD:
    the value at grid time `g` is the most recent sample at or before `g`, but
    only if that sample is no more than `max_stale` seconds old; otherwise the
    grid cell is None ("stale", treated as missing for that signal).

    A grid point is JOINTLY VALID for a set of signals only when ALL of them are
    fresh (non-None) at that point. This function returns the raw per-signal grid
    (with Nones); callers extract jointly-valid subsets via _joint_valid().

    Pure: no I/O, no numpy. Each input series is sorted by time internally, so
    callers need not pre-sort.

    Parameters
    ----------
    signals_dict : {name: [(t, v), ...]}
        Irregular sample series. Empty / missing series yield an all-None column.
    t_start, t_end : float
        Grid bounds (seconds). If t_end <= t_start, returns ([], {name: []}).
    dt : float
        Grid step (seconds).
    max_stale : float
        Maximum age (seconds) of the held value; older => None.

    Returns
    -------
    (grid_times, columns)
        grid_times : list[float]            -- the uniform time axis
        columns    : {name: list[float|None]} -- one value per grid time per signal
    """
    names = list(signals_dict.keys())
    if t_end <= t_start or dt <= 0:
        return [], {nm: [] for nm in names}

    # Build the uniform grid. Use a small epsilon so a grid point landing
    # numerically just past t_end (floating accumulation) is not dropped.
    grid_times: list[float] = []
    n_steps = int(math.floor((t_end - t_start) / dt + 1e-9))
    for k in range(n_steps + 1):
        g = t_start + k * dt
        if g > t_end + 1e-9:
            break
        grid_times.append(g)

    # Pre-sort each signal once.
    sorted_signals: dict[str, list[tuple[float, float]]] = {
        nm: sorted(signals_dict[nm], key=lambda x: x[0]) for nm in names
    }

    def _last_val(sorted_s: list[tuple[float, float]], g: float) -> float | None:
        """Binary-search last-value-hold at or before g, within max_stale."""
        lo, hi = 0, len(sorted_s)
        while lo < hi:
            mid = (lo + hi) // 2
            if sorted_s[mid][0] <= g:
                lo = mid + 1
            else:
                hi = mid
        idx = lo - 1
        if idx < 0:
            return None
        st, sv = sorted_s[idx]
        if g - st > max_stale:
            return None
        return sv

    columns: dict[str, list[float | None]] = {nm: [] for nm in names}
    for g in grid_times:
        for nm in names:
            columns[nm].append(_last_val(sorted_signals[nm], g))
    return grid_times, columns


def _joint_valid(
    grid_times: list[float],
    columns: dict[str, list[float | None]],
    names: list[str],
) -> tuple[list[float], dict[str, list[float]]]:
    """Restrict aligned columns to grid points where ALL `names` are non-None.

    Returns (kept_times, {name: [values...]}) with every per-name list the same
    length (the jointly-valid count). Pure; no numpy.
    """
    kept_times: list[float] = []
    kept: dict[str, list[float]] = {nm: [] for nm in names}
    n = len(grid_times)
    for i in range(n):
        vals = [columns[nm][i] for nm in names]
        if any(v is None for v in vals):
            continue
        kept_times.append(grid_times[i])
        for nm, v in zip(names, vals):
            kept[nm].append(v)  # type: ignore[arg-type]
    return kept_times, kept


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient of two equal-length series.

    Returns None if fewer than 3 paired points or either series is constant
    (zero variance => correlation undefined). Pure; no numpy.
    """
    n = len(xs)
    if n != len(ys) or n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    r = sxy / math.sqrt(sxx * syy)
    # Clamp tiny floating overshoot into [-1, 1].
    if r > 1.0:
        r = 1.0
    elif r < -1.0:
        r = -1.0
    return r


def _partial_corr(e: list[float], m: list[float], c: list[float]) -> float | None:
    """Partial correlation of e (EEG) with m (MAP) controlling for c (Ce).

        r(e,m | c) = (r_em - r_ec * r_mc) / sqrt((1 - r_ec^2) * (1 - r_mc^2))

    Returns None if any required pairwise Pearson correlation is undefined, or if
    a controlling variable is collinear with another (denominator -> 0). Pure.
    """
    n = len(e)
    if n != len(m) or n != len(c) or n < 3:
        return None
    r_em = _pearson(e, m)
    r_ec = _pearson(e, c)
    r_mc = _pearson(m, c)
    if r_em is None or r_ec is None or r_mc is None:
        return None
    denom_sq = (1.0 - r_ec * r_ec) * (1.0 - r_mc * r_mc)
    if denom_sq <= 0.0:
        return None
    r = (r_em - r_ec * r_mc) / math.sqrt(denom_sq)
    if r > 1.0:
        r = 1.0
    elif r < -1.0:
        r = -1.0
    return r


def _windowed_corr_mean(
    grid_times: list[float],
    eeg: list[float],
    map_: list[float],
    win_s: float = COX_WINDOW_S,
) -> tuple[float | None, float | None]:
    """Mx/COx-style windowed correlation summary over consecutive `win_s` windows.

    Splits the (jointly-valid) aligned series into consecutive non-overlapping
    windows of `win_s` seconds (anchored at grid_times[0]), computes Pearson
    corr(MAP, EEG) within each window that has >= COX_MIN_POINTS_PER_WIN points,
    and returns:

        (cox_index, impaired_frac)

      cox_index     = MEAN of the per-window correlations (sustained positive =
                      impaired autoregulation). None if < COX_MIN_WINDOWS valid
                      windows produced a defined correlation.
      impaired_frac = fraction of valid windows whose correlation > IMPAIRED_CORR_THR.
                      None under the same <COX_MIN_WINDOWS condition.

    `grid_times`, `eeg`, `map_` must be the same length and time-ordered. Pure.
    """
    n = len(grid_times)
    if n == 0 or n != len(eeg) or n != len(map_) or win_s <= 0:
        return None, None

    t0 = grid_times[0]
    # Bucket indices by window number.
    buckets: dict[int, list[int]] = {}
    for i in range(n):
        w = int(math.floor((grid_times[i] - t0) / win_s))
        buckets.setdefault(w, []).append(i)

    window_corrs: list[float] = []
    for w in sorted(buckets):
        idxs = buckets[w]
        if len(idxs) < COX_MIN_POINTS_PER_WIN:
            continue
        wm = [map_[i] for i in idxs]
        we = [eeg[i] for i in idxs]
        r = _pearson(wm, we)
        if r is not None:
            window_corrs.append(r)

    if len(window_corrs) < COX_MIN_WINDOWS:
        return None, None

    cox_index = sum(window_corrs) / len(window_corrs)
    impaired_frac = sum(1 for r in window_corrs if r > IMPAIRED_CORR_THR) / len(window_corrs)
    return cox_index, impaired_frac


# ===========================================================================
# Case-level computation (pure; operates on already-clipped/gated series).
# ===========================================================================

def compute_cerebral_autoreg(
    map_samples: list[tuple[float, float]],
    eeg_samples: list[tuple[float, float]],
    ce_samples: list[tuple[float, float]],
    t_start: float,
    t_end: float,
) -> dict[str, Any]:
    """Compute all cerebral-autoregulation features for one case.

    Inputs are physiologic-gated, window-clipped (t, v) series. `ce_samples`
    may be empty (no propofol Ce track) -- then the partial-Ce feature is None
    but the others are still computed.

    Returns a dict with every SPECS key. cautoreg_available is 0 with all other
    features None when MAP+EEG are not jointly usable for >= MIN_JOINT_POINTS.
    """
    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["cautoreg_available"] = 0

    if t_end <= t_start:
        return dict(none_row)
    if len(map_samples) < 2 or len(eeg_samples) < 2:
        return dict(none_row)

    # Align MAP, EEG (and Ce if present) onto a common grid.
    signals: dict[str, list[tuple[float, float]]] = {
        "map": map_samples,
        "eeg": eeg_samples,
    }
    has_ce = len(ce_samples) >= 2
    if has_ce:
        signals["ce"] = ce_samples

    grid_times, columns = _align_grid(signals, t_start, t_end)

    # Joint MAP+EEG validity drives availability.
    em_times, em_cols = _joint_valid(grid_times, columns, ["map", "eeg"])
    if len(em_times) < MIN_JOINT_POINTS:
        return dict(none_row)

    map_vals = em_cols["map"]
    eeg_vals = em_cols["eeg"]

    row: dict[str, Any] = dict(none_row)
    row["cautoreg_available"] = 1

    # Raw EEG-MAP correlation (confounded by drug).
    raw = _pearson(eeg_vals, map_vals)
    row["cautoreg_eeg_map_corr"] = round(raw, 6) if raw is not None else None

    # Partial correlation controlling for Ce (headline) -- requires Ce track.
    if has_ce:
        emc_times, emc_cols = _joint_valid(grid_times, columns, ["map", "eeg", "ce"])
        if len(emc_times) >= MIN_JOINT_POINTS:
            partial = _partial_corr(emc_cols["eeg"], emc_cols["map"], emc_cols["ce"])
            row["cautoreg_eeg_map_partial_ce"] = (
                round(partial, 6) if partial is not None else None
            )
    # else: leave None (cannot control for a drug we did not measure).

    # Mx/COx windowed index + impaired fraction (use the MAP+EEG joint grid).
    cox_index, impaired_frac = _windowed_corr_mean(em_times, eeg_vals, map_vals)
    row["cautoreg_cox_index"] = round(cox_index, 6) if cox_index is not None else None
    row["cautoreg_impaired_frac"] = (
        round(impaired_frac, 6) if impaired_frac is not None else None
    )

    return row


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract).
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for cerebral-autoregulation features.

    Downloads MAP, EEG (BIS/SEF preferred, else BIS/BIS), and propofol Ce tracks
    per case (cached).  When MAP or EEG is absent / not jointly usable for
    >= MIN_JOINT_POINTS aligned points, cautoreg_available=0 and every other
    feature is None.  The partial-Ce feature is additionally None when the
    propofol Ce track is absent.

    NUMERIC tracks only (no packed waveforms); stdlib-only compute path.
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float  # noqa: F401  (contract import)

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["cautoreg_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)
        if t_start is None or t_end is None or t_end <= t_start:
            # Cannot build a leakage-safe window -> treat as unavailable.
            out[cid_str] = dict(none_row)
            continue

        # ---- MAP track ------------------------------------------------------
        _map_tname, raw_map = first_available(cfg, cid_str, MAP_TRACK_CANDIDATES)
        if not raw_map:
            out[cid_str] = dict(none_row)
            continue
        map_samples = _clip_to_window(raw_map, t_start, t_end)
        map_samples = _filter_physiologic(map_samples, MAP_MIN, MAP_MAX)
        if len(map_samples) < 2:
            out[cid_str] = dict(none_row)
            continue

        # ---- EEG track: prefer SEF (0-30) then BIS index (0-100) ------------
        eeg_samples: list[tuple[float, float]] = []
        raw_sef = download_track(cfg, cid_str, SEF_TRACK)
        if raw_sef:
            sef = _clip_to_window(raw_sef, t_start, t_end)
            sef = _filter_physiologic(sef, SEF_MIN, SEF_MAX)
            if len(sef) >= 2:
                eeg_samples = sef
        if not eeg_samples:
            raw_bis = download_track(cfg, cid_str, BIS_TRACK)
            if raw_bis:
                bis = _clip_to_window(raw_bis, t_start, t_end)
                bis = _filter_physiologic(bis, BIS_MIN, BIS_MAX)
                if len(bis) >= 2:
                    eeg_samples = bis
        if len(eeg_samples) < 2:
            out[cid_str] = dict(none_row)
            continue

        # ---- Propofol Ce track (to control for drug; may be absent) ---------
        ce_samples: list[tuple[float, float]] = []
        raw_ce = download_track(cfg, cid_str, PPF_CE_PUMP_TRACK)
        if raw_ce:
            ce = _clip_to_window(raw_ce, t_start, t_end)
            ce_samples = [(t, v) for t, v in ce if v >= CE_MIN]

        out[cid_str] = compute_cerebral_autoreg(
            map_samples, eeg_samples, ce_samples, t_start, t_end
        )

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.cerebral_autoreg
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

    print(f"cerebral_autoreg validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case cerebral-autoregulation summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")

    n_avail = sum(1 for cid in cohort_ids if result.get(cid, {}).get("cautoreg_available"))
    n_partial = sum(
        1 for cid in cohort_ids
        if result.get(cid, {}).get("cautoreg_eeg_map_partial_ce") is not None
    )
    print(f"\nBIS-usable (cautoreg_available=1): {n_avail}/{len(cohort_ids)}")
    print(f"Partial-Ce computable (propofol Ce present): {n_partial}/{len(cohort_ids)}")
