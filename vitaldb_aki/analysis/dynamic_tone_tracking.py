"""dynamic_tone_tracking.py -- DYNAMIC within-case vascular-tone tracking.

THE PIVOT (high-impact + more-defensible version of the static finding)
-----------------------------------------------------------------------
The STATIC cross-sectional result (one waveform-tone value vs one measured SVRI
per case, Spearman r ~ 0.49 across patients) is defensible but modest and carries
all the usual between-patient confounding (body size, baseline tone, device
calibration).  The HIGH-IMPACT version asks a within-case temporal question:

    WITHIN a single operation, does the arterial-waveform tone index TRACK the
    measured SVR as it changes over time?

A within-case temporal correlation removes ALL between-patient confounding (each
case is its own control), and "real-time vascular-tone / vasoplegia sensing from
a standard arterial line, with NO cardiac-output monitor" is a high-impact
clinical claim: early distributive-shock / post-CPB vasoplegia / anaphylaxis
detection from a line every OR already has.

FEASIBILITY is confirmed: EV1000/SVR is a dense ~0.5-1 Hz time series
(6000-9500 samples/case) and a majority of sampled cases show substantial
within-case SVR variation (CV>0.15, ranges e.g. 526->3423) -- there is real
dynamic range to track.

COHORT
------
caseids with BOTH SNUADC/ART AND a measured SVR/SVRI track (EV1000/SVR or
EV1000/SVRI), from cache/trks.csv (built WITHOUT any download, reusing
vasoplegia_validation_extract.build_cohort).  We start with a SEEDED SAMPLE of
~50 cases (seed 20260626) to PROVE THE CONCEPT -- this is feasibility, not the
full 248.  N is a CLI/env knob (--n / DTT_N) so it can scale later.

PER CASE
--------
  1. Download SNUADC/ART (500 Hz, via aline_morphology.load_art_waveform) +
     EV1000/SVR or EV1000/SVRI + Solar8000/ART_MBP (numeric MAP).  PURGE the big
     SNUADC track (and the small monitor tracks) after each case so disk stays
     bounded (mirrors vasoplegia_validation_extract's purge).
  2. Window the intraop period into fixed windows (default WINDOW_S = 180 s,
     configurable).  Per window:
       * waveform TONE features from the ART beats in that window, reusing
         aline_morphology's per-beat machinery:
            - tau_decay  (diastolic decay time constant, R*C tone marker),
            - diastolic/MAP form factor (DBP/MAP, rises with vasoconstriction),
            - augmentation index AIx,
            - HR (from beat intervals).
       * median measured SVR (the EV1000 track) in the window,
       * median MAP (Solar8000/ART_MBP) in the window.
       * require >= MIN_BEATS_PER_WINDOW valid beats AND a valid SVR.
  3. Build a per-case time series of (window -> tone features, SVR, MAP, HR).

ANALYSES
--------
A. PRIMARY -- per-case WITHIN-case Spearman( tone , measured SVR ) across
   windows.  Aggregate: median within-case r, IQR, % cases with |r|>0.3,
   distribution.  We report the raw single-feature within-case correlations
   (tau-vs-SVR, diastolic/MAP-vs-SVR, AIx-vs-SVR) AND a pre-specified composite
   TONE INDEX = -z(tau) - z(dia/MAP) - z(AIx), oriented so HIGHER index = MORE
   vasoplegic = LOWER SVR.  We therefore EXPECT NEGATIVE within-case r between
   the composite tone index and SVR (and report the raw single features too,
   which is cleaner).

B. THE DEFENSIBLE-IMPACT TEST -- within-case PARTIAL correlation tone-vs-SVR
   GIVEN MAP (does the waveform track SVR CHANGES at matched pressure within the
   case?), and GIVEN MAP+HR (the airtight version -- removes the HR->CO->SVR
   path).  If the waveform tracks within-case SVR BEYOND MAP (and beyond MAP+HR),
   that is real tone sensing; if it only tracks via MAP/HR, we report that
   honestly.  Aggregate: median partial r across cases + a Wilcoxon signed-rank /
   sign test that the distribution of within-case (partial) r is shifted from 0.

C. EVENT detection illustration -- cases with a large within-case SVR DROP
   (vasoplegic episode); does the tone index move concordantly?

D. Honest limitations -- single-centre (SNUH), EV1000 subset, SVR is CO-derived
   & device-filtered (may lag), modest sample, windowing choices.

OUTPUTS
-------
  cache/dynamic_tone_tracking_results.json   -- aggregate results
  cache/dynamic_tone_tracking_percase.csv    -- per-case within r + partials
  docs/DYNAMIC_TONE_TRACKING.md              -- read-first limitations + verdict

CONVENTIONS
-----------
Heavy deps (numpy/scipy) are imported lazily inside functions so this module
imports with the stdlib only.  Deterministic: seed 20260626 from config; the case
sample is a seeded shuffle of the SVR-first cohort.  Runnable from the repo root:

    python vitaldb_aki/analysis/dynamic_tone_tracking.py [--n 50] [--window 180]

Leakage firewall: N/A here -- there is NO outcome label.  This is a physiologic
MEASUREMENT-VALIDATION analysis (waveform tone vs a reference SVR), entirely
within the intraop window; no postop variable is ever read.
"""
from __future__ import annotations

import csv as _csv
import json
import math
import os
import random
import sys
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Constants (binding; config-readable).
# ---------------------------------------------------------------------------
SEED = 20260626                 # overridden by config.yaml seed if present
DEFAULT_N = 50                  # seeded feasibility sample (CLI/env knob: --n / DTT_N)
DEFAULT_WINDOW_S = 180.0        # fixed analysis window (3 min); CLI/env --window / DTT_WINDOW

MIN_BEATS_PER_WINDOW = 8        # need >= this many physiologic beats in a window
MIN_SVR_SAMPLES_PER_WINDOW = 2  # need >= this many measured-SVR samples in a window
MIN_WINDOWS_PER_CASE = 5        # need >= this many usable windows to correlate
MIN_SVR_RANGE_CV = 0.0          # (informational) report CV; do not gate on it

# Track names (reuse vaso_val's definitions).
ART_TRACK = "SNUADC/ART"
SVR_TRACKS = ("EV1000/SVR", "EV1000/SVRI")   # prefer raw SVR; SVRI is just *BSA scaled
MAP_TRACK = "Solar8000/ART_MBP"

# Physiologic gates for the numeric monitor tracks (mirror vaso_val / fluid).
SVR_MIN, SVR_MAX = 100.0, 5000.0
MAP_MIN, MAP_MAX = 20.0, 200.0

# Big tracks to purge per case (bounds disk; mirrors vasoplegia_validation_extract).
_BIG_SNUADC_TRACKS = ("SNUADC/ART", "SNUADC/PLETH", "SNUADC/ECG_II")
_MONITOR_TRACKS = ("EV1000/SVR", "EV1000/SVRI", MAP_TRACK)

# Composite tone index (pre-specified): higher = more vasoplegic = expect LOWER SVR.
#   tone_index = -z(tau) - z(dia_over_map) - z(aix)
# (tau, dia/MAP, AIx all RISE with vasoconstriction / higher SVR, so negating and
# summing gives a "vasoplegia" axis that should correlate NEGATIVELY with SVR.)
TONE_COMPONENTS = ("tau", "dia_over_map", "aix")

OUT_RESULTS = "dynamic_tone_tracking_results.json"
OUT_PERCASE = "dynamic_tone_tracking_percase.csv"

# Event-detection: a "large SVR drop" case has within-case SVR dropping by at least
# this fraction of its own range across the series (illustration C).
EVENT_DROP_FRAC = 0.5


# ===========================================================================
# PURE HELPERS (stdlib only)
# ===========================================================================
def _resolve_cache_dir(cfg: dict[str, Any]) -> str:
    data = cfg.get("data")
    if isinstance(data, dict) and data.get("cache_dir"):
        return data["cache_dir"]
    if cfg.get("cache_dir"):
        return cfg["cache_dir"]
    return "vitaldb_aki/cache"


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "nan", "NA", "None", "NaN"):
        return None
    try:
        f = float(s)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _median(xs: list[float]) -> float | None:
    ys = sorted(x for x in xs if x is not None and math.isfinite(x))
    n = len(ys)
    if n == 0:
        return None
    if n % 2:
        return ys[n // 2]
    return 0.5 * (ys[n // 2 - 1] + ys[n // 2])


def _iqr(xs: list[float]) -> tuple[float | None, float | None]:
    ys = sorted(x for x in xs if x is not None and math.isfinite(x))
    n = len(ys)
    if n == 0:
        return None, None

    def q(p: float) -> float:
        if n == 1:
            return ys[0]
        idx = p * (n - 1)
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            return ys[lo]
        return ys[lo] + (ys[hi] - ys[lo]) * (idx - lo)

    return q(0.25), q(0.75)


# ===========================================================================
# CORRELATION CORES (pure; numpy lazy, scipy lazy for the p-values).
# ===========================================================================
def _rankdata(x: list[float]) -> list[float]:
    """Average-rank transform (ties get mean rank). Pure / stdlib."""
    n = len(x)
    order = sorted(range(n), key=lambda i: x[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank over the tie block
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 3 or len(y) != n:
        return None
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / math.sqrt(sxx * syy)


def spearman(x: list[float], y: list[float]) -> float | None:
    """Spearman rho via Pearson on ranks. Pure. None if < 3 finite pairs."""
    pairs = [(a, b) for a, b in zip(x, y)
             if a is not None and b is not None
             and math.isfinite(a) and math.isfinite(b)]
    if len(pairs) < 3:
        return None
    xs = [a for a, _ in pairs]
    ys = [b for _, b in pairs]
    return _pearson(_rankdata(xs), _rankdata(ys))


def partial_spearman(x: list[float], y: list[float],
                     covars: list[list[float]]) -> tuple[float | None, int]:
    """Within-case PARTIAL Spearman of x vs y controlling for `covars`.

    Rank-transform every variable, regress ranked-x and ranked-y on the ranked
    covariates (with intercept) by ordinary least squares, and take the Pearson
    correlation of the residuals.  This is the standard rank-based partial
    correlation.  Returns (partial_r, n_used).  partial_r is None when there are
    too few complete rows for the number of covariates.

    Pure; numpy lazy only for the small OLS solve.
    """
    import numpy as np

    cols = [x, y] + list(covars)
    n = len(x)
    rows = []
    for i in range(n):
        vals = [c[i] for c in cols]
        if all(v is not None and math.isfinite(v) for v in vals):
            rows.append([float(v) for v in vals])
    m = len(rows)
    k = len(covars)
    # Need more rows than parameters (intercept + k covars) + slack.
    if m < max(MIN_WINDOWS_PER_CASE, k + 3):
        return None, m

    arr = np.asarray(rows, dtype=float)              # (m, 2+k)
    # Rank-transform each column (average ranks).
    ranked = np.empty_like(arr)
    for c in range(arr.shape[1]):
        ranked[:, c] = _rankdata(list(arr[:, c]))

    rx = ranked[:, 0]
    ry = ranked[:, 1]
    if k == 0:
        r = _pearson(list(rx), list(ry))
        return r, m
    C = ranked[:, 2:]                                # (m, k)
    design = np.column_stack([np.ones(m), C])        # (m, k+1)

    def _resid(yv: "np.ndarray") -> "np.ndarray":
        beta, *_ = np.linalg.lstsq(design, yv, rcond=None)
        return yv - design @ beta

    ex = _resid(rx)
    ey = _resid(ry)
    r = _pearson(list(ex), list(ey))
    return r, m


def _zscores(xs: list[float | None]) -> list[float | None]:
    """Z-score a column (ignoring None); returns None where input is None."""
    vals = [x for x in xs if x is not None and math.isfinite(x)]
    if len(vals) < 2:
        return [None] * len(xs)
    mu = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / (len(vals) - 1))
    if sd <= 0:
        return [None] * len(xs)
    return [((x - mu) / sd) if (x is not None and math.isfinite(x)) else None
            for x in xs]


def build_tone_index(windows: list[dict[str, Any]]) -> list[float | None]:
    """Composite vasoplegia tone index per window = -z(tau)-z(dia/MAP)-z(AIx).

    Z-scores are computed WITHIN the case (across its windows) so the index is a
    within-case relative axis.  A window's index is None unless ALL available
    components are finite there (we require at least tau + dia/MAP; AIx is added
    when present so cases lacking a usable AIx are not dropped).
    """
    tau = _zscores([w.get("tau") for w in windows])
    dia = _zscores([w.get("dia_over_map") for w in windows])
    aix = _zscores([w.get("aix") for w in windows])
    out: list[float | None] = []
    for i in range(len(windows)):
        parts = []
        # Require the two robust components; AIx is optional (raw-ART approximate).
        if tau[i] is None or dia[i] is None:
            out.append(None)
            continue
        parts.append(-tau[i])
        parts.append(-dia[i])
        if aix[i] is not None:
            parts.append(-aix[i])
        out.append(sum(parts))
    return out


# ===========================================================================
# PER-WINDOW WAVEFORM TONE (reuse aline_morphology per-beat machinery)
# ===========================================================================
def window_tone(times: "Any", values: "Any", fs: float) -> dict[str, Any] | None:
    """Compute per-window waveform-tone features from the ART beats in a window.

    Reuses aline_morphology:
       detect_beats           -> (n,6) [sbp,dbp,pp,dpdt,interval,auc] for SBP/DBP/HR,
       collect_vascular_cycles + tau_decay_for_beat / aug_index_for_beat -> tau, AIx.

    Returns a dict with n_beats, sbp, dbp, map, pp, hr, dia_over_map, tau, aix
    (any of tau/aix may be None), or None if < MIN_BEATS_PER_WINDOW physiologic
    beats.  Pure / network-free.
    """
    import numpy as np

    from vitaldb_aki.features import aline_morphology as _aline

    v = np.asarray(values, dtype=float)
    t = np.asarray(times, dtype=float)
    if v.size < int(fs):
        return None

    # Sample-level artefact gate (drop flush/zeroing), mirror _process_window.
    good = (v >= _aline.ART_SAMPLE_MIN) & (v <= _aline.ART_SAMPLE_MAX) & np.isfinite(v)
    if not good.any():
        return None
    v = v[good]
    t = t[good]
    if v.size < int(fs):
        return None

    beats = _aline.detect_beats(v, fs)
    if len(beats) < MIN_BEATS_PER_WINDOW:
        return None

    sbp = float(np.mean(beats[:, 0]))
    dbp = float(np.mean(beats[:, 1]))
    pp = float(np.mean(beats[:, 2]))
    mapw = dbp + pp / 3.0
    interval = beats[:, 4]
    hr_vals = 60.0 / interval[interval > 0]
    hr = float(np.mean(hr_vals)) if hr_vals.size else None
    dia_over_map = (dbp / mapw) if mapw > 0 else None

    # tau / AIx over the accepted cycles in THIS window (window-local; cheap since a
    # 3-min window holds ~150-300 beats -- well within the per-case sampling cap).
    cycles = _aline.collect_vascular_cycles(t, v, fs)
    tau_list: list[float] = []
    aix_list: list[float] = []
    for cyc in cycles:
        tv = _aline.tau_decay_for_beat(cyc, fs)
        if tv is not None:
            tau_list.append(tv)
        av = _aline.aug_index_for_beat(cyc, fs)
        if av is not None:
            aix_list.append(av)
    tau = (sum(tau_list) / len(tau_list)) if tau_list else None
    aix = (sum(aix_list) / len(aix_list)) if len(aix_list) >= 3 else None

    return {
        "n_beats": int(len(beats)),
        "sbp": round(sbp, 3), "dbp": round(dbp, 3), "map_wave": round(mapw, 3),
        "pp": round(pp, 3),
        "hr": round(hr, 3) if hr is not None else None,
        "dia_over_map": round(dia_over_map, 5) if dia_over_map is not None else None,
        "tau": round(tau, 5) if tau is not None else None,
        "aix": round(aix, 5) if aix is not None else None,
        "n_tau": len(tau_list), "n_aix": len(aix_list),
    }


# ===========================================================================
# NUMERIC TRACK WINDOWING (SVR, MAP)
# ===========================================================================
def _window_median(samples: list[tuple[float, float]],
                   w_start: float, w_end: float,
                   vmin: float, vmax: float) -> tuple[float | None, int]:
    """Median of a numeric monitor track over [w_start, w_end) with a phys gate.

    Returns (median, n_samples_in_window). None median if no in-range samples.
    """
    vals = [v for (ts, v) in samples
            if w_start <= ts < w_end and vmin <= v <= vmax]
    if not vals:
        return None, 0
    return _median(vals), len(vals)


# ===========================================================================
# PER-CASE EXTRACTION
# ===========================================================================
def extract_case_series(cfg, cid: str, case: dict[str, Any],
                        window_s: float) -> dict[str, Any]:
    """Build the per-case window series and download/purge tracks.

    Returns a dict:
       {"caseid", "n_windows", "windows":[...], "svr_track", "svr_cv",
        "svr_min","svr_max","svr_median","note"}
    `windows` is a list of per-window dicts merging tone features + median SVR +
    median MAP (only windows with >= MIN_BEATS_PER_WINDOW beats AND a valid SVR).
    Always purges the big SNUADC + monitor tracks in `finally`.
    """
    from vitaldb_aki.data import tracks as _T
    from vitaldb_aki.features import aline_morphology as _aline

    out: dict[str, Any] = {
        "caseid": cid, "n_windows": 0, "windows": [],
        "svr_track": None, "svr_cv": None, "svr_min": None,
        "svr_max": None, "svr_median": None, "note": "",
    }
    try:
        t_start, t_end = _aline._intraop_window(case)

        # --- measured SVR track (prefer raw SVR; SVRI is BSA-scaled, monotone) ---
        svr_name = None
        svr_raw: list[tuple[float, float]] = []
        for tn in SVR_TRACKS:
            s = _T.download_track(cfg, cid, tn)
            if s:
                svr_name = tn
                svr_raw = s
                break
        if not svr_raw:
            out["note"] = "no SVR/SVRI track"
            return out
        out["svr_track"] = svr_name
        # clip to intraop window
        svr_samples = [(ts, v) for (ts, v) in svr_raw
                       if (t_start is None or ts >= t_start)
                       and (t_end is None or ts <= t_end)
                       and SVR_MIN <= v <= SVR_MAX]
        if len(svr_samples) < MIN_SVR_SAMPLES_PER_WINDOW * MIN_WINDOWS_PER_CASE:
            out["note"] = f"too few in-window SVR samples ({len(svr_samples)})"
            return out
        svr_vals = [v for _, v in svr_samples]
        out["svr_min"] = round(min(svr_vals), 2)
        out["svr_max"] = round(max(svr_vals), 2)
        med = _median(svr_vals)
        out["svr_median"] = round(med, 2) if med is not None else None
        if med and med > 0:
            mu = sum(svr_vals) / len(svr_vals)
            sd = math.sqrt(sum((v - mu) ** 2 for v in svr_vals) / len(svr_vals))
            out["svr_cv"] = round(sd / mu, 4) if mu > 0 else None

        # --- MAP track (numeric, Solar8000/ART_MBP) ---
        map_raw = _T.download_track(cfg, cid, MAP_TRACK)
        map_samples = [(ts, v) for (ts, v) in map_raw
                       if (t_start is None or ts >= t_start)
                       and (t_end is None or ts <= t_end)
                       and MAP_MIN <= v <= MAP_MAX]

        # --- ART waveform (reconstructed 500 Hz grid) ---
        wt, wv = _aline.load_art_waveform(cfg, cid, _aline.ART_TRACK_CANDIDATES)
        if wt is None or len(wt) < 2:
            out["note"] = "no usable ART waveform"
            return out

        import numpy as np
        wt = np.asarray(wt, dtype=float)
        wv = np.asarray(wv, dtype=float)
        # Intraop clip (never read t > opend).
        mask = np.ones(wt.shape, dtype=bool)
        if t_start is not None:
            mask &= wt >= t_start
        if t_end is not None:
            mask &= wt <= t_end
        wt = wt[mask]
        wv = wv[mask]
        if wt.size < 2:
            out["note"] = "ART empty after intraop clip"
            return out

        fs = _aline.estimate_fs(wt)
        w0 = float(wt[0])
        w_end = float(wt[-1])

        windows: list[dict[str, Any]] = []
        ws = w0
        while ws + window_s <= w_end + 1e-6:
            we = ws + window_s
            # slice waveform (monotone -> searchsorted)
            i0 = int(np.searchsorted(wt, ws, side="left"))
            i1 = int(np.searchsorted(wt, we, side="left"))
            ws_next = ws + window_s
            if i1 > i0:
                seg_t = wt[i0:i1]
                seg_v = wv[i0:i1]
                tone = window_tone(seg_t, seg_v, fs)
            else:
                tone = None
            svr_med, n_svr = _window_median(svr_samples, ws, we, SVR_MIN, SVR_MAX)
            map_med, n_map = _window_median(map_samples, ws, we, MAP_MIN, MAP_MAX)
            ws = ws_next
            if tone is None:
                continue
            if svr_med is None or n_svr < MIN_SVR_SAMPLES_PER_WINDOW:
                continue
            rec = dict(tone)
            rec["t_start"] = round(float(we - window_s), 1)
            rec["svr"] = round(svr_med, 3)
            rec["n_svr"] = n_svr
            rec["map_num"] = round(map_med, 3) if map_med is not None else None
            rec["n_map"] = n_map
            windows.append(rec)

        out["windows"] = windows
        out["n_windows"] = len(windows)
        return out
    finally:
        for tn in (_BIG_SNUADC_TRACKS + _MONITOR_TRACKS):
            try:
                _T.purge_track(cfg, cid, tn)
            except Exception:
                pass


# ===========================================================================
# PER-CASE ANALYSIS (within-case correlations + partials)
# ===========================================================================
def analyse_case(case_series: dict[str, Any]) -> dict[str, Any] | None:
    """Compute within-case Spearman + partials for one case's window series.

    Returns a per-case result dict, or None if too few usable windows.
    The MAP covariate uses the numeric Solar8000 MAP when available for the
    window, else the waveform-derived MAP (map_wave) as a fallback so the
    partial is still defined.
    """
    windows = case_series.get("windows") or []
    if len(windows) < MIN_WINDOWS_PER_CASE:
        return None

    svr = [w.get("svr") for w in windows]
    tau = [w.get("tau") for w in windows]
    dia = [w.get("dia_over_map") for w in windows]
    aix = [w.get("aix") for w in windows]
    hr = [w.get("hr") for w in windows]
    # MAP covariate: numeric MAP preferred, waveform MAP fallback.
    mapc = [w.get("map_num") if w.get("map_num") is not None else w.get("map_wave")
            for w in windows]
    tone_idx = build_tone_index(windows)

    res: dict[str, Any] = {
        "caseid": case_series["caseid"],
        "n_windows": len(windows),
        "svr_track": case_series.get("svr_track"),
        "svr_cv": case_series.get("svr_cv"),
        "svr_min": case_series.get("svr_min"),
        "svr_max": case_series.get("svr_max"),
    }

    # --- A: raw within-case Spearman of each tone feature vs SVR ---
    res["r_tau_svr"] = spearman(tau, svr)
    res["r_dia_svr"] = spearman(dia, svr)
    res["r_aix_svr"] = spearman(aix, svr)
    res["r_tone_svr"] = spearman(tone_idx, svr)   # composite (expect NEGATIVE)
    res["r_map_svr"] = spearman(mapc, svr)        # context: how much MAP alone tracks SVR
    res["r_hr_svr"] = spearman(hr, svr)

    # --- B: partial within-case correlation of the composite tone index vs SVR ---
    # given MAP, and given MAP+HR.  Also report tau-given-MAP+HR (single cleanest).
    def _cov_complete(cov_lists):
        return cov_lists

    r_map, n_map = partial_spearman(tone_idx, svr, [mapc])
    r_maphr, n_maphr = partial_spearman(tone_idx, svr, [mapc, hr])
    res["partial_tone_svr_given_map"] = r_map
    res["partial_tone_svr_given_map_hr"] = r_maphr
    res["n_partial_map"] = n_map
    res["n_partial_map_hr"] = n_maphr

    # tau alone (cleanest single feature) partials
    res["partial_tau_svr_given_map"], _ = partial_spearman(tau, svr, [mapc])
    res["partial_tau_svr_given_map_hr"], _ = partial_spearman(tau, svr, [mapc, hr])
    res["partial_dia_svr_given_map"], _ = partial_spearman(dia, svr, [mapc])
    res["partial_dia_svr_given_map_hr"], _ = partial_spearman(dia, svr, [mapc, hr])

    return res


# ===========================================================================
# AGGREGATE / SIGN TESTS
# ===========================================================================
def _sign_wilcoxon(values: list[float]) -> dict[str, Any]:
    """Sign test + Wilcoxon signed-rank that the distribution is shifted from 0.

    Returns {n, n_pos, n_neg, median, sign_p, wilcoxon_p} (p-values may be None if
    scipy is unavailable / sample too small).  Pure except for the scipy import.
    """
    vals = [v for v in values if v is not None and math.isfinite(v)]
    n = len(vals)
    out: dict[str, Any] = {
        "n": n,
        "n_pos": sum(1 for v in vals if v > 0),
        "n_neg": sum(1 for v in vals if v < 0),
        "median": _median(vals),
        "sign_p": None, "wilcoxon_p": None,
    }
    if n < 2:
        return out
    # Two-sided sign test (binomial on pos vs neg, excluding exact zeros).
    n_pos = out["n_pos"]
    n_neg = out["n_neg"]
    n_nz = n_pos + n_neg
    if n_nz > 0:
        k = min(n_pos, n_neg)
        # exact two-sided binomial p at q=0.5
        from math import comb
        tail = sum(comb(n_nz, i) for i in range(0, k + 1)) / (2 ** n_nz)
        out["sign_p"] = min(1.0, 2.0 * tail)
    try:
        from scipy.stats import wilcoxon
        if n >= 6 and any(v != 0 for v in vals):
            stat, p = wilcoxon(vals)
            out["wilcoxon_p"] = float(p)
    except Exception:
        pass
    return out


def aggregate(percase: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-case within-case results into the headline numbers."""
    def col(key: str) -> list[float]:
        return [r[key] for r in percase
                if r.get(key) is not None and math.isfinite(r.get(key))]

    def summ(key: str, expect_negative: bool = False) -> dict[str, Any]:
        vals = col(key)
        lo, hi = _iqr(vals)
        # "% tracking": cases whose correlation is in the expected direction with
        # |r| > 0.3.  For composite tone vs SVR we expect NEGATIVE.
        if expect_negative:
            frac = (sum(1 for v in vals if v < -0.3) / len(vals)) if vals else None
        else:
            frac = (sum(1 for v in vals if abs(v) > 0.3) / len(vals)) if vals else None
        return {
            "n": len(vals),
            "median": _median(vals),
            "iqr_lo": lo, "iqr_hi": hi,
            "frac_tracking": frac,
            "sign_wilcoxon": _sign_wilcoxon(vals),
        }

    return {
        # A: raw single-feature within-case tracking
        "r_tau_svr": summ("r_tau_svr"),
        "r_dia_svr": summ("r_dia_svr"),
        "r_aix_svr": summ("r_aix_svr"),
        "r_tone_svr": summ("r_tone_svr", expect_negative=True),
        "r_map_svr": summ("r_map_svr"),
        "r_hr_svr": summ("r_hr_svr"),
        # B: PARTIALS -- the defensible-impact numbers
        "partial_tone_svr_given_map": summ("partial_tone_svr_given_map",
                                           expect_negative=True),
        "partial_tone_svr_given_map_hr": summ("partial_tone_svr_given_map_hr",
                                              expect_negative=True),
        "partial_tau_svr_given_map": summ("partial_tau_svr_given_map"),
        "partial_tau_svr_given_map_hr": summ("partial_tau_svr_given_map_hr"),
        "partial_dia_svr_given_map": summ("partial_dia_svr_given_map"),
        "partial_dia_svr_given_map_hr": summ("partial_dia_svr_given_map_hr"),
    }


# ===========================================================================
# EVENT DETECTION (illustration C)
# ===========================================================================
def event_cases(case_series_list: list[dict[str, Any]],
                percase: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify cases with a large within-case SVR DROP and report whether the
    composite tone index moved concordantly (rose as SVR fell)."""
    by_id = {cs["caseid"]: cs for cs in case_series_list}
    events: list[dict[str, Any]] = []
    for r in percase:
        cid = r["caseid"]
        cs = by_id.get(cid)
        if not cs:
            continue
        windows = cs.get("windows") or []
        svr = [w.get("svr") for w in windows if w.get("svr") is not None]
        if len(svr) < MIN_WINDOWS_PER_CASE:
            continue
        rng = max(svr) - min(svr)
        if rng <= 0:
            continue
        # crude drop magnitude: peak-to-subsequent-trough as fraction of range
        peak_i = max(range(len(svr)), key=lambda i: svr[i])
        if peak_i >= len(svr) - 1:
            continue
        trough_after = min(svr[peak_i + 1:])
        drop_frac = (svr[peak_i] - trough_after) / rng
        if drop_frac >= EVENT_DROP_FRAC:
            events.append({
                "caseid": cid,
                "svr_peak": round(svr[peak_i], 1),
                "svr_trough_after": round(trough_after, 1),
                "drop_frac_of_range": round(drop_frac, 3),
                # r_tone_svr NEGATIVE = tone index rose as SVR fell (concordant).
                "r_tone_svr": r.get("r_tone_svr"),
                "concordant": (r.get("r_tone_svr") is not None
                               and r.get("r_tone_svr") < 0),
            })
    events.sort(key=lambda e: -e["drop_frac_of_range"])
    return events


# ===========================================================================
# MAIN
# ===========================================================================
def select_cohort(cfg, cache_dir: str, n: int, seed: int) -> list[str]:
    """Seeded sample of ~n SVR-first cases (ART AND direct EV1000/SVR or SVRI).

    Reuses vasoplegia_validation_extract.build_cohort for the cohort definition,
    then takes a deterministic seeded shuffle of the SVR-first list and keeps the
    first n.  (SVR-first = the direct-measured-SVR cases, the cleanest.)
    """
    from vitaldb_aki.analysis.vasoplegia_validation_extract import build_cohort

    trks_path = os.path.join(cache_dir, "trks.csv")
    _ordered, svr_first = build_cohort(trks_path)
    rng = random.Random(seed)
    pool = list(svr_first)
    rng.shuffle(pool)
    return pool[:n]


def main(n: int | None = None, window_s: float | None = None):
    from common.config import load_yaml
    from vitaldb_aki.data.client import fetch_cases

    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cache_dir = _resolve_cache_dir(cfg)
    os.makedirs(cache_dir, exist_ok=True)
    seed = int(cfg.get("seed", SEED) or SEED)

    if n is None:
        n = int(os.environ.get("DTT_N", DEFAULT_N))
    if window_s is None:
        window_s = float(os.environ.get("DTT_WINDOW", DEFAULT_WINDOW_S))

    cohort = select_cohort(cfg, cache_dir, n, seed)
    print(f"[dtt] dynamic tone tracking: N={len(cohort)} seeded cases "
          f"(seed={seed}), window={window_s:.0f}s", flush=True)

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    case_series_list: list[dict[str, Any]] = []
    percase: list[dict[str, Any]] = []
    n_usable = 0
    for i, cid in enumerate(cohort, 1):
        case = cases_by_id.get(str(cid))
        if case is None:
            print(f"[dtt]  [{i}/{len(cohort)}] case {cid}: not in cases table", flush=True)
            continue
        try:
            cs = extract_case_series(cfg, str(cid), case, window_s)
        except Exception as exc:
            print(f"[dtt]  [{i}/{len(cohort)}] case {cid} FAILED: "
                  f"{type(exc).__name__}: {exc}", flush=True)
            continue
        case_series_list.append(cs)
        res = analyse_case(cs)
        nw = cs.get("n_windows", 0)
        if res is None:
            print(f"[dtt]  [{i}/{len(cohort)}] case {cid}: {nw} windows "
                  f"-> too few usable ({cs.get('note','')})", flush=True)
            continue
        n_usable += 1
        percase.append(res)
        print(f"[dtt]  [{i}/{len(cohort)}] case {cid}: {nw} windows  "
              f"r(tau,SVR)={_fmt(res['r_tau_svr'])} "
              f"r(tone,SVR)={_fmt(res['r_tone_svr'])} "
              f"partial(tone|MAP)={_fmt(res['partial_tone_svr_given_map'])} "
              f"partial(tone|MAP,HR)={_fmt(res['partial_tone_svr_given_map_hr'])} "
              f"SVRcv={cs.get('svr_cv')}", flush=True)

    agg = aggregate(percase)
    events = event_cases(case_series_list, percase)

    results = {
        "config": {
            "n_requested": n, "n_attempted": len(cohort),
            "n_with_series": len(case_series_list),
            "n_usable_cases": n_usable, "window_s": window_s,
            "seed": seed,
            "min_beats_per_window": MIN_BEATS_PER_WINDOW,
            "min_windows_per_case": MIN_WINDOWS_PER_CASE,
            "tone_index": "-z(tau)-z(dia/MAP)-z(AIx); higher=vasoplegic=expect lower SVR",
        },
        "aggregate": agg,
        "events": events,
        "n_events": len(events),
    }

    out_results = os.path.join(cache_dir, OUT_RESULTS)
    with open(out_results, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, allow_nan=False)
    print(f"[dtt] wrote {out_results}", flush=True)

    _write_percase_csv(os.path.join(cache_dir, OUT_PERCASE), percase)
    print(f"[dtt] wrote {os.path.join(cache_dir, OUT_PERCASE)}", flush=True)

    _print_verdict(results)
    return results


def _fmt(v) -> str:
    return f"{v:+.2f}" if (v is not None and math.isfinite(v)) else "  na"


def _write_percase_csv(path: str, percase: list[dict[str, Any]]):
    cols = [
        "caseid", "n_windows", "svr_track", "svr_cv", "svr_min", "svr_max",
        "r_tau_svr", "r_dia_svr", "r_aix_svr", "r_tone_svr",
        "r_map_svr", "r_hr_svr",
        "partial_tone_svr_given_map", "partial_tone_svr_given_map_hr",
        "partial_tau_svr_given_map", "partial_tau_svr_given_map_hr",
        "partial_dia_svr_given_map", "partial_dia_svr_given_map_hr",
        "n_partial_map", "n_partial_map_hr",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in percase:
            w.writerow({k: r.get(k) for k in cols})


def _print_verdict(results: dict[str, Any]):
    agg = results["aggregate"]
    cfg = results["config"]
    print("\n" + "=" * 72, flush=True)
    print("DYNAMIC WITHIN-CASE VASCULAR-TONE TRACKING -- VERDICT", flush=True)
    print("=" * 72, flush=True)
    print(f"usable cases: {cfg['n_usable_cases']}/{cfg['n_attempted']} "
          f"(window={cfg['window_s']:.0f}s)", flush=True)

    def line(label, blk, neg=False):
        m = blk["median"]
        lo, hi = blk["iqr_lo"], blk["iqr_hi"]
        sw = blk["sign_wilcoxon"]
        print(f"  {label:34s} median r={_fmt(m)}  "
              f"IQR[{_fmt(lo)},{_fmt(hi)}]  "
              f"%track={_pct(blk['frac_tracking'])}  "
              f"signp={_pf(sw.get('sign_p'))} wilcoxp={_pf(sw.get('wilcoxon_p'))}",
              flush=True)

    print("\nA. RAW within-case tracking:", flush=True)
    line("tau vs SVR", agg["r_tau_svr"])
    line("diastolic/MAP vs SVR", agg["r_dia_svr"])
    line("AIx vs SVR", agg["r_aix_svr"])
    line("composite tone vs SVR (exp -)", agg["r_tone_svr"], neg=True)
    line("[context] MAP vs SVR", agg["r_map_svr"])
    line("[context] HR vs SVR", agg["r_hr_svr"])
    print("\nB. PARTIAL within-case (the defensible-impact test):", flush=True)
    line("tone vs SVR | MAP", agg["partial_tone_svr_given_map"], neg=True)
    line("tone vs SVR | MAP,HR", agg["partial_tone_svr_given_map_hr"], neg=True)
    line("tau vs SVR | MAP", agg["partial_tau_svr_given_map"])
    line("tau vs SVR | MAP,HR", agg["partial_tau_svr_given_map_hr"])
    print(f"\nC. events (large within-case SVR drop): {results['n_events']} "
          f"cases; concordant tone move in "
          f"{sum(1 for e in results['events'] if e['concordant'])}", flush=True)
    print("=" * 72, flush=True)


def _pct(f) -> str:
    return f"{100*f:.0f}%" if (f is not None and math.isfinite(f)) else "na"


def _pf(p) -> str:
    return f"{p:.3f}" if (p is not None and math.isfinite(p)) else "na"


if __name__ == "__main__":
    _n = None
    _window = None
    argv = sys.argv[1:]
    for k, a in enumerate(argv):
        if a in ("--n", "-n") and k + 1 < len(argv):
            try:
                _n = int(argv[k + 1])
            except ValueError:
                pass
        elif a.startswith("--n="):
            try:
                _n = int(a.split("=", 1)[1])
            except ValueError:
                pass
        elif a == "--window" and k + 1 < len(argv):
            try:
                _window = float(argv[k + 1])
            except ValueError:
                pass
        elif a.startswith("--window="):
            try:
                _window = float(a.split("=", 1)[1])
            except ValueError:
                pass
    main(n=_n, window_s=_window)
