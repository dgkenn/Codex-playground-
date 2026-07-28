#!/usr/bin/env python3
"""Do the guideline EEG prognostic findings mean the same thing in every aetiology?

WHY THIS IS THE CLINICALLY ACTIONABLE QUESTION. The ACNS terminology and the ERC-ESICM prognostication
guidance are built overwhelmingly on **cardiac-arrest** cohorts, and then applied to comatose patients
generally — septic, metabolic, structural, post-status. Whether that transfer is valid has never been tested
at scale, because almost every EEG-plus-outcome cohort in the literature is single-aetiology. **HEEDB is not**,
and that is the one thing this project has that others do not.

R389–R399 already showed that one *quantitative* measure — intra-burst 8–30 Hz content — reverses its
prognostic direction between anoxic and non-anoxic patients. This asks the same question of the findings that
are actually written in reports and actually used in guidelines.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  G1  PRIMARY, and pre-specified as the single primary test to keep the multiplicity honest: the **burst
      suppression** flag's association with 30-day death differs between anoxic and non-anoxic patients.
      This one is primary because it is the guideline's central malignant pattern and the subject of this
      whole programme.
      CONFIRMED IF the flag x aetiology interaction excludes zero.

  G2  FAMILY, reported whole rather than best-of: the same interaction for GPD, LPD, seizure, generalized
      slowing and focal slowing. Six tests in total including G1, so a single nominally-significant result
      among the five secondary ones is expected under the null and will be said so.

  G3  DIRECTION MATTERS MORE THAN SIZE. A finding whose association merely *weakens* in another aetiology is
      a quantitative transfer problem. A finding that **reverses sign** is a qualitative one — it would mean
      the same EEG pattern carries opposite prognostic information depending on why the patient is comatose,
      which is a different and much stronger claim. Both are reported separately.

  G4  ADJUSTED FOR MEASURED DEPTH. The flags co-occur with suppression burden, which itself differs by
      aetiology, so every interaction is re-estimated adjusting for quantitative burden. An interaction that
      vanishes on adjustment was a burden effect wearing a flag's clothes.

WHAT A POSITIVE WOULD MEAN. That guideline criteria derived from cardiac arrest should not be applied
uniformly across aetiologies — directly actionable, and testable by anyone with a mixed-aetiology cohort.
WHAT IT WOULD NOT MEAN. Nothing causal. These are associations in a cohort where 46 % die inside the
withdrawal window (L2) and where the outcome is partly a clinical decision (N14).
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import auc, logit_fit
from heedb_bs_ascertainment import AETIOLOGY, norm

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP_OLD = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_NEW = os.environ.get("OMOP_V2", "/tmp/eeg_probe/heedb_omop_quant")
BURDEN = os.environ.get("HEEDB_BURDEN", "/tmp/eeg_probe/heedb_bs_burden_win.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "1500"))
FINDINGS = ["bs", "gpd", "lpd", "seizure", "gen slowing", "foc slowing"]


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


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
    find, when = defaultdict(dict), {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            for f in FINDINGS:
                v = (r.get(f) or "").strip() not in ("", "None", "nan")
                find[p][f] = find[p].get(f, False) or v
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

    src = f"{OMOP_NEW}/condition_occurrence.csv"
    if not os.path.exists(src):
        src = f"{OMOP_OLD}/condition_occurrence.csv"
        print(f"   [wider extract absent — falling back to {src}]")
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
    assert anox, "no condition extract found"
    print(f"   aetiology source: {src}  ({len(anox):,} patients)")

    bur = defaultdict(list)
    for path in sorted(glob.glob(BURDEN)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            try:
                v = float(r["burden"])
            except (KeyError, TypeError, ValueError):
                continue
            if p.isdigit() and v == v:
                bur[int(p)].append(v)
    bur = {p: float(np.median(v)) for p, v in bur.items()}

    rows = []
    for p in anox:
        if p not in when or p not in find:
            continue
        d = death.get(p)
        if d is not None and (d - when[p]).days < -1:
            continue
        rows.append((p, 1.0 if (d is not None and (d - when[p]).days <= 30) else 0.0,
                     1.0 if anox[p] else 0.0, bur.get(p)))
    assert len(rows) >= 500, f"only {len(rows)} patients"
    y = np.array([r[1] for r in rows]); ax = np.array([r[2] for r in rows])
    has_b = np.array([r[3] is not None for r in rows])
    b = np.array([0.0 if r[3] is None else r[3] for r in rows])
    F = {f: np.array([1.0 if find[r[0]][f] else 0.0 for r in rows]) for f in FINDINGS}
    n = len(rows)
    print(f"cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%   "
          f"with measured burden {int(has_b.sum()):,}")

    one = np.ones(n)
    print("\n" + "=" * 104)
    print("G1 / G2  DOES EACH GUIDELINE FINDING MEAN THE SAME THING IN BOTH AETIOLOGIES?")
    print("=" * 104)
    print(f"{'finding':>14} {'prev':>7} {'anoxic coef':>22} {'non-anoxic coef':>22} {'interaction':>22}")
    print("-" * 104)
    results = {}
    for f in FINDINGS:
        v = F[f]
        if v.sum() < 60 or (1 - v).sum() < 60:
            print(f"{f:>14}   too few")
            continue
        cs = {}
        for lab, m in (("an", ax == 1), ("no", ax == 0)):
            k = int(m.sum())
            if k < 100 or not (0 < y[m].sum() < k) or v[m].sum() < 20 or (1 - v[m]).sum() < 20:
                cs[lab] = None
                continue
            X = np.column_stack([np.ones(k), v[m]])
            c = logit_fit(X, y[m]); lo, hi = boot_coef(X, y[m], 1, rng, NBOOT)
            cs[lab] = (c[1], lo, hi)
        Xi = np.column_stack([one, ax, v, v * ax])
        ci = logit_fit(Xi, y); li, hii = boot_coef(Xi, y, 3, rng, NBOOT)
        results[f] = (cs, ci[3], li, hii)
        s_an = f"{cs['an'][0]:+.2f} [{cs['an'][1]:+.2f},{cs['an'][2]:+.2f}]" if cs.get("an") else "n/a"
        s_no = f"{cs['no'][0]:+.2f} [{cs['no'][1]:+.2f},{cs['no'][2]:+.2f}]" if cs.get("no") else "n/a"
        star = "*" if li == li and li * hii > 0 else " "
        print(f"{f:>14} {100*v.mean():>6.1f}% {s_an:>22} {s_no:>22} "
              f"{f'{ci[3]:+.2f} [{li:+.2f},{hii:+.2f}]':>21}{star}")
    print("   * = interaction interval excludes zero.  Six tests; one nominal hit among the five secondary")
    print("   findings is expected under the null, so read the family, not the best member.")

    # ---- G3 ------------------------------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("G3  WEAKENING versus REVERSING — a sign flip is a qualitatively different claim")
    print("=" * 104)
    rev, weak = [], []
    for f, (cs, inter, li, hii) in results.items():
        if not (cs.get("an") and cs.get("no")):
            continue
        a_, n_ = cs["an"][0], cs["no"][0]
        if a_ * n_ < 0:
            rev.append((f, a_, n_, li, hii))
        elif li == li and li * hii > 0:
            weak.append((f, a_, n_))
    print(f"   REVERSING (opposite signs by aetiology): {[r[0] for r in rev] or 'none'}")
    for f, a_, n_, li, hii in rev:
        sig = "interaction excludes zero" if li == li and li * hii > 0 else "interaction spans zero"
        print(f"      {f:<14} anoxic {a_:+.2f}, non-anoxic {n_:+.2f}   ({sig})")
    print(f"   WEAKENING only (same sign, interaction excludes zero): {[w[0] for w in weak] or 'none'}")

    # ---- G4 ------------------------------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("G4  ADJUSTED FOR MEASURED SUPPRESSION BURDEN (patients with a quantitative burden only)")
    print("=" * 104)
    m = has_b
    k = int(m.sum())
    if k < 300:
        print(f"   only {k} patients have a measured burden — cannot adjust")
    else:
        print(f"   n={k:,}   30-day death {100*y[m].mean():.1f}%")
        print(f"{'finding':>14} {'interaction unadjusted':>26} {'interaction adj. burden':>28}")
        print("-" * 104)
        for f in FINDINGS:
            v = F[f][m]
            if v.sum() < 30 or (1 - v).sum() < 30:
                continue
            X0 = np.column_stack([np.ones(k), ax[m], v, v * ax[m]])
            c0 = logit_fit(X0, y[m]); l0, h0 = boot_coef(X0, y[m], 3, rng, NBOOT)
            X1 = np.column_stack([np.ones(k), b[m], ax[m], v, v * ax[m]])
            c1 = logit_fit(X1, y[m]); l1, h1 = boot_coef(X1, y[m], 4, rng, NBOOT)
            s0 = f"{c0[3]:+.2f} [{l0:+.2f},{h0:+.2f}]"
            s1 = f"{c1[4]:+.2f} [{l1:+.2f},{h1:+.2f}]"
            keep = "survives" if l1 == l1 and l1 * h1 > 0 else "gone"
            print(f"{f:>14} {s0:>26} {s1:>28}   {keep}")
        print("\n   An interaction that vanishes here was a burden effect wearing a flag's clothes.")

    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)
    if "bs" in results:
        _, inter, li, hii = results["bs"]
        ok = li == li and li * hii > 0
        print(f"   G1 (burst suppression, primary): interaction {inter:+.2f} [{li:+.2f},{hii:+.2f}] — "
              f"{'CONFIRMED, the flag does not transfer across aetiologies' if ok else 'not confirmed'}")
    print(f"   findings that REVERSE sign: {[r[0] for r in rev] or 'none'}")
    print("\n   Associations only. 46 % die inside the withdrawal window (L2) and the outcome is partly a")
    print("   clinical decision (N14), so nothing here is causal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
