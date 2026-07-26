#!/usr/bin/env python3
"""Withdrawal or refractory shock? Terminal extubation as the instrument -- the fourth attempt.

THE QUESTION, and why it will not go away. Forty-six per cent of patients in the guideline's highly-malignant
category die within three days, and measured suppression burden stratifies that early mortality from 29.5 % to
73.1 %. Burst suppression is also a criterion that informs withdrawal of life-sustaining therapy. So either the
EEG is describing patients who were dying anyway, or it is partly causing the outcome it predicts. The finding
means something different in each case and the difference is not cosmetic.

THREE INSTRUMENTS HAVE ALREADY FAILED, all in the same way -- they were STATE tables asked a DECISION question:
  * DNR / palliative-care codes: chronic care-limitation status, median 42 days from code to death.
  * Sedation depth: circular, because burst suppression itself causes unresponsiveness.
  * Vasopressor discontinuation: the medication record is CLOSED AT DEATH. 20.9 % of last-pressor ends were
    tied to the death timestamp to the minute and NOT ONE patient in the database had one falling between a
    minute and an hour before death. The signature was charting.

WHY A PROCEDURE IS DIFFERENT. Extubation is an act. Somebody does it, at a time, and it is recorded because it
happened rather than because a record was closed. A terminal extubation in a ventilated patient is followed by
death over minutes to hours, and -- unlike stopping a pressor -- it is not something an information system does
automatically when a patient dies.

  A0  THE ARTEFACT CHECK, WHICH RUNS FIRST AND CAN VETO EVERYTHING BELOW. Distribution of the interval from
      last extubation to death. A real decision puts mass over minutes to hours. A charting artefact puts a
      spike exactly at the death timestamp and a void beside it. If A0 shows the spike, this instrument is dead
      too and nothing after it may be quoted. This check exists because the vasopressor analysis produced a
      publishable-looking number and was only caught afterwards.
  P1  Among post-anoxic burst-suppression patients dying within three days, what fraction were extubated in the
      hours before death?
  P2  SPECIFICITY. That fraction should be HIGHER after cardiac arrest than in sepsis, because burst
      suppression is a withdrawal criterion after arrest and is not one in sepsis. Equal fractions would mean
      the marker is tracking dying-in-an-ICU rather than the decision.
  P3  THE ONE THAT MATTERS. Does the signature rise with BURDEN? If clinicians act on a more suppressed EEG,
      the burden-mortality gradient this project's main result rests on is partly a decision. If the signature
      is FLAT across burden while mortality climbs from 29.5 % to 73.1 %, the gradient is not explained by
      withdrawal.

INTERPRETATION, FIXED IN ADVANCE. A strong withdrawal signature does NOT invalidate the finding: burst
suppression would still identify the patients who die and the information would still be in the recording. It
changes what the finding IS -- a description of how the EEG is currently acted on rather than of how these
brains behave. Both are reportable. Conflating them is not.
"""
import csv, glob, io, os, re, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "600"))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"

# Classification happens on the CONCEPT NAME, not on procedure_source_value. The source value in this
# database is a numeric billing code ("36415" is a venipuncture), so text matching against it silently
# returns nothing -- which is how the first version of this analysis produced an empty instrument that
# looked like a clean negative.
CONCEPT_NAMES = os.environ.get("CONCEPT_NAMES", "/tmp/eeg_probe/concept_names_procedure.csv")
EXTUB = re.compile(r"extubation of trachea|extubation \(|^extubation", re.I)
COMFORT = re.compile(r"comfort care|comfort measures|palliative care|hospice care|terminal wean|"
                     r"withdraw\w* of (life|treatment|care)", re.I)
VENT = re.compile(r"mechanical ventilat|invasive ventilat|artificial respirat|respiratory ventilat|"
                  r"endotracheal intubat|insertion of endotracheal|^intubation|tracheostom", re.I)


def load_concept_names(path):
    """concept_id -> name, for classifying the extracted procedure rows."""
    m = {}
    if not os.path.exists(path):
        return m
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                m[int(r["concept_id"])] = (r.get("concept_name") or "")
            except Exception:
                continue
    return m


def main():
    rng = np.random.default_rng(20260726)

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    # last extubation at or before death; any comfort-care procedure; ever ventilated
    last_ext, comfort, vented = {}, set(), set()
    path = f"{OMOP}/procedure_life_support.csv"
    if not os.path.exists(path):
        print(f"missing {path} -- run: PIDS_FILE=/tmp/heedb_eeg_all_patients.txt python "
              "analysis/heedb_omop_extract.py procedure_life_support")
        return 1
    cname = load_concept_names(CONCEPT_NAMES)
    if not cname:
        print(f"missing {CONCEPT_NAMES} -- run: python analysis/heedb_concept_select.py procedure")
        return 1
    print(f"concept names loaded: {len(cname):,}")
    nrow = 0
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            nrow += 1
            try:
                v = cname.get(int(r.get("procedure_concept_id") or 0), "")
            except Exception:
                v = ""
            t = dt(r.get("procedure_datetime") or r.get("procedure_date") or "")
            if VENT.search(v):
                vented.add(p)
            if COMFORT.search(v):
                comfort.add(p)
            if t is None or not EXTUB.search(v):
                continue
            d = death.get(p)
            if d is None or t > d:
                continue
            if p not in last_ext or t > last_ext[p]:
                last_ext[p] = t
    print(f"procedure rows: {nrow:,}   ever ventilated: {len(vented):,}   "
          f"comfort-care procedure: {len(comfort):,}   extubation before death: {len(last_ext):,}")

    # ---- A0: the veto -------------------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("A0  ARTEFACT CHECK -- is the extubation time a decision, or a record closed at death?")
    print("=" * 92)
    gaps = np.array([(death[p] - t).total_seconds() / 3600.0 for p, t in last_ext.items()])
    if len(gaps) < 50:
        print(f"   only {len(gaps)} extubations before death; instrument unusable at this extraction depth")
        return 1
    print(f"   {'window before death':30s} {'n':>8s} {'%':>8s}")
    bands = (("exactly 0 (tied)", -1e-9, 1e-9), ("0 to 1 minute", 1e-9, 1 / 60), ("1 min to 1 hour", 1 / 60, 1.0),
             ("1 to 6 hours", 1.0, 6.0), ("6 to 24 hours", 6.0, 24.0), ("1 to 7 days", 24.0, 168.0),
             ("more than 7 days", 168.0, 1e12))
    for lab, lo, hi in bands:
        m = (gaps > lo) & (gaps <= hi)
        print(f"   {lab:30s} {int(m.sum()):8,d} {100*m.mean():7.1f}%")
    tie = float((gaps <= 1e-9).mean())
    near = float(((gaps > 1e-9) & (gaps <= 24.0)).mean())
    print(f"\n   tied to the death timestamp {100*tie:.1f}%   genuinely within a day {100*near:.1f}%")
    if tie > 0.10 and near < tie / 2:
        print("\n   *** VETO: same charting artefact as the vasopressor instrument. Nothing below may be")
        print("   quoted. The withdrawal question remains open and this is the fourth failed instrument.")
        return 2
    print("\n   USABLE: the interval has real mass in the hours before death, which a record closed")
    print("   automatically at the time of death cannot produce.")

    # ---- cohort -------------------------------------------------------------------------------------
    burden = {}
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, s, v = int(r["patient"]), int(r["session"]), float(r["burden"])
            except Exception:
                continue
            if v == v:
                # index recording, matching the main analysis -- NOT the max over all recordings
                if p not in burden or s < burden[p][0]:
                    burden[p] = (s, v)
    burden = {p: v for p, (s, v) in burden.items()}

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
            cur = (r.get("bs") or "").strip() not in ("", "None", "nan")
            if p not in when or t < when[p]:
                when[p] = t
                bs[p] = cur          # index recording only, matching the main analysis

    rows = []
    for p, t0 in when.items():
        d = death.get(p)
        if p not in cond_seen or d is None or p not in vented:
            continue
        days = (d - t0).days
        if days < -1:
            continue
        g = (d - last_ext[p]).total_seconds() / 3600.0 if p in last_ext else float("nan")
        rows.append(dict(pid=p, days=float(days), d3=1.0 if days <= 3 else 0.0,
                         bs=1.0 if bs.get(p) else 0.0, gap_h=g,
                         ext24=1.0 if (g == g and 0 <= g <= 24) else 0.0,
                         comfort=1.0 if p in comfort else 0.0,
                         bur=burden.get(p, float("nan")), labs=aet.get(p, set())))
    print(f"\nanalysable (ventilated, EEG, ascertained death): {len(rows):,}")

    def sig(g):
        if len(g) < 25:
            return None
        return (len(g), float(np.mean([r["ext24"] for r in g])), float(np.mean([r["comfort"] for r in g])))

    print("\n" + "=" * 92)
    print("P1/P2  EXTUBATED IN THE 24 h BEFORE DEATH, among those dying within three days")
    print("=" * 92)
    print(f"   {'group':28s} {'n':>6s} {'extubated <=24h':>17s} {'comfort-care proc':>19s}")
    for k in ("anoxic", "sepsis", "metabolic", "structural"):
        for bv, nm in ((1.0, "BS+"), (0.0, "BS-")):
            s = sig([r for r in rows if k in r["labs"] and r["bs"] == bv and r["d3"] == 1.0])
            if s:
                print(f"   {k+' '+nm:28s} {s[0]:6d} {100*s[1]:16.1f}% {100*s[2]:18.1f}%")
    print("\n   P2 predicts the anoxic BS+ figure exceeds the sepsis BS+ figure: burst suppression is a")
    print("   withdrawal criterion after arrest and is not one in sepsis. Equal fractions would mean this")
    print("   is tracking death in an ICU rather than the decision.")

    print("\n" + "=" * 92)
    print("P3  DOES THE SIGNATURE TRACK BURDEN?  (post-anoxic burst suppression, died <=3 d)")
    print("=" * 92)
    ga = [r for r in rows if "anoxic" in r["labs"] and r["bs"] == 1.0 and r["d3"] == 1.0
          and r["bur"] == r["bur"]]
    print(f"   n={len(ga):,}")
    if len(ga) >= 90:
        b = np.array([r["bur"] for r in ga])
        q = np.percentile(b, [33, 67])
        print(f"   {'burden tertile':16s} {'n':>6s} {'extubated <=24h':>17s} {'comfort-care proc':>19s}")
        for lab, sel in (("low", b <= q[0]), ("mid", (b > q[0]) & (b <= q[1])), ("high", b > q[1])):
            s = sig([r for r, x in zip(ga, sel) if x])
            if s:
                print(f"   {lab:16s} {s[0]:6d} {100*s[1]:16.1f}% {100*s[2]:18.1f}%")
        lo_t = [r for r, x in zip(ga, b <= q[0]) if x]
        hi_t = [r for r, x in zip(ga, b > q[1]) if x]
        if len(lo_t) >= 25 and len(hi_t) >= 25:
            d = []
            for _ in range(NBOOT):
                i = rng.integers(0, len(lo_t), len(lo_t)); j = rng.integers(0, len(hi_t), len(hi_t))
                d.append(np.mean([hi_t[x]["ext24"] for x in j]) - np.mean([lo_t[x]["ext24"] for x in i]))
            l, h = np.percentile(d, [2.5, 97.5])
            obs = np.mean([r["ext24"] for r in hi_t]) - np.mean([r["ext24"] for r in lo_t])
            print(f"\n   high minus low tertile: {100*obs:+.1f} pp [{100*l:+.1f},{100*h:+.1f}]")
            print(f"   {'MEDIATED (signature rises with burden)' if l > 0 else 'NOT MEDIATED (flat across burden)'}")
            print("   Mortality across these tertiles runs 29.5 % to 73.1 %. If the withdrawal signature is")
            print("   flat while mortality nearly triples, the gradient is not a decision artefact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
