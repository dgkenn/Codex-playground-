#!/usr/bin/env python3
"""E47 + E48 -- build the multi-cohort normative reference and test whether it is worth anything.

PRE-REGISTRATION. Written and committed before any multi-cohort feature value existed. Both decision rules
below enumerate the wrong-direction case explicitly, because this project has now printed a wrong verdict
five times (error catalogue rules 37 and 49).

=========================================================================================================
WHY TWO EXPERIMENTS AND NOT ONE
=========================================================================================================
The idea under test is: build our own normative model from several free cohorts plus HEEDB, and validate
it by checking that it agrees with what is already known. There are two separable claims in that sentence
and collapsing them would make both untestable.

  E47 asks: **is the PIPELINE calibrated?** -- does it reproduce a known age effect on a quantity where
      external truth exists?
  E48 asks: **does aperiodic correction HARMONISE?** -- does it reduce the disagreement between cohorts
      that differ in amplifier, reference and population?

E47 must pass for E48 to mean anything. A pipeline that cannot reproduce the best-replicated age effect in
quantitative EEG has no business emitting normative curves for a quantity nobody has normed.

=========================================================================================================
E47 -- THE BRIDGE. Validate on a quantity with external truth, transfer to one without.
=========================================================================================================
THE PROBLEM THIS SOLVES. `EXISTING_NORMATIVE_MODELS.md` established that no published normative database
models an aperiodic measure, so our exponent norms have nothing to be checked against. But INDIVIDUAL ALPHA
PEAK FREQUENCY does have external truth, it is computed by the same code on the same samples, and if the
pipeline reproduces the literature there then the exponent norms coming out of it inherit that credibility.

THE PUBLISHED ANCHORS, pulled through E-utilities and read rather than recalled. Each is quoted for exactly
what it says and no further (rule 42):

  * PMID 37503078 (MIDUS, N = 235, mean age 55): *"Both IAPF and the aperiodic exponent decrease with
    age"*.
  * PMID 39288668 (LEISURE, N = 96, ages 50-84): *"associations between older age and slower IAF, but not
    aIAP or global aperiodic exponent and offset"* -- so in older adults IAF declines and **the exponent
    does not reliably**.
  * PMID 36739102 (N = 502, ages 4-11): *"quadratic age-related effects for both the aperiodic offset and
    exponent"* and *"increases in periodic alpha peak frequency as a function of age"* -- in CHILDREN the
    alpha peak RISES with age.

THE CONSTRAINT THOSE THREE IMPOSE, WHICH A LINEAR LIFESPAN MODEL WOULD GET BACKWARDS. **The IAPF-age
relation changes sign between childhood and adulthood** -- rising to ~11, falling thereafter. Pooling ages
5-79 into one linear term would average a positive and a negative slope and could produce any number at
all. So:

  * the bridge test is restricted to **ADULTS (age >= 18)**, where the literature is one-directional;
  * the paediatric cohort (ds005514) is held out as a **direction-flip check**, not pooled in;
  * age enters non-linearly (natural-spline-like basis: age, age^2) whenever children are included.

PRIMARY (E47). Slope of `alpha_peak_hz` on age, adults only, healthy only, with sex and COHORT as fixed
effects so between-deposit level differences cannot masquerade as an age effect. Subject-level bootstrap CI.

DECISION RULE, two-sided and with the wrong direction named first:
  (a) FAIL -- slope > 0 with the CI excluding zero. The pipeline reproduces the OPPOSITE of the
      best-replicated adult result. E48 is not run and the exponent norms are not reported.
  (b) INCONCLUSIVE -- the CI includes zero. Underpowered or too noisy to certify; E48 runs but is
      reported as uncertified.
  (c) PASS -- slope < 0 with the CI excluding zero.

SECONDARY, and explicitly NOT a gate: slope of `whole_head_exponent` on age. Predicted negative on MIDUS,
but LEISURE found no reliable exponent-age association in 50-84, so **a null here does not fail the
bridge** and must not be reported as though it did. Registering it as secondary before the run is what
stops a null being reinterpreted afterwards.

PER-COHORT REPLICATION. The same slope fitted within each cohort separately. Agreement across cohorts is
meaningful here -- unlike rule 18's warning -- precisely because the cohorts differ in amplifier, reference
and population, so a shared slope cannot be a shared artefact of one rig.

=========================================================================================================
E48 -- DOES APERIODIC CORRECTION ACTUALLY HARMONISE?
=========================================================================================================
THE CLAIM. Absolute band power carries the aperiodic background, and the background is exactly what differs
between amplifiers, references and ages. Two cohorts can therefore disagree about alpha power while
agreeing precisely about how much alpha sits ABOVE their own backgrounds. If that is true, subtracting the
fitted aperiodic component should reduce between-cohort disagreement -- it should HARMONISE, which is the
job HarMNqEEG (PMID 35398285) and PMID 40946930 spend whole methods on.

THE STATISTIC. For each band and each parameterisation, regress the measure on age, age^2 and sex in the
POOLED healthy adult set, then take the residuals. The **batch index** is

    batch = SD across cohorts of the cohort-mean residual  /  mean within-cohort SD of the residual

a dimensionless ratio: how far apart the cohorts sit, in units of how spread out subjects are inside one.
Lower is better harmonised. Age and sex are removed FIRST so that a cohort's age composition cannot be
charged to its hardware.

THREE PARAMETERISATIONS, all from the same rows:
    abs_<band>     log10 absolute band power                     -- the uncorrected baseline
    rel_<band>     relative band power                           -- the field's usual normalisation
    resid_<band>   log10 power minus the fitted aperiodic model  -- the correction under test

PRIMARY (E48). batch(resid) - batch(abs), per band, subject-bootstrap CI.
  (a) REFUTED -- the CI includes zero, or lies ABOVE zero (correction made cohorts MORE different). The
      wrong-direction case is written first and named, because "excludes zero" and "supports the
      hypothesis" are different questions.
  (b) HARMONISES -- the CI lies entirely below zero AND the sham gate passes.
  (c) NOT INFORMATIVE -- the sham gate fails, or E47 returned FAIL.

THE SHAM GATE, and it is the one that makes this a test rather than a demonstration (rules 34, 47, 48).
Subtracting *anything* smooth and correlated shrinks variance. So the correction is repeated with an
aperiodic model taken from a DIFFERENT, randomly chosen subject in the same cohort: same functional form,
same magnitude, same smoothness, **no subject-specific information**. If the sham reduces the batch index
as much as the real correction, the reduction is variance-shrinkage rather than harmonisation. The gate is
a COMPARISON against the real effect, never an absolute threshold, and if the primary's interval includes
zero it prints NOT INFORMATIVE rather than PASSED -- a sham cannot validate a null.

WHY THE COMPARISON USES AN ANALYTIC MODEL FOR BOTH ARMS. The emitted `resid_<band>` column is computed on
the recording's own Welch grid, which the sham cannot reproduce for a different subject. Both arms
therefore recompute the correction from `(aperiodic_offset, aperiodic_exponent, abs_<band>)` through ONE
function, so real and sham differ only in whose fit is used and in nothing else.

=========================================================================================================
WHAT NEITHER EXPERIMENT CAN SHOW
=========================================================================================================
* E47 certifies the pipeline against ONE external anchor. A pipeline can get IAPF right and the exponent
  wrong; the bridge narrows the space of failures, it does not close it.
* E48's cohorts differ in POPULATION as well as hardware, and nothing here separates those. A correction
  that reduced hardware differences but not population differences would look partially effective, which
  is the honest description of what a positive result would mean.
* Neither says the reference is clinically useful. That needs the Q16 regression and a held-out site.

    python analysis/normative_multicohort.py
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "bsde", "src")))

MULTI = "/tmp/eeg_probe/multicohort_features.csv"
DS5385 = "/tmp/eeg_probe/ds005385_features.csv"
OUT = os.path.abspath(os.path.join(HERE, "..", "bsde", "results", "e47_e48_normative.json"))

BANDS = ("delta", "theta", "alpha", "beta")
ADULT_MIN_AGE = 18.0
MIN_PER_COHORT = 15
MIN_COHORTS = 3
REPS = 20000
SEED = 20260731


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:                                                        # noqa: BLE001
        return None


def _load():
    """Pool the multi-cohort table with ds005385's EYES-CLOSED rows only.

    ds005385 contributes only `task-EyesClosed`, `acq-pre`, `ses-1` -- eyes-closed because it is the only
    condition every cohort shares, acq-pre because the post-battery blocks follow two hours of cognitive
    work and are not a resting baseline, ses-1 so each subject enters once. All three restrictions are
    fixed here rather than chosen after looking.
    """
    rows = []
    if os.path.exists(MULTI):
        with open(MULTI) as fh:
            for r in csv.DictReader(fh):
                r["_cohort"] = r["cohort"]
                r["_subject"] = r["cohort"] + "/" + r["subject"]
                rows.append(r)
    if os.path.exists(DS5385):
        with open(DS5385) as fh:
            for r in csv.DictReader(fh):
                if r.get("task") != "EyesClosed" or r.get("acq") != "pre" or r.get("session") != "1":
                    continue
                r["_cohort"] = "ds005385"
                r["_subject"] = "ds005385/" + r["subject"]
                r["group"] = ""
                rows.append(r)
    # healthy only: ds004504 codes A = Alzheimer's, F = frontotemporal, C = control
    keep = []
    for r in rows:
        g = (r.get("group") or "").strip().upper()
        if g in ("A", "F"):
            continue
        if _f(r.get("age")) is None or (r.get("sex") or "").strip() == "":
            continue
        keep.append(r)
    # one row per subject (ds003775 has two sessions); keep the first deterministically
    seen, uniq = set(), []
    for r in sorted(keep, key=lambda z: (z["_subject"], z.get("session", ""), z.get("file", ""))):
        if r["_subject"] in seen:
            continue
        seen.add(r["_subject"])
        uniq.append(r)
    return uniq


def _design(rows, with_age2, cohorts):
    """[1, age, (age^2), sex_M, cohort dummies...] -- cohort as a fixed effect so a between-deposit level
    difference cannot be absorbed into the age slope."""
    cols = [np.ones(len(rows))]
    age = np.array([_f(r["age"]) for r in rows], float)
    cols.append(age)
    if with_age2:
        cols.append(age ** 2)
    cols.append(np.array([1.0 if (r["sex"] or "").upper().startswith("M") else 0.0 for r in rows]))
    for c in cohorts[1:]:
        cols.append(np.array([1.0 if r["_cohort"] == c else 0.0 for r in rows]))
    return np.vstack(cols).T


def _ols(X, y):
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef


def _boot_slope(rows, col, with_age2=False, reps=REPS, seed=SEED):
    """Age slope with a subject-level bootstrap CI. Returns (point, lo, hi, n)."""
    cohorts = sorted({r["_cohort"] for r in rows})
    y_all = np.array([_f(r.get(col)) for r in rows], float)
    ok = np.isfinite(y_all)
    rr = [r for r, k in zip(rows, ok) if k]
    if len(rr) < 30:
        return float("nan"), float("nan"), float("nan"), len(rr)
    y = np.array([_f(r.get(col)) for r in rr], float)
    X = _design(rr, with_age2, cohorts)
    point = float(_ols(X, y)[1])
    rng = np.random.default_rng(seed)
    n = len(rr)
    draws = []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        Xi, yi = X[idx], y[idx]
        if np.linalg.matrix_rank(Xi) < Xi.shape[1]:
            continue
        try:
            draws.append(float(_ols(Xi, yi)[1]))
        except Exception:                                                    # noqa: BLE001
            continue
    if len(draws) < reps // 2:
        return point, float("nan"), float("nan"), n
    d = np.sort(np.array(draws))
    return point, float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975)), n


def _model_band(offset, exponent, lo, hi, n=64):
    """Mean power the fitted aperiodic component alone predicts over [lo, hi]. ONE function, used for both
    the real and the sham correction, so the two arms differ only in whose fit is supplied."""
    if offset is None or exponent is None:
        return None
    f = np.linspace(lo, hi, n)
    return float(np.mean(10.0 ** (offset - exponent * np.log10(f))))


def _batch_index(rows, values, cohorts, denom=None):
    """SD across cohorts of the cohort-mean residual, over a FIXED within-cohort spread, after age, age^2
    and sex are regressed out. Age is removed FIRST so a cohort's age composition cannot be charged to a
    cohort's hardware.

    **THE DENOMINATOR IS SUPPLIED, NOT RECOMPUTED PER ARM, AND THAT IS THE WHOLE POINT.** The first version
    divided each arm by its OWN within-cohort SD, and `tests/test_e48_batch_index.py` showed the sham then
    BEAT the real correction (0.0184 against 0.0301) on data whose batch effect was purely aperiodic. The
    sham was not harmonising -- it was inflating its own denominator with the noise of using someone else's
    fit. A gate that rewards adding noise is worse than no gate. Every arm within a family now shares the
    denominator computed from the UNCORRECTED measure, so noise can only move the numerator."""
    v = np.asarray(values, float)
    ok = np.isfinite(v)
    if ok.sum() < 30:
        return float("nan")
    rr = [r for r, k in zip(rows, ok) if k]
    v = v[ok]
    age = np.array([_f(r["age"]) for r in rr], float)
    sex = np.array([1.0 if (r["sex"] or "").upper().startswith("M") else 0.0 for r in rr])
    X = np.vstack([np.ones(len(rr)), age, age ** 2, sex]).T
    resid = v - X @ _ols(X, v)
    means, sds = [], []
    for c in cohorts:
        m = np.array([r["_cohort"] == c for r in rr])
        if m.sum() < MIN_PER_COHORT:
            continue
        means.append(float(np.mean(resid[m])))
        sds.append(float(np.std(resid[m], ddof=1)))
    if len(means) < MIN_COHORTS:
        return float("nan")
    within = float(np.mean(sds)) if denom is None else float(denom)
    return float(np.std(means, ddof=1) / within) if within > 0 else float("nan")


def _within_spread(rows, values, cohorts):
    """Mean within-cohort SD of the age/sex-residualised measure -- the FIXED denominator for its family."""
    v = np.asarray(values, float)
    ok = np.isfinite(v)
    if ok.sum() < 30:
        return float("nan")
    rr = [r for r, k in zip(rows, ok) if k]
    v = v[ok]
    age = np.array([_f(r["age"]) for r in rr], float)
    sex = np.array([1.0 if (r["sex"] or "").upper().startswith("M") else 0.0 for r in rr])
    X = np.vstack([np.ones(len(rr)), age, age ** 2, sex]).T
    resid = v - X @ _ols(X, v)
    sds = [float(np.std(resid[np.array([r["_cohort"] == c for r in rr])], ddof=1))
           for c in cohorts
           if sum(1 for r in rr if r["_cohort"] == c) >= MIN_PER_COHORT]
    return float(np.mean(sds)) if sds else float("nan")


BAND_HZ = {"delta": (1.0, 4.0), "theta": (4.0, 8.0), "alpha": (8.0, 13.0), "beta": (13.0, 30.0)}


def _corrected(rows, band, sham_perm=None):
    """abs_<band> minus the aperiodic model's prediction over that band. `sham_perm` supplies, for each
    row, the INDEX of the row whose aperiodic fit to use instead of its own."""
    lo, hi = BAND_HZ[band]
    out = []
    for i, r in enumerate(rows):
        a = _f(r.get("abs_" + band))
        j = i if sham_perm is None else sham_perm[i]
        off, exp = _f(rows[j].get("aperiodic_offset")), _f(rows[j].get("whole_head_exponent"))
        m = _model_band(off, exp, lo, hi)
        out.append(a - math.log10(m) if (a is not None and m and m > 0) else float("nan"))
    return np.array(out, float)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reps", type=int, default=REPS)
    a = ap.parse_args(argv)

    rows = _load()
    adults = [r for r in rows if (_f(r["age"]) or 0) >= ADULT_MIN_AGE]
    cohorts = sorted({r["_cohort"] for r in adults})
    counts = {c: sum(1 for r in adults if r["_cohort"] == c) for c in cohorts}
    usable = [c for c in cohorts if counts[c] >= MIN_PER_COHORT]

    print("=" * 100)
    print("E47 / E48 -- multi-cohort normative reference")
    print("=" * 100)
    print(f"healthy rows pooled : {len(rows)}   adults (>= {ADULT_MIN_AGE:.0f}) : {len(adults)}")
    for c in cohorts:
        ages = [_f(r["age"]) for r in adults if r["_cohort"] == c]
        if ages:
            print(f"   {c:10s} n={counts[c]:4d}  age {min(ages):.0f}-{max(ages):.0f}")
    if len(usable) < MIN_COHORTS:
        print(f"\nG0 FAILED: {len(usable)} cohorts with >= {MIN_PER_COHORT} adults, need {MIN_COHORTS}.")
        print("Extraction is still running -- rerun when more rows have landed. No verdict emitted.")
        json.dump({"gate": "G0_failed", "counts": counts}, open(OUT, "w"), indent=2)
        return 1
    adults = [r for r in adults if r["_cohort"] in usable]
    print(f"G0 PASSED: {len(usable)} cohorts usable -> {usable}")

    # ------------------------------------------------------------------------------------ E47
    print("\n" + "=" * 100)
    print("E47 -- BRIDGE: does the pipeline reproduce the adult alpha-peak decline?")
    print("=" * 100)
    pt, lo, hi, n = _boot_slope(adults, "alpha_peak_hz", reps=a.reps)
    print(f"   alpha_peak_hz ~ age   slope {pt:+.5f} Hz/yr  [{lo:+.5f}, {hi:+.5f}]   n={n}")
    if not math.isfinite(lo):
        e47 = "INCONCLUSIVE (bootstrap degenerate)"
    elif lo > 0:
        e47 = "FAIL (slope POSITIVE in adults -- opposite to the published anchors; pipeline suspect)"
    elif lo <= 0 <= hi:
        e47 = "INCONCLUSIVE (interval includes zero)"
    else:
        e47 = "PASS (slope negative, interval excludes zero -- reproduces MIDUS/LEISURE direction)"
    print(f"   -> {e47}")

    pt2, lo2, hi2, n2 = _boot_slope(adults, "whole_head_exponent", reps=a.reps)
    print(f"\n   SECONDARY (not a gate): whole_head_exponent ~ age  slope {pt2:+.5f} /yr  "
          f"[{lo2:+.5f}, {hi2:+.5f}]   n={n2}")
    print("   A null here does NOT fail the bridge: PMID 39288668 found no reliable exponent-age")
    print("   association in ages 50-84, so the anchor itself is direction-specific to midlife.")

    print("\n   PER-COHORT replication of the alpha-peak slope (different rigs, so agreement is real):")
    per_cohort = {}
    for c in usable:
        sub = [r for r in adults if r["_cohort"] == c]
        p, l, h, nn = _boot_slope(sub, "alpha_peak_hz", reps=2000, seed=SEED + 7)
        per_cohort[c] = {"slope": p, "ci": [l, h], "n": nn}
        print(f"      {c:10s} {p:+.5f}  [{l:+.5f}, {h:+.5f}]  n={nn}")

    # ------------------------------------------------------------------------------------ E48
    print("\n" + "=" * 100)
    print("E48 -- does aperiodic correction reduce between-cohort disagreement?")
    print("=" * 100)
    if e47.startswith("FAIL"):
        print("   NOT INFORMATIVE: E47 failed, so the pipeline is not certified and E48 is not read.")
        json.dump({"e47": e47, "e48": "not_run_e47_failed"}, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    e48 = {}
    print(f"\n   {'band':7s} {'batch(abs)':>11s} {'batch(rel)':>11s} {'batch(gain)':>12s} "
          f"{'batch(resid)':>13s} {'batch(sham)':>12s}   verdict")
    print("   INCUMBENT is batch(gain) -- scalar gain removal, no aperiodic model. The primary is")
    print("   batch(resid) - batch(gain), NOT the comparison against raw power.")
    print("   " + "-" * 110)
    for b in BANDS:
        abs_v = np.array([_f(r.get("abs_" + b)) for r in adults], float)
        rel_v = np.array([_f(r.get("rel_" + b)) for r in adults], float)
        res_v = _corrected(adults, b)
        # SHAM: an aperiodic fit borrowed from a subject in a DIFFERENT cohort. A within-cohort sham was
        # tried first and is wrong for this claim -- everyone in a cohort shares that cohort's background,
        # so a within-cohort donor removes the batch effect just as well and the gate tests nothing. A
        # cross-cohort donor supplies a curve of the same form and magnitude carrying NO information about
        # this cohort's background, which is exactly the null "subtracting any smooth curve would do".
        perm = np.arange(len(adults))
        coh_of = np.array([r["_cohort"] for r in adults])
        for c in usable:
            idx = np.flatnonzero(coh_of == c)
            other = np.flatnonzero(coh_of != c)
            if other.size:
                perm[idx] = rng.choice(other, size=idx.size, replace=True)
        sham_v = _corrected(adults, b, sham_perm=perm)

        # INCUMBENT (rule 45), and E48 shipped without one until the numbers forced the issue: plain GAIN
        # REMOVAL -- subtract each recording's mean log power across the four bands. It removes a scalar
        # amplifier/reference gain and contains NO aperiodic model at all. If the correction cannot beat
        # it, then the harmonisation is gain removal and the exponent contributes nothing.
        gain_v = abs_v - np.nanmean(np.vstack([np.array([_f(r.get("abs_" + x)) for r in adults], float)
                                               for x in BANDS]), axis=0)

        # SELF-NORMALISED batch index: between-cohort SD over the SAME ARM's within-cohort SD.
        #
        # Both alternatives are wrong and each was tried. A per-arm denominator is gamed by ADDING NOISE
        # (inflate within, shrink the ratio) -- that is how the first within-cohort sham beat the real
        # correction. A FIXED denominator is gamed by SHRINKING EVERYTHING: the correction reduces
        # within-cohort spread to 11-22 % of the uncorrected measure, so a fixed denominator hands it a
        # free win for destroying signal. Self-normalisation is invariant to pure multiplicative
        # shrinkage, which kills the second failure, and the cross-cohort sham plus the capability gate
        # below cover the first.
        ba = _batch_index(adults, abs_v, usable)
        br = _batch_index(adults, rel_v, usable)
        bs = _batch_index(adults, res_v, usable)
        bh = _batch_index(adults, sham_v, usable)
        bg = _batch_index(adults, gain_v, usable)
        # CAPABILITY (rule 32, and E46's lesson): an arm that has destroyed its own between-subject
        # signal is not harmonised, it is empty. Report the retained spread so a collapse is visible.
        den_abs = _within_spread(adults, abs_v, usable)
        retain = _within_spread(adults, res_v, usable) / den_abs if den_abs else float("nan")

        # bootstrap the DIFFERENCE batch(resid) - batch(abs) over subjects
        n = len(adults)
        draws = []
        r2 = np.random.default_rng(SEED + 3)
        for _ in range(min(a.reps, 4000)):
            idx = r2.integers(0, n, n)
            sub = [adults[i] for i in idx]
            v1 = _batch_index(sub, gain_v[idx], usable)      # vs the INCUMBENT, not vs raw power
            v2 = _batch_index(sub, res_v[idx], usable)
            if math.isfinite(v1) and math.isfinite(v2):
                draws.append(v2 - v1)
        if draws:
            d = np.sort(np.array(draws))
            dlo, dhi = float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))
            # MUST match what the bootstrap resamples (resid vs the GAIN-REMOVAL incumbent). This read
            # `bs - ba` after the incumbent changed, and printed -4.9553 beside its own CI of
            # [-1.1882, -0.6272] -- a point estimate four times its interval, from comparing against raw
            # power while the interval compared against gain removal.
            point = bs - bg
        else:
            dlo = dhi = point = float("nan")

        sham_ok = math.isfinite(bh) and math.isfinite(bs) and bs < bh
        if not math.isfinite(dlo):
            v = "NOT INFORMATIVE (bootstrap degenerate)"
        elif not (math.isfinite(retain) and retain >= 0.10):
            v = "NOT INFORMATIVE (correction destroyed the within-cohort signal)"
        elif dlo <= 0 <= dhi:
            v = "REFUTED (no better than plain gain removal)"
        elif dlo > 0:
            v = "REFUTED IN THE OPPOSITE DIRECTION (WORSE than plain gain removal)"
        elif not sham_ok:
            v = "NOT INFORMATIVE (sham gate: a foreign cohort's fit harmonises as well)"
        else:
            v = "BEATS GAIN REMOVAL"
        e48[b] = {"batch_abs": ba, "batch_rel": br, "batch_resid": bs, "batch_sham": bh,
                  "batch_gain_removed": bg, "within_retained_vs_abs": retain,
                  "diff_vs_gain": point, "ci": [dlo, dhi], "verdict": v}
        print(f"   {b:7s} {ba:11.4f} {br:11.4f} {bg:12.4f} {bs:13.4f} {bh:12.4f}   {v}")
        print(f"   {'':7s} diff(resid - gain-removed) {point:+.4f}  [{dlo:+.4f}, {dhi:+.4f}]"
              f"   within-spread retained {retain:.3f}")

    payload = {"n_rows": len(rows), "n_adults": len(adults), "cohorts": counts, "usable": usable,
               "e47": {"alpha_peak_slope": pt, "ci": [lo, hi], "n": n, "verdict": e47,
                       "exponent_slope_secondary": pt2, "exponent_ci": [lo2, hi2],
                       "per_cohort": per_cohort},
               "e48": e48, "seed": SEED, "reps": a.reps}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(payload, open(OUT, "w"), indent=2, default=str)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
