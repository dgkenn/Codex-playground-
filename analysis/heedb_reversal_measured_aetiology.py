#!/usr/bin/env python3
"""The aetiology reversal with survivors INCLUDED and their aetiology MEASURED, not assumed.

WHY THIS EXISTS, and it is a correction rather than an extension. R393 claimed the reversal survives removing
the death-ascertainment conditioning, expanding the non-anoxic arm from 679 to 1,633. R397 then found the tell
that undermined it: the extracted `condition_occurrence` table contains **only patients with a death record**,
so those 954 additional patients had no diagnosis data at all and were labelled non-anoxic by a **code default**
(`split.get(p, (False, False))`) rather than by measurement.

Checking why exposed something better than a caveat. The restriction is an artefact of **which patient list a
previous extraction was run against**, not a property of HEEDB: zero of the 954 survivors appear in the
extracted condition table, while the source table on S3 covers the whole database. Re-extracting
`condition_occurrence` against all 2,473 morphology patients — decedents and survivors alike — takes about
twenty minutes and gives every one of them a **measured** aetiology.

That matters beyond fixing one sentence. **L3 — "every patient has an ascertained death; the outcome is how
soon, not whether" — has bounded every claim in this project.** For the aetiology work it was never a property
of the data; it was a property of an extraction. This is the first analysis in the programme that can compare
death against genuine survival with aetiology known on both sides.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the new extraction was joined to any outcome.

  V1  SANITY, and it gates everything below. The survivors must actually have diagnoses in the re-extracted
      table. Report how many of the 954 acquire an aetiology label and what fraction are anoxic.
      If they remain unlabelled the re-extraction failed and nothing below is interpretable.

  V2  PRIMARY. With aetiology MEASURED for everyone and survivors included, intra-burst 8–30 Hz content still
      ranks 30-day death in opposite directions: anoxic above 0.5, non-anoxic below, both intervals excluding
      it.
      **FALSIFIED IF the reversal weakens once the assumed labels are replaced by measured ones** — which is a
      live possibility, because some of the 954 assumed-non-anoxic survivors will turn out to be anoxic, and
      they are exactly the patients whose misassignment would have flattered R393.

  V3  THE COMPARISON THAT MAKES V2 INTERPRETABLE. Report three cohorts side by side on identical code:
        (a) decedents only, measured aetiology          — the R390 cohort
        (b) all patients, aetiology ASSUMED for the unlabelled — the R393 cohort, reproduced
        (c) all patients, aetiology MEASURED             — the corrected analysis
      If (b) and (c) agree, R393's assumption was harmless and should be recorded as such. If they differ,
      (c) supersedes it and the ledger must say so.

  V4  WHAT THE SURVIVORS ADD. Among the newly-labelled survivors specifically, does the reversal hold? They
      are a genuinely new population for this analysis — not decedents scored by time-to-death — so this is
      the closest thing to an out-of-sample test the dataset allows.

NOTE ON WHAT IS STILL NOT FIXED. This lifts L3 for the aetiology analyses only. It does not address the lead's
open weakness — external replication — which needs a mixed-aetiology cohort that does not exist among the data
available here.
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import auc
from heedb_bs_ascertainment import AETIOLOGY, norm

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP_OLD = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_NEW = os.environ.get("OMOP_V2", "/tmp/eeg_probe/heedb_omop_v2")
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


def anoxic_from(path):
    """{pid: bool} from a condition_occurrence extract; presence in the dict means aetiology is KNOWN."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            out.setdefault(p, False)
            c = norm(r.get("condition_source_value"))
            if c and any(c.startswith(x) for x in AETIOLOGY["anoxic"]):
                out[p] = True
    return out


def auc_ci(y, s, rng, reps):
    n = len(y); o = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            a = auc(y[i], s[i])
            if a == a:
                o.append(a)
    if len(o) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(o, [2.5, 97.5]))


def arm(label, y, a, ax, rng):
    res = {}
    print(f"\n   --- {label} ---")
    for nm, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        k = int(m.sum())
        if k < 60 or not (0 < y[m].sum() < k):
            print(f"      {nm:<11} n={k:>5}  too few")
            return None
        A = auc(y[m], a[m]); lo, hi = auc_ci(y[m], a[m], rng, NBOOT)
        res[nm] = (A, lo, hi)
        print(f"      {nm:<11} n={k:>5}  30-d death {100*y[m].mean():5.1f}%  AUC {A:.3f} [{lo:.3f},{hi:.3f}]"
              f"  {'-> MORE death' if A > 0.5 else '-> LESS death'}")
    an, no = res["anoxic"], res["non-anoxic"]
    strict = an[1] > 0.5 and no[2] < 0.5
    print(f"      gap {an[0]-no[0]:+.3f}   "
          f"{'REVERSAL, both intervals exclude 0.5' if strict else 'directional only — an interval spans 0.5'}")
    return res


def main():
    rng = np.random.default_rng(20260727)
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
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            p = int(p)
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
    assert ab, "morphology table empty"

    old = anoxic_from(f"{OMOP_OLD}/condition_occurrence.csv")
    new = anoxic_from(f"{OMOP_NEW}/condition_occurrence.csv")
    assert new, f"{OMOP_NEW}/condition_occurrence.csv missing or empty — run the re-extraction first"

    rows = []
    for p, v in ab.items():
        if p not in when:
            continue
        d = death.get(p)
        if d is not None and (d - when[p]).days < -1:
            continue
        rows.append((p, 1.0 if (d is not None and (d - when[p]).days <= 30) else 0.0, v, d is not None))
    assert len(rows) >= 400, f"only {len(rows)} patients"
    pid = np.array([r[0] for r in rows]); y = np.array([r[1] for r in rows])
    a = np.array([r[2] for r in rows]); dead = np.array([r[3] for r in rows])

    # ---- V1 -----------------------------------------------------------------------------------------
    print("=" * 96)
    print("V1  SANITY -- did the re-extraction actually give the survivors an aetiology?")
    print("=" * 96)
    surv = ~dead
    known_old = np.array([p in old for p in pid])
    known_new = np.array([p in new for p in pid])
    print(f"   morphology patients analysed: {len(pid):,}   survivors (no death record): {int(surv.sum()):,}")
    print(f"   aetiology KNOWN, old extract: {int(known_old.sum()):,}  "
          f"(of survivors: {int((known_old & surv).sum()):,})")
    print(f"   aetiology KNOWN, new extract: {int(known_new.sum()):,}  "
          f"(of survivors: {int((known_new & surv).sum()):,})")
    gained = int((known_new & surv).sum())
    if gained < 100:
        print("   *** V1 FAILED — the survivors still have no aetiology. Nothing below is interpretable.")
        return 1
    ax_new = np.array([1.0 if new.get(p) else 0.0 for p in pid])
    print(f"   newly labelled survivors: {gained:,}, of whom anoxic {100*ax_new[known_new & surv].mean():.1f}%"
          f"   (decedents are {100*ax_new[known_new & dead].mean():.1f}% anoxic)")

    # ---- V3 (three cohorts on identical code) --------------------------------------------------------
    print("\n" + "=" * 96)
    print("V2 / V3  THREE COHORTS, IDENTICAL CODE")
    print("=" * 96)
    ax_assumed = np.array([1.0 if old.get(p) else 0.0 for p in pid])   # unlabelled -> non-anoxic (R393)
    m_dec_known = dead & known_old
    arm("(a) decedents only, measured aetiology  [the R390 cohort]",
        y[m_dec_known], a[m_dec_known], ax_assumed[m_dec_known], rng)
    arm("(b) all patients, aetiology ASSUMED for the unlabelled  [the R393 cohort]",
        y, a, ax_assumed, rng)
    r_c = arm("(c) all patients, aetiology MEASURED  [the corrected analysis]",
              y[known_new], a[known_new], ax_new[known_new], rng)

    # ---- V4 -----------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("V4  THE SURVIVORS ALONE -- a genuinely new population for this analysis")
    print("=" * 96)
    m = known_new & surv
    if int(m.sum()) >= 120 and 0 < y[m].sum() < int(m.sum()):
        arm("survivors only (no death record), measured aetiology", y[m], a[m], ax_new[m], rng)
    else:
        print(f"   n={int(m.sum())} with {int(y[m].sum())} events — too few, or no outcome variation among")
        print("   patients with no death record (expected: their 30-day death is 0 by construction).")
        print("   The survivors therefore cannot be scored on their own; they contribute to (c) as the")
        print("   non-events that (a) structurally lacked, which is the point of the correction.")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    if r_c:
        an, no = r_c["anoxic"], r_c["non-anoxic"]
        ok = an[1] > 0.5 and no[2] < 0.5
        print(f"   V2 {'CONFIRMED — the reversal survives replacing assumed labels with measured ones' if ok else 'NOT CONFIRMED on measured labels — (c) supersedes R393 and the ledger must say so'}")
    print("   L3 is lifted for the aetiology analyses: the decedents-only restriction was an extraction")
    print("   artefact, not a property of HEEDB. It is NOT lifted for anything requiring the outcome to be")
    print("   ascertained rather than assumed absent, and it does not touch external replication.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
