#!/usr/bin/env python3
"""A discriminating test of the thalamocortical hypothesis, not another association.

WHERE THIS CANDIDATE COMES FROM. Consolidating 388 results yields 30 working constraints, and only a handful
discriminate between biological stories rather than between confounders. Three of them fit together:

  N9  Deafferented cortex produces burst suppression **in all cases** (PMID 9191587). So burst GENERATION is
      cortical and needs no thalamus.
  P6  Generalized slowing **present** marks survival strongly -- 74.9 % of >180-day survivors versus 29.7 % of
      <=3-day deaths -- a larger contrast than burden's own.
  R388 (new) The flag's effect is **largest where suppression is deepest**: -1.899 [-3.370, -0.884] in the top
      burden quintile against -0.639 [-1.273, -0.061] in the middle -- and that top quintile is exactly where
      the flag is least often positive (39.7 %).

THE CANDIDATE. Slow background rhythms require an intact thalamocortical loop; bursts do not. In a deeply
suppressed patient both states look alike on gross inspection -- mostly flat -- so **whether slow background
activity persists is what separates "cortex isolated but the thalamocortical system alive" from "cortex
isolated and the loop gone."** That is why the flag should matter most where suppression is deepest, which is
what R388 found, and it explains P6 and P5 (intra-burst content and background slowing correlate because both
index the same loop) without needing burst generation to be thalamic, which N9 forbids.

THE TEST, and it is a genuine fork rather than another association. The thalamus is **selectively vulnerable to
global hypoxia-ischaemia** and is usually structurally spared in toxic/metabolic encephalopathy. So:

  T1  REGISTERED, DIRECTIONAL. The flag's protective association, adjusted for burden and intra-burst content,
      is **LARGER in anoxic aetiology than in non-anoxic**. In anoxic injury the prior probability of thalamic
      damage is high, so preserved slowing certifies something informative; where the thalamus is usually
      intact anyway, its preservation says less.
      **FALSIFIED IF the interaction is absent or runs the other way.** A pure "slowing means less severe
      injury" account predicts NO aetiology interaction -- severity is severity -- so this discriminates
      between the thalamocortical candidate and the generic-severity account that would otherwise explain
      every one of P6, R388 and P5 equally well.

  T2  The same interaction for our quantitative intra-burst measure. If both instruments index one loop, the
      interaction should have the same sign in both. If the flag shows it and the quantitative measure does
      not, the two are not reading the same thing and the unification in the candidate is wrong.

WHAT A POSITIVE WOULD AND WOULD NOT BUY. It would not establish a mechanism -- L2 and L3 still stand, 46 % die
inside the withdrawal window and the outcome is how soon rather than whether. It would make the
thalamocortical account the only surviving candidate that predicts a pattern the generic-severity account does
not, which is the most any observational design here can deliver.
"""
import csv, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import logit_fit
from heedb_bs_ascertainment import AETIOLOGY, norm
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
BURDEN = os.environ.get("HEEDB_BURDEN", "/tmp/eeg_probe/heedb_bs_burden_win.s*.csv")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def median_by_patient(pattern, col):
    import glob
    d = defaultdict(list)
    for path in sorted(glob.glob(pattern)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            try:
                v = float(r[col])
            except (KeyError, TypeError, ValueError):
                continue
            if p.isdigit() and v == v:
                d[int(p)].append(v)
    return {p: float(np.median(v)) for p, v in d.items()}


def boot_coef(X, y, col, rng, reps):
    out, n = [], len(y)
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            try:
                out.append(float(logit_fit(X[i], y[i])[col]))
            except Exception:
                continue
    if len(out) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(out, [2.5, 97.5]))


def main():
    rng = np.random.default_rng(20260727)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))

    flag, when = {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            flag[p] = flag.get(p, False) or ((r.get("gen slowing") or "").strip() not in ("", "None", "nan"))
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t and (p not in when or t < when[p]):
                when[p] = t

    aet = defaultdict(set)
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            c = norm(r.get("condition_source_value"))
            if not c:
                continue
            for lab, pre in AETIOLOGY.items():
                if any(c.startswith(x) for x in pre):
                    aet[p].add(lab)

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except (KeyError, TypeError, ValueError):
                pass

    burden = median_by_patient(BURDEN, "burden")
    ab = median_by_patient(MORPH, "alpha_beta")
    assert burden and ab, "feature tables empty"

    rows = []
    for p in ab:
        if p not in flag or p not in when or p not in death or p not in burden:
            continue
        d = death[p]
        if d is None:
            continue
        days = (d - when[p]).days
        if days < -1:
            continue
        rows.append((p, 1.0 if days <= 30 else 0.0, 1.0 if flag[p] else 0.0,
                     burden[p], ab[p], 1.0 if "anoxic" in aet.get(p, ()) else 0.0))
    assert len(rows) >= 300, f"only {len(rows)} patients -- underpowered, and an empty join is not a result"
    y = np.array([r[1] for r in rows]); f = np.array([r[2] for r in rows])
    b = np.array([r[3] for r in rows]); a = np.array([r[4] for r in rows])
    anox = np.array([r[5] for r in rows])
    n = len(y)
    print(f"cohort: {n:,}   30-day death {100*y.mean():.1f}%   flag positive {100*f.mean():.1f}%   "
          f"anoxic {100*anox.mean():.1f}%")
    assert 0.05 < anox.mean() < 0.95, "aetiology split too extreme to test an interaction"

    one = np.ones(n)
    print("\n" + "=" * 96)
    print("T1  DOES THE FLAG'S EFFECT DEPEND ON AETIOLOGY?  (thalamocortical predicts YES, larger in anoxic)")
    print("=" * 96)
    for lab, m in (("anoxic", anox == 1), ("non-anoxic", anox == 0)):
        k = int(m.sum())
        if k < 120 or not (0 < y[m].sum() < k) or f[m].sum() < 15 or (1 - f[m]).sum() < 15:
            print(f"   {lab:<11} n={k:>5}  too few to estimate")
            continue
        X = np.column_stack([np.ones(k), b[m], a[m], f[m]])
        bb = logit_fit(X, y[m])
        lo, hi = boot_coef(X, y[m], 3, rng, NBOOT)
        print(f"   {lab:<11} n={k:>5}  death {100*y[m].mean():4.1f}%  flag positive {100*f[m].mean():4.1f}%"
              f"   flag coef {bb[3]:+.3f} [{lo:+.3f},{hi:+.3f}]")

    # the interaction itself, which is the actual test
    Xi = np.column_stack([one, b, a, anox, f, f * anox])
    bi = logit_fit(Xi, y)
    lo_i, hi_i = boot_coef(Xi, y, 5, rng, NBOOT)
    print(f"\n   INTERACTION flag x anoxic: {bi[5]:+.3f} [{lo_i:+.3f},{hi_i:+.3f}]")
    print(f"   (flag main effect in non-anoxic {bi[4]:+.3f}; implied anoxic effect {bi[4]+bi[5]:+.3f})")
    if lo_i == lo_i and lo_i * hi_i > 0:
        if bi[5] < 0:
            print("   T1 CONFIRMED -- the flag matters MORE after anoxia, as the thalamocortical account")
            print("   predicts and as a generic-severity account does not.")
        else:
            print("   T1 REVERSED -- the flag matters LESS after anoxia, which the candidate does not predict.")
    else:
        print("   T1 FALSIFIED -- no aetiology interaction. The generic-severity account survives and the")
        print("   thalamocortical candidate gains nothing over it: both predict P6, R388 and P5 equally, and")
        print("   this was the one place they disagreed.")

    print("\n" + "=" * 96)
    print("T2  SAME INTERACTION FOR THE QUANTITATIVE INTRA-BURST MEASURE")
    print("=" * 96)
    Xq = np.column_stack([one, b, anox, a, a * anox])
    bq = logit_fit(Xq, y)
    lo_q, hi_q = boot_coef(Xq, y, 4, rng, NBOOT)
    print(f"   intra-burst main effect {bq[3]:+.3f}   interaction x anoxic {bq[4]:+.3f} [{lo_q:+.3f},{hi_q:+.3f}]")
    same = (lo_i == lo_i and lo_q == lo_q and lo_i * hi_i > 0 and lo_q * hi_q > 0
            and np.sign(bi[5]) == np.sign(bq[4]))
    print(f"   {'Both instruments show the same-signed interaction -- consistent with one shared factor.' if same else 'The two instruments do NOT show a matching interaction, so the claim that they index one loop is not supported here.'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
