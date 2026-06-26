"""labeling.py -- objective KDIGO creatinine AKI label (Sec 6).

KDIGO (creatinine arm):
  * absolute rise >= 0.3 mg/dL within 48 h, OR
  * relative >= 1.5 x baseline within 7 days.

The urine-output arm is deliberately NOT used (VitalDB UO is intermittent/manual;
Sec 6 limitation). Baseline = most recent preoperative creatinine (preop_cr, with
optional fallback to a preop lab value). Windows are anchored at end of surgery
(opend) per config, and only postoperative creatinine (dt > anchor) can trigger a
label -- nothing measured after the prediction cutoff leaks into a feature, but
the LABEL is allowed to use postop creatinine by definition (Sec 11.1/11.3).

Pure stdlib: takes already-parsed numbers so it unit-tests with no network.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LabelResult:
    caseid: str
    aki: int | None                 # 1 / 0, or None if unlabelable
    stage: int                      # 0..3 (0 if no AKI), KDIGO creatinine stage
    baseline_cr: float | None
    baseline_source: str            # "preop_cr" | "preop_lab" | "none"
    peak_postop_cr: float | None
    n_postop_cr: int
    reason: str                     # why labelable / not, or which criterion fired


def _stage(baseline: float, peak: float, abs_rise: float) -> int:
    """KDIGO creatinine stage from peak/baseline ratio and absolute rise."""
    ratio = peak / baseline if baseline else 0.0
    if ratio >= 3.0 or peak >= 4.0 or abs_rise >= 4.0:
        return 3
    if ratio >= 2.0:
        return 2
    if ratio >= 1.5 or abs_rise >= 0.3:
        return 1
    return 0


def label_case(
    caseid: str,
    baseline_cr: float | None,
    baseline_source: str,
    postop_cr: list[tuple[float, float]],   # [(dt_seconds, cr), ...], dt relative to anchor
    kcfg: dict[str, Any],
) -> LabelResult:
    """Apply KDIGO to one case.

    `postop_cr` must already be filtered to measurements AFTER the window anchor
    and expressed as (seconds_after_anchor, mg/dL). A case with no baseline or no
    qualifying postop creatinine is returned with aki=None (unlabelable -> excluded
    from the labelable cohort, Sec 5).
    """
    if baseline_cr is None or baseline_cr <= 0:
        return LabelResult(caseid, None, 0, baseline_cr, "none", None, 0,
                           "no baseline creatinine")
    if not postop_cr:
        return LabelResult(caseid, None, 0, baseline_cr, baseline_source, None, 0,
                           "no postoperative creatinine")

    abs_window_s = float(kcfg["abs_window_h"]) * 3600.0
    rel_window_s = float(kcfg["rel_window_h"]) * 3600.0
    abs_rise_thr = float(kcfg["abs_rise_mgdl"])
    rel_ratio = float(kcfg["rel_ratio"])

    fired = ""
    peak = max(v for _, v in postop_cr)
    # absolute-rise criterion within its (shorter) window
    abs_hits = [v for dt, v in postop_cr if dt <= abs_window_s and (v - baseline_cr) >= abs_rise_thr]
    # relative criterion within its (longer) window
    rel_hits = [v for dt, v in postop_cr if dt <= rel_window_s and (v / baseline_cr) >= rel_ratio]
    aki = 1 if (abs_hits or rel_hits) else 0
    if abs_hits and rel_hits:
        fired = "abs+rel"
    elif abs_hits:
        fired = "abs_rise>=0.3/48h"
    elif rel_hits:
        fired = "rel>=1.5x/7d"
    else:
        fired = "no criterion met"

    # stage uses the peak within the 7-day window
    in_window = [v for dt, v in postop_cr if dt <= rel_window_s]
    peak_w = max(in_window) if in_window else peak
    stage = _stage(baseline_cr, peak_w, peak_w - baseline_cr) if aki else 0
    return LabelResult(caseid, aki, stage, baseline_cr, baseline_source, peak,
                       len(postop_cr), fired)
