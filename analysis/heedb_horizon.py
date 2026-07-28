#!/usr/bin/env python3
"""Does the aetiology gap SHRINK at longer horizons? The sharpest remaining test of what is driving it.

WHERE THIS SITS. Twelve candidate explanations have now been eliminated. Drug-induced suppression was the last
serious rival and it died decisively: post-anoxic patients turn out to be MORE likely to have an infusion running
at the EEG (74.3 % vs 64.0 % in sepsis, the reverse of the prediction), the burst-suppression effect is LARGER
with a drug running in all five aetiologies, and restricting to patients with no active infusion narrows the gap
by only 16.8 % [-1.75,+8.29]. What survives is the account in which WHAT PATIENTS DIE OF differs: post-anoxic
death is a fast, neurologically-mediated event (46.3 % within 96 h) while septic death is multi-organ attrition
spread over weeks (21.1 % within 96 h).

THE TEST THAT DISCRIMINATES IT. That account and a plain biological one ("suppression simply indexes more brain
injury after anoxia") make OPPOSITE predictions about the time horizon, and nothing tested so far separates them:

  * If the gap exists because anoxic death is FRONT-LOADED, then lengthening the horizon lets septic patients
    accumulate the deaths they were always going to have, and the gap must COMPRESS. At a long enough horizon
    almost everyone in this cohort has died, so the gap must approach zero by construction.
  * If suppression genuinely indexes more irreversible injury after anoxia, the gap should PERSIST in relative
    terms even as absolute rates converge -- an anoxic patient with suppression is not merely dying sooner, they
    are more likely to die at all within any clinically meaningful window.

  H1  The absolute (percentage-point) gap shrinks monotonically from 7 to 30 to 90 to 180 days.
      FALSIFIED IF it does not decline.
  H2  THE DISCRIMINATING ONE. The gap on the LOG-ODDS scale -- which is not mechanically compressed as rates
      approach 100 % -- also declines materially, by at least 40 % from 30 to 180 days.
      FALSIFIED IF the log-odds gap is roughly flat, which would mean the effect is not merely a timing
      phenomenon and the front-loading account is incomplete.

  H1 is close to guaranteed and is reported mainly as a sanity check; H2 is the real test, because a purely
  mechanical ceiling effect moves H1 without moving H2.

ALSO RUN, because both are cheap and both are standard robustness questions a reviewer will ask.
  R1  PURE AETIOLOGY. Patients coded with more than one of the five aetiologies blur the contrast. Restricting
      to patients carrying EXACTLY ONE of them tests whether label overlap is inflating the gap.
      FALSIFIED (i.e. contamination matters) IF the gap changes by more than a third.
  R2  PER-SITE. The headline gap has never been reported separately at the two hospitals. Both should show it.
  R3  WITHIN ANOXIC, TIMING. Guidelines put neuroprognostication at >= 72 h after arrest, and an EEG recorded
      early is widely held to be less informative. Splitting anoxic patients by delay from first anoxic
      diagnosis code to EEG tests whether our anoxic effect depends on recording time.
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
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
AE = ("anoxic", "sepsis", "metabolic", "structural", "status")
HORIZONS = (7, 30, 90, 180, 365)


def lor(g1, g0):
    a, b = float(np.mean(g1)), float(np.mean(g0))
    a = min(max(a, 5e-4), 1 - 5e-4); b = min(max(b, 5e-4), 1 - 5e-4)
    return float(np.log((a / (1 - a)) / (b / (1 - b))))


def main():
    rng = np.random.default_rng(20260726)

    aet, cond_seen, firstdx = defaultdict(set), set(), {}
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
                    t = dt(r.get("condition_start_datetime"))
                    if t is not None and ((p, lab) not in firstdx or t < firstdx[(p, lab)]):
                        firstdx[(p, lab)] = t

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
    when, bs, site = {}, {}, {}
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
                when[p] = t; site[p] = st
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
        labs = aet.get(p, set())
        core = labs & set(AE)
        rows.append(dict(days=float(days), bs=1.0 if bs.get(p) else 0.0, labs=labs,
                         npure=len(core), site=site.get(p, "?"),
                         dx_gap=((t0 - firstdx[(p, "anoxic")]).total_seconds() / 86400.0
                                 if (p, "anoxic") in firstdx else float("nan"))))
    n = len(rows)
    print(f"cohort: {n:,}")

    def gap(R, H, sub=None, scale="pp"):
        S = R if sub is None else [r for r in R if sub(r)]
        out = {}
        for k in ("anoxic", "sepsis"):
            g = [r for r in S if k in r["labs"]]
            a = [1.0 if r["days"] <= H else 0.0 for r in g if r["bs"] == 1.0]
            b = [1.0 if r["days"] <= H else 0.0 for r in g if r["bs"] == 0.0]
            if len(a) < 25 or len(b) < 25:
                return None
            out[k] = lor(a, b) if scale == "lor" else float(np.mean(a) - np.mean(b))
        return out["anoxic"] - out["sepsis"]

    # ---- H1 / H2 -------------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("H1/H2  DOES THE GAP SHRINK AS THE HORIZON LENGTHENS?")
    print("=" * 92)
    print(f"   {'horizon':>8s} {'anoxic BS+':>11s} {'anoxic BS-':>11s} {'sepsis BS+':>11s} "
          f"{'sepsis BS-':>11s} {'gap pp':>9s} {'gap logOR':>10s}")
    pp, lg = {}, {}
    for H in HORIZONS:
        cells = []
        for k in ("anoxic", "sepsis"):
            g = [r for r in rows if k in r["labs"]]
            for bv in (1.0, 0.0):
                s = [1.0 if r["days"] <= H else 0.0 for r in g if r["bs"] == bv]
                cells.append(100 * float(np.mean(s)))
        pp[H] = gap(rows, H, scale="pp"); lg[H] = gap(rows, H, scale="lor")
        print(f"   {H:7d}d {cells[0]:10.1f}% {cells[1]:10.1f}% {cells[2]:10.1f}% {cells[3]:10.1f}% "
              f"{100*pp[H]:8.2f} {lg[H]:9.3f}")
    mono = all(pp[HORIZONS[i]] >= pp[HORIZONS[i + 1]] - 1e-9 for i in range(len(HORIZONS) - 1))
    print(f"\n   H1 {'CONFIRMED' if mono else 'FALSIFIED'} (percentage-point gap declines monotonically)")
    if 30 in lg and 180 in lg and abs(lg[30]) > 1e-9:
        drop = (lg[30] - lg[180]) / lg[30]
        bd = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            R = [rows[j] for j in i]
            a, b = gap(R, 30, scale="lor"), gap(R, 180, scale="lor")
            if a is not None and b is not None and abs(a) > 1e-9:
                bd.append((a - b) / a)
        lo, hi = np.percentile(bd, [2.5, 97.5]) if bd else (float("nan"),) * 2
        print(f"   log-odds gap 30d {lg[30]:+.3f} -> 180d {lg[180]:+.3f}  "
              f"decline {100*drop:.1f} % [{100*lo:.1f},{100*hi:.1f}]")
        print(f"   H2 {'CONFIRMED' if drop >= 0.40 and lo > 0 else 'FALSIFIED'} "
              f"(registered threshold: 40 % decline on the log-odds scale)")
        print("   A flat log-odds gap would mean the effect is not merely a timing phenomenon and the")
        print("   front-loading account is incomplete.")

    # ---- R1: pure aetiology --------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("R1  DOES LABEL OVERLAP INFLATE THE GAP? (patients carrying exactly one of the five)")
    print("=" * 92)
    g_all, g_pure = gap(rows, 30), gap(rows, 30, sub=lambda r: r["npure"] == 1)
    npure = sum(1 for r in rows if r["npure"] == 1)
    if g_pure is not None:
        print(f"   all patients        gap {100*g_all:+.2f} pp   (n={n:,})")
        print(f"   single-aetiology    gap {100*g_pure:+.2f} pp   (n={npure:,})")
        ch = abs(g_pure - g_all) / abs(g_all) if abs(g_all) > 1e-9 else float("nan")
        print(f"   change {100*ch:.1f} %   R1 {'ROBUST' if ch < 0.33 else 'SENSITIVE to label overlap'}")

    # ---- R2: per site --------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("R2  DOES THE GAP APPEAR AT BOTH HOSPITALS?")
    print("=" * 92)
    for st in sorted(set(r["site"] for r in rows)):
        gs = gap(rows, 30, sub=lambda r, s=st: r["site"] == s)
        cnt = sum(1 for r in rows if r["site"] == st)
        print(f"   {st}  n={cnt:6d}  gap {100*gs:+.2f} pp" if gs is not None
              else f"   {st}  too few")

    # ---- R3: timing of the EEG within anoxic patients ------------------------------------------------
    print("\n" + "=" * 92)
    print("R3  WITHIN ANOXIC PATIENTS, DOES THE EFFECT DEPEND ON WHEN THE EEG WAS RECORDED?")
    print("=" * 92)
    ga = [r for r in rows if "anoxic" in r["labs"] and r["dx_gap"] == r["dx_gap"]]
    print(f"   anoxic patients with a dated anoxic diagnosis: {len(ga):,}")
    for lab, sel in (("EEG within 1 day", lambda r: r["dx_gap"] <= 1),
                     ("1-3 days", lambda r: 1 < r["dx_gap"] <= 3),
                     ("more than 3 days", lambda r: r["dx_gap"] > 3)):
        g = [r for r in ga if sel(r)]
        a = [1.0 if r["days"] <= 30 else 0.0 for r in g if r["bs"] == 1.0]
        b = [1.0 if r["days"] <= 30 else 0.0 for r in g if r["bs"] == 0.0]
        if len(a) >= 25 and len(b) >= 25:
            print(f"   {lab:20s} n={len(g):5d}  BS effect {100*(np.mean(a)-np.mean(b)):+7.2f} pp")
        else:
            print(f"   {lab:20s} too few")
    print("\n   Diagnosis-code date is a weak proxy for the arrest itself, so R3 is descriptive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
