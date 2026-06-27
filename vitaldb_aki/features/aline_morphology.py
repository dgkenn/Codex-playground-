"""aline_morphology.py -- Beat-level arterial-waveform morphology (§7C/§7F).

The hemodynamics module (§7C) summarizes the arterial line through Solar8000's
already-collapsed MAP/SBP numerics (~0.5 Hz). That throws away everything the raw
500 Hz arterial pressure waveform (`SNUADC/ART`, §7F -- "the all information that
tabular summaries discard") carries about *each cardiac cycle*: the upstroke slope
(contractility / dP/dt), the beat-to-beat pulse-pressure variation that signals
hypovolemia / fluid-responsiveness (PPV -- directly relevant to renal perfusion),
and the systolic ejection area. This module reconstructs those BEAT-LEVEL features
from the raw waveform and aggregates them across the case.

Why this is renally relevant (§7C/§7F):
  * dP/dt_max  -- a left-ventricular contractility surrogate; low contractility ->
                  low cardiac output -> renal hypoperfusion.
  * PPV (%)    -- a *validated* dynamic preload / fluid-responsiveness index; high
                  PPV under positive-pressure ventilation signals hypovolemia, a
                  classic prerenal-AKI driver that a static MAP mean cannot see.
  * pulse pressure & its variability -- vascular tone / stroke-volume variation.

------------------------------------------------------------------------------
WINDOWING (the waveform is BIG: ~3.5M samples / case, multi-MB)
------------------------------------------------------------------------------
We never hold or analyze the whole 500 Hz trace. We carve the intraop window into
short ANALYSIS WINDOWS -- one clean `ANALYSIS_WINDOW_S`-second segment taken every
`WINDOW_PERIOD_S` seconds across the case, capped at `MAX_ANALYSIS_WINDOWS` windows
per case. Beats are detected *within* each window, physiologic-gated, and only the
per-beat scalars (a handful of floats) are kept; the raw samples for a window are
discarded before the next window is processed. All windowing parameters are
module-top constants so a config-readable audit can reference them.

RESPIRATORY WINDOW (for PPV)
  Within each analysis window we further split into `RESP_BLOCK_S`-second blocks
  (default 8 s -- one mechanical-ventilation respiratory cycle is ~3-5 s, so an
  8 s block spans >=1 full respiratory cycle of PP oscillation). PPV per block =
  100 * (PP_max - PP_min) / PP_mean over the beats in that block; we average the
  per-block PPV across all blocks / windows (Michard's definition, §7C/§7F).

------------------------------------------------------------------------------
BEAT DETECTION
------------------------------------------------------------------------------
Light systolic-peak detection via scipy.signal.find_peaks with a refractory
distance derived from the max physiologic HR (so peaks can't be closer than one
`HR_MAX`-bpm cycle). For each systolic peak we find the preceding diastolic trough
(the local minimum in the search window before the peak); SBP = pressure at peak,
DBP = pressure at the preceding trough, PP = SBP - DBP, and dP/dt_max = the max
positive sample-to-sample slope on the upstroke between trough and peak. The
systolic AUC is the area between the waveform and the diastolic baseline from the
upstroke foot to the dicrotic region (approximated foot->next-foot above DBP),
normalized by PP*beat-duration so it is a dimensionless ejection-shape index.

PHYSIOLOGIC GATING (reject non-physiologic beats)
  HR in [HR_MIN_BPM, HR_MAX_BPM] (40-200 bpm via beat interval),
  SBP in [SBP_MIN, SBP_MAX] = [40, 250] mmHg,
  DBP in [DBP_MIN, DBP_MAX] = [10, 150] mmHg,
  SBP > DBP and PP in [PP_MIN, PP_MAX] = [5, 200] mmHg.
Beats failing any gate are dropped (flush artefacts, clamp/zeroing, ectopy).

MISSINGNESS
  If no usable ART waveform is found (track absent, or no physiologic beats in any
  window), EVERY feature is None except `aline_available` = 0 -- never fabricated
  zeros (mirrors hemodynamics.py's honest-missingness contract).

Leakage compliance (§11): the waveform is clipped to the intraop window
[anestart|opstart, opend]; NO sample with t > opend is ever read. All specs are
"intraop"; audit_specs() enforces it at import.

Protocol reference: §7C (intraoperative hemodynamic axis), §7F (raw arterial
waveform -- information tabular MAP summaries discard).
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case (downloads ~2 s).
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Raw arterial waveform track (§7F). ~500 Hz, present for ~71% of the cohort.
# ---------------------------------------------------------------------------
ART_TRACK_CANDIDATES: list[str] = [
    "SNUADC/ART",
]
# Nominal raw sampling rate; the true fs is estimated per case from timestamps.
ART_FS_HZ_NOMINAL: float = 500.0

# ---------------------------------------------------------------------------
# Windowing constants (config-readable; binding). The trace is processed window
# by window so we never hold all ~3.5M samples at once.
# ---------------------------------------------------------------------------
ANALYSIS_WINDOW_S: float = 16.0      # length of each clean analysis segment (s)
WINDOW_PERIOD_S: float = 300.0       # take one window every 5 minutes across case
MAX_ANALYSIS_WINDOWS: int = 60       # hard cap on windows per case (tractability)
RESP_BLOCK_S: float = 8.0            # respiratory block for PPV (>=1 vent cycle)
MIN_BEATS_PER_RESP_BLOCK: int = 3    # need >=3 beats to define PP_max/min/mean

# Max single inter-sample gap (s) inside a window; a larger gap means a recording
# break -- we split the window there rather than spanning the gap.
MAX_INTER_SAMPLE_DT_S: float = 0.05  # 50 ms == ~25 missing samples at 500 Hz

# ---------------------------------------------------------------------------
# Physiologic gates for beat rejection (binding; documented in pre-registration).
# ---------------------------------------------------------------------------
HR_MIN_BPM: float = 40.0
HR_MAX_BPM: float = 200.0
SBP_MIN: float = 40.0
SBP_MAX: float = 250.0
DBP_MIN: float = 10.0
DBP_MAX: float = 150.0
PP_MIN: float = 5.0
PP_MAX: float = 200.0
# Whole-waveform sample gate (drop flush/zeroing artefacts before peak finding).
ART_SAMPLE_MIN: float = 0.0
ART_SAMPLE_MAX: float = 300.0

# ---------------------------------------------------------------------------
# Vascular-tone (per-beat) feature parameters (binding; pre-registered).
#
# art_tau_decay_mean : diastolic decay time constant tau = R*C of the arterial
#   tree.  Per beat we fit P(t) = P0*exp(-t/tau) + Pinf over the DIASTOLIC
#   segment (from just after the systolic peak / dicrotic region down to
#   end-diastole) by LOG-LINEAR least squares on (P - Pinf).  tau is a strong
#   arterial-tone / SVR marker (higher tau => higher compliance*resistance).
#
# art_aug_index_mean : augmentation index AIx = (P_infl - P_dia)/(P_sys - P_dia),
#   where P_infl is the inflection (shoulder from the reflected wave) detected on
#   the upstroke-to-peak segment via the 2nd-derivative zero-crossing.  AIx from
#   raw ART is APPROXIMATE; art_aug_index_quality reports the fraction of beats
#   with a usable inflection so downstream can weight it.
# ---------------------------------------------------------------------------
TAU_MIN_S: float = 0.1          # physiologic floor for the decay constant (s)
TAU_MAX_S: float = 3.0          # physiologic ceiling for the decay constant (s)
TAU_MIN_R2: float = 0.80        # min log-linear fit R^2 to accept a beat's tau
TAU_DIASTOLE_FRAC: float = 0.25 # start the diastolic fit this fraction of the
                                #   beat AFTER the systolic peak (skip the dicrotic
                                #   notch / incisura transient)
TAU_MIN_FIT_SAMPLES: int = 5    # need >=5 samples on the diastolic segment to fit

AIX_MIN_QUALITY_BEATS: int = 3  # need >=3 beats with an inflection to report AIx
AIX_SECOND_DERIV_FRAC: float = 0.04  # smoothing window for the 2nd derivative
                                     #   (fraction of the upstroke length)

# ---------------------------------------------------------------------------
# BURDEN (cumulative-dose) thresholds (binding; pre-registered constants).
#
# These mirror the accepted "hypotension dose" (minutes / AUC below MAP 65)
# paradigm but for the WAVEFORM-derived abnormal STATE. Each burden is the
# time-integral (in MINUTES) of an abnormal per-beat / per-respiratory-epoch
# waveform state over the intraop window, time-weighted with the same 10 s gap
# cap pfds.py uses (a gap >10 s is a recording break, not abnormal-state time).
#
#   PPV_HIGH_THR  -- windowed PPV above this flags dynamic preload dependence /
#       hypovolemia (fluid-responsiveness). 13% is the canonical Michard / PPV
#       fluid-responsiveness cutpoint (PPV>13% predicts a positive fluid
#       challenge under controlled ventilation). Above it = abnormal "occult
#       hypovolemia" state.
#   PP_LOW_THR    -- pulse pressure below this flags a low stroke-volume state.
#       30 mmHg is a long-standing bedside low-stroke-volume / low-output
#       threshold (a narrow pulse pressure is the classic sign of reduced SV).
#   DPDT_LOW_THR  -- per-beat max upstroke dP/dt below this flags depressed LV
#       contractility. Healthy resting arterial dP/dt_max is ~ 800-1200 mmHg/s;
#       values < ~400 mmHg/s indicate markedly depressed contractility / low
#       cardiac output (a documented low-contractility cut; this is a peripheral
#       arterial dP/dt surrogate, NOT the LV-catheter +dP/dt, so the cut is set
#       conservatively low so only clearly depressed beats are counted).
#   DBP_LOW_THR   -- diastolic BP below this flags inadequate diastolic
#       perfusion pressure. The kidneys (and coronaries) perfuse largely in
#       diastole; DBP < 50 mmHg is a documented low-diastolic-perfusion state.
#
# PERFUSION-FAILURE (headline) gating: minutes where art MAP is ADEQUATE
#   (>= MAP_ADEQUATE_THR = 65, the conventional "safe" pressure) yet >=1
#   waveform-abnormal flag is true (PPV>13% OR PP<30 OR dP/dt low). This is the
#   waveform analogue of hypotension-dose for OCCULT failure at adequate
#   pressure -- "pressure is not perfusion." The AUC variant severity-weights
#   each abnormal minute by how many flags are tripped (1..3) so a beat failing
#   all three contributes 3x the minutes of a beat failing one.
# ---------------------------------------------------------------------------
PPV_HIGH_THR: float = 13.0        # % -- PPV above this = fluid-responsive/hypovolemic
PP_LOW_THR: float = 30.0          # mmHg -- pulse pressure below this = low stroke volume
DPDT_LOW_THR: float = 400.0       # mmHg/s -- dP/dt_max below this = depressed contractility
DBP_LOW_THR: float = 50.0         # mmHg -- diastolic BP below this = poor diastolic perfusion
MAP_ADEQUATE_THR: float = 65.0    # mmHg -- conventional "adequate" MAP (matches pfds.py)

# Gap cap shared with pfds.py: a between-sample/between-beat interval longer than
# this is a recording break, NOT continuous abnormal-state time, so it is capped.
BURDEN_MAX_INTER_SAMPLE_DT_S: float = 10.0

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11).
# All beat-morphology features are "comprehensive" (a raw-waveform refinement on
# top of the Standard MAP summaries).
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability / counts --------------------------------------------
    FeatureSpec("aline_available", "comprehensive", "intraop",
                "1 if a usable SNUADC/ART waveform with physiologic beats was found else 0"),
    FeatureSpec("aline_n_beats", "comprehensive", "intraop",
                "total number of physiologic beats analyzed across all windows"),
    # ---- pressure summaries from the waveform beats ------------------------
    FeatureSpec("art_sbp_mean", "comprehensive", "intraop",
                "mean systolic BP (mmHg) from waveform beats (§7F)"),
    FeatureSpec("art_dbp_mean", "comprehensive", "intraop",
                "mean diastolic BP (mmHg) from waveform beats (§7F)"),
    FeatureSpec("art_map_mean", "comprehensive", "intraop",
                "mean MAP (mmHg) = DBP + PP/3 from waveform beats (§7F)"),
    FeatureSpec("art_pulse_pressure_mean", "comprehensive", "intraop",
                "mean pulse pressure SBP-DBP (mmHg) from beats (§7C/§7F)"),
    FeatureSpec("art_pulse_pressure_sd", "comprehensive", "intraop",
                "SD of pulse pressure across beats (mmHg) -- PP variability (§7C/§7F)"),
    # ---- contractility surrogate (dP/dt max) -------------------------------
    FeatureSpec("art_dpdt_max_mean", "comprehensive", "intraop",
                "mean per-beat max upstroke dP/dt (mmHg/s) -- contractility surrogate (§7F)"),
    FeatureSpec("art_dpdt_max_min", "comprehensive", "intraop",
                "lowest per-window mean dP/dt_max (mmHg/s) -- worst contractility (§7F)"),
    # ---- pulse-pressure variation (dynamic preload / hypovolemia) ----------
    FeatureSpec("art_ppv_mean", "comprehensive", "intraop",
                "mean pulse-pressure variation % over respiratory blocks "
                "(100*(PPmax-PPmin)/PPmean) -- fluid-responsiveness / hypovolemia (§7C/§7F)"),
    # ---- heart rate from beat intervals ------------------------------------
    FeatureSpec("art_hr_mean", "comprehensive", "intraop",
                "mean heart rate (bpm) from arterial beat-to-beat intervals (§7F)"),
    FeatureSpec("art_hr_sd", "comprehensive", "intraop",
                "SD of instantaneous HR (bpm) across beats -- HR variability (§7F)"),
    # ---- systolic ejection shape -------------------------------------------
    FeatureSpec("art_systolic_auc_mean", "comprehensive", "intraop",
                "mean normalized systolic area under the pressure curve per beat (§7F)"),
    # ---- vascular tone: diastolic decay constant tau (= R*C) ----------------
    FeatureSpec("art_tau_decay_mean", "pk", "intraop",
                "mean diastolic decay time constant tau (s) = R*C of the arterial tree, "
                "from a per-beat log-linear fit of P(t)=P0*exp(-t/tau)+Pinf over the "
                "diastolic runoff; arterial-tone / SVR marker (§7C/§7F)"),
    # ---- vascular tone: augmentation index (best-effort, reflected wave) ----
    FeatureSpec("art_aug_index_mean", "pk", "intraop",
                "mean augmentation index AIx=(P_inflection-P_diastole)/"
                "(P_systolic-P_diastole) per beat, inflection from the upstroke "
                "2nd-derivative zero-crossing; APPROXIMATE from raw ART -- weight by "
                "art_aug_index_quality; None if no reliable inflection (§7C/§7F)"),
    FeatureSpec("art_aug_index_quality", "pk", "intraop",
                "fraction of analyzed beats with a usable reflected-wave inflection "
                "point (quality weight for art_aug_index_mean) (§7F)"),
    # ---- BURDEN (cumulative-dose) biomarkers: minutes in an abnormal waveform
    #      STATE over the intraop window, time-weighted with the 10 s gap cap;
    #      the waveform analogue of the hypotension-dose (minutes below MAP 65)
    #      paradigm. None (never 0) when no usable beats / signal. ----
    FeatureSpec("art_ppv_burden_min", "pk", "intraop",
                "minutes of intraop time with windowed PPV > 13% "
                "(fluid-responsive / hypovolemia state), time-weighted, 10 s "
                "gap-capped; cumulative-dose analogue of hypotension-dose (§7C/§7F)"),
    FeatureSpec("art_narrow_pp_burden_min", "pk", "intraop",
                "minutes with per-beat pulse pressure < 30 mmHg (low stroke-volume "
                "state), time-weighted, 10 s gap-capped (§7C/§7F)"),
    FeatureSpec("art_low_dpdt_burden_min", "pk", "intraop",
                "minutes with per-beat dP/dt_max < 400 mmHg/s (depressed "
                "contractility state), time-weighted, 10 s gap-capped (§7F)"),
    FeatureSpec("art_low_dbp_burden_min", "pk", "intraop",
                "minutes with per-beat diastolic BP < 50 mmHg (poor diastolic "
                "perfusion -- kidneys perfuse in diastole), time-weighted, 10 s "
                "gap-capped (§7C/§7F)"),
    FeatureSpec("art_perfusion_failure_burden_min", "pk", "intraop",
                "HEADLINE: minutes where art MAP >= 65 (adequate pressure) AND "
                ">=1 waveform-abnormal flag is true (PPV>13% OR PP<30 OR dP/dt<400); "
                "waveform analogue of hypotension-dose for OCCULT perfusion failure "
                "at adequate pressure -- pressure is not perfusion (§7C/§7F)"),
    FeatureSpec("art_perfusion_failure_burden_auc", "pk", "intraop",
                "severity-weighted perfusion-failure burden: each adequate-pressure "
                "minute weighted by the number of waveform-abnormal flags tripped "
                "(1..3); AUC-style severity*minutes (§7C/§7F)"),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Pure helpers (no I/O; numpy/scipy imported lazily inside).
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) seconds for the intraop window (mirrors §7C).

    Priority: [anestart, opend] -> [opstart, opend] -> (None, opend).
    opend is mandatory (prediction cutoff §11); without it return (None, None).
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


def estimate_fs(times: "Any") -> float:
    """Estimate sampling rate (Hz) from a 1-D array of sample times (seconds).

    Uses the median inter-sample dt to be robust to recording gaps. Falls back to
    the nominal rate if dt cannot be estimated.
    """
    import numpy as np

    t = np.asarray(times, dtype=float)
    if t.size < 2:
        return ART_FS_HZ_NOMINAL
    dt = np.diff(t)
    dt = dt[dt > 0]
    if dt.size == 0:
        return ART_FS_HZ_NOMINAL
    med = float(np.median(dt))
    if med <= 0:
        return ART_FS_HZ_NOMINAL
    return 1.0 / med


def detect_beats(signal: "Any", fs: float) -> "Any":
    """Detect beats on an arterial pressure waveform segment.

    Pure / network-free. `signal` is a 1-D array of pressure samples (mmHg) at a
    uniform rate `fs` (Hz). Returns an (n_beats, 6) float array, one row per
    physiologic beat:
        [sbp, dbp, pp, dpdt_max, beat_interval_s, systolic_auc_norm]
    Empty (shape (0, 6)) if no physiologic beat is found.

    Algorithm (light, deterministic):
      1. scipy.signal.find_peaks for systolic peaks with a refractory `distance`
         = one HR_MAX-bpm cycle, and a minimum prominence to ignore noise ripple.
      2. For each peak, the preceding diastolic trough = min over the search window
         [peak - max_cycle, peak].
      3. SBP = peak value; DBP = trough value; PP = SBP-DBP.
      4. dP/dt_max = max positive first difference * fs on the trough->peak upstroke.
      5. systolic AUC = trapezoid area of (signal - DBP) over trough->peak,
         normalized by PP * (peak_t - trough_t) -> dimensionless shape index in (0,1].
      6. beat interval from consecutive systolic-peak times -> HR gate.
      7. Physiologic gating drops non-physiologic beats.
    """
    import numpy as np
    from scipy.signal import find_peaks

    sig = np.asarray(signal, dtype=float)
    n = sig.size
    if n < int(fs) or fs <= 0:   # need at least ~1 s of data
        return np.empty((0, 6), dtype=float)

    # Refractory distance: peaks cannot be closer than one HR_MAX-bpm cycle.
    min_cycle_samp = max(1, int(round(fs * 60.0 / HR_MAX_BPM)))
    # Max plausible cycle: one HR_MIN-bpm cycle (search window for the trough).
    max_cycle_samp = max(min_cycle_samp + 1, int(round(fs * 60.0 / HR_MIN_BPM)))

    # Prominence: scale to a ROBUST dynamic range (5th-95th percentile) so a single
    # flush/saturation spike does not inflate the threshold and suppress real beats.
    rng = float(np.nanpercentile(sig, 95) - np.nanpercentile(sig, 5)) if n else 0.0
    prominence = max(PP_MIN, 0.2 * rng)

    peaks, _ = find_peaks(sig, distance=min_cycle_samp, prominence=prominence)
    if peaks.size < 2:
        return np.empty((0, 6), dtype=float)

    rows: list[list[float]] = []
    for i, pk in enumerate(peaks):
        # Search window for the preceding diastolic trough.
        lo = max(0, int(pk) - max_cycle_samp)
        if pk <= lo:
            continue
        seg = sig[lo:pk + 1]
        trough_rel = int(np.argmin(seg))
        trough = lo + trough_rel
        if trough >= pk:
            continue

        sbp = float(sig[pk])
        dbp = float(sig[trough])
        pp = sbp - dbp

        # dP/dt_max on the upstroke (mmHg/s).
        upstroke = sig[trough:pk + 1]
        if upstroke.size < 2:
            continue
        diffs = np.diff(upstroke) * fs
        dpdt_max = float(np.max(diffs)) if diffs.size else 0.0

        # Systolic AUC over trough->peak, baseline = DBP, normalized.
        t_up = np.arange(upstroke.size) / fs
        area = float(np.trapezoid(np.clip(upstroke - dbp, 0.0, None), t_up)) \
            if hasattr(np, "trapezoid") else \
            float(np.trapz(np.clip(upstroke - dbp, 0.0, None), t_up))
        dur_up = float(t_up[-1]) if t_up.size else 0.0
        denom = pp * dur_up
        syst_auc = (area / denom) if denom > 0 else float("nan")

        # Beat interval from consecutive peak spacing (for HR).
        if i + 1 < peaks.size:
            interval = float((peaks[i + 1] - pk) / fs)
        elif i > 0:
            interval = float((pk - peaks[i - 1]) / fs)
        else:
            interval = float("nan")

        rows.append([sbp, dbp, pp, dpdt_max, interval, syst_auc])

    if not rows:
        return np.empty((0, 6), dtype=float)
    beats = np.asarray(rows, dtype=float)
    return _gate_beats(beats)


def _gate_beats(beats: "Any") -> "Any":
    """Drop non-physiologic beats from an (n,6) beat array. Pure."""
    import numpy as np

    b = np.asarray(beats, dtype=float)
    if b.size == 0:
        return b.reshape(0, 6)
    sbp, dbp, pp = b[:, 0], b[:, 1], b[:, 2]
    interval = b[:, 4]
    hr = np.where(interval > 0, 60.0 / interval, np.nan)

    keep = (
        (sbp >= SBP_MIN) & (sbp <= SBP_MAX) &
        (dbp >= DBP_MIN) & (dbp <= DBP_MAX) &
        (pp >= PP_MIN) & (pp <= PP_MAX) &
        (sbp > dbp)
    )
    # HR gate only where interval is defined; beats with nan interval keep their
    # other gates (a single isolated beat still yields valid SBP/DBP).
    hr_ok = np.isnan(hr) | ((hr >= HR_MIN_BPM) & (hr <= HR_MAX_BPM))
    keep = keep & hr_ok
    return b[keep]


def ppv_for_block(pulse_pressures: "Any") -> float | None:
    """Pulse-pressure variation % for one respiratory block (Michard).

    PPV = 100 * (PP_max - PP_min) / PP_mean over the beats in the block.
    Returns None if fewer than MIN_BEATS_PER_RESP_BLOCK beats or PP_mean <= 0.
    """
    import numpy as np

    pp = np.asarray(pulse_pressures, dtype=float)
    pp = pp[np.isfinite(pp)]
    if pp.size < MIN_BEATS_PER_RESP_BLOCK:
        return None
    pp_mean = float(np.mean(pp))
    if pp_mean <= 0:
        return None
    return 100.0 * (float(np.max(pp)) - float(np.min(pp))) / pp_mean


# ===========================================================================
# BURDEN cores (pure / stdlib-only; threshold-integrate an abnormal-state series
# into MINUTES, time-weighted with the 10 s gap cap -- mirrors pfds.py's
# minutes/AUC-below-threshold pattern). Unit-tested without numpy.
# ===========================================================================

def _state_burden_minutes(
    series: list[tuple[float, bool]],
    max_dt_s: float = BURDEN_MAX_INTER_SAMPLE_DT_S,
    severity: list[float] | None = None,
) -> float:
    """Time-in-abnormal-state, in MINUTES, from a per-epoch boolean state series.

    `series` is a chronologically ordered list of (t_seconds, is_abnormal) epoch
    markers (one per beat or per respiratory block). Each epoch i "owns" the
    forward interval dt = min(t[i+1] - t[i], max_dt_s); if epoch i is abnormal
    that dt is added to the burden. The 10 s gap cap (mirrors pfds.py) means a
    recording break between two epochs contributes at most max_dt_s, so a gap is
    never counted as continuous abnormal-state time. The last epoch has no
    forward interval and contributes nothing (matches pfds's forward-dt scheme).

    `severity` (optional, same length as series) weights each abnormal interval
    by a per-epoch severity (e.g. number of abnormal flags tripped) -> AUC-style
    severity*minutes. When None, every abnormal epoch has weight 1.0.

    Returns minutes (float). 0.0 when no epoch is ever abnormal. Callers decide
    None-vs-0.0 missingness (no usable beats -> None upstream).
    """
    n = len(series)
    if n < 2:
        return 0.0
    total_s = 0.0
    for i in range(n - 1):
        t_i, abnormal = series[i]
        dt = series[i + 1][0] - t_i
        if dt <= 0:
            continue
        if dt > max_dt_s:
            dt = max_dt_s
        if abnormal:
            w = severity[i] if (severity is not None and i < len(severity)) else 1.0
            total_s += dt * w
    return total_s / 60.0


def burden_from_beat_series(
    beat_series: list[tuple[float, dict[str, float]]],
    ppv_series: list[tuple[float, float]],
    ppv_high_thr: float = PPV_HIGH_THR,
    pp_low_thr: float = PP_LOW_THR,
    dpdt_low_thr: float = DPDT_LOW_THR,
    dbp_low_thr: float = DBP_LOW_THR,
    map_adequate_thr: float = MAP_ADEQUATE_THR,
    max_dt_s: float = BURDEN_MAX_INTER_SAMPLE_DT_S,
) -> dict[str, float | None]:
    """Compute every per-case waveform BURDEN (minutes / AUC) from beat series.

    Pure / stdlib-only.

    Parameters
    ----------
    beat_series : list of (t_seconds, beat_dict)
        Chronologically ordered per-beat records. Each beat_dict carries the
        scalars needed for the per-beat burdens:
            "pp"   -- pulse pressure (mmHg)
            "dbp"  -- diastolic BP (mmHg)
            "map"  -- mean arterial pressure (mmHg) = dbp + pp/3
            "dpdt" -- per-beat max upstroke dP/dt (mmHg/s)
        Missing keys make that beat non-abnormal for the corresponding flag.
    ppv_series : list of (t_seconds, ppv_pct)
        Chronologically ordered per-respiratory-BLOCK PPV values (the PPV state
        lives on a coarser, respiratory-block grid than per-beat, so it gets its
        own burden integration).

    Returns
    -------
    dict with keys:
        art_ppv_burden_min, art_narrow_pp_burden_min, art_low_dpdt_burden_min,
        art_low_dbp_burden_min, art_perfusion_failure_burden_min,
        art_perfusion_failure_burden_auc
    Each is minutes (>= 0.0) when a usable series exists, else None.

    Missingness contract: a burden is None (NOT 0.0) when its underlying series
    has < 2 epochs (cannot integrate any interval) -- "truly missing". A burden
    is 0.0 when the series exists but the abnormal state never occurs.
    """
    out: dict[str, float | None] = {
        "art_ppv_burden_min": None,
        "art_narrow_pp_burden_min": None,
        "art_low_dpdt_burden_min": None,
        "art_low_dbp_burden_min": None,
        "art_perfusion_failure_burden_min": None,
        "art_perfusion_failure_burden_auc": None,
    }

    # ---- PPV burden (respiratory-block grid) ----
    if len(ppv_series) >= 2:
        ppv_state = [(t, (v > ppv_high_thr)) for t, v in ppv_series]
        out["art_ppv_burden_min"] = round(
            _state_burden_minutes(ppv_state, max_dt_s), 4)

    # ---- Per-beat burdens ----
    if len(beat_series) >= 2:
        narrow_pp = []
        low_dpdt = []
        low_dbp = []
        pf_state = []
        pf_severity: list[float] = []
        for t, bd in beat_series:
            pp = bd.get("pp")
            dbp = bd.get("dbp")
            dpdt = bd.get("dpdt")
            mp = bd.get("map")

            narrow_pp.append((t, pp is not None and pp < pp_low_thr))
            low_dpdt.append((t, dpdt is not None and dpdt < dpdt_low_thr))
            low_dbp.append((t, dbp is not None and dbp < dbp_low_thr))

            # Perfusion-failure: adequate MAP AND >=1 waveform-abnormal flag.
            # PPV is a respiratory-block metric, so for the per-beat headline we
            # use the beat-local flags (PP<30 OR dP/dt<400); the windowed-PPV
            # contribution is captured by art_ppv_burden_min. (A beat-aligned PPV
            # is not defined; using PP and dP/dt keeps this strictly per-beat.)
            n_flags = 0
            if pp is not None and pp < pp_low_thr:
                n_flags += 1
            if dpdt is not None and dpdt < dpdt_low_thr:
                n_flags += 1
            adequate = (mp is not None and mp >= map_adequate_thr)
            is_pf = adequate and n_flags >= 1
            pf_state.append((t, is_pf))
            pf_severity.append(float(n_flags) if is_pf else 0.0)

        out["art_narrow_pp_burden_min"] = round(
            _state_burden_minutes(narrow_pp, max_dt_s), 4)
        out["art_low_dpdt_burden_min"] = round(
            _state_burden_minutes(low_dpdt, max_dt_s), 4)
        out["art_low_dbp_burden_min"] = round(
            _state_burden_minutes(low_dbp, max_dt_s), 4)
        out["art_perfusion_failure_burden_min"] = round(
            _state_burden_minutes(pf_state, max_dt_s), 4)
        out["art_perfusion_failure_burden_auc"] = round(
            _state_burden_minutes(pf_state, max_dt_s, severity=pf_severity), 4)

    return out


def tau_decay_for_beat(beat: "Any", fs: float) -> float | None:
    """Diastolic decay time constant tau (seconds) for ONE beat. Pure.

    `beat` is the raw pressure samples for a single cardiac cycle (foot ->
    next foot), at uniform rate `fs`. We locate the systolic peak, start the
    diastolic segment TAU_DIASTOLE_FRAC of the beat AFTER the peak (skipping the
    dicrotic-notch transient), and fit

        P(t) = P0 * exp(-t / tau) + Pinf

    by LOG-LINEAR least squares: with Pinf taken as the end-diastolic pressure
    (the segment minimum), ln(P - Pinf) is linear in t with slope -1/tau.

    Returns tau in seconds, or None if:
      * the diastolic segment is too short (< TAU_MIN_FIT_SAMPLES),
      * the log-linear fit R^2 < TAU_MIN_R2,
      * tau falls outside [TAU_MIN_S, TAU_MAX_S].
    """
    import numpy as np

    b = np.asarray(beat, dtype=float)
    if b.size < TAU_MIN_FIT_SAMPLES + 2 or fs <= 0:
        return None

    pk = int(np.argmax(b))
    n = b.size
    # Start the diastolic fit a fraction of the beat after the systolic peak so
    # the dicrotic notch / incisura transient is excluded.
    start = pk + int(round(TAU_DIASTOLE_FRAC * n))
    if start >= n - TAU_MIN_FIT_SAMPLES:
        # Peak too late in the beat to leave a usable runoff; fall back to just
        # after the peak if that still leaves enough samples.
        start = min(pk + 1, n - TAU_MIN_FIT_SAMPLES - 1)
    if start < 0 or start >= n - TAU_MIN_FIT_SAMPLES:
        return None

    seg = b[start:]
    if seg.size < TAU_MIN_FIT_SAMPLES:
        return None
    # The diastolic runoff must be MONOTONE-ish decreasing; require the segment
    # to actually fall (first > last) so we are not fitting noise on a flat line.
    if seg[0] <= seg[-1]:
        return None

    t = np.arange(seg.size, dtype=float) / fs
    seg_min = float(np.min(seg))
    seg_range = float(seg[0] - seg_min)
    if seg_range <= 0:
        return None

    # The asymptote Pinf is unknown (the true end-diastolic pressure sits BELOW
    # the observed segment minimum). Using min(seg) forces ln(P-Pinf)->-inf at
    # the tail and corrupts the fit, so we grid-search Pinf below the minimum and
    # keep the value that maximises the log-linear R^2 (a standard windkessel
    # decay-fit strategy). ln(P - Pinf) = c - t/tau is linear -> slope = -1/tau.
    A = np.vstack([t, np.ones_like(t)]).T
    best: tuple[float, float] | None = None   # (r2, tau)
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0):
        pinf = seg_min - frac * seg_range - 1e-6
        y = seg - pinf
        if np.any(y <= 0):
            continue
        ly = np.log(y)
        coef, *_ = np.linalg.lstsq(A, ly, rcond=None)
        slope = float(coef[0])
        if slope >= 0:
            continue
        tau = -1.0 / slope
        pred = A @ coef
        ss_res = float(np.sum((ly - pred) ** 2))
        ss_tot = float(np.sum((ly - np.mean(ly)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        if best is None or r2 > best[0]:
            best = (r2, tau)

    if best is None:
        return None
    r2, tau = best
    if r2 < TAU_MIN_R2:
        return None
    if not (TAU_MIN_S <= tau <= TAU_MAX_S):
        return None
    return float(tau)


def aug_index_for_beat(beat: "Any", fs: float) -> float | None:
    """Augmentation index AIx for ONE beat (best-effort). Pure.

    AIx = (P_inflection - P_diastole) / (P_systolic_peak - P_diastole)

    The inflection point (the shoulder where the reflected pressure wave joins
    the forward wave) is detected on the upstroke-to-peak segment as the first
    ZERO-CROSSING of the smoothed 2nd derivative (curvature sign change) before
    the systolic peak. AIx from raw ART is approximate; returns None when no
    reliable inflection is found so the caller can track usable-beat fraction.

    Returns AIx (typically in roughly [-0.5, 1.0]) or None.
    """
    import numpy as np

    b = np.asarray(beat, dtype=float)
    n = b.size
    if n < 7 or fs <= 0:
        return None

    pk = int(np.argmax(b))
    foot = int(np.argmin(b[: pk + 1])) if pk > 0 else 0
    p_sys = float(b[pk])
    p_dia = float(b[foot])
    pp = p_sys - p_dia
    if pp <= 0:
        return None

    # Upstroke segment foot -> peak; need enough points to take a 2nd derivative.
    up = b[foot: pk + 1]
    if up.size < 5:
        return None

    # Smooth (valid-mode, so no convolution edge artifacts manufacture a
    # spurious curvature flip) then take the discrete 2nd derivative.
    win = max(3, int(round(AIX_SECOND_DERIV_FRAC * up.size)))
    if win % 2 == 0:
        win += 1
    if win < up.size:
        kernel = np.ones(win, dtype=float) / win
        ups = np.convolve(up, kernel, mode="valid")  # length up.size-win+1
        smooth_offset = win // 2  # 'valid' trims (win-1)/2 from each end
    else:
        ups = up
        smooth_offset = 0
    if ups.size < 5:
        return None
    d2 = np.diff(ups, n=2)
    if d2.size < 3:
        return None

    # A real reflected-wave shoulder produces curvature far above floating-point
    # noise; a pure single-rise upstroke has d2 ~ 0 (only rounding noise). Require
    # the curvature on at least one side of the candidate to clear a noise floor
    # scaled to the pulse pressure so a straight ramp does not register.
    curv_floor = 1e-3 * pp
    # Inflection = first INTERIOR sign change of the curvature on the upstroke
    # (the systolic shoulder). Skip the first/last sample of d2 so residual edge
    # curvature does not register.
    infl_rel: int | None = None
    for i in range(2, d2.size - 1):
        if d2[i - 1] == 0:
            continue
        if (d2[i - 1] > 0) != (d2[i] > 0):
            if max(abs(d2[i - 1]), abs(d2[i])) < curv_floor:
                continue  # curvature flip is just numerical noise, not a shoulder
            # map d2 index -> index into `up`: +1 for diff(n=2) center, +offset
            # for the 'valid' smoothing trim.
            infl_rel = i + 1 + smooth_offset
            break
    if infl_rel is None:
        return None

    infl_idx = foot + infl_rel + 1
    if infl_idx <= foot or infl_idx >= pk:
        return None  # inflection must sit strictly between foot and peak
    p_infl = float(b[infl_idx])

    aix = (p_infl - p_dia) / pp
    # Sanity bound: a valid inflection pressure sits between diastole and systole.
    if not (-1.0 <= aix <= 1.5):
        return None
    return float(aix)


def vascular_tone_for_window(times: "Any", values: "Any", fs: float
                             ) -> tuple[list[float], int, int]:
    """Per-window tau / AIx extraction. Pure / network-free.

    Re-detects beat boundaries (systolic peaks + preceding feet) on the window
    samples and, for each physiologic beat, slices the raw cycle (foot -> next
    foot) so tau_decay_for_beat / aug_index_for_beat can fit the actual samples
    (the per-beat scalar array does not retain raw samples). Gating mirrors
    detect_beats (SBP/DBP/PP physiologic windows + HR).

    Returns (tau_list, n_aix_beats, n_aix_usable):
      tau_list      : accepted per-beat tau values (s),
      n_aix_beats   : beats where AIx was attempted (denominator for quality),
      n_aix_usable  : beats with a usable inflection (numerator).
    AIx values themselves are accumulated via the returned numerator-style count;
    callers compute the mean over usable beats -- see vascular_tone_features().
    """
    import numpy as np
    from scipy.signal import find_peaks

    t = np.asarray(times, dtype=float)
    v = np.asarray(values, dtype=float)
    if t.size < int(fs) or fs <= 0:
        return [], 0, 0

    min_cycle_samp = max(1, int(round(fs * 60.0 / HR_MAX_BPM)))
    max_cycle_samp = max(min_cycle_samp + 1, int(round(fs * 60.0 / HR_MIN_BPM)))
    rng = float(np.nanpercentile(v, 95) - np.nanpercentile(v, 5)) if v.size else 0.0
    prominence = max(PP_MIN, 0.2 * rng)
    peaks, _ = find_peaks(v, distance=min_cycle_samp, prominence=prominence)
    if peaks.size < 2:
        return [], 0, 0

    tau_list: list[float] = []
    aix_attempt = 0
    aix_usable = 0
    aix_vals: list[float] = []

    for i in range(len(peaks) - 1):
        pk = int(peaks[i])
        nxt = int(peaks[i + 1])
        lo = max(0, pk - max_cycle_samp)
        seg_pre = v[lo:pk + 1]
        if seg_pre.size < 2:
            continue
        foot_rel = int(np.argmin(seg_pre))
        foot = lo + foot_rel
        # Next foot = min between this peak and the next peak (cycle end).
        seg_post = v[pk:nxt + 1]
        if seg_post.size < 2:
            continue
        next_foot = pk + int(np.argmin(seg_post))
        if next_foot <= foot:
            continue

        sbp = float(v[pk])
        dbp = float(v[foot])
        pp = sbp - dbp
        interval = float((nxt - pk) / fs)
        hr = 60.0 / interval if interval > 0 else float("nan")
        # Physiologic gate (mirror _gate_beats).
        if not (SBP_MIN <= sbp <= SBP_MAX and DBP_MIN <= dbp <= DBP_MAX
                and PP_MIN <= pp <= PP_MAX and sbp > dbp):
            continue
        if not (np.isnan(hr) or (HR_MIN_BPM <= hr <= HR_MAX_BPM)):
            continue

        cycle = v[foot:next_foot + 1]
        tau = tau_decay_for_beat(cycle, fs)
        if tau is not None:
            tau_list.append(tau)

        aix_attempt += 1
        aix = aug_index_for_beat(cycle, fs)
        if aix is not None:
            aix_usable += 1
            aix_vals.append(aix)

    # Stash AIx values on the function call via a parallel return: we pack the
    # mean into tau_list-independent accumulators by returning the values list
    # through n_aix_usable's companion. To keep a simple tuple signature, the
    # caller recomputes the AIx mean from the per-window value lists collected
    # in vascular_tone_features(); so we expose aix_vals via an attribute-free
    # contract: return them appended. (See vascular_tone_features.)
    vascular_tone_for_window._last_aix_vals = aix_vals  # type: ignore[attr-defined]
    return tau_list, aix_attempt, aix_usable


def vascular_tone_features(per_window: "list") -> dict[str, Any]:
    """Aggregate per-window vascular-tone results into the feature subset. Pure.

    `per_window` is a list of (tau_list, aix_attempt, aix_usable, aix_vals)
    tuples (one per analysis window). Returns the three feature values:
      art_tau_decay_mean, art_aug_index_mean, art_aug_index_quality.

    Quality gate for AIx: report a mean only when >= AIX_MIN_QUALITY_BEATS beats
    had a usable inflection; otherwise art_aug_index_mean is None (NOT 0).
    art_aug_index_quality is the usable/attempted fraction (None if no attempts).
    """
    all_tau: list[float] = []
    all_aix: list[float] = []
    n_attempt = 0
    n_usable = 0
    for tau_list, aix_attempt, aix_usable, aix_vals in per_window:
        all_tau.extend(tau_list)
        all_aix.extend(aix_vals)
        n_attempt += int(aix_attempt)
        n_usable += int(aix_usable)

    tau_mean = (sum(all_tau) / len(all_tau)) if all_tau else None
    quality = (n_usable / n_attempt) if n_attempt > 0 else None
    if len(all_aix) >= AIX_MIN_QUALITY_BEATS:
        aix_mean = sum(all_aix) / len(all_aix)
    else:
        aix_mean = None

    def _r(v: float | None, nd: int = 4) -> float | None:
        return round(v, nd) if v is not None else None

    return {
        "art_tau_decay_mean": _r(tau_mean),
        "art_aug_index_mean": _r(aix_mean),
        "art_aug_index_quality": _r(quality),
    }


def _window_starts(t_start: float, t_end: float) -> list[float]:
    """Analysis-window start times: one every WINDOW_PERIOD_S, capped."""
    if t_end <= t_start:
        return []
    starts: list[float] = []
    s = t_start
    while s + ANALYSIS_WINDOW_S <= t_end and len(starts) < MAX_ANALYSIS_WINDOWS:
        starts.append(s)
        s += WINDOW_PERIOD_S
    # Always include at least one window if the case is shorter than one period.
    if not starts and (t_end - t_start) >= 1.0:
        starts.append(t_start)
    return starts


def beat_features(beats_by_window: "list", ppv_values: "list") -> dict[str, Any]:
    """Aggregate per-window beat arrays + per-block PPVs into the feature row.

    Pure / network-free.
      beats_by_window: list of (n_i, 6) beat arrays, one per analysis window.
      ppv_values:      list of per-respiratory-block PPV floats (already computed).
    Returns the feature dict (without availability flag, which the caller sets).
    All values None if no beats.
    """
    import numpy as np

    all_beats = [b for b in beats_by_window if b is not None and len(b) > 0]
    if not all_beats:
        return {name: None for name in (
            "art_sbp_mean", "art_dbp_mean", "art_map_mean",
            "art_pulse_pressure_mean", "art_pulse_pressure_sd",
            "art_dpdt_max_mean", "art_dpdt_max_min",
            "art_ppv_mean", "art_hr_mean", "art_hr_sd",
            "art_systolic_auc_mean", "aline_n_beats",
        )}

    stacked = np.vstack(all_beats)
    sbp = stacked[:, 0]
    dbp = stacked[:, 1]
    pp = stacked[:, 2]
    dpdt = stacked[:, 3]
    interval = stacked[:, 4]
    syst_auc = stacked[:, 5]

    n_beats = int(stacked.shape[0])

    sbp_mean = float(np.mean(sbp))
    dbp_mean = float(np.mean(dbp))
    pp_mean = float(np.mean(pp))
    # MAP per beat = DBP + PP/3 (standard arterial MAP estimate), then averaged.
    map_mean = float(np.mean(dbp + pp / 3.0))
    pp_sd = float(np.std(pp)) if n_beats >= 2 else None

    dpdt_mean = float(np.mean(dpdt))
    # Lowest per-window mean dP/dt (worst-contractility window).
    per_window_dpdt = [float(np.mean(b[:, 3])) for b in all_beats if len(b) > 0]
    dpdt_min = float(min(per_window_dpdt)) if per_window_dpdt else None

    hr = 60.0 / interval[interval > 0]
    hr_mean = float(np.mean(hr)) if hr.size else None
    hr_sd = float(np.std(hr)) if hr.size >= 2 else None

    auc_valid = syst_auc[np.isfinite(syst_auc)]
    syst_auc_mean = float(np.mean(auc_valid)) if auc_valid.size else None

    ppv_clean = [p for p in ppv_values if p is not None]
    ppv_mean = float(sum(ppv_clean) / len(ppv_clean)) if ppv_clean else None

    def _r(v: float | None, nd: int = 4) -> float | None:
        return round(v, nd) if v is not None else None

    return {
        "aline_n_beats": n_beats,
        "art_sbp_mean": _r(sbp_mean),
        "art_dbp_mean": _r(dbp_mean),
        "art_map_mean": _r(map_mean),
        "art_pulse_pressure_mean": _r(pp_mean),
        "art_pulse_pressure_sd": _r(pp_sd),
        "art_dpdt_max_mean": _r(dpdt_mean),
        "art_dpdt_max_min": _r(dpdt_min),
        "art_ppv_mean": _r(ppv_mean),
        "art_hr_mean": _r(hr_mean),
        "art_hr_sd": _r(hr_sd),
        "art_systolic_auc_mean": _r(syst_auc_mean, 6),
    }


def _process_window(times: "Any", values: "Any", fs: float
                    ) -> tuple["Any", list[float], "Any", list[tuple[float, float]]]:
    """Detect beats in one analysis window and compute its per-block PPVs.

    times/values are the raw samples within [w_start, w_start+ANALYSIS_WINDOW_S].
    Returns (beat_array, list_of_block_ppvs, abs_beat_times, abs_ppv_series):
      beat_array      -- (n,6) per-beat scalars (as before),
      list_of_block_ppvs -- the per-block PPV floats (as before; for the mean),
      abs_beat_times  -- (n,) ABSOLUTE timestamps (s) for each beat row, for the
                         per-beat BURDEN integration (reconstructed from the
                         window's first sample time + cumulative beat intervals),
      abs_ppv_series  -- list of (abs_t_block_start, ppv_pct) for the windowed-PPV
                         BURDEN integration.
    The raw samples are not retained by the caller after this returns (memory
    discipline for the 500 Hz trace).
    """
    import numpy as np

    t = np.asarray(times, dtype=float)
    v = np.asarray(values, dtype=float)
    empty_beats = np.empty((0, 6), dtype=float)
    if t.size < 2:
        return empty_beats, [], np.empty(0, dtype=float), []

    # Sample-level artefact gate (flush / zeroing): drop out-of-range, then require
    # the segment to remain mostly contiguous (split on big gaps handled upstream).
    good = (v >= ART_SAMPLE_MIN) & (v <= ART_SAMPLE_MAX) & np.isfinite(v)
    if not good.any():
        return empty_beats, [], np.empty(0, dtype=float), []
    t, v = t[good], v[good]
    if t.size < int(fs):
        return empty_beats, [], np.empty(0, dtype=float), []

    beats = detect_beats(v, fs)
    if len(beats) == 0:
        return beats, [], np.empty(0, dtype=float), []

    # Per-respiratory-block PPV: split the window into RESP_BLOCK_S blocks by the
    # systolic-peak times. We approximate beat times by cumulative beat intervals
    # from the window start; intervals are in column 4. Beats lacking an interval
    # (last beat) are still assigned to the final block.
    intervals = beats[:, 4]
    # Reconstruct approximate beat timestamps within the window.
    safe_int = np.where(np.isfinite(intervals) & (intervals > 0), intervals,
                        np.nanmedian(intervals[np.isfinite(intervals)]) if np.isfinite(intervals).any() else 0.8)
    beat_times = np.concatenate([[0.0], np.cumsum(safe_int)[:-1]])
    pps = beats[:, 2]

    # Absolute beat timestamps for the per-beat burden integration: anchor the
    # within-window cumulative beat times to the window's first sample time.
    w0 = float(t[0]) if t.size else 0.0
    abs_beat_times = beat_times + w0

    ppvs: list[float] = []
    abs_ppv_series: list[tuple[float, float]] = []
    win_len = float(t[-1] - t[0]) if t.size else ANALYSIS_WINDOW_S
    n_blocks = max(1, int(np.ceil(win_len / RESP_BLOCK_S)))
    for bi in range(n_blocks):
        lo = bi * RESP_BLOCK_S
        hi = lo + RESP_BLOCK_S
        sel = (beat_times >= lo) & (beat_times < hi)
        block_pp = pps[sel]
        ppv = ppv_for_block(block_pp)
        if ppv is not None:
            ppvs.append(ppv)
            abs_ppv_series.append((w0 + lo, ppv))
    return beats, ppvs, abs_beat_times, abs_ppv_series


def extract_case_from_track(raw: list[tuple[float, float]],
                            t_start: float | None,
                            t_end: float | None) -> dict[str, Any]:
    """Compute the full feature row from a raw ART track for one case.

    Pure / network-free (takes the already-downloaded [(t, v), ...]). Applies the
    intraop-window clip (NEVER reads t > opend), carves analysis windows, detects
    beats window by window, and aggregates. Returns the feature dict including
    `aline_available`. Used by extract(); also directly unit-testable.
    """
    import numpy as np

    if not raw:
        none_row = {s.name: None for s in SPECS}
        none_row["aline_available"] = 0
        return none_row
    arr = np.asarray(raw, dtype=float)
    return _extract_from_array(arr, t_start, t_end)


def _extract_from_array(arr: "Any",
                        t_start: float | None,
                        t_end: float | None) -> dict[str, Any]:
    """Core windowed beat-morphology extraction over an (N,2) [t,v] array."""
    import numpy as np

    none_row: dict[str, Any] = {s.name: None for s in SPECS}

    if arr is None or len(arr) < 2:
        row = dict(none_row)
        row["aline_available"] = 0
        return row

    t_all = arr[:, 0]
    v_all = arr[:, 1]

    # Intraop-window clip (§11: never t > opend).
    mask = np.ones(t_all.shape, dtype=bool)
    if t_start is not None:
        mask &= t_all >= t_start
    if t_end is not None:
        mask &= t_all <= t_end
    t_all = t_all[mask]
    v_all = v_all[mask]
    if t_all.size < 2:
        row = dict(none_row)
        row["aline_available"] = 0
        return row

    fs = estimate_fs(t_all)
    w0 = float(t_all[0])
    w_end = float(t_all[-1])
    starts = _window_starts(w0, w_end)

    beats_by_window: list[Any] = []
    ppv_values: list[float] = []
    vtone_by_window: list[tuple[list[float], int, int, list[float]]] = []
    # Accumulators for the BURDEN integration: a per-case chronologically ordered
    # per-beat record series and a per-respiratory-block PPV series, both with
    # ABSOLUTE timestamps so time-in-abnormal-state is integrated across the case.
    beat_series: list[tuple[float, dict[str, float]]] = []
    ppv_series: list[tuple[float, float]] = []
    for ws in starts:
        we = ws + ANALYSIS_WINDOW_S
        # Slice this window's samples (and drop them after processing).
        sel = (t_all >= ws) & (t_all < we)
        if not sel.any():
            continue
        wt = t_all[sel]
        wv = v_all[sel]
        beats, ppvs, abs_beat_times, abs_ppv_series = _process_window(wt, wv, fs)
        if len(beats) > 0:
            beats_by_window.append(beats)
            ppv_values.extend(ppvs)
            ppv_series.extend(abs_ppv_series)
            # Per-beat burden records (absolute t + the scalars each burden needs).
            for bi in range(len(beats)):
                sbp_b = float(beats[bi, 0])
                dbp_b = float(beats[bi, 1])
                pp_b = float(beats[bi, 2])
                dpdt_b = float(beats[bi, 3])
                map_b = dbp_b + pp_b / 3.0
                beat_series.append((float(abs_beat_times[bi]), {
                    "sbp": sbp_b, "dbp": dbp_b, "pp": pp_b,
                    "dpdt": dpdt_b, "map": map_b,
                }))
            # Vascular-tone (tau / AIx) needs the raw cycle samples, so it
            # re-walks the same window's waveform before wt/wv are discarded.
            tau_list, aix_attempt, aix_usable = vascular_tone_for_window(wt, wv, fs)
            aix_vals = getattr(vascular_tone_for_window, "_last_aix_vals", [])
            vtone_by_window.append((tau_list, aix_attempt, aix_usable, list(aix_vals)))
        del wt, wv  # memory discipline

    feats = beat_features(beats_by_window, ppv_values)
    aline_available = 1 if (feats.get("aline_n_beats") or 0) > 0 else 0

    # BURDEN integration: keep the per-case series chronologically ordered (windows
    # are already in time order, but sort defensively) and integrate minutes-in-
    # abnormal-state with the 10 s gap cap.
    beat_series.sort(key=lambda r: r[0])
    ppv_series.sort(key=lambda r: r[0])
    burden = burden_from_beat_series(beat_series, ppv_series)

    row = dict(none_row)
    row.update(feats)
    row.update(vascular_tone_features(vtone_by_window))
    row.update(burden)
    row["aline_available"] = aline_available
    if aline_available == 0:
        # No physiologic beats anywhere: honest None for all morphology features,
        # n_beats = 0, available = 0.
        row = dict(none_row)
        row["aline_available"] = 0
        row["aline_n_beats"] = 0
    return row


# ===========================================================================
# Raw-waveform loader (handles VitalDB's PACKED 500 Hz format).
# ===========================================================================
#
# VitalDB serves a continuous waveform like SNUADC/ART as a two-column CSV
# (Time, value) where the TIME column is *sparse*: only the first and last rows
# (and occasional segment anchors) carry a timestamp; every intermediate row is
# ",<value>" -- an implicit uniform 500 Hz grid. The shared download_track()
# parser keeps only rows where BOTH columns parse, so it discards the entire
# waveform and yields ~0 samples. We therefore read the cached CSV ourselves and
# reconstruct the time grid: with anchors (t0 at row0, t_last at the final valued
# row) and N value rows, sample i sits at t0 + i*(t_last-t0)/(N-1). This touches
# no shared infrastructure (download_track caches the file; we re-read it).

def load_art_waveform(cfg: dict[str, Any], caseid: str,
                      tnames: list[str] = ART_TRACK_CANDIDATES):
    """Return (times, values) numpy arrays for the raw arterial waveform.

    Reconstructs the uniform time grid from sparse VitalDB packed CSVs. Falls back
    to the dense (t,v) representation when timestamps are per-row. Returns
    (None, None) if no track / no numeric samples. Caches via download_track
    (which fetches the file) but parses the file directly for the packed case.
    """
    import csv as _csv
    import os as _os

    import numpy as np

    from vitaldb_aki.data import tracks as _T

    tid = None
    chosen = None
    for tn in tnames:
        tid = _T.tid_for(cfg, caseid, tn)
        if tid:
            chosen = tn
            break
    if not tid:
        return None, None

    # Ensure the file is fetched + cached (download_track writes it; we ignore its
    # parsed return because it drops the packed waveform).
    _T.download_track(cfg, caseid, chosen)
    path = _os.path.join(cfg["data"]["cache_dir"], "tracks", f"{tid}.csv")
    if not _os.path.exists(path):
        return None, None

    times: list[float] = []   # (row_index, timestamp) anchors
    anchor_idx: list[int] = []
    anchor_t: list[float] = []
    vals: list[float] = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = _csv.reader(fh)
        next(reader, None)  # header
        i = 0
        for rowi in reader:
            if not rowi:
                continue
            tcell = rowi[0].strip() if len(rowi) >= 1 else ""
            vcell = rowi[1].strip() if len(rowi) >= 2 else ""
            # Record a timestamp anchor at this row position.
            if tcell != "":
                try:                           # validate BEFORE appending so the two
                    tv = float(tcell)          # anchor lists never diverge in length
                except ValueError:             # (a non-numeric Time cell would break
                    tv = None                  # np.interp otherwise).
                if tv is not None:
                    anchor_idx.append(i)
                    anchor_t.append(tv)
            # Value (may be blank during sensor warmup).
            if vcell != "":
                try:
                    vals.append(float(vcell))
                except ValueError:
                    vals.append(float("nan"))
            else:
                vals.append(float("nan"))
            i += 1

    if not vals or len(anchor_t) < 1:
        return None, None

    v = np.asarray(vals, dtype=float)
    n = v.size

    # Build the time grid from anchors. With >=2 anchors, linearly interpolate the
    # row->time map (handles the common 2-anchor [start,end] packed case exactly).
    if len(anchor_t) >= 2:
        t = np.interp(np.arange(n, dtype=float),
                      np.asarray(anchor_idx, dtype=float),
                      np.asarray(anchor_t, dtype=float))
    else:
        # Single anchor (start time only): assume nominal fs.
        t0 = anchor_t[0]
        t = t0 + np.arange(n, dtype=float) / ART_FS_HZ_NOMINAL

    # Drop warmup/blank values now (keep aligned timestamps).
    good = np.isfinite(v)
    if not good.any():
        return None, None
    return t[good], v[good]


def extract_case_from_arrays(times: "Any", values: "Any",
                             t_start: float | None,
                             t_end: float | None) -> dict[str, Any]:
    """Same as extract_case_from_track but takes pre-built numpy arrays.

    Avoids materializing a list of 5.7M (t,v) tuples for the real 500 Hz trace.
    """
    import numpy as np

    if times is None or values is None or len(times) < 2:
        none_row = {s.name: None for s in SPECS}
        none_row["aline_available"] = 0
        return none_row
    raw = np.column_stack([np.asarray(times, dtype=float),
                           np.asarray(values, dtype=float)])
    return _extract_from_array(raw, t_start, t_end)


# ===========================================================================
# Public extract() -- matches the FeatureSpec contract.
# ===========================================================================

def extract(cfg: dict[str, Any], cases_by_id: dict[str, dict],
            caseids: list[str]) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for arterial-waveform morphology.

    Downloads SNUADC/ART per case (cached under cache/tracks/). The raw waveform
    is read via load_art_waveform() which reconstructs VitalDB's packed 500 Hz time
    grid (the shared download_track parser drops it). Returns aline_available=0 +
    None features when no usable ART waveform is found (honest missingness; never
    fabricated zeros).
    """
    none_row: dict[str, Any] = {s.name: None for s in SPECS}

    out: dict[str, dict[str, Any]] = {}
    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            row = dict(none_row)
            row["aline_available"] = 0
            out[cid_str] = row
            continue

        t_start, t_end = _intraop_window(case)

        times, values = load_art_waveform(cfg, cid_str, ART_TRACK_CANDIDATES)
        if times is None or len(times) < 2:
            row = dict(none_row)
            row["aline_available"] = 0
            out[cid_str] = row
            continue

        out[cid_str] = extract_case_from_arrays(times, values, t_start, t_end)

    return out


# ---------------------------------------------------------------------------
# Real-data validation (run once; NOT part of unit tests). See test file's
# main-guard scratch validator and the report. Run:
#   python -m vitaldb_aki.features.aline_morphology
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import csv
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from common.config import load_yaml
    from vitaldb_aki.data.client import fetch_cases
    from vitaldb_aki.data.tracks import available_tracks

    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    cfg = load_yaml(cfg_path)

    cohort_path = os.path.join(cfg["data"]["cache_dir"], "cohort.csv")
    candidate_ids: list[str] = []
    with open(cohort_path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            candidate_ids.append(str(row["caseid"]))

    # Find up to 8 cases that actually have SNUADC/ART.
    chosen: list[str] = []
    for cid in candidate_ids:
        if "SNUADC/ART" in available_tracks(cfg, cid):
            chosen.append(cid)
        if len(chosen) >= 8:
            break

    print(f"Validating on {len(chosen)} A-line cases: {chosen}")
    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, chosen)
    for cid in chosen:
        r = result.get(cid, {})
        print(
            f"  case {cid:>5s}: avail={r.get('aline_available')} "
            f"n_beats={r.get('aline_n_beats')} "
            f"SBP={r.get('art_sbp_mean')} DBP={r.get('art_dbp_mean')} "
            f"MAP={r.get('art_map_mean')} PP={r.get('art_pulse_pressure_mean')} "
            f"HR={r.get('art_hr_mean')} PPV={r.get('art_ppv_mean')} "
            f"dPdt={r.get('art_dpdt_max_mean')}"
        )
