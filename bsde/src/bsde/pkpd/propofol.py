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
