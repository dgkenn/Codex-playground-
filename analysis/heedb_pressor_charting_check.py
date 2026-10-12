#!/usr/bin/env python3
"""Is the vasopressor "withdrawal signature" real, or is it the EHR closing the medication record at death?

WHY THIS EXISTS. The vasopressor test (`heedb_wlst_pressor.py`) reported that 74.1 % of post-anoxic
burst-suppression patients dying within three days died within six hours of their last vasopressor ending, with
a MEDIAN GAP OF 0.0 HOURS -- and reported the same median in every other group, including ones where withdrawal
after burst suppression is not standard practice. A quantity that is identical across clinically dissimilar
groups is usually not measuring the clinic. The obvious alternative is that the administrative record simply
closes an open infusion at the time of death, in which case `end == death` by construction and the "signature"
measures charting rather than a decision.

The two are separable. A genuine withdrawal produces ends scattered over MINUTES TO HOURS before death, because
someone stops the drip and the patient dies some while later. A charting truncation produces a spike EXACTLY at
death and almost nothing in the hour before it.

  C1  What fraction of last-pressor-end times fall within one minute of the death time?
      An artefact predicts a large spike; a real decision predicts almost none.
  C2  What does the interval look like once exact ties are removed?
  C3  Does "a pressor was running at the moment of death" separate from the exact tie at all -- i.e. are there
      records that genuinely extend PAST the death time, which no truncation rule would produce?

Nothing here needs the EEG or S3; it is a property of the drug and death tables alone.
"""
import csv, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
PRESSORS = ("norepinephrine", "levophed", "epinephrine", "vasopressin", "phenylephrine",
            "neosynephrine", "dopamine", "dobutamine")


def main():
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass
    print(f"patients with a death record: {len(death):,}")

    last_before, past_death, n_exp = {}, defaultdict(int), 0
    with open(f"{OMOP}/drug_vasopressors.csv") as fh:
        for r in csv.DictReader(fh):
            v = (r.get("drug_source_value") or "").lower()
            if not any(x in v for x in PRESSORS):
                continue
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            d = death.get(p)
            if d is None:
                continue
            n_exp += 1
            e = dt(r.get("drug_exposure_end_datetime"))
            if e is None:
                continue
            if e > d:
                past_death[p] += 1
            else:
                if p not in last_before or e > last_before[p]:
                    last_before[p] = e
    print(f"vasopressor exposures in patients with an ascertained death: {n_exp:,}")

    gaps = np.array([(death[p] - e).total_seconds() / 3600.0 for p, e in last_before.items()])
    n = len(gaps)
    print(f"patients with at least one pressor ending at or before death: {n:,}")
    print(f"patients with at least one pressor record extending PAST death: {len(past_death):,}")

    print("\n" + "=" * 88)
    print("C1  HOW MANY LAST-PRESSOR ENDS COINCIDE EXACTLY WITH DEATH?")
    print("=" * 88)
    for lab, m in (("within 1 minute of death", gaps <= 1.0 / 60),
                   ("within 5 minutes", gaps <= 5.0 / 60),
                   ("within 1 hour", gaps <= 1.0),
                   ("within 6 hours", gaps <= 6.0),
                   ("within 24 hours", gaps <= 24.0)):
        print(f"   {lab:28s} {int(m.sum()):7,d}   {100*m.mean():5.1f}%")

    print("\n" + "=" * 88)
    print("C2  THE INTERVAL ONCE EXACT TIES ARE REMOVED")
    print("=" * 88)
    g2 = gaps[gaps > 1.0 / 60]
    if len(g2):
        qs = np.percentile(g2, [10, 25, 50, 75, 90])
        print(f"   n = {len(g2):,}   median {qs[2]:.1f} h   IQR {qs[1]:.1f}-{qs[3]:.1f} h   "
              f"p10 {qs[0]:.1f}  p90 {qs[4]:.1f}")
        for lab, m in (("of these, within 6 h", g2 <= 6.0), ("within 24 h", g2 <= 24.0)):
            print(f"   {lab:28s} {int(m.sum()):7,d}   {100*m.mean():5.1f}%")

    print("\n" + "=" * 88)
    print("C3  IS THERE ANY MASS IN THE CLINICALLY MEANINGFUL WINDOW?")
    print("=" * 88)
    print("   A withdrawal decision is followed by death after some interval -- minutes for a patient on high-dose")
    print("   pressors, hours for one on a little. So a real decision marker must put mass BETWEEN a few minutes")
    print("   and a day. A record closed automatically at death puts it all at exactly zero and nothing nearby.")
    print(f"   {'window before death':30s} {'n':>8s} {'% of all':>9s}")
    for lab, lo, hi in (("exactly 0 (tie)", -1e-9, 1e-9),
                        ("0 to 1 minute (exclusive)", 1e-9, 1.0 / 60),
                        ("1 minute to 1 hour", 1.0 / 60, 1.0),
                        ("1 to 6 hours", 1.0, 6.0),
                        ("6 to 24 hours", 6.0, 24.0),
                        ("1 to 7 days", 24.0, 168.0),
                        ("more than 7 days", 168.0, 1e12)):
        m = (gaps > lo) & (gaps <= hi)
        print(f"   {lab:30s} {int(m.sum()):8,d} {100*m.mean():8.1f}%")

    print("\n" + "=" * 88)
    print("C4  VERDICT")
    print("=" * 88)
    tie = float((gaps <= 1e-9).mean())
    near = float(((gaps > 1e-9) & (gaps <= 24.0)).mean())
    print(f"   exact ties {100*tie:.1f}% of patients; non-tied ends within a day of death {100*near:.1f}%")
    if tie > 0.10 and near < tie / 2:
        print("\n   THE INSTRUMENT FAILS. The last-pressor-end time is not a measurement of when support stopped.")
        print("   It is bimodal and degenerate: a spike EXACTLY at the death timestamp, and then a long tail")
        print("   whose mass sits days to months earlier -- a previous admission, not a terminal decision. The")
        print("   window in which a withdrawal would actually show up is nearly empty. The only consistent")
        print("   reading is that an infusion still running is closed out at the recorded time of death.")
        print("\n   Two consequences for the vasopressor analysis, both fatal to it:")
        print("     1. 'died within 6 h of the last pressor ending' is, to within a rounding error, the tie set.")
        print("        It counts in-hospital deaths on pressors. It does not identify withdrawal.")
        print("     2. 'a pressor was running at the moment of death' was defined as start <= death <= end, which")
        print("        an end stamped AT the death time also satisfies. The two columns of that table are")
        print("        therefore the SAME EVENT reported twice, which is why they moved together.")
        print(f"   Genuinely-past-death ends -- the only unambiguous 'running at death' -- number {len(past_death):,}")
        print("   and are too few to carry the analysis.")
        print("\n   CONCLUSION: withdrawal versus refractory shock is NOT answerable from vasopressor timing in")
        print("   this extraction. The question stays open and must be labelled open. The earlier run of")
        print("   heedb_wlst_pressor.py is retracted.")
    else:
        print("\n   USABLE: there is real mass in the hours before death, so the interval carries information")
        print("   about when support actually stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
