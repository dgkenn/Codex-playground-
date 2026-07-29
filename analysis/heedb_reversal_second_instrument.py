#!/usr/bin/env python3
"""Does the aetiology reversal reproduce on an INDEPENDENT instrument? R412 just handed us one.

WHY THIS IS THE MOST VALUABLE TEST AVAILABLE. The project's lead is that intra-burst 8-30 Hz content ranks
30-day death in OPPOSITE directions by aetiology (interaction +4.646 [+3.092, +6.547]). Its one irreducible
weakness is external: no cohort anywhere has EEG + outcome + mixed aetiology, so a true replication cannot be
run at any effort (ledger §5 item 0, LESSONS). When an external replicate is structurally unavailable, the
strongest remaining check is a **second instrument that measures something else** — catalogue rule 23, which
this project learned when an exact solver caught a 0.775 deviation that seven unit tests had missed.

R412 produced exactly that. Burst amplitude carries flag-residual information and is **near-orthogonal to
everything the lead is already adjusted for**: r = -0.0001 with suppression burden, r = -0.023 with
intra-burst content. It is not a re-expression of the lead's own measure. So it can replicate the lead or
refute it, and either outcome is worth more than another robustness check on the original measure.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  T0  ORTHOGONALITY, restated on this cohort rather than inherited. Report the correlation matrix of the
      morphology measures with each other, with burden and with intra-burst content. **If burst amplitude
      turns out correlated with intra-burst content here, it is not an independent instrument and the whole
      premise fails** — say so and stop, rather than reporting a "replication" that is the same measure twice.

  T1  REFERENCE ARM. Re-estimate the lead's own interaction (aetiology x intra-burst content) on this exact
      cohort and adjustment set, so the comparison below is like-for-like and not against a quoted number
      from a different join.

  T2  PRIMARY, and burst amplitude is the ONLY pre-specified measure. Estimate the aetiology x burst-amplitude
      interaction for 30-day death, adjusted for suppression burden as quintile indicators (R388's stronger
      adjustment).
        GENERALIZES IF the interaction is non-zero and SAME-SIGNED as the lead's — the reversal is a property
        of burst vigour broadly, not of one spectral ratio, and the lead gains an independent instrument.
        SPECIFIC IF the interaction includes zero or is opposite-signed — the reversal is specific to spectral
        content. That is a genuinely informative negative: it constrains any mechanism to one that acts on
        frequency content and NOT on amplitude, which is a sharp constraint few mechanisms survive.

  T3  EXPLORATORY, and labelled as such. The same interaction for stereotypy, burst duration, burst rate and
      suppression-interval variability. **These are not tested hypotheses** — they are reported so the panel
      is visible and so a reader can see whether burst amplitude is special or one of several. No claim in
      this project may rest on them without its own registration.

  T4  DIRECTION, made concrete. Per-aetiology AUC for each measure, so "opposite directions" is shown rather
      than inferred from a coefficient sign.

WHAT A POSITIVE CANNOT MEAN. Not external replication. Same patients, same hospital network, same recordings
— only the measurement differs. It removes "the result is an artefact of how we computed one number", which
is a real and separate worry, and it removes nothing about the cohort.
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()
from icare_morph_replication import logit_fit
from heedb_bs_ascertainment import AETIOLOGY, norm

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_Q = os.environ.get("OMOP_QUANT", "/tmp/eeg_probe/heedb_omop_quant")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))
PRIMARY = "burst_amp"
REF = "alpha_beta"
EXPLORATORY = ["stereotypy", "burst_dur", "burst_rate", "supp_cv"]
ALL = [REF, PRIMARY] + EXPLORATORY


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


def quintiles(b):
    e = np.quantile(b, [0.2, 0.4, 0.6, 0.8])
    idx = np.searchsorted(e, b, side="right")
    return np.column_stack([(idx == k).astype(float) for k in range(1, 5)])


def auc(v, y):
    if not (0 < y.sum() < len(y)):
        return float("nan")
    r = np.argsort(np.argsort(v)).astype(float) + 1.0
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def main():
    rng = np.random.default_rng(20260729)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when = {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            d = dt(r.get("death_datetime"))
            if d is not None:
                try:
                    death[int(r["person_id"])] = d
                except (KeyError, TypeError, ValueError):
                    pass
    src = f"{OMOP_Q}/condition_occurrence.csv"
    assert os.path.exists(src), f"{src} missing -- rebuild the quant OMOP cache first"
    anox = {}
    with open(src) as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            anox.setdefault(p, False)
            c = norm(r.get("condition_source_value"))
            if c and any(c.startswith(x) for x in AETIOLOGY["anoxic"]):
                anox[p] = True

    cols = ALL + ["burden"]
    acc = {c: defaultdict(list) for c in cols}
    for path in sorted(glob.glob(MORPH)):
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
                    acc[c][int(p)].append(v)
    M = {c: {p: float(np.median(v)) for p, v in acc[c].items()} for c in cols}
    assert M[REF], "morphology cache empty -- an empty join is not a result"

    ids = [p for p in M[REF] if p in anox and p in when and p in death
           and all(p in M[c] for c in cols)]
    rows = []
    for p in ids:
        d = death[p]
        days = (d - when[p]).days
        if days < -1:
            continue
        rows.append((1.0 if days <= 30 else 0.0, 1.0 if anox[p] else 0.0,
                     M["burden"][p], [M[c][p] for c in ALL]))
    n = len(rows)
    assert n >= 300, f"only {n} patients"
    y = np.array([r[0] for r in rows])
    ax = np.array([r[1] for r in rows])
    b = np.array([r[2] for r in rows])
    V = np.array([r[3] for r in rows], float)
    print(f"cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%")
    for i, c in enumerate(ALL):
        assert V[:, i].std() > 1e-12, f"{c} is constant in this cohort"

    # ---- T0 orthogonality --------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("T0  ORTHOGONALITY — is burst amplitude actually a different instrument here?")
    print("=" * 100)
    names = ALL + ["burden"]
    W = np.column_stack([V, b])
    print(f"   {'':>12} " + " ".join(f"{c[:10]:>11}" for c in names))
    for i, c in enumerate(names):
        print(f"   {c:>12} " + " ".join(f"{np.corrcoef(W[:, i], W[:, j])[0, 1]:>11.3f}"
                                        for j in range(len(names))))
    r_key = float(np.corrcoef(V[:, ALL.index(PRIMARY)], V[:, ALL.index(REF)])[0, 1])
    r_bur = float(np.corrcoef(V[:, ALL.index(PRIMARY)], b)[0, 1])
    print(f"\n   {PRIMARY} vs {REF}: r = {r_key:+.3f}      {PRIMARY} vs burden: r = {r_bur:+.3f}")
    independent = abs(r_key) < 0.30
    if not independent:
        print(f"   PREMISE FAILS — |r| >= 0.30 means this is largely the same measure twice. Nothing below")
        print(f"   would be an independent replication, so no such claim may be made from this run.")

    Q = quintiles(b)
    one = np.ones(n)

    def inter(vi, reps=NBOOT):
        """Aetiology x measure interaction for 30-day death, adjusted for burden quintiles."""
        v = z(V[:, vi])
        X = np.column_stack([one, Q, ax, v, v * ax])
        c = float(logit_fit(X, y)[-1])
        out = []
        for _ in range(reps):
            i = rng.integers(0, n, n)
            if not (0 < y[i].sum() < n):
                continue
            vv = z(V[i, vi])
            Xi = np.column_stack([np.ones(n), quintiles(b[i]), ax[i], vv, vv * ax[i]])
            try:
                cc = float(logit_fit(Xi, y[i])[-1])
            except Exception:
                continue
            if np.isfinite(cc):
                out.append(cc)
        lo, hi = (np.percentile(out, [2.5, 97.5]) if len(out) > reps // 4 else (np.nan, np.nan))
        return c, lo, hi

    # ---- T1 / T2 / T3 ------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("T1 / T2 / T3  AETIOLOGY INTERACTION BY MEASURE (standardized; burden quintiles adjusted)")
    print("=" * 100)
    print(f"   {'measure':>12} {'role':>13} {'interaction':>28} {'sign':>6}")
    res = {}
    for i, c in enumerate(ALL):
        role = ("REFERENCE (the lead)" if c == REF else
                "PRIMARY" if c == PRIMARY else "exploratory")
        cc, lo, hi = inter(i)
        res[c] = (cc, lo, hi)
        sig = "" if (lo != lo or lo * hi <= 0) else ("+" if cc > 0 else "-")
        print(f"   {c:>12} {role[:13]:>13} {f'{cc:+.3f} [{lo:+.3f}, {hi:+.3f}]':>28} "
              f"{sig or 'ns':>6}")

    # ---- T4 direction ------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("T4  DIRECTION — per-aetiology AUC, so 'opposite directions' is shown, not inferred")
    print("=" * 100)
    print(f"   {'measure':>12} {'anoxic AUC':>26} {'non-anoxic AUC':>26}")
    for i, c in enumerate(ALL):
        line = f"   {c:>12}"
        for m in (ax == 1, ax == 0):
            a0 = auc(V[m, i], y[m])
            bs = []
            idx = np.flatnonzero(m)
            for _ in range(600):
                j = rng.choice(idx, len(idx), replace=True)
                v = auc(V[j, i], y[j])
                if np.isfinite(v):
                    bs.append(v)
            lo, hi = np.percentile(bs, [2.5, 97.5])
            star = "*" if (lo - .5) * (hi - .5) > 0 else " "
            line += f"   {a0:.3f} [{lo:.3f}, {hi:.3f}]{star}"
        print(line)
    print("   * = interval excludes 0.5")

    # ---- verdict -----------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    cr, lr, hr = res[REF]
    cp, lp, hp = res[PRIMARY]
    ref_ok = lr == lr and lr * hr > 0
    pri_ok = lp == lp and lp * hp > 0
    if not independent:
        print("   NO VERDICT — the orthogonality premise failed at T0 (see above).")
    elif not ref_ok:
        print("   NO VERDICT — the lead's own interaction does not clear zero on this cohort/adjustment,")
        print("   so there is no established effect for a second instrument to replicate. Fix the")
        print("   reference arm before interpreting anything else.")
    elif pri_ok and (cp * cr > 0):
        print(f"   T2 GENERALIZES — burst amplitude shows the same-signed reversal ({cp:+.3f} "
              f"[{lp:+.3f}, {hp:+.3f}]) as intra-burst content ({cr:+.3f}), on a measure correlated")
        print(f"   with it at only r = {r_key:+.3f}. The lead is not an artefact of one computed number.")
    elif pri_ok:
        print(f"   T2 OPPOSITE — burst amplitude's interaction is significant but OPPOSITE-signed "
              f"({cp:+.3f} vs {cr:+.3f}).")
        print("   Catalogue rule 16: when two arms of the same test disagree in sign, the definition is")
        print("   doing the work. Treat this as a warning about the measures, not a second finding.")
    else:
        print(f"   T2 SPECIFIC — burst amplitude shows no aetiology interaction "
              f"({cp:+.3f} [{lp:+.3f}, {hp:+.3f}]) while intra-burst content does ({cr:+.3f}).")
        print("   The reversal is specific to spectral CONTENT and does not extend to burst vigour.")
        print("   That is a sharp mechanistic constraint: any account must act on frequency content and")
        print("   NOT on amplitude, in the same bursts, in the same patients.")
    print("\n   Not external replication: same patients, same network, same recordings — only the")
    print("   measurement differs. Exploratory rows carry no claim.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
