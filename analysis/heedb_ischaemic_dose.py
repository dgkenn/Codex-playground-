#!/usr/bin/env python3
"""WHY does suppression burden stratify risk within post-anoxic patients? Brain-specific, or whole-body dose?

THE FINDING THIS INTERROGATES. Within the guideline's highly-malignant category, measured suppression burden
stratifies three-day death from 24.7 % to 66.4 % across quintiles and thirty-day death from 52.3 % to 93.1 %,
adding +0.093 cross-validated AUC over the category itself. That is established. WHY it works is not, and two
mechanisms fit everything observed so far:

  BRAIN-SPECIFIC DOSIMETER. Burden measures how much cortex died. The EEG is reporting on the organ that will
  determine the outcome, and nothing else follows from it.

  GLOBAL ISCHAEMIC DOSE. Cardiac arrest is whole-body ischaemia-reperfusion. Longer downtime damages kidney,
  liver, gut and myocardium as well as cortex, so burden is a proxy for total ischaemic dose and the EEG is
  merely its most visible readout. On this account the brain is the DISPLAY, not the cause.

These are not distinguishable from mortality alone, because both predict that higher burden means earlier death.
They differ sharply on a question mortality cannot answer: whether burden tracks injury to organs the EEG cannot
see.

  D1  Within post-anoxic patients, higher suppression burden is associated with more NON-NEUROLOGICAL organ
      injury -- acute kidney injury, hepatic injury, and shock requiring vasopressors.
      GLOBAL DOSE PREDICTS a clear gradient across burden quintiles.
      BRAIN-SPECIFIC PREDICTS little or none, because on that account burden says nothing about other organs.
      FALSIFIED (for global dose) IF the gradient across quintiles is flat or non-monotone.

  D2  SPECIFICITY BY CONTRAST. The same gradient should be ABSENT, or much weaker, in septic patients -- where
      suppression is not produced by a global ischaemic event and therefore should not index one. Sepsis also
      causes organ failure, so the test is not whether organ injury occurs but whether it TRACKS SUPPRESSION
      BURDEN the way it should if burden is a dose marker.
      FALSIFIED IF the burden-to-organ-injury gradient is as steep in sepsis as in anoxia.

  D3  MEDIATION, tested honestly and expected to be partial at most. If burden predicts death only because it
      indexes multi-organ injury, then conditioning on organ injury should attenuate the burden-mortality
      relationship substantially.
      Reported as the fraction of the burden coefficient absorbed. A fraction below 25 % means multi-organ
      injury is NOT how burden kills, whatever D1 shows.

WHY THIS IS WORTH RUNNING RATHER THAN ASSUMING. The two accounts have different clinical implications. If burden
is a brain-specific dosimeter, it belongs in neuroprognostication and nothing else. If it is a whole-body dose
marker, then a suppressed EEG after arrest is also a statement about the kidneys, and the right response is
systemic rather than neurological. The data can tell these apart and nobody has asked it to.

LIMITS. Diagnosis codes are a coarse instrument for organ injury and their timing is unreliable, so only codes
dated AFTER the index EEG are counted -- a pre-existing kidney problem says nothing about this arrest. Vasopressor
exposure is a better-timed marker but marks intensity of care as well as severity of shock.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "600"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"

ORGAN = {
    "aki":     ("N17", "5845", "5846", "5847", "5848", "5849"),
    "hepatic": ("K72", "5722", "5728", "K769", "7940"),
    "cardiac": ("I21", "410", "I469", "I462", "I472", "4275"),
}
PRESSORS = ("norepinephrine", "levophed", "epinephrine", "vasopressin", "phenylephrine",
            "neosynephrine", "dopamine", "dobutamine")


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


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

    # aetiology, plus organ-injury codes dated AFTER the index EEG
    aet, cond_seen = defaultdict(set), set()
    organ = defaultdict(set)
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
            t0 = when.get(p)
            if t0 is None:
                continue
            t = dt(r.get("condition_start_datetime"))
            if t is None or t < t0:
                continue                      # only injury dated after the recording
            for lab, pre in ORGAN.items():
                if any(c.startswith(x) for x in pre):
                    organ[p].add(lab)

    # vasopressor exposure after the EEG
    pressor, pressor_seen = set(), set()
    vf = f"{OMOP}/drug_vasopressors.csv"
    if os.path.exists(vf):
        for r in csv.DictReader(open(vf)):
            v = (r.get("drug_source_value") or "").lower()
            if not any(x in v for x in PRESSORS):
                continue
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            pressor_seen.add(p)
            t0 = when.get(p)
            s = dt(r.get("drug_exposure_start_datetime"))
            if t0 is None or s is None:
                continue
            if 0 <= (s - t0).total_seconds() <= 7 * 86400:
                pressor.add(p)
        print(f"patients with any vasopressor record: {len(pressor_seen):,}; "
              f"with one started within 7 days after the EEG: {len(pressor):,}")
    else:
        print("*** vasopressor extraction not present; D1 runs on diagnosis codes only")

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen or p not in burden or not bs.get(p):
            continue
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        rows.append(dict(pid=p, bur=burden[p], days=float(days),
                         d3=1.0 if days <= 3 else 0.0, d30=1.0 if days <= 30 else 0.0,
                         aki=1.0 if "aki" in organ.get(p, set()) else 0.0,
                         hep=1.0 if "hepatic" in organ.get(p, set()) else 0.0,
                         card=1.0 if "cardiac" in organ.get(p, set()) else 0.0,
                         press=1.0 if p in pressor else 0.0,
                         has_drug=1.0 if p in pressor_seen else 0.0,
                         labs=aet.get(p, set())))
    print(f"burst-suppression patients with a measured burden: {len(rows):,}")

    # ---- D1 / D2 -------------------------------------------------------------------------------------
    for k in ("anoxic", "sepsis"):
        g = [r for r in rows if k in r["labs"]]
        if len(g) < 200:
            continue
        print("\n" + "=" * 92)
        print(f"D1/D2  {k.upper()}: does NON-NEUROLOGICAL organ injury track suppression burden?")
        print("=" * 92)
        b = np.array([r["bur"] for r in g])
        q = np.percentile(b, [20, 40, 60, 80])
        sels = [("Q1 lowest", b <= q[0]), ("Q2", (b > q[0]) & (b <= q[1])),
                ("Q3", (b > q[1]) & (b <= q[2])), ("Q4", (b > q[2]) & (b <= q[3])),
                ("Q5 highest", b > q[3])]
        gp = [r for r in g if r["has_drug"] == 1.0]
        print(f"   {'burden quintile':18s} {'n':>5s} {'AKI':>8s} {'hepatic':>9s} {'cardiac':>9s} "
              f"{'pressor<=7d':>12s} {'3-day death':>12s}")
        for lab, sel in sels:
            if sel.sum() < 15:
                continue
            sub = [r for r, s in zip(g, sel) if s]
            subp = [r for r in sub if r["has_drug"] == 1.0]
            pv = f"{100*np.mean([r['press'] for r in subp]):11.1f}%" if len(subp) >= 10 else "        n/a"
            print(f"   {lab:18s} {len(sub):5d} {100*np.mean([r['aki'] for r in sub]):7.1f}% "
                  f"{100*np.mean([r['hep'] for r in sub]):8.1f}% "
                  f"{100*np.mean([r['card'] for r in sub]):8.1f}% {pv} "
                  f"{100*np.mean([r['d3'] for r in sub]):11.1f}%")
        # slope of each organ marker on burden
        print(f"   slopes on burden (pp per unit burden):")
        for oc in ("aki", "hep", "card", "press"):
            sub = gp if oc == "press" else g
            if len(sub) < 150:
                continue
            x = np.array([r["bur"] for r in sub]); y = np.array([r[oc] for r in sub])
            X = np.column_stack([np.ones(len(x)), x])
            b0 = float(lpm(X, y)[1])
            bt = []
            for _ in range(NBOOT):
                i = rng.integers(0, len(x), len(x))
                try:
                    bt.append(float(lpm(X[i], y[i])[1]))
                except Exception:
                    continue
            lo, hi = np.percentile(bt, [2.5, 97.5])
            print(f"      {oc:6s} {100*b0:+7.2f} pp [{100*lo:+7.2f},{100*hi:+7.2f}] "
                  f"{'*' if (lo > 0 or hi < 0) else 'ns'}  (n={len(sub)})")

    # ---- D3: does organ injury mediate burden -> death? ---------------------------------------------
    print("\n" + "=" * 92)
    print("D3  DOES MULTI-ORGAN INJURY EXPLAIN HOW BURDEN KILLS?  (post-anoxic patients)")
    print("=" * 92)
    ga = [r for r in rows if "anoxic" in r["labs"]]
    if len(ga) >= 300:
        y = np.array([r["d3"] for r in ga])
        x = np.array([r["bur"] for r in ga])
        X1 = np.column_stack([np.ones(len(ga)), x])
        X2 = np.column_stack([X1] + [np.array([r[o] for r in ga]) for o in ("aki", "hep", "card")])
        b1, b2 = float(lpm(X1, y)[1]), float(lpm(X2, y)[1])
        d = []
        for _ in range(NBOOT):
            i = rng.integers(0, len(ga), len(ga))
            try:
                d.append(float(lpm(X1[i], y[i])[1]) - float(lpm(X2[i], y[i])[1]))
            except Exception:
                continue
        lo, hi = np.percentile(d, [2.5, 97.5])
        frac = (b1 - b2) / b1 if abs(b1) > 1e-9 else float("nan")
        print(f"   burden -> 3-day death, unadjusted        {100*b1:+.2f} pp per unit")
        print(f"   adjusted for AKI, hepatic, cardiac injury {100*b2:+.2f} pp per unit")
        print(f"   absorbed {100*frac:.1f} %  (attenuation {100*(b1-b2):+.2f} pp "
              f"[{100*lo:+.2f},{100*hi:+.2f}])")
        print(f"   D3: multi-organ injury is {'a substantial' if frac >= 0.25 else 'NOT a substantial'} "
              f"part of how burden kills (threshold 25 %)")

    print("\n   Diagnosis codes are coarse and their dating unreliable, so only codes dated AFTER the index")
    print("   recording are counted. Vasopressor exposure is better timed but marks intensity of care as well")
    print("   as severity of shock, and patients without any drug record are excluded from that column rather")
    print("   than counted as unexposed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
