#!/usr/bin/env python3
"""R403 said the lead's anoxic arm does not survive the withdrawal window. R409 says the reversal retains
93 % of itself across the same landmark. Both cannot be the headline, and the difference is not biology.

WHY THIS MATTERS MORE THAN ANYTHING ELSE IN THE QUEUE. The handoff's §3 carries a standing warning — "one
arm is withdrawal-vulnerable" — sourced from R403: among patients alive at day 3, the anoxic arm's AUC is
0.535 [0.492, 0.580], an interval including 0.5, on 800 patients. That warning is the single biggest stated
weakness of the project's lead, and it is quoted as if it qualified the reversal itself.

**But R403 tested a different quantity from the one the lead claims.** The lead is a REVERSAL — the two arms
point in opposite directions — and the estimand for that is the aetiology INTERACTION. R403 instead split the
cohort and asked whether each arm separately cleared its own null, on roughly a third of the patients, with
no control for what landmarking costs in power. Meanwhile R409's sweep put the interaction at **93 % retained
at day 3, inside a matched null of [87 %, 130 %]** — no detectable attenuation at all.

Splitting a sample and finding that one half no longer clears significance is the oldest way to manufacture a
false negative. This script tests whether that is what happened.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the reconciliation was looked at.

  W1  RESTATE BOTH ESTIMANDS ON ONE COHORT. Report, full cohort and alive-at-day-3: the aetiology
      interaction with a bootstrap CI, and each arm's AUC with a bootstrap CI. Same patients, same code.

  W2  DECISIVE. Apply the R408 matched null to the ARM-WISE statistic, which R403 never did. At day 3, draw
      subsamples of the FULL anoxic arm matched on n and on 30-day death rate, with NO landmark applied, and
      ask how often such a subsample's AUC interval includes 0.5.
        R403's NEGATIVE IS A POWER ARTEFACT IF that happens often — a random subsample of the same size
        routinely fails the same test, so failing it says nothing about withdrawal.
        R403 STANDS IF matched subsamples reliably clear 0.5 while the landmark subsample does not.

  W3  WHICH ESTIMAND SHOULD THE PAPER USE. State it from the design, not from which one won: the claim is
      that the direction differs by aetiology, so the interaction is the estimand and the arm-wise AUCs are
      descriptive. This is written down before the numbers to stop the answer being chosen after the fact.

WHAT A POSITIVE MEANS. The lead's biggest stated caveat is a power artefact and the handoff's §3 warning has
to be rewritten — the reversal survives the withdrawal window.
WHAT IT CANNOT MEAN. That withdrawal is absent. It is unmeasured (five failed proxies) and R410 found no
timing fingerprint either way. This is about whether R403 was evidence, not about whether withdrawal happens.
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
OMOP_OLD = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_Q = os.environ.get("OMOP_QUANT", "/tmp/eeg_probe/heedb_omop_quant")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))
NNULL = int(os.environ.get("NNULL", "400"))


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def auc(v, y):
    if not (0 < y.sum() < len(y)):
        return float("nan")
    r = np.argsort(np.argsort(v)).astype(float) + 1.0
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def main():
    rng = np.random.default_rng(20260728)
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
    with open(f"{OMOP_OLD}/death.csv") as fh:
        for r in csv.DictReader(fh):
            d = dt(r.get("death_datetime"))
            if d is not None:
                try:
                    death[int(r["person_id"])] = d
                except (KeyError, TypeError, ValueError):
                    pass
    src = f"{OMOP_Q}/condition_occurrence.csv"
    assert os.path.exists(src), f"{src} missing"
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
    ab = defaultdict(list)
    for path in sorted(glob.glob(MORPH)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            try:
                v = float(r["alpha_beta"])
            except (KeyError, TypeError, ValueError):
                continue
            if p.isdigit() and v == v:
                ab[int(p)].append(v)
    ab = {p: float(np.median(v)) for p, v in ab.items()}
    assert len(ab) > 500, f"morphology cache looks empty: {len(ab)}"

    rows = []
    for p in ab:
        if p not in when or p not in anox:
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((1.0 if anox[p] else 0.0,
                     1e9 if days is None else float(max(days, 0)), ab[p]))
    n = len(rows)
    ax = np.array([r[0] for r in rows])
    dd = np.array([r[1] for r in rows])
    v = np.array([r[2] for r in rows])
    y = (dd <= 30).astype(float)
    alive3 = dd > 3
    print(f"cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%   "
          f"alive at day 3 {int(alive3.sum()):,}")

    # ---- W1 ---------------------------------------------------------------------------------------
    def inter(m):
        k = int(m.sum())
        X = np.column_stack([np.ones(k), ax[m], v[m], v[m] * ax[m]])
        return float(logit_fit(X, y[m])[3])

    def boot_inter(m, reps):
        idx = np.flatnonzero(m); out = []
        for _ in range(reps):
            i = rng.choice(idx, len(idx), replace=True)
            if not (0 < y[i].sum() < len(i)):
                continue
            X = np.column_stack([np.ones(len(i)), ax[i], v[i], v[i] * ax[i]])
            try:
                c = float(logit_fit(X, y[i])[3])
            except Exception:
                continue
            if np.isfinite(c):
                out.append(c)
        return np.percentile(out, [2.5, 97.5]) if len(out) > reps // 4 else (np.nan, np.nan)

    def boot_auc(m, reps):
        idx = np.flatnonzero(m); out = []
        for _ in range(reps):
            i = rng.choice(idx, len(idx), replace=True)
            a = auc(v[i], y[i])
            if np.isfinite(a):
                out.append(a)
        return np.percentile(out, [2.5, 97.5]) if len(out) > reps // 4 else (np.nan, np.nan)

    everyone = np.ones(n, bool)
    print("\n" + "=" * 100)
    print("W1  BOTH ESTIMANDS, ONE COHORT, IDENTICAL CODE")
    print("=" * 100)
    for label, m in (("full cohort", everyone), ("alive at day 3", alive3)):
        c = inter(m); lo, hi = boot_inter(m, NBOOT)
        print(f"\n   {label}  (n = {int(m.sum()):,}, deaths {100*y[m].mean():.1f}%)")
        print(f"      aetiology x intra-burst INTERACTION   {c:+.3f} [{lo:+.3f}, {hi:+.3f}]"
              f"{'   excludes zero' if lo * hi > 0 else '   INCLUDES ZERO'}")
        for arm, am in (("anoxic", m & (ax == 1)), ("non-anoxic", m & (ax == 0))):
            a = auc(v[am], y[am]); alo, ahi = boot_auc(am, NBOOT)
            print(f"      {arm:>12} arm AUC  n = {int(am.sum()):>5,}  {a:.3f} [{alo:.3f}, {ahi:.3f}]"
                  f"{'   excludes 0.5' if (alo - .5) * (ahi - .5) > 0 else '   INCLUDES 0.5'}")

    # ---- W2 ---------------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("W2  DECISIVE — the matched null applied to the ARM-WISE statistic R403 used")
    print("=" * 100)
    for arm, val in (("anoxic", 1.0), ("non-anoxic", 0.0)):
        pool = np.flatnonzero(ax == val)
        lm = np.flatnonzero((ax == val) & alive3)
        tgt_n, tgt_e = len(lm), float(y[lm].mean())
        dpool = [p for p in pool if y[p] == 1.0]
        spool = [p for p in pool if y[p] == 0.0]
        want_d = int(round(tgt_n * tgt_e))
        want_s = tgt_n - want_d
        print(f"\n   {arm} arm: full {len(pool):,}, alive at day 3 {tgt_n:,} "
              f"({100*tgt_e:.1f}% died) — drawing matched subsamples of the FULL arm")
        if want_d > len(dpool) or want_s > len(spool):
            print("      not estimable — the matched cell exceeds the pool")
            continue
        incl = 0; aucs = []
        for _ in range(NNULL):
            i = np.concatenate([rng.choice(dpool, want_d, replace=False),
                                rng.choice(spool, want_s, replace=False)])
            lo, hi = boot_auc(np.isin(np.arange(n), i), 300)
            a = auc(v[i], y[i])
            if np.isfinite(a):
                aucs.append(a)
            if np.isfinite(lo) and (lo - .5) * (hi - .5) <= 0:
                incl += 1
        frac = incl / NNULL
        lmm = np.zeros(n, bool); lmm[lm] = True
        la = auc(v[lm], y[lm]); llo, lhi = boot_auc(lmm, NBOOT)
        print(f"      matched subsamples (no landmark): AUC median {np.median(aucs):.3f}, "
              f"{100*frac:.0f}% of them have an interval INCLUDING 0.5")
        print(f"      the actual day-3 subsample:       AUC {la:.3f} [{llo:.3f}, {lhi:.3f}]")
        if arm == "anoxic":
            if frac >= 0.25:
                print(f"      -> R403's NEGATIVE IS A POWER ARTEFACT: {100*frac:.0f}% of same-size, "
                      f"same-event-rate subsamples with NO landmark fail the same test.")
            else:
                print(f"      -> R403 STANDS: only {100*frac:.0f}% of matched subsamples fail it, so the "
                      f"landmark subsample's failure is not explained by size.")

    print("\n" + "=" * 100)
    print("W3  WHICH ESTIMAND THE PAPER USES — fixed by the design, written before the numbers")
    print("=" * 100)
    print("   The claim is that the DIRECTION of association differs by aetiology. That is the interaction.")
    print("   Arm-wise AUCs are descriptive and are reported for interpretability, not as the test. Splitting")
    print("   a cohort and requiring each half to clear its own null is a strictly weaker procedure, and it")
    print("   is the one R403 used.")
    print("\n   None of this shows withdrawal is absent — it is unmeasured (five failed proxies) and R410")
    print("   found no timing fingerprint. This is about whether R403 was evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
