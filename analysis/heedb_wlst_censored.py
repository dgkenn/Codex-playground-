#!/usr/bin/env python3
"""Bound the withdrawal contribution: the aetiology interaction with and without censoring at the WLST decision.

WHY. Section 6c of docs/research/39_HEEDB_FINDINGS.md showed that roughly half the burst-suppression x aetiology
interaction sits in the first week after the EEG, where withdrawal of life-sustaining therapy and genuine early
mortality are inseparable. A day-7 landmark is a blunt instrument for that problem. The field has a recommended
one:

  Elmer J, et al. "Time to Awakening and Self-Fulfilling Prophecies After Cardiac Arrest." Crit Care Med 2023
  (PMID 36752628), verified verbatim from the MEDLINE record:
      "Compared with traditional binary outcome prediction, censoring outcomes after WLST-N may reduce potential
       for bias and self-fulfilling prophecies."

We can implement it because the DNR / palliative-care codes carry condition_start_datetime, so the care-limitation
decision has a DATE, not merely a presence.

THE ESTIMAND, and why two analyses are reported rather than one.
  UNCENSORED  Death after withdrawal is counted as the outcome. If the EEG drove the withdrawal, the EEG partly
              caused the death being used to validate it. This OVERSTATES the interaction. -> UPPER bound.
  WLST-CENSORED  Follow-up ends at the withdrawal decision. This assumes a withdrawn patient would thereafter
              have followed the same hazard as a similar patient not withdrawn. Withdrawn patients are sicker
              than that, so this UNDERSTATES the death rate. -> LOWER bound.
  Neither is the truth. Together they BRACKET it, and the width of the bracket is the honest measure of how much
  of this finding rests on clinical behaviour. Reporting one number here would be a choice about which bias to
  hide.

METHOD. Kaplan-Meier per aetiology x burst-suppression stratum, read at 30 days; non-parametric, so no
proportional-hazards assumption is imposed. The interaction for an aetiology is
    (30-day cumulative death | BS+) - (30-day cumulative death | BS-)
and the reported statistic is the spread of those interactions across aetiologies -- the same statistic as the
linear-probability analysis, so the two are directly comparable. Patient-level bootstrap for intervals.

CAVEAT THAT DOES NOT GO AWAY. This cohort is restricted to patients with an ascertained death (the
ascertainment-immune design used throughout this project), so these are not general survival curves: they
describe how SOON death came among people who died. Censoring at WLST removes person-time after the decision;
it does not resurrect anyone. Also, a DNR or palliative-care code is a proxy for the withdrawal decision, not a
record of it -- a code may be entered late, or care may be limited without one.
"""
import csv, io, os, sys
from collections import defaultdict, Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "600"))
HORIZON = float(os.environ.get("HORIZON", "30"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
DNR_CODES = ("Z66", "Z515", "V4986", "V667")


def km_at(times, events, horizon):
    """Kaplan-Meier cumulative incidence of the event at `horizon`. times in days, events 1=death 0=censored."""
    if len(times) == 0:
        return float("nan")
    t = np.asarray(times, float); e = np.asarray(events, int)
    order = np.argsort(t, kind="mergesort")
    t, e = t[order], e[order]
    n = len(t); surv = 1.0; i = 0
    while i < n and t[i] <= horizon:
        tj = t[i]
        # everyone with time >= tj is still under observation just before tj
        at_risk = n - i
        d = 0
        while i < n and t[i] == tj:
            d += e[i]
            i += 1
        if at_risk > 0 and d > 0:
            surv *= (1.0 - d / at_risk)
    return float(1.0 - surv)


def main():
    rng = np.random.default_rng(20260726)

    aet, cond_seen = defaultdict(set), set()
    wlst = {}
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
            if any(c.startswith(x) for x in DNR_CODES):
                t = dt(r.get("condition_start_datetime"))
                if t is not None and (p not in wlst or t < wlst[p]):
                    wlst[p] = t

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
    for site in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{site}_EEG__reports_findings.csv"
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

    rows = []
    stats = Counter()
    for p, t0 in when.items():
        if p not in cond_seen:
            continue
        d = death.get(p)
        if d is None:
            continue
        dd = (d - t0).days
        if dd < -1:
            continue
        w = wlst.get(p)
        wd = (w - t0).days if w is not None else None
        if wd is not None and wd < 0:
            stats["care limit predates the EEG"] += 1
            wd = None          # the EEG cannot have driven a decision already made
        rows.append(dict(pid=p, bs=1.0 if bs.get(p) else 0.0, dday=float(dd),
                         wday=(float(wd) if wd is not None else None),
                         **{k: (1.0 if k in aet.get(p, set()) else 0.0) for k in AETIOLOGY}))
    n = len(rows)
    nbs = int(sum(r["bs"] for r in rows))
    nw = sum(1 for r in rows if r["wday"] is not None)
    print(f"cohort: {n:,} ({nbs:,} BS-positive)   with a dated care-limitation code after the EEG: {nw:,} "
          f"({100*nw/n:.1f} %)")
    print(f"   care limits predating the EEG (not treated as post-EEG decisions): "
          f"{stats['care limit predates the EEG']:,}")
    withdrawn_before_death = sum(1 for r in rows if r["wday"] is not None and r["wday"] < r["dday"])
    print(f"   care limit dated BEFORE death: {withdrawn_before_death:,} "
          f"({100*withdrawn_before_death/n:.1f} % of the cohort)")

    expo = [k for k in AETIOLOGY
            if sum(r[k] for r in rows) >= 30
            and sum(r[k] * r["bs"] for r in rows) >= 25
            and sum(r[k] * (1 - r["bs"]) for r in rows) >= 25]
    print(f"   aetiologies analysed: {expo}")

    def interactions(R, censor):
        """per-aetiology (KM30 among BS+) - (KM30 among BS-), optionally censoring at the WLST date."""
        out = {}
        for k in expo:
            vals = {}
            for bsv in (1.0, 0.0):
                g = [r for r in R if r[k] > 0 and r["bs"] == bsv]
                if len(g) < 20:
                    vals = None; break
                tt, ee = [], []
                for r in g:
                    if censor and r["wday"] is not None and r["wday"] < r["dday"]:
                        tt.append(max(r["wday"], 0.0)); ee.append(0)
                    else:
                        tt.append(max(r["dday"], 0.0)); ee.append(1)
                vals[bsv] = km_at(tt, ee, HORIZON)
            if vals is None:
                continue
            out[k] = vals[1.0] - vals[0.0]
        return out

    for censor, label in ((False, "UNCENSORED  (death after withdrawal counted as outcome) -> UPPER bound"),
                          (True, "WLST-CENSORED (follow-up ends at the decision)          -> LOWER bound")):
        obs = interactions(rows, censor)
        if len(obs) < 2:
            print(f"\n{label}\n   too few strata"); continue
        sp = float(max(obs.values()) - min(obs.values()))
        bs_sp = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            R = [rows[j] for j in i]
            o = interactions(R, censor)
            if len(o) >= 2:
                bs_sp.append(float(max(o.values()) - min(o.values())))
        lo, hi = (np.percentile(bs_sp, [2.5, 97.5]) if len(bs_sp) > 50 else (float("nan"),) * 2)
        print(f"\n{label}")
        for k, v in sorted(obs.items(), key=lambda x: -x[1]):
            print(f"   {k:12s} {100*v:+7.2f} pp")
        print(f"   INTERACTION SPREAD {100*sp:.2f} pp [{100*lo:.2f},{100*hi:.2f}]")
        if not censor:
            up = sp
        else:
            print(f"\n   BRACKET: the interaction lies between {100*sp:.2f} pp (withdrawal fully discounted) and "
                  f"{100*up:.2f} pp (withdrawal fully counted).")
            print(f"   Withdrawal-attributable share is at most {100*(1-sp/max(up,1e-9)):.0f} % of the effect.")

    print("\n   Neither bound is the truth. Censoring assumes withdrawn patients would have followed the hazard")
    print("   of similar patients not withdrawn, and they were sicker than that, so the censored figure is")
    print("   conservative. Counting post-withdrawal death as the outcome lets the EEG validate a death it")
    print("   helped cause. Reporting only one of these would be a choice about which bias to hide.")
    print("   A DNR/palliative code is a proxy for the decision, not a record of it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
