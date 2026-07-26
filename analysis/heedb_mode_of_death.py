#!/usr/bin/env python3
"""Four cheap tests of the two surviving mechanisms, plus two due-diligence checks.

After eleven candidates have been eliminated, two complementary mechanisms remain, and both are testable with
data already extracted.

  MECHANISM A -- WHAT PATIENTS DIE OF DIFFERS. After cardiac arrest, death is disproportionately a
  neurologically-mediated event: catastrophic injury, prognostication, withdrawal, usually within days. In
  sepsis, death is disproportionately multi-organ attrition over a longer and more variable course, in which the
  brain is a bystander. Burst suppression reads out the anoxic pathway almost directly and the septic one only
  partially, which would produce the observed gap without any difference in what suppression IS.
    A1  Among patients who die, the SHAPE of the death-timing distribution should differ: anoxic
        burst-suppression deaths concentrated in the first days, septic ones spread out. This is a shape claim,
        distinct from the already-known difference in medians (5 days vs 189).
        FALSIFIED IF the fraction of deaths falling in the first 96 h is indistinguishable between aetiologies
        among burst-suppression patients.

  MECHANISM B -- SEPTIC SUPPRESSION IS PARTLY DRUG-INDUCED. Deep sedation is far commoner in septic ICU care
  than in post-arrest protocols, which wean sedation before prognostication. Drug-induced suppression carries
  little information about the brain, so it dilutes the septic estimate.
    B1  At the time of the EEG, septic burst-suppression patients should be more deeply sedated than anoxic ones,
        measured by the RASS score nearest the recording.
        FALSIFIED IF RASS at EEG time is similar across aetiologies among burst-suppression patients.
    B2  Restricting to patients who are NOT deeply sedated at the EEG (RASS > -4) should shrink the septic
        estimate more than the anoxic one, narrowing the gap.
        FALSIFIED IF the anoxic:sepsis gap is unchanged or widens under that restriction.

DUE DILIGENCE, run regardless because they protect everything else.
  D1  SCALE. Every gap in this project is a difference of proportions. Percentage-point differences and
      odds-ratio differences can disagree even when no stratum is near a floor or ceiling. The sign pattern --
      burst suppression positive-anoxic, slowing negative-anoxic, non-EEG predictors negative-anoxic but smaller
      -- must survive on the log-odds scale or the whole story needs re-examination.
  D2  THE COMPARATOR. The burst-suppression gap rose from +20.41 pp against all lower rungs to +23.43 against
      the adjacent rung, which was read as suppression being specifically unlike its neighbours. The simpler
      explanation is that the pooled reference contains the slowing rung, whose aetiology gap is
      equal-and-opposite, so pooling cancels part of the effect. Computing the gap against the SLOWING rung
      alone settles it: if the compositional reading is right, that comparison should be the LARGEST of the
      three.
"""
import csv, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "800"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
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
    when, F = {}, defaultdict(dict)
    FL = ("bs", "gen slowing", "foc slowing", "gpd", "lpd", "seizure", "grda", "lrda", "spikes", "status")
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
            for f in FL:
                F[p][f] = F[p].get(f, False) or ((r.get(f) or "").strip() not in ("", "None", "nan"))

    # RASS nearest the index EEG
    rass = {}
    mc = f"{OMOP}/measurement_conscious.csv"
    if os.path.exists(mc):
        best = {}
        for r in csv.DictReader(open(mc)):
            s = (r.get("measurement_source_value") or "").upper()
            if "RASS" not in s:
                continue
            try:
                p = int(r["person_id"]); v = float(r.get("value_as_number") or "nan")
            except Exception:
                continue
            if v != v or v < -5 or v > 4:
                continue
            t = dt(r.get("measurement_datetime"))
            t0 = when.get(p)
            if t is None or t0 is None:
                continue
            gap = abs((t - t0).total_seconds())
            if gap > 24 * 3600:
                continue
            if p not in best or gap < best[p][0]:
                best[p] = (gap, v)
        rass = {p: v for p, (g, v) in best.items()}
    print(f"patients with a RASS within 24 h of the index EEG: {len(rass):,}")

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
        f = F[p]
        rung = (3 if f.get("bs") else
                2 if any(f.get(k) for k in ("gpd", "lpd", "seizure", "grda", "lrda", "spikes", "status")) else
                1 if (f.get("gen slowing") or f.get("foc slowing")) else 0)
        rows.append(dict(days=float(days), d30=1.0 if days <= 30 else 0.0,
                         bs=1.0 if f.get("bs") else 0.0, rung=rung,
                         slow=1.0 if (f.get("gen slowing") or f.get("foc slowing")) else 0.0,
                         gpd=1.0 if f.get("gpd") else 0.0,
                         rass=rass.get(p, float("nan")), labs=aet.get(p, set())))
    n = len(rows)
    print(f"cohort: {n:,}")

    # ---------- A1: shape of the death-timing distribution ------------------------------------------
    print("\n" + "=" * 90)
    print("A1  MODE OF DEATH -- is anoxic death CONCENTRATED early, or merely earlier?")
    print("=" * 90)
    print(f"   among burst-suppression patients who died, cumulative fraction dead by:")
    print(f"   {'aetiology':12s} {'n':>6s} {'96 h':>8s} {'7 d':>8s} {'30 d':>8s} {'90 d':>8s} {'median d':>9s}")
    for k in AE:
        g = [r for r in rows if k in r["labs"] and r["bs"] == 1.0]
        if len(g) < 50:
            continue
        dv = np.array([r["days"] for r in g])
        print(f"   {k:12s} {len(g):6d} {100*np.mean(dv<=4):7.1f}% {100*np.mean(dv<=7):7.1f}% "
              f"{100*np.mean(dv<=30):7.1f}% {100*np.mean(dv<=90):7.1f}% {np.median(dv):8.0f}")
    ga = [r["days"] for r in rows if "anoxic" in r["labs"] and r["bs"] == 1.0]
    gs = [r["days"] for r in rows if "sepsis" in r["labs"] and r["bs"] == 1.0]
    if len(ga) > 50 and len(gs) > 50:
        d = []
        for _ in range(NBOOT):
            a = np.random.default_rng().choice(ga, len(ga)); b = np.random.default_rng().choice(gs, len(gs))
            d.append(float(np.mean(a <= 4) - np.mean(b <= 4)))
        lo, hi = np.percentile(d, [2.5, 97.5])
        print(f"\n   anoxic minus septic, fraction dead within 96 h: "
              f"{100*(np.mean(np.array(ga)<=4)-np.mean(np.array(gs)<=4)):+.2f} pp [{100*lo:+.2f},{100*hi:+.2f}]")
        print(f"   A1 {'CONFIRMED' if lo > 0 else 'FALSIFIED'} (anoxic deaths concentrated early)")

    # ---------- B1/B2: sedation depth at the EEG -----------------------------------------------------
    print("\n" + "=" * 90)
    print("B1/B2  SEDATION AT THE TIME OF THE EEG  (RASS -5 deepest, 0 alert)")
    print("=" * 90)
    have = [r for r in rows if r["rass"] == r["rass"]]
    print(f"   patients with RASS: {len(have):,}")
    print(f"   {'aetiology':12s} {'BS+ median RASS':>17s} {'BS+ % RASS<=-4':>16s} {'BS- median RASS':>17s}")
    for k in AE:
        g1 = [r["rass"] for r in have if k in r["labs"] and r["bs"] == 1.0]
        g0 = [r["rass"] for r in have if k in r["labs"] and r["bs"] == 0.0]
        if len(g1) < 30 or len(g0) < 30:
            continue
        print(f"   {k:12s} {np.median(g1):16.1f} {100*np.mean(np.array(g1)<=-4):15.1f}% "
              f"{np.median(g0):16.1f}")

    print("\n   B2  burst-suppression effect restricted to patients NOT deeply sedated (RASS > -4):")
    print(f"   {'aetiology':12s} {'all':>12s} {'RASS > -4':>12s}")
    eff = {}
    for k in AE:
        out = []
        for sel in (lambda r: True, lambda r: r["rass"] == r["rass"] and r["rass"] > -4):
            g = [r for r in have if k in r["labs"] and sel(r)]
            a = [r["d30"] for r in g if r["bs"] == 1.0]
            b = [r["d30"] for r in g if r["bs"] == 0.0]
            out.append(float(np.mean(a) - np.mean(b)) if len(a) >= 20 and len(b) >= 20 else float("nan"))
        eff[k] = out
        print(f"   {k:12s} {100*out[0]:+11.2f} {100*out[1]:+11.2f}")
    if all(v == v for v in eff.get("anoxic", [np.nan])) and all(v == v for v in eff.get("sepsis", [np.nan])):
        r_all = eff["anoxic"][0] - eff["sepsis"][0]
        r_awk = eff["anoxic"][1] - eff["sepsis"][1]
        print(f"\n   anoxic-minus-septic gap: all {100*r_all:+.2f} pp   not-deeply-sedated {100*r_awk:+.2f} pp")
        print(f"   B2 {'CONFIRMED' if r_awk < r_all else 'FALSIFIED'} "
              f"(gap narrows when drug-induced suppression is excluded)")

    # ---------- D1: does the sign pattern survive on the log-odds scale? ----------------------------
    print("\n" + "=" * 90)
    print("D1  SCALE CHECK -- do the gaps keep their signs as log odds ratios?")
    print("=" * 90)

    def lor(g1, g0):
        a = np.mean(g1); b = np.mean(g0)
        a = min(max(a, 1e-3), 1 - 1e-3); b = min(max(b, 1e-3), 1 - 1e-3)
        return float(np.log((a / (1 - a)) / (b / (1 - b))))
    print(f"   {'finding':14s} {'anoxic logOR':>14s} {'sepsis logOR':>14s} {'difference':>12s} {'pp difference':>14s}")
    for f in ("bs", "slow", "gpd"):
        lors, pps = [], []
        for k in ("anoxic", "sepsis"):
            g = [r for r in rows if k in r["labs"]]
            g1 = [r["d30"] for r in g if r[f] == 1.0]
            g0 = [r["d30"] for r in g if r[f] == 0.0]
            if len(g1) < 25 or len(g0) < 25:
                lors.append(float("nan")); pps.append(float("nan")); continue
            lors.append(lor(g1, g0)); pps.append(float(np.mean(g1) - np.mean(g0)))
        print(f"   {f:14s} {lors[0]:+13.3f} {lors[1]:+13.3f} {lors[0]-lors[1]:+11.3f} "
              f"{100*(pps[0]-pps[1]):+13.2f}")
    print("   The log-odds difference must carry the SAME SIGN as the percentage-point difference for each")
    print("   finding, or the whole C16-C18 sign pattern is scale-dependent and needs re-examination.")

    # ---------- D2: which comparator gives the largest gap? -----------------------------------------
    print("\n" + "=" * 90)
    print("D2  THE COMPARATOR -- is the 'suppression differs from its neighbours' reading just arithmetic?")
    print("=" * 90)
    print(f"   {'reference group':28s} {'anoxic':>9s} {'sepsis':>9s} {'gap':>9s}")
    for name, ref in (("all lower rungs (0,1,2)", (0, 1, 2)),
                      ("adjacent rung only (2)", (2,)),
                      ("slowing rung only (1)", (1,)),
                      ("preserved only (0)", (0,))):
        out = []
        for k in ("anoxic", "sepsis"):
            g = [r for r in rows if k in r["labs"]]
            a = [r["d30"] for r in g if r["rung"] == 3]
            b = [r["d30"] for r in g if r["rung"] in ref]
            out.append(float(np.mean(a) - np.mean(b)) if len(a) >= 25 and len(b) >= 25 else float("nan"))
        print(f"   {name:28s} {100*out[0]:+8.2f} {100*out[1]:+8.2f} {100*(out[0]-out[1]):+8.2f}")
    print("\n   If the slowing-only comparator gives the LARGEST gap, the earlier reading was compositional")
    print("   arithmetic rather than evidence that suppression differs specially from its neighbours.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
