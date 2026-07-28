#!/usr/bin/env python3
"""Was a sedative infusion actually RUNNING when the EEG was recorded? A proper test of drug-induced suppression.

WHY RASS COULD NOT ANSWER THIS. The previous attempt used the RASS score nearest the EEG as a measure of
sedation depth. That instrument is circular: RASS grades RESPONSIVENESS, and burst suppression CAUSES
unresponsiveness, so "RASS <= -4" is partly the exposure being studied rather than a measure of drug exposure.
The symptom of the circularity was visible in the output -- post-anoxic burst-suppression patients scored MORE
deeply sedated (82.8 % at RASS <= -4) than septic ones (61.1 %), the reverse of what a drug-dilution account
predicts, and restricting to RASS > -4 collapsed every aetiology's effect by roughly 80 % because it selects the
strange subgroup labelled burst-suppressed while remaining arousable.

THE RIGHT INSTRUMENT, which was available all along. drug_sedatives carries both
drug_exposure_start_datetime AND drug_exposure_end_datetime, so an administration can be tested for whether it
was ACTIVE at the moment of the recording rather than merely present somewhere in the admission. That is a
measure of the drug, not of the patient's response to it, and it cannot be caused by the EEG finding.

  ACTIVE   = a burst-suppression-capable agent (propofol, midazolam, the barbiturates) whose interval spans the
             EEG time, or which started within 4 h before it
  ABSENT   = no such agent active in that window, though the patient may have received one at other times

REGISTERED PREDICTIONS.
  I1  Among burst-suppression patients, an active infusion is MORE common in septic than in post-anoxic
      patients. Post-arrest protocols wean sedation before prognostication; septic ICU care does not.
      FALSIFIED IF the proportion is equal or higher in anoxic patients.
  I2  Burst suppression WITHOUT an active infusion -- a cortex suppressing with no drug running to explain it --
      carries a larger mortality effect than burst suppression WITH one, in every aetiology.
      FALSIFIED IF the no-infusion effect is not larger.
  I3  THE MECHANISM TEST. Restricting to patients with NO active infusion should NARROW the anoxic-versus-septic
      gap by at least 30 %, because the septic estimate is the one diluted by drug-induced suppression.
      FALSIFIED IF the gap narrows by less than 30 %, or widens. The threshold is a fraction, not a significance
      test, because significance-only criteria have passed three times in this project on trivial effects.

WHAT THIS STILL CANNOT DO. Active infusion is not randomised, and it marks sicker, more intensively managed
patients -- the H2 test earlier in this project failed exactly that way, with peri-EEG anaesthetic exposure
predicting death at +31 pp in the wrong direction because it was a severity proxy. So a confirmation of I3 is
evidence that drug-induced suppression dilutes the septic estimate, not proof, and the direction of the severity
confound works AGAINST I3 rather than for it, which is the useful way round.
"""
import csv, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "800"))
LEAD_H = float(os.environ.get("LEAD_H", "4"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
BS_CAPABLE = ("propofol", "midazolam", "pentobarbital", "thiopental", "phenobarbital")
AE = ("anoxic", "sepsis", "metabolic", "structural", "status")


def main():
    rng = np.random.default_rng(20260726)

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

    active, seen_drug = set(), set()
    sed = f"{OMOP}/drug_sedatives.csv"
    if not os.path.exists(sed):
        print(f"*** {sed} missing"); return 1
    for r in csv.DictReader(open(sed)):
        v = (r.get("drug_source_value") or "").lower()
        if not any(x in v for x in BS_CAPABLE):
            continue
        try:
            p = int(r["person_id"])
        except Exception:
            continue
        seen_drug.add(p)
        t0 = when.get(p)
        if t0 is None:
            continue
        s = dt(r.get("drug_exposure_start_datetime"))
        e = dt(r.get("drug_exposure_end_datetime"))
        if s is None:
            continue
        # active if the interval spans the EEG, or it started shortly before it
        if e is not None and s <= t0 <= e:
            active.add(p)
        elif -LEAD_H * 3600 <= (t0 - s).total_seconds() <= LEAD_H * 3600:
            active.add(p)
    print(f"patients with any BS-capable sedative record: {len(seen_drug):,}; "
          f"with one ACTIVE at the EEG: {len(active):,}")

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen or p not in seen_drug:
            continue                      # require drug data, else 'no infusion' conflates with 'not extracted'
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        rows.append(dict(d30=1.0 if days <= 30 else 0.0, bs=1.0 if bs.get(p) else 0.0,
                         act=1.0 if p in active else 0.0, labs=aet.get(p, set())))
    n = len(rows)
    print(f"cohort with drug data: {n:,}")
    if n < 500:
        print("*** insufficient; the sedative extraction may still be running"); return 1

    # ---- I1 ------------------------------------------------------------------------------------------
    print("\n" + "=" * 88)
    print("I1  IS AN INFUSION RUNNING MORE OFTEN IN SEPTIC THAN POST-ANOXIC SUPPRESSION?")
    print("=" * 88)
    print(f"   {'aetiology':12s} {'BS+ n':>7s} {'BS+ active':>12s} {'BS- n':>7s} {'BS- active':>12s}")
    prop = {}
    for k in AE:
        g1 = [r for r in rows if k in r["labs"] and r["bs"] == 1.0]
        g0 = [r for r in rows if k in r["labs"] and r["bs"] == 0.0]
        if len(g1) < 30 or len(g0) < 30:
            continue
        prop[k] = float(np.mean([r["act"] for r in g1]))
        print(f"   {k:12s} {len(g1):7d} {100*prop[k]:11.1f}% {len(g0):7d} "
              f"{100*np.mean([r['act'] for r in g0]):11.1f}%")
    if "anoxic" in prop and "sepsis" in prop:
        print(f"\n   I1 {'CONFIRMED' if prop['sepsis'] > prop['anoxic'] else 'FALSIFIED'} "
              f"(sepsis {100*prop['sepsis']:.1f}% vs anoxic {100*prop['anoxic']:.1f}%)")

    # ---- I2 / I3 -------------------------------------------------------------------------------------
    def effects(R):
        out = {}
        for k in AE:
            g = [r for r in R if k in r["labs"]]
            vals = []
            for av in (0.0, 1.0):
                h = [r for r in g if r["act"] == av]
                a = [r["d30"] for r in h if r["bs"] == 1.0]
                b = [r["d30"] for r in h if r["bs"] == 0.0]
                if len(a) < 20 or len(b) < 20:
                    vals = None; break
                vals.append(float(np.mean(a) - np.mean(b)))
            if vals:
                out[k] = vals            # [no infusion, infusion]
        return out

    print("\n" + "=" * 88)
    print("I2/I3  BURST-SUPPRESSION EFFECT, BY WHETHER A DRUG WAS RUNNING")
    print("=" * 88)
    obs = effects(rows)
    print(f"   {'aetiology':12s} {'no infusion':>14s} {'infusion active':>17s} {'difference':>12s}")
    for k in AE:
        if k not in obs:
            continue
        print(f"   {k:12s} {100*obs[k][0]:+13.2f} {100*obs[k][1]:+16.2f} "
              f"{100*(obs[k][0]-obs[k][1]):+11.2f}")
    bigger = sum(1 for k in obs if obs[k][0] > obs[k][1])
    print(f"   I2 {'CONFIRMED' if bigger == len(obs) else 'PARTIAL' if bigger else 'FALSIFIED'} "
          f"({bigger}/{len(obs)} aetiologies show a larger effect without an infusion)")

    if "anoxic" in obs and "sepsis" in obs:
        gap_all = obs["anoxic"][0] * 0 + 0  # placeholder replaced below
        # gap using everyone, and gap restricted to no-active-infusion patients
        def gap(R, restrict):
            S = [r for r in R if (r["act"] == 0.0)] if restrict else R
            o = {}
            for k in ("anoxic", "sepsis"):
                g = [r for r in S if k in r["labs"]]
                a = [r["d30"] for r in g if r["bs"] == 1.0]
                b = [r["d30"] for r in g if r["bs"] == 0.0]
                if len(a) < 20 or len(b) < 20:
                    return None
                o[k] = float(np.mean(a) - np.mean(b))
            return o["anoxic"] - o["sepsis"]
        g_all, g_off = gap(rows, False), gap(rows, True)
        bd = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            R = [rows[j] for j in i]
            a, b = gap(R, False), gap(R, True)
            if a is not None and b is not None:
                bd.append(a - b)
        lo, hi = np.percentile(bd, [2.5, 97.5]) if bd else (float("nan"),) * 2
        frac = (g_all - g_off) / g_all if g_all and abs(g_all) > 1e-9 else float("nan")
        print(f"\n   anoxic-minus-septic gap, everyone            : {100*g_all:+.2f} pp")
        print(f"   anoxic-minus-septic gap, no active infusion  : {100*g_off:+.2f} pp")
        print(f"   narrowing {100*(g_all-g_off):+.2f} pp [{100*lo:+.2f},{100*hi:+.2f}]  = {100*frac:.1f} %")
        print(f"   I3 {'CONFIRMED' if (frac >= 0.30 and lo > 0) else 'FALSIFIED'} "
              f"(registered threshold: 30 %)")

    print("\n   Active infusion is not randomised and marks more intensively managed patients. That confound")
    print("   works AGAINST I3 rather than for it, which is the useful direction, but a confirmation remains")
    print("   evidence rather than proof.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
