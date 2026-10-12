"""Propofol exposure models: from a bolus record to a predicted effect-site signal, in rungs.

WHY A LADDER RATHER THAN ONE MODEL. The investigator asked for a PK/PD model "advanced and comprehensive
but journal defendable", and then for "multiple levels" to be built and tested. `PKPD_MODEL_REVIEW.md` §6
already established the defensibility boundary: a published model may be implemented, a relation may not be
invented. This module implements the rungs that clear that boundary and stops.

THE PAYWALL ON ELEVELD 2018 DOES NOT BLOCK THIS, FOR A STRUCTURAL REASON WORTH STATING PLAINLY.
Every mammillary compartment model -- Marsh, Schnider, Eleveld, any of them -- is LINEAR and
TIME-INVARIANT. Its unit-bolus disposition function is a sum of decaying exponentials, and adding a
first-order effect-site compartment convolves one more exponential onto it, which is again a sum of
exponentials. So for a dose record `D_i` at times `t_i`,

    Ce(t) = sum_i D_i * g(t - t_i),      g(tau) = sum_k a_k exp(-lambda_k tau)

and the ONLY thing a published parameter table supplies is the particular `(a_k, lambda_k)`. `basis()`
below computes the convolution of the dose record against a FIXED grid of rates spanning half-lives from
0.5 to 64 min, and lets a downstream linear fit choose the weights. **That family CONTAINS Marsh, Schnider
and Eleveld as points**, so a fit over it cannot do worse out of sample than transporting any one of them,
except through variance. This is a stronger incumbent for the EEG to beat, not a weaker one -- and it is
the honest way to run the comparison, because a transported model handicapped by population mismatch would
have made the EEG look good for the wrong reason (rule 50: measure the difference with the mechanism held
constant).

WHAT THE RUNGS ARE. Each returns a design matrix; nothing here fits anything.

    L0  cumulative dose to date, mg/kg                        no kinetics at all
    L1  single exponential, one rate                          the crudest washout
    L2  the full exponential basis                            contains any linear compartment model
    L3  L2 with ALLOMETRIC scaling                            weight enters as published theory, not fitted
    L4  L3 plus the recorded PD covariates                    age, sex, ASA, comorbidity, chronic drugs,
                                                              and the procedural stimulus indicator

ALLOMETRY IS THE ONE EXTERNAL PARAMETER AND IT IS A PRINCIPLE, NOT A TABLE. Clearances scale as WGT^0.75
and volumes as WGT^1.0, so concentration per unit dose scales as WGT^-1 and every rate as WGT^-0.25. That
is standard allometric theory (Anderson & Holford, Annu Rev Pharmacol Toxicol 2008;48:303-32, PMID
17914927) and it is what Eleveld's own model uses for its size covariate. Applying it needs no access to
Eleveld's fitted coefficients. It matters here because the cohort spans 34-165 kg, a 4.9-fold range.

WHAT THIS DELIBERATELY DOES NOT DO. No free-fraction model from albumin, no >=2-drug interaction surface,
no tolerance covariate with a fitted coefficient from the literature -- `PKPD_MODEL_REVIEW.md` §6 Tier 3
rules all three out for want of a validated published model, and DOSE-I is propofol mono-sedation so the
interaction question does not arise in it at all. Covariates that could modify sensitivity enter L4 as
plain regressors fitted on this cohort, which is a claim about this cohort and is labelled as one.
"""
from __future__ import annotations

# Half-lives in MINUTES. The span is set by the physiology and by the recordings, not by tuning: the
# fastest resolves the effect-site equilibration that follows a bolus (propofol ke0 half-times are of order
# 1-3 min in every published model), and the slowest exceeds the median DOSE-I record length so that the
# basis can represent a component which does not decay appreciably within a case. Eight rates over seven
# doublings; a denser grid buys nothing because the convolutions become collinear.
HALF_LIVES_MIN = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)

ALLOMETRIC_REF_KG = 70.0
ALLOMETRIC_EXP_CL = 0.75
ALLOMETRIC_EXP_V = 1.0


def _rates_per_s(half_lives_min=HALF_LIVES_MIN):
    import math
    return [math.log(2.0) / (h * 60.0) for h in half_lives_min]


def basis(dose_times_s, dose_mg, eval_times_s, half_lives_min=HALF_LIVES_MIN,
          weight_kg=None, allometric=False):
    """Convolution of a bolus record against a grid of exponential decays.

    Returns an array of shape (len(eval_times_s), len(half_lives_min)) whose column k at time t is

        sum_{i : t_i <= t}  D_i * exp(-lambda_k * (t - t_i))

    i.e. the effect-site signal of a one-compartment model with rate `lambda_k` driven by the real dose
    record. A linear combination of the columns is the effect-site signal of ANY linear disposition model
    whose eigenvalues lie in the grid, which is the whole point (see module docstring).

    Doses at times AFTER an evaluation point contribute nothing, which is enforced by the `t_i <= t` filter
    rather than by trusting the caller's ordering. That filter is the only thing standing between this and
    look-ahead (rule 10), so it is explicit.

    `allometric=True` divides the dose by (WGT/70)^1.0 and multiplies every rate by (WGT/70)^(0.75-1.0)
    = (WGT/70)^-0.25, which is allometric scaling of volume and clearance respectively.
    """
    import numpy as np
    t = np.asarray(eval_times_s, dtype=float)
    dt = np.asarray(dose_times_s, dtype=float)
    dm = np.asarray(dose_mg, dtype=float)
    lam = np.asarray(_rates_per_s(half_lives_min), dtype=float)

    if allometric:
        if weight_kg is None or not np.isfinite(weight_kg) or weight_kg <= 0:
            raise ValueError("allometric scaling needs a positive weight")
        f = float(weight_kg) / ALLOMETRIC_REF_KG
        dm = dm / (f ** ALLOMETRIC_EXP_V)
        lam = lam * (f ** (ALLOMETRIC_EXP_CL - ALLOMETRIC_EXP_V))

    out = np.zeros((t.size, lam.size), dtype=float)
    if dt.size == 0:
        return out
    order = np.argsort(dt)
    dt, dm = dt[order], dm[order]
    # (n_eval, n_dose) elapsed time; a 400 x 30 matrix per recording, so the explicit form is fine and is
    # far easier to check than an incremental recursion.
    gap = t[:, None] - dt[None, :]
    live = gap >= 0.0
    for k, L in enumerate(lam):
        contrib = np.where(live, dm[None, :] * np.exp(-L * np.where(live, gap, 0.0)), 0.0)
        out[:, k] = contrib.sum(axis=1)
    return out


def infusion_basis(seg_start_s, seg_end_s, seg_rate_mg_per_s, eval_times_s,
                   half_lives_min=HALF_LIVES_MIN, weight_kg=None, allometric=False):
    """The same exponential basis driven by CONSTANT-RATE INFUSION SEGMENTS instead of boluses.

    WHY THIS EXISTS. `basis()` takes instantaneous boluses, which is what DOSE-I records (its dose column
    is administration in multiples of 10 mg, and the reconstructed total matches the deposit's own
    `PROP_sum` exactly in 168 of 171 recordings, so no infusion is hiding in it). **VitalDB is different**:
    `Orchestra/PPF20_RATE` is a syringe-pump infusion rate in mL/h, present in 145 of the 250 cases with
    EEG features, and treating an infusion as a bolus at the segment start would front-load every gram of
    drug. A model that cannot represent an infusion cannot be used on the deposit where most of this
    project's anaesthesia work happens.

    THE SOLUTION IS EXACT, NOT NUMERICAL. For a constant rate `R` over `[t0, t1]` and kernel exp(-L tau),

        contribution(t) = R * integral over [t0, min(t, t1)] of exp(-L (t - s)) ds
                        = (R / L) * ( exp(-L (t - min(t,t1))) - exp(-L (t - t0)) )   for t >= t0

    which is closed form and has no step-size error, so an infusion and a bolus are on exactly the same
    footing. The bolus limit is recovered as R -> D/dt with dt -> 0, which `tests/test_pkpd_basis.py`
    checks directly rather than taking on trust.

    Segments are half-open `[t0, t1)` and are NOT required to be contiguous; a gap is simply zero rate.
    Doses after an evaluation point contribute nothing, enforced by the clamp rather than by trusting the
    caller's ordering -- the only barrier against look-ahead in this module (rule 10).
    """
    import numpy as np
    t = np.asarray(eval_times_s, dtype=float)
    s0 = np.asarray(seg_start_s, dtype=float)
    s1 = np.asarray(seg_end_s, dtype=float)
    R = np.asarray(seg_rate_mg_per_s, dtype=float)
    lam = np.asarray(_rates_per_s(half_lives_min), dtype=float)

    if allometric:
        if weight_kg is None or not np.isfinite(weight_kg) or weight_kg <= 0:
            raise ValueError("allometric scaling needs a positive weight")
        f = float(weight_kg) / ALLOMETRIC_REF_KG
        R = R / (f ** ALLOMETRIC_EXP_V)
        lam = lam * (f ** (ALLOMETRIC_EXP_CL - ALLOMETRIC_EXP_V))

    out = np.zeros((t.size, lam.size), dtype=float)
    if s0.size == 0:
        return out
    live = t[:, None] > s0[None, :]                     # segment has begun
    a = t[:, None] - s0[None, :]                        # elapsed since segment start
    b = t[:, None] - np.minimum(t[:, None], s1[None, :])  # elapsed since segment end (0 while running)
    a = np.where(live, a, 0.0)
    b = np.where(live, b, 0.0)
    for k, L in enumerate(lam):
        c = (R[None, :] / L) * (np.exp(-L * b) - np.exp(-L * a))
        out[:, k] = np.where(live, c, 0.0).sum(axis=1)
    return out


def rate_track_to_segments(times_s, rate_ml_per_h, mg_per_ml=20.0, t_end_s=None):
    """Turn a sampled pump-rate track into constant-rate segments, holding each value until the next.

    VitalDB publishes `Orchestra/PPF20_RATE` as (time, value) samples of a rate that the pump holds
    between updates -- a ZERO-ORDER HOLD, not a series of instantaneous events. Interpolating it linearly
    or treating each sample as a bolus would both be wrong, in opposite directions.

    `PPF20` is a 20 mg/mL preparation, hence the default: mL/h at 20 mg/mL is `rate * 20 / 3600` mg/s. The
    concentration is named in the track itself rather than assumed, and it is a parameter here so that a
    different preparation cannot be applied silently.

    The final segment is closed at `t_end_s` (default: the last sample), so an infusion never runs past
    the record.
    """
    import numpy as np
    t = np.asarray(times_s, dtype=float)
    r = np.asarray(rate_ml_per_h, dtype=float)
    ok = np.isfinite(t) & np.isfinite(r)
    t, r = t[ok], r[ok]
    if t.size == 0:
        return np.array([]), np.array([]), np.array([])
    o = np.argsort(t)
    t, r = t[o], r[o]
    end = float(t_end_s) if t_end_s is not None else float(t[-1])
    # MERGE RUNS OF EQUAL RATE. A zero-order hold sampled at 1 Hz emits one sample per second, so a
    # 20 minute infusion at a constant rate becomes 1,200 identical segments. Merging them is exactly
    # equivalent -- the integral of a constant rate over [a,b] plus [b,c] is its integral over [a,c] --
    # and it is the difference between a (1278 x 12781) design matrix per case and a (1278 x ~50) one.
    # Without it a single VitalDB case allocates gigabytes and the validation cannot run at all.
    change = np.ones(t.size, dtype=bool)
    change[1:] = r[1:] != r[:-1]
    idx = np.flatnonzero(change)
    s0 = t[idx]
    s1 = np.append(t[idx[1:]], end)
    rr = r[idx]
    keep = (s1 > s0) & (rr > 0)
    return s0[keep], s1[keep], rr[keep] * mg_per_ml / 3600.0


def cumulative(dose_times_s, dose_mg, eval_times_s, weight_kg=None):
    """L0: total mg administered up to each evaluation time, per kg if a weight is given."""
    import numpy as np
    t = np.asarray(eval_times_s, dtype=float)
    dt = np.asarray(dose_times_s, dtype=float)
    dm = np.asarray(dose_mg, dtype=float)
    if dt.size == 0:
        return np.zeros((t.size, 1))
    c = np.where(t[:, None] - dt[None, :] >= 0.0, dm[None, :], 0.0).sum(axis=1)
    if weight_kg:
        c = c / float(weight_kg)
    return c[:, None]


def rung(level, dose_times_s, dose_mg, eval_times_s, weight_kg=None, covariates=None):
    """Design matrix for one rung of the ladder, plus the column names.

    `covariates` is a mapping of already-numeric per-recording values used only by L4; it is broadcast
    down the rows, because everything in it is constant within a recording except the stimulus indicator,
    which the caller passes as a per-row sequence.
    """
    import numpy as np
    if level == 0:
        return cumulative(dose_times_s, dose_mg, eval_times_s, weight_kg), ["cum_mg_per_kg"]
    if level == 1:
        b = basis(dose_times_s, dose_mg, eval_times_s, half_lives_min=(4.0,))
        return b, ["exp_4min"]
    if level in (2, 3, 4):
        b = basis(dose_times_s, dose_mg, eval_times_s,
                  weight_kg=weight_kg, allometric=(level >= 3))
        names = [f"exp_{h:g}min" for h in HALF_LIVES_MIN]
        if level < 4:
            return b, names
        cols, cnames = [b], list(names)
        for k in sorted(covariates or {}):
            v = covariates[k]
            arr = np.asarray(v, dtype=float)
            if arr.ndim == 0:
                arr = np.full(len(eval_times_s), float(arr))
            cols.append(arr[:, None])
            cnames.append(k)
        return np.hstack(cols), cnames
    raise ValueError(f"unknown rung {level}")


# =====================================================================================================
# COMBINED ADMINISTRATION, AND THE OTHER TWO DRUGS
# =====================================================================================================
# The investigator asked whether the model accounts for infusions as well as boluses. It did, separately,
# and that was not the same as accounting for BOTH -- a patient can receive an induction bolus by hand and
# a maintenance infusion by pump, and the two records live in different tracks. `exposure_basis` below is
# the single entry point; it adds the two contributions, which is exact because the system is linear.
#
# The three anaesthesia drugs in VitalDB are NOT the same kind of problem and pretending they are would be
# the error:
#
#   propofol      infusion rate (Orchestra/PPF20_RATE) and/or boluses -> needs the full PK above
#   remifentanil  infusion rate (Orchestra/RFTN20_RATE)               -> same machinery, different potency
#   sevoflurane   END-TIDAL concentration (Primus/EXP_SEVO)           -> NO PK AT ALL
#
# The last one is worth stating plainly because it is easy to get wrong in the direction of doing more
# work than the data needs. End-tidal gas is a MEASURED concentration in equilibrium with alveolar and
# hence arterial blood -- it is not a dose. There is nothing to integrate. All that separates it from the
# effect site is a first-order lag, so a single exponential smoothing of the measured trace is the whole
# model, and convolving a dose record for it would be a category error.

SEVO_KE0_PER_MIN = 0.20     # order of magnitude only; see `effect_site_lag` for why the value is not
                            # load-bearing for any rank-based statistic in this project.


def exposure_basis(eval_times_s, bolus_times_s=None, bolus_mg=None,
                   seg_start_s=None, seg_end_s=None, seg_rate_mg_per_s=None,
                   half_lives_min=HALF_LIVES_MIN, weight_kg=None, allometric=False):
    """Boluses AND infusions for one drug, summed. Either may be empty.

    Superposition is exact here rather than approximate: the disposition is linear and time invariant, so
    the response to (boluses + infusion) is the sum of the responses. That is the same property the
    exponential-basis argument rests on, used once more.
    """
    import numpy as np
    t = np.asarray(eval_times_s, dtype=float)
    out = np.zeros((t.size, len(half_lives_min)), dtype=float)
    if bolus_times_s is not None and len(bolus_times_s):
        out = out + basis(bolus_times_s, bolus_mg, t, half_lives_min=half_lives_min,
                          weight_kg=weight_kg, allometric=allometric)
    if seg_start_s is not None and len(seg_start_s):
        out = out + infusion_basis(seg_start_s, seg_end_s, seg_rate_mg_per_s, t,
                                   half_lives_min=half_lives_min,
                                   weight_kg=weight_kg, allometric=allometric)
    return out


def effect_site_lag(times_s, measured_concentration, ke0_per_min=SEVO_KE0_PER_MIN):
    """First-order effect-site lag applied to a MEASURED concentration trace (end-tidal gas).

    dCe/dt = ke0 (C_measured - Ce), integrated exactly across each sample interval under a zero-order hold
    on `C_measured`, so an irregular or gappy trace is handled without a step-size assumption:

        Ce(t + dt) = C + (Ce(t) - C) * exp(-ke0 * dt)

    WHY THE ke0 VALUE IS NOT LOAD-BEARING HERE, which is worth knowing before anyone goes looking for a
    published one. Every statistic this project computes on the resulting series is RANK-BASED, and the
    lag is a causal monotone-in-history smoother: it changes the timing of the trace, not its ordering
    within a plateau. Sensitivity to `ke0` is therefore something to REPORT by re-running at a few values,
    not something to resolve by finding a better constant. Any experiment that turns out to depend on it
    has found something about the lag rather than about the drug.
    """
    import numpy as np
    t = np.asarray(times_s, dtype=float)
    c = np.asarray(measured_concentration, dtype=float)
    ok = np.isfinite(t) & np.isfinite(c)
    if ok.sum() < 2:
        return np.full(t.size, np.nan)
    k = float(ke0_per_min) / 60.0
    ce = np.full(t.size, np.nan)
    prev_t, prev_ce = None, 0.0
    for i in range(t.size):
        if not ok[i]:
            continue
        if prev_t is None:
            prev_ce = 0.0
        else:
            dt = t[i] - prev_t
            if dt > 0:
                prev_ce = c[i] + (prev_ce - c[i]) * np.exp(-k * dt)
        ce[i] = prev_ce
        prev_t = t[i]
    return ce
