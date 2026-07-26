#!/usr/bin/env python3
"""Three free tests of the 2x anoxia-vs-sepsis gap: label noise, late deaths, and curve shape.

All three reuse quantities already computed. None needs new extraction. Two of them are GATING -- if either
collapses the gap, the headline finding is reframed before any further expensive work is worth doing.

TEST 1 (M8) -- IS THE LABEL THE SAME THING IN EVERY AETIOLOGY?
  Post-arrest EEGs are read by people following prognostication protocols that define burst suppression
  strictly. In sepsis the phrase may be applied more loosely to a severely discontinuous or attenuated
  background that would not meet the same criteria. That alone would pack the sepsis BS+ group with milder
  patterns and dilute its mortality contrast -- producing the entire 2x gap with NO biological difference.
  It also predicts what we already see: sepsis BS+ carries far more generalized slowing (80.5 % vs 58.5 %) and
  the LOWEST intra-burst fast-frequency content of any aetiology, both of which are what "severe diffuse slowing
  called burst suppression" would look like.
  THE TEST: throw the clinician label away. Define burst suppression by a single, fixed, aetiology-blind
  quantitative rule -- measured suppression burden above a threshold -- and recompute the per-aetiology effects.
  The threshold is swept rather than chosen, so the answer cannot depend on picking a flattering cut point.
  FALSIFIED (i.e. label noise is NOT the driver) IF the anoxic:sepsis effect ratio survives roughly intact under
  the blinded definition at most thresholds.

TEST 2 (M5) -- DOES THE GAP SURVIVE PAST THE WITHDRAWAL WINDOW, AETIOLOGY BY AETIOLOGY?
  Section 6c landmarked the whole interaction at day 7 and retained 45 %. That was a single pooled statistic.
  Here the per-aetiology effects are recomputed among day-7 survivors, because the withdrawal explanation makes a
  SPECIFIC prediction: the anoxic effect should shrink disproportionately, since burst suppression is a
  guideline-referenced withdrawal trigger after arrest and is not one in sepsis.
  FALSIFIED IF the anoxic:sepsis ratio is materially unchanged among day-7 survivors.

TEST 3 (M7) -- IS IT A DIFFERENT SLOPE, OR A DIFFERENT SHAPE?
  "The slope differs" assumes both aetiologies follow the same functional form. They may not. Anoxic outcomes
  may be closer to a threshold -- largely intact, or devastated, with little middle -- while sepsis is a graded
  continuum. That is a distinct claim and it is testable by comparing a linear fit against a changepoint fit of
  30-day death on burden, within each aetiology.
  Reported descriptively: whichever form fits better, by residual sum of squares, with the fitted threshold.

Nothing here can establish a mechanism. All three can eliminate one.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "800"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
PAIR = ("anoxic", "sepsis")


def eff(g1, g0):
    if len(g1) < 25 or len(g0) < 25:
        return None
    return float(np.mean(g1) - np.mean(g0))


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
        rows.append(dict(pid=p, days=float(days), d30=1.0 if days <= 30 else 0.0,
                         bs=1.0 if bs.get(p) else 0.0, bur=burden.get(p, float("nan")),
                         labs=aet.get(p, set())))
    n = len(rows)
    hb = [r for r in rows if r["bur"] == r["bur"]]
    print(f"cohort {n:,}; with a measured burden {len(hb):,}")

    def ratio(effs):
        a, s = effs.get("anoxic"), effs.get("sepsis")
        return (a / s) if (a and s and s > 0.01) else float("nan")

    # ============ TEST 1: clinician label vs blinded quantitative definition ======================
    print("\n" + "=" * 78)
    print("TEST 1  IS THE 2x GAP AN ARTEFACT OF HOW THE LABEL IS APPLIED?")
    print("=" * 78)
    print("   Reference, CLINICIAN LABEL, restricted to patients with a measured burden so the")
    print("   comparison is like-for-like:")
    ref = {}
    for k in ("anoxic", "sepsis", "metabolic", "structural", "status"):
        g1 = [r["d30"] for r in hb if k in r["labs"] and r["bs"] == 1.0]
        g0 = [r["d30"] for r in hb if k in r["labs"] and r["bs"] == 0.0]
        e = eff(g1, g0)
        if e is not None:
            ref[k] = e
            print(f"      {k:12s} n+={len(g1):5d} n-={len(g0):5d}  effect {100*e:+7.2f} pp")
    print(f"      anoxic:sepsis ratio = {ratio(ref):.2f}")

    print("\n   BLINDED QUANTITATIVE DEFINITION: burst suppression := measured burden > threshold.")
    print("   The threshold is swept, so the answer cannot depend on choosing a flattering cut point.\n")
    print(f"   {'thresh':>7s} {'anoxic':>18s} {'sepsis':>18s} {'ratio':>7s}")
    for thr in (0.02, 0.05, 0.10, 0.20, 0.30, 0.50):
        q = {}
        for k in PAIR:
            g1 = [r["d30"] for r in hb if k in r["labs"] and r["bur"] > thr]
            g0 = [r["d30"] for r in hb if k in r["labs"] and r["bur"] <= thr]
            e = eff(g1, g0)
            if e is not None:
                q[k] = (e, len(g1), len(g0))
        if len(q) == 2:
            ra = q["anoxic"][0] / q["sepsis"][0] if q["sepsis"][0] > 0.01 else float("nan")
            print(f"   {thr:7.2f} {100*q['anoxic'][0]:+9.2f}pp (n+={q['anoxic'][1]:4d}) "
                  f"{100*q['sepsis'][0]:+9.2f}pp (n+={q['sepsis'][1]:4d}) {ra:7.2f}")
    print("\n   If the ratio stays near the clinician-label value across thresholds, label noise is NOT")
    print("   driving the gap. If it collapses toward 1.0, the gap is substantially a labelling artefact.")

    # ============ TEST 2: per-aetiology effects among day-7 survivors ============================
    print("\n" + "=" * 78)
    print("TEST 2  DOES THE GAP SURVIVE PAST THE WITHDRAWAL WINDOW, AETIOLOGY BY AETIOLOGY?")
    print("=" * 78)
    late = [r for r in rows if r["days"] > 7]
    print(f"   alive at day 7: {len(late):,} of {n:,}")
    print(f"   {'aetiology':12s} {'full cohort':>14s} {'day-7 survivors':>18s}")
    lref = {}
    for k in ("anoxic", "sepsis", "metabolic", "structural", "status"):
        g1 = [r["d30"] for r in rows if k in r["labs"] and r["bs"] == 1.0]
        g0 = [r["d30"] for r in rows if k in r["labs"] and r["bs"] == 0.0]
        e_all = eff(g1, g0)
        h1 = [r["d30"] for r in late if k in r["labs"] and r["bs"] == 1.0]
        h0 = [r["d30"] for r in late if k in r["labs"] and r["bs"] == 0.0]
        e_late = eff(h1, h0)
        if e_all is None:
            continue
        lref[k] = e_late if e_late is not None else float("nan")
        s_late = f"{100*e_late:+7.2f} pp" if e_late is not None else "     n/a"
        print(f"   {k:12s} {100*e_all:+11.2f} pp {s_late:>18s}")
    r_all, r_late = ratio({k: v for k, v in zip(("anoxic", "sepsis"),
                                                (eff([r["d30"] for r in rows if "anoxic" in r["labs"] and r["bs"]==1.0],
                                                     [r["d30"] for r in rows if "anoxic" in r["labs"] and r["bs"]==0.0]),
                                                 eff([r["d30"] for r in rows if "sepsis" in r["labs"] and r["bs"]==1.0],
                                                     [r["d30"] for r in rows if "sepsis" in r["labs"] and r["bs"]==0.0])))}), ratio(lref)
    print(f"\n   anoxic:sepsis ratio  full cohort {r_all:.2f}   day-7 survivors {r_late:.2f}")
    print("   The withdrawal explanation predicts the anoxic effect shrinks disproportionately,")
    print("   i.e. the ratio falls materially. If the ratio holds, withdrawal is not what makes anoxia special.")

    # ============ TEST 3: slope or shape? ========================================================
    print("\n" + "=" * 78)
    print("TEST 3  DIFFERENT SLOPE, OR DIFFERENT SHAPE?")
    print("=" * 78)
    for k in PAIR:
        sub = [r for r in hb if k in r["labs"]]
        if len(sub) < 200:
            continue
        x = np.array([r["bur"] for r in sub]); y = np.array([r["d30"] for r in sub])
        X = np.column_stack([np.ones(len(x)), x])
        bl = np.linalg.lstsq(X, y, rcond=None)[0]
        rss_lin = float(((y - X @ bl) ** 2).sum())
        best = (None, np.inf)
        for c in np.arange(0.05, 0.90, 0.05):
            Xc = np.column_stack([np.ones(len(x)), np.maximum(x - c, 0.0)])
            bc = np.linalg.lstsq(Xc, y, rcond=None)[0]
            rss = float(((y - Xc @ bc) ** 2).sum())
            if rss < best[1]:
                best = (c, rss)
        print(f"   {k:12s} n={len(sub):5d}  linear RSS {rss_lin:9.2f} | "
              f"threshold RSS {best[1]:9.2f} at burden {best[0]:.2f}  "
              f"-> {'THRESHOLD' if best[1] < rss_lin else 'LINEAR'} fits better")
        q = np.percentile(x, [25, 50, 75])
        cells = []
        for sel in (x <= q[0], (x > q[0]) & (x <= q[1]), (x > q[1]) & (x <= q[2]), x > q[2]):
            cells.append(f"{100*y[sel].mean():.1f}%" if sel.sum() >= 10 else "  n/a")
        print(f"      quartile 30-day death: {' -> '.join(cells)}")
    print("\n   Descriptive only. A better-fitting threshold model in anoxia and a linear one in sepsis would")
    print("   mean the two aetiologies differ in the FORM of the dose-response, not merely its steepness.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
