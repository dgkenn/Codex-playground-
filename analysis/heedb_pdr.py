#!/usr/bin/env python3
"""Does a preserved POSTERIOR DOMINANT RHYTHM change what burst suppression means? (confound-controlled)

THE OBSERVATION THAT PROMPTED THIS. Stratifying the burst-suppression effect by whether a posterior dominant
rhythm was ever reported produced the largest and most orderly modification seen anywhere in this project:

    aetiology     BS effect, PDR absent    BS effect, PDR present
    anoxic              +37.12 pp                +21.37 pp
    metabolic           +31.65                   +11.66
    structural          +27.25                    +8.93
    sepsis              +22.80                    +5.58
    status              +37.64                    +4.93

A posterior dominant rhythm is the classical sign that thalamocortical machinery is intact, and the reading is
mechanistically direct: when that machinery survives, suppression is a STATE the brain is passing through; when
it does not, suppression is a property of the TISSUE. Anoxia shows much the smallest proportional collapse
(42 % against 63-87 % elsewhere), which is what one expects if post-anoxic suppression is the structural kind
even where some alpha generator persists.

WHY THAT RESULT CANNOT BE BELIEVED AS IT STANDS. Both flags were scored as "present on ANY of the patient's
reports". A patient who is suppressed on day 1 and recovers a posterior rhythm on day 6 is counted as
PDR-present, so the contrast is partly comparing patients who RECOVERED against patients who did not -- which
would produce exactly this result through reverse causation and would mean nothing. Three fixes, applied here:

  P1  SAME-RECORDING. Score both flags on the INDEX recording only -- the earliest EEG carrying burst
      suppression, or the earliest EEG overall for patients without it. A rhythm seen on the same study as the
      suppression cannot have been produced by later recovery.
      FALSIFIED IF the modification disappears when both are read off one recording.
  P2  FIRST-RECORDING-ONLY SUBSET. Restrict to patients with exactly ONE report, where "ever" and "on this
      study" are the same thing by construction and reverse causation is impossible.
      FALSIFIED IF the modification is absent in that subset.
  P3  DIRECTION. Among patients with serial recordings, a PDR appearing only on LATER studies should behave
      differently from one present at index. If the effect is carried entirely by late-appearing rhythms, it is
      recovery, not mechanism.
      FALSIFIED IF index-PDR shows no modification while later-PDR does.

  Registered expectation: some attenuation is expected once reverse causation is removed, because part of the
  "any report" contrast genuinely is recovery. The claim survives only if a substantial modification remains
  with both flags read off the same study. Stating that in advance so a shrunken effect is not narrated as a
  success -- a significance-only reading has already passed twice in this project on trivial effects.

WHY THIS MATTERS IF IT HOLDS. It is a named, classical, visually identifiable EEG feature that a clinician can
check in seconds, it has a mechanism that predicts its direction, and it modifies the interpretation of another
finding rather than merely adding to a risk score. That is the kind of object this project has been looking for,
and it is explainable in the strict sense -- no learned weights anywhere.
"""
import csv, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "1000"))
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
    # keep every report separately so index vs later can be distinguished
    reps = defaultdict(list)
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is None:
                continue
            has = lambda k: (r.get(k) or "").strip() not in ("", "None", "nan")
            reps[int(p)].append((t, has("bs"), has("pdr")))
    for p in reps:
        reps[p].sort()

    rows = []
    for p, v in reps.items():
        if p not in cond_seen:
            continue
        d = death.get(p)
        if d is None:
            continue
        t0 = v[0][0]
        days = (d - t0).days
        if days < -1:
            continue
        # INDEX recording = earliest carrying burst suppression, else the earliest overall
        idx = next((x for x in v if x[1]), v[0])
        ever_bs = any(x[1] for x in v)
        ever_pdr = any(x[2] for x in v)
        later_pdr = any(x[2] for x in v if x[0] > idx[0])
        rows.append(dict(d30=1.0 if (d - idx[0]).days <= 30 else 0.0,
                         n_rep=len(v),
                         bs_idx=1.0 if idx[1] else 0.0, pdr_idx=1.0 if idx[2] else 0.0,
                         bs_ever=1.0 if ever_bs else 0.0, pdr_ever=1.0 if ever_pdr else 0.0,
                         pdr_late=1.0 if (later_pdr and not idx[2]) else 0.0,
                         labs=aet.get(p, set())))
    n = len(rows)
    print(f"cohort: {n:,}   single-report patients: {sum(1 for r in rows if r['n_rep']==1):,}")

    def modif(R, bsk, pdrk, sub=None):
        """(BS effect | PDR absent, BS effect | PDR present) per aetiology."""
        out = {}
        S = R if sub is None else [r for r in R if sub(r)]
        for k in AE:
            g = [r for r in S if k in r["labs"]]
            vals = []
            for pv in (0.0, 1.0):
                h = [r for r in g if r[pdrk] == pv]
                a = [r["d30"] for r in h if r[bsk] == 1.0]
                b = [r["d30"] for r in h if r[bsk] == 0.0]
                if len(a) < 20 or len(b) < 20:
                    vals = None; break
                vals.append(float(np.mean(a) - np.mean(b)))
            if vals:
                out[k] = (vals[0], vals[1])
        return out

    def report(title, bsk, pdrk, sub=None):
        print("\n" + "=" * 88)
        print(title)
        print("=" * 88)
        obs = modif(rows, bsk, pdrk, sub)
        if not obs:
            print("   too few patients in one or more cells"); return
        boots = defaultdict(list)
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            o = modif([rows[j] for j in i], bsk, pdrk, sub)
            for k, v in o.items():
                boots[k].append(v[0] - v[1])
        print(f"   {'aetiology':12s} {'PDR absent':>13s} {'PDR present':>13s} {'modification':>14s} {'95% CI':>20s}")
        nsig = 0
        for k in AE:
            if k not in obs:
                continue
            b = boots.get(k, [])
            lo, hi = (np.percentile(b, [2.5, 97.5]) if len(b) > 100 else (float("nan"),) * 2)
            sig = lo > 0
            nsig += sig
            print(f"   {k:12s} {100*obs[k][0]:+12.2f} {100*obs[k][1]:+12.2f} "
                  f"{100*(obs[k][0]-obs[k][1]):+13.2f} [{100*lo:+8.2f},{100*hi:+8.2f}]{' *' if sig else ' ns'}")
        print(f"   -> modification excludes zero in {nsig}/{len(obs)} aetiologies")

    report("P1  BOTH FLAGS ON THE INDEX RECORDING (reverse causation impossible)", "bs_idx", "pdr_idx")
    report("P2  SINGLE-REPORT PATIENTS ONLY ('ever' and 'this study' identical by construction)",
           "bs_idx", "pdr_idx", sub=lambda r: r["n_rep"] == 1)
    report("REFERENCE  both flags scored 'ever', as in the original observation", "bs_ever", "pdr_ever")

    # ---- P3: is it recovery? ------------------------------------------------------------------------
    print("\n" + "=" * 88)
    print("P3  IS IT RECOVERY? PDR at index vs PDR appearing only LATER")
    print("=" * 88)
    print(f"   {'aetiology':12s} {'no PDR ever':>14s} {'PDR at index':>14s} {'PDR only later':>16s}")
    for k in AE:
        g = [r for r in rows if k in r["labs"] and r["n_rep"] >= 2]
        cells = []
        for name, sel in (("none", lambda r: r["pdr_idx"] == 0 and r["pdr_late"] == 0),
                          ("index", lambda r: r["pdr_idx"] == 1),
                          ("late", lambda r: r["pdr_late"] == 1)):
            h = [r for r in g if sel(r)]
            a = [r["d30"] for r in h if r["bs_idx"] == 1.0]
            b = [r["d30"] for r in h if r["bs_idx"] == 0.0]
            cells.append(f"{100*(np.mean(a)-np.mean(b)):+8.2f}pp" if len(a) >= 20 and len(b) >= 20
                         else "      n/a")
        print(f"   {k:12s} {cells[0]:>14s} {cells[1]:>14s} {cells[2]:>16s}")
    print("\n   If the modification is carried by LATE-appearing rhythms and absent at index, it is recovery")
    print("   rather than mechanism, and the finding should be withdrawn.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
