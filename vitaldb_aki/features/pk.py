"""pk.py -- Stage 2c: pharmacokinetic / drug-exposure features (Protocol Sec 8).

This is the study's **novel contribution** (Protocol Sec 2 H2, Sec 8): no prior
VitalDB-AKI work models drug exposure pharmacokinetically. It layers onto the
Sec 7 tabular/hemodynamic features and is tested for *incremental* value.

Scope (Sec 8) -- agents with validated models AND renal relevance only:
  * **Propofol** effect-site concentration via the **Eleveld (2018) general-purpose
    model** [1]. We re-integrate the published 3-compartment + effect-site model
    from the pump's logged infusion (Orchestra/PPF20_RATE) in pure Python, and
    emit Ce summaries (peak, time-weighted mean, AUC). We ALSO summarise the
    pump's own logged effect-site track (PPF20_CE, computed by the pump from a
    Schnider/Marsh model) as a cross-check -- the two should be strongly
    positively correlated, which validates our implementation.

    **Bolus vs continuous infusion (Sec 7E/8).** VitalDB has NO bolus tracks: the
    Orchestra `_RATE`/`_VOL` tracks are *continuous infusion only* (`_VOL` is the
    cumulative mL the pump delivered). But the `/cases` table carries the TOTAL
    drug given (`intraop_ppf` mg = bolus + infusion). We therefore decompose
    bolus = max(0, total - infused), where infused = (in-window pump `_VOL`
    delta, mL) x (infusate concentration). The derived induction **bolus** is then
    fed into the Eleveld model as an instantaneous central-compartment input at
    anaesthesia start, which the infusion-rate-only integration previously missed
    (under-estimating early effect-site Ce). The same total-minus-infused logic
    yields phenylephrine and ephedrine bolus exposures (Sec 7E vasopressors).
  * **Remifentanil** via **Minto (1997)**: the Orchestra pump already logs a
    Minto-based effect-site track (RFTN20_CE / RFTN50_CE). We summarise the pump
    Ce directly (peak, mean, AUC). (Documented choice: pump Ce is Sec-8 acceptable
    and avoids re-deriving Minto; the propofol arm carries the from-infusion
    re-integration that exercises the novel modelling.)
  * **Volatiles**: age-adjusted **MAC-hours** integrated from Primus/MAC.
  * **Vasoactive / nephrotoxin exposure** (Sec 7E): dose-time integral
    (area-under-infusion-rate), peak rate, cumulative dose, and exposure duration
    for phenylephrine, norepinephrine, and other present pressors.

Leakage firewall (Sec 11.1/11.2): ALL integration is restricted to the
intraoperative window [anestart|opstart, opend]; no sample at t > opend is ever
used. Every spec here is timing="intraop"; audit_specs() enforces it at import.

Heavy deps stay lazy (none needed -- the ODE integration is pure-Python, matching
the repo convention and avoiding scipy).

References
---------
[1] Eleveld DJ, Colin P, Absalom AR, Struys MMRF. Pharmacokinetic-pharmacodynamic
    model for propofol for broad application in anaesthesia and sedation.
    Br J Anaesth 2018;120(5):942-959. (Reference individual: 35 yr, 70 kg, 170 cm,
    male; V1=6.28, V2=25.5, V3=273 L; CL=1.79, Q2=1.75, Q3=1.11 L/min; ke0=0.146/min.)
    Covariate constants (theta) and the ageing / sigmoid-maturation / Al-Sallami
    fat-free-mass functions are reproduced verbatim in ELEVELD_THETA below.
[2] Minto CF, et al. Influence of age and gender on the pharmacokinetics and
    pharmacodynamics of remifentanil. Anesthesiology 1997;86(1):10-23.
    (Used here via the pump's logged effect-site track.)
"""
from __future__ import annotations

from math import exp
from typing import Any

from vitaldb_aki.data.client import to_float
from vitaldb_aki.features.base import FeatureSpec, audit_specs

# ----------------------------------------------------------------------------
# Feature specs (Sec 8/9). Every PK feature is fset="pk", timing="intraop".
# ----------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    # availability flag --------------------------------------------------------
    FeatureSpec("pk_available", "pk", "intraop", "1 if any propofol/remi infusion present"),
    # propofol -- Eleveld (2018) re-integrated effect-site Ce (NOVEL) ----------
    FeatureSpec("ppf_ce_peak", "pk", "intraop", "Eleveld propofol Ce peak (ug/mL)"),
    FeatureSpec("ppf_ce_mean", "pk", "intraop", "Eleveld propofol Ce time-weighted mean (ug/mL)"),
    FeatureSpec("ppf_ce_auc", "pk", "intraop", "Eleveld propofol Ce AUC (ug/mL.min)"),
    # propofol -- pump's own logged Ce (cross-check / validation) --------------
    FeatureSpec("ppf_ce_peak_pump", "pk", "intraop", "pump-logged propofol Ce peak (ug/mL)"),
    FeatureSpec("ppf_ce_auc_pump", "pk", "intraop", "pump-logged propofol Ce AUC (ug/mL.min)"),
    # propofol -- bolus vs continuous-infusion decomposition (Sec 7E/8) --------
    # total = bolus + infusion; total from /cases (intraop_ppf mg), infusion from
    # the pump VOL track (mL x 20 mg/mL). bolus = max(0, total - infused).
    FeatureSpec("ppf_total_mg", "pk", "intraop", "propofol total dose (mg, intraop_ppf from /cases)"),
    FeatureSpec("ppf_infused_mg", "pk", "intraop", "propofol delivered by continuous infusion (mg, from PPF20_VOL)"),
    FeatureSpec("ppf_bolus_mg", "pk", "intraop", "propofol bolus = max(0, total - infused) (mg)"),
    FeatureSpec("ppf_bolus_frac", "pk", "intraop", "propofol bolus fraction = bolus / total (0..1)"),
    FeatureSpec("ppf_admin_mode", "pk", "intraop", "propofol admin mode: 0=none 1=bolus-only 2=infusion-only 3=both"),
    # phenylephrine -- bolus vs infusion decomposition (Sec 7E) ----------------
    FeatureSpec("phe_total_ug", "pk", "intraop", "phenylephrine total dose (ug, intraop_phe from /cases)"),
    FeatureSpec("phe_infused_ug", "pk", "intraop", "phenylephrine delivered by continuous infusion (ug, from PHEN_VOL)"),
    FeatureSpec("phe_bolus_ug", "pk", "intraop", "phenylephrine bolus = max(0, total - infused) (ug)"),
    FeatureSpec("phe_bolus_frac", "pk", "intraop", "phenylephrine bolus fraction = bolus / total (0..1)"),
    # ephedrine -- no infusion track in VitalDB, so all of intraop_eph is bolus -
    FeatureSpec("eph_bolus_mg", "pk", "intraop", "ephedrine bolus dose (mg, = intraop_eph total; no infusion track)"),
    # remifentanil -- pump (Minto) Ce summaries --------------------------------
    FeatureSpec("rftn_ce_peak", "pk", "intraop", "remifentanil (Minto) Ce peak (ng/mL)"),
    FeatureSpec("rftn_ce_mean", "pk", "intraop", "remifentanil (Minto) Ce time-weighted mean (ng/mL)"),
    FeatureSpec("rftn_ce_auc", "pk", "intraop", "remifentanil (Minto) Ce AUC (ng/mL.min)"),
    # volatiles -- age-adjusted MAC-hours --------------------------------------
    FeatureSpec("mac_hours", "pk", "intraop", "integral of Primus/MAC over intraop time (MAC.h)"),
    # vasoactive / nephrotoxin exposure integrals (Sec 7E) ---------------------
    FeatureSpec("phe_auc_dose", "pk", "intraop", "phenylephrine area-under-rate (ug.min)"),
    FeatureSpec("phe_peak_rate", "pk", "intraop", "phenylephrine peak infusion rate (ug/min)"),
    FeatureSpec("phe_cum_dose", "pk", "intraop", "phenylephrine cumulative dose (ug, from VOL)"),
    FeatureSpec("phe_dur_min", "pk", "intraop", "phenylephrine exposure duration (min, rate>0)"),
    FeatureSpec("nepi_auc_dose", "pk", "intraop", "norepinephrine area-under-rate (ug.min)"),
    FeatureSpec("nepi_peak_rate", "pk", "intraop", "norepinephrine peak infusion rate (ug/min)"),
    FeatureSpec("nepi_cum_dose", "pk", "intraop", "norepinephrine cumulative dose (ug, from VOL)"),
    FeatureSpec("nepi_dur_min", "pk", "intraop", "norepinephrine exposure duration (min, rate>0)"),
    FeatureSpec("epi_auc_dose", "pk", "intraop", "epinephrine area-under-rate (ug.min)"),
    FeatureSpec("epi_peak_rate", "pk", "intraop", "epinephrine peak infusion rate (ug/min)"),
    FeatureSpec("epi_cum_dose", "pk", "intraop", "epinephrine cumulative dose (ug, from VOL)"),
    FeatureSpec("epi_dur_min", "pk", "intraop", "epinephrine exposure duration (min, rate>0)"),
    FeatureSpec("dopa_auc_dose", "pk", "intraop", "dopamine area-under-rate (mg.min)"),
    FeatureSpec("dopa_peak_rate", "pk", "intraop", "dopamine peak infusion rate (mg/min)"),
    FeatureSpec("dopa_cum_dose", "pk", "intraop", "dopamine cumulative dose (mg, from VOL)"),
    FeatureSpec("dopa_dur_min", "pk", "intraop", "dopamine exposure duration (min, rate>0)"),
    FeatureSpec("vaso_auc_dose", "pk", "intraop", "vasopressin area-under-rate (units.min)"),
    FeatureSpec("vaso_peak_rate", "pk", "intraop", "vasopressin peak infusion rate (units/min)"),
    FeatureSpec("vaso_cum_dose", "pk", "intraop", "vasopressin cumulative dose (units, from VOL)"),
    FeatureSpec("vaso_dur_min", "pk", "intraop", "vasopressin exposure duration (min, rate>0)"),
]
audit_specs(SPECS)  # fail at import if any PK feature is timed after the cutoff


# ============================================================================
# Eleveld (2018) propofol PK + effect-site model -- pure Python.
#
# Constants reproduced verbatim from Eleveld et al., Br J Anaesth 2018;120:942-959
# (theta table + supplementary equations). Cross-checked against the open-source
# PyTCI reference implementation. Reference individual: 35 yr / 70 kg / 170 cm male.
# ============================================================================
ELEVELD_THETA = {
    1: 6.28,      # V1 (L) reference
    2: 25.5,      # V2 (L) reference
    3: 273.0,     # V3 (L) reference
    4: 1.79,      # CL (L/min) reference, male
    5: 1.75,      # Q2 (L/min) reference
    6: 1.11,      # Q3 (L/min) reference
    7: 0.191,     # (PD; unused for PK)
    8: 42.3,      # CL maturation E50 (weeks PMA)
    9: 9.06,      # CL maturation Hill
    10: -0.0156,  # V2 ageing exponent
    11: -0.00286, # CL opiate exponent (with_opiates only)
    12: 33.6,     # V1 central-volume sigmoid E50 (kg)
    13: -0.0138,  # V3 opiate exponent (with_opiates only)
    14: 68.3,     # Q3 maturation E50 (weeks PMA)
    15: 2.10,     # CL (L/min) reference, female
    16: 1.30,     # Q2 ageing/maturation coefficient
    17: 1.42,     # (venous; unused)
    18: 0.68,     # (venous; unused)
}


def _sigmoid(x: float, e50: float, gamma: float) -> float:
    """Hill sigmoid from the Eleveld paper: x^g / (x^g + e50^g)."""
    xg = x ** gamma
    return xg / (xg + e50 ** gamma)


def _ageing(coef: float, age_yr: float) -> float:
    """Eleveld ageing function: exp(coef * (age - 35))."""
    return exp(coef * (age_yr - 35.0))


def _janmahasatian_ffm(height_cm: float, weight_kg: float, sex_male: bool) -> float:
    """Janmahasatian/Han (2005) fat-free mass (kg) -- base of Al-Sallami."""
    bmi = weight_kg / ((height_cm / 100.0) ** 2)
    if sex_male:
        return (9270.0 * weight_kg) / (6680.0 + 216.0 * bmi)
    return (9270.0 * weight_kg) / (8780.0 + 244.0 * bmi)


def _alsallami_ffm(age_yr: float, height_cm: float, weight_kg: float, sex_male: bool) -> float:
    """Al-Sallami fat-free mass (kg), as used by Eleveld for V3/Q3 scaling."""
    jm = _janmahasatian_ffm(height_cm, weight_kg, sex_male)
    if sex_male:
        return (0.88 + (0.12 / (1.0 + (age_yr / 13.4) ** -12.7))) * jm
    return (1.11 + ((1.0 - 1.11) / (1.0 + (age_yr / 7.1) ** -1.1))) * jm


def eleveld_params(age_yr: float, weight_kg: float, height_cm: float,
                   sex_male: bool) -> dict[str, float]:
    """Return the Eleveld (2018) per-patient PK parameters (V in L, CL/Q in L/min,
    ke0 in 1/min) for the given covariates. Pure function -- no I/O.

    Implements the published covariate model: V1 via a central-volume sigmoid on
    weight, V2 via weight + ageing, V3 via Al-Sallami fat-free mass; CL via an
    allometric weight^0.75 term scaled by a post-menstrual-age clearance
    maturation sigmoid (sex-specific reference); Q2/Q3 via allometric scaling of
    their volumes and a Q3 maturation sigmoid; ke0 allometric on weight.
    """
    t = ELEVELD_THETA
    pma = age_yr * 52.0 + 40.0          # post-menstrual age in weeks
    pma_ref = 35.0 * 52.0 + 40.0

    clmat = _sigmoid(pma, t[8], t[9])
    clmat_ref = _sigmoid(pma_ref, t[8], t[9])
    q3mat = _sigmoid(pma, t[14], 1.0)
    q3mat_ref = _sigmoid(pma_ref, t[14], 1.0)

    ffm = _alsallami_ffm(age_yr, height_cm, weight_kg, sex_male)
    ffm_ref = _alsallami_ffm(35.0, 170.0, 70.0, True)

    v1 = t[1] * (_sigmoid(weight_kg, t[12], 1.0) / _sigmoid(70.0, t[12], 1.0))
    v2 = t[2] * (weight_kg / 70.0) * _ageing(t[10], age_yr)
    v3 = t[3] * (ffm / ffm_ref)
    v2_ref, v3_ref = t[2], t[3]

    cl_ref = t[4] if sex_male else t[15]
    cl = cl_ref * (weight_kg / 70.0) ** 0.75 * (clmat / clmat_ref)
    q2 = t[5] * (v2 / v2_ref) ** 0.75 * (1.0 + t[16] * (1.0 - q3mat / q3mat_ref))
    q3 = t[6] * (v3 / v3_ref) ** 0.75 * (q3mat / q3mat_ref)

    ke0 = 0.146 * ((weight_kg / 70.0) ** -0.25)
    return {"v1": v1, "v2": v2, "v3": v3, "cl": cl, "q2": q2, "q3": q3, "ke0": ke0}


def eleveld_ce(infusion_mg_s: list[float], times: list[float],
               age: float, weight: float, height: float, sex_male: bool,
               bolus_mg: float = 0.0, bolus_index: int = 0) -> list[float]:
    """Integrate the Eleveld 3-compartment + effect-site model and return Ce(t).

    Pure function (unit-testable, no network). Fixed-step explicit Euler at 1 s,
    matching the published/reference TCI integration (rate constants in 1/s).

    Parameters
    ----------
    infusion_mg_s : drug delivered into the central compartment, in **mg/second**,
        for each 1-second step. len == len(times) - 1 (rate over [t_i, t_{i+1}))
        OR len == len(times) (last value ignored). Must be a 1 Hz grid.
    times : monotonic seconds grid (informational; integration assumes 1 s steps).
    age, weight, height : years, kg, cm.
    sex_male : True for male.
    bolus_mg : an **instantaneous** dose (mg) injected into the central compartment
        at step `bolus_index` (default the first step == induction). VitalDB has no
        bolus track, so the induction bolus is derived as total - infused (Sec 7E/8)
        and supplied here; the infusion-rate-only path previously missed it and
        under-estimated early effect-site Ce. Added on top of that second's
        infusion. <= 0 is a no-op (preserves the legacy infusion-only behaviour).
    bolus_index : grid step at which the bolus enters (clamped to [0, n-1]).

    Returns
    -------
    Ce(t) in ug/mL ( == mg/L, since amounts are mg and volumes L) at each grid point.
    """
    p = eleveld_params(age, weight, height, sex_male)
    v1, v2, v3 = p["v1"], p["v2"], p["v3"]
    # intercompartment clearances -> rate constants (1/min), then -> 1/s.
    k10 = (p["cl"] / v1) / 60.0
    k12 = (p["q2"] / v1) / 60.0
    k13 = (p["q3"] / v1) / 60.0
    k21 = (p["q2"] / v2) / 60.0
    k31 = (p["q3"] / v3) / 60.0
    keo = p["ke0"] / 60.0

    n = len(infusion_mg_s)
    # locate the instantaneous bolus step (clamped into the integration grid).
    bi = bolus_index
    if bi < 0:
        bi = 0
    if n > 0 and bi > n - 1:
        bi = n - 1
    x1 = x2 = x3 = xeo = 0.0  # x1..x3 are concentrations (mg/L); xeo effect-site
    ce = [0.0] * (n + 1)
    ce[0] = xeo
    for i in range(n):
        # add this second's infusion to the central compartment (mg -> conc)
        x1 += infusion_mg_s[i] / v1
        # add the induction bolus as an instantaneous central-compartment input.
        if bolus_mg > 0.0 and i == bi:
            x1 += bolus_mg / v1
        # explicit-Euler 1-second transfer (concentration form)
        d1 = x2 * k21 - x1 * k12 + x3 * k31 - x1 * k13 - x1 * k10
        d2 = x1 * k12 - x2 * k21
        d3 = x1 * k13 - x3 * k31
        de = (x1 - xeo) * keo
        x1 += d1
        x2 += d2
        x3 += d3
        xeo += de
        ce[i + 1] = xeo
    return ce


# ============================================================================
# Time-series helpers (all leakage-bounded to [t0, t1] = intraop window).
# ============================================================================
def _window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Intraop window [start, opend]: start = anestart, else opstart (Sec 8/11)."""
    opend = to_float(case.get("opend"))
    start = to_float(case.get("anestart"))
    if start is None:
        start = to_float(case.get("opstart"))
    return start, opend


def _clip(series: list[tuple[float, float]], t0: float, t1: float) -> list[tuple[float, float]]:
    """Keep samples with t0 <= t <= t1. NEVER returns a sample at t > opend (Sec 11)."""
    return [(t, v) for (t, v) in series if t0 <= t <= t1]


def _time_weighted_summary(series: list[tuple[float, float]],
                           t1: float) -> tuple[float | None, float | None, float | None]:
    """Return (peak, time-weighted mean, AUC-in-minutes) of a value track.

    AUC is the trapezoidal integral in (value . minutes); mean = AUC / duration_min.
    `series` must already be clipped to the intraop window and sorted by time.
    Trailing samples are not extrapolated past their last timestamp (<= t1).
    """
    if not series:
        return None, None, None
    series = sorted(series, key=lambda x: x[0])
    peak = max(v for _, v in series)
    if len(series) == 1:
        return peak, series[0][1], 0.0
    auc_sec = 0.0
    for (ta, va), (tb, vb) in zip(series, series[1:]):
        dt = tb - ta
        if dt <= 0:
            continue
        auc_sec += 0.5 * (va + vb) * dt
    dur_sec = series[-1][0] - series[0][0]
    auc_min = auc_sec / 60.0
    mean = (auc_sec / dur_sec) if dur_sec > 0 else series[0][1]
    return peak, mean, auc_min


def infusion_exposure(rate_series: list[tuple[float, float]],
                      vol_series: list[tuple[float, float]],
                      conc_per_ml: float,
                      t0: float, t1: float) -> dict[str, float | None]:
    """Exposure integrals for one infusion (Sec 7E/8), bounded to [t0, t1].

    Parameters
    ----------
    rate_series : Orchestra _RATE samples (t_seconds, mL/h).
    vol_series  : Orchestra _VOL samples (t_seconds, mL cumulative).
    conc_per_ml : drug units per mL of infusate (e.g. phenylephrine 100 ug/mL),
        used to convert mL -> drug units.

    Returns
    -------
    {auc_dose, peak_rate, cum_dose, dur_min}, where
      * peak_rate  : peak infusion rate in drug-units/min (mL/h -> units/min).
      * auc_dose   : area under the rate curve = total dose-time integral
                     (drug-units . min) via trapezoid on the unit-rate.
      * cum_dose   : cumulative dose (drug units) from _VOL (last - first mL) x conc,
                     restricted to the window; falls back to integral if _VOL absent.
      * dur_min    : minutes with rate > 0 within the window.
    All None if the infusion is absent in-window.
    """
    rate = sorted(_clip(rate_series, t0, t1), key=lambda x: x[0]) if rate_series else []
    vol = sorted(_clip(vol_series, t0, t1), key=lambda x: x[0]) if vol_series else []
    if not rate and not vol:
        return {"auc_dose": None, "peak_rate": None, "cum_dose": None, "dur_min": None}

    # mL/h -> drug-units/min : (mL/h) * (units/mL) / 60
    unit_rate = [(t, (r * conc_per_ml) / 60.0) for (t, r) in rate]
    peak_rate = max((ur for _, ur in unit_rate), default=None)

    auc_dose = 0.0
    dur_sec = 0.0
    for (ta, ra), (tb, rb) in zip(unit_rate, unit_rate[1:]):
        dt = tb - ta
        if dt <= 0:
            continue
        auc_dose += 0.5 * (ra + rb) * (dt / 60.0)  # units/min . min = units
        if ra > 0 or rb > 0:
            dur_sec += dt

    # cumulative dose preferentially from the pump's cumulative _VOL track
    if len(vol) >= 2:
        cum_ml = vol[-1][1] - vol[0][1]
        cum_dose = max(cum_ml, 0.0) * conc_per_ml
    elif auc_dose > 0:
        cum_dose = auc_dose  # integral of rate == delivered dose (units)
    else:
        cum_dose = 0.0

    return {
        "auc_dose": round(auc_dose, 4),
        "peak_rate": (round(peak_rate, 4) if peak_rate is not None else None),
        "cum_dose": round(cum_dose, 4),
        "dur_min": round(dur_sec / 60.0, 2),
    }


# ----------------------------------------------------------------------------
# Track wiring (Sec 8). Concentrations are per-mL drug content of the infusate.
# Orchestra naming: <DRUG><conc>_RATE (mL/h), _VOL (mL), _CE/_CP (pump conc).
# ----------------------------------------------------------------------------
PPF_RATE = "Orchestra/PPF20_RATE"
PPF_VOL = "Orchestra/PPF20_VOL"      # cumulative mL the pump infused (continuous)
PPF_CE_PUMP = "Orchestra/PPF20_CE"
PPF_MG_PER_ML = 20.0                 # PPF20 == 20 mg/mL

# phenylephrine bolus/infusion decomposition (Sec 7E). VitalDB's Orchestra
# phenylephrine channel is "PHEN"; its _VOL is cumulative mL infused.
PHE_RATE = "Orchestra/PHEN_RATE"
PHE_VOL = "Orchestra/PHEN_VOL"
# ASSUMPTION (documented, auditable): VitalDB does not publish the phenylephrine
# infusate concentration per case. The standard SNUH/Orchestra phenylephrine
# preparation is 100 ug/mL; we adopt 100 ug/mL as the named constant. This matches
# the concentration already used by the Sec-7E vasoactive exposure integrals below
# (VASO_INFUSIONS["phe"]). If a per-case concentration becomes available it should
# replace this constant; the bolus = total - infused decomposition is otherwise
# linear in the assumed concentration.
PHE_UG_PER_ML = 100.0

RFTN_CE_CANDIDATES = ["Orchestra/RFTN20_CE", "Orchestra/RFTN50_CE"]
MAC_TRACK = "Primus/MAC"

# vasoactive/nephrotoxin infusions: feature-prefix -> (drug stem, units/mL).
# Concentrations are VitalDB Orchestra defaults; documented so they are auditable.
VASO_INFUSIONS = {
    "phe":  ("PHEN", 100.0),    # phenylephrine 100 ug/mL
    "nepi": ("NEPI", 20.0),     # norepinephrine 20 ug/mL
    "epi":  ("EPI", 20.0),      # epinephrine 20 ug/mL
    "dopa": ("DOPA", 3.0),      # dopamine ~3 mg/mL (units: mg)
    "vaso": ("VASO", 1.0),      # vasopressin 1 unit/mL
}


def _to_1hz_mg_s(rate_series: list[tuple[float, float]], t0: float, t1: float) -> tuple[list[float], list[float]]:
    """Convert a sparse PPF20 _RATE (mL/h) track into a 1 Hz mg/second grid over
    [t0, t1] using zero-order hold (the pump rate is piecewise-constant).

    Returns (infusion_mg_s, times) with one entry per second of the window.
    """
    rate = sorted(_clip(rate_series, t0, t1), key=lambda x: x[0])
    n_sec = int(round(t1 - t0))
    if n_sec <= 0 or not rate:
        return [], [t0]
    # piecewise-constant: rate held from each sample until the next.
    mg_s = [0.0] * n_sec
    j = 0
    cur = 0.0
    for i in range(n_sec):
        t = t0 + i
        while j < len(rate) and rate[j][0] <= t:
            cur = rate[j][1]
            j += 1
        # mL/h * mg/mL = mg/h ; / 3600 = mg/s
        mg_s[i] = (cur * PPF_MG_PER_ML) / 3600.0
    times = [t0 + i for i in range(n_sec + 1)]
    return mg_s, times


def infused_amount(vol_series: list[tuple[float, float]], conc_per_ml: float,
                   t0: float, t1: float) -> float | None:
    """Drug delivered by **continuous infusion** within [t0, t1], in drug units.

    The Orchestra `_VOL` track is the pump's CUMULATIVE mL infused; the in-window
    amount is (last - first in-window VOL, mL) x concentration. Leakage-bounded to
    the intraop window (Sec 11): no sample at t > opend contributes. Returns None
    when the VOL track is absent (cannot attribute total to infusion vs bolus);
    returns 0.0 when present but no volume moved in-window.
    """
    vol = sorted(_clip(vol_series, t0, t1), key=lambda x: x[0]) if vol_series else []
    if len(vol) < 1:
        return None
    if len(vol) == 1:
        return 0.0
    cum_ml = max(vol[-1][1] - vol[0][1], 0.0)
    return cum_ml * conc_per_ml


def decompose_dose(total: float | None, infused: float | None) -> dict[str, float | None]:
    """Split a TOTAL drug dose into continuous-infusion and bolus components.

    VitalDB has no bolus track; the `/cases` total (intraop_*) is bolus + infusion,
    and infusion is measured from the pump `_VOL`. Hence::

        bolus = max(0, total - infused)

    The clamp at 0 absorbs rounding (e.g. _VOL x conc slightly exceeding the charted
    total). `admin_mode` encodes the dosing pattern numerically:
        0 = none (no drug), 1 = bolus-only, 2 = infusion-only, 3 = both.

    Returns {total, infused, bolus, bolus_frac, admin_mode}. Any of total/infused
    may be None (missing); bolus/frac/mode are None when total is unknown.
    """
    out: dict[str, float | None] = {
        "total": total, "infused": infused,
        "bolus": None, "bolus_frac": None, "admin_mode": None,
    }
    if total is None:
        return out
    inf = infused if infused is not None else 0.0
    if inf < 0:
        inf = 0.0
    bolus = max(0.0, total - inf)
    out["bolus"] = round(bolus, 4)
    out["bolus_frac"] = round(bolus / total, 4) if total > 0 else 0.0
    has_bolus = bolus > 1e-9
    has_inf = inf > 1e-9
    if not has_bolus and not has_inf:
        mode = 0
    elif has_bolus and not has_inf:
        mode = 1
    elif has_inf and not has_bolus:
        mode = 2
    else:
        mode = 3
    out["admin_mode"] = mode
    return out


# ============================================================================
# extract() -- the module entry point (Sec 7-9 contract).
# ============================================================================
def extract(cfg: dict[str, Any], cases_by_id: dict[str, dict],
            caseids: list[str]) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for the Sec-8 PK features.

    Downloads only the PK tracks it needs, per case, via data.tracks.download_track
    (cached). All integration is bounded to the intraop window; nothing past opend
    is read (Sec 11). Lazy import of tracks keeps the contract import stdlib-only.
    """
    from vitaldb_aki.data.tracks import available_tracks, download_track, first_available

    out: dict[str, dict[str, Any]] = {}
    for cid in caseids:
        c = cases_by_id.get(str(cid))
        if c is None:
            continue
        f: dict[str, Any] = {k: None for k in (s.name for s in SPECS)}
        f["pk_available"] = 0

        t0, t1 = _window(c)
        if t0 is None or t1 is None or t1 <= t0:
            out[str(cid)] = f
            continue

        try:
            avail = set(available_tracks(cfg, cid))
        except Exception:
            avail = set()

        # ---- Propofol: bolus/infusion decomposition + Eleveld + pump Ce ------
        # Decompose the /cases total (intraop_ppf mg) into the pump-measured
        # continuous infusion (PPF20_VOL, mL x 20 mg/mL) and the residual bolus
        # (= max(0, total - infused)); feed the induction bolus into Eleveld.
        ppf_total = to_float(c.get("intraop_ppf"))
        ppf_infused = None
        if PPF_VOL in avail:
            ppf_infused = infused_amount(download_track(cfg, cid, PPF_VOL),
                                         PPF_MG_PER_ML, t0, t1)
        dec = decompose_dose(ppf_total, ppf_infused)
        f["ppf_total_mg"] = (round(ppf_total, 4) if ppf_total is not None else None)
        f["ppf_infused_mg"] = (round(ppf_infused, 4) if ppf_infused is not None else None)
        f["ppf_bolus_mg"] = dec["bolus"]
        f["ppf_bolus_frac"] = dec["bolus_frac"]
        f["ppf_admin_mode"] = dec["admin_mode"]

        if PPF_RATE in avail:
            rate = download_track(cfg, cid, PPF_RATE)
            mg_s, times = _to_1hz_mg_s(rate, t0, t1)
            if mg_s:
                age = to_float(c.get("age"))
                wt = to_float(c.get("weight"))
                ht = to_float(c.get("height"))
                sex_male = str(c.get("sex", "")).strip().upper().startswith("M")
                if age and wt and ht and wt > 0 and ht > 0:
                    f["pk_available"] = 1
                    # Induction bolus enters the central compartment at the first
                    # infusion sample (~anaesthesia start). Only fed when we could
                    # actually attribute infusion (PPF_VOL present); otherwise the
                    # bolus is unidentifiable and we keep the legacy infusion-only
                    # behaviour to avoid double-counting drug already in _RATE.
                    bolus = dec["bolus"] if (ppf_infused is not None and dec["bolus"]) else 0.0
                    ce = eleveld_ce(mg_s, times, age, wt, ht, sex_male,
                                    bolus_mg=bolus, bolus_index=0)
                    # Ce is on a 1 Hz grid; pair with second-grid times for summary.
                    ce_series = list(zip(times, ce))
                    peak, mean, auc = _time_weighted_summary(ce_series, t1)
                    f["ppf_ce_peak"] = (round(peak, 4) if peak is not None else None)
                    f["ppf_ce_mean"] = (round(mean, 4) if mean is not None else None)
                    f["ppf_ce_auc"] = (round(auc, 4) if auc is not None else None)

        if PPF_CE_PUMP in avail:
            pump = _clip(download_track(cfg, cid, PPF_CE_PUMP), t0, t1)
            peak_p, _, auc_p = _time_weighted_summary(pump, t1)
            f["ppf_ce_peak_pump"] = (round(peak_p, 4) if peak_p is not None else None)
            f["ppf_ce_auc_pump"] = (round(auc_p, 4) if auc_p is not None else None)

        # ---- Remifentanil: pump (Minto) Ce summaries -------------------------
        rftn_name, rftn = first_available(cfg, cid, RFTN_CE_CANDIDATES)
        if rftn:
            if f["pk_available"] == 0:
                f["pk_available"] = 1
            rftn = _clip(rftn, t0, t1)
            peak_r, mean_r, auc_r = _time_weighted_summary(rftn, t1)
            f["rftn_ce_peak"] = (round(peak_r, 4) if peak_r is not None else None)
            f["rftn_ce_mean"] = (round(mean_r, 4) if mean_r is not None else None)
            f["rftn_ce_auc"] = (round(auc_r, 4) if auc_r is not None else None)

        # ---- Phenylephrine + ephedrine: bolus/infusion decomposition (Sec 7E) -
        # Phenylephrine: total from /cases (intraop_phe ug) minus pump-infused
        # (PHEN_VOL mL x 100 ug/mL). Ephedrine has NO infusion track in VitalDB,
        # so intraop_eph (mg) is entirely bolus.
        phe_total = to_float(c.get("intraop_phe"))
        phe_infused = None
        if PHE_VOL in avail:
            phe_infused = infused_amount(download_track(cfg, cid, PHE_VOL),
                                         PHE_UG_PER_ML, t0, t1)
        phe_dec = decompose_dose(phe_total, phe_infused)
        f["phe_total_ug"] = (round(phe_total, 4) if phe_total is not None else None)
        f["phe_infused_ug"] = (round(phe_infused, 4) if phe_infused is not None else None)
        f["phe_bolus_ug"] = phe_dec["bolus"]
        f["phe_bolus_frac"] = phe_dec["bolus_frac"]

        eph_total = to_float(c.get("intraop_eph"))
        f["eph_bolus_mg"] = (round(eph_total, 4) if eph_total is not None else None)

        # ---- Volatiles: age-adjusted MAC-hours -------------------------------
        if MAC_TRACK in avail:
            mac = _clip(download_track(cfg, cid, MAC_TRACK), t0, t1)
            _, _, mac_auc_min = _time_weighted_summary(mac, t1)
            # Primus/MAC is already the age-adjusted MAC fraction; integral / 60 -> MAC.h
            f["mac_hours"] = (round(mac_auc_min / 60.0, 4) if mac_auc_min is not None else None)

        # ---- Vasoactive / nephrotoxin exposure integrals (Sec 7E) ------------
        for prefix, (stem, conc) in VASO_INFUSIONS.items():
            rt = f"Orchestra/{stem}_RATE"
            vt = f"Orchestra/{stem}_VOL"
            if rt not in avail and vt not in avail:
                continue
            rate_s = download_track(cfg, cid, rt) if rt in avail else []
            vol_s = download_track(cfg, cid, vt) if vt in avail else []
            ex = infusion_exposure(rate_s, vol_s, conc, t0, t1)
            f[f"{prefix}_auc_dose"] = ex["auc_dose"]
            f[f"{prefix}_peak_rate"] = ex["peak_rate"]
            f[f"{prefix}_cum_dose"] = ex["cum_dose"]
            f[f"{prefix}_dur_min"] = ex["dur_min"]

        out[str(cid)] = f
    return out
