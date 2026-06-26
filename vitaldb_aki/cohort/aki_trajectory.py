"""aki_trajectory.py -- persistent vs transient AKI sub-phenotyping (Tier-1 idea #3).

Pre-specified definition (cite KDIGO 2012 and Kellum 2015 AKI transient/persistent):
  - TRANSIENT AKI ("pre-renal / hemodynamic"): creatinine rises to AKI threshold,
    then a LATER postop measurement demonstrates RECOVERY before or by 72 h after the
    anchor (end of surgery). Recovery = cr returns to < 1.5x baseline AND within
    0.3 mg/dL of baseline on a measurement taken between RECOVERY_EARLY_H and
    RECOVERY_LATE_H hours after the anchor.
  - PERSISTENT AKI ("intrinsic / structural"): remains >= 1.5x baseline OR >=
    baseline + 0.3 mg/dL on ALL late measurements beyond RECOVERY_LATE_H hours
    (i.e. no documented recovery within the 7-day window).
  - INDETERMINATE: AKI-positive but no creatinine measured in the recovery window
    (between RECOVERY_EARLY_H and RECOVERY_LATE_H hours) — cannot adjudicate.
    This bucket will be sizeable in VitalDB because many cases have few postop creatinines.

Window constants (pre-specified; do not change after data look):
  RECOVERY_EARLY_H = 24   -- minimum hours before checking for recovery (allow peak to develop)
  RECOVERY_LATE_H  = 72   -- must have recovered BY this hour (48-72h per KDIGO-recovery literature)
  KDIGO_WINDOW_H   = 168  -- outer AKI labeling window (7 days); used to bound series

Reference: Kellum JA et al. "The concept of acute kidney disease" (Kidney Int 2017);
  KDIGO AKI Work Group (KDIGO 2012 guidelines, Kidney Int Suppl);
  Uchino S et al. transient vs persistent AKI (JASN 2010);
  Chawla LS et al. "Acute Kidney Disease and Renal Recovery" (JASN 2017).

stdlib only; no numpy/pandas dependency — unit-testable with no creds/network.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---- Pre-specified window constants -----------------------------------------
RECOVERY_EARLY_H: float = 24.0   # earliest hour post-anchor to count as a recovery measurement
RECOVERY_LATE_H: float = 72.0    # must have recovery documented BY this hour
KDIGO_WINDOW_H: float = 168.0    # outer AKI window (7 days); consistent with config.yaml

_H = 3600.0  # seconds per hour

TrajectoryLabel = str   # "transient" | "persistent" | "indeterminate"


@dataclass
class TrajectoryResult:
    """Result of classify_trajectory for one AKI-positive case."""
    label: TrajectoryLabel          # "transient" | "persistent" | "indeterminate"
    peak_cr: float | None           # peak postop creatinine (any measurement in KDIGO window)
    peak_cr_dt_h: float | None      # time of peak (hours after anchor)
    recovery_cr: float | None       # creatinine at recovery measurement (or None)
    recovery_dt_h: float | None     # time of recovery measurement (hours after anchor) or None
    n_postop_cr: int                # total measurements in series
    n_in_recovery_window: int       # measurements in [RECOVERY_EARLY_H, RECOVERY_LATE_H]
    reason: str                     # human-readable explanation


def classify_trajectory(
    baseline: float,
    postop_cr_series: list[tuple[float, float]],   # [(dt_seconds_after_anchor, cr_mgdl), ...]
    cfg: dict[str, Any] | None = None,
) -> TrajectoryResult:
    """Classify one AKI-positive case as transient, persistent, or indeterminate.

    Parameters
    ----------
    baseline:
        Preoperative creatinine baseline (mg/dL); must be > 0.
    postop_cr_series:
        List of (dt_seconds_after_anchor, cr_mgdl) pairs, sorted or unsorted.
        Only measurements within KDIGO_WINDOW_H are used.
    cfg:
        Optional config dict (not currently used; reserved for future tuning
        of window constants without code changes). If supplied, the keys
        ``recovery_early_h``, ``recovery_late_h``, and ``kdigo_window_h``
        under an ``aki_trajectory`` block will override module-level constants.

    Returns
    -------
    TrajectoryResult with label, diagnostic details, and reason string.

    Notes
    -----
    The caller is responsible for pre-filtering the series to AKI-positive cases
    (KDIGO label == 1). Passing a non-AKI case will likely produce "indeterminate"
    because no postop measurement exceeds recovery thresholds.
    """
    if baseline is None or baseline <= 0:
        return TrajectoryResult("indeterminate", None, None, None, None, 0, 0,
                                "invalid baseline")

    # Override windows from cfg if provided
    early_h = RECOVERY_EARLY_H
    late_h = RECOVERY_LATE_H
    outer_h = KDIGO_WINDOW_H
    if cfg is not None:
        tcfg = cfg.get("aki_trajectory", {})
        early_h = float(tcfg.get("recovery_early_h", early_h))
        late_h = float(tcfg.get("recovery_late_h", late_h))
        outer_h = float(tcfg.get("kdigo_window_h", outer_h))

    # Filter to outer window
    series = [(dt, v) for dt, v in postop_cr_series if 0 < dt <= outer_h * _H]
    n_total = len(series)

    if not series:
        return TrajectoryResult("indeterminate", None, None, None, None, 0, 0,
                                "no postop creatinine in window")

    # Peak across entire window
    peak_cr = max(v for _, v in series)
    peak_dt_h = next(dt / _H for dt, v in sorted(series, key=lambda x: -x[1]) if v == peak_cr)

    # Recovery window measurements
    recovery_series = [(dt, v) for dt, v in series if early_h * _H <= dt <= late_h * _H]
    n_in_rec = len(recovery_series)

    # Recovery criterion: cr < 1.5x baseline AND within 0.3 mg/dL of baseline
    abs_thr = baseline + 0.3
    rel_thr = baseline * 1.5

    if not recovery_series:
        # No measurement in the recovery window -> indeterminate
        return TrajectoryResult(
            "indeterminate", peak_cr, peak_dt_h, None, None, n_total, n_in_rec,
            f"no creatinine between {early_h:.0f} and {late_h:.0f} h; cannot adjudicate recovery",
        )

    # Check if ANY measurement in the recovery window satisfies both recovery criteria
    recovered = [(dt, v) for dt, v in recovery_series if v < rel_thr and v < abs_thr]

    if recovered:
        # Take the earliest qualifying recovery measurement
        rec_dt, rec_v = sorted(recovered, key=lambda x: x[0])[0]
        return TrajectoryResult(
            "transient", peak_cr, peak_dt_h, rec_v, rec_dt / _H, n_total, n_in_rec,
            f"peak {peak_cr:.2f} mg/dL at {peak_dt_h:.1f}h; recovered to {rec_v:.2f} "
            f"mg/dL at {rec_dt/_H:.1f}h (< 1.5x baseline and within 0.3 mg/dL of baseline)",
        )
    else:
        # Has measurements in the recovery window but none satisfy recovery
        min_rec = min(v for _, v in recovery_series)
        min_rec_dt = next(dt for dt, v in recovery_series if v == min_rec)
        return TrajectoryResult(
            "persistent", peak_cr, peak_dt_h, min_rec, min_rec_dt / _H, n_total, n_in_rec,
            f"peak {peak_cr:.2f} mg/dL at {peak_dt_h:.1f}h; minimum in recovery window "
            f"{min_rec:.2f} mg/dL at {min_rec_dt/_H:.1f}h (>= 1.5x or >= baseline+0.3 threshold)",
        )


# ---- Cohort-level builder ---------------------------------------------------

def build_trajectories(cfg: dict[str, Any], refresh: bool = False) -> dict[str, Any]:
    """Classify all AKI-positive cases in the cohort and write output files.

    Reads:
      cache_dir/cohort.csv or cohort_composite.csv (prefers cohort.csv) for the
      AKI label and baseline creatinine per case.

    For each AKI-positive case, loads the full postop creatinine series from the
    cached labs CSV (no network; uses client.creatinine_by_case via the cache).
    Classifies each case as transient / persistent / indeterminate.

    Writes:
      cache_dir/aki_trajectory.csv          one row per AKI-positive case
      cache_dir/aki_trajectory_summary.json counts + distributions

    Also prints an EXPLORATORY preop-feature comparison (transient vs persistent).
    This comparison is PURELY EXPLORATORY (small N, no correction, not pre-registered).

    Parameters
    ----------
    cfg:
        Config dict (loaded from config.yaml).
    refresh:
        If True, re-download labs from the API (default: use cache).

    Returns
    -------
    Summary dict (also written to JSON).
    """
    from vitaldb_aki.data.client import creatinine_by_case, fetch_cases, fetch_table, to_float
    from vitaldb_aki.cohort.build import _anchor_seconds, _baseline

    cdir = cfg["data"]["cache_dir"]
    kcfg = cfg["kdigo"]

    # -- Load the cohort (prefer cohort.csv which has explicit aki column) -----
    cohort_path = os.path.join(cdir, "cohort.csv")
    if not os.path.exists(cohort_path):
        cohort_path = os.path.join(cdir, "cohort_composite.csv")
        if not os.path.exists(cohort_path):
            raise FileNotFoundError(
                f"Neither cohort.csv nor cohort_composite.csv found in {cdir}. "
                "Run build_cohort (or build_composite_cohort) first."
            )

    with open(cohort_path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        cohort_rows = list(reader)

    # Detect AKI column name (cohort.csv uses 'aki', composite uses 'organ_renal')
    if "aki" in (cohort_rows[0].keys() if cohort_rows else {}):
        aki_col = "aki"
    else:
        aki_col = "organ_renal"

    aki_cases = [r for r in cohort_rows if str(r.get(aki_col, "")).strip() == "1"]
    print(f"[aki_trajectory] {len(cohort_rows)} labelable cases in cohort, "
          f"{len(aki_cases)} AKI-positive (KDIGO creatinine)")

    # -- Load creatinine labs (uses disk cache) --------------------------------
    cr_map = creatinine_by_case(cfg, refresh=refresh)

    # -- Load cases for anchor + baseline recalc + preop features --------------
    cases_list = fetch_cases(cfg, refresh=False)
    cases_by_id = {str(c.get("caseid", "")).lstrip("﻿"): c for c in cases_list}

    # -- Classify each AKI-positive case --------------------------------------
    rows_out: list[dict] = []
    for row in aki_cases:
        cid = str(row["caseid"]).strip()
        baseline_cr = to_float(row.get("baseline_cr"))
        case = cases_by_id.get(cid, {})

        # Recompute anchor to convert absolute dt -> dt_after_anchor
        anchor = _anchor_seconds(case, kcfg)
        if anchor is None:
            # Fall back: anchor = 0 (casestart), unlikely but safe
            anchor = 0.0

        # Build postop series: dt_seconds_after_anchor
        all_cr = cr_map.get(cid, [])
        postop_series = [(dt - anchor, v) for dt, v in all_cr if dt > anchor]

        # Baseline from cohort row (already computed); fall back to recalc
        if baseline_cr is None or baseline_cr <= 0:
            baseline_cr, _ = _baseline(case, all_cr, anchor, kcfg)

        result = classify_trajectory(baseline_cr or 0.0, postop_series, cfg)

        rows_out.append({
            "caseid": cid,
            "subjectid": row.get("subjectid", ""),
            "trajectory": result.label,
            "baseline_cr": baseline_cr,
            "peak_cr": result.peak_cr,
            "peak_cr_dt_h": result.peak_cr_dt_h,
            "recovery_cr": result.recovery_cr,
            "recovery_dt_h": result.recovery_dt_h,
            "n_postop_cr": result.n_postop_cr,
            "n_in_recovery_window": result.n_in_recovery_window,
            "reason": result.reason,
            # preop features for exploratory analysis
            "age": to_float(case.get("age")),
            "asa": to_float(case.get("asa")),
            "preop_dm": to_float(case.get("preop_dm")),
            "preop_htn": to_float(case.get("preop_htn")),
            "kdigo_stage": row.get("kdigo_stage", ""),
            "criterion": row.get("criterion", ""),
        })

    # -- Write CSV ------------------------------------------------------------
    os.makedirs(cdir, exist_ok=True)
    out_csv = os.path.join(cdir, "aki_trajectory.csv")
    if rows_out:
        cols = list(rows_out[0].keys())
        with open(out_csv, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows_out)

    # -- Counts + distribution summary ----------------------------------------
    n_transient = sum(1 for r in rows_out if r["trajectory"] == "transient")
    n_persistent = sum(1 for r in rows_out if r["trajectory"] == "persistent")
    n_indet = sum(1 for r in rows_out if r["trajectory"] == "indeterminate")

    def _mean_str(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    def _group(label):
        return [r for r in rows_out if r["trajectory"] == label]

    def _dist(label):
        g = _group(label)
        return {
            "n": len(g),
            "mean_baseline_cr": _mean_str([r["baseline_cr"] for r in g]),
            "mean_peak_cr": _mean_str([r["peak_cr"] for r in g]),
            "mean_n_postop_cr": _mean_str([r.get("n_postop_cr") for r in g]),
        }

    summary = {
        "n_aki_positive": len(aki_cases),
        "n_classified": len(rows_out),
        "transient": n_transient,
        "persistent": n_persistent,
        "indeterminate": n_indet,
        "recovery_early_h": RECOVERY_EARLY_H,
        "recovery_late_h": RECOVERY_LATE_H,
        "kdigo_window_h": KDIGO_WINDOW_H,
        "distributions": {
            "transient": _dist("transient"),
            "persistent": _dist("persistent"),
            "indeterminate": _dist("indeterminate"),
        },
        "note": (
            "INDETERMINATE = AKI-positive but no creatinine measured in the 24-72h "
            "recovery window; cannot adjudicate trajectory. Exploratory preop-feature "
            "comparison printed to stdout (small N; no correction applied)."
        ),
    }

    out_json = os.path.join(cdir, "aki_trajectory_summary.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    # -- Exploratory preop-feature comparison (transient vs persistent) --------
    _print_exploratory(rows_out)

    print(f"\n[aki_trajectory] Written: {out_csv}")
    print(f"[aki_trajectory] Written: {out_json}")
    return summary


def _mean(vals: list) -> float | None:
    clean = [v for v in vals if v is not None]
    return round(sum(clean) / len(clean), 3) if clean else None


def _pct(vals: list, binary_val: float) -> float | None:
    clean = [v for v in vals if v is not None]
    if not clean:
        return None
    return round(100.0 * sum(1 for v in clean if v == binary_val) / len(clean), 1)


def _print_exploratory(rows: list[dict]) -> None:
    """Print simple group-means table comparing transient vs persistent.

    PURELY EXPLORATORY: small N, no statistical correction, not pre-registered.
    Included only to surface signal for hypothesis generation.
    """
    trans = [r for r in rows if r["trajectory"] == "transient"]
    pers = [r for r in rows if r["trajectory"] == "persistent"]

    print("\n" + "=" * 66)
    print("EXPLORATORY: Preop features by AKI trajectory (transient vs persistent)")
    print("Small N — no correction — hypothesis generation only, NOT pre-registered")
    print("=" * 66)
    print(f"{'Feature':<28} {'Transient':>12} {'Persistent':>12}")
    print(f"{'':28} {'(n=' + str(len(trans)) + ')':>12} {'(n=' + str(len(pers)) + ')':>12}")
    print("-" * 54)

    features = [
        ("Age (years, mean)", "age", "mean"),
        ("ASA class (mean)", "asa", "mean"),
        ("Baseline Cr (mg/dL, mean)", "baseline_cr", "mean"),
        ("Peak Cr (mg/dL, mean)", "peak_cr", "mean"),
        ("Diabetes (% yes)", "preop_dm", "pct1"),
        ("Hypertension (% yes)", "preop_htn", "pct1"),
        ("N postop Cr (mean)", "n_postop_cr", "mean"),
    ]

    for label, key, stat in features:
        if stat == "mean":
            tv = _mean([r.get(key) for r in trans])
            pv = _mean([r.get(key) for r in pers])
            ts = f"{tv:.2f}" if tv is not None else "N/A"
            ps = f"{pv:.2f}" if pv is not None else "N/A"
        else:  # pct1
            tv = _pct([r.get(key) for r in trans], 1.0)
            pv = _pct([r.get(key) for r in pers], 1.0)
            ts = f"{tv:.1f}%" if tv is not None else "N/A"
            ps = f"{pv:.1f}%" if pv is not None else "N/A"
        print(f"{label:<28} {ts:>12} {ps:>12}")

    print("=" * 66)
    print("NOTE: indeterminate cases excluded from this comparison.\n")
