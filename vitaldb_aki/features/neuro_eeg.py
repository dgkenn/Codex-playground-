"""neuro_eeg.py -- Intraoperative EEG / Anesthetic-Depth Biomarker family.

THE HIGHEST-NOVELTY AXIS OF THE VITALDB-AKI STUDY. The processed-EEG
(BIS-monitor) channel is **currently unmined** in this codebase: no existing
module touches the BIS tracks. ~5871 VitalDB cases carry a BIS monitor, and the
processed-EEG signals it logs (suppression ratio, BIS index, spectral edge
frequency, total power, EMG, signal quality) are a direct window onto the
patient's brain/CNS state under anesthesia.

NORTH-STAR THESIS
-----------------
**Burst suppression and EEG instability mark a fragile brain.** Intraoperative
EEG suppression (high SR, deep hypnosis, BIS<40) and an unstable cortical signal
have established associations with postoperative delirium and mortality; the
study HYPOTHESIS extends this: a brain that is electrically fragile under
anesthesia flags a patient whose ORGAN SYSTEMS are systemically vulnerable
(reduced physiologic reserve), and so should associate with AKI and the
composite organ-injury outcome. This module operationalises that axis with
time-weighted suppression/depth/instability biomarkers computable from the
numeric BIS tracks alone.

TRACKS (BIS monitor; all NUMERIC, ~1-5 s cadence)
-------------------------------------------------
  SR      "BIS/SR"      suppression ratio, 0-100 %   (gate 0..100)
  BIS     "BIS/BIS"     bispectral index, 0-100      (gate 0..100)
  SEF     "BIS/SEF"     spectral edge frequency, Hz  (gate 0..30)
  TOTPOW  "BIS/TOTPOW"  total power, dB              (read but not yet a feature)
  EMG     "BIS/EMG"     EMG band power               (read but not yet a feature)
  SQI     "BIS/SQI"     signal quality, 0-100 %      (gate: drop SQI<50 if present)

The 500 Hz RAW EEG ("BIS/EEG1_WAV"/"BIS/EEG2_WAV") is NEVER downloaded on the
default path (see the embedding hook below).

BIOMARKERS (all fset="comprehensive" unless noted; None if input absent)
------------------------------------------------------------------------
  neuro_available            1 if SR or BIS usable, else 0
  neuro_burst_supp_frac      fraction of intraop time with SR>0 (ANY suppression)
  neuro_burst_supp_burden    time-weighted mean SR (overall suppression dose)
  neuro_deep_supp_frac       fraction of time with SR>=10 (substantial suppression)
  neuro_bis_below40_frac     fraction of time with BIS<40 (excessively deep hypnosis)
  neuro_bis_mean             time-weighted mean BIS
  neuro_bis_variability      SD of BIS (anesthetic instability)
  neuro_sef_mean             time-weighted mean SEF
  neuro_sef_sd               SD of SEF
  neuro_eeg_embed_available  (fset="pk") placeholder flag for a learned raw-EEG
                             embedding; 0 by default (see hook).

LEAKAGE (Sec 11)
----------------
All features are timing="intraop". The prediction cutoff is opend; no sample at
t > opend is ever used. `_intraop_window` is copied verbatim from pfds.py and
`audit_specs(SPECS)` enforces the firewall at import.

MISSINGNESS
-----------
If neither SR nor BIS is present (or neither survives gating to >=2 samples),
neuro_available=0 and ALL other features are None (NOT 0). Individual features
are None when their specific track is absent (e.g. neuro_sef_mean is None when
SEF is missing even if BIS is present).

RAW-EEG EMBEDDING HOOK (the bridge to the parent EEG foundation model)
----------------------------------------------------------------------
`neuro_eeg_embed_available` (fset="pk") is the placeholder for a learned raw-EEG
embedding. The intent: download "BIS/EEG1_WAV" (500 Hz raw cortical EEG) and
pass it through an external EEG foundation-model encoder -- the parent project's
**MORGOTH 1.0** (HEEDB-pretrained clinical-EEG model) or its validated
operational stand-in **CBraMod** -- to obtain a per-case neuro embedding vector.
That embedding is the literal data bridge between this VitalDB-AKI study and the
HEEDB phenotype-discovery study.

This is DELIBERATELY a NotImplemented stub. The raw 500 Hz EEG is enormous and
its download would dominate extraction wall-time, so it is OFF by default. Only
when cfg["features"]["neuro_eeg_embedding"] is True AND the raw track exists for
a case does `_eeg_embedding_stub` get invoked; it returns (None, 1) -- a None
embedding (encoder not wired up) with the availability flag set to 1 to mark
that raw EEG was present and an embedding COULD be computed. On the default path
the flag stays 0 and no raw EEG is fetched, keeping the module fast.

Protocol reference: §7-novel (neuro axis), docs/MORGOTH_INTEGRATION.md.
"""
from __future__ import annotations

from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range constants (binding; artifact gates)
# ---------------------------------------------------------------------------
SR_MIN: float = 0.0      # % -- suppression ratio floor
SR_MAX: float = 100.0    # % -- suppression ratio ceiling
BIS_MIN: float = 0.0     # index -- BIS floor
BIS_MAX: float = 100.0   # index -- BIS ceiling
SEF_MIN: float = 0.0     # Hz -- spectral edge frequency floor
SEF_MAX: float = 30.0    # Hz -- spectral edge frequency ceiling

# ---------------------------------------------------------------------------
# Threshold / parameter constants (pre-registered)
# ---------------------------------------------------------------------------
SR_ANY_THR: float = 0.0      # SR > this => ANY suppression (burst suppression)
DEEP_SUPP_THR: float = 10.0  # SR >= this => substantial ("deep") suppression
BIS_DEEP_THR: float = 40.0   # BIS < this => excessively deep hypnosis
SQI_MIN_THR: float = 50.0    # drop samples with SQI < this (if SQI present)
MAX_INTER_SAMPLE_DT_S: float = 10.0  # s -- gap cap (shared convention)

# ---------------------------------------------------------------------------
# Track names (binding)
# ---------------------------------------------------------------------------
SR_TRACK: str = "BIS/SR"
BIS_TRACK: str = "BIS/BIS"
SEF_TRACK: str = "BIS/SEF"
TOTPOW_TRACK: str = "BIS/TOTPOW"
EMG_TRACK: str = "BIS/EMG"
SQI_TRACK: str = "BIS/SQI"
# Raw 500 Hz EEG -- NEVER downloaded on the default path (see embedding hook).
EEG1_WAV_TRACK: str = "BIS/EEG1_WAV"
EEG2_WAV_TRACK: str = "BIS/EEG2_WAV"

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11)
# First spec is neuro_available, by contract.
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # ---- availability -------------------------------------------------------
    FeatureSpec(
        "neuro_available", "comprehensive", "intraop",
        "1 if a usable processed-EEG track (SR or BIS) is present, else 0",
    ),
    # ---- suppression (burst suppression / suppression dose) -----------------
    FeatureSpec(
        "neuro_burst_supp_frac", "comprehensive", "intraop",
        "Fraction of intraop time with SR>0 -- ANY EEG suppression "
        "(burst-suppression exposure); time-weighted",
    ),
    FeatureSpec(
        "neuro_burst_supp_burden", "comprehensive", "intraop",
        "Time-weighted mean suppression ratio (SR) -- overall suppression dose",
    ),
    FeatureSpec(
        "neuro_deep_supp_frac", "comprehensive", "intraop",
        "Fraction of intraop time with SR>=10 -- substantial (deep) suppression; "
        "time-weighted",
    ),
    # ---- depth (excessively deep hypnosis) ----------------------------------
    FeatureSpec(
        "neuro_bis_below40_frac", "comprehensive", "intraop",
        "Fraction of intraop time with BIS<40 -- excessively deep hypnosis; "
        "time-weighted",
    ),
    FeatureSpec(
        "neuro_bis_mean", "comprehensive", "intraop",
        "Time-weighted mean BIS index (overall hypnotic depth)",
    ),
    # ---- instability --------------------------------------------------------
    FeatureSpec(
        "neuro_bis_variability", "comprehensive", "intraop",
        "Standard deviation of BIS -- anesthetic/cortical instability",
    ),
    FeatureSpec(
        "neuro_sef_mean", "comprehensive", "intraop",
        "Time-weighted mean spectral edge frequency (SEF, Hz)",
    ),
    FeatureSpec(
        "neuro_sef_sd", "comprehensive", "intraop",
        "Standard deviation of SEF -- spectral instability",
    ),
    # ---- raw-EEG embedding placeholder (bridge to MORGOTH/CBraMod) ----------
    FeatureSpec(
        "neuro_eeg_embed_available", "pk", "intraop",
        "Placeholder flag (0 by default) for a learned raw-EEG embedding from "
        "BIS/EEG1_WAV via an external EEG foundation model (MORGOTH/CBraMod); "
        "set to 1 only when the embedding flag + raw track both exist",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Low-level helpers (pure; no I/O; unit-testable on synthetic series)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds.py -- the leakage cutoff is opend.
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


def _time_weighted_mean(
    samples: list[tuple[float, float]],
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Forward-dt time-weighted mean (mirrors pfds._time_weighted_mean)."""
    if len(samples) < 2:
        return None
    tw = tw_v = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        tw += dt
        tw_v += samples[i][1] * dt
    return (tw_v / tw) if tw > 0 else None


def _frac_time_above(
    samples: list[tuple[float, float]],
    thr: float,
    inclusive: bool = False,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Time-weighted fraction of recording with value strictly above `thr`.

    Uses the same forward-dt gap-capped weighting as `_time_weighted_mean`: each
    sample contributes the (capped) interval to the NEXT sample. A sample counts
    toward the "above" total when its value > thr (or >= thr when inclusive).

    Returns None if < 2 samples or total weighted time is 0.
    Returns a value in [0, 1] otherwise.
    """
    if len(samples) < 2:
        return None
    tw = 0.0
    tw_above = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        tw += dt
        v = samples[i][1]
        if (v >= thr) if inclusive else (v > thr):
            tw_above += dt
    if tw <= 0:
        return None
    return round(tw_above / tw, 6)


def _frac_time_below(
    samples: list[tuple[float, float]],
    thr: float,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> float | None:
    """Time-weighted fraction of recording with value strictly below `thr`.

    Mirror of `_frac_time_above` for the deep-hypnosis (BIS<40) feature.
    """
    if len(samples) < 2:
        return None
    tw = 0.0
    tw_below = 0.0
    for i in range(len(samples) - 1):
        dt = min(samples[i + 1][0] - samples[i][0], max_dt_s)
        if dt <= 0:
            continue
        tw += dt
        if samples[i][1] < thr:
            tw_below += dt
    if tw <= 0:
        return None
    return round(tw_below / tw, 6)


def _sd(samples: list[tuple[float, float]]) -> float | None:
    """Sample standard deviation (n-1) of the VALUES in a (t, v) series.

    Unweighted -- a measure of signal dispersion/instability. Returns None if
    fewer than 2 samples.
    """
    vals = [v for _, v in samples]
    n = len(vals)
    if n < 2:
        return None
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    return round(var ** 0.5, 6)


def _sqi_gate(
    samples: list[tuple[float, float]],
    sqi_sorted: list[tuple[float, float]],
    sqi_min: float = SQI_MIN_THR,
    max_dt_s: float = MAX_INTER_SAMPLE_DT_S,
) -> list[tuple[float, float]]:
    """Drop samples whose nearest preceding SQI (last-value hold) is < sqi_min.

    If `sqi_sorted` is empty the series is returned unchanged (no SQI => no
    gating). A sample with no SQI value within max_dt_s lookback is KEPT (we do
    not penalise a sample for missing quality metadata).
    """
    if not sqi_sorted:
        return list(samples)

    def _last_val(sorted_s: list[tuple[float, float]], t: float) -> float | None:
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
        if t - st > max_dt_s:
            return None
        return sv

    out: list[tuple[float, float]] = []
    for t, v in samples:
        q = _last_val(sqi_sorted, t)
        if q is not None and q < sqi_min:
            continue  # poor signal quality -- drop
        out.append((t, v))
    return out


# ===========================================================================
# Raw-EEG embedding hook (the bridge to MORGOTH/CBraMod).  NotImplemented stub.
# ===========================================================================

def _eeg_embedding_stub(
    cfg: dict[str, Any],
    caseid: str,
    t_start: float | None,
    t_end: float | None,
) -> tuple[list[float] | None, int]:
    """Placeholder for a learned raw-EEG embedding (NOT wired up).

    INTENT (documented, deliberately not implemented):
      1. download_track(cfg, caseid, "BIS/EEG1_WAV") -- the 500 Hz raw cortical
         EEG (huge; clipped to [t_start, t_end] for leakage safety).
      2. Pass the windowed waveform to an EXTERNAL EEG foundation-model encoder
         -- the parent project's MORGOTH 1.0 (HEEDB-pretrained) or its validated
         operational stand-in CBraMod -- to obtain a per-case embedding vector.
      3. Return (embedding_vector, 1).

    This is the literal data bridge between the VitalDB-AKI study and the HEEDB
    phenotype-discovery study (see docs/MORGOTH_INTEGRATION.md).

    Until the encoder is wired up this returns (None, 1): a None embedding with
    the availability flag set to 1, signalling that raw EEG was present and an
    embedding COULD be computed. It is only ever called when the cfg flag is set
    AND the raw track exists, so on the default path it never runs and no raw
    EEG is fetched.
    """
    # NotImplemented: the foundation-model encoder is not part of this repo yet.
    # We do NOT download the raw waveform here either -- existence of the track
    # is checked by the caller via the tid index (no heavy fetch).
    return None, 1


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for all neuro-EEG biomarkers.

    Default path downloads only the NUMERIC BIS tracks (SR/BIS/SEF/SQI). The
    500 Hz raw EEG is fetched ONLY behind the cfg["features"]["neuro_eeg_embedding"]
    flag (and even then the embedding itself is a NotImplemented stub).

    Missingness: if neither SR nor BIS survives gating to >=2 samples,
    neuro_available=0 and all other features are None (NOT 0).
    """
    from vitaldb_aki.data.tracks import download_track, first_available, tid_for

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["neuro_available"] = 0
    none_row["neuro_eeg_embed_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)

        # ---- SQI track (gating; numeric, optional) ---------------------------
        raw_sqi = download_track(cfg, cid_str, SQI_TRACK)
        sqi_sorted: list[tuple[float, float]] = []
        if raw_sqi:
            sqi_clipped = _clip_to_window(raw_sqi, t_start, t_end)
            # SQI is itself 0..100; gate to that range as an artifact filter.
            sqi_clipped = _filter_physiologic(sqi_clipped, 0.0, 100.0)
            sqi_sorted = sorted(sqi_clipped, key=lambda x: x[0])

        # ---- SR track (suppression ratio) ------------------------------------
        raw_sr = download_track(cfg, cid_str, SR_TRACK)
        sr_samples: list[tuple[float, float]] = []
        if raw_sr:
            sr_samples = _clip_to_window(raw_sr, t_start, t_end)
            sr_samples = _filter_physiologic(sr_samples, SR_MIN, SR_MAX)
            sr_samples = _sqi_gate(sr_samples, sqi_sorted)

        # ---- BIS index track -------------------------------------------------
        raw_bis = download_track(cfg, cid_str, BIS_TRACK)
        bis_samples: list[tuple[float, float]] = []
        if raw_bis:
            bis_samples = _clip_to_window(raw_bis, t_start, t_end)
            bis_samples = _filter_physiologic(bis_samples, BIS_MIN, BIS_MAX)
            bis_samples = _sqi_gate(bis_samples, sqi_sorted)

        sr_usable = len(sr_samples) >= 2
        bis_usable = len(bis_samples) >= 2

        # ---- Availability gate: need SR or BIS -------------------------------
        if not sr_usable and not bis_usable:
            row = dict(none_row)
            row["neuro_available"] = 0
            row["neuro_eeg_embed_available"] = 0
            out[cid_str] = row
            continue

        row: dict[str, Any] = dict(none_row)
        row["neuro_available"] = 1

        # ---- SEF track (numeric; optional) -----------------------------------
        raw_sef = download_track(cfg, cid_str, SEF_TRACK)
        sef_samples: list[tuple[float, float]] = []
        if raw_sef:
            sef_samples = _clip_to_window(raw_sef, t_start, t_end)
            sef_samples = _filter_physiologic(sef_samples, SEF_MIN, SEF_MAX)
            sef_samples = _sqi_gate(sef_samples, sqi_sorted)

        # ======================================================================
        # Compute biomarkers (each None if its required track absent)
        # ======================================================================

        # ---- Suppression (SR-derived) ---------------------------------------
        if sr_usable:
            row["neuro_burst_supp_frac"] = _frac_time_above(sr_samples, SR_ANY_THR)
            row["neuro_burst_supp_burden"] = _round(_time_weighted_mean(sr_samples))
            row["neuro_deep_supp_frac"] = _frac_time_above(
                sr_samples, DEEP_SUPP_THR, inclusive=True
            )

        # ---- Depth + instability (BIS-derived) ------------------------------
        if bis_usable:
            row["neuro_bis_below40_frac"] = _frac_time_below(bis_samples, BIS_DEEP_THR)
            row["neuro_bis_mean"] = _round(_time_weighted_mean(bis_samples))
            row["neuro_bis_variability"] = _sd(bis_samples)

        # ---- Spectral instability (SEF-derived) -----------------------------
        if len(sef_samples) >= 2:
            row["neuro_sef_mean"] = _round(_time_weighted_mean(sef_samples))
            row["neuro_sef_sd"] = _sd(sef_samples)

        # ---- Raw-EEG embedding hook (OFF by default) ------------------------
        # Only when the opt-in flag is set AND the raw 500 Hz EEG track exists
        # for this case do we engage the (NotImplemented) embedding stub. We
        # check track EXISTENCE via the tid index -- no heavy download here.
        if cfg.get("features", {}).get("neuro_eeg_embedding", False):
            if tid_for(cfg, cid_str, EEG1_WAV_TRACK) is not None:
                _embedding, embed_avail = _eeg_embedding_stub(
                    cfg, cid_str, t_start, t_end
                )
                # _embedding stays None until the encoder is wired up; the flag
                # marks that raw EEG was present and an embedding is computable.
                row["neuro_eeg_embed_available"] = embed_avail
            else:
                row["neuro_eeg_embed_available"] = 0
        else:
            row["neuro_eeg_embed_available"] = 0

        out[cid_str] = row

    return out


def _round(v: float | None, ndigits: int = 6) -> float | None:
    """Round a value, passing None through (for time-weighted means)."""
    return round(v, ndigits) if v is not None else None


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.neuro_eeg
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

    print(f"neuro_eeg validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case neuro-EEG summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")

    n_avail = sum(1 for cid in cohort_ids if result.get(cid, {}).get("neuro_available") == 1)
    print(f"\nneuro_available in {n_avail}/{len(cohort_ids)} sampled cases "
          f"(~5871 of the full VitalDB cohort carry a BIS monitor).")
