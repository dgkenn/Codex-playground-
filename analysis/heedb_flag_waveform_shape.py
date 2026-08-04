#!/usr/bin/env python3
"""The last untested candidate for the clinician-flag residual: waveform SHAPE rather than band power.

THE STANDING CONSTRAINT. R358-R360: the clinician's "generalized slowing" flag carries
**-0.752 [-1.075, -0.434]** for 30-day death after adjusting for suppression burden AND for our intra-burst
8-30 Hz measure. A human reading the record sees something our numbers do not. R388 showed this is not an
artefact of adjusting for burden linearly (it survives quintile indicators). Four candidates were named:

    whole-record background spectrum   ELIMINATED (B3, R361-R364) -- redundant with the intra-burst measure
    spatial distribution / topography  ELIMINATED (T3, R365-R368) -- +0.014 [-0.021, +0.040] increment
    reactivity                         UNAVAILABLE -- no stimulation annotation in this schema
    waveform shape rather than spectrum  <- this script

**Why this candidate is not just the previous two again.** Both eliminations failed for the same reason,
now catalogue rule 28: a measurement taken in a different *place* is not thereby measuring a different
*thing*. Background spectrum and topography were both spectral measures relocated. Stereotypy, burst
amplitude, burst duration and suppression-interval variability differ in **kind** from a band-power ratio --
they describe the morphology of the waveform, not how its energy divides across frequencies. That is the
reason to rate this candidate above the two that failed, and it is stated before the run.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  S0  PRECONDITION, and it gates everything. Show the shape block carries SOME outcome information on its own
      (out-of-bag AUC increment over burden + intra-burst content, and its own coefficients). **If it carries
      nothing, this test cannot speak to the residual at all** and the verdict must be "uninformative", not
      "shape does not explain it" -- an empty filter is not evidence of absence (catalogue rule 5).

  S1  BASELINE. Reproduce the residual on this cohort: flag coefficient adjusted for burden and intra-burst
      content, with burden entered BOTH linearly and as quintile indicators (R388's stronger adjustment).
      The flexible version is primary.

  S2  PRIMARY. Add the shape block and report the change in the flag coefficient, bootstrapped PAIRED (the
      same resampled patients supply both fits, so the change is estimated on identical data).

  S3  PLACEBO, and it GATES S2 (catalogue rule 34). Adding four covariates moves a coefficient by chance.
      Permute the shape block ACROSS PATIENTS -- destroying its relation to outcome and to the flag while
      preserving its marginal distributions and its internal correlations -- and re-fit many times. That is
      the distribution of "attenuation" produced by four informationless covariates with this exact joint
      structure.
        CONFIRMED IF the real attenuation falls outside the permutation null.
        FALSIFIED IF it sits inside -- the flag residual is not waveform shape, and with all four named
        candidates then eliminated or unavailable, the residual becomes a standing negative rather than an
        open lead.

SCOPE LIMIT, stated up front. Morphology can only be extracted from recordings that have bursts, so this
cohort is burst-suppressed by construction (R409: the burst-suppression flag is present in 100.0 % of it).
The finding therefore applies to the residual WITHIN burst-suppressed patients, which is the same stratum
R360 was estimated in -- so the comparison is like-for-like -- but it is not a statement about all patients.
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()
from icare_morph_replication import logit_fit, oob_increment

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
BURDEN = os.environ.get("HEEDB_BURDEN", "/tmp/eeg_probe/heedb_bs_burden_win.s*.csv")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "1200"))
NPERM = int(os.environ.get("NPERM", "400"))
SHAPE = ["stereotypy", "burst_amp", "burst_dur", "supp_cv"]


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def median_by_patient(pattern, cols):
    d = {c: defaultdict(list) for c in cols}
    files = sorted(glob.glob(pattern))
    if not files:
        return {}
    for path in files:
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            if not p.isdigit():
                continue
            for c in cols:
                try:
                    v = float(r[c])
                except (KeyError, TypeError, ValueError):
                    continue
                if v == v:
                    d[c][int(p)].append(v)
    return {c: {p: float(np.median(v)) for p, v in d[c].items()} for c in cols}


def z(a):
    s = a.std()
    return (a - a.mean()) / (s if s > 1e-12 else 1.0)


def quintiles(b):
    e = np.quantile(b, [0.2, 0.4, 0.6, 0.8])
    idx = np.searchsorted(e, b, side="right")
    return np.column_stack([(idx == k).astype(float) for k in range(1, 5)])


def main():
    rng = np.random.default_rng(20260728)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    flag, when = {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        rd = csv.DictReader(io.StringIO(txt))
        assert "gen slowing" in (rd.fieldnames or []), "'gen slowing' column missing"
        for r in rd:
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            flag[p] = flag.get(p, False) or (
                (r.get("gen slowing") or "").strip() not in ("", "None", "nan"))
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is not None and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except (KeyError, TypeError, ValueError):
                pass

    bur = median_by_patient(BURDEN, ["burden"])["burden"]
    mor = median_by_patient(MORPH, ["alpha_beta"] + SHAPE)
    assert bur and mor["alpha_beta"], "burden or morphology table empty -- the join cannot be tested"

    ids = [p for p in bur if p in flag and p in when and p in death
           and all(p in mor[c] for c in ["alpha_beta"] + SHAPE)]
    rows = []
    for p in ids:
        d = death[p]
        if d is None:
            continue
        days = (d - when[p]).days
        if days < -1:
            continue
        rows.append((1.0 if days <= 30 else 0.0, 1.0 if flag[p] else 0.0, bur[p],
                     mor["alpha_beta"][p], [mor[c][p] for c in SHAPE]))
    n = len(rows)
    assert n >= 300, f"only {n} patients -- an empty join is not a result"
    y = np.array([r[0] for r in rows])
    f = np.array([r[1] for r in rows])
    b = np.array([r[2] for r in rows])
    a = np.array([r[3] for r in rows])
    S = np.array([r[4] for r in rows], float)
    print(f"cohort with flag + burden + intra-burst + shape + ascertained death: {n:,}")
    print(f"   30-day death {100*y.mean():.1f}%   flag positive {100*f.mean():.1f}%")

    # rule 32: every predictor must actually VARY here
    print("\n   shape block, distribution check (a covariate with no variance cannot explain anything):")
    for i, c in enumerate(SHAPE):
        v = S[:, i]
        print(f"      {c:>12}  median {np.median(v):>9.4f}  IQR "
              f"[{np.percentile(v,25):>8.4f}, {np.percentile(v,75):>8.4f}]  sd {v.std():>8.4f}")
        assert v.std() > 1e-9, f"{c} is constant in this cohort"
    Sz = np.column_stack([z(S[:, i]) for i in range(S.shape[1])])
    az, bz = z(a), z(b)
    Q = quintiles(b)
    one = np.ones(n)

    # ---- S0 precondition ---------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("S0  PRECONDITION — does the shape block carry ANY outcome information here?")
    print("=" * 100)
    Xbase_f = np.column_stack([one, Q, az])                 # flexible burden + intra-burst
    Xshape_f = np.column_stack([Xbase_f, Sz])
    mid_i, lo_i, hi_i, n_i = oob_increment(Xbase_f, Xshape_f, y, rng, reps=300)
    print(f"   out-of-bag AUC increment of the shape block over burden + intra-burst: "
          f"{mid_i:+.4f} [{lo_i:+.4f}, {hi_i:+.4f}]  ({n_i} usable resamples)")
    cs = logit_fit(Xshape_f, y)
    print("   shape-block coefficients in that model (standardized):")
    for i, c in enumerate(SHAPE):
        print(f"      {c:>12}  {cs[Xbase_f.shape[1] + i]:+.4f}")
    informative = (lo_i == lo_i and lo_i > 0) or any(
        abs(cs[Xbase_f.shape[1] + i]) > 0.15 for i in range(len(SHAPE)))
    print(f"   -> shape block is {'INFORMATIVE' if informative else 'UNINFORMATIVE'} about outcome here")

    # ---- S1 baseline -------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("S1  BASELINE — reproduce the flag residual on this cohort")
    print("=" * 100)

    def flagcoef(X, yy=None):
        yy = y if yy is None else yy
        return float(logit_fit(X, yy)[-1])

    lin_base = np.column_stack([one, bz, az, f])
    flex_base = np.column_stack([one, Q, az, f])
    lin_shape = np.column_stack([one, bz, az, Sz, f])
    flex_shape = np.column_stack([one, Q, az, Sz, f])
    for label, X in (("linear burden", lin_base), ("quintile burden (primary, R388)", flex_base)):
        c = flagcoef(X)
        print(f"   flag coefficient, {label:>32}: {c:+.4f}")
    print("   (R360 reported -0.752 [-1.075, -0.434] on its own cohort; this join differs, so the")
    print("    comparison is a similarity check, not a replication.)")

    # ---- S2 paired bootstrap -----------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("S2  PRIMARY — does adding the shape block attenuate the flag coefficient?")
    print("=" * 100)
    c0 = flagcoef(flex_base); c1 = flagcoef(flex_shape)
    d_obs = c1 - c0
    ret = c1 / c0 if abs(c0) > 1e-9 else float("nan")
    boots = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        if not (0 < y[i].sum() < n):
            continue
        try:
            bb = flagcoef(flex_base[i], y[i]); cc = flagcoef(flex_shape[i], y[i])
        except Exception:
            continue
        if np.isfinite(bb) and np.isfinite(cc):
            boots.append(cc - bb)
    blo, bhi = (np.percentile(boots, [2.5, 97.5]) if len(boots) > NBOOT // 4 else (np.nan, np.nan))
    print(f"   flag coefficient without shape: {c0:+.4f}")
    print(f"   flag coefficient with    shape: {c1:+.4f}     retained {100*ret:.0f}%")
    print(f"   paired change: {d_obs:+.4f} [{blo:+.4f}, {bhi:+.4f}]"
          f"{'   excludes zero' if blo * bhi > 0 else '   INCLUDES ZERO'}")

    # ---- S3 placebo, which gates S2 ------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("S3  PLACEBO — the same four covariates, permuted across patients (gates S2)")
    print("=" * 100)
    perm = []
    for _ in range(NPERM):
        pi = rng.permutation(n)
        Xp = np.column_stack([one, Q, az, Sz[pi], f])
        try:
            perm.append(flagcoef(Xp) - c0)
        except Exception:
            continue
    perm = np.array([p for p in perm if np.isfinite(p)])
    plo, phi = np.percentile(perm, [2.5, 97.5])
    print(f"   permuted-shape change in the flag coefficient: median {np.median(perm):+.4f}, "
          f"95 % of draws in [{plo:+.4f}, {phi:+.4f}]  ({len(perm)} draws)")
    outside = d_obs < plo or d_obs > phi
    print(f"   observed change {d_obs:+.4f} is {'OUTSIDE' if outside else 'INSIDE'} that interval")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not informative:
        print("   UNINFORMATIVE — the shape block carries no detectable outcome information in this cohort,")
        print("   so its failure to attenuate the flag says nothing about the residual. An empty filter is")
        print("   not evidence of absence (rule 5). Do NOT record this as eliminating waveform shape.")
    elif outside and abs(d_obs) > abs(0.05 * c0):
        print("   S2 CONFIRMED — waveform shape absorbs part of the clinician-flag residual, by more than")
        print("   four informationless covariates do. This is the first positive on the residual.")
    else:
        print("   S2 FALSIFIED — the shape block carries outcome information yet does NOT move the flag")
        print("   coefficient beyond what four permuted covariates move it. Waveform shape is eliminated")
        print("   as an explanation of the residual.")
        print("   With background spectrum (B3), topography (T3) and now shape eliminated, and reactivity")
        print("   unavailable in this schema, the residual becomes a STANDING NEGATIVE: the clinician sees")
        print("   something none of the four named candidates captures.")
    print("\n   Scope: burst-suppressed patients only (morphology requires bursts) — the same stratum R360")
    print("   was estimated in, so the comparison is like-for-like, but not a claim about all patients.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
