#!/usr/bin/env python3
"""Which decomposed measures SURVIVE each other? R417 reported marginals; this asks what is redundant.

R417 found that every ratio-based measure reverses by aetiology -- `alpha_beta`, `alpha_frac`, `beta_frac`
and `ab_iqr` -- while neither ABSOLUTE band power does. But marginal reversals cannot be added up: the
measures are correlated (ab_iqr with alpha_beta at +0.628; beta_frac with alpha_beta at +0.926), so R417
deliberately refused to call any of them independent and deferred the question here.

THREE THINGS THIS SETTLES, none of which R417 could.

  U1  IS DISPERSION MORE THAN LEVEL? `ab_iqr` reverses marginally. Does its aetiology interaction survive
      adjustment for `alpha_beta` and ITS interaction? If not, monotony (F3) is level in disguise and the
      candidate closes.

  U2  IS THE REVERSAL ORTHOGONAL TO POWER, FORMALLY? R417 showed absolute power does not reverse and that
      `alpha_beta` correlates +0.002 with absolute fast power. The formal version: does the aetiology x
      alpha_beta interaction survive adjustment for BOTH absolute powers and their interactions? If it is
      unchanged, "the reversal is about balance, not amount" is established rather than inferred from a
      correlation.

  U3  ALPHA VERSUS BETA, HEAD TO HEAD. Both reversed marginally, and beta at least as strongly. Entered
      TOGETHER, does either survive? If neither does, the reversal is genuinely broadband and the sub-band
      split buys nothing -- which is itself worth recording so nobody splits it again.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the mutual models were fitted.

  Every model is a logistic fit for 30-day death, age-adjusted, with each measure standardized and entered
  WITH its own aetiology interaction, so an interaction is never adjusted for a main effect alone -- the
  classic way to make an interaction look robust when it is not.

  U1  y ~ age + aetiology + ab + ab:aetiology + iqr + iqr:aetiology.  REPORT the iqr:aetiology term.
        F3 SURVIVES IF it still excludes zero. F3 CLOSES IF it does not.
  U2  y ~ age + aetiology + ab + ab:aetiology + fastpw + fastpw:aetiology + slowpw + slowpw:aetiology.
      REPORT ab:aetiology, against its R417 marginal value.
        ORTHOGONALITY ESTABLISHED IF ab:aetiology is essentially unchanged (retains >= 80 %).
  U3  y ~ age + aetiology + alpha + alpha:aetiology + beta + beta:aetiology. REPORT both interactions.
        LOCALISED IF exactly one survives. BROADBAND IF neither does or both do.

  U4  COLLINEARITY DISCLOSURE, because it is the honest limit of U3. beta_frac correlates +0.926 with
      alpha_beta and alpha_frac +0.697; entering correlated predictors together inflates variance and can
      make BOTH lose significance for reasons of precision, not biology. So U3's "neither survives" reading
      must be reported ALONGSIDE the marginals, never instead of them, and the variance inflation is printed.

WHAT THIS CANNOT DO. Mutual adjustment identifies redundancy, not causation, and it cannot rescue a measure
that is simply noisier. A measure that loses significance here is not thereby shown to be unrelated to
outcome -- only shown not to add to the others.
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()
from icare_morph_replication import logit_fit

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
SUB = os.environ.get("SUBBAND", "/tmp/eeg_probe/heedb_burst_subband.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "1500"))
COLS = ["alpha_beta", "alpha_frac", "beta_frac", "ab_iqr", "log_fast_pw", "log_slow_pw"]


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def z(a):
    s = a.std()
    return (a - a.mean()) / (s if s > 1e-12 else 1.0)


def main():
    rng = np.random.default_rng(20260729)
    acc = {c: defaultdict(list) for c in COLS}
    files = sorted(glob.glob(SUB))
    assert files, f"no sub-band data at {SUB}"
    for path in files:
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            if not p.isdigit():
                continue
            for c in COLS:
                try:
                    v = float(r[c])
                except (KeyError, TypeError, ValueError):
                    continue
                if v == v:
                    acc[c][int(p)].append(v)
    S = {c: {p: float(np.median(v)) for p, v in d.items()} for c, d in acc.items()}

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when, age = {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for rr in csv.DictReader(io.StringIO(txt)):
            p = (rr.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            t = dt(rr.get("EndTime(EEG)") or rr.get("StartTime(EEG)") or "")
            if t and (p not in when or t < when[p]):
                when[p] = t
            try:
                v = float(rr.get("AgeAtVisit") or "")
                if v == v and p not in age:
                    age[p] = v
            except ValueError:
                pass
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for rr in csv.DictReader(fh):
            d = dt(rr.get("death_datetime"))
            if d is not None:
                try:
                    death[int(rr["person_id"])] = d
                except (KeyError, TypeError, ValueError):
                    pass
    from heedb_aetiology_compact import load_anoxic
    anox = load_anoxic()

    rows = []
    for p in S["alpha_beta"]:
        if p not in anox or p not in when or p not in age or not all(p in S[c] for c in COLS):
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((0.0 if days is None else (1.0 if days <= 30 else 0.0),
                     1.0 if anox[p] else 0.0, age[p], [S[c][p] for c in COLS]))
    n = len(rows)
    assert n >= 300, f"only {n} patients"
    y = np.array([r[0] for r in rows])
    ax = np.array([r[1] for r in rows])
    ag = np.array([r[2] for r in rows])
    V = np.array([r[3] for r in rows], float)
    Z = {c: z(V[:, i]) for i, c in enumerate(COLS)}
    print(f"cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%")

    one = np.ones(n)
    agz = z(ag)

    def fit(measures, want, reps=NBOOT):
        """measures = list of column names entered WITH their aetiology interactions.
        Returns the bootstrap CI for the `want` measure's interaction."""
        def design(idx=None):
            if idx is None:
                a, g, cols = ax, agz, {c: Z[c] for c in measures}
            else:
                a, g = ax[idx], z(ag[idx])
                cols = {c: z(V[idx, COLS.index(c)]) for c in measures}
            X = [one[:len(a)] if idx is None else np.ones(len(a)), g, a]
            for c in measures:
                X.append(cols[c])
            for c in measures:
                X.append(cols[c] * a)
            return np.column_stack(X)
        pos = 3 + len(measures) + measures.index(want)
        try:
            c0 = float(logit_fit(design(), y)[pos])
        except Exception:
            return None
        out = []
        for _ in range(reps):
            i = rng.integers(0, n, n)
            if not (0 < y[i].sum() < n):
                continue
            try:
                cc = float(logit_fit(design(i), y[i])[pos])
            except Exception:
                continue
            if np.isfinite(cc):
                out.append(cc)
        if len(out) < reps // 4:
            return None
        return c0, float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))

    def show(label, r, ref=None):
        if r is None:
            print(f"   {label:>46}: not estimable"); return
        tag = "   excludes zero" if r[1] * r[2] > 0 else "   INCLUDES ZERO"
        ret = f"   retains {100*r[0]/ref[0]:>3.0f}%" if ref and abs(ref[0]) > 1e-9 else ""
        print(f"   {label:>46}: {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]{tag}{ret}")

    print("\n" + "=" * 104)
    print("MARGINALS (each measure alone with its interaction) — the R417 reference point")
    print("=" * 104)
    marg = {}
    for c in ("alpha_beta", "ab_iqr", "alpha_frac", "beta_frac"):
        marg[c] = fit([c], c)
        show(f"{c} x aetiology, alone", marg[c])

    print("\n" + "=" * 104)
    print("U1  DISPERSION vs LEVEL — does ab_iqr survive adjustment for alpha_beta?")
    print("=" * 104)
    u1_iqr = fit(["alpha_beta", "ab_iqr"], "ab_iqr")
    u1_ab = fit(["alpha_beta", "ab_iqr"], "alpha_beta")
    show("ab_iqr x aetiology | + alpha_beta", u1_iqr, marg["ab_iqr"])
    show("alpha_beta x aetiology | + ab_iqr", u1_ab, marg["alpha_beta"])

    print("\n" + "=" * 104)
    print("U2  ORTHOGONALITY TO POWER — does alpha_beta survive adjustment for BOTH absolute powers?")
    print("=" * 104)
    u2 = fit(["alpha_beta", "log_fast_pw", "log_slow_pw"], "alpha_beta")
    show("alpha_beta x aetiology | + abs fast + abs slow", u2, marg["alpha_beta"])

    print("\n" + "=" * 104)
    print("U3  ALPHA vs BETA HEAD TO HEAD")
    print("=" * 104)
    u3_a = fit(["alpha_frac", "beta_frac"], "alpha_frac")
    u3_b = fit(["alpha_frac", "beta_frac"], "beta_frac")
    show("alpha_frac x aetiology | + beta_frac", u3_a, marg["alpha_frac"])
    show("beta_frac  x aetiology | + alpha_frac", u3_b, marg["beta_frac"])

    print("\n" + "=" * 104)
    print("U4  COLLINEARITY DISCLOSURE — how much precision does joint entry cost? (rule 28)")
    print("=" * 104)
    print(f"   {'pair':>34} {'r':>8} {'CI width alone -> joint':>32}")
    for a_, b_, ra, rj in (("alpha_frac", "beta_frac", marg["alpha_frac"], u3_a),
                           ("beta_frac", "alpha_frac", marg["beta_frac"], u3_b),
                           ("ab_iqr", "alpha_beta", marg["ab_iqr"], u1_iqr)):
        r_ = float(np.corrcoef(Z[a_], Z[b_])[0, 1])
        if ra and rj:
            wa, wj = ra[2] - ra[1], rj[2] - rj[1]
            print(f"   {a_+' with '+b_:>34} {r_:>+8.3f} {f'{wa:.3f} -> {wj:.3f}  (x{wj/max(wa,1e-9):.2f})':>32}")

    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)

    def sig(r):
        return r is not None and r[1] * r[2] > 0

    if sig(u1_iqr):
        print("   U1: F3 SURVIVES — dispersion adds to level; monotony is a real second axis.")
    else:
        print("   U1: F3 CLOSES — ab_iqr's marginal reversal does NOT survive adjustment for alpha_beta.")
        print("       Monotony is level in disguise, and the candidate is closed.")
    if sig(u2) and marg["alpha_beta"] and abs(u2[0]) >= 0.8 * abs(marg["alpha_beta"][0]):
        print("   U2: ORTHOGONALITY ESTABLISHED — the reversal is unchanged by absolute power in either")
        print("       band. 'Balance, not amount' is now a fitted result, not an inference from r = 0.002.")
    elif sig(u2):
        print("   U2: the reversal survives absolute power but is attenuated; report the retained fraction.")
    else:
        print("   U2: the reversal does NOT survive adjustment for absolute power — which would overturn")
        print("       R417's reading and must be investigated before anything is claimed.")
    if sig(u3_a) != sig(u3_b):
        print(f"   U3: LOCALISED — {'alpha' if sig(u3_a) else 'beta'} survives head-to-head.")
    elif not sig(u3_a) and not sig(u3_b):
        print("   U3: BROADBAND — neither sub-band survives the other. Read WITH U4: they correlate")
        print("       strongly, so joint entry costs precision, and the marginals both reversed. The")
        print("       honest claim is that the split buys nothing, NOT that neither band matters.")
    else:
        print("   U3: both survive — the two sub-bands carry separable information.")
    print("\n   Mutual adjustment identifies redundancy, not causation, and cannot rescue a noisier measure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
