#!/usr/bin/env python3
"""What is burden a marker OF? Dead cortex cannot seize -- so ask whether it seizes later.

WHY THIS EXISTS. The intended instrument for this question was neuron-specific enolase, the guideline-endorsed
serum marker of neuronal death after arrest. It is not available: a scan of all 551 parts of the merged
`measurement` table returned essentially no NSE assays for this cohort. NSE is a send-out test and is not part
of routine care at these sites. That is a fact about the data source, not about the biology, and it forces a
different external reference.

THE IDEA. There is one already in the recordings, and it is arguably sharper than a serum marker because it is
mechanistic rather than correlational: **cortex that has died cannot generate epileptiform activity.** Seizures,
periodic discharges and rhythmic patterns are all produced by living, synaptically connected neurons. So the two
candidate readings of burden make OPPOSITE predictions about what the same brain does days later:

  STRUCTURAL LOSS -- burden counts cortex that is already gone. A patient who survives with a high index burden
  has less viable cortex left, so their LATER recordings should show LESS epileptiform activity. Burden should
  predict its ABSENCE.

  REVERSIBLE SUPPRESSION -- burden measures how deeply a living cortex is currently suppressed, whether by
  metabolic failure or by drug. Living cortex emerging from suppression is famously irritable, so high burden
  should predict the SAME or MORE epileptiform activity later, not less.

This is the rare test where the two hypotheses do not merely differ in effect size but in SIGN.

REGISTERED PREDICTIONS.
  E1  Among post-anoxic patients ALIVE at a later recording, higher index suppression burden predicts a LOWER
      probability of epileptiform activity (seizure, status, GPD, LPD) on that later recording.
      STRUCTURAL PREDICTS a negative association. REVERSIBLE PREDICTS null or positive.
  E2  The association survives adjustment for whether suppression is still present on the later recording.
      This matters because ongoing suppression trivially suppresses epileptiform activity: if the effect
      disappears once that is controlled, this is measuring "still suppressed", not "cortex gone".
  E3  DOSE. The association is monotone across burden quartiles rather than driven by an extreme group.

THE TRAP, and how it is handled. A patient must survive to have a later recording, so the cohort is landmarked
at that later recording: everyone in it was alive at that moment. Without this, index burden would predict the
later finding partly by killing the patients who would have had it -- which is the immortal-time trap that made
an earlier persistence analysis in this project uninterpretable.

A SECOND, INDEPENDENT LIMIT worth stating plainly. Anti-seizure drugs suppress epileptiform activity and are
given more often to sicker patients. That confound is not fully removable here, and it pushes in the same
direction as the structural hypothesis, so a confirmed E1 is suggestive rather than decisive on its own. E2 is
what separates "cortex gone" from "still suppressed"; nothing available here separates it from "more heavily
treated".
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "600"))
MIN_GAP_D = float(os.environ.get("MIN_GAP_D", "1"))
MAX_GAP_D = float(os.environ.get("MAX_GAP_D", "21"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"

EPI = ("seizure", "status", "gpd", "lpd")


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def main():
    rng = np.random.default_rng(20260726)

    # index-recording burden, matching the main analysis (NOT the max over all recordings)
    burden = {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, s, v = int(r["patient"]), int(r["session"]), float(r["burden"])
            except Exception:
                continue
            if v == v and (p not in burden or s < burden[p][0]):
                burden[p] = (s, v)
    burden = {p: v for p, (s, v) in burden.items()}

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

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

    # every report, kept per recording so a LATER one can be examined
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    recs = defaultdict(list)
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
            f = {k: ((r.get(k) or "").strip() not in ("", "None", "nan"))
                 for k in EPI + ("bs", "low voltage", "gen slowing", "pdr")}
            recs[int(p)].append((t, f))
    for p in recs:
        recs[p].sort(key=lambda x: x[0])

    rows = []
    for p, lst in recs.items():
        if p not in cond_seen or p not in burden or len(lst) < 2:
            continue
        t0, f0 = lst[0]
        later = next(((t, f) for t, f in lst[1:]
                      if MIN_GAP_D <= (t - t0).total_seconds() / 86400.0 <= MAX_GAP_D), None)
        if later is None:
            continue
        t1, f1 = later
        d = death.get(p)
        if d is not None and d < t1:
            continue                      # LANDMARK: alive at the later recording
        rows.append(dict(pid=p, bur=burden[p],
                         epi_idx=1.0 if any(f0[k] for k in EPI) else 0.0,
                         epi_late=1.0 if any(f1[k] for k in EPI) else 0.0,
                         bs_late=1.0 if f1["bs"] else 0.0,
                         slow_late=1.0 if f1["gen slowing"] else 0.0,
                         gap=(t1 - t0).total_seconds() / 86400.0,
                         labs=aet.get(p, set())))
    g = [r for r in rows if "anoxic" in r["labs"]]
    print(f"patients with a later recording {MIN_GAP_D:.0f}-{MAX_GAP_D:.0f} d after the index, alive at it: "
          f"{len(rows):,}   post-anoxic: {len(g):,}")
    if len(g) < 100:
        print("*** too few post-anoxic; reporting the all-aetiology cohort as well")
    use = g if len(g) >= 100 else rows
    n = len(use)
    if n < 100:
        print("*** insufficient")
        return 1
    print(f"   median interval {np.median([r['gap'] for r in use]):.1f} d   "
          f"epileptiform on the later recording: {100*np.mean([r['epi_late'] for r in use]):.1f}%   "
          f"still suppressed: {100*np.mean([r['bs_late'] for r in use]):.1f}%")

    b = np.array([r["bur"] for r in use]); y = np.array([r["epi_late"] for r in use])

    # ---- E1 / E3 ------------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("E1/E3  DOES A HIGHER INDEX BURDEN PREDICT LESS EPILEPTIFORM ACTIVITY LATER?")
    print("=" * 92)
    q = np.percentile(b, [25, 50, 75])
    print(f"   {'index burden':18s} {'n':>6s} {'epileptiform later':>20s} {'still suppressed':>18s}")
    for lab, sel in (("Q1 lowest", b <= q[0]), ("Q2", (b > q[0]) & (b <= q[1])),
                     ("Q3", (b > q[1]) & (b <= q[2])), ("Q4 highest", b > q[2])):
        if sel.sum() >= 15:
            print(f"   {lab:18s} {int(sel.sum()):6d} {100*y[sel].mean():19.1f}% "
                  f"{100*np.mean([r['bs_late'] for r, x in zip(use, sel) if x]):17.1f}%")
    hi, lo = b > q[2], b <= q[0]
    obs = float(y[hi].mean() - y[lo].mean())
    d = []
    for _ in range(NBOOT):
        i = rng.integers(0, n, n)
        bb, yy = b[i], y[i]
        qq = np.percentile(bb, [25, 75])
        h, l = bb > qq[1], bb <= qq[0]
        if h.sum() >= 10 and l.sum() >= 10:
            d.append(float(yy[h].mean() - yy[l].mean()))
    lo_c, hi_c = np.percentile(d, [2.5, 97.5]) if len(d) > 100 else (float("nan"),) * 2
    print(f"\n   highest minus lowest burden quartile: {100*obs:+.1f} pp [{100*lo_c:+.1f},{100*hi_c:+.1f}]")
    if hi_c < 0:
        print("   E1 CONFIRMED -- STRUCTURAL. More index suppression, less epileptiform activity in the")
        print("   surviving brain days later. Cortex that is gone cannot discharge.")
    elif lo_c > 0:
        print("   E1 REVERSED -- more index suppression predicts MORE later epileptiform activity, which is")
        print("   what irritable but LIVING cortex emerging from suppression does.")
    else:
        print("   E1 NULL -- no association in either direction; this instrument does not separate them.")

    # ---- E2: is it just that they are still suppressed? --------------------------------------------
    print("\n" + "=" * 92)
    print("E2  IS IT 'CORTEX GONE', OR MERELY 'STILL SUPPRESSED'?")
    print("=" * 92)
    sub = [r for r in use if r["bs_late"] == 0.0]
    print(f"   restricted to patients NO LONGER suppressed on the later recording: n={len(sub):,}")
    if len(sub) >= 80:
        bb = np.array([r["bur"] for r in sub]); yy = np.array([r["epi_late"] for r in sub])
        qq = np.percentile(bb, [25, 75])
        h, l = bb > qq[1], bb <= qq[0]
        if h.sum() >= 15 and l.sum() >= 15:
            o2 = float(yy[h].mean() - yy[l].mean())
            d2 = []
            for _ in range(NBOOT):
                i = rng.integers(0, len(sub), len(sub))
                b2, y2 = bb[i], yy[i]
                q2 = np.percentile(b2, [25, 75])
                hh, ll = b2 > q2[1], b2 <= q2[0]
                if hh.sum() >= 8 and ll.sum() >= 8:
                    d2.append(float(y2[hh].mean() - y2[ll].mean()))
            l2, h2 = np.percentile(d2, [2.5, 97.5]) if len(d2) > 100 else (float("nan"),) * 2
            print(f"   highest minus lowest burden quartile: {100*o2:+.1f} pp [{100*l2:+.1f},{100*h2:+.1f}]")
            print(f"   E2 {'SURVIVES' if h2 < 0 else 'DOES NOT SURVIVE'} the control.")
            if h2 >= 0:
                print("   Without it, E1 is consistent with nothing more than ongoing suppression suppressing")
                print("   discharges, which says nothing about whether the cortex is gone.")
    else:
        print("   too few unsuppressed later recordings to run the control")

    print("\n   LIMIT that cannot be removed here: anti-seizure drugs suppress epileptiform activity and are")
    print("   given more often to sicker patients, which pushes the same way as the structural hypothesis.")
    print("   E2 separates 'cortex gone' from 'still suppressed'. Nothing available separates it from")
    print("   'more heavily treated'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
