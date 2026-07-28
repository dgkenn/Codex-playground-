#!/usr/bin/env python3
"""Does suppression burden INDEX different things in different aetiologies? (the dosimeter hypothesis)

THE HYPOTHESIS, constructed to satisfy the accumulated constraint set in docs/research/41_RESULTS_LEDGER.md and
therefore POST HOC. It is tested here on an implication it was NOT built to explain.

  Burst suppression burden is one measurement with two referents. After anoxia it indexes HOW MUCH CORTEX DIED --
  an injury dosimeter. In sepsis and metabolic derangement the identical measurement indexes HOW DEEPLY THE
  PATIENT WAS SEDATED -- a drug dosimeter. Same number, different meaning.

WHY IT FITS WHAT WE ALREADY KNOW (this part is curve-fitting and proves nothing on its own):
  * the burden->death SLOPE differs by aetiology while depth per se does not explain the effect -- the slope
    differs because the referent differs;
  * within anoxia the dose-response is steep and monotone (35.6 -> 86.6 % across quartiles);
  * every aetiology is still positive, because deeper suppression correlates with something bad everywhere --
    either injury extent or the severity that prompted deep sedation;
  * post-anoxic suppression keeps LESS company (fewer GPDs, less generalized slowing), as injury-driven
    suppression need not sit in a systemically deranged brain;
  * persistence is prognostic but explains little independent variance, being downstream of, and collinear with,
    injury extent;
  * clinicians already believe the injury reading and act on it, so the withdrawal signal is a PREDICTION of the
    hypothesis rather than a competitor to it.

THE FRESH IMPLICATION, registered before fitting. If burden indexes injury in anoxia and sedation elsewhere:
  P1  Within ANOXIC patients, the burden->death slope should be STEEPER in those with NO burst-suppression-capable
      anaesthetic around the EEG (where burden is a pure injury signal) than in those with one (where it is
      diluted by a drug contribution).
      FALSIFIED IF the no-anaesthetic slope is not larger, or the paired difference covers zero.
  P2  Within SEPSIS and METABOLIC patients the burden->death slope should be SHALLOWER than in anoxic patients,
      and should be further attenuated among those with peri-EEG anaesthetic.
      FALSIFIED IF the sepsis/metabolic slope is not shallower than the anoxic slope.

  These are about SLOPES WITHIN STRATA, computed as unadjusted differences, not interaction coefficients. An
  interaction coefficient is measured against a reference group and is not the effect within a stratum -- reading
  one as the other is the error that produced this project's false "suppression is benign in sepsis" claim
  (docs/LESSONS.md).

ALSO TESTED, because it is nearly free and it discriminates a rival explanation.
  RIVAL: "anoxic patients are simply sicker, so any marker looks worse in them."
  The rival predicts that aetiologies with higher baseline mortality show larger burst-suppression effects. It is
  checkable directly: correlate each aetiology's BS-NEGATIVE 30-day mortality against its BS effect size. The
  striking pair is anoxic and sepsis, whose BS-negative mortality is nearly identical (32.8 % vs 32.7 %) while
  their BS effects differ almost twofold (+38.3 vs +17.9 pp). If baseline severity drove the effect, that could
  not happen.

LIMITS. Peri-EEG anaesthetic exposure is itself a severity proxy in this cohort (the H2 test failed exactly that
way, +31.00 pp in the wrong direction), so it cannot be read as a clean instrument for "this suppression is
drug-induced". P1 is therefore suggestive at best, and a positive result would need the exposure replaced by
something better before it is believed. Stated in advance so a confirmation is not over-read.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "1000"))
WIN_H = float(os.environ.get("WIN_H", "24"))
BS_CAPABLE = ("propofol", "midazolam", "pentobarbital", "thiopental", "phenobarbital")
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def slope(xs, ys, rng, nboot):
    x = np.asarray(xs, float); y = np.asarray(ys, float)
    if len(x) < 40 or x.std() < 1e-9:
        return None
    X = np.column_stack([np.ones(len(x)), x])
    b = float(lpm(X, y)[1])
    bs = []
    for _ in range(nboot):
        i = rng.integers(0, len(x), len(x))
        try:
            bs.append(float(lpm(X[i], y[i])[1]))
        except Exception:
            continue
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return b, lo, hi, len(x), bs


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

    # peri-EEG BS-capable anaesthetic, from the sedative extraction over the full EEG cohort
    anaes = set()
    sedfile = f"{OMOP}/drug_sedatives.csv"
    if os.path.exists(sedfile):
        for r in csv.DictReader(open(sedfile)):
            v = (r.get("drug_source_value") or "").lower()
            if not any(x in v for x in BS_CAPABLE):
                continue
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            t0 = when.get(p)
            s = dt(r.get("drug_exposure_start_datetime"))
            if t0 is None or s is None:
                continue
            if abs((s - t0).total_seconds()) <= WIN_H * 3600.0:
                anaes.add(p)
    print(f"patients with a peri-EEG BS-capable anaesthetic: {len(anaes):,}")

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen:
            continue
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        rows.append(dict(pid=p, d30=1.0 if days <= 30 else 0.0, bs=1.0 if bs.get(p) else 0.0,
                         bur=burden.get(p, float("nan")), an=1.0 if p in anaes else 0.0,
                         labs=aet.get(p, set())))
    print(f"cohort: {len(rows):,}   with a measured burden: {sum(1 for r in rows if r['bur']==r['bur']):,}")

    # ---------- RIVAL: is the effect just baseline severity? -----------------------------------------
    print("\n" + "=" * 78)
    print("RIVAL EXPLANATION: 'anoxic patients are simply sicker, so any marker looks worse'")
    print("=" * 78)
    print(f"   {'aetiology':12s} {'BS- 30d':>9s} {'BS+ 30d':>9s} {'BS effect':>11s}")
    pts = []
    for k in AETIOLOGY:
        g1 = [r for r in rows if k in r["labs"] and r["bs"] == 1.0]
        g0 = [r for r in rows if k in r["labs"] and r["bs"] == 0.0]
        if len(g1) < 30 or len(g0) < 30:
            continue
        a = float(np.mean([r["d30"] for r in g1])); b = float(np.mean([r["d30"] for r in g0]))
        pts.append((k, b, a - b))
        print(f"   {k:12s} {100*b:8.1f}% {100*a:8.1f}% {100*(a-b):+10.1f}pp")
    if len(pts) >= 4:
        bl = np.array([p[1] for p in pts]); ef = np.array([p[2] for p in pts])
        r = float(np.corrcoef(bl, ef)[0, 1])
        print(f"\n   correlation between BASELINE (BS-negative) mortality and BS effect size: r = {r:+.3f}")
        print("   The rival requires this to be strongly POSITIVE. Anoxic and sepsis are the decisive pair:")
        an = [p for p in pts if p[0] == "anoxic"]; se = [p for p in pts if p[0] == "sepsis"]
        if an and se:
            print(f"      anoxic baseline {100*an[0][1]:.1f}% -> effect {100*an[0][2]:+.1f}pp")
            print(f"      sepsis baseline {100*se[0][1]:.1f}% -> effect {100*se[0][2]:+.1f}pp")
            print("      near-identical baseline severity, effects differing about twofold.")

    # ---------- P1 / P2: the dosimeter test ----------------------------------------------------------
    print("\n" + "=" * 78)
    print("P1/P2  BURDEN -> 30-DAY DEATH SLOPE, within aetiology and by peri-EEG anaesthetic")
    print("=" * 78)
    print("   slope is percentage points of 30-day death per unit burden (0 = none, 1 = fully suppressed)\n")
    print(f"   {'stratum':34s} {'n':>5s} {'slope pp/unit':>15s} {'95% CI':>22s}")
    store = {}
    for k in ("anoxic", "sepsis", "metabolic", "structural", "status"):
        sub = [r for r in rows if k in r["labs"] and r["bur"] == r["bur"]]
        if len(sub) < 60:
            continue
        s_all = slope([r["bur"] for r in sub], [r["d30"] for r in sub], rng, NBOOT)
        if s_all:
            print(f"   {k+' (all)':34s} {s_all[3]:5d} {100*s_all[0]:14.2f} "
                  f"[{100*s_all[1]:+7.2f},{100*s_all[2]:+7.2f}]")
            store[k] = s_all
        for av, nm in ((0.0, "no peri-EEG anaesthetic"), (1.0, "peri-EEG anaesthetic")):
            g = [r for r in sub if r["an"] == av]
            s2 = slope([r["bur"] for r in g], [r["d30"] for r in g], rng, NBOOT)
            if s2:
                print(f"   {'   '+k+' / '+nm:34s} {s2[3]:5d} {100*s2[0]:14.2f} "
                      f"[{100*s2[1]:+7.2f},{100*s2[2]:+7.2f}]")
                store[(k, av)] = s2

    # P1: anoxic, no-anaesthetic slope steeper than with-anaesthetic, differenced per replicate
    if ("anoxic", 0.0) in store and ("anoxic", 1.0) in store:
        a0, a1 = store[("anoxic", 0.0)], store[("anoxic", 1.0)]
        m = min(len(a0[4]), len(a1[4]))
        d = np.array(a0[4][:m]) - np.array(a1[4][:m])
        lo, hi = np.percentile(d, [2.5, 97.5])
        print(f"\n   P1  anoxic: (no anaesthetic) - (anaesthetic) = {100*(a0[0]-a1[0]):+.2f} pp "
              f"[{100*lo:+.2f},{100*hi:+.2f}]")
        print(f"   P1 {'CONFIRMED' if lo > 0 else 'FALSIFIED'} (predicted the no-anaesthetic slope to be steeper)")

    # P2: sepsis/metabolic shallower than anoxic
    if "anoxic" in store:
        for k in ("sepsis", "metabolic"):
            if k in store:
                m = min(len(store["anoxic"][4]), len(store[k][4]))
                d = np.array(store["anoxic"][4][:m]) - np.array(store[k][4][:m])
                lo, hi = np.percentile(d, [2.5, 97.5])
                print(f"   P2  anoxic - {k}: {100*(store['anoxic'][0]-store[k][0]):+.2f} pp "
                      f"[{100*lo:+.2f},{100*hi:+.2f}] {'CONFIRMED' if lo > 0 else 'FALSIFIED'}")

    print("\n   Peri-EEG anaesthetic exposure is itself a severity proxy in this cohort (the H2 test failed")
    print("   exactly that way), so P1 is suggestive at best and a confirmation must not be over-read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
