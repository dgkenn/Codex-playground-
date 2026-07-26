#!/usr/bin/env python3
"""Is the three-day death mass WITHDRAWAL or REFRACTORY SHOCK? Vasopressor discontinuation as the instrument.

THE QUESTION, and why it is the last major one. The entire aetiology effect lives in a fixed subgroup that dies
early: 40.6 % of post-anoxic burst-suppression patients are dead within three days, the excess is exhausted
among 30-day survivors, and measured burden stratifies that early mortality from 24.7 % to 66.4 %. Everything
now rests on what those early deaths ARE. Two possibilities, with opposite implications:

  REFRACTORY SHOCK -- the patient dies despite escalating support. Vasopressors are RUNNING at the moment of
  death. The EEG is describing a patient who was dying anyway, and burden is prognostic information.

  WITHDRAWAL -- support is deliberately stopped and death follows within hours. Vasopressors END shortly BEFORE
  death, in a tight cluster. Burst suppression is a guideline criterion for exactly this decision, so the EEG
  may be partly causing the outcome it predicts.

Earlier attempts at this failed on the instrument. DNR and palliative-care codes proved a blunt proxy -- median
42 days from code to death, only 5 % dying within a day -- because they document chronic care-limitation status
rather than an acute decision. Stopping a vasopressor in a pressor-dependent patient is followed by death within
hours, so the DISCONTINUATION TIME is a far sharper marker, and drug_exposure carries the end datetime.

  W1  Among post-anoxic burst-suppression patients who die within three days AND were on vasopressors, the
      interval from last vasopressor end to death is SHORT and tightly clustered -- the withdrawal signature.
      Reported as the fraction dying within 6 h and within 24 h of the last pressor ending.
  W2  SPECIFICITY. That signature should be STRONGER in post-anoxic burst-suppression patients than in septic
      ones, because burst suppression is a withdrawal criterion after arrest and is not one in sepsis.
      FALSIFIED IF the signature is equally strong in sepsis.
  W3  DOSE. If withdrawal is driving the burden gradient, the withdrawal signature should be commoner at HIGH
      burden -- clinicians act on a more suppressed EEG. If burden predicts death independently of the decision,
      the signature should be flat across burden and the gradient must come from somewhere else.
      This is the one that matters most: it asks whether the burden-mortality relationship this project has
      built its main result on is mediated by a clinical decision.

INTERPRETATION, fixed in advance so it cannot drift. A strong withdrawal signature does NOT invalidate the
finding -- burst suppression would still identify the patients who die, and the information is still in the
recording. It changes what the finding IS: a description of how the EEG is currently ACTED ON rather than of how
these brains behave. Both are reportable; conflating them is not.

LIMITS. Vasopressor discontinuation marks a decision to stop escalating, not necessarily a formal withdrawal of
care, and patients can be weaned because they improved. Restricting to patients who then died within a short
window removes most of that ambiguity but not all of it. Patients never on vasopressors are excluded rather than
counted as not-withdrawn.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "600"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
PRESSORS = ("norepinephrine", "levophed", "epinephrine", "vasopressin", "phenylephrine",
            "neosynephrine", "dopamine", "dobutamine")


def main():
    rng = np.random.default_rng(20260726)

    burden = {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, v = int(r["patient"]), float(r["burden"])
            except Exception:
                continue
            if v == v:
                burden[p] = max(burden.get(p, 0.0), v)

    aet, cond_seen = defaultdict(set), set()
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            cond_seen.add(p)
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
            except Exception:
                pass

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when, bs = {}, {}
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
            if t is None:
                continue
            if p not in when or t < when[p]:
                when[p] = t
            bs[p] = bs.get(p, False) or ((r.get("bs") or "").strip() not in ("", "None", "nan"))

    # last vasopressor END before death, and whether one spanned the death time
    last_end, spanned, seen = {}, set(), set()
    with open(f"{OMOP}/drug_vasopressors.csv") as fh:
        for r in csv.DictReader(fh):
            v = (r.get("drug_source_value") or "").lower()
            if not any(x in v for x in PRESSORS):
                continue
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            seen.add(p)
            d = death.get(p)
            if d is None:
                continue
            s = dt(r.get("drug_exposure_start_datetime"))
            e = dt(r.get("drug_exposure_end_datetime"))
            if e is not None and e <= d:
                if p not in last_end or e > last_end[p]:
                    last_end[p] = e
            if s is not None and e is not None and s <= d <= e:
                spanned.add(p)
    print(f"patients with a vasopressor record: {len(seen):,}")

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen or p not in seen:
            continue
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        gap_h = ((d - last_end[p]).total_seconds() / 3600.0) if p in last_end else float("nan")
        rows.append(dict(pid=p, days=float(days), d3=1.0 if days <= 3 else 0.0,
                         bs=1.0 if bs.get(p) else 0.0, gap_h=gap_h,
                         span=1.0 if p in spanned else 0.0,
                         bur=burden.get(p, float("nan")), labs=aet.get(p, set())))
    n = len(rows)
    print(f"analysable (EEG, ascertained death, vasopressor record): {n:,}")

    def sig(g):
        """withdrawal signature among a group: fraction dying soon after the last pressor ended."""
        h = [r["gap_h"] for r in g if r["gap_h"] == r["gap_h"] and r["gap_h"] >= 0]
        if len(h) < 25:
            return None
        h = np.array(h)
        return (len(h), float(np.mean(h <= 6)), float(np.mean(h <= 24)), float(np.median(h)),
                float(np.mean([r["span"] for r in g])))

    print("\n" + "=" * 96)
    print("W1/W2  AMONG PATIENTS DYING WITHIN 3 DAYS: was support stopped, or running at death?")
    print("=" * 96)
    print(f"   {'group':26s} {'n':>5s} {'died <=6h after':>16s} {'<=24h':>8s} "
          f"{'median h':>9s} {'pressor running':>16s}")
    for k in ("anoxic", "sepsis", "metabolic", "structural"):
        for bv, nm in ((1.0, "BS+"), (0.0, "BS-")):
            g = [r for r in rows if k in r["labs"] and r["bs"] == bv and r["d3"] == 1.0]
            s = sig(g)
            if s is None:
                continue
            print(f"   {k+' '+nm+' (died<=3d)':26s} {s[0]:5d} {100*s[1]:15.1f}% {100*s[2]:7.1f}% "
                  f"{s[3]:8.1f} {100*s[4]:15.1f}%")
    print("\n   A withdrawal signature is a high fraction dying within hours of the last pressor ending.")
    print("   Refractory shock instead shows a pressor still RUNNING at the moment of death.")

    # ---- W3: does the signature track burden? -------------------------------------------------------
    print("\n" + "=" * 96)
    print("W3  DOES THE WITHDRAWAL SIGNATURE TRACK BURDEN?  (post-anoxic burst suppression, died <=3 d)")
    print("=" * 96)
    ga = [r for r in rows if "anoxic" in r["labs"] and r["bs"] == 1.0 and r["d3"] == 1.0
          and r["bur"] == r["bur"]]
    print(f"   n={len(ga):,}")
    if len(ga) >= 120:
        b = np.array([r["bur"] for r in ga])
        q = np.percentile(b, [33, 67])
        print(f"   {'burden tertile':18s} {'n':>5s} {'died <=6h after':>16s} {'<=24h':>8s} "
              f"{'pressor running':>16s}")
        for lab, sel in (("low", b <= q[0]), ("mid", (b > q[0]) & (b <= q[1])), ("high", b > q[1])):
            s = sig([r for r, x in zip(ga, sel) if x])
            if s:
                print(f"   {lab:18s} {s[0]:5d} {100*s[1]:15.1f}% {100*s[2]:7.1f}% {100*s[4]:15.1f}%")
        print("\n   If the signature RISES with burden, the burden-mortality gradient is at least partly")
        print("   mediated by a clinical decision. If it is FLAT, the gradient is not explained by withdrawal")
        print("   and burden is carrying information independent of what was done.")

    # ---- the same, for all post-anoxic BS+ regardless of when they died ------------------------------
    print("\n" + "=" * 96)
    print("CONTEXT  all post-anoxic burst-suppression patients on vasopressors, by burden tertile")
    print("=" * 96)
    gb = [r for r in rows if "anoxic" in r["labs"] and r["bs"] == 1.0 and r["bur"] == r["bur"]]
    if len(gb) >= 150:
        b = np.array([r["bur"] for r in gb])
        q = np.percentile(b, [33, 67])
        print(f"   {'burden tertile':18s} {'n':>5s} {'3-day death':>12s} {'pressor running at death':>26s}")
        for lab, sel in (("low", b <= q[0]), ("mid", (b > q[0]) & (b <= q[1])), ("high", b > q[1])):
            sub = [r for r, x in zip(gb, sel) if x]
            if len(sub) >= 25:
                print(f"   {lab:18s} {len(sub):5d} {100*np.mean([r['d3'] for r in sub]):11.1f}% "
                      f"{100*np.mean([r['span'] for r in sub]):25.1f}%")

    print("\n   A strong withdrawal signature would NOT invalidate the finding -- burst suppression would still")
    print("   identify the patients who die, and the information would still be in the recording. It changes")
    print("   what the finding IS: a description of how the EEG is currently acted on rather than of how these")
    print("   brains behave. Vasopressor discontinuation also marks weaning after improvement, which restricting")
    print("   to patients who then died removes most but not all of.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
