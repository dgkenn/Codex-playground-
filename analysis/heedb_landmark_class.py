#!/usr/bin/env python3
"""Is the constant relative gap a DOOMED SUBGROUP or a PERSISTENT HAZARD? The landmark test that separates them.

THE QUESTION THIS ANSWERS. Burst suppression after anoxia carries the same RELATIVE excess risk at every horizon
from 7 days to a year (log-odds gap +0.736, +0.872, +0.849, +0.844, +0.732), while the absolute
percentage-point gap compresses as every stratum approaches saturation. Twelve mechanisms have been eliminated.
What remains is a question about the CLASS of explanation, and two classes fit the marginal curve equally well:

  CLASS A -- A FIXED SUBGROUP whose fate is sealed at the time of the EEG. Post-anoxic suppression identifies
  patients who will die whatever happens; everyone else behaves like the background population. As the horizon
  lengthens the doomed members of both arms are used up, so the patients still alive are increasingly drawn from
  the ordinary remainder.
      SIGNATURE: the gap measured AMONG SURVIVORS AT A LATER LANDMARK must ATTENUATE TOWARD ZERO.

  CLASS B -- A PERSISTENT HAZARD DIFFERENCE that keeps applying to whoever is still alive. Nothing is used up.
      SIGNATURE: the gap among landmark survivors is INDISTINGUISHABLE from the gap measured from the EEG.

The marginal odds-ratio-versus-horizon curve cannot separate these -- a mild mixture and a near-constant hazard
shift both produce a nearly flat line. Conditioning on survival to a landmark can, because only Class A predicts
that the excess is exhausted by the people who already died.

  L1  Gap among patients alive at day 30, for death in the following 30 days.
  L2  Gap among patients alive at day 90, for death in the following 90 days.
  L3  Gap among patients alive at day 180, for death in the following 180 days.
      CLASS A CONFIRMED IF the gap declines materially and monotonically across landmarks, reaching less than
      half its day-0 value by the day-180 landmark.
      CLASS B CONFIRMED IF the gap at each landmark overlaps the day-0 gap.
      Anything else -- decline that stalls, or a partial attenuation -- indicates BOTH are operating, which is
      the outcome the round-three brainstorm considered most likely given the 96-hour concentration difference
      (46.3 % vs 21.1 %) sitting alongside an undecayed 180-day odds ratio.

WHY THIS IS THE RIGHT TEST TO RUN NOW. It requires no new data, no feature engineering and no modelling
assumptions beyond the ones already in use, and every other surviving candidate is downstream of its answer: a
Class A result points at what distinguishes the doomed subgroup, a Class B result points at what keeps
generating hazard for a year.

CAVEAT THAT LIMITS INTERPRETATION. Every patient in this cohort has an ascertained death, so "survivors at a
landmark" means patients who had not yet died, not patients who lived. Conditioning on survival also conditions
on everything that caused survival, so a landmark analysis is not free of selection -- it answers whether the
EXCESS is exhausted, which is what distinguishes the two classes, and not whether the excess is causal.
"""
import csv, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "800"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"


def lor(g1, g0):
    a, b = float(np.mean(g1)), float(np.mean(g0))
    a = min(max(a, 5e-4), 1 - 5e-4); b = min(max(b, 5e-4), 1 - 5e-4)
    return float(np.log((a / (1 - a)) / (b / (1 - b))))


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
        rows.append(dict(days=float(days), bs=1.0 if bs.get(p) else 0.0, labs=aet.get(p, set())))
    n = len(rows)
    print(f"cohort: {n:,}")

    def gap_at(R, landmark, window, scale):
        """gap among patients still alive at `landmark`, for death within the next `window` days."""
        out = {}
        for k in ("anoxic", "sepsis"):
            g = [r for r in R if k in r["labs"] and r["days"] > landmark]
            a = [1.0 if r["days"] <= landmark + window else 0.0 for r in g if r["bs"] == 1.0]
            b = [1.0 if r["days"] <= landmark + window else 0.0 for r in g if r["bs"] == 0.0]
            if len(a) < 25 or len(b) < 25:
                return None
            out[k] = lor(a, b) if scale == "lor" else float(np.mean(a) - np.mean(b))
        return out["anoxic"] - out["sepsis"], out

    print("\n" + "=" * 96)
    print("LANDMARK TEST -- is the excess EXHAUSTED by those who already died (Class A),")
    print("                 or does it keep applying to whoever is alive (Class B)?")
    print("=" * 96)
    print(f"   {'landmark':>10s} {'window':>8s} {'n at risk':>10s} {'anoxic BS eff':>14s} "
          f"{'sepsis BS eff':>14s} {'gap pp':>9s} {'gap logOR':>11s} {'95% CI (logOR)':>20s}")

    base = None
    results = {}
    for landmark, window in ((0, 30), (30, 30), (90, 90), (180, 180)):
        res = gap_at(rows, landmark, window, "lor")
        resp = gap_at(rows, landmark, window, "pp")
        if res is None or resp is None:
            print(f"   {landmark:9d}d {window:7d}d  too few at risk")
            continue
        g_lor, parts = res
        g_pp, partsp = resp
        atrisk = sum(1 for r in rows if r["days"] > landmark
                     and ({"anoxic", "sepsis"} & r["labs"]))
        bd = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            rr = gap_at([rows[j] for j in i], landmark, window, "lor")
            if rr is not None:
                bd.append(rr[0])
        lo, hi = np.percentile(bd, [2.5, 97.5]) if len(bd) > 100 else (float("nan"),) * 2
        results[landmark] = (g_lor, lo, hi)
        if base is None:
            base = g_lor
        print(f"   {landmark:9d}d {window:7d}d {atrisk:10d} {100*partsp['anoxic']:13.2f} "
              f"{100*partsp['sepsis']:13.2f} {100*g_pp:8.2f} {g_lor:10.3f} "
              f"[{lo:+8.3f},{hi:+8.3f}]")

    if 180 in results and base:
        frac = results[180][0] / base if abs(base) > 1e-9 else float("nan")
        print(f"\n   day-180-landmark gap is {100*frac:.0f} % of the day-0 gap "
              f"({results[180][0]:+.3f} vs {base:+.3f})")
        classA = frac < 0.5
        classB = results[180][1] <= base <= results[180][2]
        print(f"   CLASS A (doomed subgroup, excess exhausted): "
              f"{'SUPPORTED' if classA else 'not supported'}")
        print(f"   CLASS B (persistent hazard, excess undiminished): "
              f"{'SUPPORTED' if classB else 'not supported'}")
        if not classA and not classB:
            print("   -> partial attenuation: BOTH appear to operate, which is what the 96-hour concentration")
            print("      difference alongside an undecayed 180-day odds ratio already suggested.")

    # ---- shape check: is the anoxic BS+ death-time distribution bimodal? ----------------------------
    print("\n" + "=" * 96)
    print("SHAPE -- a doomed compartment should show up as a distinct early mass, not a smooth shift")
    print("=" * 96)
    print(f"   {'group':22s} " + " ".join(f"{b:>9s}" for b in
          ("0-3d", "4-7d", "8-30d", "31-90d", "91-180d", ">180d")))
    for k in ("anoxic", "sepsis"):
        for bv, nm in ((1.0, "BS+"), (0.0, "BS-")):
            g = [r["days"] for r in rows if k in r["labs"] and r["bs"] == bv]
            if len(g) < 50:
                continue
            d = np.array(g)
            frac = [np.mean(d <= 3), np.mean((d > 3) & (d <= 7)), np.mean((d > 7) & (d <= 30)),
                    np.mean((d > 30) & (d <= 90)), np.mean((d > 90) & (d <= 180)), np.mean(d > 180)]
            print(f"   {k+' '+nm:22s} " + " ".join(f"{100*x:8.1f}%" for x in frac))
    print("\n   Every patient here has an ascertained death, so 'alive at a landmark' means 'had not yet died'.")
    print("   Conditioning on survival conditions on whatever caused it, so this test asks whether the EXCESS")
    print("   is exhausted -- which is what separates the two classes -- not whether it is causal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
