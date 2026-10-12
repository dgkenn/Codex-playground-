#!/usr/bin/env python3
"""What IS the 'unexplained' burst-suppression group? (exploratory, post-hoc -- labelled as such)

WHY THIS MATTERS. The review this project is answering (Guay, Agrawal, Tseng, Gallo, Schreier, Brown,
Anesthesiology 2025;143(6):1595-1618) says: "Determining the exact etiology of burst suppression in the ICU can be
challenging". In our cohort that difficulty is quantified: 35.4 % of burst-suppression patients with condition
data carry none of the five pre-registered aetiologies. That group is the single largest hole in
39_HEEDB_FINDINGS.md -- it is excluded from the interaction model rather than explained, and it is also the
LEAST-ascertained group (29.1 % have a death record, against 61.9 % for anoxic).

WHAT THE CODES SAY. Tabulating conditions in the 2,513 unexplained patients, the group is not miscellaneous. It is
dominated by seizure disorder that does not meet the status-epilepticus definition:

    78039  other convulsions (ICD-9)                                        42.4 %
    R569   unspecified convulsions (ICD-10)                                 37.9 %
    34590  epilepsy unspecified, not intractable (ICD-9)                    25.5 %
    G40909 epilepsy unspecified, not intractable, WITHOUT status (ICD-10)   22.8 %
    ... plus 34591, G40919, 34540, 34510, G40309, G40109, 34541, 34550     each 8-12 %

The pre-registered `status` category matches only the WITH-status codes (3453, 34561, 34571, G4101, G411, G412,
G419, G40901). G40909 differs from G40901 in exactly the digit that encodes "without status epilepticus", so this
is not a coding gap -- the dictionary is doing what it was written to do, and these patients are genuinely a
different group: epilepsy or convulsions, EEG ordered, no documented status.

REGISTERED PREDICTION, stated before running the model.
  Mechanism: in epilepsy-without-status, burst suppression is most plausibly PHARMACOLOGICAL -- the product of
  anti-seizure and anaesthetic infusions given to a brain that is not structurally dying -- rather than a marker
  of injury. That is the same iatrogenic phenotype the pre-registered H2 was about.
  Therefore: the 30-day timing coefficient for `epilepsy_nonstatus` should be NEGATIVE (these patients die LATER
  after the EEG), resembling status epilepticus (-7.29 pp) and opposite to anoxic injury (+29.52 pp).
  FALSIFIED IF: the coefficient is positive, or its interval covers zero with a point estimate above +5 pp. That
  would mean the unexplained group is not benign-pharmacological and the iatrogenic reading is wrong.

STATUS: EXPLORATORY. Adding a sixth category after seeing the data is a post-hoc refinement of the pre-registered
dictionary. It is reported as exploratory and does not enter the confirmatory result, whatever it shows. The
prediction above is registered in this docstring, in the commit that precedes the run, so that it cannot be
rewritten afterwards -- a failure mode this project has already committed once (see docs/LESSONS.md, P1/P2).

DESIGN: identical to the ascertainment-immune CHECK 2 in heedb_bs_ascertainment.py -- restrict to patients with a
recorded death and model how SOON they died. Helpers are imported from that module rather than reimplemented.
"""
import csv, os, sys
from collections import defaultdict, Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt, eeg_times   # validated; do not reimplement

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
NBOOT = int(os.environ.get("NBOOT", "2000"))

# epilepsy / convulsions that do NOT meet the status-epilepticus definition. Matched as: an epilepsy-family code
# that is not already claimed by the pre-registered `status` set, so the two categories cannot overlap by
# construction and no patient is counted twice.
EPI_FAMILY = ("345", "G40", "78039", "R569")
STATUS_CODES = AETIOLOGY["status"]


def is_epi_nonstatus(c):
    if not c or any(c.startswith(x) for x in STATUS_CODES):
        return False
    return any(c.startswith(x) for x in EPI_FAMILY)


def lpm(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def main():
    rng = np.random.default_rng(20260725)
    pids = {int(x) for x in open("/tmp/heedb_bs_patients.txt").read().split() if x.strip().isdigit()}

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
            if is_epi_nonstatus(c):
                aet[p].add("epilepsy_nonstatus")

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    base = sorted(pids & cond_seen)
    pre5 = list(AETIOLOGY)
    unexp_before = [p for p in base if not (aet.get(p, set()) & set(pre5))]
    absorbed = [p for p in unexp_before if "epilepsy_nonstatus" in aet.get(p, set())]
    print(f"burst-suppression patients with condition data: {len(base)}")
    print(f"  unexplained by the five pre-registered aetiologies : {len(unexp_before)} "
          f"({100*len(unexp_before)/max(len(base),1):.1f} %)")
    print(f"  of those, captured by epilepsy-without-status      : {len(absorbed)} "
          f"({100*len(absorbed)/max(len(unexp_before),1):.1f} % of the unexplained group)")
    print(f"  still unexplained after the refinement             : {len(unexp_before)-len(absorbed)} "
          f"({100*(len(unexp_before)-len(absorbed))/max(len(base),1):.1f} % of the cohort)")

    et = eeg_times()
    rows = []
    keys = pre5 + ["epilepsy_nonstatus"]
    for p in base:
        d, t = death.get(p), et.get(p)
        if d is None or t is None:
            continue
        days = (d - t).days
        if days < -1:
            continue
        labs = aet.get(p, set())
        rows.append(dict(d30=1.0 if days <= 30 else 0.0, d90=1.0 if days <= 90 else 0.0,
                         **{k: (1.0 if k in labs else 0.0) for k in keys}))
    n = len(rows)
    print(f"\nanalysable (death record + EEG time): {n} patients")
    if n < 300:
        print("insufficient"); return 1

    expo = [k for k in keys if sum(r[k] for r in rows) >= 30]
    for out, lab in (("d30", "death within 30 days"), ("d90", "death within 90 days")):
        y = np.asarray([r[out] for r in rows], float)
        X = np.column_stack([np.ones(n)] + [np.asarray([r[k] for r in rows], float) for k in expo])
        b = lpm(X, y)
        boots = defaultdict(list)
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            try:
                bb = lpm(X[i], y[i])
            except Exception:
                continue
            for j, k in enumerate(expo, 1):
                boots[k].append(bb[j])
        print(f"\n   --- {lab} (baseline {100*y.mean():.1f} %) ---")
        for j, k in enumerate(expo, 1):
            lo, hi = np.percentile(boots[k], [2.5, 97.5])
            star = "*" if lo > 0 or hi < 0 else "ns"
            mark = "   <-- REGISTERED PREDICTION: negative" if k == "epilepsy_nonstatus" else ""
            print(f"      {k:20s} {100*b[j]:+7.2f} pp [{100*lo:+7.2f},{100*hi:+7.2f}] {star}{mark}")

    print("\n   EXPLORATORY. The sixth category was added after inspecting the codes in the unexplained group,")
    print("   so this is a post-hoc refinement and does not enter the confirmatory result. The prediction that")
    print("   epilepsy-without-status would be NEGATIVE was registered in this file's docstring and committed")
    print("   before the model was fit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
