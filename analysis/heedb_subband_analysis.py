#!/usr/bin/env python3
"""Which PART of the ratio carries the reversal? Alpha vs beta, fast vs slow, median vs monotony.

The lead measures `alpha_beta` = P[8-30] / P[1-30] and finds its prognostic sign reverses by aetiology.
`heedb_burst_subband.py` decomposes that single number, on the SAME bursts, into the pieces that three
surviving mechanism candidates disagree about. This script tests them.

    F1  ALPHA COMA      -> the ALPHA sub-band (8-13) carries the reversal; beta (13-30) does not.
                           R416 demoted F1 from mechanism to magnitude-modifier, so this is now a test of
                           whether any alpha-specific signal survives at all.
    F2  SLOW DENOMINATOR -> `alpha_beta` is a RATIO: high means little 1-8 Hz as much as much 8-30 Hz. If
                           ABSOLUTE slow power carries the reversal and absolute fast power does not, the
                           finding has been misdescribed from the start -- it would be a reversal in SLOW
                           content, seen through a denominator.
    F3  MONOTONY        -> the WITHIN-PATIENT DISPERSION of per-burst alpha_beta carries it, not the median.
                           Non-reactive/invariant fast content is the malignant thing.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the sub-band data was looked at.

  V0  REPRODUCTION GATE, and nothing below may be read until it passes. The extraction recomputes
      `alpha_beta`, which the cached morphology table already holds. Correlate them per patient.
      **Exact equality is NOT expected and must not be the criterion** -- the 4 sampling windows can fail
      independently between runs, so a patient whose window set differs will differ (verified at smoke-test:
      one patient reproduced to 5 decimals with 8/8 bursts, another differed with 4 vs 1 bursts).
        PASS IF Pearson r >= 0.90 on patients present in both AND the mean signed difference is within
        0.02 (no systematic shift).
        FAIL -> the extraction has drifted; report that and interpret NOTHING (rule 31).

  V1  REFERENCE. Re-estimate the aetiology x `alpha_beta` interaction on THIS cohort using the NEW
      extraction, so every sub-band comparison below is like-for-like rather than against a number from a
      different join and a different run.

  V2  PRIMARY, three pre-specified contrasts, each an aetiology x measure interaction for 30-day death,
      standardized, age-adjusted:
          alpha_frac   (F1)      beta_frac   (F1 control)
          slow_frac and log_slow_pw / log_fast_pw   (F2)
          ab_iqr       (F3)
      Read by comparison WITH the V1 reference, not in isolation.

  V3  DIRECTION, model-free: per-aetiology AUC for each measure. A reversal means the two arms sit on
      OPPOSITE sides of 0.5 with both intervals excluding it -- the same bar `alpha_beta` itself clears.

  V4  DECOMPOSITION HONESTY (rule 28, and it is the trap here). `alpha_frac + beta_frac` is essentially
      `alpha_beta`, and `slow_frac = 1 - alpha_beta` EXACTLY. So slow_frac CANNOT be an independent finding
      -- it is the same number reflected, and if it "carries the reversal" that is arithmetic, not biology.
      **Only the ABSOLUTE powers (log_slow_pw, log_fast_pw) can separate "more fast" from "less slow".**
      This is stated before the run so the result cannot be over-read afterwards. Report the correlation
      matrix so the reader sees which measures are algebraically bound.

WHAT A POSITIVE MEANS. That the reversal is localised to a specific physiological band or to variability
rather than level -- which converts "8-30 Hz content" into a sharper claim.
WHAT IT CANNOT MEAN. A mechanism. Localising a signal in frequency constrains mechanisms; it does not
identify one.
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
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
SUB = os.environ.get("SUBBAND", "/tmp/eeg_probe/heedb_burst_subband.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "1500"))
MEASURES = ["alpha_beta", "alpha_frac", "beta_frac", "slow_frac", "ab_iqr",
            "log_fast_pw", "log_slow_pw"]
R_MIN, DIFF_MAX = 0.90, 0.02


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


def auc(v, y):
    if not (0 < y.sum() < len(y)):
        return float("nan")
    r = np.argsort(np.argsort(v)).astype(float) + 1.0
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def by_patient(pattern, cols):
    acc = {c: defaultdict(list) for c in cols}
    files = sorted(glob.glob(pattern))
    if not files:
        return {}, 0
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
                    acc[c][int(p)].append(v)
    return {c: {p: float(np.median(v)) for p, v in d.items()} for c, d in acc.items()}, len(files)


def main():
    rng = np.random.default_rng(20260729)
    S, nf = by_patient(SUB, MEASURES)
    assert S and S["alpha_beta"], f"no sub-band data at {SUB} -- extraction not finished?"
    O, _ = by_patient(MORPH, ["alpha_beta"])
    print(f"sub-band shards: {nf}   patients with sub-band data: {len(S['alpha_beta']):,}")

    # ---- V0 reproduction gate ----------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("V0  REPRODUCTION GATE — does the new extraction reproduce the cached alpha_beta?")
    print("=" * 100)
    both = sorted(set(S["alpha_beta"]) & set(O["alpha_beta"]))
    a = np.array([S["alpha_beta"][p] for p in both])
    b = np.array([O["alpha_beta"][p] for p in both])
    r = float(np.corrcoef(a, b)[0, 1]) if len(both) > 10 else float("nan")
    md = float(np.mean(a - b))
    exact = int(np.sum(np.abs(a - b) < 1e-4))
    print(f"   patients in both: {len(both):,}   Pearson r = {r:.4f}   mean signed diff = {md:+.4f}")
    print(f"   reproducing to 1e-4: {exact:,} ({100*exact/max(len(both),1):.0f}%)  "
          f"-- windows can fail independently between runs, so <100% is expected")
    gate = (r == r and r >= R_MIN and abs(md) <= DIFF_MAX)
    print(f"   GATE: {'PASS' if gate else 'FAIL'}  (needs r >= {R_MIN} and |mean diff| <= {DIFF_MAX})")
    if not gate:
        print("\n   *** EXTRACTION DRIFT — interpreting nothing below (rule 31).")
        return 1

    # ---- cohort ------------------------------------------------------------------------------------
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
        if p not in anox or p not in when or p not in age:
            continue
        if not all(p in S[m] for m in MEASURES):
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((0.0 if days is None else (1.0 if days <= 30 else 0.0),
                     1.0 if anox[p] else 0.0, age[p],
                     [S[m][p] for m in MEASURES]))
    n = len(rows)
    assert n >= 300, f"only {n} patients after the join"
    y = np.array([r_[0] for r_ in rows])
    ax = np.array([r_[1] for r_ in rows])
    ag = np.array([r_[2] for r_ in rows])
    V = np.array([r_[3] for r_ in rows], float)
    print(f"\n   analysis cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%")

    # ---- V4 algebraic-binding disclosure ------------------------------------------------------------
    print("\n" + "=" * 100)
    print("V4  WHICH MEASURES ARE ALGEBRAICALLY BOUND? (rule 28 — read this before the results)")
    print("=" * 100)
    print(f"   {'':>12} " + " ".join(f"{m[:10]:>11}" for m in MEASURES))
    for i, m in enumerate(MEASURES):
        print(f"   {m:>12} " + " ".join(f"{np.corrcoef(V[:, i], V[:, j])[0, 1]:>11.3f}"
                                        for j in range(len(MEASURES))))
    ab_i, sf_i = MEASURES.index("alpha_beta"), MEASURES.index("slow_frac")
    print(f"\n   alpha_beta vs slow_frac: r = {np.corrcoef(V[:, ab_i], V[:, sf_i])[0,1]:+.4f}"
          f"  — slow_frac = 1 - alpha_beta EXACTLY, so it cannot be an independent finding.")

    one = np.ones(n)
    agz = z(ag)

    def inter(vi, reps=NBOOT):
        vz = z(V[:, vi])
        X = np.column_stack([one, agz, ax, vz, vz * ax])
        try:
            c = float(logit_fit(X, y)[-1])
        except Exception:
            return None
        out = []
        for _ in range(reps):
            i = rng.integers(0, n, n)
            if not (0 < y[i].sum() < n):
                continue
            vv = z(V[i, vi])
            Xi = np.column_stack([np.ones(n), z(ag[i]), ax[i], vv, vv * ax[i]])
            try:
                cc = float(logit_fit(Xi, y[i])[-1])
            except Exception:
                continue
            if np.isfinite(cc):
                out.append(cc)
        if len(out) < reps // 4:
            return None
        return c, float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))

    print("\n" + "=" * 100)
    print("V1 / V2  AETIOLOGY x MEASURE INTERACTION (standardized, age-adjusted)")
    print("=" * 100)
    print(f"   {'measure':>12} {'role':>22} {'interaction':>28}")
    role = {"alpha_beta": "V1 REFERENCE", "alpha_frac": "F1 alpha", "beta_frac": "F1 beta (control)",
            "slow_frac": "F2 (bound to ref)", "log_slow_pw": "F2 absolute slow",
            "log_fast_pw": "F2 absolute fast", "ab_iqr": "F3 monotony"}
    res = {}
    for i, m in enumerate(MEASURES):
        c = inter(i)
        res[m] = c
        if c is None:
            print(f"   {m:>12} {role[m]:>22} {'not estimable':>28}")
        else:
            print(f"   {m:>12} {role[m]:>22} {f'{c[0]:+.3f} [{c[1]:+.3f}, {c[2]:+.3f}]':>28}"
                  f"{'  *' if c[1]*c[2] > 0 else ''}")

    print("\n" + "=" * 100)
    print("V3  DIRECTION, model-free — per-aetiology AUC (a reversal = opposite sides of 0.5)")
    print("=" * 100)
    print(f"   {'measure':>12} {'anoxic AUC':>26} {'non-anoxic AUC':>26} {'reversal?':>11}")
    for i, m in enumerate(MEASURES):
        line, sides = f"   {m:>12}", []
        for am in (ax == 1, ax == 0):
            idx = np.flatnonzero(am)
            a0 = auc(V[idx, i], y[idx])
            bs = []
            for _ in range(600):
                j = rng.choice(idx, len(idx), replace=True)
                v_ = auc(V[j, i], y[j])
                if np.isfinite(v_):
                    bs.append(v_)
            lo, hi = np.percentile(bs, [2.5, 97.5])
            star = "*" if (lo - .5) * (hi - .5) > 0 else " "
            sides.append(1 if lo > .5 else (-1 if hi < .5 else 0))
            line += f"   {a0:.3f} [{lo:.3f}, {hi:.3f}]{star}"
        rev = "YES" if (sides[0] * sides[1] == -1) else "no"
        print(line + f" {rev:>11}")
    print("   * = excludes 0.5")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    ref = res["alpha_beta"]
    if ref is None or ref[1] * ref[2] <= 0:
        print("   NO VERDICT — the reference interaction does not clear zero on this cohort, so there is")
        print("   nothing for the sub-bands to be compared against (rule 31).")
    else:
        def sig(m):
            c = res[m]
            return c is not None and c[1] * c[2] > 0
        print(f"   reference alpha_beta: {ref[0]:+.3f} [{ref[1]:+.3f}, {ref[2]:+.3f}]")
        if sig("alpha_frac") and not sig("beta_frac"):
            print("   F1 LOCALISED — alpha (8-13) carries the reversal and beta (13-30) does not.")
        elif sig("beta_frac") and not sig("alpha_frac"):
            print("   F1 REVERSED — beta carries it, alpha does not. Alpha coma does not fit.")
        elif sig("alpha_frac") and sig("beta_frac"):
            print("   NOT LOCALISED IN FREQUENCY — both sub-bands carry it, so the reversal is a broadband")
            print("   8-30 Hz phenomenon and no alpha-specific account is needed.")
        else:
            print("   NEITHER SUB-BAND clears zero alone — the split costs power and localises nothing.")
        if sig("log_slow_pw") and not sig("log_fast_pw"):
            print("   F2 SUPPORTED — ABSOLUTE SLOW power carries the reversal and absolute fast does not.")
            print("   The finding is a slow-content reversal seen through a denominator, and the paper's")
            print("   central description would need rewriting.")
        elif sig("log_fast_pw") and not sig("log_slow_pw"):
            print("   F2 REJECTED — absolute FAST power carries it; the measure means what it says.")
        else:
            print("   F2 UNRESOLVED on absolute powers (both or neither clear zero).")
        print("   F3 monotony: " + ("ab_iqr carries an independent reversal." if sig("ab_iqr")
                                    else "ab_iqr does NOT carry the reversal — level, not variability."))
    print("\n   slow_frac is 1 - alpha_beta exactly; any 'result' for it is arithmetic (V4).")
    print("   Localising a signal in frequency constrains mechanisms; it does not identify one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
