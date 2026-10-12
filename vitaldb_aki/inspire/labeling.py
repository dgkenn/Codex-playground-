"""labeling.py -- KDIGO AKI label on INSPIRE creatinine.

Uses the IDENTICAL thresholds as vitaldb_aki/cohort/labeling.py (imported
directly -- single source of truth).  Only the data-mapping layer differs:
INSPIRE uses a 'labs' table with (caseid, time, name, result) rows where
``name == 'cr'`` and time is seconds from opstart (confirmed from PhysioNet
docs -- validate on first real data access and update _TIME_UNIT_SECONDS below
if needed).

Design decisions (binding, document before touching INSPIRE outcomes):
  * Baseline creatinine = most-recent cr measurement with time < 0 (i.e., before
    opstart / within-op if no preop value available -- see _pick_baseline).
  * If no preop creatinine exists, a fallback window of BASELINE_PREOP_WINDOW_S
    before surgery is used (labs with slightly negative time within 30 days).
  * Postop creatinine = cr measurements with time > opend_s (duration of surgery).
  * Window anchor = opend (end of surgery), consistent with VitalDB protocol.
  * Primary: KDIGO within 7 days (168 h).  Sensitivity: 48 h.

The KDIGO config dict defaults match config.yaml but callers can pass a custom
dict for sensitivity analyses.
"""
from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------
# Re-use the IDENTICAL KDIGO implementation from cohort/labeling.py
# --------------------------------------------------------------------------
from vitaldb_aki.cohort.labeling import LabelResult, label_case  # noqa: F401  (re-export)

# --------------------------------------------------------------------------
# INSPIRE-specific constants (update if schema differs from PhysioNet docs)
# --------------------------------------------------------------------------

# Time unit in the INSPIRE vitals/labs tables.
# PhysioNet docs say "time is in seconds from opstart" for INSPIRE v1.4.2.
_TIME_UNIT = "seconds_from_opstart"   # document; confirm on first real run

# Preoperative window: accept creatinine up to this many seconds before opstart
# as the baseline (30 days = 2_592_000 s).
BASELINE_PREOP_WINDOW_S: float = 30 * 24 * 3600.0

# Default KDIGO config -- mirrors config.yaml kdigo block.
DEFAULT_KDIGO_CFG: dict[str, Any] = {
    "abs_rise_mgdl": 0.3,
    "abs_window_h": 48,
    "rel_ratio": 1.5,
    "rel_window_h": 168,
}


# --------------------------------------------------------------------------
# Data-mapping helpers
# --------------------------------------------------------------------------

def creatinine_by_case(
    lab_rows: list[dict[str, str]],
) -> dict[str, list[tuple[float, float]]]:
    """Map INSPIRE labs rows -> {caseid: [(time_seconds, cr_mgdl), ...] sorted}.

    Filters to ``name == 'cr'`` (case-insensitive) and drops non-numeric rows.
    Time is kept as-is (seconds from opstart per INSPIRE schema).
    """
    from vitaldb_aki.inspire.client import to_float

    out: dict[str, list[tuple[float, float]]] = {}
    for row in lab_rows:
        if row.get("name", "").strip().lower() != "cr":
            continue
        cid = row.get("caseid", "").strip()
        if not cid:
            continue
        t = to_float(row.get("time"))
        v = to_float(row.get("result"))
        if t is None or v is None or v <= 0:
            continue
        out.setdefault(cid, []).append((t, v))
    for cid in out:
        out[cid].sort(key=lambda x: x[0])
    return out


def _pick_baseline(
    cr_series: list[tuple[float, float]],
) -> tuple[float | None, str]:
    """Select baseline creatinine from a per-case series.

    Strategy (mirrors VitalDB: most-recent preoperative creatinine):
      1. Most recent cr with time < 0 (preoperative).
      2. If none, most recent cr within the last 30 days of the preop window
         (time >= -BASELINE_PREOP_WINDOW_S and time < 0) -- same as above since
         all time < 0 is preop; this branch handles a case with no negative-time
         labs at all (unlabelable).
      3. Returns (None, "none") when no preop creatinine exists.

    Returns (baseline_value, source_tag).
    """
    preop = [(t, v) for t, v in cr_series if t < 0]
    if not preop:
        return None, "none"
    # most recent = largest t among negatives
    best = max(preop, key=lambda x: x[0])
    # accept only within 30-day window
    if best[0] < -BASELINE_PREOP_WINDOW_S:
        return None, "none"
    return best[1], "preop_lab"


def label_inspire_case(
    caseid: str,
    cr_series: list[tuple[float, float]],
    op_duration_s: float,
    kcfg: dict[str, Any] | None = None,
) -> LabelResult:
    """Apply KDIGO to one INSPIRE case.

    Parameters
    ----------
    caseid        : case identifier string
    cr_series     : [(time_seconds_from_opstart, cr_mgdl), ...] sorted
    op_duration_s : duration of surgery in seconds (= opend - opstart); used as
                    the postop anchor (time > op_duration_s are postop)
    kcfg          : KDIGO config dict (defaults to DEFAULT_KDIGO_CFG)

    Returns
    -------
    LabelResult (identical schema to cohort/labeling.py; reusable downstream)
    """
    if kcfg is None:
        kcfg = DEFAULT_KDIGO_CFG

    baseline, source = _pick_baseline(cr_series)

    # Postop = time > op_duration_s; express dt relative to anchor (opend)
    postop = [
        (t - op_duration_s, v)
        for t, v in cr_series
        if t > op_duration_s
    ]

    return label_case(caseid, baseline, source, postop, kcfg)


def label_all_cases(
    operations: list[dict[str, str]],
    lab_rows: list[dict[str, str]],
    kcfg: dict[str, Any] | None = None,
) -> dict[str, LabelResult]:
    """Label every case in the operations table.

    Parameters
    ----------
    operations : rows from INSPIRE operations.csv
    lab_rows   : rows from INSPIRE labs.csv
    kcfg       : KDIGO config (default: DEFAULT_KDIGO_CFG)

    Returns
    -------
    {caseid: LabelResult}
    """
    from vitaldb_aki.inspire.client import to_float

    cr_map = creatinine_by_case(lab_rows)
    out: dict[str, LabelResult] = {}
    for row in operations:
        cid = row.get("caseid", "").strip()
        if not cid:
            continue
        opstart = to_float(row.get("opstart")) or 0.0
        opend = to_float(row.get("opend"))
        if opend is None:
            # Cannot determine postop window without opend
            out[cid] = LabelResult(
                cid, None, 0, None, "none", None, 0, "missing opend"
            )
            continue
        op_duration_s = opend - opstart
        series = cr_map.get(cid, [])
        out[cid] = label_inspire_case(cid, series, op_duration_s, kcfg)
    return out
