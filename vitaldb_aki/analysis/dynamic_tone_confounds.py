"""dynamic_tone_confounds.py -- DYNAMIC-CONFOUND BATTERY for the within-case
A-line vascular-tone TRACKING finding (VitalDB-AKI Pivot 2).

CONTEXT
-------
analysis/dynamic_tone_tracking.py found that the arterial waveform tracks
within-case measured SVR (carrier = diastolic/MAP form factor; composite tone
index median within-case partial Spearman r ~ -0.33 given MAP+HR, p=3e-7).
The agreement test (docs/PIVOT2_PREPUB_TESTS.md) showed it is a TREND/ranking
signal, not a calibrated SVR estimate.  Three confounds remained UNTESTED and
are critical for the dynamic claim before publication:

1. *** VASOPRESSOR CONFOUND (the critical one) ***
   When a clinician gives/titrates a vasopressor, SVR rises AND the arterial
   waveform changes -- so within-case tone<->SVR tracking could merely be
   detecting DRUG ADMINISTRATION, not sensing tone.
     (a) within-case PARTIAL Spearman(tone, SVR | vasopressor infusion rate):
         does tracking survive controlling for the pressor?
     (b) restrict to STABLE-pressor windows (pressor rate ~constant across
         adjacent windows): does tone still track SVR there?
   If tracking only appears around pressor CHANGES -> drug-detection, not
   tone-sensing -> honest scope/retraction of the dynamic claim.

2. LEAD/LAG
   within-case cross-correlation of tone vs SVR at lags (-L..+L windows) --
   does the waveform tone LEAD measured SVR (early vasoplegia detection) or
   lag it (just following)?  Report the median best-lag.

3. WINDOW-LENGTH sensitivity
   re-run the core within-case tracking at 1-min, 3-min, 5-min windows -- is
   the result robust to the (arbitrary) window choice?

METHOD / REUSE
--------------
Reuses analysis.dynamic_tone_tracking's machinery (windowing of ART, per-window
tone via aline_morphology, median SVR/MAP/HR, composite tone index, partial
Spearman core) and features.vasoactive_pd's pressor-pump knowledge.  We EXTEND
per-window extraction to ALSO pull the Orchestra infusion-pump RATE tracks
(phenylephrine/norepinephrine/epinephrine/dopamine/dobutamine/vasopressin) and
compute, per window, a TOTAL pressor infusion rate.  Two pressor summaries are
carried per window:
   * pressor_norm  -- within-drug normalised total (each pump scaled 0..1 to its
     own in-case max, then summed; unit-free, comparable across drugs).  This is
     the partial-correlation covariate (vasoactive_pd._max_infusion_norm logic).
   * pressor_any   -- 1.0 if any pressor running in the window, else 0.0.

Cohort = the SAME ART + EV1000-SVR seeded sample as dynamic_tone_tracking
(seed 20260626; --n / DTT_N knob; feasibility ~50 cases).  Each case downloads
ART + SVR + MAP + pressor pumps, windows them, and PURGES the big SNUADC + the
small monitor/pump tracks after the case (mirrors dynamic_tone_tracking).

OUTPUTS
-------
  cache/dynamic_tone_confounds_results.json   -- aggregate confound results
  cache/dynamic_tone_confounds_percase.csv    -- per-case partials + best-lag
  docs/PIVOT2_DYNAMIC_CONFOUNDS.md             -- READ-FIRST verdict

Runnable from the repo root /home/user/Codex-playground-/ :
    python vitaldb_aki/analysis/dynamic_tone_confounds.py [--n 50] [--window 180]
Heavy deps (numpy/scipy) are lazy.  Deterministic: seed 20260626.  RESUMABLE: a
per-case window cache (cache/dtc_windows/<caseid>_w<W>.json) lets a re-run skip
already-extracted cases without re-downloading ART.

Leakage firewall: N/A -- no outcome label; entirely within the intraop window
(a physiologic measurement-validation analysis).
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

# Reuse the validated machinery from the tracking module (do NOT modify it).
from vitaldb_aki.analysis import dynamic_tone_tracking as DTT  # noqa: E402

SEED = DTT.SEED                       # 20260626
DEFAULT_N = DTT.DEFAULT_N             # 50
DEFAULT_WINDOW_S = DTT.DEFAULT_WINDOW_S  # 180 (3 min)

# Window lengths for the sensitivity sweep (seconds): 1-min, 3-min, 5-min.
WINDOW_SWEEP_S = (60.0, 180.0, 300.0)

# Lead/lag range, in WINDOWS.  +lag means tone[t] vs SVR[t+lag] (tone leads SVR).
MAX_LAG_WINDOWS = 3

# Pressor pumps (reuse vasoactive_pd's pre-registered list).
from vitaldb_aki.features.vasoactive_pd import PRESSORS  # noqa: E402

# A window is "pressor-stable" if the change in normalised pressor rate from the
# PREVIOUS window is below this absolute threshold (no meaningful titration).
PRESSOR_STABLE_DELTA = 0.05

OUT_RESULTS = "dynamic_tone_confounds_results.json"
OUT_PERCASE = "dynamic_tone_confounds_percase.csv"
_WIN_CACHE_DIR = "dtc_windows"   # under cache/; resumable per-case window series


# ===========================================================================
# PER-WINDOW PRESSOR RATE (extends DTT.extract_case_series)
# ===========================================================================
def _pump_window_norm(pump_series: dict[str, list[tuple[float, float]]],
                      pump_max: dict[str, float],
                      w_start: float, w_end: float) -> tuple[float, float]:
    """Per-window pressor summaries from the Orchestra pump RATE tracks.

    Returns (pressor_norm, pressor_any):
      pressor_norm = sum over pumps of (median in-window rate / in-case max rate),
                     i.e. each pump normalised within-drug to 0..1, then summed.
                     Robust to wildly different dosing units across drugs.
      pressor_any  = 1.0 if any pump has a positive in-window sample, else 0.0.

    If a window has no in-window samples for a pump, that pump contributes 0 to
    the window (the pump is idle / no data there).  We use the median in-window
    rate (not last-value-hold) to mirror the SVR/MAP per-window median used in
    DTT, so all per-window quantities are window-median summaries.
    """
    total = 0.0
    any_run = 0.0
    for tn, series in pump_series.items():
        mx = pump_max.get(tn, 0.0)
        if mx <= 0.0:
            continue
        vals = [v for (ts, v) in series if w_start <= ts < w_end and v >= 0.0]
        if not vals:
            continue
        med = DTT._median(vals)
        if med is None:
            continue
        if med > 0.0:
            any_run = 1.0
        total += med / mx
    return round(total, 6), any_run


def extract_case_series_with_pressor(cfg, cid: str, case: dict[str, Any],
                                     window_s: float) -> dict[str, Any]:
    """Like DTT.extract_case_series but ALSO attaches per-window pressor rate.

    We re-run the same ART/SVR/MAP windowing as DTT (calling DTT.extract_case_series
    is not enough because we must add a per-window pressor field; rather than
    duplicate the heavy ART download twice, we inline the extraction once and add
    the pump tracks).  Always purges the big SNUADC + monitor + pump tracks in a
    finally block.
    """
    from vitaldb_aki.data import tracks as _T
    from vitaldb_aki.features import aline_morphology as _aline

    out: dict[str, Any] = {
        "caseid": cid, "n_windows": 0, "windows": [],
        "svr_track": None, "svr_cv": None, "svr_min": None,
        "svr_max": None, "svr_median": None, "note": "",
        "n_pressor_pumps": 0, "frac_windows_on_pressor": None,
    }
    try:
        t_start, t_end = _aline._intraop_window(case)

        # --- measured SVR track (prefer raw SVR; SVRI is BSA-scaled, monotone) ---
        svr_name = None
        svr_raw: list[tuple[float, float]] = []
        for tn in DTT.SVR_TRACKS:
            s = _T.download_track(cfg, cid, tn)
            if s:
                svr_name = tn
                svr_raw = s
                break
        if not svr_raw:
            out["note"] = "no SVR/SVRI track"
            return out
        out["svr_track"] = svr_name
        svr_samples = [(ts, v) for (ts, v) in svr_raw
                       if (t_start is None or ts >= t_start)
                       and (t_end is None or ts <= t_end)
                       and DTT.SVR_MIN <= v <= DTT.SVR_MAX]
        if len(svr_samples) < DTT.MIN_SVR_SAMPLES_PER_WINDOW * DTT.MIN_WINDOWS_PER_CASE:
            out["note"] = f"too few in-window SVR samples ({len(svr_samples)})"
            return out
        svr_vals = [v for _, v in svr_samples]
        out["svr_min"] = round(min(svr_vals), 2)
        out["svr_max"] = round(max(svr_vals), 2)
        med = DTT._median(svr_vals)
        out["svr_median"] = round(med, 2) if med is not None else None
        if med and med > 0:
            mu = sum(svr_vals) / len(svr_vals)
            sd = math.sqrt(sum((v - mu) ** 2 for v in svr_vals) / len(svr_vals))
            out["svr_cv"] = round(sd / mu, 4) if mu > 0 else None

        # --- MAP track (numeric, Solar8000/ART_MBP) ---
        map_raw = _T.download_track(cfg, cid, DTT.MAP_TRACK)
        map_samples = [(ts, v) for (ts, v) in map_raw
                       if (t_start is None or ts >= t_start)
                       and (t_end is None or ts <= t_end)
                       and DTT.MAP_MIN <= v <= DTT.MAP_MAX]

        # --- Pressor RATE pump tracks (reuse vasoactive_pd pump set) ---
        pump_series: dict[str, list[tuple[float, float]]] = {}
        pump_max: dict[str, float] = {}
        for tn in PRESSORS:
            raw = _T.download_track(cfg, cid, tn)
            if not raw:
                continue
            clipped = [(ts, v) for (ts, v) in raw
                       if (t_start is None or ts >= t_start)
                       and (t_end is None or ts <= t_end)
                       and v >= 0.0]
            if not clipped:
                continue
            mx = max((v for _, v in clipped if v > 0.0), default=0.0)
            if mx <= 0.0:
                # pump present but never ran in window; still record as 0-contribution
                continue
            pump_series[tn] = clipped
            pump_max[tn] = mx
        out["n_pressor_pumps"] = len(pump_series)

        # --- ART waveform (reconstructed 500 Hz grid) ---
        wt, wv = _aline.load_art_waveform(cfg, cid, _aline.ART_TRACK_CANDIDATES)
        if wt is None or len(wt) < 2:
            out["note"] = "no usable ART waveform"
            return out

        import numpy as np
        wt = np.asarray(wt, dtype=float)
        wv = np.asarray(wv, dtype=float)
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
        w_endt = float(wt[-1])

        windows: list[dict[str, Any]] = []
        n_on_pressor = 0
        ws = w0
        while ws + window_s <= w_endt + 1e-6:
            we = ws + window_s
            i0 = int(np.searchsorted(wt, ws, side="left"))
            i1 = int(np.searchsorted(wt, we, side="left"))
            ws_next = ws + window_s
            if i1 > i0:
                seg_t = wt[i0:i1]
                seg_v = wv[i0:i1]
                tone = DTT.window_tone(seg_t, seg_v, fs)
            else:
                tone = None
            svr_med, n_svr = DTT._window_median(svr_samples, ws, we,
                                                DTT.SVR_MIN, DTT.SVR_MAX)
            map_med, n_map = DTT._window_median(map_samples, ws, we,
                                                DTT.MAP_MIN, DTT.MAP_MAX)
            pressor_norm, pressor_any = _pump_window_norm(
                pump_series, pump_max, ws, we)
            ws = ws_next
            if tone is None:
                continue
            if svr_med is None or n_svr < DTT.MIN_SVR_SAMPLES_PER_WINDOW:
                continue
            rec = dict(tone)
            rec["t_start"] = round(float(we - window_s), 1)
            rec["svr"] = round(svr_med, 3)
            rec["n_svr"] = n_svr
            rec["map_num"] = round(map_med, 3) if map_med is not None else None
            rec["n_map"] = n_map
            rec["pressor_norm"] = pressor_norm
            rec["pressor_any"] = pressor_any
            if pressor_any > 0.0:
                n_on_pressor += 1
            windows.append(rec)

        out["windows"] = windows
        out["n_windows"] = len(windows)
        out["frac_windows_on_pressor"] = (
            round(n_on_pressor / len(windows), 4) if windows else None)
        return out
    finally:
        for tn in (DTT._BIG_SNUADC_TRACKS + DTT._MONITOR_TRACKS + tuple(PRESSORS)):
            try:
                _T.purge_track(cfg, cid, tn)
            except Exception:
                pass


# ===========================================================================
# CONFOUND 1: VASOPRESSOR PARTIAL + STABLE-PRESSOR WINDOWS
# ===========================================================================
def analyse_case_confounds(cs: dict[str, Any]) -> dict[str, Any] | None:
    """Within-case confound analyses for one case's pressor-augmented series."""
    windows = cs.get("windows") or []
    if len(windows) < DTT.MIN_WINDOWS_PER_CASE:
        return None

    svr = [w.get("svr") for w in windows]
    dia = [w.get("dia_over_map") for w in windows]
    hr = [w.get("hr") for w in windows]
    mapc = [w.get("map_num") if w.get("map_num") is not None else w.get("map_wave")
            for w in windows]
    pressor = [w.get("pressor_norm") for w in windows]
    tone_idx = DTT.build_tone_index(windows)

    res: dict[str, Any] = {
        "caseid": cs["caseid"],
        "n_windows": len(windows),
        "svr_cv": cs.get("svr_cv"),
        "frac_windows_on_pressor": cs.get("frac_windows_on_pressor"),
        "n_pressor_pumps": cs.get("n_pressor_pumps", 0),
    }

    # ---- baseline (unadjusted + given MAP+HR, to anchor against DTT) ----
    res["r_tone_svr"] = DTT.spearman(tone_idx, svr)
    res["r_dia_svr"] = DTT.spearman(dia, svr)
    res["partial_tone_svr_given_map_hr"], _ = DTT.partial_spearman(
        tone_idx, svr, [mapc, hr])
    res["partial_dia_svr_given_map_hr"], _ = DTT.partial_spearman(
        dia, svr, [mapc, hr])

    # ---- CONFOUND 1a: PARTIAL given vasopressor rate (and given MAP+HR+pressor) ----
    # Only meaningful if pressor actually varied within the case.
    pvals = [p for p in pressor if p is not None and math.isfinite(p)]
    pressor_varies = len(pvals) >= 3 and (max(pvals) - min(pvals)) > 1e-9
    res["pressor_varies"] = bool(pressor_varies)
    if pressor_varies:
        r_p, n_p = DTT.partial_spearman(tone_idx, svr, [pressor])
        r_dp, _ = DTT.partial_spearman(dia, svr, [pressor])
        r_full, n_full = DTT.partial_spearman(tone_idx, svr, [mapc, hr, pressor])
        r_dfull, _ = DTT.partial_spearman(dia, svr, [mapc, hr, pressor])
        res["partial_tone_svr_given_pressor"] = r_p
        res["partial_dia_svr_given_pressor"] = r_dp
        res["partial_tone_svr_given_map_hr_pressor"] = r_full
        res["partial_dia_svr_given_map_hr_pressor"] = r_dfull
        res["n_partial_pressor"] = n_p
    else:
        res["partial_tone_svr_given_pressor"] = None
        res["partial_dia_svr_given_pressor"] = None
        res["partial_tone_svr_given_map_hr_pressor"] = None
        res["partial_dia_svr_given_map_hr_pressor"] = None
        res["n_partial_pressor"] = None

    # ---- CONFOUND 1b: STABLE-PRESSOR WINDOWS ----
    # Keep window i (i>=1) iff |pressor[i]-pressor[i-1]| < threshold AND that
    # window is not adjacent to a titration.  Within those stable windows, does
    # tone still track SVR?  (If tracking vanishes here -> drug-detection.)
    stable_idx: list[int] = []
    for i in range(1, len(windows)):
        pi, pj = pressor[i], pressor[i - 1]
        if pi is None or pj is None:
            continue
        if abs(pi - pj) < PRESSOR_STABLE_DELTA:
            stable_idx.append(i)
    res["n_stable_windows"] = len(stable_idx)
    if len(stable_idx) >= DTT.MIN_WINDOWS_PER_CASE:
        s_tone = [tone_idx[i] for i in stable_idx]
        s_dia = [dia[i] for i in stable_idx]
        s_svr = [svr[i] for i in stable_idx]
        s_map = [mapc[i] for i in stable_idx]
        s_hr = [hr[i] for i in stable_idx]
        res["r_tone_svr_stable"] = DTT.spearman(s_tone, s_svr)
        res["r_dia_svr_stable"] = DTT.spearman(s_dia, s_svr)
        res["partial_tone_svr_stable_given_map_hr"], _ = DTT.partial_spearman(
            s_tone, s_svr, [s_map, s_hr])
        res["partial_dia_svr_stable_given_map_hr"], _ = DTT.partial_spearman(
            s_dia, s_svr, [s_map, s_hr])
    else:
        res["r_tone_svr_stable"] = None
        res["r_dia_svr_stable"] = None
        res["partial_tone_svr_stable_given_map_hr"] = None
        res["partial_dia_svr_stable_given_map_hr"] = None

    # ---- CONFOUND 2: LEAD/LAG cross-correlation ----
    # tone[t] vs SVR[t+lag].  +lag = tone leads SVR (clinically valuable).
    # Use the dia/MAP carrier (cleanest single feature) AND composite tone.
    res["best_lag_dia"], res["best_lag_r_dia"], res["lag_profile_dia"] = \
        _best_lag(dia, svr, MAX_LAG_WINDOWS, expect_sign=+1)
    res["best_lag_tone"], res["best_lag_r_tone"], res["lag_profile_tone"] = \
        _best_lag(tone_idx, svr, MAX_LAG_WINDOWS, expect_sign=-1)

    return res


def _best_lag(x: list[float | None], y: list[float | None], max_lag: int,
              expect_sign: int) -> tuple[int | None, float | None, dict[int, float | None]]:
    """Lagged Spearman of x[t] vs y[t+lag] for lag in [-max_lag, +max_lag].

    +lag => x leads y (x at t correlated with y at t+lag).  Returns
    (best_lag, r_at_best_lag, full_profile).  "best" = the lag whose correlation
    is most extreme in the EXPECTED direction (expect_sign: +1 for dia/MAP which
    tracks SVR positively, -1 for composite tone which tracks negatively), so a
    spurious wrong-sign peak does not masquerade as the lead.
    """
    n = len(x)
    profile: dict[int, float | None] = {}
    for lag in range(-max_lag, max_lag + 1):
        # align x[t] with y[t+lag]
        xs: list[float] = []
        ys: list[float] = []
        for t in range(n):
            u = t + lag
            if 0 <= u < n:
                a, b = x[t], y[u]
                if (a is not None and b is not None
                        and math.isfinite(a) and math.isfinite(b)):
                    xs.append(a)
                    ys.append(b)
        profile[lag] = DTT.spearman(xs, ys) if len(xs) >= DTT.MIN_WINDOWS_PER_CASE else None
    # best = most-extreme correlation in the expected direction
    best_lag = None
    best_r = None
    for lag, r in profile.items():
        if r is None:
            continue
        signed = expect_sign * r  # larger = more in expected direction
        if best_r is None or signed > expect_sign * best_r:
            best_lag = lag
            best_r = r
    return best_lag, best_r, profile


# ===========================================================================
# AGGREGATION
# ===========================================================================
def _summ(percase: list[dict[str, Any]], key: str,
          expect_negative: bool = False) -> dict[str, Any]:
    vals = [r[key] for r in percase
            if r.get(key) is not None and isinstance(r.get(key), (int, float))
            and math.isfinite(r.get(key))]
    lo, hi = DTT._iqr(vals)
    if expect_negative:
        frac = (sum(1 for v in vals if v < -0.3) / len(vals)) if vals else None
    else:
        frac = (sum(1 for v in vals if abs(v) > 0.3) / len(vals)) if vals else None
    return {
        "n": len(vals),
        "median": DTT._median(vals),
        "iqr_lo": lo, "iqr_hi": hi,
        "frac_tracking": frac,
        "sign_wilcoxon": DTT._sign_wilcoxon(vals),
    }


def aggregate_confounds(percase: list[dict[str, Any]]) -> dict[str, Any]:
    # subset of cases where pressor varied (the ones where 1a is meaningful)
    pc_var = [r for r in percase if r.get("pressor_varies")]
    pc_stable = [r for r in percase if r.get("r_dia_svr_stable") is not None]

    # lead/lag aggregate
    lags_dia = [r["best_lag_dia"] for r in percase if r.get("best_lag_dia") is not None]
    lags_tone = [r["best_lag_tone"] for r in percase if r.get("best_lag_tone") is not None]

    return {
        "anchor": {
            "r_dia_svr": _summ(percase, "r_dia_svr"),
            "r_tone_svr": _summ(percase, "r_tone_svr", expect_negative=True),
            "partial_dia_svr_given_map_hr": _summ(percase, "partial_dia_svr_given_map_hr"),
            "partial_tone_svr_given_map_hr": _summ(percase, "partial_tone_svr_given_map_hr",
                                                   expect_negative=True),
        },
        "confound1_vasopressor": {
            "n_cases_pressor_varies": len(pc_var),
            "partial_dia_svr_given_pressor": _summ(pc_var, "partial_dia_svr_given_pressor"),
            "partial_tone_svr_given_pressor": _summ(pc_var, "partial_tone_svr_given_pressor",
                                                    expect_negative=True),
            "partial_dia_svr_given_map_hr_pressor": _summ(
                pc_var, "partial_dia_svr_given_map_hr_pressor"),
            "partial_tone_svr_given_map_hr_pressor": _summ(
                pc_var, "partial_tone_svr_given_map_hr_pressor", expect_negative=True),
        },
        "confound1b_stable_pressor_windows": {
            "n_cases_with_stable_windows": len(pc_stable),
            "r_dia_svr_stable": _summ(pc_stable, "r_dia_svr_stable"),
            "r_tone_svr_stable": _summ(pc_stable, "r_tone_svr_stable", expect_negative=True),
            "partial_dia_svr_stable_given_map_hr": _summ(
                pc_stable, "partial_dia_svr_stable_given_map_hr"),
            "partial_tone_svr_stable_given_map_hr": _summ(
                pc_stable, "partial_tone_svr_stable_given_map_hr", expect_negative=True),
        },
        "confound2_lead_lag": {
            "n_cases_dia": len(lags_dia),
            "median_best_lag_dia": DTT._median([float(x) for x in lags_dia]),
            "lag_histogram_dia": _lag_hist(lags_dia),
            "best_lag_r_dia": _summ(percase, "best_lag_r_dia"),
            "n_cases_tone": len(lags_tone),
            "median_best_lag_tone": DTT._median([float(x) for x in lags_tone]),
            "lag_histogram_tone": _lag_hist(lags_tone),
        },
    }


def _lag_hist(lags: list[int]) -> dict[str, int]:
    h: dict[str, int] = {}
    for l in lags:
        h[str(l)] = h.get(str(l), 0) + 1
    return dict(sorted(h.items(), key=lambda kv: int(kv[0])))


# ===========================================================================
# MAIN
# ===========================================================================
def _win_cache_path(cache_dir: str, cid: str, window_s: float) -> str:
    d = os.path.join(cache_dir, _WIN_CACHE_DIR)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{cid}_w{int(window_s)}.json")


def get_case_series(cfg, cache_dir: str, cid: str, case: dict[str, Any],
                    window_s: float) -> dict[str, Any]:
    """Resumable: load the per-case window series from disk if cached, else
    extract (downloading + purging ART) and persist it."""
    path = _win_cache_path(cache_dir, cid, window_s)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                cs = json.load(fh)
            if cs.get("windows"):
                return cs
        except Exception:
            pass
    cs = extract_case_series_with_pressor(cfg, cid, case, window_s)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cs, fh, allow_nan=False)
    except Exception:
        pass
    return cs


def main(n: int | None = None, window_s: float | None = None):
    from common.config import load_yaml
    from vitaldb_aki.data.client import fetch_cases

    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cache_dir = DTT._resolve_cache_dir(cfg)
    os.makedirs(cache_dir, exist_ok=True)
    seed = int(cfg.get("seed", SEED) or SEED)

    if n is None:
        n = int(os.environ.get("DTT_N", DEFAULT_N))
    if window_s is None:
        window_s = float(os.environ.get("DTT_WINDOW", DEFAULT_WINDOW_S))

    cohort = DTT.select_cohort(cfg, cache_dir, n, seed)
    print(f"[dtc] dynamic-tone CONFOUND battery: N={len(cohort)} seeded cases "
          f"(seed={seed}), primary window={window_s:.0f}s", flush=True)
    print(f"[dtc] pressor pumps: {list(PRESSORS)}", flush=True)

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    # ---- PRIMARY-WINDOW pass: extract pressor-augmented series + confound 1/2 ----
    percase: list[dict[str, Any]] = []
    series_by_id: dict[str, dict[str, Any]] = {}
    n_usable = 0
    for i, cid in enumerate(cohort, 1):
        case = cases_by_id.get(str(cid))
        if case is None:
            print(f"[dtc]  [{i}/{len(cohort)}] case {cid}: not in cases table", flush=True)
            continue
        try:
            cs = get_case_series(cfg, cache_dir, str(cid), case, window_s)
        except Exception as exc:
            print(f"[dtc]  [{i}/{len(cohort)}] case {cid} FAILED: "
                  f"{type(exc).__name__}: {exc}", flush=True)
            continue
        series_by_id[str(cid)] = cs
        res = analyse_case_confounds(cs)
        nw = cs.get("n_windows", 0)
        if res is None:
            print(f"[dtc]  [{i}/{len(cohort)}] case {cid}: {nw} windows "
                  f"-> too few usable ({cs.get('note','')})", flush=True)
            continue
        n_usable += 1
        percase.append(res)
        print(f"[dtc]  [{i}/{len(cohort)}] case {cid}: {nw}w  "
              f"onPressor={_pct(cs.get('frac_windows_on_pressor'))}  "
              f"dia|MAP,HR={_f(res.get('partial_dia_svr_given_map_hr'))}  "
              f"dia|pressor={_f(res.get('partial_dia_svr_given_pressor'))}  "
              f"dia|MAP,HR,P={_f(res.get('partial_dia_svr_given_map_hr_pressor'))}  "
              f"diaStable={_f(res.get('r_dia_svr_stable'))}  "
              f"lag(dia)={res.get('best_lag_dia')}", flush=True)

    agg = aggregate_confounds(percase)

    # ---- CONFOUND 3: WINDOW-LENGTH SENSITIVITY ----
    # Re-run the core within-case tracking (dia/MAP + composite tone, given MAP+HR)
    # at 1/3/5-min windows.  Reuse the resumable per-case cache.
    print("\n[dtc] window-length sensitivity sweep "
          f"({', '.join(str(int(w)) for w in WINDOW_SWEEP_S)}s) ...", flush=True)
    window_sweep: dict[str, Any] = {}
    for w in WINDOW_SWEEP_S:
        pc_w: list[dict[str, Any]] = []
        for cid in cohort:
            case = cases_by_id.get(str(cid))
            if case is None:
                continue
            try:
                cs = get_case_series(cfg, cache_dir, str(cid), case, w)
            except Exception:
                continue
            r = analyse_case_confounds(cs)
            if r is not None:
                pc_w.append(r)
        window_sweep[f"{int(w)}s"] = {
            "n_usable": len(pc_w),
            "r_dia_svr": _summ(pc_w, "r_dia_svr"),
            "partial_dia_svr_given_map_hr": _summ(pc_w, "partial_dia_svr_given_map_hr"),
            "r_tone_svr": _summ(pc_w, "r_tone_svr", expect_negative=True),
            "partial_tone_svr_given_map_hr": _summ(
                pc_w, "partial_tone_svr_given_map_hr", expect_negative=True),
        }
        b = window_sweep[f"{int(w)}s"]
        print(f"[dtc]   window={int(w)}s: n={b['n_usable']:2d}  "
              f"dia r={_f(b['r_dia_svr']['median'])}  "
              f"dia|MAP,HR={_f(b['partial_dia_svr_given_map_hr']['median'])}  "
              f"tone|MAP,HR={_f(b['partial_tone_svr_given_map_hr']['median'])}",
              flush=True)

    results = {
        "config": {
            "n_requested": n, "n_attempted": len(cohort),
            "n_usable_cases": n_usable, "primary_window_s": window_s,
            "window_sweep_s": list(WINDOW_SWEEP_S),
            "max_lag_windows": MAX_LAG_WINDOWS,
            "pressor_stable_delta": PRESSOR_STABLE_DELTA,
            "pressors": list(PRESSORS),
            "seed": seed,
            "tone_index": "-z(tau)-z(dia/MAP)-z(AIx); higher=vasoplegic=expect lower SVR",
            "pressor_norm": "sum over pumps of (median in-window rate / in-case max); unitless",
        },
        "aggregate": agg,
        "window_sweep": window_sweep,
    }

    out_results = os.path.join(cache_dir, OUT_RESULTS)
    with open(out_results, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, allow_nan=False)
    print(f"\n[dtc] wrote {out_results}", flush=True)

    _write_percase_csv(os.path.join(cache_dir, OUT_PERCASE), percase)
    print(f"[dtc] wrote {os.path.join(cache_dir, OUT_PERCASE)}", flush=True)

    _print_verdict(results)
    return results


def _f(v) -> str:
    if isinstance(v, dict):
        v = v.get("median")
    return f"{v:+.2f}" if (v is not None and isinstance(v, (int, float))
                           and math.isfinite(v)) else "  na"


def _pct(f) -> str:
    return f"{100*f:.0f}%" if (f is not None and isinstance(f, (int, float))
                               and math.isfinite(f)) else "na"


def _pf(p) -> str:
    return f"{p:.2e}" if (p is not None and isinstance(p, (int, float))
                          and math.isfinite(p)) else "na"


def _write_percase_csv(path: str, percase: list[dict[str, Any]]):
    cols = [
        "caseid", "n_windows", "svr_cv", "frac_windows_on_pressor",
        "n_pressor_pumps", "pressor_varies",
        "r_dia_svr", "r_tone_svr",
        "partial_dia_svr_given_map_hr", "partial_tone_svr_given_map_hr",
        "partial_dia_svr_given_pressor", "partial_tone_svr_given_pressor",
        "partial_dia_svr_given_map_hr_pressor", "partial_tone_svr_given_map_hr_pressor",
        "n_stable_windows", "r_dia_svr_stable", "r_tone_svr_stable",
        "partial_dia_svr_stable_given_map_hr", "partial_tone_svr_stable_given_map_hr",
        "best_lag_dia", "best_lag_r_dia", "best_lag_tone",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in percase:
            w.writerow({k: r.get(k) for k in cols})


def _print_verdict(results: dict[str, Any]):
    agg = results["aggregate"]
    cfg = results["config"]
    print("\n" + "=" * 74, flush=True)
    print("DYNAMIC-TONE CONFOUND BATTERY -- VERDICT", flush=True)
    print("=" * 74, flush=True)
    print(f"usable cases: {cfg['n_usable_cases']}/{cfg['n_attempted']} "
          f"(window={cfg['primary_window_s']:.0f}s)", flush=True)

    def line(label, blk):
        m = blk["median"]
        lo, hi = blk["iqr_lo"], blk["iqr_hi"]
        sw = blk["sign_wilcoxon"]
        print(f"  {label:40s} n={blk['n']:2d} med r={_f(m)} "
              f"IQR[{_f(lo)},{_f(hi)}] %trk={_pct(blk['frac_tracking'])} "
              f"wilcoxp={_pf(sw.get('wilcoxon_p'))}", flush=True)

    an = agg["anchor"]
    print("\nANCHOR (reproduce DTT within this run):", flush=True)
    line("dia/MAP vs SVR", an["r_dia_svr"])
    line("dia/MAP vs SVR | MAP,HR", an["partial_dia_svr_given_map_hr"])
    line("composite tone vs SVR | MAP,HR", an["partial_tone_svr_given_map_hr"])

    c1 = agg["confound1_vasopressor"]
    print(f"\nCONFOUND 1 -- VASOPRESSOR (n cases pressor varied = "
          f"{c1['n_cases_pressor_varies']}):", flush=True)
    line("dia/MAP vs SVR | pressor", c1["partial_dia_svr_given_pressor"])
    line("dia/MAP vs SVR | MAP,HR,pressor", c1["partial_dia_svr_given_map_hr_pressor"])
    line("tone vs SVR | MAP,HR,pressor", c1["partial_tone_svr_given_map_hr_pressor"])

    c1b = agg["confound1b_stable_pressor_windows"]
    print(f"\nCONFOUND 1b -- STABLE-PRESSOR WINDOWS (n cases = "
          f"{c1b['n_cases_with_stable_windows']}):", flush=True)
    line("dia/MAP vs SVR (stable windows)", c1b["r_dia_svr_stable"])
    line("dia/MAP vs SVR | MAP,HR (stable)", c1b["partial_dia_svr_stable_given_map_hr"])

    c2 = agg["confound2_lead_lag"]
    print(f"\nCONFOUND 2 -- LEAD/LAG (+lag = tone LEADS SVR):", flush=True)
    print(f"  dia/MAP best lag: median={c2['median_best_lag_dia']} windows  "
          f"hist={c2['lag_histogram_dia']}", flush=True)
    print(f"  tone     best lag: median={c2['median_best_lag_tone']} windows  "
          f"hist={c2['lag_histogram_tone']}", flush=True)

    print(f"\nCONFOUND 3 -- WINDOW-LENGTH SENSITIVITY:", flush=True)
    for w, b in results["window_sweep"].items():
        print(f"  {w:>5s}: n={b['n_usable']:2d}  dia r={_f(b['r_dia_svr']['median'])}  "
              f"dia|MAP,HR={_f(b['partial_dia_svr_given_map_hr']['median'])}  "
              f"tone|MAP,HR={_f(b['partial_tone_svr_given_map_hr']['median'])}",
              flush=True)
    print("=" * 74, flush=True)


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
